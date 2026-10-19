"""Synthetic execution regressions. No market load, replay, or production I/O."""
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
from vnpy.trader.setting import SETTINGS
SETTINGS['log.file']=False
from stage003_candidate import FullMarketNoAIOneLot
from stage004_run import FeeStrategy,FullMarketDailyEngine
from qmt_roll_portfolio_strategy import ProductState,PositionLayer
from vnpy_portfoliostrategy.template import StrategyTemplate
from vnpy.trader.constant import Exchange,Direction,Offset,Status
from vnpy.trader.object import BarData,OrderData,TradeData

OLD='rb201905.SHFE'
NEW='i201909.DCE'
SIGNAL=datetime(2019,4,2)
FILL=datetime(2019,4,3)


def bar(vt,*,open_price=100,close_price=100):
    symbol,exchange=vt.split('.')
    return BarData(symbol=symbol,exchange=Exchange(exchange),datetime=FILL,
                   open_price=open_price,high_price=max(open_price,close_price),
                   low_price=min(open_price,close_price),close_price=close_price,
                   volume=10,gateway_name='SYNTHETIC')


def order(vt=NEW):
    symbol,exchange=vt.split('.')
    return OrderData(symbol=symbol,exchange=Exchange(exchange),orderid='1',
                     direction=Direction.LONG,offset=Offset.OPEN,volume=1,
                     price=100,status=Status.SUBMITTING,datetime=SIGNAL,
                     gateway_name='BACKTESTING')


class MinimalStrategy(StrategyTemplate):
    def on_init(self):pass
    def on_bars(self,bars):pass


