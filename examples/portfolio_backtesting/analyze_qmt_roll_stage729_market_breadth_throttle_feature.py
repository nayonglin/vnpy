from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage723_throttle_external_bar_features as s723


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage729_market_breadth_throttle_feature_v1"
OUTPUT_PREFIX = "qmt_roll_stage729_market_breadth_throttle_feature"
LINE_ID = "futures_trend_winner_trade_forensics"

SOURCE_STAGE716_PATH = s723.SOURCE_STAGE716_PATH
SOURCE_STAGE723_ENRICHED_PATH = s723.ENRICHED_PATH

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

MARKET_BREADTH_FEATURES = [
    "market_same_edge_share_bucket",
    "market_same_ret60_share_bucket",
    "market_net_edge_bucket",
    "market_net_ret60_bucket",
    "market_regime_bucket",
    "candidate_breadth_alignment_bucket",
    "product_edge_plus_breadth_bucket",
    "product_edge_plus_ret_breadth_bucket",
    "candidate_breadth_no_opposite_bucket",
]


def _json_safe(value: Any) -> Any:
    return s723._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s723._md_table(frame, max_rows=max_rows)


def _truthy(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "1.0", "yes", "y"})


def _load_universe() -> list[str]:
    if not SOURCE_STAGE716_PATH.exists():
        raise FileNotFoundError(SOURCE_STAGE716_PATH)
    data = pd.read_csv(SOURCE_STAGE716_PATH, encoding="utf-8-sig", usecols=["product_vt_symbol"])
    products = sorted(set(data["product_vt_symbol"].dropna().astype(str)))
    if not products:
        raise ValueError("empty official product universe")
    return products


def _load_enriched_candidates() -> pd.DataFrame:
    if SOURCE_STAGE723_ENRICHED_PATH.exists():
        data = pd.read_csv(SOURCE_STAGE723_ENRICHED_PATH, encoding="utf-8-sig")
    else:
        data = s723._load_actionable()
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
    data["date"] = pd.to_datetime(data["date"]).dt.normalize()
    if "year" not in data.columns:
        data["year"] = data["date"].dt.year
    data["year"] = data["year"].astype(int)
    return data.reset_index(drop=True)


def _bucket_edge_share(value: float) -> str:
    if pd.isna(value):
        return "missing"
    if value >= 0.30:
        return "edge_breadth_high_ge30p"
    if value >= 0.20:
        return "edge_breadth_mid_20_30p"
    return "edge_breadth_low_lt20p"


def _bucket_ret_share(value: float) -> str:
    if pd.isna(value):
        return "missing"
    if value >= 0.60:
        return "ret_breadth_high_ge60p"
    if value >= 0.45:
        return "ret_breadth_mid_45_60p"
    return "ret_breadth_low_lt45p"


def _bucket_net(value: float, *, strong: float = 0.10) -> str:
    if pd.isna(value):
        return "missing"
    if value >= strong:
        return "net_support_pos"
    if value <= -strong:
        return "net_against_neg"
    return "net_mixed"


def _market_regime(long_edge_share: float, short_edge_share: float) -> str:
    if pd.isna(long_edge_share) or pd.isna(short_edge_share):
        return "missing"
    if long_edge_share >= 0.30 and long_edge_share - short_edge_share >= 0.10:
        return "market_long_breadth"
    if short_edge_share >= 0.30 and short_edge_share - long_edge_share >= 0.10:
        return "market_short_breadth"
    if max(long_edge_share, short_edge_share) >= 0.30:
        return "market_two_sided_extreme"
    return "market_mixed_or_no_breadth"


def _candidate_alignment(direction: str, same_edge: float, opposite_edge: float) -> str:
    if pd.isna(same_edge) or pd.isna(opposite_edge):
        return "missing"
    if same_edge >= 0.30 and same_edge - opposite_edge >= 0.10:
        return "aligned_edge_breadth_strong"
    if same_edge >= 0.20 and same_edge >= opposite_edge:
        return "aligned_edge_breadth_mild"
    if opposite_edge - same_edge >= 0.10:
        return "breadth_against_candidate"
    return "breadth_mixed"


def _product_edge_plus_breadth(product_edge: str, alignment: str) -> str:
    if product_edge == "directional_edge" and alignment == "aligned_edge_breadth_strong":
        return "product_edge_and_market_breadth"
    if product_edge == "directional_edge":
        return "product_edge_without_market_breadth"
    if alignment == "aligned_edge_breadth_strong":
        return "market_breadth_without_product_edge"
    return "no_product_or_market_edge"


