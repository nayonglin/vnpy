from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

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
from run_qmt_roll_monte_carlo import RNG_SEED
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO
from run_qmt_roll_stage225_stage78_1_ai_ablation_suite import (
    _build_round_trip_pnls,
    _daily_to_frame,
    _mc_summary,
    _simulate_daily_block_bootstrap,
    _simulate_trade_bootstrap,
    _slippage_stress,
    _trades_to_frame,
)


MODEL_TAG = "stage227_risk_overlay_layered_profit_lock_v1"
OUTPUT_PREFIX = "qmt_roll_stage227_risk_overlay_layered_profit_lock"

WINDOWS: tuple[tuple[str, str, datetime, datetime], ...] = (
    ("full_2020_2026", "2020起点至今", START_DT, END_DT),
    ("since_2021", "2021起点至今", datetime(2021, 1, 1), END_DT),
    ("since_2022", "2022起点至今", datetime(2022, 1, 1), END_DT),
    ("since_2023", "2023起点至今", datetime(2023, 1, 1), END_DT),
    ("since_2024", "2024起点至今", datetime(2024, 1, 1), END_DT),
    ("since_2025", "2025起点至今", datetime(2025, 1, 1), END_DT),
    ("ytd_2026", "2026起点至今", datetime(2026, 1, 1), END_DT),
    ("phase_2020_2021", "2020-2021独立启动", datetime(2020, 1, 1), datetime(2021, 12, 31)),
    ("phase_2022_2023", "2022-2023独立启动", datetime(2022, 1, 1), datetime(2023, 12, 31)),
    ("phase_2024_2025", "2024-2025独立启动", datetime(2024, 1, 1), datetime(2025, 12, 31)),
    ("phase_2026_latest", "2026独立启动至最新", datetime(2026, 1, 1), END_DT),
)


def _variant_overrides(variant: str, analysis_start: datetime) -> dict[str, Any]:
    overrides = build_official_stage78_overrides()
    overrides["trade_start_date"] = analysis_start.date().isoformat()
    if variant == "layered_profit_lock_v1":
        overrides.update(
            {
                "enable_layered_profit_lock_sizing": True,
                "layered_profit_lock_base_equity": 1_000_000.0,
                "layered_profit_lock_start_equity": 2_000_000.0,
                "layered_profit_lock_ratio": 0.50,
            }
        )
    return overrides


def _run_window(variant: str, window_name: str, display_label: str, analysis_start: datetime, analysis_end: datetime) -> tuple[Any, pd.DataFrame, dict[str, Any]]:
    preload_start = max(PRELOAD_START_DT, analysis_start - timedelta(days=365))
    return run_backtest(
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=_variant_overrides(variant, analysis_start),
        analysis_start=analysis_start,
        analysis_end=analysis_end,
        preload_start=preload_start,
        capital=OFFICIAL_STAGE78_CAPITAL,
        save_artifacts=False,
        include_start_year_sweep=False,
        file_prefix=f"{OUTPUT_PREFIX}_{variant}_{window_name}",
        chart_title=f"Stage227 risk overlay {variant} {display_label}",
    )


