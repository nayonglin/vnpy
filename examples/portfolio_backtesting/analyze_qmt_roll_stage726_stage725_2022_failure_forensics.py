from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660
import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719
import analyze_qmt_roll_stage725_drawdown_gated_directional_edge60_exemption as s725
from qmt_roll_official_live_config import OFFICIAL_LIVE_CAPITAL, OFFICIAL_LIVE_PROFILE_NAME, OFFICIAL_LIVE_VERSION
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
from run_qmt_alignment_backtest import (
    build_entry_candidate_snapshots_df,
    build_entry_risk_diagnostics_df,
    build_positions_df,
    build_trades_df,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage726_stage725_2022_failure_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage726_stage725_2022_failure_forensics"
LINE_ID = "futures_trend_winner_trade_forensics"

BASE_VARIANT = OFFICIAL_LIVE_PROFILE_NAME
CANDIDATE_VARIANT = s725.CANDIDATE_VARIANT
ANALYSIS_START = pd.Timestamp("2022-01-01")
ANALYSIS_END = pd.Timestamp("2023-12-31")

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
RECOVERY_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_recovery_lots_{MODEL_TAG}.csv"
PRODUCT_SIGNAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_signal_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _run_engine_for_spec(
    spec: s653.ForcedVariant,
    metadata: dict[str, Any],
) -> Any:
    original_start = s653.s517.START_DT
    original_end = s653.s517.END_DT
    try:
        s653.s517.START_DT = ANALYSIS_START.to_pydatetime()
        s653.s517.END_DT = ANALYSIS_END.to_pydatetime()
        s653.s517.assert_stage196_database_sentinels()
        s653.s517.s506._patch_stage506_raw_roots()
        c3_overrides = s513._c3_overrides(s653.s517.START_DT)
        preload_start = max(s653.s517.PRELOAD_START_DT, s653.s517.START_DT - timedelta(days=365))
        _, open_map = s653.s517.s506.s501._seed_proxy_maps()
        engine = s653.s517.s506.s502.ConfirmedDailyNextRealOpenEngine(open_map)
        engine.output = lambda msg: None
        engine.set_parameters(
            vt_symbols=metadata["vt_symbols"],
            interval=s653.s517.Interval.DAILY,
            start=preload_start,
            end=s653.s517.END_DT,
            rates=metadata["rates"],
            slippages=metadata["slippages"],
            sizes=metadata["sizes"],
            priceticks=metadata["priceticks"],
            capital=spec.capital.c3_capital,
        )
        setting = s653.s517.build_roll_setting(
            metadata["margin_ratios"],
            risk_ratio=s653.s517.BASE_RISK_RATIO * float(spec.capital.risk_multiplier),
            strategy_overrides=c3_overrides,
        )
        setting["capital_base"] = spec.capital.c3_capital
        setting.update(spec.overrides)
        engine.add_strategy(QmtRollPortfolioStrategy, setting)
        engine.load_data()
        engine.run_backtesting()
        engine.calculate_result()
        return engine
    finally:
        s653.s517.START_DT = original_start
        s653.s517.END_DT = original_end


def _extract_frames(engine: Any, spec: s653.ForcedVariant, metadata: dict[str, Any]) -> dict[str, pd.DataFrame]:
    frames = {
        "trades": build_trades_df(engine),
        "positions": build_positions_df(engine),
        "entry_risk": build_entry_risk_diagnostics_df(engine),
        "entry_candidates": build_entry_candidate_snapshots_df(engine),
    }
    frames["closed_lots"] = s719._build_closed_lots(
        frames["trades"],
        frames["entry_risk"],
        frames["entry_candidates"],
        metadata,
    )
    for frame in frames.values():
        if frame.empty:
            continue
        frame["variant"] = spec.capital.variant
        frame["label"] = spec.capital.label
        frame["official_live_version"] = OFFICIAL_LIVE_VERSION
    return frames


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if not np.isfinite(result):
        return default
    return result


def _summarize_closed_lots(closed_lots: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if closed_lots.empty:
        return pd.DataFrame()
    data = closed_lots.copy()
    data["realized_pnl"] = pd.to_numeric(data.get("realized_pnl"), errors="coerce").fillna(0.0)
    data["r_multiple"] = pd.to_numeric(data.get("r_multiple"), errors="coerce")
    data["volume"] = pd.to_numeric(data.get("volume"), errors="coerce").fillna(0.0)
    data["streak_entry_structure_risk_recovery_applied"] = pd.to_numeric(
        data.get("streak_entry_structure_risk_recovery_applied", 0),
        errors="coerce",
    ).fillna(0.0)
    data["risk_multiplier"] = pd.to_numeric(data.get("risk_multiplier", np.nan), errors="coerce")
    for variant, group in data.groupby("variant", sort=False):
        recovery = group[group["streak_entry_structure_risk_recovery_applied"].eq(1.0)]
        throttle = group[group["risk_multiplier"].le(0.100001)]
        rows.append(
            {
                "variant": variant,
                "closed_lot_count": int(len(group)),
                "total_realized_pnl": float(group["realized_pnl"].sum()),
                "avg_r": float(group["r_multiple"].mean(skipna=True)),
                "win_rate_pct": float(group["realized_pnl"].gt(0.0).mean() * 100.0),
                "recovery_lot_count": int(len(recovery)),
                "recovery_total_realized_pnl": float(recovery["realized_pnl"].sum()),
                "recovery_avg_r": float(recovery["r_multiple"].mean(skipna=True)) if len(recovery) else 0.0,
                "recovery_win_rate_pct": float(recovery["realized_pnl"].gt(0.0).mean() * 100.0)
                if len(recovery)
                else 0.0,
                "risk_floor_lot_count": int(len(throttle)),
                "risk_floor_total_realized_pnl": float(throttle["realized_pnl"].sum()),
            }
        )
    return pd.DataFrame(rows)


def _product_signal_summary(closed_lots: pd.DataFrame) -> pd.DataFrame:
    if closed_lots.empty:
        return pd.DataFrame()
    data = closed_lots.copy()
    data = data[data["variant"].astype(str).eq(CANDIDATE_VARIANT)]
    data["streak_entry_structure_risk_recovery_applied"] = pd.to_numeric(
        data.get("streak_entry_structure_risk_recovery_applied", 0),
        errors="coerce",
    ).fillna(0.0)
    data = data[data["streak_entry_structure_risk_recovery_applied"].eq(1.0)]
    if data.empty:
        return pd.DataFrame()
    data["realized_pnl"] = pd.to_numeric(data.get("realized_pnl"), errors="coerce").fillna(0.0)
    data["r_multiple"] = pd.to_numeric(data.get("r_multiple"), errors="coerce")
    rows = []
    for (product, signal), group in data.groupby(["product", "signal"], dropna=False):
        rows.append(
            {
                "product": product,
                "signal": signal,
                "count": int(len(group)),
                "total_realized_pnl": float(group["realized_pnl"].sum()),
                "avg_r": float(group["r_multiple"].mean(skipna=True)),
                "win_rate_pct": float(group["realized_pnl"].gt(0.0).mean() * 100.0),
                "first_entry": str(pd.to_datetime(group["entry_date"], errors="coerce").min().date()),
                "last_entry": str(pd.to_datetime(group["entry_date"], errors="coerce").max().date()),
            }
        )
    return pd.DataFrame(rows).sort_values(["total_realized_pnl", "count"], ascending=[True, False])


def _decision(summary: pd.DataFrame, recovery_lots: pd.DataFrame, product_signal: pd.DataFrame) -> dict[str, Any]:
    candidate_summary = summary[summary["variant"].eq(CANDIDATE_VARIANT)]
    base_summary = summary[summary["variant"].eq(BASE_VARIANT)]
    base_recovery_count = int(base_summary["recovery_lot_count"].iloc[0]) if not base_summary.empty else 0
    base_closed_lot_count = int(base_summary["closed_lot_count"].iloc[0]) if not base_summary.empty else 0
    candidate_closed_lot_count = (
        int(candidate_summary["closed_lot_count"].iloc[0]) if not candidate_summary.empty else 0
    )
    candidate_recovery_count = int(candidate_summary["recovery_lot_count"].iloc[0]) if not candidate_summary.empty else 0
    candidate_recovery_pnl = (
        float(candidate_summary["recovery_total_realized_pnl"].iloc[0]) if not candidate_summary.empty else 0.0
    )
    unique_products = int(recovery_lots["product"].nunique()) if not recovery_lots.empty else 0
    sample_too_small = candidate_recovery_count < 30 or unique_products < 8
    direct_loss_source = candidate_recovery_pnl < 0.0
    official_sleeve_removed = base_recovery_count > 0 and candidate_recovery_count == 0
    if official_sleeve_removed:
        label = "stage725_failure_forensics_official_sleeve_removed"
    elif sample_too_small:
        label = "stage725_failure_forensics_sample_too_small_no_selector"
    elif direct_loss_source:
        label = "stage725_failure_forensics_recovery_lift_negative_no_promotion"
    else:
        label = "stage725_failure_forensics_needs_deeper_path_analysis"
    return {
        "stage": "Stage008",
        "script_stage": "Stage726",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "analysis_window": {
            "start": ANALYSIS_START.date().isoformat(),
            "end": ANALYSIS_END.date().isoformat(),
        },
        "baseline": BASE_VARIANT,
        "candidate": CANDIDATE_VARIANT,
        "decision": label,
        "candidate_recovery_lot_count": candidate_recovery_count,
        "candidate_recovery_total_realized_pnl": candidate_recovery_pnl,
        "candidate_recovery_unique_products": unique_products,
        "base_recovery_lot_count": base_recovery_count,
        "base_closed_lot_count": base_closed_lot_count,
        "candidate_closed_lot_count": candidate_closed_lot_count,
        "closed_lot_delta_vs_base": candidate_closed_lot_count - base_closed_lot_count,
        "official_sleeve_removed": official_sleeve_removed,
        "selector_training_viable": bool(not sample_too_small and not direct_loss_source),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "entry_risk": str(ENTRY_RISK_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "trades": str(TRADES_PATH),
            "closed_lots": str(CLOSED_LOTS_PATH),
            "recovery_lots": str(RECOVERY_LOTS_PATH),
            "product_signal": str(PRODUCT_SIGNAL_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _write_report(
    summary: pd.DataFrame,
    recovery_lots: pd.DataFrame,
    product_signal: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    columns = [
        "variant",
        "closed_lot_count",
        "total_realized_pnl",
        "avg_r",
        "win_rate_pct",
        "recovery_lot_count",
        "recovery_total_realized_pnl",
        "recovery_avg_r",
        "recovery_win_rate_pct",
        "risk_floor_lot_count",
        "risk_floor_total_realized_pnl",
    ]
    recovery_cols = [
        "entry_date",
        "exit_date",
        "product",
        "vt_symbol",
        "direction",
        "signal",
        "volume",
        "realized_pnl",
        "r_multiple",
        "risk_multiplier",
        "portfolio_drawdown_pct",
        "selected_volume",
        "streak_entry_structure_risk_recovery_directional_edge_close_position",
    ]
    lines = [
        "# Stage726 Stage725 2022-2023 Failure Forensics",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 窗口：`{ANALYSIS_START.date().isoformat()}` 至 `{ANALYSIS_END.date().isoformat()}`",
        "- 性质：只读法证，不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## Summary",
        "",
        _md_table(summary[columns] if not summary.empty else summary),
        "",
        "## Candidate Recovery Lots",
        "",
        _md_table(recovery_lots[[c for c in recovery_cols if c in recovery_lots.columns]], max_rows=80),
        "",
        "## Product Signal Summary",
        "",
        _md_table(product_signal, max_rows=80),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- candidate_recovery_lot_count：`{decision['candidate_recovery_lot_count']}`",
        f"- candidate_recovery_total_realized_pnl：`{decision['candidate_recovery_total_realized_pnl']:.2f}`",
        f"- candidate_recovery_unique_products：`{decision['candidate_recovery_unique_products']}`",
        f"- base_recovery_lot_count：`{decision['base_recovery_lot_count']}`",
        f"- closed_lot_delta_vs_base：`{decision['closed_lot_delta_vs_base']}`",
        f"- official_sleeve_removed：`{decision['official_sleeve_removed']}`",
        f"- selector_training_viable：`{decision['selector_training_viable']}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    metadata = s513._metadata()
    specs = [
        s660._official_spec(metadata),
        s725._candidate_spec(metadata),
    ]
    all_frames: dict[str, list[pd.DataFrame]] = {
        "trades": [],
        "positions": [],
        "entry_risk": [],
        "entry_candidates": [],
        "closed_lots": [],
    }
    for spec in specs:
        print(f"[stage726] running {spec.capital.variant}", flush=True)
        engine = _run_engine_for_spec(replace(spec), metadata)
        frames = _extract_frames(engine, spec, metadata)
        for name, frame in frames.items():
            if not frame.empty:
                all_frames[name].append(frame)

    combined = {
        name: pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
        for name, frames in all_frames.items()
    }
    summary = _summarize_closed_lots(combined["closed_lots"])
    recovery_lots = combined["closed_lots"].copy()
    if not recovery_lots.empty:
        recovery_lots["streak_entry_structure_risk_recovery_applied"] = pd.to_numeric(
            recovery_lots.get("streak_entry_structure_risk_recovery_applied", 0),
            errors="coerce",
        ).fillna(0.0)
        recovery_lots = recovery_lots[
            recovery_lots["variant"].astype(str).eq(CANDIDATE_VARIANT)
            & recovery_lots["streak_entry_structure_risk_recovery_applied"].eq(1.0)
        ].copy()
        recovery_lots["realized_pnl"] = pd.to_numeric(recovery_lots.get("realized_pnl"), errors="coerce").fillna(0.0)
        recovery_lots.sort_values(["entry_date", "product", "signal"], inplace=True)
    product_signal = _product_signal_summary(combined["closed_lots"])
    decision = _decision(summary, recovery_lots, product_signal)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    combined["entry_risk"].to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    combined["entry_candidates"].to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    combined["trades"].to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    combined["closed_lots"].to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
    recovery_lots.to_csv(RECOVERY_LOTS_PATH, index=False, encoding="utf-8-sig")
    product_signal.to_csv(PRODUCT_SIGNAL_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(s650._json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, recovery_lots, product_signal, decision)
    print(json.dumps(s650._json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
