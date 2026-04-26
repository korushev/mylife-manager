# AGENTS.md

## Project Overview
Однопользовательский веб-сервис для управления задачами и календарным планированием.
Первая версия: REST API для задач, проектов, дедлайнов и приоритетов.

## Repo Layout
- backend/app/ — исходный код FastAPI
- backend/tests/ — тесты
- specs/ — спецификации и ТЗ

## Commands (Use these)
- Install: python3 -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements.txt
- Run app: uvicorn backend.app.main:app --reload
- Run tests: pytest backend/tests
- Format: black backend/
- Lint: flake8 backend/

## Guardrails
- Не добавлять внешние зависимости без запроса.
- Перед завершением задачи запускать тесты и линтер.
- Если требуется более 3 новых файлов сверх плана, остановиться и уточнить у пользователя.
