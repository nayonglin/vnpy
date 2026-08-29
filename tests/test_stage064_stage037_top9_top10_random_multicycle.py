from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_rollover_shape_same_volume" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def _runner():
    try:
        return importlib.import_module("stage064_stage037_top9_top10_random_multicycle")
    except ModuleNotFoundError as exc:
        pytest.fail(f"Stage064 runner is not implemented: {exc}")


def test_stage064_draws_reproducible_random_trading_day_starts() -> None:
    runner = _runner()
    trading_dates = pd.bdate_range("2020-01-01", "2024-12-31")

    first = runner._build_random_windows(
        trading_dates=trading_dates,
        seed=123,
        samples_per_duration=2,
    )
    second = runner._build_random_windows(
        trading_dates=trading_dates,
        seed=123,
        samples_per_duration=2,
    )
    changed = runner._build_random_windows(
        trading_dates=trading_dates,
        seed=124,
        samples_per_duration=2,
    )

    pd.testing.assert_frame_equal(first, second)
    assert first["requested_start"].tolist() == [
        "2020-05-29",
        "2022-02-07",
        "2020-05-05",
        "2021-08-06",
        "2021-01-15",
        "2020-06-03",
    ]
    assert changed["requested_start"].tolist() != first["requested_start"].tolist()
    assert first.groupby("duration_years").size().to_dict() == {1: 2, 2: 2, 3: 2}
    assert first["requested_start"].isin(trading_dates.strftime("%Y-%m-%d")).all()
    assert first["window_id"].is_unique
    assert first["draw_index"].tolist() == [1, 2, 1, 2, 1, 2]


def test_stage064_frozen_design_has_192_random_windows_and_three_paired_arms() -> None:
    runner = _runner()

    assert runner.SAMPLES_PER_DURATION == 64
    assert runner.DURATIONS_YEARS == (1, 2, 3)
    assert [arm["arm"] for arm in runner.ARMS] == ["A", "B", "C"]
    assert [arm["top_n"] for arm in runner.ARMS] == [8, 9, 10]
    assert runner.EXPECTED_RANDOM_WINDOW_COUNT == 192
    assert runner.EXPECTED_ENGINE_RUN_COUNT == 576
    assert set(runner.CHART_FILES) == {"full_period", "1y", "2y", "3y", "aggregate"}
    assert len(set(runner.CHART_FILES.values())) == 5


def test_stage064_seed_and_frozen_plan_are_reproducible_and_fail_closed(
    tmp_path: Path,
) -> None:
    runner = _runner()
    dates = pd.bdate_range("2018-01-01", "2026-08-28")
    plan_path = tmp_path / "plan.csv"

    assert runner._derive_random_seed("abc", "def") == 4385965271391192385
    metadata = runner._freeze_window_plan(
        trading_dates=dates,
        database_sha256="database-sha",
        path=plan_path,
    )
    loaded = runner._load_frozen_window_plan(
        path=plan_path,
        trading_dates=dates,
        expected_seed=metadata["random_seed"],
    )

    assert metadata["window_count"] == 192
    assert metadata["plan_sha256"] == runner._file_sha256(plan_path)
    assert len(loaded) == 192
    assert loaded.groupby("duration_years").size().to_dict() == {1: 64, 2: 64, 3: 64}

    corrupted = loaded.copy()
    corrupted.loc[1, "window_id"] = corrupted.loc[0, "window_id"]
    corrupted.to_csv(plan_path, index=False)
    with pytest.raises(RuntimeError, match="stage064_window_plan_duplicate"):
        runner._load_frozen_window_plan(
            path=plan_path,
            trading_dates=dates,
            expected_seed=metadata["random_seed"],
        )


def test_stage064_reused_sources_are_locked_to_stage063_git_commit(monkeypatch) -> None:
    runner = _runner()

    contract = runner._assert_reuse_sources_frozen()

    assert contract["commit"] == runner.STAGE063_SOURCE_COMMIT
    assert set(contract["files"]) == {
        str(path.relative_to(runner.PROJECT_DIR)) for path in runner.REUSE_SOURCE_PATHS
    }
    assert all(
        values["workspace_sha256"] == values["git_blob_sha256"]
        for values in contract["files"].values()
    )

    target = runner.REUSE_SOURCE_PATHS[0]
    original = runner._file_sha256
    monkeypatch.setattr(
        runner,
        "_file_sha256",
        lambda path: "f" * 64 if Path(path) == target else original(path),
    )
    with pytest.raises(RuntimeError, match="stage064_reuse_source_git_drift"):
        runner._assert_reuse_sources_frozen()


