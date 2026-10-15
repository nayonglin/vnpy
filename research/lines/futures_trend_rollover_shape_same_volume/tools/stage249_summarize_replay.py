"""Stage249只读逐日现金流与完整持仓周期对账；不导入策略或回测引擎。"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import numpy as np
import pandas as pd

EPS=1e-6

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();src=a.source.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    files=['trades.csv','daily.csv','positions.csv','execution_clock.csv','execution_proxy_usage.csv','internal_equity_daily.csv','entry_candidates.csv','effective_parameters.json','minute_scan_requests.csv']
    hashes={name:hashlib.sha256((src/name).read_bytes()).hexdigest() for name in files}
    par=json.loads((src/'effective_parameters.json').read_text());t=pd.read_csv(src/'trades.csv').fillna('');u=pd.read_csv(src/'execution_proxy_usage.csv').fillna('');clock=pd.read_csv(src/'execution_clock.csv')
    assert t.trade_id.is_unique and u.trade_id.is_unique and clock.trade_id.is_unique
    assert set(t.trade_id)==set(u.trade_id)==set(clock.trade_id)
    t['date']=t.trade_id.map(clock.set_index('trade_id').trading_date)
    t['id']=t.trade_id.str.rsplit('.',n=1).str[-1].astype(int);t=t.sort_values('id').reset_index(drop=True)
    assert t.id.tolist()==list(range(1,len(t)+1))
    t=t.merge(u[['trade_id','signal_date','price_source']],on='trade_id',validate='one_to_one')
    t['cost']=t.apply(lambda x:x.volume*par['contract_sizes'][x.vt_symbol]*(x.price*par['rates'][x.vt_symbol]+par['slippages'][x.vt_symbol]),axis=1)
    t['cashflow']=t.apply(lambda x:-x.signed_volume*x.price*par['contract_sizes'][x.vt_symbol],axis=1)
    d=pd.read_csv(src/'daily.csv').sort_values('date');p=pd.read_csv(src/'positions.csv')
    eq=pd.read_csv(src/'internal_equity_daily.csv');candidates=pd.read_csv(src/'entry_candidates.csv')
    joined=d.merge(eq,on='date',validate='one_to_one');assert len(joined)==len(d)
    eqres=float((joined.account_equity-joined.estimated_equity).abs().max());assert eqres<EPS
    cs=candidates.merge(d[['date','account_equity']],on='date',validate='many_to_one');sizingres=float((cs.sizing_equity-cs.account_equity).abs().max());assert sizingres<EPS
    capital=float(d.account_capital.iloc[0]);assert abs(capital+t.cashflow.sum()-t.cost.sum()+sum(float(r.end_pos)*float(r.close_price)*par['contract_sizes'][r.vt_symbol] for r in p[p.date.eq(d.date.iloc[-1])].itertuples())-d.account_equity.iloc[-1])<EPS
    cash=t.groupby('date').apply(lambda g:(g.cashflow-g.cost).sum(),include_groups=False).reindex(d.date,fill_value=0).cumsum()
    marks=p[p.date.isin(d.date)].copy();marks['value']=marks.apply(lambda x:x.end_pos*x.close_price*par['contract_sizes'][x.vt_symbol],axis=1)
    value=marks.groupby('date').value.sum().reindex(d.date,fill_value=0)
    independent=capital+cash+value;cashres=float(np.max(np.abs(independent.to_numpy()-d.account_equity.to_numpy())));assert cashres<EPS
    active={};done=[];trade_to_root={};root_by_order={};retry_links=[]
    for x in t.to_dict('records'):
        sym=x['vt_symbol'];opening=x['offset']=='开'
        if sym not in active:
            assert opening
            # Synthetic retry inherits its ordinary parent order; no date/price heuristics.
            is_retry=x['price_source']=='stage847_intraday_reentry_at_original_entry'
            parent=x['order_id'].split('.intraday.')[0]
            if is_retry:
                assert parent in root_by_order and parent!=x['order_id'], 'unproven_retry_parent'
                original=t[t.order_id.eq(parent)&t.offset.eq('开')]
                assert len(original)==1 and original.iloc[0].vt_symbol==sym and original.iloc[0]['date']==x['date']
            root=root_by_order[parent] if is_retry else x['id']
            if root!=x['id']:retry_links.append({'root_id':root,'retry_id':x['id'],'order_id':x['order_id']})
            root_by_order[x['order_id']]=root
            active[sym]={'vt_symbol':sym,'product':re.sub(r'\d+','',sym),'direction':'long' if x['signed_volume']>0 else 'short','first_id':x['id'],'first_trade_id':x['trade_id'],'first_datetime':x['datetime'],'entry_date':x['date'],'signal_date':x['signal_date'],'entry_price':x['price'],'entry_source':x['price_source'],'root_id':root,'is_retry':root!=x['id'],'signed_pos':0.,'gross_pnl':0.,'cost':0.,'opened_volume':0.,'closed_volume':0.,'trade_ids':[]}
        z=active[sym]
        if opening:
            assert z['signed_pos']==0 or np.sign(z['signed_pos'])==np.sign(x['signed_volume']);z['opened_volume']+=x['volume']
        else:
            assert np.sign(z['signed_pos'])!=np.sign(x['signed_volume']) and abs(z['signed_pos'])+EPS>=x['volume'];z['closed_volume']+=x['volume']
        z['signed_pos']+=x['signed_volume'];z['gross_pnl']+=x['cashflow'];z['cost']+=x['cost'];z['trade_ids'].append(x['trade_id'])
        trade_to_root[x['id']]=z['root_id']
        if abs(z['signed_pos'])<EPS:
            z.update(last_id=x['id'],last_trade_id=x['trade_id'],last_datetime=x['datetime'],exit_date=x['date'],exit_price=x['price'],exit_reason=x['exit_reason'] or x['price_source'],net_pnl=z['gross_pnl']-z['cost'])
            done.append(z);del active[sym]
    cycles=pd.DataFrame(done).sort_values('last_id');open_rows=[]
    final_marks=p[p.date.eq(d.date.iloc[-1])].set_index('vt_symbol')
    for sym,z in active.items():
        mark=float(final_marks.loc[sym,'close_price']);z.update(mark_price=mark,mark_date=d.date.iloc[-1],net_mtm=z['gross_pnl']+z['signed_pos']*mark*par['contract_sizes'][sym]-z['cost']);open_rows.append(z)
    assert abs(cycles.net_pnl.sum()+sum(x['net_mtm'] for x in open_rows)-d.net_pnl.sum())<EPS
    assert abs(t.cost.sum()-d.slippage.sum()-d.commission.sum())<EPS
    assert abs(p[p.date.isin(d.date)].net_pnl.sum()-d.net_pnl.sum())<EPS
    episodes=[]
    for key,g in cycles.groupby('root_id',sort=True):
        if any(z['root_id']==key for z in open_rows):continue
        first=g.sort_values('first_id').iloc[0];last=g.sort_values('last_id').iloc[-1]
        episodes.append({'root_id':key,'entry_date':first.entry_date,'exit_date':last.exit_date,'net_pnl':g.net_pnl.sum(),'cost':g.cost.sum(),'cycle_count':len(g)})
    episodes=pd.DataFrame(episodes)
    def stats(g):
        v=g.net_pnl;wins=v[v>EPS];loss=v[v<-EPS]
        return {'closed_cycles':len(g),'wins':len(wins),'losses':len(loss),'win_rate_pct':len(wins)/len(g)*100 if len(g) else None,'net_pnl':float(v.sum()),'profit_factor':float(wins.sum()/-loss.sum()) if len(loss) else None}
    def period(start):
        before=d[d.date<start];dd=d[d.date>=start];initial=float(before.account_equity.iloc[-1]) if len(before) else capital
        path=np.r_[initial,dd.account_equity.to_numpy()];cohort=cycles[cycles.entry_date>=start]
        return {'start':start,'end':str(dd.date.iloc[-1]),'start_equity':initial,'end_equity':float(dd.account_equity.iloc[-1]),'return_pct':float((path[-1]/initial-1)*100),'net_mtm_pnl':float(dd.net_pnl.sum()),'max_dd_pct':float(((path/np.maximum.accumulate(path))-1).min()*100),'fill_count':int(dd.trade_count.sum()),'slippage':float(dd.slippage.sum()),'entry_cohort_complete_cycles':stats(cohort),'closed_in_period':stats(cycles[cycles.exit_date>=start]),'entry_cohort_complete_episodes':stats(episodes[episodes.entry_date>=start])}
    periods={'all':period('2020-01-01'),'since_202509':period('2025-09-01')}
    grouped=[]
    for frequency in ['year','month']:
        for key,g in d.groupby(d.date.str[:4 if frequency=='year' else 7]):
            previous=d[d.date<g.date.iloc[0]];initial=float(previous.account_equity.iloc[-1]) if len(previous) else capital
            rows=cycles[cycles.exit_date.str.startswith(key)];path=np.r_[initial,g.account_equity.to_numpy()]
            grouped.append({'frequency':frequency,'period':key,'start_equity':initial,'end_equity':path[-1],'net_mtm_pnl':g.net_pnl.sum(),'return_pct':(path[-1]/initial-1)*100,'max_dd_pct':((path/np.maximum.accumulate(path))-1).min()*100,'fill_count':int(g.trade_count.sum()),'slippage':g.slippage.sum(),**{f'exit_{k}':v for k,v in stats(rows).items()}})
    # Signal-to-trade AI evidence: retry follows its original signal.
    cand=candidates[candidates.candidate_status.eq('opened')].copy()
    cand['direction_match']=cand.direction if 'direction' in cand else ''
    for i,row in cycles.iterrows():
        match=cand[cand.date.eq(row.signal_date)&cand.contract_vt_symbol.eq(row.vt_symbol)]
        if 'direction' in match:match=match[match.direction.eq(row.direction)]
        if len(match)==1:
            for col in ['candidate_index','ai_product_pool_signal_date','ai_product_pool_rank','ai_product_pool_score','sizing_equity']:
                if col in match:cycles.loc[i,col]=match.iloc[0][col]
    for name,frame in [('complete_cycles',cycles),('complete_episodes',episodes),('open_positions',pd.DataFrame(open_rows)),('year_month_results',pd.DataFrame(grouped)),('retry_links',pd.DataFrame(retry_links)),('trades_costed',t)]:
        frame.to_csv(out/f'{name}.csv',index=False,encoding='utf-8-sig')
    scans=pd.read_csv(src/'minute_scan_requests.csv').drop_duplicates(['vt_symbol','trading_date'])
    checks={'status':'arithmetic_passed','source_hashes':hashes,'daily_rows':len(d),'fill_count':len(t),'equity_max_abs_residual':eqres,'sizing_max_abs_residual':sizingres,'independent_cashflow_max_abs_residual':cashres,'closed_cycles':len(cycles),'closed_episodes':len(episodes),'end_open_contracts':len(open_rows),'end_open_mtm':sum(x['net_mtm'] for x in open_rows),'scan_keys':len(scans),'incomplete_scan_keys':int(scans.coverage_status.ne('complete').sum()),'unique_missing_minutes':int(scans.missing_bar_count.sum()),'periods':periods}
    for name,digest in hashes.items():assert hashlib.sha256((src/name).read_bytes()).hexdigest()==digest
    (out/'summary.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in checks.items() if k!='source_hashes'},ensure_ascii=False))

if __name__=='__main__':main()
