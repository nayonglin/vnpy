# Stage001 Account Context Feature Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建并冻结一个完全不读取账户标签的Stage001特征生产器，按已确认公式生成51个月×rank10..18的十五项XGBoost输入及可复验PIT审计。

**Architecture:** 在新研究线内实现一个单文件纯函数工具：底层负责六项组合上下文数学函数，中层负责逐合约损益聚合、严格120日窗口和月度面板拼装，顶层负责输入SHA门禁、确定性产物发布和只读审计。Stage001只生产特征合同，不导入XGBoost、不训练模型、不回测；Stage002和Stage003不属于本计划。

**Tech Stack:** Python `3.11.15`、NumPy `2.4.4`、pandas `2.3.3`、pytest、标准库`hashlib/json/pathlib/re`。

**Spec:** `research/lines/futures_trend_xgboost_account_context/LINE.md`（SHA256 `ec3e585636d3e3dbd30e11df992cbe023120c2ed98bbe76e2a3ba30d69d94364`）及`research/lines/futures_trend_xgboost_account_context/stages/20260902_1107_stage000_account_context_design.md`（SHA256 `1591494f782fd12c6d5fd4bb2da48d9d0b7c1d54b0bfedb7616d9cb61f565d34`）。

## Global Constraints

- 解释器固定使用`.py311/bin/python`；测试固定使用`.py311/bin/python -m pytest`。
- 正式基准固定为`ai_top10_plus_fu_official_live_v1`、release `m0005_20260901T165450+0800_1961d98ccb2b`。
- 只允许写`research/lines/futures_trend_xgboost_account_context/`及结果落地后的`research/registry.md`一行增量；不得修改上游研究线和`/Users/bytedance/Desktop/person/vnpy_production_live`。
- Stage001不得引用、打开、hash或统计Stage015 development标签和sealed holdout标签；允许读取的CSV只有正式完整排序、Stage014标签前面板和冻结`position_changes`。
- `eval_date`窗口固定为源文件中`<=eval_date`的最后120个全局交易日并包含`eval_date`；不得缩窗、插补非结构缺失、删月份、删品种或改公式。
- 六项上下文特征、原九项特征、51个月、459行、rank10..18、39/12 development/holdout切分均按规格逐项冻结。
- Stage001不得导入`xgboost`、不得训练模型、不得运行回测、不得连接CTP、不得调用订单API。
- 当前工作区已有无关改动。每次`git add`只能列出本研究线的明确文件；禁止`git add -A`、`git add .`或提交`research/registry.md`中的既有混合改动。
- Stage001实际数据可行性失败即记录并闭线；实现缺陷可以修复，但不得用结果修改数学定义。

## File Structure

- Create: `research/lines/futures_trend_xgboost_account_context/tools/stage001_account_context_feature_contract.py`
  - 唯一职责：纯数学函数、PIT面板拼装、输入身份验证、确定性Stage001产物发布。
- Create: `research/lines/futures_trend_xgboost_account_context/tests/test_stage001_account_context_feature_contract.py`
  - 唯一职责：公式数值、失败边界、未来扰动不变性、真实冻结输入集成和产物确定性测试。
- Create at runtime: `research/lines/futures_trend_xgboost_account_context/artifacts/stage001_account_context_feature_contract/`
  - `prelabel_feature_panel.csv`
  - `window_audit.csv`
  - `feature_contract.json`
  - `report.md`
  - `artifact_manifest.json`
- Create after the frozen run: `research/lines/futures_trend_xgboost_account_context/stages/20260902_<HHMM>_stage001_account_context_feature_contract_result.md`
- Modify after the frozen run: `research/lines/futures_trend_xgboost_account_context/LINE.md`
- Modify after the frozen run: `research/registry.md`，只更新本线行和索引时间。

---

### Task 1: Freeze Pure Context Mathematics

**Files:**
- Create: `research/lines/futures_trend_xgboost_account_context/tools/stage001_account_context_feature_contract.py`
- Create: `research/lines/futures_trend_xgboost_account_context/tests/test_stage001_account_context_feature_contract.py`

**Interfaces:**
- Consumes: 三个长度恰为120、全有限的`numpy.ndarray`：Top9聚合损益、正式rank10损益、候选损益。
- Produces: `compute_context_feature_deltas(top9_aggregate: np.ndarray, rank10: np.ndarray, candidate: np.ndarray) -> dict[str, float]`，键顺序与六项冻结特征完全一致。
- Raises: `Stage001ContractError(code: str)`；`str(error)`必须等于稳定机器错误码。

- [ ] **Step 1: Write the failing contract and happy-path tests**

Create the test module with these imports, loader, fixture and assertions:

```python
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/stage001_account_context_feature_contract.py"


def load_module():
    assert MODULE_PATH.exists(), "Stage001 account-context feature contract is not implemented"
    spec = importlib.util.spec_from_file_location(
        "stage001_account_context_feature_contract", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def deterministic_vectors() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    top9 = np.tile(np.array([2.0, -2.0, 1.0, -1.0]), 30)
    rank10 = 0.5 * top9
    challenger = -0.5 * top9
    return top9, rank10, challenger


def test_context_feature_names_are_exactly_frozen() -> None:
    module = load_module()
    assert module.CONTEXT_FEATURE_COLUMNS == [
        "candidate_top9_aggregate_corr_120d_delta_vs_rank10",
        "candidate_top9_downside_corr_120d_delta_vs_rank10",
        "candidate_top9_active_overlap_rate_120d_delta_vs_rank10",
        "candidate_top9_joint_loss_rate_120d_delta_vs_rank10",
        "top9_plus_candidate_drawdown_improvement_ratio_120d_vs_rank10",
        "top9_plus_candidate_sharpe_improvement_120d_vs_rank10",
    ]
    assert module.WINDOW_DAYS == 120
    assert module.MIN_DOWNSIDE_DAYS == 20


def test_context_deltas_match_hand_calculation() -> None:
    module = load_module()
    top9, rank10, challenger = deterministic_vectors()
    result = module.compute_context_feature_deltas(top9, rank10, challenger)

    assert list(result) == module.CONTEXT_FEATURE_COLUMNS
    assert result[module.CONTEXT_FEATURE_COLUMNS[0]] == pytest.approx(-2.0)
    assert result[module.CONTEXT_FEATURE_COLUMNS[1]] == pytest.approx(-2.0)
    assert result[module.CONTEXT_FEATURE_COLUMNS[2]] == pytest.approx(0.0)
    assert result[module.CONTEXT_FEATURE_COLUMNS[3]] == pytest.approx(-0.5)
    assert result[module.CONTEXT_FEATURE_COLUMNS[4]] == pytest.approx(2.0 / 3.0)
    assert result[module.CONTEXT_FEATURE_COLUMNS[5]] == pytest.approx(0.0, abs=1e-15)


def test_rank10_self_comparison_is_exact_zero() -> None:
    module = load_module()
    top9, rank10, _ = deterministic_vectors()
    result = module.compute_context_feature_deltas(top9, rank10, rank10.copy())
    assert result == {name: 0.0 for name in module.CONTEXT_FEATURE_COLUMNS}
```

