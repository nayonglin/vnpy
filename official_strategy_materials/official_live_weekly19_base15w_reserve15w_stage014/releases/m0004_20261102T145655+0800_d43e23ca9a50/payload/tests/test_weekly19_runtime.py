"""Offline fixtures; no broker/provider or production qualification is asserted."""
import copy
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest
from zoneinfo import ZoneInfo

import pandas as pd
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import BarData

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'examples/portfolio_backtesting'))
try:
    import qmt_roll_weekly19_runtime as runtime
except ModuleNotFoundError as exc:
    if exc.name != 'qmt_roll_weekly19_runtime':
        raise
    runtime = None
import qmt_roll_weekly19_funding as funding

NOW = datetime(2026, 10, 30, 15, 15, tzinfo=ZoneInfo('Asia/Shanghai'))
ACCOUNT = hashlib.sha256(b'9999\0fixture-account').hexdigest()
RELEASE = 'weekly19-runtime-fixture'
SYMBOL = 'rb2612.SHFE'


def envelope(raw):
    text = json.dumps(raw, sort_keys=True, separators=(',', ':'))
    return dict(raw_payload=text, raw_sha256=hashlib.sha256(text.encode()).hexdigest())


def broker(balance='150000.00', available='150000.00', positions=None, now=NOW, day='2026-10-30'):
    common = dict(account_key=ACCOUNT, material_release_id=RELEASE, observed_at=now.isoformat(),
                  trading_day=day, generation_uuid='fixture-query', query_reqid=1, query_complete=True)
    return dict(account=envelope(dict(common, schema='weekly19.ctp-account.v1',
        source_kind='ctp_account_callback', BrokerID='9999', AccountID='fixture-account',
        CurrencyID='CNY', Balance=balance, Available=available, Deposit='0.00', Withdraw='0.00')),
        positions=envelope(dict(common, schema='weekly19.ctp-positions.v1',
        source_kind='ctp_position_query', positions=[] if positions is None else positions)))


def fixture():
    products = ['AP.CZCE', 'CF.CZCE', 'FG.CZCE', 'MA.CZCE', 'OI.CZCE', 'SA.CZCE', 'SH.CZCE',
                'SM.CZCE', 'au.SHFE', 'cu.SHFE', 'fu.SHFE', 'hc.SHFE', 'jm.DCE', 'lc.GFEX',
                'lh.DCE', 'rb.SHFE', 'ru.SHFE', 'si.GFEX', 'sp.SHFE']
    symbols = {p: p.replace('.', '612.' if p.endswith('CZCE') else '2612.') for p in products}
    calendar = pd.bdate_range('2026-05-04', '2026-11-06').strftime('%Y-%m-%d').tolist()
    days = [d for d in calendar if d <= '2026-10-30']
    rows = []
    bars = {}
    for i, day in enumerate(days):
        price = 101.0 if day >= '2026-10-26' else 100.0
        b = BarData(symbol='rb2612', exchange=Exchange.SHFE, datetime=pd.Timestamp(day).to_pydatetime(),
                    gateway_name='FIXTURE', interval=Interval.DAILY,
                    open_price=price, high_price=price + .5, low_price=price - .5,
                    close_price=price, volume=1000, open_interest=2000)
        bars[day] = {SYMBOL: b}
        rows.append(dict(vt_symbol=SYMBOL, date=day, contract_epoch_id='rb2612-physical',
                         open=price, high=price + .5, low=price - .5, close=price, volume=1000, close_oi=2000.0))
    meta = dict(vt_symbols=list(symbols.values()), product_symbols=products,
                source_symbol_by_contract={s:p for p,s in symbols.items()},
                daily_mapping={d: dict(symbols) for d in days},
                sizes={s:10 for s in symbols.values()}, priceticks={s:1.0 for s in symbols.values()},
                margin_ratios={s:.1 for s in symbols.values()}, rates={s:0.0 for s in symbols.values()},
                slippages={s:0.0 for s in symbols.values()}, source_sha256='a'*64)
    return calendar, pd.DataFrame(rows), bars, meta


def build(evidence=None, durable=None, funds_state=None, now=NOW):
    calendar, epochs, bars, meta = fixture()
    obj = runtime.build_weekly19_runtime(runtime.DEFAULT_SETTINGS_ASSET, meta, calendar, epochs,
        broker() if evidence is None else evidence, durable,
        funding.initial_state(ACCOUNT, RELEASE, '2026-10-30') if funds_state is None else funds_state, clock=lambda: now)
    return obj, bars


def receipt(day='2026-10-30'):
    return dict(schema='weekly19.data-receipt.v1', trading_date=day, complete=True,
                material_release_id=RELEASE, source_sha256='b'*64)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(runtime, 'weekly19 runtime has not been implemented')

    def ready(self, evidence=None):
        obj, bars = build(evidence)
        obj.warmup([bars[d] for d in sorted(bars) if d < '2026-10-30'])
        return obj, bars

    def test_pure_warmup_has_no_targets_positions_funding_or_strategy_state(self):
        obj, bars = self.ready()
        self.assertEqual(obj.strategy.get_pos(SYMBOL), 0)
        self.assertFalse(any(obj.strategy.target_data.values()))
        self.assertFalse(any(s.layers for s in obj.strategy.states.values()))
        self.assertEqual(obj.confirmed_cash_state['requests'], {})
        self.assertEqual(obj.engine.intents, [])
        self.assertGreaterEqual(obj.strategy.ams[SYMBOL].count, 21)

    def test_actual_mro_and_original_protection_guards_are_retained(self):
        obj, _ = build()
        names = [c.__name__ for c in type(obj.strategy).__mro__]
        for name in ['HistoricalSafetyStrategy', 'ShortBottom20RangeStrategy', 'WeekCloseExitStrategyV2',
                     'NoMacdThreeMaWeeklyIndicatorsStrategy', 'QmtRollPortfolioStrategyStage827C2']:
            self.assertIn(name, names)
        self.assertNotIn('ReserveTopupStrategy', names)
        self.assertFalse(obj.strategy.research_daily_addon_enabled)
        self.assertFalse(obj.strategy._can_open_short_signal('short_case2'))

    def test_native_admission_recommends_before_parent_sizing_without_cash_injection(self):
        obj, bars = self.ready(broker(balance='120000.00', available='0.00'))
        decision = obj.process_completed_day('2026-10-30', bars['2026-10-30'], receipt(),
                                             broker(balance='120000.00', available='0.00'), obj.confirmed_cash_state)
        self.assertTrue(decision['funding_admitted_ids'])
        self.assertEqual(decision['funding_recommendation']['amount_fen'], 3000000)
        self.assertEqual(obj.strategy.estimated_equity, 120000.0)
        self.assertEqual(obj.strategy.settled_balance, 120000.0)
        self.assertFalse(any(x['offset']=='open' and x['executable'] for x in decision['intents']))
        self.assertFalse(any(obj.strategy.pos_data.values()))

    def test_same_day_replay_is_idempotent_and_conflicting_receipt_is_rejected(self):
        obj, bars = self.ready()
        first = obj.process_completed_day('2026-10-30', bars['2026-10-30'], receipt(), broker(), obj.confirmed_cash_state)
        before = obj.export_state()
        self.assertEqual(first['after_state_sha256'], before['state_sha256'])
        again = obj.process_completed_day('2026-10-30', bars['2026-10-30'], receipt(), broker(), obj.confirmed_cash_state)
        self.assertEqual(first, again)
        self.assertEqual(before, obj.export_state())
        with self.assertRaisesRegex(runtime.RuntimeContractError, 'day_receipt_conflict'):
            obj.process_completed_day('2026-10-30', bars['2026-10-30'], dict(receipt(), source_sha256='c'*64), broker(), obj.confirmed_cash_state)

    def test_nonpositive_broker_equity_does_not_fall_back_to_base_capital(self):
        obj, bars = self.ready(broker(balance='0.00'))
        result = obj.process_completed_day('2026-10-30', bars['2026-10-30'], receipt(), broker(balance='0.00'), obj.confirmed_cash_state)
        self.assertEqual(obj.strategy.estimated_equity, 0.0)
        self.assertFalse(any(x['offset']=='open' and x['executable'] for x in result['intents']))
        self.assertFalse(any(obj.strategy.target_data.values()))

    def test_unprotected_external_position_fails_closed(self):
        with self.assertRaisesRegex(runtime.RuntimeContractError, 'unprotected_broker_position'):
            build(broker(positions=[dict(vt_symbol=SYMBOL, direction='long', volume=1)]))

    def test_real_fill_and_restart_preserve_layer_weekly_and_account_state(self):
        obj, bars = self.ready()
        result = obj.process_completed_day('2026-10-30', bars['2026-10-30'], receipt(), broker(), obj.confirmed_cash_state)
        opening = next(x for x in result['intents'] if x['offset']=='open' and x['executable'])
        identity = dict(intent_id=opening['intent_id'], signal_order_id=opening['signal_order_id'],
                        signal_datetime=opening['signal_datetime'], trading_date='2026-11-02')
        fill = envelope(dict(schema='weekly19.ctp-trade.v1', source_kind='ctp_trade_callback',
            account_key=ACCOUNT, material_release_id=RELEASE, trade_id='fixture-trade-1',
            broker_order_id='fixture-broker-order-1', vt_symbol=SYMBOL, direction='long', offset='open',
            volume=1, price=101.5, trading_day='2026-11-02',
            execution_datetime='2026-10-30T21:00:01+08:00'))
        fill_now = NOW.replace(hour=21, minute=1)
        obj.clock = lambda: fill_now
        obj.apply_broker_fill(fill, identity)
        self.assertEqual(obj.strategy.get_pos(SYMBOL), 1)
        layer = next(x for x in obj.strategy.states['rb.SHFE'].layers if x.entry_price_synced)
        self.assertEqual(layer.entry_price, 101.5)
        self.assertEqual(obj.strategy.estimated_equity, 150000.0)
        fresh = broker(positions=[dict(vt_symbol=SYMBOL, direction='long', volume=1)], now=fill_now, day='2026-11-02')
        obj.reconcile_broker_snapshot(fresh, obj.confirmed_cash_state)
        state = obj.export_state()
        restored, _ = build(fresh, state, obj.confirmed_cash_state, now=fill_now)
        self.assertEqual(state, restored.export_state())
        self.assertEqual(obj.apply_broker_fill(fill, identity), restored.apply_broker_fill(fill, identity))
        self.assertEqual(restored.strategy.get_pos(SYMBOL), 1)
        altered = copy.deepcopy(state); altered['state_sha256'] = 'f'*64
        with self.assertRaisesRegex(runtime.RuntimeContractError, 'state_checksum'):
            build(durable=altered)

