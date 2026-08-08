# Stage211 C9/15万大赢家日K量价上下文实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把Stage209的71张大赢家单图升级为“15分钟K线 + 日K线 + 日成交量”，日线固定覆盖开仓前60根到最终平仓后5根，同时保持样本、收益率排序和分钟口径不变。

**Architecture:** 在现有只读脚本中增加逐月合约日线加载、时区归一化和按根数截窗三个纯边界，并把绘图拆成可测试的三轴figure构建器；主入口仍只编排本地冻结输入。日线来自vn.py本地数据库，逐合约规范化帧以SHA256落盘，缺失只显示占位，不回退主连、不下载、不补值。

**Tech Stack:** Python 3.11 (`.py311/bin/python`)、pandas、NumPy、Matplotlib Agg、vn.py database API、pytest、标准库 hashlib/json/pathlib。

## Global Constraints

- 正式版本固定为 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。
- winner manifest固定71笔，`aggregate_r >= 2.0`，收益率排序和排名不得改变。
- 15分钟窗口固定开仓日前5个正式交易日、开仓日、后5个正式交易日。
- 日K窗口固定逐月合约开仓前60根、开仓日至最终平仓日、最终平仓后5根。
- 上层只画15分钟K，不画15分钟成交量；中层画日K；下层只画日成交量。
- 日线严格使用winner的逐月 `vt_symbol`；不得替换为主连、指数或产品连续合约。
- 不下载、不插值、不补空K、不填充成交量；缺失或不足必须审计并保留图片。
- 不修改正式配置、回测参数、AI池、CTP、邮件、launchd、其他研究线或根目录总账。
- `send_order_api_called_count=0`、`cancel_order_api_called_count=0`、`ctp_connected=false`。
- 本阶段不是新回测，不触发回测结果独立agent review要求。

---

## 文件结构

- Modify: `research/lines/futures_trend_stage819_intraday_rules/tools/stage208_c9_2r_winner_15m_atlas.py`
  - 新职责：加载逐月日线、截取日线窗口、构建三轴图、写日线来源manifest和覆盖审计。
- Modify: `research/lines/futures_trend_stage819_intraday_rules/tests/test_stage208_c9_2r_winner_15m_atlas.py`
  - 新职责：验证日线时区、窗口、partial语义、三轴布局、日成交量颜色和端到端产物。
- Modify at runtime: `research/lines/futures_trend_stage819_intraday_rules/outputs/stage208_c9_2r_winner_15m_atlas/`
  - 覆盖71张单图和18页Atlas；更新CSV/JSON/Markdown/hash并新增 `daily_source_manifest.csv`。
- Create after verified run: `research/lines/futures_trend_stage819_intraday_rules/stages/20260808_1822_stage212_c9_2r_winner_daily_context_result.md`
  - 中文记录真实完成时间、日线覆盖、视觉验证、测试、输入身份和反思。

### Task 1: 日线加载、时区归一化和60/5窗口

**Files:**
- Modify: `research/lines/futures_trend_stage819_intraday_rules/tools/stage208_c9_2r_winner_15m_atlas.py:1-360`
- Test: `research/lines/futures_trend_stage819_intraday_rules/tests/test_stage208_c9_2r_winner_15m_atlas.py`

**Interfaces:**
- Produces: `daily_bars_to_frame(vt_symbol: str, bars: list[object]) -> pd.DataFrame`
- Produces: `load_daily_context(winners: pd.DataFrame, database: object | None = None) -> dict[str, pd.DataFrame]`
- Produces: `select_daily_window(event: pd.Series, daily_bars: pd.DataFrame, before: int = 60, after: int = 5) -> tuple[pd.DataFrame, dict[str, object]]`
- Produces: `build_daily_source_manifest(daily_context: dict[str, pd.DataFrame]) -> pd.DataFrame`

- [ ] **Step 1: 写日线时区归一化失败测试**

在测试文件中加入：

```python
from types import SimpleNamespace


def test_daily_bars_to_frame_normalizes_timezone_and_ohlcv() -> None:
    bars = [
        SimpleNamespace(
            datetime=pd.Timestamp("2021-01-04 00:00:00+08:00"),
            open_price=100.0,
            high_price=105.0,
            low_price=99.0,
            close_price=104.0,
            volume=12.0,
            open_interest=88.0,
        )
    ]
    result = stage208.daily_bars_to_frame("rb2105.SHFE", bars)
    assert result["trade_date"].tolist() == [pd.Timestamp("2021-01-04")]
    assert result.iloc[0][["open", "high", "low", "close", "volume", "close_oi"]].tolist() == [100.0, 105.0, 99.0, 104.0, 12.0, 88.0]
```

