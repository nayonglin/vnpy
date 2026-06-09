from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage723_throttle_external_bar_features as s723


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage729_market_breadth_throttle_features_v1"
OUTPUT_PREFIX = "qmt_roll_stage729_market_breadth_throttle_features"
LINE_ID = "futures_trend_winner_trade_forensics"

SOURCE_STAGE716_PATH = s723.SOURCE_STAGE716_PATH

ENRICHED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_enriched_candidates_{MODEL_TAG}.csv"
DATE_BREADTH_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_date_breadth_{MODEL_TAG}.csv"
FEATURE_METRICS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_metrics_{MODEL_TAG}.csv"
YEAR_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_detail_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

MIN_RELIABLE_ROWS = 30
MIN_RELIABLE_YEARS = 4
MIN_RELIABLE_PRODUCTS = 6
MAX_DOMINANT_PRODUCT_SHARE = 0.35
MIN_GOOD_LIFT_PP = 10.0
MAX_BAD_RATE_PCT = 60.0
MIN_GOOD_YEARS = 4
MIN_POSITIVE_SCORE_YEARS = 4

MARKET_FEATURES = [
    "market_trend_breadth_bucket",
    "market_net_direction_bucket",
    "market_abs_momentum_bucket",
    "candidate_market_alignment_bucket",
    "candidate_same_side_breadth_bucket",
    "candidate_opposite_side_breadth_bucket",
    "candidate_side_dominance_bucket",
    "candidate_supported_regime_bucket",
]


def _truthy(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "1.0", "yes", "y"})


def _load_official_universe() -> list[str]:
    if not SOURCE_STAGE716_PATH.exists():
        raise FileNotFoundError(SOURCE_STAGE716_PATH)
    data = pd.read_csv(SOURCE_STAGE716_PATH, usecols=["product_vt_symbol"], encoding="utf-8-sig")
    universe = sorted(data["product_vt_symbol"].dropna().astype(str).unique().tolist())
    if not universe:
        raise RuntimeError("empty official product universe")
    return universe


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
        return float(value) if np.isfinite(value) else None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _bucket_breadth(value: float) -> str:
    if pd.isna(value):
        return "missing"
    if value >= 0.45:
        return "breadth_strong_ge45"
    if value >= 0.25:
        return "breadth_mid_25_45"
    return "breadth_weak_lt25"


def _bucket_net_direction(value: float) -> str:
    if pd.isna(value):
        return "missing"
    if value >= 0.20:
        return "net_up_ge20"
    if value <= -0.20:
        return "net_down_le_minus20"
    return "net_balanced"


def _bucket_abs_momentum(value: float) -> str:
    if pd.isna(value):
        return "missing"
    if value >= 0.08:
        return "abs_mom_high_ge8"
    if value >= 0.04:
        return "abs_mom_mid_4_8"
    return "abs_mom_low_lt4"


def _bucket_side_ratio(value: float, prefix: str) -> str:
    if pd.isna(value):
        return "missing"
    if value >= 0.30:
        return f"{prefix}_high_ge30"
    if value >= 0.15:
        return f"{prefix}_mid_15_30"
    return f"{prefix}_low_lt15"


