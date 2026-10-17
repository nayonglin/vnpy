"""Independently accept complete actual-request packets from frozen Stage037 or Stage041.

CLI: --packet-dir ABS [ABS...] --terminal-sha256 SHA [SHA...].
Success: exit 0, JSON status=accepted with immutable receipt path/SHA.
Failure: exit 1, JSON status=blocked. Never writes an engine response.
Only provider delivery is supported. Daily/local preparation is a separate tool.
"""
from pathlib import Path
from datetime import datetime
import argparse
import json
import sys

LINE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(LINE/'tools'))
import numpy as np
import pandas as pd
import stage002_local_minute_overlay as old
import stage021_blocking_data_gate as gate
import stage037_b_ts_request_provider as provider037
import stage041_exact_daily_request_provider as provider041

PROVIDERS=((provider037,'19c9a83e83f2d69b70446cd49a8c84201c44e65a4f20380b0aaa8698ca2786d1'),
    (provider041,'e4320208cc70d25959db7f66b80518ac0f6ceaaf3e6a61a97bdfc23f008bfa0d'))
GATE_SHA='150dd70a264f360046f6d633829a4dff9a81c371c34bad6288e41a081bbb498b'
REVIEWER='root_scope_adapter_of_independent_043_runtime_old_key_protected'
OUTPUT=LINE/'outputs/stage048_general_provider_delivery'
PROTOCOL=LINE/'stages/20261018_0429_stage048_general_provider_physical_key_contract.md'


