from __future__ import annotations

import importlib
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_rollover_shape_same_volume" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def _runner():
    return importlib.import_module("stage048_stage037_vs_current_online_multicycle")


def test_stage048_freezes_two_arms_and_fixed_five_chart_contract() -> None:
    runner = _runner()

    assert [item["arm"] for item in runner.ARMS] == ["A", "C"]
    assert runner.DURATIONS_YEARS == (1, 2, 3)
    assert runner.START_MONTHS == (1, 6)
    assert set(runner.CHART_FILES) == {"full_period", "1y", "2y", "3y", "aggregate"}
    assert len(set(runner.CHART_FILES.values())) == 5


def test_stage048_builds_full_plus_42_complete_january_june_windows() -> None:
    runner = _runner()
    windows = runner._build_windows()

    assert len(windows) == 43
    assert windows[0]["window_group"] == "full_period"
    rolling = pd.DataFrame(windows[1:])
    assert rolling.groupby("duration_years").size().to_dict() == {1: 16, 2: 14, 3: 12}
    assert set(rolling["start_month_num"].astype(int)) == {1, 6}
    assert rolling["complete"].all()
    assert not rolling["terminal_near_complete"].any()


def test_stage048_cycle_gate_is_predeclared_and_strict() -> None:
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

    failing = {**passing, "return_win_rate_pct": 49.999}
    assert runner._cycle_gates(failing)["return_win_rate_ge_50pct"] is False


def test_stage048_candidate_scope_reuses_exact_stage047_thirteen_differences() -> None:
    runner = _runner()

    assert runner.s47.override_diff() == runner.s47._expected_override_diff()
    assert len(runner.s47.override_diff()) == 13
    assert runner.CANDIDATE_LOGIC_COMMIT == "827764ed33f95e9aee6cc03b2b6703805a939ace"
