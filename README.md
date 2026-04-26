# MyLife Manager

MVP веб-сервис для персонального планирования задач с voice-first взаимодействием.

## Current focus
- Voice Inbox: диктовка задач, анализ и чат-уточнения
- Dashboard
- Tasks List (CRUD)
- Kanban board (drag-and-drop by status)
- Sprints with 4 directions
- Calendar / time-block feed

## AI Provider (DeepSeek first)
По умолчанию сервис использует `DeepSeek` для разбора сообщения на задачи.
Если ключ не задан или API недоступен, включается локальный fallback.

### Environment variables
```bash
# Provider: deepseek | openai
MYLIFE_AI_PROVIDER=deepseek

# DeepSeek (default path)
DEEPSEEK_API_KEY=...
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_CHAT_COMPLETIONS_URL=https://api.deepseek.com/v1/chat/completions

# Optional OpenAI path
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.5
OPENAI_CHAT_COMPLETIONS_URL=https://api.openai.com/v1/chat/completions
```

## Voice flow (main UX)
1. Нажать `Start Dictation` и надиктовать задачу.
2. Нажать `Analyze`.
3. Если не хватает полей (длительность/приоритет/статус), система задаст вопрос в чате справа.
4. Можно ответить в chat input для уточнения, но это не обязательно.
5. `Create Task` всегда создаёт задачу, даже с неполными данными.

## Voice endpoints
- `POST /api/voice/parse-task` — анализ одной задачи
- `POST /api/voice/create-task` — создание одной задачи
- `POST /api/voice/analyze-message` — анализ сообщения на несколько задач
- `POST /api/voice/create-tasks-from-message` — массовое создание задач из одного сообщения
- `GET /api/voice/capabilities`

## Deferred for next stage
- CRM UI workflow
- Real speech-to-text model on server side
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

## Quality checks
```bash
source .venv/bin/activate
pytest backend/tests
flake8 backend
black --check backend
```
