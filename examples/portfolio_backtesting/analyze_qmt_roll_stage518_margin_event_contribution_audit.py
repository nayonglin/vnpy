from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513  # noqa: E402


MODEL_TAG = "stage518_margin_event_contribution_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage518_margin_event_contribution_audit"

SOURCE_PREFIX = "qmt_roll_stage517_portfolio_margin_deleverage_frontier"
SOURCE_TAG = "stage517_portfolio_margin_deleverage_frontier_v1"

MARGIN_DAILY_IN = OUTPUT_DIR / f"{SOURCE_PREFIX}_margin_daily_{SOURCE_TAG}.csv"
POSITIONS_IN = OUTPUT_DIR / f"{SOURCE_PREFIX}_positions_{SOURCE_TAG}.csv"
SUMMARY_IN = OUTPUT_DIR / f"{SOURCE_PREFIX}_summary_{SOURCE_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
EVENT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_events_{MODEL_TAG}.csv"
PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_rank_{MODEL_TAG}.csv"
PRODUCT_AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_aggregate_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

BROKER_MARGIN_MULTIPLIER = float(s513.s403.BROKER10_MULTIPLIER)
TARGET_VARIANTS = (
    "r060_legacy_nocap_control",
    "r070_legacy_nocap_control",
    "r070_cluster35",
    "r070_pm_all_90_110",
)
CHUNK_SIZE = 400_000


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


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


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = equity.astype(float)
    return (values / values.cummax() - 1.0) * 100.0


def _product_from_contract_series(vt_symbols: pd.Series) -> pd.Series:
    raw = vt_symbols.astype(str)
    symbol = raw.str.split(".", n=1, expand=True)[0]
    exchange = raw.str.split(".", n=1, expand=True)[1].fillna("")
    letters = symbol.str.replace(r"[^A-Za-z]", "", regex=True)
    product = letters.where(letters.ne(""), symbol)
    return product + "." + exchange


