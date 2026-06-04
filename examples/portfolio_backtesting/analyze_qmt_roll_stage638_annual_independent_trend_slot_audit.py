from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage638_annual_independent_trend_slot_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage638_annual_independent_trend_slot_audit"

STAGE541_ANNUAL = OUTPUT_DIR / "qmt_roll_stage541_single_product_opportunity_map_annual_stage541_single_product_opportunity_map_v1.csv"
STAGE541_SUMMARY = OUTPUT_DIR / "qmt_roll_stage541_single_product_opportunity_map_summary_stage541_single_product_opportunity_map_v1.csv"
STAGE557_PRODUCT = OUTPUT_DIR / "qmt_roll_stage557_breadth_low_single_risk_pool_audit_satellite_product_harvest_stage557_breadth_low_single_risk_pool_audit_v1.csv"
STAGE563_DECISION = OUTPUT_DIR / "qmt_roll_stage563_breadth_pool_product_selection_thesis_audit_decision_stage563_breadth_pool_product_selection_thesis_audit_v1.json"
STAGE633_PRODUCT_MAP = OUTPUT_DIR / "qmt_roll_stage633_independent_risk_slot_correlation_map_product_map_stage633_independent_risk_slot_correlation_map_v1.csv"
STAGE633_FAMILY_MAP = OUTPUT_DIR / "qmt_roll_stage633_independent_risk_slot_correlation_map_family_map_stage633_independent_risk_slot_correlation_map_v1.csv"

ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_slot_opportunity_{MODEL_TAG}.csv"
FAMILY_YEAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_year_opportunity_{MODEL_TAG}.csv"
PRODUCT_LADDER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_ladder_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

REFERENCES = [
    "Trend-following, Risk-Parity and the Influence of Correlations: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2673124",
    "Trend Following, Risk Parity and Momentum in Commodity Futures: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2126813",
    "Increasing Diversification of Commodities Trend-Following Strategies: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4871376",
    "Diversifying Trends / CoTrend dependence measure: https://www.sciencedirect.com/science/article/abs/pii/S245230622100109X",
    "NBER Facts and Fantasies about Commodity Futures: https://www.nber.org/papers/w10595",
]

TOP_N = 6
MIN_TOP_FAMILY_COUNT = 3
MIN_WATCH_OR_WORKLIST_PRODUCTS_PER_YEAR = 2
TARGET_EFFECTIVE_SLOTS = 7
CURRENT_EFFECTIVE_SLOTS = 4

WORKLIST_BUCKETS = {
    "p1_existing_worklist_source_tca_blocked",
    "p2_existing_forward_monitor",
    "observe_low_corr_but_weak_trend",
}
REJECT_BUCKETS = {
    "reject_high_core_corr",
    "reject_data_or_liquidity",
    "reject_out_of_commodity_scope",
    "same_family_depth_not_slot",
}


