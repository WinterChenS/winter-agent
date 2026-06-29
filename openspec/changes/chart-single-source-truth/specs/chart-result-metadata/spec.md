## MODIFIED Requirements

### Requirement: ChartResult contains image path, metadata, and summary
Every chart generation SHALL return a `ChartResult` object with `image_path`, `metadata`, and `summary` fields.

#### Scenario: ChartResult created after chart generation
- **WHEN** a chart is successfully rendered
- **THEN** The returned ChartResult SHALL contain a non-empty `image_path`, a `metadata` object, and a `summary` string

### Requirement: ChartMetadata includes title, chart type, and series info
The metadata SHALL contain `title`, `chart_type`, and `series` fields, with optional `xlabel` and `ylabel`.

#### Scenario: Bar chart metadata
- **WHEN** a bar chart titled "Sales Report" is generated with two series "Product A" and "Product B"
- **THEN** `metadata.title` SHALL be "Sales Report", `metadata.chart_type` SHALL be "bar", and `metadata.series` SHALL have 2 entries each with `name`, `color` (hex), and `color_name` (Chinese)

### Requirement: metadata.json output alongside PNG
Every chart PNG SHALL be accompanied by a `metadata.json` file in the same directory with the same base filename.

#### Scenario: Metadata JSON output
- **WHEN** chart is saved as `/tmp/chart_abc12345.png`
- **THEN** a file `/tmp/chart_abc12345_metadata.json` SHALL exist and contain valid JSON with title, chart_type, series, xlabel, ylabel fields

#### Scenario: Metadata JSON is valid JSON
- **WHEN** reading the metadata.json file
- **THEN** The file SHALL parse as valid JSON with all required fields present

### Requirement: Series info links color to name
Each series entry in metadata SHALL contain both the hex color and its Chinese color name from the Palette.

#### Scenario: Series color_name matches Palette
- **WHEN** a series uses the PRIMARY color `#2F80ED`
- **THEN** The series SHALL have `color="#2F80ED"` and `color_name="蓝色"`

### Requirement: Summary auto-computed from chart data
`ChartResult.summary` SHALL be automatically computed by ChartRenderer from the ChartSpec data. It SHALL include at minimum the maximum value, minimum value, and average of all numeric data.

#### Scenario: Summary contains statistics for bar chart
- **WHEN** a bar chart has series with values [100, 200, 150, 300, 250]
- **THEN** `ChartResult.summary` SHALL include max=300, min=100, avg=200

#### Scenario: Summary includes trend for time series
- **WHEN** a line chart has series values [100, 120, 150, 180, 200]
- **THEN** `ChartResult.summary` SHALL indicate an upward trend

#### Scenario: Summary is empty when no numeric data
- **WHEN** a chart has no numeric series/slices/points data to compute statistics from
- **THEN** `ChartResult.summary` SHALL be an empty string
