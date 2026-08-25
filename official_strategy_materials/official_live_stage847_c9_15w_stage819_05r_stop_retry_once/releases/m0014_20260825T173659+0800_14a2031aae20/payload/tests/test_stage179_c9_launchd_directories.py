from __future__ import annotations

from pathlib import Path
import plistlib
import sys
import tempfile
import unittest


PORTFOLIO_DIR = (
    Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
)
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import provision_qmt_roll_c9_launchd_directories as provisioner  # noqa: E402


class Stage179C9LaunchdDirectoriesTest(unittest.TestCase):
    def test_canonical_plan_is_c9_only_bounded_and_never_calls_launchctl(self) -> None:
        plan = provisioner.build_directory_provision_plan()

        self.assertTrue(
            all(path.is_relative_to(plan.allowed_root) for path in plan.directories)
        )
        self.assertEqual(3, len(plan.plist_paths))
        self.assertTrue(all("c9-readonly" in path.name for path in plan.plist_paths))
        self.assertTrue(all("stage372" not in str(path) for path in plan.plist_paths))

        result = provisioner.provision_directories(plan, create=False)

        self.assertEqual(0, result["launchctl_called_count"])
        self.assertEqual(0, result["send_order_api_called_count"])
        self.assertEqual(0, result["cancel_order_api_called_count"])
        self.assertEqual(0, result["order_api_called_count"])

    def test_plist_directory_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plist = root / "escape.plist"
            plist.write_bytes(
                plistlib.dumps(
                    {
                        "Label": "test.escape",
                        "ProgramArguments": ["python"],
                        "StandardOutPath": str(root.parent / "outside" / "out.log"),
                    }
                )
            )

            with self.assertRaisesRegex(
                ValueError,
                "c9_launchd_directory_outside_allowed_root",
            ):
                provisioner._collect_required_directories(
                    (plist,),
                    allowed_root=root / "allowed",
                )


if __name__ == "__main__":
    unittest.main()
