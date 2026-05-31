# P0 JSON Mode + Three-Phase Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace fragile text-based JSON parsing with JSON Mode in a three-phase pipeline (ReAct data collection → chart planning → streaming answer), with charts dynamically interleaved in text via `[CHART:n]` markers.

**Architecture:** Three-phase LangGraph pipeline. Phase 1: JSON Mode ReAct loop for tool calls. Phase 2: JSON Mode chart planner extracts charts from conversation. Phase 3: Normal Mode streaming answer with `[CHART:n]` markers. All manual JSON parsing, chart denial filtering, preamble buffering, and control JSON buffering removed.

**Tech Stack:** Python FastAPI, LangGraph, LangChain OpenAI, DeepSeek v4-flash, React + TypeScript + ECharts

---

### Task 1: Remove dead code

**Files:**
- Delete: `ai_service/graph/chart_planner.py`
- Delete: `ai_service/graph/chart_generator.py`
- Delete: `ai_service/graph/content_composer.py`
- Delete: `ai_service/tools/chart/tool.py`
- Delete: `ai_service/tools/output_text/tool.py`
- Delete: `ai_service/tools/echo/tool.py`
- Delete: `ai_service/tools/echo/__init__.py`
- Modify: `ai_service/tools/__init__.py`

- [ ] **Step 1: Delete legacy chart pipeline files**

```bash
rm ai_service/graph/chart_planner.py
rm ai_service/graph/chart_generator.py
rm ai_service/graph/content_composer.py
```

- [ ] **Step 2: Delete ChartTool and OutputTextTool**

```bash
rm ai_service/tools/chart/tool.py
rm ai_service/tools/output_text/tool.py
```

- [ ] **Step 3: Delete EchoTool (commented out in main.py, unused)**

```bash
rm ai_service/tools/echo/tool.py
rm ai_service/tools/echo/__init__.py
```

- [ ] **Step 4: Update tools/__init__.py to remove dead imports**

Read `ai_service/tools/__init__.py` and if it has re-exports of ChartTool/EchoTool/OutputTextTool, remove them.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: remove dead code (legacy chart pipeline, ChartTool, OutputTextTool, EchoTool)"
```

---

### Task 2: Add route field to State and validators module

**Files:**
- Modify: `ai_service/graph/state.py`
- Create: `ai_service/graph/validators.py`

- [ ] **Step 1: Add `route` field to State**

```python
# ai_service/graph/state.py — append to State TypedDict:
class State(TypedDict):
    # ... existing fields ...

    # ── V0.4 three-phase routing ─────────────────────────────────────────
    route: str  # "tool" | "chart_planner" | "answer" | "end"
```

Use Edit to add this field before the closing `}` of the State class.

- [ ] **Step 2: Create validators.py for ChartSpec validation**

```python
# ai_service/graph/validators.py
from __future__ import annotations

import logging
from domain.chart_spec import ChartSpec, ChartDataPoint, ChartType

logger = logging.getLogger(__name__)

ALLOWED_CHART_TYPES: set[str] = {"line", "bar", "pie", "scatter", "area", "radar"}

MAX_DATA_POINTS = 20
MAX_TITLE_LEN = 200
MAX_DESC_LEN = 500
MAX_LABEL_LEN = 100


def _validate_chart_type(ct: str) -> str:
    ct = str(ct).strip().lower()
    return ct if ct in ALLOWED_CHART_TYPES else "bar"


def _validate_data_points(data: list) -> list[ChartDataPoint]:
    result = []
    for d in data[:MAX_DATA_POINTS]:
        if not isinstance(d, dict):
            continue
        name = str(d.get("name", "")).strip()
        if not name:
            continue
        try:
            value = float(d.get("value", 0))
        except (ValueError, TypeError):
            continue
        group = str(d.get("group", "")).strip()
        result.append(ChartDataPoint(name=name, value=value, group=group))
    return result


def validate_chart_specs(charts: list) -> list[dict]:
    """Validate and normalize chart specs from LLM output. Returns list of ChartSpec dicts."""
    valid = []
    for c in charts:
        if not isinstance(c, dict):
            continue
        try:
            spec = ChartSpec(
                id=int(c.get("id", len(valid))),
                title=str(c.get("title", ""))[:MAX_TITLE_LEN],
                chart_type=_validate_chart_type(c.get("chart_type", "bar")),
                description=str(c.get("description", ""))[:MAX_DESC_LEN],
                x_axis_label=str(c.get("x_axis_label", ""))[:MAX_LABEL_LEN],
                y_axis_label=str(c.get("y_axis_label", ""))[:MAX_LABEL_LEN],
                data=_validate_data_points(c.get("data", [])),
            )
            if spec.data:
                valid.append(spec.to_dict())
        except Exception as e:
            logger.warning("Chart validation failed for item: %s", e)
    return valid
```

- [ ] **Step 3: Create test for validators**

```python
# ai_service/tests/test_chart_validators.py
import pytest
from graph.validators import validate_chart_specs, _validate_chart_type, _validate_data_points, MAX_DATA_POINTS

def test_validate_empty_list():
    assert validate_chart_specs([]) == []

def test_validate_non_dict_skipped():
    assert validate_chart_specs(["not-a-dict", 123, None]) == []

def test_validate_basic_chart():
    result = validate_chart_specs([{
        "id": 0,
        "chart_type": "bar",
        "title": "Test Chart",
        "data": [{"name": "A", "value": 10}, {"name": "B", "value": 20}],
    }])
    assert len(result) == 1
    assert result[0]["chartType"] == "bar"
    assert len(result[0]["data"]) == 2

def test_validate_chart_type_fallback():
    result = validate_chart_specs([{
        "id": 0,
        "chart_type": "invalid_type",
        "title": "Test",
        "data": [{"name": "A", "value": 1}],
    }])
    assert result[0]["chartType"] == "bar"

def test_validate_no_data_skipped():
    result = validate_chart_specs([{
        "id": 0,
        "chart_type": "bar",
        "title": "Empty",
        "data": [],
    }])
    assert result == []

