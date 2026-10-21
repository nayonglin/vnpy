"""Six bounded behavioral fixtures; no accepted data, prices or financial work."""
from pathlib import Path
import importlib.util
import unittest

SOURCE = Path(__file__).with_name('stage154_rule_coverage.py')


def metadata(exchange, product, symbol, maturity, listed='2020-01-01', trading_code=None):
    return dict(exchange=exchange, underlying_symbol=product, order_book_id=symbol,
                maturity_date=maturity, de_listed_date=maturity, listed_date=listed,
                trading_code=trading_code or symbol, type='Future', product='Commodity',
                start_delivery_date=None, end_delivery_date=None)


CATALOG = {'rows': [
    {'rule_id': 'DCE_F_cash_branch', 'source_status': 'formal body missing'},
    {'rule_id': 'DCE_ordinary_physical', 'source_url': 'https://example.invalid/dce'},
    {'rule_id': 'CZCE_natural_before_delivery_month', 'source_url': 'https://example.invalid/czce'},
    {'rule_id': 'INE_SC_LU_NR_legacy_T8', 'source_url': 'https://example.invalid/ine8'},
    {'rule_id': 'INE_BC_2020_T3', 'source_url': 'https://example.invalid/bc3'},
    {'rule_id': 'INE_EC_cash', 'source_url': 'https://example.invalid/ec'},
    {'rule_id': 'CFFEX_index_cash', 'source_url': 'https://example.invalid/index'},
    {'rule_id': 'CFFEX_treasury_unapproved_custody', 'source_url': 'https://example.invalid/treasury'}]}
OVERLAY = {'INE': {'historical_cutpoint_candidate': {
    'claimed_announcement_date': '2023-08-25', 'claimed_effective_date': '2023-10-18',
    'claimed_first_contract_month': '2023-11', 'evidence_level': 'candidate_only_not_promoted_to_strict_primary',
    'claimed_transition': {'LU': {'before_2311_offset': 8, '2311_and_after_offset': 5},
                           'NR': {'before_2311_offset': 8, '2311_and_after_offset': 5},
                           'BC': {'before_2311_offset': 3, '2311_and_after_offset': 5}}},
    'strict_transition_primary_ready': False}, 'GFEX': {'all_five_products_retained': []}}


