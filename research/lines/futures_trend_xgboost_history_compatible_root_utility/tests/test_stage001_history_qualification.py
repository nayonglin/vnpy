import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


PATH = Path(__file__).resolve().parents[1] / "tools/stage001_history_qualification.py"


def module():
    assert PATH.exists(), "history qualification implementation missing"
    spec = importlib.util.spec_from_file_location("history_qualification", PATH)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


IDENTITY = {"formal_release_id": "test", "formal_strategy": "formal",
            "official_live_version": "c9", "formal_material_manifest_sha256": "a" * 64}


def candidate(**overrides):
    row = dict(candidate_index=1, datetime="2020-01-02 00:00:00+08:00", date="2020-01-02",
               product_vt_symbol="sp.SHFE", contract_vt_symbol="sp2005.SHFE", entry_context="flat_entry",
               candidate_status="opened", is_opened=1, direction="long", signal="long_case2",
               ai_product_pool_strategy="formal", ai_product_pool_signal_date="2019-12-31",
               planned_entry_price=100, oi_price_confirm_entry_oi=110, oi_price_confirm_prev_oi=100,
               estimated_equity=1000, max_concurrent_positions=4, rsi_value=75, ma_mid_value=100,
               ma_long_value=98, ma_mid_prev_value=99, ma_long_prev_value=97,
               stop_distance=2, portfolio_drawdown_pct=0.1, total_margin_in_use_before=100,
               active_positions_before=1, loss_streak=1,
               same_direction_correlation_gate_enabled=1, same_direction_correlation_active_count=1,
               same_direction_correlation_corr_count=1, same_direction_correlation_max_corr=0.3,
               same_direction_correlation_candidate_return_count=20,
               same_direction_correlation_min_required_count=10,
               same_direction_correlation_candidate_history_available=1,
               same_direction_correlation_active_count_recomputed=1,
               same_direction_correlation_corr_count_recomputed=1,
               same_direction_correlation_max_corr_recomputed=0.3,
               same_direction_correlation_trace_exact=1)
    return {**row, **overrides}


def test_static_roots_keep_shared_features_without_ai_rank():
    m = module()
    frame = m.build_features(pd.DataFrame([candidate()]), IDENTITY)
    assert len(frame) == 1
    assert len(m.FEATURES) == 10
    assert "formal_rank_percentile" not in frame
    assert frame.iloc[0].directional_rsi == 0.5
    assert frame.iloc[0].directional_ma_gap == 0.02
    assert frame.iloc[0].directional_ma_slope == 0.01
    assert frame.iloc[0].margin_to_equity_before == 0.1
    assert frame.iloc[0].active_positions_fraction == 0.25


def test_direction_and_event_identity():
    m = module()
    a = m.build_features(pd.DataFrame([candidate()]), IDENTITY).iloc[0]
    b = m.build_features(pd.DataFrame([candidate(direction="short", signal="short_case2")]), IDENTITY).iloc[0]
    assert b.directional_rsi == -a.directional_rsi
    assert a.event_id != b.event_id
    assert a.event_id == m.upstream._event_id(a, IDENTITY)


def test_fixed_fu_and_non_root_never_enter():
    m = module()
    rows = [candidate(), candidate(candidate_index=2, product_vt_symbol="fu.SHFE"),
            candidate(candidate_index=3, entry_context="rollover"), candidate(candidate_index=4, is_opened=0)]
    assert m.build_features(pd.DataFrame(rows), IDENTITY).candidate_index.tolist() == [1]


@pytest.mark.parametrize("overrides", [
    {"planned_entry_price": 0}, {"estimated_equity": np.nan}, {"direction": "unknown"},
    {"ai_product_pool_signal_date": "2020-01-02"}, {"ai_product_pool_strategy": "wrong"},
    {"same_direction_correlation_candidate_return_count": 1},
    {"same_direction_correlation_corr_count_recomputed": 0},
    {"same_direction_correlation_max_corr_recomputed": 0.4},
    {"same_direction_correlation_trace_exact": 0}, {"loss_streak": -1},
])
def test_invalid_inputs_fail_without_dropping_rows(overrides):
    with pytest.raises((RuntimeError, ValueError)):
        module().build_features(pd.DataFrame([candidate(**overrides)]), IDENTITY)


def test_no_active_correlation_zero_requires_valid_history():
    m = module()
    row = candidate(same_direction_correlation_active_count=0, same_direction_correlation_corr_count=0,
                    same_direction_correlation_active_count_recomputed=0,
                    same_direction_correlation_corr_count_recomputed=0,
                    same_direction_correlation_max_corr=0, same_direction_correlation_max_corr_recomputed=0)
    assert m.build_features(pd.DataFrame([row]), IDENTITY).iloc[0].same_direction_correlation == 0
    row["same_direction_correlation_candidate_history_available"] = 0
    with pytest.raises((RuntimeError, ValueError)):
        m.build_features(pd.DataFrame([row]), IDENTITY)


def test_duplicate_event_rejected():
    with pytest.raises((RuntimeError, ValueError)):
        module().build_features(pd.DataFrame([candidate(), candidate()]), IDENTITY)


def test_eligibility_uses_score_rank_source_field():
    m = module()
    actual = {"ai_product_pool_score": 0, "ai_product_pool_rank": 15, "ai_product_pool_top_n": 18}
    formal = {"score": 0, "score_rank": 15, "top_n": 18}
    assert hasattr(m, "verify_membership"), "eligibility verifier missing"
    m.verify_membership(actual, formal)
    with pytest.raises(RuntimeError):
        m.verify_membership(actual, {**formal, "score_rank": 14})
