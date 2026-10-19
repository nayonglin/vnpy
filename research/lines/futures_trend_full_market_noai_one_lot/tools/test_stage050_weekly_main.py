"""Synthetic causal weekly contract tests: no financial replay."""
import json
import unittest
import numpy as np
import pandas as pd
try:
    from stage050_weekly_main import WeeklyMainTrend
except ModuleNotFoundError:
    WeeklyMainTrend = None


def source(weeks=42):
    calendar = pd.bdate_range('2024-01-01', periods=weeks * 5)
    fridays = calendar[calendar.weekday == 4]
    market = pd.DataFrame(dict(date=fridays, vt_symbol='a2409.DCE', close=np.arange(1, weeks + 1, dtype=float), volume=10.))
    mapping = pd.DataFrame(dict(date=fridays, continuous_symbol_vt='a.DCE', main_contract_vt='a2409.DCE', observation_date=fridays-pd.Timedelta(days=1)))
    return market, mapping, calendar


class WeeklyMainTests(unittest.TestCase):
    def build(self, *args):
        self.assertIsNotNone(WeeklyMainTrend, 'weekly causal gate implementation is missing')
        return WeeklyMainTrend(*args)

    def test_forty_completed_weeks_have_hand_calculated_strict_means(self):
        gate = self.build(*source())
        r = gate.lookup('a.DCE', '2024-10-04')
        self.assertTrue(r['allowed'])
        self.assertEqual([r[f'ma{n}'] for n in (5,10,20,40)], [38.,35.5,30.5,20.5])
        self.assertEqual((r['history_weeks'],r['valid_weeks']), (40,40))
        self.assertEqual(r['week_last_session'], '2024-10-04')
        self.assertEqual(r['phase'], 'signal_close')
        json.dumps(r, allow_nan=False)
        self.assertEqual(len(gate.weekly),42)

    def test_friday_open_and_monday_cannot_use_future_friday_close(self):
        gate = self.build(*source())
        for date,phase in [('2024-10-04','open'),('2024-09-30','open'),('2024-09-30','signal_close')]:
            r = gate.lookup('a.DCE', date, phase=phase)
            self.assertFalse(r['allowed'])
            self.assertEqual(r['week_last_session'],'2024-09-27')
            self.assertEqual(r['history_weeks'],39)
        self.assertTrue(gate.lookup('a.DCE','2024-10-04')['allowed'])

    def test_holiday_thursday_completes_week_and_all_closed_week_gets_no_bar(self):
        m,mp,cal = source()
        cal = cal[~cal.isin(pd.date_range('2024-10-04','2024-10-13'))]
        m.loc[39,'date'] = pd.Timestamp('2024-10-03')
        mp.loc[39,['date','observation_date']] = [pd.Timestamp('2024-10-03'),pd.Timestamp('2024-10-02')]
        gate = self.build(m,mp,cal)
        self.assertTrue(gate.lookup('a.DCE','2024-10-03')['allowed'])
        self.assertFalse(gate.lookup('a.DCE','2024-10-03',phase='open')['allowed'])
        self.assertEqual(gate.lookup('a.DCE','2024-10-11')['week_last_session'],'2024-10-03')
        self.assertEqual(len(gate.weekly),41)

    def test_source_truncated_wednesday_does_not_complete_the_week(self):
        m,mp,cal = source(40)
        m.loc[39,'date'] = pd.Timestamp('2024-10-02')
        mp.loc[39,['date','observation_date']] = [pd.Timestamp('2024-10-02'),pd.Timestamp('2024-10-01')]
        gate = self.build(m,mp,cal)
        self.assertEqual(gate.lookup('a.DCE','2024-10-02')['week_last_session'],'2024-09-27')
        self.assertEqual(gate.weekly.iloc[-1]['week_last_session'],'2024-10-04')
        self.assertFalse(gate.weekly.iloc[-1]['valid'])

    def test_broad_calendar_grid_stays_in_source_weeks_without_clipping_eow(self):
        m,mp,_=source(40)
        cal=pd.bdate_range('1900-01-01','2050-12-31')
        gate=self.build(m,mp,cal)
        self.assertEqual(len(gate.weekly),40)
        self.assertEqual(gate.weekly.iloc[0]['week_last_session'],'2024-01-05')
        self.assertTrue(gate.lookup('a.DCE','2024-10-04')['allowed'])

    def test_broad_calendar_midweek_prefix_retains_true_future_eow_invalid(self):
        m,mp,_=source(40); cal=pd.bdate_range('1900-01-01','2050-12-31')
        m.loc[39,'date']=pd.Timestamp('2024-10-02')
        mp.loc[39,['date','observation_date']]=[pd.Timestamp('2024-10-02'),pd.Timestamp('2024-10-01')]
        gate=self.build(m,mp,cal)
        self.assertEqual(len(gate.weekly),40)
        self.assertEqual(gate.weekly.iloc[-1]['week_last_session'],'2024-10-04')
        self.assertFalse(gate.weekly.iloc[-1]['valid'])
        self.assertEqual(gate.lookup('a.DCE','2024-10-02')['week_last_session'],'2024-09-27')

    def test_equal_or_descending_means_do_not_authorize_long(self):
        for prices in ([100.]*40,list(range(40,0,-1)),list(range(1,31))+[40.]*10,
                       [1.]*20+[10.]*10+[2.]*5+[18.]*5,[10.5]*20+list(range(1,21))):
            m,mp,cal = source(40); m['close'] = prices
            self.assertFalse(self.build(m,mp,cal).lookup('a.DCE','2024-10-04')['allowed'])

    def test_bad_week_is_not_dropped_or_forward_filled(self):
        m,mp,cal = source(); m.loc[4,'close'] = float('nan')
        gate = self.build(m,mp,cal); row = gate.weekly.iloc[39]
        self.assertFalse(row['allowed'])
        self.assertEqual((row['history_weeks'],row['valid_weeks']),(40,39))
        self.assertTrue(pd.isna(row['ma40']))
        self.assertTrue(pd.isna(gate.weekly.iloc[4]['close']))
        self.assertFalse(gate.lookup('a.DCE','2024-10-18')['allowed'])

    def test_bad_week_recovers_only_when_it_ages_out_of_full_window(self):
        m,mp,cal=source(45); m.loc[4,'close']=float('nan')
        gate=self.build(m,mp,cal)
        self.assertFalse(gate.lookup('a.DCE','2024-11-01')['allowed'])
        self.assertTrue(gate.lookup('a.DCE','2024-11-08')['allowed'])

    def test_products_keep_independent_histories_and_json_lookup_is_detached(self):
        m,mp,cal=source(40)
        b=m.copy(); b['vt_symbol']='b2409.DCE'; b['close']=100.
        bm=mp.copy(); bm['continuous_symbol_vt']='b.DCE'; bm['main_contract_vt']='b2409.DCE'
        gate=self.build(pd.concat([m,b]),pd.concat([mp,bm]),cal)
        r=gate.lookup('a.DCE','2024-10-04'); r['allowed']=False
        self.assertTrue(gate.lookup('a.DCE','2024-10-04')['allowed'])
        self.assertFalse(gate.lookup('b.DCE','2024-10-04')['allowed'])
        self.assertEqual(gate.lookup('b.DCE','2024-10-04')['ma40'],100.)

    def test_selected_quote_cannot_be_replaced_by_another_contract(self):
        for mutation in ('missing','zero_volume','negative_close','quote_only','unknown_execution','quote_class'):
            with self.subTest(mutation=mutation):
                m,mp,cal = source(40)
                other = m.iloc[[-1]].copy(); other['vt_symbol']='a2410.DCE'; other['close']=10000.
                m = pd.concat([m,other],ignore_index=True)
                if mutation=='missing': m=m.drop(index=39)
                elif mutation=='zero_volume': m.loc[39,'volume']=0
                elif mutation=='negative_close': m.loc[39,'close']=-1
                elif mutation=='quote_only':
                    m['execution_only']=False; m.loc[39,'execution_only']=True
                elif mutation=='unknown_execution':
                    m['execution_only']=pd.Series([False]*len(m),dtype=object); m.loc[39,'execution_only']=None
                else:
                    m['quote_class']='clean'; m.loc[39,'quote_class']='quantity_conflict_price_consensus_execution_only'
                r=self.build(m,mp,cal).lookup('a.DCE','2024-10-04')
                self.assertFalse(r['allowed']); self.assertIsNone(r['ma5'])

    def test_notready_or_noncausal_mapping_invalidates_week_without_global_failure(self):
        for contract,obs in [('', ''),('a2409.DCE',''),('a2409.DCE','2024-10-04'),('a2409.DCE','2024-10-07')]:
            m,mp,cal=source(40); mp['observation_date']=mp.observation_date.astype(object)
            mp.loc[39,['main_contract_vt','observation_date']]=[contract,obs]
            self.assertFalse(self.build(m,mp,cal).lookup('a.DCE','2024-10-04')['allowed'])
        m,mp,cal=source(40)
        self.assertFalse(self.build(m,mp.drop(index=39),cal).lookup('a.DCE','2024-10-04')['allowed'])

    def test_roll_uses_raw_mapped_close_without_adjustment_or_same_day_oi_selection(self):
        m,mp,cal=source(40)
        m.loc[39,['vt_symbol','close']]=['a2501.DCE',200.]; mp.loc[39,'main_contract_vt']='a2501.DCE'
        other=m.iloc[[-1]].copy(); other['vt_symbol']='a2409.DCE'; other['close']=10000.; other['open_interest']=1e12
        gate=self.build(pd.concat([m,other],ignore_index=True),mp,cal)
        self.assertEqual(gate.weekly.iloc[-1]['close'],200.)
        self.assertEqual(gate.lookup('a.DCE','2024-10-04')['ma5'],70.)

    def test_future_mapping_and_price_changes_preserve_past_and_prefix_evidence(self):
        m,mp,cal=source(); baseline=self.build(m,mp,cal)
        m2=m.copy(); m2.loc[m2.date.ge('2024-10-04'),'close']=99999.
        mp2=mp.copy(); mp2.loc[mp2.date.ge('2024-10-04'),'main_contract_vt']='a9999.DCE'
        changed=self.build(m2,mp2,cal)
        prefix=self.build(m[m.date.lt('2024-10-04')],mp[mp.date.lt('2024-10-04')],cal)
        for date,phase in [('2024-09-30','signal_close'),('2024-10-04','open')]:
            expected=baseline.lookup('a.DCE',date,phase)
            self.assertEqual(changed.lookup('a.DCE',date,phase),expected)
            self.assertEqual(prefix.lookup('a.DCE',date,phase),expected)

    def test_empty_unknown_and_before_first_week_fail_closed_json_safe(self):
        m,mp,cal=source(); gate=self.build(m,mp,cal)
        for product,date in [('a.DCE','2023-12-30'),('missing.DCE','2024-10-04'),('','2024-10-04')]:
            r=gate.lookup(product,date); self.assertFalse(r['allowed']); self.assertIsNone(r['week_last_session']); json.dumps(r,allow_nan=False)
        empty=self.build(m.iloc[:0],mp.iloc[:0],cal)
        self.assertTrue(empty.weekly.empty)
        self.assertFalse(empty.lookup('a.DCE','2024-10-04')['allowed'])

    def test_duplicate_prices_or_mapping_raise_instead_of_arbitrary_selection(self):
        m,mp,cal=source(40)
        for prices,maps in [(pd.concat([m,m.iloc[[0]]]),mp),(m,pd.concat([mp,mp.iloc[[0]]]))]:
            with self.assertRaises(ValueError): self.build(prices,maps,cal)

    def test_invalid_phase_does_not_implicitly_expose_close(self):
        with self.assertRaises(ValueError): self.build(*source()).lookup('a.DCE','2024-10-04',phase='intraday')


if __name__=='__main__': unittest.main()
