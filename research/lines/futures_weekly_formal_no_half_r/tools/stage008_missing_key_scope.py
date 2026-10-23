"""Data-only additions to missing minute keys; never overwrite a legacy observation.

The caller first freezes and strictly reconciles legacy layers. New layers are
strictly reconciled with each other before their entire legacy-key intersection
(equal observations included) is excluded. No result, price or volume ranking is
used. Consumption of any excluded conflicting key subsequently rejects the run.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
from stage005_merge import merge_verified_layers

KEYS=['vt_symbol','bar_datetime']


def _local_stamp(value):
    stamp=pd.Timestamp(value)
    if pd.isna(stamp):raise ValueError('missing_scope_timestamp')
    return stamp.tz_convert('Asia/Shanghai').tz_localize(None) if stamp.tzinfo else stamp


def _key(symbol,stamp):return str(symbol),_local_stamp(stamp)


def _scalar(value):
    value=value.item() if isinstance(value,np.generic) else value
    if isinstance(value,float) and not math.isfinite(value):return None
    return value


class RequestedKeyOverlapConflict(ValueError):
    def __init__(self,report):
        super().__init__('requested_key_overlap_conflict')
        self.scope_report=report


def merge_missing_key_scope(legacy,new_patches,values,requested_keys):
    """Return (merged, full scope report), or reject a declared-request conflict.

    `legacy` is the caller's strictly reconciled old layer. The same immutable
    stage005 strict merge validates each new patch and all new-new overlaps.
    All matching legacy keys are excluded regardless of value equality. Old/new
    comparisons use exactly its absolute 1e-8 tolerance, with NaN unequal.
    """
    values=list(values);patches=list(new_patches)
    def normalized(frame):
        result=frame.copy(deep=True)
        result['bar_datetime']=result.bar_datetime.map(_local_stamp)
        return result
    old=merge_verified_layers(normalized(legacy),[],values)
    new=merge_verified_layers(old.iloc[:0].copy(),[normalized(p) for p in patches],values)
    requested={_key(symbol,stamp) for symbol,stamp in requested_keys}
    old_rows={_key(r['vt_symbol'],r['bar_datetime']):r for r in old.to_dict('records')}
    excluded=[];additions=[];added_keys=[]
    for row in new.to_dict('records'):
        key=_key(row['vt_symbol'],row['bar_datetime'])
        identity=dict(vt_symbol=key[0],bar_datetime=key[1].isoformat(),requested_key=key in requested)
        if key not in old_rows:
            additions.append(row);added_keys.append(identity);continue
        prior=old_rows[key]
        differences={name:dict(old=_scalar(prior[name]),new=_scalar(row[name])) for name in values
            if not np.isclose(float(prior[name]),float(row[name]),rtol=0,atol=1e-8,equal_nan=False)}
        excluded.append(dict(**identity,old={name:_scalar(prior[name]) for name in values},
            new={name:_scalar(row[name]) for name in values},conflicting_fields=differences))
    conflicts=[item for item in excluded if item['conflicting_fields']]
    requested_conflicts=[item for item in conflicts if item['requested_key']]
    report=dict(schema='stage008_missing_key_scope_v1',status='REJECT_REQUESTED_KEY_CONFLICT' if requested_conflicts else 'PASS_MISSING_KEYS_ONLY',
        policy='strict new-new; exclude every legacy existing key including equal values; add only absent keys; never overwrite legacy',
        legacy_count=len(old),new_layer_count=len(patches),new_input_rows=sum(len(p) for p in patches),new_unique_count=len(new),
        requested_key_count=len(requested),excluded_existing_count=len(excluded),conflicting_existing_count=len(conflicts),
        requested_conflicting_count=len(requested_conflicts),added_count=len(additions),
        excluded_existing_keys=excluded,conflicting_existing_keys=conflicts,added_keys=added_keys,
        old_value_overrides=0,financial_replays=0)
    if requested_conflicts:raise RequestedKeyOverlapConflict(report)
    additional=pd.DataFrame(additions,columns=new.columns)
    merged=merge_verified_layers(old,[additional] if len(additional) else [],values)
    return merged,report


def audit_scope_consumption(trades,anchor_requests,scope_report):
    """Fail closed when an actual fill or actual/requested anchor uses a conflict.

    Check actual trades plus every captured request, not the precomputed signal
    plan. Both expected_start and actual_time are independently inspected.
    Naive stamps are Shanghai local; aware stamps normalize to Shanghai local.
    """
    if scope_report.get('schema')!='stage008_missing_key_scope_v1':
        raise ValueError('unsupported_missing_key_scope_schema')
    conflicts={_key(item['vt_symbol'],item['bar_datetime']):item
        for item in scope_report['conflicting_existing_keys']}
    hits=[];checked=0
    for origin,records,fields in [('trade',trades,['execution_datetime']),('anchor_request',anchor_requests,['actual_time','expected_start'])]:
        records=records.to_dict('records') if isinstance(records,pd.DataFrame) else records
        for index,record in enumerate(records):
            for field in fields:
                checked+=1
                try:key=_key(record['vt_symbol'],record[field])
                except (KeyError,ValueError,TypeError,OverflowError):
                    hits.append(dict(origin=origin,index=index,field=field,vt_symbol=str(record.get('vt_symbol','')),
                        reason='invalid_actual_consumption_key'));continue
                if key in conflicts:
                    hits.append(dict(origin=origin,index=index,field=field,vt_symbol=key[0],bar_datetime=key[1].isoformat(),
                        trade_id=str(record.get('trade_id','')),reason='excluded_conflicting_key_consumed',
                        conflicting_fields=conflicts[key]['conflicting_fields']))
    accepted=not hits
    return dict(schema='stage008_scope_consumption_acceptance_v1',accepted=accepted,
        verdict='PASS_NO_CONFLICTED_ANCHOR_CONSUMED' if accepted else 'REJECT_EXECUTION_ANCHOR_MISMATCH',
        checked_key_count=checked,conflicting_scope_key_count=len(conflicts),hit_count=len(hits),hits=hits,
        qualification_note='This audit only checks excluded conflicting observations; positive minute volume and independent review remain required.')
