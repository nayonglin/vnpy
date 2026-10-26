"""Stage029 bounded daily-only Tq evidence and additive snapshot; no financial replay."""
from pathlib import Path
from datetime import date, datetime
from zoneinfo import ZoneInfo
import argparse, contextlib, hashlib, io, json, math, os, re, shutil, socket, sqlite3, time
import pandas as pd

ROOT=Path(__file__).resolve().parents[4]
LINE=ROOT/'research/lines/futures_weekly_formal_no_half_r'
BASE=LINE/'outputs/stage025_history_data_approved'
N002=LINE/'outputs/N_attempt002'
OUT=LINE/'outputs/stage029_latest_data'
PROBE=OUT/'probe_attempt001'
SNAPSHOT=OUT/'data_approved'
CONTRACT=LINE/'stages/20261026_1924_stage029_week_close_exit_contract_plan.md'
TARGET='2026-10-26'
TZ=ZoneInfo('Asia/Shanghai')
FIELDS=['open','high','low','close','volume','close_oi']
AUTHORITY='stage029_predeclared_Tq_only_single_sided_close_oi'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def dump(path,obj):
    path=Path(path);tmp=Path(str(path)+'.pending')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
    os.replace(tmp,path)


def validate_daily(row):
    values={k:float(row[k]) for k in FIELDS}
    if not all(math.isfinite(x) for x in values.values()):raise ValueError('nonfinite_daily')
    o,h,l,c,v,oi=(values[k] for k in FIELDS)
    if min(o,h,l,c,v)<=0 or oi<0 or l>min(o,c) or h<max(o,c) or l>h:raise ValueError('nonpositive_or_illegal_daily')
    return values


def permitted_key(symbol,day):
    return day==TARGET or (symbol=='cu2612.SHFE' and '2026-10-19'<=day<='2026-10-23')


def bind_physical(symbol,day,epochs):
    choices=[r for r in epochs if str(r['vt_symbol'])==symbol and (not r.get('listed_date') or r['listed_date']<=day) and (not r.get('delisted_date') or day<=r['delisted_date'])]
    if len(choices)!=1:raise ValueError('physical_identity_not_unique:'+symbol+':'+day)
    row=choices[0];yyyymm=str(row['contract_yyyymm'])
    code,exchange=symbol.split('.');match=re.fullmatch(r'([A-Za-z]+)(\d{3,4})',code)
    if not re.fullmatch(r'\d{4}(0[1-9]|1[0-2])',yyyymm) or not match or yyyymm[-(3 if exchange=='CZCE' else 4):]!=match[2]:raise ValueError('physical_month_mismatch:'+symbol)
    expected=exchange+'.'+match[1].upper()+'.'+yyyymm
    if row['contract_epoch_id']!=expected:raise ValueError('physical_epoch_id_mismatch:'+symbol)
    return row


def frozen_inputs():
    files={}
    for manifest in [BASE/'source_manifest.json',N002/'input_manifest.json']:
        obj=json.loads(manifest.read_text());files.update(obj.get('files',obj));files[str(manifest)]=sha(manifest)
    for p in [BASE/'receipt.json',N002/'positions.csv',N002/'pending_orders.csv',CONTRACT,Path(__file__),OUT/'tests/test_latest_data.py']:
        files[str(p)]=sha(p)
    bad=[p for p,d in files.items() if not Path(p).is_file() or sha(p)!=d]
    if bad:raise ValueError('frozen_input_changed:'+repr(bad))
    return files


def tq_to_vt(value):
    exchange,code=value.split('.',1);return code+'.'+exchange


