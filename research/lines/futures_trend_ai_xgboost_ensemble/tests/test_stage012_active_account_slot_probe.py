from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/stage012_active_account_slot_probe.py"


def load_module():
    assert MODULE_PATH.exists(), "Stage012 active account slot probe is not implemented"
    spec = importlib.util.spec_from_file_location("stage012_active_account_slot_probe", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_probe_spec_accepts_only_stage011_mechanical_selection() -> None:
    module = load_module()
    selection = {
        "decision": "stage011_first_active_marginal_month_qualified",
        "eval_date": "2022-05-31",
        "next_eval_date": "2022-06-30",
        "baseline_rank": 10,
        "challenger_ranks": [12, 13],
    }

    spec = module.probe_spec_from_selection(selection)

    assert spec["eval_date"] == "2022-05-31"
    assert spec["end"] == pd.Timestamp("2022-06-30")
    assert spec["candidate_ranks"] == {"A": 10, "C12": 12, "C13": 13}


def test_probe_spec_rejects_performance_selected_rank() -> None:
    module = load_module()
    selection = {
        "decision": "stage011_first_active_marginal_month_qualified",
        "eval_date": "2022-05-31",
        "next_eval_date": "2022-06-30",
        "baseline_rank": 10,
        "challenger_ranks": [12, 14],
    }

    with pytest.raises(RuntimeError, match="stage011_selection_drift"):
        module.probe_spec_from_selection(selection)


def test_worker_environment_uses_unique_stage012_directories() -> None:
    module = load_module()

    a = module.worker_environment({}, Path("/tmp/stage012"), "A1")
    c = module.worker_environment({}, Path("/tmp/stage012"), "C12")

    assert a["TMPDIR"] != c["TMPDIR"]
    assert a["MPLCONFIGDIR"] != c["MPLCONFIGDIR"]


def test_startup_identity_includes_sitecustomize_and_all_effective_pth() -> None:
    module = load_module()

    files = module.startup_hook_identity_files()

    assert files["python_sitecustomize"].resolve() == (
        module.WORKSPACE_ROOT / "sitecustomize.py"
    ).resolve()
    pth_names = {path.name for key, path in files.items() if key.startswith("python_site_pth/")}
    assert {"_editable_impl_vnpy.pth", "distutils-precedence.pth"} <= pth_names
    assert any(
        key.startswith("python_startup_module/_distutils_hack")
        for key in files
    )


def test_candidate_files_change_only_target_rank10_row() -> None:
    module = load_module()
    spec = module._load_probe_spec()
    formal = pd.read_csv(module.FORMAL_ELIGIBILITY)
    ranking = pd.read_csv(module.STAGE009_RANKING)

    candidates, _ = module.build_probe_eligibilities(formal, ranking, spec=spec)
    formal_cmp = formal.copy()
    formal_cmp["eval_date"] = pd.to_datetime(formal_cmp["eval_date"]).dt.date.astype(str)
    target = formal_cmp[formal_cmp["eval_date"].eq(spec["eval_date"])].sort_values("score_rank")

    for arm in ("C12", "C13"):
        observed = candidates[arm]
        observed = observed[observed["eval_date"].eq(spec["eval_date"])].sort_values("score_rank")
        pd.testing.assert_frame_equal(
            target[target["score_rank"].ne(10)].reset_index(drop=True),
            observed[observed["score_rank"].ne(10)].reset_index(drop=True),
            check_dtype=False,
        )
        assert target[target["score_rank"].eq(10)]["product_vt_symbol"].iloc[0] != (
            observed[observed["score_rank"].eq(10)]["product_vt_symbol"].iloc[0]
        )
