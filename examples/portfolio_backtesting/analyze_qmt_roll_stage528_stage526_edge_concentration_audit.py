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

MODEL_TAG = "stage528_stage526_edge_concentration_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage528_stage526_edge_concentration_audit"

STAGE526_TAG = "stage526_productcap25_breadth_frontier_v1"
STAGE526_PREFIX = "qmt_roll_stage526_productcap25_breadth_frontier"
STAGE520_TAG = "stage520_product_cap_usage_gate_frontier_v1"
STAGE520_PREFIX = "qmt_roll_stage520_product_cap_usage_gate_frontier"

STAGE526_DAILY_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_margin_daily_{STAGE526_TAG}.csv"
STAGE520_DAILY_IN = OUTPUT_DIR / f"{STAGE520_PREFIX}_margin_daily_{STAGE520_TAG}.csv"

PAIR_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pair_summary_{MODEL_TAG}.csv"
YEAR_EDGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_edge_{MODEL_TAG}.csv"
LEAVE_YEAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_leave_one_year_{MODEL_TAG}.csv"
TOP_EDGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_edge_days_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

CANDIDATE = "r080_pc25_maxpos4"
PAIRS: tuple[tuple[str, str], ...] = (
    ("r080_pc25_u75", "old_yield_hard_shell"),
    ("r070_pc30_u75", "old_stable_hard_shell"),
    ("r080_pc30_u80", "old_near_pass_high_yield"),
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


def _load_daily() -> pd.DataFrame:
    daily = pd.concat(
        [
            pd.read_csv(STAGE526_DAILY_IN, encoding="utf-8-sig"),
            pd.read_csv(STAGE520_DAILY_IN, encoding="utf-8-sig"),
        ],
        ignore_index=True,
        sort=False,
    )
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    for column in ["total_net_pnl", "account_equity", "broker10_margin_to_equity_pct"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    variants = {CANDIDATE, *[pair[0] for pair in PAIRS]}
    return daily[daily["variant"].isin(variants)].dropna(subset=["date"]).copy()


def _pair_edges(daily: pd.DataFrame) -> pd.DataFrame:
    cand = daily[daily["variant"].eq(CANDIDATE)][["date", "total_net_pnl", "account_equity", "broker10_margin_to_equity_pct"]].copy()
    rows: list[pd.DataFrame] = []
    for ref_variant, ref_label in PAIRS:
        ref = daily[daily["variant"].eq(ref_variant)][["date", "total_net_pnl", "account_equity", "broker10_margin_to_equity_pct"]].copy()
        merged = cand.merge(ref, on="date", how="inner", suffixes=("_candidate", "_reference"))
        merged["reference_variant"] = ref_variant
        merged["reference_label"] = ref_label
        merged["edge_pnl_candidate_minus_reference"] = merged["total_net_pnl_candidate"] - merged["total_net_pnl_reference"]
        merged["cum_edge_pnl"] = merged["edge_pnl_candidate_minus_reference"].cumsum()
        merged["year"] = merged["date"].dt.year
        rows.append(merged)
    return pd.concat(rows, ignore_index=True, sort=False)


def _summaries(edges: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pair_rows: list[dict[str, Any]] = []
    leave_rows: list[dict[str, Any]] = []
    top_rows: list[pd.DataFrame] = []
    year_edge = (
        edges.groupby(["reference_variant", "reference_label", "year"], as_index=False)
        .agg(
            edge_pnl=("edge_pnl_candidate_minus_reference", "sum"),
            positive_edge_pnl=("edge_pnl_candidate_minus_reference", lambda x: float(x[x > 0].sum())),
            negative_edge_pnl=("edge_pnl_candidate_minus_reference", lambda x: float(x[x < 0].sum())),
        )
        .sort_values(["reference_variant", "year"])
    )
    for reference, frame in edges.groupby("reference_variant", sort=False):
        label = str(frame["reference_label"].iloc[0])
        total_edge = float(frame["edge_pnl_candidate_minus_reference"].sum())
        positive_edge = float(frame.loc[frame["edge_pnl_candidate_minus_reference"] > 0, "edge_pnl_candidate_minus_reference"].sum())
        negative_edge = float(frame.loc[frame["edge_pnl_candidate_minus_reference"] < 0, "edge_pnl_candidate_minus_reference"].sum())
        top = frame.sort_values("edge_pnl_candidate_minus_reference", ascending=False).head(20).copy()
        top_rows.append(top[["reference_variant", "reference_label", "date", "edge_pnl_candidate_minus_reference", "total_net_pnl_candidate", "total_net_pnl_reference", "broker10_margin_to_equity_pct_candidate", "broker10_margin_to_equity_pct_reference"]])
        top5 = float(top.head(5)["edge_pnl_candidate_minus_reference"].sum())
        top10 = float(top.head(10)["edge_pnl_candidate_minus_reference"].sum())
        year_view = year_edge[year_edge["reference_variant"].eq(reference)].copy()
        max_year_edge = float(year_view["edge_pnl"].max()) if not year_view.empty else 0.0
        pair_rows.append(
            {
                "reference_variant": reference,
                "reference_label": label,
                "total_edge_pnl": total_edge,
                "positive_edge_pnl": positive_edge,
                "negative_edge_pnl": negative_edge,
                "top5_share_of_positive_edge_pct": _safe_div(top5, positive_edge) * 100.0,
                "top10_share_of_positive_edge_pct": _safe_div(top10, positive_edge) * 100.0,
                "max_year_edge_pnl": max_year_edge,
                "max_year_share_of_total_edge_pct": _safe_div(max_year_edge, total_edge) * 100.0,
                "edge_days_positive_pct": float((frame["edge_pnl_candidate_minus_reference"] > 0).mean() * 100.0),
            }
        )
        for year in sorted(frame["year"].dropna().unique()):
            remain = frame[~frame["year"].eq(year)]
            leave_rows.append(
                {
                    "reference_variant": reference,
                    "reference_label": label,
                    "left_out_year": int(year),
                    "remaining_edge_pnl": float(remain["edge_pnl_candidate_minus_reference"].sum()),
                    "remaining_positive": int(float(remain["edge_pnl_candidate_minus_reference"].sum()) > 0.0),
                }
            )
    return pd.DataFrame(pair_rows), year_edge, pd.DataFrame(leave_rows), pd.concat(top_rows, ignore_index=True, sort=False)


def _decision(pair_summary: pd.DataFrame, leave_year: pd.DataFrame) -> dict[str, Any]:
    primary = pair_summary[pair_summary["reference_variant"].eq("r080_pc25_u75")]
    primary_leave = leave_year[leave_year["reference_variant"].eq("r080_pc25_u75")]
    if primary.empty:
        label = "edge_audit_missing_primary"
    else:
        top5_share = float(primary["top5_share_of_positive_edge_pct"].iloc[0])
        max_year_share = float(primary["max_year_share_of_total_edge_pct"].iloc[0])
        all_leave_positive = bool(primary_leave["remaining_positive"].min() == 1) if not primary_leave.empty else False
        if all_leave_positive and top5_share < 35.0 and max_year_share < 50.0:
            label = "edge_not_one_day_leave_year_positive"
        elif all_leave_positive:
            label = "edge_positive_leave_year_but_concentrated"
        else:
            label = "edge_fails_leave_one_year"
    return {
        "decision": label,
        "primary_vs_r080_pc25_u75": primary.to_dict(orient="records"),
        "primary_leave_one_year": primary_leave.to_dict(orient="records"),
    }


def _plot(edges: pd.DataFrame, year_edge: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(1, 2, figsize=(15, 5))
    ax_cum, ax_year = axes
    for reference, frame in edges.groupby("reference_variant", sort=False):
        frame = frame.sort_values("date")
        ax_cum.plot(frame["date"], frame["cum_edge_pnl"], label=f"{CANDIDATE} - {reference}", linewidth=0.95)
    ax_cum.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_cum.set_title("累计edge PnL")
    ax_cum.grid(alpha=0.25)
    ax_cum.legend(fontsize=8)
    pivot = year_edge.pivot(index="year", columns="reference_variant", values="edge_pnl")
    pivot.plot(kind="bar", ax=ax_year)
    ax_year.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_year.set_title("按年份edge")
    ax_year.set_ylabel("PnL")
    ax_year.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(pair_summary: pd.DataFrame, year_edge: pd.DataFrame, leave_year: pd.DataFrame, top_edge: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage528 Stage526候选edge集中度审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        "- 阶段性质：只读反过拟合审计；不改策略、不重跑回测。",
        f"- 决策：`{decision.get('decision', '')}`。",
        "",
        "## Pair总览",
        "",
        _md_table(pair_summary),
        "",
        "## 年度edge",
        "",
        _md_table(year_edge),
        "",
        "## Leave-one-year",
        "",
        _md_table(leave_year),
        "",
        "## Top edge days",
        "",
        _md_table(top_edge, max_rows=20),
        "",
        "## 决策JSON",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    daily = _load_daily()
    edges = _pair_edges(daily)
    pair_summary, year_edge, leave_year, top_edge = _summaries(edges)
    decision = _decision(pair_summary, leave_year)
    _plot(edges, year_edge)
    _write_report(pair_summary, year_edge, leave_year, top_edge, decision)
    pair_summary.to_csv(PAIR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    year_edge.to_csv(YEAR_EDGE_PATH, index=False, encoding="utf-8-sig")
    leave_year.to_csv(LEAVE_YEAR_PATH, index=False, encoding="utf-8-sig")
    top_edge.to_csv(TOP_EDGE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
