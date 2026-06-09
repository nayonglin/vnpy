from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage723_throttle_external_bar_features as s723
from qmt_roll_official_live_config import OFFICIAL_LIVE_CAPITAL


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage730_account_state_throttle_feature_v1"
OUTPUT_PREFIX = "qmt_roll_stage730_account_state_throttle_feature"
LINE_ID = "futures_trend_winner_trade_forensics"

SOURCE_STAGE723_ENRICHED_PATH = s723.ENRICHED_PATH
SOURCE_STAGE719_POSITIONS_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage719_official_winner_trade_forensics_positions_"
    "stage719_official_winner_trade_forensics_v1.csv"
)

ENRICHED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_enriched_candidates_{MODEL_TAG}.csv"
FEATURE_METRICS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_metrics_{MODEL_TAG}.csv"
YEAR_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_detail_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

MIN_RELIABLE_ROWS = 30
MIN_RELIABLE_YEARS = 4
MIN_RELIABLE_PRODUCTS = 6
MAX_DOMINANT_PRODUCT_SHARE = 0.35
MAX_DOMINANT_YEAR_SHARE = 0.45
MIN_GOOD_LIFT_PP = 10.0
MAX_BAD_RATE_PCT = 60.0
MIN_GOOD_YEARS = 4
MIN_POSITIVE_SCORE_YEARS = 4

ACCOUNT_STATE_FEATURES = [
    "account_dd_bucket",
    "account_ret20_bucket",
    "account_ret60_bucket",
    "account_ret20_60_bucket",
    "account_drawdown_age_bucket",
    "account_ma200_bucket",
    "account_recovery_phase_bucket",
    "account_margin_usage_bucket",
    "account_free_capital_bucket",
    "account_book_state_bucket",
    "loss_streak_depth_bucket",
    "account_state_plus_edge_bucket",
]


def _json_safe(value: Any) -> Any:
    return s723._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s723._md_table(frame, max_rows=max_rows)


