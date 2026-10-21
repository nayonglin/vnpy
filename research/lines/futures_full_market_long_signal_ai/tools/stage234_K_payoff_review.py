"""Independent bounded K-point review. Actual I/O requires exact root authorization."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
import time
import numpy as np

TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
PROTOCOL = LINE/'outputs/stage230_K_payoff_measurement_protocol/protocol.json'
PROTOCOL_SHA = 'ba46ca70fd2bc6387f0cd89d9c7bb7313283b1de38cc9893442487e7ec754f85'
ACTUAL = LINE/'outputs/stage233_K_payoff_measurement/actual_run1'
OUTPUT = LINE/'outputs/stage234_K_payoff_numeric_review/actual_run1'
PHASE = 'after_all_source_close'
SCENARIOS = {'base': ('2', '.0001', '.0001', 1), 'stress': ('6', '.0003', '.0003', 3)}
POTENTIAL = {'closed_on_K_priority_reprice', 'closed_after_K', 'unknown_after_K', 'open_K_reached'}


class QuoteUnrepresentable(ValueError):
    pass


def number(value):
    value = float(value)
    if not math.isfinite(value): raise ValueError('nonfinite_numeric_evidence')
    return value


def optional(value):
    return None if value in ('', None) else number(value)


def integer(value):
    value = number(value)
    if not value.is_integer() or abs(value)>2**53: raise ValueError('invalid_integer')
    return int(value)


def close(actual, expected, name, atol=1e-9):
    a, b = number(actual), number(expected)
    if abs(a-b)>atol+1e-12*abs(b): raise ValueError('numeric_mismatch '+name+' '+repr((a,b)))


def independent_quote(reference, multiplier, tick, scenario):
    """Independent Decimal SELL, no author/kernel imports."""
    p, mult = Decimal(str(reference)), Decimal(str(multiplier))
    if not p.is_finite() or p<=0 or not mult.is_finite() or mult<=0:
        raise ValueError('invalid_quote_source')
    fmin, fbps, sbps, sticks = SCENARIOS[scenario]
    t = Decimal(str(tick)) if tick not in ('', None) else Decimal('NaN')
    tickized = bool(t.is_finite() and t>0)
    slip = abs(p)*Decimal(sbps)
    if tickized: slip=max(slip,t*sticks)
    fill=p-slip
    if tickized: fill=(fill/t).to_integral_value(rounding=ROUND_FLOOR)*t
    if not fill.is_finite() or fill<=0: raise QuoteUnrepresentable('nonpositive_adverse_fill')
    fee=max(Decimal(fmin),abs(fill)*mult*Decimal(fbps))
    slip_cny=abs(fill-p)*mult
    result=dict(fill_price=float(fill),fee_per_lot=float(fee),slippage_per_lot=float(slip_cny),tickized=int(tickized))
    if not all(math.isfinite(v) for v in result.values()): raise QuoteUnrepresentable('nonfinite_quote')
    return result


def new_payoff(raw, K_open, scenario):
    N,M,risk=(number(raw[k]) for k in ('N_u','multiplier','cash_risk_unit'))
    if min(N,M,risk)<=0 or integer(raw['filled'])!=1: raise ValueError('incomplete_inherited_entry')
    close(raw['R0_points'],.25*N,'R0_points'); close(risk,.25*N*M,'cash_risk_unit')
    entry=number(raw[scenario+'_entry_fill']); fee=number(raw[scenario+'_entry_fee_per_lot'])
    slip=number(raw[scenario+'_entry_slippage_per_lot']); F=number(raw['entry_reference'])
    if min(entry,F)<=0 or min(fee,slip)<0: raise ValueError('invalid_inherited_entry')
    q=independent_quote(K_open,M,raw['tick_size'],scenario)
    net=M*(q['fill_price']-entry)-fee-q['fee_per_lot']
    alt=M*(number(K_open)-F)-slip-q['slippage_per_lot']-fee-q['fee_per_lot']
    close(net,alt,'two_equivalent_cost_identities')
    R=net/risk; aux=net/(2*N*M)
    if not all(math.isfinite(v) for v in (net,R,aux)): raise QuoteUnrepresentable('nonfinite_payoff')
    return dict(q,net_pnl=net,net_R=R,net_R_common2N=aux,total_fee=fee+q['fee_per_lot'],
                total_slippage=slip+q['slippage_per_lot'])


def native_point(cache, epoch, K):
    epochs=cache['epochs']; slot=int(np.searchsorted(epochs,epoch))
    if slot>=len(epochs) or epochs[slot]!=epoch: raise ValueError('K_epoch_not_found')
    start,end=int(cache['offsets'][slot]),int(cache['offsets'][slot+1])
    days=cache['days'][start:end]; local=int(np.searchsorted(days,K))
    if local>=len(days) or int(days[local])!=K: raise ValueError('claimed_prefix_missing_K_point')
    flat=start+local; O=float(cache['values'][flat,0]); valid=bool(cache['valid'][flat])
    if not valid or not math.isfinite(O) or O<=0: raise ValueError('claimed_prefix_invalid_K_point')
    return dict(epoch_slot=slot,offset_start=start,offset_end=end,local_row=local,flat_row=flat,
                native_day=K,native_open=O,native_valid=int(valid))


def branch_contract(primary,timing,allowed,K_date,participation_date,u_date=None,u_eligible=True):
    result=dict(mode='unknown',policy_reward=None,policy_known_date=None,known_phase=None)
    if not primary:
        if not u_eligible or allowed is not None:
            result.update(mode='noaction',policy_reward=0.,policy_known_date=u_date,known_phase=PHASE)
    elif timing=='closed_before_K': result.update(mode='copy')
    elif timing=='known_nonparticipation':
        result.update(mode='cancel',policy_reward=0.,policy_known_date=participation_date,known_phase=PHASE)
    elif timing in POTENTIAL: result.update(mode='quote',known_phase=PHASE)
    return result


def parent_tally(mother_count, parents):
    a=np.asarray(parents,dtype=np.int64)
    if (a<0).any() or (a>=mother_count).any(): raise ValueError('invalid_parent_identity')
    return np.bincount(a,minlength=mother_count)


def binding(path):
    p=Path(path).resolve(); raw=p.read_bytes()
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def read_bound(b):
    raw=Path(b['path']).read_bytes()
    if len(raw)!=b['bytes'] or hashlib.sha256(raw).hexdigest()!=b['sha256']: raise ValueError('small_binding_changed '+b['path'])
    return raw


def write(path,value):
    with Path(path).open('x',encoding='utf8') as f:
        json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')


def source_bundle():
    return [binding(TOOLS/name) for name in ('stage234_K_payoff_review.py','test_stage234_K_payoff_review.py',
            'stage227_K_clock_support.py','stage156_voluntary_choices.py')]


def producer_bundle():
    return sorted([binding(TOOLS/name) for name in ('stage233_K_payoff_measurement.py','test_stage233_K_payoff_measurement.py',
                   'stage227_K_clock_support.py','stage156_voluntary_choices.py','stage042_cross_session_experiment.py')],key=lambda b:b['path'])


def load_classifier():
    spec=importlib.util.spec_from_file_location('accepted227_stage234',TOOLS/'stage227_K_clock_support.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


class HashReader(io.RawIOBase):
    def __init__(self,source): self.source=source;self.digest=hashlib.sha256()
    def readable(self): return True
    def readinto(self,buf):
        n=self.source.readinto(buf)
        if n: self.digest.update(memoryview(buf)[:n])
        return n


def csv_rows(b):
    """A single compressed-file stream, hashing while its rows are consumed."""
    with Path(b['path']).open('rb') as source:
        hashed=HashReader(source)
        with io.BufferedReader(hashed) as buffered:
            with gzip.GzipFile(fileobj=buffered) as z:
                with io.TextIOWrapper(z,encoding='utf8',newline='') as text:
                    reader=csv.DictReader(text)
                    if len(reader.fieldnames)!=len(set(reader.fieldnames)): raise ValueError('duplicate_csv_column')
                    for row in reader:
                        if None in row or any(v is None for v in row.values()): raise ValueError('malformed_csv')
                        yield row
            while buffered.read(1024*1024): pass
        if hashed.digest.hexdigest()!=b['sha256'] or Path(b['path']).stat().st_size!=b['bytes']:
            raise ValueError('new_artifact_binding_changed '+b['path'])


def stat_old(b):
    s=Path(b['path']).stat()
    if s.st_size!=b['bytes']: raise ValueError('inherited_input_size_changed')
    return dict(bytes=s.st_size,device=s.st_dev,inode=s.st_ino,mtime_ns=s.st_mtime_ns,
                inherited_sha256=b['sha256'],rehashed=False)


def equal_token(actual,expected,name):
    if ('' if expected is None else str(expected))!=actual:
        raise ValueError('exact_token_mismatch '+name)


def check_nullable(actual,expected,name,atol=1e-9):
    if expected is None:
        if actual not in ('',None): raise ValueError('unknown_not_null '+name)
    else: close(actual,expected,name,atol)


def check_json(actual,expected,path='summary'):
    """Only compare independently specified keys, preserving zero metric groups."""
    if isinstance(expected,dict):
        if not isinstance(actual,dict): raise ValueError('object_expected '+path)
        for k,v in expected.items():
            if k not in actual: raise ValueError('missing_report_key '+path+'/'+k)
            check_json(actual[k],v,path+'/'+k)
    elif isinstance(expected,list):
        if not isinstance(actual,list) or len(actual)!=len(expected): raise ValueError('report_list_length '+path)
        for i,(a,b) in enumerate(zip(actual,expected)): check_json(a,b,path+'/'+str(i))
    elif isinstance(expected,float):
        close(actual,expected,path,1e-11)
    elif actual!=expected: raise ValueError('report_value_mismatch '+path+' '+repr((actual,expected)))


class SummaryAudit:
    """Independent row aggregates; action deltas never become account returns."""
    def __init__(self):
        self.counts=defaultdict(Counter);self.deltas=defaultdict(list);self.signs=defaultdict(Counter)

    @staticmethod
    def keys(product,family,day):
        for scope in (('all','2020onward') if day>='2020-01-01' else ('all',)):
            yield (scope,'global','all')
            yield (scope,'year',day[:4]);yield (scope,'family',family);yield (scope,'product',product)

    def action(self,identity,primary,timing,branch,results,original):
        metrics=Counter(action_count=1,primary_domain_count=int(primary),new_K_quote_action_count=int(branch=='quote'))
        metrics['timing_'+timing+'_count']+=1;metrics['primary_timing_'+timing+'_count']+=int(primary)
        pair={}
        for cost,r in results.items():
            known=bool(r['known']);mode=r['mode']
            metrics[cost+'_known_count']+=known
            metrics[cost+'_noaction_count']+=mode in ('cancel','noaction')
            metrics[cost+'_unknown_count']+=not known and mode not in ('cancel','noaction')
            metrics[cost+'_state_'+r['state']+'_count']+=1
            old=original[cost]
            if primary and old is not None:
                metrics[cost+'_oldclosed_primary_count']+=1
                metrics[cost+'_oldclosed_newknown_count']+=known
                metrics[cost+'_oldclosed_newunknown_count']+=not known
            if primary and known and old is not None:
                delta=number(r['net_R'])-old
                metrics[cost+'_known_pair_count']+=1
                metrics[cost+'_known_pair_changed_count']+=abs(delta)>1e-12*(1+abs(old))
                pair[cost]=(delta,('negative' if old<0 else 'positive' if old>0 else 'zero')+'->'+
                            ('negative' if r['net_R']<0 else 'positive' if r['net_R']>0 else 'zero'))
            if primary and known and old is None: metrics[cost+'_oldunknown_newknown_count']+=1
        for key in self.keys(identity['product_id'],identity['family_id'],identity['u_date']):
            self.counts[key].update(metrics)
            for cost,(delta,sign) in pair.items():
                self.deltas[(key,cost)].append(delta);self.signs[(key,cost)][sign]+=1

    def mother(self,identity,child_count):
        for key in self.keys(identity['product_id'],identity['family_id'],identity['u_date']):
            self.counts[key].update(mother_count=1,nochild_mother_count=int(child_count==0))

    def paired(self,key,cost):
        values=self.deltas[(key,cost)]
        return dict(count=len(values),sign_matrix=dict(self.signs[(key,cost)]),
                    absdelta_R_quantiles=(np.quantile(np.abs(values),[.5,.9,.99,1.]).tolist() if values else None))


def metadata_from_label(row, calendar):
    """Reuse accepted227 only for clocks; absent non-deriving fields are not reaudited."""
    names=('sequence_index','action_id','mother_sequence_index','mother_event_id','product_id','family_id',
           'u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible','participation_state','label_state',
           'filled','trade_label_known','entry_index','entry_date','exit_index','exit_date','unknown_index','unknown_date',
           'label_known_date','label_known_phase','participation_known_date','participation_known_phase','cancel_reason')
    raw={k:row[k] for k in names}
    raw.update(action_sequence_index=row['sequence_index'],D_index=str(integer(row['u_index'])+1),
               label_history_ready20='0' if row['label_state']=='not_history_ready' else '1',last_path_index='')
    return raw


def expected_branch(row,derived):
    primary=bool(derived['primary_domain']);timing=derived['timing_state']
    ueligible=integer(row['u_action_eligible'])==1
    c=branch_contract(primary,timing,derived['calendar_allowed'],derived['K_date'],
                      row['participation_known_date'],row['u_date'],u_eligible=ueligible)
    names={'copy':'copy_before_K','quote':'quote_K','cancel':'known_nonparticipation','noaction':'nonprimary_noaction'}
    branch=names.get(c['mode'],'unresolved' if primary else 'nonprimary_calendar_unknown')
    if branch=='known_nonparticipation' and row['participation_known_phase']!=PHASE:
        raise ValueError('original_cancel_phase_changed')
    return branch,c


def verify_cost(row,cost,branch,payoff=None):
    prefix='K_'+cost+'_';known=branch=='copy_before_K' or branch=='quote_K' and payoff is not None
    equal_token(row[prefix+'known'],int(known),prefix+'known')
    if branch=='copy_before_K':
        state='known_original_before_K'
        for old,new in [('net_pnl_'+cost+'_per_lot','net_pnl_per_lot'),('net_R_'+cost,'net_R'),
                        ('net_R_common2N_'+cost,'net_R_common2N'),('label_known_date','known_date'),
                        ('label_known_phase','known_phase'),('exit_index','exit_index'),('exit_date','exit_date'),
                        ('exit_reason','exit_reason')]: equal_token(row[prefix+new],row[old],prefix+new)
    elif known:
        state='known_K_quote'
        for key in ('net_pnl_per_lot','net_R','net_R_common2N'):
            check_nullable(row[prefix+key],payoff['net_pnl' if key=='net_pnl_per_lot' else key],prefix+key,
                           1e-11 if 'R' in key else 1e-9)
        for key,value in [('known_date',row['K_date']),('known_phase',PHASE),('exit_index',row['K_index']),
                          ('exit_date',row['K_date']),('exit_reason','K_deadline_open')]: equal_token(row[prefix+key],value,prefix+key)
    else:
        state=('unknown_K_cost' if branch=='quote_K' else branch if branch.startswith('nonprimary')
               else row['timing_state'])
        for key in ('net_pnl_per_lot','net_R','net_R_common2N','known_date','known_phase','exit_index','exit_date','exit_reason'):
            equal_token(row[prefix+key],'',prefix+key)
    equal_token(row[prefix+'state'],state,prefix+'state')
    if known:
        R=number(row[prefix+'net_R']);number(row[prefix+'net_pnl_per_lot']);number(row[prefix+'net_R_common2N'])
        if row['label_state']=='closed_complete_bar_model' and (row[prefix+'known_date']>row['label_known_date'] or
                row[prefix+'known_phase']!=row['label_known_phase']): raise ValueError('oldclosed_known_clock_not_dominated')
    else: R=None
    mode='cancel' if branch=='known_nonparticipation' else 'noaction' if branch=='nonprimary_noaction' else 'trade'
    return dict(known=known,state=state,net_R=R,mode=mode)


def stats_expected(audit,key,quantiles):
    c=audit.counts[key]
    result=dict(action_count=c['action_count'],primary_count=c['primary_domain_count'],K_quote_count=c['new_K_quote_action_count'],
                mother_count=c['mother_count'],nochild_mother_count=c['nochild_mother_count'],
                noaction_count=c['base_noaction_count'],timing_counts={},primary_timing_counts={},calendar_counts={},costs={})
    for k,v in c.items():
        if k.startswith('primary_timing_') and k.endswith('_count'): result['primary_timing_counts'][k[15:-6]]=v
        elif k.startswith('timing_') and k.endswith('_count'): result['timing_counts'][k[7:-6]]=v
        elif k.startswith('calendar:'): result['calendar_counts'][k[9:]]=v
    for cost in SCENARIOS:
        pair=audit.paired(key,cost)
        states={k[len(cost)+7:-6]:v for k,v in c.items() if k.startswith(cost+'_state_') and k.endswith('_count')}
        q=pair['absdelta_R_quantiles']
        result['costs'][cost]=dict(known_count=c[cost+'_known_count'],unknown_count=c[cost+'_unknown_count'],
            noaction_count=c[cost+'_noaction_count'],states=states,oldclosed_primary_count=c[cost+'_oldclosed_primary_count'],
            oldclosed_newknown_count=c[cost+'_oldclosed_newknown_count'],oldclosed_cost_unknown_count=c[cost+'_oldclosed_newunknown_count'],
            oldclosed_clock_violation_count=0,paired_count=pair['count'],changed_count=c[cost+'_known_pair_changed_count'],
            oldunknown_newknown_count=c[cost+'_oldunknown_newknown_count'],sign_matrix=pair['sign_matrix'],
            absdelta_R_quantiles=(dict(zip(('p50','p90','p99','max'),q)) if quantiles and q else {}))
    return result


def compare_stats(actual,expected,path):
    # Counter maps may omit genuine zeros, but may not introduce a nonzero extra.
    for field in ('timing_counts','primary_timing_counts','calendar_counts'):
        for key in set(actual[field])|set(expected[field]):
            if actual[field].get(key,0)!=expected[field].get(key,0): raise ValueError('counter_mismatch '+path+'/'+field+'/'+key)
    for cost in SCENARIOS:
        for field in ('states','sign_matrix'):
            a=actual['costs'][cost][field];e=expected['costs'][cost][field]
            if any(a.get(k,0)!=e.get(k,0) for k in set(a)|set(e)): raise ValueError('cost_counter_mismatch '+path+'/'+cost+'/'+field)
        e={k:v for k,v in expected['costs'][cost].items() if k not in ('states','sign_matrix','absdelta_R_quantiles')}
        check_json(actual['costs'][cost],e,path+'/'+cost)
        q=expected['costs'][cost]['absdelta_R_quantiles'];aq=actual['costs'][cost]['absdelta_R_quantiles']
        check_json(aq,q,path+'/'+cost+'/quantiles')
    check_json(actual,{k:v for k,v in expected.items() if k not in ('costs','timing_counts','primary_timing_counts','calendar_counts')},path)


def review_new_outputs(protocol, manifest, actual_dir):
    if (manifest.get('status')!='completed' or manifest.get('schema')!='stage233_K_payoff_measurement_v1' or
            manifest.get('protocol_sha256')!=PROTOCOL_SHA or manifest.get('input_bindings')!=protocol['input_bindings']):
        raise ValueError('author_actual_manifest_not_exact_completed230')
    if manifest.get('protocol')!=binding(PROTOCOL) or manifest.get('source_bundle')!=producer_bundle():
        raise ValueError('author_frozen_protocol_or_source_bundle_changed')
    producer_auth=json.loads(read_bound(manifest['authorization']))
    required=dict(schema='stage230_exact_root_authorization_v1',authorized_by='root',stage='measurement',
                  exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(actual_dir),source_bundle=manifest['source_bundle'])
    if any(producer_auth.get(k)!=v for k,v in required.items()): raise ValueError('producer_exact_root_authorization_changed')
    if (len(manifest['label_columns'])!=68 or len(manifest['evidence_columns'])!=96 or len(manifest['mother_columns'])!=16):
        raise ValueError('frozen_compact_output_interface_changed')
    artifacts=manifest['artifacts']
    def artifact(name):
        b=artifacts[name]
        if Path(b['path']).resolve().parent!=actual_dir: raise ValueError('new_artifact_outside_actual_dir')
        return b
    expected_io=protocol['source_budget']
    started=json.loads(read_bound(artifact('started.json')))
    if any(started.get(k)!=manifest[k] for k in ('protocol','authorization','source_bundle')):
        raise ValueError('producer_started_source_identity_mismatch')
    terminal=json.loads(read_bound(artifact('terminal.json')))
    reads=json.loads(read_bound(artifact('source_read_receipt.json')))
    if (terminal['schema']!='stage233_K_payoff_terminal_v1' or terminal['status']!='completed' or terminal['automatic_retry'] is not False or terminal['new_fit']!=0 or terminal['new_cash']!=0 or
            manifest['counters']!=expected_io or terminal['counters']!=expected_io or reads['counters']!=expected_io or
            reads['new_K_path_replays']!=0 or reads['physical_NPZ_point_only_reads_claimed'] is not False or
            reads['inputs']!=protocol['input_bindings']): raise ValueError('author_source_read_budget_mismatch')
    for role in ('actions','mothers','native_cache'):
        recorded=reads['source_stats'][role];b=protocol['input_bindings'][role]
        if (recorded['before']!=recorded['after'] or recorded['before']['bytes']!=b['bytes'] or
                recorded['before']['inherited_sha256']!=b['sha256'] or recorded['before']['rehashed'] is not False):
            raise ValueError('author_inherited_source_stats_mismatch '+role)
    for b in manifest['source_bundle']: read_bound(b)
    for role in ('classifier227','calendar_gate156','quote_kernel042'):
        read_bound(protocol['input_bindings'][role])
    classifier=load_classifier(); cal=np.load(io.BytesIO(read_bound(protocol['input_bindings']['calendar'])),allow_pickle=False)
    if cal.dtype.kind in 'iu':
        calendar=[datetime.strptime(str(int(value)),'%Y%m%d').date().isoformat() for value in cal]
    else: calendar=cal.astype('datetime64[D]').astype(str).tolist()
    if calendar!=sorted(set(calendar)) or protocol['sample_end'] not in calendar: raise ValueError('calendar_invalid')
    days_set=set(calendar); cache_b=protocol['input_bindings']['native_cache'];before=stat_old(cache_b)
    cache_meta=json.loads(read_bound(protocol['input_bindings']['native_cache_manifest']))
    if (cache_meta['schema']!='stage132_native_store_recovery_cache_v1' or cache_meta['native_rows']!=1552456 or
            cache_meta['native_epochs']!=9520 or cache_meta['file']!=cache_b): raise ValueError('accepted_cache_manifest_changed')
    with np.load(cache_b['path'],allow_pickle=False) as z: cache={k:z[k] for k in protocol['native_members']}
    n=len(cache['days'])
    if (len(cache['epochs'])!=9520 or n!=1552456 or cache['offsets'][0]!=0 or cache['offsets'][-1]!=n or
            len(cache['offsets'])!=len(cache['epochs'])+1 or (np.diff(cache['offsets'])<0).any() or
            cache['values'].shape!=(n,5) or len(cache['valid'])!=n or
            not np.array_equal(cache['epochs'],np.unique(cache['epochs']))): raise ValueError('cache_mapping_schema_changed')
    evidence={};expected_costs={};quote_sequence=[]
    for row in csv_rows(artifact('K_quote_evidence.csv.gz')):
        seq=integer(row['sequence_index'])
        if seq in evidence or quote_sequence and seq<=quote_sequence[-1]: raise ValueError('quote_identity_order_or_duplicate')
        if row['branch']!='quote_K': raise ValueError('extra_quote_branch')
        p=native_point(cache,row['reference_epoch'],integer(row['K_index']))
        for key in p:
            if key=='native_open': close(row[key],p[key],key,1e-12)
            else: equal_token(row[key],p[key],key)
        expected_costs[seq]={}
        for cost in SCENARIOS:
            try: payoff=new_payoff(row,p['native_open'],cost)
            except QuoteUnrepresentable: payoff=None
            expected_costs[seq][cost]=payoff
            for target,source in [('sell_fill','fill_price'),('sell_fee_per_lot','fee_per_lot'),
                                  ('sell_slippage_per_lot','slippage_per_lot'),('tickized','tickized')]:
                check_nullable(row['K_'+cost+'_'+target],None if payoff is None else payoff[source],cost+'/'+target)
        evidence[seq]=row;quote_sequence.append(seq)
    if len(evidence)!=protocol['expected_new_K_quote_actions']: raise ValueError('K_quote_domain_count')
    del cache
    after=stat_old(cache_b)
    if before!=after: raise ValueError('cache_stat_changed')
    mother_fields=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
    count_fields=['child_count','primary_count','K_quote_count']+[s+'_'+v+'_count' for s in SCENARIOS for v in ('known','unknown','noaction')]
    mothers={k:[] for k in mother_fields};reported=[]
    for row in csv_rows(artifact('mothers_K.csv.gz')):
        seq=len(reported)
        if integer(row['sequence_index'])!=seq or not 0<=integer(row['u_index'])<len(calendar) or calendar[integer(row['u_index'])]!=row['u_date']:
            raise ValueError('mother_sequence_or_clock')
        if row['family_id']!=row['product_id'].removesuffix('_F') or row['reference_epoch'] and row['reference_epoch'].rsplit('.',1)[0]!=row['product_id']:
            raise ValueError('mother_product_epoch')
        for k in mother_fields: mothers[k].append(row[k])
        reported.append([integer(row[k]) for k in count_fields])
    m=len(reported)
    if m!=protocol['expected_mother_rows']: raise ValueError('mother_domain_count')
    reported=np.asarray(reported,dtype=np.int32);counts=np.zeros_like(reported)
    audit=SummaryAudit(); boundary_cache={};rows=0;seen_quotes=0
    for row in csv_rows(artifact('labels_K.csv.gz')):
        seq=integer(row['sequence_index']);parent=integer(row['mother_sequence_index'])
        if seq!=rows or not row['action_id'] or not 0<=parent<m: raise ValueError('action_sequence_parent')
        for k in ('product_id','family_id','u_date','u_index'):
            if row[k]!=mothers[k][parent]: raise ValueError('action_mother_'+k)
        if row['mother_event_id']!=mothers['event_id'][parent] or row['anchor_epoch']!=mothers['reference_epoch'][parent]:
            raise ValueError('action_mother_identity_anchor')
        raw=metadata_from_label(row,calendar);epoch=row['reference_epoch']
        if epoch not in boundary_cache: boundary_cache[epoch]=classifier.gate_helper().calendar_boundary(epoch,calendar,protocol['sample_end'])
        d=classifier.classify_action(raw,calendar,protocol['sample_end'],boundary_cache[epoch],days_set)
        for k in ('primary_domain','calendar_allowed','calendar_state','D_date','K_target_date','K_index','K_date','K_state','K_after_sample_end','timing_state'):
            equal_token(row[k],d[k],k)
        branch,c=expected_branch(row,d);equal_token(row['branch'],branch,'branch')
        policy_known=branch in ('nonprimary_noaction','known_nonparticipation')
        equal_token(row['policy_reward_known'],int(policy_known),'policy_reward_known')
        check_nullable(row['policy_reward'],0. if policy_known else None,'policy_reward')
        equal_token(row['policy_known_date'],c['policy_known_date'] if policy_known else None,'policy_known_date')
        equal_token(row['policy_known_phase'],PHASE if policy_known else None,'policy_known_phase')
        if branch=='quote_K':
            if seq not in evidence: raise ValueError('missing_quote_evidence')
            for k,v in row.items(): equal_token(evidence[seq][k],v,'label_evidence_join/'+k)
            payoffs=expected_costs[seq];seen_quotes+=1
        else:
            if seq in evidence: raise ValueError('quote_outside_potential_domain')
            payoffs=dict.fromkeys(SCENARIOS)
        results={cost:verify_cost(row,cost,branch,payoffs[cost]) for cost in SCENARIOS}
        original={cost:(number(row['net_R_'+cost]) if row['label_state']=='closed_complete_bar_model' else None) for cost in SCENARIOS}
        audit.action(row,bool(d['primary_domain']),d['timing_state'],'quote' if branch=='quote_K' else branch,results,original)
        for key in audit.keys(row['product_id'],row['family_id'],row['u_date']): audit.counts[key]['calendar:'+row['calendar_state']]+=1
        values=[1,d['primary_domain'],int(branch=='quote_K')]
        for cost in SCENARIOS:
            r=results[cost];noaction=r['mode'] in ('cancel','noaction')
            values.extend((int(r['known']),int(not r['known'] and not noaction),int(noaction)))
        counts[parent]+=values;rows+=1
    if rows!=protocol['expected_action_rows'] or seen_quotes!=len(evidence) or not np.array_equal(counts,reported):
        raise ValueError('full_domain_or_mother_counts_mismatch')
    nochild=int(np.sum(counts[:,0]==0))
    if nochild!=protocol['expected_nochild_mothers']: raise ValueError('nochild_domain_mismatch')
    for parent in range(m): audit.mother({k:mothers[k][parent] for k in ('product_id','family_id','u_date')},int(counts[parent,0]))
    summary=json.loads(read_bound(artifact('summary.json')))
    for name,key in [('all',('all','global','all')),('post2020',('2020onward','global','all'))]:
        compare_stats(summary['scopes'][name],stats_expected(audit,key,True),'scopes/'+name)
        if audit.counts[key]['primary_domain_count']!=protocol['expected_primary'][name]: raise ValueError('accepted_primary_count_changed')
    for dimension in ('year','family','product'):
        groups=sorted({mothers['u_date'][i][:4] if dimension=='year' else mothers[dimension+'_id'][i] for i in range(m)})
        if set(summary['partitions'][dimension])!=set(groups): raise ValueError('fixed_partition_domain_changed '+dimension)
        for group in groups:
            compare_stats(summary['partitions'][dimension][group],stats_expected(audit,('all',dimension,group),False),dimension+'/'+group)
    clock_summary=json.loads(read_bound(protocol['input_bindings']['clock_summary227']))
    for scope in ('all','2020onward'):
        c=audit.counts[(scope,'global','all')]
        for timing in classifier.TIMING_STATES:
            name='primary_timing_'+timing+'_count'
            if c[name]!=clock_summary['scopes'][scope][name]: raise ValueError('accepted227_primary_timing_changed '+scope+'/'+timing)
    nanchors=min(16,len(quote_sequence));positions=[i*(len(quote_sequence)-1)//(nanchors-1) for i in range(nanchors)] if nanchors>1 else [0]
    anchors=json.loads(read_bound(artifact('anchors.json')))
    if isinstance(anchors,dict): anchors=anchors['anchors']
    if len(anchors)!=nanchors: raise ValueError('mechanical_anchor_count')
    for anchor,pos in zip(anchors,positions):
        expected=evidence[quote_sequence[pos]]
        for k,v in anchor.items():
            if k not in expected: continue
            if isinstance(v,(int,float)): close(expected[k],v,'anchor/'+k)
            else: equal_token(expected[k],v,'anchor/'+k)
        if integer(anchor['sequence_index'])!=quote_sequence[pos]: raise ValueError('mechanical_anchor_position')
    return dict(action_rows=rows,mother_rows=m,nochild_mothers=nochild,K_quote_actions=len(evidence),
                K_quote_costs=2*len(evidence),all_new_K_points_independently_checked=True,
                all_new_labels_null_copy_clocks_counts_checked=True,all_fixed_summary_partitions_checked=True,
                mechanical_anchors=nanchors,core_findings=dict(P0=0,P1=0,P2=0),
                cache_before=before,cache_after=after,calendar_reads=1,native_npz_opens=1,native_members_loaded=list(protocol['native_members']),
                old_actions_reads=0,old_mothers_reads=0,old_clock_projection_reads=0,old_price_cleaning_reaudit=False,
                original_path_replays=0,old_training_cache_reads=0,fit=0,cash=0,SQL=0,
                original_source_authenticity_inherited=True,metadata_non_deriving_flags_not_reaudited=True,
                original_goal_complete=False,alpha_or_production_qualification=False)


def run_actual(args):
    output=Path(args.output).resolve();actual=Path(args.actual_dir).resolve()
    if output!=OUTPUT or output.exists() or actual!=ACTUAL: raise ValueError('exact_fresh_actual_paths_required')
    pb=binding(PROTOCOL)
    if pb['sha256']!=PROTOCOL_SHA: raise ValueError('frozen230_changed')
    protocol=json.loads(read_bound(pb));ab=binding(args.authorization)
    if ab['sha256']!=args.authorization_sha256: raise ValueError('root_authorization_SHA_changed')
    auth=json.loads(read_bound(ab));mb=binding(actual/'manifest.json')
    needed=dict(schema='stage234_exact_root_review_authorization_v1',authorized_by='root',exact_source_authorized=True,
                protocol_sha256=PROTOCOL_SHA,actual_dir=str(actual),output=str(output))
    if any(auth.get(k)!=v for k,v in needed.items()) or auth.get('source_bundle')!=source_bundle() or auth.get('actual_manifest')!=mb:
        raise ValueError('exact_root_review_authorization_changed')
    manifest=json.loads(read_bound(mb));output.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    write(output/'started.json',dict(status='started',protocol=pb,authorization=ab,actual_manifest=mb,source_bundle=source_bundle(),
                                   automatic_retry=False,started_at=datetime.now(timezone.utc).isoformat()))
    try:
        report=review_new_outputs(protocol,manifest,actual)
        report.update(status='completed',schema='stage234_K_payoff_independent_review_v1',actual_manifest=mb,
                      protocol=pb,source_bundle=source_bundle(),elapsed_seconds=time.monotonic()-started)
        write(output/'receipt.json',report)
        terminal=dict(status='completed',exit_code=0,elapsed_seconds=time.monotonic()-started)
    except Exception as exc:
        terminal=dict(status='failed',exit_code=1,error_type=type(exc).__name__,error=str(exc),elapsed_seconds=time.monotonic()-started)
        write(output/'terminal.json',terminal);raise
    write(output/'terminal.json',terminal)
    write(output/'manifest.json',dict(schema='stage234_K_payoff_review_manifest_v1',status='completed',actual_manifest=mb,
          artifacts={name:binding(output/name) for name in ('receipt.json','terminal.json','started.json')}))
    print(json.dumps(terminal),flush=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--actual-dir',required=True);parser.add_argument('--authorization',required=True)
    parser.add_argument('--authorization-sha256',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    run_actual(args)


if __name__=='__main__': main()
