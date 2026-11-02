"""Frozen execution-correctness regressions; these tests do not tune strategy alpha."""
from collections import Counter
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'examples' / 'portfolio_backtesting'))
import analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac as c2
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as c9
from vnpy.trader.constant import Direction, Exchange, Offset
from vnpy.trader.object import TradeData


def bars(*rows):
    frame = pd.DataFrame(rows, columns=['bar_datetime', 'open', 'high', 'low', 'close'])
    frame['bar_datetime'] = pd.to_datetime(frame['bar_datetime'])
    frame['bar_date'] = frame['bar_datetime'].dt.normalize()
    return frame


def strategy(frame, *, short=False, tick=1, c2_only=False):
    cls = c2.QmtRollPortfolioStrategyStage827C2 if c2_only else c9.QmtRollPortfolioStrategyStage847C9StopRetry
    obj = object.__new__(cls)
    direction = 'short' if short else 'long'
    obj.state = SimpleNamespace(layers=[SimpleNamespace(direction=direction, stop_price=110 if short else 90,
        entry_price=100., volume=1)], direction=direction, contract_vt_symbol='cu2611.SHFE', product_vt_symbol='cu.SHFE')
    obj._find_state_by_contract = lambda symbol: obj.state
    obj.get_pricetick = lambda symbol: tick
    obj.stage827_minute_by_symbol = {'cu2611.SHFE': frame}
    obj.available_trade_dates = list(pd.to_datetime(['2026-10-09', '2026-10-12', '2026-10-13', '2026-10-14', '2026-10-15']))
    obj.strategy_engine = SimpleNamespace(bars={}, datetime=datetime(2026,10,14))
    obj.stage827_intraday_c2_events = []
    obj.stage827_intraday_c2_stop_count = 0
    obj.stage847_stop_retry_events = []
    obj.stage847_stop_retry_event_count = 0
    obj.stage827_require_complete_minutes = False
    obj.enable_stage827_intraday_c2_stop = c2_only
    obj.enable_stage847_half_r_stop_retry = not c2_only
    obj._close_all_layers_and_set_flat_target = lambda *args, **kwargs: None
    obj._record_trade_event = lambda **kwargs: None
    obj._close_layers = lambda *args, **kwargs: None
    obj._apply_state_target = lambda *args, **kwargs: None
    return obj


def trade(at='2026-10-14', *, short=False, execution_at='2026-10-14 09:00'):
    result = TradeData(symbol='cu2611', exchange=Exchange.SHFE, orderid='1', tradeid='1',
        direction=Direction.SHORT if short else Direction.LONG, offset=Offset.OPEN,
        price=100., volume=1, datetime=pd.Timestamp(at).to_pydatetime(), gateway_name='BACKTESTING')
    result.execution_datetime = pd.Timestamp(execution_at).to_pydatetime()
    result.trading_date = pd.Timestamp(at).normalize().date()
    return result


