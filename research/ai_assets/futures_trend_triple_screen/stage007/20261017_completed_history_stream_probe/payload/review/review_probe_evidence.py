"""Offline independent review of a saved 345-minute probe; no TqSdk import."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
from importlib import metadata
import ast
import base64
import csv
import hashlib
import json
import math
import sqlite3

LINE = Path(__file__).resolve().parents[2]
ROOT = LINE.parents[2]
DEST = Path(__file__).resolve().parent
SOURCE = LINE / 'outputs/stage007_tqsdk_stream_probe'
ATTEMPT = SOURCE / 'network_attempt1'
PROJECT = ROOT / 'examples/portfolio_backtesting'
CSV = PROJECT / 'downloaded_futures/tqsdk_daily_2010_2026_04/SHFE/rb2010.csv'
IMPORTER = PROJECT / 'import_tqsdk_all_futures_daily_to_db.py'
TOOL = LINE / 'tools/stage007_tqsdk_stream_probe.py'
FIELDS = ['open', 'high', 'low', 'close', 'volume', 'open_oi', 'close_oi']


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def minute_range(start, count):
    return [datetime.fromisoformat(start) + timedelta(minutes=i) for i in range(count)]


def main():
    preflight = json.loads((SOURCE / 'preflight.json').read_text())
    parent = json.loads((ATTEMPT / 'parent_receipt.json').read_text())
    worker = json.loads((ATTEMPT / 'worker_receipt.json').read_text())
    quality = json.loads((ATTEMPT / 'quality.json').read_text())
    assert sha(SOURCE / 'preflight.json') == parent['preflight_sha256']
    assert all(sha(ATTEMPT / name) == value for name, value in parent['artifact_sha256'].items())
    assert parent['exit_code'] == 1 and parent['all_inputs_unchanged']
    assert parent['elapsed_seconds'] < parent['parent_timeout_seconds'] == 180
    assert parent['no_automatic_retry'] and parent['provider_replay_attempts_max'] == 1
    assert worker['provider_replay_attempts'] == 1 and worker['local_TqSim_created']
    assert worker['status'] == 'completed_quality_rejected'
    assert quality['accepted'] is False and quality['completion_evidence_complete']
    assert quality['daily_csv_check']['status'] == 'accepted'
    assert quality['database_check']['status'] == 'quarantined'
    assert quality['database_check']['daily_mismatch_fields'] == ['close_oi']
    for receipt in (parent, worker):
        for field in ('financial_strategy_replays', 'broker_or_ctp_connections', 'order_calls', 'cancel_calls'):
            assert receipt[field] == 0
        assert receipt['credential_values_saved'] is False
        assert receipt['production_qualified'] is False
        assert receipt['execution_fallback_enabled'] is False

    # Independent explicit rb session grid, not a call to the implementation/helper.
    grid = (minute_range('2020-08-11T21:00:00', 120)
            + minute_range('2020-08-12T09:00:00', 75)
            + minute_range('2020-08-12T10:30:00', 60)
            + minute_range('2020-08-12T13:30:00', 90))
    with (ATTEMPT / 'raw_completed_minutes.csv').open(newline='') as f:
        raw = list(csv.DictReader(f))
    with (ATTEMPT / 'completion_evidence.csv').open(newline='') as f:
        evidence = list(csv.DictReader(f))
    times = [datetime.fromisoformat(row['bar_datetime']) for row in raw]
    assert times == grid and len(set(times)) == len(raw) == len(evidence) == 345
    assert all(row['vt_symbol'] == 'rb2010.SHFE' for row in raw + evidence)
    evidence_map = {datetime.fromisoformat(row['bar_datetime']): row for row in evidence}
    assert set(evidence_map) == set(grid)
    for moment in grid:
        row = evidence_map[moment]
        assert row['method'] == 'observed_later_serial_kline' and row['completed'] == 'True'
        assert datetime.fromisoformat(row['successor_time']) >= moment + timedelta(minutes=1)
    assert evidence_map[grid[-1]]['successor_time'] == '2020-08-12T21:00:00'
    values = [{field: float(row[field]) for field in FIELDS} for row in raw]
    for row in values:
        assert all(math.isfinite(x) for x in row.values())
        assert min(row[k] for k in ['open', 'high', 'low', 'close']) > 0
        assert min(row[k] for k in ['volume', 'open_oi', 'close_oi']) >= 0
        assert row['low'] <= min(row['open'], row['close']) <= max(row['open'], row['close']) <= row['high']
    aggregate = dict(open=values[0]['open'], high=max(row['high'] for row in values),
        low=min(row['low'] for row in values), close=values[-1]['close'],
        volume=math.fsum(row['volume'] for row in values), open_oi=values[0]['open_oi'], close_oi=values[-1]['close_oi'])
    daily_csv = {}
    with CSV.open(encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            if row['trade_date'] in ['2020-08-11', '2020-08-12', '2020-08-13']:
                assert row['trade_date'] not in daily_csv
                daily_csv[row['trade_date']] = {key: float(row[key]) for key in FIELDS}
    assert len(daily_csv) == 3
    assert aggregate == daily_csv['2020-08-12'] == quality['daily_csv_check']['aggregate']

    database = ROOT / '.vntrader/database.db'
    with sqlite3.connect(database.resolve().as_uri() + '?mode=ro&immutable=1', uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        db_rows = db.execute("SELECT datetime,open_price,high_price,low_price,close_price,volume,open_interest "
            "FROM dbbardata WHERE symbol='rb2010' AND exchange='SHFE' AND interval='d' "
            "AND datetime>='2020-08-11' AND datetime<'2020-08-14' ORDER BY datetime").fetchall()
    assert len(db_rows) == 3
    oi_checks = []
    for row in db_rows:
        day = row[0][:10]
        reference = daily_csv[day]
        for key, item in zip(['open', 'high', 'low', 'close', 'volume'], row[1:6]):
            assert float(item) == reference[key]
        assert float(row[6]) == reference['open_oi']
        assert float(row[6]) != reference['close_oi']
        oi_checks.append(dict(date=day, database_open_interest=float(row[6]),
            csv_open_oi=reference['open_oi'], csv_close_oi=reference['close_oi'],
            OHLCV_exact=True, database_matches_csv_open_oi=True, database_matches_csv_close_oi=False))

    importer_tree = ast.parse(IMPORTER.read_text())
    importer_keyword = next(keyword for node in ast.walk(importer_tree) if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name) and node.func.id == 'BarData'
        for keyword in node.keywords if keyword.arg == 'open_interest')
    assert any(isinstance(n, ast.Constant) and n.value == 'open_oi' for n in ast.walk(importer_keyword.value))
    tool_source = TOOL.read_text()
    tool_tree = ast.parse(tool_source)
    worker_ast = next(n for n in tool_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'worker')
    call_names = []
    for n in ast.walk(worker_ast):
        if isinstance(n, ast.Call):
            call_names.append(n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id if isinstance(n.func, ast.Name) else '')
    assert 'TqSim' in call_names and 'TqAuth' in call_names and 'TqApi' in call_names and 'TqBacktest' in call_names
    assert not set(call_names) & {'insert_order', 'cancel_order', 'TargetPosTask', 'TqAccount', 'TqKq'}
    assert "['open','high','low','close','volume','close_oi']" in tool_source
    assert "pd.to_datetime(value,unit='ns',utc=True" in tool_source
    assert "process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--_worker',str(os.getpid())]" in tool_source
    assert 'stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True' in tool_source
    assert 'os.killpg(process.pid,signal.SIGKILL)' in tool_source
    assert 'redirect_stdout(discard),redirect_stderr(discard)' in tool_source
    assert 'logging.disable(logging.CRITICAL)' in tool_source
    assert "if ATTEMPT.exists():raise FileExistsError('existing_provider_attempt_refusing_retry')" in tool_source

    # Match installed wheel RECORD and the actual preflight fingerprint, without importing TqSdk.
    dist = metadata.distribution('tqsdk')
    sdk_names = {'tqsdk/api.py', 'tqsdk/auth.py', 'tqsdk/tradeable/sim/tqsim.py',
                 'tqsdk/backtest/backtest.py', 'tqsdk/tools/downloader.py'}
    sdk_checks = []
    for path in dist.files:
        if str(path) not in sdk_names:
            continue
        actual = dist.locate_file(path).resolve()
        digest = hashlib.sha256(actual.read_bytes()).digest()
        encoded = base64.urlsafe_b64encode(digest).decode().rstrip('=')
        assert path.hash and path.hash.mode == 'sha256' and path.hash.value == encoded
        assert digest.hex() == preflight['source_fingerprints'][str(actual)]
        sdk_checks.append(dict(path=str(actual), sha256=digest.hex(), matches_install_RECORD=True,
                               matches_preflight=True))
    assert len(sdk_checks) == 5 and metadata.version('tqsdk') == '3.10.2'
    for path in (TOOL, CSV, LINE / 'stages/20261017_2338_stage007_tqsdk_official_stream_probe_protocol.md'):
        assert sha(path) == preflight['source_fingerprints'][str(path)]
    # One independent clock arithmetic sentinel, no serial replay or SDK call.
    utc = datetime(2020, 8, 11, 13, tzinfo=timezone.utc)
    assert utc.astimezone(timezone(timedelta(hours=8))).replace(tzinfo=None) == grid[0]

    report = dict(reviewed_at=datetime.now().astimezone().isoformat(timespec='seconds'),
        status='saved_completed_probe_review_pass_original_quality_remains_rejected',
        original_quality_accepted=False, original_worker_status=worker['status'], parent_exit_code=1,
        p0_findings=0, known_field_semantics_findings=1,
        network_connections_in_review=0, provider_replays_in_review=0,
        provider_probe_attempts_historical=1, provider_probe_elapsed_seconds=parent['elapsed_seconds'],
        financial_replays=0, orders_or_cancel_calls=0, credential_config_read_by_reviewer=False,
        independent_exact_grid_and_evidence_rows=345, raw_rows_finite_legal_unique=True,
        last_target_bar=grid[-1].isoformat(), observed_successor_for_last_target=evidence_map[grid[-1]]['successor_time'],
        completion_evidence_scope='saved successor record for every accepted target; collector code only accepts a non-final serial row with strictly later successor; original provider serial/log is deliberately not retained',
        UTC_to_Shanghai_source_and_clock_sentinel_match=True,
        independent_minute_aggregate=aggregate, all7_CSV_daily_fields_exact=True,
        exact_SQL_daily_rows_checked=3, DB_vs_CSV_OI=oi_checks,
        importer_open_interest_keyword_line=importer_keyword.lineno,
        importer_open_interest_expression=ast.unparse(importer_keyword.value), importer_sha256=sha(IMPORTER),
        root_cause='Stage007 maps database open_interest to close_oi, but this accepted rb CSV import writes row.open_oi into database open_interest',
        target_database_open_oi_verified=aggregate['open_oi'], target_database_close_oi='not_provided_unknown',
        corrected_semantics_scope='exact rb2010 source and three observed dates plus original importer contract; no claim that every DB row from all sources has identical provenance',
        raw_data_requalification_done=False, original_rejected_quality_preserved=True,
        sdk_auth_and_related_files_match_wheel_RECORD_and_preflight=sdk_checks,
        no_order_evidence='static worker call graph creates only TqSim and calls data API; parent/worker allowlisted receipts report zero orders/cancels; no broker account is passed',
        credentials_policy='tool locally reads settings, passes only in-process TqAuth; no values in subprocess argv or receipts; SDK stdout/stderr/logging discarded; reviewer did not read private settings',
        hard_timeout_evidence='single parent Popen session; 180s parent deadline, killpg SIGKILL on timeout and finally, no retry; actual probe finished before deadline',
        source_data_writes=False, cache_or_overlay_written=False, execution_fallback_enabled=False, production_qualified=False,
        stage008_boundary='separate declared field-aware requalification may check DB OHLCV+known openOI; DB closeOI remains unknown; Stage007 files remain immutable/rejected',
        financial_attempts_cumulative_unchanged=4, financial_completed_cumulative_unchanged=1,
        C0_alpha_verdict='not_evaluable', C0_attempt3_authorized=False,
        overfitting=False, overfitting_reason='data completion and source schema verified without outcomes or parameter choice',
        continued_value=True, continued_value_reason='correct source-field qualification separates provider capability from importer semantic mismatch',
        checked_artifacts_sha256={str(p): sha(p) for p in [SOURCE / 'preflight.json', *sorted(ATTEMPT.iterdir()), TOOL, IMPORTER] if p.is_file()})
    (DEST / 'probe_evidence_checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({k: report[k] for k in ['status', 'independent_exact_grid_and_evidence_rows',
        'all7_CSV_daily_fields_exact', 'exact_SQL_daily_rows_checked', 'target_database_close_oi',
        'original_rejected_quality_preserved', 'network_connections_in_review']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
