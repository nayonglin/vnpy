"""EMA_LIMIT identity and persistence; imports stay standard-library only."""
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Mapping
from datetime import datetime
from types import SimpleNamespace
import gzip
import hashlib
import json
import os
import pickle
import re
import uuid

ACCOUNT_ID='EMA_LIMIT'
MECHANISM_ID='stage124_ema_limit_v1'
CONTEXT_SCHEMA='stage140_ema_run_context_v1'
PREFLIGHT_SCHEMA='stage140_ema_preflight_v1'
READINESS_SCHEMA='stage140_ema_execution_readiness_v1'


@dataclass(frozen=True)
class BoundAsset:
    path: Path
    sha256: str
    bytes: int


@dataclass(frozen=True)
class EmaRun:
    run_id: str
    attempt: int
    global_attempt: int
    output: Path
    started_at: str
    fixture_only: bool


VALIDATION=dict(engine_returned=True,actual_settings_equal_reference=True,parameters_equal_reference=True,
    actual_daily_dates_equal_reference=True,captured_bar_failures=0,strict_minute_missing_bars=0,
    all_consumed_inputs_unchanged=True,frozen_sources_unchanged=True,historical_shared_input_empty=True)


def regular(path):
    path=Path(path).absolute()
    if any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('ema_symlink_source_or_destination')
    return path


def asset(path):
    path=regular(path)
    with path.open('rb')as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    return BoundAsset(path,digest,path.stat().st_size)


def read_asset(bound):
    if not isinstance(bound,BoundAsset) or not bound.path.is_absolute():raise ValueError('ema_bound_asset_required')
    raw=regular(bound.path).read_bytes()
    if len(raw)!=bound.bytes or hashlib.sha256(raw).hexdigest()!=bound.sha256:raise ValueError('ema_asset_changed:'+str(bound.path))
    return raw


def json_bytes(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False,default=str)+'\n').encode()


