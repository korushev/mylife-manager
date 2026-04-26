# MyLife Manager

MVP backend для персонального планирования задач и базового CRM.

## Features
- Task lists
- Tasks with statuses, priorities, deadlines, durations
- Sprints with 4 directions
- Time blocking and calendar feed
- CRM contacts and deals
- AI/Voice stubs
- Google Calendar integration stub

## Quick Start
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r backend/requirements.txt
uvicorn backend.app.main:app --reload
```

Open docs at `http://127.0.0.1:8000/docs`.

## Tests and Quality
```bash
source .venv/bin/activate
pytest backend/tests
flake8 backend
black --check backend
```

## Main API Groups
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