class IntradayCorrectionTest(unittest.TestCase):
    def event(self, frame, *, short=False, tick=1, entry=None, c2_only=False):
        obj = strategy(frame, short=short, tick=tick, c2_only=c2_only)
        return obj.stage827_intraday_exit_after_open_trade(entry or trade(short=short))

    def test_includes_previous_night_and_excludes_next_night(self):
        frame = bars(('2026-10-13 21:00',100,101,94,96), ('2026-10-14 09:00',100,101,99,100),
            ('2026-10-14 21:00',90,92,89,90))
        result = self.event(frame, entry=trade(execution_at='2026-10-13 21:00'))
        self.assertEqual(result['first_stop_time'], '2026-10-13T21:00:00')

    def test_no_scan_before_actual_open(self):
        frame = bars(('2026-10-14 09:00',100,101,94,96), ('2026-10-14 10:00',100,101,99,100))
        self.assertIsNone(self.event(frame, entry=trade(execution_at='2026-10-14 10:00')))

    def test_no_next_trading_day_night_at_endpoint(self):
        frame = bars(('2026-10-14 09:00',100,101,99,100), ('2026-10-14 21:00',90,92,89,90))
        self.assertIsNone(self.event(frame))

    def test_gap_stop_executes_at_open_not_unreachable_threshold(self):
        result = self.event(bars(('2026-10-14 09:00',90,92,89,91)))
        self.assertEqual(result['synthetic_trades'][0]['price'], 90.)

    def test_short_gap_stop_executes_at_open(self):
        result = self.event(bars(('2026-10-14 09:00',110,112,109,111)), short=True)
        self.assertEqual(result['synthetic_trades'][0]['price'], 110.)

    def test_off_tick_stop_rounds_in_adverse_direction(self):
        obj = strategy(bars(('2026-10-14 09:00',100,101,94,96)))
        obj.state.layers[0].stop_price = 91
        result = obj.stage827_intraday_exit_after_open_trade(trade())
        self.assertEqual(result['stop_price'], 95.5)
        self.assertEqual(result['synthetic_trades'][0]['price'], 95.)

    def test_progress_at_open_precedes_later_intrabar_stop(self):
        frame = bars(('2026-10-14 09:00',106,107,94,96))
        self.assertIsNone(self.event(frame))

    def test_retry_bar_can_stop_after_reclaim_in_same_bar(self):
        frame = bars(('2026-10-14 09:00',100,101,94,96), ('2026-10-14 09:01',96,100,94,98))
        result = self.event(frame)
        self.assertEqual(len(result['synthetic_trades']), 3)
        self.assertEqual(result['retry_failed_time'], result['reentry_time'])
        self.assertIn('same_bar', result['synthetic_trades'][2]['execution_note'])

    def test_retry_gap_uses_actual_open(self):
        frame = bars(('2026-10-14 09:00',100,101,94,96), ('2026-10-14 09:01',102,103,99,102))
        result = self.event(frame)
        self.assertEqual(result['synthetic_trades'][1]['price'], 102.)

    def test_c2_stop_has_reachable_fill_and_actual_hit_time(self):
        result = self.event(bars(('2026-10-14 09:00',85,87,84,86)), c2_only=True)
        self.assertEqual(result.get('fill_price'), 85.)
        self.assertEqual(result['hit_time'], '2026-10-14T09:00:00')

    def test_missing_minutes_raise_in_strict_mode_and_record_request(self):
        obj = strategy(bars())
        obj.stage827_require_complete_minutes = True
        with self.assertRaisesRegex(ValueError, 'intraday_minute_coverage'):
            obj.stage827_intraday_exit_after_open_trade(trade())
        self.assertEqual(obj.minute_scan_requests[-1]['vt_symbol'], 'cu2611.SHFE')


