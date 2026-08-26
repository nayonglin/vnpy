from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime
from io import BytesIO
import json
from pathlib import Path
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
import qmt_roll_candidate_stage027_target_contract_history_config as stage027_cfg  # noqa: E402
import qmt_roll_candidate_stage028_delayed_rollover_config as stage028_cfg  # noqa: E402
import qmt_roll_official_live_config as live_cfg  # noqa: E402
from qmt_roll_official_baseline_identity import (  # noqa: E402
    assert_official_checkout_matches_active_material,
)


LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage028"
START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-08-25")
PRODUCTION_ROOT = Path("/Users/bytedance/Desktop/person/vnpy_production_live")

A_PROFILE = "stage028_A_formal_q_immediate_backadjusted"
B_PROFILE = "stage028_B_stage027_target_only_immediate"
C_PROFILE = "stage028_C_target_only_delay_5td"
ARMS: tuple[dict[str, str], ...] = (
    {
        "arm": "A",
        "profile": A_PROFILE,
        "label": "A: 当前正式 Q（立即换月、旧主力复权历史）",
        "plot_label": "A Formal Q: immediate/back-adjusted",
        "color": "#2563eb",
    },
    {
        "arm": "B",
        "profile": B_PROFILE,
        "label": "B: Stage027（立即换月、新主力自身K线）",
        "plot_label": "B Stage027: immediate/target-only",
        "color": "#dc2626",
    },
    {
        "arm": "C",
        "profile": C_PROFILE,
        "label": "C: Stage028（延迟5交易日、新主力自身K线）",
        "plot_label": "C Stage028: +5 sessions/target-only",
        "color": "#16a34a",
    },
)

SUMMARY_PATH = OUTPUT_DIR / "stage028_abc_summary.csv"
COMPARISON_PATH = OUTPUT_DIR / "stage028_abc_comparison.csv"
CURVE_PATH = OUTPUT_DIR / "stage028_abc_curve.csv"
ROLLOVER_PATH = OUTPUT_DIR / "stage028_rollover_diagnostics.csv"
DELAY_PATH = OUTPUT_DIR / "stage028_delay_diagnostics.csv"
TRADES_PATH = OUTPUT_DIR / "stage028_trades.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / "stage028_trade_events.csv"
DECISION_PATH = OUTPUT_DIR / "stage028_decision.json"
CHART_PATH = OUTPUT_DIR / "stage028_full_period_equity_abc.png"


def build_arm_overrides(arm: str) -> dict[str, Any]:
    if arm == "A":
        return live_cfg.build_official_live_strategy_overrides()
    if arm == "B":
        return stage027_cfg.build_candidate_overrides()
    if arm == "C":
        return stage028_cfg.build_candidate_overrides()
    raise ValueError(f"unknown stage028 arm: {arm}")


def override_diff(left_arm: str, right_arm: str) -> dict[str, tuple[Any, Any]]:
    left = build_arm_overrides(left_arm)
    right = build_arm_overrides(right_arm)
    keys = set(left) | set(right)
    return {
        key: (left.get(key), right.get(key))
        for key in sorted(keys)
        if left.get(key) != right.get(key)
    }


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=PROJECT_DIR,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _assert_identity_and_scope() -> dict[str, Any]:
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", stage028_cfg.BASE_COMMIT, "HEAD"],
        cwd=PROJECT_DIR,
        check=True,
    )
    formal = asdict(assert_official_checkout_matches_active_material(PROJECT_DIR))
    production = asdict(assert_official_checkout_matches_active_material(PRODUCTION_ROOT))
    if formal != production:
        raise RuntimeError("stage028_formal_production_identity_mismatch")
    remote_master = _git("rev-parse", "origin/master")
    if remote_master != stage027_cfg.BASE_COMMIT:
        raise RuntimeError(
            "stage028_remote_master_changed: "
            f"expected={stage027_cfg.BASE_COMMIT} actual={remote_master}"
        )
    diff = override_diff("B", "C")
    expected = {"rollover_delay_trading_days": (None, 5)}
    if diff != expected:
        raise RuntimeError(f"stage028_override_scope_drift: {diff}")
    return {
        "formal_identity": formal,
        "production_identity": production,
        "remote_master": remote_master,
        "stage027_base_commit": stage028_cfg.BASE_COMMIT,
        "stage027_to_stage028_override_diff": diff,
    }


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

    capital = replace(live_spec.capital, variant=arm["profile"], label=arm["label"])
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
        if not frame.empty:
            frame["experiment_arm"] = arm["arm"]
    return summary, curve, frames


