"""Independent readonly audit of completed multi-contract frozen display artifacts.

No 071/072/063/financial strategy imports. Recompute quantity/cash allocation,
actual total-risk R, calendar weekly OHLC/MA, account curves and artifact closure.
Only writes a new explicit report JSON; never reruns finance or modifies inputs.
"""
import argparse,hashlib,json,math,re,subprocess,tempfile
from decimal import Decimal
from pathlib import Path
import numpy as np
import pandas as pd

BASELINE_SHA='859982f079da55aa1292154d5fc9b1004d1f0d5f23f75c4ec58ca892a102cb25'
RISK_FIELDS={'risk_amount','r_multiple','risk_per_lot','initial_risk_total','commission','slippage','cost','net_pnl'}
FIELDS=('open','high','low','close','volume','ma5','ma10','ma20','ma40')
NODE=Path('/Users/mac/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')

def check(ok,reason):
    if not ok:raise ValueError(reason)

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()

def read(path):return json.loads(Path(path).read_text())
def csv(path):return pd.read_csv(path,float_precision='round_trip')
def close(a,b,label):check(math.isclose(float(a),float(b),abs_tol=1e-6,rel_tol=1e-11),label)
def decmul(a,b):return float(Decimal(str(a))*Decimal(str(b)))

def bound_files(root,manifest=False):
    summary=read(root/('manifest.json' if manifest else 'summary.json'));entries=dict(summary['hashes' if manifest else 'artifact_sha256'])
    if manifest:entries.update({'code_snapshot/'+k:v for k,v in summary.get('code_snapshot_hashes',{}).items()})
    for name,digest in entries.items():
        path=(root/name).resolve();check(path.is_relative_to(root.resolve()) and path.is_file(),'unsafe_hash_member:'+name);check(sha(path)==digest,'artifact_hash:'+str(root)+':'+name)
    return {**entries,('manifest.json' if manifest else 'summary.json'):sha(root/('manifest.json' if manifest else 'summary.json'))}

def match_entries(trades,sizes):
    active={};complete={};partial=[];seen=set();all_cost=0.
    for r in trades.to_dict('records'):
        ident=str(r['trade_id']);check(ident not in seen,'duplicate_trade_id');seen.add(ident)
        q=r['volume'];check(not isinstance(q,bool) and math.isfinite(q) and q>0 and q==int(q),'trade_quantity');q=int(q)
        check(r['direction'] in ('long','short') and r['offset'] in ('open','close'),'trade_side')
        cost=float(r['commission'])+float(r['slippage']);check(cost>=0 and math.isfinite(cost),'trade_cost');all_cost+=cost
        side=r['direction'] if r['offset']=='open' else ('short' if r['direction']=='long' else 'long');key=(r['vt_symbol'],side)
        if r['offset']=='open':
            check(key not in active,'overlapping_open');active[key]={'entry':r,'remaining':q,'pieces':[]};continue
        check(key in active and q<=active[key]['remaining'],'close_quantity');a=active[key];e=a['entry'];entry_cost=(e['commission']+e['slippage'])*q/e['volume']
        gross=(r['price']-e['price'])*(1 if side=='long' else -1)*sizes[r['vt_symbol']]*q
        part=dict(open_trade_id=str(e['trade_id']),exit_trade_id=ident,volume=q,gross_pnl=gross,cost=entry_cost+cost,net_pnl=gross-entry_cost-cost,exit_price=r['price'])
        a['pieces'].append(part);a['remaining']-=q
        if a['remaining']==0:
            pieces=a['pieces'];gross=sum(p['gross_pnl'] for p in pieces);cash=float(e['commission']+e['slippage'])+sum((float(p['cost'])-float((e['commission']+e['slippage'])*p['volume']/e['volume'])) for p in pieces)
            risk=e['stage068_entry_risk'];check(risk>0 and math.isfinite(risk),'missing_initial_total_risk')
            complete[str(e['trade_id'])]=dict(volume=int(e['volume']),gross_pnl=gross,cost=cash,net_pnl=gross-cash,risk_amount=risk,r_multiple=gross/risk,weighted_exit_price=sum(p['exit_price']*p['volume'] for p in pieces)/e['volume'],entry_price=e['price'],exit_price=r['price'],exit_trade_id=ident,vt_symbol=e['vt_symbol'],direction=side,entry_date=e['date'],exit_date=r['date']);del active[key]
    residual={str(a['entry']['trade_id']):dict(volume=a['remaining'],original_open_volume=int(a['entry']['volume']),closed_volume=int(a['entry']['volume'])-a['remaining'],cost=(a['entry']['commission']+a['entry']['slippage'])*a['remaining']/a['entry']['volume']) for a in active.values()}
    partial=[p for a in active.values() for p in a['pieces']];remaining=sum(r['cost'] for r in residual.values())
    close(all_cost,sum(r['cost'] for r in complete.values())+sum(p['cost'] for p in partial)+remaining,'all_fill_cost_closure')
    return dict(complete=complete,partial=partial,residual=residual,remaining_entry_cost=remaining,all_fill_cost=all_cost)

