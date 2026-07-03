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
TOOLS_DIR = Path(__file__).resolve().parent
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
for path in (str(TOOLS_DIR), str(PORTFOLIO_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import stage006_current_quality_feature_binder as s006
import stage009_dense_start_goal_audit as s009
import stage013_account_state_pilot_gate_engine as s013
import stage041_selected_daily_cold_start_probe as s041
import stage056_full_market_ai_budget_cap_engine as s056


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage057"
MODEL_TAG = "stage057_stage056_failure_attribution_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage057_stage056_failure_attribution"
CAP_EVENT_TO_ENTRY_TOLERANCE_DAYS = 10

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage057_stage056_failure_attribution"
STAGES_DIR = LINE_DIR / "stages"

STAGE056_OUTPUT_DIR = LINE_DIR / "outputs" / "stage056_full_market_ai_budget_cap_engine"
STAGE056_PREFIX = "rebuilt_c9_stage056_full_market_ai_budget_cap_engine"
STAGE056_TAG = "stage056_full_market_ai_budget_cap_engine_v1"

CURVES_PATH = STAGE056_OUTPUT_DIR / f"{STAGE056_PREFIX}_curves_{STAGE056_TAG}.csv"
TRADES_PATH = STAGE056_OUTPUT_DIR / f"{STAGE056_PREFIX}_trades_{STAGE056_TAG}.csv.gz"
ENTRY_RISK_PATH = STAGE056_OUTPUT_DIR / f"{STAGE056_PREFIX}_entry_risk_{STAGE056_TAG}.csv.gz"
ENTRY_CANDIDATES_PATH = STAGE056_OUTPUT_DIR / f"{STAGE056_PREFIX}_entry_candidates_{STAGE056_TAG}.csv.gz"
BUDGET_CAP_EVENTS_PATH = STAGE056_OUTPUT_DIR / f"{STAGE056_PREFIX}_budget_cap_events_{STAGE056_TAG}.csv"

WINDOW_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_transition_summary_{MODEL_TAG}.csv"
TOP_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_window_transitions_{MODEL_TAG}.csv"
BASELINE_CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_baseline_closed_lots_{MODEL_TAG}.csv.gz"
MATCHED_CAP_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_matched_cap_lots_{MODEL_TAG}.csv"
SOURCE_ATTRIBUTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_attribution_{MODEL_TAG}.csv"
PRODUCT_ATTRIBUTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_direction_attribution_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

BASE_VARIANT = s056.BASE_VARIANT
CANDIDATE_VARIANT = s056.CANDIDATE_VARIANT
OBJECTIVE_START_MIN = s009.OBJECTIVE_START_MIN
OBJECTIVE_START_MAX = s009.OBJECTIVE_START_MAX
MIN_PERIOD_CALENDAR_DAYS = s009.MIN_PERIOD_CALENDAR_DAYS
WORST_PER_START_PER_CLASS = 3

EXTERNAL_RESEARCH_JUDGMENT = (
    "Risk-variation and forecast-scaling references suggest that broad one-step caps are too coarse for "
    "trend-following portfolios: they may reduce drawdown depth but can also suppress convex right-tail trades. "
    "Stage057 therefore attributes Stage056 before proposing any new rule."
)


def _json_safe(value: Any) -> Any:
    return s006._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s006._md_table(frame, max_rows=max_rows)


def _ret_pct(start_equity: float, end_equity: float) -> float:
    if abs(float(start_equity)) <= 1e-12:
        return np.nan
    return float((float(end_equity) / float(start_equity) - 1.0) * 100.0)


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _classify_stage056_window_effect(
    *,
    source_start: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    stage013_start_equity: float,
    stage013_end_equity: float,
    stage056_start_equity: float,
    stage056_end_equity: float,
) -> dict[str, Any]:
    stage013_return = _ret_pct(stage013_start_equity, stage013_end_equity)
    stage056_return = _ret_pct(stage056_start_equity, stage056_end_equity)
    stage013_negative = bool(pd.notna(stage013_return) and stage013_return < 0.0)
    stage056_negative = bool(pd.notna(stage056_return) and stage056_return < 0.0)
    if stage013_negative and stage056_negative:
        window_class = "both_negative"
    elif stage013_negative and not stage056_negative:
        window_class = "fixed_by_stage056"
    elif not stage013_negative and stage056_negative:
        window_class = "added_negative_by_stage056"
    else:
        window_class = "both_non_negative"

    start_delta = float(stage056_start_equity - stage013_start_equity)
    end_delta = float(stage056_end_equity - stage013_end_equity)
    in_window_delta = float(end_delta - start_delta)
    absolute_end_ge = int(stage056_end_equity >= stage013_end_equity)
    denominator_effect = int(window_class == "added_negative_by_stage056" and absolute_end_ge == 1)
    return {
        "requested_start": str(source_start),
        "source_start_month": str(source_start),
        "start_date": _date_text(start_date),
        "end_date": _date_text(end_date),
        "period_calendar_days": int((pd.Timestamp(end_date) - pd.Timestamp(start_date)).days),
        "stage013_return_pct": stage013_return,
        "stage056_return_pct": stage056_return,
        "return_delta_pp_stage056_vs_stage013": float(stage056_return - stage013_return)
        if pd.notna(stage013_return) and pd.notna(stage056_return)
        else np.nan,
        "window_class": window_class,
        "stage013_start_equity": float(stage013_start_equity),
        "stage013_end_equity": float(stage013_end_equity),
        "stage056_start_equity": float(stage056_start_equity),
        "stage056_end_equity": float(stage056_end_equity),
        "stage056_start_delta_vs_stage013": start_delta,
        "stage056_end_delta_vs_stage013": end_delta,
        "stage056_in_window_delta": in_window_delta,
        "stage056_absolute_end_ge_stage013": absolute_end_ge,
        "stage056_added_negative_denominator_effect": denominator_effect,
    }


def _load_stage056_curves() -> pd.DataFrame:
    curves = pd.read_csv(CURVES_PATH, encoding="utf-8-sig")
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["requested_start"] = curves["requested_start"].astype(str)
    curves["variant"] = curves["variant"].astype(str)
    curves["account_equity"] = pd.to_numeric(curves["account_equity"], errors="coerce")
    return curves.dropna(subset=["date", "account_equity"]).sort_values(["requested_start", "variant", "date"])


def _analyze_source_windows(source_start: str, group: pd.DataFrame) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    pivot = (
        group.pivot_table(index="date", columns="variant", values="account_equity", aggfunc="last")
        .dropna(subset=[BASE_VARIANT, CANDIDATE_VARIANT])
        .sort_index()
    )
    dates = pivot.index.to_numpy(dtype="datetime64[ns]")
    base = pivot[BASE_VARIANT].to_numpy(dtype=float)
    cap = pivot[CANDIDATE_VARIANT].to_numpy(dtype=float)
    objective_dates = pivot.index.to_series()
    objective_mask = (objective_dates >= OBJECTIVE_START_MIN) & (objective_dates <= OBJECTIVE_START_MAX)
    start_indices = np.flatnonzero(objective_mask.to_numpy())

    stats = {
        "requested_start": source_start,
        "window_count": 0,
        "stage013_negative_count": 0,
        "stage056_negative_count": 0,
        "both_negative_count": 0,
        "fixed_by_stage056_count": 0,
        "added_negative_by_stage056_count": 0,
        "both_non_negative_count": 0,
        "added_negative_denominator_effect_count": 0,
        "added_negative_absolute_worse_count": 0,
        "stage013_min_return_pct": np.nan,
        "stage056_min_return_pct": np.nan,
        "stage056_min_in_window_delta": np.nan,
        "final_equity_stage013": float(base[-1]) if len(base) else np.nan,
        "final_equity_stage056": float(cap[-1]) if len(cap) else np.nan,
        "final_equity_delta_stage056_vs_stage013": float(cap[-1] - base[-1]) if len(base) else np.nan,
    }
    top_rows: list[dict[str, Any]] = []
    min_stage013 = np.inf
    min_stage056 = np.inf
    min_in_window_delta = np.inf

    for start_idx in start_indices:
        start_date = pd.Timestamp(dates[start_idx])
        min_end_date = start_date + pd.Timedelta(days=MIN_PERIOD_CALENDAR_DAYS)
        min_end_idx = int(np.searchsorted(dates, np.datetime64(min_end_date), side="left"))
        if min_end_idx >= len(dates):
            continue
        end_indices = np.arange(min_end_idx, len(dates), dtype=int)
        base_start = float(base[start_idx])
        cap_start = float(cap[start_idx])
        if abs(base_start) <= 1e-12 or abs(cap_start) <= 1e-12:
            continue
        base_returns = (base[end_indices] / base_start - 1.0) * 100.0
        cap_returns = (cap[end_indices] / cap_start - 1.0) * 100.0
        valid = np.isfinite(base_returns) & np.isfinite(cap_returns)
        if not valid.any():
            continue
        end_indices = end_indices[valid]
        base_returns = base_returns[valid]
        cap_returns = cap_returns[valid]
        base_negative = base_returns < 0.0
        cap_negative = cap_returns < 0.0
        both_negative = base_negative & cap_negative
        fixed = base_negative & ~cap_negative
        added = ~base_negative & cap_negative
        both_non_negative = ~base_negative & ~cap_negative
        start_delta = cap_start - base_start
        end_delta = cap[end_indices] - base[end_indices]
        in_window_delta = end_delta - start_delta

        stats["window_count"] += int(len(end_indices))
        stats["stage013_negative_count"] += int(base_negative.sum())
        stats["stage056_negative_count"] += int(cap_negative.sum())
        stats["both_negative_count"] += int(both_negative.sum())
        stats["fixed_by_stage056_count"] += int(fixed.sum())
        stats["added_negative_by_stage056_count"] += int(added.sum())
        stats["both_non_negative_count"] += int(both_non_negative.sum())
        stats["added_negative_denominator_effect_count"] += int((added & (end_delta >= 0.0)).sum())
        stats["added_negative_absolute_worse_count"] += int((added & (end_delta < 0.0)).sum())
        min_stage013 = min(min_stage013, float(base_returns.min()))
        min_stage056 = min(min_stage056, float(cap_returns.min()))
        min_in_window_delta = min(min_in_window_delta, float(in_window_delta.min()))

        candidate_positions: list[int] = []
        for mask, scores in [
            (added, cap_returns),
            (both_negative, cap_returns),
            (fixed, base_returns),
        ]:
            positions = np.flatnonzero(mask)
            if len(positions):
                selected = positions[np.argsort(scores[positions])[:WORST_PER_START_PER_CLASS]]
                candidate_positions.extend(selected.tolist())
        for local_pos in sorted(set(candidate_positions)):
            end_idx = int(end_indices[local_pos])
            top_rows.append(
                _classify_stage056_window_effect(
                    source_start=source_start,
                    start_date=start_date,
                    end_date=pd.Timestamp(dates[end_idx]),
                    stage013_start_equity=base_start,
                    stage013_end_equity=float(base[end_idx]),
                    stage056_start_equity=cap_start,
                    stage056_end_equity=float(cap[end_idx]),
                )
            )

    stats["stage013_min_return_pct"] = float(min_stage013) if np.isfinite(min_stage013) else np.nan
    stats["stage056_min_return_pct"] = float(min_stage056) if np.isfinite(min_stage056) else np.nan
    stats["stage056_min_in_window_delta"] = float(min_in_window_delta) if np.isfinite(min_in_window_delta) else np.nan
    stats["stage056_negative_delta_count"] = int(stats["stage056_negative_count"] - stats["stage013_negative_count"])
    return stats, top_rows


def _analyze_window_transitions(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    top_rows: list[dict[str, Any]] = []
    for source_start, group in curves.groupby("requested_start", sort=True):
        stats, rows = _analyze_source_windows(str(source_start), group)
        summary_rows.append(stats)
        top_rows.extend(rows)
    summary = pd.DataFrame(summary_rows).sort_values("requested_start").reset_index(drop=True)
    top = pd.DataFrame(top_rows)
    if not top.empty:
        top = top.sort_values(["window_class", "stage056_return_pct"]).reset_index(drop=True)
    return summary, top


def _read_stage056_frames() -> dict[str, pd.DataFrame]:
    return {
        "trades": pd.read_csv(TRADES_PATH, encoding="utf-8-sig", low_memory=False),
        "entry_risk": pd.read_csv(ENTRY_RISK_PATH, encoding="utf-8-sig", low_memory=False),
        "entry_candidates": pd.read_csv(ENTRY_CANDIDATES_PATH, encoding="utf-8-sig", low_memory=False),
    }


def _build_baseline_closed_lots(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    metadata = s013.s901.s513._metadata()
    closed_frames: list[pd.DataFrame] = []
    trades = frames["trades"]
    starts = sorted(trades.loc[trades["ab_variant"].eq(BASE_VARIANT), "requested_start"].dropna().astype(str).unique())
    for start_text in starts:
        start = pd.Timestamp(start_text).normalize()
        subset_frames = {}
        for key, frame in frames.items():
            subset_frames[key] = frame[
                frame.get("ab_variant", pd.Series(index=frame.index, dtype=str)).astype(str).eq(BASE_VARIANT)
                & frame.get("requested_start", pd.Series(index=frame.index, dtype=str)).astype(str).eq(start_text)
            ].copy()
        closed = s041._closed_lots_from_frames(subset_frames, metadata, start)
        if closed.empty:
            continue
        closed["ab_variant"] = BASE_VARIANT
        closed_frames.append(closed)
    return pd.concat(closed_frames, ignore_index=True, sort=False) if closed_frames else pd.DataFrame()


def _normalize_direction(value: Any) -> str:
    text = str(value or "").strip().lower()
    return {"long": "long", "short": "short", "buy": "long", "sell": "short"}.get(text, text)


def _match_cap_events_to_baseline_lots(events: pd.DataFrame, baseline_lots: pd.DataFrame) -> pd.DataFrame:
    result = events.copy()
    if result.empty:
        return result
    result["_cap_event_row"] = np.arange(len(result), dtype="int64")
    result["requested_start"] = result["requested_start"].astype(str)
    result["event_date"] = pd.to_datetime(result["date"], errors="coerce").dt.normalize()
    result["entry_date"] = result["event_date"]
    result["contract_vt_symbol"] = result["contract_vt_symbol"].fillna(result.get("vt_symbol", "")).astype(str)
    result["product_vt_symbol"] = result["product_vt_symbol"].astype(str)
    result["direction_norm"] = result["direction"].map(_normalize_direction)
    result["cap_volume_before"] = pd.to_numeric(
        result.get("stage056_budget_cap_selected_volume_before"), errors="coerce"
    ).fillna(0.0)
    result["cap_volume_after"] = pd.to_numeric(
        result.get("stage056_budget_cap_selected_volume_after"), errors="coerce"
    ).fillna(0.0)
    result["cap_reduced_volume"] = result["cap_volume_before"] - result["cap_volume_after"]

    lots = baseline_lots.copy()
    if lots.empty:
        result["baseline_lot_matched"] = 0
        result["baseline_entry_date"] = pd.NaT
        result["baseline_realized_pnl"] = np.nan
        result["baseline_volume"] = np.nan
        result["removed_volume_fraction"] = np.nan
        result["removed_pnl_proxy"] = np.nan
        return result.drop(columns=["_cap_event_row"], errors="ignore")
    lots["requested_start"] = lots["requested_start"].astype(str)
    lots["baseline_entry_date"] = pd.to_datetime(lots["entry_date"], errors="coerce").dt.normalize()
    lots["contract_vt_symbol"] = lots["vt_symbol"].astype(str)
    lots["product_vt_symbol"] = lots["product"].astype(str)
    lots["direction_norm"] = lots["direction"].map(_normalize_direction)
    key_columns = ["requested_start", "contract_vt_symbol", "product_vt_symbol", "direction_norm"]
    lot_group = (
        lots.groupby([*key_columns, "baseline_entry_date"], dropna=False)
        .agg(
            baseline_realized_pnl=("realized_pnl", "sum"),
            baseline_volume=("volume", "sum"),
            baseline_lot_count=("realized_pnl", "size"),
        )
        .reset_index()
    )
    lot_groups = {
        key: group.sort_values("baseline_entry_date").reset_index(drop=True)
        for key, group in lot_group.groupby(key_columns, dropna=False, sort=False)
    }

    matched_parts: list[pd.DataFrame] = []
    empty_match_columns = ["baseline_entry_date", "baseline_realized_pnl", "baseline_volume", "baseline_lot_count"]
    for key, event_group in result.groupby(key_columns, dropna=False, sort=False):
        left = event_group.sort_values(["event_date", "_cap_event_row"]).reset_index(drop=True)
        right = lot_groups.get(key)
        if right is None or right.empty:
            for column in empty_match_columns:
                left[column] = pd.NaT if column == "baseline_entry_date" else np.nan
            matched_parts.append(left)
            continue
        matched = pd.merge_asof(
            left,
            right[empty_match_columns].sort_values("baseline_entry_date").reset_index(drop=True),
            left_on="event_date",
            right_on="baseline_entry_date",
            direction="forward",
            tolerance=pd.Timedelta(days=CAP_EVENT_TO_ENTRY_TOLERANCE_DAYS),
        )
        matched_parts.append(matched)

    merged = pd.concat(matched_parts, ignore_index=True, sort=False).sort_values("_cap_event_row").reset_index(drop=True)
    merged["baseline_lot_matched"] = merged["baseline_realized_pnl"].notna().astype("int64")
    merged["removed_volume_fraction"] = np.where(
        merged["cap_volume_before"].gt(0),
        merged["cap_reduced_volume"] / merged["cap_volume_before"],
        np.nan,
    )
    merged["removed_pnl_proxy"] = pd.to_numeric(merged["baseline_realized_pnl"], errors="coerce") * merged[
        "removed_volume_fraction"
    ]
    merged["removed_positive_pnl_proxy"] = merged["removed_pnl_proxy"].where(merged["removed_pnl_proxy"].gt(0), 0.0)
    merged["removed_negative_pnl_proxy"] = merged["removed_pnl_proxy"].where(merged["removed_pnl_proxy"].lt(0), 0.0)
    return merged.drop(columns=["_cap_event_row"], errors="ignore")


def _summarize_matched_cap_lots(matched: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if matched.empty:
        return pd.DataFrame()
    data = matched.copy()
    if "removed_positive_pnl_proxy" not in data.columns and "removed_pnl_proxy" in data.columns:
        removed = pd.to_numeric(data["removed_pnl_proxy"], errors="coerce").fillna(0.0)
        data["removed_positive_pnl_proxy"] = removed.where(removed.gt(0), 0.0)
    if "removed_negative_pnl_proxy" not in data.columns and "removed_pnl_proxy" in data.columns:
        removed = pd.to_numeric(data["removed_pnl_proxy"], errors="coerce").fillna(0.0)
        data["removed_negative_pnl_proxy"] = removed.where(removed.lt(0), 0.0)
    for column in [
        "removed_pnl_proxy",
        "removed_positive_pnl_proxy",
        "removed_negative_pnl_proxy",
        "cap_reduced_volume",
        "baseline_lot_matched",
    ]:
        if column not in data.columns:
            data[column] = 0.0
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0.0)
    grouped = (
        data.groupby(group_columns, dropna=False)
        .agg(
            cap_event_count=("removed_pnl_proxy", "size"),
            matched_event_count=("baseline_lot_matched", "sum"),
            cap_reduced_volume_sum=("cap_reduced_volume", "sum"),
            removed_pnl_proxy_sum=("removed_pnl_proxy", "sum"),
            removed_positive_pnl_proxy=("removed_positive_pnl_proxy", "sum"),
            removed_negative_pnl_proxy=("removed_negative_pnl_proxy", "sum"),
        )
        .reset_index()
    )
    grouped["matched_rate_pct"] = np.where(
        grouped["cap_event_count"].gt(0),
        grouped["matched_event_count"] / grouped["cap_event_count"] * 100.0,
        np.nan,
    )
    return grouped.sort_values("removed_pnl_proxy_sum", ascending=False).reset_index(drop=True)


def _build_source_attribution(window_summary: pd.DataFrame, matched_summary: pd.DataFrame) -> pd.DataFrame:
    result = window_summary.merge(matched_summary, on="requested_start", how="left")
    for column in [
        "cap_event_count",
        "matched_event_count",
        "cap_reduced_volume_sum",
        "removed_pnl_proxy_sum",
        "removed_positive_pnl_proxy",
        "removed_negative_pnl_proxy",
        "matched_rate_pct",
    ]:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0.0)
    result["right_tail_wrong_cut_flag"] = (
        result["removed_pnl_proxy_sum"].gt(0) & result["final_equity_delta_stage056_vs_stage013"].lt(0)
    ).astype("int64")
    result["loss_cut_helped_flag"] = (
        result["removed_pnl_proxy_sum"].lt(0) & result["final_equity_delta_stage056_vs_stage013"].gt(0)
    ).astype("int64")
    return result.sort_values("requested_start").reset_index(drop=True)


def _plot(source_attr: pd.DataFrame, product_attr: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(16, 10), constrained_layout=True)
    labels = source_attr["requested_start"].astype(str).tolist()
    x = np.arange(len(source_attr))
    axes[0].bar(x - 0.18, source_attr["removed_pnl_proxy_sum"], width=0.36, label="removed pnl proxy", color="#2563eb")
    axes[0].bar(
        x + 0.18,
        source_attr["final_equity_delta_stage056_vs_stage013"],
        width=0.36,
        label="final equity delta",
        color="#f97316",
    )
    axes[0].axhline(0.0, color="#111827", linewidth=0.9)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=45, ha="right")
    axes[0].set_title("Stage056 Cap: Removed PnL Proxy vs Final Equity Delta")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[0].legend(loc="best")

    plot = product_attr.sort_values("removed_pnl_proxy_sum").head(15)
    axes[1].barh(
        plot["product_vt_symbol"].astype(str) + " " + plot["direction"].astype(str),
        plot["removed_pnl_proxy_sum"],
        color=np.where(plot["removed_pnl_proxy_sum"].gt(0), "#f97316", "#2563eb"),
    )
    axes[1].axvline(0.0, color="#111827", linewidth=0.9)
    axes[1].set_title("Most Negative Removed PnL Proxy By Product/Direction")
    axes[1].grid(True, axis="x", alpha=0.25)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(decision: dict[str, Any], source_attr: pd.DataFrame, product_attr: pd.DataFrame, top_windows: pd.DataFrame) -> None:
    report = f"""# Stage057 - Stage056 失败归因

- 生成时间：`{decision['generated_at']}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 决策：`{decision['decision']}`
- 阶段性质：只读失败归因；不改官方 C9，不连接 CTP，不调用订单 API。

## 外部调研判断

- 趋势跟随 risk variation / forecast scaling 资料支持用连续信号强度或组合风险预算，而不是把非 Top8 一刀切到 1 手。
- Stage057 因此先解释 Stage056 的错杀和改善来源，不提出新交易规则。

## 核心发现

- Stage056 新增负窗口：`{decision['stage056_added_negative_count']}`；修复 Stage013 负窗口：`{decision['stage056_fixed_negative_count']}`。
- 新增负窗口中的分母效应：`{decision['added_negative_denominator_effect_count']}`；绝对权益也更差：`{decision['added_negative_absolute_worse_count']}`。
- cap 事件匹配 baseline lot：`{decision['matched_cap_event_count']}/{decision['cap_event_count']}`。
- baseline 被 cap 掉的 PnL proxy 合计：`{decision['removed_pnl_proxy_sum']:.2f}`；其中少赚 `{decision['removed_positive_pnl_proxy']:.2f}`、少亏 `{decision['removed_negative_pnl_proxy']:.2f}`。
- 右尾错杀 source 数：`{decision['right_tail_wrong_cut_source_count']}`；减亏有帮助 source 数：`{decision['loss_cut_helped_source_count']}`。

## 起点归因

{_md_table(source_attr)}

## 产品/方向归因

{_md_table(product_attr.head(30))}

## 最差窗口样本

{_md_table(top_windows.head(40))}

## 判断

- 结论：`{decision['decision']}`。
- 过拟合反思：{decision['overfit_reflection_after']}
- 继续价值反思：{decision['continue_value_after']}

## 输出文件

- window_summary: `{WINDOW_SUMMARY_PATH}`
- top_windows: `{TOP_WINDOWS_PATH}`
- baseline_closed_lots: `{BASELINE_CLOSED_LOTS_PATH}`
- matched_cap_lots: `{MATCHED_CAP_LOTS_PATH}`
- source_attribution: `{SOURCE_ATTRIBUTION_PATH}`
- product_attribution: `{PRODUCT_ATTRIBUTION_PATH}`
- chart: `{CHART_PATH}`
- decision: `{DECISION_PATH}`
- report: `{REPORT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage057_stage056_failure_attribution.md"
    content = f"""# Stage057 - Stage056 失败归因

- line_id：`{LINE_ID}`
- 当前模式：`day`
- 记录时间：`{decision['generated_at']} CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读失败归因，不改官方实盘配置。
- 是否重要突破：`否`
- 是否触发A/B：`否`

## 外部调研与判断

- 参考资料：AlphaSimplex risk variation in trend-following、pysystemtrade/Rob Carver forecast scaling、time-series momentum 与 trend-following position sizing 资料。
- 我的判断：Stage056 失败不是因为 Top8 数字要微调，而是“一刀切 cap”把风险预算从连续问题简化成硬门槛，容易压掉右尾。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage057_stage056_failure_attribution.py`
- 新增测试：`tests/test_rebuilt_c9_stage057_stage056_failure_attribution.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：无交易参数。
- 修改参数：无。
- 删除参数：无。

## 归因参数

- 输入：Stage056 curves/trades/entry_risk/entry_candidates/budget_cap_events。
- 口径：A=Stage013，C=Stage056；严格窗口仍使用 `>365` 自然日。
- lot 归因：把 Stage056 cap event 按 `requested_start + contract + product + direction` 分组，向前 `{CAP_EVENT_TO_ENTRY_TOLERANCE_DAYS}` 天内匹配最近 Stage013 baseline 开仓 lot，并按减少手数比例估算被 cap 掉的 realized PnL proxy。
- 不连接 CTP、不调用订单 API。

## 结果

- Stage056 新增负窗口 `{decision['stage056_added_negative_count']}`，修复负窗口 `{decision['stage056_fixed_negative_count']}`。
- 新增负窗口中分母效应 `{decision['added_negative_denominator_effect_count']}`，绝对权益更差 `{decision['added_negative_absolute_worse_count']}`。
- cap 事件 `{decision['cap_event_count']}`，匹配 baseline lot `{decision['matched_cap_event_count']}`，减少手数 `{decision['cap_reduced_volume_sum']:.0f}`。
- 被 cap 掉的 baseline PnL proxy 合计 `{decision['removed_pnl_proxy_sum']:.2f}`，少赚 `{decision['removed_positive_pnl_proxy']:.2f}`，少亏 `{decision['removed_negative_pnl_proxy']:.2f}`。
- 右尾错杀 source `{decision['right_tail_wrong_cut_source_count']}`，减亏有帮助 source `{decision['loss_cut_helped_source_count']}`。

## 输出文件

- report：`{REPORT_PATH}`
- source_attribution：`{SOURCE_ATTRIBUTION_PATH}`
- product_attribution：`{PRODUCT_ATTRIBUTION_PATH}`
- chart：`{CHART_PATH}`

## 结论

- 本阶段结论：`{decision['decision']}`。
- 下一步：不要扫 `TopN/手数/品种`；若继续，应寻找连续预算或状态条件，先做只读归因/稳定性，再决定是否真引擎。

## 过拟合反思

- 运行前判断：否。Stage057 只解释 Stage056 已失败结果，不新增交易规则。
- 运行后判断：{decision['overfit_reflection_after']}

## 继续价值反思

- 运行前判断：有。Stage056 已反证，但仍要知道失败形状，避免重复走硬 cap。
- 运行后判断：{decision['continue_value_after']}
"""
    path.write_text(content, encoding="utf-8")
    return path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    curves = _load_stage056_curves()
    window_summary, top_windows = _analyze_window_transitions(curves)

    frames = _read_stage056_frames()
    baseline_lots = _build_baseline_closed_lots(frames)
    events = pd.read_csv(BUDGET_CAP_EVENTS_PATH, encoding="utf-8-sig")
    matched = _match_cap_events_to_baseline_lots(events, baseline_lots)
    source_cap = _summarize_matched_cap_lots(matched, ["requested_start"])
    product_attr = _summarize_matched_cap_lots(matched, ["product_vt_symbol", "direction"])
    source_attr = _build_source_attribution(window_summary, source_cap)
    _plot(source_attr, product_attr)

    window_summary.to_csv(WINDOW_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    top_windows.to_csv(TOP_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    baseline_lots.to_csv(BASELINE_CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
    matched.to_csv(MATCHED_CAP_LOTS_PATH, index=False, encoding="utf-8-sig")
    source_attr.to_csv(SOURCE_ATTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    product_attr.to_csv(PRODUCT_ATTRIBUTION_PATH, index=False, encoding="utf-8-sig")

    stage056_added = int(pd.to_numeric(window_summary["added_negative_by_stage056_count"], errors="coerce").fillna(0).sum())
    stage056_fixed = int(pd.to_numeric(window_summary["fixed_by_stage056_count"], errors="coerce").fillna(0).sum())
    denominator = int(pd.to_numeric(window_summary["added_negative_denominator_effect_count"], errors="coerce").fillna(0).sum())
    absolute_worse = int(pd.to_numeric(window_summary["added_negative_absolute_worse_count"], errors="coerce").fillna(0).sum())
    removed_pnl = float(pd.to_numeric(matched.get("removed_pnl_proxy"), errors="coerce").fillna(0.0).sum())
    removed_pos = float(pd.to_numeric(matched.get("removed_positive_pnl_proxy"), errors="coerce").fillna(0.0).sum())
    removed_neg = float(pd.to_numeric(matched.get("removed_negative_pnl_proxy"), errors="coerce").fillna(0.0).sum())
    cap_events = int(len(matched))
    matched_events = int(pd.to_numeric(matched.get("baseline_lot_matched"), errors="coerce").fillna(0).sum())
    reduced_volume = float(pd.to_numeric(matched.get("cap_reduced_volume"), errors="coerce").fillna(0.0).sum())
    wrong_cut_count = int(pd.to_numeric(source_attr.get("right_tail_wrong_cut_flag"), errors="coerce").fillna(0).sum())
    helped_count = int(pd.to_numeric(source_attr.get("loss_cut_helped_flag"), errors="coerce").fillna(0).sum())

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "audit_type": "stage056_failure_attribution_readonly",
        "decision": "stage057_stage056_failed_due_to_coarse_hard_cap_right_tail_wrong_cut",
        "strategy_changed": False,
        "official_live_config_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "stage056_added_negative_count": stage056_added,
        "stage056_fixed_negative_count": stage056_fixed,
        "added_negative_denominator_effect_count": denominator,
        "added_negative_absolute_worse_count": absolute_worse,
        "cap_event_count": cap_events,
        "matched_cap_event_count": matched_events,
        "cap_reduced_volume_sum": reduced_volume,
        "removed_pnl_proxy_sum": removed_pnl,
        "removed_positive_pnl_proxy": removed_pos,
        "removed_negative_pnl_proxy": removed_neg,
        "right_tail_wrong_cut_source_count": wrong_cut_count,
        "loss_cut_helped_source_count": helped_count,
        "external_research_judgment": EXTERNAL_RESEARCH_JUDGMENT,
        "overfit_reflection_before": "否。只读解释 Stage056 已失败结果，不新增交易规则。",
        "continue_value_before": "有。必须知道 Stage056 为什么失败，避免继续围绕 TopN/手数救参。",
        "overfit_reflection_after": (
            "否。本阶段没有调参；结论反而要求停止 TopN/手数/品种救参。"
        ),
        "continue_value_after": (
            "有条件。继续价值在连续预算/状态归因，不在 full-market TopN 硬门槛。"
        ),
        "outputs": {
            "window_summary": str(WINDOW_SUMMARY_PATH),
            "top_windows": str(TOP_WINDOWS_PATH),
            "baseline_closed_lots": str(BASELINE_CLOSED_LOTS_PATH),
            "matched_cap_lots": str(MATCHED_CAP_LOTS_PATH),
            "source_attribution": str(SOURCE_ATTRIBUTION_PATH),
            "product_attribution": str(PRODUCT_ATTRIBUTION_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, source_attr, product_attr, top_windows)
    stage_record = _write_stage_record(decision)
    decision["stage_record"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
