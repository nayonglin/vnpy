"""Bounded Stage266 read-only product-day observation export, never a trade/label."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing, contextmanager
from datetime import date, datetime
import csv
import gzip
import hashlib
import io
from itertools import groupby
import json
import math
from pathlib import Path
import re
import sqlite3
import sys
import time

EXCHANGES=frozenset({'SHFE','INE','DCE','CZCE','CFFEX','GFEX'})
VERSION='stage004_product_day_long_v1'
START='2010-01-01'
END='2026-10-16'
FIELDS=['event_id','product_id','exchange','product','u_date','direction','status','candidate_count','rejected_count',
    'reference_epoch','contract_yyyymm','source_symbol','source_id','source_locator','open','high','low','close','volume',
    'close_oi','close_oi_status','open_oi','open_oi_status','legacy108_row_usable','train_eligible',
    'planned_execution_date','execution_day_status','execution_qualification']
BAR_FIELDS=['contract_epoch_id','exchange','product','contract_yyyymm','trade_date','source_symbol','source_id','source_locator',
    'open','high','low','close','volume','close_oi','open_oi','open_oi_status','quality_status','legacy108_row_usable','train_eligible']


def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


def digest(raw):return hashlib.sha256(raw).hexdigest()


def day(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):raise ValueError('date must use YYYY-MM-DD')
    if date.fromisoformat(value).isoformat()!=value:raise ValueError('noncanonical date')
    return value


def calendar_dates(values):
    result=[day(v) for v in values]
    if result!=sorted(set(result)) or not result:raise ValueError('calendar must be nonempty unique increasing source dates')
    return result


def load_calendar(raw):
    # The sole numerical library operation is loading this small bound NPY.
    import numpy as np
    values=np.load(io.BytesIO(raw),allow_pickle=False)
    if values.ndim!=1 or values.dtype.kind not in ('i','u','M'):raise ValueError('calendar requires 1D integers or datetime64')
    result=[]
    for value in values:
        if values.dtype.kind in ('i','u'):
            text=str(int(value))
            if not re.fullmatch(r'\d{8}',text):raise ValueError('invalid calendar YYYYMMDD')
            text=text[:4]+'-'+text[4:6]+'-'+text[6:]
        else:
            text=str(value)
            if len(text)>10 and re.fullmatch(r'T00:00(?::00)?(?:\.0+)?',text[10:]) is None:
                raise ValueError('calendar datetime must be midnight')
            text=text[:10]
        result.append(day(text))
    return calendar_dates(result)


def identity(epoch,exchange,product,month):
    if exchange not in EXCHANGES or not re.fullmatch(r'[A-Z]+(?:_F)?',product):raise ValueError('invalid product identity')
    if not re.fullmatch(r'\d{6}',str(month)) or int(str(month)[:4])<1900 or not 1<=int(str(month)[4:])<=12:
        raise ValueError('invalid delivery identity YYYYMM')
    if epoch!=f'{exchange}.{product}.{month}':raise ValueError('contract epoch identity conflict')
    if product.endswith('_F') and (exchange!='DCE' or product not in {'L_F','PP_F','V_F'}):raise ValueError('unsupported F family identity')
    return f'{exchange}.{product}'


@contextmanager
def open_readonly(path):
    path=Path(path).resolve()
    if not path.is_file():raise FileNotFoundError(path)
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        db.row_factory=sqlite3.Row
        yield db


def finite(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def oi_status(value):
    if value is None:return None,'missing'
    if not finite(value):return None,'nonfinite_or_nonnumeric'
    if value<0:return None,'negative'
    return value,'observed_nonnegative'


def candidate(row):
    reasons=[]
    if row['quality_status']!='accepted':reasons.append('quality_not_accepted')
    prices=[row[f] for f in ('open','high','low','close')]
    if not all(finite(v) and v>0 for v in prices):reasons.append('invalid_ohlc_finite_positive')
    elif row['low']>min(row['open'],row['close']) or row['high']<max(row['open'],row['close']) or row['high']<row['low']:
        reasons.append('invalid_ohlc_geometry')
    if not finite(row['volume']) or row['volume']<=0:reasons.append('volume_not_finite_positive')
    return reasons


def scan_database(db_path,calendar,*,start_date=START,end_date=END,emit,emit_rejected=None):
    cal=calendar_dates(calendar);start_date=day(start_date);end_date=day(end_date)
    if start_date>end_date:raise ValueError('start_date after end_date')
    target=[d for d in cal if start_date<=d<=end_date]
    if not target:raise ValueError('empty source calendar scope')
    target_set=set(target);successor=dict(zip(cal,cal[1:]))
    counts=Counter(source_observation_rows=0,qualified_candidate_rows=0,rejected_rows=0,panel_rows=0,
        observed_long_research_opportunity=0,no_accepted_observation=0)
    product_year=defaultdict(Counter);exchange_year=defaultdict(Counter)
    reject_reasons=Counter();catalog={};roster={}
    with open_readonly(db_path) as db:
        schema={r[1] for r in db.execute('PRAGMA table_info(daily_bars)')}
        if not set(BAR_FIELDS)<=schema:raise ValueError('daily_bars schema missing: '+','.join(sorted(set(BAR_FIELDS)-schema)))
        qmarks=','.join('?' for _ in EXCHANGES);exchanges=sorted(EXCHANGES)
        for raw in db.execute(f'SELECT contract_epoch_id,exchange,product,contract_yyyymm,metadata_status FROM contracts WHERE exchange IN ({qmarks}) ORDER BY contract_epoch_id',exchanges):
            r=dict(raw);epoch=r['contract_epoch_id']
            pid=identity(epoch,r['exchange'],r['product'],r['contract_yyyymm'])
            if epoch in catalog:raise ValueError('duplicate catalog epoch identity')
            catalog[epoch]=pid
            if pid not in roster:
                roster[pid]=dict(product_id=pid,exchange=r['exchange'],product=r['product'],catalog_contract_count=0,
                    source_observation_rows=0,qualified_candidate_rows=0,contracts_with_candidates=set(),
                    first_accepted_observation='',last_accepted_observation='',metadata_statuses=set(),
                    historical_lifecycle_certified=False)
            roster[pid]['catalog_contract_count']+=1;roster[pid]['metadata_statuses'].add(r['metadata_status'] or '')
        if not roster:raise ValueError('no six-exchange catalog products')
        sql=f"SELECT {','.join(BAR_FIELDS)} FROM daily_bars WHERE exchange IN ({qmarks}) AND trade_date>=? AND trade_date<=? ORDER BY exchange,product,trade_date,contract_epoch_id"
        cursor=db.execute(sql,[*exchanges,start_date,end_date])
        groups=iter(groupby(cursor,key=lambda r:(r['exchange']+'.'+r['product'],r['trade_date'])))
        current=next(groups,None)
        for pid in sorted(roster):
            product=roster[pid]
            for u in target:
                key=(pid,u);valid=[];rejected=0;seen=set()
                if current is not None and current[0]<key:raise ValueError('source identity or date outside bound calendar/roster: '+repr(current[0]))
                if current is not None and current[0]==key:
                    for raw in current[1]:
                        r=dict(raw);epoch=r['contract_epoch_id'];day(r['trade_date'])
                        found=identity(epoch,r['exchange'],r['product'],r['contract_yyyymm'])
                        if found!=pid or catalog.get(epoch)!=pid:raise ValueError('stored identity conflicts with catalog')
                        if epoch in seen:raise ValueError('duplicate exact-contract source date')
                        seen.add(epoch);counts['source_observation_rows']+=1;product['source_observation_rows']+=1
                        reasons=candidate(r)
                        if reasons:
                            rejected+=1;counts['rejected_rows']+=1;reject_reasons.update(reasons)
                            if emit_rejected is not None:
                                values={k:(str(v) if isinstance(v,float) and not math.isfinite(v) else v) for k,v in r.items() if k in ('open','high','low','close','volume','close_oi')}
                                emit_rejected(dict(contract_epoch_id=epoch,product_id=pid,u_date=u,source_id=r['source_id'],reasons=';'.join(reasons),raw_values=canonical(values)))
                            continue
                        valid.append(r);counts['qualified_candidate_rows']+=1;product['qualified_candidate_rows']+=1
                        product['contracts_with_candidates'].add(epoch)
                        if not product['first_accepted_observation']:product['first_accepted_observation']=u
                        product['last_accepted_observation']=u
                    current=next(groups,None)
                def ranking(r):
                    oi,_=oi_status(r['close_oi'])
                    return (-r['volume'],oi is None,-oi if oi is not None else 0,r['contract_epoch_id'])
                reference=min(valid,key=ranking) if valid else None
                event_key=dict(version=VERSION,product_id=pid,u_date=u)
                row={f:None for f in FIELDS}
                row.update(event_id=VERSION+'_'+digest(canonical(event_key).encode()),product_id=pid,exchange=product['exchange'],
                    product=product['product'],u_date=u,direction='long',status='observed_long_research_opportunity' if reference else 'no_accepted_observation',
                    candidate_count=len(valid),rejected_count=rejected,reference_epoch='',contract_yyyymm='',source_symbol='',source_id='',source_locator='',
                    open_oi_status='',close_oi_status='no_reference',planned_execution_date=successor.get(u,''),
                    execution_day_status='calendar_successor_known' if u in successor else 'execution_day_unknown',execution_qualification='not_assessed')
                if reference:
                    for f in ('contract_yyyymm','source_symbol','source_id','source_locator','open','high','low','close','volume','open_oi_status','legacy108_row_usable','train_eligible'):
                        row[f]=reference[f]
                    row['open_oi']=reference['open_oi'] if finite(reference['open_oi']) else None
                    row['close_oi'],row['close_oi_status']=oi_status(reference['close_oi'])
                    row['reference_epoch']=reference['contract_epoch_id']
                    assert catalog[row['reference_epoch']]==pid and reference['trade_date']==u
                emit(row);counts['panel_rows']+=1;counts[row['status']]+=1
                for table,groupkey in ((product_year,(pid,u[:4])),(exchange_year,(product['exchange'],u[:4]))):
                    table[groupkey]['panel_rows']+=1;table[groupkey][row['status']]+=1
        if current is not None:raise ValueError('source identity/date not represented by complete calendar panel')
    for product in roster.values():
        product['contracts_with_candidates']=len(product['contracts_with_candidates'])
        product['metadata_statuses']=canonical(sorted(product['metadata_statuses']))
    counts.update(catalog_contracts=len(catalog),catalog_products=len(roster),calendar_days=len(target),
        products_with_candidates=sum(p['contracts_with_candidates']>0 for p in roster.values()),
        contracts_with_candidates=sum(p['contracts_with_candidates'] for p in roster.values()))
    assert counts['panel_rows']==len(roster)*len(target)
    assert counts['source_observation_rows']==counts['qualified_candidate_rows']+counts['rejected_rows']
    def grouped(table,field):return [dict(zip((field,'year'),key),**dict(value)) for key,value in sorted(table.items())]
    return dict(product_roster=list(roster.values()),counts=dict(counts),rejected_reasons=dict(reject_reasons),
        product_year_counts=grouped(product_year,'product_id'),exchange_year_counts=grouped(exchange_year,'exchange'),
        calendar_scope=[target[0],target[-1]],source_calendar_last=cal[-1])


def file_state(path):
    p=Path(path);stat=p.stat()
    return dict(path=str(p.resolve()),bytes=stat.st_size,mtime_ns=stat.st_mtime_ns,inode=stat.st_ino,device=stat.st_dev,
        wal_present=Path(str(p)+'-wal').exists(),shm_present=Path(str(p)+'-shm').exists())


def bound_bytes(item):
    path=Path(item['path'])
    if not path.is_absolute():raise ValueError('source binding path must be absolute')
    raw=path.read_bytes()
    if digest(raw)!=item['sha256'] or ('bytes' in item and len(raw)!=item['bytes']):raise ValueError('small source binding mismatch: '+str(path))
    return raw


def check_database(binding):
    if not Path(binding['path']).is_absolute():raise ValueError('database path must be absolute')
    state=file_state(binding['path'])
    for key in ('bytes','mtime_ns','wal_present','shm_present'):
        if key not in binding or state[key]!=binding[key]:raise ValueError('database source state mismatch: '+key)
    for key in ('inode','device'):
        if key in binding and state[key]!=binding[key]:raise ValueError('database source state mismatch: '+key)
    if state['wal_present'] or state['shm_present']:raise ValueError('database sidecar present')
    if not re.fullmatch(r'[0-9a-f]{64}',binding.get('sha256','')):raise ValueError('inherited database SHA required')
    return state


def csv_value(value):
    if isinstance(value,float):return format(value,'.17g') if math.isfinite(value) else ''
    return value


def write_json(path,value):
    raw=(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    Path(path).write_bytes(raw)


def export_panel(bindings_path,bindings_sha256,output):
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    binding_item=dict(path=str(Path(bindings_path).resolve()),sha256=bindings_sha256)
    binding_raw=bound_bytes(binding_item);bindings=json.loads(binding_raw)
    if bindings.get('schema')!='stage004_source_bindings_v1':raise ValueError('unsupported source bindings schema')
    if bindings.get('scope_start',START)!=START or bindings.get('scope_end',END)!=END:raise ValueError('fixed opportunity scope mismatch')
    before=check_database(bindings['database'])
    payloads={}
    for item in [bindings['calendar'],*bindings['small_bindings']]:payloads[item['path']]=bound_bytes(item)
    calendar=load_calendar(payloads[bindings['calendar']['path']])
    small_before={path:file_state(path) for path in payloads}
    output.mkdir(parents=True,exist_ok=False)
    rejected_path=output/'rejected_source_rows.csv'
    with rejected_path.open('x',newline='',encoding='utf-8') as reject_stream:
        reject_writer=csv.DictWriter(reject_stream,fieldnames=['contract_epoch_id','product_id','u_date','source_id','reasons','raw_values'],lineterminator='\n');reject_writer.writeheader()
        with (output/'product_day_opportunities.csv.gz').open('xb') as compressed:
            with gzip.GzipFile(filename='',fileobj=compressed,mode='wb',mtime=0) as zipped:
                with io.TextIOWrapper(zipped,encoding='utf-8',newline='') as stream:
                    writer=csv.DictWriter(stream,fieldnames=FIELDS,lineterminator='\n');writer.writeheader()
                    def emit(row):writer.writerow({k:csv_value(v) for k,v in row.items()})
                    info=scan_database(bindings['database']['path'],calendar,emit=emit,emit_rejected=reject_writer.writerow)
    after=check_database(bindings['database'])
    if before!=after:raise ValueError('database changed during read-only export')
    if any(file_state(path)!=state for path,state in small_before.items()):raise ValueError('small source changed during export')
    count_mapping=dict(product_catalog='catalog_products',calendar_scope_days='calendar_days',complete_panel_rows='panel_rows',
        observed_product_days='observed_long_research_opportunity',accepted_contract_day_rows='qualified_candidate_rows')
    expected_checks={}
    for key,value in bindings.get('expected_input_counts',{}).items():
        if key not in count_mapping:raise ValueError('unknown expected input count: '+key)
        expected_checks[key]=info['counts'][count_mapping[key]]==value
    if not all(expected_checks.values()):raise ValueError('input inventory count mismatch: '+canonical(expected_checks))
    for name,rows in [('product_roster.csv',info['product_roster']),('product_year_counts.csv',info['product_year_counts']),('exchange_year_counts.csv',info['exchange_year_counts'])]:
        with (output/name).open('x',newline='',encoding='utf-8') as stream:
            # Counter omits zero keys: supply explicit common count columns.
            columns=list(rows[0]) if name=='product_roster.csv' else [*(['product_id'] if name.startswith('product_') else ['exchange']),'year','panel_rows','observed_long_research_opportunity','no_accepted_observation']
            writer=csv.DictWriter(stream,fieldnames=columns,restval=0,lineterminator='\n');writer.writeheader();writer.writerows(rows)
    write_json(output/'source_bindings.json',bindings)
    artifacts={p.name:dict(sha256=digest(p.read_bytes()),bytes=p.stat().st_size) for p in output.iterdir() if p.is_file()}
    np=sys.modules.get('numpy')
    manifest=dict(schema=VERSION,scope=[START,END],exchanges=sorted(EXCHANGES),**{k:v for k,v in info.items() if k!='product_roster'},
        product_count=len(info['product_roster']),source_binding_file=dict(binding_item,bytes=len(binding_raw)),source_bindings=bindings,
        expected_input_count_checks=expected_checks,input_inventory_independently_reviewed=bindings.get('input_inventory_independently_reviewed',False),
        database_before=before,database_after=after,database_sha_policy='inherited_accepted_Stage266_SHA_not_rehashed_by_this_export',
        source_bytes_hashed_again=0,artifacts=artifacts,source_code=dict(path=str(Path(__file__).resolve()),sha256=digest(Path(__file__).read_bytes())),
        event_id_contract='canonical(version,product_id,u_date); reference epoch separately bound under this fixed rule version',
        representative_rule='u volume descending; finite nonnegative close_oi descending, missing last; epoch lexicographic ascending',
        information_set_contract='after_u_daily_data_available_before_D_execution',publication_pit_certified=False,
        execution_qualification='not_assessed',financial_ready=False,label_ready=False,model_ready=False,production_qualified=False,
        runtime=dict(executable=sys.executable,python=sys.version,sqlite=sqlite3.sqlite_version,numpy=getattr(np,'__version__',None)),
        limitations=['Complete catalog-calendar observations, not listings certification, executable trades, mature labels or independent samples.',
            'No C9/monthly-pool/legacy train flag/D-data/future volume eligibility gate.',
            'Opening OI missing is retained; close OI invalid/missing ranks last without deleting an otherwise legal observation.',
            'Missing multiplier/tick/margin/fees/session/minutes remains outside this observation export.'],
        financial_runs=0,model_loads=0,training_runs=0,network_calls=0)
    write_json(output/'manifest.json',manifest)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bindings',type=Path,required=True);parser.add_argument('--bindings-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    started=datetime.now().astimezone().isoformat(timespec='seconds');began=time.monotonic()
    result=export_panel(args.bindings,args.bindings_sha256,args.output)
    terminal=dict(schema='stage004_actual_terminal_v1',started_at=started,finished_at=datetime.now().astimezone().isoformat(timespec='seconds'),
        elapsed_seconds=time.monotonic()-began,exit_code=0,actual_export_invocations=1,command=sys.argv,
        source_code_sha256=digest(Path(__file__).read_bytes()),manifest_sha256=digest((args.output/'manifest.json').read_bytes()),
        counts=result['counts'],financial_runs=0,training_runs=0,network_calls=0)
    write_json(args.output/'actual_terminal.json',terminal)
    print(canonical(terminal))


if __name__=='__main__':main()
