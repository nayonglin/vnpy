from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


TOOL_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import stage002_endofday_full_market_source_rebuild as stage2  # noqa: E402


class FakeFinished(Exception):
    pass


class FakeApi:
    def __init__(self) -> None:
        timestamp = pd.Timestamp("2026-06-30", tz="Asia/Shanghai").tz_convert("UTC").value
        self.frames = {
            "DCE.m2609": pd.DataFrame(
                {
                    "datetime": [timestamp],
                    "open": [2500.0],
                    "high": [2500.0],
                    "low": [2500.0],
                    "close": [2500.0],
                    "volume": [0.0],
                    "open_oi": [200.0],
                    "close_oi": [200.0],
                }
            ),
            "SHFE.cu2607": pd.DataFrame(
                {
                    "datetime": [timestamp],
                    "open": [100000.0],
                    "high": [100000.0],
                    "low": [100000.0],
                    "close": [100000.0],
                    "volume": [0.0],
                    "open_oi": [500.0],
                    "close_oi": [500.0],
                }
            ),
        }
        self.subscriptions: list[str] = []
        self.wait_calls = 0

    def get_kline_serial(
        self, symbol: str, *, duration_seconds: int, data_length: int
    ) -> pd.DataFrame:
        assert duration_seconds == 86_400
        assert data_length >= 1_000
        self.subscriptions.append(symbol)
        return self.frames[symbol]

    def wait_update(self) -> None:
        self.wait_calls += 1
        for frame in self.frames.values():
            frame.loc[0, "high"] += 100.0
            frame.loc[0, "low"] -= 100.0
            frame.loc[0, "close"] += 50.0
            frame.loc[0, "volume"] = 100.0
            frame.loc[0, "close_oi"] += 10.0
        raise FakeFinished()


def test_collect_finished_serials_subscribes_whole_batch_before_copying() -> None:
    api = FakeApi()
    symbols = ["DCE.m2609", "SHFE.cu2607"]

    frames = stage2.collect_finished_serials(
        api,
        symbols,
        data_length=2_000,
        source_start=pd.Timestamp("2021-01-18"),
        cutoff=pd.Timestamp("2026-06-30"),
        finished_exception=FakeFinished,
    )

    assert api.subscriptions == symbols
    assert api.wait_calls == 1
    assert frames["DCE.m2609"]["volume"].tolist() == [100.0]
    assert frames["DCE.m2609"]["close"].tolist() == [2550.0]
    assert frames["SHFE.cu2607"]["volume"].tolist() == [100.0]


def test_stage002_output_paths_are_separate_from_frozen_stage001() -> None:
    paths = stage2.build_output_paths()

    assert "stage002_endofday_source_rebuild" in str(paths["output_dir"])
    assert "stage001_full_market_source_rebuild" not in str(paths["output_dir"])
    assert len(set(paths.values())) == len(paths)
