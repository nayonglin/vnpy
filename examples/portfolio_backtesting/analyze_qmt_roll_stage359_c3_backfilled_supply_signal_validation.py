from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

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
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO
from run_qmt_roll_stage310_stage78_1_drawdown_gate_engine_validation import _pressure040_overrides


MODEL_TAG = "stage359_c3_backfilled_supply_signal_validation_v1"
OUTPUT_PREFIX = "qmt_roll_stage359_c3_backfilled_supply_signal_validation"
LINE_ID = "futures_trend_drawdown30_preserve_return"

CURRENT_SIGNAL_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage316_supply_demand_quality_probe_external_signals_stage316_supply_demand_quality_probe_v1.csv"
)
BACKFILLED_SIGNAL_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage358_supply_demand_backfill_2020_2022_external_signals_stage358_supply_demand_backfill_2020_2022_v1.csv"
)
COMBINED_SIGNAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combined_external_signals_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

TARGET_MAX_DD_PCT = -30.0
RETURN_RETENTION_GATE_PCT = 80.0


@dataclass(frozen=True)
class Profile:
    name: str
    label: str
    overrides: dict[str, Any]


WINDOWS: tuple[tuple[str, str, datetime, datetime], ...] = (
    ("full_2020_2026", "2020起点至今", START_DT, END_DT),
    ("start_2021", "2021起点至今", datetime(2021, 1, 1), END_DT),
    ("start_2022", "2022起点至今", datetime(2022, 1, 1), END_DT),
    ("since_2023", "2023起点至今", datetime(2023, 1, 1), END_DT),
    ("phase_2024_2025", "2024-2025独立启动", datetime(2024, 1, 1), datetime(2025, 12, 31)),
    ("ytd_2026", "2026年初至今", datetime(2026, 1, 1), END_DT),
)


