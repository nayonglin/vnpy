from __future__ import annotations

from datetime import datetime
from io import StringIO
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any
from uuid import uuid4

import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import stage001_rollover_shape_same_volume_ac as s1


LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage002"

BASE_PROFILE = "stage002_A_official_live_c9_15w"
EXACT_PROFILE = "stage002_B_rollover_exact_or_skip"
SHRINK_PROFILE = "stage002_C_rollover_shrink_to_allowed"

SUMMARY_PATH = OUTPUT_DIR / "stage002_abc_summary.csv"
COMPARISON_PATH = OUTPUT_DIR / "stage002_abc_comparison.csv"
CURVE_PATH = OUTPUT_DIR / "stage002_abc_curve.csv"
ROLLOVER_PATH = OUTPUT_DIR / "stage002_rollover_shape_diagnostics.csv"
TRADES_PATH = OUTPUT_DIR / "stage002_trades.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / "stage002_trade_events.csv"
DECISION_PATH = OUTPUT_DIR / "stage002_decision.json"

ARMS: tuple[dict[str, Any], ...] = (
    {
        "profile": BASE_PROFILE,
        "candidate": False,
        "volume_policy": "exact_or_skip",
        "label": "A: 正式 C9/15万原样基线",
    },
    {
        "profile": EXACT_PROFILE,
        "candidate": True,
        "volume_policy": "exact_or_skip",
        "label": "B: 换月形态确认 + 原手数或不开仓",
    },
    {
        "profile": SHRINK_PROFILE,
        "candidate": True,
        "volume_policy": "shrink_to_allowed",
        "label": "C: 换月形态确认 + 缩减至硬风控允许手数",
    },
)


def _numeric_series(frame: pd.DataFrame, column: str) -> pd.Series:
    source = frame[column] if column in frame.columns else pd.Series(0, index=frame.index)
    return pd.to_numeric(source, errors="coerce").fillna(0)


def _candidate_contract_pass(
    diagnostics: pd.DataFrame,
    *,
    expected_policy: str,
    rollover_close_count: int,
) -> bool:
    if diagnostics.empty or len(diagnostics) != rollover_close_count:
        return False

    previous = _numeric_series(diagnostics, "previous_volume").astype(int)
    selected = _numeric_series(diagnostics, "selected_volume_before_exact_gate").astype(int)
    final = _numeric_series(diagnostics, "final_volume").astype(int)
    fill = _numeric_series(diagnostics, "fill_volume").astype(int)
    selected = selected.clip(lower=0)
    expected = (
        previous.where(selected >= previous, 0)
        if expected_policy == "exact_or_skip"
        else pd.concat([previous, selected], axis=1).min(axis=1).astype(int)
        if expected_policy == "shrink_to_allowed"
        else pd.Series(-1, index=diagnostics.index, dtype="int64")
    )
    expected_status = pd.Series("skipped", index=diagnostics.index, dtype="object")
    expected_status.loc[expected > 0] = "targeted"
    expected_outcome = pd.Series("skipped", index=diagnostics.index, dtype="object")
    expected_outcome.loc[(expected > 0) & (expected < previous)] = "reduced"
    expected_outcome.loc[(expected > 0) & (expected == previous)] = "full"
    expected_reduced = ((expected > 0) & (expected < previous)).astype(int)

    status = diagnostics.get("status", pd.Series("", index=diagnostics.index)).astype(str)
    policy = diagnostics.get("volume_policy", pd.Series("", index=diagnostics.index)).astype(str)
    outcome = diagnostics.get("volume_outcome", pd.Series("", index=diagnostics.index)).astype(str)
    reduced = _numeric_series(diagnostics, "was_reduced").astype(int)
    fill_status = diagnostics.get(
        "fill_status",
        pd.Series("", index=diagnostics.index),
    ).fillna("").astype(str)
    targeted = expected > 0
    return bool(
        (previous > 0).all()
        and policy.eq(expected_policy).all()
        and final.eq(expected).all()
        and status.eq(expected_status).all()
        and outcome.eq(expected_outcome).all()
        and reduced.eq(expected_reduced).all()
        and fill_status.loc[targeted].eq("filled").all()
        and fill.loc[targeted].eq(final.loc[targeted]).all()
        and fill_status.loc[~targeted].eq("").all()
        and fill.loc[~targeted].eq(0).all()
    )


