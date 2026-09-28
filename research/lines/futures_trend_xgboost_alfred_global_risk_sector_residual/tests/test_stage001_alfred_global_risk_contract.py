from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stage001_alfred_global_risk_contract as stage001


def _snapshot_bytes(
    series_id: str,
    eval_date: str,
    rows: list[tuple[str, object]],
) -> bytes:
    suffix = pd.Timestamp(eval_date).strftime("%Y%m%d")
    body = [f"observation_date,{series_id}_{suffix}"]
    body.extend(f"{date},{value}" for date, value in rows)
    return ("\n".join(body) + "\n").encode("utf-8")


def _snapshot_frame(values: np.ndarray, end: str = "2024-01-30") -> pd.DataFrame:
    dates = pd.bdate_range(end=pd.Timestamp(end), periods=len(values))
    return pd.DataFrame({"observation_date": dates, "value": values})


def _state_snapshot_fixture() -> dict[tuple[pd.Timestamp, str], pd.DataFrame]:
    eval_date = pd.Timestamp("2024-01-31")
    index = np.arange(260, dtype=float)
    return {
        (eval_date, "DEXCHUS"): _snapshot_frame(6.2 * np.exp(0.0004 * index)),
        (eval_date, "DTWEXBGS"): _snapshot_frame(95.0 * np.exp(0.0003 * index)),
        (eval_date, "VIXCLS"): _snapshot_frame(12.0 + (index % 37) / 3.0),
    }


def _monthly_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "eval_date": pd.Timestamp("2024-01-31"),
                "cny_depreciation_shock_20d": 0.5,
                "broad_usd_shock_20d": -0.25,
                "vix_stress_percentile_252d": 0.8,
            }
        ]
    )


def test_parse_snapshot_requires_exact_vintage_column() -> None:
    content = b"observation_date,DEXCHUS_20200124\n2020-01-22,6.93\n"

    with pytest.raises(stage001.Stage001Error, match="snapshot_column_mismatch"):
        stage001.parse_snapshot("DEXCHUS", pd.Timestamp("2020-01-23"), content)


def test_parse_snapshot_rejects_same_day_observation() -> None:
    content = b"observation_date,VIXCLS_20200123\n2020-01-23,12.0\n"

    with pytest.raises(stage001.Stage001Error, match="snapshot_future_observation"):
        stage001.parse_snapshot("VIXCLS", pd.Timestamp("2020-01-23"), content)


def test_parse_snapshot_rejects_duplicate_dates() -> None:
    content = _snapshot_bytes(
        "DEXCHUS",
        "2020-01-23",
        [("2020-01-22", 6.93), ("2020-01-22", 6.94)],
    )

    with pytest.raises(stage001.Stage001Error, match="snapshot_duplicate_date"):
        stage001.parse_snapshot("DEXCHUS", pd.Timestamp("2020-01-23"), content)


def test_parse_snapshot_normalizes_missing_and_positive_values() -> None:
    content = _snapshot_bytes(
        "DEXCHUS",
        "2020-01-23",
        [("2020-01-20", "."), ("2020-01-21", 6.92), ("2020-01-22", 6.93)],
    )

    frame = stage001.parse_snapshot(
        "DEXCHUS",
        pd.Timestamp("2020-01-23"),
        content,
    )

    assert frame.to_dict("records") == [
        {"observation_date": pd.Timestamp("2020-01-21"), "value": 6.92},
        {"observation_date": pd.Timestamp("2020-01-22"), "value": 6.93},
    ]

    nonpositive = _snapshot_bytes(
        "DEXCHUS",
        "2020-01-23",
        [("2020-01-22", 0)],
    )
    with pytest.raises(stage001.Stage001Error, match="snapshot_nonpositive_value"):
        stage001.parse_snapshot("DEXCHUS", pd.Timestamp("2020-01-23"), nonpositive)


def test_state_features_match_hand_derived_formulas() -> None:
    eval_date = pd.Timestamp("2024-01-31")
    snapshots = _state_snapshot_fixture()

    monthly = stage001.build_state_features(snapshots, [eval_date])
    row = monthly.iloc[0]

    for series_id, feature in (
        ("DEXCHUS", "cny_depreciation_shock_20d"),
        ("DTWEXBGS", "broad_usd_shock_20d"),
    ):
        values = snapshots[(eval_date, series_id)]["value"]
        returns = np.log(values / values.shift(1)).dropna()
        expected = np.log(values.iloc[-1] / values.iloc[-21]) / (
            returns.iloc[-252:].std(ddof=1) * np.sqrt(20.0)
        )
        assert row[feature] == pytest.approx(expected)

    vix = snapshots[(eval_date, "VIXCLS")]["value"].iloc[-252:]
    assert row["vix_stress_percentile_252d"] == pytest.approx(
        float((vix <= vix.iloc[-1]).mean())
    )


