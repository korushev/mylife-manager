from backend.app.routers.ai import router as ai_router
from backend.app.routers.calendar import router as calendar_router
from backend.app.routers.crm import router as crm_router
from backend.app.routers.health import router as health_router
from backend.app.routers.integrations import router as integrations_router
from backend.app.routers.lists import router as lists_router
from backend.app.routers.sprints import router as sprints_router
from backend.app.routers.tasks import router as tasks_router
from backend.app.routers.voice import router as voice_router

__all__ = [
    "ai_router",
    "calendar_router",
    "crm_router",
    "health_router",
    "integrations_router",
    "lists_router",
    "sprints_router",
    "tasks_router",
    "voice_router",
]