def _event_summary(
    profile_name: str,
    frames: dict[str, pd.DataFrame],
    *,
    expected_policy: str | None,
) -> tuple[dict[str, Any], pd.DataFrame]:
    diagnostics = frames.get("rollover_shape_same_volume", pd.DataFrame()).copy()
    trades = frames.get("trades", pd.DataFrame()).copy()
    diagnostics = s1._reconcile_targeted_trades(diagnostics, trades)
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    rollover_close_count = 0
    if not trade_events.empty and "reason" in trade_events.columns:
        rollover_close_count = int(trade_events["reason"].astype(str).eq("rollover_close").sum())

    status = diagnostics.get("status", pd.Series(dtype="object")).astype(str)
    targeted = diagnostics[status.eq("targeted")].copy()
    skipped = diagnostics[status.eq("skipped")].copy()
    opened = targeted[
        targeted.get("fill_status", pd.Series(dtype="object")).astype(str).eq("filled")
    ].copy()
    short_history = (
        diagnostics[
            pd.to_numeric(diagnostics.get("target_am_inited", 1), errors="coerce")
            .fillna(1)
            .eq(0)
        ].copy()
        if not diagnostics.empty
        else pd.DataFrame()
    )

    targeted_previous = _numeric_series(targeted, "previous_volume")
    targeted_final = _numeric_series(targeted, "final_volume")
    opened_fill = _numeric_series(opened, "fill_volume")
    opened_final = _numeric_series(opened, "final_volume")
    full_count = int(targeted_final.eq(targeted_previous).sum())
    reduced_count = int(((targeted_final > 0) & (targeted_final < targeted_previous)).sum())

    volume_contract_pass = bool(
        expected_policy
        and _candidate_contract_pass(
            diagnostics,
            expected_policy=expected_policy,
            rollover_close_count=rollover_close_count,
        )
    )
    exact_volume_pass = bool(volume_contract_pass and full_count == len(targeted))
    return {
        "profile": profile_name,
        "rollover_close_count": rollover_close_count,
        "candidate_diagnostic_count": int(len(diagnostics)),
        "short_history_candidate_count": int(len(short_history)),
        "targeted_count": int(len(targeted)),
        "opened_count": int(len(opened)),
        "unfilled_target_count": int(len(targeted) - len(opened)),
        "full_volume_count": full_count,
        "reduced_volume_count": reduced_count,
        "skipped_count": int(len(skipped)),
        "volume_contract_pass": int(volume_contract_pass),
        "exact_volume_pass": int(exact_volume_pass),
    }, diagnostics


def _curve_identity_pass(curve: pd.DataFrame) -> bool:
    stage001_path = LINE_DIR / "artifacts" / "stage001" / "stage001_ac_curve.csv"
    if not stage001_path.exists():
        return False
    serialized = StringIO()
    curve.to_csv(serialized, index=False)
    serialized.seek(0)
    curve = pd.read_csv(serialized)
    stage001 = pd.read_csv(stage001_path)
    pairs = (
        (stage001, "stage001_A_official_live_c9_15w", curve, BASE_PROFILE),
        (
            stage001,
            "stage001_C_official_live_c9_15w_rollover_shape_same_volume",
            curve,
            EXACT_PROFILE,
        ),
    )
    excluded = {"profile", "arm", "variant", "label"}
    for left_frame, left_profile, right_frame, right_profile in pairs:
        left = left_frame[left_frame["profile"].eq(left_profile)].reset_index(drop=True)
        right = right_frame[right_frame["profile"].eq(right_profile)].reset_index(drop=True)
        common = [column for column in left.columns if column in right.columns and column not in excluded]
        if len(left) != len(right) or not common:
            return False
        for column in common:
            if not left[column].astype(str).equals(right[column].astype(str)):
                return False
    return True


