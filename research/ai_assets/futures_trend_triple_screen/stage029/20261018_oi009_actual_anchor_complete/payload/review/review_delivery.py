"""Offline independent review of one actual CLOSE anchor; never publishes a response."""
from datetime import datetime
from pathlib import Path
import difflib
import hashlib
import json
import sys

import numpy as np
import pandas as pd

ROOT = Path('/Users/mac/Desktop/fian')
LINE = ROOT / 'research/lines/futures_trend_triple_screen'
sys.path.insert(0, str(LINE / 'tools'))
import stage002_local_minute_overlay as old
import stage021_blocking_data_gate as gate

DIGEST = 'd9bd8bda7ffa8f9e11560ed7ceccdf58fb49fb1dd8c23a00bb448474708f79ff'
REQUEST_SHA = '1fb7330081df0ce12576800d2c8e45b969b24eff062198872d9acd0a05691259'
OUT = Path(__file__).resolve().parent
PACKET = LINE / f'outputs/stage029_ordered_request_provider/request_{DIGEST}/packet_000'
ATTEMPT = PACKET / 'network_attempt1'
REQUEST = LINE / f'outputs/stage028_ordered_account/C_TS/data_wait/request_{DIGEST}/request.json'
SYMBOL, DAY, STAMP = 'OI009.CZCE', '2020-07-15', '2020-07-14T21:00:00'
FINGERPRINTS = {}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(path, expected=None):
    path = Path(path).resolve()
    digest = sha(path)
    assert expected is None or digest == expected, ('source_sha_mismatch', str(path))
    if str(path) in FINGERPRINTS:
        assert FINGERPRINTS[str(path)] == digest
    FINGERPRINTS[str(path)] = digest
    return path


def read_json(path, expected=None):
    return json.loads(bind(path, expected).read_text())


def write_json(path, value):
    assert not path.exists(), ('refusing_to_overwrite_independent_artifact', str(path))
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


request = read_json(REQUEST, REQUEST_SHA)
assert request['schema'] == gate.REQUEST_SCHEMA
assert gate.request_sha256(request) == DIGEST == request['request_sha256']
assert request['execution_trade_date'] == DAY and request['request_sequence'] == 1
assert request['active_orders'] == [{'order_id': 'BACKTESTING.29', 'vt_symbol': SYMBOL, 'requirement_kind': 'anchor'}]
assert len(request['requirements']) == 1
required = request['requirements'][0]
assert required == dict(vt_symbol=SYMBOL, execution_trade_date=DAY, requirement_kind='anchor',
    required_timestamps=[STAMP], missing_or_unqualified_timestamps=[STAMP], existing_source_timestamps=[])
assert read_json(REQUEST.parent / 'request_fingerprint.json') == dict(request_sha256=DIGEST,
    request_file_sha256=REQUEST_SHA, request_path=str(REQUEST))

manifest = read_json(PACKET / 'packet_manifest.json')
preflight = read_json(PACKET / 'preflight.json')
assert preflight['status'] == 'passed_offline_preflight_no_connection'
assert preflight['fixture_scope'] is False and manifest['fixture_scope'] is False and manifest['fixture_root'] is None
assert preflight['request_sha256'] == manifest['request_sha256'] == DIGEST
assert manifest['request_path'] == str(REQUEST) and manifest['request_file_sha256'] == REQUEST_SHA
for packet in [preflight, manifest]:
    assert packet['packet_index'] == 0 and packet['packet_count'] == 1 and packet['covers_whole_request'] is True
assert manifest['packet_contracts'] == [SYMBOL] and manifest['total_request_contracts'] == 1
assert manifest['request_required_minutes'] == manifest['packet_required_minutes'] == preflight['target_minutes'] == 1
assert preflight['provider_attempts_max'] == 1 and preflight['soft_seconds'] == 570 and preflight['hard_seconds'] == 600
assert preflight['auth_checks_unmodified'] is True and preflight['credential_values_saved'] is False
for path, digest in manifest['input_sha256'].items():
    bind(path, digest)
for path, digest in preflight['source_fingerprints'].items():
    bind(path, digest)

source023 = bind(LINE / 'tools/stage023_request_provider.py',
    '6d056953e6e200435b3c75a02ca7922883db9402b2bbb1c72b242f296adeff34')
source029 = bind(LINE / 'tools/stage029_ordered_request_provider.py',
    '8330c62ce8de9ea4704d255faffa231177c80a9b8a47d14e0e97504b1b236c99')
differences = [(index + 1, a, b) for index, (a, b) in enumerate(zip(
    source023.read_text().splitlines(), source029.read_text().splitlines())) if a != b]
assert len(source023.read_text().splitlines()) == len(source029.read_text().splitlines())
assert len(differences) == 4 and [row[0] for row in differences] == [1, 27, 28, 29]
assert all(row[1].split('=')[0] == row[2].split('=')[0] for row in differences[1:])