def test_state_features_require_253_levels_and_nonzero_fx_volatility() -> None:
    eval_date = pd.Timestamp("2024-01-31")
    snapshots = _state_snapshot_fixture()
    snapshots[(eval_date, "DEXCHUS")] = snapshots[(eval_date, "DEXCHUS")].tail(252)

    with pytest.raises(stage001.Stage001Error, match="snapshot_window_incomplete"):
        stage001.build_state_features(snapshots, [eval_date])

    snapshots = _state_snapshot_fixture()
    snapshots[(eval_date, "DTWEXBGS")]["value"] = 100.0
    with pytest.raises(stage001.Stage001Error, match="fx_volatility_nonpositive"):
        stage001.build_state_features(snapshots, [eval_date])


def test_state_features_require_every_series_and_exact_eval_date() -> None:
    eval_date = pd.Timestamp("2024-01-31")
    snapshots = _state_snapshot_fixture()
    del snapshots[(eval_date, "VIXCLS")]

    with pytest.raises(stage001.Stage001Error, match="snapshot_missing"):
        stage001.build_state_features(snapshots, [eval_date])


def test_sector_mapping_covers_formal_products_without_static_one_hot() -> None:
    panel, columns = stage001.build_interaction_panel(
        _monthly_fixture(),
        stage001.FORMAL_PRODUCTS,
    )

    assert len(panel) == 18
    assert panel.groupby("product_vt_symbol").size().eq(1).all()
    assert panel["sector"].value_counts().to_dict() == {
        "chemicals_materials": 6,
        "metals": 4,
        "ferrous": 4,
        "agriculture": 4,
    }
    assert len(columns) == 15
    assert not any(column.startswith("sector_") for column in columns)
    assert panel[columns].drop_duplicates().shape[0] == 4


def test_nonmember_interactions_are_zero_and_member_is_exact() -> None:
    panel, _ = stage001.build_interaction_panel(
        _monthly_fixture(),
        ["au.SHFE", "AP.CZCE"],
    )
    au = panel.loc[panel["product_vt_symbol"].eq("au.SHFE")].iloc[0]
    feature = "cny_depreciation_shock_20d"

    assert au[f"{feature}_x_agriculture"] == 0.0
    assert au[f"{feature}_x_metals"] == au[feature]


def test_sector_mapping_rejects_unknown_or_duplicate_products() -> None:
    monthly = _monthly_fixture()

    with pytest.raises(stage001.Stage001Error, match="product_sector_missing"):
        stage001.build_interaction_panel(monthly, ["unknown.TEST"])
    with pytest.raises(stage001.Stage001Error, match="duplicate_formal_product"):
        stage001.build_interaction_panel(monthly, ["au.SHFE", "au.SHFE"])


def test_reconstruct_eval_dates_never_requires_label_columns() -> None:
    fold_plan = pd.DataFrame(
        {
            "test_eval_date": ["2022-04-29", "2022-05-31"],
            "train_eval_dates": [
                "2020-01-23,2020-02-28",
                "2020-01-23,2020-02-28,2020-03-31",
            ],
            "secret_label_value": [999.0, 888.0],
        }
    )

    all_dates, oos_dates = stage001.reconstruct_eval_dates(fold_plan)

    assert all_dates == list(
        pd.to_datetime(
            [
                "2020-01-23",
                "2020-02-28",
                "2020-03-31",
                "2022-04-29",
                "2022-05-31",
            ]
        )
    )
    assert oos_dates == list(pd.to_datetime(["2022-04-29", "2022-05-31"]))


def test_snapshot_url_is_strict_prior_day_vintage() -> None:
    url = stage001.build_snapshot_url("DEXCHUS", pd.Timestamp("2020-01-23"))

    assert url == (
        "https://alfred.stlouisfed.org/graph/alfredgraph.csv?"
        "id=DEXCHUS&cosd=2019-01-01&coed=2020-01-22&vintage_date=2020-01-23"
    )


def test_snapshot_resume_rejects_content_with_wrong_vintage(tmp_path: Path) -> None:
    raw = tmp_path / "raw_snapshots"
    raw.mkdir()
    (raw / "2020-01-23_DEXCHUS.csv").write_bytes(
        b"observation_date,DEXCHUS_20200124\n2020-01-22,6.93\n"
    )
    fetch_calls: list[str] = []

    with pytest.raises(stage001.Stage001Error, match="existing_snapshot_invalid"):
        stage001.acquire_snapshots(
            raw,
            lambda url: fetch_calls.append(url) or b"unused",
            eval_dates=[pd.Timestamp("2020-01-23")],
            series_ids=["DEXCHUS"],
            max_workers=1,
        )

    assert fetch_calls == []


