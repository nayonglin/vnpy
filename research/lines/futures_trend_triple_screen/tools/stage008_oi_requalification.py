"""Zero-network requalification of fixed Stage007 bytes under proven OI semantics."""
from __future__ import annotations
import argparse
import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[4]
LINE=ROOT/'research/lines/futures_trend_triple_screen'
PROJECT=ROOT/'examples/portfolio_backtesting'
PRIOR=LINE/'outputs/stage007_tqsdk_stream_probe'
ATTEMPT=PRIOR/'network_attempt1'
OUTPUT=LINE/'outputs/stage008_oi_requalification'
PROTOCOL=LINE/'stages/20261017_2349_stage008_oi_semantics_requalification_protocol.md'
IMPORTER=PROJECT/'import_tqsdk_all_futures_daily_to_db.py'
DATABASE=ROOT/'.vntrader/database.db'
DAILY_CSV=PROJECT/'downloaded_futures/tqsdk_daily_2010_2026_04/SHFE/rb2010.csv'
MAPPING=PROJECT/'backtest_outputs/tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv'
VALUES=['open','high','low','close','volume','open_oi','close_oi']
SYMBOL='rb2010.SHFE'
TARGET='2020-08-12'
RAW_SHA='0805e7083b24e988469bee78fabc53419d2855e85f92928256a184d9db9480ac'
EVIDENCE_SHA='3eecacbf83069daac6e0508b5ebdb79e6db50ba60b89b1486d76ce2979f8aff2'
QUALITY_SHA='9bf02a770b12c7fe65d2efb105e3bfc4f29227d2961352eb0a614a6d5eb6625e'
sys.path.insert(0,str(PROJECT))
from qmt_roll_intraday_execution import session_minutes


