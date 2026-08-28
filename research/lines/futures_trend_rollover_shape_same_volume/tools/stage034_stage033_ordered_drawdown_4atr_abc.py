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

import qmt_roll_candidate_stage032_long_range_stall_filter_config as stage032_cfg  # noqa: E402
import qmt_roll_candidate_stage033_ordered_drawdown_or_filter_config as stage033_cfg  # noqa: E402
import qmt_roll_candidate_stage034_ordered_drawdown_4atr_config as stage034_cfg  # noqa: E402
import qmt_roll_official_live_config as live_cfg  # noqa: E402
import stage028_q_delayed_rollover_abc as s28  # noqa: E402
import stage029_stage028_multicycle_abc as s29  # noqa: E402


LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage034"
STAGE032_DIR = LINE_DIR / "artifacts" / "stage032"
STAGE033_DIR = LINE_DIR / "artifacts" / "stage033"
START = pd.Timestamp("2018-01-01")
EXPECTED_FIRST_TRADING_DAY = pd.Timestamp("2018-01-02")
END = pd.Timestamp("2026-08-25")

ARMS: tuple[dict[str, str], ...] = (
    {
        "arm": "A",
        "profile": "stage034_A_formal_q",
        "label": "A: 当前正式 Q",
        "plot_label": "A Formal Q",
        "color": "#2563eb",
    },
    {
        "arm": "B",
        "profile": "stage034_B_stage033_ordered_drawdown_3atr",
        "label": "B: Stage033 有序回撤严格大于3倍ATR5",
        "plot_label": "B Stage033: ordered drawdown > 3 ATR",
        "color": "#dc2626",
    },
    {
        "arm": "C",
        "profile": "stage034_C_ordered_drawdown_4atr",
        "label": "C: Stage034 有序回撤严格大于4倍ATR5",
        "plot_label": "C Stage034: ordered drawdown > 4 ATR",
        "color": "#16a34a",
    },
)

METRICS = s28.METRICS
SUMMARY_NAME = "stage034_abc_summary.csv"
COMPARISON_NAME = "stage034_abc_comparison.csv"
CURVE_NAME = "stage034_abc_curve.csv"
FILTER_NAME = "stage034_long_range_atr_diagnostics.csv"
FILTER_CONTRACT_NAME = "stage034_long_range_atr_contract_summary.csv"
ROLLOVER_NAME = "stage034_rollover_diagnostics.csv"
DELAY_NAME = "stage034_delay_diagnostics.csv"
TRADES_NAME = "stage034_trades.csv"
TRADE_EVENTS_NAME = "stage034_trade_events.csv"
DECISION_NAME = "stage034_decision.json"
REPORT_NAME = "stage034_report.md"
CHART_NAME = "stage034_full_period_equity_abc.png"

REFERENCE_FILES = {
    SUMMARY_NAME: "stage033_abc_summary.csv",
    CURVE_NAME: "stage033_abc_curve.csv",
    FILTER_NAME: "stage033_long_range_atr_diagnostics.csv",
    ROLLOVER_NAME: "stage033_rollover_diagnostics.csv",
    DELAY_NAME: "stage033_delay_diagnostics.csv",
    TRADES_NAME: "stage033_trades.csv",
    TRADE_EVENTS_NAME: "stage033_trade_events.csv",
}


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=PROJECT_DIR, check=True, capture_output=True, text=True
    ).stdout.strip()


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
        return stage033_cfg.build_candidate_overrides()
    if arm == "C":
        return stage034_cfg.build_candidate_overrides()
    raise ValueError(f"unknown stage034 arm:{arm}")


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
    return {
        "long_signal_range_ordered_drawdown_atr_multiplier": (None, 4.0),
    }