def test_validate_invalid_data_points_skipped():
    result = validate_chart_specs([{
        "id": 0,
        "chart_type": "bar",
        "title": "Bad Data",
        "data": [
            {"name": "", "value": 10},  # empty name
            {"name": "B", "value": "not-a-number"},  # bad value
            {"name": "C", "value": 30},  # valid
        ],
    }])
    assert len(result[0]["data"]) == 1
    assert result[0]["data"][0]["name"] == "C"

def test_validate_truncates_over_max():
    data = [{"name": f"Item{i}", "value": i} for i in range(MAX_DATA_POINTS + 10)]
    result = validate_chart_specs([{
        "id": 0,
        "chart_type": "bar",
        "title": "Large",
        "data": data,
    }])
    assert len(result[0]["data"]) == MAX_DATA_POINTS

def test_validate_multi_chart():
    result = validate_chart_specs([
        {"id": 0, "chart_type": "bar", "title": "C1", "data": [{"name": "A", "value": 1}]},
        {"id": 1, "chart_type": "pie", "title": "C2", "data": [{"name": "B", "value": 2}]},
    ])
    assert len(result) == 2

def test_validate_truncates_long_strings():
    result = validate_chart_specs([{
        "id": 0,
        "chart_type": "bar",
        "title": "T" * 300,
        "description": "D" * 600,
        "x_axis_label": "X" * 200,
        "y_axis_label": "Y" * 200,
        "data": [{"name": "A", "value": 1}],
    }])
    assert len(result[0]["title"]) <= 200
    assert len(result[0]["description"]) <= 500
    assert len(result[0]["xAxisLabel"]) <= 100
    assert len(result[0]["yAxisLabel"]) <= 100
```

- [ ] **Step 4: Run tests**

```bash
cd ai_service && python -m pytest tests/test_chart_validators.py -v
```

Expected: 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add ai_service/graph/state.py ai_service/graph/validators.py ai_service/tests/test_chart_validators.py
git commit -m "feat: add route field to State, add ChartSpec validators with tests"
```

---

### Task 3: Rewrite agent_node with JSON Mode

**Files:**
- Modify: `ai_service/graph/nodes.py`

- [ ] **Step 1: Replace the system prompt with JSON Mode version**

Replace `_REACT_SYSTEM_PROMPT` (lines 30-53) with:

```python
_REACT_SYSTEM_PROMPT = """\
You are a ReAct agent. Your response MUST be a single valid JSON object.

[Internal Cycle: Thought → Action → Observation → Final Answer]

CRITICAL: Output ONLY the JSON object. No markdown wrapping, no explanation.

Tool call format:
{"action":"tool","tool":"<name>","query":"<query>"}

Final answer ready (data collection complete):
{"action":"final_answer"}

Available tools:
- search: web search. Returns titles, URLs, and content snippets.
- browser: open a URL and read its content. MUST use exact URL from search results. Never fabricate URLs.
- time: get current date/time. Use for time-related questions.

Rules:
1. Output ONLY the JSON. No other text.
2. After search results, use browser to read at least one relevant page before concluding.
3. If browser returns an error, fall back to using search snippets — do NOT retry browser.
4. Call final_answer only when you have sufficient information to answer the user's question fully.
"""
```

- [ ] **Step 2: Rewrite `_build_llm()` to accept `response_format` parameter**

```python
def _build_llm(streaming: bool = True, json_mode: bool = False) -> ChatOpenAI:
    kwargs = {
        "model": settings.model,
        "temperature": 0.3 if json_mode else settings.temperature,
        "streaming": streaming,
        "api_key": settings.api_key,
        "base_url": settings.base_url,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    return ChatOpenAI(**kwargs)
```

Remove the old `_build_llm` function and the `extra_body={"thinking": {"type": "disabled"}}` line.

- [ ] **Step 3: Rewrite `agent_node()` — core logic**

Replace the current `agent_node` function (lines 266-545) with:

```python
async def agent_node(state: State) -> dict:
    registry = get_tool_registry()

    # 1. Build tool list description
    tools_desc = ""
    if registry:
        for t in registry.list_tools():
            tools_desc += f"  - {t['name']}: {t['description']}\n"

    # 2. Build system prompt with Observation
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    tool_result = state.get("tool_result")
    tool_result_sanitized = normalize_tool_result_for_prompt(tool_result)
    current_iteration = int(state.get("iteration_count", 0) or 0)

    system_lines = [
        _REACT_SYSTEM_PROMPT,
        f"Current server time: {now_str}",
    ]
    if tools_desc:
        system_lines.append(f"Available tools:\n{tools_desc}")

    if tool_result_sanitized:
        remaining = MAX_ITERATIONS - current_iteration
        system_lines.append(
            f"\n--- Observation (iteration {current_iteration}/{MAX_ITERATIONS}) ---\n"
            f"{tool_result_sanitized}\n"
            "--- End Observation ---\n"
        )
        system_lines.append(
            "Continue the ReAct cycle: if you need more info, call another tool. "
            f"Otherwise, output final_answer. ({remaining} iterations remaining)"
        )

    system_prompt = "\n".join(system_lines)

    # 3. Call LLM with JSON Mode
    messages = [SystemMessage(content=system_prompt)] + list(state["messages"])
    llm = _build_llm(streaming=False, json_mode=True)

    try:
        response = await llm.ainvoke(messages)
        content = (response.content or "").strip()
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("agent_node: JSON parse failed, forcing final answer: %s", e)
        return _force_final_answer(state, tool_result)

    action = str(parsed.get("action", "")).strip().lower()

    # 4. Handle tool call
    if action == "tool":
        tool_name = str(parsed.get("tool", "")).strip().lower()
        query = str(parsed.get("query", "")).strip()

        if not tool_name:
            return _force_final_answer(state, tool_result)

        normalized_query = _normalize_query(query)
        consecutive_search_count = int(state.get("consecutive_search_count", 0) or 0)
        next_consecutive = consecutive_search_count + 1 if tool_name == "search" else 0

        # Guard: max iterations
        if current_iteration >= MAX_ITERATIONS:
            reason = _reason_record("agent_node", "MAX_ITERATIONS_REACHED",
                f"Iteration limit ({MAX_ITERATIONS}) reached; forcing final answer.")
            return _force_final_answer(state, tool_result, reason)

        # Guard: duplicate tool call
        last_tool_name = (state.get("last_tool_name") or "").strip().lower()
        last_tool_query = _normalize_query(str(state.get("last_tool_query") or ""))
        if last_tool_name == tool_name and last_tool_query == normalized_query:
            reason = _reason_record("agent_node", "DUPLICATE_TOOL_CALL_BLOCKED",
                f"Blocked duplicate: tool='{tool_name}', query='{query}'.",
                extra={"tool": tool_name, "query": query})
            return _force_final_answer(state, tool_result, reason)

        # Guard: max consecutive search
        max_search = _max_consecutive_search_calls()
        if tool_name == "search" and next_consecutive > max_search:
            reason = _reason_record("agent_node", "MAX_CONSECUTIVE_SEARCH_REACHED",
                f"Consecutive search limit ({max_search}) reached; forcing final answer.",
                extra={"count": next_consecutive, "limit": max_search})
            return _force_final_answer(state, tool_result, reason)

        reason = _reason_record("agent_node", "TOOL_CALL_DECIDED",
            f"Tool call: '{tool_name}' query='{query}'", extra={"tool": tool_name})
        return {
            "current_tool": tool_name,
            "tool_input": {"query": query},
            "tool_result": None,
            "iteration_count": current_iteration + 1,
            "last_tool_name": tool_name,
            "last_tool_query": query,
            "consecutive_search_count": next_consecutive,
            "reasoning_steps": _append_reason(state, reason),
            "route": "tool",
        }

    # 5. Handle final_answer
    if action == "final_answer":
        reason = _reason_record("agent_node", "FINAL_ANSWER",
            "Agent decided data collection is complete.")
        return {
            "current_tool": None,
            "tool_input": None,
            "tool_result": None,
            "last_tool_name": None,
            "last_tool_query": None,
            "consecutive_search_count": 0,
            "reasoning_steps": _append_reason(state, reason),
            "route": "chart_planner",
        }

    # Unknown action → force final
    logger.warning("agent_node: unknown action '%s', forcing final answer", action)
    return _force_final_answer(state, tool_result)
```

