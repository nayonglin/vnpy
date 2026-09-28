from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3

import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/stage001_curve_coverage.py"
SPEC = importlib.util.spec_from_file_location("stage001_curve_coverage", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_inputs(root: Path) -> tuple[dict[str, Path], dict[str, str]]:
    root.mkdir(parents=True)
    panel_rows = []
    for eval_date, window_id in [("2024-01-31", "wf_01"), ("2024-02-29", "wf_02")]:
        for rank, (product, probability) in enumerate(
            [("MA.CZCE", 0.9), ("rb.SHFE", 0.8)], start=1
        ):
            panel_rows.append(
                {
                    "eval_date": eval_date,
                    "product_vt_symbol": product,
                    "pit_logistic_probability": probability,
                    "window_id": window_id,
                    "a_rank": rank,
                    "role": "top9" if rank == 1 else "a_rank10",
                    "future_account_return_delta": "must_not_be_read",
                }
            )
    panel = root / "ranked.csv"
    pd.DataFrame(panel_rows).to_csv(panel, index=False)

    database = root / "database.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE dbbardata (
                symbol TEXT NOT NULL,
                exchange TEXT NOT NULL,
                datetime TEXT NOT NULL,
                interval TEXT NOT NULL,
                close_price REAL NOT NULL,
                open_interest REAL NOT NULL,
                volume REAL NOT NULL
            )
            """
        )
        rows = []
        for eval_date in ["2024-01-31", "2024-02-29"]:
            for symbol, exchange, close in [
                ("MA403", "CZCE", 2400.0),
                ("MA405", "CZCE", 2420.0),
                ("MA409", "CZCE", 2450.0),
                ("rb2403", "SHFE", 3800.0),
                ("rb2405", "SHFE", 3820.0),
                ("rb2410", "SHFE", 3860.0),
            ]:
                rows.append((symbol, exchange, eval_date, "d", close, 1000.0, 500.0))
        connection.executemany(
            "INSERT INTO dbbardata VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    spec = root / "spec.md"
    spec.write_text("frozen\n", encoding="utf-8")
    paths = {"ranked_panel": panel, "database": database, "spec": spec}
    return paths, {name: _sha256(path) for name, path in paths.items()}


def test_stage001_reads_only_frozen_columns_and_is_deterministic(tmp_path: Path) -> None:
    paths, hashes = _write_inputs(tmp_path / "inputs")
    kwargs = {
        "input_paths": paths,
        "expected_sha256": hashes,
        "expected_rows": 4,
        "expected_months": 2,
        "expected_products": 2,
        "minimum_contracts": 3,
    }

    first = module.run_stage001(tmp_path / "first", **kwargs)
    second = module.run_stage001(tmp_path / "second", **kwargs)

    assert first["decision"] == "stage001_curve_coverage_pass_ready_for_feature_preregistration"
    assert first["panel_columns_read"] == [
        "eval_date",
        "product_vt_symbol",
        "pit_logistic_probability",
        "window_id",
        "a_rank",
        "role",
    ]
    assert first["database_columns_read"] == [
        "symbol",
        "exchange",
        "datetime",
        "interval",
        "close_price",
        "open_interest",
        "volume",
    ]
    assert first["label_columns_read"] == []
    assert first["strategy_backtest_runs"] == 0
    assert first["trains_model"] is False
    assert first["database_open_mode"] == "read_only"
    assert json.loads((tmp_path / "first/artifact_manifest.json").read_text()) == json.loads(
        (tmp_path / "second/artifact_manifest.json").read_text()
    )
    assert len(pd.read_csv(tmp_path / "first/eligible_contract_snapshot.csv.gz")) == 12
