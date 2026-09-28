"""Run the frozen Stage003 XGBoost pool through the production-equivalent engine."""

from __future__ import annotations

import gc
import hashlib
import json
import os
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd


LINE = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
PRODUCTION_ROOT = Path("/Users/bytedance/Desktop/person/vnpy_production_live")
PORTFOLIO_DIR = PRODUCTION_ROOT / "examples/portfolio_backtesting"
RUNTIME_ROOT = Path("/private/tmp/vnpy-stage004-xgboost-runtime")
RUNTIME_DATABASE = RUNTIME_ROOT / ".vntrader/database.db"
OUT = LINE / "artifacts/stage004_fullperiod_true_engine"
CHECKPOINT_DIR = OUT / "checkpoints"

FORMAL_RELEASE_ID = "m0004_20260831T112631+0800_2485073e9594"
FORMAL_RELEASE = (
    PRODUCTION_ROOT
    / "official_strategy_materials/ai_top10_plus_fu_official_live_v1/releases"
    / FORMAL_RELEASE_ID
)
FORMAL_ELIGIBILITY = FORMAL_RELEASE / "payload/ai/stage182/combined_eligibility.csv"
FORMAL_CURRENT = PRODUCTION_ROOT / "official_strategy_materials/CURRENT.json"
STAGE003_SUMMARY = LINE / "artifacts/stage003_two_month_confirmed_ranker/summary.json"
STAGE003_PREDICTIONS = (
    LINE / "artifacts/stage003_two_month_confirmed_ranker/confirmed_predictions.csv"
)
CANDIDATE_ELIGIBILITY = OUT / "stage004_candidate_eligibility.csv"

OFFICIAL_STRATEGY = "ai_top10_plus_fu_official_live_v1"
FIXED_PRODUCT = "fu.SHFE"
PRE_AI_DATE = "2019-12-31"
PREDICTION_SCORE_COLUMN = "score_two_month_confirmed"
CANDIDATE_SCORE_TYPE = "stage003_two_month_confirmed_xgboost_top10_plus_fixed_fu"
ELIGIBILITY_COLUMNS = [
    "strategy",
    "score_type",
    "eval_date",
    "product_vt_symbol",
    "score",
    "score_rank",
    "top_n",
]
EXPECTED_OOS_MONTHS = 49
EXPECTED_FIRST_OOS_DATE = "2022-04-29"
EXPECTED_LAST_OOS_DATE = "2026-04-30"
START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-08-28")
EXPECTED_FIRST_TRADING_DAY = pd.Timestamp("2018-01-02")

FROZEN_REFERENCE_KEY = "stage061_top10_plus_fu_full_20180102_20260828_operator_override"
FROZEN_REFERENCE = {
    "end_equity": 21_870_488.80,
    "total_return_pct": 14_480.3259,
    "max_dd_pct": -39.9147,
    "sharpe": 1.586976,
    "total_slippage": 2_163_390.0,
    "total_trade_count": 798.0,
    "win_rate_pct": 53.7348,
    "broker10_peak_margin_to_equity_pct": 93.5807,
}
REFERENCE_TOLERANCES = {
    "end_equity": 0.11,
    "total_return_pct": 0.00011,
    "max_dd_pct": 0.00011,
    "sharpe": 0.0000011,
    "total_slippage": 0.01,
    "total_trade_count": 0.01,
    "win_rate_pct": 0.00011,
    "broker10_peak_margin_to_equity_pct": 0.00011,
}


def _canonical_dates(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="raise").dt.normalize()
    return parsed.dt.date.astype(str)


def _snapshot_blockers(month: pd.DataFrame, eval_date: str) -> list[str]:
    blockers: list[str] = []
    products = month["product_vt_symbol"].astype(str).tolist()
    ranks = pd.to_numeric(month["score_rank"], errors="coerce").tolist()
    top_ns = pd.to_numeric(month["top_n"], errors="coerce").tolist()
    if len(products) != len(set(products)):
        blockers.append("duplicate_products")
    if sorted(ranks) != list(range(1, len(month) + 1)):
        blockers.append("rank_range")
    if set(top_ns) != {len(month)}:
        blockers.append("top_n")
    if eval_date == PRE_AI_DATE:
        if len(month) != 18:
            blockers.append("pre_ai_count")
        if FIXED_PRODUCT in products:
            blockers.append("pre_ai_contains_fu")
        if not month["score_type"].astype(str).str.endswith("static18_pre_ai_boundary").all():
            blockers.append("pre_ai_score_type")
    else:
        if len(month) != 11:
            blockers.append("monthly_count")
        if products.count(FIXED_PRODUCT) != 1:
            blockers.append("fixed_fu_count")
        fixed_ranks = month.loc[
            month["product_vt_symbol"].astype(str).eq(FIXED_PRODUCT), "score_rank"
        ].tolist()
        if fixed_ranks != [11]:
            blockers.append("fixed_fu_rank")
    return blockers


