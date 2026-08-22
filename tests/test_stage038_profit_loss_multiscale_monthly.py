from __future__ import annotations

import importlib.util
from pathlib import Path
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
        self.assertIn("name:'月成交量'", rendered)
        self.assertIn("name:'周K'", rendered)
        self.assertIn("name:'日K'", rendered)
        self.assertIn("name:'15分钟K'", rendered)
        self.assertIn("matches:'x'", rendered)
        self.assertNotIn("range:[0,mo.x.length]", rendered)

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
        calendar_dates = pd.date_range("2015-01-01", "2020-12-01", freq="MS")
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

        self.assertEqual(daily["date"].min(), pd.Timestamp("2017-07-01"))
        self.assertEqual(daily["date"].max(), pd.Timestamp("2020-01-01"))
        self.assertEqual(
            daily.loc[daily["monthly_display"].eq(1), "date"].min(),
            pd.Timestamp("2019-03-01"),
        )


if __name__ == "__main__":
    unittest.main()
