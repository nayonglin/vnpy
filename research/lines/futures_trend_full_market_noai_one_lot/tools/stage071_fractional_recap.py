"""Readonly 0.5%-equity multi-lot R/cost adapter; reuse canonical episode/HTML.

Each completed original opening fill is one statistical episode. Partial exits
allocate risk and both fills' total cash costs by quantity, without rerunning finance.
"""
import argparse,csv,json,math,shutil
from decimal import Decimal
from pathlib import Path
import numpy as np
import pandas as pd
from stage001_frozen_recap import CANONICAL,load_display_functions,sha256
from stage042_account_overview import verify_hashes,safe_member

BASELINE_COMMIT='e553d1703bc4efb9c612143a6c3f2ccc9885f6b3'
BASELINE_SHA='859982f079da55aa1292154d5fc9b1004d1f0d5f23f75c4ec58ca892a102cb25'
FRACTIONAL_POLICY=dict(risk_fraction=.005,equity_basis='causal_marked_total_account_equity',signal_budget='signal_equity * 0.005',
    opening_budget='min(original_signal_budget, opening_equity_after_prior_fills_costs * 0.005)',rounding='floor_integer_contracts_no_minimum_one',
    opening_order_policy='all_or_none_reject_if_total_stop_risk_exceeds_budget',currency_min_max_and_risk_multipliers='replaced_by_fixed_equity_fraction',
    native_quantity_and_margin_gates='preserved_reduce_only',one_lot_cap=False,adds=False)
FRACTIONAL_FLAGS=dict(fractional_risk_budget_enabled=True,position_volume_cap_removed=True,position_count_limit_removed=True,next_open_risk_recheck=True,one_lot_is_maximum_not_fixed=False,native_risk_budget_restored=False)
META_FIELDS=('risk_amount','r_multiple','risk_per_lot','initial_risk_total','commission','slippage','cost','net_pnl')
NOTE=('单笔预算=因果已标记账户总权益×0.5%（0.005，100万对应5000元），按每手止损现金风险向下取整；取消1手上限，不加仓。'
    '旧风险金额min/max、风险比例与货币倍率停用，其余native减量/数量/资金/保证金闸门保留；实际开盘按原授权整单复核，超预算拒绝整单。'
    'R=完整entry毛价差盈亏/实际接受的整笔初始止损风险（实际手数×开盘每手风险），不是每手风险、目标预算或净盈亏。'
    '每次原始OPEN完全平仓才计一个胜率样本，多手及分批平仓不拆成独立样本；页内盈亏筛选仍按canonical毛价差分类，净胜率按完整entry扣成本统计。'
    '费用/滑点为各成交全部手数总现金，entry及close费用按匹配数量分摊；残仓未分配到已平段的entry费用已计入账户，不再重复扣日账。'
    '原顺序、尾部标签及图形数组保留，补R不追溯重选。')


def require(ok,message):
    if not ok:raise ValueError(message)


def positive(v):
    return not isinstance(v,(bool,np.bool_)) and isinstance(v,(float,int,np.number)) and math.isfinite(float(v)) and float(v)>0


def integer(v):return positive(v) and int(v)==v


def budget(equity):return float(Decimal(str(equity))*Decimal('.005'))


def total_risk(per_lot,volume):return float(Decimal(str(per_lot))*Decimal(str(int(volume))))


def near(a,b,label):require(math.isclose(float(a),float(b),abs_tol=1e-7,rel_tol=1e-10),label)


def validate_policy(identity,metrics):
    for obj in (identity,metrics):
        require(obj.get('fractional_risk_policy')==FRACTIONAL_POLICY,'fractional_risk_policy_mismatch')
        for flag in ('fractional_risk_budget_enabled','position_volume_cap_removed','position_count_limit_removed','next_open_risk_recheck'):
            require(obj.get(flag) is True,'fractional_flag:'+flag)
        require(obj.get('one_lot_is_maximum_not_fixed') is False and obj.get('native_risk_budget_restored') is False,'legacy_one_lot_policy_active')
        require(obj.get('baseline_commit')==BASELINE_COMMIT,'baseline_N_commit_mismatch')
    require(identity.get('baseline_run_manifest_sha256')==BASELINE_SHA,'baseline_N_manifest_mismatch')
    p=identity['parameters'];require(p.get('stage068_risk_fraction')==.005 and p.get('max_position_size')==2147483647 and p.get('min_position_size')==1 and p.get('fixed_size')==0 and p.get('max_concurrent_positions')==93,'fractional_sizing_parameters_mismatch')


