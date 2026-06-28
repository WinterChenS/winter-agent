## ADDED Requirements

### Requirement: Clone Agent Endpoint
Python AI Service SHALL provide an endpoint to clone an existing agent definition.

#### Scenario: Clone an existing agent
- **WHEN** `POST /api/v1/agents/{id}/clone` is called
- **THEN** a new agent is created with all fields copied from the source agent, a new unique `id`, and `display_name` set to `"{original_display_name} (Copy)"`

#### Scenario: Clone with name conflict
- **WHEN** cloning would result in a duplicate `name`
- **THEN** the system appends a suffix to make the name unique (e.g., `"{name}-copy"`)

#### Scenario: Clone non-existent agent
- **WHEN** `POST /api/v1/agents/{id}/clone` is called with a non-existent id
- **THEN** a 404 error response is returned

#### Scenario: Cloned agent inherits tools and config
- **WHEN** an agent with specific tools, model_config, and collaboration_strategy is cloned
- **THEN** the cloned agent has identical tools, model_config, and collaboration_strategy

### Requirement: SpringBoot Clone Proxy
Spring Boot SHALL proxy clone requests to the Python AI Service.

#### Scenario: Proxy clone request
- **WHEN** `POST /api/agents/{id}/clone` is called
- **THEN** Spring Boot forwards to Python `POST /api/v1/agents/{id}/clone` and returns the result