METRICS = (
    "end_equity",
    "total_return_pct",
    "max_dd_pct",
    "sharpe",
    "total_slippage",
    "total_trade_count",
    "nonzero_daily_win_rate_pct",
    "max_broker10_margin_to_equity_pct",
    "days_over_100pct",
)


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    indexed = summary.set_index("experiment_arm")
    for left_arm, right_arm in (("A", "B"), ("B", "C"), ("A", "C")):
        left = indexed.loc[left_arm]
        right = indexed.loc[right_arm]
        row: dict[str, Any] = {
            "comparison": f"{left_arm}_vs_{right_arm}",
            "baseline": str(left["profile"]),
            "candidate": str(right["profile"]),
        }
        for metric in METRICS:
            left_value = float(left[metric])
            right_value = float(right[metric])
            row[f"{left_arm}_{metric}"] = left_value
            row[f"{right_arm}_{metric}"] = right_value
            row[f"delta_{metric}"] = right_value - left_value
        row[f"slippage_ratio_{right_arm}_over_{left_arm}"] = (
            float(right["total_slippage"]) / float(left["total_slippage"])
            if float(left["total_slippage"]) > 0
            else np.nan
        )
        rows.append(row)
    return pd.DataFrame(rows)


def _history_contract(diagnostics: pd.DataFrame, arm: str) -> dict[str, Any]:
    frame = diagnostics[diagnostics["experiment_arm"].eq(arm)].copy()
    targeted = frame[frame["status"].astype(str).eq("targeted")]
    insufficient = frame[frame["reason"].astype(str).eq("insufficient_indicator_history")]
    source_count = pd.to_numeric(frame["source_observed_bar_count"], errors="coerce")
    target_count = pd.to_numeric(frame["target_observed_bar_count"], errors="coerce")
    ratios = pd.to_numeric(frame["roll_adjustment_ratio"], errors="coerce")
    result = {
        "arm": arm,
        "diagnostic_count": int(len(frame)),
        "targeted_count": int(len(targeted)),
        "skipped_count": int(len(frame) - len(targeted)),
        "insufficient_history_count": int(len(insufficient)),
        "history_mode_pass": bool(not frame.empty and frame["history_mode"].astype(str).eq("target_contract_only").all()),
        "history_source_pass": bool(not frame.empty and frame["history_source"].astype(str).eq("target_contract_observed").all()),
        "source_equals_target_count_pass": bool(not frame.empty and source_count.eq(target_count).all()),
        "no_cross_contract_adjustment_pass": bool(
            not frame.empty and np.isclose(ratios, 1.0, rtol=0.0, atol=1e-12).all()
        ),
        "targeted_history_min_40_pass": bool(
            targeted.empty
            or pd.to_numeric(targeted["observed_bar_count"], errors="coerce").ge(40).all()
        ),
    }
    result["all_pass"] = bool(
        result["history_mode_pass"]
        and result["history_source_pass"]
        and result["source_equals_target_count_pass"]
        and result["no_cross_contract_adjustment_pass"]
        and result["targeted_history_min_40_pass"]
    )
    return result


def _delay_contract(delay: pd.DataFrame, rollover: pd.DataFrame) -> dict[str, Any]:
    frame = delay[delay["experiment_arm"].eq("C")].copy()
    due = frame[frame["status"].astype(str).eq("due")]
    scheduled = frame[frame["status"].astype(str).eq("scheduled")]
    c_rollovers = rollover[rollover["experiment_arm"].eq("C")].copy()
    due_keys = set(
        zip(
            due["date"].astype(str),
            due["product_vt_symbol"].astype(str),
            due["target_contract_vt_symbol"].astype(str),
        )
    )
    rollover_keys = set(
        zip(
            c_rollovers["date"].astype(str),
            c_rollovers["product_vt_symbol"].astype(str),
            c_rollovers["target_contract_vt_symbol"].astype(str),
        )
    )
    result = {
        "diagnostic_count": int(len(frame)),
        "scheduled_count": int(len(scheduled)),
        "due_count": int(len(due)),
        "cancelled_before_due_count": int(max(0, len(scheduled) - len(due))),
        "required_days_exact_5_pass": bool(
            not frame.empty
            and pd.to_numeric(frame["required_trading_days"], errors="coerce").eq(5).all()
        ),
        "due_elapsed_exact_5_pass": bool(
            not due.empty
            and pd.to_numeric(due["elapsed_trading_days"], errors="coerce").eq(5).all()
        ),
        "rollover_only_on_due_pass": bool(rollover_keys.issubset(due_keys)),
        "due_has_rollover_diagnostic_pass": bool(due_keys.issubset(rollover_keys)),
    }
    result["all_pass"] = bool(
        result["required_days_exact_5_pass"]
        and result["due_elapsed_exact_5_pass"]
        and result["rollover_only_on_due_pass"]
        and result["due_has_rollover_diagnostic_pass"]
    )
    return result


