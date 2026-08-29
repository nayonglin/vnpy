from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pandas as pd
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = (
    PROJECT_ROOT
    / "examples"
    / "portfolio_backtesting"
    / "build_qmt_roll_stage065_top10_fu_formal_ai_bundle.py"
)
PORTFOLIO_DIR = BUILDER_PATH.parent
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy  # noqa: E402

SOURCE_STRATEGY = "ai_top10_plus_fu_width_sweep"
OFFICIAL_STRATEGY = "ai_top10_plus_fu_official_live_v1"
STATIC_PRODUCTS = (
    "AP.CZCE",
    "CF.CZCE",
    "FG.CZCE",
    "MA.CZCE",
    "OI.CZCE",
    "RM.CZCE",
    "SA.CZCE",
    "SF.CZCE",
    "SM.CZCE",
    "au.SHFE",
    "cu.SHFE",
    "hc.SHFE",
    "rb.SHFE",
    "ru.SHFE",
    "sp.SHFE",
    "i.DCE",
    "jm.DCE",
    "lh.DCE",
)
RANKED_PRODUCTS = (
    "jm.DCE",
    "si.GFEX",
    "SA.CZCE",
    "au.SHFE",
    "lc.GFEX",
    "cu.SHFE",
    "SM.CZCE",
    "lh.DCE",
    "MA.CZCE",
    "OI.CZCE",
)