class EngineExecutionTest(unittest.TestCase):
    def engine(self):
        from vnpy.trader.object import BarData, OrderData
        from vnpy.trader.constant import Status
        eng = c9.Stage847StopRetryEngine({})
        eng.datetime = datetime(2026,10,14)
        eng.output = lambda message: None
        eng.seen = []
        eng.finalized = []
        eng.strategy = SimpleNamespace(
            available_trade_dates=pd.to_datetime(['2026-10-12','2026-10-13','2026-10-14','2026-10-15']),
            stage827_minute_by_symbol={}, stage827_require_complete_minutes=False,
            update_order=lambda order: None, update_trade=lambda event: eng.seen.append(event),
            stage827_intraday_exit_after_open_trade=lambda event: None,
            _stage827_finalize_intraday_action=lambda event,item,final: eng.finalized.append((item['time'],final)),
        )
        eng.priceticks = {'cu2611.SHFE':1,'au2612.SHFE':1}
        eng.bars = {symbol: BarData(symbol=symbol.split('.')[0],exchange=Exchange.SHFE,
            datetime=eng.datetime, open_price=100, high_price=110,low_price=90,close_price=101,gateway_name='BACKTESTING')
            for symbol in eng.priceticks}
        eng.make_order = lambda symbol, number: OrderData(symbol=symbol.split('.')[0],exchange=Exchange.SHFE,
            orderid=str(number), direction=Direction.LONG,offset=Offset.OPEN,price=100,volume=1,
            status=Status.SUBMITTING,datetime=datetime(2026,10,13),gateway_name='BACKTESTING')
        eng._resolve_trade_price = lambda order,bar: (100.,'raw_test_first_open',{
            'proxy_first_time':'2026-10-13 21:00' if order.symbol.startswith('cu') else '2026-10-14 09:00'})
        return eng

    def test_ordinary_trade_keeps_execution_time_and_trading_date_separate(self):
        eng=self.engine()
        order=eng.make_order('cu2611.SHFE',1)
        eng._fill_order(order,eng.bars[order.vt_symbol])
        result=eng.seen[0]
        self.assertEqual(result.datetime,datetime(2026,10,13,21))
        self.assertEqual(str(getattr(result,'trading_date',None)),'2026-10-14')
        self.assertEqual(eng.trade_usage_rows[0].get('execution_datetime'),'2026-10-13T21:00:00')

    def test_c2_fallback_emitter_uses_fill_price_and_actual_time(self):
        eng=self.engine()
        order=eng.make_order('cu2611.SHFE',1)
        event={'volume':1,'stop_price':95.5,'fill_price':90.,'hit_time':'2026-10-13T21:01:00',
            'trading_date':'2026-10-14','exit_reason':'stage827_intraday_c2_1r_stop','vt_symbol':order.vt_symbol}
        eng._fill_synthetic_intraday_close(order,trade(execution_at='2026-10-13 21:00'),event)
        self.assertEqual(eng.seen[0].price,90.)
        self.assertEqual(eng.seen[0].datetime,datetime(2026,10,13,21,1))

    def test_cross_symbol_orders_and_synthetic_are_chronological(self):
        eng=self.engine()
        first=eng.make_order('cu2611.SHFE',1)
        second=eng.make_order('au2612.SHFE',2)
        eng.active_limit_orders={first.vt_orderid:first,second.vt_orderid:second}
        def hook(open_trade):
            if open_trade.symbol!='cu2611':
                return None
            return {'volume':1,'stop_price':95.,'fill_price':95.,'hit_time':'2026-10-14T10:00:00',
                'trading_date':'2026-10-14','exit_reason':'stage827_intraday_c2_1r_stop','vt_symbol':open_trade.vt_symbol}
        eng.strategy.stage827_intraday_exit_after_open_trade=hook
        eng.cross_delayed_orders()
        self.assertEqual([item.symbol for item in eng.seen],['cu2611','au2612','cu2611'])
        self.assertEqual([item.datetime for item in eng.seen],sorted(item.datetime for item in eng.seen))
        self.assertEqual(eng.finalized,[('2026-10-14T10:00:00',True)])

    def test_night_fill_is_booked_on_target_trading_day(self):
        from vnpy_portfoliostrategy.backtesting import PortfolioDailyResult
        eng=self.engine()
        item=trade(execution_at='2026-10-13 21:00')
        item.datetime=item.execution_datetime
        eng.trades={item.vt_tradeid:item}
        eng.daily_results={datetime(2026,10,13).date():PortfolioDailyResult(datetime(2026,10,13).date(),{'cu2611.SHFE':99}),
            datetime(2026,10,14).date():PortfolioDailyResult(datetime(2026,10,14).date(),{'cu2611.SHFE':101})}
        eng.sizes={'cu2611.SHFE':1}; eng.rates={'cu2611.SHFE':0}; eng.slippages={'cu2611.SHFE':0}
        result=eng.calculate_result()
        self.assertEqual(result.loc[datetime(2026,10,13).date(),'trade_count'],0)
        self.assertEqual(result.loc[datetime(2026,10,14).date(),'net_pnl'],1)
        self.assertEqual(eng.trades[item.vt_tradeid].datetime,datetime(2026,10,13,21))

    def test_retry_actual_price_updates_live_layer(self):
        obj=strategy(bars(('2026-10-14 09:00',100,101,94,96),('2026-10-14 09:01',102,103,99,102)))
        event=obj.stage827_intraday_exit_after_open_trade(trade())
        self.assertEqual(obj.state.layers[0].entry_price,100.)
        obj._stage827_finalize_intraday_action(event,event['synthetic_trades'][1],final=True)
        self.assertEqual(obj.state.layers[0].entry_price,102.)