parent = read_json(ATTEMPT / 'parent_receipt.json')
worker = read_json(ATTEMPT / 'worker_receipt.json')
quality = read_json(ATTEMPT / 'quality.json')
assert parent['status'] == 'worker_terminal' and parent['exit_code'] == 0
assert parent['hard_kill'] is False and parent['all_inputs_unchanged'] is True
assert 0 < parent['elapsed_seconds'] < 600 and parent['automatic_retry'] is False
assert worker['status'] == 'all_target_minutes_completed' and worker['provider_attempts'] == 1
assert worker['completed_minutes'] == worker['target_minutes'] == 1
for terminal in [parent, worker, quality]:
    assert terminal['request_sha256'] == DIGEST
for terminal in [parent, worker]:
    assert terminal['financial_replays'] == terminal['orders'] == terminal['cancels'] == terminal['broker_or_ctp_connections'] == 0
    assert terminal['credential_values_saved'] is False and terminal['cache_or_overlay_written'] is False
    assert terminal['response_written'] is False and terminal['production_qualified'] is False
for name, digest in parent['artifact_sha256'].items():
    bind(ATTEMPT / name, digest)
assert quality['packet_all_targets_accepted'] is True and quality['request_fully_qualified_by_this_packet'] is True
assert quality['raw_rows'] == quality['accepted_requirements'] == 1

mapping = bind(old.MAPPING, '55e95a468f4ebd989e5db4da282d69a319ebc75ea08a068e1be8ff87ef1ff325')
calendar = pd.DatetimeIndex(pd.to_datetime(sorted(pd.read_csv(mapping, usecols=['date']).date.unique())))
bind(ROOT / 'examples/portfolio_backtesting/qmt_roll_intraday_execution.py',
    '95de37e240ed5f34e8370cf9652e958c3c44fa3f36bef1d905c3e757a8304272')
grid = old.session_grid(SYMBOL, DAY, calendar)
assert grid[0].isoformat() == STAMP and len(grid) > 1
later = calendar[calendar > pd.Timestamp(DAY)][0] + pd.Timedelta(hours=9, minutes=1)
assert manifest['provider_start'] == preflight['provider_start'] == later.isoformat()
assert manifest['provider_end'] == preflight['provider_end'] == (later + pd.Timedelta(minutes=4)).isoformat()

raw_path = bind(ATTEMPT / 'raw_completed_minutes.csv')
raw = pd.read_csv(raw_path)
assert list(raw.columns) == gate.FIELDS and len(raw) == 1
assert raw.vt_symbol.tolist() == [SYMBOL] and raw.bar_datetime.tolist() == [STAMP]
assert not raw.duplicated(['vt_symbol', 'bar_datetime']).any()
values = raw[old.VALUES].to_numpy(dtype=float)
row = raw.iloc[0]
assert np.isfinite(values).all() and min(row.open, row.high, row.low, row.close) > 0
assert min(row.volume, row.open_oi, row.close_oi) >= 0
assert row.low <= min(row.open, row.close) <= max(row.open, row.close) <= row.high
proof = pd.read_csv(bind(ATTEMPT / 'completion_evidence.csv'))
assert len(proof) == 1 and proof.vt_symbol.tolist() == [SYMBOL] and proof.bar_datetime.tolist() == [STAMP]
assert str(proof.completed.iloc[0]).lower() == 'true'
assert proof.method.iloc[0] == 'observed_later_serial_kline'
assert pd.Timestamp(proof.successor_time.iloc[0]) >= pd.Timestamp(STAMP) + pd.Timedelta(minutes=1)

daily_review = read_json(LINE / 'outputs/stage013_independent_review/review_receipt.json',
    '194e48847c9e0927772c482cd5bacc3529a625ac76aeec2a157089924177c795')
assert daily_review['qualified_research_daily'] is True
assert daily_review['p0_findings'] == daily_review['p1_findings'] == 0
assert (SYMBOL, DAY) not in {(r['vt_symbol'], r['trade_date']) for r in daily_review['rejected_targets']}
daily_path = bind(daily_review['qualified_daily_path'], daily_review['source_fingerprints'][daily_review['qualified_daily_path']])
audit_path = bind(daily_review['target_qualification_path'], daily_review['source_fingerprints'][daily_review['target_qualification_path']])
daily_all, audit_all = pd.read_csv(daily_path), pd.read_csv(audit_path, dtype=str)
daily = daily_all.loc[daily_all.vt_symbol.eq(SYMBOL) & daily_all.trade_date.eq(DAY)]
audit = audit_all.loc[audit_all.vt_symbol.eq(SYMBOL) & audit_all.trade_date.eq(DAY)]
assert len(daily) == len(audit) == 1
drow, arow = daily.iloc[0], audit.iloc[0]
assert arow.accepted.lower() == 'true' and arow.reason == 'completed_and_six_fields_matched'
for field in ['source_bar_id', 'source_datetime_ns', 'successor_id', 'successor_datetime_ns']:
    assert int(drow[field]) == int(float(arow[field]))
assert int(drow.successor_id) > int(drow.source_bar_id)
assert int(drow.successor_datetime_ns) > int(drow.source_datetime_ns)
assert pd.Timestamp(int(drow.source_datetime_ns), unit='ns', tz='UTC').tz_convert('Asia/Shanghai').date().isoformat() == DAY
assert pd.Timestamp(int(drow.successor_datetime_ns), unit='ns', tz='UTC').tz_convert('Asia/Shanghai') > pd.Timestamp(drow['datetime'])
assert len(manifest['targets']) == 1
target = manifest['targets'][0]
for key, value in required.items():
    assert target[key] == value