def attribute_closed_lots(trades,closed,receipts):
    require(not trades.trade_id.astype(str).duplicated().any(),'duplicate_trade_identity')
    indexed=trades.set_index(trades.trade_id.astype(str));result=closed.copy()
    for i,row in result.iterrows():
        key=str(row.open_trade_id);require(key in receipts,'entry_risk_receipt_missing:'+key)
        receipt=receipts[key];entry=indexed.loc[key];exit_=indexed.loc[str(row.close_trade_id)]
        require(integer(receipt['filled_volume']) and receipt['filled_volume']==entry.volume,'receipt_volume_mismatch:'+key)
        require(positive(receipt['risk_per_lot']) and positive(receipt['initial_risk_total']) and receipt['initial_risk_total']==total_risk(receipt['risk_per_lot'],receipt['filled_volume']),'receipt_total_risk_mismatch:'+key)
        require(integer(row.volume) and row.volume<=entry.volume and row.volume<=exit_.volume,'closed_matched_volume_invalid')
        for field in ('commission','slippage'):
            require(all(math.isfinite(float(v)) and float(v)>=0 for v in (entry[field],exit_[field])),'invalid_fill_cost')
            result.at[i,field]=float(entry[field])*row.volume/entry.volume+float(exit_[field])*row.volume/exit_.volume
        risk=total_risk(receipt['risk_per_lot'],row.volume);cost=result.at[i,'commission']+result.at[i,'slippage']
        result.at[i,'risk_amount']=risk;result.at[i,'r_multiple']=float(row.realized_pnl)/risk
        result.at[i,'risk_per_lot']=receipt['risk_per_lot'];result.at[i,'initial_risk_total']=receipt['initial_risk_total']
        result.at[i,'cost']=cost;result.at[i,'net_pnl']=float(row.realized_pnl)-cost
    return result


def complete_entry_episodes(trades,closed):
    opens=trades[trades.offset.eq('open')].set_index(trades[trades.offset.eq('open')].trade_id.astype(str))
    volumes=closed.groupby('open_trade_id',sort=False).volume.sum();complete=[]
    for key,volume in volumes.items():
        require(key in opens.index and volume<=opens.loc[key,'volume'],'closed_volume_exceeds_open')
        if volume==opens.loc[key,'volume']:complete.append(key)
    full=closed[closed.open_trade_id.isin(complete)].copy();partial=closed[~closed.open_trade_id.isin(complete)].copy()
    renderer=load_display_functions({});episodes=renderer._trade_episodes(full) if len(full) else pd.DataFrame()
    for i,row in episodes.iterrows():
        group=full[full.open_trade_id.eq(row.open_trade_id)]
        for field in ('commission','slippage','cost','net_pnl'):episodes.at[i,field]=float(group[field].sum())
        episodes.at[i,'risk_amount']=float(group.initial_risk_total.iloc[0]);episodes.at[i,'initial_risk_total']=float(group.initial_risk_total.iloc[0])
        episodes.at[i,'risk_per_lot']=float(group.risk_per_lot.iloc[0]);episodes.at[i,'r_multiple']=row.realized_pnl/episodes.at[i,'risk_amount']
    return episodes,partial


