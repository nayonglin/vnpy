import importlib.util
import json
import lzma
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / "tools/stage026_sdk_cache_catalog.py"
    assert path.exists(), "SDK cache adapter missing"
    spec = importlib.util.spec_from_file_location("cache_test026", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def raw(symbol="SHFE.rb2005", **changes):
    value = dict(instrument_id=symbol, ins_class="FUTURE", exchange_id="SHFE", product_id="rb",
                 expired=True, expire_datetime=pd.Timestamp("2020-05-15", tz="Asia/Shanghai").timestamp(),
                 delivery_year=2020, delivery_month=5, price_tick=1, volume_multiple=10)
    value.update(changes)
    return value


def test_cache_all_chain_members_kept_not_just_event_contracts():
    m = module()
    a = raw()
    b = raw("SHFE.rb2006", delivery_month=6)
    out, counts = m.project_cache({a["instrument_id"]: a, b["instrument_id"]: b}, {"rb.SHFE"})
    assert out.instrument_id.tolist() == ["SHFE.rb2005", "SHFE.rb2006"]
    assert counts["included"] == 2


def test_scope_exclusions_are_counted_without_using_unused_nan():
    m = module()
    a = raw(strike_price=float("nan"))
    old = raw("SHFE.rb1905", delivery_year=2019, expire_datetime=1557846000)
    option = raw("SHFE.rb2005C100", ins_class="FUTURE_OPTION")
    other = raw("SHFE.cu2005", product_id="cu")
    out, counts = m.project_cache({x["instrument_id"]: x for x in [a, old, option, other]}, {"rb.SHFE"})
    assert len(out) == 1
    assert counts == dict(total=4, non_future=1, other_product=1, before_start=1, included=1)


def test_cache_key_mismatch_rejected():
    with pytest.raises(ValueError, match="key_identity"):
        module().project_cache({"SHFE.rb2006": raw()}, {"rb.SHFE"})


@pytest.mark.parametrize("field,value", [("expire_datetime", float("nan")), ("delivery_year", 2020.5),
    ("delivery_month", 6), ("price_tick", 0), ("volume_multiple", -1), ("expired", "True")])
def test_bad_required_cache_metadata_fails(field, value):
    with pytest.raises((ValueError, RuntimeError)):
        module().project_cache({"SHFE.rb2005": raw(**{field: value})}, {"rb.SHFE"})


def test_duplicate_json_key_rejected(tmp_path):
    p = tmp_path / "cache.lzma"
    p.write_bytes(lzma.compress(b'{"x":{},"x":{}}'))
    with pytest.raises(ValueError, match="duplicate_json_key"):
        module().load_cache(p)


def test_modern_duplicate_rejected():
    m = module()
    with pytest.raises(ValueError, match="duplicate"):
        m.combine(pd.DataFrame([raw(), raw()]), pd.DataFrame([raw()]), {"rb.SHFE"})


def test_equal_overlap_deduplicated_with_both_sources():
    m = module()
    merged, sources = m.combine(pd.DataFrame([raw()]), pd.DataFrame([raw()]), {"rb.SHFE"})
    assert len(merged) == 1
    assert sources.source.tolist() == ["stage024+sdk_pre20_cache"]


@pytest.mark.parametrize("field,value", [("price_tick", 2), ("volume_multiple", 20),
    ("expire_datetime", 1589526000), ("expired", False)])
def test_valid_but_conflicting_overlap_rejected(field, value):
    m = module()
    with pytest.raises(ValueError, match="overlap_conflict"):
        m.combine(pd.DataFrame([raw()]), pd.DataFrame([raw(**{field: value})]), {"rb.SHFE"})


def test_combination_retains_modern_and_cache_only():
    m = module()
    b = raw("SHFE.rb2006", delivery_month=6)
    merged, sources = m.combine(pd.DataFrame([b]), pd.DataFrame([raw()]), {"rb.SHFE"})
    assert merged.instrument_id.tolist() == ["SHFE.rb2005", "SHFE.rb2006"]
    assert sources.source.tolist() == ["sdk_pre20_cache", "stage024"]


def test_load_valid_cache(tmp_path):
    p = tmp_path / "cache.lzma"
    p.write_bytes(lzma.compress(json.dumps({"SHFE.rb2005": raw()}).encode()))
    assert module().load_cache(p)["SHFE.rb2005"] == raw()