- [ ] **Step 2: 运行测试确认RED**

Run:

```bash
.py311/bin/python -m pytest research/lines/futures_trend_stage819_intraday_rules/tests/test_stage208_c9_2r_winner_15m_atlas.py::test_daily_bars_to_frame_normalizes_timezone_and_ohlcv -v
```

Expected: FAIL，`daily_bars_to_frame` 未定义。

- [ ] **Step 3: 实现最小时区归一化**

实现要求：

```python
def daily_bars_to_frame(vt_symbol: str, bars: list[object]) -> pd.DataFrame:
    rows = []
    for bar in bars:
        dt = pd.Timestamp(bar.datetime)
        if dt.tzinfo is not None:
            dt = dt.tz_convert("Asia/Shanghai").tz_localize(None)
        rows.append({
            "vt_symbol": vt_symbol,
            "trade_date": dt.normalize(),
            "open": float(bar.open_price),
            "high": float(bar.high_price),
            "low": float(bar.low_price),
            "close": float(bar.close_price),
            "volume": float(bar.volume or 0.0),
            "close_oi": float(bar.open_interest or 0.0),
        })
    return pd.DataFrame(rows).drop_duplicates(["vt_symbol", "trade_date"], keep="last").sort_values("trade_date").reset_index(drop=True)
```

空输入返回带固定列的空DataFrame。

- [ ] **Step 4: 写60日前置、完整持有段和5日后置失败测试**

```python
def test_select_daily_window_keeps_60_before_holding_and_5_after() -> None:
    dates = pd.bdate_range("2020-01-01", periods=90)
    daily = pd.DataFrame({
        "vt_symbol": ["rb2105.SHFE"] * 90,
        "trade_date": dates,
        "open": range(90), "high": range(1, 91), "low": range(90),
        "close": range(1, 91), "volume": range(100, 190), "close_oi": range(200, 290),
    })
    event = pd.Series({"entry_date": dates[60], "exit_date": dates[70]})
    window, coverage = stage208.select_daily_window(event, daily)
    assert window["trade_date"].tolist() == list(dates[:76])
    assert coverage == {
        "daily_bar_count": 76,
        "daily_before_count": 60,
        "daily_holding_count": 11,
        "daily_after_count": 5,
        "daily_coverage_state": "complete",
    }
```

- [ ] **Step 5: 写不足窗口不补值测试**

```python
def test_select_daily_window_reports_partial_without_filling() -> None:
    dates = pd.bdate_range("2021-01-01", periods=20)
    daily = pd.DataFrame({"trade_date": dates})
    event = pd.Series({"entry_date": dates[10], "exit_date": dates[17]})
    window, coverage = stage208.select_daily_window(event, daily)
    assert len(window) == 20
    assert coverage["daily_before_count"] == 10
    assert coverage["daily_after_count"] == 2
    assert coverage["daily_coverage_state"] == "partial"
```

- [ ] **Step 6: 实现窗口、数据库加载与来源manifest**

`load_daily_context()` 必须：

- 延迟导入 `get_database`、`Exchange`、`Interval`，测试可注入fake database。
- 每个唯一 `vt_symbol` 只查一次，查询区间固定 `2010-01-01 -> 2026-07-15`。
- 调用 `daily_bars_to_frame()`，不使用连续合约fallback。
- 返回 `{vt_symbol: normalized_frame}`。

`select_daily_window()` 必须按帧内真实日K根数截取；开仓日前取最后60根，最终平仓日后取最先5根，持有段全部保留。开仓日缺失时返回空窗口和 `daily_coverage_state="missing_entry_day"`。

`build_daily_source_manifest()` 每个合约一行，字段固定为 `vt_symbol/row_count/min_trade_date/max_trade_date/canonical_sha256/source`；SHA256使用按固定列和ISO日期输出的UTF-8 CSV字节。

- [ ] **Step 7: 运行Task 1测试**

Run:

```bash
.py311/bin/python -m pytest research/lines/futures_trend_stage819_intraday_rules/tests/test_stage208_c9_2r_winner_15m_atlas.py -v
```

Expected: all tests PASS。

- [ ] **Step 8: 提交Task 1**

```bash
git add research/lines/futures_trend_stage819_intraday_rules/tools/stage208_c9_2r_winner_15m_atlas.py research/lines/futures_trend_stage819_intraday_rules/tests/test_stage208_c9_2r_winner_15m_atlas.py
git commit -m "feat: add stage210 daily context pipeline"
```