- [ ] **Step 4: Add helper `_force_final_answer()`**

```python
def _force_final_answer(state: State, tool_result: str | None,
                         reason: dict | None = None) -> dict:
    """Force transition to chart_planner when guardrails trigger."""
    record = reason or _reason_record("agent_node", "FORCED_FINAL",
        "Forcing transition to chart planner.")
    return {
        "current_tool": None,
        "tool_input": None,
        "tool_result": None,
        "last_tool_name": None,
        "last_tool_query": None,
        "consecutive_search_count": 0,
        "last_guard_reason": record,
        "reasoning_steps": _append_reason(state, record),
        "route": "chart_planner",
    }
```

- [ ] **Step 5: Remove dead functions**

Delete these functions from nodes.py:
- `_parse_tool_call()` (lines 119-164)
- `_extract_tool_from_parsed()` (lines 167-200)
- `_strip_thought_tags()` (lines 208-216)
- `_extract_iso_date()` (lines 203-205)
- `_generate_forced_final_answer()` (lines 234-260)
- `_latest_user_text()` (lines 219-231)
- `_build_local_final_fallback()` (lines 679-683)
- `_build_observation_message()` (lines 686-720)
- `llm_node()` (lines 669-672)

- [ ] **Step 6: Verify nodes.py has no import errors**

```bash
cd ai_service && python -c "from graph.nodes import agent_node, tool_node; print('OK')"
```

Expected: OK

- [ ] **Step 7: Commit**

```bash
git add ai_service/graph/nodes.py
git commit -m "refactor: rewrite agent_node with JSON Mode, remove text-based JSON parsing"
```

---

### Task 4: Rewrite tool_node (simplify, remove chart/text inline blocks)

**Files:**
- Modify: `ai_service/graph/nodes.py`

- [ ] **Step 1: Rewrite `tool_node()` — remove pending_chart_spec and pending_text_block logic**

Replace the `tool_node` function (lines 551-663) with:

```python
async def tool_node(state: State) -> dict:
    tool_name = state.get("current_tool") or ""
    tool_input = state.get("tool_input") or {}
    start_time = time.time()
    gate = _build_policy_gate()
    call = CapabilityCall(capability_name=tool_name, input_payload=tool_input)

    decision = gate.evaluate(
        call,
        context=PolicyContext(
            conversation_id=str(state.get("conversation_id") or ""),
            agent_id=str(state.get("active_agent") or "agent.main"),
        ),
    )

    if decision.action != "allow":
        result = {
            "ok": False,
            "error": {
                "code": decision.code or "POLICY_DENIED",
                "message": decision.reason or "Blocked by policy gate",
                "retryable": False,
            },
        }
        result_str = json.dumps(result, ensure_ascii=False)
        step = f"[tool_node] Policy denied '{tool_name}': {decision.reason or decision.code}"
        status = "error"
        error_msg = _error_text(result.get("error"))
    else:
        registry = get_tool_registry()
        if not registry:
            result = {"ok": False, "error": "ToolRegistry not initialized"}
            result_str = json.dumps(result, ensure_ascii=False)
            step = f"[tool_node] ERROR: registry not available, skipped '{tool_name}'"
            status = "error"
            error_msg = "ToolRegistry not initialized"
        else:
            try:
                timeout_ms = gate.timeout_override_ms
                if timeout_ms and timeout_ms > 0:
                    result = await asyncio.wait_for(
                        registry.invoke_capability(call),
                        timeout=timeout_ms / 1000,
                    )
                else:
                    result = await registry.invoke_capability(call)
            except asyncio.TimeoutError:
                result = {
                    "ok": False,
                    "error": {
                        "code": "TOOL_TIMEOUT",
                        "message": "tool invocation timeout",
                        "retryable": True,
                    },
                }
            except Exception as exc:
                logger.exception("tool_node invoke failed for tool=%s", tool_name)
                result = {
                    "ok": False,
                    "error": {
                        "code": "TOOL_INVOKE_EXCEPTION",
                        "message": f"tool invoke exception: {str(exc)[:200]}",
                        "retryable": False,
                    },
                }

            result_str = json.dumps(result, ensure_ascii=False)
            ok = bool(result.get("ok", False))
            status = "completed" if ok else "error"
            error_msg = _error_text(result.get("error")) if not ok else None
            step = (
                f"[tool_node] Tool '{tool_name}' executed successfully."
                if ok
                else f"[tool_node] Tool '{tool_name}' returned error: {error_msg}"
            )

    elapsed_time = time.time() - start_time
    tool_step_record = normalize_tool_step_record(
        tool_name=tool_name,
        tool_input=tool_input,
        status=status,
        elapsed_ms=int(elapsed_time * 1000),
        timestamp=start_time,
        error=error_msg,
    )

    new_tool_steps = list(state.get("tool_steps", [])) + [tool_step_record]

    return {
        "tool_result": result_str,
        "tool_steps": new_tool_steps,
        "current_tool": None,
        "tool_input": None,
        "last_tool_name": None,
        "last_tool_query": None,
        "reasoning_steps": _append_reason(state, step),
        "route": "agent",
    }
```

