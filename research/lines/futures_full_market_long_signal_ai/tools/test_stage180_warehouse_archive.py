"""Five bounded synthetic archive fixtures; never contacts a real source."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    import stage180_warehouse_archive as archive
except ModuleNotFoundError:
    archive = None


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def plan_for(dates, reuse=None):
    reuse = reuse or {}
    records = []
    for i, date in enumerate(dates):
        fmt = 'json' if date < '20251118' else 'html'
        url = ('https://www.shfe.com.cn/data/tradedata/future/dailydata/' + date + 'dailystock.dat'
               if fmt == 'json' else 'https://www.shfe.com.cn/data/tradedata/future/stockdata/dailystock_' + date + '/ZH/all.html')
        records.append(dict(sequence_index=i, date=date, format=fmt, url=url,
                            action='reuse' if date in reuse else 'new_get'))
    domain = dict(dates=dates, count=len(dates), format_cutpoint='20251118',
                  before_cutpoint_template='https://www.shfe.com.cn/data/tradedata/future/dailydata/{YYYYMMDD}dailystock.dat',
                  at_or_after_cutpoint_template='https://www.shfe.com.cn/data/tradedata/future/stockdata/dailystock_{YYYYMMDD}/ZH/all.html',
                  dates_sha256=digest(dates), full_action_records_sha256=digest(records),
                  new_get_records_sha256=digest([r for r in records if r['action'] == 'new_get']),
                  reuse_count=len(reuse), new_get_count=len(dates)-len(reuse),
                  reuse_dates=sorted(reuse))
    return dict(frozen_candidate_domain=domain, reuse_by_date=reuse)


def budget_for(**overrides):
    result = dict(max_new_report_GETs=10, minimum_gap_between_GETs_seconds=1,
                  connect_timeout_seconds=8, read_timeout_seconds=20,
                  hard_per_report_elapsed_seconds=35, hard_batch_elapsed_seconds=14400,
                  per_body_cap_bytes=1024, global_new_response_body_cap_bytes=10000,
                  oversize_sentinel_max_extra_bytes=1, metadata_archive_cap_bytes=1048576)
    result.update(overrides)
    return result


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Raw:
    def __init__(self, body):
        self.stream = io.BytesIO(body)

    def read(self, size, decode_content=True):
        return self.stream.read(size)


class Response:
    def __init__(self, body, status=200):
        self.raw = Raw(body)
        self.status_code = status
        self.headers = {'Date': 'synthetic', 'Content-Type': 'application/json'}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(archive, 'stage180 implementation is missing')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_plan(self, plan, get, *, suffix='run', budget=None, clock=None):
        clock = clock or Clock()
        out = self.root / suffix
        result = archive.run_archive(plan, budget or budget_for(), out, get=get,
                                     monotonic=clock, sleep=clock.sleep)
        rows = json.loads((out / 'date_manifest.json').read_text())
        return result, rows, out

    def test_fixed_domain_hash_and_format_identity_are_checked(self):
        # Catches an altered domain/URL or action digest being silently accepted.
        plan = plan_for(['20251117', '20251118'])
        rows = archive.build_actions(plan)
        self.assertEqual(rows, [
            dict(sequence_index=0, date='20251117', format='json', action='new_get',
                 url='https://www.shfe.com.cn/data/tradedata/future/dailydata/20251117dailystock.dat'),
            dict(sequence_index=1, date='20251118', format='html', action='new_get',
                 url='https://www.shfe.com.cn/data/tradedata/future/stockdata/dailystock_20251118/ZH/all.html')])
        plan['frozen_candidate_domain']['dates'].reverse()
        with self.assertRaises(ValueError):
            archive.build_actions(plan)

    def test_all_reuse_precedes_get_no_fallback_and_get_start_gap(self):
        # Catches late reuse validation, re-download fallback, and zero GET spacing.
        body = b'{"o_cursor":[],"report_date":"20251117"}'
        old = self.root / 'old.dat'
        old.write_bytes(body)
        ref = dict(date='20251117', format='json',
                   url='https://www.shfe.com.cn/data/tradedata/future/dailydata/20251117dailystock.dat',
                   body=dict(path=str(old), bytes=len(body), sha256=hashlib.sha256(body).hexdigest()),
                   original_fetch_metadata={'http_status': 200, 'headers': {'Date': 'old'}})
        plan = plan_for(['20251113', '20251114', '20251117'], {'20251117': ref})
        clock = Clock()
        starts = []

        def get(url, **kwargs):
            journal = (self.root / 'run' / 'journal.jsonl').read_text()
            self.assertIn('reused_binding_verified', journal)
            self.assertFalse(kwargs['allow_redirects'])
            self.assertTrue(kwargs['verify'])
            starts.append(clock())
            return Response(b'{"o_cursor":[]}')

        manifest, rows, out = self.run_plan(plan, get, clock=clock)
        self.assertEqual(manifest['status'], 'completed')
        self.assertEqual([r['state'] for r in rows],
                         ['http200_expected_envelope', 'http200_expected_envelope', 'reused_binding_verified'])
        self.assertGreaterEqual(starts[1] - starts[0], 1)
        self.assertEqual(rows[2]['body']['path'], str(old))
        self.assertFalse((out / '20251117.dat').exists())
        with self.assertRaises(FileExistsError):
            archive.run_archive(plan, budget_for(), out, get=get)
        ref['body']['sha256'] = '0' * 64
        bad, badrows, _ = self.run_plan(plan, lambda *a, **k: self.fail('GET before reuse validated'), suffix='bad')
        self.assertEqual(bad['summary']['report_requests_attempted'], 0)
        self.assertEqual(bad['status'], 'stopped')
        self.assertEqual(badrows[0]['state'], 'not_attempted_after_stop')
        self.assertEqual(badrows[2]['state'], 'failed_reuse_binding')

    def test_first_http_network_envelope_or_date_failure_stops_remaining(self):
        # Catches continuing a batch after the first source failure or losing its body.
        for kind in ['http', 'network', 'envelope', 'date']:
            with self.subTest(kind=kind):
                calls = []

                def get(url, **kwargs):
                    calls.append(url)
                    if kind == 'network':
                        raise OSError('synthetic connection failure')
                    if kind == 'http':
                        return Response(b'failure evidence', 503)
                    if kind == 'envelope':
                        return Response(b'{"not_cursor":[]}')
                    return Response(b'{"o_cursor":[],"report_date":"20251112"}')

                m, rows, out = self.run_plan(plan_for(['20251113', '20251114']), get, suffix=kind)
                self.assertEqual(len(calls), 1)
                self.assertEqual(m['status'], 'stopped')
                self.assertTrue(rows[0]['state'].startswith('failed_'))
                self.assertEqual(rows[1]['state'], 'not_attempted_after_stop')
                self.assertTrue((out / 'terminal.json').exists())
                self.assertTrue(rows[0]['body']['complete'] if kind != 'network' else not rows[0]['body']['complete'])
                self.assertTrue(Path(rows[0]['body']['path']).exists())

    def test_missing_date_differs_from_conflict_and_html_uses_intro_only(self):
        # Catches fabricating missing dates or reading script/warehouse dates as report date.
        no_date = archive.inspect_body(b'{"o_cursor":[]}', 'json', '20251118')
        self.assertTrue(no_date['expected_envelope'])
        self.assertEqual(no_date['date_state'], 'absent')
        conflict = archive.inspect_body(b'{"o_cursor":[],"report_date":"20251118","o_tradingday":"20251117"}', 'json', '20251118')
        self.assertEqual(conflict['date_state'], 'conflict')
        html = '''<html><script>var report_date="2020-01-01";</script>
        <table class="content_intro"><tr><td>仓单日报</td><td>日期：2025-11-18</td></tr></table>
        <table><tr><th>地区</th><th>仓库</th><th>期货</th><th>增减</th></tr>
        <tr><td>仓库改名于2019-02-03</td><td>甲库</td><td>1</td><td>0</td></tr></table></html>'''.encode()
        checked = archive.inspect_body(html, 'html', '20251118')
        self.assertTrue(checked['expected_envelope'])
        self.assertEqual(checked['date_state'], 'matched')
        self.assertEqual(checked['report_dates'], {'intro': ['20251118']})
        absent = archive.inspect_body(b'<table><tr><td>2025-11-18</td></tr></table>', 'html', '20251118')
        self.assertEqual(absent['date_state'], 'absent')
        self.assertFalse(absent['expected_envelope'])
        legal_absent = archive.inspect_body(html.replace(b'2025-11-18', b''), 'html', '20251118')
        self.assertTrue(legal_absent['expected_envelope'])
        self.assertEqual(legal_absent['date_state'], 'absent')
        m, rows, _ = self.run_plan(plan_for(['20251118', '20251119']),
                                   lambda *a, **k: Response(b'<table><tr><td>HTTP200 generic error</td></tr></table>'),
                                   suffix='generic_html')
        self.assertEqual(m['status'], 'stopped')
        self.assertEqual(rows[0]['state'], 'failed_envelope_or_report_date')
        self.assertEqual(rows[1]['state'], 'not_attempted_after_stop')

    def test_overbudget_body_parse_stops_before_the_next_get(self):
        # Catches a parser exceeding the report clock but still being marked successful.
        clock = Clock()
        parse = archive.inspect_body

        def measured_parse(*args):
            checked = parse(*args)
            clock.now += 36  # Synthetic elapsed parse, with real envelope/date computation.
            return checked

        with patch.object(archive, 'inspect_body', measured_parse):
            m, rows, _ = self.run_plan(plan_for(['20251113', '20251114']),
                                       lambda *a, **k: Response(b'{"o_cursor":[]}'), clock=clock,
                                       suffix='overparse')
        self.assertEqual(m['status'], 'stopped')
        self.assertEqual(m['summary']['report_requests_attempted'], 1)
        self.assertEqual(rows[0]['state'], 'failed_bound_or_budget')
        self.assertEqual(rows[0]['error'], 'report_elapsed_cap')
        self.assertTrue(rows[0]['body']['complete'])
        self.assertEqual(rows[1]['state'], 'not_attempted_after_stop')

    def test_stream_caps_save_exact_prefix_with_at_most_one_sentinel(self):
        # Catches an oversized read, discarded failure prefix, or renewed global budget.
        plan = plan_for(['20251113', '20251114'])
        m, rows, out = self.run_plan(plan, lambda *a, **k: Response(b'abcdefghijklmnop'),
                                     suffix='per', budget=budget_for(per_body_cap_bytes=8))
        self.assertEqual(m['summary']['new_response_body_bytes'], 9)
        self.assertEqual(Path(rows[0]['body']['path']).read_bytes(), b'abcdefghi')
        self.assertFalse(rows[0]['body']['complete'])
        self.assertTrue(rows[0]['body']['truncated_prefix'])
        self.assertEqual(rows[0]['state'], 'failed_bound_or_budget')
        self.assertEqual(rows[1]['state'], 'not_attempted_after_stop')
        body = b'{"o_cursor":[]}'
        cap = len(body) + 2
        m, rows, out = self.run_plan(plan, lambda *a, **k: Response(body), suffix='global',
                                     budget=budget_for(global_new_response_body_cap_bytes=cap))
        self.assertEqual(m['summary']['new_response_body_bytes'], cap + 1)
        self.assertEqual(rows[0]['state'], 'http200_expected_envelope')
        self.assertEqual(rows[1]['body']['bytes'], 3)
        self.assertEqual(rows[1]['state'], 'failed_bound_or_budget')
        self.assertEqual(rows[1]['body']['sha256'], hashlib.sha256(body[:3]).hexdigest())


if __name__ == '__main__':
    unittest.main()