class SessionAndPriceContractTest(unittest.TestCase):
    def test_weekend_night_and_saturday_are_monday_session(self):
        grid=c2.execution.session_minutes('au2612.SHFE','2026-10-12',['2026-10-09','2026-10-12'])
        self.assertEqual(len(grid),555)
        self.assertIn(pd.Timestamp('2026-10-10 01:30'),grid)
        self.assertNotIn(pd.Timestamp('2026-10-12 00:00'),grid)
        self.assertNotIn(pd.Timestamp('2026-10-12 21:00'),grid)

    def test_holiday_eve_and_2020_night_pause_are_closed(self):
        holiday=c2.execution.session_minutes('cu2611.SHFE','2026-10-09',['2026-09-30','2026-10-09'])
        pause=c2.execution.session_minutes('cu2005.SHFE','2020-03-04',['2020-03-03','2020-03-04'])
        resume=c2.execution.session_minutes('cu2005.SHFE','2020-05-07',['2020-05-06','2020-05-07'])
        self.assertEqual(len(holiday),225)
        self.assertEqual(len(pause),225)
        self.assertEqual(len(resume),465)

    def test_sh_has_night_and_sm_is_day_only(self):
        calendar=['2026-10-13','2026-10-14']
        self.assertEqual(len(c2.execution.session_minutes('SH701.CZCE','2026-10-14',calendar)),345)
        self.assertEqual(len(c2.execution.session_minutes('SM701.CZCE','2026-10-14',calendar)),225)

    def test_float_noise_does_not_add_whole_adverse_tick(self):
        self.assertEqual(c2.execution.adverse_tick(0.1+0.2,0.1,buy=True),0.3)
        self.assertEqual(c2.execution.adverse_tick(0.3-1e-16,0.1,buy=False),0.3)

    def test_complete_minute_grid_accepted_in_strict_mode(self):
        grid=c2.execution.session_minutes('cu2611.SHFE','2026-10-14',['2026-10-13','2026-10-14'])
        frame=bars(*[(stamp,100,101,99,100) for stamp in grid])
        obj=strategy(frame);obj.stage827_require_complete_minutes=True
        self.assertIsNone(obj.stage827_intraday_exit_after_open_trade(trade(execution_at='2026-10-13 21:00')))
        self.assertEqual(obj.minute_scan_requests[-1]['missing_bar_count'],0)

    def test_invalid_ohlc_fails_before_planning(self):
        obj=strategy(bars(('2026-10-14 09:00',100,101,102,100)))
        with self.assertRaisesRegex(ValueError,'intraday_invalid_ohlc'):
            obj.stage827_intraday_exit_after_open_trade(trade())

    def test_short_retry_bar_uses_adverse_tick_after_reclaim(self):
        frame=bars(('2026-10-14 09:00',100,106,99,104),('2026-10-14 09:01',104,106,99,103))
        obj=strategy(frame,short=True)
        result=obj.stage827_intraday_exit_after_open_trade(trade(short=True))
        self.assertEqual([item['price'] for item in result['synthetic_trades']],[105.,100.,105.])
        self.assertEqual(result['retry_failed_time'],result['reentry_time'])


