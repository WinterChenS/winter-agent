## ADDED Requirements

### Requirement: Agent can execute Python code in sandbox
The system SHALL provide an `execute_python` tool that runs Python code in an isolated Docker container. The container MUST have network access disabled, CPU limited to 1 core, memory limited to 256MB, and a 30-second default timeout.

#### Scenario: Execute data analysis code
- **WHEN** the agent calls `execute_python` with valid Python code that computes a result
- **THEN** the sandbox returns stdout output within the timeout period

#### Scenario: Timeout handling
- **WHEN** Python code execution exceeds the timeout (default 30s)
- **THEN** the container is forcefully terminated and the tool returns an error with code `TIMEOUT`

#### Scenario: Malicious code isolation
- **WHEN** the agent attempts to execute code that accesses the filesystem outside the sandbox directory
- **THEN** the operation is blocked by Docker container isolation and the process fails safely

### Requirement: Sandbox supports pip packages
The sandbox SHALL pre-install common data analysis packages (`pandas`, `numpy`, `matplotlib`) and allow the agent to `pip install` additional packages during execution.

#### Scenario: Use pre-installed pandas
- **WHEN** the code uses `import pandas` without prior installation
- **THEN** pandas is available and functional

#### Scenario: Install additional package
- **WHEN** the code includes `pip install requests` before using it
- **THEN** the package is installed and usable within the same execution session
