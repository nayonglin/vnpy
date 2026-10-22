"""从既有已验收Tq completed snapshot只读派生全市场canonical首分钟。

无下载、账户、策略或回测调用。原source/snapshot/serial_bounds保留不改；每个
raw SHA只派生一次。派生proof不递归用作源。新目录完整写好后原子移入扫描目录；
已存在则严格重验后跳过，绝不覆盖既有patch。--self-test只运行内置合成边界测试。
"""
from __future__ import annotations
from bisect import bisect_right
from datetime import datetime
from pathlib import Path
import argparse, hashlib, json, os, sys, tempfile
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parents[4]
LINE=ROOT/'research/lines/futures_weekly_formal_no_half_r'
OUT=LINE/'outputs'
sys.path[:0]=[str(Path(__file__).parent),str(ROOT/'examples/portfolio_backtesting'),str(ROOT/'research/lines/futures_trend_rollover_shape_same_volume/tools')]
import stage249_prepare_replay as replay
from stage005_sessions import canonical_open_timestamp,product_symbol

# 只放宽本进程的合法产品身份；原模块文件及原验证逻辑不改。
def _fullmarket_product(symbol):return product_symbol(str(symbol)).split('.')[0]
replay.product_of=_fullmarket_product

PATTERNS=['minute_probe/*_proof.json','minute_patches/*/*_proof.json',
          'stage003_minute_patches/*/*_proof.json','stage005_minute_patches/*/*_proof.json']
VALUES=replay.VALUES


def naive(value):
    stamp=pd.Timestamp(value)
    if pd.isna(stamp) or stamp.tzinfo is not None:raise ValueError('snapshot_timestamp_not_naive')
    return stamp


def snapshot_frame(raw,source):
    """检验完整raw的原始bounds身份，而非只检查拟派生的一行。"""
    required={'vt_symbol','bar_datetime',*VALUES}
    if raw.empty or not required.issubset(raw.columns):raise ValueError('snapshot_raw_columns_or_rows_missing')
    frame=raw.copy();frame['bar_datetime']=pd.to_datetime(frame.bar_datetime,errors='raise')
    if frame.bar_datetime.dt.tz is not None or frame.bar_datetime.isna().any():raise ValueError('snapshot_raw_timezone_or_null')
    if frame.duplicated(['vt_symbol','bar_datetime']).any():raise ValueError('snapshot_raw_duplicate')
    snapshot=naive(source['snapshot_at'])
    for symbol,g in frame.groupby('vt_symbol'):
        bound=source['serial_bounds'].get(symbol)
        if not bound:raise ValueError('snapshot_serial_bound_missing:'+str(symbol))
        earliest,latest=naive(bound['earliest']),naive(bound['latest'])
        if earliest!=g.bar_datetime.min() or latest!=g.bar_datetime.max() or int(bound['rows'])!=len(g):raise ValueError('snapshot_raw_bound_identity_mismatch:'+str(symbol))
        if not earliest<=latest<snapshot:raise ValueError('snapshot_serial_latest_not_completed')
    return frame


def assert_parent(proof_path):
    payload=json.loads(proof_path.read_text());source=payload.get('source',{})
    if source.get('kind')!='tqsdk_completed_snapshot':raise ValueError('not_tqsdk_completed_snapshot')
    raw_path=Path(source['raw_path'])
    if replay.sha256(raw_path)!=source['source_sha256']:raise ValueError('parent_raw_sha_changed')
    parent_parquet=proof_path.with_name(proof_path.name.replace('_proof.json','.parquet'))
    verified=replay.verify_patch(parent_parquet,proof_path)
    raw=snapshot_frame(pd.read_parquet(raw_path),source)
    expected=replay.extract_fragments(raw,verified['tasks'])
    actual=pd.read_parquet(parent_parquet)
    for col in ['vt_symbol','bar_datetime','bar_date','trading_day',*VALUES]:
        if col in VALUES:
            if not np.array_equal(actual[col].to_numpy(float),expected[col].to_numpy(float)):raise ValueError('parent_raw_patch_value_mismatch:'+col)
        elif not actual[col].astype(str).reset_index(drop=True).equals(expected[col].astype(str).reset_index(drop=True)):
            raise ValueError('parent_raw_patch_label_mismatch:'+col)
    for task in verified['tasks']:
        moments=replay.task_moments(task);selected=raw.loc[raw.vt_symbol.eq(task['vt_symbol']) & raw.bar_datetime.isin(moments)]
        bound=source['serial_bounds'][task['vt_symbol']]
        replay.validate_serial_bounds(selected,task,naive(source['snapshot_at']).to_pydatetime(),
            earliest=naive(bound['earliest']).to_pydatetime(),latest=naive(bound['latest']).to_pydatetime())
    return verified,raw


