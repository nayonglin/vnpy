from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stage004_underwater_only_quality_transfer as s004


def test_underwater_gate_is_binary_and_causal() -> None:
    assert s004.underwater_gate_active(enabled=True, entry_context="flat_entry", portfolio_drawdown_pct=0.0) == (
        False,
        "high_water_unchanged",
    )


def test_stage004_reads_positional_entry_context(monkeypatch) -> None:
    strategy = object.__new__(s004.QmtRollPortfolioStrategyStage004UnderwaterOnly)
    strategy.enable_stage004_underwater_only = True
    strategy.enable_stage003_risk_transfer = True
    strategy.portfolio_drawdown_pct = 10.0

    def fake_parent_sizing(self, *args, **kwargs):
        weight = 0.75 if self.enable_stage003_risk_transfer else 1.0
        return {"stage003_budget_weight": weight}

    monkeypatch.setattr(
        s004.s003.QmtRollPortfolioStrategyStage003RiskTransfer,
        "_calculate_entry_sizing",
        fake_parent_sizing,
    )
    result = strategy._calculate_entry_sizing(
        "rb.SHFE",
        "long",
        None,
        pd.DataFrame(),
        {},
        None,
        "rollover_reopen",
    )
    assert result["stage004_underwater_gate_active"] == 0
    assert result["stage004_gate_reason"] == "non_flat_entry"
    assert result["stage004_budget_weight"] == 1.0
    assert s004.underwater_gate_active(enabled=True, entry_context="flat_entry", portfolio_drawdown_pct=1e-12) == (
        True,
        "underwater_quality_transfer",
    )
    assert s004.underwater_gate_active(enabled=True, entry_context="rollover_reopen", portfolio_drawdown_pct=0.5) == (
        False,
        "non_flat_entry",
    )


def test_config_diff_is_only_frozen_stage003_plus_stage004_gate() -> None:
    metadata = s004.s003.s901.s513._metadata()
    audit = s004.config_audit(metadata)
    changed = audit[audit.changed.eq(1)]
    assert not changed.empty
    assert changed.allowed.eq(1).all()
    assert "enable_stage004_underwater_only" in set(changed.key)


def test_stage004_fields_have_no_ai_derivatives() -> None:
    assert all(not s004.s003.is_ai_derived_field(column) for column in s004.STAGE004_AUDIT_FIELDS)


def test_comparison_reuses_same_hard_gate_math() -> None:
    summary = pd.DataFrame(
        [
            {"variant": "A_official", "requested_start_month": "2022-01", "total_return_pct": 100.0, "max_dd_pct": -50.0, "sharpe": 1.0, "total_slippage": 10.0, "total_trade_count": 20.0},
            {"variant": s004.VARIANT, "requested_start_month": "2022-01", "total_return_pct": 80.0, "max_dd_pct": -45.0, "sharpe": 1.1, "total_slippage": 9.0, "total_trade_count": 18.0},
        ]
    )
    row = s004._comparison(summary).iloc[0]
    assert row.return_retention_ratio == 0.8
    assert row.dd_improvement_pp == 5.0
