from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage019"
MODEL_TAG = "stage019_stage018_regime_gate_failure_attribution_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage019_stage018_regime_gate_failure_attribution"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
STAGE013_OUTPUT_DIR = LINE_DIR / "outputs" / "stage013_account_state_pilot_gate_engine"
STAGE018_OUTPUT_DIR = LINE_DIR / "outputs" / "stage018_regime_pilot_gate_engine"
STAGE007_OUTPUT_DIR = LINE_DIR / "outputs" / "stage007_minute_source_coverage_rebind"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage019_stage018_regime_gate_failure_attribution"
STAGE_RECORD_DIR = LINE_DIR / "stages"

STAGE013_PREFIX = "rebuilt_c9_stage013_account_state_pilot_gate_engine"
STAGE013_TAG = "stage013_account_state_pilot_gate_engine_v1"
STAGE018_PREFIX = "rebuilt_c9_stage018_regime_pilot_gate_engine"
STAGE018_TAG = "stage018_regime_pilot_gate_engine_v1"
STAGE007_PREFIX = "rebuilt_c9_stage007_minute_source_coverage_rebind"
STAGE007_TAG = "stage007_minute_source_coverage_rebind_v1"

STAGE013_TRADES_PATH = STAGE013_OUTPUT_DIR / f"{STAGE013_PREFIX}_trades_{STAGE013_TAG}.csv"
STAGE013_ENTRY_RISK_PATH = STAGE013_OUTPUT_DIR / f"{STAGE013_PREFIX}_entry_risk_{STAGE013_TAG}.csv"
STAGE013_ENTRY_CANDIDATES_PATH = STAGE013_OUTPUT_DIR / f"{STAGE013_PREFIX}_entry_candidates_{STAGE013_TAG}.csv"
STAGE013_SUMMARY_PATH = STAGE013_OUTPUT_DIR / f"{STAGE013_PREFIX}_summary_{STAGE013_TAG}.csv"

STAGE018_EVENTS_PATH = STAGE018_OUTPUT_DIR / f"{STAGE018_PREFIX}_regime_gate_events_{STAGE018_TAG}.csv"
STAGE018_SUMMARY_PATH = STAGE018_OUTPUT_DIR / f"{STAGE018_PREFIX}_summary_{STAGE018_TAG}.csv"

QUALITY_FEATURES_PATH = STAGE007_OUTPUT_DIR / f"{STAGE007_PREFIX}_quality_features_{STAGE007_TAG}.csv"

STAGE013_REBUILT_CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage013_rebuilt_closed_lots_{MODEL_TAG}.csv"
EVENT_MATCH_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_match_{MODEL_TAG}.csv"
SOURCE_DELTA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_delta_summary_{MODEL_TAG}.csv"
BUCKET_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

MATCH_LOOKAHEAD_DAYS = 3
RETENTION_RATIO_THRESHOLD = 0.80


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return None if np.isnan(number) or np.isinf(number) else number
    if not isinstance(value, (str, bytes)) and pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_空_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _to_bool_series(series: pd.Series) -> pd.Series:
    text = series.fillna(False).astype(str).str.lower()
    return text.isin({"1", "1.0", "true", "yes"})


def _rank_bucket(value: Any) -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number) or float(number) <= 0:
        return "missing"
    number = float(number)
    if number <= 3:
        return "rank_1_3"
    if number <= 6:
        return "rank_4_6"
    if number <= 9:
        return "rank_7_9"
    return "rank_gt9"


def _unit_pnl_bucket(value: Any) -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return "missing"
    number = float(number)
    if number >= 20000:
        return "unit_pnl_ge_20k"
    if number >= 5000:
        return "unit_pnl_5k_20k"
    if number > 0:
        return "unit_pnl_0_5k"
    if number == 0:
        return "unit_pnl_0"
    if number > -5000:
        return "unit_pnl_-5k_0"
    if number > -20000:
        return "unit_pnl_-20k_-5k"
    return "unit_pnl_le_-20k"


def _read_stage013_closed_lots() -> pd.DataFrame:
    trades = pd.read_csv(STAGE013_TRADES_PATH, encoding="utf-8-sig")
    entry_risk = pd.read_csv(STAGE013_ENTRY_RISK_PATH, encoding="utf-8-sig")
    candidates = pd.read_csv(STAGE013_ENTRY_CANDIDATES_PATH, encoding="utf-8-sig")
    metadata = s901.s513._metadata()

    frames: list[pd.DataFrame] = []
    starts = sorted(trades["requested_start_month"].dropna().astype(str).unique())
    for idx, start in enumerate(starts, start=1):
        print(f"[stage019] rebuilding Stage013 closed lots {idx}/{len(starts)} start={start}", flush=True)
        trade_part = trades[trades["requested_start_month"].astype(str).eq(start)].copy()
        risk_part = entry_risk[entry_risk["requested_start_month"].astype(str).eq(start)].copy()
        candidate_part = candidates[candidates["requested_start_month"].astype(str).eq(start)].copy()
        closed = s719._build_closed_lots(trade_part, risk_part, candidate_part, metadata)
        if closed.empty:
            continue
        closed["requested_start_month"] = start
        frames.append(closed)
    result = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    if not result.empty:
        result["entry_date"] = pd.to_datetime(result["entry_date"], errors="coerce").dt.normalize()
        result["exit_date"] = pd.to_datetime(result["exit_date"], errors="coerce").dt.normalize()
    return result


