from __future__ import annotations

from pathlib import Path
import re
import unittest


STRATEGY_PATH = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "portfolio_backtesting"
    / "qmt_roll_portfolio_strategy.py"
)
STAGE830_PATH = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "portfolio_backtesting"
    / "analyze_qmt_roll_stage830_stage827_c2_broker10_margin_cap.py"
)
STAGE847_PATH = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "portfolio_backtesting"
    / "analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine.py"
)
STAGE901_PATH = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "portfolio_backtesting"
    / "analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py"
)


def _method_block(source: str, name: str) -> str:
    pattern = re.compile(rf"^    def {re.escape(name)}\(.*?(?=^    def |\Z)", re.M | re.S)
    match = pattern.search(source)
    if not match:
        raise AssertionError(f"method not found: {name}")
    return match.group(0)


def _function_block(source: str, name: str) -> str:
    pattern = re.compile(rf"^def {re.escape(name)}\(.*?(?=^def |^class |\Z)", re.M | re.S)
    match = pattern.search(source)
    if not match:
        raise AssertionError(f"function not found: {name}")
    return match.group(0)


class QmtEntryContextDiagnosticsTest(unittest.TestCase):
    def test_entry_sizing_snapshot_preserves_original_context_for_all_branches(self) -> None:
        source = STRATEGY_PATH.read_text(encoding="utf-8")
        block = _method_block(source, "_calculate_entry_sizing")

        self.assertGreaterEqual(
            block.count('"entry_context": entry_context'),
            2,
            "fixed_size and risk_budget sizing branches must both preserve the original entry_context",
        )

    def test_entry_risk_diagnostic_exports_original_entry_context(self) -> None:
        source = STRATEGY_PATH.read_text(encoding="utf-8")
        block = _method_block(source, "_record_entry_risk_diagnostic")

        self.assertIn('"entry_context"', block)
        self.assertIn('sizing_snapshot.get("entry_context")', block)

    def test_stage830_broker10_cap_fail_closes_reverse_entry(self) -> None:
        source = STAGE830_PATH.read_text(encoding="utf-8")
        block = _method_block(source, "_calculate_entry_sizing")

        self.assertIn('entry_context == "reverse_entry"', block)
        self.assertIn('"stage830_broker10_margin_cap_reason"] = "reverse_entry_fail_closed"', block)
        self.assertIn('sizing["stage830_broker10_margin_cap_applied"] = 1', block)
        self.assertIn('sizing["stage830_margin_cap_selected_volume_after"] = 0', block)
        self.assertIn('sizing["selected_volume"] = 0', block)

    def test_stage847_synthetic_trade_datetime_uses_event_time(self) -> None:
        source = STAGE847_PATH.read_text(encoding="utf-8")
        block = _method_block(source, "_fill_synthetic_intraday_close")
        helper_block = _function_block(source, "_stage847_synthetic_trade_datetime")

        self.assertIn("trade_datetime = _stage847_synthetic_trade_datetime", block)
        self.assertIn("datetime=trade_datetime", block)
        self.assertIn("_naive_date(trade_datetime)", block)
        self.assertNotIn("datetime=self.datetime", block)
        self.assertNotIn("_naive_date(self.datetime)", block)
        self.assertIn("fallback_timezone", helper_block)
        self.assertIn("tz_localize(fallback_timezone)", helper_block)

    def test_stage847_profile_pins_legacy_base_profile(self) -> None:
        source = STAGE847_PATH.read_text(encoding="utf-8")
        profile_block = _function_block(source, "_c9_profile")

        self.assertIn("_stage847_stage372_legacy_official_context", source)
        self.assertIn("LEGACY_STAGE372_PROFILE_NAME", source)
        self.assertIn("with _stage847_stage372_legacy_official_context():", profile_block)
        self.assertIn("profile = s830._cap_profile(metadata)", profile_block)

    def test_stage901_does_not_patch_stage660_globals(self) -> None:
        source = STAGE901_PATH.read_text(encoding="utf-8")
        run_block = _function_block(source, "_run_live_c9")

        self.assertNotIn("s660.OFFICIAL_LIVE_PROFILE_NAME", run_block)
        self.assertNotIn("setattr(s660", run_block)
        self.assertNotIn("LEGACY_STAGE372_STRATEGY_OVERRIDES", source)


if __name__ == "__main__":
    unittest.main()
