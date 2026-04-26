from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.database import get_connection, row_to_dict
from backend.app.routers.utils import new_id, utc_now
from backend.app.schemas import (
    CalendarEventOut,
    TimeBlockCreate,
    TimeBlockOut,
    TimeBlockUpdate,
)

router = APIRouter(prefix="/api", tags=["calendar"])


@router.get("/time-blocks", response_model=list[TimeBlockOut])
def list_time_blocks() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, task_id, start_at, end_at, created_at FROM time_blocks ORDER BY start_at ASC"
        ).fetchall()
    return [row_to_dict(row) for row in rows]


@router.post("/time-blocks", response_model=TimeBlockOut, status_code=201)
def create_time_block(payload: TimeBlockCreate) -> dict:
    if payload.end_at <= payload.start_at:
        raise HTTPException(status_code=400, detail="end_at must be after start_at")

    block_id = new_id()
    now = utc_now()

    with get_connection() as conn:
        task_exists = conn.execute(
            "SELECT id FROM tasks WHERE id = ?", (payload.task_id,)
        ).fetchone()
        if task_exists is None:
            raise HTTPException(status_code=400, detail="task_id does not exist")

        conn.execute(
            (
                "INSERT INTO time_blocks (id, task_id, start_at, end_at, created_at) "
                "VALUES (?, ?, ?, ?, ?)"
            ),
            (
                block_id,
                payload.task_id,
                payload.start_at.isoformat(),
                payload.end_at.isoformat(),
                now,
            ),
        )
        row = conn.execute(
            "SELECT id, task_id, start_at, end_at, created_at FROM time_blocks WHERE id = ?",
            (block_id,),
        ).fetchone()
    return row_to_dict(row)


@router.patch("/time-blocks/{block_id}", response_model=TimeBlockOut)
def update_time_block(block_id: str, payload: TimeBlockUpdate) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id, task_id, start_at, end_at, created_at FROM time_blocks WHERE id = ?",
            (block_id,),
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Time block not found")

        current = row_to_dict(existing)
        next_start = updates.get("start_at", current["start_at"])
        next_end = updates.get("end_at", current["end_at"])

        if hasattr(next_start, "isoformat"):
            next_start = next_start.isoformat()
        if hasattr(next_end, "isoformat"):
            next_end = next_end.isoformat()

        if next_end <= next_start:
            raise HTTPException(status_code=400, detail="end_at must be after start_at")

        fields: list[str] = []
        values: list[str] = []
        for key, value in updates.items():
            fields.append(f"{key} = ?")
            values.append(value.isoformat() if hasattr(value, "isoformat") else value)
        values.append(block_id)

        conn.execute(
            f"UPDATE time_blocks SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )
        row = conn.execute(
            "SELECT id, task_id, start_at, end_at, created_at FROM time_blocks WHERE id = ?",
            (block_id,),
        ).fetchone()
    return row_to_dict(row)


@router.delete("/time-blocks/{block_id}", status_code=200)
def delete_time_block(block_id: str) -> None:
    with get_connection() as conn:
        result = conn.execute("DELETE FROM time_blocks WHERE id = ?", (block_id,))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Time block not found")


@router.get("/calendar", response_model=list[CalendarEventOut])
def calendar_view() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            (
                "SELECT "
                "tb.id AS block_id, tb.task_id, tb.start_at, tb.end_at, tb.created_at AS block_created_at, "
                "t.id AS task_id_ref, t.title, t.note, t.status, t.priority, t.duration_min, t.deadline, "
                "t.list_id, t.sprint_id, t.sprint_direction_id, t.created_at AS task_created_at, "
                "t.updated_at AS task_updated_at "
                "FROM time_blocks tb JOIN tasks t ON t.id = tb.task_id "
                "ORDER BY tb.start_at ASC"
            )
        ).fetchall()

    events: list[dict] = []
    for row in rows:
        events.append(
            {
                "block": {
                    "id": row["block_id"],
                    "task_id": row["task_id"],
                    "start_at": row["start_at"],
                    "end_at": row["end_at"],
                    "created_at": row["block_created_at"],
                },
                "task": {
                    "id": row["task_id_ref"],
                    "title": row["title"],
                    "note": row["note"],
                    "status": row["status"],
                    "priority": row["priority"],
                    "duration_min": row["duration_min"],
                    "deadline": row["deadline"],
                    "list_id": row["list_id"],
                    "sprint_id": row["sprint_id"],
                    "sprint_direction_id": row["sprint_direction_id"],
                    "created_at": row["task_created_at"],
                    "updated_at": row["task_updated_at"],
                },
            }
        )
    return events
