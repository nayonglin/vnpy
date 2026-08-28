from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any
from uuid import uuid4

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
sys.path.insert(0, str(PORTFOLIO_DIR))

import qmt_roll_candidate_stage034_ordered_drawdown_4atr_config as stage034_cfg  # noqa: E402
import qmt_roll_candidate_stage037_short_mirror_block_config as stage037_cfg  # noqa: E402
import qmt_roll_official_live_config as live_cfg  # noqa: E402
import stage028_q_delayed_rollover_abc as s28  # noqa: E402
import stage029_stage028_multicycle_abc as s29  # noqa: E402
import stage034_stage033_ordered_drawdown_4atr_abc as s34  # noqa: E402


LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage037"
RECOVERY_DIR = LINE_DIR / "artifacts" / ".stage037_recovery"
STAGE034_DIR = LINE_DIR / "artifacts" / "stage034"
START = pd.Timestamp("2018-01-01")
EXPECTED_FIRST_TRADING_DAY = pd.Timestamp("2018-01-02")
END = pd.Timestamp("2026-08-25")
METRICS = s28.METRICS

ARMS: tuple[dict[str, str], ...] = (
    {
        "arm": "A",
        "profile": "stage037_A_formal_q",
        "label": "A: 当前正式 Q",
        "plot_label": "A Formal Q",
        "color": "#2563eb",
    },
    {
        "arm": "B",
        "profile": "stage037_B_stage034_long_only_hard_block",
        "label": "B: Stage034 仅多头硬拦截",
        "plot_label": "B Stage034: long only",
        "color": "#dc2626",
    },
    {
        "arm": "C",
        "profile": "stage037_C_long_short_mirror_hard_block",
        "label": "C: Stage037 多空镜像硬拦截",
        "plot_label": "C Stage037: long + short",
        "color": "#16a34a",
    },
)

SUMMARY_NAME = "stage037_abc_summary.csv"
COMPARISON_NAME = "stage037_abc_comparison.csv"
CURVE_NAME = "stage037_abc_curve.csv"
FILTER_NAME = "stage037_long_short_range_atr_diagnostics.csv"
FILTER_CONTRACT_NAME = "stage037_long_short_filter_contract_summary.csv"
ROLLOVER_NAME = "stage037_rollover_diagnostics.csv"
DELAY_NAME = "stage037_delay_diagnostics.csv"
TRADES_NAME = "stage037_trades.csv"
TRADE_EVENTS_NAME = "stage037_trade_events.csv"
DECISION_NAME = "stage037_decision.json"
REPORT_NAME = "stage037_report.md"
CHART_NAME = "stage037_full_period_equity_abc.png"

REFERENCE_FILES = {
    SUMMARY_NAME: "stage034_abc_summary.csv",
    CURVE_NAME: "stage034_abc_curve.csv",
    FILTER_NAME: "stage034_long_range_atr_diagnostics.csv",
    ROLLOVER_NAME: "stage034_rollover_diagnostics.csv",
    DELAY_NAME: "stage034_delay_diagnostics.csv",
    TRADES_NAME: "stage034_trades.csv",
    TRADE_EVENTS_NAME: "stage034_trade_events.csv",
}


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_arm_overrides(arm: str) -> dict[str, Any]:
    if arm == "A":
        return live_cfg.build_official_live_strategy_overrides()
    if arm == "B":
        return stage034_cfg.build_candidate_overrides()
    if arm == "C":
        return stage037_cfg.build_candidate_overrides()
    raise ValueError(f"unknown stage037 arm:{arm}")


def override_diff(left_arm: str, right_arm: str) -> dict[str, tuple[Any, Any]]:
    left = build_arm_overrides(left_arm)
    right = build_arm_overrides(right_arm)
    keys = set(left) | set(right)
    return {
        key: (left.get(key), right.get(key))
        for key in sorted(keys)
        if left.get(key) != right.get(key)
    }


