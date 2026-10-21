"""Evidence-only minute adapter; base source data/policy and logical anchor frozen."""
import argparse
from copy import deepcopy
from datetime import datetime
import hashlib,json,math,pickle,shutil
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import stage042_coldstart_coverage as source

LINE=Path(__file__).resolve().parents[1];ROOT=LINE.parents[2]
OUT=LINE/'outputs/stage058_minute_augmented_source'
BASE=LINE/'outputs/stage046b_final'
_INDEX=None;_USAGE=set()
_BASE_CASE=source.ProductCases;_BASE_PRODUCT_RUN=source.product_run
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def validate_review_gate(path,manifest_sha):
    receipt=json.loads(Path(path).read_text())
    if receipt.get('accepts_stage056_inputs') is not True or receipt.get('qualified_inputs_manifest_sha256')!=manifest_sha:
        raise ValueError('Stage057_exact_manifest_acceptance_required')
    if any(receipt.get('unresolved_'+level)!=0 for level in ['P0','P1','P2']):
        raise ValueError('Stage057_has_unresolved_input_blocker')
    return receipt

class MinuteEvidenceIndex:
    def __init__(self,manifest_path):
        self.manifest_path=Path(manifest_path).resolve();self.manifest_sha256=sha(self.manifest_path)
        self.events={};self.snapshots={};self.source_members=set()
        manifest=json.loads(self.manifest_path.read_text())
        if not isinstance(manifest,list) or not manifest:raise ValueError('empty_or_invalid_manifest')
        for item in manifest:
            if item.get('physical_session_verified') is not False or item.get('usable_for_trading') is not False or item.get('reference_policy_grid_only') is not True:
                raise ValueError('conditional_reference_scope_required')
            bindings=item.get('bindings');ids=item.get('source_ids')
            if not bindings or not ids or set(ids)!={b['source_id'] for b in bindings}:raise ValueError('source_membership_not_preserved')
            keys={(b['contract_epoch_id'],b['source_trade_date']) for b in bindings}
            if len(keys)!=1:raise ValueError('manifest_exact_identity_conflict')
            key=next(iter(keys))
            if item['requirement_id']!=hashlib.sha256(('|'.join(key)).encode()).hexdigest()[:20]:raise ValueError('requirement_exact_key_mismatch')
            path=Path(item['data_path']).resolve();before=path.stat()
            if sha(path)!=item['data_csv_sha256']:raise ValueError('qualified_snapshot_sha_mismatch')
            frame=pd.read_csv(path,float_precision='round_trip')
            if list(frame.columns)!=['bar_datetime','open','high','low','close']:raise ValueError('qualified_snapshot_schema_mismatch')
            rows=[]
            for r in frame.to_dict('records'):
                values=[r[k] for k in ['open','high','low','close']]
                if any(isinstance(v,(bool,np.bool_)) or not math.isfinite(float(v)) or float(v)<=0 for v in values):raise ValueError('invalid_snapshot_OHLC')
                if r['low']>min(r['open'],r['close']) or r['high']<max(r['open'],r['close']):raise ValueError('invalid_snapshot_OHLC_geometry')
                rows.append(dict(bar_datetime=str(r['bar_datetime']),**{k:float(r[k]) for k in ['open','high','low','close']}))
            if len(rows)!=item['rows'] or not rows:raise ValueError('snapshot_rows_mismatch')
            dates=[r['bar_datetime'] for r in rows]
            if dates!=sorted(set(dates)):raise ValueError('snapshot_time_not_strict')
            digest=hashlib.sha256(canonical(rows)).hexdigest()
            if digest!=item['canonical_input_sha256']:raise ValueError('canonical_snapshot_hash_mismatch')
            grid_hash=hashlib.sha256('\n'.join(dates).encode()).hexdigest()
            aggregate=dict(open=rows[0]['open'],high=max(r['high'] for r in rows),low=min(r['low'] for r in rows),close=rows[-1]['close'])
            for b in bindings:
                if b.get('physical_session_verified') is not False or b.get('broker_symbol_qualified') is not False:raise ValueError('physical_qualification_not_allowed')
                if b['expected_grid_sha256']!=grid_hash or b['expected_minutes']!=len(rows):raise ValueError('reviewed_grid_binding_mismatch')
                if any(not math.isclose(aggregate[k],float(b['source_daily_OHLC'][k]),rel_tol=0,abs_tol=1e-8) for k in aggregate) or not math.isclose(aggregate['open'],float(b['entry_open']),rel_tol=0,abs_tol=1e-8):raise ValueError('reviewed_price_binding_mismatch')
            after=path.stat()
            if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):raise ValueError('snapshot_changed_during_read')
            self.snapshots[str(path)]=dict(path=str(path),sha256=item['data_csv_sha256'],bytes=before.st_size,mtime_ns=before.st_mtime_ns,inode=before.st_ino)
            group=self.events.setdefault(key,{})
            if digest not in group:group[digest]=dict(path=rows,aggregate=aggregate,snapshots=[],bindings=[],source_ids=set())
            group[digest]['snapshots'].append(dict(path=str(path),sha256=item['data_csv_sha256']))
            group[digest]['bindings'].extend(deepcopy(bindings));group[digest]['source_ids'].update(ids);self.source_members.update(ids)
        for group in self.events.values():
            if len(group)>256:raise ValueError('minute_path_budget_exceeded_no_truncation')

    def attach(self,base,epoch,day):
        group=self.events.get((epoch,day))
        if base is None or not group:return base
        if base.get('minute_paths') is not None or base.get('minute_evidence_id') is not None:raise ValueError('base_already_has_minutes_do_not_replace')
        original=pickle.dumps(base,protocol=5);out=deepcopy(base);paths=[];receipts=[];ids=set()
        for digest,item in sorted(group.items()):
            if any(not math.isclose(float(base['bar'][k]),item['aggregate'][k],rel_tol=0,abs_tol=1e-8) for k in ['open','high','low','close']):raise ValueError('current_source_daily_OHLC_mismatch')
            anchor=base.get('anchor')
            if anchor and not math.isclose(float(anchor['price']),item['aggregate']['open'],rel_tol=0,abs_tol=1e-8):raise ValueError('current_source_open_mismatch')
            paths.append(deepcopy(item['path']));ids.update(item['source_ids'])
            receipts.append(dict(canonical_input_sha256=digest,snapshots=deepcopy(item['snapshots']),source_ids=sorted(item['source_ids'])))
        receipt=dict(contract_epoch_id=epoch,source_trade_date=day,manifest_path=str(self.manifest_path),manifest_sha256=self.manifest_sha256,
                     distinct_inputs=receipts,source_ids=sorted(ids),physical_session_verified=False,reference_policy_grid_only=True,usable_for_trading=False,
                     base_daily_anchor_policy='unchanged logical T00; no physical timestamp promotion')
        out.update(minute_paths=paths,minute_evidence_id='stage058-reference-input:'+hashlib.sha256(canonical(receipt)).hexdigest(),minute_input_receipt=receipt)
        assert original==pickle.dumps(base,protocol=5)
        return out

