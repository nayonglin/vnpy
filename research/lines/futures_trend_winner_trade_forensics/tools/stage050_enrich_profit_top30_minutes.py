"""Add bounded, audited 15m layers to the frozen Stage049 atlas. No strategy run."""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import pandas as pd

import stage038_c9_15w_big_winner_multiscale_html as atlas


OUT = atlas.STAGE061_TOP10_OUTPUT_DIR
BASE_HTML_SHA = 'd07e8b6f16d4b565f791a8696a1600eb792adf3ea45db6757ceb691cb057fbe9'
BASE_JSON_SHA = 'a46cf5905ddfbdf15a52d185f6ae444d891445c7e64eb5d562f1964248b76a2b'
COLS = ['vt_symbol', 'bar_datetime', 'trading_day', 'open', 'high', 'low', 'close', 'volume']
DAY_SLOTS = {'09:00','09:15','09:30','09:45','10:00','10:30','10:45','11:00','11:15','13:30','13:45','14:00','14:15','14:30','14:45'}


def completed_serial_rows(serial: pd.DataFrame, seen: set[int]) -> pd.DataFrame:
    completed = serial.iloc[:-1]
    completed = completed[completed.id.ge(0) & completed.datetime.gt(0) & ~completed.id.isin(seen)].copy()
    seen.update(int(value) for value in completed.id)
    return completed


def terminal_completed_row(serial: pd.DataFrame, seen: set[int], completed_until: pd.Timestamp) -> pd.DataFrame:
    """Only call after normal replay completion; expiry may leave no next candle."""
    last = serial.iloc[-1:]
    if last.empty or last.iloc[0]['id'] < 0 or int(last.iloc[0]['id']) in seen:
        return last.iloc[:0]
    stamp = atlas._normalize_tq_datetime(last.iloc[0]['datetime'])
    if pd.isna(stamp) or stamp+pd.Timedelta(minutes=15) > completed_until:
        return last.iloc[:0]
    seen.add(int(last.iloc[0]['id']))
    return last.copy()


