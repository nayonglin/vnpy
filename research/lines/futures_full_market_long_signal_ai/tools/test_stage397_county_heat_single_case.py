"""Small numerical contract only; no historical experiment is rerun."""
import importlib.util
import unittest
from pathlib import Path

import numpy as np


class SpatialContract(unittest.TestCase):
    def test_periodic_nearest_and_missing_mass(self):
        path = Path(__file__).with_name("stage397_county_heat_single_case.py")
        spec = importlib.util.spec_from_file_location("stage397", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Near the longitude seam,359 is closer to-1 than0; equal points tie at0.
        self.assertEqual(module.nearest(0, -1, np.array([0., 0.]), np.array([0., 359.]))[0], 1)
        self.assertEqual(module.nearest(0, 1, np.array([0., 0.]), np.array([1., 1.]))[0], 0)
        # Missing half of county pixels must not make a100% covered average.
        value, covered = module.weighted_component([10, 10], [2., None])
        self.assertEqual(value, 1.)
        self.assertEqual(covered, .5)


if __name__ == "__main__":
    unittest.main()
