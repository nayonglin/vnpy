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
STAGE = "Stage097"
MODEL_TAG = "stage097_position_concentration_refined_causality_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage097_position_concentration_refined_causality_audit"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage097_position_concentration_refined_causality_audit"
STAGES_DIR = LINE_DIR / "stages"

STAGE096_OUT = LINE_DIR / "outputs" / "stage096_position_concentration_predictive_audit"
STAGE096_PREFIX = "rebuilt_c9_v2_stage096_position_concentration_predictive_audit"
STAGE096_TAG = "stage096_position_concentration_predictive_audit_v1"
STAGE096_POSITIONS = STAGE096_OUT / f"{STAGE096_PREFIX}_positions_{STAGE096_TAG}.csv.gz"
STAGE096_PANEL = STAGE096_OUT / f"{STAGE096_PREFIX}_exposure_panel_{STAGE096_TAG}.csv.gz"
STAGE096_DECISION = STAGE096_OUT / f"{STAGE096_PREFIX}_decision_{STAGE096_TAG}.json"

ENRICHED_PANEL_PATH = OUT / f"{OUTPUT_PREFIX}_enriched_panel_{MODEL_TAG}.csv.gz"
CONDITION_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_condition_summary_{MODEL_TAG}.csv"
BAD_WINDOW_PATH = OUT / f"{OUTPUT_PREFIX}_bad_window_nextdate_decomposition_{MODEL_TAG}.csv"
TARGET_DECOMP_PATH = OUT / f"{OUTPUT_PREFIX}_target_decomposition_summary_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

BAD_WINDOW_START = pd.Timestamp("2022-07-15")
BAD_WINDOW_END = pd.Timestamp("2023-07-05")
BOOTSTRAP_SEED = 20260705
BOOTSTRAP_ITERATIONS = 500

SOURCE_FILES = [STAGE096_POSITIONS, STAGE096_PANEL, STAGE096_DECISION]

EXTERNAL_RESEARCH = [
    {
        "source": "Freqtrade lookahead-analysis documentation",
        "url": "https://www.freqtrade.io/en/stable/lookahead-analysis/",
        "finding": "Lookahead bias is easy to introduce and hard to detect; validation should stress whether entries/exits move when future information is removed.",
    },
    {
        "source": "pysystemtrade backtesting documentation",
        "url": "https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md",
        "finding": "System evaluation should separate account curve, instrument/rule contribution and portfolio construction instead of reading one aggregate curve as proof.",
    },
    {
        "source": "Hudson & Thames backtest tutorial repository",
        "url": "https://github.com/hudson-and-thames/backtest_tutorial",
        "finding": "Backtest methodology and transaction costs should be explicit; vectorized shortcuts need careful timing and cost treatment.",
    },
]

