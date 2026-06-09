from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage723_throttle_external_bar_features as s723


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage731_slow_trend_throttle_features_v1"
OUTPUT_PREFIX = "qmt_roll_stage731_slow_trend_throttle_features"
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

SLOW_TREND_FEATURES = [
    "product_signed_ret120_bucket",
    "product_signed_ret200_bucket",
    "product_directional_edge120_bucket",
    "product_directional_edge200_bucket",
    "product_ma50_200_alignment_bucket",
    "product_ma100_200_alignment_bucket",
    "product_slow_trend_consensus_bucket",
    "product_fast_slow_agreement_bucket",
    "product_slow_trend_without_fast_edge_bucket",
]


def _json_safe(value: Any) -> Any:
    return s723._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s723._md_table(frame, max_rows=max_rows)


def _load_candidates() -> pd.DataFrame:
    if SOURCE_STAGE723_ENRICHED_PATH.exists():
        data = pd.read_csv(SOURCE_STAGE723_ENRICHED_PATH, encoding="utf-8-sig")
    else:
        data = s723._load_actionable()
    data["date"] = pd.to_datetime(data["date"]).dt.normalize()
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
    data["year"] = data["year"].astype(int)
    return data.reset_index(drop=True)


def _add_slow_features(bars: pd.DataFrame) -> pd.DataFrame:
    base = s723._add_rolling_features(bars)
    frames: list[pd.DataFrame] = []
    for vt_symbol, group in base.groupby("vt_symbol"):
        df = group.sort_values("date").copy()
        close = df["close_price"].replace(0.0, np.nan)
        high = df["high_price"]
        low = df["low_price"]
        df["ret120"] = close / close.shift(120) - 1.0
        df["ret200"] = close / close.shift(200) - 1.0
        df["ma50"] = close.rolling(50, min_periods=30).mean()
        df["ma100"] = close.rolling(100, min_periods=60).mean()
        df["ma200"] = close.rolling(200, min_periods=120).mean()
        high120 = high.rolling(120, min_periods=80).max()
        low120 = low.rolling(120, min_periods=80).min()
        high200 = high.rolling(200, min_periods=120).max()
        low200 = low.rolling(200, min_periods=120).min()
        df["close_pos120"] = (close - low120) / (high120 - low120)
        df["close_pos200"] = (close - low200) / (high200 - low200)
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _bucket_signed_ret(value: float, *, medium: float = 0.05, strong: float = 0.15) -> str:
    if pd.isna(value):
        return "missing"
    if value >= strong:
        return "signed_ret_strong_pos"
    if value >= medium:
        return "signed_ret_mild_pos"
    if value > -medium:
        return "signed_ret_flat"
    return "signed_ret_neg"


def _bucket_edge(direction: str, close_pos: float, suffix: str) -> str:
    if pd.isna(close_pos):
        return "missing"
    if direction == "long":
        if close_pos >= 0.80:
            return f"directional_edge{suffix}"
        if close_pos <= 0.20:
            return f"counter_edge{suffix}"
        return f"range_middle{suffix}"
    if direction == "short":
        if close_pos <= 0.20:
            return f"directional_edge{suffix}"
        if close_pos >= 0.80:
            return f"counter_edge{suffix}"
        return f"range_middle{suffix}"
    return "missing"


def _ma_alignment(direction: str, close: float, fast_ma: float, slow_ma: float, suffix: str) -> str:
    if pd.isna(close) or pd.isna(fast_ma) or pd.isna(slow_ma):
        return "missing"
    if direction == "long":
        if close > slow_ma and fast_ma > slow_ma:
            return f"ma{suffix}_aligned"
        if close < slow_ma and fast_ma < slow_ma:
            return f"ma{suffix}_counter"
        return f"ma{suffix}_mixed"
    if direction == "short":
        if close < slow_ma and fast_ma < slow_ma:
            return f"ma{suffix}_aligned"
        if close > slow_ma and fast_ma > slow_ma:
            return f"ma{suffix}_counter"
        return f"ma{suffix}_mixed"
    return "missing"


def _slow_consensus(signed_ret120: float, signed_ret200: float, ma50_200: str, ma100_200: str) -> str:
    ret_ok = not pd.isna(signed_ret120) and not pd.isna(signed_ret200) and signed_ret120 > 0.0 and signed_ret200 > 0.0
    ret_bad = not pd.isna(signed_ret120) and not pd.isna(signed_ret200) and signed_ret120 < 0.0 and signed_ret200 < 0.0
    ma_ok = ma50_200.endswith("_aligned") and ma100_200.endswith("_aligned")
    ma_bad = ma50_200.endswith("_counter") and ma100_200.endswith("_counter")
    if ret_ok and ma_ok:
        return "slow_consensus_aligned"
    if ret_bad and ma_bad:
        return "slow_consensus_counter"
    if ret_ok or ma_ok:
        return "slow_consensus_partial"
    return "slow_consensus_missing_or_mixed"


def _fast_slow_agreement(fast_edge: str, slow_consensus: str) -> str:
    fast_ok = fast_edge == "directional_edge"
    slow_ok = slow_consensus == "slow_consensus_aligned"
    if fast_ok and slow_ok:
        return "fast_edge_and_slow_consensus"
    if fast_ok:
        return "fast_edge_without_slow_consensus"
    if slow_ok:
        return "slow_consensus_without_fast_edge"
    return "no_fast_or_slow_consensus"