def _expected_override_diff() -> dict[str, tuple[Any, Any]]:
    return {"enable_short_signal_range_atr_filter": (None, True)}


def _preflight() -> dict[str, Any]:
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", stage037_cfg.BASE_COMMIT, "HEAD"],
        cwd=PROJECT_DIR,
        check=True,
    )
    subprocess.run(
        [
            "git",
            "diff",
            "--quiet",
            stage037_cfg.BASE_COMMIT,
            "--",
            str(STAGE034_DIR.relative_to(PROJECT_DIR)),
        ],
        cwd=PROJECT_DIR,
        check=True,
    )
    diff = override_diff("B", "C")
    if diff != _expected_override_diff():
        raise RuntimeError(f"stage037_override_scope_drift:{diff}")
    candidate = build_arm_overrides("C")
    frozen = {
        "long_signal_range_lookback": 10,
        "long_signal_range_atr_period": 5,
        "long_signal_range_atr_multiplier": 3.0,
        "long_signal_range_recent_gain_lookback": 3,
        "long_signal_range_recent_gain_atr_multiplier": 0.5,
        "long_signal_range_ordered_drawdown_atr_multiplier": 4.0,
    }
    for key, value in frozen.items():
        if candidate.get(key) != value:
            raise RuntimeError(f"stage037_frozen_parameter_drift:{key}")
    reference_decision = json.loads(
        (STAGE034_DIR / "stage034_decision.json").read_text(encoding="utf-8")
    )
    if (
        reference_decision.get("stage") != "Stage034"
        or not reference_decision.get("filter_contract", {}).get("all_pass")
        or not reference_decision.get("named_case_contract", {}).get("all_pass")
        or reference_decision.get("order_api_called_count") != 0
        or reference_decision.get("ctp_connected") is not False
    ):
        raise RuntimeError("stage037_stage034_reference_invalid")
    runtime = s29._assert_runtime_database_binding()
    database_sha256 = _file_sha256(Path(runtime["database_path"]))
    reference_database_sha256 = str(
        reference_decision.get("identity", {})
        .get("runtime_binding", {})
        .get("database_sha256", "")
    )
    if database_sha256 != reference_database_sha256:
        raise RuntimeError(
            "stage037_stage034_database_snapshot_mismatch:"
            f"{database_sha256}!={reference_database_sha256}"
        )
    reference_hashes = {
        path.name: _file_sha256(path)
        for path in sorted(STAGE034_DIR.iterdir())
        if path.is_file()
    }
    return {
        "stage034_base_commit": stage037_cfg.BASE_COMMIT,
        "stage034_to_stage037_override_diff": diff,
        "stage034_reference_hashes": reference_hashes,
        "stage034_reference_identity": reference_decision.get("identity", {}),
        "runtime_binding": {
            **runtime,
            "database_sha256": database_sha256,
            "stage034_reference_database_sha256": reference_database_sha256,
        },
    }


