#!/usr/bin/env python3
"""Stage007: paired half-year validation for reconciled Stage013 equity."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterator

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage002_stage013_current_ai_halfyear as old_halfyear  # noqa: E402
import stage006_stage013_reconciled_equity_engine as s6  # noqa: E402


LINE_ID = s6.LINE_ID
STAGE_ID = "stage007_stage006_reconciled_equity_halfyear"
STAGE_LABEL = "Stage007"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"stage013_current_ai_{STAGE_ID}"

A_VERSION = s6.A_VERSION
C_VERSION = s6.C_VERSION
VERSIONS = (A_VERSION, C_VERSION)
CAPITAL = s6.stage001.CAPITAL
REQUESTED_END = pd.Timestamp("2026-06-30")
START_DATES = tuple(
    pd.Timestamp(year=year, month=month, day=1)
    for year in range(2020, 2027)
    for month in (1, 7)
    if pd.Timestamp(year=year, month=month, day=1) <= pd.Timestamp("2026-01-01")
)
MATURE_TRADING_DAYS = 252

MATURE_DD_IMPROVED_RATIO_MIN = 0.80
MAX_MATURE_DD_WORSENING_PP = 3.0
MATURE_MEDIAN_RETURN_RETENTION_MIN = 0.70
FULL_RETURN_RETENTION_MIN = 0.70
WORST_DD_IMPROVEMENT_MIN_PP = 3.0

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / STAGE_ID
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
PAIR_PATH = OUT / f"{OUTPUT_PREFIX}_pair_summary_{MODEL_TAG}.csv"
STATS_PATH = OUT / f"{OUTPUT_PREFIX}_stats_{MODEL_TAG}.csv"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
RECONCILIATION_PATH = OUT / f"{OUTPUT_PREFIX}_reconciliation_{MODEL_TAG}.csv"
PILOT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_pilot_audit_{MODEL_TAG}.csv"
PILOT_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_pilot_events_{MODEL_TAG}.csv.gz"
AI_USAGE_PATH = OUT / f"{OUTPUT_PREFIX}_ai_usage_{MODEL_TAG}.csv"
AI_CALENDAR_PATH = OUT / f"{OUTPUT_PREFIX}_ai_calendar_{MODEL_TAG}.csv"
AI_PARITY_PATH = OUT / f"{OUTPUT_PREFIX}_ai_parity_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
LINEAGE_PATH = OUT / f"{OUTPUT_PREFIX}_lineage_{MODEL_TAG}.json"
MANIFEST_PATH = OUT / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.csv"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
NAV_GRID_PATH = OUT / f"{OUTPUT_PREFIX}_nav_grid_{MODEL_TAG}.png"
SUMMARY_CHART_PATH = OUT / f"{OUTPUT_PREFIX}_summary_chart_{MODEL_TAG}.png"

PILOT_VIOLATION_COLUMNS = (
    "official_dd_below_trigger_count",
    "authoritative_dd_below_trigger_count",
    "non_flat_entry_count",
    "not_applied_count",
    "wrong_reason_count",
    "not_opened_count",
    "after_not_one_count",
    "above_active_limit_count",
    "event_equity_mismatch_count",
)
SAVE_FRAME_NAMES = (
    "entry_candidates",
    "trades",
    "trade_events",
    "pilot_gate_events",
    "stage006_equity_daily",
    "stage006_trade_corrections",
)


def _start_month(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _all_reconciliations_pass(
    frame: pd.DataFrame, *, expected_count: int
) -> bool:
    if len(frame) != int(expected_count):
        return False
    required_zero = (
        "missing_date_count",
        "duplicate_date_count",
        "future_trade_violation_count",
    )
    return bool(
        frame["reconciliation_pass"].astype(bool).all()
        and all(
            pd.to_numeric(frame[column], errors="coerce").fillna(1).eq(0).all()
            for column in required_zero
        )
    )


def _all_pilot_semantics_pass(frame: pd.DataFrame) -> bool:
    if frame.empty or int(pd.to_numeric(frame["rows"], errors="coerce").fillna(0).sum()) <= 0:
        return False
    return bool(
        all(
            pd.to_numeric(frame[column], errors="coerce").fillna(1).eq(0).all()
            for column in PILOT_VIOLATION_COLUMNS
        )
    )


@contextmanager
def _requested_window(start: pd.Timestamp) -> Iterator[None]:
    base = s6.stage001.source.s006.base
    old_start = base.REQUESTED_START
    old_end = base.REQUESTED_END
    old_month = base.START_MONTH
    try:
        base.REQUESTED_START = pd.Timestamp(start).normalize()
        base.REQUESTED_END = REQUESTED_END.normalize()
        base.START_MONTH = _start_month(start)
        yield
    finally:
        base.REQUESTED_START = old_start
        base.REQUESTED_END = old_end
        base.START_MONTH = old_month


def _tag(
    frame: pd.DataFrame, start: pd.Timestamp, version: str
) -> pd.DataFrame:
    result = frame.copy()
    if result.empty:
        return result
    result["start_month"] = _start_month(start)
    result["requested_start_month"] = _start_month(start)
    result["requested_end"] = REQUESTED_END.date().isoformat()
    result["version"] = version
    result["stage"] = STAGE_LABEL
    result["model_tag"] = MODEL_TAG
    result["line_id"] = LINE_ID
    return result


def _run_for_start(
    metadata: dict[str, Any],
    profile: dict[str, Any],
    version: str,
    start: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    with _requested_window(start):
        daily, frames = s6._run(metadata, profile, version)
    daily = _tag(daily, start, version)
    return daily, {
        name: _tag(frame, start, version) for name, frame in frames.items()
    }


def _summary_row(
    daily: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    metadata: dict[str, Any],
    version: str,
    start: pd.Timestamp,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    row, curve, closed = s6._summary_row(version, daily, frames, metadata)
    row.update(
        {
            "stage": STAGE_LABEL,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "requested_start_month": _start_month(start),
            "requested_end": REQUESTED_END.date().isoformat(),
        }
    )
    curve = _tag(curve, start, version)
    closed = _tag(closed, start, version)
    return row, curve, closed


def _save_path_details(
    start: pd.Timestamp,
    version: str,
    daily: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    closed: pd.DataFrame,
) -> None:
    prefix = f"{OUTPUT_PREFIX}_{_start_month(start)}_{version}"
    daily.to_csv(
        OUT / f"{prefix}_daily_{MODEL_TAG}.csv.gz",
        index=False,
        encoding="utf-8-sig",
    )
    if not closed.empty:
        closed.to_csv(
            OUT / f"{prefix}_closed_lots_{MODEL_TAG}.csv.gz",
            index=False,
            encoding="utf-8-sig",
        )
    for name in SAVE_FRAME_NAMES:
        frame = frames.get(name, pd.DataFrame())
        if frame.empty:
            continue
        frame.to_csv(
            OUT / f"{prefix}_{name}_{MODEL_TAG}.csv.gz",
            index=False,
            encoding="utf-8-sig",
        )


def _ai_usage_row(
    frames: dict[str, pd.DataFrame], version: str, start: pd.Timestamp
) -> dict[str, Any]:
    entry = frames.get("entry_candidates", pd.DataFrame())
    audit = s6.stage001.source.s006.base._ai_usage_audit(entry)
    if "ai_product_pool_signal_date" in audit.columns:
        summary = audit[
            audit["ai_product_pool_signal_date"].astype(str).eq("__summary__")
        ]
        selected = summary.iloc[0] if not summary.empty else audit.iloc[0]
    else:
        selected = audit.iloc[0]
    row = selected.to_dict()
    row.update(
        {"requested_start_month": _start_month(start), "version": version}
    )
    return row


def _pair_summary(summary: pd.DataFrame, pilot: pd.DataFrame) -> pd.DataFrame:
    rows = []
    pilot_lookup = pilot.set_index("requested_start_month")
    for start_month, group in summary.groupby("requested_start_month", sort=True):
        a = group[group["version"].eq(A_VERSION)].iloc[0]
        c = group[group["version"].eq(C_VERSION)].iloc[0]
        a_return = float(a["total_return_pct"])
        c_return = float(c["total_return_pct"])
        dd_improvement = float(c["max_drawdown_pct"] - a["max_drawdown_pct"])
        mature = min(int(a["trading_days"]), int(c["trading_days"])) >= MATURE_TRADING_DAYS
        rows.append(
            {
                "requested_start_month": start_month,
                "trading_days": min(int(a["trading_days"]), int(c["trading_days"])),
                "mature": int(mature),
                "a_end_equity": float(a["end_equity"]),
                "c_end_equity": float(c["end_equity"]),
                "a_total_return_pct": a_return,
                "c_total_return_pct": c_return,
                "return_retention_ratio": (
                    c_return / a_return if a_return > 0.0 else np.nan
                ),
                "return_delta_pct": c_return - a_return,
                "a_max_drawdown_pct": float(a["max_drawdown_pct"]),
                "c_max_drawdown_pct": float(c["max_drawdown_pct"]),
                "drawdown_improvement_pp": dd_improvement,
                "a_sharpe": float(a["sharpe"]),
                "c_sharpe": float(c["sharpe"]),
                "sharpe_delta": float(c["sharpe"] - a["sharpe"]),
                "a_total_slippage": float(a["total_slippage"]),
                "c_total_slippage": float(c["total_slippage"]),
                "a_total_trade_count": float(a["total_trade_count"]),
                "c_total_trade_count": float(c["total_trade_count"]),
                "a_broker10_peak_pct": float(a["max_broker10_margin_to_equity_pct"]),
                "c_broker10_peak_pct": float(c["max_broker10_margin_to_equity_pct"]),
                "broker10_delta_pp": float(
                    c["max_broker10_margin_to_equity_pct"]
                    - a["max_broker10_margin_to_equity_pct"]
                ),
                "c_positive": int(c_return > 0.0),
                "drawdown_improved_or_equal": int(dd_improvement >= -1e-9),
                "drawdown_worse_gt3pp": int(
                    dd_improvement < -MAX_MATURE_DD_WORSENING_PP - 1e-9
                ),
                "pilot_event_count": int(pilot_lookup.loc[start_month, "rows"]),
            }
        )
    return pd.DataFrame(rows).sort_values("requested_start_month").reset_index(drop=True)


def _stats(pair: pd.DataFrame) -> pd.DataFrame:
    mature = pair[pair["mature"].eq(1)].copy()
    positive_a = mature[mature["a_total_return_pct"].gt(0.0)].copy()
    worst_a_dd = float(mature["a_max_drawdown_pct"].min())
    worst_c_dd = float(mature["c_max_drawdown_pct"].min())
    worst_a_broker = float(mature["a_broker10_peak_pct"].max())
    worst_c_broker = float(mature["c_broker10_peak_pct"].max())
    return pd.DataFrame(
        [
            {
                "sample_count": int(len(pair)),
                "mature_count": int(len(mature)),
                "mature_c_positive_count": int(mature["c_positive"].sum()),
                "mature_dd_improved_count": int(
                    mature["drawdown_improved_or_equal"].sum()
                ),
                "mature_dd_improved_ratio": float(
                    mature["drawdown_improved_or_equal"].mean()
                ),
                "mature_dd_worse_gt3pp_count": int(
                    mature["drawdown_worse_gt3pp"].sum()
                ),
                "positive_a_mature_count": int(len(positive_a)),
                "median_return_retention_ratio": float(
                    positive_a["return_retention_ratio"].median()
                ),
                "min_return_retention_ratio": float(
                    positive_a["return_retention_ratio"].min()
                ),
                "worst_a_drawdown_pct": worst_a_dd,
                "worst_c_drawdown_pct": worst_c_dd,
                "worst_drawdown_improvement_pp": worst_c_dd - worst_a_dd,
                "worst_a_broker10_pct": worst_a_broker,
                "worst_c_broker10_pct": worst_c_broker,
                "worst_broker10_delta_pp": worst_c_broker - worst_a_broker,
                "pilot_event_count": int(pair["pilot_event_count"].sum()),
            }
        ]
    )


def _ai_parity(
    eligibility: dict[str, pd.DataFrame], paths: dict[str, Path]
) -> pd.DataFrame:
    rows = []
    for version in VERSIONS:
        frame = eligibility[version]
        rows.append(
            {
                "version": version,
                "rows": int(len(frame)),
                "eval_date_count": int(frame["eval_date"].nunique()),
                "normalized_sha256": s6.stage001.source._normalized_ai_hash(frame),
                "eligibility_sha256": _sha256(paths[version]),
            }
        )
    result = pd.DataFrame(rows)
    result["all_normalized_equal"] = int(
        result["normalized_sha256"].nunique() == 1
    )
    return result


def _decision(
    pair: pd.DataFrame,
    stats: pd.DataFrame,
    reconciliation: pd.DataFrame,
    pilot: pd.DataFrame,
    ai_usage: pd.DataFrame,
    ai_calendar: pd.DataFrame,
    ai_parity: pd.DataFrame,
) -> dict[str, Any]:
    stat = stats.iloc[0].to_dict()
    full = pair[pair["requested_start_month"].eq("2020-01")].iloc[0]
    performance_gates = {
        "all_mature_c_positive": int(stat["mature_c_positive_count"])
        == int(stat["mature_count"]),
        "mature_dd_improved_ratio_ge_80pct": float(
            stat["mature_dd_improved_ratio"]
        )
        >= MATURE_DD_IMPROVED_RATIO_MIN,
        "no_mature_dd_worse_gt3pp": int(
            stat["mature_dd_worse_gt3pp_count"]
        )
        == 0,
        "mature_median_return_retention_ge_70pct": float(
            stat["median_return_retention_ratio"]
        )
        >= MATURE_MEDIAN_RETURN_RETENTION_MIN,
        "full_2020_return_retention_ge_70pct": float(
            full["return_retention_ratio"]
        )
        >= FULL_RETURN_RETENTION_MIN,
        "cross_start_worst_dd_improves_ge_3pp": float(
            stat["worst_drawdown_improvement_pp"]
        )
        >= WORST_DD_IMPROVEMENT_MIN_PP,
        "worst_c_broker_not_above_a": float(
            stat["worst_broker10_delta_pp"]
        )
        <= 1e-9,
    }
    usage_rows = pd.to_numeric(ai_usage["ai_usage_rows"], errors="coerce").fillna(0)
    enabled_rows = pd.to_numeric(ai_usage["ai_enabled_rows"], errors="coerce").fillna(0)
    missing_signal = pd.to_numeric(
        ai_usage["missing_signal_date_rows"], errors="coerce"
    ).fillna(0)
    monthly = ai_calendar[
        ai_calendar["month"].astype(str).between("2022-01", "2026-06")
    ]
    reconciliation_ok = _all_reconciliations_pass(
        reconciliation, expected_count=len(START_DATES)
    )
    pilot_ok = _all_pilot_semantics_pass(pilot)
    semantic_gates = {
        "all_path_reconciliations_pass": reconciliation_ok,
        "all_pilot_semantics_pass": pilot_ok,
        "ai_eligibility_normalized_equal": bool(
            ai_parity["all_normalized_equal"].all()
        ),
        "all_candidate_rows_ai_enabled": bool((usage_rows == enabled_rows).all()),
        "no_missing_ai_signal_date_rows": bool(missing_signal.sum() == 0),
        "monthly_ai_policy_2022_2026_complete": bool(
            len(monthly) == 54 and monthly["present"].eq(1).all()
        ),
    }
    performance_ok = all(performance_gates.values())
    semantics_ok = all(semantic_gates.values())
    return {
        "stage": STAGE_LABEL,
        "stage_id": STAGE_ID,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "requested_starts": [_start_month(item) for item in START_DATES],
        "requested_end": REQUESTED_END.date().isoformat(),
        "mature_trading_days": MATURE_TRADING_DAYS,
        "performance_gates": performance_gates,
        "semantic_gates": semantic_gates,
        "performance_ok": bool(performance_ok),
        "semantics_ok": bool(semantics_ok),
        "stats": stat,
        "full_2020_pair": full.to_dict(),
        "decision": (
            "stage007_pass_reconciled_halfyear_pending_cost_review"
            if performance_ok and semantics_ok
            else "stage007_fail_close_no_parameter_rescue"
        ),
        "overfit_before": "low: frozen rule, starts, maturity, and gates",
        "overfit_after": "pending_independent_review",
        "continue_value_before": "yes: falsify single-start reconciled Stage013",
        "continue_value_after": "pending_independent_review",
    }


def _plot_nav_grid(curves: pd.DataFrame, pair: pd.DataFrame) -> None:
    fig, axes = plt.subplots(4, 4, figsize=(20, 16))
    colors = {A_VERSION: "#111827", C_VERSION: "#0f766e"}
    labels = {A_VERSION: "A current C9", C_VERSION: "C reconciled Stage013"}
    starts = sorted(curves["requested_start_month"].unique())
    for axis, start_month in zip(axes.flat, starts):
        subset = curves[curves["requested_start_month"].eq(start_month)]
        for version in VERSIONS:
            group = subset[subset["version"].eq(version)].sort_values("date")
            equity = pd.to_numeric(
                group["account_equity_for_metrics"], errors="coerce"
            ).ffill()
            axis.plot(
                pd.to_datetime(group["date"]),
                equity / CAPITAL,
                color=colors[version],
                label=labels[version],
                linewidth=1.0,
            )
        row = pair[pair["requested_start_month"].eq(start_month)].iloc[0]
        axis.set_title(
            f"{start_month} | ret A {row['a_total_return_pct']:.0f}% C {row['c_total_return_pct']:.0f}%\n"
            f"DD A {row['a_max_drawdown_pct']:.1f}% C {row['c_max_drawdown_pct']:.1f}%",
            fontsize=9,
        )
        axis.axhline(1.0, color="#94a3b8", linestyle=":", linewidth=0.7)
        locator = mdates.AutoDateLocator(minticks=3, maxticks=5)
        axis.xaxis.set_major_locator(locator)
        axis.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
        axis.grid(alpha=0.22)
    for axis in axes.flat[len(starts) :]:
        axis.axis("off")
    axes.flat[0].legend(fontsize=8)
    fig.suptitle("Stage007 reconciled Stage013 half-year starts", fontsize=15)
    fig.tight_layout()
    fig.savefig(NAV_GRID_PATH, dpi=170, bbox_inches="tight")
    plt.close(fig)


def _plot_summary(pair: pd.DataFrame) -> None:
    x = np.arange(len(pair))
    labels = [
        f"{row.requested_start_month}{'*' if int(row.mature) == 0 else ''}"
        for row in pair.itertuples(index=False)
    ]
    width = 0.38
    fig, axes = plt.subplots(2, 2, figsize=(17, 10))
    axes[0, 0].bar(x - width / 2, pair["a_total_return_pct"], width, color="#64748b", label="A")
    axes[0, 0].bar(x + width / 2, pair["c_total_return_pct"], width, color="#0f766e", label="C")
    axes[0, 0].set_title("Total return by start")
    axes[0, 0].legend()
    axes[0, 1].bar(x - width / 2, pair["a_max_drawdown_pct"], width, color="#64748b", label="A")
    axes[0, 1].bar(x + width / 2, pair["c_max_drawdown_pct"], width, color="#0f766e", label="C")
    axes[0, 1].set_title("Maximum drawdown by start")
    axes[1, 0].plot(x, pair["return_retention_ratio"] * 100.0, marker="o", color="#2563eb")
    axes[1, 0].axhline(70.0, color="#dc2626", linestyle="--", linewidth=0.9)
    axes[1, 0].set_title("C/A return retention")
    axes[1, 1].bar(x, pair["drawdown_improvement_pp"], color="#16a34a")
    axes[1, 1].axhline(0.0, color="#111827", linewidth=0.7)
    axes[1, 1].set_title("Drawdown improvement pp")
    for axis in axes.flat:
        axis.set_xticks(x)
        axis.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
        axis.grid(axis="y", alpha=0.22)
    fig.suptitle("Stage007 reconciled Stage013 multi-start summary", fontsize=15)
    fig.tight_layout()
    fig.savefig(SUMMARY_CHART_PATH, dpi=170, bbox_inches="tight")
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    pair: pd.DataFrame,
    stats: pd.DataFrame,
    reconciliation: pd.DataFrame,
    pilot: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    REPORT_PATH.write_text(
        f"""# Stage007 权威权益 Stage013 逐半年 A/C

