from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.database import get_connection, row_to_dict
from backend.app.routers.utils import new_id, utc_now
from backend.app.schemas import (
    SprintCreate,
    SprintDirectionOut,
    SprintDirectionUpdate,
    SprintOut,
    SprintUpdate,
)

router = APIRouter(prefix="/api/sprints", tags=["sprints"])


def _fetch_directions(conn, sprint_id: str) -> list[dict]:
    rows = conn.execute(
        (
            "SELECT id, sprint_id, name, position, created_at "
            "FROM sprint_directions WHERE sprint_id = ? ORDER BY position ASC"
        ),
        (sprint_id,),
    ).fetchall()
    return [row_to_dict(row) for row in rows]


def _fetch_sprint(conn, sprint_id: str) -> dict | None:
    row = conn.execute(
        "SELECT id, name, start_date, end_date, created_at FROM sprints WHERE id = ?",
        (sprint_id,),
    ).fetchone()
    sprint = row_to_dict(row)
    if sprint is None:
        return None
    sprint["directions"] = _fetch_directions(conn, sprint_id)
    return sprint


@router.get("", response_model=list[SprintOut])
def list_sprints() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id FROM sprints ORDER BY created_at DESC"
        ).fetchall()
        return [_fetch_sprint(conn, row["id"]) for row in rows]


@router.post("", response_model=SprintOut, status_code=201)
def create_sprint(payload: SprintCreate) -> dict:
    sprint_id = new_id()
    now = utc_now()
    with get_connection() as conn:
        conn.execute(
            (
                "INSERT INTO sprints (id, name, start_date, end_date, created_at) "
                "VALUES (?, ?, ?, ?, ?)"
            ),
            (
                sprint_id,
                payload.name,
                payload.start_date.isoformat() if payload.start_date else None,
                payload.end_date.isoformat() if payload.end_date else None,
                now,
            ),
        )

        for index, direction_name in enumerate(payload.directions):
            conn.execute(
                (
                    "INSERT INTO sprint_directions (id, sprint_id, name, position, created_at) "
                    "VALUES (?, ?, ?, ?, ?)"
                ),
                (new_id(), sprint_id, direction_name, index, now),
            )

        sprint = _fetch_sprint(conn, sprint_id)
    return sprint


@router.patch("/{sprint_id}", response_model=SprintOut)
def update_sprint(sprint_id: str, payload: SprintUpdate) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    with get_connection() as conn:
        exists = conn.execute(
            "SELECT id FROM sprints WHERE id = ?", (sprint_id,)
        ).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="Sprint not found")

        mapped: dict[str, str | None] = {}
        for key, value in updates.items():
            mapped[key] = (
                value.isoformat() if hasattr(value, "isoformat") and value else value
            )

        fields: list[str] = []
        values: list[str | None] = []
        for key, value in mapped.items():
            fields.append(f"{key} = ?")
            values.append(value)
        values.append(sprint_id)
        conn.execute(
            f"UPDATE sprints SET {', '.join(fields)} WHERE id = ?", tuple(values)
        )

        sprint = _fetch_sprint(conn, sprint_id)
    return sprint


@router.delete("/{sprint_id}", status_code=200)
def delete_sprint(sprint_id: str) -> None:
    with get_connection() as conn:
        result = conn.execute("DELETE FROM sprints WHERE id = ?", (sprint_id,))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Sprint not found")


@router.patch("/directions/{direction_id}", response_model=SprintDirectionOut)
def update_direction(direction_id: str, payload: SprintDirectionUpdate) -> dict:
    with get_connection() as conn:
        exists = conn.execute(
            "SELECT id FROM sprint_directions WHERE id = ?", (direction_id,)
        ).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="Direction not found")

        conn.execute(
            "UPDATE sprint_directions SET name = ? WHERE id = ?",
            (payload.name, direction_id),
        )
        row = conn.execute(
            (
                "SELECT id, sprint_id, name, position, created_at "
                "FROM sprint_directions WHERE id = ?"
            ),
            (direction_id,),
        ).fetchone()
    return row_to_dict(row)
