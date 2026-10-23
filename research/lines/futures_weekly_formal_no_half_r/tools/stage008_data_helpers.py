"""G仅数据辅助：原19canonical、只缺key预取、完整proof原子发布。

volume=0的已有key仍为已有，绝不改取下一分钟；是否可执行由整窗实际fill审查。
只复用21天真实snapshot读取与既有原始proof验收，不替代成交，不推演账户。
"""
from pathlib import Path
import contextlib,io,json,os,re,sys,tempfile
import pandas as pd
ROOT=Path(__file__).resolve().parents[4]
LINE=ROOT/'research/lines/futures_weekly_formal_no_half_r';OUT=LINE/'outputs'
sys.path[:0]=[str(Path(__file__).parent),str(ROOT),str(ROOT/'examples/portfolio_backtesting'),str(ROOT/'research/lines/futures_trend_rollover_shape_same_volume/tools')]
from stage008_signal_anchor_plan import ORIGINAL19,STANDARD_TASK_COLUMNS,assert_original19,assert_g_setting
import stage005_snapshot_anchors as snapshots
from stage005_sessions import canonical_open_timestamp,product_symbol
from stage005_download_open_window_21 import download_open_window_21
rules=snapshots.replay
PATCH_PATTERNS=snapshots.PATTERNS+['stage008_minute_patches/*/*_proof.json']


def atomic_json(path,payload):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.'+path.name+'_',dir=path.parent)
    temporary=Path(name)
    try:
        with os.fdopen(fd,'w') as f:json.dump(payload,f,ensure_ascii=False,indent=2,default=str)
        os.replace(temporary,path)
    finally:temporary.unlink(missing_ok=True)


def task_key(task):return str(task['vt_symbol']),pd.Timestamp(str(task['natural_date'])+' '+str(task['start']))


def canonical_task(symbol,day,calendar):
    if product_symbol(symbol) not in ORIGINAL19:raise ValueError('G_original19_only:'+symbol)
    if not '2020-01-01'<=str(day)<='2026-10-22':raise ValueError('G_outside_frozen_window')
    ts=canonical_open_timestamp(symbol,str(day),calendar)
    return dict(vt_symbol=symbol,trading_day=str(day),natural_date=ts.strftime('%Y-%m-%d'),start=ts.strftime('%H:%M'),
        end_exclusive=(ts+pd.Timedelta(minutes=1)).strftime('%H:%M'),session='night' if ts.hour==21 else 'day')


def validate_tasks(tasks,calendar):
    result=[]
    for task in tasks:
        standard={k:str(task[k]) for k in STANDARD_TASK_COLUMNS}
        if standard!=canonical_task(standard['vt_symbol'],standard['trading_day'],calendar):raise ValueError('G_noncanonical_task')
        result.append(standard)
    return rules.normalize_tasks(result) if result else []


def group_tasks(tasks):
    groups=[]
    for task in sorted(tasks,key=lambda t:(t['natural_date'],t['vt_symbol'],t['start'])):
        if not groups or (pd.Timestamp(task['natural_date'])-pd.Timestamp(groups[-1][0]['natural_date'])).days>=14:groups.append([])
        groups[-1].append(task)
    return groups


def select_missing(tasks,keys):
    unique={}
    for task in tasks:
        key=task_key(task)
        if key not in keys:unique.setdefault(key,task)
    return list(unique.values())


def error_task(terminal,calendar):
    error=str(terminal.get('error',''))
    match=re.search(r'intraday_open_anchor_missing:([^:]+):(\d{4}-\d{2}-\d{2})',error)
    if not match:raise ValueError('G_non_anchor_failure_requires_investigation:'+error)
    return canonical_task(*match.groups(),calendar)


def load_plan(out=OUT):
    folder=out/'stage008_anchor_plan'
    for path,digest in json.loads((folder/'input_manifest.json').read_text()).items():
        if rules.sha256(Path(path))!=digest:raise ValueError('G_plan_source_changed:'+path)
    config=json.loads((folder/'configuration.json').read_text());summary=json.loads((folder/'summary.json').read_text())
    assert_g_setting(config['setting'])
    assert_original19(config['universe'],json.loads((out/'E_attempt009/preflight.json').read_text()))
    if not config.get('E9_setting_exact_match') or config.get('ready_observed_weeks')!=21 or summary.get('financial_replays')!=0 or summary.get('status')!='completed_data_only_prefetch_plan':raise ValueError('G_plan_contract_invalid')
    calendar=sorted(pd.read_csv(out/'stage005_data/mapping.csv').date.astype(str).unique())
    frame=pd.read_csv(folder/'tasks.csv',dtype=str)
    if list(frame.columns)!=STANDARD_TASK_COLUMNS:raise ValueError('G_plan_nonstandard_task_columns')
    tasks=validate_tasks(frame.to_dict('records'),calendar)
    if len(tasks)!=summary['unique_tasks']:raise ValueError('G_plan_task_count_changed')
    return tasks,calendar


