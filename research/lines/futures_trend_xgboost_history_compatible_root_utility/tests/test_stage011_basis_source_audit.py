import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / "tools/stage011_basis_source_audit.py"
    assert path.exists(), "basis audit implementation missing"
    spec = importlib.util.spec_from_file_location("basis_audit_test", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def basis(days=("20210101", "20210102")):
    return pd.DataFrame({"date": list(days), "symbol": ["RB"] * len(days),
        "spot_price": [100.] * len(days), "near_contract_price": [90.] * len(days),
        "dominant_contract_price": [110.] * len(days), "near_basis_rate": [-0.1] * len(days),
        "dom_basis_rate": [0.1] * len(days), "near_contract": ["rb2101"] * len(days),
        "dominant_contract": ["rb2105"] * len(days)})


def events(days=("2021-01-02", "2021-01-09", "2021-01-10")):
    return pd.DataFrame({"event_id": [str(i) for i in range(len(days))], "decision_date": list(days),
        "product_vt_symbol": ["rb.SHFE"] * len(days), "contract_vt_symbol": ["rb2105.SHFE"] * len(days),
        "direction": ["long"] * len(days)})


def test_formula_uses_futures_over_spot_not_vendor_display_sign():
    m = module()
    data = basis()
    assert m.normalize_basis(data).quality_ok.all()
    data.loc[0, "dom_basis_rate"] = -0.1
    assert not m.normalize_basis(data).loc[0, "quality_ok"]


@pytest.mark.parametrize("field,value", [("spot_price", 0), ("near_contract_price", float("inf")),
                                          ("dom_basis_rate", float("nan"))])
def test_invalid_quotes_remain_rows_but_not_eligible(field, value):
    data = basis()
    data.loc[0, field] = value
    got = module().normalize_basis(data)
    assert len(got) == 2
    assert got.quality_ok.tolist() == [False, True]


def test_same_day_future_and_stale_rules_are_exact():
    m = module()
    got = m.coverage(events(), m.normalize_basis(basis()))
    assert got.coverage_status.tolist() == ["available", "available", "stale"]
    assert got.source_date.tolist() == ["2021-01-01", "2021-01-02", "2021-01-02"]
    assert got.age_days.tolist() == [1, 7, 8]
    assert pd.isna(got.loc[2, "dom_basis_rate"])
    early = m.coverage(events(("2020-12-31", "2021-01-01")), m.normalize_basis(basis()))
    assert early.coverage_status.tolist() == ["no_prior", "no_prior"]


def test_latest_invalid_quote_does_not_fall_back_to_older_good_row():
    m = module()
    data = basis()
    data.loc[1, "spot_price"] = 0
    got = m.coverage(events(("2021-01-03",)), m.normalize_basis(data))
    assert got.loc[0, "coverage_status"] == "invalid_latest"
    assert got.loc[0, "source_date"] == "2021-01-02"
    assert pd.isna(got.loc[0, "dom_basis_rate"])


def test_duplicate_source_keys_and_invalid_dates_are_rejected():
    with pytest.raises(RuntimeError, match="duplicate"):
        module().normalize_basis(basis(("20210101", "20210101")))
    with pytest.raises(RuntimeError, match="date"):
        module().normalize_basis(basis(("20210230",)))


def test_missing_product_not_imputed_and_contract_mismatch_disclosed():
    m = module()
    ev = events(("2021-01-03", "2021-01-04"))
    ev.loc[0, "contract_vt_symbol"] = "rb2110.SHFE"
    ev.loc[1, "product_vt_symbol"] = "cu.SHFE"
    got = m.coverage(ev, m.normalize_basis(basis()))
    assert got.coverage_status.tolist() == ["available", "no_prior"]
    assert not got.loc[0, "same_vendor_dominant_contract"]


def test_mature_count_excludes_equal_cutoff_and_censored_without_reading_targets():
    m = module()
    rows = events(("2021-01-02", "2021-01-03", "2021-01-04"))
    rows["coverage_status"] = "available"
    lifecycle = pd.DataFrame({"event_id": ["0", "1", "2"], "end_date": ["2021-01-31", "2021-02-01", None],
                              "status": ["mature", "mature_cancelled_unfilled", "right_censored_open"]})
    result = m.maturity_counts(rows, lifecycle, ["2021-02-01", "2021-03-01"])
    assert result.available_mature_count.tolist() == [1, 2]
    with pytest.raises(RuntimeError, match="inventory"):
        m.maturity_counts(rows, lifecycle.iloc[:2], ["2021-02-01"])


def test_publication_is_page_claim_not_fetch_time_and_wrong_day_is_rejected():
    m = module()
    html = '<html><title>2025年12月10日商品现货与期货价格对比表</title><body>https://www.100ppi.com 2025年12月10日 16:30 来源：生意社</body></html>'
    got = m.page_publication(html, "2025-12-10")
    assert got["declared_publication_at"] == "2025-12-10T16:30:00+08:00"
    assert got["historical_revision_verified"] is False
    with pytest.raises(RuntimeError, match="page_date"):
        m.page_publication(html, "2025-12-11")


def test_output_already_exists_stops_before_any_source_or_network_read(tmp_path, monkeypatch):
    m = module()
    monkeypatch.setattr(m, "OUTPUT", tmp_path)
    with pytest.raises(RuntimeError, match="already_exists"):
        m.run()


def test_gap_plan_contains_all_frozen_calendar_days_not_only_entry_days():
    m = module()
    calendar = pd.DataFrame({"date": ["2026-04-17", "2026-04-20", "2026-04-21", "2026-08-28", "2026-08-31"]})
    assert m.gap_days(calendar, "2026-04-17").date.tolist() == ["2026-04-20", "2026-04-21", "2026-08-28"]
    with pytest.raises(RuntimeError, match="calendar_inventory"):
        m.gap_days(pd.concat([calendar, calendar]), "2026-04-17")


def test_probe_is_three_single_requests_without_redirect_or_retry(tmp_path, monkeypatch):
    import requests

    m = module()
    monkeypatch.setattr(m, "OUTPUT", tmp_path)
    (tmp_path / "summary.json").write_text(json.dumps({"outputs": {}, "gap_first": "2026-04-20", "gap_last": "2026-08-28"}))
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(status_code=403, url=url, content=b"denied")

    monkeypatch.setattr(requests, "get", get)
    result = m.probe()
    assert result["requests"] == len(calls) == 3
    assert result["retries"] == 0
    assert not result["data_extension_performed"]
    assert all(options == {"timeout": (5, 10), "allow_redirects": False} for _, options in calls)
    assert all(row["status"] == "http_failure" for row in result["probes"])
    assert [Path(url).name for url, _ in calls] == ["day-2025-12-10.html", "day-2026-04-20.html", "day-2026-08-28.html"]
    with pytest.raises(RuntimeError, match="already_exists"):
        m.probe()
    assert len(calls) == 3


def test_no_publication_timestamp_is_not_invented_from_fetch_time():
    result = module().page_publication("<title>2025年12月10日商品现货与期货价格对比表</title>", "2025-12-10")
    assert result["declared_publication_at"] is None
    assert not result["historical_revision_verified"]
