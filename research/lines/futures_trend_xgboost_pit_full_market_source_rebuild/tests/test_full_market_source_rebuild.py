from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import pytest


TOOL_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import full_market_source_rebuild as core  # noqa: E402


def _catalog_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "instrument_id": "DCE.m2605",
                "ins_class": "FUTURE",
                "exchange_id": "DCE",
                "product_id": "m",
                "expired": True,
                "expire_datetime": pd.Timestamp("2026-05-15", tz="Asia/Shanghai").timestamp(),
                "delivery_year": 2026,
                "delivery_month": 5,
                "price_tick": 1.0,
                "volume_multiple": 10.0,
            },
            {
                "instrument_id": "DCE.m2609",
                "ins_class": "FUTURE",
                "exchange_id": "DCE",
                "product_id": "m",
                "expired": False,
                "expire_datetime": pd.Timestamp("2026-09-15", tz="Asia/Shanghai").timestamp(),
                "delivery_year": 2026,
                "delivery_month": 9,
                "price_tick": 1.0,
                "volume_multiple": 10.0,
            },
            {
                "instrument_id": "CZCE.SR609",
                "ins_class": "FUTURE",
                "exchange_id": "CZCE",
                "product_id": "SR",
                "expired": False,
                "expire_datetime": pd.Timestamp("2026-09-15", tz="Asia/Shanghai").timestamp(),
                "delivery_year": 2026,
                "delivery_month": 9,
                "price_tick": 1.0,
                "volume_multiple": 10.0,
            },
            {
                "instrument_id": "CFFEX.IF2609",
                "ins_class": "FUTURE",
                "exchange_id": "CFFEX",
                "product_id": "IF",
                "expired": False,
                "expire_datetime": pd.Timestamp("2026-09-18", tz="Asia/Shanghai").timestamp(),
                "delivery_year": 2026,
                "delivery_month": 9,
                "price_tick": 0.2,
                "volume_multiple": 300.0,
            },
            {
                "instrument_id": "DCE.l2602F",
                "ins_class": "FUTURE",
                "exchange_id": "DCE",
                "product_id": "l",
                "expired": True,
                "expire_datetime": pd.Timestamp("2026-02-27", tz="Asia/Shanghai").timestamp(),
                "delivery_year": 2026,
                "delivery_month": 2,
                "price_tick": 1.0,
                "volume_multiple": 5.0,
            },
        ]
    )


def test_normalise_catalog_keeps_asof_expired_and_live_commodity_contracts() -> None:
    catalog = core.normalise_catalog(
        _catalog_rows(),
        catalog_as_of=pd.Timestamp("2026-06-30"),
        source_start=pd.Timestamp("2021-01-18"),
        cutoff=pd.Timestamp("2026-06-30"),
    )

    assert catalog["tq_symbol"].tolist() == ["CZCE.SR609", "DCE.m2605", "DCE.m2609"]
    assert catalog.set_index("tq_symbol").loc["DCE.m2605", "expired_asof"]
    assert not catalog.set_index("tq_symbol").loc["DCE.m2609", "expired_asof"]
    assert catalog.set_index("tq_symbol").loc["CZCE.SR609", "vt_symbol"] == "SR609.CZCE"
    assert set(catalog["product_vt_symbol"]) == {"m.DCE", "SR.CZCE"}


def test_normalise_catalog_rejects_catalog_observed_after_cutoff() -> None:
    with pytest.raises(core.SourceContractError, match="catalog_asof_after_cutoff"):
        core.normalise_catalog(
            _catalog_rows(),
            catalog_as_of=pd.Timestamp("2026-07-01"),
            source_start=pd.Timestamp("2021-01-18"),
            cutoff=pd.Timestamp("2026-06-30"),
        )


def test_normalise_catalog_still_rejects_unknown_nonstandard_symbol_shape() -> None:
    raw = _catalog_rows().copy()
    raw.loc[raw["instrument_id"].eq("DCE.m2609"), "instrument_id"] = "DCE.m26X"

    with pytest.raises(core.SourceContractError, match="catalog_contract_symbol_invalid:DCE.m26X"):
        core.normalise_catalog(
            raw,
            catalog_as_of=pd.Timestamp("2026-06-30"),
            source_start=pd.Timestamp("2021-01-18"),
            cutoff=pd.Timestamp("2026-06-30"),
        )


