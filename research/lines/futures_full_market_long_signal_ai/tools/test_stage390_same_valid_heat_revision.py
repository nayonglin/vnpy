"""Only the new Stage390 nonlinear integral, missingness and grid contract."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stage390_same_valid_heat_revision as probe


class PhysicalHeatFixture(unittest.TestCase):
    def test_integrate_before_trapezoid_missing_and_grid(self):
        np = probe.np
        old = np.array([[29., 30.], [31., 31.], [29., 32.]]) + 273.15
        new = np.array([[31., 31.], [31., np.nan], [31., 33.]]) + 273.15
        grid = {"metadata": {"gridType": "regular_ll", "scanningMode": 0},
                "latitudes": np.array([42., 40.]), "longitudes": np.array([267., 271.])}
        result = probe.paired_heat(old, new, grid, grid)
        # max before integration gives .25, while max after averaging gives0.
        self.assertAlmostEqual(result["old_EDD"][0], .25)
        self.assertAlmostEqual(result["new_EDD"][0], .5)
        self.assertAlmostEqual(result["revision_EDD"][0], .25)
        self.assertAlmostEqual(result["old_EDD"][1], .5)
        self.assertTrue(result["new_missing"][1])
        self.assertTrue(result["revision_missing"][1])
        self.assertTrue(np.isnan(result["new_EDD"][1]))
        self.assertTrue(np.isnan(result["revision_EDD"][1]))
        self.assertFalse(result["old_missing"].any())
        shifted = {**grid, "latitudes": grid["latitudes"][::-1]}
        with self.assertRaisesRegex(ValueError, "grid"):
            probe.paired_heat(old, new, grid, shifted)
        scanned = {**grid, "metadata": {"gridType": "regular_ll", "scanningMode": 64}}
        with self.assertRaisesRegex(ValueError, "grid"):
            probe.paired_heat(old, new, grid, scanned)


if __name__ == "__main__":
    unittest.main()
