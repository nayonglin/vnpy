from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stage001_cffex_macro_contract as stage001


def _bars(rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


def _three_day_contract_fixture() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    values = {
        "2024-01-02": [("IF2401", 100.0, 300.0, 100.0), ("IF2402", 200.0, 200.0, 200.0)],
        "2024-01-03": [("IF2401", 101.0, 100.0, 100.0), ("IF2402", 201.0, 900.0, 500.0)],
        "2024-01-04": [("IF2401", 102.0, 100.0, 100.0), ("IF2402", 202.0, 900.0, 500.0)],
    }
    for date, contracts in values.items():
        for symbol, close, volume, open_interest in contracts:
            rows.append(
                {
                    "date": date,
                    "root": "IF",
                    "symbol": symbol,
                    "close": close,
                    "volume": volume,
                    "open_interest": open_interest,
                }
            )
    return _bars(rows)


def _roll_fixture() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    values = {
        "2024-01-02": [("IF2401", 100.0, 300.0, 500.0), ("IF2402", 200.0, 200.0, 100.0)],
        "2024-01-03": [("IF2401", 101.0, 100.0, 100.0), ("IF2402", 201.0, 900.0, 900.0)],
        "2024-01-04": [("IF2401", 102.0, 100.0, 50.0), ("IF2402", 202.0, 900.0, 900.0)],
    }
    for date, contracts in values.items():
        for symbol, close, volume, open_interest in contracts:
            rows.append(
                {
                    "date": date,
                    "root": "IF",
                    "symbol": symbol,
                    "close": close,
                    "volume": volume,
                    "open_interest": open_interest,
                }
            )
    return _bars(rows)


def _archive_bytes(filename: str, csv_text: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(filename, csv_text.encode("gb18030"))
    return buffer.getvalue()


def test_month_range_is_inclusive() -> None:
    assert stage001.month_range("201911", "202002") == [
        "201911",
        "201912",
        "202001",
        "202002",
    ]


def test_parse_month_archive_reads_daily_date_and_filters_six_roots() -> None:
    content = _archive_bytes(
        "20240103_1.csv",
        "合约代码,今收盘,成交量,持仓量\n"
        "IF2401,3210.4,1234,5678\n"
        "IM2401,5432.1,2345,6789\n"
        "IO2401-C-3000,1.2,30,40\n",
    )

    bars, daily_files = stage001.parse_month_archive("202401", content)

    assert daily_files == ["20240103_1.csv"]
    assert bars.to_dict("records") == [
        {
            "date": pd.Timestamp("2024-01-03"),
            "root": "IF",
            "symbol": "IF2401",
            "close": 3210.4,
            "volume": 1234.0,
            "open_interest": 5678.0,
        }
    ]


def test_prior_day_oi_wins_even_when_same_day_oi_flips() -> None:
    selected = stage001.build_prior_oi_main_series(_three_day_contract_fixture())

    row = selected.loc[selected["date"].eq(pd.Timestamp("2024-01-03"))].iloc[0]
    assert row["symbol"] == "IF2402"
    assert row["prior_open_interest"] == 200.0
    assert row["open_interest"] == 500.0


def test_prior_day_ties_use_prior_volume_then_symbol() -> None:
    bars = _three_day_contract_fixture()
    prior = bars["date"].eq(pd.Timestamp("2024-01-02"))
    bars.loc[prior, "open_interest"] = 200.0
    bars.loc[prior, "volume"] = 300.0

    selected = stage001.build_prior_oi_main_series(bars)

    row = selected.loc[selected["date"].eq(pd.Timestamp("2024-01-03"))].iloc[0]
    assert row["symbol"] == "IF2401"


def test_missing_exact_previous_market_day_fails_closed() -> None:
    bars = _three_day_contract_fixture()
    tf = bars.copy()
    tf["root"] = "TF"
    tf["symbol"] = tf["symbol"].str.replace("IF", "TF", regex=False)
    tf = tf[~tf["date"].eq(pd.Timestamp("2024-01-03"))]
    combined = pd.concat([bars, tf], ignore_index=True)

    with pytest.raises(stage001.Stage001Error, match="stale_prior_date"):
        stage001.build_prior_oi_main_series(combined)


def test_roll_day_return_is_zero() -> None:
    selected = stage001.build_prior_oi_main_series(_roll_fixture())

    roll = selected.loc[selected["roll_event"].eq(1)].iloc[0]
    assert roll["date"] == pd.Timestamp("2024-01-04")
    assert roll["product_return"] == 0.0


def test_duplicate_contract_day_fails_closed() -> None:
    bars = _three_day_contract_fixture()
    duplicated = pd.concat([bars, bars.iloc[[0]]], ignore_index=True)

    with pytest.raises(stage001.Stage001Error, match="duplicate_contract_day"):
        stage001.build_prior_oi_main_series(duplicated)


def _selected_return_fixture(days: int = 130) -> pd.DataFrame:
    dates = pd.bdate_range("2023-01-02", periods=days)
    rows: list[dict[str, object]] = []
    offsets = {"IF": 1, "IH": 2, "IC": 3, "T": 4, "TF": 5, "TS": 6}
    for index, date in enumerate(dates):
        for root, offset in offsets.items():
            wave = ((index + offset) % 9 - 4) / 10_000.0
            drift = 0.00035 if root in {"IF", "IH", "IC"} else 0.00010
            rows.append(
                {
                    "date": date,
                    "root": root,
                    "product_return": drift + wave,
                }
            )
    return pd.DataFrame(rows)


def _macro_fixture() -> pd.DataFrame:
    row: dict[str, object] = {"eval_date": pd.Timestamp("2024-01-31")}
    for index, column in enumerate(stage001.MACRO_FEATURES, start=1):
        row[column] = float(index) / 10.0
    return pd.DataFrame([row])


def test_macro_features_match_hand_derived_windows() -> None:
    selected = _selected_return_fixture()
    factors = stage001.build_daily_factors(selected)
    last = factors.iloc[-1]
    pivot = selected.pivot(index="date", columns="root", values="product_return")
    equity = pivot[["IF", "IH", "IC"]].mean(axis=1)
    rates = pivot[["T", "TF", "TS"]].mean(axis=1)
    equity_root_momentum = [
        float(np.prod(1.0 + pivot[root].tail(60)) - 1.0)
        for root in ("IF", "IH", "IC")
    ]

    assert last["cffex_equity_momentum_60d"] == pytest.approx(
        float(np.prod(1.0 + equity.tail(60)) - 1.0)
    )
    assert last["cffex_rates_momentum_60d"] == pytest.approx(
        float(np.prod(1.0 + rates.tail(60)) - 1.0)
    )
    assert last["cffex_equity_vol_ratio_20_120"] == pytest.approx(
        float(equity.tail(20).std(ddof=1) / equity.tail(120).std(ddof=1))
    )
    assert last["cffex_rates_vol_ratio_20_120"] == pytest.approx(
        float(rates.tail(20).std(ddof=1) / rates.tail(120).std(ddof=1))
    )
    assert last["cffex_equity_rates_corr_60d"] == pytest.approx(
        float(equity.tail(60).corr(rates.tail(60)))
    )
    assert last["cffex_equity_breadth_60d"] == pytest.approx(
        float(np.mean(np.asarray(equity_root_momentum) > 0.0))
    )
    assert last["cffex_equity_dispersion_60d"] == pytest.approx(
        float(np.std(equity_root_momentum, ddof=1))
    )


def test_macro_monthly_selection_requires_exact_date_and_120_days() -> None:
    factors = stage001.build_daily_factors(_selected_return_fixture())
    valid_date = pd.Timestamp(factors.iloc[-1]["date"])

    monthly = stage001.build_monthly_macro_features(factors, [valid_date])
    assert monthly["eval_date"].tolist() == [valid_date]
    assert monthly[list(stage001.MACRO_FEATURES)].notna().all(axis=None)

    with pytest.raises(stage001.Stage001Error, match="eval_date_missing"):
        stage001.build_monthly_macro_features(
            factors,
            [valid_date + pd.Timedelta(days=1)],
        )
    with pytest.raises(stage001.Stage001Error, match="window_incomplete"):
        stage001.build_monthly_macro_features(
            factors,
            [pd.Timestamp(factors.iloc[118]["date"])],
        )


def test_sector_mapping_covers_formal_products_once() -> None:
    panel, columns = stage001.build_interaction_panel(
        _macro_fixture(),
        stage001.FORMAL_PRODUCTS,
    )

    assert panel.groupby("product_vt_symbol").size().eq(1).all()
    assert panel[list(stage001.SECTOR_COLUMNS)].sum(axis=1).eq(1.0).all()
    assert len(columns) == 39
    assert len(panel) == 18


def test_nonmember_interactions_are_zero_and_member_is_exact() -> None:
    panel, _ = stage001.build_interaction_panel(
        _macro_fixture(),
        ["au.SHFE", "AP.CZCE"],
    )
    au = panel.loc[panel["product_vt_symbol"].eq("au.SHFE")].iloc[0]
    feature = "cffex_equity_momentum_60d"

    assert au[f"{feature}_x_agriculture"] == 0.0
    assert au[f"{feature}_x_metals"] == au[feature]


def test_sector_mapping_rejects_unknown_or_duplicate_products() -> None:
    monthly = _macro_fixture()
    with pytest.raises(stage001.Stage001Error, match="product_sector_missing"):
        stage001.build_interaction_panel(monthly, ["unknown.TEST"])
    with pytest.raises(stage001.Stage001Error, match="duplicate_formal_product"):
        stage001.build_interaction_panel(monthly, ["au.SHFE", "au.SHFE"])


def test_archive_resume_rejects_corrupt_existing_zip(tmp_path: Path) -> None:
    raw = tmp_path / "raw_archives"
    raw.mkdir()
    (raw / "201906.zip").write_bytes(b"not-a-zip")
    fetch_calls: list[str] = []

    with pytest.raises(stage001.Stage001Error, match="existing_archive_invalid"):
        stage001.acquire_archives(
            raw,
            lambda month: fetch_calls.append(month) or b"unused",
            months=["201906"],
        )

    assert fetch_calls == []


def test_archive_acquisition_persists_and_reports_source_identity(tmp_path: Path) -> None:
    content = _archive_bytes(
        "20190603_1.csv",
        "合约代码,今收盘,成交量,持仓量\nIF1906,100,20,30\n",
    )

    records, bars = stage001.acquire_archives(
        tmp_path / "raw_archives",
        lambda month: content,
        months=["201906"],
    )

    assert (tmp_path / "raw_archives/201906.zip").read_bytes() == content
    assert records[0]["month"] == "201906"
    assert records[0]["archive_bytes"] == len(content)
    assert records[0]["daily_file_count"] == 1
    assert records[0]["raw_row_count"] == 1
    assert records[0]["core_row_count"] == 1
    assert len(records[0]["sha256"]) == 64
    assert len(bars) == 1


def test_official_archive_fetch_uses_reachable_cffex_http_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class Response:
        status_code = 200
        content = b"official-archive"

    def fake_get(url: str, **kwargs: object) -> Response:
        calls.append(url)
        assert kwargs["timeout"] == (15, 90)
        return Response()

    monkeypatch.setattr(stage001.requests, "get", fake_get)

    assert stage001._official_fetch_month("201906") == b"official-archive"
    assert calls == [
        "http://www.cffex.com.cn/sj/historysj/201906/zip/201906.zip"
    ]


def test_archive_acquisition_stops_after_first_exhausted_month(tmp_path: Path) -> None:
    calls: list[str] = []

    def fail(month: str) -> bytes:
        calls.append(month)
        raise ConnectionError("offline")

    with pytest.raises(stage001.Stage001Error, match="archive_download_failed:201906"):
        stage001.acquire_archives(
            tmp_path / "raw_archives",
            fail,
            months=["201906", "201907", "201908"],
            max_workers=1,
        )

    assert calls == ["201906", "201906", "201906"]


def test_aggregate_archive_hash_binds_month_and_digest_order() -> None:
    first = [
        {"month": "201906", "sha256": "1" * 64},
        {"month": "201907", "sha256": "2" * 64},
    ]
    reversed_records = list(reversed(first))

    assert stage001.aggregate_archive_hash(first) == stage001.aggregate_archive_hash(
        reversed_records
    )
    changed = [dict(first[0]), dict(first[1])]
    changed[1]["sha256"] = "3" * 64
    assert stage001.aggregate_archive_hash(first) != stage001.aggregate_archive_hash(changed)


def test_fold_plan_date_extraction_never_requires_label_columns(tmp_path: Path) -> None:
    path = tmp_path / "fold_plan.csv"
    pd.DataFrame(
        {
            "test_eval_date": ["2022-04-29", "2022-05-31"],
            "train_eval_dates": [
                "2020-01-23,2020-02-28",
                "2020-01-23,2020-02-28,2020-03-31",
            ],
            "secret_label_value": [999.0, 888.0],
        }
    ).to_csv(path, index=False)

    all_dates, oos_dates = stage001.load_fold_eval_dates(path)

    assert all_dates == list(pd.to_datetime([
        "2020-01-23",
        "2020-02-28",
        "2020-03-31",
        "2022-04-29",
        "2022-05-31",
    ]))
    assert oos_dates == list(pd.to_datetime(["2022-04-29", "2022-05-31"]))


def _passing_gate_metrics() -> dict[str, object]:
    return {
        "input_identity_mismatch_count": 0,
        "current_release_id": stage001.EXPECTED_RELEASE_ID,
        "current_strategy_id": stage001.EXPECTED_STRATEGY_ID,
        "current_pointer_matches_release": True,
        "source_month_count": 84,
        "source_daily_file_count": 1695,
        "source_archive_bytes": 26_066_955,
        "source_raw_row_count": 847_781,
        "source_core_row_count": 35_595,
        "source_duplicate_key_count": 0,
        "source_aggregate_sha256": stage001.EXPECTED_SOURCE_AGGREGATE_SHA256,
        "source_first_date": "2019-06-03",
        "source_last_date": "2026-05-29",
        "pit_root_count": 6,
        "pit_min_selected_days": 1694,
        "pit_max_selected_days": 1694,
        "pit_first_date": "2019-06-04",
        "pit_last_date": "2026-05-29",
        "pit_all_roots_date_contract_match": True,
        "pit_future_row_count": 0,
        "pit_stale_prior_row_count": 0,
        "pit_fallback_row_count": 0,
        "pit_roll_nonzero_return_count": 0,
        "eval_date_count": 77,
        "oos_eval_date_count": 50,
        "eval_exact_count": 77,
        "eval_complete_120_count": 77,
        "oos_exact_count": 50,
        "oos_complete_120_count": 50,
        "monthly_macro_row_count": 77,
        "macro_feature_count": 7,
        "interaction_panel_row_count": 1386,
        "formal_product_count": 18,
        "interaction_feature_count": 39,
        "minimum_products_per_month": 18,
        "maximum_products_per_month": 18,
        "nonfinite_feature_cell_count": 0,
        "minimum_macro_unique_count": 20,
        "minimum_macro_std": 0.000001,
        "sector_count_contract_match": True,
        "one_hot_violation_count": 0,
        "interaction_mismatch_cell_count": 0,
        "label_value_read_count": 0,
        "model_fit_count": 0,
        "model_predict_count": 0,
        "strategy_backtest_count": 0,
        "holdout_read_count": 0,
        "ctp_connection_count": 0,
        "order_api_call_count": 0,
        "production_write_count": 0,
        "execution_receipt_exists": True,
        "event_ledger_event_count": 4,
        "atomic_publish_ready": True,
    }


def test_gate_evaluation_accepts_only_exact_frozen_contract() -> None:
    gates, failures = stage001.evaluate_gates(_passing_gate_metrics())

    assert all(gates.values())
    assert failures == []


@pytest.mark.parametrize(
    ("field", "value", "failure"),
    [
        ("source_archive_bytes", 26_066_954, "source_contract"),
        ("source_first_date", "2019-06-04", "source_contract"),
        ("current_pointer_matches_release", False, "identity_contract"),
        ("pit_max_selected_days", 1693, "pit_contract"),
        ("pit_all_roots_date_contract_match", False, "pit_contract"),
        ("eval_complete_120_count", 76, "eval_contract"),
        ("interaction_feature_count", 38, "feature_contract"),
        ("interaction_mismatch_cell_count", 1, "expression_contract"),
        ("model_fit_count", 1, "side_effect_contract"),
        ("event_ledger_event_count", 0, "durability_contract"),
    ],
)
def test_gate_evaluation_fails_closed(
    field: str,
    value: object,
    failure: str,
) -> None:
    metrics = _passing_gate_metrics()
    metrics[field] = value

    gates, failures = stage001.evaluate_gates(metrics)

    assert gates[failure] is False
    assert failure in failures


def _write_valid_bundle(root: Path) -> Path:
    bundle = root / "bundle"
    (bundle / "raw_archives").mkdir(parents=True)
    (bundle / "raw_archives/201906.zip").write_bytes(b"archive")
    (bundle / "monthly_macro_features.csv").write_text("a\n1\n", encoding="utf-8")
    (bundle / "summary.json").write_text(
        json.dumps({"decision": "test"}),
        encoding="utf-8",
    )
    stage001.write_artifact_manifest(bundle)
    return bundle


def test_manifest_verification_detects_mutation(tmp_path: Path) -> None:
    bundle = _write_valid_bundle(tmp_path)
    (bundle / "monthly_macro_features.csv").write_text("mutated", encoding="utf-8")

    with pytest.raises(stage001.Stage001Error, match="manifest_mismatch"):
        stage001.verify_artifact_bundle(bundle)


def test_manifest_verification_detects_unmanifested_file(tmp_path: Path) -> None:
    bundle = _write_valid_bundle(tmp_path)
    (bundle / "unmanifested.txt").write_text("unexpected", encoding="utf-8")

    with pytest.raises(stage001.Stage001Error, match="unmanifested_file"):
        stage001.verify_artifact_bundle(bundle)


def test_atomic_publish_is_non_overwritable(tmp_path: Path) -> None:
    staging = _write_valid_bundle(tmp_path / "first")
    final = tmp_path / "final"

    stage001.publish_staged_directory(staging, final)
    assert stage001.verify_artifact_bundle(final)["artifact_bundle_valid"] is True

    other = _write_valid_bundle(tmp_path / "second")
    with pytest.raises(stage001.Stage001Error, match="final_output_exists"):
        stage001.publish_staged_directory(other, final)
    assert other.exists()


def test_event_ledger_binds_nonce_and_sequence(tmp_path: Path) -> None:
    nonce = "a" * 64
    ledger = stage001.DurableEventLedger(tmp_path / "event_ledger.ndjson", nonce)

    ledger.record("run_started", mode="label_free")
    ledger.record("archive_validated", month="201906")

    events = [json.loads(line) for line in ledger.path.read_text().splitlines()]
    assert [event["sequence"] for event in events] == [1, 2]
    assert {event["run_nonce"] for event in events} == {nonce}


def test_event_ledger_rejects_noncanonical_nonce(tmp_path: Path) -> None:
    with pytest.raises(stage001.Stage001Error, match="run_nonce_invalid"):
        stage001.DurableEventLedger(tmp_path / "event_ledger.ndjson", "A" * 64)
