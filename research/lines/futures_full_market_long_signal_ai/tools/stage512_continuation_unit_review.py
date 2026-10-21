"""Independent continuation construction review; no author imports or import I/O.

The actual adapter is intentionally absent until the Stage511 schema is final.
Pure helpers and short-range NPY reads can be tested with newly made toy files.
No historic payload is opened by importing or running the toy tests.
"""
from __future__ import annotations

import ast
import bisect
from collections import Counter, defaultdict
import csv
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import time
import zipfile
import numpy as np


def close(a, b, label, *, atol=1e-9, rtol=1e-12):
    if a is None or b is None:
        if a is not None or b is not None:
            raise AssertionError((label, a, b))
    elif not (math.isfinite(float(a)) and math.isfinite(float(b))
              and math.isclose(float(a), float(b), abs_tol=atol, rel_tol=rtol)):
        raise AssertionError((label, a, b))


def nominal_K(epoch, dates):
    suffix = epoch.rsplit('.', 1)[1]
    if len(suffix) != 6 or not suffix.isdigit() or not 1 <= int(suffix[4:]) <= 12:
        raise AssertionError('bad complete month')
    y, m = int(suffix[:4]), int(suffix[4:])
    first = (y - 1, 12) if m == 1 else (y, m - 1)
    target = '%04d-%02d-01' % first
    if target < dates[0]:
        return target, None, None, 'before_calendar_blocked'
    j = bisect.bisect_left(dates, target)
    return ((target, None, None, 'after_calendar_pending') if j == len(dates)
            else (target, j, dates[j], 'in_calendar'))


def expected_force(anchor, canonical, tomorrow, deadline, previous):
    if tomorrow >= deadline:
        return 'lifecycle_exit'
    if previous:
        return previous
    if not canonical:
        return 'observation_exit_requested'
    return 'liquidity_reference_changed' if canonical != anchor else None


def independent_quote(reference, econ, scenario, side='SELL'):
    """Separately written original042 cost arithmetic; no author call."""
    if scenario not in ('base', 'stress') or side not in ('BUY', 'SELL'):
        raise AssertionError('unknown scenario/side')
    def pos(x):
        try:
            return math.isfinite(float(x)) and float(x) > 0
        except (TypeError, ValueError):
            return False
    if not pos(reference):
        return 'reference_unknown_or_nonpositive', None, None, None
    mult = econ.get('contract_multiplier')
    if not pos(mult):
        return 'multiplier_unknown_or_nonpositive', None, None, None
    n = 1 if scenario == 'base' else 3
    rate = Decimal('0.0001') * n
    r = Decimal(str(reference))
    movement = abs(r) * rate
    tick = econ.get('tick_size')
    if pos(tick):
        step = Decimal(str(tick))
        movement = max(movement, step * n)
    q = r - movement if side == 'SELL' else r + movement
    if pos(tick):
        q = (q / step).to_integral_value(rounding=ROUND_FLOOR if side == 'SELL'
                                        else ROUND_CEILING) * step
    q = float(q)
    if not pos(q):
        return 'nonpositive_adverse_fill', None, None, None
    fee = max(2.0 * n, abs(q) * float(mult) * float(rate))
    slip = abs(q - float(reference)) * float(mult)
    return 'observed_research_quote', q, fee, slip