def test_snapshot_acquisition_persists_and_reports_identity(tmp_path: Path) -> None:
    content = _snapshot_bytes(
        "DEXCHUS",
        "2020-01-23",
        [("2020-01-21", 6.92), ("2020-01-22", 6.93)],
    )

    records, snapshots = stage001.acquire_snapshots(
        tmp_path / "raw_snapshots",
        lambda url: content,
        eval_dates=[pd.Timestamp("2020-01-23")],
        series_ids=["DEXCHUS"],
        max_workers=1,
    )

    stored = tmp_path / "raw_snapshots/2020-01-23_DEXCHUS.csv"
    assert stored.read_bytes() == content
    assert records[0]["eval_date"] == "2020-01-23"
    assert records[0]["series_id"] == "DEXCHUS"
    assert records[0]["snapshot_bytes"] == len(content)
    assert records[0]["valid_row_count"] == 2
    assert records[0]["latest_observation_date"] == "2020-01-22"
    assert records[0]["latest_lag_days"] == 1
    assert len(records[0]["sha256"]) == 64
    assert len(snapshots[(pd.Timestamp("2020-01-23"), "DEXCHUS")]) == 2


def test_snapshot_acquisition_stops_after_first_exhausted_item(
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    def fail(url: str) -> bytes:
        calls.append(url)
        raise ConnectionError("offline")

    with pytest.raises(stage001.Stage001Error, match="snapshot_download_failed"):
        stage001.acquire_snapshots(
            tmp_path / "raw_snapshots",
            fail,
            eval_dates=[pd.Timestamp("2020-01-23"), pd.Timestamp("2020-02-28")],
            series_ids=["DEXCHUS"],
            max_workers=1,
            max_attempts=5,
            retry_sleep_seconds=0.0,
        )

    assert len(calls) == 5
    assert all("vintage_date=2020-01-23" in url for url in calls)


def test_official_snapshot_fetch_uses_bounded_curl_without_shell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    class Result:
        returncode = 0
        stdout = b"official-snapshot"
        stderr = b""

    def fake_run(args: list[str], **kwargs: object) -> Result:
        calls.append((args, kwargs))
        return Result()

    monkeypatch.setattr(stage001.subprocess, "run", fake_run)
    url = stage001.build_snapshot_url("DEXCHUS", pd.Timestamp("2020-01-23"))

    assert stage001._official_fetch_snapshot(url) == b"official-snapshot"
    args, kwargs = calls[0]
    assert args == [
        "/usr/bin/curl",
        "--http1.1",
        "--fail",
        "--location",
        "--silent",
        "--show-error",
        "--max-time",
        "30",
        "--connect-timeout",
        "15",
        url,
    ]
    assert kwargs == {
        "capture_output": True,
        "check": False,
        "timeout": 45,
    }


def test_official_snapshot_fetch_rejects_curl_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Result:
        returncode = 22
        stdout = b""
        stderr = b"curl: (22) HTTP 404"

    monkeypatch.setattr(stage001.subprocess, "run", lambda *args, **kwargs: Result())
    url = stage001.build_snapshot_url("DEXCHUS", pd.Timestamp("2020-01-23"))

    with pytest.raises(stage001.Stage001Error, match="alfred_curl_failed:22"):
        stage001._official_fetch_snapshot(url)


def test_aggregate_snapshot_hash_binds_date_series_and_digest_order() -> None:
    first = [
        {"eval_date": "2020-01-23", "series_id": "DEXCHUS", "sha256": "1" * 64},
        {"eval_date": "2020-01-23", "series_id": "VIXCLS", "sha256": "2" * 64},
    ]

    assert stage001.aggregate_snapshot_hash(first) == stage001.aggregate_snapshot_hash(
        list(reversed(first))
    )
    changed = [dict(first[0]), dict(first[1])]
    changed[1]["sha256"] = "3" * 64
    assert stage001.aggregate_snapshot_hash(first) != stage001.aggregate_snapshot_hash(
        changed
    )


def _passing_gate_metrics() -> dict[str, object]:
    return {
        "input_identity_mismatch_count": 0,
        "current_release_id": stage001.EXPECTED_RELEASE_ID,
        "current_strategy_id": stage001.EXPECTED_STRATEGY_ID,
        "current_pointer_matches_release": True,
        "source_snapshot_count": 231,
        "source_series_count": 3,
        "source_min_snapshots_per_series": 77,
        "source_max_snapshots_per_series": 77,
        "source_total_bytes": 4_624_211,
        "source_aggregate_sha256": stage001.EXPECTED_SOURCE_AGGREGATE_SHA256,
        "source_min_valid_level_count": 253,
        "source_future_row_count": 0,
        "source_duplicate_identity_count": 0,
        "source_current_fred_fallback_count": 0,
        "source_third_party_fallback_count": 0,
        "source_max_lag_days": {"DEXCHUS": 10, "DTWEXBGS": 10, "VIXCLS": 3},
        "eval_date_count": 77,
        "oos_eval_date_count": 50,
        "monthly_state_row_count": 77,
        "state_feature_count": 3,
        "state_unique_counts": {
            "cny_depreciation_shock_20d": 77,
            "broad_usd_shock_20d": 77,
            "vix_stress_percentile_252d": 62,
        },
        "minimum_state_std": 0.1,
        "interaction_panel_row_count": 1386,
        "formal_product_count": 18,
        "interaction_feature_count": 15,
        "minimum_products_per_month": 18,
        "maximum_products_per_month": 18,
        "effective_month_sector_state_count": 308,
        "nonfinite_feature_cell_count": 0,
        "sector_count_contract_match": True,
        "static_sector_one_hot_column_count": 0,
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
        ("source_total_bytes", 4_624_210, "source_contract"),
        ("source_min_valid_level_count", 252, "source_contract"),
        ("current_pointer_matches_release", False, "identity_contract"),
        ("oos_eval_date_count", 49, "eval_contract"),
        ("interaction_feature_count", 16, "feature_contract"),
        ("effective_month_sector_state_count", 307, "feature_contract"),
        ("static_sector_one_hot_column_count", 1, "expression_contract"),
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
    (bundle / "raw_snapshots").mkdir(parents=True)
    (bundle / "raw_snapshots/2020-01-23_DEXCHUS.csv").write_bytes(b"snapshot")
    (bundle / "monthly_state_features.csv").write_text("a\n1\n", encoding="utf-8")
    (bundle / "summary.json").write_text(
        json.dumps({"decision": "test"}),
        encoding="utf-8",
    )
    stage001.write_artifact_manifest(bundle)
    return bundle


def test_manifest_verification_detects_mutation(tmp_path: Path) -> None:
    bundle = _write_valid_bundle(tmp_path)
    (bundle / "monthly_state_features.csv").write_text("mutated", encoding="utf-8")

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
    ledger.record("snapshot_retry", attempt=2)

    events = [json.loads(line) for line in ledger.path.read_text().splitlines()]
    assert [event["sequence"] for event in events] == [1, 2]
    assert {event["run_nonce"] for event in events} == {nonce}
    assert ledger.event_count == 2


def test_event_ledger_rejects_noncanonical_nonce(tmp_path: Path) -> None:
    with pytest.raises(stage001.Stage001Error, match="run_nonce_invalid"):
        stage001.DurableEventLedger(tmp_path / "event_ledger.ndjson", "A" * 64)


def test_build_metrics_reports_effective_month_sector_sample() -> None:
    dates = list(pd.bdate_range("2020-01-23", periods=77, freq="20B"))
    monthly = pd.DataFrame(
        {
            "eval_date": dates,
            "cny_depreciation_shock_20d": np.arange(77, dtype=float),
            "broad_usd_shock_20d": np.arange(77, dtype=float) + 0.5,
            "vix_stress_percentile_252d": (np.arange(77) % 62) / 62.0,
        }
    )
    panel, feature_columns = stage001.build_interaction_panel(
        monthly,
        stage001.FORMAL_PRODUCTS,
    )
    records: list[dict[str, object]] = []
    for date in dates:
        for series_id in stage001.SERIES_IDS:
            records.append(
                {
                    "eval_date": pd.Timestamp(date).strftime("%Y-%m-%d"),
                    "series_id": series_id,
                    "snapshot_bytes": 1,
                    "sha256": hashlib.sha256(
                        f"{date}:{series_id}".encode()
                    ).hexdigest(),
                    "valid_row_count": 253,
                    "latest_lag_days": stage001.EXPECTED_MAX_LAG_DAYS[series_id],
                }
            )
    identities = {
        "x": {
            "matches_expected": True,
            "sha256": "a" * 64,
            "size": 1,
            "mtime_ns": 1,
        }
    }

    metrics = stage001._build_metrics(
        records=records,
        monthly=monthly,
        panel=panel,
        feature_columns=feature_columns,
        eval_dates=dates,
        oos_dates=dates[:50],
        identities_before=identities,
        identities_after=identities,
        current={
            "release_id": stage001.EXPECTED_RELEASE_ID,
            "strategy_version": stage001.EXPECTED_STRATEGY_ID,
        },
        release_manifest={
            "release_id": stage001.EXPECTED_RELEASE_ID,
            "strategy_version": stage001.EXPECTED_STRATEGY_ID,
        },
        ledger_event_count=10,
    )

    assert metrics["interaction_panel_row_count"] == 1386
    assert metrics["interaction_feature_count"] == 15
    assert metrics["effective_month_sector_state_count"] == 308
    assert metrics["static_sector_one_hot_column_count"] == 0
    assert metrics["interaction_mismatch_cell_count"] == 0
    assert metrics["sector_count_contract_match"] is True