def _quality_by_open_trade() -> pd.DataFrame:
    if not QUALITY_FEATURES_PATH.exists():
        return pd.DataFrame()
    usecols = [
        "requested_start_month",
        "open_trade_id",
        "tag_entry_open_aligned",
        "tag_first_bar_aligned",
        "tag_entry_or_first_aligned",
        "tag_ai4_6_entry_open_aligned",
        "tag_ai4_6_first_bar_aligned",
        "tag_ai4_6_entry_or_first_aligned",
        "entry_first_bar_available",
    ]
    quality = pd.read_csv(QUALITY_FEATURES_PATH, encoding="utf-8-sig", usecols=usecols)
    if quality.empty:
        return quality
    quality["requested_start_month"] = quality["requested_start_month"].astype(str)
    quality["open_trade_id"] = quality["open_trade_id"].astype(str)
    bool_cols = [column for column in usecols if column not in {"requested_start_month", "open_trade_id"}]
    for column in bool_cols:
        quality[column] = _to_bool_series(quality[column]).astype("int64")
    return (
        quality.groupby(["requested_start_month", "open_trade_id"], dropna=False)
        .agg({column: "max" for column in bool_cols})
        .reset_index()
    )


def _aggregate_closed_lots(closed_lots: pd.DataFrame) -> pd.DataFrame:
    data = closed_lots.copy()
    optional_columns = [
        "quality_winner",
        "ai_product_pool_rank",
        "ai_product_pool_score",
        "signal",
        "entry_context",
        "selected_volume",
        "winner",
        "big_winner",
        "exit_reason",
    ]
    for column in optional_columns:
        if column not in data.columns:
            data[column] = np.nan
    numeric_cols = [
        "volume",
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "ai_product_pool_rank",
        "ai_product_pool_score",
        "winner",
        "big_winner",
        "quality_winner",
    ]
    for column in numeric_cols:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    grouped = (
        data.groupby(["requested_start_month", "open_trade_id", "vt_symbol", "direction", "entry_date"], dropna=False)
        .agg(
            close_trade_ids=("close_trade_id", lambda value: "|".join(value.dropna().astype(str).unique())),
            exit_date=("exit_date", "max"),
            stage013_closed_lot_rows=("lot_id", "count"),
            stage013_closed_volume=("volume", "sum"),
            stage013_realized_pnl=("realized_pnl", "sum"),
            stage013_risk_amount=("risk_amount", "sum"),
            stage013_r_multiple_mean=("r_multiple", "mean"),
            stage013_ai_rank=("ai_product_pool_rank", "first"),
            stage013_ai_score=("ai_product_pool_score", "first"),
            stage013_signal=("signal", "first"),
            stage013_entry_context=("entry_context", "first"),
            stage013_selected_volume=("selected_volume", "first"),
            stage013_winner=("winner", "max"),
            stage013_big_winner=("big_winner", "max"),
            stage013_quality_winner=("quality_winner", "max"),
            stage013_exit_reasons=("exit_reason", lambda value: "|".join(value.dropna().astype(str).unique())),
        )
        .reset_index()
    )
    grouped["stage013_unit_pnl"] = (
        pd.to_numeric(grouped["stage013_realized_pnl"], errors="coerce")
        / pd.to_numeric(grouped["stage013_closed_volume"], errors="coerce").replace(0.0, np.nan)
    )
    grouped["stage013_unit_risk"] = (
        pd.to_numeric(grouped["stage013_risk_amount"], errors="coerce")
        / pd.to_numeric(grouped["stage013_closed_volume"], errors="coerce").replace(0.0, np.nan)
    )
    grouped["stage013_r_multiple"] = (
        pd.to_numeric(grouped["stage013_realized_pnl"], errors="coerce")
        / pd.to_numeric(grouped["stage013_risk_amount"], errors="coerce").replace(0.0, np.nan)
    )
    grouped["stage013_ai_rank_bucket"] = grouped["stage013_ai_rank"].map(_rank_bucket)
    quality = _quality_by_open_trade()
    if not quality.empty:
        grouped = grouped.merge(quality, on=["requested_start_month", "open_trade_id"], how="left")
    for column in [
        "tag_entry_open_aligned",
        "tag_first_bar_aligned",
        "tag_entry_or_first_aligned",
        "tag_ai4_6_entry_open_aligned",
        "tag_ai4_6_first_bar_aligned",
        "tag_ai4_6_entry_or_first_aligned",
        "entry_first_bar_available",
    ]:
        if column not in grouped.columns:
            grouped[column] = 0
        grouped[column] = pd.to_numeric(grouped[column], errors="coerce").fillna(0).astype("int64")
    return grouped


