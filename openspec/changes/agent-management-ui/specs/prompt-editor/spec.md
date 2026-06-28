## ADDED Requirements

### Requirement: CodeMirror 6 Prompt Editor
The system SHALL use CodeMirror 6 as the editor for System Prompt in the Agent Drawer.

#### Scenario: Markdown editing
- **WHEN** user edits the system prompt
- **THEN** CodeMirror 6 editor renders with Markdown syntax highlighting

#### Scenario: Word wrap
- **WHEN** system prompt content exceeds the editor width
- **THEN** lines wrap automatically (wordWrap enabled)

#### Scenario: Copy content
- **WHEN** user clicks a copy button near the editor
- **THEN** the full editor content is copied to clipboard as plain text

#### Scenario: Fullscreen toggle
- **WHEN** user clicks the fullscreen button
- **THEN** the editor expands to fill the viewport and a close button appears

#### Scenario: Tab key handling
- **WHEN** user presses Tab in the editor
- **THEN** 2 spaces are inserted (not navigating focus away)
