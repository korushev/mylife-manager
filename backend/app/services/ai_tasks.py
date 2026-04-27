from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any

import httpx

from backend.app.services.voice_tasks import parse_voice_task

ALLOWED_STATUSES = {"inbox", "todo", "in_progress", "done"}
ALLOWED_PRIORITIES = {"low", "medium", "high"}


def _provider_config() -> dict[str, str | None]:
    provider = os.getenv("MYLIFE_AI_PROVIDER", "deepseek").strip().lower()

    if provider == "openai":
        return {
            "provider": "openai",
            "api_key": os.getenv("OPENAI_API_KEY"),
            "url": os.getenv(
                "OPENAI_CHAT_COMPLETIONS_URL",
                "https://api.openai.com/v1/chat/completions",
            ),
            "model": os.getenv("OPENAI_MODEL", "gpt-5.5"),
        }

    return {
        "provider": "deepseek",
        "api_key": os.getenv("DEEPSEEK_API_KEY"),
        "url": os.getenv(
            "DEEPSEEK_CHAT_COMPLETIONS_URL",
            "https://api.deepseek.com/v1/chat/completions",
        ),
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    }


def _extract_json_from_text(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(stripped[start : end + 1])
        raise


def _to_deadline(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _normalize_task(item: dict[str, Any]) -> dict[str, Any]:
    title = str(item.get("title") or "Новая задача").strip()
    if not title:
        title = "Новая задача"

    note = item.get("note")
    status = item.get("status")
    priority = item.get("priority")
    duration_min = item.get("duration_min")

    parsed_duration: int | None = None
    if isinstance(duration_min, (int, float)):
        as_int = int(duration_min)
        if 1 <= as_int <= 1440:
            parsed_duration = as_int

    normalized = {
        "title": title[:200],
        "note": str(note).strip() if isinstance(note, str) and note.strip() else None,
        "status": status if status in ALLOWED_STATUSES else None,
        "priority": priority if priority in ALLOWED_PRIORITIES else None,
        "duration_min": parsed_duration,
        "deadline": _to_deadline(item.get("deadline")),
    }

    missing_fields: list[str] = []
    if normalized["duration_min"] is None:
        missing_fields.append("duration_min")
    if normalized["priority"] is None:
        missing_fields.append("priority")
    if normalized["status"] is None:
        missing_fields.append("status")

    normalized["missing_fields"] = missing_fields
    normalized["requires_clarification"] = len(missing_fields) > 0
    normalized["next_question"] = (
        "Уточни недостающие поля для этой задачи." if missing_fields else None
    )
    return normalized


def _split_by_time_mentions(text: str) -> list[str]:
    pattern = re.compile(
        r"\bв\s*\d{1,2}(?::\d{2})?\s*(?:утра|дня|вечера|ночи)?\b",
        re.IGNORECASE,
    )
    matches = list(pattern.finditer(text))
    if len(matches) < 2:
        return [text]

    parts: list[str] = []
    start = 0
    for match in matches[1:]:
        chunk = text[start : match.start()].strip(" ;,.\n")
        if chunk:
            parts.append(chunk)
        start = match.start()

    last = text[start:].strip(" ;,.\n")
    if last:
        parts.append(last)

    return parts if len(parts) > 1 else [text]


def _split_fallback(message: str) -> list[str]:
    text = message.strip()
    if not text:
        return []

    numbered = re.split(r"(?:^|\n)\s*\d+[\).]\s+", text)
    numbered = [x.strip(" ;,.\n") for x in numbered if x.strip(" ;,.\n")]
    if len(numbered) > 1:
        return numbered

    chunks = re.split(
        r"\s*(?:;|\n|\bпотом\b|\bи еще\b|\bзатем\b|\bthen\b|\balso\b)\s*",
        text,
    )
    cleaned = [x.strip(" ;,.\n") for x in chunks if x.strip(" ;,.\n")]
    if len(cleaned) > 1:
        return cleaned

    temporal_text = re.sub(
        r"\bпосле\s+этого\b|\bа\s+потом\b|\bи\s+потом\b|\bдалее\b|\bзатем\b|\bи\s+вечером\b",
        ";",
        text,
        flags=re.IGNORECASE,
    )
    temporal_chunks = [
        x.strip(" ;,.\n") for x in temporal_text.split(";") if x.strip(" ;,.\n")
    ]
    if len(temporal_chunks) > 1:
        return temporal_chunks

    time_chunks = _split_by_time_mentions(text)
    if len(time_chunks) > 1:
        return time_chunks

    return [text]


def _fallback_tasks(message: str) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for chunk in _split_fallback(message):
        parsed = parse_voice_task(chunk)
        tasks.append(
            {
                "title": parsed["title"],
                "note": parsed["note"],
                "status": parsed["status"],
                "priority": parsed["priority"],
                "duration_min": parsed["duration_min"],
                "deadline": parsed["deadline"],
                "missing_fields": parsed["missing_fields"],
                "requires_clarification": parsed["requires_clarification"],
                "next_question": parsed["next_question"],
            }
        )
    return tasks


def _looks_like_multi_task_message(message: str) -> bool:
    lower = message.lower()
    connectors = [
        "после этого",
        "а потом",
        "и потом",
        "затем",
        "и вечером",
        ";",
        "\n",
    ]
    if any(token in lower for token in connectors):
        return True

    time_mentions = re.findall(
        r"\bв\s*\d{1,2}(?::\d{2})?\s*(?:утра|дня|вечера|ночи)?\b",
        lower,
    )
    return len(time_mentions) >= 2


def extract_tasks_from_message(message: str) -> dict[str, Any]:
    cfg = _provider_config()
    api_key = cfg["api_key"]

    if not api_key:
        return {
            "provider": "fallback",
            "model": None,
            "tasks": _fallback_tasks(message),
            "error": None,
        }

    system_prompt = (
        "You extract tasks from one user message. "
        "If message contains multiple tasks, return all of them separately. "
        "Return strict JSON only: "
        '{"tasks":[{"title":string,"note":string|null,"status":"inbox"|"todo"|"in_progress"|"done"|null,'
        '"priority":"low"|"medium"|"high"|null,"duration_min":number|null,"deadline":ISO8601|null}]}. '
        "If user packs several actions in one sentence, split them into separate tasks."
    )

    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                str(cfg["url"]),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = _extract_json_from_text(content)
        raw_tasks = parsed.get("tasks") if isinstance(parsed, dict) else None
        if not isinstance(raw_tasks, list) or not raw_tasks:
            raise ValueError("No tasks returned by provider")

        tasks = [_normalize_task(item) for item in raw_tasks if isinstance(item, dict)]
        if not tasks:
            raise ValueError("No valid tasks returned by provider")

        # Guardrail: if provider collapsed a multi-intent message into one task,
        # force-split using local heuristic and use the richer multi-task result.
        if len(tasks) == 1 and _looks_like_multi_task_message(message):
            split_tasks = _fallback_tasks(message)
            if len(split_tasks) > 1:
                return {
                    "provider": f"{cfg['provider']}+heuristic_split",
                    "model": cfg["model"],
                    "tasks": split_tasks,
                    "error": None,
                }

        return {
            "provider": cfg["provider"],
            "model": cfg["model"],
            "tasks": tasks,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "provider": "fallback",
            "model": None,
            "tasks": _fallback_tasks(message),
            "error": str(exc),
        }
