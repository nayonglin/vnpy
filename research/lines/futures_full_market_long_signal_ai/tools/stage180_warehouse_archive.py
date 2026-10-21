"""One fixed SHFE warehouse source archive. No normalization or financial imports.

Importing this module performs no I/O. Only the CLI loads the frozen protocol;
run_archive permits an injected transport/clock for bounded synthetic fixtures.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import time


PROTOCOL_SHA256 = 'a67cf844699c8b2d1b34cc3cd66ac88eaae0c6bedd5621796d886f129cfbb0c5'
PLAN_SHA256 = '06129933ce2c892d6855ae7ba499a63b36b1b4bc4503c0163e4ee9cbc83d69b8'
JSON_URL = 'https://www.shfe.com.cn/data/tradedata/future/dailydata/{YYYYMMDD}dailystock.dat'
HTML_URL = 'https://www.shfe.com.cn/data/tradedata/future/stockdata/dailystock_{YYYYMMDD}/ZH/all.html'
ZERO_BUDGETS = dict(new_fit=0, new_cash=0, SQL=0, new_labels=0, new_prices=0,
                    financial_authorization=False, first_publication_PIT_proved=False)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(value):
    return hashlib.sha256(value).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def binding(path, body=None):
    path = Path(path).resolve()
    body = path.read_bytes() if body is None else body
    return dict(path=str(path), bytes=len(body), sha256=sha(body))


def build_actions(plan):
    """Reproduce Stage178 canonical five-field action identities, without raw I/O."""
    domain = plan['frozen_candidate_domain']
    dates = domain['dates']
    reuse = plan['reuse_by_date']
    if (not dates or dates != sorted(set(dates)) or
            sha(encoded(dates)) != domain['dates_sha256'] or len(dates) != domain['count']):
        raise ValueError('frozen_date_domain_mismatch')
    for date in dates:
        if not isinstance(date, str) or not re.fullmatch(r'[0-9]{8}', date):
            raise ValueError('invalid_frozen_date')
        datetime.strptime(date, '%Y%m%d')
    if (domain['format_cutpoint'] != '20251118' or
            domain['before_cutpoint_template'] != JSON_URL or
            domain['at_or_after_cutpoint_template'] != HTML_URL or
            not set(reuse).issubset(dates)):
        raise ValueError('fixed_route_or_reuse_domain_mismatch')
    records = []
    for i, date in enumerate(dates):
        fmt = 'json' if date < '20251118' else 'html'
        url = (JSON_URL if fmt == 'json' else HTML_URL).format(YYYYMMDD=date)
        rec = dict(sequence_index=i, date=date, format=fmt, url=url,
                   action='reuse' if date in reuse else 'new_get')
        if date in reuse and any(reuse[date][k] != rec[k] for k in ('date', 'format', 'url')):
            raise ValueError('reuse_source_identity_mismatch')
        records.append(rec)
    new = [r for r in records if r['action'] == 'new_get']
    if (sha(encoded(records)) != domain['full_action_records_sha256'] or
            sha(encoded(new)) != domain['new_get_records_sha256'] or
            len(new) != domain['new_get_count'] or len(reuse) != domain['reuse_count'] or
            sorted(reuse) != domain['reuse_dates']):
        raise ValueError('frozen_action_domain_mismatch')
    for key, observed in [('by_year', Counter(d[:4] for d in dates)),
                          ('by_format', Counter(r['format'] for r in records)),
                          ('new_get_by_format', Counter(r['format'] for r in new))]:
        if key in domain and dict(observed) != domain[key]:
            raise ValueError('frozen_' + key + '_mismatch')
    return records


class IntroParser(HTMLParser):
    """Read intro dates and minimal report headers; never execute page scripts."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.intro = []
        self.tables = 0
        self.intro_present = False
        self.table_headers = []
        self.table_stack = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        intro_element = 'content_intro' in attrs.get('class', '').split()
        self.intro_present = self.intro_present or intro_element
        inside = (self.stack[-1][1] if self.stack else False) or intro_element
        suppressed = tag in ('script', 'style') or (self.stack[-1][2] if self.stack else False)
        if tag == 'table':
            self.tables += 1
            self.table_headers.append(dict(intro=inside, rows=[]))
            self.table_stack.append(len(self.table_headers)-1)
        elif tag == 'tr' and self.table_stack:
            self.row = []
        elif tag in ('td', 'th') and self.row is not None:
            self.cell = []
        if tag not in ('br', 'hr', 'img', 'meta', 'link', 'input', 'source', 'wbr'):
            self.stack.append((tag, inside, suppressed))
        if inside and not suppressed:
            self.intro.append(' ')

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None and self.row is not None:
            self.row.append(re.sub(r'\s+', '', ''.join(self.cell)))
            self.cell = None
        elif tag == 'tr' and self.row is not None and self.table_stack:
            self.table_headers[self.table_stack[-1]]['rows'].append(self.row)
            self.row = None
        elif tag == 'table' and self.table_stack:
            self.table_stack.pop()
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self.stack and self.stack[-1][1] and not self.stack[-1][2]:
            self.intro.append(data)
        if self.cell is not None and self.stack and not self.stack[-1][2]:
            self.cell.append(data)


