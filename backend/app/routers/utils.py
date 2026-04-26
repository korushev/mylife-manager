from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid4())
