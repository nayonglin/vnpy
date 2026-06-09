from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage733_shadowless_preentry_quality as s733


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage735_postentry_smooth_kline_hold_quality_v1"
OUTPUT_PREFIX = "qmt_roll_stage735_postentry_smooth_kline_hold_quality"
LINE_ID = "futures_trend_winner_trade_forensics"

ENRICHED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_enriched_closed_lots_{MODEL_TAG}.csv"
FEATURE_METRICS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_metrics_{MODEL_TAG}.csv"
YEAR_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_detail_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

WINDOWS = [1, 2, 3, 5]
MIN_RELIABLE_ROWS = 30
MIN_RELIABLE_YEARS = 5
MIN_RELIABLE_PRODUCTS = 8
MAX_DOMINANT_PRODUCT_SHARE = 0.30
MIN_RESIDUAL_R_LIFT = 0.25
MIN_FINAL_BIG_WINNER_RATE_LIFT_PP = 5.0
MIN_RESIDUAL_POSITIVE_RATE_LIFT_PP = 5.0
MIN_POSITIVE_RESIDUAL_YEARS = 5
MAX_RESIDUAL_BAD_RATE_PCT = 55.0

POST_FEATURE_BUCKETS = [
    "post1_avg_directional_close_strength_ge60",
    "post2_avg_directional_close_strength_ge60",
    "post3_avg_directional_close_strength_ge60",
    "post5_avg_directional_close_strength_ge60",
    "post1_directional_bar_ratio_ge60",
    "post2_directional_bar_ratio_ge60",
    "post3_directional_bar_ratio_ge60",
    "post5_directional_bar_ratio_ge60",
    "post1_body60_ratio_ge50",
    "post2_body60_ratio_ge50",
    "post3_body60_ratio_ge50",
    "post5_body60_ratio_ge50",
    "post1_short30_ratio_ge50",
    "post2_short30_ratio_ge50",
    "post3_short30_ratio_ge50",
    "post5_short30_ratio_ge50",
    "post1_long60_ratio_le20",
    "post2_long60_ratio_le20",
    "post3_long60_ratio_le20",
    "post5_long60_ratio_le20",
    "post1_avg_adverse_wick_le25",
    "post2_avg_adverse_wick_le25",
    "post3_avg_adverse_wick_le25",
    "post5_avg_adverse_wick_le25",
    "post1_smooth_directional_combo",
    "post2_smooth_directional_combo",
    "post3_smooth_directional_combo",
    "post5_smooth_directional_combo",
    "post1_clean_shadow_combo",
    "post2_clean_shadow_combo",
    "post3_clean_shadow_combo",
    "post5_clean_shadow_combo",
]


def _post_window_stats(bars: pd.DataFrame, row: pd.Series, window: int) -> dict[str, Any]:
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    exit_date = pd.Timestamp(row["exit_date"]).normalize()
    direction = str(row["direction"])
    held_bars = bars[(bars["date"] >= entry_date) & (bars["date"] < exit_date)].head(window).copy()
    if len(held_bars) < window:
        return {}

    featured = s733._add_candle_features(held_bars, direction)
    nth = featured.iloc[-1]
    entry_price = float(row["entry_price"])
    nth_close = float(nth["close_price"])
    volume = float(row["volume"])
    size = float(row["size"])
    risk_amount = float(row["risk_amount"])
    final_r = float(row["r_multiple"])
    if direction == "long":
        early_cash = (nth_close - entry_price) * volume * size
    elif direction == "short":
        early_cash = (entry_price - nth_close) * volume * size
    else:
        early_cash = np.nan
    early_r = early_cash / risk_amount if risk_amount else np.nan
    residual_r = final_r - early_r if not np.isnan(early_r) else np.nan

    total = featured["total_wick_pct_of_range"]
    body = featured["body_pct_of_range"]
    adverse = featured["adverse_wick_pct_of_range"]
    directional_strength = featured["directional_close_strength"]
    return {
        f"post{window}_available_bars": int(len(featured)),
        f"post{window}_observation_date": nth["date"].strftime("%Y-%m-%d"),
        f"post{window}_close": nth_close,
        f"post{window}_early_r_proxy": float(early_r),
        f"post{window}_residual_r_proxy": float(residual_r),
        f"post{window}_avg_total_wick_pct": float(total.mean()),
        f"post{window}_median_total_wick_pct": float(total.median()),
        f"post{window}_avg_body_pct": float(body.mean()),
        f"post{window}_avg_adverse_wick_pct": float(adverse.mean()),
        f"post{window}_avg_favorable_wick_pct": float(featured["favorable_wick_pct_of_range"].mean()),
        f"post{window}_avg_directional_close_strength": float(directional_strength.mean()),
        f"post{window}_short30_ratio": float((total <= 0.30).mean()),
        f"post{window}_long60_ratio": float((total >= 0.60).mean()),
        f"post{window}_body60_ratio": float((body >= 0.60).mean()),
        f"post{window}_directional_bar_ratio": float(featured["directional_bar"].mean()),
        f"post{window}_marubozu_directional_ratio": float(featured["marubozu_directional_bar"].mean()),
    }