def _merge(*items: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for item in items:
        merged.update(item)
    return merged


def _supply_demand_headwind_overrides(signal_path: Path) -> dict[str, Any]:
    return {
        "enable_supply_demand_headwind_filter": True,
        "supply_demand_signal_path": str(signal_path),
        "supply_demand_headwind_threshold": -0.35,
        "supply_demand_headwind_weight_floor": 0.0,
        "supply_demand_headwind_max_age_days": 7,
    }


def _build_combined_signal_file() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for source_name, path in (("backfilled_2020_2022", BACKFILLED_SIGNAL_PATH), ("current_2023_2026", CURRENT_SIGNAL_PATH)):
        if not path.exists():
            raise FileNotFoundError(f"missing signal file: {path}")
        frame = pd.read_csv(path)
        frame["signal_source_window"] = source_name
        frames.append(frame)
    combined = pd.concat(frames, ignore_index=True)
    combined["available_datetime"] = pd.to_datetime(combined["available_datetime"], errors="coerce")
    combined = combined[combined["available_datetime"].notna()].copy()
    combined.sort_values(["available_datetime", "product_vt_symbol", "direction", "signal_source_window"], inplace=True)
    dedupe_cols = ["available_datetime", "product_vt_symbol", "direction", "source_type", "text_hash"]
    combined.drop_duplicates(subset=dedupe_cols, keep="last", inplace=True)
    combined["available_datetime"] = combined["available_datetime"].dt.strftime("%Y-%m-%dT%H:%M:%S")
    combined.to_csv(COMBINED_SIGNAL_PATH, index=False, encoding="utf-8-sig")
    return combined


PROFILES: tuple[Profile, ...] = (
    Profile("C_pressure040", "热度降暴露0.40", _pressure040_overrides()),
    Profile(
        "C3_existing_2023plus",
        "C3现有供需2023+",
        _merge(_pressure040_overrides(), _supply_demand_headwind_overrides(CURRENT_SIGNAL_PATH)),
    ),
    Profile(
        "C3_backfilled_2020_2026",
        "C3补齐供需2020-2026",
        _merge(_pressure040_overrides(), _supply_demand_headwind_overrides(COMBINED_SIGNAL_PATH)),
    ),
)


def _profile_overrides(profile: Profile, analysis_start: datetime) -> dict[str, Any]:
    overrides = build_official_stage78_overrides()
    overrides["trade_start_date"] = analysis_start.date().isoformat()
    overrides.update(profile.overrides)
    return overrides


def _run_profile(
    profile: Profile,
    window_name: str,
    display_label: str,
    analysis_start: datetime,
    analysis_end: datetime,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    preload_start = max(PRELOAD_START_DT, analysis_start - timedelta(days=365))
    _, analysis_df, statistics = run_backtest(
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=_profile_overrides(profile, analysis_start),
        analysis_start=analysis_start,
        analysis_end=analysis_end,
        preload_start=preload_start,
        capital=OFFICIAL_STAGE78_CAPITAL,
        save_artifacts=False,
        include_start_year_sweep=False,
        file_prefix=f"{OUTPUT_PREFIX}_{profile.name}_{window_name}",
        chart_title=f"Stage359 {profile.label} {display_label}",
    )
    return analysis_df, statistics


def _run_suite() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    for window_name, display_label, analysis_start, analysis_end in WINDOWS:
        for profile in PROFILES:
            print(f"[stage359] {window_name} {profile.name}", flush=True)
            analysis_df, statistics = _run_profile(profile, window_name, display_label, analysis_start, analysis_end)
            summary_rows.append(
                build_summary_row(
                    statistics,
                    analysis_start=analysis_start,
                    analysis_end=analysis_end,
                    variant=profile.name,
                    display_label=profile.label,
                    window_name=window_name,
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
            if analysis_df is not None and not analysis_df.empty:
                curve_df = analysis_df[["balance"]].reset_index().rename(columns={"index": "date"})
                curve_df["date"] = pd.to_datetime(curve_df["date"])
                curve_df["variant"] = profile.name
                curve_df["display_label"] = profile.label
                curve_df["window_name"] = window_name
                first_balance = float(curve_df["balance"].iloc[0] or OFFICIAL_STAGE78_CAPITAL)
                curve_df["normalized_nav"] = curve_df["balance"] / max(1e-9, first_balance)
                curve_frames.append(curve_df)
    summary_df = pd.DataFrame(summary_rows)
    curves_df = pd.concat(curve_frames, ignore_index=True) if curve_frames else pd.DataFrame()
    return summary_df, curves_df


def _comparison(summary_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, group in summary_df.groupby("window_name", sort=False):
        pressure = group[group["variant"].eq("C_pressure040")]
        existing = group[group["variant"].eq("C3_existing_2023plus")]
        backfilled = group[group["variant"].eq("C3_backfilled_2020_2026")]
        if pressure.empty or existing.empty or backfilled.empty:
            continue
        p = pressure.iloc[0]
        old = existing.iloc[0]
        new = backfilled.iloc[0]
        old_return = float(old["total_return_pct"])
        new_return = float(new["total_return_pct"])
        pressure_return = float(p["total_return_pct"])
        rows.append(
            {
                "window_name": window_name,
                "pressure_return_pct": pressure_return,
                "existing_c3_return_pct": old_return,
                "backfilled_c3_return_pct": new_return,
                "retention_vs_existing_pct": new_return / old_return * 100.0 if old_return > 0 else np.nan,
                "retention_vs_pressure_pct": new_return / pressure_return * 100.0 if pressure_return > 0 else np.nan,
                "pressure_max_dd_pct": float(p["max_dd_percent"]),
                "existing_c3_max_dd_pct": float(old["max_dd_percent"]),
                "backfilled_c3_max_dd_pct": float(new["max_dd_percent"]),
                "dd_improvement_vs_existing_pct": float(new["max_dd_percent"]) - float(old["max_dd_percent"]),
                "dd_improvement_vs_pressure_pct": float(new["max_dd_percent"]) - float(p["max_dd_percent"]),
                "existing_c3_sharpe": float(old["sharpe_ratio"]),
                "backfilled_c3_sharpe": float(new["sharpe_ratio"]),
                "existing_c3_trades": int(old["total_trade_count"]),
                "backfilled_c3_trades": int(new["total_trade_count"]),
                "existing_c3_slippage": float(old["total_slippage"]),
                "backfilled_c3_slippage": float(new["total_slippage"]),
                "dd_ok": int(float(new["max_dd_percent"]) >= TARGET_MAX_DD_PCT),
                "return_ok": int((new_return / old_return * 100.0 if old_return > 0 else 0.0) >= RETURN_RETENTION_GATE_PCT),
            }
        )
    return pd.DataFrame(rows)


def _decision(comparison_df: pd.DataFrame, combined_signal_rows: int) -> dict[str, Any]:
    full = comparison_df[comparison_df["window_name"].eq("full_2020_2026")]
    start_2021 = comparison_df[comparison_df["window_name"].eq("start_2021")]
    if full.empty or start_2021.empty:
        decision = "fail_missing_core_windows"
    else:
        full_row = full.iloc[0]
        start_2021_row = start_2021.iloc[0]
        if int(full_row["dd_ok"]) and int(full_row["return_ok"]) and float(start_2021_row["backfilled_c3_max_dd_pct"]) >= TARGET_MAX_DD_PCT:
            decision = "candidate_requires_multiperiod_slippage_validation"
        else:
            decision = "fail_backfilled_supply_does_not_solve_drawdown30"
    return {
        "decision": decision,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "combined_signal_rows": int(combined_signal_rows),
        "target_max_dd_pct": TARGET_MAX_DD_PCT,
        "return_retention_gate_pct": RETURN_RETENTION_GATE_PCT,
        "full": full.to_dict("records"),
        "start_2021": start_2021.to_dict("records"),
    }


def _build_report(summary_df: pd.DataFrame, comparison_df: pd.DataFrame, decision: dict[str, Any]) -> str:
    full = summary_df[summary_df["window_name"].eq("full_2020_2026")].copy()
    lines = [
        "# Stage359 C3补齐供需信号真实引擎验证",
        "",
        "## 定位",
        "",
        "- 合并 Stage358 2020-2022 与 Stage316 2023-2026 供需信号。",
        "- 固定供需强逆风阈值 `-0.35`，不调公式、不调权重、不改 AI 池和品种池。",
        "- 对比 `C_pressure040`、现有 C3、补齐供需后的 C3。",
        "",
        "## 全样本结果",
        "",
        to_markdown_table(
            full[
                [
                    "variant",
                    "total_return_pct",
                    "max_dd_percent",
                    "sharpe_ratio",
                    "total_trade_count",
                    "total_slippage",
                    "win_ratio_pct",
                ]
            ]
        ),
        "",
        "## 多窗口对比",
        "",
        to_markdown_table(comparison_df),
        "",
        "## 判定",
        "",
        f"- `{decision['decision']}`",
        "",
        "## 反思",
        "",
        "- 是否过拟合：否。只补点时化历史供需信号，阈值和规则冻结。",
        "- 是否继续有价值：若未压低 full/start_2021 回撤，则当前供需补齐路线停止；若压低且保收益，再进入滑点压力。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    assert_stage196_database_sentinels()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    combined_signals = _build_combined_signal_file()
    summary_df, curves_df = _run_suite()
    comparison_df = _comparison(summary_df)
    decision = _decision(comparison_df, len(combined_signals))

    summary_df.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curves_df.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    comparison_df.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(summary_df, comparison_df, decision), encoding="utf-8")
    manifest = build_official_stage78_manifest()
    manifest.update(
        {
            "output_prefix": OUTPUT_PREFIX,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "combined_signal_path": str(COMBINED_SIGNAL_PATH),
            "current_signal_path": str(CURRENT_SIGNAL_PATH),
            "backfilled_signal_path": str(BACKFILLED_SIGNAL_PATH),
            "decision": decision,
        }
    )
    manifest_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