class RuntimePendingTests(unittest.TestCase):
    setUp = RuntimeTests.setUp
    ready = RuntimeTests.ready

    def test_cancelled_unfilled_open_removes_plan_without_creating_a_trade(self):
        obj, bars = self.ready()
        decision = obj.process_completed_day('2026-10-30', bars['2026-10-30'], receipt(), broker(), obj.confirmed_cash_state)
        opening = next(x for x in decision['intents'] if x.get('offset')=='open')
        event = envelope(dict(schema='weekly19.ctp-order.v1', source_kind='ctp_order_callback',
            account_key=ACCOUNT, material_release_id=RELEASE, signal_order_id=opening['signal_order_id'],
            event_id='cancel-1', status='cancelled', traded=0, broker_order_id='broker-1'))
        obj.apply_order_update(event)
        self.assertFalse(obj.strategy.states['rb.SHFE'].layers)
        self.assertEqual(obj.strategy.get_target(SYMBOL), 0)
        self.assertEqual(obj.strategy.get_pos(SYMBOL), 0)
        self.assertEqual(obj.broker_equity, 150000.0)
        saved = obj.export_state()
        restored, _ = build(broker(), saved, obj.confirmed_cash_state)
        self.assertEqual(saved, restored.export_state())

    def test_terminal_order_disagrees_with_actual_fill_total_is_rejected_atomically(self):
        obj, bars = self.ready()
        decision = obj.process_completed_day('2026-10-30', bars['2026-10-30'], receipt(), broker(), obj.confirmed_cash_state)
        opening = next(x for x in decision['intents'] if x.get('offset')=='open')
        event = envelope(dict(schema='weekly19.ctp-order.v1', source_kind='ctp_order_callback',
            account_key=ACCOUNT, material_release_id=RELEASE, signal_order_id=opening['signal_order_id'],
            event_id='bad-cancel', status='cancelled', traded=1, broker_order_id='broker-1'))
        before = obj.export_state()
        with self.assertRaisesRegex(runtime.RuntimeContractError, 'order_fill_total_mismatch'):
            obj.apply_order_update(event)
        self.assertEqual(before, obj.export_state())

class CloseLifecycleTests(unittest.TestCase):
    setUp = RuntimeTests.setUp

    def opened(self):
        obj, bars = RuntimeTests.ready(self)
        decision = obj.process_completed_day('2026-10-30', bars['2026-10-30'], receipt(), broker(), obj.confirmed_cash_state)
        plan = next(x for x in decision['intents'] if x.get('offset')=='open')
        obj.clock = lambda: NOW.replace(hour=21, minute=1)
        self.fill(obj, plan, plan['volume'], 101.5, 'opening')
        evidence = broker(positions=[dict(vt_symbol=SYMBOL,direction='long',volume=plan['volume'])],
                          now=obj.clock(), day='2026-11-02')
        obj.reconcile_broker_snapshot(evidence,obj.confirmed_cash_state)
        return obj,bars,plan['volume']

    def fill(self,obj,plan,volume,price,tid):
        obj.apply_broker_fill(envelope(dict(schema='weekly19.ctp-trade.v1',source_kind='ctp_trade_callback',
            account_key=ACCOUNT,material_release_id=RELEASE,trade_id=tid,broker_order_id='broker-'+plan['intent_id'],
            vt_symbol=SYMBOL,direction=plan['direction'],offset=plan['offset'],volume=volume,price=price,
            trading_day=plan['trading_date'],execution_datetime=obj.clock().isoformat())),plan['signal_identity'])

    def plan_close(self,obj,bars):
        # Exercise the original close primitive after a confirmed technical exit;
        # this fixture tests asynchronous ownership, not signal performance.
        state=obj.strategy.states['rb.SHFE']
        obj.strategy._close_all_layers_and_set_flat_target(state,100.0,exit_reason='long_base_stop')
        obj.strategy.rebalance_portfolio(bars['2026-10-30'])
        return next(x for x in reversed(obj.engine.intents) if x.get('offset')=='close')

    def test_partial_close_cancel_restart_retry_commits_actual_outcome_once(self):
        obj,bars,volume=self.opened()
        close=self.plan_close(obj,bars)
        self.assertEqual(obj.strategy.loss_streak,0)
        self.assertEqual(obj.strategy.realized_pnl,0)
        self.assertEqual(obj.strategy.states['rb.SHFE'].active_volume(),volume)
        self.fill(obj,close,1,100.0,'partial-close')
        self.assertEqual(obj.strategy.get_pos(SYMBOL),volume-1)
        self.assertEqual(obj.strategy.states['rb.SHFE'].active_volume(),volume-1)
        self.assertEqual(obj.strategy.loss_streak,0)
        self.assertEqual(obj.strategy.realized_pnl,-15.0)
        cancel=envelope(dict(schema='weekly19.ctp-order.v1',source_kind='ctp_order_callback',
            account_key=ACCOUNT,material_release_id=RELEASE,signal_order_id=close['signal_order_id'],
            event_id='close-cancel',status='cancelled',traded=1,broker_order_id='broker-'+close['intent_id']))
        obj.apply_order_update(cancel)
        snapshot=broker(balance='140000.00',positions=[dict(vt_symbol=SYMBOL,direction='long',volume=volume-1)],
                        now=obj.clock(),day='2026-11-02')
        result=obj.reconcile_broker_snapshot(snapshot,obj.confirmed_cash_state)
        self.assertFalse(result['retry_intents'][0]['executable'])
        saved=obj.export_state()
        restored,_=build(snapshot,saved,obj.confirmed_cash_state,now=obj.clock())
        self.assertEqual(saved,restored.export_state())
        quote=dict(symbol=SYMBOL,observed_at=obj.clock().isoformat(),bid=99.0,ask=99.5,
                   session_id='fixture-night',trading_date='2026-11-02')
        retry=restored.reconcile_broker_snapshot(snapshot,restored.confirmed_cash_state,quote_snapshot=quote)['retry_intents'][0]
        self.assertEqual(retry['volume'],volume-1)
        self.fill(restored,retry,volume-1,99.0,'final-close')
        self.assertEqual(restored.strategy.get_pos(SYMBOL),0)
        self.assertFalse(restored.strategy.states['rb.SHFE'].layers)
        self.assertEqual(restored.strategy.realized_pnl,-15.0-25.0*(volume-1))
        self.assertEqual(restored.strategy.loss_streak,1)
        self.assertEqual(restored.broker_equity,140000.0)
        self.assertTrue(next(iter(restored.close_lifecycles.values()))['risk_committed'])

    def test_rejected_close_keeps_all_real_inventory_and_can_retry(self):
        obj,bars,volume=self.opened()
        close=self.plan_close(obj,bars)
        event=envelope(dict(schema='weekly19.ctp-order.v1',source_kind='ctp_order_callback',
            account_key=ACCOUNT,material_release_id=RELEASE,signal_order_id=close['signal_order_id'],
            event_id='close-reject',status='rejected',traded=0,broker_order_id='close-reject'))
        obj.apply_order_update(event)
        self.assertEqual(obj.strategy.get_pos(SYMBOL),volume)
        self.assertEqual(obj.strategy.states['rb.SHFE'].active_volume(),volume)
        self.assertEqual(obj.strategy.loss_streak,0)
        self.assertEqual(next(iter(obj.close_lifecycles.values()))['status'],'retry_required')

