#!/usr/bin/env python3
"""Stage008: true-engine slippage sensitivity for reconciled Stage013."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage005_stage013_current_ai_cost_execution_stress as old_cost  # noqa: E402
import stage006_stage013_reconciled_equity_engine as s6  # noqa: E402


LINE_ID = s6.LINE_ID
STAGE_ID = "stage008_reconciled_equity_slippage_stress"
STAGE_LABEL = "Stage008"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"stage013_current_ai_{STAGE_ID}"

A_VERSION = s6.A_VERSION
C_VERSION = s6.C_VERSION
VERSIONS = (A_VERSION, C_VERSION)
COST_MULTIPLIERS = (1.0, 2.0, 3.0)
RUN_ORDER = (
    (1.0, A_VERSION),
    (1.0, C_VERSION),
    (2.0, C_VERSION),
    (2.0, A_VERSION),
    (3.0, A_VERSION),
    (3.0, C_VERSION),
)

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / STAGE_ID
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
STRESS_PATH = OUT / f"{OUTPUT_PREFIX}_stress_{MODEL_TAG}.csv"
PAIR_PATH = OUT / f"{OUTPUT_PREFIX}_paired_gates_{MODEL_TAG}.csv"
RECONCILIATION_PATH = OUT / f"{OUTPUT_PREFIX}_reconciliation_{MODEL_TAG}.csv"
PILOT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_pilot_audit_{MODEL_TAG}.csv"
COST_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_cost_metadata_audit_{MODEL_TAG}.csv"
REPRODUCTION_PATH = OUT / f"{OUTPUT_PREFIX}_stage006_reproduction_{MODEL_TAG}.csv"
PNL_DECOMPOSITION_PATH = OUT / f"{OUTPUT_PREFIX}_pnl_decomposition_{MODEL_TAG}.csv"
AI_PARITY_PATH = OUT / f"{OUTPUT_PREFIX}_ai_parity_{MODEL_TAG}.csv"
AI_USAGE_PATH = OUT / f"{OUTPUT_PREFIX}_ai_usage_{MODEL_TAG}.csv"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
LINEAGE_PATH = OUT / f"{OUTPUT_PREFIX}_lineage_{MODEL_TAG}.json"
MANIFEST_PATH = OUT / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.csv"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_equity_drawdown_by_slippage_{MODEL_TAG}.png"

SAVE_FRAME_NAMES = (
    "entry_candidates",
    "trades",
    "trade_events",
    "pilot_gate_events",
    "stage006_equity_daily",
    "stage006_trade_corrections",
    "stop_retry_events",
)

_scaled_metadata = old_cost._scaled_metadata
_paired_gate_row = old_cost._paired_gate_row


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _token(multiplier: float) -> str:
    return f"{multiplier:g}x".replace(".", "p")


def _all_cost_reconciliations_pass(frame: pd.DataFrame) -> bool:
    if len(frame) != len(COST_MULTIPLIERS):
        return False
    if set(pd.to_numeric(frame["slippage_multiplier"]).astype(float)) != set(
        COST_MULTIPLIERS
    ):
        return False
    zero_columns = (
        "missing_date_count",
        "duplicate_date_count",
        "pre_start_invalid_count",
        "in_range_extra_audit_count",
        "post_end_audit_count",
        "future_trade_violation_count",
    )
    return bool(
        frame["reconciliation_pass"].astype(bool).all()
        and all(
            pd.to_numeric(frame[column], errors="coerce").fillna(1).eq(0).all()
            for column in zero_columns
        )
    )


def _eligibility(
    strategy: str, score_type: str, version: str
) -> tuple[pd.DataFrame, Path]:
    frame = s6.stage001.source.s006._official_eligibility_for_strategy(
        strategy, score_type
    )
    path = OUT / f"{OUTPUT_PREFIX}_{version}_eligibility_{MODEL_TAG}.csv"
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return frame, path


def _run_arm(
    metadata: dict[str, Any],
    profile: dict[str, Any],
    version: str,
    multiplier: float,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    daily, frames = s6._run(metadata, profile, version)
    daily = daily.copy()
    daily["stage"] = STAGE_LABEL
    daily["model_tag"] = MODEL_TAG
    daily["line_id"] = LINE_ID
    daily["slippage_multiplier"] = float(multiplier)
    for name, frame in list(frames.items()):
        data = frame.copy()
        if not data.empty:
            data["stage"] = STAGE_LABEL
            data["model_tag"] = MODEL_TAG
            data["line_id"] = LINE_ID
            data["slippage_multiplier"] = float(multiplier)
        frames[name] = data
    return daily, frames


def _summary_row(
    metadata: dict[str, Any],
    multiplier: float,
    version: str,
    daily: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    row, curve, closed = s6._summary_row(version, daily, frames, metadata)
    row.update(
        {
            "stage": STAGE_LABEL,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "slippage_multiplier": float(multiplier),
        }
    )
    curve["stage"] = STAGE_LABEL
    curve["model_tag"] = MODEL_TAG
    curve["line_id"] = LINE_ID
    curve["slippage_multiplier"] = float(multiplier)
    return row, curve, closed


def _save_arm(
    multiplier: float,
    version: str,
    daily: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    closed: pd.DataFrame,
) -> None:
    prefix = f"{OUTPUT_PREFIX}_{_token(multiplier)}_{version}"
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


def _metric(summary: pd.DataFrame, multiplier: float, version: str) -> dict[str, Any]:
    return summary[
        summary["slippage_multiplier"].eq(multiplier)
        & summary["version"].eq(version)
    ].iloc[0].to_dict()


def _window_map(stress: pd.DataFrame, multiplier: float, version: str) -> dict[str, float]:
    data = stress[
        stress["slippage_multiplier"].eq(multiplier)
        & stress["version"].eq(version)
    ]
    return {
        str(row["window"]): float(row["window_max_drawdown_pct"])
        for _, row in data.iterrows()
    }


def _paired_gates(summary: pd.DataFrame, stress: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            _paired_gate_row(
                multiplier,
                _metric(summary, multiplier, A_VERSION),
                _metric(summary, multiplier, C_VERSION),
                _window_map(stress, multiplier, A_VERSION),
                _window_map(stress, multiplier, C_VERSION),
            )
            for multiplier in COST_MULTIPLIERS
        ]
    )


def _reproduction(summary: pd.DataFrame) -> pd.DataFrame:
    reference_summary = pd.read_csv(s6.SUMMARY_PATH, encoding="utf-8-sig")
    rows = []
    for version in VERSIONS:
        reference_path = (
            s6.OUT / f"{s6.OUTPUT_PREFIX}_{version}_daily_{s6.MODEL_TAG}.csv.gz"
        )
        fresh_path = (
            OUT
            / f"{OUTPUT_PREFIX}_{_token(1.0)}_{version}_daily_{MODEL_TAG}.csv.gz"
        )
        comparison = old_cost._compare_persisted_daily(
            reference_path, fresh_path
        )
        reference = reference_summary[
            reference_summary["version"].eq(version)
        ].iloc[0]
        current = summary[
            summary["version"].eq(version)
            & summary["slippage_multiplier"].eq(1.0)
        ].iloc[0]
        summary_diff = max(
            abs(float(reference[column]) - float(current[column]))
            for column in old_cost.CORE_SUMMARY_COLUMNS
        )
        rows.append(
            {
                "version": version,
                "reference_daily_path": str(reference_path),
                "fresh_daily_path": str(fresh_path),
                **comparison,
                "summary_max_abs_difference": summary_diff,
                "reproduction_pass": bool(
                    comparison["missing_date_count"] == 0
                    and comparison["daily_mismatch_cell_count"] == 0
                    and comparison["core_daily_hash_equal"]
                    and summary_diff <= old_cost.CORE_TOLERANCE
                ),
            }
        )
    return pd.DataFrame(rows)


def _pnl_decomposition(
    daily_by_key: dict[tuple[float, str], pd.DataFrame]
) -> pd.DataFrame:
    rows = []
    for multiplier in COST_MULTIPLIERS:
        values = {}
        for version in VERSIONS:
            daily = daily_by_key[(multiplier, version)]
            values[version] = {
                "gross_pnl": float(pd.to_numeric(daily["total_pnl"]).sum()),
                "commission": float(pd.to_numeric(daily["commission"]).sum()),
                "slippage": float(pd.to_numeric(daily["slippage"]).sum()),
                "net_pnl": float(pd.to_numeric(daily["net_pnl"]).sum()),
            }
        a = values[A_VERSION]
        c = values[C_VERSION]
        rows.append(
            {
                "slippage_multiplier": multiplier,
                "a_net_pnl": a["net_pnl"],
                "c_net_pnl": c["net_pnl"],
                "c_minus_a_net_pnl": c["net_pnl"] - a["net_pnl"],
                "c_minus_a_gross_pnl": c["gross_pnl"] - a["gross_pnl"],
                "c_slippage_saved": a["slippage"] - c["slippage"],
                "c_commission_saved": a["commission"] - c["commission"],
            }
        )
    return pd.DataFrame(rows)


def _pilot_semantics_pass(pilot: pd.DataFrame) -> bool:
    if len(pilot) != len(COST_MULTIPLIERS):
        return False
    violations = (
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
    return bool(
        pd.to_numeric(pilot["rows"], errors="coerce").fillna(0).gt(0).all()
        and all(
            pd.to_numeric(pilot[column], errors="coerce").fillna(1).eq(0).all()
            for column in violations
        )
    )


def _plot(curves: pd.DataFrame) -> None:
    labels = {A_VERSION: "A current C9", C_VERSION: "C reconciled Stage013"}
    colors = {A_VERSION: "#111827", C_VERSION: "#0f766e"}
    fig, axes = plt.subplots(2, 3, figsize=(18, 9), sharex="col")
    for column, multiplier in enumerate(COST_MULTIPLIERS):
        subset = curves[curves["slippage_multiplier"].eq(multiplier)]
        for version in VERSIONS:
            group = subset[subset["version"].eq(version)].sort_values("date")
            dates = pd.to_datetime(group["date"], errors="coerce")
            equity = pd.to_numeric(
                group["account_equity_for_metrics"], errors="coerce"
            ).ffill()
            axes[0, column].plot(
                dates, equity, color=colors[version], label=labels[version], linewidth=1.0
            )
            axes[1, column].plot(
                dates,
                s6.stage001.source.s006.base._drawdown_pct(equity),
                color=colors[version],
                label=labels[version],
                linewidth=0.9,
            )
        axes[0, column].axhline(
            s6.stage001.CAPITAL, color="#64748b", linestyle="--", linewidth=0.7
        )
        axes[0, column].set_title(f"{multiplier:g}x slippage: equity")
        axes[1, column].set_title(f"{multiplier:g}x slippage: drawdown")
        axes[0, column].grid(alpha=0.22)
        axes[1, column].grid(alpha=0.22)
        axes[0, column].legend(fontsize=8)
        axes[1, column].legend(fontsize=8)
    axes[0, 0].set_ylabel("account equity")
    axes[1, 0].set_ylabel("drawdown %")
    fig.suptitle("Stage008 reconciled Stage013 slippage sensitivity")
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170, bbox_inches="tight")
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    stress: pd.DataFrame,
    pairs: pd.DataFrame,
    reconciliation: pd.DataFrame,
    pilot: pd.DataFrame,
    reproduction: pd.DataFrame,
    pnl: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    REPORT_PATH.write_text(
        f"""# Stage008 权威权益 Stage013 单位滑点敏感性

