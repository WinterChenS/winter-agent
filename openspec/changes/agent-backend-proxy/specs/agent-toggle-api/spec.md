## ADDED Requirements

### Requirement: Enable Agent Endpoint
Python AI Service SHALL provide an endpoint to enable an agent definition.

#### Scenario: Enable a disabled agent
- **WHEN** `POST /api/v1/agents/{id}/enable` is called
- **THEN** the agent's `enabled` field is set to `true` and the updated agent is returned

#### Scenario: Enable an already enabled agent
- **WHEN** `POST /api/v1/agents/{id}/enable` is called on an already enabled agent
- **THEN** the agent is returned unchanged with `enabled: true`

#### Scenario: Enable non-existent agent
- **WHEN** `POST /api/v1/agents/{id}/enable` is called with a non-existent id
- **THEN** a 404 error response is returned

### Requirement: Disable Agent Endpoint
Python AI Service SHALL provide an endpoint to disable an agent definition.

#### Scenario: Disable an enabled agent
- **WHEN** `POST /api/v1/agents/{id}/disable` is called
- **THEN** the agent's `enabled` field is set to `false` and the updated agent is returned

#### Scenario: Disable an already disabled agent
- **WHEN** `POST /api/v1/agents/{id}/disable` is called on an already disabled agent
- **THEN** the agent is returned unchanged with `enabled: false`

#### Scenario: Disable non-existent agent
- **WHEN** `POST /api/v1/agents/{id}/disable` is called with a non-existent id
- **THEN** a 404 error response is returned

### Requirement: SpringBoot Toggle Proxy
Spring Boot SHALL proxy enable/disable requests to the Python AI Service.

#### Scenario: Proxy enable request
- **WHEN** `POST /api/agents/{id}/enable` is called
- **THEN** Spring Boot forwards to Python `POST /api/v1/agents/{id}/enable` and returns the result

#### Scenario: Proxy disable request
- **WHEN** `POST /api/agents/{id}/disable` is called
- **THEN** Spring Boot forwards to Python `POST /api/v1/agents/{id}/disable` and returns the result
