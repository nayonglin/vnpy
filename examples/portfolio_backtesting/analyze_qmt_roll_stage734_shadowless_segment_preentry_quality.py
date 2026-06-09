from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage733_shadowless_preentry_quality as s733


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage734_shadowless_segment_preentry_quality_v1"
OUTPUT_PREFIX = "qmt_roll_stage734_shadowless_segment_preentry_quality"
LINE_ID = "futures_trend_winner_trade_forensics"

ENRICHED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_enriched_closed_lots_{MODEL_TAG}.csv"
FEATURE_METRICS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_metrics_{MODEL_TAG}.csv"
YEAR_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_detail_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

WINDOWS = [10, 20, 40]
MIN_RELIABLE_ROWS = 30
MIN_RELIABLE_YEARS = 5
MIN_RELIABLE_PRODUCTS = 8
MAX_DOMINANT_PRODUCT_SHARE = 0.30
MIN_AVG_R_LIFT = 0.50
MIN_BIG_WINNER_RATE_LIFT_PP = 5.0
MIN_POSITIVE_R_YEARS = 5
MAX_BAD_RATE_PCT = 55.0

SEGMENT_FEATURE_BUCKETS = [
    "pre10_avg_total_wick_le40",
    "pre20_avg_total_wick_le40",
    "pre40_avg_total_wick_le40",
    "pre10_short30_ratio_ge50",
    "pre20_short30_ratio_ge50",
    "pre40_short30_ratio_ge50",
    "pre10_body60_ratio_ge50",
    "pre20_body60_ratio_ge50",
    "pre40_body60_ratio_ge50",
    "pre10_long60_ratio_le20",
    "pre20_long60_ratio_le20",
    "pre40_long60_ratio_le20",
    "pre10_avg_adverse_wick_le25",
    "pre20_avg_adverse_wick_le25",
    "pre40_avg_adverse_wick_le25",
    "pre10_directional_close_strength_ge60",
    "pre20_directional_close_strength_ge60",
    "pre40_directional_close_strength_ge60",
    "pre20_clean_segment_combo",
    "pre40_clean_segment_combo",
]


def _segment_stats(bars: pd.DataFrame, entry_date: pd.Timestamp, direction: str, window: int) -> dict[str, Any]:
    prior = bars[bars["date"] < entry_date].tail(window).copy()
    if len(prior) < window:
        return {}
    featured = s733._add_candle_features(prior, direction)
    total = featured["total_wick_pct_of_range"]
    body = featured["body_pct_of_range"]
    adverse = featured["adverse_wick_pct_of_range"]
    directional_strength = featured["directional_close_strength"]
    result: dict[str, Any] = {
        f"pre{window}_available_bars": int(len(featured)),
        f"pre{window}_first_bar_date": featured["date"].iloc[0].strftime("%Y-%m-%d"),
        f"pre{window}_last_bar_date": featured["date"].iloc[-1].strftime("%Y-%m-%d"),
        f"pre{window}_avg_total_wick_pct": float(total.mean()),
        f"pre{window}_median_total_wick_pct": float(total.median()),
        f"pre{window}_p80_total_wick_pct": float(total.quantile(0.80)),
        f"pre{window}_avg_body_pct": float(body.mean()),
        f"pre{window}_avg_adverse_wick_pct": float(adverse.mean()),
        f"pre{window}_avg_favorable_wick_pct": float(featured["favorable_wick_pct_of_range"].mean()),
        f"pre{window}_avg_directional_close_strength": float(directional_strength.mean()),
        f"pre{window}_short20_ratio": float((total <= 0.20).mean()),
        f"pre{window}_short30_ratio": float((total <= 0.30).mean()),
        f"pre{window}_body60_ratio": float((body >= 0.60).mean()),
        f"pre{window}_long60_ratio": float((total >= 0.60).mean()),
        f"pre{window}_directional_bar_ratio": float(featured["directional_bar"].mean()),
        f"pre{window}_marubozu_directional_ratio": float(featured["marubozu_directional_bar"].mean()),
    }
    return result


