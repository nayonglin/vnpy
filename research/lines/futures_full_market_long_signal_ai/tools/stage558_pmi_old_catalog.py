"""Frozen year/page metadata requests only; no article or financial access."""
import argparse, concurrent.futures, hashlib, html, json, re, threading, time, unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError

BASE = Path(__file__).resolve().parents[1]
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')

def binding(path):
    body = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(body), sha256=hashlib.sha256(body).hexdigest())

def plain(text): return unicodedata.normalize('NFKC', html.unescape(re.sub(r'<[^>]*>', '', str(text or '')))).strip()

def parse(payload, source):
    if not isinstance(payload, dict) or payload.get('ok') is not True or payload.get('code') not in (None, 200):
        raise ValueError('API not ok or non-null failure code')
    docs = payload.get('resultDocs')
    if not isinstance(docs, list): raise ValueError('resultDocs not list')
    rows, ids = [], []
    for i, doc in enumerate(docs):
        if not isinstance(doc, dict) or not isinstance(doc.get('data'), dict) or not doc.get('id'):
            raise ValueError('resultDocs schema/id missing')
        data = doc['data']; title = plain(data.get('titleO') or data.get('title')); url = data.get('url')
        if not isinstance(url, str): raise ValueError('result URL missing')
        part = urlsplit(url); reason = 'official_original_report_candidate'
        if part.scheme not in ('http', 'https') or part.hostname != 'www.stats.gov.cn' or part.username or part.port:
            reason = 'non_observed_NBS_domain_or_scheme'
        elif not re.search(r'采购经理(?:人)?指数|\bPMI\b', title, re.I): reason = 'no_PMI_title'
        elif re.search(r'解读|统计师|图解|释义|访谈|答记者问|专家|微信|微博', title): reason = 'commentary_or_social_title'
        elif '非制造业' in title and not re.search(r'(?<!非)制造业', title): reason = 'nonmanufacturing_only'
        match = re.search(r'([12]\d{3})年\s*(1[0-2]|0?[1-9])月份?', title)
        month = f'{match[1]}-{int(match[2]):02d}' if match else None
        rows.append(dict(source=source, result_index=i, id=doc['id'], url=url, title=title,
                         docDate=data.get('docDate'), report_month=month, month_basis='explicit_title' if month else 'unknown',
                         candidate=reason == 'official_original_report_candidate', candidate_reason=reason))
        ids.append(str(doc['id']))
    return rows, tuple(sorted(set(ids)))

class Batch:
    def __init__(self, protocol, output):
        self.p, self.out = protocol, output; self.lock = threading.Lock(); self.next_start = 0.0
    def pace(self):
        with self.lock:
            time.sleep(max(0, self.next_start-time.monotonic()))
            self.next_start = time.monotonic()+self.p['minimum_gap_seconds']
    def year(self, year):
        out = self.out/str(year); out.mkdir(); rows, receipts, seen = [], [], set(); stop = 'page10_cap'
        for page in self.p['pages']:
            params = dict(self.p['base_params'], page=str(page), startDateStr=f'{year}-01-01',
                          endDateStr=f'{year}-11-14' if year == 2021 else f'{year}-12-31')
            rec = dict(year=year, page=page, params=params, url=self.p['url'], retry=False, redirect=False)
            raw = b''; response = None; self.pace(); start = time.monotonic()
            rec['started_utc'] = datetime.now(timezone.utc).isoformat()
            try:
                req = Request(self.p['url'], data=urlencode(params).encode(), headers={'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)', 'Accept-Encoding':'identity'})
                try: response = build_opener(NoRedirect()).open(req, timeout=self.p['timeout_seconds'])
                except HTTPError as error: response = error
                rec.update(http_status=response.status, response_url=response.geturl(), headers=dict(response.headers.items()))
                raw = response.read()
                if response.status != 200: raise ValueError('HTTP status not 200')
                page_rows, ids = parse(json.loads(raw.decode('utf-8')), dict(year=year, page=page))
                rec.update(result_docs=len(page_rows), response_id_set=list(ids))
                rows.extend(page_rows)
                if not page_rows: stop = 'empty_resultDocs'
                elif ids in seen: stop = 'identical_prior_response_ID_set_pagination_unverified'
                else: seen.add(ids); stop = 'page10_cap' if page == 10 else 'continue'
            except Exception as error:
                rec.update(error_type=type(error).__name__, error=str(error)); stop = 'HTTP_API_schema_or_transport_error_partial'
            finally:
                if response is not None: response.close()
            body_path = out/f'page_{page:02d}.body'; body_path.write_bytes(raw)
            rec.update(raw=binding(body_path), elapsed_seconds=time.monotonic()-start, stop_reason=stop)
            save(out/f'page_{page:02d}_receipt.json', rec); receipts.append(rec)
            print(json.dumps(dict(year=year, page=page, status=rec.get('http_status'), docs=rec.get('result_docs'), stop=stop)), flush=True)
            if stop != 'continue': break
        save(out/'year_summary.json', dict(year=year, stop_reason=stop, requests=len(receipts), metadata_rows=len(rows)))
        return dict(year=year, stop_reason=stop, receipts=receipts, metadata_rows=rows)