def validate_states(path, states, terminal, end_index):
    """Normalized path/state rows; checks causal cash mechanics, not native map.

    terminal is a label-only record with ``bar`` and new mechanics exit fields.
    All source bars are supplied by new output; bounded native anchors certify
    only a declared subset of those mappings in a later authorized actual run.
    """
    entered = path['participation_state'] == 'entered'
    if not entered:
        if states or path.get('entry_index') is not None:
            raise AssertionError('nonentered path has states/entry')
        return dict(states=0, riskset=0, stale=0, force=0)
    D = path['u_index'] + 1
    if path['entry_index'] != D or not path['u_action_eligible']:
        raise AssertionError('entry clock/prospective eligibility')
    F, sl = path['entry_reference'], path['SL0']
    close(sl, F - .25 * path['N_u'], 'SL0')
    if 'R0' in path:close(path['R0'],.25*path['N_u'],'R0')
    if F <= path['low20_u'] or sl <= 0:
        raise AssertionError('stale/invalid entry not cancelled')
    boundary, mark, previous_force = max(sl, path['low20_u']), F, None
    stale, deferred = 0, False
    totals = Counter(states=0, riskset=0, stale=0, force=0)
    for n, s in enumerate(states):
        t = D + n
        if s['t_index'] != t:
            raise AssertionError('state calendar chain skips/reorders')
        for key, value in [('entry_index', D), ('entry_reference', F),
                           ('N_u', path['N_u']), ('SL0', sl)]:
            close(s[key], value, key)
        close(s['boundary_in'], boundary, 'incoming boundary')
        if 'force_in' in s and (s['force_in'] or None)!=previous_force:
            raise AssertionError('incoming force state')
        if 'deferred_in' in s and bool(s['deferred_in'])!=deferred:
            raise AssertionError('incoming deferred state')
        if 'previous_mark' in s:
            close(s['previous_mark'], mark, 'previous mark')
        if s['age_source_days'] != t - D + 1:
            raise AssertionError('age uses wrong clock')
        if s['current_native_valid']:
            if deferred or previous_force:
                raise AssertionError('valid bar after pending force survived')
            if s['open'] <= boundary or s['low'] <= boundary:
                raise AssertionError('stop-hit bar survived')
            if 'u_close' in path:
                close(s['previous_close'],path['u_close'] if n==0 else mark,
                      'strict previous-calendar close')
            mark, stale = s['close'], 0
            boundary = max(sl, s['low20_t'])
            previous_force = expected_force(path['anchor_epoch'],
                s['canonical_reference'], t + 1,
                path['effective_lifecycle_index'], previous_force)
            if s['mark_state'] != 'native_close':
                raise AssertionError('valid state not native_close')
        else:
            stale += 1
            deferred, previous_force = True, 'research_deferred_liquidation'
            if s['mark_state'] != 'stale':
                raise AssertionError('missing native state not stale')
            if any(s.get(k) is not None for k in ('open','high','low','close','volume')):
                raise AssertionError('missing quote replaced by numeric price')
        close(s['mark'], mark, 'current mark')
        close(s['boundary_next'], boundary, 'next own boundary')
        if (s['stale_days'] != stale or bool(s['deferred']) != deferred
                or (s['force_next'] or None) != previous_force):
            raise AssertionError('stale/deferred/force chain')
        risk = int(bool(s['current_native_valid']) and not previous_force)
        if s['riskset'] != risk:
            raise AssertionError('causal risk set differs')
        if s['next_planned_index'] != t + 1:
            raise AssertionError('wrong prospective next date')
        totals.update(states=1,riskset=risk,stale=int(not s['current_native_valid']),
                      force=int(bool(previous_force)))
    for key, name in [('state_count','states'),('riskset_count','riskset'),
                      ('stale_count','stale')]:
        if path[key] != totals[name]:
            raise AssertionError(('path count', key))
    closed = path['terminal_state'] == 'closed_complete_bar_model'
    if closed:
        x = D + len(states)
        if path['exit_index'] != x or terminal is None or terminal.get('bar') is None:
            raise AssertionError('terminal clock/bar')
        bar = terminal['bar']
        if deferred or previous_force:
            expected_price = bar['open']
            reason = 'research_deferred_liquidation' if deferred else previous_force
        elif bar['open'] <= boundary:
            expected_price, reason = bar['open'], 'gap_stop'
        elif bar['low'] <= boundary:
            expected_price, reason = boundary, 'stop_boundary'
        else:
            raise AssertionError('baseline closed without exit trigger')
        close(path['exit_reference'], expected_price, 'terminal reference')
        if path['terminal_reason'] != reason:
            raise AssertionError('terminal reason/priority')
        if 'exit_available_phase' in path and path['exit_available_phase']!=(
                'intraday' if reason=='stop_boundary' else 'open'):
            raise AssertionError('terminal available phase')
    else:
        expected_state = 'stale_open_unresolved' if deferred else 'open_right_censored'
        if (path['terminal_state'] != expected_state or not states
                or states[-1]['t_index'] != end_index
                or path.get('exit_index') is not None
                or path.get('exit_reference') is not None):
            raise AssertionError('unresolved path became zero/closed')
    return dict(totals)


def expected_voluntary(states, terminal_index=None, terminal_open=None):
    """Independent reverse nearest-valid-open algorithm on new state chains."""
    next_day, next_open = terminal_index, terminal_open
    expected = {}
    for s in reversed(states):
        if s['riskset']:
            expected[s['t_index']] = (next_day, next_open)
        if s['current_native_valid']:
            next_day, next_open = s['t_index'], s['open']
    return expected


