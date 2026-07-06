from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage099"
MODEL_TAG = "stage099_held_trend_deterioration_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage099_held_trend_deterioration_audit"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage099_held_trend_deterioration_audit"
STAGES_DIR = LINE_DIR / "stages"

STAGE096_OUT = LINE_DIR / "outputs" / "stage096_position_concentration_predictive_audit"
STAGE096_PREFIX = "rebuilt_c9_v2_stage096_position_concentration_predictive_audit"
STAGE096_TAG = "stage096_position_concentration_predictive_audit_v1"
POSITIONS_PATH = STAGE096_OUT / f"{STAGE096_PREFIX}_positions_{STAGE096_TAG}.csv.gz"
PANEL_PATH = STAGE096_OUT / f"{STAGE096_PREFIX}_exposure_panel_{STAGE096_TAG}.csv.gz"

HELD_PANEL_PATH = OUT / f"{OUTPUT_PREFIX}_held_panel_{MODEL_TAG}.csv.gz"
SEGMENT_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_segment_summary_{MODEL_TAG}.csv"
CONDITION_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_condition_summary_{MODEL_TAG}.csv"
BAD_WINDOW_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_bad_window_condition_summary_{MODEL_TAG}.csv"
TOP_LOSS_DAYS_PATH = OUT / f"{OUTPUT_PREFIX}_top_loss_days_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

BAD_WINDOW_START = pd.Timestamp("2022-07-15")
BAD_WINDOW_END = pd.Timestamp("2023-07-05")

EXTERNAL_RESEARCH = [
    {
        "source": "pysystemtrade backtesting documentation",
        "url": "https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md",
        "finding": "Position inertia/buffering separates signal changes from trading costs; exit attribution should avoid over-trading costs.",
    },
    {
        "source": "Rob Carver, Dynamic trend following",
        "url": "https://qoppac.blogspot.com/2020/12/dynamic-trend-following.html",
        "finding": "Stops can change trade path but easily harm trend right tails; use path attribution before changing exits.",
    },
    {
        "source": "Hudson & Thames meta-labeling / triple barrier",
        "url": "https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method/",
        "finding": "Secondary filters should use features available at decision time and need OOS validation before strategy use.",
    },
]

