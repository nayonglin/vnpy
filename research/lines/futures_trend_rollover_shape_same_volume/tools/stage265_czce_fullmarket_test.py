"""Contract identity safeguards for full-source sparse CZCE normalization."""
from collections import defaultdict
import unittest
from pathlib import Path
import tempfile
import stage265_czce_fullmarket as full


def candidate(code,listed,last):
    item=full.normalize_metadata_code(code,listed,last)
    return item['identity_key'],item


class FullMarketIdentityTests(unittest.TestCase):
    def test_four_and_three_digit_aliases_share_full_delivery_identity(self):
        key,row=candidate('SM1501.CZC','2014-08-08','2015-01-16')
        meta={('SM.CZCE','201501'):[row]}
        a=full.parse_identity('SM1501.CZC','2015-01-05',meta)
        b=full.parse_identity('SM501.CZC','2015-01-05',meta)
        self.assertEqual(a,b)
        self.assertEqual(a[0],'SM501.CZCE@201501')

    def test_metadata_separates_identical_code_across_decades(self):
        _,a=candidate('SM1501.CZC','2014-08-08','2015-01-16')
        _,b=candidate('SM2501.CZC','2024-01-15','2025-01-15')
        meta={('SM.CZCE','201501'):[a],('SM.CZCE','202501'):[b]}
        self.assertEqual(full.parse_identity('SM501.CZC','2015-01-05',meta)[3],'201501')
        self.assertEqual(full.parse_identity('SM501.CZC','2025-01-06',meta)[3],'202501')

    def test_old_product_code_is_not_renamed_from_filename(self):
        _,row=candidate('ME1505.CZC','2014-05-16','2015-05-15')
        parsed=full.parse_identity('ME1505.CZC','2015-01-05',{('ME.CZCE','201505'):[row]})
        self.assertEqual(parsed[2],'ME.CZCE')

    def test_before_issue_after_expiry_and_unknown_metadata_reject(self):
        _,row=candidate('SM1501.CZC','2014-08-08','2015-01-16')
        meta={('SM.CZCE','201501'):[row]}
        for day,source in [('2014-08-07',meta),('2015-01-17',meta),('2015-01-05',{})]:
            with self.subTest(day=day),self.assertRaisesRegex(ValueError,'missing_or_ambiguous'):
                full.parse_identity('SM1501.CZC',day,source)

    def test_duplicate_equal_cells_deduplicate_but_conflicts_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=full.CZCE) as folder:
            path=Path(folder)/'tiny.csv'
            path.write_text(',SM501.CZC\n2015-01-05,1\n2015-01-05,1\n2015-01-06,2\n2015-01-06,3\n')
            cells,info=full.read_wide(path)
            self.assertEqual(cells[('2015-01-05','SM501.CZC')][0],1)
            self.assertNotIn(('2015-01-06','SM501.CZC'),cells)
            self.assertEqual(info['identical_duplicate_nonmissing_cells_deduplicated'],1)
            self.assertEqual(len(info['conflicting_duplicate_nonmissing_cells_rejected']),1)

    def test_continuous_and_option_codes_are_not_real_contracts(self):
        for code in ['SM88.CZC','SM8888.CZC','SM501C6000.CZC','SM501.DCE']:
            with self.subTest(code=code),self.assertRaises(ValueError):
                full.parse_identity(code,'2015-01-05',{})


if __name__=='__main__':
    unittest.main()
