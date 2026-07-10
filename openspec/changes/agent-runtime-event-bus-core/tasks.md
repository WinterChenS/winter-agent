## 1. Event Model

- [x] 1.1 Add a `RuntimeEvent` model with event ID, event type, timestamp, source, trace/span IDs, payload, and metadata.
- [x] 1.2 Add helpers for creating events with default timestamp, generated ID, and empty metadata.
- [x] 1.3 Add unit tests for required fields, default values, and serialization.

## 2. Event Bus Core

- [x] 2.1 Implement in-process Event Bus publish, subscribe, and unsubscribe APIs.
- [x] 2.2 Implement exact topic matching and single-segment wildcard matching.
- [ ] 2.3 Ensure subscriber failures are isolated from publish callers.
- [ ] 2.4 Add tests for exact subscriptions, wildcard subscriptions, no-subscriber publish, unsubscribe, and handler failure.

## 3. Compatibility and Integration Boundary

- [ ] 3.1 Add a compatibility path or adapter for existing `StreamingEventBus` usage.
- [ ] 3.2 Document the no-external-component constraint in code comments or module docs where the bus implementation is introduced.
- [ ] 3.3 Verify existing tests for streaming event behavior still pass.

## 4. Validation

- [ ] 4.1 Run targeted AI service tests for event bus and streaming compatibility.
- [ ] 4.2 Run OpenSpec validation for `agent-runtime-event-bus-core`.
