"""Import immutable EIA archive issues; derive the frozen Stage059 causal event input.

Only the official date cells define releases. Raw HTML/CSV/header bodies stay excluded.
No estimator, prices, native SQL, account simulation, or product filtering is used.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import time as clock
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
LINE = Path(__file__).resolve().parents[1]
OUT = LINE / 'outputs/stage060_eia_report_import'
LABELS = ('Commercial (Excluding SPR)', 'Total Motor Gasoline', 'Distillate Fuel Oil')
ARCHIVE = 'https://www.eia.gov/petroleum/supply/weekly/archive/'
UNIT_SOURCE = 'https://www.eia.gov/petroleum/supply/weekly/pdf/table1.pdf'
SOURCE_END = '2026-10-16'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36'
MONTHS = {name: i for i, name in enumerate(('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'), 1)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def binding(path, role):
    p = Path(path).resolve()
    return dict(path=str(p), bytes=p.stat().st_size, sha256=sha(p), declared_role=role)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


class _Cells(HTMLParser):
    """Accept the archive's real orphan td groups as well as normal tr groups."""
    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = []
        self.cell = None

    def flush(self):
        if self.row:
            self.rows.append(self.row)
            self.row = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('tr', 'th'):
            self.flush()
        if tag == 'td':
            self.cell = dict(text='', hrefs=[], span=int(attrs.get('colspan', '1')))
        elif tag == 'a' and self.cell is not None and attrs.get('href'):
            self.cell['hrefs'].append(attrs['href'])

    def handle_data(self, value):
        if self.cell is not None:
            self.cell['text'] += value

    def handle_endtag(self, tag):
        if tag == 'td' and self.cell is not None:
            self.cell['text'] = ' '.join(self.cell['text'].split())
            self.row.extend([self.cell] * self.cell['span'])
            self.cell = None
            if len(self.row) >= 5:
                self.flush()
        elif tag == 'tr':
            self.flush()


def parse_archive_html(html: str) -> list[dict]:
    parser = _Cells()
    parser.feed(html)
    parser.flush()
    years = {}
    month = None
    reports = []
    for cells in parser.rows:
        if not cells:
            continue
        y = {i: int(c['text']) for i, c in enumerate(cells) if re.fullmatch(r'20\d{2}', c['text'])}
        if y:
            years = y
            month = None
            continue
        if cells[0]['text'] in MONTHS:
            month = MONTHS[cells[0]['text']]
        for i, cell in enumerate(cells):
            links = [h for h in cell['hrefs'] if '/petroleum/supply/weekly/archive/' in h and 'wpsr' in h]
            for href in links:
                if month is None or i not in years or i+1 >= len(cells):
                    raise ValueError('issue outside explicit archive year/month/data-ending columns')
                year = years[i]
                release_day = int(cell['text'])
                release = date(year, month, release_day)
                ending_text = cells[i+1]['text']
                bits = ending_text.split('/')
                if len(bits) == 2:
                    em, ed = map(int, bits)
                elif len(bits) == 1:
                    em, ed = month, int(bits[0])
                else:
                    raise ValueError(f'invalid official data-ending cell: {ending_text}')
                ending = date(year - int(em > month), em, ed)
                if ending >= release:
                    raise ValueError('official ending is not earlier than release')
                url = urljoin(ARCHIVE, href)
                issue = Path(urlparse(url).path).parent.name
                reports.append(dict(report_id='eia_wpsr_' + issue, issue_id=issue,
                                    issue_url=url, release_date=release.isoformat(),
                                    data_ending_expected=ending.isoformat(),
                                    release_date_evidence='official_archive_release_cell',
                                    table1_url=urljoin(url, 'csv/table1.csv')))
    if len({r['report_id'] for r in reports}) != len(reports):
        raise ValueError('duplicate issue identity in official calendar')
    reports.sort(key=lambda r: (r['release_date'], r['data_ending_expected'], r['report_id']))
    for ordinal, r in enumerate(reports):
        r['ordinal'] = ordinal
    return reports


def _table_date(text):
    return datetime.strptime(text.strip(), '%m/%d/%y').date().isoformat()


