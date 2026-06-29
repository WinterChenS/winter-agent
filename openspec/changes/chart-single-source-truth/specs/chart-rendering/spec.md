## MODIFIED Requirements

### Requirement: ChartRenderer.render() returns ChartResult
`ChartRenderer.render(code, output_path)` SHALL return a `ChartResult` object instead of a plain string. The ChartResult SHALL contain the image path, structured metadata extracted from the rendered figure, and a summary.

#### Scenario: render returns ChartResult
- **WHEN** `renderer.render(code, output_path)` completes successfully
- **THEN** The return value SHALL be a `ChartResult` with `image_path` pointing to the generated PNG

#### Scenario: metadata extracted from figure
- **WHEN** user code sets `ax.set_title("GDP Growth")` and `ax.set_xlabel("Year")`
- **THEN** `ChartResult.metadata.title` SHALL be "GDP Growth" and `ChartResult.metadata.xlabel` SHALL be "Year"

#### Scenario: Legacy code compatibility
- **WHEN** existing code accesses `ChartResult.image_path`
- **THEN** It SHALL return the same string value as the old `render()` return value (the PNG file path)

### Requirement: ChartRenderer.render_from_spec renders from ChartSpec
`ChartRenderer.render_from_spec(spec: ChartSpec, output_path)` SHALL render a chart from a ChartSpec object and return a `ChartResult` with metadata directly derived from the ChartSpec.

#### Scenario: Bar chart from ChartSpec
- **WHEN** `render_from_spec(spec, output_path)` is called with a bar ChartSpec containing 2 series
- **THEN** A bar chart SHALL be rendered with correctly colored bars, legend, title, and axis labels

#### Scenario: Metadata from ChartSpec
- **WHEN** `render_from_spec(spec, output_path)` returns a ChartResult
- **THEN** `ChartResult.metadata.title` SHALL equal `spec.title` and `ChartResult.metadata.series` SHALL equal `spec.series`

#### Scenario: Pie chart from ChartSpec
- **WHEN** `render_from_spec(spec, output_path)` is called with a pie ChartSpec containing slices
- **THEN** A pie chart SHALL be rendered with correctly colored and labeled slices

### Requirement: All matplotlib charts support Chinese text
Every matplotlib chart type SHALL render Chinese text correctly across all text elements, not only those covered by rcParams.

#### Scenario: Box plot Chinese labels
- **WHEN** a box plot is generated with Chinese title and labels
- **THEN** All text elements SHALL display Chinese characters without tofu boxes

#### Scenario: Histogram Chinese labels
- **WHEN** a histogram is generated with Chinese title and axis labels
- **THEN** All text elements SHALL display Chinese characters correctly

#### Scenario: Heatmap Chinese annotations
- **WHEN** a heatmap is generated with Chinese annotations via `ax.text()`
- **THEN** All annotation text SHALL display Chinese characters correctly
