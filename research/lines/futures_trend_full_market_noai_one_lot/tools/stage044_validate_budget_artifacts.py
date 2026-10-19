"""Read-only acceptance of a completed native-budget source and canonical recap.

No strategy execution or result repair. Source and recap are explicit, hash-bound
inputs. JS is parsed with Node --check; browser interaction remains a separate gate.
"""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pandas as pd

from stage001_frozen_recap import sha256

BUNDLED_NODE=Path('/Users/mac/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')
PERIODS=('day30','day10','monthly','weekly','daily','intraday')


def require(condition,message):
    if not condition:raise ValueError(message)


def read_frozen_csv(path,**kwargs):
    return pd.read_csv(path,float_precision='round_trip',**kwargs)


def finite_positive(value):
    try:return math.isfinite(float(value)) and float(value)>0
    except (TypeError,ValueError,OverflowError):return False


def close(a,b,label):
    require(math.isfinite(float(a)) and math.isfinite(float(b)) and math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-7),label)


def flag(value):
    return value is True or isinstance(value,np.bool_) and bool(value) or str(value).strip().lower()=='true'


class Scripts(HTMLParser):
    def __init__(self):super().__init__();self.inside=False;self.parts=[];self.scripts=[]
    def handle_starttag(self,tag,attrs):
        if tag=='script':self.inside=True;self.parts=[]
    def handle_data(self,data):
        if self.inside:self.parts.append(data)
    def handle_endtag(self,tag):
        if tag=='script' and self.inside:self.scripts.append(''.join(self.parts));self.inside=False


def check_javascript(page,node=None):
    executable=str(node or shutil.which('node') or BUNDLED_NODE)
    require(Path(executable).is_file(),'JavaScript_Node_runtime_unavailable')
    parser=Scripts();parser.feed(page)
    require(len(parser.scripts)>=2,'JavaScript_scripts_missing')
    for index,script in enumerate(parser.scripts):
        result=subprocess.run([executable,'--check'],input=script,text=True,capture_output=True)
        require(result.returncode==0,f'JavaScript_syntax_error_script_{index}: {result.stderr[:600]}')
    return len(parser.scripts)


def budget_arithmetic(snapshot,equity,reserved):
    required=('target_risk_amount','risk_ratio','risk_multiplier','portfolio_overheat_cooldown_scale',
              'directional_30d_risk_boost_multiplier','min_risk_per_trade','max_risk_per_trade',
              'effective_capital_usage_ratio','sizing_equity','limited_balance')
    require(all(key in snapshot for key in required),'budget_snapshot_fields_missing')
    values={key:float(snapshot[key]) for key in required}
    require(all(math.isfinite(value) and value>=0 for value in values.values()),'budget_snapshot_nonfinite_or_negative')
    require(values['max_risk_per_trade']>=values['min_risk_per_trade'],'budget_snapshot_min_max_invalid')
    factor=values['risk_multiplier']*values['portfolio_overheat_cooldown_scale']*values['directional_30d_risk_boost_multiplier']
    signal_base=min(values['max_risk_per_trade'],max(values['min_risk_per_trade'],values['limited_balance']*values['risk_ratio']))
    close(signal_base*factor,values['target_risk_amount'],'budget_signal_native_arithmetic_mismatch')
    require(math.isfinite(float(equity)) and float(equity)>0 and math.isfinite(float(reserved)) and float(reserved)>=0,'budget_open_resources_invalid')
    cap=min(values['sizing_equity'],float(equity))
    remaining=max(0.,min(cap-float(reserved),cap*values['effective_capital_usage_ratio']-float(reserved)))
    at_open=min(values['max_risk_per_trade'],max(values['min_risk_per_trade'],remaining*values['risk_ratio']))*factor
    return min(values['target_risk_amount'],at_open)