def run(protocol_path, output):
    p = json.loads(protocol_path.read_text())
    if p['schema'] != 'stage557_old_pmi_metadata_year_pagination_v1' or p['maximum_requests'] != 120:
        raise ValueError('wrong frozen protocol')
    if p['publication_years'] != list(range(2010,2022)) or p['pages'] != list(range(1,11)) or p['concurrency'] != 2:
        raise ValueError('unexpected year/page/concurrency')
    output.mkdir(parents=True, exist_ok=False); started = time.monotonic()
    save(output/'started.json', dict(protocol=binding(protocol_path), source=binding(Path(__file__)), started_utc=datetime.now(timezone.utc).isoformat(), fit=0, cash=0, SQL=0))
    batch = Batch(p, output)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(batch.year, p['publication_years']))
    rows = [r for year in results for r in year['metadata_rows']]
    save(output/'all_metadata.json', rows)
    old = [r for r in rows if r['candidate']]; static_path = BASE/'outputs/stage552_pmi_static_catalog/actual_run1/pmi_candidates.json'
    static = json.loads(static_path.read_text()); candidates = {}
    for row in [*old, *[dict(r, source={'stage':552}) for r in static]]:
        item = candidates.setdefault(row['url'], dict(url=row['url'], titles=[], report_months=[], sources=[], body_fetched=False))
        if row['title'] not in item['titles']: item['titles'].append(row['title'])
        if row.get('report_month') and row['report_month'] not in item['report_months']: item['report_months'].append(row['report_month'])
        item['sources'].append(row.get('source'))
    save(output/'old_candidates_with_duplicates.json', old); save(output/'candidate_urls.json', list(candidates.values()))
    grid = []
    for year in range(2010,2027):
        for month in range(1,13):
            key = f'{year}-{month:02d}'
            if key > '2026-09': break
            urls = [r['url'] for r in candidates.values() if key in r['report_months']]
            grid.append(dict(report_month=key, candidate_urls=urls, url_candidate_found=bool(urls), fields_qualified=False, availability_qualified=False))
    save(output/'coverage_201_months.json', grid)
    terminal = dict(status='completed', elapsed_seconds=time.monotonic()-started, requests=sum(len(y['receipts']) for y in results), http200=sum(r.get('http_status') == 200 for y in results for r in y['receipts']), metadata_rows=len(rows), old_candidate_rows=len(old), combined_unique_urls=len(candidates), explicit_month_coverage=sum(r['url_candidate_found'] for r in grid), year_stop_reasons={str(y['year']):y['stop_reason'] for y in results}, fit=0, cash=0, SQL=0, article_GET=0, goal_complete=False, source_qualified=False)
    save(output/'manifest.json', dict(protocol=binding(protocol_path), source=binding(Path(__file__)), static_candidates=binding(static_path), terminal=terminal)); save(output/'terminal.json', terminal)
    return terminal

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--protocol', type=Path); parser.add_argument('--output', type=Path); parser.add_argument('--actual', action='store_true'); parser.add_argument('--fixture', action='store_true'); args = parser.parse_args()
    if args.fixture:
        cases = []
        for stage in ['stage553_pmi_public_search_probe','stage556_pmi_corrected_old_search']:
            rows, ids = parse(json.loads((BASE/f'outputs/{stage}/actual_run1/search.body').read_text()), {'fixture':stage})
            cases.append(dict(stage=stage, docs=len(rows), unique_ids=len(ids), candidates=sum(r['candidate'] for r in rows), months=sorted({r['report_month'] for r in rows if r['candidate'] and r['report_month']})))
        assert cases[0]['docs'] == 20 and cases[0]['candidates'] == 1
        assert cases[1]['docs'] == 16 and {'2021-09','2021-10'} <= set(cases[1]['months'])
        print(json.dumps(dict(status='fixture_pass', cases=cases, network=0, fit=0, cash=0), ensure_ascii=False))
    elif args.actual and args.protocol and args.output: print(json.dumps(run(args.protocol, args.output), ensure_ascii=False))
    else: parser.error('use --fixture, or explicit --actual --protocol --output')
