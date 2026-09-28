import importlib.util
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
DAYS = pd.bdate_range("2020-01-02", periods=9).strftime("%Y-%m-%d").tolist()


def module():
    path = ROOT / "tools/stage028_chain_coverage.py"
    assert path.exists(), "chain coverage missing"
    spec = importlib.util.spec_from_file_location("chain_coverage_test028", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def catalog():
    return pd.DataFrame([dict(tq_symbol="SHFE.rb2005", vt_symbol="rb2005.SHFE",
        product_vt_symbol="rb.SHFE", expire_date="2020-05-15"),
        dict(tq_symbol="SHFE.rb2010", vt_symbol="rb2010.SHFE", product_vt_symbol="rb.SHFE", expire_date="2020-10-15")])


def bars():
    return pd.DataFrame([dict(tq_symbol=s, trade_date=d, volume=5, open_oi=10, close_oi=12)
        for s in catalog().tq_symbol for d in DAYS])


def event(day=DAYS[-1]):
    return pd.DataFrame([dict(event_id="e", decision_date=day, product_vt_symbol="rb.SHFE",
        contract_vt_symbol="rb2005.SHFE", direction="long")])


def test_complete_chain_and_exact_six_prior_sessions():
    m = module(); chain, gaps, lifetime = m.audit_chain(bars(), catalog(), DAYS)
    out = m.event_coverage(event(), bars(), catalog(), chain, DAYS)
    assert gaps.empty and len(lifetime) == 2
    assert chain.coverage_status.eq("available").all()
    assert out.coverage_status.tolist() == ["available"]
    assert out.source_date.tolist() == [DAYS[-2]]
    assert out.window_start.tolist() == [DAYS[-7]]


def test_unobserved_future_contract_cannot_enter_past_chain():
    b = bars(); b = b[~(b.tq_symbol.eq("SHFE.rb2010") & b.trade_date.lt(DAYS[4]))]
    chain, gaps, _ = module().audit_chain(b, catalog(), DAYS)
    assert gaps.empty
    assert chain.expected_contracts.tolist() == [1]*4 + [2]*5


def test_missing_last_days_not_hidden_using_future_last_seen():
    b = bars(); b = b[~(b.tq_symbol.eq("SHFE.rb2010") & b.trade_date.ge(DAYS[-2]))]
    chain, gaps, _ = module().audit_chain(b, catalog(), DAYS)
    assert gaps.trade_date.tolist() == DAYS[-2:]
    assert chain.iloc[-1].coverage_status == "missing_observed_contract"


def test_expired_contract_not_expected_after_expiry():
    c = catalog(); c.loc[1,"expire_date"] = DAYS[3]
    b = bars(); b = b[~(b.tq_symbol.eq("SHFE.rb2010") & b.trade_date.gt(DAYS[3]))]
    chain, gaps, _ = module().audit_chain(b,c,DAYS)
    assert gaps.empty and chain.expected_contracts.tolist() == [2]*4 + [1]*5


def test_missing_other_contract_blocks_event_without_zero_fill():
    m = module(); b=bars(); b=b[~(b.tq_symbol.eq("SHFE.rb2010") & b.trade_date.eq(DAYS[3]))]
    chain,gaps,_=m.audit_chain(b,catalog(),DAYS)
    out=m.event_coverage(event(),b,catalog(),chain,DAYS)
    assert len(gaps)==1 and out.coverage_status.tolist()==["incomplete_chain_window"]


def test_missing_current_day_does_not_contaminate_prior_decision():
    m=module(); b=bars(); b=b[b.trade_date.ne(DAYS[-1])]
    chain,_,_=m.audit_chain(b,catalog(),DAYS)
    assert m.event_coverage(event(),b,catalog(),chain,DAYS).coverage_status.tolist()==["available"]


def test_zero_total_oi_fails_without_adding_epsilon():
    b=bars();b["close_oi"]=0
    chain,_,_=module().audit_chain(b,catalog(),DAYS)
    assert chain.coverage_status.eq("nonpositive_chain_oi").all()


def test_calendar_gap_is_not_inferred_from_data_union():
    b=bars();b=b[b.trade_date.ne(DAYS[4])]
    _,gaps,_=module().audit_chain(b,catalog(),DAYS)
    assert len(gaps)==2 and set(gaps.trade_date)=={DAYS[4]}


@pytest.mark.parametrize("change", ["duplicate", "after_expiry", "nonfinite", "unknown"])
def test_invalid_source_rejected(change):
    b=bars(); c=catalog()
    if change=="duplicate": b=pd.concat([b,b.iloc[:1]],ignore_index=True)
    elif change=="after_expiry": c.loc[0,"expire_date"]=DAYS[3]
    elif change=="nonfinite": b.loc[0,"close_oi"]=float("nan")
    else: b.loc[0,"tq_symbol"]="SHFE.cu2005"
    with pytest.raises(ValueError):module().audit_chain(b,c,DAYS)


def test_unknown_product_or_wrong_contract_blocks_event():
    m=module();c=catalog();b=bars();chain,_,_=m.audit_chain(b,c,DAYS)
    e=event();e["product_vt_symbol"]="cu.SHFE"
    with pytest.raises(ValueError):m.event_coverage(e,b,c,chain,DAYS)


def test_insufficient_history_stays_visible():
    m=module();c=catalog();b=bars();chain,_,_=m.audit_chain(b,c,DAYS)
    assert m.event_coverage(event(DAYS[3]),b,c,chain,DAYS).coverage_status.tolist()==["insufficient_history"]


def test_duplicate_calendar_is_error():
    with pytest.raises(ValueError):module().audit_chain(bars(),catalog(),DAYS+DAYS[-1:])
