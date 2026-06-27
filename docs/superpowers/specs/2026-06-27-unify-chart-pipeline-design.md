---
comet_change: unify-chart-pipeline
role: technical-design
canonical_spec: openspec
---

# Unify Chart Pipeline — Technical Design

## 1. Architecture

```
用户 "画折线图"
    │
    ▼
Agent (execute_python tool)
    │
    ▼
LLM writes matplotlib code
    │
    ▼
ChartService.render(code)
    ├── ChartTheme.initialize()
    ├── exec(code) → generates PNG
    ├── MinioStorage.upload(path) → URL
    └── cleanup local file
    │
    ▼
Tool Result: {"type": "image", "url": "...", "width": 1600, "height": 900, "title": "..."}
    │
    ▼
SSE: image.uploaded {filename, url}
    │
    ▼
Frontend: <img src={url} />
```

## 2. Module Design

### 2.1 chart/chart_theme.py
```python
class ChartTheme:
    @staticmethod
    def initialize():
        plt.rcParams["font.sans-serif"] = ["PingFang SC", "Microsoft YaHei", "SimHei", "Noto Sans CJK SC"]
        plt.rcParams["axes.unicode_minus"] = False
        plt.rcParams["figure.dpi"] = 200
        plt.rcParams["figure.figsize"] = (16, 9)
        plt.rcParams["figure.facecolor"] = "white"
        plt.rcParams["axes.grid"] = True
        plt.rcParams["grid.alpha"] = 0.3
        plt.rcParams["font.size"] = 12
        plt.rcParams["axes.titlesize"] = 16
        plt.rcParams["axes.titleweight"] = "bold"
```

### 2.2 chart/chart_renderer.py
```python
from abc import ABC, abstractmethod

class AbstractChartRenderer(ABC):
    @abstractmethod
    def render(self, code: str, output_path: str) -> str:
        """Execute code, generate chart, return output_path."""
```

### 2.3 chart/renderers/matplotlib_renderer.py
```python
class MatplotlibRenderer(AbstractChartRenderer):
    def render(self, code: str, output_path: str) -> str:
        ChartTheme.initialize()
        exec(code, {"__output_path__": output_path})
        return output_path
```

### 2.4 chart/minio_storage.py
```python
class MinioStorage:
    def upload(self, filepath: str) -> str:
        """Upload file to MinIO agent-images bucket, return presigned URL."""
        from services.minio_client import upload_image
        url = upload_image(filepath)
        os.remove(filepath)
        return url
```

### 2.5 chart/chart_service.py
```python
class ChartService:
    def __init__(self):
        self.renderer = MatplotlibRenderer()
        self.storage = MinioStorage()

    def render(self, code: str) -> dict:
        path = f"/tmp/chart_{uuid4().hex}.png"
        self.renderer.render(code, path)
        url = self.storage.upload(path)
        return {"type": "image", "url": url, "width": 1600, "height": 900}
```

## 3. Code Deletions

| File | Delete |
|------|--------|
| `collaboration.py` | `_extract_charts()` method, chart_keywords check in `execute()` |
| `multi_agent_graph.py` | `chart_specs` from collaboration return |
| `chat.py` | chart_specs extraction + chart SSE event emission |
| `event_envelope.py` | `message_id` param from `envelope_chart` |
| `nodes.py` | `_build_chart_section()`, `[CHART:n]` references in prompt |
| `chatApi.ts` | `chart` SSE event case |
| `chatStore.ts` | `addChart`, `charts` field |
| `types/chat.ts` | `charts` field |
| `MessageBubble.tsx` | `ReactECharts`, `chartSpecToOption`, `[CHART:n]` parsing |
| `package.json` | `echarts`, `echarts-for-react` |

## 4. Frontend Simplification

MessageBubble chart rendering → single `<img>` with click preview:
```tsx
{message.images && Object.entries(message.images).map(([filename, url]) => (
  <img key={filename} src={url} alt={filename}
       className="max-w-full rounded cursor-pointer hover:opacity-90"
       onClick={() => window.open(url, '_blank')} />
))}
```

## 5. Agent Prompt

All agents' system_prompt updated to include:
```
## Chart Rules (MANDATORY)
- When asked for charts/visualizations/data analysis: ONLY use execute_python
- NEVER output ECharts option JSON, JavaScript, or HTML
- matplotlib is pre-configured with Chinese fonts and enterprise theme
- Just write: plt.savefig("chart.png")
- The system handles upload and display automatically
```