class CoverageFixtures(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), 'Stage154 coverage implementation is missing')
        spec = importlib.util.spec_from_file_location('coverage154_fixture', SOURCE)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)

    def build(self, rows, inventory=()):
        return self.m.build_epoch_coverage(rows, list(inventory), {}, CATALOG, OVERLAY, '2026-10-16')

    def test_f_variant_does_not_inherit_ordinary_physical_deadline(self):
        """Catch merging L_F into the ordinary L rule branch."""
        rows = self.build([metadata('DCE', 'L', 'L2602', '2026-02-13'),
                           metadata('DCE', 'L_F', 'L2602F', '2026-01-30')])
        self.assertEqual(set(rows), {'DCE.L.202602', 'DCE.L_F.202602'})
        self.assertEqual(rows['DCE.L_F.202602']['rule_group'], 'DCE_F_cash_branch')
        self.assertEqual(rows['DCE.L_F.202602']['delivery_class_candidate'], 'cash')
        self.assertNotEqual(rows['DCE.L.202602']['candidate_formula'], rows['DCE.L_F.202602']['candidate_formula'])

    def test_czce_same_short_symbol_keeps_two_decades(self):
        """Catch collapsing SR501 from 2015 and 2025 into one epoch."""
        rows = self.build([metadata('CZCE', 'SR', 'SR1501', '2015-01-16', trading_code='SR501'),
                           metadata('CZCE', 'SR', 'SR2501', '2025-01-15', trading_code='SR501')])
        self.assertEqual(set(rows), {'CZCE.SR.201501', 'CZCE.SR.202501'})
        self.assertEqual(rows['CZCE.SR.201501']['nominal_contract_month'], '201501')

    def test_symbol_only_inventory_epoch_is_retained_without_donor_dates(self):
        """Catch dropping a clean identity without precise instrument metadata."""
        rows = self.build([], [{'contract_epoch_id': 'DCE.L_F.202704'}])
        row = rows['DCE.L_F.202704']
        self.assertFalse(row['metadata_present'])
        self.assertTrue(row['has_clean_observations'])
        self.assertIsNone(row['maturity_date'])
        self.assertIn('exact_epoch_metadata_dates', row['required_missing_fields'])
        self.assertFalse(row['strict_account_cutoff_ready'])

    def test_ine_2311_transition_is_candidate_and_sc_stays_separate(self):
        """Catch either promoting the broker cutpoint or applying LU5 to SC."""
        rows = self.build([metadata('INE', 'LU', 'LU2310', '2023-09-28'),
                           metadata('INE', 'LU', 'LU2311', '2023-10-31'),
                           metadata('INE', 'SC', 'SC2311', '2023-10-31'),
                           metadata('INE', 'BC', 'BC2310', '2023-09-28')])
        self.assertEqual(rows['INE.LU.202310']['candidate_formula'], 'flat_after_close_T_minus_8_trading_days')
        self.assertEqual(rows['INE.LU.202311']['candidate_formula'], 'flat_after_close_T_minus_5_trading_days')
        self.assertEqual(rows['INE.BC.202310']['candidate_formula'], 'flat_after_close_T_minus_3_trading_days')
        self.assertEqual(rows['INE.SC.202311']['candidate_formula'], 'flat_after_close_T_minus_8_trading_days')
        self.assertEqual(rows['INE.LU.202311']['temporal_applicability'], 'broker_candidate_2311_plus_not_official_known')
        self.assertTrue(all(not r['strict_account_cutoff_ready'] for r in rows.values()))
        self.assertTrue(all('account_cutoff_date' not in r for r in rows.values()))
        no_epoch = self.m.classify_rule('INE.LU', None, CATALOG, OVERLAY)
        self.assertEqual(no_epoch['candidate_formula'], 'conditional_candidate_T_minus_8_or_5_without_epoch_phase')

    def test_cash_branches_do_not_receive_physical_zero_rule(self):
        """Catch applying invoice/physical-delivery flat rules to EC or IF."""
        rows = self.build([metadata('INE', 'EC', 'EC2404', '2024-04-29'),
                           metadata('CFFEX', 'IF', 'IF2404', '2024-04-19'),
                           metadata('CFFEX', 'T', 'T2406', '2024-06-14')])
        for epoch in ['INE.EC.202404', 'CFFEX.IF.202404']:
            self.assertEqual(rows[epoch]['candidate_formula'], 'cash_settlement_separate_from_market_fill')
            self.assertEqual(rows[epoch]['delivery_class_candidate'], 'cash')
        self.assertEqual(rows['CFFEX.T.202406']['rule_group'], 'CFFEX_treasury_unapproved_custody')

    def test_no_observation_mother_is_retained_and_counted_in_2020_domain(self):
        """Catch inner-joining away an empty canonical reference and its denominator."""
        rows = self.build([metadata('DCE', 'L', 'L2401', '2024-01-15')])
        mothers = [dict(event_id='missing', sequence_index='0', product_id='DCE.L',
                        reference_epoch='', u_date='2020-01-02', u_index='1'),
                   dict(event_id='observed', sequence_index='1', product_id='DCE.L',
                        reference_epoch='DCE.L.202401', u_date='2024-01-02', u_index='2')]
        projected = list(self.m.project_mothers(iter(mothers), rows, CATALOG, OVERLAY))
        self.assertEqual(len(projected), 2)
        self.assertEqual(projected[0]['event_id'], 'missing')
        self.assertEqual(projected[0]['observation_state'], 'no_reference_observation')
        self.assertIsNone(projected[0]['has_clean_observations'])
        summary = self.m.summarize(projected)
        self.assertEqual(summary['rows'], 2)
        self.assertEqual(summary['no_reference_observation'], 1)
        self.assertEqual(summary['candidate_formula_expressible'], 2)


if __name__ == '__main__':
    unittest.main()