def _product_edge_plus_ret_breadth(product_edge: str, same_ret_bucket: str, net_ret_bucket: str) -> str:
    ret_broad = same_ret_bucket == "ret_breadth_high_ge60p" and net_ret_bucket == "net_support_pos"
    if product_edge == "directional_edge" and ret_broad:
        return "product_edge_and_ret_breadth"
    if product_edge == "directional_edge":
        return "product_edge_without_ret_breadth"
    if ret_broad:
        return "ret_breadth_without_product_edge"
    return "no_product_or_ret_breadth"


def _asof_map(features: pd.DataFrame, universe: list[str], date: pd.Timestamp) -> list[pd.Series]:
    rows: list[pd.Series] = []
    for vt_symbol in universe:
        row = s723._asof_row(features, vt_symbol, date)
        if row is not None:
            rows.append(row)
    return rows


def _snapshot(features: pd.DataFrame, universe: list[str], date: pd.Timestamp) -> dict[str, float]:
    rows = _asof_map(features, universe, date)
    available = [row for row in rows if not pd.isna(row.get("close_pos60", np.nan))]
    ret_available = [row for row in rows if not pd.isna(row.get("ret60", np.nan))]
    count = len(available)
    ret_count = len(ret_available)
    if count == 0:
        return {
            "market_available_count": 0,
            "market_ret_available_count": ret_count,
            "market_long_edge_share": np.nan,
            "market_short_edge_share": np.nan,
            "market_long_ret60_share": np.nan,
            "market_short_ret60_share": np.nan,
        }
    long_edge = sum(float(row["close_pos60"]) >= 0.80 for row in available)
    short_edge = sum(float(row["close_pos60"]) <= 0.20 for row in available)
    if ret_count:
        long_ret = sum(float(row["ret60"]) > 0.0 for row in ret_available)
        short_ret = sum(float(row["ret60"]) < 0.0 for row in ret_available)
        long_ret_share = long_ret / ret_count
        short_ret_share = short_ret / ret_count
    else:
        long_ret_share = np.nan
        short_ret_share = np.nan
    return {
        "market_available_count": count,
        "market_ret_available_count": ret_count,
        "market_long_edge_share": long_edge / count,
        "market_short_edge_share": short_edge / count,
        "market_long_ret60_share": long_ret_share,
        "market_short_ret60_share": short_ret_share,
    }


