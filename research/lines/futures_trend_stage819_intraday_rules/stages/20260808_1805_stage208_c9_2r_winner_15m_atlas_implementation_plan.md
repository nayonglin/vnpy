# Stage208 C9/15万 2R大赢家15分钟K线图谱实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为当前正式 C9/15万 `2020-01` 基准中全部聚合收益 `>=2R` 的71笔交易，按聚合R降序生成开仓日前后各5个交易日的连续15分钟K线图、分页图谱和完整覆盖审计。

**Architecture:** 一个独立只读脚本完成冻结交易样本加载、交易日历映射、分钟数据分块读取、15分钟OHLC聚合、单图/atlas绘制和报告输出。纯函数承担样本聚合、夜盘交易日映射和15分钟重采样，先以单元测试锁定；主入口只编排本地历史文件，不导入或调用任何CTP/订单模块。

**Tech Stack:** Python 3.11 (`.py311/bin/python`)、pandas、NumPy、Matplotlib Agg、pytest、标准库 hashlib/json/pathlib。

## Global Constraints

- 正式版本固定为 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。
- 只使用 `requested_start_month == "2020-01"`；聚合键固定为 `open_trade_id`。
- `aggregate_r = sum(realized_pnl) / sum(risk_amount)`；选择门固定为 `aggregate_r >= 2.0`。
- 预期聚合开仓事件 `309`、赢家事件 `71`；任何不一致直接失败。
- 排序固定为 `aggregate_r desc, realized_pnl desc, entry_date asc, open_trade_id asc`。
- 图形窗口固定为前5、当日、后5个正式交易日；粒度固定为15分钟。
- 不能下载、插值或伪造缺失分钟K；缺失事件必须保留并生成占位图。
- 不修改正式配置、AI池、回测参数、CTP、邮件、launchd、其他研究线或根目录总账。
- `send_order_api_called_count=0`、`cancel_order_api_called_count=0`、`ctp_connected=false`。
- 运行前后都在报告中给出过拟合判断和继续价值判断。

---

## 文件结构

- Create: `research/lines/futures_trend_stage819_intraday_rules/tools/stage208_c9_2r_winner_15m_atlas.py`
  - 唯一职责：只读构建冻结赢家样本、交易日窗口、15分钟K线和图谱产物。
- Create: `research/lines/futures_trend_stage819_intraday_rules/tests/test_stage208_c9_2r_winner_15m_atlas.py`
  - 唯一职责：验证聚合筛选、排序、夜盘交易日映射、15分钟OHLC、窗口边界和占位图。
- Create at runtime: `research/lines/futures_trend_stage819_intraday_rules/outputs/stage208_c9_2r_winner_15m_atlas/`
  - 唯一职责：保存本阶段可再生的CSV、JSON、Markdown和PNG产物。
- Create after verified run: `research/lines/futures_trend_stage819_intraday_rules/stages/20260808_1805_stage209_c9_2r_winner_15m_atlas_result.md`
  - 唯一职责：中文记录实际运行参数、覆盖、结果、验证、反思和后续边界；正文记录运行完成时的真实分钟。

### Task 1: 冻结赢家选择、交易日映射和15分钟聚合

**Files:**
- Create: `research/lines/futures_trend_stage819_intraday_rules/tools/stage208_c9_2r_winner_15m_atlas.py`
- Create: `research/lines/futures_trend_stage819_intraday_rules/tests/test_stage208_c9_2r_winner_15m_atlas.py`

**Interfaces:**
- Produces: `build_winner_events(closed_lots: pd.DataFrame) -> pd.DataFrame`
- Produces: `build_trading_calendar(curves: pd.DataFrame) -> pd.DatetimeIndex`
- Produces: `assign_trading_day(bars: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.DataFrame`
- Produces: `select_window_days(entry_day: pd.Timestamp, calendar: pd.DatetimeIndex, before: int = 5, after: int = 5) -> list[pd.Timestamp]`
- Produces: `resample_15m(bars: pd.DataFrame) -> pd.DataFrame`

- [ ] **Step 1: 创建测试文件并写赢家聚合与排序失败测试**