def independent_weekly(market,contracts,calendar,symbols):
    market=market.copy();market['date']=pd.to_datetime(market.date).dt.normalize();check(not market.duplicated(['vt_symbol','date']).any(),'duplicate_market_key')
    cal=pd.DatetimeIndex(pd.to_datetime(calendar.date)).normalize();check(not cal.has_duplicates,'duplicate_calendar');ends=pd.Series(cal).groupby(cal.to_period('W-SUN')).max();metadata=contracts.set_index('vt_symbol');out={}
    groups={vt:g.sort_values('date') for vt,g in market.groupby('vt_symbol',sort=False)}
    false=lambda v:isinstance(v,(bool,np.bool_)) and not bool(v)
    for vt in sorted(symbols):
        g=groups[vt];listed=pd.to_datetime(metadata.loc[vt].get('listed_date'),errors='coerce');start=listed if pd.notna(listed) else g.date.min()
        local_ends=ends.loc[(ends.index>=start.to_period('W-SUN'))&(ends.index<=g.date.max().to_period('W-SUN'))];local_ends=local_ends[local_ends.ge(start)]
        values=g[['open','high','low','close','volume']].apply(pd.to_numeric,errors='coerce');valid=g.execution_only.map(false)&g.quote_class.eq('accepted_clean')&np.isfinite(values).all(axis=1)&values.gt(0).all(axis=1)
        if 'allow_new_open' in g:valid&=~g.allow_new_open.map(false)
        valid&=values.high.ge(values[['open','low','close']].max(axis=1))&values.low.le(values[['open','high','close']].min(axis=1));clean=g.loc[valid&g.date.ge(start)].copy();clean['week']=clean.date.dt.to_period('W-SUN')
        grouped={p:h for p,h in clean.groupby('week',sort=False)};rows=[]
        for period,end in local_ends.items():
            h=grouped.get(period);good=h is not None and bool(h.date.eq(end).any())
            row=dict(week=str(end.to_period('W-FRI')))
            row.update(dict(open=float(h.open.iloc[0]),high=float(h.high.max()),low=float(h.low.min()),close=float(h.close.iloc[-1]),volume=float(h.volume.sum())) if good else {k:float('nan') for k in FIELDS[:5]});rows.append(row)
        frame=pd.DataFrame(rows,columns=['week',*FIELDS[:5]])
        for n in (5,10,20,40):frame['ma'+str(n)]=frame.close.rolling(n,min_periods=n).mean()
        out[vt]=frame
    return out

def protected(records,mode):
    h=hashlib.sha256()
    for r in records:
        value={**r,'meta':{k:v for k,v in r['meta'].items() if not(mode=='risk' and k in RISK_FIELDS) and not(mode=='weekly' and k=='weekly_contract_display')}}
        if mode=='weekly':value.pop('weekly',None)
        h.update(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode());h.update(b'\n')
    return h.hexdigest()

def records_at(root):
    records=read(root/'records.json');text=(root/'index.html').read_text();marker='const records=';embedded,_=json.JSONDecoder().raw_decode(text[text.index(marker)+len(marker):]);check(embedded==records,'embedded_records:'+str(root));return records

def scripts(root,node):
    text=(root/'index.html').read_text();count=0
    with tempfile.TemporaryDirectory(prefix='fian-display081-js-') as tmp:
        for i,(attrs,body) in enumerate(re.findall(r'<script\b([^>]*)>(.*?)</script>',text,flags=re.S|re.I)):
            if not body.strip() or re.search(r'type=[\"\']application/(?:ld\+)?json',attrs):continue
            path=Path(tmp)/f'{i}.js';path.write_text(body);r=subprocess.run([str(node),'--check',str(path)],capture_output=True,text=True);check(r.returncode==0,'javascript_syntax:'+r.stderr);count+=1
    return count