Key changes from old tool_node:
- Removed `pending_chart_spec`, `pending_text_block`, `chart_specs` extra fields
- Added explicit `"route": "agent"` return

- [ ] **Step 2: Verify tool_node works**

```bash
cd ai_service && python -c "from graph.nodes import tool_node; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add ai_service/graph/nodes.py
git commit -m "refactor: simplify tool_node, remove inline chart/text block handling"
```

---

### Task 5: Add chart_planner_node and answer_node

**Files:**
- Modify: `ai_service/graph/nodes.py`

- [ ] **Step 1: Add chart_planner_node**

Append to nodes.py:

```python
# ────────────────────────────────────────────────────────────────────────────
# chart_planner_node：JSON Mode 图表规划（阶段二）
# ────────────────────────────────────────────────────────────────────────────
_CHART_PLANNER_SYSTEM_PROMPT = """\
You are a data analyst. Analyze the conversation below and extract chart-worthy numerical data.
Output a single valid JSON object. No markdown wrapping.

{
  "charts": [
    {
      "id": 0,
      "chart_type": "bar",
      "title": "Chart Title",
      "description": "What this chart shows",
      "x_axis_label": "X Label",
      "y_axis_label": "Y Label",
      "data": [
        {"name": "Item A", "value": 123},
        {"name": "Item B", "value": 456}
      ]
    }
  ]
}

Rules:
- chart_type: line | bar | pie | scatter | area | radar
- id: sequential integer starting from 0
- data: maximum 20 data points
- pie chart: do NOT set x_axis_label or y_axis_label
- Use ONLY data found in the conversation — never fabricate numbers
- If there is NO numerical data suitable for charts, return {"charts": []}
"""


async def chart_planner_node(state: State) -> dict:
    """Phase 2: Extract chart data from conversation context using JSON Mode."""
    from graph.validators import validate_chart_specs

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    system_content = _CHART_PLANNER_SYSTEM_PROMPT
    if now_str:
        system_content += f"\nCurrent time: {now_str}"

    messages = [SystemMessage(content=system_content)] + list(state["messages"])

    llm = _build_llm(streaming=False, json_mode=True)
    # Override temperature for chart extraction — precision matters
    llm.temperature = 0.1

    try:
        response = await llm.ainvoke(messages)
        result = json.loads(response.content)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("chart_planner_node: JSON parse failed: %s", e)
        result = {"charts": []}

    raw_charts = result.get("charts", [])
    if not isinstance(raw_charts, list):
        raw_charts = []

    validated = validate_chart_specs(raw_charts)

    return {
        "chart_specs": validated,
        "route": "answer",
    }
```

- [ ] **Step 2: Add answer_node**

Append to nodes.py:

```python
# ────────────────────────────────────────────────────────────────────────────
# answer_node：Normal Mode 流式最终答案（阶段三）
# ────────────────────────────────────────────────────────────────────────────
_ANSWER_SYSTEM_PROMPT_TEMPLATE = """\
You are a helpful AI assistant. Answer the user's question based on the research results.
Use Markdown for formatting and structure.

{chart_section}

[Output Instructions]
- When your analysis reaches a point where a chart would help illustrate the data,
  reference it using [CHART:n] on its own line (e.g., a line containing only "[CHART:0]")
- Each available chart MUST be referenced at least once in your answer
- When you reference a chart, do NOT repeat all its data values as text — trust the chart
- Write naturally as if the chart is embedded in your response
- Keep answers concise and well-structured
- Reply in the same language as the user's question

Current time: {now_str}
"""


def _build_chart_section(chart_specs: list[dict]) -> str:
    """Build the chart description section for the answer prompt."""
    if not chart_specs:
        return "[Available Charts]\nNone. Answer without referencing any charts."

    lines = ["[Available Charts]"]
    for c in chart_specs:
        cid = c.get("id", "?")
        ctype = c.get("chartType", "bar")
        title = c.get("title", "Untitled")
        desc = c.get("description", "")
        x_label = c.get("xAxisLabel", "")
        y_label = c.get("yAxisLabel", "")
        data_count = len(c.get("data", []))
        lines.append(
            f"  Chart {cid} ({ctype}): \"{title}\" — {desc} "
            f"({data_count} data points, x={x_label}, y={y_label})"
        )
    return "\n".join(lines)


async def answer_node(state: State) -> dict:
    """Phase 3: Generate streaming final answer with [CHART:n] markers."""
    chart_specs = list(state.get("chart_specs", []) or [])
    chart_section = _build_chart_section(chart_specs)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    system_content = _ANSWER_SYSTEM_PROMPT_TEMPLATE.format(
        chart_section=chart_section,
        now_str=now_str,
    )

    messages = [SystemMessage(content=system_content)] + list(state["messages"])

    llm = _build_llm(streaming=True, json_mode=False)

    try:
        response = await llm.ainvoke(messages)
    except Exception as exc:
        logger.exception("answer_node: LLM invoke failed")
        fallback = "抱歉，生成回答时出现错误，请重试。"
        return {
            "messages": [AIMessage(content=fallback)],
            "chart_specs": chart_specs,
            "route": "end",
        }

    return {
        "messages": [response],
        "chart_specs": chart_specs,
        "route": "end",
    }
```

