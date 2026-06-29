## ADDED Requirements

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
