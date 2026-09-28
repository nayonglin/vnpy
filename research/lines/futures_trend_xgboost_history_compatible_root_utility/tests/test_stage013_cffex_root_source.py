import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
import zipfile

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / "tools/stage013_cffex_root_source.py"
    assert path.exists(), "CFFEX source implementation missing"
    spec = importlib.util.spec_from_file_location("cffex_root_source_test", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def bars():
    rows = []
    for day, values in {"2024-01-02": [(100, 500), (200, 100)],
                        "2024-01-03": [(101, 100), (201, 900)],
                        "2024-01-04": [(102, 50), (202, 900)]}.items():
        for month, (close, oi) in zip(("2401", "2402"), values):
            rows.append(dict(date=day, root="IF", symbol="IF" + month, close=close, volume=100, open_interest=oi))
    return pd.DataFrame(rows)


def test_prior_selection_and_same_contract_return_include_roll_day():
    got = module().select_returns(bars())
    assert got.symbol.tolist() == ["IF2401", "IF2402"]
    assert got.selection_date.tolist() == ["2024-01-02", "2024-01-03"]
    assert got.product_return.tolist() == pytest.approx([101 / 100 - 1, 202 / 201 - 1])
    assert got.roll_event.tolist() == [False, True]


def test_future_oi_does_not_change_selection_or_prior_returns():
    m = module()
    data = bars()
    first = m.select_returns(data).iloc[0]
    data.loc[data.date.eq("2024-01-03"), "open_interest"] = [90000, 1]
    second = m.select_returns(data).iloc[0]
    assert first.symbol == second.symbol
    assert first.product_return == second.product_return


def test_missing_selected_contract_never_falls_back_to_current_survivor():
    data = bars()
    data = data.loc[~(data.date.eq("2024-01-03") & data.symbol.eq("IF2401"))]
    with pytest.raises(RuntimeError, match="selected_current_missing"):
        module().select_returns(data)


def test_invalid_current_selected_price_and_duplicates_rejected():
    m = module()
    data = bars()
    data.loc[data.date.eq("2024-01-03") & data.symbol.eq("IF2401"), "close"] = 0
    with pytest.raises(RuntimeError, match="selected_current_price"):
        m.select_returns(data)
    with pytest.raises(RuntimeError, match="duplicate"):
        m.select_returns(pd.concat([bars(), bars().iloc[:1]]))


def archive(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for name, contents in files.items():
            output.writestr(name, contents.encode())
    return buffer.getvalue()


def test_zip_month_safety_and_raw_bad_quote_retention():
    m = module()
    csv = "symbol,close,volume,open_interest\nIF2401,0,100,200\nIF2402,201,100,300\nIM2401,1,1,1\n"
    got, days = m.parse_archive("202401", archive({"20240102_1.csv": csv}))
    assert len(got) == 2
    assert got.quality_ok.tolist() == [False, True]
    assert days == ["2024-01-02"]
    with pytest.raises(RuntimeError, match="month"):
        m.parse_archive("202402", archive({"20240102_1.csv": csv}))
    with pytest.raises(RuntimeError, match="unsafe"):
        m.parse_archive("202401", archive({"../20240102_1.csv": csv}))


def selected():
    days = pd.bdate_range("2023-01-02", periods=125).strftime("%Y-%m-%d")
    return pd.DataFrame([{"date": day, "root": root, "product_return": i / 10000}
                         for i, day in enumerate(days) for root in module().ROOTS])


def test_coverage_requires_exact_prior_calendar_day_and_full_warmup():
    m = module()
    source = selected()
    days = sorted(source.date.unique())
    decisions = pd.Series([days[119], days[120], days[122]])
    got = m.coverage(decisions, source, days)
    assert got.coverage_status.tolist() == ["insufficient_history", "available", "available"]
    assert got.source_date.tolist() == [days[118], days[119], days[121]]
    missing = source.loc[~source.date.eq(days[121])]
    assert m.coverage(pd.Series([days[122]]), missing, days).loc[0, "coverage_status"] == "missing_prior_day"


def test_one_missing_root_inside_lookback_is_not_zero_filled():
    m = module()
    source = selected()
    days = sorted(source.date.unique())
    source = source.loc[~(source.date.eq(days[50]) & source.root.eq("IF"))]
    got = m.coverage(pd.Series([days[121]]), source, days)
    assert got.loc[0, "coverage_status"] == "incomplete_window"


def test_download_records_rejection_without_redirect_or_retry(tmp_path, monkeypatch):
    import requests

    m = module()
    calls = []

    def get(url, **options):
        calls.append((url, options))
        return SimpleNamespace(status_code=403, content=b"denied")

    monkeypatch.setattr(requests, "get", get)
    with pytest.raises(RuntimeError, match="http"):
        m.download("202606", tmp_path)
    assert len(calls) == 1
    assert calls[0][1]["timeout"] == (5, 20)
    assert calls[0][1]["allow_redirects"] is False
    assert (tmp_path / "202606.response").read_bytes() == b"denied"


def test_existing_output_rejected_before_reading_or_downloading(tmp_path, monkeypatch):
    m = module()
    monkeypatch.setattr(m, "OUTPUT", tmp_path)
    with pytest.raises(RuntimeError, match="already_exists"):
        m.run()
