from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage721_throttle_exemption_feature_reliability_v1"
OUTPUT_PREFIX = "qmt_roll_stage721_throttle_exemption_feature_reliability"
LINE_ID = "futures_trend_winner_trade_forensics"

SOURCE_STAGE716_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage716_official_throttle_quality_readonly_labeled_candidates_"
    "stage716_official_throttle_quality_readonly_v1.csv"
)
SOURCE_STAGE716_SCOPE_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage716_official_throttle_quality_readonly_scope_summary_"
    "stage716_official_throttle_quality_readonly_v1.csv"
)
SOURCE_STAGE698_DECISION_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage698_stage407_zero_volume_min_one_decision_"
    "stage698_stage407_zero_volume_min_one_v1.json"
)

FEATURE_RELIABILITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_reliability_{MODEL_TAG}.csv"
WATCHLIST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_watchlist_{MODEL_TAG}.csv"
YEAR_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_detail_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

MIN_RELIABLE_ROWS = 30
MIN_RELIABLE_YEARS = 4
MAX_DOMINANT_PRODUCT_SHARE = 0.35
MIN_GOOD_LIFT = 0.10
MAX_BAD_RATE = 0.60
MIN_SCORE_POSITIVE_YEARS = 4
MIN_GOOD_YEARS = 4

FEATURE_COLUMNS = [
    "direction",
    "signal",
    "risk_mode",
    "status_scope",
    "ai_rank_bucket",
    "rsi_direction_bucket",
    "corr_bucket",
    "drawdown_bucket",
    "active_positions_bucket",
    "pairwise_rank_bucket",
    "contracts_by_risk_bucket",
    "target_risk_bucket",
    "stop_distance_pct_bucket",
    "breakout_bucket",
    "streak_entry_structure_risk_recovery_applied",
    "recovery_sleeve_applied",
    "risk_multiplier",
    "streak_entry_structure_risk_recovery_reason",
    "recovery_sleeve_reason",
]

