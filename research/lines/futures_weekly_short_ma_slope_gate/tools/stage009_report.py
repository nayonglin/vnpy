"""Publish only a complete92-row same-capital reserve comparison; no replay."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,json,os,tempfile
import numpy as np
import pandas as pd
from stage009_accounting import compare_pair,require
from stage009_contract import STARTS,LINE,sha,load,validate_freeze
from stage009_derive import CACHE,FREEZE,REGISTRY,verify_cache,write_json,verify_map
from stage009_plots import render_five,FIGURE_NAMES

OUT=LINE/'artifacts/stage009_multistart'
VARIANTS=('A_idle','A_R','C_idle','C_R')


def require_complete(registry,cache_count,audit_count):
    require(len(registry.get('jobs',{}))==46 and all(j.get('status')=='validated' for j in registry['jobs'].values()),'all46_financial_validated')
    require(registry.get('financial_engine_batch_complete') is True and registry.get('financial_replays_started')==46,'all46_new_engines_completed')
    require(cache_count==92 and audit_count==46,'all92_caches_and46_audits_required')
    return True


def make_pairs(summary):
    keys=list(zip(summary.start,summary.variant));expected={(s,v) for s in STARTS for v in VARIANTS}
    require(len(keys)==92 and len(set(keys))==92 and set(keys)==expected,'exact92_summary')
    rows=[]
    for start in STARTS:
        for arm in ['A','C']:
            idle=summary.loc[summary.start.eq(start)&summary.variant.eq(arm+'_idle')].iloc[0].to_dict()
            reserve=summary.loc[summary.start.eq(start)&summary.variant.eq(arm+'_R')].iloc[0].to_dict()
            idle['initial_capital']=reserve['initial_capital']=300000.
            p=compare_pair(idle,reserve,start,'2026-10-29')
            p.update(arm=arm,cohort='January' if start[5:7]=='01' else 'June',eligible=p['vote_eligible'])
            for key in ['end_equity','total_return_pct','max_dd_pct','sharpe','total_slippage','modeled_fill_count']:
                p['idle_'+key]=idle[key];p['reserve_'+key]=reserve[key];p['delta_'+key]=reserve[key]-idle[key]
            p.update(total_transferred=reserve['total_transferred'],reserve_end_balance=reserve['reserve_end_balance'])
            rows.append(p)
    return pd.DataFrame(rows)


def cohort_summary(summary,paired):
    rows=[]
    for arm in ['A','C']:
        for cohort in ['January','June','combined']:
            for mature in [True,False]:
                p=paired.loc[paired.arm.eq(arm)&paired.vote_eligible.eq(mature)]
                if cohort!='combined':p=p.loc[p.cohort.eq(cohort)]
                q=summary.loc[summary.start.isin(p.start)&summary.variant.eq(arm+'_R')]
                n=len(p);voters=n if mature else 0
                r=dict(arm=arm,cohort=cohort,sample='complete_ge_1y' if mature else 'observation_lt_1y',windows=n,vote_windows=voters,observation_windows=0 if mature else n)
                for name,key,op in [('return_wins','return_comparison',1),('return_ties','return_comparison',0),('return_losses','return_comparison',-1),('dd_wins','dd_comparison',1),('sharpe_wins','sharpe_comparison',1)]:r[name]=int(p[key].eq(op).sum()) if mature else 0
                r['three_gate_pass_count']=int(p.three_gate_pass.sum()) if mature else 0
                for key in ['return_wins','dd_wins','sharpe_wins','three_gate_pass_count']:r[key+'_rate_pct']=r[key]/voters*100 if voters else None
                r.update(reserve_negative_return_count=int(q.total_return_pct.lt(0).sum()),reserve_nonpositive_total_windows=int(q.nonpositive_total_equity_days.gt(0).sum()),reserve_nonpositive_trading_windows=int(q.nonpositive_trading_equity_days.gt(0).sum()),median_transfer=float(q.total_transferred.median()) if n else None,exhausted_reserve_windows=int(q.reserve_end_balance.le(1e-6).sum()),median_dd_pct=float(q.max_dd_pct.median()) if n else None,worst_dd_pct=float(q.max_dd_pct.min()) if n else None,median_sharpe=float(q.sharpe.median()) if n else None,worst_sharpe=float(q.sharpe.min()) if n else None)
                if 'trading_margin_over100_days' in q:r['reserve_trading_margin_failure_windows']=int((q.trading_margin_over100_days.gt(0)|q.nonpositive_trading_equity_days.gt(0)).sum())
                rows.append(r)
    return pd.DataFrame(rows)


def build():
    require(not OUT.exists(),'immutable_report_already_exists')
    freeze,freeze_sha=validate_freeze(FREEZE);reg=load(REGISTRY)
    paths=list(CACHE.glob('*/ledger.json'));audits=list((LINE/'stages/stage009_independent_receipts').glob('*.json'))
    require_complete(reg,len(paths),len(audits));require(reg['freeze_sha256']==freeze_sha,'report_registry_freeze')
    sources={str(FREEZE):freeze_sha,str(REGISTRY):sha(REGISTRY)}
    for p in audits:
        r=load(p);require(str(r.get('status','')).startswith('PASS') and all(r.get(k)==0 for k in ['P0','P1','P2','failures']),'all_window_audits_pass')
        require(r.get('freeze_sha256')==freeze_sha,'window_audit_freeze');sources[str(p)]=sha(p)
    rows=[];daily=[];events=[]
    for start in STARTS:
        for variant in VARIANTS:
            dest=CACHE/(start.replace('-','')+'_'+variant);d=verify_cache(dest);m=d['metrics'];require(d['freeze_sha256']==freeze_sha and d['variant']==variant and d['start']==start,'cache_exact_report_window')
            roundstats=d['accounting']['complete_contract_rounds'];eligible=start!='2026-01-01'
            rows.append(dict(start=start,variant=variant,arm=d['arm'],mode=d['mode'],source_path=d['source_path'],vote_eligible=eligible,observation_only=not eligible,transfer_event_count=d['transfer_event_count'],**m,**d['risk'],**{'round_'+k:v for k,v in roundstats.items()},open_round_net_mtm=d['accounting']['open_round_net_mtm']))
            frame=pd.read_csv(dest/'daily.csv');frame['start']=start;frame['variant']=variant;daily.append(frame)
            if d['transfer_event_count']:
                e=pd.read_csv(dest/'reserve_events.csv');e['start']=start;e['variant']=variant;events.append(e)
            sources.update(d['sources_sha256']);sources.update(d['derivation_sources_sha256'])
            for p in dest.iterdir():
                if p.is_file():sources[str(p)]=sha(p)
    summary=pd.DataFrame(rows);paired=make_pairs(summary);cohorts=cohort_summary(summary,paired);curves=pd.concat(daily,ignore_index=True)
    require(len(curves)==141996,'all_actual_daily_points')
    figures=render_five(summary,paired,curves)
    code_paths=[Path(__file__),Path(__file__).with_name('test_stage009_report.py'),Path(__file__).with_name('stage009_plots.py'),Path(__file__).with_name('test_stage009_plots.py'),Path(__file__).with_name('stage009_derive.py'),Path(__file__).with_name('stage009_accounting.py'),Path(__file__).with_name('test_stage009_accounting.py')]
    sources.update({str(p.resolve()):sha(p) for p in code_paths})
    decision={}
    for arm in ['A','C']:
        q=cohorts.loc[cohorts.arm.eq(arm)&cohorts.cohort.eq('combined')&cohorts['sample'].eq('complete_ge_1y')].iloc[0]
        decision[arm]={k:q[k] for k in ['vote_windows','return_wins','return_losses','dd_wins','sharpe_wins','three_gate_pass_count','reserve_negative_return_count','reserve_nonpositive_total_windows','reserve_nonpositive_trading_windows','reserve_trading_margin_failure_windows','exhausted_reserve_windows']}
    passed=all(v['three_gate_pass_count']==22 and v['reserve_negative_return_count']==v['reserve_nonpositive_total_windows']==v['reserve_nonpositive_trading_windows']==v['reserve_trading_margin_failure_windows']==0 for v in decision.values())
    verdict='PASS_FIXED_USER_SCOPE_ONLY' if passed else 'MIXED_OR_FAIL_NO_RESCUE_TUNING'
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.stage009_report_',dir=OUT.parent) as td:
        t=Path(td)
        for name,frame in [('summary',summary),('paired',paired),('cohort_summary',cohorts),('all_daily',curves),('reserve_events',pd.concat(events,ignore_index=True) if events else pd.DataFrame())]:frame.to_csv(t/(name+'.csv'),index=False)
        for name,fig in figures.items():fig.savefig(t/name,dpi=160,bbox_inches='tight');fig.clear()
        write_json(t/'decision.json',dict(strategy_verdict=verdict,promotion_decision='NO_PROMOTION',arms=decision))
        write_json(t/'source_hashes.json',sources)
        comparison=dict(schema='stage009_23starts_two_bucket_report_v1',created_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),review_status='PENDING_INDEPENDENT_AGGREGATE_REVIEW',freeze_sha256=freeze_sha,source_head=freeze['source_head'],financial_source_head=freeze['source_head'],cutoff=freeze['cutoff'],starts=list(STARTS),variants=list(VARIANTS),arm_windows=46,summary_rows=92,paired_windows=46,independent_starts=23,complete_pairs_per_arm=22,observation_per_arm=1,expected_new_engines=46,total_initial_capital=300000,engine_initial_capital=150000,reserve_initial_capital=150000,total_daily_points=141996,five_figures=list(FIGURE_NAMES),strategy_verdict=verdict,promotion_decision='NO_PROMOTION',source_files_sha256=sources,arms=decision,limitations=['Overlapping start-to-cutoff histories are not independent statistical samples or new OOS.','Internal transfers are not PnL. Idle and reserve variants each have initial total wealth300000.','Unused reserve stays permanently excluded from trading risk and margin capacity; profit sizing uses all trading equity.','Zero commission; static configured exchange margin times1.65 is not historical broker capacity.','Available cached contract history is not proven complete listing/PIT truth.','Original next-open engine preserved; no new execution-time cash/quote/capacity gate.'])
        write_json(t/'comparison.json',comparison)
        (t/'report.md').write_text('# Stage009 30万总本金、15万交易＋15万隔离备用\n\n'+f'- 23起点至2026-10-29；46新回放；同30万闲置资金对照46份。结论{verdict}/NO_PROMOTION。\n- A_R/A_idle与C_R/C_idle分别比较；多头/多空新增MA过滤关闭，C保留空头底20%。\n- 总权益=交易桶+备用桶=300000+真实交易净盈亏。内部转账不算盈利。\n- 22成熟起点/臂、2026Jan观察1个/臂；不平均不同长度总收益预测未来。\n\n'+cohorts.to_markdown(index=False)+'\n')
        write_json(t/'delivery_manifest.json',dict(schema='stage009_pending_report_delivery_v1',files_sha256={p.name:sha(p) for p in t.iterdir() if p.is_file()},self_hash_excluded=True))
        verify_map(sources);os.rename(t,OUT)
    print(json.dumps(dict(report=str(OUT),strategy_verdict=verdict,arms=decision,total_daily_points=141996),ensure_ascii=False,default=float))


if __name__=='__main__':build()
