from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/stage010_account_marginal_slot_probe.py"


def load_module():
    assert MODULE_PATH.exists(), "Stage010 account marginal slot probe is not implemented"
    spec = importlib.util.spec_from_file_location("stage010_account_marginal_slot_probe", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def formal_month() -> pd.DataFrame:
    rows = []
    for rank in range(1, 11):
        rows.append(
            {
                "strategy": "formal",
                "score_type": "formal_score",
                "eval_date": "2022-04-29",
                "product_vt_symbol": f"p{rank}.X",
                "score": 20 - rank,
                "score_rank": rank,
                "top_n": 11,
            }
        )
    rows.append(
        {
            "strategy": "formal",
            "score_type": "formal_score",
            "eval_date": "2022-04-29",
            "product_vt_symbol": "fu.SHFE",
            "score": 9 - 1e-6,
            "score_rank": 11,
            "top_n": 11,
        }
    )
    return pd.DataFrame(rows)


def full_ranking() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "eval_date": ["2022-04-29"] * 18,
            "product_vt_symbol": [f"p{rank}.X" for rank in range(1, 19)],
            "score": [20 - rank for rank in range(1, 19)],
            "score_rank": list(range(1, 19)),
            "score_type": ["ai_probability_top19_plus_fixed_fu"] * 18,
        }
    )


def test_build_probe_month_keeps_core_and_replaces_only_rank10() -> None:
    module = load_module()

    arms, audit = module.build_probe_eligibilities(
        formal_month(),
        full_ranking(),
        eval_date="2022-04-29",
        candidate_ranks={"A": 10, "C11": 11, "C18": 18},
    )

    assert set(arms) == {"A", "C11", "C18"}
    assert arms["A"]["product_vt_symbol"].tolist() == [
        *(f"p{rank}.X" for rank in range(1, 11)),
        "fu.SHFE",
    ]
    assert arms["C11"]["product_vt_symbol"].tolist()[-2:] == ["p11.X", "fu.SHFE"]
    assert arms["C18"]["product_vt_symbol"].tolist()[-2:] == ["p18.X", "fu.SHFE"]
    assert audit.set_index("arm").loc["C11", "changed_slots"] == 1


def test_future_period_label_uses_predecision_equity_and_future_drawdown() -> None:
    module = load_module()
    curve = pd.DataFrame(
        {
            "date": pd.to_datetime(["2022-04-28", "2022-04-29", "2022-05-05", "2022-05-06"]),
            "account_equity": [100.0, 110.0, 99.0, 121.0],
            "net_pnl": [0.0, 10.0, -11.0, 22.0],
            "slippage": [0.0, 0.0, 2.0, 3.0],
            "trade_count": [0.0, 0.0, 1.0, 2.0],
        }
    )

    label = module.future_period_label(curve, pd.Timestamp("2022-04-29"))

    assert abs(label["future_return"] - 0.1) < 1e-12
    assert abs(label["future_max_drawdown"] - (-0.1)) < 1e-12
    assert label["future_net_pnl"] == 11.0
    assert label["future_slippage"] == 5.0
    assert label["future_trade_count"] == 3.0


def test_runtime_stability_rejects_sys_path_change() -> None:
    module = load_module()
    expected = {"python": "3.11", "sys_path": ["a", "b"]}

    with pytest.raises(RuntimeError, match="runtime_contract_changed:sys_path"):
        module.validate_runtime_stability(expected, {"python": "3.11", "sys_path": ["a", "c"]})


def test_worker_environment_is_arm_specific() -> None:
    module = load_module()

    a = module.worker_environment({}, Path("/tmp/probe"), "A1")
    c = module.worker_environment({}, Path("/tmp/probe"), "C11")

    assert a["TMPDIR"] != c["TMPDIR"]
    assert a["MPLCONFIGDIR"] != c["MPLCONFIGDIR"]


def test_stage010_is_bound_to_current_m0005_online_identity() -> None:
    module = load_module()

    assert module.FORMAL_RELEASE_ID == "m0005_20260901T165450+0800_1961d98ccb2b"
    assert module.EXPECTED_PRODUCTION_HEAD == "d492ee072aa5a9d71477235d79f17d2a5db59db3"
    assert module.FORMAL_RELEASE.name == module.FORMAL_RELEASE_ID


def test_repository_values_reject_stage007_old_head() -> None:
    module = load_module()

    current = module.validate_repository_values(
        "d492ee072aa5a9d71477235d79f17d2a5db59db3", "", ""
    )
    assert current["production_head"] == module.EXPECTED_PRODUCTION_HEAD

    with pytest.raises(RuntimeError, match="production_head_drift"):
        module.validate_repository_values(
            "1961d98ccb2b9129e35fe982b7330ae4217dcde6", "", ""
        )
