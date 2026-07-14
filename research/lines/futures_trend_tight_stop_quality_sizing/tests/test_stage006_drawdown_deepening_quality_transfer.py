from __future__ import annotations

from pathlib import Path
import sys

import numpy as np


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stage003_lower_half_stop_moderate_body_risk_transfer as s003  # noqa: E402
import stage006_drawdown_deepening_quality_transfer as s006  # noqa: E402


def test_drawdown_deepening_gate_has_no_numeric_threshold() -> None:
    assert s006.drawdown_deepening_gate(enabled=True, entry_context="flat_entry", prior=0.10, current=0.1000001)[0]
    assert not s006.drawdown_deepening_gate(enabled=True, entry_context="flat_entry", prior=0.10, current=0.10)[0]
    assert not s006.drawdown_deepening_gate(enabled=True, entry_context="flat_entry", prior=0.10, current=0.09)[0]


def test_drawdown_deepening_gate_is_flat_entry_only() -> None:
    active, reason = s006.drawdown_deepening_gate(enabled=True, entry_context="reverse_entry", prior=0.0, current=0.2)
    assert not active
    assert reason == "non_flat_entry"


def test_drawdown_deepening_gate_disabled_fail_unchanged() -> None:
    active, reason = s006.drawdown_deepening_gate(enabled=False, entry_context="flat_entry", prior=0.0, current=0.2)
    assert not active
    assert reason == "disabled"


def test_stage006_fields_are_not_ai_derived() -> None:
    assert not any(s003.is_ai_derived_field(field) for field in s006.STAGE006_AUDIT_FIELDS)


def test_delta_tolerance_is_only_floating_point_guard() -> None:
    assert not s006.drawdown_deepening_gate(enabled=True, entry_context="flat_entry", prior=0.1, current=0.1 + 5e-13)[0]
    assert s006.drawdown_deepening_gate(enabled=True, entry_context="flat_entry", prior=0.1, current=0.1 + 2e-12)[0]
    assert np.isclose((0.1 + 2e-12) - 0.1, 2e-12, rtol=0.0, atol=1e-16)