def normalize_receipts(source,trades):
    require({'stage068_open_budget','stage068_entry_risk','stage068_risk_per_contract','stage068_signal_snapshot'}.issubset(trades.columns),'fractional_receipt_fields_missing')
    opens=trades[trades.offset.eq('open')];require(not opens.empty,'missing_fractional_opens')
    audit=pd.read_csv(source/'open_budget_audit.csv',float_precision='round_trip');accepted=audit[audit.filled.astype(str).str.lower().eq('true')]
    require(not accepted.trade_id.astype(str).duplicated().any() and set(accepted.trade_id.astype(str))==set(opens.trade_id.astype(str)),'fractional_audit_identity_mismatch')
    accepted=accepted.set_index(accepted.trade_id.astype(str));metadata=pd.read_csv(source/'contract_metadata.csv',float_precision='round_trip').set_index('vt_symbol');receipts={}
    for r in opens.itertuples():
        key=str(r.trade_id);a=accepted.loc[key];s=json.loads(r.stage068_signal_snapshot)
        require(s==json.loads(a.signal_snapshot),'fractional_snapshot_audit_mismatch:'+key)
        require(s.get('contract_vt_symbol')==r.vt_symbol and s.get('direction')==r.direction,'fractional_receipt_identity_mismatch:'+key)
        require(s.get('risk_fraction')==.005 and positive(s.get('signal_equity')) and s.get('target_risk_amount')==budget(s['signal_equity']),'fractional_signal_budget_mismatch:'+key)
        require(integer(r.volume) and r.volume==s['authorized_volume']==a.volume,'fractional_filled_volume_mismatch:'+key)
        require(positive(s.get('risk_per_contract')) and int(Decimal(str(s['target_risk_amount']))/Decimal(str(s['risk_per_contract'])))>=r.volume,'fractional_signal_volume_exceeds_budget:'+key)
        stop=float(s['stop_price']);meta=metadata.loc[r.vt_symbol]
        require(positive(stop) and s.get('product_vt_symbol')==meta['product_vt_symbol'],'fractional_receipt_product_or_stop_invalid:'+key)
        require(r.price>stop if r.direction=='long' else r.price<stop,'fractional_stop_already_crossed:'+key)
        risk=max(abs(r.price-stop)*float(meta['size']),float(meta['pricetick'])*float(meta['size']),1.)
        require(r.stage068_risk_per_contract==risk and r.stage068_entry_risk==total_risk(risk,r.volume),'fractional_actual_initial_risk_mismatch:'+key)
        expected=min(s['target_risk_amount'],budget(a.opening_equity))
        require(positive(a.opening_equity) and r.stage068_open_budget==a.opening_budget==expected and r.stage068_entry_risk<=expected,'fractional_open_budget_exceeded:'+key)
        require(a.risk_per_contract==risk and a.total_risk==r.stage068_entry_risk and a.max_affordable_volume==int(Decimal(str(expected))/Decimal(str(risk))),'fractional_open_audit_value_mismatch:'+key)
        receipts[key]=dict(filled_volume=int(r.volume),risk_per_lot=risk,initial_risk_total=r.stage068_entry_risk)
    require(len({json.loads(r.stage068_signal_snapshot)['snapshot_id'] for r in opens.itertuples()})==len(receipts),'fractional_authorization_reused_for_multiple_opens')
    return receipts


def protected_hash(records):
    import hashlib
    h=hashlib.sha256()
    for r in records:
        value={**r,'meta':{k:v for k,v in r['meta'].items() if k not in META_FIELDS}}
        h.update(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode());h.update(b'\n')
    return h.hexdigest()


def write_episode_csv(parent,output,name,episodes):
    with (parent/name).open(newline='',encoding='utf-8-sig') as f:reader=csv.DictReader(f);fields=list(reader.fieldnames);rows=list(reader)
    indexed=episodes.set_index('open_trade_id')
    for r in rows:
        evidence=indexed.loc[r['open_trade_id']]
        for key in META_FIELDS:r[key]=repr(float(evidence[key]))
    with (output/name).open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields+[key for key in META_FIELDS if key not in fields]);writer.writeheader();writer.writerows(rows)


def render_page(renderer,records,summary):
    page=renderer._html(records,summary)
    old="['净利润',pnlValue]";new="['毛/净盈亏',pnlValue+'<span class=\"submetric\">净 '+fmt(m.net_pnl,2)+'；成本 '+fmt(m.cost,2)+'</span>']"
    require(page.count(old)==1,'canonical_gross_metric_contract_changed');page=page.replace(old,new,1)
    old="['平仓lot',m.lot_count]";require(page.count(old)==1,'canonical_volume_metric_contract_changed')
    return page.replace(old,"['交易手数',m.volume]",1)


