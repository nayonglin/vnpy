"""Source-bound pure derivation of Stage009 reserve and same-capital idle controls."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,json,os,tempfile,time
import numpy as np
import pandas as pd
import stage008_accounting as previous
from stage009_accounting import bucket_curve,curve_metrics,close,require
from stage009_contract import STARTS,LINE,sha,load,validate_freeze,read_checkpoint,snapshot_dir

FREEZE=LINE/'stages/stage009_freeze.json'
REGISTRY=LINE/'outputs/stage009_multistart/registry.json'
CACHE=LINE/'outputs/stage009_derived/cache'


def write_json(path,doc):
    Path(path).write_text(json.dumps(previous.safe(doc),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def verify_map(mapping):
    for p,h in mapping.items():require(Path(p).is_file() and sha(p)==h,'derivation_source_changed:'+p)


def risk_metrics(d):
    require('total_margin_exact' in d,'raw_static_margin_required')
    out={}
    for label,key in [('trading','trading_account_equity'),('total','total_account_equity')]:
        ratio=d.total_margin_exact.astype(float)*1.65/d[key].where(d[key].gt(0))*100
        out[label+'_margin_peak_pct']=float(ratio.max()) if ratio.notna().any() else None
        out[label+'_margin_over100_days']=int(ratio.gt(100).sum())
        out[label+'_margin_undefined_days']=int(d[key].le(0).sum())
    return out


def raw_engine_curve_metrics(daily,capital=150000.):
    """Source parity for the auxiliary150k+PnL curve, never wealth performance.

    The frozen finance engine uses s650._sharpe even when raw equity crosses0.
    Legacy pure accounting deliberately returns None on that boundary. Preserve
    every legacy metric and use the exact source convention only for that None.
    Actual trading/total wealth and their survival are assessed separately.
    """
    m=previous.legacy.curve_metrics(daily,capital)
    if m['sharpe'] is None:
        r=daily.account_equity.astype(float).pct_change().replace([np.inf,-np.inf],np.nan).fillna(0.)
        std=float(r.std(ddof=1))
        m['sharpe']=float(r.mean()/std*np.sqrt(252)) if np.isfinite(std) and std>0 else 0.
        m['raw_sharpe_compat_applied']=True
    else:m['raw_sharpe_compat_applied']=False
    m['raw_curve_is_investable_wealth']=False
    return m


def load_reserve_raw_ledger(path,start,arm,freeze):
    tree,adapter=previous.loader_ast();env=dict(vars(previous.legacy))
    env.update(curve_metrics=raw_engine_curve_metrics,
        _stage008_gate_identity=previous.range_contract.validate_gate,
        _stage008_window_identity=lambda pre,daily:previous.validate_window(pre,daily,start))
    exec(compile(tree,str(Path(__file__))+'::raw_source_parity_adapter','exec'),env)
    x=env['_stage008_pure_accounting_loader'](path,'baseline' if arm=='A' else 'candidate')
    pre=x['preflight']
    require(pre['arm']==arm and pre['head']==freeze['source_head'] and pre['data_identity']==freeze['data_identity'],'actual_reserve_raw_identity')
    require(pre.get('daily_addon_enabled') is False and pre.get('long_price_range_gate_enabled') is False,'actual_reserve_disabled_modules')
    for side in ['short','long']:
        q=x['acceptances'][side+'_ma_slope_acceptance.json']
        require(q.get('enabled') is False and q.get('decision_count')==q.get('applied_block_count')==0 and q.get('MA_periods')==[],'actual_reserve_MA_off')
    previous.validate_disabled_long(x['acceptances'],True);previous.normalize_settings(x['settings'],start)
    x['loader_adapter']={**adapter,'raw_sharpe_only_None_source_compatibility':True,'financial_inventory_arithmetic_unchanged':True}
    return x


def load_signed_accounting(path,start,arm,freeze,job):
    """Reuse completed independent inventory audit; still rederive all cash math.

    Deep canary loading above was executed successfully for both arms. Each
    subsequent window already has that complete raw+funding audit in its signed
    receipt. Repeating the expensive inventory pass does not add independence.
    """
    rp=LINE/'stages/stage009_independent_receipts'/f'{start}_{arm}.json';r=load(rp)
    require(r.get('status')=='PASS_WITH_LIMITATIONS' and all(r.get(k)==0 for k in ['P0','P1','P2','failures']),'signed_window_audit_pass')
    require((r.get('requested_start'),r.get('arm'),r.get('end'))==(start,arm,freeze['cutoff']),'signed_window_scope')
    require(r.get('freeze_sha256')==sha(FREEZE) and r.get('frozen_source_head')==freeze['source_head'] and Path(r['path']).resolve()==path.resolve(),'signed_window_frozen_identity')
    require(r['source_files_sha256']==job['files_sha256']==snapshot_dir(path),'signed_window_exact_output_snapshot')
    sources={**r['source_files_sha256'],**load(path/'input_manifest.json'),str(rp):sha(rp)}
    auditor=LINE/'tools/stage009_independent_window.py'
    require(sha(auditor)==r['auditor_source_sha256'],'signed_window_auditor_source')
    sources[str(auditor)]=r['auditor_source_sha256']
    old=Path(r['old_raw_auditor_source']);require(sha(old)==r['old_raw_auditor_sha256'],'signed_raw_auditor_source');sources[str(old)]=r['old_raw_auditor_sha256']
    raw=pd.read_csv(path/'daily.csv');rounds=r['metrics']['rounds'];open_mtm=r['metrics']['open_round_net_mtm']
    require(close(rounds['closed_net_pnl']+open_mtm,raw.net_pnl.sum()),'signed_rounds_plus_open_PnL')
    count=0
    for chunk in pd.read_csv(path/'positions.csv',usecols=['date','vt_symbol','end_pos'],chunksize=100000):
        count+=int((chunk.date.astype(str).str[:10].eq(freeze['cutoff'])&chunk.end_pos.ne(0)).sum())
    return dict(daily=raw,accounting=dict(complete_contract_rounds=rounds,open_round_net_mtm=open_mtm,open_round_count=count),
        settings=load(path/'actual_strategy_settings.json'),effective=load(path/'effective_parameters.json'),metrics=r['raw_metrics'],
        loader_adapter=dict(mode='reuse_exact_signed_independent_raw_and_funding_inventory_audit',receipt=str(rp),receipt_sha256=sha(rp),core_checks=r['raw_core_checks'],funding_checks=r['funding_checks'],cash_math_independently_rederived=True,financial_replays=0),
        sources=sources,attempt_snapshot=r['source_files_sha256'],acceptances={p.name:load(p) for p in path.glob('*_acceptance.json')},
        position_audit=dict(source='signed_independent_audit',position_financial_rows=r['position_financial_rows'],raw_core_checks=r['raw_core_checks']))


def verify_cache(dest):
    manifest=load(dest/'delivery_manifest.json')
    verify_map({str(dest/p):h for p,h in manifest['files_sha256'].items()})
    doc=load(dest/'ledger.json');verify_map(doc['sources_sha256']);verify_map(doc['derivation_sources_sha256'])
    require(snapshot_dir(doc['source_path'])==doc['attempt_snapshot'],'cached_financial_source_snapshot_changed')
    return doc


def derive_one(start,arm,mode):
    require(start in STARTS and arm in {'A','C'} and mode in {'idle','reserve'},'exact_arm_window_mode')
    f,freeze_sha=validate_freeze(FREEZE);variant=arm+('_R' if mode=='reserve' else '_idle')
    dest=CACHE/(start.replace('-','')+'_'+variant)
    if dest.exists():return verify_cache(dest)
    sources={str(FREEZE):freeze_sha};accounting=None;events=[]
    if mode=='reserve':
        registry=load(REGISTRY);job=registry['jobs'][start+'|'+arm]
        require(registry['freeze_sha256']==freeze_sha and job['status']=='validated','financial_job_not_validated')
        checked=read_checkpoint(job['checkpoint'],f,freeze_sha,arm,start)
        require(checked['path']==job['path'] and checked['files_sha256']==job['files_sha256'],'checkpoint_registry_mismatch')
        path=Path(job['path']);proof=load(path/'reserve_acceptance.json')
        require(proof.get('accepted') is True and proof.get('enabled') is True,'actual_reserve_enabled_proof')
        phase=proof.get('phase_proof',{});checks=proof.get('checks_proof',{});snap=proof.get('snapshot_proof',{})
        require(phase.get('accepted') is True and phase.get('post_sizing_fill_count')==0 and phase.get('all_event_raw_account_equity_matches_same_day_raw_daily') is True,'actual_fill_phase_anchor')
        require(checks.get('accepted') is True and checks.get('nonpositive_equity_purchasing_power_guard') is True and snap.get('accepted') is True,'actual_signal_and_snapshot_proofs')
        x=load_signed_accounting(path,start,arm,f,job)
        raw=x['daily'];accounting=x['accounting'];settings=x['settings'];effective=x['effective'];raw_metrics=x['metrics'];adapter=x['loader_adapter']
        sources.update(x['sources']);events=load(path/'reserve_events.json')
        sources[str(Path(job['checkpoint']).resolve())]=sha(job['checkpoint'])
        attempt=x['attempt_snapshot'];gate_proofs=x['acceptances'];position_audit=x['position_audit']
    else:
        oldreg=load(f['idle_control_registry']);job=oldreg['jobs'][start+'|'+arm]
        oldcache=previous.CACHE/(start.replace('-','')+'_'+arm)
        old=previous.verify_cache(oldcache,job,deep=True);path=Path(old['source_path'])
        require(path==Path(job['path']) and old['start']==start and old['arm']==arm,'exact_idle_source')
        raw=pd.read_csv(path/'daily.csv');accounting=old['accounting'];settings=old['settings'];effective=old['effective'];raw_metrics=old['metrics'];adapter=old.get('loader_adapter',{})
        sources.update(old['source_files_sha256']);sources[str(oldcache/'ledger.json')]=sha(oldcache/'ledger.json')
        sources[str(oldcache/'delivery_manifest.json')]=sha(oldcache/'delivery_manifest.json')
        sources[str(Path(f['idle_control_registry']))]=f['idle_control_registry_sha256']
        attempt=old['attempt_snapshot'];gate_proofs=old['gate_certificates'];position_audit=old['position_audit']
    d=bucket_curve(raw,events,arm);m=curve_metrics(d);risk=risk_metrics(d)
    if mode=='reserve':
        declared=pd.read_csv(path/'reserve_daily.csv');metrics=load(path/'reserve_total_metrics.json')
        require(declared.date.astype(str).str[:10].tolist()==d.date.tolist(),'declared_reserve_daily_dates')
        for key in ['raw_account_equity','cumulative_transfer','trading_account_equity','reserve_balance','total_account_equity']:
            require(np.allclose(declared[key],d[key],rtol=1e-10,atol=1e-6),'declared_reserve_daily:'+key)
        require(metrics.get('initial_capital')==300000 and metrics.get('equity_basis')=='total_account_equity','declared_total_metric_basis')
        for key in ['end_equity','total_return_pct','max_dd_pct','sharpe','total_slippage']:
            require(close(m[key],metrics[key]),'declared_total_metric:'+key)
        require(close(m['modeled_fill_count'],metrics['total_trade_count']),'declared_fill_count')
    require(close(accounting['complete_contract_rounds']['closed_net_pnl']+accounting['open_round_net_mtm'],m['net_pnl']),'closed_open_total_PnL_bridge')
    derivation={str(p.resolve()):sha(p) for p in [Path(__file__),Path(__file__).with_name('test_stage009_derive.py'),Path(__file__).with_name('stage009_accounting.py'),Path(__file__).with_name('test_stage009_accounting.py'),Path(previous.__file__),Path(previous.legacy.__file__),Path(previous.range_contract.__file__)]}
    doc=dict(schema='stage009_pure_bucket_cache_v1',status='DERIVED_PENDING_INDEPENDENT_REVIEW',generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        key=start+'|'+variant,start=start,end=f['cutoff'],arm=arm,variant=variant,mode=mode,source_path=str(path),
        freeze_sha256=freeze_sha,source_head=f['source_head'],metrics=m,raw_engine_metrics=raw_metrics,raw_accounting_adapter=adapter,risk=risk,accounting=accounting,
        transfer_event_count=len(events),settings=settings,effective=effective,gate_certificates=gate_proofs,position_audit=position_audit,
        sources_sha256=sources,attempt_snapshot=attempt,derivation_sources_sha256=derivation,financial_replays=0,market_downloads=0,production_accesses=0)
    CACHE.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.stage009_derive_',dir=CACHE) as td:
        temp=Path(td);d.to_csv(temp/'daily.csv',index=False);pd.DataFrame(events).to_csv(temp/'reserve_events.csv',index=False)
        write_json(temp/'ledger.json',doc);write_json(temp/'delivery_manifest.json',dict(files_sha256={p.name:sha(p) for p in temp.iterdir() if p.is_file()},self_hash_excluded=True))
        verify_map(sources);verify_map(derivation);require(snapshot_dir(path)==attempt,'source_drift_during_derivation');os.rename(temp,dest)
    print('DERIVED '+doc['key']+' total_equity='+str(m['end_equity']),flush=True)
    return doc


def cache_ready():
    f,h=validate_freeze(FREEZE);r=load(REGISTRY);require(r['freeze_sha256']==h,'registry_freeze')
    for start in STARTS:
        for arm in ['A','C']:
            for mode in ['idle','reserve']:
                if mode=='reserve' and (r['jobs'][start+'|'+arm]['status']!='validated' or not (LINE/'stages/stage009_independent_receipts'/f'{start}_{arm}.json').is_file()):continue
                dest=CACHE/(start.replace('-','')+'_'+arm+('_R' if mode=='reserve' else '_idle'))
                if not dest.exists():derive_one(start,arm,mode)
    count=len(list(CACHE.glob('*/ledger.json')));print(json.dumps(dict(cache_count=count,expected=92,not_final_report=True)),flush=True)
    return count


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--watch',action='store_true');ap.add_argument('--start',choices=STARTS);ap.add_argument('--arm',choices=['A','C']);ap.add_argument('--mode',choices=['idle','reserve']);args=ap.parse_args()
    if args.start:
        require(args.arm and args.mode,'explicit_arm_and_mode_required');derive_one(args.start,args.arm,args.mode)
    elif args.watch:
        while cache_ready()<92:time.sleep(15)
    else:cache_ready()


if __name__=='__main__':main()
