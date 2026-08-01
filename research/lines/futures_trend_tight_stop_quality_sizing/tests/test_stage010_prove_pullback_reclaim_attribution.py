from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stage010_prove_pullback_reclaim_attribution as s010


def _event(direction: str = "long") -> dict[str, object]:
    return {
        "open_trade_id": "T1",
        "vt_symbol": "rb2205.SHFE",
        "product": "rb.SHFE",
        "direction": direction,
        "entry_date": pd.Timestamp("2022-01-04"),
        "planned_entry_price": 100.0,
        "actual_entry_price": 100.0,
        "planned_stop_distance": 10.0,
        "actual_stop_distance": 10.0,
        "baseline_realized_pnl": 1_000.0,
        "baseline_r_multiple": 1.5,
        "sample_segment": "discovery",
    }


def _session(
    direction: str = "long",
    *,
    proof_index: int = 5,
    retest_index: int | None = 31,
    retest_extreme: float | None = None,
    next_open: float | None = None,
    same_bar_proof_and_stop: bool = False,
    same_bar_outcome: bool = False,
) -> pd.DataFrame:
    count = 80
    times = pd.date_range("2022-01-03 21:00:00", periods=count, freq="min")
    if direction == "long":
        opens = np.full(count, 101.0)
        highs = np.full(count, 102.0)
        lows = np.full(count, 100.5)
        closes = np.full(count, 101.0)
        opens[0] = 100.0
        lows[0] = 99.5
        highs[proof_index] = 106.0
        lows[proof_index] = 100.5
        if same_bar_proof_and_stop:
            lows[proof_index] = 94.0
        if retest_index is not None:
            lows[retest_index] = 99.0 if retest_extreme is None else retest_extreme
            highs[retest_index] = 103.0
            opens[retest_index] = 102.0
            closes[retest_index] = 101.0
            opens[retest_index + 1] = 102.0 if next_open is None else next_open
            highs[retest_index + 1] = 107.0
            lows[retest_index + 1] = 101.0
            closes[retest_index + 1] = 106.0
            if next_open is not None:
                lows[retest_index + 1] = min(lows[retest_index + 1], next_open - 0.5)
            highs[retest_index + 2] = 111.0
            closes[retest_index + 2] = 110.0
            if same_bar_outcome:
                lows[retest_index + 1] = 97.0
                highs[retest_index + 1] = 111.0
    else:
        opens = np.full(count, 99.0)
        highs = np.full(count, 99.5)
        lows = np.full(count, 98.0)
        closes = np.full(count, 99.0)
        opens[0] = 100.0
        highs[0] = 100.5
        lows[proof_index] = 94.0
        highs[proof_index] = 99.5
        if same_bar_proof_and_stop:
            highs[proof_index] = 106.0
        if retest_index is not None:
            highs[retest_index] = 101.0 if retest_extreme is None else retest_extreme
            lows[retest_index] = 97.0
            opens[retest_index] = 98.0
            closes[retest_index] = 99.0
            opens[retest_index + 1] = 98.0 if next_open is None else next_open
            highs[retest_index + 1] = 99.0
            lows[retest_index + 1] = 93.0
            closes[retest_index + 1] = 94.0
            if next_open is not None:
                highs[retest_index + 1] = max(highs[retest_index + 1], next_open + 0.5)
            lows[retest_index + 2] = 89.0
            closes[retest_index + 2] = 90.0
            if same_bar_outcome:
                highs[retest_index + 1] = 103.0
                lows[retest_index + 1] = 89.0
    return pd.DataFrame(
        {
            "vt_symbol": "rb2205.SHFE",
            "bar_date": pd.Timestamp("2022-01-04"),
            "bar_datetime": times,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": 100.0,
        }
    )


@pytest.mark.parametrize("direction", ["long", "short"])
def test_candidate_state_machine_is_direction_symmetric_and_uses_next_open(direction: str) -> None:
    result = s010.compute_pullback_reclaim_event(
        _event(direction),
        _session(direction),
        pricetick=1.0,
        pricetick_rule="current_metadata",
        compute_outcomes=True,
    )

    assert result["candidate_status"] == "candidate"
    assert result["proof_bar_index"] == 5
    assert result["retest_bar_index"] == 31
    assert result["reclaim_bar_index"] == 31
    assert result["counterfactual_entry_bar_index"] == 32
    assert pd.Timestamp(result["reclaim_time"]) < pd.Timestamp(result["counterfactual_entry_time"])
    assert result["counterfactual_entry_price"] == pytest.approx(102.0 if direction == "long" else 98.0)
    assert result["structural_stop_price"] == pytest.approx(98.0 if direction == "long" else 102.0)
    assert result["micro_stop_distance"] == pytest.approx(4.0)
    assert result["micro_stop_actual_risk_ratio"] == pytest.approx(0.4)
    assert result["completed_minutes_before_decision"] == 32
    assert result["micro_first_touch_1r"] == "target_first"
    assert result["micro_first_touch_2r"] == "target_first"


@pytest.mark.parametrize("direction", ["long", "short"])
def test_same_bar_proof_and_half_r_stop_fails_stop_first(direction: str) -> None:
    result = s010.compute_pullback_reclaim_event(
        _event(direction),
        _session(direction, same_bar_proof_and_stop=True),
        pricetick=1.0,
        pricetick_rule="current_metadata",
        compute_outcomes=True,
    )

    assert result["candidate_status"] == "prior_half_r_stop"
    assert np.isnan(result["proof_bar_index"])


