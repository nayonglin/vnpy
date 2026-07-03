from __future__ import annotations

from dataclasses import replace
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
for path in (str(PORTFOLIO_DIR), str(Path(__file__).resolve().parent)):
    if path not in sys.path:
        sys.path.insert(0, path)

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660
from qmt_roll_official_live_config import LEGACY_STAGE372_LIVE_PROFILE_NAME, LEGACY_STAGE372_LIVE_VERSION


LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage017"
MODEL_TAG = "stage017_fixed_sleeve_blend_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage017_fixed_sleeve_blend_audit"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage017_fixed_sleeve_blend_audit"

C9_CURVES_PATH = (
    PORTFOLIO_DIR
    / "backtest_outputs"
    / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_curves_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv"
)

OFFICIAL_CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_stage372_curves_{MODEL_TAG}.csv"
COMBO_CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combo_curves_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_aggregate_{MODEL_TAG}.csv"
TO_FINAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_to_final_windows_{MODEL_TAG}.csv"
FIXED_HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_fixed_horizon_windows_{MODEL_TAG}.csv"
WORST_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_worst_windows_{MODEL_TAG}.csv"
RETENTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_retention_vs_c9_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_blend_goal_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
STAGE_RECORD_PATH = LINE_DIR / "stages" / "20260702_0524_stage017_fixed_sleeve_blend_audit.md"

CAPITAL = 150_000.0
ANALYSIS_END = pd.Timestamp("2026-06-30")
START_MONTHS = tuple(pd.date_range("2020-01-01", "2025-01-01", freq="6MS"))
OBJECTIVE_START_MIN = pd.Timestamp("2020-01-01")
OBJECTIVE_START_MAX = pd.Timestamp("2025-06-30")
MIN_PERIOD_CALENDAR_DAYS = 366
FIXED_HORIZON_DAYS = (366, 540, 730, 1095)
WORST_OUTPUT_ROWS = 1000

FIXED_C9_WEIGHTS = {
    "c9_100": 1.00,
    "c9_80_official_20": 0.80,
    "c9_70_official_30": 0.70,
    "c9_60_official_40": 0.60,
    "official_100": 0.00,
}
LEGACY_STAGE372_BASE_PROFILE_NAME = "stage526_200k_force95_to80_largest_margin_r080_pc25_maxpos4"
RECOVERY_BROKER_MARGIN_MULTIPLIER = 1.65
RECOVERY_MAX_SINGLE_CONTRACT_BROKER_MARGIN_TO_EQUITY = 0.20
RECOVERY_COOLDOWN_CALENDAR_DAYS = 20


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _month_text(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _normalize_curve(frame: pd.DataFrame, *, equity_column: str = "account_equity") -> pd.DataFrame:
    data = frame.copy()
    data["requested_start_month"] = data["requested_start_month"].astype(str)
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data["account_equity"] = pd.to_numeric(data[equity_column], errors="coerce")
    data = data.dropna(subset=["requested_start_month", "date", "account_equity"]).copy()
    parts: list[pd.DataFrame] = []
    for start_month, group in data.groupby("requested_start_month", sort=True):
        g = group.sort_values("date").drop_duplicates("date").copy()
        initial = float(g["account_equity"].iloc[0])
        if initial == 0.0:
            continue
        g["nav"] = g["account_equity"] / initial
        g["source_initial_equity"] = initial
        parts.append(g[["requested_start_month", "date", "account_equity", "nav", "source_initial_equity"]])
    return pd.concat(parts, ignore_index=True, sort=False) if parts else pd.DataFrame()


def build_fixed_weight_combo_curves(
    c9_curves: pd.DataFrame,
    official_curves: pd.DataFrame,
    c9_weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    weights = c9_weights or FIXED_C9_WEIGHTS
    c9 = _normalize_curve(c9_curves).rename(
        columns={"account_equity": "c9_account_equity", "nav": "c9_nav", "source_initial_equity": "c9_initial_equity"}
    )
    official = _normalize_curve(official_curves).rename(
        columns={
            "account_equity": "official_account_equity",
            "nav": "official_nav",
            "source_initial_equity": "official_initial_equity",
        }
    )
    merged = c9.merge(official, on=["requested_start_month", "date"], how="inner")
    rows: list[pd.DataFrame] = []
    for variant, c9_weight in weights.items():
        official_weight = 1.0 - float(c9_weight)
        data = merged.copy()
        data["variant"] = variant
        data["c9_weight"] = float(c9_weight)
        data["official_weight"] = official_weight
        data["combo_nav"] = data["c9_nav"] * float(c9_weight) + data["official_nav"] * official_weight
        data["account_equity"] = data["combo_nav"] * CAPITAL
        data["stage"] = STAGE
        data["model_tag"] = MODEL_TAG
        data["line_id"] = LINE_ID
        rows.append(data)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True, sort=False).sort_values(
        ["variant", "requested_start_month", "date"]
    ).reset_index(drop=True)


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


def summarize_curve(curve: pd.DataFrame, *, variant: str, requested_start_month: str) -> dict[str, Any]:
    data = curve.sort_values("date").drop_duplicates("date").copy()
    equity = pd.to_numeric(data["account_equity"], errors="coerce")
    start_equity = float(equity.iloc[0])
    end_equity = float(equity.iloc[-1])
    dd = _drawdown_pct(equity)
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "variant": variant,
        "requested_start_month": requested_start_month,
        "start_date": pd.Timestamp(data["date"].iloc[0]).date().isoformat(),
        "end_date": pd.Timestamp(data["date"].iloc[-1]).date().isoformat(),
        "trading_days": int(len(data)),
        "start_equity": start_equity,
        "end_equity": end_equity,
        "total_return_pct": float((end_equity / start_equity - 1.0) * 100.0) if start_equity else np.nan,
        "max_drawdown_pct": float(dd.min()),
        "sharpe": _sharpe_from_equity(equity),
        "min_equity": float(equity.min()),
    }