def canonical_tasks(frame,source,calendar):
    dates=sorted({str(d)[:10] for d in calendar});days=set(dates);tasks=[];rejected={}
    def reject(reason):rejected[reason]=rejected.get(reason,0)+1
    selected=frame.loc[frame.bar_datetime.dt.strftime('%H:%M').isin(['09:00','09:15','09:30','21:00'])]
    for row in selected.itertuples():
        stamp=naive(row.bar_datetime);natural=stamp.strftime('%Y-%m-%d');clock=stamp.strftime('%H:%M')
        if stamp.second or stamp.microsecond or stamp.nanosecond:reject('not_exact_minute');continue
        if clock=='21:00':
            index=bisect_right(dates,natural);day=dates[index] if index<len(dates) else None
        else:day=natural if natural in days else None
        if day is None or day<'2020-01-01' or day>'2026-10-22':reject('outside_research_calendar');continue
        try:expected=canonical_open_timestamp(row.vt_symbol,day,dates)
        except ValueError:reject('unknown_product_or_session');continue
        if stamp!=expected:reject('not_canonical');continue
        bound=source['serial_bounds'][row.vt_symbol]
        earliest,latest,snapshot=naive(bound['earliest']),naive(bound['latest']),naive(source['snapshot_at'])
        if not (earliest<stamp<=latest<snapshot and stamp+pd.Timedelta(minutes=1)<=snapshot):reject('snapshot_bounds_incomplete');continue
        task=dict(vt_symbol=row.vt_symbol,trading_day=day,natural_date=natural,start=clock,
                  end_exclusive=(stamp+pd.Timedelta(minutes=1)).strftime('%H:%M'),session='night' if clock=='21:00' else 'day')
        piece=frame.loc[frame.vt_symbol.eq(row.vt_symbol) & frame.bar_datetime.eq(stamp)]
        try:replay.validate_fragment(piece,task)
        except ValueError:reject('invalid_anchor_values');continue
        tasks.append(task)
    return replay.normalize_tasks(tasks) if tasks else [],rejected


def verify_derived(folder,raw_digest,calendar,calendar_digest):
    proofs=list(folder.glob('*_proof.json'))
    if len(proofs)!=1:raise ValueError('existing_derived_folder_incomplete_or_ambiguous:'+str(folder))
    proof_path=proofs[0];payload,raw=assert_parent(proof_path);source=payload['source']
    if source['source_sha256']!=raw_digest:raise ValueError('derived_raw_identity_mismatch')
    if source.get('derivation_calendar_sha256')!=calendar_digest:raise ValueError('derived_calendar_identity_changed')
    parent=Path(source['parent_proof_path'])
    if replay.sha256(parent)!=source['parent_proof_sha256']:raise ValueError('derived_parent_proof_changed')
    original=json.loads(parent.read_text())
    if original['source'].get('parent_proof_path') or parent.parent.name.startswith('snapshot_'):raise ValueError('recursive_snapshot_derivation')
    if original['source']['source_sha256']!=raw_digest:raise ValueError('derived_parent_raw_identity_mismatch')
    for key,value in original['source'].items():
        if source.get(key)!=value:raise ValueError('derived_original_source_metadata_changed:'+key)
    expected,_=canonical_tasks(raw,source,calendar)
    if payload['tasks']!=expected:raise ValueError('derived_task_set_changed')
    return dict(parquet=str(proof_path.with_name(proof_path.name.replace('_proof.json','.parquet'))),proof=str(proof_path),rows=payload['rows'])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--self-test',action='store_true');args=parser.parse_args()
    if args.self_test:return self_test()
    calendar_path=OUT/'stage005_data/mapping.csv';calendar=sorted(pd.read_csv(calendar_path).date.unique());calendar_digest=replay.sha256(calendar_path)
    proofs=sorted({p for pattern in PATTERNS for p in OUT.glob(pattern)})
    by_digest={};skipped_derived=0;skipped_other=0
    for proof in proofs:
        payload=json.loads(proof.read_text());source=payload.get('source',{})
        if source.get('kind')!='tqsdk_completed_snapshot':skipped_other+=1;continue
        if source.get('parent_proof_path') or proof.parent.name.startswith('snapshot_'):skipped_derived+=1;continue
        digest=source.get('source_sha256')
        if not isinstance(digest,str) or len(digest)!=64:raise ValueError('source_sha_missing:'+str(proof))
        by_digest.setdefault(digest,proof)
    results=[]
    for digest,proof in sorted(by_digest.items()):
        parent,raw=assert_parent(proof)
        tasks,rejected=canonical_tasks(raw,parent['source'],calendar)
        if not tasks:
            results.append(dict(raw_sha256=digest,status='no_eligible_canonical_anchors',rejected=rejected));continue
        folder=OUT/'stage005_minute_patches'/('snapshot_'+digest)
        if folder.exists():
            patch=verify_derived(folder,digest,calendar,calendar_digest)
            results.append(dict(raw_sha256=digest,status='verified_existing_skipped',patch=patch,rejected=rejected));continue
        staging=OUT/'stage005_snapshot_builds';staging.mkdir(parents=True,exist_ok=True)
        temporary=Path(tempfile.mkdtemp(prefix='snapshot_'+digest+'_',dir=staging))
        source={**parent['source'],'parent_proof_path':str(proof.resolve()),'parent_proof_sha256':replay.sha256(proof),
                'derivation_kind':'stage005_canonical_open_anchors_from_unchanged_completed_raw',
                'derivation_calendar_path':str(calendar_path),'derivation_calendar_sha256':calendar_digest,
                'derivation_script_path':str(Path(__file__).resolve()),'derivation_script_sha256':replay.sha256(Path(__file__))}
        patch=replay.save_patch(temporary,tasks,raw,source)
        verify_derived(temporary,digest,calendar,calendar_digest)
        (OUT/'stage005_minute_patches').mkdir(parents=True,exist_ok=True)
        if folder.exists():raise ValueError('concurrent_derivation_destination_exists:'+str(folder))
        os.rename(temporary,folder)
        patch=verify_derived(folder,digest,calendar,calendar_digest)
        results.append(dict(raw_sha256=digest,status='new_derived_patch',patch=patch,rejected=rejected))
        print(json.dumps(results[-1],ensure_ascii=False),flush=True)
    if replay.sha256(calendar_path)!=calendar_digest:raise ValueError('calendar_changed_during_derivation')
    summary=dict(data_only=True,downloads=0,financial_replays=0,order_api_calls=0,source_raws=len(by_digest),
        new_sources=sum(r['status']=='new_derived_patch' for r in results),
        existing_sources=sum(r['status']=='verified_existing_skipped' for r in results),
        skipped_derived_proofs=skipped_derived,skipped_non_completed_proofs=skipped_other,results=results)
    runs=OUT/'stage005_snapshot_anchors_runs';runs.mkdir(parents=True,exist_ok=True)
    path=runs/(datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.json')
    with path.open('x') as handle:json.dump(summary,handle,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in summary.items() if k!='results'},ensure_ascii=False),flush=True)