class StoredNativeRanges:
    """Bounded element reads from uncompressed132 .npz, no full-array load.

    Opening reads only ZIP directory and NPY headers. Every direct payload range
    is logged with offset/bytes. Caller supplies explicit max payload byte budget.
    No digest of the110MB payload is attempted; provenance remains inherited.
    """
    def __init__(self, path, *, max_bytes=250000):
        self.path = Path(path)
        self.max_bytes, self.bytes_read, self.ranges = max_bytes, 0, []
        self.stat_before = self.path.stat()
        self.stream = self.path.open('rb')
        self.arrays = {}
        class DirectoryView:
            def __init__(self,owner):self.owner=owner
            def seek(self,*args):return self.owner.stream.seek(*args)
            def tell(self):return self.owner.stream.tell()
            def seekable(self):return True
            def read(self,n=-1):
                offset=self.tell()
                if n<0:n=self.owner.stat_before.st_size-offset
                return self.owner._read(offset,n,'zip_directory')
        with zipfile.ZipFile(DirectoryView(self)) as archive:
            for z in archive.infolist():
                if z.compress_type != zipfile.ZIP_STORED or z.flag_bits & 1:
                    self.stream.close()
                    raise AssertionError('only unencrypted ZIP_STORED supported')
                raw = self._read(z.header_offset, 30, 'zip_local_header')
                values = struct.unpack('<IHHHHHIIIHH', raw)
                if values[0] != 0x04034b50:
                    raise AssertionError('invalid ZIP local header')
                start = z.header_offset + 30 + values[-2] + values[-1]
                magic = self._read(start,8,'npy_magic')
                if magic[:6] != b'\x93NUMPY' or magic[6] not in (1,2,3):
                    raise AssertionError('unsupported NPY magic/version')
                nlen = 2 if magic[6] == 1 else 4
                n = int.from_bytes(self._read(start+8,nlen,'npy_header_len'),'little')
                if n>10000:
                    raise AssertionError('oversize NPY metadata')
                h = ast.literal_eval(self._read(start+8+nlen,n,'npy_header').decode('latin1'))
                dtype = np.dtype(h['descr'])
                if h['fortran_order'] or dtype.hasobject:
                    raise AssertionError('non-flat/object payload not permitted')
                self.arrays[z.filename.removesuffix('.npy')] = dict(
                    offset=start+8+nlen+n,dtype=dtype,shape=h['shape'])

    def _read(self, offset, n, purpose):
        if n<0 or self.bytes_read+n > self.max_bytes:
            raise AssertionError('native anchor byte budget exceeded')
        self.stream.seek(offset)
        b = self.stream.read(n)
        if len(b) != n:
            raise AssertionError('short range read')
        self.bytes_read += n
        self.ranges.append(dict(offset=offset,bytes=n,purpose=purpose))
        return b

    def row(self, key, index):
        a = self.arrays[key]
        if not 0<=index<a['shape'][0]:
            raise AssertionError('range row outside member')
        width = math.prod(a['shape'][1:]) or 1
        data = self._read(a['offset']+index*width*a['dtype'].itemsize,
                          width*a['dtype'].itemsize,'row:'+key)
        result = np.frombuffer(data,dtype=a['dtype']).copy()
        return result[0].item() if width==1 else result

    def epoch_bounds(self, epoch):
        lo, hi = 0, self.arrays['epochs']['shape'][0]
        while lo<hi:
            mid = (lo+hi)//2
            if self.row('epochs',mid)<epoch:
                lo=mid+1
            else:
                hi=mid
        if lo>=self.arrays['epochs']['shape'][0] or self.row('epochs',lo)!=epoch:
            raise AssertionError('anchor epoch absent')
        return int(self.row('offsets',lo)),int(self.row('offsets',lo+1))

    def day_row(self, epoch, day, fields=('values','valid','N','low20','run')):
        lo,hi = self.epoch_bounds(epoch)
        finish=hi
        while lo<hi:
            mid=(lo+hi)//2
            if self.row('days',mid)<day:
                lo=mid+1
            else:
                hi=mid
        if lo>=finish or self.row('days',lo)!=day:
            return None
        return {key:self.row(key,lo) for key in fields}

    def close(self):
        self.stream.close()
        after=self.path.stat()
        if (after.st_size,after.st_mtime_ns,after.st_ino)!=(
                self.stat_before.st_size,self.stat_before.st_mtime_ns,self.stat_before.st_ino):
            raise AssertionError('native file changed during anchor reads')


def normalized(raw):
    row={}
    for key,value in raw.items():
        if value=='':
            row[key]=None
        else:
            try:
                number=float(value)
            except (ValueError,TypeError):
                row[key]=value
            else:
                if not math.isfinite(number):
                    raise AssertionError(('nonfinite exported numeric',key,value))
                row[key]=int(number) if number.is_integer() else number
    return row


def file_binding(path):
    p=Path(path);data=p.read_bytes()
    return dict(path=str(p.resolve()),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def small_json(binding,cap=2000000):
    if binding['bytes']>cap or file_binding(binding['path'])!={
            key:binding[key] for key in ('path','bytes','sha256')}:
        raise AssertionError('small exact binding mismatch')
    return json.loads(Path(binding['path']).read_text())


def write_json(path,value):
    with Path(path).open('x') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False)
        f.write('\n')