def canonical_date(value):
    text = str(value).strip()
    if not text:
        return None
    match = re.fullmatch(r'([0-9]{4})(?:-?)([0-9]{2})(?:-?)([0-9]{2})', text)
    if not match:
        return None
    date = ''.join(match.groups())
    try:
        datetime.strptime(date, '%Y%m%d')
    except ValueError:
        return None
    return date


def inspect_body(body, fmt, request_date):
    result = dict(expected_envelope=False, report_date_fields={}, report_dates={},
                  date_state='absent', date_evidence_scope='JSON top fields only' if fmt == 'json' else 'visible content_intro only')
    try:
        text = body.decode('utf-8-sig')
        if fmt == 'json':
            obj = json.loads(text)
            result['expected_envelope'] = isinstance(obj, dict) and isinstance(obj.get('o_cursor'), list)
            if not isinstance(obj, dict):
                return result
            result['report_date_fields'] = {k: obj[k] for k in ('report_date', 'o_tradingday') if k in obj}
            for key, value in result['report_date_fields'].items():
                if value is not None and str(value).strip():
                    result['report_dates'][key] = canonical_date(value)
        else:
            parser = IntroParser()
            parser.feed(text)
            parser.close()
            data_headers = sum(any(set(row) & {'期货', '本日数量'} and
                                   set(row) & {'仓库', '厂库', '交割仓库', '地区/仓库', '地区/厂库', '厂库/地区', '仓库/地区'}
                                   for row in table['rows'])
                               for table in parser.table_headers if not table['intro'])
            result.update(expected_envelope=parser.intro_present and data_headers > 0,
                          table_count=parser.tables, intro_present=parser.intro_present,
                          report_header_table_count=data_headers)
            intro = ''.join(parser.intro)
            result['report_date_fields'] = {'intro_text': intro}
            matches = re.findall(r'(?<![0-9])([0-9]{4})[-年]([0-9]{2})[-月]([0-9]{2})(?:日)?(?![0-9])|(?<![0-9])([0-9]{8})(?![0-9])', intro)
            dates = sorted(set(canonical_date(''.join(m[:3]) if m[0] else m[3]) for m in matches), key=lambda v: v or '')
            if matches:
                result['report_dates']['intro'] = dates
        found = []
        for value in result['report_dates'].values():
            found.extend(value if isinstance(value, list) else [value])
        result['date_state'] = ('unparseable' if None in found else
                                'conflict' if any(d != request_date for d in found) else
                                'matched' if found else 'absent')
    except (ValueError, UnicodeError, TypeError) as error:
        result['envelope_error'] = type(error).__name__ + ': ' + str(error)
    return result


class ArchiveStop(Exception):
    pass