- [ ] **Step 3: Verify imports and syntax**

```bash
cd ai_service && python -c "from graph.nodes import agent_node, tool_node, chart_planner_node, answer_node; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add ai_service/graph/nodes.py
git commit -m "feat: add chart_planner_node (JSON Mode) and answer_node (streaming with [CHART:n] markers)"
```

---

### Task 6: Rewrite graph.py for three-phase routing

**Files:**
- Modify: `ai_service/graph/graph.py`

- [ ] **Step 1: Replace graph.py**

```python
# ai_service/graph/graph.py
from langgraph.graph import StateGraph, END

from graph.nodes import agent_node, tool_node, chart_planner_node, answer_node, MAX_ITERATIONS
from graph.state import State


def _route_after_agent(state: State) -> str:
    route = state.get("route", "chart_planner")
    if route == "tool" and int(state.get("iteration_count", 0) or 0) <= MAX_ITERATIONS:
        return "tool"
    return "chart_planner"


def _route_after_tool(state: State) -> str:
    route = state.get("route", "agent")
    return route  # "agent" to loop back


def _route_after_chart_planner(state: State) -> str:
    route = state.get("route", "answer")
    return route  # "answer"


def _route_after_answer(state: State) -> str:
    route = state.get("route", "end")
    return route if route == "end" else END


def create_agent_graph(checkpointer=None):
    """
    V0.4 three-phase pipeline:

    Phase 1: JSON Mode ReAct
        agent_node ←→ tool_node (search/browser/time)

    Phase 2: JSON Mode Chart Planning
        chart_planner_node (extracts charts from conversation)

    Phase 3: Normal Mode Streaming Answer
        answer_node (streaming text with [CHART:n] markers)
    """
    workflow = StateGraph(State)

    workflow.add_node("agent", agent_node)
    workflow.add_node("tool", tool_node)
    workflow.add_node("chart_planner", chart_planner_node)
    workflow.add_node("answer", answer_node)

    workflow.set_entry_point("agent")

    workflow.add_conditional_edges("agent", _route_after_agent, {
        "tool": "tool",
        "chart_planner": "chart_planner",
        END: END,
    })

    workflow.add_conditional_edges("tool", _route_after_tool, {
        "agent": "agent",
        END: END,
    })

    workflow.add_conditional_edges("chart_planner", _route_after_chart_planner, {
        "answer": "answer",
        END: END,
    })

    workflow.add_conditional_edges("answer", _route_after_answer, {
        "end": END,
        END: END,
    })

    return workflow.compile(checkpointer=checkpointer)
```

- [ ] **Step 2: Verify graph compiles**

```bash
cd ai_service && python -c "from graph.graph import create_agent_graph; g = create_agent_graph(); print('Graph compiled OK')"
```

- [ ] **Step 3: Commit**

```bash
git add ai_service/graph/graph.py
git commit -m "refactor: rewrite graph for three-phase pipeline (agent → chart_planner → answer)"
```

---

### Task 7: Simplify event_mapper.py

**Files:**
- Modify: `ai_service/api/events/event_mapper.py`

- [ ] **Step 1: Delete dead functions**

Remove:
- `_filter_chart_denial()` (lines 24-43)
- `_stream_event_with_content()` (lines 46-53)
- `safe_json_loads()` (lines 57-61)
- `is_tool_action_json()` (lines 65-68)
- `is_tool_action_json_str()` (lines 70-85)
- `process_stream_token_event()` (lines 88-141) — the entire JSON filtering pipeline

- [ ] **Step 2: Simplify `map_langgraph_event_to_envelopes()`**

Replace with a version that does NOT filter tool JSON from stream (this is now handled by JSON Mode — no tool JSON leaks into the text stream):

```python
def map_langgraph_event_to_envelopes(
    event: dict[str, Any],
    ctx: EventMapContext,
    active_tool_span_id: str | None,
) -> tuple[list[dict[str, Any]], str | None, dict[str, Any] | None]:
    envelopes: list[dict[str, Any]] = []
    final_state: dict[str, Any] | None = None

    event_type = event.get("event")
    event_name = event.get("name")

    if event_type == "on_chat_model_stream":
        chunk = event.get("data", {}).get("chunk")
        content = getattr(chunk, "content", "")
        if content:
            envelopes.append(envelope_token(ctx.trace_ctx, content))

    elif event_type == "on_chain_start" and event_name == "tool":
        input_state = event.get("data", {}).get("input", {})
        tool_name = "unknown"
        if isinstance(input_state, dict):
            tool_name = input_state.get("current_tool") or tool_name

        active_tool_span_id = new_span(ctx.trace_ctx.span_id, name=f"tool:{tool_name}")
        tool_ctx = replace(ctx.trace_ctx, span_id=active_tool_span_id,
                          parent_span_id=ctx.trace_ctx.span_id)
        envelopes.append(
            envelope_tool_start(tool_ctx, tool_name,
                              f"\n\n🛠️ 正在调用工具：{tool_name}...\n")
        )

    elif event_type == "on_chain_end" and event_name == "tool":
        output_state = event.get("data", {}).get("output", {})
        input_state = event.get("data", {}).get("input", {})
        tool_name = "tool"
        if isinstance(output_state, dict):
            tool_name = output_state.get("current_tool") or tool_name
        if tool_name == "tool" and isinstance(input_state, dict):
            tool_name = input_state.get("current_tool") or tool_name

        summary = summarize_tool_result(tool_name, output_state if isinstance(output_state, dict) else {})
        tool_ctx = replace(
            ctx.trace_ctx,
            span_id=active_tool_span_id or new_span(ctx.trace_ctx.span_id, name=f"tool:{tool_name}"),
            parent_span_id=ctx.trace_ctx.span_id,
        )
        envelopes.append(envelope_tool_result(tool_ctx, tool_name, f"{summary}\n\n"))
        active_tool_span_id = None

    elif event_type == "on_chain_end":
        output_state = event.get("data", {}).get("output", {})
        if isinstance(output_state, dict) and "messages" in output_state:
            final_state = output_state

    return envelopes, active_tool_span_id, final_state
```