def _enrich_breadth(candidates: pd.DataFrame, bars: pd.DataFrame, universe: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    snapshot_cache: dict[pd.Timestamp, dict[str, float]] = {}
    for row in candidates.itertuples(index=False):
        record = row._asdict()
        date = pd.Timestamp(row.date).normalize()
        direction = str(row.direction)
        if date not in snapshot_cache:
            snapshot_cache[date] = _snapshot(bars, universe, date)
        snap = snapshot_cache[date]
        record.update(snap)
        same_edge = snap["market_long_edge_share"] if direction == "long" else snap["market_short_edge_share"]
        opposite_edge = snap["market_short_edge_share"] if direction == "long" else snap["market_long_edge_share"]
        same_ret = snap["market_long_ret60_share"] if direction == "long" else snap["market_short_ret60_share"]
        opposite_ret = snap["market_short_ret60_share"] if direction == "long" else snap["market_long_ret60_share"]
        record["market_same_edge_share"] = same_edge
        record["market_opposite_edge_share"] = opposite_edge
        record["market_net_edge_share"] = same_edge - opposite_edge if not pd.isna(same_edge) else np.nan
        record["market_same_ret60_share"] = same_ret
        record["market_opposite_ret60_share"] = opposite_ret
        record["market_net_ret60_share"] = same_ret - opposite_ret if not pd.isna(same_ret) else np.nan
        record["market_same_edge_share_bucket"] = _bucket_edge_share(record["market_same_edge_share"])
        record["market_same_ret60_share_bucket"] = _bucket_ret_share(record["market_same_ret60_share"])
        record["market_net_edge_bucket"] = _bucket_net(record["market_net_edge_share"])
        record["market_net_ret60_bucket"] = _bucket_net(record["market_net_ret60_share"], strong=0.15)
        record["market_regime_bucket"] = _market_regime(
            snap["market_long_edge_share"],
            snap["market_short_edge_share"],
        )
        record["candidate_breadth_alignment_bucket"] = _candidate_alignment(direction, same_edge, opposite_edge)
        product_edge = str(record.get("product_directional_edge60_bucket") or "missing")
        record["product_edge_plus_breadth_bucket"] = _product_edge_plus_breadth(
            product_edge,
            record["candidate_breadth_alignment_bucket"],
        )
        record["product_edge_plus_ret_breadth_bucket"] = _product_edge_plus_ret_breadth(
            product_edge,
            record["market_same_ret60_share_bucket"],
            record["market_net_ret60_bucket"],
        )
        record["candidate_breadth_no_opposite_bucket"] = (
            "same_breadth_without_opposite"
            if same_edge >= 0.20 and opposite_edge < 0.20
            else "opposite_or_mixed_breadth"
        )
        rows.append(record)
    return pd.DataFrame(rows)


def _dominant_share(group: pd.DataFrame) -> tuple[str, float]:
    share = group["product"].value_counts(normalize=True)
    if share.empty:
        return "", np.nan
    return str(share.index[0]), float(share.iloc[0])


def _feature_rows(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    baseline_good = float(data["h40_barrier_good"].mean())
    baseline_bad = float(data["h40_barrier_bad"].mean())
    baseline_score = float(data["h40_path_score_r"].mean())
    rows: list[dict[str, Any]] = []
    year_rows: list[dict[str, Any]] = []
    for feature in MARKET_BREADTH_FEATURES:
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
        ["reliable_market_breadth_candidate", "watch_only_market_breadth_sample_or_stability_gap"],
        default="not_reliable",
    )
    return (
        metrics.sort_values(
            ["passes_reliability_gate", "screen_score", "good_lift_pp", "rows"],
            ascending=[False, False, False, False],
        ).reset_index(drop=True),
        pd.DataFrame(year_rows),
    )


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


def _coverage(enriched: pd.DataFrame, universe: list[str]) -> dict[str, Any]:
    return {
        "candidate_rows": int(len(enriched)),
        "universe_products": int(len(universe)),
        "median_available_products": float(enriched["market_available_count"].median()),
        "min_available_products": int(enriched["market_available_count"].min()),
        "median_ret_available_products": float(enriched["market_ret_available_count"].median()),
        "baseline_good_rate_pct": float(enriched["h40_barrier_good"].mean() * 100.0),
        "baseline_bad_rate_pct": float(enriched["h40_barrier_bad"].mean() * 100.0),
        "baseline_path_score_r": float(enriched["h40_path_score_r"].mean()),
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
    axes[0].set_title("Market breadth features: H40 good lift")
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
    fig.suptitle("Stage729 Market Breadth Throttle Feature Audit", fontsize=15)
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
            "# Stage729 Market Breadth Throttle Feature Audit",
            "",
            f"- line_id: `{LINE_ID}`",
            f"- generated_at: `{decision['generated_at']}`",
            f"- source_stage716: `{SOURCE_STAGE716_PATH}`",
            f"- source_stage723: `{SOURCE_STAGE723_ENRICHED_PATH}`",
            f"- database: `{s723.DATABASE_PATH}`",
            f"- actionable_h40_rows: `{len(enriched)}`",
            f"- initial_gate_candidate_count: `{decision['initial_gate_candidate_count']}`",
            f"- decision: `{decision['decision']}`",
            "",
            "## Predeclared Features",
            "",
            "- Same-direction edge breadth: share of the official universe at 60-day range extremes aligned with the candidate direction.",
            "- Same-direction ret60 breadth: share of the official universe with 60-day return aligned with the candidate direction.",
            "- Net breadth: same-direction breadth minus opposite-direction breadth.",
            "- Product edge plus breadth: candidate product directional edge combined with cross-sectional breadth.",
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
            "## Top Market Breadth Features",
            "",
            _md_table(metrics[columns], max_rows=25) if not metrics.empty else "_empty_",
            "",
            "## Interpretation",
            "",
            "- This is a read-only audit. It does not change the official strategy or run order logic.",
            "- The breadth buckets are fixed before inspecting the result and do not use product names, years, or the red-box window.",
            "- A surviving initial gate would still need a predeclared A/C strategy replay before any official-rule change.",
        ]
    ) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = _load_enriched_candidates()
    universe = _load_universe()
    bars = s723._add_rolling_features(s723._load_bar_frame(universe))
    enriched = _enrich_breadth(candidates, bars, universe)
    metrics, year_detail = _feature_rows(enriched)
    initial_gate = metrics[metrics["passes_reliability_gate"]] if not metrics.empty else metrics
    has_initial_gate = not initial_gate.empty
    decision = {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_stage716": str(SOURCE_STAGE716_PATH),
        "source_stage723": str(SOURCE_STAGE723_ENRICHED_PATH),
        "database": str(s723.DATABASE_PATH),
        "universe": universe,
        "coverage": _coverage(enriched, universe),
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
            "market_breadth_initial_gate_candidate_requires_strategy_ab_validation"
            if has_initial_gate
            else "no_market_breadth_reliable_exemption_feature_found"
        ),
        "next_step": (
            "Run a predeclared A/C replay for the surviving market-breadth gate."
            if has_initial_gate
            else "Do not implement a market-breadth exemption. Continue only via forward watch or new orthogonal data."
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