def _enrich_slow_trend(candidates: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in candidates.itertuples(index=False):
        record = row._asdict()
        date = pd.Timestamp(row.date).normalize()
        direction = str(row.direction)
        product_vt = str(row.product_vt_symbol)
        product_bar = s723._asof_row(bars, product_vt, date)
        if product_bar is None:
            for column in [
                "ret120",
                "ret200",
                "close_pos120",
                "close_pos200",
                "ma50",
                "ma100",
                "ma200",
            ]:
                record[f"product_{column}"] = np.nan
            signed_ret120 = np.nan
            signed_ret200 = np.nan
            close = np.nan
        else:
            sign = 1.0 if direction == "long" else -1.0 if direction == "short" else np.nan
            close = float(product_bar.get("close_price", np.nan))
            signed_ret120 = sign * float(product_bar.get("ret120", np.nan))
            signed_ret200 = sign * float(product_bar.get("ret200", np.nan))
            for column in [
                "ret120",
                "ret200",
                "close_pos120",
                "close_pos200",
                "ma50",
                "ma100",
                "ma200",
            ]:
                record[f"product_{column}"] = float(product_bar.get(column, np.nan))
        record["product_signed_ret120"] = signed_ret120
        record["product_signed_ret200"] = signed_ret200
        record["product_signed_ret120_bucket"] = _bucket_signed_ret(signed_ret120)
        record["product_signed_ret200_bucket"] = _bucket_signed_ret(signed_ret200)
        record["product_directional_edge120_bucket"] = _bucket_edge(
            direction,
            record["product_close_pos120"],
            "120",
        )
        record["product_directional_edge200_bucket"] = _bucket_edge(
            direction,
            record["product_close_pos200"],
            "200",
        )
        record["product_ma50_200_alignment_bucket"] = _ma_alignment(
            direction,
            close,
            record["product_ma50"],
            record["product_ma200"],
            "50_200",
        )
        record["product_ma100_200_alignment_bucket"] = _ma_alignment(
            direction,
            close,
            record["product_ma100"],
            record["product_ma200"],
            "100_200",
        )
        record["product_slow_trend_consensus_bucket"] = _slow_consensus(
            signed_ret120,
            signed_ret200,
            record["product_ma50_200_alignment_bucket"],
            record["product_ma100_200_alignment_bucket"],
        )
        fast_edge = str(record.get("product_directional_edge60_bucket") or "missing")
        record["product_fast_slow_agreement_bucket"] = _fast_slow_agreement(
            fast_edge,
            record["product_slow_trend_consensus_bucket"],
        )
        record["product_slow_trend_without_fast_edge_bucket"] = (
            "slow_without_fast_yes"
            if record["product_fast_slow_agreement_bucket"] == "slow_consensus_without_fast_edge"
            else "slow_without_fast_no"
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
    for feature in SLOW_TREND_FEATURES:
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
        ["reliable_slow_trend_candidate", "watch_only_slow_trend_sample_or_stability_gap"],
        default="not_reliable",
    )
    metrics = metrics.sort_values(
        ["passes_reliability_gate", "screen_score", "good_lift_pp", "rows"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)
    return metrics, pd.DataFrame(year_rows)


def _coverage(enriched: pd.DataFrame) -> dict[str, Any]:
    return {
        "candidate_rows": int(len(enriched)),
        "nonmissing_ret120_pct": float(enriched["product_signed_ret120"].notna().mean() * 100.0),
        "nonmissing_ret200_pct": float(enriched["product_signed_ret200"].notna().mean() * 100.0),
        "nonmissing_ma200_pct": float(enriched["product_ma200"].notna().mean() * 100.0),
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
    axes[0].set_title("Slow-trend features: H40 good lift")
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
    fig.suptitle("Stage731 Slow-Trend Throttle Feature Audit", fontsize=15)
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
            "# Stage731 Slow-Trend Throttle Feature Audit",
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
            "## Predeclared Slow-Trend Features",
            "",
            "- 120/200-day signed return aligned with the candidate direction.",
            "- 120/200-day range-edge state aligned with the candidate direction.",
            "- 50/200 and 100/200 moving-average alignment.",
            "- Slow-trend consensus and its agreement with the prior 60-day directional edge.",
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
            "## Top Slow-Trend Features",
            "",
            _md_table(metrics[columns], max_rows=25) if not metrics.empty else "_empty_",
            "",
            "## Interpretation",
            "",
            "- This audit is read-only and uses fixed 120/200-day slow trend definitions.",
            "- A surviving gate is still only an initial candidate and must pass a predeclared A/C strategy replay before promotion.",
            "- Failing gates imply slow-trend evidence should remain diagnostic/watch evidence, not a 0.1-bypass rule.",
        ]
    ) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = _load_candidates()
    universe = sorted(set(candidates["product_vt_symbol"].dropna().astype(str)))
    bars = _add_slow_features(s723._load_bar_frame(universe))
    enriched = _enrich_slow_trend(candidates, bars)
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
            "slow_trend_initial_gate_candidate_requires_strategy_ac_validation"
            if has_initial_gate
            else "no_slow_trend_reliable_exemption_feature_found"
        ),
        "next_step": (
            "Run a predeclared A/C replay for the surviving slow-trend gate."
            if has_initial_gate
            else "Do not implement a slow-trend exemption. Continue only via truly independent data or forward watch."
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