def _enrich_lots(lots: pd.DataFrame) -> pd.DataFrame:
    bar_cache: dict[str, pd.DataFrame] = {}
    records: list[dict[str, Any]] = []
    for row in lots.itertuples(index=False):
        record = row._asdict()
        vt_symbol = str(row.vt_symbol)
        bars = bar_cache.get(vt_symbol)
        if bars is None:
            bars = s733._load_contract_bars(vt_symbol)
            bar_cache[vt_symbol] = bars
        if not bars.empty:
            entry_date = pd.Timestamp(row.entry_date).normalize()
            direction = str(row.direction)
            for window in WINDOWS:
                record.update(_segment_stats(bars, entry_date, direction, window))
        records.append(record)
    enriched = pd.DataFrame(records)
    enriched["entry_year"] = pd.to_datetime(enriched["entry_date"]).dt.year

    for window in WINDOWS:
        prefix = f"pre{window}"
        enriched[f"{prefix}_avg_total_wick_le40"] = enriched[f"{prefix}_avg_total_wick_pct"] <= 0.40
        enriched[f"{prefix}_short30_ratio_ge50"] = enriched[f"{prefix}_short30_ratio"] >= 0.50
        enriched[f"{prefix}_body60_ratio_ge50"] = enriched[f"{prefix}_body60_ratio"] >= 0.50
        enriched[f"{prefix}_long60_ratio_le20"] = enriched[f"{prefix}_long60_ratio"] <= 0.20
        enriched[f"{prefix}_avg_adverse_wick_le25"] = enriched[f"{prefix}_avg_adverse_wick_pct"] <= 0.25
        enriched[f"{prefix}_directional_close_strength_ge60"] = (
            enriched[f"{prefix}_avg_directional_close_strength"] >= 0.60
        )

    enriched["pre20_clean_segment_combo"] = (
        (enriched["pre20_short30_ratio"] >= 0.40)
        & (enriched["pre20_long60_ratio"] <= 0.20)
        & (enriched["pre20_avg_body_pct"] >= 0.50)
    )
    enriched["pre40_clean_segment_combo"] = (
        (enriched["pre40_short30_ratio"] >= 0.40)
        & (enriched["pre40_long60_ratio"] <= 0.20)
        & (enriched["pre40_avg_body_pct"] >= 0.50)
    )
    return enriched


def _baseline_metrics(data: pd.DataFrame) -> dict[str, float]:
    valid = data.dropna(subset=["r_multiple"]).copy()
    return {
        "rows": float(len(valid)),
        "avg_r": float(valid["r_multiple"].mean()),
        "median_r": float(valid["r_multiple"].median()),
        "winner_rate_pct": float((valid["realized_pnl"] > 0).mean() * 100.0),
        "big_winner_rate_pct": float(valid["big_winner"].fillna(0).mean() * 100.0),
        "quality_winner_rate_pct": float(valid["quality_winner"].fillna(0).mean() * 100.0),
        "bad_rate_pct": float((valid["r_multiple"] <= -1.0).mean() * 100.0),
        "sum_r": float(valid["r_multiple"].sum()),
    }


def _feature_year_detail(data: pd.DataFrame, feature: str) -> pd.DataFrame:
    selected = data[data[feature].fillna(False)].copy()
    if selected.empty:
        return pd.DataFrame()
    return (
        selected.groupby("entry_year")
        .agg(
            rows=("lot_id", "count"),
            products=("product", "nunique"),
            directions=("direction", "nunique"),
            avg_r=("r_multiple", "mean"),
            sum_r=("r_multiple", "sum"),
            winners=("winner", "sum"),
            big_winners=("big_winner", "sum"),
            pnl=("realized_pnl", "sum"),
        )
        .reset_index()
        .assign(feature=feature)
    )