class AugmentedProductCases(_BASE_CASE):
    def __init__(self,key):super().__init__(key);self.augmented_cache={}
    def record(self,epoch,day,index):
        key=(epoch,day)
        if key in self.augmented_cache:return self.augmented_cache[key]
        base=super().record(epoch,day,index);result=_INDEX.attach(base,epoch,day)
        if result is not base:_USAGE.add(key)
        self.augmented_cache[key]=result;return result

def augmented_product_run(key):
    global _USAGE
    _USAGE=set();receipt=_BASE_PRODUCT_RUN(key)
    receipt.update(minute_adapter_injected_epoch_days=[list(k) for k in sorted(_USAGE)],minute_adapter_injected_unique_events=len(_USAGE),
                   minute_adapter_distinct_paths=sum(len(_INDEX.events[k]) for k in _USAGE))
    return receipt

def compare_original_known(new_path):
    old=pd.read_csv(BASE/'monthly_coldstart_coverage.csv',float_precision='round_trip')
    new=pd.read_csv(new_path,float_precision='round_trip')
    identity=['exchange','product','product_vt_symbol','eval_date','row_role','asof_eligible','asof_status','reference_epoch','target_day','observed_through','maturity_clock_reached','conditional_economics','training_eligible','net_60d_training_label']
    assert len(new)==19698 and len(old)==19698
    pd.testing.assert_frame_equal(old[identity],new[identity],check_exact=True)
    known=old.status.eq('conditional_value_known')&old.maturity_clock_reached&old.cumulative_net_r.notna()&old.all_paths_value_known
    if int(known.sum())!=4508:raise ValueError('frozen_old_known_count_changed')
    for col in ['cumulative_net_r','cumulative_gross_r','net_r_min','net_r_max']:
        a=old.loc[known,col].to_numpy(dtype='float64').view('uint64');b=new.loc[known,col].to_numpy(dtype='float64').view('uint64')
        if not np.array_equal(a,b):raise ValueError('P1_old_known_float_bits_changed:'+col)
    for col in ['status','path_count','known_paths','all_paths_value_known','episodes']:
        if not old.loc[known,col].equals(new.loc[known,col]):raise ValueError('P1_old_known_state_changed:'+col)
    newpoint=new.asof_eligible&new.maturity_clock_reached&new.all_paths_value_known&new.cumulative_net_r.notna()
    first_changed=(old.first_unknown_day.fillna('')!=new.first_unknown_day.fillna(''))|(old.first_unknown_reason.fillna('')!=new.first_unknown_reason.fillna(''))
    return old,new,dict(original_known_count=4508,original_known_bits_unchanged=True,asof_clock_role_identity_unchanged=True,
                       mature_point_known=int(newpoint.sum()),newly_mature_point_known=int((newpoint&~known).sum()),
                       original_unknown_first_blocker_changed=int((old.asof_eligible&~known&first_changed).sum()),
                       all_19698_rows_preserved=True)