def _safe_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _load_candidates() -> pd.DataFrame:
    if not SOURCE_STAGE723_ENRICHED_PATH.exists():
        raise FileNotFoundError(SOURCE_STAGE723_ENRICHED_PATH)
    data = pd.read_csv(SOURCE_STAGE723_ENRICHED_PATH, encoding="utf-8-sig")
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    for column in [
        "candidate_index",
        "h40_barrier_good",
        "h40_barrier_bad",
        "h40_path_score_r",
        "h40_mfe_r",
        "h40_mae_r",
        "year",
        "estimated_equity",
        "portfolio_drawdown_pct",
        "portfolio_equity_high_water",
        "total_margin_in_use_before",
        "free_capital",
        "active_positions_before",
        "loss_streak",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    if "year" not in data.columns:
        data["year"] = data["date"].dt.year
    data = data[data["h40_barrier_good"].notna()].copy()
    if data.empty:
        raise RuntimeError("no H40-labeled candidates")
    return data.sort_values(["date", "candidate_index"]).reset_index(drop=True)


def _load_daily_account() -> pd.DataFrame:
    if not SOURCE_STAGE719_POSITIONS_PATH.exists():
        raise FileNotFoundError(SOURCE_STAGE719_POSITIONS_PATH)
    positions = pd.read_csv(SOURCE_STAGE719_POSITIONS_PATH, encoding="utf-8-sig")
    positions["date"] = pd.to_datetime(positions["date"], errors="coerce").dt.normalize()
    positions["net_pnl"] = pd.to_numeric(positions["net_pnl"], errors="coerce").fillna(0.0)
    positions["commission"] = pd.to_numeric(positions.get("commission", 0.0), errors="coerce").fillna(0.0)
    positions["slippage"] = pd.to_numeric(positions.get("slippage", 0.0), errors="coerce").fillna(0.0)
    positions["trade_count"] = pd.to_numeric(positions.get("trade_count", 0.0), errors="coerce").fillna(0.0)
    daily = (
        positions.groupby("date", as_index=False)
        .agg(
            account_daily_net_pnl=("net_pnl", "sum"),
            account_daily_commission=("commission", "sum"),
            account_daily_slippage=("slippage", "sum"),
            account_daily_trade_count=("trade_count", "sum"),
        )
        .sort_values("date")
    )
    daily["account_equity"] = float(OFFICIAL_LIVE_CAPITAL) + daily["account_daily_net_pnl"].cumsum()
    daily["account_ret1"] = daily["account_equity"].pct_change().fillna(0.0)
    daily["account_ret20"] = daily["account_equity"] / daily["account_equity"].shift(20) - 1.0
    daily["account_ret60"] = daily["account_equity"] / daily["account_equity"].shift(60) - 1.0
    daily["account_sma200"] = daily["account_equity"].rolling(200, min_periods=20).mean()
    daily["account_ma200_gap"] = daily["account_equity"] / daily["account_sma200"] - 1.0
    daily["account_equity_high_water_calc"] = daily["account_equity"].cummax()
    daily["account_drawdown_calc"] = 1.0 - daily["account_equity"] / daily["account_equity_high_water_calc"]
    days_since_high: list[float] = []
    last_high_date: pd.Timestamp | None = None
    for date, equity, high_water in zip(
        daily["date"], daily["account_equity"], daily["account_equity_high_water_calc"]
    ):
        if np.isfinite(equity) and np.isfinite(high_water) and abs(float(equity) - float(high_water)) < 1e-8:
            last_high_date = pd.Timestamp(date)
        days_since_high.append((pd.Timestamp(date) - last_high_date).days if last_high_date is not None else np.nan)
    daily["account_days_since_high"] = days_since_high
    daily["account_vol20"] = daily["account_ret1"].rolling(20, min_periods=5).std() * np.sqrt(252.0)
    daily["account_vol60"] = daily["account_ret1"].rolling(60, min_periods=20).std() * np.sqrt(252.0)
    return daily


def _bucket_drawdown(value: float) -> str:
    if pd.isna(value):
        return "missing"
    if value <= 0.05:
        return "near_high_le5"
    if value <= 0.15:
        return "dd_5_15"
    if value <= 0.25:
        return "dd_15_25"
    return "dd_gt25"


def _bucket_ret20(value: float) -> str:
    if pd.isna(value):
        return "missing"
    if value >= 0.10:
        return "ret20_strong_up_ge10"
    if value >= 0.02:
        return "ret20_up_2_10"
    if value >= -0.05:
        return "ret20_flat_minus5_2"
    return "ret20_down_lt_minus5"


def _bucket_ret60(value: float) -> str:
    if pd.isna(value):
        return "missing"
    if value >= 0.25:
        return "ret60_strong_up_ge25"
    if value >= 0.05:
        return "ret60_up_5_25"
    if value >= -0.10:
        return "ret60_flat_minus10_5"
    return "ret60_down_lt_minus10"


def _bucket_ret20_60(ret20: float, ret60: float) -> str:
    if pd.isna(ret20) or pd.isna(ret60):
        return "missing"
    if ret20 >= 0.0 and ret60 >= 0.0:
        return "ret20_60_both_up"
    if ret20 < 0.0 and ret60 < 0.0:
        return "ret20_60_both_down"
    if ret20 >= 0.0 and ret60 < 0.0:
        return "ret20_up_ret60_down"
    return "ret20_down_ret60_up"


def _bucket_age(value: float) -> str:
    if pd.isna(value):
        return "missing"
    if value <= 20:
        return "age_le20"
    if value <= 80:
        return "age_21_80"
    return "age_gt80"


def _bucket_ma200(value: float) -> str:
    if pd.isna(value):
        return "missing"
    if value >= 0.05:
        return "above_ma200_ge5"
    if value >= 0.0:
        return "above_ma200_0_5"
    if value >= -0.10:
        return "below_ma200_0_10"
    return "below_ma200_gt10"


def _bucket_recovery_phase(drawdown: float, ret20: float, ret60: float) -> str:
    if pd.isna(drawdown) or pd.isna(ret20) or pd.isna(ret60):
        return "missing"
    if drawdown <= 0.05:
        return "near_high"
    if ret20 >= 0.0 and ret60 >= 0.0:
        return "recovering_dd"
    if ret20 < 0.0 and ret60 < 0.0:
        return "falling_dd"
    if ret20 >= 0.0:
        return "short_rebound_dd"
    return "weakening_dd"


def _bucket_margin_usage(margin: float, equity: float) -> str:
    if pd.isna(margin) or pd.isna(equity) or equity <= 0.0:
        return "missing"
    usage = margin / equity
    if usage <= 0.05:
        return "margin_light_le5"
    if usage <= 0.20:
        return "margin_mid_5_20"
    return "margin_heavy_gt20"


def _bucket_free_capital(free_capital: float, equity: float) -> str:
    if pd.isna(free_capital) or pd.isna(equity) or equity <= 0.0:
        return "missing"
    ratio = free_capital / equity
    if ratio >= 0.85:
        return "free_abundant_ge85"
    if ratio >= 0.60:
        return "free_ok_60_85"
    return "free_tight_lt60"


def _bucket_book_state(active_positions: float) -> str:
    if pd.isna(active_positions):
        return "missing"
    if active_positions <= 0:
        return "book_flat"
    if active_positions <= 1:
        return "book_one_position"
    return "book_multi_positions"


def _bucket_loss_streak(value: float) -> str:
    if pd.isna(value):
        return "missing"
    if value <= 3:
        return "loss3"
    if value <= 5:
        return "loss4_5"
    if value <= 9:
        return "loss6_9"
    return "loss_ge10"


def _state_plus_edge(edge_bucket: str, phase_bucket: str) -> str:
    has_edge = str(edge_bucket) == "directional_edge"
    if has_edge and phase_bucket in {"near_high", "recovering_dd", "short_rebound_dd"}:
        return "edge_in_healthy_or_recovery_account"
    if has_edge and phase_bucket == "falling_dd":
        return "edge_in_falling_account"
    if has_edge:
        return "edge_other_account"
    return "no_edge"


def _enrich_account_state(candidates: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    merged = pd.merge_asof(
        candidates.sort_values("date"),
        daily.sort_values("date"),
        on="date",
        direction="backward",
    )
    official_drawdown = _safe_num(merged.get("portfolio_drawdown_pct", pd.Series(np.nan, index=merged.index)))
    merged["account_drawdown_pct"] = official_drawdown.where(
        official_drawdown.notna(),
        merged["account_drawdown_calc"],
    )
    merged["account_margin_usage"] = (
        _safe_num(merged["total_margin_in_use_before"]) / _safe_num(merged["estimated_equity"])
    )
    merged["account_free_capital_ratio"] = _safe_num(merged["free_capital"]) / _safe_num(merged["estimated_equity"])

    merged["account_dd_bucket"] = merged["account_drawdown_pct"].map(_bucket_drawdown)
    merged["account_ret20_bucket"] = merged["account_ret20"].map(_bucket_ret20)
    merged["account_ret60_bucket"] = merged["account_ret60"].map(_bucket_ret60)
    merged["account_ret20_60_bucket"] = [
        _bucket_ret20_60(ret20, ret60) for ret20, ret60 in zip(merged["account_ret20"], merged["account_ret60"])
    ]
    merged["account_drawdown_age_bucket"] = merged["account_days_since_high"].map(_bucket_age)
    merged["account_ma200_bucket"] = merged["account_ma200_gap"].map(_bucket_ma200)
    merged["account_recovery_phase_bucket"] = [
        _bucket_recovery_phase(drawdown, ret20, ret60)
        for drawdown, ret20, ret60 in zip(
            merged["account_drawdown_pct"],
            merged["account_ret20"],
            merged["account_ret60"],
        )
    ]
    merged["account_margin_usage_bucket"] = [
        _bucket_margin_usage(margin, equity)
        for margin, equity in zip(merged["total_margin_in_use_before"], merged["estimated_equity"])
    ]
    merged["account_free_capital_bucket"] = [
        _bucket_free_capital(free_capital, equity)
        for free_capital, equity in zip(merged["free_capital"], merged["estimated_equity"])
    ]
    merged["account_book_state_bucket"] = merged["active_positions_before"].map(_bucket_book_state)
    merged["loss_streak_depth_bucket"] = merged["loss_streak"].map(_bucket_loss_streak)
    merged["account_state_plus_edge_bucket"] = [
        _state_plus_edge(edge, phase)
        for edge, phase in zip(
            merged.get("product_directional_edge60_bucket", pd.Series("", index=merged.index)),
            merged["account_recovery_phase_bucket"],
        )
    ]
    return merged.sort_values(["date", "candidate_index"]).reset_index(drop=True)


def _dominant_share(group: pd.DataFrame, column: str) -> tuple[str, float]:
    share = group[column].value_counts(normalize=True)
    if share.empty:
        return "", np.nan
    return str(share.index[0]), float(share.iloc[0])


def _fail_reasons(row: pd.Series) -> str:
    reasons: list[str] = []
    if int(row["rows"]) < MIN_RELIABLE_ROWS:
        reasons.append(f"rows<{MIN_RELIABLE_ROWS}")
    if int(row["years"]) < MIN_RELIABLE_YEARS:
        reasons.append(f"years<{MIN_RELIABLE_YEARS}")
    if int(row["product_count"]) < MIN_RELIABLE_PRODUCTS:
        reasons.append(f"products<{MIN_RELIABLE_PRODUCTS}")
    if float(row["dominant_product_share_pct"]) > MAX_DOMINANT_PRODUCT_SHARE * 100.0:
        reasons.append(f"dominant_product_share>{MAX_DOMINANT_PRODUCT_SHARE * 100:.0f}%")
    if float(row["dominant_year_share_pct"]) > MAX_DOMINANT_YEAR_SHARE * 100.0:
        reasons.append(f"dominant_year_share>{MAX_DOMINANT_YEAR_SHARE * 100:.0f}%")
    if float(row["good_lift_pp"]) < MIN_GOOD_LIFT_PP:
        reasons.append(f"good_lift<{MIN_GOOD_LIFT_PP:.0f}pp")
    if float(row["bad_rate_pct"]) > MAX_BAD_RATE_PCT:
        reasons.append(f"bad_rate>{MAX_BAD_RATE_PCT:.0f}%")
    if int(row["years_good_ge_base"]) < MIN_GOOD_YEARS:
        reasons.append(f"good_years<{MIN_GOOD_YEARS}")
    if int(row["years_score_positive"]) < MIN_POSITIVE_SCORE_YEARS:
        reasons.append(f"positive_score_years<{MIN_POSITIVE_SCORE_YEARS}")
    return "; ".join(reasons)


def _feature_rows(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    baseline_good = float(data["h40_barrier_good"].mean())
    baseline_bad = float(data["h40_barrier_bad"].mean())
    baseline_score = float(data["h40_path_score_r"].mean())
    rows: list[dict[str, Any]] = []
    year_rows: list[dict[str, Any]] = []
    for feature in ACCOUNT_STATE_FEATURES:
        for value, group in data.groupby(feature, dropna=False):
            label = "missing" if pd.isna(value) or str(value) == "" else str(value)
            if label in {"missing", "nan", ""} or len(group) < 5:
                continue
            dominant_product, dominant_product_share = _dominant_share(group, "product")
            dominant_year, dominant_year_share = _dominant_share(group, "year")
            year_stats = group.groupby("year").agg(
                rows=("candidate_index", "count"),
                good_rate=("h40_barrier_good", "mean"),
                bad_rate=("h40_barrier_bad", "mean"),
                avg_score=("h40_path_score_r", "mean"),
            )
            rows.append(
                {
                    "feature": feature,
                    "feature_value": label,
                    "rows": int(len(group)),
                    "good_rate_pct": float(group["h40_barrier_good"].mean() * 100.0),
                    "bad_rate_pct": float(group["h40_barrier_bad"].mean() * 100.0),
                    "good_lift_pp": float((group["h40_barrier_good"].mean() - baseline_good) * 100.0),
                    "bad_lift_pp": float((group["h40_barrier_bad"].mean() - baseline_bad) * 100.0),
                    "avg_path_score_r": float(group["h40_path_score_r"].mean()),
                    "score_lift_r": float(group["h40_path_score_r"].mean() - baseline_score),
                    "years": int(len(year_stats)),
                    "years_good_ge_base": int((year_stats["good_rate"] >= baseline_good).sum()),
                    "years_score_positive": int((year_stats["avg_score"] > 0.0).sum()),
                    "product_count": int(group["product"].nunique()),
                    "dominant_product": dominant_product,
                    "dominant_product_share_pct": float(dominant_product_share * 100.0),
                    "dominant_year": dominant_year,
                    "dominant_year_share_pct": float(dominant_year_share * 100.0),
                    "baseline_good_rate_pct": baseline_good * 100.0,
                    "baseline_bad_rate_pct": baseline_bad * 100.0,
                    "baseline_path_score_r": baseline_score,
                }
            )
            for year, year_group in group.groupby("year"):
                year_rows.append(
                    {
                        "feature": feature,
                        "feature_value": label,
                        "year": int(year),
                        "rows": int(len(year_group)),
                        "good_rate_pct": float(year_group["h40_barrier_good"].mean() * 100.0),
                        "bad_rate_pct": float(year_group["h40_barrier_bad"].mean() * 100.0),
                        "avg_path_score_r": float(year_group["h40_path_score_r"].mean()),
                    }
                )
    metrics = pd.DataFrame(rows)
    if metrics.empty:
        return metrics, pd.DataFrame(year_rows)
    metrics["fail_reasons"] = metrics.apply(_fail_reasons, axis=1)
    metrics["passes_reliability_gate"] = metrics["fail_reasons"].eq("")
    metrics["screen_score"] = (
        metrics["good_lift_pp"]
        - np.maximum(metrics["bad_lift_pp"], 0.0)
        + np.minimum(metrics["avg_path_score_r"], 20.0)
        + metrics["years_good_ge_base"] * 2.0
        + np.minimum(metrics["rows"], 40.0) / 4.0
        - np.maximum(metrics["dominant_year_share_pct"] - 35.0, 0.0) / 4.0
    )
    metrics["classification"] = np.select(
        [
            metrics["passes_reliability_gate"],
            (metrics["good_lift_pp"] >= MIN_GOOD_LIFT_PP) & (metrics["rows"] >= 12),
        ],
        ["reliable_account_state_candidate", "watch_only_account_state_sample_or_stability_gap"],
        default="not_reliable",
    )
    return (
        metrics.sort_values(
            ["passes_reliability_gate", "screen_score", "good_lift_pp", "rows"],
            ascending=[False, False, False, False],
        ).reset_index(drop=True),
        pd.DataFrame(year_rows),
    )


def _coverage(enriched: pd.DataFrame) -> dict[str, Any]:
    return {
        "candidate_rows": int(len(enriched)),
        "baseline_good_rate_pct": float(enriched["h40_barrier_good"].mean() * 100.0),
        "baseline_bad_rate_pct": float(enriched["h40_barrier_bad"].mean() * 100.0),
        "baseline_path_score_r": float(enriched["h40_path_score_r"].mean()),
        "median_account_drawdown_pct": float(enriched["account_drawdown_pct"].median() * 100.0),
        "min_account_drawdown_pct": float(enriched["account_drawdown_pct"].min() * 100.0),
        "max_account_drawdown_pct": float(enriched["account_drawdown_pct"].max() * 100.0),
        "median_loss_streak": float(enriched["loss_streak"].median()),
        "median_margin_usage_pct": float(enriched["account_margin_usage"].median() * 100.0),
    }


def _plot(metrics: pd.DataFrame) -> None:
    if metrics.empty:
        return
    plt.rcParams["font.family"] = "DejaVu Sans"
    top = metrics.head(14).copy()
    labels = top["feature"] + "=" + top["feature_value"]
    colors = [
        "#2f855a" if passed else "#dd6b20" if "watch" in classification else "#718096"
        for passed, classification in zip(top["passes_reliability_gate"], top["classification"])
    ]
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    axes[0].barh(labels, top["good_lift_pp"], color=colors)
    axes[0].axvline(MIN_GOOD_LIFT_PP, color="#2f855a", linestyle="--", linewidth=1.0, label="required +10pp")
    axes[0].axvline(0.0, color="#4a5568", linewidth=0.8)
    axes[0].set_title("Account-state features: H40 good lift")
    axes[0].set_xlabel("good lift (pp)")
    axes[0].invert_yaxis()
    axes[0].legend()
    axes[1].scatter(metrics["rows"], metrics["good_rate_pct"], s=48, alpha=0.68, color="#2b6cb0")
    axes[1].axhline(float(metrics["baseline_good_rate_pct"].iloc[0]), color="#4a5568", linestyle="--", label="baseline")
    axes[1].axvline(MIN_RELIABLE_ROWS, color="#2f855a", linestyle="--", label="required rows")
    axes[1].set_title("Feature support vs good rate")
    axes[1].set_xlabel("rows")
    axes[1].set_ylabel("H40 +2R first-hit rate (%)")
    axes[1].legend()
    fig.suptitle("Stage730 Account-State Throttle Feature Audit", fontsize=15)
    fig.tight_layout(rect=[0, 0.02, 1, 0.94])
    CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _build_report(enriched: pd.DataFrame, metrics: pd.DataFrame, decision: dict[str, Any]) -> str:
    columns = [
        "feature",
        "feature_value",
        "rows",
        "good_rate_pct",
        "bad_rate_pct",
        "good_lift_pp",
        "avg_path_score_r",
        "years",
        "years_good_ge_base",
        "product_count",
        "dominant_product_share_pct",
        "dominant_year_share_pct",
        "classification",
        "fail_reasons",
    ]
    return "\n".join(
        [
            "# Stage730 Account-State Throttle Feature Audit",
            "",
            f"- line_id: `{LINE_ID}`",
            f"- generated_at: `{decision['generated_at']}`",
            f"- source_stage723: `{SOURCE_STAGE723_ENRICHED_PATH}`",
            f"- source_stage719_positions: `{SOURCE_STAGE719_POSITIONS_PATH}`",
            f"- actionable_h40_rows: `{len(enriched)}`",
            f"- initial_gate_candidate_count: `{decision['initial_gate_candidate_count']}`",
            f"- decision: `{decision['decision']}`",
            "",
            "## Predeclared Features",
            "",
            "- Account drawdown level, drawdown age, 20/60 day account returns, equity MA200 gap, margin usage, free capital, book state and loss-streak depth.",
            "- A fixed interaction between account recovery phase and Stage723 product directional edge60.",
            "- No product names, years, or red-box window are used as rule features.",
            "",
            "## Coverage",
            "",
            _md_table(pd.DataFrame([decision["coverage"]]), max_rows=None),
            "",
            "## Gate",
            "",
            f"- rows >= `{MIN_RELIABLE_ROWS}`",
            f"- years >= `{MIN_RELIABLE_YEARS}`",
            f"- products >= `{MIN_RELIABLE_PRODUCTS}`",
            f"- dominant product share <= `{MAX_DOMINANT_PRODUCT_SHARE * 100:.0f}%`",
            f"- dominant year share <= `{MAX_DOMINANT_YEAR_SHARE * 100:.0f}%`",
            f"- H40 +2R good lift >= `{MIN_GOOD_LIFT_PP:.0f}pp`",
            f"- H40 -1R bad rate <= `{MAX_BAD_RATE_PCT:.0f}%`",
            f"- good years >= `{MIN_GOOD_YEARS}` and positive-score years >= `{MIN_POSITIVE_SCORE_YEARS}`",
            "",
            "## Top Account-State Features",
            "",
            _md_table(metrics[columns], max_rows=30) if not metrics.empty else "_empty_",
            "",
            "## Interpretation",
            "",
            "- This is a read-only audit. It does not change the official strategy or run order logic.",
            "- Account-state features are especially prone to acting as year/path proxies, so the gate includes dominant-year concentration.",
            "- A surviving initial gate would still need a predeclared A/C strategy replay before any official-rule change.",
        ]
    ) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = _load_candidates()
    daily = _load_daily_account()
    enriched = _enrich_account_state(candidates, daily)
    metrics, year_detail = _feature_rows(enriched)
    initial_gate = metrics[metrics["passes_reliability_gate"]] if not metrics.empty else metrics
    has_initial_gate = not initial_gate.empty
    decision = {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_stage723": str(SOURCE_STAGE723_ENRICHED_PATH),
        "source_stage719_positions": str(SOURCE_STAGE719_POSITIONS_PATH),
        "coverage": _coverage(enriched),
        "initial_gate_candidate_count": int(len(initial_gate)),
        "initial_gate_candidates": initial_gate[
            ["feature", "feature_value", "rows", "good_rate_pct", "good_lift_pp", "fail_reasons"]
        ].to_dict(orient="records")
        if has_initial_gate
        else [],
        "top_watch_features": metrics.head(8)[
            ["feature", "feature_value", "rows", "good_rate_pct", "good_lift_pp", "fail_reasons"]
        ].to_dict(orient="records")
        if not metrics.empty
        else [],
        "decision": (
            "account_state_initial_gate_candidate_requires_strategy_ab_validation"
            if has_initial_gate
            else "no_account_state_reliable_exemption_feature_found"
        ),
        "next_step": (
            "Run a predeclared A/C replay for the surviving account-state gate."
            if has_initial_gate
            else "Do not implement an account-state exemption. Continue only via forward watch or new orthogonal data."
        ),
    }
    enriched.to_csv(ENRICHED_PATH, index=False, encoding="utf-8-sig")
    metrics.to_csv(FEATURE_METRICS_PATH, index=False, encoding="utf-8-sig")
    year_detail.to_csv(YEAR_DETAIL_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(enriched, metrics, decision), encoding="utf-8")
    _plot(metrics)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
