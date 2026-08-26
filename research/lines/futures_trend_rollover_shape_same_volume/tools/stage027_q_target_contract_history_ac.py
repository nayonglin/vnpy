from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
sys.path.insert(0, str(PORTFOLIO_DIR))

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513  # noqa: E402
import analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac as s827  # noqa: E402
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901  # noqa: E402
import qmt_roll_candidate_stage027_target_contract_history_config as candidate_cfg  # noqa: E402
import qmt_roll_official_live_config as live_cfg  # noqa: E402
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy  # noqa: E402


LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage027"
START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-08-25")

A_PROFILE = "stage027_A_formal_q_backwards_ratio_continuous"
C_PROFILE = "stage027_C_formal_q_target_contract_only"
ARMS: tuple[dict[str, str], ...] = (
    {
        "arm": "A",
        "profile": A_PROFILE,
        "label": "A: 当前正式 Q（旧主力复权连续历史）",
        "plot_label": "A Formal Q (back-adjusted old contract)",
        "color": "#2563eb",
    },
    {
        "arm": "C",
        "profile": C_PROFILE,
        "label": "C: 正式 Q + 新主力自身日K形态",
        "plot_label": "C New-contract-only history",
        "color": "#dc2626",
    },
)

SUMMARY_PATH = OUTPUT_DIR / "stage027_ac_summary.csv"
COMPARISON_PATH = OUTPUT_DIR / "stage027_ac_comparison.csv"
CURVE_PATH = OUTPUT_DIR / "stage027_ac_curve.csv"
ROLLOVER_PATH = OUTPUT_DIR / "stage027_rollover_diagnostics.csv"
TRADES_PATH = OUTPUT_DIR / "stage027_trades.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / "stage027_trade_events.csv"
DECISION_PATH = OUTPUT_DIR / "stage027_decision.json"
CHART_PATH = OUTPUT_DIR / "stage027_full_period_equity_ac.png"


def build_arm_overrides(arm: str) -> dict[str, Any]:
    if arm == "A":
        return live_cfg.build_official_live_strategy_overrides()
    if arm == "C":
        return candidate_cfg.build_candidate_overrides()
    raise ValueError(f"unknown stage027 arm: {arm}")


def override_diff() -> dict[str, tuple[Any, Any]]:
    baseline = build_arm_overrides("A")
    candidate = build_arm_overrides("C")
    keys = set(baseline) | set(candidate)
    return {
        key: (baseline.get(key), candidate.get(key))
        for key in sorted(keys)
        if baseline.get(key) != candidate.get(key)
    }


def _assert_base_commit_is_ancestor() -> None:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", candidate_cfg.BASE_COMMIT, "HEAD"],
        cwd=PROJECT_DIR,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "stage027_base_commit_not_ancestor: "
            f"base={candidate_cfg.BASE_COMMIT} stderr={result.stderr.strip()}"
        )


def _run_arm(
    arm: dict[str, str],
    metadata: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    original_builder = s901.build_official_live_strategy_overrides
    try:
        s901.build_official_live_strategy_overrides = lambda: build_arm_overrides(arm["arm"])
        combined, frames, live_spec = s901._run_live_c9(metadata, START, END)
    finally:
        s901.build_official_live_strategy_overrides = original_builder

    capital = replace(
        live_spec.capital,
        variant=arm["profile"],
        label=arm["label"],
    )
    metric_spec = replace(live_spec, capital=capital, profile=arm["profile"])
    summary, curve = s827._metric(
        {"profile": arm["profile"], "spec": metric_spec},
        combined,
    )
    summary["experiment_arm"] = arm["arm"]
    summary["window_name"] = "full_2018_20260825"
    summary["window_label"] = "2018-01-01 independent start to 2026-08-25"
    curve["experiment_arm"] = arm["arm"]
    for frame in frames.values():
        if frame.empty:
            continue
        frame["experiment_arm"] = arm["arm"]
    return summary, curve, frames


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "max_broker10_margin_to_equity_pct",
        "days_over_100pct",
    ]
    baseline = summary[summary["experiment_arm"].eq("A")].iloc[0]
    candidate = summary[summary["experiment_arm"].eq("C")].iloc[0]
    row: dict[str, Any] = {"comparison": "A_vs_C", "baseline": A_PROFILE, "candidate": C_PROFILE}
    for metric in metrics:
        a_value = float(baseline[metric])
        c_value = float(candidate[metric])
        row[f"A_{metric}"] = a_value
        row[f"C_{metric}"] = c_value
        row[f"delta_{metric}"] = c_value - a_value
    row["slippage_ratio_C_over_A"] = (
        float(candidate["total_slippage"]) / float(baseline["total_slippage"])
        if float(baseline["total_slippage"]) > 0
        else np.nan
    )
    return pd.DataFrame([row])


