from __future__ import annotations

import importlib
import json
import math
from pathlib import Path
import sys
import warnings

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


def _renderer():
    try:
        return importlib.import_module("stage063_render_charts")
    except ModuleNotFoundError as exc:
        pytest.fail(f"Stage063 renderer is not implemented: {exc}")


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


def test_stage063_reuse_sources_are_locked_to_frozen_git_blobs(monkeypatch) -> None:
    runner = _runner()

    contract = runner._assert_reuse_sources_frozen()

    assert contract["commit"] == runner.REUSE_SOURCE_COMMIT
    assert set(contract["files"]) == {
        str(path.relative_to(runner.PROJECT_DIR)) for path in runner.REUSE_SOURCE_PATHS
    }
    assert all(
        values["workspace_sha256"] == values["git_blob_sha256"]
        for values in contract["files"].values()
    )

    target = runner.REUSE_SOURCE_PATHS[0]
    original_file_sha256 = runner._file_sha256
    monkeypatch.setattr(
        runner,
        "_file_sha256",
        lambda path: "0" * 64 if Path(path) == target else original_file_sha256(path),
    )
    with pytest.raises(RuntimeError, match="stage063_reuse_source_git_drift"):
        runner._assert_reuse_sources_frozen()


def test_stage063_renderer_uses_ascii_labels_without_changing_arm_colors() -> None:
    runner = _runner()
    renderer = _renderer()

    assert [arm["color"] for arm in renderer.RENDER_ARMS] == [
        arm["color"] for arm in runner.ARMS
    ]
    assert [arm["plot_label"] for arm in renderer.RENDER_ARMS] == [
        "Formal Stage037 Top8+fu",
        "Top9+fu",
        "Top10+fu",
    ]
    assert all(
        label.isascii() for label in (arm["plot_label"] for arm in renderer.RENDER_ARMS)
    )


def test_stage063_renderer_loads_published_curves_without_dtype_warning() -> None:
    renderer = _renderer()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        curve, comparison, aggregate = renderer._load_frames()

    assert not caught
    assert not curve.empty
    assert not comparison.empty
    assert not aggregate.empty


def test_stage063_renderer_records_immutable_chart_provenance() -> None:
    runner = _runner()
    renderer = _renderer()

    decision = json.loads(
        (runner.OUTPUT_DIR / runner.DECISION_NAME).read_text(encoding="utf-8")
    )
    provenance = decision["render_provenance"]

    assert provenance["renderer_sha256"] == runner._file_sha256(Path(renderer.__file__))
    assert set(provenance["chart_sha256"]) == set(runner.CHART_FILES.values())
    assert all(
        digest == runner._file_sha256(runner.OUTPUT_DIR / name)
        for name, digest in provenance["chart_sha256"].items()
    )
    assert decision["publication_reuse_contract"] == runner._assert_reuse_sources_frozen()
    contracts = decision["runtime_contracts"]
    assert contracts["engine_checkpoint"]["sha256"] == decision["identity"][
        "runtime_contract_sha256"
    ]
    assert contracts["engine_checkpoint"]["generated_before_reuse_hardening"] is True
    assert contracts["current_runner"]["sha256"] == runner._runtime_contract_hash(
        {
            "B": runner.INPUT_DIR / "stage063_top9_eligibility.csv",
            "C": runner.INPUT_DIR / "stage063_top10_eligibility.csv",
        }
    )
    assert contracts["current_runner"]["sha256"] != contracts["engine_checkpoint"][
        "sha256"
    ]
    publication_payload = {
        "reuse_source_contract": decision["publication_reuse_contract"],
        "renderer_sha256": provenance["renderer_sha256"],
        "chart_sha256": provenance["chart_sha256"],
    }
    assert contracts["publication"]["sha256"] == runner._json_sha256(
        publication_payload
    )
    assert contracts["publication"]["covers_published_reuse_and_charts"] is True


def test_stage063_published_artifacts_recompute_all_129_arm_windows() -> None:
    runner = _runner()
    output = runner.OUTPUT_DIR
    summary = pd.read_csv(output / runner.SUMMARY_NAME, low_memory=False)
    curve = pd.read_csv(output / runner.CURVE_NAME, low_memory=False)
    comparison = pd.read_csv(output / runner.COMPARISON_NAME)
    aggregate = pd.read_csv(output / runner.AGGREGATE_NAME)
    decision = json.loads((output / runner.DECISION_NAME).read_text(encoding="utf-8"))

    assert len(summary) == 129
    assert summary.groupby(["window_id", "promotion_arm"]).size().eq(1).all()
    assert set(zip(curve["window_id"], curve["promotion_arm"], strict=False)) == set(
        zip(summary["window_id"], summary["promotion_arm"], strict=False)
    )
    for row in summary.itertuples(index=False):
        arm_curve = curve[
            curve["window_id"].astype(str).eq(str(row.window_id))
            & curve["promotion_arm"].astype(str).eq(str(row.promotion_arm))
        ].sort_values("date")
        dates = pd.to_datetime(arm_curve["date"], errors="raise")
        equity = pd.to_numeric(arm_curve["account_equity"], errors="raise")
        daily_returns = equity.ffill().pct_change().fillna(0.0)
        nonzero_pnl = pd.to_numeric(arm_curve["net_pnl"], errors="raise")
        nonzero_pnl = nonzero_pnl[nonzero_pnl.abs().gt(1e-12)]

        assert dates.is_unique
        assert dates.is_monotonic_increasing
        assert float(row.account_capital) == pytest.approx(150_000.0)
        assert float(row.end_equity) == pytest.approx(float(equity.iloc[-1]))
        assert float(row.total_return_pct) == pytest.approx(
            (float(equity.iloc[-1]) / 150_000.0 - 1.0) * 100.0
        )
        assert float(row.max_dd_pct) == pytest.approx(
            float((equity / equity.cummax() - 1.0).min() * 100.0)
        )
        assert float(row.sharpe) == pytest.approx(
            float(daily_returns.mean() / daily_returns.std(ddof=1) * math.sqrt(252.0))
        )
        assert float(row.total_slippage) == pytest.approx(
            float(pd.to_numeric(arm_curve["total_slippage"], errors="raise").sum())
        )
        assert int(row.total_trade_count) == int(
            pd.to_numeric(arm_curve["trade_count"], errors="raise").sum()
        )
        assert float(row.nonzero_daily_win_rate_pct) == pytest.approx(
            float(nonzero_pnl.gt(0.0).mean() * 100.0)
        )

    runner._configure_shared_contract()
    recomputed_aggregate = runner.s29._aggregate(comparison)
    pd.testing.assert_frame_equal(
        aggregate.reset_index(drop=True),
        recomputed_aggregate.reset_index(drop=True),
        check_dtype=False,
    )
    assert decision["candidate_all_multicycle_gates_pass"] == {"B": False, "C": False}
    assert decision["run_provenance"]["checkpoint_generated_count"] == 84
    assert decision["order_api_called_count"] == 0
    assert decision["send_order_api_called_count"] == 0
    assert decision["cancel_order_api_called_count"] == 0
    assert decision["ctp_connected"] is False