def run(manifest_path,review_receipt,workers=4):
    global _INDEX,_USAGE
    if OUT.exists():raise ValueError('immutable_output_exists')
    manifest_path=Path(manifest_path).resolve();review_receipt=Path(review_receipt).resolve()
    validate_review_gate(review_receipt,sha(manifest_path))
    _INDEX=MinuteEvidenceIndex(manifest_path);started=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    locked={str(p):sha(p) for p in [Path(__file__),Path(__file__).with_name('test_stage058_minute_evidence_adapter.py'),manifest_path,review_receipt,manifest_path.parent/'summary.json',LINE/'tools/stage055_minute_input_qualification.py',LINE/'tools/stage056_uniform_minute_input_audit.py',BASE/'monthly_coldstart_coverage.csv']}
    snapshots=deepcopy(_INDEX.snapshots);source.ProductCases=AugmentedProductCases;source.product_run=augmented_product_run
    try:source.run(workers,output_path=OUT)
    finally:source.ProductCases=_BASE_CASE;source.product_run=_BASE_PRODUCT_RUN
    try:old,new,comparison=compare_original_known(OUT/'monthly_coldstart_coverage.csv')
    except Exception as exc:
        (OUT/'P1_BLOCKING_comparison_failure.json').write_text(json.dumps(dict(error=repr(exc),no_acceptance=True))+'\n');raise
    for path,digest in locked.items():
        if sha(path)!=digest:raise ValueError('adapter_or_evidence_changed_during_run:'+path)
    for path,stamp in snapshots.items():
        p=Path(path);stat=p.stat()
        if sha(path)!=stamp['sha256'] or (stat.st_size,stat.st_mtime_ns,stat.st_ino)!=(stamp['bytes'],stamp['mtime_ns'],stamp['inode']):raise ValueError('minute_snapshot_changed_during_run')
    (OUT/'minute_input_snapshots').mkdir()
    for path,stamp in snapshots.items():
        dest=OUT/'minute_input_snapshots'/(stamp['sha256']+'.csv')
        if not dest.exists():shutil.copyfile(path,dest)
        if sha(dest)!=stamp['sha256']:raise ValueError('copied_snapshot_sha_mismatch')
    binding=json.loads((OUT/'bindings.json').read_text());injected={tuple(k) for r in binding['checkpoints'] for k in r['minute_adapter_injected_epoch_days']}
    changed=old.add_prefix('old_').join(new.add_prefix('new_'))
    mask=(old.status!=new.status)|(old.first_unknown_day.fillna('')!=new.first_unknown_day.fillna(''))|(old.first_unknown_reason.fillna('')!=new.first_unknown_reason.fillna(''))|(old.path_count!=new.path_count)
    changed.loc[mask].to_csv(OUT/'old_unknown_source_changes.csv',index=False)
    receipt=dict(started_at=started,completed_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),**comparison,
                 evidence_events_available=len(_INDEX.events),evidence_distinct_inputs=sum(len(g) for g in _INDEX.events.values()),
                 evidence_source_ids=len(_INDEX.source_members),evidence_source_members=sum(len(item['source_ids']) for group in _INDEX.events.values() for item in group.values()),injected_unique_record_events=len(injected),
                 injected_record_paths=sum(len(_INDEX.events[k]) for k in injected),injected_event_keys=[list(k) for k in sorted(injected)],
                 minute_csv_snapshots=snapshots,locked_input_and_adapter_sha256=locked,
                 evidence_scope='Stage057-accepted reference-policy grid inputs only; physical/broker/PIT qualification unchangedFalse',
                 source_scope='same frozen source, only minute_paths/evidence_id/receipt attached; logical T00 anchors unchanged',
                 model_fits=0,production_changes=0,orders=0,downloads=0,independent_source_review_pending=True,
                 new_coverage_sha256=sha(OUT/'monthly_coldstart_coverage.csv'),old_coverage_sha256=sha(BASE/'monthly_coldstart_coverage.csv'))
    (OUT/'minute_adapter_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['minute_csv_snapshots','locked_input_and_adapter_sha256','injected_event_keys']},ensure_ascii=False),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',type=Path,required=True);parser.add_argument('--review-receipt',type=Path,required=True);parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args();run(args.manifest,args.review_receipt,args.workers)