assert target['daily_reference_source'] == 'reviewed_stage013_daily' and target['daily_reference_path'] == str(daily_path)
assert target['daily_reference'] == {field: float(drow[field]) for field in old.VALUES}
assert float(row.open) == float(drow.open) == 8015.0
assert float(row.open_oi) == float(drow.open_oi) == 169061.0

bind(LINE / 'outputs/stage020_independent_review/review_receipt.json')
anchors_path = bind(old.A0 / 'execution_anchor_requests.csv',
    '72b61783602257c16b1b8c0307b0da4221430204808fdc29f21124f7556fbb20')
scans_path = bind(old.A0 / 'minute_scan_requests.csv',
    'cedf3627a530985083839af071f997482dd417e3f2721ca21208b50b086a03ab')
disjoint = old.prove_read_disjointness(raw, pd.read_csv(anchors_path), pd.read_csv(scans_path), calendar)
assert disjoint['distinct_actual_read_keys'] == 106731 and disjoint['intersection_count'] == 0
assert disjoint['path_equivalent'] is True and disjoint['added_keys'] == 1

checks = dict(reviewed_at=datetime.now().astimezone().isoformat(), status='one_actual_anchor_accepted',
    request_sha256=DIGEST, request_file_sha256=REQUEST_SHA, request_canonical_grid_exact=True,
    independent_terminal_checked=True, parent_status=parent['status'], parent_exit_code=0,
    worker_status=worker['status'], provider_attempts=1, all_inputs_unchanged=True,
    provider_sources_sha_checked=len(preflight['source_fingerprints']), provider_copy_changed_only_four_scope_lines=True,
    raw_rows=1, exact_key=True, legal_seven_values=True, raw_seven_values_unmodified=True,
    successor_time=str(proof.successor_time.iloc[0]), completed_by_observed_successor=True,
    daily_source='reviewed_stage013_daily', daily_target_completed_and_accepted=True,
    daily_open_exact=True, daily_openOI_exact=True, daily_open=8015.0, daily_open_oi=169061.0,
    qualification='anchor_only_not_full_session', full_day_OHLC7_recertified=False,
    a0_disjointness=disjoint, old_1590_source_prices_reaudited=False,
    p0_findings=0, p1_findings=0, network_calls=0, downloads=0, financial_replays=0,
    model_fits=0, broker_or_ctp_connections=0, orders=0, cancels=0,
    overfitting=False, overfitting_reason='固定真实订单触发的数据资格审查，无收益筛选或参数搜索。',
    continued_value=True, continued_value_reason='唯一实际缺失锚点通过后允许同一等待引擎继续，保持完整路径。',
    response_written=False, production_qualified=False)
write_json(OUT / 'key_checks.json', checks)
bind(OUT / 'key_checks.json')
bind(__file__)
for path, digest in FINGERPRINTS.items():
    assert sha(path) == digest, ('source_changed_during_independent_review', path)

receipt = dict(schema=gate.RECEIPT_SCHEMA, independent_review=True, reviewer='ordered_data_delivery_review',
    reviewed_at=checks['reviewed_at'], qualified_research_data=True, p0_findings=0, p1_findings=0,
    request_sha256=DIGEST, data_path=str(raw_path), data_sha256=sha(raw_path), source_fingerprints=FINGERPRINTS,
    accepted_requirements=[dict(vt_symbol=SYMBOL, execution_trade_date=DAY, requirement_kind='anchor',
        accepted=True, completed_bars_and_daily_qualified=True, accepted_timestamps=required['required_timestamps'],
        qualification_kind='anchor_only_not_full_session', daily_checks=['open', 'open_oi'])],
    qualified_minute_rows=1, full_request_qualified=True, full_session_qualified=False,
    request_path=str(REQUEST), request_file_sha256=REQUEST_SHA, provider_attempts=1,
    parent_exit_code=0, all_inputs_unchanged=True, a0_actual_read_intersection=0,
    response_written=False, network_calls=0, downloads=0, financial_replays=0, model_fits=0,
    broker_or_ctp_connections=0, orders=0, cancels=0, overfitting=False, continued_value=True,
    production_qualified=False)
receipt_path = OUT / 'delivery_receipt.json'
write_json(receipt_path, receipt)
parsed, full, anchors, info = gate._read_delivery(request, gate.QualifiedDelivery(receipt_path, sha(receipt_path)))
assert len(parsed) == 1 and not full and anchors == {(SYMBOL, pd.Timestamp(STAMP))}
print(json.dumps(dict(receipt_path=str(receipt_path), receipt_sha256=sha(receipt_path),
    data_sha256=sha(raw_path), schema_parse_passed=True, accepted_rows=1, full_session_qualified=False,
    source_fingerprints=len(FINGERPRINTS), p0_findings=0, p1_findings=0), ensure_ascii=False))
