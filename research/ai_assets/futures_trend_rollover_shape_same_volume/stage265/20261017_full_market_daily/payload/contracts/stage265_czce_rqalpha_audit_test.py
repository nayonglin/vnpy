"""Real monthly-average contracts remain separate from standard and continuous IDs."""
import unittest
from stage265_czce_rqalpha_independent_audit import classify


def meta(name,underlying,exchange,maturity):
    return {'order_book_id':name,'underlying_symbol':underlying,'exchange':exchange,'maturity_date':maturity}


class AuditContractFamilyTests(unittest.TestCase):
    def test_monthly_average_uses_code_month_not_prior_month_maturity(self):
        self.assertEqual(classify(meta('L2602F','L_F','DCE','2026-01-30')),('202602',None))
        self.assertEqual(classify(meta('PP2701F','PP_F','DCE','2026-12-31')),('202701',None))

    def test_suffix_does_not_authorize_merging_or_wrong_exchange(self):
        self.assertIsNone(classify(meta('L2602F','L','DCE','2026-01-30'))[0])
        self.assertIsNone(classify(meta('L2602F','L_F','CZCE','2026-01-30'))[0])

    def test_old_continuous_code_is_excluded_even_with_maturity(self):
        for name in ['ME88','ME888','ME889','ME99']:
            self.assertIsNone(classify(meta(name,'ME','CZCE','2015-05-15'))[0])

    def test_january_contract_can_mature_in_previous_year(self):
        self.assertEqual(classify(meta('SC2701','SC','INE','2026-12-31')),('202701',None))


if __name__=='__main__':unittest.main()
