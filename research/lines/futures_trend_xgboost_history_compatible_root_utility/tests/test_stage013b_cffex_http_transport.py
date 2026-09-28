import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / "tools/stage013b_cffex_http_transport.py"
    assert path.exists(), "transport amendment implementation missing"
    spec = importlib.util.spec_from_file_location("cffex_http_transport_test", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_http_url_and_receipt_are_truthful_without_retry_or_redirect(tmp_path, monkeypatch):
    import json
    import requests

    m = module()
    calls = []

    def get(url, **options):
        calls.append((url, options))
        return SimpleNamespace(status_code=200, content=b"test-body")

    monkeypatch.setattr(requests, "get", get)
    assert m.download("202606", tmp_path) == b"test-body"
    record = json.loads((tmp_path / "202606.request.json").read_text())
    assert calls[0][0] == record["url"] == "http://www.cffex.com.cn/sj/historysj/202606/zip/202606.zip"
    assert calls[0][1]["timeout"] == (5, 20)
    assert calls[0][1]["allow_redirects"] is False
    with pytest.raises(RuntimeError, match="already_exists"):
        m.download("202606", tmp_path)
    assert len(calls) == 1


def test_scientific_functions_are_unmodified_parent_objects():
    m = module()
    base = m.configured()
    assert base.parse_archive.__module__ == "cffex_source_scientific_parent"
    assert base.select_returns.__module__ == "cffex_source_scientific_parent"
    assert base.coverage.__module__ == "cffex_source_scientific_parent"
    assert base.download is m.download
    assert base.OUTPUT == m.OUTPUT


def test_existing_destination_prevents_all_source_and_network_work(tmp_path, monkeypatch):
    m = module()
    monkeypatch.setattr(m, "OUTPUT", tmp_path)
    with pytest.raises(RuntimeError, match="already_exists"):
        m.run()
