from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as stage901  # noqa: E402
import analyze_qmt_roll_stage659_stage653_2026_ytd_latest_ai_shadow as stage659  # noqa: E402
from qmt_roll_official_ai_pool_policy import (  # noqa: E402
    OFFICIAL_AI_PRODUCT_POOL_STRATEGY,
    official_ai_pool_snapshot_blockers,
)
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy  # noqa: E402
import run_qmt_roll_stage909_official_live_shadow_refresh_gate as stage909  # noqa: E402


def test_stage901_ai_pool_audit_reads_official_top10_plus_fu_strategy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    mapping = tmp_path / "mapping.csv"
    mapping.write_text(
        "date\n2026-07-30\n2026-07-31\n2026-08-03\n",
        encoding="utf-8",
    )
    products = [*[f"p{index}.TEST" for index in range(1, 11)], "fu.SHFE"]
    eligibility = tmp_path / "combined.csv"
    pd.DataFrame(
        {
            "strategy": ["ai_top10_plus_fu_official_live_v1"] * 11,
            "score_type": ["stage182_live"] * 11,
            "eval_date": ["2026-07-31"] * 11,
            "product_vt_symbol": products,
            "score": list(range(11, 0, -1)),
            "score_rank": list(range(1, 12)),
            "top_n": [11] * 11,
        }
    ).to_csv(eligibility, index=False, encoding="utf-8-sig")
    monkeypatch.setattr(stage901, "ALL_FUTURES_MAPPING_PATH", mapping)

    audit = stage901._ai_pool_audit(
        eligibility,
        pd.Timestamp("2026-08-03"),
        pd.Timestamp("2026-08-03"),
    )

    assert audit["rows"] == 11
    assert audit["latest_products"] == products
    assert audit["missing_required_eval_dates"] == []
    assert audit["contract_status"] == "valid"
    assert audit["invalid_contract_eval_dates"] == []


def test_stage901_ai_pool_audit_rejects_required_month_without_fixed_fu(
    tmp_path: Path,
    monkeypatch,
) -> None:
    mapping = tmp_path / "mapping.csv"
    mapping.write_text(
        "date\n2026-07-30\n2026-07-31\n2026-08-03\n",
        encoding="utf-8",
    )
    eligibility = tmp_path / "combined.csv"
    pd.DataFrame(
        {
            "strategy": ["ai_top10_plus_fu_official_live_v1"] * 10,
            "score_type": ["stage182_live"] * 10,
            "eval_date": ["2026-07-31"] * 10,
            "product_vt_symbol": [f"p{index}.TEST" for index in range(1, 11)],
            "score": list(range(10, 0, -1)),
            "score_rank": list(range(1, 11)),
            "top_n": [11] * 10,
        }
    ).to_csv(eligibility, index=False, encoding="utf-8-sig")
    monkeypatch.setattr(stage901, "ALL_FUTURES_MAPPING_PATH", mapping)

    audit = stage901._ai_pool_audit(
        eligibility,
        pd.Timestamp("2026-08-03"),
        pd.Timestamp("2026-08-03"),
    )

    assert audit["missing_required_eval_dates"] == []
    assert audit["contract_status"] == "invalid"
    assert audit["invalid_contract_eval_dates"] == ["2026-07-31"]
    assert "2026-07-31:row_count" in audit["contract_blockers"]
    assert "2026-07-31:missing_fixed_product" in audit["contract_blockers"]


def test_stage901_ai_pool_audit_fails_closed_without_trading_calendar(
    tmp_path: Path,
    monkeypatch,
) -> None:
    eligibility = tmp_path / "combined.csv"
    products = [*[f"p{index}.TEST" for index in range(1, 11)], "fu.SHFE"]
    pd.DataFrame(
        {
            "strategy": ["ai_top10_plus_fu_official_live_v1"] * 11,
            "score_type": ["stage182_live"] * 11,
            "eval_date": ["2026-07-31"] * 11,
            "product_vt_symbol": products,
            "score": list(range(11, 0, -1)),
            "score_rank": list(range(1, 12)),
            "top_n": [11] * 11,
        }
    ).to_csv(eligibility, index=False, encoding="utf-8-sig")
    monkeypatch.setattr(stage901, "ALL_FUTURES_MAPPING_PATH", tmp_path / "missing.csv")

    audit = stage901._ai_pool_audit(
        eligibility,
        pd.Timestamp("2026-08-03"),
        pd.Timestamp("2026-08-03"),
    )

    assert audit["contract_status"] == "invalid"
    assert "trading_calendar_unavailable" in audit["contract_blockers"]
    with pytest.raises(RuntimeError, match="official_ai_pool_contract_invalid"):
        stage901._assert_ai_pool_contract_valid(audit)


