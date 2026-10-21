import unittest
from stage042_coldstart_coverage import asof_status, economics_fields, session_signal

class CoverageTests(unittest.TestCase):
    def test_eligibility_uses_past_not_future(self):
        rows=[dict(reference_epoch='A',input_ready=1,product='AU',exchange='SHFE') for _ in range(121)]
        self.assertEqual(asof_status(rows,119),'eligible')
        rows[120]['reference_epoch']=''
        self.assertEqual(asof_status(rows,119),'eligible')
        rows[0]['reference_epoch']=''
        self.assertEqual(asof_status(rows,119),'past120_representative_missing')
        self.assertEqual(asof_status(rows,118),'past120_clock_insufficient')

    def test_fixed_and_F_separate(self):
        for p,e,status in [('fu','SHFE','fixed_fu'),('AU_F','SHFE','monthly_average_F')]:
            rows=[dict(reference_epoch='A',input_ready=1,product=p,exchange=e) for _ in range(120)]
            self.assertEqual(asof_status(rows,119),status)

    def test_missing_future_observation_is_not_no_signal(self):
        self.assertEqual(session_signal(dict(input_ready=0)),('unknown',None))
        self.assertEqual(session_signal(dict(input_ready=1,reference_epoch='A',fresh_after_hardblocks=0)),('known',None))
        status,signal=session_signal(dict(input_ready=1,fresh_after_hardblocks=1,signal_direction='long',reference_epoch='A',signal_stop=99,high=101,low=99))
        self.assertEqual(status,'known');self.assertEqual(signal['qty'],2)

    def test_fee_mapping_unknowns_and_effective_LC_tick(self):
        row=dict(contract_multiplier=1,tick_size=20,commission_type='by_money',open_commission_ratio=.001,close_commission_ratio=None,close_commission_today_ratio=0)
        econ,guard=economics_fields(row,'lc2101.GFEX','2024-01-01')
        self.assertEqual(guard,20);self.assertEqual(econ['tick'],50)
        self.assertEqual(econ['open_per_lot'],0)
        self.assertIsNone(econ['close_per_lot']);self.assertIsNone(econ['close_rate'])
        self.assertEqual(econ['close_today_rate'],0)
        self.assertFalse(econ['historical_validated'])

    def test_unknown_hardblock_is_not_a_known_absent_fresh_signal(self):
        row=dict(input_ready=1,reference_epoch='A',fresh_direction_allowed=1,
                 fresh_after_hardblocks=0,hardblock_status='unknown')
        self.assertEqual(session_signal(row),('unknown',None))
        row['hardblock_status']='known'
        self.assertEqual(session_signal(row),('known',None))

if __name__=='__main__':unittest.main()
