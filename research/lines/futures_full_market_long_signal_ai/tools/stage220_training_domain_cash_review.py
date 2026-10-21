"""Append-only four-new-book review; accepted phase1 is never rerun.

Reuse accepted158/132/102 pure ledger checks, not any strategy/account driver.
Old157 is summary/daily identity only. Original indices, no SQL or old replay.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import time
import traceback
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent; LINE=TOOLS.parent
PROTOCOL=LINE/'outputs/stage217_training_domain_loss_protocol/protocol.json'
PROTOCOL_SHA='b86c21d02b70e55181b7324efc1ebb6b363ee9d842738efe0f2baedfc3747b53'
OUTPUT=LINE/'outputs/stage220_training_domain_loss_review/cash2'
PHASE1=LINE/'outputs/stage220_training_domain_loss_review/model_forecast_selection1/review_receipt.json'
CM=LINE/'outputs/stage219_training_domain_loss_cash/actual_run1/manifest.json'
ARM='DOMAIN52'; CONTROL='CONTROL157_REUSED'
WINDOWS=('primary_2020','cold_2023'); COSTS=('base','stress')
HELPERS=('stage158_voluntary_review.py','stage132_contract_choice_review.py','stage102_cash_adapter.py',
         'stage102_cash_core.py','stage102_cash_diagnostics.py')

def binding(path):
    p=Path(path).resolve(); raw=p.read_bytes()
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def sources():
    return [binding(TOOLS/n) for n in ('stage220_training_domain_cash_review.py',
        'test_stage220_training_domain_cash_review.py',*HELPERS)]

def doc(b):
    assert binding(b['path'])=={k:b[k] for k in ('path','bytes','sha256')}
    return json.loads(Path(b['path']).read_text())

def stat(b):
    p=Path(b['path']); s=p.stat(); assert s.st_size==b['bytes']
    return dict(path=str(p.resolve()),bytes=s.st_size,inode=s.st_ino,device=s.st_dev,
        mtime_ns=s.st_mtime_ns,inherited_sha256=b['sha256'],rehashed=False)

def write(path,obj):
    def safe(value):
        if isinstance(value,dict): return {str(k):safe(v) for k,v in value.items()}
        if isinstance(value,(list,tuple)): return [safe(v) for v in value]
        if isinstance(value,np.ndarray): return safe(value.tolist())
        if isinstance(value,(np.integer,np.bool_)): return value.item()
        if isinstance(value,(float,np.floating)): return float(value) if math.isfinite(value) else None
        return value
    with Path(path).open('x') as f: json.dump(safe(obj),f,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False);f.write('\n')

def log_growth(daily):
    eq=np.asarray(daily.equity,float)
    flags=daily.ever_insolvent.astype(str).str.lower()
    assert flags.isin(['true','false','1','0']).all()
    if flags.isin(['true','1']).any() or not np.isfinite(eq).all() or (eq<=0).any(): return None
    return np.diff(np.log(np.r_[1000000.,eq]))

def paired(active,control,indices):
    assert indices.shape==(2000,len(active)) and indices.dtype.kind in 'iu' and indices.min()>=0 and indices.max()<len(active)
    aa,bb=log_growth(active),log_growth(control)
    if aa is None or bb is None:
        return dict(mean_daily_log_difference=None,cumulative_log_difference=None,ci95_low=None,ci95_high=None),np.full(2000,np.nan)
    delta=aa-bb; dist=delta[indices].mean(axis=1); low,high=np.quantile(dist,[.025,.975])
    return dict(mean_daily_log_difference=float(delta.mean()),cumulative_log_difference=float(delta.sum()),
        ci95_low=float(low),ci95_high=float(high)),dist

def gate(points,held,stale,unknown,wealth):
    assert set(points)=={(w,c) for w in WINDOWS for c in COSTS}
    finite=lambda x:x is not None and math.isfinite(float(x))
    own=all(finite(p['active_total_return_pct']) and p['active_total_return_pct']>0 for p in points.values())
    ret=all(finite(p['return_percentage_point_difference']) and (p['return_percentage_point_difference']>0
        if k==('primary_2020','stress') else p['return_percentage_point_difference']>=0) for k,p in points.items())
    dd_known=all(finite(p['drawdown_percentage_point_difference']) for p in points.values())
    dd=dd_known and all(p['drawdown_percentage_point_difference']>0 if k==('primary_2020','stress')
        else p['drawdown_percentage_point_difference']>=0 for k,p in points.items())
    ci=all(finite(p['ci95_low']) and p['ci95_low']>0 for p in points.values())
    hn=all(finite(g['known_u_equal_mean_increment_R']) and g['known_u_equal_mean_increment_R']>0 for g in held.values())
    hu=any(g['unknown_differential_selected_events']>0 for g in held.values())
    hp=hn and not hu and all(g['nominal_pass'] for g in held.values())
    cash=own and ret and dd and ci and wealth; financial_unknown=not dd_known or stale or unknown
    return dict(cash_nominal_pass=bool(cash),held_known_strictly_positive_all_two=bool(hn),held_known_nominal_pass=bool(hp),
        nominal_pass=bool(cash and hp and not financial_unknown),own_returns_positive_all_four=bool(own),return_gate=bool(ret),
        drawdown_gate=bool(dd),all_four_daily_log_CI_lower_positive=bool(ci),actual_wealth_positive=bool(wealth),
        financial_unknown=bool(financial_unknown),held_signal_unknown=bool(hu),execution_unknown=bool(unknown),any_historical_stale=bool(stale))

def verify_terminal_schemas(actual_terminal,financial_terminal):
    for d in (actual_terminal,financial_terminal):
        assert d['status']=='completed' and d['exit_code']==0
        assert d['cash_accounts_started']==d['new_cash_accounts']==d['raw_ledgers_checkpointed']==4
        assert d['actual_model_fit_calls']==d['native_source_queries']==d['new_labels']==0
    assert actual_terminal['old_control_cash_replays']==actual_terminal['old_baseline_replays']==0
    assert financial_terminal['old_control_book_replays']==0

def verify_phase_contract(phase,manifest):
    assert phase['schema']=='stage220_domain_model_review_v1' and phase['status']=='completed'
    assert phase['core_blockers']==0 and phase['new_prediction_model_rows']==1933480 and phase['cash_eligible'] is True
    assert manifest['schema']=='stage219_training_domain_loss_cash_v1' and manifest['status']=='completed'
    assert manifest['input_bindings']['fit_manifest']==phase['manifest']

def actual(auth,out):
    began=time.monotonic();out.mkdir(parents=True,exist_ok=False)
    try:
        phase=doc(auth['model_phase_receipt']); manifest=doc(auth['cash_manifest']); protocol=json.loads(PROTOCOL.read_text())
        verify_phase_contract(phase,manifest)
        producer=doc(phase['manifest']); inputs=protocol['input_bindings']; ci=manifest['input_bindings']
        assert manifest['schema']=='stage219_training_domain_loss_cash_v1' and manifest['status']=='completed'
        assert manifest['protocol_sha256']==PROTOCOL_SHA and manifest['new_cash_accounts']==4
        for field in ('actual_model_fit_calls','native_source_queries','new_labels','old_control_book_replays','old_baseline_replays'): assert manifest[field]==0
        for k,b in inputs.items(): assert ci[k]==b
        assert ci['fit_manifest']==phase['manifest']
        for k in ('choices_main','boundaries','held_diagnostic'): assert ci[k]==producer[k]
        for src in manifest['source_bundle']: assert binding(src['path'])==src
        terminal=doc(manifest['terminal']); financial=doc(manifest['financial_terminal'])
        verify_terminal_schemas(terminal,financial)
        assert terminal['cumulative_fit']==financial['cumulative_fit']==433 and terminal['cumulative_cash']==financial['cumulative_cash']==234
        spec=importlib.util.spec_from_file_location('accepted158cash',TOOLS/'stage158_voluntary_review.py')
        h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
        accepted_review=doc(inputs['control_cash_review'])
        assert accepted_review['completed'] and accepted_review['research_arithmetic_accepted'] and accepted_review['C']==accepted_review['I']==0
        old_sources={b['path']:b for b in accepted_review['source_bundle']}
        for n in HELPERS: assert binding(TOOLS/n)==old_sources[str(TOOLS/n)]
        r,cash,diag=h.helpers()
        baseline=doc(inputs['control_cash_manifest']); execution=doc(inputs['execution_protocol']); bridge=doc(inputs['market_protocol'])
        assert baseline['new_cash_accounts']==4 and len(baseline['accounts'])==4
        own_control={(a['window'],a['cost']):a for a in baseline['accounts']}
        assert set(own_control)=={(w,c) for w in WINDOWS for c in COSTS}
        cache_meta=doc(inputs['native_cache_manifest']); assert cache_meta['file']==inputs['native_cache']
        inherited={'native_cache':inputs['native_cache'],'mothers':inputs['mothers']}
        inherited.update({'bootstrap/'+w:execution['bootstrap_indices'][w] for w in WINDOWS})
        before={k:stat(b) for k,b in inherited.items()}
        cal=np.load(io.BytesIO(Path(inputs['calendar']['path']).read_bytes()),allow_pickle=False)
        calendar=([str(int(d))[:4]+'-'+str(int(d))[4:6]+'-'+str(int(d))[6:8] for d in cal]
            if cal.dtype.kind in 'iu' else cal.astype('datetime64[D]').astype(str).tolist())
        assert len(calendar)==5587 and calendar==sorted(set(calendar))
        store=r.NativeBars(calendar)
        with np.load(inputs['native_cache']['path'],allow_pickle=False) as z:
            epochs=z['epochs'].tolist(); offsets=z['offsets']; arrays={k:z[k] for k in ('days','values','accepted','valid','N','low20','run')}
            assert len(epochs)==9520 and offsets[0]==0 and offsets[-1]==1552456
            for i,e in enumerate(epochs): store.series[e]={k:v[int(offsets[i]):int(offsets[i+1])] for k,v in arrays.items()}
        econ_binding=bridge['economic_projection']; es=stat(econ_binding)
        economics=json.loads(Path(econ_binding['path']).read_text())['instruments']; assert set(economics)==set(store.series)
        assert es==stat(econ_binding) and manifest['economic_projection']==econ_binding
        mothers=h.numeric(pd.read_csv(inputs['mothers']['path'],dtype=str,keep_default_na=False,usecols=h.IDENTITY),['sequence_index','u_index'])
        assert len(mothers)==399252 and mothers.event_id.is_unique and mothers.family_id.nunique()==95
        choices=h.numeric(h.table(ci['choices_main']),['sequence_index','u_index','selected','chosen_action_sequence_index','score'])
        assert len(choices)==161014 and choices.arm.eq(ARM).all() and choices.scope.eq('main').all()
        picked=choices.loc[choices.selected.eq(1)]
        bounds=doc(ci['boundaries'])['epochs']; saved=h.table(manifest['signals'])
        numeric=['action_sequence_index','u_index','D_index','label_history_ready20','N_u','low20_u','u_close','history_run',
            'lifecycle_index','entry_capacity_qty','u_gross_capacity_qty','potential','score','source_lifecycle_index',
            'voluntary_boundary_index','effective_lifecycle_index']
        h.numeric(saved,numeric); assert saved.event_id.is_unique and saved.event_id.tolist()==picked.chosen_action_id.tolist()
        assert not saved.duplicated(['family_id','u_date']).any(); signals=saved.set_index('event_id',drop=False); origins=Counter()
        for c in picked.itertuples(index=False):
            epoch=c.chosen_epoch; u=h.integer(c.u_index); native=store.series[epoch]; j=store.locate(epoch,u)
            assert j is not None and native['valid'][j] and native['run'][j]>=20 and c.score>0
            gross,entry=r.capacity(native['values'][j,4],economics[epoch]['round_lot'])
            source=r.lifecycle(epoch,economics[epoch],calendar); b=bounds[epoch]; effective,origin=h.effective_boundary(source,b,u+1)
            want=dict(mother_event_id=c.event_id,action_sequence_index=h.integer(c.chosen_action_sequence_index),
                product_id=c.product_id,family_id=c.family_id,u_date=c.u_date,u_index=u,D_index=u+1,reference_epoch=epoch,
                anchor_epoch=c.anchor_epoch,label_history_ready20=1,N_u=float(native['N'][j]),low20_u=float(native['low20'][j]),
                u_close=float(native['values'][j,3]),history_run=h.integer(native['run'][j]),lifecycle_index=effective,
                entry_capacity_qty=h.integer(entry),u_gross_capacity_qty=h.integer(gross),potential=1,score=float(c.score),
                arm=ARM,control_id=ARM,policy='NARROW',cutoff=c.cutoff,source_lifecycle_index=source,
                voluntary_boundary_index=b['K_index'],effective_lifecycle_index=effective,effective_boundary_origin=origin,
                K_target_date=b['K_target_date'],K_date=b['K_date'],K_state=b['K_state'])
            h.fields(signals.loc[c.chosen_action_id].to_dict(),want,'new cash selected signal/native/K'); origins[origin]+=1
        signals['planned_execution_date']=[calendar[int(u)+1] for u in signals.u_index]
        trace=h.table(manifest['boundary_lineage']); assert trace.event_id.tolist()==saved.event_id.tolist()
        for key in trace:
            if key in numeric: h.compare(pd.to_numeric(trace[key].replace('',np.nan)),saved[key],'boundary sidecar '+key)
            else: assert trace[key].tolist()==saved[key].tolist()
        reports=doc(manifest['diagnostics']); old_reports=doc(baseline['diagnostics'])
        family=diag._read(Path(manifest['family_year_including_zero']['path']).parent,'family_year_including_zero')
        summtab=h.table(manifest['account_summaries']); annual=h.table(manifest['annual_slices']); capacity=h.table(manifest['capacity_summary'])
        assert len(summtab)==8 and len(capacity)==4
        accounts={(a['window'],a['cost']):a for a in manifest['accounts']}; assert set(accounts)==set(own_control)
        metrics={};daily={};logs={};book_checks=[];families=sorted(mothers.family_id.unique());sigdict=signals.to_dict('index')
        for key in [(w,c) for w in WINDOWS for c in COSTS]:
            w,c=key; a=accounts[key]; name=f'NARROW_{ARM}_{w}_{c}'; folder=Path(a['directory'])
            assert a['account_id']==name and a['arm']==ARM and folder==CM.parent/name and set(a['ledgers'])==set(h.LEDGERS)
            for role,b in a['ledgers'].items(): assert Path(b['path'])==folder/(role+'.csv.gz'); h.verify(b)
            summary=doc(a['summary']); window=execution['cash']['windows'][w]
            with h.cash_context(r,cash,cash.csv(folder/'positions.csv.gz')):
                arithmetic=cash.review_account(folder,c,dict(id=w,start=window[0],end=window[1]),execution,signals,economics,calendar,.25)
                native=r.account_native_and_capacity(folder,signals,mothers,store,economics,summary,c)
            roots=pd.concat([cash.csv(folder/'closed.csv.gz'),cash.csv(folder/'open.csv.gz')],ignore_index=True)
            for root in roots.to_dict('records'): h.check_root_boundary(root,sigdict)
            sf=family.loc[family.arm.eq(ARM)&family.window.eq(w)&family.cost.eq(c)]
            d,log,numbers,fy=diag._account(folder,summary,reports[name],sf,families);diag._daily_summary(d,summary,1000000.)
            row=summtab.loc[summtab.account.eq(name)]; assert len(row)==1
            h.fields(row.iloc[0].to_dict(),{k:v for k,v in summary.items() if not isinstance(v,(dict,list))},'new metric table')
            caps=capacity.loc[capacity.account.eq(name)];assert len(caps)==1
            h.fields(caps.iloc[0].to_dict(),{k:summary[k] for k in ('execution_unknown','unknown_capacity_fills','capacity_unknown_roots','entry_execution_unknown')},'new capacity table')
            ar=annual.loc[annual.account.eq(name)].sort_values('year');assert len(ar)==len(reports[name]['annual_slices'])
            for got,want in zip(ar.to_dict('records'),reports[name]['annual_slices']):h.fields(got,want,'new annual summary')
            assert summary['any_historical_stale']==(numbers['stale_days']>0)
            book_checks.append(dict(account_id=name,ledger=arithmetic,native=native,diagnostics=numbers,roots_checked=len(roots)))
            metrics[key]=summary;daily[key]=d;logs[key]=log
            write(out/(name+'.json'),book_checks[-1]);print(json.dumps(dict(phase='new_cash_book_verified',account=name)),flush=True)
        comp=h.table(manifest['comparisons']);dist=h.table(manifest['bootstrap_distributions']);references=doc(manifest['baseline_references'])
        assert len(comp)==4 and not comp.duplicated(['window','cost']).any() and len(dist)==2000
        points={};controls={};control_logs={};control_names=[]
        for w in WINDOWS:
            assert manifest['bootstrap_indices'][w]==execution['bootstrap_indices'][w]
            indices=np.load(execution['bootstrap_indices'][w]['path'],allow_pickle=False)
            for c in COSTS:
                key=(w,c); old=own_control[key]; name=f'NARROW_VOLUNTARY_RESELECT_{w}_{c}'; control_names.append(name)
                assert old['account_id']==name and old['arm']=='VOLUNTARY_RESELECT'
                ref=references[w+'_'+c]
                assert ref['source_account_id']==name and ref['summary']==old['summary'] and ref['daily']==old['ledgers']['daily']
                assert ref['source_only'] and not ref['replayed']
                control=doc(old['summary']); cd=pd.read_csv(old['ledgers']['daily']['path'],float_precision='round_trip')
                assert cd.date.tolist()==daily[key].date.tolist() and control['account']==name and control['arm']=='VOLUNTARY_RESELECT'
                stats,distribution=paired(daily[key],cd,indices); active=metrics[key]
                p=dict(stats,active_total_return_pct=active['total_return_pct'],reference_total_return_pct=control['total_return_pct'],
                    return_percentage_point_difference=active['total_return_pct']-control['total_return_pct'],
                    drawdown_percentage_point_difference=active['max_drawdown_pct']-control['max_drawdown_pct'])
                row=comp.loc[comp.window.eq(w)&comp.cost.eq(c)];assert len(row)==1
                h.fields(row.iloc[0].to_dict(),p,'four independent paired confidence comparisons')
                h.compare(pd.to_numeric(dist[w+'_'+c+'_'+ARM+'_minus_'+CONTROL].replace('',np.nan)),distribution,'original070 distribution '+w+c,atol=1e-12)
                row=summtab.loc[summtab.account.eq(name)];assert len(row)==1
                h.fields(row.iloc[0].to_dict(),dict({k:v for k,v in control.items() if not isinstance(v,(dict,list))},
                    arm=CONTROL,window=w,cost=c,source_only=True,replayed=False),'own157 control metrics identity')
                points[key]=p; controls[key]=control;control_logs[key]=log_growth(cd)
        assert set(summtab.account)==set(control_names)|{a['account_id'] for a in accounts.values()}
        stale=any(b['diagnostics']['stale_days']>0 for b in book_checks) or any(old_reports[n]['stale_days']>0 for n in control_names)
        unknown=any(s['execution_unknown'] for s in [*metrics.values(),*controls.values()])
        wealth=all(x is not None for x in [*logs.values(),*control_logs.values()])
        expected_gate=gate(points,phase['held_checks'],stale,unknown,wealth); saved_gate=doc(manifest['continuation_gate'])
        h.fields(saved_gate,expected_gate,'fixed217 independent cash plus held gate')
        for k,b in inherited.items(): assert stat(b)==before[k]
        receipt=dict(schema='stage220_training_domain_cash_review_v1',status='completed',core_blockers=0,model_phase_receipt=auth['model_phase_receipt'],
            cash_manifest=auth['cash_manifest'],source_bundle=sources(),accounts=book_checks,
            points=[dict(window=w,cost=c,**p) for (w,c),p in points.items()],gate=expected_gate,
            inherited_old_control_math=True,new_book_math_verified=4,old_book_reaudits=0,strategy_replays=0,
            fit=0,cash=0,SQL=0,models_or_forecasts_rerun=0,large_old_input_hash_scans=0,native_cache_reads=1,
            raw_database_reads=0,raw_database_hashes=0,old_actions_reads=0,bootstrap_indices_regenerated=False,
            cumulative_fit=433,cumulative_cash=234,elapsed_seconds=time.monotonic()-began,
            numerical_errors=h.ERRORS,accepted132_errors=r.ERRORS,remaining_core_problems=[],
            interpretation='fixed DOMAIN52 loss/K experiment; accounting acceptance is not alpha or increased-betting qualification')
        write(out/'review_receipt.json',receipt);write(out/'terminal.json',dict(status='completed',exit_code=0,elapsed_seconds=time.monotonic()-began))
        print(json.dumps(dict(status='completed',core_blockers=0,new_books_verified=4,gate=expected_gate)),flush=True)
    except BaseException as exc:
        write(out/'failure.json',dict(status='failed',error=str(exc),traceback=traceback.format_exc(),automatic_retry=False));raise

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--actual',required=True,action='store_true');p.add_argument('--authorization',required=True)
    p.add_argument('--authorization-sha256',required=True);p.add_argument('--output',type=Path,default=OUTPUT);args=p.parse_args(argv)
    out=args.output.resolve();assert out==OUTPUT and not out.exists()
    ab=binding(args.authorization);assert ab['sha256']==args.authorization_sha256;auth=doc(ab)
    assert auth['schema']=='stage217_exact_root_cash_review_authorization_v1' and auth['authorized_by']=='root' and auth['phase']=='cash'
    assert auth['protocol_sha256']==PROTOCOL_SHA and binding(PROTOCOL)['sha256']==PROTOCOL_SHA and auth['source_bundle']==sources()
    assert auth['output']==str(out) and auth['model_phase_receipt']['path']==str(PHASE1)
    assert auth['cash_manifest']['path']==str(CM)
    actual(auth,out)

if __name__=='__main__':main()
