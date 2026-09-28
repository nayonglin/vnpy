import importlib.util
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / "tools/stage027_native_chain_source.py"
    assert path.exists(), "native chain source missing"
    spec = importlib.util.spec_from_file_location("chain_test027", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def bar(day="2020-01-02", **changes):
    row = dict(id=1, datetime=pd.Timestamp(day, tz="Asia/Shanghai").value,
               open=10, high=12, low=9, close=11, volume=50, open_oi=40, close_oi=47)
    row.update(changes)
    return row


def convert(rows, expiry="2020-05-15"):
    return module().normalise(pd.DataFrame(rows), "SHFE.rb2005", expiry)


def test_both_oi_fields_retained_without_alias():
    out, stats = convert([bar()])
    assert out.open_oi.tolist() == [40]
    assert out.close_oi.tolist() == [47]
    assert "open_interest" not in out.columns
    assert stats["rows"] == 1
    assert out.trade_date.tolist() == ["2020-01-02"]


def test_padding_and_before_start_are_counted():
    out, stats = convert([bar(id=-1, datetime=0), bar("2019-10-31", id=0), bar()])
    assert len(out) == 1
    assert stats["padding_rows"] == 1 and stats["before_start_rows"] == 1


@pytest.mark.parametrize("field,value", [("close_oi", float("nan")), ("close_oi", -1),
    ("open_oi", float("inf")), ("volume", -1), ("open", 13), ("low", 11),
    ("high", 10), ("close", 0), ("datetime", 0), ("id", float("nan"))])
def test_invalid_real_rows_not_silently_dropped(field, value):
    with pytest.raises(ValueError):
        convert([bar(**{field: value})])


@pytest.mark.parametrize("day", ["2020-05-18", "2026-08-31"])
def test_after_expiry_or_cutoff_rejected(day):
    with pytest.raises(ValueError):
        convert([bar(day)])


def test_duplicate_days_fail():
    with pytest.raises(ValueError, match="duplicate"):
        convert([bar(), bar(id=2)])


def test_empty_serial_is_explicit_not_zero_data():
    out, stats = convert([bar(id=-1, datetime=0)])
    assert out.empty and stats["status"] == "empty_unqualified"


def test_all_symbols_in_exactly_one_batch_with_probe_first():
    batches = module().plan_batches(["SHFE.rb2005", "SHFE.rb2006", "SHFE.rb2007"], ["SHFE.rb2006"])
    assert batches == [["SHFE.rb2006"], ["SHFE.rb2005", "SHFE.rb2007"]]


def test_bad_probe_inventory_is_error():
    with pytest.raises(ValueError):
        module().plan_batches(["SHFE.rb2005"], ["SHFE.rb2006"])