def parse_table1(content: bytes, report: dict) -> list[dict]:
    rows = list(csv.reader(io.StringIO(content.decode('utf-8-sig', errors='replace').replace('\x1a', ''))))
    if not rows or len(rows[0]) < 4 or rows[0][0] != 'STUB_1' or rows[0][3] != 'Difference':
        raise ValueError('Table1 stock header not recognized')
    ending = _table_date(rows[0][1])
    prior_ending = _table_date(rows[0][2])
    if ending != report['data_ending_expected']:
        raise ValueError(f"data-ending differs from official calendar: {ending} != {report['data_ending_expected']}")
    found = {}
    for rownum, row in enumerate(rows[1:], 2):
        if row and row[0] == 'STUB_1':
            break  # second table is thousand barrels/day and is never an inventory input.
        if not row or row[0] not in LABELS:
            continue
        if row[0] in found or len(row) < 4:
            raise ValueError('duplicate or short stock component')
        try:
            current, prior, delta = [Decimal(x.replace(',', '').strip()) for x in row[1:4]]
        except InvalidOperation as exc:
            raise ValueError('missing/non-numeric stock component') from exc
        if not all(x.is_finite() for x in (current, prior, delta)) or current <= 0 or prior <= 0:
            raise ValueError('nonfinite or nonpositive stock level')
        residual = current - prior - delta
        if residual != 0:
            raise ValueError(f'current-prior does not equal reported Difference: {residual}')
        found[row[0]] = dict(report_id=report['report_id'], series_label=row[0],
                            data_ending=ending, prior_data_ending=prior_ending,
                            native_unit='million_barrels', normalized_unit='thousand_barrels',
                            unit_conversion_factor=1000, unit_evidence_url=UNIT_SOURCE,
                            current=float(current*1000), prior_inline=float(prior*1000), delta=float(delta*1000),
                            raw_current=str(current), raw_prior_inline=str(prior), raw_delta=str(delta),
                            arithmetic_residual_thousand_barrels=float(residual*1000),
                            source_row_number=rownum, value_status='known',
                            source_sha256=hashlib.sha256(content).hexdigest(),
                            source_url=report.get('table1_url', urljoin(report['issue_url'], 'csv/table1.csv')))
    if set(found) != set(LABELS):
        raise ValueError('three stock components not all present before flow header')
    return [found[k] for k in LABELS]


def make_report_signals(calendar_reports, normalized_values, china_dates, source_end=SOURCE_END) -> pd.DataFrame:
    reports = sorted([dict(x) for x in calendar_reports], key=lambda r: (r['release_date'], r['data_ending_expected'], r['report_id']))
    values = normalized_values.to_dict('records') if isinstance(normalized_values, pd.DataFrame) else normalized_values
    stocks = {(r['report_id'], r['series_label']): r for r in values}
    dates = sorted({pd.Timestamp(d).date().isoformat() for d in china_dates if pd.Timestamp(d).date().isoformat() <= source_end})
    closes = [datetime.combine(date.fromisoformat(d), time(16), ZoneInfo('Asia/Shanghai')) for d in dates]
    scalars = []
    result = []
    for ordinal, r in enumerate(reports):
        rid = r['report_id']
        required = [(rid, k) for k in LABELS]
        missing = any(key not in stocks or not (stocks[key].get('current') is not None and np.isfinite(stocks[key]['current'])) or not (stocks[key].get('delta') is not None and np.isfinite(stocks[key]['delta'])) for key in required)
        scalar = np.nan
        reason = 'current_stock_missing' if missing else 'warmup_less_than_52_calendar_reports' if ordinal < 52 else ''
        if not reason:
            lag_id, prev_id = reports[ordinal-52]['report_id'], reports[ordinal-1]['report_id']
            components = []
            for k in LABELS:
                lag = stocks.get((lag_id, k), {}).get('delta', np.nan)
                prior = stocks.get((prev_id, k), {}).get('current', np.nan)
                if lag is None or prior is None or not np.isfinite(lag) or not np.isfinite(prior) or prior <= 0:
                    reason = 'lag52_delta_or_previous_archived_stock_missing'
                    break
                components.append(-(stocks[(rid, k)]['delta'] - lag) / prior)
            if not reason:
                scalar = float(np.mean(components))
        candidates = [j for j in range(max(0, ordinal-52), ordinal) if np.isfinite(scalars[j])]
        shared_missing = not np.isfinite(scalar) or not candidates
        sampled = None
        sham = 0.
        if not shared_missing:
            code = int(hashlib.sha256(('stage057_past_sham_v1|' + rid).encode()).hexdigest(), 16)
            sampled = candidates[code % len(candidates)]
            sham = scalars[sampled]
        scalars.append(scalar)
        available = datetime.combine(date.fromisoformat(r['release_date']), time(23,59,59), ZoneInfo('America/New_York'))
        ui = next((i for i, close in enumerate(closes) if close > available), None)
        u = dates[ui] if ui is not None else None
        d = dates[ui+1] if ui is not None and ui+1 < len(dates) else None
        result.append(dict(**{k:v for k,v in r.items() if k != 'ordinal'}, ordinal=ordinal,
                           available_at_utc=available.astimezone(timezone.utc).isoformat(),
                           available_at_china=available.astimezone(ZoneInfo('Asia/Shanghai')).isoformat(),
                           availability_precision='date_only_conservative_end_of_day',
                           s=scalar, stock_missing=int(missing), s_missing_reason=reason,
                           inventory_s=0. if shared_missing else scalar,
                           past_sham_s=sham, past_sham_report_id=reports[sampled]['report_id'] if sampled is not None else None,
                           past_sham_ordinal=sampled, past_sham_candidates=len(candidates),
                           external_missing=int(shared_missing), u_date=u, native_D_date=d,
                           execution_state='not_available_by_source_end' if u is None else 'pending_after_source_end' if d is None else 'mapped_next_native_D',
                           superseded_before_first_decision=False))
    frame = pd.DataFrame(result)
    if not frame.empty:
        for _, group in frame.dropna(subset=['u_date']).groupby('u_date', sort=True):
            order = group.sort_values(['data_ending_expected','report_id']).index
            frame.loc[order[:-1], 'superseded_before_first_decision'] = True
    return frame


