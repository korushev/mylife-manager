from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from backend.app.schemas import TaskPriority, TaskStatus

STATUS_KEYWORDS: list[tuple[str, TaskStatus]] = [
    ("in progress", "in_progress"),
    ("в работе", "in_progress"),
    ("сделано", "done"),
    ("готово", "done"),
    ("todo", "todo"),
    ("к выполнению", "todo"),
    ("inbox", "inbox"),
    ("входящие", "inbox"),
]

PRIORITY_KEYWORDS: list[tuple[str, TaskPriority]] = [
    ("high", "high"),
    ("высок", "high"),
    ("urgent", "high"),
    ("сроч", "high"),
    ("medium", "medium"),
    ("средн", "medium"),
    ("low", "low"),
    ("низк", "low"),
]

DURATION_PATTERNS = [
    re.compile(r"(\d{1,3})\s*мин"),
    re.compile(r"(\d{1,3})\s*m(?:in)?\b"),
    re.compile(r"(\d{1,2})\s*час"),
    re.compile(r"(\d{1,2})\s*h(?:our)?\b"),
]

FILLER_PATTERNS = [
    re.compile(r"\bя\s+хочу\b", re.IGNORECASE),
    re.compile(r"\bпожалуйста\b", re.IGNORECASE),
    re.compile(r"\bты\s+поставь\b", re.IGNORECASE),
    re.compile(r"\bпоставь\s+задач[ау]\b", re.IGNORECASE),
]

QUESTION_BY_FIELD = {
    "duration_min": "Сколько минут закладываем на задачу?",
    "priority": "Какой приоритет: low, medium или high?",
    "status": "В какой статус поставить: inbox, todo, in_progress или done?",
}


def normalize_transcript(transcript: str) -> str:
    text = transcript.strip()
    text = re.sub(r"\s+", " ", text)

    words = text.split(" ")
    compact: list[str] = []
    for word in words:
        if not compact or compact[-1].lower() != word.lower():
            compact.append(word)
    text = " ".join(compact)

    for pattern in FILLER_PATTERNS:
        text = pattern.sub("", text)

    text = re.sub(r"\s+", " ", text).strip(" .,!?-")
    return text


def infer_status(transcript: str) -> tuple[TaskStatus | None, bool]:
    lower = transcript.lower()
    for keyword, status in STATUS_KEYWORDS:
        if keyword in lower:
            return status, True
    return None, False


def infer_priority(transcript: str) -> tuple[TaskPriority | None, bool]:
    lower = transcript.lower()
    for keyword, priority in PRIORITY_KEYWORDS:
        if keyword in lower:
            return priority, True
    return None, False


def infer_duration(transcript: str) -> tuple[int | None, bool]:
    lower = transcript.lower()

    minutes_match = DURATION_PATTERNS[0].search(lower) or DURATION_PATTERNS[1].search(
        lower
    )
    if minutes_match:
        value = int(minutes_match.group(1))
        return max(1, min(value, 1440)), True

    hours_match = DURATION_PATTERNS[2].search(lower) or DURATION_PATTERNS[3].search(
        lower
    )
    if hours_match:
        value = int(hours_match.group(1)) * 60
        return max(1, min(value, 1440)), True

    return None, False


def infer_deadline(transcript: str) -> datetime | None:
    lower = transcript.lower()
    now = datetime.now(tz=timezone.utc)

    if "tomorrow" in lower or "завтра" in lower:
        return (now + timedelta(days=1)).replace(
            hour=18, minute=0, second=0, microsecond=0
        )

    if "today" in lower or "сегодня" in lower:
        return now.replace(hour=20, minute=0, second=0, microsecond=0)

    day_match = re.search(r"(?:до\s*)?(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?", lower)
    if day_match:
        day = int(day_match.group(1))
        month = int(day_match.group(2))
        year = int(day_match.group(3)) if day_match.group(3) else now.year
        try:
            return datetime(year, month, day, 18, 0, tzinfo=timezone.utc)
        except ValueError:
            return None

    return None


def infer_title_and_note(transcript: str) -> tuple[str, str | None]:
    cleaned = normalize_transcript(transcript)
    if not cleaned:
        return "Новая задача", None

    tokens = re.split(r"[.!?]", cleaned, maxsplit=1)
    title = tokens[0].strip(" ,")
    note = tokens[1].strip() if len(tokens) > 1 and tokens[1].strip() else None

    if len(title) > 200:
        title = title[:200].rstrip()

    if not title:
        title = "Новая задача"

    return title, note


def parse_voice_task(transcript: str) -> dict:
    title, note = infer_title_and_note(transcript)

    status, has_status = infer_status(transcript)
    priority, has_priority = infer_priority(transcript)
    duration_min, has_duration = infer_duration(transcript)

    missing_fields: list[str] = []
    if not has_duration:
        missing_fields.append("duration_min")
    if not has_priority:
        missing_fields.append("priority")
    if not has_status:
        missing_fields.append("status")

    next_question = QUESTION_BY_FIELD[missing_fields[0]] if missing_fields else None

    return {
        "title": title,
        "note": note,
        "status": status,
        "priority": priority,
        "duration_min": duration_min,
        "deadline": infer_deadline(transcript),
        "missing_fields": missing_fields,
        "requires_clarification": len(missing_fields) > 0,
        "next_question": next_question,
    }
