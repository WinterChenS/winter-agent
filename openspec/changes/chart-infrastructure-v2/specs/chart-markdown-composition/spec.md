## MODIFIED Requirements

### Requirement: Markdown color descriptions reference metadata
When composing Markdown reports, the system SHALL reference chart metadata (`ChartResult.metadata` and `ChartResult.summary`) for all color descriptions. The system MUST NOT allow the LLM to infer or guess colors from the chart image.

#### Scenario: Color description from metadata
- **WHEN** generating Markdown for a chart with metadata series `[{"name":"GDP","color":"#2F80ED","color_name":"蓝色"}]`
- **THEN** The Markdown SHALL describe GDP as "GDP（蓝色）", using the color_name from metadata

#### Scenario: No guessed color descriptions
- **WHEN** the chart has no color information in metadata
- **THEN** The Markdown SHALL NOT include any color-based descriptions (e.g., "红色表示...", "蓝色柱状图...")

#### Scenario: Reference summary text
- **WHEN** ChartResult.summary contains "GDP 在 2020-2024 年间保持稳定增长"
- **THEN** The Markdown SHALL include this summary text verbatim, framed as a chart description

### Requirement: Chart code prompt prohibits rcParams font configuration
The chart code generation prompt SHALL instruct the LLM to use `fontproperties=cn_font` for all text elements and SHALL explicitly prohibit `plt.rcParams['font.sans-serif']` configuration.

#### Scenario: Prompt includes FontProperties instruction
- **WHEN** examining the chart code generation prompt
- **THEN** It SHALL contain explicit instruction to use `cn_font` (FontProperties) for all text APIs

#### Scenario: Prompt prohibits rcParams
- **WHEN** examining the chart code generation prompt
- **THEN** It SHALL explicitly forbid setting `plt.rcParams['font.sans-serif']`

### Requirement: Data Analyst prompt requires metadata-based color attribution
The Data Analyst Agent system prompt SHALL require that all color descriptions come from chart metadata, not from visual interpretation of the image.

#### Scenario: Prompt forbids image-based color guessing
- **WHEN** examining the Data Analyst Agent system prompt
- **THEN** It SHALL include a rule stating that colors must be sourced from Chart Metadata, not inferred from the image