def enrich(source,parent,output):
    source,parent,output=(Path(p).resolve() for p in (source,parent,output))
    for root in (source,parent):require(not(output.is_relative_to(root) or root.is_relative_to(output)),'output_not_isolated')
    if output.exists():raise FileExistsError(output)
    code_hash=sha256(Path(__file__));identity=json.loads((source/'manifest.json').read_text());bound=verify_hashes(source,identity);source_hash=sha256(source/'manifest.json');metrics=json.loads((source/'summary.json').read_text());validate_policy(identity,metrics)
    for name in ('open_budget_audit.csv','partial_closes_of_residual_entries.csv'):require(name in bound,'fractional_source_binding_missing:'+name)
    summary=json.loads((parent/'summary.json').read_text());parent_hash=sha256(parent/'summary.json');require(summary['source_manifest_sha256']==source_hash and summary['backtest_metrics']==metrics,'fractional_parent_source_mismatch')
    require(Path(summary['canonical_renderer']).resolve()==CANONICAL and summary['canonical_renderer_sha256']==sha256(CANONICAL),'canonical_hash_mismatch')
    for name,digest in summary['artifact_sha256'].items():require(sha256(safe_member(parent,name))==digest,'parent_hash_mismatch:'+name)
    records=json.loads((parent/'records.json').read_text());page=(parent/'index.html').read_text();marker='const records=';embedded,_=json.JSONDecoder().raw_decode(page[page.index(marker)+len(marker):]);require(embedded==records,'parent_embedded_records_mismatch');del page,embedded
    before=protected_hash(records);trades=pd.read_csv(source/'trades.csv',float_precision='round_trip');receipts=normalize_receipts(source,trades)
    metadata=pd.read_csv(source/'contract_metadata.csv',float_precision='round_trip');renderer=load_display_functions(metadata.set_index('vt_symbol').get('product',pd.Series(dtype=str)).to_dict())
    all_closed=renderer._closed_lots_from_trade_ledger(trades,sizes=metadata.set_index('vt_symbol')['size'].to_dict(),allow_residual_open=True,source_prefix=identity['run_id'])
    signals=trades[trades.offset.eq('open')].set_index(trades[trades.offset.eq('open')].trade_id.astype(str)).get('signal',pd.Series(dtype=str))
    all_closed['signal']=all_closed.open_trade_id.astype(str).map(signals).fillna('')
    attributed=attribute_closed_lots(trades,all_closed,receipts);episodes,partials=complete_entry_episodes(trades,attributed);ids=[str(r['meta']['open_trade_id']) for r in records]
    require(set(ids)==set(episodes.open_trade_id) and len(ids)==len(set(ids))==metrics['completed_episodes'],'fractional_complete_episode_count_mismatch')
    frozen=pd.read_csv(source/'closed_episodes.csv',float_precision='round_trip');require(set(frozen.open_trade_id.astype(str))==set(ids),'fractional_frozen_complete_ids_mismatch');frozen=frozen.set_index(frozen.open_trade_id.astype(str));by_id=episodes.set_index('open_trade_id')
    for r in records:
        key=str(r['meta']['open_trade_id']);e=by_id.loc[key];f=frozen.loc[key]
        for a,b in ((e.volume,f.volume),(e.realized_pnl,f.gross_pnl),(e.cost,f.cost),(e.net_pnl,f.net_pnl),(e.weighted_exit_price,f.exit_price)):near(a,b,'fractional_frozen_episode_mismatch:'+key)
        for field in META_FIELDS:r['meta'][field]=float(e[field])
    require(protected_hash(records)==before,'nonfinancial_chart_payload_changed')
    residual_cost=float((trades.commission+trades.slippage).sum()-attributed.cost.sum());require(residual_cost>=-1e-7,'cost_attribution_exceeds_all_fill_costs')
    source_partial=pd.read_csv(source/'partial_closes_of_residual_entries.csv',float_precision='round_trip');require(len(source_partial)==len(partials),'fractional_partial_segment_count_mismatch')
    partial_index={(str(r.open_trade_id),str(r.close_trade_id)):r for r in partials.itertuples()}
    for r in source_partial.itertuples():
        require((str(r.open_trade_id),str(r.exit_trade_id)) in partial_index,'fractional_partial_identity_mismatch');p=partial_index[(str(r.open_trade_id),str(r.exit_trade_id))]
        for a,b in ((p.volume,r.volume),(p.realized_pnl,r.gross_pnl),(p.cost,r.cost),(p.net_pnl,r.net_pnl)):near(a,b,'fractional_partial_ledger_mismatch')
    source_residual=json.loads((source/'residual_open_positions.json').read_text());near(residual_cost,sum(float(r['commission'])+float(r['slippage']) for r in source_residual),'fractional_residual_cost_allocation_mismatch')
    summary['page_title']='【日线近似】全市场无AI · 0.5%总权益风险预算 · 多手整数定仓逐笔复盘';summary['source_label']='合约自身完成周线N为基线；0.5%风险预算，多手、不加仓'
    warning=str(summary['source_warning']).replace('无品种数上限，每品种1手。','').replace('R不可获得时显示N/A。','')
    summary['source_warning']=warning+' '+NOTE
    provenance=dict(generator_sha256=code_hash,source_manifest_sha256=source_hash,parent_directory=str(parent),parent_summary_sha256=parent_hash,parent_artifact_sha256=dict(summary['artifact_sha256']),
        completed_episodes=len(episodes),completed_contracts=float(episodes.volume.sum()),partial_close_segments_of_residual_entries=len(partials),all_closed_matched_segments=len(attributed),
        unallocated_remaining_entry_cash_cost=residual_cost,complete_gross_pnl=float(episodes.realized_pnl.sum()),complete_net_pnl=float(episodes.net_pnl.sum()),
        protected_payload_sha256_before=before,protected_payload_sha256_after=protected_hash(records),risk_denominator='accepted_actual_total_initial_stop_risk_stage068_entry_risk',fractional_risk_policy=FRACTIONAL_POLICY,
        financial_replays=0,market_downloads=0,source_mutations=0)
    summary['fractional_recap_enrichment']=provenance;page=render_page(renderer,records,summary)
    require(sha256(source/'manifest.json')==source_hash and sha256(parent/'summary.json')==parent_hash and sha256(Path(__file__))==code_hash,'inputs_changed_during_fractional_enrichment')
    output.mkdir(parents=True)
    for name in summary['artifact_sha256']:
        if name not in ('index.html','records.json','closed_lots.csv','all_trade_episodes.csv','chart_manifest.csv','summary.json'):shutil.copy2(parent/name,output/name)
    attributed[attributed.open_trade_id.isin(ids)].to_csv(output/'closed_lots.csv',index=False)
    for name in ('all_trade_episodes.csv','chart_manifest.csv'):write_episode_csv(parent,output,name,episodes)
    partials.to_csv(output/'partial_closes_of_residual_entries.csv',index=False)
    (output/'records.json').write_text(json.dumps(renderer._json_safe(records),ensure_ascii=False,separators=(',',':'))+'\n');(output/'index.html').write_text(page)
    (output/'fractional_recap_manifest.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n')
    require(verify_hashes(source,identity)==bound and sha256(source/'manifest.json')==source_hash,'source_changed_during_fractional_enrichment')
    for name,digest in provenance['parent_artifact_sha256'].items():require(sha256(safe_member(parent,name))==digest,'parent_changed_during_fractional_enrichment')
    summary['artifact_sha256']={p.name:sha256(p) for p in output.iterdir() if p.name!='summary.json'};(output/'summary.json').write_text(json.dumps(renderer._json_safe(summary),ensure_ascii=False,indent=2)+'\n');return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','parent','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=enrich(a.source,a.parent,a.output);print(json.dumps(r['fractional_recap_enrichment'],ensure_ascii=False,indent=2))

if __name__=='__main__':main()