def _enrich_lots(lots: pd.DataFrame) -> pd.DataFrame:
    bar_cache: dict[str, pd.DataFrame] = {}
    records: list[dict[str, Any]] = []
    for _, row in lots.iterrows():
        record = row.to_dict()
        vt_symbol = str(row["vt_symbol"])
        bars = bar_cache.get(vt_symbol)
        if bars is None:
            bars = s733._load_contract_bars(vt_symbol)
            bar_cache[vt_symbol] = bars
        if not bars.empty:
            for window in WINDOWS:
                record.update(_post_window_stats(bars, row, window))
        records.append(record)
    enriched = pd.DataFrame(records)
    enriched["entry_year"] = pd.to_datetime(enriched["entry_date"]).dt.year

    for window in WINDOWS:
        prefix = f"post{window}"
        enriched[f"{prefix}_avg_directional_close_strength_ge60"] = (
            enriched[f"{prefix}_avg_directional_close_strength"] >= 0.60
        )
        enriched[f"{prefix}_directional_bar_ratio_ge60"] = enriched[f"{prefix}_directional_bar_ratio"] >= 0.60
        enriched[f"{prefix}_body60_ratio_ge50"] = enriched[f"{prefix}_body60_ratio"] >= 0.50
        enriched[f"{prefix}_short30_ratio_ge50"] = enriched[f"{prefix}_short30_ratio"] >= 0.50
        enriched[f"{prefix}_long60_ratio_le20"] = enriched[f"{prefix}_long60_ratio"] <= 0.20
        enriched[f"{prefix}_avg_adverse_wick_le25"] = enriched[f"{prefix}_avg_adverse_wick_pct"] <= 0.25
        enriched[f"{prefix}_smooth_directional_combo"] = (
            (enriched[f"{prefix}_avg_directional_close_strength"] >= 0.60)
            & (enriched[f"{prefix}_body60_ratio"] >= 0.40)
            & (enriched[f"{prefix}_long60_ratio"] <= 0.40)
        )
        enriched[f"{prefix}_clean_shadow_combo"] = (
            (enriched[f"{prefix}_short30_ratio"] >= 0.40)
            & (enriched[f"{prefix}_avg_directional_close_strength"] >= 0.60)
        )
    return enriched


def _feature_window(feature: str) -> int:
    match = re.match(r"post(\d+)_", feature)
    if not match:
        raise ValueError(f"cannot infer post window from feature {feature}")
    return int(match.group(1))