def _load_c9_curves() -> pd.DataFrame:
    data = _read_csv(C9_CURVES_PATH)
    data["requested_start_month"] = data["requested_start_month"].astype(str)
    wanted = {_month_text(start) for start in START_MONTHS}
    data = data[data["requested_start_month"].isin(wanted)].copy()
    return data[["requested_start_month", "date", "account_equity"]].reset_index(drop=True)


def _legacy_stage372_spec(metadata: dict[str, Any]) -> s653.ForcedVariant:
    identity_map = s653.s519._product_identity_cluster_map(metadata)
    for spec in s653._variants(identity_map):
        if spec.capital.variant == LEGACY_STAGE372_LIVE_PROFILE_NAME:
            return replace(spec)
        if spec.capital.variant == LEGACY_STAGE372_BASE_PROFILE_NAME:
            capital = replace(
                spec.capital,
                variant=LEGACY_STAGE372_LIVE_PROFILE_NAME,
                label="20w legacy Stage372 recovery sleeve",
                note=(
                    "Legacy Stage372 official live: force95->80 base plus one-lot recovery sleeve only "
                    "for clean long_case1a/short_case1a structure recovery at the 0.1 risk floor."
                ),
            )
            overrides = {
                **spec.overrides,
                "enable_streak_entry_structure_risk_recovery": True,
                "streak_entry_structure_recovery_signals": "long_case1a,short_case1a",
                "streak_entry_structure_recovery_min_multiplier": 1.0,
                "streak_entry_structure_recovery_require_flat_portfolio": True,
                "streak_entry_structure_recovery_max_same_direction_corr": 0.30,
                "streak_entry_structure_recovery_require_rsi_confirmation": False,
                "enable_recovery_sleeve": True,
                "recovery_sleeve_base_multiplier_max": 0.1000001,
                "recovery_sleeve_broker_margin_multiplier": RECOVERY_BROKER_MARGIN_MULTIPLIER,
                "recovery_sleeve_max_single_contract_broker_margin_to_equity": (
                    RECOVERY_MAX_SINGLE_CONTRACT_BROKER_MARGIN_TO_EQUITY
                ),
                "recovery_sleeve_cooldown_days": RECOVERY_COOLDOWN_CALENDAR_DAYS,
                "recovery_sleeve_volume": 1,
            }
            return replace(spec, capital=capital, overrides=overrides, profile="forced_margin_95_to_80_recovery_sleeve")
    raise ValueError(f"legacy Stage372 base spec not found: {LEGACY_STAGE372_BASE_PROFILE_NAME}")