def validate(source,baseline,raw=None,fractional=None,weekly=None,final=None,overview=None,node=NODE):
    source,baseline=Path(source).resolve(),Path(baseline).resolve();m=read(source/'manifest.json');check(sha(source/'manifest.json')=='7614f09d8dab584fae901901bfafc6dae7f72bca1beba4b6193195642f323d35','trusted_enabled_source_identity');stats=read(source/'summary.json');source_hashes=bound_files(source,True);base_hashes=bound_files(baseline,True)
    check(m['run_id']==source.name and m['baseline_run_manifest_sha256']==sha(baseline/'manifest.json')==BASELINE_SHA,'source_N_identity');check(not (source/'failure_snapshot.json').exists() and stats.get('performance_certifiable') is True,'source_failed_or_incomplete')
    check(m['fractional_risk_policy']['risk_fraction']==stats['fractional_risk_policy']['risk_fraction']==.0025 and m['parameters']['max_position_size']==2147483647,'source_fractional_policy')
    trades=csv(source/'trades.csv');metadata=csv(source/'contract_metadata.csv');result=match_entries(trades,metadata.set_index('vt_symbol')['size'].to_dict());expected=result['complete'];audit=csv(source/'open_budget_audit.csv');accepted=audit[audit.filled.astype(str).str.lower().eq('true')].set_index(audit[audit.filled.astype(str).str.lower().eq('true')].trade_id.astype(str));opens=trades[trades.offset.eq('open')]
    check(set(opens.trade_id.astype(str))==set(accepted.index) and len(opens)==len(accepted),'open_audit_ids')
    spec=metadata.set_index('vt_symbol')
    for r in opens.itertuples():
        a=accepted.loc[str(r.trade_id)];s=json.loads(r.stage068_signal_snapshot);mta=spec.loc[r.vt_symbol];risk=max(abs(r.price-s['stop_price'])*mta['size'],mta['pricetick']*mta['size'],1.)
        check(s==json.loads(a.signal_snapshot) and s['risk_fraction']==.0025 and s['target_risk_amount']==decmul(s['signal_equity'],.0025),'signal_budget_receipt')
        check(r.volume==s['authorized_volume']==a.volume and r.stage068_entry_risk==decmul(risk,int(r.volume)) and r.stage068_risk_per_contract==risk,'actual_total_risk')
        budget=min(s['target_risk_amount'],decmul(a.opening_equity,.0025));check(r.stage068_open_budget==a.opening_budget==budget and r.stage068_entry_risk<=budget,'actual_open_budget')
    frozen=csv(source/'closed_episodes.csv');check(set(frozen.open_trade_id.astype(str))==set(expected) and len(frozen)==stats['completed_episodes'],'complete_entry_ids')
    for r in frozen.itertuples():
        e=expected[str(r.open_trade_id)]
        for key in ('volume','gross_pnl','cost','net_pnl'):close(getattr(r,key),e[key],'closed_source:'+key)
        close(r.exit_price,e['weighted_exit_price'],'weighted_exit')
    partial=csv(source/'partial_closes_of_residual_entries.csv');parts={(p['open_trade_id'],p['exit_trade_id']):p for p in result['partial']};check(len(partial)==len(parts),'partial_count')
    for r in partial.itertuples():
        p=parts[(str(r.open_trade_id),str(r.exit_trade_id))]
        for key in ('volume','gross_pnl','cost','net_pnl'):close(getattr(r,key),p[key],'residual_partial:'+key)
    residual=read(source/'residual_open_positions.json');check({str(r['trade_id']) for r in residual}==set(result['residual']),'residual_ids')
    for r in residual:
        e=result['residual'][str(r['trade_id'])]
        for key in ('volume','original_open_volume','closed_volume'):check(r[key]==e[key],'residual_quantity')
        close(r['commission']+r['slippage'],e['cost'],'remaining_entry_cash')
    report=dict(independent_method_source_sha256='843e7bdcc8ffe3014d34e8195003a0dcbcf5cdf395ce7e06a9255318b4d38f52',quarter_formula_literal=.0025,status='PASS_DISPLAY_ONLY',source=str(source),source_manifest_sha256=sha(source/'manifest.json'),baseline=str(baseline),baseline_manifest_sha256=BASELINE_SHA,source_hashes=source_hashes,baseline_hashes=base_hashes,complete_entries=len(expected),complete_contracts=sum(e['volume'] for e in expected.values()),partial_segments=len(parts),residual_entries=len(residual),residual_contracts=sum(r['volume'] for r in residual),remaining_entry_cash_cost=result['remaining_entry_cost'],all_fill_cost=result['all_fill_cost'],actual_open_risk_receipts=len(opens),financial_replays=0,market_downloads=0,source_mutations=0,browser_status='separate_root_check_required',artifacts={})
    all_records={}
    for label,root in [('raw',raw),('fractional',fractional),('weekly',weekly),('final',final)]:
        if root is None:continue
        root=Path(root).resolve();summ=read(root/'summary.json');check(summ['source_manifest_sha256']==report['source_manifest_sha256'] and summ['backtest_metrics']==stats,'display_source:'+label);report['artifacts'][label]=dict(directory=str(root),hashes=bound_files(root),javascript_blocks=scripts(root,node));recs=records_at(root);all_records[label]=recs
        check({str(r['meta']['open_trade_id']) for r in recs}==set(expected) and len(recs)==len(expected),'display_complete_entries:'+label)
        if label!='raw':
            for r in recs:
                e=expected[str(r['meta']['open_trade_id'])];mta=r['meta']
                for key,a in [('volume',e['volume']),('realized_pnl',e['gross_pnl']),('net_pnl',e['net_pnl']),('cost',e['cost']),('risk_amount',e['risk_amount']),('r_multiple',e['r_multiple']),('weighted_exit_price',e['weighted_exit_price']),('exit_price',e['exit_price']),('entry_price',e['entry_price'])]:close(mta[key],a,'record_'+key)
                check(mta['exit_date']==e['exit_date'] and mta['entry_date']==e['entry_date'],'actual_entry_exit_dates')
                if mta['exit_source']==mta['vt_symbol']:close(mta['exit_marker_price'],e['exit_price'],'actual_final_exit_marker')
            page=(root/'index.html').read_text();check('0.25%' in page and '2500' in page and '每品种1手' not in summ['source_warning'],'multi_lot_display_text')
            if label in ('fractional','final'):check("['交易手数',m.volume]" in page and "['毛/净盈亏'" in page,'final_multilot_metric_labels')
    if {'raw','fractional'}.issubset(all_records):check(protected(all_records['raw'],'risk')==protected(all_records['fractional'],'risk'),'raw_fractional_nonfinancial_payload');report['raw_fractional_protected_sha256']=protected(all_records['raw'],'risk')
    if {'fractional','weekly'}.issubset(all_records):
        before,after=all_records['fractional'],all_records['weekly'];check(protected(before,'weekly')==protected(after,'weekly'),'nonweekly_payload')
        for a,b in zip(before,after):
            for key in ('label','x','width'):check(a['weekly'][key]==b['weekly'][key],'weekly_coordinate:'+key)
        tables=independent_weekly(csv(source/'market_daily.csv'),metadata,csv(source/'trading_calendar.csv'),{r['meta']['vt_symbol'] for r in after});slots=0;missing=0;max_delta=0.
        for r in after:
            w=r['weekly'];frame=tables[r['meta']['vt_symbol']].set_index('week').reindex(w['label']);slots+=len(w['label']);missing+=int(frame.close.isna().sum())
            for key in FIELDS:
                actual=np.array([np.nan if v is None else float(v) for v in w[key]]);wanted=frame[key].to_numpy(dtype=float);check(np.array_equal(np.isnan(actual),np.isnan(wanted)),'weekly_null_mask:'+key);check(np.allclose(actual,wanted,equal_nan=True,atol=1e-8,rtol=1e-12),'weekly_independent_values:'+key)
                delta=np.abs(actual-wanted);max_delta=max(max_delta,float(np.nanmax(delta)) if np.isfinite(delta).any() else 0.)
        report['exact_weekly']=dict(records=len(after),contracts=len(tables),slots=slots,missing_slots=missing,ohlcv_values=slots*5,ma_values=slots*4,max_absolute_delta=max_delta,nonweekly_sha256=protected(after,'weekly'))
    if {'weekly','final'}.issubset(all_records):check(sha(Path(weekly)/'records.json')==sha(Path(final)/'records.json'),'final_records_bytes_changed');report['final_records_byte_sha256']=sha(Path(final)/'records.json')
    if overview:
        overview=Path(overview).resolve();s=read(overview/'summary.json');report['artifacts']['overview']=dict(directory=str(overview),hashes=bound_files(overview),javascript_blocks=scripts(overview,node));check(s['source_manifest_sha256']==report['source_manifest_sha256'] and s['baseline_manifest_sha256']==BASELINE_SHA,'overview_identity')
        d=csv(source/'daily.csv');capital=stats['initial_capital'];equity=capital+d.net_pnl.cumsum();peak=equity.cummax().clip(lower=capital);draw=(equity/peak-1)*100;export=csv(overview/'equity_drawdown.csv');figure=read(overview/'figure.json')
        check(len(d)==len(export)==stats['total_days']==2862,'overview_2862_points');check(export.date.tolist()==d.date.tolist(),'overview_dates')
        check(np.allclose(d.equity,equity,rtol=0,atol=1e-5) and np.allclose(d.balance,equity,rtol=0,atol=1e-5),'independent_source_equity');close(stats['end_balance'],equity.iloc[-1],'independent_end_equity');close(stats['total_return'],(equity.iloc[-1]/capital-1)*100,'independent_total_return');close(stats['max_ddpercent'],draw.min(),'independent_max_drawdown');close(d.commission.sum(),trades.commission.sum(),'daily_fill_commission');close(d.slippage.sum(),trades.slippage.sum(),'daily_fill_slippage')
        for col,want in [('equity',equity),('high_watermark',peak),('drawdown_amount',equity-peak),('drawdown_pct',draw)]:check(np.allclose(export[col],want,atol=1e-7,rtol=0),'overview_csv:'+col)
        for trace,want in zip(figure['data'][:3],(equity/10000,peak/10000,draw)):
            check(len(trace['x'])==2862 and [str(x)[:10] for x in trace['x']]==d.date.tolist() and np.allclose(trace['y'],want,atol=1e-9,rtol=0),'plotly_all_points')
        bm=read(baseline/'summary.json')
        for row in s['comparison']:
            key=row['key'];check(key in ('initial_capital','end_balance','total_return','max_ddpercent','sharpe_ratio','payoff_ratio','profit_factor','win_rate_pct','completed_episodes','total_trade_count','total_commission','total_slippage'),'unrecognized_comparison_key')
            if key and bm.get(key) is not None and stats.get(key) is not None:
                close(row['baseline'],bm[key],'overview_N_comparison');close(row['candidate'],stats[key],'overview_new_comparison');close(row['delta'],stats[key]-bm[key],'overview_comparison_delta')
        page=(overview/'index.html').read_text();check('基线N' in page and '0.25%' in page and '2500' in page and '原风险预算后最多1手' not in page and '用户选定基线N' in page,'overview_text_contract')
        png=(overview/'equity_drawdown.png').read_bytes();check(png.startswith(b'\x89PNG\r\n\x1a\n') and len(png)>1000,'overview_png');report['overview']=dict(points=2862,traces=3,comparison_rows=len(s['comparison']),png_bytes=len(png))
    for artifact in report['artifacts'].values():check(bound_files(Path(artifact['directory']))==artifact['hashes'],'artifact_changed_during_audit')
    check(bound_files(source,True)==source_hashes and bound_files(baseline,True)==base_hashes,'source_changed_during_audit');report['validator_sha256']=sha(Path(__file__));return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','baseline','output'):parser.add_argument('--'+name,type=Path,required=True)
    for name in ('raw','fractional','weekly','final','overview'):parser.add_argument('--'+name,type=Path)
    parser.add_argument('--node',type=Path,default=NODE);a=parser.parse_args();check(not a.output.exists(),'report_already_exists')
    for root in (a.source,a.baseline,a.raw,a.fractional,a.weekly,a.final,a.overview):
        if root:check(not a.output.resolve().is_relative_to(root.resolve()),'report_inside_frozen_input')
    report=validate(a.source,a.baseline,a.raw,a.fractional,a.weekly,a.final,a.overview,a.node);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('source_hashes','baseline_hashes','artifacts')},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