- [ ] **Step 3: Fix imports in event_mapper.py**

Remove unused imports. Check the top of the file and ensure only needed imports remain:
```python
from __future__ import annotations
from dataclasses import dataclass, replace
from typing import Any
from domain.event_envelope import (
    envelope_agent_step, envelope_chart, envelope_token,
    envelope_tool_result, envelope_tool_start, envelope_tool_summary,
)
from observability.trace import TraceContext, new_span
```

Remove `json` import if no longer used.

- [ ] **Step 4: Verify**

```bash
cd ai_service && python -c "from api.events.event_mapper import map_langgraph_event_to_envelopes, EventMapContext; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add ai_service/api/events/event_mapper.py
git commit -m "refactor: simplify event_mapper, remove JSON filtering and chart denial logic"
```

---

### Task 8: Simplify chat.py route

**Files:**
- Modify: `ai_service/api/routes/chat.py`

- [ ] **Step 1: Rewrite `stream_generate` — remove control_json_buffer, preamble_buffer**

Replace the event generator (lines 83-244) with:

```python
@router.post("/generate/stream")
async def stream_generate(request: GenerateRequest):
    @timeit
    async def event_generator():
        trace_ctx = ensure_trace_context(request.conversation_id)
        event_ctx = EventMapContext(trace_ctx=trace_ctx, known_tools=_tool_names())
        try:
            if not settings.api_key:
                response = random.choice(MOCK_RESPONSES)
                for char in response:
                    yield to_sse_data(envelope_token(trace_ctx, char))
                    await asyncio.sleep(0.05)
            else:
                checkpointer = get_checkpointer()
                graph = create_agent_graph(checkpointer=checkpointer)
                inputs = {
                    "messages": [HumanMessage(content=request.message)],
                    "conversation_id": trace_ctx.conversation_id,
                    "tool_steps": [],
                    "iteration_count": 0,
                    "current_tool": None,
                    "tool_input": None,
                    "tool_result": None,
                    "last_tool_name": None,
                    "last_tool_query": None,
                    "consecutive_search_count": 0,
                    "last_guard_reason": None,
                    "trace_id": trace_ctx.trace_id,
                    "turn_id": trace_ctx.turn_id,
                    "span_id": trace_ctx.span_id,
                    "parent_span_id": trace_ctx.parent_span_id,
                    "active_agent": trace_ctx.agent_id,
                    "chart_specs": [],
                    "blocks": [],
                    "route": "tool",
                }

                thread_id = trace_ctx.conversation_id
                config: RunnableConfig = {"configurable": {"thread_id": thread_id}, "recursion_limit": 256}

                tool_summary_sent = False
                final_state = None
                saw_tool_event = False
                assistant_text_emitted = False
                active_tool_span_id: str | None = None
                # Pre-send chart data cache: chart_id → sent
                charts_sent: set[str] = set()

                async for event in graph.astream_events(inputs, config=config, version="v2"):
                    mapped, active_tool_span_id, captured_final_state = map_langgraph_event_to_envelopes(
                        event, event_ctx, active_tool_span_id,
                    )
                    if captured_final_state is not None:
                        final_state = captured_final_state

                    for envelope in mapped:
                        envelope_type = envelope.get("type")
                        if envelope_type in {"tool_start", "tool_result"}:
                            saw_tool_event = True
                        if envelope_type == "token":
                            assistant_text_emitted = True
                        yield to_sse_data(envelope)

                    # Inline: send charts from chart_planner_node output
                    if final_state:
                        chart_specs = final_state.get("chart_specs")
                        if isinstance(chart_specs, list):
                            for cs in chart_specs:
                                if isinstance(cs, dict) and cs.get("id") not in charts_sent:
                                    cid = cs["id"] if isinstance(cs["id"], str) else str(cs.get("id", ""))
                                    charts_sent.add(cid)
                                    yield to_sse_data(envelope_chart(trace_ctx, cs))

                # Fallback: extract answer text if no tokens emitted
                if not assistant_text_emitted:
                    fallback_text = extract_last_assistant_text(final_state)
                    if fallback_text:
                        yield to_sse_data(envelope_token(trace_ctx, fallback_text))

                # Emit guard reason
                guard_envelope = emit_guard_reason_envelope(final_state, event_ctx)
                if guard_envelope:
                    yield to_sse_data(guard_envelope)

                # Emit tool summary
                if final_state and not tool_summary_sent:
                    summary_envelope = emit_final_summary_envelope(final_state, event_ctx)
                    if summary_envelope:
                        yield to_sse_data(summary_envelope)
                        tool_summary_sent = True

        except Exception as e:
            yield to_sse_data(envelope_error(trace_ctx, str(e)))

    return EventSourceResponse(event_generator())
```

Key simplifications from old code:
- Removed `collecting_control_json`, `control_json_buffer`, `preamble_buffer`
- Removed `process_stream_token_event()` call
- Removed `current_block_id`, `block_start/block_chunk/block_end` logic
- Removed `_filter_chart_denial()` inline calls
- Removed `pending_chart_spec`, `pending_text_block`, `chart_placeholder` logic
- Charts are now sent inline when `chart_specs` appear in final_state (from chart_planner_node)

- [ ] **Step 2: Update imports in chat.py**

Remove unused imports:
- `envelope_block`, `envelope_block_start`, `envelope_block_chunk`, `envelope_block_end`
- `envelope_chart_placeholder`, `envelope_chart_ready`
- `is_tool_action_json`, `process_stream_token_event`
- `_filter_chart_denial`

Add `envelope_chart` import.

- [ ] **Step 3: Update `_tool_names()` to not include chart/output_text**

```python
def _tool_names() -> set[str]:
    registry = get_tool_registry()
    if not registry:
        return set()
    try:
        return {str(t.get("name", "")).strip().lower() for t in registry.list_tools() if isinstance(t, dict)}
    except Exception:
        return set()
```

