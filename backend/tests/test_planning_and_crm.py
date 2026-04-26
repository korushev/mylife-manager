from fastapi.testclient import TestClient

from backend.app.main import app


def test_tasks_sprints_calendar_and_crm_flow() -> None:
    with TestClient(app) as client:
        list_response = client.post(
            "/api/lists", json={"name": "Work", "color": "#0ea5e9"}
        )
        assert list_response.status_code == 201
        list_id = list_response.json()["id"]

        sprint_response = client.post(
            "/api/sprints",
            json={
                "name": "Sprint 1",
                "directions": ["Health", "Career", "Family", "Systems"],
            },
        )
        assert sprint_response.status_code == 201
        sprint = sprint_response.json()
        sprint_id = sprint["id"]
        direction_id = sprint["directions"][0]["id"]

        task_response = client.post(
            "/api/tasks",
            json={
                "title": "Plan week",
                "status": "todo",
                "priority": "high",
                "duration_min": 60,
                "list_id": list_id,
                "sprint_id": sprint_id,
                "sprint_direction_id": direction_id,
            },
        )
        assert task_response.status_code == 201
        task_id = task_response.json()["id"]

        move_response = client.post(
            f"/api/tasks/{task_id}/move", json={"status": "in_progress"}
        )
        assert move_response.status_code == 200
        assert move_response.json()["status"] == "in_progress"

        block_response = client.post(
            "/api/time-blocks",
            json={
                "task_id": task_id,
                "start_at": "2026-04-28T08:00:00+00:00",
                "end_at": "2026-04-28T09:00:00+00:00",
            },
        )
        assert block_response.status_code == 201

        calendar_response = client.get("/api/calendar")
        assert calendar_response.status_code == 200
        assert len(calendar_response.json()) >= 1

        contact_response = client.post(
            "/api/crm/contacts",
            json={"full_name": "Test Client", "email": "client@example.com"},
        )
        assert contact_response.status_code == 201
        contact_id = contact_response.json()["id"]

        deal_response = client.post(
            "/api/crm/deals",
            json={
                "title": "Website redesign",
                "contact_id": contact_id,
                "status": "lead",
                "value_amount": 1200,
                "linked_task_id": task_id,
            },
        )
        assert deal_response.status_code == 201
        assert deal_response.json()["contact_id"] == contact_id
