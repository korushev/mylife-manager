from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException

from backend.app.database import get_connection, row_to_dict
from backend.app.routers.utils import new_id, utc_now
from backend.app.schemas import (
    ChatHistoryConfigOut,
    ChatHistoryConfigUpdate,
    ChatHistoryMessageOut,
    MemoryFactOut,
    StubCapabilityOut,
    TaskOut,
    VoiceApplyActionOut,
    VoiceApplyActionRequest,
    VoiceChatTurnOut,
    VoiceChatTurnRequest,
    VoiceConfirmTasksOut,
    VoiceConfirmTasksRequest,
    VoiceCreateManyOut,
    VoiceCreateManyRequest,
    VoiceMessageAnalyzeOut,
    VoiceMessageAnalyzeRequest,
    VoiceTaskCreateRequest,
    VoiceTaskParseOut,
    VoiceTaskParseRequest,
)
from backend.app.services.ai_tasks import (
    chat_turn_plan,
    extract_tasks_from_message,
    provider_runtime_status,
)
from backend.app.services.voice_tasks import parse_voice_task

router = APIRouter(prefix="/api/voice", tags=["voice"])

TASK_SELECT = (
    "SELECT id, title, note, status, priority, duration_min, deadline, list_id, "
    "sprint_id, sprint_direction_id, created_at, updated_at FROM tasks"
)
_ACTIVE_SPRINT_KEY = "active_sprint_id"
_CHAT_HISTORY_ENABLED_KEY = "chat_history_enabled"
_CHAT_HISTORY_RETENTION_KEY = "chat_history_retention_days"
_CHAT_HISTORY_CONTEXT_LIMIT_KEY = "chat_history_context_limit"


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


def _active_sprint_context(conn) -> dict:
    row = conn.execute(
        (
            "SELECT s.id, s.name FROM app_settings cfg "
            "JOIN sprints s ON s.id = cfg.value "
            "WHERE cfg.key = ?"
        ),
        (_ACTIVE_SPRINT_KEY,),
    ).fetchone()
    context = row_to_dict(row)
    if context is not None:
        return context

    stale = conn.execute(
        "SELECT value FROM app_settings WHERE key = ?", (_ACTIVE_SPRINT_KEY,)
    ).fetchone()
    if stale is not None:
        conn.execute("DELETE FROM app_settings WHERE key = ?", (_ACTIVE_SPRINT_KEY,))
    return {"id": None, "name": None}


def _resolve_sprint_assignment(
    conn, requested_sprint_id: str | None
) -> tuple[str | None, dict]:
    active = _active_sprint_context(conn)
    return (requested_sprint_id or active["id"], active)


def _get_chat_history_config(conn) -> dict:
    enabled_row = conn.execute(
        "SELECT value FROM app_settings WHERE key = ?", (_CHAT_HISTORY_ENABLED_KEY,)
    ).fetchone()
    retention_row = conn.execute(
        "SELECT value FROM app_settings WHERE key = ?", (_CHAT_HISTORY_RETENTION_KEY,)
    ).fetchone()
    context_limit_row = conn.execute(
        "SELECT value FROM app_settings WHERE key = ?",
        (_CHAT_HISTORY_CONTEXT_LIMIT_KEY,),
    ).fetchone()

    enabled = True
    if enabled_row is not None:
        enabled = str(enabled_row["value"]).strip() not in {"0", "false", "False"}

    retention_days = 30
    if retention_row is not None:
        try:
            retention_days = max(1, min(int(retention_row["value"]), 365))
        except (TypeError, ValueError):
            retention_days = 30

    context_limit = 10
    if context_limit_row is not None:
        try:
            context_limit = max(4, min(int(context_limit_row["value"]), 40))
        except (TypeError, ValueError):
            context_limit = 10

    return {
        "enabled": enabled,
        "retention_days": retention_days,
        "context_limit": context_limit,
    }


