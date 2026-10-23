"""Synthetic bar-open context tests, never a financial replay."""
from types import SimpleNamespace
from datetime import datetime
import unittest
import pandas as pd
from vnpy.trader.object import BarData
from vnpy.trader.constant import Exchange,Interval,Offset
try:
    from stage011_bar_open_execution import bar_open_order_context
except ImportError:
    bar_open_order_context=None

CAL=['2025-01-02','2025-01-03','2025-01-06','2025-01-07']
def objects(fill='2025-01-06',signal='2025-01-03',symbol='rb2501',exchange=Exchange.SHFE):
    bar=BarData(symbol=symbol,exchange=exchange,datetime=datetime.fromisoformat(fill),interval=Interval.DAILY,
        open_price=100.,high_price=110.,low_price=90.,close_price=105.,volume=20.,gateway_name='TEST')
    class Engine:
        datetime=pd.Timestamp(fill)
        @property
        def strategy(self):raise AssertionError('must not inspect minute strategy/cache')
        def _resolve_trade_price(self,*args):raise AssertionError('must not resolve proxy/raw')
        def _stage827_order_context(self,*args):raise AssertionError('must not call old context')
    order=SimpleNamespace(vt_symbol=bar.vt_symbol,vt_orderid='TEST.1',datetime=pd.Timestamp(signal),offset=Offset.OPEN,price=88.,volume=1.)
    return Engine(),order,bar

class BarOpenTests(unittest.TestCase):
    def call(self,e,o,b,cal=CAL):
        self.assertIsNotNone(bar_open_order_context,'bar-open context API missing')
        return bar_open_order_context(e,o,b,cal)
    def test_completed_friday_signal_uses_next_week_bar_open_and_friday_night_model_clock(self):
        e,o,b=objects();c=self.call(e,o,b)
        self.assertEqual(c['price'],100.);self.assertEqual(str(c['trading_date']),'2025-01-06')
        self.assertEqual(c['execution_datetime'],pd.Timestamp('2025-01-03 21:00:00'))
        self.assertFalse(c['minute_quote_confirmed']);self.assertEqual(c['source'],'declared_daily_bar_open_model')
        self.assertEqual(c['proxy']['proxy_bar_count'],0)
        r=e.execution_anchor_requests[0]
        self.assertEqual(r['coverage_status'],'declared_daily_bar_open_model');self.assertFalse(r['minute_quote_confirmed'])
        self.assertEqual(r['source'],'declared_daily_bar_open_model')
    def test_holiday_reopen_uses_day_open_clock_with_no_minute_lookup(self):
        e,o,b=objects('2025-10-09','2025-09-30')
        c=self.call(e,o,b,['2025-09-29','2025-09-30','2025-10-09'])
        self.assertEqual(c['execution_datetime'],pd.Timestamp('2025-10-09 09:00:00'))
        self.assertEqual(c['price'],b.open_price)
    def test_day_only_product_has_day_open_clock(self):
        e,o,b=objects(symbol='AP501',exchange=Exchange.CZCE)
        c=self.call(e,o,b);self.assertEqual(c['execution_datetime'],pd.Timestamp('2025-01-06 09:00:00'))
    def test_stale_daily_bar_is_rejected_even_with_positive_volume(self):
        e,o,b=objects();b.datetime=datetime(2025,1,3)
        with self.assertRaisesRegex(ValueError,'stale_daily_bar'):self.call(e,o,b)
        self.assertFalse(hasattr(e,'execution_anchor_requests'))
    def test_daily_zero_volume_is_rejected_and_not_repaired(self):
        e,o,b=objects();b.volume=0.
        with self.assertRaisesRegex(ValueError,'invalid_daily_bar_volume'):self.call(e,o,b)
    def test_nonfinite_nonpositive_or_invalid_ohlc_rejected(self):
        for attr,value in [('open_price',float('nan')),('high_price',float('inf')),('low_price',0.),('high_price',99.),('low_price',106.)]:
            with self.subTest(attr=attr,value=value):
                e,o,b=objects();setattr(b,attr,value)
                with self.assertRaisesRegex(ValueError,'invalid_daily_bar_ohlc'):self.call(e,o,b)
    def test_bar_symbol_and_interval_must_match_real_daily_contract(self):
        e,o,b=objects();b.symbol='ru2501';b.vt_symbol='ru2501.SHFE'
        with self.assertRaisesRegex(ValueError,'daily_bar_symbol_mismatch'):self.call(e,o,b)
        e,o,b=objects();b.interval=Interval.MINUTE
        with self.assertRaisesRegex(ValueError,'daily_bar_interval_required'):self.call(e,o,b)
    def test_same_day_and_skipped_trade_day_orders_are_rejected(self):
        for fill,signal in [('2025-01-06','2025-01-06'),('2025-01-07','2025-01-03')]:
            with self.subTest(fill=fill,signal=signal):
                e,o,b=objects(fill,signal)
                with self.assertRaisesRegex(ValueError,'next_trading_day_required'):self.call(e,o,b)
    def test_missing_calendar_day_rejected(self):
        e,o,b=objects()
        with self.assertRaisesRegex(ValueError,'calendar'):self.call(e,o,b,['2025-01-02','2025-01-03'])
    def test_timezone_normalizes_date_and_context_has_all_fill_compatibility_fields(self):
        e,o,b=objects();e.datetime=pd.Timestamp('2025-01-05T16:00:00Z');o.datetime=pd.Timestamp('2025-01-02T16:00:00Z')
        c=self.call(e,o,b)
        required={'price','source','proxy','execution_datetime','trading_date','execution_time_source','anchor_coverage_status','expected_session_start','corrected_legacy_proxy','legacy_proxy_time','legacy_proxy_price'}
        self.assertTrue(required.issubset(c));self.assertFalse(c['corrected_legacy_proxy'])
        self.assertEqual(c['legacy_proxy_time'],'');self.assertIsNone(c['legacy_proxy_price'])
    def test_close_and_open_orders_have_identical_declared_bar_open_execution(self):
        e,o,b=objects('2025-01-07','2025-01-06');o.offset=Offset.CLOSE
        c=self.call(e,o,b);self.assertEqual(c['price'],100.)
        self.assertEqual(c['execution_datetime'],pd.Timestamp('2025-01-06 21:00:00'))
        self.assertEqual(e.execution_anchor_requests[0]['offset'],Offset.CLOSE.value)

