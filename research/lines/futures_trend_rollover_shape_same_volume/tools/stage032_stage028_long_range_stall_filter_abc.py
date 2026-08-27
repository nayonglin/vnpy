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

import qmt_roll_candidate_stage028_delayed_rollover_config as stage028_cfg  # noqa: E402
import qmt_roll_candidate_stage032_long_range_stall_filter_config as stage032_cfg  # noqa: E402
import qmt_roll_official_live_config as live_cfg  # noqa: E402
import stage028_q_delayed_rollover_abc as s28  # noqa: E402
import stage029_stage028_multicycle_abc as s29  # noqa: E402


LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage032"
STAGE028_DIR = LINE_DIR / "artifacts" / "stage028"
START = pd.Timestamp("2018-01-01")
EXPECTED_FIRST_TRADING_DAY = pd.Timestamp("2018-01-02")
END = pd.Timestamp("2026-08-25")

ARMS: tuple[dict[str, str], ...] = (
    {
        "arm": "A",
        "profile": "stage032_A_formal_q",
        "label": "A: 当前正式 Q（立即换月、旧主力复权历史）",
        "plot_label": "A Formal Q",
        "color": "#2563eb",
    },
    {
        "arm": "B",
        "profile": "stage032_B_stage028_delay_5td",
        "label": "B: Stage028（延迟5交易日、新主力自身K线）",
        "plot_label": "B Stage028 +5 sessions",
        "color": "#dc2626",
    },
    {
        "arm": "C",
        "profile": "stage032_C_stage028_long_range_3d_stall_filter",
        "label": "C: Stage028 + 多头10日扩张且3日滞涨禁开",
        "plot_label": "C Stage032: B + long expansion and 3D stall filter",
        "color": "#16a34a",
    },
)

METRICS = s28.METRICS
SUMMARY_NAME = "stage032_abc_summary.csv"
COMPARISON_NAME = "stage032_abc_comparison.csv"
CURVE_NAME = "stage032_abc_curve.csv"
FILTER_NAME = "stage032_long_range_atr_diagnostics.csv"
FILTER_CONTRACT_NAME = "stage032_long_range_atr_contract_summary.csv"
ROLLOVER_NAME = "stage032_rollover_diagnostics.csv"
DELAY_NAME = "stage032_delay_diagnostics.csv"
TRADES_NAME = "stage032_trades.csv"
TRADE_EVENTS_NAME = "stage032_trade_events.csv"
DECISION_NAME = "stage032_decision.json"
REPORT_NAME = "stage032_report.md"
CHART_NAME = "stage032_full_period_equity_abc.png"


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
        return stage028_cfg.build_candidate_overrides()
    if arm == "C":
        return stage032_cfg.build_candidate_overrides()
    raise ValueError(f"unknown stage032 arm:{arm}")


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
        "enable_long_signal_range_atr_filter": (None, True),
        "long_signal_range_atr_entry_contexts": (
            None,
            "flat_entry,reverse_entry,rollover_reopen",
        ),
        "long_signal_range_atr_multiplier": (None, 3.0),
        "long_signal_range_atr_period": (None, 5),
        "long_signal_range_lookback": (None, 10),
        "long_signal_range_recent_gain_atr_multiplier": (None, 0.5),
        "long_signal_range_recent_gain_lookback": (None, 3),
        "long_signal_range_require_recent_stall": (None, True),
    }


def _preflight() -> dict[str, Any]:
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", stage032_cfg.BASE_COMMIT, "HEAD"],
        cwd=PROJECT_DIR,
        check=True,
    )
    identity = s28._assert_identity_and_scope()
    diff = override_diff("B", "C")
    if diff != _expected_override_diff():
        raise RuntimeError(f"stage032_override_scope_drift:{diff}")
    runtime = s29._assert_runtime_database_binding()
    database_path = Path(runtime["database_path"])
    return {
        **identity,
        "stage028_base_commit": stage032_cfg.BASE_COMMIT,
        "stage028_to_stage032_override_diff": diff,
        "runtime_binding": {
            **runtime,
            "database_sha256": _file_sha256(database_path),
        },
    }


