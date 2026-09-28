from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools/stage011_marginal_slot_activity_qualification.py"
)


def load_module():
    assert MODULE_PATH.exists(), "Stage011 marginal slot activity audit is not implemented"
    spec = importlib.util.spec_from_file_location(
        "stage011_marginal_slot_activity_qualification", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_contract_to_product_preserves_exchange() -> None:
    module = load_module()

    assert module.contract_to_product("OI209.CZCE") == "OI.CZCE"
    assert module.contract_to_product("ru2209.SHFE") == "ru.SHFE"


def test_activity_audit_selects_first_month_with_active_baseline_and_two_challengers() -> None:
    module = load_module()
    ranking_rows = []
    for eval_date in ("2022-04-29", "2022-05-31", "2022-06-30"):
        for rank in range(1, 19):
            ranking_rows.append(
                {
                    "eval_date": eval_date,
                    "product_vt_symbol": f"p{rank}.X",
                    "score_rank": rank,
                }
            )
    ranking = pd.DataFrame(ranking_rows)
    trades = pd.DataFrame(
        {
            "experiment_arm": ["T18", "T18", "T18", "T18", "T10"],
            "offset": ["开", "开", "开", "开", "开"],
            "date": [
                "2022-05-10",
                "2022-06-08",
                "2022-06-09",
                "2022-06-10",
                "2022-06-11",
            ],
            "vt_symbol": ["p10a.X", "p10b.X", "p12b.X", "p13b.X", "p18b.X"],
        }
    )
    product_map = {
        "p10a.X": "p10.X",
        "p10b.X": "p10.X",
        "p12b.X": "p12.X",
        "p13b.X": "p13.X",
        "p18b.X": "p18.X",
    }

    audit = module.build_activity_audit(
        trades,
        ranking,
        first_eval_date="2022-04-29",
        product_resolver=lambda value: product_map[value],
    )
    selected = module.select_first_qualified_month(audit, min_active_challengers=2)

    assert selected["eval_date"] == "2022-05-31"
    assert selected["next_eval_date"] == "2022-06-30"
    assert selected["baseline_rank"] == 10
    assert selected["challenger_ranks"] == [12, 13]