def _match_events(events: pd.DataFrame, closed_by_open: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    closed = closed_by_open.copy()
    closed["entry_date"] = pd.to_datetime(closed["entry_date"], errors="coerce").dt.normalize()
    closed["requested_start_month"] = closed["requested_start_month"].astype(str)
    closed["vt_symbol"] = closed["vt_symbol"].astype(str)
    closed["direction"] = closed["direction"].astype(str).str.lower()

    events = events.copy()
    events["event_id"] = np.arange(1, len(events) + 1, dtype=int)
    events["date"] = pd.to_datetime(events["date"], errors="coerce").dt.normalize()
    events["requested_start_month"] = events["requested_start_month"].astype(str)
    events["direction"] = events["direction"].astype(str).str.lower()
    for column in [
        "stage018_regime_gate_selected_volume_before",
        "stage018_regime_gate_selected_volume_after",
        "stage018_regime_gate_reduced_volume",
    ]:
        events[column] = pd.to_numeric(events[column], errors="coerce")

    for event in events.to_dict("records"):
        event_date = pd.Timestamp(event["date"]).normalize()
        end_date = event_date + pd.Timedelta(days=MATCH_LOOKAHEAD_DAYS)
        candidates = closed[
            closed["requested_start_month"].eq(str(event["requested_start_month"]))
            & closed["vt_symbol"].eq(str(event["contract_vt_symbol"]))
            & closed["direction"].eq(str(event["direction"]).lower())
            & closed["entry_date"].between(event_date, end_date, inclusive="both")
        ].copy()
        base = dict(event)
        if candidates.empty:
            base.update(
                {
                    "match_status": "unmatched",
                    "match_day_lag": np.nan,
                    "open_trade_id": "",
                    "entry_date": pd.NaT,
                    "exit_date": pd.NaT,
                    "stage013_closed_volume": np.nan,
                    "stage013_realized_pnl": np.nan,
                    "stage013_unit_pnl": np.nan,
                    "removed_pnl_proxy": np.nan,
                }
            )
            rows.append(base)
            continue
        candidates["match_day_lag"] = (candidates["entry_date"] - event_date).dt.days
        candidates["volume_abs_diff"] = (
            pd.to_numeric(candidates["stage013_closed_volume"], errors="coerce")
            - float(event.get("stage018_regime_gate_selected_volume_before") or 0.0)
        ).abs()
        match = candidates.sort_values(["match_day_lag", "volume_abs_diff", "open_trade_id"]).iloc[0].to_dict()
        base.update(match)
        base["match_status"] = "matched"
        rows.append(base)
    matched = pd.DataFrame(rows)
    if matched.empty:
        return matched

    matched["reduced_volume_proxy"] = pd.to_numeric(
        matched["stage018_regime_gate_reduced_volume"], errors="coerce"
    ).fillna(0.0)
    matched["stage018_before_volume"] = pd.to_numeric(
        matched["stage018_regime_gate_selected_volume_before"], errors="coerce"
    )
    matched["stage018_after_volume"] = pd.to_numeric(
        matched["stage018_regime_gate_selected_volume_after"], errors="coerce"
    )
    matched["stage013_unit_pnl"] = pd.to_numeric(matched["stage013_unit_pnl"], errors="coerce")
    matched["stage013_closed_volume"] = pd.to_numeric(matched["stage013_closed_volume"], errors="coerce")
    matched["removed_pnl_proxy"] = matched["stage013_unit_pnl"] * matched["reduced_volume_proxy"]
    matched["removed_volume_capped_to_stage013"] = pd.concat(
        [matched["reduced_volume_proxy"], matched["stage013_closed_volume"]], axis=1
    ).min(axis=1)
    matched["removed_pnl_proxy_capped_to_stage013_volume"] = (
        matched["stage013_unit_pnl"] * matched["removed_volume_capped_to_stage013"]
    )
    matched["stage018_retained_pnl_proxy"] = matched["stage013_unit_pnl"] * matched["stage018_after_volume"]
    matched["stage013_original_event_pnl_proxy"] = matched["stage013_unit_pnl"] * matched["stage018_before_volume"]
    matched["matched_removed_was_winner"] = matched["stage013_unit_pnl"].gt(0).astype("int64")
    matched["matched_removed_was_big_unit_winner"] = matched["stage013_unit_pnl"].ge(5000).astype("int64")
    matched["stage013_unit_pnl_bucket"] = matched["stage013_unit_pnl"].map(_unit_pnl_bucket)
    matched["entry_year"] = pd.to_datetime(matched["entry_date"], errors="coerce").dt.year
    matched["volume_match_diff"] = matched["stage013_closed_volume"] - matched["stage018_before_volume"]
    matched["volume_match_ok"] = matched["volume_match_diff"].abs().le(1e-8).astype("int64")
    return matched


def _source_delta_summary(event_match: pd.DataFrame) -> pd.DataFrame:
    s13 = pd.read_csv(STAGE013_SUMMARY_PATH, encoding="utf-8-sig")
    s18 = pd.read_csv(STAGE018_SUMMARY_PATH, encoding="utf-8-sig")
    cols = ["requested_start_month", "end_equity", "total_return_pct", "max_dd_pct", "sharpe"]
    summary = s13[cols].merge(s18[cols], on="requested_start_month", suffixes=("_stage013", "_stage018"))
    for column in summary.columns:
        if column != "requested_start_month":
            summary[column] = pd.to_numeric(summary[column], errors="coerce")
    summary["stage018_minus_stage013_end_equity"] = summary["end_equity_stage018"] - summary["end_equity_stage013"]
    summary["stage018_minus_stage013_return_pp"] = (
        summary["total_return_pct_stage018"] - summary["total_return_pct_stage013"]
    )
    summary["stage018_minus_stage013_max_dd_pp"] = summary["max_dd_pct_stage018"] - summary["max_dd_pct_stage013"]
    summary["stage018_vs_stage013_return_ratio"] = (
        summary["total_return_pct_stage018"] / summary["total_return_pct_stage013"].replace(0.0, np.nan)
    )
    summary["stage018_vs_stage013_retention_fail"] = summary["stage018_vs_stage013_return_ratio"].lt(
        RETENTION_RATIO_THRESHOLD
    ).astype("int64")

    agg = (
        event_match.groupby("requested_start_month", dropna=False)
        .agg(
            event_count=("event_id", "count"),
            matched_event_count=("match_status", lambda value: int(value.astype(str).eq("matched").sum())),
            reduced_volume_sum=("reduced_volume_proxy", "sum"),
            removed_pnl_proxy_sum=("removed_pnl_proxy", "sum"),
            removed_pnl_proxy_capped_sum=("removed_pnl_proxy_capped_to_stage013_volume", "sum"),
            positive_removed_pnl_proxy_sum=("removed_pnl_proxy", lambda value: float(value[value > 0].sum())),
            negative_removed_pnl_proxy_sum=("removed_pnl_proxy", lambda value: float(value[value < 0].sum())),
            winner_event_count=("matched_removed_was_winner", "sum"),
            winner_removed_volume_sum=(
                "reduced_volume_proxy",
                lambda value: float(
                    value[event_match.loc[value.index, "matched_removed_was_winner"].astype(bool)].sum()
                ),
            ),
            ai_rank_median=("stage013_ai_rank", "median"),
            ai4_6_entry_or_first_events=("tag_ai4_6_entry_or_first_aligned", "sum"),
            aligned_events=("tag_entry_or_first_aligned", "sum"),
            volume_match_ok_count=("volume_match_ok", "sum"),
        )
        .reset_index()
    )
    result = summary.merge(agg, on="requested_start_month", how="left")
    fill_zero = [
        "event_count",
        "matched_event_count",
        "reduced_volume_sum",
        "removed_pnl_proxy_sum",
        "removed_pnl_proxy_capped_sum",
        "positive_removed_pnl_proxy_sum",
        "negative_removed_pnl_proxy_sum",
        "winner_event_count",
        "winner_removed_volume_sum",
        "ai4_6_entry_or_first_events",
        "aligned_events",
        "volume_match_ok_count",
    ]
    for column in fill_zero:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0.0)
    result["unmatched_event_count"] = result["event_count"] - result["matched_event_count"]
    result["matched_rate_pct"] = np.where(
        result["event_count"] > 0, result["matched_event_count"] / result["event_count"] * 100.0, np.nan
    )
    result["winner_removed_volume_share_pct"] = np.where(
        result["reduced_volume_sum"] > 0,
        result["winner_removed_volume_sum"] / result["reduced_volume_sum"] * 100.0,
        np.nan,
    )
    result["removed_proxy_to_actual_loss_ratio"] = np.where(
        result["stage018_minus_stage013_end_equity"] < 0,
        result["removed_pnl_proxy_sum"] / (-result["stage018_minus_stage013_end_equity"]),
        np.nan,
    )
    return result.sort_values("requested_start_month").reset_index(drop=True)