def build_candidate_eligibility(
    formal: pd.DataFrame,
    predictions: pd.DataFrame,
    *,
    expected_oos_months: int = EXPECTED_OOS_MONTHS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    missing_formal = set(ELIGIBILITY_COLUMNS) - set(formal.columns)
    missing_predictions = {
        "eval_date",
        "product_vt_symbol",
        PREDICTION_SCORE_COLUMN,
    } - set(predictions.columns)
    if missing_formal:
        raise RuntimeError(f"formal_columns_missing:{sorted(missing_formal)}")
    if missing_predictions:
        raise RuntimeError(f"prediction_columns_missing:{sorted(missing_predictions)}")

    formal = formal.loc[:, ELIGIBILITY_COLUMNS].copy()
    formal["eval_date"] = _canonical_dates(formal["eval_date"])
    predictions = predictions.loc[
        :, ["eval_date", "product_vt_symbol", PREDICTION_SCORE_COLUMN]
    ].copy()
    predictions["eval_date"] = _canonical_dates(predictions["eval_date"])
    predictions["product_vt_symbol"] = predictions["product_vt_symbol"].astype(str)
    predictions[PREDICTION_SCORE_COLUMN] = pd.to_numeric(
        predictions[PREDICTION_SCORE_COLUMN], errors="raise"
    )

    strategies = set(formal["strategy"].astype(str))
    if len(strategies) != 1:
        raise RuntimeError(f"formal_strategy_count:{len(strategies)}")
    strategy = next(iter(strategies))
    if predictions.duplicated(["eval_date", "product_vt_symbol"]).any():
        raise RuntimeError("duplicate_prediction_product_month")
    prediction_dates = sorted(predictions["eval_date"].unique())
    if len(prediction_dates) != expected_oos_months:
        raise RuntimeError(
            f"unexpected_oos_month_count:{len(prediction_dates)}:{expected_oos_months}"
        )
    formal_dates = set(formal["eval_date"].unique())
    missing_dates = sorted(set(prediction_dates) - formal_dates)
    if missing_dates:
        raise RuntimeError(f"prediction_dates_not_in_formal:{missing_dates}")

    rows: list[pd.DataFrame] = []
    audits: list[dict[str, Any]] = []
    prediction_date_set = set(prediction_dates)
    for eval_date, formal_month in formal.groupby("eval_date", sort=True):
        formal_month = formal_month.sort_values("score_rank", kind="mergesort").reset_index(drop=True)
        formal_blockers = _snapshot_blockers(formal_month, str(eval_date))
        if formal_blockers:
            raise RuntimeError(f"formal_snapshot_invalid:{eval_date}:{formal_blockers}")
        if eval_date not in prediction_date_set:
            selected = formal_month.copy()
            source = "formal_preserved"
        else:
            prediction_month = predictions[predictions["eval_date"].eq(eval_date)].copy()
            if len(prediction_month) != 18 or prediction_month["product_vt_symbol"].nunique() != 18:
                raise RuntimeError(f"prediction_month_shape:{eval_date}:{len(prediction_month)}")
            if FIXED_PRODUCT in set(prediction_month["product_vt_symbol"]):
                raise RuntimeError(f"prediction_contains_fixed_fu:{eval_date}")
            prediction_month.sort_values(
                [PREDICTION_SCORE_COLUMN, "product_vt_symbol"],
                ascending=[False, True],
                kind="mergesort",
                inplace=True,
            )
            top10 = prediction_month.head(10).reset_index(drop=True)
            selected_rows = [
                {
                    "strategy": strategy,
                    "score_type": CANDIDATE_SCORE_TYPE,
                    "eval_date": str(eval_date),
                    "product_vt_symbol": str(row.product_vt_symbol),
                    "score": float(getattr(row, PREDICTION_SCORE_COLUMN)),
                    "score_rank": rank,
                    "top_n": 11,
                }
                for rank, row in enumerate(top10.itertuples(index=False), start=1)
            ]
            selected_rows.append(
                {
                    "strategy": strategy,
                    "score_type": CANDIDATE_SCORE_TYPE,
                    "eval_date": str(eval_date),
                    "product_vt_symbol": FIXED_PRODUCT,
                    "score": float(top10[PREDICTION_SCORE_COLUMN].min()) - 1e-6,
                    "score_rank": 11,
                    "top_n": 11,
                }
            )
            selected = pd.DataFrame(selected_rows, columns=ELIGIBILITY_COLUMNS)
            source = "stage003_oos"
        candidate_blockers = _snapshot_blockers(selected, str(eval_date))
        if candidate_blockers:
            raise RuntimeError(f"candidate_snapshot_invalid:{eval_date}:{candidate_blockers}")
        rows.append(selected)
        if eval_date != PRE_AI_DATE:
            formal_members = set(formal_month["product_vt_symbol"].astype(str)) - {FIXED_PRODUCT}
            candidate_members = set(selected["product_vt_symbol"].astype(str)) - {FIXED_PRODUCT}
            audits.append(
                {
                    "eval_date": str(eval_date),
                    "source": source,
                    "formal_non_fu_members": ",".join(sorted(formal_members)),
                    "candidate_non_fu_members": ",".join(sorted(candidate_members)),
                    "added_products": ",".join(sorted(candidate_members - formal_members)),
                    "removed_products": ",".join(sorted(formal_members - candidate_members)),
                    "changed_member_count": len(candidate_members - formal_members),
                    "fixed_fu_present": FIXED_PRODUCT in set(selected["product_vt_symbol"]),
                }
            )

    candidate = pd.concat(rows, ignore_index=True).loc[:, ELIGIBILITY_COLUMNS]
    if candidate.groupby("eval_date").size().to_dict() != formal.groupby("eval_date").size().to_dict():
        raise RuntimeError("candidate_month_coverage_drift")
    preserved_dates = formal_dates - prediction_date_set
    for eval_date in preserved_dates:
        left = formal[formal["eval_date"].eq(eval_date)].sort_values("score_rank").reset_index(drop=True)
        right = candidate[candidate["eval_date"].eq(eval_date)].sort_values("score_rank").reset_index(drop=True)
        if not left.equals(right):
            raise RuntimeError(f"formal_preservation_failed:{eval_date}")
    return candidate.reset_index(drop=True), pd.DataFrame(audits)


def baseline_reference_parity(
    actual: dict[str, Any] | pd.Series,
    reference: dict[str, float],
) -> dict[str, Any]:
    actual_map = dict(actual)
    mappings = {
        "end_equity": "end_equity",
        "total_return_pct": "total_return_pct",
        "max_dd_pct": "max_dd_pct",
        "sharpe": "sharpe",
        "total_slippage": "total_slippage",
        "total_trade_count": "total_trade_count",
        "win_rate_pct": "nonzero_daily_win_rate_pct",
        "broker10_peak_margin_to_equity_pct": "max_broker10_margin_to_equity_pct",
    }
    gates: dict[str, bool] = {}
    deltas: dict[str, float] = {}
    actual_values: dict[str, float] = {}
    for reference_key, actual_key in mappings.items():
        expected = float(reference[reference_key])
        observed = float(actual_map[actual_key])
        delta = observed - expected
        actual_values[reference_key] = observed
        deltas[reference_key] = delta
        gates[f"{reference_key}_within_tolerance"] = (
            abs(delta) <= REFERENCE_TOLERANCES[reference_key]
        )
    return {
        "passed": all(gates.values()),
        "gates": gates,
        "actual": actual_values,
        "expected": {key: float(value) for key, value in reference.items()},
        "deltas": deltas,
        "tolerances": REFERENCE_TOLERANCES,
    }


def evaluate_fullperiod_gates(
    baseline: dict[str, Any] | pd.Series,
    candidate: dict[str, Any] | pd.Series,
    *,
    baseline_reproduction_pass: bool,
    coverage_pass: bool = True,
    input_identity_pass: bool = True,
) -> dict[str, Any]:
    a = dict(baseline)
    c = dict(candidate)
    gates = {
        "input_identity_pass": bool(input_identity_pass),
        "baseline_reproduction_pass": bool(baseline_reproduction_pass),
        "coverage_pass": bool(coverage_pass),
        "total_return_strictly_higher": float(c["total_return_pct"])
        > float(a["total_return_pct"]),
        "max_drawdown_strictly_better": float(c["max_dd_pct"]) > float(a["max_dd_pct"]),
        "sharpe_noninferior": float(c["sharpe"]) >= float(a["sharpe"]),
        "slippage_le_105pct": float(c["total_slippage"])
        <= float(a["total_slippage"]) * 1.05,
        "trade_count_positive": float(c["total_trade_count"]) > 0,
        "account_survival_pass": bool(int(c["account_survival_pass"])),
        "broker10_peak_le_100pct": float(c["max_broker10_margin_to_equity_pct"]) <= 100.0,
        "days_over_100pct_not_worse": int(c["days_over_100pct"])
        <= int(a["days_over_100pct"]),
    }
    deltas = {
        key: float(c[key]) - float(a[key])
        for key in (
            "end_equity",
            "total_return_pct",
            "max_dd_pct",
            "sharpe",
            "total_slippage",
            "total_trade_count",
            "nonzero_daily_win_rate_pct",
            "max_broker10_margin_to_equity_pct",
            "days_over_100pct",
        )
        if key in a and key in c
    }
    return {"passed": all(gates.values()), "gates": gates, "deltas": deltas}


def _identity(path: Path, *, include_sha256: bool = True) -> dict[str, Any]:
    before = path.stat()
    result: dict[str, Any] = {
        "path": str(path.resolve()),
        "size": before.st_size,
        "mtime_ns": before.st_mtime_ns,
    }
    if include_sha256:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        result["sha256"] = digest.hexdigest()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError(f"file_changed_while_hashing:{path}")
    return result


def _load_production_modules() -> tuple[Any, Any, Any, Any]:
    if str(PORTFOLIO_DIR) not in sys.path:
        sys.path.insert(0, str(PORTFOLIO_DIR))
    import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
    import analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac as s827
    import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
    import qmt_roll_official_live_config as live_cfg

    return live_cfg, s513, s827, s901


def _coverage(curves: dict[str, pd.DataFrame]) -> dict[str, Any]:
    dates_by_arm: dict[str, pd.DatetimeIndex] = {}
    gates: dict[str, bool] = {}
    for arm, curve in curves.items():
        dates = pd.DatetimeIndex(pd.to_datetime(curve["date"], errors="raise").dt.normalize())
        dates_by_arm[arm] = dates
        gates[f"{arm}_dates_unique"] = not dates.duplicated().any()
        gates[f"{arm}_first_date"] = dates.min() == EXPECTED_FIRST_TRADING_DAY
        gates[f"{arm}_last_date"] = dates.max() == END
    gates["arm_dates_equal"] = dates_by_arm["A"].equals(dates_by_arm["C"])
    return {
        "passed": all(gates.values()),
        "gates": gates,
        "row_counts": {arm: len(dates) for arm, dates in dates_by_arm.items()},
    }


def _contract_sha256(
    arm: str,
    identities: dict[str, dict[str, Any]],
) -> str:
    payload = {
        "arm": arm,
        "start": START.date().isoformat(),
        "end": END.date().isoformat(),
        "identities": {
            key: {"size": value["size"], "sha256": value.get("sha256", "")}
            for key, value in identities.items()
        },
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _load_checkpoint(
    arm: str,
    contract_sha256: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame] | None:
    directory = CHECKPOINT_DIR / arm
    metadata_path = directory / "metadata.json"
    if not metadata_path.exists():
        return None
    metadata = json.loads(metadata_path.read_text())
    if metadata.get("contract_sha256") != contract_sha256:
        return None
    return (
        pd.read_csv(directory / "summary.csv"),
        pd.read_csv(directory / "curve.csv"),
        pd.read_csv(directory / "trades.csv"),
    )


def _save_checkpoint(
    arm: str,
    contract_sha256: str,
    summary: pd.DataFrame,
    curve: pd.DataFrame,
    trades: pd.DataFrame,
) -> None:
    directory = CHECKPOINT_DIR / arm
    directory.mkdir(parents=True, exist_ok=True)
    summary.to_csv(directory / "summary.csv", index=False)
    curve.to_csv(directory / "curve.csv", index=False)
    trades.to_csv(directory / "trades.csv", index=False)
    (directory / "metadata.json").write_text(
        json.dumps(
            {
                "arm": arm,
                "contract_sha256": contract_sha256,
                "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


def _run_arm(
    arm: str,
    *,
    metadata: dict[str, Any],
    s827: Any,
    s901: Any,
    override_builder: Callable[[], dict[str, Any]],
    contract_sha256: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cached = _load_checkpoint(arm, contract_sha256)
    if cached is not None:
        print(f"[stage004] reuse checkpoint {arm}", flush=True)
        return cached
    profile_name = (
        "stage004_A_official_logistic_pool"
        if arm == "A"
        else "stage004_C_stage003_two_month_confirmed_xgboost_pool"
    )
    label = "A formal AI pool" if arm == "A" else "C Stage003 confirmed XGBoost pool"
    original_builder = s901.build_official_live_strategy_overrides
    try:
        s901.build_official_live_strategy_overrides = override_builder
        combined, frames, live_spec = s901._run_live_c9(metadata, START, END)
    finally:
        s901.build_official_live_strategy_overrides = original_builder
    capital = replace(live_spec.capital, variant=profile_name, label=label)
    metric_spec = replace(live_spec, capital=capital, profile=profile_name)
    summary, curve = s827._metric(
        {"profile": profile_name, "spec": metric_spec}, combined
    )
    summary["experiment_arm"] = arm
    summary["window_name"] = "full_2018_20260828"
    curve["experiment_arm"] = arm
    trades = frames.get("trades", pd.DataFrame()).copy()
    trades["experiment_arm"] = arm
    _save_checkpoint(arm, contract_sha256, summary, curve, trades)
    del combined, frames
    gc.collect()
    return summary, curve, trades


def _report(
    summary: pd.DataFrame,
    baseline_parity: dict[str, Any],
    qualification: dict[str, Any],
    pool_audit: pd.DataFrame,
) -> str:
    indexed = summary.set_index("experiment_arm")
    lines = [
        "# Stage004 两月确认XGBoost全周期真引擎A/C",
        "",
        f"- 决策：`{'PASS' if qualification['passed'] else 'FAIL'}`",
        f"- A冻结基准复现：`{'PASS' if baseline_parity['passed'] else 'FAIL'}`",
        f"- 区间：`{START.date()}`至`{END.date()}`，15万元，交易规则与成本完全一致。",
        "- 唯一变量：2022-04至2026-04的49个月度选品池。",
        "",
        "| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | broker10峰值 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm, label in (("A", "A正式逻辑回归池"), ("C", "C两月确认XGBoost池")):
        row = indexed.loc[arm]
        lines.append(
            f"| {label} | {row['end_equity']:,.2f} | {row['total_return_pct']:.4f}% | "
            f"{row['max_dd_pct']:.4f}% | {row['sharpe']:.6f} | "
            f"{row['total_slippage']:,.0f} | {int(row['total_trade_count'])} | "
            f"{row['nonzero_daily_win_rate_pct']:.4f}% | "
            f"{row['max_broker10_margin_to_equity_pct']:.4f}% |"
        )
    lines.extend(["", "## 预声明门槛", ""])
    for name, passed in qualification["gates"].items():
        lines.append(f"- `{'PASS' if passed else 'FAIL'}` `{name}`")
    oos = pool_audit[pool_audit["source"].eq("stage003_oos")]
    lines.extend(
        [
            "",
            "## 月池边界",
            "",
            f"- 候选替换月份：`{len(oos)}`；首月`{oos['eval_date'].min()}`，末月`{oos['eval_date'].max()}`。",
            f"- 月均相对正式池换入品种数：`{oos['changed_member_count'].mean():.4f}`。",
            "- 2019-12-31前AI边界，以及候选窗口前后月份逐行保留正式物料。",
            "- 离线研究，不连接CTP，不调用下单，不自动晋升正式版本。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    if Path.cwd().resolve() != RUNTIME_ROOT.resolve():
        raise RuntimeError(
            f"stage004_must_run_from_isolated_runtime:{Path.cwd().resolve()}"
        )
    if os.environ.get("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR") != "1":
        raise RuntimeError("stage004_non_project_runtime_guard_override_missing")
    if os.environ.get("PYTHONDONTWRITEBYTECODE") not in {"1", "true", "True"}:
        print("[stage004] warning: run with -B or PYTHONDONTWRITEBYTECODE=1", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    upstream = json.loads(STAGE003_SUMMARY.read_text())
    if upstream.get("decision") != "stage003_two_month_confirmed_pass_allow_true_engine":
        raise RuntimeError("stage003_not_qualified")
    formal = pd.read_csv(FORMAL_ELIGIBILITY)
    predictions = pd.read_csv(STAGE003_PREDICTIONS)
    candidate, pool_audit = build_candidate_eligibility(formal, predictions)
    oos_dates = pool_audit.loc[
        pool_audit["source"].eq("stage003_oos"), "eval_date"
    ].tolist()
    if (
        len(oos_dates) != EXPECTED_OOS_MONTHS
        or min(oos_dates) != EXPECTED_FIRST_OOS_DATE
        or max(oos_dates) != EXPECTED_LAST_OOS_DATE
    ):
        raise RuntimeError(f"stage004_oos_boundary_drift:{min(oos_dates)}:{max(oos_dates)}")
    candidate.to_csv(CANDIDATE_ELIGIBILITY, index=False)
    pool_audit.to_csv(OUT / "stage004_membership_audit.csv", index=False)

    live_cfg, s513, s827, s901 = _load_production_modules()
    if live_cfg.OFFICIAL_LIVE_MATERIAL_RELEASE_ID != FORMAL_RELEASE_ID:
        raise RuntimeError(
            f"active_release_drift:{live_cfg.OFFICIAL_LIVE_MATERIAL_RELEASE_ID}"
        )
    if Path(live_cfg.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH).resolve() != FORMAL_ELIGIBILITY.resolve():
        raise RuntimeError("formal_eligibility_resolution_drift")
    config_reference = live_cfg.OFFICIAL_LIVE_REFERENCE_METRICS[FROZEN_REFERENCE_KEY]
    for key, expected in FROZEN_REFERENCE.items():
        if float(config_reference[key]) != float(expected):
            raise RuntimeError(f"frozen_reference_config_drift:{key}")

    core_paths = {
        "formal_current": FORMAL_CURRENT,
        "formal_eligibility": FORMAL_ELIGIBILITY,
        "stage003_summary": STAGE003_SUMMARY,
        "stage003_predictions": STAGE003_PREDICTIONS,
        "candidate_eligibility": CANDIDATE_ELIGIBILITY,
        "runner": Path(__file__).resolve(),
        "production_live_config": PORTFOLIO_DIR / "qmt_roll_official_live_config.py",
        "production_strategy": PORTFOLIO_DIR / "qmt_roll_portfolio_strategy.py",
        "production_universe": PORTFOLIO_DIR / "qmt_universe.py",
        "production_database": PRODUCTION_ROOT / ".vntrader/database.db",
        "runtime_database_copy": RUNTIME_DATABASE,
    }
    identities_before = {name: _identity(path) for name, path in core_paths.items()}
    expected_database_sha = "ecbe812bd092ec8cedbd00d8b4b3ec2b1fa9311034dc8379fc6981033405eaf3"
    if identities_before["production_database"]["sha256"] != expected_database_sha:
        raise RuntimeError("production_database_identity_drift")
    if identities_before["runtime_database_copy"]["sha256"] != expected_database_sha:
        raise RuntimeError("runtime_database_copy_identity_drift")

    metadata = s513._metadata()
    official_builder = live_cfg.build_official_live_strategy_overrides

    def candidate_builder() -> dict[str, Any]:
        overrides = dict(official_builder())
        overrides["ai_product_pool_eligibility_path"] = str(CANDIDATE_ELIGIBILITY.resolve())
        overrides["ai_product_pool_strategy"] = OFFICIAL_STRATEGY
        return overrides

    summaries: list[pd.DataFrame] = []
    curves: dict[str, pd.DataFrame] = {}
    trades: list[pd.DataFrame] = []
    for arm, builder in (("A", official_builder), ("C", candidate_builder)):
        contract = _contract_sha256(arm, identities_before)
        arm_summary, arm_curve, arm_trades = _run_arm(
            arm,
            metadata=metadata,
            s827=s827,
            s901=s901,
            override_builder=builder,
            contract_sha256=contract,
        )
        summaries.append(arm_summary)
        curves[arm] = arm_curve
        trades.append(arm_trades)
        if arm == "A":
            parity = baseline_reference_parity(
                arm_summary.iloc[0], FROZEN_REFERENCE
            )
            if not parity["passed"]:
                decision = {
                    "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "decision": "stage004_invalid_baseline_reproduction_stop_before_candidate",
                    "baseline_reference_parity": parity,
                    "safety": {
                        "writes_production": False,
                        "ctp_connected": False,
                        "order_api_called_count": 0,
                        "send_order_api_called_count": 0,
                        "cancel_order_api_called_count": 0,
                    },
                }
                (OUT / "decision.json").write_text(
                    json.dumps(decision, ensure_ascii=False, indent=2) + "\n"
                )
                raise RuntimeError("stage004_baseline_reproduction_failed")

    summary = pd.concat(summaries, ignore_index=True)
    curve = pd.concat([curves["A"], curves["C"]], ignore_index=True)
    trade_frame = pd.concat(trades, ignore_index=True) if trades else pd.DataFrame()
    coverage = _coverage(curves)
    indexed = summary.set_index("experiment_arm")
    baseline_parity = baseline_reference_parity(indexed.loc["A"], FROZEN_REFERENCE)
    identities_after = {name: _identity(path) for name, path in core_paths.items()}
    input_identity_pass = identities_before == identities_after
    qualification = evaluate_fullperiod_gates(
        indexed.loc["A"],
        indexed.loc["C"],
        baseline_reproduction_pass=baseline_parity["passed"],
        coverage_pass=coverage["passed"],
        input_identity_pass=input_identity_pass,
    )
    decision_name = (
        "stage004_fullperiod_pass_allow_multicycle"
        if qualification["passed"]
        else "stage004_fullperiod_fail_stop_candidate"
    )
    decision = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision": decision_name,
        "formal_release_id": FORMAL_RELEASE_ID,
        "window": {
            "start": START.date().isoformat(),
            "first_trading_day": EXPECTED_FIRST_TRADING_DAY.date().isoformat(),
            "end": END.date().isoformat(),
        },
        "candidate_pool": {
            "source_stage": "Stage003",
            "oos_months": len(oos_dates),
            "first_oos_date": min(oos_dates),
            "last_oos_date": max(oos_dates),
            "mean_changed_member_count_vs_formal": float(
                pool_audit.loc[
                    pool_audit["source"].eq("stage003_oos"), "changed_member_count"
                ].mean()
            ),
            "pre_and_post_oos_formal_rows_preserved": True,
            "fixed_fu_rank": 11,
        },
        "baseline_reference_parity": baseline_parity,
        "coverage": coverage,
        "qualification": qualification,
        "metrics": {
            arm: {
                key: float(indexed.loc[arm, key])
                for key in (
                    "end_equity",
                    "total_return_pct",
                    "max_dd_pct",
                    "sharpe",
                    "total_slippage",
                    "total_trade_count",
                    "nonzero_daily_win_rate_pct",
                    "account_survival_pass",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                )
            }
            for arm in ("A", "C")
        },
        "input_identity_pass": input_identity_pass,
        "identities": identities_before,
        "safety": {
            "strategy_backtest_ran": True,
            "writes_production": False,
            "ctp_connected": False,
            "order_api_called_count": 0,
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
            "automatic_promotion": False,
        },
    }
    summary.to_csv(OUT / "summary.csv", index=False)
    curve.to_csv(OUT / "equity_curve.csv", index=False)
    trade_frame.to_csv(OUT / "trades.csv", index=False)
    (OUT / "decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    (OUT / "report.md").write_text(
        _report(summary, baseline_parity, qualification, pool_audit)
    )
    print(
        json.dumps(
            {
                "decision": decision_name,
                "metrics": decision["metrics"],
                "qualification": qualification,
                "baseline_reference_parity": baseline_parity["passed"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
