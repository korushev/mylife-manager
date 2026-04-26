# MyLife Manager

MVP веб-сервис для персонального планирования задач с voice-first взаимодействием.

## Current focus
- Voice Inbox: диктовка задач и авторазбор в поля задачи
- Dashboard
- Tasks List (CRUD)
- Kanban board (drag-and-drop by status)
- Sprints with 4 directions
- Calendar / time-block feed

## Deferred for next stage
- CRM UI workflow
- Real AI speech-to-text model
- TTS/voice responses

## Quick Start
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r backend/requirements.txt
uvicorn backend.app.main:app --reload
```

Open app at `http://127.0.0.1:8000/`.
API docs at `http://127.0.0.1:8000/docs`.

## Voice endpoints
- `POST /api/voice/parse-task`
- `POST /api/voice/create-task`
- `GET /api/voice/capabilities`

## Quality checks
```bash
source .venv/bin/activate
pytest backend/tests
flake8 backend
black --check backend
```
