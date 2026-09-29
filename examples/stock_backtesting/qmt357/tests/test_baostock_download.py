"""Baostock normalization and offline-failure tests; no network calls."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def downloader():
    path = Path(__file__).resolve().parents[1] / "baostock_download.py"
    spec = importlib.util.spec_from_file_location("baostock_download_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stock_raw():
    return pd.DataFrame([
        dict(date="2024-07-17", code="sh.600000", open="8.90", high="9.07", low="8.86", close="9.04", preclose="8.86", volume="10000", tradestatus="1", isST="0"),
        dict(date="2024-07-18", code="sh.600000", open="8.75", high="8.78", low="8.61", close="8.77", preclose="8.72", volume="20000", tradestatus="1", isST="0"),
    ])


def factors():
    return pd.DataFrame([
        dict(code="sh.600000", dividOperateDate="2023-07-21", backAdjustFactor="11.949786"),
        dict(code="sh.600000", dividOperateDate="2024-07-18", backAdjustFactor="12.388310"),
    ])


def dividends():
    return pd.DataFrame([
        dict(code="sh.600000", dividOperateDate="2024-07-18", dividCashPsBeforeTax="0.321", dividStocksPs="0.0", dividReserveToStockPs=""),
    ])


def test_ex_date_uses_reference_preclose_and_explicit_cash(downloader):
    # Catches prior raw close limits, future factor fill, or treating per-share cash as per-10.
    out = downloader.normalize_stock(stock_raw(), factors(), dividends())
    assert out["limit_up"].tolist() == [9.75, 9.59]
    assert out["limit_down"].tolist() == [7.97, 7.85]
    assert out["adj_factor"].tolist() == [11.949786, 12.388310]
    assert out["cash_dividend"].tolist() == [0.0, 0.321]
    assert out["split_ratio"].tolist() == [1.0, 1.0]


def test_derived_limit_rounds_decimal_half_up_without_binary_float_error(downloader):
    raw = stock_raw()
    raw["preclose"] = "0.70"
    raw["isST"] = "1"
    out = downloader.normalize_stock(raw, factors(), dividends())
    assert out["limit_down"].tolist() == [0.67, 0.67]


def test_repeated_dividend_announcement_does_not_duplicate_economic_action(downloader):
    events = pd.concat([dividends(), dividends()], ignore_index=True)
    events["dividCashStock"] = ["10派3.21元含税", "10派3.21元"]
    out = downloader.normalize_stock(stock_raw(), factors(), events)
    assert out["cash_dividend"].tolist() == [0.0, 0.321]


def test_conflicting_dividends_on_same_effective_date_fail_closed(downloader):
    events = pd.concat([dividends(), dividends()], ignore_index=True)
    events.loc[1, "dividCashPsBeforeTax"] = "0.5"
    with pytest.raises(ValueError):
        downloader.normalize_stock(stock_raw(), factors(), events)


@pytest.mark.parametrize("kind", ["missing", "duplicate", "future_date", "null_date"])
def test_historical_snapshot_must_have_300_unique_nonfuture_members(downloader, kind):
    rows = [dict(updateDate="2024-06-24", code=f"sh.{600000+i}", code_name="sample") for i in range(300)]
    frame = pd.DataFrame(rows)
    if kind == "missing":
        frame = frame.iloc[:-1]
    elif kind == "duplicate":
        frame.loc[1, "code"] = frame.loc[0, "code"]
    elif kind == "future_date":
        frame.loc[0, "updateDate"] = "2024-07-01"
    elif kind == "null_date":
        frame.loc[0, "updateDate"] = None
    with pytest.raises(ValueError):
        downloader.validate_components(frame, "2024-06-30")


def test_st_limits_and_suspension_are_not_treated_as_regular_trading(downloader):
    raw = stock_raw()
    raw.loc[0, "isST"] = "1"
    raw.loc[1, "tradestatus"] = "0"
    raw.loc[1, "volume"] = "0"
    out = downloader.normalize_stock(raw, factors(), dividends())
    assert len(out) == 1
    assert out.iloc[0]["is_st"]
    assert out.iloc[0]["limit_up"] == 9.30
    assert out.iloc[0]["limit_down"] == 8.42


@pytest.mark.parametrize("is_st", ["0", "1"])
@pytest.mark.parametrize("code", ["sz.301236", "sz.302132"])
def test_retained_301_chinext_uses_twenty_percent_even_when_st(downloader, is_st, code):
    raw = stock_raw().assign(code=code, preclose="10.00", isST=is_st)
    out = downloader.normalize_stock(raw, pd.DataFrame(), pd.DataFrame())
    assert out["limit_up"].tolist() == [12.0, 12.0]
    assert out["limit_down"].tolist() == [8.0, 8.0]


def test_outside_derived_limits_is_reported_without_removing_stock(downloader):
    panel = downloader.normalize_stock(stock_raw(), factors(), dividends())
    panel.loc[0, "high"] = 11.0
    panel.loc[0, "is_member"] = True
    audit = downloader.audit_limits(panel)
    assert len(audit) == 1
    assert audit.iloc[0]["vt_symbol"] == "600000.SSE"
    assert audit.iloc[0]["is_member"]
    assert len(panel) == 2


def test_dividends_add_both_bonus_and_capitalisation_shares(downloader):
    events = dividends()
    events.loc[0, "dividStocksPs"] = "0.2"
    events.loc[0, "dividReserveToStockPs"] = "0.3"
    out = downloader.normalize_stock(stock_raw(), factors(), events)
    assert out["split_ratio"].tolist() == [1.0, 1.5]


def test_membership_takes_effect_strictly_after_snapshot_date(downloader):
    snapshots = pd.DataFrame([
        {"snapshot_date": "2024-06-30", "code": "sh.600000"},
        {"snapshot_date": "2024-07-18", "code": "sz.000001"},
    ])
    flags = downloader.membership_flags(pd.to_datetime(["2024-06-30", "2024-07-17", "2024-07-18", "2024-07-19"]), "sh.600000", snapshots)
    assert list(flags) == [False, True, True, False]


def test_factor_future_event_does_not_backfill_earlier_day(downloader):
    out = downloader.normalize_stock(stock_raw(), factors().iloc[[1]], dividends())
    assert out["adj_factor"].tolist() == [1.0, 12.388310]


@pytest.mark.parametrize("column,value", [("isST", ""), ("preclose", "0"), ("tradestatus", "unknown")])
def test_unknown_execution_fields_fail_instead_of_defaulting(downloader, column, value):
    raw = stock_raw()
    raw.loc[0, column] = value
    with pytest.raises(ValueError):
        downloader.normalize_stock(raw, factors(), dividends())


def test_monthly_history_starts_before_price_window(downloader):
    assert downloader.snapshot_dates("20231001", "20231231") == ["2023-09-30", "2023-10-31", "2023-11-30", "2023-12-31"]


def test_result_error_does_not_become_empty_success(downloader):
    class ErrorResponse:
        error_code = "10002007"
        error_msg = "network failure"
        fields = []
    with pytest.raises(RuntimeError, match="network failure"):
        downloader.collect_response(ErrorResponse())


class LocalResponse:
    """Transport fixture with complete SDK result iteration, not a production mock."""
    error_code = "0"
    error_msg = "success"

    def __init__(self, frame):
        self.fields = list(frame.columns)
        self.rows = frame.astype(str).values.tolist()
        self.index = -1

    def next(self):
        self.index += 1
        return self.index < len(self.rows)

    def get_row_data(self):
        return self.rows[self.index]


class LocalClient:
    """Only the slow network boundary is replaced; parsing and files remain real."""
    def login(self):
        return LocalResponse(pd.DataFrame())

    def logout(self):
        return LocalResponse(pd.DataFrame())

    def query_hs300_stocks(self, date):
        rows = [dict(updateDate=date, code="sh.600000", code_name="浦发银行")]
        rows += [dict(updateDate=date, code=f"sz.{300000+i}", code_name="excluded GEM stock") for i in range(299)]
        return LocalResponse(pd.DataFrame(rows))

    def query_history_k_data_plus(self, code, **kwargs):
        return LocalResponse(stock_raw().assign(code=code))

    def query_adjust_factor(self, **kwargs):
        return LocalResponse(factors())

    def query_dividend_data(self, **kwargs):
        return LocalResponse(dividends())


def test_download_produces_isolated_complete_source_with_limitations(downloader, tmp_path, monkeypatch):
    monkeypatch.setattr(downloader, "DOWNLOADS_DIR", tmp_path / "data" / "downloads")
    output = downloader.download_panel("20240717", "20240719", client=LocalClient())
    assert output.parent.parent == downloader.DOWNLOADS_DIR
    panel = pd.read_parquet(output)
    assert len(panel) == 4
    assert set(panel["vt_symbol"]) == {"600000.SSE", "000300.SSE"}
    assert panel.loc[panel["vt_symbol"] == "600000.SSE", "is_member"].tolist() == [True, True]
    assert "derived_limits" in panel.attrs["data_limitations"]
    assert panel.attrs["historical_membership_verified"] is True
    assert (output.parent / "download_manifest.json").is_file()


def test_download_never_overwrites_an_external_manifest_symlink(downloader, tmp_path, monkeypatch):
    monkeypatch.setattr(downloader, "DOWNLOADS_DIR", tmp_path / "data" / "downloads")
    directory = downloader.DOWNLOADS_DIR / "baostock_20240717_20240719"
    directory.mkdir(parents=True)
    outside = tmp_path / "outside.json"
    outside.write_text("external original")
    (directory / "download_manifest.json").symlink_to(outside)
    with pytest.raises(ValueError):
        downloader.download_panel("20240717", "20240719", client=LocalClient())
    assert outside.read_text() == "external original"


@pytest.mark.parametrize("end", ["20260706", "20260707"])
def test_download_rejects_unimplemented_new_mainboard_st_rule_before_any_write(downloader, tmp_path, monkeypatch, end):
    monkeypatch.setattr(downloader, "DOWNLOADS_DIR", tmp_path / "data" / "downloads")
    with pytest.raises(ValueError):
        downloader.download_panel("20240717", end, client=LocalClient())
    assert not downloader.DOWNLOADS_DIR.exists()


def test_download_allows_last_day_before_new_rule_and_discloses_boundary(downloader, tmp_path, monkeypatch):
    monkeypatch.setattr(downloader, "DOWNLOADS_DIR", tmp_path / "data" / "downloads")
    output = downloader.download_panel("20240717", "20260705", client=LocalClient())
    metadata = pd.read_parquet(output).attrs
    assert metadata["derived_limit_rule_valid_before"] == "2026-07-06"
    assert metadata["derived_limit_rule_boundary_source"].startswith("https://investor.szse.cn/")