def _jm2701_database_acceptance() -> dict[str, Any]:
    database_path = PROJECT_DIR / ".vntrader" / "database.db"
    query = """
        SELECT datetime, open_price, high_price, low_price, close_price, volume, open_interest
        FROM dbbardata
        WHERE lower(symbol) = 'jm2701'
          AND exchange = 'DCE'
          AND interval = 'd'
          AND datetime <= '2026-08-19 23:59:59'
        ORDER BY datetime
    """
    with sqlite3.connect(database_path) as connection:
        bars = pd.read_sql_query(query, connection)
    if len(bars) < 40:
        raise RuntimeError(f"stage027_jm2701_database_history_insufficient: {len(bars)}")

    candidate_overrides = build_arm_overrides("C")
    if "research_exact_array_manager_size" not in candidate_overrides:
        raise RuntimeError("stage027_exact_array_manager_size_missing")
    array_manager_size = int(candidate_overrides["research_exact_array_manager_size"])
    history = bars.tail(array_manager_size).rename(
        columns={
            "open_price": "open",
            "high_price": "high",
            "low_price": "low",
            "close_price": "close",
        }
    )
    strategy = QmtRollPortfolioStrategy.__new__(QmtRollPortfolioStrategy)
    strategy.ma_short = 5
    strategy.ma_mid = 10
    strategy.ma_long = 20
    strategy.ma_extra_long = 40
    strategy.long_entry_enabled = True
    strategy.short_entry_enabled = True
    snapshot = strategy._rollover_shape_continuation_snapshot("long", history)
    return {
        "database_path": str(database_path),
        "contract": "jm2701.DCE",
        "cutoff": "2026-08-19",
        "database_bar_count": int(len(bars)),
        "first_bar_date": str(pd.Timestamp(bars.iloc[0]["datetime"]).date()),
        "last_bar_date": str(pd.Timestamp(bars.iloc[-1]["datetime"]).date()),
        "array_manager_size": array_manager_size,
        "strategy_history_bar_count": int(len(history)),
        **snapshot,
        "expected_long_rollover_action": "reopen" if int(snapshot["allowed"]) else "skip",
        "pass": bool(
            len(bars) == 79
            and len(history) >= 40
            and int(snapshot["bullish_alignment"]) == 0
            and int(snapshot["allowed"]) == 0
        ),
    }


def _rollover_contract(diagnostics: pd.DataFrame) -> dict[str, Any]:
    candidate = diagnostics[diagnostics["experiment_arm"].eq("C")].copy()
    if candidate.empty:
        raise RuntimeError("stage027_candidate_rollover_diagnostics_missing")

    numeric_target = pd.to_numeric(candidate["target_observed_bar_count"], errors="coerce")
    numeric_source = pd.to_numeric(candidate["source_observed_bar_count"], errors="coerce")
    ratios = pd.to_numeric(candidate["roll_adjustment_ratio"], errors="coerce")
    targeted = candidate[candidate["status"].astype(str).eq("targeted")]
    insufficient = candidate[candidate["reason"].astype(str).eq("insufficient_indicator_history")]
    jm_database_acceptance = _jm2701_database_acceptance()

    contract = {
        "diagnostic_count": int(len(candidate)),
        "targeted_count": int(len(targeted)),
        "skipped_count": int(len(candidate) - len(targeted)),
        "insufficient_history_count": int(len(insufficient)),
        "history_mode_pass": bool(candidate["history_mode"].astype(str).eq("target_contract_only").all()),
        "history_source_pass": bool(candidate["history_source"].astype(str).eq("target_contract_observed").all()),
        "source_equals_target_count_pass": bool(numeric_source.eq(numeric_target).all()),
        "no_cross_contract_adjustment_pass": bool(np.isclose(ratios, 1.0, rtol=0.0, atol=1e-12).all()),
        "targeted_history_min_40_pass": bool(
            not targeted.empty
            and pd.to_numeric(targeted["observed_bar_count"], errors="coerce").ge(40).all()
        ),
        "jm2701_20260819_full_path_event_count": 0,
        "jm2701_20260819_full_path_note": "full backtest held no JM position on the rollover date",
        "jm2701_20260819_database_acceptance": jm_database_acceptance,
    }
    contract["all_pass"] = bool(
        contract["history_mode_pass"]
        and contract["history_source_pass"]
        and contract["source_equals_target_count_pass"]
        and contract["no_cross_contract_adjustment_pass"]
        and contract["targeted_history_min_40_pass"]
        and jm_database_acceptance["pass"]
    )
    return contract


