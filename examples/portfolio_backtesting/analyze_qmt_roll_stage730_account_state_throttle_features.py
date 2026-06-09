from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage721_throttle_exemption_feature_reliability as s721


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage730_account_state_throttle_features_v1"
OUTPUT_PREFIX = "qmt_roll_stage730_account_state_throttle_features"
LINE_ID = "futures_trend_winner_trade_forensics"

SOURCE_STAGE716_PATH = s721.SOURCE_STAGE716_PATH
SOURCE_STAGE719_CLOSED_LOTS_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage719_official_winner_trade_forensics_closed_lots_"
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
MIN_GOOD_LIFT_PP = 10.0
MAX_BAD_RATE_PCT = 60.0
MIN_GOOD_YEARS = 4
MIN_POSITIVE_SCORE_YEARS = 4

ACCOUNT_STATE_FEATURES = [
    "acct_prior_trade_count_bucket",
    "acct_recent_r3_bucket",
    "acct_recent_r5_bucket",
    "acct_recent_r10_bucket",
    "acct_recent_win5_bucket",
    "acct_recent_mfe5_bucket",
    "acct_last_winner_age_bucket",
    "acct_last_big_winner_age_bucket",
    "acct_recent_close_velocity20_bucket",
    "acct_recent_chop20_bucket",
    "same_direction_recent_r5_bucket",
    "same_product_direction_last_bucket",
    "same_product_direction_r3_bucket",
    "account_recovery_state_bucket",
]


def _json_safe(value: Any) -> Any:
    return s721._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s721._md_table(frame, max_rows=max_rows)


def _load_actionable() -> pd.DataFrame:
    data = s721._load_actionable_candidates()
    data["date"] = pd.to_datetime(data["date"]).dt.normalize()
    data["year"] = data["year"].astype(int)
    return data.reset_index(drop=True)


def _load_closed_lots() -> pd.DataFrame:
    if not SOURCE_STAGE719_CLOSED_LOTS_PATH.exists():
        raise FileNotFoundError(SOURCE_STAGE719_CLOSED_LOTS_PATH)
    lots = pd.read_csv(SOURCE_STAGE719_CLOSED_LOTS_PATH, encoding="utf-8-sig")
    lots["entry_date"] = pd.to_datetime(lots["entry_date"], errors="coerce").dt.normalize()
    lots["exit_date"] = pd.to_datetime(lots["exit_date"], errors="coerce").dt.normalize()
    for column in [
        "r_multiple",
        "mfe_r",
        "mae_r",
        "winner",
        "big_winner",
        "volume",
        "realized_pnl",
    ]:
        if column in lots.columns:
            lots[column] = pd.to_numeric(lots[column], errors="coerce")
    lots = lots.dropna(subset=["exit_date"]).sort_values(["exit_date", "lot_id"]).reset_index(drop=True)
    lots["direction"] = lots["direction"].astype(str)
    lots["product"] = lots["product"].astype(str)
    return lots


def _sum_bucket(value: float, *, pos: float = 0.0, deep: float = -3.0) -> str:
    if pd.isna(value):
        return "missing"
    if value >= pos:
        return "sum_positive"
    if value > deep:
        return "sum_mild_loss"
    return "sum_deep_loss"


def _sum10_bucket(value: float) -> str:
    if pd.isna(value):
        return "missing"
    if value >= 2.0:
        return "sum10_strong_positive_ge2r"
    if value >= 0.0:
        return "sum10_positive_0_2r"
    if value > -5.0:
        return "sum10_mild_loss"
    return "sum10_deep_loss_le_minus5r"


def _win5_bucket(value: float) -> str:
    if pd.isna(value):
        return "missing"
    if value <= 0:
        return "win5_zero"
    if value == 1:
        return "win5_one"
    return "win5_ge2"


def _mfe5_bucket(value: float) -> str:
    if pd.isna(value):
        return "missing"
    if value >= 2.0:
        return "mfe5_high_ge2r"
    if value >= 1.0:
        return "mfe5_mid_1_2r"
    return "mfe5_low_lt1r"


def _age_bucket(days: float) -> str:
    if pd.isna(days):
        return "age_none"
    if days <= 20:
        return "age_recent_le20d"
    if days <= 60:
        return "age_mid_21_60d"
    return "age_old_gt60d"


def _velocity_bucket(count: int) -> str:
    if count <= 1:
        return "close_velocity_low_0_1"
    if count <= 3:
        return "close_velocity_mid_2_3"
    return "close_velocity_high_ge4"


