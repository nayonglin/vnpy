from __future__ import annotations

import csv
from pathlib import Path
import sys


PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import qmt_roll_candidate_stage037_short_mirror_block_config as candidate_cfg
import qmt_roll_official_live_config as live_cfg
import qmt_roll_official_stage021_q_ruleset_config as stage021_q_cfg
import qmt_roll_official_stage037_ruleset_config as stage037_cfg


def test_formal_stage037_ruleset_equals_frozen_research_candidate() -> None:
    formal = live_cfg.build_official_live_strategy_overrides()
    candidate = candidate_cfg.build_candidate_overrides()

    ai_identity_fields = {
        "ai_product_pool_eligibility_path",
        "ai_product_pool_strategy",
    }
    assert formal["ai_product_pool_strategy"] == "ai_top10_plus_fu_official_live_v1"
    assert formal["ai_product_pool_eligibility_path"] == str(
        live_cfg.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH
    )
    assert Path(formal["ai_product_pool_eligibility_path"]).is_file()
    assert candidate["ai_product_pool_strategy"] == (
        "ai_top8_plus_fu_satellite_post_signal_entry_filter"
    )
    candidate_eligibility = Path(candidate["ai_product_pool_eligibility_path"])
    assert "m0016_20260829T034012+0800_374df2d52e4f" in candidate_eligibility.parts
    with candidate_eligibility.open(encoding="utf-8-sig", newline="") as handle:
        assert {
            row["strategy"] for row in csv.DictReader(handle)
        } == {candidate["ai_product_pool_strategy"]}
    assert {
        key: value for key, value in formal.items() if key not in ai_identity_fields
    } == {
        key: value for key, value in candidate.items() if key not in ai_identity_fields
    }
    assert live_cfg.OFFICIAL_LIVE_RULESET_VERSION == candidate_cfg.CANDIDATE_VERSION
    assert stage037_cfg.RULESET_VERSION == candidate_cfg.CANDIDATE_VERSION
    assert stage037_cfg.PREVIOUS_RULESET_VERSION == stage021_q_cfg.RULESET_VERSION


def test_formal_stage037_delta_is_exactly_thirteen_fields_over_q() -> None:
    stage847 = live_cfg.stage847_c9_cfg.build_official_candidate_stage847_c9_overrides()
    q = stage021_q_cfg.apply_stage021_q_ruleset(stage847)
    stage037 = stage037_cfg.apply_stage037_ruleset(stage847)
    delta = {
        key: (q.get(key), stage037.get(key))
        for key in sorted(set(q) | set(stage037))
        if q.get(key) != stage037.get(key)
    }

    assert set(delta) == set(stage037_cfg.STAGE037_RELATIVE_OVERRIDES)
    assert len(delta) == 13
    assert {
        key: actual for key, (_, actual) in delta.items()
    } == stage037_cfg.STAGE037_RELATIVE_OVERRIDES