def test_stage659_ai_pool_audit_reads_official_top10_plus_fu_strategy(
    tmp_path: Path,
) -> None:
    products = [*[f"p{index}.TEST" for index in range(1, 11)], "fu.SHFE"]
    eligibility = tmp_path / "combined.csv"
    pd.DataFrame(
        {
            "strategy": ["ai_top10_plus_fu_official_live_v1"] * 11,
            "score_type": ["stage182_live"] * 11,
            "eval_date": ["2026-07-31"] * 11,
            "product_vt_symbol": products,
            "score": list(range(11, 0, -1)),
            "score_rank": list(range(1, 12)),
            "top_n": [11] * 11,
        }
    ).to_csv(eligibility, index=False, encoding="utf-8-sig")

    audit = stage659._ai_pool_audit(eligibility)

    assert audit["rows"] == 11
    assert audit["latest_products"] == products
    assert audit["contract_status"] == "valid"
    stage659._assert_ai_pool_contract_valid(audit)


def test_stage659_ai_pool_contract_rejects_missing_file(tmp_path: Path) -> None:
    audit = stage659._ai_pool_audit(tmp_path / "missing.csv")

    assert audit["contract_status"] == "invalid"
    with pytest.raises(RuntimeError, match="official_ai_pool_contract_invalid"):
        stage659._assert_ai_pool_contract_valid(audit)


def test_stage659_legacy_stage372_pool_keeps_its_own_contract(tmp_path: Path) -> None:
    strategy = "ai_top8_plus_fu_satellite_post_signal_entry_filter"
    products = [*[f"p{index}.TEST" for index in range(1, 9)], "fu.SHFE"]
    eligibility = tmp_path / "legacy-stage372.csv"
    pd.DataFrame(
        {
            "strategy": [strategy] * 9,
            "eval_date": ["2026-07-31"] * 9,
            "product_vt_symbol": products,
            "score_rank": list(range(1, 10)),
            "top_n": [9] * 9,
        }
    ).to_csv(eligibility, index=False, encoding="utf-8-sig")

    audit = stage659._ai_pool_audit(
        eligibility,
        strategy=strategy,
        enforce_official_contract=False,
    )

    assert audit["contract_status"] == "valid"
    assert audit["latest_products"] == products


def test_official_policy_rejects_fractional_rank_and_top_n() -> None:
    products = [*[f"p{index}.TEST" for index in range(1, 11)], "fu.SHFE"]

    fractional_ranks = official_ai_pool_snapshot_blockers(
        products=products,
        ranks=[index + 0.9 for index in range(1, 12)],
        top_ns=[11] * 11,
    )
    fractional_top_n = official_ai_pool_snapshot_blockers(
        products=products,
        ranks=list(range(1, 12)),
        top_ns=[11.9] * 11,
    )

    assert "rank_range" in fractional_ranks
    assert "top_n" in fractional_top_n


@pytest.mark.parametrize("missing_product", [None, float("nan"), "", "  "])
def test_official_policy_rejects_missing_product_value(missing_product) -> None:
    products = [
        missing_product,
        *[f"p{index}.TEST" for index in range(2, 11)],
        "fu.SHFE",
    ]

    blockers = official_ai_pool_snapshot_blockers(
        products=products,
        ranks=list(range(1, 12)),
        top_ns=[11] * 11,
    )

    assert "product_value" in blockers


