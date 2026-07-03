from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]

LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage030"
MODEL_TAG = "stage030_stage029_failure_attribution_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage030_stage029_failure_attribution"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage030_stage029_failure_attribution"
STAGE_RECORD_DIR = LINE_DIR / "stages"
BACK_LOG_PATH = PROJECT_DIR / "back_log.md"

STAGE006_OUTPUT_DIR = LINE_DIR / "outputs" / "stage006_current_quality_feature_binder"
STAGE006_PREFIX = "rebuilt_c9_stage006_current_quality_feature_binder"
STAGE006_TAG = "stage006_current_quality_feature_binder_v1"
STAGE029_OUTPUT_DIR = LINE_DIR / "outputs" / "stage029_account_injury_flat_entry_pause_engine"
STAGE029_PREFIX = "rebuilt_c9_stage029_account_injury_flat_entry_pause_engine"
STAGE029_TAG = "stage029_account_injury_flat_entry_pause_engine_v1"

BASE_SUMMARY_PATH = STAGE006_OUTPUT_DIR / f"{STAGE006_PREFIX}_summary_{STAGE006_TAG}.csv"
BASE_CURVES_PATH = STAGE006_OUTPUT_DIR / f"{STAGE006_PREFIX}_curves_{STAGE006_TAG}.csv"
BASE_CLOSED_LOTS_PATH = STAGE006_OUTPUT_DIR / f"{STAGE006_PREFIX}_closed_lots_{STAGE006_TAG}.csv"
BASE_ENTRY_CANDIDATES_PATH = STAGE006_OUTPUT_DIR / f"{STAGE006_PREFIX}_entry_candidates_{STAGE006_TAG}.csv"
STAGE029_SUMMARY_PATH = STAGE029_OUTPUT_DIR / f"{STAGE029_PREFIX}_summary_{STAGE029_TAG}.csv"
STAGE029_CURVES_PATH = STAGE029_OUTPUT_DIR / f"{STAGE029_PREFIX}_curves_{STAGE029_TAG}.csv"
STAGE029_EVENTS_PATH = STAGE029_OUTPUT_DIR / f"{STAGE029_PREFIX}_injury_pause_events_{STAGE029_TAG}.csv"
STAGE029_RETENTION_PATH = STAGE029_OUTPUT_DIR / f"{STAGE029_PREFIX}_retention_{STAGE029_TAG}.csv"
STAGE029_WORST_WINDOWS_PATH = STAGE029_OUTPUT_DIR / f"{STAGE029_PREFIX}_goal_worst_windows_{STAGE029_TAG}.csv"
STAGE029_DECISION_PATH = STAGE029_OUTPUT_DIR / f"{STAGE029_PREFIX}_decision_{STAGE029_TAG}.json"

SOURCE_DELTA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_delta_summary_{MODEL_TAG}.csv"
EVENT_ATTRIBUTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_lot_attribution_{MODEL_TAG}.csv"
TRIGGER_BUCKET_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trigger_bucket_summary_{MODEL_TAG}.csv"
MONTH_BUCKET_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_month_bucket_summary_{MODEL_TAG}.csv"
PRODUCT_DIRECTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_direction_summary_{MODEL_TAG}.csv"
WORST_WINDOW_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_worst_window_pause_coverage_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_failure_attribution_chart_{MODEL_TAG}.png"