def _run_arm(
    arm: dict[str, str], metadata: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    original_builder = s28.s901.build_official_live_strategy_overrides
    try:
        s28.s901.build_official_live_strategy_overrides = lambda: build_arm_overrides(arm["arm"])
        combined, frames, live_spec = s28.s901._run_live_c9(metadata, START, END)
    finally:
        s28.s901.build_official_live_strategy_overrides = original_builder

    capital = replace(live_spec.capital, variant=arm["profile"], label=arm["label"])
    metric_spec = replace(live_spec, capital=capital, profile=arm["profile"])
    summary, curve = s28.s827._metric(
        {"profile": arm["profile"], "spec": metric_spec}, combined
    )
    summary["experiment_arm"] = arm["arm"]
    summary["window_name"] = "full_2018_20260825"
    summary["window_label"] = "2018-01-01 independent start to 2026-08-25"
    curve["experiment_arm"] = arm["arm"]
    for frame in frames.values():
        if not frame.empty:
            frame["experiment_arm"] = arm["arm"]
    return summary, curve, frames


def _assert_full_period_coverage(summary: pd.DataFrame, curve: pd.DataFrame) -> None:
    expected_arms = {"A", "B", "C"}
    if len(summary) != 3 or set(summary["experiment_arm"].astype(str)) != expected_arms:
        raise RuntimeError("stage032_summary_arm_identity_failed")
    for row in summary.itertuples(index=False):
        actual_start = pd.Timestamp(row.analysis_start).normalize()
        actual_end = pd.Timestamp(row.analysis_end).normalize()
        if actual_start != EXPECTED_FIRST_TRADING_DAY or actual_end != END:
            raise RuntimeError(
                f"stage032_full_period_coverage_failed:{row.experiment_arm}:"
                f"{row.analysis_start}:{row.analysis_end}"
            )
        arm_curve = curve[curve["experiment_arm"].astype(str).eq(str(row.experiment_arm))]
        dates = pd.to_datetime(arm_curve["date"], errors="raise", format="mixed").dt.normalize()
        if dates.duplicated().any():
            raise RuntimeError(f"stage032_duplicate_curve_date:{row.experiment_arm}")
        if len(dates) != 2098 or dates.min() != actual_start or dates.max() != actual_end:
            raise RuntimeError(f"stage032_curve_coverage_failed:{row.experiment_arm}")


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


def _verify_stage028_reproduction(
    summary: pd.DataFrame, curve: pd.DataFrame
) -> dict[str, Any]:
    reference_summary = pd.read_csv(STAGE028_DIR / "stage028_abc_summary.csv")
    reference_curve = pd.read_csv(STAGE028_DIR / "stage028_abc_curve.csv")
    curve_numeric = [
        "account_equity",
        "nav",
        "drawdown_pct",
        "broker10_margin_to_equity_pct",
        "net_pnl",
        "trade_count",
        "total_slippage",
    ]
    result: dict[str, Any] = {"pairs": {}}
    for old_arm, new_arm in (("A", "A"), ("C", "B")):
        old_row = reference_summary[reference_summary["experiment_arm"].astype(str).eq(old_arm)].iloc[0]
        new_row = summary[summary["experiment_arm"].astype(str).eq(new_arm)].iloc[0]
        metric_diffs = {
            metric: abs(float(old_row[metric]) - float(new_row[metric]))
            for metric in METRICS
        }
        old_curve = reference_curve[
            reference_curve["experiment_arm"].astype(str).eq(old_arm)
        ].reset_index(drop=True)
        new_curve = curve[curve["experiment_arm"].astype(str).eq(new_arm)].reset_index(drop=True)
        dates_equal = old_curve["date"].astype(str).equals(new_curve["date"].astype(str))
        old_values = old_curve[curve_numeric].to_numpy(dtype="float64")
        new_values = new_curve[curve_numeric].to_numpy(dtype="float64")
        curve_abs_diff = np.abs(old_values - new_values)
        curve_allowed_diff = np.maximum(
            1e-9,
            np.maximum(np.spacing(np.abs(old_values)), np.spacing(np.abs(new_values))),
        )
        curve_nan_pattern_equal = bool(
            np.array_equal(np.isnan(old_values), np.isnan(new_values))
        )
        max_curve_diff = float(np.nanmax(curve_abs_diff))
        curve_values_equal = bool(
            curve_nan_pattern_equal
            and np.all(curve_abs_diff[~np.isnan(curve_abs_diff)] <= curve_allowed_diff[~np.isnan(curve_abs_diff)])
        )
        pair_pass = bool(
            len(old_curve) == len(new_curve)
            and dates_equal
            and max(metric_diffs.values(), default=0.0) <= 1e-9
            and curve_values_equal
        )
        result["pairs"][f"stage028_{old_arm}_to_stage032_{new_arm}"] = {
            "summary_max_abs_diff": max(metric_diffs.values(), default=0.0),
            "curve_max_abs_diff": max_curve_diff,
            "curve_tolerance": "max(1e-9, one_float64_ulp)",
            "curve_nan_pattern_equal": curve_nan_pattern_equal,
            "row_count": len(new_curve),
            "dates_equal": dates_equal,
            "pass": pair_pass,
        }
    result["all_pass"] = all(pair["pass"] for pair in result["pairs"].values())
    return result


def _filter_contract(diagnostics: pd.DataFrame) -> dict[str, Any]:
    frame = diagnostics[diagnostics["experiment_arm"].astype(str).eq("C")].copy()
    for column in (
        "long_signal_range_value",
        "long_signal_range_prior_atr",
        "long_signal_range_atr_threshold",
        "long_signal_range_recent_gain",
        "long_signal_range_recent_gain_atr_threshold",
        "long_signal_range_recent_stall_condition_met",
        "long_signal_range_atr_selected_volume_before",
        "long_signal_range_atr_selected_volume_after",
        "long_signal_range_atr_condition_met",
        "long_signal_range_atr_blocked",
    ):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    valid = frame[
        frame["long_signal_range_atr_reason"].astype(str).isin(
            {
                "range_strictly_above_and_recent_gain_below_threshold",
                "range_above_but_recent_gain_not_stalled",
                "range_not_above_threshold",
            }
        )
    ]
    blocked = frame[frame["long_signal_range_atr_blocked"].eq(1)]
    positive_unblocked = valid[
        valid["long_signal_range_atr_selected_volume_before"].gt(0)
        & valid["long_signal_range_atr_blocked"].eq(0)
    ]
    matched_zero_before = valid[
        valid["long_signal_range_atr_condition_met"].eq(1)
        & valid["long_signal_range_atr_selected_volume_before"].eq(0)
    ]
    short = frame[frame["direction"].astype(str).eq("short")]
    allowed_contexts = {"flat_entry", "reverse_entry", "rollover_reopen"}
    actual_context_counts = {
        str(key): int(value)
        for key, value in blocked.groupby("entry_context").size().to_dict().items()
    }
    result = {
        "diagnostic_count": int(len(frame)),
        "valid_long_count": int(len(valid)),
        "condition_met_count": int(frame["long_signal_range_atr_condition_met"].eq(1).sum()),
        "actual_incremental_block_count": int(len(blocked)),
        "matched_after_prior_zero_count": int(len(matched_zero_before)),
        "actual_block_context_counts": actual_context_counts,
        "config_pass": bool(
            not frame.empty
            and frame["long_signal_range_atr_enabled"].astype(int).eq(1).all()
            and frame["long_signal_range_lookback"].astype(int).eq(10).all()
            and frame["long_signal_range_atr_period"].astype(int).eq(5).all()
            and frame["long_signal_range_require_recent_stall"].astype(int).eq(1).all()
            and frame["long_signal_range_recent_gain_lookback"].astype(int).eq(3).all()
            and np.isclose(
                pd.to_numeric(frame["long_signal_range_atr_multiplier"], errors="coerce"),
                3.0,
                rtol=0.0,
                atol=1e-12,
            ).all()
            and np.isclose(
                pd.to_numeric(
                    frame["long_signal_range_recent_gain_atr_multiplier"],
                    errors="coerce",
                ),
                0.5,
                rtol=0.0,
                atol=1e-12,
            ).all()
        ),
        "blocked_semantics_pass": bool(
            blocked.empty
            or (
                blocked["direction"].astype(str).eq("long").all()
                and blocked["entry_context"].astype(str).isin(allowed_contexts).all()
                and blocked["long_signal_range_atr_selected_volume_before"].gt(0).all()
                and blocked["long_signal_range_atr_selected_volume_after"].eq(0).all()
                and blocked["long_signal_range_value"]
                .gt(blocked["long_signal_range_atr_threshold"])
                .all()
                and blocked["long_signal_range_recent_gain"]
                .lt(blocked["long_signal_range_recent_gain_atr_threshold"])
                .all()
            )
        ),
        "positive_unblocked_semantics_pass": bool(
            positive_unblocked.empty
            or (
                positive_unblocked["long_signal_range_value"].le(
                    positive_unblocked["long_signal_range_atr_threshold"]
                )
                | positive_unblocked["long_signal_range_recent_gain"].ge(
                    positive_unblocked[
                        "long_signal_range_recent_gain_atr_threshold"
                    ]
                )
            ).all()
        ),
        "short_never_blocked_pass": bool(
            short.empty
            or (
                short["long_signal_range_atr_blocked"].eq(0).all()
                and short["long_signal_range_atr_reason"].astype(str).eq("direction_excluded").all()
            )
        ),
        "prior_zero_not_double_counted_pass": bool(
            matched_zero_before.empty
            or matched_zero_before["long_signal_range_atr_blocked"].eq(0).all()
        ),
    }
    result["all_pass"] = bool(
        result["config_pass"]
        and result["blocked_semantics_pass"]
        and result["positive_unblocked_semantics_pass"]
        and result["short_never_blocked_pass"]
        and result["prior_zero_not_double_counted_pass"]
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
            raise RuntimeError(f"stage032_named_case_cardinality:{symbol}:{date}:{len(rows)}")
        return rows.iloc[0]

    cu = one("cu2109.SHFE", "2021-07-30")
    fg = one("FG009.CZCE", "2020-07-02")
    cu_pass = bool(
        np.isclose(float(cu["long_signal_range_value"]), 5340.0)
        and np.isclose(float(cu["long_signal_range_prior_atr"]), 1218.0)
        and np.isclose(float(cu["long_signal_range_recent_gain"]), 50.0)
        and int(cu["long_signal_range_atr_blocked"]) == 1
        and int(cu["long_signal_range_atr_selected_volume_before"]) > 0
        and int(cu["long_signal_range_atr_selected_volume_after"]) == 0
    )
    fg_pass = bool(
        np.isclose(float(fg["long_signal_range_value"]), 67.0)
        and np.isclose(float(fg["long_signal_range_prior_atr"]), 18.4)
        and np.isclose(float(fg["long_signal_range_recent_gain"]), 24.0)
        and int(fg["long_signal_range_atr_blocked"]) == 0
        and int(fg["long_signal_range_atr_selected_volume_before"]) > 0
        and int(fg["long_signal_range_atr_selected_volume_after"])
        == int(fg["long_signal_range_atr_selected_volume_before"])
        and str(fg["long_signal_range_atr_reason"])
        == "range_above_but_recent_gain_not_stalled"
    )
    return {
        "cu2109_signal_date": "2021-07-30",
        "cu2109_range_atr_ratio": float(
            cu["long_signal_range_value"] / cu["long_signal_range_prior_atr"]
        ),
        "cu2109_recent_gain_atr_ratio": float(
            cu["long_signal_range_recent_gain"] / cu["long_signal_range_prior_atr"]
        ),
        "cu2109_blocked_pass": cu_pass,
        "fg009_signal_date": "2020-07-02",
        "fg009_range_atr_ratio": float(
            fg["long_signal_range_value"] / fg["long_signal_range_prior_atr"]
        ),
        "fg009_recent_gain_atr_ratio": float(
            fg["long_signal_range_recent_gain"] / fg["long_signal_range_prior_atr"]
        ),
        "fg009_allowed_pass": fg_pass,
        "all_pass": bool(cu_pass and fg_pass),
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
    ax.set_title(
        "Stage032: Formal Q vs Stage028 +5TD vs Long 10D Expansion + 3D Stall Filter"
    )
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
        "# Stage032 五日换月版 + 多头10日扩张且3日滞涨过滤",
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
    named = decision["named_case_contract"]
    lines.extend(
        [
            "",
            "## 增量结果",
            "",
            f"- C相对B：期末权益 `{bc['delta_end_equity']:+,.2f}`，收益 "
            f"`{bc['delta_total_return_pct']:+.4f}pp`，回撤 `{bc['delta_max_dd_pct']:+.4f}pp`，"
            f"Sharpe `{bc['delta_sharpe']:+.6f}`。",
            f"- C相对A：期末权益 `{ac['delta_end_equity']:+,.2f}`，收益 "
            f"`{ac['delta_total_return_pct']:+.4f}pp`，回撤 `{ac['delta_max_dd_pct']:+.4f}pp`，"
            f"Sharpe `{ac['delta_sharpe']:+.6f}`。",
            f"- 条件命中 `{contract['condition_met_count']}` 次；已有规则先归零后重复命中 "
            f"`{contract['matched_after_prior_zero_count']}` 次；C路径过滤节点前仍为正手数并被置0的"
            f"sizing候选事件 `{contract['actual_incremental_block_count']}` 个，入口分布 "
            f"`{json.dumps(contract['actual_block_context_counts'], ensure_ascii=False)}`。"
            f"这些不是B路径原本必然成交的{contract['actual_incremental_block_count']}笔反事实交易。",
            f"- 点名案例：cu2109区间/ATR `{named['cu2109_range_atr_ratio']:.4f}`、"
            f"3日涨幅/ATR `{named['cu2109_recent_gain_atr_ratio']:.4f}`，已拦截；"
            f"FG009对应为 `{named['fg009_range_atr_ratio']:.4f}` / "
            f"`{named['fg009_recent_gain_atr_ratio']:.4f}`，已放行。",
            "",
            "## 安全与研究判断",
            "",
            "- A/B逐值复现Stage028；只读研究数据库，未连接CTP，未调用订单API。",
            "- 运行前过拟合判断：是，偏高；只允许本次冻结口径，不扫描窗口、ATR周期或倍数。",
            f"- 是否进入多周期：`{str(decision['escalate_to_multicycle']).lower()}`。",
            "",
        ]
    )
    return "\n".join(lines)


def _publish(
    frames: dict[str, pd.DataFrame], decision: dict[str, Any], report: str, chart: bytes
) -> None:
    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".stage032.tmp-", dir=OUTPUT_DIR.parent))
    backup = OUTPUT_DIR.with_name(f".stage032.backup-{uuid4().hex}")
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
    summaries: list[pd.DataFrame] = []
    curves: list[pd.DataFrame] = []
    collected: dict[str, list[pd.DataFrame]] = {
        "long_signal_range_atr": [],
        "rollover_shape_same_volume": [],
        "rollover_delay": [],
        "trades": [],
        "trade_events": [],
    }
    for arm in ARMS:
        print(f"[stage032] running {arm['arm']} {START.date()}->{END.date()}", flush=True)
        arm_summary, arm_curve, frames = _run_arm(arm, metadata)
        summaries.append(arm_summary)
        curves.append(arm_curve)
        for key in collected:
            frame = frames.get(key, pd.DataFrame()).copy()
            if not frame.empty:
                collected[key].append(frame)

    summary = pd.concat(summaries, ignore_index=True, sort=False)
    curve = pd.concat(curves, ignore_index=True, sort=False)
    _assert_full_period_coverage(summary, curve)
    frames = {
        key: pd.concat(items, ignore_index=True, sort=False) if items else pd.DataFrame()
        for key, items in collected.items()
    }
    comparison = _comparison(summary)
    reproduction = _verify_stage028_reproduction(summary, curve)
    if not reproduction["all_pass"]:
        raise RuntimeError(f"stage032_stage028_reproduction_failed:{reproduction}")
    history_b = s28._history_contract(frames["rollover_shape_same_volume"], "B")
    history_c = s28._history_contract(frames["rollover_shape_same_volume"], "C")
    delay_c = s28._delay_contract(
        frames["rollover_delay"],
        frames["rollover_shape_same_volume"],
        frames["trade_events"],
    )
    if not history_b["all_pass"] or not history_c["all_pass"] or not delay_c["all_pass"]:
        raise RuntimeError("stage032_stage028_contract_failed")
    filter_contract = _filter_contract(frames["long_signal_range_atr"])
    if not filter_contract["all_pass"]:
        raise RuntimeError(f"stage032_filter_contract_failed:{filter_contract}")
    named_case_contract = _named_case_contract(frames["long_signal_range_atr"])
    if not named_case_contract["all_pass"]:
        raise RuntimeError(f"stage032_named_case_contract_failed:{named_case_contract}")

    indexed = summary.set_index("experiment_arm")
    a_row, b_row, c_row = indexed.loc["A"], indexed.loc["B"], indexed.loc["C"]
    bc = comparison[comparison["comparison"].eq("B_vs_C")].iloc[0]
    ac = comparison[comparison["comparison"].eq("A_vs_C")].iloc[0]
    gates = {
        "scope_exact_frozen_filter": override_diff("B", "C") == _expected_override_diff(),
        "stage028_A_B_reproduction_pass": bool(reproduction["all_pass"]),
        "stage028_history_and_delay_contract_pass": bool(
            history_b["all_pass"] and history_c["all_pass"] and delay_c["all_pass"]
        ),
        "filter_semantics_pass": bool(filter_contract["all_pass"]),
        "named_cu_blocked_fg_allowed_pass": bool(named_case_contract["all_pass"]),
        "has_actual_incremental_blocks": filter_contract["actual_incremental_block_count"] > 0,
        "full_period_account_survival": float(c_row["min_equity"]) > 0,
        "C_end_equity_not_lower_than_B": float(c_row["end_equity"]) >= float(b_row["end_equity"]),
        "C_max_drawdown_not_worse_than_B_by_more_than_2pp": float(bc["delta_max_dd_pct"]) >= -2.0,
        "C_sharpe_not_lower_than_B_by_more_than_0_02": float(bc["delta_sharpe"]) >= -0.02,
        "C_slippage_not_above_B": float(bc["slippage_ratio_C_over_B"]) <= 1.0,
        "C_broker100_fail_count_not_above_B": int(c_row["days_over_100pct"])
        <= int(b_row["days_over_100pct"]),
        "C_end_equity_not_lower_than_A": float(c_row["end_equity"]) >= float(a_row["end_equity"]),
        "C_max_drawdown_not_worse_than_A_by_more_than_2pp": float(ac["delta_max_dd_pct"]) >= -2.0,
        "C_sharpe_not_lower_than_A_by_more_than_0_02": float(ac["delta_sharpe"]) >= -0.02,
        "C_slippage_not_above_105pct_of_A": float(ac["slippage_ratio_C_over_A"]) <= 1.05,
        "C_broker10_days_over_100_eq_0": int(c_row["days_over_100pct"]) == 0,
    }
    escalate = bool(all(gates.values()))
    decision = {
        "line_id": "futures_trend_rollover_shape_same_volume",
        "stage": "Stage032",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "identity": identity,
        "base_candidate_version": stage028_cfg.CANDIDATE_VERSION,
        "candidate_version": stage032_cfg.CANDIDATE_VERSION,
        "period": {"start": str(START.date()), "end": str(END.date())},
        "arms": {arm["arm"]: arm["profile"] for arm in ARMS},
        "candidate_hypothesis": (
            "Stage028多头初始信号若最近10日高低区间严格超过3倍前置ATR5，"
            "且最近3日收盘净涨幅低于0.5倍前置ATR5，可能属于扩张后高位滞涨；"
            "过滤该类开仓可避免错杀仍在顺畅展开的趋势。"
        ),
        "overfitting_risk_predeclared": True,
        "reproduction": reproduction,
        "history_contract_B": history_b,
        "history_contract_C": history_c,
        "delay_contract_C": delay_c,
        "filter_contract": filter_contract,
        "named_case_contract": named_case_contract,
        "gates": gates,
        "comparisons": comparison.to_dict(orient="records"),
        "escalate_to_multicycle": escalate,
        "decision": (
            "stage032_long_range_stall_pass_full_period_run_multicycle"
            if escalate
            else "stage032_long_range_stall_fail_full_period_stop"
        ),
        "order_api_called_count": 0,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
    }
    contract_summary = pd.DataFrame([filter_contract])
    output_frames = {
        SUMMARY_NAME: summary,
        COMPARISON_NAME: comparison,
        CURVE_NAME: curve,
        FILTER_NAME: frames["long_signal_range_atr"],
        FILTER_CONTRACT_NAME: contract_summary,
        ROLLOVER_NAME: frames["rollover_shape_same_volume"],
        DELAY_NAME: frames["rollover_delay"],
        TRADES_NAME: frames["trades"],
        TRADE_EVENTS_NAME: frames["trade_events"],
    }
    _publish(output_frames, decision, _report(summary, comparison, decision), _plot(curve))
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
