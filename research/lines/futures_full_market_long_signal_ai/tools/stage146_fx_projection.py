"""Stage145 frozen ECB adjacent-row projection. No native SQL, fit, or cash.

The archive is a historical reconstruction, not first-release vintage evidence.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib,json,os,time
from pathlib import Path
import numpy as np
import pandas as pd
TOOLS=Path(__file__).resolve().parent;LINE=TOOLS.parent
PROTOCOL=LINE/'outputs/stage145_fx_information_protocol/protocol.json'
PROTOCOL_SHA='be0431bff87dc90d91a9f1b16940c9a6d8112a66d4309879abef46466ce4f270'
IDENTITY=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
INPUT_ROLES={'values','content_receipt','mothers'}

def file_binding(path):
 path=Path(path).resolve();digest=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1<<20),b''):digest.update(chunk)
 return dict(path=str(path),bytes=path.stat().st_size,sha256=digest.hexdigest())
def same_binding(a,b):return all(a.get(k)==b.get(k) for k in ['path','bytes','sha256'])
def read_bound(binding):
 raw=Path(binding['path']).read_bytes()
 if len(raw)!=binding['bytes'] or hashlib.sha256(raw).hexdigest()!=binding['sha256']:raise ValueError('bound input changed '+binding['path'])
 return raw
def write_json(path,value):
 with Path(path).open('x') as f:
  json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def write_csv(path,frame):
 if Path(path).exists():raise FileExistsError(str(path))
 frame.to_csv(path,index=False,compression={'method':'gzip','mtime':0},float_format='%.17g');return file_binding(path)
def source_bundle():return sorted([file_binding(TOOLS/n) for n in ['stage146_fx_projection.py','test_stage146_fx_projection.py']],key=lambda x:x['path'])

def project_dates(values,u_dates):
 """Adjacent source positions are selected before inspecting any currency values."""
 required={'date','USD_per_EUR','CNY_per_EUR'}
 if not required.issubset(values):raise ValueError('source columns missing')
 source=values.copy();source['date']=pd.to_datetime(source.date,format='%Y-%m-%d',errors='raise').dt.strftime('%Y-%m-%d')
 if source.empty or source.date.duplicated().any():raise ValueError('empty/duplicate source dates')
 source=source.sort_values('date',kind='stable').reset_index(drop=True)
 dates=source.date.to_numpy();legs=source[['USD_per_EUR','CNY_per_EUR']].apply(pd.to_numeric,errors='coerce').to_numpy(float)
 result=[]
 for u in sorted(set(map(str,u_dates))):
  day=pd.Timestamp(u)
  if day.strftime('%Y-%m-%d')!=u:raise ValueError('noncanonical domestic date')
  ni=int(np.searchsorted(dates,u,side='left'))-1
  row=dict(u_date=u,q=np.nan,fx_missing=1,projection_state='missing_adjacent_source',assigned_time='',decision_time=(day.tz_localize('Asia/Shanghai')+pd.Timedelta(hours=15)).isoformat())
  for key,index in [('n',ni),('d',ni-1),('w',ni-2)]:
   exists=index>=0
   row[key+'_date']=str(dates[index]) if exists else ''
   row[key+'_source_row_index']=index if exists else -1
   row[key+'_age_days']=int((day-pd.Timestamp(dates[index])).days) if exists else -1
   row[key+'_USD_per_EUR']=float(legs[index,0]) if exists else np.nan
   row[key+'_CNY_per_EUR']=float(legs[index,1]) if exists else np.nan
  row['change_date']=row['d_date'];row['finalization_date']=row['n_date']
  if ni>=0:
   assigned=pd.Timestamp(dates[ni]).tz_localize('Asia/Shanghai')+pd.Timedelta(days=1,hours=8)
   row['assigned_time']=assigned.isoformat()
   if assigned>pd.Timestamp(row['decision_time']):raise ValueError('FX assigned after decision')
  if ni>=2:
   batch=legs[ni-2:ni+1]
   if np.isfinite(batch).all() and (batch>0).all():
    sd=legs[ni-1,1]/legs[ni-1,0];sw=legs[ni-2,1]/legs[ni-2,0]
    q=float(np.log(sd/sw))
    if not np.isfinite(q):raise ValueError('nonfinite FX change')
    row.update(q=q,fx_missing=0,projection_state='observed_conservative_archive_reconstruction')
   else:row['projection_state']='missing_adjacent_currency_leg'
  result.append(row)
 return pd.DataFrame(result)

def project_mothers(values,mothers):
 if mothers.event_id.duplicated().any():raise ValueError('duplicate mother identity')
 dates=project_dates(values,mothers.u_date)
 out=mothers.merge(dates,on='u_date',how='left',validate='many_to_one',sort=False)
 if len(out)!=len(mothers) or not np.array_equal(out.event_id,mothers.event_id) or out.fx_missing.isna().any():raise ValueError('projection shrank mother population')
 return out

def authorize(args):
 output=Path(args.output).resolve();root=LINE/'outputs/stage146_fx_projection'
 if output.exists() or root not in output.parents:raise ValueError('fresh Stage146 output required')
 if args.protocol_sha256!=PROTOCOL_SHA or file_binding(args.protocol)['sha256']!=PROTOCOL_SHA:raise ValueError('frozen145 mismatch')
 binding=file_binding(args.authorization)
 if binding['sha256']!=args.authorization_sha256:raise ValueError('authorization hash mismatch')
 auth=json.loads(read_bound(binding));required=dict(schema='stage145_exact_root_authorization_v1',authorized_by='root',stage='projection',exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(output))
 if any(auth.get(k)!=v for k,v in required.items()) or auth.get('source_bundle')!=source_bundle() or set(auth.get('input_bindings',{}))!=INPUT_ROLES:raise ValueError('exact root projection authorization mismatch')
 protocol=json.loads(read_bound(file_binding(PROTOCOL)))
 for role,expected in [('values',protocol['source']['values']),('content_receipt',protocol['source']['content_receipt']),('mothers',protocol['input_roles']['mothers'])]:
  if not same_binding(auth['input_bindings'][role],expected):raise ValueError('frozen projection role mismatch '+role)
 return output,auth,binding

def run_actual(output,auth,binding):
 output.mkdir(parents=True,exist_ok=False);started=time.monotonic();bundle=source_bundle()
 write_json(output/'actual_started.json',dict(status='started',stage='projection',started_at=datetime.now(timezone.utc).isoformat(),authorization=binding,source_bundle=bundle,protocol=file_binding(PROTOCOL)))
 try:
  inputs=auth['input_bindings'];receipt=json.loads(read_bound(inputs['content_receipt']))
  if not same_binding(receipt.get('normalized',{}),inputs['values']) or receipt.get('rows')!=7116:raise ValueError('accepted144 source receipt mismatch')
  values=pd.read_csv(__import__('io').BytesIO(read_bound(inputs['values'])),dtype={'date':str},float_precision='round_trip')
  if len(values)!=7116:raise ValueError('incomplete original ECB calendar')
  if not same_binding(file_binding(inputs['mothers']['path']),inputs['mothers']):raise ValueError('mother binding changed')
  mothers=pd.read_csv(inputs['mothers']['path'],usecols=IDENTITY,dtype=str,keep_default_na=False)
  mothers.sequence_index=pd.to_numeric(mothers.sequence_index);mothers.u_index=pd.to_numeric(mothers.u_index)
  if len(mothers)!=399252 or not np.array_equal(mothers.sequence_index,np.arange(len(mothers))):raise ValueError('full399252 mother identity required')
  projection=project_mothers(values,mothers);dates=projection.drop_duplicates('u_date').drop(columns=[c for c in IDENTITY if c!='u_date']).reset_index(drop=True)
  artifacts=dict(projection=write_csv(output/'projection.csv.gz',projection),source_dates=write_csv(output/'source_dates.csv.gz',dates))
  summary=dict(status='completed',mother_rows=len(projection),domestic_dates=len(dates),observed_mothers=int(projection.fx_missing.eq(0).sum()),missing_mothers=int(projection.fx_missing.sum()),distinct_release_cohorts=int(dates.loc[dates.fx_missing.eq(0),'n_date'].nunique()),repeated_domestic_asof_states=int(dates.loc[dates.fx_missing.eq(0),'n_date'].duplicated().sum()),strict_pit_accepted=False,production_qualified=False,goal_complete=False)
  write_json(output/'summary.json',summary)
  if bundle!=source_bundle():raise ValueError('source changed during projection')
  write_json(output/'actual_terminal.json',dict(status='completed',exit_code=0,actual_fit_calls_attempted=0,actual_fit_calls_completed=0,cash_replays=0,native_source_queries=0,downloads=0,automatic_retry=False,elapsed_seconds=time.monotonic()-started))
  manifest=dict(schema='stage146_fx_projection_v1',status='completed',mode='actual',source_bundle=bundle,protocol=file_binding(PROTOCOL),protocol_sha256=PROTOCOL_SHA,authorization=binding,input_bindings=inputs,mother_rows=len(projection),summary=file_binding(output/'summary.json'),terminal=file_binding(output/'actual_terminal.json'),**artifacts)
  manifest['artifacts']={str(p.relative_to(output)):file_binding(p) for p in sorted(output.rglob('*')) if p.is_file()};write_json(output/'manifest.json',manifest);return manifest
 except BaseException as error:
  if not (output/'actual_terminal.json').exists():write_json(output/'actual_terminal.json',dict(status='failed',exit_code=1,error_type=type(error).__name__,error=str(error),actual_fit_calls_attempted=0,actual_fit_calls_completed=0,cash_replays=0,native_source_queries=0,automatic_retry=False,elapsed_seconds=time.monotonic()-started))
  raise

def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['protocol','protocol-sha256','authorization','authorization-sha256','output']:p.add_argument('--'+name,required=True)
 args=p.parse_args(argv);output,auth,binding=authorize(args);manifest=run_actual(output,auth,binding);print(json.dumps(dict(status=manifest['status'],output=str(output))),flush=True)
if __name__=='__main__':main()
