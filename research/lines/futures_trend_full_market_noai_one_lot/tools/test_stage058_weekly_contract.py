"""Exact-contract completed weekly bars; synthetic data only, no financial run."""
import json
import unittest
import numpy as np
import pandas as pd
try:
    from stage058_weekly_contract import WeeklyContractTrend
except ModuleNotFoundError:
    WeeklyContractTrend=None


def source(weeks=42):
    cal=pd.bdate_range('2024-01-01',periods=weeks*5)
    ends=cal[cal.weekday==4]
    market=pd.DataFrame(dict(date=ends,vt_symbol='a202412.DCE',close=np.arange(1,weeks+1,dtype=float),volume=10.))
    contracts=pd.DataFrame([dict(vt_symbol='a202412.DCE',product_vt_symbol='a.DCE',listed_date='2024-01-01',maturity_date='2024-12-31')])
    return market,contracts,cal


class WeeklyContractTests(unittest.TestCase):
    def build(self,*args):
        self.assertIsNotNone(WeeklyContractTrend,'exact-contract weekly implementation is missing')
        return WeeklyContractTrend(*args)

    def test_exact_contract_forty_weeks_have_hand_calculated_means(self):
        gate=self.build(*source())
        r=gate.lookup('a202412.DCE','2024-10-04')
        self.assertTrue(r['allowed'])
        self.assertEqual(r['product_vt_symbol'],'a.DCE')
        self.assertEqual(r['contract_vt_symbol'],'a202412.DCE')
        self.assertEqual([r[f'ma{n}'] for n in (5,10,20,40)],[38.,35.5,30.5,20.5])
        self.assertEqual((r['history_weeks'],r['valid_weeks']),(40,40))
        self.assertEqual(r['week_last_session'],'2024-10-04')
        self.assertEqual((r['close'],r['volume']),(40.,10.))
        json.dumps(r,allow_nan=False)

    def test_same_product_opposite_contract_trends_stay_separate(self):
        m,c,cal=source(40)
        other=m.copy();other['vt_symbol']='a202503.DCE';other['close']=np.arange(40,0,-1,dtype=float)
        c=pd.concat([c,c.assign(vt_symbol='a202503.DCE')],ignore_index=True)
        gate=self.build(pd.concat([m,other],ignore_index=True),c,cal)
        self.assertTrue(gate.lookup('a202412.DCE','2024-10-04')['allowed'])
        r=gate.lookup('a202503.DCE','2024-10-04')
        self.assertFalse(r['allowed']);self.assertEqual(r['ma5'],3.)
        self.assertEqual(r['ma40'],20.5)

    def test_new_contract_cannot_borrow_other_contracts_forty_week_history(self):
        m,c,cal=source(40)
        other=m.iloc[-3:].copy();other['vt_symbol']='a202503.DCE';other['close']=[1000.,2000.,3000.]
        new=c.assign(vt_symbol='a202503.DCE',listed_date='2024-09-16')
        gate=self.build(pd.concat([m,other],ignore_index=True),pd.concat([c,new],ignore_index=True),cal)
        r=gate.lookup('a202503.DCE','2024-10-04')
        self.assertFalse(r['allowed']);self.assertEqual(r['history_weeks'],3);self.assertIsNone(r['ma40'])
        self.assertEqual(len(gate.weekly),3)
        self.assertEqual(gate.weekly.iloc[0]['week_last_session'],'2024-09-20')

    def test_other_contract_roll_gap_never_changes_current_contract_evidence(self):
        m,c,cal=source(40)
        original=self.build(m,c,cal).lookup('a202412.DCE','2024-10-04')
        other=m.copy();other['vt_symbol']='a202503.DCE';other['close']=1e8
        merged=self.build(pd.concat([m,other],ignore_index=True),pd.concat([c,c.assign(vt_symbol='a202503.DCE')]),cal)
        self.assertEqual(merged.lookup('a202412.DCE','2024-10-04'),original)

    def test_phase_and_monday_reject_future_week_close(self):
        gate=self.build(*source())
        for date,phase in [('2024-10-04','open'),('2024-09-30','signal_close'),('2024-09-30','open')]:
            r=gate.lookup('a202412.DCE',date,phase)
            self.assertFalse(r['allowed']);self.assertEqual(r['week_last_session'],'2024-09-27')
            self.assertEqual(r['history_weeks'],39)
        self.assertTrue(gate.lookup('a202412.DCE','2024-10-04')['allowed'])

    def test_missing_latest_completed_week_cannot_reuse_old_allowed_snapshot(self):
        m,c,cal=source()
        gate=self.build(m.iloc[:40],c,cal)
        self.assertTrue(gate.lookup('a202412.DCE','2024-10-04')['allowed'])
        self.assertTrue(gate.lookup('a202412.DCE','2024-10-11','open')['allowed'])
        r=gate.lookup('a202412.DCE','2024-10-11','signal_close')
        self.assertFalse(r['allowed']);self.assertEqual(r['reason'],'missing_latest_completed_contract_week')
        self.assertFalse(gate.lookup('a202412.DCE','2024-10-14','open')['allowed'])
        self.assertEqual(len(gate.weekly),40)  # no indefinite expired-contract padding

    def test_holiday_thursday_and_entire_closed_week_follow_independent_calendar(self):
        m,c,cal=source()
        cal=cal[~cal.isin(pd.date_range('2024-10-04','2024-10-13'))]
        m.loc[39,'date']=pd.Timestamp('2024-10-03')
        gate=self.build(m,c,cal)
        self.assertTrue(gate.lookup('a202412.DCE','2024-10-03')['allowed'])
        self.assertFalse(gate.lookup('a202412.DCE','2024-10-03','open')['allowed'])
        self.assertEqual(gate.lookup('a202412.DCE','2024-10-11')['week_last_session'],'2024-10-03')
        self.assertEqual(len(gate.weekly),41)

    def test_midweek_prefix_uses_full_calendar_future_friday_not_wednesday(self):
        m,c,_=source(40);m.loc[39,'date']=pd.Timestamp('2024-10-02')
        cal=pd.bdate_range('1900-01-01','2050-12-31')
        gate=self.build(m,c,cal)
        r=gate.lookup('a202412.DCE','2024-10-02')
        self.assertEqual(r['week_last_session'],'2024-09-27')
        self.assertEqual(len(gate.weekly),40)
        self.assertEqual(gate.weekly.iloc[-1]['week_last_session'],'2024-10-04')
        self.assertFalse(gate.weekly.iloc[-1]['valid'])

    def test_future_prices_and_added_future_contract_do_not_change_prefix_lookup(self):
        m,c,cal=source();baseline=self.build(m,c,cal)
        changed=m.copy();changed.loc[changed.date.ge('2024-10-04'),'close']=99999.
        other=changed.iloc[-1:].copy();other['vt_symbol']='a202503.DCE'
        future=self.build(pd.concat([changed,other],ignore_index=True),pd.concat([c,c.assign(vt_symbol='a202503.DCE')]),cal)
        prefix=self.build(m[m.date.lt('2024-10-04')],c,cal)
        for date,phase in [('2024-09-30','signal_close'),('2024-10-04','open')]:
            expected=baseline.lookup('a202412.DCE',date,phase)
            self.assertEqual(future.lookup('a202412.DCE',date,phase),expected)
            self.assertEqual(prefix.lookup('a202412.DCE',date,phase),expected)

    def test_bad_week_is_not_dropped_filled_or_borrowed_and_ages_out_normally(self):
        m,c,cal=source(45);m=m.drop(index=4)
        gate=self.build(m,c,cal)
        r=gate.lookup('a202412.DCE','2024-10-04')
        self.assertFalse(r['allowed']);self.assertEqual((r['history_weeks'],r['valid_weeks']),(40,39));self.assertIsNone(r['ma40'])
        self.assertTrue(pd.isna(gate.weekly.iloc[4]['close']))
        self.assertFalse(gate.lookup('a202412.DCE','2024-11-01')['allowed'])
        self.assertTrue(gate.lookup('a202412.DCE','2024-11-08')['allowed'])

    def test_quote_only_expiry_only_zero_volume_and_nan_fail_closed(self):
        for mutation in ('execution_only','expiry_only','unknown_execution','zero_volume','nan_close','negative_close','missing_eow'):
            with self.subTest(mutation=mutation):
                m,c,cal=source(40)
                if mutation=='execution_only':m['execution_only']=False;m.loc[39,'execution_only']=True
                elif mutation=='expiry_only':m['quote_class']='clean';m.loc[39,'quote_class']='expiry_execution_only'
                elif mutation=='unknown_execution':m['execution_only']=pd.Series([False]*40,dtype=object);m.loc[39,'execution_only']=None
                elif mutation=='zero_volume':m.loc[39,'volume']=0
                elif mutation=='nan_close':m.loc[39,'close']=np.nan
                elif mutation=='negative_close':m.loc[39,'close']=-1
                else:m.loc[39,'date']=pd.Timestamp('2024-10-03')
                r=self.build(m,c,cal).lookup('a202412.DCE','2024-10-04')
                self.assertFalse(r['allowed']);self.assertIsNone(r['ma5'])

    def test_equality_of_any_adjacent_mean_never_authorizes_long(self):
        for prices in ([100.]*40,list(range(1,31))+[40.]*10,[1.]*20+[10.]*10+[2.]*5+[18.]*5,[10.5]*20+list(range(1,21))):
            m,c,cal=source(40);m['close']=prices
            self.assertFalse(self.build(m,c,cal).lookup('a202412.DCE','2024-10-04')['allowed'])

    def test_lazy_export_is_explicit_queried_subset_not_all_contract_cartesian_grid(self):
        m,c,cal=source(40)
        c=pd.concat([c,pd.DataFrame([dict(vt_symbol=f'b{i:06}.DCE',product_vt_symbol='b.DCE',listed_date='2014-01-01') for i in range(4328)])])
        gate=self.build(m,c,pd.bdate_range('1900-01-01','2050-12-31'))
        self.assertTrue(gate.weekly.empty)
        gate.lookup('a202412.DCE','2024-10-04')
        self.assertEqual(len(gate.weekly),40)
        self.assertEqual(set(gate.weekly.contract_vt_symbol),{'a202412.DCE'})
        self.assertEqual(gate.export_scope,'queried_contracts_complete_local_weeks')
        self.assertEqual(set(gate.weekly.export_scope),{gate.export_scope})
        self.assertEqual(gate.queried_contracts,['a202412.DCE'])

    def test_unknown_empty_and_prelisting_contracts_are_json_safe(self):
        m,c,cal=source();gate=self.build(m,c,cal)
        for vt,date in [('a.DCE','2024-10-04'),('a202503.DCE','2024-10-04'),('','2024-10-04'),('a202412.DCE','2023-12-29')]:
            r=gate.lookup(vt,date);self.assertFalse(r['allowed']);self.assertIsNone(r['week_last_session']);json.dumps(r,allow_nan=False)
        c.loc[0,'listed_date']='2025-01-01'
        gate=self.build(m,c,cal)
        self.assertFalse(gate.lookup('a202412.DCE','2024-10-04')['allowed']);self.assertTrue(gate.weekly.empty)
        empty=self.build(m.iloc[:0],c,cal)
        self.assertFalse(empty.lookup('a202412.DCE','2024-10-04')['allowed'])

    def test_duplicate_exact_prices_or_contract_metadata_raise(self):
        m,c,cal=source()
        for prices,contracts in [(pd.concat([m,m.iloc[[0]]]),c),(m,pd.concat([c,c]))]:
            with self.assertRaises(ValueError):self.build(prices,contracts,cal)

    def test_invalid_phase_or_nonstr_contract_cannot_fall_back_to_product(self):
        gate=self.build(*source())
        with self.assertRaises(ValueError):gate.lookup('a202412.DCE','2024-10-04','intraday')
        with self.assertRaises(ValueError):gate.lookup(None,'2024-10-04')


if __name__=='__main__':unittest.main()
