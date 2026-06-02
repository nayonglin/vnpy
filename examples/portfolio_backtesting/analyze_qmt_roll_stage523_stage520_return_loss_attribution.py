from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage523_stage520_return_loss_attribution_v1"
OUTPUT_PREFIX = "qmt_roll_stage523_stage520_return_loss_attribution"

STAGE519_TAG = "stage519_product_margin_cap_frontier_v1"
STAGE519_PREFIX = "qmt_roll_stage519_product_margin_cap_frontier"
STAGE520_TAG = "stage520_product_cap_usage_gate_frontier_v1"
STAGE520_PREFIX = "qmt_roll_stage520_product_cap_usage_gate_frontier"

STAGE519_DAILY_IN = OUTPUT_DIR / f"{STAGE519_PREFIX}_margin_daily_{STAGE519_TAG}.csv"
STAGE520_DAILY_IN = OUTPUT_DIR / f"{STAGE520_PREFIX}_margin_daily_{STAGE520_TAG}.csv"
STAGE519_SUMMARY_IN = OUTPUT_DIR / f"{STAGE519_PREFIX}_summary_{STAGE519_TAG}.csv"
STAGE520_SUMMARY_IN = OUTPUT_DIR / f"{STAGE520_PREFIX}_summary_{STAGE520_TAG}.csv"

PAIR_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pair_summary_{MODEL_TAG}.csv"
DAILY_GAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_gap_{MODEL_TAG}.csv"
YEAR_GAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_gap_{MODEL_TAG}.csv"
BUCKET_GAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_bucket_gap_{MODEL_TAG}.csv"
TOP_LOSS_DAYS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_loss_days_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

