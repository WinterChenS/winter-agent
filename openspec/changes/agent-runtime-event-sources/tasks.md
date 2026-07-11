## 1. Dependency Alignment

- [ ] 1.1 Confirm `agent-runtime-event-bus-core` is implemented or available before wiring event sources.
- [ ] 1.2 Identify the runtime publisher injection points for LLM, Tool, and Graph execution.

## 2. LLM Events

- [ ] 2.1 Publish `llm.request` before LLM calls in the plan-execute-compose path.
- [ ] 2.2 Publish `llm.response` after successful LLM calls with safe summary metadata.
- [ ] 2.3 Publish `llm.error` when LLM calls fail without changing existing error handling.
- [ ] 2.4 Add tests for successful and failed LLM lifecycle event emission.

## 3. Tool Events

- [ ] 3.1 Publish `tool.invoke` before tool execution.
- [ ] 3.2 Publish `tool.progress` from streaming/progress-capable tools.
- [ ] 3.3 Publish `tool.result` for successful tool execution.
- [ ] 3.4 Publish `tool.error` for failed tool execution.
- [ ] 3.5 Add tests for single tool, failed tool, and parallel tool execution event emission.

## 4. Graph Events

- [ ] 4.1 Publish `graph.enter` and `graph.exit` around planning, execution, and composer nodes.
- [ ] 4.2 Publish `graph.error` when node execution fails.
- [ ] 4.3 Add tests proving graph event failures do not alter graph business results.

## 5. Validation

- [ ] 5.1 Run targeted AI service tests for graph nodes, tool registry, and event sources.
- [ ] 5.2 Run OpenSpec validation for `agent-runtime-event-sources`.
