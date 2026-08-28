from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_rollover_shape_same_volume" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def test_stage047_freezes_two_arms_and_full_period() -> None:
    runner = importlib.import_module("stage047_stage037_vs_current_online_fullperiod")

    assert [item["arm"] for item in runner.ARMS] == ["A", "C"]
    assert str(runner.START.date()) == "2018-01-01"
    assert str(runner.END.date()) == "2026-08-28"
    assert runner.live_cfg.OFFICIAL_LIVE_VERSION == (
        "official_live_stage847_c9_15w_stage819_05r_stop_retry_once"
    )
    assert runner.live_cfg.OFFICIAL_LIVE_CAPITAL == 150_000.0


def test_stage047_freezes_exact_online_to_stage037_scope() -> None:
    runner = importlib.import_module("stage047_stage037_vs_current_online_fullperiod")

    assert runner.override_diff() == runner._expected_override_diff()
    assert set(runner._expected_override_diff()) == {
        "enable_long_signal_range_atr_filter",
        "enable_short_signal_range_atr_filter",
        "long_signal_range_atr_entry_contexts",
        "long_signal_range_atr_multiplier",
        "long_signal_range_atr_period",
        "long_signal_range_enable_ordered_drawdown_filter",
        "long_signal_range_lookback",
        "long_signal_range_ordered_drawdown_atr_multiplier",
        "long_signal_range_recent_gain_atr_multiplier",
        "long_signal_range_recent_gain_lookback",
        "long_signal_range_require_recent_stall",
        "rollover_delay_trading_days",
        "rollover_shape_history_mode",
    }


def test_stage047_ai_pool_identity_fails_closed_on_production_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = importlib.import_module("stage047_stage037_vs_current_online_fullperiod")
    project = tmp_path / "research"
    production = tmp_path / "production"
    relative = Path("official_strategy_materials/release/pool.csv")
    local_path = project / relative
    production_path = production / relative
    local_path.parent.mkdir(parents=True)
    production_path.parent.mkdir(parents=True)
    pd.DataFrame({"eval_date": ["2026-07-31"], "eligible": [1]}).to_csv(
        local_path, index=False
    )
    pd.DataFrame({"eval_date": ["2026-07-31"], "eligible": [0]}).to_csv(
        production_path, index=False
    )
    monkeypatch.setattr(runner, "PROJECT_DIR", project)
    monkeypatch.setattr(runner, "PRODUCTION_ROOT", production)
    monkeypatch.setattr(runner.live_cfg, "OFFICIAL_LIVE_AI_ELIGIBILITY_PATH", local_path)

    with pytest.raises(RuntimeError, match="ai_pool_production_parity_failed"):
        runner._ai_pool_identity()


def test_stage047_production_engine_binding_requires_exact_module_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = importlib.import_module("stage047_stage037_vs_current_online_fullperiod")
    production = tmp_path / "production"
    portfolio = production / "examples" / "portfolio_backtesting"
    portfolio.mkdir(parents=True)
    names = {
        "s513": "analyze_qmt_roll_stage513_stage208_exact_position_margin_audit.py",
        "s827": "analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac.py",
        "s901": "analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py",
        "live_config": "qmt_roll_official_live_config.py",
        "strategy": "qmt_roll_portfolio_strategy.py",
    }
    paths = {}
    for key, filename in names.items():
        path = portfolio / filename
        path.write_text(f"# {key}\n", encoding="utf-8")
        paths[key] = str(path)
    monkeypatch.setattr(runner, "PRODUCTION_ROOT", production)
    monkeypatch.setattr(runner, "PRODUCTION_CONFIG", portfolio / names["live_config"])
    monkeypatch.setattr(runner, "PRODUCTION_STRATEGY", portfolio / names["strategy"])

    binding = runner._validate_production_engine_binding(paths)
    assert binding["all_modules_from_production_checkout"] is True
    assert set(binding["module_sha256"]) == set(names)

    paths["strategy"] = str(tmp_path / "wrong_strategy.py")
    with pytest.raises(RuntimeError, match="production_engine_binding_failed"):
        runner._validate_production_engine_binding(paths)


def test_stage047_published_decision_is_research_only_and_contracts_pass() -> None:
    artifact = (
        ROOT
        / "research"
        / "lines"
        / "futures_trend_rollover_shape_same_volume"
        / "artifacts"
        / "stage047_stage037_vs_live"
        / "stage047_stage037_vs_live_decision.json"
    )
    decision = json.loads(artifact.read_text(encoding="utf-8"))

    assert decision["promote_to_official"] is False
    assert decision["order_api_called_count"] == 0
    assert decision["send_order_api_called_count"] == 0
    assert decision["cancel_order_api_called_count"] == 0
    assert decision["ctp_connected"] is False
    assert decision["history_contract_C"]["all_pass"] is True
    assert decision["delay_contract_C"]["all_pass"] is True
    assert decision["filter_contract"]["all_pass"] is True
    assert decision["identity"]["production_engine_binding"][
        "all_modules_from_production_checkout"
    ] is True
    assert decision["identity"]["ai_pool"]["production_parity_pass"] is True
