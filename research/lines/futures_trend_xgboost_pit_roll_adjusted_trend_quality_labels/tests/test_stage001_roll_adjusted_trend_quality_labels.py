from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import pandas as pd


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stage001_roll_adjusted_trend_quality_labels as stage001


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fixture(tmp_path: Path, *, feature_missing: bool = False) -> tuple[dict[str, Path], dict[str, str]]:
    source = tmp_path / "inputs"
    source.mkdir()
    query_date = pd.Timestamp("2025-01-31")
    dates = pd.bdate_range("2025-02-03", periods=3)
    path_rows: list[dict[str, object]] = []
    leg_rows: list[dict[str, object]] = []
    bar_rows: list[dict[str, object]] = []
    feature_rows: list[dict[str, object]] = []
    for product_index in range(10):
        product = f"p{product_index}.EX"
        first_contract = f"P{product_index}A.EX"
        second_contract = f"P{product_index}B.EX"
        path_rows.append(
            {
                "query_date": query_date,
                "product_vt_symbol": product,
                "main_contract_vt": first_contract,
                "entry_date": dates[0],
                "label_end": dates[2],
                "leg_count": 2,
                "path_valid": True,
            }
        )
        feature_rows.append(
            {
                "query_date": query_date,
                "product_vt_symbol": product,
                "main_contract_vt": first_contract,
            }
        )
        first_return = 0.01 * (product_index + 1)
        second_return = -0.001 * (product_index % 3)
        for leg_index, (contract, previous, current, value) in enumerate(
            [
                (first_contract, dates[0], dates[1], first_return),
                (second_contract, dates[1], dates[2], second_return),
            ],
            start=1,
        ):
            start_price = 100.0 + product_index * 10 + leg_index * 100
            end_price = start_price * math.exp(value)
            symbol, exchange = contract.split(".")
            bar_rows.extend(
                [
                    {
                        "datetime": previous,
                        "symbol": symbol,
                        "exchange": exchange,
                        "interval": "d",
                        "close_price": start_price,
                    },
                    {
                        "datetime": current,
                        "symbol": symbol,
                        "exchange": exchange,
                        "interval": "d",
                        "close_price": end_price,
                    },
                ]
            )
            leg_rows.append(
                {
                    "query_date": query_date,
                    "product_vt_symbol": product,
                    "leg_index": leg_index,
                    "previous_date": previous,
                    "return_date": current,
                    "selected_contract_vt": contract,
                    "leg_valid": True,
                    "previous_bar_present": True,
                    "return_bar_present": True,
                    "roll_event": leg_index == 2,
                }
            )
    if feature_missing:
        feature_rows.pop()
    paths = {
        "upstream_manifest": source / "upstream_manifest.json",
        "upstream_paths": source / "upstream_paths.csv.gz",
        "upstream_legs": source / "upstream_legs.csv.gz",
        "upstream_summary": source / "upstream_summary.json",
        "source_manifest": source / "source_manifest.json",
        "source_summary": source / "source_summary.json",
        "source_bars": source / "source_bars.csv.gz",
        "feature_manifest": source / "feature_manifest.json",
        "feature_panel": source / "feature_panel.csv.gz",
        "v2_contract_manifest": source / "v2_contract_manifest.json",
        "v2_contract_summary": source / "v2_contract_summary.json",
    }
    pd.DataFrame(path_rows).to_csv(paths["upstream_paths"], index=False)
    pd.DataFrame(leg_rows).to_csv(paths["upstream_legs"], index=False)
    pd.DataFrame(bar_rows).drop_duplicates(
        ["datetime", "symbol", "exchange"]
    ).to_csv(paths["source_bars"], index=False)
    pd.DataFrame(feature_rows).to_csv(paths["feature_panel"], index=False)
    documents = {
        "upstream_manifest": {"kind": "synthetic_upstream_manifest"},
        "upstream_summary": {
            "decision": stage001.UPSTREAM_PASS_DECISION,
            "all_gates_passed": True,
        },
        "source_manifest": {"kind": "synthetic_source_manifest"},
        "source_summary": {
            "decision": stage001.SOURCE_PASS_DECISION,
            "all_gates_passed": True,
        },
        "feature_manifest": {"kind": "synthetic_feature_manifest"},
        "v2_contract_manifest": {"kind": "synthetic_v2_manifest"},
        "v2_contract_summary": {
            "decision": stage001.V2_CONTRACT_PASS_DECISION,
            "all_gates_passed": True,
        },
    }
    for key, document in documents.items():
        paths[key].write_text(
            json.dumps(document, sort_keys=True), encoding="utf-8"
        )
    expected_sha = {key: _sha(path) for key, path in paths.items()}
    return paths, expected_sha


def _verified() -> dict[str, dict[str, object]]:
    return {
        "upstream": {"verified": True, "errors": []},
        "source": {"verified": True, "errors": []},
        "feature": {"verified": True, "errors": []},
        "v2_contract": {"verified": True, "errors": []},
    }


def test_synthetic_stage001_publishes_and_verifies(monkeypatch, tmp_path: Path) -> None:
    input_paths, expected_sha = _fixture(tmp_path)
    line_dir = tmp_path / "line"
    output_dir = line_dir / "artifacts" / "stage001"
    line_dir.mkdir()
    monkeypatch.setattr(stage001, "_verify_upstream_bundles", lambda **_: _verified())

    summary = stage001.run_stage001(
        line_dir=line_dir,
        output_dir=output_dir,
        input_paths=input_paths,
        expected_sha256=expected_sha,
        expected=stage001.ExpectedCounts(
            path_rows=10,
            path_qids=1,
            leg_rows=20,
            feature_rows=10,
            holding_period=2,
            minimum_candidates_per_qid=5,
            relevance_levels=5,
        ),
    )

    assert summary["all_gates_passed"] is True
    assert summary["decision"] == stage001.PASS_DECISION
    assert summary["logical_close_reads"] == 40
    assert summary["cross_contract_price_comparisons"] == 0
    assert summary["xgboost_fit_count"] == 0
    assert summary["strategy_backtest_runs"] == 0
    assert summary["order_api_called_count"] == 0
    assert stage001.verify_final_bundle(output_dir)["verified"] is True
    labels = pd.read_csv(output_dir / "path_labels.csv.gz")
    assert set(labels["trend_quality_relevance"]) == {0, 1, 2, 3, 4}


def test_feature_identity_gap_fails_decision_but_publishes_bundle(
    monkeypatch, tmp_path: Path
) -> None:
    input_paths, expected_sha = _fixture(tmp_path, feature_missing=True)
    line_dir = tmp_path / "line"
    output_dir = line_dir / "artifacts" / "stage001"
    line_dir.mkdir()
    monkeypatch.setattr(stage001, "_verify_upstream_bundles", lambda **_: _verified())

    summary = stage001.run_stage001(
        line_dir=line_dir,
        output_dir=output_dir,
        input_paths=input_paths,
        expected_sha256=expected_sha,
        expected=stage001.ExpectedCounts(
            path_rows=10,
            path_qids=1,
            leg_rows=20,
            feature_rows=9,
            holding_period=2,
            minimum_candidates_per_qid=5,
            relevance_levels=5,
        ),
    )

    assert summary["all_gates_passed"] is False
    assert summary["decision"] == stage001.FAIL_DECISION
    assert summary["feature_identity_missing_paths"] == 1
    assert summary["gates"]["feature_identity_coverage"] is False
    assert stage001.verify_final_bundle(output_dir)["verified"] is True
