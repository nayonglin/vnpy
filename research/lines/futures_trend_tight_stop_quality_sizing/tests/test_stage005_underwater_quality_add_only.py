from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stage003_lower_half_stop_moderate_body_risk_transfer as s003  # noqa: E402
import stage005_underwater_quality_add_only as s005  # noqa: E402


def test_stage005_reason_is_explicit_about_unchanged_other() -> None:
    assert s005._stage005_reason({"stage004_underwater_gate_active": 0}) == "high_water_unchanged"
    assert s005._stage005_reason({"stage004_underwater_gate_active": 1, "stage003_reason": "quality_risk_increase"}) == "underwater_quality_risk_increase"
    assert s005._stage005_reason({"stage004_underwater_gate_active": 1, "stage003_reason": "other_risk_decrease"}) == "underwater_other_unchanged"


def test_candidate_profile_changes_only_frozen_quality_add_only_knobs(monkeypatch) -> None:
    class Capital:
        account_capital = s005.EXPECTED_CAPITAL

    class Spec:
        overrides = {
            "enable_stage003_risk_transfer": True,
            "stage003_quality_weight": s003.QUALITY_WEIGHT,
            "stage003_other_weight": s003.OTHER_WEIGHT,
            "enable_stage004_underwater_only": True,
        }
        capital = Capital()
        profile = "stage004"

    monkeypatch.setattr(s005.s004, "_candidate_profile", lambda metadata: {"spec": Spec(), "profile": "stage004"})
    monkeypatch.setattr(s005, "replace", lambda spec, **kwargs: type("Result", (), {**spec.__dict__, **kwargs})())
    profile = s005._candidate_profile({})
    assert profile["strategy_cls"] is s005.QmtRollPortfolioStrategyStage005UnderwaterQualityAddOnly
    assert profile["spec"].overrides["stage003_quality_weight"] == s003.QUALITY_WEIGHT
    assert profile["spec"].overrides["stage003_other_weight"] == 1.0
    assert profile["spec"].overrides["enable_stage004_underwater_only"] is True


def test_comparison_uses_frozen_70_percent_gate() -> None:
    rows = []
    for variant, result in (("A_official", (100.0, -40.0)), (s005.VARIANT, (70.0, -35.0))):
        rows.append({
            "variant": variant,
            "requested_start_month": "2022-01",
            "total_return_pct": result[0],
            "max_dd_pct": result[1],
            "sharpe": 1.0,
            "total_slippage": 10.0,
            "total_trade_count": 5.0,
        })
    comparison = s005._comparison(pd.DataFrame(rows))
    assert np.isclose(comparison.loc[0, "return_retention_ratio"], 0.70)
    assert comparison.loc[0, "retention_70_pass"] == 1
    assert comparison.loc[0, "dd_improve_3pp_pass"] == 1


def test_stage005_audit_fields_are_not_ai_derived() -> None:
    assert not any(s003.is_ai_derived_field(field) for field in s005.STAGE005_AUDIT_FIELDS)
