"""Bounded142 source qualification, then one accepted127 scalar feature build."""
from collections import Counter, defaultdict
import csv
from datetime import datetime
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sqlite3
import struct
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = Path('/Users/mac/Desktop/fian')
LINE = ROOT / 'research/lines/futures_trend_triple_screen'
OUT = LINE / 'outputs/stage142_ema_daily_qualification_and_features'
CANDIDATE = LINE / 'outputs/stage141_ema_daily_normalized_source'
MANIFEST_SHA = '96eea70a16b7a5715f697aaa06a4e34107e328109849ca573eba88be78cc8b90'
DAILY_SHA = '71dd740fb605e1ff8365fb6fc7236ab6d19f8d90a7f7be72c753d29733b7df5c'
KEYS_SHA = '5e8493067d422c27ba7e4512dfbb30ea74de11193b46d0a71547940ed3f48317'
DB_SHA = '273f0bc18de3070e4e085e4d6585fba71d6e1bb1256e3c7fb5adfc6532836a54'
MODEL = LINE / 'tools/stage127_ema_limit_model.py'
MODEL_SHA = '6568f87ec74bebdb9afa730b3347c5eb52cdf31bd8f3ca3cc9208b1c55c2f7d6'
REVIEW132 = LINE / 'outputs/stage132_ema_limit_overall_review/review_receipt.json'
REVIEW132_SHA = 'bb4d79bd77a40475e98e0631737bc8b937d64ff609fc6d4771c48e06fd0e640b'
COLUMNS = ['date', 'vt_symbol', 'open', 'high', 'low', 'close', 'volume']
ANNOUNCEMENT = 'https://www.nanhua.net/news/2024/12/b0c7febb-514a-422c-8b9c-386f640b37a1.html?updatetime=short'


def check(value, reason):
    if not value:
        raise AssertionError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path, expected):
    path = Path(path)
    check(path.is_absolute() and not path.is_symlink(), 'absolute non-symlink source required')
    raw = path.read_bytes()
    check(digest(raw) == expected, 'source SHA mismatch: ' + str(path))
    return raw


def write(name, data):
    with (OUT / name).open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def parsed_csv(raw):
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''))
    return reader.fieldnames, list(reader)


def bits(values):
    return struct.pack('!5d', *values)


def status(path):
    p = Path(path)
    if not p.exists():
        return {'exists': False, 'bytes': 0}
    s = p.stat()
    return {'exists': True, 'bytes': s.st_size, 'mtime_ns': s.st_mtime_ns}