- [ ] **Step 2: Run the tests and observe the required red state**

Run:

```bash
.py311/bin/python -m pytest research/lines/futures_trend_xgboost_account_context/tests/test_stage001_account_context_feature_contract.py -q
```

Expected: FAIL with `Stage001 account-context feature contract is not implemented` because the tool file does not exist.

- [ ] **Step 3: Add explicit failure-boundary tests**

Append:

```python
@pytest.mark.parametrize(
    ("top9", "rank10", "candidate", "code"),
    [
        (np.ones(119), np.ones(119), np.ones(119), "context_window_length_not_120"),
        (
            np.r_[np.array([-2.0, -1.0] * 9), -1.0, np.ones(101)],
            np.tile(np.array([1.0, 2.0]), 60),
            np.tile(np.array([2.0, 1.0]), 60),
            "top9_downside_days_below_20",
        ),
        (
            np.tile(np.array([1.0, -1.0]), 60),
            np.zeros(120),
            np.tile(np.array([1.0, -1.0]), 60),
            "rank10_activity_days_zero",
        ),
        (
            np.tile(np.array([1.0, -1.0]), 60),
            np.tile(np.array([1.0, -1.0]), 60),
            np.full(120, np.nan),
            "context_vector_nonfinite",
        ),
    ],
)
def test_context_contract_rejects_invalid_vectors(
    top9: np.ndarray,
    rank10: np.ndarray,
    candidate: np.ndarray,
    code: str,
) -> None:
    module = load_module()
    with pytest.raises(module.Stage001ContractError, match=f"^{code}$"):
        module.compute_context_feature_deltas(top9, rank10, candidate)
```

- [ ] **Step 4: Implement the minimal pure functions**

Create the tool with the following public constants, error type and numerical implementation:

```python
from __future__ import annotations

import math
from typing import Final

import numpy as np


WINDOW_DAYS: Final = 120
MIN_DOWNSIDE_DAYS: Final = 20
CONTEXT_FEATURE_COLUMNS: Final = [
    "candidate_top9_aggregate_corr_120d_delta_vs_rank10",
    "candidate_top9_downside_corr_120d_delta_vs_rank10",
    "candidate_top9_active_overlap_rate_120d_delta_vs_rank10",
    "candidate_top9_joint_loss_rate_120d_delta_vs_rank10",
    "top9_plus_candidate_drawdown_improvement_ratio_120d_vs_rank10",
    "top9_plus_candidate_sharpe_improvement_120d_vs_rank10",
]


class Stage001ContractError(RuntimeError):
    pass


def _vectors(*values: np.ndarray) -> tuple[np.ndarray, ...]:
    arrays = tuple(np.asarray(value, dtype=float).reshape(-1) for value in values)
    if any(array.size != WINDOW_DAYS for array in arrays):
        raise Stage001ContractError("context_window_length_not_120")
    if any(not np.isfinite(array).all() for array in arrays):
        raise Stage001ContractError("context_vector_nonfinite")
    return arrays


def _pearson(left: np.ndarray, right: np.ndarray, prefix: str) -> float:
    if float(np.std(left, ddof=1)) <= 0.0 or float(np.std(right, ddof=1)) <= 0.0:
        raise Stage001ContractError(f"{prefix}_standard_deviation_zero")
    value = float(np.corrcoef(left, right)[0, 1])
    if not math.isfinite(value):
        raise Stage001ContractError(f"{prefix}_correlation_nonfinite")
    return value


def _active_overlap(candidate: np.ndarray, top9: np.ndarray, prefix: str) -> float:
    active = candidate != 0.0
    count = int(active.sum())
    if count == 0:
        raise Stage001ContractError(f"{prefix}_activity_days_zero")
    return float(np.logical_and(active, top9 != 0.0).sum() / count)


def _drawdown(values: np.ndarray) -> float:
    cumulative = np.cumsum(values)
    return float(np.min(cumulative - np.maximum.accumulate(cumulative)))


def _sharpe(values: np.ndarray, prefix: str) -> float:
    scale = float(np.std(values, ddof=1))
    if scale <= 0.0:
        raise Stage001ContractError(f"{prefix}_portfolio_standard_deviation_zero")
    return float(np.mean(values) / scale * math.sqrt(252.0))


def compute_context_feature_deltas(
    top9_aggregate: np.ndarray,
    rank10: np.ndarray,
    candidate: np.ndarray,
) -> dict[str, float]:
    top9, baseline, challenger = _vectors(top9_aggregate, rank10, candidate)
    downside = top9 < 0.0
    if int(downside.sum()) < MIN_DOWNSIDE_DAYS:
        raise Stage001ContractError("top9_downside_days_below_20")

    baseline_overlap = _active_overlap(baseline, top9, "rank10")
    challenger_overlap = _active_overlap(challenger, top9, "candidate")
    baseline_corr = _pearson(baseline, top9, "rank10_top9")
    challenger_corr = _pearson(challenger, top9, "candidate_top9")
    baseline_down_corr = _pearson(baseline[downside], top9[downside], "rank10_top9_downside")
    challenger_down_corr = _pearson(
        challenger[downside], top9[downside], "candidate_top9_downside"
    )
    baseline_joint_loss = float(np.logical_and(baseline < 0.0, top9 < 0.0).sum() / WINDOW_DAYS)
    challenger_joint_loss = float(
        np.logical_and(challenger < 0.0, top9 < 0.0).sum() / WINDOW_DAYS
    )
    baseline_portfolio = top9 + baseline
    challenger_portfolio = top9 + challenger
    baseline_drawdown = _drawdown(baseline_portfolio)
    if not baseline_drawdown < 0.0:
        raise Stage001ContractError("rank10_portfolio_drawdown_not_negative")

    values = [
        challenger_corr - baseline_corr,
        challenger_down_corr - baseline_down_corr,
        challenger_overlap - baseline_overlap,
        challenger_joint_loss - baseline_joint_loss,
        (_drawdown(challenger_portfolio) - baseline_drawdown) / abs(baseline_drawdown),
        _sharpe(challenger_portfolio, "candidate")
        - _sharpe(baseline_portfolio, "rank10"),
    ]
    if not np.isfinite(np.asarray(values, dtype=float)).all():
        raise Stage001ContractError("context_feature_nonfinite")
    return {
        name: 0.0 if challenger is baseline or np.array_equal(challenger, baseline) else float(value)
        for name, value in zip(CONTEXT_FEATURE_COLUMNS, values)
    }
```

