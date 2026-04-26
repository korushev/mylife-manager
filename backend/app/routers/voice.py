from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.database import get_connection, row_to_dict
from backend.app.routers.utils import new_id, utc_now
from backend.app.schemas import (
    StubCapabilityOut,
    TaskOut,
    VoiceTaskCreateRequest,
    VoiceTaskParseOut,
    VoiceTaskParseRequest,
)
from backend.app.services import parse_voice_task

router = APIRouter(prefix="/api/voice", tags=["voice"])

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


@router.get("/capabilities", response_model=StubCapabilityOut)
def voice_capabilities() -> StubCapabilityOut:
    return StubCapabilityOut(
        module="voice",
        status="available",
        message="Dictate a task, parse transcript, and create task from voice input.",
    )


@router.post("/parse-task", response_model=VoiceTaskParseOut)
def parse_task(payload: VoiceTaskParseRequest) -> VoiceTaskParseOut:
    parsed = parse_voice_task(payload.transcript)
    return VoiceTaskParseOut(
        transcript=payload.transcript,
        title=parsed["title"],
        note=parsed["note"],
        status=parsed["status"],
        priority=parsed["priority"],
        duration_min=parsed["duration_min"],
        deadline=parsed["deadline"],
        list_id=payload.list_id,
    )


@router.post("/create-task", response_model=TaskOut, status_code=201)
def create_task_from_voice(payload: VoiceTaskCreateRequest) -> dict:
    parsed = parse_voice_task(payload.transcript)
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
                parsed["title"],
                parsed["note"],
                parsed["status"],
                parsed["priority"],
                parsed["duration_min"],
                parsed["deadline"].isoformat() if parsed["deadline"] else None,
                payload.list_id,
                payload.sprint_id,
                payload.sprint_direction_id,
                now,
                now,
            ),
        )
        row = conn.execute(f"{TASK_SELECT} WHERE id = ?", (task_id,)).fetchone()

    return row_to_dict(row)
