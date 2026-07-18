from __future__ import annotations

from pathlib import Path
import sys
import unittest


PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

from qmt_roll_official_execution_profile import (
    C9_15W_HISTORICAL_PROFILE,
    STAGE372_20W_PROFILE,
    ExecutionStrategyMode,
    assert_profile_identity,
    resolve_execution_profile,
)


class OfficialExecutionProfileTest(unittest.TestCase):
    def test_stage372_profile_is_official_daily_only_default(self) -> None:
        profile = resolve_execution_profile()

        self.assertIs(profile, STAGE372_20W_PROFILE)
        self.assertEqual(profile.profile_key, "stage372-20w")
        self.assertEqual(
            profile.official_version,
            "official_live_stage372_20w_recovery_sleeve",
        )
        self.assertEqual(profile.alias, "Stage372-20w")
        self.assertEqual(profile.source_stage, "Stage372")
        self.assertEqual(profile.capital, 200_000.0)
        self.assertEqual(profile.capital_label, "20w")
        self.assertFalse(profile.intraday_stop_retry_enabled)
        self.assertEqual(
            profile.allowed_intent_sources,
            ("stage260_stage372_daily",),
        )
        self.assertIn("stage659_stage372", profile.summary_path.name)
        self.assertIn("stage659_stage372", profile.signal_plan_path.name)
        self.assertIn("stage659_stage372", profile.current_positions_path.name)

    def test_profile_resolution_accepts_enum_and_rejects_unknown(self) -> None:
        self.assertIs(
            resolve_execution_profile(ExecutionStrategyMode.STAGE372_20W),
            STAGE372_20W_PROFILE,
        )
        self.assertIs(
            resolve_execution_profile("c9-15w-historical"),
            C9_15W_HISTORICAL_PROFILE,
        )
        with self.assertRaisesRegex(ValueError, "execution_profile_unknown"):
            resolve_execution_profile("not-a-profile")

    def test_profile_identity_mismatch_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "execution_profile_version_mismatch",
        ):
            assert_profile_identity(
                STAGE372_20W_PROFILE,
                official_version="official_live_stage847_c9_15w_stage819_05r_stop_retry_once",
                capital=200_000.0,
                capital_label="20w",
            )

        with self.assertRaisesRegex(
            ValueError,
            "execution_profile_capital_mismatch",
        ):
            assert_profile_identity(
                STAGE372_20W_PROFILE,
                official_version=STAGE372_20W_PROFILE.official_version,
                capital=150_000.0,
                capital_label="20w",
            )

        with self.assertRaisesRegex(
            ValueError,
            "execution_profile_capital_label_mismatch",
        ):
            assert_profile_identity(
                STAGE372_20W_PROFILE,
                official_version=STAGE372_20W_PROFILE.official_version,
                capital=200_000.0,
                capital_label="15w",
            )

    def test_historical_c9_profile_is_explicit_and_intraday(self) -> None:
        profile = C9_15W_HISTORICAL_PROFILE

        self.assertEqual(profile.profile_key, "c9-15w-historical")
        self.assertTrue(profile.intraday_stop_retry_enabled)
        self.assertIn("stage904_c9_intraday_close", profile.allowed_intent_sources)
        self.assertNotEqual(profile, STAGE372_20W_PROFILE)


if __name__ == "__main__":
    unittest.main()