EXTERNAL_RESEARCH_JUDGMENT = (
    "Man Group drawdown review and Rob Carver/pysystemtrade writing both warn that trend-following drawdowns "
    "are part of the right-tail return distribution; Research Affiliates' skew tradeoff paper and Concretum's "
    "position-sizing discussion support risk-budget analysis, but not mechanical drawdown filters without "
    "right-tail attribution. Stage030 therefore performs read-only failure attribution instead of a new rule."
)
OVERFIT_REFLECTION_BEFORE = (
    "否。Stage030 不产生新候选、不扫阈值、不按品种/日期修规则，只复盘 Stage029 暂停事件与 Stage006 基准路径。"
)
CONTINUE_VALUE_BEFORE = (
    "有。Stage029 已证明账户受伤标签有信息量但规则过粗，必须先解释错杀来自哪里，才能决定下一步是否还值得做交易层规则。"
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if not np.isfinite(value):
            return None
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if pd.isna(value):
        return None
    return value


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无数据_"
    shown = frame.copy()
    if max_rows is not None:
        shown = shown.head(max_rows)
    return shown.to_markdown(index=False)


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _pctize(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    sample = values.replace([np.inf, -np.inf], np.nan).dropna().abs()
    if not sample.empty and sample.quantile(0.99) <= 1.5:
        values = values * 100.0
    return values


def _load_source_delta() -> pd.DataFrame:
    base = _read_csv(BASE_SUMMARY_PATH)
    stage029 = _read_csv(STAGE029_SUMMARY_PATH)
    retention = _read_csv(STAGE029_RETENTION_PATH)

    cols = [
        "requested_start_month",
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_trade_count",
        "total_slippage",
        "max_broker10_margin_to_equity_pct",
    ]
    merged = base[cols].merge(
        stage029[cols],
        on="requested_start_month",
        how="inner",
        suffixes=("_stage006", "_stage029"),
    )
    merged = merged.merge(
        retention[["requested_start_month", "stage029_vs_base_return_ratio", "passes_80pct_retention"]],
        on="requested_start_month",
        how="left",
    )
    merged["equity_delta_stage029_minus_stage006"] = (
        pd.to_numeric(merged["end_equity_stage029"], errors="coerce")
        - pd.to_numeric(merged["end_equity_stage006"], errors="coerce")
    )
    merged["return_delta_pp_stage029_minus_stage006"] = (
        pd.to_numeric(merged["total_return_pct_stage029"], errors="coerce")
        - pd.to_numeric(merged["total_return_pct_stage006"], errors="coerce")
    )
    merged["max_dd_improvement_pp"] = (
        pd.to_numeric(merged["max_dd_pct_stage029"], errors="coerce")
        - pd.to_numeric(merged["max_dd_pct_stage006"], errors="coerce")
    )
    merged["trade_count_delta"] = (
        pd.to_numeric(merged["total_trade_count_stage029"], errors="coerce")
        - pd.to_numeric(merged["total_trade_count_stage006"], errors="coerce")
    )
    merged["slippage_delta"] = (
        pd.to_numeric(merged["total_slippage_stage029"], errors="coerce")
        - pd.to_numeric(merged["total_slippage_stage006"], errors="coerce")
    )
    return merged.sort_values("return_delta_pp_stage029_minus_stage006").reset_index(drop=True)


def _prepare_stage029_events() -> pd.DataFrame:
    events = _read_csv(STAGE029_EVENTS_PATH)
    events = events.copy()
    events["requested_start_month"] = events["requested_start_month"].astype(str)
    events["date"] = pd.to_datetime(events["date"], errors="coerce").dt.normalize()
    events["event_month"] = events["date"].dt.strftime("%Y-%m")
    events["product_vt_symbol"] = events["product_vt_symbol"].astype(str)
    events["direction"] = events["direction"].astype(str).str.lower()
    events["stage029_injury_pause_reduced_volume"] = pd.to_numeric(
        events.get("stage029_injury_pause_reduced_volume"), errors="coerce"
    ).fillna(0.0)
    events["stage029_injury_pause_drawdown_abs_pct"] = _pctize(
        events.get("stage029_injury_pause_drawdown_pct", pd.Series(dtype=float))
    )
    events["stage029_injury_pause_loss_streak"] = pd.to_numeric(
        events.get("stage029_injury_pause_loss_streak"), errors="coerce"
    ).fillna(0.0)
    drawdown_hit = pd.to_numeric(events.get("stage029_injury_pause_drawdown_hit"), errors="coerce").fillna(0).astype(int)
    streak_hit = pd.to_numeric(events.get("stage029_injury_pause_loss_streak_hit"), errors="coerce").fillna(0).astype(int)
    events["trigger_bucket"] = np.select(
        [
            drawdown_hit.eq(1) & streak_hit.eq(1),
            drawdown_hit.eq(1) & streak_hit.eq(0),
            drawdown_hit.eq(0) & streak_hit.eq(1),
        ],
        ["both_drawdown_and_loss_streak", "drawdown_only", "loss_streak_only"],
        default="other",
    )
    return events.dropna(subset=["date"]).reset_index(drop=True)


def _prepare_baseline_lots() -> pd.DataFrame:
    lots = _read_csv(BASE_CLOSED_LOTS_PATH)
    lots = lots.copy()
    lots["requested_start_month"] = lots["requested_start_month"].astype(str)
    lots["entry_date"] = pd.to_datetime(lots["entry_date"], errors="coerce").dt.normalize()
    lots["product_vt_symbol"] = lots["product"].astype(str)
    lots["direction"] = lots["direction"].astype(str).str.lower()
    lots["realized_pnl"] = pd.to_numeric(lots["realized_pnl"], errors="coerce").fillna(0.0)
    lots["volume"] = pd.to_numeric(lots["volume"], errors="coerce").fillna(0.0)
    lots["r_multiple"] = pd.to_numeric(lots["r_multiple"], errors="coerce")
    lots["winner"] = pd.to_numeric(lots.get("winner", 0), errors="coerce").fillna(0).astype(int)
    lots["big_winner"] = pd.to_numeric(lots.get("big_winner", 0), errors="coerce").fillna(0).astype(int)
    lots["ai_product_pool_rank"] = pd.to_numeric(lots.get("ai_product_pool_rank"), errors="coerce")
    lots["ai_rank_bucket"] = lots.get("ai_rank_bucket", pd.Series(["missing"] * len(lots))).astype(str)
    lots["risk_multiplier_bucket"] = lots.get("risk_multiplier_bucket", pd.Series(["missing"] * len(lots))).astype(str)
    lots["entry_context"] = lots.get("entry_context", pd.Series([""] * len(lots))).astype(str)
    return lots.dropna(subset=["entry_date"]).reset_index(drop=True)


def _prepare_baseline_candidates() -> pd.DataFrame:
    columns = [
        "candidate_index",
        "date",
        "product_vt_symbol",
        "direction",
        "entry_context",
        "candidate_status",
        "is_opened",
        "selected_volume",
        "selected_volume_ungated",
        "ai_product_pool_rank",
        "ai_product_pool_score",
        "portfolio_drawdown_pct",
        "loss_streak",
        "requested_start_month",
    ]
    available = list(_read_csv(BASE_ENTRY_CANDIDATES_PATH, nrows=0).columns)
    usecols = [column for column in columns if column in available]
    candidates = _read_csv(BASE_ENTRY_CANDIDATES_PATH, usecols=usecols, low_memory=False)
    candidates = candidates.copy()
    candidates["requested_start_month"] = candidates["requested_start_month"].astype(str)
    candidates["date"] = pd.to_datetime(candidates["date"], errors="coerce").dt.normalize()
    candidates["product_vt_symbol"] = candidates["product_vt_symbol"].astype(str)
    candidates["direction"] = candidates["direction"].astype(str).str.lower()
    candidates["entry_context"] = candidates.get("entry_context", pd.Series([""] * len(candidates))).astype(str)
    candidates["candidate_status"] = candidates.get("candidate_status", pd.Series([""] * len(candidates))).astype(str)
    for column in [
        "is_opened",
        "selected_volume",
        "selected_volume_ungated",
        "ai_product_pool_rank",
        "ai_product_pool_score",
        "portfolio_drawdown_pct",
        "loss_streak",
    ]:
        if column in candidates.columns:
            candidates[column] = pd.to_numeric(candidates[column], errors="coerce")
    return candidates.dropna(subset=["date"]).reset_index(drop=True)


def _baseline_candidate_group(candidates: pd.DataFrame) -> pd.DataFrame:
    flat = candidates[candidates["entry_context"].eq("flat_entry")].copy()
    grouped = (
        flat.groupby(["requested_start_month", "date", "product_vt_symbol", "direction"], as_index=False)
        .agg(
            baseline_candidate_rows=("candidate_index", "count"),
            baseline_opened_candidate_count=("is_opened", lambda s: pd.to_numeric(s, errors="coerce").fillna(0).sum()),
            baseline_selected_volume_sum=("selected_volume", lambda s: pd.to_numeric(s, errors="coerce").fillna(0).sum()),
            baseline_selected_volume_ungated_sum=(
                "selected_volume_ungated",
                lambda s: pd.to_numeric(s, errors="coerce").fillna(0).sum(),
            ),
            baseline_candidate_min_ai_rank=("ai_product_pool_rank", "min"),
            baseline_max_ai_score=("ai_product_pool_score", "max"),
            baseline_avg_portfolio_drawdown_pct=("portfolio_drawdown_pct", "mean"),
            baseline_max_loss_streak=("loss_streak", "max"),
            baseline_statuses=("candidate_status", lambda s: "|".join(sorted(set(map(str, s.dropna())))[:4])),
        )
    )
    return grouped


def _match_events_to_baseline_lots(
    events: pd.DataFrame,
    lots: pd.DataFrame,
    candidates: pd.DataFrame,
) -> pd.DataFrame:
    lot_group = (
        lots[lots["entry_context"].eq("flat_entry")]
        .groupby(["requested_start_month", "entry_date", "product_vt_symbol", "direction"], as_index=False)
        .agg(
            baseline_lot_count=("lot_id", "count"),
            baseline_lot_volume=("volume", "sum"),
            baseline_realized_pnl_proxy=("realized_pnl", "sum"),
            baseline_mean_r_multiple=("r_multiple", "mean"),
            baseline_winner_lot_count=("winner", "sum"),
            baseline_big_winner_lot_count=("big_winner", "sum"),
            baseline_min_ai_rank=("ai_product_pool_rank", "min"),
            baseline_ai_rank_bucket=("ai_rank_bucket", lambda s: "|".join(sorted(set(map(str, s.dropna())))[:4])),
            baseline_risk_multiplier_bucket=("risk_multiplier_bucket", lambda s: "|".join(sorted(set(map(str, s.dropna())))[:4])),
        )
    )
    matched = events.merge(
        lot_group,
        left_on=["requested_start_month", "date", "product_vt_symbol", "direction"],
        right_on=["requested_start_month", "entry_date", "product_vt_symbol", "direction"],
        how="left",
    )
    candidate_group = _baseline_candidate_group(candidates)
    matched = matched.merge(
        candidate_group,
        on=["requested_start_month", "date", "product_vt_symbol", "direction"],
        how="left",
    )
    matched["baseline_lot_matched"] = matched["baseline_lot_count"].notna().astype(int)
    matched["baseline_candidate_matched"] = matched["baseline_candidate_rows"].notna().astype(int)
    matched["baseline_candidate_opened"] = (
        pd.to_numeric(matched["baseline_opened_candidate_count"], errors="coerce").fillna(0.0) > 0.0
    ).astype(int)
    numeric_cols = [
        "baseline_lot_count",
        "baseline_lot_volume",
        "baseline_realized_pnl_proxy",
        "baseline_mean_r_multiple",
        "baseline_winner_lot_count",
        "baseline_big_winner_lot_count",
        "baseline_candidate_rows",
        "baseline_opened_candidate_count",
        "baseline_selected_volume_sum",
        "baseline_selected_volume_ungated_sum",
        "baseline_candidate_min_ai_rank",
        "baseline_max_ai_score",
        "baseline_avg_portfolio_drawdown_pct",
        "baseline_max_loss_streak",
    ]
    for column in numeric_cols:
        matched[column] = pd.to_numeric(matched[column], errors="coerce")
    matched["baseline_realized_pnl_proxy"] = matched["baseline_realized_pnl_proxy"].fillna(0.0)
    matched["baseline_was_profitable_proxy"] = (matched["baseline_realized_pnl_proxy"] > 0.0).astype(int)
    matched["baseline_was_loss_proxy"] = (matched["baseline_realized_pnl_proxy"] < 0.0).astype(int)
    matched["baseline_was_big_winner_proxy"] = (
        pd.to_numeric(matched["baseline_big_winner_lot_count"], errors="coerce").fillna(0) > 0
    ).astype(int)
    return matched


def _summarize_group(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    grouped = (
        frame.groupby(group_cols, dropna=False)
        .agg(
            pause_event_count=("date", "count"),
            reduced_volume_sum=("stage029_injury_pause_reduced_volume", "sum"),
            baseline_candidate_match_count=("baseline_candidate_matched", "sum"),
            baseline_opened_candidate_match_count=("baseline_candidate_opened", "sum"),
            baseline_selected_volume_sum=("baseline_selected_volume_sum", "sum"),
            matched_event_count=("baseline_lot_matched", "sum"),
            baseline_realized_pnl_proxy=("baseline_realized_pnl_proxy", "sum"),
            profitable_proxy_event_count=("baseline_was_profitable_proxy", "sum"),
            loss_proxy_event_count=("baseline_was_loss_proxy", "sum"),
            big_winner_proxy_event_count=("baseline_was_big_winner_proxy", "sum"),
            avg_drawdown_abs_pct=("stage029_injury_pause_drawdown_abs_pct", "mean"),
            avg_loss_streak=("stage029_injury_pause_loss_streak", "mean"),
            min_ai_rank=("baseline_min_ai_rank", "min"),
        )
        .reset_index()
    )
    grouped["matched_event_rate_pct"] = np.where(
        grouped["pause_event_count"] > 0,
        grouped["matched_event_count"] / grouped["pause_event_count"] * 100.0,
        np.nan,
    )
    grouped["baseline_candidate_match_rate_pct"] = np.where(
        grouped["pause_event_count"] > 0,
        grouped["baseline_candidate_match_count"] / grouped["pause_event_count"] * 100.0,
        np.nan,
    )
    grouped["baseline_opened_candidate_match_rate_pct"] = np.where(
        grouped["pause_event_count"] > 0,
        grouped["baseline_opened_candidate_match_count"] / grouped["pause_event_count"] * 100.0,
        np.nan,
    )
    grouped["profitable_proxy_event_rate_pct"] = np.where(
        grouped["matched_event_count"] > 0,
        grouped["profitable_proxy_event_count"] / grouped["matched_event_count"] * 100.0,
        np.nan,
    )
    return grouped


def _source_event_summary(matched: pd.DataFrame, source_delta: pd.DataFrame) -> pd.DataFrame:
    source_events = _summarize_group(matched, ["requested_start_month"])
    merged = source_delta.merge(source_events, on="requested_start_month", how="left")
    fill_cols = [
        "pause_event_count",
        "reduced_volume_sum",
        "matched_event_count",
        "baseline_candidate_match_count",
        "baseline_opened_candidate_match_count",
        "baseline_selected_volume_sum",
        "baseline_realized_pnl_proxy",
        "profitable_proxy_event_count",
        "loss_proxy_event_count",
        "big_winner_proxy_event_count",
    ]
    for column in fill_cols:
        merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0.0)
    return merged.sort_values("return_delta_pp_stage029_minus_stage006").reset_index(drop=True)


def _worst_window_coverage(events: pd.DataFrame) -> pd.DataFrame:
    windows = _read_csv(STAGE029_WORST_WINDOWS_PATH)
    windows = windows.copy()
    windows["source_start_month"] = windows["source_start_month"].astype(str)
    windows["start_date"] = pd.to_datetime(windows["start_date"], errors="coerce").dt.normalize()
    windows["end_date"] = pd.to_datetime(windows["end_date"], errors="coerce").dt.normalize()
    windows["return_pct"] = pd.to_numeric(windows["return_pct"], errors="coerce")
    windows = windows.dropna(subset=["start_date", "end_date"]).head(300).reset_index(drop=True)

    rows: list[dict[str, Any]] = []
    for rank, row in windows.iterrows():
        mask = (
            events["requested_start_month"].eq(str(row["source_start_month"]))
            & events["date"].ge(row["start_date"])
            & events["date"].le(row["end_date"])
        )
        subset = events.loc[mask]
        bucket_counts = subset["trigger_bucket"].value_counts().to_dict() if not subset.empty else {}
        rows.append(
            {
                "selected_rank": int(rank + 1),
                "source_start_month": str(row["source_start_month"]),
                "window_type": row.get("window_type", ""),
                "start_date": _date_text(row["start_date"]),
                "end_date": _date_text(row["end_date"]),
                "return_pct": float(row["return_pct"]) if pd.notna(row["return_pct"]) else np.nan,
                "paused_event_count_inside_window": int(len(subset)),
                "reduced_volume_inside_window": float(
                    pd.to_numeric(subset.get("stage029_injury_pause_reduced_volume", pd.Series(dtype=float)), errors="coerce")
                    .fillna(0.0)
                    .sum()
                ),
                "baseline_realized_pnl_proxy_inside_window": float(
                    pd.to_numeric(subset.get("baseline_realized_pnl_proxy", pd.Series(dtype=float)), errors="coerce")
                    .fillna(0.0)
                    .sum()
                ),
                "loss_streak_only_count": int(bucket_counts.get("loss_streak_only", 0)),
                "drawdown_only_count": int(bucket_counts.get("drawdown_only", 0)),
                "both_count": int(bucket_counts.get("both_drawdown_and_loss_streak", 0)),
            }
        )
    return pd.DataFrame(rows)


def _plot(source_summary: pd.DataFrame, trigger: pd.DataFrame, month: pd.DataFrame, product: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 10), constrained_layout=True)

    ax = axes[0, 0]
    plot = source_summary.sort_values("requested_start_month")
    x = np.arange(len(plot))
    ax.bar(x - 0.2, plot["total_return_pct_stage006"], width=0.4, label="Stage006", color="#94a3b8")
    ax.bar(x + 0.2, plot["total_return_pct_stage029"], width=0.4, label="Stage029", color="#ef4444")
    ax.set_xticks(x)
    ax.set_xticklabels(plot["requested_start_month"], rotation=45, ha="right", fontsize=8)
    ax.set_title("Total Return By Cold Start")
    ax.set_ylabel("return %")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[0, 1]
    trigger_plot = trigger.sort_values("baseline_realized_pnl_proxy")
    ax.barh(trigger_plot["trigger_bucket"], trigger_plot["baseline_realized_pnl_proxy"], color="#f97316")
    ax.set_title("Stage006 PnL Proxy Of Paused Events")
    ax.set_xlabel("realized pnl proxy")
    ax.grid(True, axis="x", alpha=0.25)

    ax = axes[1, 0]
    month_plot = month.sort_values("event_month").tail(36)
    ax.bar(month_plot["event_month"], month_plot["reduced_volume_sum"], color="#2563eb")
    ax.set_title("Paused Volume By Month")
    ax.set_ylabel("reduced volume")
    ax.tick_params(axis="x", rotation=60, labelsize=7)
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1, 1]
    product_plot = product.sort_values("baseline_realized_pnl_proxy", ascending=False).head(15)
    labels = product_plot["product_vt_symbol"].astype(str) + " " + product_plot["direction"].astype(str)
    ax.barh(labels[::-1], product_plot["baseline_realized_pnl_proxy"][::-1], color="#16a34a")
    ax.set_title("Top Missed Positive PnL Proxy By Product Direction")
    ax.set_xlabel("realized pnl proxy")
    ax.grid(True, axis="x", alpha=0.25)

    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _decision(
    source_summary: pd.DataFrame,
    trigger: pd.DataFrame,
    month: pd.DataFrame,
    product: pd.DataFrame,
    worst_window_coverage: pd.DataFrame,
    matched: pd.DataFrame,
) -> dict[str, Any]:
    total_events = int(len(matched))
    matched_events = int(pd.to_numeric(matched["baseline_lot_matched"], errors="coerce").fillna(0).sum())
    candidate_matches = int(pd.to_numeric(matched["baseline_candidate_matched"], errors="coerce").fillna(0).sum())
    opened_candidate_matches = int(pd.to_numeric(matched["baseline_candidate_opened"], errors="coerce").fillna(0).sum())
    baseline_selected_volume_sum = float(
        pd.to_numeric(matched["baseline_selected_volume_sum"], errors="coerce").fillna(0.0).sum()
    )
    pnl_proxy = float(pd.to_numeric(matched["baseline_realized_pnl_proxy"], errors="coerce").fillna(0.0).sum())
    positive_proxy_events = int(pd.to_numeric(matched["baseline_was_profitable_proxy"], errors="coerce").fillna(0).sum())
    negative_proxy_events = int(pd.to_numeric(matched["baseline_was_loss_proxy"], errors="coerce").fillna(0).sum())
    loss_only = trigger[trigger["trigger_bucket"].eq("loss_streak_only")]
    both = trigger[trigger["trigger_bucket"].eq("both_drawdown_and_loss_streak")]
    dd_only = trigger[trigger["trigger_bucket"].eq("drawdown_only")]
    source_loss = float(source_summary["equity_delta_stage029_minus_stage006"].sum())
    worst_top100 = worst_window_coverage.head(100)

    decision = "stage030_failure_attribution_complete_no_new_candidate"
    conclusion = (
        "Stage029 的收益失败主要是规则太早、太广地暂停 flat_entry；绝大多数暂停事件在 Stage006 基准里同日同品种方向有候选，"
        "其中大量本来会打开。closed-lot 精确收益代理样本较少，但命中样本净贡献为正，说明被暂停集合不是纯亏损集合。"
        "下一步不应继续扫阈值。"
    )
    if pnl_proxy < 0 and positive_proxy_events <= negative_proxy_events:
        conclusion = (
            "Stage029 暂停集合在闭合 lot 精确代理上偏亏，但全路径仍严重失去收益，说明后续恢复段/复利路径被切断。"
            "下一步仍不应扫阈值，应做路径交互或非交易账户层归因。"
        )

    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "decision": decision,
        "conclusion": conclusion,
        "external_research_judgment": EXTERNAL_RESEARCH_JUDGMENT,
        "overfit_reflection_before": OVERFIT_REFLECTION_BEFORE,
        "continue_value_before": CONTINUE_VALUE_BEFORE,
        "overfit_reflection_after": (
            "否。本阶段没有生成交易规则，也没有按回测结果调阈值；如果据此直接改 DD/loss_streak 阈值才是过拟合。"
        ),
        "continue_value_after": (
            "有，但方向要收窄。继续价值在识别不切断右尾的外生/质量信息，或非交易账户层资金安排；"
            "直接暂停/小手数化 flat_entry 的价值下降。"
        ),
        "metrics": {
            "source_count": int(len(source_summary)),
            "source_positive_count_stage029": int((source_summary["total_return_pct_stage029"] > 0).sum()),
            "stage029_80pct_retention_pass_count": int(source_summary["passes_80pct_retention"].fillna(0).sum()),
            "stage029_total_equity_delta_vs_stage006": source_loss,
            "pause_event_count": total_events,
            "baseline_candidate_match_count": candidate_matches,
            "baseline_candidate_match_rate_pct": float(candidate_matches / total_events * 100.0) if total_events else 0.0,
            "baseline_opened_candidate_match_count": opened_candidate_matches,
            "baseline_opened_candidate_match_rate_pct": float(opened_candidate_matches / total_events * 100.0)
            if total_events
            else 0.0,
            "baseline_selected_volume_sum_for_paused_keys": baseline_selected_volume_sum,
            "matched_event_count": matched_events,
            "matched_event_rate_pct": float(matched_events / total_events * 100.0) if total_events else 0.0,
            "baseline_realized_pnl_proxy_of_paused_events": pnl_proxy,
            "positive_proxy_event_count": positive_proxy_events,
            "negative_proxy_event_count": negative_proxy_events,
            "loss_streak_only_event_count": int(loss_only["pause_event_count"].sum()) if not loss_only.empty else 0,
            "loss_streak_only_pnl_proxy": float(loss_only["baseline_realized_pnl_proxy"].sum()) if not loss_only.empty else 0.0,
            "drawdown_only_event_count": int(dd_only["pause_event_count"].sum()) if not dd_only.empty else 0,
            "drawdown_only_pnl_proxy": float(dd_only["baseline_realized_pnl_proxy"].sum()) if not dd_only.empty else 0.0,
            "both_trigger_event_count": int(both["pause_event_count"].sum()) if not both.empty else 0,
            "both_trigger_pnl_proxy": float(both["baseline_realized_pnl_proxy"].sum()) if not both.empty else 0.0,
            "top100_worst_window_paused_event_sum": int(worst_top100["paused_event_count_inside_window"].sum())
            if not worst_top100.empty
            else 0,
            "top100_worst_window_reduced_volume_sum": float(worst_top100["reduced_volume_inside_window"].sum())
            if not worst_top100.empty
            else 0.0,
        },
        "outputs": {
            "source_delta_summary": str(SOURCE_DELTA_PATH),
            "event_lot_attribution": str(EVENT_ATTRIBUTION_PATH),
            "trigger_bucket_summary": str(TRIGGER_BUCKET_PATH),
            "month_bucket_summary": str(MONTH_BUCKET_PATH),
            "product_direction_summary": str(PRODUCT_DIRECTION_PATH),
            "worst_window_pause_coverage": str(WORST_WINDOW_COVERAGE_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _write_report(
    decision: dict[str, Any],
    source_summary: pd.DataFrame,
    trigger: pd.DataFrame,
    month: pd.DataFrame,
    product: pd.DataFrame,
    worst_window_coverage: pd.DataFrame,
) -> None:
    metrics = decision["metrics"]
    lines = [
        "# Stage030 Stage029 失败归因",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 阶段性质：只读失败归因；不生成新策略候选、不改官方 live config、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        f"- {EXTERNAL_RESEARCH_JUDGMENT}",
        "",
        "## 核心结论",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 结论：{decision['conclusion']}",
        f"- Stage029 正收益起点：`{metrics['source_positive_count_stage029']}/{metrics['source_count']}`。",
        f"- Stage029 80% 收益保留：`{metrics['stage029_80pct_retention_pass_count']}/{metrics['source_count']}`。",
        f"- Stage029 vs Stage006 期末权益差合计：`{metrics['stage029_total_equity_delta_vs_stage006']:.2f}`。",
        f"- 暂停事件：`{metrics['pause_event_count']}`，匹配 Stage006 closed-lot 事件：`{metrics['matched_event_count']}`，匹配率 `{metrics['matched_event_rate_pct']:.4f}%`。",
        f"- 匹配 Stage006 同日同品种方向 flat-entry 候选：`{metrics['baseline_candidate_match_count']}`，匹配率 `{metrics['baseline_candidate_match_rate_pct']:.4f}%`。",
        f"- 其中 Stage006 实际打开候选：`{metrics['baseline_opened_candidate_match_count']}`，打开匹配率 `{metrics['baseline_opened_candidate_match_rate_pct']:.4f}%`，对应 Stage006 selected_volume 合计 `{metrics['baseline_selected_volume_sum_for_paused_keys']:.0f}`。",
        f"- 被暂停事件的 Stage006 realized PnL 代理合计：`{metrics['baseline_realized_pnl_proxy_of_paused_events']:.2f}`。",
        f"- 正/负 PnL 代理事件：`{metrics['positive_proxy_event_count']}` / `{metrics['negative_proxy_event_count']}`。",
        f"- loss_streak_only 事件/PNL代理：`{metrics['loss_streak_only_event_count']}` / `{metrics['loss_streak_only_pnl_proxy']:.2f}`。",
        f"- drawdown_only 事件/PNL代理：`{metrics['drawdown_only_event_count']}` / `{metrics['drawdown_only_pnl_proxy']:.2f}`。",
        f"- both_trigger 事件/PNL代理：`{metrics['both_trigger_event_count']}` / `{metrics['both_trigger_pnl_proxy']:.2f}`。",
        f"- Stage029 top100 最差窗口内暂停事件：`{metrics['top100_worst_window_paused_event_sum']}`，减少手数 `{metrics['top100_worst_window_reduced_volume_sum']:.0f}`。",
        "",
        "## Source 级差异",
        "",
        _md_table(
            source_summary[
                [
                    "requested_start_month",
                    "total_return_pct_stage006",
                    "total_return_pct_stage029",
                    "return_delta_pp_stage029_minus_stage006",
                    "max_dd_improvement_pp",
                    "pause_event_count",
                    "baseline_candidate_match_count",
                    "baseline_opened_candidate_match_count",
                    "baseline_selected_volume_sum",
                    "baseline_realized_pnl_proxy",
                    "passes_80pct_retention",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## Trigger 归因",
        "",
        _md_table(trigger, max_rows=20),
        "",
        "## 暂停月份 Top20",
        "",
        _md_table(month.sort_values("reduced_volume_sum", ascending=False).head(20), max_rows=20),
        "",
        "## 产品方向 Top20",
        "",
        _md_table(product.sort_values("baseline_realized_pnl_proxy", ascending=False).head(20), max_rows=20),
        "",
        "## 最差窗口覆盖",
        "",
        _md_table(worst_window_coverage.head(30), max_rows=30),
        "",
        "## 判断",
        "",
        f"- 过拟合反思：{decision['overfit_reflection_after']}",
        f"- 继续价值反思：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    metrics = decision["metrics"]
    path = STAGE_RECORD_DIR / "20260701_1705_stage030_stage029_failure_attribution.md"
    lines = [
        "# Stage030 - Stage029 暂停规则失败归因",
        "",
        f"- 时间：`{decision['generated_at']}`",
        "- 是否重要突破版本：否；这是失败归因，不是候选策略。",
        "- 新增参数：无。",
        "- 修改参数：无。",
        "- 删除参数：无。",
        "- 新增回测结果：无新增真实回测；复用 Stage006/Stage029 已有产物做只读归因。",
        "- 修改回测结果：无。",
        "- 删除回测结果：无。",
        f"- 暂停事件：`{metrics['pause_event_count']}`。",
        f"- Stage006 同日同品种方向候选匹配：`{metrics['baseline_candidate_match_count']}`，匹配率 `{metrics['baseline_candidate_match_rate_pct']:.4f}%`。",
        f"- Stage006 实际打开候选匹配：`{metrics['baseline_opened_candidate_match_count']}`，打开匹配率 `{metrics['baseline_opened_candidate_match_rate_pct']:.4f}%`，selected_volume 合计 `{metrics['baseline_selected_volume_sum_for_paused_keys']:.0f}`。",
        f"- Stage006 closed-lot 匹配事件：`{metrics['matched_event_count']}`，匹配率 `{metrics['matched_event_rate_pct']:.4f}%`。",
        f"- 被暂停事件 Stage006 realized PnL 代理：`{metrics['baseline_realized_pnl_proxy_of_paused_events']:.2f}`。",
        f"- 正/负 PnL 代理事件：`{metrics['positive_proxy_event_count']}` / `{metrics['negative_proxy_event_count']}`。",
        f"- Stage029 正收益起点：`{metrics['source_positive_count_stage029']}/{metrics['source_count']}`。",
        f"- Stage029 80% 收益保留：`{metrics['stage029_80pct_retention_pass_count']}/{metrics['source_count']}`。",
        f"- 期末权益差合计 Stage029-Stage006：`{metrics['stage029_total_equity_delta_vs_stage006']:.2f}`。",
        "- 胜率：不新增逐笔胜率口径；使用 Stage006 closed-lot PnL 代理正负事件。",
        f"- 过拟合反思：{decision['overfit_reflection_after']}",
        f"- 继续价值反思：{decision['continue_value_after']}",
        "- 后续规划：不继续扫 DD/loss_streak 阈值；下一步只允许研究不切断右尾的外生/质量信息，或转非交易账户层资金安排。",
        "",
        "## 输出",
        "",
        f"- 报告：`{REPORT_PATH}`",
        f"- 决策：`{DECISION_PATH}`",
        f"- 图表：`{CHART_PATH}`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _append_back_log(decision: dict[str, Any], stage_record: Path) -> None:
    marker = "`futures_trend_rebuilt_c9_15w_optimization` Stage030"
    if BACK_LOG_PATH.exists() and marker in BACK_LOG_PATH.read_text(encoding="utf-8"):
        return
    metrics = decision["metrics"]
    line = (
        f"\n{datetime.now().strftime('%Y-%m-%d %H:%M CST')}：`{LINE_ID}` Stage030 完成 Stage029 暂停规则失败归因，"
        f"决策 `{decision['decision']}`。本阶段只读复用 Stage006/Stage029 产物，不改正式配置、不连接 CTP、不调用订单 API。"
        f"暂停事件 `{metrics['pause_event_count']}`，匹配 Stage006 同日候选 `{metrics['baseline_candidate_match_count']}`，"
        f"其中实际打开 `{metrics['baseline_opened_candidate_match_count']}`；匹配 Stage006 closed-lot `{metrics['matched_event_count']}`，"
        f"匹配率 `{metrics['matched_event_rate_pct']:.4f}%`，被暂停事件 Stage006 realized PnL 代理 "
        f"`{metrics['baseline_realized_pnl_proxy_of_paused_events']:.2f}`，正/负 PnL 代理事件 "
        f"`{metrics['positive_proxy_event_count']}/{metrics['negative_proxy_event_count']}`。"
        f"Stage029 正收益起点 `{metrics['source_positive_count_stage029']}/{metrics['source_count']}`，"
        f"80% 收益保留 `{metrics['stage029_80pct_retention_pass_count']}/{metrics['source_count']}`，"
        f"说明直接暂停账户受伤状态 flat_entry 过粗，不能上线，也不应继续扫 DD/loss_streak 阈值。"
        f"记录 `{stage_record}`，报告 `{REPORT_PATH}`。\n"
    )
    with BACK_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_RECORD_DIR.mkdir(parents=True, exist_ok=True)

    source_delta = _load_source_delta()
    events = _prepare_stage029_events()
    lots = _prepare_baseline_lots()
    candidates = _prepare_baseline_candidates()
    matched = _match_events_to_baseline_lots(events, lots, candidates)
    source_summary = _source_event_summary(matched, source_delta)
    trigger = _summarize_group(matched, ["trigger_bucket"]).sort_values(
        ["baseline_realized_pnl_proxy", "pause_event_count"], ascending=[True, False]
    )
    month = _summarize_group(matched, ["event_month"]).sort_values("event_month")
    product = _summarize_group(matched, ["product_vt_symbol", "direction"]).sort_values(
        "baseline_realized_pnl_proxy", ascending=False
    )
    worst_window_coverage = _worst_window_coverage(matched)

    source_summary.to_csv(SOURCE_DELTA_PATH, index=False, encoding="utf-8-sig")
    matched.to_csv(EVENT_ATTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    trigger.to_csv(TRIGGER_BUCKET_PATH, index=False, encoding="utf-8-sig")
    month.to_csv(MONTH_BUCKET_PATH, index=False, encoding="utf-8-sig")
    product.to_csv(PRODUCT_DIRECTION_PATH, index=False, encoding="utf-8-sig")
    worst_window_coverage.to_csv(WORST_WINDOW_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    _plot(source_summary, trigger, month, product)

    decision = _decision(source_summary, trigger, month, product, worst_window_coverage, matched)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, source_summary, trigger, month, product, worst_window_coverage)
    stage_record = _write_stage_record(decision)
    _append_back_log(decision, stage_record)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
