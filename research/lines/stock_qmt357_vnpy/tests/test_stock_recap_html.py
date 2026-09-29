"""Display-only stock adapter contracts; no backtest or futures imports."""
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

LINE = Path(__file__).resolve().parents[1]
MODULE = LINE / "tools/stage014_stock_recap_html.py"


@pytest.fixture
def adapter():
    class LazyAdapter:
        def __getattr__(self, name):
            assert MODULE.exists(), "stock recap adapter has not been implemented"
            spec = importlib.util.spec_from_file_location("stock_recap", MODULE)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return getattr(module, name)
    return LazyAdapter()


def ledger():
    trades = pd.DataFrame([
        dict(date="2020-01-06T00:00:00", vt_symbol="600000.SSE", direction="buy",
             price=10.01, shares=100, turnover=1001., commission=5., slippage=1.,
             signal_date="2020-01-03", reason="reversal", cash_after=198994.),
        dict(date="2020-01-08T00:00:00", vt_symbol="600000.SSE", direction="sell",
             price=9.99, shares=100, turnover=999., commission=5., slippage=1.,
             signal_date="2020-01-07", reason="stop_loss", cash_after=200008.),
    ])
    trips = pd.DataFrame([dict(vt_symbol="600000.SSE", entry_date="2020-01-06",
                              exit_date="2020-01-08", entry_cost=1006., proceeds=994.,
                              dividends=20., net_pnl=8.)])
    return trades, trips


def bars():
    dates = pd.bdate_range("2019-01-01", "2020-03-31")
    return pd.DataFrame(dict(date=dates, vt_symbol="600000.SSE", open=10., high=11.,
                             low=9., close=np.arange(len(dates)) / 100 + 10,
                             volume=10000., adj_factor=1., cash_dividend=0., split_ratio=1.))


def test_renderer_loading_does_not_import_futures_or_change_cwd(adapter):
    before = set(sys.modules)
    cwd = Path.cwd()
    renderer = adapter.load_renderer()
    result = renderer._add_moving_averages(pd.DataFrame({"close": [1., 2., 3., 4., 5.]}))
    assert result.ma5.iloc[-1] == 3.
    assert Path.cwd() == cwd
    assert not any(name.startswith(("vnpy", "tqsdk", "qmt_roll", "analyze_qmt"))
                   for name in set(sys.modules) - before)


def test_pairing_preserves_dividends_fees_and_execution_prices(adapter):
    result = adapter.pair_episodes(*ledger())
    row = result.iloc[0]
    assert row.realized_pnl == 8.
    assert row.dividends == 20.
    assert row.entry_price == 10.01
    assert row.exit_price == 9.99
    assert row.volume == 100
    assert row.result_type == "profit"  # Price fell, but dividend made net profit.
    assert row.price_change_pct == pytest.approx(-0.1998001998)
    assert np.isnan(row.r_multiple)  # Never invent a futures risk multiple.


@pytest.mark.parametrize("kind", ["duplicate_fill", "unpaired_fill", "wrong_pnl", "wrong_shares", "wrong_cost"])
def test_pairing_rejects_inconsistent_ledger(adapter, kind):
    trades, trips = ledger()
    if kind == "duplicate_fill":
        trades = pd.concat([trades, trades.iloc[[0]]], ignore_index=True)
    elif kind == "unpaired_fill":
        trades.loc[2] = trades.iloc[0]
        trades.loc[2, "vt_symbol"] = "600001.SSE"
    elif kind == "wrong_pnl":
        trips.loc[0, "net_pnl"] = 9.
    elif kind == "wrong_shares":
        trades.loc[1, "shares"] = 200
    else:
        trips.loc[0, "entry_cost"] = 1007.
    with pytest.raises(ValueError):
        adapter.pair_episodes(trades, trips)


def test_missing_minute_and_short_real_history_are_disclosed(adapter):
    episodes = adapter.pair_episodes(*ledger())
    records, manifest = adapter.build_records(episodes, bars(), adapter.load_renderer())
    rec = records[0]
    assert rec["intraday"]["x"] == []
    assert rec["meta"]["draw_intraday"] == 0
    assert rec["meta"]["entry_marker_price"] == 10.01
    assert rec["meta"]["exit_marker_price"] == 9.99
    assert rec["meta"]["pre_daily_bars"] < 300
    assert rec["meta"]["post_daily_bars"] == 50
    assert rec["meta"]["daily_start"] == "2019-01-01"
    assert rec["meta"]["price_basis"] == "unadjusted"
    assert manifest.bars_15m.tolist() == [0]
    assert manifest.pre_history_truncated.tolist() == [True]


