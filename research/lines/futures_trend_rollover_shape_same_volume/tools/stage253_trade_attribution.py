"""Stage253 existing-run trade/candidate attribution. No strategy, replay, or download."""
from __future__ import annotations
from pathlib import Path
import argparse, ast, hashlib, json
import numpy as np
import pandas as pd

KEY=['signal_date','vt_symbol','direction']
EPS=1e-6

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def save(frame,path): frame.to_csv(path,index=False,encoding='utf-8-sig')
def period(value):
    y=int(str(value)[:4]);return '2020-2022' if y<=2022 else '2023-2025' if y<=2025 else '2026'
def stats(g):
    v=g.net_pnl;w=v[v>EPS];l=v[v<-EPS];top=w.nlargest(5)
    closed_v=g.loc[g.closed,'net_pnl'] if 'closed' in g else v
    return {'rows':len(g),'closed_rows':len(closed_v),'win_rate_scope':'closed_rows_only','pnl_and_normalized_mean_scope':'all_rows_including_open_mark_to_market','net_pnl':float(v.sum()),'wins':int((closed_v>EPS).sum()),'losses':int((closed_v<-EPS).sum()),'win_rate_pct':float((closed_v>EPS).mean()*100) if len(closed_v) else None,'positive_pnl':float(w.sum()),'negative_pnl':float(l.sum()),'top5_winner_pnl':float(top.sum()),'top5_share_positive_pct':float(top.sum()/w.sum()*100) if len(w) else None,'top5_share_net_pct':float(top.sum()/v.sum()*100) if abs(v.sum())>EPS else None,'mean_net_per_entry_lot':float(g.net_per_entry_lot.mean()),'mean_net_entry_notional_bps':float(g.net_entry_notional_bps.mean()),'median_net_entry_notional_bps':float(g.net_entry_notional_bps.median())}