def _build_feature_metrics(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    valid = data.dropna(subset=["r_multiple", "pre20_avg_total_wick_pct"]).copy()
    baseline = _baseline_metrics(valid)
    metric_rows: list[dict[str, Any]] = []
    year_frames: list[pd.DataFrame] = []
    for feature in SEGMENT_FEATURE_BUCKETS:
        selected = valid[valid[feature].fillna(False)].copy()
        if selected.empty:
            continue
        unselected = valid[~valid[feature].fillna(False)].copy()
        product_share = selected["product"].value_counts(normalize=True).iloc[0]
        years = int(selected["entry_year"].nunique())
        products = int(selected["product"].nunique())
        directions = int(selected["direction"].nunique())
        year_detail = _feature_year_detail(valid, feature)
        if not year_detail.empty:
            year_frames.append(year_detail)
        positive_r_years = int((year_detail["sum_r"] > 0).sum()) if not year_detail.empty else 0
        avg_r = float(selected["r_multiple"].mean())
        median_r = float(selected["r_multiple"].median())
        big_rate = float(selected["big_winner"].fillna(0).mean() * 100.0)
        bad_rate = float((selected["r_multiple"] <= -1.0).mean() * 100.0)
        metric_rows.append(
            {
                "feature": feature,
                "rows": int(len(selected)),
                "coverage_pct": len(selected) / len(valid) * 100.0,
                "years": years,
                "products": products,
                "directions": directions,
                "dominant_product_share_pct": product_share * 100.0,
                "winner_rate_pct": float((selected["realized_pnl"] > 0).mean() * 100.0),
                "big_winner_rate_pct": big_rate,
                "quality_winner_rate_pct": float(selected["quality_winner"].fillna(0).mean() * 100.0),
                "bad_rate_pct": bad_rate,
                "avg_r": avg_r,
                "median_r": median_r,
                "sum_r": float(selected["r_multiple"].sum()),
                "avg_r_lift": avg_r - baseline["avg_r"],
                "median_r_lift": median_r - baseline["median_r"],
                "big_winner_rate_lift_pp": big_rate - baseline["big_winner_rate_pct"],
                "bad_rate_lift_pp": bad_rate - baseline["bad_rate_pct"],
                "unselected_rows": int(len(unselected)),
                "unselected_avg_r": float(unselected["r_multiple"].mean()) if not unselected.empty else np.nan,
                "unselected_big_winner_rate_pct": (
                    float(unselected["big_winner"].fillna(0).mean() * 100.0) if not unselected.empty else np.nan
                ),
                "positive_r_years": positive_r_years,
                "passes_reliable_gate": bool(
                    len(selected) >= MIN_RELIABLE_ROWS
                    and years >= MIN_RELIABLE_YEARS
                    and products >= MIN_RELIABLE_PRODUCTS
                    and product_share <= MAX_DOMINANT_PRODUCT_SHARE
                    and directions >= 2
                    and (avg_r - baseline["avg_r"]) >= MIN_AVG_R_LIFT
                    and (big_rate - baseline["big_winner_rate_pct"]) >= MIN_BIG_WINNER_RATE_LIFT_PP
                    and positive_r_years >= MIN_POSITIVE_R_YEARS
                    and bad_rate <= MAX_BAD_RATE_PCT
                ),
            }
        )
    metrics = pd.DataFrame(metric_rows).sort_values(
        ["passes_reliable_gate", "avg_r_lift", "big_winner_rate_lift_pp"], ascending=[False, False, False]
    )
    year_detail = pd.concat(year_frames, ignore_index=True) if year_frames else pd.DataFrame()
    return metrics, year_detail, baseline


def _plot_feature_metrics(metrics: pd.DataFrame, baseline: dict[str, float]) -> None:
    if metrics.empty:
        return
    top = metrics.sort_values("avg_r_lift", ascending=False).head(12).copy()
    plt.figure(figsize=(13, 7))
    colors = ["#2ca02c" if value else "#1f77b4" for value in top["passes_reliable_gate"]]
    plt.barh(top["feature"], top["avg_r_lift"], color=colors)
    plt.axvline(0.0, color="#666666", linewidth=1)
    plt.axvline(MIN_AVG_R_LIFT, color="#cc3333", linewidth=1, linestyle="--", label="avg R lift gate")
    plt.title("Stage734 pre-entry segment short-wick feature avg R lift")
    plt.xlabel(f"Avg R lift vs baseline avg R {baseline['avg_r']:.3f}")
    plt.gca().invert_yaxis()
    plt.grid(axis="x", alpha=0.25)
    plt.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(CHART_PATH, dpi=160)
    plt.close()


def _build_report(enriched: pd.DataFrame, metrics: pd.DataFrame, year_detail: pd.DataFrame, baseline: dict[str, float]) -> str:
    pass_df = metrics[metrics["passes_reliable_gate"]].copy()
    top_cols = [
        "feature",
        "rows",
        "coverage_pct",
        "years",
        "products",
        "directions",
        "dominant_product_share_pct",
        "avg_r",
        "avg_r_lift",
        "median_r",
        "big_winner_rate_pct",
        "big_winner_rate_lift_pp",
        "bad_rate_pct",
        "positive_r_years",
        "passes_reliable_gate",
    ]
    sample_cols = [
        "lot_id",
        "vt_symbol",
        "direction",
        "entry_date",
        "r_multiple",
        "mfe_r",
        "realized_pnl",
        "pre20_avg_total_wick_pct",
        "pre20_short30_ratio",
        "pre20_long60_ratio",
        "pre20_avg_body_pct",
        "pre20_clean_segment_combo",
        "pre40_avg_total_wick_pct",
        "pre40_short30_ratio",
        "pre40_long60_ratio",
        "pre40_clean_segment_combo",
    ]
    top_winners = enriched.sort_values("r_multiple", ascending=False).head(30)
    lines = [
        "# Stage734 入场前一段时间短影线质量特征审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CST",
        f"- 研究线：`{LINE_ID}`",
        f"- 数据源：`{s733.SOURCE_CLOSED_LOTS_PATH.name}`",
        "- 口径：只读正式版 Stage719 closed lots；对每笔实际入场只使用 `entry_date` 之前 `10/20/40` 个已完成合约日线。",
        "- 特征：一段时间内短影线比例、长影线比例、平均总影线、平均不利影线和方向性收盘强度；不做小数阈值扫描。",
        "",
        "## Baseline",
        "",
        s733._md_table(pd.DataFrame([baseline])),
        "",
        "## 通过特征",
        "",
        s733._md_table(pass_df[top_cols] if not pass_df.empty else pass_df),
        "",
        "## Top 特征指标",
        "",
        s733._md_table(metrics[top_cols], max_rows=24),
        "",
        "## Top R 赢家的一段时间影线状态",
        "",
        s733._md_table(top_winners[sample_cols], max_rows=30),
        "",
        "## 年度明细 Top",
        "",
        s733._md_table(year_detail.sort_values(["feature", "entry_year"]).head(100) if not year_detail.empty else year_detail),
        "",
        "## 结论",
        "",
    ]
    if pass_df.empty:
        lines.extend(
            [
                "- 没有入场前 `10/20/40` 日短影线段特征通过完整可靠性闸门。",
                "- 当前不能把“一段时间影线很短”接成所有交易风险放大规则。",
            ]
        )
    else:
        lines.extend(
            [
                f"- 有 {len(pass_df)} 个特征通过完整可靠性闸门，可以进入下一步 A/C 风险放大压力测试。",
                "- 下一步必须检验全周期、多起点、弱窗口和成本压力，不能直接合入正式版。",
            ]
        )
    lines.extend(
        [
            "",
            "## 过拟合反思",
            "",
            "- 本阶段修正了 Stage016 对用户意图的窗口定义，但仍只读审计、不改仓位。",
            "- 若继续围绕 `10/20/40` 的具体阈值、小数、品种、年份或方向补条件，会转为历史赢家图形过拟合。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lots = s733._load_closed_lots()
    enriched = _enrich_lots(lots)
    metrics, year_detail, baseline = _build_feature_metrics(enriched)
    _plot_feature_metrics(metrics, baseline)

    enriched.to_csv(ENRICHED_PATH, index=False, encoding="utf-8-sig")
    metrics.to_csv(FEATURE_METRICS_PATH, index=False, encoding="utf-8-sig")
    year_detail.to_csv(YEAR_DETAIL_PATH, index=False, encoding="utf-8-sig")
    REPORT_PATH.write_text(_build_report(enriched, metrics, year_detail, baseline), encoding="utf-8")

    pass_df = metrics[metrics["passes_reliable_gate"]].copy()
    top_big = enriched[enriched["big_winner"] == 1].copy()
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "closed_lots": int(len(lots)),
        "feature_valid_lots": int(enriched["pre20_avg_total_wick_pct"].notna().sum()),
        "baseline": baseline,
        "passed_feature_count": int(len(pass_df)),
        "passed_features": pass_df["feature"].tolist(),
        "big_winner_pre20_clean_segment_combo_count": int(top_big["pre20_clean_segment_combo"].fillna(False).sum()),
        "big_winner_pre40_clean_segment_combo_count": int(top_big["pre40_clean_segment_combo"].fillna(False).sum()),
        "big_winner_count": int(len(top_big)),
        "decision": (
            "shadowless_segment_feature_can_enter_ac_backtest"
            if not pass_df.empty
            else "no_reliable_shadowless_segment_risk_expansion_feature_found"
        ),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(s733._json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(s733._json_safe(decision), ensure_ascii=False, indent=2))
    print(metrics.head(24).to_string(index=False))


if __name__ == "__main__":
    main()