```python
from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "stage208_c9_2r_winner_15m_atlas.py"
)
SPEC = importlib.util.spec_from_file_location("stage208", MODULE_PATH)
stage208 = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(stage208)


def test_build_winner_events_aggregates_filters_and_sorts() -> None:
    frame = pd.DataFrame(
        [
            {"requested_start_month": "2020-01", "open_trade_id": "A", "lot_id": 1, "vt_symbol": "rb.SHFE", "direction": "long", "entry_date": "2021-01-04", "exit_date": "2021-01-08", "entry_price": 100.0, "realized_pnl": 120.0, "risk_amount": 40.0},
            {"requested_start_month": "2020-01", "open_trade_id": "A", "lot_id": 2, "vt_symbol": "rb.SHFE", "direction": "long", "entry_date": "2021-01-04", "exit_date": "2021-01-11", "entry_price": 100.0, "realized_pnl": 80.0, "risk_amount": 40.0},
            {"requested_start_month": "2020-01", "open_trade_id": "B", "lot_id": 3, "vt_symbol": "jm.DCE", "direction": "short", "entry_date": "2021-02-01", "exit_date": "2021-02-03", "entry_price": 200.0, "realized_pnl": 60.0, "risk_amount": 20.0},
            {"requested_start_month": "2020-01", "open_trade_id": "C", "lot_id": 4, "vt_symbol": "FG.CZCE", "direction": "long", "entry_date": "2021-03-01", "exit_date": "2021-03-02", "entry_price": 300.0, "realized_pnl": 19.0, "risk_amount": 10.0},
            {"requested_start_month": "2021-01", "open_trade_id": "D", "lot_id": 5, "vt_symbol": "au.SHFE", "direction": "long", "entry_date": "2021-04-01", "exit_date": "2021-04-02", "entry_price": 400.0, "realized_pnl": 1000.0, "risk_amount": 10.0},
        ]
    )
    result = stage208.build_winner_events(frame, enforce_expected_counts=False)
    assert result["open_trade_id"].tolist() == ["B", "A"]
    assert result["aggregate_r"].round(2).tolist() == [3.00, 2.50]
    assert result["realized_pnl"].tolist() == [60.0, 200.0]
    assert result["winner_rank"].tolist() == [1, 2]
```

- [ ] **Step 2: 运行单测，确认因模块或函数缺失而失败**

Run:

```bash
.py311/bin/python -m pytest research/lines/futures_trend_stage819_intraday_rules/tests/test_stage208_c9_2r_winner_15m_atlas.py::test_build_winner_events_aggregates_filters_and_sorts -v
```

Expected: FAIL，报 `FileNotFoundError`、模块缺失或 `build_winner_events` 未定义。

- [ ] **Step 3: 写最小赢家聚合实现**

在实现脚本中定义常量 `EXPECTED_EVENT_COUNT = 309`、`EXPECTED_WINNER_COUNT = 71`、`WINNER_R_THRESHOLD = 2.0`，并实现：

```python
def build_winner_events(closed_lots: pd.DataFrame, *, enforce_expected_counts: bool = True) -> pd.DataFrame:
    frame = closed_lots[closed_lots["requested_start_month"].astype(str).eq("2020-01")].copy()
    for column in ["realized_pnl", "risk_amount", "entry_price"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in ["entry_date", "exit_date"]:
        frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.normalize()
    grouped = (
        frame.sort_values(["open_trade_id", "entry_date", "exit_date", "lot_id"])
        .groupby(["open_trade_id", "vt_symbol", "direction", "entry_date", "entry_price"], dropna=False)
        .agg(
            exit_date=("exit_date", "max"),
            realized_pnl=("realized_pnl", "sum"),
            risk_amount=("risk_amount", "sum"),
            lot_count=("lot_id", "size"),
        )
        .reset_index()
    )
    grouped["aggregate_r"] = grouped["realized_pnl"] / grouped["risk_amount"].replace(0.0, np.nan)
    if enforce_expected_counts and len(grouped) != EXPECTED_EVENT_COUNT:
        raise RuntimeError(f"expected {EXPECTED_EVENT_COUNT} events, got {len(grouped)}")
    winners = grouped[grouped["aggregate_r"].ge(WINNER_R_THRESHOLD)].copy()
    if enforce_expected_counts and len(winners) != EXPECTED_WINNER_COUNT:
        raise RuntimeError(f"expected {EXPECTED_WINNER_COUNT} winners, got {len(winners)}")
    winners = winners.sort_values(
        ["aggregate_r", "realized_pnl", "entry_date", "open_trade_id"],
        ascending=[False, False, True, True],
    ).reset_index(drop=True)
    winners.insert(0, "winner_rank", np.arange(1, len(winners) + 1, dtype=int))
    return winners
```

