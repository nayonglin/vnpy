"""Independent fixed-event identity and six SQL sentinels; never reads PnL."""
from pathlib import Path
import csv
import hashlib
import io
import json
import sqlite3
import subprocess
from datetime import datetime
import pandas as pd

LINE = Path(__file__).resolve().parents[2]
ROOT = LINE.parents[2]
DEST = Path(__file__).resolve().parent
SOURCE = LINE / 'outputs/stage006_daily_open_equivalence'
A0 = LINE / 'outputs/stage001_first_screen/A0_attempt2'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()


def main():
    summary = json.loads((SOURCE / 'data_open_equivalence.json').read_text())
    inputs = json.loads((SOURCE / 'input_manifest.json').read_text())
    assert summary['financial_replays'] == 0 and summary['pnl_columns_read'] == 0
    assert summary['execution_fallback_enabled'] is False
    assert summary['production_qualified'] is False
    assert all(sha(path) == value for path, value in inputs.items())
    assert all(sha(SOURCE/name) == value for name, value in summary['artifact_sha256'].items())
    events = pd.read_csv(SOURCE/'event_checks.csv').fillna('')
    anchors = pd.read_csv(A0/'execution_anchor_requests.csv').fillna('')
    orders = pd.read_csv(A0/'trades.csv', usecols=['trade_id','order_id','vt_symbol','trading_date','direction','offset'], dtype=str).fillna('')
    assert len(events) == len(anchors) == 535
    assert events.event_number.tolist() == list(range(1, 536))
    for name in ['vt_symbol','trading_date','order_id','offset','expected_start','actual_time','source']:
        assert events[name].tolist() == anchors[name].tolist()
    assert events.anchor_price.tolist() == anchors.price.tolist()
    orders['offset'] = orders.offset.replace({'开':'Open','平':'Close','平今':'CloseToday','平昨':'CloseYesterday'})
    orders['direction'] = orders.direction.replace({'多':'Long','空':'Short'})
    joined = events.merge(orders, on=['order_id','vt_symbol','trading_date','offset'], suffixes=('_audit','_order'), how='left', validate='one_to_one')
    assert joined.trade_id.ne('').all() and not joined.trade_id.isna().any()
    assert joined.direction_audit.eq(joined.direction_order).all()
    assert events.daily_row_count.eq(1).all() and events.physical_time_match.eq(True).all()
    assert events.expected_start_match.eq(True).all()
    assert events.price_exact_match.sum() == events.price_tolerance_match.sum() == 534
    assert events.loc[events.offset.eq('Open'),'price_exact_match'].sum() == 319
    anomaly = events.loc[~events.price_exact_match]
    assert len(anomaly) == 1
    anomaly = anomaly.iloc[0]
    assert anomaly.vt_symbol == 'au2610.SHFE' and anomaly.trading_date == '2026-10-14'
    assert anomaly.order_id == 'BACKTESTING.560' and anomaly.offset == 'Close' and anomaly.direction == 'Long'
    sample = [events.iloc[0], events.iloc[1], events.iloc[100], events.iloc[318], events.iloc[534], anomaly]
    sql_checks = []
    database = ROOT/'.vntrader/database.db'
    with sqlite3.connect(database.resolve().as_uri()+'?mode=ro&immutable=1', uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        for row in sample:
            native, exchange = row.vt_symbol.rsplit('.',1)
            result = db.execute("SELECT datetime,open_price FROM dbbardata WHERE symbol=? AND exchange=? AND interval='d' AND substr(datetime,1,10)=?", [native,exchange,row.trading_date]).fetchall()
            assert len(result) == 1 and float(result[0][1]) == row.daily_open_price
            assert abs(float(row.anchor_price)-float(result[0][1])) == row.absolute_price_difference
            sql_checks.append(dict(symbol=row.vt_symbol,trading_date=row.trading_date,
                daily_datetime=result[0][0],daily_open=float(result[0][1]),anchor=float(row.anchor_price),
                physical=row.actual_time,exact=bool(row.price_exact_match)))
        adjacent_db = db.execute("SELECT datetime,open_price FROM dbbardata WHERE symbol='au2610' AND exchange='SHFE' AND interval IN ('1m','m') AND datetime>='2026-10-13 20:59' AND datetime<'2026-10-13 21:03'").fetchall()
    cache = ROOT/'examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage861_stage860_full_visual_atlas_full_minute_bars_stage861_stage860_full_visual_atlas_v1.csv'
    target = subprocess.run(['rg','^au2610\\.SHFE,[^,]+,2026-10-13 (20:59|21:00|21:01|21:02)',str(cache)],capture_output=True,text=True,check=False)
    assert target.returncode in (0,1)
    rows = list(csv.reader(io.StringIO(target.stdout)))
    adjacent = [dict(symbol=r[0],physical_time=r[2],open=float(r[4]),high=float(r[5]),low=float(r[6]),close=float(r[7]),
        volume=float(r[8]),open_oi=float(r[9]),close_oi=float(r[10]),source=r[-1]) for r in rows]
    assert len(adjacent) == 1 and adjacent[0]['physical_time'] == '2026-10-13 21:00:00'
    assert adjacent[0]['open'] == 903.62 and adjacent[0]['volume'] == 0
    consumer = LINE/'tools/stage001_run_first_screen.py'
    final_consumer = json.loads((LINE/'outputs/stage002_independent_review/consumer_checks.json').read_text())
    assert sha(consumer) == final_consumer['runner_sha256']
    report = dict(reviewed_at=datetime.now().astimezone().isoformat(timespec='seconds'),
        status='limited_fixed_event_equivalence_audit_review_pass_global_equivalence_false',
        production_qualified=False, financial_replays=0, pnl_columns_read=0, execution_fallback_enabled=False,
        fixed_events_identity_checked=535, unique_exact_order_joins=535, direction_join_matches=535,
        exact_prices_from_fixed_event_table=534, Open_event_exact_matches=319,
        real_daily_SQL_sentinel_queries=len(sql_checks), SQL_sentinels=sql_checks,
        unique_anomaly=anomaly.to_dict(), anomaly_order_meaning='Long is buy direction; Close+Long is closing a short, not a long position',
        existing_cache_adjacent_rows=adjacent, existing_DB_adjacent_minute_rows=adjacent_db,
        expected_original_daily_CSV_exists=(ROOT/'examples/portfolio_backtesting/downloaded_futures/tqsdk_daily_2010_2026_04/SHFE/au2610.csv').exists(),
        observed_fact='unique daily open904.98 differs from zero-volume canonical21:00 open903.62 by1.36',
        inference_only='zero-trade minute carry versus daily first-trade/auction/source convention is a possible cause, not established without adjacent raw trades/auction data',
        limits='6 independent daily SQL sentinels plus all535 identity joins; no repeated535 SQL audit, no PnL/account reconstruction, no source repair or broader QA',
        unchanged_consumer_sha256=sha(consumer), source_summary_sha256=sha(SOURCE/'data_open_equivalence.json'),
        all_audit_input_fingerprints_match=True, source_scope='fixed535 accepted A0 events only; cannot generalize319 matching Opens to unseen candidate paths')
    DEST.mkdir(parents=True,exist_ok=True)
    (DEST/'fixed_event_checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__ == '__main__': main()