Implementation note: do not use object identity to define rank10 equality alone. The `np.array_equal` branch is required so a copied rank10 vector publishes exact `0.0` while all validity checks still execute.

- [ ] **Step 5: Run the focused tests and confirm green**

Run the same pytest command. Expected: all Task 1 tests PASS.

- [ ] **Step 6: Commit only the Task 1 files**

```bash
git add research/lines/futures_trend_xgboost_account_context/tools/stage001_account_context_feature_contract.py research/lines/futures_trend_xgboost_account_context/tests/test_stage001_account_context_feature_contract.py
git commit -m "test: freeze account context feature math"
```

Do not stage `research/registry.md` or any upstream untracked research line.

---

### Task 2: Build the Strict PIT Monthly Feature Panel

**Files:**
- Modify: `research/lines/futures_trend_xgboost_account_context/tools/stage001_account_context_feature_contract.py`
- Modify: `research/lines/futures_trend_xgboost_account_context/tests/test_stage001_account_context_feature_contract.py`

**Interfaces:**
- Consumes: `position_changes` rows with`date/vt_symbol/net_pnl`、正式完整排序 rows with`eval_date/product_vt_symbol/score_rank`、Stage014标签前面板。
- Produces: `build_product_daily(position_changes: pd.DataFrame, products: list[str]) -> pd.DataFrame`。
- Produces: `build_context_feature_panel(base_panel: pd.DataFrame, formal_ranking: pd.DataFrame, product_daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]`；第二个返回值是一月一行的窗口审计。

- [ ] **Step 1: Add product aggregation and zero-grid tests**

Append these imports and test:

```python
import pandas as pd


def test_product_daily_matches_formal_contract_mapping_and_zero_grid() -> None:
    module = load_module()
    raw = pd.DataFrame(
        {
            "date": ["2022-01-03", "2022-01-03", "2022-01-04"],
            "vt_symbol": ["AP205.CZCE", "AP209.CZCE", "rb2205.SHFE"],
            "net_pnl": [10.0, -3.0, 5.0],
        }
    )
    result = module.build_product_daily(raw, ["AP.CZCE", "rb.SHFE"])
    pivot = result.pivot(index="date", columns="product_vt_symbol", values="net_pnl")

    assert pivot.loc[pd.Timestamp("2022-01-03"), "AP.CZCE"] == 7.0
    assert pivot.loc[pd.Timestamp("2022-01-03"), "rb.SHFE"] == 0.0
    assert pivot.loc[pd.Timestamp("2022-01-04"), "AP.CZCE"] == 0.0
    assert pivot.loc[pd.Timestamp("2022-01-04"), "rb.SHFE"] == 5.0
```

- [ ] **Step 2: Add a complete one-month PIT fixture**

Append the exact fixture builder:

```python
BASE_FEATURE_COLUMNS = [
    "formal_probability_delta_vs_rank10",
    "formal_rank_distance",
    "pnl120_z_delta_vs_rank10",
    "pnl60_z_delta_vs_rank10",
    "sharpe60_z_delta_vs_rank10",
    "positive_day60_z_delta_vs_rank10",
    "opened60_z_delta_vs_rank10",
    "slippage60_z_delta_vs_rank10",
    "drawdown60_z_delta_vs_rank10",
]


def one_month_pit_fixture():
    dates = pd.bdate_range(end="2022-06-30", periods=121)
    eval_date = dates[-2]
    products = [f"p{rank}.TEST" for rank in range(1, 19)]
    top9 = np.tile(np.array([2.0, -2.0, 1.0, -1.0]), 30)
    values: dict[str, np.ndarray] = {}
    for rank, product in enumerate(products, start=1):
        if rank == 1:
            series = np.r_[top9, 0.0]
        elif rank <= 9:
            series = np.zeros(121)
        elif rank == 10:
            series = np.r_[0.5 * top9, 0.0]
        elif rank == 11:
            series = np.r_[-0.5 * top9, 1_000_000.0]
        else:
            series = np.r_[0.25 * top9, 0.0]
        values[product] = series

    daily_rows = [
        {"date": date, "product_vt_symbol": product, "net_pnl": float(values[product][i])}
        for i, date in enumerate(dates)
        for product in products
    ]
    ranking = pd.DataFrame(
        {
            "eval_date": [eval_date] * 18,
            "product_vt_symbol": products,
            "score_rank": list(range(1, 19)),
        }
    )
    base_rows = []
    for rank in range(10, 19):
        row = {
            "eval_date": eval_date,
            "next_eval_date": pd.Timestamp("2022-07-29"),
            "product_vt_symbol": f"p{rank}.TEST",
            "score_rank": rank,
            "score_type": "ai_probability_top19_plus_fixed_fu",
            "split": "development",
            "label_values_read_allowed": True,
        }
        row.update({name: 0.0 for name in BASE_FEATURE_COLUMNS})
        base_rows.append(row)
    return pd.DataFrame(base_rows), ranking, pd.DataFrame(daily_rows), eval_date
```

