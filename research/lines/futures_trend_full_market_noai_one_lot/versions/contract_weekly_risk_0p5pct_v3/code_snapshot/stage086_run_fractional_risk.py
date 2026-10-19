"""Isolated 0.5% total-equity risk research replay; exact-contract weekly longs, integer quantities."""
from __future__ import annotations
from collections import deque
from contextlib import redirect_stdout,redirect_stderr
from dataclasses import asdict
from datetime import date,datetime
import hashlib,json,os,subprocess,time,inspect
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from stage003_candidate import ROOT,CAPITAL,research_fee
from stage068_fractional_risk import candidate_overrides as budget_candidate_overrides, RISK_FRACTION, _positive_integer
from stage075_fractional_weekly import FullMarketContractWeeklyFractional as FullMarketNoAIOneLot,WeeklyLongExecutionMixin
from stage058_weekly_contract import WeeklyContractTrend
from stage068_fractional_risk import FractionalOpeningRiskMixin
from stage074_pending_close_quantity import PendingCloseQuantityMixin
from stage078_forced_margin_planning import ForcedMarginIntentMixin
from stage085_pending_open_lifecycle import PendingOpenLifecycleMixin,PendingOpenLifecycleEngineMixin
from stage069_quantity_ledger import closed_ledger
import numpy as np
import pandas as pd
from vnpy.trader.constant import Exchange,Interval,Direction,Offset
from vnpy.trader.object import BarData
from vnpy_portfoliostrategy.template import StrategyTemplate
from analyze_qmt_roll_stage502_confirmed_daily_next_real_open_replay import ConfirmedDailyNextRealOpenEngine
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847
from qmt_roll_official_stage78_config import _build_official_stage78_overrides
from run_qmt_roll_stage310_stage78_1_drawdown_gate_engine_validation import _pressure040_overrides
from run_qmt_roll_stage318_supply_demand_headwind_engine_validation import _supply_demand_headwind_overrides
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg
from run_qmt_roll_backtest import build_roll_setting
import qmt_roll_portfolio_strategy as native_strategy
from qmt_roll_official_baseline_identity import assert_official_checkout_matches_active_material
from stage002_market_source import load_source,_meta_epoch,SOURCE_LINE
from stage016_contract_lifecycle import LifecyclePolicy,LifecycleStrategyMixin,LifecycleEngineMixin
from stage024_execution_quotes import load_quantity_execution_overlay

LINE=ROOT/'research/lines/futures_trend_full_market_noai_one_lot'
START=pd.Timestamp('2015-01-01')
END=pd.Timestamp('2026-10-16')
FRACTIONAL_RISK_POLICY=dict(risk_fraction=0.005,equity_basis='causal_marked_total_account_equity',
    signal_budget='signal_equity * 0.005',
    opening_budget='min(original_signal_budget, opening_equity_after_prior_fills_costs * 0.005)',
    rounding='floor_integer_contracts_no_minimum_one',
    opening_order_policy='all_or_none_reject_if_total_stop_risk_exceeds_budget',
    currency_min_max_and_risk_multipliers='replaced_by_fixed_equity_fraction',
    native_quantity_and_margin_gates='preserved_reduce_only',one_lot_cap=False,adds=False)
BASELINE_COMMIT='e553d1703bc4efb9c612143a6c3f2ccc9885f6b3'
BASELINE_MANIFEST_SHA256='859982f079da55aa1292154d5fc9b1004d1f0d5f23f75c4ec58ca892a102cb25'
PRIOR_FAILED_RUN='run_20261020_contract_weekly_risk05_v1'
PRIOR_FAILED_PROTOCOL_SHA256='74bf1c2a7003155cbc4369f59ac8e8f245fa45a9eb3456ef0f048e3fc4708184'
PRIOR_REJECTED_RUN='run_20261020_contract_weekly_risk05_v2'
PRIOR_REJECTED_MANIFEST_SHA256='b5357eef7ec6f3ce9a844bfbf680b7eb5fe24e4fb6e91dec6e87f6ea56933635'
PRIOR_REJECTED_PROTOCOL_SHA256='ccba699bf4b3576d17442c9f655ec7596a385f13750c9c6b39ce50666dd2aa50'
EXECUTION_STATE_POLICY='pending_open_original_receipt_preserved_through_defer_reconcile_rebalance_without_reauthorization; only_truly_deferred_or_preserved_receipts_receive_mapping_validation_before_later_fills; ordinary_first_next_open_unchanged; cached_order_quotes_dispatch_only; funding_actual_plus_valid_unfilled_open_without_reservation_double_count; cluster_pnl_actual_synced_layers_plus_unfilled_close_lots_only; forced_margin_projected_actual_minus_pending_close_plus_unfilled_open; cancel_whole_unfilled_intents_before_any_cash_close; actual_margin_retained_until_real_fills'



def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()


