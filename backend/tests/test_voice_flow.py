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
        parsed = parse_response.json()
        assert parsed["status"] == "in_progress"
        assert parsed["priority"] == "high"
        assert parsed["duration_min"] == 45

        create_response = client.post(
            "/api/voice/create-task",
            json={
                "transcript": "Сделать рефакторинг модуля, medium, 30 min",
                "list_id": list_id,
            },
        )
        assert create_response.status_code == 201
        task = create_response.json()
        assert task["title"]
        assert task["list_id"] == list_id
        assert task["duration_min"] == 30