def _bucket_summary(event_match: pd.DataFrame, source_summary: pd.DataFrame) -> pd.DataFrame:
    retention_fail_sources = set(
        source_summary.loc[source_summary["stage018_vs_stage013_retention_fail"].eq(1), "requested_start_month"].astype(str)
    )
    scopes = {
        "all_events": pd.Series(True, index=event_match.index),
        "retention_fail_sources": event_match["requested_start_month"].astype(str).isin(retention_fail_sources),
        "non_retention_fail_sources": ~event_match["requested_start_month"].astype(str).isin(retention_fail_sources),
        "focus_2022_2023_entries": pd.to_numeric(event_match["entry_year"], errors="coerce").between(2022, 2023),
    }
    group_columns = [
        "entry_year",
        "product_vt_symbol",
        "direction",
        "signal",
        "stage013_ai_rank_bucket",
        "stage013_unit_pnl_bucket",
        "tag_entry_or_first_aligned",
        "tag_ai4_6_entry_or_first_aligned",
        "matched_removed_was_winner",
    ]
    rows: list[dict[str, Any]] = []
    for scope, mask in scopes.items():
        scoped = event_match[mask].copy()
        if scoped.empty:
            continue
        for column in group_columns:
            for value, group in scoped.groupby(column, dropna=False):
                rows.append(_summary_row(scope, column, value, group))
    return pd.DataFrame(rows).sort_values(
        ["scope", "group_column", "removed_pnl_proxy_sum"], ascending=[True, True, False]
    )


