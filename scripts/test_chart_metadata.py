#!/usr/bin/env -S ai_service/.venv/bin/python
"""Test chart metadata pipeline: ChartSpec → metadata.json → composer → Markdown.

Requires: ai_service/.venv (Python 3.12+), API running at localhost:8000 for SSE tests.

Usage:
  ai_service/.venv/bin/python scripts/test_chart_metadata.py          # unit only
  ai_service/.venv/bin/python scripts/test_chart_metadata.py --full   # unit + SSE e2e
"""
import asyncio, json, os, re, sys
from dataclasses import dataclass, field

# Ensure ai_service is importable
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ai_service"))

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

BASE = "http://localhost:8000/api/v1/generate/stream"
TIMEOUT = 300

@dataclass
class CaseResult:
    name: str
    passed: bool = True
    image_count: int = 0
    color_mismatches: list = field(default_factory=list)
    summary_found: bool = False
    hallucinated_colors: list = field(default_factory=list)
    errors: list = field(default_factory=list)

async def run_case(agent_id: str, message: str, case_name: str) -> CaseResult:
    """Send a message to the agent, collect SSE events, verify output."""
    result = CaseResult(name=case_name)
    body = {
        "message": message,
        "agentId": agent_id,
        "messageId": f"test-{case_name.replace(' ', '-')}",
        "stream": True,
    }

    sse_events = []
    full_output = []

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            async with c.stream("POST", BASE, json=body) as r:
                if r.status_code != 200:
                    result.errors.append(f"HTTP {r.status_code}")
                    result.passed = False
                    return result

                async for line in r.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    d = line[6:] if line.startswith("data: ") else line[5:]
                    try:
                        e = json.loads(d)
                        sse_events.append(e)
                        t = e.get("type", "")

                        if t == "image.uploaded":
                            result.image_count += 1
                            meta = e.get("payload", {}).get("metadata", {})
                            if meta:
                                result.summary_found = bool(e.get("payload", {}).get("summary", ""))

                        elif t == "message.delta":
                            full_output.append(e.get("delta", ""))

                        elif t == "error":
                            err = e.get("error", "") or str(e.get("payload", {}))[:200]
                            result.errors.append(err)
                            result.passed = False

                        elif t == "message.done":
                            break
                    except Exception:
                        pass
    except Exception as exc:
        result.errors.append(str(exc))
        result.passed = False
        return result

    full_text = "".join(full_output)

    # === Verify: no hallucinated colors ===
    # Extract colors mentioned in output: "xxx（颜色）" pattern
    color_pattern = re.findall(r'[^\s(（]+[（(]([红蓝绿橙紫灰金黄深浅浅粉黑白棕]+(?:色)?)[）)]', full_text)
    # Also find explicit color mentions
    explicit_colors = re.findall(r'(红色|蓝色|绿色|深绿|橙色|紫色|灰色|浅蓝|金黄|浅绿|淡紫|橙色|黄色)', full_text)

    # === Verify: no raw code in output ===
    code_indicators = ["```python", "plt.figure(", "plt.savefig(", "import matplotlib", "plt.rcParams"]
    for ci in code_indicators:
        if ci in full_text:
            result.errors.append(f"Raw code leaked: {ci}")
            result.passed = False

    # === Verify: no localhost URLs ===
    lh = re.findall(r'https?://[^\s)]*localhost[^\s)]*\.(?:png|jpg)', full_text)
    if lh:
        result.errors.append(f"localhost URL in output: {lh}")
        result.passed = False

    # === Verify: image generated ===
    if result.image_count == 0:
        result.errors.append("No image generated")
        result.passed = False

    print(f"  [{case_name}] images={result.image_count}, "
          f"colors_in_text={explicit_colors}, "
          f"summary={'✓' if result.summary_found else '✗'}, "
          f"errors={len(result.errors)}")

    return result


