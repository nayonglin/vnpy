from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/stage001_physical_positioning_coverage.py"
SPEC = importlib.util.spec_from_file_location("stage001_physical_positioning_coverage", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _member_row(date: str, product: str, *, long_oi: float = 120.0, short_oi: float = 80.0) -> dict[str, object]:
    return {
        "date": date,
        "symbol": product,
        "variety": product,
        "vol_top20": 400.0,
        "long_open_interest_top20": long_oi,
        "short_open_interest_top20": short_oi,
        "long_open_interest_chg_top20": 12.0,
        "short_open_interest_chg_top20": 8.0,
    }


def test_feature_panel_uses_only_t1_visible_fresh_rows() -> None:
    panel = pd.DataFrame(
        [
            {
                "eval_date": "2024-01-31",
                "product_vt_symbol": "MA.CZCE",
                "pit_logistic_probability": 0.6,
                "window_id": "wf_01",
                "a_rank": 10,
                "role": "a_rank10",
            }
        ]
    )
    basis = pd.DataFrame(
        [
            {"date": "2024-01-30", "symbol": "MA", "dom_basis_rate": 0.10, "near_basis_rate": 0.08},
            {"date": "2024-01-31", "symbol": "MA", "dom_basis_rate": 9.90, "near_basis_rate": 9.80},
        ]
    )
    warehouse = pd.DataFrame(
        [
            {
                "date": "2024-01-23",
                "product_code": "MA",
                "warehouse_receipt_quantity": 100.0,
                "warehouse_receipt_change": 5.0,
            }
        ]
    )
    member = pd.DataFrame(
        [
            _member_row("2024-01-30", "MA"),
            _member_row("2024-01-31", "MA", long_oi=1000.0, short_oi=1.0),
        ]
    )

    result = module.build_physical_feature_panel(
        panel,
        basis,
        warehouse,
        member,
        max_source_age_days=7,
    )

    row = result.iloc[0]
    assert row["basis_dom_rate"] == pytest.approx(0.10)
    assert row["member_net_position_ratio"] == pytest.approx(0.20)
    assert row["basis_feature_date"] == pd.Timestamp("2024-01-30")
    assert row["member_feature_date"] == pd.Timestamp("2024-01-30")
    assert bool(row["basis_available"]) is True
    assert bool(row["member_available"]) is True
    assert bool(row["warehouse_available"]) is False
    assert pd.isna(row["warehouse_receipt_quantity"])


def _write_inputs(root: Path) -> tuple[dict[str, Path], dict[str, str]]:
    root.mkdir(parents=True)
    eval_dates = ["2024-01-31", "2024-02-29", "2024-03-29"]
    products = ["MA.CZCE", "rb.SHFE", "au.SHFE", "jm.DCE"]
    ranks = [9, 10, 11, 12]
    panel_rows: list[dict[str, object]] = []
    basis_rows: list[dict[str, object]] = []
    warehouse_rows: list[dict[str, object]] = []
    member_rows: list[dict[str, object]] = []
    for month_index, eval_date_text in enumerate(eval_dates, start=1):
        eval_date = pd.Timestamp(eval_date_text)
        prior_date = eval_date - pd.Timedelta(days=1)
        for rank, product in zip(ranks, products, strict=True):
            product_code = product.split(".", 1)[0].upper()
            panel_rows.append(
                {
                    "eval_date": eval_date_text,
                    "product_vt_symbol": product,
                    "pit_logistic_probability": 0.90 - rank / 100.0,
                    "window_id": f"wf_{month_index:02d}",
                    "a_rank": rank,
                    "role": "top9" if rank < 10 else ("a_rank10" if rank == 10 else "challenger"),
                    "future_account_return_delta": "must_not_be_read",
                }
            )
            basis_rows.extend(
                [
                    {
                        "date": prior_date.date().isoformat(),
                        "symbol": product_code,
                        "dom_basis_rate": rank / 100.0,
                        "near_basis_rate": rank / 200.0,
                    },
                    {
                        "date": eval_date_text,
                        "symbol": product_code,
                        "dom_basis_rate": 99.0,
                        "near_basis_rate": 99.0,
                    },
                ]
            )
            member_rows.append(_member_row(prior_date.date().isoformat(), product_code))
            if rank == 10:
                warehouse_rows.append(
                    {
                        "date": prior_date.date().isoformat(),
                        "product_code": product_code,
                        "warehouse_receipt_quantity": 100.0 + month_index,
                        "warehouse_receipt_change": 1.0,
                    }
                )

    paths = {
        "ranked_panel": root / "ranked_panel.csv",
        "basis_2020_2022": root / "basis_a.csv",
        "basis_2023_2026": root / "basis_b.csv",
        "warehouse_2020_2022": root / "warehouse_a.csv",
        "warehouse_2023_2026": root / "warehouse_b.csv",
        "member_rank_raw": root / "member.csv",
        "spec": root / "spec.md",
    }
    pd.DataFrame(panel_rows).to_csv(paths["ranked_panel"], index=False)
    midpoint = len(basis_rows) // 2
    pd.DataFrame(basis_rows[:midpoint]).to_csv(paths["basis_2020_2022"], index=False)
    pd.DataFrame(basis_rows[midpoint:]).to_csv(paths["basis_2023_2026"], index=False)
    warehouse = pd.DataFrame(warehouse_rows)
    warehouse.iloc[:1].to_csv(paths["warehouse_2020_2022"], index=False)
    warehouse.iloc[1:].to_csv(paths["warehouse_2023_2026"], index=False)
    pd.DataFrame(member_rows).to_csv(paths["member_rank_raw"], index=False)
    paths["spec"].write_text("frozen coverage contract\n", encoding="utf-8")
    return paths, {name: _sha256(path) for name, path in paths.items()}


def test_stage001_is_deterministic_and_admits_only_qualified_families(tmp_path: Path) -> None:
    paths, hashes = _write_inputs(tmp_path / "inputs")
    kwargs = {
        "input_paths": paths,
        "expected_sha256": hashes,
        "expected_rows": 12,
        "expected_months": 3,
        "expected_products": 4,
        "development_months": 2,
        "minimum_family_row_coverage": 0.50,
        "minimum_active_months": 2,
        "minimum_development_active_months": 1,
        "minimum_active_months_per_year": 1,
        "minimum_eligible_families": 2,
    }

    first = module.run_stage001(tmp_path / "first", **kwargs)
    second = module.run_stage001(tmp_path / "second", **kwargs)

    assert first["decision"] == "stage001_physical_positioning_coverage_pass_ready_for_feature_preregistration"
    assert first["eligible_families"] == ["basis", "member"]
    assert first["diagnostic_only_families"] == ["warehouse"]
    assert first["panel_columns_read"] == [
        "eval_date",
        "product_vt_symbol",
        "pit_logistic_probability",
        "window_id",
        "a_rank",
        "role",
    ]
    assert first["label_columns_read"] == []
    assert first["label_values_read"] is False
    assert first["trains_model"] is False
    assert first["strategy_backtest_runs"] == 0
    assert json.loads((tmp_path / "first/artifact_manifest.json").read_text()) == json.loads(
        (tmp_path / "second/artifact_manifest.json").read_text()
    )
    feature_panel = pd.read_csv(tmp_path / "first/physical_feature_panel.csv.gz")
    assert len(feature_panel) == 12
    available_basis = feature_panel[feature_panel["basis_available"].astype(bool)]
    assert (pd.to_datetime(available_basis["basis_feature_date"]) < pd.to_datetime(available_basis["eval_date"])).all()
    assert available_basis["basis_dom_rate"].max() < 1.0


def test_stage001_fails_closed_on_input_hash_drift(tmp_path: Path) -> None:
    paths, hashes = _write_inputs(tmp_path / "inputs")
    paths["spec"].write_text("changed after freeze\n", encoding="utf-8")

    with pytest.raises(module.Stage001Error, match="input_sha256_drift:spec"):
        module.run_stage001(
            tmp_path / "output",
            input_paths=paths,
            expected_sha256=hashes,
            expected_rows=12,
            expected_months=3,
            expected_products=4,
            development_months=2,
            minimum_family_row_coverage=0.50,
            minimum_active_months=2,
            minimum_development_active_months=1,
            minimum_active_months_per_year=1,
            minimum_eligible_families=2,
        )
