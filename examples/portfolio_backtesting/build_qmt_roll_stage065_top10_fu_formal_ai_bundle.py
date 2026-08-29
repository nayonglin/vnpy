"""Build the immutable Stage065 Top10 + fixed-fu formal AI asset bundle.

This command is a packaging/validation step only.  It does not run a
backtest, train or score a model, connect to CTP, or call an order API.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from qmt_roll_official_ai_pool_policy import (
    OFFICIAL_AI_FIXED_PRODUCT,
    OFFICIAL_AI_PRE_AI_EVAL_DATE,
    OFFICIAL_AI_PRE_AI_PRODUCT_COUNT,
    OFFICIAL_AI_PRE_AI_SCORE_TYPE,
    OFFICIAL_AI_PRODUCT_POOL_STRATEGY,
    OFFICIAL_AI_RANKED_PRODUCT_COUNT,
    OFFICIAL_AI_TOTAL_PRODUCT_COUNT,
)


SOURCE_ELIGIBILITY_SHA256 = (
    "cf3cced22a61b354dadbc2f67091143eec74d7a2f03577faf2fd4c10dcec0c0d"
)
SOURCE_COMMIT = "6750783fe7aab92e6dbdd6820fa212e2e53ea353"
SOURCE_STRATEGY = "ai_top10_plus_fu_width_sweep"
OFFICIAL_STRATEGY = OFFICIAL_AI_PRODUCT_POOL_STRATEGY
FIXED_PRODUCT = OFFICIAL_AI_FIXED_PRODUCT
RANKED_NON_FU_COUNT = OFFICIAL_AI_RANKED_PRODUCT_COUNT
AI_MONTH_PRODUCT_COUNT = OFFICIAL_AI_TOTAL_PRODUCT_COUNT
PRE_AI_PRODUCT_COUNT = OFFICIAL_AI_PRE_AI_PRODUCT_COUNT
SOURCE_DATA_CUTOFF = "2026-08-03"
TRAINING_LABEL_CUTOFF = "2026-05-07"
PRE_AI_SCORE_TYPE = OFFICIAL_AI_PRE_AI_SCORE_TYPE
AI_SCORE_TYPE = "ai_probability_top10_plus_fixed_fu"
LOCKED_AI_SCORE_TYPE = "membership_locked_top10_plus_fixed_fu"
PROMOTED_SCORE_TYPE_PREFIX = "stage182_promoted_"
ELIGIBILITY_COLUMNS = (
    "strategy",
    "score_type",
    "eval_date",
    "product_vt_symbol",
    "score",
    "score_rank",
    "top_n",
)
OUTPUT_NAMES = {
    "live_pool": "latest_pool.csv",
    "live_eligibility": "live_eligibility.csv",
    "combined_eligibility": "combined_eligibility.csv",
    "summary": "summary.json",
    "report": "report.md",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _generated_at_cst(value: str | None) -> str:
    if value:
        parsed = datetime.fromisoformat(value)
        if parsed.utcoffset() is None:
            raise RuntimeError("stage065_generated_at_cst_missing_timezone")
        return parsed.isoformat(timespec="seconds")
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def _load_and_validate_source(source_path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    source_path = source_path.expanduser().resolve(strict=True)
    source_sha256 = _sha256(source_path)
    if source_sha256 != SOURCE_ELIGIBILITY_SHA256:
        raise RuntimeError(
            "stage065_source_sha256_mismatch:"
            f"expected={SOURCE_ELIGIBILITY_SHA256}:actual={source_sha256}"
        )

    frame = pd.read_csv(source_path, encoding="utf-8-sig")
    missing_columns = sorted(set(ELIGIBILITY_COLUMNS) - set(frame.columns))
    if missing_columns:
        raise RuntimeError(f"stage065_source_columns_missing:{','.join(missing_columns)}")
    frame = frame.loc[:, ELIGIBILITY_COLUMNS].copy()
    if frame.empty:
        raise RuntimeError("stage065_source_empty")
    if set(frame["strategy"].astype(str)) != {SOURCE_STRATEGY}:
        raise RuntimeError("stage065_source_strategy_mismatch")

    parsed_dates = pd.to_datetime(frame["eval_date"], errors="coerce")
    if parsed_dates.isna().any():
        raise RuntimeError("stage065_source_eval_date_invalid")
    frame["eval_date"] = parsed_dates.dt.date.astype(str)
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    frame["score_type"] = frame["score_type"].astype(str)
    frame["score"] = pd.to_numeric(frame["score"], errors="coerce")
    frame["score_rank"] = pd.to_numeric(frame["score_rank"], errors="coerce")
    frame["top_n"] = pd.to_numeric(frame["top_n"], errors="coerce")
    if frame[["score", "score_rank", "top_n"]].isna().any().any():
        raise RuntimeError("stage065_source_numeric_value_invalid")
    frame["score_rank"] = frame["score_rank"].astype(int)
    frame["top_n"] = frame["top_n"].astype(int)
    frame.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    frame.reset_index(drop=True, inplace=True)

    if frame.duplicated(["eval_date", "product_vt_symbol"]).any():
        raise RuntimeError("stage065_source_duplicate_eval_product")

    static_dates = sorted(
        frame.loc[frame["score_type"].eq(PRE_AI_SCORE_TYPE), "eval_date"].unique().tolist()
    )
    if len(static_dates) != 1:
        raise RuntimeError("stage065_pre_ai_boundary_count")
    pre_ai_eval_date = static_dates[0]
    if pre_ai_eval_date != OFFICIAL_AI_PRE_AI_EVAL_DATE:
        raise RuntimeError("stage065_pre_ai_boundary_date_mismatch")
    if pre_ai_eval_date != frame["eval_date"].min():
        raise RuntimeError("stage065_pre_ai_boundary_not_first")

    static = frame[frame["eval_date"].eq(pre_ai_eval_date)].copy()
    if len(static) != PRE_AI_PRODUCT_COUNT:
        raise RuntimeError(
            f"stage065_pre_ai_product_count:expected={PRE_AI_PRODUCT_COUNT}:actual={len(static)}"
        )
    if set(static["score_type"]) != {PRE_AI_SCORE_TYPE}:
        raise RuntimeError("stage065_pre_ai_score_type_mixed")
    if FIXED_PRODUCT in set(static["product_vt_symbol"]):
        raise RuntimeError("stage065_pre_ai_contains_fixed_fu")
    if static["score_rank"].tolist() != list(range(1, PRE_AI_PRODUCT_COUNT + 1)):
        raise RuntimeError("stage065_pre_ai_rank_range")
    if set(static["top_n"]) != {PRE_AI_PRODUCT_COUNT}:
        raise RuntimeError("stage065_pre_ai_top_n")

    ai = frame[frame["eval_date"].ne(pre_ai_eval_date)].copy()
    if ai.empty:
        raise RuntimeError("stage065_ai_months_missing")
    if not set(ai["score_type"]).issubset({AI_SCORE_TYPE, LOCKED_AI_SCORE_TYPE}):
        raise RuntimeError("stage065_ai_score_type_mismatch")
    for eval_date, month in ai.groupby("eval_date", sort=True):
        month = month.sort_values(["score_rank", "product_vt_symbol"], kind="stable")
        if month["score_type"].nunique() != 1:
            raise RuntimeError(f"stage065_ai_month_score_type_mixed:eval_date={eval_date}")
        if len(month) != AI_MONTH_PRODUCT_COUNT:
            raise RuntimeError(
                "stage065_ai_month_product_count:"
                f"eval_date={eval_date}:expected={AI_MONTH_PRODUCT_COUNT}:actual={len(month)}"
            )
        if month["product_vt_symbol"].nunique() != AI_MONTH_PRODUCT_COUNT:
            raise RuntimeError(f"stage065_ai_month_duplicate_product:eval_date={eval_date}")
        if month["score_rank"].tolist() != list(range(1, AI_MONTH_PRODUCT_COUNT + 1)):
            raise RuntimeError(f"stage065_ai_month_rank_range:eval_date={eval_date}")
        if set(month["top_n"]) != {AI_MONTH_PRODUCT_COUNT}:
            raise RuntimeError(f"stage065_ai_month_top_n:eval_date={eval_date}")
        fixed_rows = month[month["product_vt_symbol"].eq(FIXED_PRODUCT)]
        if len(fixed_rows) != 1 or int(fixed_rows.iloc[0]["score_rank"]) != AI_MONTH_PRODUCT_COUNT:
            raise RuntimeError(f"stage065_ai_month_fixed_fu:eval_date={eval_date}")
        non_fu = month[~month["product_vt_symbol"].eq(FIXED_PRODUCT)]
        if len(non_fu) != RANKED_NON_FU_COUNT or non_fu["score_rank"].tolist() != list(
            range(1, RANKED_NON_FU_COUNT + 1)
        ):
            raise RuntimeError(f"stage065_ai_month_ranked_non_fu:eval_date={eval_date}")

    latest_eval_date = str(ai["eval_date"].max())
    audit = {
        "source_path": str(source_path),
        "sha256": source_sha256,
        "row_count": int(len(frame)),
        "eval_date_count": int(frame["eval_date"].nunique()),
        "ai_eval_date_count": int(ai["eval_date"].nunique()),
        "pre_ai_eval_date": pre_ai_eval_date,
        "latest_eval_date": latest_eval_date,
    }
    return frame, audit


def _promote_eligibility(source: pd.DataFrame) -> pd.DataFrame:
    promoted = source.copy()
    promoted["strategy"] = OFFICIAL_STRATEGY
    promoted["score_type"] = promoted["score_type"].map(
        lambda value: (
            str(value)
            if str(value).startswith(PROMOTED_SCORE_TYPE_PREFIX)
            else f"{PROMOTED_SCORE_TYPE_PREFIX}{value}"
        )
    )
    promoted.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    promoted.reset_index(drop=True, inplace=True)
    return promoted.loc[:, ELIGIBILITY_COLUMNS]


def _latest_pool(live_eligibility: pd.DataFrame) -> pd.DataFrame:
    result = live_eligibility.loc[
        :, ["strategy", "eval_date", "product_vt_symbol", "score", "score_rank", "score_type"]
    ].copy()
    result.rename(
        columns={
            "score": "predicted_product_suitability_probability",
            "score_rank": "ai_rank",
            "score_type": "source_score_type",
        },
        inplace=True,
    )
    result["selection_role"] = result["product_vt_symbol"].map(
        lambda product: "fixed_fu" if product == FIXED_PRODUCT else "model_ranked"
    )
    return result.loc[
        :,
        [
            "strategy",
            "eval_date",
            "product_vt_symbol",
            "predicted_product_suitability_probability",
            "ai_rank",
            "selection_role",
            "source_score_type",
        ],
    ]


def _research_evidence() -> dict[str, Any]:
    return {
        "Stage061": {
            "passed": False,
            "decision": "offline_width_sweep_no_fullperiod_candidate_keep_stage037",
            "failed_gates": ["full_period_slippage_ratio_le_105pct"],
            "top10_full_period": {
                "end_equity": 21_870_488.80,
                "total_return_pct": 14_480.325867,
                "max_drawdown_pct": -39.914746,
                "sharpe": 1.586976,
                "total_slippage": 2_163_390.0,
                "trade_count": 798,
                "win_rate_pct": 53.734756,
                "broker10_peak_pct": 93.580701,
                "slippage_ratio_to_stage037": 1.3035964460352323,
            },
        },
        "Stage063": {
            "passed": False,
            "decision": "offline_top9_top10_multicycle_has_hard_fail_keep_stage037",
            "failed_gates": [
                "full_period_slippage_ratio_le_105pct",
                "fixed_cycle_dd_noninferior_rate_ge_80pct",
                "fixed_cycle_aggregate_slippage_le_105pct",
                "fixed_cycle_broker100_fail_count_not_above_stage037",
            ],
        },
        "Stage064": {
            "passed": False,
            "decision": "random_stress_diagnostic_only_keep_stage037_stop_topn_scan",
            "failed_gates": [
                "random_dd_noninferior_rate_ge_80pct",
                "random_aggregate_slippage_le_105pct",
                "random_broker100_fail_count_not_above_stage037",
                "stage063_fixed_multicycle_gates_already_failed",
            ],
            "top10_random_all_192_windows": {
                "return_noninferior_rate_pct": 84.375,
                "median_return_delta_pct": 9.973333,
                "dd_noninferior_2pp_rate_pct": 72.916667,
                "sharpe_noninferior_005_rate_pct": 92.708333,
                "aggregate_slippage_ratio": 1.136614,
                "broker100_fail_count": 1,
            },
        },
    }


def _build_report(summary: dict[str, Any], live_pool: pd.DataFrame) -> str:
    rows = [
        "| 排名 | 品种 | 角色 | 模型分数 |",
        "| ---: | --- | --- | ---: |",
    ]
    for row in live_pool.itertuples(index=False):
        rows.append(
            f"| {int(row.ai_rank)} | {row.product_vt_symbol} | "
            f"{row.selection_role} | {float(row.predicted_product_suitability_probability):.6f} |"
        )
    evidence = summary["research_evidence"]
    return "\n".join(
        [
            "# Stage065 Top10 + 固定 fu 正式晋升 AI 物料",
            "",
            f"- 生成时间（CST）：`{summary['generated_at_cst']}`",
            f"- 来源 commit：`{summary['source']['commit']}`",
            f"- 来源 eligibility SHA256：`{summary['source']['sha256']}`",
            f"- 正式选品策略：`{summary['eligibility_contract']['strategy']}`",
            f"- 最新 eval_date：`{summary['eval_date']}`",
            f"- 训练标签截止：`{summary['training_label_cutoff']}`",
            "- 自然门禁结论：`FAIL`",
            "- 本次晋升依据：用户显式授权，`operator_override=true`；不得表述为自然通过研究门禁。",
            "- 安全边界：仅转换并固化已有 eligibility；不训练、不评分、不回测、不连接 CTP，send/cancel/order API 调用均为 `0`。",
            "",
            "## 已知失败（完整保留）",
            "",
            f"- Stage061：`{evidence['Stage061']['decision']}`；全周期滑点为正式 Stage037 的 `130.36%`，超过冻结 `105%` 门。",
            f"- Stage063：`{evidence['Stage063']['decision']}`；固定多周期存在成本、回撤非劣和 broker100 硬失败。",
            f"- Stage064：`{evidence['Stage064']['decision']}`；192个随机窗口的回撤非劣率 `72.92%`、总滑点比 `113.66%`，并出现 `1` 个 broker100 失败窗口。",
            "",
            "## 最新正式池",
            "",
            *rows,
            "",
            "## 结构契约",
            "",
            "- AI月份：模型评分 Top10（不含fu）+ 固定 `fu.SHFE`，共11个；rank固定为1..11，top_n固定为11。",
            "- pre-AI边界：2019-12-31静态18品种，不含fu，rank为1..18，top_n为18。",
            "- 所有 score_type 均加 `stage182_promoted_` 前缀，允许后续 Stage182 月更保留历史快照。",
            "",
        ]
    )


def build_bundle(
    source_eligibility_path: Path,
    output_dir: Path,
    *,
    generated_at_cst: str | None = None,
) -> dict[str, Any]:
    source, source_audit = _load_and_validate_source(Path(source_eligibility_path))
    promoted = _promote_eligibility(source)
    latest_eval_date = source_audit["latest_eval_date"]
    live_eligibility = promoted[promoted["eval_date"].eq(latest_eval_date)].copy()
    live_eligibility.reset_index(drop=True, inplace=True)
    live_pool = _latest_pool(live_eligibility)

    requested_output_root = Path(output_dir).expanduser()
    if requested_output_root.is_symlink():
        raise RuntimeError("stage065_output_dir_symlink_forbidden")
    output_root = requested_output_root.resolve(strict=False)
    if output_root.exists():
        if not output_root.is_dir():
            raise RuntimeError("stage065_output_path_not_directory")
        if any(output_root.iterdir()):
            raise RuntimeError("stage065_output_dir_not_empty")
    else:
        output_root.mkdir(parents=True)
    output_paths = {name: output_root / filename for name, filename in OUTPUT_NAMES.items()}
    live_pool.to_csv(output_paths["live_pool"], index=False, encoding="utf-8-sig")
    live_eligibility.to_csv(
        output_paths["live_eligibility"], index=False, encoding="utf-8-sig"
    )
    promoted.to_csv(
        output_paths["combined_eligibility"], index=False, encoding="utf-8-sig"
    )

    generated_at = _generated_at_cst(generated_at_cst)
    summary: dict[str, Any] = {
        "model_tag": "stage065_top10_fu_formal_ai_bundle_v1",
        "source_model_tag": "product_suitability_wf_v1",
        "generated_at_cst": generated_at,
        "eval_date": latest_eval_date,
        "data_cutoff": SOURCE_DATA_CUTOFF,
        "source_max_date": SOURCE_DATA_CUTOFF,
        "training_label_cutoff": TRAINING_LABEL_CUTOFF,
        "training_label_cutoff_provenance": (
            "Stage182 live model metadata inherited by the Stage061 frozen ranking source"
        ),
        "source": {
            "stage": "Stage061",
            "commit": SOURCE_COMMIT,
            **source_audit,
        },
        "eligibility_contract": {
            "strategy": OFFICIAL_STRATEGY,
            "fixed_product": FIXED_PRODUCT,
            "ranked_non_fu_count": RANKED_NON_FU_COUNT,
            "ai_month_total_product_count": AI_MONTH_PRODUCT_COUNT,
            "pre_ai_static_product_count": PRE_AI_PRODUCT_COUNT,
            "pre_ai_static_contains_fu": False,
            "pre_ai_eval_date": source_audit["pre_ai_eval_date"],
            "latest_eval_date": latest_eval_date,
            "eval_date_count": source_audit["eval_date_count"],
            "ai_eval_date_count": source_audit["ai_eval_date_count"],
        },
        "research_evidence": _research_evidence(),
        "promotion_decision": {
            "natural_gates_pass": False,
            "operator_override": True,
            "override_scope": "user_authorized_direct_formal_promotion_of_top10_plus_fixed_fu",
            "known_failures_preserved": True,
        },
        "outputs": {name: str(path) for name, path in output_paths.items()},
        "order_api_called_count": 0,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "safety": {
            "overwrites_official_stage78_eligibility": False,
            "uses_future_label_for_eval_date": False,
            "real_order_enabled": False,
            "runs_backtest": False,
            "trains_or_scores_model": False,
            "order_api_called_count": 0,
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
        },
    }
    output_paths["summary"].write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    output_paths["report"].write_text(
        _build_report(summary, live_pool), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the Stage065 Top10 + fixed-fu formal AI five-asset bundle."
    )
    parser.add_argument("--source-eligibility", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--generated-at-cst",
        default="",
        help="Optional timezone-aware ISO timestamp; defaults to current Asia/Shanghai time.",
    )
    args = parser.parse_args()
    summary = build_bundle(
        args.source_eligibility,
        args.output_dir,
        generated_at_cst=args.generated_at_cst or None,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