- [ ] **Step 4: 增加夜盘映射、窗口和15分钟聚合测试**

```python
def test_assign_trading_day_maps_night_to_next_available_day() -> None:
    calendar = pd.DatetimeIndex(pd.to_datetime(["2021-01-08", "2021-01-11", "2021-01-12"]))
    bars = pd.DataFrame(
        {
            "bar_datetime": pd.to_datetime(["2021-01-08 21:01", "2021-01-11 00:01", "2021-01-11 09:01"]),
            "vt_symbol": ["rb.SHFE"] * 3,
        }
    )
    result = stage208.assign_trading_day(bars, calendar)
    assert result["trading_day"].dt.strftime("%Y-%m-%d").tolist() == ["2021-01-11", "2021-01-11", "2021-01-11"]


def test_select_window_days_returns_five_before_and_after() -> None:
    calendar = pd.bdate_range("2021-01-01", periods=20)
    result = stage208.select_window_days(calendar[10], calendar)
    assert result == list(calendar[5:16])


def test_resample_15m_uses_ohlcv_and_does_not_fill_empty_buckets() -> None:
    bars = pd.DataFrame(
        {
            "vt_symbol": ["rb.SHFE"] * 4,
            "trading_day": pd.to_datetime(["2021-01-11"] * 4),
            "bar_datetime": pd.to_datetime(["2021-01-08 21:01", "2021-01-08 21:14", "2021-01-08 21:16", "2021-01-08 21:29"]),
            "open": [100, 102, 104, 103],
            "high": [103, 105, 106, 104],
            "low": [99, 101, 103, 100],
            "close": [102, 104, 103, 101],
            "volume": [1, 2, 3, 4],
            "open_oi": [10, 11, 12, 13],
            "close_oi": [11, 12, 13, 14],
        }
    )
    result = stage208.resample_15m(bars)
    assert len(result) == 2
    assert result.iloc[0][["open", "high", "low", "close", "volume", "open_oi", "close_oi"]].tolist() == [100, 105, 99, 104, 3, 10, 12]
    assert result.iloc[1][["open", "high", "low", "close", "volume", "open_oi", "close_oi"]].tolist() == [104, 106, 100, 101, 7, 12, 14]
```

- [ ] **Step 5: 实现交易日历、夜盘映射、窗口和重采样函数**

实现要求：

```python
def build_trading_calendar(curves: pd.DataFrame) -> pd.DatetimeIndex:
    frame = curves[curves["requested_start_month"].astype(str).eq("2020-01")].copy()
    dates = pd.to_datetime(frame["date"], errors="coerce").dropna().dt.normalize().drop_duplicates().sort_values()
    return pd.DatetimeIndex(dates)


def select_window_days(entry_day: pd.Timestamp, calendar: pd.DatetimeIndex, before: int = 5, after: int = 5) -> list[pd.Timestamp]:
    normalized = pd.Timestamp(entry_day).normalize()
    positions = np.flatnonzero(calendar == normalized)
    if len(positions) != 1:
        raise RuntimeError(f"entry day not uniquely present in calendar: {normalized.date()}")
    pos = int(positions[0])
    return list(calendar[max(0, pos - before) : min(len(calendar), pos + after + 1)])
```

`assign_trading_day()` 对 `hour >= 20` 使用 `calendar.searchsorted(calendar_date + 1 day, side="left")`，对其余分钟使用自然日；自然日不在日历时使用 `searchsorted(calendar_date, side="left")`，越过日历末端的记录标记 `NaT`。`resample_15m()` 用 `bar_datetime.dt.floor("15min")` 分桶并执行设计文档冻结的OHLCV/OI聚合，不生成空桶。

- [ ] **Step 6: 运行Task 1全部测试并确认通过**

Run:

```bash
.py311/bin/python -m pytest research/lines/futures_trend_stage819_intraday_rules/tests/test_stage208_c9_2r_winner_15m_atlas.py -v
```

Expected: 3 tests PASS, 0 failed。

- [ ] **Step 7: 提交Task 1**

```bash
git add research/lines/futures_trend_stage819_intraday_rules/tools/stage208_c9_2r_winner_15m_atlas.py research/lines/futures_trend_stage819_intraday_rules/tests/test_stage208_c9_2r_winner_15m_atlas.py
git commit -m "feat: add stage208 winner atlas data pipeline"
```