class FillSynchronizationTest(unittest.TestCase):
    def layer(self, volume=1, price=100., *, day='2026-10-13', synced=False):
        from qmt_roll_portfolio_strategy import PositionLayer
        return PositionLayer(kind='base', direction='long', volume=volume, entry_price=price,
            stop_price=90., highest_price=101., lowest_price=99., signal='long',
            entry_date=day, entry_price_synced=synced)

    def fill(self, price=102., volume=1, signal_day='2026-10-13'):
        item=trade();item.price=price;item.volume=volume
        item.signal_datetime=pd.Timestamp(signal_day).to_pydatetime()
        item.signal_order_id='BACKTESTING.1'
        return item

    def test_next_day_fill_syncs_signal_layer_without_changing_age(self):
        obj=strategy(bars());obj.state.layers=[self.layer()];obj.state.bars_since_entry=7
        obj._sync_open_trade(self.fill())
        layer=obj.state.layers[0]
        self.assertEqual((layer.entry_price,layer.entry_price_synced),(102.,True))
        self.assertEqual((layer.entry_date,obj.state.bars_since_entry),('2026-10-13',7))

    def test_next_day_fill_accepts_native_compact_date_without_rewriting_it(self):
        obj=strategy(bars());obj.state.layers=[self.layer(day='20261013')]
        obj._sync_open_trade(self.fill())
        self.assertEqual((obj.state.layers[0].entry_price,obj.state.layers[0].entry_date),(102.,'20261013'))

    def test_partial_fills_split_only_pending_signal_batch(self):
        obj=strategy(bars());old=self.layer(2,80.,day='2026-10-09',synced=True)
        unrelated=self.layer(4,70.,day='2026-10-12')
        obj.state.layers=[old,unrelated,self.layer(3)]
        obj._sync_open_trade(self.fill(102.,1))
        self.assertEqual(sorted((x.volume,x.entry_price,x.entry_price_synced) for x in obj.state.layers),
                         [(1,102.,True),(2,80.,True),(2,100.,False),(4,70.,False)])
        obj._sync_open_trade(self.fill(105.,2))
        self.assertEqual(sorted((x.volume,x.entry_price,x.entry_price_synced) for x in obj.state.layers),
                         [(1,102.,True),(2,80.,True),(2,105.,True),(4,70.,False)])
        self.assertEqual(old.entry_date,'2026-10-09')

    def diagnostic(self, day, volume):
        return dict(datetime=pd.Timestamp(day), selected_volume=volume, volume=volume,
            filled_entry_price=None, entry_price=100., stop_price=90., size=10,
            margin_ratio=.1,total_margin_in_use_before=200.)

    def test_partial_diagnostic_tracks_actual_volume_and_weighted_fill(self):
        obj=strategy(bars());old=self.diagnostic('2026-10-12',2);row=self.diagnostic('2026-10-13',3)
        obj.entry_risk_diagnostics=[old,row]
        obj.pending_entry_diagnostics={('cu2611.SHFE','long'):[0,1]}
        obj._sync_entry_risk_diagnostic(self.fill(102.,1))
        self.assertEqual(row['filled_entry_price'],102.)
        self.assertEqual(row['actual_filled_volume'],1)
        self.assertEqual(row['actual_risk_amount'],120.)
        self.assertAlmostEqual(row['actual_margin_amount'],102.)
        obj._sync_entry_risk_diagnostic(self.fill(105.,2))
        self.assertEqual(row['filled_entry_price'],104.)
        self.assertEqual(row['actual_filled_volume'],3)
        self.assertEqual(row['actual_risk_amount'],420.)
        self.assertAlmostEqual(row['actual_margin_amount'],312.)
        self.assertAlmostEqual(row['projected_total_margin_after'],512.)
        self.assertIsNone(old['filled_entry_price'])
        self.assertEqual(obj.pending_entry_diagnostics[('cu2611.SHFE','long')],[0])

    def test_rollover_diagnostic_completion_uses_final_volume_not_risk_recommendation(self):
        obj=strategy(bars());row=self.diagnostic('2026-10-13',3);row['selected_volume']=5
        obj.entry_risk_diagnostics=[row];obj.pending_entry_diagnostics={('cu2611.SHFE','long'):[0]}
        obj._sync_entry_risk_diagnostic(self.fill(102.,3))
        self.assertEqual((row['actual_filled_volume'],row['volume'],row['selected_volume']),(3,3,5))
        self.assertNotIn(('cu2611.SHFE','long'),obj.pending_entry_diagnostics)
        self.assertEqual(row['actual_risk_amount'],360.)

    def test_partial_fill_layer_and_diagnostic_use_same_signal_batch_order(self):
        obj=strategy(bars());older=self.layer();older.stop_price=80.;newer=self.layer(2)
        obj.state.layers=[older,newer]
        old_row=self.diagnostic('2026-10-13',1);old_row['stop_price']=80.
        new_row=self.diagnostic('2026-10-13',2)
        obj.entry_risk_diagnostics=[old_row,new_row]
        obj.pending_entry_diagnostics={('cu2611.SHFE','long'):[0,1]}
        item=self.fill(102.,1);obj._sync_open_trade(item);obj._sync_entry_risk_diagnostic(item)
        self.assertFalse(older.entry_price_synced)
        self.assertIsNone(old_row['filled_entry_price'])
        self.assertEqual(new_row['filled_entry_price'],102.)
        self.assertEqual(new_row['actual_risk_amount'],120.)

    def test_retry_keeps_episode_layer_identity_after_unrelated_insert(self):
        obj=strategy(bars(('2026-10-14 09:00',100,101,94,96),('2026-10-14 09:01',102,103,99,102)))
        original=self.layer(synced=True);obj.state.layers=[original]
        event=obj.stage827_intraday_exit_after_open_trade(trade())
        unrelated=self.layer(2,80.,day='2026-10-09',synced=True)
        obj.state.layers.insert(0,unrelated)
        obj._stage827_finalize_intraday_action(event,event['synthetic_trades'][1],final=True)
        self.assertEqual((original.entry_price,unrelated.entry_price),(102.,80.))
        self.assertEqual(original.entry_date,'2026-10-13')

    def test_retry_does_not_consume_ordinary_pending_layer_or_diagnostic(self):
        obj=strategy(bars());pending=self.layer(day='2026-10-14');obj.state.layers=[pending]
        row=self.diagnostic('2026-10-14',1);obj.entry_risk_diagnostics=[row]
        obj.pending_entry_diagnostics={('cu2611.SHFE','long'):[0]}
        item=self.fill(104.,signal_day='2026-10-14');item.intraday_episode_id='BACKTESTING.original-fill'
        obj._sync_open_trade(item);obj._sync_entry_risk_diagnostic(item)
        self.assertEqual((pending.entry_price,pending.entry_price_synced),(100.,False))
        self.assertIsNone(row['filled_entry_price'])

    def test_ordinary_engine_attaches_signal_batch(self):
        eng=EngineExecutionTest().engine();order=eng.make_order('cu2611.SHFE',1)
        eng._fill_order(order,eng.bars[order.vt_symbol]);item=eng.seen[0]
        self.assertEqual(getattr(item,'signal_datetime',None),datetime(2026,10,13))
        self.assertEqual(getattr(item,'signal_order_id',None),order.vt_orderid)

    def test_synthetic_engine_attaches_episode_identity(self):
        eng=EngineExecutionTest().engine();order=eng.make_order('cu2611.SHFE',1);opening=trade()
        event={'vt_symbol':order.vt_symbol,'trading_date':'2026-10-14','volume':1,
            'synthetic_trades':[dict(action='open',source='retry',price=102.,volume=1,time='2026-10-14 09:01')]}
        eng._fill_synthetic_intraday_close(order,opening,event)
        self.assertEqual(getattr(eng.seen[0],'intraday_episode_id',None),opening.vt_tradeid)


    def test_stale_synthetic_episode_fails_before_mutation(self):
        obj=strategy(bars(('2026-10-14 09:00',100,101,94,96)))
        event=obj.stage827_intraday_exit_after_open_trade(trade())
        obj.state.layers=[]
        with self.assertRaisesRegex(ValueError,'intraday_stale_episode'):
            obj._stage827_finalize_intraday_action(event,event['synthetic_trades'][0],final=True)

    def test_empty_exception_cannot_be_reported_as_completed_replay(self):
        from unittest.mock import patch
        eng=EngineExecutionTest().engine();order=eng.make_order('cu2611.SHFE',1)
        eng.active_limit_orders={order.vt_orderid:order}
        def fail(*args):
            raise AssertionError()
        eng._stage827_order_context=fail
        with self.assertRaises(AssertionError):
            eng.cross_delayed_orders()
        with patch.object(c2.Stage827IntradayC2Engine.__bases__[0],'run_backtesting',return_value=None):
            with self.assertRaises(RuntimeError):
                eng.run_backtesting()


