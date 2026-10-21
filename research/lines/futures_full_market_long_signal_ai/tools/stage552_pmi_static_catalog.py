"""Enumerate the frozen NBS 67-page metadata catalog; never fetch article bodies."""
import argparse, csv, hashlib, json, re, time, unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
import urllib.error, urllib.parse, urllib.request

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl): return None

def now(): return datetime.now(timezone.utc).isoformat()
def digest(data): return hashlib.sha256(data).hexdigest()
def binding(path):
    data = path.read_bytes()
    return {'path': str(path.resolve()), 'bytes': len(data), 'sha256': digest(data)}
def dump(path, value):
    with path.open('x') as f: json.dump(value, f, ensure_ascii=False, indent=2); f.write('\n')

class Catalog(HTMLParser):
    def __init__(self, base):
        super().__init__(); self.base = base; self.item = None; self.rows = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'li': self.item = {'text': [], 'anchors': [], 'desktop': []}
        if tag == 'a' and self.item is not None:
            url = urllib.parse.urljoin(self.base, attrs.get('href', ''))
            self.item['anchors'].append(url)
            if 'pc_1600' in attrs.get('class', '').split():
                self.item['desktop'].append((url, attrs.get('title', '')))
    def handle_data(self, data):
        if self.item is not None: self.item['text'].append(data)
    def handle_endtag(self, tag):
        if tag != 'li' or self.item is None: return
        for url, title in self.item['desktop']:
            if not re.search(r'/t\d+_\d+\.html$', urllib.parse.urlsplit(url).path): continue
            date = re.search(r'\b\d{4}-\d{2}-\d{2}\b', ''.join(self.item['text']))
            self.rows.append({'url': url, 'title': title, 'display_date': date.group() if date else None,
                              'same_li_anchor_count': self.item['anchors'].count(url)})
        self.item = None

def parse(body, url, index):
    p = Catalog(url); p.feed(body.decode('utf-8-sig', errors='strict'))
    unique = {}
    for row in p.rows:
        row['source_page_indices'] = [index]; unique.setdefault(row['url'], row)
    return list(unique.values())

def candidate(row):
    title = unicodedata.normalize('NFKC', row['title'])
    if not (re.search(r'采购经理(?:人)?指数|\bPMI\b', title, re.I)): return None
    if re.search(r'解读|统计师', title): return None
    if '非制造业' in title and '制造业' not in title.replace('非制造业', ''): return None
    match = re.search(r'(20\d{2})年\s*(1[0-2]|0?[1-9])月', title)
    month = f'{int(match[1]):04d}-{int(match[2]):02d}' if match else None
    return dict(row, report_month=month, month_basis='explicit_title' if month else 'unknown',
                availability_qualified=False, fields_qualified=False)