class DispatchRevisionTests(unittest.TestCase):
    setUp = RuntimeTests.setUp
    ready = RuntimeTests.ready

    def test_fresh_execution_revalidation_caps_plan_without_advancing_strategy(self):
        obj,bars=self.ready()
        decision=obj.process_completed_day('2026-10-30',bars['2026-10-30'],receipt(),broker(),obj.confirmed_cash_state)
        plan=next(x for x in decision['intents'] if x.get('offset')=='open')
        self.assertTrue(plan['position_epoch_id'].startswith('w19-pos-'))
        self.assertTrue(plan['state_generation'].split(':')[-1].isdigit())
        obj.clock=lambda: NOW.replace(hour=21,minute=1)
        # The request was already baseline-bound on Friday. This fixture remains
        # on that cashflow day to isolate pure risk revalidation from day-roll.
        fresh=broker(balance='75000.00',available='75000.00',now=obj.clock(),day='2026-11-02')
        quote=dict(symbol=SYMBOL,observed_at=obj.clock().isoformat(),bid=101.0,ask=101.5,
                   session_id='fixture-night',trading_date='2026-11-02')
        before=obj.export_state()
        proof=obj.revalidate_open_intent(plan['intent_id'],broker_snapshot=fresh,
            confirmed_cash_state=obj.confirmed_cash_state,quote_snapshot=quote)
        self.assertLessEqual(proof['selected_volume'],plan['volume'])
        self.assertEqual(proof['current_equity'],75000.0)
        self.assertEqual(before,obj.export_state())
        state=obj.execution_state(plan['intent_id'])
        self.assertEqual(state['position_epoch_id'],plan['position_epoch_id'])
        self.assertEqual(state['durable_state_sha256'],before['state_sha256'])

class FundingReplanTests(unittest.TestCase):
    setUp = RuntimeTests.setUp
    ready = RuntimeTests.ready

    def test_real_cash_confirmation_creates_new_plan_without_repeating_funding_admission(self):
        obj,bars=self.ready(broker(balance='120000.00',available='0.00'))
        original=obj.process_completed_day('2026-10-30',bars['2026-10-30'],receipt(),
            broker(balance='120000.00',available='0.00'),obj.confirmed_cash_state)
        admission=original['funding_admissions'][0]
        rid=original['funding_recommendation']['request_id']
        at=NOW+timedelta(minutes=2)
        closing=broker(balance='150000.00',now=at)
        raw=json.loads(closing['account']['raw_payload']);raw['Deposit']='30000.00';closing['account']=envelope(raw)
        deposit=envelope(dict(schema='weekly19.bank-cashflow.v1',source_kind='broker_cashflow_receipt',
            account_key=ACCOUNT,material_release_id=RELEASE,request_id=rid,receipt_id='real-fixture-deposit',
            trading_day='2026-10-30',occurred_at=(NOW+timedelta(minutes=1)).isoformat(),
            Amount='30000.00',Direction='deposit',Status='completed'))
        confirmed=funding.confirm_topup(obj.confirmed_cash_state,rid,deposit,closing['account'],at)
        night=NOW.replace(hour=21,minute=1)
        following=broker(balance='150000.00',now=night,day='2026-11-02')
        continuity=envelope(dict(schema='weekly19.cashflow-day-close.v1',source_kind='broker_cashflow_day_close',
            account_key=ACCOUNT,material_release_id=RELEASE,statement_id='fixture-close-statement',
            trading_day='2026-10-30',next_trading_day='2026-11-02',closed_at=(NOW+timedelta(minutes=5)).isoformat(),
            closing_account_sha256=closing['account']['raw_sha256'],Deposit='30000.00',Withdraw='0.00',cashflows_complete=True))
        confirmed=funding.reconcile_trading_day(confirmed,closing['account'],following['account'],night,
                                               continuity_receipt=continuity)
        obj.clock=lambda:night
        quote=dict(symbol=SYMBOL,observed_at=night.isoformat(),bid=101.0,ask=101.5,
                   session_id='fixture-night',trading_date='2026-11-02')
        count=obj.strategy.ams[SYMBOL].count
        replanned=obj.replan_after_confirmed_funding(admission['signal_identity'],following,confirmed,quote)
        self.assertTrue(replanned['replanned'])
        self.assertGreater(replanned['selected_volume'],0)
        self.assertEqual(obj.strategy.estimated_equity,150000.0)
        self.assertEqual(obj.strategy.settled_balance,150000.0)
        self.assertEqual(obj.strategy.ams[SYMBOL].count,count)
        self.assertEqual(len(obj.confirmed_cash_state['requests']),1)
        self.assertEqual(obj.confirmed_cash_state['reserve_remaining_fen'],12000000)
        plan=replanned['intents'][0]
        self.assertEqual(plan['original_funding_admission_id'],admission['admitted_entry_id'])
        proof=obj.revalidate_open_intent(plan['intent_id'],broker_snapshot=following,
            confirmed_cash_state=confirmed,quote_snapshot=quote)
        self.assertLessEqual(proof['selected_volume'],plan['volume'])
        self.assertEqual(len(obj.confirmed_cash_state['requests']),1)
        before=obj.export_state()
        again=obj.replan_after_confirmed_funding(admission['signal_identity'],following,confirmed,quote)
        self.assertEqual(again['intents'][0]['intent_id'],plan['intent_id'])
        self.assertEqual(before,obj.export_state())

class IncrementalInputTests(unittest.TestCase):
    setUp = RuntimeTests.setUp
    ready = RuntimeTests.ready

    def test_append_only_future_data_can_restore_but_accepted_history_cannot_change(self):
        obj,bars=self.ready()
        saved=obj.export_state()
        calendar,frame,_,meta=fixture()
        extra=frame.iloc[-1:].copy();extra['date']='2026-11-02'
        extended=pd.concat([frame,extra],ignore_index=True)
        meta['daily_mapping']['2026-11-02']=dict(meta['daily_mapping']['2026-10-30'])
        restored=runtime.build_weekly19_runtime(runtime.DEFAULT_SETTINGS_ASSET,meta,calendar,extended,
            broker(),saved,obj.confirmed_cash_state,clock=lambda:NOW)
        self.assertEqual(runtime._encode(obj.strategy.ams[SYMBOL]),runtime._encode(restored.strategy.ams[SYMBOL]))
        changed=extended.copy();changed.loc[0,'low']=98.0
        with self.assertRaisesRegex(runtime.RuntimeContractError,'accepted_input_prefix_changed'):
            runtime.build_weekly19_runtime(runtime.DEFAULT_SETTINGS_ASSET,meta,calendar,changed,
                broker(),saved,obj.confirmed_cash_state,clock=lambda:NOW)

class PendingDayQueueTests(unittest.TestCase):
    setUp=RuntimeTests.setUp
    opened=CloseLifecycleTests.opened
    fill=CloseLifecycleTests.fill
    plan_close=CloseLifecycleTests.plan_close
    def test_pending_close_queues_only_indicators_and_never_replays_old_opens(self):
        obj,bars,volume=self.opened()
        self.plan_close(obj,bars)
        saved=obj.export_state()
        calendar,frame,_,meta=fixture()
        extra=frame.iloc[-1:].copy();extra['date']='2026-11-02'
        frame=pd.concat([frame,extra],ignore_index=True)
        meta['daily_mapping']['2026-11-02']=dict(meta['daily_mapping']['2026-10-30'])
        day_now=datetime(2026,11,2,15,15,tzinfo=ZoneInfo('Asia/Shanghai'))
        snapshot=broker(positions=[dict(vt_symbol=SYMBOL,direction='long',volume=volume)],now=day_now,day='2026-11-02')
        restored=runtime.build_weekly19_runtime(runtime.DEFAULT_SETTINGS_ASSET,meta,calendar,frame,
            snapshot,saved,obj.confirmed_cash_state,clock=lambda:day_now)
        bar=runtime._decode(runtime._encode(bars['2026-10-30'][SYMBOL]));bar.datetime=day_now.replace(hour=0,minute=0)
        result=restored.process_completed_day('2026-11-02',{SYMBOL:bar},receipt('2026-11-02'),snapshot,restored.confirmed_cash_state)
        self.assertTrue(result['reduce_only'])
        self.assertTrue(result['bars_queued'])
        self.assertEqual(result['intents'],[])
        self.assertEqual(restored.strategy.get_pos(SYMBOL),volume)
        self.assertEqual(restored.strategy.loss_streak,0)