def _baseline_metrics(data: pd.DataFrame, window: int) -> dict[str, float]:
    residual_col = f"post{window}_residual_r_proxy"
    valid = data.dropna(subset=["r_multiple", residual_col]).copy()
    return {
        "rows": float(len(valid)),
        "final_avg_r": float(valid["r_multiple"].mean()),
        "final_big_winner_rate_pct": float(valid["big_winner"].fillna(0).mean() * 100.0),
        "residual_avg_r": float(valid[residual_col].mean()),
        "residual_median_r": float(valid[residual_col].median()),
        "residual_positive_rate_pct": float((valid[residual_col] > 0.0).mean() * 100.0),
        "residual_ge1r_rate_pct": float((valid[residual_col] >= 1.0).mean() * 100.0),
        "residual_bad_rate_pct": float((valid[residual_col] <= -1.0).mean() * 100.0),
    }


def _feature_year_detail(data: pd.DataFrame, feature: str, window: int) -> pd.DataFrame:
    residual_col = f"post{window}_residual_r_proxy"
    selected = data[data[feature].fillna(False)].dropna(subset=[residual_col]).copy()
    if selected.empty:
        return pd.DataFrame()
    return (
        selected.groupby("entry_year")
        .agg(
            rows=("lot_id", "count"),
            products=("product", "nunique"),
            directions=("direction", "nunique"),
            final_avg_r=("r_multiple", "mean"),
            residual_avg_r=(residual_col, "mean"),
            residual_sum_r=(residual_col, "sum"),
            residual_positive_count=(residual_col, lambda s: int((s > 0.0).sum())),
            final_big_winners=("big_winner", "sum"),
            pnl=("realized_pnl", "sum"),
        )
        .reset_index()
        .assign(feature=feature)
    )


def _build_feature_metrics(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict[str, float]]]:
    baselines = {f"post{window}": _baseline_metrics(data, window) for window in WINDOWS}
    metric_rows: list[dict[str, Any]] = []
    year_frames: list[pd.DataFrame] = []
    for feature in POST_FEATURE_BUCKETS:
        window = _feature_window(feature)
        residual_col = f"post{window}_residual_r_proxy"
        valid = data.dropna(subset=["r_multiple", residual_col]).copy()
        if valid.empty:
            continue
        selected = valid[valid[feature].fillna(False)].copy()
        if selected.empty:
            continue
        unselected = valid[~valid[feature].fillna(False)].copy()
        baseline = baselines[f"post{window}"]
        product_share = selected["product"].value_counts(normalize=True).iloc[0]
        years = int(selected["entry_year"].nunique())
        products = int(selected["product"].nunique())
        directions = int(selected["direction"].nunique())
        year_detail = _feature_year_detail(valid, feature, window)
        if not year_detail.empty:
            year_frames.append(year_detail)
        positive_residual_years = int((year_detail["residual_sum_r"] > 0).sum()) if not year_detail.empty else 0
        residual_avg = float(selected[residual_col].mean())
        residual_positive_rate = float((selected[residual_col] > 0.0).mean() * 100.0)
        residual_ge1r_rate = float((selected[residual_col] >= 1.0).mean() * 100.0)
        residual_bad_rate = float((selected[residual_col] <= -1.0).mean() * 100.0)
        final_big_rate = float(selected["big_winner"].fillna(0).mean() * 100.0)
        metric_rows.append(
            {
                "feature": feature,
                "window": window,
                "baseline_rows": int(baseline["rows"]),
                "rows": int(len(selected)),
                "coverage_pct": len(selected) / len(valid) * 100.0,
                "years": years,
                "products": products,
                "directions": directions,
                "dominant_product_share_pct": product_share * 100.0,
                "final_avg_r": float(selected["r_multiple"].mean()),
                "final_big_winner_rate_pct": final_big_rate,
                "final_big_winner_rate_lift_pp": final_big_rate - baseline["final_big_winner_rate_pct"],
                "residual_avg_r": residual_avg,
                "residual_avg_r_lift": residual_avg - baseline["residual_avg_r"],
                "residual_median_r": float(selected[residual_col].median()),
                "residual_positive_rate_pct": residual_positive_rate,
                "residual_positive_rate_lift_pp": residual_positive_rate - baseline["residual_positive_rate_pct"],
                "residual_ge1r_rate_pct": residual_ge1r_rate,
                "residual_ge1r_rate_lift_pp": residual_ge1r_rate - baseline["residual_ge1r_rate_pct"],
                "residual_bad_rate_pct": residual_bad_rate,
                "residual_bad_rate_lift_pp": residual_bad_rate - baseline["residual_bad_rate_pct"],
                "positive_residual_years": positive_residual_years,
                "unselected_rows": int(len(unselected)),
                "unselected_residual_avg_r": float(unselected[residual_col].mean()) if not unselected.empty else np.nan,
                "passes_reliable_gate": bool(
                    len(selected) >= MIN_RELIABLE_ROWS
                    and years >= MIN_RELIABLE_YEARS
                    and products >= MIN_RELIABLE_PRODUCTS
                    and product_share <= MAX_DOMINANT_PRODUCT_SHARE
                    and directions >= 2
                    and (residual_avg - baseline["residual_avg_r"]) >= MIN_RESIDUAL_R_LIFT
                    and (final_big_rate - baseline["final_big_winner_rate_pct"]) >= MIN_FINAL_BIG_WINNER_RATE_LIFT_PP
                    and (residual_positive_rate - baseline["residual_positive_rate_pct"])
                    >= MIN_RESIDUAL_POSITIVE_RATE_LIFT_PP
                    and positive_residual_years >= MIN_POSITIVE_RESIDUAL_YEARS
                    and residual_bad_rate <= MAX_RESIDUAL_BAD_RATE_PCT
                ),
            }
        )
    metrics = pd.DataFrame(metric_rows).sort_values(
        ["passes_reliable_gate", "residual_avg_r_lift", "final_big_winner_rate_lift_pp"],
        ascending=[False, False, False],
    )
    year_detail = pd.concat(year_frames, ignore_index=True) if year_frames else pd.DataFrame()
    return metrics, year_detail, baselines