def _same_pd_last_bucket(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "same_pd_no_history"
    last = frame.iloc[-1]
    if float(last.get("r_multiple", np.nan)) > 0:
        return "same_pd_last_win"
    return "same_pd_last_loss"


def _recovery_state(r5_sum: float, win5_count: float, last_winner_age_days: float, velocity20: int) -> str:
    has_recent_winner = not pd.isna(last_winner_age_days) and last_winner_age_days <= 20
    if r5_sum >= 0 and win5_count >= 1:
        return "recent_realized_recovery"
    if has_recent_winner and r5_sum > -3.0:
        return "recent_winner_mild_damage"
    if r5_sum <= -3.0 and velocity20 >= 4:
        return "high_churn_deep_damage"
    if pd.isna(last_winner_age_days) or last_winner_age_days > 60:
        return "winner_absent_or_stale"
    return "mixed_account_state"


def _prior_slice(lots: pd.DataFrame, date: pd.Timestamp) -> pd.DataFrame:
    return lots[lots["exit_date"] < date]


def _enrich_account_state(candidates: pd.DataFrame, lots: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in candidates.itertuples(index=False):
        record = row._asdict()
        date = pd.Timestamp(row.date).normalize()
        direction = str(row.direction)
        product = str(row.product)
        prior = _prior_slice(lots, date)
        r = pd.to_numeric(prior["r_multiple"], errors="coerce").dropna()
        last3 = r.tail(3)
        last5 = r.tail(5)
        last10 = r.tail(10)
        winners = prior[pd.to_numeric(prior["r_multiple"], errors="coerce") > 0]
        big_winners = prior[pd.to_numeric(prior.get("big_winner", 0), errors="coerce").fillna(0) > 0]
        recent20 = prior[prior["exit_date"] >= date - pd.Timedelta(days=20)]
        same_direction = prior[prior["direction"].astype(str).eq(direction)]
        same_pd = same_direction[same_direction["product"].astype(str).eq(product)]
        same_pd_r = pd.to_numeric(same_pd["r_multiple"], errors="coerce").dropna()
        same_dir_r = pd.to_numeric(same_direction["r_multiple"], errors="coerce").dropna()

        prior_trade_count = int(len(prior))
        r3_sum = float(last3.sum()) if len(last3) else np.nan
        r5_sum = float(last5.sum()) if len(last5) else np.nan
        r10_sum = float(last10.sum()) if len(last10) else np.nan
        win5_count = float((last5 > 0).sum()) if len(last5) else np.nan
        mfe5_mean = float(pd.to_numeric(prior["mfe_r"], errors="coerce").dropna().tail(5).mean())
        if np.isnan(mfe5_mean):
            mfe5_mean = np.nan
        if winners.empty:
            last_winner_age_days = np.nan
        else:
            last_winner_age_days = float((date - pd.Timestamp(winners["exit_date"].iloc[-1])).days)
        if big_winners.empty:
            last_big_winner_age_days = np.nan
        else:
            last_big_winner_age_days = float((date - pd.Timestamp(big_winners["exit_date"].iloc[-1])).days)
        same_dir_r5_sum = float(same_dir_r.tail(5).sum()) if len(same_dir_r) else np.nan
        same_pd_r3_sum = float(same_pd_r.tail(3).sum()) if len(same_pd_r) else np.nan

        record.update(
            {
                "acct_prior_trade_count": prior_trade_count,
                "acct_recent_r3_sum": r3_sum,
                "acct_recent_r5_sum": r5_sum,
                "acct_recent_r10_sum": r10_sum,
                "acct_recent_win5_count": win5_count,
                "acct_recent_mfe5_mean": mfe5_mean,
                "acct_last_winner_age_days": last_winner_age_days,
                "acct_last_big_winner_age_days": last_big_winner_age_days,
                "acct_recent_close_count20": int(len(recent20)),
                "same_direction_recent_r5_sum": same_dir_r5_sum,
                "same_product_direction_recent_r3_sum": same_pd_r3_sum,
                "acct_prior_trade_count_bucket": "prior_trade_lt20" if prior_trade_count < 20 else "prior_trade_ge20",
                "acct_recent_r3_bucket": _sum_bucket(r3_sum, pos=0.0, deep=-3.0),
                "acct_recent_r5_bucket": _sum_bucket(r5_sum, pos=0.0, deep=-3.0),
                "acct_recent_r10_bucket": _sum10_bucket(r10_sum),
                "acct_recent_win5_bucket": _win5_bucket(win5_count),
                "acct_recent_mfe5_bucket": _mfe5_bucket(mfe5_mean),
                "acct_last_winner_age_bucket": _age_bucket(last_winner_age_days),
                "acct_last_big_winner_age_bucket": _age_bucket(last_big_winner_age_days),
                "acct_recent_close_velocity20_bucket": _velocity_bucket(int(len(recent20))),
                "acct_recent_chop20_bucket": (
                    "chop20_high_churn_loss"
                    if len(recent20) >= 4 and not pd.isna(r5_sum) and r5_sum < 0 and not pd.isna(win5_count) and win5_count <= 1
                    else "chop20_not_high_churn_loss"
                ),
                "same_direction_recent_r5_bucket": _sum_bucket(same_dir_r5_sum, pos=0.0, deep=-3.0),
                "same_product_direction_last_bucket": _same_pd_last_bucket(same_pd),
                "same_product_direction_r3_bucket": _sum_bucket(same_pd_r3_sum, pos=0.0, deep=-3.0),
                "account_recovery_state_bucket": _recovery_state(
                    r5_sum,
                    win5_count,
                    last_winner_age_days,
                    int(len(recent20)),
                ),
            }
        )
        rows.append(record)
    return pd.DataFrame(rows)


def _dominant_share(group: pd.DataFrame) -> tuple[str, float]:
    share = group["product"].value_counts(normalize=True)
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
        if feature not in data.columns:
            continue
        for value, group in data.groupby(feature, dropna=False):
            label = "missing" if pd.isna(value) or str(value) == "" else str(value)
            if label in {"missing", "nan", ""} or len(group) < 5:
                continue
            dominant_product, dominant_product_share = _dominant_share(group)
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
    )
    metrics["classification"] = np.select(
        [
            metrics["passes_reliability_gate"],
            (metrics["good_lift_pp"] >= MIN_GOOD_LIFT_PP) & (metrics["rows"] >= 12),
        ],
        ["reliable_account_state_candidate", "watch_only_account_state_sample_or_stability_gap"],
        default="not_reliable",
    )
    metrics = metrics.sort_values(
        ["passes_reliability_gate", "screen_score", "good_lift_pp", "rows"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)
    return metrics, pd.DataFrame(year_rows)


def _coverage(enriched: pd.DataFrame, lots: pd.DataFrame) -> dict[str, Any]:
    return {
        "candidate_rows": int(len(enriched)),
        "closed_lots_rows": int(len(lots)),
        "baseline_good_rate_pct": float(enriched["h40_barrier_good"].mean() * 100.0),
        "baseline_bad_rate_pct": float(enriched["h40_barrier_bad"].mean() * 100.0),
        "baseline_path_score_r": float(enriched["h40_path_score_r"].mean()),
        "median_prior_trade_count": float(enriched["acct_prior_trade_count"].median()),
        "min_prior_trade_count": int(enriched["acct_prior_trade_count"].min()),
        "max_prior_trade_count": int(enriched["acct_prior_trade_count"].max()),
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
        "classification",
        "fail_reasons",
    ]
    return "\n".join(
        [
            "# Stage730 Account-State Throttle Feature Audit",
            "",
            f"- line_id: `{LINE_ID}`",
            f"- generated_at: `{decision['generated_at']}`",
            f"- source_stage716: `{SOURCE_STAGE716_PATH}`",
            f"- source_stage719_closed_lots: `{SOURCE_STAGE719_CLOSED_LOTS_PATH}`",
            f"- actionable_h40_rows: `{len(enriched)}`",
            f"- initial_gate_candidate_count: `{decision['initial_gate_candidate_count']}`",
            f"- decision: `{decision['decision']}`",
            "",
            "## Predeclared Account-State Features",
            "",
            "- Recent realized R-sums from already-closed lots before the candidate date.",
            "- Recent winner age and big-winner age.",
            "- Recent close velocity/chop state.",
            "- Same-direction and same-product-direction realized state.",
            "- A fixed composite account recovery state, without fitting thresholds to any year or red-box window.",
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
            f"- H40 +2R good lift >= `{MIN_GOOD_LIFT_PP:.0f}pp`",
            f"- H40 -1R bad rate <= `{MAX_BAD_RATE_PCT:.0f}%`",
            f"- good years >= `{MIN_GOOD_YEARS}` and positive-score years >= `{MIN_POSITIVE_SCORE_YEARS}`",
            "",
            "## Top Account-State Features",
            "",
            _md_table(metrics[columns], max_rows=25) if not metrics.empty else "_empty_",
            "",
            "## Interpretation",
            "",
            "- This audit only uses information available before each candidate date.",
            "- A surviving gate is still only an initial candidate and must pass a predeclared A/C strategy replay before promotion.",
            "- Failing gates imply account-state features should remain diagnostic/watch features, not 0.1-bypass rules.",
        ]
    ) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = _load_actionable()
    lots = _load_closed_lots()
    enriched = _enrich_account_state(candidates, lots)
    metrics, year_detail = _feature_rows(enriched)
    initial_gate = metrics[metrics["passes_reliability_gate"]] if not metrics.empty else metrics
    has_initial_gate = not initial_gate.empty
    decision = {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_stage716": str(SOURCE_STAGE716_PATH),
        "source_stage719_closed_lots": str(SOURCE_STAGE719_CLOSED_LOTS_PATH),
        "coverage": _coverage(enriched, lots),
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
            "account_state_initial_gate_candidate_requires_strategy_ac_validation"
            if has_initial_gate
            else "no_account_state_reliable_exemption_feature_found"
        ),
        "next_step": (
            "Run a predeclared A/C replay for the surviving account-state gate."
            if has_initial_gate
            else "Do not implement an account-state exemption. Continue only via truly independent data or forward watch."
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
