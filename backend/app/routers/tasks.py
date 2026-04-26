from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.app.database import get_connection, row_to_dict
from backend.app.routers.utils import new_id, utc_now
from backend.app.schemas import TaskCreate, TaskMove, TaskOut, TaskUpdate

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


TASK_SELECT = (
    "SELECT id, title, note, status, priority, duration_min, deadline, list_id, "
    "sprint_id, sprint_direction_id, created_at, updated_at FROM tasks"
)


def _validate_refs(
    conn, list_id: str, sprint_id: str | None, sprint_direction_id: str | None
) -> None:
    list_exists = conn.execute(
        "SELECT id FROM task_lists WHERE id = ?", (list_id,)
    ).fetchone()
    if list_exists is None:
        raise HTTPException(status_code=400, detail="list_id does not exist")

    if sprint_id is not None:
        sprint_exists = conn.execute(
            "SELECT id FROM sprints WHERE id = ?", (sprint_id,)
        ).fetchone()
        if sprint_exists is None:
            raise HTTPException(status_code=400, detail="sprint_id does not exist")

    if sprint_direction_id is not None:
        direction_exists = conn.execute(
            "SELECT id, sprint_id FROM sprint_directions WHERE id = ?",
            (sprint_direction_id,),
        ).fetchone()
        if direction_exists is None:
            raise HTTPException(
                status_code=400, detail="sprint_direction_id does not exist"
            )
        if sprint_id is not None and direction_exists["sprint_id"] != sprint_id:
            raise HTTPException(
                status_code=400,
                detail="sprint_direction_id does not belong to sprint_id",
            )


@router.get("", response_model=list[TaskOut])
def list_tasks(
    status: str | None = Query(default=None),
    list_id: str | None = Query(default=None),
    sprint_id: str | None = Query(default=None),
) -> list[dict]:
    where: list[str] = []
    params: list[str] = []

    if status:
        where.append("status = ?")
        params.append(status)
    if list_id:
        where.append("list_id = ?")
        params.append(list_id)
    if sprint_id:
        where.append("sprint_id = ?")
        params.append(sprint_id)

    query = TASK_SELECT
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY created_at DESC"

    with get_connection() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    return [row_to_dict(row) for row in rows]


@router.post("", response_model=TaskOut, status_code=201)
def create_task(payload: TaskCreate) -> dict:
    task_id = new_id()
    now = utc_now()

    with get_connection() as conn:
        _validate_refs(
            conn, payload.list_id, payload.sprint_id, payload.sprint_direction_id
        )

        conn.execute(
            (
                "INSERT INTO tasks (id, title, note, status, priority, duration_min, deadline, list_id, "
                "sprint_id, sprint_direction_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            (
                task_id,
                payload.title,
                payload.note,
                payload.status,
                payload.priority,
                payload.duration_min,
                payload.deadline.isoformat() if payload.deadline else None,
                payload.list_id,
                payload.sprint_id,
                payload.sprint_direction_id,
                now,
                now,
            ),
        )
        row = conn.execute(f"{TASK_SELECT} WHERE id = ?", (task_id,)).fetchone()
    return row_to_dict(row)


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(task_id: str, payload: TaskUpdate) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    with get_connection() as conn:
        existing = conn.execute(f"{TASK_SELECT} WHERE id = ?", (task_id,)).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Task not found")

        merged = row_to_dict(existing)
        for key, value in updates.items():
            merged[key] = (
                value.isoformat() if hasattr(value, "isoformat") and value else value
            )
        _validate_refs(
            conn, merged["list_id"], merged["sprint_id"], merged["sprint_direction_id"]
        )

        fields: list[str] = []
        values: list[str | int | None] = []
        for key, value in updates.items():
            fields.append(f"{key} = ?")
            if hasattr(value, "isoformat") and value is not None:
                values.append(value.isoformat())
            else:
                values.append(value)
        fields.append("updated_at = ?")
        values.append(utc_now())
        values.append(task_id)

        conn.execute(
            f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", tuple(values)
        )
        row = conn.execute(f"{TASK_SELECT} WHERE id = ?", (task_id,)).fetchone()
    return row_to_dict(row)


@router.post("/{task_id}/move", response_model=TaskOut)
def move_task(task_id: str, payload: TaskMove) -> dict:
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Task not found")
        conn.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (payload.status, utc_now(), task_id),
        )
        row = conn.execute(f"{TASK_SELECT} WHERE id = ?", (task_id,)).fetchone()
    return row_to_dict(row)


@router.delete("/{task_id}", status_code=200)
def delete_task(task_id: str) -> None:
    with get_connection() as conn:
        result = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Task not found")
