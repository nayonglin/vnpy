from __future__ import annotations

import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path

import pandas as pd


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools/stage001_pit_contract_return_coverage.py"
)
SPEC = importlib.util.spec_from_file_location(
    "stage001_pit_contract_return_coverage", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_database(path: Path, *, omit_c_date: str | None = None) -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        """
        create table dbbardata (
            id integer primary key,
            symbol text not null,
            exchange text not null,
            datetime text not null,
            interval text not null,
            volume real not null,
            turnover real not null,
            open_interest real not null,
            open_price real not null,
            high_price real not null,
            low_price real not null,
            close_price real not null
        )
        """
    )
    rows = []
    row_id = 1
    for product_index, code in enumerate(["a", "b", "c"], start=1):
        for day_index, date in enumerate(
            ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
            start=1,
        ):
            if code == "c" and date == omit_c_date:
                continue
            close = 100.0 * product_index + day_index
            rows.append(
                (
                    row_id,
                    f"{code}2401",
                    "X",
                    f"{date} 00:00:00",
                    "d",
                    1000.0,
                    0.0,
                    500.0,
                    close,
                    close,
                    close,
                    close,
                )
            )
            row_id += 1
    connection.executemany(
        "insert into dbbardata values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    connection.commit()
    connection.close()


def _inputs(tmp_path: Path, *, omit_c_date: str | None = None):
    database = tmp_path / "database.db"
    _write_database(database, omit_c_date=omit_c_date)
    ranking = tmp_path / "formal.csv"
    pd.DataFrame(
        {
            "eval_date": ["2024-01-05"] * 3,
            "product_vt_symbol": ["a.X", "b.X", "c.X"],
            "score_rank": [1, 2, 3],
        }
    ).to_csv(ranking, index=False)
    base = tmp_path / "base.csv"
    pd.DataFrame(
        {
            "eval_date": ["2024-01-05"],
            "product_vt_symbol": ["c.X"],
            "score_rank": [3],
            "split": ["development"],
        }
    ).to_csv(base, index=False)
    spec = tmp_path / "spec.md"
    spec.write_text("frozen test spec\n", encoding="utf-8")
    paths = {
        "database": database,
        "formal_full_ranking": ranking,
        "base_feature_panel": base,
        "spec": spec,
    }
    identities = {key: _sha(path) for key, path in paths.items()}
    return paths, identities


def _run(tmp_path: Path, *, omit_c_date: str | None = None):
    paths, identities = _inputs(tmp_path, omit_c_date=omit_c_date)
    output = tmp_path / "output"
    summary = module.run_stage001(
        output,
        input_paths=paths,
        expected_sha256=identities,
        window_days=3,
        top_rank_count=2,
        expected_candidate_rows=1,
        expected_product_count=3,
        expected_month_count=1,
        expected_split_counts={"development": 1},
    )
    return output, paths, identities, summary


def test_run_publishes_pass_package_without_mutating_database(tmp_path: Path) -> None:
    output, paths, identities, summary = _run(tmp_path)

    assert summary["decision"] == module.core.PASS_DECISION
    assert summary["input_identity_stable"] is True
    assert _sha(paths["database"]) == identities["database"]
    assert summary["label_files_read"] == []
    assert summary["trains_model"] is False
    assert summary["runs_backtest"] is False
    assert summary["ctp_connected"] is False
    assert summary["order_api_called_count"] == 0
    assert (output / "product_daily_returns.csv.gz").is_file()
    assert (output / "coverage_by_eval_product.csv").is_file()
    assert (output / "missing_required_cells.csv").is_file()

    manifest = json.loads((output / "artifact_manifest.json").read_text())
    assert set(manifest) == {
        "coverage_by_eval_product.csv",
        "missing_required_cells.csv",
        "product_daily_returns.csv.gz",
        "report.md",
        "source_product_summary.csv",
        "stage001_summary.json",
        "window_audit.csv",
    }
    assert all(_sha(output / name) == digest for name, digest in manifest.items())


def test_run_publishes_fail_closed_package_with_missing_detail(tmp_path: Path) -> None:
    output, _, _, summary = _run(tmp_path, omit_c_date="2024-01-04")

    assert summary["decision"] == module.core.FAIL_DECISION
    assert summary["all_gates_passed"] is False
    assert summary["missing_required_cells"] >= 1
    missing = pd.read_csv(output / "missing_required_cells.csv")
    assert "c.X" in set(missing["product_vt_symbol"])
    assert (output / "product_daily_returns.csv.gz").is_file()
    report = (output / "report.md").read_text(encoding="utf-8")
    assert "不训练模型" in report
    assert module.core.FAIL_DECISION in report


def test_run_rejects_input_identity_drift_before_reading_database(tmp_path: Path) -> None:
    paths, identities = _inputs(tmp_path)
    paths["spec"].write_text("changed\n", encoding="utf-8")

    try:
        module.run_stage001(
            tmp_path / "output",
            input_paths=paths,
            expected_sha256=identities,
            window_days=3,
            top_rank_count=2,
            expected_candidate_rows=1,
            expected_product_count=3,
            expected_month_count=1,
            expected_split_counts={"development": 1},
        )
    except module.Stage001Error as exc:
        assert str(exc) == "input_sha256_drift:spec"
    else:
        raise AssertionError("identity drift must fail closed")
    assert not (tmp_path / "output").exists()


def test_run_refuses_to_overwrite_existing_output(tmp_path: Path) -> None:
    output, paths, identities, _ = _run(tmp_path)

    try:
        module.run_stage001(
            output,
            input_paths=paths,
            expected_sha256=identities,
            window_days=3,
            top_rank_count=2,
            expected_candidate_rows=1,
            expected_product_count=3,
            expected_month_count=1,
            expected_split_counts={"development": 1},
        )
    except module.Stage001Error as exc:
        assert str(exc) == "stage001_output_already_exists"
    else:
        raise AssertionError("existing output must not be overwritten")