def _run_official_stage372_curves() -> pd.DataFrame:
    metadata = s513._metadata()
    spec = _legacy_stage372_spec(metadata)
    rows: list[pd.DataFrame] = []
    for idx, start in enumerate(START_MONTHS, start=1):
        start_ts = pd.Timestamp(start).normalize()
        print(
            f"[stage017] running {LEGACY_STAGE372_LIVE_VERSION} {idx}/{len(START_MONTHS)} "
            f"{start_ts.date()} -> {ANALYSIS_END.date()}",
            flush=True,
        )
        combined, forced_events = s660._run_independent_window(
            spec=replace(spec),
            metadata=metadata,
            analysis_start=start_ts,
            analysis_end=ANALYSIS_END,
        )
        data = combined.copy()
        data["requested_start_month"] = _month_text(start_ts)
        data["requested_start"] = start_ts.date().isoformat()
        data["requested_end"] = ANALYSIS_END.date().isoformat()
        data["forced_margin_deleverage_count_total"] = int(len(forced_events))
        rows.append(data[["requested_start_month", "requested_start", "requested_end", "date", "account_equity", "net_pnl", "trade_count", "slippage", "forced_margin_deleverage_count_total"]])
    result = pd.concat(rows, ignore_index=True, sort=False)
    result["date"] = pd.to_datetime(result["date"], errors="coerce").dt.normalize()
    return result.sort_values(["requested_start_month", "date"]).reset_index(drop=True)