class HistoricalTickTest(unittest.TestCase):
    def test_lithium_tick_boundary_preserves_other_execution_specs(self):
        self.assertEqual(c2.execution.effective_pricetick('lc2407.GFEX','2024-05-31',20.),50.)
        self.assertEqual(c2.execution.effective_pricetick('lc2501.GFEX','2024-12-17',20.),50.)
        self.assertEqual(c2.execution.effective_pricetick('lc2501.GFEX','2024-12-18',20.),20.)
        self.assertEqual(c2.execution.effective_pricetick('cu2501.SHFE','2024-12-17',10.),10.)

    def test_historical_lithium_buy_stop_uses_50_tick(self):
        obj=strategy(bars(),short=True,tick=20.)
        obj.state.contract_vt_symbol='lc2407.GFEX';obj.state.product_vt_symbol='lc.GFEX'
        obj.state.layers[0].stop_price=113760.;obj.state.layers[0].entry_price=100000.
        obj.available_trade_dates=pd.to_datetime(['2024-05-30','2024-05-31'])
        obj.stage827_minute_by_symbol={'lc2407.GFEX':bars(('2024-05-31 09:00',100000,107000,99950,106900))}
        item=TradeData(symbol='lc2407',exchange=Exchange.GFEX,orderid='1',tradeid='1',
            direction=Direction.SHORT,offset=Offset.OPEN,price=100000.,volume=1,
            datetime=datetime(2024,5,31,9),gateway_name='BACKTESTING')
        item.execution_datetime=item.datetime;item.trading_date=datetime(2024,5,31).date()
        result=obj.stage827_intraday_exit_after_open_trade(item)
        self.assertEqual(result['stop_price'],106880.)
        self.assertEqual(result['synthetic_trades'][0]['price'],106900.)
        self.assertEqual(result['effective_tick'],50.)


