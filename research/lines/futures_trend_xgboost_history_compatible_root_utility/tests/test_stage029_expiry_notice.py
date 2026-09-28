import importlib.util
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / "tools/stage029_expiry_notice.py"
    assert path.exists(), "expiry notice adapter missing"
    spec = importlib.util.spec_from_file_location("expiry_notice_test029", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def catalog():
    return pd.DataFrame([dict(tq_symbol="SHFE.cu2102", expire_date="2021-02-18", delivery_year=2021, delivery_month=2),
        dict(tq_symbol="SHFE.sp2102", expire_date="2021-02-18", delivery_year=2021, delivery_month=2),
        dict(tq_symbol="SHFE.cu2103", expire_date="2021-03-15", delivery_year=2021, delivery_month=3)])


def notice():
    return dict(notice_id="SHFE[2020]66", published_on="2020-03-12", available_on="2020-03-13",
        contracts=[dict(tq_symbol=s, last_trade_date="2021-02-05") for s in ["SHFE.cu2102","SHFE.sp2102","SHFE.au2102"]])


def test_notice_applies_full_catalog_intersection_and_preserves_original():
    c=catalog(); original=c.copy(deep=True)
    corrected,audit=module().apply_notice(c,notice())
    assert corrected.expire_date.tolist()==["2021-02-05","2021-02-05","2021-03-15"]
    pd.testing.assert_frame_equal(c,original)
    assert audit.status.tolist()==["corrected","corrected","outside_research_catalog"]
    pd.testing.assert_frame_equal(corrected.drop(columns="expire_date"),c.drop(columns="expire_date"))


def test_notice_published_after_new_last_day_rejected():
    n=notice(); n['available_on']='2021-02-06'
    with pytest.raises(ValueError):module().apply_notice(catalog(),n)


def test_duplicate_notice_entry_rejected():
    n=notice();n['contracts'].append(n['contracts'][0])
    with pytest.raises(ValueError):module().apply_notice(catalog(),n)


def test_wrong_month_is_not_matched_by_product_prefix():
    c=catalog().iloc[2:].copy();corrected,audit=module().apply_notice(c,notice())
    pd.testing.assert_frame_equal(corrected,c)
    assert audit.status.eq('outside_research_catalog').all()


def test_announcement_cannot_change_preannouncement_active_set():
    c=catalog();fixed,_=module().apply_notice(c,notice())
    for day in ['2020-01-02','2020-03-12']:
        assert c.tq_symbol[c.expire_date.ge(day)].tolist()==fixed.tq_symbol[fixed.expire_date.ge(day)].tolist()


def test_parse_yearbook_close_and_oi_with_spaced_thousands():
    text='cu2102 57 ,750 20210104 60,680 20210108 56,730 20210205 58,040 20210205\ncu2102 60,680 20210108 36,600 20200323 3,215 20210205 1,456,088 42,825,445.40'
    result=module().yearbook_row(text,'cu2102')
    assert result==dict(symbol='cu2102',close_date='2021-02-05',close=58040.0,oi_date='2021-02-05',close_oi=3215.0)


def test_yearbook_ambiguous_rows_rejected():
    with pytest.raises(ValueError):module().yearbook_row('cu2102 20210205','cu2102')