def fetch_history(symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Read all completed historical rows, including replay initialization/jumps."""
    username = str(atlas.SETTINGS.get('datafeed.username', ''))
    password = str(atlas.SETTINGS.get('datafeed.password', ''))
    if not username or not password:
        raise RuntimeError('Historical market credentials are missing')
    api = None
    chunks, seen = [], set()
    try:
        api = atlas.TqApi(atlas.TqSim(), backtest=atlas.TqBacktest(
            start_dt=(start-pd.Timedelta(days=7)).to_pydatetime(),
            end_dt=(end+pd.Timedelta(days=14,hours=23,minutes=59)).to_pydatetime()),
            auth=atlas.TqAuth(username,password))
        serial = api.get_kline_serial(atlas._to_tq_symbol(symbol), duration_seconds=900, data_length=500)
        deadline = time.monotonic()+210
        while time.monotonic() < deadline:
            api.wait_update(deadline=time.time()+5)
            complete = completed_serial_rows(serial,seen)
            if not complete.empty:
                chunks.append(complete)
        raise TimeoutError('Bounded historical reader timed out')
    except atlas.BacktestFinished:
        completed_until = min(end+pd.Timedelta(days=14,hours=23,minutes=59),
                              pd.Timestamp.now(tz='Asia/Shanghai').tz_localize(None))
        final = terminal_completed_row(serial, seen, completed_until)
        if not final.empty:
            chunks.append(final)
    finally:
        if api is not None:
            api.close()
    if not chunks:
        raise RuntimeError(f'No completed historical bars for {symbol}')
    data = pd.concat(chunks,ignore_index=True)
    data['bar_datetime'] = data.datetime.map(atlas._normalize_tq_datetime)
    data['vt_symbol'] = symbol
    return data[['vt_symbol','bar_datetime','open','high','low','close','volume']].dropna().sort_values('bar_datetime')


def select_profit_top(records: list[dict], count: int = 30) -> dict[str, dict]:
    if count < 1:
        raise ValueError('count must be positive')
    selected = {}
    for direction, sign in [('long', 1), ('short', -1)]:
        eligible = []
        for record in records:
            m = record['meta']
            if m['result_type'] != 'profit' or m['direction'] != direction:
                continue
            pct = float(m['price_change_pct'])
            if not math.isfinite(pct) or pct * sign <= 0:
                raise ValueError(f'Invalid profitable price change: {m["open_trade_id"]}')
            eligible.append(m)
        eligible.sort(key=lambda m: (-sign * float(m['price_change_pct']), m['entry_date'], m['open_trade_id']))
        for rank, m in enumerate(eligible[:count], 1):
            key = m['open_trade_id']
            if key in selected:
                raise ValueError(f'Duplicate trade: {key}')
            selected[key] = {'direction': direction, 'rank': rank, 'gain_pct': sign * float(m['price_change_pct'])}
    return selected


def aggregate_local_minutes(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Only aggregate all 15 one-minute bars; a truncated bucket is not a candle."""
    data = frame.copy()
    data['bar_datetime'] = pd.to_datetime(data['bar_datetime'], errors='coerce')
    data = data.dropna(subset=['bar_datetime', 'open', 'high', 'low', 'close', 'volume'])
    data = data.drop_duplicates('bar_datetime', keep='last').sort_values('bar_datetime')
    rows = []
    for start, group in data.groupby(data.bar_datetime.dt.floor('15min'), sort=True):
        expected = pd.date_range(start, periods=15, freq='min')
        if len(group) != 15 or group.bar_datetime.tolist() != expected.tolist():
            continue
        rows.append({'vt_symbol': symbol, 'bar_datetime': start, 'open': group.open.iloc[0],
                     'high': group.high.max(), 'low': group.low.min(), 'close': group.close.iloc[-1],
                     'volume': group.volume.sum(), 'origin': 'local_1m_complete_15bar_bucket'})
    return pd.DataFrame(rows, columns=[*COLS[:2], *COLS[3:], 'origin'])


def expected_night_slots(symbol: str, day: pd.Timestamp, calendar: list[pd.Timestamp]) -> set[str]:
    """Bounded historical session table for this frozen atlas, not a live calendar.

    Sources: xfqh.cn/dt/142.52392.html (2019-12-25 late open);
    cfc108.com/zxjtqh/2019-12/10/article_414860.shtml (CZCE hours change);
    nanhua.net 2020-04-24 customer notice (2020-05-06 evening restart).
    Holiday reopening is derived from the frozen product calendar, excluding weekends.
    """
    product = atlas.s719._infer_product(symbol).lower()
    if product in {'ap','sm','lh','lc','si'}:
        return set()
    if product not in {'cf','fg','ma','oi','sa','sh','cu','fu','hc','jm','rb','ru','sp'}:
        raise ValueError(f'No audited historical night schedule for {symbol}')
    if pd.Timestamp('2020-02-03') <= day <= pd.Timestamp('2020-05-06'):
        return set()
    pos = calendar.index(day)
    if pos == 0 or calendar[pos-1] != day-pd.offsets.BDay(1):
        return set()
    start = 22*60+30 if day == pd.Timestamp('2019-12-26') else 21*60
    end = 25*60 if product == 'cu' else 23*60
    if symbol.endswith('.CZCE') and day < pd.Timestamp('2019-12-12'):
        end = 23*60+30
    return {f'{(minute//60)%24:02}:{minute%60:02}' for minute in range(start,end,15)}


def day_issues(frame: pd.DataFrame, expected_night: set[str] | None = None) -> list[str]:
    if frame.empty:
        return ['no_bars']
    issues = []
    dates = pd.to_datetime(frame.bar_datetime)
    slots = set(dates.dt.strftime('%H:%M'))
    if not DAY_SLOTS.issubset(slots):
        issues.append('day_session_slots_missing')
    values = frame[['open', 'high', 'low', 'close', 'volume']].apply(pd.to_numeric, errors='coerce')
    valid = (np.isfinite(values).all(axis=1) & values[['open','high','low','close']].gt(0).all(axis=1)
             & values.volume.ge(0) & values.high.ge(values[['open','close','low']].max(axis=1))
             & values.low.le(values[['open','close','high']].min(axis=1)))
    if not valid.all():
        issues.append('invalid_ohlcv')
    if dates.duplicated().any():
        issues.append('duplicate_timestamp')
    night = dates[(dates.dt.hour >= 20) | (dates.dt.hour < 3)].sort_values()
    night_start = '22:30' if len(night) and night.iloc[0].date().isoformat() == '2019-12-25' else '21:00'
    if len(night) and night.iloc[0].strftime('%H:%M') != night_start:
        issues.append('night_session_start_missing')
    if len(night) and (night.diff().dropna() != pd.Timedelta(minutes=15)).any():
        issues.append('night_session_internal_gap')
    if expected_night is not None:
        actual = set(night.dt.strftime('%H:%M'))
        if expected_night-actual:
            issues.append('night_session_slots_missing')
        if actual-expected_night:
            issues.append('unexpected_night_slots')
    return issues


def merge_completed_days(existing: pd.DataFrame, fetched: pd.DataFrame,
                         calendar: list[pd.Timestamp] | None = None) -> pd.DataFrame:
    """Replay padding may start/end mid-session; it must not degrade a good day."""
    parts = []
    all_days = sorted(set(pd.to_datetime(existing.trading_day)) | set(pd.to_datetime(fetched.trading_day)))
    for day in all_days:
        old = existing[pd.to_datetime(existing.trading_day).eq(day)]
        new = fetched[pd.to_datetime(fetched.trading_day).eq(day)]
        sample = new if not new.empty else old
        expected = expected_night_slots(str(sample.vt_symbol.iloc[0]),day,calendar) if calendar is not None else None
        if new.empty:
            chosen = old
        elif old.empty or not day_issues(new,expected):
            chosen = new
        elif not day_issues(old,expected):
            chosen = old
        else:
            chosen = new if len(new) > len(old) else old
        if not chosen.empty:
            parts.append(chosen)
    return pd.concat(parts,ignore_index=True) if parts else pd.DataFrame(columns=COLS)


def visible_rows(record: dict) -> list[tuple[str, str, float]]:
    m, d = record['meta'], record['daily']
    return [(day, symbol, x) for day, symbol, x in zip(d['date'], d['source'], d['x'])
            if m['intraday_start'] <= day <= m['intraday_end']]


def enrich_record(record: dict, bars: pd.DataFrame, selection: dict) -> tuple[dict, list[dict]]:
    result = copy.deepcopy(record)
    meta = result['meta']
    parts, audit = [], []
    by_symbol = {}
    for symbol, group in bars.groupby('vt_symbol', sort=False):
        group = group.sort_values('bar_datetime').drop_duplicates('bar_datetime').copy()
        # Real historical warmup, separately per contract; no proxy price splice in MA.
        by_symbol[symbol] = atlas._add_moving_averages(group)
    missing = []
    for day, symbol, x in visible_rows(record):
        history = by_symbol.get(symbol, pd.DataFrame(columns=COLS))
        group = history[pd.to_datetime(history.trading_day).eq(pd.Timestamp(day))].copy()
        calendar = list(pd.to_datetime(record['daily']['date']))
        expected = expected_night_slots(symbol,pd.Timestamp(day),calendar)
        issues = day_issues(group,expected)
        if issues:
            missing.append(day)
        if not group.empty:
            group['x'] = x - 0.5 + (np.arange(len(group)) + 0.5) / len(group)
            parts.append(group)
        audit.append({'open_trade_id': meta['open_trade_id'], 'trading_day': day, 'source': symbol,
                      'bars': len(group), 'status': 'missing' if group.empty else ('partial' if issues else 'covered'),
                      'issues': '|'.join(issues), 'expected_night_bars':len(expected),
                      'origin': '|'.join(sorted(set(group.get('origin', []))))})
    minute = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=[*COLS, 'x', *[f'ma{p}' for p in atlas.MA_PERIODS]])
    payload = {column: [atlas._json_safe(v) for v in minute[column].tolist()]
               for column in ['x','open','high','low','close','volume', *[f'ma{p}' for p in atlas.MA_PERIODS]]}
    payload.update({'datetime': [pd.Timestamp(v).strftime('%Y-%m-%d %H:%M') for v in minute.bar_datetime],
                    'trading_day': [pd.Timestamp(v).date().isoformat() for v in minute.trading_day],
                    'source': minute.vt_symbol.tolist()})
    meta.update({'draw_intraday': int(not minute.empty), 'intraday_top_rank': selection['rank'],
                 'intraday_selection': f"{'多头' if selection['direction']=='long' else '空头'}盈利涨跌幅Top30 · 第{selection['rank']}名",
                 'missing_15m_dates': missing, 'intraday_daily_preserved': True,
                 'intraday_ma40_warmup_missing_bars': int(minute.ma40.isna().sum())})
    result['intraday'] = payload
    return result, audit


