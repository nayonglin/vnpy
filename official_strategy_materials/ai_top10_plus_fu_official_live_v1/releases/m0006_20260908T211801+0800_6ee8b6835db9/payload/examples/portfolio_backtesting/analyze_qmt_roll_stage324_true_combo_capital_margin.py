from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from main_contract_mapping import build_contract_metadata, load_product_universe_symbols
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_manifest,
    build_official_stage78_overrides,
)
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import OUTPUT_DIR, build_positions_df
from run_qmt_range_reversion_core4_directed_backtest import (
    CORE_UNIVERSE_PATH,
    run_backtest as run_range_backtest,
)
from run_qmt_roll_backtest import run_backtest as run_roll_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO
from run_qmt_roll_stage310_stage78_1_drawdown_gate_engine_validation import _pressure040_overrides
from run_qmt_roll_stage318_supply_demand_headwind_engine_validation import _supply_demand_headwind_overrides


MODEL_TAG = "stage324_true_combo_capital_margin_v1"
OUTPUT_PREFIX = "qmt_roll_stage324_true_combo_capital_margin"
LINE_ID = "futures_trend_drawdown30_preserve_return"

TOTAL_CAPITAL: float = 500_000.0
C3_CAPITAL: float = 400_000.0
SATELLITE_CAPITAL: float = 100_000.0
SATELLITE_RISK_RATIO: float = 0.008

MARGIN_WATCH_PCT: float = 60.0
MARGIN_REVIEW_PCT: float = 80.0
MARGIN_REJECT_PCT: float = 100.0


@dataclass(frozen=True)
class Window:
    name: str
    label: str
    start: datetime
    end: datetime


WINDOWS: tuple[Window, ...] = (
    Window("full_2020_2026", "2020起点至今", START_DT, END_DT),
    Window("since_2022", "2022起点至今", datetime(2022, 1, 1), END_DT),
    Window("since_2023", "2023起点至今", datetime(2023, 1, 1), END_DT),
    Window("since_2024", "2024起点至今", datetime(2024, 1, 1), END_DT),
    Window("phase_2024_2025", "2024-2025独立启动", datetime(2024, 1, 1), datetime(2025, 12, 31)),
    Window("ytd_2026", "2026年初至今", datetime(2026, 1, 1), END_DT),
)


SATELLITE_OVERRIDES: dict[str, Any] = {
    "range_use_product_continuous_signal": True,
    "range_product_signal_adjustment_mode": "back_adjust_additive",
    "streak_risk_multipliers": "1.0,1.0,1.0,1.0",
    "range_previous_day_stop_long_enabled": False,
    "range_previous_day_stop_short_enabled": True,
    "range_two_stage_stop_enabled": True,
    "range_soft_stop_confirm_bars": 1,
    "range_hard_stop_r_multiple": 2.0,
}