class RolloverLifecycleTests(unittest.TestCase):
    setUp=RuntimeTests.setUp

    def test_roll_reopen_waits_for_real_flat_and_fresh_current_sizing(self):
        calendar,frame,bars,meta=fixture();new_symbol='rb2701.SHFE'
        second=frame.copy();second['vt_symbol']=new_symbol;second['contract_epoch_id']='rb2701-physical'
        frame=pd.concat([frame,second],ignore_index=True)
        for batch in bars.values():
            b=runtime._decode(runtime._encode(batch[SYMBOL]));b.symbol='rb2701';b.vt_symbol=new_symbol;batch[new_symbol]=b
        meta['vt_symbols'].append(new_symbol);meta['source_symbol_by_contract'][new_symbol]='rb.SHFE'
        for key,value in [('sizes',10),('priceticks',1.0),('margin_ratios',.1),('rates',0.0),('slippages',0.0)]:meta[key][new_symbol]=value
        obj=runtime.build_weekly19_runtime(runtime.DEFAULT_SETTINGS_ASSET,meta,calendar,frame,broker(),None,
            funding.initial_state(ACCOUNT,RELEASE,'2026-10-30'),clock=lambda:NOW)
        obj.warmup([bars[d] for d in sorted(bars) if d<'2026-10-30'])
        opening=obj.process_completed_day('2026-10-30',bars['2026-10-30'],receipt(),broker(),obj.confirmed_cash_state)['intents'][0]
        night=NOW.replace(hour=21,minute=1);obj.clock=lambda:night
        CloseLifecycleTests.fill(self,obj,opening,opening['volume'],101.5,'roll-old-open')
        obj.strategy._handle_rollover(obj.strategy.states['rb.SHFE'],new_symbol,bars['2026-10-30'])
        obj.strategy.rebalance_portfolio(bars['2026-10-30'])
        close=next(x for x in reversed(obj.engine.intents) if x.get('offset')=='close')
        self.assertFalse(any(x.get('intent_kind')=='rollover_reopen' for x in obj.engine.intents))
        self.assertTrue(obj.pending_rollovers)
        CloseLifecycleTests.fill(self,obj,close,close['volume'],100.0,'roll-old-close')
        following=broker(balance='140000.00',now=night,day='2026-11-02')
        closing=broker()
        continuity=envelope(dict(schema='weekly19.cashflow-day-close.v1',source_kind='broker_cashflow_day_close',
            account_key=ACCOUNT,material_release_id=RELEASE,statement_id='roll-close-statement',
            trading_day='2026-10-30',next_trading_day='2026-11-02',closed_at=(NOW+timedelta(minutes=5)).isoformat(),
            closing_account_sha256=closing['account']['raw_sha256'],Deposit='0.00',Withdraw='0.00',cashflows_complete=True))
        cash=funding.reconcile_trading_day(obj.confirmed_cash_state,closing['account'],following['account'],night,continuity_receipt=continuity)
        quote=dict(symbol=new_symbol,observed_at=night.isoformat(),bid=101.0,ask=101.5,
                   session_id='fixture-night',trading_date='2026-11-02')
        result=obj.reconcile_broker_snapshot(following,cash,quote_snapshot=quote)
        reopened=result['rollover_intents'][0]
        self.assertGreater(reopened['volume'],0)
        self.assertLessEqual(reopened['volume'],opening['volume'])
        self.assertEqual(reopened['depends_on_close_intent_id'],close['intent_id'])
        self.assertEqual(reopened['root_position_id'],opening['root_position_id'])
        self.assertEqual(obj.strategy.get_pos(new_symbol),0)
        self.assertEqual(obj.strategy.estimated_equity,140000.0)

class NativeOffsetTests(unittest.TestCase):
    setUp=RuntimeTests.setUp
    opened=CloseLifecycleTests.opened
    fill=CloseLifecycleTests.fill
    plan_close=CloseLifecycleTests.plan_close

    def test_each_native_close_offset_preserves_business_lot_accounting(self):
        for native,flag in [('close','1'),('closetoday','3'),('closeyesterday','4')]:
            with self.subTest(native=native):
                obj,bars,volume=self.opened();plan=self.plan_close(obj,bars)
                raw=dict(schema='weekly19.ctp-trade.v1',source_kind='ctp_trade_callback',account_key=ACCOUNT,
                    material_release_id=RELEASE,trade_id='offset-'+native,broker_order_id='offset-order-'+native,
                    vt_symbol=SYMBOL,direction='short',offset='close',business_offset='close',
                    broker_offset=native,native_offset_flag=flag,volume=1,price=100.0,
                    trading_day=plan['trading_date'],execution_datetime=obj.clock().isoformat())
                obj.apply_broker_fill(envelope(raw),plan['signal_identity'])
                self.assertEqual(obj.strategy.get_pos(SYMBOL),volume-1)
                self.assertEqual(obj.strategy.states['rb.SHFE'].active_volume(),volume-1)
                self.assertEqual(sum(x['volume'] for x in obj.strategy.pending_close_lots[SYMBOL]),volume-1)
                self.assertEqual(obj.strategy.realized_pnl,-15.0)
                bad=dict(raw,trade_id='bad-native',broker_offset='unknown')
                before=obj.export_state()
                with self.assertRaisesRegex(runtime.RuntimeContractError,'native_offset'):
                    obj.apply_broker_fill(envelope(bad),plan['signal_identity'])
                self.assertEqual(before,obj.export_state())

    def test_partial_open_cancel_keeps_actual_costs_and_original_signal(self):
        obj,bars=RuntimeTests.ready(self)
        plan=obj.process_completed_day('2026-10-30',bars['2026-10-30'],receipt(),broker(),obj.confirmed_cash_state)['intents'][0]
        obj.clock=lambda:NOW.replace(hour=21,minute=1)
        self.fill(obj,plan,1,101.5,'partial-open-1')
        self.fill(obj,plan,2,102.0,'partial-open-2')
        event=envelope(dict(schema='weekly19.ctp-order.v1',source_kind='ctp_order_callback',account_key=ACCOUNT,
            material_release_id=RELEASE,signal_order_id=plan['signal_order_id'],event_id='partial-open-cancel',
            status='cancelled',traded=3,broker_order_id='broker-'+plan['intent_id']))
        obj.apply_order_update(event)
        state=obj.strategy.states['rb.SHFE']
        self.assertEqual(state.active_volume(),3)
        self.assertAlmostEqual(state.avg_entry_price(),(101.5+204.0)/3)
        self.assertTrue(all(l.entry_price_synced and l._stage827_signal_order_id==plan['signal_order_id'] for l in state.layers))
        self.assertEqual(obj.strategy.get_target(SYMBOL),3)

class EvidenceReplayTests(unittest.TestCase):
    setUp=RuntimeTests.setUp
    ready=RuntimeTests.ready

    def test_same_real_fill_and_order_status_from_new_query_generation_are_noops(self):
        obj,bars=self.ready()
        plan=obj.process_completed_day('2026-10-30',bars['2026-10-30'],receipt(),broker(),obj.confirmed_cash_state)['intents'][0]
        obj.clock=lambda:NOW.replace(hour=21,minute=1)
        trade=dict(schema='weekly19.ctp-trade.v1',source_kind='ctp_trade_callback',source_callback='onRspQryTrade',
            account_key=ACCOUNT,material_release_id=RELEASE,trade_id='ctp:stable-trade',broker_order_id='semantic-order',
            intent_id=plan['intent_id'],signal_order_id=plan['signal_order_id'],signal_identity=plan['signal_identity'],
            vt_symbol=SYMBOL,direction='long',offset='open',business_offset='open',broker_offset='open',native_offset_flag='0',
            volume=1,price='101.50',trading_day=plan['trading_date'],execution_datetime=obj.clock().isoformat(),
            generation_uuid='query-one',observed_at=obj.clock().isoformat(),raw_capture_sha256='a'*64)
        obj.apply_broker_fill(envelope(trade),plan['signal_identity'])
        before=obj.export_state()
        repeat=dict(trade,generation_uuid='query-two',raw_capture_sha256='b'*64,source_callback='onRtnTrade')
        obj.apply_broker_fill(envelope(repeat),plan['signal_identity'])
        self.assertEqual(before,obj.export_state())
        semantic=dict(account_key=ACCOUNT,material_release_id=RELEASE,intent_id=plan['intent_id'],
            signal_order_id=plan['signal_order_id'],signal_identity=plan['signal_identity'],broker_order_id='semantic-order',
            vt_symbol=SYMBOL,direction='long',offset='open',broker_offset='open',volume=plan['volume'],traded=1,status='working')
        digest=funding._hash(semantic)
        order=dict(semantic,schema='weekly19.ctp-order.v1',source_kind='ctp_order_callback',source_callback='onRspQryOrder',
            event_id='ctp-order:'+digest,event_semantic_sha256=digest,generation_uuid='query-one',raw_capture_sha256='c'*64)
        obj.apply_order_update(envelope(order))
        before=obj.export_state()
        obj.apply_order_update(envelope(dict(order,generation_uuid='query-two',raw_capture_sha256='d'*64)))
        self.assertEqual(before,obj.export_state())
        with self.assertRaises(runtime.RuntimeContractError):
            obj.apply_broker_fill(envelope(dict(repeat,price='102.00')),plan['signal_identity'])
        self.assertEqual(before,obj.export_state())

