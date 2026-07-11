## 1. Dependency Alignment

- [ ] 1.1 Confirm RuntimeEvent core exists before replacing or wrapping existing streaming event mapping.
- [ ] 1.2 Confirm event source names and payload fields used by LLM, Tool, and Graph publishers.

## 2. SSE Adapter

- [ ] 2.1 Implement RuntimeEvent to EventEnvelope mapping.
- [ ] 2.2 Map tool runtime events to existing frontend-compatible tool status events.
- [ ] 2.3 Preserve `message.delta`, `message.tool_call`, `message.done`, and `image.uploaded` compatibility.
- [ ] 2.4 Add handling for unknown runtime events using the chosen pass-through or filter strategy.

## 3. Chat Stream Merge

- [ ] 3.1 Update chat stream merge logic to consume RuntimeEvent through the adapter.
- [ ] 3.2 Ensure graph completion closes the event bus and emits final `message.done`.
- [ ] 3.3 Ensure graph errors produce error envelopes and clean up event tasks.

## 4. Frontend Compatibility

- [ ] 4.1 Update frontend event types only if required by the adapter output.
- [ ] 4.2 Add or update frontend/store tests for mapped tool lifecycle events if payload shape changes.

## 5. Validation

- [ ] 5.1 Add mapper tests for tool, graph, unknown, and backward-compatible message events.
- [ ] 5.2 Run targeted chat SSE tests and existing frontend chat store tests.
- [ ] 5.3 Run OpenSpec validation for `agent-runtime-event-sse-adapter`.