(No change needed — `list_tools()` will already exclude removed ChartTool/OutputTextTool)

- [ ] **Step 4: Verify**

```bash
cd ai_service && python -c "from api.routes.chat import router; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add ai_service/api/routes/chat.py
git commit -m "refactor: simplify chat route, remove control JSON and preamble buffers, inline chart emission"
```

---

### Task 9: Simplify event_envelope.py and update tool registration

**Files:**
- Modify: `ai_service/domain/event_envelope.py`
- Modify: `ai_service/main.py`
- Modify: `ai_service/tools/__init__.py` (if needed)

- [ ] **Step 1: Remove deprecated envelope functions from event_envelope.py**

Remove these functions (keep their definitions accessible if referenced elsewhere — check first):
- `envelope_block_start()` (lines 129-137)
- `envelope_block_chunk()` (lines 139-147)
- `envelope_block_end()` (lines 149-157)
- `envelope_block()` (lines 159-167)
- `envelope_chart_placeholder()` (lines 169-177)
- `envelope_chart_ready()` (lines 179-187)

Keep: `envelope_token`, `envelope_tool_start`, `envelope_tool_result`, `envelope_tool_summary`, `envelope_agent_step`, `envelope_chart`, `envelope_error`, `build_envelope`, `to_sse_data`.

- [ ] **Step 2: Update main.py — remove ChartTool and OutputTextTool registration**

```python
# In lifespan startup:
tool_registry = ToolRegistry()
tool_registry.register(SearchTool())
tool_registry.register(TimeTool())
tool_registry.register(BrowserUseTool())
# Removed: ChartTool(), OutputTextTool(), EchoTool()
print(f"ToolRegistry ready: {[t['name'] for t in tool_registry.list_tools()]}")
```

Remove these imports:
```python
from tools.chart.tool import ChartTool
from tools.output_text.tool import OutputTextTool
from tools.echo import EchoTool
```

- [ ] **Step 3: Verify startup**

```bash
cd ai_service && python -c "
from tools import ToolRegistry
from tools.search import SearchTool
from tools.time.tool import TimeTool
from tools.browser import BrowserUseTool
r = ToolRegistry()
r.register(SearchTool())
r.register(TimeTool())
r.register(BrowserUseTool())
print([t['name'] for t in r.list_tools()])
"
```

Expected: `['search', 'time', 'browser']`

- [ ] **Step 4: Commit**

```bash
git add ai_service/domain/event_envelope.py ai_service/main.py
git commit -m "refactor: remove block/chart placeholder events, remove ChartTool/OutputTextTool from registry"
```

---

### Task 10: Update frontend types and SSE event handling

**Files:**
- Modify: `frontend/src/types/chat.ts`
- Modify: `frontend/src/hooks/useChat.ts`

- [ ] **Step 1: Simplify chat.ts types**

Remove `GuardReason` (not needed in new types, keep in existing code as inline), `StreamEvent` (unused). The key note: types stay mostly the same, just ensure `ChartSpecData` and `AgentProcessStep` are still correct.

No changes needed to `chat.ts` — the data types are still valid.

- [ ] **Step 2: Rewrite `useChat.ts` handleParsedEvent**

Replace the current `handleParsedEvent` (lines 189-387) with a simplified version:

```typescript
// Chart data cache: stage 2 sends chart data, stage 3 markers trigger render
let chartDataCache: Map<string, ChartSpecData> = new Map();

const handleParsedEvent = (parsed: StreamPayload) => {
  const payload = parsed.payload ?? {};
  const textChunk = payload.content ?? parsed.content ?? parsed.token ?? '';

  // Chart data received (from phase 2 chart_planner_node)
  if (parsed.type === 'chart' && (parsed as any).chartSpec) {
    const spec = (parsed as any).chartSpec as ChartSpecData;
    const key = String(spec.id ?? '0');
    chartDataCache.set(key, spec);
    return;
  }

  // Legacy chart event
  if ((parsed as any).chartSpec && !parsed.type) {
    const spec = (parsed as any).chartSpec as ChartSpecData;
    chartDataCache.set(String(spec.id ?? '0'), spec);
    return;
  }

  // Token event: stream text, scan for [CHART:n] markers
  if ((parsed.type === 'token' || !parsed.type) && textChunk) {
    // Split text by [CHART:n] markers
    const parts = textChunk.split(/(\[CHART:\d+\])/g);
    for (const part of parts) {
      const chartMatch = part.match(/^\[CHART:(\d+)\]$/);
      if (chartMatch) {
        // Render chart at this position
        const chartId = chartMatch[1];
        const spec = chartDataCache.get(chartId);
        if (spec) {
          chartDatasForAssistant = [...chartDatasForAssistant, spec];
        }
      } else if (part) {
        appendText(part);
      }
    }
    return;
  }

  // Tool events
  if (parsed.type === 'tool_start') {
    const toolName = payload.toolName ?? parsed.toolName ?? 'unknown';
    const input = stringifyInput(payload.input);
    const newStep: ThinkingStep = {
      kind: 'tool', tool: toolName, title: `调用 ${toolName}`,
      summary: input ? `输入：${input}` : '准备执行工具',
      input, status: 'running', startTime: Date.now(),
    };
    if (!thinkingMessageId) {
      thinkingMessageId = addMessage({ role: 'thinking', content: '', toolSteps: [newStep as any] });
    }
    thinkingSteps.push(newStep);
    updateThinkingMessage();
    scrollToBottom();
    return;
  }

  if (parsed.type === 'tool_result') {
    const toolName = payload.toolName ?? parsed.toolName ?? 'unknown';
    const contentText = textChunk || '';
    const now = Date.now();
    thinkingSteps = thinkingSteps.map(s => {
      if (s.tool === toolName && s.status === 'running') {
        return {
          ...s,
          status: (payload.status === 'error' || contentText.includes('失败')) ? 'error' as const : 'completed' as const,
          elapsed_ms: payload.elapsed_ms ?? (now - s.startTime),
          summary: payload.summary || contentText.trim() || s.summary,
          detail: contentText.trim(),
          error: payload.error || (contentText.includes('失败') ? contentText.slice(0, 100) : undefined),
        };
      }
      return s;
    });
    updateThinkingMessage();
    return;
  }

  if (parsed.type === 'tool_summary') {
    const incomingSteps = parsed.payload?.steps ?? parsed.steps;
    if (Array.isArray(incomingSteps) && incomingSteps.length > 0) {
      thinkingSteps = incomingSteps.map((s: any) => ({
        kind: s.kind || 'tool', tool: s.tool || 'unknown',
        title: s.title || `调用 ${s.tool || 'tool'}`,
        summary: s.summary || '', input: s.input || '',
        status: (s.status === 'error' ? 'error' : 'completed') as ThinkingStep['status'],
        elapsed_ms: s.elapsed_ms || 0, error: s.error,
        startTime: Date.now() - (s.elapsed_ms || 0),
      }));
      updateThinkingMessage();
    }
    if (thinkingMessageId) { updateMessage(thinkingMessageId, { content: 'done' }); }
    return;
  }

  if (parsed.type === 'agent_step') {
    const incomingReason = parsed.payload?.reason ?? parsed.reason;
    if (incomingReason) {
      updateMessage(assistantMessageId, { guardReason: incomingReason as any });
    }
    if (thinkingMessageId && thinkingSteps.length > 0) {
      updateMessage(thinkingMessageId, { content: 'done' });
    }
    return;
  }

  if (parsed.type === 'thought' || parsed.type === 'reasoning_delta') {
    // Compatibility: log but don't render separate thought messages
    return;
  }

  if (parsed.type === 'error' || parsed.error) {
    throw new Error(parsed.error || '流式响应异常');
  }

  if (parsed.conversationId) {
    setConversationId(parsed.conversationId);
  }
};
```

