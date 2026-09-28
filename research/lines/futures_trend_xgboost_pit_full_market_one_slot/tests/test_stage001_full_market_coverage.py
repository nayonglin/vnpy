from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import sys

import pandas as pd
import pytest


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import full_market_coverage as core  # noqa: E402
import stage001_full_market_coverage as runner  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture_inputs(tmp_path: Path) -> tuple[dict[str, Path], core.CoverageConfig]:
    products = ["A.DCE", "B.DCE", "X.SHFE"]
    dates = pd.date_range("2024-01-02", "2024-01-04", freq="D")
    mapping_rows: list[dict[str, object]] = []
    bar_rows: list[dict[str, object]] = []
    for product in products:
        code, exchange = product.split(".")
        for index, date in enumerate(dates, start=1):
            contract = f"{code}240{index}"
            mapping_rows.append(
                {
                    "date": date,
                    "continuous_symbol_vt": product,
                    "main_contract_vt": f"{contract}.{exchange}",
                    "exchange": exchange,
                }
            )
            bar_rows.append(
                {
                    "symbol": contract,
                    "exchange": exchange,
                    "datetime": date.strftime("%Y-%m-%d 00:00:00"),
                    "interval": "d",
                    "close_price": 100.0,
                    "volume": 1000.0,
                    "open_interest": 500.0,
                }
            )
        for suffix in ("2405", "2409"):
            bar_rows.append(
                {
                    "symbol": f"{code}{suffix}",
                    "exchange": exchange,
                    "datetime": "2024-01-04 00:00:00",
                    "interval": "d",
                    "close_price": 101.0,
                    "volume": 900.0,
                    "open_interest": 400.0,
                }
            )

    ranking = pd.DataFrame(
        [
            {
                "eval_date": "2024-01-04",
                "product_vt_symbol": "A.DCE",
                "score": 0.9,
                "score_rank": 1,
                "score_type": "formal",
            },
            {
                "eval_date": "2024-01-04",
                "product_vt_symbol": "B.DCE",
                "score": 0.8,
                "score_rank": 2,
                "score_type": "formal",
            },
        ]
    )
    metadata = pd.DataFrame(
        [
            {
                "vt_symbol": product,
                "symbol_kind": "product_cont",
                "price_tick": 1.0,
                "volume_multiple": 10.0,
                "fetched_at": "2099-01-01",
            }
            for product in products
        ]
    )

    paths = {
        "formal_ranking": tmp_path / "formal.csv",
        "mapping": tmp_path / "mapping.csv",
        "metadata": tmp_path / "metadata.csv",
        "database": tmp_path / "database.db",
        "spec": tmp_path / "spec.md",
    }
    ranking.to_csv(paths["formal_ranking"], index=False)
    pd.DataFrame(mapping_rows).to_csv(paths["mapping"], index=False)
    metadata.to_csv(paths["metadata"], index=False)
    paths["spec"].write_text("frozen test spec\n", encoding="utf-8")
    with sqlite3.connect(paths["database"]) as connection:
        pd.DataFrame(bar_rows).to_sql("dbbardata", connection, index=False)

    config = core.CoverageConfig(
        eval_start=pd.Timestamp("2024-01-04"),
        eval_end=pd.Timestamp("2024-01-04"),
        expected_months=1,
        expected_ranks_per_month=2,
        expected_static_products=2,
        replacement_rank=2,
        minimum_mapping_days=3,
        minimum_valid_close_days=3,
        activity_window_days=2,
        minimum_activity_ratio=1.0,
        minimum_curve_contracts=2,
        minimum_total_eligible=3,
        minimum_action_months=1,
        minimum_challengers=1,
        capital=1_000.0,
        conservative_margin_ratio=0.15,
    )
    return paths, config


def test_runner_publishes_a_reproducible_zero_label_audit(tmp_path: Path) -> None:
    """Catches publishing partial output or silently touching model/label operations."""
    paths, config = _fixture_inputs(tmp_path)
    expected = {name: _sha256(path) for name, path in paths.items()}
    output = tmp_path / "stage001"

    summary = runner.run_stage001(
        output_dir=output,
        input_paths=paths,
        expected_sha256=expected,
        config=config,
    )

    assert summary["decision"] == core.PASS_DECISION
    assert summary["database_open_mode"] == "read_only"
    assert summary["label_columns_read"] == []
    assert summary["label_values_read"] is False
    assert summary["model_fit_count"] == 0
    assert summary["model_predict_count"] == 0
    assert summary["strategy_backtest_runs"] == 0
    assert summary["ctp_connected"] is False
    assert summary["order_api_called_count"] == 0
    assert summary["input_identity_stable"] is True
    assert summary["repeat_exact"] is True
    assert output.is_dir()
    assert not output.with_name("stage001.tmp").exists()

    manifest = json.loads((output / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert manifest == {
        name: _sha256(output / name)
        for name in sorted(manifest)
    }


def test_runner_fails_closed_on_input_hash_drift(tmp_path: Path) -> None:
    """Catches using a changed market input under the frozen Stage001 identity."""
    paths, config = _fixture_inputs(tmp_path)
    expected = {name: _sha256(path) for name, path in paths.items()}
    expected["mapping"] = "0" * 64
    output = tmp_path / "stage001"

    with pytest.raises(runner.Stage001Error, match="input_sha256_drift:mapping"):
        runner.run_stage001(
            output_dir=output,
            input_paths=paths,
            expected_sha256=expected,
            config=config,
        )

    assert not output.exists()
    assert not output.with_name("stage001.tmp").exists()