- 生成时间：`{decision['generated_at']}`
- 决策：`{decision['decision']}`
- 绩效门：`{decision['performance_ok']}`
- 语义门：`{decision['semantics_ok']}`
- 独立 review：待完成。

## 跨起点统计

{stats.to_markdown(index=False)}

## A/C 配对

{pair.to_markdown(index=False)}

## 分臂结果

{summary.to_markdown(index=False)}

## 权益对账

{reconciliation.to_markdown(index=False)}

## Pilot 语义

{pilot.to_markdown(index=False)}
""",
        encoding="utf-8",
    )


def _lineage(metadata: dict[str, Any]) -> dict[str, Any]:
    paths = {
        "stage007_tool": Path(__file__).resolve(),
        "stage007_test": TOOLS_DIR / "test_stage007_stage006_reconciled_equity_halfyear.py",
        "stage006_tool": Path(s6.__file__).resolve(),
        "stage006_test": TOOLS_DIR / "test_stage006_stage013_reconciled_equity_engine.py",
        "stage013_source": Path(s6.stage001.stage013.__file__).resolve(),
        "official_ai": s6.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
    }
    result = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "inputs": {},
        "metadata_hashes": {},
        "history_database_snapshot_complete": False,
    }
    for name, path in paths.items():
        result["inputs"][name] = {
            "path": str(path),
            "sha256": _sha256(path),
            "bytes": int(path.stat().st_size),
        }
    for key in ("vt_symbols", "rates", "slippages", "sizes", "priceticks", "margin_ratios"):
        value = metadata.get(key, {})
        payload = json.dumps(value, default=str, sort_keys=True, ensure_ascii=True)
        result["metadata_hashes"][key] = {
            "rows": int(len(value)),
            "sha256": hashlib.sha256(payload.encode("ascii")).hexdigest(),
        }
    return result


def _manifest() -> pd.DataFrame:
    rows = []
    for path in sorted(OUT.iterdir()):
        if not path.is_file() or path == MANIFEST_PATH:
            continue
        rows.append(
            {"file": path.name, "bytes": int(path.stat().st_size), "sha256": _sha256(path)}
        )
    return pd.DataFrame(rows)


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    metadata = s6.stage001.source._metadata()
    a_eligibility = s6.stage001.source.s006._official_eligibility_for_strategy(
        s6.A_STRATEGY, A_VERSION
    )
    c_eligibility = s6.stage001.source.s006._official_eligibility_for_strategy(
        s6.C_STRATEGY, C_VERSION
    )
    # Stage-local copies avoid mutating Stage006's output lineage.
    paths: dict[str, Path] = {}
    eligibility = {A_VERSION: a_eligibility, C_VERSION: c_eligibility}
    for version, frame in eligibility.items():
        path = OUT / f"{OUTPUT_PREFIX}_{version}_eligibility_{MODEL_TAG}.csv"
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        paths[version] = path
    profiles = {
        A_VERSION: s6.stage001._a_profile(metadata, paths[A_VERSION]),
        C_VERSION: s6._candidate_profile(metadata, paths[C_VERSION]),
    }

    summary_rows = []
    curves = []
    reconciliation_rows = []
    pilot_rows = []
    pilot_events = []
    ai_usage_rows = []
    total_runs = len(START_DATES) * len(VERSIONS)
    run_index = 0
    for start in START_DATES:
        for version in VERSIONS:
            run_index += 1
            print(
                f"[stage007] run {run_index}/{total_runs} start={_start_month(start)} version={version}",
                flush=True,
            )
            daily, frames = _run_for_start(
                metadata, profiles[version], version, start
            )
            row, curve, closed = _summary_row(
                daily, frames, metadata, version, start
            )
            _save_path_details(start, version, daily, frames, closed)
            summary_rows.append(row)
            curves.append(curve)
            ai_usage_rows.append(_ai_usage_row(frames, version, start))
            if version == C_VERSION:
                reconciliation = s6._equity_reconciliation(daily, frames)
                reconciliation["requested_start_month"] = _start_month(start)
                reconciliation_rows.append(reconciliation)
                pilot = s6._pilot_audit(daily, frames)
                pilot = pilot[pilot["sample"].astype(str).eq("all")].copy()
                pilot["requested_start_month"] = _start_month(start)
                pilot_rows.append(pilot)
                events = frames.get("pilot_gate_events", pd.DataFrame())
                if not events.empty:
                    pilot_events.append(events)

    summary = pd.DataFrame(summary_rows).sort_values(
        ["requested_start_month", "version"]
    ).reset_index(drop=True)
    curve_frame = pd.concat(curves, ignore_index=True, sort=False).sort_values(
        ["requested_start_month", "version", "date"]
    ).reset_index(drop=True)
    reconciliation = pd.concat(
        reconciliation_rows, ignore_index=True, sort=False
    ).sort_values("requested_start_month").reset_index(drop=True)
    pilot = pd.concat(pilot_rows, ignore_index=True, sort=False).sort_values(
        "requested_start_month"
    ).reset_index(drop=True)
    event_frame = (
        pd.concat(pilot_events, ignore_index=True, sort=False)
        if pilot_events
        else pd.DataFrame()
    )
    ai_usage = pd.DataFrame(ai_usage_rows).sort_values(
        ["requested_start_month", "version"]
    ).reset_index(drop=True)
    ai_calendar = old_halfyear._ai_calendar(a_eligibility)
    ai_parity = _ai_parity(eligibility, paths)
    pair = _pair_summary(summary, pilot)
    stats = _stats(pair)
    decision = _decision(
        pair, stats, reconciliation, pilot, ai_usage, ai_calendar, ai_parity
    )

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    pair.to_csv(PAIR_PATH, index=False, encoding="utf-8-sig")
    stats.to_csv(STATS_PATH, index=False, encoding="utf-8-sig")
    curve_frame.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    reconciliation.to_csv(RECONCILIATION_PATH, index=False, encoding="utf-8-sig")
    pilot.to_csv(PILOT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    if not event_frame.empty:
        event_frame.to_csv(PILOT_EVENTS_PATH, index=False, encoding="utf-8-sig")
    ai_usage.to_csv(AI_USAGE_PATH, index=False, encoding="utf-8-sig")
    ai_calendar.to_csv(AI_CALENDAR_PATH, index=False, encoding="utf-8-sig")
    ai_parity.to_csv(AI_PARITY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(
        json.dumps(
            s6.stage001.source.s006.base._json_safe(decision),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    LINEAGE_PATH.write_text(
        json.dumps(_lineage(metadata), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _plot_nav_grid(curve_frame, pair)
    _plot_summary(pair)
    _write_report(summary, pair, stats, reconciliation, pilot, decision)
    _manifest().to_csv(MANIFEST_PATH, index=False, encoding="utf-8-sig")
    return {
        "summary": summary,
        "pair": pair,
        "stats": stats,
        "reconciliation": reconciliation,
        "pilot": pilot,
        "decision": decision,
    }


if __name__ == "__main__":
    result = build()
    print(result["stats"].to_string(index=False))
    print(result["pair"].to_string(index=False))
    print(
        json.dumps(
            s6.stage001.source.s006.base._json_safe(result["decision"]),
            ensure_ascii=False,
            indent=2,
        )
    )
