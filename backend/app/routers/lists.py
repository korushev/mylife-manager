from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.database import get_connection, row_to_dict
from backend.app.routers.utils import new_id, utc_now
from backend.app.schemas import TaskListCreate, TaskListOut, TaskListUpdate

router = APIRouter(prefix="/api/lists", tags=["lists"])


@router.get("", response_model=list[TaskListOut])
def list_lists() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, color, created_at FROM task_lists ORDER BY created_at DESC"
        ).fetchall()
    return [row_to_dict(row) for row in rows]


@router.post("", response_model=TaskListOut, status_code=201)
def create_list(payload: TaskListCreate) -> dict:
    list_id = new_id()
    now = utc_now()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO task_lists (id, name, color, created_at) VALUES (?, ?, ?, ?)",
            (list_id, payload.name, payload.color, now),
        )
        row = conn.execute(
            "SELECT id, name, color, created_at FROM task_lists WHERE id = ?",
            (list_id,),
        ).fetchone()
    return row_to_dict(row)


@router.patch("/{list_id}", response_model=TaskListOut)
def update_list(list_id: str, payload: TaskListUpdate) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM task_lists WHERE id = ?", (list_id,)
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="List not found")

        fields: list[str] = []
        values: list[str] = []
        for key, value in updates.items():
            fields.append(f"{key} = ?")
            values.append(value)
        values.append(list_id)

        conn.execute(
            f"UPDATE task_lists SET {', '.join(fields)} WHERE id = ?", tuple(values)
        )
        row = conn.execute(
            "SELECT id, name, color, created_at FROM task_lists WHERE id = ?",
            (list_id,),
        ).fetchone()
    return row_to_dict(row)


@router.delete("/{list_id}", status_code=200)
def delete_list(list_id: str) -> None:
    with get_connection() as conn:
        result = conn.execute("DELETE FROM task_lists WHERE id = ?", (list_id,))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="List not found")