def _summarize_all(combo_curves: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (variant, start_month), group in combo_curves.groupby(["variant", "requested_start_month"], sort=True):
        rows.append(summarize_curve(group, variant=str(variant), requested_start_month=str(start_month)))
    return pd.DataFrame(rows).sort_values(["variant", "requested_start_month"]).reset_index(drop=True)


def _ret_pct(start_equity: float, end_equity: float) -> float:
    return float((end_equity / start_equity - 1.0) * 100.0) if start_equity else np.nan


def _audit_group(variant: str, source_start: str, group: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    data = group.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    dates = data["date"].to_numpy(dtype="datetime64[ns]")
    equity = pd.to_numeric(data["account_equity"], errors="coerce").to_numpy(dtype=float)
    start_mask = (data["date"] >= OBJECTIVE_START_MIN) & (data["date"] <= OBJECTIVE_START_MAX)
    start_indices = np.flatnonzero(start_mask.to_numpy())
    aggregate_rows: list[dict[str, Any]] = []
    to_final_rows: list[dict[str, Any]] = []
    fixed_rows: list[dict[str, Any]] = []
    worst_rows: list[dict[str, Any]] = []

    all_count = 0
    all_positive = 0
    all_negative = 0
    all_min = np.inf
    all_sum = 0.0
    final_count = 0
    final_negative = 0
    final_min = np.inf
    final_sum = 0.0

    for idx in start_indices:
        start_date = pd.Timestamp(dates[idx])
        start_equity = float(equity[idx])
        min_end_date = start_date + pd.Timedelta(days=MIN_PERIOD_CALENDAR_DAYS)
        min_end_idx = int(np.searchsorted(dates, np.datetime64(min_end_date), side="left"))
        if min_end_idx >= len(dates):
            continue
        end_indices = np.arange(min_end_idx, len(dates), dtype=int)
        returns = (equity[end_indices] / start_equity - 1.0) * 100.0
        valid = np.isfinite(returns)
        returns = returns[valid]
        valid_end_indices = end_indices[valid]
        if len(returns) == 0:
            continue

        all_count += int(len(returns))
        all_positive += int((returns > 0.0).sum())
        all_negative += int((returns < 0.0).sum())
        all_min = min(all_min, float(returns.min()))
        all_sum += float(returns.sum())

        negative_positions = np.flatnonzero(returns < 0.0)
        if len(negative_positions):
            k = min(3, len(negative_positions))
            local = negative_positions[np.argpartition(returns[negative_positions], k - 1)[:k]]
            for pos in local:
                end_idx = int(valid_end_indices[pos])
                worst_rows.append(
                    {
                        "variant": variant,
                        "source_start_month": source_start,
                        "window_type": "all_gt_1y",
                        "start_date": start_date.date().isoformat(),
                        "end_date": pd.Timestamp(dates[end_idx]).date().isoformat(),
                        "period_calendar_days": int((pd.Timestamp(dates[end_idx]) - start_date).days),
                        "period_trading_days": int(end_idx - idx + 1),
                        "return_pct": float(returns[pos]),
                        "start_equity": start_equity,
                        "end_equity": float(equity[end_idx]),
                    }
                )

        final_ret = _ret_pct(start_equity, float(equity[-1]))
        final_count += 1
        final_negative += int(final_ret < 0.0)
        final_min = min(final_min, final_ret)
        final_sum += final_ret
        to_final_rows.append(
            {
                "variant": variant,
                "source_start_month": source_start,
                "start_date": start_date.date().isoformat(),
                "end_date": pd.Timestamp(dates[-1]).date().isoformat(),
                "period_calendar_days": int((pd.Timestamp(dates[-1]) - start_date).days),
                "period_trading_days": int(len(dates) - idx),
                "return_pct": final_ret,
                "positive_return": int(final_ret > 0.0),
            }
        )

        for horizon in FIXED_HORIZON_DAYS:
            target_date = start_date + pd.Timedelta(days=horizon)
            end_idx = int(np.searchsorted(dates, np.datetime64(target_date), side="left"))
            if end_idx >= len(dates):
                continue
            ret = _ret_pct(start_equity, float(equity[end_idx]))
            fixed_rows.append(
                {
                    "variant": variant,
                    "source_start_month": source_start,
                    "horizon_days": horizon,
                    "start_date": start_date.date().isoformat(),
                    "end_date": pd.Timestamp(dates[end_idx]).date().isoformat(),
                    "actual_calendar_days": int((pd.Timestamp(dates[end_idx]) - start_date).days),
                    "period_trading_days": int(end_idx - idx + 1),
                    "return_pct": ret,
                    "positive_return": int(ret > 0.0),
                }
            )

    aggregate_rows.append(
        {
            "variant": variant,
            "source_start_month": source_start,
            "audit_scope": "all_trading_end_dates_gt_1y",
            "window_count": all_count,
            "positive_count": all_positive,
            "negative_count": all_negative,
            "negative_rate_pct": float(all_negative / all_count * 100.0) if all_count else np.nan,
            "min_return_pct": float(all_min) if np.isfinite(all_min) else np.nan,
            "mean_return_pct": float(all_sum / all_count) if all_count else np.nan,
            "is_independent_daily_cold_start": 0,
        }
    )
    aggregate_rows.append(
        {
            "variant": variant,
            "source_start_month": source_start,
            "audit_scope": "start_to_2026_06_30_only",
            "window_count": final_count,
            "positive_count": int(final_count - final_negative),
            "negative_count": final_negative,
            "negative_rate_pct": float(final_negative / final_count * 100.0) if final_count else np.nan,
            "min_return_pct": float(final_min) if np.isfinite(final_min) else np.nan,
            "mean_return_pct": float(final_sum / final_count) if final_count else np.nan,
            "is_independent_daily_cold_start": 0,
        }
    )
    return aggregate_rows, to_final_rows, fixed_rows, worst_rows


def audit_goal_windows(combo_curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    aggregate_rows: list[dict[str, Any]] = []
    to_final_rows: list[dict[str, Any]] = []
    fixed_rows: list[dict[str, Any]] = []
    worst_rows: list[dict[str, Any]] = []
    for (variant, source_start), group in combo_curves.groupby(["variant", "requested_start_month"], sort=True):
        agg, final, fixed, worst = _audit_group(str(variant), str(source_start), group)
        aggregate_rows.extend(agg)
        to_final_rows.extend(final)
        fixed_rows.extend(fixed)
        worst_rows.extend(worst)
    aggregate = pd.DataFrame(aggregate_rows)
    to_final = pd.DataFrame(to_final_rows)
    fixed = pd.DataFrame(fixed_rows)
    worst = pd.DataFrame(worst_rows)
    if not worst.empty:
        worst = worst.sort_values("return_pct").head(WORST_OUTPUT_ROWS).reset_index(drop=True)
    return aggregate, to_final, fixed, worst


def retention_vs_c9(summary: pd.DataFrame) -> pd.DataFrame:
    c9 = summary[summary["variant"].eq("c9_100")][["requested_start_month", "total_return_pct"]].rename(
        columns={"total_return_pct": "c9_total_return_pct"}
    )
    merged = summary.merge(c9, on="requested_start_month", how="left")
    merged["return_retention_vs_c9"] = merged["total_return_pct"] / merged["c9_total_return_pct"].replace(0.0, np.nan)
    merged["passes_80pct_retention"] = merged["total_return_pct"].ge(merged["c9_total_return_pct"] * 0.8).astype("int64")
    return merged[
        [
            "variant",
            "requested_start_month",
            "total_return_pct",
            "c9_total_return_pct",
            "return_retention_vs_c9",
            "passes_80pct_retention",
        ]
    ].sort_values(["variant", "requested_start_month"]).reset_index(drop=True)


def _plot(summary: pd.DataFrame, aggregate: pd.DataFrame, retention: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10), constrained_layout=True)
    summary_agg = summary.groupby("variant", as_index=False).agg(
        median_return_pct=("total_return_pct", "median"),
        worst_dd_pct=("max_drawdown_pct", "min"),
        median_sharpe=("sharpe", "median"),
    )
    axes[0, 0].bar(summary_agg["variant"], summary_agg["median_return_pct"], color="#2563eb")
    axes[0, 0].set_title("Median start-to-final return")
    axes[0, 0].tick_params(axis="x", rotation=35)
    axes[0, 0].grid(True, axis="y", alpha=0.25)
    axes[0, 1].bar(summary_agg["variant"], summary_agg["worst_dd_pct"], color="#dc2626")
    axes[0, 1].set_title("Worst max drawdown")
    axes[0, 1].tick_params(axis="x", rotation=35)
    axes[0, 1].grid(True, axis="y", alpha=0.25)
    all_scope = (
        aggregate[aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")]
        .groupby("variant", as_index=False)
        .agg(negative_count=("negative_count", "sum"), window_count=("window_count", "sum"), min_return_pct=("min_return_pct", "min"))
    )
    all_scope["negative_rate_pct"] = all_scope["negative_count"] / all_scope["window_count"].replace(0, np.nan) * 100.0
    axes[1, 0].bar(all_scope["variant"], all_scope["negative_rate_pct"], color="#f97316")
    axes[1, 0].set_title("Dense >1Y negative window rate")
    axes[1, 0].tick_params(axis="x", rotation=35)
    axes[1, 0].grid(True, axis="y", alpha=0.25)
    ret = retention.groupby("variant", as_index=False).agg(pass_count=("passes_80pct_retention", "sum"), rows=("passes_80pct_retention", "size"))
    ret["pass_rate_pct"] = ret["pass_count"] / ret["rows"].replace(0, np.nan) * 100.0
    axes[1, 1].bar(ret["variant"], ret["pass_rate_pct"], color="#16a34a")
    axes[1, 1].set_title("80% full-return retention pass rate vs C9")
    axes[1, 1].tick_params(axis="x", rotation=35)
    axes[1, 1].grid(True, axis="y", alpha=0.25)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _decision(summary: pd.DataFrame, aggregate: pd.DataFrame, retention: pd.DataFrame) -> dict[str, Any]:
    all_scope = (
        aggregate[aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")]
        .groupby("variant", as_index=False)
        .agg(
            all_gt1y_window_count=("window_count", "sum"),
            all_gt1y_negative_count=("negative_count", "sum"),
            all_gt1y_min_return_pct=("min_return_pct", "min"),
        )
    )
    final_scope = (
        aggregate[aggregate["audit_scope"].eq("start_to_2026_06_30_only")]
        .groupby("variant", as_index=False)
        .agg(to_final_window_count=("window_count", "sum"), to_final_negative_count=("negative_count", "sum"), to_final_min_return_pct=("min_return_pct", "min"))
    )
    ret_scope = retention.groupby("variant", as_index=False).agg(
        retention_80pct_pass_count=("passes_80pct_retention", "sum"),
        retention_rows=("passes_80pct_retention", "size"),
        min_retention=("return_retention_vs_c9", "min"),
    )
    merged = all_scope.merge(final_scope, on="variant", how="outer").merge(ret_scope, on="variant", how="outer")
    merged["objective_pass"] = (
        merged["all_gt1y_negative_count"].fillna(1).eq(0)
        & merged["to_final_negative_count"].fillna(1).eq(0)
        & merged["retention_80pct_pass_count"].eq(merged["retention_rows"])
    )
    c9_row = merged[merged["variant"].eq("c9_100")].iloc[0].to_dict()
    non_c9 = merged[~merged["variant"].eq("c9_100")].copy()
    pass_rows = non_c9[non_c9["objective_pass"]]
    if not pass_rows.empty:
        best = pass_rows.sort_values(["all_gt1y_negative_count", "min_retention"], ascending=[True, False]).iloc[0].to_dict()
        decision = "stage017_fixed_sleeve_blend_has_goal_candidate_needs_true_engine_ab"
        reason = "固定权重 C9/Stage372 组合在密集 >1 年窗口和 80% 收益保留上通过代理门，值得进入真实组合引擎 A/B。"
    else:
        best = non_c9.sort_values(["all_gt1y_negative_count", "all_gt1y_min_return_pct"], ascending=[True, False]).iloc[0].to_dict()
        decision = "stage017_fixed_sleeve_blend_not_goal_keep_readonly"
        reason = "固定权重 C9/Stage372 组合不能同时清零密集 >1 年负窗口并保留 C9 80% 全周期收益。"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "start_months": [_month_text(item) for item in START_MONTHS],
        "analysis_end": ANALYSIS_END.date().isoformat(),
        "weights": FIXED_C9_WEIGHTS,
        "objective_start_min": OBJECTIVE_START_MIN.date().isoformat(),
        "objective_start_max": OBJECTIVE_START_MAX.date().isoformat(),
        "min_period_calendar_days": MIN_PERIOD_CALENDAR_DAYS,
        "is_independent_daily_cold_start": False,
        "c9_all_gt1y_negative_count": int(c9_row["all_gt1y_negative_count"]),
        "c9_all_gt1y_min_return_pct": float(c9_row["all_gt1y_min_return_pct"]),
        "best_non_c9_variant": str(best["variant"]),
        "best_non_c9_all_gt1y_negative_count": int(best["all_gt1y_negative_count"]),
        "best_non_c9_all_gt1y_min_return_pct": float(best["all_gt1y_min_return_pct"]),
        "best_non_c9_min_retention": float(best["min_retention"]),
        "objective_pass_variant_count": int(merged["objective_pass"].sum()),
        "strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "formal_ab_triggered": False,
        "decision": decision,
        "decision_reason": reason,
        "external_research_judgment": (
            "Trend-following robustness research and pysystemtrade practice support diversification across rules/sleeves, "
            "but only if fixed blends improve path robustness without cutting the convex right tail."
        ),
        "overfit_reflection_before": (
            "否。组合权重是预声明的粗固定资金袖，不按具体坏窗口、品种、方向或月份调参。"
        ),
        "overfit_reflection_after": (
            "若失败后继续扫 65/75/85 或按坏窗口动态切换 C9/Stage372，就是过拟合；固定组合只保留为结构审计。"
        ),
        "continue_value_before": (
            "有价值。Stage074/075 证明单纯压低早期风险会伤右尾，固定多母本组合是不同结构。"
        ),
        "continue_value_after": (
            "若没有通过目标门，继续做细权重价值低；更应转全新外生信息源或真正低相关收益腿。"
        ),
        "variant_goal_table": merged.to_dict(orient="records"),
        "outputs": {
            "official_curves": str(OFFICIAL_CURVES_PATH),
            "combo_curves": str(COMBO_CURVES_PATH),
            "summary": str(SUMMARY_PATH),
            "aggregate": str(AGGREGATE_PATH),
            "to_final": str(TO_FINAL_PATH),
            "fixed_horizon": str(FIXED_HORIZON_PATH),
            "worst_windows": str(WORST_WINDOWS_PATH),
            "retention": str(RETENTION_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(
    decision: dict[str, Any],
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    to_final: pd.DataFrame,
    fixed: pd.DataFrame,
    worst: pd.DataFrame,
    retention: pd.DataFrame,
) -> None:
    variant_goal = pd.DataFrame(decision["variant_goal_table"])
    text = f"""# Stage017 Fixed Sleeve Blend Audit

- line_id：`{LINE_ID}`
- 记录时间：{decision["generated_at"]}
- 决策：`{decision["decision"]}`
- 阶段性质：固定权重 C9/Stage372 标准化 NAV 资金袖组合审计；不改实盘配置、不连接 CTP、不调用订单 API。

## 假设

当前 C9/15w 右尾强但左尾厚，Stage372/20w 更防守。若二者不是完全同一风险形状，固定资金袖组合可能降低任意起点左尾，同时尽量保留 C9 右尾。

## 方法

- C9 输入：Stage167 当前线上 C9/15w 多周期曲线。
- Stage372 输入：本阶段只读重跑 `official_live_stage372_20w_recovery_sleeve`，起点与 C9 对齐。
- 组合方法：每个 sleeve 先归一化为 NAV，再按固定权重合成，最后映射回 `150,000` 资金曲线。
- 固定权重：`{json.dumps(FIXED_C9_WEIGHTS, ensure_ascii=False)}`
- 审计：对 `2020-01-01` 到 `2025-06-30` 的所有曲线内交易日起点，检查所有 `>{MIN_PERIOD_CALENDAR_DAYS - 1}` 自然日终点收益；另看到 `2026-06-30`、固定 horizon 和相对 C9 的 80% 收益保留。
- 注意：这是 curve-level 组合审计，不是独立任意日冷启动真引擎证明。

## 目标门汇总

{_md_table(variant_goal, max_rows=20)}

## 多起点摘要

{_md_table(summary, max_rows=30)}

## 聚合窗口

{_md_table(aggregate, max_rows=60)}

## 80% 收益保留

{_md_table(retention, max_rows=60)}

## 最差窗口

{_md_table(worst, max_rows=40)}

## 结论

- {decision["decision_reason"]}
- 本阶段不改变 AI 池、品种池、C9 逻辑或实盘链路。

## 过拟合反思

- 运行前：{decision["overfit_reflection_before"]}
- 运行后：{decision["overfit_reflection_after"]}

## 继续价值反思

- 运行前：{decision["continue_value_before"]}
- 运行后：{decision["continue_value_after"]}
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def _write_stage_record(
    decision: dict[str, Any],
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    worst: pd.DataFrame,
    retention: pd.DataFrame,
) -> None:
    variant_goal = pd.DataFrame(decision["variant_goal_table"])
    text = f"""# Stage017 Fixed Sleeve Blend Audit

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision["generated_at"]}
- 阶段性质：当前重建 C9/15w 与 previous Stage372/20w 固定资金袖组合只读审计
- 是否重要突破：否
- 是否触发A/B：触发 A/B 候选门检查，但未进入正式 A/B；本阶段只是 curve-level 组合审计

## 外部调研与判断

- 参考资料：pysystemtrade 多规则组合/forecast diversification、managed futures/trend following 分散化研究、Rob Carver 对趋势系统 robustness 与过拟合的公开讨论。
- 我的判断：固定多母本组合是比“账户回撤阈值降风险”更结构化的账户外层，因为它不要求根据近期亏损主动砍掉 C9 持仓；但只有在不明显牺牲 C9 右尾且能降低密集左尾时才有继续价值。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage017_fixed_sleeve_blend_audit.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage017_fixed_sleeve_blend_audit.py`
- 新增参数：`FIXED_C9_WEIGHTS={json.dumps(FIXED_C9_WEIGHTS, ensure_ascii=False)}`、`START_MONTHS={[ _month_text(item) for item in START_MONTHS ]}`、`ANALYSIS_END={ANALYSIS_END.date()}`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- C9 密集 >1 年负窗口数：`{decision["c9_all_gt1y_negative_count"]}`
- C9 密集 >1 年最差收益：`{decision["c9_all_gt1y_min_return_pct"]:.4f}%`
- 最优非 C9 组合：`{decision["best_non_c9_variant"]}`
- 最优非 C9 组合密集 >1 年负窗口数：`{decision["best_non_c9_all_gt1y_negative_count"]}`
- 最优非 C9 组合密集 >1 年最差收益：`{decision["best_non_c9_all_gt1y_min_return_pct"]:.4f}%`
- 最优非 C9 组合最小收益保留：`{decision["best_non_c9_min_retention"]:.4f}`
- 目标通过 variant 数：`{decision["objective_pass_variant_count"]}`
- 决策：`{decision["decision"]}`
- 原因：{decision["decision_reason"]}

## 目标门汇总

{_md_table(variant_goal, max_rows=20)}

## 多起点摘要

{_md_table(summary, max_rows=30)}

## 聚合窗口

{_md_table(aggregate, max_rows=60)}

## 80% 收益保留

{_md_table(retention, max_rows=60)}

## 最差窗口

{_md_table(worst, max_rows=40)}

## 过拟合反思

- 运行前判断：{decision["overfit_reflection_before"]}
- 运行后判断：{decision["overfit_reflection_after"]}

## 继续价值反思

- 运行前判断：{decision["continue_value_before"]}
- 运行后判断：{decision["continue_value_after"]}

## 输出文件

- official_curves: `{OFFICIAL_CURVES_PATH}`
- combo_curves: `{COMBO_CURVES_PATH}`
- summary: `{SUMMARY_PATH}`
- aggregate: `{AGGREGATE_PATH}`
- to_final: `{TO_FINAL_PATH}`
- fixed_horizon: `{FIXED_HORIZON_PATH}`
- worst_windows: `{WORST_WINDOWS_PATH}`
- retention: `{RETENTION_PATH}`
- chart: `{CHART_PATH}`
- decision: `{DECISION_PATH}`
- report: `{REPORT_PATH}`
"""
    STAGE_RECORD_PATH.write_text(text, encoding="utf-8")


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    c9_curves = _load_c9_curves()
    official_curves = _run_official_stage372_curves()
    official_curves.to_csv(OFFICIAL_CURVES_PATH, index=False, encoding="utf-8-sig")
    combo_curves = build_fixed_weight_combo_curves(c9_curves, official_curves, FIXED_C9_WEIGHTS)
    summary = _summarize_all(combo_curves)
    aggregate, to_final, fixed, worst = audit_goal_windows(combo_curves)
    retention = retention_vs_c9(summary)
    decision = _decision(summary, aggregate, retention)

    combo_curves.to_csv(COMBO_CURVES_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    to_final.to_csv(TO_FINAL_PATH, index=False, encoding="utf-8-sig")
    fixed.to_csv(FIXED_HORIZON_PATH, index=False, encoding="utf-8-sig")
    worst.to_csv(WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")
    _plot(summary, aggregate, retention)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, summary, aggregate, to_final, fixed, worst, retention)
    _write_stage_record(decision, summary, aggregate, worst, retention)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
