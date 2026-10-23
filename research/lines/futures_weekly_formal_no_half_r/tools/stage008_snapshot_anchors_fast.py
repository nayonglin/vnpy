"""Stage008原19快照首分钟派生加速：首次完整验收并固定receipt，后续逐SHA重验。

保留原脚本不变。快路径仅用于存在且已通过完整canonical验收的同一raw/parent/
derived proof/patch/日历/代码字节；每次仍hash真实raw，并verify父与派生补片。
无receipt时完整bootstrap一次；变更拒绝，绝不自动重建receipt或改写旧patch。
新raw仍使用原完整核验与canonical过程。无下载/账户/订单/策略/回测调用。
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import argparse, hashlib, json, os, tempfile
import pandas as pd
import stage005_snapshot_anchors as slow
import stage005_sessions as sessions
from stage008_signal_anchor_plan import ORIGINAL19
TOOLS_HELPER=Path(__file__).with_name('stage008_signal_anchor_plan.py')

PATTERNS=slow.PATTERNS+['stage008_minute_patches/*/*_proof.json']

def canonical_tasks(frame,source,calendar):
    tasks,rejected=slow.canonical_tasks(frame,source,calendar)
    accepted=[]
    for task in tasks:
        if sessions.product_symbol(task['vt_symbol']) in ORIGINAL19:accepted.append(task)
        else:rejected['outside_original19']=rejected.get('outside_original19',0)+1
    return accepted,rejected

def verify_derived(folder,raw_digest,calendar,calendar_digest):
    proofs=list(folder.glob('*_proof.json'))
    if len(proofs)!=1:raise ValueError('G_derived_folder_ambiguous_or_incomplete')
    payload,raw=slow.assert_parent(proofs[0]);source=payload['source']
    parent=Path(source['parent_proof_path'])
    if slow.replay.sha256(parent)!=source['parent_proof_sha256']:raise ValueError('G_parent_proof_changed')
    original=json.loads(parent.read_text())['source']
    if original.get('parent_proof_path') or parent.parent.name.startswith('snapshot_'):raise ValueError('G_recursive_derivation_rejected')
    if source['source_sha256']!=raw_digest or original['source_sha256']!=raw_digest:raise ValueError('G_raw_identity_changed')
    if source.get('derivation_calendar_sha256')!=calendar_digest:raise ValueError('G_calendar_identity_changed')
    if any(source.get(k)!=v for k,v in original.items()):raise ValueError('G_original_source_metadata_changed')
    expected,_=canonical_tasks(raw,source,calendar)
    if expected!=payload['tasks']:raise ValueError('G_derived_task_set_changed')
    return dict(parquet=str(proofs[0].with_name(proofs[0].name.replace('_proof.json','.parquet'))),proof=str(proofs[0]),rows=payload['rows'])

OUT=slow.OUT
SCHEMA='stage008_original19_snapshot_fast_receipt_v1'
DERIVATION_KEYS={'parent_proof_path','parent_proof_sha256','derivation_kind',
    'derivation_calendar_path','derivation_calendar_sha256','derivation_script_path','derivation_script_sha256'}


def checksum(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def seal_receipt(payload):return {**payload,'receipt_checksum':checksum(payload)}


def check_receipt(receipt):
    core={k:v for k,v in receipt.items() if k!='receipt_checksum'}
    if receipt.get('schema')!=SCHEMA or receipt.get('receipt_checksum')!=checksum(core):raise ValueError('fast_receipt_integrity_invalid')
    return core


def current_identity(folder,raw_digest,calendar_path,calendar_digest):
    """不读取raw DataFrame、不聚合canonical；验证所有当前字节和父链。"""
    proofs=list(folder.glob('*_proof.json'))
    if len(proofs)!=1:raise ValueError('fast_derived_folder_ambiguous_or_incomplete')
    proof_path=proofs[0];payload=json.loads(proof_path.read_text());source=payload.get('source',{})
    if source.get('kind')!='tqsdk_completed_snapshot' or source.get('source_sha256')!=raw_digest:raise ValueError('fast_derived_source_identity_invalid')
    parent=Path(source['parent_proof_path']);parent_sha=slow.replay.sha256(parent)
    if parent_sha!=source.get('parent_proof_sha256'):raise ValueError('fast_parent_proof_sha_changed')
    original=json.loads(parent.read_text());original_source=original.get('source',{})
    if original_source.get('parent_proof_path') or parent.parent.name.startswith('snapshot_'):raise ValueError('fast_recursive_derivation_rejected')
    if original_source.get('kind')!='tqsdk_completed_snapshot' or original_source.get('source_sha256')!=raw_digest:raise ValueError('fast_parent_source_identity_invalid')
    if set(source)!=set(original_source)|DERIVATION_KEYS:raise ValueError('fast_source_metadata_key_set_changed')
    if any(source.get(k)!=v for k,v in original_source.items()):raise ValueError('fast_original_source_metadata_changed')
    if source.get('derivation_kind')!='stage008_original19_canonical_open_anchors_from_unchanged_completed_raw':raise ValueError('fast_derivation_kind_changed')
    if Path(source['derivation_calendar_path']).resolve()!=calendar_path.resolve() or source.get('derivation_calendar_sha256')!=calendar_digest:raise ValueError('fast_calendar_identity_changed')
    generator=Path(source['derivation_script_path']).resolve()
    if generator not in {Path(__file__).resolve()}:raise ValueError('fast_unknown_derivation_generator')
    if slow.replay.sha256(generator)!=source.get('derivation_script_sha256'):raise ValueError('fast_derivation_generator_changed')
    raw=Path(source['raw_path'])
    if slow.replay.sha256(raw)!=raw_digest:raise ValueError('fast_raw_sha_changed')
    derived_parquet=proof_path.with_name(proof_path.name.replace('_proof.json','.parquet'))
    parent_parquet=parent.with_name(parent.name.replace('_proof.json','.parquet'))
    slow.replay.verify_patch(parent_parquet,parent)
    verified=slow.replay.verify_patch(derived_parquet,proof_path)
    files={str(path.resolve()):slow.replay.sha256(path) for path in [raw,parent,parent_parquet,proof_path,derived_parquet,calendar_path,
        Path(slow.__file__),Path(__file__),Path(TOOLS_HELPER),Path(sessions.__file__),Path(slow.replay.__file__),Path(sessions.execution.__file__)]}
    if files[str(calendar_path.resolve())]!=calendar_digest:raise ValueError('fast_calendar_changed_during_check')
    return dict(raw_sha256=raw_digest,folder=str(folder.resolve()),files=files,source=source,
                patch=dict(parquet=str(derived_parquet),proof=str(proof_path),rows=verified['rows']))


def bootstrap_receipt(folder,raw_digest,calendar,calendar_path,calendar_digest):
    """仅首次：按原流程完整验收，随后固定快路径比较对象。"""
    before=current_identity(folder,raw_digest,calendar_path,calendar_digest)
    verify_derived(folder,raw_digest,calendar,calendar_digest)
    after=current_identity(folder,raw_digest,calendar_path,calendar_digest)
    if before!=after:raise ValueError('fast_bootstrap_inputs_changed')
    return seal_receipt(dict(schema=SCHEMA,validated_at=datetime.now().astimezone().isoformat(),
        validation='original_full_raw_parent_values_bounds_canonical_task_set_passed',identity=after))


def quick_skip(folder,raw_digest,calendar_path,calendar_digest,receipt):
    core=check_receipt(receipt)
    actual=current_identity(folder,raw_digest,calendar_path,calendar_digest)
    if actual!=core['identity']:raise ValueError('fast_cached_identity_changed')
    return actual['patch']


def write_receipt(path,receipt):
    # 只创建新receipt，不覆盖。文件完整写好后以hard link原子创建目标名。
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.receipt_',dir=path.parent)
    temporary=Path(name)
    try:
        with os.fdopen(fd,'w') as handle:json.dump(receipt,handle,ensure_ascii=False,indent=2)
        os.link(temporary,path)
    finally:temporary.unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--self-test',action='store_true');args=parser.parse_args()
    if args.self_test:return self_test()
    calendar_path=OUT/'stage005_data/mapping.csv';calendar=sorted(pd.read_csv(calendar_path).date.unique());calendar_digest=slow.replay.sha256(calendar_path)
    proofs=sorted({p for pattern in PATTERNS for p in OUT.glob(pattern)})
    by_digest={};derived=other=0
    for proof in proofs:
        payload=json.loads(proof.read_text());source=payload.get('source',{})
        if source.get('kind')!='tqsdk_completed_snapshot':other+=1;continue
        if source.get('parent_proof_path') or proof.parent.name.startswith('snapshot_'):derived+=1;continue
        digest=source.get('source_sha256')
        if not isinstance(digest,str) or len(digest)!=64:raise ValueError('source_sha_missing')
        by_digest.setdefault(digest,proof)
    results=[]
    for digest,proof in sorted(by_digest.items()):
        folder=OUT/'stage008_minute_patches'/('snapshot_'+digest)
        receipt_path=OUT/'stage008_snapshot_fast_receipts'/(digest+'.json')
        if folder.exists():
            if receipt_path.exists():
                receipt=json.loads(receipt_path.read_text());patch=quick_skip(folder,digest,calendar_path,calendar_digest,receipt);status='verified_fast_skipped'
            else:
                receipt=bootstrap_receipt(folder,digest,calendar,calendar_path,calendar_digest);write_receipt(receipt_path,receipt);patch=receipt['identity']['patch'];status='full_bootstrap_receipt_created'
            results.append(dict(raw_sha256=digest,status=status,patch=patch,receipt=str(receipt_path)))
            continue
        if receipt_path.exists():raise ValueError('cached_derived_folder_missing')
        parent,raw=slow.assert_parent(proof);tasks,rejected=canonical_tasks(raw,parent['source'],calendar)
        if not tasks:
            results.append(dict(raw_sha256=digest,status='no_eligible_canonical_anchors',rejected=rejected));continue
        staging=OUT/'stage008_snapshot_builds';staging.mkdir(parents=True,exist_ok=True)
        temporary=Path(tempfile.mkdtemp(prefix='snapshot_'+digest+'_',dir=staging))
        source={**parent['source'],'parent_proof_path':str(proof.resolve()),'parent_proof_sha256':slow.replay.sha256(proof),
            'derivation_kind':'stage008_original19_canonical_open_anchors_from_unchanged_completed_raw',
            'derivation_calendar_path':str(calendar_path),'derivation_calendar_sha256':calendar_digest,
            'derivation_script_path':str(Path(__file__).resolve()),'derivation_script_sha256':slow.replay.sha256(Path(__file__))}
        slow.replay.save_patch(temporary,tasks,raw,source)
        verify_derived(temporary,digest,calendar,calendar_digest)
        (OUT/'stage008_minute_patches').mkdir(parents=True,exist_ok=True)
        if folder.exists():raise ValueError('concurrent_derivation_destination_exists')
        os.rename(temporary,folder)
        receipt=bootstrap_receipt(folder,digest,calendar,calendar_path,calendar_digest);write_receipt(receipt_path,receipt)
        results.append(dict(raw_sha256=digest,status='new_full_derived_with_receipt',patch=receipt['identity']['patch'],receipt=str(receipt_path),rejected=rejected))
        print(json.dumps(results[-1],ensure_ascii=False),flush=True)
    # 结束重算唯一文件，排除同轮中途变更；receipt本身也核验checksum。
    final_files={}
    for result in results:
        if 'receipt' not in result:continue
        receipt=json.loads(Path(result['receipt']).read_text());core=check_receipt(receipt)
        for path,digest in core['identity']['files'].items():
            if path in final_files and final_files[path]!=digest:raise ValueError('fast_receipt_shared_input_conflict')
            final_files[path]=digest
    for path,digest in final_files.items():
        if slow.replay.sha256(Path(path))!=digest:raise ValueError('fast_input_changed_during_run:'+path)
    if slow.replay.sha256(calendar_path)!=calendar_digest:raise ValueError('fast_calendar_changed_during_run')
    summary=dict(data_only=True,downloads=0,financial_replays=0,order_api_calls=0,source_raws=len(by_digest),
        quick_skipped=sum(r['status']=='verified_fast_skipped' for r in results),
        bootstrapped=sum(r['status']=='full_bootstrap_receipt_created' for r in results),
        new_sources=sum(r['status']=='new_full_derived_with_receipt' for r in results),
        skipped_derived_proofs=derived,skipped_other_proofs=other,results=results)
    runs=OUT/'stage008_snapshot_anchors_fast_runs';runs.mkdir(parents=True,exist_ok=True)
    with (runs/(datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.json')).open('x') as handle:json.dump(summary,handle,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in summary.items() if k!='results'},ensure_ascii=False),flush=True)


def self_test():
    import unittest
    from unittest.mock import patch
    class Tests(unittest.TestCase):
        def setUp(self):
            self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
            self.calendar=['2026-10-21','2026-10-22'];self.cal=self.root/'mapping.csv';self.cal.write_text('date\n2026-10-21\n2026-10-22\n');self.cal_sha=slow.replay.sha256(self.cal)
            self.raw_path=self.root/'raw.parquet'
            times=pd.to_datetime(['2026-10-21 20:59','2026-10-21 21:00','2026-10-21 21:01'])
            raw=pd.DataFrame([dict(vt_symbol='au2612.SHFE',bar_datetime=t,open=100.,high=101.,low=99.,close=100.,volume=1.,open_oi=1.,close_oi=1.) for t in times]);raw.to_parquet(self.raw_path,index=False)
            self.digest=slow.replay.sha256(self.raw_path)
            source=dict(kind='tqsdk_completed_snapshot',snapshot_at='2026-10-22 08:00',serial_bounds={'au2612.SHFE':dict(earliest=str(times[0]),latest=str(times[-1]),rows=3)},raw_path=str(self.raw_path),source_sha256=self.digest)
            tasks,_=canonical_tasks(raw,source,self.calendar)
            parent_folder=self.root/'original';parent=slow.replay.save_patch(parent_folder,tasks,raw,source)
            self.parent=Path(parent['proof']);self.folder=self.root/('snapshot_'+self.digest)
            derived_source={**source,'parent_proof_path':str(self.parent),'parent_proof_sha256':slow.replay.sha256(self.parent),
                'derivation_kind':'stage008_original19_canonical_open_anchors_from_unchanged_completed_raw',
                'derivation_calendar_path':str(self.cal),'derivation_calendar_sha256':self.cal_sha,
                'derivation_script_path':str(Path(__file__).resolve()),'derivation_script_sha256':slow.replay.sha256(Path(__file__))}
            slow.replay.save_patch(self.folder,tasks,raw,derived_source)
            self.receipt=bootstrap_receipt(self.folder,self.digest,self.calendar,self.cal,self.cal_sha)
        def tearDown(self):self.tmp.cleanup()
        def test_quick_has_no_raw_dataframe_or_canonical_work(self):
            read=pd.read_parquet
            def guarded(path,*a,**kw):
                if Path(path).resolve()==self.raw_path.resolve():raise AssertionError('raw dataframe forbidden on quick path')
                return read(path,*a,**kw)
            with patch.dict(quick_skip.__globals__,{'canonical_tasks':lambda *a,**k:(_ for _ in ()).throw(AssertionError('canonical forbidden'))}),patch.object(pd,'read_parquet',side_effect=guarded):
                self.assertEqual(quick_skip(self.folder,self.digest,self.cal,self.cal_sha,self.receipt)['rows'],1)
        def test_original19_only_and_zero_volume_retained(self):
            raw=pd.read_parquet(self.raw_path)
            outside=raw.copy();outside['vt_symbol']='al2612.SHFE'
            raw['volume']=0.
            both=pd.concat([raw,outside],ignore_index=True)
            source=dict(snapshot_at='2026-10-22 08:00',serial_bounds={symbol:dict(earliest='2026-10-21 20:59:00',latest='2026-10-21 21:01:00',rows=3) for symbol in both.vt_symbol.unique()})
            tasks,rejected=canonical_tasks(both,source,self.calendar)
            self.assertEqual([task['vt_symbol'] for task in tasks],['au2612.SHFE'])
            self.assertEqual(rejected['outside_original19'],1)
        def test_input_changed_rejection_not_a_completed_ledger(self):
            from stage008_complete_replay import completion_pointer
            self.assertIsNone(completion_pointer('/tmp/G_attempt001',dict(status='rejected_input_changed')))
            pointer=completion_pointer('/tmp/G_attempt001',dict(status='rejected_reject_execution_zero_volume',error=None))
            self.assertTrue(pointer['diagnostic_completed']);self.assertFalse(pointer['qualified_execution'])
        def test_receipt_tampering_rejected(self):
            changed={**self.receipt,'validation':'tampered'}
            with self.assertRaisesRegex(ValueError,'integrity'):quick_skip(self.folder,self.digest,self.cal,self.cal_sha,changed)
        def test_raw_tampering_rejected(self):
            with self.raw_path.open('ab') as handle:handle.write(b'x')
            with self.assertRaisesRegex(ValueError,'raw_sha'):quick_skip(self.folder,self.digest,self.cal,self.cal_sha,self.receipt)
        def test_parent_proof_tampering_rejected(self):
            with self.parent.open('a') as handle:handle.write(' ')
            with self.assertRaisesRegex(ValueError,'parent_proof_sha'):quick_skip(self.folder,self.digest,self.cal,self.cal_sha,self.receipt)
        def test_derived_proof_tampering_rejected(self):
            p=next(self.folder.glob('*_proof.json'))
            with p.open('a') as handle:handle.write(' ')
            with self.assertRaisesRegex(ValueError,'cached_identity'):quick_skip(self.folder,self.digest,self.cal,self.cal_sha,self.receipt)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    if not result.wasSuccessful():raise SystemExit(1)

if __name__=='__main__':main()
