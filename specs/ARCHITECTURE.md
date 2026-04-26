# Architecture (MVP)

## Style
Modular monolith на FastAPI + SQLite.

## Modules
- tasks
- lists
- sprints
- calendar
- crm
- integrations
- ai (stub)
- voice (stub)

## Data Entities
- TaskList
- Sprint
- SprintDirection (4 направления на спринт)
- Task
- TimeBlock
- CRMContact
- CRMDeal
- IntegrationConfig

## Extension Points
- Calendar provider abstraction через `integrations` модуль
- AI и Voice выделены в отдельные API-модули-заглушки
- CRM связана с задачами через `linked_task_id`, что позволяет строить workflow
