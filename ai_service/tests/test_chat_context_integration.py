from fastapi.testclient import TestClient

from api.routes import chat as chat_route
from main import app


class _FakeGraph:
    def __init__(self, captured):
        self._captured = captured

    async def astream_events(self, inputs, config=None, version=None):
        self._captured["inputs"] = inputs
        self._captured["config"] = config
        self._captured["version"] = version
        if False:
            yield None


class _FakeAgentRepo:
    async def get_by_id(self, agent_id):
        return {"id": agent_id}


def test_stream_endpoint_degrades_when_pool_acquisition_fails(monkeypatch):
    captured = {}

    monkeypatch.setattr(chat_route.settings, "api_key", "test-key")
    monkeypatch.setattr(chat_route, "get_pool", lambda: (_ for _ in ()).throw(RuntimeError("pool down")))
    monkeypatch.setattr(chat_route, "get_checkpointer", lambda: None)
    monkeypatch.setattr(chat_route, "create_plan_execute_graph", lambda **_: _FakeGraph(captured))

    client = TestClient(app)
    response = client.post(
        "/api/v1/generate/stream",
        json={"message": "继续", "conversationId": "conv-ctx-fallback"},
    )

    assert response.status_code == 200
    assert captured["inputs"]["conversation_id"] == "conv-ctx-fallback"
    assert captured["inputs"]["active_agent"] == "default"
    assert captured["inputs"]["runtime_context_prompt"] is None
    assert captured["inputs"]["runtime_context_messages"] == []
    assert captured["inputs"]["runtime_context_meta"] is None


def test_stream_endpoint_passes_runtime_context_into_graph_state(monkeypatch):
    captured = {}

    async def fake_build_runtime_context(pool, conversation_id, active_agent, user_query):
        captured["conversation_id"] = conversation_id
        captured["active_agent"] = active_agent
        captured["user_query"] = user_query
        return type(
            "Ctx",
            (),
            {
                "rendered_prompt": "[session]\nuser: 历史",
                "recent_messages": [{"role": "user", "content": "历史"}],
                "metadata": {"providers": ["session"], "source": "session"},
            },
        )()

    monkeypatch.setattr(chat_route.settings, "api_key", "test-key")
    monkeypatch.setattr(chat_route, "get_pool", lambda: None)
    monkeypatch.setattr(chat_route, "get_checkpointer", lambda: None)
    monkeypatch.setattr(chat_route, "get_agent_repository", lambda: _FakeAgentRepo())
    monkeypatch.setattr(chat_route, "create_plan_execute_graph", lambda **_: _FakeGraph(captured))
    monkeypatch.setattr(chat_route, "_build_runtime_context", fake_build_runtime_context, raising=False)

    client = TestClient(app)
    response = client.post(
        "/api/v1/generate/stream",
        json={"message": "继续", "conversationId": "conv-ctx-1", "agentId": "agent-42"},
    )

    assert response.status_code == 200
    assert captured["conversation_id"] == "conv-ctx-1"
    assert captured["active_agent"] == "agent-42"
    assert captured["user_query"] == "继续"
    assert captured["inputs"]["conversation_id"] == "conv-ctx-1"
    assert captured["inputs"]["active_agent"] == "agent-42"
    assert captured["inputs"]["runtime_context_prompt"] == "[session]\nuser: 历史"
    assert captured["inputs"]["runtime_context_messages"] == [{"role": "user", "content": "历史"}]
    assert captured["inputs"]["runtime_context_meta"] == {"providers": ["session"], "source": "session"}