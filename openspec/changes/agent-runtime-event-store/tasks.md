## 1. Dependency Alignment

- [ ] 1.1 Confirm RuntimeEvent core exists before implementing Event Store.
- [ ] 1.2 Confirm event source payload shape and filtering needs before choosing stored fields.

## 2. Storage Model

- [ ] 2.1 Add PostgreSQL table initialization or migration for runtime events.
- [ ] 2.2 Store event ID, event type, source, trace ID, span ID, conversation ID, timestamp, payload, and metadata.
- [ ] 2.3 Add indexes for trace ID, conversation ID, event type, and timestamp.

## 3. Event Store Subscriber

- [ ] 3.1 Implement Event Store as an Event Bus subscriber.
- [ ] 3.2 Add configuration to enable or disable event persistence.
- [ ] 3.3 Ensure write failures are logged and do not affect Agent runtime execution.
- [ ] 3.4 Add tests for enabled, disabled, and write-failure scenarios.

## 4. Query API

- [ ] 4.1 Implement repository/service query by trace ID.
- [ ] 4.2 Implement repository/service query by conversation ID, event type, and time range.
- [ ] 4.3 Add a lightweight FastAPI route or internal service interface for querying event chains.
- [ ] 4.4 Add tests for query ordering and filter behavior.

## 5. Validation

- [ ] 5.1 Run targeted AI service database tests.
- [ ] 5.2 Verify chat streaming continues when Event Store is disabled or database writes fail.
- [ ] 5.3 Run OpenSpec validation for `agent-runtime-event-store`.
