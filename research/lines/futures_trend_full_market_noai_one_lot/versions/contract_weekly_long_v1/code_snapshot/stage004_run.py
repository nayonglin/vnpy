"""One frozen, isolated research replay. Daily proxy requires explicit mode selection."""
from __future__ import annotations
from collections import deque
from contextlib import redirect_stdout,redirect_stderr
from dataclasses import asdict
from datetime import date,datetime
import hashlib,json,os,subprocess,time
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from stage003_candidate import ROOT,CAPITAL,FullMarketNoAIOneLot,candidate_overrides,research_fee
import numpy as np
import pandas as pd
from vnpy.trader.constant import Exchange,Interval,Direction,Offset
from vnpy.trader.object import BarData
from analyze_qmt_roll_stage502_confirmed_daily_next_real_open_replay import ConfirmedDailyNextRealOpenEngine
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847
from qmt_roll_official_stage78_config import _build_official_stage78_overrides
from run_qmt_roll_stage310_stage78_1_drawdown_gate_engine_validation import _pressure040_overrides
from run_qmt_roll_stage318_supply_demand_headwind_engine_validation import _supply_demand_headwind_overrides
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg
from run_qmt_roll_backtest import build_roll_setting
import qmt_roll_portfolio_strategy as native_strategy
from qmt_roll_official_baseline_identity import assert_official_checkout_matches_active_material
from stage002_market_source import load_source

LINE=ROOT/'research/lines/futures_trend_full_market_noai_one_lot'
START=pd.Timestamp('2015-01-01')
END=pd.Timestamp('2026-10-16')


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


def pending_open_layer(strategy,vt_symbol,direction):
    state=strategy._find_state_by_contract(vt_symbol)
    if state is None or state.direction!=direction:return None
    layers=[x for x in state.layers if x.direction==direction and not x.entry_price_synced and int(x.volume)==1]
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
                float(self.history_data[(self.datetime,o.vt_symbol)].volume)<=0}
        for key,order in absent.items():
            self.deferred_orders.append(dict(date=str(self.datetime.date()),order_id=key,vt_symbol=order.vt_symbol,reason='no_real_positive_volume_bar'))
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
            if int(order.volume)!=1:raise RuntimeError('non_one_lot_open_order')
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
                margin+=float(bar.open_price)*meta['size']*meta['margin_ratio']
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
                product_volumes[product]=product_volumes.get(product,0)+abs(qty)
            if any(q>1 for q in product_volumes.values()):
                self.failure_snapshot=dict(date=str(dt.date()),positions=positions,product_volumes=product_volumes,
                    targets=dict(self.strategy.target_data),
                    states={k:dict(contract=v.contract_vt_symbol,direction=v.direction,layers=[dict(kind=x.kind,volume=x.volume,entry_date=str(x.entry_date)) for x in v.layers]) for k,v in self.strategy.states.items() if v.contract_vt_symbol},
                    active_orders=[dict(id=o.vt_orderid,vt_symbol=o.vt_symbol,direction=str(o.direction),offset=str(o.offset),volume=o.volume,signal_date=str(o.datetime)) for o in self.active_limit_orders.values()],
                    last_trades=[dict(id=t.vt_tradeid,vt_symbol=t.vt_symbol,direction=str(t.direction),offset=str(t.offset),volume=t.volume,datetime=str(t.datetime),price=t.price) for t in list(self.trades.values())[-60:]])
                raise RuntimeError('more_than_one_lot_per_product:'+str(self.failure_snapshot))
            self.account_snapshots.append(dict(date=str(dt.date()),strategy_equity=self.strategy.estimated_equity,
                margin=self.strategy.total_margin_in_use,positions=json.dumps(positions,sort_keys=True)))
        if dt.year!=self.progress_year:
            self.progress_year=dt.year
            print(f'PROGRESS {dt.date()} fills={len(self.trades)}',flush=True)


class FullMarketDailyEngine(CleanExecution,ConfirmedDailyNextRealOpenEngine):pass
class FullMarketStrictEngine(CleanExecution,s847.Stage847StopRetryEngine):pass


def accounting_date(trade):
    value=getattr(trade,'trading_date',None)
    return pd.Timestamp(value if value is not None else trade.datetime).date()


class FeeStrategy(FullMarketNoAIOneLot):
    def on_bars(self,bars):
        signal_bars={vt:bar for vt,bar in bars.items() if not getattr(bar,'execution_only',False)}
        if signal_bars:
            super().on_bars(signal_bars)
        elif bars:
            # A quote-only batch still has an accounting boundary, even though
            # there is no bar eligible to update indicators or create signals.
            date=next(iter(bars.values())).datetime.strftime('%Y-%m-%d')
            self.current_bar_date=pd.Timestamp(date)
            self.estimated_equity=self._estimate_equity({})
            self.settled_balance=self.estimated_equity
            self.equity_start_positions={vt:int(q) for vt,q in self.pos_data.items()}
            self.equity_settlement_date=date
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


