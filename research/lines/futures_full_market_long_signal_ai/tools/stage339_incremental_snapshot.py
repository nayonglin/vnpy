"""Pure incremental snapshot adapter; no loader, receiver, cash or T0 creation.

Caller supplies the accepted331 compact checkpoint/inventory, confirmed source
calendar and a separately accepted canonical overlay.336 raw success alone is
never an accepted input. Reuse caller325's injected320 core for class identity.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import date
import math
import re
from types import SimpleNamespace

import numpy as np

SCHEMA='stage339_incremental_snapshot_v1'
BAR_NAMES=('open','high','low','close','volume')
DATE_STATES={'operational_midnight_label','session_mapped'}


class SnapshotMarket:
    """Exact index only; an old saved state never becomes a current quote."""
    def __init__(self,series,dates):self.series=series;self.dates=list(dates)

    def bar(self,epoch,k):
        s=self.series.get(epoch)
        if s is None:return None
        j=int(np.searchsorted(s.days,k))
        if j>=len(s.days) or s.days[j]!=k or not s.valid[j]:return None
        return {key:float(v) for key,v in zip(BAR_NAMES,s.values[j])}

    def indicator(self,epoch,k):
        s=self.series.get(epoch);j=int(np.searchsorted(s.days,k)) if s is not None else -1
        if j<0 or j>=len(s.days) or s.days[j]!=k or not s.valid[j]:
            return dict(N=math.nan,low20=math.nan,run_length=0,high55_before=math.nan)
        return dict(N=float(s.N[j]),low20=float(s.low20[j]),run_length=int(s.run[j]),high55_before=math.nan)


def _epoch_product(epoch):
    if not isinstance(epoch,str) or not re.fullmatch(r'[^.]+\.[^.]+\.\d{6}',epoch):
        raise ValueError('explicit true YYYYMM epoch required')
    product,month=epoch.rsplit('.',1)
    date(int(month[:4]),int(month[4:]),1)
    return product


def _empty_series(core):return core.WilderState().to_series()


def _row_reasons(row):
    reasons=[]
    for key,wanted in (('identity_state','known_explicit'),('units_status','canonical_normalized'),
                       ('canonical_quality_status','accepted')):
        if row.get(key)!=wanted:reasons.append(key)
    if row.get('date_mapping_state') not in DATE_STATES:reasons.append('date_mapping_state')
    if row.get('model_input_eligible') is not True:reasons.append('model_input_eligible')
    if not row.get('source_receipt'):reasons.append('source_receipt')
    return reasons


def build_incremental_snapshot(warmup_states,epoch_inventory,normalized_rows,*,dates,
        previous_u_date,u_date,products,economics,calendar_confirmation,
        normalization_receipt,source_receipt,D_context=None,clock=None,core):
    """Advance only new explicitly accepted rows and return330-compatible input.

    warmup_states maps epoch->331 final_state (or this adapter's returned JSON
    state). Inventory contains every old epoch, even without a prior-u bar.
    Rows before/equal the checkpoint date, future rows and unknown rows are
    audited but never appended. New epochs start at their first accepted new
    day, never from the receiver's35-bar historical overlap. No files are read.
    """
    if (normalization_receipt.get('status')!='completed'
            or normalization_receipt.get('canonical_rows_accepted') is not True):
        raise ValueError('explicit accepted canonical overlay receipt required;336 raw is not accepted')
    dates=list(dates)
    if not dates or dates!=sorted(set(dates)):
        raise ValueError('unique append-only source calendar required')
    for value in dates:
        if date.fromisoformat(value).isoformat()!=value:raise ValueError('canonical date required')
    if previous_u_date not in dates or u_date not in dates or u_date<=previous_u_date:
        raise ValueError('new u must follow checkpoint in the stable source calendar')
    previous=dates.index(previous_u_date);u=dates.index(u_date)
    if (calendar_confirmation.get('confirmed') is not True
            or calendar_confirmation.get('u_date')!=u_date
            or calendar_confirmation.get('u_index')!=u
            or not calendar_confirmation.get('proof')):
        raise ValueError('explicit new-u source-calendar date/index confirmation required')
    dc=deepcopy(D_context) if D_context is not None else dict(confirmed=False,D_index=None,D_date=None,proof='D_not_confirmed')
    core._calendar(dates,u,dc)  # Existing320's exact next-source-index contract.
    products=sorted(products)
    if (len(products)!=98 or len(set(products))!=98
            or len({p.removesuffix('_F') for p in products})!=95):
        raise ValueError('complete accepted98/95 mother domain required, including unavailable products')
    inventory={}
    for original in epoch_inventory:
        r=deepcopy(original);epoch=r['epoch'];product=_epoch_product(epoch)
        if epoch in inventory or r.get('product_id')!=product:raise ValueError('inventory identity duplicate/mismatch')
        last=r.get('last_index')
        if last is not None:
            if isinstance(last,bool) or not isinstance(last,int) or not 0<=last<=previous:
                raise ValueError('inventory last source index exceeds checkpoint')
            if r.get('last_date')!=dates[last]:raise ValueError('inventory last date/index mismatch')
        if r.get('has_current_bar') is not (last==previous):
            raise ValueError('inventory prior-u current flag mismatch')
        inventory[epoch]=r
    states={}
    for epoch,value in warmup_states.items():
        if epoch not in inventory:raise ValueError('saved state absent from complete inventory')
        state=core.WilderState.from_dict(value)
        if state.last_seen!=inventory[epoch]['last_index']:
            raise ValueError('saved state/inventory last index mismatch')
        states[epoch]=state
    for epoch,r in inventory.items():
        if r['has_current_bar'] and epoch not in states:
            raise ValueError('prior-u epoch missing its accepted compact final state')

    dispositions=[];accepted={};unsupported=[]
    for index,raw in enumerate(normalized_rows):
        r=deepcopy(raw);epoch=r.get('contract_epoch_id');day=r.get('trade_date')
        audit=dict(row_index=index,contract_epoch_id=epoch,trade_date=day,
            source_receipt=deepcopy(r.get('source_receipt')),reasons=_row_reasons(r),status='not_consumed')
        if not audit['reasons']:
            try:product=_epoch_product(epoch)
            except (TypeError,ValueError):audit['reasons'].append('contract_epoch_id')
            if not isinstance(day,str) or day not in dates:audit['reasons'].append('trade_date_not_confirmed')
        if not audit['reasons']:
            if day<=previous_u_date:audit['reasons'].append('outside_incremental_window')
            elif day>u_date:audit['reasons'].append('future_row_not_consumed')
            elif product not in products:
                audit['reasons'].append('unsupported_product');unsupported.append(dict(product_id=product,
                    reference_epoch=epoch,u_date=day,status='unsupported_product',source_receipt=r['source_receipt']))
            else:
                values=r.get('canonical_values')
                if not isinstance(values,dict) or any(k not in values for k in (*BAR_NAMES,'close_oi')):
                    audit['reasons'].append('canonical_values_missing')
                else:
                    # This is a check, never a unit conversion or missing->zero.
                    bar=dict({k:values[k] for k in (*BAR_NAMES,'close_oi')},quality_status=r['canonical_quality_status'])
                    if core._helpers().mother.candidate(bar):audit['reasons'].append('canonical_values_invalid')
                    oi=bar['close_oi']
                    if oi is not None and (not isinstance(oi,(int,float)) or not math.isfinite(oi) or oi<0):
                        audit['reasons'].append('canonical_close_oi_invalid')
        if not audit['reasons']:
            key=(epoch,day)
            if key in accepted:raise ValueError('duplicate accepted epoch/date;no implicit last-write-wins')
            accepted[key]=(dict(bar,quality_status='accepted'),audit)
            audit['status']='accepted_new_bar'
        dispositions.append(audit)

    groups={}
    for (epoch,day),record in sorted(accepted.items(),key=lambda v:(v[0][0],v[0][1])):
        groups.setdefault(epoch,[]).append((dates.index(day),day,*record))
    continuation=[]
    for epoch,records in groups.items():
        prior=inventory.get(epoch);state=states.get(epoch)
        kind='continued_exact_prior_u' if prior and prior['has_current_bar'] else 'known_epoch_prior_gap' if prior else 'new_epoch_first_accepted_day'
        if kind!='continued_exact_prior_u':state=core.WilderState()
        before=state.to_dict();bars=[]
        for k,day,bar,audit in records:
            state.append(k,bar)
            bars.append(dict(u_index=k,trade_date=day,bar=deepcopy(bar),source_receipt=audit['source_receipt']))
        states[epoch]=state
        if prior is None:
            inventory[epoch]=dict(epoch=epoch,product_id=_epoch_product(epoch),rows=0,
                last_index=None,last_date=None,has_current_bar=False,origin='new_accepted_epoch')
        inventory[epoch]['canonical_rows_appended']=inventory[epoch].get('canonical_rows_appended',0)+len(records)
        continuation.append(dict(epoch=epoch,mode=kind,checkpoint_before=before,appended=bars,final_state=state.to_dict()))
    arrays={epoch:states[epoch].to_series() if epoch in states else _empty_series(core) for epoch in inventory}
    forward={epoch:states[epoch] if epoch in states and states[epoch].last_seen==u else arrays[epoch]
             for epoch in inventory}
    current=set(epoch for epoch in states if states[epoch].last_seen==u)
    for epoch,r in inventory.items():
        if epoch in states:r['last_index']=states[epoch].last_seen
        r['last_date']=dates[r['last_index']] if r['last_index'] is not None else None
        r['has_current_bar']=epoch in current
    counts=Counter(_epoch_product(e) for e in current)
    product_states=[dict(product_id=p,current_rows=counts[p],status='observed_current_rows' if counts[p] else 'no_current_observation') for p in products]
    audit=dict(input_rows=len(dispositions),appended_rows=len(accepted),updated_epochs=len(groups),
        current_epoch_count=len(current),prior_inventory_count=len(epoch_inventory),inventory_count=len(inventory),
        unsupported_product_rows=len(unsupported),disposition_counts=dict(Counter(a['status'] for a in dispositions)),
        continuation_modes=dict(Counter(r['mode'] for r in continuation)),old_native_cache_loads=0,
        economic_projection_loads=0,SQL=0,new_fit=0,new_cash=0,paper_state_calls=0,history_overlap_replayed=0)
    receipt=dict(schema='stage339_incremental_source_receipt_v1',status='completed',
        source_receipt=deepcopy(source_receipt),normalization_receipt=deepcopy(normalization_receipt),
        calendar_confirmation=deepcopy(calendar_confirmation),previous_u_date=previous_u_date,
        previous_u_index=previous,u_date=u_date,u_index=u,counts=audit,
        boundary='Pure accepted-overlay continuation;does not certify raw units,source publication or operational clocks.')
    return dict(schema=SCHEMA,development_only=True,frozen_at=None,u_date=u_date,u_index=u,dates=dates,
        economics=deepcopy(economics),products=products,series_by_epoch=forward,warmup_state={e:s.to_dict() for e,s in states.items()},
        market=SnapshotMarket(arrays,dates),D_context=dc,
        clock=deepcopy(clock) if clock is not None else dict(source_completed_at=None,D_open_at=None),
        product_states=product_states,source='accepted_incremental_canonical_overlay',version=source_receipt,
        source_receipt=receipt,completed_at=None,incremental_audit=audit,unsupported_catalog=unsupported,
        _inventory=[inventory[e] for e in sorted(inventory)],_row_dispositions=dispositions,
        _continuation_evidence=continuation)
