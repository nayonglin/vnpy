"""Corporate actions: source units, fail-closed reconciliation and real parser boundary."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import requests


def test_public_module_is_importable():
    assert importlib.util.find_spec("examples.stock_backtesting.qmt357.corporate_actions") is not None


@pytest.fixture
def actions():
    name = "examples.stock_backtesting.qmt357.corporate_actions"
    assert importlib.util.find_spec(name) is not None, "corporate_actions module not implemented"
    return importlib.import_module(name)


def sina(**changes):
    row = {"公告日期": "2024-11-19", "送股": 0, "转增": 0, "派息": 12.13,
           "进度": "实施", "除权除息日": "2024-11-25", "股权登记日": "2024-11-22", "红股上市日": pd.NaT}
    row.update(changes)
    return row


def bao(**changes):
    row = {"dividOperateDate": "2024-11-25", "dividCashPsBeforeTax": "1.213",
           "dividStocksPs": "0", "dividReserveToStockPs": ""}
    row.update(changes)
    return row


def normal(actions, rows):
    return actions.normalize_sina_actions(pd.DataFrame(rows), start="20240101", end="20241231")


def merged(actions, bao_rows, sina_rows):
    return actions.merge_actions(pd.DataFrame(bao_rows), pd.DataFrame(sina_rows), start="2024-01-01", end="2024-12-31")


def test_per_ten_cash_bonus_and_capitalisation_are_converted_once(actions):
    result = normal(actions, [sina(送股=4, 转增=1, 派息=16)])
    assert list(result.columns) == ["date", "cash_dividend", "split_ratio"]
    assert result.to_dict("records") == [{"date": pd.Timestamp("2024-11-25"), "cash_dividend": 1.6, "split_ratio": 1.5}]


def test_proposals_invalid_exdates_and_out_of_window_are_not_implemented(actions):
    result = normal(actions, [sina(进度="预案"), sina(除权除息日=pd.NaT), sina(除权除息日="--"),
                              sina(除权除息日="2025-01-01"), sina(除权除息日="2023-12-31"), sina()])
    assert result["cash_dividend"].tolist() == [1.213]


def test_repeated_announcements_never_double_cash(actions):
    result = normal(actions, [sina(), sina(公告日期="2024-11-20")])
    assert result["cash_dividend"].tolist() == [1.213]


def test_same_day_conflicting_sina_events_fail(actions):
    with pytest.raises(ValueError, match="Conflicting"):
        normal(actions, [sina(), sina(派息=13)])


@pytest.mark.parametrize("value", [None, float("nan"), "broken", -1, float("inf")])
def test_implemented_cash_cannot_be_silently_zeroed(actions, value):
    with pytest.raises(ValueError):
        normal(actions, [sina(派息=value)])


def test_bao_per_share_precision_is_preserved_and_sina_only_date_is_added(actions):
    result, audit = merged(actions, [bao(dividCashPsBeforeTax="2.0001254")],
                           [sina(派息="20.0013"), sina(除权除息日="2024-06-05", 派息=30)])
    assert result["cash_dividend"].tolist() == [3.0, 2.0001254]
    assert audit["sina_only_count"] == 1
    assert audit["matched_count"] == 1
    assert audit["rounding_match_count"] == 1
    assert audit["differences"][0]["date"] == "2024-11-25"
    assert audit["differences"][0]["reason"] == "sina_display_rounding"


def test_bao_bonus_and_capitalisation_are_per_share(actions):
    result, audit = merged(actions, [bao(dividStocksPs="0.4", dividReserveToStockPs="0.1")], [])
    assert result["split_ratio"].tolist() == [1.5]
    assert audit["baostock_only_count"] == 1


def test_bao_duplicates_are_not_summed(actions):
    result, audit = merged(actions, [bao(), bao()], [sina()])
    assert result["cash_dividend"].tolist() == [1.213]
    assert audit["baostock_duplicate_count"] == 1


@pytest.mark.parametrize("cash", ["1.2131", "1.214", "1.3"])
def test_real_cash_conflict_is_not_hidden_by_broad_tolerance(actions, cash):
    with pytest.raises(ValueError, match="Conflicting"):
        merged(actions, [bao(dividCashPsBeforeTax=cash)], [sina()])


def test_tiny_difference_without_matching_display_rounding_is_rejected(actions):
    with pytest.raises(ValueError, match="Conflicting"):
        merged(actions, [bao(dividCashPsBeforeTax="2.0001254")], [sina(派息="20.0012")])


def test_duplicate_display_does_not_hide_more_precise_source_evidence(actions):
    with pytest.raises(ValueError, match="Conflicting"):
        merged(actions, [bao(dividCashPsBeforeTax="1.213001")], [sina(派息="12.13"), sina(派息="12.130000")])


def test_float_without_original_display_evidence_cannot_authorize_rounding(actions):
    with pytest.raises(ValueError, match="Conflicting"):
        merged(actions, [bao(dividCashPsBeforeTax="2.0001254")], [sina(派息=20.0013)])


def test_coarse_display_does_not_license_large_cash_difference(actions):
    with pytest.raises(ValueError, match="Conflicting"):
        merged(actions, [bao(dividCashPsBeforeTax="0.101")], [sina(派息="1")])


def test_original_display_half_step_preserves_high_precision_cash(actions):
    result, audit = merged(actions, [bao(dividCashPsBeforeTax="28.02423")], [sina(派息="280.242")])
    assert result["cash_dividend"].tolist() == [28.02423]
    assert audit["differences"][0]["display_half_step_per_share"] == "0.00005"
    assert audit["differences"][0]["cash_difference_per_share"] == "0.00003"


def test_display_matching_difference_still_has_a_small_absolute_cap(actions):
    with pytest.raises(ValueError, match="Conflicting"):
        merged(actions, [bao(dividCashPsBeforeTax="1.21306")], [sina(派息="12.13")])


def test_symmetric_display_evidence_selects_finer_sina_precision(actions):
    result, audit = merged(actions, [bao(dividCashPsBeforeTax="0.086486")], [sina(派息="0.864862")])
    assert result["cash_dividend"].tolist() == [0.0864862]
    assert audit["differences"][0]["reason"] == "baostock_display_rounding"
    assert audit["differences"][0]["selected_source"] == "sina"
    assert audit["event_sources"]["2024-11-25"] == "sina_higher_precision"


def test_rounding_requires_baostock_original_string_not_float_repr(actions):
    with pytest.raises(ValueError, match="Conflicting"):
        merged(actions, [bao(dividCashPsBeforeTax=2.0001254)], [sina(派息="20.0013")])


def test_split_conflict_is_not_inferred_from_cash_or_factor(actions):
    with pytest.raises(ValueError, match="Conflicting"):
        merged(actions, [bao(dividStocksPs="0.2")], [sina(送股=4)])


def test_conflicting_bao_duplicates_fail_even_without_sina(actions):
    with pytest.raises(ValueError, match="Conflicting"):
        merged(actions, [bao(), bao(dividCashPsBeforeTax="2")], [])


def test_unknown_bao_cash_is_recovered_from_same_date_peer_and_sina_with_audit(actions):
    raw = pd.DataFrame([bao(dividCashPsBeforeTax="", dividCashStock="10派12.13元（含税）"), bao()])
    original = raw.copy(deep=True)
    result, audit = actions.merge_actions(raw, pd.DataFrame([sina()]), start="20240101", end="20241231")
    assert result["cash_dividend"].tolist() == [1.213]
    assert audit["baostock_recovered_cash_count"] == 1
    assert audit["baostock_cash_recoveries"][0]["reason"] == "complete_peer_and_sina"
    pd.testing.assert_frame_equal(raw, original)


def test_unknown_bao_cash_can_use_unambiguous_plan_only_when_sina_agrees(actions):
    result, audit = merged(actions, [bao(dividCashPsBeforeTax="", dividCashStock="10派12.13元（含税，扣税后10.917元）")], [sina()])
    assert result["cash_dividend"].tolist() == [1.213]
    assert audit["baostock_cash_recoveries"][0]["reason"] == "explicit_plan_and_sina"


def test_unknown_bao_cash_without_sina_corroboration_is_not_zero(actions):
    with pytest.raises(ValueError, match="Unresolved"):
        merged(actions, [bao(dividCashPsBeforeTax=""), bao()], [])


def test_explicit_bao_zero_is_never_recovered_as_missing(actions):
    with pytest.raises(ValueError, match="Conflicting"):
        merged(actions, [bao(dividCashPsBeforeTax="0", dividCashStock="10派12.13元（含税）")], [sina()])


def test_unknown_cash_plan_conflicting_with_complete_peer_fails(actions):
    with pytest.raises(ValueError, match="Conflicting"):
        merged(actions, [bao(dividCashPsBeforeTax="", dividCashStock="10派15元（含税）"), bao()], [sina()])


@pytest.mark.parametrize("plan,bonus,capital", [("10转4", "0", "0.4"), ("10送2转3", "0.2", "0.3")])
def test_complete_pure_share_plan_and_sina_zero_prove_no_cash(actions, plan, bonus, capital):
    result, audit = merged(actions, [bao(dividCashPsBeforeTax="", dividCashStock=plan, dividStocksPs=bonus, dividReserveToStockPs=capital)],
                           [sina(派息="0", 送股=str(float(bonus) * 10), 转增=str(float(capital) * 10))])
    assert result["cash_dividend"].tolist() == [0]
    assert audit["baostock_cash_recoveries"][0]["reason"] == "pure_share_plan_and_sina_zero"


@pytest.mark.parametrize("plan,capital,sina_cash,sina_capital", [
    ("10转4，方案待定", "0.4", "0", "4"),
    ("10转4", "0.3", "0", "4"),
    ("10转4", "0.4", "1", "4"),
    ("10转4", "0.4", "0", "3"),
])
def test_incomplete_or_conflicting_pure_share_evidence_cannot_zero_cash(actions, plan, capital, sina_cash, sina_capital):
    with pytest.raises(ValueError):
        merged(actions, [bao(dividCashPsBeforeTax="", dividCashStock=plan, dividReserveToStockPs=capital)],
               [sina(派息=sina_cash, 转增=sina_capital)])


def test_notice_resolution_applies_only_to_verified_public_share_event(actions):
    result, audit = actions.merge_actions(
        pd.DataFrame([bao(dividOperateDate="2020-06-19", dividCashPsBeforeTax="0.14913")]),
        pd.DataFrame([sina(除权除息日="2020-06-19", 派息="1.8")]),
        start="20200101", end="20201231", symbol="600025.SSE")
    assert result["cash_dividend"].tolist() == [0.18]
    resolution = audit["action_resolutions"][0]
    assert resolution["original_cash_per_share"] == "0.14913"
    assert resolution["resolved_cash_per_share"] == "0.18"
    assert resolution["applicable_shareholder"] == "public_A_shareholder"
    assert resolution["notice_date"] == "2020-06-12"
    assert resolution["source_url"] == "https://pdf.dfcfw.com/pdf/H2_AN202006111384194389_1.pdf"
    assert resolution["pdf_sha256"] == "316b5b0cd8667807c3697319a66473571e9a0958a1058ea072ce8a7ef2abc2ca"
    assert audit["action_resolution_count"] == 1


@pytest.mark.parametrize("symbol,date,bao_cash,sina_cash", [
    (None, "2020-06-19", "0.14913", "1.8"),
    ("600026.SSE", "2020-06-19", "0.14913", "1.8"),
    ("600025.SSE", "2020-06-20", "0.14913", "1.8"),
    ("600025.SSE", "2020-06-19", "0.14914", "1.8"),
    ("600025.SSE", "2020-06-19", "0.14913", "1.9"),
])
def test_notice_resolution_never_licenses_other_identity_date_or_amount(actions, symbol, date, bao_cash, sina_cash):
    with pytest.raises(ValueError, match="Conflicting"):
        actions.merge_actions(pd.DataFrame([bao(dividOperateDate=date, dividCashPsBeforeTax=bao_cash)]),
                              pd.DataFrame([sina(除权除息日=date, 派息=sina_cash)]),
                              start="20200101", end="20201231", symbol=symbol)


@pytest.mark.parametrize("symbol,date,bao_values,sina_per_ten,want", [
    ("600803.SSE", "2024-08-01", ["0.91"], "6.6", 0.91),
    ("600803.SSE", "2025-07-22", ["1.03"], "8.1", 1.03),
    ("601966.SSE", "2024-06-14", ["0.286", "0.091"], "2.86", 0.377),
    ("601966.SSE", "2025-07-10", ["0.07"], "0.14", 0.084),
    ("600989.SSE", "2021-05-20", ["0.32091", "0.26472"], "3.2091", 0.32091),
    ("600989.SSE", "2020-06-04", ["0.27545"], "3.2091", 0.32091),
    ("600989.SSE", "2022-05-12", ["0.2648"], "3.21", 0.321),
    ("600989.SSE", "2022-12-27", ["0.1216"], "1.841", 0.1841),
    ("600989.SSE", "2026-04-28", ["0.42"], "4.921", 0.4921),
    ("600989.SSE", "2024-07-24", ["0.28"], "3.158", 0.3158),
    ("600989.SSE", "2025-05-13", ["0.409993"], "4.598", 0.4598),
    ("000333.SZSE", "2021-06-02", ["1.600585"], "16.0058", 1.6005847),
    ("000671.SZSE", "2021-07-05", ["0.380642"], "3.80643", 0.3806425),
    ("002352.SZSE", "2024-11-07", ["1.4"], "4", 1.4),
    ("002709.SZSE", "2026-04-29", ["0.3"], "2", 0.3),
    ("301308.SZSE", "2026-06-02", ["0.34676", "0.643984"], "3.4676", 0.9907442),
])
def test_notice_component_totals_only_apply_to_exact_source_evidence(actions, symbol, date, bao_values, sina_per_ten, want):
    raw = pd.DataFrame([bao(dividOperateDate=date, dividCashPsBeforeTax=value) for value in bao_values])
    original = raw.copy(deep=True)
    result, audit = actions.merge_actions(raw, pd.DataFrame([sina(除权除息日=date, 派息=sina_per_ten)]),
                                         start="20200101", end="20261231", symbol=symbol)
    assert result["cash_dividend"].tolist() == [want]
    assert audit["action_resolution_count"] == 1
    assert audit["action_resolutions"][0]["original_baostock_cash_components"] == sorted(bao_values)
    assert audit["action_resolutions"][0]["source_url"].startswith("https://")
    pd.testing.assert_frame_equal(raw, original)


def test_repeated_noticed_component_is_not_paid_twice(actions):
    result, audit = actions.merge_actions(
        pd.DataFrame([bao(dividOperateDate="2024-06-14", dividCashPsBeforeTax=value) for value in ["0.286", "0.286", "0.091"]]),
        pd.DataFrame([sina(除权除息日="2024-06-14", 派息="2.86")]),
        start="20200101", end="20261231", symbol="601966.SSE")
    assert result["cash_dividend"].tolist() == [0.377]
    assert audit["baostock_duplicate_count"] == 1


@pytest.mark.parametrize("symbol,date,values,sina_cash", [
    (None, "2024-06-14", ["0.286", "0.091"], "2.86"),
    ("601965.SSE", "2024-06-14", ["0.286", "0.091"], "2.86"),
    ("601966.SSE", "2024-06-15", ["0.286", "0.091"], "2.86"),
    ("601966.SSE", "2024-06-14", ["0.286", "0.092"], "2.86"),
    ("601966.SSE", "2024-06-14", ["0.286", "0.091"], "2.87"),
    ("601966.SSE", "2024-06-14", ["0.286"], "2.86"),
    ("601966.SSE", "2024-06-14", [], "2.86"),
    (None, "2021-05-20", ["0.32091", "0.26472"], "3.2091"),
    ("600988.SSE", "2021-05-20", ["0.32091", "0.26472"], "3.2091"),
    ("600989.SSE", "2021-05-21", ["0.32091", "0.26472"], "3.2091"),
    ("600989.SSE", "2021-05-20", ["0.32091", "0.26473"], "3.2091"),
    ("600989.SSE", "2021-05-20", ["0.32091", "0.26472"], "3.2092"),
    ("600989.SSE", "2021-05-20", ["0.32091"], "3.2091"),
    ("600989.SSE", "2026-04-28", ["0.43"], "4.921"),
    (None, "2021-06-02", ["1.600585"], "16.0058"),
    ("000333.SZSE", "2021-06-03", ["1.600585"], "16.0058"),
    ("000333.SZSE", "2021-06-02", ["1.600584"], "16.0058"),
    ("000333.SZSE", "2021-06-02", ["1.600585"], "16.0059"),
    (None, "2021-07-05", ["0.380642"], "3.80643"),
    ("000672.SZSE", "2021-07-05", ["0.380642"], "3.80643"),
    ("000671.SZSE", "2021-07-05", ["0.380643"], "3.80643"),
    (None, "2024-11-07", ["1.4"], "4"),
    ("002353.SZSE", "2024-11-07", ["1.4"], "4"),
    ("002352.SZSE", "2024-11-08", ["1.4"], "4"),
    ("002352.SZSE", "2024-11-07", ["1.5"], "4"),
    ("002352.SZSE", "2024-11-07", ["1.4"], "5"),
    (None, "2026-04-29", ["0.3"], "2"),
    ("002709.SZSE", "2026-04-30", ["0.3"], "2"),
    ("002709.SZSE", "2026-04-29", ["0.4"], "2"),
    (None, "2026-06-02", ["0.34676", "0.643984"], "3.4676"),
    ("301308.SZSE", "2026-06-03", ["0.34676", "0.643984"], "3.4676"),
    ("301308.SZSE", "2026-06-02", ["0.34676"], "3.4676"),
    ("301308.SZSE", "2026-06-02", ["0.34676", "0.643983"], "3.4676"),
])
def test_notice_component_resolution_fails_closed_on_identity_or_evidence_mismatch(actions, symbol, date, values, sina_cash):
    with pytest.raises(ValueError, match="Conflicting"):
        actions.merge_actions(pd.DataFrame([bao(dividOperateDate=date, dividCashPsBeforeTax=value) for value in values]),
                              pd.DataFrame([sina(除权除息日=date, 派息=sina_cash)]), start="20200101", end="20261231", symbol=symbol)


def test_empty_sources_have_typed_schema_and_json_serializable_semantics(actions):
    import json
    result, audit = merged(actions, [], [])
    assert list(result.columns) == ["date", "cash_dividend", "split_ratio"]
    assert pd.api.types.is_datetime64_any_dtype(result["date"])
    assert "before-tax" in audit["execution_semantics"]["cash_dividend"]
    assert "listing" in audit["execution_semantics"]["split_ratio"]
    assert "per_account_cash_cent_rounding_not_modeled" in audit["data_limitations"]
    assert json.loads(json.dumps(audit))["event_count"] == 0


def test_reversed_date_window_fails(actions):
    with pytest.raises(ValueError):
        actions.normalize_sina_actions(pd.DataFrame(), start="20250101", end="20240101")


def test_fetch_round_trips_raw_cache_without_new_request(actions, tmp_path, monkeypatch):
    source = pd.DataFrame([sina()])
    monkeypatch.setattr(actions, "_request_sina", lambda symbol: source)
    first = actions.fetch_sina_actions("000538", tmp_path)
    monkeypatch.setattr(actions, "_request_sina", lambda symbol: pytest.fail("cache should prevent network"))
    second = actions.fetch_sina_actions("000538", tmp_path)
    pd.testing.assert_frame_equal(first, second)
    assert (tmp_path / "sina_actions_000538.parquet").is_file()


def test_corrupt_cache_fails_without_refetch_or_empty_success(actions, tmp_path, monkeypatch):
    (tmp_path / "sina_actions_000538.parquet").write_bytes(b"corrupt parquet")
    monkeypatch.setattr(actions, "_request_sina", lambda symbol: pytest.fail("corrupt cache must fail closed"))
    with pytest.raises(Exception):
        actions.fetch_sina_actions("000538", tmp_path)


def test_transient_failure_retries_then_caches_real_result(actions, tmp_path, monkeypatch):
    attempts = []
    def request(symbol):
        attempts.append(symbol)
        if len(attempts) < 3:
            raise requests.Timeout("temporary")
        return pd.DataFrame([sina()])
    monkeypatch.setattr(actions, "_request_sina", request)
    monkeypatch.setattr(actions.time, "sleep", lambda delay: None)
    result = actions.fetch_sina_actions("000538", tmp_path)
    assert result["派息"].tolist() == [12.13]
    assert attempts == ["000538", "000538", "000538"]


def test_exhausted_retry_never_creates_success_cache(actions, tmp_path, monkeypatch):
    attempts = []
    def request(symbol):
        attempts.append(symbol)
        raise requests.Timeout("still down")
    monkeypatch.setattr(actions, "_request_sina", request)
    monkeypatch.setattr(actions.time, "sleep", lambda delay: None)
    with pytest.raises(requests.Timeout):
        actions.fetch_sina_actions("000538", tmp_path)
    assert len(attempts) == 3
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("frame", [pd.DataFrame(), pd.DataFrame({"unexpected": [1]})])
def test_unverified_empty_or_changed_schema_cannot_be_cached(actions, tmp_path, monkeypatch, frame):
    monkeypatch.setattr(actions, "_request_sina", lambda symbol: frame)
    with pytest.raises(ValueError):
        actions.fetch_sina_actions("000538", tmp_path)
    assert not list(tmp_path.iterdir())


def test_invalid_symbol_cannot_escape_cache_path(actions, tmp_path):
    with pytest.raises(ValueError):
        actions.fetch_sina_actions("../000538", tmp_path)


def test_http_permission_failure_is_not_retried_or_cached(actions, tmp_path, monkeypatch):
    attempts = []
    def request(symbol):
        attempts.append(symbol)
        raise requests.HTTPError("forbidden", response=SimpleNamespace(status_code=403))
    monkeypatch.setattr(actions, "_request_sina", request)
    with pytest.raises(requests.HTTPError):
        actions.fetch_sina_actions("000538", tmp_path)
    assert attempts == ["000538"]
    assert not list(tmp_path.iterdir())


def test_explicit_source_confirmed_empty_history_is_cacheable(actions, tmp_path, monkeypatch):
    source = pd.DataFrame(columns=list(sina()))
    source.attrs["source_empty_confirmed"] = True
    monkeypatch.setattr(actions, "_request_sina", lambda symbol: source)
    result = actions.fetch_sina_actions("000538", tmp_path)
    assert result.empty and result.attrs["source_empty_confirmed"]
    assert pd.read_parquet(tmp_path / "sina_actions_000538.parquet").attrs["source_empty_confirmed"]


def test_installed_sina_parser_uses_local_timeout_transport_without_global_patch(actions, tmp_path, monkeypatch):
    import akshare as ak
    original = ak.stock_history_dividend_detail.__globals__["requests"]
    columns = pd.MultiIndex.from_tuples([("分红", "每10股", name) for name in list(sina()) + ["查看详细"]])
    table = pd.DataFrame([["2024-11-19", 0, 0, 12.13, "实施", "2024-11-25", "2024-11-22", "--", "详情"]], columns=columns)
    body = "<table><tr><td>prefix</td></tr></table>" * 12 + table.to_html(index=False)
    class Session:
        def get(self, url, **kwargs):
            assert url == "https://vip.stock.finance.sina.com.cn/corp/go.php/vISSUE_ShareBonus/stockid/000538.phtml"
            assert kwargs["timeout"] == (5, 20)
            return SimpleNamespace(text=body, raise_for_status=lambda: None)
        def close(self):
            pass
    monkeypatch.setattr(requests, "Session", Session)
    result = actions.fetch_sina_actions("000538", tmp_path)
    assert result["派息"].tolist() == [12.13]
    assert str(result.iloc[0]["除权除息日"]) == "2024-11-25"
    assert ak.stock_history_dividend_detail.__globals__["requests"] is original


def test_real_parser_preserves_trailing_zero_evidence_for_conflict_gate(actions, tmp_path, monkeypatch):
    columns = pd.MultiIndex.from_tuples([("分红", "每10股", name) for name in list(sina()) + ["查看详细"]])
    table = pd.DataFrame([["2024-11-19", 0, 0, "12.130000", "实施", "2024-11-25", "2024-11-22", "--", "详情"]], columns=columns)
    body = "<table><tr><td>prefix</td></tr></table>" * 12 + table.to_html(index=False)
    class Session:
        def get(self, url, **kwargs):
            return SimpleNamespace(text=body, raise_for_status=lambda: None)
        def close(self):
            pass
    monkeypatch.setattr(requests, "Session", Session)
    raw = actions.fetch_sina_actions("000538", tmp_path)
    with pytest.raises(ValueError, match="Conflicting"):
        actions.merge_actions(pd.DataFrame([bao(dividCashPsBeforeTax="1.213001")]), raw, start="20240101", end="20241231")
    cached = pd.read_parquet(tmp_path / "sina_actions_000538.parquet")
    assert cached["_sina_cash_raw"].tolist() == ["12.130000"]