### Task 2: 图形输出、覆盖审计和报告

**Files:**
- Modify: `research/lines/futures_trend_stage819_intraday_rules/tools/stage208_c9_2r_winner_15m_atlas.py`
- Modify: `research/lines/futures_trend_stage819_intraday_rules/tests/test_stage208_c9_2r_winner_15m_atlas.py`

**Interfaces:**
- Consumes: Task 1的 `build_winner_events()`、`build_trading_calendar()`、`assign_trading_day()`、`select_window_days()`、`resample_15m()`。
- Produces: `load_target_minutes(path: Path, winners: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.DataFrame`
- Produces: `plot_winner(event: pd.Series, bars15: pd.DataFrame, window_days: list[pd.Timestamp], output_path: Path) -> dict[str, object]`
- Produces: `write_placeholder(event: pd.Series, output_path: Path, reason: str) -> None`
- Produces: `run(output_dir: Path = OUTPUT_DIR) -> dict[str, object]`

- [ ] **Step 1: 写分块分钟读取和缺失占位图测试**

```python
def test_load_target_minutes_filters_symbols_and_window(tmp_path: Path) -> None:
    source = tmp_path / "minutes.csv"
    pd.DataFrame(
        {
            "vt_symbol": ["rb.SHFE", "rb.SHFE", "jm.DCE"],
            "bar_datetime": ["2021-01-08 21:01", "2021-02-01 09:01", "2021-01-08 21:01"],
            "open": [100, 110, 200], "high": [101, 111, 201], "low": [99, 109, 199], "close": [100, 110, 200],
            "volume": [1, 1, 1], "open_oi": [10, 10, 20], "close_oi": [10, 10, 20],
        }
    ).to_csv(source, index=False)
    winners = pd.DataFrame([{"vt_symbol": "rb.SHFE", "entry_date": pd.Timestamp("2021-01-11")}])
    calendar = pd.DatetimeIndex(pd.to_datetime(["2021-01-08", "2021-01-11", "2021-01-12"]))
    result = stage208.load_target_minutes(source, winners, calendar, chunksize=2)
    assert result["vt_symbol"].unique().tolist() == ["rb.SHFE"]
    assert result["bar_datetime"].dt.strftime("%Y-%m-%d %H:%M").tolist() == ["2021-01-08 21:01"]


def test_write_placeholder_creates_nonempty_png(tmp_path: Path) -> None:
    output = tmp_path / "missing.png"
    event = pd.Series({"winner_rank": 71, "vt_symbol": "jm2609.DCE", "direction": "long", "entry_date": pd.Timestamp("2026-06-03"), "aggregate_r": 4.6667})
    stage208.write_placeholder(event, output, "no local minute bars")
    assert output.exists()
    assert output.stat().st_size > 1000
```

- [ ] **Step 2: 运行新增测试，确认函数缺失而失败**

Run:

```bash
.py311/bin/python -m pytest research/lines/futures_trend_stage819_intraday_rules/tests/test_stage208_c9_2r_winner_15m_atlas.py -v
```

Expected: FAIL at `load_target_minutes` or `write_placeholder` not defined。

- [ ] **Step 3: 实现分块读取与目标窗口过滤**

`load_target_minutes()` 必须：

- 先为每笔winner调用 `select_window_days()`，构建 `vt_symbol -> set[trading_day]`。
- 用 `pd.read_csv(..., chunksize=250_000, usecols=...)` 分块读取201MB分钟源。
- 先按目标 `vt_symbol` 过滤，再解析 `bar_datetime` 和数值列，然后调用 `assign_trading_day()`。
- 只保留该合约目标交易日集合内记录；按 `vt_symbol + bar_datetime` 去重、排序。
- 返回空DataFrame而不是下载或补值。

- [ ] **Step 4: 实现蜡烛图、成交量、占位图和分页atlas**

`plot_winner()` 使用 `matplotlib.use("Agg")`，以整数序号作为压缩后的连续x轴：

