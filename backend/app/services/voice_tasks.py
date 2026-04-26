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


def infer_status(transcript: str) -> TaskStatus:
    lower = transcript.lower()
    for keyword, status in STATUS_KEYWORDS:
        if keyword in lower:
            return status
    return "inbox"


def infer_priority(transcript: str) -> TaskPriority:
    lower = transcript.lower()
    for keyword, priority in PRIORITY_KEYWORDS:
        if keyword in lower:
            return priority
    return "medium"


def infer_duration(transcript: str) -> int:
    lower = transcript.lower()

    minutes_match = DURATION_PATTERNS[0].search(lower) or DURATION_PATTERNS[1].search(
        lower
    )
    if minutes_match:
        value = int(minutes_match.group(1))
        return max(1, min(value, 1440))

    hours_match = DURATION_PATTERNS[2].search(lower) or DURATION_PATTERNS[3].search(
        lower
    )
    if hours_match:
        value = int(hours_match.group(1)) * 60
        return max(1, min(value, 1440))

    return 30


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
    cleaned = transcript.strip()
    if not cleaned:
        return "Untitled task", None

    tokens = re.split(r"[,.!?]", cleaned, maxsplit=1)
    title = tokens[0].strip()
    note = tokens[1].strip() if len(tokens) > 1 and tokens[1].strip() else None

    if len(title) > 200:
        title = title[:200].rstrip()

    return title, note


def parse_voice_task(transcript: str) -> dict:
    title, note = infer_title_and_note(transcript)
    return {
        "title": title,
        "note": note,
        "status": infer_status(transcript),
        "priority": infer_priority(transcript),
        "duration_min": infer_duration(transcript),
        "deadline": infer_deadline(transcript),
    }