def read_cache(path: Path, symbol: str, dates: list[pd.Timestamp]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=COLS)
    data = pd.read_csv(path)
    if data.empty:
        return pd.DataFrame(columns=COLS)
    data = data[data.vt_symbol.eq(symbol)].copy()
    data['bar_datetime'] = pd.to_datetime(data.bar_datetime)
    return atlas._assign_trading_day(data.drop(columns='trading_day', errors='ignore'), dates)


def request_dates(records: list[dict], selection: dict, mapping: pd.DataFrame) -> dict[str, set[pd.Timestamp]]:
    requests = {}
    for record in records:
        if record['meta']['open_trade_id'] not in selection:
            continue
        for day, symbol, _ in visible_rows(record):
            requests.setdefault(symbol, set()).add(pd.Timestamp(day))
    for symbol, days in requests.items():
        calendar = atlas._product_calendar(mapping, symbol)
        # Four previous trading days guarantee >=40 bars for the commodity day session.
        warm = set()
        for day in days:
            pos = calendar.index(day)
            warm.update(calendar[max(0, pos-4):pos])
        days.update(warm)
    return requests


def validate_base(path: Path) -> dict:
    if atlas._sha256(path) != BASE_JSON_SHA:
        raise RuntimeError('Frozen base fingerprint mismatch')
    return json.loads(path.read_text())