def qualify():
    write('qualification_attempt_started.json', {'started_at': datetime.now().astimezone().isoformat(), 'attempt': 1})
    manifest = json.loads(read(CANDIDATE / 'candidate_manifest.json', MANIFEST_SHA))
    check(manifest['schema'] == 'stage141_ema_normalized_daily_candidate_v1'
          and manifest['status'] == 'pending_independent_source_review'
          and manifest['qualification_granted'] is False and manifest['qualifier_sha256'] is None,
          'candidate must remain honestly pending')
    db_path = ROOT / '.vntrader/database.db'
    before = {s: status(str(db_path) + s) for s in ('', '-wal', '-shm')}
    check(not before['-wal']['bytes'] and not before['-shm']['bytes'], 'nonempty DB sidecar')
    payloads, bindings = {}, {}
    for item in manifest['source_bindings']:
        p, h = item['path'], item['sha256']
        check(p not in bindings, 'duplicate candidate source identity')
        payloads[p] = read(p, h)
        check(len(payloads[p]) == item['bytes'], 'bound bytes count')
        bindings[p] = h
    check(len(bindings) == 21 and bindings[str(db_path)] == DB_SHA, 'finite source closure')
    by_role = {item['role']: item['path'] for item in manifest['source_bindings']}
    parameters = json.loads(payloads[by_role['accepted_A_OFF_parameters']])
    old = json.loads(payloads[by_role['accepted_A0_parameters']])
    check(all(parameters[k] == old[k] for k in ('contract_sizes', 'priceticks')), 'accepted metadata drift')
    contracts = sorted(parameters['contract_sizes'])
    check(len(contracts) == 806 and all(re.fullmatch(r'[A-Za-z]+\d{3,4}\.[A-Z]+', c) for c in contracts), 'metadata contract scope')
    _, cal_rows = parsed_csv(payloads[by_role['accepted_calendar']])
    calendar = [r['date'] for r in cal_rows]
    check(calendar == sorted(set(calendar)) and len(calendar) == 1786 and calendar[-1] == '2026-10-14', 'original calendar')
    raw_daily = read(CANDIDATE / 'daily.csv', DAILY_SHA)
    header, csv_rows = parsed_csv(raw_daily)
    check(header == COLUMNS and not raw_daily.startswith(b'\xef\xbb\xbf'), 'canonical seven-column UTF8 schema')
    normalized, ordered_keys = {}, []
    for r in csv_rows:
        k = (r['vt_symbol'], r['date'])
        check(k not in normalized and k[0] in contracts and k[1] in calendar, 'duplicate/unexpected daily key')
        v = tuple(float(r[n]) for n in COLUMNS[2:])
        check(all(math.isfinite(x) for x in v) and min(v[:4]) > 0 and v[4] >= 0
              and v[2] <= min(v[0], v[3]) <= max(v[0], v[3]) <= v[1], 'invalid OHLCV')
        normalized[k] = v; ordered_keys.append(k)
    check(ordered_keys == sorted(ordered_keys), 'canonical order')
    key_header, key_rows = parsed_csv(read(CANDIDATE / 'exact_keys.csv', KEYS_SHA))
    check(key_header == ['vt_symbol', 'date'] and [(r['vt_symbol'], r['date']) for r in key_rows] == ordered_keys, 'exact keys differ')
    expected = {}
    with sqlite3.connect(':memory:') as db:
        db.deserialize(payloads[str(db_path)])
        db.execute('PRAGMA query_only=ON')
        check(db.execute('PRAGMA query_only').fetchone()[0] == 1, 'readonly snapshot')
        query = ("SELECT symbol,exchange,datetime,open_price,high_price,low_price,close_price,volume "
                 "FROM dbbardata WHERE interval='d' AND datetime>=? AND datetime<=? "
                 "AND symbol||'.'||exchange IN (" + ','.join('?' for _ in contracts) + ')')
        for symbol, exchange, stamp, *raw in db.execute(query, ['2019-06-01 00:00:00', '2026-10-14 00:00:00', *contracts]):
            dt = datetime.fromisoformat(stamp)
            if dt.tzinfo is not None:
                dt = dt.astimezone(ZoneInfo('Asia/Shanghai'))
            check(dt.hour == dt.minute == dt.second == dt.microsecond == 0, 'nonlocal-midnight source')
            k = (symbol + '.' + exchange, dt.date().isoformat())
            check(k not in expected, 'duplicate frozen DB daily key')
            expected[k] = tuple(float(x) for x in raw)
    check(set(expected) == set(normalized), 'DB/export exact-key set differs')
    check(all(bits(expected[k]) == bits(normalized[k]) for k in expected), 'DB/export float64 scalar differs')
    check(len(expected) == 116394 and len({k[0] for k in expected}) == 533
          and {k[1] for k in expected} == set(calendar), 'source scope changed')
    check(sum(v[4] == 0 for v in expected.values()) == sum(v[4] == 0 for v in normalized.values()) == 1468, 'zero-volume filtering')
    after = {s: status(str(db_path) + s) for s in ('', '-wal', '-shm')}
    check(before == after, 'source/sidecar stat changed during single-byte-read audit')
    inventory = json.loads(payloads[by_role['138_source_inventory']])
    followup = json.loads(payloads[by_role['138_carry_and_zero_volume_evidence']])
    excluded = inventory['stage013_excluded_exact_DB_checks']
    check(len(excluded) == 16 and all((x['vt_symbol'], x['execution_trade_date']) not in normalized for x in excluded), 'native carry key entered source')
    samples = [
        {'path': followup['zero_volume_source']['path'], 'sha256': followup['zero_volume_source']['sha256'], 'contract': 'AP101.CZCE', 'day': '2021-01-14'},
        {'path': inventory['sampled_price_checks'][3]['source'], 'contract': 'fu2101.SHFE', 'day': '2020-06-29'},
        {'path': inventory['sampled_price_checks'][2]['source'], 'contract': 'sp2611.SHFE', 'day': '2026-10-14'},
    ]
    for sample in samples:
        sample['sha256'] = sample.get('sha256', inventory['source_bindings'].get(sample['path'], {}).get('sha256'))
        _, original_rows = parsed_csv(read(sample['path'], sample['sha256']))
        matches = [r for r in original_rows if r['trade_date'] == sample['day']
                   and r.get('vt_symbol', sample['contract']) == sample['contract']]
        check(len(matches) == 1, 'finite original sample not unique')
        original_values = tuple(float(matches[0][n]) for n in COLUMNS[2:])
        check(bits(original_values) == bits(normalized[(sample['contract'], sample['day'])]), 'finite cross-source sample differs')
        sample.update(all_five_values_bit_equal=True, values=dict(zip(COLUMNS[2:], original_values)))
    scalar = hashlib.sha256()
    for k in ordered_keys:
        scalar.update(k[1].encode() + b'\0' + k[0].encode() + b'\0' + bits(normalized[k]))
    check(scalar.hexdigest() == manifest['self_checks']['source_scalar_sha256'], 'scalar source fingerprint')
    audit = dict(schema='stage142_independent_daily_source_audit_v1', completed_at=datetime.now().astimezone().isoformat(),
        all_checks_passed=True, candidate_manifest_sha256=MANIFEST_SHA, rows=116394, contracts=533, dates=1786, zero_volume_rows_retained=1468,
        database_read_bytes_calls=1, database_path_opened_as_sqlite=False, sqlite_deserialize_same_hashed_bytes=True, sqlite_query_only=True,
        database_sha256=DB_SHA, database_before=before, database_after=after, all_exact_keys_equal=True, all_five_float64_values_bit_equal=True,
        scalar_sha256=scalar.hexdigest(), candidate_sources_verified=len(bindings), finite_samples=samples,
        native_carry_excluded_exact_keys=16, tail_rows_not_filtered_by_future_successor=True, old013_4500_scope_extended=False,
        all_market_minute_reaggregation=False, native_model_provider_network_financial_runs=0, p0_findings=0, p1_findings=0, p2_findings=0)
    write('source_audit.json', audit)
    qualifier = dict(schema='stage142_independent_daily_source_qualification_v1', reviewed_at=datetime.now().astimezone().isoformat(),
        reviewer='off_wait_delta_review_stage142', independent_review=True, p0_findings=0, p1_findings=0, p2_findings=0, findings=[],
        new_data_qualification=True, qualified_research_data=True, qualification_scope='all116394_exact_research_keys_only',
        raw_same_baseline_source=True, fully_independent_market_repricing=False,
        acceptance_basis=['accepted_baseline_same_frozen_real_contract_DB', 'lossless_seven_column_normalization', 'three_bounded_original_CSV_samples_and138_carry_evidence'],
        candidate_manifest={'path': str(CANDIDATE / 'candidate_manifest.json'), 'sha256': MANIFEST_SHA},
        daily_csv={'path': str(CANDIDATE / 'daily.csv'), 'sha256': DAILY_SHA},
        exact_keys={'path': str(CANDIDATE / 'exact_keys.csv'), 'sha256': KEYS_SHA, 'count': 116394, 'contract_column': 'vt_symbol', 'date_column': 'date'},
        source_audit={'path': str(OUT / 'source_audit.json'), 'sha256': digest((OUT / 'source_audit.json').read_bytes())},
        source_bindings=bindings, scope=manifest['source_scope'], zero_volume_rows_retained=1468,
        financial_ready=False, production_qualified=False,
        limitations=['Same frozen accepted baseline DB source inherited;not a new independent vendor or full minute/daily price reaggregation.',
            'Stage0134500 exact-key qualification remains4500;new all116394 research-key acceptance is separately signed under139 boundary.',
            'Original provider zero-volume rows and real-contract final rows retained without future-successor filtering;no fill,splice,adjustment or new calendar.',
            'Finite AP zero-volume sample proves this row existed before native carry,not provider-serial completion or all1468 zero-volume correctness.',
            'Carry16 missing DB keys excluded;calendar gaps remain genuine127 warmup resets.',
            'No financial readiness,alpha,full B account,production or live-trading qualification granted.'])
    write('daily_source_qualification.json', qualifier)
    print(json.dumps({'qualified_research_data': True, 'rows': 116394, 'qualifier_sha256': digest((OUT / 'daily_source_qualification.json').read_bytes()), 'source_audit_sha256': digest((OUT / 'source_audit.json').read_bytes())}))


