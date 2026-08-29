from __future__ import annotations

import importlib
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_rollover_shape_same_volume" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def _annotation():
    return importlib.import_module("stage059_multicycle_review_annotation")


def _wrapper():
    return importlib.import_module("stage059_run_and_publish")


def test_effect_diagnostics_keep_frozen_nonunderperformance_and_separate_ties() -> None:
    module = _annotation()
    comparison = pd.DataFrame(
        {
            "duration_years": [1, 1, 1, 1],
            "start_month_num": [1, 1, 6, 6],
            "delta_return_pct": [0.0, 2.0, -1.0, 0.0],
        }
    )
    aggregate = pd.DataFrame(
        {
            "duration_years": [1, 1, 1],
            "start_cohort": ["combined", "january", "june"],
            "return_win_rate_pct": [75.0, 100.0, 50.0],
        }
    )

    result = module.add_effect_diagnostics(aggregate, comparison)
    combined = result[result["start_cohort"].eq("combined")].iloc[0]
    assert combined["return_nonunderperformance_rate_pct"] == 75.0
    assert combined["tie_window_count"] == 2
    assert combined["effect_window_count"] == 2
    assert combined["strict_return_win_count"] == 1
    assert combined["strict_return_loss_count"] == 1
    assert combined["strict_return_win_rate_effect_pct"] == 50.0


def test_stage059_real_artifacts_have_expected_effect_window_contract() -> None:
    module = _annotation()
    comparison = pd.read_csv(module.OUTPUT_DIR / module.runner.COMPARISON_NAME)
    aggregate = pd.read_csv(module.OUTPUT_DIR / module.runner.AGGREGATE_NAME)
    result = module.add_effect_diagnostics(aggregate, comparison)
    combined = result[result["start_cohort"].eq("combined")].set_index("duration_years")

    assert combined["effect_window_count"].to_dict() == {1: 9, 2: 9, 3: 9}
    assert combined["strict_return_win_count"].to_dict() == {1: 3, 2: 6, 3: 4}
    assert combined["strict_return_loss_count"].to_dict() == {1: 6, 2: 3, 3: 5}


def test_report_annotation_is_explicitly_offline_and_idempotent() -> None:
    module = _annotation()
    aggregate = module.add_effect_diagnostics(
        pd.read_csv(module.OUTPUT_DIR / module.runner.AGGREGATE_NAME),
        pd.read_csv(module.OUTPUT_DIR / module.runner.COMPARISON_NAME),
    )
    report = (module.OUTPUT_DIR / module.runner.REPORT_NAME).read_text(encoding="utf-8")

    once = module._annotate_report(report, aggregate)
    twice = module._annotate_report(once, aggregate)

    assert once == twice
    assert "**OFFLINE RESEARCH**" in once
    assert once.count("## 独立review后的收益口径澄清") == 1
    assert "严格胜率(不含并列)" in once


def test_single_entrypoint_runs_backtest_then_review_annotation(monkeypatch) -> None:
    module = _wrapper()
    calls: list[str] = []
    monkeypatch.setattr(module.runner, "main", lambda: calls.append("runner"))
    monkeypatch.setattr(module.annotation, "main", lambda: calls.append("annotation"))

    module.main()

    assert calls == ["runner", "annotation"]


def test_disk_artifacts_are_review_annotated() -> None:
    module = _annotation()
    decision = pd.read_json(module.OUTPUT_DIR / module.runner.DECISION_NAME, typ="series")
    aggregate = pd.read_csv(module.OUTPUT_DIR / module.runner.AGGREGATE_NAME)
    report = (module.OUTPUT_DIR / module.runner.REPORT_NAME).read_text(encoding="utf-8")

    assert decision["post_review_annotation"]["frozen_gates_changed"] is False
    assert {
        "return_nonunderperformance_rate_pct",
        "effect_window_count",
        "tie_window_count",
        "strict_return_win_rate_effect_pct",
    }.issubset(aggregate.columns)
    assert "**OFFLINE RESEARCH**" in report
    assert "严格胜率(不含并列)" in report
    assert "stage059_run_and_publish.py" in report
    for filename in module.runner.CHART_FILES.values():
        assert (module.OUTPUT_DIR / filename).stat().st_size > 100_000