def test_official_policy_accepts_only_the_exact_pre_ai_boundary() -> None:
    products = [f"p{index}.TEST" for index in range(1, 19)]
    valid = official_ai_pool_snapshot_blockers(
        products=products,
        ranks=list(range(1, 19)),
        top_ns=[18] * 18,
        eval_date="2019-12-31",
        score_types=["stage182_promoted_static18_pre_ai_boundary"] * 18,
    )
    wrong_date = official_ai_pool_snapshot_blockers(
        products=products,
        ranks=list(range(1, 19)),
        top_ns=[18] * 18,
        eval_date="2020-01-31",
        score_types=["stage182_promoted_static18_pre_ai_boundary"] * 18,
    )

    assert valid == []
    assert "pre_ai_score_type_date" in wrong_date
    assert "row_count" in wrong_date


@pytest.mark.parametrize("missing_score_type", [None, float("nan"), "", "  "])
def test_official_policy_rejects_missing_ai_score_type(missing_score_type) -> None:
    products = [*[f"p{index}.TEST" for index in range(1, 11)], "fu.SHFE"]
    score_types = ["stage182_live"] * 11
    score_types[0] = missing_score_type

    blockers = official_ai_pool_snapshot_blockers(
        products=products,
        ranks=list(range(1, 12)),
        top_ns=[11] * 11,
        eval_date="2026-07-31",
        score_types=score_types,
    )

    assert "score_type" in blockers


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "wrong_strategy",
        "fractional_rank",
        "official_without_fu",
        "official_missing_product",
        "official_missing_score_type",
    ],
)
def test_strategy_consumer_fails_closed_for_invalid_enabled_ai_pool(
    tmp_path: Path,
    case: str,
) -> None:
    path = tmp_path / "eligibility.csv"
    if case != "missing":
        strategy = (
            "different_strategy"
            if case == "wrong_strategy"
            else OFFICIAL_AI_PRODUCT_POOL_STRATEGY
        )
        if case in {
            "official_without_fu",
            "official_missing_product",
            "official_missing_score_type",
        }:
            products = [f"p{index}.TEST" for index in range(1, 12)]
            if case == "official_missing_product":
                products[0] = None
            ranks = list(range(1, 12))
            top_ns = [11] * 11
        else:
            products = ["p1.TEST"]
            ranks = [1.5 if case == "fractional_rank" else 1]
            top_ns = [1]
        score_types = ["stage182_live"] * len(products)
        if case == "official_missing_score_type":
            score_types[0] = None
        pd.DataFrame(
            {
                "strategy": [strategy] * len(products),
                "score_type": score_types,
                "eval_date": ["2026-07-31"] * len(products),
                "product_vt_symbol": products,
                "score": [0.9] * len(products),
                "score_rank": ranks,
                "top_n": top_ns,
            }
        ).to_csv(path, index=False, encoding="utf-8-sig")

    consumer = object.__new__(QmtRollPortfolioStrategy)
    consumer.ai_product_pool_eligibility_path = str(path)
    consumer.ai_product_pool_strategy = OFFICIAL_AI_PRODUCT_POOL_STRATEGY
    consumer.ai_product_pool_by_date = {}
    consumer.ai_product_pool_eval_dates = []
    consumer.ai_product_pool_load_status = "not_loaded"
    consumer.write_log = lambda _message: None

    with pytest.raises(RuntimeError, match="ai_product_pool_contract_invalid"):
        consumer._load_ai_product_pool_eligibility()

    assert consumer.ai_product_pool_load_status == "invalid"


def test_stage909_requires_valid_ai_contract_before_marking_refresh_complete() -> None:
    valid = {
        "shadow_replay_ai_pool_status": "valid",
        "ai_pool_audit": {
            "contract_status": "valid",
            "missing_required_eval_dates": [],
        },
    }
    invalid = {
        "shadow_replay_ai_pool_status": "invalid_ai_pool_contract",
        "ai_pool_audit": {
            "contract_status": "invalid",
            "missing_required_eval_dates": [],
        },
    }

    assert stage909._official_shadow_ai_pool_contract_ready(valid)
    assert not stage909._official_shadow_ai_pool_contract_ready(invalid)
    assert not stage909._official_shadow_ai_pool_contract_ready({})
