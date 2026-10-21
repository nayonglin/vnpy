"""New reviewer metadata adapter behavior only; no actual source/model audit."""
import unittest
import source_checks as subject


class ExactMetadataInteger(unittest.TestCase):
    def test_integral_decimal_csv_representation_preserves_row_identity(self):
        self.assertTrue(hasattr(subject,'metadata_integer'),'strict integral Decimal metadata adapter is missing')
        self.assertEqual(subject.metadata_integer('3.0'),3)
        self.assertEqual(subject.metadata_integer('3'),3)

    def test_fractional_and_nonfinite_row_numbers_are_rejected(self):
        self.assertTrue(hasattr(subject,'metadata_integer'),'strict integral Decimal metadata adapter is missing')
        for value in ['3.5','NaN','Infinity','-Infinity','sNaN']:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):subject.metadata_integer(value)


if __name__=='__main__':unittest.main(verbosity=2)
