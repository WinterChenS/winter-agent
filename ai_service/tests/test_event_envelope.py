import json

from domain.event_envelope import (
    build_envelope,
    envelope_token,
    envelope_message_delta,
    envelope_message_tool_call,
    envelope_message_reasoning,
    envelope_message_done,
    to_sse_data,
)
from observability.trace import TraceContext, ensure_trace_context


def test_required_fields_present():
    ctx = ensure_trace_context("conv-1")
    envelope = build_envelope("token", ctx, payload={"content": "hello"})

    required = {
        "type",
        "schemaVersion",
        "conversationId",
        "turnId",
        "agentId",
        "traceId",
        "spanId",
        "timestamp",
        "payload",
    }
    assert required.issubset(set(envelope.keys()))
    assert envelope["conversationId"] == "conv-1"


def test_compat_flat_fields_dual_write():
    ctx = ensure_trace_context("conv-2")
    envelope = envelope_token(ctx, "hi")

    assert envelope["type"] == "token"
    assert envelope["payload"]["content"] == "hi"
    assert envelope["content"] == "hi"
    assert envelope["token"] == "hi"


def test_payload_preserves_structured_data():
    ctx = ensure_trace_context("conv-3")
    envelope = build_envelope("tool_summary", ctx, payload={"steps": [{"tool": "search"}]})
    sse = to_sse_data(envelope)
    decoded = json.loads(sse["data"])

    assert decoded["payload"]["steps"][0]["tool"] == "search"


def make_ctx():
    return TraceContext(
        conversation_id="conv-1",
        trace_id="tr-1",
        turn_id="turn-1",
        span_id="span-1",
        parent_span_id=None,
        agent_id="agent-1",
    )


def test_message_delta_has_correct_type():
    ctx = make_ctx()
    env = envelope_message_delta(ctx, "msg-1", "Hello")
    assert env["type"] == "message.delta"
    assert env["payload"]["messageId"] == "msg-1"
    assert env["payload"]["delta"] == "Hello"
    assert env["payload"]["agentId"] == "agent-1"


def test_message_tool_call_has_toolcall_payload():
    ctx = make_ctx()
    tc = {"id": "tc-1", "name": "search", "arguments": {"q": "x"}, "status": "running"}
    env = envelope_message_tool_call(ctx, "msg-1", tc)
    assert env["type"] == "message.tool_call"
    assert env["payload"]["toolCall"]["id"] == "tc-1"
    assert env["payload"]["toolCall"]["status"] == "running"


def test_message_reasoning():
    ctx = make_ctx()
    env = envelope_message_reasoning(ctx, "msg-1", "Let me think...")
    assert env["type"] == "message.reasoning"
    assert env["payload"]["delta"] == "Let me think..."


def test_message_done_success():
    ctx = make_ctx()
    env = envelope_message_done(ctx, "msg-1", status="done")
    assert env["type"] == "message.done"
    assert env["payload"]["status"] == "done"
    assert "error" not in env["payload"]


def test_message_done_error():
    ctx = make_ctx()
    env = envelope_message_done(ctx, "msg-1", status="error", error="Agent not found")
    assert env["payload"]["status"] == "error"
    assert env["payload"]["error"] == "Agent not found"


def test_to_sse_data_wraps_json():
    ctx = make_ctx()
    env = envelope_message_delta(ctx, "msg-1", "x")
    sse = to_sse_data(env)
    assert "data" in sse
    assert "message.delta" in sse["data"]


class TestToolProgressEnvelope:
    def test_envelope_tool_progress(self):
        """tool.progress 信封应包含进度百分比和消息。"""
        from domain.event_envelope import envelope_tool_progress

        ctx = make_ctx()
        envelope = envelope_tool_progress(ctx, tool_name="execute_python", progress=50, message="Executing...")
        assert envelope["type"] == "tool.progress"
        assert envelope["payload"]["toolName"] == "execute_python"
        assert envelope["payload"]["progress"] == 50
        assert envelope["payload"]["message"] == "Executing..."

    def test_envelope_tool_output(self):
        """tool.output 信封应携带输出内容块。"""
        from domain.event_envelope import envelope_tool_output

        ctx = make_ctx()
        envelope = envelope_tool_output(ctx, tool_name="execute_python", output="print('hello')", chunk_index=0)
        assert envelope["type"] == "tool.output"
        assert envelope["payload"]["toolName"] == "execute_python"
        assert envelope["payload"]["output"] == "print('hello')"
        assert envelope["payload"]["chunkIndex"] == 0

    def test_envelope_tool_completed(self):
        """tool.completed 信封应携带最终结果和耗时。"""
        from domain.event_envelope import envelope_tool_completed

        ctx = make_ctx()
        envelope = envelope_tool_completed(ctx, tool_name="execute_python", result={"ok": True}, elapsed_ms=1500)
        assert envelope["type"] == "tool.completed"
        assert envelope["payload"]["toolName"] == "execute_python"
        assert envelope["payload"]["elapsed_ms"] == 1500

