from fastapi.testclient import TestClient

from backend.app.main import app


def test_voice_parse_and_create_task() -> None:
    with TestClient(app) as client:
        list_response = client.post(
            "/api/lists",
            json={"name": "Voice", "color": "#1d4ed8"},
        )
        assert list_response.status_code == 201
        list_id = list_response.json()["id"]

        parse_response = client.post(
            "/api/voice/parse-task",
            json={
                "transcript": "Завтра в работе подготовить отчет, высокий приоритет, 45 минут",
                "list_id": list_id,
            },
        )
        assert parse_response.status_code == 200

        create_response = client.post(
            "/api/voice/create-task",
            json={
                "transcript": "Сделать рефакторинг модуля, medium, 30 min, todo",
                "list_id": list_id,
            },
        )
        assert create_response.status_code == 201


def test_chat_turn_and_confirm_tasks() -> None:
    with TestClient(app) as client:
        list_response = client.post(
            "/api/lists",
            json={"name": "Chat", "color": "#0369a1"},
        )
        list_id = list_response.json()["id"]

        turn = client.post(
            "/api/voice/chat-turn",
            json={
                "message": "Сходить к врачу; выпить кофе; вечером поиграть с сыном",
                "list_id": list_id,
            },
        )
        assert turn.status_code == 200
        turn_data = turn.json()
        assert turn_data["assistant_reply"]
        assert isinstance(turn_data["tasks"], list)
        assert len(turn_data["tasks"]) >= 1

        confirm = client.post(
            "/api/voice/confirm-tasks",
            json={"list_id": list_id, "tasks": turn_data["tasks"]},
        )
        assert confirm.status_code == 201
        confirm_data = confirm.json()
        assert confirm_data["created_count"] >= 1


def test_analyze_and_create_multiple_tasks_from_one_message() -> None:
    with TestClient(app) as client:
        list_response = client.post(
            "/api/lists",
            json={"name": "Voice3", "color": "#0ea5e9"},
        )
        list_id = list_response.json()["id"]

        message = "1) Позвонить клиенту 20 минут high todo; 2) Подготовить КП завтра"

        analyze = client.post("/api/voice/analyze-message", json={"message": message})
        assert analyze.status_code == 200

        create_many = client.post(
            "/api/voice/create-tasks-from-message",
            json={"message": message, "list_id": list_id},
        )
        assert create_many.status_code == 201
        data = create_many.json()
        assert data["created_count"] >= 1


def test_confirm_tasks_uses_active_sprint_by_default() -> None:
    with TestClient(app) as client:
        list_response = client.post(
            "/api/lists",
            json={"name": "Active Voice", "color": "#2563eb"},
        )
        list_id = list_response.json()["id"]

        sprint_response = client.post(
            "/api/sprints",
            json={
                "name": "Focus Sprint",
                "directions": ["Health", "Career", "Family", "Growth"],
            },
        )
        sprint_id = sprint_response.json()["id"]

        set_active = client.put("/api/sprints/active", json={"sprint_id": sprint_id})
        assert set_active.status_code == 200

        turn = client.post(
            "/api/voice/chat-turn",
            json={
                "message": "Позвонить клиенту и проверить бюджет",
                "list_id": list_id,
            },
        )
        assert turn.status_code == 200
        tasks = turn.json()["tasks"]
        assert len(tasks) >= 1

        confirm = client.post(
            "/api/voice/confirm-tasks",
            json={"list_id": list_id, "tasks": tasks},
        )
        assert confirm.status_code == 201
        created = confirm.json()["tasks"]
        assert len(created) >= 1
        assert all(task["sprint_id"] == sprint_id for task in created)


def test_voice_chat_can_query_and_update_and_delete_tasks() -> None:
    with TestClient(app) as client:
        list_response = client.post(
            "/api/lists",
            json={"name": "Voice Ops", "color": "#0284c7"},
        )
        list_id = list_response.json()["id"]

        created_1 = client.post(
            "/api/tasks",
            json={
                "title": "Финансы: проверить бюджет",
                "status": "todo",
                "priority": "medium",
                "duration_min": 30,
                "list_id": list_id,
            },
        )
        assert created_1.status_code == 201

        created_2 = client.post(
            "/api/tasks",
            json={
                "title": "Финансы: оплатить налог",
                "status": "todo",
                "priority": "high",
                "duration_min": 20,
                "list_id": list_id,
            },
        )
        assert created_2.status_code == 201

        turn_query = client.post(
            "/api/voice/chat-turn",
            json={
                "message": "Покажи задачи связанные с финансами",
                "list_id": list_id,
            },
        )
        assert turn_query.status_code == 200
        plan_query = turn_query.json()
        assert any(action["action"] == "run_query" for action in plan_query["actions"])

        run_query = client.post(
            "/api/voice/apply-action",
            json={
                "action": "run_query",
                "operation": plan_query["operation"],
                "list_id": list_id,
            },
        )
        assert run_query.status_code == 200
        assert run_query.json()["affected_count"] >= 2

        turn_update = client.post(
            "/api/voice/chat-turn",
            json={
                "message": "Отметь выполненными задачи связанные с финансами",
                "list_id": list_id,
            },
        )
        assert turn_update.status_code == 200
        plan_update = turn_update.json()
        assert any(
            action["action"] == "confirm_update_status"
            for action in plan_update["actions"]
        )

        run_update = client.post(
            "/api/voice/apply-action",
            json={
                "action": "confirm_update_status",
                "operation": plan_update["operation"],
                "list_id": list_id,
            },
        )
        assert run_update.status_code == 200
        assert run_update.json()["affected_count"] >= 2

        turn_delete = client.post(
            "/api/voice/chat-turn",
            json={
                "message": "Удали задачи связанные с финансами",
                "list_id": list_id,
            },
        )
        assert turn_delete.status_code == 200
        plan_delete = turn_delete.json()
        assert any(
            action["action"] == "confirm_delete" for action in plan_delete["actions"]
        )

        preview_delete = client.post(
            "/api/voice/apply-action",
            json={
                "action": "run_query",
                "operation": plan_delete["operation"],
                "list_id": list_id,
            },
        )
        assert preview_delete.status_code == 200
        delete_ids = [task["id"] for task in preview_delete.json()["tasks"]]
        assert len(delete_ids) >= 2

        run_delete = client.post(
            "/api/voice/apply-action",
            json={
                "action": "confirm_delete",
                "operation": plan_delete["operation"],
                "list_id": list_id,
                "task_ids": delete_ids,
            },
        )
        assert run_delete.status_code == 200
        assert run_delete.json()["affected_count"] >= 2


def test_query_intent_does_not_call_provider_for_non_ascii_key(monkeypatch) -> None:
    monkeypatch.setenv("MYLIFE_AI_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ключ_с_кириллицей")

    with TestClient(app) as client:
        list_response = client.post(
            "/api/lists",
            json={"name": "Query List", "color": "#0ea5e9"},
        )
        list_id = list_response.json()["id"]

        client.post(
            "/api/tasks",
            json={
                "title": "Сходить к врачу",
                "status": "todo",
                "priority": "medium",
                "duration_min": 20,
                "list_id": list_id,
            },
        )

        turn = client.post(
            "/api/voice/chat-turn",
            json={
                "message": "Покажи все задачи списком",
                "list_id": list_id,
            },
        )
        assert turn.status_code == 200
        data = turn.json()
        assert data["intent"] == "task_query"
        assert data["error"] is None
        assert any(action["action"] == "run_query" for action in data["actions"])