def test_full_history_is_used_for_ma_warmup_before_visible_window(adapter):
    panel = bars()
    early = pd.bdate_range("2017-01-02", "2018-12-31")
    extra = pd.DataFrame(dict(date=early, vt_symbol="600000.SSE", open=10., high=11.,
                             low=9., close=10., volume=10000.))
    panel = pd.concat([extra, panel], ignore_index=True)
    records, _ = adapter.build_records(adapter.pair_episodes(*ledger()), panel, adapter.load_renderer())
    rec = records[0]
    assert rec["meta"]["pre_daily_bars"] == 300
    assert rec["daily"]["ma40"][0] == 10.
    assert len(rec["daily"]["date"]) == 353  # 300 before, 3 holding, 50 after.
    assert rec["meta"]["chart_x_start"] <= rec["daily"]["x"][0]
    assert rec["meta"]["chart_x_end"] >= rec["daily"]["x"][-1]


def test_missing_entry_bar_is_rejected_not_forward_filled(adapter):
    panel = bars()
    panel = panel[panel.date.ne(pd.Timestamp("2020-01-06"))]
    with pytest.raises((ValueError, RuntimeError)):
        adapter.build_records(adapter.pair_episodes(*ledger()), panel, adapter.load_renderer())


@pytest.mark.parametrize("state", ["RUNNING", "FAILED", "incomplete", "open"])
def test_incomplete_or_residual_position_bundle_is_rejected(adapter, tmp_path, state):
    manifest = dict(status="COMPLETE", complete_period_result=True)
    summary = dict(open_positions=0)
    if state in ("RUNNING", "FAILED"):
        manifest["status"] = state
    elif state == "incomplete":
        manifest["complete_period_result"] = False
    else:
        summary["open_positions"] = 1
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "summary.json").write_text(json.dumps(summary))
    with pytest.raises(ValueError, match="complete|residual"):
        adapter.verify_bundle(tmp_path, tmp_path / "absent.parquet")


def test_output_is_scoped_to_stock_line_and_never_overwrites(adapter, tmp_path):
    with pytest.raises(ValueError):
        adapter.validate_output_path(tmp_path / "futures")
    with pytest.raises(ValueError):
        adapter.validate_output_path(LINE / "outputs")
    target = LINE / "outputs/unit-test-existing-do-not-write"
    target.mkdir(parents=True, exist_ok=False)
    try:
        with pytest.raises(FileExistsError):
            adapter.validate_output_path(target)
    finally:
        target.rmdir()


def test_stock_html_uses_canonical_charts_with_stock_units_and_dividends(adapter):
    renderer = adapter.load_renderer()
    records, _ = adapter.build_records(adapter.pair_episodes(*ledger()), bars(), renderer)
    summary = dict(page_title="股票复盘测试", episode_scope="all", source_label="冻结股票",
                   source_version="test", rank_basis="realized_pnl", source_warning="未复权",
                   coverage_note="没有分钟数据。", footer_scope="1笔；",
                   frozen_metrics={"end_equity": 200008., "total_return_pct": .004,
                                   "max_drawdown_pct": 0., "sharpe": 0., "total_slippage": 2.,
                                   "total_commission": 10., "total_trade_count": 2,
                                   "closed_round_trips": 1, "win_rate_pct": 100.})
    page = adapter.render_stock_html(records, summary, renderer)
    from html.parser import HTMLParser

    class Page(HTMLParser):
        def __init__(self):
            super().__init__()
            self.checked = []
            self.text = []
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "input" and "checked" in attrs:
                self.checked.append(attrs.get("data-period"))
        def handle_data(self, text):
            self.text.append(text)

    parsed = Page()
    parsed.feed(page)
    assert parsed.checked == ["day30", "daily"]
    text = " ".join(parsed.text)
    assert "股数" in text and "分红" in text and "200,008" in text
    assert "主力代理" not in text and "平仓lot" not in text
