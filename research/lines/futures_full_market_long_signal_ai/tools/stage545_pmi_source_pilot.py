"""One frozen five-page public-source probe; no strategy inputs or financial run."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class TextAndTables(HTMLParser):
    def __init__(self):
        super().__init__(); self.skip = 0; self.text = []; self.tables = []
        self.table = None; self.row = None; self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'): self.skip += 1
        if tag in ('p', 'br', 'tr', 'h1', 'h2', 'div'): self.text.append('\n')
        if tag == 'table': self.table = []
        if tag == 'tr' and self.table is not None: self.row = []
        if tag in ('td', 'th') and self.row is not None: self.cell = []

    def handle_data(self, data):
        if not self.skip:
            self.text.append(data)
            if self.cell is not None: self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.skip: self.skip -= 1
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(re.sub(r'\s+', '', ''.join(self.cell))); self.cell = None
        if tag == 'tr' and self.row is not None:
            self.table.append(self.row); self.row = None
        if tag == 'table' and self.table is not None:
            self.tables.append(self.table); self.table = None


def binding(path):
    data = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def write_json(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def run(protocol_path, output):
    protocol = json.loads(protocol_path.read_text()); output.mkdir(parents=True, exist_ok=False)
    if protocol['schema'] != 'stage544_pmi_source_only_frozen_pilot_v1' or len(protocol['requests']) != 5:
        raise ValueError('exact five-page pilot required')
    start = time.monotonic(); records = []
    write_json(output/'started.json', dict(started_at=datetime.now(timezone.utc).isoformat(),
        protocol=binding(protocol_path), source=binding(Path(__file__)), retry=False, fit=0, cash=0))
    opener = urllib.request.build_opener(NoRedirect())
    for item in protocol['requests']:
        record = dict(item, fetched_at=datetime.now(timezone.utc).isoformat(), request_count=1,
                      automatic_retry=False, redirect_followed=False)
        response = None
        try:
            req = urllib.request.Request(item['url'], headers={
                'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
                'Accept':'text/html', 'Accept-Encoding':'identity'})
            try:
                response = opener.open(req, timeout=protocol['network']['timeout_seconds'])
            except urllib.error.HTTPError as error:
                response = error
            record['http_status'] = response.status
            record['response_url'] = response.geturl()
            record['headers'] = {k:response.headers.get(k) for k in
                ['Content-Type','Content-Length','Content-Encoding','Date','Last-Modified','ETag','Location']}
            body = response.read(protocol['network']['max_body_bytes']+1)
            path = output/(item['id']+'.html'); path.write_bytes(body); record['raw'] = binding(path)
            record['body_over_limit'] = len(body) > protocol['network']['max_body_bytes']
            record['transport_accepted'] = response.status == 200 and not record['body_over_limit']
            if record['transport_accepted']:
                hint = (record['headers']['Content-Type'] or '')+' '+body[:4096].decode('ascii', errors='ignore')
                match = re.search(r'charset\s*=\s*[\"\']?([a-zA-Z0-9_-]+)', hint, re.I)
                encoding = match.group(1).lower() if match else 'utf-8'
                if encoding in ('gbk','gb2312'): encoding = 'gb18030'
                record['decode_encoding'] = encoding
                parser = TextAndTables(); parser.feed(body.decode(encoding, errors='strict'))
                text = re.sub(r'[ \t\r\f\v]+',' ', ''.join(parser.text))
                text = re.sub(r'\n\s*\n+', '\n', text)
                tp = output/(item['id']+'.txt'); tp.write_text(text)
                record['text'] = binding(tp)
                tablep = output/(item['id']+'_tables.json'); write_json(tablep, parser.tables)
                record['tables'] = binding(tablep)
                record['parse_state'] = 'readable_text_and_cells_only_not_field_certification'
        except Exception as error:
            record['error_type'] = type(error).__name__; record['error'] = str(error)
            record.setdefault('transport_accepted', False)
        finally:
            if response is not None: response.close()
        records.append(record); write_json(output/(item['id']+'_receipt.json'),record)
        print(json.dumps({'id':item['id'],'status':record.get('http_status'),
            'transport':record['transport_accepted'],'error':record.get('error_type')},ensure_ascii=False),flush=True)
    terminal = dict(schema='stage545_pmi_source_pilot_terminal_v1', status='completed',
        exit_code=0, request_attempts=len(records), successful_http200=sum(r['transport_accepted'] for r in records),
        fit=0,cash=0,SQL=0,retries=0,elapsed_seconds=time.monotonic()-start,
        source_qualified=False, full_history_qualified=False, goal_complete=False)
    write_json(output/'manifest.json',dict(schema='stage545_pmi_source_pilot_v1',protocol=binding(protocol_path),
        source=binding(Path(__file__)),records=records,terminal=terminal))
    write_json(output/'terminal.json',terminal)
    return terminal


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--protocol',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    a = p.parse_args(); print(json.dumps(run(a.protocol,a.output),ensure_ascii=False),flush=True)