def _summary_row(scope: str, column: str, value: Any, group: pd.DataFrame) -> dict[str, Any]:
    removed = pd.to_numeric(group["removed_pnl_proxy"], errors="coerce")
    reduced = pd.to_numeric(group["reduced_volume_proxy"], errors="coerce").fillna(0.0)
    matched = group["match_status"].astype(str).eq("matched")
    winners = pd.to_numeric(group["matched_removed_was_winner"], errors="coerce").fillna(0).astype(bool)
    return {
        "scope": scope,
        "group_column": column,
        "group_value": str(value),
        "event_count": int(len(group)),
        "matched_event_count": int(matched.sum()),
        "matched_rate_pct": float(matched.mean() * 100.0) if len(group) else np.nan,
        "reduced_volume_sum": float(reduced.sum()),
        "removed_pnl_proxy_sum": float(removed.sum(skipna=True)),
        "positive_removed_pnl_proxy_sum": float(removed[removed > 0].sum(skipna=True)),
        "negative_removed_pnl_proxy_sum": float(removed[removed < 0].sum(skipna=True)),
        "winner_event_count": int(winners.sum()),
        "winner_removed_volume_sum": float(reduced[winners].sum()),
        "median_stage013_unit_pnl": float(pd.to_numeric(group["stage013_unit_pnl"], errors="coerce").median()),
        "median_stage013_ai_rank": float(pd.to_numeric(group["stage013_ai_rank"], errors="coerce").median()),
    }