class FrozenParameterTests(unittest.TestCase):
    setUp=RuntimeTests.setUp
    ready=RuntimeTests.ready

    def test_loaded_parameter_drift_is_rejected_before_original_day_loop(self):
        obj,bars=self.ready()
        obj.strategy.enable_stage827_intraday_c2_stop=True
        with self.assertRaisesRegex(runtime.RuntimeContractError,'fixed_strategy_parameter_changed'):
            obj.process_completed_day('2026-10-30',bars['2026-10-30'],receipt(),broker(),obj.confirmed_cash_state)
        self.assertFalse(any(obj.strategy.pos_data.values()))
        self.assertFalse(any(obj.strategy.target_data.values()))

class RestartRecoveryTests(unittest.TestCase):
    setUp=RuntimeTests.setUp
    ready=RuntimeTests.ready

    def test_saved_pending_plan_consumes_real_recovery_fills_before_fresh_position_reconcile(self):
        obj,bars=self.ready()
        plan=obj.process_completed_day('2026-10-30',bars['2026-10-30'],receipt(),broker(),obj.confirmed_cash_state)['intents'][0]
        saved=obj.export_state();night=NOW.replace(hour=21,minute=1)
        fill=envelope(dict(schema='weekly19.ctp-trade.v1',source_kind='ctp_trade_callback',source_callback='onRspQryTrade',
            account_key=ACCOUNT,material_release_id=RELEASE,trade_id='recovery-real-fill',broker_order_id='recovery-order',
            vt_symbol=SYMBOL,direction='long',offset='open',volume=1,price=101.5,
            trading_day='2026-11-02',execution_datetime=night.isoformat()))
        order=envelope(dict(schema='weekly19.ctp-order.v1',source_kind='ctp_order_callback',source_callback='onRspQryOrder',
            account_key=ACCOUNT,material_release_id=RELEASE,signal_order_id=plan['signal_order_id'],
            broker_order_id='recovery-order',event_id='recovery-partial-order',status='partially_filled',traded=1))
        actual=broker(balance='149999.00',positions=[dict(vt_symbol=SYMBOL,direction='long',volume=1)],now=night,day='2026-11-02')
        calendar,frame,_,meta=fixture()
        with self.assertRaisesRegex(runtime.RuntimeContractError,'broker_strategy_position_mismatch'):
            runtime.build_weekly19_runtime(runtime.DEFAULT_SETTINGS_ASSET,meta,calendar,frame,actual,saved,
                obj.confirmed_cash_state,clock=lambda:night)
        events=[dict(kind='order',envelope=order),dict(kind='fill',envelope=fill,signal_identity=plan['signal_identity'])]
        recovered=runtime.build_weekly19_runtime(runtime.DEFAULT_SETTINGS_ASSET,meta,calendar,frame,actual,saved,
            obj.confirmed_cash_state,clock=lambda:night,recovery_events=events)
        self.assertEqual(recovered.strategy.get_pos(SYMBOL),1)
        self.assertEqual(recovered.strategy.estimated_equity,149999.0)
        self.assertEqual(sum(l.volume for l in recovered.strategy.states['rb.SHFE'].layers if l.entry_price_synced),1)
        self.assertEqual(saved,obj.export_state())
        again=runtime.build_weekly19_runtime(runtime.DEFAULT_SETTINGS_ASSET,meta,calendar,frame,actual,recovered.export_state(),
            recovered.confirmed_cash_state,clock=lambda:night,recovery_events=events)
        self.assertEqual(recovered.export_state(),again.export_state())

    def test_fresh_state_cannot_import_foreign_recovery_events(self):
        calendar,frame,_,meta=fixture()
        with self.assertRaisesRegex(runtime.RuntimeContractError,'recovery_events_require_durable_state'):
            runtime.build_weekly19_runtime(runtime.DEFAULT_SETTINGS_ASSET,meta,calendar,frame,broker(),None,
                funding.initial_state(ACCOUNT,RELEASE,'2026-10-30'),clock=lambda:NOW,
                recovery_events=[dict(kind='fill',envelope={})])

class FundingContinuityTests(unittest.TestCase):
    def test_unreconciled_cash_day_preserves_weekly_stop_and_blocks_new_candidate(self):
        calendar, _, original_bars, meta = fixture()
        rows=[]; batches={}
        for day in sorted(original_bars):
            batches[day]={}
            for symbol in (SYMBOL, 'hc2612.SHFE'):
                price=(101.0 if '2026-10-19' <= day <= '2026-10-23' else
                       98.0 if day >= '2026-10-26' else 100.0) if symbol==SYMBOL else (101.0 if day >= '2026-10-26' else 100.0)
                native, exchange=symbol.split('.')
                batches[day][symbol]=BarData(symbol=native,exchange=Exchange(exchange),
                    datetime=pd.Timestamp(day).to_pydatetime(),gateway_name='FIXTURE',interval=Interval.DAILY,
                    open_price=price,high_price=price+.5,low_price=price-.5,close_price=price,
                    volume=1000,open_interest=2000)
                rows.append(dict(vt_symbol=symbol,date=day,contract_epoch_id=symbol+'-physical',
                    open=price,high=price+.5,low=price-.5,close=price,volume=1000,close_oi=2000.0))
        moment=[NOW.replace(day=23)]
        cash=funding.initial_state(ACCOUNT,RELEASE,'2026-10-23')
        obj=runtime.build_weekly19_runtime(runtime.DEFAULT_SETTINGS_ASSET,meta,calendar,pd.DataFrame(rows),
            broker(now=moment[0],day='2026-10-23'),None,cash,clock=lambda:moment[0])
        obj.warmup([batches[d] for d in sorted(batches) if d<'2026-10-23'])
        initial=obj.process_completed_day('2026-10-23',batches['2026-10-23'],receipt('2026-10-23'),
            broker(now=moment[0],day='2026-10-23'),obj.confirmed_cash_state)
        opening=next(x for x in initial['intents'] if x.get('offset')=='open' and x['vt_symbol']==SYMBOL)
        moment[0]=moment[0].replace(hour=21,minute=1)
        obj.apply_broker_fill(envelope(dict(schema='weekly19.ctp-trade.v1',source_kind='ctp_trade_callback',
            account_key=ACCOUNT,material_release_id=RELEASE,trade_id='cash-day-open',broker_order_id='cash-day-order',
            vt_symbol=SYMBOL,direction='long',offset='open',volume=opening['volume'],price=101.0,
            trading_day=opening['trading_date'],execution_datetime=moment[0].isoformat())),opening['signal_identity'])
        cash_before=copy.deepcopy(obj.confirmed_cash_state)
        for day in sorted(d for d in batches if '2026-10-23'<d<='2026-10-30'):
            moment[0]=datetime.fromisoformat(day+'T15:15:00+08:00')
            actual=broker(now=moment[0],day=day,positions=[dict(vt_symbol=SYMBOL,direction='long',volume=opening['volume'])])
            decision=obj.process_completed_day(day,batches[day],receipt(day),actual,obj.confirmed_cash_state)
        self.assertTrue(any(x['offset']=='close' and x['vt_symbol']==SYMBOL for x in decision['intents']))
        self.assertTrue(decision['funding_admitted_ids'])
        self.assertFalse(any(x['offset']=='open' for x in decision['intents']))
        self.assertEqual(decision['funding_recommendation']['blocked_reason'],'day_roll_requires_reconciliation')
        self.assertFalse(decision['funding_recommendation']['actionable'])
        self.assertEqual(cash_before,obj.confirmed_cash_state)
        self.assertEqual(obj.strategy.get_pos(SYMBOL),opening['volume'])

class CompactCloneTests(unittest.TestCase):
    setUp=RuntimeTests.setUp
    ready=RuntimeTests.ready
    def test_sizing_clone_does_not_rebuild_actor_and_preserves_all_symbols_without_mutating_owner(self):
        from unittest.mock import patch
        obj,_=self.ready();before=obj.export_state()
        with patch.object(runtime.Runtime,'__init__',side_effect=AssertionError('full actor rebuild')):
            clone=obj._clone_for_sizing(broker(),obj.confirmed_cash_state)
        self.assertEqual(set(clone.strategy.states),set(obj.strategy.states))
        self.assertEqual(set(clone.strategy.ams),set(obj.strategy.ams))
        self.assertIsNot(clone.strategy.states,obj.strategy.states)
        self.assertIsNot(clone.strategy.ams[SYMBOL].inner.close_array,obj.strategy.ams[SYMBOL].inner.close_array)
        clone.strategy.ams[SYMBOL].inner.close_array[-1]=3
        clone.strategy.states['rb.SHFE'].bars_since_entry=999
        self.assertEqual(before,obj.export_state())
    def test_compact_durable_uses_bound_shared_weeks_and_lossless_restore(self):
        obj,_=self.ready();saved=obj.export_state()
        self.assertIn('shared_inputs',saved)
        self.assertEqual(saved['shared_inputs']['weeks']['sha256'],runtime._hash(runtime._encode(obj.weeks)))
        restored,_=build(durable=saved)
        self.assertIs(restored.strategy.ams[SYMBOL].weeks,restored.weeks)
        self.assertEqual(saved,restored.export_state())
        changed=copy.deepcopy(saved);changed['shared_inputs']['weeks']['sha256']='f'*64
        changed['state_sha256']=runtime._state_digest({k:v for k,v in changed.items() if k!='state_sha256'})
        with self.assertRaisesRegex(runtime.RuntimeContractError,'shared_calendar_digest_mismatch'):
            build(durable=changed)

