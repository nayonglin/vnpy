import importlib.util
import io
import json
import zipfile
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / "tools/stage020_member_raw_probe.py"
    assert path.exists(), "member raw probe implementation missing"
    spec = importlib.util.spec_from_file_location("member_probe_test", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_plan_is_eight_frozen_readonly_requests():
    plan = module().PLAN
    assert len(plan) == 8
    assert [p['exchange'] for p in plan] == ['SHFE','SHFE','CZCE','CZCE','DCE','GFEX','GFEX','GFEX']
    assert plan[4]['json']['contractId'] == 'jm2005'
    assert [p['data']['data_type'] for p in plan[5:]] == ['1','2','3']


def test_shfe_requires_nonempty_cursor_and_exact_early_contract():
    m = module()
    body = json.dumps({'report_date':'20200107','o_cursor':[{'INSTRUMENTID':' rb2005 '}]}).encode()
    assert m.inspect(m.PLAN[0], body)['expected_contract_present']
    with pytest.raises(RuntimeError, match='contract'):
        m.inspect(m.PLAN[0], body.replace(b'rb2005', b'rb2010'))
    with pytest.raises(RuntimeError, match='empty'):
        m.inspect(m.PLAN[0], b'{"o_cursor": []}')


def test_html_challenge_is_not_a_workbook():
    m = module()
    with pytest.raises(RuntimeError, match='workbook'):
        m.inspect(m.PLAN[2], b'<html>verify access</html>')


def test_workbook_matching_is_token_bounded_and_not_claimed_pit():
    m = module()
    buf = io.BytesIO()
    pd.DataFrame([['2020-03-11'],['contract:CF005']]).to_excel(buf, index=False, header=False)
    got = m.inspect(m.PLAN[2], buf.getvalue())
    assert got['expected_contract_present']
    assert got['historical_publication_verified'] is False
    buf = io.BytesIO()
    pd.DataFrame([['contract:CF0050']]).to_excel(buf, index=False, header=False)
    with pytest.raises(RuntimeError, match='contract'):
        m.inspect(m.PLAN[2], buf.getvalue())


def test_dce_checks_filename_date_and_contract_without_extracting():
    m = module()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('20200108_jm2005_rank.txt', 'opaque')
    assert m.inspect(m.PLAN[4], buf.getvalue())['matching_archive_members'] == ['20200108_jm2005_rank.txt']
    with pytest.raises(RuntimeError, match='contract'):
        m.inspect({**m.PLAN[4], 'contract': 'jm2010'}, buf.getvalue())


def test_gfex_needs_rows_and_position_fields():
    m = module()
    got = m.inspect(m.PLAN[5], b'{"data":[{"abbr":"A","todayQty":20}]}')
    assert got['row_count'] == 1 and got['response_contract_identity_verified'] is False
    with pytest.raises(RuntimeError, match='empty'):
        m.inspect(m.PLAN[5], b'{"data":[]}')


def test_first_exchange_failure_skips_later_calls_and_preserves_other_exchanges(tmp_path):
    m = module()
    called = []
    def attempt(item, output):
        called.append(item['id'])
        return {'id':item['id'],'exchange':item['exchange'],'status':'failed'}
    records = m.execute(m.PLAN, tmp_path, attempt=attempt)
    assert len(called) == 4
    assert sum(r['status']=='skipped_after_exchange_failure' for r in records) == 4


def test_existing_output_fails_without_network(tmp_path, monkeypatch):
    m = module()
    monkeypatch.setattr(m, 'OUTPUT', tmp_path)
    with pytest.raises(RuntimeError, match='already_exists'):
        m.run()


def test_request_has_fixed_timeout_no_redirect_no_custom_credentials(tmp_path, monkeypatch):
    import requests
    m = module()
    calls = []
    class Response:
        status_code = 403
        headers = {'Content-Type': 'text/html'}
        def iter_content(self, chunk_size):
            yield b'denied'
        def close(self):
            pass
    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return Response()
    monkeypatch.setattr(requests, 'request', request)
    result = m.fetch(m.PLAN[0], tmp_path)
    assert len(calls) == 1 and result['status'] == 'failed'
    assert calls[0][2] == {'timeout': (5,15), 'allow_redirects': False, 'stream': True}
    assert (tmp_path / (m.PLAN[0]['id'] + '.body')).read_bytes() == b'denied'


def test_oversized_response_preserves_prefix_but_never_passes(tmp_path, monkeypatch):
    import requests
    m = module()
    monkeypatch.setattr(m, 'MAX_BYTES', 4)
    class Response:
        status_code = 200
        headers = {}
        def iter_content(self, chunk_size):
            yield b'123456'
        def close(self):
            pass
    monkeypatch.setattr(requests, 'request', lambda *args, **kwargs: Response())
    result = m.fetch(m.PLAN[0], tmp_path)
    assert result['status'] == 'failed' and result['body_truncated'] is True
    assert result['received_bytes'] == 4
    assert 'response_size_limit' in result['error']
