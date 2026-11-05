from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from stage061_2022_recap import DESTINATION, RUN, load_frozen, write


class Stage061RecapTest(unittest.TestCase):
    def test_annual_scope_preserves_cross_year_episodes_and_source_identity(self):
        bundle = load_frozen(RUN)
        self.assertEqual((len(bundle.closed), len(bundle.residual)), (167, 0))
        self.assertEqual((bundle.closed.net_pnl.gt(0).sum(), bundle.closed.net_pnl.lt(0).sum()), (52, 115))
        self.assertEqual(bundle.closed.net_pnl.sum(), 40080)
        self.assertEqual(bundle.closed.exit_day.gt("2022-12-31").sum(), 2)
        self.assertEqual(bundle.calendar_year_pnl, 38980)
        self.assertEqual(bundle.year_end_equity, 238980)
        self.assertEqual(bundle.metrics["equity"], 806115)
        self.assertEqual((bundle.metrics["closed_cycles"], bundle.metrics["open_positions"]), (1022, 12))
        self.assertEqual(len(bundle.fills.loc[bundle.fills.cycle.isin(bundle.closed.cycle)]), 360)
        self.assertEqual(len(bundle.rejected), 0)

    def test_wrong_or_incomplete_source_does_not_create_output(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "page"
            with self.assertRaises((ValueError, FileNotFoundError)):
                load_frozen(Path(tmp) / RUN.name)
            self.assertFalse(target.exists())

    def test_output_collision_and_cross_line_paths_are_rejected(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                write(RUN, Path(tmp) / "wrong-output")
        with self.assertRaises(FileExistsError):
            write(RUN, DESTINATION.parent)


if __name__ == "__main__":
    unittest.main()
