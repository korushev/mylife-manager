# MyLife Manager

MVP веб-сервис для персонального планирования задач и базового CRM.

## What is included
- Dashboard
- Tasks List (CRUD)
- Kanban board (drag-and-drop by status)
- Sprints with 4 directions
- Calendar / time-block feed
- CRM contacts and deals
- Google Calendar settings stub
- AI and Voice stubs

## Quick Start
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r backend/requirements.txt
uvicorn backend.app.main:app --reload
```

Open app at `http://127.0.0.1:8000/`.
API docs at `http://127.0.0.1:8000/docs`.

## Quality checks
```bash
source .venv/bin/activate
pytest backend/tests
flake8 backend
black --check backend
```

## API groups
- `/api/lists`
- `/api/tasks`
- `/api/sprints`
- `/api/time-blocks`
- `/api/calendar`
- `/api/crm/contacts`
- `/api/crm/deals`
- `/api/integrations/google-calendar`
- `/api/ai/capabilities`
- `/api/voice/capabilities`