def _load_builder():
    assert BUILDER_PATH.is_file(), "Stage065 formal AI bundle builder is missing"
    spec = importlib.util.spec_from_file_location("stage065_formal_ai_bundle", BUILDER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_source(path: Path, *, include_fu: bool = True) -> str:
    rows: list[dict[str, object]] = []
    for rank, product in enumerate(STATIC_PRODUCTS, start=1):
        rows.append(
            {
                "strategy": SOURCE_STRATEGY,
                "score_type": "static18_pre_ai_boundary",
                "eval_date": "2019-12-31",
                "product_vt_symbol": product,
                "score": 0.0,
                "score_rank": rank,
                "top_n": 18,
            }
        )
    for eval_date, score_offset in (("2026-06-30", 0.0), ("2026-07-31", 0.01)):
        score_type = (
            "membership_locked_top10_plus_fixed_fu"
            if eval_date == "2026-06-30"
            else "ai_probability_top10_plus_fixed_fu"
        )
        for rank, product in enumerate(RANKED_PRODUCTS, start=1):
            rows.append(
                {
                    "strategy": SOURCE_STRATEGY,
                    "score_type": score_type,
                    "eval_date": eval_date,
                    "product_vt_symbol": product,
                    "score": 0.80 - rank / 100 + score_offset,
                    "score_rank": rank,
                    "top_n": 11,
                }
            )
        if include_fu:
            rows.append(
                {
                    "strategy": SOURCE_STRATEGY,
                    "score_type": score_type,
                    "eval_date": eval_date,
                    "product_vt_symbol": "fu.SHFE",
                    "score": 0.69 + score_offset,
                    "score_rank": 11,
                    "top_n": 11,
                }
            )
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_build_bundle_writes_five_assets_with_official_pool_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    builder = _load_builder()
    source_path = tmp_path / "stage061_top10_eligibility.csv"
    source_sha256 = _write_source(source_path)
    monkeypatch.setattr(builder, "SOURCE_ELIGIBILITY_SHA256", source_sha256)

    output_dir = tmp_path / "bundle"
    summary = builder.build_bundle(
        source_path,
        output_dir,
        generated_at_cst="2026-08-30T09:15:00+08:00",
    )

    assert {path.name for path in output_dir.iterdir()} == {
        "latest_pool.csv",
        "live_eligibility.csv",
        "combined_eligibility.csv",
        "summary.json",
        "report.md",
    }
    combined = pd.read_csv(output_dir / "combined_eligibility.csv")
    assert combined["strategy"].unique().tolist() == [OFFICIAL_STRATEGY]
    assert combined["score_type"].str.startswith("stage182_promoted_").all()

    static = combined[combined["eval_date"].eq("2019-12-31")]
    assert len(static) == 18
    assert "fu.SHFE" not in set(static["product_vt_symbol"])
    assert static["score_rank"].tolist() == list(range(1, 19))
    assert static["top_n"].unique().tolist() == [18]

    ai = combined[combined["eval_date"].ne("2019-12-31")]
    for _, month in ai.groupby("eval_date"):
        assert len(month) == 11
        assert month["product_vt_symbol"].nunique() == 11
        assert month["score_rank"].tolist() == list(range(1, 12))
        assert month["top_n"].unique().tolist() == [11]
        assert month["product_vt_symbol"].tolist()[-1] == "fu.SHFE"
        assert set(month.iloc[:10]["product_vt_symbol"]) == set(RANKED_PRODUCTS)

    live = pd.read_csv(output_dir / "live_eligibility.csv")
    assert live["eval_date"].unique().tolist() == ["2026-07-31"]
    assert live.equals(ai[ai["eval_date"].eq("2026-07-31")].reset_index(drop=True))

    latest = pd.read_csv(output_dir / "latest_pool.csv")
    assert latest["ai_rank"].tolist() == list(range(1, 12))
    assert latest["product_vt_symbol"].tolist()[-1] == "fu.SHFE"
    assert latest["selection_role"].tolist() == ["model_ranked"] * 10 + ["fixed_fu"]

    on_disk_summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary == on_disk_summary
    assert summary["generated_at_cst"] == "2026-08-30T09:15:00+08:00"
    assert summary["source_model_tag"] == "product_suitability_wf_v1"
    assert summary["training_label_cutoff"] == "2026-05-07"
    assert summary["data_cutoff"] == "2026-08-03"
    assert summary["source_max_date"] == "2026-08-03"
    assert summary["source"]["commit"] == "6750783fe7aab92e6dbdd6820fa212e2e53ea353"
    assert summary["source"]["sha256"] == source_sha256
    assert summary["source"]["source_path"] == "source/stage061_top10_eligibility.csv"
    assert summary["outputs"] == {
        "live_pool": "latest_pool.csv",
        "live_eligibility": "live_eligibility.csv",
        "combined_eligibility": "combined_eligibility.csv",
        "summary": "summary.json",
        "report": "report.md",
    }
    assert summary["eligibility_contract"] == {
        "strategy": OFFICIAL_STRATEGY,
        "fixed_product": "fu.SHFE",
        "ranked_non_fu_count": 10,
        "ai_month_total_product_count": 11,
        "pre_ai_static_product_count": 18,
        "pre_ai_static_contains_fu": False,
        "pre_ai_eval_date": "2019-12-31",
        "latest_eval_date": "2026-07-31",
        "eval_date_count": 3,
        "ai_eval_date_count": 2,
    }
    assert summary["promotion_decision"]["natural_gates_pass"] is False
    assert summary["promotion_decision"]["operator_override"] is True
    assert summary["research_evidence"]["Stage061"]["passed"] is False
    assert summary["research_evidence"]["Stage063"]["passed"] is False
    assert summary["research_evidence"]["Stage064"]["passed"] is False
    assert summary["order_api_called_count"] == 0
    assert summary["send_order_api_called_count"] == 0
    assert summary["cancel_order_api_called_count"] == 0
    assert summary["safety"]["real_order_enabled"] is False

    consumer = object.__new__(QmtRollPortfolioStrategy)
    consumer.ai_product_pool_eligibility_path = str(
        output_dir / "combined_eligibility.csv"
    )
    consumer.ai_product_pool_strategy = OFFICIAL_STRATEGY
    consumer.ai_product_pool_by_date = {}
    consumer.ai_product_pool_eval_dates = []
    consumer.ai_product_pool_load_status = "not_loaded"
    consumer.write_log = lambda _message: None
    consumer._load_ai_product_pool_eligibility()
    assert consumer.ai_product_pool_load_status == "valid"
    assert len(consumer.ai_product_pool_by_date[pd.Timestamp("2019-12-31")]) == 18
    assert len(consumer.ai_product_pool_by_date[pd.Timestamp("2026-07-31")]) == 11

    report = (output_dir / "report.md").read_text(encoding="utf-8")
    assert "自然门禁结论：`FAIL`" in report
    assert "operator_override=true" in report
    assert "Stage061" in report and "Stage063" in report and "Stage064" in report
    assert "send/cancel/order API 调用均为 `0`" in report


def test_build_bundle_rejects_source_sha_drift(tmp_path: Path) -> None:
    builder = _load_builder()
    source_path = tmp_path / "not_the_frozen_stage061_source.csv"
    _write_source(source_path)

    with pytest.raises(RuntimeError, match="stage065_source_sha256_mismatch"):
        builder.build_bundle(source_path, tmp_path / "bundle")


def test_build_bundle_rejects_ai_month_without_fixed_fu(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    builder = _load_builder()
    source_path = tmp_path / "malformed_stage061_source.csv"
    source_sha256 = _write_source(source_path, include_fu=False)
    monkeypatch.setattr(builder, "SOURCE_ELIGIBILITY_SHA256", source_sha256)

    with pytest.raises(RuntimeError, match="stage065_ai_month_product_count"):
        builder.build_bundle(source_path, tmp_path / "bundle")


def test_build_bundle_rejects_nonempty_output_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    builder = _load_builder()
    source_path = tmp_path / "stage061_top10_eligibility.csv"
    source_sha256 = _write_source(source_path)
    monkeypatch.setattr(builder, "SOURCE_ELIGIBILITY_SHA256", source_sha256)
    output_dir = tmp_path / "bundle"
    output_dir.mkdir()
    (output_dir / "stale.csv").write_text("stale\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="stage065_output_dir_not_empty"):
        builder.build_bundle(source_path, output_dir)