- 生成时间：`{decision['generated_at']}`
- 决策：`{decision['decision']}`
- 1x Stage006 复现：`{decision['stage006_reproduction_ok']}`
- 账本/事件/AI语义：`{decision['semantics_ok']}`
- 三档绩效门：`{decision['performance_ok']}`
- 边界：只验证单位滑点现金扣费，不是完整执行仿真，不解决 2022-01 收益保留目标缺口。
- 独立 review：待完成。

## 同成本 A/C

{pairs.to_markdown(index=False)}

## 全周期

{summary.to_markdown(index=False)}

## 压力窗口

{stress.to_markdown(index=False)}

## 权益对账

{reconciliation.to_markdown(index=False)}

## Pilot

{pilot.to_markdown(index=False)}

## 1x复现

{reproduction.to_markdown(index=False)}

## PnL归因

{pnl.to_markdown(index=False)}
""",
        encoding="utf-8",
    )


def _lineage(metadata: dict[str, Any]) -> dict[str, Any]:
    paths = {
        "stage008_tool": Path(__file__).resolve(),
        "stage008_test": TOOLS_DIR / "test_stage008_reconciled_equity_slippage_stress.py",
        "stage006_tool": Path(s6.__file__).resolve(),
        "stage005_cost_tool": Path(old_cost.__file__).resolve(),
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
    base_metadata = s6.stage001.source._metadata()
    base_hash_before = old_cost._mapping_sha256(base_metadata["slippages"])
    a_eligibility, a_path = _eligibility(s6.A_STRATEGY, A_VERSION, A_VERSION)
    c_eligibility, c_path = _eligibility(s6.C_STRATEGY, C_VERSION, C_VERSION)
    eligibility = {A_VERSION: a_eligibility, C_VERSION: c_eligibility}

    metadata_by_multiplier = {}
    profiles = {}
    cost_rows = []
    for multiplier in COST_MULTIPLIERS:
        metadata, audit = _scaled_metadata(base_metadata, multiplier)
        metadata_by_multiplier[multiplier] = metadata
        profiles[(multiplier, A_VERSION)] = s6.stage001._a_profile(
            metadata, a_path
        )
        profiles[(multiplier, C_VERSION)] = s6._candidate_profile(
            metadata, c_path
        )
        cost_rows.append(audit)

    daily_by_key = {}
    frames_by_key = {}
    summary_rows = []
    curves = []
    for index, (multiplier, version) in enumerate(RUN_ORDER, start=1):
        print(
            f"[stage008] run {index}/{len(RUN_ORDER)} slippage={multiplier:g}x version={version}",
            flush=True,
        )
        metadata = metadata_by_multiplier[multiplier]
        daily, frames = _run_arm(
            metadata, profiles[(multiplier, version)], version, multiplier
        )
        row, curve, closed = _summary_row(
            metadata, multiplier, version, daily, frames
        )
        _save_arm(multiplier, version, daily, frames, closed)
        daily_by_key[(multiplier, version)] = daily
        frames_by_key[(multiplier, version)] = frames
        summary_rows.append(row)
        curves.append(curve)

    summary = pd.DataFrame(summary_rows).sort_values(
        ["slippage_multiplier", "version"]
    ).reset_index(drop=True)
    curve_frame = pd.concat(curves, ignore_index=True, sort=False)
    stress_parts = []
    reconciliation_parts = []
    pilot_parts = []
    ai_usage_parts = []
    for multiplier in COST_MULTIPLIERS:
        daily_pair = {
            version: daily_by_key[(multiplier, version)] for version in VERSIONS
        }
        stress = s6.stage001._stress(daily_pair)
        stress["slippage_multiplier"] = multiplier
        stress_parts.append(stress)
        reconciliation = s6._equity_reconciliation(
            daily_by_key[(multiplier, C_VERSION)],
            frames_by_key[(multiplier, C_VERSION)],
        )
        reconciliation["slippage_multiplier"] = multiplier
        reconciliation_parts.append(reconciliation)
        pilot = s6._pilot_audit(
            daily_by_key[(multiplier, C_VERSION)],
            frames_by_key[(multiplier, C_VERSION)],
        )
        pilot = pilot[pilot["sample"].astype(str).eq("all")].copy()
        pilot["slippage_multiplier"] = multiplier
        pilot_parts.append(pilot)
        usage = s6.stage001.source.s006._ai_usage_audit(
            {version: frames_by_key[(multiplier, version)] for version in VERSIONS}
        )
        usage["slippage_multiplier"] = multiplier
        ai_usage_parts.append(usage)

    stress = pd.concat(stress_parts, ignore_index=True, sort=False)
    reconciliation = pd.concat(
        reconciliation_parts, ignore_index=True, sort=False
    )
    pilot = pd.concat(pilot_parts, ignore_index=True, sort=False)
    ai_usage = pd.concat(ai_usage_parts, ignore_index=True, sort=False)
    pairs = _paired_gates(summary, stress)
    reproduction = _reproduction(summary)
    pnl = _pnl_decomposition(daily_by_key)
    ai_parity = s6.stage001._ai_parity(eligibility)
    base_hash_after = old_cost._mapping_sha256(base_metadata["slippages"])
    for row in cost_rows:
        row["base_metadata_hash_before"] = base_hash_before
        row["base_metadata_hash_after"] = base_hash_after
        row["base_metadata_unmodified"] = base_hash_before == base_hash_after
    cost_audit = pd.DataFrame(cost_rows)

    reproduction_ok = bool(reproduction["reproduction_pass"].all())
    cost_ok = bool(
        cost_audit["ratio_error_count"].eq(0).all()
        and cost_audit["missing_symbol_count"].eq(0).all()
        and cost_audit["base_metadata_unmodified"].astype(bool).all()
    )
    reconciliation_ok = _all_cost_reconciliations_pass(reconciliation)
    pilot_ok = _pilot_semantics_pass(pilot)
    ai_ok = bool(ai_parity["all_normalized_equal"].all())
    performance_ok = bool(pairs["performance_gate_pass"].all())
    semantics_ok = bool(
        reproduction_ok and cost_ok and reconciliation_ok and pilot_ok and ai_ok
    )
    decision = {
        "stage": STAGE_LABEL,
        "stage_id": STAGE_ID,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "stage006_reproduction_ok": reproduction_ok,
        "cost_metadata_ok": cost_ok,
        "all_cost_reconciliations_ok": reconciliation_ok,
        "pilot_semantics_ok": pilot_ok,
        "ai_parity_ok": ai_ok,
        "semantics_ok": semantics_ok,
        "performance_ok": performance_ok,
        "paired_gates": pairs.to_dict("records"),
        "final_2022_start_retention_goal_complete": False,
        "final_goal_residual": "2022-01 independent-start retention remains 57.7149% from Stage007",
        "decision": (
            "stage008_slippage_sensitivity_pass_final_2022_goal_open"
            if semantics_ok and performance_ok
            else "stage008_fail_close_no_parameter_rescue"
        ),
        "overfit_before": "no: fixed monotonic slippage stress",
        "overfit_after": "pending_independent_review",
        "continue_value_before": "yes: verify cost sensitivity after ledger repair",
        "continue_value_after": "pending_independent_review",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    stress.to_csv(STRESS_PATH, index=False, encoding="utf-8-sig")
    pairs.to_csv(PAIR_PATH, index=False, encoding="utf-8-sig")
    reconciliation.to_csv(RECONCILIATION_PATH, index=False, encoding="utf-8-sig")
    pilot.to_csv(PILOT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    cost_audit.to_csv(COST_AUDIT_PATH, index=False, encoding="utf-8-sig")
    reproduction.to_csv(REPRODUCTION_PATH, index=False, encoding="utf-8-sig")
    pnl.to_csv(PNL_DECOMPOSITION_PATH, index=False, encoding="utf-8-sig")
    ai_parity.to_csv(AI_PARITY_PATH, index=False, encoding="utf-8-sig")
    ai_usage.to_csv(AI_USAGE_PATH, index=False, encoding="utf-8-sig")
    curve_frame.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
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
        json.dumps(_lineage(base_metadata), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _plot(curve_frame)
    _write_report(
        summary, stress, pairs, reconciliation, pilot, reproduction, pnl, decision
    )
    _manifest().to_csv(MANIFEST_PATH, index=False, encoding="utf-8-sig")
    return {
        "summary": summary,
        "pairs": pairs,
        "reconciliation": reconciliation,
        "pilot": pilot,
        "pnl": pnl,
        "decision": decision,
    }


if __name__ == "__main__":
    result = build()
    print(result["summary"].to_string(index=False))
    print(result["pairs"].to_string(index=False))
    print(result["reconciliation"].to_string(index=False))
    print(
        json.dumps(
            s6.stage001.source.s006.base._json_safe(result["decision"]),
            ensure_ascii=False,
            indent=2,
        )
    )
