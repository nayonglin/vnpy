from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import pytest


TOOL_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import stage001_full_market_source_rebuild as stage  # noqa: E402


def test_require_authorization_rejects_implicit_network_run() -> None:
    with pytest.raises(stage.Stage001Error, match="explicit_data_rebuild_authorization_required"):
        stage.require_authorization(False)

    stage.require_authorization(True)


def test_verify_input_identities_rejects_hash_drift(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("frozen\n", encoding="utf-8")
    expected = stage.sha256_file(source)

    identities = stage.verify_input_identities({"source": source}, {"source": expected})
    assert identities["source"]["sha256"] == expected

    source.write_text("drifted\n", encoding="utf-8")
    with pytest.raises(stage.Stage001Error, match="input_sha256_drift:source"):
        stage.verify_input_identities({"source": source}, {"source": expected})


def test_serial_to_raw_frame_rejects_future_rows() -> None:
    serial = pd.DataFrame(
        {
            "datetime": pd.to_datetime(["2026-06-30", "2026-07-01"], utc=True).view("int64"),
            "open": [1.0, 2.0],
            "high": [1.0, 2.0],
            "low": [1.0, 2.0],
            "close": [1.0, 2.0],
            "volume": [10.0, 20.0],
            "open_oi": [100.0, 200.0],
            "close_oi": [101.0, 201.0],
        }
    )

    with pytest.raises(stage.Stage001Error, match="fetched_bar_after_cutoff:DCE.m2609"):
        stage.serial_to_raw_frame(
            serial,
            tq_symbol="DCE.m2609",
            source_start=pd.Timestamp("2021-01-18"),
            cutoff=pd.Timestamp("2026-06-30"),
        )


def test_serial_to_raw_frame_writes_only_exact_window() -> None:
    dates = pd.to_datetime(["2021-01-17", "2021-01-18", "2026-06-30"], utc=True)
    serial = pd.DataFrame(
        {
            "datetime": dates.view("int64"),
            "open": [1.0, 2.0, 3.0],
            "high": [1.0, 2.0, 3.0],
            "low": [1.0, 2.0, 3.0],
            "close": [1.0, 2.0, 3.0],
            "volume": [10.0, 20.0, 30.0],
            "open_oi": [100.0, 200.0, 300.0],
            "close_oi": [101.0, 201.0, 301.0],
        }
    )

    raw = stage.serial_to_raw_frame(
        serial,
        tq_symbol="DCE.m2609",
        source_start=pd.Timestamp("2021-01-18"),
        cutoff=pd.Timestamp("2026-06-30"),
    )

    assert raw["trade_date"].tolist() == ["2021-01-18", "2026-06-30"]
    assert raw["datetime"].tolist() == [
        "2021-01-18 08:00:00+08:00",
        "2026-06-30 08:00:00+08:00",
    ]


def test_output_paths_are_confined_to_line(tmp_path: Path) -> None:
    line_dir = tmp_path / "research" / "lines" / "source_rebuild"
    paths = stage.build_output_paths(line_dir)

    assert paths
    assert all(path.resolve().is_relative_to(line_dir.resolve()) for path in paths.values())
    assert len(set(paths.values())) == len(paths)


def test_continuous_symbols_are_derived_from_frozen_catalog_products() -> None:
    catalog = pd.DataFrame(
        {
            "product": ["m", "m", "SR"],
            "exchange_id": ["DCE", "DCE", "CZCE"],
            "product_vt_symbol": ["m.DCE", "m.DCE", "SR.CZCE"],
        }
    )

    assert stage.continuous_symbols_from_catalog(catalog) == ["KQ.m@CZCE.SR", "KQ.m@DCE.m"]


def test_inspect_incremental_raw_revalidates_resumable_file(tmp_path: Path) -> None:
    path = tmp_path / "DCE" / "m2609.csv.gz"
    path.parent.mkdir(parents=True)
    pd.DataFrame(
        {
            "trade_date": ["2026-06-29", "2026-06-30"],
            "datetime": ["2026-06-29 00:00:00+08:00", "2026-06-30 00:00:00+08:00"],
            "open": [2500.0, 2510.0],
            "high": [2520.0, 2530.0],
            "low": [2490.0, 2500.0],
            "close": [2510.0, 2520.0],
            "volume": [100.0, 110.0],
            "open_oi": [200.0, 210.0],
            "close_oi": [210.0, 220.0],
        }
    ).to_csv(path, index=False, compression="gzip")

    receipt = stage.inspect_incremental_raw(
        path,
        tq_symbol="DCE.m2609",
        source_start=pd.Timestamp("2021-01-18"),
        cutoff=pd.Timestamp("2026-06-30"),
    )

    assert receipt["status"] == "fetched"
    assert receipt["rows"] == 2
    assert receipt["min_date"] == "2026-06-29"
    assert receipt["max_date"] == "2026-06-30"
    assert len(receipt["sha256"]) == 64

    broken = pd.read_csv(path)
    broken.loc[len(broken)] = broken.iloc[-1]
    broken.loc[len(broken) - 1, "trade_date"] = "2026-07-01"
    broken.to_csv(path, index=False, compression="gzip")
    with pytest.raises(stage.Stage001Error, match="incremental_bar_after_cutoff:DCE.m2609"):
        stage.inspect_incremental_raw(
            path,
            tq_symbol="DCE.m2609",
            source_start=pd.Timestamp("2021-01-18"),
            cutoff=pd.Timestamp("2026-06-30"),
        )
