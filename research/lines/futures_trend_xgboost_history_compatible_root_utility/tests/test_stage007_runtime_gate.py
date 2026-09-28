import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "tools/stage007_runtime_gate.py"


def module():
    assert PATH.exists(), "runtime gate implementation missing"
    spec = importlib.util.spec_from_file_location("runtime_gate_test", PATH)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class ToyStrategy:
    def __init__(self):
        self.entry_candidate_snapshots = []
        self.opened = []
        self.margin = 0
        self.last_signal = "before"

    def _record_entry_candidate_snapshot(self, *, product, candidate_status):
        self.entry_candidate_snapshots.append({"product": product, "candidate_status": candidate_status,
                                               "margin_before": self.margin})

    def on_bars(self, bars):
        for product, candidate_status in bars:
            self._record_entry_candidate_snapshot(product=product, candidate_status=candidate_status)
            if candidate_status != "opened":
                continue
            self.opened.append(product)
            self.margin += 10
            self.last_signal = product


class ChildStrategy(ToyStrategy):
    pass


def test_noop_is_exact_and_method_and_globals_are_restored():
    m = module()
    bars = [("a", "opened"), ("b", "skipped"), ("c", "opened")]
    expected = ToyStrategy()
    expected.on_bars(bars)
    original = ChildStrategy.on_bars
    namespace_keys = set(original.__globals__)
    observed = ChildStrategy()
    with m.install_gate(ChildStrategy, lambda self: False) as audit:
        observed.on_bars(bars)
        assert audit["gate_call_count"] == 2
    assert observed.__dict__ == expected.__dict__
    assert ChildStrategy.on_bars is original and "on_bars" not in ChildStrategy.__dict__
    assert set(original.__globals__) == namespace_keys


def test_gate_observes_current_snapshot_and_skips_all_opening_side_effects():
    m = module()
    observed = ChildStrategy()
    calls = []
    def decide(self):
        row = self.entry_candidate_snapshots[-1]
        calls.append((row["product"], row["margin_before"]))
        if row["product"] == "b":
            row["candidate_status"] = "skipped"
            return True
        return False
    with m.install_gate(ChildStrategy, decide) as audit:
        observed.on_bars([("a", "opened"), ("b", "opened"), ("c", "opened")])
        assert audit["gate_call_count"] == 3 and audit["skip_count"] == 1
    assert calls == [("a", 0), ("b", 10), ("c", 10)]
    assert observed.opened == ["a", "c"] and observed.margin == 20 and observed.last_signal == "c"


def test_skipped_last_candidate_does_not_overwrite_last_signal():
    observed = ChildStrategy()
    with module().install_gate(ChildStrategy, lambda self: True):
        observed.on_bars([("b", "opened")])
    assert observed.last_signal == "before" and observed.margin == 0 and observed.opened == []


def test_original_local_method_restored_on_callback_failure():
    m = module()
    original = ToyStrategy.on_bars
    def fail(self):
        raise RuntimeError("synthetic_failure")
    with pytest.raises(RuntimeError, match="synthetic_failure"):
        with m.install_gate(ToyStrategy, fail):
            ToyStrategy().on_bars([("a", "opened")])
    assert ToyStrategy.on_bars is original


def test_source_without_single_known_gate_is_rejected():
    source = "def on_bars(self, bars):\n    return None\n"
    with pytest.raises(RuntimeError, match="runtime_gate_shape_changed"):
        module().instrument_source(source)


def test_canonical_source_has_exactly_one_eligible_insertion_site():
    source = (ROOT.parents[2] / "examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py").read_text()
    tree = module().instrument_source(source, method_only=False)
    assert tree is not None


def test_nested_installation_is_rejected_without_breaking_outer_gate():
    m = module()
    with m.install_gate(ChildStrategy, lambda self: False):
        with pytest.raises(RuntimeError, match="runtime_gate_already_installed"):
            with m.install_gate(ChildStrategy, lambda self: False):
                pass
        observed = ChildStrategy()
        observed.on_bars([("a", "opened")])
        assert observed.opened == ["a"]


def test_decider_records_current_features_and_marks_only_vetoed_snapshot():
    from types import SimpleNamespace
    row = {"product_vt_symbol": "rb.SHFE", "entry_context": "flat_entry", "candidate_status": "opened",
           "is_opened": 1, "skip_reason": "", "estimated_equity": 75000, "total_margin_in_use_before": 15000}
    strategy = SimpleNamespace(entry_candidate_snapshots=[row])
    def features(current):
        assert current is not row and current == row
        return {"event_id": "current-not-baseline", "margin_to_equity_before": current["total_margin_in_use_before"] / current["estimated_equity"]}
    def predict(event):
        assert event["margin_to_equity_before"] == 0.2
        return {"status": "predicted", "skip": True, "return_marginal": -0.01, "drawdown_marginal": -0.02}
    decide, records = module().make_decider(features, predict)
    assert decide(strategy) is True
    assert row["candidate_status"] == "skipped" and row["is_opened"] == 0
    assert row["skip_reason"] == "research_xgb_predicted_harm"
    assert records[0]["event_id"] == "current-not-baseline" and records[0]["skip"] is True


def test_fixed_fu_never_builds_model_features():
    from types import SimpleNamespace
    row = {"product_vt_symbol": "fu.SHFE"}
    def forbidden(_):
        raise AssertionError("FU must not reach model")
    decide, records = module().make_decider(forbidden, forbidden)
    assert decide(SimpleNamespace(entry_candidate_snapshots=[row])) is False
    assert records == [] and row == {"product_vt_symbol": "fu.SHFE"}


def test_inconsistent_prediction_cannot_veto_order():
    from types import SimpleNamespace
    row = {"product_vt_symbol": "rb.SHFE", "entry_context": "flat_entry", "candidate_status": "opened", "is_opened": 1}
    decide, _ = module().make_decider(lambda row: {}, lambda event: {"status": "predicted", "skip": True,
                                        "return_marginal": 0.01, "drawdown_marginal": -0.02})
    with pytest.raises(RuntimeError, match="runtime_prediction_action_mismatch"):
        decide(SimpleNamespace(entry_candidate_snapshots=[row]))
    assert row["candidate_status"] == "opened"