def run_archive(plan, budget, output, *, get=None, monotonic=time.monotonic,
                sleep=time.sleep, inputs=None):
    """One fresh run; first source/budget failure ends all new requests, never retry."""
    actions = build_actions(plan)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    session = None
    if get is None:
        import requests
        session = requests.Session()
        session.trust_env = False  # No environment proxy/netrc credentials.
        get = session.get
    inputs = inputs or {}
    began = monotonic()
    records = [dict(r, state='not_attempted_pending', attempt=0) for r in actions]
    record_sizes = [len(encoded(r)) for r in records]
    final_date_size = sum(record_sizes) + max(0, len(records)-1) + 3
    metadata_sizes = {}
    metadata_used = 0
    total_bytes = 0
    attempted = 0
    previous_get_start = None
    stop_reason = None
    timeout_note = ('35s/report and 4h/batch are monotonic checks before/after blocking calls; '
                    'requests connect/read timeout is finite but is not a system-level wall-clock interrupt; observed overruns are recorded')

    def update(i, rec):
        nonlocal final_date_size
        size = len(encoded(rec))
        final_date_size += size - record_sizes[i]
        record_sizes[i] = size
        records[i] = rec

    def metadata(name, value, *, append=False, final=False):
        nonlocal metadata_used
        data = encoded(value) + b'\n'
        old = metadata_sizes.get(name, 0)
        new = old + len(data) if append else len(data)
        projected = metadata_used - old + new
        # Reserve the exact current final date-list size plus small terminal/manifest space.
        reserve = 0 if final else max(0, final_date_size - metadata_sizes.get('date_manifest.json', 0)) + 32768
        if projected + reserve > budget['metadata_archive_cap_bytes']:
            raise ArchiveStop('metadata_archive_cap')
        path = output / name
        with path.open('ab' if append else 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        metadata_used = projected
        metadata_sizes[name] = new

    def journal(event):
        metadata('journal.jsonl', dict(event, archived_at=utc_now()), append=True)

    def guard(report_start=None):
        now = monotonic()
        if now - began >= budget['hard_batch_elapsed_seconds']:
            raise ArchiveStop('batch_elapsed_cap')
        if report_start is not None and now - report_start >= budget['hard_per_report_elapsed_seconds']:
            raise ArchiveStop('report_elapsed_cap')

    def persist(i, rec):
        update(i, rec)
        response_name = rec['date'] + '_response.json'
        response_bytes = encoded(rec) + b'\n'
        metadata(response_name, rec)
        rec = dict(rec, response=binding(output/response_name, response_bytes))
        update(i, rec)
        journal(dict(event='date_terminal', record=rec))

    metadata('started.json', dict(schema='stage180_warehouse_archive_started_v1', started_at=utc_now(),
             inputs=inputs, frozen_domain=plan['frozen_candidate_domain'], http=budget,
             timeout_enforcement=timeout_note, automatic_retry=False, **ZERO_BUDGETS))
    metadata('date_manifest.json', records)
    journal(dict(event='batch_started', date_count=len(actions),
                 full_action_records_sha256=plan['frozen_candidate_domain']['full_action_records_sha256']))
    try:
        # All existing bodies are validated once before any GET; never copy or substitute.
        for item in actions:
            if item['action'] != 'reuse':
                continue
            i = item['sequence_index']
            rec = dict(records[i], started_at=utc_now())
            source = plan['reuse_by_date'][item['date']]
            rec.update(original_body_binding=source['body'],
                       original_fetch_metadata=source.get('original_fetch_metadata', {}),
                       original_evidence=source.get('evidence', {}))
            try:
                guard()
                raw = Path(source['body']['path']).read_bytes()
                observed = dict(path=source['body']['path'], bytes=len(raw), sha256=sha(raw))
                rec['body'] = dict(observed, complete=True, truncated_prefix=False, reused=True)
                if any(observed[k] != source['body'][k] for k in ('bytes', 'sha256')):
                    raise ValueError('reused_bytes_or_sha256_mismatch')
                check = inspect_body(raw, item['format'], item['date'])
                rec.update(check)
                if not check['expected_envelope'] or check['date_state'] in ('conflict', 'unparseable'):
                    raise ValueError('reused_envelope_or_report_date_mismatch')
                rec['state'] = 'reused_binding_verified'
            except Exception as error:
                rec.update(state='failed_reuse_binding', error_type=type(error).__name__, error=str(error))
                stop_reason = rec['state'] + ':' + str(error)
            rec['finished_at'] = utc_now()
            persist(i, rec)
            if stop_reason:
                break
        if not stop_reason:
            for item in actions:
                if item['action'] == 'reuse':
                    continue
                i = item['sequence_index']
                rec = dict(records[i])
                try:
                    guard()
                    if attempted >= budget['max_new_report_GETs']:
                        raise ArchiveStop('max_new_report_GETs')
                    if total_bytes >= budget['global_new_response_body_cap_bytes']:
                        raise ArchiveStop('global_new_response_body_cap')
                    if previous_get_start is not None:
                        remaining = budget['minimum_gap_between_GETs_seconds'] - (monotonic() - previous_get_start)
                        if remaining > 0:
                            sleep(remaining)
                    guard()
                except ArchiveStop as error:
                    rec.update(state='failed_bound_or_budget', error=str(error), finished_at=utc_now())
                    persist(i, rec)
                    stop_reason = str(error)
                    break
                report_start = monotonic()
                attempted += 1
                rec.update(attempt=1, started_at=utc_now(), get_start_elapsed_seconds=report_start-began)
                journal(dict(event='get_dispatch_pending', sequence_index=i, date=item['date'], url=item['url'],
                             prepared_elapsed_seconds=report_start-began, attempt=1))
                path = output / (item['date'] + ('.dat' if item['format'] == 'json' else '.html'))
                size = 0
                hasher = hashlib.sha256()
                parts = []
                complete = False
                rec['state'] = 'failed_http_or_network'
                with path.open('xb') as handle:
                    try:
                        guard()
                        if previous_get_start is not None:
                            gap = budget['minimum_gap_between_GETs_seconds'] - (monotonic()-previous_get_start)
                            if gap > 0:
                                sleep(gap)
                        guard()
                        if session is not None:
                            session.cookies.clear()  # Never send a prior response cookie.
                        report_start = monotonic()
                        previous_get_start = report_start
                        rec.update(started_at=utc_now(), get_start_elapsed_seconds=report_start-began)
                        remaining = min(budget['hard_per_report_elapsed_seconds'],
                                        budget['hard_batch_elapsed_seconds']-(report_start-began))
                        timeout = (min(budget['connect_timeout_seconds'], remaining),
                                   min(budget['read_timeout_seconds'], remaining))
                        rec['requested_timeout_seconds'] = list(timeout)
                        with get(item['url'], headers={'User-Agent': 'Mozilla/5.0 (compatible; public futures data research)',
                                 'Accept-Encoding': 'identity'}, timeout=timeout,
                                 verify=True, allow_redirects=False, stream=True) as response:
                            rec.update(http_status=response.status_code, headers=dict(response.headers),
                                       headers_basis='requests.Response.headers',
                                       body_bytes_basis='HTTP decoded entity bytes; plain saved without re-encoding')
                            while True:
                                guard(report_start)
                                allowance = min(budget['per_body_cap_bytes']-size,
                                                budget['global_new_response_body_cap_bytes']-total_bytes)
                                # Read at most the remaining body allowance plus one sentinel.
                                part = response.raw.read(min(65536, allowance + 1), decode_content=True)
                                if not part:
                                    complete = True
                                    break
                                handle.write(part)
                                hasher.update(part)
                                parts.append(part)
                                size += len(part)
                                total_bytes += len(part)
                                if size > budget['per_body_cap_bytes']:
                                    raise ArchiveStop('per_body_cap')
                                if total_bytes > budget['global_new_response_body_cap_bytes']:
                                    raise ArchiveStop('global_new_response_body_cap')
                                guard(report_start)
                        guard(report_start)
                        if rec['http_status'] != 200:
                            rec.update(state='failed_http_or_network', error='non_200_or_redirect')
                        else:
                            check = inspect_body(b''.join(parts), item['format'], item['date'])
                            rec.update(check)
                            guard(report_start)
                            rec['state'] = ('http200_expected_envelope' if check['expected_envelope'] and
                                            check['date_state'] in ('matched', 'absent') else 'failed_envelope_or_report_date')
                    except ArchiveStop as error:
                        rec.update(state='failed_bound_or_budget', error_type=type(error).__name__, error=str(error))
                    except Exception as error:
                        rec.update(state='failed_http_or_network', error_type=type(error).__name__, error=str(error))
                    finally:
                        handle.flush()
                        os.fsync(handle.fileno())
                rec['body'] = dict(path=str(path), bytes=size, sha256=hasher.hexdigest(),
                                   complete=complete, truncated_prefix=not complete, reused=False,
                                   archived_at=utc_now())
                rec.update(finished_at=utc_now(), elapsed_seconds=monotonic()-report_start,
                           report_elapsed_cap_exceeded=monotonic()-report_start > budget['hard_per_report_elapsed_seconds'],
                           batch_elapsed_seconds=monotonic()-began)
                persist(i, rec)
                print(json.dumps(dict(date=rec['date'], state=rec['state'], attempts=attempted,
                                      new_response_body_bytes=total_bytes)), flush=True)
                if rec['state'] != 'http200_expected_envelope':
                    stop_reason = rec['state'] + ':' + rec.get('error', rec.get('date_state', 'unknown'))
                    break
    except Exception as error:
        stop_reason = type(error).__name__ + ':' + str(error)
        # If metadata itself exceeds budget, retain explicit compact failure evidence.
        # Exact body bytes already saved are never removed or replaced.
        if 'rec' in locals() and 'i' in locals():
            compact = {k: rec[k] for k in ('sequence_index', 'date', 'format', 'url', 'action', 'attempt', 'body', 'response') if k in rec}
            compact.update(state='failed_bound_or_budget' if isinstance(error, ArchiveStop) else 'failed_archive_io',
                           error=stop_reason, metadata_capture_truncated=True,
                           omitted_record_bytes=len(encoded(rec)), omitted_record_sha256=sha(encoded(rec)))
            update(i, compact)
            try:
                metadata('journal.jsonl', dict(event='archive_failure', record=compact, archived_at=utc_now()), append=True, final=True)
            except (OSError, ArchiveStop):
                pass  # Final date_manifest/terminal remain the canonical failure record.
    finally:
        for i, rec in enumerate(records):
            if rec['state'] == 'not_attempted_pending':
                update(i, dict(rec, state='not_attempted_after_stop'))
        counts = Counter(r['state'] for r in records)
        success = counts['reused_binding_verified'] + counts['http200_expected_envelope']
        completed = success == len(actions) and stop_reason is None
        summary = dict(date_count=len(actions), state_counts=dict(counts), report_requests_attempted=attempted,
                       reused_binding_verified=counts['reused_binding_verified'],
                       new_expected_envelopes=counts['http200_expected_envelope'], completed_dates=success,
                       not_attempted=counts['not_attempted_after_stop'], new_response_body_bytes=total_bytes,
                       reused_body_bytes=sum(r.get('body', {}).get('bytes', 0) for r in records if r['state'] == 'reused_binding_verified'),
                       metadata_bytes_before_terminal=metadata_used)
        metadata('date_manifest.json', records, final=True)
        terminal = dict(schema='stage180_warehouse_archive_terminal_v1', status='completed' if completed else 'stopped',
                        exit_code=0 if completed else 1, finished_at=utc_now(), elapsed_seconds=monotonic()-began,
                        stop_reason=stop_reason, summary=summary, automatic_retry=False, automatic_resume=False,
                        timeout_enforcement=timeout_note, batch_elapsed_cap_exceeded=monotonic()-began > budget['hard_batch_elapsed_seconds'],
                        cumulative_fit=409, cumulative_cash=218, goal_complete=False, **ZERO_BUDGETS)
        metadata('terminal.json', terminal, final=True)
        artifacts = {name.removesuffix('.json').removesuffix('.jsonl'): binding(output/name)
                     for name in ('started.json', 'date_manifest.json', 'journal.jsonl', 'terminal.json')}
        manifest = dict(schema='stage180_warehouse_archive_manifest_v1', status=terminal['status'], inputs=inputs,
                        **artifacts, summary=summary, budget=budget, body_binding_role='every date_manifest body, including referenced old originals',
                        strict_PIT=False, automatic_retry=False, automatic_resume=False, **ZERO_BUDGETS)
        metadata('manifest.json', manifest, final=True)
        if session is not None:
            session.close()
    return manifest


def load_fixed_inputs(protocol_path):
    protocol_path = Path(protocol_path).resolve()
    raw = protocol_path.read_bytes()
    if sha(raw) != PROTOCOL_SHA256:
        raise ValueError('frozen179_protocol_sha256_mismatch')
    protocol = json.loads(raw)
    if protocol['schema'] != 'stage179_fixed_history_warehouse_archive_v1' or protocol['approved_by'] != 'root':
        raise ValueError('unexpected179_protocol')
    plan_binding = protocol['plan']
    plan_raw = Path(plan_binding['path']).read_bytes()
    if len(plan_raw) != plan_binding['bytes'] or sha(plan_raw) != plan_binding['sha256'] or sha(plan_raw) != PLAN_SHA256:
        raise ValueError('frozen178_plan_binding_mismatch')
    plan = json.loads(plan_raw)
    if protocol['http'] != plan['proposed_network_budget']:
        raise ValueError('frozen_budget_mismatch')
    domain = {k: v for k, v in plan['frozen_candidate_domain'].items() if k != 'dates'}
    if domain != protocol['expected_domain']:
        raise ValueError('frozen179_domain_mismatch')
    build_actions(plan)
    return plan, protocol['http'], dict(protocol=binding(protocol_path, raw), plan=plan_binding,
                                       source=binding(Path(__file__).resolve()))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    plan, budget, inputs = load_fixed_inputs(args.protocol)
    result = run_archive(plan, budget, args.output, inputs=inputs)
    return 0 if result['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