class ActualFillConsumerTest(unittest.TestCase):
    def test_original_fill_order_consumes_context_without_proxy_or_minute_reads(self):
        from collections import Counter
        from vnpy.trader.object import OrderData
        from vnpy.trader.constant import Direction,Status
        from analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac import Stage827IntradayC2Engine
        e,o,b=objects()
        self.assertIsNotNone(bar_open_order_context,'bar-open context API missing')
        order=OrderData(symbol=b.symbol,exchange=b.exchange,orderid='1',direction=Direction.LONG,offset=Offset.OPEN,
            price=88.,volume=2.,datetime=o.datetime.to_pydatetime(),gateway_name='TEST',status=Status.SUBMITTING)
        context=bar_open_order_context(e,order,b,CAL)
        observed=[]
        strategy=SimpleNamespace(update_order=lambda order:None,update_trade=lambda trade:observed.append(trade))
        def forbidden(*args):raise AssertionError('no legacy order context or proxy read allowed')
        consumer=SimpleNamespace(_stage827_order_contexts={order.vt_orderid:context},_stage827_order_context=forbidden,
            _resolve_trade_price=forbidden,_stage827_physical_datetime=lambda stamp:pd.Timestamp(stamp).to_pydatetime(),
            strategy=strategy,active_limit_orders={order.vt_orderid:order},trade_count=0,trades={},gateway_name='TEST',
            source_counter=Counter(),trade_usage_rows=[],priceticks={order.vt_symbol:1.},datetime=e.datetime)
        Stage827IntradayC2Engine._fill_order(consumer,order,b)
        self.assertEqual(len(observed),1);self.assertEqual(observed[0].price,100.)
        self.assertEqual(observed[0].volume,2.);self.assertEqual(observed[0].datetime,datetime(2025,1,3,21))
        self.assertEqual(str(observed[0].trading_date),'2025-01-06')
        self.assertEqual(consumer.trade_usage_rows[0]['price_source'],'declared_daily_bar_open_model')
        self.assertEqual(consumer.trade_usage_rows[0]['proxy_bar_count'],0)
        self.assertEqual(consumer.active_limit_orders,{})

if __name__=='__main__':unittest.main()