def read(path):return json.loads(Path(path).read_text())
def write(path,value):
    with Path(path).open('x')as f:f.write(json.dumps(old.safe(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def keys(frame):return {(str(r.vt_symbol),pd.Timestamp(r.bar_datetime))for r in frame.itertuples(index=False)}
def legal(frame):
    n=frame[old.VALUES].to_numpy(dtype=float)
    return bool(np.isfinite(n).all()and(frame[['open','high','low','close']]>0).all().all()and
        (frame[['volume','open_oi','close_oi']]>=0).all().all()and
        (frame.low<=frame[['open','close']].min(axis=1)).all()and(frame.high>=frame[['open','close']].max(axis=1)).all())


def select_provider(folders):
    selected=[]
    for folder in folders:
        folder=Path(folder).resolve()
        matches=[item for item in PROVIDERS if folder.is_relative_to(item[0].OUTPUT.resolve())]
        if len(matches)!=1:raise ValueError('provider_packet_family_not_allowed')
        selected.append(matches[0])
    if not selected or any(item[1]!=selected[0][1]for item in selected):
        raise ValueError('one_request_must_not_mix_provider_families')
    return selected[0]


def new_physical_data(data,request):
    required=set();existing=set()
    for target in request['requirements']:
        symbol=str(target['vt_symbol'])
        rows=[(symbol,pd.Timestamp(t))for t in target['required_timestamps']]
        before=[(symbol,pd.Timestamp(t))for t in target['existing_source_timestamps']]
        missing=[(symbol,pd.Timestamp(t))for t in target['missing_or_unqualified_timestamps']]
        if(len(set(rows))!=len(rows)or len(set(before))!=len(before)or len(set(missing))!=len(missing)or
            not missing or not set(before).issubset(rows)or not set(missing).issubset(rows)or
            not(set(rows)-set(before)).issubset(missing)):
            raise ValueError('actual_required_existing_missing_scope_invalid')
        if required.intersection(rows):raise ValueError('duplicate_requirement_key')
        required.update(rows);existing.update(before)
    if keys(data)!=required:raise ValueError('data_not_equal_complete_actual_requirement_keys')
    mask=[(str(row.vt_symbol),pd.Timestamp(row.bar_datetime))not in existing for row in data.itertuples(index=False)]
    return data.loc[mask].copy(),len(existing)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet-dir',nargs='+',type=Path,required=True)
    parser.add_argument('--terminal-sha256',nargs='+',required=True)
    args=parser.parse_args()
    assert len(args.packet_dir)==len(args.terminal_sha256)>0
    provider,SOURCE_SHA=select_provider(args.packet_dir)
    inputs={}
    def bind(path,expected=None):
        path=Path(path).resolve();digest=old.sha256(path)
        assert expected is None or digest==expected,'bound_source_changed:'+str(path)
        assert str(path)not in inputs or inputs[str(path)]==digest
        inputs[str(path)]=digest
        return digest
    bind(Path(__file__))
    bind(PROTOCOL)
    bind(Path(provider.__file__),SOURCE_SHA);bind(Path(gate.__file__),GATE_SHA)
    packets=[];request=None;digest=None;all_data=[];all_evidence=[];all_targets=[];packet_audits=[]
    for folder,terminal_sha in zip(args.packet_dir,args.terminal_sha256):
        folder=folder.resolve();manifest=provider.read_packet(folder)
        assert not manifest['fixture_scope']
        observed=folder/'terminal_observed.json';bind(observed,terminal_sha);terminal=read(observed)
        assert terminal['schema']=='stage041_provider_actual_tool_terminal_v1'and terminal['terminal_observed']is True
        assert terminal['exit_code']==terminal['worker_exit_code']==0 and terminal['all_inputs_unchanged']is True
        assert terminal['source_sha256']==SOURCE_SHA and terminal['parent_status']=='worker_terminal'
        assert terminal.get('new_provider_connections')==terminal.get('new_minute_provider_connections')==1
        assert terminal.get('financial_replays')==terminal.get('model_fits')==terminal.get('orders')==0
        bind(folder/'preflight.json',terminal['preflight_sha256']);preflight=read(folder/'preflight.json')
        bind(folder/'packet_manifest.json')
        assert preflight['source_fingerprints'][str(Path(provider.__file__).resolve())]==SOURCE_SHA
        for path,expected in preflight['source_fingerprints'].items():bind(path,expected)
        current,_=provider.read_request(manifest['request_path'],manifest['request_file_sha256'])
        if request is None:request=current;digest=current['request_sha256']
        assert current==request and terminal['request_sha256']==digest==manifest['request_sha256']==preflight['request_sha256']
        assert manifest['packet_count']==preflight['packet_count']and manifest['packet_index']==preflight['packet_index']
        attempt=folder/'network_attempt1';parent_path=attempt/'parent_receipt.json'
        bind(parent_path,terminal['parent_receipt_sha256']);parent=read(parent_path)
        assert parent['status']=='worker_terminal'and parent['exit_code']==0 and parent['all_inputs_unchanged']and not parent['hard_kill']
        assert parent['request_sha256']==digest and parent['provider_attempts_max']==1 and not parent['automatic_retry']
        assert parent['packet_index']==manifest['packet_index']and parent['packet_count']==manifest['packet_count']
        assert parent['elapsed_seconds']<600 and parent['response_written']is False and not parent['production_qualified']
        for name,expected in parent['artifact_sha256'].items():bind(attempt/name,expected)
        worker=read(attempt/'worker_receipt.json');quality=read(attempt/'quality.json')
        assert worker['status']=='all_target_minutes_completed'and worker['request_sha256']==digest
        assert worker['provider_attempts']==1 and worker['local_TqSim_created']is True
        assert worker['completed_minutes']==worker['target_minutes']==manifest['packet_required_minutes']
        assert quality['packet_all_targets_accepted']is True and quality['request_sha256']==digest
        for item in [parent,worker]:
            assert all(item[key]==0 for key in ['financial_replays','orders','cancels','broker_or_ctp_connections'])
            assert not item['credential_values_saved']and not item['raw_sdk_output_saved']and not item['cache_or_overlay_written']
        raw=old.normal_times(pd.read_csv(attempt/'raw_completed_minutes.csv'))
        evidence=old.normal_times(pd.read_csv(attempt/'completion_evidence.csv'))
        assert set(raw.columns)==set(gate.FIELDS)and not old.minute_keys(raw).has_duplicates and legal(raw)
        assert not old.minute_keys(evidence).has_duplicates and keys(raw)==keys(evidence)
        expected={(row['vt_symbol'],pd.Timestamp(stamp))for row in manifest['targets']for stamp in row['required_timestamps']}
        assert keys(raw)==expected and len(raw)==manifest['packet_required_minutes']
        assert evidence.completed.astype(str).str.lower().eq('true').all()
        assert evidence.method.eq('observed_later_serial_kline').all()
        successor=pd.to_datetime(evidence.successor_time)
        if successor.dt.tz is not None:successor=successor.dt.tz_convert('Asia/Shanghai').dt.tz_localize(None)
        evidence['successor_time']=successor
        assert (successor>=evidence.bar_datetime+pd.Timedelta(minutes=1)).all()
        inside=sum((str(row.vt_symbol),pd.Timestamp(row.successor_time))in expected for row in evidence.itertuples(index=False))
        # Outside-target successor timestamps are actual observations of the pinned
        # collector, not reconstructed OHLC rows or fabricated clock increments.
        packet_audits.append(dict(packet_dir=str(folder),packet_index=manifest['packet_index'],rows=len(raw),
            completion_rows=len(evidence),successors_also_in_delivered_raw=inside,
            observed_successors_outside_target=len(evidence)-inside,
            last_evidence=evidence.iloc[-1].to_dict(),root_terminal_path=str(observed),root_terminal_sha256=terminal_sha,
            provider_elapsed_seconds=parent['elapsed_seconds']))
        all_data.append(raw);all_evidence.append(evidence);all_targets.extend(manifest['targets']);packets.append(manifest)
    count=packets[0]['packet_count']
    assert len(packets)==count and {p['packet_index']for p in packets}==set(range(count))
    assert all(p['packet_count']==count for p in packets)
    data=pd.concat(all_data,ignore_index=True).sort_values(['vt_symbol','bar_datetime']).reset_index(drop=True)
    evidence=pd.concat(all_evidence,ignore_index=True).sort_values(['vt_symbol','bar_datetime']).reset_index(drop=True)
    assert not old.minute_keys(data).has_duplicates and not old.minute_keys(evidence).has_duplicates
    wanted={(r['vt_symbol'],r['execution_trade_date'],r['requirement_kind']):r for r in request['requirements']}
    targets={(r['vt_symbol'],r['execution_trade_date'],r['requirement_kind']):r for r in all_targets}
    assert len(wanted)==len(request['requirements'])==len(targets)==len(all_targets)and set(wanted)==set(targets)
    calendar=pd.DatetimeIndex(pd.to_datetime(sorted(pd.read_csv(old.MAPPING,usecols=['date']).date.unique())))
    bind(old.MAPPING)
    accepted=[];sessions=[]
    for identity,target in targets.items():
        symbol,day,kind=identity;original=wanted[identity]
        for name in ['required_timestamps','missing_or_unqualified_timestamps','existing_source_timestamps']:assert target[name]==original[name]
        grid=old.session_grid(symbol,day,calendar);required=grid if kind=='full_session'else grid[:1]
        assert [t.isoformat()for t in required]==original['required_timestamps']
        frame=data.loc[data.vt_symbol.eq(symbol)&data.bar_datetime.isin(required)].sort_values('bar_datetime')
        assert list(frame.bar_datetime)==list(required)
        reference=target['daily_reference'];reference_path=Path(target['daily_reference_path'])
        assert str(reference_path)in inputs,'unbound daily reference'
        daily=pd.read_csv(reference_path);hit=daily.loc[daily.vt_symbol.eq(symbol)&pd.to_datetime(daily.trade_date).dt.strftime('%Y-%m-%d').eq(day)]if'vt_symbol'in daily else daily.loc[pd.to_datetime(daily.trade_date).dt.strftime('%Y-%m-%d').eq(day)]
        assert len(hit)==1 and all(float(hit.iloc[0][name])==float(value)for name,value in reference.items())
        if target['daily_reference_source']=='independently_reviewed_exact_request_daily':
            owner=next(p for p in packets if any(t['vt_symbol']==symbol and t['execution_trade_date']==day for t in p['targets']))
            review=read(owner['daily_review_path']);bind(owner['daily_review_path'],owner['daily_review_sha256'])
            assert review['request_sha256']==digest and review['independent_review']is True and review['qualified_research_daily']is True
            assert not review['p0_findings']and not review['p1_findings']and [symbol,day]in review['accepted_target_keys']
            assert review['six_fields_checked']is True and review['actual_raw_forward_successor_checked']is True
            assert review['database_closeOI']=='N/A_not_independently_available'
            for path,expected in review['source_fingerprints'].items():bind(path,expected)
        if kind=='full_session':
            assert set(old.VALUES).issubset(reference)
            _,check=old.validate_session(frame,grid,reference,frame.iloc[:0])
            assert check['status']=='accepted'and not check['daily_mismatch_fields'],check
        else:
            assert len(frame)==1 and legal(frame)
            fields=['open']+(['open_oi']if np.isfinite(float(reference.get('open_oi',np.nan)))else[])
            assert all(np.isclose(float(frame.iloc[0][name]),float(reference[name]),rtol=1e-12,atol=1e-8)for name in fields)
            check=dict(status='accepted',reason='anchor_only_completed_daily_open_matched',expected_minutes=1,
                aggregate={name:float(frame.iloc[0][name])for name in fields},not_full_session_qualified=True)
        sessions.append(dict(vt_symbol=symbol,execution_trade_date=day,requirement_kind=kind,**check))
        accepted.append(dict(vt_symbol=symbol,execution_trade_date=day,requirement_kind=kind,accepted=True,
            completed_bars_and_daily_qualified=True,accepted_timestamps=original['required_timestamps']))
    anchors=old.A0/'execution_anchor_requests.csv';scans=old.A0/'minute_scan_requests.csv'
    bind(anchors,'72b61783602257c16b1b8c0307b0da4221430204808fdc29f21124f7556fbb20')
    bind(scans,'cedf3627a530985083839af071f997482dd417e3f2721ca21208b50b086a03ab')
    new_data,existing_count=new_physical_data(data,request)
    disjoint=old.prove_read_disjointness(new_data,pd.read_csv(anchors),pd.read_csv(scans),calendar)
    assert disjoint['path_equivalent']and disjoint['intersection_count']==0
    OUTPUT.mkdir(parents=True,exist_ok=True)
    dest=OUTPUT/('request_'+digest);dest.mkdir(exist_ok=False)
    data_path=dest/'delivery_minutes.csv';data[gate.FIELDS].to_csv(data_path,index=False);data_sha=bind(data_path)
    evidence.to_csv(dest/'completion_evidence.csv',index=False);bind(dest/'completion_evidence.csv')
    checks=dict(request_sha256=digest,rows=len(data),sessions=sessions,packets=packet_audits,A0_actual_read_disjointness=disjoint,
        request_scope_existing_physical_keys=existing_count,new_request_scope_physical_keys=len(new_data),global_existing_keys_claimed_empty=False,
        old_key_protection='Delegated to actual frozen Stage021 ensure: exact overlap seven-values before any commit; append absent keys only. Reader does not claim independent old-value reload.',
        independent_old_physical_values_reloaded=False,A0_disjoint_scope='only_actual_new_physical_keys',
        successor_boundary='Actual frozen collector observations; successor OHLC outside target is not exported or independently reconstructed.',
        source_stack_requalified=False,engine_loaded=False,network_connections_in_review=0,financial_replays=0)
    write(dest/'checks.json',checks);bind(dest/'checks.json')
    assert all(old.sha256(path)==expected for path,expected in inputs.items())
    receipt=dict(schema=gate.RECEIPT_SCHEMA,reviewed_at=datetime.now().astimezone().isoformat(),independent_review=True,
        reviewer=REVIEWER,qualified_research_data=True,p0_findings=0,p1_findings=0,p2_findings=0,
        request_sha256=digest,accepted_requirements=accepted,data_path=str(data_path),data_sha256=data_sha,source_fingerprints=inputs,
        confidence='high_for_exact_request; no profitability or all-minute-quality claim',network_connections_in_review=0,
        financial_replays=0,model_fits=0,orders=0,response_written=False,original_CSV_or_DB_modified=False,production_qualified=False)
    receipt_path=dest/'delivery_receipt.json';write(receipt_path,receipt);receipt_sha=old.sha256(receipt_path)
    parsed,full,anchor,info=gate._read_delivery(request,gate.QualifiedDelivery(receipt_path,receipt_sha))
    assert len(parsed)==len(data)and info['accepted_keys']==len(data)and len(full)+len(anchor)==len(data)
    result=dict(status='accepted',request_sha256=digest,receipt_path=str(receipt_path),receipt_sha256=receipt_sha,
        rows=len(parsed),full_keys=len(full),anchor_keys=len(anchor),actual_stage021_parser_passed=True,
        response_written=False,financial_replays=0,network_connections_in_review=0)
    write(dest/'parse_result.json',result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps(dict(status='blocked',error_type=type(error).__name__,error=str(error),response_written=False),ensure_ascii=False))
        raise SystemExit(1)