def load_base() -> tuple[list[dict], dict]:
    base = OUT / 'minute_enrichment_base.json'
    if base.exists():
        document = validate_base(base)
        if document['html_sha256'] != BASE_HTML_SHA:
            raise RuntimeError('Unexpected enrichment base identity')
        return document['records'], document['summary']
    html_path = OUT / 'index.html'
    if atlas._sha256(html_path) != BASE_HTML_SHA:
        raise RuntimeError('Original Stage049 HTML fingerprint mismatch; do not overwrite')
    records = json.JSONDecoder().raw_decode(html_path.read_text().split('const records=', 1)[1])[0]
    summary = json.loads((OUT / 'summary.json').read_text())
    if summary['source_commit'] != atlas.STAGE061_TOP10_SOURCE_COMMIT:
        raise RuntimeError('Frozen source commit mismatch')
    base.write_text(json.dumps({'html_sha256': BASE_HTML_SHA, 'records': records, 'summary': summary}, ensure_ascii=False, separators=(',',':')))
    validate_base(base)
    return records, summary


def collect_cache(requests: dict, mapping: pd.DataFrame, download: bool) -> tuple[pd.DataFrame, list[dict]]:
    cache_dir = OUT / 'minute_top30_cache'
    cache_dir.mkdir(exist_ok=True)
    old = pd.read_csv(atlas.MINUTE_15M_PATH)
    all_frames, statuses = [], []
    for index, (symbol, days) in enumerate(sorted(requests.items()), 1):
        calendar = atlas._product_calendar(mapping, symbol)
        cache_file = cache_dir / f'{symbol}.csv'
        data = read_cache(cache_file, symbol, calendar)
        old_symbol = old[old.vt_symbol.eq(symbol)].copy()
        if not old_symbol.empty:
            old_symbol['bar_datetime'] = pd.to_datetime(old_symbol.bar_datetime)
            old_symbol = atlas._assign_trading_day(old_symbol.drop(columns='trading_day', errors='ignore'), calendar)
            old_symbol['origin'] = 'existing_tqsdk_15m_cache'
            data = pd.concat([old_symbol, data], ignore_index=True) if not data.empty else old_symbol
        # Reuse local minute data only as whole, validated fifteen-bar candles.
        raw_symbol, exchange = symbol.split('.')
        local_paths = sorted(atlas.LOCAL_MINUTE_ROOT.glob(f'*/{exchange}/{raw_symbol}_completed_minute_backtest.csv'))
        local_frames = []
        for path in local_paths:
            local = pd.read_csv(path, usecols=['bar_datetime','open','high','low','close','volume'])
            local['bar_datetime'] = pd.to_datetime(local.bar_datetime)
            local = local[local.bar_datetime.between(min(days)-pd.Timedelta(days=7), max(days)+pd.Timedelta(days=1))]
            if not local.empty:
                local_frames.append(local)
        if local_frames:
            local = aggregate_local_minutes(pd.concat(local_frames, ignore_index=True), symbol)
            local = atlas._assign_trading_day(local, calendar)
            data = pd.concat([local, data], ignore_index=True) if not data.empty else local
        data = data.drop_duplicates(['vt_symbol','bar_datetime'], keep='last')
        data = data[pd.to_datetime(data.trading_day).isin(days)].copy()
        missing = [d for d in sorted(days) if day_issues(data[pd.to_datetime(data.trading_day).eq(d)],expected_night_slots(symbol,d,calendar))]
        status = {'symbol': symbol, 'required_days':len(days), 'local_missing_days':len(missing), 'downloaded':False}
        if missing and download:
            # One bounded child prevents a stalled data connection from blocking the atlas indefinitely.
            task_path = cache_dir / f'{symbol}.request.json'
            task_path.write_text(json.dumps({'symbol':symbol, 'start':min(missing).date().isoformat(),
                                             'end':max(missing).date().isoformat(), 'output':str(cache_dir / f'{symbol}.download.csv')}))
            print(f'15m download {index}/{len(requests)} {symbol}: {len(missing)} days', flush=True)
            try:
                process = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--fetch-task', str(task_path)],
                                         capture_output=True, text=True, timeout=240)
                status['returncode'] = process.returncode
                if process.returncode == 0:
                    fetched = read_cache(cache_dir / f'{symbol}.download.csv', symbol, calendar)
                    fetched['origin'] = 'tqsdk_completed_15m_replay'
                    fetched = fetched[pd.to_datetime(fetched.trading_day).isin(days)]
                    data = merge_completed_days(data, fetched, calendar)
                    status['downloaded'] = True
                else:
                    status['error'] = 'historical_reader_failed'
            except subprocess.TimeoutExpired:
                status['error'] = 'historical_reader_timeout_240s'
        data = data.sort_values('bar_datetime').drop_duplicates(['vt_symbol','bar_datetime'], keep='last')
        data.to_csv(cache_file, index=False)
        status['remaining_days'] = sum(bool(day_issues(data[pd.to_datetime(data.trading_day).eq(d)],expected_night_slots(symbol,d,calendar))) for d in days)
        status['download_allowed_this_run'] = download
        status['cache_origin_counts'] = data['origin'].value_counts().to_dict() if 'origin' in data else {}
        status['bars'] = len(data)
        statuses.append(status)
        if not data.empty:
            all_frames.append(data)
        print(f'15m cache {index}/{len(requests)} {symbol}: {len(data)} bars; gaps={status["remaining_days"]}', flush=True)
        (cache_dir / 'collection_status.json').write_text(json.dumps(statuses, ensure_ascii=False, indent=2))
    return (pd.concat(all_frames, ignore_index=True) if all_frames else pd.DataFrame(columns=COLS)), statuses


