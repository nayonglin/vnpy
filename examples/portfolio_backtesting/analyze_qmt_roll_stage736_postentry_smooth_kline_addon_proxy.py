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
import analyze_qmt_roll_stage735_postentry_smooth_kline_hold_quality as s735


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage736_postentry_smooth_kline_addon_proxy_v1"
OUTPUT_PREFIX = "qmt_roll_stage736_postentry_smooth_kline_addon_proxy"
LINE_ID = "futures_trend_winner_trade_forensics"

SOURCE_ENRICHED_PATH = s735.ENRICHED_PATH
SOURCE_METRICS_PATH = s735.FEATURE_METRICS_PATH

ADDON_METRICS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_addon_metrics_{MODEL_TAG}.csv"
ADDON_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_addon_lots_{MODEL_TAG}.csv"
YEAR_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_detail_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

ADDON_RISK_FRACTION = 0.50
MIN_ROWS = 30
MIN_YEARS = 5
MIN_PRODUCTS = 8
MAX_DOMINANT_PRODUCT_SHARE = 0.30
MIN_POSITIVE_YEARS = 5
MIN_AVG_PROXY_ADDON_R = 0.50


def _feature_window(feature: str) -> int:
    match = re.match(r"post(\d+)_", feature)
    if not match:
        raise ValueError(f"cannot infer post window from feature {feature}")
    return int(match.group(1))


def _load_sources() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not SOURCE_ENRICHED_PATH.exists() or not SOURCE_METRICS_PATH.exists():
        s735.main()
    enriched = pd.read_csv(SOURCE_ENRICHED_PATH, encoding="utf-8-sig")
    metrics = pd.read_csv(SOURCE_METRICS_PATH, encoding="utf-8-sig")
    for column in ["entry_date", "exit_date"]:
        enriched[column] = pd.to_datetime(enriched[column], errors="coerce").dt.normalize()
    for column in [
        "risk_amount",
        "r_multiple",
        "realized_pnl",
        "big_winner",
        "quality_winner",
        "volume",
        "size",
    ]:
        if column in enriched.columns:
            enriched[column] = pd.to_numeric(enriched[column], errors="coerce")
    return enriched, metrics