def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb')as source:
        for chunk in iter(lambda:source.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def write_json(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def field_checks(aggregate,csv_daily,database):
    checks=[]
    for source,reference,mapping in [
        ('csv',csv_daily,{key:key for key in VALUES}),
        ('database',database,{**{key:key for key in ['open','high','low','close','volume']},'open_interest':'open_oi'}),
    ]:
        for source_field,aggregate_field in mapping.items():
            actual=float(aggregate[aggregate_field]);expected=float(reference[source_field])
            finite=bool(np.isfinite(actual)and np.isfinite(expected))
            checks.append(dict(source=source,source_field=source_field,aggregate_field=aggregate_field,
                reference_value=expected if np.isfinite(expected)else None,
                aggregate_value=actual if np.isfinite(actual)else None,
                absolute_difference=abs(actual-expected)if finite else None,
                matches=bool(finite and np.isclose(actual,expected,rtol=1e-12,atol=1e-8))))
    return checks


def completion_check(evidence,expected):
    expected=pd.DatetimeIndex(expected)
    observed=pd.to_datetime(evidence.bar_datetime,errors='coerce')
    successor=pd.to_datetime(evidence.successor_time,errors='coerce')
    valid=not observed.isna().any()and not successor.isna().any()
    valid=bool(valid and len(evidence)==len(expected)and not observed.duplicated().any()
        and set(observed)==set(expected)and evidence.vt_symbol.eq(SYMBOL).all()
        and evidence.method.eq('observed_later_serial_kline').all()
        and evidence.completed.astype(str).str.lower().eq('true').all())
    forward=bool((successor>=observed+pd.Timedelta(minutes=1)).all())
    return dict(accepted=bool(valid and forward),evidence_rows=len(evidence),expected_minutes=len(expected),
        missing_evidence_minutes=len(set(expected)-set(observed)),all_successors_forward=forward,
        final_target_time=expected[-1].isoformat(),
        final_successor_time=str(evidence.loc[observed.eq(expected[-1]),'successor_time'].iloc[0])
            if observed.eq(expected[-1]).sum()==1 else None)


def minute_check(raw,expected):
    raw=raw.copy();raw['bar_datetime']=pd.to_datetime(raw.bar_datetime,errors='raise')
    unique=not raw.bar_datetime.duplicated().any()
    grid=bool(len(raw)==len(expected)and set(raw.bar_datetime)==set(expected)and raw.vt_symbol.eq(SYMBOL).all())
    numeric=raw[VALUES].apply(pd.to_numeric,errors='coerce')
    prices=numeric[['open','high','low','close']]
    legal=bool(np.isfinite(numeric.to_numpy()).all()and (prices>0).all().all()
        and(numeric[['volume','open_oi','close_oi']]>=0).all().all()
        and(numeric.low<=numeric[['open','close']].min(axis=1)).all()
        and(numeric.high>=numeric[['open','close']].max(axis=1)).all())
    aggregate=None
    if unique and grid and legal:
        ordered=raw.sort_values('bar_datetime')[VALUES].astype(float)
        aggregate=dict(open=float(ordered.open.iloc[0]),high=float(ordered.high.max()),low=float(ordered.low.min()),
            close=float(ordered.close.iloc[-1]),volume=float(ordered.volume.sum()),
            open_oi=float(ordered.open_oi.iloc[0]),close_oi=float(ordered.close_oi.iloc[-1]))
    return dict(accepted=bool(unique and grid and legal),rows=len(raw),unique_keys=bool(unique),
        exact_target_grid=grid,legal_ohlcvoi=legal,aggregate=aggregate)


def importer_semantics():
    tree=ast.parse(IMPORTER.read_text());matches=[]
    for node in ast.walk(tree):
        if not isinstance(node,ast.keyword)or node.arg!='open_interest':continue
        reads=[call for call in ast.walk(node.value)if isinstance(call,ast.Call)
            and isinstance(call.func,ast.Name)and call.func.id=='getattr'and len(call.args)>=2
            and isinstance(call.args[0],ast.Name)and call.args[0].id=='row'
            and isinstance(call.args[1],ast.Constant)and call.args[1].value=='open_oi']
        if reads:matches.append(dict(line=node.lineno,expression=ast.unparse(node.value)))
    if len(matches)!=1:raise ValueError('importer_open_oi_semantics_not_unique')
    return dict(path=str(IMPORTER),sha256=sha256(IMPORTER),**matches[0],
        interpretation='For this known CSV importer, DB open_interest stores CSV open_oi; no independent DB closeOI exists.')


def audit():
    if OUTPUT.exists():raise FileExistsError('existing_requalification_refusing_repeat')
    OUTPUT.mkdir(parents=True,exist_ok=False);began=time.monotonic()
    write_json(OUTPUT/'attempt_started.json',dict(started_at=datetime.now().astimezone().isoformat(),
        network_calls=0,provider_replays=0,financial_strategy_replays=0))
    try:
        parent=json.loads((ATTEMPT/'parent_receipt.json').read_text())
        worker=json.loads((ATTEMPT/'worker_receipt.json').read_text())
        preflight=json.loads((PRIOR/'preflight.json').read_text())
        original=json.loads((ATTEMPT/'quality.json').read_text())
        if not(parent['exit_code']==1 and parent['all_inputs_unchanged']and worker['provider_replay_attempts']==1
            and worker['financial_strategy_replays']==0 and worker['order_calls']==0 and worker['cancel_calls']==0
            and worker['status']=='completed_quality_rejected'and original['accepted']is False
            and original['database_check']['daily_mismatch_fields']==['close_oi']):
            raise ValueError('original_probe_evidence_changed')
        if sha256(PRIOR/'preflight.json')!=parent['preflight_sha256']:raise ValueError('original_preflight_changed')
        for name,digest in parent['artifact_sha256'].items():
            if sha256(ATTEMPT/name)!=digest:raise ValueError('original_probe_artifact_changed')
        for path,digest in preflight['source_fingerprints'].items():
            if sha256(path)!=digest:raise ValueError('original_probe_input_changed')
        for name,digest in [('raw_completed_minutes.csv',RAW_SHA),('completion_evidence.csv',EVIDENCE_SHA),('quality.json',QUALITY_SHA)]:
            if sha256(ATTEMPT/name)!=digest:raise ValueError('protocol_pinned_artifact_changed')
        inputs={str(path):sha256(path)for path in [Path(__file__),PROTOCOL,IMPORTER,DATABASE,DAILY_CSV,MAPPING,
            PROJECT/'qmt_roll_intraday_execution.py',PRIOR/'preflight.json',ATTEMPT/'parent_receipt.json',
            *[ATTEMPT/name for name in parent['artifact_sha256']]]}
        semantics=importer_semantics()
        calendar=pd.DatetimeIndex(sorted(pd.to_datetime(pd.read_csv(MAPPING,usecols=['date']).date).unique()))
        position=calendar.get_indexer([pd.Timestamp(TARGET)])[0]
        expected=session_minutes(SYMBOL,TARGET,calendar[max(0,position-1):position+1])
        if len(expected)!=345:raise ValueError('target_grid_changed')
        raw=pd.read_csv(ATTEMPT/'raw_completed_minutes.csv')
        evidence=pd.read_csv(ATTEMPT/'completion_evidence.csv')
        minutes=minute_check(raw,expected);completion=completion_check(evidence,expected)
        daily=pd.read_csv(DAILY_CSV)
        selected=daily.loc[pd.to_datetime(daily.trade_date).dt.normalize().eq(pd.Timestamp(TARGET))]
        if len(selected)!=1:raise ValueError('daily_csv_target_not_unique')
        csv_daily={key:float(selected.iloc[0][key])for key in VALUES}
        wal=Path(str(DATABASE)+'-wal')
        if wal.exists()and wal.stat().st_size:raise ValueError('nonempty_database_wal')
        with sqlite3.connect(DATABASE.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)as database:
            rows=database.execute("SELECT open_price,high_price,low_price,close_price,volume,open_interest FROM dbbardata WHERE symbol=? AND exchange=? AND interval='d' AND datetime>=? AND datetime<?",('rb2010','SHFE',TARGET,'2020-08-13')).fetchall()
        if len(rows)!=1:raise ValueError('real_database_target_not_unique')
        db_daily=dict(zip(['open','high','low','close','volume','open_interest'],map(float,rows[0])))
        checks=field_checks(minutes['aggregate'],csv_daily,db_daily)if minutes['aggregate']is not None else[]
        pd.DataFrame(checks).to_csv(OUTPUT/'field_checks.csv',index=False)
        accepted=bool(minutes['accepted']and completion['accepted']and len(checks)==13 and all(row['matches']for row in checks))
        if not all(sha256(path)==digest for path,digest in inputs.items()):raise ValueError('input_changed_during_audit')
        write_json(OUTPUT/'input_manifest.json',inputs)
        result=dict(status='target_requalified_pending_independent_review'if accepted else'target_requalification_rejected',
            accepted=accepted,elapsed_seconds=time.monotonic()-began,vt_symbol=SYMBOL,target_trading_date=TARGET,
            network_calls=0,provider_replays=0,TqApi_instances=0,TqSim_instances=0,financial_strategy_replays=0,
            order_calls=0,cancel_calls=0,model_fits=0,source_writes=0,cache_or_overlay_written=False,
            execution_fallback_enabled=False,production_qualified=False,all_inputs_unchanged=True,
            raw_path=str(ATTEMPT/'raw_completed_minutes.csv'),raw_sha256=RAW_SHA,
            completion_evidence_sha256=EVIDENCE_SHA,minute_check=minutes,completion_check=completion,
            field_checks=checks,database_close_oi='N/A_not_independently_available',importer_semantics=semantics,
            original_probe=dict(provider_replay_attempts=1,status=worker['status'],exit_code=parent['exit_code'],
                quality_sha256=QUALITY_SHA,original_accepted=False,original_mismatch_fields=['close_oi'],unchanged=True),
            limitations=['Only rb2010.SHFE trading date 2020-08-12 and this proven importer source; not a whole-market OI claim.',
                'Official strategy continues using the unchanged DB OI semantics; no alpha or closeOI signal change.',
                'Research data candidate only; no base/overlay merge, C0 attempt3, fallback or deployment authorization.'])
        result['artifact_sha256']={path.name:sha256(path)for path in OUTPUT.iterdir()if path.is_file()}
        write_json(OUTPUT/'requalification.json',result)
        print(json.dumps(dict(status=result['status'],accepted=accepted,minutes=len(raw),field_checks=len(checks),network_calls=0)))
        return 0 if accepted else 1
    except BaseException as error:
        write_json(OUTPUT/'audit_failure.json',dict(error_type=type(error).__name__,error=str(error),network_calls=0,financial_strategy_replays=0))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--audit',action='store_true',required=True);parser.parse_args()
    raise SystemExit(audit())