def main(protocol_path, output, check):
    protocol = json.loads(protocol_path.read_text()); spec = protocol['static']
    assert protocol['schema'] == 'stage551_pmi_catalog_frozen_metadata_batch_v1'
    assert spec['indices'] == list(range(67)) and spec['new_GET_indices'] == list(range(1, 66))
    assert (spec['concurrency'], spec['timeout_seconds'], spec['request_min_gap_seconds']) == (2, 12, 0.3)
    assert not spec['retry'] and not spec['redirect'] and spec['maximum_new_GET'] == 65
    output.mkdir(parents=True, exist_ok=False); started = time.monotonic(); cached = {}
    for key, expected in spec['cached'].items():
        data = Path(expected['path']).read_bytes()
        assert (len(data), digest(data)) == (expected['bytes'], expected['sha256'])
        cached[int(key)] = data
    if check:
        checks = []
        for index, count in [(0, 15), (66, 10)]:
            rows = parse(cached[index], spec['base_url'], index)
            assert len(rows) == count and all(r['same_li_anchor_count'] == 3 for r in rows)
            checks.append({'page': index, 'unique_articles': count, 'all_anchor_count': count * 3})
        result = {'source_ready': True, 'actual_started': False, 'source': binding(Path(__file__)),
                  'protocol': binding(protocol_path), 'cache_checks': checks, 'GET': 0, 'fit': 0, 'cash': 0, 'SQL': 0}
        dump(output / 'source_ready.json', result); print(json.dumps(result)); return
    dump(output / 'started.json', {'started_at': now(), 'protocol': binding(protocol_path), 'source': binding(Path(__file__))})
    def fetch(index):
        url = urllib.parse.urljoin(spec['base_url'], 'index.html' if index == 0 else f'index_{index}.html')
        record = {'index': index, 'url': url, 'fetched_at': now(), 'request_count': int(index not in cached),
                  'cached': index in cached, 'redirect_followed': False, 'retry': False}; body = b''; response = None
        try:
            if index in cached:
                body = cached[index]; record.update(http_status=200, cached_source=spec['cached'][str(index)], headers={})
            else:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept-Encoding': 'identity'})
                try: response = urllib.request.build_opener(NoRedirect()).open(req, timeout=12)
                except urllib.error.HTTPError as e: response = e
                record.update(http_status=response.status, response_url=response.geturl(), headers=dict(response.headers))
                body = response.read()
            rows = parse(body, url, index) if record['http_status'] == 200 else []
            record.update(article_count=len(rows), parsed=record['http_status'] == 200)
        except Exception as e:
            record.update(error_type=type(e).__name__, error=str(e), parsed=False); rows = []
        finally:
            if response is not None: response.close()
            if index not in cached: time.sleep(0.3)
        raw = output / f'page_{index:02d}.body'; raw.write_bytes(body); record['raw'] = binding(raw)
        dump(output / f'page_{index:02d}_receipt.json', record)
        print(json.dumps({'page': index, 'status': record.get('http_status'), 'articles': len(rows)}), flush=True)
        return record, rows
    with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(fetch, spec['indices']))
    unique = {}
    for _, rows in results:
        for row in rows:
            if row['url'] in unique: unique[row['url']]['source_page_indices'] += row['source_page_indices']
            else: unique[row['url']] = row
    articles = sorted(unique.values(), key=lambda r: (r['display_date'] or '', r['url']))
    candidates = [c for row in articles if (c := candidate(row)) is not None]
    dump(output / 'articles.json', articles); dump(output / 'pmi_candidates.json', candidates)
    with (output / 'articles.csv').open('x', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['url','title','display_date','same_li_anchor_count','source_page_indices'])
        writer.writeheader(); writer.writerows(articles)
    months = [f'{y:04d}-{m:02d}' for y in range(2010, 2027) for m in range(1, 13) if (y,m) <= (2026,9)]
    coverage = [{'report_month': month, 'candidate_urls': [c['url'] for c in candidates if c['report_month'] == month],
                 'state': 'title_discovered_only' if any(c['report_month'] == month for c in candidates) else 'not_discovered_in_this_catalog',
                 'fields_qualified': False, 'availability_qualified': False} for month in months]
    dump(output / 'coverage_201_months.json', {'months': coverage, 'unknown_title_month_candidates': [c for c in candidates if not c['report_month']]})
    terminal = {'status': 'completed', 'exit_code': 0, 'new_GET_attempts': sum(r['request_count'] for r,_ in results),
                'cached_pages': 2, 'pages': len(results), 'http200': sum(r.get('http_status') == 200 for r,_ in results),
                'parse_failures': sum(not r['parsed'] for r,_ in results), 'unique_articles': len(articles), 'pmi_candidates': len(candidates),
                'month_count': len(months), 'elapsed_seconds': time.monotonic()-started, 'fit': 0, 'cash': 0, 'SQL': 0,
                'source_qualified': False, 'full_history_qualified': False, 'goal_complete': False}
    dump(output / 'manifest.json', {'protocol': binding(protocol_path), 'source': binding(Path(__file__)), 'records': [r for r,_ in results], 'terminal': terminal})
    dump(output / 'terminal.json', terminal); print(json.dumps(terminal), flush=True)

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--protocol', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True); p.add_argument('--check-cache', action='store_true')
    a = p.parse_args(); main(a.protocol, a.output, a.check_cache)
