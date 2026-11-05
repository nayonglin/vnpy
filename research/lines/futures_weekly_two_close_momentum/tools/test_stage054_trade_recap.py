from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from stage054_trade_recap import DESTINATION, RUN, load_frozen, write


class Stage054RecapTest(unittest.TestCase):
    def test_frozen_window_keeps_residual_and_rejections_separate(self):
        bundle = load_frozen(RUN)
        self.assertEqual((len(bundle.closed), len(bundle.residual), len(bundle.fills)), (107, 15, 295))
        self.assertEqual((len(bundle.rejected), len(bundle.stops)), (75, 1))
        self.assertEqual(bundle.metrics["equity"], 160295)
        self.assertEqual(bundle.closed.net_pnl.sum(), -100075)
        self.assertEqual(bundle.residual.net_pnl.sum(), 110370)

    def test_incomplete_bundle_fails_before_output(self):
        with TemporaryDirectory() as tmp:
            destination = Path(tmp) / "output"
            with self.assertRaises((ValueError, FileNotFoundError)):
                write(Path(tmp) / RUN.name, destination)
            self.assertFalse(destination.exists())

    def test_existing_and_cross_line_outputs_are_rejected(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                write(RUN, Path(tmp) / "cross-line")
        self.assertEqual(DESTINATION.name, "stage054_s21_gold_touch_2026_recap_v1")
        with self.assertRaises(FileExistsError):
            write(RUN, DESTINATION.parent)


if __name__ == "__main__":
    unittest.main()
