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
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
UPSTREAM_LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage022"
MODEL_TAG = "stage022_xsmom_entry_confirmation_proxy_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage022_xsmom_entry_confirmation_proxy"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
UPSTREAM_LINE_DIR = PROJECT_DIR / "research" / "lines" / UPSTREAM_LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage022_xsmom_entry_confirmation_proxy"
STAGES_DIR = LINE_DIR / "stages"
TOOLS_DIR = Path(__file__).resolve().parent
UPSTREAM_TOOLS_DIR = UPSTREAM_LINE_DIR / "tools"
for path in (TOOLS_DIR, UPSTREAM_TOOLS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import stage009_dense_start_goal_audit as s009_goal  # noqa: E402
import stage009_meta_label_entry_quality_audit as s009_quality  # noqa: E402


STAGE009_OUTPUT_DIR = LINE_DIR / "outputs" / "stage009_meta_label_entry_quality_audit"
STAGE009_PREFIX = "rebuilt_c9_v2_stage009_meta_label_entry_quality_audit"
STAGE009_TAG = "stage009_meta_label_entry_quality_audit_v1"
QUALITY_EVENTS_PATH = STAGE009_OUTPUT_DIR / f"{STAGE009_PREFIX}_quality_events_{STAGE009_TAG}.csv.gz"

STAGE020_OUTPUT_DIR = LINE_DIR / "outputs" / "stage020_sqlite_jd_repair_xsmom_inputs"
STAGE020_PREFIX = "rebuilt_c9_v2_stage020_sqlite_jd_repair_xsmom_inputs"
STAGE020_TAG = "stage020_sqlite_jd_repair_xsmom_inputs_v1"
SATELLITE_DAILY_PATH = STAGE020_OUTPUT_DIR / f"{STAGE020_PREFIX}_satellite_daily_{STAGE020_TAG}.csv"

STAGE013_OUTPUT_DIR = UPSTREAM_LINE_DIR / "outputs" / "stage013_account_state_pilot_gate_engine"
STAGE013_PREFIX = "rebuilt_c9_stage013_account_state_pilot_gate_engine"
STAGE013_TAG = "stage013_account_state_pilot_gate_engine_v1"
STAGE013_CURVES_PATH = STAGE013_OUTPUT_DIR / f"{STAGE013_PREFIX}_curves_{STAGE013_TAG}.csv"

TAGGED_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tagged_events_{MODEL_TAG}.csv.gz"
CONDITION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_summary_{MODEL_TAG}.csv"
LOT_DELTAS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_deltas_{MODEL_TAG}.csv.gz"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
GOAL_AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_aggregate_{MODEL_TAG}.csv"
GOAL_TO_FINAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_to_final_windows_{MODEL_TAG}.csv"
GOAL_FIXED_HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_fixed_horizon_windows_{MODEL_TAG}.csv"
GOAL_WORST_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_worst_windows_{MODEL_TAG}.csv"
RETENTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_retention_vs_stage013_{MODEL_TAG}.csv"
VARIANT_GOAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_variant_goal_table_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
STAGE_RECORD_PATH = STAGES_DIR / "20260702_0624_stage022_xsmom_entry_confirmation_proxy.md"

BASE_VARIANT = "stage013_engine"
ADD_RISK_FRACTION = 0.25
SPECS = ("mom_12m_skip1m", "mom_6m_skip1m")
CAPITAL = 150_000.0
OBJECTIVE_START_MIN = pd.Timestamp("2020-01-01")
OBJECTIVE_START_MAX = pd.Timestamp("2025-06-30")
MIN_PERIOD_CALENDAR_DAYS = 366
EPS = 1e-9


def _json_safe(value: Any) -> Any:
    return s009_quality._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s009_quality._md_table(frame, max_rows=max_rows or 20)


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _numeric(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    return s009_quality._numeric(frame, column, default)


def _short_spec(spec: str) -> str:
    if spec == "mom_12m_skip1m":
        return "xsmom12"
    if spec == "mom_6m_skip1m":
        return "xsmom6"
    return "xsmom_" + "".join(ch if ch.isalnum() else "_" for ch in spec).strip("_")


def _product_set(value: Any) -> set[str]:
    if pd.isna(value):
        return set()
    return {item.strip() for item in str(value).split(",") if item.strip()}


def _base_quality_mask(events: pd.DataFrame) -> pd.Series:
    rank = _numeric(events, "ai_product_pool_rank")
    selected_volume = _numeric(events, "selected_volume")
    return rank.ge(1) & rank.le(8) & selected_volume.gt(1)


def _guarded_quality_mask(events: pd.DataFrame) -> pd.Series:
    return _base_quality_mask(events) & _numeric(events, "risk_multiplier").lt(2)


def attach_prior_xsmom_context(
    events: pd.DataFrame,
    satellite_daily: pd.DataFrame,
    *,
    specs: tuple[str, ...] = SPECS,
) -> pd.DataFrame:
    tagged = events.copy()
    tagged["entry_date"] = pd.to_datetime(tagged["entry_date"], errors="coerce").dt.normalize()
    tagged["product"] = tagged["product"].astype(str)
    tagged["direction"] = tagged["direction"].astype(str).str.lower()
    satellite = satellite_daily.copy()
    satellite["date"] = pd.to_datetime(satellite["date"], errors="coerce").dt.normalize()
    satellite["spec"] = satellite["spec"].astype(str)
    for spec in specs:
        prefix = _short_spec(spec)
        spec_daily = satellite[satellite["spec"].eq(spec)].sort_values("date").copy()
        context = pd.DataFrame({"entry_date": spec_daily["date"]})
        context[f"{prefix}_prior_signal_date"] = spec_daily["date"].shift(1).dt.date.astype("string")
        context[f"{prefix}_prior_long_products"] = spec_daily["long_products"].shift(1).fillna("").astype(str)
        context[f"{prefix}_prior_short_products"] = spec_daily["short_products"].shift(1).fillna("").astype(str)
        context[f"{prefix}_prior_active_products"] = pd.to_numeric(
            spec_daily["active_products"].shift(1), errors="coerce"
        ).fillna(0.0)
        tagged = tagged.merge(context, on="entry_date", how="left")

        aligned: list[int] = []
        opposed: list[int] = []
        active: list[int] = []
        covered: list[int] = []
        for row in tagged.itertuples(index=False):
            product = str(getattr(row, "product"))
            direction = str(getattr(row, "direction")).lower()
            long_products = _product_set(getattr(row, f"{prefix}_prior_long_products", ""))
            short_products = _product_set(getattr(row, f"{prefix}_prior_short_products", ""))
            active_count = float(getattr(row, f"{prefix}_prior_active_products", 0.0) or 0.0)
            signal_date = getattr(row, f"{prefix}_prior_signal_date", "")
            is_active = active_count > 0
            is_covered = bool(str(signal_date)) and str(signal_date).lower() not in {"<na>", "nat", "nan"}
            is_aligned = (direction == "long" and product in long_products) or (
                direction == "short" and product in short_products
            )
            is_opposed = (direction == "long" and product in short_products) or (
                direction == "short" and product in long_products
            )
            active.append(int(is_active))
            covered.append(int(is_covered))
            aligned.append(int(is_active and is_aligned))
            opposed.append(int(is_active and is_opposed))
        tagged[f"{prefix}_active"] = active
        tagged[f"{prefix}_covered"] = covered
        tagged[f"{prefix}_aligned"] = aligned
        tagged[f"{prefix}_opposed"] = opposed
        tagged[f"{prefix}_not_opposed"] = (
            pd.Series(active, index=tagged.index).astype(bool)
            & ~pd.Series(opposed, index=tagged.index).astype(bool)
        ).astype("int64")
    return tagged


def condition_masks(tagged: pd.DataFrame) -> dict[str, pd.Series]:
    base = _base_quality_mask(tagged)
    guarded = _guarded_quality_mask(tagged)
    x12_aligned = _numeric(tagged, "xsmom12_aligned", 0.0).eq(1)
    x12_not_opposed = _numeric(tagged, "xsmom12_not_opposed", 0.0).eq(1)
    x6_aligned = _numeric(tagged, "xsmom6_aligned", 0.0).eq(1)
    x6_not_opposed = _numeric(tagged, "xsmom6_not_opposed", 0.0).eq(1)
    return {
        "stage010_quality": base,
        "stage010_quality_xsmom12_aligned": base & x12_aligned,
        "stage010_quality_xsmom12_not_opposed": base & x12_not_opposed,
        "stage010_quality_xsmom6_aligned": base & x6_aligned,
        "stage010_quality_xsmom6_not_opposed": base & x6_not_opposed,
        "stage010_quality_both_xsmom_aligned": base & x12_aligned & x6_aligned,
        "stage013_guarded_quality": guarded,
        "stage013_guarded_quality_xsmom12_aligned": guarded & x12_aligned,
        "stage013_guarded_quality_xsmom12_not_opposed": guarded & x12_not_opposed,
        "stage013_guarded_quality_xsmom6_aligned": guarded & x6_aligned,
        "stage013_guarded_quality_xsmom6_not_opposed": guarded & x6_not_opposed,
        "stage013_guarded_quality_both_xsmom_aligned": guarded & x12_aligned & x6_aligned,
    }


def build_condition_summary(tagged: pd.DataFrame, masks: dict[str, pd.Series]) -> pd.DataFrame:
    descriptions = {
        "stage010_quality": "Stage010 条件：AI rank 1-8 且 selected_volume>1",
        "stage010_quality_xsmom12_aligned": "Stage010 条件且入场方向与前一交易日 12-1m xsmom top/bottom 一致",
        "stage010_quality_xsmom12_not_opposed": "Stage010 条件且前一交易日 12-1m xsmom 未反向",
        "stage010_quality_xsmom6_aligned": "Stage010 条件且入场方向与前一交易日 6-1m xsmom top/bottom 一致",
        "stage010_quality_xsmom6_not_opposed": "Stage010 条件且前一交易日 6-1m xsmom 未反向",
        "stage010_quality_both_xsmom_aligned": "Stage010 条件且 12-1m 与 6-1m xsmom 同时一致",
        "stage013_guarded_quality": "Stage013 guarded 条件：Stage010 条件且 risk_multiplier<2",
        "stage013_guarded_quality_xsmom12_aligned": "Stage013 guarded 且 12-1m xsmom 一致",
        "stage013_guarded_quality_xsmom12_not_opposed": "Stage013 guarded 且 12-1m xsmom 未反向",
        "stage013_guarded_quality_xsmom6_aligned": "Stage013 guarded 且 6-1m xsmom 一致",
        "stage013_guarded_quality_xsmom6_not_opposed": "Stage013 guarded 且 6-1m xsmom 未反向",
        "stage013_guarded_quality_both_xsmom_aligned": "Stage013 guarded 且两个 xsmom 口径同时一致",
    }
    rows = []
    for name, mask in masks.items():
        rows.append(
            s009_quality.evaluate_quality_condition(
                tagged,
                name=name,
                description=descriptions.get(name, name),
                mask=mask,
                min_event_count=60,
                min_year_count=4,
                min_mean_pnl_lift=1.10,
                max_bad_path_rate_delta_pp=5.0,
                candidate_eligible=not name.endswith("quality"),
            )
        )
    summary = pd.DataFrame(rows)
    return summary.sort_values(
        ["stable_quality_candidate", "mean_pnl_lift", "total_pnl", "event_count"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)


def build_condition_lot_deltas(
    tagged: pd.DataFrame,
    masks: dict[str, pd.Series],
    *,
    add_risk_fraction: float = ADD_RISK_FRACTION,
) -> pd.DataFrame:
    base = _base_quality_mask(tagged)
    rows: list[pd.DataFrame] = []
    data = tagged.copy()
    data["requested_start_month"] = data["requested_start_month"].astype(str)
    data["exit_date"] = pd.to_datetime(data["exit_date"], errors="coerce").dt.normalize()
    data["entry_date"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.normalize()
    data["realized_pnl"] = _numeric(data, "realized_pnl", 0.0).fillna(0.0)
    for name, mask in masks.items():
        selected = data.loc[(base & mask.reindex(data.index).fillna(False).astype(bool))].copy()
        if selected.empty:
            continue
        selected["condition"] = name
        selected["stage022_add_risk_fraction"] = float(add_risk_fraction)
        selected["stage022_proxy_delta_pnl"] = selected["realized_pnl"] * float(add_risk_fraction)
        rows.append(selected)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True, sort=False)


def build_proxy_curves(base_curves: pd.DataFrame, lot_deltas: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    base = base_curves.copy()
    base["requested_start_month"] = base["requested_start_month"].astype(str)
    base["date"] = pd.to_datetime(base["date"], errors="coerce").dt.normalize()
    base["account_equity"] = pd.to_numeric(base["account_equity"], errors="coerce")
    base = base.dropna(subset=["date", "account_equity"]).sort_values(["requested_start_month", "date"])
    base_rows = base.copy()
    base_rows["variant"] = BASE_VARIANT
    base_rows["condition"] = BASE_VARIANT
    base_rows["stage022_daily_delta"] = 0.0
    base_rows["stage022_cum_delta"] = 0.0

    frames = [base_rows]
    unmatched = 0
    if lot_deltas.empty:
        return base_rows.reset_index(drop=True), 0
    daily = (
        lot_deltas.groupby(["condition", "requested_start_month", "exit_date"], dropna=False)[
            "stage022_proxy_delta_pnl"
        ]
        .sum()
        .reset_index()
    )
    daily["requested_start_month"] = daily["requested_start_month"].astype(str)
    daily["exit_date"] = pd.to_datetime(daily["exit_date"], errors="coerce").dt.normalize()
    curve_dates = set(zip(base["requested_start_month"].astype(str), base["date"]))
    for row in daily.itertuples(index=False):
        if (str(row.requested_start_month), pd.Timestamp(row.exit_date)) not in curve_dates:
            unmatched += 1
    for condition, condition_delta in daily.groupby("condition", sort=True):
        merged = base.merge(
            condition_delta.rename(columns={"exit_date": "date", "stage022_proxy_delta_pnl": "stage022_daily_delta"})[
                ["requested_start_month", "date", "stage022_daily_delta"]
            ],
            on=["requested_start_month", "date"],
            how="left",
        )
        merged["stage022_daily_delta"] = pd.to_numeric(merged["stage022_daily_delta"], errors="coerce").fillna(0.0)
        parts = []
        for _, group in merged.groupby("requested_start_month", sort=True):
            g = group.sort_values("date").copy()
            g["stage022_cum_delta"] = g["stage022_daily_delta"].cumsum()
            g["account_equity"] = g["account_equity"] + g["stage022_cum_delta"]
            parts.append(g)
        candidate = pd.concat(parts, ignore_index=True, sort=False)
        candidate["variant"] = f"stage022_{condition}"
        candidate["condition"] = condition
        frames.append(candidate)
    return pd.concat(frames, ignore_index=True, sort=False).sort_values(
        ["variant", "requested_start_month", "date"]
    ).reset_index(drop=True), int(unmatched)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _sharpe_from_equity(equity: pd.Series) -> float:
    values = pd.to_numeric(equity, errors="coerce").dropna()
    returns = values.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty or float(returns.std(ddof=1)) == 0.0:
        return 0.0
    return float(returns.mean() / returns.std(ddof=1) * np.sqrt(252.0))


def summarize_all(curves: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (variant, start_month), group in curves.groupby(["variant", "requested_start_month"], sort=True):
        data = group.sort_values("date").drop_duplicates("date").copy()
        equity = pd.to_numeric(data["account_equity"], errors="coerce")
        start_equity = float(equity.iloc[0])
        end_equity = float(equity.iloc[-1])
        rows.append(
            {
                "stage": STAGE,
                "line_id": LINE_ID,
                "model_tag": MODEL_TAG,
                "variant": str(variant),
                "condition": str(data["condition"].iloc[0]),
                "requested_start_month": str(start_month),
                "start_date": pd.Timestamp(data["date"].iloc[0]).date().isoformat(),
                "end_date": pd.Timestamp(data["date"].iloc[-1]).date().isoformat(),
                "trading_days": int(len(data)),
                "start_equity": start_equity,
                "end_equity": end_equity,
                "total_return_pct": float((end_equity / start_equity - 1.0) * 100.0)
                if start_equity
                else np.nan,
                "max_drawdown_pct": float(_drawdown_pct(equity).min()),
                "sharpe": _sharpe_from_equity(equity),
                "stage022_cum_delta_end": float(
                    pd.to_numeric(data.get("stage022_cum_delta", pd.Series(0.0, index=data.index)), errors="coerce").iloc[-1]
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["variant", "requested_start_month"]).reset_index(drop=True)


def audit_goal_windows(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    data = curves[["requested_start_month", "date", "variant", "account_equity"]].copy()
    data.rename(columns={"account_equity": "equity"}, inplace=True)
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data["equity"] = pd.to_numeric(data["equity"], errors="coerce")
    data = data.dropna(subset=["date", "equity"]).sort_values(["variant", "requested_start_month", "date"])
    return s009_goal._run_audit(data)


def retention_vs_base(summary: pd.DataFrame) -> pd.DataFrame:
    data = summary.copy()
    if {"start_date", "end_date"}.issubset(data.columns):
        data["start_date"] = pd.to_datetime(data["start_date"], errors="coerce").dt.normalize()
        data["end_date"] = pd.to_datetime(data["end_date"], errors="coerce").dt.normalize()
        eligible = (
            data["start_date"].ge(OBJECTIVE_START_MIN)
            & data["start_date"].le(OBJECTIVE_START_MAX)
            & ((data["end_date"] - data["start_date"]).dt.days >= MIN_PERIOD_CALENDAR_DAYS)
        )
        data = data.loc[eligible].copy()
    base = data[data["variant"].eq(BASE_VARIANT)][["requested_start_month", "total_return_pct"]].rename(
        columns={"total_return_pct": "base_total_return_pct"}
    )
    merged = data.merge(base, on="requested_start_month", how="left")
    merged["return_retention_vs_base"] = merged["total_return_pct"] / merged["base_total_return_pct"].replace(
        0.0, np.nan
    )
    merged["passes_80pct_retention"] = merged["total_return_pct"].ge(
        merged["base_total_return_pct"] * 0.8
    ).astype("int64")
    return merged[
        [
            "variant",
            "condition",
            "requested_start_month",
            "total_return_pct",
            "base_total_return_pct",
            "return_retention_vs_base",
            "passes_80pct_retention",
        ]
    ].sort_values(["variant", "requested_start_month"]).reset_index(drop=True)


def variant_goal_table(aggregate: pd.DataFrame, retention: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    all_scope = (
        aggregate[aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")]
        .groupby("variant", as_index=False)
        .agg(
            all_gt1y_window_count=("window_count", "sum"),
            all_gt1y_negative_count=("negative_count", "sum"),
            all_gt1y_min_return_pct=("min_return_pct", "min"),
            all_gt1y_mean_return_pct=("mean_return_pct", "mean"),
        )
    )
    final_scope = (
        aggregate[aggregate["audit_scope"].eq("start_to_2026_06_30_only")]
        .groupby("variant", as_index=False)
        .agg(
            to_final_window_count=("window_count", "sum"),
            to_final_negative_count=("negative_count", "sum"),
            to_final_min_return_pct=("min_return_pct", "min"),
            to_final_mean_return_pct=("mean_return_pct", "mean"),
        )
    )
    ret_scope = retention.groupby("variant", as_index=False).agg(
        retention_80pct_pass_count=("passes_80pct_retention", "sum"),
        retention_rows=("passes_80pct_retention", "size"),
        min_retention=("return_retention_vs_base", "min"),
    )
    summary_scope = summary.groupby("variant", as_index=False).agg(
        median_total_return_pct=("total_return_pct", "median"),
        min_total_return_pct=("total_return_pct", "min"),
        worst_max_drawdown_pct=("max_drawdown_pct", "min"),
        median_sharpe=("sharpe", "median"),
        median_cum_delta_end=("stage022_cum_delta_end", "median"),
    )
    table = (
        all_scope.merge(final_scope, on="variant", how="outer")
        .merge(ret_scope, on="variant", how="outer")
        .merge(summary_scope, on="variant", how="outer")
    )
    table["objective_pass"] = (
        table["all_gt1y_negative_count"].fillna(1).eq(0)
        & table["to_final_negative_count"].fillna(1).eq(0)
        & table["retention_80pct_pass_count"].eq(table["retention_rows"])
    ).astype("int64")
    return table.sort_values(
        ["objective_pass", "all_gt1y_negative_count", "all_gt1y_min_return_pct", "min_retention"],
        ascending=[False, True, False, False],
    ).reset_index(drop=True)


def make_decision(
    tagged: pd.DataFrame,
    condition_summary: pd.DataFrame,
    lot_deltas: pd.DataFrame,
    variant_goal: pd.DataFrame,
    unmatched_delta_dates: int,
) -> dict[str, Any]:
    base = variant_goal[variant_goal["variant"].eq(BASE_VARIANT)].iloc[0].to_dict()
    candidates = variant_goal[~variant_goal["variant"].eq(BASE_VARIANT)].copy()
    best = (
        candidates.sort_values(
            ["objective_pass", "all_gt1y_negative_count", "all_gt1y_min_return_pct", "min_retention"],
            ascending=[False, True, False, False],
        )
        .head(1)
        .to_dict("records")
    )
    best_row = best[0] if best else {}
    pass_count = int(candidates["objective_pass"].sum()) if not candidates.empty else 0
    base_neg = int(base["all_gt1y_negative_count"])
    best_neg = int(best_row.get("all_gt1y_negative_count", 0)) if best_row else 0
    best_retention_full = bool(
        best_row
        and int(best_row.get("retention_80pct_pass_count", -1)) == int(best_row.get("retention_rows", 0))
    )
    if pass_count > 0:
        decision = "stage022_xsmom_confirmed_quality_has_goal_candidate_needs_true_engine"
        continue_after = "有。proxy 达到目标门，下一步必须冻结条件进入真实引擎/保证金/整数手审计。"
    elif best_row and best_neg < base_neg and best_retention_full:
        decision = "stage022_xsmom_confirmed_quality_improves_left_tail_need_failure_attribution"
        continue_after = "有但未达标。xsmom 确认能改善左尾且保留收益，下一步归因剩余负窗口并评估真实引擎。"
    else:
        decision = "stage022_xsmom_confirmation_not_promoted_keep_readonly"
        continue_after = "有限。若不能比 Stage013/Stage010 proxy 改善左尾，不应继续调同一 xsmom 确认条件。"
    stable = condition_summary[
        condition_summary.get("stable_quality_candidate", pd.Series(False, index=condition_summary.index)).astype(bool)
    ].copy()
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "add_risk_fraction": ADD_RISK_FRACTION,
        "input_paths": {
            "quality_events": str(QUALITY_EVENTS_PATH),
            "satellite_daily": str(SATELLITE_DAILY_PATH),
            "base_curves": str(STAGE013_CURVES_PATH),
        },
        "analysis_scope": {
            "tagged_event_count": int(len(tagged)),
            "lot_delta_count": int(len(lot_deltas)),
            "condition_count": int(condition_summary["condition"].nunique()) if not condition_summary.empty else 0,
            "stable_condition_count": int(len(stable)),
            "unmatched_delta_dates": int(unmatched_delta_dates),
        },
        "base_all_gt1y_negative_count": base_neg,
        "base_all_gt1y_min_return_pct": float(base["all_gt1y_min_return_pct"]),
        "best_variant": str(best_row.get("variant", "")) if best_row else "",
        "best_all_gt1y_negative_count": best_neg,
        "best_all_gt1y_min_return_pct": float(best_row.get("all_gt1y_min_return_pct", np.nan)) if best_row else np.nan,
        "best_min_retention": float(best_row.get("min_retention", np.nan)) if best_row else np.nan,
        "best_median_total_return_pct": float(best_row.get("median_total_return_pct", np.nan)) if best_row else np.nan,
        "best_worst_max_drawdown_pct": float(best_row.get("worst_max_drawdown_pct", np.nan)) if best_row else np.nan,
        "objective_pass_variant_count": pass_count,
        "stable_conditions": stable["condition"].head(12).tolist() if not stable.empty else [],
        "decision": decision,
        "external_research_judgment": (
            "Meta-labeling/bet-sizing research supports using a secondary layer to decide confidence for a primary "
            "trend signal. This stage uses only entry-prior xsmom state and keeps the primary C9 direction unchanged."
        ),
        "overfit_reflection_before": (
            "否。只复用 Stage010/013 冻结质量条件和 Stage020 固定 xsmom 状态，且用前一交易日信号；不按产品、日期、方向或坏窗口调参。"
        ),
        "overfit_reflection_after": (
            "否。本阶段没有根据结果改 xsmom lookback/topN/权重；若失败后继续调这些细节，就是过拟合。"
        ),
        "continue_value_before": (
            "有价值。Stage021 说明 xsmom 不适合作独立收益袖，但它仍可能作为入场质量确认，直接服务 AI 高质量信号加风险目标。"
        ),
        "continue_value_after": continue_after,
        "official_live_impact": {
            "strategy_changed": False,
            "official_live_config_changed": False,
            "order_api_called": False,
            "ctp_connected": False,
            "research_only": True,
        },
        "variant_goal_table": variant_goal.to_dict(orient="records"),
        "top_condition_summary": _json_safe(condition_summary.head(20).to_dict("records")),
        "outputs": {
            "tagged_events": str(TAGGED_EVENTS_PATH),
            "condition_summary": str(CONDITION_SUMMARY_PATH),
            "lot_deltas": str(LOT_DELTAS_PATH),
            "curves": str(CURVES_PATH),
            "summary": str(SUMMARY_PATH),
            "goal_aggregate": str(GOAL_AGGREGATE_PATH),
            "goal_to_final": str(GOAL_TO_FINAL_PATH),
            "goal_fixed_horizon": str(GOAL_FIXED_HORIZON_PATH),
            "goal_worst_windows": str(GOAL_WORST_WINDOWS_PATH),
            "retention": str(RETENTION_PATH),
            "variant_goal": str(VARIANT_GOAL_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
            "stage_record": str(STAGE_RECORD_PATH),
        },
    }


def _plot(variant_goal: pd.DataFrame) -> None:
    shown = variant_goal.head(14).copy()
    fig, axes = plt.subplots(1, 2, figsize=(18, 7), constrained_layout=True)
    labels = shown["variant"].astype(str).str.replace("stage022_", "", regex=False).tolist()
    y = np.arange(len(shown))
    colors = np.where(shown["objective_pass"].astype(bool), "#16a34a", "#64748b")
    axes[0].barh(y, shown["all_gt1y_negative_count"], color=colors)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(labels, fontsize=7)
    axes[0].invert_yaxis()
    axes[0].set_title("Dense >1Y Negative Windows")
    axes[0].grid(True, axis="x", alpha=0.25)
    axes[1].barh(y, shown["all_gt1y_min_return_pct"], color=colors)
    axes[1].axvline(0.0, color="#111827", linestyle="--", linewidth=0.8)
    axes[1].set_yticks(y)
    axes[1].set_yticklabels(labels, fontsize=7)
    axes[1].invert_yaxis()
    axes[1].set_title("Worst >1Y Return %")
    axes[1].grid(True, axis="x", alpha=0.25)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(decision: dict[str, Any], condition_summary: pd.DataFrame, variant_goal: pd.DataFrame) -> None:
    text = f"""# Stage022 xsmom 入场确认加风险 proxy

- line_id：`{LINE_ID}`
- 记录时间：{decision["generated_at"]}
- 决策：`{decision["decision"]}`
- 阶段性质：closed-lot + curve proxy；不改官方 live config、不连接 CTP、不调用下单。

## 方法

- 主方向仍由 C9/Stage010 quality 事件决定，xsmom 只作为入场前一交易日可见的确认层。
- `xsmom aligned`：long 入场品种在前一交易日 xsmom long_products，或 short 入场品种在 short_products。
- `not opposed`：前一交易日 xsmom 已活跃，且入场方向没有落在反向列表。
- 加风险方式：选中 lot 在退出日叠加 `realized_pnl * {ADD_RISK_FRACTION:.0%}`，这是只读 proxy。
- 基础曲线：恢复线 Stage013 曲线；因此本阶段不是当前 Stage167 C9 真引擎证明。

## 目标门汇总

{_md_table(variant_goal[["variant", "all_gt1y_negative_count", "all_gt1y_min_return_pct", "to_final_negative_count", "min_retention", "median_total_return_pct", "worst_max_drawdown_pct", "objective_pass"]], max_rows=30)}

## 条件质量摘要

{_md_table(condition_summary[["condition", "event_count", "year_count", "positive_year_count", "total_pnl", "mean_pnl_lift", "bad_path_rate_delta_pp", "stable_quality_candidate"]], max_rows=30)}

## 结论

- 基准严格 `>1` 年负窗口：`{decision["base_all_gt1y_negative_count"]}`，最差 `{decision["base_all_gt1y_min_return_pct"]:.4f}%`。
- 最优候选：`{decision["best_variant"]}`，负窗口 `{decision["best_all_gt1y_negative_count"]}`，最差 `{decision["best_all_gt1y_min_return_pct"]:.4f}%`。
- 目标通过 variant 数：`{decision["objective_pass_variant_count"]}`。

## 反思

- 运行前过拟合反思：{decision["overfit_reflection_before"]}
- 运行后过拟合反思：{decision["overfit_reflection_after"]}
- 运行前继续价值反思：{decision["continue_value_before"]}
- 运行后继续价值反思：{decision["continue_value_after"]}
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], condition_summary: pd.DataFrame, variant_goal: pd.DataFrame) -> None:
    record = f"""# Stage022 xsmom 入场确认加风险 proxy

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision["generated_at"]}
- 阶段性质：closed-lot + curve proxy；不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否；若出现达标候选，也必须先转真实引擎/保证金/整数手审计

## 外部调研与判断

- 参考：meta-labeling / bet sizing、trend-following signal confidence、cross-sectional momentum alignment。
- 我的判断：方向应由 C9 主策略给出，二级层只负责决定哪些入场值得加风险；xsmom 作为独立收益袖失败后，作为入场确认仍值得只读验证。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage022_xsmom_entry_confirmation_proxy.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage022_xsmom_entry_confirmation.py`
- 新增参数：`ADD_RISK_FRACTION={ADD_RISK_FRACTION}`、`SPECS={list(SPECS)}`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 输入事件：Stage009 quality events。
- xsmom 状态：Stage020 satellite daily，使用入场前一交易日 long/short 产品列表。
- proxy：每个条件选中 lot 在退出日增加 `realized_pnl * 25%`。
- 基础曲线：Stage013 account-state pilot curves；不是 Stage167 current C9 真引擎。

## 结果

- tagged events：`{decision["analysis_scope"]["tagged_event_count"]}`
- lot deltas：`{decision["analysis_scope"]["lot_delta_count"]}`
- stable condition count：`{decision["analysis_scope"]["stable_condition_count"]}`
- 基准严格 `>1` 年负窗口：`{decision["base_all_gt1y_negative_count"]}`，最差 `{decision["base_all_gt1y_min_return_pct"]:.4f}%`
- 最优候选：`{decision["best_variant"]}`
- 最优候选严格 `>1` 年负窗口：`{decision["best_all_gt1y_negative_count"]}`，最差 `{decision["best_all_gt1y_min_return_pct"]:.4f}%`
- 最优候选最小收益保留：`{decision["best_min_retention"]:.4f}`
- 目标通过 variant 数：`{decision["objective_pass_variant_count"]}`
- 决策：`{decision["decision"]}`

## 目标门汇总

{_md_table(variant_goal[["variant", "all_gt1y_negative_count", "all_gt1y_min_return_pct", "to_final_negative_count", "min_retention", "median_total_return_pct", "worst_max_drawdown_pct", "objective_pass"]], max_rows=30)}

## 条件质量摘要

{_md_table(condition_summary[["condition", "event_count", "year_count", "positive_year_count", "total_pnl", "mean_pnl_lift", "bad_path_rate_delta_pp", "stable_quality_candidate"]], max_rows=30)}

## 过拟合反思

- 运行前判断：{decision["overfit_reflection_before"]}
- 运行后判断：{decision["overfit_reflection_after"]}

## 继续价值反思

- 运行前判断：{decision["continue_value_before"]}
- 运行后判断：{decision["continue_value_after"]}

## 输出文件

- tagged_events：`{TAGGED_EVENTS_PATH}`
- condition_summary：`{CONDITION_SUMMARY_PATH}`
- lot_deltas：`{LOT_DELTAS_PATH}`
- curves：`{CURVES_PATH}`
- goal_aggregate：`{GOAL_AGGREGATE_PATH}`
- retention：`{RETENTION_PATH}`
- chart：`{CHART_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`
"""
    STAGE_RECORD_PATH.write_text(record, encoding="utf-8")


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    events = _read_csv(QUALITY_EVENTS_PATH)
    satellite = _read_csv(SATELLITE_DAILY_PATH)
    tagged = attach_prior_xsmom_context(events, satellite)
    masks = condition_masks(tagged)
    condition_summary = build_condition_summary(tagged, masks)
    lot_deltas = build_condition_lot_deltas(tagged, masks)
    base_curves = _read_csv(STAGE013_CURVES_PATH, parse_dates=["date"])
    curves, unmatched = build_proxy_curves(base_curves, lot_deltas)
    summary = summarize_all(curves)
    aggregate, to_final, fixed, worst = audit_goal_windows(curves)
    retention = retention_vs_base(summary)
    variant_goal = variant_goal_table(aggregate, retention, summary)
    decision = make_decision(tagged, condition_summary, lot_deltas, variant_goal, unmatched)

    tagged.to_csv(TAGGED_EVENTS_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    condition_summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    lot_deltas.to_csv(LOT_DELTAS_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(GOAL_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    to_final.to_csv(GOAL_TO_FINAL_PATH, index=False, encoding="utf-8-sig")
    fixed.to_csv(GOAL_FIXED_HORIZON_PATH, index=False, encoding="utf-8-sig")
    worst.to_csv(GOAL_WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")
    variant_goal.to_csv(VARIANT_GOAL_PATH, index=False, encoding="utf-8-sig")
    _plot(variant_goal)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, condition_summary, variant_goal)
    _write_stage_record(decision, condition_summary, variant_goal)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
