## ADDED Requirements

### Requirement: ChartSpec provides type-specific chart definition
The system SHALL provide a `ChartSpec` dataclass that serves as the Single Source of Truth for chart rendering and metadata. ChartSpec SHALL support type-specific fields for different chart types.

#### Scenario: Bar chart with series
- **WHEN** constructing a ChartSpec with `chart_type="bar"`, `title="Sales Report"`, and `series=[SeriesSpec(name="Product A", color="#2F80ED", color_name="蓝色", values=[100, 200, 150])]`
- **THEN** the ChartSpec SHALL store all fields for rendering and metadata extraction

#### Scenario: Pie chart with slices
- **WHEN** constructing a ChartSpec with `chart_type="pie"`, `slices=[SliceSpec(label="A", value=30, color="#2F80ED", color_name="蓝色")]`
- **THEN** the ChartSpec SHALL store pie-specific slice data

#### Scenario: Scatter chart with points
- **WHEN** constructing a ChartSpec with `chart_type="scatter"`, `points=[PointSpec(x=1.0, y=2.5, label="sample")]`
- **THEN** the ChartSpec SHALL store scatter-specific point data

### Requirement: SeriesSpec links data to color identity
Each series in a chart SHALL be described by a `SeriesSpec` containing `name`, `color` (hex), `color_name` (Chinese), and `values` (list of floats).

#### Scenario: SeriesSpec with all fields populated
- **WHEN** creating `SeriesSpec(name="GDP", color="#2F80ED", color_name="蓝色", values=[120, 150, 180])`
- **THEN** all fields SHALL be accessible for rendering and metadata output

### Requirement: Palette color assignment fills color_name automatically
When constructing ChartSpec with Palette constants, the `color_name` field SHALL be automatically derived from the Palette's color-to-name mapping.

#### Scenario: Series uses Palette.SUCCESS
- **WHEN** `SeriesSpec(name="Revenue", color=Palette.SUCCESS.hex, values=[...])` is created
- **THEN** `color_name` SHALL be populated as `Palette.SUCCESS.name_cn` (e.g., "深绿") if not explicitly provided