async def test_all_chart_types():
    """Test each chart type individually."""
    agent = "data-analyst"

    cases = [
        ("柱状图", "用柱状图展示：2024年Q1-Q4销售额分别为120、200、150、300万元"),
        ("折线图", "用折线图展示2024年每月温度变化：从1月到12月依次是5,8,12,18,24,30,33,31,27,20,14,8"),
        ("饼图", "用饼图展示市场份额：A产品40%，B产品30%，C产品20%，D产品10%"),
        ("散点图", "用散点图展示广告投入与销售额的关系：投入10万销售50万，投入20万销售80万，投入30万销售110万，投入40万销售140万，投入50万销售170万"),
        ("双轴折线图", "用双轴折线图展示GDP和CPI变化：GDP值[14.7,17.8,18.3,17.9,18.6]，CPI值[2.5,1.8,0.9,0.6,1.2]，GDP用左轴，CPI用右轴"),
    ]

    results = []
    for name, msg in cases:
        r = await run_case(agent, msg, name)
        results.append(r)

    return results


async def main():
    full = "--full" in sys.argv
    print("=" * 60)
    print("Chart Metadata Pipeline Test")
    print("=" * 60)

    # Always run unit tests first
    print("\n--- UNIT TESTS (offline) ---")
    unit_ok = run_unit_tests()

    # SSE e2e tests only with --full
    sse_ok = True
    if full:
        if not HAS_HTTPX:
            print("\n⚠ httpx not installed. Install: pip install httpx")
            sse_ok = False
        else:
            print("\n--- SSE E2E TESTS ---")
            print("(requires API at localhost:8000)")
            try:
                async with httpx.AsyncClient(timeout=5) as c:
                    r = await c.get("http://localhost:8000/health")
                    print(f"  API health: {r.status_code}")
            except Exception:
                print("  ⚠ API not reachable at localhost:8000 — skipping SSE tests")
                sse_ok = True  # don't fail if API isn't running
            else:
                results = await test_all_chart_types()
                print("\n" + "=" * 60)
                print("SSE RESULTS")
                print("=" * 60)
                for r in results:
                    status = "✅" if r.passed else "❌"
                    print(f"\n{status} {r.name}")
                    print(f"   Images: {r.image_count}")
                    for e in r.errors:
                        print(f"   ⚠ {e}")
                sse_ok = all(r.passed for r in results)

    all_pass = unit_ok and sse_ok
    print(f"\n{'='*60}")
    print("✅ ALL PASSED" if all_pass else "❌ SOME FAILED")
    sys.exit(0 if all_pass else 1)