### Task 2: 三轴单图和日成交量

**Files:**
- Modify: `research/lines/futures_trend_stage819_intraday_rules/tools/stage208_c9_2r_winner_15m_atlas.py:362-533`
- Test: `research/lines/futures_trend_stage819_intraday_rules/tests/test_stage208_c9_2r_winner_15m_atlas.py`

**Interfaces:**
- Consumes: Task 1的 `select_daily_window()`。
- Produces: `create_winner_figure(event: pd.Series, bars15: pd.DataFrame, daily_window: pd.DataFrame, window_days: list[pd.Timestamp], raw_1m_bars: int, daily_coverage: dict[str, object]) -> tuple[matplotlib.figure.Figure, dict[str, object]]`
- Modifies: `plot_winner(..., daily_bars: pd.DataFrame, ...) -> dict[str, object]`

- [ ] **Step 1: 写三轴结构失败测试**

构造2根15分钟K和3根日K，调用 `create_winner_figure()`：

```python
figure, coverage = stage208.create_winner_figure(
    event, bars15, daily_window, window_days, raw_1m_bars=2,
    daily_coverage={"daily_bar_count": 3, "daily_before_count": 1, "daily_holding_count": 1, "daily_after_count": 1, "daily_coverage_state": "partial"},
)
assert len(figure.axes) == 3
assert [axis.get_ylabel() for axis in figure.axes] == ["15m Price", "Daily Price", "Daily Volume"]
assert len(figure.axes[0].containers) == 0
assert len(figure.axes[2].containers) == 1
plt.close(figure)
```

- [ ] **Step 2: 运行三轴测试确认RED**

Run focused pytest，Expected: FAIL，函数未定义。

- [ ] **Step 3: 实现三轴figure构建器**

- `plt.subplots(3, 1, figsize=(18, 12), dpi=150, gridspec_kw={"height_ratios": [5, 2.6, 1]})`。
- 15分钟轴复用现有蜡烛绘制、开仓日背景、交易日边界和开仓价线，删除原分钟volume bar。
- 日K轴按连续整数x绘制wick与body，红涨绿跌；开仓日 `axvspan`，最终平仓日紫色 `axvline`，开仓价蓝色虚线。
- 日成交量轴用与日K一致颜色，和日K共享x轴；日期刻度只放最下轴，最多12个均匀刻度。
- 覆盖结果合并分钟和日线字段。
- 日线窗口空时，中下轴关闭刻度并显示 `Daily bars unavailable: <state>`；仍返回figure。

- [ ] **Step 4: 写日成交量颜色测试**

两根日K分别上涨和下跌，断言日成交量两个patch颜色依次为 `#d62728`、`#159447`；允许Matplotlib RGBA浮点误差，使用 `matplotlib.colors.to_rgba` 与 `np.allclose`。

- [ ] **Step 5: 改造保存函数和Atlas尺寸**

- `plot_winner()` 调 `create_winner_figure()` 后保存并关闭。
- `write_placeholder()` 同步改为 `18x12`，缺分钟时仍在顶部说明；若日线可用，不能整张图直接退化为空白占位，必须继续画日K与日成交量。
- `_write_atlas_pages()` 维持2x2/每页4笔，页面改为约 `24x16`，标题不变。

- [ ] **Step 6: 运行Task 2测试并视觉查看fixture PNG**

Run full Stage208 test file，Expected: all PASS。使用本地图片查看测试生成图，确认三层比例、标题和刻度不重叠。

- [ ] **Step 7: 提交Task 2**

```bash
git add research/lines/futures_trend_stage819_intraday_rules/tools/stage208_c9_2r_winner_15m_atlas.py research/lines/futures_trend_stage819_intraday_rules/tests/test_stage208_c9_2r_winner_15m_atlas.py
git commit -m "feat: render daily context under stage210 winners"
```

### Task 3: 输出审计、正式重建和Stage212记录

**Files:**
- Modify: `research/lines/futures_trend_stage819_intraday_rules/tools/stage208_c9_2r_winner_15m_atlas.py:535-end`
- Modify: `research/lines/futures_trend_stage819_intraday_rules/tests/test_stage208_c9_2r_winner_15m_atlas.py`
- Modify at runtime: `research/lines/futures_trend_stage819_intraday_rules/outputs/stage208_c9_2r_winner_15m_atlas/*`
- Create: `research/lines/futures_trend_stage819_intraday_rules/stages/20260808_1822_stage212_c9_2r_winner_daily_context_result.md`
- Modify: `research/lines/futures_trend_stage819_intraday_rules/LINE.md`

