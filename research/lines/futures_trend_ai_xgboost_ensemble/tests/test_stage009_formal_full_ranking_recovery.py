from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/stage009_formal_full_ranking_recovery.py"


def load_module():
    assert MODULE_PATH.exists(), "Stage009 formal ranking recovery is not implemented"
    spec = importlib.util.spec_from_file_location(
        "stage009_formal_full_ranking_recovery", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample_source() -> pd.DataFrame:
    rows = []
    for eval_date, scores in (
        ("2022-01-31", (0.9, 0.8, 0.7)),
        ("2022-02-28", (0.6, 0.5, 0.4)),
    ):
        for rank, (product, score) in enumerate(
            zip(("a.X", "b.X", "c.X"), scores), start=1
        ):
            rows.append(
                {
                    "strategy": "ai_top19_plus_fu_width_sweep",
                    "score_type": "ai_probability_top19_plus_fixed_fu",
                    "eval_date": eval_date,
                    "product_vt_symbol": product,
                    "score": score,
                    "score_rank": rank,
                    "top_n": 4,
                    "requested_top_n": 19,
                }
            )
        rows.append(
            {
                "strategy": "ai_top19_plus_fu_width_sweep",
                "score_type": "ai_probability_top19_plus_fixed_fu",
                "eval_date": eval_date,
                "product_vt_symbol": "fu.SHFE",
                "score": min(scores) - 1e-6,
                "score_rank": 4,
                "top_n": 4,
                "requested_top_n": 19,
            }
        )
    return pd.DataFrame(rows)


def sample_release() -> pd.DataFrame:
    source = sample_source()
    result = source[source["score_rank"].le(2)].copy()
    result["strategy"] = "ai_top10_plus_fu_official_live_v1"
    result["score_type"] = "stage182_promoted_ai_probability_top10_plus_fixed_fu"
    result["top_n"] = 3
    fu = source[source["product_vt_symbol"].eq("fu.SHFE")].copy()
    fu["strategy"] = "ai_top10_plus_fu_official_live_v1"
    fu["score_type"] = "stage182_promoted_ai_probability_top10_plus_fixed_fu"
    fu["score_rank"] = 3
    fu["top_n"] = 3
    return pd.concat([result, fu], ignore_index=True)


def test_recover_full_ranking_requires_exact_release_prefix() -> None:
    module = load_module()

    ranking, audit = module.recover_full_ranking(
        sample_source(),
        sample_release(),
        expected_months=2,
        expected_non_fu_count=3,
        formal_top_n=2,
    )

    assert len(ranking) == 6
    assert ranking.groupby("eval_date").size().tolist() == [3, 3]
    assert audit["exact_prefix_months"] == 2
    assert audit["score_max_abs_error"] == 0.0


def test_recover_full_ranking_rejects_release_score_drift() -> None:
    module = load_module()
    release = sample_release()
    release.loc[release["product_vt_symbol"].eq("a.X"), "score"] += 0.01

    with pytest.raises(RuntimeError, match="formal_prefix_score_drift"):
        module.recover_full_ranking(
            sample_source(),
            release,
            expected_months=2,
            expected_non_fu_count=3,
            formal_top_n=2,
        )


def test_recover_full_ranking_rejects_duplicate_product() -> None:
    module = load_module()
    source = pd.concat([sample_source(), sample_source().iloc[[0]]], ignore_index=True)

    with pytest.raises(RuntimeError, match="full_ranking_duplicate"):
        module.recover_full_ranking(
            source,
            sample_release(),
            expected_months=2,
            expected_non_fu_count=3,
            formal_top_n=2,
        )


def test_recover_full_ranking_includes_membership_locked_ai_month() -> None:
    module = load_module()
    source = sample_source()
    release = sample_release()
    source.loc[
        source["eval_date"].eq("2022-02-28"), "score_type"
    ] = "membership_locked_top19_plus_fixed_fu"
    release.loc[
        release["eval_date"].eq("2022-02-28"), "score_type"
    ] = "stage182_promoted_membership_locked_top10_plus_fixed_fu"
    source.loc[
        source["eval_date"].eq("2022-02-28")
        & source["product_vt_symbol"].eq("a.X"),
        "score",
    ] = 0.45
    release.loc[
        release["eval_date"].eq("2022-02-28")
        & release["product_vt_symbol"].eq("a.X"),
        "score",
    ] = 0.45

    ranking, audit = module.recover_full_ranking(
        source,
        release,
        expected_months=2,
        expected_non_fu_count=3,
        formal_top_n=2,
    )

    assert len(ranking) == 6
    assert audit["exact_prefix_months"] == 2
    assert audit["membership_locked_months"] == 1