- [ ] **Step 3: Add future-shock, rank shape and audit tests**

```python
def test_monthly_context_panel_uses_only_dates_through_eval_date() -> None:
    module = load_module()
    base, ranking, daily, eval_date = one_month_pit_fixture()
    panel, audit = module.build_context_feature_panel(base, ranking, daily)

    rank10 = panel.loc[panel["score_rank"].eq(10), module.CONTEXT_FEATURE_COLUMNS]
    rank11 = panel.loc[panel["score_rank"].eq(11)].iloc[0]
    assert len(panel) == 9
    assert panel["score_rank"].tolist() == list(range(10, 19))
    assert (rank10.to_numpy(float) == 0.0).all()
    assert rank11[module.CONTEXT_FEATURE_COLUMNS[0]] == pytest.approx(-2.0)
    assert rank11[module.CONTEXT_FEATURE_COLUMNS[3]] == pytest.approx(-0.5)
    assert audit.to_dict("records") == [
        {
            "eval_date": eval_date.normalize(),
            "window_start": daily.loc[daily["date"].le(eval_date), "date"].drop_duplicates().sort_values().iloc[-120],
            "window_end": eval_date.normalize(),
            "window_days": 120,
            "top9_downside_days": 60,
            "rank_count": 18,
            "candidate_count": 9,
            "max_source_date_used": eval_date.normalize(),
        }
    ]


def test_future_position_change_cannot_change_any_feature() -> None:
    module = load_module()
    base, ranking, daily, eval_date = one_month_pit_fixture()
    first, _ = module.build_context_feature_panel(base, ranking, daily)
    future = daily["date"].gt(eval_date) & daily["product_vt_symbol"].eq("p11.TEST")
    daily.loc[future, "net_pnl"] = -9_000_000_000.0
    second, _ = module.build_context_feature_panel(base, ranking, daily)
    pd.testing.assert_frame_equal(first, second, check_exact=True)


def test_missing_rank_or_short_window_is_a_hard_failure() -> None:
    module = load_module()
    base, ranking, daily, _ = one_month_pit_fixture()
    with pytest.raises(module.Stage001ContractError, match="^formal_ranking_month_ranks_not_1_to_18$"):
        module.build_context_feature_panel(base, ranking[ranking["score_rank"].ne(7)], daily)
    short = daily[daily["date"].isin(sorted(daily["date"].unique())[-119:])]
    with pytest.raises(module.Stage001ContractError, match="^context_window_dates_below_120$"):
        module.build_context_feature_panel(base, ranking, short)
```

- [ ] **Step 4: Run the new tests and observe the red state**

Expected: FAIL with `AttributeError` for `build_product_daily` or `build_context_feature_panel`.

- [ ] **Step 5: Implement contract mapping, product daily aggregation and trailing matrix**

Add these imports, constants and functions to the tool:

```python
import re
from collections.abc import Sequence

import pandas as pd


BASE_FEATURE_COLUMNS: Final = [
    "formal_probability_delta_vs_rank10",
    "formal_rank_distance",
    "pnl120_z_delta_vs_rank10",
    "pnl60_z_delta_vs_rank10",
    "sharpe60_z_delta_vs_rank10",
    "positive_day60_z_delta_vs_rank10",
    "opened60_z_delta_vs_rank10",
    "slippage60_z_delta_vs_rank10",
    "drawdown60_z_delta_vs_rank10",
]
MODEL_FEATURE_COLUMNS: Final = [*BASE_FEATURE_COLUMNS, *CONTEXT_FEATURE_COLUMNS]


def product_from_contract(vt_symbol: object) -> str:
    raw = str(vt_symbol)
    if "." not in raw:
        return raw
    symbol, exchange = raw.split(".", 1)
    match = re.match(r"^([A-Za-z]+)", symbol)
    product = match.group(1) if match else symbol
    return f"{product}.{exchange}"


def build_product_daily(position_changes: pd.DataFrame, products: list[str]) -> pd.DataFrame:
    required = {"date", "vt_symbol", "net_pnl"}
    if missing := sorted(required - set(position_changes.columns)):
        raise Stage001ContractError(f"position_change_columns_missing:{','.join(missing)}")
    frame = position_changes.loc[:, ["date", "vt_symbol", "net_pnl"]].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
    frame["product_vt_symbol"] = frame["vt_symbol"].map(product_from_contract)
    frame["net_pnl"] = pd.to_numeric(frame["net_pnl"], errors="raise").astype(float)
    if not np.isfinite(frame["net_pnl"].to_numpy()).all():
        raise Stage001ContractError("position_change_net_pnl_nonfinite")
    grouped = frame.groupby(["date", "product_vt_symbol"], as_index=False)["net_pnl"].sum()
    dates = pd.DatetimeIndex(sorted(grouped["date"].unique()))
    index = pd.MultiIndex.from_product(
        [dates, sorted(products)], names=["date", "product_vt_symbol"]
    )
    result = grouped.set_index(["date", "product_vt_symbol"]).reindex(index).reset_index()
    result["net_pnl"] = result["net_pnl"].fillna(0.0).astype(float)
    return result


def _trailing_product_matrix(
    product_daily: pd.DataFrame,
    eval_date: pd.Timestamp,
    products: Sequence[str],
) -> pd.DataFrame:
    cutoff = pd.Timestamp(eval_date).normalize()
    dates = pd.DatetimeIndex(
        sorted(product_daily.loc[product_daily["date"].le(cutoff), "date"].unique())
    )
    if len(dates) < WINDOW_DAYS:
        raise Stage001ContractError("context_window_dates_below_120")
    window_dates = dates[-WINDOW_DAYS:]
    window = product_daily[
        product_daily["date"].isin(window_dates)
        & product_daily["product_vt_symbol"].isin(products)
    ].pivot(index="date", columns="product_vt_symbol", values="net_pnl")
    window = window.reindex(index=window_dates, columns=list(products))
    if window.shape != (WINDOW_DAYS, len(products)) or window.isna().any().any():
        raise Stage001ContractError("context_window_product_grid_incomplete")
    if window.index.max() > cutoff:
        raise Stage001ContractError("context_window_future_date_used")
    return window
```