TARGET_COMPONENTS = [
    "next_holding_pnl",
    "next_same_symbol_rebalance_net_pnl",
    "next_same_symbol_net_pnl",
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    try:
        if pd.isna(value) and not isinstance(value, (str, bytes)):
            return None
    except Exception:
        pass
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _input_audit(paths: list[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.exists():
            stat = path.stat()
            rows.append(
                {
                    "path": str(path),
                    "exists": True,
                    "bytes": int(stat.st_size),
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    "sha256": _sha256(path),
                }
            )
        else:
            rows.append({"path": str(path), "exists": False, "bytes": 0, "mtime": "", "sha256": ""})
    return pd.DataFrame(rows)


def _numeric(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column in frame.columns:
        return pd.to_numeric(frame[column], errors="coerce").fillna(default)
    return pd.Series(default, index=frame.index, dtype=float)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    positions = pd.read_csv(POSITIONS_PATH, encoding="utf-8-sig")
    panel = pd.read_csv(PANEL_PATH, encoding="utf-8-sig")
    positions["date"] = pd.to_datetime(positions["date"], errors="coerce").dt.normalize()
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce").dt.normalize()
    panel["next_date"] = pd.to_datetime(panel["next_date"], errors="coerce").dt.normalize()
    positions["requested_start_month"] = positions["requested_start_month"].astype(str)
    panel["requested_start_month"] = panel["requested_start_month"].astype(str)
    for column in [
        "start_pos",
        "end_pos",
        "pos_change",
        "close_price",
        "pre_close",
        "holding_pnl",
        "trading_pnl",
        "commission",
        "slippage",
        "net_pnl",
        "trade_count",
    ]:
        positions[column] = _numeric(positions, column)
    for column in ["drawdown_depth_pct", "next_net_pnl", "account_equity"]:
        panel[column] = _numeric(panel, column)
    return positions.dropna(subset=["date"]).copy(), panel.dropna(subset=["date", "next_date"]).copy()


def build_price_features(positions: pd.DataFrame) -> pd.DataFrame:
    prices = (
        positions[["date", "vt_symbol", "close_price", "pre_close"]]
        .drop_duplicates(subset=["date", "vt_symbol"])
        .sort_values(["vt_symbol", "date"])
        .copy()
    )
    prices["close_price"] = prices["close_price"].where(prices["close_price"].gt(0), np.nan)
    prices["pre_close"] = prices["pre_close"].where(prices["pre_close"].gt(0), np.nan)
    grouped = prices.groupby("vt_symbol", group_keys=False)
    prices["ret1"] = prices["close_price"].div(prices["pre_close"]).sub(1.0)
    prices.loc[~np.isfinite(prices["ret1"]), "ret1"] = np.nan
    for window in [5, 20, 60, 120]:
        prices[f"ret{window}"] = grouped["close_price"].transform(lambda s, w=window: s.div(s.shift(w)).sub(1.0))
    for window in [20, 60, 120]:
        prices[f"ma{window}"] = grouped["close_price"].transform(lambda s, w=window: s.rolling(w, min_periods=w).mean())
    prices["vol20_abs_ret"] = grouped["ret1"].transform(lambda s: s.abs().rolling(20, min_periods=10).mean())
    prices["price_feature_ready"] = prices[["ma20", "ma60", "ret20"]].notna().all(axis=1)
    return prices


def build_held_panel(positions: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    price_features = build_price_features(positions)
    base = panel[
        [
            "requested_start_month",
            "date",
            "next_date",
            "drawdown_depth_pct",
            "next_net_pnl",
            "account_equity",
        ]
    ].copy()
    base["in_bad_window_by_next_date"] = base["next_date"].between(BAD_WINDOW_START, BAD_WINDOW_END)
    active = positions[positions["end_pos"].abs().gt(1e-9)][
        ["requested_start_month", "date", "vt_symbol", "end_pos", "close_price"]
    ].copy()
    held = active.merge(base, on=["requested_start_month", "date"], how="inner")
    next_positions = positions[
        [
            "requested_start_month",
            "date",
            "vt_symbol",
            "start_pos",
            "end_pos",
            "pos_change",
            "holding_pnl",
            "trading_pnl",
            "commission",
            "slippage",
            "net_pnl",
            "trade_count",
        ]
    ].rename(columns={"date": "next_date"})
    held = held.merge(
        next_positions,
        on=["requested_start_month", "next_date", "vt_symbol"],
        how="left",
        suffixes=("_prev", "_next"),
    )
    if "end_pos_prev" in held.columns:
        held = held.rename(columns={"end_pos_prev": "end_pos"})
    for column in ["start_pos", "end_pos_next", "pos_change", "holding_pnl", "trading_pnl", "commission", "slippage", "net_pnl", "trade_count"]:
        held[column] = _numeric(held, column)
    held = held.merge(
        price_features.drop(columns=["close_price", "pre_close"]),
        on=["date", "vt_symbol"],
        how="left",
    )
    held["direction_sign"] = np.sign(held["end_pos"])
    held["next_holding_pnl"] = held["holding_pnl"]
    held["next_same_symbol_rebalance_net_pnl"] = held["trading_pnl"] - held["commission"] - held["slippage"]
    held["next_same_symbol_net_pnl"] = held["net_pnl"]
    for window in [5, 20, 60, 120]:
        held[f"signed_ret{window}"] = held["direction_sign"] * held[f"ret{window}"]
    for window in [20, 60, 120]:
        held[f"signed_ma{window}_gap"] = held["direction_sign"] * held["close_price"].div(held[f"ma{window}"]).sub(1.0)
    held["signed_ma20_vs_ma60"] = held["direction_sign"] * held["ma20"].div(held["ma60"]).sub(1.0)
    held["signed_ret5_over_vol20"] = held["signed_ret5"].div(held["vol20_abs_ret"].replace(0.0, np.nan))
    held["trend_feature_ready"] = held[
        ["signed_ret5", "signed_ret20", "signed_ma20_gap", "signed_ma60_gap", "signed_ma20_vs_ma60"]
    ].notna().all(axis=1)
    return held


def _component_stats(frame: pd.DataFrame, segment: str) -> dict[str, Any]:
    row: dict[str, Any] = {
        "segment": segment,
        "rows": int(len(frame)),
        "start_count": int(frame["requested_start_month"].nunique()) if not frame.empty else 0,
        "date_count": int(frame["date"].nunique()) if not frame.empty else 0,
        "symbol_count": int(frame["vt_symbol"].nunique()) if not frame.empty else 0,
    }
    for component in TARGET_COMPONENTS:
        values = pd.to_numeric(frame[component], errors="coerce").fillna(0.0) if not frame.empty else pd.Series(dtype=float)
        row[f"{component}_sum"] = float(values.sum()) if not values.empty else 0.0
        row[f"{component}_positive_sum"] = float(values[values.gt(0)].sum()) if not values.empty else 0.0
        row[f"{component}_negative_abs_sum"] = float(-values[values.lt(0)].sum()) if not values.empty else 0.0
        row[f"{component}_loss_rate"] = float(values.lt(0).mean()) if not values.empty else np.nan
    return row


def build_segment_summary(held: pd.DataFrame) -> pd.DataFrame:
    groups = {
        "all_held_rows": held,
        "feature_ready": held[held["trend_feature_ready"]].copy(),
        "bad_window_by_next_date": held[held["in_bad_window_by_next_date"]].copy(),
        "bad_window_feature_ready": held[held["in_bad_window_by_next_date"] & held["trend_feature_ready"]].copy(),
        "outside_bad_window_feature_ready": held[~held["in_bad_window_by_next_date"] & held["trend_feature_ready"]].copy(),
    }
    return pd.DataFrame([_component_stats(frame, name) for name, frame in groups.items()])


def _condition_specs(held: pd.DataFrame) -> list[tuple[str, str, pd.Series]]:
    ready = held["trend_feature_ready"].fillna(False)
    wrong_ma20 = ready & held["signed_ma20_gap"].lt(0.0)
    wrong_ma60 = ready & held["signed_ma60_gap"].lt(0.0)
    wrong_ma20_ma60 = wrong_ma20 & wrong_ma60
    stack_broken = ready & held["signed_ma20_vs_ma60"].lt(0.0)
    ret20_negative = ready & held["signed_ret20"].lt(0.0)
    ret5_negative = ready & held["signed_ret5"].lt(0.0)
    ret5_adverse_1vol = ready & held["signed_ret5_over_vol20"].lt(-1.0)
    dd30 = held["drawdown_depth_pct"].ge(30.0)
    dd20 = held["drawdown_depth_pct"].ge(20.0)
    return [
        ("feature_ready", "Feature-ready held positions", ready),
        ("wrong_side_ma20", "Held direction wrong side of MA20", wrong_ma20),
        ("wrong_side_ma60", "Held direction wrong side of MA60", wrong_ma60),
        ("wrong_side_ma20_ma60", "Wrong side of both MA20 and MA60", wrong_ma20_ma60),
        ("ma_stack_broken", "MA20/MA60 stack broken for held direction", stack_broken),
        ("ret20_negative", "20d signed return negative", ret20_negative),
        ("ret5_negative", "5d signed return negative", ret5_negative),
        ("ret5_adverse_1vol", "5d signed return below -1x rolling abs-ret", ret5_adverse_1vol),
        ("wrong_ma20_and_ret5_negative", "Wrong MA20 and 5d adverse", wrong_ma20 & ret5_negative),
        ("stack_broken_and_ret20_negative", "MA stack broken and 20d adverse", stack_broken & ret20_negative),
        ("dd20_and_wrong_ma20", "Account DD>=20 and wrong MA20", dd20 & wrong_ma20),
        ("dd30_and_wrong_ma20", "Account DD>=30 and wrong MA20", dd30 & wrong_ma20),
        ("dd30_and_stack_broken", "Account DD>=30 and MA stack broken", dd30 & stack_broken),
    ]


def _condition_component_stats(
    held: pd.DataFrame, condition: str, label: str, mask: pd.Series, component: str, scope: str
) -> dict[str, Any]:
    selected = held[mask.fillna(False)].copy()
    total = pd.to_numeric(held[component], errors="coerce").fillna(0.0)
    total_positive = float(total[total.gt(0)].sum())
    total_negative_abs = float(-total[total.lt(0)].sum())
    if selected.empty:
        return {
            "scope": scope,
            "condition": condition,
            "label": label,
            "component": component,
            "rows": 0,
            "start_count": 0,
            "date_count": 0,
            "symbol_count": 0,
            "component_pnl_sum": 0.0,
            "negative_start_rate": np.nan,
            "negative_date_rate": np.nan,
            "loss_capture_share": 0.0,
            "gain_sacrifice_share": 0.0,
            "loss_minus_gain_share": 0.0,
            "candidate_for_proxy": False,
        }
    values = pd.to_numeric(selected[component], errors="coerce").fillna(0.0)
    by_start = selected.groupby("requested_start_month")[component].sum()
    by_date = selected.groupby("date")[component].sum()
    positive = float(values[values.gt(0)].sum())
    negative_abs = float(-values[values.lt(0)].sum())
    loss_share = negative_abs / total_negative_abs if total_negative_abs > 0 else np.nan
    gain_share = positive / total_positive if total_positive > 0 else np.nan
    negative_start_rate = float(by_start.lt(0).mean()) if len(by_start) else np.nan
    negative_date_rate = float(by_date.lt(0).mean()) if len(by_date) else np.nan
    candidate = bool(
        scope == "all"
        and len(selected) >= 120
        and len(by_start) >= 8
        and len(by_date) >= 120
        and values.sum() < 0
        and np.isfinite(loss_share)
        and np.isfinite(gain_share)
        and loss_share > gain_share * 1.5
        and negative_start_rate >= 0.60
        and negative_date_rate >= 0.55
    )
    return {
        "scope": scope,
        "condition": condition,
        "label": label,
        "component": component,
        "rows": int(len(selected)),
        "start_count": int(len(by_start)),
        "date_count": int(len(by_date)),
        "symbol_count": int(selected["vt_symbol"].nunique()),
        "negative_start_count": int(by_start.lt(0).sum()),
        "negative_start_rate": negative_start_rate,
        "negative_date_count": int(by_date.lt(0).sum()),
        "negative_date_rate": negative_date_rate,
        "component_pnl_sum": float(values.sum()),
        "positive_component_pnl_sum": positive,
        "negative_component_pnl_abs_sum": negative_abs,
        "loss_capture_share": float(loss_share),
        "gain_sacrifice_share": float(gain_share),
        "loss_minus_gain_share": float(loss_share - gain_share),
        "candidate_for_proxy": candidate,
    }


def build_condition_summary(held: pd.DataFrame, scope: str = "all") -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    data = held.copy()
    if scope == "bad_window":
        data = data[data["in_bad_window_by_next_date"]].copy()
    for condition, label, mask in _condition_specs(data):
        for component in TARGET_COMPONENTS:
            rows.append(_condition_component_stats(data, condition, label, mask, component, scope))
    summary = pd.DataFrame(rows)
    return summary.sort_values(
        ["candidate_for_proxy", "component", "loss_minus_gain_share", "component_pnl_sum"],
        ascending=[False, True, False, True],
    ).reset_index(drop=True)


def build_top_loss_days(held: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "requested_start_month",
        "date",
        "next_date",
        "vt_symbol",
        "end_pos",
        "drawdown_depth_pct",
        "in_bad_window_by_next_date",
        "signed_ret5",
        "signed_ret20",
        "signed_ma20_gap",
        "signed_ma60_gap",
        "signed_ma20_vs_ma60",
        "next_holding_pnl",
        "next_same_symbol_rebalance_net_pnl",
        "next_same_symbol_net_pnl",
    ]
    frames: list[pd.DataFrame] = []
    for component in TARGET_COMPONENTS:
        view = held[cols].copy()
        view["component"] = component
        view["component_pnl"] = view[component]
        frames.append(view.sort_values("component_pnl").head(30))
    return pd.concat(frames, ignore_index=True, sort=False)


def make_decision(segment_summary: pd.DataFrame, condition_summary: pd.DataFrame) -> dict[str, Any]:
    candidates = condition_summary[condition_summary["candidate_for_proxy"].astype(bool)].copy()
    bad = segment_summary[segment_summary["segment"].eq("bad_window_feature_ready")]
    bad_row = bad.iloc[0].to_dict() if not bad.empty else {}
    if candidates.empty:
        decision = "stage099_no_held_trend_deterioration_candidate"
        best_candidate = ""
        next_step = (
            "不进入 held-trend exit proxy；若继续，优先做更底层的真实 exit-event/持仓生命周期审计，"
            "或回到独立收益腿数据补齐。"
        )
        continue_after = "有但需换层"
        continue_reason = "持仓趋势衰减特征可解释部分坏窗口，但未形成跨起点、跨自然日稳定可交易条件。"
    else:
        best = candidates.sort_values(["loss_minus_gain_share", "negative_date_rate"], ascending=[False, False]).iloc[0]
        decision = "stage099_held_trend_deterioration_candidate_for_proxy"
        best_candidate = f"{best['component']}::{best['condition']}"
        next_step = f"只允许对 `{best_candidate}` 做一次冻结 no-lookahead 降风险 proxy；不得继续扫窗口、阈值、品种、方向。"
        continue_after = "有"
        continue_reason = "持仓趋势衰减条件出现稳定候选，但仍需 proxy/true engine 验证右尾损伤。"
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision,
        "candidate_rule_count": int(len(candidates)),
        "best_candidate": best_candidate,
        "bad_window_feature_ready_rows": int(bad_row.get("rows", 0) or 0),
        "bad_window_next_holding_pnl_sum": float(bad_row.get("next_holding_pnl_sum", 0.0) or 0.0),
        "bad_window_next_same_symbol_rebalance_net_pnl_sum": float(
            bad_row.get("next_same_symbol_rebalance_net_pnl_sum", 0.0) or 0.0
        ),
        "bad_window_next_same_symbol_net_pnl_sum": float(bad_row.get("next_same_symbol_net_pnl_sum", 0.0) or 0.0),
        "promote_to_proxy": bool(not candidates.empty),
        "promote_to_true_engine": False,
        "strategy_changed": False,
        "true_engine_run": False,
        "order_api_calls": 0,
        "ctp_connected": False,
        "next_step": next_step,
        "overfit_after": (
            "否。只用固定 20/60/120 日 EOD 趋势衰减口径做只读归因；"
            "未按品种、方向、月份、坏窗口日期或阈值搜索。"
        ),
        "continue_after": continue_after,
        "continue_reason": continue_reason,
    }


def write_report(
    segment_summary: pd.DataFrame,
    condition_summary: pd.DataFrame,
    bad_window_summary: pd.DataFrame,
    top_loss_days: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    research_rows = "\n".join(
        f"| {item['source']} | {item['url']} | {item['finding']} |" for item in EXTERNAL_RESEARCH
    )
    report = f"""# {STAGE} Held Trend Deterioration Audit

## 外部调研与判断

| source | url | finding |
| --- | --- | --- |
{research_rows}

我的判断：趋势系统的退出/减仓规则容易把正常右尾波动误杀；本阶段先做 EOD 可见趋势衰减对下一日持仓 PnL 的只读归因，不改 C9。

## Segment Summary

{_md_table(segment_summary)}

## Condition Summary

{_md_table(condition_summary, 120)}

## Bad Window Condition Summary

{_md_table(bad_window_summary, 120)}

## Top Loss Days

{_md_table(top_loss_days, 120)}

## 决策

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## 统计口径

- 样本：Stage096 的 C9/15w EOD active positions，逐半年起点 `2020-01` 到 `2026-01`，统一终点 `2026-06-30`。
- 特征：只使用 `date` 当日 EOD 以前可见的 close/MA/return，不使用 `next_date` 价格构造条件。
- 目标：下一交易日同合约 `holding_pnl`、`trading_pnl - commission - slippage`、`net_pnl`。
- 候选条件：只允许固定 20/60/120 日趋势衰减与账户 DD20/DD30 组合；本阶段不进入 true engine。

## 过拟合反思

- 运行前：否。固定窗口来自常见趋势跟随结构，不按坏窗口调参。
- 运行后：{decision['overfit_after']}

## 继续价值反思

- 运行前：有。Stage098 显示坏窗口主要来自 carryover 持仓，需要判断是否是退出太慢还是趋势正常回撤。
- 运行后：{decision['continue_after']}。{decision['continue_reason']}

## 输出

- held_panel：`{HELD_PANEL_PATH}`
- segment_summary：`{SEGMENT_SUMMARY_PATH}`
- condition_summary：`{CONDITION_SUMMARY_PATH}`
- bad_window_summary：`{BAD_WINDOW_SUMMARY_PATH}`
- top_loss_days：`{TOP_LOSS_DAYS_PATH}`
- input_audit：`{INPUT_AUDIT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def write_stage_record(
    segment_summary: pd.DataFrame,
    condition_summary: pd.DataFrame,
    bad_window_summary: pd.DataFrame,
    top_loss_days: pd.DataFrame,
    decision: dict[str, Any],
) -> Path:
    now = datetime.now()
    path = STAGES_DIR / f"{now:%Y%m%d_%H%M}_stage099_held_trend_deterioration_audit.md"
    text = f"""# Stage099 持仓趋势衰减只读审计

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{now:%Y-%m-%d %H:%M} CST
- 工作区/分支：`{ROOT}`
- 阶段性质：只读持仓趋势衰减归因；不重新跑策略
- 是否重要突破：否
- 是否触发A/B：否，本阶段不提出可合入候选

## 外部调研与判断

- 参考资料：pysystemtrade position buffering、Rob Carver dynamic trend following、Hudson & Thames meta-labeling。
- 我的判断：不能直接加退出/尾随止损扫参；应先看 EOD 可见趋势衰减能否稳定解释下一日持仓亏损。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage099_held_trend_deterioration_audit.py`
- 修改脚本：无正式交易入口修改。
- 删除脚本：无。
- 新增参数：固定审计窗口 `5/20/60/120` 与 DD20/DD30 诊断条件；不新增正式交易参数。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 输入：Stage096 positions 与 exposure panel。
- 数据区间：Stage096 的 `2020-01` 至 `2026-01` 逐半年起点，统一终点 `2026-06-30`。
- 引擎口径：本阶段不重新跑引擎。
- 审计口径：EOD trend feature -> next-day same-symbol component PnL；不做产品/方向/日期黑名单。

## Segment Summary

{_md_table(segment_summary)}

## Condition Summary

{_md_table(condition_summary, 120)}

## Bad Window Condition Summary

{_md_table(bad_window_summary, 120)}

## Top Loss Days

{_md_table(top_loss_days, 120)}

## 结论

- 本阶段结论：`{decision['decision']}`。
- 候选数：`{decision['candidate_rule_count']}`。
- 最优候选：`{decision['best_candidate']}`。
- bad-window feature-ready rows：`{decision['bad_window_feature_ready_rows']}`。
- bad-window next holding PnL：`{decision['bad_window_next_holding_pnl_sum']:.4f}`。
- bad-window next rebalance net PnL：`{decision['bad_window_next_same_symbol_rebalance_net_pnl_sum']:.4f}`。
- bad-window next same-symbol net PnL：`{decision['bad_window_next_same_symbol_net_pnl_sum']:.4f}`。
- 是否进入 proxy：`{decision['promote_to_proxy']}`。
- 是否进入 true engine：`{decision['promote_to_true_engine']}`。
- 下一步：{decision['next_step']}

## 回测记录字段

- 期末权益/总收益/最大回撤/Sharpe/总滑点/总交易次数/胜率：本阶段不是新策略曲线，不新增这些汇总。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：{decision['overfit_after']}

## 继续价值反思

- 运行前判断：有。
- 运行后判断：{decision['continue_after']}
- 原因：{decision['continue_reason']}

## 合入建议

- 是否更新本线 `LINE.md`：否，等独立 agent 审查。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段无重要突破。
"""
    path.write_text(text, encoding="utf-8")
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    positions, panel = load_inputs()
    held = build_held_panel(positions, panel)
    segment_summary = build_segment_summary(held)
    condition_summary = build_condition_summary(held, "all")
    bad_window_summary = build_condition_summary(held, "bad_window")
    top_loss_days = build_top_loss_days(held)
    input_audit = _input_audit([POSITIONS_PATH, PANEL_PATH])
    decision = make_decision(segment_summary, condition_summary)

    held.to_csv(HELD_PANEL_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    segment_summary.to_csv(SEGMENT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    condition_summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    bad_window_summary.to_csv(BAD_WINDOW_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    top_loss_days.to_csv(TOP_LOSS_DAYS_PATH, index=False, encoding="utf-8-sig")
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(segment_summary, condition_summary, bad_window_summary, top_loss_days, decision)
    stage_path = write_stage_record(segment_summary, condition_summary, bad_window_summary, top_loss_days, decision)
    print(json.dumps(_json_safe({"decision": decision, "stage_path": stage_path, "report_path": REPORT_PATH}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