def run_variants() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    daily_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    for variant in ("baseline_78_1", "layered_profit_lock_v1"):
        for window_name, display_label, analysis_start, analysis_end in WINDOWS:
            print(f"[stage227] {variant} {window_name}", flush=True)
            engine, analysis_df, statistics = _run_window(variant, window_name, display_label, analysis_start, analysis_end)
            summary_rows.append(
                build_summary_row(
                    statistics,
                    variant=variant,
                    window_name=window_name,
                    display_label=display_label,
                    analysis_start=analysis_start,
                    analysis_end=analysis_end,
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
            daily_frame["window_name"] = window_name
            daily_frames.append(daily_frame)
            if window_name == "full_2020_2026":
                trade_frame = _trades_to_frame(engine)
                trade_frame["variant"] = variant
                trade_frames.append(trade_frame)
    return pd.DataFrame(summary_rows), pd.concat(daily_frames, ignore_index=True), pd.concat(trade_frames, ignore_index=True)


def _comparison(summary_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, group in summary_df.groupby("window_name", sort=False):
        baseline = group[group["variant"].eq("baseline_78_1")]
        candidate = group[group["variant"].eq("layered_profit_lock_v1")]
        if baseline.empty or candidate.empty:
            continue
        a = baseline.iloc[0]
        c = candidate.iloc[0]
        rows.append(
            {
                "window_name": window_name,
                "display_label": c["display_label"],
                "baseline_return_pct": a["total_return_pct"],
                "candidate_return_pct": c["total_return_pct"],
                "return_delta_pct": c["total_return_pct"] - a["total_return_pct"],
                "baseline_max_dd_pct": a["max_dd_percent"],
                "candidate_max_dd_pct": c["max_dd_percent"],
                "max_dd_delta_pct": c["max_dd_percent"] - a["max_dd_percent"],
                "baseline_sharpe": a["sharpe_ratio"],
                "candidate_sharpe": c["sharpe_ratio"],
                "baseline_trades": a["total_trade_count"],
                "candidate_trades": c["total_trade_count"],
            }
        )
    return pd.DataFrame(rows)


def _build_report(summary_df: pd.DataFrame, comparison_df: pd.DataFrame, slippage_df: pd.DataFrame, mc_summary_df: pd.DataFrame, paths: dict[str, str]) -> str:
    lines = [
        "# Stage227 风险覆盖层：分层出金/权益锁定多周期验证",
        "",
        "## 口径",
        "",
        f"- 基准：`{OFFICIAL_STAGE78_VERSION}`",
        f"- 初始资金：`{OFFICIAL_STAGE78_CAPITAL:,.0f}`",
        "- A：`baseline_78_1`，保持78-1正式配置。",
        "- C：`layered_profit_lock_v1`，只启用分层出金/权益锁定sizing覆盖层。",
        "- 反过拟合原则：先做结构性覆盖层最小验证，不扫小数参数。",
        "",
        "## 窗口结果",
        "",
        summary_df[["variant", "window_name", "end_balance", "total_return_pct", "max_dd_percent", "sharpe_ratio", "total_trade_count", "total_slippage"]].to_markdown(index=False),
        "",
        "## A vs C差异",
        "",
        comparison_df.to_markdown(index=False),
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


def main() -> None:
    assert_stage196_database_sentinels()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = build_official_stage78_manifest()
    summary_df, daily_df, trades_df = run_variants()
    comparison_df = _comparison(summary_df)

    full_daily = daily_df[daily_df["window_name"].eq("full_2020_2026")]
    slippage_df = pd.concat(
        [_slippage_stress(variant, full_daily[full_daily["variant"].eq(variant)]) for variant in ("baseline_78_1", "layered_profit_lock_v1")],
        ignore_index=True,
    )

    supported_symbols = load_product_universe_symbols(str(manifest["product_universe_csv_path"]))
    metadata = build_contract_metadata(supported_symbols=supported_symbols)
    rng = np.random.default_rng(RNG_SEED)
    sim_frames: list[pd.DataFrame] = []
    for variant in ("baseline_78_1", "layered_profit_lock_v1"):
        daily_variant = full_daily[full_daily["variant"].eq(variant)].copy()
        trades_variant = trades_df[trades_df["variant"].eq(variant)].copy()
        returns = pd.to_numeric(daily_variant["return"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        round_trip_pnls = _build_round_trip_pnls(trades_variant, metadata["sizes"])
        sim_frames.append(_simulate_daily_block_bootstrap(returns, rng, variant))
        sim_frames.append(_simulate_trade_bootstrap(round_trip_pnls, rng, variant))
    mc_sim_df = pd.concat(sim_frames, ignore_index=True)
    mc_summary_df = _mc_summary(mc_sim_df)

    paths = {
        "summary": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv").resolve()),
        "daily": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv").resolve()),
        "trades": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv").resolve()),
        "comparison": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv").resolve()),
        "slippage_stress": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_slippage_stress_{MODEL_TAG}.csv").resolve()),
        "mc_simulations": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_monte_carlo_simulations_{MODEL_TAG}.csv").resolve()),
        "mc_summary": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_monte_carlo_summary_{MODEL_TAG}.csv").resolve()),
        "report_md": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md").resolve()),
        "manifest": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.json").resolve()),
    }
    summary_df.to_csv(paths["summary"], index=False, encoding="utf-8-sig")
    daily_df.to_csv(paths["daily"], index=False, encoding="utf-8-sig")
    trades_df.to_csv(paths["trades"], index=False, encoding="utf-8-sig")
    comparison_df.to_csv(paths["comparison"], index=False, encoding="utf-8-sig")
    slippage_df.to_csv(paths["slippage_stress"], index=False, encoding="utf-8-sig")
    mc_sim_df.to_csv(paths["mc_simulations"], index=False, encoding="utf-8-sig")
    mc_summary_df.to_csv(paths["mc_summary"], index=False, encoding="utf-8-sig")
    Path(paths["report_md"]).write_text(_build_report(summary_df, comparison_df, slippage_df, mc_summary_df, paths), encoding="utf-8")
    Path(paths["manifest"]).write_text(
        json.dumps(
            {
                "model_tag": MODEL_TAG,
                "output_prefix": OUTPUT_PREFIX,
                "official_manifest": manifest,
                "line_id": "futures_trend_risk_overlay",
                "arms": {
                    "A": "baseline_78_1",
                    "C": "layered_profit_lock_v1",
                },
                "candidate_overrides": _variant_overrides("layered_profit_lock_v1", START_DT),
                "paths": paths,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(paths, ensure_ascii=False, indent=2))
    print(summary_df[["variant", "window_name", "end_balance", "total_return_pct", "max_dd_percent", "sharpe_ratio", "total_trade_count"]].to_string(index=False))
    print(mc_summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