- [ ] **Step 6: Implement monthly assembly without reading labels**

Add `build_context_feature_panel` with these checks and output ordering:

```python
def build_context_feature_panel(
    base_panel: pd.DataFrame,
    formal_ranking: pd.DataFrame,
    product_daily: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = base_panel.copy()
    ranking = formal_ranking.copy()
    daily = product_daily.copy()
    base["eval_date"] = pd.to_datetime(base["eval_date"], errors="raise").dt.normalize()
    ranking["eval_date"] = pd.to_datetime(ranking["eval_date"], errors="raise").dt.normalize()
    daily["date"] = pd.to_datetime(daily["date"], errors="raise").dt.normalize()
    base["score_rank"] = pd.to_numeric(base["score_rank"], errors="raise").astype(int)
    ranking["score_rank"] = pd.to_numeric(ranking["score_rank"], errors="raise").astype(int)
    if missing := sorted(set(BASE_FEATURE_COLUMNS) - set(base.columns)):
        raise Stage001ContractError(f"base_feature_columns_missing:{','.join(missing)}")
    if base.duplicated(["eval_date", "score_rank"]).any():
        raise Stage001ContractError("base_panel_month_rank_duplicate")

    rows: list[dict[str, object]] = []
    audits: list[dict[str, object]] = []
    for eval_date, month_base in base.groupby("eval_date", sort=True):
        month_base = month_base.sort_values("score_rank", kind="mergesort")
        if month_base["score_rank"].tolist() != list(range(10, 19)):
            raise Stage001ContractError("base_panel_month_ranks_not_10_to_18")
        month_ranking = ranking[ranking["eval_date"].eq(eval_date)].sort_values(
            "score_rank", kind="mergesort"
        )
        if month_ranking["score_rank"].tolist() != list(range(1, 19)):
            raise Stage001ContractError("formal_ranking_month_ranks_not_1_to_18")
        products = month_ranking["product_vt_symbol"].astype(str).tolist()
        if len(set(products)) != 18:
            raise Stage001ContractError("formal_ranking_month_product_duplicate")
        matrix = _trailing_product_matrix(daily, eval_date, products)
        top9_products = products[:9]
        rank10_product = products[9]
        top9 = matrix.loc[:, top9_products].sum(axis=1).to_numpy(float)
        baseline = matrix.loc[:, rank10_product].to_numpy(float)

        for source_row in month_base.to_dict("records"):
            product = str(source_row["product_vt_symbol"])
            expected_product = products[int(source_row["score_rank"]) - 1]
            if product != expected_product:
                raise Stage001ContractError("base_panel_formal_ranking_identity_mismatch")
            values = compute_context_feature_deltas(
                top9, baseline, matrix.loc[:, product].to_numpy(float)
            )
            rows.append({**source_row, **values})

        audits.append(
            {
                "eval_date": eval_date,
                "window_start": matrix.index.min(),
                "window_end": matrix.index.max(),
                "window_days": int(len(matrix)),
                "top9_downside_days": int((top9 < 0.0).sum()),
                "rank_count": int(len(month_ranking)),
                "candidate_count": int(len(month_base)),
                "max_source_date_used": matrix.index.max(),
            }
        )

    panel = pd.DataFrame(rows).sort_values(["eval_date", "score_rank"], kind="mergesort")
    panel.reset_index(drop=True, inplace=True)
    context = panel.loc[:, CONTEXT_FEATURE_COLUMNS].to_numpy(float)
    if not np.isfinite(context).all():
        raise Stage001ContractError("context_panel_nonfinite")
    rank10 = panel["score_rank"].eq(10)
    if not (panel.loc[rank10, CONTEXT_FEATURE_COLUMNS].to_numpy(float) == 0.0).all():
        raise Stage001ContractError("rank10_context_features_not_exact_zero")
    audit = pd.DataFrame(audits).sort_values("eval_date", kind="mergesort").reset_index(drop=True)
    return panel, audit
```

- [ ] **Step 7: Run all Stage001 unit tests and confirm green**

```bash
.py311/bin/python -m pytest research/lines/futures_trend_xgboost_account_context/tests/test_stage001_account_context_feature_contract.py -q
```

Expected: all Task 1 and Task 2 tests PASS, including future-shock invariance.

- [ ] **Step 8: Commit only the modified tool and test**

```bash
git add research/lines/futures_trend_xgboost_account_context/tools/stage001_account_context_feature_contract.py research/lines/futures_trend_xgboost_account_context/tests/test_stage001_account_context_feature_contract.py
git commit -m "feat: build PIT account context feature panel"
```

---

### Task 3: Publish a Deterministic, Label-Free Stage001 Contract

**Files:**
- Modify: `research/lines/futures_trend_xgboost_account_context/tools/stage001_account_context_feature_contract.py`
- Modify: `research/lines/futures_trend_xgboost_account_context/tests/test_stage001_account_context_feature_contract.py`
- Create at runtime: `research/lines/futures_trend_xgboost_account_context/artifacts/stage001_account_context_feature_contract/*`

