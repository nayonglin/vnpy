from __future__ import annotations

from datetime import datetime
from io import StringIO
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import stage001_rollover_shape_same_volume_ac as s1
import stage002_rollover_shape_shrink_to_allowed_abc as s2


LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage003"

BASE_PROFILE = "stage003_A_official_live_c9_15w"
TARGET_HISTORY_PROFILE = "stage003_B_target_history_40_shrink"
CONTINUOUS_PROFILE = "stage003_C_same_day_quote_metadata_continuous_shrink"

SUMMARY_PATH = OUTPUT_DIR / "stage003_abc_summary.csv"
COMPARISON_PATH = OUTPUT_DIR / "stage003_abc_comparison.csv"
CURVE_PATH = OUTPUT_DIR / "stage003_abc_curve.csv"
ROLLOVER_PATH = OUTPUT_DIR / "stage003_rollover_shape_diagnostics.csv"
TRADES_PATH = OUTPUT_DIR / "stage003_trades.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / "stage003_trade_events.csv"
DECISION_PATH = OUTPUT_DIR / "stage003_decision.json"

ARMS: tuple[dict[str, Any], ...] = (
    {
        "profile": BASE_PROFILE,
        "candidate": False,
        "volume_policy": "shrink_to_allowed",
        "history_mode": "target_contract_only",
        "label": "A: 正式 C9/15万原样基线",
    },
    {
        "profile": TARGET_HISTORY_PROFILE,
        "candidate": True,
        "volume_policy": "shrink_to_allowed",
        "history_mode": "target_contract_only",
        "label": "B: 新主力自身至少40根日K + 硬风控缩手",
    },
    {
        "profile": CONTINUOUS_PROFILE,
        "candidate": True,
        "volume_policy": "shrink_to_allowed",
        "history_mode": "backwards_ratio_continuous",
        "label": "C: 新主力仅当日可交易行情及元数据 + 连续历史形态 + 硬风控缩手",
    },
)


def _history_contract_pass(
    diagnostics: pd.DataFrame,
    *,
    expected_mode: str,
    rollover_close_count: int,
) -> tuple[bool, int]:
    if diagnostics.empty or len(diagnostics) != rollover_close_count:
        return False, 0

    mode = diagnostics.get("history_mode", pd.Series("", index=diagnostics.index)).astype(str)
    target_count = s2._numeric_series(diagnostics, "target_observed_bar_count").astype(int)
    source_count = s2._numeric_series(diagnostics, "source_observed_bar_count").astype(int)
    observed_count = s2._numeric_series(diagnostics, "observed_bar_count").astype(int)
    required_count = s2._numeric_series(diagnostics, "required_bar_count").astype(int)
    history_ready = s2._numeric_series(diagnostics, "history_input_ready").astype(int).eq(1)
    target_bar_appended = s2._numeric_series(diagnostics, "target_bar_appended").astype(int)
    reason = diagnostics.get("reason", pd.Series("", index=diagnostics.index)).astype(str)

    if expected_mode == "target_contract_only":
        return bool(
            mode.eq(expected_mode).all()
            and source_count.eq(target_count).all()
            and observed_count.eq(target_count).all()
        ), 0

    if expected_mode != "backwards_ratio_continuous":
        return False, 0

    same_day_ready = s2._numeric_series(diagnostics, "same_day_bar_ready").astype(int).eq(1)
    market_ready = s2._numeric_series(diagnostics, "market_data_ready").astype(int).eq(1)
    metadata_ready = s2._numeric_series(diagnostics, "metadata_ready").astype(int).eq(1)
    ratio = pd.to_numeric(
        diagnostics.get("roll_adjustment_ratio", pd.Series(np.nan, index=diagnostics.index)),
        errors="coerce",
    )
    bypass = (
        history_ready
        & target_count.lt(required_count)
        & source_count.ge(required_count)
    )
    ready_contract = bool(
        same_day_ready.loc[history_ready].all()
        and market_ready.loc[history_ready].all()
        and metadata_ready.loc[history_ready].all()
        and observed_count.loc[history_ready]
        .eq(source_count.loc[history_ready] + target_bar_appended.loc[history_ready])
        .all()
        and ratio.loc[history_ready].map(lambda value: bool(np.isfinite(value) and value > 0)).all()
    )
    no_target_count_gate = bool(
        not reason.loc[bypass].eq("insufficient_indicator_history").any()
    )
    return bool(
        mode.eq(expected_mode).all()
        and ready_contract
        and no_target_count_gate
        and int(bypass.sum()) > 0
    ), int(bypass.sum())