def probe(files):
    PROBE.mkdir(parents=True,exist_ok=False)
    (PROBE/'raw_daily').mkdir();(PROBE/'contract_receipts').mkdir()
    receipt=dict(schema='stage029_latest_daily_probe_v1',status='started',target_date=TARGET,started_at=datetime.now(TZ).isoformat(),raw_daily_interval_seconds=86400,per_contract_raw_limit=64,max_contracts=48,financial_replays=0,minute_reads=0,order_api_count=0,source_authority=AUTHORITY,source_consensus_claim=False,forming_future_daily_admission=False,inputs_before=files)
    dump(PROBE/'progress.json',receipt)
    api=None;stage='preflight';guards=dict(insert_order_calls=0,cancel_order_calls=0)
    statuses=[]
    try:
        now=datetime.now(TZ)
        if now<datetime(2026,10,26,15,30,tzinfo=TZ):raise ValueError('target_day_not_completed')
        os.environ.update(TZ='Asia/Shanghai',OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED='0',OFFICIAL_LIVE_PHASE_D_SESSION_DAEMON_ENABLED='0')
        time.tzset();socket.setdefaulttimeout(25)
        products=json.loads((BASE/'receipt.json').read_text())['products']
        if len(products)!=19:raise ValueError('fixed_original19_required')
        stage='authentication_and_fresh_main_response'
        credentials=json.loads(Path('/Users/mac/Desktop/fian/.vntrader/vt_setting.json').read_text())
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            from tqsdk import TqApi,TqAuth,TqSim
            from tqsdk.calendar import TqContCalendar
            import tqsdk,requests
            auth=TqAuth(credentials['datafeed.username'],credentials['datafeed.password']);auth.login()
            fetched_start=datetime.now(TZ).isoformat()
            response=requests.get('https://files.shinnytech.com/continuous_table.json',headers=auth._base_headers,timeout=25)
            response.raise_for_status();raw=response.content;table=response.json();fetched_end=datetime.now(TZ).isoformat()
            raw_path=PROBE/'fresh_main_continuous_table.raw.json';raw_path.write_bytes(raw)
            TqContCalendar.continuous={f'KQ.m@{key}':value for key,value in table.items()}
            symbols=['KQ.m@'+p.split('.')[1]+'.'+p.split('.')[0] for p in products]
            calendar=TqContCalendar(start_dt=date(2026,10,19),end_dt=date(2026,10,30),symbols=symbols,headers=auth._base_headers)
        calendar.df.to_csv(PROBE/'fresh_calendar_raw.csv',index=False)
        dump(PROBE/'fresh_main_response_receipt.json',dict(source_url='https://files.shinnytech.com/continuous_table.json',retrieval_started_at=fetched_start,retrieval_completed_at=fetched_end,response_body_path=str(raw_path),response_body_sha256=sha(raw_path),response_bytes=len(raw),http_status=200,source_authority=AUTHORITY,not_a_PIT_claim=True))
        mapping_rows=[]
        for row in calendar.df.to_dict('records'):
            day=str(row['date'])[:10]
            for product,key in zip(products,symbols):
                value=row.get(key);value='' if pd.isna(value) else str(value)
                mapping_rows.append(dict(date=day,product=product.split('.')[0],exchange=product.split('.')[1],continuous_symbol_tq=key,continuous_symbol_vt=product,main_contract_tq=value,main_contract_vt=tq_to_vt(value) if value else ''))
        mapping=pd.DataFrame(mapping_rows);mapping.to_csv(PROBE/'fresh_mapping_probe.csv',index=False)
        target=mapping.loc[mapping.date.eq(TARGET)].copy();target.to_csv(PROBE/'target_mapping.csv',index=False)
        prior=pd.read_csv(BASE/'mapping.csv').fillna('');prior=prior.loc[prior.date.eq('2026-10-23')&prior.continuous_symbol_vt.isin(products)]
        overlap=prior.merge(mapping.loc[mapping.date.eq('2026-10-23')],on=['date','continuous_symbol_vt'],suffixes=('_frozen','_fresh'))
        overlap['same_main_contract']=overlap.main_contract_vt_frozen.eq(overlap.main_contract_vt_fresh)
        overlap.to_csv(PROBE/'mapping_overlap_20261023.csv',index=False)
        if len(overlap)!=19 or not overlap.same_main_contract.all():raise ValueError('historical_mapping_response_changed')
        if len(target)!=19 or target.continuous_symbol_vt.nunique()!=19 or target.main_contract_vt.eq('').any():raise ValueError('fresh_target_mapping_incomplete')
        future=sorted(d for d in mapping.date.unique() if d>TARGET)
        if not future:raise ValueError('forward_trading_calendar_missing')
        held=pd.read_csv(N002/'positions.csv');last=str(held.date.max());held_symbols=set(held.loc[held.date.eq(last)&held.end_pos.ne(0),'vt_symbol'])
        pending=pd.read_csv(N002/'pending_orders.csv');pending_symbols=set(pending.vt_symbol.dropna().astype(str)) if 'vt_symbol' in pending else set()
        offmain=json.loads((LINE/'outputs/stage022_offmain_probe/probe_receipt.json').read_text())
        offmain_symbols={r['vt_symbol'] for r in offmain['contract_statuses']}
        wanted=sorted(set(target.main_contract_vt)|set(prior.main_contract_vt)|held_symbols|pending_symbols|offmain_symbols)
        if len(wanted)>48 or len(offmain_symbols)!=8:raise ValueError('declared_contract_budget_exceeded')
        if any(re.sub(r'\d+(?=\.)','',s) not in products for s in wanted):raise ValueError('contract_outside_fixed_original19')
        epochs=pd.read_csv(BASE/'physical_epochs.csv',dtype=str).fillna('').to_dict('records')
        for symbol in wanted:bind_physical(symbol,TARGET,epochs)
        dump(PROBE/'selection.json',dict(fresh_main=sorted(set(target.main_contract_vt)),previous_main=sorted(set(prior.main_contract_vt)),frozen_terminal_positions=sorted(held_symbols),frozen_pending_contracts=sorted(pending_symbols),old_offmain_tail=sorted(offmain_symbols),requested_contracts=wanted,contract_count=len(wanted),selection_uses_strategy_profit=False))
        stage='daily_serials'
        def forbidden(key):
            def block(*args,**kwargs):guards[key]+=1;raise RuntimeError('order_api_forbidden')
            return block
        TqApi.insert_order=forbidden('insert_order_calls');TqApi.cancel_order=forbidden('cancel_order_calls')
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            api=TqApi(TqSim(),auth=auth,disable_print=True)
        for symbol in wanted:
            code,exchange=symbol.split('.')
            try:
                with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                    serial=api.get_kline_serial(exchange+'.'+code,86400,data_length=64);deadline=time.time()+35
                    while not api.is_serial_ready(serial):
                        if time.time()>deadline:raise TimeoutError('daily_serial_not_ready')
                        api.wait_update(deadline=deadline)
                    raw=serial.copy();stamp=datetime.now(TZ).isoformat()
                path=PROBE/'raw_daily'/(symbol+'.csv');raw.to_csv(path,index=False)
                status=dict(vt_symbol=symbol,status='fetched',snapshot_at=stamp,raw_path=str(path),raw_sha256=sha(path),raw_rows=len(raw),serial_ready=True,duration_seconds=86400)
            except Exception as exc:
                status=dict(vt_symbol=symbol,status='failed',error_type=type(exc).__name__)
            statuses.append(status);dump(PROBE/'contract_receipts'/(symbol+'.json'),status)
            dump(PROBE/'progress.json',{**receipt,'stage':stage,'requested_contracts':len(wanted),'completed_contracts':len(statuses),'contract_statuses':statuses})
            print(json.dumps(dict(contract=symbol,completed=len(statuses),total=len(wanted),status=status['status'])),flush=True)
            if status['status']!='fetched':raise ValueError('contract_probe_failed_no_retry')
        stage='current_main_quotes'
        quote_rows=[]
        for product,key in zip(products,symbols):
            with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):q=api.get_quote(key)
            quote_rows.append(dict(product_vt_symbol=product,continuous_symbol_tq=key,underlying_symbol=str(q.underlying_symbol),quote_datetime=str(q.datetime),snapshot_at=datetime.now(TZ).isoformat()))
        quotes=pd.DataFrame(quote_rows);quotes.to_csv(PROBE/'current_main_quotes.csv',index=False)
        joined=target.merge(quotes,left_on='continuous_symbol_vt',right_on='product_vt_symbol',validate='one_to_one');joined['same_main_contract']=joined.main_contract_tq.eq(joined.underlying_symbol);joined.to_csv(PROBE/'main_quote_comparison.csv',index=False)
        if len(joined)!=19 or not joined.same_main_contract.all():raise ValueError('fresh_main_quote_disagreement')
        receipt.update(status='raw_daily_probe_ready',tqsdk_version=tqsdk.__version__,requested_contracts=wanted,contract_count=len(wanted),contract_statuses=statuses,next_trading_date=future[0],current_main_quote_agreement=19,target_is_ordinary_week_end=False,weekly_boundary_reason='2026-10-26 is first trading day of the week; 10/27 exists in fresh calendar',completed_at=datetime.now(TZ).isoformat())
    except Exception as exc:
        receipt.update(status='failed_probe',error_type=type(exc).__name__,failure_stage=stage,contract_statuses=statuses,completed_at=datetime.now(TZ).isoformat())
    finally:
        if api is not None:
            with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):api.close()
        changed=[p for p,d in files.items() if sha(p)!=d]
        receipt.update(guards=guards,original_inputs_unchanged=not changed,changed_inputs=changed)
        if changed:receipt['status']='REJECT_FROZEN_INPUT_CHANGED'
        dump(PROBE/'probe_receipt.json',receipt)
    return receipt


