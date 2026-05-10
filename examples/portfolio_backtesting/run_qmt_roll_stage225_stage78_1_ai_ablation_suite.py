from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from main_contract_mapping import build_contract_metadata, load_product_universe_symbols
from qmt_backtest_runtime_guard import assert_stage196_database_sentinels
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_manifest,
    build_official_stage78_overrides,
)
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_monte_carlo import DAILY_BLOCK_SIZE, N_SIMULATIONS, RNG_SEED, TRADE_BLOCK_SIZE
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


MODEL_TAG = "stage225_stage78_1_ai_ablation_suite_v1"
OUTPUT_PREFIX = "qmt_roll_stage225_stage78_1_ai_ablation_suite"
SLIPPAGE_MULTIPLIERS = (1.0, 2.0, 3.0, 5.0)
WINDOWS: tuple[tuple[str, str, str, datetime, datetime], ...] = (
    ("since_2020", "2020起点至今", "start_year_to_latest", datetime(2020, 1, 1), END_DT),
    ("since_2021", "2021起点至今", "start_year_to_latest", datetime(2021, 1, 1), END_DT),
    ("since_2022", "2022起点至今", "start_year_to_latest", datetime(2022, 1, 1), END_DT),
    ("since_2023", "2023起点至今", "start_year_to_latest", datetime(2023, 1, 1), END_DT),
    ("since_2024", "2024起点至今", "start_year_to_latest", datetime(2024, 1, 1), END_DT),
    ("since_2025", "2025起点至今", "start_year_to_latest", datetime(2025, 1, 1), END_DT),
    ("since_2026", "2026起点至今", "start_year_to_latest", datetime(2026, 1, 1), END_DT),
    ("phase_2020_2021", "2020-2021独立启动", "independent_phase", datetime(2020, 1, 1), datetime(2021, 12, 31)),
    ("phase_2022_2023", "2022-2023独立启动", "independent_phase", datetime(2022, 1, 1), datetime(2023, 12, 31)),
    ("phase_2024_2025", "2024-2025独立启动", "independent_phase", datetime(2024, 1, 1), datetime(2025, 12, 31)),
    ("phase_2026_latest", "2026独立启动至最新", "independent_phase", datetime(2026, 1, 1), END_DT),
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _variant_overrides(ai_enabled: bool) -> dict[str, Any]:
    overrides = build_official_stage78_overrides()
    overrides["enable_ai_product_pool_filter"] = bool(ai_enabled)
    if not ai_enabled:
        overrides["ai_product_pool_strategy"] = "disabled_for_stage225_ablation"
    return overrides


def _variant_label(ai_enabled: bool) -> str:
    return "ai_on" if ai_enabled else "ai_off"


def _daily_to_frame(daily_df: pd.DataFrame | None) -> pd.DataFrame:
    if daily_df is None or daily_df.empty:
        return pd.DataFrame()
    frame = daily_df.copy()
    frame.insert(0, "date", pd.to_datetime(frame.index).date)
    return frame


def _trades_to_frame(engine: Any) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for trade in sorted(engine.get_all_trades(), key=lambda item: (pd.Timestamp(item.datetime), item.vt_tradeid)):
        rows.append(
            {
                "datetime": pd.Timestamp(trade.datetime).isoformat(),
                "vt_tradeid": trade.vt_tradeid,
                "vt_orderid": trade.vt_orderid,
                "symbol": trade.symbol,
                "exchange": trade.exchange.value,
                "vt_symbol": trade.vt_symbol,
                "direction": trade.direction.value,
                "offset": trade.offset.value,
                "price": float(trade.price),
                "volume": float(trade.volume),
            }
        )
    return pd.DataFrame(rows)


def _path_metrics_from_pnl(net_pnl: np.ndarray, initial_capital: float) -> dict[str, float]:
    if net_pnl.size == 0:
        return {"end_balance": initial_capital, "total_return_pct": 0.0, "max_drawdown": 0.0, "max_dd_percent": 0.0, "sharpe_ratio": 0.0}
    equity = initial_capital + np.cumsum(net_pnl)
    previous = np.concatenate([[initial_capital], equity[:-1]])
    returns = np.divide(net_pnl, previous, out=np.zeros_like(net_pnl, dtype=float), where=previous != 0)
    high = np.maximum.accumulate(np.insert(equity, 0, initial_capital))[1:]
    drawdown = equity - high
    dd_pct = np.divide(drawdown, high, out=np.zeros_like(drawdown, dtype=float), where=high != 0) * 100.0
    std = float(np.std(returns, ddof=1)) if returns.size > 1 else 0.0
    return {
        "end_balance": float(equity[-1]),
        "total_return_pct": float((equity[-1] / initial_capital - 1.0) * 100.0),
        "max_drawdown": float(drawdown.min()),
        "max_dd_percent": float(dd_pct.min()),
        "sharpe_ratio": float(np.mean(returns) / std * np.sqrt(240.0)) if std > 0 else 0.0,
    }


def _slippage_stress(variant: str, daily_df: pd.DataFrame) -> pd.DataFrame:
    net_pnl = pd.to_numeric(daily_df["net_pnl"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    slippage = pd.to_numeric(daily_df.get("slippage", 0.0), errors="coerce").fillna(0.0).to_numpy(dtype=float)
    rows: list[dict[str, Any]] = []
    for multiplier in SLIPPAGE_MULTIPLIERS:
        stressed = net_pnl - (multiplier - 1.0) * slippage
        rows.append(
            {
                "variant": variant,
                "slippage_multiplier": multiplier,
                **_path_metrics_from_pnl(stressed, OFFICIAL_STAGE78_CAPITAL),
                "total_net_pnl": float(stressed.sum()),
                "total_slippage": float(slippage.sum() * multiplier),
            }
        )
    return pd.DataFrame(rows)


def _calculate_path_metrics(values: np.ndarray, initial_capital: float) -> dict[str, float]:
    if values.size == 0:
        return {"end_balance": initial_capital, "total_return_pct": 0.0, "max_drawdown": 0.0, "max_dd_percent": 0.0, "min_balance": initial_capital}
    high = np.maximum.accumulate(values)
    drawdown = values - high
    dd_percent = np.divide(drawdown, high, out=np.zeros_like(drawdown, dtype=float), where=high != 0) * 100.0
    return {
        "end_balance": float(values[-1]),
        "total_return_pct": float((values[-1] / initial_capital - 1.0) * 100.0),
        "max_drawdown": float(drawdown.min()),
        "max_dd_percent": float(dd_percent.min()),
        "min_balance": float(values.min()),
    }


def _build_round_trip_pnls(trades_df: pd.DataFrame, size_map: dict[str, float]) -> np.ndarray:
    if trades_df.empty:
        return np.array([], dtype=float)
    frame = trades_df.copy()
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    frame.sort_values(["datetime", "vt_tradeid"], inplace=True)
    queues: dict[tuple[str, str], list[dict[str, float]]] = {}
    realized: list[float] = []
    for row in frame.itertuples(index=False):
        vt_symbol = str(row.vt_symbol)
        direction = str(row.direction)
        offset = str(row.offset)
        price = float(row.price)
        volume = float(row.volume)
        size = float(size_map.get(vt_symbol, 1.0))
        if offset == "Open":
            pos_direction = "long" if direction == "Long" else "short"
            queues.setdefault((vt_symbol, pos_direction), []).append({"price": price, "volume": volume})
            continue
        pos_direction = "long" if direction == "Short" else "short"
        queue = queues.setdefault((vt_symbol, pos_direction), [])
        remain = volume
        while remain > 1e-9 and queue:
            entry = queue[0]
            matched = min(remain, float(entry["volume"]))
            entry_price = float(entry["price"])
            pnl = (price - entry_price) * matched * size if pos_direction == "long" else (entry_price - price) * matched * size
            realized.append(float(pnl))
            entry["volume"] = float(entry["volume"]) - matched
            remain -= matched
            if float(entry["volume"]) <= 1e-9:
                queue.pop(0)
    return np.array(realized, dtype=float)


def _simulate_trade_bootstrap(round_trip_pnls: np.ndarray, rng: np.random.Generator, variant: str) -> pd.DataFrame:
    n = len(round_trip_pnls)
    if n == 0:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    blocks_per_path = int(np.ceil(n / TRADE_BLOCK_SIZE))
    for simulation in range(1, N_SIMULATIONS + 1):
        sampled: list[float] = []
        for _ in range(blocks_per_path):
            start_idx = int(rng.integers(0, n))
            sampled.extend(float(round_trip_pnls[(start_idx + offset) % n]) for offset in range(TRADE_BLOCK_SIZE))
        values = OFFICIAL_STAGE78_CAPITAL + np.cumsum(np.array(sampled[:n], dtype=float))
        rows.append({"variant": variant, "simulation": simulation, "method": "trade_block_bootstrap", **_calculate_path_metrics(values, OFFICIAL_STAGE78_CAPITAL)})
    return pd.DataFrame(rows)


def _simulate_daily_block_bootstrap(daily_returns: np.ndarray, rng: np.random.Generator, variant: str) -> pd.DataFrame:
    n = len(daily_returns)
    if n == 0:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    blocks_per_path = int(np.ceil(n / DAILY_BLOCK_SIZE))
    for simulation in range(1, N_SIMULATIONS + 1):
        sampled: list[float] = []
        for _ in range(blocks_per_path):
            start_idx = int(rng.integers(0, n))
            sampled.extend(float(daily_returns[(start_idx + offset) % n]) for offset in range(DAILY_BLOCK_SIZE))
        values = OFFICIAL_STAGE78_CAPITAL * np.cumprod(1.0 + np.array(sampled[:n], dtype=float))
        rows.append({"variant": variant, "simulation": simulation, "method": "daily_block_bootstrap", **_calculate_path_metrics(values, OFFICIAL_STAGE78_CAPITAL)})
    return pd.DataFrame(rows)


def _mc_summary(sim_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (variant, method), group in sim_df.groupby(["variant", "method"]):
        row: dict[str, Any] = {
            "variant": variant,
            "method": method,
            "simulations": int(len(group)),
            "loss_probability_pct": float((group["end_balance"] < OFFICIAL_STAGE78_CAPITAL).mean() * 100.0),
            "ruin_probability_pct": float((group["min_balance"] <= 0).mean() * 100.0),
            "dd_over_20pct_probability_pct": float((group["max_dd_percent"] <= -20.0).mean() * 100.0),
            "dd_over_30pct_probability_pct": float((group["max_dd_percent"] <= -30.0).mean() * 100.0),
            "dd_over_40pct_probability_pct": float((group["max_dd_percent"] <= -40.0).mean() * 100.0),
        }
        for q in (0.01, 0.05, 0.10, 0.50, 0.90):
            label = str(int(q * 100)).zfill(2)
            row[f"end_balance_q{label}"] = float(group["end_balance"].quantile(q))
            row[f"return_pct_q{label}"] = float(group["total_return_pct"].quantile(q))
            row[f"max_dd_pct_q{label}"] = float(group["max_dd_percent"].quantile(q))
        rows.append(row)
    return pd.DataFrame(rows)


def run_main_variants() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    daily_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    for ai_enabled in (True, False):
        variant = _variant_label(ai_enabled)
        print(f"[stage225] main {variant}", flush=True)
        overrides = _variant_overrides(ai_enabled)
        overrides["trade_start_date"] = START_DT.date().isoformat()
        engine, analysis_df, statistics = run_backtest(
            risk_ratio=BASE_RISK_RATIO,
            strategy_overrides=overrides,
            analysis_start=START_DT,
            analysis_end=END_DT,
            capital=OFFICIAL_STAGE78_CAPITAL,
            save_artifacts=False,
            include_start_year_sweep=False,
            file_prefix=f"{OUTPUT_PREFIX}_{variant}_main",
            chart_title=f"Stage225 78-1 AI ablation {variant}",
        )
        summary_rows.append(
            build_summary_row(
                statistics,
                variant=variant,
                ai_enabled=ai_enabled,
                analysis_start=START_DT,
                analysis_end=END_DT,
                official_version=OFFICIAL_STAGE78_VERSION,
                official_role=OFFICIAL_STAGE78_ROLE,
                model_tag=MODEL_TAG,
                capital=OFFICIAL_STAGE78_CAPITAL,
                base_risk_ratio=BASE_RISK_RATIO,
                total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                total_slippage=float(statistics.get("total_slippage", 0) or 0),
                total_commission=float(statistics.get("total_commission", 0) or 0),
                profit_days=int(statistics.get("profit_days", 0) or 0),
                loss_days=int(statistics.get("loss_days", 0) or 0),
            )
        )
        daily_frame = _daily_to_frame(analysis_df)
        daily_frame["variant"] = variant
        daily_frames.append(daily_frame)
        trade_frame = _trades_to_frame(engine)
        trade_frame["variant"] = variant
        trade_frames.append(trade_frame)
    return pd.DataFrame(summary_rows), pd.concat(daily_frames, ignore_index=True), pd.concat(trade_frames, ignore_index=True)


def run_multiperiod() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    for ai_enabled in (True, False):
        variant = _variant_label(ai_enabled)
        for window_name, display_label, group, analysis_start, analysis_end in WINDOWS:
            print(f"[stage225] multiperiod {variant} {window_name}", flush=True)
            overrides = _variant_overrides(ai_enabled)
            overrides["trade_start_date"] = analysis_start.date().isoformat()
            preload_start = max(PRELOAD_START_DT, analysis_start - timedelta(days=365))
            _, analysis_df, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=overrides,
                analysis_start=analysis_start,
                analysis_end=analysis_end,
                preload_start=preload_start,
                capital=OFFICIAL_STAGE78_CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
                file_prefix=f"{OUTPUT_PREFIX}_{variant}_{window_name}",
                chart_title=f"Stage225 78-1 {variant} {display_label}",
            )
            summary = build_summary_row(
                statistics,
                variant=variant,
                ai_enabled=ai_enabled,
                window_name=window_name,
                display_label=display_label,
                group=group,
                analysis_start=analysis_start,
                analysis_end=analysis_end,
                official_version=OFFICIAL_STAGE78_VERSION,
                official_role=OFFICIAL_STAGE78_ROLE,
                model_tag=MODEL_TAG,
                trade_start_date=analysis_start.date().isoformat(),
                preload_start=preload_start.date().isoformat(),
                capital=OFFICIAL_STAGE78_CAPITAL,
                base_risk_ratio=BASE_RISK_RATIO,
                total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                total_slippage=float(statistics.get("total_slippage", 0) or 0),
                total_commission=float(statistics.get("total_commission", 0) or 0),
                profit_days=int(statistics.get("profit_days", 0) or 0),
                loss_days=int(statistics.get("loss_days", 0) or 0),
            )
            summary_rows.append(summary)
            if analysis_df is not None and not analysis_df.empty:
                curve = analysis_df.copy().reset_index().rename(columns={"index": "date"})
                curve["date"] = pd.to_datetime(curve["date"])
                curve["variant"] = variant
                curve["window_name"] = window_name
                curve["display_label"] = display_label
                curve["group"] = group
                net_pnl = pd.to_numeric(curve["net_pnl"], errors="coerce").fillna(0.0)
                curve["rebased_balance"] = OFFICIAL_STAGE78_CAPITAL + net_pnl.cumsum()
                curve["normalized_nav"] = curve["rebased_balance"] / OFFICIAL_STAGE78_CAPITAL
                high = curve["rebased_balance"].cummax()
                curve["drawdown_pct"] = (curve["rebased_balance"] / high - 1.0) * 100.0
                curve_frames.append(curve)
    return pd.DataFrame(summary_rows), pd.concat(curve_frames, ignore_index=True)


def build_report(
    main_df: pd.DataFrame,
    multi_df: pd.DataFrame,
    slippage_df: pd.DataFrame,
    mc_summary_df: pd.DataFrame,
    paths: dict[str, str],
) -> str:
    comparison = main_df.pivot_table(index=[], columns="variant", values=["end_balance", "total_return_pct", "max_dd_percent", "sharpe_ratio", "total_trade_count", "total_slippage"], aggfunc="first")
    diff_rows: list[dict[str, Any]] = []
    for window_name, group in multi_df.groupby("window_name"):
        ai_on = group[group["variant"].eq("ai_on")]
        ai_off = group[group["variant"].eq("ai_off")]
        if ai_on.empty or ai_off.empty:
            continue
        on = ai_on.iloc[0]
        off = ai_off.iloc[0]
        diff_rows.append(
            {
                "window_name": window_name,
                "display_label": on.get("display_label", window_name),
                "ai_on_return_pct": on["total_return_pct"],
                "ai_off_return_pct": off["total_return_pct"],
                "return_delta_pct": on["total_return_pct"] - off["total_return_pct"],
                "ai_on_max_dd_pct": on["max_dd_percent"],
                "ai_off_max_dd_pct": off["max_dd_percent"],
                "ai_on_sharpe": on["sharpe_ratio"],
                "ai_off_sharpe": off["sharpe_ratio"],
                "ai_on_trades": on["total_trade_count"],
                "ai_off_trades": off["total_trade_count"],
            }
        )
    diff_df = pd.DataFrame(diff_rows)
    lines = [
        "# Stage225 Stage78-1 AI选品开关A/B实验报告",
        "",
        "## 口径",
        "",
        f"- 版本：`{OFFICIAL_STAGE78_VERSION}`",
        f"- 初始资金：`{OFFICIAL_STAGE78_CAPITAL:,.0f}`",
        "- 唯一变量：`enable_ai_product_pool_filter` 开/关",
        "- 其他条件：同一产品宇宙、FU卫星、无sizing封顶、风险四档、短空门禁、同日收盘撮合。",
        "- 反过拟合原则：本次只做消融审计，不根据结果调参。",
        "",
        "## 主回测",
        "",
        main_df[["variant", "end_balance", "total_return_pct", "max_dd_percent", "sharpe_ratio", "total_trade_count", "total_slippage"]].to_markdown(index=False),
        "",
        "## 多周期差异",
        "",
        diff_df.to_markdown(index=False) if not diff_df.empty else "_empty_",
        "",
        "## 滑点压力",
        "",
        slippage_df[["variant", "slippage_multiplier", "end_balance", "total_return_pct", "max_dd_percent", "sharpe_ratio", "total_slippage"]].to_markdown(index=False),
        "",
        "## Monte Carlo",
        "",
        mc_summary_df.to_markdown(index=False),
        "",
        "## 输出文件",
        "",
    ]
    for name, path in paths.items():
        lines.append(f"- {name}: `{path}`")
    return "\n".join(lines) + "\n"


def build_html(multi_df: pd.DataFrame, curves_df: pd.DataFrame) -> str:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=False, vertical_spacing=0.12, subplot_titles=("NAV", "Drawdown %"))
    for (variant, label), group in curves_df.groupby(["variant", "display_label"], sort=False):
        name = f"{variant} {label}"
        fig.add_trace(go.Scatter(x=group["date"], y=group["normalized_nav"], mode="lines", name=name), row=1, col=1)
        fig.add_trace(go.Scatter(x=group["date"], y=group["drawdown_pct"], mode="lines", name=f"{name} DD", showlegend=False), row=2, col=1)
    fig.update_layout(title="Stage225 Stage78-1 AI ON/OFF 多周期曲线", height=1000, template="plotly_white")
    return "\n".join(
        [
            "<!doctype html>",
            "<html><head><meta charset='utf-8'><title>Stage225 AI Ablation</title></head><body>",
            "<h1>Stage225 Stage78-1 AI ON/OFF 多周期曲线</h1>",
            multi_df.to_html(index=False, float_format=lambda value: f"{value:,.4f}", border=0),
            fig.to_html(full_html=False, include_plotlyjs="cdn"),
            "</body></html>",
        ]
    )


def main() -> None:
    assert_stage196_database_sentinels()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = build_official_stage78_manifest()
    main_df, daily_df, trades_df = run_main_variants()
    multi_df, curves_df = run_multiperiod()
    slippage_df = pd.concat([_slippage_stress(variant, daily_df[daily_df["variant"].eq(variant)]) for variant in ("ai_on", "ai_off")], ignore_index=True)

    supported_symbols = load_product_universe_symbols(str(manifest["product_universe_csv_path"]))
    metadata = build_contract_metadata(supported_symbols=supported_symbols)
    rng = np.random.default_rng(RNG_SEED)
    sim_frames: list[pd.DataFrame] = []
    for variant in ("ai_on", "ai_off"):
        daily_variant = daily_df[daily_df["variant"].eq(variant)].copy()
        trades_variant = trades_df[trades_df["variant"].eq(variant)].copy()
        returns = pd.to_numeric(daily_variant["return"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        round_trip_pnls = _build_round_trip_pnls(trades_variant, metadata["sizes"])
        sim_frames.append(_simulate_daily_block_bootstrap(returns, rng, variant))
        sim_frames.append(_simulate_trade_bootstrap(round_trip_pnls, rng, variant))
    mc_sim_df = pd.concat(sim_frames, ignore_index=True)
    mc_summary_df = _mc_summary(mc_sim_df)

    paths = {
        "main_summary": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_main_summary_{MODEL_TAG}.csv").resolve()),
        "main_daily": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_main_daily_{MODEL_TAG}.csv").resolve()),
        "main_trades": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_main_trades_{MODEL_TAG}.csv").resolve()),
        "multiperiod_summary": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_multiperiod_summary_{MODEL_TAG}.csv").resolve()),
        "multiperiod_curves": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_multiperiod_curves_{MODEL_TAG}.csv").resolve()),
        "slippage_stress": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_slippage_stress_{MODEL_TAG}.csv").resolve()),
        "mc_simulations": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_monte_carlo_simulations_{MODEL_TAG}.csv").resolve()),
        "mc_summary": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_monte_carlo_summary_{MODEL_TAG}.csv").resolve()),
        "report_md": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md").resolve()),
        "report_html": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.html").resolve()),
        "manifest": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.json").resolve()),
    }
    main_df.to_csv(paths["main_summary"], index=False, encoding="utf-8-sig")
    daily_df.to_csv(paths["main_daily"], index=False, encoding="utf-8-sig")
    trades_df.to_csv(paths["main_trades"], index=False, encoding="utf-8-sig")
    multi_df.to_csv(paths["multiperiod_summary"], index=False, encoding="utf-8-sig")
    curves_df.to_csv(paths["multiperiod_curves"], index=False, encoding="utf-8-sig")
    slippage_df.to_csv(paths["slippage_stress"], index=False, encoding="utf-8-sig")
    mc_sim_df.to_csv(paths["mc_simulations"], index=False, encoding="utf-8-sig")
    mc_summary_df.to_csv(paths["mc_summary"], index=False, encoding="utf-8-sig")
    Path(paths["report_md"]).write_text(build_report(main_df, multi_df, slippage_df, mc_summary_df, paths), encoding="utf-8")
    Path(paths["report_html"]).write_text(build_html(multi_df, curves_df), encoding="utf-8")
    Path(paths["manifest"]).write_text(
        json.dumps(
            {
                "model_tag": MODEL_TAG,
                "output_prefix": OUTPUT_PREFIX,
                "official_manifest": manifest,
                "ablation": {"only_variable": "enable_ai_product_pool_filter", "variants": ["ai_on", "ai_off"]},
                "paths": paths,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(paths, ensure_ascii=False, indent=2))
    print(main_df[["variant", "end_balance", "total_return_pct", "max_dd_percent", "sharpe_ratio", "total_trade_count"]].to_string(index=False))
    print(mc_summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