class CanonicalOpenAnchorTest(unittest.TestCase):
    def engine(self, *, include_anchor=True, strict=True, closing=False):
        from vnpy.trader.object import BarData, OrderData
        from vnpy.trader.constant import Status
        eng=EngineExecutionTest().engine();symbol='SH601.CZCE'
        eng.datetime=datetime(2025,8,25);eng.priceticks={symbol:1.}
        eng.strategy.available_trade_dates=pd.to_datetime(['2025-08-21','2025-08-22','2025-08-25'])
        rows=[('2025-08-25 09:00',2741,2742,2740,2741)]
        if include_anchor:
            rows.insert(0,('2025-08-22 21:00',2745,2746,2744,2745))
        eng.strategy.stage827_minute_by_symbol={symbol:bars(*rows)}
        eng.strategy.stage827_require_complete_minutes=strict
        bar=BarData(symbol='SH601',exchange=Exchange.CZCE,datetime=eng.datetime,
            open_price=2745,high_price=2750,low_price=2700,close_price=2730,gateway_name='BACKTESTING')
        eng.bars={symbol:bar}
        order=OrderData(symbol='SH601',exchange=Exchange.CZCE,orderid='1',
            direction=Direction.SHORT if closing else Direction.LONG,
            offset=Offset.CLOSE if closing else Offset.OPEN,price=2740,volume=1,status=Status.SUBMITTING,
            datetime=datetime(2025,8,22),gateway_name='BACKTESTING')
        eng._resolve_trade_price=lambda order,bar:(2741.,'legacy_next_real_open',{'proxy_first_time':'2025-08-25 09:00'})
        return eng,order,bar

    def test_weekend_sh_open_and_close_use_canonical_night_anchor(self):
        for closing in (False,True):
            eng,order,bar=self.engine(closing=closing)
            eng._fill_order(order,bar)
            self.assertEqual((eng.seen[0].datetime,eng.seen[0].price),(datetime(2025,8,22,21),2745.))
            self.assertEqual(eng.trade_usage_rows[0]['anchor_coverage_status'],'complete')
            self.assertTrue(eng.execution_anchor_requests[0]['anchor_present'])

    def test_late_proxy_is_not_a_verified_anchor_when_first_minute_is_missing(self):
        eng,order,bar=self.engine(include_anchor=False)
        with self.assertRaisesRegex(ValueError,'intraday_open_anchor_missing'):
            eng._fill_order(order,bar)
        self.assertFalse(eng.execution_anchor_requests[-1]['anchor_present'])
        self.assertEqual(eng.seen,[])

    def test_diagnostic_missing_anchor_is_explicitly_incomplete(self):
        eng,order,bar=self.engine(include_anchor=False,strict=False)
        eng._fill_order(order,bar)
        self.assertEqual(eng.trade_usage_rows[0].get('anchor_coverage_status'),'incomplete')
        self.assertFalse(eng.execution_anchor_requests[-1]['anchor_present'])