BACKTEST_CONTRADICTIONS = {
    ("status_scope", "sizing_zero_volume"): (
        "Stage411 zero-volume min-one was already backtested and failed: official end equity fell "
        "from 8,728,285 to 6,901,460; Stage407 also fell from 3,284,935 to 2,643,000."
    ),
    ("pairwise_rank_bucket", "pair_missing"): (
        "This is the same non-opened/sizing-zero population as `sizing_zero_volume`, and is covered by "
        "the failed Stage411/Stage420 tests."
    ),
    ("recovery_sleeve_reason", "cooldown"): (
        "Small sample only; related low-risk scout and recovery-sleeve expansion tests did not promote."
    ),
}


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
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    data = data.fillna("")
    headers = [str(column) for column in data.columns]
    rows = [[str(value) for value in row] for row in data.to_numpy()]
    widths = [len(header) for header in headers]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    line = "| " + " | ".join(header.ljust(width) for header, width in zip(headers, widths)) + " |"
    sep = "| " + " | ".join("-" * width for width in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |" for row in rows]
    return "\n".join([line, sep, *body])


def _load_actionable_candidates() -> pd.DataFrame:
    if not SOURCE_STAGE716_PATH.exists():
        raise FileNotFoundError(SOURCE_STAGE716_PATH)
    data = pd.read_csv(SOURCE_STAGE716_PATH, encoding="utf-8-sig")
    actionable_flag = (
        data["actionable_throttle"]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin({"true", "1", "1.0", "yes", "y"})
    )
    for column in [
        "h40_barrier_good",
        "h40_barrier_bad",
        "h40_mfe_r",
        "h40_mae_r",
        "h40_path_score_r",
        "year",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    actionable = data[
        actionable_flag & data["h40_label_status"].astype(str).eq("ok")
    ].copy()
    actionable["year"] = actionable["year"].astype(int)
    return actionable


def _feature_rows(actionable: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    baseline_good = float(actionable["h40_barrier_good"].mean())
    baseline_bad = float(actionable["h40_barrier_bad"].mean())
    baseline_score = float(actionable["h40_path_score_r"].mean())

    rows: list[dict[str, Any]] = []
    year_rows: list[dict[str, Any]] = []
    for feature in FEATURE_COLUMNS:
        if feature not in actionable.columns:
            continue
        for value, group in actionable.groupby(feature, dropna=False):
            label = "missing" if pd.isna(value) or str(value) == "" else str(value)
            if label in {"missing", "nan", ""}:
                continue
            if len(group) < 5:
                continue
            product_share = group["product"].value_counts(normalize=True)
            dominant_product = str(product_share.index[0]) if not product_share.empty else ""
            dominant_share = float(product_share.iloc[0]) if not product_share.empty else np.nan
            year_stats = group.groupby("year").agg(
                rows=("candidate_index", "count"),
                good_rate=("h40_barrier_good", "mean"),
                bad_rate=("h40_barrier_bad", "mean"),
                avg_score=("h40_path_score_r", "mean"),
                avg_mfe=("h40_mfe_r", "mean"),
                avg_mae=("h40_mae_r", "mean"),
            )
            rows.append(
                {
                    "feature": feature,
                    "feature_value": label,
                    "rows": int(len(group)),
                    "opened_rate_pct": float(group["status_scope"].astype(str).eq("opened").mean() * 100.0),
                    "good_rate_pct": float(group["h40_barrier_good"].mean() * 100.0),
                    "bad_rate_pct": float(group["h40_barrier_bad"].mean() * 100.0),
                    "good_lift_pp": float((group["h40_barrier_good"].mean() - baseline_good) * 100.0),
                    "bad_lift_pp": float((group["h40_barrier_bad"].mean() - baseline_bad) * 100.0),
                    "avg_mfe_r": float(group["h40_mfe_r"].mean()),
                    "avg_mae_r": float(group["h40_mae_r"].mean()),
                    "avg_path_score_r": float(group["h40_path_score_r"].mean()),
                    "score_lift_r": float(group["h40_path_score_r"].mean() - baseline_score),
                    "years": int(len(year_stats)),
                    "years_good_ge_base": int((year_stats["good_rate"] >= baseline_good).sum()),
                    "years_score_positive": int((year_stats["avg_score"] > 0.0).sum()),
                    "product_count": int(group["product"].nunique()),
                    "dominant_product": dominant_product,
                    "dominant_product_share_pct": dominant_share * 100.0,
                    "baseline_good_rate_pct": baseline_good * 100.0,
                    "baseline_bad_rate_pct": baseline_bad * 100.0,
                    "baseline_path_score_r": baseline_score,
                    "backtest_contradiction": BACKTEST_CONTRADICTIONS.get((feature, label), ""),
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
                        "avg_mfe_r": float(year_group["h40_mfe_r"].mean()),
                        "avg_mae_r": float(year_group["h40_mae_r"].mean()),
                    }
                )

    reliability = pd.DataFrame(rows)
    reliability["fail_reasons"] = reliability.apply(_fail_reasons, axis=1)
    reliability["passes_reliability_gate"] = reliability["fail_reasons"].eq("")
    reliability["classification"] = np.select(
        [
            reliability["passes_reliability_gate"],
            reliability["backtest_contradiction"].astype(str).ne(""),
            (reliability["good_lift_pp"] >= 10.0) & (reliability["rows"] >= 8),
        ],
        ["reliable_exemption_candidate", "watch_but_backtest_contradicted", "watch_only_sample_or_stability_gap"],
        default="not_reliable",
    )
    reliability = reliability.sort_values(
        ["passes_reliability_gate", "good_lift_pp", "avg_path_score_r", "rows"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)
    return reliability, pd.DataFrame(year_rows)


def _fail_reasons(row: pd.Series) -> str:
    reasons: list[str] = []
    if int(row["rows"]) < MIN_RELIABLE_ROWS:
        reasons.append(f"rows<{MIN_RELIABLE_ROWS}")
    if int(row["years"]) < MIN_RELIABLE_YEARS:
        reasons.append(f"years<{MIN_RELIABLE_YEARS}")
    if float(row["good_lift_pp"]) < MIN_GOOD_LIFT * 100.0:
        reasons.append(f"good_lift<{MIN_GOOD_LIFT * 100:.0f}pp")
    if float(row["bad_rate_pct"]) > MAX_BAD_RATE * 100.0:
        reasons.append(f"bad_rate>{MAX_BAD_RATE * 100:.0f}%")
    if int(row["years_good_ge_base"]) < MIN_GOOD_YEARS:
        reasons.append(f"good_years<{MIN_GOOD_YEARS}")
    if int(row["years_score_positive"]) < MIN_SCORE_POSITIVE_YEARS:
        reasons.append(f"positive_score_years<{MIN_SCORE_POSITIVE_YEARS}")
    if float(row["dominant_product_share_pct"]) > MAX_DOMINANT_PRODUCT_SHARE * 100.0:
        reasons.append(f"dominant_product_share>{MAX_DOMINANT_PRODUCT_SHARE * 100:.0f}%")
    if str(row.get("backtest_contradiction") or ""):
        reasons.append("contradicted_by_prior_backtest")
    return "; ".join(reasons)


def _watchlist(reliability: pd.DataFrame) -> pd.DataFrame:
    watch = reliability[
        reliability["classification"].isin(
            ["watch_but_backtest_contradicted", "watch_only_sample_or_stability_gap"]
        )
    ].copy()
    if watch.empty:
        return watch
    watch["watch_score"] = (
        watch["good_lift_pp"]
        - np.maximum(watch["bad_lift_pp"], 0.0)
        + np.minimum(watch["avg_path_score_r"], 20.0)
        + watch["years_good_ge_base"] * 2.0
    )
    return watch.sort_values(["watch_score", "rows"], ascending=[False, False]).reset_index(drop=True)


def _prior_backtest_summary() -> dict[str, Any]:
    summary = {
        "stage411_zero_volume_min_one": {
            "official_baseline_end_equity": 8728285,
            "official_min_one_end_equity": 6901460,
            "official_return_delta_pp": -913.4125,
            "stage407_baseline_end_equity": 3284935,
            "stage407_min_one_end_equity": 2643000,
            "decision": "not_promoted",
        },
        "stage420_low_risk_scout_sleeve": {
            "official_baseline_end_equity": 8728285,
            "official_plus_scout_end_equity": 8705625,
            "scout_pnl": -22660,
            "decision": "not_promoted",
        },
    }
    if SOURCE_STAGE698_DECISION_PATH.exists():
        try:
            payload = json.loads(SOURCE_STAGE698_DECISION_PATH.read_text(encoding="utf-8"))
            summary["stage411_zero_volume_min_one"]["decision_payload"] = payload.get("decision")
        except json.JSONDecodeError:
            pass
    return summary


def _plot(reliability: pd.DataFrame, watch: pd.DataFrame) -> None:
    plt.rcParams["font.family"] = "DejaVu Sans"
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    top = reliability.sort_values(["good_lift_pp", "avg_path_score_r"], ascending=[False, False]).head(12)
    colors = [
        "#2f855a" if cls == "reliable_exemption_candidate" else "#dd6b20" if "watch" in cls else "#718096"
        for cls in top["classification"]
    ]
    axes[0].barh(top["feature"] + "=" + top["feature_value"], top["good_lift_pp"], color=colors)
    axes[0].axvline(10.0, color="#2f855a", linestyle="--", linewidth=1.0, label="required +10pp")
    axes[0].axvline(0.0, color="#4a5568", linewidth=0.8)
    axes[0].set_title("H40 +2R first-hit lift vs actionable throttle baseline")
    axes[0].set_xlabel("good lift (pp)")
    axes[0].invert_yaxis()
    axes[0].legend()

    if not watch.empty:
        view = watch.head(10)
        axes[1].scatter(view["rows"], view["good_rate_pct"], s=80, color="#2b6cb0")
        for _, row in view.iterrows():
            axes[1].text(row["rows"] + 0.3, row["good_rate_pct"], f"{row['feature']}={row['feature_value']}", fontsize=8)
    axes[1].axhline(float(reliability["baseline_good_rate_pct"].iloc[0]), color="#4a5568", linestyle="--", label="baseline")
    axes[1].axvline(MIN_RELIABLE_ROWS, color="#2f855a", linestyle="--", label="required rows")
    axes[1].set_title("Watch features: sample size vs good rate")
    axes[1].set_xlabel("rows")
    axes[1].set_ylabel("H40 good rate (%)")
    axes[1].legend()

    fig.suptitle("Stage721 Throttle Exemption Feature Reliability", fontsize=15)
    fig.tight_layout(rect=[0, 0.02, 1, 0.94])
    CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _build_report(
    actionable: pd.DataFrame,
    reliability: pd.DataFrame,
    watch: pd.DataFrame,
    decision: dict[str, Any],
) -> str:
    top_columns = [
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
    watch_columns = [
        "feature",
        "feature_value",
        "rows",
        "good_rate_pct",
        "bad_rate_pct",
        "avg_path_score_r",
        "years",
        "years_good_ge_base",
        "dominant_product_share_pct",
        "classification",
        "backtest_contradiction",
    ]
    lines = [
        "# Stage721 Throttle Exemption Feature Reliability",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- generated_at: `{decision['generated_at']}`",
        f"- source: `{SOURCE_STAGE716_PATH}`",
        f"- actionable_h40_rows: `{len(actionable)}`",
        f"- baseline_h40_good_rate: `{decision['baseline_h40_good_rate_pct']:.4f}%`",
        f"- baseline_h40_bad_rate: `{decision['baseline_h40_bad_rate_pct']:.4f}%`",
        f"- decision: `{decision['decision']}`",
        "",
        "## Reliability Gate",
        "",
        f"- rows >= `{MIN_RELIABLE_ROWS}`",
        f"- years >= `{MIN_RELIABLE_YEARS}`",
        f"- H40 +2R first-hit lift >= `{MIN_GOOD_LIFT * 100:.0f}pp` vs actionable throttle baseline",
        f"- H40 -1R first-hit bad rate <= `{MAX_BAD_RATE * 100:.0f}%`",
        f"- good years >= `{MIN_GOOD_YEARS}` and positive-score years >= `{MIN_SCORE_POSITIVE_YEARS}`",
        f"- dominant product share <= `{MAX_DOMINANT_PRODUCT_SHARE * 100:.0f}%`",
        "- must not be contradicted by prior actual path backtests.",
        "",
        "## Top Feature Values",
        "",
        _md_table(reliability[top_columns], max_rows=25),
        "",
        "## Watchlist",
        "",
        _md_table(watch[watch_columns], max_rows=12),
        "",
        "## Interpretation",
        "",
        "- No positive feature passes the full reliability gate for bypassing the 0.1 loss-streak floor.",
        "- `sizing_zero_volume` and its alias-like `pair_missing` look attractive in fixed-horizon labels, but the actual Stage411 min-one backtest already reduced official equity materially.",
        "- `recovery_sleeve_reason=cooldown` has the best raw H40 good rate, but it has only 9 rows and is too small to support a trading rule.",
        "- Broad 0.1-floor groups still have high bad-first rates; the safer conclusion remains that three-loss throttling is a defensive state, not a hidden high-quality opportunity pool.",
        "",
        "## External Research Takeaway",
        "",
        "- Walk-forward/OOS checks are the minimum standard for trading filters because single-path feature selection can easily hide overfitting.",
        "- Losing-streak risk reduction is generally a capital-survival mechanism; overriding it requires stronger evidence than a small set of attractive historical examples.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    actionable = _load_actionable_candidates()
    reliability, year_detail = _feature_rows(actionable)
    watch = _watchlist(reliability)
    promoted = reliability[reliability["passes_reliability_gate"]]
    baseline_good = float(actionable["h40_barrier_good"].mean() * 100.0)
    baseline_bad = float(actionable["h40_barrier_bad"].mean() * 100.0)
    decision = {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": str(SOURCE_STAGE716_PATH),
        "actionable_h40_rows": int(len(actionable)),
        "baseline_h40_good_rate_pct": baseline_good,
        "baseline_h40_bad_rate_pct": baseline_bad,
        "promoted_feature_count": int(len(promoted)),
        "promoted_features": promoted[["feature", "feature_value"]].to_dict(orient="records"),
        "watch_features": watch.head(5)[["feature", "feature_value", "rows", "good_rate_pct", "fail_reasons"]].to_dict(
            orient="records"
        )
        if not watch.empty
        else [],
        "prior_backtests": _prior_backtest_summary(),
        "decision": "no_reliable_positive_exemption_feature_found",
        "next_step": (
            "Do not implement a 0.1 bypass from current historical features. If the goal continues, collect forward "
            "watch samples or build an upstream account-level selector with a predeclared label and enough OOS windows."
        ),
    }

    reliability.to_csv(FEATURE_RELIABILITY_PATH, index=False, encoding="utf-8-sig")
    year_detail.to_csv(YEAR_DETAIL_PATH, index=False, encoding="utf-8-sig")
    watch.to_csv(WATCHLIST_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(reliability, watch)
    REPORT_PATH.write_text(_build_report(actionable, reliability, watch, decision), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
