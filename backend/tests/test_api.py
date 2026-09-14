from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_agent_generates_typed_workflow() -> None:
    response = client.post("/api/agent/generate", json={"prompt": "创建一个 7 镜头短视频"})
    assert response.status_code == 200
    body = response.json()
    assert len(body["nodes"]) == 6
    assert len(body["edges"]) == 5
    storyboard = next(node for node in body["nodes"] if node["data"]["kind"] == "storyboard")
    assert storyboard["data"]["config"]["scenes"] == 7

