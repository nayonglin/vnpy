from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sqlite3
import sys

import pandas as pd
import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools/stage001_pit_listing_membership.py"
)
SPEC = importlib.util.spec_from_file_location(
    "stage001_pit_listing_membership", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


PRODUCT_CODES = ["AA", "BB", "CC", "DD", "EE", "FF", "GG", "HH", "II", "JJ", "KK", "LL"]
PRODUCTS = [f"{code}.DCE" for code in PRODUCT_CODES]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            "create table dbbardata ("
            "symbol text, exchange text, datetime text, interval text, "
            "close_price real, open_interest real, volume real)"
        )
        rows = []
        for code in PRODUCT_CODES:
            first = "2020-01-01 00:00:00"
            if code in {"CC", "GG"}:
                first = "2022-08-01 00:00:00"
            rows.append((f"{code}2205", "DCE", first, "d", 100.0, 10.0, 10.0))
        connection.executemany(
            "insert into dbbardata values (?, ?, ?, ?, ?, ?, ?)", rows
        )


def _write_inputs(root: Path) -> tuple[dict[str, Path], dict[str, str]]:
    database = root / "database.db"
    ranking_path = root / "ranking.csv"
    formal_path = root / "formal.csv"
    spec_path = root / "spec.md"
    core_path = Path(__file__).resolve().parents[1] / "tools/pit_listing_eligibility.py"
    _write_database(database)

    ranking_rows = []
    formal_rows = []
    for eval_date in ["2022-07-29", "2023-09-28"]:
        order = PRODUCTS if eval_date == "2022-07-29" else list(reversed(PRODUCTS))
        for index, product in enumerate(order, start=1):
            ranking_rows.append(
                {
                    "eval_date": eval_date,
                    "product_vt_symbol": product,
                    "score": 1.0 - 0.01 * index,
                    "score_rank": index,
                    "score_type": "formal_rank",
                }
            )
        for index, product in enumerate(order[:10], start=1):
            formal_rows.append(
                {
                    "strategy": "formal",
                    "score_type": "formal_top10",
                    "eval_date": eval_date,
                    "product_vt_symbol": product,
                    "score": 1.0 - 0.01 * index,
                    "score_rank": index,
                    "top_n": 11,
                }
            )
        formal_rows.append(
            {
                "strategy": "formal",
                "score_type": "fixed_fu",
                "eval_date": eval_date,
                "product_vt_symbol": "fu.SHFE",
                "score": 0.0,
                "score_rank": 11,
                "top_n": 11,
            }
        )
    pd.DataFrame(ranking_rows).to_csv(ranking_path, index=False)
    pd.DataFrame(formal_rows).to_csv(formal_path, index=False)
    spec_path.write_text("frozen\n", encoding="utf-8")
    paths = {
        "database": database,
        "formal_full_ranking": ranking_path,
        "formal_eligibility": formal_path,
        "spec": spec_path,
        "core": core_path,
    }
    return paths, {name: _sha256(path) for name, path in paths.items()}


def test_stage001_publishes_complete_read_only_audit(tmp_path: Path) -> None:
    inputs, expected = _write_inputs(tmp_path)
    before = {name: _sha256(path) for name, path in inputs.items()}
    output = tmp_path / "out"

    result = MODULE.run_stage001(
        output,
        input_paths=inputs,
        expected_sha256=expected,
        expected_ranked_products=12,
        expected_ranking_months=2,
        unchanged_from=pd.Timestamp("2023-09-28"),
    )

    assert result["decision"] == MODULE.PASS_DECISION
    assert result["all_gates_passed"] is True
    assert result["changed_months"] == 1
    assert result["unavailable_formal_top10_slots"] == 2
    assert result["candidate_unavailable_count"] == 0
    assert result["database_query_only"] is True
    assert before == {name: _sha256(path) for name, path in inputs.items()}
    assert set(path.name for path in output.iterdir()) == {
        "artifact_manifest.json",
        "candidate_eligibility.csv",
        "first_available_dates.csv",
        "membership_audit.csv",
        "report.md",
        "stage001_summary.json",
    }


def test_stage001_rejects_input_drift_before_publishing(tmp_path: Path) -> None:
    inputs, expected = _write_inputs(tmp_path)
    expected["formal_full_ranking"] = "0" * 64

    with pytest.raises(MODULE.Stage001Error, match="input_sha256_drift:formal_full_ranking"):
        MODULE.run_stage001(
            tmp_path / "out",
            input_paths=inputs,
            expected_sha256=expected,
            expected_ranked_products=12,
            expected_ranking_months=2,
            unchanged_from=pd.Timestamp("2023-09-28"),
        )
    assert not (tmp_path / "out").exists()


def test_stage001_never_overwrites_existing_output(tmp_path: Path) -> None:
    inputs, expected = _write_inputs(tmp_path)
    output = tmp_path / "out"
    output.mkdir()

    with pytest.raises(MODULE.Stage001Error, match="stage001_output_already_exists"):
        MODULE.run_stage001(
            output,
            input_paths=inputs,
            expected_sha256=expected,
            expected_ranked_products=12,
            expected_ranking_months=2,
            unchanged_from=pd.Timestamp("2023-09-28"),
        )