def validate(source:Path,recap:Path,*,node=None):
    source,recap=Path(source).resolve(),Path(recap).resolve()
    identity=json.loads((source/'manifest.json').read_text())
    for name,digest in identity['hashes'].items():
        require(Path(name).name==name and (source/name).is_file(),'source_hash_member_missing:'+name)
        require(sha256(source/name)==digest,'source_hash_mismatch:'+name)
    summary=json.loads((recap/'summary.json').read_text())
    require(Path(summary['source_directory']).resolve()==source,'explicit_source_does_not_match_recap')
    require(summary['source_manifest_sha256']==sha256(source/'manifest.json'),'recap_source_manifest_changed')
    for name,digest in summary['artifact_sha256'].items():
        require(Path(name).name==name and (recap/name).is_file() and sha256(recap/name)==digest,'recap_artifact_hash_mismatch:'+name)
    require('records.json' in summary['artifact_sha256'],'records_cache_not_hash_bound')
    metrics=json.loads((source/'summary.json').read_text())
    require(metrics==summary['backtest_metrics'],'frozen_metrics_changed_in_recap')
    for key in ('native_risk_budget_restored','one_lot_is_maximum_not_fixed','next_open_risk_recheck','position_count_limit_removed'):
        require(identity.get(key) is True and metrics.get(key) is True,'source_policy_flag_missing:'+key)
    parameters=identity['parameters']
    require(parameters.get('fixed_size')==0 and parameters.get('min_position_size')==1 and parameters.get('max_position_size')==1,'native_budget_max_one_parameters_invalid')
    require(parameters.get('max_concurrent_positions')==93,'source_capacity_must_be_93')
    require(0<=int(metrics['max_actual_products'])<=93,'actual_product_count_exceeds_capacity')
    metadata=read_frozen_csv(source/'contract_metadata.csv').set_index('vt_symbol')
    product_count=metadata['product_vt_symbol'].nunique() if 'product_vt_symbol' in metadata else (metadata['product'].astype(str)+'.'+metadata['exchange'].astype(str)).nunique()
    require(product_count==93 and metrics['universe_product_count']==93,'source_capacity_universe_mismatch')
    trades=read_frozen_csv(source/'trades.csv')
    require(not trades.trade_id.duplicated().any() and trades.volume.eq(1).all(),'source_fills_not_unique_one_lot')
    require(len(trades)==metrics['total_trade_count'],'source_trade_count_mismatch')
    require(str(trades.date.max())==metrics['last_fill_date'],'source_last_fill_mismatch')
    indexed=trades.set_index('trade_id')
    positions={};max_replayed_products=0
    product_by_contract=(metadata['product_vt_symbol'].astype(str).to_dict() if 'product_vt_symbol' in metadata else (metadata['product'].astype(str)+'.'+metadata['exchange'].astype(str)).to_dict())
    for fill in trades.itertuples(index=False):
        require(fill.direction in ('long','short') and fill.offset in ('open','close'),'source_fill_side_invalid')
        sign=1 if fill.direction=='long' else -1
        previous=positions.get(fill.vt_symbol,0)
        if fill.offset=='open':require(previous==0,'one_lot_position_existing_contract_add')
        else:require(previous*sign<0,'one_lot_position_unmatched_close')
        positions[fill.vt_symbol]=previous+sign*int(fill.volume)
        gross_by_product={}
        for symbol,quantity in positions.items():
            if quantity:
                require(symbol in product_by_contract,'one_lot_position_metadata_missing')
                product=product_by_contract[symbol]
                gross_by_product[product]=gross_by_product.get(product,0)+abs(quantity)
        require(all(quantity<=1 for quantity in gross_by_product.values()),'one_lot_position_product_gross_exceeds_one')
        max_replayed_products=max(max_replayed_products,len(gross_by_product))
    require(int(metrics['max_actual_products'])<=max_replayed_products<=93,'actual_product_count_not_supported_by_fills')
    actual_opens=trades[trades.offset.eq('open')]
    audit=read_frozen_csv(source/'open_budget_audit.csv')
    filled=audit[audit.filled.map(flag)]
    require(len(audit)==metrics['open_budget_checks'] and len(audit)-len(filled)==metrics['open_budget_rejections'],'budget_audit_counts_mismatch')
    require(not filled.trade_id.duplicated().any() and set(filled.trade_id)==set(actual_opens.trade_id),'budget_actual_open_audit_binding_mismatch')
    audit_by_id=filled.set_index('trade_id')
    snapshots=set()
    for row in actual_opens.itertuples(index=False):
        bound=audit_by_id.loc[row.trade_id]
        require(flag(bound.allowed),'budget_filled_open_was_not_allowed')
        snapshot=json.loads(row.stage041_signal_snapshot)
        require(snapshot==json.loads(bound.signal_snapshot),'budget_signal_snapshot_audit_mismatch')
        require(bool(snapshot.get('snapshot_id')) and snapshot['snapshot_id'] not in snapshots,'budget_signal_snapshot_identity_reused')
        snapshots.add(snapshot['snapshot_id'])
        product=str(metadata.loc[row.vt_symbol,'product_vt_symbol']) if 'product_vt_symbol' in metadata else str(metadata.loc[row.vt_symbol,'product'])+'.'+str(metadata.loc[row.vt_symbol,'exchange'])
        require(snapshot.get('contract_vt_symbol')==row.vt_symbol and snapshot.get('product_vt_symbol')==product and snapshot.get('direction')==row.direction and snapshot.get('signal')==row.signal,'budget_signal_snapshot_identity_mismatch')
        require(pd.Timestamp(snapshot['signal_datetime']).date()==pd.Timestamp(row.signal_datetime).date()<pd.Timestamp(row.date).date(),'budget_signal_time_not_before_fill')
        require(bound.vt_symbol==row.vt_symbol and bound.direction==row.direction and int(bound.volume)==1,'budget_audit_trade_identity_mismatch')
        require(str(bound.date)==str(row.date),'budget_audit_trade_date_mismatch')
        close(bound.open_price,row.price,'budget_audit_actual_price_mismatch')
        close(bound['size'],metadata.loc[row.vt_symbol,'size'],'budget_audit_contract_size_mismatch')
        close(bound.pricetick,metadata.loc[row.vt_symbol,'pricetick'],'budget_audit_tick_mismatch')
        close(bound.stop_price,snapshot['stop_price'],'budget_frozen_stop_mismatch')
        require(all(finite_positive(x) for x in (row.price,bound.stop_price,bound['size'],bound.pricetick)),'budget_open_or_stop_invalid')
        require(row.price>bound.stop_price if row.direction=='long' else row.price<bound.stop_price,'budget_stop_crossed_before_open')
        require(finite_positive(row.stage041_entry_risk) and finite_positive(row.stage041_open_budget) and row.stage041_entry_risk<=row.stage041_open_budget<=snapshot['target_risk_amount'],'budget_exact_actual_authorization_ceiling_exceeded')
        risk=max(abs(row.price-bound.stop_price)*bound['size'],bound.pricetick*bound['size'],1.)
        budget=budget_arithmetic(snapshot,bound.opening_equity,bound.reserved_margin)
        close(risk,bound.one_lot_risk,'budget_audit_actual_risk_mismatch')
        close(risk,row.stage041_entry_risk,'budget_trade_actual_risk_mismatch')
        close(budget,bound.opening_budget,'budget_opening_arithmetic_mismatch')
        close(budget,row.stage041_open_budget,'budget_trade_actual_budget_mismatch')
        require(finite_positive(budget) and risk<=budget<=snapshot['target_risk_amount'],'budget_oversized_or_unauthorized_actual_open')
    require(metrics['actual_open_budget_violations']==0,'budget_reported_actual_violation')

    records=json.loads((recap/'records.json').read_text())
    page=(recap/'index.html').read_text()
    marker='const records=';start=page.index(marker)+len(marker)
    embedded,_=json.JSONDecoder().raw_decode(page[start:])
    require(records==embedded,'embedded_records_differ_from_hash_bound_cache')
    episodes=read_frozen_csv(recap/'all_trade_episodes.csv');manifest=read_frozen_csv(recap/'chart_manifest.csv')
    closed=read_frozen_csv(source/'closed_episodes.csv')
    require(len(records)==len(episodes)==len(manifest)==len(closed)==metrics['completed_episodes'],'complete_episode_count_mismatch')
    record_ids={row['meta']['open_trade_id'] for row in records}
    require(len(record_ids)==len(records) and record_ids==set(episodes.open_trade_id)==set(manifest.open_trade_id)==set(closed.entry_trade_id),'complete_episode_identity_mismatch')
    counts=episodes.result_type.value_counts().to_dict()
    for key in ('profit','loss','flat'):require(counts.get(key,0)==summary['chart_'+key+'_episodes'],'episode_result_count_mismatch:'+key)
    closed_by_id=closed.set_index('entry_trade_id');episode_by_id=episodes.set_index('open_trade_id');manifest_by_id=manifest.set_index('open_trade_id');ma_points=0;period_counts={period:0 for period in PERIODS}
    for record in records:
        m=record['meta'];entry=indexed.loc[m['open_trade_id']];exit_=indexed.loc[m['close_trade_id']];frozen=closed_by_id.loc[m['open_trade_id']]
        require(entry.offset=='open' and exit_.offset=='close' and frozen.exit_trade_id==m['close_trade_id'],'episode_not_bound_to_complete_fills')
        require(m['entry_date']==entry.date and m['exit_date']==exit_.date and m['vt_symbol']==entry.vt_symbol==exit_.vt_symbol,'episode_dates_or_contract_changed')
        require(m['signal']==entry.signal==frozen.signal and m['direction']==entry.direction==frozen.direction,'episode_signal_or_direction_changed')
        close(m['entry_price'],entry.price,'episode_entry_price_changed');close(m['exit_price'],exit_.price,'episode_exit_price_changed')
        require(frozen.entry_date==entry.date and frozen.exit_date==exit_.date,'closed_source_dates_changed')
        close(frozen.entry_price,entry.price,'closed_source_entry_price_changed');close(frozen.exit_price,exit_.price,'closed_source_exit_price_changed')
        for frame,label in ((episode_by_id,'episode_csv'),(manifest_by_id,'manifest')):
            item=frame.loc[m['open_trade_id']]
            for key in ('close_trade_id','vt_symbol','direction','signal','entry_date','exit_date','result_type'):
                require(str(item[key])==str(m[key]),label+'_record_value_mismatch:'+key)
            for key in ('entry_price','exit_price','realized_pnl','price_change_pct'):
                close(item[key],m[key],label+'_record_value_mismatch:'+key)
        gross=(exit_.price-entry.price)*float(metadata.loc[entry.vt_symbol,'size'])*(1 if entry.direction=='long' else -1)
        cost=sum(float(row.commission)+float(row.slippage) for row in (entry,exit_))
        close(gross,m['realized_pnl'],'episode_gross_price_pnl_mismatch');close(gross,frozen.gross_pnl,'closed_gross_pnl_mismatch')
        require(m['result_type']==('profit' if gross>0 else 'loss' if gross<0 else 'flat'),'record_gross_result_classification_mismatch')
        close(cost,frozen.cost,'closed_cost_mismatch');close(gross-cost,frozen.net_pnl,'closed_net_pnl_mismatch')
        close((exit_.price/entry.price-1)*100,m['price_change_pct'],'underlying_price_change_mismatch')
        for period in PERIODS:
            require(period in record,'canonical_period_missing:'+period)
            payload=record[period];length=len(payload['x']);period_counts[period]+=length
            manifest_column={'intraday':'bars_15m'}.get(period,period+'_bars')
            require(int(manifest_by_id.loc[m['open_trade_id'],manifest_column])==length,'manifest_period_bar_count_mismatch:'+period)
            require(period=='intraday' or length>0,'canonical_period_empty:'+period)
            require(all(len(payload[key])==length for key in ('open','high','low','close','volume','ma5','ma10','ma20','ma40')),'canonical_period_array_length_mismatch:'+period)
            close_series=pd.Series(payload['close'],dtype=float)
            for window in (5,10,20,40):
                if length<window:continue
                expected=close_series.rolling(window).mean().iloc[window-1:].to_numpy()
                actual=np.asarray(payload['ma'+str(window)][window-1:],dtype=float)
                require(np.isfinite(actual).all() and np.allclose(actual,expected,atol=1e-7,rtol=1e-10),'canonical_MA_mismatch:'+period+':'+str(window))
                ma_points+=len(expected)
        available=int(len(record['intraday']['x'])>0)
        require(int(m['draw_intraday'])==available,'minute_availability_flag_mismatch')
    require(manifest.bars_15m.sum()==period_counts['intraday'],'minute_manifest_count_mismatch')
    lifecycle=read_frozen_csv(source/'lifecycle_deadlines.csv').set_index('vt_symbol')
    for symbol,group in trades.groupby('vt_symbol'):
        deadline=str(lifecycle.loc[symbol,'deadline'])
        require(group.date.max()<=deadline and group.loc[group.offset.eq('open'),'date'].lt(deadline).all(),'lifecycle_fill_after_deadline:'+symbol)
    residual=json.loads((source/'residual_open_positions.json').read_text())
    require(len(residual)==metrics['residual_open_positions']==len(summary['residual_open_positions']),'residual_count_mismatch')
    residual_positions={}
    for row in residual:
        require(str(lifecycle.loc[row['vt_symbol'],'deadline'])>metrics['analysis_end'],'residual_past_lifecycle_deadline')
        symbol=row['vt_symbol'];sign=1 if row['direction']=='long' else -1
        residual_positions[symbol]=residual_positions.get(symbol,0)+sign*float(row['volume'])
    require(residual_positions=={key:quantity for key,quantity in positions.items() if quantity},'residual_positions_do_not_match_actual_fills')
    recap_residual={}
    for row in summary['residual_open_positions']:
        symbol=row['vt_symbol'];sign=1 if row['direction']=='long' else -1
        recap_residual[symbol]=recap_residual.get(symbol,0)+sign*float(row['volume'])
    require(recap_residual==residual_positions,'recap_residual_positions_changed')
    for disclosure in ('日线近似','无品种数上限','供需过滤'):require(disclosure in page,'required_disclosure_missing:'+disclosure)
    scripts=check_javascript(page,node)
    result=dict(status='PASS_native_budget_daily_research_artifact',episodes=len(records),source_fills=len(trades),
        gross_result_counts=counts,period_bar_counts=period_counts,ma_points_independently_checked=ma_points,
        javascript_syntax_checked=True,javascript_scripts_checked=scripts,actual_opens_budget_checked=len(actual_opens),
        actual_open_budget_violations=0,original_signal_snapshot_binding_checked=True,
        native_signal_and_open_budget_independently_recalculated=True,all_entry_exit_dates_prices_signals_matched=True,
        frozen_metrics_unchanged=True,configured_product_capacity=93,max_actual_products=metrics['max_actual_products'],
        max_products_reconstructed_after_each_fill=max_replayed_products,max_product_gross_lots=1,
        last_fill_date=metrics['last_fill_date'],performance_certifiable=metrics.get('performance_certifiable'),
        financial_replays=0,source_manifest_sha256=sha256(source/'manifest.json'),
        html_sha256=sha256(recap/'index.html'),summary_sha256=sha256(recap/'summary.json'),validator_sha256=sha256(Path(__file__)))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path);parser.add_argument('--recap',required=True,type=Path)
    parser.add_argument('--output',type=Path);parser.add_argument('--node',type=Path)
    args=parser.parse_args()
    if args.output and args.output.exists():raise FileExistsError(args.output)
    result=validate(args.source,args.recap,node=args.node)
    rendered=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.output:args.output.write_text(rendered,encoding='utf-8')
    print(rendered,end='')


if __name__=='__main__':main()
