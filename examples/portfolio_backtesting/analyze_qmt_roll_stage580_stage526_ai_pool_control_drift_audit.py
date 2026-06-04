from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage516_margin_aware_sizing_frontier as s516  # noqa: E402
import analyze_qmt_roll_stage577_stage526_failure_memory_micro_sizing_replay as s577  # noqa: E402


MODEL_TAG = "stage580_stage526_ai_pool_control_drift_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage580_stage526_ai_pool_control_drift_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

OLD_STAGE526_TAG = "stage526_productcap25_breadth_frontier_v1"
OLD_STAGE526_PREFIX = "qmt_roll_stage526_productcap25_breadth_frontier"
STAGE577_TAG = "stage577_stage526_failure_memory_micro_sizing_replay_v1"
STAGE577_PREFIX = "qmt_roll_stage577_stage526_failure_memory_micro_sizing_replay"

OLD_SUMMARY_PATH = OUTPUT_DIR / f"{OLD_STAGE526_PREFIX}_summary_{OLD_STAGE526_TAG}.csv"
OLD_DAILY_PATH = OUTPUT_DIR / f"{OLD_STAGE526_PREFIX}_margin_daily_{OLD_STAGE526_TAG}.csv"
OLD_POSITIONS_PATH = OUTPUT_DIR / f"{OLD_STAGE526_PREFIX}_positions_{OLD_STAGE526_TAG}.csv"
PREPATCH_SUMMARY_PATH = OUTPUT_DIR / f"{STAGE577_PREFIX}_summary_{STAGE577_TAG}.csv"
PREPATCH_DAILY_PATH = OUTPUT_DIR / f"{STAGE577_PREFIX}_margin_daily_{STAGE577_TAG}.csv"
PREPATCH_SNAPSHOT_PATH = OUTPUT_DIR / f"{STAGE577_PREFIX}_entry_candidate_snapshots_{STAGE577_TAG}.csv"

REPAIRED_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_repaired_summary_{MODEL_TAG}.csv"
REPAIRED_COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_repaired_cost_{MODEL_TAG}.csv"
REPAIRED_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_repaired_margin_daily_{MODEL_TAG}.csv"
REPAIRED_POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_repaired_positions_{MODEL_TAG}.csv"
REPAIRED_SNAPSHOT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_repaired_entry_candidate_snapshots_{MODEL_TAG}.csv"
COMPARE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_compare_{MODEL_TAG}.csv"
DAILY_DIFF_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_diff_{MODEL_TAG}.csv"
AI_EVENT_COMPARE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_event_compare_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _run_repaired_control() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metadata = s577.s513._metadata()
    identity_map = s577.s519._product_identity_cluster_map(metadata)
    pc25 = s577.s519._product_cap_overrides(0.25, identity_map)
    spec = s577.VariantSpec(
        "stage526_repaired_control",
        "Stage526 repaired control after AI-pool eval-date fix",
        0.80,
        {**pc25, "max_concurrent_positions": 4},
        "恢复 AI product pool eval_date 完成后下一交易日生效语义。",
    )
    daily, positions, snapshots = s577._run_variant(spec, metadata)
    margin_daily, _product_margin = s577.s513._position_margin(positions, metadata)
    xsmom_daily = s577.s513._load_xsmom_daily()
    combo_daily = s577.s517._combine_daily(daily, margin_daily, xsmom_daily)
    summary, cost = s577._summary_and_cost(combo_daily, (spec,))
    return combo_daily, positions, snapshots, summary, cost


def _load_summary(path: Path, variant: str, label: str) -> dict[str, Any]:
    frame = pd.read_csv(path, encoding="utf-8-sig")
    row = frame[frame["variant"].astype(str).eq(variant)].iloc[0].to_dict()
    row["source"] = label
    return row


