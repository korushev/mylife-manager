from __future__ import annotations

from fastapi import APIRouter

from backend.app.database import get_connection, row_to_dict
from backend.app.routers.utils import utc_now
from backend.app.schemas import IntegrationConfigOut, IntegrationConfigUpdate

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


@router.get("/google-calendar", response_model=IntegrationConfigOut)
def get_google_calendar_config() -> dict:
    with get_connection() as conn:
        row = conn.execute(
            (
                "SELECT provider, enabled, settings_json, updated_at "
                "FROM integration_configs WHERE provider = 'google_calendar'"
            )
        ).fetchone()
        if row is None:
            now = utc_now()
            conn.execute(
                (
                    "INSERT INTO integration_configs (provider, enabled, settings_json, updated_at) "
                    "VALUES ('google_calendar', 0, '{}', ?)"
                ),
                (now,),
            )
            row = conn.execute(
                (
                    "SELECT provider, enabled, settings_json, updated_at "
                    "FROM integration_configs WHERE provider = 'google_calendar'"
                )
            ).fetchone()

    data = row_to_dict(row)
    data["enabled"] = bool(data["enabled"])
    return data


@router.post("/google-calendar", response_model=IntegrationConfigOut)
def update_google_calendar_config(payload: IntegrationConfigUpdate) -> dict:
    now = utc_now()
    with get_connection() as conn:
        conn.execute(
            (
                "INSERT INTO integration_configs (provider, enabled, settings_json, updated_at) "
                "VALUES ('google_calendar', ?, ?, ?) "
                "ON CONFLICT(provider) DO UPDATE SET enabled=excluded.enabled, "
                "settings_json=excluded.settings_json, updated_at=excluded.updated_at"
            ),
            (1 if payload.enabled else 0, payload.settings_json, now),
        )
        row = conn.execute(
            (
                "SELECT provider, enabled, settings_json, updated_at "
                "FROM integration_configs WHERE provider = 'google_calendar'"
            )
        ).fetchone()

    data = row_to_dict(row)
    data["enabled"] = bool(data["enabled"])
    return data