class ExecutionRegressions(unittest.TestCase):
    def opening_outcome(self,close):
        e=FullMarketDailyEngine({});e.datetime=FILL
        s=MinimalStrategy(e,'synthetic',[OLD,NEW],{});e.strategy=s
        s.source_symbol_by_contract={OLD:'rb.SHFE',NEW:'i.DCE'}
        s.pos_data[OLD]=1;s.estimated_equity=1000;s.settled_balance=1000
        s.equity_start_positions={OLD:1};s.last_close_prices={OLD:100}
        s.stage830_broker_margin_multiplier=1
        s.stage830_projected_broker10_margin_to_equity_cap=1
        s.max_concurrent_positions=4
        e.bars={OLD:bar(OLD,close_price=close),NEW:bar(NEW)}
        e.history_data={(FILL,vt):b for vt,b in e.bars.items()}
        e.sizes={OLD:10,NEW:10};e.rates={OLD:0,NEW:0};e.slippages={OLD:0,NEW:0}
        e.research_metadata={vt:dict(size=10,margin_ratio=.1,fee_method='by_volume',
            fee_open=0,fee_close=0,fee_close_today=0) for vt in [OLD,NEW]}
        o=order();e.active_limit_orders={o.vt_orderid:o};e.limit_orders={o.vt_orderid:o}
        # Existing code has no opening snapshot; still exercise its behavior for RED.
        prepare=getattr(e,'prepare_opening_risk',None)
        if prepare is not None:prepare(FILL)
        e.cross_delayed_orders()
        return s.get_pos(NEW),[r['reason'] for r in e.blocked_open_orders]

    def test_opening_fill_ignores_later_close_of_existing_position(self):
        low_close=self.opening_outcome(100)
        high_close=self.opening_outcome(1000)
        self.assertEqual(low_close,(1,[]))
        self.assertEqual(high_close,low_close,
                         'same opening information must produce same opening fill')

    def test_next_day_fill_binds_signal_order_and_updates_layer_entry(self):
        e=FullMarketDailyEngine({});e.datetime=FILL
        e.sizes={OLD:10};e.priceticks={OLD:1};e.slippages={OLD:0}
        e.research_metadata={OLD:dict(size=10,margin_ratio=.1,fee_method='by_volume',
            fee_open=0,fee_close=0,fee_close_today=0)}
        e.bars={OLD:bar(OLD,open_price=120,close_price=125)}
        o=order(OLD);e.limit_orders={o.vt_orderid:o};e.current_fill_order=o
        s=object.__new__(FeeStrategy);s.strategy_engine=e;e.strategy=s
        s.pos_data=defaultdict(int);s.equity_start_positions={};s.last_close_prices={OLD:100}
        s.equity_settlement_date='2019-04-02';s.settled_balance=10000
        s.base_capital=10000;s.estimated_equity=10000;s.trade_costs_total=0
        s.source_symbol_by_contract={OLD:'rb.SHFE'};s.pending_entry_diagnostics={}
        layer=PositionLayer('base','long',1,100,95,100,100,'long_case1a','20190402')
        s.states={'rb.SHFE':ProductState(product_vt_symbol='rb.SHFE',
            contract_vt_symbol=OLD,direction='long',layers=[layer])}
        t=TradeData(symbol='rb201905',exchange=Exchange.SHFE,orderid='1',tradeid='1',
                    direction=Direction.LONG,offset=Offset.OPEN,price=120,volume=1,
                    datetime=FILL,gateway_name='BACKTESTING')
        s.update_trade(t)
        self.assertEqual(layer.entry_price,120,'layer must use the actual next-open fill')
        self.assertTrue(layer.entry_price_synced)
        self.assertEqual(getattr(t,'signal_datetime',None),SIGNAL)
        self.assertEqual(s.get_pos(OLD),1)

    def test_repeated_unfilled_close_keeps_one_pending_lot(self):
        new_same='rb201910.SHFE'
        s=object.__new__(FullMarketNoAIOneLot)
        s.source_symbol_by_contract={OLD:'rb.SHFE',new_same:'rb.SHFE'}
        s.pos_data={OLD:1,new_same:0};s.target_data=defaultdict(int)
        s.pending_close_lots={};s.pending_close_reasons={}
        s.realized_pnl=0;s.trade_event_diagnostics=[]
        s.get_size=lambda vt:10;s._margin_ratio_for_symbol=lambda vt:.1
        # Isolate queue idempotence while observing outcome side effects.
        s._record_product_direction_outcome=lambda *args,**kwargs:None
        streak_calls=[]
        s._update_streak_risk_state=lambda *args,**kwargs:streak_calls.append(args)
        cached=bar(OLD,open_price=110,close_price=110)
        s.strategy_engine=SimpleNamespace(bars={OLD:cached})
        state=ProductState(product_vt_symbol='rb.SHFE',contract_vt_symbol=OLD,
            direction='long',layers=[PositionLayer('base','long',1,100,95,110,100,
                                                 'long_case1a','20190301')])
        s.states={'rb.SHFE':state}
        for _ in range(2):
            s._close_position_when_target_unavailable('rb.SHFE',state=state,
                target_contract=new_same,bars={},reason='rollover_close_missing_target_bar')
        self.assertEqual(s.pos_data[OLD],1)
        self.assertEqual(sum(x['volume'] for x in s.pending_close_lots[OLD]),1,
                         'one actual lot cannot create repeated pending close lots')
        self.assertEqual(len(streak_calls),1)
        self.assertEqual(s.get_target(OLD),0)


    def test_execution_only_quote_cannot_fill_prior_day_open(self):
        e=FullMarketDailyEngine({});e.datetime=FILL
        s=MinimalStrategy(e,'synthetic',[NEW],{});e.strategy=s
        s.source_symbol_by_contract={NEW:'i.DCE'}
        b=bar(NEW);b.execution_only=True
        e.bars={NEW:b};e.history_data={(FILL,NEW):b}
        o=order();e.active_limit_orders={o.vt_orderid:o}
        e.cross_delayed_orders()
        self.assertEqual(s.get_pos(NEW),0)
        self.assertFalse(e.trades)
        self.assertEqual(e.blocked_open_orders[-1]['reason'],
                         'execution_only_quote_no_new_open')

    def accounting_strategy(self):
        e=FullMarketDailyEngine({});e.datetime=FILL
        e.sizes={OLD:10,NEW:10};e.priceticks={OLD:1,NEW:1}
        e.slippages={OLD:0,NEW:0};e.rates={OLD:0,NEW:0}
        metadata=dict(product_symbols=[],source_symbol_by_contract={OLD:'rb.SHFE',NEW:'i.DCE'})
        # Replace only external input loaders; execute real strategy accounting.
        with patch('qmt_roll_portfolio_strategy.load_product_universe_symbols',return_value=set()), \
             patch('qmt_roll_portfolio_strategy.build_daily_mapping',return_value={}), \
             patch('qmt_roll_portfolio_strategy.build_contract_metadata',return_value=metadata):
            s=FeeStrategy(e,'synthetic',[OLD,NEW],dict(capital_base=1000,
                enable_ai_product_pool_filter=False,enable_selection_pairwise_v2=False,
                enable_supply_demand_headwind_filter=False))
        e.strategy=s;s.pos_data[OLD]=1;s.equity_start_positions={OLD:1}
        s.settled_balance=1000;s.estimated_equity=1000
        s.last_close_prices={OLD:100};s.equity_settlement_date='2019-04-02'
        return e,s

    def test_execution_only_holding_leg_is_settled_once(self):
        e,s=self.accounting_strategy()
        quote=bar(OLD,close_price=110);quote.execution_only=True
        normal=bar(NEW)
        e.bars={OLD:quote,NEW:normal}
        s.on_bars(e.bars)
        self.assertEqual(s.estimated_equity,1100)
        self.assertEqual(s.settled_balance,1100)
        self.assertEqual(s.last_close_prices[OLD],110)
        self.assertEqual(s.ams[OLD].count,0,'execution-only quote must not feed indicators')
        tomorrow=bar(NEW);tomorrow.datetime=datetime(2019,4,4)
        e.datetime=tomorrow.datetime;e.bars[NEW]=tomorrow
        s.on_bars({NEW:tomorrow})
        self.assertEqual(s.estimated_equity,1100,'holding PNL cannot be booked twice')
        self.assertEqual(s.settled_balance,1100)


    def test_execution_only_close_preserves_holding_and_trading_legs(self):
        e,s=self.accounting_strategy()
        quote=bar(OLD,open_price=105,close_price=110);quote.execution_only=True
        e.bars={OLD:quote,NEW:bar(NEW)}
        e.history_data={(FILL,OLD):quote}
        e.research_metadata={OLD:dict(size=10,margin_ratio=.1,fee_method='by_volume',
            fee_open=0,fee_close=0,fee_close_today=0)}
        o=order(OLD);o.direction=Direction.SHORT;o.offset=Offset.CLOSE
        e.limit_orders={o.vt_orderid:o};e.active_limit_orders={o.vt_orderid:o}
        e.prepare_opening_risk(FILL)
        e.cross_delayed_orders()
        self.assertEqual(s.get_pos(OLD),0)
        s.on_bars(e.bars)
        self.assertEqual(s.estimated_equity,1050)
        self.assertEqual(s.settled_balance,1050)
        self.assertEqual(s.ams[OLD].count,0)
        tomorrow=bar(NEW);tomorrow.datetime=datetime(2019,4,4)
        e.datetime=tomorrow.datetime;e.bars[NEW]=tomorrow
        s.on_bars({NEW:tomorrow})
        self.assertEqual(s.estimated_equity,1050)


    def test_stale_open_without_matching_pending_layer_never_fills(self):
        for invalid in ['empty_state','wrong_direction','already_synced','ambiguous_layers']:
            with self.subTest(invalid=invalid):
                e,s=self.accounting_strategy()
                s.pos_data=defaultdict(int);s.equity_start_positions={}
                s.target_data[NEW]=1
                state=ProductState(product_vt_symbol='i.DCE')
                if invalid!='empty_state':
                    direction='short' if invalid=='wrong_direction' else 'long'
                    state.contract_vt_symbol=NEW;state.direction=direction
                    state.layers=[PositionLayer('base',direction,1,100,95,100,100,
                        'long_case1a','20190402',entry_price_synced=invalid=='already_synced')]
                    if invalid=='ambiguous_layers':
                        state.layers.append(PositionLayer('base','long',1,100,95,100,100,
                                                          'long_case1a','20190401'))
                s.states={'i.DCE':state}
                e.bars={NEW:bar(NEW,open_price=120,close_price=120)}
                e.history_data={(FILL,NEW):e.bars[NEW]}
                e.research_metadata={NEW:dict(size=10,margin_ratio=.1,
                    fee_method='by_volume',fee_open=0,fee_close=0,fee_close_today=0)}
                o=order();e.limit_orders={o.vt_orderid:o};e.active_limit_orders={o.vt_orderid:o}
                e.prepare_opening_risk(FILL)
                try:
                    e.cross_delayed_orders()
                except ValueError:
                    # The failing implementation mutates actual pos before sync rejects it.
                    pass
                self.assertEqual(s.get_pos(NEW),0,
                                 'stale open must be rejected before actual position mutation')
                self.assertFalse(e.trades)
                self.assertEqual(s.get_target(NEW),0,'stale target must not revive tomorrow')
                self.assertNotIn(o.vt_orderid,e.active_limit_orders,'stale order must be cancelled')
                self.assertEqual(e.blocked_open_orders[-1]['reason'],'stale_open_intent')

    def test_reissued_valid_open_keeps_unique_original_layer_signal(self):
        e,s=self.accounting_strategy()
        s.pos_data=defaultdict(int);s.equity_start_positions={}
        original_signal=datetime(2019,4,1)
        layer=PositionLayer('base','long',1,100,95,100,100,'long_case1a','20190401')
        s.states={'rb.SHFE':ProductState(product_vt_symbol='rb.SHFE',
            contract_vt_symbol=OLD,direction='long',layers=[layer])}
        e.bars={OLD:bar(OLD,open_price=120,close_price=125)}
        e.research_metadata={OLD:dict(size=10,margin_ratio=.1,
            fee_method='by_volume',fee_open=0,fee_close=0,fee_close_today=0)}
        o=order(OLD);e.limit_orders={o.vt_orderid:o};e.current_fill_order=o
        t=TradeData(symbol='rb201905',exchange=Exchange.SHFE,orderid='1',tradeid='1',
            direction=Direction.LONG,offset=Offset.OPEN,price=120,volume=1,
            datetime=FILL,gateway_name='BACKTESTING')
        try:
            s.update_trade(t)
        except ValueError:
            pass
        self.assertEqual(layer.entry_price,120,'reissue date must not replace original layer signal date')
        self.assertTrue(layer.entry_price_synced)
        self.assertEqual(getattr(t,'signal_datetime',None),original_signal)
        self.assertEqual(getattr(t,'order_reissue_datetime',None),SIGNAL)
        self.assertEqual(s.get_pos(OLD),1)

    def test_only_execution_quote_batch_still_settles_holding_leg(self):
        e,s=self.accounting_strategy()
        quote=bar(OLD,close_price=110);quote.execution_only=True
        e.bars={OLD:quote}
        s.on_bars(e.bars)
        self.assertEqual(s.estimated_equity,1100)
        self.assertEqual(s.settled_balance,1100)
        self.assertEqual(s.last_close_prices[OLD],110)
        self.assertEqual(s.equity_settlement_date,'2019-04-03')
        self.assertEqual(s.ams[OLD].count,0)


if __name__=='__main__':unittest.main()
