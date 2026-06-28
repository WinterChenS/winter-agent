## ADDED Requirements

### Requirement: ChatGPT-Style Sidebar
The sidebar SHALL feature a ChatGPT-style layout with a fixed top navigation section and a scrollable Recent Chats section below.

#### Scenario: Top navigation fixed
- **WHEN** the user scrolls the Recent Chats list
- **THEN** the top navigation (AI Studio / New Chat / Agents menu items) remains fixed in place

#### Scenario: Recent Chats scrollable
- **WHEN** there are more chats than fit the available height
- **THEN** only the Recent Chats section scrolls, grouped by Today / Yesterday

#### Scenario: Chat time grouping
- **WHEN** chats are displayed in Recent Chats
- **THEN** they are grouped under "Today" and "Yesterday" headers based on their creation time

### Requirement: Navigation Menu Items
The sidebar navigation SHALL include these menu items: AI Studio (brand), New Chat, Agents, with reserved slots for Tools, Knowledge, MCP, Settings.

#### Scenario: Default menu structure
- **WHEN** the sidebar renders
- **THEN** it displays: AI Studio (brand header), New Chat button, Agents link, future-slot labels (Tools, Knowledge, MCP, Settings) with disabled/locked styling

#### Scenario: Navigate to Agents page
- **WHEN** the user clicks "Agents" in the sidebar
- **THEN** the app navigates to `/agents` route

#### Scenario: Navigate to New Chat
- **WHEN** the user clicks "New Chat" in the sidebar
- **THEN** a new conversation is created and the app navigates to `/`
