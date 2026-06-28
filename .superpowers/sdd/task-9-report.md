# Task 9: Locate and update Data Analyst Agent system prompt

## Search Results

The Data Analyst Agent's system prompt was found in:

- **`ai_service/db/migrations/002_seed_agents_and_setup.sql`** — The primary location. The Data Analyst agent (`data-analyst` / `data_analyst`) is seeded as Agent 5 in this migration, with a full system prompt string defined in the INSERT statement (lines 188-256).

The prompt was **not** found in:
- `graph/nodes.py` — contains generic "data analyst" references in other prompts (chart planner, report writer), not the Data Analyst agent itself.
- `db/migrations/V003__agent_upgrade.sql` — only references `data_analyst` by name in a backfill UPDATE, does not contain the prompt.

## Changes Made

Three new rules were added to the `## Chart Guidelines (MANDATORY)` section of the Data Analyst system prompt:

1. `颜色描述必须来自 Chart Metadata，不得根据图片推测`
2. `引用图例格式: 系列名（颜色名），颜色信息来自图表元数据`
3. `使用 ChartResult.summary 作为图表描述，不要自行解释图表`

## Commit

`74e75fe` — `feat: update Data Analyst prompt with chart metadata rules`
1 file changed, 3 insertions(+)
