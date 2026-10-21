import unittest
import pandas as pd
from stage055_minute_input_qualification import qualify_component, reference_grid


class MinuteQualificationTests(unittest.TestCase):
    def setUp(self):
        self.expected=pd.date_range('2024-01-08T09:00:00',periods=3,freq='min')
        self.frame=pd.DataFrame(dict(bar_datetime=self.expected,open=[100,101,102],high=[102,103,104],low=[99,100,101],close=[101,102,103]))
        self.req=dict(contract_epoch_id='SHFE.AU.202406',source_trade_date='2024-01-08',exchange='SHFE',product='AU',
                      entry_price=100,source_open=100,source_high=104,source_low=99,source_close=103)
        self.binding=dict(contract_epoch_id=self.req['contract_epoch_id'],source_trade_date=self.req['source_trade_date'],
                          source_id='fixed-fixture',component='single',identity_basis='explicit exact epoch fixture')

    def test_complete_reference_input(self):
        r=qualify_component(self.frame,self.expected,self.req,self.binding)
        self.assertEqual(r['status'],'conditional_reference_input_qualified')
        self.assertFalse(r['physical_session_verified']);self.assertEqual(len(r['minute_path']),3)

    def test_missing_duplicate_unexpected_minute_rejected(self):
        self.assertEqual(qualify_component(self.frame.iloc[:2],self.expected,self.req,self.binding)['status'],'incomplete_grid')
        dup=pd.concat([self.frame,self.frame.iloc[:1]])
        self.assertEqual(qualify_component(dup,self.expected,self.req,self.binding)['status'],'duplicate_minute')
        extra=self.frame.copy();extra.loc[2,'bar_datetime']=pd.Timestamp('2024-01-08T10:00:00')
        self.assertEqual(qualify_component(extra,self.expected,self.req,self.binding)['status'],'incomplete_or_unexpected_grid')

    def test_exact_identity_and_daily_prices_required(self):
        wrong={**self.binding,'contract_epoch_id':'SHFE.AU.202412'}
        self.assertEqual(qualify_component(self.frame,self.expected,self.req,wrong)['status'],'exact_identity_mismatch')
        wrong={**self.req,'source_close':104}
        self.assertEqual(qualify_component(self.frame,self.expected,wrong,self.binding)['status'],'daily_ohlc_mismatch')

    def test_bad_geometry_and_mixed_components_rejected(self):
        bad=self.frame.copy();bad.loc[0,'low']=101
        self.assertEqual(qualify_component(bad,self.expected,self.req,self.binding)['status'],'invalid_ohlc')
        bad=self.frame.copy();bad['minute_source']=['a','b','b']
        self.assertEqual(qualify_component(bad,self.expected,self.req,self.binding)['status'],'mixed_source_components')

    def test_declared_component_and_explicit_row_identity_must_agree(self):
        bad=self.frame.copy();bad['minute_source']='other'
        self.assertEqual(qualify_component(bad,self.expected,self.req,self.binding)['status'],'source_component_mismatch')
        for key,value in [('contract_epoch_id','SHFE.AU.202412'),('source_trade_date','2024-01-09')]:
            bad=self.frame.copy();bad[key]=value
            self.assertEqual(qualify_component(bad,self.expected,self.req,self.binding)['status'],'explicit_row_identity_mismatch')

    def test_source_fields_require_real_prices_and_exact_date(self):
        bad={**self.req,'source_open':True}
        self.assertEqual(qualify_component(self.frame,self.expected,bad,self.binding)['status'],'invalid_source_prices')
        with self.assertRaises(ValueError):reference_grid({**self.req,'source_trade_date':'NaT'},self.expected)

    def test_exact_identity_cannot_be_mutually_absent_or_empty(self):
        for missing in ['contract_epoch_id','source_trade_date']:
            req={k:v for k,v in self.req.items() if k!=missing};binding={k:v for k,v in self.binding.items() if k!=missing}
            self.assertEqual(qualify_component(self.frame,self.expected,req,binding)['status'],'invalid_exact_identity')
            req={**self.req,missing:''};binding={**self.binding,missing:''}
            self.assertEqual(qualify_component(self.frame,self.expected,req,binding)['status'],'invalid_exact_identity')

    def test_calendar_is_trading_day_not_natural_day(self):
        calendar=pd.to_datetime(['2024-01-05','2024-01-08'])
        grid=reference_grid(self.req,calendar)
        self.assertEqual(grid[0],pd.Timestamp('2024-01-05T21:00:00'))
        self.assertEqual(grid[-1],pd.Timestamp('2024-01-08T14:59:00'))
        self.assertEqual(len(grid),555)
        for date,product in [('2019-01-08','AU'),('2024-01-08','J')]:
            with self.assertRaises(ValueError):reference_grid({**self.req,'source_trade_date':date,'product':product},calendar)


if __name__=='__main__':unittest.main()
