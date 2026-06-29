# chart-font-management Specification

## Purpose
TBD - created by archiving change chart-infrastructure-v2. Update Purpose after archive.
## Requirements
### Requirement: FontManager provides cached FontProperties
FontManager SHALL discover and cache a Chinese-capable FontProperties instance at initialization time. Subsequent calls to `get_cn_font()` MUST return the cached instance without re-scanning the filesystem.

#### Scenario: First initialization caches font
- **WHEN** `FontManager.initialize()` is called for the first time
- **THEN** FontManager SHALL scan the system for Chinese-capable fonts, cache the FontProperties, and log the selected font name

#### Scenario: Subsequent calls use cache
- **WHEN** `FontManager.get_cn_font()` is called after initialization
- **THEN** FontManager MUST return the cached FontProperties without any filesystem scan

#### Scenario: Re-initialization uses cache
- **WHEN** `FontManager.initialize()` is called multiple times
- **THEN** Only the first call SHALL perform a font scan; subsequent calls MUST return immediately

### Requirement: FontProperties explicitly passed to all matplotlib text APIs
All matplotlib Artist text elements SHALL receive `fontproperties=<cn_font>` explicitly. The system MUST NOT rely on `plt.rcParams` for Chinese font rendering.

#### Scenario: Title uses FontProperties
- **WHEN** chart code calls `ax.set_title("中文标题", fontproperties=cn_font)`
- **THEN** The title SHALL render Chinese characters correctly without tofu boxes

#### Scenario: Legend uses FontProperties
- **WHEN** chart code calls `ax.legend(prop=cn_font)`
- **THEN** Legend text SHALL render Chinese characters correctly

#### Scenario: Table cells use FontProperties
- **WHEN** chart code creates a table via `ax.table()` and sets `cell.get_text().set_fontproperties(cn_font)` for every cell
- **THEN** All table cell text SHALL render Chinese characters correctly

#### Scenario: Annotation uses FontProperties
- **WHEN** chart code calls `ax.annotate("中文注释", ..., fontproperties=cn_font)`
- **THEN** Annotation text SHALL render Chinese characters correctly

#### Scenario: Tick labels use FontProperties
- **WHEN** chart code applies `plt.setp(ax.get_xticklabels(), fontproperties=cn_font)`
- **THEN** Tick labels SHALL render Chinese characters correctly

### Requirement: Font discovery covers platform-specific fonts
FontManager SHALL search a prioritized platform-specific font list and return the first available font.

#### Scenario: macOS font discovery
- **WHEN** running on macOS
- **THEN** FontManager SHALL search in order: PingFang SC, Heiti SC, STHeiti, Arial Unicode MS

#### Scenario: Fallback when no Chinese font found
- **WHEN** no Chinese-capable font is found on the system
- **THEN** FontManager SHALL return a default FontProperties, log a WARNING, and allow chart generation to continue with potentially missing Chinese glyphs