def _merge(*items: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for item in items:
        merged.update(item)
    return merged


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _to_builtin(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _to_builtin(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_builtin(item) for item in value]
    if isinstance(value, tuple):
        return [_to_builtin(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 50) -> str:
    if df.empty:
        return "_empty_"
    view = df[columns].copy() if columns else df.copy()
    view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    header = "| " + " | ".join(view.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()]
    return "\n".join([header, separator, *rows])


def _c3_overrides(analysis_start: datetime) -> dict[str, Any]:
    overrides = build_official_stage78_overrides()
    overrides["trade_start_date"] = analysis_start.date().isoformat()
    overrides.update(_merge(_pressure040_overrides(), _supply_demand_headwind_overrides()))
    return overrides


def _daily_from_analysis(analysis_df: pd.DataFrame | None, capital: float, label: str) -> pd.DataFrame:
    if analysis_df is None or analysis_df.empty:
        return pd.DataFrame(columns=["date", f"{label}_balance", f"{label}_net_pnl", f"{label}_trade_count"])
    frame = analysis_df.copy().reset_index().rename(columns={"index": "date"})
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame = frame.sort_values("date").drop_duplicates("date", keep="last")
    frame[f"{label}_balance"] = pd.to_numeric(frame.get("balance", capital), errors="coerce").ffill().fillna(capital)
    frame[f"{label}_net_pnl"] = pd.to_numeric(frame.get("net_pnl", 0.0), errors="coerce").fillna(0.0)
    frame[f"{label}_trade_count"] = pd.to_numeric(frame.get("trade_count", 0.0), errors="coerce").fillna(0.0)
    return frame[["date", f"{label}_balance", f"{label}_net_pnl", f"{label}_trade_count"]]


def _path_metrics(daily: pd.DataFrame, capital: float, balance_column: str = "balance") -> dict[str, float]:
    if daily.empty or balance_column not in daily.columns:
        return {
            "end_balance": capital,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
        }
    balance = pd.to_numeric(daily[balance_column], errors="coerce").ffill().fillna(capital)
    arr = balance.to_numpy(dtype=float)
    high = np.maximum.accumulate(arr)
    dd_pct = np.divide(arr - high, high, out=np.zeros_like(arr), where=high != 0) * 100.0
    returns = pd.Series(arr).pct_change().fillna(0.0).to_numpy(dtype=float)
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / std * np.sqrt(252)) if std > 0 else 0.0
    return {
        "end_balance": float(arr[-1]),
        "total_return_pct": float((arr[-1] / capital - 1.0) * 100.0),
        "max_dd_percent": float(dd_pct.min()),
        "sharpe_ratio": sharpe,
    }


def _combine_daily(c3_daily: pd.DataFrame, satellite_daily: pd.DataFrame) -> pd.DataFrame:
    dates = sorted(set(c3_daily["date"]).union(set(satellite_daily["date"])))
    if not dates:
        return pd.DataFrame()
    base = pd.DataFrame({"date": pd.to_datetime(dates)})
    merged = base.merge(c3_daily, on="date", how="left").merge(satellite_daily, on="date", how="left")
    merged["c3_net_pnl"] = pd.to_numeric(merged["c3_net_pnl"], errors="coerce").fillna(0.0)
    merged["satellite_net_pnl"] = pd.to_numeric(merged["satellite_net_pnl"], errors="coerce").fillna(0.0)
    merged["c3_trade_count"] = pd.to_numeric(merged["c3_trade_count"], errors="coerce").fillna(0.0)
    merged["satellite_trade_count"] = pd.to_numeric(merged["satellite_trade_count"], errors="coerce").fillna(0.0)
    merged["combo_net_pnl"] = merged["c3_net_pnl"] + merged["satellite_net_pnl"]
    merged["balance"] = TOTAL_CAPITAL + merged["combo_net_pnl"].cumsum()
    merged["highlevel"] = merged["balance"].cummax()
    merged["drawdown"] = merged["balance"] - merged["highlevel"]
    merged["ddpercent"] = np.divide(
        merged["drawdown"],
        merged["highlevel"].replace(0.0, np.nan),
    ).fillna(0.0) * 100.0
    merged["trade_count"] = merged["c3_trade_count"] + merged["satellite_trade_count"]
    return merged


def _product_from_contract(vt_symbol: object) -> str:
    raw = str(vt_symbol)
    if "." not in raw:
        return raw
    symbol, exchange = raw.split(".", 1)
    letters = "".join(ch for ch in symbol if ch.isalpha())
    return f"{letters or symbol}.{exchange}"


def _metadata() -> dict[str, Any]:
    manifest = build_official_stage78_manifest()
    symbols: set[str] = set(load_product_universe_symbols(manifest["product_universe_csv_path"]) or [])
    symbols.update(load_product_universe_symbols(CORE_UNIVERSE_PATH) or [])
    return build_contract_metadata(supported_symbols=sorted(symbols))


def _margin_daily(positions: pd.DataFrame, metadata: dict[str, Any], label: str) -> pd.DataFrame:
    if positions.empty:
        return pd.DataFrame(columns=["date", f"{label}_margin", f"{label}_active_contracts", f"{label}_active_products"])
    frame = positions.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    for column in ["end_pos", "close_price"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    frame["size"] = frame["vt_symbol"].map(metadata["sizes"]).fillna(1.0).astype(float)
    frame["margin_ratio"] = frame["vt_symbol"].map(metadata["margin_ratios"]).fillna(0.15).astype(float)
    frame["product_vt_symbol"] = frame["vt_symbol"].map(_product_from_contract)
    frame["abs_end_pos"] = frame["end_pos"].abs()
    frame["position_margin"] = frame["abs_end_pos"] * frame["close_price"].clip(lower=0.0) * frame["size"] * frame["margin_ratio"]
    frame["active_contract"] = (frame["abs_end_pos"] > 0).astype(int)
    product_daily = (
        frame.groupby(["date", "product_vt_symbol"], as_index=False)
        .agg(
            product_margin=("position_margin", "sum"),
            active_contracts=("active_contract", "sum"),
        )
    )
    product_daily["active_product"] = (product_daily["product_margin"] > 0).astype(int)
    daily = (
        product_daily.groupby("date", as_index=False)
        .agg(
            **{
                f"{label}_margin": ("product_margin", "sum"),
                f"{label}_active_contracts": ("active_contracts", "sum"),
                f"{label}_active_products": ("active_product", "sum"),
            }
        )
        .sort_values("date")
        .reset_index(drop=True)
    )
    return daily


def _combine_margin(
    combo_daily: pd.DataFrame,
    c3_positions: pd.DataFrame,
    satellite_positions: pd.DataFrame,
    metadata: dict[str, Any],
) -> pd.DataFrame:
    if combo_daily.empty:
        return pd.DataFrame()
    margin = combo_daily[["date", "balance"]].copy()
    margin = margin.merge(_margin_daily(c3_positions, metadata, "c3"), on="date", how="left")
    margin = margin.merge(_margin_daily(satellite_positions, metadata, "satellite"), on="date", how="left")
    for column in [
        "c3_margin",
        "satellite_margin",
        "c3_active_contracts",
        "satellite_active_contracts",
        "c3_active_products",
        "satellite_active_products",
    ]:
        margin[column] = pd.to_numeric(margin.get(column, 0.0), errors="coerce").fillna(0.0)
    margin["total_margin"] = margin["c3_margin"] + margin["satellite_margin"]
    margin["total_active_contracts"] = margin["c3_active_contracts"] + margin["satellite_active_contracts"]
    margin["total_active_products"] = margin["c3_active_products"] + margin["satellite_active_products"]
    margin["margin_to_equity_pct"] = (
        margin["total_margin"] / margin["balance"].replace(0.0, np.nan) * 100.0
    ).fillna(0.0)
    margin["margin_to_initial_capital_pct"] = margin["total_margin"] / TOTAL_CAPITAL * 100.0
    return margin


def _margin_summary(margin: pd.DataFrame) -> dict[str, Any]:
    if margin.empty:
        return {
            "max_margin_to_equity_pct": 0.0,
            "p95_margin_to_equity_pct": 0.0,
            "watch_days": 0,
            "review_days": 0,
            "reject_days": 0,
            "max_active_contracts": 0,
            "max_active_products": 0,
        }
    max_idx = margin["margin_to_equity_pct"].idxmax()
    max_row = margin.loc[max_idx]
    return {
        "max_margin_date": str(pd.to_datetime(max_row["date"]).date()),
        "max_margin": _safe_float(max_row["total_margin"]),
        "max_margin_to_equity_pct": _safe_float(max_row["margin_to_equity_pct"]),
        "p95_margin_to_equity_pct": _safe_float(margin["margin_to_equity_pct"].quantile(0.95)),
        "watch_days": int((margin["margin_to_equity_pct"] >= MARGIN_WATCH_PCT).sum()),
        "review_days": int((margin["margin_to_equity_pct"] >= MARGIN_REVIEW_PCT).sum()),
        "reject_days": int((margin["margin_to_equity_pct"] >= MARGIN_REJECT_PCT).sum()),
        "max_active_contracts": int(margin["total_active_contracts"].max()),
        "max_active_products": int(margin["total_active_products"].max()),
    }


def _run_c3(window: Window, save_artifacts: bool) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    preload_start = max(PRELOAD_START_DT, window.start - timedelta(days=365))
    print(f"[stage324] run C3 {window.name} capital={C3_CAPITAL:.0f}", flush=True)
    engine, analysis_df, statistics = run_roll_backtest(
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=_c3_overrides(window.start),
        analysis_start=window.start,
        analysis_end=window.end,
        preload_start=preload_start,
        capital=C3_CAPITAL,
        save_artifacts=save_artifacts,
        include_start_year_sweep=False,
        file_prefix=f"{OUTPUT_PREFIX}_c3_400k_{window.name}",
        chart_title=f"Stage324 C3 400k {window.label}",
    )
    return _daily_from_analysis(analysis_df, C3_CAPITAL, "c3"), build_positions_df(engine), statistics


def _run_satellite(window: Window, save_artifacts: bool) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    preload_start = max(PRELOAD_START_DT, window.start - timedelta(days=365))
    print(f"[stage324] run satellite {window.name} capital={SATELLITE_CAPITAL:.0f}", flush=True)
    engine, analysis_df, statistics = run_range_backtest(
        risk_ratio=SATELLITE_RISK_RATIO,
        analysis_start=window.start,
        analysis_end=window.end,
        preload_start=preload_start,
        capital=SATELLITE_CAPITAL,
        save_artifacts=save_artifacts,
        file_prefix=f"{OUTPUT_PREFIX}_satellite_100k_{window.name}",
        chart_title=f"Stage324 Satellite 100k {window.label}",
        strategy_tag="range_reversion_core4_directed_product_signal_back_adjusted_v8_two_stage_stop_cap100k",
        setting_overrides=SATELLITE_OVERRIDES,
    )
    return _daily_from_analysis(analysis_df, SATELLITE_CAPITAL, "satellite"), build_positions_df(engine), statistics


def _summarize_window(
    window: Window,
    c3_daily: pd.DataFrame,
    satellite_daily: pd.DataFrame,
    combo_daily: pd.DataFrame,
    margin: pd.DataFrame,
    c3_stats: dict[str, Any],
    satellite_stats: dict[str, Any],
) -> dict[str, Any]:
    combo_metrics = _path_metrics(combo_daily, TOTAL_CAPITAL)
    c3_return = _safe_float(c3_stats.get("total_return"))
    satellite_return = _safe_float(satellite_stats.get("total_return"))
    margin_metrics = _margin_summary(margin)
    combo_return = combo_metrics["total_return_pct"]
    return {
        "window_name": window.name,
        "window_label": window.label,
        "analysis_start": window.start.date().isoformat(),
        "analysis_end": window.end.date().isoformat(),
        "c3_capital": C3_CAPITAL,
        "satellite_capital": SATELLITE_CAPITAL,
        "total_capital": TOTAL_CAPITAL,
        "c3_return_pct": c3_return,
        "c3_max_dd_pct": _safe_float(c3_stats.get("max_ddpercent")),
        "c3_sharpe": _safe_float(c3_stats.get("sharpe_ratio")),
        "c3_trade_count": int(_safe_float(c3_stats.get("total_trade_count"))),
        "satellite_return_pct": satellite_return,
        "satellite_max_dd_pct": _safe_float(satellite_stats.get("max_ddpercent")),
        "satellite_sharpe": _safe_float(satellite_stats.get("sharpe_ratio")),
        "satellite_trade_count": int(_safe_float(satellite_stats.get("total_trade_count"))),
        "combo_end_balance": combo_metrics["end_balance"],
        "combo_return_pct": combo_return,
        "combo_return_retention_vs_c3_pct": combo_return / c3_return * 100.0 if c3_return > 0 else 0.0,
        "combo_max_dd_pct": combo_metrics["max_dd_percent"],
        "combo_sharpe": combo_metrics["sharpe_ratio"],
        "combo_trade_count": int(combo_daily["trade_count"].sum()) if not combo_daily.empty else 0,
        "c3_days": int(len(c3_daily)),
        "satellite_days": int(len(satellite_daily)),
        "combo_days": int(len(combo_daily)),
        **margin_metrics,
        "dd_lt_30_ok": int(combo_metrics["max_dd_percent"] >= -30.0),
        "retention_vs_c3_ge_80_ok": int((combo_return / c3_return * 100.0) >= 80.0) if c3_return > 0 else 0,
        "margin_review_ok": int(margin_metrics["reject_days"] == 0 and margin_metrics["max_margin_to_equity_pct"] < MARGIN_REVIEW_PCT),
    }


def _build_report(summary_df: pd.DataFrame) -> str:
    lines = [
        "# Stage324 真实组合资金与保证金约束验证",
        "",
        "## 目标",
        "",
        "- 将 Stage323 的净值层 `80% C3 + 20% 卫星` 改为真实资金拆分验证。",
        f"- 趋势底座 C3 使用 `{C3_CAPITAL:,.0f}` 资金独立回测；低相关卫星使用 `{SATELLITE_CAPITAL:,.0f}` 资金独立回测。",
        "- 合并时只叠加两条腿的真实日盈亏，不做小数手数缩放。",
        "- 保证金按两条腿绝对持仓保守相加，暂不做同合约跨策略净额抵消。",
        "",
        "## 窗口结果",
        "",
    ]
    display_cols = [
        "window_name",
        "c3_return_pct",
        "c3_max_dd_pct",
        "satellite_return_pct",
        "satellite_max_dd_pct",
        "combo_return_pct",
        "combo_return_retention_vs_c3_pct",
        "combo_max_dd_pct",
        "combo_sharpe",
        "max_margin_to_equity_pct",
        "p95_margin_to_equity_pct",
        "watch_days",
        "review_days",
        "reject_days",
        "dd_lt_30_ok",
        "retention_vs_c3_ge_80_ok",
        "margin_review_ok",
    ]
    lines.append(_to_markdown_table(summary_df, display_cols))
    lines.extend(["", "## 阶段判断", ""])
    if summary_df.empty:
        lines.append("- 未产出有效结果。")
    else:
        full = summary_df[summary_df["window_name"].eq("full_2020_2026")].iloc[0]
        positive_windows = summary_df[summary_df["c3_return_pct"] > 0]
        all_dd_ok = bool(positive_windows["dd_lt_30_ok"].all()) if not positive_windows.empty else False
        all_retention_ok = bool(positive_windows["retention_vs_c3_ge_80_ok"].all()) if not positive_windows.empty else False
        all_margin_ok = bool(summary_df["margin_review_ok"].all())
        lines.append(
            f"- 全样本组合收益 `{full['combo_return_pct']:.3f}%`，最大回撤 `{full['combo_max_dd_pct']:.4f}%`，"
            f"相对 C3 收益保留 `{full['combo_return_retention_vs_c3_pct']:.2f}%`。"
        )
        lines.append(
            f"- 全样本最大保证金/权益 `{full['max_margin_to_equity_pct']:.2f}%`，"
            f"80%复核线触发 `{int(full['review_days'])}` 天，100%拒绝线触发 `{int(full['reject_days'])}` 天。"
        )
        if all_dd_ok and all_retention_ok and all_margin_ok:
            lines.append("- 结论：通过真实资金拆分和保证金约束的研究闸门，可以进入更严格的实盘执行对账验证。")
        elif all_dd_ok and all_retention_ok:
            lines.append("- 结论：收益和回撤目标基本成立，但保证金约束仍需处理，不能直接合入。")
        elif all_dd_ok:
            lines.append("- 结论：回撤目标成立，但收益保留不足，不能作为当前目标的正式候选。")
        else:
            lines.append("- 结论：真实资金/整数手数约束后没有稳定通过回撤30以内闸门，Stage323 仍只能是净值层研究线索。")
    lines.extend(
        [
            "",
            "## 过拟合反思",
            "",
            "- 本阶段不是通过新增参数寻找更好结果，而是把上一阶段候选放到更真实执行约束下复验。",
            "- 如果真实资金拆分失败，应优先否决候选或回到结构归因，而不是围绕 `0.19/0.21` 继续微调权重。",
            "",
            "## 继续价值反思",
            "",
            "- 这一步有价值，因为它直接检验上一阶段最接近目标的路径是否可执行。",
            "- 若通过，下一步看近端收益损失来源；若失败，说明组合层卫星方向需要重新找更低离散度或更强低相关腿。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = _metadata()
    summary_rows: list[dict[str, Any]] = []
    combo_daily_frames: list[pd.DataFrame] = []
    margin_frames: list[pd.DataFrame] = []

    for window in WINDOWS:
        save_artifacts = window.name == "full_2020_2026"
        c3_daily, c3_positions, c3_stats = _run_c3(window, save_artifacts=save_artifacts)
        satellite_daily, satellite_positions, satellite_stats = _run_satellite(window, save_artifacts=save_artifacts)
        combo_daily = _combine_daily(c3_daily, satellite_daily)
        margin = _combine_margin(combo_daily, c3_positions, satellite_positions, metadata)

        combo_daily["window_name"] = window.name
        margin["window_name"] = window.name
        combo_daily_frames.append(combo_daily)
        margin_frames.append(margin)
        summary_rows.append(
            _summarize_window(
                window,
                c3_daily,
                satellite_daily,
                combo_daily,
                margin,
                c3_stats,
                satellite_stats,
            )
        )

    summary_df = pd.DataFrame(summary_rows)
    combo_daily_df = pd.concat(combo_daily_frames, ignore_index=True) if combo_daily_frames else pd.DataFrame()
    margin_df = pd.concat(margin_frames, ignore_index=True) if margin_frames else pd.DataFrame()

    summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    combo_daily_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combo_daily_{MODEL_TAG}.csv"
    margin_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_{MODEL_TAG}.csv"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    combo_daily_df.to_csv(combo_daily_path, index=False, encoding="utf-8-sig")
    margin_df.to_csv(margin_path, index=False, encoding="utf-8-sig")
    report_path.write_text(_build_report(summary_df), encoding="utf-8")

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "capital_split": {
            "total": TOTAL_CAPITAL,
            "c3": C3_CAPITAL,
            "satellite": SATELLITE_CAPITAL,
        },
        "windows": summary_df.to_dict(orient="records"),
        "paths": {
            "summary": str(summary_path),
            "combo_daily": str(combo_daily_path),
            "margin": str(margin_path),
            "report": str(report_path),
        },
    }
    decision_path.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[stage324] summary={summary_path}")
    print(f"[stage324] combo_daily={combo_daily_path}")
    print(f"[stage324] margin={margin_path}")
    print(f"[stage324] report={report_path}")
    print(f"[stage324] decision={decision_path}")
    print(report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
