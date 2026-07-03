from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from graph.nodes import agent_node


@pytest.mark.asyncio
async def test_agent_node_includes_runtime_context_before_observation(monkeypatch):
    captured = {}

    class _LLM:
        async def ainvoke(self, messages):
            captured["system_prompt"] = messages[0].content
            return AIMessage(content='{"action": "final_answer"}')

    monkeypatch.setattr("graph.nodes._build_llm", lambda streaming=False, json_mode=True: _LLM())
    monkeypatch.setattr("graph.nodes.get_tool_registry", lambda: None)

    await agent_node(
        {
            "messages": [HumanMessage(content="继续")],
            "active_agent": "default",
            "iteration_count": 1,
            "tool_result": '{"ok": true, "data": {"query": "历史", "results": []}}',
            "runtime_context_prompt": "[session]\nuser: 历史",
            "reasoning_steps": [],
        }
    )

    assert "[session]" in captured["system_prompt"]
    assert captured["system_prompt"].index("[session]") < captured["system_prompt"].index("--- Observation")