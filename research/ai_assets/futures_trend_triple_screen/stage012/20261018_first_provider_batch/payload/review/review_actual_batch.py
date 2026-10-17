"""Limited independent review: standard-library keys/evidence and Decimal samples."""
from collections import defaultdict
import csv
from datetime import datetime,timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[5]
LINE=ROOT/'research/lines/futures_trend_triple_screen'
SOURCE=LINE/'outputs/stage012_provider_batch'
ATTEMPT=SOURCE/'network_attempt1'
OUTPUT=Path(__file__).parent
VALUES=['open','high','low','close','volume','open_oi','close_oi']


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read_csv(path):
    with Path(path).open(encoding='utf-8-sig',newline='')as source:return list(csv.DictReader(source))
def save(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def main():
    if (OUTPUT/'review_receipt.json').exists():raise FileExistsError('existing_review_refusing_repeat')
    paths=[SOURCE/'batch_manifest.json',SOURCE/'preflight.json',
        *[ATTEMPT/name for name in ['raw_completed_minutes.csv','completion_evidence.csv','quality.json','parent_receipt.json','worker_receipt.json']],
        Path(__file__)]
    fingerprints={str(path):sha(path)for path in paths}
    manifest=json.loads((SOURCE/'batch_manifest.json').read_text())
    preflight=json.loads((SOURCE/'preflight.json').read_text())
    parent=json.loads((ATTEMPT/'parent_receipt.json').read_text())
    worker=json.loads((ATTEMPT/'worker_receipt.json').read_text())
    quality=json.loads((ATTEMPT/'quality.json').read_text())
    changed=[path for path,digest in preflight['source_fingerprints'].items()if sha(path)!=digest]
    assert not changed,'frozen_preflight_input_changed'
    assert parent['exit_code']==0 and parent['all_inputs_unchanged']is True and parent['hard_kill']is False
    assert parent['automatic_retry']is False and worker['provider_attempts']==1
    assert worker['status']=='all_target_minutes_completed'
    for key in ['financial_replays','orders','cancels','broker_or_ctp_connections','model_fits']:assert worker[key]==0
    for key in ['credential_values_saved','raw_sdk_output_saved','cache_or_overlay_written','production_qualified']:assert worker[key]is False
    assert worker['local_TqSim_created']is True
    expected={};sessions={}
    for target in manifest['targets']:
        session_key=target['vt_symbol'],target['execution_trade_date']
        assert session_key not in sessions
        sessions[session_key]=target
        for text in target['expected_timestamps']:
            key=target['vt_symbol'],datetime.fromisoformat(text)
            assert key not in expected
            expected[key]=session_key
        assert len(target['expected_timestamps'])==target['expected_minutes']==225
    assert len(sessions)==11 and len(expected)==2475
    raw={};groups=defaultdict(list)
    for row in read_csv(ATTEMPT/'raw_completed_minutes.csv'):
        key=row['vt_symbol'],datetime.fromisoformat(row['bar_datetime'])
        assert key not in raw and key in expected
        values={name:Decimal(row[name])for name in VALUES}
        assert all(value.is_finite()for value in values.values())
        assert all(values[name]>0 for name in ['open','high','low','close'])
        assert all(values[name]>=0 for name in ['volume','open_oi','close_oi'])
        assert values['low']<=min(values['open'],values['close'])<=max(values['open'],values['close'])<=values['high']
        raw[key]=values;groups[expected[key]].append((key[1],values))
    assert set(raw)==set(expected)
    evidence={};observed_end=datetime.fromisoformat(manifest['provider_end'])
    for row in read_csv(ATTEMPT/'completion_evidence.csv'):
        key=row['vt_symbol'],datetime.fromisoformat(row['bar_datetime'])
        successor=datetime.fromisoformat(row['successor_time'])
        assert key not in evidence and key in expected
        assert row['completed'].lower()=='true'and row['method']=='observed_later_serial_kline'
        assert key[1]+timedelta(minutes=1)<=successor<=observed_end
        evidence[key]=successor
    assert set(evidence)==set(expected)
    quality_sessions={(row['vt_symbol'],row['execution_trade_date']):row for row in quality['sessions']}
    assert set(quality_sessions)==set(sessions)
    for key,row in quality_sessions.items():
        assert row['accepted']is True and row['completion_evidence_complete']is True
        assert row['actual_rows']==row['expected_minutes']==225 and row['missing_minutes']==0
        assert row['daily_mismatch_fields']==[] and row['daily_open_oi_check']=='checked'
    assert quality['all_sessions_accepted']is True and quality['accepted_sessions']==11 and quality['database_closeOI']=='N/A_not_used'
    samples=[]
    for symbol in sorted({key[0]for key in sessions}):
        keys=sorted(key for key in sessions if key[0]==symbol)
        for key in [keys[0],keys[-1]]:
            target=sessions[key];ordered=sorted(groups[key]);numbers=[item[1]for item in ordered]
            aggregate=dict(open=numbers[0]['open'],high=max(row['high']for row in numbers),
                low=min(row['low']for row in numbers),close=numbers[-1]['close'],
                volume=sum((row['volume']for row in numbers),Decimal(0)),
                open_oi=numbers[0]['open_oi'],close_oi=numbers[-1]['close_oi'])
            reference=[row for row in read_csv(target['daily_csv_path'])if row['trade_date'][:10]==key[1]]
            assert len(reference)==1
            checks={name:aggregate[name]==Decimal(reference[0][name])for name in VALUES}
            assert all(checks.values())
            assert all(aggregate[name]==Decimal(str(quality_sessions[key]['aggregate'][name]))for name in VALUES)
            samples.append(dict(vt_symbol=key[0],trading_date=key[1],rows=len(numbers),checks=checks,
                aggregate={name:str(value)for name,value in aggregate.items()},
                original_daily_csv_sha256=sha(target['daily_csv_path']),
                final_minute=ordered[-1][0].isoformat(),final_successor=evidence[(symbol,ordered[-1][0])].isoformat()))
    assert all(sha(path)==digest for path,digest in fingerprints.items())
    save(OUTPUT/'independent_checks.json',dict(full_grid_keys=2475,full_legal_rows=2475,
        full_completion_evidence_keys=2475,quality_receipt_sessions=11,independent_Decimal_aggregate_samples=samples,
        frozen_inputs_measured=len(preflight['source_fingerprints']),frozen_input_changes=changed))
    review='''# Stage012 单次批量数据有限独立审查\n\n审查通过，P0/P1 为 0。范围只限 hc2010/rb2010 的 11 个冻结 session，共 2,475 根分钟。\n\n- 逐键独立核 2,475 个目标网格、唯一键、有限合法 OHLC/量仓以及同键后继完成证据；末行形成中 K 线未被作为目标完成记录接收。后继均至少晚一分钟，且不越过已冻结观察窗口。\n- 用标准库 csv 与 Decimal 独立聚合两个合约各自首末目标日，共 4 个 session，七字段逐项精确等于原已绑定日线 CSV；其余 7 个 session 的既有质量 receipt 读取为通过，未宣称独立重算全部日聚合。DB closeOI 未用于验收。\n- 父进程 exit0、all_inputs_unchanged=true，37.93 秒；子进程 1 次正常提供商回放、显式本地 TqSim，全部 11 个 session 通过。输入指纹当前无变化。\n- 复用启动前静态审查：公开 TqBacktest/get_kline_serial 暖机历史、正常登录鉴权，未见授权改写；凭证不进入 argv/日志/manifest，SDK 原输出不保存。代码中父 exitcode 对输入漂移的 P2 注意项在本批没有触发，接受结论明确依赖 all_inputs_unchanged=true。\n- 本次审查无网络连接、无账户/指标回放、无数据合并或原数据修改。\n\n该结论是这些精确 session 的研究数据资格，不能推广全部需求、逐 tick 路径真实性或提供商全历史权限；不授权行情合并、fallback 或 C0 重跑。未独立访问提供商重新证明后继消息，只核固定证据与原 CSV 的一致性。\n'''
    (OUTPUT/'independent_review.md').write_text(review)
    save(OUTPUT/'review_receipt.json',dict(reviewed_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        status='limited_independent_grid_completion_and_4_Decimal_aggregates_pass',p0_findings=0,p1_findings=0,
        qualified_precise_sessions=11,qualified_minute_rows=2475,independent_aggregate_sessions=4,
        provider_connections_by_reviewer=0,financial_replays=0,indicator_streams_repeated=0,
        source_writes=0,cache_or_overlay_written=False,execution_fallback_authorized=False,production_qualified=False,
        all_reviewed_files_unchanged=True,source_fingerprints=fingerprints,
        independent_checks_sha256=sha(OUTPUT/'independent_checks.json'),report_sha256=sha(OUTPUT/'independent_review.md')))
    print(json.dumps(dict(status='pass',p0=0,p1=0,sessions=11,rows=2475,Decimal_samples=len(samples))))


if __name__=='__main__':main()
