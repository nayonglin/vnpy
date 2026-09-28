from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    REPO_ROOT
    / "research"
    / "lines"
    / "futures_trend_winner_trade_forensics"
    / "tools"
    / "stage038_c9_15w_big_winner_multiscale_html.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("stage038_monthly_test_target", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Stage038MonthlyChartTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_module()

    def test_monthly_window_keeps_ten_months_each_side_with_strict_ma40(self) -> None:
        dates = pd.date_range("2015-01-01", periods=84, freq="MS")
        daily = pd.DataFrame(
            {
                "date": dates,
                "open": range(1, 85),
                "high": range(2, 86),
                "low": range(0, 84),
                "close": range(1, 85),
                "volume": [100.0] * 84,
            }
        )

        monthly = self.module._add_moving_averages(self.module._monthly_from_daily(daily))
        visible = self.module._monthly_window(
            monthly,
            entry_date=pd.Timestamp("2020-01-15"),
            exit_date=pd.Timestamp("2020-01-31"),
        )

        self.assertEqual(visible["month"].iloc[0], "2019-03")
        self.assertEqual(visible["month"].iloc[-1], "2020-11")
        self.assertEqual(len(visible), 21)
        self.assertEqual(float(visible["ma40"].iloc[0]), 31.5)

    def test_monthly_ohlcv_uses_calendar_month_boundaries(self) -> None:
        daily = pd.DataFrame(
            {
                "date": pd.to_datetime(["2020-01-02", "2020-01-31", "2020-02-03"]),
                "open": [10.0, 12.0, 20.0],
                "high": [13.0, 15.0, 23.0],
                "low": [9.0, 11.0, 19.0],
                "close": [12.0, 14.0, 22.0],
                "volume": [100.0, 200.0, 300.0],
            }
        )

        monthly = self.module._monthly_from_daily(daily)

        self.assertEqual(monthly["month"].tolist(), ["2020-01", "2020-02"])
        self.assertEqual(
            monthly.loc[0, ["open", "high", "low", "close", "volume"]].tolist(),
            [10.0, 15.0, 9.0, 14.0, 300.0],
        )

    def test_trade_episode_uses_volume_weighted_exit_for_raw_price_change(self) -> None:
        closed = pd.DataFrame(
            [
                {
                    "open_trade_id": "open-1",
                    "close_trade_id": "close-1",
                    "lot_id": "lot-1",
                    "entry_date": "2021-09-01",
                    "exit_date": "2021-09-20",
                    "entry_price": 8624.0,
                    "exit_price": 11500.0,
                    "volume": 41.0,
                    "realized_pnl": 589580.0,
                    "risk_amount": 35481.4,
                    "direction": "long",
                    "exit_reason": "close-a",
                },
                {
                    "open_trade_id": "open-1",
                    "close_trade_id": "close-2",
                    "lot_id": "lot-2",
                    "entry_date": "2021-09-01",
                    "exit_date": "2021-09-27",
                    "entry_price": 8624.0,
                    "exit_price": 11100.0,
                    "volume": 41.0,
                    "realized_pnl": 507580.0,
                    "risk_amount": 35481.4,
                    "direction": "long",
                    "exit_reason": "close-b",
                },
            ]
        )

        episode = self.module._trade_episodes(closed).iloc[0]

        self.assertEqual(float(episode["weighted_exit_price"]), 11300.0)
        self.assertAlmostEqual(float(episode["price_change_pct"]), 31.02968460111317)
        self.assertEqual(episode["price_change_label"], "价格上涨 31.03%")

    def test_ten_day_bars_use_non_overlapping_fixed_calendar_buckets(self) -> None:
        daily = pd.DataFrame(
            {
                "date": pd.date_range("2020-01-01", periods=23, freq="B"),
                "trading_day_index": range(30, 53),
                "open": [float(value) for value in range(1, 24)],
                "high": [float(value + 2) for value in range(1, 24)],
                "low": [float(value - 1) for value in range(1, 24)],
                "close": [float(value + 1) for value in range(1, 24)],
                "volume": [10.0] * 23,
            }
        )

        bars = self.module._trading_day_bars_from_daily(daily, period_days=10)

        self.assertEqual(bars["day_count"].tolist(), [10, 10, 3])
        self.assertEqual(bars["period_days"].tolist(), [10, 10, 10])
        self.assertEqual(
            bars.loc[0, ["open", "high", "low", "close", "volume"]].tolist(),
            [1.0, 12.0, 0.0, 11.0, 100.0],
        )
        self.assertEqual(
            bars.loc[2, ["open", "high", "low", "close", "volume"]].tolist(),
            [21.0, 25.0, 20.0, 24.0, 30.0],
        )
        self.assertTrue(bars.loc[0, "label"].endswith("10/10日"))
        self.assertTrue(bars.loc[2, "label"].endswith("3/10日"))

    def test_thirty_day_bars_keep_the_latest_incomplete_bucket(self) -> None:
        daily = pd.DataFrame(
            {
                "date": pd.date_range("2020-01-01", periods=65, freq="B"),
                "trading_day_index": range(65),
                "open": [100.0] * 65,
                "high": [110.0] * 65,
                "low": [90.0] * 65,
                "close": [105.0] * 65,
                "volume": [1.0] * 65,
            }
        )

        bars = self.module._trading_day_bars_from_daily(daily, period_days=30)

        self.assertEqual(bars["day_count"].tolist(), [30, 30, 5])
        self.assertEqual(bars["volume"].tolist(), [30.0, 30.0, 5.0])
        self.assertTrue(bars.loc[2, "label"].endswith("5/30日"))

    def test_existing_minute_bars_rebuild_daily_with_night_session(self) -> None:
        minute = pd.DataFrame(
            {
                "bar_datetime": pd.to_datetime(
                    ["2026-02-05 21:00:00", "2026-02-06 09:00:00", "2026-02-06 14:59:00"]
                ),
                "open": [10.0, 12.0, 11.0],
                "high": [13.0, 14.0, 12.0],
                "low": [9.0, 10.0, 8.0],
                "close": [12.0, 11.0, 9.0],
                "volume": [100.0, 200.0, 300.0],
            }
        )

        daily = self.module._daily_from_minute_frame(
            minute,
            [pd.Timestamp("2026-02-05"), pd.Timestamp("2026-02-06"), pd.Timestamp("2026-02-09")],
        )

        self.assertEqual(daily["date"].tolist(), [pd.Timestamp("2026-02-06")])
        self.assertEqual(
            daily.loc[0, ["open", "high", "low", "close", "volume"]].tolist(),
            [10.0, 14.0, 8.0, 9.0, 600.0],
        )

    def test_html_renders_monthly_above_existing_three_timeframes(self) -> None:
        rendered = self.module._html([], {})

        self.assertIn("月K × 周K × 日K × 15分钟K", rendered)
        self.assertIn("name:'月K'", rendered)
        self.assertIn("volumeName:'月成交量'", rendered)
        self.assertIn("name:'周K'", rendered)
        self.assertIn("name:'日K'", rendered)
        self.assertIn("name:'15分钟K'", rendered)
        self.assertIn(".matches='x'", rendered)
        self.assertNotIn("range:[0,mo.x.length]", rendered)

    def test_html_period_picker_defaults_to_thirty_day_and_daily(self) -> None:
        rendered = self.module._html([], {})
        inputs = re.findall(
            r'<input[^>]+type="checkbox"[^>]+data-period="([^"]+)"[^>]*>',
            rendered,
        )

        self.assertEqual(inputs, ["day30", "day10", "monthly", "weekly", "daily", "intraday"])
        checked = {
            period
            for period in inputs
            if re.search(
                rf'<input[^>]+data-period="{period}"[^>]+checked(?:="checked")?[^>]*>',
                rendered,
            )
        }
        self.assertEqual(checked, {"day30", "daily"})
        for label in ["30日K", "10日K", "月K", "周K", "日K", "15分钟K"]:
            self.assertIn(label, rendered)
        self.assertIn("当前交易无15分钟数据", rendered)
        self.assertIn("selectedPeriods", rendered)

    def test_full_scope_keeps_all_episodes_but_only_tail_draws_intraday(self) -> None:
        closed = pd.read_csv(self.module.CLOSED_LOTS_PATH, encoding="utf-8-sig")

        episodes = self.module._all_trade_episodes(closed)

        self.assertEqual(len(episodes), 402)
        self.assertEqual(int(episodes["result_type"].eq("profit").sum()), 158)
        self.assertEqual(int(episodes["result_type"].eq("loss").sum()), 238)
        self.assertEqual(int(episodes["result_type"].eq("flat").sum()), 6)
        self.assertEqual(int(episodes["draw_intraday"].sum()), 73)
        self.assertEqual(int(episodes["is_tail"].sum()), 73)

    def test_html_offers_full_scope_filters_and_conditional_intraday(self) -> None:
        rendered = self.module._html([], {})

        for label in ["全部交易", "全部盈利", "全部亏损", "持平交易", "盈利尾部", "亏损尾部"]:
            self.assertIn(label, rendered)
        self.assertIn("m.draw_intraday===1", rendered)
        self.assertIn("日背景缺口", rendered)

    def test_period_coordinates_share_the_daily_context_axis(self) -> None:
        context_dates = pd.to_datetime(
            ["2020-01-02", "2020-01-31", "2020-02-03", "2020-02-28"]
        )
        periods = pd.DataFrame(
            {
                "date_start": pd.to_datetime(["2020-01-02", "2020-02-03"]),
                "date_end": pd.to_datetime(["2020-01-31", "2020-02-28"]),
            }
        )

        x, width = self.module._period_coordinates(context_dates, periods)

        self.assertEqual(x, [1.0, 3.0])
        self.assertEqual(width, [1.56, 1.56])

    def test_daily_window_is_exactly_300_trading_days_before_and_50_after(self) -> None:
        calendar_dates = pd.bdate_range("2023-01-03", periods=620)
        mapping = pd.DataFrame(
            {
                "product": ["X"] * len(calendar_dates),
                "exchange": ["SHFE"] * len(calendar_dates),
                "date": calendar_dates,
                "main_contract_vt": ["x9999.SHFE"] * len(calendar_dates),
            }
        )
        local_bars = pd.DataFrame(
            {
                "date": calendar_dates,
                "open": [10.0] * len(calendar_dates),
                "high": [11.0] * len(calendar_dates),
                "low": [9.0] * len(calendar_dates),
                "close": [10.5] * len(calendar_dates),
                "volume": [100.0] * len(calendar_dates),
            }
        )
        episode = SimpleNamespace(
            product="X.SHFE",
            vt_symbol="x9999.SHFE",
            entry_date=calendar_dates[400].date().isoformat(),
            exit_date=calendar_dates[410].date().isoformat(),
            open_trade_id="open-window",
        )

        with mock.patch.object(self.module, "_contract_daily", return_value=local_bars):
            daily, _ = self.module._context_daily(
                episode,
                mapping,
                {},
                allow_daily_download=False,
                data_end=calendar_dates[-1],
            )

        visible = daily.loc[daily["display"].eq(1)].reset_index(drop=True)
        weekly_visible = daily.loc[daily["weekly_display"].eq(1)].reset_index(drop=True)
        self.assertEqual(visible["date"].iloc[0], calendar_dates[100])
        self.assertEqual(visible["date"].iloc[-1], calendar_dates[460])
        self.assertEqual(len(visible), 361)
        self.assertLessEqual(weekly_visible["date"].iloc[0], visible["date"].iloc[0])
        self.assertGreaterEqual(weekly_visible["date"].iloc[-1], visible["date"].iloc[-1])

        # The shared monthly range must not clip the longer 300-day daily window.
        chart_episode = {
            **vars(episode), "result_rank": 1, "result_type": "profit",
            "is_tail": 0, "draw_intraday": 0, "lot_id": "lot-window", "lot_count": 1,
            "close_trade_id": "close-window", "direction": "long", "entry_price": 10.0,
            "exit_price": 11.0, "weighted_exit_price": 11.0, "price_change_pct": 10.0,
            "price_change_label": "价格上涨 10.00%", "volume": 1.0, "realized_pnl": 1.0,
            "r_multiple": float("nan"), "selection_basis": "全部交易", "holding_calendar_days": 14,
            "exit_reason": "normal", "signal": "", "profit_r_threshold": float("nan"),
            "loss_r_threshold": float("nan"),
        }
        records, _ = self.module._records(
            pd.DataFrame([chart_episode]), {"open-window": daily},
            {"open-window": [calendar_dates[400], calendar_dates[410]]},
            pd.DataFrame(columns=["vt_symbol"]),
        )
        self.assertLessEqual(records[0]["meta"]["chart_x_start"], min(records[0]["daily"]["x"]))
        self.assertGreaterEqual(records[0]["meta"]["chart_x_end"], max(records[0]["daily"]["x"]))

    def test_reuse_existing_strategy_artifacts_does_not_run_strategy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            closed_path = root / "closed.csv"
            selected_path = root / "selected.csv"
            daily_path = root / "daily.csv"
            summary_path = root / "summary.json"
            pd.DataFrame([{"winner": 1, "lot_id": "lot-1"}]).to_csv(closed_path, index=False)
            pd.DataFrame(
                [
                    {
                        "open_trade_id": "open-1",
                        "result_type": "profit",
                        "entry_date": "2020-01-15",
                        "exit_date": "2020-01-31",
                    }
                ]
            ).to_csv(selected_path, index=False)
            pd.DataFrame([{"date": "2020-01-31", "account_equity": 100_000.0}]).to_csv(
                daily_path,
                index=False,
            )
            summary_path.write_text(
                '{"backtest_metrics":{"total_return_pct":1.0},"strategy_profile":"frozen"}\n',
                encoding="utf-8",
            )

            with mock.patch.object(
                self.module,
                "_run_current_c9",
                side_effect=AssertionError("strategy must not run"),
            ):
                combined, closed, selected, spec, prior_summary = self.module._strategy_inputs(
                    pd.Timestamp("2026-08-12"),
                    reuse_existing=True,
                    closed_path=closed_path,
                    selected_path=selected_path,
                    daily_path=daily_path,
                    summary_path=summary_path,
                )

            self.assertIsNone(spec)
            self.assertEqual(combined["account_equity"].tolist(), [100_000.0])
            self.assertEqual(closed["lot_id"].tolist(), ["lot-1"])
            self.assertEqual(selected["open_trade_id"].tolist(), ["open-1"])
            self.assertEqual(prior_summary["strategy_profile"], "frozen")

    def test_offline_context_skips_missing_hidden_warmup_without_downloading(self) -> None:
        calendar_dates = pd.bdate_range("2015-01-01", "2020-12-01")
        mapping = pd.DataFrame(
            {
                "product": ["X"] * len(calendar_dates),
                "exchange": ["SHFE"] * len(calendar_dates),
                "date": calendar_dates,
                "main_contract_vt": ["x2401.SHFE"] * len(calendar_dates),
            }
        )
        local_dates = calendar_dates[calendar_dates >= pd.Timestamp("2017-07-01")]
        local_bars = pd.DataFrame(
            {
                "date": local_dates,
                "open": [10.0] * len(local_dates),
                "high": [11.0] * len(local_dates),
                "low": [9.0] * len(local_dates),
                "close": [10.5] * len(local_dates),
                "volume": [100.0] * len(local_dates),
            }
        )
        episode = SimpleNamespace(
            product="X.SHFE",
            vt_symbol="x9999.SHFE",
            entry_date="2020-01-01",
            exit_date="2020-01-01",
            open_trade_id="open-1",
        )

        with (
            mock.patch.object(self.module, "_contract_daily", return_value=local_bars),
            mock.patch.object(
                self.module,
                "_fetch_daily_tq",
                side_effect=AssertionError("offline rebuild must not download daily bars"),
            ),
        ):
            daily, _ = self.module._context_daily(
                episode,
                mapping,
                {},
                allow_daily_download=False,
                data_end=pd.Timestamp("2020-01-01"),
            )

        self.assertEqual(daily["date"].min(), pd.Timestamp("2017-07-03"))
        self.assertEqual(daily["date"].max(), pd.Timestamp("2020-01-01"))
        self.assertEqual(
            daily.loc[daily["monthly_display"].eq(1), "date"].min(),
            pd.Timestamp("2019-03-01"),
        )

    def test_full_scope_can_disclose_and_skip_noncritical_daily_gap(self) -> None:
        calendar_dates = pd.date_range("2017-01-01", "2020-01-01", freq="MS")
        mapping = pd.DataFrame(
            {
                "product": ["X"] * len(calendar_dates),
                "exchange": ["SHFE"] * len(calendar_dates),
                "date": calendar_dates,
                "main_contract_vt": ["x2401.SHFE"] * len(calendar_dates),
            }
        )
        missing_day = pd.Timestamp("2019-12-01")
        local_dates = calendar_dates[calendar_dates != missing_day]
        local_bars = pd.DataFrame(
            {
                "date": local_dates,
                "open": [10.0] * len(local_dates),
                "high": [11.0] * len(local_dates),
                "low": [9.0] * len(local_dates),
                "close": [10.5] * len(local_dates),
                "volume": [100.0] * len(local_dates),
            }
        )
        episode = SimpleNamespace(
            product="X.SHFE",
            vt_symbol="x9999.SHFE",
            entry_date="2020-01-01",
            exit_date="2020-01-01",
            open_trade_id="open-gap",
        )

        with (
            mock.patch.object(self.module, "_contract_daily", return_value=local_bars),
            mock.patch.object(self.module, "_daily_from_existing_minute_files", return_value=pd.DataFrame()),
            mock.patch.object(
                self.module,
                "_fetch_daily_tq",
                side_effect=AssertionError("offline rebuild must not download daily bars"),
            ),
        ):
            daily, _ = self.module._context_daily(
                episode,
                mapping,
                {},
                allow_daily_download=False,
                allow_noncritical_daily_gaps=True,
                data_end=pd.Timestamp("2020-01-01"),
            )

        self.assertNotIn(missing_day, set(daily["date"]))
        self.assertEqual(daily.attrs["missing_context_dates"], ["2019-12-01"])

    def test_stage037c_source_loader_reads_only_the_frozen_c_arm(self) -> None:
        loader = getattr(self.module, "_load_stage037c_frozen_source", None)
        self.assertIsNotNone(loader)

        curve, trades, metrics, provenance = loader()

        self.assertEqual(len(trades), 733)
        self.assertEqual(set(trades["experiment_arm"]), {"C"})
        self.assertEqual(trades["date"].min(), "2018-01-15")
        self.assertEqual(trades["date"].max(), "2026-08-19")
        self.assertEqual(set(curve["experiment_arm"]), {"C"})
        self.assertEqual(float(metrics["end_equity"]), 17_051_717.30)
        self.assertEqual(
            provenance["source_commit"],
            "ec4f1a39b48ed168662059aea7a98030a01a3ccf",
        )

    def test_top10_source_selects_only_t10_and_reconstructs_all_completed_entries(self) -> None:
        loader = getattr(self.module, "_load_stage061_top10_frozen_source", None)
        self.assertIsNotNone(loader, "Top10 frozen source loader is missing")
        curve, trades, metrics, provenance = loader()
        self.assertEqual(set(trades["experiment_arm"]), {"T10"})
        self.assertEqual(len(trades), 798)
        self.assertEqual(len(curve), 2101)
        self.assertEqual(set(curve["experiment_arm"]), {"T10"})
        self.assertEqual(curve["date"].iloc[0], "2018-01-02")
        self.assertEqual(curve["date"].iloc[-1], "2026-08-28")
        self.assertAlmostEqual(float(curve["account_equity"].iloc[-1]), 21_870_488.80)
        self.assertAlmostEqual(float(metrics["end_equity"]), 21_870_488.80)
        self.assertEqual(provenance["source_commit"], "6750783fe7aab92e6dbdd6820fa212e2e53ea353")
        closed = self.module._closed_lots_from_trade_ledger(
            trades, sizes=self.module.s513._metadata()["sizes"],
            allow_residual_open=True, source_prefix="stage061_top10",
        )
        self.assertEqual(len(closed), 406)
        self.assertEqual(closed["open_trade_id"].nunique(), 391)
        self.assertTrue(closed["lot_id"].str.startswith("stage061_top10.").all())
        self.assertEqual(closed.attrs["residual_open_positions"], [
            {"vt_symbol": "si2611.GFEX", "direction": "long", "volume": 460.0},
        ])

    def test_top10_source_rejects_an_incomplete_trade_ledger(self) -> None:
        loader = getattr(self.module, "_load_stage061_top10_frozen_source", None)
        self.assertIsNotNone(loader, "Top10 frozen source loader is missing")
        read_csv = self.module._read_git_csv
        def incomplete(commit, path):
            frame, digest = read_csv(commit, path)
            if path.endswith("stage061_trades.csv"):
                frame = frame.drop(frame.index[frame["experiment_arm"].eq("T10")][0])
            return frame, digest
        with mock.patch.object(self.module, "_read_git_csv", side_effect=incomplete):
            with self.assertRaisesRegex(RuntimeError, "Frozen Top10 evidence mismatch"):
                loader()

    def test_top10_cli_refuses_tail_scope_before_creating_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "atlas"
            with (
                mock.patch.object(sys, "argv", ["atlas", "--source-profile", "stage061_top10", "--episode-scope", "tail"]),
                mock.patch.object(self.module, "STAGE061_TOP10_OUTPUT_DIR", output),
                self.assertRaisesRegex(RuntimeError, "only in full-cycle scope"),
            ):
                self.module.main()
            self.assertFalse(output.exists())

    def test_frozen_trade_ledger_fifo_closes_partial_long_and_short_positions(self) -> None:
        builder = getattr(self.module, "_closed_lots_from_trade_ledger", None)
        self.assertIsNotNone(builder)
        trades = pd.DataFrame(
            [
                {
                    "trade_id": "open-long",
                    "datetime": "2024-01-02 09:00:00+08:00",
                    "date": "2024-01-02",
                    "vt_symbol": "x2405.SHFE",
                    "direction": "多",
                    "offset": "开",
                    "price": 100.0,
                    "volume": 10.0,
                    "exit_reason": "",
                },
                {
                    "trade_id": "close-long-a",
                    "datetime": "2024-01-03 09:00:00+08:00",
                    "date": "2024-01-03",
                    "vt_symbol": "x2405.SHFE",
                    "direction": "空",
                    "offset": "平",
                    "price": 110.0,
                    "volume": 4.0,
                    "exit_reason": "partial",
                },
                {
                    "trade_id": "close-long-b",
                    "datetime": "2024-01-04 09:00:00+08:00",
                    "date": "2024-01-04",
                    "vt_symbol": "x2405.SHFE",
                    "direction": "空",
                    "offset": "平",
                    "price": 120.0,
                    "volume": 6.0,
                    "exit_reason": "final",
                },
                {
                    "trade_id": "open-short",
                    "datetime": "2024-01-05 09:00:00+08:00",
                    "date": "2024-01-05",
                    "vt_symbol": "y2405.DCE",
                    "direction": "空",
                    "offset": "开",
                    "price": 200.0,
                    "volume": 2.0,
                    "exit_reason": "",
                },
                {
                    "trade_id": "close-short",
                    "datetime": "2024-01-08 09:00:00+08:00",
                    "date": "2024-01-08",
                    "vt_symbol": "y2405.DCE",
                    "direction": "多",
                    "offset": "平",
                    "price": 180.0,
                    "volume": 2.0,
                    "exit_reason": "short-close",
                },
            ]
        )

        closed = builder(trades, sizes={"x2405.SHFE": 1, "y2405.DCE": 1})

        self.assertEqual(closed["open_trade_id"].tolist(), ["open-long", "open-long", "open-short"])
        self.assertEqual(closed["direction"].tolist(), ["long", "long", "short"])
        self.assertEqual(closed["volume"].tolist(), [4.0, 6.0, 2.0])
        self.assertEqual(closed["realized_pnl"].tolist(), [40.0, 120.0, 40.0])
        self.assertTrue(closed["risk_amount"].isna().all())
        self.assertTrue(closed["r_multiple"].isna().all())

    def test_research_html_discloses_stage037c_identity_and_pnl_sorting(self) -> None:
        output = self.module._html(
            [],
            {
                "episode_scope": "all",
                "chart_episodes": 360,
                "intraday_draw_episodes": 0,
                "page_title": "Stage037 C研究版全周期逐笔复盘",
                "source_label": "Stage037 C研究版",
                "source_version": "stage037_C_long_short_mirror_hard_block",
                "source_warning": "研究版未晋级，不是当前正式策略。",
                "rank_basis": "realized_pnl",
            },
        )

        self.assertIn("Stage037 C研究版全周期逐笔复盘", output)
        self.assertIn("Stage037 C研究版", output)
        self.assertIn("研究版未晋级，不是当前正式策略。", output)
        self.assertIn("净利润绝对值从大到小", output)
        self.assertNotIn("数据：当前正式 Stage847-C9-15w", output)

    def test_research_html_offers_signed_price_change_sorting(self) -> None:
        output = self.module._html(
            [],
            {
                "episode_scope": "all",
                "rank_basis": "realized_pnl",
            },
        )

        self.assertIn("价格涨跌百分比从大到小", output)
        self.assertIn("价格涨跌百分比从小到大", output)
        self.assertIn("sortMode==='price_desc'", output)
        self.assertIn("Number(a.meta.price_change_pct)", output)
        self.assertIn("?'涨跌幅排序':", output)


if __name__ == "__main__":
    unittest.main()