class HashInput(io.RawIOBase):
    def __init__(self,path):
        self.f=Path(path).open('rb');self.n=0;self.h=hashlib.sha256()
    def readable(self):return True
    def readinto(self,buffer):
        n=self.f.readinto(buffer)
        if n:self.h.update(memoryview(buffer)[:n]);self.n+=n
        return n
    def close(self):
        self.f.close();super().close()


class OnceTable:
    def __init__(self,binding):
        self.binding=binding
        self.raw=HashInput(binding['path'])
        self.text=io.TextIOWrapper(gzip.GzipFile(fileobj=io.BufferedReader(self.raw)),newline='')
        self.reader=csv.DictReader(self.text);self.fields=self.reader.fieldnames
        self.pending=None;self.eof=False;self.rows=0
    def pop(self):
        if self.pending is not None:
            r=self.pending;self.pending=None;return r
        if self.eof:return None
        try:r=normalized(next(self.reader))
        except StopIteration:self.eof=True;return None
        self.rows+=1;return r
    def group(self,sequence):
        rows=[]
        while (r:=self.pop()) is not None:
            if r['sequence_index']<sequence:
                raise AssertionError('unordered/extra output group')
            if r['sequence_index']>sequence:
                self.pending=r;break
            rows.append(r)
        return rows
    def finish(self):
        if self.pop() is not None:raise AssertionError('unconsumed output rows')
        if (self.raw.n!=self.binding['bytes']
                or self.raw.h.hexdigest()!=self.binding['sha256']):
            raise AssertionError('new output stream exact hash differs')
        result=dict(self.binding,rows=self.rows,streams=1)
        self.text.close();return result


def check_observation_quote(row,prefix,reference,econ,side):
    for cost in ('base','stress'):
        want=independent_quote(reference,econ,cost,side)
        actual=row[cost+'_'+prefix+'_quote_state']
        if actual!=want[0]:raise AssertionError(('quote status',prefix,actual,want))
        for suffix,value in zip(('fill_price','fee_per_lot','slippage_per_lot'),want[1:]):
            close(row[cost+'_'+prefix+'_'+suffix],value,'quote '+suffix)
        tick=econ.get('tick_size')
        positive_tick=tick is not None and math.isfinite(float(tick)) and float(tick)>0
        if row[cost+'_'+prefix+'_tickized']!=int(positive_tick):
            raise AssertionError('tickized flag')


