import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / "tools/stage012_alternative_spot_source.py"
    assert path.exists(), "alternative spot probe implementation missing"
    spec = importlib.util.spec_from_file_location("alternative_spot_test", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def catalog_html(items):
    data = {"props": {"pageProps": {"data": {"varietyListData": [{"productList": items}]}}}}
    return '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(data) + "</script>"


def test_catalog_uses_source_ids_and_rejects_ambiguous_inventory():
    m = module()
    item = {"qhExchangeName": "上海期货交易所", "name": "螺纹钢", "productId": 22}
    assert m.catalog(catalog_html([item]))[0]["productId"] == 22
    with pytest.raises(RuntimeError, match="duplicate"):
        m.catalog(catalog_html([item, item]))
    with pytest.raises(RuntimeError, match="catalog"):
        m.catalog("<html>安全检查</html>")


def payload(rows=None):
    return {"code": 200, "data": {"list": rows or [{"date": "2026-08-28", "fp": "3100", "sp": "3200"}]}}


def test_price_quality_does_not_invent_publication_or_settlement_contract():
    rows, meta = module().history(payload())
    assert rows.loc[0, "futures_over_spot_minus_one"] == pytest.approx(3100 / 3200 - 1)
    assert rows.loc[0, "quality_ok"]
    assert meta["historical_publication_verified"] is False
    assert meta["futures_price_type"] == "vendor_close_not_settlement"
    assert meta["safe_to_splice_into_100ppi"] is False


@pytest.mark.parametrize("field,value", [("fp", 0), ("sp", float("nan")), ("sp", -1)])
def test_bad_price_retained_without_imputation(field, value):
    data = payload()
    data["data"]["list"][0][field] = value
    rows, _ = module().history(data)
    assert len(rows) == 1
    assert not rows.loc[0, "quality_ok"]


def test_duplicate_bad_date_outside_window_and_business_denial_rejected():
    m = module()
    data = payload()
    row = data["data"]["list"][0]
    with pytest.raises(RuntimeError, match="duplicate"):
        m.history(payload([row, row]))
    with pytest.raises(RuntimeError, match="date"):
        m.history(payload([{**row, "date": "2026-02-30"}]))
    with pytest.raises(RuntimeError, match="window"):
        m.history(payload([{**row, "date": "2026-08-31"}]))
    data["code"] = 403
    with pytest.raises(RuntimeError, match="business"):
        m.history(data)


def test_incomplete_pagination_is_not_full_history():
    m = module()
    data = payload()
    data["data"]["total"] = 2
    with pytest.raises(RuntimeError, match="pagination"):
        m.history(data)


def test_existing_output_prevents_network_and_source_reads(tmp_path, monkeypatch):
    m = module()
    monkeypatch.setattr(m, "OUTPUT", tmp_path)
    with pytest.raises(RuntimeError, match="already_exists"):
        m.run()


def test_access_denial_stops_after_one_request_and_does_not_retry(tmp_path, monkeypatch):
    import requests

    m = module()
    monkeypatch.setattr(m, "OUTPUT", tmp_path / "result")
    monkeypatch.setattr(m, "source_identities", lambda: {})
    calls = []

    def get(url, **options):
        calls.append((url, options))
        return SimpleNamespace(status_code=403, content=b"denied", headers={})

    monkeypatch.setattr(requests, "get", get)
    result = m.run()
    assert result["status"] == "source_not_qualified"
    assert result["request_count"] == len(calls) == 1
    assert calls[0][1]["allow_redirects"] is False
    assert calls[0][1]["timeout"] == (5, 10)
    assert not result["history"]


def test_four_request_budget_source_ids_and_header_not_persisted(tmp_path, monkeypatch):
    import requests

    m = module()
    monkeypatch.setattr(m, "OUTPUT", tmp_path / "result")
    monkeypatch.setattr(m, "source_identities", lambda: {})
    items = [{"qhExchangeName": "SHFE", "name": "螺纹钢", "productId": 22},
             {"qhExchangeName": "CZCE", "name": "苹果", "productId": 91}]
    bodies = [catalog_html(items).encode(), b"public bootstrap", json.dumps(payload()).encode(), json.dumps(payload()).encode()]
    calls = []

    def get(url, **options):
        calls.append((url, options))
        index = len(calls) - 1
        return SimpleNamespace(status_code=200, content=bodies[index], headers={"_pcc": "ephemeral-test-header"})

    monkeypatch.setattr(requests, "get", get)
    result = m.run()
    assert result["request_count"] == len(calls) == 4
    assert result["status"] == "samples_observed_not_full_source_qualification"
    assert calls[2][1]["params"]["productId"] == 22
    assert calls[3][1]["params"]["productId"] == 91
    assert all(call[1]["params"]["endDate"] == "2026-08-28" for call in calls[2:])
    assert all(b"ephemeral-test-header" not in p.read_bytes() for p in m.OUTPUT.rglob("*") if p.is_file())