def available_keys(symbols,out=OUT):
    """与严格runner读取的已验收缓存/proof相同来源；不按volume过滤。"""
    from stage005_base_minute_cache import load_cached_minute_bars
    keys={(str(r.vt_symbol),pd.Timestamp(r.bar_datetime)) for r in load_cached_minute_bars(set(symbols)).itertuples()}
    catalog_root=out/'stage003_anchor_catalog';manifest=json.loads((catalog_root/'manifest.json').read_text())
    if not manifest['source_files_unchanged'] or rules.sha256(catalog_root/'catalog.csv')!=manifest['catalog_sha256']:raise ValueError('G_catalog_changed')
    for path,digest in manifest['source_files'].items():
        if rules.sha256(Path(path))!=digest:raise ValueError('G_catalog_source_changed:'+path)
    catalog=pd.read_csv(catalog_root/'catalog.csv',usecols=['vt_symbol','bar_datetime'])
    for r in catalog.loc[catalog.vt_symbol.isin(symbols)].itertuples():keys.add((str(r.vt_symbol),pd.Timestamp(r.bar_datetime)))
    proofs=sorted({p for pattern in PATCH_PATTERNS for p in out.glob(pattern)})
    for proof in proofs:
        parquet=proof.with_name(proof.name.replace('_proof.json','.parquet'))
        verified=rules.verify_patch(parquet,proof);source=verified['source']
        if rules.sha256(Path(source['raw_path']))!=source['source_sha256']:raise ValueError('G_patch_raw_changed')
        if source.get('parent_proof_path') and rules.sha256(Path(source['parent_proof_path']))!=source['parent_proof_sha256']:raise ValueError('G_patch_parent_changed')
        frame=pd.read_parquet(parquet,columns=['vt_symbol','bar_datetime'])
        for r in frame.loc[frame.vt_symbol.isin(symbols)].itertuples():keys.add((str(r.vt_symbol),pd.Timestamp(r.bar_datetime)))
    return keys


def publish_snapshot(tasks,raw,source,destination,calendar,out=OUT):
    """raw独立内容寻址先完整发布；patch/proof/result目录仅一次原子rename。"""
    destination=Path(destination);out=Path(out)
    if destination.exists():raise ValueError('G_immutable_batch_exists:'+str(destination))
    tasks=validate_tasks(tasks,calendar)
    if not tasks:raise ValueError('G_empty_download_batch')
    if len(group_tasks(tasks))!=1:raise ValueError('G_snapshot_span_exceeds_14_days')
    if source.get('kind')!='tqsdk_completed_snapshot' or source.get('order_api_calls',0)!=0 or source.get('cancel_api_calls',0)!=0:raise ValueError('G_invalid_snapshot_source')
    snapshots.snapshot_frame(raw,source)
    rawroot=out/'stage008_raw_snapshots';rawroot.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.raw_',suffix='.parquet',dir=rawroot);os.close(fd);temporary_raw=Path(name)
    try:
        raw.to_parquet(temporary_raw,index=False);digest=rules.sha256(temporary_raw);rawpath=(rawroot/(digest+'.parquet')).resolve()
        try:os.link(temporary_raw,rawpath)
        except FileExistsError:
            if rules.sha256(rawpath)!=digest:raise ValueError('G_raw_sha_collision_or_change')
    finally:temporary_raw.unlink(missing_ok=True)
    source={**source,'raw_path':str(rawpath),'source_sha256':digest}
    staging=out/'stage008_snapshot_builds';staging.mkdir(parents=True,exist_ok=True)
    temporary=Path(tempfile.mkdtemp(prefix='download_',dir=staging))
    patch=rules.save_patch(temporary,tasks,raw,source)
    snapshots.assert_parent(Path(patch['proof']))
    published={k:str((destination/Path(v).name).resolve()) for k,v in patch.items()}
    receipt=dict(status='complete',data_only=True,financial_replays=0,order_api_calls=0,cancel_api_calls=0,
        patch=published,raw_path=str(rawpath),raw_sha256=digest,tasks=tasks,
        zero_volume_rows=int((raw.volume==0).sum()),zero_volume_policy='retained_as_data_never_reclassified_as_missing',
        source_files={str(Path(__file__).resolve()):rules.sha256(Path(__file__)),str(Path(snapshots.__file__).resolve()):rules.sha256(Path(snapshots.__file__))})
    (temporary/'tasks.json').write_text(json.dumps(tasks,ensure_ascii=False,indent=2)+'\n')
    (temporary/'result.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    rules.verify_patch(Path(patch['parquet']),Path(patch['proof']))
    if rules.sha256(rawpath)!=digest:raise ValueError('G_raw_changed_before_publication')
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():raise ValueError('G_concurrent_batch_destination_exists')
    os.rename(temporary,destination)
    return receipt


def download_batch(tasks,destination,calendar,*,timeout=120,out=OUT):
    tasks=validate_tasks(tasks,calendar)
    credentials=json.loads(Path('/Users/mac/Desktop/fian/.vntrader/vt_setting.json').read_text())
    with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
        raw,source=download_open_window_21(tasks,credentials,timeout,data_length=10000)
    return publish_snapshot(tasks,raw,source,destination,calendar,out)