def _event_summary(
    profile_name: str,
    frames: dict[str, pd.DataFrame],
    *,
    expected_mode: str | None,
) -> tuple[dict[str, Any], pd.DataFrame]:
    row, diagnostics = s2._event_summary(
        profile_name,
        frames,
        expected_policy="shrink_to_allowed" if expected_mode else None,
    )
    history_contract_pass = False
    target_history_bypass_count = 0
    if expected_mode:
        history_contract_pass, target_history_bypass_count = _history_contract_pass(
            diagnostics,
            expected_mode=expected_mode,
            rollover_close_count=int(row["rollover_close_count"]),
        )
    row.update(
        {
            "history_mode": expected_mode or "official",
            "history_contract_pass": int(history_contract_pass),
            "target_history_bypass_count": int(target_history_bypass_count),
        }
    )
    return row, diagnostics


def _curve_identity_pass(curve: pd.DataFrame) -> bool:
    stage002_path = LINE_DIR / "artifacts" / "stage002" / "stage002_abc_curve.csv"
    if not stage002_path.exists():
        return False
    serialized = StringIO()
    curve.to_csv(serialized, index=False)
    serialized.seek(0)
    current = pd.read_csv(serialized)
    stage002 = pd.read_csv(stage002_path)
    pairs = (
        ("stage002_A_official_live_c9_15w", BASE_PROFILE),
        ("stage002_C_rollover_shrink_to_allowed", TARGET_HISTORY_PROFILE),
    )
    excluded = {"profile", "arm", "variant", "label"}
    for old_profile, new_profile in pairs:
        left = stage002[stage002["profile"].eq(old_profile)].reset_index(drop=True)
        right = current[current["profile"].eq(new_profile)].reset_index(drop=True)
        common = [column for column in left.columns if column in right.columns and column not in excluded]
        if len(left) != len(right) or not common:
            return False
        for column in common:
            if not left[column].astype(str).equals(right[column].astype(str)):
                return False
    return True


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
        ("A_vs_B", BASE_PROFILE, TARGET_HISTORY_PROFILE),
        ("A_vs_C", BASE_PROFILE, CONTINUOUS_PROFILE),
        ("B_vs_C", TARGET_HISTORY_PROFILE, CONTINUOUS_PROFILE),
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
            "full_volume_count",
            "reduced_volume_count",
            "skipped_count",
            "volume_contract_pass",
            "history_contract_pass",
            "target_history_bypass_count",
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
            history_mode=str(arm["history_mode"]),
            label=str(arm["label"]),
        )
        summaries.append(summary)
        curves.append(curve)
        event_row, reconciled_diagnostics = _event_summary(
            profile_name,
            frames,
            expected_mode=(str(arm["history_mode"]) if bool(arm["candidate"]) else None),
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

    for profile in [TARGET_HISTORY_PROFILE, CONTINUOUS_PROFILE]:
        row = event_summary[event_summary["profile"].eq(profile)].iloc[0]
        if int(row["volume_contract_pass"]) != 1:
            raise RuntimeError(f"stage003_volume_contract_failed:{profile}")
        if int(row["history_contract_pass"]) != 1:
            raise RuntimeError(f"stage003_history_contract_failed:{profile}")
    identity_pass = _curve_identity_pass(curve)
    if not identity_pass:
        raise RuntimeError("stage003_stage002_curve_identity_failed")

    decision = {
        "line_id": "futures_trend_rollover_shape_same_volume",
        "stage": "Stage003",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "period": {"start": str(s1.START.date()), "end": str(s1.END.date())},
        "arms": {
            "A": BASE_PROFILE,
            "B": TARGET_HISTORY_PROFILE,
            "C": CONTINUOUS_PROFILE,
        },
        "candidate_rule": {
            "target_contract_gate": "same-day positive-volume OHLC bar and complete size/pricetick/margin metadata only",
            "indicator_history": "point-in-time old-contract history backwards-ratio adjusted to target current close; replace the same-day old row or append the target row when the old contract stopped earlier",
            "shape": "directional MA5/10/20/40 alignment and MACD histogram sign",
            "volume": "min(previous live volume, hard-risk allowed volume); skip only at zero",
        },
        "event_summary": event_rows,
        "stage002_curve_identity_pass": int(identity_pass),
        "comparison": comparison.to_dict(orient="records"),
    }
    s2._publish_outputs_atomically(
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
        decision_filename=DECISION_PATH.name,
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
