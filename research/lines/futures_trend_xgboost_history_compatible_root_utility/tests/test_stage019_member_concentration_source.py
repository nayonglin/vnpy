import importlib.util
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / "tools/stage019_member_concentration_source.py"
    assert path.exists(), "member concentration source implementation missing"
    spec = importlib.util.spec_from_file_location("member_source_test", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def source(symbols=("RB2105",), days=("20210108",)):
    data = {"date": list(days), "symbol": list(symbols), "variety": ["RB"] * len(days)}
    for family in ("long_open_interest", "short_open_interest", "vol"):
        for rank in (5, 10, 15, 20):
            data[f"{family}_top{rank}"] = [float(rank * 10)] * len(days)
    return pd.DataFrame(data)


def events(days=("2021-01-11",)):
    return pd.DataFrame({"event_id": [str(i) for i in range(len(days))], "decision_date": list(days),
                         "product_vt_symbol": ["rb.SHFE"] * len(days),
                         "contract_vt_symbol": ["rb2105.SHFE"] * len(days),
                         "direction": ["long"] * len(days)})


def calendar():
    return pd.DataFrame({"date": ["2021-01-07", "2021-01-08", "2021-01-11", "2021-01-12"]})


def test_source_validates_cumulative_contract_counts_without_producing_features():
    got = module().normalize(source())
    assert got.quality_ok.tolist() == [True]
    assert got.source_date.tolist() == ["2021-01-08"]
    assert not any("ratio" in col or "concentration" in col for col in got.columns)


@pytest.mark.parametrize("column,value", [("vol_top20", 0), ("vol_top10", 1000),
    ("long_open_interest_top5", -1), ("short_open_interest_top20", float("nan")),
    ("vol_top5", float("inf")), ("long_open_interest_top5", 50.5)])
def test_bad_values_are_preserved_and_marked_not_filled(column, value):
    raw = source()
    raw.loc[0, column] = value
    got = module().normalize(raw)
    assert len(got) == 1 and not got.loc[0, "quality_ok"]
    if pd.isna(value):
        assert pd.isna(got.loc[0, column])
    else:
        assert got.loc[0, column] == value


def test_duplicate_dates_and_contract_keys_fail_including_case_alias():
    with pytest.raises(RuntimeError, match="duplicate"):
        module().normalize(source(("RB2105", "rb2105"), ("20210108", "20210108")))
    with pytest.raises(RuntimeError, match="date"):
        module().normalize(source(days=("20210230",)))


def test_invalid_contract_and_variety_identity_fail():
    with pytest.raises(RuntimeError, match="symbol"):
        module().normalize(source(symbols=("RB210513",)))
    raw = source()
    raw.loc[0, "variety"] = "CU"
    with pytest.raises(RuntimeError, match="variety"):
        module().normalize(raw)


def test_previous_trading_session_not_previous_natural_day_is_used():
    m = module()
    got = m.coverage(events(), m.normalize(source()), calendar())
    assert got.loc[0, "coverage_status"] == "available"
    assert got.loc[0, "required_source_date"] == "2021-01-08"


def test_same_day_and_older_observations_cannot_fill_previous_session():
    m = module()
    raw = source(("RB2105", "RB2105"), ("20210107", "20210111"))
    got = m.coverage(events(), m.normalize(raw), calendar())
    assert got.loc[0, "coverage_status"] == "missing_contract"


def test_product_total_and_different_maturity_do_not_fill_contract():
    m = module()
    raw = source(("RB", "RB2110"), ("20210108", "20210108"))
    got = m.coverage(events(), m.normalize(raw), calendar())
    assert got.loc[0, "coverage_status"] == "missing_contract"
    assert got.loc[0, "same_day_aggregate_present"]
    assert got.loc[0, "same_day_other_contract_count"] == 1


def test_bad_exact_row_cannot_fall_back_to_good_aggregate():
    m = module()
    raw = source(("RB2105", "RB"), ("20210108", "20210108"))
    raw.loc[0, "vol_top20"] = float("nan")
    got = m.coverage(events(), m.normalize(raw), calendar())
    assert got.loc[0, "coverage_status"] == "invalid_exact"


def test_outside_source_time_and_no_previous_calendar_are_explicit():
    m = module()
    got = m.coverage(events(("2021-01-07", "2021-01-08", "2021-01-12")),
                     m.normalize(source()), calendar())
    assert got.coverage_status.tolist() == ["no_previous_session", "outside_source_range", "outside_source_range"]


def test_calendar_and_event_identity_are_validated():
    m = module()
    with pytest.raises(RuntimeError, match="calendar"):
        m.coverage(events(), m.normalize(source()), pd.concat([calendar(), calendar()]))
    with pytest.raises(RuntimeError, match="calendar"):
        m.coverage(events(("2021-01-09",)), m.normalize(source()), calendar())
    with pytest.raises(RuntimeError, match="event"):
        m.coverage(pd.concat([events(), events()]), m.normalize(source()), calendar())
    ev = events()
    ev.loc[0, "contract_vt_symbol"] = "rb2105.DCE"
    with pytest.raises(RuntimeError, match="event"):
        m.coverage(ev, m.normalize(source()), calendar())


def test_existing_output_stops_before_reading_source(tmp_path, monkeypatch):
    m = module()
    monkeypatch.setattr(m, "OUTPUT", tmp_path)
    with pytest.raises(RuntimeError, match="already_exists"):
        m.run()
