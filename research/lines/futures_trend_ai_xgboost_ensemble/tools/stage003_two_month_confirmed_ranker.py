"""Qualify a two-month-confirmed overlay on frozen Stage002 predictions."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


LINE = Path(__file__).resolve().parents[1]
OUT = LINE / "artifacts/stage003_two_month_confirmed_ranker"
STAGE002_PATH = LINE / "tools/stage002_dual_objective_ranker.py"
STAGE002_OUT = LINE / "artifacts/stage002_dual_objective_ranker"
STAGE002_PREDICTIONS = STAGE002_OUT / "oos_predictions.csv"
STAGE002_SUMMARY = STAGE002_OUT / "summary.json"
DATE_COLUMN = "eval_date"
PRODUCT_COLUMN = "product_vt_symbol"
TOP_N = 10
SCORE_COLUMN = "score_two_month_confirmed"


def _load_stage002_module():
    spec = importlib.util.spec_from_file_location("stage002_for_stage003", STAGE002_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load Stage002 module: {STAGE002_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def add_two_month_confirmed_scores(
    predictions: pd.DataFrame,
    *,
    top_n: int = TOP_N,
) -> pd.DataFrame:
    result = predictions.copy()
    result[DATE_COLUMN] = pd.to_datetime(result[DATE_COLUMN]).dt.normalize()
    result.sort_values([DATE_COLUMN, PRODUCT_COLUMN], inplace=True)
    result[SCORE_COLUMN] = np.nan
    result["confirmed_by_two_months"] = False
    result["confirmed_count"] = 0
    previous_raw_top: set[str] | None = None
    for eval_date, month in result.groupby(DATE_COLUMN, sort=True):
        raw_order = month.sort_values(
            ["score_fused", PRODUCT_COLUMN], ascending=[False, True], kind="mergesort"
        )[PRODUCT_COLUMN].astype(str).tolist()
        logistic_order = month.sort_values(
            ["score_logistic", PRODUCT_COLUMN], ascending=[False, True], kind="mergesort"
        )[PRODUCT_COLUMN].astype(str).tolist()
        raw_top = set(raw_order[:top_n])
        confirmed = (
            [product for product in raw_order[:top_n] if product in previous_raw_top]
            if previous_raw_top is not None
            else []
        )
        full_order = confirmed + [product for product in logistic_order if product not in confirmed]
        if len(full_order) != len(month) or len(set(full_order)) != len(month):
            raise RuntimeError(f"invalid confirmed order: {pd.Timestamp(eval_date).date()}")
        score_by_product = {
            product: float(len(full_order) - rank)
            for rank, product in enumerate(full_order)
        }
        mask = result[DATE_COLUMN].eq(eval_date)
        result.loc[mask, SCORE_COLUMN] = result.loc[mask, PRODUCT_COLUMN].map(score_by_product)
        result.loc[mask, "confirmed_by_two_months"] = result.loc[mask, PRODUCT_COLUMN].isin(confirmed)
        result.loc[mask, "confirmed_count"] = len(confirmed)
        previous_raw_top = raw_top
    if result[SCORE_COLUMN].isna().any():
        raise RuntimeError("confirmed score construction left missing values")
    return result.reset_index(drop=True)


def _identity(path: Path) -> dict[str, Any]:
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError(f"file changed while hashing: {path}")
    return {"path": str(path), "size": after.st_size, "sha256": digest.hexdigest()}


def _render_report(summary: dict[str, Any]) -> str:
    a = summary["arms"]["A_logistic"]
    c = summary["arms"]["C3_confirmed"]
    lines = [
        "# Stage003 两月确认XGBoost月池资格报告",
        "",
        f"- 决策：`{summary['decision']}`",
        f"- OOS月份：`{summary['oos_months']}`",
        f"- 平均确认品种数：`{summary['confirmation']['mean_confirmed_count']:.4f}`",
        "",
        "| 指标 | A逻辑回归 | C3两月确认 |",
        "| --- | ---: | ---: |",
        f"| 双目标Rank IC均值 | {a['mean_dual_rank_ic']:.6f} | {c['mean_dual_rank_ic']:.6f} |",
        f"| 双目标Rank IC中位数 | {a['median_dual_rank_ic']:.6f} | {c['median_dual_rank_ic']:.6f} |",
        f"| Top10月均未来净利润 | {a['top10_mean_future_net_pnl_60d']:.2f} | {c['top10_mean_future_net_pnl_60d']:.2f} |",
        f"| Top10净利润10%分位 | {a['top10_p10_future_net_pnl_60d']:.2f} | {c['top10_p10_future_net_pnl_60d']:.2f} |",
        f"| Top10月均未来最大回撤 | {a['top10_mean_future_max_drawdown_60d']:.2f} | {c['top10_mean_future_max_drawdown_60d']:.2f} |",
        f"| Top10回撤10%分位 | {a['top10_p10_future_max_drawdown_60d']:.2f} | {c['top10_p10_future_max_drawdown_60d']:.2f} |",
        f"| Top10换入率 | {a['top10_turnover']:.4%} | {c['top10_turnover']:.4%} |",
        "",
        "## 预声明门槛",
        "",
    ]
    for name, passed in summary["qualification"]["gates"].items():
        lines.append(f"- `{'PASS' if passed else 'FAIL'}` `{name}`")
    lines.extend(
        [
            "",
            "- 资格通过才允许进入真引擎；失败不得修改确认月数或填充规则。",
            "- 本阶段没有运行策略回测，不产生实际权益、最大回撤或Sharpe。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    stage002 = _load_stage002_module()
    stage001 = stage002._load_stage001_module()
    OUT.mkdir(parents=True, exist_ok=True)
    upstream = json.loads(STAGE002_SUMMARY.read_text())
    if upstream["decision"] != "stage002_dual_objective_ranker_fail_stop_no_backtest":
        raise RuntimeError("Stage002 decision changed")
    current_path = stage001.MATERIALS / "CURRENT.json"
    current = stage001.read_json(current_path)
    if current.get("release_id") != stage001.FORMAL_RELEASE_ID:
        raise RuntimeError("active formal release changed")
    metadata = stage001.read_json(stage001.ORIGINAL_METADATA)
    source_paths = [
        Path(metadata["source_paths"][key])
        for key in ("position_changes", "entry_candidate_snapshots")
    ]
    tracked = [
        current_path,
        stage001.ORIGINAL_METADATA,
        STAGE002_PATH,
        STAGE002_SUMMARY,
        STAGE002_PREDICTIONS,
        *source_paths,
        Path(__file__).resolve(),
    ]
    before = {str(path): _identity(path) for path in tracked}
    for key, source_path in zip(("position_changes", "entry_candidate_snapshots"), source_paths):
        expected = metadata["source_identities"][key]
        actual = before[str(source_path)]
        if actual["sha256"] != expected["sha256"] or actual["size"] != expected["size"]:
            raise RuntimeError(f"source identity mismatch: {key}")

    predictions = pd.read_csv(STAGE002_PREDICTIONS, parse_dates=[DATE_COLUMN])
    products = sorted(predictions[PRODUCT_COLUMN].astype(str).unique())
    if len(products) != 18 or predictions[DATE_COLUMN].nunique() != 49:
        raise RuntimeError("Stage002 prediction panel changed")
    model_code = stage001._load_frozen_model_code(products)
    model_code.POSITION_CHANGES_PATH = source_paths[0]
    model_code.ENTRY_SNAPSHOTS_PATH = source_paths[1]
    daily = model_code.build_product_daily()
    candidate = add_two_month_confirmed_scores(predictions)
    score_columns = {
        "A_logistic": "score_logistic",
        "C3_confirmed": SCORE_COLUMN,
    }
    monthly, selections = stage002.build_metric_rows(candidate, daily, score_columns)
    arms = {arm: stage002.summarize_arm(monthly, selections, arm) for arm in score_columns}
    yearly = monthly.groupby(["year", "arm"], as_index=False).agg(
        mean_dual_rank_ic=("dual_rank_ic", "mean"),
        mean_top10_future_net_pnl_60d=("top10_future_net_pnl_60d", "mean"),
        mean_top10_future_max_drawdown_60d=("top10_future_max_drawdown_60d", "mean"),
        months=(DATE_COLUMN, "nunique"),
    )
    inputs = stage002.build_gate_inputs(
        arms,
        yearly,
        "C3_confirmed",
        identity_pass=True,
        determinism_pass=upstream["determinism_max_abs_error"] <= 1e-12,
        path_parity_pass=upstream["path_parity_max_abs_error"] <= 1e-10,
        oos_months=int(candidate[DATE_COLUMN].nunique()),
    )
    qualification = stage002.evaluate_candidate_gates(inputs)
    decision = (
        "stage003_two_month_confirmed_pass_allow_true_engine"
        if qualification["passed"]
        else "stage003_two_month_confirmed_fail_stop_no_backtest"
    )
    after = {str(path): _identity(path) for path in tracked}
    if before != after:
        raise RuntimeError("Stage003 source changed during run")
    confirmed_by_month = candidate.groupby(DATE_COLUMN, as_index=False)["confirmed_count"].first()
    summary = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision": decision,
        "formal_release_id": stage001.FORMAL_RELEASE_ID,
        "upstream_stage002_summary_sha256": before[str(STAGE002_SUMMARY)]["sha256"],
        "oos_months": int(candidate[DATE_COLUMN].nunique()),
        "arms": arms,
        "gate_inputs": inputs,
        "qualification": qualification,
        "confirmation": {
            "months": 2,
            "first_month_falls_back_to_a": True,
            "mean_confirmed_count": float(confirmed_by_month["confirmed_count"].mean()),
            "median_confirmed_count": float(confirmed_by_month["confirmed_count"].median()),
            "minimum_confirmed_count": int(confirmed_by_month["confirmed_count"].min()),
            "maximum_confirmed_count": int(confirmed_by_month["confirmed_count"].max()),
        },
        "source_unchanged": True,
        "identities": before,
        "safety": {
            "runs_strategy_backtest": False,
            "writes_production": False,
            "ctp_connected": False,
            "order_api_called_count": 0,
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
        },
    }
    candidate[
        [
            DATE_COLUMN,
            PRODUCT_COLUMN,
            "score_logistic",
            "score_fused",
            SCORE_COLUMN,
            "confirmed_by_two_months",
            "confirmed_count",
            stage002.FUTURE_PNL_COLUMN,
            stage002.FUTURE_DRAWDOWN_COLUMN,
            stage002.DUAL_UTILITY_COLUMN,
        ]
    ].to_csv(OUT / "confirmed_predictions.csv", index=False)
    monthly.to_csv(OUT / "monthly_metrics.csv", index=False)
    yearly.to_csv(OUT / "yearly_metrics.csv", index=False)
    confirmed_by_month.to_csv(OUT / "confirmed_count_by_month.csv", index=False)
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    (OUT / "report.md").write_text(_render_report(summary))
    print(
        json.dumps(
            {
                "decision": decision,
                "arms": arms,
                "confirmation": summary["confirmation"],
                "qualification": qualification,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
