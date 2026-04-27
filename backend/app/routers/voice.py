from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.database import get_connection, row_to_dict
from backend.app.routers.utils import new_id, utc_now
from backend.app.schemas import (
    StubCapabilityOut,
    TaskOut,
    VoiceCreateManyOut,
    VoiceCreateManyRequest,
    VoiceMessageAnalyzeOut,
    VoiceMessageAnalyzeRequest,
    VoiceTaskCreateRequest,
    VoiceTaskParseOut,
    VoiceTaskParseRequest,
)
from backend.app.services.ai_tasks import (
    extract_tasks_from_message,
    provider_runtime_status,
)
from backend.app.services.voice_tasks import parse_voice_task

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


def _resolve_task_fields(candidate: dict, payload: VoiceTaskCreateRequest) -> tuple:
    resolved_title = payload.title or candidate.get("title") or "Новая задача"
    resolved_note = payload.note if payload.note is not None else candidate.get("note")
    resolved_status = payload.status or candidate.get("status") or "inbox"
    resolved_priority = payload.priority or candidate.get("priority") or "medium"
    resolved_duration = payload.duration_min or candidate.get("duration_min") or 30
    resolved_deadline = (
        payload.deadline if payload.deadline is not None else candidate.get("deadline")
    )
    return (
        resolved_title,
        resolved_note,
        resolved_status,
        resolved_priority,
        resolved_duration,
        resolved_deadline,
    )


@router.get("/capabilities", response_model=StubCapabilityOut)
def voice_capabilities() -> StubCapabilityOut:
    runtime = provider_runtime_status()
    mode = "configured" if runtime["configured"] else "not_configured"
    return StubCapabilityOut(
        module="voice",
        status="available",
        message=(
            f"AI provider={runtime['provider']} ({mode}), model={runtime['model']}. "
            "Use analyze-message for LLM parsing; fallback only if provider is unavailable."
        ),
    )


@router.post("/analyze-message", response_model=VoiceMessageAnalyzeOut)
def analyze_message(payload: VoiceMessageAnalyzeRequest) -> VoiceMessageAnalyzeOut:
    result = extract_tasks_from_message(payload.message)
    return VoiceMessageAnalyzeOut(
        provider=result["provider"],
        model=result["model"],
        tasks=result["tasks"],
        error=result["error"],
    )


@router.post("/parse-task", response_model=VoiceTaskParseOut)
def parse_task(payload: VoiceTaskParseRequest) -> VoiceTaskParseOut:
    result = extract_tasks_from_message(payload.transcript)
    first = (
        result["tasks"][0] if result["tasks"] else parse_voice_task(payload.transcript)
    )

    return VoiceTaskParseOut(
        transcript=payload.transcript,
        title=first["title"],
        note=first["note"],
        status=first["status"],
        priority=first["priority"],
        duration_min=first["duration_min"],
        deadline=first["deadline"],
        list_id=payload.list_id,
        missing_fields=first["missing_fields"],
        requires_clarification=first["requires_clarification"],
        next_question=first["next_question"],
    )


@router.post("/create-task", response_model=TaskOut, status_code=201)
def create_task_from_voice(payload: VoiceTaskCreateRequest) -> dict:
    result = extract_tasks_from_message(payload.transcript)
    first = (
        result["tasks"][0] if result["tasks"] else parse_voice_task(payload.transcript)
    )

    (
        resolved_title,
        resolved_note,
        resolved_status,
        resolved_priority,
        resolved_duration,
        resolved_deadline,
    ) = _resolve_task_fields(first, payload)

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
                resolved_title,
                resolved_note,
                resolved_status,
                resolved_priority,
                resolved_duration,
                resolved_deadline.isoformat() if resolved_deadline else None,
                payload.list_id,
                payload.sprint_id,
                payload.sprint_direction_id,
                now,
                now,
            ),
        )
        row = conn.execute(f"{TASK_SELECT} WHERE id = ?", (task_id,)).fetchone()

    return row_to_dict(row)


@router.post(
    "/create-tasks-from-message", response_model=VoiceCreateManyOut, status_code=201
)
def create_tasks_from_message(payload: VoiceCreateManyRequest) -> VoiceCreateManyOut:
    result = extract_tasks_from_message(payload.message)
    created: list[dict] = []

    with get_connection() as conn:
        _validate_refs(
            conn, payload.list_id, payload.sprint_id, payload.sprint_direction_id
        )

        for candidate in result["tasks"]:
            task_id = new_id()
            now = utc_now()

            resolved_title = candidate.get("title") or "Новая задача"
            resolved_note = candidate.get("note")
            resolved_status = candidate.get("status") or "inbox"
            resolved_priority = candidate.get("priority") or "medium"
            resolved_duration = candidate.get("duration_min") or 30
            resolved_deadline = candidate.get("deadline")

            conn.execute(
                (
                    "INSERT INTO tasks (id, title, note, status, priority, duration_min, deadline, list_id, "
                    "sprint_id, sprint_direction_id, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                ),
                (
                    task_id,
                    resolved_title,
                    resolved_note,
                    resolved_status,
                    resolved_priority,
                    resolved_duration,
                    resolved_deadline.isoformat() if resolved_deadline else None,
                    payload.list_id,
                    payload.sprint_id,
                    payload.sprint_direction_id,
                    now,
                    now,
                ),
            )
            row = conn.execute(f"{TASK_SELECT} WHERE id = ?", (task_id,)).fetchone()
            created.append(row_to_dict(row))

    return VoiceCreateManyOut(
        provider=result["provider"],
        model=result["model"],
        created_count=len(created),
        tasks=created,
        error=result["error"],
    )
