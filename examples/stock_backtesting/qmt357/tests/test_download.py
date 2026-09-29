"""Point-in-time stock panel normalization; no network or strategy replay."""

import importlib.util

import pandas as pd
import pytest


def api():
    assert importlib.util.find_spec("examples.stock_backtesting.qmt357.download") is not None, "stock downloader not implemented"
    from examples.stock_backtesting.qmt357.download import (
        CachedTushareClient, DataSourceError, membership_flags, normalize_symbol,
    )
    return CachedTushareClient, DataSourceError, membership_flags, normalize_symbol


def raw_inputs():
    daily = pd.DataFrame({
        "ts_code": ["000001.SZ"] * 3, "trade_date": ["20240102", "20240103", "20240104"],
        "open": [10., 9.5, 9.6], "high": [10.1, 9.7, 9.8],
        "low": [9.8, 9.4, 9.5], "close": [10., 9.6, 9.7], "vol": [12., 13., 14.],
    })
    factors = daily[["ts_code", "trade_date"]].assign(adj_factor=[1., 1.1, 1.1])
    limits = daily[["ts_code", "trade_date"]].assign(up_limit=[11., 10.45, 10.56], down_limit=[9., 8.55, 8.64])
    names = pd.DataFrame({"ts_code": ["000001.SZ"] * 2, "name": ["平安银行", "ST银行"], "start_date": ["20120101", "20240103"], "end_date": ["20240102", None]})
    weights = pd.DataFrame({"trade_date": ["20231229", "20240103"], "con_code": ["000001.SZ", "000002.SZ"]})
    dividends = pd.DataFrame({"ts_code": ["000001.SZ"] * 2, "end_date": ["20231231"] * 2, "div_proc": ["实施", "预案"], "ex_date": ["20240103", "20240103"], "cash_div_tax": [.5, 99.], "stk_bo_rate": [.1, 2.], "stk_co_rate": [.2, 3.], "stk_div": [.3, 5.]})
    return daily, factors, limits, names, dividends, weights


def test_membership_snapshot_is_only_effective_strictly_after_its_date():
    _, _, flags, _ = api()
    dates = pd.to_datetime(["2023-12-29", "2024-01-02", "2024-01-03", "2024-01-04"])
    weights = raw_inputs()[-1]
    assert flags(dates, "000001.SZ", weights).tolist() == [False, True, True, False]
    assert flags(dates, "000002.SZ", weights).tolist() == [False, False, False, True]


def test_normalization_keeps_raw_prices_share_units_and_actual_events():
    _, _, _, normalize = api()
    result = normalize(*raw_inputs())
    assert result["vt_symbol"].tolist() == ["000001.SZSE"] * 3
    assert result["volume"].tolist() == [1200., 1300., 1400.]
    assert result["close"].tolist() == [10., 9.6, 9.7]
    assert result["is_member"].tolist() == [True, True, False]
    assert result["is_st"].tolist() == [False, True, True]
    assert result["cash_dividend"].tolist() == [0., .5, 0.]
    assert result["split_ratio"].tolist() == [1., 1.3, 1.]
    assert result["limit_up"].tolist() == [11., 10.45, 10.56]


@pytest.mark.parametrize("broken", ["factor", "limit", "name"])
def test_missing_historical_metadata_is_not_replaced_by_tradable_defaults(broken):
    _, _, _, normalize = api()
    args = list(raw_inputs())
    if broken == "factor":
        args[1] = args[1].iloc[1:]
    elif broken == "limit":
        args[2] = args[2].iloc[1:]
    else:
        args[3] = args[3].iloc[1:]
    with pytest.raises(ValueError, match="missing|uncovered"):
        normalize(*args)


def test_conflicting_actions_are_rejected_instead_of_double_counted():
    _, _, _, normalize = api()
    args = list(raw_inputs())
    altered = args[4].iloc[[0]].copy()
    altered["cash_div_tax"] = .6
    args[4] = pd.concat([args[4], altered], ignore_index=True)
    with pytest.raises(ValueError, match="Conflicting"):
        normalize(*args)


def test_cache_reuses_success_and_auth_failure_is_not_retried(tmp_path):
    client_class, source_error, _, _ = api()
    calls = []

    class Feed:
        def query(self, endpoint, **params):
            calls.append(endpoint)
            if endpoint == "blocked":
                raise Exception("您的token不对，请确认。")
            return pd.DataFrame({"value": [7]})

    client = client_class(Feed(), tmp_path, min_interval=0, token="test-sensitive-value")
    first = client.fetch("daily", {"ts_code": "000001.SZ"}, fields="value")
    second = client.fetch("daily", {"ts_code": "000001.SZ"}, fields="value")
    pd.testing.assert_frame_equal(first, second)
    with pytest.raises(source_error, match="authentication"):
        client.fetch("blocked", {}, fields="value")
    assert calls == ["daily", "blocked"]
    assert "test-sensitive-value" not in "".join(p.read_text() for p in tmp_path.glob("*.json"))


def test_download_source_metadata_reaches_frozen_snapshot_manifest(tmp_path, monkeypatch):
    import json
    from examples.stock_backtesting.qmt357 import data, download
    daily, factors, limits, names, dividends, _ = raw_inputs()

    class FixtureSource:
        def fetch(self, endpoint, params, fields):
            if endpoint == 'index_weight':
                # Exactly 300 historical members; original board exclusions leave one stock.
                codes = ['000001.SZ'] + [f'300{i:03d}.SZ' for i in range(299)]
                snapshot = '20231229' if params['start_date'] == '20231201' else '20240103'
                return pd.DataFrame({'index_code': ['399300.SZ'] * 300, 'con_code': codes,
                                     'trade_date': [snapshot] * 300, 'weight': [1 / 3] * 300})
            if endpoint == 'index_daily':
                return daily.assign(ts_code='000300.SH')
            return {'daily': daily, 'adj_factor': factors, 'stk_limit': limits,
                    'namechange': names, 'dividend': dividends}[endpoint].copy()

    monkeypatch.setattr(download, 'ROOT', tmp_path / 'download_root')
    monkeypatch.setattr(data, 'DATA_DIR', tmp_path / 'snapshots')
    source = download.download_panel('20240101', '20240104', client=FixtureSource())
    snapshot = data.prepare_snapshot(source, 'tushare_metadata_contract')
    manifest = json.loads((snapshot / 'manifest.json').read_text())
    assert manifest['provider'] == 'tushare'
    assert manifest['data_limitations']
    semantics = manifest['execution_semantics']
    assert semantics['cash_dividend'] == 'pretax_cash_div_tax_credited_on_ex_date_not_pay_date'
    assert semantics['stock_distribution'] == 'bonus_plus_capitalisation_on_ex_date_sellable_without_listing_delay'
    assert semantics['price_limits'] == 'tushare_stk_limit_reported_daily_limits'
    downloaded_manifest = json.loads((source.parent / 'download_manifest.json').read_text())
    assert downloaded_manifest['provider'] == manifest['provider']
    assert downloaded_manifest['data_limitations'] == manifest['data_limitations']