def _preflight() -> dict[str, Any]:
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", stage034_cfg.BASE_COMMIT, "HEAD"],
        cwd=PROJECT_DIR,
        check=True,
    )
    identity = s28._assert_identity_and_scope()
    subprocess.run(
        [
            "git",
            "diff",
            "--quiet",
            stage034_cfg.BASE_COMMIT,
            "--",
            str(STAGE033_DIR.relative_to(PROJECT_DIR)),
        ],
        cwd=PROJECT_DIR,
        check=True,
    )
    diff = override_diff("B", "C")
    if diff != _expected_override_diff():
        raise RuntimeError(f"stage034_override_scope_drift:{diff}")
    if float(build_arm_overrides("C")["long_signal_range_atr_multiplier"]) != 3.0:
        raise RuntimeError("stage034_expansion_stall_multiplier_drift")
    reference_decision = json.loads(
        (STAGE033_DIR / "stage033_decision.json").read_text(encoding="utf-8")
    )
    if (
        reference_decision.get("stage") != "Stage033"
        or not reference_decision.get("reproduction", {}).get("all_pass")
        or not reference_decision.get("filter_contract", {}).get("all_pass")
        or reference_decision.get("order_api_called_count") != 0
        or reference_decision.get("send_order_api_called_count") != 0
        or reference_decision.get("cancel_order_api_called_count") != 0
        or reference_decision.get("ctp_connected") is not False
        or reference_decision.get("identity", {}).get("formal_identity")
        != identity["formal_identity"]
        or reference_decision.get("identity", {}).get("production_identity")
        != identity["production_identity"]
        or reference_decision.get("identity", {}).get("remote_master")
        != identity["remote_master"]
    ):
        raise RuntimeError("stage034_stage033_reference_invalid")
    runtime = s29._assert_runtime_database_binding()
    database_path = Path(runtime["database_path"])
    reference_hashes = {
        path.name: _file_sha256(path)
        for path in sorted(STAGE033_DIR.iterdir())
        if path.is_file()
    }
    return {
        **identity,
        "stage033_base_commit": stage034_cfg.BASE_COMMIT,
        "stage033_to_stage034_override_diff": diff,
        "stage033_reference_hashes": reference_hashes,
        "runtime_binding": {
            **runtime,
            "database_sha256": _file_sha256(database_path),
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


def _reference_frame(filename: str) -> pd.DataFrame:
    frame = pd.read_csv(STAGE033_DIR / filename)
    if "experiment_arm" not in frame.columns:
        return frame
    reference = frame[frame["experiment_arm"].astype(str).isin({"A", "C"})].copy()
    reference.loc[reference["experiment_arm"].astype(str).eq("C"), "experiment_arm"] = "B"
    if "profile" in reference.columns:
        reference.loc[reference["experiment_arm"].astype(str).eq("A"), "profile"] = ARMS[0]["profile"]
        reference.loc[reference["experiment_arm"].astype(str).eq("B"), "profile"] = ARMS[1]["profile"]
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


def _metric_delta(left: pd.Series, right: pd.Series) -> dict[str, float]:
    return {metric: float(right[metric]) - float(left[metric]) for metric in METRICS}


def _assert_coverage(summary: pd.DataFrame, curve: pd.DataFrame) -> None:
    if len(summary) != 3 or set(summary["experiment_arm"].astype(str)) != {"A", "B", "C"}:
        raise RuntimeError("stage034_summary_arm_identity_failed")
    for arm in ("A", "B", "C"):
        row = summary[summary["experiment_arm"].astype(str).eq(arm)].iloc[0]
        dates = pd.to_datetime(
            curve[curve["experiment_arm"].astype(str).eq(arm)]["date"],
            errors="raise",
            format="mixed",
        ).dt.normalize()
        if (
            len(dates) != 2098
            or dates.duplicated().any()
            or dates.min() != EXPECTED_FIRST_TRADING_DAY
            or dates.max() != END
            or pd.Timestamp(row["analysis_start"]).normalize() != EXPECTED_FIRST_TRADING_DAY
            or pd.Timestamp(row["analysis_end"]).normalize() != END
        ):
            raise RuntimeError(f"stage034_full_period_coverage_failed:{arm}")


def _filter_contract(diagnostics: pd.DataFrame) -> dict[str, Any]:
    frame = diagnostics[diagnostics["experiment_arm"].astype(str).eq("C")].copy()
    numeric_columns = (
        "long_signal_range_value",
        "long_signal_range_prior_atr",
        "long_signal_range_atr_threshold",
        "long_signal_range_recent_gain",
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
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    valid_reasons = {
        "range_strictly_above_and_recent_gain_below_threshold",
        "range_stall_and_ordered_drawdown_both",
        "ordered_drawdown_strictly_above_threshold",
        "range_above_but_recent_gain_not_stalled",
        "range_not_above_threshold",
    }
    valid = frame[frame["long_signal_range_atr_reason"].astype(str).isin(valid_reasons)]
    expansion = valid["long_signal_range_expansion_stall_condition_met"].eq(1)
    ordered = valid["long_signal_range_ordered_drawdown_condition_met"].eq(1)
    combined = valid["long_signal_range_atr_condition_met"].eq(1)
    blocked = valid[valid["long_signal_range_atr_blocked"].eq(1)]
    matched_zero = valid[
        combined & valid["long_signal_range_atr_selected_volume_before"].eq(0)
    ]
    expansion_expected = valid["long_signal_range_value"].gt(
        valid["long_signal_range_atr_threshold"]
    ) & valid["long_signal_range_recent_gain"].lt(
        valid["long_signal_range_recent_gain_atr_threshold"]
    )
    ordered_expected = valid["long_signal_range_ordered_drawdown_value"].gt(
        valid["long_signal_range_ordered_drawdown_atr_threshold"]
    )
    result = {
        "diagnostic_count": int(len(frame)),
        "valid_long_count": int(len(valid)),
        "condition_met_count": int(combined.sum()),
        "expansion_stall_condition_count": int(expansion.sum()),
        "ordered_drawdown_condition_count": int(ordered.sum()),
        "both_condition_count": int((expansion & ordered).sum()),
        "expansion_stall_only_count": int((expansion & ~ordered).sum()),
        "ordered_drawdown_only_count": int((ordered & ~expansion).sum()),
        "actual_incremental_block_count": int(len(blocked)),
        "matched_after_prior_zero_count": int(len(matched_zero)),
        "actual_block_context_counts": {
            str(key): int(value)
            for key, value in blocked.groupby("entry_context").size().to_dict().items()
        },
        "config_pass": bool(
            not frame.empty
            and frame["long_signal_range_atr_enabled"].astype(int).eq(1).all()
            and frame["long_signal_range_lookback"].astype(int).eq(10).all()
            and frame["long_signal_range_atr_period"].astype(int).eq(5).all()
            and np.isclose(frame["long_signal_range_atr_multiplier"].astype(float), 3.0).all()
            and np.isclose(
                frame["long_signal_range_ordered_drawdown_atr_multiplier"].astype(float),
                4.0,
            ).all()
            and frame["long_signal_range_enable_ordered_drawdown_filter"].astype(int).eq(1).all()
        ),
        "or_semantics_pass": bool(valid.empty or combined.equals(expansion | ordered)),
        "expansion_component_pass": bool(valid.empty or expansion.equals(expansion_expected)),
        "ordered_component_pass": bool(
            valid.empty
            or (
                ordered.equals(ordered_expected)
                and valid["long_signal_range_ordered_drawdown_peak_index"]
                .lt(valid["long_signal_range_ordered_drawdown_trough_index"])
                .all()
            )
        ),
        "blocked_semantics_pass": bool(
            blocked.empty
            or (
                blocked["direction"].astype(str).eq("long").all()
                and blocked["entry_context"].astype(str)
                .isin({"flat_entry", "reverse_entry", "rollover_reopen"})
                .all()
                and blocked["long_signal_range_atr_selected_volume_before"].gt(0).all()
                and blocked["long_signal_range_atr_selected_volume_after"].eq(0).all()
            )
        ),
        "prior_zero_not_double_counted_pass": bool(
            matched_zero.empty or matched_zero["long_signal_range_atr_blocked"].eq(0).all()
        ),
        "short_never_blocked_pass": bool(
            frame[frame["direction"].astype(str).eq("short")][
                "long_signal_range_atr_blocked"
            ].eq(0).all()
        ),
    }
    result["all_pass"] = bool(
        result["config_pass"]
        and result["or_semantics_pass"]
        and result["expansion_component_pass"]
        and result["ordered_component_pass"]
        and result["blocked_semantics_pass"]
        and result["prior_zero_not_double_counted_pass"]
        and result["short_never_blocked_pass"]
    )
    return result


def _named_case_contract(diagnostics: pd.DataFrame) -> dict[str, Any]:
    frame = diagnostics[diagnostics["experiment_arm"].astype(str).eq("C")].copy()

    def one(symbol: str, date: str) -> pd.Series:
        rows = frame[
            frame["contract_vt_symbol"].astype(str).str.casefold().eq(symbol.casefold())
            & frame["date"].astype(str).eq(date)
        ]
        if len(rows) != 1:
            raise RuntimeError(f"stage034_named_case_cardinality:{symbol}:{date}:{len(rows)}")
        return rows.iloc[0]

    cu = one("cu2109.SHFE", "2021-07-30")
    fg = one("FG009.CZCE", "2020-07-02")
    oi = one("OI905.CZCE", "2019-03-25")
    lh = one("lh2201.DCE", "2021-10-29")
    cu_pass = bool(
        np.isclose(float(cu["long_signal_range_atr_threshold"]), 3654.0)
        and int(cu["long_signal_range_expansion_stall_condition_met"]) == 1
        and int(cu["long_signal_range_atr_blocked"]) == 1
    )
    fg_pass = bool(
        int(fg["long_signal_range_expansion_stall_condition_met"]) == 0
        and int(fg["long_signal_range_ordered_drawdown_condition_met"]) == 0
        and int(fg["long_signal_range_atr_blocked"]) == 0
    )
    oi_pass = bool(
        np.isclose(float(oi["long_signal_range_ordered_drawdown_value"]), 425.0)
        and np.isclose(float(oi["long_signal_range_prior_atr"]), 104.6)
        and np.isclose(
            float(oi["long_signal_range_ordered_drawdown_atr_threshold"]), 418.4
        )
        and int(oi["long_signal_range_ordered_drawdown_condition_met"]) == 1
        and int(oi["long_signal_range_atr_blocked"]) == 1
    )
    lh_pass = bool(
        np.isclose(float(lh["long_signal_range_ordered_drawdown_value"]), 995.0)
        and np.isclose(float(lh["long_signal_range_prior_atr"]), 719.0)
        and int(lh["long_signal_range_ordered_drawdown_condition_met"]) == 0
        and int(lh["long_signal_range_atr_blocked"]) == 0
    )
    return {
        "cu2109_blocked_by_original_3atr_leg_pass": cu_pass,
        "fg009_allowed_pass": fg_pass,
        "oi905_ordered_drawdown_atr_ratio": float(
            oi["long_signal_range_ordered_drawdown_value"]
            / oi["long_signal_range_prior_atr"]
        ),
        "oi905_blocked_above_4atr_pass": oi_pass,
        "lh2201_ordered_drawdown_atr_ratio": float(
            lh["long_signal_range_ordered_drawdown_value"]
            / lh["long_signal_range_prior_atr"]
        ),
        "lh2201_allowed_pass": lh_pass,
        "all_pass": bool(cu_pass and fg_pass and oi_pass and lh_pass),
    }


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
    ax.set_title("Stage034: Formal Q vs Ordered Drawdown >3 ATR vs >4 ATR")
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
        "# Stage034 Stage033有序峰谷回撤4倍ATR敏感性",
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
    s32 = decision["stage032_reference_comparison"]
    contract = decision["filter_contract"]
    lines.extend(
        [
            "",
            "## 增量结果",
            "",
            f"- C相对Stage033 B：期末权益 `{bc['delta_end_equity']:+,.2f}`，收益 "
            f"`{bc['delta_total_return_pct']:+.4f}pp`，回撤 `{bc['delta_max_dd_pct']:+.4f}pp`，"
            f"Sharpe `{bc['delta_sharpe']:+.6f}`。",
            f"- C相对正式A：期末权益 `{ac['delta_end_equity']:+,.2f}`，收益 "
            f"`{ac['delta_total_return_pct']:+.4f}pp`，回撤 `{ac['delta_max_dd_pct']:+.4f}pp`，"
            f"Sharpe `{ac['delta_sharpe']:+.6f}`。",
            f"- C相对Stage032无有序回撤参考：期末权益 `{s32['delta_end_equity']:+,.2f}`，"
            f"Sharpe `{s32['delta_sharpe']:+.6f}`，回撤 `{s32['delta_max_dd_pct']:+.4f}pp`。",
            f"- C中OR命中 `{contract['condition_met_count']}`：原条件A "
            f"`{contract['expansion_stall_condition_count']}`、4倍有序回撤 "
            f"`{contract['ordered_drawdown_condition_count']}`、重叠 "
            f"`{contract['both_condition_count']}`、有序回撤独有 "
            f"`{contract['ordered_drawdown_only_count']}`；过滤节点前正手数置0 "
            f"`{contract['actual_incremental_block_count']}` 个。",
            "",
            "## 安全与研究判断",
            "",
            "- A/B直接复用并按SHA校验Stage033已验证产物；仅C重新运行真引擎。",
            "- OI905仍拦截，lh2201仍放行；原条件A保持3倍ATR阈值。",
            "- 未连接CTP，未调用订单API。",
            f"- 是否进入多周期：`{str(decision['escalate_to_multicycle']).lower()}`。",
            "",
        ]
    )
    return "\n".join(lines)


def _publish(frames: dict[str, pd.DataFrame], decision: dict[str, Any], report: str, chart: bytes) -> None:
    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".stage034.tmp-", dir=OUTPUT_DIR.parent))
    backup = OUTPUT_DIR.with_name(f".stage034.backup-{uuid4().hex}")
    try:
        for filename, frame in frames.items():
            frame.to_csv(temporary / filename, index=False, encoding="utf-8-sig")
        (temporary / DECISION_NAME).write_text(
            json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (temporary / REPORT_NAME).write_text(report, encoding="utf-8")
        (temporary / CHART_NAME).write_bytes(chart)
        if OUTPUT_DIR.exists():
            os.replace(OUTPUT_DIR, backup)
        try:
            os.replace(temporary, OUTPUT_DIR)
        except Exception:
            if backup.exists() and not OUTPUT_DIR.exists():
                os.replace(backup, OUTPUT_DIR)
            raise
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)


def main() -> None:
    identity = _preflight()
    metadata = s28.s513._metadata()
    print(f"[stage034] running C only {START.date()}->{END.date()}", flush=True)
    c_summary, c_curve, c_frames = _run_new_c(metadata)
    reference_summary = _reference_frame("stage033_abc_summary.csv")
    reference_curve = _reference_frame("stage033_abc_curve.csv")
    summary = pd.concat([reference_summary, c_summary], ignore_index=True, sort=False)
    curve = pd.concat([reference_curve, c_curve], ignore_index=True, sort=False)
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
        output_frames[output_name] = pd.concat(
            [reference, current], ignore_index=True, sort=False
        )

    history_c = s28._history_contract(c_frames["rollover_shape_same_volume"], "C")
    delay_c = s28._delay_contract(
        c_frames["rollover_delay"],
        c_frames["rollover_shape_same_volume"],
        c_frames["trade_events"],
    )
    filter_contract = _filter_contract(output_frames[FILTER_NAME])
    named_case_contract = _named_case_contract(output_frames[FILTER_NAME])
    if not history_c["all_pass"] or not delay_c["all_pass"]:
        raise RuntimeError("stage034_stage028_contract_failed")
    if not filter_contract["all_pass"]:
        raise RuntimeError(f"stage034_filter_contract_failed:{filter_contract}")
    if not named_case_contract["all_pass"]:
        raise RuntimeError(f"stage034_named_case_contract_failed:{named_case_contract}")

    indexed = summary.set_index("experiment_arm")
    a_row, b_row, c_row = indexed.loc["A"], indexed.loc["B"], indexed.loc["C"]
    stage032_summary = pd.read_csv(STAGE032_DIR / "stage032_abc_summary.csv")
    stage032_row = stage032_summary[
        stage032_summary["experiment_arm"].astype(str).eq("C")
    ].iloc[0]
    stage032_delta = _metric_delta(stage032_row, c_row)
    bc = comparison[comparison["comparison"].eq("B_vs_C")].iloc[0]
    ac = comparison[comparison["comparison"].eq("A_vs_C")].iloc[0]
    gates = {
        "scope_exact_only_ordered_drawdown_multiplier_4": override_diff("B", "C")
        == _expected_override_diff(),
        "history_and_delay_contract_pass": bool(history_c["all_pass"] and delay_c["all_pass"]),
        "filter_semantics_pass": bool(filter_contract["all_pass"]),
        "named_case_contract_pass": bool(named_case_contract["all_pass"]),
        "full_period_account_survival": float(c_row["min_equity"]) > 0,
        "C_end_equity_higher_than_stage033_B": float(c_row["end_equity"]) > float(b_row["end_equity"]),
        "C_sharpe_higher_than_stage033_B": float(c_row["sharpe"]) > float(b_row["sharpe"]),
        "C_max_drawdown_not_worse_than_stage033_B_by_more_than_2pp": float(bc["delta_max_dd_pct"]) >= -2.0,
        "C_broker100_fail_count_not_above_stage033_B": int(c_row["days_over_100pct"])
        <= int(b_row["days_over_100pct"]),
        "C_end_equity_not_lower_than_stage032": float(c_row["end_equity"])
        >= float(stage032_row["end_equity"]),
        "C_max_drawdown_not_worse_than_stage032_by_more_than_2pp": stage032_delta["max_dd_pct"] >= -2.0,
        "C_sharpe_not_lower_than_stage032_by_more_than_0_02": stage032_delta["sharpe"] >= -0.02,
        "C_slippage_not_above_stage032": float(c_row["total_slippage"])
        <= float(stage032_row["total_slippage"]),
        "C_broker100_fail_count_not_above_stage032": int(c_row["days_over_100pct"])
        <= int(stage032_row["days_over_100pct"]),
        "C_end_equity_not_lower_than_A": float(c_row["end_equity"]) >= float(a_row["end_equity"]),
        "C_max_drawdown_not_worse_than_A_by_more_than_2pp": float(ac["delta_max_dd_pct"]) >= -2.0,
        "C_sharpe_not_lower_than_A_by_more_than_0_02": float(ac["delta_sharpe"]) >= -0.02,
        "C_slippage_not_above_105pct_of_A": float(c_row["total_slippage"])
        <= 1.05 * float(a_row["total_slippage"]),
        "C_broker10_days_over_100_eq_0": int(c_row["days_over_100pct"]) == 0,
    }
    escalate = bool(all(gates.values()))
    decision = {
        "line_id": "futures_trend_rollover_shape_same_volume",
        "stage": "Stage034",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "identity": identity,
        "base_candidate_version": stage033_cfg.CANDIDATE_VERSION,
        "candidate_version": stage034_cfg.CANDIDATE_VERSION,
        "period": {"start": str(START.date()), "end": str(END.date())},
        "arms": {arm["arm"]: arm["profile"] for arm in ARMS},
        "candidate_hypothesis": (
            "保持Stage032扩张滞涨条件为3倍ATR，仅把有序峰谷回撤从严格大于3倍收紧至4倍，"
            "减少中等回撤趋势误杀，同时保留OI905级极端先高后低拦截。"
        ),
        "overfitting_risk_predeclared": True,
        "reference_reuse": {
            "A_and_B_from_stage033": True,
            "only_C_new_engine_run": True,
            "stage033_reference_hashes": identity["stage033_reference_hashes"],
        },
        "history_contract_C": history_c,
        "delay_contract_C": delay_c,
        "filter_contract": filter_contract,
        "named_case_contract": named_case_contract,
        "stage032_reference_comparison": {
            **{f"stage032_{metric}": float(stage032_row[metric]) for metric in METRICS},
            **{f"C_{metric}": float(c_row[metric]) for metric in METRICS},
            **{f"delta_{metric}": value for metric, value in stage032_delta.items()},
        },
        "gates": gates,
        "comparisons": comparison.to_dict(orient="records"),
        "escalate_to_multicycle": escalate,
        "decision": (
            "stage034_ordered_drawdown_4atr_pass_full_period_run_multicycle"
            if escalate
            else "stage034_ordered_drawdown_4atr_fail_full_period_stop"
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
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