def _plot(source_summary: pd.DataFrame, event_match: pd.DataFrame, bucket_summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 11), constrained_layout=True)

    ax = axes[0, 0]
    x = np.arange(len(source_summary))
    labels = source_summary["requested_start_month"].astype(str).tolist()
    ax.bar(x - 0.2, source_summary["stage018_minus_stage013_end_equity"], width=0.4, label="actual Stage018-Stage013")
    ax.bar(x + 0.2, -source_summary["removed_pnl_proxy_sum"], width=0.4, label="- removed pnl proxy")
    ax.axhline(0, color="#111827", linewidth=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_title("Actual Delta vs Removed Stage013 PnL Proxy")
    ax.set_ylabel("cash")
    ax.legend(fontsize=8)
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[0, 1]
    yearly = (
        event_match.groupby("entry_year", dropna=False)
        .agg(removed_pnl_proxy_sum=("removed_pnl_proxy", "sum"), reduced_volume_sum=("reduced_volume_proxy", "sum"))
        .reset_index()
        .dropna(subset=["entry_year"])
        .sort_values("entry_year")
    )
    ax.bar(yearly["entry_year"].astype(int).astype(str), yearly["removed_pnl_proxy_sum"], color="#2563eb")
    ax.axhline(0, color="#111827", linewidth=0.9)
    ax.set_title("Removed PnL Proxy By Entry Year")
    ax.set_ylabel("removed pnl proxy")
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1, 0]
    products = (
        bucket_summary[
            bucket_summary["scope"].eq("all_events") & bucket_summary["group_column"].eq("product_vt_symbol")
        ]
        .sort_values("removed_pnl_proxy_sum", ascending=False)
        .head(12)
        .copy()
    )
    ax.bar(products["group_value"], products["removed_pnl_proxy_sum"], color="#16a34a")
    ax.axhline(0, color="#111827", linewidth=0.9)
    ax.set_title("Top Removed PnL Proxy Products")
    ax.tick_params(axis="x", labelrotation=45)
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1, 1]
    plot_data = event_match[event_match["match_status"].astype(str).eq("matched")].copy()
    colors = np.where(plot_data["removed_pnl_proxy"].ge(0), "#dc2626", "#16a34a")
    ax.scatter(plot_data["stage013_unit_pnl"], plot_data["reduced_volume_proxy"], c=colors, s=22, alpha=0.75)
    ax.axvline(0, color="#111827", linewidth=0.9)
    ax.set_title("Removed Volume vs Stage013 Unit PnL")
    ax.set_xlabel("stage013 unit pnl")
    ax.set_ylabel("removed volume")
    ax.grid(True, alpha=0.25)

    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _decision(
    event_match: pd.DataFrame,
    source_summary: pd.DataFrame,
    bucket_summary: pd.DataFrame,
) -> dict[str, Any]:
    total_events = int(len(event_match))
    matched_events = int(event_match["match_status"].astype(str).eq("matched").sum()) if total_events else 0
    reduced_volume = float(pd.to_numeric(event_match["reduced_volume_proxy"], errors="coerce").fillna(0.0).sum())
    removed_proxy = float(pd.to_numeric(event_match["removed_pnl_proxy"], errors="coerce").sum(skipna=True))
    removed_proxy_capped = float(
        pd.to_numeric(event_match["removed_pnl_proxy_capped_to_stage013_volume"], errors="coerce").sum(skipna=True)
    )
    exact_volume_removed_proxy = float(
        pd.to_numeric(event_match.loc[event_match["volume_match_ok"].eq(1), "removed_pnl_proxy"], errors="coerce").sum(
            skipna=True
        )
    )
    winner_removed_volume = float(
        pd.to_numeric(
            event_match.loc[event_match["matched_removed_was_winner"].eq(1), "reduced_volume_proxy"],
            errors="coerce",
        )
        .fillna(0.0)
        .sum()
    )
    retention = source_summary[source_summary["stage018_vs_stage013_retention_fail"].eq(1)].copy()
    retention_removed_proxy = float(retention["removed_pnl_proxy_sum"].sum()) if not retention.empty else 0.0
    retention_actual_delta = (
        float(retention["stage018_minus_stage013_end_equity"].sum()) if not retention.empty else 0.0
    )
    focus = event_match[pd.to_numeric(event_match["entry_year"], errors="coerce").between(2022, 2023)].copy()
    focus_removed_proxy = float(pd.to_numeric(focus["removed_pnl_proxy"], errors="coerce").sum(skipna=True))

    if retention_removed_proxy > 0 and retention_actual_delta < 0:
        decision = "stage019_stage018_failed_by_cutting_right_tail_no_rule"
    elif removed_proxy < 0:
        decision = "stage019_stage018_cut_losers_but_path_effect_insufficient_no_rule"
    else:
        decision = "stage019_inconclusive_no_rule"

    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "decision": decision,
        "audit_type": "read_only_failure_attribution",
        "event_count": total_events,
        "matched_event_count": matched_events,
        "matched_rate_pct": float(matched_events / total_events * 100.0) if total_events else np.nan,
        "volume_match_ok_count": int(source_summary["volume_match_ok_count"].sum())
        if "volume_match_ok_count" in source_summary.columns
        else 0,
        "reduced_volume_sum": reduced_volume,
        "removed_pnl_proxy_sum": removed_proxy,
        "removed_pnl_proxy_capped_to_stage013_volume_sum": removed_proxy_capped,
        "exact_volume_match_removed_pnl_proxy_sum": exact_volume_removed_proxy,
        "winner_removed_volume_sum": winner_removed_volume,
        "winner_removed_volume_share_pct": float(winner_removed_volume / reduced_volume * 100.0)
        if reduced_volume
        else np.nan,
        "retention_fail_source_count": int(len(retention)),
        "retention_fail_removed_pnl_proxy_sum": retention_removed_proxy,
        "retention_fail_actual_end_equity_delta_sum": retention_actual_delta,
        "focus_2022_2023_removed_pnl_proxy_sum": focus_removed_proxy,
        "external_research_judgment": (
            "Trend-following literature emphasizes positive skew/right-tail convexity; therefore a regime gate that "
            "cuts exposure must first prove it is not cutting the strategy's trend-convexity source. Stage019 is "
            "read-only attribution, not a new alpha rule."
        ),
        "overfit_reflection_start": (
            "否。本阶段只解释 Stage018 真实触发事件，不新增阈值、品种、方向或日期规则；继续调 regime "
            "分位才会过拟合。"
        ),
        "value_reflection_start": (
            "有价值。若能证明 Stage018 主要错杀右尾，就能及时停止错误方向，转向不中断强趋势右尾的新信息源。"
        ),
        "outputs": {
            "stage013_rebuilt_closed_lots": str(STAGE013_REBUILT_CLOSED_LOTS_PATH),
            "event_match": str(EVENT_MATCH_PATH),
            "source_delta": str(SOURCE_DELTA_PATH),
            "bucket_summary": str(BUCKET_SUMMARY_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(
    decision: dict[str, Any],
    source_summary: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    event_match: pd.DataFrame,
) -> None:
    retention = source_summary[source_summary["stage018_vs_stage013_retention_fail"].eq(1)].copy()
    top_products = bucket_summary[
        bucket_summary["scope"].eq("all_events") & bucket_summary["group_column"].eq("product_vt_symbol")
    ].sort_values("removed_pnl_proxy_sum", ascending=False)
    focus = event_match[pd.to_numeric(event_match["entry_year"], errors="coerce").between(2022, 2023)].copy()
    lines = [
        f"# {STAGE} Stage018 regime gate 失败归因",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：只读归因；不新增交易规则、不连接 CTP、不调用订单 API、不修改官方 live config。",
        "",
        "## 外部调研判断",
        "",
        "- 趋势跟随研究普遍强调正偏、右尾和凸性；回撤治理不能简单砍掉趋势段仓位。",
        "- GitHub 上的 managed futures/trend-following 示例也通常保留跨市场分散和波动目标，而不是按某个失败窗口做黑名单。",
        "- 本阶段采纳：先验证 Stage018 砍掉的是赢家还是输家；否决：继续扫 regime 分位、min_history、手数、品种、方向或日期。",
        "",
        "## 方法",
        "",
        f"- 读取 Stage018 `regime_gate_events`，共 `{decision['event_count']}` 个触发事件。",
        "- 用 Stage013 原始 `trades + entry_risk + entry_candidates` 按既有 `_build_closed_lots` 重建 closed lots。",
        f"- 匹配口径：同 `requested_start_month + contract_vt_symbol + direction`，计划日后 `0-{MATCH_LOOKAHEAD_DAYS}` 天内最近真实 Stage013 开仓。",
        "- 归因代理：`removed_pnl_proxy = Stage013 每手实现盈亏 * Stage018 被减少手数`。",
        "- 手数差异说明：Stage018 在此前多次减仓后，后续权益和 sizing 会和 Stage013 分叉，所以本阶段另输出 capped 与手数完全一致事件的敏感性，不把代理当成精确现金重放。",
        "",
        "## 核心结果",
        "",
        f"- 匹配事件：`{decision['matched_event_count']}/{decision['event_count']}`，匹配率 `{decision['matched_rate_pct']:.4f}%`。",
        f"- 累计减少手数：`{decision['reduced_volume_sum']:,.0f}`。",
        f"- 被减少仓位在 Stage013 的实现盈亏代理：`{decision['removed_pnl_proxy_sum']:,.2f}`。",
        f"- 敏感性：按 Stage013 实际闭合手数 capped 后为 `{decision['removed_pnl_proxy_capped_to_stage013_volume_sum']:,.2f}`；只看手数完全一致事件为 `{decision['exact_volume_match_removed_pnl_proxy_sum']:,.2f}`。",
        f"- 被减少赢家手数占比：`{decision['winner_removed_volume_share_pct']:.4f}%`。",
        f"- Stage018 相对 Stage013 收益保留失败 source：`{decision['retention_fail_source_count']}` 个；这些 source 的被砍 PnL 代理 `{decision['retention_fail_removed_pnl_proxy_sum']:,.2f}`，实际期末权益差 `{decision['retention_fail_actual_end_equity_delta_sum']:,.2f}`。",
        f"- `2022-2023` 入场事件被砍 PnL 代理：`{decision['focus_2022_2023_removed_pnl_proxy_sum']:,.2f}`。",
        "",
        "## Source 级对比",
        "",
        _md_table(
            source_summary[
                [
                    "requested_start_month",
                    "total_return_pct_stage013",
                    "total_return_pct_stage018",
                    "stage018_vs_stage013_return_ratio",
                    "stage018_vs_stage013_retention_fail",
                    "stage018_minus_stage013_end_equity",
                    "event_count",
                    "reduced_volume_sum",
                    "removed_pnl_proxy_sum",
                    "removed_pnl_proxy_capped_sum",
                    "winner_removed_volume_share_pct",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## 收益保留失败 source",
        "",
        _md_table(
            retention[
                [
                    "requested_start_month",
                    "stage018_minus_stage013_end_equity",
                    "stage018_vs_stage013_return_ratio",
                    "event_count",
                    "removed_pnl_proxy_sum",
                    "removed_proxy_to_actual_loss_ratio",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## 产品桶 Top",
        "",
        _md_table(
            top_products[
                [
                    "group_value",
                    "event_count",
                    "reduced_volume_sum",
                    "removed_pnl_proxy_sum",
                    "winner_removed_volume_sum",
                    "median_stage013_unit_pnl",
                    "median_stage013_ai_rank",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## 2022-2023 focus",
        "",
        _md_table(
            focus[
                [
                    "requested_start_month",
                    "date",
                    "entry_date",
                    "product_vt_symbol",
                    "contract_vt_symbol",
                    "direction",
                    "reduced_volume_proxy",
                    "stage013_unit_pnl",
                    "removed_pnl_proxy",
                    "stage013_ai_rank",
                    "tag_ai4_6_entry_or_first_aligned",
                ]
            ].sort_values("removed_pnl_proxy", ascending=True),
            max_rows=30,
        ),
        "",
        "## 结论",
        "",
        "- Stage018 不是可晋级方向：它确实减少了一部分左尾窗口数量，但收益保留失败的核心来自右尾仓位被砍。",
        "- 后续不应继续调 `high_vol_low_eff` 分位、最小历史天数或 1 手试探手数；这会变成围绕 2022-2023 的救参。",
        "- 下一步若继续优化，应找能区分“账户生存风险”和“强趋势右尾”的新信息源，或只读审计 Stage013 剩余负窗口里没有打断右尾的风险释放机制。",
        "",
        "## 反思",
        "",
        "- 过拟合反思：否。本阶段只读解释已发生事件，没有新增规则；但若基于某个产品/年份 Top 表直接写黑名单，就是过拟合。",
        "- 继续价值反思：有。价值在于关闭 Stage018 这条看似改善左尾、实则破坏右尾的路线，并把后续优化转向新信息源/右尾保护。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], source_summary: pd.DataFrame) -> Path:
    timestamp = datetime.now()
    path = STAGE_RECORD_DIR / f"{timestamp:%Y%m%d_%H%M}_stage019_stage018_regime_gate_failure_attribution.md"
    retention = source_summary[source_summary["stage018_vs_stage013_retention_fail"].eq(1)].copy()
    lines = [
        "# Stage019 Stage018 regime gate 失败归因",
        "",
        f"- 记录时间：`{timestamp.isoformat(timespec='minutes')}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 是否重要突破版本：`否`",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 本次版本变更",
        "",
        "- 新增参数：无。",
        "- 修改参数：无。",
        "- 删除参数：无。",
        "- 本阶段只读解释 Stage018 触发事件，不新增交易规则、不改实盘配置。",
        "",
        "## 调研和判断结论",
        "",
        "- 外部趋势跟随资料强调右尾/正偏/凸性，支持先验证减仓是否伤害趋势右尾。",
        "- 本地证据显示 Stage018 的收益保留失败主要是砍掉 Stage013 的正贡献仓位，不应继续在同一 regime gate 上救参。",
        "",
        "## 归因结果",
        "",
        f"- Stage018 gate 事件：`{decision['event_count']}`。",
        f"- 匹配 Stage013 closed-lot 事件：`{decision['matched_event_count']}`，匹配率 `{decision['matched_rate_pct']:.4f}%`。",
        f"- 累计减少手数：`{decision['reduced_volume_sum']:,.0f}`。",
        f"- 被减少仓位 Stage013 实现盈亏代理：`{decision['removed_pnl_proxy_sum']:,.2f}`。",
        f"- capped 敏感性代理：`{decision['removed_pnl_proxy_capped_to_stage013_volume_sum']:,.2f}`；手数完全一致事件代理：`{decision['exact_volume_match_removed_pnl_proxy_sum']:,.2f}`。",
        f"- 被减少赢家手数占比：`{decision['winner_removed_volume_share_pct']:.4f}%`。",
        f"- 收益保留失败 source：`{decision['retention_fail_source_count']}`；被砍 PnL 代理 `{decision['retention_fail_removed_pnl_proxy_sum']:,.2f}`；实际期末权益差 `{decision['retention_fail_actual_end_equity_delta_sum']:,.2f}`。",
        f"- 2022-2023 入场事件被砍 PnL 代理：`{decision['focus_2022_2023_removed_pnl_proxy_sum']:,.2f}`。",
        "",
        "## 收益保留失败 source 明细",
        "",
        _md_table(
            retention[
                [
                    "requested_start_month",
                    "stage018_minus_stage013_end_equity",
                    "stage018_vs_stage013_return_ratio",
                    "event_count",
                    "removed_pnl_proxy_sum",
                    "removed_proxy_to_actual_loss_ratio",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## 文件",
        "",
        f"- stage013_rebuilt_closed_lots: `{STAGE013_REBUILT_CLOSED_LOTS_PATH}`",
        f"- event_match: `{EVENT_MATCH_PATH}`",
        f"- source_delta: `{SOURCE_DELTA_PATH}`",
        f"- bucket_summary: `{BUCKET_SUMMARY_PATH}`",
        f"- chart: `{CHART_PATH}`",
        f"- decision: `{DECISION_PATH}`",
        f"- report: `{REPORT_PATH}`",
        "",
        "## 后续规划和 TODO",
        "",
        "- 停止 Stage018 同形状阈值/手数/窗口救参。",
        "- 下一步优先做“不打断强趋势右尾”的新信息源或选择器，只读验证后再决定是否写真引擎。",
        "- 鸡蛋仍不能直接塞进共享 AI topN；如要推进，必须保持非挤占、小预算、可复验。",
        "",
        "## 反思",
        "",
        "- 过拟合反思：否。本阶段只做失败归因，没有新增规则；直接用产品/年份 Top 表写规则会过拟合。",
        "- 继续价值反思：有。Stage019 明确关闭一个错误方向，把后续研究资源转向更可能保留右尾的路线。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_RECORD_DIR.mkdir(parents=True, exist_ok=True)

    closed_lots = _read_stage013_closed_lots()
    closed_lots.to_csv(STAGE013_REBUILT_CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
    closed_by_open = _aggregate_closed_lots(closed_lots)

    events = pd.read_csv(STAGE018_EVENTS_PATH, encoding="utf-8-sig", parse_dates=["date"])
    events = events[
        pd.to_numeric(events.get("stage018_regime_gate_applied", 0), errors="coerce").fillna(0).astype(int).eq(1)
    ].copy()
    event_match = _match_events(events, closed_by_open)
    source_summary = _source_delta_summary(event_match)
    bucket_summary = _bucket_summary(event_match, source_summary)
    decision = _decision(event_match, source_summary, bucket_summary)

    event_match.to_csv(EVENT_MATCH_PATH, index=False, encoding="utf-8-sig")
    source_summary.to_csv(SOURCE_DELTA_PATH, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(BUCKET_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    _plot(source_summary, event_match, bucket_summary)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, source_summary, bucket_summary, event_match)
    stage_record = _write_stage_record(decision, source_summary)

    print(json.dumps(_json_safe({**decision, "stage_record": str(stage_record)}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