def _plot_feature_metrics(metrics: pd.DataFrame) -> None:
    if metrics.empty:
        return
    top = metrics.sort_values("residual_avg_r_lift", ascending=False).head(14).copy()
    plt.figure(figsize=(13, 7))
    colors = ["#2ca02c" if value else "#1f77b4" for value in top["passes_reliable_gate"]]
    plt.barh(top["feature"], top["residual_avg_r_lift"], color=colors)
    plt.axvline(0.0, color="#666666", linewidth=1)
    plt.axvline(MIN_RESIDUAL_R_LIFT, color="#cc3333", linewidth=1, linestyle="--", label="residual R lift gate")
    plt.title("Stage735 post-entry smooth K-line residual R lift")
    plt.xlabel("Residual R lift after observation window")
    plt.gca().invert_yaxis()
    plt.grid(axis="x", alpha=0.25)
    plt.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(CHART_PATH, dpi=160)
    plt.close()


def _build_report(
    enriched: pd.DataFrame,
    metrics: pd.DataFrame,
    year_detail: pd.DataFrame,
    baselines: dict[str, dict[str, float]],
) -> str:
    pass_df = metrics[metrics["passes_reliable_gate"]].copy()
    top_cols = [
        "feature",
        "window",
        "baseline_rows",
        "rows",
        "coverage_pct",
        "years",
        "products",
        "directions",
        "final_avg_r",
        "final_big_winner_rate_pct",
        "final_big_winner_rate_lift_pp",
        "residual_avg_r",
        "residual_avg_r_lift",
        "residual_positive_rate_pct",
        "residual_positive_rate_lift_pp",
        "residual_ge1r_rate_pct",
        "residual_bad_rate_pct",
        "positive_residual_years",
        "passes_reliable_gate",
    ]
    sample_cols = [
        "lot_id",
        "vt_symbol",
        "direction",
        "entry_date",
        "exit_date",
        "r_multiple",
        "post1_early_r_proxy",
        "post1_residual_r_proxy",
        "post1_avg_directional_close_strength",
        "post1_avg_body_pct",
        "post1_avg_adverse_wick_pct",
        "post3_early_r_proxy",
        "post3_residual_r_proxy",
        "post3_avg_directional_close_strength",
        "post3_avg_body_pct",
        "post3_smooth_directional_combo",
    ]
    top_winners = enriched.sort_values("r_multiple", ascending=False).head(30)
    baseline_table = pd.DataFrame(
        [{"window": key, **value} for key, value in baselines.items()]
    )
    lines = [
        "# Stage735 入场后早期顺畅 K 线持仓质量审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CST",
        f"- 研究线：`{LINE_ID}`",
        f"- 数据源：`{s733.SOURCE_CLOSED_LOTS_PATH.name}`",
        "- 口径：只读正式版 Stage719 closed lots；对每笔实际成交只观察入场后 `1/2/3/5` 个已完成且早于退出日的合约日线。",
        "- 关键约束：这是入场后信息，只能用于持仓管理/确认加仓/锁盈减仓研究，不能用于初始风险放大。",
        "- 核心标签：除最终 R 外，同时计算观察窗口结束后的 `residual_r_proxy = final_r - early_move_r_proxy`。",
        "",
        "## Baseline By Observation Window",
        "",
        s733._md_table(baseline_table),
        "",
        "## 通过特征",
        "",
        s733._md_table(pass_df[top_cols] if not pass_df.empty else pass_df),
        "",
        "## Top 特征指标",
        "",
        s733._md_table(metrics[top_cols], max_rows=28),
        "",
        "## Top R 赢家早期 K 线状态",
        "",
        s733._md_table(top_winners[sample_cols], max_rows=30),
        "",
        "## 年度明细 Top",
        "",
        s733._md_table(year_detail.sort_values(["feature", "entry_year"]).head(120) if not year_detail.empty else year_detail),
        "",
        "## 结论",
        "",
    ]
    if pass_df.empty:
        lines.extend(
            [
                "- 没有入场后早期顺畅 K 线特征通过完整可靠性闸门。",
                "- 当前不能把这些特征直接接成确认加仓或放宽锁盈规则。",
            ]
        )
    else:
        lines.extend(
            [
                f"- 有 {len(pass_df)} 个特征通过完整可靠性闸门，可以进入下一步 A/C 持仓管理压力测试。",
                "- 下一步仍需多起点、弱窗口、成本和强制减仓压力验证。",
            ]
        )
    lines.extend(
        [
            "",
            "## 过拟合反思",
            "",
            "- 本阶段只读审计，没有改变正式策略。",
            "- 如果继续围绕某个窗口/阈值微调以通过闸门，会把入场后走势图形过拟合成持仓规则。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lots = s733._load_closed_lots()
    enriched = _enrich_lots(lots)
    metrics, year_detail, baselines = _build_feature_metrics(enriched)
    _plot_feature_metrics(metrics)

    enriched.to_csv(ENRICHED_PATH, index=False, encoding="utf-8-sig")
    metrics.to_csv(FEATURE_METRICS_PATH, index=False, encoding="utf-8-sig")
    year_detail.to_csv(YEAR_DETAIL_PATH, index=False, encoding="utf-8-sig")
    REPORT_PATH.write_text(_build_report(enriched, metrics, year_detail, baselines), encoding="utf-8")

    pass_df = metrics[metrics["passes_reliable_gate"]].copy()
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "closed_lots": int(len(lots)),
        "baselines": baselines,
        "passed_feature_count": int(len(pass_df)),
        "passed_features": pass_df["feature"].tolist(),
        "decision": (
            "postentry_smooth_kline_feature_can_enter_hold_management_ac"
            if not pass_df.empty
            else "no_reliable_postentry_smooth_kline_hold_feature_found"
        ),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(s733._json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(s733._json_safe(decision), ensure_ascii=False, indent=2))
    print(metrics.head(28).to_string(index=False))


if __name__ == "__main__":
    main()