def test_calendar_to_mapping_nulls_unresolvable_vendor_contract_without_fallback() -> None:
    catalog = core.normalise_catalog(
        _catalog_rows(),
        catalog_as_of=pd.Timestamp("2026-06-30"),
        source_start=pd.Timestamp("2021-01-18"),
        cutoff=pd.Timestamp("2026-06-30"),
    )
    calendar = pd.DataFrame(
        {
            "date": ["2026-06-29", "2026-06-30"],
            "trading": [True, True],
            "KQ.m@DCE.m": ["DCE.m2605", "DCE.m2609"],
            "KQ.m@CZCE.SR": ["CZCE.SR609", "CZCE.SR609"],
        }
    )

    mapping = core.calendar_to_mapping(
        calendar,
        catalog,
        source_start=pd.Timestamp("2021-01-18"),
        cutoff=pd.Timestamp("2026-06-30"),
    )

    assert mapping[["date", "continuous_symbol_vt", "main_contract_vt"]].to_dict("records") == [
        {
            "date": pd.Timestamp("2026-06-29"),
            "continuous_symbol_vt": "SR.CZCE",
            "main_contract_vt": "SR609.CZCE",
        },
        {
            "date": pd.Timestamp("2026-06-29"),
            "continuous_symbol_vt": "m.DCE",
            "main_contract_vt": "m2605.DCE",
        },
        {
            "date": pd.Timestamp("2026-06-30"),
            "continuous_symbol_vt": "SR.CZCE",
            "main_contract_vt": "SR609.CZCE",
        },
        {
            "date": pd.Timestamp("2026-06-30"),
            "continuous_symbol_vt": "m.DCE",
            "main_contract_vt": "m2609.DCE",
        },
    ]

    broken = calendar.copy()
    broken.loc[1, "KQ.m@DCE.m"] = "DCE.m2701"
    unresolved = core.calendar_to_mapping(
        broken,
        catalog,
        source_start=pd.Timestamp("2021-01-18"),
        cutoff=pd.Timestamp("2026-06-30"),
    )
    row = unresolved[
        unresolved["date"].eq(pd.Timestamp("2026-06-30"))
        & unresolved["continuous_symbol_vt"].eq("m.DCE")
    ].iloc[0]
    assert row["calendar_main_contract_tq"] == "DCE.m2701"
    assert row["main_contract_tq"] == ""
    assert row["main_contract_vt"] == ""
    assert row["mapping_resolution"] == "unresolved_not_in_asof_catalog"


def test_build_acquisition_plan_reuses_complete_expired_and_fetches_live_or_missing_required() -> None:
    catalog = core.normalise_catalog(
        _catalog_rows(),
        catalog_as_of=pd.Timestamp("2026-06-30"),
        source_start=pd.Timestamp("2021-01-18"),
        cutoff=pd.Timestamp("2026-06-30"),
    )
    inventory = pd.DataFrame(
        [
            {
                "tq_symbol": "DCE.m2605",
                "status": "available",
                "rows": 300,
                "min_date": "2025-03-01",
                "max_date": "2026-05-14",
                "path": "/archive/DCE/m2605.csv",
                "sha256": "a" * 64,
            },
            {
                "tq_symbol": "CZCE.SR609",
                "status": "missing",
                "rows": 0,
                "min_date": "",
                "max_date": "",
                "path": "",
                "sha256": "",
            },
        ]
    )

    plan = core.build_acquisition_plan(
        catalog,
        inventory,
        required_contracts={"DCE.m2605", "DCE.m2609", "CZCE.SR609"},
        source_start=pd.Timestamp("2021-01-18"),
        cutoff=pd.Timestamp("2026-06-30"),
    ).set_index("tq_symbol")

    assert plan.loc["DCE.m2605", "action"] == "reuse_archive"
    assert plan.loc["DCE.m2609", "action"] == "fetch_asof_history"
    assert plan.loc["CZCE.SR609", "action"] == "fetch_asof_history"
    assert plan.loc["DCE.m2609", "fetch_end"] == pd.Timestamp("2026-06-30")


def test_normalise_raw_bars_clips_exact_range_and_uses_open_oi() -> None:
    raw = pd.DataFrame(
        {
            "trade_date": ["2021-01-15", "2021-01-18", "2026-06-30", "2026-07-01"],
            "open": [1.0, 2.0, 3.0, 4.0],
            "high": [1.0, 2.0, 3.0, 4.0],
            "low": [1.0, 2.0, 3.0, 4.0],
            "close": [1.0, 2.0, 3.0, 4.0],
            "volume": [1.0, 2.0, 3.0, 4.0],
            "open_oi": [10.0, 20.0, 30.0, 40.0],
            "close_oi": [11.0, 21.0, 31.0, 41.0],
        }
    )

    bars, diagnostics = core.normalise_raw_bars(
        raw,
        tq_symbol="DCE.m2609",
        source_start=pd.Timestamp("2021-01-18"),
        cutoff=pd.Timestamp("2026-06-30"),
        source_kind="incremental_tqsdk",
    )

    assert bars["datetime"].tolist() == [pd.Timestamp("2021-01-18"), pd.Timestamp("2026-06-30")]
    assert bars["open_interest"].tolist() == [20.0, 30.0]
    assert diagnostics == {
        "source_rows": 4,
        "rows_before_start_dropped": 1,
        "rows_after_cutoff_dropped": 1,
        "normalised_rows": 2,
    }