def cash_capacity(volume,lot):
    if volume is None or volume<0 or lot is None or lot<=0 or int(lot)!=lot:
        return None,None,'execution_capacity_unknown'
    gross=int((Decimal(str(volume))/Decimal(100)/Decimal(str(lot))).to_integral_value(
              rounding=ROUND_FLOOR))*int(lot)
    entry=(gross//(2*int(lot)))*int(lot)
    return gross,entry,'known_roundtrip_capacity' if entry>=lot else 'capacity_below_one_roundtrip'


def metadata_lifecycle(epoch,econ,calendar):
    suffix=epoch.rsplit('.',1)[1]
    possible=[suffix[:4]+'-'+suffix[4:]+'-01']
    for key in ('known_lifecycle_exit_boundary','nominal_month_first_date',
                'maturity_date','de_listed_date'):
        value=econ.get(key)
        if isinstance(value,str) and len(value)>=10 and value[:10]>='1900-01-01':
            possible.append(value[:10])
    target=min(possible)
    return bisect.bisect_left(calendar,target),target


def compare_identity(row,path):
    for name in ('sequence_index','action_id','product_id','family_id','reference_epoch'):
        if row[name]!=path[name]:raise AssertionError(('observation identity',name))


def run_review(manifest_binding,protocol_binding,authorization,output):
    """One new-five-table stream; small metadata and <=12 native range anchors.

    Root must bind completed511 manifest, reviewer source, protocol and output.
    This is never a second complete read of466 metadata/mothers or132 arrays.
    """
    start=time.monotonic();out=Path(output);out.mkdir(exist_ok=False)
    write_json(out/'started.json',dict(started_at=datetime.now(timezone.utc).isoformat(),
                                    automatic_retry=False,fit=0,cash=0,SQL=0))
    phase='binding';tables={};read_receipts={}
    try:
        if not authorization.get('root_authorized'):
            raise AssertionError('root authorization required')
        for key,want in [('manifest',manifest_binding),('protocol',protocol_binding)]:
            if authorization[key]!=want:raise AssertionError(('authorization input',key))
        if authorization['output']!=str(out.resolve()):raise AssertionError('output authorization')
        if authorization['reviewer_source']!=file_binding(__file__):
            raise AssertionError('reviewer source authorization')
        manifest=small_json(manifest_binding);protocol=small_json(protocol_binding)
        if manifest['status']!='completed' or manifest['protocol_binding']!=protocol_binding:
            raise AssertionError('completed exact511 input required')
        summary=small_json(manifest['artifacts']['summary'])
        expected_budget=dict(new_table_streams=5,native_max_anchors=12,economics_reads=1,
                             calendar_reads=1,old_metadata_reads=0,old_mother_reads=0,
                             native_full_array_reads=0,fit=0,cash=0,SQL=0)
        if authorization['budget']!=expected_budget:raise AssertionError('fixed review budget')
        inputs=protocol['inputs']
        for role in ('calendar','economics'):
            b=inputs[role];raw=Path(b['path']).read_bytes()
            if len(raw)!=b['bytes'] or hashlib.sha256(raw).hexdigest()!=b['sha256']:
                raise AssertionError(('small metadata exact binding',role))
            if role=='economics':economics=json.loads(raw)['instruments']
            else:
                a=np.load(io.BytesIO(raw),allow_pickle=False)
                calendar=([str(int(v))[:4]+'-'+str(int(v))[4:6]+'-'+str(int(v))[6:]
                           for v in a] if a.dtype.kind in 'iu'
                          else a.astype('datetime64[D]').astype(str).tolist())
            read_receipts[role]=dict(b,reads=1)
        end=calendar.index(protocol['sample_end'])
        roles=('mother_domain','action_path_summary','unit_states',
               'baseline_terminal_observations','voluntary_exit_observations')
        tables={role:OnceTable(manifest['artifacts'][role]) for role in roles}
        forbidden=('exit_index','exit_date','exit_reference','terminal_state','terminal_reason',
                   'available_at','available_phase','reference','first_legal_open')
        if set(forbidden)&set(tables['unit_states'].fields):
            raise AssertionError('future observation column in causal states')
        phase='mother_domain';mothers=[];canonical=defaultdict(dict);products=set();families=set();exchanges=set()
        while (r:=tables['mother_domain'].pop()) is not None:
            if r['sequence_index']!=len(mothers) or r['u_date']!=calendar[r['u_index']]:
                raise AssertionError('full mother sequence/calendar')
            if r['family_id']!=r['product_id'].removesuffix('_F'):
                raise AssertionError('mother F family')
            if r['u_index'] in canonical[r['product_id']]:raise AssertionError('duplicate mother')
            canonical[r['product_id']][r['u_index']]=r['reference_epoch'] or ''
            mothers.append(r);products.add(r['product_id']);families.add(r['family_id'])
            exchanges.add(r['product_id'].split('.')[0])
        read_receipts['mother_domain']=tables['mother_domain'].finish()
        domain=protocol['domain']
        if (len(mothers),len(products),len(families),len(exchanges),sum(r['nochild'] for r in mothers))!=(
                domain['mothers'],domain['policy_products'],domain['policy_families'],
                domain['exchanges'],domain['no_child_mothers']):
            raise AssertionError('canonical domain narrowed')
        write_json(out/'mother_phase.json',dict(status='passed',mothers=len(mothers),
                                               products=sorted(products),families=sorted(families)))
        child=np.zeros(len(mothers),dtype=np.int64);eligible_child=child.copy()
        counts=Counter();participation=Counter();terminal_counts=Counter();forces=Counter();quote_status=Counter()
        child_products=set();child_families=set();cohorts=defaultdict(Counter)
        cohort_dates=defaultdict(set);family_days=defaultdict(set);anchors={}
        phase='single_joint_path_states_observations_stream'
        while (p:=tables['action_path_summary'].pop()) is not None:
            seq=p['sequence_index'];u=p['u_index'];D=u+1
            if seq!=counts['actions'] or p['D_index']!=D or p['u_date']!=calendar[u]:
                raise AssertionError('complete action ordering/calendar')
            parent=mothers[p['mother_sequence_index']]
            for x,y in [('mother_event_id','event_id'),('product_id','product_id'),
                        ('family_id','family_id'),('u_date','u_date'),('u_index','u_index'),
                        ('anchor_epoch','reference_epoch'),('family_hash_group','family_hash_group')]:
                if (p[x] or '')!=(parent[y] or ''):raise AssertionError(('mother relationship',x))
            g=int(hashlib.sha256(p['family_id'].encode()).hexdigest(),16)%2
            if p['family_hash_group']!=g:raise AssertionError('independent family split')
            if p['reference_epoch'].rsplit('.',1)[0]!=p['product_id']:
                raise AssertionError('action epoch/product')
            e=economics.get(p['reference_epoch'],{})
            life,target=metadata_lifecycle(p['reference_epoch'],e,calendar)
            ktarget,k,kday,kstate=nominal_K(p['reference_epoch'],calendar)
            if (p['source_lifecycle_index'],p['source_lifecycle_target_date'])!=(life,target):
                raise AssertionError('source lifecycle projection')
            if (p['K_target_date'],p['K_index'],p['K_date'],p['K_state'])!=(ktarget,k,kday,kstate):
                raise AssertionError('independent original commonK')
            eff=min(life,k) if k is not None else life
            if p['effective_lifecycle_index']!=eff:raise AssertionError('effective commonK boundary')
            eligible=p['u_action_eligible']
            if eligible not in (0,1) or bool(p['u_ineligibility_reason'])==bool(eligible):
                raise AssertionError('prospective eligibility reasons')
            if not eligible and p['participation_state']!='u_ineligible':raise AssertionError('u gate')
            if eligible and (kstate=='before_calendar_blocked' or k is not None and D>=k):
                if p['participation_state']!='D_not_before_K':raise AssertionError('D<K gate')
            states=tables['unit_states'].group(seq)
            baselines=tables['baseline_terminal_observations'].group(seq)
            observations=tables['voluntary_exit_observations'].group(seq)
            entered=p['participation_state']=='entered'
            counts['entered_paths']+=int(entered)
            counts['same_day_entry_exit_paths']+=int(entered and p['entry_index']==p['exit_index'])
            counts['entered_paths_with_any_riskset']+=int(entered and p['riskset_count']>0)
            if len(baselines)!=int(entered):raise AssertionError('baseline terminal full entered domain')
            baseline=baselines[0] if entered else None
            terminal_record=None
            if baseline:
                compare_identity(baseline,p)
                for field in ('entry_index','entry_date','entry_reference','terminal_state',
                              'terminal_reason','exit_index','exit_date','exit_reference'):
                    if baseline[field]!=p[field]:raise AssertionError(('terminal linkage',field))
                if baseline['available_at']!=p['exit_date'] or baseline['available_phase']!=p['exit_available_phase']:
                    raise AssertionError('baseline availability clock')
                terminal_record=dict(bar=None if not baseline['terminal_bar_valid'] else
                    {field:baseline['terminal_bar_'+field] for field in ('open','high','low','close','volume')})
                for prefix,ref,side in [('entry_BUY',p['entry_reference'],'BUY'),
                                      ('entry_SELL_estimate',p['entry_reference'],'SELL'),
                                      ('terminal_SELL',p['exit_reference'],'SELL')]:
                    check_observation_quote(baseline,prefix,ref,e,side)
            totals=validate_states(p,states,terminal_record,end)
            if not entered and (observations or states):raise AssertionError('nonentered generated risk set')
            nearest=expected_voluntary(states,p['exit_index'],
                None if not baseline or not baseline['terminal_bar_valid'] else baseline['terminal_bar_open'])
            if len(observations)!=len(nearest):raise AssertionError('voluntary not exactly causal risk set')
            for state in states:
                compare_identity(state,p);t=state['t_index']
                if state['t_date']!=calendar[t] or state['next_planned_date']!=(calendar[t+1] if t+1<len(calendar) else None):
                    raise AssertionError('state calendar clock')
                if (state['canonical_reference'] or '')!=canonical[p['product_id']].get(t,''):
                    raise AssertionError('current canonical reference')
                gross,cap,cstate=cash_capacity(state['volume'],e.get('round_lot'))
                if (state['current_gross_capacity_qty'],state['current_next_entry_capacity_qty'],
                    state['current_capacity_state'])!=(gross,cap,cstate):
                    raise AssertionError('current known volume capacity')
                complete=int(all(state[f] is not None for f in
                    ('close','N_t','low20_t','previous_close','SL0','R0','boundary_next')))
                if state['state_values_complete']!=complete:raise AssertionError('state completeness mask')
                forces[state['force_next'] or 'free_choice']+=1
            seen_t=set()
            for observation in observations:
                compare_identity(observation,p);t=observation['t_index']
                if t in seen_t or t not in nearest:raise AssertionError('voluntary duplicate/nonriskset')
                seen_t.add(t);day,price=nearest[t]
                if observation['planned_index']!=t+1 or observation['exit_index']!=day:
                    raise AssertionError('first legal execution clock')
                close(observation['reference'],price,'voluntary first legal open price')
                want_state=('pending_no_legal_open' if day is None else 'observed_next_open'
                            if day==t+1 else 'observed_deferred_first_legal_open')
                if observation['state']!=want_state:raise AssertionError('voluntary availability status')
                if (observation['available_at']!=(calendar[day] if day is not None else None)
                        or observation['available_phase']!=('open' if day is not None else None)):
                    raise AssertionError('voluntary quote becomes known at wrong clock')
                check_observation_quote(observation,'SELL',price,e,'SELL')
                for cost in ('base','stress'):
                    quote_status[cost+':voluntary:'+observation[cost+'_SELL_quote_state']]+=1
            for cutoff in protocol['cutoffs']:
                if p['u_date']>=cutoff or kday is None or kday>=cutoff:continue
                for scope in ('main','holdout_0','holdout_1'):
                    if scope!='main' and g==int(scope[-1]):continue
                    key=(cutoff,scope);c=cohorts[key]
                    c['all_cohort_actions']+=1;c['u_eligible_actions']+=eligible
                    c['participation:'+p['participation_state']]+=1
                    for state in states:
                        if state['t_date']>=cutoff:continue
                        c['held_close_states']+=1;c['decision_states']+=state['riskset']
                        c['stale_states']+=int(state['mark_state']=='stale')
                        c['mandatory_states']+=int(bool(state['force_next']))
                        if state['riskset']:
                            cohort_dates[key].add(state['t_date'])
                            family_days[key].add((p['family_id'],state['t_date']))
                    for observation in observations:
                        if observation['t_date']>=cutoff:continue
                        known=(p['exit_date'] is not None and p['exit_date']<cutoff
                               and observation['exit_date'] is not None and observation['exit_date']<cutoff)
                        for cost in ('base','stress'):
                            good=(known and observation[cost+'_SELL_quote_state']=='observed_research_quote'
                                  and baseline[cost+'_terminal_SELL_quote_state']=='observed_research_quote')
                            c[cost+':paired_exit_price_quote_known' if good else
                              cost+':paired_exit_price_quote_unknown']+=1
            counts.update(actions=1,states=totals['states'],riskset=totals['riskset'],stale=totals['stale'])
            participation[p['participation_state']]+=1;terminal_counts[p['terminal_state']]+=1
            child[p['mother_sequence_index']]+=1;eligible_child[p['mother_sequence_index']]+=eligible
            child_products.add(p['product_id']);child_families.add(p['family_id'])
            if entered and states:
                exchange=p['product_id'].split('.')[0]
                candidate=dict(path=dict(p),state=dict(next((s for s in reversed(states) if s['deferred']),
                    next((s for s in reversed(states) if s['force_next']),states[-1]))),
                    baseline=dict(baseline),first_state=dict(states[0]),
                    priority=(int(totals['stale']>0),int(totals['force']>0),u,seq))
                anchors.setdefault((exchange,'earliest'),candidate)
                old=anchors.get((exchange,'mechanism_then_latest'))
                if old is None or candidate['priority']>old['priority']:
                    anchors[(exchange,'mechanism_then_latest')]=candidate
            if counts['actions']%100000==0:
                write_json(out/('progress_%07d.json'%counts['actions']),
                           dict(counts,elapsed_seconds=time.monotonic()-start))
                print(json.dumps(dict(counts,phase=phase)),flush=True)
        for role in roles[1:]:read_receipts[role]=tables[role].finish()
        if (counts['actions'],len(child_products),len(child_families))!=(
                domain['actions'],domain['observed_child_products'],domain['observed_child_families']):
            raise AssertionError('full observed action domain')
        for i,r in enumerate(mothers):
            if (child[i],eligible_child[i])!=(r['child_count'],r['eligible_child_count']):
                raise AssertionError('independent mother child conservation')
            if (r['observed_child_count'],r['observed_eligible_child_count'])!=(int(child[i]),int(eligible_child[i])):
                raise AssertionError('reported mother child conservation')
        report=[]
        for row in summary['cohort_support']:
            key=(row['cutoff'],row['scope']);actual=dict(cohorts[key])
            if (actual!=row['counts'] or len(cohort_dates[key])!=row['distinct_decision_dates']
                    or len(family_days[key])!=row['distinct_family_days']):
                raise AssertionError(('six independent cohorts',key))
            report.append(dict(cutoff=key[0],scope=key[1],counts=actual,
                               distinct_decision_dates=len(cohort_dates[key]),
                               distinct_family_days=len(family_days[key])))
        for actual,want,name in [(dict(participation),summary['participation'],'participation'),
                                 (dict(terminal_counts),summary['terminal'],'terminal'),
                                 (dict(forces),summary['force_state_counts'],'force'),
                                 (dict(quote_status),summary['quote_states'],'quote statuses')]:
            if actual!=want:raise AssertionError(('summary counters',name))
        if (counts['states'],counts['riskset'],counts['stale'])!=(summary['held_close_states'],
                summary['decision_riskset_states'],summary['stale_states']):
            raise AssertionError('summary full state totals')
        write_json(out/'new_tables_core_pass.json',dict(status='passed',counts=dict(counts),
                   new_table_read_receipts=read_receipts,cohort_support=report,
                   material_disagreements=0,old_native_array_reloads=0,fit=0,cash=0,SQL=0))
        # Save selections before entering bounded native phase, enabling tail-only
        # recovery without a new sweep if an indexing adapter ever fails.
        write_json(out/'native_anchor_selection.json',dict(
            selection_rule='per exchange first entered-with-state sequence, plus max(stale,force,u,seq); no PnL',
            anchors=[dict(slot=list(key),**value) for key,value in sorted(anchors.items())]))
        phase='bounded_native_anchors';native=StoredNativeRanges(inputs['native_cache']['path'])
        anchor_report=[]
        for key,item in sorted(anchors.items()):
            p=item['path'];s=item['state'];epoch=p['reference_epoch']
            if len(anchor_report)>=12:raise AssertionError('native anchor count exceeded')
            rows={}
            for label,day in [('u',p['u_index']),('entry',p['entry_index']),
                              ('current',s['t_index']),('next',s['t_index']+1),
                              ('terminal',p['exit_index'])]:
                rows[label]=None if day is None else native.day_row(epoch,day)
            own=rows['u']
            if own is None or not own['valid']:raise AssertionError('anchor u native legal map')
            close(p['N_u'],own['N'],'anchor Nu');close(p['low20_u'],own['low20'],'anchor low20u')
            close(p['u_close'],own['values'][3],'anchor uclose')
            close(p['entry_reference'],rows['entry']['values'][0],'anchor entry open')
            current=rows['current'];valid=current is not None and bool(current['valid'])
            if bool(s['current_native_valid'])!=valid:raise AssertionError('anchor current validity')
            if valid:
                for j,field in enumerate(('open','high','low','close','volume')):
                    close(s[field],current['values'][j],'anchor current '+field)
                close(s['N_t'],current['N'],'anchor current N')
                close(s['low20_t'],current['low20'],'anchor current low20')
            if p['exit_index'] is not None:
                terminal=rows['terminal']
                if terminal is None or not terminal['valid']:raise AssertionError('terminal anchor legal')
                for j,field in enumerate(('open','high','low','close','volume')):
                    close(item['baseline']['terminal_bar_'+field],terminal['values'][j],
                          'anchor terminal '+field)
            anchor_report.append(dict(slot=list(key),sequence_index=p['sequence_index'],
                product_id=p['product_id'],u_date=p['u_date'],selected_t=s['t_date'],
                stale=s['deferred'],force=s['force_next'],mapped_rows=list(rows)))
        native.close()
        range_receipt=dict(file=inputs['native_cache'],full_digest_verification=False,
            full_array_loads=0,anchor_count=len(anchor_report),bytes_read=native.bytes_read,
            ranges=native.ranges,anchors=anchor_report,provenance_sha_inherited=True)
        write_json(out/'native_range_anchor_receipt.json',range_receipt)
        receipt=dict(schema='stage512_continuation_independent_review_v1',status='completed',
            completed=True,material_disagreements=0,manifest=manifest_binding,protocol=protocol_binding,
            counts=dict(counts),cohort_support=report,new_table_streams=5,
            old_metadata_reads=0,old_mother_reads=0,native_full_array_reads=0,
            native_range_anchors=len(anchor_report),native_bytes_read=native.bytes_read,
            economics_reads=1,calendar_reads=1,fit=0,cash=0,SQL=0,new_reward_labels=0,
            scope='all new output mechanics/quotes/counts plus12 bounded native mapping anchors; no global PIT/source recertification',
            not_established=['actual account prefix','alpha','higher return/lower drawdown',
                             'uncensored training target','real execution','increased betting'],
            elapsed_seconds=time.monotonic()-start,goal_complete=False,production_qualified=False)
        write_json(out/'review_receipt.json',receipt)
        write_json(out/'terminal.json',dict(status='completed',exit_code=0,
                   elapsed_seconds=time.monotonic()-start,fit=0,cash=0,SQL=0))
        print(json.dumps(dict(status='completed',counts=dict(counts),native_anchors=len(anchor_report))),flush=True)
        return receipt
    except Exception:
        import traceback
        write_json(out/'failed_checkpoint.json',dict(status='failed',phase=phase,
             traceback=traceback.format_exc(),completed_read_receipts=read_receipts,
             automatic_retry=False,fit=0,cash=0,SQL=0))
        write_json(out/'terminal.json',dict(status='failed',exit_code=1,phase=phase,
                   automatic_retry=False,elapsed_seconds=time.monotonic()-start))
        raise


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser()
    for flag in ('manifest','manifest-sha256','protocol','protocol-sha256','authorization','output'):
        parser.add_argument('--'+flag,required=True)
    args=parser.parse_args()
    mb=file_binding(args.manifest);pb=file_binding(args.protocol)
    if mb['sha256']!=args.manifest_sha256 or pb['sha256']!=args.protocol_sha256:
        raise SystemExit('root input SHA mismatch')
    run_review(mb,pb,json.loads(Path(args.authorization).read_text()),args.output)