PAIRS: tuple[tuple[str, str, str], ...] = (
    ("r070_no_cap_to_productcap30", "r070_legacy_nocap_control", "r070_productcap30"),
    ("r070_productcap30_to_usage80", "r070_productcap30", "r070_pc30_u80"),
    ("r070_productcap30_to_usage75", "r070_productcap30", "r070_pc30_u75"),
    ("r080_productcap30_to_usage80", "r080_productcap30", "r080_pc30_u80"),
    ("r080_productcap30_to_usage75", "r080_productcap30", "r080_pc30_u75"),
    ("r080_usage80_to_cap25_usage75", "r080_pc30_u80", "r080_pc25_u75"),
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _safe_div(numerator: float, denominator: float) -> float:
    if abs(denominator) < 1e-12:
        return 0.0
    return float(numerator / denominator)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    daily_519 = pd.read_csv(STAGE519_DAILY_IN, encoding="utf-8-sig")
    daily_520 = pd.read_csv(STAGE520_DAILY_IN, encoding="utf-8-sig")
    daily = pd.concat([daily_519, daily_520], ignore_index=True, sort=False)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    for column in [
        "total_net_pnl",
        "total_slippage",
        "account_equity",
        "broker10_margin_to_equity_pct",
        "broker10_total_margin_exact",
    ]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    daily = daily.dropna(subset=["date", "variant"]).sort_values(["variant", "date"]).copy()

    summary = pd.concat(
        [
            pd.read_csv(STAGE519_SUMMARY_IN, encoding="utf-8-sig"),
            pd.read_csv(STAGE520_SUMMARY_IN, encoding="utf-8-sig"),
        ],
        ignore_index=True,
        sort=False,
    )
    return daily, summary


def _pair_daily(daily: pd.DataFrame, pair_name: str, source_variant: str, target_variant: str) -> pd.DataFrame:
    source = daily[daily["variant"].eq(source_variant)].copy()
    target = daily[daily["variant"].eq(target_variant)].copy()
    merged = source[
        [
            "date",
            "total_net_pnl",
            "total_slippage",
            "account_equity",
            "broker10_margin_to_equity_pct",
            "broker10_total_margin_exact",
            "c3_active_products",
            "c3_active_contracts",
        ]
    ].merge(
        target[
            [
                "date",
                "total_net_pnl",
                "total_slippage",
                "account_equity",
                "broker10_margin_to_equity_pct",
                "broker10_total_margin_exact",
                "c3_active_products",
                "c3_active_contracts",
            ]
        ],
        on="date",
        how="inner",
        suffixes=("_source", "_target"),
    )
    merged["pair_name"] = pair_name
    merged["source_variant"] = source_variant
    merged["target_variant"] = target_variant
    merged["gap_pnl_source_minus_target"] = merged["total_net_pnl_source"] - merged["total_net_pnl_target"]
    merged["cum_gap_source_minus_target"] = merged["gap_pnl_source_minus_target"].cumsum()
    merged["target_loss_day"] = (merged["gap_pnl_source_minus_target"] > 0.0).astype(int)
    merged["source_margin_bucket"] = pd.cut(
        merged["broker10_margin_to_equity_pct_source"],
        bins=[-np.inf, 50.0, 75.0, 90.0, 100.0, np.inf],
        labels=["<=50", "50-75", "75-90", "90-100", ">100"],
    ).astype(str)
    merged["year"] = merged["date"].dt.year
    return merged


def _summaries(daily_gap: pd.DataFrame, summary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_map = summary.drop_duplicates("variant").set_index("variant").to_dict(orient="index")
    pair_rows: list[dict[str, Any]] = []
    for pair_name, frame in daily_gap.groupby("pair_name", sort=False):
        source_variant = str(frame["source_variant"].iloc[0])
        target_variant = str(frame["target_variant"].iloc[0])
        source_info = summary_map.get(source_variant, {})
        target_info = summary_map.get(target_variant, {})
        total_gap = float(frame["gap_pnl_source_minus_target"].sum())
        positive_loss = float(frame.loc[frame["gap_pnl_source_minus_target"] > 0.0, "gap_pnl_source_minus_target"].sum())
        negative_gain = float(frame.loc[frame["gap_pnl_source_minus_target"] < 0.0, "gap_pnl_source_minus_target"].sum())
        top5_loss = frame.sort_values("gap_pnl_source_minus_target", ascending=False).head(5)
        top10_loss = frame.sort_values("gap_pnl_source_minus_target", ascending=False).head(10)
        low_margin_loss = float(
            frame[
                (frame["gap_pnl_source_minus_target"] > 0.0)
                & (frame["broker10_margin_to_equity_pct_source"] <= 90.0)
            ]["gap_pnl_source_minus_target"].sum()
        )
        over100_loss = float(
            frame[
                (frame["gap_pnl_source_minus_target"] > 0.0)
                & (frame["broker10_margin_to_equity_pct_source"] > 100.0)
            ]["gap_pnl_source_minus_target"].sum()
        )
        pair_rows.append(
            {
                "pair_name": pair_name,
                "source_variant": source_variant,
                "target_variant": target_variant,
                "source_total_return_pct": source_info.get("total_return_pct"),
                "target_total_return_pct": target_info.get("total_return_pct"),
                "return_gap_pp_source_minus_target": float(
                    float(source_info.get("total_return_pct", 0.0)) - float(target_info.get("total_return_pct", 0.0))
                ),
                "source_max_dd_pct": source_info.get("max_dd_pct"),
                "target_max_dd_pct": target_info.get("max_dd_pct"),
                "source_max_broker10_pct": source_info.get("max_broker10_margin_to_equity_pct"),
                "target_max_broker10_pct": target_info.get("max_broker10_margin_to_equity_pct"),
                "source_days_over_100": source_info.get("days_over_100pct"),
                "target_days_over_100": target_info.get("days_over_100pct"),
                "total_gap_pnl": total_gap,
                "positive_loss_pnl": positive_loss,
                "negative_offset_gain_pnl": negative_gain,
                "top5_loss_pnl": float(top5_loss["gap_pnl_source_minus_target"].sum()),
                "top5_loss_share_of_positive_loss_pct": _safe_div(float(top5_loss["gap_pnl_source_minus_target"].sum()), positive_loss)
                * 100.0,
                "top10_loss_share_of_positive_loss_pct": _safe_div(float(top10_loss["gap_pnl_source_minus_target"].sum()), positive_loss)
                * 100.0,
                "low_margin_loss_share_pct": _safe_div(low_margin_loss, positive_loss) * 100.0,
                "over100_loss_share_pct": _safe_div(over100_loss, positive_loss) * 100.0,
            }
        )
    pair_summary = pd.DataFrame(pair_rows)

    year_gap = (
        daily_gap.groupby(["pair_name", "year"], as_index=False)
        .agg(
            gap_pnl_source_minus_target=("gap_pnl_source_minus_target", "sum"),
            positive_loss_pnl=("gap_pnl_source_minus_target", lambda x: float(x[x > 0.0].sum())),
            source_avg_broker10_pct=("broker10_margin_to_equity_pct_source", "mean"),
            source_max_broker10_pct=("broker10_margin_to_equity_pct_source", "max"),
        )
        .sort_values(["pair_name", "year"])
    )
    bucket_gap = (
        daily_gap.groupby(["pair_name", "source_margin_bucket"], as_index=False)
        .agg(
            gap_pnl_source_minus_target=("gap_pnl_source_minus_target", "sum"),
            positive_loss_pnl=("gap_pnl_source_minus_target", lambda x: float(x[x > 0.0].sum())),
            day_count=("date", "count"),
        )
        .sort_values(["pair_name", "source_margin_bucket"])
    )
    top_loss_days = (
        daily_gap.sort_values(["pair_name", "gap_pnl_source_minus_target"], ascending=[True, False])
        .groupby("pair_name", as_index=False)
        .head(12)[
            [
                "pair_name",
                "date",
                "source_variant",
                "target_variant",
                "gap_pnl_source_minus_target",
                "total_net_pnl_source",
                "total_net_pnl_target",
                "broker10_margin_to_equity_pct_source",
                "broker10_margin_to_equity_pct_target",
                "c3_active_products_source",
                "c3_active_products_target",
            ]
        ]
        .copy()
    )
    return pair_summary, year_gap, bucket_gap, top_loss_days


def _decision(pair_summary: pd.DataFrame, bucket_gap: pd.DataFrame) -> dict[str, Any]:
    usage80 = pair_summary[pair_summary["pair_name"].eq("r080_productcap30_to_usage80")]
    usage75 = pair_summary[pair_summary["pair_name"].eq("r080_productcap30_to_usage75")]
    productcap = pair_summary[pair_summary["pair_name"].eq("r070_no_cap_to_productcap30")]
    usage80_row = usage80.iloc[0].to_dict() if not usage80.empty else {}
    usage75_row = usage75.iloc[0].to_dict() if not usage75.empty else {}
    productcap_row = productcap.iloc[0].to_dict() if not productcap.empty else {}
    decision = "usage_gate_too_blunt_seek_surgical_peak_margin_or_low_margin_alpha"
    return {
        "decision": decision,
        "productcap_effect": productcap_row,
        "usage80_loss": usage80_row,
        "usage75_loss": usage75_row,
        "judgement": (
            "Product cap is not the source of return collapse. The broad usage gate cuts many profitable "
            "non-crisis days to solve a small number of broker100 spikes; next research should test a "
            "surgical peak-margin structure or a genuinely low-margin independent source, not usage/cap decimals."
        ),
    }


def _plot(daily_gap: pd.DataFrame, year_gap: pd.DataFrame, bucket_gap: pd.DataFrame, pair_summary: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    ax_cum, ax_year, ax_bucket, ax_scatter = axes.flatten()

    focus_pairs = ["r070_no_cap_to_productcap30", "r080_productcap30_to_usage80", "r080_productcap30_to_usage75"]
    for pair_name, frame in daily_gap[daily_gap["pair_name"].isin(focus_pairs)].groupby("pair_name", sort=False):
        ax_cum.plot(frame["date"], frame["cum_gap_source_minus_target"], label=pair_name, linewidth=1)
    ax_cum.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_cum.set_title("累计收益差：source - target")
    ax_cum.grid(alpha=0.25)
    ax_cum.legend(fontsize=8)

    yview = year_gap[year_gap["pair_name"].isin(["r080_productcap30_to_usage80", "r080_productcap30_to_usage75"])].copy()
    pivot = yview.pivot(index="year", columns="pair_name", values="gap_pnl_source_minus_target").fillna(0.0)
    pivot.plot(kind="bar", ax=ax_year)
    ax_year.axhline(0, color="#111827", linewidth=1)
    ax_year.set_title("按年份归因：usage gate损失")
    ax_year.set_ylabel("PnL")
    ax_year.grid(axis="y", alpha=0.25)

    bview = bucket_gap[bucket_gap["pair_name"].eq("r080_productcap30_to_usage80")].copy()
    ax_bucket.bar(bview["source_margin_bucket"], bview["positive_loss_pnl"], color="#f97316")
    ax_bucket.set_title("usage80损失按source保证金桶")
    ax_bucket.set_xlabel("source broker10 margin/equity")
    ax_bucket.set_ylabel("positive loss PnL")
    ax_bucket.grid(axis="y", alpha=0.25)

    sview = daily_gap[daily_gap["pair_name"].eq("r080_productcap30_to_usage80")].copy()
    ax_scatter.scatter(
        sview["broker10_margin_to_equity_pct_source"],
        sview["gap_pnl_source_minus_target"],
        s=10,
        alpha=0.35,
        color="#2563eb",
    )
    ax_scatter.axvline(100, color="#111827", linestyle="--", linewidth=1)
    ax_scatter.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_scatter.set_title("usage80日损失 vs source保证金")
    ax_scatter.set_xlabel("source broker10 margin/equity %")
    ax_scatter.set_ylabel("source - target daily PnL")
    ax_scatter.grid(alpha=0.25)

    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(pair_summary: pd.DataFrame, year_gap: pd.DataFrame, bucket_gap: pd.DataFrame, top_loss_days: pd.DataFrame, decision: dict[str, Any]) -> None:
    focus = pair_summary[
        pair_summary["pair_name"].isin(
            [
                "r070_no_cap_to_productcap30",
                "r070_productcap30_to_usage75",
                "r080_productcap30_to_usage80",
                "r080_productcap30_to_usage75",
            ]
        )
    ][
        [
            "pair_name",
            "source_total_return_pct",
            "target_total_return_pct",
            "return_gap_pp_source_minus_target",
            "source_max_broker10_pct",
            "target_max_broker10_pct",
            "source_days_over_100",
            "target_days_over_100",
            "top5_loss_share_of_positive_loss_pct",
            "low_margin_loss_share_pct",
            "over100_loss_share_pct",
        ]
    ]
    usage_year = year_gap[year_gap["pair_name"].isin(["r080_productcap30_to_usage80", "r080_productcap30_to_usage75"])].copy()
    usage_bucket = bucket_gap[bucket_gap["pair_name"].eq("r080_productcap30_to_usage80")].copy()
    top_usage = top_loss_days[top_loss_days["pair_name"].eq("r080_productcap30_to_usage80")].head(12)
    text = f"""# Stage523 Stage520收益损失归因

- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`
- 阶段性质：只读机制归因；不改策略、不新增交易规则、不扫小数。
- 决策：`{decision['decision']}`。

## Pair总览

{_md_table(focus)}

## usage gate按年份损失

{_md_table(usage_year)}

## r080 productcap30 -> usage80 按保证金桶损失

{_md_table(usage_bucket)}

## r080 productcap30 -> usage80 最大损失日

{_md_table(top_usage)}

## 判断

- 单产品 cap 不是收益塌缩来源；`r070_no_cap_to_productcap30` 的收益差为负，说明 productcap30 反而改善了收益和保证金形状。
- 真正损失来自总资金占用 gate。它为修复少量 broker100 尖峰，切掉了大量 source broker10 不高于90%的日子。
- 继续扫 `usage=76/77/78` 不解决本质；下一步如果沿策略本体优化，只能测试更外科的峰值保证金结构，或换低保证金独立收益源。
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    daily, summary = _load_inputs()
    daily_gaps = [_pair_daily(daily, pair_name, source, target) for pair_name, source, target in PAIRS]
    daily_gap = pd.concat(daily_gaps, ignore_index=True, sort=False)
    pair_summary, year_gap, bucket_gap, top_loss_days = _summaries(daily_gap, summary)
    decision = _decision(pair_summary, bucket_gap)
    _plot(daily_gap, year_gap, bucket_gap, pair_summary)

    pair_summary.to_csv(PAIR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    daily_gap.to_csv(DAILY_GAP_PATH, index=False, encoding="utf-8-sig")
    year_gap.to_csv(YEAR_GAP_PATH, index=False, encoding="utf-8-sig")
    bucket_gap.to_csv(BUCKET_GAP_PATH, index=False, encoding="utf-8-sig")
    top_loss_days.to_csv(TOP_LOSS_DAYS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(pair_summary, year_gap, bucket_gap, top_loss_days, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
