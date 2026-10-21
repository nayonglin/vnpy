"""Frozen121 fixed12-calendar-month return chain; one source read, no fit/cash.

For each v the representative known at prev(v) supplies both same-epoch closes.
The complete mother and missing states stay intact. Actual requires exact root
bindings and a fresh output; imports/semantic fixtures do no actual source I/O.
"""
from __future__ import annotations
import argparse
from bisect import bisect_right
from datetime import date,datetime,timezone
import importlib.util
import io
import json
from pathlib import Path
import time
import numpy as np
import pandas as pd
TOOLS=Path(__file__).resolve().parent;LINE=TOOLS.parent
PROTOCOL=LINE/'outputs/stage121_long_history_protocol/protocol.json'
PROTOCOL_SHA='c9a9538de0160266624c2bbfd8912964a44b2cfda97e639d1079fb1614bd7421'
STAGE_ROOT=LINE/'outputs/stage122_long_history_projection'
INPUT_ROLES={'market_protocol','narrow_labels','narrow_manifest'}
def _module(name,file):
    spec=importlib.util.spec_from_file_location(name,TOOLS/file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
legacy=_module('stage122_accepted071','stage071_settlement_narrow_fit.py')
kernel=_module('stage122_accepted070kernel','stage070_policy_kernel.py')
IDENTITY=legacy.IDENTITY
file_binding=legacy.file_binding;read_bound=legacy.read_bound;same_binding=legacy.same_binding
write_json=legacy.write_json;write_csv=legacy.write_csv
FACTOR_COLUMNS=IDENTITY+['prev_u_date','prev_u_index','prev_reference_epoch','prev_close','current_close','factor','factor_observed','factor_state','economics_status']
PROJECTION_COLUMNS=IDENTITY+['lower_boundary_date','window_first_date','window_source_days','valid_factor_days','missing_factor_days','first_missing_factor_date','external_scalar_raw','external_observed','external_missing','projection_state','missing_reason']
def source_bundle():
    return sorted([file_binding(TOOLS/n) for n in ('stage122_long_history_projection.py','test_stage122_long_history_projection.py','stage071_settlement_narrow_fit.py','stage070_policy_kernel.py','stage042_cross_session_experiment.py')],key=lambda b:b['path'])
def lower_boundary(day):
    d=date.fromisoformat(day)
    try:return d.replace(year=d.year-1).isoformat()
    except ValueError:return d.replace(year=d.year-1,day=28).isoformat()
def project_mother(mother,market,economics):
    """Pure projection from accepted arrays; original native indices retained."""
    if mother.duplicated(['product_id','u_date']).any() or mother.event_id.duplicated().any():raise ValueError('duplicate mother identity')
    calendar=sorted(mother.u_date.unique());ranks={d:i for i,d in enumerate(calendar)}
    day_index=mother[['u_date','u_index']].drop_duplicates()
    if day_index.u_date.duplicated().any() or day_index.u_index.duplicated().any():raise ValueError('native calendar mapping differs')
    mapping=dict(zip(day_index.u_date,day_index.u_index))
    if any(mapping[a]>=mapping[b] for a,b in zip(calendar,calendar[1:])):raise ValueError('native calendar not monotonic')
    boundaries=[lower_boundary(d) for d in calendar];starts=[bisect_right(calendar,b) for b in boundaries]
    projected=[];audits=[]
    for product,part in mother.groupby('product_id',sort=True):
        part=part.sort_values('u_date')
        if part.u_date.tolist()!=calendar:raise ValueError('full mother product calendar differs')
        rows=part[IDENTITY].to_dict('records');factors=[];factor_states=[]
        for i,row in enumerate(rows):
            prev=rows[i-1] if i else None;epoch=prev['reference_epoch'] if prev else ''
            econ=economics.get(epoch,{})
            audit=dict(row,prev_u_date=prev['u_date'] if prev else '',prev_u_index=int(prev['u_index']) if prev else -1,
                prev_reference_epoch=epoch,prev_close=np.nan,current_close=np.nan,factor=np.nan,factor_observed=0,
                factor_state='',economics_status=econ.get('economics_status','unresolved_exact_epoch_metadata'))
            if prev is None:state='no_previous_mother_date'
            elif not epoch:state='no_previous_reference_epoch'
            elif not kernel.qualified_economics(econ):state='unqualified_epoch_economics'
            else:
                left=market.bar(epoch,int(prev['u_index']));right=market.bar(epoch,int(row['u_index']))
                audit['prev_close']=left['close'] if left else np.nan;audit['current_close']=right['close'] if right else np.nan
                if left is None:state='missing_or_invalid_previous_native_bar'
                elif right is None:state='missing_or_invalid_current_native_bar'
                else:
                    with np.errstate(over='ignore',invalid='ignore',divide='ignore'):factor=float(np.float64(right['close'])/np.float64(left['close']))
                    if not np.isfinite(factor) or factor<=0:state='nonfinite_or_nonpositive_factor'
                    else:audit.update(factor=factor,factor_observed=1);state='observed_same_epoch_pair'
            audit['factor_state']=state;audits.append(audit);factors.append(audit['factor']);factor_states.append(state)
        values=np.array(factors,float);valid=np.isfinite(values)&(values>0)
        logs=np.zeros(len(values));logs[valid]=np.log(values[valid]);logsum=np.r_[0.,np.cumsum(logs)]
        invalidsum=np.r_[0,np.cumsum(~valid)]
        for i,row in enumerate(rows):
            j=starts[i];n=i-j+1;bad=int(invalidsum[i+1]-invalidsum[j]);observed=False;q=np.nan
            reason=''
            if calendar[0]>boundaries[i]:reason='insufficient_calendar_history'
            elif n<=0:reason='empty_calendar_window'
            elif bad:reason='missing_required_daily_factor'
            else:
                with np.errstate(over='ignore',invalid='ignore',under='ignore'):q=float(np.expm1(logsum[i+1]-logsum[j]))
                if not np.isfinite(q) or q<-1:reason='nonfinite_cumulative_return';q=np.nan
                else:observed=True
            missing_indices=np.flatnonzero(~valid[j:i+1]) if n>0 else []
            projected.append(dict(row,lower_boundary_date=boundaries[i],window_first_date=calendar[j] if n>0 else '',
                window_source_days=max(n,0),valid_factor_days=max(n,0)-bad,missing_factor_days=bad,
                first_missing_factor_date=calendar[j+int(missing_indices[0])] if len(missing_indices) else '',
                external_scalar_raw=q if observed else np.nan,external_observed=int(observed),external_missing=int(not observed),
                projection_state='observed_fixed12_calendar_month_return_chain' if observed else 'missing',missing_reason=reason))
    projection=pd.DataFrame(projected,columns=PROJECTION_COLUMNS).sort_values('sequence_index').reset_index(drop=True)
    audit=pd.DataFrame(audits,columns=FACTOR_COLUMNS).sort_values('sequence_index').reset_index(drop=True)
    legacy._identity(mother,projection);legacy._identity(mother,audit)
    return projection,audit

def authorize(args):
    out=Path(args.output).resolve()
    if STAGE_ROOT.resolve() not in out.parents or out.exists():raise ValueError('fresh Stage122 output required')
    if args.protocol_sha256!=PROTOCOL_SHA or file_binding(PROTOCOL)['sha256']!=PROTOCOL_SHA:raise ValueError('frozen121 protocol required')
    protocol=json.loads(PROTOCOL.read_bytes());binding=file_binding(args.authorization)
    if binding['sha256']!=args.authorization_sha256:raise ValueError('authorization SHA differs')
    auth=json.loads(read_bound(binding));required=dict(schema='stage121_exact_root_authorization_v1',authorized_by='root',stage='projection',exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(out))
    if any(auth.get(k)!=v for k,v in required.items()):raise ValueError('exact root122 authorization required')
    if sorted(auth.get('source_bundle',[]),key=lambda b:b['path'])!=source_bundle():raise ValueError('projection source bundle differs')
    if set(auth.get('input_bindings',{}))!=INPUT_ROLES:raise ValueError('projection input roles differ')
    for role in INPUT_ROLES:
        if not same_binding(auth['input_bindings'][role],protocol['inputs'][role]):raise ValueError('fixed121 input binding differs '+role)
    return out,protocol,auth,binding

def run_actual(out,protocol,auth,authorization):
    out.mkdir(parents=True,exist_ok=False);started=time.monotonic();bundle=source_bundle();inputs=auth['input_bindings'];sql=0
    write_json(out/'actual_started.json',dict(status='started',started_utc=datetime.now(timezone.utc).isoformat(),protocol=file_binding(PROTOCOL),source_bundle=bundle,authorization=authorization,fixture=False))
    try:
        narrow=json.loads(read_bound(inputs['narrow_manifest']))
        if narrow.get('schema')!='stage070_narrow_labels_v1' or narrow.get('status')!='completed' or not same_binding(narrow.get('labels_narrow',{}),inputs['narrow_labels']):raise ValueError('accepted mother manifest differs')
        mother=pd.read_csv(io.BytesIO(read_bound(inputs['narrow_labels'])),compression='gzip',usecols=IDENTITY,dtype=str,keep_default_na=False)
        legacy._numeric(mother,['sequence_index','u_index'])
        if len(mother)!=399252 or mother.event_id.duplicated().any() or not np.array_equal(mother.sequence_index,np.arange(399252)) or mother.u_date.nunique()!=4074 or mother.product_id.nunique()!=98 or mother.family_id.nunique()!=95:raise ValueError('complete mother identity differs')
        panel,market,dates,economics,scope_dates,receipt,_=kernel.load_market_bridge(auth);sql=kernel.ref.NATIVE_QUERIES
        if sql!=1:raise ValueError('exact one shared source query required')
        compare=mother.merge(panel[['event_id','product_id','u_date','reference_epoch']],on='event_id',suffixes=('','_native'),validate='one_to_one')
        if len(compare)!=len(mother) or any(not compare[c].eq(compare[c+'_native']).all() for c in ('product_id','u_date','reference_epoch')):raise ValueError('mother vs accepted native representative differs')
        if (panel.exchange.nunique()!=6 or sorted(mother.u_date.unique())!=scope_dates or
                not mother.u_date.eq(mother.u_index.map(lambda k:dates[int(k)])).all()):raise ValueError('source/mother native calendar mapping differs')
        projection,audit=project_mother(mother,market,economics)
        p=write_csv(out/'long_history_projection.csv.gz',projection);a=write_csv(out/'daily_factor_audit.csv.gz',audit)
        write_json(out/'source_read_receipt.json',receipt)
        write_json(out/'summary.json',dict(schema='stage122_long_history_projection_summary_v1',mother_rows=len(mother),products=98,families=95,exchanges=6,mother_dates=4074,native_calendar_dates=len(dates),observed=int(projection.external_observed.sum()),missing=int(projection.external_missing.sum()),missing_reasons=projection.missing_reason.value_counts().to_dict(),factor_states=audit.factor_state.value_counts().to_dict(),scalar_min=float(projection.external_scalar_raw.min()) if projection.external_observed.any() else None,scalar_max=float(projection.external_scalar_raw.max()) if projection.external_observed.any() else None,true_zero_observed=int((projection.external_observed.eq(1)&projection.external_scalar_raw.eq(0)).sum()),goal_complete=False,production_qualified=False))
        if source_bundle()!=bundle:raise ValueError('source changed during actual projection')
        terminal=write_json(out/'actual_terminal.json',dict(status='completed',exit_code=0,completed_projection_rows=len(projection),completed_factor_audit_rows=len(audit),native_source_queries=sql,actual_model_fit_calls=0,new_cash_accounts=0,new_labels=0,downloads=0,whole_database_hashes=0,fixture=False,elapsed_seconds=time.monotonic()-started))
        artifacts={str(p.relative_to(out)):file_binding(p) for p in sorted(out.rglob('*')) if p.is_file()}
        manifest=dict(schema='stage122_long_history_projection_v1',status='completed',mode='actual',protocol=file_binding(PROTOCOL),protocol_sha256=PROTOCOL_SHA,source_bundle=bundle,authorization=authorization,input_bindings=inputs,mother_rows=399252,products=98,families=95,exchanges=6,mother_dates=4074,projection=p,daily_factor_audit=a,source_read_receipt=file_binding(out/'source_read_receipt.json'),terminal=file_binding(out/'actual_terminal.json'),artifacts=artifacts,native_source_queries=sql,actual_model_fit_calls=0,new_cash_accounts=0,new_labels=0,downloads=0,whole_database_hashes=0,goal_complete=False,production_qualified=False)
        write_json(out/'manifest.json',manifest);return manifest
    except BaseException as error:
        write_json(out/'actual_terminal.json',dict(status='failed',exit_code=1,native_source_queries=kernel.ref.NATIVE_QUERIES,actual_model_fit_calls=0,new_cash_accounts=0,new_labels=0,error_type=type(error).__name__,error=str(error),automatic_retry=False,elapsed_seconds=time.monotonic()-started));raise

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('output','protocol-sha256','authorization','authorization-sha256'):parser.add_argument('--'+key,required=True)
    args=parser.parse_args(argv);out,protocol,auth,binding=authorize(args);result=run_actual(out,protocol,auth,binding)
    print(json.dumps(dict(status=result['status'],output=str(out),projection_rows=result['mother_rows'])),flush=True)
if __name__=='__main__':main()
