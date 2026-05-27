from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage324_true_combo_capital_margin import (
    TOTAL_CAPITAL,
    _path_metrics,
    _to_builtin,
    _to_markdown_table,
)
from analyze_qmt_roll_stage328_c3_single_path_loss_attribution import (
    _drawdown_window,
    _product_from_vt_symbol,
    _run_c3,
)
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_ROLE, OFFICIAL_STAGE78_VERSION
from qmt_universe import END_DT, START_DT
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage360_c3_product_group_ledger_ablation_v1"
OUTPUT_PREFIX = "qmt_roll_stage360_c3_product_group_ledger_ablation"
LINE_ID = "futures_trend_drawdown30_preserve_return"


@dataclass(frozen=True)
class Window:
    name: str
    label: str
    start: datetime
    end: datetime


WINDOWS: tuple[Window, ...] = (
    Window("full_2020_2026", "2020起点至今", START_DT, END_DT),
)


PRODUCT_GROUPS: dict[str, tuple[str, ...]] = {
    "黑色建材链": ("hc.SHFE", "rb.SHFE", "jm.DCE", "FG.CZCE", "SM.CZCE", "SA.CZCE"),
    "能化工业链": ("MA.CZCE", "fu.SHFE", "sp.SHFE", "ru.SHFE", "OI.CZCE", "SH.CZCE"),
    "农产品软商品": ("AP.CZCE", "CF.CZCE", "lh.DCE"),
    "金属贵金属": ("au.SHFE", "cu.SHFE", "si.GFEX", "lc.GFEX"),
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _prepare_position_product_daily(positions: pd.DataFrame) -> pd.DataFrame:
    if positions.empty:
        return pd.DataFrame(columns=["date", "product_vt_symbol", "net_pnl", "trade_count", "slippage"])
    frame = positions.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["product_vt_symbol"] = frame["vt_symbol"].map(_product_from_vt_symbol)
    for column in ("net_pnl", "trade_count", "slippage"):
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return (
        frame.groupby(["date", "product_vt_symbol"], as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            trade_count=("trade_count", "sum"),
            slippage=("slippage", "sum"),
        )
        .sort_values(["date", "product_vt_symbol"])
        .reset_index(drop=True)
    )


def _contribution_frame(
    base_daily: pd.DataFrame,
    product_daily: pd.DataFrame,
    *,
    products: tuple[str, ...],
    label: str,
) -> pd.DataFrame:
    dates = base_daily[["date"]].copy()
    part = product_daily[product_daily["product_vt_symbol"].isin(products)].copy()
    if part.empty:
        contrib = pd.DataFrame(columns=["date", "removed_net_pnl", "removed_trade_count", "removed_slippage"])
    else:
        contrib = (
            part.groupby("date", as_index=False)
            .agg(
                removed_net_pnl=("net_pnl", "sum"),
                removed_trade_count=("trade_count", "sum"),
                removed_slippage=("slippage", "sum"),
            )
            .sort_values("date")
            .reset_index(drop=True)
        )
    merged = dates.merge(contrib, on="date", how="left")
    for column in ("removed_net_pnl", "removed_trade_count", "removed_slippage"):
        merged[column] = pd.to_numeric(merged.get(column, 0.0), errors="coerce").fillna(0.0)
    merged["variant"] = label
    merged["removed_products"] = ",".join(products)
    return merged


def _variant_daily(base_daily: pd.DataFrame, contribution: pd.DataFrame, variant: str) -> pd.DataFrame:
    frame = base_daily[["date", "net_pnl", "trade_count", "slippage"]].copy()
    frame = frame.merge(
        contribution[["date", "removed_net_pnl", "removed_trade_count", "removed_slippage"]],
        on="date",
        how="left",
    )
    for column in ("removed_net_pnl", "removed_trade_count", "removed_slippage"):
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    frame["variant"] = variant
    frame["ledger_net_pnl"] = frame["net_pnl"] - frame["removed_net_pnl"]
    frame["ledger_trade_count"] = (frame["trade_count"] - frame["removed_trade_count"]).clip(lower=0.0)
    frame["ledger_slippage"] = (frame["slippage"] - frame["removed_slippage"]).clip(lower=0.0)
    frame["balance"] = TOTAL_CAPITAL + frame["ledger_net_pnl"].cumsum()
    return frame


def _slice_metrics(daily: pd.DataFrame, window: Window) -> dict[str, Any]:
    frame = daily[(daily["date"] >= pd.Timestamp(window.start)) & (daily["date"] <= pd.Timestamp(window.end))].copy()
    if frame.empty:
        metrics = _path_metrics(pd.DataFrame(columns=["balance"]), TOTAL_CAPITAL)
        return {
            "window_name": window.name,
            "window_label": window.label,
            **metrics,
            "trade_count": 0.0,
            "slippage": 0.0,
            "net_pnl": 0.0,
        }
    frame["balance"] = TOTAL_CAPITAL + pd.to_numeric(frame["ledger_net_pnl"], errors="coerce").fillna(0.0).cumsum()
    metrics = _path_metrics(frame[["date", "balance"]], TOTAL_CAPITAL)
    return {
        "window_name": window.name,
        "window_label": window.label,
        **metrics,
        "trade_count": float(pd.to_numeric(frame["ledger_trade_count"], errors="coerce").fillna(0.0).sum()),
        "slippage": float(pd.to_numeric(frame["ledger_slippage"], errors="coerce").fillna(0.0).sum()),
        "net_pnl": float(pd.to_numeric(frame["ledger_net_pnl"], errors="coerce").fillna(0.0).sum()),
    }


def _baseline_daily_from_run(daily: pd.DataFrame) -> pd.DataFrame:
    frame = daily[["date", "balance", "net_pnl", "trade_count", "slippage"]].copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    for column in ("balance", "net_pnl", "trade_count", "slippage"):
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame.sort_values("date").reset_index(drop=True)


def _build_variants(base_daily: pd.DataFrame, product_daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    variants: list[pd.DataFrame] = []
    variant_meta: list[dict[str, Any]] = []

    baseline = base_daily[["date", "net_pnl", "trade_count", "slippage"]].copy()
    baseline["variant"] = "baseline_c3"
    baseline["ledger_net_pnl"] = baseline["net_pnl"]
    baseline["ledger_trade_count"] = baseline["trade_count"]
    baseline["ledger_slippage"] = baseline["slippage"]
    baseline["balance"] = TOTAL_CAPITAL + baseline["ledger_net_pnl"].cumsum()
    variants.append(baseline)
    variant_meta.append(
        {
            "variant": "baseline_c3",
            "variant_type": "baseline",
            "removed_products": "",
            "description": "C3原始账本",
        }
    )

    products = tuple(sorted(product_daily["product_vt_symbol"].astype(str).unique()))
    for product in products:
        label = f"remove_product:{product}"
        contrib = _contribution_frame(base_daily, product_daily, products=(product,), label=label)
        variants.append(_variant_daily(base_daily, contrib, label))
        variant_meta.append(
            {
                "variant": label,
                "variant_type": "leave_one_product",
                "removed_products": product,
                "description": f"账本反事实：移除{product}",
            }
        )

    for group_name, group_products in PRODUCT_GROUPS.items():
        actual_products = tuple(product for product in group_products if product in products)
        if not actual_products:
            continue
        label = f"remove_group:{group_name}"
        contrib = _contribution_frame(base_daily, product_daily, products=actual_products, label=label)
        variants.append(_variant_daily(base_daily, contrib, label))
        variant_meta.append(
            {
                "variant": label,
                "variant_type": "predeclared_group",
                "removed_products": ",".join(actual_products),
                "description": f"账本反事实：移除预声明{group_name}",
            }
        )

    return pd.concat(variants, ignore_index=True), pd.DataFrame(variant_meta)


def _summarize_variants(variant_daily: pd.DataFrame, variant_meta: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    baseline_by_window: dict[str, dict[str, Any]] = {}

    for variant, group in variant_daily.groupby("variant", sort=False):
        for window in WINDOWS:
            metrics = _slice_metrics(group, window)
            row = {"variant": variant, **metrics}
            rows.append(row)
            if variant == "baseline_c3":
                baseline_by_window[window.name] = metrics

    summary = pd.DataFrame(rows)
    summary = summary.merge(variant_meta, on="variant", how="left")
    summary["baseline_return_pct"] = summary["window_name"].map(
        {name: data["total_return_pct"] for name, data in baseline_by_window.items()}
    )
    summary["baseline_max_dd_percent"] = summary["window_name"].map(
        {name: data["max_dd_percent"] for name, data in baseline_by_window.items()}
    )
    summary["return_retention_pct"] = np.where(
        summary["baseline_return_pct"].abs() > 1e-12,
        summary["total_return_pct"] / summary["baseline_return_pct"] * 100.0,
        np.nan,
    )
    summary["drawdown_improvement_pp"] = summary["max_dd_percent"] - summary["baseline_max_dd_percent"]
    summary["window_gate_ok"] = (
        summary["max_dd_percent"].ge(-30.0)
        & (summary["return_retention_pct"].ge(80.0) | summary["variant"].eq("baseline_c3"))
    ).astype(int)
    return summary


def _candidate_frontier(summary: pd.DataFrame) -> pd.DataFrame:
    non_base = summary[~summary["variant"].eq("baseline_c3")].copy()
    if non_base.empty:
        return pd.DataFrame()
    grouped = (
        non_base.groupby(["variant", "variant_type", "description", "removed_products"], as_index=False)
        .agg(
            full_return_pct=("total_return_pct", lambda s: float(s[non_base.loc[s.index, "window_name"].eq("full_2020_2026")].iloc[0]) if any(non_base.loc[s.index, "window_name"].eq("full_2020_2026")) else np.nan),
            full_max_dd_percent=("max_dd_percent", lambda s: float(s[non_base.loc[s.index, "window_name"].eq("full_2020_2026")].iloc[0]) if any(non_base.loc[s.index, "window_name"].eq("full_2020_2026")) else np.nan),
            full_return_retention_pct=("return_retention_pct", lambda s: float(s[non_base.loc[s.index, "window_name"].eq("full_2020_2026")].iloc[0]) if any(non_base.loc[s.index, "window_name"].eq("full_2020_2026")) else np.nan),
            min_return_retention_pct=("return_retention_pct", "min"),
            worst_max_dd_percent=("max_dd_percent", "min"),
            passed_window_count=("window_gate_ok", "sum"),
            window_count=("window_gate_ok", "count"),
        )
    )
    grouped["all_windows_gate_ok"] = grouped["passed_window_count"].eq(grouped["window_count"]).astype(int)
    grouped["diagnostic_rank"] = (
        grouped["all_windows_gate_ok"] * 10_000
        + grouped["full_max_dd_percent"].clip(lower=-100, upper=0) * 100
        + grouped["min_return_retention_pct"].fillna(-999)
    )
    return grouped.sort_values(
        ["all_windows_gate_ok", "full_max_dd_percent", "min_return_retention_pct"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def _product_contribution(product_daily: pd.DataFrame, drawdown: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    if product_daily.empty:
        return pd.DataFrame(), pd.DataFrame()
    full = (
        product_daily.groupby("product_vt_symbol", as_index=False)
        .agg(
            full_net_pnl=("net_pnl", "sum"),
            full_trade_count=("trade_count", "sum"),
            full_slippage=("slippage", "sum"),
            active_days=("net_pnl", lambda s: int((s.abs() > 1e-9).sum())),
        )
        .sort_values("full_net_pnl")
        .reset_index(drop=True)
    )
    peak = pd.Timestamp(drawdown["peak_date"]).normalize()
    trough = pd.Timestamp(drawdown["trough_date"]).normalize()
    window = product_daily[(product_daily["date"] > peak) & (product_daily["date"] <= trough)].copy()
    dd = (
        window.groupby("product_vt_symbol", as_index=False)
        .agg(
            dd_window_net_pnl=("net_pnl", "sum"),
            dd_window_trade_count=("trade_count", "sum"),
            dd_window_slippage=("slippage", "sum"),
        )
        .sort_values("dd_window_net_pnl")
        .reset_index(drop=True)
    )
    return full, dd


def _build_report(
    baseline_stats: dict[str, Any],
    drawdown: dict[str, Any],
    summary: pd.DataFrame,
    frontier: pd.DataFrame,
    product_full: pd.DataFrame,
    product_dd: pd.DataFrame,
    decision: dict[str, Any],
    paths: dict[str, Path],
) -> str:
    full_summary = summary[summary["window_name"].eq("full_2020_2026")].copy()
    full_summary = full_summary.sort_values(
        ["window_gate_ok", "max_dd_percent", "return_retention_pct"],
        ascending=[False, False, False],
    )
    group_frontier = frontier[frontier["variant_type"].eq("predeclared_group")].copy()
    product_frontier = frontier[frontier["variant_type"].eq("leave_one_product")].copy()
    lines = [
        "# Stage060 C3产品/产业簇账本反事实诊断",
        "",
        "## 定位",
        "",
        "- 本阶段是诊断侦察，不修改正式78-1/C3交易引擎，不产生可直接实盘版本。",
        "- 目标是判断 C3 剩余 `-31%` 左右回撤，是否由稳定的产品或产业簇暴露造成。",
        "- 反过拟合约束：单品种 leave-one 只用于归因，不允许直接变成黑名单；预声明产业簇若过线，也必须进入真实引擎多周期复验。",
        "- 口径约束：本阶段只使用全样本账本反事实，不把账本中途切片当成独立冷启动回测；多周期必须另跑真实引擎。",
        "",
        "## 外部调研判断",
        "",
        "- 趋势跟随长期有效性通常来自跨市场分散，但趋势策略真正的组合风险不是普通相关性，而是多个市场同时押注同一趋势来源。",
        "- 因此本阶段采用横截面/产业簇暴露诊断，而不是继续调供需阈值、现金比例或单笔风险上限。",
        "",
        "## C3基准",
        "",
        f"- 期末权益：`{_safe_float(baseline_stats.get('end_balance')):,.0f}`",
        f"- 总收益：`{_safe_float(baseline_stats.get('total_return')):.4f}%`",
        f"- 最大回撤：`{_safe_float(baseline_stats.get('max_ddpercent')):.4f}%`",
        f"- Sharpe：`{_safe_float(baseline_stats.get('sharpe_ratio')):.4f}`",
        f"- 总滑点：`{_safe_float(baseline_stats.get('total_slippage')):,.0f}`",
        f"- 总交易次数：`{_safe_float(baseline_stats.get('total_trade_count')):,.0f}`",
        f"- 胜率：`{_safe_float(baseline_stats.get('win_ratio')):.4f}%`",
        "",
        "## 最大回撤窗口",
        "",
        f"- 高点：`{pd.Timestamp(drawdown['peak_date']).date()}`，权益 `{drawdown['peak_balance']:,.2f}`",
        f"- 低点：`{pd.Timestamp(drawdown['trough_date']).date()}`，权益 `{drawdown['trough_balance']:,.2f}`",
        f"- 最大回撤：`{drawdown['max_dd_percent']:.4f}%`",
        "",
        "## 全样本反事实前沿",
        "",
        _to_markdown_table(
            full_summary.head(20),
            [
                "variant",
                "variant_type",
                "total_return_pct",
                "return_retention_pct",
                "max_dd_percent",
                "drawdown_improvement_pp",
                "sharpe_ratio",
                "window_gate_ok",
            ],
            max_rows=20,
        ),
        "",
        "## 预声明产业簇前沿",
        "",
        _to_markdown_table(
            group_frontier,
            [
                "variant",
                "removed_products",
                "full_return_retention_pct",
                "full_max_dd_percent",
                "passed_window_count",
                "window_count",
                "all_windows_gate_ok",
            ],
            max_rows=20,
        ),
        "",
        "## 单品种 leave-one 诊断",
        "",
        _to_markdown_table(
            product_frontier.head(20),
            [
                "variant",
                "full_return_retention_pct",
                "full_max_dd_percent",
                "passed_window_count",
                "window_count",
            ],
            max_rows=20,
        ),
        "",
        "## 产品全样本贡献",
        "",
        _to_markdown_table(product_full.head(20), product_full.columns.tolist(), max_rows=20),
        "",
        "## 最大回撤窗口产品贡献",
        "",
        _to_markdown_table(product_dd.head(20), product_dd.columns.tolist(), max_rows=20),
        "",
        "## 结论",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 通过全样本账本闸门的预声明产业簇数量：`{decision['passed_predeclared_group_count']}`。",
        f"- 通过全样本账本闸门的单品种诊断数量：`{decision['passed_leave_one_product_count']}`。",
        "- 若只有单品种诊断好看，不晋级，因为这会变成后验黑名单。",
        "- 若预声明产业簇也不能通过，说明产品/产业簇删减不是当前最优主路径。",
        "",
        "## 输出",
        "",
        f"- summary：`{paths['summary'].name}`",
        f"- frontier：`{paths['frontier'].name}`",
        f"- product_full：`{paths['product_full'].name}`",
        f"- product_dd：`{paths['product_dd'].name}`",
        f"- decision：`{paths['decision'].name}`",
        "",
        "## 反思",
        "",
        "- 是否过拟合：本阶段本身不是过拟合，因为它只做预声明分组和全品种 leave-one 诊断；但把结果直接转成单品种黑名单会过拟合。",
        "- 是否还有价值继续：有。若诊断不过线，可以明确停止产品删减路线；若预声明产业簇过线，再做真实引擎复验。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    daily, positions, _trades, _candidates, _risks, statistics = _run_c3()
    base_daily = _baseline_daily_from_run(daily)
    product_daily = _prepare_position_product_daily(positions)
    drawdown = _drawdown_window(base_daily)
    variant_daily, variant_meta = _build_variants(base_daily, product_daily)
    summary = _summarize_variants(variant_daily, variant_meta)
    frontier = _candidate_frontier(summary)
    product_full, product_dd = _product_contribution(product_daily, drawdown)

    passed_groups = frontier[
        frontier["variant_type"].eq("predeclared_group") & frontier["all_windows_gate_ok"].eq(1)
    ].copy()
    passed_products = frontier[
        frontier["variant_type"].eq("leave_one_product") & frontier["all_windows_gate_ok"].eq(1)
    ].copy()
    if not passed_groups.empty:
        decision_label = "predeclared_group_candidate_requires_true_engine"
    elif not passed_products.empty:
        decision_label = "leave_one_product_only_diagnostic_do_not_blacklist"
    else:
        decision_label = "no_product_group_ledger_candidate"

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "decision": decision_label,
        "passed_predeclared_group_count": int(len(passed_groups)),
        "passed_leave_one_product_count": int(len(passed_products)),
        "baseline": {
            "end_balance": _safe_float(statistics.get("end_balance")),
            "total_return_pct": _safe_float(statistics.get("total_return")),
            "max_dd_percent": _safe_float(statistics.get("max_ddpercent")),
            "sharpe_ratio": _safe_float(statistics.get("sharpe_ratio")),
            "total_slippage": _safe_float(statistics.get("total_slippage")),
            "total_trade_count": int(_safe_float(statistics.get("total_trade_count"))),
            "win_ratio_pct": _safe_float(statistics.get("win_ratio")),
        },
        "drawdown": {key: _to_builtin(value) for key, value in drawdown.items() if key != "curve"},
        "overfit_guard": {
            "leave_one_product_is_diagnostic_only": True,
            "predeclared_groups": PRODUCT_GROUPS,
            "ledger_counterfactual_requires_true_engine_before_promotion": True,
        },
    }

    paths = {
        "variant_daily": OUTPUT_DIR / f"{OUTPUT_PREFIX}_variant_daily_{MODEL_TAG}.csv",
        "summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv",
        "frontier": OUTPUT_DIR / f"{OUTPUT_PREFIX}_frontier_{MODEL_TAG}.csv",
        "product_daily": OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_daily_{MODEL_TAG}.csv",
        "product_full": OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_full_{MODEL_TAG}.csv",
        "product_dd": OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_dd_{MODEL_TAG}.csv",
        "report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md",
        "decision": OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json",
    }

    variant_daily.to_csv(paths["variant_daily"], index=False, encoding="utf-8-sig")
    summary.to_csv(paths["summary"], index=False, encoding="utf-8-sig")
    frontier.to_csv(paths["frontier"], index=False, encoding="utf-8-sig")
    product_daily.to_csv(paths["product_daily"], index=False, encoding="utf-8-sig")
    product_full.to_csv(paths["product_full"], index=False, encoding="utf-8-sig")
    product_dd.to_csv(paths["product_dd"], index=False, encoding="utf-8-sig")
    paths["decision"].write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    paths["report"].write_text(
        _build_report(statistics, drawdown, summary, frontier, product_full, product_dd, decision, paths),
        encoding="utf-8",
    )

    print(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2))
    print(f"[stage360] report: {paths['report']}")


if __name__ == "__main__":
    main()
