from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/stage002_physical_features.py"
SPEC = importlib.util.spec_from_file_location("stage002_physical_features", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _panel() -> pd.DataFrame:
    dates = ["2024-01-31", "2024-02-29", "2024-03-29"]
    products = ["MA.CZCE", "rb.SHFE", "au.SHFE", "jm.DCE"]
    rows: list[dict[str, object]] = []
    for month_index, eval_date in enumerate(dates):
        for rank, product in zip(range(10, 14), products, strict=True):
            basis_available = True
            member_available = True
            if month_index == 1 and rank == 12:
                member_available = False
            if month_index == 1 and rank == 13:
                basis_available = False
            if month_index == 2 and rank == 10:
                member_available = False
            offset = float(rank - 10)
            rows.append(
                {
                    "eval_date": eval_date,
                    "product_vt_symbol": product,
                    "pit_logistic_probability": 0.80 - month_index * 0.01 - offset * 0.02,
                    "window_id": f"wf_{month_index + 1:02d}",
                    "a_rank": rank,
                    "role": "a_rank10" if rank == 10 else "challenger",
                    "basis_available": basis_available,
                    "basis_dom_rate": 0.10 + month_index + offset * 0.10 if basis_available else None,
                    "basis_near_rate": 0.05 + month_index + offset * 0.05 if basis_available else None,
                    "member_available": member_available,
                    "member_net_position_ratio": 0.01 + offset * 0.02 if member_available else None,
                    "member_net_position_change_ratio": 0.001 + offset * 0.003 if member_available else None,
                    "member_turnover_pressure_ratio": 1.0 + offset * 0.25 if member_available else None,
                    "future_return": "must_not_be_read",
                }
            )
    return pd.DataFrame(rows)


def test_build_features_uses_complete_active_months_and_exact_rank10_deltas() -> None:
    artifacts = module.build_feature_artifacts(
        _panel(), development_months=1, development_oos_months=1
    )

    candidate = artifacts["candidate_panel"]
    eligible = artifacts["eligible_panel"]
    month = artifacts["month_eligibility"]

    assert len(candidate) == 12
    assert len(eligible) == 4
    assert month["active_month"].tolist() == [True, False, False]
    assert month["model_eligible_rows"].tolist() == [4, 0, 0]
    assert candidate.loc[candidate["model_eligible"], "eval_date"].nunique() == 1
    assert candidate.loc[~candidate["model_eligible"], module.MODEL_FEATURES].isna().all().all()

    anchor = eligible[eligible["a_rank"].eq(10)].iloc[0]
    assert anchor[module.MODEL_FEATURES].eq(0.0).all()
    challenger = eligible[eligible["a_rank"].eq(11)].iloc[0]
    assert challenger["formal_probability_delta_vs_rank10"] == pytest.approx(-0.02)
    assert challenger["basis_dom_rate_delta_vs_rank10"] == pytest.approx(0.10)
    assert challenger["basis_near_rate_delta_vs_rank10"] == pytest.approx(0.05)
    assert challenger["member_net_position_ratio_delta_vs_rank10"] == pytest.approx(0.02)
    assert challenger["member_net_position_change_ratio_delta_vs_rank10"] == pytest.approx(0.003)
    assert challenger["member_turnover_pressure_ratio_delta_vs_rank10"] == pytest.approx(0.25)
    assert not any("warehouse" in column for column in module.MODEL_FEATURES)


def _write_inputs(root: Path) -> tuple[dict[str, Path], dict[str, str]]:
    root.mkdir(parents=True)
    paths = {
        "feature_panel": root / "physical_feature_panel.csv",
        "stage001_summary": root / "stage001_summary.json",
        "family_coverage": root / "family_coverage.csv",
        "stage001_manifest": root / "stage001_manifest.json",
        "preregistration": root / "stage002_preregistration.md",
        "independent_review": root / "stage002_review.md",
        "review_decision": root / "stage002_review_decision.json",
    }
    _panel().to_csv(paths["feature_panel"], index=False)
    paths["stage001_summary"].write_text(
        json.dumps(
            {
                "decision": "stage001_physical_positioning_coverage_pass_ready_for_feature_preregistration",
                "eligible_families": ["basis", "member"],
                "diagnostic_only_families": ["warehouse"],
                "pit_source_date_violation_rows": 0,
                "label_columns_read": [],
                "label_values_read": False,
                "sealed_holdout_files_read": [],
                "trains_model": False,
                "model_fit_count": 0,
                "strategy_backtest_runs": 0,
                "ctp_connected": False,
                "order_api_called_count": 0,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {"family": "basis", "eligible_for_feature_preregistration": True},
            {"family": "member", "eligible_for_feature_preregistration": True},
            {"family": "warehouse", "eligible_for_feature_preregistration": False},
        ]
    ).to_csv(paths["family_coverage"], index=False)
    paths["preregistration"].write_text("frozen stage002 contract\n", encoding="utf-8")
    paths["independent_review"].write_text("independent review\n", encoding="utf-8")
    paths["stage001_manifest"].write_text(
        json.dumps(
            {
                "physical_feature_panel.csv.gz": _sha256(paths["feature_panel"]),
                "stage001_summary.json": _sha256(paths["stage001_summary"]),
                "family_coverage.csv": _sha256(paths["family_coverage"]),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    review_sha = _sha256(paths["independent_review"])
    paths["review_decision"].write_text(
        json.dumps(
            {
                "decision": "ALLOW_STAGE002_TDD_IMPLEMENTATION_ONLY",
                "allowed": True,
                "severity": {"P0": 0, "P1": 0, "P2": 0, "P3": 2},
                "review_sha256": review_sha,
                "preregistration_sha256": _sha256(paths["preregistration"]),
                "stage001_manifest_sha256": _sha256(paths["stage001_manifest"]),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return paths, {name: _sha256(path) for name, path in paths.items()}


def test_stage002_is_deterministic_and_reports_both_correlation_scopes(tmp_path: Path) -> None:
    paths, hashes = _write_inputs(tmp_path / "inputs")
    expected_counts = {
        "candidate_rows": 12,
        "candidate_months": 3,
        "candidate_products": 4,
        "active_months": 1,
        "model_eligible_rows": 4,
        "rank10_anchors": 1,
        "eligible_challengers": 3,
        "segment_active_months": [1, 0, 0],
        "segment_eligible_rows": [4, 0, 0],
        "active_months_by_year": {"2024": 1},
    }
    kwargs = {
        "input_paths": paths,
        "expected_sha256": hashes,
        "expected_counts": expected_counts,
        "development_months": 1,
        "development_oos_months": 1,
        "minimum_challenger_unique": 2,
        "minimum_challenger_nonzero": 2,
    }

    first = module.run_stage002(tmp_path / "first", **kwargs)
    second = module.run_stage002(tmp_path / "second", **kwargs)

    assert first["decision"] == "stage002_physical_features_pass_ready_for_training_contract_preregistration"
    assert first["technical_gate_pass"] is True
    assert first["panel_columns_read"] == module.PANEL_COLUMNS
    assert first["label_columns_read"] == []
    assert first["label_values_read"] is False
    assert first["model_fit_count"] == 0
    assert first["strategy_backtest_runs"] == 0
    assert json.loads((tmp_path / "first/artifact_manifest.json").read_text()) == json.loads(
        (tmp_path / "second/artifact_manifest.json").read_text()
    )
    correlations = pd.read_csv(tmp_path / "first/feature_correlations.csv")
    assert set(correlations["scope"]) == {"eligible_all", "eligible_challengers"}
    product = pd.read_csv(tmp_path / "first/product_eligibility.csv")
    assert len(product) == 4
    assert "eligible_challenger_rows" in product.columns
    candidate = pd.read_csv(tmp_path / "first/candidate_physical_feature_panel.csv")
    assert "future_return" not in candidate.columns


def test_stage002_fails_closed_on_preregistration_hash_drift(tmp_path: Path) -> None:
    paths, hashes = _write_inputs(tmp_path / "inputs")
    paths["preregistration"].write_text("changed after independent review\n", encoding="utf-8")

    with pytest.raises(module.Stage002Error, match="input_sha256_drift:preregistration"):
        module.run_stage002(
            tmp_path / "output",
            input_paths=paths,
            expected_sha256=hashes,
            expected_counts={},
            development_months=1,
            development_oos_months=1,
            minimum_challenger_unique=2,
            minimum_challenger_nonzero=2,
        )