def _plot(curve: pd.DataFrame) -> bytes:
    fig, ax = plt.subplots(figsize=(14, 6))
    for arm in ARMS:
        frame = curve[curve["experiment_arm"].eq(arm["arm"])].sort_values("date")
        ax.plot(
            pd.to_datetime(frame["date"]),
            pd.to_numeric(frame["account_equity"], errors="coerce") / 10_000.0,
            color=arm["color"],
            linewidth=1.35,
            label=arm["plot_label"],
        )
    ax.set_title("Stage028: Formal Q vs Target-only Immediate vs Target-only +5 Sessions")
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
    identity = _assert_identity_and_scope()
    metadata = s513._metadata()
    summaries: list[pd.DataFrame] = []
    curves: list[pd.DataFrame] = []
    rollovers: list[pd.DataFrame] = []
    delays: list[pd.DataFrame] = []
    trades: list[pd.DataFrame] = []
    trade_events: list[pd.DataFrame] = []

    for arm in ARMS:
        print(f"[stage028] running {arm['arm']} {START.date()}->{END.date()}", flush=True)
        summary, curve, frames = _run_arm(arm, metadata)
        summaries.append(summary)
        curves.append(curve)
        for key, target in (
            ("rollover_shape_same_volume", rollovers),
            ("rollover_delay", delays),
            ("trades", trades),
            ("trade_events", trade_events),
        ):
            frame = frames.get(key, pd.DataFrame()).copy()
            if not frame.empty:
                target.append(frame)

    summary = pd.concat(summaries, ignore_index=True, sort=False)
    curve = pd.concat(curves, ignore_index=True, sort=False)
    rollover = pd.concat(rollovers, ignore_index=True, sort=False)
    delay = pd.concat(delays, ignore_index=True, sort=False)
    trades_frame = pd.concat(trades, ignore_index=True, sort=False)
    trade_events_frame = pd.concat(trade_events, ignore_index=True, sort=False)
    comparison = _comparison(summary)
    b_history_contract = _history_contract(rollover, "B")
    c_history_contract = _history_contract(rollover, "C")
    delay_contract = _delay_contract(delay, rollover)
    if not b_history_contract["all_pass"] or not c_history_contract["all_pass"]:
        raise RuntimeError("stage028_target_history_contract_failed")
    if not delay_contract["all_pass"]:
        raise RuntimeError("stage028_delay_contract_failed: " + json.dumps(delay_contract, ensure_ascii=False))

    indexed = summary.set_index("experiment_arm")
    b_row = indexed.loc["B"]
    c_row = indexed.loc["C"]
    bc = comparison[comparison["comparison"].eq("B_vs_C")].iloc[0]
    ac = comparison[comparison["comparison"].eq("A_vs_C")].iloc[0]
    gates = {
        "scope_only_one_override": True,
        "target_history_contract_pass": bool(c_history_contract["all_pass"]),
        "delay_contract_pass": bool(delay_contract["all_pass"]),
        "full_period_account_survival": float(c_row["min_equity"]) > 0,
        "C_end_equity_not_lower_than_B": float(c_row["end_equity"]) >= float(b_row["end_equity"]),
        "C_max_drawdown_not_worse_than_B_by_more_than_2pp": float(bc["delta_max_dd_pct"]) >= -2.0,
        "C_sharpe_not_lower_than_B_by_more_than_0_02": float(bc["delta_sharpe"]) >= -0.02,
        "C_slippage_not_above_105pct_of_B": float(bc["slippage_ratio_C_over_B"]) <= 1.05,
        "C_max_drawdown_not_worse_than_A_by_more_than_2pp": float(ac["delta_max_dd_pct"]) >= -2.0,
        "C_sharpe_not_lower_than_A_by_more_than_0_02": float(ac["delta_sharpe"]) >= -0.02,
        "C_broker10_days_over_100_eq_0": int(c_row["days_over_100pct"]) == 0,
    }
    escalate = bool(all(gates.values()))
    decision = {
        "line_id": "futures_trend_rollover_shape_same_volume",
        "stage": "Stage028",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "identity": identity,
        "base_candidate_version": stage027_cfg.CANDIDATE_VERSION,
        "candidate_version": stage028_cfg.CANDIDATE_VERSION,
        "period": {"start": str(START.date()), "end": str(END.date())},
        "arms": {arm["arm"]: arm["profile"] for arm in ARMS},
        "candidate_hypothesis": (
            "主力切换后固定等待5个交易日，可让新合约完成短期价格发现；等待期仍管理旧仓，"
            "第5日按新合约自身可见历史重新判断，不使用未来数据。"
        ),
        "initial_predeclared_gate": [key for key in gates if key != "C_broker10_days_over_100_eq_0"],
        "evaluation_gate": list(gates),
        "mandatory_safety_gate_note": (
            "broker10不得超过100%是正式策略既有硬闸；首轮决策生成器遗漏该字段，发现后补入，"
            "不改变策略参数且本轮本已因Sharpe门失败。"
        ),
        "gates": gates,
        "history_contract_B": b_history_contract,
        "history_contract_C": c_history_contract,
        "delay_contract": delay_contract,
        "comparisons": comparison.to_dict(orient="records"),
        "escalate_to_multicycle": escalate,
        "decision": (
            "stage028_delay_5td_pass_full_period_run_multicycle"
            if escalate
            else "stage028_delay_5td_fail_full_period_keep_research_only"
        ),
        "order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    curve.to_csv(CURVE_PATH, index=False, encoding="utf-8-sig")
    rollover.to_csv(ROLLOVER_PATH, index=False, encoding="utf-8-sig")
    delay.to_csv(DELAY_PATH, index=False, encoding="utf-8-sig")
    trades_frame.to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    trade_events_frame.to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    CHART_PATH.write_bytes(_plot(curve))
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
