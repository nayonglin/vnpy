from __future__ import annotations

import importlib
from pathlib import Path
import sys

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_rollover_shape_same_volume" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def _runner():
    return importlib.import_module("stage059_stage056_vs_stage037_multicycle")


def test_stage059_freezes_stage037_and_stage056_with_five_chart_contract() -> None:
    runner = _runner()

    assert [item["arm"] for item in runner.ARMS] == ["A", "C"]
    assert runner.ARMS[0]["profile"] == "stage059_A_master_m0016_stage037_top8_plus_fu"
    assert runner.ARMS[1]["profile"] == "stage059_C_stage056_stage037_top14_plus_fu"
    assert runner.START_MONTHS == (1, 6)
    assert runner.DURATIONS_YEARS == (1, 2, 3)
    assert set(runner.CHART_FILES) == {"full_period", "1y", "2y", "3y", "aggregate"}
    assert len(set(runner.CHART_FILES.values())) == 5


def test_stage059_builds_full_plus_42_complete_january_june_windows() -> None:
    runner = _runner()
    windows = runner._build_windows()

    assert len(windows) == 43
    assert windows[0]["window_group"] == "full_period"
    rolling = pd.DataFrame(windows[1:])
    assert rolling.groupby("duration_years").size().to_dict() == {1: 16, 2: 14, 3: 12}
    assert set(rolling["start_month_num"].astype(int)) == {1, 6}
    assert rolling["complete"].all()
    assert not rolling["terminal_near_complete"].any()


def test_stage059_offline_identity_records_but_does_not_hide_production_drift() -> None:
    runner = _runner()
    stage037 = {
        "strategy_version": "official_live_stage847_c9_15w_stage819_05r_stop_retry_once",
        "ruleset_version": runner.BASE_RULESET_VERSION,
        "material_release_id": runner.BASE_RELEASE_ID,
        "source_commit": runner.BASE_SOURCE_COMMIT,
    }
    production_q = {
        **stage037,
        "ruleset_version": "stage021_q_rollover_volume_atr_v1",
        "material_release_id": "m0015",
    }

    evidence = runner._assert_offline_identity_contract(
        checkout_identity=stage037,
        production_identity=production_q,
        remote_master=runner.BASE_MASTER_COMMIT,
    )

    assert evidence["research_protocol"] == "explicit_stage037_vs_stage056_offline"
    assert evidence["checkout_stage037_identity_pass"] is True
    assert evidence["production_identity_matches_stage037"] is False
    assert evidence["formal_production_ac_compliant"] is False
    assert evidence["promotion_permitted"] is False

    with pytest.raises(RuntimeError, match="stage059_stage037_identity_mismatch"):
        runner._assert_offline_identity_contract(
            checkout_identity={**stage037, "ruleset_version": "wrong"},
            production_identity=production_q,
            remote_master=runner.BASE_MASTER_COMMIT,
        )


def test_stage059_cycle_gate_reuses_predeclared_multicycle_thresholds() -> None:
    runner = _runner()
    passing = {
        "return_win_rate_pct": 50.0,
        "median_return_delta_pct": 0.0,
        "dd_noninferior_2pp_rate_pct": 80.0,
        "left_dd50_fail_count": 1,
        "right_dd50_fail_count": 1,
        "sharpe_noninferior_005_rate_pct": 80.0,
        "slippage_ratio": 1.05,
        "all_right_survival": 1,
        "left_broker100_fail_count": 0,
        "right_broker100_fail_count": 0,
    }

    assert all(runner._cycle_gates(passing).values())
    assert runner._cycle_gates({**passing, "slippage_ratio": 1.050001})[
        "aggregate_slippage_le_105pct"
    ] is False


def test_stage059_full_period_artifact_round_trips_exactly() -> None:
    runner = _runner()
    summary, curve = runner._load_full_period()

    runner._verify_full_identity(summary, curve)