def make_event_map(report_features):
    events = report_features.loc[report_features.u_date.notna() & ~report_features.superseded_before_first_decision].copy()
    events = events.sort_values('u_date').reset_index(drop=True)
    if events.u_date.duplicated().any():
        raise ValueError('event map has more than one report per decision u')
    return events


def _fetch_report(r, rawdir, cache):
    start = clock.monotonic()
    rid = r['report_id']
    body = rawdir / (rid + '.csv')
    headers = rawdir / (rid + '_headers.txt')
    rec = dict(report_id=rid, url=r['table1_url'], attempted_at=datetime.now(timezone.utc).isoformat(),
               automatic_retries=0, timeout_seconds=20, request_headers={'User-Agent': UA})
    if rid in cache:
        old = cache[rid]
        if sha(old['raw_path']) != old['sha256']:
            raise ValueError('058 cache binding changed')
        shutil.copyfile(old['raw_path'], body)
        rec.update(status=200, transport='accepted_stage058_cache', final_url=old['final_url'],
                   content_type=old['content_type'], original_source_binding=old)
    else:
        proc = subprocess.run(['curl','--silent','--show-error','--location','--max-time','20','--connect-timeout','10',
                               '--user-agent', UA, '--dump-header', str(headers), '--output', str(body),
                               '--write-out','%{http_code} %{url_effective} %{time_total}', r['table1_url']],
                              capture_output=True, text=True, timeout=23)
        bits = proc.stdout.split()
        status = int(bits[0]) if bits and bits[0].isdigit() else 0
        header_text = headers.read_text(errors='replace') if headers.exists() else ''
        ctypes = re.findall(r'(?im)^Content-Type:\s*([^\r\n]+)', header_text)
        rec.update(status=status, transport='curl', curl_returncode=proc.returncode, stderr=proc.stderr,
                   final_url=bits[1] if len(bits)>1 else None, content_type=ctypes[-1] if ctypes else None,
                   response_headers=header_text)
    rec['elapsed_seconds'] = clock.monotonic()-start
    if body.exists():
        rec.update(raw_path=str(body.resolve()), bytes=body.stat().st_size, sha256=sha(body))
    if rec['status'] != 200 or (rec.get('curl_returncode',0) != 0):
        rec.update(source_status='unknown_download_failed', parse_status='not_parsed')
        return rec, []
    try:
        values = parse_table1(body.read_bytes(), r)
        rec.update(source_status='known', parse_status='three_stock_components_validated')
    except (ValueError, OverflowError) as exc:
        rec.update(source_status='unknown_parse_failed', parse_status='rejected', parse_error=str(exc))
        values = []
    return rec, values


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--archive-file', type=Path, required=True)
    ap.add_argument('--archive-receipt', type=Path, required=True)
    ap.add_argument('--china-calendar', type=Path, required=True)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    terminal = OUT/'actual_terminal.json'
    if terminal.exists():
        raise RuntimeError('Stage060 actual run already attempted; do not silently restart')
    start = clock.monotonic()
    state = dict(schema='stage060_eia_import_terminal_v1', status='running', started_at=datetime.now(timezone.utc).isoformat(),
                 process_id=__import__('os').getpid(), source_end=SOURCE_END, model_fits=0,cash_accounts=0,sql_queries=0,
                 downloads_retried=0, source_actual_startups=1, goal_complete=False)
    write_json(terminal,state)
    try:
        protocol_path=LINE/'outputs/stage059_eia_full_market_protocol/protocol.json'
        if sha(protocol_path) != 'ff1ecad21420681e8e1e8645be3da51172d35d4e24ef506ee3f88d2ed5e20158':
            raise ValueError('frozen protocol binding changed')
        indexrec=json.loads(args.archive_receipt.read_text())
        if indexrec['status'] != 200 or sha(args.archive_file) != indexrec['sha256']:
            raise ValueError('archive acquisition binding is invalid')
        reports=parse_archive_html(args.archive_file.read_text())
        if not reports or len(reports)>900:
            raise ValueError('official calendar count outside bounded source contract')
        pd.DataFrame(reports).to_csv(OUT/'calendar.csv',index=False)
        npydates=np.load(args.china_calendar,allow_pickle=False)
        china_dates=[datetime.strptime(str(int(d)), '%Y%m%d').date().isoformat() for d in npydates]
        cachepath=LINE/'outputs/stage058_eia_small_source_probe/csv_probe_receipt.json'
        cache_receipt=json.loads(cachepath.read_text())
        cache={'eia_wpsr_'+Path(urlparse(v['url']).path).parent.parent.name:v for v in cache_receipt['requests'] if v['status']==200}
        records=[]; stocks=[]
        with (OUT/'source_progress.jsonl').open('w') as progress:
            with ThreadPoolExecutor(max_workers=4) as pool:
                future_map={pool.submit(_fetch_report,r,OUT/'excluded_raw_sources',cache):r for r in reports}
                for future in as_completed(future_map):
                    r=future_map[future]
                    try:
                        rec,vals=future.result()
                    except Exception as exc:
                        rec=dict(report_id=r['report_id'],url=r['table1_url'],source_status='unknown_transport_exception',parse_status='not_parsed',error=repr(exc),automatic_retries=0)
                        vals=[]
                    records.append(rec); stocks.extend(vals)
                    progress.write(json.dumps(rec,ensure_ascii=False,allow_nan=False)+'\n'); progress.flush()
                    if len(records)%25==0 or len(records)==len(reports):
                        print(json.dumps(dict(completed=len(records),total=len(reports),known=sum(v['source_status']=='known' for v in records),elapsed_seconds=round(clock.monotonic()-start,2))),flush=True)
        records.sort(key=lambda r:r['report_id'])
        write_json(OUT/'source_bindings.json',dict(schema='stage060_eia_source_bindings_v1',archive=indexrec,reports=records))
        known={(v['report_id'],v['series_label']):v for v in stocks}
        long=[]
        for r in reports:
            for k in LABELS:
                long.append(known.get((r['report_id'],k),dict(report_id=r['report_id'],series_label=k,value_status='unknown',data_ending=r['data_ending_expected'],current=None,prior_inline=None,delta=None,native_unit='million_barrels',normalized_unit='thousand_barrels',source_url=r['table1_url'])))
        pd.DataFrame(long).to_csv(OUT/'normalized_stocks.csv',index=False)
        features=make_report_signals(reports,long,china_dates)
        events=make_event_map(features)
        features.to_csv(OUT/'report_features.csv',index=False)
        events.to_csv(OUT/'event_map.csv',index=False)
        yearcounts=features.assign(year=features.release_date.str[:4]).groupby('year').agg(reports=('report_id','size'),stock_missing=('stock_missing','sum'),external_missing=('external_missing','sum')).reset_index()
        yearcounts.to_csv(OUT/'coverage_by_year.csv',index=False)
        coverage=dict(schema='stage060_eia_coverage_v1',calendar_reports=len(reports),calendar_first=reports[0]['release_date'],calendar_last=reports[-1]['release_date'],
                      http200=sum(r.get('status')==200 for r in records),cached_reports=sum(r.get('transport')=='accepted_stage058_cache' for r in records),
                      network_report_attempts=sum(r.get('transport')!='accepted_stage058_cache' for r in records),
                      known_reports=sum(r['source_status']=='known' for r in records),unknown_reports=sum(r['source_status']!='known' for r in records),normalized_stock_rows=len(long),
                      scalar_known=int(features.s.notna().sum()),shared_information_known=int(features.external_missing.eq(0).sum()),
                      decision_events=len(events),decision_events_2020plus=int(events.u_date.ge('2020-01-01').sum()),
                      decision_events_shared_known_2020plus=int((events.u_date.ge('2020-01-01') & events.external_missing.eq(0)).sum()),
                      superseded_reports=int(features.superseded_before_first_decision.sum()),pending_after_source_end=int(events.execution_state.eq('pending_after_source_end').sum()),
                      source_failures=[{k:v for k,v in rec.items() if k in ('report_id','status','source_status','parse_error','error','stderr')} for rec in records if rec['source_status']!='known'],
                      missing_ordinals_retained=True,all_family_eligibility_unchanged=True,raw_sources_in_git=False,
                      limitations=['official archive begins2011-08-03; no invented2010 releases','archived source is not independently proven first-vintage; no modern revised series fill','date-only conservative availability; no historical10:30 assumption','only source import; no new alpha or financial qualification'])
        write_json(OUT/'coverage.json',coverage)
        state.update(status='completed',finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=clock.monotonic()-start,
                     calendar_reports=len(reports),known_reports=coverage['known_reports'],unknown_reports=coverage['unknown_reports'],
                     report_network_attempts=coverage['network_report_attempts'],cached_reports=coverage['cached_reports'])
        write_json(terminal,state)
        roles={'calendar':('calendar.csv','normalized_official_release_calendar'), 'normalized_stocks':('normalized_stocks.csv','normalized_reproducibility_input_three_inventory_components'),
               'report_features':('report_features.csv','causal_full_calendar_scalar_and_past_sham'), 'event_map':('event_map.csv','unique_decision_date_causal_external_input_all_families'),
               'coverage':('coverage.json','source_coverage_and_unknown_receipt'), 'coverage_by_year':('coverage_by_year.csv','source_annual_coverage'),
               'source_bindings':('source_bindings.json','public_source_hash_header_and_status_bindings'), 'source_progress':('source_progress.jsonl','complete_actual_source_progress'),
               'actual_terminal':('actual_terminal.json','actual_execution_terminal'), 'tests_red':('tests_red.log','new_behavior_red_evidence'), 'tests_green':('tests_green.log','new_behavior_green_evidence')}
        manifest=dict(schema='stage060_eia_import_manifest_v1',status='completed',artifacts={role:binding(OUT/name,declared) for role,(name,declared) in roles.items()},
                      input_bindings=dict(protocol=binding(protocol_path,'frozen_protocol'),archive_acquisition=binding(args.archive_receipt,'official_index_acquisition_receipt'),
                                          accepted_china_calendar=binding(args.china_calendar,'accepted_source_trading_calendar_no_prices'),stage058_cache_receipt=binding(cachepath,'accepted_two_csv_cache_bindings'),
                                          implementation=binding(__file__,'implementation_contract'),tests=binding(Path(__file__).with_name('test_stage060_eia_report_import.py'),'new_behavior_contract_tests')),
                      raw_source_handling='excluded_raw_sources only; never register raw HTML/CSV/PDF', source_end=SOURCE_END,
                      all_families_same_event_eligibility=True,fit_or_cash_authorized=False,goal_complete=False)
        write_json(OUT/'manifest.json',manifest)
        print(json.dumps(dict(status='completed',coverage=coverage),ensure_ascii=False),flush=True)
    except Exception as exc:
        state.update(status='failed',error=repr(exc),finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=clock.monotonic()-start)
        write_json(terminal,state)
        raise


if __name__=='__main__':
    main()