def closed_ledger(trades,metadata):
    queues={};closed=[]
    for r in trades.to_dict('records'):
        key=(r['vt_symbol'],r['direction'] if r['offset']=='open' else ('short' if r['direction']=='long' else 'long'))
        q=queues.setdefault(key,deque())
        if r['offset']=='open':
            if q:raise RuntimeError('more_than_one_lot_per_contract')
            q.append(r)
        else:
            if not q:raise RuntimeError('unmatched_close')
            entry=q.popleft();sign=1 if key[1]=='long' else -1
            gross=(r['price']-entry['price'])*sign*metadata[key[0]]['size']
            cost=sum(x['commission']+x['slippage'] for x in (entry,r))
            closed.append(dict(vt_symbol=key[0],direction=key[1],entry_date=entry['date'],exit_date=r['date'],
                entry_price=entry['price'],exit_price=r['price'],gross_pnl=gross,cost=cost,net_pnl=gross-cost,
                signal=entry.get('signal',''),entry_trade_id=entry['trade_id'],exit_trade_id=r['trade_id']))
    return pd.DataFrame(closed),[v for q in queues.values() for v in q]


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
        strategy_overrides={**base,**profile['spec'].overrides,**candidate_overrides(universe)})
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
    identity=asdict(assert_official_checkout_matches_active_material(ROOT))
    market,mapping,contracts,source_manifest=load_source()
    market,overlay_binding=load_execution_overlay(market,contracts)
    metadata=_metadata(contracts)
    universe=LINE/'outputs/inputs/product_universe.csv'
    settings=supply_settings(build_settings(metadata,universe),supply_policy)
    if mode=='daily-proxy':
        settings.update(enable_stage827_intraday_c2_stop=False,enable_stage847_half_r_stop_retry=False)
    engine=(FullMarketDailyEngine if mode=='daily-proxy' else FullMarketStrictEngine)({})
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
        engine.history_data[(dt,r.vt_symbol)]=b;engine.dts.add(dt)
    manifest=dict(run_id=output.name,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True,cwd=ROOT).strip(),
        start=str(START.date()),end=str(END.date()),parameters=settings,mode=mode,official_material_identity=identity,
        source_manifest=source_manifest,expiry_execution_overlay=overlay_binding,supply_policy=supply_policy,production_qualified=False,order_api_calls=0,market_downloads=0,
        boundaries=['静态合约规格、保证金及费用快照，非逐历史日PIT交易所账单。',
          '133条到期日OHLCV双源一致但OI冲突记录，仅用于已有仓位委托成交和估值；不进入信号或新开仓，不使用结算字段伪造成交。',
          '本研究主力由前一源交易日持仓量/成交量确定，不是正式冻结主力映射。',
          '日线近似关闭C2日内止损与C9的0.5R日内止损/重试；其余日线信号、退出和风控沿用Stage037。' if mode=='daily-proxy' else 'C9分钟规则严格缺失即停止，不允许降级。',
          '缺日线不生成信号、不允许成交；已有仓位用上次收盘估值并持续占用1手、并发和保证金；未获真实平仓或结算的残余仓会限制账户后续交易，此估值不可当作可实现收益。',
          '用户单独授权后停用供需过滤：本机缺冻结供需signal CSV。' if supply_policy=='disabled-research' else '供需过滤使用冻结CSV；本次未停用。'])
    (output/'protocol.json').write_text(json.dumps(safe(manifest),ensure_ascii=False,indent=2))
    code_start={str(p):sha(p) for p in [Path(__file__),Path(__file__).with_name('stage003_candidate.py'),Path(__file__).with_name('stage002_market_source.py')]}
    (output/'code_start_hashes.json').write_text(json.dumps(code_start,indent=2))
    snapshots_dir=output/'code_snapshot';snapshots_dir.mkdir()
    for filename in code_start:
        original=Path(filename)
        (snapshots_dir/original.name).write_bytes(original.read_bytes())
    with (output/'engine.log').open('w',buffering=1) as log,redirect_stdout(log),redirect_stderr(log):
        engine.run_backtesting()
        if pd.Timestamp(engine.datetime).tz_localize(None).normalize()!=END:
            failure=dict(status='failed_before_complete',date=str(engine.datetime),snapshot=getattr(engine,'failure_snapshot',{}),financial_metrics_valid=False)
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
            signal=str(getattr(trade,'signal','')),signal_datetime=str(getattr(trade,'signal_datetime','')),order_reissue_datetime=str(getattr(trade,'order_reissue_datetime','')),
            commission=engine.trade_fee_by_id[trade.vt_tradeid],slippage=int(trade.volume)*meta['size']*meta['slippage'],
            exit_reason=engine.strategy.trade_reason_by_trade_id.get(trade.vt_tradeid,'')))
    trades=pd.DataFrame(rows)
    if not trades.volume.eq(1).all():raise RuntimeError('non_one_lot_fill')
    daily=raw.loc[(raw.index>=START.date())&(raw.index<=END.date())].copy()
    fees=trades.groupby('date').commission.sum();daily['commission']=[fees.get(str(d),0.0) for d in daily.index]
    daily['net_pnl']=daily.total_pnl-daily.commission-daily.slippage
    daily['equity']=CAPITAL+daily.net_pnl.cumsum()
    engine.daily_df=daily
    statistics=engine.calculate_statistics(daily,output=False)
    snapshots=pd.DataFrame(engine.account_snapshots).set_index('date')
    differences=np.abs(daily.equity.to_numpy()-snapshots.reindex([str(d) for d in daily.index]).strategy_equity.to_numpy())
    account_error=float(np.nanmax(differences))
    if not np.isfinite(differences).all() or account_error>1e-5:raise RuntimeError(f'strategy_account_disagreement:{account_error}')
    closed,residual=closed_ledger(trades,engine.research_metadata)
    annual=daily.groupby(pd.to_datetime(daily.index).year).agg(net_pnl=('net_pnl','sum'),commission=('commission','sum'),slippage=('slippage','sum'),trade_count=('trade_count','sum'))
    annual['start_equity']=CAPITAL+annual.net_pnl.cumsum()-annual.net_pnl;annual['return_pct']=annual.net_pnl/annual.start_equity*100
    summary=dict(statistics,initial_capital=CAPITAL,total_trade_count=len(trades),total_slippage=float(daily.slippage.sum()),
        total_commission=float(daily.commission.sum()),win_rate_pct=float((closed.net_pnl>0).mean()*100),
        completed_episodes=len(closed),residual_open_positions=len(residual),
        strategy_account_max_abs_error=account_error,mode=mode,analysis_start=str(START.date()),analysis_end=str(END.date()),
        universe_product_count=int(contracts.product_vt_symbol.nunique()),traded_product_count=int(contracts[contracts.vt_symbol.isin(trades.vt_symbol)].product_vt_symbol.nunique()),
        max_margin=float(snapshots.margin.max()),deferred_missing_bar_order_attempts=len(engine.deferred_orders),
        missing_held_contract_days=len(engine.held_missing),blocked_open_order_attempts=len(engine.blocked_open_orders),elapsed_seconds=time.monotonic()-started,boundaries=manifest['boundaries'])
    daily.reset_index().to_csv(output/'daily.csv',index=False)
    trades.to_csv(output/'trades.csv',index=False)
    contracts.to_csv(output/'contract_metadata.csv',index=False)
    mapping.to_csv(output/'mapping.csv',index=False)
    market.to_csv(output/'market_daily.csv',index=False)
    closed.to_csv(output/'closed_episodes.csv',index=False)
    annual.to_csv(output/'annual.csv')
    snapshots.to_csv(output/'account_snapshots.csv')
    pd.DataFrame(engine.deferred_orders,columns=['date','order_id','vt_symbol','reason']).to_csv(output/'deferred_orders.csv',index=False)
    pd.DataFrame(engine.held_missing,columns=['date','vt_symbol','position']).to_csv(output/'held_missing.csv',index=False)
    pd.DataFrame(engine.blocked_open_orders,columns=['date','order_id','vt_symbol','reason']).to_csv(output/'blocked_open_orders.csv',index=False)
    pd.DataFrame(engine.strategy.entry_candidate_snapshots).to_csv(output/'candidates.csv',index=False)
    pd.DataFrame(engine.strategy.entry_risk_diagnostics).to_csv(output/'entry_risk.csv',index=False)
    pd.DataFrame(engine.strategy.trade_event_diagnostics).to_csv(output/'trade_events.csv',index=False)
    (output/'residual_open_positions.json').write_text(json.dumps(safe(residual),ensure_ascii=False,indent=2))
    (output/'summary.json').write_text(json.dumps(safe(summary),ensure_ascii=False,indent=2))
    manifest['hashes']={p.name:sha(p) for p in output.iterdir() if p.is_file()}
    import importlib.metadata,inspect
    import vnpy_portfoliostrategy.backtesting as vendor
    paths=[Path(__file__),Path(__file__).with_name('stage003_candidate.py'),Path(__file__).with_name('stage002_market_source.py'),Path(native_strategy.__file__),Path(vendor.__file__),Path(inspect.getfile(ConfirmedDailyNextRealOpenEngine)),Path(s847.__file__)]
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
