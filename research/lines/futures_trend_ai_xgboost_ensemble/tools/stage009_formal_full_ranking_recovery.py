"""Recover the formal model's full 18-product ranking from its frozen Git source."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


LINE = Path(__file__).resolve().parents[1]
OUT = LINE / "artifacts/stage009_formal_full_ranking_recovery"
PREREGISTRATION = LINE / "stages/20260901_1721_stage009_formal_full_ranking_recovery.md"
PRODUCTION_REPO = Path("/Users/bytedance/Desktop/person/vnpy_production_live")
SOURCE_COMMIT = "6750783fe7aab92e6dbdd6820fa212e2e53ea353"
SOURCE_PATH = (
    "research/lines/futures_trend_rollover_shape_same_volume/artifacts/"
    "stage061_ai_top10_to_top19_fullperiod/stage061_eligibility.csv"
)
RELEASE_ROOT = Path(
    "/Users/bytedance/Desktop/person/vnpy_production_live/official_strategy_materials/"
    "ai_top10_plus_fu_official_live_v1/releases/"
    "m0004_20260831T112631+0800_2485073e9594"
)
RELEASE_ELIGIBILITY = RELEASE_ROOT / "payload/ai/stage182/combined_eligibility.csv"
RELEASE_SUMMARY = RELEASE_ROOT / "payload/ai/stage182/summary.json"
EXPECTED_MONTHS = 55
EXPECTED_NON_FU_COUNT = 18
FORMAL_TOP_N = 10


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _git_object_bytes(commit: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=PRODUCTION_REPO,
        check=True,
        capture_output=True,
    ).stdout


def _git_blob_id(commit: str, path: str) -> str:
    return subprocess.run(
        ["git", "rev-parse", f"{commit}:{path}"],
        cwd=PRODUCTION_REPO,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def recover_full_ranking(
    source: pd.DataFrame,
    release: pd.DataFrame,
    *,
    expected_months: int = EXPECTED_MONTHS,
    expected_non_fu_count: int = EXPECTED_NON_FU_COUNT,
    formal_top_n: int = FORMAL_TOP_N,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    required_source = {
        "score_type",
        "eval_date",
        "product_vt_symbol",
        "score",
        "score_rank",
        "requested_top_n",
    }
    required_release = required_source - {"requested_top_n"}
    if missing := sorted(required_source - set(source.columns)):
        raise RuntimeError(f"source_columns_missing:{missing}")
    if missing := sorted(required_release - set(release.columns)):
        raise RuntimeError(f"release_columns_missing:{missing}")

    source_ai_types = {
        "ai_probability_top19_plus_fixed_fu",
        "membership_locked_top19_plus_fixed_fu",
    }
    full = source[
        source["requested_top_n"].eq(19)
        & source["score_type"].astype(str).isin(source_ai_types)
        & ~source["product_vt_symbol"].astype(str).eq("fu.SHFE")
    ].copy()
    full["eval_date"] = pd.to_datetime(full["eval_date"], errors="raise").dt.date.astype(str)
    full["score_rank"] = pd.to_numeric(full["score_rank"], errors="raise").astype(int)
    full["score"] = pd.to_numeric(full["score"], errors="raise").astype(float)
    if full.duplicated(["eval_date", "product_vt_symbol"]).any():
        raise RuntimeError("full_ranking_duplicate")
    if full["eval_date"].nunique() != expected_months:
        raise RuntimeError(
            f"full_ranking_month_count:{full['eval_date'].nunique()}:{expected_months}"
        )
    for eval_date, month in full.groupby("eval_date", sort=True):
        if len(month) != expected_non_fu_count:
            raise RuntimeError(f"full_ranking_month_shape:{eval_date}:{len(month)}")
        ranks = sorted(month["score_rank"].tolist())
        if ranks != list(range(1, expected_non_fu_count + 1)):
            raise RuntimeError(f"full_ranking_rank_shape:{eval_date}:{ranks}")
        ordered = month.sort_values("score_rank")
        score_type = str(ordered["score_type"].iloc[0])
        if ordered["score_type"].nunique() != 1:
            raise RuntimeError(f"full_ranking_mixed_score_type:{eval_date}")
        if (
            score_type == "ai_probability_top19_plus_fixed_fu"
            and not ordered["score"].is_monotonic_decreasing
        ):
            raise RuntimeError(f"full_ranking_score_order:{eval_date}")

    release_ai_suffixes = (
        "ai_probability_top10_plus_fixed_fu",
        "membership_locked_top10_plus_fixed_fu",
    )
    formal = release[
        release["score_type"].astype(str).str.endswith(release_ai_suffixes)
        & ~release["product_vt_symbol"].astype(str).eq("fu.SHFE")
    ].copy()
    formal["eval_date"] = pd.to_datetime(formal["eval_date"], errors="raise").dt.date.astype(str)
    formal["score_rank"] = pd.to_numeric(formal["score_rank"], errors="raise").astype(int)
    formal["score"] = pd.to_numeric(formal["score"], errors="raise").astype(float)
    formal = formal[formal["score_rank"].le(formal_top_n)].copy()
    if formal.duplicated(["eval_date", "score_rank"]).any():
        raise RuntimeError("formal_prefix_duplicate")
    if formal["eval_date"].nunique() != expected_months:
        raise RuntimeError(
            f"formal_prefix_month_count:{formal['eval_date'].nunique()}:{expected_months}"
        )
    if not formal.groupby("eval_date").size().eq(formal_top_n).all():
        raise RuntimeError("formal_prefix_month_shape")

    prefix = full[full["score_rank"].le(formal_top_n)].copy()
    compared = prefix.merge(
        formal[["eval_date", "score_rank", "product_vt_symbol", "score"]],
        on=["eval_date", "score_rank"],
        how="outer",
        suffixes=("_source", "_release"),
        indicator=True,
        validate="one_to_one",
    )
    if not compared["_merge"].eq("both").all():
        raise RuntimeError("formal_prefix_key_drift")
    if not compared["product_vt_symbol_source"].eq(
        compared["product_vt_symbol_release"]
    ).all():
        raise RuntimeError("formal_prefix_product_drift")
    score_error = np.abs(
        compared["score_source"].to_numpy(dtype="float64")
        - compared["score_release"].to_numpy(dtype="float64")
    )
    max_error = float(score_error.max(initial=0.0))
    if max_error != 0.0:
        raise RuntimeError(f"formal_prefix_score_drift:{max_error}")

    full = full.sort_values(
        ["eval_date", "score_rank", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)
    ranking = full[
        ["eval_date", "product_vt_symbol", "score", "score_rank", "score_type"]
    ].copy()
    membership_locked_months = int(
        ranking.loc[
            ranking["score_type"].eq("membership_locked_top19_plus_fixed_fu"),
            "eval_date",
        ].nunique()
    )
    audit = {
        "months": int(ranking["eval_date"].nunique()),
        "rows": int(len(ranking)),
        "products_per_month": expected_non_fu_count,
        "formal_top_n": formal_top_n,
        "exact_prefix_months": int(compared["eval_date"].nunique()),
        "exact_prefix_rows": int(len(compared)),
        "score_max_abs_error": max_error,
        "probability_ranked_months": int(expected_months - membership_locked_months),
        "membership_locked_months": membership_locked_months,
        "first_eval_date": ranking["eval_date"].min(),
        "latest_eval_date": ranking["eval_date"].max(),
    }
    return ranking, audit


def main() -> None:
    if OUT.exists():
        raise RuntimeError(f"stage009_output_already_exists:{OUT}")
    source_payload = _git_object_bytes(SOURCE_COMMIT, SOURCE_PATH)
    source = pd.read_csv(BytesIO(source_payload))
    release = pd.read_csv(RELEASE_ELIGIBILITY)
    release_summary = json.loads(RELEASE_SUMMARY.read_text(encoding="utf-8"))
    if release_summary["source"]["commit"] != SOURCE_COMMIT:
        raise RuntimeError("release_source_commit_drift")

    ranking, audit = recover_full_ranking(source, release)
    if audit["probability_ranked_months"] != 52 or audit["membership_locked_months"] != 3:
        raise RuntimeError(
            "formal_ranking_mode_count_drift:"
            f"{audit['probability_ranked_months']}:{audit['membership_locked_months']}"
        )
    OUT.mkdir(parents=True)
    ranking_path = OUT / "formal_full_ranking.csv"
    ranking.to_csv(ranking_path, index=False, encoding="utf-8-sig")
    audit.update(
        {
            "line_id": "futures_trend_ai_xgboost_ensemble",
            "stage": "Stage009",
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "decision": "stage009_formal_full_ranking_exactly_recovered",
            "source_commit": SOURCE_COMMIT,
            "source_path": SOURCE_PATH,
            "source_blob_id": _git_blob_id(SOURCE_COMMIT, SOURCE_PATH),
            "source_payload_sha256": _sha256_bytes(source_payload),
            "release_id": RELEASE_ROOT.name,
            "release_eligibility_sha256": _sha256_file(RELEASE_ELIGIBILITY),
            "release_summary_sha256": _sha256_file(RELEASE_SUMMARY),
            "preregistration_sha256": _sha256_file(PREREGISTRATION),
            "output_sha256": _sha256_file(ranking_path),
            "uses_future_return": False,
            "trains_model": False,
            "runs_backtest": False,
            "order_api_called_count": 0,
            "ctp_connected": False,
        }
    )
    (OUT / "audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report = (
        "# Stage009 正式完整排序恢复\n\n"
        f"- 决策：`{audit['decision']}`\n"
        f"- 完整排序：`{audit['months']}`月、`{audit['rows']}`行，每月18个非fu。\n"
        f"- release前缀：`{audit['exact_prefix_months']}`月、"
        f"`{audit['exact_prefix_rows']}`行，score最大绝对误差`{audit['score_max_abs_error']}`。\n"
        f"- 排名模式：普通概率排序`{audit['probability_ranked_months']}`月，"
        f"正式成员锁定`{audit['membership_locked_months']}`月。\n"
        f"- 日期：`{audit['first_eval_date']}`至`{audit['latest_eval_date']}`。\n"
        "- 本阶段不训练、不回测、不连接CTP、不调用订单API。\n"
    )
    (OUT / "report.md").write_text(report, encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
