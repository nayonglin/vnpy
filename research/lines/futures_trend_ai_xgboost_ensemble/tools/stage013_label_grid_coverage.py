"""Audit complete account-label coverage without pruning on future activity."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


LINE = Path(__file__).resolve().parents[1]
ACTIVITY_PATH = (
    LINE / "artifacts/stage011_marginal_slot_activity_qualification/activity_audit.csv"
)
STAGE012_BASE = LINE / "artifacts/stage012_active_account_slot_probe"
PREREGISTRATION = LINE / "stages/20260901_1805_stage013_label_grid_coverage.md"
OUT = LINE / "artifacts/stage013_label_grid_coverage"
EXPECTED_RANKS = list(range(10, 19))
REQUIRED_COLUMNS = {
    "eval_date",
    "next_eval_date",
    "score_rank",
    "product_vt_symbol",
    "t18_open_trade_count",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validated_panel(activity: pd.DataFrame) -> pd.DataFrame:
    if missing := sorted(REQUIRED_COLUMNS - set(activity.columns)):
        raise RuntimeError(f"activity_columns_missing:{missing}")
    panel = activity.loc[:, sorted(REQUIRED_COLUMNS)].copy()
    panel["eval_date"] = pd.to_datetime(panel["eval_date"], errors="raise").dt.date.astype(str)
    panel["next_eval_date"] = pd.to_datetime(
        panel["next_eval_date"], errors="raise"
    ).dt.date.astype(str)
    panel["score_rank"] = pd.to_numeric(
        panel["score_rank"], errors="raise"
    ).astype(int)
    panel["t18_open_trade_count"] = pd.to_numeric(
        panel["t18_open_trade_count"], errors="raise"
    ).astype(int)
    if panel["t18_open_trade_count"].lt(0).any():
        raise RuntimeError("negative_activity_count")
    if panel.duplicated(["eval_date", "score_rank"]).any():
        raise RuntimeError("duplicate_month_rank")
    for eval_date, month in panel.groupby("eval_date", sort=True):
        observed = sorted(month["score_rank"].tolist())
        if observed != EXPECTED_RANKS:
            raise RuntimeError(f"month_rank_shape:{eval_date}:{observed}")
        if month["product_vt_symbol"].astype(str).duplicated().any():
            raise RuntimeError(f"month_product_duplicate:{eval_date}")
        if month["next_eval_date"].nunique() != 1:
            raise RuntimeError(f"month_next_date_shape:{eval_date}")
    panel.sort_values(["eval_date", "score_rank"], inplace=True, kind="mergesort")
    panel.reset_index(drop=True, inplace=True)
    return panel


def build_full_grid_label_plan(activity: pd.DataFrame) -> pd.DataFrame:
    panel = _validated_panel(activity)
    plan = panel.copy()
    plan["arm"] = plan["score_rank"].map(lambda value: f"R{int(value):02d}")
    plan["label_run_required"] = True
    plan["future_activity_used_for_pruning"] = False
    plan["historical_t18_active_diagnostic"] = plan["t18_open_trade_count"].gt(0)
    plan["run_id"] = plan["eval_date"].str.replace("-", "", regex=False) + "_" + plan["arm"]
    return plan


def summarize_coverage(activity: pd.DataFrame) -> dict[str, int]:
    panel = _validated_panel(activity)
    panel["active"] = panel["t18_open_trade_count"].gt(0)
    monthly = panel.groupby("eval_date", sort=True).agg(
        active_rows=("active", "sum"),
        rank10_active=("active", "first"),
    )
    monthly["active_challengers"] = (
        monthly["active_rows"] - monthly["rank10_active"].astype(int)
    )
    return {
        "months": int(panel["eval_date"].nunique()),
        "full_grid_runs": int(len(panel)),
        "rank10_active_months": int(monthly["rank10_active"].sum()),
        "active_challenger_rows": int(
            panel[panel["score_rank"].gt(10)]["active"].sum()
        ),
        "months_with_active_challenger": int(
            monthly["active_challengers"].ge(1).sum()
        ),
        "months_with_two_active_challengers": int(
            monthly["active_challengers"].ge(2).sum()
        ),
    }


def _stage012_decision_path() -> Path:
    latest = json.loads((STAGE012_BASE / "LATEST.json").read_text(encoding="utf-8"))
    return Path(latest["attempt_path"]) / "decision.json"


def _budget(
    *,
    full_grid_runs: int,
    months: int,
    stage012_decision: dict[str, Any],
) -> dict[str, Any]:
    wall = np.array(
        [
            float(receipt["wall_seconds"])
            for receipt in stage012_decision["worker_receipts"].values()
        ],
        dtype=float,
    )
    sentinel_repeat_runs = len(range(0, months, 12))
    total_runs = full_grid_runs + sentinel_repeat_runs
    median_seconds = float(np.median(wall))
    observed_max_seconds = float(wall.max())
    return {
        "stage012_observed_workers": int(len(wall)),
        "stage012_wall_seconds_median": median_seconds,
        "stage012_wall_seconds_max": observed_max_seconds,
        "full_grid_main_runs": int(full_grid_runs),
        "A2_sentinel_repeat_runs": int(sentinel_repeat_runs),
        "total_process_runs": int(total_runs),
        "serial_hours_at_observed_median": float(total_runs * median_seconds / 3600.0),
        "serial_hours_at_observed_max": float(total_runs * observed_max_seconds / 3600.0),
        "two_worker_hours_at_observed_max": float(
            total_runs * observed_max_seconds / 3600.0 / 2.0
        ),
        "four_worker_hours_at_observed_max": float(
            total_runs * observed_max_seconds / 3600.0 / 4.0
        ),
        "budget_is_lower_bound_for_later_end_dates": True,
    }


def main() -> None:
    if OUT.exists():
        raise RuntimeError(f"stage013_output_already_exists:{OUT}")
    activity = pd.read_csv(ACTIVITY_PATH)
    plan = build_full_grid_label_plan(activity)
    coverage = summarize_coverage(activity)
    stage012_path = _stage012_decision_path()
    stage012 = json.loads(stage012_path.read_text(encoding="utf-8"))
    if stage012.get("decision") != "stage012_account_label_identifiable_continue_coverage_study":
        raise RuntimeError("stage012_upstream_not_qualified")
    budget = _budget(
        full_grid_runs=coverage["full_grid_runs"],
        months=coverage["months"],
        stage012_decision=stage012,
    )
    panel = _validated_panel(activity)
    panel["active"] = panel["t18_open_trade_count"].gt(0)
    by_rank = (
        panel.groupby("score_rank", sort=True)
        .agg(
            months=("eval_date", "size"),
            active_months=("active", "sum"),
            open_trades=("t18_open_trade_count", "sum"),
        )
        .reset_index()
    )
    monthly = (
        panel.groupby(["eval_date", "next_eval_date"], sort=True)
        .agg(
            active_rows=("active", "sum"),
            open_trades=("t18_open_trade_count", "sum"),
        )
        .reset_index()
    )
    active_pruned_runs = coverage["months"] + coverage["active_challenger_rows"]
    summary = {
        "line_id": "futures_trend_ai_xgboost_ensemble",
        "stage": "Stage013",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision": "stage013_full_grid_required_activity_pruning_rejected",
        "coverage": coverage,
        "activity_pruned_runs_for_diagnostic_only": int(active_pruned_runs),
        "runs_omitted_if_illegally_pruned": int(
            coverage["full_grid_runs"] - active_pruned_runs
        ),
        "activity_pruning_allowed": False,
        "upstream_identity_clean": False,
        "label_batch_launch_allowed": False,
        "identity_blockers": [
            "workspace_root_sitecustomize_not_in_stage012_contract",
            "python_site_packages_pth_not_in_stage012_contract",
            "stage012_identity_hardened_cold_rerun_pending",
            "stage012_independent_review_pending",
        ],
        "reason": (
            "T18 activity is post-decision and account-context-dependent; inactivity "
            "cannot establish a zero Top10 counterfactual label"
        ),
        "budget": budget,
        "model_geometry": {
            "month_groups": coverage["months"],
            "rows": coverage["full_grid_runs"],
            "legacy_feature_count": 108,
            "rows_per_legacy_feature": float(coverage["full_grid_runs"] / 108.0),
            "month_groups_per_legacy_feature": float(coverage["months"] / 108.0),
            "direct_108_feature_training_allowed": False,
            "label_based_feature_selection_allowed": False,
        },
        "next_protocol": {
            "complete_rank_grid": EXPECTED_RANKS,
            "A2_sentinel_every_n_months": 12,
            "cold_process": True,
            "checkpoint_reuse": False,
            "campaign_level_identity_contract": True,
            "compact_target_period_artifacts": True,
            "partial_result_driven_pruning": False,
        },
        "inputs": {
            "activity_audit": str(ACTIVITY_PATH.resolve()),
            "activity_audit_sha256": _sha256(ACTIVITY_PATH),
            "stage012_decision": str(stage012_path.resolve()),
            "stage012_decision_sha256": _sha256(stage012_path),
            "preregistration": str(PREREGISTRATION.resolve()),
            "preregistration_sha256": _sha256(PREREGISTRATION),
        },
        "runs_backtest": False,
        "trains_model": False,
        "order_api_called_count": 0,
        "ctp_connected": False,
    }
    OUT.mkdir(parents=True, exist_ok=False)
    plan.to_csv(OUT / "full_grid_label_plan.csv", index=False, encoding="utf-8-sig")
    by_rank.to_csv(OUT / "activity_by_rank.csv", index=False, encoding="utf-8-sig")
    monthly.to_csv(OUT / "monthly_coverage.csv", index=False, encoding="utf-8-sig")
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report = (
        "# Stage013 账户边际标签完整网格与计算预算\n\n"
        f"- 决策：`{summary['decision']}`。\n"
        f"- 完整网格：{coverage['months']}个月 × 9 ranks = "
        f"{coverage['full_grid_runs']}个主任务。\n"
        f"- 若按未来活动非法裁剪只剩{active_pruned_runs}个任务，会漏掉"
        f"{summary['runs_omitted_if_illegally_pruned']}个上下文未知标签。\n"
        f"- Stage012墙钟外推：串行中位约{budget['serial_hours_at_observed_median']:.2f}小时，"
        f"按观测最大值约{budget['serial_hours_at_observed_max']:.2f}小时；后期月份可能更慢。\n"
        "- 51个月组不足以直接承载108特征XGBoost；必须在看标签前固定低维特征合同。\n"
        "- 批量启动门关闭：先补`sitecustomize/.pth`身份、冷重跑Stage012并完成独立复核。\n"
        "- 本阶段不回测、不训练模型、不连接CTP、不调用订单API。\n\n"
        + by_rank.to_markdown(index=False)
        + "\n"
    )
    (OUT / "report.md").write_text(report, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