def _publish_outputs_atomically(
    output_dir: Path,
    frames: dict[str, pd.DataFrame],
    decision: dict[str, Any],
) -> None:
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary_dir = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.tmp-", dir=output_dir.parent)
    )
    backup_dir = output_dir.with_name(f".{output_dir.name}.backup-{uuid4().hex}")
    try:
        for filename, frame in frames.items():
            frame.to_csv(temporary_dir / filename, index=False, encoding="utf-8-sig")
        (temporary_dir / DECISION_PATH.name).write_text(
            json.dumps(decision, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        if output_dir.exists():
            os.replace(output_dir, backup_dir)
        try:
            os.replace(temporary_dir, output_dir)
        except Exception:
            if backup_dir.exists() and not output_dir.exists():
                os.replace(backup_dir, output_dir)
            raise
        if backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)
    finally:
        if temporary_dir.exists():
            shutil.rmtree(temporary_dir, ignore_errors=True)


def _comparison(summary: pd.DataFrame, event_summary: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
    ]
    pairs = (
        ("A_vs_B", BASE_PROFILE, EXACT_PROFILE),
        ("A_vs_C", BASE_PROFILE, SHRINK_PROFILE),
        ("B_vs_C", EXACT_PROFILE, SHRINK_PROFILE),
    )
    rows: list[dict[str, Any]] = []
    for comparison_name, left_name, right_name in pairs:
        left = summary[summary["arm"].eq(left_name)].iloc[0]
        right = summary[summary["arm"].eq(right_name)].iloc[0]
        row: dict[str, Any] = {
            "comparison": comparison_name,
            "left": left_name,
            "right": right_name,
        }
        for metric in metrics:
            left_value = float(left[metric])
            right_value = float(right[metric])
            row[f"left_{metric}"] = left_value
            row[f"right_{metric}"] = right_value
            row[f"delta_{metric}"] = right_value - left_value
        right_events = event_summary[event_summary["profile"].eq(right_name)].iloc[0]
        for key in [
            "rollover_close_count",
            "candidate_diagnostic_count",
            "short_history_candidate_count",
            "targeted_count",
            "opened_count",
            "unfilled_target_count",
            "full_volume_count",
            "reduced_volume_count",
            "skipped_count",
            "volume_contract_pass",
            "exact_volume_pass",
        ]:
            row[key] = int(right_events[key])
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    metadata = s513._metadata()
    summaries: list[pd.DataFrame] = []
    curves: list[pd.DataFrame] = []
    event_rows: list[dict[str, Any]] = []
    diagnostics: list[pd.DataFrame] = []
    actual_trades: list[pd.DataFrame] = []
    trade_events: list[pd.DataFrame] = []

    for arm in ARMS:
        profile_name = str(arm["profile"])
        summary, curve, frames = s1._run_arm(
            profile_name=profile_name,
            candidate=bool(arm["candidate"]),
            metadata=metadata,
            volume_policy=str(arm["volume_policy"]),
            label=str(arm["label"]),
        )
        summaries.append(summary)
        curves.append(curve)
        event_row, reconciled_diagnostics = _event_summary(
            profile_name,
            frames,
            expected_policy=(str(arm["volume_policy"]) if bool(arm["candidate"]) else None),
        )
        event_rows.append(event_row)
        for source, target in [
            (reconciled_diagnostics, diagnostics),
            (frames.get("trades", pd.DataFrame()), actual_trades),
            (frames.get("trade_events", pd.DataFrame()), trade_events),
        ]:
            if source.empty:
                continue
            item = source.copy()
            item["profile"] = profile_name
            target.append(item)

    summary = pd.concat(summaries, ignore_index=True, sort=False)
    curve = pd.concat(curves, ignore_index=True, sort=False)
    event_summary = pd.DataFrame(event_rows)
    comparison = _comparison(summary, event_summary)
    diagnostic_frame = pd.concat(diagnostics, ignore_index=True, sort=False)
    trades_frame = pd.concat(actual_trades, ignore_index=True, sort=False)
    trade_event_frame = pd.concat(trade_events, ignore_index=True, sort=False)

    exact_events = event_summary[event_summary["profile"].eq(EXACT_PROFILE)].iloc[0]
    shrink_events = event_summary[event_summary["profile"].eq(SHRINK_PROFILE)].iloc[0]
    if int(exact_events["exact_volume_pass"]) != 1:
        raise RuntimeError("stage002_exact_arm_contract_failed")
    if int(shrink_events["volume_contract_pass"]) != 1:
        raise RuntimeError("stage002_shrink_arm_contract_failed")
    if int(shrink_events["reduced_volume_count"]) <= 0:
        raise RuntimeError("stage002_no_reduced_rollover_sample")
    identity_pass = _curve_identity_pass(curve)
    if not identity_pass:
        raise RuntimeError("stage002_stage001_curve_identity_failed")

    decision = {
        "line_id": "futures_trend_rollover_shape_same_volume",
        "stage": "Stage002",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "period": {"start": str(s1.START.date()), "end": str(s1.END.date())},
        "arms": {"A": BASE_PROFILE, "B": EXACT_PROFILE, "C": SHRINK_PROFILE},
        "candidate_rule": {
            "history": "new contract only, point-in-time, minimum MA40 observations",
            "shape": "directional MA5/10/20/40 alignment and MACD histogram sign",
            "volume": "min(previous live volume, hard-risk allowed volume); skip only at zero",
        },
        "event_summary": event_rows,
        "stage001_curve_identity_pass": int(identity_pass),
        "comparison": comparison.to_dict(orient="records"),
    }
    _publish_outputs_atomically(
        OUTPUT_DIR,
        {
            SUMMARY_PATH.name: summary,
            COMPARISON_PATH.name: comparison,
            CURVE_PATH.name: curve,
            ROLLOVER_PATH.name: diagnostic_frame,
            TRADES_PATH.name: trades_frame,
            TRADE_EVENTS_PATH.name: trade_event_frame,
        },
        decision,
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