def publish(records: list[dict], summary: dict, selection: dict, bars: pd.DataFrame, statuses: list[dict]) -> dict:
    enriched, audits = [], []
    for record in records:
        key = record['meta']['open_trade_id']
        if key in selection:
            result, audit = enrich_record(record, bars, selection[key])
            enriched.append(result)
            audits.extend(audit)
        else:
            enriched.append(copy.deepcopy(record))
    # An invariant, not a numerical tolerance: non-minute chart and trade fields cannot change.
    for before, after in zip(records, enriched):
        for key in ['daily', 'weekly', 'monthly', 'day10', 'day30']:
            if before[key] != after[key]:
                raise RuntimeError(f'Frozen {key} changed')
        for key, value in before['meta'].items():
            if key not in ['draw_intraday', 'missing_15m_dates'] and value != after['meta'][key]:
                raise RuntimeError(f'Frozen trade field {key} changed')
    audit_frame = pd.DataFrame(audits)
    audit_path = OUT / 'minute_top30_coverage.csv'
    audit_frame.to_csv(audit_path, index=False)
    selected_path = OUT / 'minute_top30_selection.csv'
    pd.DataFrame([{**r['meta'], **selection[r['meta']['open_trade_id']]} for r in records if r['meta']['open_trade_id'] in selection]).to_csv(selected_path,index=False)
    bars_path = OUT / 'profit_top30_bars_15m.csv'
    bars.to_csv(bars_path, index=False)
    summary = copy.deepcopy(summary)
    summary.update({'stage':'Stage050', 'model_tag':'stage050_profit_top30_each_side_minutes_v1',
                    'bars_15m':len(bars), 'chart_bars_15m':sum(len(r['intraday']['x']) for r in enriched),
                    'intraday_draw_episodes':sum(r['meta']['draw_intraday'] for r in enriched),
                    'intraday_missing_days':int(audit_frame.status.ne('covered').sum()),
                    'intraday_top_selection':{'per_direction':30, 'count':len(selection), 'basis':'direction_adjusted_price_change_pct',
                                              'warmup_trading_days':4, 'visible_pre_days':5,'visible_post_days':5},
                    'market_download_disabled':not any(s.get('download_allowed_this_run') for s in statuses),
                    'downloaded_this_run':any(s['downloaded'] for s in statuses),
                    'minute_cache_origin_counts':bars.origin.value_counts().to_dict(), 'fetch_status':statuses,
                    'minute_enrichment_base_html_sha256':BASE_HTML_SHA, 'frozen_nonminute_equal':True,
                    'page_title':summary['page_title']+' / 盈利多空各Top30·15分钟K',
                    'coverage_note':('全部391笔交易保留原有多周期图；盈利多头按涨幅、空头按跌幅各前30笔补15分钟K，其他交易不画分钟线。'
                                     '分钟窗口为开仓前5个交易日至最终平仓后5个交易日，均线使用额外真实历史预热。'
                                     '日线保留冻结源，不用新分钟线改写；不同数据源的日线收盘口径可能与最后一根分钟收盘略有差异。缺失或不完整交易日单独标注。')})
    manifest = pd.DataFrame([{**r['meta'], **{k+'_bars':len(r[k]['x']) for k in ['day30','day10','monthly','daily','weekly']},
                              'bars_15m':len(r['intraday']['x']), 'intraday_missing_days':len(r['meta']['missing_15m_dates'])} for r in enriched])
    manifest_path = OUT / 'chart_manifest.csv'
    manifest.to_csv(manifest_path,index=False,encoding='utf-8-sig')
    summary['artifacts'].update({'bars_15m':str(bars_path),'minute_selection':str(selected_path),'minute_coverage':str(audit_path)})
    html_path = OUT / 'index.html'
    temporary = OUT / 'index.enrichment.tmp'
    temporary.write_text(atlas._html(enriched, summary), encoding='utf-8')
    temporary.replace(html_path)
    summary['artifact_sha256'].update({k:atlas._sha256(p) for k,p in {'html':html_path,'manifest':manifest_path,'bars_15m':bars_path,
                                                                  'minute_selection':selected_path,'minute_coverage':audit_path}.items()})
    (OUT / 'summary.json').write_text(json.dumps(atlas._json_safe(summary),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:summary[k] for k in ['intraday_draw_episodes','chart_bars_15m','intraday_missing_days','frozen_nonminute_equal']}, ensure_ascii=False), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download-missing', action='store_true')
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--fetch-task', type=Path)
    args = parser.parse_args()
    if args.fetch_task:
        task = json.loads(args.fetch_task.read_text())
        # TqSim is local; this historical market reader never invokes strategy/order methods.
        frame = fetch_history(task['symbol'],pd.Timestamp(task['start']),pd.Timestamp(task['end']))
        frame.to_csv(task['output'], index=False)
        print(json.dumps({'symbol':task['symbol'],'rows':len(frame),'status':'completed_history_read'}))
        return
    records, summary = load_base()
    selection = select_profit_top(records)
    if len(selection) != 60:
        raise RuntimeError('Expected exactly 30 long and 30 short profitable episodes')
    mapping = atlas._main_mapping()
    mapping = mapping[mapping.date.le(pd.Timestamp('2026-08-28'))]
    requests = request_dates(records,selection,mapping)
    print(f'Frozen 391 trades; selected {len(selection)}; {len(requests)} source contracts; {sum(map(len, requests.values()))} days incl. warmup', flush=True)
    bars, statuses = collect_cache(requests,mapping,args.download_missing)
    if args.publish:
        publish(records,summary,selection,bars,statuses)


if __name__ == '__main__':
    main()