TARGET_COLUMNS = [
    "next_net_pnl",
    "next_continuation_net_pnl",
    "next_noncontinuation_net_pnl",
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


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not STAGE096_POSITIONS.exists() or not STAGE096_PANEL.exists():
        raise FileNotFoundError("Stage096 outputs are required before Stage097")
    positions = pd.read_csv(STAGE096_POSITIONS, encoding="utf-8-sig")
    panel = pd.read_csv(STAGE096_PANEL, encoding="utf-8-sig")
    positions["date"] = pd.to_datetime(positions["date"], errors="coerce").dt.normalize()
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce").dt.normalize()
    panel["next_date"] = pd.to_datetime(panel["next_date"], errors="coerce").dt.normalize()
    positions["requested_start_month"] = positions["requested_start_month"].astype(str)
    panel["requested_start_month"] = panel["requested_start_month"].astype(str)
    for column in [
        "start_pos",
        "end_pos",
        "pos_change",
        "holding_pnl",
        "trading_pnl",
        "net_pnl",
        "commission",
        "slippage",
        "trade_count",
    ]:
        positions[column] = pd.to_numeric(positions.get(column, 0.0), errors="coerce").fillna(0.0)
    for column in [
        "next_net_pnl",
        "active_contract_count",
        "active_product_count",
        "top1_product_margin_share",
        "top2_product_margin_share",
        "product_margin_hhi",
        "top_product_direction_margin_share",
        "direction_dominance_margin_share",
        "dominant_direction_product_count",
        "broker10_margin_to_equity_pct",
        "drawdown_depth_pct",
    ]:
        panel[column] = pd.to_numeric(panel.get(column, 0.0), errors="coerce").fillna(0.0)
    return positions.dropna(subset=["date"]), panel.dropna(subset=["date", "next_date"]).copy()


def attach_continuation_targets(positions: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    active = positions[positions["end_pos"].abs().gt(1e-9)][["requested_start_month", "date", "vt_symbol"]].copy()
    active = active.drop_duplicates()
    active_next = active.merge(
        panel[["requested_start_month", "date", "next_date"]],
        on=["requested_start_month", "date"],
        how="inner",
    )
    next_positions = positions[
        [
            "requested_start_month",
            "date",
            "vt_symbol",
            "net_pnl",
            "holding_pnl",
            "trading_pnl",
            "commission",
            "slippage",
            "trade_count",
        ]
    ].rename(
        columns={
            "date": "next_date",
            "net_pnl": "continuation_net_pnl",
            "holding_pnl": "continuation_holding_pnl",
            "trading_pnl": "continuation_trading_pnl",
            "commission": "continuation_commission",
            "slippage": "continuation_slippage",
            "trade_count": "continuation_trade_count",
        }
    )
    joined = active_next.merge(
        next_positions,
        on=["requested_start_month", "next_date", "vt_symbol"],
        how="left",
    )
    for column in [
        "continuation_net_pnl",
        "continuation_holding_pnl",
        "continuation_trading_pnl",
        "continuation_commission",
        "continuation_slippage",
        "continuation_trade_count",
    ]:
        joined[column] = pd.to_numeric(joined.get(column, 0.0), errors="coerce").fillna(0.0)
    continuation = (
        joined.groupby(["requested_start_month", "date"], as_index=False)
        .agg(
            next_continuation_net_pnl=("continuation_net_pnl", "sum"),
            next_continuation_holding_pnl=("continuation_holding_pnl", "sum"),
            next_continuation_trading_pnl=("continuation_trading_pnl", "sum"),
            next_continuation_commission=("continuation_commission", "sum"),
            next_continuation_slippage=("continuation_slippage", "sum"),
            next_continuation_trade_count=("continuation_trade_count", "sum"),
            continuation_symbol_count=("vt_symbol", "nunique"),
        )
        .copy()
    )
    enriched = panel.merge(continuation, on=["requested_start_month", "date"], how="left")
    for column in [
        "next_continuation_net_pnl",
        "next_continuation_holding_pnl",
        "next_continuation_trading_pnl",
        "next_continuation_commission",
        "next_continuation_slippage",
        "next_continuation_trade_count",
        "continuation_symbol_count",
    ]:
        enriched[column] = pd.to_numeric(enriched.get(column, 0.0), errors="coerce").fillna(0.0)
    enriched["next_noncontinuation_net_pnl"] = enriched["next_net_pnl"] - enriched["next_continuation_net_pnl"]
    enriched["in_bad_window_by_next_date"] = enriched["next_date"].between(BAD_WINDOW_START, BAD_WINDOW_END)
    enriched["eod_active"] = enriched["active_contract_count"].gt(0)
    return enriched


def condition_specs(panel: pd.DataFrame) -> list[tuple[str, str, pd.Series]]:
    active = panel["active_contract_count"].gt(0)
    dd20 = panel["drawdown_depth_pct"].ge(20.0)
    dd30 = panel["drawdown_depth_pct"].ge(30.0)
    one_product = active & panel["active_product_count"].eq(1)
    multi_product = active & panel["active_product_count"].ge(2)
    single_direction = active & panel["direction_dominance_margin_share"].ge(0.999999)
    top1_ge80 = active & panel["top1_product_margin_share"].ge(0.80)
    top2_ge90 = active & panel["top2_product_margin_share"].ge(0.90)
    broker50 = panel["broker10_margin_to_equity_pct"].ge(50.0)
    broker70 = panel["broker10_margin_to_equity_pct"].ge(70.0)
    return [
        ("eod_active", "EOD has any active position", active),
        ("eod_flat", "EOD has no active position", ~active),
        ("single_product_active", "EOD active in exactly one product", one_product),
        ("multi_product_active", "EOD active in two or more products", multi_product),
        ("single_direction_active", "EOD all active margin in one direction", single_direction),
        ("top1_share_ge80_active", "EOD top1 product margin share >=80%", top1_ge80),
        ("top2_share_ge90_active", "EOD top2 product margin share >=90%", top2_ge90),
        ("broker10_ge50", "Broker10 margin/equity >=50%", broker50),
        ("broker10_ge70", "Broker10 margin/equity >=70%", broker70),
        ("dd20", "Current drawdown >=20%", dd20),
        ("dd30", "Current drawdown >=30%", dd30),
        ("active_and_dd20", "EOD active and DD>=20%", active & dd20),
        ("active_and_dd30", "EOD active and DD>=30%", active & dd30),
        ("single_product_and_dd20", "Single product and DD>=20%", one_product & dd20),
        ("single_product_and_dd30", "Single product and DD>=30%", one_product & dd30),
        ("top1_ge80_and_dd20", "Top1 share>=80% and DD>=20%", top1_ge80 & dd20),
        ("top1_ge80_and_dd30", "Top1 share>=80% and DD>=30%", top1_ge80 & dd30),
        ("single_direction_and_dd20", "Single direction and DD>=20%", single_direction & dd20),
        ("single_direction_and_dd30", "Single direction and DD>=30%", single_direction & dd30),
        ("broker50_and_dd20", "Broker10>=50% and DD>=20%", broker50 & dd20),
        ("broker70_and_dd20", "Broker10>=70% and DD>=20%", broker70 & dd20),
    ]


def _bootstrap_date_mean(date_pnl: pd.Series) -> tuple[float, float, float]:
    values = pd.to_numeric(date_pnl, errors="coerce").dropna().to_numpy(dtype=float)
    if len(values) == 0:
        return (np.nan, np.nan, np.nan)
    if len(values) == 1:
        return (float(values[0]), float(values[0]), float(values[0]))
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    means = np.empty(BOOTSTRAP_ITERATIONS, dtype=float)
    for idx in range(BOOTSTRAP_ITERATIONS):
        sample = rng.choice(values, size=len(values), replace=True)
        means[idx] = float(np.mean(sample))
    p05, p50, p95 = np.quantile(means, [0.05, 0.50, 0.95])
    return float(p05), float(p50), float(p95)


def _condition_stats(panel: pd.DataFrame, target_col: str, condition: str, label: str, mask: pd.Series) -> dict[str, Any]:
    selected = panel[mask.fillna(False)].copy()
    target = pd.to_numeric(panel[target_col], errors="coerce").fillna(0.0)
    total_positive = float(target[target.gt(0.0)].sum())
    total_negative_abs = float(-target[target.lt(0.0)].sum())
    if selected.empty:
        return {
            "target_col": target_col,
            "condition": condition,
            "label": label,
            "rows": 0,
            "row_share": 0.0,
            "start_count": 0,
            "date_count": 0,
            "negative_start_count": 0,
            "negative_start_rate": np.nan,
            "negative_date_count": 0,
            "negative_date_rate": np.nan,
            "target_pnl_sum": 0.0,
            "positive_target_pnl_sum": 0.0,
            "negative_target_pnl_abs_sum": 0.0,
            "loss_capture_share": 0.0,
            "gain_sacrifice_share": 0.0,
            "loss_minus_gain_share": 0.0,
            "bootstrap_date_mean_p05": np.nan,
            "bootstrap_date_mean_p50": np.nan,
            "bootstrap_date_mean_p95": np.nan,
            "candidate_for_proxy": False,
        }
    selected_target = pd.to_numeric(selected[target_col], errors="coerce").fillna(0.0)
    positive = float(selected_target[selected_target.gt(0.0)].sum())
    negative_abs = float(-selected_target[selected_target.lt(0.0)].sum())
    by_start = selected.groupby("requested_start_month")[target_col].sum()
    by_date = selected.groupby("date")[target_col].sum()
    start_count = int(by_start.size)
    date_count = int(by_date.size)
    negative_start_count = int(by_start.lt(0.0).sum())
    negative_date_count = int(by_date.lt(0.0).sum())
    loss_share = negative_abs / total_negative_abs if total_negative_abs > 0 else np.nan
    gain_share = positive / total_positive if total_positive > 0 else np.nan
    p05, p50, p95 = _bootstrap_date_mean(by_date)
    candidate = bool(
        len(selected) >= 60
        and start_count >= 8
        and date_count >= 80
        and float(selected_target.sum()) < 0.0
        and np.isfinite(loss_share)
        and np.isfinite(gain_share)
        and loss_share > gain_share * 1.5
        and (negative_start_count / start_count if start_count else 0.0) >= 0.60
        and (negative_date_count / date_count if date_count else 0.0) >= 0.55
        and np.isfinite(p95)
        and p95 < 0.0
    )
    return {
        "target_col": target_col,
        "condition": condition,
        "label": label,
        "rows": int(len(selected)),
        "row_share": float(len(selected) / len(panel)),
        "start_count": start_count,
        "date_count": date_count,
        "negative_start_count": negative_start_count,
        "negative_start_rate": float(negative_start_count / start_count) if start_count else np.nan,
        "negative_date_count": negative_date_count,
        "negative_date_rate": float(negative_date_count / date_count) if date_count else np.nan,
        "target_pnl_sum": float(selected_target.sum()),
        "positive_target_pnl_sum": positive,
        "negative_target_pnl_abs_sum": negative_abs,
        "loss_capture_share": float(loss_share),
        "gain_sacrifice_share": float(gain_share),
        "loss_minus_gain_share": float(loss_share - gain_share),
        "bootstrap_date_mean_p05": p05,
        "bootstrap_date_mean_p50": p50,
        "bootstrap_date_mean_p95": p95,
        "candidate_for_proxy": candidate,
    }


def build_condition_summary(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    specs = condition_specs(panel)
    for target_col in TARGET_COLUMNS:
        for condition, label, mask in specs:
            rows.append(_condition_stats(panel, target_col, condition, label, mask))
    summary = pd.DataFrame(rows)
    return summary.sort_values(
        ["candidate_for_proxy", "target_col", "loss_minus_gain_share", "target_pnl_sum"],
        ascending=[False, True, False, True],
    ).reset_index(drop=True)


def build_bad_window_summary(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for start_month, group in panel.groupby("requested_start_month", sort=True):
        for active_state, subset in [
            ("all_rows", group),
            ("eod_active_only", group[group["eod_active"]].copy()),
            ("eod_flat_only", group[~group["eod_active"]].copy()),
        ]:
            bad = subset[subset["in_bad_window_by_next_date"]].copy()
            outside = subset[~subset["in_bad_window_by_next_date"]].copy()
            row: dict[str, Any] = {
                "requested_start_month": start_month,
                "active_state": active_state,
                "bad_rows": int(len(bad)),
                "outside_rows": int(len(outside)),
                "bad_loss_rate_total_target": float(bad["next_net_pnl"].lt(0.0).mean()) if not bad.empty else np.nan,
                "outside_loss_rate_total_target": float(outside["next_net_pnl"].lt(0.0).mean()) if not outside.empty else np.nan,
            }
            for target_col in TARGET_COLUMNS:
                row[f"bad_{target_col}_sum"] = float(bad[target_col].sum()) if not bad.empty else 0.0
                row[f"outside_{target_col}_sum"] = float(outside[target_col].sum()) if not outside.empty else 0.0
            rows.append(row)
    return pd.DataFrame(rows)


def build_target_decomposition_summary(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    groups = {
        "all_rows": panel,
        "eod_active_only": panel[panel["eod_active"]].copy(),
        "eod_flat_only": panel[~panel["eod_active"]].copy(),
        "bad_window_by_next_date": panel[panel["in_bad_window_by_next_date"]].copy(),
        "bad_window_active_by_next_date": panel[panel["in_bad_window_by_next_date"] & panel["eod_active"]].copy(),
        "bad_window_flat_by_next_date": panel[panel["in_bad_window_by_next_date"] & ~panel["eod_active"]].copy(),
    }
    for name, frame in groups.items():
        row: dict[str, Any] = {
            "segment": name,
            "rows": int(len(frame)),
            "start_count": int(frame["requested_start_month"].nunique()) if not frame.empty else 0,
            "date_count": int(frame["date"].nunique()) if not frame.empty else 0,
        }
        for target_col in TARGET_COLUMNS:
            values = pd.to_numeric(frame[target_col], errors="coerce").fillna(0.0) if not frame.empty else pd.Series(dtype=float)
            row[f"{target_col}_sum"] = float(values.sum()) if not values.empty else 0.0
            row[f"{target_col}_positive_sum"] = float(values[values.gt(0.0)].sum()) if not values.empty else 0.0
            row[f"{target_col}_negative_abs_sum"] = float(-values[values.lt(0.0)].sum()) if not values.empty else 0.0
            row[f"{target_col}_loss_rate"] = float(values.lt(0.0).mean()) if not values.empty else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def make_decision(condition_summary: pd.DataFrame, decomp: pd.DataFrame) -> dict[str, Any]:
    candidate_targets = ["next_net_pnl", "next_continuation_net_pnl"]
    candidates = condition_summary[
        condition_summary["candidate_for_proxy"].astype(bool)
        & condition_summary["target_col"].isin(candidate_targets)
    ].copy()
    if candidates.empty:
        decision = "stage097_no_discrete_concentration_or_continuation_candidate"
        best_candidate = ""
        next_step = "不进入 concentration proxy；停止 EOD 集中度 gate 救参，转向独立收益腿数据补齐或入场/日内新交易因果归因。"
        continue_after = "有但需换层"
        continue_reason = "EOD 集中度和 continuation PnL 分解仍没有形成稳定候选；继续扫阈值会过拟合。"
    else:
        best = candidates.sort_values(["loss_minus_gain_share", "negative_date_rate"], ascending=[False, False]).iloc[0]
        decision = "stage097_discrete_concentration_candidate_for_proxy"
        best_candidate = f"{best['target_col']}::{best['condition']}"
        next_step = f"只允许对 `{best_candidate}` 做一次冻结 no-lookahead proxy；不得扫阈值、产品、方向、日期。"
        continue_after = "有"
        continue_reason = "离散条件经日期聚类和 continuation target 仍有候选，但还不是 true engine 证据。"
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision,
        "candidate_rule_count": int(len(candidates)),
        "best_candidate": best_candidate,
        "condition_rows": int(len(condition_summary)),
        "target_decomposition_rows": int(len(decomp)),
        "promote_to_true_engine": False,
        "strategy_changed": False,
        "true_engine_run": False,
        "order_api_calls": 0,
        "ctp_connected": False,
        "next_step": next_step,
        "overfit_after": "否。只修正 Stage096 审查指出的口径，用离散规则、next_date 窗口和自然日期聚类；没有新增可调参数搜索。",
        "continue_after": continue_after,
        "continue_reason": continue_reason,
    }


def write_report(
    condition_summary: pd.DataFrame,
    bad_window: pd.DataFrame,
    decomp: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    research_rows = "\n".join(
        f"| {item['source']} | {item['url']} | {item['finding']} |" for item in EXTERNAL_RESEARCH
    )
    report = f"""# {STAGE} Position Concentration Refined Causality Audit

## 外部调研与判断

| source | url | finding |
| --- | --- | --- |
{research_rows}

我的判断：Stage096 的 no-candidate 成立，但审查指出 EOD 持仓、全样本分位和重复日期会限制外推。本阶段只做冻结口径修正：离散状态、`next_date` bad window、自然日期聚类 bootstrap、next-day PnL 拆成 continuation 与 non-continuation。

## Condition Summary

{_md_table(condition_summary, 120)}

## Target Decomposition

{_md_table(decomp)}

## Bad Window Next-Date Decomposition

{_md_table(bad_window, 80)}

## 决策

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## 统计口径

- `next_continuation_net_pnl`：前一日 EOD 已持有的合约，在下一交易日贡献的净 PnL。
- `next_noncontinuation_net_pnl`：下一日总净 PnL 减去 continuation PnL，主要代表新开仓/非前日持仓相关 PnL。
- 候选必须同时满足跨起点、跨自然日期、loss capture/gain sacrifice、bootstrap 日期均值上界为负等门槛。
- 本阶段复用 Stage096 outputs，不重新跑策略，不连接 CTP，不调用订单 API。

## 过拟合反思

- 运行前：否。只修正已知统计口径，不新增参数搜索。
- 运行后：{decision['overfit_after']}

## 继续价值反思

- 运行前：有。Stage096 的 no-candidate 需要避免被统计口径误读。
- 运行后：{decision['continue_after']}。{decision['continue_reason']}

## 输出

- enriched_panel：`{ENRICHED_PANEL_PATH}`
- condition_summary：`{CONDITION_SUMMARY_PATH}`
- bad_window_nextdate_decomposition：`{BAD_WINDOW_PATH}`
- target_decomposition_summary：`{TARGET_DECOMP_PATH}`
- input_audit：`{INPUT_AUDIT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def write_stage_record(
    condition_summary: pd.DataFrame,
    bad_window: pd.DataFrame,
    decomp: pd.DataFrame,
    decision: dict[str, Any],
) -> Path:
    now = datetime.now()
    stage_path = STAGES_DIR / f"{now:%Y%m%d_%H%M}_stage097_position_concentration_refined_causality_audit.md"
    text = f"""# Stage097 持仓集中度因果口径修正审计

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{now:%Y-%m-%d %H:%M} CST
- 工作区/分支：`{ROOT}`
- 阶段性质：只读统计口径修正；不重新跑策略
- 是否重要突破：否
- 是否触发A/B：否，本阶段不提出可合入候选

## 外部调研与判断

- 参考资料：Freqtrade lookahead-analysis、pysystemtrade backtesting、Hudson & Thames backtest tutorial。
- 我的判断：必须修正 Stage096 审查指出的全样本分位、重复日期和 EOD 对 next-day 总 PnL 的解释边界；但不能借修正口径继续扫阈值。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage097_position_concentration_refined_causality_audit.py`
- 修改脚本：无正式交易入口修改。
- 删除脚本：无。
- 新增参数：固定离散状态条件、自然日期聚类 bootstrap、`next_date` bad window；不新增正式交易参数。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 输入：Stage096 positions 与 exposure panel。
- 数据区间：Stage096 的 `2020-01` 至 `2026-01` 逐半年起点，统一终点 `2026-06-30`。
- 引擎口径：本阶段不重新跑引擎。
- 审计口径：当日 EOD 暴露预测下一交易日 PnL，并拆成 continuation / non-continuation。

## Condition Summary

{_md_table(condition_summary, 120)}

## Target Decomposition

{_md_table(decomp)}

## Bad Window Next-Date Decomposition

{_md_table(bad_window, 80)}

## 结论

- 本阶段结论：`{decision['decision']}`。
- 候选数：`{decision['candidate_rule_count']}`。
- 最优候选：`{decision['best_candidate']}`。
- 是否进入 true engine：`{decision['promote_to_true_engine']}`。
- 下一步：{decision['next_step']}

## 回测记录字段

- 期末权益/总收益/最大回撤/Sharpe/总滑点/总交易次数/胜率：本阶段不是新策略曲线，不新增这些汇总。
- condition rows：`{decision['condition_rows']}`。

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
    stage_path.write_text(text, encoding="utf-8")
    return stage_path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    positions, panel = load_inputs()
    enriched = attach_continuation_targets(positions, panel)
    condition_summary = build_condition_summary(enriched)
    bad_window = build_bad_window_summary(enriched)
    decomp = build_target_decomposition_summary(enriched)
    input_audit = _input_audit(SOURCE_FILES)
    decision = make_decision(condition_summary, decomp)

    enriched.to_csv(ENRICHED_PANEL_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    condition_summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    bad_window.to_csv(BAD_WINDOW_PATH, index=False, encoding="utf-8-sig")
    decomp.to_csv(TARGET_DECOMP_PATH, index=False, encoding="utf-8-sig")
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(condition_summary, bad_window, decomp, decision)
    stage_path = write_stage_record(condition_summary, bad_window, decomp, decision)
    print(json.dumps(_json_safe({"decision": decision, "stage_path": stage_path, "report_path": REPORT_PATH}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
