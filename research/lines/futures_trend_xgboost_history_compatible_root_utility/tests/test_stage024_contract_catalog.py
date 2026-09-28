import importlib.util
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / "tools/stage024_contract_catalog.py"
    assert path.exists(), "contract catalog implementation missing"
    spec = importlib.util.spec_from_file_location("catalog_test024", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def raw(symbol="SHFE.rb2005", **changes):
    value = dict(instrument_id=symbol, ins_class="FUTURE", exchange_id="SHFE", product_id="rb",
                 expired=True, expire_datetime=pd.Timestamp("2020-05-15", tz="Asia/Shanghai").timestamp(),
                 delivery_year=2020, delivery_month=5, price_tick=1, volume_multiple=10)
    value.update(changes)
    return value


def events(**changes):
    row = dict(event_id="a", decision_date="2020-01-02", product_vt_symbol="rb.SHFE",
               contract_vt_symbol="rb2005.SHFE")
    row.update(changes)
    return pd.DataFrame([row])


def test_early_contract_not_lost_by_old_source_start():
    m = module()
    catalog = m.normalise(pd.DataFrame([raw()]), {"rb.SHFE"})
    assert catalog.vt_symbol.tolist() == ["rb2005.SHFE"]
    assert str(catalog.expire_date.iloc[0])[:10] == "2020-05-15"
    assert m.assess(catalog, events())["status"] == "catalog_qualified_not_bar_coverage"


def test_metadata_resolves_three_digit_year_without_decade_guessing():
    m = module()
    value = raw("CZCE.AP010", exchange_id="CZCE", product_id="AP", delivery_month=10,
                expire_datetime=pd.Timestamp("2020-10-20", tz="Asia/Shanghai").timestamp())
    cat = m.normalise(pd.DataFrame([value]), {"AP.CZCE"})
    assert int(cat.delivery_year.iloc[0]) == 2020
    assert cat.vt_symbol.tolist() == ["AP010.CZCE"]


def test_missing_contract_stays_visible_and_does_not_shrink_event_scope():
    m = module()
    cat = m.normalise(pd.DataFrame([raw()]), {"rb.SHFE"})
    data = pd.concat([events(), events(event_id="b", contract_vt_symbol="rb2010.SHFE")], ignore_index=True)
    report = m.assess(cat, data)
    assert report["status"] == "catalog_gap_stop_no_bars"
    assert report["event_count"] == 2
    assert report["missing_event_contracts"] == ["rb2010.SHFE"]


@pytest.mark.parametrize("changes", [dict(delivery_year=float("nan")), dict(delivery_month=13),
    dict(delivery_month=6), dict(delivery_year=2020.5), dict(expire_datetime=float("nan")),
    dict(price_tick=float("nan")), dict(expired="False")])
def test_invalid_metadata_rejected_without_imputation(changes):
    with pytest.raises((ValueError, RuntimeError)):
        module().normalise(pd.DataFrame([raw(**changes)]), {"rb.SHFE"})


def test_duplicate_raw_contract_is_error():
    with pytest.raises((ValueError, RuntimeError)):
        module().normalise(pd.DataFrame([raw(), raw()]), {"rb.SHFE"})


@pytest.mark.parametrize("changes", [dict(product_vt_symbol="cu.SHFE"), dict(decision_date="2020-05-18")])
def test_event_semantic_mismatch_does_not_pass(changes):
    m = module()
    cat = m.normalise(pd.DataFrame([raw()]), {"rb.SHFE"})
    assert m.assess(cat, events(**changes))["status"] == "catalog_gap_stop_no_bars"


def test_catalog_before_declared_source_is_excluded_not_latest_contract_substituted():
    m = module()
    old = raw("SHFE.rb1905", delivery_year=2019,
              expire_datetime=pd.Timestamp("2019-05-15", tz="Asia/Shanghai").timestamp())
    cat = m.normalise(pd.DataFrame([old, raw()]), {"rb.SHFE"})
    assert cat.vt_symbol.tolist() == ["rb2005.SHFE"]


def test_event_identity_duplicate_fails():
    m = module()
    cat = m.normalise(pd.DataFrame([raw()]), {"rb.SHFE"})
    with pytest.raises(ValueError):
        m.assess(cat, pd.concat([events(), events()], ignore_index=True))
