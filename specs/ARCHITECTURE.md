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

## Sprint-First Workflow (Product Decision)
- Пользователь сначала определяет активный спринт (обычно 3-4 недели) и его фокус.
- Только после этого задачи создаются/раскладываются в контексте этого спринта.
- Внутри спринта используются 4 стабильных направления:
  - work_finance
  - family_relationships
  - personal_growth
  - health
- AI в чате должен учитывать активный спринт как главный контекст фокуса, а не просто раскидывать задачи по случайным тегам.
- Для задач вне фокуса спринта AI должен предлагать:
  - либо отложить задачу (backlog),
  - либо явно спросить подтверждение на добавление в текущий спринт.