def _asof_universe_rows(features: pd.DataFrame, universe: list[str], date: pd.Timestamp) -> pd.DataFrame:
    rows: list[pd.Series] = []
    for vt_symbol in universe:
        row = s723._asof_row(features, vt_symbol, date)
        if row is not None:
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _date_breadth_rows(
    features: pd.DataFrame,
    universe: list[str],
    dates: list[pd.Timestamp],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for date in sorted(set(pd.Timestamp(item).normalize() for item in dates)):
        frame = _asof_universe_rows(features, universe, date)
        if frame.empty:
            rows.append(
                {
                    "date": date,
                    "available_products": 0,
                    "up_trend_count": 0,
                    "down_trend_count": 0,
                    "directional_trend_count": 0,
                    "up_trend_ratio": np.nan,
                    "down_trend_ratio": np.nan,
                    "directional_trend_ratio": np.nan,
                    "net_trend_ratio": np.nan,
                    "median_abs_ret60": np.nan,
                    "market_trend_breadth_bucket": "missing",
                    "market_net_direction_bucket": "missing",
                    "market_abs_momentum_bucket": "missing",
                }
            )
            continue
        ret60 = pd.to_numeric(frame.get("ret60"), errors="coerce")
        close_pos60 = pd.to_numeric(frame.get("close_pos60"), errors="coerce")
        valid = ret60.notna() & close_pos60.notna()
        available = int(valid.sum())
        up = valid & ret60.gt(0.05) & close_pos60.ge(0.67)
        down = valid & ret60.lt(-0.05) & close_pos60.le(0.33)
        up_count = int(up.sum())
        down_count = int(down.sum())
        directional_count = up_count + down_count
        up_ratio = up_count / available if available else np.nan
        down_ratio = down_count / available if available else np.nan
        directional_ratio = directional_count / available if available else np.nan
        net_ratio = (up_count - down_count) / available if available else np.nan
        median_abs_ret60 = float(ret60[valid].abs().median()) if available else np.nan
        rows.append(
            {
                "date": date,
                "available_products": available,
                "up_trend_count": up_count,
                "down_trend_count": down_count,
                "directional_trend_count": directional_count,
                "up_trend_ratio": up_ratio,
                "down_trend_ratio": down_ratio,
                "directional_trend_ratio": directional_ratio,
                "net_trend_ratio": net_ratio,
                "median_abs_ret60": median_abs_ret60,
                "market_trend_breadth_bucket": _bucket_breadth(directional_ratio),
                "market_net_direction_bucket": _bucket_net_direction(net_ratio),
                "market_abs_momentum_bucket": _bucket_abs_momentum(median_abs_ret60),
            }
        )
    return pd.DataFrame(rows)


def _candidate_alignment(row: pd.Series) -> str:
    net_bucket = str(row.get("market_net_direction_bucket") or "")
    direction = str(row.get("direction") or "")
    if net_bucket == "net_balanced":
        return "market_balanced"
    if (direction == "long" and net_bucket == "net_up_ge20") or (
        direction == "short" and net_bucket == "net_down_le_minus20"
    ):
        return "candidate_aligned"
    if net_bucket in {"net_up_ge20", "net_down_le_minus20"}:
        return "candidate_counter"
    return "missing"


def _side_dominance(row: pd.Series) -> str:
    same = float(row.get("candidate_same_side_trend_ratio", np.nan))
    opposite = float(row.get("candidate_opposite_side_trend_ratio", np.nan))
    if pd.isna(same) or pd.isna(opposite):
        return "missing"
    if same >= 0.30 and opposite <= 0.15:
        return "same_side_dominant"
    if same >= 0.30:
        return "same_side_present"
    if same < 0.15:
        return "same_side_absent"
    return "side_mixed"


def _supported_regime(row: pd.Series) -> str:
    if row.get("market_trend_breadth_bucket") == "breadth_weak_lt25":
        return "trend_chop"
    if row.get("candidate_side_dominance_bucket") == "same_side_dominant":
        return "candidate_supported_regime"
    if row.get("candidate_market_alignment_bucket") == "candidate_aligned":
        return "candidate_aligned_mixed_breadth"
    if row.get("candidate_market_alignment_bucket") == "candidate_counter":
        return "candidate_counter_regime"
    return "mixed_regime"


def _enrich_candidates(candidates: pd.DataFrame, breadth: pd.DataFrame) -> pd.DataFrame:
    data = candidates.copy()
    data["date"] = pd.to_datetime(data["date"]).dt.normalize()
    merged = data.merge(breadth, on="date", how="left")
    merged["candidate_same_side_trend_ratio"] = np.where(
        merged["direction"].astype(str).eq("long"),
        merged["up_trend_ratio"],
        np.where(merged["direction"].astype(str).eq("short"), merged["down_trend_ratio"], np.nan),
    )
    merged["candidate_opposite_side_trend_ratio"] = np.where(
        merged["direction"].astype(str).eq("long"),
        merged["down_trend_ratio"],
        np.where(merged["direction"].astype(str).eq("short"), merged["up_trend_ratio"], np.nan),
    )
    merged["candidate_market_alignment_bucket"] = merged.apply(_candidate_alignment, axis=1)
    merged["candidate_same_side_breadth_bucket"] = merged["candidate_same_side_trend_ratio"].map(
        lambda value: _bucket_side_ratio(value, "same")
    )
    merged["candidate_opposite_side_breadth_bucket"] = merged["candidate_opposite_side_trend_ratio"].map(
        lambda value: _bucket_side_ratio(value, "opposite")
    )
    merged["candidate_side_dominance_bucket"] = merged.apply(_side_dominance, axis=1)
    merged["candidate_supported_regime_bucket"] = merged.apply(_supported_regime, axis=1)
    return merged


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
    for feature in MARKET_FEATURES:
        if feature not in data.columns:
            continue
        for value, group in data.groupby(feature, dropna=False):
            label = "missing" if pd.isna(value) or str(value) == "" else str(value)
            if label in {"missing", "nan", ""} or len(group) < 5:
                continue
            dominant_product, dominant_share = _dominant_share(group)
            year_stats = group.groupby("year").agg(
                rows=("candidate_index", "count"),
                good_rate=("h40_barrier_good", "mean"),
                bad_rate=("h40_barrier_bad", "mean"),
                avg_score=("h40_path_score_r", "mean"),
            )
            row = {
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
                "dominant_product_share_pct": float(dominant_share * 100.0),
                "baseline_good_rate_pct": baseline_good * 100.0,
                "baseline_bad_rate_pct": baseline_bad * 100.0,
                "baseline_path_score_r": baseline_score,
            }
            rows.append(row)
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
        ["reliable_market_breadth_exemption_candidate", "watch_only_market_breadth_sample_or_stability_gap"],
        default="not_reliable",
    )
    metrics = metrics.sort_values(
        ["passes_reliability_gate", "screen_score", "good_lift_pp", "rows"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)
    return metrics, pd.DataFrame(year_rows)


def _coverage_summary(enriched: pd.DataFrame, universe: list[str]) -> dict[str, Any]:
    return {
        "candidate_rows": int(len(enriched)),
        "universe_products": int(len(universe)),
        "median_available_products": float(pd.to_numeric(enriched["available_products"], errors="coerce").median()),
        "min_available_products": int(pd.to_numeric(enriched["available_products"], errors="coerce").min()),
        "max_available_products": int(pd.to_numeric(enriched["available_products"], errors="coerce").max()),
        "baseline_good_rate_pct": float(enriched["h40_barrier_good"].mean() * 100.0),
        "baseline_bad_rate_pct": float(enriched["h40_barrier_bad"].mean() * 100.0),
        "baseline_path_score_r": float(enriched["h40_path_score_r"].mean()),
    }


def _write_report(
    enriched: pd.DataFrame,
    date_breadth: pd.DataFrame,
    metrics: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
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
        "years_score_positive",
        "product_count",
        "dominant_product_share_pct",
        "classification",
        "fail_reasons",
    ]
    lines = [
        "# Stage729 Market Breadth Throttle Features",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- generated_at：`{decision['generated_at']}`",
        f"- source：`{SOURCE_STAGE716_PATH}`",
        f"- database：`{s723.DATABASE_PATH}`",
        "- 目的：只读审计三连败低风险档候选是否能被全池趋势广度识别为高质量机会。",
        "- 不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## Coverage",
        "",
        s723._md_table(pd.DataFrame([decision["coverage"]]), max_rows=None),
        "",
        "## Date Breadth Sample",
        "",
        s723._md_table(date_breadth.head(20), max_rows=20),
        "",
        "## Feature Metrics",
        "",
        s723._md_table(metrics[columns], max_rows=40) if not metrics.empty else "_empty_",
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- initial_gate_candidate_count：`{decision['initial_gate_candidate_count']}`",
        "",
        "## Interpretation",
        "",
        "- 本阶段只使用全池趋势状态，不使用产品名、年份、红框或事后交易结果训练。",
        "- 如果特征不能同时满足样本、年份、产品覆盖、good lift、bad rate 和年度稳定性，就不能进入策略 A/C。",
        "- 若出现初筛候选，也只代表下一步可做预声明策略回测，不能直接接正式版。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = s723._load_actionable()
    universe = _load_official_universe()
    product_bars = s723._add_rolling_features(s723._load_bar_frame(universe))
    if product_bars.empty:
        raise RuntimeError("empty product breadth bars")
    breadth = _date_breadth_rows(product_bars, universe, candidates["date"].tolist())
    enriched = _enrich_candidates(candidates, breadth)
    metrics, year_detail = _feature_rows(enriched)
    initial_gate = metrics[metrics["passes_reliability_gate"]] if not metrics.empty else pd.DataFrame()
    decision_label = (
        "market_breadth_initial_gate_candidate_requires_strategy_ab_validation"
        if not initial_gate.empty
        else "no_market_breadth_exemption_feature_found"
    )
    decision = {
        "stage": "Stage011",
        "script_stage": "Stage729",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": str(SOURCE_STAGE716_PATH),
        "database": str(s723.DATABASE_PATH),
        "decision": decision_label,
        "coverage": _coverage_summary(enriched, universe),
        "initial_gate_candidate_count": int(len(initial_gate)),
        "initial_gate_candidates": initial_gate[
            ["feature", "feature_value", "rows", "good_rate_pct", "good_lift_pp", "bad_rate_pct"]
        ].to_dict(orient="records")
        if not initial_gate.empty
        else [],
        "top_watch_features": metrics.head(10)[
            ["feature", "feature_value", "rows", "good_rate_pct", "good_lift_pp", "bad_rate_pct", "fail_reasons"]
        ].to_dict(orient="records")
        if not metrics.empty
        else [],
        "outputs": {
            "enriched": str(ENRICHED_PATH),
            "date_breadth": str(DATE_BREADTH_PATH),
            "feature_metrics": str(FEATURE_METRICS_PATH),
            "year_detail": str(YEAR_DETAIL_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }
    enriched.to_csv(ENRICHED_PATH, index=False, encoding="utf-8-sig")
    breadth.to_csv(DATE_BREADTH_PATH, index=False, encoding="utf-8-sig")
    metrics.to_csv(FEATURE_METRICS_PATH, index=False, encoding="utf-8-sig")
    year_detail.to_csv(YEAR_DETAIL_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(enriched, breadth, metrics, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
