import importlib.util
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest


PATH = Path(__file__).resolve().parents[1] / "tools/stage004_label_batch.py"


def module():
    assert PATH.exists(), "batch implementation missing"
    spec = importlib.util.spec_from_file_location("label_batch_test", PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_job_plan_keeps_censored_rows_without_zero_labels():
    rows = []
    for i, status in enumerate(["mature", "mature_cancelled_unfilled", "right_censored_open", "right_censored_pending_entry"]):
        rows.append({"event_id": str(i), "candidate_index": i, "decision_date": "2020-01-02",
                     "end_date": "2020-01-03" if i == 0 else ("2020-01-02" if i == 1 else None),
                     "status": status, "product_vt_symbol": "sp.SHFE"})
    jobs, censored = module().partition_events(rows)
    assert len(jobs) == len(censored) == 2
    assert jobs[1]["end_date"] == "2020-01-02"
    assert all("return_marginal" not in row for row in censored)


@pytest.mark.parametrize("change", [{"status": "unresolved"}, {"end_date": None},
                                     {"end_date": "2019-12-31"}, {"product_vt_symbol": "fu.SHFE"}])
def test_invalid_lifecycle_blocks_plan(change):
    row = {"event_id": "x", "candidate_index": 1, "decision_date": "2020-01-02", "end_date": "2020-01-03",
           "status": "mature", "product_vt_symbol": "sp.SHFE"}
    with pytest.raises(RuntimeError):
        module().partition_events([{**row, **change}])


def test_duplicate_job_rejected():
    row = {"event_id": "x", "candidate_index": 1, "decision_date": "2020-01-02", "end_date": "2020-01-03",
           "status": "mature", "product_vt_symbol": "sp.SHFE"}
    with pytest.raises(RuntimeError):
        module().partition_events([row, row])


def test_empty_root_output_preserves_schema():
    m = module()
    h = m.load_history()
    candidates = pd.DataFrame([{"is_opened": 0, "entry_context": "flat_entry", "candidate_status": "skipped", "product_vt_symbol": "sp.SHFE"}])
    result = m.feature_adapter(candidates, None, {})
    assert result.empty
    assert result.columns.tolist() == [*h.ID_COLUMNS, *h.FEATURES]


def test_worker_configuration_uses_stdlib_before_bootstrap():
    m = module()
    code = "import runpy; m=runpy.run_path(" + repr(str(PATH)) + "); m['configured'](); print('ready')"
    result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "ready" in result.stdout


def test_calendar_mismatch_fails_even_if_values_equal():
    m = module()
    a = pd.DataFrame({"date": ["2020-01-02", "2020-01-03"], "account_equity": [100.0, 101.0]})
    s = a.copy()
    s.loc[1, "date"] = "2020-01-04"
    with pytest.raises(RuntimeError):
        m.validate_daily_calendar(a, s, "2020-01-03")