def test_stage064_random_aggregate_uses_all_windows_and_each_horizon() -> None:
    runner = _runner()
    comparison = pd.DataFrame(
        [
            {
                "comparison": "A_vs_B",
                "duration_years": years,
                "return_win": win,
                "delta_return_pct": delta,
                "left_return_pct": 10.0,
                "right_return_pct": 10.0 + delta,
                "left_positive": 1,
                "right_positive": int(10.0 + delta > 0.0),
                "dd_noninferior_2pp": dd_ok,
                "left_dd50_fail": 0,
                "right_dd50_fail": 0,
                "sharpe_noninferior_005": sharpe_ok,
                "left_slippage": 100.0,
                "right_slippage": cost,
                "left_trades": 10,
                "right_trades": 11,
                "right_survival_pass": 1,
                "left_broker100_pass": 1,
                "right_broker100_pass": 1,
            }
            for years, win, delta, dd_ok, sharpe_ok, cost in (
                (1, 1, 4.0, 1, 1, 104.0),
                (1, 0, -2.0, 0, 1, 106.0),
                (2, 1, 8.0, 1, 0, 110.0),
                (2, 1, 2.0, 1, 1, 100.0),
                (3, 0, -6.0, 1, 1, 105.0),
                (3, 1, 10.0, 1, 1, 105.0),
            )
        ]
    )

    aggregate = runner._random_aggregate(comparison)

    assert aggregate[["duration_years", "window_count"]].values.tolist() == [
        [0, 6],
        [1, 2],
        [2, 2],
        [3, 2],
    ]
    overall = aggregate.iloc[0]
    assert overall["return_win_rate_pct"] == pytest.approx(4 / 6 * 100.0)
    assert overall["median_return_delta_pct"] == pytest.approx(3.0)
    assert overall["dd_noninferior_2pp_rate_pct"] == pytest.approx(5 / 6 * 100.0)
    assert overall["sharpe_noninferior_005_rate_pct"] == pytest.approx(5 / 6 * 100.0)
    assert overall["slippage_ratio"] == pytest.approx(630.0 / 600.0)


def test_stage064_random_gates_fail_closed_on_cost_and_path_instability() -> None:
    runner = _runner()
    row = {
        "return_win_rate_pct": 75.0,
        "median_return_delta_pct": 3.0,
        "dd_noninferior_2pp_rate_pct": 79.99,
        "left_dd50_fail_count": 1,
        "right_dd50_fail_count": 1,
        "sharpe_noninferior_005_rate_pct": 90.0,
        "slippage_ratio": 1.050001,
        "all_right_survival": 1,
        "left_broker100_fail_count": 0,
        "right_broker100_fail_count": 0,
    }

    gates = runner._random_cycle_gates(row)

    assert gates["return_win_rate_ge_50pct"] is True
    assert gates["dd_noninferior_2pp_rate_ge_80pct"] is False
    assert gates["aggregate_slippage_le_105pct"] is False
    assert all(
        gates[key]
        for key in gates
        if key not in {"dd_noninferior_2pp_rate_ge_80pct", "aggregate_slippage_le_105pct"}
    )


def test_stage064_published_artifacts_are_complete_when_present() -> None:
    runner = _runner()
    if not runner.OUTPUT_DIR.exists():
        pytest.skip("Stage064 backtest has not been published yet")

    summary = pd.read_csv(runner.OUTPUT_DIR / runner.SUMMARY_NAME, low_memory=False)
    curve = pd.read_csv(runner.OUTPUT_DIR / runner.CURVE_NAME, low_memory=False)
    aggregate = pd.read_csv(runner.OUTPUT_DIR / runner.AGGREGATE_NAME)
    decision = json.loads(
        (runner.OUTPUT_DIR / runner.DECISION_NAME).read_text(encoding="utf-8")
    )

    assert len(summary) == 576
    assert summary.groupby(["window_id", "promotion_arm"]).size().eq(1).all()
    assert summary.groupby(["duration_years", "promotion_arm"]).size().eq(64).all()
    assert len(set(zip(curve["window_id"], curve["promotion_arm"], strict=False))) == 576
    assert aggregate.groupby("comparison").size().eq(4).all()
    assert decision["run_provenance"]["random_window_count"] == 192
    assert decision["run_provenance"]["logical_arm_window_count"] == 576
    assert decision["run_provenance"]["random_windows_redrawn_after_results"] is False
    assert decision["order_api_called_count"] == 0
    assert decision["send_order_api_called_count"] == 0
    assert decision["cancel_order_api_called_count"] == 0
    assert decision["ctp_connected"] is False
