from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/stage003_account_label_plan.py"
SPEC = importlib.util.spec_from_file_location("stage003_account_label_plan", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_inputs(root: Path) -> tuple[dict[str, Path], dict[str, str]]:
    root.mkdir(parents=True)
    dates = ["2022-01-31", "2022-02-28", "2022-03-31", "2022-04-29"]
    ranking_rows = []
    feature_rows = []
    for date_index, eval_date in enumerate(dates[:-1]):
        for rank in range(1, 13):
            row = {
                "eval_date": eval_date,
                "product_vt_symbol": f"clean_{date_index}_{rank}.X",
                "pit_logistic_probability": 0.95 - rank / 100.0,
                "window_id": "wf_01",
                "a_rank": rank,
                "role": "top9" if rank < 10 else "candidate",
            }
            ranking_rows.append(row)
            if rank >= 10:
                feature_rows.append({**row, "feature_one": float(rank - 10)})
    formal_rows = []
    for date_index, eval_date in enumerate(dates):
        for rank in range(1, 12):
            formal_rows.append(
                {
                    "strategy": "formal_strategy",
                    "score_type": "formal_ai",
                    "eval_date": eval_date,
                    "product_vt_symbol": (
                        "fu.X" if rank == 11 else f"old_{date_index}_{rank}.X"
                    ),
                    "score": 1.0 - rank / 100.0,
                    "score_rank": rank,
                    "top_n": 11,
                }
            )

    files = {
        "feature_panel": root / "feature_panel.csv",
        "ranked_panel": root / "ranked_panel.csv",
        "formal_eligibility": root / "formal_eligibility.csv",
        "stage002_summary": root / "stage002_summary.json",
        "stage002_manifest": root / "stage002_manifest.json",
        "formal_current": root / "CURRENT.json",
        "old_builder": root / "old_builder.py",
        "old_completion": root / "old_completion.md",
        "spec": root / "spec.md",
    }
    pd.DataFrame(feature_rows).to_csv(files["feature_panel"], index=False)
    pd.DataFrame(ranking_rows).to_csv(files["ranked_panel"], index=False)
    pd.DataFrame(formal_rows).to_csv(files["formal_eligibility"], index=False)
    files["stage002_summary"].write_text(
        json.dumps(
            {
                "decision": "stage002_curve_features_pass_ready_for_account_label_contract",
                "all_gates_passed": True,
                "label_values_read": False,
                "strategy_backtest_runs": 0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    files["stage002_manifest"].write_text("{}\n", encoding="utf-8")
    files["formal_current"].write_text(
        json.dumps(
            {
                "activation_mode": "active",
                "release_id": "test_release",
                "strategy_version": "formal_strategy",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    files["old_builder"].write_text("# semantic source\n", encoding="utf-8")
    files["old_completion"].write_text("# completed old campaign\n", encoding="utf-8")
    files["spec"].write_text("frozen\n", encoding="utf-8")
    return files, {name: _sha256(path) for name, path in files.items()}


def test_stage003_publishes_deterministic_label_free_plan(tmp_path: Path) -> None:
    paths, hashes = _write_inputs(tmp_path / "inputs")
    runtime = {
        "minimum_free_bytes": 1024,
        "free_bytes": 4096,
        "disk_gate_passed": True,
        "production_head": "test_head",
        "expected_production_head": "test_head",
        "production_checkout_clean": True,
        "production_database_sha256": "new_database",
        "old_frozen_database_sha256": "old_database",
        "old_frozen_runtime_exists": False,
        "isolated_research_snapshot_frozen": False,
        "sqlite_integrity_check": None,
        "runtime_preflight_passed": False,
        "blocking_reasons": [
            "old_frozen_runtime_missing",
            "isolated_research_snapshot_not_frozen",
        ],
    }
    kwargs = {
        "input_paths": paths,
        "expected_sha256": hashes,
        "formal_release_id": "test_release",
        "official_strategy": "formal_strategy",
        "fixed_product": "fu.X",
        "expected_months": 3,
        "expected_rows": 9,
        "development_month_count": 2,
        "expected_development_rows": 6,
        "expected_holdout_rows": 3,
        "sentinel_month_indexes": (0, 1),
        "expected_development_jobs": 8,
        "runtime_preflight": runtime,
    }
    first = module.run_stage003(tmp_path / "first", **kwargs)
    second = module.run_stage003(tmp_path / "second", **kwargs)

    assert (
        first["decision"]
        == "stage003_account_label_plan_pass_smoke_blocked_on_runtime_preflight"
    )
    assert first["all_structural_gates_passed"] is True
    assert first["runtime_preflight_passed"] is False
    assert first["development_main_jobs"] == 6
    assert first["development_jobs_with_sentinels"] == 8
    assert first["sealed_holdout_jobs_created"] == 0
    assert first["label_values_read"] is False
    assert first["strategy_backtest_runs"] == 0
    assert first["smoke_job_ids"] == [
        "20220131_R10",
        "20220131_R10_A2",
        "20220228_R10",
        "20220228_R11",
    ]
    assert len(pd.read_csv(tmp_path / "first/full_feature_split.csv")) == 9
    assert len(pd.read_csv(tmp_path / "first/development_eligibility_audit.csv")) == 6
    first_manifest = json.loads((tmp_path / "first/artifact_manifest.json").read_text())
    second_manifest = json.loads((tmp_path / "second/artifact_manifest.json").read_text())
    assert first_manifest == second_manifest