def write_bytes(path,raw):
    path=regular(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise FileExistsError('ema_refuse_overwrite:'+str(path))
    temporary=path.with_name('.'+path.name+'.'+uuid.uuid4().hex)
    try:
        with temporary.open('xb')as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.link(temporary,path)
    finally:
        if temporary.exists():temporary.unlink()
    return BoundAsset(path,hashlib.sha256(raw).hexdigest(),len(raw))


def write_json(path,value):return write_bytes(path,json_bytes(value))


def _verify_bindings(bindings):
    for path,binding in bindings.items():
        observed=asset(path)
        if observed.sha256!=binding['sha256']or observed.bytes!=binding['bytes']:raise ValueError('ema_binding_changed:'+path)


def _snapshot_bindings(preflight):
    files=dict(preflight['source_bindings'])
    files.update({p:b for p,b in preflight['data_bindings'].items() if Path(p).suffix in ('.md','.txt')})
    return files


def _save_source_snapshots(run,preflight):
    files={}
    for original,binding in sorted(_snapshot_bindings(preflight).items()):
        bound=BoundAsset(Path(original),binding['sha256'],binding['bytes'])
        raw=read_asset(bound)
        relative=Path('source_snapshots')/(bound.sha256+Path(original).suffix)
        target=run.output/relative
        if target.exists():read_asset(BoundAsset(target,bound.sha256,bound.bytes))
        else:write_bytes(target,raw)
        files[original]=dict(binding,snapshot_path=relative.as_posix())
    return write_json(run.output/'source_snapshot_manifest.json',dict(schema='stage140_ema_source_snapshots_v1',
        account_id=ACCOUNT_ID,run_id=run.run_id,files=files,fixture_only=run.fixture_only))


def _verify_source_snapshots(run,context,preflight):
    path=Path(context['source_snapshot_manifest_path'])
    if path!=run.output/'source_snapshot_manifest.json':raise ValueError('ema_source_snapshot_manifest_path')
    manifest=json.loads(read_asset(BoundAsset(path,context['source_snapshot_manifest_sha256'],context['source_snapshot_manifest_bytes'])))
    expected=_snapshot_bindings(preflight)
    if (manifest.get('schema')!='stage140_ema_source_snapshots_v1' or manifest.get('run_id')!=run.run_id
        or manifest.get('account_id')!=ACCOUNT_ID or manifest.get('fixture_only')is not run.fixture_only
        or set(manifest['files'])!=set(expected)):raise ValueError('ema_source_snapshot_scope')
    for original,binding in expected.items():
        item=manifest['files'][original]
        relative=Path('source_snapshots')/(binding['sha256']+Path(original).suffix)
        if item!=dict(binding,snapshot_path=relative.as_posix()):raise ValueError('ema_source_snapshot_binding')
        read_asset(BoundAsset(run.output/relative,binding['sha256'],binding['bytes']))


def start_run(*,preflight:Mapping,readiness:BoundAsset,started_at:str,global_attempt:int)->EmaRun:
    signed=json.loads(read_asset(readiness));fixture=preflight.get('fixture_only')
    expected=dict(schema=READINESS_SCHEMA,account_id=ACCOUNT_ID,mechanism_id=MECHANISM_ID,attempt=1,
        global_attempt=global_attempt,fixture_only=fixture,preflight_sha256=hashlib.sha256(json_bytes(preflight)).hexdigest(),
        source_bindings=preflight['source_bindings'],data_bindings=preflight['data_bindings'])
    if (preflight.get('schema')!=PREFLIGHT_SCHEMA or type(fixture)is not bool
        or preflight.get('account_id')!=ACCOUNT_ID or preflight.get('mechanism_id')!=MECHANISM_ID
        or preflight.get('attempt')!=1 or type(global_attempt)is not int or global_attempt<1
        or any(signed.get(k)!=v for k,v in expected.items())):raise ValueError('ema_root_readiness_binding_required')
    if fixture:
        if signed.get('issued_by')!='fixture_only' or signed.get('fixture_execution_authorized')is not True or signed.get('financial_execution_authorized')is not False:
            raise ValueError('ema_fixture_cannot_claim_financial_authorization')
    elif (signed.get('issued_by')!='root' or signed.get('financial_execution_authorized')is not True
        or signed.get('independent_integration_accepted')is not True
        or signed.get('limits_decision')!=dict(action='inherit_original_limits',wait_seconds=1800,run_seconds=7200)):
        raise ValueError('ema_real_root_financial_authorization_required')
    for group in ('source_bindings','data_bindings'):_verify_bindings(preflight[group])
    integration=BoundAsset(Path(signed['integration_review_path']),signed['integration_review_sha256'],signed['integration_review_bytes'])
    read_asset(integration)
    root=regular(preflight['account_root'])
    if not fixture and root!=Path(__file__).resolve().parents[1]/'outputs/stage140_ema_account/EMA_LIMIT':
        raise ValueError('ema_account_root_identity')
    if not fixture and (preflight.get('capital')!=150000 or len(preflight.get('reference_calendar',[]))!=1641
        or preflight.get('period')!=['2020-01-01','2026-10-14']):raise ValueError('ema_fixed_real_period_capital')
    run=EmaRun(uuid.uuid4().hex,1,global_attempt,root/uuid.uuid4().hex,started_at,fixture)
    # Directory name and run_id are one identity, including fixtures.
    run=EmaRun(run.run_id,run.attempt,run.global_attempt,root/run.run_id,run.started_at,fixture)
    run.output.mkdir(parents=True,exist_ok=False)
    preflight_asset=write_json(run.output/'preflight_used.json',preflight)
    snapshots=_save_source_snapshots(run,preflight)
    context=dict(schema=CONTEXT_SCHEMA,account_id=ACCOUNT_ID,mechanism_id=MECHANISM_ID,
        run_id=run.run_id,attempt=1,global_attempt=global_attempt,fixture_only=fixture,
        output_directory=str(run.output),started_at=started_at,preflight_path=str(preflight_asset.path),
        preflight_sha256=preflight_asset.sha256,preflight_bytes=preflight_asset.bytes,
        readiness_path=str(readiness.path),readiness_sha256=readiness.sha256,readiness_bytes=readiness.bytes,
        integration_review_path=str(integration.path),integration_review_sha256=integration.sha256,integration_review_bytes=integration.bytes,
        source_snapshot_manifest_path=str(snapshots.path),source_snapshot_manifest_sha256=snapshots.sha256,source_snapshot_manifest_bytes=snapshots.bytes,
        source_bindings=preflight['source_bindings'],data_bindings=preflight['data_bindings'],
        writer=Path(__file__).name,writer_source_sha256=asset(__file__).sha256,production_qualified=False)
    write_json(run.output/'run_context.json',context)
    return run


def load_context(run,verify_sources=True):
    context=json.loads(regular(run.output/'run_context.json').read_bytes())
    expected=dict(schema=CONTEXT_SCHEMA,account_id=ACCOUNT_ID,mechanism_id=MECHANISM_ID,run_id=run.run_id,
        attempt=run.attempt,global_attempt=run.global_attempt,output_directory=str(run.output),started_at=run.started_at,fixture_only=run.fixture_only)
    if any(context.get(k)!=v for k,v in expected.items()):raise ValueError('ema_context_identity')
    preflight=json.loads(read_asset(BoundAsset(Path(context['preflight_path']),context['preflight_sha256'],context['preflight_bytes'])))
    read_asset(BoundAsset(Path(context['readiness_path']),context['readiness_sha256'],context['readiness_bytes']))
    _verify_source_snapshots(run,context,preflight)
    if verify_sources:
        if context['writer_source_sha256']!=asset(__file__).sha256:raise ValueError('ema_writer_changed')
        for group in ('source_bindings','data_bindings'):_verify_bindings(context[group])
    return context,preflight


def run_from_context(bound):
    c=json.loads(read_asset(bound))
    run=EmaRun(c['run_id'],c['attempt'],c['global_attempt'],Path(c['output_directory']),c['started_at'],c['fixture_only'])
    if bound.path!=run.output/'run_context.json':raise ValueError('ema_context_path_identity')
    load_context(run);return run


def save_failure(run:EmaRun,partial:Mapping,error:str,phase:str)->BoundAsset:
    from stage065_account_checkpoint import _account_only
    _account_only(partial)
    capture=write_bytes(run.output/('failure_'+uuid.uuid4().hex+'.pkl.gz'),gzip.compress(pickle.dumps(dict(
        schema='stage140_ema_partial_failure_v1',partial=True,capture=partial),protocol=5),mtime=0))
    return write_json(run.output/('failure_'+uuid.uuid4().hex+'.json'),dict(schema='stage140_ema_failure_v1',
        account_id=ACCOUNT_ID,run_id=run.run_id,phase=phase,error=error,capture_path=str(capture.path),capture_sha256=capture.sha256,
        complete_performance=False,fixture_only=run.fixture_only,production_qualified=False))


def save_raw(run:EmaRun,payload:Mapping)->BoundAsset:
    from stage065_account_checkpoint import _account_only
    context,preflight=load_context(run,verify_sources=False)
    required={'combined','frames','capture','actual_trade_identities','ema','actual','parameters','spec','input_fingerprints','run_context','preflight'}
    if not required.issubset(payload) or payload.get('combined')is None or not payload.get('frames'):
        raise ValueError('ema_incomplete_engine_return')
    if payload['run_context']!=context or payload['preflight']!=preflight:raise ValueError('ema_payload_identity')
    if set(payload['ema'])!={'decision','fill','execution','budget','pending'}:raise ValueError('ema_capture_scope')
    _account_only(payload)
    raw=write_bytes(run.output/'checkpoint/raw_account.pkl.gz',gzip.compress(pickle.dumps(dict(payload,
        schema='stage140_ema_raw_account_v1'),protocol=5),mtime=0))
    write_json(run.output/'checkpoint/raw_manifest.json',dict(schema='stage140_ema_raw_manifest_v1',
        account_id=ACCOUNT_ID,mechanism_id=MECHANISM_ID,run_id=run.run_id,raw_path=str(raw.path),raw_sha256=raw.sha256,
        raw_bytes=raw.bytes,context_sha256=asset(run.output/'run_context.json').sha256,
        fixture_only=run.fixture_only,status='raw_not_validated',production_qualified=False))
    return raw


def seal_raw(run:EmaRun,raw:BoundAsset,validation:Mapping)->BoundAsset:
    context,preflight=load_context(run);read_asset(raw)
    manifest=json.loads((run.output/'checkpoint/raw_manifest.json').read_bytes())
    if (raw.path!=run.output/'checkpoint/raw_account.pkl.gz' or raw.sha256!=manifest['raw_sha256']
        or raw.bytes!=manifest['raw_bytes'] or manifest['run_id']!=run.run_id
        or manifest['context_sha256']!=asset(run.output/'run_context.json').sha256
        or any(type(validation.get(k))is not type(v)or validation[k]!=v for k,v in VALIDATION.items())
        or validation.get('actual_daily_count')!=len(preflight['reference_calendar'])
        or validation.get('fixture_only')is not run.fixture_only):raise ValueError('ema_validation_not_passed')
    return write_json(run.output/'checkpoint/validation_seal.json',dict(schema='stage140_ema_validation_seal_v1',
        account_id=ACCOUNT_ID,run_id=run.run_id,raw_sha256=raw.sha256,raw_manifest_sha256=asset(run.output/'checkpoint/raw_manifest.json').sha256,
        context_sha256=manifest['context_sha256'],validation=dict(validation),fixture_only=run.fixture_only,production_qualified=False))


def load_sealed(run:EmaRun)->tuple[Mapping,Mapping]:
    context,preflight=load_context(run)
    manifest_asset=asset(run.output/'checkpoint/raw_manifest.json');manifest=json.loads(read_asset(manifest_asset))
    raw=BoundAsset(Path(manifest['raw_path']),manifest['raw_sha256'],manifest['raw_bytes'])
    seal_asset=asset(run.output/'checkpoint/validation_seal.json');seal=json.loads(read_asset(seal_asset))
    if (manifest.get('schema')!='stage140_ema_raw_manifest_v1' or manifest.get('run_id')!=run.run_id
        or manifest.get('account_id')!=ACCOUNT_ID or manifest.get('mechanism_id')!=MECHANISM_ID
        or manifest.get('fixture_only')is not run.fixture_only
        or manifest.get('context_sha256')!=asset(run.output/'run_context.json').sha256
        or seal.get('schema')!='stage140_ema_validation_seal_v1' or seal.get('run_id')!=run.run_id
        or seal.get('account_id')!=ACCOUNT_ID or seal.get('fixture_only')is not run.fixture_only
        or seal.get('raw_sha256')!=raw.sha256 or seal.get('raw_manifest_sha256')!=manifest_asset.sha256
        or seal.get('context_sha256')!=asset(run.output/'run_context.json').sha256
        or raw.path!=run.output/'checkpoint/raw_account.pkl.gz'):raise ValueError('ema_seal_binding')
    validation=seal['validation']
    if (any(type(validation.get(k))is not type(v)or validation[k]!=v for k,v in VALIDATION.items())
        or type(validation.get('actual_daily_count'))is not int or validation['actual_daily_count']!=len(preflight['reference_calendar'])
        or validation.get('fixture_only')is not run.fixture_only):raise ValueError('ema_invalid_seal_validation')
    payload=pickle.loads(gzip.decompress(read_asset(raw)))
    if payload.get('schema')!='stage140_ema_raw_account_v1' or payload['run_context']!=context or payload['preflight']!=preflight:
        raise ValueError('ema_raw_owner_identity')
    return payload,dict(manifest=manifest,seal=seal,seal_sha256=seal_asset.sha256,raw_manifest_sha256=manifest_asset.sha256)


def export_sealed(run:EmaRun,destination:Path)->dict:
    """Pure native table export; no preparation, data loader, engine or model."""
    import pandas as pd
    from stage022_run_c0_qualified_wait import canonical_trade_enums,attach_trading_dates
    from stage031_run_ordered_checkpoint import build_execution_clock
    from analyze_qmt_roll_stage650_stage526_200k_capital_reality_check import _metrics
    if (run.output/'export_success.json').exists():raise FileExistsError('ema_success_refusing_duplicate_export')
    payload,binding=load_sealed(run);destination=regular(destination)
    if destination.parent!=run.output/'exports' or not re.fullmatch(r'export_[0-9]{3,4}',destination.name):raise ValueError('ema_export_destination_identity')
    destination.mkdir(parents=True,exist_ok=False)
    try:
        clock,usage=build_execution_clock(payload['capture'],payload['actual_trade_identities'])
        frames={k:v.copy(deep=True)for k,v in payload['frames'].items()}
        trades=canonical_trade_enums(frames['trades'])
        if trades.empty or set(trades.trade_id)!=set(clock.trade_id):raise ValueError('ema_native_trade_clock_identity')
        truth=pd.DataFrame(payload['actual_trade_identities']).set_index('trade_id',verify_integrity=True)
        for field in ('research_mechanism','economic_mother_id'):
            trades[field]=trades.trade_id.map(truth[field])
        frames['trades']=attach_trading_dates(trades,clock)
        tables={**frames,'daily':payload['combined'],'execution_clock':clock,'execution_proxy_usage':usage,
            'actual_trade_identities':pd.DataFrame(payload['actual_trade_identities']),
            'internal_equity_daily':pd.DataFrame(payload['capture'].get('equity',[]))}
        tables.update({'ema_'+k+'_audit':pd.DataFrame(v)for k,v in payload['ema'].items()})
        artifacts={}
        for name,frame in tables.items():
            if not re.fullmatch('[A-Za-z0-9_]+',name):raise ValueError('ema_table_name')
            if frame.empty and not len(frame.columns):frame=pd.DataFrame(columns=['date','vt_symbol','event','reason'])
            artifacts[name+'.csv']=write_bytes(destination/(name+'.csv'),frame.to_csv(index=False).encode('utf-8-sig')).sha256
        metrics=_metrics(payload['combined'],SimpleNamespace(**payload['spec']['capital']),1.0)
        summary=dict(schema='stage140_ema_export_v1',account_id=ACCOUNT_ID,mechanism_id=MECHANISM_ID,run_id=run.run_id,
            source_raw_sha256=binding['manifest']['raw_sha256'],seal_sha256=binding['seal_sha256'],statistics=metrics,
            artifacts=artifacts,fixture_only=run.fixture_only,financial_replays_this_export=0,production_qualified=False)
        completed=write_json(destination/'summary.json',summary)
        write_json(run.output/'export_success.json',dict(schema='stage140_ema_export_success_v1',run_id=run.run_id,
            summary_path=str(completed.path),summary_sha256=completed.sha256,summary_bytes=completed.bytes,
            raw_sha256=binding['manifest']['raw_sha256'],fixture_only=run.fixture_only))
        return summary
    except BaseException as error:
        write_json(destination/'export_failure.json',dict(schema='stage140_ema_export_failure_v1',run_id=run.run_id,
            raw_preserved=True,error=repr(error),fixture_only=run.fixture_only));raise