**Interfaces:**
- Consumes: `run_stage001(output_dir: Path, input_paths: Mapping[str, Path] = INPUT_PATHS, expected_sha256: Mapping[str, str] = EXPECTED_SHA256) -> dict[str, Any]`。
- Produces: five deterministic files and a returned contract dictionary。
- Source read audit: `contract["read_paths"]` must list exactly three pinned inputs; `account_label_files_read=[]` and `account_label_values_read=False`.

- [ ] **Step 1: Add frozen identity and forbidden-import tests**

Append:

```python
def test_frozen_input_identities_and_stage_scope_are_exact() -> None:
    module = load_module()
    assert module.EXPECTED_SHA256 == {
        "formal_full_ranking": "b2cb417b6c57a7679ae43a1e564c1e79683ca9644b3434cb6a3bfc9e039fcfc0",
        "base_feature_panel": "e8272438cd69fe784b236ac91763f4ec0da71d2b711cd38b576c5e66d237f5fd",
        "position_changes": "17c81f2dbb30f836b544161c3fc4d4bd6415151d89b8f8937378739e868c21aa",
        "spec": "1591494f782fd12c6d5fd4bb2da48d9d0b7c1d54b0bfedb7616d9cb61f565d34",
    }
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "development_labels.csv" not in source
    assert "sealed_holdout_labels" not in source
    assert "import xgboost" not in source
    assert "from xgboost" not in source


def test_identity_drift_stops_before_any_csv_read(tmp_path, monkeypatch) -> None:
    module = load_module()
    tampered = tmp_path / "ranking.csv"
    tampered.write_text("tampered\n", encoding="utf-8")
    paths = dict(module.INPUT_PATHS)
    paths["formal_full_ranking"] = tampered
    calls: list[object] = []
    monkeypatch.setattr(module.pd, "read_csv", lambda *args, **kwargs: calls.append(args[0]))
    with pytest.raises(module.Stage001ContractError, match="^input_sha256_drift:formal_full_ranking$"):
        module.run_stage001(tmp_path / "out", input_paths=paths)
    assert calls == []
```

- [ ] **Step 2: Add real-input shape, read-audit and deterministic-output integration test**

```python
import hashlib
import json


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_real_frozen_inputs_publish_deterministic_label_free_contract(tmp_path) -> None:
    module = load_module()
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first = module.run_stage001(first_dir)
    second = module.run_stage001(second_dir)

    assert first == second
    assert first["decision"] == "stage001_account_context_prelabel_contract_pass"
    assert first["panel"] == {
        "rows": 459,
        "months": 51,
        "ranks_per_month": 9,
        "development_months": 39,
        "sealed_holdout_months": 12,
    }
    assert first["feature_count"] == 15
    assert first["account_label_files_read"] == []
    assert first["account_label_values_read"] is False
    assert first["runs_backtest"] is False
    assert first["trains_model"] is False
    assert first["ctp_connected"] is False
    assert first["order_api_called_count"] == 0
    assert set(first["read_paths"]) == {
        str(module.INPUT_PATHS["formal_full_ranking"]),
        str(module.INPUT_PATHS["base_feature_panel"]),
        str(module.INPUT_PATHS["position_changes"]),
    }
    assert first["pit"]["future_date_violations"] == 0
    assert first["pit"]["window_days_min"] == 120
    assert first["pit"]["window_days_max"] == 120
    assert first["quality"]["context_nonfinite_cells"] == 0
    assert first["quality"]["rank10_nonzero_context_cells"] == 0

    names = {
        "prelabel_feature_panel.csv",
        "window_audit.csv",
        "feature_contract.json",
        "report.md",
        "artifact_manifest.json",
    }
    assert {path.name for path in first_dir.iterdir()} == names
    assert {name: sha256(first_dir / name) for name in names} == {
        name: sha256(second_dir / name) for name in names
    }
    manifest = json.loads((first_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert manifest == {
        name: sha256(first_dir / name)
        for name in sorted(names - {"artifact_manifest.json"})
    }
```

- [ ] **Step 3: Run the publisher tests and observe the red state**

Expected: FAIL with `AttributeError` for `EXPECTED_SHA256`, `INPUT_PATHS` or `run_stage001`.

- [ ] **Step 4: Add frozen paths, SHA verification and deterministic serializers**

Add these imports and constants:

```python
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


LINE = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
UPSTREAM = WORKSPACE_ROOT / "research/lines/futures_trend_ai_xgboost_ensemble"
INPUT_PATHS: Final = {
    "formal_full_ranking": UPSTREAM / "artifacts/stage009_formal_full_ranking_recovery/formal_full_ranking.csv",
    "base_feature_panel": UPSTREAM / "artifacts/stage014_prelabel_feature_contract/prelabel_feature_panel.csv",
    "position_changes": Path(
        "/Users/bytedance/Library/Application Support/qmt-roll-stage179/production-live/official-live/"
        "qmt_roll_stage183_ai_source_floor35_position_changes_2020_2026_04.csv"
    ),
    "spec": LINE / "stages/20260902_1107_stage000_account_context_design.md",
}
EXPECTED_SHA256: Final = {
    "formal_full_ranking": "b2cb417b6c57a7679ae43a1e564c1e79683ca9644b3434cb6a3bfc9e039fcfc0",
    "base_feature_panel": "e8272438cd69fe784b236ac91763f4ec0da71d2b711cd38b576c5e66d237f5fd",
    "position_changes": "17c81f2dbb30f836b544161c3fc4d4bd6415151d89b8f8937378739e868c21aa",
    "spec": "1591494f782fd12c6d5fd4bb2da48d9d0b7c1d54b0bfedb7616d9cb61f565d34",
}
OUT = LINE / "artifacts/stage001_account_context_feature_contract"
DESIGN_FROZEN_AT: Final = "2026-09-02T11:07:00+08:00"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_inputs(paths: Mapping[str, Path], expected: Mapping[str, str]) -> None:
    if set(paths) != set(expected):
        raise Stage001ContractError("input_identity_keys_mismatch")
    for key in sorted(expected):
        path = Path(paths[key])
        if not path.is_file():
            raise Stage001ContractError(f"input_missing:{key}")
        if sha256_file(path) != expected[key]:
            raise Stage001ContractError(f"input_sha256_drift:{key}")
```