def _standardize_daily(path: Path, variant: str, source: str) -> pd.DataFrame:
    frame = pd.read_csv(path, encoding="utf-8-sig")
    frame = frame[frame["variant"].astype(str).eq(variant)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["source"] = source
    for column in ["net_pnl", "total_net_pnl", "slippage", "total_slippage", "account_equity", "trade_count"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date"]).sort_values("date").copy()


def _summary_compare(repaired_summary: pd.DataFrame) -> pd.DataFrame:
    rows = [
        _load_summary(OLD_SUMMARY_PATH, "r080_pc25_maxpos4", "old_stage526_authority"),
        _load_summary(PREPATCH_SUMMARY_PATH, "stage526_control", "stage577_prepatch_inclusive_eval_date"),
    ]
    repaired = repaired_summary.iloc[0].to_dict()
    repaired["source"] = "stage580_repaired_replay"
    rows.append(repaired)
    compare = pd.DataFrame(rows)
    keep = [
        "source",
        "variant",
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "ulcer_pct",
        "sharpe",
        "max_broker10_margin_to_equity_pct",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
    ]
    return compare[[column for column in keep if column in compare.columns]].copy()


def _daily_diff(repaired_daily: pd.DataFrame) -> pd.DataFrame:
    old = _standardize_daily(OLD_DAILY_PATH, "r080_pc25_maxpos4", "old")
    pre = _standardize_daily(PREPATCH_DAILY_PATH, "stage526_control", "prepatch")
    repaired = repaired_daily.copy()
    repaired["date"] = pd.to_datetime(repaired["date"], errors="coerce").dt.normalize()
    for column in ["net_pnl", "total_net_pnl", "slippage", "total_slippage", "account_equity", "trade_count"]:
        repaired[column] = pd.to_numeric(repaired.get(column, 0.0), errors="coerce").fillna(0.0)
    repaired["source"] = "repaired"
    merged = old[["date", "net_pnl", "total_net_pnl", "total_slippage", "account_equity", "trade_count"]].merge(
        pre[["date", "net_pnl", "total_net_pnl", "total_slippage", "account_equity", "trade_count"]],
        on="date",
        suffixes=("_old", "_prepatch"),
    ).merge(
        repaired[["date", "net_pnl", "total_net_pnl", "total_slippage", "account_equity", "trade_count"]],
        on="date",
    )
    merged.rename(
        columns={
            "net_pnl": "net_pnl_repaired",
            "total_net_pnl": "total_net_pnl_repaired",
            "total_slippage": "total_slippage_repaired",
            "account_equity": "account_equity_repaired",
            "trade_count": "trade_count_repaired",
        },
        inplace=True,
    )
    for prefix in ["net_pnl", "total_net_pnl", "total_slippage", "account_equity", "trade_count"]:
        merged[f"{prefix}_prepatch_minus_old"] = merged[f"{prefix}_prepatch"] - merged[f"{prefix}_old"]
        merged[f"{prefix}_repaired_minus_old"] = merged[f"{prefix}_repaired"] - merged[f"{prefix}_old"]
    return merged


def _ai_event_compare(repaired_snapshots: pd.DataFrame) -> pd.DataFrame:
    if not PREPATCH_SNAPSHOT_PATH.exists() or repaired_snapshots.empty:
        return pd.DataFrame()
    pre = pd.read_csv(PREPATCH_SNAPSHOT_PATH, encoding="utf-8-sig")
    pre = pre[pre["variant"].astype(str).eq("stage526_control")].copy()
    rep = repaired_snapshots.copy()
    for frame in [pre, rep]:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    keys = ["date", "product_vt_symbol", "contract_vt_symbol", "direction", "signal"]
    cols = keys + [
        "candidate_status",
        "skip_reason",
        "selected_volume",
        "ai_product_pool_entry_effective_date",
        "ai_product_pool_signal_date",
        "ai_product_pool_allowed",
        "ai_product_pool_rank",
        "ai_product_pool_top_n",
    ]
    pre_small = pre[[column for column in cols if column in pre.columns]].copy()
    rep_small = rep[[column for column in cols if column in rep.columns]].copy()
    merged = pre_small.merge(rep_small, on=keys, how="outer", suffixes=("_prepatch", "_repaired"))
    status_changed = (
        merged.get("candidate_status_prepatch", "").astype(str)
        != merged.get("candidate_status_repaired", "").astype(str)
    )
    signal_changed = (
        merged.get("ai_product_pool_signal_date_prepatch", "").astype(str)
        != merged.get("ai_product_pool_signal_date_repaired", "").astype(str)
    )
    return merged[status_changed | signal_changed].sort_values(keys).copy()


def _build_decision(compare: pd.DataFrame, daily_diff: pd.DataFrame, ai_events: pd.DataFrame) -> dict[str, Any]:
    indexed = compare.set_index("source")
    old = indexed.loc["old_stage526_authority"]
    pre = indexed.loc["stage577_prepatch_inclusive_eval_date"]
    repaired = indexed.loc["stage580_repaired_replay"]
    end_diff_repaired = float(repaired["end_equity"] - old["end_equity"])
    return_diff_repaired = float(repaired["total_return_pct"] - old["total_return_pct"])
    slip_diff_repaired = float(repaired["total_slippage"] - old["total_slippage"])
    end_diff_pre = float(pre["end_equity"] - old["end_equity"])
    exact_match = (
        abs(end_diff_repaired) < 1e-9
        and abs(return_diff_repaired) < 1e-9
        and abs(slip_diff_repaired) < 1e-9
    )
    daily_repaired_nonzero = int((daily_diff["total_net_pnl_repaired_minus_old"].abs() > 1e-9).sum())
    daily_prepatch_nonzero = int((daily_diff["total_net_pnl_prepatch_minus_old"].abs() > 1e-9).sum())
    decision = "ai_pool_eval_date_regression_repaired" if exact_match else "ai_pool_eval_date_regression_partially_repaired"
    return {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at_cst": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision,
        "root_cause": (
            "Stage256 changed AI product pool snapshot lookup from side='left' to side='right'. "
            "That made monthly eval_date snapshots tradable on the same date and drifted Stage526 control."
        ),
        "repair": "Restore side='left' so eval_date is a completed snapshot tradable after that date.",
        "summary": {
            "prepatch_end_equity_minus_old": end_diff_pre,
            "repaired_end_equity_minus_old": end_diff_repaired,
            "repaired_total_return_minus_old_pp": return_diff_repaired,
            "repaired_total_slippage_minus_old": slip_diff_repaired,
            "prepatch_daily_net_pnl_diff_days": daily_prepatch_nonzero,
            "repaired_daily_net_pnl_diff_days": daily_repaired_nonzero,
            "ai_event_changed_rows_after_repair": int(len(ai_events)),
            "exact_match_old_authority": exact_match,
        },
        "outputs": {
            "compare": str(COMPARE_PATH),
            "daily_diff": str(DAILY_DIFF_PATH),
            "ai_event_compare": str(AI_EVENT_COMPARE_PATH),
            "repaired_summary": str(REPAIRED_SUMMARY_PATH),
            "repaired_daily": str(REPAIRED_DAILY_PATH),
            "repaired_positions": str(REPAIRED_POSITIONS_PATH),
            "repaired_snapshots": str(REPAIRED_SNAPSHOT_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }


def _plot(compare: pd.DataFrame, daily_diff: pd.DataFrame) -> None:
    old = _standardize_daily(OLD_DAILY_PATH, "r080_pc25_maxpos4", "old")
    pre = _standardize_daily(PREPATCH_DAILY_PATH, "stage526_control", "prepatch")
    repaired = _standardize_daily(REPAIRED_DAILY_PATH, "stage526_repaired_control", "repaired")
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    ax_eq, ax_drift, ax_daily, ax_bar = axes.ravel()
    for frame, label, color in [
        (old, "old Stage526 authority", "#2563eb"),
        (pre, "prepatch inclusive eval_date", "#dc2626"),
        (repaired, "repaired replay", "#16a34a"),
    ]:
        ax_eq.plot(frame["date"], frame["account_equity"], label=label, linewidth=0.95, color=color)
    ax_eq.set_title("Account equity: old vs prepatch vs repaired")
    ax_eq.grid(alpha=0.25)
    ax_eq.legend(fontsize=8)
    x = pd.to_datetime(daily_diff["date"])
    ax_drift.plot(x, daily_diff["account_equity_prepatch_minus_old"], label="prepatch - old", color="#dc2626")
    ax_drift.plot(x, daily_diff["account_equity_repaired_minus_old"], label="repaired - old", color="#16a34a")
    ax_drift.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_drift.set_title("Cumulative account drift vs old authority")
    ax_drift.grid(alpha=0.25)
    ax_drift.legend(fontsize=8)
    ax_daily.plot(x, daily_diff["total_net_pnl_prepatch_minus_old"], label="prepatch daily PnL diff", color="#dc2626", linewidth=0.8)
    ax_daily.plot(x, daily_diff["total_net_pnl_repaired_minus_old"], label="repaired daily PnL diff", color="#16a34a", linewidth=0.8)
    ax_daily.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_daily.set_title("Daily total PnL diff")
    ax_daily.grid(alpha=0.25)
    ax_daily.legend(fontsize=8)
    bar = compare.set_index("source")[["total_return_pct", "max_dd_pct", "total_slippage"]].copy()
    bar[["total_return_pct", "max_dd_pct"]].plot(kind="bar", ax=ax_bar, color=["#2563eb", "#f59e0b"])
    ax_bar.set_title("Metric comparison")
    ax_bar.grid(axis="y", alpha=0.25)
    ax_bar.tick_params(axis="x", labelrotation=20)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(compare: pd.DataFrame, daily_diff: pd.DataFrame, ai_events: pd.DataFrame, decision: dict[str, Any]) -> None:
    top_drift = daily_diff.assign(
        abs_prepatch_diff=daily_diff["total_net_pnl_prepatch_minus_old"].abs()
    ).sort_values("abs_prepatch_diff", ascending=False).head(12)
    lines = [
        "# Stage580 Stage526 AI pool control drift audit",
        "",
        f"- 生成时间：`{decision['generated_at_cst']} CST`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：控制组复现/漂移审计；不新增 alpha，不新增交易候选。",
        "",
        "## Summary Compare",
        "",
        _md_table(compare),
        "",
        "## Drift Diagnostics",
        "",
        _md_table(
            top_drift[
                [
                    "date",
                    "total_net_pnl_old",
                    "total_net_pnl_prepatch",
                    "total_net_pnl_repaired",
                    "total_net_pnl_prepatch_minus_old",
                    "total_net_pnl_repaired_minus_old",
                ]
            ],
            max_rows=12,
        ),
        "",
        "## AI Event Changes",
        "",
        _md_table(ai_events.head(20), max_rows=20),
        "",
        "## Decision",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    repaired_daily, repaired_positions, repaired_snapshots, repaired_summary, repaired_cost = _run_repaired_control()
    repaired_daily.to_csv(REPAIRED_DAILY_PATH, index=False, encoding="utf-8-sig")
    repaired_positions.to_csv(REPAIRED_POSITIONS_PATH, index=False, encoding="utf-8-sig")
    repaired_snapshots.to_csv(REPAIRED_SNAPSHOT_PATH, index=False, encoding="utf-8-sig")
    repaired_summary.to_csv(REPAIRED_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    repaired_cost.to_csv(REPAIRED_COST_PATH, index=False, encoding="utf-8-sig")

    compare = _summary_compare(repaired_summary)
    daily_diff = _daily_diff(repaired_daily)
    ai_events = _ai_event_compare(repaired_snapshots)
    decision = _build_decision(compare, daily_diff, ai_events)
    compare.to_csv(COMPARE_PATH, index=False, encoding="utf-8-sig")
    daily_diff.to_csv(DAILY_DIFF_PATH, index=False, encoding="utf-8-sig")
    ai_events.to_csv(AI_EVENT_COMPARE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot(compare, daily_diff)
    _write_report(compare, daily_diff, ai_events, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