def build():
    qualifier_path = OUT / 'daily_source_qualification.json'
    qualifier_bytes = qualifier_path.read_bytes(); qualifier_sha = digest(qualifier_bytes)
    qualifier = json.loads(qualifier_bytes)
    check(qualifier['independent_review'] is True and qualifier['new_data_qualification'] is True
          and qualifier['qualified_research_data'] is True and qualifier['p0_findings'] == qualifier['p1_findings'] == 0,
          'real independent qualifier required before model call')
    manifest = json.loads(read(CANDIDATE / 'candidate_manifest.json', MANIFEST_SHA))
    check(read(MODEL, MODEL_SHA) and json.loads(read(REVIEW132, REVIEW132_SHA))['source_fingerprints']['tools/stage127_ema_limit_model.py'] == MODEL_SHA, 'accepted model source')
    _, key_rows = parsed_csv(read(CANDIDATE / 'exact_keys.csv', KEYS_SHA))
    qualified_keys = frozenset((r['vt_symbol'], r['date']) for r in key_rows)
    check(len(qualified_keys) == 116394 and qualifier['exact_keys']['sha256'] == KEYS_SHA, 'qualified exact keys')
    write('feature_build_started.json', {'started_at': datetime.now().astimezone().isoformat(), 'attempt': 1, 'qualifier_sha256': qualifier_sha, 'model_sha256': MODEL_SHA})
    sys.path.insert(0, str(LINE / 'tools'))
    import stage127_ema_limit_model as model
    # These two accepted public methods are each called exactly once.
    rows, source_bindings = model.load_bound_daily_csv(CANDIDATE / 'daily.csv', sha256=DAILY_SHA,
        qualified_keys=qualified_keys, qualifier_sha256=qualifier_sha)
    by_role = {x['role']: x for x in manifest['source_bindings']}
    cal_binding = by_role['accepted_calendar']; par_binding = by_role['accepted_A_OFF_parameters']
    _, cal_rows = parsed_csv(read(cal_binding['path'], cal_binding['sha256']))
    calendar = [r['date'] for r in cal_rows]
    parameters = json.loads(read(par_binding['path'], par_binding['sha256']))
    features = model.build_ema_rows(rows, calendar, source_bindings=source_bindings)
    check(len(rows) == len(features) == len(qualified_keys), 'feature scope count')
    feature_index = {(f['contract'], f['asof']): f for f in features}
    check(len(feature_index) == len(features) and set(feature_index) == qualified_keys, 'feature unique key scope')
    next_day = dict(zip(calendar, calendar[1:] + [None]))
    import stage022_run_c0_qualified_wait as runtime
    with tempfile.TemporaryDirectory(prefix='stage142-runtime-', dir=OUT) as temporary:
        previous = runtime.OUTPUT
        try:
            runtime.OUTPUT = Path(temporary) / 'runtime'
            runtime.configure_runtime(Path(temporary) / 'shared')
        finally:
            runtime.OUTPUT = previous
        import qmt_roll_intraday_execution as execution
        rule = manifest['execution_tick_binding']
        check(digest(read(rule['rule_source'], rule['rule_sha256'])) == rule['rule_sha256'], 'execution rule source')
        for f in features:
            contract, u = f['contract'], f['asof']; d = next_day[u]
            configured = float(parameters['priceticks'][contract])
            if re.fullmatch(r'lc[0-9]+\.GFEX', contract) and d is not None and d >= '2024-12-18':
                check(u >= '2024-12-06', 'future LC rule not public as of u')
            f.update(execution_day=d, configured_tick=configured,
                execution_tick=execution.effective_pricetick(contract, d or u, configured),
                execution_tick_known_asof=u, execution_tick_order_usable=d is not None,
                execution_tick_status='u_known_next_D_rule' if d is not None else 'no_next_session_feature_only',
                source_ref='daily_source', execution_rule_ref='execution_tick_rules')
            f.pop('source_bindings')
    # Two bounded actual38-bar scalar windows, independently expanded as weighted closes.
    grouped = defaultdict(list)
    for r in rows:
        grouped[r['vt_symbol']].append(r)
    probes = []
    for contract in ('AP005.CZCE', 'fu2101.SHFE'):
        f = next(x for x in features if x['contract'] == contract and x['ready'])
        segment = sorted([r for r in grouped[contract] if f['segment_start'] <= r['date'] <= f['asof']], key=lambda r: r['date'])
        check(len(segment) == 38, 'bounded first-ready sample is not38 real bars')
        seed = math.fsum(r['close'] for r in segment[:13]) / 13
        a, b = 1 / 7, 6 / 7
        ema = [seed] + [b ** (j - 12) * seed + a * math.fsum(b ** (j - k) * segment[k]['close'] for k in range(13, j + 1)) for j in range(13, 38)]
        down = [max(e - r['low'], 0) for e, r in zip(ema, segment[12:])]
        up = [max(r['high'] - e, 0) for e, r in zip(ema, segment[12:])]
        pdn, pup = [v for v in down if v > 0], [v for v in up if v > 0]
        values = {'ema': ema[-1], 'ema_prev': ema[-2], 'mean_down': math.fsum(pdn) / len(pdn) if pdn else None,
                  'mean_up': math.fsum(pup) / len(pup) if pup else None}
        for name, v in values.items():
            check((v is None and f[name] is None) or (v is not None and math.isclose(v, f[name], rel_tol=1e-12, abs_tol=1e-9)), 'bounded scalar sample differs: ' + name)
        seed_feature = feature_index[(contract, segment[12]['date'])]
        check(seed_feature['ema'] == seed and f['valid_ema_count'] == 26
              and f['positive_down_count'] == len(pdn) and f['positive_up_count'] == len(pup), 'seed/window/count sample differs')
        probes.append({'contract': contract, 'asof': f['asof'], 'segment_start': f['segment_start'], 'real_bars': 38,
                       'seed': seed, 'valid_ema_count': 26, 'closed_form_scalar_matches': True, 'values': values})
    boundary = []
    for u, d, tick in [('2024-12-16', '2024-12-17', 50.0), ('2024-12-17', '2024-12-18', 20.0)]:
        matches = [f for f in features if f['asof'] == u and re.fullmatch(r'lc[0-9]+\.GFEX', f['contract'])]
        check(matches and all(f['execution_day'] == d and f['execution_tick'] == tick for f in matches), 'actual LC PIT boundary')
        boundary.append({'asof': u, 'execution_day': d, 'execution_tick': tick, 'actual_contract_rows': len(matches), 'known_from': '2024-12-06'})
    columns = ['asof', 'contract', 'ready', 'reason', 'ema', 'ema_prev', 'mean_down', 'mean_up',
        'positive_down_count', 'positive_up_count', 'valid_ema_count', 'segment_start', 'execution_tick',
        'execution_day', 'configured_tick', 'execution_tick_known_asof', 'execution_tick_order_usable',
        'execution_tick_status', 'source_ref', 'execution_rule_ref']
    with (OUT / 'features.csv').open('x', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator='\n'); writer.writeheader()
        for f in features:
            check(set(f) == set(columns), 'scalar feature schema')
            writer.writerow({k: format(v, '.17g') if isinstance(v, float) else v for k, v in f.items()})
    reasons = Counter(f['reason'] for f in features)
    yearly = {year: {'rows': sum(f['asof'][:4] == year for f in features),
                     'ready': sum(f['asof'][:4] == year and f['ready'] for f in features)} for year in sorted({f['asof'][:4] for f in features})}
    ready = sum(f['ready'] for f in features)
    summary = {'rows': len(features), 'contracts': len(grouped), 'dates': len(calendar), 'ready_rows': ready,
        'not_ready_rows': len(features) - ready, 'reason_counts': dict(reasons), 'yearly': yearly,
        'first_asof': min(f['asof'] for f in features), 'last_asof': max(f['asof'] for f in features),
        'contracts_with_ready': len({f['contract'] for f in features if f['ready']}),
        'zero_volume_rows_retained': sum(r['volume'] == 0 for r in rows),
        'last_calendar_no_next_session_rows': sum(f['execution_day'] is None for f in features),
        'future_append_prefix_tests': 'inherited accepted127 unit/132 evidence;not rerun'}
    write('feature_build_evidence.json', {'schema': 'stage142_one_feature_build_evidence_v1', 'completed_at': datetime.now().astimezone().isoformat(),
        'load_bound_daily_csv_calls': 1, 'build_ema_rows_calls': 1, 'summary': summary, 'scalar_probes': probes,
        'LC_actual_boundary': boundary, 'financial_native_training_provider_network_guard_runs': 0})
    feature_manifest = {'schema': 'stage142_accepted127_scalar_features_v1', 'status': 'research_features_only',
        'model_path': str(MODEL), 'model_sha256': MODEL_SHA, 'model_independent_review': {'path': str(REVIEW132), 'sha256': REVIEW132_SHA},
        'candidate_manifest': {'path': str(CANDIDATE / 'candidate_manifest.json'), 'sha256': MANIFEST_SHA},
        'daily_source_qualification': {'path': str(qualifier_path), 'sha256': qualifier_sha},
        'source_bindings': {'daily_source': source_bindings},
        'qualified_keys_storage': 'One collection inside source_bindings.daily_source.qualified_keys;no per-feature source/key dump.',
        'calendar': {'path': cal_binding['path'], 'sha256': cal_binding['sha256'], 'count': len(calendar)},
        'execution_tick_rules': {**manifest['execution_tick_binding'], 'no_feature_tick_rows_built': False,
            'parameters_path': par_binding['path'], 'parameters_sha256': par_binding['sha256'],
            'announcement_url': ANNOUNCEMENT, 'announcement_known_on': '2024-12-06',
            'known_asof_rule': 'At u freeze effective_pricetick(contract,next_calendar_D,configured);LC change known12/6. Last calendar row has D=None,current-day effective tick is feature-only and unusable for order.'},
        'features': {'path': str(OUT / 'features.csv'), 'sha256': digest((OUT / 'features.csv').read_bytes()), 'columns': columns, 'rows': len(features)},
        'summary': summary, 'feature_build_evidence_sha256': digest((OUT / 'feature_build_evidence.json').read_bytes()),
        'load_bound_daily_csv_calls': 1, 'build_ema_rows_calls': 1, 'financial_ready': False, 'production_qualified': False,
        'actual_trades_generated': 0, 'PnL_generated': False, 'new_financial_arms': 0,
        'confidence_scope': 'Raw same accepted baseline source research qualification,not independent full-market repricing or alpha proof.'}
    write('feature_manifest.json', feature_manifest)
    print(json.dumps({'summary': summary, 'features_sha256': feature_manifest['features']['sha256'], 'feature_manifest_sha256': digest((OUT / 'feature_manifest.json').read_bytes()), 'qualifier_sha256': qualifier_sha}, ensure_ascii=False))


if __name__ == '__main__':
    check(len(sys.argv) == 2 and sys.argv[1] in ('qualify', 'build'), 'choose qualify or build')
    (qualify if sys.argv[1] == 'qualify' else build)()