- [ ] **Step 5: Implement the end-to-end publisher**

`run_stage001` must follow this exact order:

1. Verify all four SHA values before any `pd.read_csv` call.
2. Read only the ranking, base panel and `position_changes`; append each resolved path to a local `read_paths` list.
3. Derive the formal product universe from ranking rows used by the 51 base-panel months.
4. Call `build_product_daily` and `build_context_feature_panel`.
5. Enforce 459 rows, 51 months, rank10..18, 39 development months, 12 sealed-holdout feature months, exact rank10 zeros, finite six-feature matrix and zero future-date violations.
6. Build a deterministic contract with `design_frozen_at=DESIGN_FROZEN_AT`; do not include wall-clock time, PID, temp directory or output directory.
7. Write to a new sibling temporary directory, then rename it atomically to`output_dir`; fail if either destination already exists.

Use this contract shape:

```python
contract = {
    "line_id": "futures_trend_xgboost_account_context",
    "stage": "Stage001",
    "design_frozen_at": DESIGN_FROZEN_AT,
    "decision": "stage001_account_context_prelabel_contract_pass",
    "formal_release_id": "m0005_20260901T165450+0800_1961d98ccb2b",
    "feature_count": 15,
    "base_features": BASE_FEATURE_COLUMNS,
    "context_features": CONTEXT_FEATURE_COLUMNS,
    "model_features": MODEL_FEATURE_COLUMNS,
    "panel": {
        "rows": 459,
        "months": 51,
        "ranks_per_month": 9,
        "development_months": 39,
        "sealed_holdout_months": 12,
    },
    "pit": {
        "window_days_min": int(audit["window_days"].min()),
        "window_days_max": int(audit["window_days"].max()),
        "minimum_top9_downside_days": int(audit["top9_downside_days"].min()),
        "max_source_date_used": audit["max_source_date_used"].max().date().isoformat(),
        "future_date_violations": int(
            audit["max_source_date_used"].gt(audit["eval_date"]).sum()
        ),
    },
    "quality": {
        "context_nonfinite_cells": int(
            (~np.isfinite(panel[CONTEXT_FEATURE_COLUMNS].to_numpy(float))).sum()
        ),
        "rank10_nonzero_context_cells": int(
            (panel.loc[panel["score_rank"].eq(10), CONTEXT_FEATURE_COLUMNS]
             .to_numpy(float) != 0.0).sum()
        ),
    },
    "input_identities": {
        key: {"path": str(Path(input_paths[key])), "sha256": expected_sha256[key]}
        for key in sorted(expected_sha256)
    },
    "read_paths": sorted(read_paths),
    "account_label_files_read": [],
    "account_label_values_read": False,
    "runs_backtest": False,
    "trains_model": False,
    "ctp_connected": False,
    "order_api_called_count": 0,
}
```

Serialization rules:

```python
panel.to_csv(temp_dir / "prelabel_feature_panel.csv", index=False, encoding="utf-8-sig", float_format="%.17g")
audit.to_csv(temp_dir / "window_audit.csv", index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
(temp_dir / "feature_contract.json").write_text(
    json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
```

The deterministic `report.md` must state the decision, 15 features, 459 rows/51 months, 120-day PIT range, minimum downside-day count, zero nonfinite cells, zero rank10 nonzero cells, and explicitly state “未读取账户标签、未训练模型、未回测、未连接CTP、未调用订单API”。 Build `artifact_manifest.json` last from the other four files, sorted by filename, and do not include the manifest's own hash.

Add:

```python
def main() -> None:
    contract = run_stage001(OUT)
    print(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run the complete Stage001 test file twice**

```bash
.py311/bin/python -m pytest research/lines/futures_trend_xgboost_account_context/tests/test_stage001_account_context_feature_contract.py -q
.py311/bin/python -m pytest research/lines/futures_trend_xgboost_account_context/tests/test_stage001_account_context_feature_contract.py -q
```

Expected: both runs PASS; the real-input integration test proves byte-identical outputs in two independent temp directories.

- [ ] **Step 7: Run syntax and source-scope checks**

```bash
.py311/bin/python -m py_compile research/lines/futures_trend_xgboost_account_context/tools/stage001_account_context_feature_contract.py research/lines/futures_trend_xgboost_account_context/tests/test_stage001_account_context_feature_contract.py
rg -n 'development_labels\.csv|sealed_holdout_labels|import xgboost|from xgboost|ctp|order_api' research/lines/futures_trend_xgboost_account_context/tools/stage001_account_context_feature_contract.py
```

Expected: compile succeeds; `rg` may show only the negative audit fields`account_label_values_read/ctp_connected/order_api_called_count`, and must show no label path, XGBoost import, CTP connection code or order invocation.

- [ ] **Step 8: Commit the deterministic publisher and tests**

```bash
git add research/lines/futures_trend_xgboost_account_context/tools/stage001_account_context_feature_contract.py research/lines/futures_trend_xgboost_account_context/tests/test_stage001_account_context_feature_contract.py
git commit -m "feat: publish label-free account context contract"
```

---

### Task 4: Execute the One Frozen Stage001 Run and Record the Decision

**Files:**
- Create at runtime: `research/lines/futures_trend_xgboost_account_context/artifacts/stage001_account_context_feature_contract/*`
- Create: `research/lines/futures_trend_xgboost_account_context/stages/20260902_<HHMM>_stage001_account_context_feature_contract_result.md`
- Modify: `research/lines/futures_trend_xgboost_account_context/LINE.md`
- Modify: `research/registry.md`

**Interfaces:**
- Consumes: Task 3 green test suite and exact frozen source SHAs.
- Produces on pass: decision `stage001_account_context_prelabel_contract_pass` and authorization only to draft the separate Stage002 preregistration; it does not authorize model training by itself.
- Produces on contract failure: stable error code, Stage001 failure record and closed research line; no formula fallback.

- [ ] **Step 1: Re-run the focused suite immediately before the frozen run**

```bash
.py311/bin/python -m pytest research/lines/futures_trend_xgboost_account_context/tests/test_stage001_account_context_feature_contract.py -q
```

Expected: PASS. Do not execute the frozen run after any failure.

- [ ] **Step 2: Confirm the production output directory does not exist**

```bash
test ! -e research/lines/futures_trend_xgboost_account_context/artifacts/stage001_account_context_feature_contract
```

Expected: exit 0. If it exists, stop and audit it; do not delete or overwrite it.

- [ ] **Step 3: Execute exactly one frozen Stage001 run**

```bash
.py311/bin/python research/lines/futures_trend_xgboost_account_context/tools/stage001_account_context_feature_contract.py
```

Expected pass path: prints JSON with`decision=stage001_account_context_prelabel_contract_pass` and creates exactly five files. Expected failure path: raises one stable`Stage001ContractError`; record that exact code and close the line without changing formulas.

- [ ] **Step 4: Verify the published contract and file identities independently**

```bash
.py311/bin/python -m json.tool research/lines/futures_trend_xgboost_account_context/artifacts/stage001_account_context_feature_contract/feature_contract.json
shasum -a 256 research/lines/futures_trend_xgboost_account_context/artifacts/stage001_account_context_feature_contract/prelabel_feature_panel.csv research/lines/futures_trend_xgboost_account_context/artifacts/stage001_account_context_feature_contract/window_audit.csv research/lines/futures_trend_xgboost_account_context/artifacts/stage001_account_context_feature_contract/feature_contract.json research/lines/futures_trend_xgboost_account_context/artifacts/stage001_account_context_feature_contract/report.md research/lines/futures_trend_xgboost_account_context/artifacts/stage001_account_context_feature_contract/artifact_manifest.json
```

Then run this read-only assertion:

```bash
.py311/bin/python -c 'import json,pathlib; p=pathlib.Path("research/lines/futures_trend_xgboost_account_context/artifacts/stage001_account_context_feature_contract/feature_contract.json"); c=json.loads(p.read_text()); assert c["decision"]=="stage001_account_context_prelabel_contract_pass"; assert c["panel"]=={"development_months":39,"months":51,"ranks_per_month":9,"rows":459,"sealed_holdout_months":12}; assert c["feature_count"]==15; assert c["pit"]["window_days_min"]==c["pit"]["window_days_max"]==120; assert c["pit"]["future_date_violations"]==0; assert c["quality"]["context_nonfinite_cells"]==0; assert c["quality"]["rank10_nonzero_context_cells"]==0; assert c["account_label_files_read"]==[] and c["account_label_values_read"] is False; assert c["runs_backtest"] is False and c["trains_model"] is False and c["ctp_connected"] is False and c["order_api_called_count"]==0; print("stage001_contract_verified")'
```

Expected: `stage001_contract_verified`.

- [ ] **Step 5: Write the Chinese Stage001 result record**

Use `date '+%Y%m%d_%H%M %Y-%m-%d %H:%M:%S %z'` once to choose the immutable stage filename. The record must include:

- exact five output SHAs from Step 4;
- actual row/month/rank/window/downside-day counts from `feature_contract.json`;
- source SHA identities and zero future-date violation;
- `期末权益/总收益/最大回撤/Sharpe/总滑点/总交易次数/胜率` all written as “不适用；Stage001未回测”；
- no independent backtest reviewer because no new backtest data was produced;
- pass decision authorizes only a separate Stage002 preregistration and pre-run review, not training in this plan;
- failure decision closes the line with the exact stable error code and no fallback;
- start/end overfit judgment and continue-value judgment.

- [ ] **Step 6: Update line status and registry surgically**

On pass, set `LINE.md` current status to “Stage001标签前特征合同通过；等待Stage002独立预注册和运行前复核”，and set the next step to drafting Stage002 only. On failure, set status to “Stage001可行性失败并闭线”，record the error code, and prohibit formula/window/product rescue.

In `research/registry.md`, modify only the `futures_trend_xgboost_account_context` row and the top update timestamp. Re-read the file immediately before applying the patch so concurrent unrelated edits remain intact.

- [ ] **Step 7: Run final verification**

```bash
.py311/bin/python -m pytest research/lines/futures_trend_xgboost_account_context/tests/test_stage001_account_context_feature_contract.py -q
.py311/bin/python -m py_compile research/lines/futures_trend_xgboost_account_context/tools/stage001_account_context_feature_contract.py
rg -n '[[:blank:]]+$|TO''DO|TB''D|待''定|待''补' research/lines/futures_trend_xgboost_account_context
git diff --check -- research/registry.md
git status --short -- research/lines/futures_trend_xgboost_account_context research/registry.md
```

Expected: tests and compile PASS; the red-flag scan has no output; whitespace check passes; status lists only intentional new-line files plus the pre-existing mixed registry modification.

- [ ] **Step 8: Commit only the new research-line implementation and records**

```bash
git add research/lines/futures_trend_xgboost_account_context
git commit -m "research: freeze account context feature contract"
```

Do not stage or commit`research/registry.md` in this dirty worktree. Report the registry update as local-only and separately identify the scoped commit SHA. Do not push, deploy or touch the production checkout.

## Self-Review Results

- Spec coverage: all six formulas、120日/PIT边界、原9+新增6、459行/51月、rank10精确零、禁止标签读取、确定性发布、无模型/回测/CTP/订单、阶段记录和研究线更新均有对应任务。
- Scope coverage: Stage002训练和Stage003真引擎明确排除；Stage001通过只会产生下一份预注册资格。
- Placeholder scan: no unresolved placeholder markers or generic “添加适当处理” steps。
- Type consistency: public names固定为`Stage001ContractError`、`compute_context_feature_deltas`、`build_product_daily`、`build_context_feature_panel`、`run_stage001`; tests and later tasks use the same signatures。
- Dirty-worktree safety: commits只包含新研究线；registry保留local-only，禁止批量stage。
