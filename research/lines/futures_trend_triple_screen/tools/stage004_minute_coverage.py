"""Read-only session coverage: conservative requirement sets, no account replay."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import csv
from datetime import datetime
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
import time
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[4]
LINE=ROOT/'research/lines/futures_trend_triple_screen'
PROJECT=ROOT/'examples/portfolio_backtesting'
OUTPUT=LINE/'outputs/stage004_minute_coverage'
PROTOCOL=LINE/'stages/20261017_2312_stage004_minute_coverage_protocol.md'
MAPPING=PROJECT/'backtest_outputs/tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv'
DATABASE=ROOT/'.vntrader/database.db'
BASE=PROJECT/'backtest_outputs/qmt_roll_stage861_stage860_full_visual_atlas_full_minute_bars_stage861_stage860_full_visual_atlas_v1.csv'
OVERLAY_DIR=LINE/'outputs/stage002_local_minute_overlay/attempt2'
REVIEW=LINE/'outputs/stage002_independent_review/overlay_independent_checks.json'
OLD=ROOT/'research/lines/futures_trend_rollover_shape_same_volume/outputs/stage251_half_r_ab/A_final3'
A0=LINE/'outputs/stage001_first_screen/A0_attempt2'
FORMAL19={'AP.CZCE','CF.CZCE','FG.CZCE','MA.CZCE','OI.CZCE','SA.CZCE','SH.CZCE','SM.CZCE',
    'jm.DCE','lh.DCE','lc.GFEX','si.GFEX','au.SHFE','cu.SHFE','fu.SHFE','hc.SHFE','rb.SHFE','ru.SHFE','sp.SHFE'}
sys.path.insert(0,str(PROJECT))
from qmt_roll_intraday_execution import session_minutes


def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb')as source:
        for block in iter(lambda:source.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def write_json(path,payload):Path(path).write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def index_minutes(paths):
    pieces=defaultdict(list);counts={}
    for path in paths:
        count=0
        for frame in pd.read_csv(path,usecols=['vt_symbol','bar_datetime'],chunksize=200000):
            times=pd.to_datetime(frame.bar_datetime,errors='raise')
            if times.dt.tz is not None:times=times.dt.tz_convert('Asia/Shanghai').dt.tz_localize(None)
            frame['time_ns']=times.astype('int64');count+=len(frame)
            for symbol,group in frame.groupby('vt_symbol',sort=False):pieces[str(symbol)].append(group.time_ns.to_numpy())
        counts[str(path)]=count
    result={}
    for symbol,groups in pieces.items():
        values=np.sort(np.concatenate(groups))
        if len(values)>1 and np.any(values[1:]==values[:-1]):raise ValueError(f'duplicate_available_minute_key:{symbol}')
        result[symbol]=values
    return result,counts


def coverage_counts(available,expected):
    if len(expected)==0:raise ValueError('empty_session_grid')
    positions=np.searchsorted(available,expected,side='left')
    present=np.zeros(len(expected),dtype=bool)
    inside=positions<len(available)
    present[inside]=available[positions[inside]]==expected[inside]
    observed=int(present.sum())
    return dict(expected_minutes=len(expected),available_minutes=observed,missing_minutes=len(expected)-observed,
        anchor_present=bool(present[0]),complete=observed==len(expected))


def source_session_grid(product,position,calendar):
    code,exchange=product.rsplit('.',1)
    day=calendar[position]
    grid=session_minutes(f'{code}0.{exchange}',day,calendar[max(0,position-1):position+1])
    return grid.to_numpy(dtype='datetime64[ns]').astype(np.int64)


def build_requirements(mapping,real,calendar):
    calendar=pd.DatetimeIndex(calendar)
    result={}
    products=dict(zip(mapping.main_contract_vt,mapping.continuous_symbol_vt))
    def info(symbol):
        if symbol not in result:result[symbol]=dict(product=products.get(symbol,''),main=set(),previous=set(),real=set(),first_main=None)
        return result[symbol]
    for product,group in mapping.sort_values('date').groupby('continuous_symbol_vt',sort=False):
        current='';previous=''
        for row in group.itertuples():
            if not row.main_contract_vt:continue
            position=int(calendar.get_indexer([pd.Timestamp(row.date)])[0])
            if position<0:continue
            if row.main_contract_vt!=current:previous,current=current,row.main_contract_vt
            current_info=info(current);current_info['product']=product;current_info['main'].add(position)
            if current_info['first_main']is None:current_info['first_main']=position
            if previous:info(previous)['previous'].add(position)
    for symbol,group in real.groupby('vt_symbol',sort=False):
        positions=calendar.get_indexer(pd.to_datetime(group.trade_date))
        info(symbol)['real'].update(int(x)for x in positions if x>=0)
    for symbol,row in result.items():
        if not row['product']:
            native,exchange=symbol.rsplit('.',1);row['product']=f'{re.sub("[0-9]+$","",native)}.{exchange}'
        upper=range(row['first_main'],len(calendar))if row['first_main']is not None else []
        row['positions']=np.union1d(np.array(sorted(row['real']),dtype=np.int32),np.array(list(upper),dtype=np.int32))
    return result


def classify_requirement(info,position):
    main=position in info['main'];previous=position in info['previous'];real=position in info['real']
    upper=info['first_main']is not None and position>=info['first_main']
    role='current_main'if main else'adjacent_previous_main'if previous else'earlier_prior_main'if upper else'metadata_real_only'
    return dict(main_only=main,main_plus_previous=main or previous,metadata_real=real,ever_main_upper=upper,
        real_daily_present=real,mapping_role=role,carry_risk=upper and not real)


def real_data_gap(row):return bool(row['real_daily_present']and row['missing_minutes']>0)


def candidate_inventory(metadata,declared):
    roots=[ROOT,Path('/Users/mac/Documents/Codex/fian-research-20261014'),
        Path('/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014/repo'),
        Path('/Users/mac/.codex/worktrees/formal-2020-replay/fian'),Path('/Users/mac/.codex/worktrees/formal-correctness-replay/fian')]
    pattern=re.compile(r'^([A-Za-z]+[0-9]+)(?:_completed)?_minute_backtest\.csv$')
    rows=[]
    for root in roots:
        folder=root/'examples/portfolio_backtesting/downloaded_futures'
        if not folder.is_dir():continue
        for path in folder.rglob('*.csv'):
            match=pattern.fullmatch(path.name)
            if not match:continue
            symbol=f'{match.group(1)}.{path.parent.name}'
            if symbol not in metadata:continue
            family=path.relative_to(folder).parts[0]
            relative=str(path.relative_to(root))
            rows.append(dict(vt_symbol=symbol,path=str(path),workspace_root=str(root),family=family,
                bytes=path.stat().st_size,manifest_declared_sha256=declared.get(relative,''),measured_sha256='',
                sha_status='manifest_declaration_only_not_rehashed'if relative in declared else'not_declared_not_rehashed',
                semantics_hint='filename_says_completed_not_validated'if'_completed_'in path.name else'raw_or_forming_unverified',
                auto_accepted=False,covered_dates_verified=False))
    return pd.DataFrame(rows).sort_values(['vt_symbol','workspace_root','family','path']).reset_index(drop=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--audit',action='store_true',required=True);parser.parse_args()
    if OUTPUT.exists():raise FileExistsError('existing_coverage_audit_refusing_repeat')
    declared=json.loads((OLD/'input_manifest.json').read_text())
    overlay_summary=json.loads((OVERLAY_DIR/'summary.json').read_text())
    review=json.loads(REVIEW.read_text())
    if review['status']!='independent_overlay_and_A0_path_equivalence_pass':raise ValueError('overlay_not_independently_accepted')
    for name,value in review['source_hashes'].items():
        if sha256(OVERLAY_DIR/name)!=value:raise ValueError(f'changed_reviewed_overlay_asset:{name}')
    inputs={str(path):sha256(path)for path in [BASE,OVERLAY_DIR/'overlay.csv',OVERLAY_DIR/'summary.json',REVIEW,
        MAPPING,DATABASE,A0/'effective_parameters.json',A0/'actual_strategy_settings.json',PROTOCOL,
        Path(__file__),PROJECT/'qmt_roll_intraday_execution.py']}
    for path in [BASE,MAPPING,DATABASE]:
        if inputs[str(path)]!=declared.get(str(path.relative_to(ROOT))):raise ValueError(f'accepted_original_input_changed:{path}')
    if inputs[str(OVERLAY_DIR/'overlay.csv')]!=overlay_summary['overlay_sha256']:raise ValueError('overlay_sha_changed')
    OUTPUT.mkdir(parents=True,exist_ok=False)
    write_json(OUTPUT/'attempt_started.json',dict(started_at=datetime.now().astimezone().isoformat(),financial_attempts=0,downloads=0))
    started=time.monotonic()
    try:
        mapping=pd.read_csv(MAPPING,usecols=['date','continuous_symbol_vt','main_contract_vt']).fillna('')
        mapping['date']=pd.to_datetime(mapping.date)
        full_calendar=pd.DatetimeIndex(sorted(mapping.date.unique()))
        calendar=full_calendar[(full_calendar>='2020-01-01')&(full_calendar<='2026-10-14')]
        all_mapping=mapping.loc[mapping.continuous_symbol_vt.isin(FORMAL19)&mapping.main_contract_vt.ne('')]
        metadata=set(json.loads((A0/'effective_parameters.json').read_text())['contract_sizes'])
        if metadata!=set(all_mapping.main_contract_vt):raise ValueError('metadata_mapping_identity_disagreement')
        settings=json.loads((A0/'actual_strategy_settings.json').read_text())[0]['actual']
        if settings['trade_start_date']!='2020-01-01':raise ValueError('initial_flat_start_assumption_changed')
        current_mapping=all_mapping.loc[all_mapping.date.isin(calendar)].copy()
        with sqlite3.connect(DATABASE.resolve().as_uri()+'?mode=ro',uri=True)as db:
            db.execute('PRAGMA query_only=ON')
            real=pd.read_sql_query("SELECT symbol||'.'||exchange AS vt_symbol,substr(datetime,1,10) AS trade_date FROM dbbardata WHERE interval='d' AND datetime>='2020-01-01' AND datetime<'2026-10-15'",db)
        real=real.loc[real.vt_symbol.isin(metadata)].copy()
        real['trade_date']=pd.to_datetime(real.trade_date)
        if real.duplicated(['vt_symbol','trade_date']).any():raise ValueError('duplicate_real_daily_identity')
        outside=int((~real.trade_date.isin(calendar)).sum())
        if outside:raise ValueError(f'real_daily_dates_outside_source_calendar:{outside}')
        requirements=build_requirements(current_mapping,real,calendar)
        indexes,input_row_counts=index_minutes([BASE,OVERLAY_DIR/'overlay.csv'])
        print(f'indexed {sum(input_row_counts.values())} accepted minute keys; requirement contracts={len(requirements)}',flush=True)
        inventory=candidate_inventory(metadata,declared)
        inventory.to_csv(OUTPUT/'local_source_candidates.csv',index=False,encoding='utf-8-sig')
        candidate_counts=inventory.vt_symbol.value_counts().to_dict()
        source_positions=full_calendar.get_indexer(calendar)
        @lru_cache(maxsize=None)
        def grid(product,position):return source_session_grid(product,int(source_positions[position]),full_calendar)
        counters=defaultdict(lambda:Counter());examples=[];example_counts=Counter();known_failures=[];session_count=0
        labels=['main_only','main_plus_previous','metadata_real','ever_main_upper']
        fieldnames=['vt_symbol','product_vt_symbol','date','mapping_role',*labels,'real_daily_present','carry_risk',
            'expected_minutes','available_minutes','missing_minutes','anchor_present','complete','real_data_gap','local_candidate_paths']
        with gzip.open(OUTPUT/'session_coverage.csv.gz','wt',encoding='utf-8',newline='',compresslevel=4)as handle:
            writer=csv.DictWriter(handle,fieldnames=fieldnames);writer.writeheader()
            for number,(symbol,info)in enumerate(sorted(requirements.items())):
                available=indexes.get(symbol,np.empty(0,dtype=np.int64))
                for position in info['positions']:
                    position=int(position);day=calendar[position];flags=classify_requirement(info,position)
                    counts=coverage_counts(available,grid(info['product'],position))
                    row=dict(vt_symbol=symbol,product_vt_symbol=info['product'],date=str(day.date()),**flags,**counts,
                        local_candidate_paths=int(candidate_counts.get(symbol,0)))
                    row['real_data_gap']=real_data_gap(row);writer.writerow(row);session_count+=1
                    year=str(day.year)
                    for label in labels:
                        if not row[label]:continue
                        count=counters[(label,symbol,info['product'],year)]
                        count.update(sessions=1,expected_minutes=counts['expected_minutes'],available_minutes=counts['available_minutes'],
                            missing_minutes=counts['missing_minutes'],anchor_present=int(counts['anchor_present']),
                            complete_sessions=int(counts['complete']),real_daily_sessions=int(flags['real_daily_present']),
                            carry_risk_sessions=int(flags['carry_risk']),real_data_gap_sessions=int(row['real_data_gap']))
                    if row['missing_minutes']:
                        bucket=(year,info['product'],row['mapping_role'],row['real_daily_present'])
                        if example_counts[bucket]<3:examples.append(row.copy());example_counts[bucket]+=1
                    if symbol=='rb2010.SHFE'and row['date']in ('2020-05-18','2020-08-12'):known_failures.append(row.copy())
                if (number+1)%50==0:print(f'audited {number+1}/{len(requirements)} contracts; sessions={session_count}; cached grids={grid.cache_info().currsize}',flush=True)
        detail=pd.DataFrame([dict(requirement_set=label,vt_symbol=symbol,product_vt_symbol=product,year=year,**dict(values))
            for(label,symbol,product,year),values in counters.items()])
        numeric=[name for name in detail.columns if name not in ['requirement_set','vt_symbol','product_vt_symbol','year']]
        def save_aggregate(keys,name):
            result=detail.groupby(keys,as_index=False)[numeric].sum()
            result['missing_anchor_sessions']=result.sessions-result.anchor_present
            result['full_session_coverage_pct']=100*result.complete_sessions/result.sessions
            result.to_csv(OUTPUT/name,index=False,encoding='utf-8-sig');return result
        detail['local_candidate_paths']=detail.vt_symbol.map(candidate_counts).fillna(0).astype(int)
        detail.to_csv(OUTPUT/'contract_year_summary.csv',index=False,encoding='utf-8-sig')
        save_aggregate(['requirement_set','product_vt_symbol','year'],'product_year_summary.csv')
        save_aggregate(['requirement_set','year'],'year_summary.csv')
        save_aggregate(['requirement_set','vt_symbol','product_vt_symbol'],'contract_summary.csv')
        totals=save_aggregate(['requirement_set'],'requirement_set_summary.csv')
        pd.DataFrame(examples).to_csv(OUTPUT/'gap_examples.csv',index=False,encoding='utf-8-sig')
        pd.DataFrame(known_failures).to_csv(OUTPUT/'known_failure_session_coverage.csv',index=False,encoding='utf-8-sig')
        changed=[path for path,digest in inputs.items()if sha256(path)!=digest]
        if changed:raise ValueError(f'inputs_changed_during_coverage_audit:{changed}')
        write_json(OUTPUT/'input_manifest.json',inputs)
        summary=dict(status='completed_zero_account_coverage_audit_pending_independent_review',
            started_protocol_sha256=inputs[str(PROTOCOL)],source_code_sha256=inputs[str(Path(__file__))],
            elapsed_seconds=time.monotonic()-started,financial_attempts=0,downloads=0,model_fits=0,source_writes=0,
            all_inputs_unchanged=True,base_rows=input_row_counts[str(BASE)],overlay_rows=input_row_counts[str(OVERLAY_DIR/'overlay.csv')],
            unique_available_minute_keys=sum(len(values)for values in indexes.values()),duplicate_available_keys=0,
            metadata_contracts=len(metadata),contracts_with_requirements=len(requirements),source_trading_dates=len(calendar),
            products=len(FORMAL19),union_session_rows=session_count,cached_product_date_grids=grid.cache_info().currsize,
            requirement_sets=totals.to_dict('records'),local_candidate_file_paths=len(inventory),
            candidate_family_counts=dict(Counter(inventory.family)),candidate_file_contents_read=0,candidate_files_measured_SHA=0,
            candidate_sha_meaning='Only old-manifest declarations are copied; current candidate contents/coverage are not verified.',
            potential_signal_set_is_exact=False,production_qualified=False,order_api_calls=0,cancel_api_calls=0,
            known_failure_sessions=known_failures,gap_examples=len(examples),
            assumptions=['Initial account flat; indicator warmup cannot trade before 2020-01-01.',
                'Only products/contracts entering the fixed main mapping may originate positions; retries/rollovers derive from them.',
                'ever_main_upper keeps every research-period former main until the end, including expired/no-real-bar dates.',
                'It is not sufficient for arbitrary injected positions, pre-start holdings, non-mapping entries or all metadata carry states.',
                'metadata_real is a separate physical-bar coverage set, including pre-main bars; no exact signal claim.'],
            interpretation=['Full coverage counts expected timestamp keys only, relying on previously accepted base/overlay prices.',
                'No-real-bar upper-bound gaps are carry diagnostics, not a download shopping list.',
                'A local candidate path and declared checksum do not prove a completed session.',
                'Next step requires outcome-blind exact candidate/preparation events before data supplementation or another account run.'],
            runtime=dict(python=sys.executable,numpy=np.__version__,pandas=pd.__version__))
        files=[p for p in OUTPUT.iterdir()if p.is_file()and p.name!='summary.json']
        summary['artifact_sha256']={p.name:sha256(p)for p in files}
        write_json(OUTPUT/'summary.json',summary)
        print(json.dumps({k:summary[k]for k in ['status','elapsed_seconds','financial_attempts','union_session_rows','requirement_sets','local_candidate_file_paths']},ensure_ascii=False),flush=True)
    except Exception as error:
        write_json(OUTPUT/'failure.json',dict(status='failed_no_accepted_coverage',error=repr(error),financial_attempts=0,downloads=0))
        raise


if __name__=='__main__':main()