def assemble(files):
    receipt=json.loads((PROBE/'probe_receipt.json').read_text())
    if receipt['status']!='raw_daily_probe_ready' or not receipt['original_inputs_unchanged']:raise ValueError('probe_not_ready')
    if SNAPSHOT.exists():raise ValueError('immutable_snapshot_exists')
    old=pd.read_csv(BASE/'physical_epoch_daily.csv',dtype=str).fillna('');oldkeys=set(zip(old.vt_symbol,old.date));epochs=pd.read_csv(BASE/'physical_epochs.csv',dtype=str).fillna('').to_dict('records')
    records=[];rejected=[];future_rows=0;overlaps=[]
    for status in receipt['contract_statuses']:
        symbol=status['vt_symbol'];path=Path(status['raw_path'])
        if sha(path)!=status['raw_sha256']:raise ValueError('raw_source_changed:'+symbol)
        raw=pd.read_csv(path);raw=raw.loc[pd.to_numeric(raw.datetime).gt(0)&pd.to_numeric(raw.id).ge(0)].copy()
        raw['date']=pd.to_datetime(pd.to_numeric(raw.datetime),unit='ns',utc=True).dt.tz_convert(TZ).dt.strftime('%Y-%m-%d')
        if raw.date.duplicated().any():raise ValueError('duplicate_raw_daily:'+symbol)
        future_rows+=int(raw.date.gt(TARGET).sum())
        for row in raw.to_dict('records'):
            day=row['date']
            if not permitted_key(symbol,day):continue
            if 'duration' not in row or int(row['duration'])!=86400:raise ValueError('not_real_daily:'+symbol)
            ep=bind_physical(symbol,day,epochs)
            if (symbol,day) in oldkeys:
                prev=old.loc[old.vt_symbol.eq(symbol)&old.date.eq(day)].iloc[0]
                differences={f:dict(frozen=float(prev[f]),fresh=float(row[f])) for f in FIELDS if float(prev[f])!=float(row[f])}
                overlaps.append(dict(vt_symbol=symbol,date=day,source_observation_only=True,frozen_preserved=True,differences=differences));continue
            try:values=validate_daily(row)
            except (ValueError,TypeError,KeyError):
                rejected.append(dict(vt_symbol=symbol,date=day,classification='raw_zero_or_invalid_not_bar',raw_path=str(path),raw_sha256=status['raw_sha256'],source_locator=json.dumps({'id':row.get('id'),'datetime_ns':row.get('datetime'),'date':day}),volume=row.get('volume')));continue
            records.append(dict(vt_symbol=symbol,date=day,contract_epoch_id=ep['contract_epoch_id'],contract_yyyymm=ep['contract_yyyymm'],**values,source_id=AUTHORITY,source_path=str(path),source_sha256=status['raw_sha256'],source_locator=json.dumps({'date':day,'id':row.get('id'),'datetime_ns':row.get('datetime')},ensure_ascii=False),lifecycle_status=ep['lifecycle_status'],admission_reason='predeclared_latest_completed_day_or_missing_CU202612_week_sources'))
    new=pd.DataFrame(records,columns=list(old.columns))
    if new.duplicated(['vt_symbol','date']).any():raise ValueError('duplicate_new_daily')
    targets=pd.read_csv(PROBE/'target_mapping.csv');present=set(zip(new.vt_symbol,new.date))|oldkeys
    main_missing=[dict(vt_symbol=s,date=TARGET) for s in targets.main_contract_vt if (s,TARGET) not in present]
    cu_missing=[d for d in ['2026-10-19','2026-10-20','2026-10-21','2026-10-22','2026-10-23'] if ('cu2612.SHFE',d) not in present]
    pd.DataFrame(rejected,columns=['vt_symbol','date','classification','raw_path','raw_sha256','source_locator','volume']).to_csv(PROBE/'rejected_not_bars.csv',index=False)
    dump(PROBE/'frozen_overlap_observations.json',overlaps)
    if main_missing or cu_missing:
        dump(PROBE/'admission_failure.json',dict(main_missing=main_missing,cu_missing_week_sources=cu_missing,rejected=rejected,no_fallback=True));raise ValueError('required_new_main_or_CU_week_sources_unavailable')
    SNAPSHOT.mkdir()
    for name in ['metadata.csv','physical_epochs.csv','known_lifecycle_excluded.csv','known_no_trade_main.csv','structural_unavailable_main.csv','warmup_missing_main_2014.csv']:
        shutil.copyfile(BASE/name,SNAPSHOT/name)
    # Append source CSV lines verbatim; every frozen row, identity and source locator is byte-preserved.
    with (SNAPSHOT/'physical_epoch_daily.csv').open('wb') as dst:
        original=(BASE/'physical_epoch_daily.csv').read_bytes();dst.write(original)
        if original and not original.endswith(b'\n'):raise ValueError('base_csv_missing_terminal_newline')
        dst.write(new.to_csv(index=False,header=False).encode())
    old_mapping_bytes=(BASE/'mapping.csv').read_bytes()
    with (SNAPSHOT/'mapping.csv').open('wb') as dst:
        dst.write(old_mapping_bytes)
        if not old_mapping_bytes.endswith(b'\n'):raise ValueError('base_mapping_missing_terminal_newline')
        dst.write(targets.to_csv(index=False,header=False).encode())
    new.to_csv(SNAPSHOT/'admitted_new_daily.csv',index=False);targets.to_csv(SNAPSHOT/'admitted_new_mapping.csv',index=False)
    pd.DataFrame(rejected,columns=['vt_symbol','date','classification','raw_path','raw_sha256','source_locator','volume']).to_csv(SNAPSHOT/'new_missing_or_zero_not_bar.csv',index=False)
    pd.DataFrame(columns=['date','main_contract_vt','reason']).to_csv(SNAPSHOT/'missing_main.csv',index=False)
    shutil.copyfile(BASE/'daily.sqlite',SNAPSHOT/'daily.sqlite')
    with sqlite3.connect(SNAPSHOT/'daily.sqlite') as db:
        for row in records:
            code,exchange=row['vt_symbol'].split('.')
            found=db.execute("select count(*) from dbbardata where symbol=? and exchange=? and interval='d' and substr(datetime,1,10)=?",(code,exchange,row['date'])).fetchone()[0]
            if found:raise ValueError('new_key_already_in_database:'+row['vt_symbol']+':'+row['date'])
            db.execute("insert into dbbardata(symbol,exchange,datetime,interval,volume,turnover,open_interest,open_price,high_price,low_price,close_price) values(?,?,?,'d',?,0,?,?,?,?,?)",(code,exchange,row['date']+' 00:00:00',row['volume'],row['close_oi'],row['open'],row['high'],row['low'],row['close']))
        for symbol in sorted(set(new.vt_symbol)):
            code,exchange=symbol.split('.');count,begin,end=db.execute("select count(*),min(datetime),max(datetime) from dbbardata where symbol=? and exchange=? and interval='d'",(code,exchange)).fetchone()
            db.execute("delete from dbbaroverview where symbol=? and exchange=? and interval='d'",(code,exchange));db.execute("insert into dbbaroverview(symbol,exchange,interval,count,start,end) values(?,?,'d',?,?,?)",(code,exchange,count,begin,end))
        db.commit()
        if db.execute('pragma integrity_check').fetchone()[0]!='ok':raise ValueError('snapshot_integrity_failed')
        db.execute('attach database ? as frozen',(str(BASE/'daily.sqlite'),))
        old_count=db.execute('select count(*) from frozen.dbbardata').fetchone()[0]
        old_missing=db.execute('select count(*) from (select * from frozen.dbbardata except select * from main.dbbardata)').fetchone()[0]
        new_count=db.execute('select count(*) from main.dbbardata').fetchone()[0]
        if old_missing or new_count!=old_count+len(new):raise ValueError('frozen_database_rows_changed')
        parity=[]
        for row in records:
            code,exchange=row['vt_symbol'].split('.')
            values=db.execute("select open_price,high_price,low_price,close_price,volume,open_interest from main.dbbardata where symbol=? and exchange=? and interval='d' and substr(datetime,1,10)=?",(code,exchange,row['date'])).fetchall()
            if values!=[tuple(row[k] for k in FIELDS)]:raise ValueError('new_database_field_parity_failed')
    # Parse and compare all frozen fields after the append, not only prices.
    merged=pd.read_csv(SNAPSHOT/'physical_epoch_daily.csv',dtype=str).fillna('')
    prefix_equal=merged.iloc[:len(old)].reset_index(drop=True).equals(old.reset_index(drop=True))
    mapping=pd.read_csv(SNAPSHOT/'mapping.csv',dtype=str).fillna('');oldmap=pd.read_csv(BASE/'mapping.csv',dtype=str).fillna('')
    if not prefix_equal or not mapping.iloc[:len(oldmap)].reset_index(drop=True).equals(oldmap):raise ValueError('frozen_csv_rows_changed')
    if merged.duplicated(['vt_symbol','date']).any():raise ValueError('merged_duplicate_daily')
    oldreceipt=json.loads((BASE/'receipt.json').read_text())
    coverage=dict(old_accepted_rows=len(old),new_accepted_rows=len(new),accepted_rows=len(merged),old_physical_rows_all_fields_exact=prefix_equal,old_physical_csv_bytes_prefix_exact=(SNAPSHOT/'physical_epoch_daily.csv').read_bytes().startswith(original),old_mapping_rows_all_fields_exact=True,old_mapping_bytes_prefix_exact=(SNAPSHOT/'mapping.csv').read_bytes().startswith(old_mapping_bytes),old_database_all_rows_preserved=old_missing==0,old_database_rows=old_count,new_database_rows=new_count,new_database_field_parity=True,metadata_bytes_unchanged=sha(BASE/'metadata.csv')==sha(SNAPSHOT/'metadata.csv'),physical_epochs_bytes_unchanged=sha(BASE/'physical_epochs.csv')==sha(SNAPSHOT/'physical_epochs.csv'),forming_future_raw_rows_excluded=future_rows,rejected_raw_not_bars=len(rejected),fresh_main_positive_valid_rows=19,cu2612_missing_week_days=[],no_price_or_date_fallback=True)
    dump(SNAPSHOT/'additive_preservation_proof.json',coverage)
    output_receipt={**oldreceipt,'schema':'stage029_additive_history_data_receipt_v1','status':'prepared_additive_Tq_latest_daily','date_end':TARGET,'data_ready':True,'data_ready_for_bounded_replay':True,'accepted_rows':len(merged),'source_authority':AUTHORITY,'source_consensus_claim':False,'base_data_directory':str(BASE),'base_receipt_sha256':sha(BASE/'receipt.json'),'base_source_manifest_sha256':sha(BASE/'source_manifest.json'),'latest_probe_directory':str(PROBE),'latest_probe_receipt_sha256':sha(PROBE/'probe_receipt.json'),'financial_replays':0,'promotion_decision':'NO_PROMOTION','original_inputs_unchanged':True,'new_data':coverage,'latest_day_is_completed_week':False,'next_trading_date':receipt['next_trading_date'],'completed_at':datetime.now(TZ).isoformat(),'readiness_limitations':oldreceipt['readiness_limitations']+['New Tq authority was declared before finance; no multi-source consensus or PIT claim.','Only 10/26 and missing CU202612 10/19-23 bars may be added; true zero/missing offmain days are not tradable bars. Strict held/traded-day positivity remains mandatory.','10/26 is an incomplete new week; ordinary weekly signal cannot consume it.']}
    changed=[p for p,d in files.items() if sha(p)!=d]
    if changed:raise ValueError('frozen_input_changed_after_assembly:'+repr(changed))
    dump(SNAPSHOT/'receipt.json',output_receipt)
    manifest=dict(files)
    for p in [*PROBE.rglob('*'),*SNAPSHOT.rglob('*')]:
        if p.is_file():manifest[str(p)]=sha(p)
    dump(SNAPSHOT/'source_manifest.json',dict(schema='stage029_history_source_manifest_v1',files=manifest,source_manifest_self_not_in_files=True,financial_replays=0,immutable_output=True))
    return output_receipt


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--assemble-only',action='store_true');args=parser.parse_args()
    files=frozen_inputs();dump(OUT/('assembly_inputs.json' if args.assemble_only else 'initial_inputs.json'),files)
    if not args.assemble_only:
        result=probe(files)
        if result['status']!='raw_daily_probe_ready':
            print(json.dumps({k:result.get(k) for k in ['status','failure_stage','error_type','original_inputs_unchanged']}));return
    try:
        result=assemble(files)
        print(json.dumps(dict(status=result['status'],data_ready=result['data_ready'],date_end=result['date_end'],accepted_rows=result['accepted_rows'],new_data=result['new_data'],data_dir=str(SNAPSHOT)),ensure_ascii=False),flush=True)
    except Exception as exc:
        dump(PROBE/'assembly_failure.json',dict(status='failed_assembly',error_type=type(exc).__name__,error=str(exc),financial_replays=0,original_inputs_unchanged=all(sha(p)==d for p,d in files.items()),completed_at=datetime.now(TZ).isoformat()))
        print(json.dumps(dict(status='failed_assembly',error_type=type(exc).__name__,error=str(exc))),flush=True)
        raise

if __name__=='__main__':main()