def safe(v):
    if isinstance(v,dict):return {str(k):safe(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [safe(x) for x in v]
    if isinstance(v,(date,datetime,pd.Timestamp)):return v.isoformat()
    if isinstance(v,np.generic):return safe(v.item())
    if isinstance(v,float) and not np.isfinite(v):return None
    return v


def annotate_quote_provenance(rows,market):
    """Export-only labels; never change a valuation, order or financial input."""
    result=[]
    dates={str(vt):pd.DatetimeIndex(pd.to_datetime(frame['date'])).tz_localize(None).normalize().sort_values()
           for vt,frame in market.groupby('vt_symbol')}
    for original in rows:
        row=dict(original)
        current=pd.Timestamp(row['date']).tz_localize(None).normalize()
        available=dates.get(str(row['vt_symbol']),pd.DatetimeIndex([]))
        index=available.searchsorted(current,side='right')-1
        asof=available[index] if index>=0 else None
        row['causal_quote_asof']=asof.date().isoformat() if asof is not None else ''
        row['valuation_proxy']=asof is None or asof<current
        row['quote_datetime_semantics']='engine_event_label_may_be_forward_filled; causal_quote_asof_is_latest_frozen_real_quote_date'
        result.append(row)
    return result


def runtime_failure_snapshot(engine):
    """Capture on_bars failures as well as _fill_order failures, without mutation."""
    s=engine.strategy
    states={}
    for product,state in s.states.items():
        if not state.contract_vt_symbol and not state.layers:continue
        states[product]=dict(contract=state.contract_vt_symbol,direction=state.direction,
            layers=[dict(kind=getattr(layer,'kind',''),direction=layer.direction,volume=layer.volume,
                entry_price=layer.entry_price,stop_price=layer.stop_price,entry_date=str(layer.entry_date),
                signal=layer.signal,synced=layer.entry_price_synced,
                fractional_authorization=asdict(layer.stage068_signal_risk_budget) if hasattr(layer,'stage068_signal_risk_budget') else {})
                for layer in state.layers])
    return dict(date=str(engine.datetime),actual_positions={vt:int(q) for vt,q in s.pos_data.items() if q},
        targets=dict(s.target_data),states=states,pending_close_lots=dict(s.pending_close_lots),
        pending_active_products=sorted(s.pending_active_products),pending_entry_diagnostics=str(s.pending_entry_diagnostics),
        marked_equity=s.estimated_equity,settled_balance=s.settled_balance,total_margin_in_use=s.total_margin_in_use,
        pending_margin_reservation=s.pending_margin_reservation,pending_cluster_margin_reservation=dict(s.pending_cluster_margin_reservation),
        opening_equity=getattr(engine,'opening_equity',None),open_execution_costs=getattr(engine,'open_execution_costs',None),
        forced_margin_events=s.forced_margin_deleverage_events[-12:],
        unfilled_intent_cancellations=getattr(s,'stage078_intent_cancellations',[])[-12:],
        pending_open_events=getattr(s,'stage085_pending_open_events',[])[-12:],
        active_orders=[dict(id=o.vt_orderid,vt_symbol=o.vt_symbol,offset=str(o.offset),direction=str(o.direction),volume=o.volume,signal_date=str(o.datetime)) for o in engine.active_limit_orders.values()])


def pending_open_layer(strategy,vt_symbol,direction):
    state=strategy._find_state_by_contract(vt_symbol)
    if state is None or state.direction!=direction:return None
    layers=[x for x in state.layers if x.direction==direction and not x.entry_price_synced and _positive_integer(x.volume)]
    return layers[0] if len(layers)==1 else None


class CleanExecution:
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.deferred_orders=[]
        self.blocked_open_orders=[]
        self.account_snapshots=[]
        self.held_missing=[]
        self.trade_fee_by_id={}
        self.research_metadata={}
        self.open_day_by_symbol={}
        self.progress_year=None

    def _resolve_trade_price(self,order,bar):
        return float(bar.open_price),'real_clean_daily_next_open',{}

    def cross_delayed_orders(self):
        absent={k:o for k,o in self.active_limit_orders.items()
                if (self.datetime,o.vt_symbol) not in self.history_data or
                float(self.history_data[(self.datetime,o.vt_symbol)].volume)<int(o.volume)}
        for key,order in absent.items():
            self.deferred_orders.append(dict(date=str(self.datetime.date()),order_id=key,vt_symbol=order.vt_symbol,reason='no_real_bar_for_full_integer_quantity',volume=int(order.volume)))
            self.active_limit_orders.pop(key)
        # Real close fills release positions before replacement open fills.
        self.active_limit_orders=dict(sorted(self.active_limit_orders.items(),key=lambda pair:0 if getattr(pair[1],'offset',None)==Offset.CLOSE else 1))
        try:super().cross_delayed_orders()
        finally:self.active_limit_orders.update(absent)

    def prepare_opening_risk(self,dt):
        strategy=self.strategy
        equity=float(getattr(strategy,'settled_balance',self.capital))
        prices={}
        for vt,qty in strategy.pos_data.items():
            if not qty:continue
            prior=self.bars.get(vt)
            raw=self.history_data.get((dt,vt))
            if raw is not None and float(raw.volume)>0:
                mark=float(raw.open_price)
            elif prior is not None:mark=float(prior.close_price)
            else:raise RuntimeError('opening_margin_price_unknown:'+vt)
            previous=float(strategy.last_close_prices.get(vt,prior.close_price if prior is not None else mark))
            equity+=int(qty)*(mark-previous)*self.sizes[vt]
            prices[vt]=mark
        self.opening_equity=equity
        self.open_risk_prices=prices
        self.open_execution_costs=0.0

    def _fill_order(self,order,bar):
        if order.offset==Offset.OPEN:
            if not _positive_integer(order.volume):raise RuntimeError('invalid_integer_open_volume')
            mapping=self.strategy.source_symbol_by_contract
            product=mapping[order.vt_symbol]
            held={vt:int(q) for vt,q in self.strategy.pos_data.items() if q}
            products={mapping[vt] for vt in held}
            reason=''
            if getattr(bar,'execution_only',False):reason='execution_only_quote_no_new_open'
            elif isinstance(self.strategy,FullMarketNoAIOneLot) and pending_open_layer(self.strategy,order.vt_symbol,'long' if order.direction==Direction.LONG else 'short') is None:reason='stale_open_intent'
            elif product in products:reason='existing_actual_product_position'
            elif len(products)>=int(getattr(self.strategy,'max_concurrent_positions',4)):reason='actual_concurrency_limit'
            elif order.vt_symbol in self.research_metadata:
                meta=self.research_metadata[order.vt_symbol]
                margin=0.0
                for vt,qty in held.items():
                    mark=self.open_risk_prices.get(vt)
                    if mark is None:raise RuntimeError('actual_margin_unknown:'+vt)
                    row=self.research_metadata[vt]
                    margin+=abs(qty)*mark*row['size']*row['margin_ratio']
                margin+=int(order.volume)*float(bar.open_price)*meta['size']*meta['margin_ratio']
                equity=float(self.opening_equity)-float(self.open_execution_costs)
                multiplier=float(getattr(self.strategy,'stage830_broker_margin_multiplier',1.65))
                cap=float(getattr(self.strategy,'stage830_projected_broker10_margin_to_equity_cap',1.0))
                if margin*multiplier>equity*cap:reason='actual_broker_margin_cap'
            if reason:
                self.blocked_open_orders.append(dict(date=str(self.datetime.date()),order_id=order.vt_orderid,vt_symbol=order.vt_symbol,reason=reason))
                if reason=='stale_open_intent':
                    self.strategy.set_target(order.vt_symbol,0)
                    self.cancel_order(self.strategy,order.vt_orderid)
                return
        elif order.offset==Offset.CLOSE:
            current=int(self.strategy.get_pos(order.vt_symbol))
            closing_long=order.direction==Direction.SHORT and current>0
            closing_short=order.direction==Direction.LONG and current<0
            if not (closing_long or closing_short) or int(order.volume)>abs(current):
                raise RuntimeError('invalid_actual_close:'+order.vt_symbol)
        before=set(self.trades)
        self.current_fill_order=order
        try:result=super()._fill_order(order,bar)
        except Exception as exc:
            self.failure_snapshot=dict(date=str(self.datetime),error=repr(exc),order=dict(id=order.vt_orderid,vt_symbol=order.vt_symbol,direction=str(order.direction),offset=str(order.offset),volume=order.volume,signal_date=str(order.datetime)),
                positions={k:int(v) for k,v in self.strategy.pos_data.items() if v},
                states={k:dict(contract=v.contract_vt_symbol,direction=v.direction,layers=[dict(volume=x.volume,signal=x.signal,entry_date=str(x.entry_date),synced=x.entry_price_synced) for x in v.layers]) for k,v in getattr(self.strategy,'states',{}).items() if v.contract_vt_symbol})
            raise
        finally:self.current_fill_order=None
        for key in set(self.trades)-before:
            trade=self.trades[key]
            trade.execution_only_quote=bool(getattr(bar,"execution_only",False))
            trade.execution_quote_class=str(getattr(bar,"execution_quote_class","accepted_clean"))
            trade.execution_evidence_id=str(getattr(bar,"execution_evidence_id",""))
            if not hasattr(self,'open_risk_prices'):self.open_risk_prices={}
            self.open_risk_prices[trade.vt_symbol]=float(trade.price)
            cost=float(self.trade_fee_by_id.get(key,0))+int(trade.volume)*self.sizes[trade.vt_symbol]*self.slippages[trade.vt_symbol]
            self.open_execution_costs=getattr(self,'open_execution_costs',0.0)+cost
        return result

    def new_bars(self,dt):
        self.prepare_opening_risk(dt)
        for vt,pos in self.strategy.pos_data.items():
            if pos and (dt,vt) not in self.history_data:
                self.held_missing.append(dict(date=str(dt.date()),vt_symbol=vt,position=int(pos)))
        super().new_bars(dt)
        if self.strategy.inited and pd.Timestamp(dt).tz_localize(None)>=START:
            positions={k:int(v) for k,v in self.strategy.pos_data.items() if v}
            product_volumes={}
            for vt,qty in positions.items():
                product=self.strategy.source_symbol_by_contract[vt]
                product_volumes[product]=product_volumes.get(product,0)+1
            if any(q>1 for q in product_volumes.values()):
                self.failure_snapshot=dict(date=str(dt.date()),positions=positions,product_volumes=product_volumes,
                    targets=dict(self.strategy.target_data),
                    states={k:dict(contract=v.contract_vt_symbol,direction=v.direction,layers=[dict(kind=x.kind,volume=x.volume,entry_date=str(x.entry_date)) for x in v.layers]) for k,v in self.strategy.states.items() if v.contract_vt_symbol},
                    active_orders=[dict(id=o.vt_orderid,vt_symbol=o.vt_symbol,direction=str(o.direction),offset=str(o.offset),volume=o.volume,signal_date=str(o.datetime)) for o in self.active_limit_orders.values()],
                    last_trades=[dict(id=t.vt_tradeid,vt_symbol=t.vt_symbol,direction=str(t.direction),offset=str(t.offset),volume=t.volume,datetime=str(t.datetime),price=t.price) for t in list(self.trades.values())[-60:]])
                raise RuntimeError('multiple_actual_contracts_per_product:'+str(self.failure_snapshot))
            self.account_snapshots.append(dict(date=str(dt.date()),strategy_equity=self.strategy.estimated_equity,
                margin=self.strategy.total_margin_in_use,positions=json.dumps(positions,sort_keys=True),
                actual_margin=sum(self.strategy._actual_margin_by_cluster(self.bars).values()),
                actual_plus_pending_margin=self.strategy._estimate_margin_usage(self.bars),
                reserved_margin=self.strategy._reserved_margin_in_use(),
                pending_margin_reservation=self.strategy.pending_margin_reservation,
                funding_by_cluster_json=json.dumps(self.strategy._estimate_margin_usage_by_cluster(self.bars),sort_keys=True),
                actual_pnl_by_cluster_json=json.dumps(self.strategy._estimate_unrealized_pnl_by_cluster(self.bars),sort_keys=True)))
        if dt.year!=self.progress_year:
            self.progress_year=dt.year
            print(f'PROGRESS {dt.date()} fills={len(self.trades)}',flush=True)


class FullMarketDailyEngine(PendingOpenLifecycleEngineMixin,WeeklyLongExecutionMixin,FractionalOpeningRiskMixin,LifecycleEngineMixin,CleanExecution,ConfirmedDailyNextRealOpenEngine):pass
class FullMarketStrictEngine(PendingOpenLifecycleEngineMixin,WeeklyLongExecutionMixin,FractionalOpeningRiskMixin,LifecycleEngineMixin,CleanExecution,s847.Stage847StopRetryEngine):pass


def accounting_date(trade):
    value=getattr(trade,'trading_date',None)
    return pd.Timestamp(value if value is not None else trade.datetime).date()


class FeeStrategy(PendingOpenLifecycleMixin,ForcedMarginIntentMixin,PendingCloseQuantityMixin,LifecycleStrategyMixin,FullMarketNoAIOneLot):
    def on_bars(self,bars):
        result=self.apply_lifecycle_targets(bars)
        if result is None:return
        today,forced=result;original=self.daily_mapping.get(today,{})
        policy=self.strategy_engine.lifecycle_policy
        next_day=policy.next_session(today)
        self.daily_mapping[today]={p:vt for p,vt in original.items() if p not in forced and policy.entry_allowed(vt,next_day)}
        try:return self._accounted_on_bars(bars)
        finally:self.daily_mapping[today]=original

    def _accounted_on_bars(self,bars):
        signal_bars={vt:bar for vt,bar in bars.items() if not getattr(bar,'execution_only',False)}
        if signal_bars:
            super(LifecycleStrategyMixin,self).on_bars(signal_bars)
        elif bars:
            # A quote-only batch still has an accounting boundary, even though
            # there is no bar eligible to update indicators or create signals.
            date=next(iter(bars.values())).datetime.strftime('%Y-%m-%d')
            self.current_bar_date=pd.Timestamp(date)
            self.estimated_equity=self._estimate_equity({})
            self.settled_balance=self.estimated_equity
            self.equity_start_positions={vt:int(q) for vt,q in self.pos_data.items()}
            self.equity_settlement_date=date
            # Quote-only sessions still dispatch existing-position CLOSE orders.
            close_bars={vt:bar for vt,bar in bars.items() if self.get_pos(vt) and self.get_target(vt)==0}
            StrategyTemplate.rebalance_portfolio(self,close_bars)
        # The account already booked these quotes via _estimate_equity; advance
        # their settlement marks too, so tomorrow cannot book the holding leg twice.
        self.last_close_prices.update({vt:float(bar.close_price) for vt,bar in bars.items() if getattr(bar,'execution_only',False)})

    def update_trade(self,trade):
        engine=self.strategy_engine
        if not hasattr(trade,'signal_datetime'):
            order=getattr(engine,'current_fill_order',None) or getattr(engine,'limit_orders',{}).get(trade.vt_orderid)
            if order is not None:
                trade.order_reissue_datetime=order.datetime
                layer=pending_open_layer(self,trade.vt_symbol,'long' if trade.direction==Direction.LONG else 'short') if trade.offset==Offset.OPEN else None
                if trade.offset==Offset.OPEN and layer is None:raise ValueError('unbound_actual_open:'+trade.vt_tradeid)
                trade.signal_datetime=pd.Timestamp(layer.entry_date).to_pydatetime() if layer is not None else order.datetime
                trade.signal_order_id=order.vt_orderid
                trade.trading_date=engine.datetime.date()
                if layer is not None:trade.signal=layer.signal
        dt=accounting_date(trade)
        meta=engine.research_metadata[trade.vt_symbol]
        fee=research_fee(meta,price=trade.price,volume=int(trade.volume),
            offset='open' if trade.offset==Offset.OPEN else 'close',
            same_day=engine.open_day_by_symbol.get(trade.vt_symbol)==dt)
        engine.trade_fee_by_id[trade.vt_tradeid]=fee
        super().update_trade(trade)
        if trade.offset==Offset.OPEN:engine.open_day_by_symbol[trade.vt_symbol]=dt
        elif self.get_pos(trade.vt_symbol)==0:engine.open_day_by_symbol.pop(trade.vt_symbol,None)

    def _trade_cost(self,trade):
        e=self.strategy_engine
        return e.trade_fee_by_id[trade.vt_tradeid]+int(trade.volume)*self.get_size(trade.vt_symbol)*e.slippages[trade.vt_symbol]


def _metadata(frame):
    meta={k:dict(zip(frame.vt_symbol,frame[col])) for k,col in
          [('sizes','size'),('priceticks','pricetick'),('slippages','slippage'),('margin_ratios','margin_ratio')]}
    meta.update(vt_symbols=frame.vt_symbol.tolist(),product_symbols=sorted(frame.product_vt_symbol.unique()),
        rates={vt:0.0 for vt in frame.vt_symbol},metadata_sources={vt:'research_static_disclosed' for vt in frame.vt_symbol},
        source_symbol_by_contract=dict(zip(frame.vt_symbol,frame.product_vt_symbol)))
    return meta


def candidate_overrides(universe_path,product_count=93):
    return budget_candidate_overrides(universe_path,product_count)


def build_settings(metadata,universe):
    # Preserve the full formal engine profile, including Stage653 margin guards.
    # Replace only the side-effectful legacy input builder with its pure form.
    original=stage819_cfg.build_official_candidate_stage819_30w_overrides
    stage819_cfg.build_official_candidate_stage819_30w_overrides=lambda:stage819_cfg._build_official_candidate_stage819_30w_overrides(universe,Path('/unused/no_ai.csv'))
    try:profile=s847._c9_profile(metadata)
    finally:stage819_cfg.build_official_candidate_stage819_30w_overrides=original
    base={**_build_official_stage78_overrides(universe,Path('/unused/no_ai.csv')),
          **_pressure040_overrides(),**_supply_demand_headwind_overrides()}
    settings=build_roll_setting(metadata['margin_ratios'],risk_ratio=0.045*profile['spec'].capital.risk_multiplier,
        strategy_overrides={**base,**profile['spec'].overrides,**candidate_overrides(universe,len(metadata["product_symbols"]))})
    settings.update(mapping_csv_path=str(LINE/'outputs/inputs/mapping.csv'),trade_start_date=str(START.date()),capital_base=CAPITAL)
    return settings


def supply_settings(settings,policy):
    result=dict(settings)
    if policy=='disabled-research':
        result['enable_supply_demand_headwind_filter']=False
    elif policy=='require-frozen':
        if result.get('enable_supply_demand_headwind_filter') and not Path(result['supply_demand_signal_path']).is_file():
            raise ValueError('missing_frozen_supply: restore the frozen CSV or obtain explicit research-only disable authorization')
    else:raise ValueError('unknown_supply_policy')
    return result


def load_execution_overlay(market,contracts):
    csv=LINE/'outputs/expiry_execution_overlay.csv'
    receipt=LINE/'outputs/expiry_execution_overlay_manifest.json'
    evidence=json.loads(receipt.read_text())
    if sha(csv)!=evidence['output']['sha256']:raise RuntimeError('execution_overlay_changed')
    overlay=pd.read_csv(csv)
    if not overlay.execution_only.eq(True).all() or overlay.allow_new_open.ne(False).any():raise RuntimeError('invalid_overlay_qualification')
    overlay=overlay[overlay.vt_symbol.isin(contracts.vt_symbol)].copy()
    regular=market.copy();regular['execution_only']=False
    combined=pd.concat([regular,overlay],ignore_index=True,sort=False)
    if combined.duplicated(['vt_symbol','date']).any():raise RuntimeError('overlay_overlaps_clean')
    combined=combined.sort_values(['vt_symbol','date']).reset_index(drop=True)
    binding=dict(csv_sha256=sha(csv),manifest_sha256=sha(receipt),bound_rows=len(overlay),total_rows=evidence['rows'],
        policy='existing_position_execution_and_valuation_only_not_signals_or_new_open')
    return combined,binding


def run(mode,output,*,supply_policy='require-frozen'):
    if output.exists():raise FileExistsError('refusing to overwrite a financial run')
    output.mkdir(parents=True)
    started=time.monotonic()
    if sha(LINE/'outputs'/PRIOR_REJECTED_RUN/'manifest.json')!=PRIOR_REJECTED_MANIFEST_SHA256:raise RuntimeError('rejected_v2_manifest_changed')
    if sha(LINE/'outputs'/PRIOR_REJECTED_RUN/'protocol.json')!=PRIOR_REJECTED_PROTOCOL_SHA256:raise RuntimeError('rejected_v2_protocol_changed')
    if sha(LINE/'outputs'/PRIOR_FAILED_RUN/'protocol.json')!=PRIOR_FAILED_PROTOCOL_SHA256:raise RuntimeError('failed_v1_evidence_changed')
    identity=asdict(assert_official_checkout_matches_active_material(ROOT))
    market,mapping,contracts,source_manifest=load_source()
    market,overlay_binding=load_execution_overlay(market,contracts)
    market["quote_class"]=market.execution_only.map({True:"expiry_oi_execution_only",False:"accepted_clean"})
    quantity_dir=LINE/"outputs/stage023_quantity_price_overlay"
    market,quantity_binding=load_quantity_execution_overlay(market,contracts,quantity_dir/"execution_quotes.csv",quantity_dir/"receipt.json")
    quantity_receipt=json.loads((quantity_dir/"receipt.json").read_text())
    if quantity_receipt["scope"]["metadata_sha256"]!=sha(LINE/"outputs/inputs/contract_metadata.csv"):raise ValueError("quantity_metadata_binding_mismatch")
    if quantity_receipt["scope"]["expiry_overlay_sha256"]!=sha(LINE/"outputs/expiry_execution_overlay.csv"):raise ValueError("quantity_expiry_binding_mismatch")
    rq=SOURCE_LINE/"stage265_deep_daily/rqalpha"
    instruments_path=rq/"futures_metadata.json";calendar_path=rq/"trading_dates.npy"
    instruments={_meta_epoch(row):row for row in json.loads(instruments_path.read_text()) if _meta_epoch(row)}
    contracts["product_class"]=[instruments[str(epoch)]["product"] for epoch in contracts.contract_epoch_id]
    calendar=pd.to_datetime(np.load(calendar_path).astype(str),format="%Y%m%d").strftime("%Y-%m-%d").tolist()
    lifecycle=LifecyclePolicy(contracts.set_index("vt_symbol").to_dict("index"),calendar)
    lifecycle_sources={str(p):sha(p) for p in [instruments_path,calendar_path]}
    metadata=_metadata(contracts)
    universe=LINE/'outputs/inputs/product_universe.csv'
    settings=supply_settings(build_settings(metadata,universe),supply_policy)
    baseline_directory=LINE/'outputs/run_20261019_contract_weekly_long_v1'
    if sha(baseline_directory/'manifest.json')!=BASELINE_MANIFEST_SHA256:raise RuntimeError('fractional_baseline_identity_mismatch')
    baseline_manifest=json.loads((baseline_directory/'manifest.json').read_text())
    for name,digest in baseline_manifest['hashes'].items():
        if sha(baseline_directory/name)!=digest:raise RuntimeError('fractional_baseline_file_changed:'+name)
    for key,observed in [('source_manifest',source_manifest),('expiry_execution_overlay',overlay_binding),
                         ('quantity_execution_overlay',quantity_binding),('lifecycle_sources',lifecycle_sources)]:
        if baseline_manifest[key]!=observed:raise RuntimeError('fractional_shared_input_mismatch:'+key)
    if int(settings["max_concurrent_positions"])!=len(metadata["product_symbols"]):raise RuntimeError("count_capacity_mismatch")
    if mode=='daily-proxy':
        settings.update(enable_stage827_intraday_c2_stop=False,enable_stage847_half_r_stop_retry=False)
    parameter_changes={key:(baseline_manifest['parameters'].get(key),value) for key,value in settings.items() if baseline_manifest['parameters'].get(key)!=value}
    expected_changes={'max_position_size':(1,2147483647),'stage068_risk_fraction':(None,0.005)}
    if parameter_changes!=expected_changes or set(baseline_manifest['parameters'])-set(settings):raise RuntimeError('unexpected_fractional_parameter_changes:'+repr(parameter_changes))
    engine=(FullMarketDailyEngine if mode=='daily-proxy' else FullMarketStrictEngine)({})
    engine.weekly_contract=WeeklyContractTrend(market,contracts,calendar)
    engine.lifecycle_policy=lifecycle
    engine.research_metadata=contracts.set_index('vt_symbol').to_dict('index')
    engine.output=lambda msg:print(msg,flush=True)
    engine.set_parameters(vt_symbols=metadata['vt_symbols'],interval=Interval.DAILY,
        start=datetime(2014,1,1),end=END.to_pydatetime(),rates=metadata['rates'],slippages=metadata['slippages'],
        sizes=metadata['sizes'],priceticks=metadata['priceticks'],capital=CAPITAL)
    # Bind metadata only inside this isolated process; never alter official files.
    native_strategy.build_contract_metadata=lambda *a,**kw:metadata
    engine.add_strategy(FeeStrategy,settings)
    for r in market.itertuples():
        symbol,ex=r.vt_symbol.split('.')
        dt=pd.Timestamp(r.date).to_pydatetime().replace(tzinfo=ZoneInfo('Asia/Shanghai'))
        b=BarData(symbol=symbol,exchange=Exchange(ex),datetime=dt,interval=Interval.DAILY,
            open_price=float(r.open),high_price=float(r.high),low_price=float(r.low),close_price=float(r.close),
            volume=float(r.volume),open_interest=float(r.close_oi),gateway_name='RESEARCH_CLEAN_READ_ONLY')
        b.execution_only=bool(getattr(r,'execution_only',False))
        b.execution_quote_class=str(getattr(r,"quote_class","accepted_clean"))
        evidence_id=getattr(r,"evidence_id",None)
        b.execution_evidence_id="" if pd.isna(evidence_id) else str(evidence_id)
        engine.history_data[(dt,r.vt_symbol)]=b;engine.dts.add(dt)
    manifest=dict(run_id=output.name,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True,cwd=ROOT).strip(),
        start=str(START.date()),end=str(END.date()),parameters=settings,mode=mode,official_material_identity=identity,
        source_manifest=source_manifest,expiry_execution_overlay=overlay_binding,supply_policy=supply_policy,production_qualified=False,order_api_calls=0,market_downloads=0,
        baseline_commit=BASELINE_COMMIT,baseline_run_manifest_sha256=BASELINE_MANIFEST_SHA256,
        fractional_risk_policy=FRACTIONAL_RISK_POLICY,position_volume_cap_removed=True,fractional_risk_budget_enabled=True,
        prior_failed_run=PRIOR_FAILED_RUN,prior_failed_protocol_sha256=PRIOR_FAILED_PROTOCOL_SHA256,
        prior_rejected_run=PRIOR_REJECTED_RUN,prior_rejected_manifest_sha256=PRIOR_REJECTED_MANIFEST_SHA256,prior_rejected_protocol_sha256=PRIOR_REJECTED_PROTOCOL_SHA256,execution_state_policy=EXECUTION_STATE_POLICY,
        previous_weekly_main_commit='12f9d3500305ad0da47e092c8c39177459d228ec',previous_weekly_main_manifest_sha256='7e6f2647de1d99253ba2cbade3e0852158d50d3cbfde19e8da4afdba6f16fed4',
        weekly_feature_export_scope='queried_contracts_complete_local_weeks',long_weekly_filter=True,weekly_policy=dict(periods=[5,10,20,40],comparison='ma5>ma10>ma20>ma40',
            source='exact_traded_contract_unadjusted_accepted_clean',signal_phase='completed_week_at_signal_close',
            execution_phase='completed_week_strictly_before_fill_day',minimum_valid_weeks=40,
            missing_week='fail_closed_do_not_drop',applies_to='all_long_open_including_rollover',
            exclude_env_probe=True,shorts_and_all_closes_unchanged=True),
        position_count_limit_removed=True,native_risk_budget_restored=False,one_lot_is_maximum_not_fixed=False,next_open_risk_recheck=True,lifecycle_sources=lifecycle_sources,quantity_execution_overlay=quantity_binding,
        lifecycle_policy=dict(index_expiry_buffer_sessions=1,non_index_expiry_buffer_sessions=10,
                              non_index_delivery_month_buffer_sessions=2,next_open_intent_lead_sessions=1),
        boundaries=[
          "用户指定仅开多新增周均线MA5>MA10>MA20>MA40严格多头排列，至少40根有效完成周收盘；不足/相等/坏周不压缩、不造价，拒绝开多。空头开仓和全部平仓不加此限制，env_probe共用环境输入保持原逻辑；组合现金路径仍可能间接改变空头成交。",
          "周线门仅使用当前交易合约自身accepted-clean周收盘，禁止主力连续、其他合约或换月拼接补历史；新合约不足40有效周直接不开多。实际交易合约选择仍沿用原因果主力映射，但该映射不参与周均线计算。独立完整交易日历定义周末会话，整周休市不造K，周五假期可周四完成。",
          "收盘信号可用当日刚完成周；实际开盘只用严格早于成交日已完成周。所有开多含移仓、旧单重挂同时核原信号周授权及开盘前最新完成周，不能用成交日全天close偷看。只加开仓门，不因周线转弱强平已有多仓。",
          "每笔开仓风险预算改为信号时账户总权益(含浮盈亏)的0.5%=0.005，100万为5000元；不再限定1手，按原有效初始止损距离向下取整，不足1手不开。旧风险金额min/max、各risk-mode比例、streak/overheat/30d货币倍率不再改写该固定预算，保留raw诊断；原数量、环境、相关、集群、ATR及资金保证金闸门仍按新预算依序执行且只能减量。",
          "所有新开含移仓于实际开盘按冻结原止损复核整笔风险=成交手数×每手风险，必须不大于min(原信号0.5%预算,因果开盘账户权益扣前序成交费用后的0.5%预算)；超额整单拒绝、不部分缩单或重新扩大授权，止损已穿越/授权缺失/非正权益均拒绝。止损预算不保证跳空退出的实际亏损上限。",
          "开盘拒单仅清理本未成交意向/target/诊断，不擦除真实持仓；原信号budget和整数手数/合约/方向/原止损均须绑定。实际保证金按全部成交手数计算，已持仓和pending意向仍占用资金。保留RSI部分平仓，缺bar延迟平仓不能把已减的layer重新补回；多手账本按整entry聚合，不把每手或每次分平当独立胜率样本。",
          "独立价格共识退出报价层仍只供已有仓位退出/估值，不进入信号/新开/主力；量仓有争议不认证真实总量。所有逐日全单成交至少要求冻结bar所示正量/多源保守最小量足够本单全部手数，否则保留延迟意向，不造成交或强制结算；此下界非盘口/排队或真实冲击模型。强制保证金减仓仅在独立规划上下文计算actual扣有效待平量再加未成交开仓意向，先整单撤未成交意向、仅对真实剩余层排平；真实保证金与持仓直到实际成交仍保留，避免虚构平仓及重复过量排单，原阈值/优先级不变。",
          "延期OPEN只有存在同合约/方向/整数手数的真实活动委托且原信号预算/止损/周线授权有效时保留原层；禁止新flat计划覆盖。缺bar或量不足不重授权，缓存价只用于派单/估值、不进入指标或成交；映射变化/生命周期截止/授权失效完整取消并归档。缓存估值quote_datetime可能是引擎forward-fill事件日，causal_quote_asof另标原始真实报价日。",
          "本次修复到期生命周期：股指在最后交易日前1交易日、非股指在名义月首前2交易日与到期前10交易日的较早日退出；提前1交易日发单，截止仍持仓硬失败。固定研究运营政策，非历史法规完整复刻，不参与收益调参。",
          "逐笔图中的MA按复盘价格上下文计算，可含退出报价；策略实际指标仍只用accepted clean，两者不能混为信号计算证据。",
          "用户授权取消最多4品种限制：native名额兼容设为全市场93品种自然容量，环境权重不再缩减品种数；实际同产品只持一个交易合约、禁止加仓，手数由0.5%预算和资金/保证金风控决定。",'静态合约规格、保证金及费用快照，非逐历史日PIT交易所账单。',
          '133条到期日OHLCV双源一致但OI冲突记录，仅用于已有仓位委托成交和估值；不进入信号或新开仓，不使用结算字段伪造成交。',
          '本研究主力由前一源交易日持仓量/成交量确定，不是正式冻结主力映射。',
          '日线近似关闭C2日内止损与C9的0.5R日内止损/重试；其余日线信号、退出和风控沿用Stage037。' if mode=='daily-proxy' else 'C9分钟规则严格缺失即停止，不允许降级。',
          '缺日线不生成信号、不允许成交；已有仓位用上次收盘估值并持续占用实际手数、并发和保证金；未获真实平仓或结算的残余仓会限制账户后续交易，此估值不可当作可实现收益。',
          '用户单独授权后停用供需过滤：本机缺冻结供需signal CSV。' if supply_policy=='disabled-research' else '供需过滤使用冻结CSV；本次未停用。'])
    (output/'protocol.json').write_text(json.dumps(safe(manifest),ensure_ascii=False,indent=2))
    pd.DataFrame(lifecycle.rows.values()).to_csv(output/'lifecycle_deadlines.csv',index=False)
    code_start={str(p):sha(p) for p in [Path(__file__),Path(__file__).with_name('stage003_candidate.py'),Path(__file__).with_name('stage058_weekly_contract.py'),Path(__file__).with_name('stage075_fractional_weekly.py'),Path(__file__).with_name('stage068_fractional_risk.py'),Path(__file__).with_name('stage069_quantity_ledger.py'),Path(__file__).with_name('stage074_pending_close_quantity.py'),Path(__file__).with_name('stage078_forced_margin_planning.py'),Path(__file__).with_name('stage085_pending_open_lifecycle.py'),Path(__file__).with_name('stage002_market_source.py'),Path(__file__).with_name('stage016_contract_lifecycle.py'),Path(__file__).with_name('stage004_run.py'),Path(__file__).with_name('stage024_execution_quotes.py'),Path(__file__).with_name('stage023_quantity_price_overlay.py')]}
    for cls in (*FeeStrategy.__mro__,*type(engine).__mro__):
        if cls.__module__.startswith(('qmt_roll','analyze_qmt','vnpy_portfoliostrategy')):
            p=Path(inspect.getfile(cls));code_start[str(p)]=sha(p)
    (output/'code_start_hashes.json').write_text(json.dumps(code_start,indent=2))
    snapshots_dir=output/'code_snapshot';snapshots_dir.mkdir()
    for filename in code_start:
        original=Path(filename)
        (snapshots_dir/original.name).write_bytes(original.read_bytes())
    with (output/'engine.log').open('w',buffering=1) as log,redirect_stdout(log),redirect_stderr(log):
        engine.run_backtesting()
        if pd.Timestamp(engine.datetime).tz_localize(None).normalize()!=END:
            failure=dict(status='failed_before_complete',date=str(engine.datetime),snapshot=runtime_failure_snapshot(engine),last_fill_failure_snapshot=getattr(engine,'failure_snapshot',{}),financial_metrics_valid=False)
            failure['active_orders']=[dict(id=o.vt_orderid,vt_symbol=o.vt_symbol,offset=str(o.offset),direction=str(o.direction),volume=o.volume,signal_date=str(o.datetime)) for o in engine.active_limit_orders.values()]
            pd.DataFrame([dict(trade_id=t.vt_tradeid,datetime=str(t.datetime),vt_symbol=t.vt_symbol,direction=str(t.direction),offset=str(t.offset),volume=t.volume,price=t.price,signal=str(getattr(t,'signal',''))) for t in engine.trades.values()]).to_csv(output/'failed_prefix_trades.csv',index=False)
            pd.DataFrame(engine.lifecycle_events).to_csv(output/'failed_lifecycle_events.csv',index=False)
            (output/'failure_snapshot.json').write_text(json.dumps(safe(failure),ensure_ascii=False,indent=2))
            raise RuntimeError('partial_replay:'+str(engine.datetime))
        text=log.name
        raw=engine.calculate_result()
    if raw is None or raw.empty:raise RuntimeError('no_completed_ledger')
    if any(sha(path)!=digest for path,digest in code_start.items()):raise RuntimeError('code_changed_during_replay')
    logs=(output/'engine.log').read_text()
    if 'Traceback (most recent call last)' in logs or '触发异常' in logs:raise RuntimeError('caught_engine_exception')
    rows=[]
    for trade in engine.trades.values():
        meta=engine.research_metadata[trade.vt_symbol]
        rows.append(dict(trade_id=trade.vt_tradeid,datetime=trade.datetime.isoformat(),date=str(accounting_date(trade)),
            vt_symbol=trade.vt_symbol,direction='long' if trade.direction==Direction.LONG else 'short',
            offset='open' if trade.offset==Offset.OPEN else 'close',volume=int(trade.volume),price=trade.price,
            signal=str(getattr(trade,'signal','')),signal_order_id=str(getattr(trade,'signal_order_id','')),signal_datetime=str(getattr(trade,'signal_datetime','')),order_reissue_datetime=str(getattr(trade,'order_reissue_datetime','')),
            execution_only_quote=bool(getattr(trade,'execution_only_quote',False)),execution_quote_class=str(getattr(trade,'execution_quote_class','accepted_clean')),execution_evidence_id=str(getattr(trade,'execution_evidence_id','')),
            commission=engine.trade_fee_by_id[trade.vt_tradeid],slippage=int(trade.volume)*meta['size']*meta['slippage'],
            exit_reason=engine.strategy.trade_reason_by_trade_id.get(trade.vt_tradeid,''),
            stage068_open_budget=getattr(trade,'stage068_budget',None),stage068_entry_risk=getattr(trade,'stage068_entry_risk',None),
            stage068_risk_per_contract=getattr(trade,'stage068_risk_per_contract',None),
            stage068_signal_snapshot=json.dumps(safe(getattr(trade,'stage068_signal_snapshot',{})),sort_keys=True),
            stage059_weekly_signal_snapshot=json.dumps(safe(getattr(trade,'stage059_weekly_signal_snapshot',{})),sort_keys=True),
            stage059_weekly_open_snapshot=json.dumps(safe(getattr(trade,'stage059_weekly_open_snapshot',{})),sort_keys=True)))
    trades=pd.DataFrame(rows)
    if not trades.volume.map(_positive_integer).all():raise RuntimeError('non_integer_or_nonpositive_fill')
    daily=raw.loc[(raw.index>=START.date())&(raw.index<=END.date())].copy()
    fees=trades.groupby('date').commission.sum();daily['commission']=[fees.get(str(d),0.0) for d in daily.index]
    daily['net_pnl']=daily.total_pnl-daily.commission-daily.slippage
    daily['equity']=CAPITAL+daily.net_pnl.cumsum()
    if any(sha(path)!=digest for path,digest in lifecycle_sources.items()):raise RuntimeError("lifecycle_sources_changed")
    if sha(quantity_dir/"execution_quotes.csv")!=quantity_binding["csv_sha256"] or sha(quantity_dir/"receipt.json")!=quantity_binding["manifest_sha256"]:raise RuntimeError("quantity_overlay_changed_during_replay")
    engine.daily_df=daily
    statistics=engine.calculate_statistics(daily,output=False)
    snapshots=pd.DataFrame(engine.account_snapshots).set_index('date')
    differences=np.abs(daily.equity.to_numpy()-snapshots.reindex([str(d) for d in daily.index]).strategy_equity.to_numpy())
    account_error=float(np.nanmax(differences))
    if not np.isfinite(differences).all() or account_error>1e-5:raise RuntimeError(f'strategy_account_disagreement:{account_error}')
    closed,residual=closed_ledger(trades,engine.research_metadata)
    annual=daily.groupby(pd.to_datetime(daily.index).year).agg(net_pnl=('net_pnl','sum'),commission=('commission','sum'),slippage=('slippage','sum'),trade_count=('trade_count','sum'))
    annual['start_equity']=CAPITAL+annual.net_pnl.cumsum()-annual.net_pnl;annual['return_pct']=annual.net_pnl/annual.start_equity*100
    wins=closed.loc[closed.net_pnl>0,'net_pnl'];losses=closed.loc[closed.net_pnl<0,'net_pnl']
    summary=dict(statistics,performance_certifiable=True,performance_scope='daily_approximation_fractional_risk_0p5pct_exact_contract_weekly_long_ma5_10_20_40',
        long_weekly_filter=True,weekly_policy=manifest['weekly_policy'],baseline_commit=manifest['baseline_commit'],
        baseline_run_manifest_sha256=BASELINE_MANIFEST_SHA256,fractional_risk_policy=FRACTIONAL_RISK_POLICY,
        fractional_risk_budget_enabled=True,position_volume_cap_removed=True,execution_state_policy=EXECUTION_STATE_POLICY,
        prior_failed_run=PRIOR_FAILED_RUN,prior_failed_protocol_sha256=PRIOR_FAILED_PROTOCOL_SHA256,
        prior_rejected_run=PRIOR_REJECTED_RUN,prior_rejected_manifest_sha256=PRIOR_REJECTED_MANIFEST_SHA256,prior_rejected_protocol_sha256=PRIOR_REJECTED_PROTOCOL_SHA256,
        previous_weekly_main_commit=manifest['previous_weekly_main_commit'],previous_weekly_main_manifest_sha256=manifest['previous_weekly_main_manifest_sha256'],
        weekly_signal_candidates=len(getattr(engine.strategy,'weekly_signal_audit',[])),
        weekly_budget_eligible_long_signal_rejections=sum(x['native_selected_volume']>0 and not x['weekly_allowed'] for x in getattr(engine.strategy,'weekly_signal_audit',[])),
        weekly_execution_checks=len(engine.weekly_execution_audit),weekly_execution_rejections=sum(not x['weekly_allowed'] for x in engine.weekly_execution_audit),
        actual_long_open_count=int(((trades.offset=='open')&(trades.direction=='long')).sum()),
        actual_short_open_count=int(((trades.offset=='open')&(trades.direction=='short')).sum()),
        actual_long_weekly_violations=sum(not (json.loads(t.stage059_weekly_signal_snapshot).get('allowed') and json.loads(t.stage059_weekly_open_snapshot).get('allowed')) for t in trades[(trades.offset=='open')&(trades.direction=='long')].itertuples()),
        native_risk_budget_restored=False,one_lot_is_maximum_not_fixed=False,next_open_risk_recheck=True,
        open_budget_checks=len(engine.open_budget_audit),open_budget_rejections=sum(not x['filled'] for x in engine.open_budget_audit),
        forced_margin_unfilled_intent_cancellations=len(getattr(engine.strategy,'stage078_intent_cancellations',[])),
        pending_open_lifecycle_events=len(getattr(engine.strategy,'stage085_pending_open_events',[])),
        actual_open_budget_violations=sum(x['total_risk']>x['opening_budget'] for x in engine.open_budget_audit if x['filled']),
        position_count_limit_removed=True,last_fill_date=str(trades.date.max()),
        max_actual_products=int(max(len(json.loads(x)) for x in snapshots.positions)),
        max_lots_per_product=int(max(max([abs(v) for v in json.loads(x).values()] or [0]) for x in snapshots.positions)),
        total_open_contracts=int(trades.loc[trades.offset=='open','volume'].sum()),
        completed_contracts=int(closed.volume.sum()),residual_contracts=sum(x['volume'] for x in residual),
        partial_closes_of_residual_entries=sum(len(x['realized_segments']) for x in residual),
        payoff_ratio=float(wins.mean()/abs(losses.mean())),profit_factor=float(wins.sum()/abs(losses.sum())),
        avg_net_win=float(wins.mean()),avg_net_loss=float(losses.mean()),initial_capital=CAPITAL,total_trade_count=len(trades),total_slippage=float(daily.slippage.sum()),
        total_commission=float(daily.commission.sum()),win_rate_pct=float((closed.net_pnl>0).mean()*100),
        completed_episodes=len(closed),residual_open_positions=len(residual),
        strategy_account_max_abs_error=account_error,mode=mode,analysis_start=str(START.date()),analysis_end=str(END.date()),
        universe_product_count=int(contracts.product_vt_symbol.nunique()),traded_product_count=int(contracts[contracts.vt_symbol.isin(trades.vt_symbol)].product_vt_symbol.nunique()),
        max_margin=float(snapshots.margin.max()),deferred_missing_bar_order_attempts=len(engine.deferred_orders),
        missing_held_contract_days=len(engine.held_missing),blocked_open_order_attempts=len(engine.blocked_open_orders),elapsed_seconds=time.monotonic()-started,boundaries=manifest['boundaries'])
    weekly_features=engine.weekly_contract.weekly
    weekly_features.to_csv(output/'weekly_contract_features.csv',index=False)
    pd.DataFrame({'date':calendar}).to_csv(output/'trading_calendar.csv',index=False)
    manifest['weekly_feature_export']=dict(scope=engine.weekly_contract.export_scope,queried_contracts=engine.weekly_contract.queried_contracts,rows=len(weekly_features))
    pd.DataFrame(getattr(engine.strategy,'weekly_signal_audit',[])).to_csv(output/'weekly_signal_audit.csv',index=False)
    pd.DataFrame(engine.weekly_execution_audit).to_csv(output/'weekly_execution_audit.csv',index=False)
    pd.DataFrame(engine.open_budget_audit).to_csv(output/'open_budget_audit.csv',index=False)
    pd.DataFrame(engine.lifecycle_events).to_csv(output/'lifecycle_events.csv',index=False)
    pd.DataFrame(annotate_quote_provenance(getattr(engine.strategy,'stage078_intent_cancellations',[]),market)).to_csv(output/'unfilled_intent_cancellations.csv',index=False)
    pd.DataFrame(annotate_quote_provenance(getattr(engine.strategy,'stage085_pending_open_events',[]),market)).to_csv(output/'pending_open_lifecycle_events.csv',index=False)
    forced_columns=['datetime','date','vt_symbol','product_vt_symbol','direction','priority','trigger_ratio','target_ratio','broker_multiplier','equity','margin_before','ratio_before','margin_per_contract','reduce_volume','volume_before','volume_after','price','margin_after','ratio_after']
    pd.DataFrame(engine.strategy.forced_margin_deleverage_events,columns=forced_columns).to_csv(output/'forced_margin_deleverage_events.csv',index=False)
    daily.reset_index().to_csv(output/'daily.csv',index=False)
    trades.to_csv(output/'trades.csv',index=False)
    contracts.to_csv(output/'contract_metadata.csv',index=False)
    mapping.to_csv(output/'mapping.csv',index=False)
    market.to_csv(output/'market_daily.csv',index=False)
    closed.to_csv(output/'closed_episodes.csv',index=False)
    pd.DataFrame([p for r in residual for p in r['realized_segments']],columns=['vt_symbol','direction','entry_trade_id','open_trade_id','exit_trade_id','entry_date','exit_date','entry_price','exit_price','volume','gross_pnl','entry_cost','exit_cost','cost','net_pnl','signal']).to_csv(output/'partial_closes_of_residual_entries.csv',index=False)
    annual.to_csv(output/'annual.csv')
    snapshots.to_csv(output/'account_snapshots.csv')
    pd.DataFrame(engine.deferred_orders,columns=['date','order_id','vt_symbol','reason','volume']).to_csv(output/'deferred_orders.csv',index=False)
    pd.DataFrame(engine.held_missing,columns=['date','vt_symbol','position']).to_csv(output/'held_missing.csv',index=False)
    pd.DataFrame(engine.blocked_open_orders,columns=['date','order_id','vt_symbol','reason']).to_csv(output/'blocked_open_orders.csv',index=False)
    pd.DataFrame(engine.strategy.entry_candidate_snapshots).to_csv(output/'candidates.csv',index=False)
    pd.DataFrame(engine.strategy.entry_risk_diagnostics).to_csv(output/'entry_risk.csv',index=False)
    pd.DataFrame(engine.strategy.trade_event_diagnostics).to_csv(output/'trade_events.csv',index=False)
    (output/'residual_open_positions.json').write_text(json.dumps(safe(residual),ensure_ascii=False,indent=2))
    (output/'summary.json').write_text(json.dumps(safe(summary),ensure_ascii=False,indent=2))
    for name in ('market_daily.csv','mapping.csv','contract_metadata.csv','lifecycle_deadlines.csv','trading_calendar.csv'):
        if sha(output/name)!=baseline_manifest['hashes'][name]:raise RuntimeError('fractional_shared_frozen_table_changed:'+name)
    if sha(baseline_directory/'manifest.json')!=BASELINE_MANIFEST_SHA256:raise RuntimeError('baseline_changed_during_replay')
    manifest['baseline_parameter_changes']=parameter_changes
    manifest['hashes']={p.name:sha(p) for p in output.iterdir() if p.is_file()}
    import importlib.metadata
    import vnpy_portfoliostrategy.backtesting as vendor
    paths=[Path(p) for cls in FeeStrategy.__mro__ if cls.__module__.startswith(('qmt_roll','analyze_qmt')) for p in [inspect.getfile(cls)]]+[Path(__file__),Path(__file__).with_name('stage003_candidate.py'),Path(__file__).with_name('stage058_weekly_contract.py'),Path(__file__).with_name('stage075_fractional_weekly.py'),Path(__file__).with_name('stage068_fractional_risk.py'),Path(__file__).with_name('stage069_quantity_ledger.py'),Path(__file__).with_name('stage074_pending_close_quantity.py'),Path(__file__).with_name('stage078_forced_margin_planning.py'),Path(__file__).with_name('stage085_pending_open_lifecycle.py'),Path(__file__).with_name('stage002_market_source.py'),Path(native_strategy.__file__),Path(vendor.__file__),Path(inspect.getfile(ConfirmedDailyNextRealOpenEngine)),Path(s847.__file__),Path(inspect.getfile(StrategyTemplate)),Path(__file__).with_name('stage016_contract_lifecycle.py'),Path(__file__).with_name('stage024_execution_quotes.py'),Path(__file__).with_name('stage023_quantity_price_overlay.py')]
    manifest['code_hashes']={str(p):sha(p) for p in paths}
    manifest['code_snapshot_hashes']={p.name:sha(p) for p in (output/'code_snapshot').iterdir()}
    manifest['runtime']={'python':sys.executable,'version':sys.version,'packages':{name:importlib.metadata.version(name) for name in ['numpy','pandas','vnpy_portfoliostrategy']}}
    (output/'manifest.json').write_text(json.dumps(safe(manifest),ensure_ascii=False,indent=2))
    print(json.dumps(safe(summary),ensure_ascii=False,indent=2))


def main():
    p=__import__('argparse').ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=['strict','daily-proxy'],required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--supply-policy',choices=['require-frozen','disabled-research'],default='require-frozen')
    a=p.parse_args();os.chdir(ROOT);run(a.mode,a.output.resolve(),supply_policy=a.supply_policy)

if __name__=='__main__':main()