- wick：`ax.vlines(x, low, high)`；实体：`matplotlib.patches.Rectangle`。
- `close >= open` 为红色，反之为绿色；边框使用相同颜色。
- 用每个 `trading_day` 的首尾x范围绘制开仓日背景和日期分隔线。
- 开仓价水平虚线；只在可信非午夜时间存在时画开仓点。
- 成交量使用共享x轴的下方subplot。
- 图尺寸固定 `18 x 9` 英寸、`dpi=150`，标题包含排名、合约、方向、开仓日、退出日、入场价、R和PnL。
- 返回覆盖字段：`raw_1m_bars/aggregated_15m_bars/actual_trading_days/expected_trading_days/coverage_state/chart_path`。
- `write_placeholder()` 使用同样尺寸输出缺失原因、交易身份和收益排名。
- atlas读取已生成单图，按排名每页4张组成 `2 x 2`，最后一页空位关闭坐标轴。

- [ ] **Step 5: 实现run编排、hash、CSV/JSON/Markdown输出**

`run()` 固定读取：

```text
research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage006_current_quality_feature_binder/rebuilt_c9_stage006_current_quality_feature_binder_closed_lots_stage006_current_quality_feature_binder_v1.csv
research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage006_current_quality_feature_binder/rebuilt_c9_stage006_current_quality_feature_binder_curves_stage006_current_quality_feature_binder_v1.csv
research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage006_current_quality_feature_binder/rebuilt_c9_stage006_current_quality_feature_binder_trades_stage006_current_quality_feature_binder_v1.csv
examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage861_stage860_full_visual_atlas_full_minute_bars_stage861_stage860_full_visual_atlas_v1.csv
```

输出 `winner_manifest.csv`、`coverage_summary.csv`、71个 `winner_*.png`、18个 `atlas_page*.png`、`decision.json`、`report.md`。`decision.json` 必须包含四个输入的SHA256、`event_count=309`、`winner_count=71`、覆盖计数、单图计数、atlas页数、`send_order_api_called_count=0`、`cancel_order_api_called_count=0`、`ctp_connected=false`、运行前后反思。

- [ ] **Step 6: 增加小型端到端输出测试**

使用 `tmp_path` 构建2个winner和少量分钟数据，调用内部 `write_outputs()`（允许 `enforce_expected_counts=False`），断言：

```python
assert len(pd.read_csv(output_dir / "winner_manifest.csv")) == 2
assert len(list(output_dir.glob("winner_*.png"))) == 2
assert len(list(output_dir.glob("atlas_page*.png"))) == 1
decision = json.loads((output_dir / "decision.json").read_text())
assert decision["send_order_api_called_count"] == 0
assert decision["cancel_order_api_called_count"] == 0
assert decision["ctp_connected"] is False
```

- [ ] **Step 7: 运行全部Stage208测试**

Run:

```bash
.py311/bin/python -m pytest research/lines/futures_trend_stage819_intraday_rules/tests/test_stage208_c9_2r_winner_15m_atlas.py -v
```

Expected: all tests PASS, 0 failed。

- [ ] **Step 8: 提交Task 2代码**

```bash
git add research/lines/futures_trend_stage819_intraday_rules/tools/stage208_c9_2r_winner_15m_atlas.py research/lines/futures_trend_stage819_intraday_rules/tests/test_stage208_c9_2r_winner_15m_atlas.py
git commit -m "feat: render stage208 winner kline atlas"
```

### Task 3: 正式只读运行、视觉验证和中文阶段记录

**Files:**
- Create at runtime: `research/lines/futures_trend_stage819_intraday_rules/outputs/stage208_c9_2r_winner_15m_atlas/*`
- Create: `research/lines/futures_trend_stage819_intraday_rules/stages/20260808_1805_stage209_c9_2r_winner_15m_atlas_result.md`

**Interfaces:**
- Consumes: Task 2完整Stage208脚本和测试。
- Produces: 71笔按收益率排序的单图、18页atlas、覆盖审计和中文结果记录。

- [ ] **Step 1: 运行正式只读图谱生成**

Run:

```bash
.py311/bin/python research/lines/futures_trend_stage819_intraday_rules/tools/stage208_c9_2r_winner_15m_atlas.py
```

Expected: exit 0；stdout报告 `event_count=309`、`winner_count=71`、`single_chart_count=71`、`atlas_page_count=18`、订单API计数0。

- [ ] **Step 2: 执行机器验证**

Run:

```bash
.py311/bin/python - <<'PY'
import json
from pathlib import Path
import pandas as pd

out = Path('research/lines/futures_trend_stage819_intraday_rules/outputs/stage208_c9_2r_winner_15m_atlas')
manifest = pd.read_csv(out / 'winner_manifest.csv', encoding='utf-8-sig')
coverage = pd.read_csv(out / 'coverage_summary.csv', encoding='utf-8-sig')
decision = json.loads((out / 'decision.json').read_text(encoding='utf-8'))
assert len(manifest) == 71
assert manifest['aggregate_r'].is_monotonic_decreasing
assert manifest['winner_rank'].tolist() == list(range(1, 72))
assert len(coverage) == 71
assert len(list(out.glob('winner_*.png'))) == 71
assert len(list(out.glob('atlas_page*.png'))) == 18
assert decision['event_count'] == 309
assert decision['winner_count'] == 71
assert decision['send_order_api_called_count'] == 0
assert decision['cancel_order_api_called_count'] == 0
assert decision['ctp_connected'] is False
print(decision)
PY
```

Expected: exit 0 and printed decision JSON。

- [ ] **Step 3: 视觉抽查排名1、中位、末位、缺失占位和atlas首页**

使用本地图片查看工具逐张检查：

- `winner_0001_*.png`
- `winner_0036_*.png`
- `winner_0071_*.png`
- manifest中 `BACKTESTING.626` 对应PNG
- `atlas_page001.png`

验证蜡烛、成交量、日期标签、开仓日阴影、开仓价、标题和缺失原因无重叠或截断。若发现布局问题，只调整图形尺寸、刻度密度或文字位置；不得改变样本、R门槛、排序或数据。

- [ ] **Step 4: 重跑测试和静态检查**

Run:

```bash
.py311/bin/python -m pytest research/lines/futures_trend_stage819_intraday_rules/tests/test_stage208_c9_2r_winner_15m_atlas.py -v
.py311/bin/python -m py_compile research/lines/futures_trend_stage819_intraday_rules/tools/stage208_c9_2r_winner_15m_atlas.py
git diff --check
```

Expected: all tests PASS；`py_compile` exit 0；`git diff --check`无输出。

- [ ] **Step 5: 写Stage209中文结果记录**

记录真实完成时间、是否重要突破、数据区间、账户资金、正式版本、筛选门、排序、71笔清单摘要、覆盖率、缺失事件、输入hash、产物路径、测试结果、订单API计数、运行前后过拟合判断和继续价值判断。明确：图谱是事后赢家法证，不能直接生成交易规则或修改正式版。

- [ ] **Step 6: 提交产物清单与结果记录**

提交脚本、测试、CSV/JSON/Markdown和Stage209记录；71张单图与18张atlas PNG保留为本地可再生产物，不加入Git，避免把约89张大图写进仓库历史。Stage209记录PNG绝对目录、数量与hash清单。

Run:

```bash
git add \
  research/lines/futures_trend_stage819_intraday_rules/tools/stage208_c9_2r_winner_15m_atlas.py \
  research/lines/futures_trend_stage819_intraday_rules/tests/test_stage208_c9_2r_winner_15m_atlas.py \
  research/lines/futures_trend_stage819_intraday_rules/outputs/stage208_c9_2r_winner_15m_atlas/winner_manifest.csv \
  research/lines/futures_trend_stage819_intraday_rules/outputs/stage208_c9_2r_winner_15m_atlas/coverage_summary.csv \
  research/lines/futures_trend_stage819_intraday_rules/outputs/stage208_c9_2r_winner_15m_atlas/decision.json \
  research/lines/futures_trend_stage819_intraday_rules/outputs/stage208_c9_2r_winner_15m_atlas/report.md \
  research/lines/futures_trend_stage819_intraday_rules/outputs/stage208_c9_2r_winner_15m_atlas/png_sha256.csv \
  research/lines/futures_trend_stage819_intraday_rules/stages/20260808_1805_stage209_c9_2r_winner_15m_atlas_result.md
git commit -m "research: add stage208 2r winner kline atlas"
```

Suggested commit message:

```text
research: add stage208 2r winner kline atlas
```

## 计划自检

- 设计覆盖：赢家定义、2020起点、71笔全量、收益率排序、11交易日、15分钟聚合、夜盘映射、缺失保留、单图/atlas、覆盖报告和零订单API均有对应任务。
- 完整性检查：接口和输出路径都已冻结；Stage209正文记录真实完成分钟。
- 类型一致：Task 2消费的五个纯函数名称和Task 1完全一致；正式运行使用同一个 `run()` 入口。
- 隔离检查：只修改当前研究线的tools/tests/stages/outputs，不修改其他研究线、正式配置或执行链路。
