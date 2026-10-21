"""One reviewer-only corruption case; never runs author suites or real sources."""
import copy
import unittest
try:
    import stage187_warehouse_history_normalization_review as review
except ModuleNotFoundError:
    review = None


class ReviewerTests(unittest.TestCase):
    def test_retained_exact_decimal_mutation_is_rejected(self):
        self.assertIsNotNone(review, 'independent reviewer is missing')
        overlay = dict(entries=[], research_product_ids=['SHFE.CU'], disclosed_code_blocking_identities={})
        raw = dict(REGNAME='沪', REGSORT=0, ROWORDER=1, ROWSTATUS='0', VARNAME='铜$$COPPER',
                   VARSORT=0, WGHTUNIT='2', WHABBRNAME='甲库', WHROWS=1, WRTCHANGE=0,
                   WRTWGHTS='0.100000000000000005')
        row = review.json_rows([raw], '20200102', overlay)[0]
        saved = copy.deepcopy(row)
        saved['quantity']['value'] = '0.1'
        with self.assertRaises(AssertionError):
            review.equal(saved, row, 'numeric corruption')
        self.assertEqual(row['quantity']['value'], '0.100000000000000005')


if __name__ == '__main__':
    unittest.main()