class NewContractHistoryTests(unittest.TestCase):
    setUp=RuntimeTests.setUp
    ready=RuntimeTests.ready
    def extension(self):
        obj,bars=self.ready();saved=obj.export_state();calendar,frame,_,meta=fixture()
        symbol='rb2701.SHFE';new=frame.copy();new['vt_symbol']=symbol;new['contract_epoch_id']='SHFE.RB.202701';new['close_oi']=2000.
        full=pd.concat([frame,new],ignore_index=True)
        meta['vt_symbols'].append(symbol);meta['source_symbol_by_contract'][symbol]='rb.SHFE'
        for key,value in [('sizes',10),('priceticks',1.),('margin_ratios',.1),('rates',0.),('slippages',0.)]:meta[key][symbol]=value
        source_bars=[]
        for day in sorted(bars):
            b=runtime._decode(runtime._encode(bars[day][SYMBOL]));b.symbol='rb2701';b.vt_symbol=symbol;source_bars.append(b)
        meta['new_contract_history_bars']={symbol:source_bars}
        meta['new_contract_history_admissions']=[dict(schema='weekly19.new-contract-history-admission.v1',vt_symbol=symbol,
            contract_epoch_id='SHFE.RB.202701',contract_yyyymm='202701',listed_date='2026-05-04',delisted_date='2027-01-15',
            available_history_complete=True,source_sha256='a'*64,metadata_sha256='b'*64)]
        return obj,saved,calendar,full,meta
    def test_new_never_owned_contract_only_prewarms_real_history_without_replaying_signals(self):
        obj,saved,calendar,full,meta=self.extension()
        restored=runtime.build_weekly19_runtime(runtime.DEFAULT_SETTINGS_ASSET,meta,calendar,full,
            broker(),saved,obj.confirmed_cash_state,clock=lambda:NOW)
        self.assertGreaterEqual(restored.strategy.ams['rb2701.SHFE'].count,21)
        self.assertEqual(runtime._encode(obj.strategy.ams[SYMBOL]),runtime._encode(restored.strategy.ams[SYMBOL]))
        self.assertFalse(restored.engine.intents);self.assertFalse(any(restored.strategy.pos_data.values()))
        self.assertEqual(saved,obj.export_state())
        self.assertIn('rb2701.SHFE',restored.export_state()['accepted_scope']['contracts'])
    def test_new_history_without_explicit_delivery_and_actual_bar_admission_is_rejected(self):
        obj,saved,calendar,full,meta=self.extension();meta.pop('new_contract_history_admissions')
        with self.assertRaisesRegex(runtime.RuntimeContractError,'new_contract_history_admission_required'):
            runtime.build_weekly19_runtime(runtime.DEFAULT_SETTINGS_ASSET,meta,calendar,full,
                broker(),saved,obj.confirmed_cash_state,clock=lambda:NOW)

class PhysicalChildBatchTests(unittest.TestCase):
    setUp=RuntimeTests.setUp
    def opening_and_close(self):
        obj,bars=RuntimeTests.ready(self,broker(available='400.00'))
        decision=obj.process_completed_day('2026-10-30',bars['2026-10-30'],receipt(),broker(available='400.00'),obj.confirmed_cash_state)
        opening=next(x for x in decision['intents'] if x.get('offset')=='open');self.assertEqual(opening['volume'],2)
        obj.clock=lambda:NOW.replace(hour=21,minute=1)
        CloseLifecycleTests.fill(self,obj,opening,2,101.5,'batch-opening')
        obj.reconcile_broker_snapshot(broker(positions=[dict(vt_symbol=SYMBOL,direction='long',volume=2)],now=obj.clock(),day='2026-11-02'),obj.confirmed_cash_state)
        plan=CloseLifecycleTests.plan_close(self,obj,bars)
        children=[dict(child_order_id='physical-'+str(i),child_order_index=i,volume=1,broker_offset=offset,
                       vt_symbol=SYMBOL,direction='short',trading_date=plan['trading_date'])
                  for i,offset in enumerate(('closetoday','closeyesterday'))]
        batch=dict(api_slot_batch_id='0123456789abcdef01234567',api_slot_batch_count=2,
            expected_children=children,expected_children_sha256=runtime._hash(children),approved_parent_volume=2)
        return obj,plan,batch
    def child_fill(self,obj,plan,batch,index):
        child=batch['expected_children'][index]
        raw=dict(schema='weekly19.ctp-trade.v1',source_kind='ctp_trade_callback',source_callback='onRtnTrade',
            account_key=ACCOUNT,material_release_id=RELEASE,trade_id='batch-close-trade-'+str(index),
            intent_id=plan['intent_id'],signal_identity=plan['signal_identity'],signal_order_id=plan['signal_order_id'],
            broker_order_id='actual-broker-'+str(index),vt_symbol=SYMBOL,direction='short',offset='close',business_offset='close',
            broker_offset=child['broker_offset'],native_offset_flag='3' if index==0 else '4',volume=1,price=100.,
            trading_day=plan['trading_date'],execution_datetime=obj.clock().isoformat(),child_order_id=child['child_order_id'],**batch)
        return obj.apply_broker_fill(envelope(raw),plan['signal_identity'])
    def child_status(self,obj,plan,batch,index,status,traded):
        child=batch['expected_children'][index]
        raw=dict(schema='weekly19.ctp-order.v1',source_kind='ctp_order_callback',source_callback='onRspQryOrder',
            account_key=ACCOUNT,material_release_id=RELEASE,intent_id=plan['intent_id'],signal_order_id=plan['signal_order_id'],
            signal_identity=plan['signal_identity'],broker_order_id='actual-broker-'+str(index),vt_symbol=SYMBOL,direction='short',
            offset='close',broker_offset=child['broker_offset'],volume=1,traded=traded,status=status,
            child_order_id=child['child_order_id'],**batch)
        keys=('account_key','material_release_id','intent_id','signal_order_id','signal_identity','broker_order_id','vt_symbol','direction','offset','broker_offset','volume','traded','status')
        digest=runtime._hash({k:raw[k] for k in keys});raw.update(event_semantic_sha256=digest,event_id='ctp-order:'+digest)
        return obj.apply_order_update(envelope(raw))
    def test_split_close_first_child_terminal_keeps_second_child_and_survives_restart(self):
        obj,plan,batch=self.opening_and_close();self.child_fill(obj,plan,batch,0)
        self.child_status(obj,plan,batch,0,'filled',1)
        self.assertEqual(obj.strategy.get_pos(SYMBOL),1)
        self.assertNotIn(plan['signal_order_id'],obj.engine.order_terminal)
        self.assertEqual(sum(x.volume for x in obj.strategy.states['rb.SHFE'].layers),1)
        saved=obj.export_state()
        fresh=broker(positions=[dict(vt_symbol=SYMBOL,direction='long',volume=1)],now=obj.clock(),day='2026-11-02')
        restored,_=build(fresh,saved,obj.confirmed_cash_state,now=obj.clock())
        self.child_status(restored,plan,batch,1,'working',0)
        self.assertNotIn(plan['signal_order_id'],restored.engine.order_terminal)
        self.child_fill(restored,plan,batch,1);self.child_status(restored,plan,batch,1,'filled',1)
        self.assertEqual(restored.strategy.get_pos(SYMBOL),0)
        self.assertEqual(restored.engine.order_terminal[plan['signal_order_id']],'filled')
        self.assertTrue(next(iter(restored.close_lifecycles.values()))['risk_committed'])
    def test_cancelled_child_and_other_working_cannot_terminate_parent(self):
        obj,plan,batch=self.opening_and_close()
        self.child_status(obj,plan,batch,0,'cancelled',0);self.child_status(obj,plan,batch,1,'working',0)
        self.assertNotIn(plan['signal_order_id'],obj.engine.order_terminal)
        self.assertEqual(obj.strategy.get_pos(SYMBOL),2)
        self.child_fill(obj,plan,batch,1);self.child_status(obj,plan,batch,1,'filled',1)
        self.assertEqual(obj.strategy.get_pos(SYMBOL),1)
        self.assertEqual(next(iter(obj.close_lifecycles.values()))['status'],'retry_required')
        self.assertFalse(next(iter(obj.close_lifecycles.values()))['risk_committed'])

    def test_changed_manifest_cannot_rebind_pending_child_after_actual_fill(self):
        obj,plan,batch=self.opening_and_close();self.child_fill(obj,plan,batch,0);before=obj.export_state()
        changed=copy.deepcopy(batch);changed['expected_children'][1]['child_order_id']='forged-child'
        changed['expected_children_sha256']=runtime._hash(changed['expected_children'])
        with self.assertRaisesRegex(runtime.RuntimeContractError,'physical_child_manifest_changed'):
            self.child_status(obj,plan,changed,1,'working',0)
        self.assertEqual(before,obj.export_state())

    def test_verified_execution_batch_alias_preserves_same_child_protocol(self):
        obj,plan,batch=self.opening_and_close();batch['execution_batch_id']=batch.pop('api_slot_batch_id')
        self.child_fill(obj,plan,batch,0);self.child_status(obj,plan,batch,0,'filled',1)
        self.assertEqual(obj.strategy.get_pos(SYMBOL),1)
        self.assertNotIn(plan['signal_order_id'],obj.engine.order_terminal)