def _build_proxy(enriched: pd.DataFrame, metrics: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    passed_features = metrics.loc[metrics["passes_reliable_gate"].fillna(False).astype(bool), "feature"].tolist()
    lot_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    year_rows: list[pd.DataFrame] = []
    for feature in passed_features:
        window = _feature_window(feature)
        residual_col = f"post{window}_residual_r_proxy"
        observation_date_col = f"post{window}_observation_date"
        selected = enriched[enriched[feature].fillna(False)].dropna(subset=[residual_col, "risk_amount"]).copy()
        if selected.empty:
            continue
        selected["addon_feature"] = feature
        selected["addon_window"] = window
        selected["addon_risk_fraction"] = ADDON_RISK_FRACTION
        selected["addon_residual_r_proxy"] = selected[residual_col].astype("float64")
        selected["addon_pnl_proxy"] = (
            selected["addon_residual_r_proxy"] * selected["risk_amount"].astype("float64") * ADDON_RISK_FRACTION
        )
        selected["addon_observation_date"] = selected[observation_date_col]
        lot_rows.extend(selected.to_dict(orient="records"))

        year_detail = (
            selected.groupby("entry_year")
            .agg(
                rows=("lot_id", "count"),
                products=("product", "nunique"),
                directions=("direction", "nunique"),
                addon_pnl_proxy=("addon_pnl_proxy", "sum"),
                avg_addon_residual_r=("addon_residual_r_proxy", "mean"),
                positive_addon_count=("addon_residual_r_proxy", lambda s: int((s > 0.0).sum())),
                final_big_winners=("big_winner", "sum"),
            )
            .reset_index()
            .assign(feature=feature)
        )
        year_rows.append(year_detail)

        product_share = selected["product"].value_counts(normalize=True).iloc[0]
        positive_years = int((year_detail["addon_pnl_proxy"] > 0).sum())
        metric_rows.append(
            {
                "feature": feature,
                "window": window,
                "rows": int(len(selected)),
                "years": int(selected["entry_year"].nunique()),
                "products": int(selected["product"].nunique()),
                "directions": int(selected["direction"].nunique()),
                "dominant_product_share_pct": product_share * 100.0,
                "total_addon_pnl_proxy": float(selected["addon_pnl_proxy"].sum()),
                "avg_addon_pnl_proxy": float(selected["addon_pnl_proxy"].mean()),
                "avg_addon_residual_r": float(selected["addon_residual_r_proxy"].mean()),
                "median_addon_residual_r": float(selected["addon_residual_r_proxy"].median()),
                "addon_positive_rate_pct": float((selected["addon_residual_r_proxy"] > 0.0).mean() * 100.0),
                "addon_ge1r_rate_pct": float((selected["addon_residual_r_proxy"] >= 1.0).mean() * 100.0),
                "addon_bad_rate_pct": float((selected["addon_residual_r_proxy"] <= -1.0).mean() * 100.0),
                "positive_years": positive_years,
                "worst_year_pnl_proxy": float(year_detail["addon_pnl_proxy"].min()),
                "best_year_pnl_proxy": float(year_detail["addon_pnl_proxy"].max()),
                "final_big_winner_rate_pct": float(selected["big_winner"].fillna(0).mean() * 100.0),
                "passes_proxy_gate": bool(
                    len(selected) >= MIN_ROWS
                    and selected["entry_year"].nunique() >= MIN_YEARS
                    and selected["product"].nunique() >= MIN_PRODUCTS
                    and product_share <= MAX_DOMINANT_PRODUCT_SHARE
                    and selected["direction"].nunique() >= 2
                    and positive_years >= MIN_POSITIVE_YEARS
                    and selected["addon_residual_r_proxy"].mean() >= MIN_AVG_PROXY_ADDON_R
                    and selected["addon_pnl_proxy"].sum() > 0.0
                ),
            }
        )
    addon_lots = pd.DataFrame(lot_rows)
    addon_metrics = pd.DataFrame(metric_rows).sort_values(
        ["passes_proxy_gate", "total_addon_pnl_proxy", "avg_addon_residual_r"],
        ascending=[False, False, False],
    )
    year_detail_all = pd.concat(year_rows, ignore_index=True) if year_rows else pd.DataFrame()
    return addon_lots, addon_metrics, year_detail_all


def _plot_metrics(metrics: pd.DataFrame) -> None:
    if metrics.empty:
        return
    top = metrics.head(9).copy()
    plt.figure(figsize=(13, 6))
    colors = ["#2ca02c" if value else "#1f77b4" for value in top["passes_proxy_gate"]]
    plt.barh(top["feature"], top["total_addon_pnl_proxy"], color=colors)
    plt.axvline(0.0, color="#666666", linewidth=1)
    plt.title("Stage736 0.5x add-on proxy PnL by post-entry feature")
    plt.xlabel("Proxy incremental PnL")
    plt.gca().invert_yaxis()
    plt.grid(axis="x", alpha=0.25)
    plt.tight_layout()
    plt.savefig(CHART_PATH, dpi=160)
    plt.close()


def _build_report(addon_metrics: pd.DataFrame, addon_lots: pd.DataFrame, year_detail: pd.DataFrame) -> str:
    cols = [
        "feature",
        "window",
        "rows",
        "years",
        "products",
        "directions",
        "dominant_product_share_pct",
        "total_addon_pnl_proxy",
        "avg_addon_residual_r",
        "median_addon_residual_r",
        "addon_positive_rate_pct",
        "addon_ge1r_rate_pct",
        "addon_bad_rate_pct",
        "positive_years",
        "worst_year_pnl_proxy",
        "final_big_winner_rate_pct",
        "passes_proxy_gate",
    ]
    sample_cols = [
        "addon_feature",
        "lot_id",
        "vt_symbol",
        "direction",
        "entry_date",
        "addon_observation_date",
        "exit_date",
        "r_multiple",
        "addon_residual_r_proxy",
        "risk_amount",
        "addon_pnl_proxy",
        "realized_pnl",
        "big_winner",
    ]
    top_lots = addon_lots.sort_values("addon_pnl_proxy", ascending=False).head(40) if not addon_lots.empty else addon_lots
    pass_df = addon_metrics[addon_metrics["passes_proxy_gate"].fillna(False)] if not addon_metrics.empty else addon_metrics
    lines = [
        "# Stage736 入场后顺畅K线确认仓代理测算",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CST",
        f"- 研究线：`{LINE_ID}`",
        f"- 数据源：`{SOURCE_ENRICHED_PATH.name}` + `{SOURCE_METRICS_PATH.name}`",
        f"- 代理口径：只对 Stage735 已通过闸门的特征，模拟观察完成后增加 `0.5x` 原交易风险的小确认仓。",
        "- 增量 PnL 估算：`residual_r_proxy * original_risk_amount * 0.5`；不含真实保证金、整数手、排队、滑点和组合交互。",
        "",
        "## 通过代理闸门特征",
        "",
        s733._md_table(pass_df[cols] if not pass_df.empty else pass_df),
        "",
        "## 全部候选代理结果",
        "",
        s733._md_table(addon_metrics[cols], max_rows=20),
        "",
        "## 最大代理贡献交易",
        "",
        s733._md_table(top_lots[sample_cols], max_rows=40),
        "",
        "## 年度明细",
        "",
        s733._md_table(year_detail.sort_values(["feature", "entry_year"]).head(120) if not year_detail.empty else year_detail),
        "",
        "## 结论",
        "",
    ]
    if pass_df.empty:
        lines.extend(
            [
                "- 没有特征通过 0.5x 确认仓代理闸门，不进入真实 A/C。",
            ]
        )
    else:
        lines.extend(
            [
                f"- 有 {len(pass_df)} 个特征通过代理闸门，可以进入真实策略 A/C 之前的设计讨论。",
                "- 这仍不是正式回测；真实 A/C 必须处理整数手、保证金、maxpos、强制减仓和额外滑点。",
            ]
        )
    lines.extend(
        [
            "",
            "## 过拟合反思",
            "",
            "- 本阶段没有新增阈值，只使用 Stage735 已通过的特征和固定 0.5x 风险。",
            "- 若继续扫确认仓倍数、观察窗口或组合条件，会快速变成历史赢家路径拟合。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    enriched, metrics = _load_sources()
    addon_lots, addon_metrics, year_detail = _build_proxy(enriched, metrics)
    _plot_metrics(addon_metrics)

    addon_lots.to_csv(ADDON_LOTS_PATH, index=False, encoding="utf-8-sig")
    addon_metrics.to_csv(ADDON_METRICS_PATH, index=False, encoding="utf-8-sig")
    year_detail.to_csv(YEAR_DETAIL_PATH, index=False, encoding="utf-8-sig")
    REPORT_PATH.write_text(_build_report(addon_metrics, addon_lots, year_detail), encoding="utf-8")

    pass_df = addon_metrics[addon_metrics["passes_proxy_gate"].fillna(False)] if not addon_metrics.empty else addon_metrics
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "addon_risk_fraction": ADDON_RISK_FRACTION,
        "source_features": metrics.loc[metrics["passes_reliable_gate"].fillna(False).astype(bool), "feature"].tolist(),
        "passed_proxy_count": int(len(pass_df)),
        "passed_proxy_features": pass_df["feature"].tolist() if not pass_df.empty else [],
        "best_total_addon_pnl_proxy": (
            float(addon_metrics["total_addon_pnl_proxy"].max()) if not addon_metrics.empty else 0.0
        ),
        "decision": (
            "postentry_smooth_kline_addon_proxy_promising_needs_real_ac_design"
            if not pass_df.empty
            else "postentry_smooth_kline_addon_proxy_not_promoted"
        ),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(s733._json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(s733._json_safe(decision), ensure_ascii=False, indent=2))
    print(addon_metrics.to_string(index=False))


if __name__ == "__main__":
    main()