class RealFillSynchronizationTest(unittest.TestCase):
    def test_real_engine_callback_syncs_layer_and_diagnostic_with_signal_identity(self):
        from unittest.mock import patch
        import qmt_roll_portfolio_strategy as base
        eng=EngineExecutionTest().engine();calendar=eng.strategy.available_trade_dates
        eng.capital=150000.;eng.sizes={symbol:10 for symbol in eng.priceticks}
        eng.rates={symbol:0 for symbol in eng.priceticks};eng.slippages=dict(eng.rates)
        metadata={'product_symbols':[], 'source_symbol_by_contract':{'cu2611.SHFE':'cu.SHFE'}}
        with patch.object(base,'load_product_universe_symbols',return_value=[]), \
             patch.object(base,'build_daily_mapping',return_value={}), \
             patch.object(base,'build_contract_metadata',return_value=metadata):
            obj=c9.QmtRollPortfolioStrategyStage847C9StopRetry(eng,'fill-integration',list(eng.priceticks),{'capital_base':150000.})
        eng.strategy=obj;obj.available_trade_dates=calendar;obj.stage827_require_complete_minutes=False
        obj.enable_stage827_intraday_c2_stop=False;obj.enable_stage847_half_r_stop_retry=False
        from vnpy.trader.object import BarData
        state=base.ProductState(product_vt_symbol='cu.SHFE');obj.states={'cu.SHFE':state}
        signal_bar=BarData(symbol='cu2611',exchange=Exchange.SHFE,datetime=datetime(2026,10,13),
            open_price=100.,high_price=101.,low_price=99.,close_price=100.,gateway_name='BACKTESTING')
        obj._open_position(state,'cu2611.SHFE','long',1,signal_bar,'long',pd.DataFrame(),{},
            sizing_snapshot={'stop_price':90.,'selected_volume':1,'margin_ratio':.1})
        layer=state.layers[0];row=obj.entry_risk_diagnostics[0]
        state.bars_since_entry=7
        self.assertEqual(layer.entry_date,'20261013')
        obj.trading=True;eng.datetime=signal_bar.datetime
        obj._apply_state_target(state)
        obj.rebalance_portfolio({'cu2611.SHFE':signal_bar})
        order=next(iter(eng.active_limit_orders.values()))
        eng.datetime=datetime(2026,10,14)
        eng._resolve_trade_price=lambda order,bar:(102.,'raw_test_first_open',{'proxy_first_time':'2026-10-13 21:00'})
        eng._fill_order(order,eng.bars[order.vt_symbol])
        self.assertEqual(obj.pos_data['cu2611.SHFE'],1)
        self.assertEqual((layer.entry_price,layer.entry_price_synced,layer.entry_date),(102.,True,'20261013'))
        self.assertEqual((row['filled_entry_price'],row['actual_filled_volume']),(102.,1))
        self.assertEqual(obj.states['cu.SHFE'].bars_since_entry,7)


if __name__ == '__main__':
    unittest.main()