class QueuedReceiptGateTests(unittest.TestCase):
    fill=CloseLifecycleTests.fill
    def test_queued_day_origin_and_cross_day_close_retry_bind_new_receipt_through_store_and_gate(self):
        from qmt_roll_weekly19_pipeline_state import PipelineStateStore
        import qmt_roll_weekly19_execution as execution
        import tempfile
        obj,bars,volume=CloseLifecycleTests.opened(self);close=CloseLifecycleTests.plan_close(self,obj,bars)
        original_receipt=close['data_receipt_sha256'];saved=obj.export_state()
        calendar,frame,_,meta=fixture();extra=frame.iloc[-1:].copy();extra['date']='2026-11-02'
        frame=pd.concat([frame,extra],ignore_index=True);meta['daily_mapping']['2026-11-02']=dict(meta['daily_mapping']['2026-10-30'])
        now=datetime(2026,11,2,15,15,tzinfo=ZoneInfo('Asia/Shanghai'))
        snapshot=broker(positions=[dict(vt_symbol=SYMBOL,direction='long',volume=volume)],now=now,day='2026-11-02')
        restored=runtime.build_weekly19_runtime(runtime.DEFAULT_SETTINGS_ASSET,meta,calendar,frame,snapshot,saved,obj.confirmed_cash_state,clock=lambda:now)
        bar=runtime._decode(runtime._encode(bars['2026-10-30'][SYMBOL]));bar.datetime=now.replace(hour=0,minute=0)
        new_receipt=receipt('2026-11-02')
        decision=restored.process_completed_day('2026-11-02',{SYMBOL:bar},new_receipt,snapshot,restored.confirmed_cash_state)
        origin=restored.export_state()
        with tempfile.TemporaryDirectory(dir='/private/tmp') as folder:
            path=Path(folder).resolve();path.chmod(0o700)
            store=PipelineStateStore(path/'state.json',ACCOUNT,RELEASE)
            store.initialize(dict(schema='weekly19.pipeline-state.v1',revision=0,account_key=ACCOUNT,material_release_id=RELEASE,
                funding=restored.confirmed_cash_state,runtime=origin,decision_state=origin,decision=decision))
            self.assertEqual(store.read()['decision']['data_receipt_sha256'],runtime._hash(new_receipt))
        restored.apply_order_update(envelope(dict(schema='weekly19.ctp-order.v1',source_kind='ctp_order_callback',
            account_key=ACCOUNT,material_release_id=RELEASE,signal_order_id=close['signal_order_id'],
            event_id='queued-close-cancel',status='cancelled',traded=0,broker_order_id='queued-close-old')))
        night=now.replace(hour=21,minute=1);restored.clock=lambda:night
        fresh=broker(positions=[dict(vt_symbol=SYMBOL,direction='long',volume=volume)],now=night,day='2026-11-03')
        quote=dict(symbol=SYMBOL,observed_at=night.isoformat(),bid=100.,ask=101.,session_id='fixture-Tuesday-night',trading_date='2026-11-03')
        retry=restored.reconcile_broker_snapshot(fresh,restored.confirmed_cash_state,quote_snapshot=quote)['retry_intents'][0]
        self.assertEqual(retry['target_date'],'2026-11-02');self.assertEqual(retry['data_receipt_sha256'],runtime._hash(new_receipt))
        self.assertEqual(retry['lifecycle_origin_signal_receipt'],original_receipt)
        profile=execution.PROFILE
        ready=dict(retry,execution_profile=profile.profile_key,official_live_version=profile.official_version,
            capital=profile.capital,capital_label=profile.capital_label,ruleset_version=profile.ruleset_version)
        order_raw=json.loads(fresh['positions']['raw_payload']);order_raw.pop('positions');order_raw.update(schema='weekly19.ctp-orders.v1',source_kind='ctp_order_query',orders=[])
        fresh['orders']=envelope(order_raw)
        context=dict(material_release_id=RELEASE,account_fingerprint=ACCOUNT,trading_date='2026-11-03',cold_start_date='2026-10-30',
            target_cutoff_date='2026-11-02',data_receipt_sha256=runtime._hash(new_receipt),confirmed_cash_state=restored.confirmed_cash_state,
            broker_snapshot=fresh,quote=quote,metadata=dict(vt_symbol=SYMBOL,physical_epoch_id=retry['physical_epoch_id'],pricetick=1,
                size=10,broker_margin_rate='.165',min_volume=1,max_volume=10000),
            session=dict(is_open=True,trading_date='2026-11-03',session_id=quote['session_id'],starts_at=night.isoformat(),ends_at=(night+timedelta(hours=2)).isoformat()),execution_ledger_rows=[])
        result=execution.evaluate_intent(ready,context,now=night)
        self.assertTrue(result['allowed'],result)
        self.assertEqual(restored.strategy.get_pos(SYMBOL),volume)

class EquityRecoveredReplanTests(unittest.TestCase):
    ready=RuntimeTests.ready
    def test_equity_recovers_above_floor_without_transfer_reuses_original_admission_once(self):
        obj,bars=self.ready(broker(balance='120000.00',available='0.00'))
        decision=obj.process_completed_day('2026-10-30',bars['2026-10-30'],receipt(),
            broker(balance='120000.00',available='0.00'),obj.confirmed_cash_state)
        self.assertFalse(decision['intents']);admission=decision['funding_admissions'][0]
        at=NOW+timedelta(minutes=2);closing=broker(balance='151000.00',now=at)
        night=NOW.replace(hour=21,minute=1);following=broker(balance='151000.00',now=night,day='2026-11-02')
        continuity=envelope(dict(schema='weekly19.cashflow-day-close.v1',source_kind='broker_cashflow_day_close',
            account_key=ACCOUNT,material_release_id=RELEASE,statement_id='recovery-no-transfer',trading_day='2026-10-30',
            next_trading_day='2026-11-02',closed_at=(NOW+timedelta(minutes=5)).isoformat(),
            closing_account_sha256=closing['account']['raw_sha256'],Deposit='0.00',Withdraw='0.00',cashflows_complete=True))
        cash=funding.reconcile_trading_day(obj.confirmed_cash_state,closing['account'],following['account'],night,continuity_receipt=continuity)
        obj.clock=lambda:night
        quote=dict(symbol=SYMBOL,observed_at=night.isoformat(),bid=101.,ask=101.5,session_id='recovery-fixture',trading_date='2026-11-02')
        before_count=obj.strategy.ams[SYMBOL].count
        before=obj.export_state()
        bad=copy.deepcopy(following);raw=json.loads(bad['account']['raw_payload']);raw['Deposit']='100.00';bad['account']=envelope(raw)
        with self.assertRaisesRegex(funding.FundingError,'unreconciled_cashflow_deposit'):
            obj.replan_after_confirmed_funding(admission['signal_identity'],bad,cash,quote)
        self.assertEqual(before,obj.export_state())
        below=broker(balance='149000.00',now=night,day='2026-11-02')
        with self.assertRaisesRegex(funding.FundingError,'funding_pending'):
            obj.replan_after_confirmed_funding(admission['signal_identity'],below,cash,quote)
        self.assertEqual(before,obj.export_state())
        result=obj.replan_after_confirmed_funding(admission['signal_identity'],following,cash,quote)
        self.assertTrue(result['replanned']);self.assertGreater(result['selected_volume'],0)
        self.assertEqual(result['funding_ready_reason'],'equity_recovered_without_transfer')
        self.assertEqual(obj.confirmed_cash_state['confirmed_topup_fen'],0)
        self.assertEqual(obj.confirmed_cash_state['reserve_remaining_fen'],15000000)
        self.assertEqual(obj.confirmed_cash_state['receipts'],{})
        self.assertEqual(len(obj.confirmed_cash_state['requests']),1)
        self.assertEqual(result['intents'][0]['original_funding_admission_id'],admission['admitted_entry_id'])
        self.assertEqual(obj.strategy.ams[SYMBOL].count,before_count)
        before=obj.export_state();again=obj.replan_after_confirmed_funding(admission['signal_identity'],following,cash,quote)
        self.assertEqual(result['intents'],again['intents']);self.assertEqual(before,obj.export_state())

    def test_deferred_flag_cannot_use_untransferred_reserve_below_floor_but_real_equity_can_clear_it(self):
        day='2026-10-29';at=NOW.replace(day=29);snapshot=broker(now=at,day=day)
        raw=json.loads(snapshot['account']['raw_payload']);raw.update(query_last_seen=True,query_error_rows=0)
        snapshot['account']=envelope(raw)
        cash=funding.begin_cash_observation(funding.initial_state(ACCOUNT,RELEASE,day),snapshot['account'],at)
        calendar,frame,_,meta=fixture()
        obj=runtime.build_weekly19_runtime(runtime.DEFAULT_SETTINGS_ASSET,meta,calendar,frame,snapshot,None,cash,clock=lambda:at)
        obj.open_block_reason='funding_recommendation_deferred_to_friday'
        obj.reconcile_broker_snapshot(broker(balance='120000.00',now=at,day=day),cash)
        self.assertFalse(obj._open_ready());self.assertEqual(obj.confirmed_cash_state['confirmed_topup_fen'],0)
        obj.reconcile_broker_snapshot(broker(balance='151000.00',now=at,day=day),cash)
        self.assertTrue(obj._open_ready());self.assertEqual(obj.open_block_reason,'')
        self.assertEqual(obj.confirmed_cash_state['reserve_remaining_fen'],15000000)