def test_merge_bar_sources_rejects_conflicting_duplicate_values() -> None:
    base = pd.DataFrame(
        {
            "datetime": [pd.Timestamp("2026-06-30")],
            "symbol": ["m2609"],
            "exchange": ["DCE"],
            "interval": ["d"],
            "close_price": [2500.0],
            "volume": [100.0],
            "open_interest": [200.0],
            "source_kind": ["archive_tqsdk"],
        }
    )
    conflicting = base.copy()
    conflicting.loc[0, "close_price"] = 2501.0
    conflicting.loc[0, "source_kind"] = "incremental_tqsdk"

    with pytest.raises(core.SourceContractError, match="bar_duplicate_conflict"):
        core.merge_bar_sources([base, conflicting])


def test_invariant_product_metadata_excludes_products_with_changed_specs() -> None:
    catalog = core.normalise_catalog(
        _catalog_rows(),
        catalog_as_of=pd.Timestamp("2026-06-30"),
        source_start=pd.Timestamp("2021-01-18"),
        cutoff=pd.Timestamp("2026-06-30"),
    )
    changed = catalog.copy()
    changed.loc[changed["tq_symbol"].eq("DCE.m2609"), "volume_multiple"] = 20.0

    metadata, diagnostics = core.build_invariant_product_metadata(changed)

    assert metadata["vt_symbol"].tolist() == ["SR.CZCE"]
    assert diagnostics["variant_products"] == ["m.DCE"]


def test_assert_line_local_output_rejects_shared_or_parent_paths(tmp_path: Path) -> None:
    line_dir = tmp_path / "research" / "lines" / "new_line"
    allowed = line_dir / "artifacts" / "stage001" / "summary.json"
    assert core.assert_line_local_output(line_dir, allowed) == allowed.resolve()

    with pytest.raises(core.SourceContractError, match="output_path_outside_line"):
        core.assert_line_local_output(line_dir, tmp_path / "examples" / "shared.csv")


def test_scan_archive_inventory_derives_identity_from_file_contents(tmp_path: Path) -> None:
    catalog = core.normalise_catalog(
        _catalog_rows(),
        catalog_as_of=pd.Timestamp("2026-06-30"),
        source_start=pd.Timestamp("2021-01-18"),
        cutoff=pd.Timestamp("2026-06-30"),
    )
    archive = tmp_path / "archive"
    (archive / "DCE").mkdir(parents=True)
    (archive / "DCE" / "m2605.csv").write_text(
        "trade_date,close,volume,open_oi\n"
        "2026-05-13,2500,100,200\n"
        "2026-05-14,2510,110,210\n",
        encoding="utf-8",
    )

    inventory = core.scan_archive_inventory(catalog, archive).set_index("tq_symbol")

    assert inventory.loc["DCE.m2605", "status"] == "available"
    assert inventory.loc["DCE.m2605", "rows"] == 2
    assert inventory.loc["DCE.m2605", "min_date"] == pd.Timestamp("2026-05-13")
    assert inventory.loc["DCE.m2605", "max_date"] == pd.Timestamp("2026-05-14")
    assert len(inventory.loc["DCE.m2605", "sha256"]) == 64
    assert inventory.loc["DCE.m2609", "status"] == "missing"


def test_scan_archive_inventory_rejects_contract_file_with_duplicate_dates(tmp_path: Path) -> None:
    catalog = core.normalise_catalog(
        _catalog_rows(),
        catalog_as_of=pd.Timestamp("2026-06-30"),
        source_start=pd.Timestamp("2021-01-18"),
        cutoff=pd.Timestamp("2026-06-30"),
    )
    archive = tmp_path / "archive"
    (archive / "DCE").mkdir(parents=True)
    (archive / "DCE" / "m2605.csv").write_text(
        "trade_date,close,volume,open_oi\n"
        "2026-05-13,2500,100,200\n"
        "2026-05-13,2510,110,210\n",
        encoding="utf-8",
    )

    with pytest.raises(core.SourceContractError, match="archive_bar_date_duplicate:DCE.m2605"):
        core.scan_archive_inventory(catalog, archive)