- [ ] **Step 3: Add `chartDataCache` as a ref in sendMessage scope**

The `chartDataCache` variable should be declared at the top of `sendMessage` alongside `chartDatasForAssistant`, replacing the old placeholder-based chart accumulation.

- [ ] **Step 4: Remove old block event handling**

Remove handling for `block_start`, `block_chunk`, `block_end`, `block`, `chart_placeholder`, `chart_ready` from `handleParsedEvent` and from the `StreamPayload` type.

- [ ] **Step 5: Update StreamPayload type in useChat.ts**

Remove block and chart placeholder types from the `type` union:
```typescript
interface StreamPayload {
  type?: 'token' | 'tool_start' | 'tool_result' | 'tool_summary' | 'agent_step' | 'chart' | 'error' | 'thought' | 'reasoning_delta';
  // ... rest unchanged
}
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hooks/useChat.ts frontend/src/types/chat.ts
git commit -m "refactor: simplify frontend SSE handling with [CHART:n] marker parsing"
```

---

### Task 11: Update ChatMessage.tsx — remove block parsing

**Files:**
- Modify: `frontend/src/components/ChatMessage.tsx`

- [ ] **Step 1: Simplify tool line parsing**

The `splitToolLines` function currently tries to parse JSON action lines from content. Since JSON Mode eliminates tool JSON leaking into answer text, this function can be simplified or removed. However, for backward compatibility with history messages, keep it but simplify:

No changes strictly needed — old content may still have tool lines. The function is harmless. But remove the `parseActionJsonLine` call which tries to parse `{"action":"tool",...}` from text:

In `ChatMessage.tsx`, remove the `parseActionJsonLine` function (lines 37-60) and its usage in `splitToolLines` (lines 117-121).

- [ ] **Step 2: Ensure `[CHART:n]` markers are stripped from displayed text**

In the answer rendering section, filter out `[CHART:n]` lines from markdown content:

In the assistant answer section (around line 372), add a pre-processing step:

```typescript
// Filter [CHART:n] markers from displayed text (charts are rendered separately)
const displayContent = answer.replace(/\[CHART:\d+\]/g, '').trim();
```

Then use `displayContent` instead of `answer` in the `<ReactMarkdown>` component.

- [ ] **Step 3: Verify frontend builds**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ChatMessage.tsx
git commit -m "refactor: remove JSON action line parsing from ChatMessage, strip [CHART:n] markers"
```

---

### Task 12: Integration verification and final cleanup

**Files:**
- Modify: Various — fix any issues found during testing

- [ ] **Step 1: Run all existing Python tests**

```bash
cd ai_service && python -m pytest tests/ -v --ignore=tests/test_chart_generator.py --ignore=tests/test_chart_planner.py --ignore=tests/test_chart_event_mapper.py 2>&1 | head -100
```

Note: Skip tests for deleted modules (test_chart_generator, test_chart_planner, test_chart_event_mapper).

- [ ] **Step 2: Verify the full import chain**

```bash
cd ai_service && python -c "
from graph.graph import create_agent_graph
from graph.nodes import agent_node, tool_node, chart_planner_node, answer_node
from graph.validators import validate_chart_specs
from api.events.event_mapper import map_langgraph_event_to_envelopes
from api.routes.chat import router
from domain.event_envelope import envelope_token, envelope_chart, to_sse_data
print('All imports OK')
"
```

- [ ] **Step 3: Verify graph compiles and runs a dry-run**

```bash
cd ai_service && python -c "
from graph.graph import create_agent_graph
g = create_agent_graph()
print('Graph nodes:', list(g.nodes.keys()))
print('Graph compiled successfully')
"
```

- [ ] **Step 4: Check TypeScript types**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -50
```

- [ ] **Step 5: Start dev server and smoke test**

```bash
# In terminal 1: start backend
cd ai_service && uvicorn main:app --port 8000 &
# In terminal 2: start frontend
cd frontend && npm run dev &
```

Then send a test message like "搜索今天的科技新闻" and verify:
1. ReAct loop runs with search/browser tools
2. Chart data is generated (if numerical data found)
3. Final answer streams with typewriter effect
4. Charts render at [CHART:n] positions

- [ ] **Step 6: Commit final fixes**

```bash
git add -A
git commit -m "chore: final cleanup and integration fixes for P0 three-phase refactor"
```
