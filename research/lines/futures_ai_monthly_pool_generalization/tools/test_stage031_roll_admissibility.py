import copy
from datetime import date, timedelta
import unittest
import stage031_roll_admissibility as roll


def fixture(falling=False):
    closes=list(range(100,141))
    if falling:closes=closes[::-1]
    history=[dict(open=float(c),high=float(c+2),low=float(c-2),close=float(c),volume=100.,open_interest=200.) for c in closes]
    dates=[(date(2020,1,1)+timedelta(days=i)).isoformat() for i in range(41)]
    return history,dates


class RollAdmissibilityTests(unittest.TestCase):
    def setUp(self):
        for name in ("source_binding","advance_delay","evaluate_roll"):
            self.assertTrue(callable(getattr(roll,name,None)), "missing roll API: "+name)

    def test_source_binding_pins_release_and_shape(self):
        b=roll.source_binding()
        self.assertEqual(b['release_id'],'m0008_20261008T204054+0800_2a7420a9f955')
        self.assertEqual(b['required_delay_days'],5)
        self.assertEqual(set(b['method_ast_sha256']),{'_rollover_shape_continuation_snapshot','_calculate_macd'})

    def test_first_delay_zero_not_due(self):
        s=roll.advance_delay(None,'au2012.SHFE','2020-01-01')
        self.assertEqual((s['elapsed'],s['signal_day'],s['last_counted_day'],s['due']),(0,'2020-01-01','2020-01-01',False))

    def test_delay_counts_distinct_processed_days_not_calendar_distance(self):
        s=roll.advance_delay(None,'au2012.SHFE','2020-01-01')
        s=roll.advance_delay(s,'au2012.SHFE','2020-02-01')
        self.assertEqual(s['elapsed'],1)
        for day in ['2020-02-02','2020-02-03','2020-02-04','2020-02-05']:s=roll.advance_delay(s,'au2012.SHFE',day)
        self.assertTrue(s['due']);self.assertEqual(s['elapsed'],5)

    def test_repeated_day_idempotent_and_input_immutable(self):
        s=roll.advance_delay(None,'au2012.SHFE','2020-01-01');before=copy.deepcopy(s)
        self.assertEqual(roll.advance_delay(s,'au2012.SHFE','2020-01-01'),s)
        self.assertEqual(s,before)

    def test_target_change_resets_even_same_day(self):
        s=roll.advance_delay(None,'au2012.SHFE','2020-01-01');s=roll.advance_delay(s,'au2106.SHFE','2020-01-03')
        self.assertEqual((s['elapsed'],s['target_contract'],s['signal_day']),(0,'au2106.SHFE','2020-01-03'))

    def test_delay_rejects_backwards_or_invalid_state(self):
        s=roll.advance_delay(None,'au2012.SHFE','2020-02-01')
        for state,target,day in [(s,'au2012.SHFE','2020-01-01'),(s,'au2106.SHFE','2020-01-01'),(None,'','2020-01-01'),(None,'x','2020-1-1'),({**s,'elapsed':True},'x','2020-03-01'),({**s,'signal_day':'2021-01-01'},'x','2020-03-01')]:
            with self.subTest(state=state,target=target,day=day),self.assertRaises(ValueError):roll.advance_delay(state,target,day)

    def test_long_shape_stop_and_scope(self):
        h,ds=fixture();before=copy.deepcopy(h)
        result=roll.evaluate_roll('long',h,ds,ds[-1],contract='au2012.SHFE')
        self.assertTrue(result['allowed']);self.assertEqual(result['signal_stop'],138.)
        self.assertEqual(result['contract'],'au2012.SHFE');self.assertFalse(result['formal_roll_qualified'])
        self.assertFalse(result['calendar_continuity_certified']);self.assertEqual(h,before)

    def test_short_shape_inherited_stop(self):
        h,ds=fixture(True);result=roll.evaluate_roll('short',h,ds,ds[-1])
        self.assertTrue(result['allowed']);self.assertEqual(result['signal_stop'],102.)

    def test_opposite_or_flat_shape_known_disallowed(self):
        h,ds=fixture();self.assertFalse(roll.evaluate_roll('short',h,ds,ds[-1])['allowed'])
        for row in h:row.update(open=100.,high=102.,low=98.,close=100.)
        self.assertFalse(roll.evaluate_roll('long',h,ds,ds[-1])['allowed'])

    def test_invalid_history_does_not_drop_or_fill(self):
        h,ds=fixture()
        bad=[]
        for field,value in [('close',float('nan')),('volume',0),('low',200),('open',True),('high',float('inf'))]:
            hh=copy.deepcopy(h);hh[0][field]=value;bad.append(hh)
        hh=copy.deepcopy(h);del hh[0]['volume'];bad.append(hh);bad.extend([h[:-1],h+h[-1:]])
        for hh in bad:
            with self.subTest(h=hh[0]),self.assertRaises(ValueError):roll.evaluate_roll('long',hh,ds,ds[-1])

    def test_dates_must_be_strict_and_end_on_signal(self):
        h,ds=fixture();duplicate=ds.copy();duplicate[2]=duplicate[1]
        for dates,signal in [(ds[:-1],ds[-1]),(duplicate,ds[-1]),(ds[::-1],ds[0]),(ds,'2021-01-01')]:
            with self.subTest(dates=dates,signal=signal),self.assertRaises(ValueError):roll.evaluate_roll('long',h,dates,signal)

    def test_invalid_direction_and_contract_rejected(self):
        h,ds=fixture()
        for direction,contract in [('sideways',None),('long',''),('long',True)]:
            with self.subTest(direction=direction,contract=contract),self.assertRaises(ValueError):roll.evaluate_roll(direction,h,ds,ds[-1],contract=contract)

if __name__=='__main__':unittest.main()
