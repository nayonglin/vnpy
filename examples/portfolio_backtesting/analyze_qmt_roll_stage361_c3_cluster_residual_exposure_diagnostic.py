from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage324_true_combo_capital_margin import (
    TOTAL_CAPITAL,
    _to_builtin,
    _to_markdown_table,
)
from analyze_qmt_roll_stage328_c3_single_path_loss_attribution import (
    _drawdown_window,
    _product_from_vt_symbol,
    _run_c3,
)
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_ROLE, OFFICIAL_STAGE78_VERSION
from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_stage298_stage78_1_risk_cluster_cap import RISK_CLUSTER_MAP


MODEL_TAG = "stage361_c3_cluster_residual_exposure_diagnostic_v1"
OUTPUT_PREFIX = "qmt_roll_stage361_c3_cluster_residual_exposure_diagnostic"
LINE_ID = "futures_trend_drawdown30_preserve_return"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _parse_cluster_map(raw: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in str(raw or "").split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and value:
            mapping[key] = value
            if "." in key:
                symbol, exchange = key.split(".", 1)
                mapping[f"{symbol.lower()}.{exchange.upper()}"] = value
                mapping[f"{symbol.upper()}.{exchange.upper()}"] = value
    return mapping


CLUSTER_MAP = _parse_cluster_map(RISK_CLUSTER_MAP)


def _cluster_for_product(product_vt_symbol: str) -> str:
    raw = str(product_vt_symbol or "")
    keys = [raw]
    if "." in raw:
        symbol, exchange = raw.split(".", 1)
        keys.extend([f"{symbol.lower()}.{exchange.upper()}", f"{symbol.upper()}.{exchange.upper()}"])
    for key in keys:
        cluster = CLUSTER_MAP.get(key)
        if cluster:
            return cluster
    return "未分组"


def _prepare_positions(positions: pd.DataFrame) -> pd.DataFrame:
    if positions.empty:
        return pd.DataFrame()
    frame = positions.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["product_vt_symbol"] = frame["vt_symbol"].map(_product_from_vt_symbol)
    frame["risk_cluster"] = frame["product_vt_symbol"].map(_cluster_for_product)
    for column in ("start_pos", "end_pos", "net_pnl", "trade_count", "slippage", "holding_pnl", "trading_pnl"):
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    frame["active_position_flag"] = (
        frame["start_pos"].abs().gt(1e-9) | frame["end_pos"].abs().gt(1e-9) | frame["trade_count"].gt(0)
    ).astype(int)
    frame["direction_sign"] = np.where(
        frame["end_pos"].abs().gt(1e-9),
        np.sign(frame["end_pos"]),
        np.sign(frame["start_pos"]),
    )
    frame["direction_label"] = np.where(
        frame["direction_sign"].gt(0),
        "long",
        np.where(frame["direction_sign"].lt(0), "short", "flat"),
    )
    return frame


def _cluster_daily(positions: pd.DataFrame) -> pd.DataFrame:
    if positions.empty:
        return pd.DataFrame()
    active = positions[positions["active_position_flag"].eq(1)].copy()
    if active.empty:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for (date, cluster), group in active.groupby(["date", "risk_cluster"], sort=True):
        products = sorted(group["product_vt_symbol"].astype(str).unique())
        long_products = sorted(group.loc[group["direction_sign"].gt(0), "product_vt_symbol"].astype(str).unique())
        short_products = sorted(group.loc[group["direction_sign"].lt(0), "product_vt_symbol"].astype(str).unique())
        rows.append(
            {
                "date": pd.Timestamp(date),
                "risk_cluster": str(cluster),
                "net_pnl": float(group["net_pnl"].sum()),
                "holding_pnl": float(group["holding_pnl"].sum()),
                "trading_pnl": float(group["trading_pnl"].sum()),
                "trade_count": float(group["trade_count"].sum()),
                "slippage": float(group["slippage"].sum()),
                "active_product_count": int(len(products)),
                "active_contract_count": int(group["vt_symbol"].astype(str).nunique()),
                "long_product_count": int(len(long_products)),
                "short_product_count": int(len(short_products)),
                "mixed_direction_flag": int(bool(long_products and short_products)),
                "same_direction_multi_flag": int(len(products) >= 2 and not (long_products and short_products)),
                "products": ",".join(products),
            }
        )
    result = pd.DataFrame(rows).sort_values(["date", "risk_cluster"]).reset_index(drop=True)
    result["exposure_bucket"] = np.where(result["active_product_count"].ge(2), "multi_product", "single_product")
    return result


def _drawdown_slice(frame: pd.DataFrame, drawdown: dict[str, Any]) -> pd.DataFrame:
    peak = pd.Timestamp(drawdown["peak_date"]).normalize()
    trough = pd.Timestamp(drawdown["trough_date"]).normalize()
    return frame[(frame["date"] > peak) & (frame["date"] <= trough)].copy()


def _cluster_summary(cluster_daily: pd.DataFrame, drawdown: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    if cluster_daily.empty:
        return pd.DataFrame(), pd.DataFrame()
    dd = _drawdown_slice(cluster_daily, drawdown)
    grouped = (
        dd.groupby("risk_cluster", as_index=False)
        .agg(
            dd_window_net_pnl=("net_pnl", "sum"),
            dd_window_holding_pnl=("holding_pnl", "sum"),
            dd_window_trading_pnl=("trading_pnl", "sum"),
            dd_window_trade_count=("trade_count", "sum"),
            dd_window_slippage=("slippage", "sum"),
            active_days=("date", "count"),
            max_active_product_count=("active_product_count", "max"),
            multi_product_days=("active_product_count", lambda s: int((s >= 2).sum())),
            same_direction_multi_days=("same_direction_multi_flag", "sum"),
            mixed_direction_days=("mixed_direction_flag", "sum"),
        )
        .sort_values("dd_window_net_pnl")
        .reset_index(drop=True)
    )

    bucket = (
        dd.groupby(["risk_cluster", "exposure_bucket"], as_index=False)
        .agg(
            bucket_net_pnl=("net_pnl", "sum"),
            bucket_days=("date", "count"),
            bucket_trade_count=("trade_count", "sum"),
            bucket_slippage=("slippage", "sum"),
        )
        .sort_values(["risk_cluster", "exposure_bucket"])
        .reset_index(drop=True)
    )
    return grouped, bucket


def _portfolio_exposure_daily(cluster_daily: pd.DataFrame) -> pd.DataFrame:
    if cluster_daily.empty:
        return pd.DataFrame()
    rows = (
        cluster_daily.groupby("date", as_index=False)
        .agg(
            active_cluster_count=("risk_cluster", "nunique"),
            active_product_count=("active_product_count", "sum"),
            multi_product_cluster_count=("active_product_count", lambda s: int((s >= 2).sum())),
            same_direction_multi_cluster_count=("same_direction_multi_flag", "sum"),
            mixed_direction_cluster_count=("mixed_direction_flag", "sum"),
            net_pnl=("net_pnl", "sum"),
        )
        .sort_values("date")
        .reset_index(drop=True)
    )
    return rows


def _heat_deleverage_events(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty or "exit_reason" not in trades.columns:
        return pd.DataFrame()
    frame = trades.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["exit_reason"] = frame["exit_reason"].fillna("").astype(str)
    frame = frame[frame["exit_reason"].str.contains("risk_cluster_heat_deleverage", regex=False)].copy()
    if frame.empty:
        return pd.DataFrame()
    frame["product_vt_symbol"] = frame["vt_symbol"].map(_product_from_vt_symbol)
    frame["risk_cluster"] = frame["product_vt_symbol"].map(_cluster_for_product)
    for column in ("volume", "price"):
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return (
        frame.groupby(["date", "risk_cluster", "product_vt_symbol", "exit_reason"], as_index=False)
        .agg(
            close_volume=("volume", "sum"),
            trade_count=("trade_id", "count"),
            avg_price=("price", "mean"),
        )
        .sort_values(["date", "risk_cluster", "product_vt_symbol"])
        .reset_index(drop=True)
    )


def _decision(
    baseline_stats: dict[str, Any],
    drawdown: dict[str, Any],
    cluster_dd: pd.DataFrame,
    bucket_dd: pd.DataFrame,
    heat_events: pd.DataFrame,
) -> dict[str, Any]:
    dd_loss = max(1e-9, float(drawdown["peak_balance"]) - float(drawdown["trough_balance"]))
    negative_clusters = cluster_dd[cluster_dd["dd_window_net_pnl"].lt(0)].copy()
    multi_bucket = bucket_dd[
        bucket_dd["exposure_bucket"].eq("multi_product") & bucket_dd["bucket_net_pnl"].lt(0)
    ].copy()
    multi_loss = float(-multi_bucket["bucket_net_pnl"].sum()) if not multi_bucket.empty else 0.0
    top_cluster = negative_clusters.iloc[0].to_dict() if not negative_clusters.empty else {}
    heat_dd = _drawdown_slice(heat_events, drawdown) if not heat_events.empty else pd.DataFrame()
    heat_close_count = int(heat_dd["trade_count"].sum()) if not heat_dd.empty else 0
    multi_loss_share = multi_loss / dd_loss * 100.0
    top_cluster_loss_share = (
        max(0.0, -_safe_float(top_cluster.get("dd_window_net_pnl"))) / dd_loss * 100.0 if top_cluster else 0.0
    )

    if multi_loss_share >= 50.0 and heat_close_count == 0:
        decision_label = "cluster_duplicate_compression_candidate_requires_engine"
    elif multi_loss_share >= 50.0:
        decision_label = "cluster_duplicate_compression_diagnostic_supported_but_heat_delev_already_active"
    else:
        decision_label = "residual_drawdown_not_mainly_multi_product_cluster_exposure"

    return {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "baseline": {
            "end_balance": _safe_float(baseline_stats.get("end_balance")),
            "total_return_pct": _safe_float(baseline_stats.get("total_return")),
            "max_dd_percent": _safe_float(baseline_stats.get("max_ddpercent")),
            "sharpe_ratio": _safe_float(baseline_stats.get("sharpe_ratio")),
            "total_slippage": _safe_float(baseline_stats.get("total_slippage")),
            "total_trade_count": int(_safe_float(baseline_stats.get("total_trade_count"))),
            "win_ratio_pct": _safe_float(baseline_stats.get("win_ratio")),
        },
        "drawdown": {key: _to_builtin(value) for key, value in drawdown.items() if key != "curve"},
        "decision": decision_label,
        "dd_loss_amount": dd_loss,
        "multi_product_cluster_loss_amount": multi_loss,
        "multi_product_cluster_loss_share_of_dd_pct": multi_loss_share,
        "top_loss_cluster": top_cluster.get("risk_cluster", ""),
        "top_loss_cluster_share_of_dd_pct": top_cluster_loss_share,
        "heat_deleverage_close_count_in_dd_window": heat_close_count,
        "overfit_guard": {
            "diagnostic_only": True,
            "does_not_change_engine": True,
            "no_product_blacklist": True,
            "no_threshold_search": True,
        },
    }


def _build_report(
    baseline_stats: dict[str, Any],
    drawdown: dict[str, Any],
    cluster_dd: pd.DataFrame,
    bucket_dd: pd.DataFrame,
    exposure_daily: pd.DataFrame,
    heat_events: pd.DataFrame,
    decision: dict[str, Any],
    paths: dict[str, Path],
) -> str:
    peak = pd.Timestamp(drawdown["peak_date"]).normalize()
    trough = pd.Timestamp(drawdown["trough_date"]).normalize()
    exposure_dd = _drawdown_slice(exposure_daily, drawdown)
    heat_dd = _drawdown_slice(heat_events, drawdown) if not heat_events.empty else pd.DataFrame()
    exposure_summary = pd.DataFrame(
        [
            {
                "窗口": "最大回撤窗口",
                "起点后": str(peak.date()),
                "终点": str(trough.date()),
                "天数": int(len(exposure_dd)),
                "平均活跃品种数": float(exposure_dd["active_product_count"].mean()) if not exposure_dd.empty else 0.0,
                "最大活跃品种数": int(exposure_dd["active_product_count"].max()) if not exposure_dd.empty else 0,
                "多品种风险簇日数": int((exposure_dd["multi_product_cluster_count"] > 0).sum()) if not exposure_dd.empty else 0,
                "同向多品种风险簇日数": int((exposure_dd["same_direction_multi_cluster_count"] > 0).sum()) if not exposure_dd.empty else 0,
            }
        ]
    )
    lines = [
        "# Stage061 C3风险簇剩余暴露诊断",
        "",
        "## 定位",
        "",
        "- 本阶段只做诊断，不改交易引擎，不产生可直接实盘的新版本。",
        "- 目标是确认 C3 剩余 `-31%` 最大回撤是否主要来自同一风险簇内的多品种/同向暴露残留。",
        "- 若证据不足，停止“同簇暴露压缩”方向；若证据充分，再进入真实引擎候选，而不是直接调阈值。",
        "",
        "## 外部调研判断",
        "",
        "- 趋势策略长期优势来自跨市场分散和风险配置；商品趋势研究也强调跨市场聚合、交易成本和反数据挖掘。",
        "- 因此本阶段只检验风险暴露结构，不做单品种黑名单、行业组删除或供需阈值补丁。",
        "",
        "## C3基准",
        "",
        f"- 期末权益：`{_safe_float(baseline_stats.get('end_balance')):,.0f}`",
        f"- 总收益：`{_safe_float(baseline_stats.get('total_return')):.4f}%`",
        f"- 最大回撤：`{_safe_float(baseline_stats.get('max_ddpercent')):.4f}%`",
        f"- Sharpe：`{_safe_float(baseline_stats.get('sharpe_ratio')):.4f}`",
        f"- 总滑点：`{_safe_float(baseline_stats.get('total_slippage')):,.0f}`",
        f"- 总交易次数：`{int(_safe_float(baseline_stats.get('total_trade_count'))):,}`",
        f"- 胜率：`{_safe_float(baseline_stats.get('win_ratio')):.4f}%`",
        "",
        "## 最大回撤窗口",
        "",
        f"- 高点：`{peak.date()}`，权益 `{drawdown['peak_balance']:,.2f}`",
        f"- 低点：`{trough.date()}`，权益 `{drawdown['trough_balance']:,.2f}`",
        f"- 回撤金额：`{decision['dd_loss_amount']:,.2f}`",
        f"- 最大回撤：`{drawdown['max_dd_percent']:.4f}%`",
        "",
        "## 窗口暴露概览",
        "",
        _to_markdown_table(exposure_summary, max_rows=10),
        "",
        "## 最大回撤窗口风险簇亏损",
        "",
        _to_markdown_table(
            cluster_dd,
            [
                "risk_cluster",
                "dd_window_net_pnl",
                "dd_window_holding_pnl",
                "dd_window_trading_pnl",
                "active_days",
                "max_active_product_count",
                "multi_product_days",
                "same_direction_multi_days",
                "mixed_direction_days",
            ],
            max_rows=20,
        ),
        "",
        "## 单品种/多品种暴露拆分",
        "",
        _to_markdown_table(
            bucket_dd,
            ["risk_cluster", "exposure_bucket", "bucket_net_pnl", "bucket_days", "bucket_trade_count", "bucket_slippage"],
            max_rows=40,
        ),
        "",
        "## 风险簇热度降暴露实际触发",
        "",
        _to_markdown_table(
            heat_dd,
            ["date", "risk_cluster", "product_vt_symbol", "exit_reason", "close_volume", "trade_count", "avg_price"],
            max_rows=40,
        ),
        "",
        "## 结论",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 多品种风险簇亏损占最大回撤金额：`{decision['multi_product_cluster_loss_share_of_dd_pct']:.4f}%`。",
        f"- 最大亏损风险簇：`{decision['top_loss_cluster']}`，占最大回撤金额 `{decision['top_loss_cluster_share_of_dd_pct']:.4f}%`。",
        f"- 最大回撤窗口内 `risk_cluster_heat_deleverage` 平仓回报次数：`{decision['heat_deleverage_close_count_in_dd_window']}`。",
        "",
        "## 输出",
        "",
        f"- cluster_daily：`{paths['cluster_daily'].name}`",
        f"- cluster_dd：`{paths['cluster_dd'].name}`",
        f"- bucket_dd：`{paths['bucket_dd'].name}`",
        f"- heat_events：`{paths['heat_events'].name}`",
        f"- decision：`{paths['decision'].name}`",
        "",
        "## 反思",
        "",
        "- 是否过拟合：不是。本阶段不改策略参数，只验证一个结构性问题：剩余回撤是否来自风险簇多品种暴露。",
        "- 是否还有价值继续：取决于决策标签。若多品种风险簇亏损占比高，才值得做真实引擎候选；否则继续该方向会变成补丁。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    daily, positions, trades, _candidates, _risks, statistics = _run_c3()
    drawdown = _drawdown_window(daily)
    position_frame = _prepare_positions(positions)
    cluster_daily = _cluster_daily(position_frame)
    exposure_daily = _portfolio_exposure_daily(cluster_daily)
    cluster_dd, bucket_dd = _cluster_summary(cluster_daily, drawdown)
    heat_events = _heat_deleverage_events(trades)
    decision = _decision(statistics, drawdown, cluster_dd, bucket_dd, heat_events)

    paths = {
        "positions": OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv",
        "cluster_daily": OUTPUT_DIR / f"{OUTPUT_PREFIX}_cluster_daily_{MODEL_TAG}.csv",
        "exposure_daily": OUTPUT_DIR / f"{OUTPUT_PREFIX}_exposure_daily_{MODEL_TAG}.csv",
        "cluster_dd": OUTPUT_DIR / f"{OUTPUT_PREFIX}_cluster_dd_{MODEL_TAG}.csv",
        "bucket_dd": OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_dd_{MODEL_TAG}.csv",
        "heat_events": OUTPUT_DIR / f"{OUTPUT_PREFIX}_heat_events_{MODEL_TAG}.csv",
        "report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md",
        "decision": OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json",
    }

    position_frame.to_csv(paths["positions"], index=False, encoding="utf-8-sig")
    cluster_daily.to_csv(paths["cluster_daily"], index=False, encoding="utf-8-sig")
    exposure_daily.to_csv(paths["exposure_daily"], index=False, encoding="utf-8-sig")
    cluster_dd.to_csv(paths["cluster_dd"], index=False, encoding="utf-8-sig")
    bucket_dd.to_csv(paths["bucket_dd"], index=False, encoding="utf-8-sig")
    heat_events.to_csv(paths["heat_events"], index=False, encoding="utf-8-sig")
    paths["decision"].write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    paths["report"].write_text(
        _build_report(statistics, drawdown, cluster_dd, bucket_dd, exposure_daily, heat_events, decision, paths),
        encoding="utf-8",
    )

    print(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2))
    print(f"[stage361] report: {paths['report']}")


if __name__ == "__main__":
    main()