def test_proof_bar_cannot_also_supply_the_retest() -> None:
    session = _session("long", retest_index=None)
    session.loc[5, ["high", "low", "open", "close"]] = [106.0, 99.0, 101.0, 101.0]

    result = s010.compute_pullback_reclaim_event(
        _event("long"),
        session,
        pricetick=1.0,
        pricetick_rule="current_metadata",
        compute_outcomes=True,
    )

    assert result["proof_bar_index"] == 5
    assert result["candidate_status"] == "no_retest"


def test_reclaim_before_thirty_completed_minutes_is_rejected_without_delay() -> None:
    result = s010.compute_pullback_reclaim_event(
        _event("long"),
        _session("long", retest_index=20),
        pricetick=1.0,
        pricetick_rule="current_metadata",
        compute_outcomes=True,
    )

    assert result["candidate_status"] == "early_reclaim"
    assert result["completed_minutes_before_decision"] == 21
    assert np.isnan(result["counterfactual_entry_price"])


def test_next_open_must_hold_reclaim_and_micro_stop_must_be_at_most_half_r() -> None:
    lost = s010.compute_pullback_reclaim_event(
        _event("long"),
        _session("long", next_open=99.5),
        pricetick=1.0,
        pricetick_rule="current_metadata",
        compute_outcomes=True,
    )
    wide = s010.compute_pullback_reclaim_event(
        _event("long"),
        _session("long", retest_extreme=95.5),
        pricetick=1.0,
        pricetick_rule="current_metadata",
        compute_outcomes=True,
    )

    assert lost["candidate_status"] == "next_open_lost_reclaim"
    assert wide["candidate_status"] == "micro_stop_too_wide"
    assert wide["micro_stop_actual_risk_ratio"] > 0.5


@pytest.mark.parametrize("direction", ["long", "short"])
def test_candidate_same_bar_stop_and_targets_are_conservatively_stop_first(direction: str) -> None:
    result = s010.compute_pullback_reclaim_event(
        _event(direction),
        _session(direction, same_bar_outcome=True),
        pricetick=1.0,
        pricetick_rule="current_metadata",
        compute_outcomes=True,
    )

    assert result["candidate_status"] == "candidate"
    assert result["micro_first_touch_1r"] == "stop_first"
    assert result["micro_first_touch_2r"] == "stop_first"


def test_future_feature_seal_does_not_depend_on_outcomes() -> None:
    discovery = s010.compute_pullback_reclaim_event(
        _event("long"),
        _session("long"),
        pricetick=1.0,
        pricetick_rule="current_metadata",
        compute_outcomes=True,
    )
    validation_event = _event("short")
    validation_event["open_trade_id"] = "V1"
    validation_event["sample_segment"] = "validation"
    validation = s010.compute_pullback_reclaim_event(
        validation_event,
        _session("short"),
        pricetick=1.0,
        pricetick_rule="current_metadata",
        compute_outcomes=False,
    )
    frame = pd.DataFrame([discovery, validation])
    _, seal = s010.partition_outputs(frame)
    mutated = frame.copy()
    mutated.loc[mutated["sample_segment"].eq("validation"), "micro_first_touch_2r"] = "target_first"
    mutated.loc[mutated["sample_segment"].eq("validation"), "baseline_realized_pnl"] = 1e12
    _, mutated_seal = s010.partition_outputs(mutated)

    assert seal["feature_only_sha256"] == mutated_seal["feature_only_sha256"]
    assert seal["future_outcomes_computed"] is False
    assert seal["true_oos_claim"] is False


def _gate_candidates() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    products = [f"p{index}.EX" for index in range(8)]
    for year in (2020, 2021, 2022):
        for index in range(16):
            rows.append(
                {
                    "open_trade_id": f"{year}-{index}",
                    "product": products[index % len(products)],
                    "direction": "long" if index % 2 == 0 else "short",
                    "entry_date": pd.Timestamp(f"{year}-06-01"),
                    "micro_first_touch_1r": "target_first" if index < 12 else "stop_first",
                    "micro_first_touch_2r": "target_first" if index < 11 else "stop_first",
                    "baseline_realized_pnl": 100.0,
                    "baseline_r_multiple": 1.0,
                    "return_5m_micro_r": 0.1,
                    "return_15m_micro_r": 0.2,
                    "return_60m_micro_r": 0.3,
                }
            )
    return pd.DataFrame(rows)


def test_discovery_gate_is_fixed_and_fails_if_one_year_is_below_two_r_breakeven() -> None:
    candidates = _gate_candidates()
    passed = s010.evaluate_discovery_gate(candidates)
    failed_candidates = candidates.copy()
    year_mask = pd.to_datetime(failed_candidates["entry_date"]).dt.year.eq(2022)
    failed_candidates.loc[year_mask, "micro_first_touch_2r"] = "stop_first"
    failed = s010.evaluate_discovery_gate(failed_candidates)

    assert passed["coverage_gate_pass"] is True
    assert passed["first_touch_gate_pass"] is True
    assert passed["baseline_right_tail_gate_pass"] is True
    assert passed["stage011_real_engine_predecl_allowed"] is True
    assert failed["coverage_gate_pass"] is True
    assert failed["first_touch_gate_pass"] is False
    assert failed["stage011_real_engine_predecl_allowed"] is False