def _plot(curve: pd.DataFrame) -> bytes:
    fig, ax = plt.subplots(figsize=(14, 6))
    for arm in ARMS:
        frame = curve[curve["experiment_arm"].eq(arm["arm"])].sort_values("date")
        ax.plot(
            pd.to_datetime(frame["date"]),
            pd.to_numeric(frame["account_equity"], errors="coerce") / 10_000.0,
            color=arm["color"],
            linewidth=1.4,
            label=arm["plot_label"],
        )
    ax.set_title("Stage027: Formal Q vs New-Contract-Only Rollover History")
    ax.set_ylabel("Equity (10k CNY)")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=170)
    plt.close(fig)
    return buffer.getvalue()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _assert_base_commit_is_ancestor()
    diff = override_diff()
    if diff != {"rollover_shape_history_mode": ("backwards_ratio_continuous", "target_contract_only")}:
        raise RuntimeError(f"stage027_override_scope_drift: {diff}")

    metadata = s513._metadata()
    summaries: list[pd.DataFrame] = []
    curves: list[pd.DataFrame] = []
    diagnostics: list[pd.DataFrame] = []
    trades: list[pd.DataFrame] = []
    trade_events: list[pd.DataFrame] = []

    for arm in ARMS:
        print(f"[stage027] running {arm['arm']} {arm['profile']} {START.date()}->{END.date()}", flush=True)
        summary, curve, frames = _run_arm(arm, metadata)
        summaries.append(summary)
        curves.append(curve)
        for key, target in (
            ("rollover_shape_same_volume", diagnostics),
            ("trades", trades),
            ("trade_events", trade_events),
        ):
            frame = frames.get(key, pd.DataFrame()).copy()
            if not frame.empty:
                target.append(frame)

    summary = pd.concat(summaries, ignore_index=True, sort=False)
    curve = pd.concat(curves, ignore_index=True, sort=False)
    diagnostic_frame = pd.concat(diagnostics, ignore_index=True, sort=False)
    trades_frame = pd.concat(trades, ignore_index=True, sort=False)
    trade_event_frame = pd.concat(trade_events, ignore_index=True, sort=False)
    comparison = _comparison(summary)
    rollover_contract = _rollover_contract(diagnostic_frame)
    if not rollover_contract["all_pass"]:
        raise RuntimeError("stage027_rollover_contract_failed: " + json.dumps(rollover_contract, ensure_ascii=False))

    decision = {
        "line_id": "futures_trend_rollover_shape_same_volume",
        "stage": "Stage027",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "base_commit": candidate_cfg.BASE_COMMIT,
        "base_ruleset": live_cfg.OFFICIAL_LIVE_RULESET_VERSION,
        "candidate_version": candidate_cfg.CANDIDATE_VERSION,
        "period": {"start": str(START.date()), "end": str(END.date())},
        "arms": {arm["arm"]: arm["profile"] for arm in ARMS},
        "override_diff": diff,
        "candidate_hypothesis": (
            "换月形态应由新主力自身截至当日的日K决定，避免旧主力复权历史替代新合约真实结构。"
        ),
        "predeclared_gate": {
            "scope_only_one_override": True,
            "candidate_history_contract_pass": True,
            "full_period_account_survival": True,
            "candidate_max_drawdown_not_worse_by_more_than_2pp": True,
            "candidate_sharpe_not_lower_by_more_than_0.02": True,
            "candidate_slippage_not_above_105pct_of_formal": True,
        },
        "comparison": comparison.iloc[0].to_dict(),
        "rollover_contract": rollover_contract,
        "order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
    }
    c_row = summary[summary["experiment_arm"].eq("C")].iloc[0]
    comp = comparison.iloc[0]
    gates = {
        "scope_only_one_override": len(diff) == 1,
        "candidate_history_contract_pass": bool(rollover_contract["all_pass"]),
        "full_period_account_survival": float(c_row["min_equity"]) > 0,
        "candidate_max_drawdown_not_worse_by_more_than_2pp": float(comp["delta_max_dd_pct"]) >= -2.0,
        "candidate_sharpe_not_lower_by_more_than_0.02": float(comp["delta_sharpe"]) >= -0.02,
        "candidate_slippage_not_above_105pct_of_formal": float(comp["slippage_ratio_C_over_A"]) <= 1.05,
    }
    decision["gates"] = gates
    decision["escalate_to_multicycle"] = bool(all(gates.values()))
    decision["decision"] = (
        "stage027_target_contract_history_pass_full_period_run_multicycle"
        if decision["escalate_to_multicycle"]
        else "stage027_target_contract_history_fail_full_period_keep_research_only"
    )

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    curve.to_csv(CURVE_PATH, index=False, encoding="utf-8-sig")
    diagnostic_frame.to_csv(ROLLOVER_PATH, index=False, encoding="utf-8-sig")
    trades_frame.to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    trade_event_frame.to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    CHART_PATH.write_bytes(_plot(curve))
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
