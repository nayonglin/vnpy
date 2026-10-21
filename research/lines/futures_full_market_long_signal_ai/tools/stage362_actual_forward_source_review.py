"""One bounded offline review of the original361 terminal; no source rescue.

Independent raw/date/normalization, one-step Wilder and clock checks. Raw26
reconstruction uses frozen320 and is explicitly same-source consistency only.
No receiver, scoring, fitting, cash, journal append or old price replay.
"""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
import csv
from datetime import datetime, timezone
from decimal import Decimal
import gzip
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

LINE = Path(__file__).resolve().parents[1]
PLAN = LINE/'outputs/stage360_frozen_reference_decision/execution_plan.json'
OUT = LINE/'outputs/stage362_u20_forward_source_review'
U, PREV, D = '2026-10-20', '2026-10-19', '2026-10-21'
FIELDS = ('open', 'high', 'low', 'close', 'volume', 'close_oi')
KNOWN_FALSE = {'invalid_u_native_bar', 'insufficient_or_gap_history20',
               'known_entry_ineligible_lifecycle', 'capacity_below_one_roundtrip'}


def encoded(value, newline=False):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(',', ':'), allow_nan=False)+('\n' if newline else '')).encode()


def binding(path, raw=None):
    p = Path(path).resolve(); raw = p.read_bytes() if raw is None else raw
    return dict(path=str(p), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def write(path, value):
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
    with Path(path).open('xb') as f: f.write(raw)
    return binding(path, raw)


def utc(value):
    if value is None: return None
    t = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if t.tzinfo is None: raise ValueError('timezone required')
    return t.astimezone(timezone.utc)


def finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def clean(value):
    if isinstance(value, dict): return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [clean(v) for v in value]
    if hasattr(value, 'item'): return clean(value.item())
    if isinstance(value, float) and not math.isfinite(value): return None
    return value


def valid(v):
    return (all(finite(v.get(k)) and v[k] > 0 for k in FIELDS[:5])
            and v['low'] <= min(v['open'], v['close']) <= max(v['open'], v['close']) <= v['high']
            and (v.get('close_oi') is None or finite(v['close_oi']) and v['close_oi'] >= 0))


def raw_day(row, dtype, calendar):
    ns = row.get('raw_ns')
    if not (isinstance(ns, int) and not isinstance(ns, bool) and ns > 0
            and row.get('timestamp_state') == 'strict_integer_ns'):
        x = row.get('values', {}).get('datetime')
        if not (dtype == 'float64' and row.get('raw_datetime_type') == 'float64'
                and isinstance(x, float) and finite(x) and x > 0 and x.is_integer()): return None
        ns = int(x)
        if float(ns) != x or Decimal(row['raw_datetime_literal']) != ns: return None
    if ns % 10**9: return None
    t = datetime.fromtimestamp(ns//10**9, timezone.utc).astimezone(ZoneInfo('Asia/Shanghai'))
    day = t.date().isoformat()
    return day if t.hour == t.minute == t.second == 0 and calendar.get(day) is True else None


def empty_state():
    return dict(schema='stage320_wilder_state_v1', last_seen=None, last_day=None,
                last_close=None, N=None, seed=0., run=0, lows=[], history=[])


def advance(before, k, values):
    """Independent one new accepted bar, never a historical window replay."""
    s = deepcopy(before)
    if s['last_day'] is None or k != s['last_day']+1:
        s.update(last_day=None, last_close=None, N=None, seed=0., run=0, lows=[])
    O, H, L, C, V = [float(values[n]) for n in FIELDS[:5]]
    tr = H-L if s['last_close'] is None else max(H-L, abs(H-s['last_close']), abs(L-s['last_close']))
    s['run'] += 1
    if s['run'] <= 20:
        s['seed'] += tr
        if s['run'] == 20: s['N'] = s['seed']/20.
    else: s['N'] = (19.*s['N']+tr)/20.
    s['lows'] = [p for p in s['lows'] if p[0] >= k-19]
    while s['lows'] and s['lows'][-1][1] >= L: s['lows'].pop()
    s['lows'].append([k, L])
    low = s['lows'][0][1] if s['run'] >= 20 else None
    s.update(last_seen=k, last_day=k, last_close=C)
    s['history'] = (s['history']+[dict(day=k, values=[O,H,L,C,V], valid=True,
        N=s['N'], low20=low, run=s['run'], close_oi=values.get('close_oi'))])[-21:]
    return s


class Review:
    def __init__(self): self.cache={}; self.checks=Counter(); self.errors=[]; self.maxdiff=0.
    def check(self, name, okay, detail=None):
        self.checks[name] += 1
        if not okay: self.errors.append(dict(check=name, detail=detail))
    def read(self, b):
        path = str(Path(b['path']).resolve())
        if path not in self.cache: self.cache[path]=Path(path).read_bytes()
        raw=self.cache[path]
        self.check('binding_bytes_sha', len(raw)==b['bytes'] and hashlib.sha256(raw).hexdigest()==b['sha256'], path)
        return raw
    def json(self, b): return json.loads(self.read(b))
    def lines(self, b): return [json.loads(v) for v in gzip.decompress(self.read(b)).splitlines() if v]
    def equal(self, name, actual, expected, detail=None):
        def same(a,b):
            if finite(a) and finite(b):
                self.maxdiff=max(self.maxdiff, abs(a-b)); return math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-12)
            if isinstance(a,dict) and isinstance(b,dict): return a.keys()==b.keys() and all(same(a[k],b[k]) for k in a)
            if isinstance(a,list) and isinstance(b,list): return len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
            return a==b
        self.check(name,same(actual,expected),detail)
    def journal(self, path):
        meta=json.loads((path/'policy_identity.json').read_bytes()); rows=[]; prev='0'*64; keys=set()
        for line in (path/'journal.jsonl').read_bytes().splitlines(keepends=True):
            e=json.loads(line); content={k:v for k,v in e.items() if k!='entry_hash'}
            self.check('journal_chain', line.endswith(b'\n') and e['sequence']==len(rows)
                and e['previous_entry_hash']==prev and e['key'] not in keys
                and hashlib.sha256(encoded(content,True)).hexdigest()==e['entry_hash']
                and e['policy_sha256']==meta['policy_sha256'])
            self.check('journal_monotone',not rows or utc(e['recorded_at'])>=utc(rows[-1]['recorded_at']))
            prev=e['entry_hash']; keys.add(e['key']); rows.append(e)
        self.check('journal_policy', hashlib.sha256(encoded(meta['policy_identity'],True)).hexdigest()==meta['policy_sha256'])
        return rows


def prepare():
    plan=json.loads(PLAN.read_bytes()); out=OUT/'prepare1'; out.mkdir(parents=True,exist_ok=False)
    return write(out/'readiness.json',dict(schema='stage362_source_review_prepared_v1',
        plan=binding(PLAN), reviewer=binding(__file__), actual_output=plan['output'], actual_review_started=False,
        waiting_for='root original361 process terminal and session handle; no polling',
        independent_checks=['raw bytes/hash, symbol/epoch/date and incomplete statuses',
            'forming and unknown exclusion; exact u19 same-product witnesses and conditional factor1',
            'one-step prior compact Wilder N/low20/history; no old price replay',
            'full98 products/95 families and current/missing mother states',
            'prescore eligible-or-unresolved D domain; all current causal input domain; unknown clocks retained'],
        same_source_only=['frozen320 raw26 and original qualification reconstruction from final checkpoint'],
        excluded=['model scoring','financial replay','API/SQL','old suites','source retry','new account'],
        new_fit=0,new_cash=0,actual_API=0))


def finish(r, summary, out):
    summary.update(status='accepted_in_review_scope' if not r.errors else 'limitations_or_blockers_preserved',
        core_blockers=len(r.errors),errors=r.errors,checks=dict(r.checks),numeric_max_abs_difference=r.maxdiff,
        reviewed_at=datetime.now(timezone.utc).isoformat(),
        boundary='Source/observation scope only; unknowns do not become known, no alpha, funded acceptance or production qualification.')
    write(out/'actual_receipt.json',summary)
    print(json.dumps({k:summary.get(k) for k in ('status','core_blockers','raw_files','accepted_current','clocks','source_manifest_status')},ensure_ascii=False))
    return 0 if not r.errors else 1


def review_no_raw(r, manifest, capture, root, summary, out):
    """Acquisition failure is neither an empty trading signal nor a forward sample."""
    items=capture.get('items',{})
    r.check('no_archived_raw',not any('raw' in v for v in items.values()))
    r.check('raw_directory_empty',not (root/'raw').exists() or not list((root/'raw').iterdir()))
    r.check('single_attempt_no_retry',capture.get('api_instances_attempted')==1 and capture.get('retries')==0)
    r.check('failed_capture_preserved',capture.get('status')=='partial' and bool(capture.get('error_type')))
    entries=[]
    if (root/'source_journal/journal.jsonl').exists(): entries=r.journal(root/'source_journal')
    r.check('no_raw_receipts',len(entries)==0)
    result_binding=manifest.get('artifacts',{}).get('result')
    observed=r.json(result_binding) if result_binding else {}
    saved=observed.get('result',{});counts=saved.get('counts',{})
    for name in ('new_state_calls','advance_D_calls','seal_u_calls','new_fit','old_control_replays','SQL'):
        if name in counts:r.check('no_raw_boundary_zero',counts[name]==0,name)
    if saved:
        r.check('no_raw_candidates_or_scores',not saved.get('observations',{}).get('candidates') and not saved.get('scores'))
        r.check('no_raw_unfunded',saved.get('states') is None and saved.get('active') is False)
    clock=observed.get('research_clock',manifest.get('research_clock'))
    if clock:
        r.check('no_forward_claim',clock.get('forward_observation') is False and clock.get('timely_decision') is False
            and clock.get('timestamps_utc',{}).get('source_completed_at') is None)
    model_entries=[]
    if (root/'model_journal/journal.jsonl').exists():model_entries=r.journal(root/'model_journal')
    for e in model_entries:
        raw=(root/'model_journal/objects'/(e['payload_sha256']+'.json')).read_bytes()
        r.check('empty_source_journal_object_hash',hashlib.sha256(raw).hexdigest()==e['payload_sha256'])
    summary.update(source_manifest=binding(root/'manifest.json'),capture_status=capture.get('status'),
        source_manifest_status=manifest.get('status'),source_acquisition_succeeded=False,
        disposition='NO_NEW_RAW_OBSERVATION; acquisition failure, not a strategy empty-signal decision',
        raw_files=0,raw_rows=0,raw_statuses=dict(Counter(v.get('status') for v in items.values())),
        raw_expected_items=len(items),accepted_current=manifest.get('canonical_rows',0),
        capture_error_type=capture.get('error_type'),capture_error_redacted=capture.get('error_redacted'),
        raw_source_receipts=0,model_journal_kinds=dict(Counter(v['kind'] for v in model_entries)),
        unfunded_empty_source_research_seal_present=bool(observed.get('research_seal')),
        funded_decision_seals=0,model_scores=len(saved.get('scores',[])),
        forward_observations=0,clocks=clock,source_completed_at=None,D_open_at=None,
        forming_or_new_u_values_consumed=0,raw26_reconstruction_calls=0,old_compact_reads=0,
        numerics_review='not applicable: no newly acquired raw; no empty-source reconstruction rerun',
        full_domain_note='Frozen98/95 identity retained by source; no newly observed full-domain prices asserted',
        missing_or_failure_reclassified_as_zero=False,no_retry_or_source_repair=True)
    return finish(r,summary,out)


def review(session):
    r=Review(); plan=json.loads(PLAN.read_bytes()); root=Path(plan['output']); out=OUT/'actual_run1'
    out.mkdir(parents=True,exist_ok=False)
    write(out/'started.json',dict(schema='stage362_single_actual_review_started_v1',source_session=session,
        plan=binding(PLAN),reviewer=binding(__file__),actual_batch=str(root),API=0,SQL=0,new_fit=0,new_cash=0))
    summary=dict(schema='stage362_actual_source_review_v1',source_session=session,actual_batch=str(root),
        independent=True,raw_passes=1,model_inference=0,API=0,SQL=0,new_fit=0,new_cash=0,
        old_price_replay=0,old_suites=0,journal_append=0,active=False,states=None)
    try:
        auth=r.json(plan['authorization']); manifest=r.json(binding(root/'manifest.json'))
        terminal=r.json(binding(root/'terminal.json')); r.equal('manifest_terminal',terminal,manifest)
        r.check('exact_manifest_scope',manifest['schema']=='stage357_daily_collect_compose_manifest_v1'
            and manifest['inputs']==auth['inputs'] and manifest['source_bundle']==auth['source_bundle']
            and manifest['target_u']==U and manifest['mode']=='observe_only' and manifest['active'] is False
            and manifest['states'] is None and manifest['T0']==plan['T0'] and manifest['T0_created'] is False)
        for name in ('new_fit','new_cash','financial_D','SQL','old_native_cache','original_economics_projection_loads','metadata_queries','retries'):
            r.check('boundary_zero',manifest[name]==0,name)
        inp=auth['inputs']; art=manifest['artifacts']; capture=r.json(art['capture'])
        if manifest['status']=='no_raw_observation':
            return review_no_raw(r,manifest,capture,root,summary,out)
        result=r.json(art['result']); domains=r.json(art['clock_domains']); audit=r.json(art['normalization_audit'])
        overlay=r.json(art['canonical_overlay']); warmup=r.json(art['warmup_state'])
        inventory=r.json(art['epoch_inventory']); continuation=r.json(art['continuation_evidence'])
        calendar=r.json(inp['calendar338'])['days']; identity=r.json(inp['identity354'])['identity_map']
        symbols=r.json(inp['catalog338'])['symbols']; prior={v['native_values']['symbol']:v for v in r.lines(inp['overlay344'])}
        before={v['epoch']:v['final_state'] for v in r.lines(inp['warmup344'])}
        prior_inventory={v['epoch']:v for v in r.lines(inp['inventory344'])}
        sessions={(v['symbol'],v['trade_date']):v for v in r.lines(inp['sessions354'])}
        products=sorted(v['product_id'] for v in csv.DictReader(io.StringIO(r.read(inp['roster']).decode('utf-8-sig'))))
        dates_array=np.load(io.BytesIO(r.read(inp['source_calendar'])),allow_pickle=False)
        dates=([f'{int(v):08d}'[:4]+'-'+f'{int(v):08d}'[4:6]+'-'+f'{int(v):08d}'[6:8] for v in dates_array]
            if dates_array.dtype.kind in 'iu' else dates_array.astype('datetime64[D]').astype(str).tolist())
        u=dates.index(U); contract=r.json(inp['clock_contract'])
        r.check('full98_95',len(products)==len(set(products))==98 and len({v.removesuffix('_F') for v in products})==95)
        r.check('original874_domain',len(symbols)==len(identity)==874 and set(symbols)==set(identity)==set(capture['items']))
        r.check('one_api_no_retry',capture['api_instances_attempted']<=1 and capture['retries']==0
            and capture.get('requests',{}).get('single_symbol_serial',0)<=874)
        source_index=r.journal(root/'source_journal'); receipts={e['entry_hash']:e for e in source_index}
        raw_rows=[]; matches=set(); conflicts=set(); status_counts=Counter(); date_counts=Counter(); raw_files=0
        for symbol,item in sorted(capture['items'].items()):
            status_counts[item['status']]+=1
            if 'raw' not in item: continue
            raw_files+=1; b=item['raw']; r.check('raw_in_actual_directory',Path(b['path']).parent==root/'raw',symbol)
            raw=r.json(b); receipt=item['receipt']; r.check('original_raw_receipt',receipts.get(receipt['entry_hash'])==receipt,symbol)
            payload=(root/'source_journal/objects'/(receipt['payload_sha256']+'.json')).read_bytes()
            r.check('raw_receipt_payload',hashlib.sha256(payload).hexdigest()==receipt['payload_sha256']
                and json.loads(payload)==dict(symbol=symbol,raw=b,source_version=capture['source_version']),symbol)
            r.check('raw_schema_symbol_size',raw['schema']=='stage357_raw_daily3_v1' and raw['symbol']==symbol
                and raw['duration_seconds']==86400 and raw['data_length']==3 and len(raw['rows'])<=3
                and raw['fresh_ready']==item['fresh_ready'] and raw['scaling_applied']=='none',symbol)
            rows=[dict(symbol=symbol,epoch=identity.get(symbol),day=raw_day(v,raw['dtypes'].get('datetime'),calendar),
                values=v['values'],receipt=receipt,ready=item['fresh_ready'],raw_index=v['row_index']) for v in raw['rows']]
            raw_rows.extend(rows);date_counts.update(v['day'] or 'unknown' for v in rows)
            if symbol in prior:
                overlaps=[v for v in rows if v['day']==PREV]
                if (len(overlaps)==1 and item['fresh_ready'] is True and identity.get(symbol)==prior[symbol]['contract_epoch_id']
                        and all(overlaps[0]['values'].get(k)==prior[symbol]['canonical_values'].get(k) for k in FIELDS)): matches.add(symbol)
                else: conflicts.add(symbol)
            r.check('collection_receipt_window',utc(plan['hard_not_before'])<=utc(receipt['recorded_at'])<utc(plan['hard_not_after']),symbol)
        witnesses={identity[s].rsplit('.',1)[0] for s in matches}; prior_products={v['contract_epoch_id'].rsplit('.',1)[0] for v in prior.values()}
        accepted={}; rejected=Counter()
        for row in raw_rows:
            s,e,day=row['symbol'],row['epoch'],row['day']; reason=None
            if day!=U: reason='future_forming_not_consumed' if day and day>U else 'overlap_or_other_date_not_replayed' if day else 'date_unknown'
            elif row['ready'] is not True: reason='serial_not_ready'
            elif not e: reason='identity_unknown'
            elif s in conflicts: reason='u19_overlap_conflict_or_missing'
            elif not valid(row['values']): reason='invalid_or_zero_volume'
            elif e.rsplit('.',1)[0] not in prior_products or e.rsplit('.',1)[0] not in witnesses: reason='units_unconfirmed_product'
            if reason: rejected[reason]+=1
            else:
                r.check('unique_current_epoch',e not in accepted,e); accepted[e]=row
        r.equal('u19_overlap_matches',audit['overlap_matches'],sorted(matches)); r.equal('u19_overlap_conflicts',audit['overlap_conflicts'],sorted(conflicts))
        r.equal('witness_products',audit['witness_products'],sorted(witnesses)); r.equal('all_rejection_reasons',audit['reason_counts'],dict(rejected))
        r.check('raw_counts',audit['input_raw_rows']==len(raw_rows) and audit['accepted_current_rows']==len(accepted))
        current={v['contract_epoch_id']:v for v in overlay}; r.check('exact_accepted_overlay',len(current)==len(overlay) and set(current)==set(accepted))
        for e,v in current.items():
            a=accepted[e];r.equal('raw_to_canonical_values',v['canonical_values'],{k:a['values'].get(k) for k in FIELDS},e)
            r.check('u20_only_factor1',v['trade_date']==U and v['symbol']==a['symbol'] and v['received_at']==a['receipt']['recorded_at']
                and v['unit_overlay']['volume_factor']==v['unit_overlay']['oi_factor']==1
                and v['vendor_finality']=='unknown' and v['source_first_published_at'] is None,e)
        steps={v['epoch']:v for v in continuation};r.check('one_step_per_current',len(steps)==len(continuation) and set(steps)==set(current))
        expected_states=deepcopy(before)
        for e,c in steps.items():
            continuous=prior_inventory.get(e,{}).get('has_current_bar') is True
            expected_before=before[e] if continuous else empty_state()
            r.equal('before_checkpoint',c['checkpoint_before'],expected_before,e)
            r.check('one_new_u_append',len(c['appended'])==1 and c['appended'][0]['u_index']==u and c['appended'][0]['trade_date']==U,e)
            r.equal('append_bar',c['appended'][0]['bar'],dict(current[e]['canonical_values'],quality_status='accepted'),e)
            expected_states[e]=advance(expected_before,u,current[e]['canonical_values'])
            r.equal('independent_single_step_Wilder',c['final_state'],expected_states[e],e)
        r.equal('all_final_states_and_stale_retention',warmup,expected_states)
        inv={v['epoch']:v for v in inventory};r.check('inventory_no_drop',len(inv)==len(inventory) and set(prior_inventory)<=set(inv))
        r.check('inventory_current_exact',{e for e,v in inv.items() if v['has_current_bar']}==set(current))
        for e,v in inv.items():
            k=v['last_index'];r.check('inventory_date_no_future',k is None or 0<=k<=u and v['last_date']==dates[k],e)
            if e in warmup:r.check('state_inventory_last_seen',warmup[e]['last_seen']==k,e)
        economics=r.json(inp['economics331'])
        for e,v in r.json(inp['economics344']).items():
            r.check('economics_merge_no_conflict',e not in economics or economics[e]==v,e);economics[e]=v
        r.equal('current_economics_subset',r.json(art['current_economics']),{e:economics.get(e,{}) for e in current})
        saved=result['result']; obs=saved['observations']; source_bundle=r.json(auth['source_bundle'])
        core_binding=next(v for v in source_bundle['sources'] if Path(v['path']).name=='stage320_causal_forward_core.py')
        r.read(core_binding); spec=importlib.util.spec_from_file_location('stage362_frozen320',core_binding['path'])
        core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
        series={e:core.WilderState.from_dict(warmup[e]) if e in warmup and warmup[e]['last_seen']==u
            else core.WilderState.from_dict(warmup[e]).to_series() if e in warmup else core.WilderState().to_series() for e in inv}
        rebuilt=core.build_u_observations(series,u,dates,economics,products,D_context=obs['D_context'])
        # This is one same-source consistency check, not independent formulas or inference.
        r.equal('same_source_all_observations_raw26',clean(rebuilt),obs)
        r.check('full_mother_domain',sorted(v['product_id'] for v in obs['mothers'])==products
            and len({v['family_id'] for v in obs['mothers']})==95)
        r.check('raw26_shape_current',len(obs['raw_rows'])==len(obs['candidates'])==len(current)
            and all(len(v['raw26'])==26 for v in obs['raw_rows']))
        r.equal('domain_policy',domains['policy'],contract)
        execution=sorted(v['reference_epoch'] for v in obs['candidates'] if v['u_action_eligible']==1
            or not(v['u_action_eligible']==0 and v['u_ineligibility_reason'] in KNOWN_FALSE))
        r.check('before_score_domain',domains['before_score'] is True and domains['score_or_winner_used'] is False
            and domains['execution_deadline']['explicit_dependencies']==[])
        r.equal('all_current_input_domain',domains['input_completion']['epochs'],sorted(current))
        r.equal('prescore_eligible_unresolved_domain',domains['execution_deadline']['epochs'],execution)
        ends=[];opens=[];input_unknown=[];D_unknown=[];inverse={e:s for s,e in identity.items()}
        for e,v in sorted(current.items()):
            ss=sessions.get((v['symbol'],U),{}); end=ss.get('session_end') if ss.get('state')=='operational_regular_schedule' else None
            if not end or utc(v['received_at'])<utc(end):input_unknown.append(e);end=None
            else:ends.append(end)
            r.check('per_input_actual_completion',v['source_completed_at']==end
                and v['completion_observed_at']==(v['received_at'] if end else None),e)
        for e in execution:
            ss=sessions.get((inverse.get(e),D),{});opened=ss.get('first_open') if ss.get('state')=='operational_regular_schedule' else None
            if opened:opens.append(opened)
            else:D_unknown.append(e)
        complete=max(ends,key=utc) if ends and not input_unknown else None
        opened=min(opens,key=utc) if opens and not D_unknown else None
        r.equal('input_unknowns',domains['input_completion']['unknown_epochs'],input_unknown)
        r.equal('D_unknowns',domains['execution_deadline']['unknown_epochs'],D_unknown)
        r.equal('source_complete_aggregate',domains['input_completion']['source_completed_at'],complete)
        r.equal('D_open_aggregate',domains['execution_deadline']['D_open_at'],opened)
        entries=r.journal(root/'model_journal');emap={v['entry_hash']:v for v in entries}
        r.check('real_input_observe_seal_receipts',all(emap.get(v['entry_hash'])==v for v in
            (saved['input_receipt'],saved['observation_receipt'],result['research_seal'])))
        input_receipt=saved['input_receipt']; input_raw=(root/'model_journal/objects'/(input_receipt['payload_sha256']+'.json')).read_bytes()
        r.check('input_object_hash',hashlib.sha256(input_raw).hexdigest()==input_receipt['payload_sha256'])
        provenance=json.loads(input_raw)
        r.check('original_input_clock',provenance['clock']['source_completed_at']==complete and provenance['clock']['D_open_at']==opened
            and provenance['u_date']==U and provenance['u_index']==u and provenance['development_only'] is True)
        for receipt,want in ((saved['observation_receipt'],dict(observations=obs,scores=saved['scores'],selection=saved['selection'],
                instrument_evidence=saved['instrument_evidence'],cost_scenarios=saved['cost_scenarios'],input_entry_hash=input_receipt['entry_hash'],active=False)),):
            raw=(root/'model_journal/objects'/(receipt['payload_sha256']+'.json')).read_bytes()
            r.check('observation_object_hash',hashlib.sha256(raw).hexdigest()==receipt['payload_sha256'] and raw==encoded(want,True))
        seal=result['research_seal'];seal_raw=(root/'model_journal/objects'/(seal['payload_sha256']+'.json')).read_bytes()
        seal_payload=dict(schema='stage357_unfunded_research_decision_v1',active=False,states=None,
            observations=obs,scores=saved['scores'],selection=saved['selection'],instrument_evidence=saved['instrument_evidence'],
            cost_scenarios=saved['cost_scenarios'],input_receipt=saved['input_receipt'],observation_receipt=saved['observation_receipt'],
            clock_domains=domains,policy_identity=saved['policy_identity'],
            boundary='Complete unfunded research object;not an executable or funded account decision.')
        r.check('full_unfunded_seal_object_hash',hashlib.sha256(seal_raw).hexdigest()==seal['payload_sha256']
            and seal_raw==encoded(seal_payload,True))
        clock=result['research_clock']; times=clock['timestamps_utc']
        r.check('research_clock_actual_times',times==dict(frozen_at=utc(manifest['T0']).isoformat(),
            source_completed_at=utc(complete).isoformat() if complete else None,received_at=utc(input_receipt['recorded_at']).isoformat(),
            decision_sealed_at=utc(result['research_seal']['recorded_at']).isoformat(),D_open_at=utc(opened).isoformat() if opened else None))
        forward=complete is not None and utc(complete)>utc(manifest['T0']); received=utc(input_receipt['recorded_at']); sealed=utc(result['research_seal']['recorded_at'])
        status=('completion_clock_unknown' if complete is None else 'historical_before_freeze' if not forward else
            'received_before_completion' if received<utc(complete) else 'D_clock_unknown' if opened is None else
            'late_input' if received>=utc(opened) else 'late_decision' if sealed>=utc(opened) else 'timely_forward_decision')
        r.check('independent_research_clock_classification',clock['status']==status and clock['forward_observation']==forward
            and clock['timely_decision']==(status=='timely_forward_decision') and clock['clock_provenance_certified'] is False)
        r.check('unfunded_only',result['active'] is False and result['states'] is None and result['new_fit']==result['new_cash']==0
            and saved['mode']=='observe_only' and all(saved['counts'][k]==0 for k in ('new_state_calls','advance_D_calls','seal_u_calls','new_fit','old_control_replays','SQL')))
        summary.update(source_manifest=binding(root/'manifest.json'),capture_status=capture['status'],source_manifest_status=manifest['status'],
            raw_files=raw_files,raw_rows=len(raw_rows),raw_statuses=dict(status_counts),raw_dates=dict(date_counts),
            accepted_current=len(current),normalization_rejections=dict(rejected),u19_matches=len(matches),u19_conflicts=len(conflicts),
            warmup_states=len(warmup),inventory_epochs=len(inv),mothers=len(obs['mothers']),families=95,
            no_observation_products=[v['product_id'] for v in obs['mothers'] if v['status']=='no_accepted_observation'],
            input_domain=len(current),input_clock_unknown_epochs=input_unknown,execution_domain=len(execution),D_clock_unknown_epochs=D_unknown,
            clocks=clock,same_source_raw26_consistency=True,independent_raw26_formula_implementation=False,
            completed_capture_is_not_all_clocks_known=True,vendor_finality='unknown',source_first_published_at='unknown')
    except Exception as error:
        summary.update(exception_type=type(error).__name__,exception=str(error))
        r.errors.append(dict(check='review_completed_without_exception',detail=str(error)))
    return finish(r,summary,out)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--prepare',action='store_true');g.add_argument('--review',action='store_true')
    p.add_argument('--source-session');args=p.parse_args()
    if args.prepare: print(json.dumps(prepare()))
    elif not args.source_session: p.error('root original terminal session handle required')
    else: raise SystemExit(review(args.source_session))