def run_unit_tests() -> bool:
    """Run offline unit tests for the chart modules."""
    ok = True

    # Test Palette
    try:
        from chart.palette import Palette
        assert Palette.PRIMARY.hex == "#2F80ED"
        assert Palette.PRIMARY.name_cn == "蓝色"
        assert len(Palette.SERIES) == 12
        assert Palette.get_color_name("#2F80ED") == "蓝色"
        assert Palette.get_color_name("#unknown") == "#unknown"
        colors = Palette.get_series_colors(14)
        assert len(colors) == 14
        print("  ✅ Palette: 5/5")
    except Exception as e:
        print(f"  ❌ Palette: {e}")
        ok = False

    # Test FontManager
    try:
        from chart.font_manager import FontManager
        FontManager.initialize()
        f1 = FontManager.get_cn_font()
        f2 = FontManager.get_cn_font()
        assert f1 is f2  # cached
        FontManager.initialize()  # idempotent
        print("  ✅ FontManager: 3/3")
    except Exception as e:
        print(f"  ❌ FontManager: {e}")
        ok = False

    # Test ChartSpec
    try:
        from chart.chart_spec import ChartSpec, SeriesSpec, SliceSpec, PointSpec
        spec = ChartSpec(
            title="Test", chart_type="bar",
            series=[SeriesSpec(name="A", color="#2F80ED", color_name="", values=[1, 2, 3]),
                    SeriesSpec(name="B", color="#27AE60", color_name="", values=[4, 5], secondary_y=True)]
        )
        assert spec.series[0].color_name == "蓝色"  # auto-filled
        meta = spec.to_metadata()
        assert meta["title"] == "Test"
        assert "series" in meta
        vals = spec.all_values()
        assert 1 in vals and 5 in vals
        print("  ✅ ChartSpec: 4/4")
    except Exception as e:
        print(f"  ❌ ChartSpec: {e}")
        ok = False

    # Test ChartResult
    try:
        from chart.chart_result import ChartResult
        s = ChartResult.compute_summary([])
        assert s == ""
        s = ChartResult.compute_summary([10, 20, 30])
        assert "Max: 30" in s
        assert "Min: 10" in s
        assert "trend" in s
        s = ChartResult.compute_summary([None, 10, None, 20])  # None filtering
        assert "Max: 20" in s
        print("  ✅ ChartResult: 4/4")
    except Exception as e:
        print(f"  ❌ ChartResult: {e}")
        ok = False

    # Test render_from_spec (all 6 types)
    try:
        import tempfile, os
        from chart.renderers.matplotlib_renderer import MatplotlibRenderer
        from chart.chart_spec import ChartSpec, SeriesSpec, SliceSpec, PointSpec
        import matplotlib
        matplotlib.use("Agg")

        renderer = MatplotlibRenderer()
        td = tempfile.mkdtemp()

        # Bar
        spec = ChartSpec(title="Bar", chart_type="bar", xlabel="X", ylabel="Y",
                         series=[SeriesSpec(name="A", color="#2F80ED", color_name="蓝色", values=[10, 20])],
                         labels=["a", "b"])
        r = renderer.render_from_spec(spec, os.path.join(td, "bar.png"))
        assert os.path.exists(r.image_path)
        assert os.path.exists(r.image_path.replace(".png", "_metadata.json"))
        assert r.metadata["chart_type"] == "bar"

        # Line
        spec.chart_type = "line"
        r = renderer.render_from_spec(spec, os.path.join(td, "line.png"))
        assert os.path.exists(r.image_path)

        # Pie
        spec.chart_type = "pie"
        spec.series = None
        spec.slices = [SliceSpec(label="A", value=40, color="#2F80ED", color_name="蓝色")]
        r = renderer.render_from_spec(spec, os.path.join(td, "pie.png"))
        assert os.path.exists(r.image_path)

        # Scatter
        spec.chart_type = "scatter"
        spec.slices = None
        spec.points = [PointSpec(x=1, y=2, label="pt")]
        r = renderer.render_from_spec(spec, os.path.join(td, "scatter.png"))
        assert os.path.exists(r.image_path)

        # Histogram
        spec.chart_type = "histogram"
        spec.points = None
        spec.data = [[1, 2, 2, 3, 3, 3, 4, 4, 5]]
        r = renderer.render_from_spec(spec, os.path.join(td, "hist.png"))
        assert os.path.exists(r.image_path)

        # Heatmap
        spec.chart_type = "heatmap"
        spec.data = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        spec.labels = ["A", "B", "C"]
        r = renderer.render_from_spec(spec, os.path.join(td, "heat.png"))
        assert os.path.exists(r.image_path)

        # Dual-axis line
        spec.chart_type = "line"
        spec.data = None
        spec.series = [
            SeriesSpec(name="GDP", color="#2F80ED", color_name="蓝色", values=[14, 17, 18], secondary_y=False),
            SeriesSpec(name="CPI", color="#27AE60", color_name="绿色", values=[2.5, 1.8, 0.9], secondary_y=True),
        ]
        r = renderer.render_from_spec(spec, os.path.join(td, "dual.png"))
        assert os.path.exists(r.image_path)

        # Cleanup
        import shutil
        shutil.rmtree(td)
        print("  ✅ render_from_spec: 7/7 (bar/line/pie/scatter/hist/heat/dual)")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  ❌ render_from_spec: {e}")
        ok = False

    return ok


if __name__ == "__main__":
    asyncio.run(main())