def _now_cst() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def _fmt_cst(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S CST")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return (
        pd.to_numeric(frame[column], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(default)
        .astype(float)
    )


def _str(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series("", index=frame.index, dtype=str)
    return frame[column].fillna("").astype(str).str.strip()


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
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 40) -> str:
    if frame.empty:
        return "_empty_"
    view = frame.copy()
    if columns is not None:
        view = view[[column for column in columns if column in view.columns]]
    if len(view) > max_rows:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    annual = _read_csv(STAGE541_ANNUAL)
    summary = _read_csv(STAGE541_SUMMARY)
    product_map = _read_csv(STAGE633_PRODUCT_MAP)
    family_map = _read_csv(STAGE633_FAMILY_MAP)
    stage557_product = _read_csv(STAGE557_PRODUCT)
    stage563_decision = _read_json(STAGE563_DECISION)

    annual["product_vt_symbol"] = _str(annual, "product_vt_symbol")
    summary["product_vt_symbol"] = _str(summary, "product_vt_symbol")
    product_map["product_vt_symbol"] = _str(product_map, "product_vt_symbol")

    keep_cols = [
        "product_vt_symbol",
        "exchange",
        "product_family",
        "structural_bucket",
        "max_abs_corr_to_p0",
        "tail_abs_corr_to_p0_composite",
        "rolling_abs_corr_p75_to_p0",
        "low_corr_pass",
        "watch_corr_pass",
        "trend_opportunity_pass",
        "data_pass",
        "liquidity_pass",
        "deployable_new_slot_now",
        "paper_allowed_now",
        "trading_whitelist_allowed_now",
    ]
    product_map = product_map[[column for column in keep_cols if column in product_map.columns]].copy()
    for column in [
        "low_corr_pass",
        "watch_corr_pass",
        "trend_opportunity_pass",
        "data_pass",
        "liquidity_pass",
        "deployable_new_slot_now",
        "paper_allowed_now",
        "trading_whitelist_allowed_now",
    ]:
        product_map[column] = _num(product_map, column).astype(int)
    for column in ["max_abs_corr_to_p0", "tail_abs_corr_to_p0_composite", "rolling_abs_corr_p75_to_p0"]:
        product_map[column] = _num(product_map, column, np.nan)

    summary_keep = [
        "product_vt_symbol",
        "exchange",
        "is_core_product",
        "total_pnl",
        "total_return_pct",
        "max_dd_pct",
        "ulcer_pct",
        "sharpe",
        "trade_count",
        "active_year_count",
        "positive_active_years",
        "positive_active_year_rate_pct",
        "core_daily_pnl_corr",
        "candidate_materiality_pass",
        "opportunity_score",
        "recent_median_volume",
    ]
    summary = summary[[column for column in summary_keep if column in summary.columns]].copy()
    for column in [
        "is_core_product",
        "total_pnl",
        "total_return_pct",
        "max_dd_pct",
        "ulcer_pct",
        "sharpe",
        "trade_count",
        "active_year_count",
        "positive_active_years",
        "positive_active_year_rate_pct",
        "core_daily_pnl_corr",
        "candidate_materiality_pass",
        "opportunity_score",
        "recent_median_volume",
    ]:
        summary[column] = _num(summary, column)

    merged = annual.merge(summary[["product_vt_symbol", "exchange"]], on="product_vt_symbol", how="left")
    merged = merged.merge(product_map, on=["product_vt_symbol", "exchange"], how="left")
    merged["product_family"] = _str(merged, "product_family").replace("", "unknown")
    merged["structural_bucket"] = _str(merged, "structural_bucket").replace("", "unknown")
    for column in ["year", "is_core_product", "trade_count", "active_days"]:
        merged[column] = _num(merged, column).astype(int)
    merged["net_pnl"] = _num(merged, "net_pnl")
    merged["slippage"] = _num(merged, "slippage")
    return merged, summary, product_map, family_map, stage557_product, stage563_decision


def _bucket_counts(group: pd.DataFrame) -> dict[str, int]:
    return {str(key): int(value) for key, value in group["structural_bucket"].value_counts().sort_index().items()}


def _build_annual_slot_opportunity(annual: pd.DataFrame) -> pd.DataFrame:
    frame = annual[annual["is_core_product"].eq(0) & annual["exchange"].ne("CFFEX")].copy()
    rows: list[dict[str, Any]] = []
    for year, group in frame.groupby("year"):
        group = group.sort_values("net_pnl", ascending=False).copy()
        active = group[group["trade_count"].gt(0)]
        positive = group[group["net_pnl"].gt(0)]
        top = group.head(TOP_N).copy()
        top_positive = top[top["net_pnl"].gt(0)]
        top_pnl = float(top["net_pnl"].sum())
        positive_pnl = float(positive["net_pnl"].sum())
        top_family_sum = top.groupby("product_family")["net_pnl"].sum().sort_values(ascending=False)
        top_family_positive_sum = top_positive.groupby("product_family")["net_pnl"].sum().sort_values(ascending=False)
        best_family_pnl = float(top_family_sum.iloc[0]) if not top_family_sum.empty else 0.0
        best_family_positive_pnl = float(top_family_positive_sum.iloc[0]) if not top_family_positive_sum.empty else 0.0
        top_worklist = top[top["structural_bucket"].isin(WORKLIST_BUCKETS)]
        top_reject = top[top["structural_bucket"].isin(REJECT_BUCKETS)]
        top_low_or_watch = top[_num(top, "low_corr_pass").eq(1) | _num(top, "watch_corr_pass").eq(1)]
        bucket_counts = _bucket_counts(top)
        rows.append(
            {
                "year": int(year),
                "noncore_products": int(group["product_vt_symbol"].nunique()),
                "active_noncore_products": int(active["product_vt_symbol"].nunique()),
                "positive_noncore_products": int(positive["product_vt_symbol"].nunique()),
                "positive_noncore_pnl": positive_pnl,
                "top6_pnl": top_pnl,
                "top6_products": ",".join(top["product_vt_symbol"].tolist()),
                "top6_families": ",".join(top["product_family"].drop_duplicates().tolist()),
                "top6_family_count": int(top["product_family"].nunique()),
                "top6_positive_family_count": int(top_positive["product_family"].nunique()),
                "top6_low_or_watch_corr_products": int(len(top_low_or_watch)),
                "top6_worklist_or_monitor_products": int(len(top_worklist)),
                "top6_reject_bucket_products": int(len(top_reject)),
                "top6_deployable_products": int(_num(top, "deployable_new_slot_now").sum()),
                "best_product": str(top["product_vt_symbol"].iloc[0]) if not top.empty else "",
                "best_product_pnl": float(top["net_pnl"].iloc[0]) if not top.empty else 0.0,
                "best_product_family": str(top["product_family"].iloc[0]) if not top.empty else "",
                "best_product_bucket": str(top["structural_bucket"].iloc[0]) if not top.empty else "",
                "top1_share_of_top6_pct": float(top["net_pnl"].iloc[0] / top_pnl * 100.0) if top_pnl > 0 and not top.empty else 0.0,
                "best_family_share_of_top6_pct": float(best_family_pnl / top_pnl * 100.0) if top_pnl > 0 else 0.0,
                "best_family_share_of_positive_top6_pct": (
                    float(best_family_positive_pnl / top_positive["net_pnl"].sum() * 100.0)
                    if float(top_positive["net_pnl"].sum()) > 0
                    else 0.0
                ),
                "top6_bucket_counts_json": json.dumps(bucket_counts, ensure_ascii=False, sort_keys=True),
                "annual_opportunity_exists": int(top_pnl > 0 and int(positive["product_vt_symbol"].nunique()) >= 3),
                "annual_independent_family_pass": int(top["product_family"].nunique() >= MIN_TOP_FAMILY_COUNT),
                "annual_worklist_monitor_pass": int(len(top_worklist) >= MIN_WATCH_OR_WORKLIST_PRODUCTS_PER_YEAR),
                "annual_deployable_pass": int(_num(top, "deployable_new_slot_now").sum() > 0),
            }
        )
    return pd.DataFrame(rows).sort_values("year").reset_index(drop=True)


def _build_family_year(annual: pd.DataFrame) -> pd.DataFrame:
    frame = annual[annual["is_core_product"].eq(0) & annual["exchange"].ne("CFFEX")].copy()
    rows = (
        frame.groupby(["year", "product_family", "structural_bucket"], as_index=False)
        .agg(
            family_bucket_pnl=("net_pnl", "sum"),
            active_products=("product_vt_symbol", "nunique"),
            positive_products=("net_pnl", lambda item: int((item > 0).sum())),
            trades=("trade_count", "sum"),
        )
        .sort_values(["year", "family_bucket_pnl"], ascending=[True, False])
    )
    rows["family_rank_by_year"] = rows.groupby("year")["family_bucket_pnl"].rank(method="first", ascending=False).astype(int)
    return rows


def _build_product_ladder(summary: pd.DataFrame, product_map: pd.DataFrame, stage557_product: pd.DataFrame) -> pd.DataFrame:
    frame = summary[summary["is_core_product"].eq(0) & summary["exchange"].ne("CFFEX")].copy()
    frame = frame.merge(product_map, on=["product_vt_symbol", "exchange"], how="left", suffixes=("", "_stage633"))
    if not stage557_product.empty and {"product_vt_symbol", "satellite_product_net_pnl"}.issubset(stage557_product.columns):
        harvest = stage557_product.copy()
        harvest["product_vt_symbol"] = _str(harvest, "product_vt_symbol")
        harvest = (
            harvest.groupby("product_vt_symbol", as_index=False)
            .agg(
                breadth_all_noncore_satellite_pnl=("satellite_product_net_pnl", "sum"),
                breadth_all_noncore_active_days=("active_days", "sum"),
                breadth_all_noncore_max_margin=("max_margin", "max"),
            )
        )
        frame = frame.merge(harvest, on="product_vt_symbol", how="left")
    else:
        frame["breadth_all_noncore_satellite_pnl"] = 0.0
        frame["breadth_all_noncore_active_days"] = 0.0
        frame["breadth_all_noncore_max_margin"] = 0.0
    for column in ["candidate_materiality_pass", "low_corr_pass", "watch_corr_pass", "deployable_new_slot_now"]:
        frame[column] = _num(frame, column).astype(int)
    frame["abs_core_daily_pnl_corr"] = _num(frame, "core_daily_pnl_corr").abs()
    frame["ladder_bucket"] = np.select(
        [
            frame["deployable_new_slot_now"].gt(0),
            frame["structural_bucket"].eq("p1_existing_worklist_source_tca_blocked"),
            frame["structural_bucket"].eq("p2_existing_forward_monitor"),
            frame["structural_bucket"].eq("observe_low_corr_but_weak_trend"),
            frame["candidate_materiality_pass"].eq(1),
        ],
        [
            "deployable_now",
            "p1_source_tca_blocked",
            "p2_forward_monitor",
            "watch_low_corr_source_needed",
            "material_but_not_independent_slot",
        ],
        default="reject_or_reference",
    )
    return frame.sort_values(
        ["ladder_bucket", "candidate_materiality_pass", "total_pnl", "opportunity_score"],
        ascending=[True, False, False, False],
    ).reset_index(drop=True)


def _build_gates(annual_slot: pd.DataFrame, product_ladder: pd.DataFrame, stage563_decision: dict[str, Any]) -> pd.DataFrame:
    years = int(len(annual_slot))
    opportunity_years = int(annual_slot["annual_opportunity_exists"].sum())
    independent_family_years = int(annual_slot["annual_independent_family_pass"].sum())
    worklist_years = int(annual_slot["annual_worklist_monitor_pass"].sum())
    deployable_years = int(annual_slot["annual_deployable_pass"].sum())
    deployable_products = int(product_ladder["deployable_new_slot_now"].sum())
    p1_products = int(product_ladder["ladder_bucket"].eq("p1_source_tca_blocked").sum())
    p2_products = int(product_ladder["ladder_bucket"].eq("p2_forward_monitor").sum())
    watch_products = int(product_ladder["ladder_bucket"].eq("watch_low_corr_source_needed").sum())
    all_breadth_pnl = float(stage563_decision.get("all_breadth_sleeve_pnl", np.nan))
    prevpos_pnl = float(stage563_decision.get("prev_year_positive_sleeve_pnl", np.nan))
    rows = [
        {
            "gate": "annual_opportunity_exists",
            "passed": int(opportunity_years == years and years > 0),
            "current": f"{opportunity_years}/{years}",
            "required": "all years",
            "note": "Non-core single-product oracle top6 has positive opportunity each year.",
        },
        {
            "gate": "opportunity_not_single_family_only",
            "passed": int(independent_family_years >= max(1, years - 1)),
            "current": f"{independent_family_years}/{years}",
            "required": f">={years - 1}/{years}",
            "note": "Annual top6 should usually span at least 3 product families.",
        },
        {
            "gate": "worklist_monitor_year_coverage",
            "passed": int((p1_products + p2_products + watch_products) > 0 and worklist_years > 0),
            "current": f"products={p1_products + p2_products + watch_products},years={worklist_years}/{years}",
            "required": f">=2 top6 worklist/monitor products in at least 1/{years} year",
            "note": "Worklist products exist globally, but annual oracle top6 is not sufficiently covered by current P1/P2/watch lanes.",
        },
        {
            "gate": "broad_low_risk_sleeve_failed_capture",
            "passed": int(pd.notna(all_breadth_pnl) and pd.notna(prevpos_pnl) and all_breadth_pnl > 0 and prevpos_pnl < 0),
            "current": f"all={all_breadth_pnl:.0f},prevpos={prevpos_pnl:.0f}",
            "required": "wide pool weak",
            "note": "Stage563 shows broad low-risk sleeve did not reliably capture opportunity.",
        },
        {
            "gate": "deployable_new_slot_zero",
            "passed": int(deployable_products == 0 and deployable_years == 0),
            "current": f"products={deployable_products},years={deployable_years}/{years}",
            "required": "0",
            "note": "No annual opportunity is allowed to become deployable without source/TCA/selector gates.",
        },
        {
            "gate": "target_effective_slots_not_met",
            "passed": int(CURRENT_EFFECTIVE_SLOTS < TARGET_EFFECTIVE_SLOTS and deployable_products == 0),
            "current": f"{CURRENT_EFFECTIVE_SLOTS}/{TARGET_EFFECTIVE_SLOTS}",
            "required": "fail closed",
            "note": "The desired lower single-slot risk is still aspirational, not available for live sizing.",
        },
        {
            "gate": "paper_and_whitelist_zero",
            "passed": int(_num(product_ladder, "paper_allowed_now").sum() == 0 and _num(product_ladder, "trading_whitelist_allowed_now").sum() == 0),
            "current": f"paper={int(_num(product_ladder, 'paper_allowed_now').sum())},whitelist={int(_num(product_ladder, 'trading_whitelist_allowed_now').sum())}",
            "required": "0/0",
            "note": "This audit must not create paper or trading whitelist rows.",
        },
    ]
    return pd.DataFrame(rows)


def _write_chart(annual_slot: pd.DataFrame, family_year: pd.DataFrame, product_ladder: pd.DataFrame, gates: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 11))
    fig.suptitle("Stage638 annual independent trend slot audit: opportunity exists, selector still locked", fontsize=16)

    ax = axes[0, 0]
    x = np.arange(len(annual_slot))
    ax.bar(x, annual_slot["top6_pnl"], color="#3182ce", label="oracle top6 pnl")
    ax2 = ax.twinx()
    ax2.plot(x, annual_slot["top6_family_count"], color="#dd6b20", marker="o", label="top6 families")
    ax2.plot(x, annual_slot["top6_worklist_or_monitor_products"], color="#805ad5", marker="s", label="worklist/monitor products")
    ax.set_xticks(x)
    ax.set_xticklabels(annual_slot["year"].astype(str), rotation=0)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Annual non-core oracle top6 opportunity and family breadth")
    ax.set_ylabel("PnL")
    ax2.set_ylabel("count")
    ax.legend(loc="upper left", fontsize=8)
    ax2.legend(loc="upper right", fontsize=8)

    ax = axes[0, 1]
    bucket_rows = []
    for _, row in annual_slot.iterrows():
        counts = json.loads(row["top6_bucket_counts_json"])
        for bucket, count in counts.items():
            bucket_rows.append({"year": int(row["year"]), "bucket": bucket, "count": int(count)})
    bucket = pd.DataFrame(bucket_rows)
    if not bucket.empty:
        pivot = bucket.pivot_table(index="year", columns="bucket", values="count", fill_value=0, aggfunc="sum")
        order = [column for column in [
            "p1_existing_worklist_source_tca_blocked",
            "p2_existing_forward_monitor",
            "observe_low_corr_but_weak_trend",
            "reject_high_core_corr",
            "reject_data_or_liquidity",
            "p0_reference_existing_slot",
            "unknown",
        ] if column in pivot.columns] + [column for column in pivot.columns if column not in {
            "p1_existing_worklist_source_tca_blocked",
            "p2_existing_forward_monitor",
            "observe_low_corr_but_weak_trend",
            "reject_high_core_corr",
            "reject_data_or_liquidity",
            "p0_reference_existing_slot",
            "unknown",
        }]
        bottom = np.zeros(len(pivot))
        colors = {
            "p1_existing_worklist_source_tca_blocked": "#ed8936",
            "p2_existing_forward_monitor": "#9f7aea",
            "observe_low_corr_but_weak_trend": "#38a169",
            "reject_high_core_corr": "#e53e3e",
            "reject_data_or_liquidity": "#4a5568",
            "p0_reference_existing_slot": "#2b6cb0",
            "unknown": "#a0aec0",
        }
        for column in order:
            values = pivot[column].to_numpy(dtype=float)
            ax.bar(pivot.index.astype(str), values, bottom=bottom, label=column, color=colors.get(column, "#cbd5e0"))
            bottom += values
        ax.set_title("Annual top6 structural buckets")
        ax.set_ylabel("top6 product count")
        ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=7)
    else:
        ax.text(0.5, 0.5, "No bucket rows", ha="center", va="center")
        ax.set_axis_off()

    ax = axes[1, 0]
    top_family = (
        family_year[family_year["family_rank_by_year"].le(1)]
        .sort_values(["year", "family_bucket_pnl"], ascending=[True, False])
        .copy()
    )
    family_keep = (
        family_year.groupby("product_family")["family_bucket_pnl"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .index.tolist()
    )
    heat = (
        family_year[family_year["product_family"].isin(family_keep)]
        .pivot_table(index="product_family", columns="year", values="family_bucket_pnl", aggfunc="sum", fill_value=0.0)
        .reindex(family_keep)
    )
    if not heat.empty:
        vmax = max(abs(float(heat.min().min())), abs(float(heat.max().max())), 1.0)
        image = ax.imshow(heat.values, cmap="coolwarm", vmin=-vmax, vmax=vmax, aspect="auto")
        ax.set_xticks(np.arange(len(heat.columns)))
        ax.set_xticklabels(heat.columns.astype(str), rotation=0)
        ax.set_yticks(np.arange(len(heat.index)))
        ax.set_yticklabels(heat.index, fontsize=8)
        ax.set_title("Family-year single-product opportunity heatmap")
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
        for _, row in top_family.iterrows():
            if row["product_family"] in heat.index and row["year"] in heat.columns:
                y = list(heat.index).index(row["product_family"])
                xloc = list(heat.columns).index(row["year"])
                ax.text(xloc, y, "*", ha="center", va="center", fontsize=12, color="black")
    else:
        ax.text(0.5, 0.5, "No heatmap", ha="center", va="center")
        ax.set_axis_off()

    ax = axes[1, 1]
    colors = ["tab:green" if int(item) == 1 else "tab:red" for item in gates["passed"]]
    ax.barh(gates["gate"], gates["passed"], color=colors)
    ax.set_xlim(0, 1)
    ax.set_title("Hard gates: green includes fail-closed locks")
    ax.tick_params(axis="y", labelsize=8)
    for i, row in gates.iterrows():
        ax.text(0.02, i, str(row["current"]), va="center", ha="left", fontsize=8, color="white")

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    generated_at: datetime,
    annual_slot: pd.DataFrame,
    family_year: pd.DataFrame,
    product_ladder: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage638 Annual Independent Trend Slot Audit Report",
        "",
        f"- generated_at_cst: `{_fmt_cst(generated_at)}`",
        f"- decision: `{decision['decision']}`",
        "- stage nature: annual opportunity x independent risk slot audit; no strategy replay, no selector, no paper, no CTP.",
        "",
        "## External Research Judgement",
        "",
        "文献方向支持趋势策略需要广市场分散，但分散的有效单位不是产品数量，而是不同经济来源、不同相关结构和不同尾部行为的风险槽。仅靠降低单笔风险并扩大产品数，容易把同一产业链或同一宏观风险重复买入；真正有价值的是：年度趋势机会存在、跨家族分布、低相关/可监控、并且有可实盘累计的 PIT source/TCA/selector。",
        "",
        "References:",
        *[f"- {item}" for item in REFERENCES],
        "",
        "## Key Numbers",
        "",
        f"- annual years: `{decision['annual_years']}`",
        f"- opportunity years: `{decision['opportunity_years']}`",
        f"- independent-family years: `{decision['independent_family_years']}`",
        f"- worklist/monitor years: `{decision['worklist_monitor_years']}`",
        f"- deployable products: `{decision['deployable_products']}`",
        f"- p1 products: `{decision['p1_products']}`",
        f"- p2 products: `{decision['p2_products']}`",
        f"- watch products: `{decision['watch_products']}`",
        f"- all-breadth sleeve pnl from Stage563: `{decision['stage563_all_breadth_sleeve_pnl']}`",
        f"- prev-year-positive sleeve pnl from Stage563: `{decision['stage563_prev_year_positive_sleeve_pnl']}`",
        f"- hard gates: `{decision['hard_gates_passed']}/{decision['hard_gates_total']}`",
        "",
        "## Annual Slot Opportunity",
        "",
        _md_table(
            annual_slot,
            columns=[
                "year",
                "positive_noncore_products",
                "top6_pnl",
                "top6_family_count",
                "top6_worklist_or_monitor_products",
                "top6_reject_bucket_products",
                "top6_deployable_products",
                "top1_share_of_top6_pct",
                "best_family_share_of_top6_pct",
                "top6_products",
                "top6_families",
                "best_product_bucket",
            ],
        ),
        "",
        "## Product Ladder",
        "",
        _md_table(
            product_ladder.sort_values(["ladder_bucket", "total_pnl"], ascending=[True, False]),
            columns=[
                "product_vt_symbol",
                "product_family",
                "ladder_bucket",
                "structural_bucket",
                "total_pnl",
                "max_dd_pct",
                "candidate_materiality_pass",
                "max_abs_corr_to_p0",
                "tail_abs_corr_to_p0_composite",
                "watch_corr_pass",
                "breadth_all_noncore_satellite_pnl",
            ],
            max_rows=35,
        ),
        "",
        "## Top Family-Year Opportunity",
        "",
        _md_table(
            family_year.sort_values(["year", "family_bucket_pnl"], ascending=[True, False]),
            columns=[
                "year",
                "product_family",
                "structural_bucket",
                "family_bucket_pnl",
                "active_products",
                "positive_products",
                "family_rank_by_year",
            ],
            max_rows=50,
        ),
        "",
        "## Gates",
        "",
        _md_table(gates),
        "",
        "## Interpretation",
        "",
        "- 年度趋势机会不是问题：非核心单品种 oracle top6 在所有年份都有正机会。",
        "- 机会通常跨多个家族，但这只是 hindsight/oracle 事实；真正的难点是事前选出，并且保证 source/TCA/相关性实时可执行。",
        "- Stage563 已经证明宽池低单笔风险没有可靠捕获这些机会，说明问题不在仓位太大，而在 selector 不够强。",
        "- 本阶段不产生 selector、paper、A/B 或交易白名单；下一步仍是 P1/P2/watch 产品的 PIT/source/TCA/outcome 累计。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    generated_at = _now_cst()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    annual, summary, product_map, _family_map, stage557_product, stage563_decision = _load_inputs()
    annual_slot = _build_annual_slot_opportunity(annual)
    family_year = _build_family_year(annual)
    product_ladder = _build_product_ladder(summary, product_map, stage557_product)
    gates = _build_gates(annual_slot, product_ladder, stage563_decision)

    years = int(len(annual_slot))
    p1_products = int(product_ladder["ladder_bucket"].eq("p1_source_tca_blocked").sum())
    p2_products = int(product_ladder["ladder_bucket"].eq("p2_forward_monitor").sum())
    watch_products = int(product_ladder["ladder_bucket"].eq("watch_low_corr_source_needed").sum())
    deployable_products = int(product_ladder["deployable_new_slot_now"].sum())
    decision = {
        "model_tag": MODEL_TAG,
        "decision": "annual_opportunity_valid_selector_not_ready_no_promotion",
        "generated_at_cst": _fmt_cst(generated_at),
        "line_id": LINE_ID,
        "annual_years": years,
        "opportunity_years": int(annual_slot["annual_opportunity_exists"].sum()),
        "independent_family_years": int(annual_slot["annual_independent_family_pass"].sum()),
        "worklist_monitor_years": int(annual_slot["annual_worklist_monitor_pass"].sum()),
        "deployable_years": int(annual_slot["annual_deployable_pass"].sum()),
        "deployable_products": deployable_products,
        "p1_products": p1_products,
        "p2_products": p2_products,
        "watch_products": watch_products,
        "current_effective_slots": CURRENT_EFFECTIVE_SLOTS,
        "target_effective_slots": TARGET_EFFECTIVE_SLOTS,
        "stage563_all_breadth_sleeve_pnl": float(stage563_decision.get("all_breadth_sleeve_pnl", np.nan)),
        "stage563_prev_year_positive_sleeve_pnl": float(stage563_decision.get("prev_year_positive_sleeve_pnl", np.nan)),
        "hard_gates_passed": int(gates["passed"].sum()),
        "hard_gates_total": int(len(gates)),
        "annual_path": str(ANNUAL_PATH),
        "family_year_path": str(FAMILY_YEAR_PATH),
        "product_ladder_path": str(PRODUCT_LADDER_PATH),
        "chart_path": str(CHART_PATH),
    }

    annual_slot.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    family_year.to_csv(FAMILY_YEAR_PATH, index=False, encoding="utf-8-sig")
    product_ladder.to_csv(PRODUCT_LADDER_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_report(generated_at, annual_slot, family_year, product_ladder, gates, decision)
    _write_chart(annual_slot, family_year, product_ladder, gates)
    print(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
