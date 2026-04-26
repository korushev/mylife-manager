from fastapi import FastAPI

from backend.app.database import init_db
from backend.app.routers import (
    ai_router,
    calendar_router,
    crm_router,
    health_router,
    integrations_router,
    lists_router,
    sprints_router,
    tasks_router,
    voice_router,
)

app = FastAPI(title="MyLife Manager API", version="0.1.0")


@app.on_event("startup")
def startup() -> None:
    init_db()


app.include_router(health_router)
app.include_router(lists_router)
app.include_router(tasks_router)
app.include_router(sprints_router)
app.include_router(calendar_router)
app.include_router(crm_router)
app.include_router(integrations_router)
app.include_router(ai_router)
app.include_router(voice_router)