def _set_chat_history_config(
    conn, enabled: bool, retention_days: int, context_limit: int
) -> dict:
    now = utc_now()
    conn.execute(
        (
            "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at"
        ),
        (_CHAT_HISTORY_ENABLED_KEY, "1" if enabled else "0", now),
    )
    conn.execute(
        (
            "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at"
        ),
        (_CHAT_HISTORY_RETENTION_KEY, str(retention_days), now),
    )
    conn.execute(
        (
            "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at"
        ),
        (_CHAT_HISTORY_CONTEXT_LIMIT_KEY, str(context_limit), now),
    )
    return {
        "enabled": enabled,
        "retention_days": retention_days,
        "context_limit": context_limit,
    }


def _purge_old_chat_messages(conn, retention_days: int) -> None:
    conn.execute(
        "DELETE FROM chat_messages WHERE datetime(created_at) < datetime('now', ?)",
        (f"-{retention_days} days",),
    )


def _log_chat_message(
    conn,
    *,
    role: str,
    content: str,
    intent: str | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> None:
    cfg = _get_chat_history_config(conn)
    if not cfg["enabled"]:
        return

    _purge_old_chat_messages(conn, cfg["retention_days"])
    conn.execute(
        (
            "INSERT INTO chat_messages (id, role, content, intent, provider, model, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)"
        ),
        (new_id(), role, content, intent, provider, model, utc_now()),
    )


def _fetch_short_history(conn, limit: int) -> list[dict]:
    rows = conn.execute(
        (
            "SELECT role, content, created_at FROM chat_messages "
            "ORDER BY created_at DESC LIMIT ?"
        ),
        (limit,),
    ).fetchall()
    items = [row_to_dict(row) for row in rows]
    items.reverse()
    return items


def _fetch_long_memory(conn, limit: int = 20) -> list[dict]:
    rows = conn.execute(
        (
            "SELECT id, fact, source, created_at, updated_at "
            "FROM memory_facts ORDER BY updated_at DESC LIMIT ?"
        ),
        (limit,),
    ).fetchall()
    return [row_to_dict(row) for row in rows]


def _memory_candidates_from_user_message(message: str) -> list[str]:
    text = message.strip()
    lower = text.lower()
    candidates: list[str] = []

    if "спринт" in lower and any(
        x in lower for x in ("работ", "сем", "рост", "здоров")
    ):
        candidates.append(
            "Пользователь планирует спринтами и использует 4 направления: "
            "работа/финансы, семья/отношения, личностный рост, здоровье."
        )
    if any(x in lower for x in ("голос", "диктов", "аудио")) and any(
        x in lower for x in ("основ", "глав", "важно")
    ):
        candidates.append(
            "Голосовой ввод — приоритетный способ взаимодействия для пользователя."
        )
    if (
        any(x in lower for x in ("мне важно", "мне нужно", "я хочу"))
        and len(text) <= 220
    ):
        candidates.append(text[:220])

    # Keep unique order
    unique: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _upsert_memory_fact(conn, fact: str, source: str = "auto") -> None:
    now = utc_now()
    existing = conn.execute(
        "SELECT id FROM memory_facts WHERE LOWER(fact) = LOWER(?)",
        (fact,),
    ).fetchone()
    if existing is not None:
        conn.execute(
            "UPDATE memory_facts SET updated_at = ? WHERE id = ?",
            (now, existing["id"]),
        )
        return
    conn.execute(
        (
            "INSERT INTO memory_facts (id, fact, source, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)"
        ),
        (new_id(), fact, source, now, now),
    )


def _find_tasks_by_operation(
    conn, operation: dict | None, list_id: str | None
) -> list[dict]:
    if operation is None:
        return []

    where: list[str] = []
    params: list[str] = []

    if list_id:
        where.append("list_id = ?")
        params.append(list_id)

    text = operation.get("text")
    if isinstance(text, str) and text.strip():
        tokens = re.findall(r"[a-zA-Zа-яА-Я0-9]+", text.lower())
        normalized = [token[:5] for token in tokens if len(token) >= 3][:6]
        if normalized:
            parts: list[str] = []
            for token in normalized:
                parts.append(
                    "("
                    "title LIKE ? OR COALESCE(note, '') LIKE ? "
                    "OR title LIKE ? OR COALESCE(note, '') LIKE ?"
                    ")"
                )
                lower_like = f"%{token}%"
                upper_like = f"%{token[:1].upper()}{token[1:]}%"
                params.append(lower_like)
                params.append(lower_like)
                params.append(upper_like)
                params.append(upper_like)
            where.append("(" + " OR ".join(parts) + ")")

    status = operation.get("status")
    if status in {"inbox", "todo", "in_progress", "done"}:
        where.append("status = ?")
        params.append(status)

    if operation.get("without_deadline"):
        where.append("deadline IS NULL")

    relative_day = operation.get("relative_day")
    if relative_day == "yesterday":
        where.append("date(updated_at) = date('now', '-1 day')")
    elif relative_day == "today":
        where.append("date(updated_at) = date('now')")

    sql = TASK_SELECT
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC"

    limit = operation.get("limit") or 10
    try:
        safe_limit = max(1, min(int(limit), 50))
    except (TypeError, ValueError):
        safe_limit = 10
    sql += f" LIMIT {safe_limit}"

    rows = conn.execute(sql, tuple(params)).fetchall()
    return [row_to_dict(row) for row in rows]


@router.get("/capabilities", response_model=StubCapabilityOut)
def voice_capabilities() -> StubCapabilityOut:
    runtime = provider_runtime_status()
    mode = "configured" if runtime["configured"] else "not_configured"
    return StubCapabilityOut(
        module="voice",
        status="available",
        message=(
            f"AI provider={runtime['provider']} ({mode}), model={runtime['model']}. "
            "Chat-first flow: chat-turn -> confirm-tasks."
        ),
    )


@router.post("/chat-turn", response_model=VoiceChatTurnOut)
def chat_turn(payload: VoiceChatTurnRequest) -> VoiceChatTurnOut:
    with get_connection() as conn:
        active = _active_sprint_context(conn)
        history_cfg = _get_chat_history_config(conn)
        short_history = _fetch_short_history(conn, history_cfg["context_limit"])
        long_memory = _fetch_long_memory(conn, limit=20)

    plan = chat_turn_plan(
        payload.message,
        active_sprint_name=active["name"],
        short_history=short_history,
        long_memory=long_memory,
    )
    with get_connection() as conn:
        _log_chat_message(
            conn,
            role="user",
            content=payload.message,
        )
        for fact in _memory_candidates_from_user_message(payload.message):
            _upsert_memory_fact(conn, fact, source="auto")
        _log_chat_message(
            conn,
            role="assistant",
            content=plan["assistant_reply"],
            intent=plan["intent"],
            provider=plan["provider"],
            model=plan["model"],
        )
    return VoiceChatTurnOut(
        provider=plan["provider"],
        model=plan["model"],
        intent=plan["intent"],
        assistant_reply=plan["assistant_reply"],
        active_sprint_id=active["id"],
        active_sprint_name=active["name"],
        tasks=plan["tasks"],
        actions=plan["actions"],
        operation=plan.get("operation"),
        error=plan["error"],
    )


@router.post("/apply-action", response_model=VoiceApplyActionOut)
def apply_action(payload: VoiceApplyActionRequest) -> VoiceApplyActionOut:
    action = payload.action
    operation = payload.operation.model_dump() if payload.operation else None

    with get_connection() as conn:
        matched = _find_tasks_by_operation(conn, operation, payload.list_id)
        if action == "run_query":
            return VoiceApplyActionOut(
                action=action,
                affected_count=len(matched),
                tasks=matched,
                assistant_reply=f"Нашел задач: {len(matched)}.",
                preview_only=True,
            )

        if action == "confirm_delete":
            if payload.task_ids:
                target_ids = [task_id for task_id in payload.task_ids if task_id]
            else:
                target_ids = [task["id"] for task in matched]

            deleted_count = 0
            for task_id in target_ids:
                if payload.list_id:
                    result = conn.execute(
                        "DELETE FROM tasks WHERE id = ? AND list_id = ?",
                        (task_id, payload.list_id),
                    )
                else:
                    result = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                deleted_count += result.rowcount

            return VoiceApplyActionOut(
                action=action,
                affected_count=deleted_count,
                tasks=[],
                assistant_reply=f"Удалил задач: {deleted_count}.",
                preview_only=False,
            )

        if action == "confirm_update_status":
            if operation is None or operation.get("new_status") not in {
                "inbox",
                "todo",
                "in_progress",
                "done",
            }:
                raise HTTPException(
                    status_code=400, detail="new_status is required for update_status"
                )
            new_status = operation["new_status"]
            for task in matched:
                conn.execute(
                    "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
                    (new_status, utc_now(), task["id"]),
                )
            updated = _find_tasks_by_operation(conn, operation, payload.list_id)
            return VoiceApplyActionOut(
                action=action,
                affected_count=len(matched),
                tasks=updated,
                assistant_reply=f"Обновил статус у задач: {len(matched)}.",
                preview_only=False,
            )

    raise HTTPException(status_code=400, detail="Unsupported action")


@router.get("/history-config", response_model=ChatHistoryConfigOut)
def get_history_config() -> dict:
    with get_connection() as conn:
        return _get_chat_history_config(conn)


@router.post("/history-config", response_model=ChatHistoryConfigOut)
def update_history_config(payload: ChatHistoryConfigUpdate) -> dict:
    with get_connection() as conn:
        return _set_chat_history_config(
            conn,
            payload.enabled,
            payload.retention_days,
            payload.context_limit,
        )


@router.get("/history", response_model=list[ChatHistoryMessageOut])
def get_history(limit: int = 50) -> list[dict]:
    safe_limit = max(1, min(limit, 200))
    with get_connection() as conn:
        cfg = _get_chat_history_config(conn)
        _purge_old_chat_messages(conn, cfg["retention_days"])
        rows = conn.execute(
            (
                "SELECT id, role, content, intent, provider, model, created_at "
                "FROM chat_messages ORDER BY created_at DESC LIMIT ?"
            ),
            (safe_limit,),
        ).fetchall()
    return [row_to_dict(row) for row in rows]


@router.post("/history/clear", status_code=200)
def clear_history() -> dict:
    with get_connection() as conn:
        conn.execute("DELETE FROM chat_messages")
    return {"status": "ok"}


@router.get("/memory", response_model=list[MemoryFactOut])
def get_memory(limit: int = 50) -> list[dict]:
    safe_limit = max(1, min(limit, 200))
    with get_connection() as conn:
        return _fetch_long_memory(conn, safe_limit)


@router.post("/memory/clear", status_code=200)
def clear_memory() -> dict:
    with get_connection() as conn:
        conn.execute("DELETE FROM memory_facts")
    return {"status": "ok"}


@router.post("/confirm-tasks", response_model=VoiceConfirmTasksOut, status_code=201)
def confirm_tasks(payload: VoiceConfirmTasksRequest) -> VoiceConfirmTasksOut:
    created: list[dict] = []

    with get_connection() as conn:
        resolved_sprint_id, _active = _resolve_sprint_assignment(
            conn, payload.sprint_id
        )
        _validate_refs(
            conn, payload.list_id, resolved_sprint_id, payload.sprint_direction_id
        )

        for candidate in payload.tasks:
            task_id = new_id()
            now = utc_now()

            resolved_title = candidate.title or "Новая задача"
            resolved_note = candidate.note
            resolved_status = candidate.status or "inbox"
            resolved_priority = candidate.priority or "medium"
            resolved_duration = candidate.duration_min or 30
            resolved_deadline = candidate.deadline

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
                    resolved_sprint_id,
                    payload.sprint_direction_id,
                    now,
                    now,
                ),
            )
            row = conn.execute(f"{TASK_SELECT} WHERE id = ?", (task_id,)).fetchone()
            created.append(row_to_dict(row))

    runtime = provider_runtime_status()
    return VoiceConfirmTasksOut(
        provider=runtime["provider"],
        model=runtime["model"],
        created_count=len(created),
        tasks=created,
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
        resolved_sprint_id, _active = _resolve_sprint_assignment(
            conn, payload.sprint_id
        )
        _validate_refs(
            conn, payload.list_id, resolved_sprint_id, payload.sprint_direction_id
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
                resolved_sprint_id,
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
        resolved_sprint_id, _active = _resolve_sprint_assignment(
            conn, payload.sprint_id
        )
        _validate_refs(
            conn, payload.list_id, resolved_sprint_id, payload.sprint_direction_id
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
                    resolved_sprint_id,
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