**Interfaces:**
- Consumes: `load_daily_context()`、`build_daily_source_manifest()`、三轴 `plot_winner()`。
- Modifies: `write_outputs(..., daily_context: dict[str, pd.DataFrame], ...) -> dict[str, object]`
- Modifies: `run(output_dir: Path = OUTPUT_DIR) -> dict[str, object]`

- [ ] **Step 1: 更新端到端测试为日线必传**

在现有两winner fixture中，为两个合约各构造至少66根日K并传 `daily_context`。新增断言：

```python
coverage = pd.read_csv(output_dir / "coverage_summary.csv")
assert coverage["daily_coverage_state"].tolist() == ["complete", "complete"]
assert (output_dir / "daily_source_manifest.csv").exists()
decision = json.loads((output_dir / "decision.json").read_text())
assert decision["daily_complete_count"] == 2
assert decision["daily_missing_count"] == 0
```

- [ ] **Step 2: 运行端到端测试确认RED**

Expected: FAIL，`write_outputs()` 不接受daily_context或缺少日线审计字段。

- [ ] **Step 3: 改造输出编排**

- `write_outputs()` 对每笔winner取 `daily_context[vt_symbol]`，调用 `select_daily_window()`，再传给 `plot_winner()`。
- 输出 `daily_source_manifest.csv`。
- `coverage_summary.csv` 增加设计冻结的6个日线字段。
- `decision.json` 增加 `daily_source="vnpy_local_database_exact_contract_daily"`、`daily_complete_count`、`daily_partial_count`、`daily_missing_count`、`daily_contract_count`、`layout="15m_kline+daily_kline+daily_volume"`。
- `report.md` 明确分钟成交量已删除，日成交量来自逐月日K。
- `run()` 在绘图前调用 `load_daily_context(winners)`，不得连接CTP或调用订单模块。

- [ ] **Step 4: 运行全部定向测试与静态检查**

```bash
.py311/bin/python -m pytest research/lines/futures_trend_stage819_intraday_rules/tests/test_stage208_c9_2r_winner_15m_atlas.py -v
.py311/bin/python -m py_compile research/lines/futures_trend_stage819_intraday_rules/tools/stage208_c9_2r_winner_15m_atlas.py
git diff --check
```

- [ ] **Step 5: 正式只读重建71张单图和18页Atlas**

```bash
.py311/bin/python research/lines/futures_trend_stage819_intraday_rules/tools/stage208_c9_2r_winner_15m_atlas.py
```

Expected: `winner_count=71`、`daily_complete_count=71`、`single_chart_count=71`、`atlas_page_count=18`、订单API 0、CTP false。

- [ ] **Step 6: 执行机器闸门**

检查：manifest 71且R单调不增；coverage 71且日线complete 71；winner PNG 71；Atlas 18；PNG hash 89/89；daily source manifest 71；订单API 0；CTP false。

- [ ] **Step 7: 视觉抽查**

查看排名1、36、41、71和Atlas首页；确认：顶部没有分钟成交量；中间日K覆盖60日前置到5日后置；底部日成交量颜色与日K一致；开仓日黄色、平仓日紫色、开仓价蓝线；标题/刻度无截断。

- [ ] **Step 8: 写Stage212中文结果和更新LINE**

记录真实完成分钟、日线71/71覆盖、布局变化、输入身份hash、分钟52/19覆盖、测试和视觉结果、全量pytest既有失败状态、零订单API、过拟合与继续价值判断。明确本图谱仍是事后赢家法证。

- [ ] **Step 9: 提交审计元数据和结果记录**

PNG保留本地、不进Git。强制添加ignored输出中的 `winner_manifest.csv/coverage_summary.csv/daily_source_manifest.csv/decision.json/report.md/png_sha256.csv/minute_cache_sha256.csv`，提交脚本、测试、Stage212和LINE：

```bash
git commit -m "research: add daily context to stage210 winner atlas"
```

## 计划自检

- 设计覆盖：删除分钟量、增加日K和日成交量、60/5窗口、逐月合约、71/71覆盖、Atlas同步、缺失审计均有明确任务。
- 边界一致：Task 1返回日线帧和覆盖；Task 2只负责figure；Task 3编排和落盘。
- 类型一致：`daily_context` 全程为 `dict[str, pd.DataFrame]`；`select_daily_window()` 全程返回 `(DataFrame, dict)`。
- 隔离一致：只修改当前研究线的tools/tests/stages/outputs/LINE，不修改正式配置、回测或执行链路。
- 无占位步骤：每个实现、测试、运行和验收动作均给出接口、输入和预期结果。