def _load_margin_daily() -> pd.DataFrame:
    frame = pd.read_csv(MARGIN_DAILY_IN, encoding="utf-8-sig")
    frame = frame[frame["variant"].isin(TARGET_VARIANTS)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    numeric_columns = [
        "account_equity",
        "broker10_margin_to_equity_pct",
        "total_margin_exact",
        "broker10_total_margin_exact",
        "c3_margin_exact",
        "xsmom_true_margin",
        "xsmom_true_daily_pnl",
        "net_pnl",
        "total_net_pnl",
    ]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    pieces: list[pd.DataFrame] = []
    for variant, group in frame.groupby("variant", sort=False):
        ordered = group.sort_values("date").copy()
        ordered["drawdown_pct"] = _drawdown_pct(
            pd.Series(ordered["account_equity"].to_numpy(dtype=float), index=ordered["date"])
        ).to_numpy()
        pieces.append(ordered)
    return pd.concat(pieces, ignore_index=True)


def _event_days(margin_daily: pd.DataFrame) -> pd.DataFrame:
    events = margin_daily[margin_daily["broker10_margin_to_equity_pct"].gt(100.0)].copy()
    events["required_exact_margin_reduction"] = (
        events["total_margin_exact"] - events["account_equity"] / BROKER_MARGIN_MULTIPLIER
    ).clip(lower=0.0)
    events["required_margin_reduction_pct_of_total"] = (
        events["required_exact_margin_reduction"] / events["total_margin_exact"].replace(0.0, np.nan) * 100.0
    ).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return events.sort_values(["variant", "date"]).reset_index(drop=True)


def _load_event_product_margin(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    metadata = s513._metadata()
    sizes = {str(key): float(value) for key, value in metadata["sizes"].items()}
    margin_ratios = {str(key): float(value) for key, value in metadata["margin_ratios"].items()}
    event_dates = set(events["date"].dt.strftime("%Y-%m-%d"))
    event_variants = set(events["variant"].astype(str))
    columns = [
        "date",
        "vt_symbol",
        "end_pos",
        "close_price",
        "holding_pnl",
        "trading_pnl",
        "net_pnl",
        "variant",
    ]
    pieces: list[pd.DataFrame] = []
    for chunk in pd.read_csv(POSITIONS_IN, usecols=columns, chunksize=CHUNK_SIZE, encoding="utf-8-sig"):
        chunk = chunk[
            chunk["variant"].astype(str).isin(event_variants)
            & chunk["date"].astype(str).isin(event_dates)
        ].copy()
        if chunk.empty:
            continue
        for column in ["end_pos", "close_price", "holding_pnl", "trading_pnl", "net_pnl"]:
            chunk[column] = pd.to_numeric(chunk[column], errors="coerce").fillna(0.0)
        chunk["abs_end_pos"] = chunk["end_pos"].abs()
        chunk = chunk[chunk["abs_end_pos"].gt(0.0)].copy()
        if chunk.empty:
            continue
        chunk["size"] = chunk["vt_symbol"].astype(str).map(sizes).fillna(1.0).astype(float)
        chunk["margin_ratio"] = chunk["vt_symbol"].astype(str).map(margin_ratios).fillna(0.15).astype(float)
        chunk["product_vt_symbol"] = _product_from_contract_series(chunk["vt_symbol"])
        chunk["c3_margin_exact"] = (
            chunk["abs_end_pos"] * chunk["close_price"].clip(lower=0.0) * chunk["size"] * chunk["margin_ratio"]
        )
        grouped = (
            chunk.groupby(["variant", "date", "product_vt_symbol"], as_index=False)
            .agg(
                c3_margin_exact=("c3_margin_exact", "sum"),
                active_contracts=("vt_symbol", "nunique"),
                holding_pnl=("holding_pnl", "sum"),
                trading_pnl=("trading_pnl", "sum"),
                net_pnl=("net_pnl", "sum"),
            )
        )
        pieces.append(grouped)
    product = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()
    if product.empty:
        return product
    product = (
        product.groupby(["variant", "date", "product_vt_symbol"], as_index=False)
        .agg(
            c3_margin_exact=("c3_margin_exact", "sum"),
            active_contracts=("active_contracts", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            net_pnl=("net_pnl", "sum"),
        )
    )
    product["date"] = pd.to_datetime(product["date"], errors="coerce").dt.normalize()

    x_rows = events[events["xsmom_true_margin"].gt(0.0)].copy()
    if not x_rows.empty:
        x_product = pd.DataFrame(
            {
                "variant": x_rows["variant"],
                "date": x_rows["date"],
                "product_vt_symbol": "xsmom_true",
                "c3_margin_exact": x_rows["xsmom_true_margin"].astype(float),
                "active_contracts": np.nan,
                "holding_pnl": x_rows["xsmom_true_daily_pnl"].astype(float),
                "trading_pnl": 0.0,
                "net_pnl": x_rows["xsmom_true_daily_pnl"].astype(float),
            }
        )
        product = pd.concat([product, x_product], ignore_index=True, sort=False)
    return product.sort_values(["variant", "date", "c3_margin_exact"], ascending=[True, True, False]).reset_index(
        drop=True
    )


def _rank_products(events: pd.DataFrame, products: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    ranked_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    if events.empty or products.empty:
        return pd.DataFrame(), pd.DataFrame()
    event_lookup = events.set_index(["variant", "date"])
    for (variant, date), group in products.groupby(["variant", "date"], sort=False):
        if (variant, date) not in event_lookup.index:
            continue
        event = event_lookup.loc[(variant, date)]
        ordered = group.sort_values("c3_margin_exact", ascending=False).reset_index(drop=True).copy()
        total_margin = _safe_float(event["total_margin_exact"])
        equity = _safe_float(event["account_equity"])
        required = _safe_float(event["required_exact_margin_reduction"])
        ordered["rank"] = np.arange(1, len(ordered) + 1)
        ordered["cum_margin_removed"] = ordered["c3_margin_exact"].astype(float).cumsum()
        ordered["margin_share_pct"] = ordered["c3_margin_exact"].astype(float) / max(total_margin, 1.0) * 100.0
        ordered["after_remove_margin_to_equity_pct"] = (
            (total_margin - ordered["cum_margin_removed"]).clip(lower=0.0)
            * BROKER_MARGIN_MULTIPLIER
            / max(equity, 1.0)
            * 100.0
        )
        required_mask = ordered["cum_margin_removed"].ge(required)
        min_products = int(ordered.loc[required_mask, "rank"].iloc[0]) if required_mask.any() else int(len(ordered))
        top_needed = ordered[ordered["rank"].le(min_products)].copy()
        top1 = ordered.iloc[0]
        top2_ratio = (
            float(ordered.loc[ordered["rank"].eq(2), "after_remove_margin_to_equity_pct"].iloc[0])
            if len(ordered) >= 2
            else float(top1["after_remove_margin_to_equity_pct"])
        )
        top3_ratio = (
            float(ordered.loc[ordered["rank"].eq(3), "after_remove_margin_to_equity_pct"].iloc[0])
            if len(ordered) >= 3
            else float(ordered["after_remove_margin_to_equity_pct"].iloc[-1])
        )
        event_rows.append(
            {
                "variant": variant,
                "date": pd.Timestamp(date).date().isoformat(),
                "account_equity": equity,
                "drawdown_pct": _safe_float(event["drawdown_pct"]),
                "broker10_margin_to_equity_pct": _safe_float(event["broker10_margin_to_equity_pct"]),
                "total_margin_exact": total_margin,
                "required_exact_margin_reduction": required,
                "required_margin_reduction_pct_of_total": _safe_float(
                    event["required_margin_reduction_pct_of_total"]
                ),
                "active_products": int(len(ordered)),
                "min_products_to_broker10_100": min_products,
                "top1_product": str(top1["product_vt_symbol"]),
                "top1_margin_share_pct": _safe_float(top1["margin_share_pct"]),
                "after_top1_margin_to_equity_pct": _safe_float(top1["after_remove_margin_to_equity_pct"]),
                "after_top2_margin_to_equity_pct": top2_ratio,
                "after_top3_margin_to_equity_pct": top3_ratio,
                "required_removed_event_net_pnl": float(top_needed["net_pnl"].astype(float).sum()),
                "top1_event_net_pnl": _safe_float(top1["net_pnl"]),
            }
        )
        for row in ordered.itertuples(index=False):
            row_dict = row._asdict()
            row_dict.update(
                {
                    "date": pd.Timestamp(date).date().isoformat(),
                    "required_for_100pct": int(int(row_dict["rank"]) <= min_products),
                    "event_broker10_margin_to_equity_pct": _safe_float(event["broker10_margin_to_equity_pct"]),
                    "event_required_exact_margin_reduction": required,
                }
            )
            ranked_rows.append(row_dict)
    return pd.DataFrame(event_rows), pd.DataFrame(ranked_rows)


def _summarize(events: pd.DataFrame, product_rank: pd.DataFrame, source_summary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    product_rows: list[dict[str, Any]] = []
    source = source_summary.set_index("variant") if not source_summary.empty else pd.DataFrame()
    for variant in TARGET_VARIANTS:
        ev = events[events["variant"].eq(variant)].copy()
        pr = product_rank[product_rank["variant"].eq(variant)].copy()
        source_row = source.loc[variant] if variant in source.index else None
        if ev.empty:
            summary_rows.append(
                {
                    "variant": variant,
                    "over100_days": 0,
                    "max_broker10_margin_to_equity_pct": 0.0,
                    "median_event_margin_to_equity_pct": 0.0,
                    "median_required_margin_reduction_pct_of_total": 0.0,
                    "median_min_products_to_100": 0.0,
                    "one_product_enough_pct": 0.0,
                    "two_products_enough_pct": 0.0,
                    "top1_same_product_concentration_pct": 0.0,
                    "required_product_unique_count": 0,
                    "source_total_return_pct": _safe_float(getattr(source_row, "total_return_pct", 0.0)),
                    "source_max_dd_pct": _safe_float(getattr(source_row, "max_dd_pct", 0.0)),
                }
            )
            continue
        top1_concentration = (
            ev["top1_product"].value_counts(normalize=True).iloc[0] * 100.0 if not ev["top1_product"].empty else 0.0
        )
        required_unique = (
            int(pr[pr["required_for_100pct"].eq(1)]["product_vt_symbol"].nunique()) if not pr.empty else 0
        )
        summary_rows.append(
            {
                "variant": variant,
                "over100_days": int(len(ev)),
                "max_broker10_margin_to_equity_pct": float(ev["broker10_margin_to_equity_pct"].max()),
                "median_event_margin_to_equity_pct": float(ev["broker10_margin_to_equity_pct"].median()),
                "median_required_margin_reduction_pct_of_total": float(
                    ev["required_margin_reduction_pct_of_total"].median()
                ),
                "median_min_products_to_100": float(ev["min_products_to_broker10_100"].median()),
                "one_product_enough_pct": float(ev["min_products_to_broker10_100"].le(1).mean() * 100.0),
                "two_products_enough_pct": float(ev["min_products_to_broker10_100"].le(2).mean() * 100.0),
                "top1_same_product_concentration_pct": float(top1_concentration),
                "required_product_unique_count": required_unique,
                "source_total_return_pct": _safe_float(source_row["total_return_pct"] if source_row is not None else 0.0),
                "source_max_dd_pct": _safe_float(source_row["max_dd_pct"] if source_row is not None else 0.0),
            }
        )
        if not pr.empty:
            required = pr[pr["required_for_100pct"].eq(1)].copy()
            for product, group in pr.groupby("product_vt_symbol", sort=False):
                req_group = required[required["product_vt_symbol"].eq(product)]
                product_rows.append(
                    {
                        "variant": variant,
                        "product_vt_symbol": product,
                        "event_active_count": int(group["date"].nunique()),
                        "top1_count": int(group[group["rank"].eq(1)]["date"].nunique()),
                        "required_count": int(req_group["date"].nunique()),
                        "sum_event_margin_exact": float(group["c3_margin_exact"].astype(float).sum()),
                        "mean_margin_share_pct": float(group["margin_share_pct"].astype(float).mean()),
                        "sum_event_net_pnl": float(group["net_pnl"].astype(float).sum()),
                        "sum_required_event_net_pnl": float(req_group["net_pnl"].astype(float).sum())
                        if not req_group.empty
                        else 0.0,
                    }
                )
    product_agg = pd.DataFrame(product_rows)
    if not product_agg.empty:
        product_agg = product_agg.sort_values(
            ["variant", "required_count", "top1_count", "sum_event_margin_exact"],
            ascending=[True, False, False, False],
        )
    return pd.DataFrame(summary_rows), product_agg


def _plot(margin_daily: pd.DataFrame, events: pd.DataFrame, product_agg: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    ax0, ax1, ax2, ax3 = axes.flatten()
    colors = {
        "r060_legacy_nocap_control": "#2563eb",
        "r070_legacy_nocap_control": "#dc2626",
        "r070_cluster35": "#059669",
        "r070_pm_all_90_110": "#7c3aed",
    }
    for variant, group in margin_daily.groupby("variant", sort=False):
        ax0.plot(group["date"], group["broker10_margin_to_equity_pct"], label=variant, linewidth=0.9, color=colors.get(variant))
    ax0.axhline(100, color="#111827", linestyle="--", linewidth=1)
    ax0.set_title("broker10保证金/权益路径")
    ax0.set_ylabel("%")
    ax0.legend(fontsize=7)
    ax0.grid(alpha=0.25)

    if not events.empty:
        ev = events[events["variant"].eq("r070_legacy_nocap_control")]
        ax1.scatter(
            ev["required_margin_reduction_pct_of_total"],
            ev["top1_margin_share_pct"],
            s=np.maximum(ev["broker10_margin_to_equity_pct"] - 95.0, 8.0) * 5.0,
            color="#dc2626",
            alpha=0.75,
        )
        max_axis = max(
            float(ev["required_margin_reduction_pct_of_total"].max()),
            float(ev["top1_margin_share_pct"].max()),
            1.0,
        )
        ax1.plot([0, max_axis], [0, max_axis], color="#111827", linestyle="--", linewidth=1)
        ax1.set_title("r070超限日：需要削减 vs 第一大持仓")
        ax1.set_xlabel("需要削减的保证金占比")
        ax1.set_ylabel("第一大持仓保证金占比")
        ax1.grid(alpha=0.25)

    top = product_agg[product_agg["variant"].eq("r070_legacy_nocap_control")].head(10)
    if not top.empty:
        ax2.barh(top["product_vt_symbol"], top["required_count"], color="#0f766e")
        ax2.invert_yaxis()
        ax2.set_title("r070超限日 required 产品频次")
        ax2.set_xlabel("天数")
        ax2.grid(axis="x", alpha=0.25)

    top_margin = product_agg[product_agg["variant"].eq("r070_cluster35")].head(10)
    if not top_margin.empty:
        ax3.scatter(
            top_margin["sum_event_margin_exact"],
            top_margin["sum_event_net_pnl"],
            s=np.maximum(top_margin["required_count"], 1) * 22,
            color="#059669",
            alpha=0.75,
        )
        for row in top_margin.itertuples(index=False):
            ax3.annotate(str(row.product_vt_symbol), (row.sum_event_margin_exact, row.sum_event_net_pnl), fontsize=8)
        ax3.axhline(0, color="#111827", linewidth=0.8)
        ax3.set_title("r070_cluster35超限产品：保证金 vs 当日PnL")
        ax3.set_xlabel("超限日保证金合计")
        ax3.set_ylabel("超限日PnL合计")
        ax3.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _decision(summary: pd.DataFrame, product_agg: pd.DataFrame) -> dict[str, Any]:
    r070 = summary[summary["variant"].eq("r070_legacy_nocap_control")]
    cluster = summary[summary["variant"].eq("r070_cluster35")]
    r070_row = r070.iloc[0].to_dict() if not r070.empty else {}
    cluster_row = cluster.iloc[0].to_dict() if not cluster.empty else {}
    surgical_possible = bool(
        _safe_float(r070_row.get("two_products_enough_pct", 0.0)) >= 70.0
        and _safe_float(r070_row.get("top1_same_product_concentration_pct", 0.0)) >= 40.0
        and _safe_float(r070_row.get("required_product_unique_count", 99.0)) <= 8.0
    )
    top_required = product_agg[
        product_agg["variant"].eq("r070_legacy_nocap_control") & product_agg["required_count"].gt(0)
    ].head(8)
    return {
        "decision": "targeted_margin_postmortem_promising" if surgical_possible else "targeted_margin_postmortem_not_surgical_enough",
        "surgical_possible_by_r070_event_shape": surgical_possible,
        "r070_over100_days": int(_safe_float(r070_row.get("over100_days", 0))),
        "r070_two_products_enough_pct": _safe_float(r070_row.get("two_products_enough_pct", 0.0)),
        "r070_top1_concentration_pct": _safe_float(r070_row.get("top1_same_product_concentration_pct", 0.0)),
        "r070_required_unique_count": int(_safe_float(r070_row.get("required_product_unique_count", 0))),
        "r070_cluster35_over100_days": int(_safe_float(cluster_row.get("over100_days", 0))),
        "r070_cluster35_two_products_enough_pct": _safe_float(cluster_row.get("two_products_enough_pct", 0.0)),
        "top_required_products_r070": top_required.to_dict(orient="records"),
        "next_step": (
            "If event shape is concentrated, test a predeclared product-margin entry veto on the recurring high-margin products; "
            "otherwise stop product blacklist-style rescue and move to independent low-margin alpha."
        ),
    }


def _write_report(summary: pd.DataFrame, events: pd.DataFrame, product_agg: pd.DataFrame, decision: dict[str, Any]) -> None:
    r070_events = events[events["variant"].eq("r070_legacy_nocap_control")].sort_values(
        "broker10_margin_to_equity_pct", ascending=False
    )
    r070_products = product_agg[product_agg["variant"].eq("r070_legacy_nocap_control")]
    cluster_products = product_agg[product_agg["variant"].eq("r070_cluster35")]
    lines = [
        "# Stage518 保证金超限日持仓贡献审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 数据来源：Stage517 exact position margin 输出；broker multiplier=`{BROKER_MARGIN_MULTIPLIER:.2f}`。",
        "- 阶段性质：只读归因，不修改交易规则，不按坏日期调参。",
        f"- 决策：`{decision['decision']}`。",
        "",
        "## 调研判断",
        "",
        "- Managed futures 的分散价值来自低相关收益源，但相关性会随市场状态变化；因此本阶段不把低相关口号当成结论，而是回到真实持仓保证金贡献。",
        "- 期货保证金是清算/券商风险管理约束，组合或价差抵扣要有真实制度支持；本线当前以 exact position margin 加 broker10 上浮作为硬闸门。",
        "- GitHub/vn.py 资料显示组合策略和价差策略可以工程化，但公开框架不会替我们解决本账户的整数手、真实窗口、保证金上浮和现金约束，所以必须做本地持仓级审计。",
        "",
        "## 总览",
        "",
        _md_table(summary),
        "",
        "## r070 legacy 超限日",
        "",
        _md_table(
            r070_events[
                [
                    "date",
                    "broker10_margin_to_equity_pct",
                    "drawdown_pct",
                    "required_margin_reduction_pct_of_total",
                    "active_products",
                    "min_products_to_broker10_100",
                    "top1_product",
                    "top1_margin_share_pct",
                    "after_top1_margin_to_equity_pct",
                    "after_top2_margin_to_equity_pct",
                ]
            ],
            max_rows=12,
        ),
        "",
        "## r070 legacy 产品聚合",
        "",
        _md_table(
            r070_products[
                [
                    "product_vt_symbol",
                    "event_active_count",
                    "top1_count",
                    "required_count",
                    "mean_margin_share_pct",
                    "sum_event_net_pnl",
                    "sum_required_event_net_pnl",
                ]
            ],
            max_rows=12,
        ),
        "",
        "## r070_cluster35 剩余超限产品",
        "",
        _md_table(
            cluster_products[
                [
                    "product_vt_symbol",
                    "event_active_count",
                    "top1_count",
                    "required_count",
                    "mean_margin_share_pct",
                    "sum_event_net_pnl",
                    "sum_required_event_net_pnl",
                ]
            ],
            max_rows=12,
        ),
        "",
        "## 结论",
        "",
        "- 如果 `r070` 超限主要由少数固定产品贡献，下一步才值得做预声明的产品保证金入场 veto；如果贡献分散或削掉的是主要赚钱腿，则不应做产品黑名单式救援。",
        "- 本阶段仍是归因，不证明任何新版本可部署；任何后续规则都必须先预声明，再全周期、多起点、2x成本和 exact margin 复验。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    margin_daily = _load_margin_daily()
    source_summary = pd.read_csv(SUMMARY_IN, encoding="utf-8-sig") if SUMMARY_IN.exists() else pd.DataFrame()
    events_raw = _event_days(margin_daily)
    products = _load_event_product_margin(events_raw)
    events, product_rank = _rank_products(events_raw, products)
    summary, product_agg = _summarize(events, product_rank, source_summary)
    decision = _decision(summary, product_agg)
    _plot(margin_daily, events, product_agg)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    events.to_csv(EVENT_PATH, index=False, encoding="utf-8-sig")
    product_rank.to_csv(PRODUCT_PATH, index=False, encoding="utf-8-sig")
    product_agg.to_csv(PRODUCT_AGG_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, events, product_agg, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
