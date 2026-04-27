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