def _run_new_c(metadata: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    arm = ARMS[2]
    original_builder = s28.s901.build_official_live_strategy_overrides
    try:
        s28.s901.build_official_live_strategy_overrides = lambda: build_arm_overrides("C")
        combined, frames, live_spec = s28.s901._run_live_c9(metadata, START, END)
    finally:
        s28.s901.build_official_live_strategy_overrides = original_builder
    capital = replace(live_spec.capital, variant=arm["profile"], label=arm["label"])
    metric_spec = replace(live_spec, capital=capital, profile=arm["profile"])
    summary, curve = s28.s827._metric(
        {"profile": arm["profile"], "spec": metric_spec}, combined
    )
    summary["experiment_arm"] = "C"
    summary["window_name"] = "full_2018_20260825"
    summary["window_label"] = "2018-01-01 independent start to 2026-08-25"
    curve["experiment_arm"] = "C"
    for frame in frames.values():
        if not frame.empty:
            frame["experiment_arm"] = "C"
    return summary, curve, frames


def _recovery_contract(identity: dict[str, Any]) -> dict[str, Any]:
    payload = json.dumps(
        build_arm_overrides("C"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return {
        "database_sha256": identity["runtime_binding"]["database_sha256"],
        "candidate_version": stage037_cfg.CANDIDATE_VERSION,
        "period": {"start": str(START.date()), "end": str(END.date())},
        "candidate_overrides_sha256": sha256(payload).hexdigest(),
    }


def _persist_recovery_snapshot(
    summary: pd.DataFrame,
    curve: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    contract: dict[str, Any],
) -> None:
    RECOVERY_DIR.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".stage037-recovery.tmp-", dir=RECOVERY_DIR.parent))
    try:
        summary.to_pickle(temporary / "summary.pkl")
        curve.to_pickle(temporary / "curve.pkl")
        frame_keys = sorted(frames)
        for key in frame_keys:
            frames[key].to_pickle(temporary / f"frame_{key}.pkl")
        (temporary / "manifest.json").write_text(
            json.dumps(
                {"frame_keys": frame_keys, "recovery_contract": contract},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        if RECOVERY_DIR.exists():
            shutil.rmtree(RECOVERY_DIR)
        os.replace(temporary, RECOVERY_DIR)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)


def _reference_frame(filename: str) -> pd.DataFrame:
    frame = pd.read_csv(STAGE034_DIR / filename)
    if "experiment_arm" not in frame.columns:
        return frame
    reference = frame[frame["experiment_arm"].astype(str).isin({"A", "C"})].copy()
    reference.loc[reference["experiment_arm"].astype(str).eq("C"), "experiment_arm"] = "B"
    if "profile" in reference.columns:
        for arm in ARMS[:2]:
            reference.loc[
                reference["experiment_arm"].astype(str).eq(arm["arm"]), "profile"
            ] = arm["profile"]
    return reference


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
            row[f"{left_arm}_{metric}"] = float(left[metric])
            row[f"{right_arm}_{metric}"] = float(right[metric])
            row[f"delta_{metric}"] = float(right[metric]) - float(left[metric])
        rows.append(row)
    return pd.DataFrame(rows)


def _assert_coverage(summary: pd.DataFrame, curve: pd.DataFrame) -> None:
    if len(summary) != 3 or set(summary["experiment_arm"].astype(str)) != {"A", "B", "C"}:
        raise RuntimeError("stage037_summary_arm_identity_failed")
    reference_dates: pd.DatetimeIndex | None = None
    for arm in ("A", "B", "C"):
        row = summary[summary["experiment_arm"].astype(str).eq(arm)].iloc[0]
        dates = pd.DatetimeIndex(
            pd.to_datetime(
                curve[curve["experiment_arm"].astype(str).eq(arm)]["date"],
                errors="raise",
                format="mixed",
            ).dt.normalize()
        )
        if reference_dates is None:
            reference_dates = dates
        if (
            dates.duplicated().any()
            or not dates.equals(reference_dates)
            or dates.min() != EXPECTED_FIRST_TRADING_DAY
            or dates.max() != END
            or pd.Timestamp(row["analysis_start"]).normalize() != EXPECTED_FIRST_TRADING_DAY
            or pd.Timestamp(row["analysis_end"]).normalize() != END
        ):
            raise RuntimeError(f"stage037_full_period_coverage_failed:{arm}")


def _filter_contract(diagnostics: pd.DataFrame) -> dict[str, Any]:
    frame = diagnostics[diagnostics["experiment_arm"].astype(str).eq("C")].copy()
    numeric = (
        "long_signal_range_value",
        "long_signal_range_prior_atr",
        "long_signal_range_atr_threshold",
        "long_signal_range_directional_recent_move",
        "long_signal_range_recent_gain_atr_threshold",
        "long_signal_range_expansion_stall_condition_met",
        "long_signal_range_ordered_drawdown_value",
        "long_signal_range_ordered_drawdown_atr_threshold",
        "long_signal_range_ordered_drawdown_peak_index",
        "long_signal_range_ordered_drawdown_trough_index",
        "long_signal_range_ordered_drawdown_condition_met",
        "long_signal_range_atr_condition_met",
        "long_signal_range_atr_blocked",
        "long_signal_range_atr_selected_volume_before",
        "long_signal_range_atr_selected_volume_after",
    )
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    valid = frame[
        frame["direction"].astype(str).isin({"long", "short"})
        & ~frame["long_signal_range_atr_reason"].astype(str).isin(
            {"disabled", "direction_excluded", "entry_context_excluded", "invalid_configuration", "insufficient_history", "invalid_history", "invalid_prior_true_range", "invalid_recent_close_history", "invalid_prior_atr_or_range"}
        )
    ].copy()
    expansion = valid["long_signal_range_expansion_stall_condition_met"].eq(1)
    ordered = valid["long_signal_range_ordered_drawdown_condition_met"].eq(1)
    combined = valid["long_signal_range_atr_condition_met"].eq(1)
    expansion_expected = valid["long_signal_range_value"].gt(
        valid["long_signal_range_atr_threshold"]
    ) & valid["long_signal_range_directional_recent_move"].lt(
        valid["long_signal_range_recent_gain_atr_threshold"]
    )
    ordered_expected = valid["long_signal_range_ordered_drawdown_value"].gt(
        valid["long_signal_range_ordered_drawdown_atr_threshold"]
    )
    blocked = valid[valid["long_signal_range_atr_blocked"].eq(1)]
    matched_zero = valid[
        combined & valid["long_signal_range_atr_selected_volume_before"].eq(0)
    ]
    long_rows = valid[valid["direction"].astype(str).eq("long")]
    short_rows = valid[valid["direction"].astype(str).eq("short")]
    long_order = long_rows["long_signal_range_ordered_drawdown_peak_index"].lt(
        long_rows["long_signal_range_ordered_drawdown_trough_index"]
    )
    short_order = short_rows["long_signal_range_ordered_drawdown_trough_index"].lt(
        short_rows["long_signal_range_ordered_drawdown_peak_index"]
    )
    result = {
        "diagnostic_count": int(len(frame)),
        "valid_count": int(len(valid)),
        "long_valid_count": int(len(long_rows)),
        "short_valid_count": int(len(short_rows)),
        "condition_met_count": int(combined.sum()),
        "long_condition_met_count": int(combined[long_rows.index].sum()),
        "short_condition_met_count": int(combined[short_rows.index].sum()),
        "expansion_stall_condition_count": int(expansion.sum()),
        "ordered_adverse_move_condition_count": int(ordered.sum()),
        "both_condition_count": int((expansion & ordered).sum()),
        "actual_incremental_block_count": int(len(blocked)),
        "long_incremental_block_count": int(blocked["direction"].astype(str).eq("long").sum()),
        "short_incremental_block_count": int(blocked["direction"].astype(str).eq("short").sum()),
        "matched_after_prior_zero_count": int(len(matched_zero)),
        "config_pass": bool(
            not frame.empty
            and frame["long_signal_range_atr_long_enabled"].astype(int).eq(1).all()
            and frame["long_signal_range_atr_short_enabled"].astype(int).eq(1).all()
            and frame["long_signal_range_lookback"].astype(int).eq(10).all()
            and frame["long_signal_range_atr_period"].astype(int).eq(5).all()
            and np.isclose(frame["long_signal_range_atr_multiplier"].astype(float), 3.0).all()
            and np.isclose(frame["long_signal_range_ordered_drawdown_atr_multiplier"].astype(float), 4.0).all()
        ),
        "or_semantics_pass": bool(valid.empty or combined.equals(expansion | ordered)),
        "expansion_component_pass": bool(valid.empty or expansion.equals(expansion_expected)),
        "ordered_component_pass": bool(valid.empty or ordered.equals(ordered_expected)),
        "directional_order_pass": bool(
            (long_rows.empty or long_order.all())
            and (short_rows.empty or short_order.all())
        ),
        "hard_block_semantics_pass": bool(
            blocked.empty
            or (
                blocked["entry_context"].astype(str)
                .isin({"flat_entry", "reverse_entry", "rollover_reopen"})
                .all()
                and blocked["long_signal_range_atr_selected_volume_before"].gt(0).all()
                and blocked["long_signal_range_atr_selected_volume_after"].eq(0).all()
            )
        ),
        "prior_zero_not_double_counted_pass": bool(
            matched_zero.empty or matched_zero["long_signal_range_atr_blocked"].eq(0).all()
        ),
        "short_rule_has_observed_power": bool(
            int(combined[short_rows.index].sum()) > 0
            and int(blocked["direction"].astype(str).eq("short").sum()) > 0
        ),
    }
    result["all_pass"] = bool(
        result["config_pass"]
        and result["or_semantics_pass"]
        and result["expansion_component_pass"]
        and result["ordered_component_pass"]
        and result["directional_order_pass"]
        and result["hard_block_semantics_pass"]
        and result["prior_zero_not_double_counted_pass"]
        and result["short_rule_has_observed_power"]
    )
    return result


def _plot(curve: pd.DataFrame) -> bytes:
    fig, ax = plt.subplots(figsize=(14, 6))
    for arm in ARMS:
        frame = curve[curve["experiment_arm"].astype(str).eq(arm["arm"])].sort_values("date")
        ax.plot(
            pd.to_datetime(frame["date"]),
            pd.to_numeric(frame["account_equity"], errors="coerce") / 10_000.0,
            color=arm["color"],
            linewidth=1.35,
            label=arm["plot_label"],
        )
    ax.set_title("Stage037: Formal Q vs Stage034 Long Only vs Long + Short Mirror")
    ax.set_ylabel("Equity (10k CNY)")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=170)
    plt.close(fig)
    return buffer.getvalue()


def _report(summary: pd.DataFrame, comparison: pd.DataFrame, decision: dict[str, Any]) -> str:
    indexed = summary.set_index("experiment_arm")
    lines = [
        "# Stage037 Stage034空头镜像硬拦截全周期A/B/C",
        "",
        f"结论：`{decision['decision']}`。",
        "",
        "| Arm | 期末权益 | 总收益 | 最大回撤 | Sharpe | 滑点 | 交易数 | 胜率 | broker10峰值 | 超100%天数 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in ("A", "B", "C"):
        row = indexed.loc[arm]
        lines.append(
            f"| {arm} | {row['end_equity']:,.2f} | {row['total_return_pct']:.4f}% | "
            f"{row['max_dd_pct']:.4f}% | {row['sharpe']:.6f} | {row['total_slippage']:,.0f} | "
            f"{int(row['total_trade_count'])} | {row['nonzero_daily_win_rate_pct']:.4f}% | "
            f"{row['max_broker10_margin_to_equity_pct']:.4f}% | {int(row['days_over_100pct'])} |"
        )
    bc = comparison[comparison["comparison"].eq("B_vs_C")].iloc[0]
    ac = comparison[comparison["comparison"].eq("A_vs_C")].iloc[0]
    contract = decision["filter_contract"]
    lines.extend(
        [
            "",
            "## 增量结果",
            "",
            f"- C相对Stage034 B：期末权益 `{bc['delta_end_equity']:+,.2f}`，收益 `{bc['delta_total_return_pct']:+.4f}pp`，最大回撤 `{bc['delta_max_dd_pct']:+.4f}pp`，Sharpe `{bc['delta_sharpe']:+.6f}`，滑点 `{bc['delta_total_slippage']:+,.0f}`。",
            f"- C相对正式A：期末权益 `{ac['delta_end_equity']:+,.2f}`，收益 `{ac['delta_total_return_pct']:+.4f}pp`，最大回撤 `{ac['delta_max_dd_pct']:+.4f}pp`，Sharpe `{ac['delta_sharpe']:+.6f}`。",
            f"- C共命中 `{contract['condition_met_count']}` 个候选事件，其中多头 `{contract['long_condition_met_count']}`、空头 `{contract['short_condition_met_count']}`；实际正手数硬拦截多头 `{contract['long_incremental_block_count']}`、空头 `{contract['short_incremental_block_count']}`。",
            "",
            "## 安全与研究判断",
            "",
            "- A/B逐值复用Stage034冻结产物；只重新运行C。",
            "- 仅普通开仓、反转开仓、换月重开受影响；加仓、retry、退出和持仓管理不变。",
            "- 未连接CTP，未调用订单API，也未修改正式物料、master或生产。",
            f"- 是否建议进入多周期：`{str(decision['escalate_to_multicycle']).lower()}`。",
            "",
        ]
    )
    return "\n".join(lines)


def _publish(frames: dict[str, pd.DataFrame], decision: dict[str, Any], report: str, chart: bytes) -> None:
    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".stage037.tmp-", dir=OUTPUT_DIR.parent))
    backup = OUTPUT_DIR.with_name(f".stage037.backup-{uuid4().hex}")
    try:
        for filename, frame in frames.items():
            frame.to_csv(temporary / filename, index=False, encoding="utf-8-sig")
        (temporary / DECISION_NAME).write_text(
            json.dumps(decision, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (temporary / REPORT_NAME).write_text(report, encoding="utf-8")
        (temporary / CHART_NAME).write_bytes(chart)
        if OUTPUT_DIR.exists():
            os.replace(OUTPUT_DIR, backup)
        os.replace(temporary, OUTPUT_DIR)
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)


def main() -> None:
    identity = _preflight()
    metadata = s28.s513._metadata()
    recovery_contract = _recovery_contract(identity)
    print(f"[stage037] running C only {START.date()}->{END.date()}", flush=True)
    c_summary, c_curve, c_frames = _run_new_c(metadata)
    _persist_recovery_snapshot(c_summary, c_curve, c_frames, recovery_contract)

    summary = pd.concat(
        [_reference_frame("stage034_abc_summary.csv"), c_summary],
        ignore_index=True,
        sort=False,
    )
    curve = pd.concat(
        [_reference_frame("stage034_abc_curve.csv"), c_curve],
        ignore_index=True,
        sort=False,
    )
    _assert_coverage(summary, curve)
    comparison = _comparison(summary)

    output_frames: dict[str, pd.DataFrame] = {}
    frame_keys = {
        FILTER_NAME: "long_signal_range_atr",
        ROLLOVER_NAME: "rollover_shape_same_volume",
        DELAY_NAME: "rollover_delay",
        TRADES_NAME: "trades",
        TRADE_EVENTS_NAME: "trade_events",
    }
    for output_name, frame_key in frame_keys.items():
        reference = _reference_frame(REFERENCE_FILES[output_name])
        current = c_frames.get(frame_key, pd.DataFrame()).copy()
        output_frames[output_name] = pd.concat([reference, current], ignore_index=True, sort=False)

    history_c = s28._history_contract(c_frames["rollover_shape_same_volume"], "C")
    delay_c = s28._delay_contract(
        c_frames["rollover_delay"],
        c_frames["rollover_shape_same_volume"],
        c_frames["trade_events"],
    )
    filter_contract = _filter_contract(output_frames[FILTER_NAME])
    if not history_c["all_pass"] or not delay_c["all_pass"]:
        raise RuntimeError("stage037_stage028_contract_failed")
    if not filter_contract["all_pass"]:
        raise RuntimeError(f"stage037_filter_contract_failed:{filter_contract}")

    indexed = summary.set_index("experiment_arm")
    a_row, b_row, c_row = indexed.loc["A"], indexed.loc["B"], indexed.loc["C"]
    bc = comparison[comparison["comparison"].eq("B_vs_C")].iloc[0]
    ac = comparison[comparison["comparison"].eq("A_vs_C")].iloc[0]
    gates = {
        "scope_exact_only_enable_short_filter": override_diff("B", "C") == _expected_override_diff(),
        "history_and_delay_contract_pass": bool(history_c["all_pass"] and delay_c["all_pass"]),
        "filter_semantics_pass": bool(filter_contract["all_pass"]),
        "full_period_account_survival": float(c_row["min_equity"]) > 0,
        "short_rule_has_observed_power": bool(filter_contract["short_rule_has_observed_power"]),
        "C_end_equity_not_lower_than_B": float(c_row["end_equity"]) >= float(b_row["end_equity"]),
        "C_sharpe_not_lower_than_B_by_more_than_0_02": float(bc["delta_sharpe"]) >= -0.02,
        "C_max_drawdown_not_worse_than_B_by_more_than_2pp": float(bc["delta_max_dd_pct"]) >= -2.0,
        "C_slippage_not_above_105pct_of_B": float(c_row["total_slippage"]) <= 1.05 * float(b_row["total_slippage"]),
        "C_broker100_fail_count_not_above_B": int(c_row["days_over_100pct"]) <= int(b_row["days_over_100pct"]),
        "C_end_equity_not_lower_than_A": float(c_row["end_equity"]) >= float(a_row["end_equity"]),
        "C_sharpe_not_lower_than_A_by_more_than_0_02": float(ac["delta_sharpe"]) >= -0.02,
        "C_max_drawdown_not_worse_than_A_by_more_than_2pp": float(ac["delta_max_dd_pct"]) >= -2.0,
        "C_slippage_not_above_105pct_of_A": float(c_row["total_slippage"]) <= 1.05 * float(a_row["total_slippage"]),
        "C_broker100_fail_count_not_above_A": int(c_row["days_over_100pct"]) <= int(a_row["days_over_100pct"]),
    }
    escalate = bool(all(gates.values()))
    decision = {
        "line_id": "futures_trend_rollover_shape_same_volume",
        "stage": "Stage037",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "identity": identity,
        "base_candidate_version": stage034_cfg.CANDIDATE_VERSION,
        "candidate_version": stage037_cfg.CANDIDATE_VERSION,
        "period": {"start": str(START.date()), "end": str(END.date())},
        "arms": {arm["arm"]: arm["profile"] for arm in ARMS},
        "candidate_hypothesis": "Stage034长头A/B或条件原样保留，并对空头使用方向镜像：弱近3日下跌与先低后高反弹，命中任一即硬拦截。",
        "overfitting_risk_predeclared": True,
        "reference_reuse": {
            "A_and_B_from_stage034": True,
            "only_C_new_engine_run": True,
            "stage034_reference_hashes": identity["stage034_reference_hashes"],
        },
        "recovery_snapshot_contract": recovery_contract,
        "history_contract_C": history_c,
        "delay_contract_C": delay_c,
        "filter_contract": filter_contract,
        "gates": gates,
        "comparisons": comparison.to_dict(orient="records"),
        "escalate_to_multicycle": escalate,
        "decision": (
            "stage037_short_mirror_block_pass_full_period_ask_before_multicycle"
            if escalate
            else "stage037_short_mirror_block_fail_full_period_stop"
        ),
        "order_api_called_count": 0,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
    }
    output_frames[SUMMARY_NAME] = summary
    output_frames[COMPARISON_NAME] = comparison
    output_frames[CURVE_NAME] = curve
    output_frames[FILTER_CONTRACT_NAME] = pd.DataFrame([filter_contract])
    _publish(output_frames, decision, _report(summary, comparison, decision), _plot(curve))
    shutil.rmtree(RECOVERY_DIR, ignore_errors=True)
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
