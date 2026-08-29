from __future__ import annotations

from dataclasses import asdict
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
    try:
        return importlib.import_module("stage063_stage037_top9_top10_multicycle")
    except ModuleNotFoundError as exc:
        pytest.fail(f"Stage063 runner is not implemented: {exc}")


def test_stage063_freezes_three_arms_and_fixed_multicycle_shape() -> None:
    runner = _runner()

    assert [arm["arm"] for arm in runner.ARMS] == ["A", "B", "C"]
    assert [arm["top_n"] for arm in runner.ARMS] == [8, 9, 10]
    assert [arm["color"] for arm in runner.ARMS] == ["#111827", "#dc2626", "#2563eb"]
    assert runner.START_MONTHS == (1, 6)
    assert runner.DURATIONS_YEARS == (1, 2, 3)
    assert len(runner.WINDOWS) == 43
    rolling = pd.DataFrame(runner.WINDOWS[1:])
    assert rolling.groupby("duration_years").size().to_dict() == {1: 16, 2: 14, 3: 12}
    assert set(runner.CHART_FILES) == {"full_period", "1y", "2y", "3y", "aggregate"}
    assert len(set(runner.CHART_FILES.values())) == 5


def test_stage063_offline_override_never_hides_formal_or_remote_drift() -> None:
    runner = _runner()
    formal = {
        "strategy_version": "official_live_stage847_c9_15w_stage819_05r_stop_retry_once",
        "ruleset_version": runner.BASE_RULESET_VERSION,
        "material_release_id": runner.BASE_RELEASE_ID,
        "source_commit": runner.BASE_SOURCE_COMMIT,
    }
    production_q = {
        **formal,
        "ruleset_version": "stage021_q_rollover_volume_atr_v1",
        "material_release_id": "m0015_20260825T205121+0800_c097d7836dd4",
        "source_commit": "c097d7836dd4133a88e61effa230b473c24355b3",
    }

    evidence = runner._assert_offline_identity_contract(
        checkout_identity=formal,
        production_identity=production_q,
        remote_master=runner.BASE_MASTER_COMMIT,
    )

    assert evidence["checkout_stage037_identity_pass"] is True
    assert evidence["production_identity_matches_stage037"] is False
    assert evidence["user_authorized_offline_identity_override"] is True
    assert evidence["formal_production_ac_compliant"] is False
    assert evidence["promotion_permitted"] is False

    with pytest.raises(RuntimeError, match="stage063_formal_identity_mismatch"):
        runner._assert_offline_identity_contract(
            checkout_identity={**formal, "ruleset_version": "wrong"},
            production_identity=production_q,
            remote_master=runner.BASE_MASTER_COMMIT,
        )
    with pytest.raises(RuntimeError, match="stage063_formal_identity_mismatch"):
        runner._assert_offline_identity_contract(
            checkout_identity=formal,
            production_identity=production_q,
            remote_master="wrong",
        )


def test_stage063_candidates_change_only_ai_membership(tmp_path: Path) -> None:
    runner = _runner()
    top9 = runner._candidate_overrides("B", tmp_path / "top9.csv")
    top10 = runner._candidate_overrides("C", tmp_path / "top10.csv")
    formal = runner.s56.candidate_cfg.live_cfg.build_official_live_strategy_overrides()

    for candidate in (top9, top10):
        changed = {key for key in candidate if candidate.get(key) != formal.get(key)}
        assert changed == {"ai_product_pool_eligibility_path", "ai_product_pool_strategy"}
        assert candidate["enable_ai_product_pool_filter"] is True
    assert top9["ai_product_pool_strategy"] == "ai_top9_plus_fu_boundary_check"
    assert top10["ai_product_pool_strategy"] == "ai_top10_plus_fu_width_sweep"


def test_stage063_reuses_and_verifies_three_full_period_arms() -> None:
    runner = _runner()

    summary, curve = runner._load_full_period()
    runner._verify_full_identity(summary, curve)

    assert set(summary["promotion_arm"].astype(str)) == {"A", "B", "C"}
    assert summary.groupby("promotion_arm").size().to_dict() == {"A": 1, "B": 1, "C": 1}
    assert curve.groupby("promotion_arm").size().to_dict() == {
        "A": 2101,
        "B": 2101,
        "C": 2101,
    }


def test_stage063_reuses_only_verified_formal_rolling_windows() -> None:
    runner = _runner()

    summary, curve = runner._load_reused_formal_rolling()

    assert len(summary) == 42
    assert summary["promotion_arm"].astype(str).eq("A").all()
    assert set(summary["window_id"].astype(str)) == {
        str(window["window_id"]) for window in runner.WINDOWS[1:]
    }
    assert set(curve["promotion_arm"].astype(str)) == {"A"}

