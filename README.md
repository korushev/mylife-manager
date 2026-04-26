# MyLife Manager

MVP веб-сервис для персонального планирования задач с voice-first взаимодействием.

## Current focus
- Voice Inbox: диктовка задач, анализ и чат-уточнения
- Dashboard
- Tasks List (CRUD)
- Kanban board (drag-and-drop by status)
- Sprints with 4 directions
- Calendar / time-block feed

## Voice flow (main UX)
1. Нажать `Start Dictation` и надиктовать задачу.
2. Нажать `Analyze`.
3. Если не хватает полей (длительность/приоритет/статус), система задаст вопрос в чате справа.
4. Ответить в chat input, пока задача не станет полной.
5. Нажать `Create Task`.

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