def grouped(frame,columns):
    rows=[]
    for key,g in frame.groupby(columns,dropna=False,sort=True):
        if len(columns)==1:key=(key,) if not isinstance(key,tuple) else key
        row=dict(zip(columns,key),**stats(g))
        for col in ['source_run','data_completeness','ai_label_scope']:
            if col in g:
                assert g[col].nunique()==1
                row[col]=g[col].iloc[0]
        rows.append(row)
    return pd.DataFrame(rows)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[4]);ap.add_argument('--output',type=Path);args=ap.parse_args()
    root=args.root.resolve();line=root/'research/lines/futures_trend_rollover_shape_same_volume';base=line/'outputs';out=args.output or base/'stage253_ai_forensics/trade_attribution';out.mkdir(parents=True,exist_ok=True)
    paths={'A':base/'stage251_half_r_ab/A_final3','H':base/'stage251_half_r_ab/C_final','N':base/'stage252_no_ai_ab/C_diagnostic1','NH':base/'stage252_no_ai_ab/C_no_ai_no_half_r_existing_data'}
    setting=read(paths['A']/'actual_strategy_settings.json')[0]['actual'];elig_path=Path(setting['ai_product_pool_eligibility_path']);elig=pd.read_csv(elig_path);elig=elig[elig.strategy.eq(setting['ai_product_pool_strategy'])];assert not elig[['eval_date','product_vt_symbol']].duplicated().any()
    dates=sorted(elig.eval_date.unique());snapshots={d:g.set_index('product_vt_symbol') for d,g in elig.groupby('eval_date')}
    def label(signal,product):
        # Exactly strategy _ai_product_pool_snapshot searchsorted(side='left')-1.
        i=int(np.searchsorted(dates,str(signal),side='left'))-1;assert i>=0
        ev=dates[i];g=snapshots[ev];allowed=product in g.index;r=g.loc[product] if allowed else None
        category='static18_boundary' if ev=='2019-12-31' else 'fixed_fu' if product=='fu.SHFE' else 'monthly_ai_ranked'
        return {'replayed_ai_allowed':int(allowed),'replayed_eval_date':ev,'replayed_rank':int(r.score_rank) if allowed else None,'replayed_score':float(r.score) if allowed else None,'eligibility_class':category,'ai_label_scope':'posthoc_label_on_observed_trade_not_counterfactual','eligibility_source':str(elig_path)}
    runs={};evidence={};checks={};daily_contrib=[]
    for arm,src in paths.items():
        prov=read(src/'run_provenance.json');summ=read(src/'statistics_audit/summary.json');par=read(src/'effective_parameters.json');actual=read(src/'actual_strategy_settings.json')[0]['actual']
        evidence[arm]={'run_path':str(src),'diagnostic':prov['diagnostic_incomplete_minutes'],'minute_sha256':prov['minute_input_sha256'],'input_manifest_sha256':sha(src/'input_manifest.json'),'hashes':{}}
        assert prov['minute_input_unchanged_during_run'] and prov['all_data_and_model_inputs_unchanged_during_run'] and prov['captured_bar_failure_count']==0
        for name,digest in summ['source_hashes'].items():assert sha(src/name)==digest,(arm,name)
        names=['run_provenance.json','entry_candidates.csv','entry_risk.csv','positions.csv','minute_scan_requests.csv','execution_anchor_requests.csv','statistics_audit/complete_cycles.csv','statistics_audit/open_positions.csv','statistics_audit/complete_episodes.csv','statistics_audit/open_episodes.csv']
        evidence[arm]['hashes']={n:sha(src/n) for n in names}
        quality='strict_complete_accepted' if not prov['diagnostic_incomplete_minutes'] else 'diagnostic_incomplete_not_performance_accepted'
        cand=pd.read_csv(src/'entry_candidates.csv').rename(columns={'date':'signal_date','contract_vt_symbol':'vt_symbol'});assert not cand[KEY].duplicated().any();assert cand.ai_product_pool_use_next_trade_date_for_entry.eq(0).all()
        assert cand.signal_date.eq(cand.ai_product_pool_entry_effective_date).all()
        labels=pd.DataFrame([label(r.signal_date,r.product_vt_symbol) for r in cand.itertuples()]);cand=pd.concat([cand,labels],axis=1)
        if arm in ['A','H']:
            assert cand.ai_product_pool_allowed.eq(cand.replayed_ai_allowed).all()
            assert cand.ai_product_pool_signal_date.eq(cand.replayed_eval_date).all()
            assert cand.ai_product_pool_rank.eq(cand.replayed_rank.fillna(0)).all()
            assert np.max(abs(cand.ai_product_pool_score-cand.replayed_score.fillna(0)))<1e-10
        else:assert cand.ai_product_pool_allowed.eq(1).all()
        cand['arm']=arm;cand['source_run']=str(src);cand['data_completeness']=quality;cand['cohort_period']=cand.signal_date.map(period)
        cy=pd.read_csv(src/'statistics_audit/complete_cycles.csv');cy['closed']=True;op=pd.read_csv(src/'statistics_audit/open_positions.csv');op['closed']=False;op['net_pnl']=op.net_mtm
        cy=pd.concat([cy,op],ignore_index=True).sort_values('first_id');cy['leg']='ordinary';cy.loc[cy.is_retry,'leg']='retry';assert not cy[KEY+['leg']].duplicated().any()
        cy['size']=cy.vt_symbol.map(par['contract_sizes']);cy['entry_volume']=cy.opened_volume;cy['entry_notional']=cy.entry_volume*cy.entry_price*cy['size'];assert cy.entry_volume.gt(0).all()
        cy['net_per_entry_lot']=cy.net_pnl/cy.entry_volume;cy['net_price_units']=cy.net_pnl/(cy.entry_volume*cy['size']);cy['net_entry_notional_bps']=cy.net_pnl/cy.entry_notional*10000
        cy['arm']=arm;cy['source_run']=str(src);cy['data_completeness']=quality;cy['cohort_period']=cy.signal_date.map(period);cy['cohort_year']=cy.signal_date.str[:4];cy['cohort_month']=cy.signal_date.str[:7]
        cy=cy.drop(columns=['ai_product_pool_signal_date','ai_product_pool_rank','ai_product_pool_score'],errors='ignore')
        cy=pd.concat([cy.reset_index(drop=True),pd.DataFrame([label(r.signal_date,r.product) for r in cy.itertuples()])],axis=1)
        trade=pd.read_csv(src/'trades.csv').fillna('').set_index('trade_id');usage=pd.read_csv(src/'execution_proxy_usage.csv').fillna('').set_index('trade_id');scans=pd.read_csv(src/'minute_scan_requests.csv');scan=scans.sort_values('requested_start').drop_duplicates(['vt_symbol','trading_date']).set_index(['vt_symbol','trading_date']);anchors=pd.read_csv(src/'execution_anchor_requests.csv').set_index('order_id')
        assert anchors.index.is_unique
        for i,r in cy.iterrows():
            ids=ast.literal_eval(r.trade_ids);tr=trade.loc[ids];entry=tr[tr.offset.isin(['开','Open'])];assert len(entry)==1 and entry.iloc[0].volume==r.entry_volume
            cy.loc[i,'fills']=len(tr);cy.loc[i,'exit_signature']=json.dumps(tr[~tr.offset.isin(['开','Open'])][['datetime','price','volume','exit_reason']].to_dict('records'),ensure_ascii=False,sort_keys=True)
            cy.loc[i,'exit_timing_price_signature']=json.dumps(tr[~tr.offset.isin(['开','Open'])][['datetime','price','exit_reason']].to_dict('records'),ensure_ascii=False,sort_keys=True)
            ordinary=tr[~tr.order_id.str.contains('.intraday.',regex=False)];ar=anchors.reindex(ordinary.order_id);assert ar.coverage_status.notna().all()
            cy.loc[i,'incomplete_anchor_count']=int(ar.coverage_status.ne('complete').sum());cy.loc[i,'daily_fallback_count']=int(usage.loc[ids,'price_source'].eq('fallback_daily_next_open').sum())
            sk=(r.vt_symbol,r.entry_date);cy.loc[i,'entry_scan_status']=scan.loc[sk,'coverage_status'] if sk in scan.index else 'not_requested'
        cy['cycle_data_gap_observed']=cy.incomplete_anchor_count.gt(0)|cy.entry_scan_status.eq('incomplete')
        cy['entry_scan_complete']=cy.entry_scan_status.eq('complete')
        cy['all_cycle_ordinary_anchors_complete']=cy.incomplete_anchor_count.eq(0)
        cy['local_coverage_complete']=cy.entry_scan_complete&cy.all_cycle_ordinary_anchors_complete
        ep=[]
        for root_id,g in cy.groupby('root_id',sort=True):
            first=g.sort_values('first_id').iloc[0];last=g.sort_values('first_id').iloc[-1];row=first.to_dict();row.update(root_id=root_id,closed=bool(g.closed.all()),net_pnl=float(g.net_pnl.sum()),cost=float(g.cost.sum()),cycle_count=len(g),retry_count=int(g.is_retry.sum()),total_opened_volume=float(g.entry_volume.sum()),exit_date=last.exit_date if last.closed else '',last_datetime=last.last_datetime if last.closed else '',exit_reason=last.exit_reason if last.closed else 'open_mtm',exit_signature=json.dumps(g.exit_signature.tolist()),incomplete_anchor_count=int(g.incomplete_anchor_count.sum()),daily_fallback_count=int(g.daily_fallback_count.sum()),cycle_data_gap_observed=bool(g.cycle_data_gap_observed.any()))
            row['net_per_entry_lot']=row['net_pnl']/row['entry_volume'];row['net_price_units']=row['net_pnl']/(row['entry_volume']*row['size']);row['net_entry_notional_bps']=row['net_pnl']/row['entry_notional']*10000;ep.append(row)
            row.update(trade_ids=str([item for ids in g.trade_ids for item in ast.literal_eval(ids)]),last_id=last.last_id if last.closed else None,last_trade_id=last.last_trade_id if last.closed else '',exit_price=last.exit_price if last.closed else None,gross_pnl=float(g.gross_pnl.sum()),opened_volume=float(g.opened_volume.sum()),closed_volume=float(g.closed_volume.sum()),signed_pos=float(last.signed_pos),fills=int(g.fills.sum()),exit_timing_price_signature=json.dumps(g.exit_timing_price_signature.tolist()),entry_scan_complete=bool(g.entry_scan_complete.all()),all_cycle_ordinary_anchors_complete=bool(g.all_cycle_ordinary_anchors_complete.all()),local_coverage_complete=bool(g.local_coverage_complete.all()))
        ep=pd.DataFrame(ep);assert not ep[KEY].duplicated().any()
        expected=read(src/'metrics.json')['end_equity']-150000;assert abs(cy.net_pnl.sum()-expected)<EPS and abs(ep.net_pnl.sum()-expected)<EPS
        complete=pd.read_csv(src/'statistics_audit/complete_episodes.csv').set_index('root_id');assert set(complete.index)==set(ep.loc[ep.closed,'root_id'])
        assert np.max(abs(ep[ep.closed].set_index('root_id').net_pnl-complete.net_pnl))<EPS
        candidates_export=['arm','source_run','data_completeness']+KEY+['product_vt_symbol','entry_context','signal','candidate_status','skip_reason','selected_volume','sizing_equity','ai_product_pool_allowed','ai_product_pool_rank','replayed_ai_allowed','replayed_eval_date','replayed_rank','replayed_score','eligibility_class','ai_label_scope','eligibility_source','cohort_period']
        candidates_export += [x for x in cand if x.startswith('selection_pairwise') and ('score' in x or 'rank' in x or 'volume_tilt_multiplier' in x)]
        save(cand[candidates_export],out/f'{arm}_candidates.csv');save(cy,out/f'{arm}_cycles.csv');save(ep,out/f'{arm}_episodes.csv')
        pos=pd.read_csv(src/'positions.csv');pos['product']=pos.vt_symbol.str.replace(r'\d+','',regex=True);daily=pd.read_csv(src/'daily.csv');assert abs(pos.net_pnl.sum()-daily.net_pnl.sum())<EPS
        for dim,col in [('year',pos.date.str[:4]),('month',pos.date.str[:7]),('period',pos.date.map(period)),('product',pos['product'])]:
            for k,g in pos.groupby(col):daily_contrib.append({'arm':arm,'source_run':str(src),'data_completeness':quality,'basis':'actual_daily_mark_to_market','dimension':dim,'key':str(k),'net_pnl':float(g.net_pnl.sum()),'slippage':float(g.slippage.sum())})
        top=ep[ep.closed].nlargest(5,'net_pnl');save(top,out/f'{arm}_top5_winners.csv')
        checks[arm]={'cycles':len(cy),'closed_cycles':int(cy.closed.sum()),'episodes':len(ep),'closed_episodes':int(ep.closed.sum()),'candidate_count':len(cand),'reconciled_total_net_pnl':float(ep.net_pnl.sum()),'end_equity':expected+150000,'closed_episode_statistics':stats(ep[ep.closed]),'episodes_with_observed_data_gap':int(ep.cycle_data_gap_observed.sum()),'unique_episode_keys':True,'unique_cycle_keys_with_leg':True}
        runs[arm]={'cycles':cy,'episodes':ep,'candidates':cand,'daily':daily,'settings':actual}
    assert len({e['minute_sha256'] for e in evidence.values()})==1 and len({e['input_manifest_sha256'] for e in evidence.values()})==1
    contributions=pd.DataFrame(daily_contrib);save(contributions,out/'daily_mtm_contributions.csv')
    pair_results={}
    for left,right in [('H','NH'),('A','N')]:
        pair=f'{left}_vs_{right}';result={}
        assert {k for k in runs[left]['settings'].keys()|runs[right]['settings'].keys() if runs[left]['settings'].get(k)!=runs[right]['settings'].get(k)}=={'enable_ai_product_pool_filter'}
        for unit in ['episodes','cycles','candidates']:
            l=runs[left][unit];r=runs[right][unit];key=KEY+(['leg'] if unit=='cycles' else [])
            m=l.merge(r,on=key,how='outer',suffixes=('_on','_off'),indicator=True,validate='one_to_one');m['match_status']=m.pop('_merge').astype(str).replace({'both':'common','left_only':'AI_on_only','right_only':'AI_off_only'})
            if unit!='candidates':
                m['net_delta_off_minus_on']=m.net_pnl_off.fillna(0)-m.net_pnl_on.fillna(0);both=m.match_status.eq('common')
                m['entry_volume_changed']=both&~np.isclose(m.entry_volume_on.fillna(0),m.entry_volume_off.fillna(0));m['entry_price_changed']=both&~np.isclose(m.entry_price_on.fillna(0),m.entry_price_off.fillna(0));m['exit_path_changed']=both&m.exit_timing_price_signature_on.ne(m.exit_timing_price_signature_off)
                # Exact symmetric algebra decomposition, not causal attribution.
                m['size_term_off_minus_on']=np.where(both,(m.entry_volume_off-m.entry_volume_on)*(m.net_per_entry_lot_off+m.net_per_entry_lot_on)/2,np.nan)
                m['normalized_outcome_term_off_minus_on']=np.where(both,(m.net_per_entry_lot_off-m.net_per_entry_lot_on)*(m.entry_volume_off+m.entry_volume_on)/2,np.nan)
                assert np.max(abs(m.loc[both,'size_term_off_minus_on']+m.loc[both,'normalized_outcome_term_off_minus_on']-m.loc[both,'net_delta_off_minus_on']))<EPS
                assert abs(m.net_delta_off_minus_on.sum()-(checks[right]['reconciled_total_net_pnl']-checks[left]['reconciled_total_net_pnl']))<EPS
                result[unit]={'common':int(both.sum()),'AI_on_only':int(m.match_status.eq('AI_on_only').sum()),'AI_off_only':int(m.match_status.eq('AI_off_only').sum()),'common_entry_volume_changed':int(m.entry_volume_changed.sum()),'common_entry_price_changed':int(m.entry_price_changed.sum()),'common_exit_path_changed':int(m.exit_path_changed.sum()),'common_net_delta_off_minus_on':float(m.loc[both,'net_delta_off_minus_on'].sum()),'common_size_algebra_term':float(m.loc[both,'size_term_off_minus_on'].sum()),'common_normalized_outcome_algebra_term':float(m.loc[both,'normalized_outcome_term_off_minus_on'].sum()),'AI_on_only_net_pnl':float(m.loc[m.match_status.eq('AI_on_only'),'net_pnl_on'].sum()),'AI_off_only_net_pnl':float(m.loc[m.match_status.eq('AI_off_only'),'net_pnl_off'].sum()),'total_net_delta_off_minus_on':float(m.net_delta_off_minus_on.sum())}
                result[unit].update(common_mean_net_entry_notional_bps_on=float(m.loc[both,'net_entry_notional_bps_on'].mean()),common_mean_net_entry_notional_bps_off=float(m.loc[both,'net_entry_notional_bps_off'].mean()),common_net_per_lot_changed=int((both&~np.isclose(m.net_per_entry_lot_on.fillna(0),m.net_per_entry_lot_off.fillna(0))).sum()))
                for status in ['common','AI_on_only','AI_off_only']:save(m[m.match_status.eq(status)],out/f'{pair}_{unit}_{status}.csv')
                if unit=='episodes' and pair=='H_vs_NH':
                    examples=m[both&m.entry_volume_changed].assign(abs_net_delta=lambda g:g.net_delta_off_minus_on.abs()).nlargest(5,'abs_net_delta')
                    save(examples,out/'examples_common_signals_quantity_difference.csv')
            else:result[unit]=m.match_status.value_counts().to_dict()
            save(m,out/f'{pair}_{unit}_all.csv')
        pair_results[pair]=result
    cohorts=[]
    for arm,v in runs.items():
        for dimension in ['product','cohort_year','cohort_month','cohort_period','eligibility_class']:
            g=grouped(v['episodes'],[dimension]);g.insert(0,'dimension',dimension);g=g.rename(columns={dimension:'key'});g.insert(0,'arm',arm);cohorts.append(g)
    save(pd.concat(cohorts,ignore_index=True),out/'episode_cohort_contributions.csv')
    nh=runs['NH']['episodes'];posthoc=grouped(nh,['eligibility_class','replayed_ai_allowed']);save(posthoc,out/'NH_posthoc_ai_groups.csv')
    save(grouped(nh,['cohort_period','eligibility_class','replayed_ai_allowed']),out/'NH_posthoc_ai_groups_by_period.csv')
    save(grouped(nh,['cohort_year','eligibility_class','replayed_ai_allowed']),out/'NH_posthoc_ai_groups_by_year.csv')
    normalized_closed=grouped(nh[nh.closed],['eligibility_class','replayed_ai_allowed']);save(normalized_closed,out/'NH_posthoc_ai_groups_closed_only.csv')
    locally_complete=grouped(nh[nh.closed&nh.local_coverage_complete],['eligibility_class','replayed_ai_allowed'])
    locally_complete['limitation']='Local observed grid/anchors only; earlier account path may be affected by missing data; not OOS or complete causal validation.'
    save(locally_complete,out/'NH_posthoc_closed_local_coverage_complete.csv')
    blocked=nh[nh.closed&nh.eligibility_class.eq('monthly_ai_ranked')&nh.replayed_ai_allowed.eq(0)]
    save(blocked.nsmallest(5,'net_pnl'),out/'examples_NH_monthly_AI_would_block_losses.csv')
    save(blocked[blocked.net_pnl.gt(0)].nlargest(5,'net_pnl'),out/'examples_NH_monthly_AI_would_block_winners.csv')
    # Rank is only known for exported included products, not full-universe rejected ranks.
    save(grouped(nh,['eligibility_class','replayed_rank']),out/'NH_posthoc_known_rank_groups.csv')
    summary={'status':'existing_run_attribution_completed_no_new_backtest','primary_pair':'H_vs_NH','auxiliary_pair':'A_vs_N','key':KEY,'cycle_duplicate_resolution':'Explicit ordinary/retry leg only; episode keys and candidate keys unique; never cross-arm trade IDs','source_evidence':evidence,'eligibility_sha256':sha(elig_path),'eligibility_policy':'latest eval_date strictly earlier than signal_date; next-trade-date flag is zero in all exported candidates','historical_replay_validation':'Every A and H candidate allowed/eval_date/rank/score matched official snapshots exactly','rank_limitation':'CSV exports allowed products only; absent product rank/score left blank, never claimed rank>10','normalization':'Net after costs per initial opening lot, per initial lot*contract multiplier, and initial-entry-notional basis points; episode retry PnL divided by original opening denominator. Not portfolio returns. No fabricated initial R.','comparison_direction':'AI-off minus AI-on','pair_results':pair_results,'run_statistics':checks,'NH_posthoc_ai_groups':posthoc.to_dict('records'),'NH_closed_posthoc_ai_groups':normalized_closed.to_dict('records'),'limitations':['N/NH minute gaps and unverified execution anchors; same input bytes do not imply equal completeness on different paths.','Static18 pre-AI gate excluded fu; fixed fu after monthly launch is policy, not AI ranking.','Observed-trade posthoc labels are not a filtered counterfactual equity curve: filtering alters capital, concurrent slots, ranking, costs and later candidates.','Snapshot date discipline does not establish model training OOS or prevent historical model/rule selection bias.','Economic differences mix qualification, path-dependent sizing, exits and missing-data effects; algebra components are descriptive, not pure AI causal contributions.','Four existing runs on one historical window are not four independent out-of-sample tests.'],'script_sha256':sha(__file__)}
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    def table(df,cols):
        lines=['| '+' | '.join(cols)+' |','|'+'|'.join(['---']*len(cols))+'|']
        for row in df[cols].itertuples(index=False,name=None):lines.append('| '+' | '.join(f'{v:,.4f}' if isinstance(v,(float,np.floating)) else str(v) for v in row)+' |')
        return lines
    lines=['# Stage253 AI资格逐笔归因（既有结果）','','本报告只读取四臂既有结果，不回测、不补数、不改策略。主比较 H（AI开/0.5R关，严格）对 NH（AI关/0.5R关，缺分钟诊断）；辅比较 A 对 N。收益差额不能解释为纯AI因果。','', '## 匹配与对账','', '信号日+合约+方向是候选、episode唯一键。A/N存在同信号一次retry，cycle只再加ordinary/retry腿标记，绝不按跨臂tradeID匹配。所有完整和未平仓cycle、episode均输出，期末MTM参与净损益对账。','']
    for pair,result in pair_results.items():
        s=result['episodes'];lines += [f'- {pair}：共同episode {s["common"]}，AI开独有{s["AI_on_only"]}，AI关独有{s["AI_off_only"]}；共同项手数变化{s["common_entry_volume_changed"]}、入场价变化{s["common_entry_price_changed"]}、退出路径变化{s["common_exit_path_changed"]}。',f'  AI关−AI开净损益差{s["total_net_delta_off_minus_on"]:,.0f}；共同项差{s["common_net_delta_off_minus_on"]:,.0f}，AI开独有交易原组净额{s["AI_on_only_net_pnl"]:+,.0f}（计算AI关−AI开时取负，其差额贡献{-s["AI_on_only_net_pnl"]:+,.0f}），AI关独有交易原组净额{s["AI_off_only_net_pnl"]:+,.0f}（其差额贡献同为{s["AI_off_only_net_pnl"]:+,.0f}）。共同项对称代数拆分：数量项{s["common_size_algebra_term"]:,.2f}，每手结果项{s["common_normalized_outcome_algebra_term"]:,.2f}，二者精确加回；它们不是因果效应。']
    lines+=['','## NH既有交易的事后AI标签','','正式eligibility严格取信号日前最近快照；已逐一复现A/H所有候选的allowed、快照、rank和score。排除品种没有可用全宇宙rank，保持空值。静态18、月池后的固定fu、月池非fu排名分开，固定fu不是AI选出来的。','']
    lines+=table(posthoc,['eligibility_class','replayed_ai_allowed','rows','closed_rows','net_pnl','win_rate_pct','mean_net_entry_notional_bps','median_net_entry_notional_bps'])
    lines+=['','该表在NH已发生交易上分组，不能把“会放行”行直接累加称为AI策略收益。原账户资金、仓位和随后候选不会保持不变。net_pnl及每手/名义本金归一均值含期末未平仓MTM；wins、losses、win_rate_pct仅按closed_rows统计，未平仓不计胜负。closed_only文件同时排除未平仓损益后另报净损益和均值。','', '## 集中度与时间段','','前五赢家以完整episode排序，分母同时报全部正收益及净收益；净收益比可能超过100%，这是亏损抵消所致。','']
    concentration=pd.DataFrame([{'arm':a,**v['closed_episode_statistics']} for a,v in checks.items()]);lines+=table(concentration,['arm','rows','net_pnl','top5_winner_pnl','top5_share_positive_pct','top5_share_net_pct'])
    lines+=['','以下是实际逐日盯市净损益，不是按开仓年归属的交易cohort：',''];per=contributions[contributions.dimension.eq('period')].pivot(index='key',columns='arm',values='net_pnl').reset_index();lines+=table(per,['key','A','H','N','NH'])
    lines+=['','月池非fu的信号期分组（含期末MTM）：','']
    byperiod=grouped(nh[nh.eligibility_class.eq('monthly_ai_ranked')],['cohort_period','replayed_ai_allowed'])
    lines+=table(byperiod,['cohort_period','replayed_ai_allowed','rows','net_pnl','mean_net_entry_notional_bps'])
    lines+=['','## 局部覆盖及正反案例','','逐笔列 entry_scan_complete 按实际入场交易日匹配扫描记录；all_cycle_ordinary_anchors_complete 按本cycle全部普通成交的order绑定首锚。episode要求所有腿都满足。该标签只证明已有grid/锚状态，不抹去此前账户路径受缺数据影响的可能，不升级为独立OOS。','']
    lines+=table(locally_complete,['eligibility_class','replayed_ai_allowed','rows','net_pnl','mean_net_entry_notional_bps'])
    lines+=['','局部覆盖完整的月池会拦截子集仅6笔，选择偏差很强；不能将其当成完整月池效果估计。','', '以下是NH实际发生、月池事后会拦截的最大亏损和盈利各3笔。称为“会拦截”，不称为真实反事实避免损失：','']
    examples=pd.concat([blocked.nsmallest(3,'net_pnl'),blocked[blocked.net_pnl.gt(0)].nlargest(3,'net_pnl')])
    lines+=table(examples,['signal_date','vt_symbol','direction','net_pnl','net_entry_notional_bps','local_coverage_complete'])
    lines+=['','上述大额正反案例均有局部数据缺口，只能作为诊断路径的例子。共同信号的手数差异（金额差也可能含退出差）：','']
    examples=pd.read_csv(out/'examples_common_signals_quantity_difference.csv')
    lines+=table(examples,['signal_date','vt_symbol','entry_volume_on','entry_volume_off','net_pnl_on','net_pnl_off','exit_path_changed'])
    summary['NH_closed_local_coverage_complete_groups']=locally_complete.to_dict('records')
    summary['NH_monthly_groups_by_signal_period']=byperiod.to_dict('records')
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    lines+=['','年度、月份、品种的逐日贡献见daily_mtm_contributions.csv；按信号年/月/品种分组的完整与未平仓episode贡献另见episode_cohort_contributions.csv，二者不可混称。逐笔文件保留run路径、严格/诊断标签、局部扫描缺口及普通首锚状态。','', '## 判断边界','','本轮核验支持描述“已有路径中的选择与仓位差异”，不能证明AI泛化有效，也不能单凭关AI后变差证明没有过拟合。N/NH有缺分钟，静态18与fu固定资格混杂；同一窗口反复选择规则和模型仍有选择偏差。未做新参数搜索，本次属于有价值的只读证据整理。停止进一步扫阈值或按赢家倒推规则；是否泛化应依赖预声明、未参与设计的数据或真实前瞻记录，不能从这些收益差额中补造。']
    (out/'trade_report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'output':str(out),'pair_results':pair_results,'posthoc_groups':summary['NH_posthoc_ai_groups']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