class ProviderChildIntegrationTests(unittest.TestCase):
    opening_and_close=PhysicalChildBatchTests.opening_and_close
    def test_v6_native_query_packets_drive_child_aggregation_restart_and_repeat_idempotence(self):
        from unittest import mock
        import tests.test_weekly19_broker_evidence as source_tests
        import qmt_roll_weekly19_broker_evidence as provider
        import qmt_roll_official_live_execution_ledger as ledger
        obj,plan,_=self.opening_and_close();now=obj.clock()
        with mock.patch.multiple(source_tests,ACCOUNT=ACCOUNT,RELEASE=RELEASE,NOW=now):
            source=source_tests.BrokerEvidenceTest(methodName='runTest');source.setUp();self.addCleanup(source.doCleanups)
            rows=source.batch_ledger()
            def bind(value):
                if isinstance(value,list):return [bind(v) for v in value]
                if not isinstance(value,dict):return value
                result={}
                for key,item in value.items():
                    if key=='signal_identity':result[key]=copy.deepcopy(plan['signal_identity'])
                    elif key=='planned_intent_id':result[key]=plan['intent_id']
                    elif key=='signal_order_id':result[key]=plan['signal_order_id']
                    elif key=='vt_symbol':result[key]=SYMBOL
                    elif key in ('direction','planned_direction'):result[key]='short'
                    elif key in ('account_key','account_fingerprint'):result[key]=ACCOUNT
                    elif key=='material_release_id':result[key]=RELEASE
                    elif key=='source':result[key]='weekly19_risk_reduce'
                    elif key=='target_date':result[key]=plan['target_date']
                    else:result[key]=bind(item)
                if 'expected_children' in result:result['expected_children_sha256']=runtime._hash(result['expected_children'])
                return result
            rows=bind(rows)
            batchid=runtime._hash(dict(target_date=plan['target_date'],slot_type='send_order',usage_before=0,base_events=rows[0]['api_slot_batch_children']))[:24]
            for row in rows:row['api_slot_batch_id']=batchid;row['record_checksum']=ledger._record_checksum(row)
            bindings=provider.derive_order_intent_bindings(rows,expected_account_key=ACCOUNT,material_release_id=RELEASE,execution_profile=source_tests.PROFILE)
            source.account.update(AccountID='fixture-account',Balance=150000.,Available=150000.)
            source.position.update(InvestorID='fixture-account',InstrumentID='rb2612',Position=1,TodayPosition=0,YdPosition=1)
            order1=dict(source.order,InvestorID='fixture-account',InstrumentID='rb2612',Direction='1',CombOffsetFlag='3',
                VolumeTotalOriginal=1,VolumeTraded=1,OrderStatus='0')
            order2=dict(order1,CombOffsetFlag='4',OrderRef='34',OrderSysID='SYS-2',VolumeTraded=0,OrderStatus='3')
            trade1=dict(source.trade,InvestorID='fixture-account',InstrumentID='rb2612',Direction='1',OffsetFlag='3',Price=100.)
            trade2=dict(trade1,OffsetFlag='4',TradeID='TR-2',OrderSysID='SYS-2')
            source.publish(orders=[order1,order2],trades=[trade1])
            policy=source._load_kwargs()
            first_fills=provider.load_broker_fills(source.summary_path,source.manifest_path,bindings,**policy)
            first_orders=provider.load_broker_order_updates(source.summary_path,source.manifest_path,bindings,**policy)
            for fill in first_fills:obj.apply_broker_fill(fill,json.loads(fill['raw_payload'])['signal_identity'])
            for event in first_orders:obj.apply_order_update(event)
            self.assertEqual(obj.strategy.get_pos(SYMBOL),1);self.assertNotIn(plan['signal_order_id'],obj.engine.order_terminal)
            saved=obj.export_state();fresh=broker(positions=[dict(vt_symbol=SYMBOL,direction='long',volume=1)],now=now,day='2026-11-02')
            restored,_=build(fresh,saved,obj.confirmed_cash_state,now=now)
            source.position.update(Position=0,YdPosition=0);order2.update(VolumeTraded=1,OrderStatus='0')
            with mock.patch.object(source_tests,'GENERATION','22222222-3333-4444-8555-666666666666'):
                source.publish(orders=[order1,order2],trades=[trade1,trade2])
                fills=provider.load_broker_fills(source.summary_path,source.manifest_path,bindings,**policy)
                orders=provider.load_broker_order_updates(source.summary_path,source.manifest_path,bindings,**policy)
            for fill in fills:restored.apply_broker_fill(fill,json.loads(fill['raw_payload'])['signal_identity'])
            for event in orders:restored.apply_order_update(event)
            self.assertEqual(restored.strategy.get_pos(SYMBOL),0)
            self.assertEqual(restored.engine.order_terminal[plan['signal_order_id']],'filled')
            self.assertTrue(next(iter(restored.close_lifecycles.values()))['risk_committed'])
            final=restored.export_state()
            for fill in fills:restored.apply_broker_fill(fill,json.loads(fill['raw_payload'])['signal_identity'])
            for event in orders:restored.apply_order_update(event)
            self.assertEqual(final,restored.export_state())

class SourceBarBindingTests(unittest.TestCase):
    def test_all_ohlc_volume_closeoi_are_finite_and_bound_to_approved_source(self):
        obj,bars=build();bar=bars['2026-10-30'][SYMBOL]
        for field,value in [('high_price',999.),('open_price',100.9),('low_price',.1),('volume',float('nan')),
                            ('volume',float('inf')),('volume',0.),('open_interest',987654321.),('open_interest',float('nan')),
                            ('open_interest',-1.)]:
            with self.subTest(field=field,value=value):
                changed=runtime._decode(runtime._encode(bar));setattr(changed,field,value)
                with self.assertRaises(runtime.RuntimeContractError):obj._validate_bars({SYMBOL:changed})
    def test_missing_physical_closeoi_has_no_fallback_but_real_zero_is_valid(self):
        calendar,frame,bars,meta=fixture();snapshot=broker();cash=funding.initial_state(ACCOUNT,RELEASE,'2026-10-30')
        frame['close_oi']=0.
        obj=runtime.build_weekly19_runtime(runtime.DEFAULT_SETTINGS_ASSET,meta,calendar,frame,snapshot,None,cash,clock=lambda:NOW)
        bar=runtime._decode(runtime._encode(bars['2026-10-30'][SYMBOL]));bar.open_interest=0.
        self.assertEqual(obj._validate_bars({SYMBOL:bar}),'2026-10-30')
        bad=runtime.build_weekly19_runtime(runtime.DEFAULT_SETTINGS_ASSET,meta,calendar,frame.drop(columns='close_oi'),snapshot,None,cash,clock=lambda:NOW)
        with self.assertRaisesRegex(runtime.RuntimeContractError,'approved_physical_ohlcvoi_required'):
            bad._validate_bars({SYMBOL:bar})

    def test_runtime_rejects_future_and_same_day_forming_even_with_approved_source_row(self):
        obj,bars=build();bar=runtime._decode(runtime._encode(bars['2026-10-30'][SYMBOL]))
        obj.clock=lambda:NOW.replace(hour=14,minute=59)
        with self.assertRaisesRegex(runtime.RuntimeContractError,'bar_trading_day_not_completed'):
            obj._validate_bars({SYMBOL:bar})
        obj.clock=lambda:NOW
        future=runtime._decode(runtime._encode(bar));future.datetime=datetime(2026,11,2)
        with self.assertRaisesRegex(runtime.RuntimeContractError,'bar_trading_day_not_completed'):
            obj._validate_bars({SYMBOL:future})