def self_test():
    import unittest
    class Tests(unittest.TestCase):
        def test_bounds_canonical_and_unknown(self):
            moments=['2026-10-21 20:59','2026-10-21 21:00','2026-10-22 09:00','2026-10-22 09:15','2026-10-22 09:30']
            rows=[dict(vt_symbol=symbol,bar_datetime=pd.Timestamp(t),open=100.,high=101.,low=99.,close=100.,volume=1.,open_oi=1.,close_oi=1.) for symbol in ['al2612.SHFE','IF2612.CFFEX','UNKNOWN2612.SHFE'] for t in moments]
            raw=pd.DataFrame(rows);source=dict(snapshot_at='2026-10-23 08:00',serial_bounds={s:dict(earliest=moments[0],latest=moments[-1],rows=5) for s in raw.vt_symbol.unique()})
            frame=snapshot_frame(raw,source);tasks,rejected=canonical_tasks(frame,source,['2026-10-21','2026-10-22'])
            self.assertEqual([(t['vt_symbol'],t['start']) for t in tasks],[('al2612.SHFE','21:00'),('IF2612.CFFEX','09:30')])
            self.assertGreater(rejected.get('unknown_product_or_session',0),0)
            bad={**source,'snapshot_at':'2026-10-22 09:30'}
            with self.assertRaisesRegex(ValueError,'completed'):snapshot_frame(raw,bad)
        def test_earliest_not_accepted_and_fragment_completion(self):
            raw=pd.DataFrame([dict(vt_symbol='al2612.SHFE',bar_datetime=pd.Timestamp('2026-10-21 21:00'),open=100.,high=101.,low=99.,close=100.,volume=1.,open_oi=1.,close_oi=1.)])
            source=dict(snapshot_at='2026-10-22 08:00',serial_bounds={'al2612.SHFE':dict(earliest='2026-10-21 21:00',latest='2026-10-21 21:00',rows=1)})
            tasks,rejected=canonical_tasks(raw,source,['2026-10-21','2026-10-22'])
            self.assertEqual(tasks,[]);self.assertEqual(rejected.get('snapshot_bounds_incomplete'),1)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    if not result.wasSuccessful():raise SystemExit(1)

if __name__=='__main__':main()
