from __future__ import annotations

import importlib.util
import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from vnpy.trader.constant import Interval

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
STAGE087_SCRIPT = PROJECT_DIR / "analyze_qmt_roll_stage387_stage079_short_holding_candidates.py"

sys.path.insert(0, str(PROJECT_DIR.resolve()))
from analyze_qmt_roll_stage324_true_combo_capital_margin import _c3_overrides  # noqa: E402
from build_qmt_roll_stage153_stage78_anti_fit_validation import NextOpenDelayedExecutionEngine  # noqa: E402
from main_contract_mapping import build_contract_metadata, load_product_universe_symbols  # noqa: E402
from qmt_backtest_runtime_guard import assert_stage196_database_sentinels  # noqa: E402
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy  # noqa: E402
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT  # noqa: E402
from run_qmt_roll_backtest import build_roll_setting  # noqa: E402
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (  # noqa: E402
    BASE_RISK_RATIO,
)


MODEL_TAG = "stage441_execution_timing_gap_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage441_execution_timing_gap_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
C3_CAPITAL = 500_000.0
STAGE079_CASH = 115_000.0
BASELINE_VARIANT = "stage079"
STAGE103_VARIANT = "stage103_same_day_close"
STAGE079_T1_VARIANT = "stage079_c3_t1_next_open"
STAGE103_T1_VARIANT = "stage103_c3_t1_next_open_satellite_frozen"

STAGE403_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage403_stage079_xsmom_execution_margin_audit_daily_stage403_stage079_xsmom_execution_margin_audit_v1.csv"
)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
DELTA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_delta_{MODEL_TAG}.csv"
C3_T1_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_c3_t1_daily_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _load_stage087_module():
    spec = importlib.util.spec_from_file_location("stage087_gate_for_stage441", STAGE087_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {STAGE087_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["stage087_gate_for_stage441"] = module
    spec.loader.exec_module(module)
    return module


s087 = _load_stage087_module()


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda x: f"{x:.4f}" if pd.notna(x) else "")
    return view.to_markdown(index=False)


def _run_c3_t1() -> pd.DataFrame:
    assert_stage196_database_sentinels()
    overrides = _c3_overrides(START_DT)
    preload_start = max(PRELOAD_START_DT, START_DT - timedelta(days=365))
    supported_symbols = load_product_universe_symbols(str(overrides.get("product_universe_csv_path", "") or ""))
    metadata = build_contract_metadata(supported_symbols=supported_symbols)

    engine = NextOpenDelayedExecutionEngine()
    engine.output = lambda msg: None
    engine.set_parameters(
        vt_symbols=metadata["vt_symbols"],
        interval=Interval.DAILY,
        start=preload_start,
        end=END_DT,
        rates=metadata["rates"],
        slippages=metadata["slippages"],
        sizes=metadata["sizes"],
        priceticks=metadata["priceticks"],
        capital=C3_CAPITAL,
    )
    setting = build_roll_setting(
        metadata["margin_ratios"],
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=overrides,
    )
    setting["capital_base"] = C3_CAPITAL
    engine.add_strategy(QmtRollPortfolioStrategy, setting)
    engine.load_data()
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    if daily_df is None or daily_df.empty:
        return pd.DataFrame(columns=["date", "c3_t1_balance", "c3_t1_net_pnl", "c3_t1_trade_count", "c3_t1_slippage"])
    frame = daily_df.copy()
    frame = frame.loc[(frame.index >= START_DT.date()) & (frame.index <= END_DT.date())]
    frame = frame.reset_index().rename(columns={"index": "date"})
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["c3_t1_net_pnl"] = pd.to_numeric(frame.get("net_pnl", 0.0), errors="coerce").fillna(0.0)
    frame["c3_t1_trade_count"] = pd.to_numeric(frame.get("trade_count", 0.0), errors="coerce").fillna(0.0)
    frame["c3_t1_slippage"] = pd.to_numeric(frame.get("slippage", 0.0), errors="coerce").fillna(0.0)
    if "balance" in frame.columns:
        frame["c3_t1_balance"] = pd.to_numeric(frame["balance"], errors="coerce").ffill().fillna(C3_CAPITAL)
    else:
        frame["c3_t1_balance"] = C3_CAPITAL + frame["c3_t1_net_pnl"].cumsum()
    return frame[["date", "c3_t1_balance", "c3_t1_net_pnl", "c3_t1_trade_count", "c3_t1_slippage"]]


def _candidate(variant: str, label: str, equity: pd.Series, note: str) -> Any:
    equity = equity.sort_index().dropna()
    return s087.Candidate(
        variant=variant,
        label=label,
        equity=equity,
        capital_used=ACCOUNT_CAPITAL,
        candidate_class="execution_timing_audit",
        eligible_for_promotion=False,
        note=note,
    )


def _load_stage403_full() -> pd.DataFrame:
    frame = pd.read_csv(STAGE403_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[frame["window_name"].eq("start_2020")].copy()
    numeric_cols = [
        "c3_net_pnl",
        "c3_trade_count",
        "c3_slippage",
        "satellite_daily_pnl",
        "satellite_slippage_cost",
        "equity",
        "trade_count",
        "combo_slippage",
    ]
    for column in numeric_cols:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date"]).sort_values(["variant", "date"])


def _build_audit_curves(stage403: pd.DataFrame, c3_t1: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    baseline = (
        stage403[stage403["variant"].eq("stage079")]
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .copy()
    )
    stage103 = (
        stage403[stage403["variant"].eq("xsmom_vt10_q_momq_round_half_true_broker10_guard")]
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .copy()
    )
    merged = baseline[
        ["date", "equity", "c3_net_pnl", "c3_trade_count", "c3_slippage"]
    ].rename(
        columns={
            "equity": "stage079_same_equity",
            "c3_net_pnl": "c3_same_net_pnl",
            "c3_trade_count": "c3_same_trade_count",
            "c3_slippage": "c3_same_slippage",
        }
    )
    merged = merged.merge(
        stage103[["date", "equity", "satellite_daily_pnl", "satellite_slippage_cost", "trade_count", "combo_slippage"]].rename(
            columns={
                "equity": "stage103_same_equity",
                "satellite_daily_pnl": "stage103_satellite_pnl",
                "satellite_slippage_cost": "stage103_satellite_slippage",
                "trade_count": "stage103_same_trade_count",
                "combo_slippage": "stage103_same_slippage",
            }
        ),
        on="date",
        how="outer",
    )
    merged = merged.merge(c3_t1, on="date", how="outer")
    merged = merged.sort_values("date").reset_index(drop=True)
    for column in [
        "c3_same_net_pnl",
        "c3_same_trade_count",
        "c3_same_slippage",
        "stage103_satellite_pnl",
        "stage103_satellite_slippage",
        "stage103_same_trade_count",
        "stage103_same_slippage",
        "c3_t1_net_pnl",
        "c3_t1_trade_count",
        "c3_t1_slippage",
    ]:
        merged[column] = pd.to_numeric(merged.get(column, 0.0), errors="coerce").fillna(0.0)

    merged["stage079_same_equity_rebuilt"] = ACCOUNT_CAPITAL + merged["c3_same_net_pnl"].cumsum()
    merged["stage079_t1_equity"] = ACCOUNT_CAPITAL + merged["c3_t1_net_pnl"].cumsum()
    merged["stage103_t1_equity"] = ACCOUNT_CAPITAL + (merged["c3_t1_net_pnl"] + merged["stage103_satellite_pnl"]).cumsum()
    merged["c3_t1_minus_same_net_pnl"] = merged["c3_t1_net_pnl"] - merged["c3_same_net_pnl"]
    merged["stage079_t1_minus_same_equity"] = merged["stage079_t1_equity"] - merged["stage079_same_equity_rebuilt"]
    merged["stage103_t1_minus_same_equity"] = merged["stage103_t1_equity"] - merged["stage103_same_equity"]

    curves = pd.concat(
        [
            pd.DataFrame(
                {
                    "date": merged["date"],
                    "variant": BASELINE_VARIANT,
                    "label": "Stage079 same-day close",
                    "equity": merged["stage079_same_equity_rebuilt"],
                    "trade_count": merged["c3_same_trade_count"],
                    "slippage": merged["c3_same_slippage"],
                }
            ),
            pd.DataFrame(
                {
                    "date": merged["date"],
                    "variant": STAGE079_T1_VARIANT,
                    "label": "Stage079 C3 T+1 next open",
                    "equity": merged["stage079_t1_equity"],
                    "trade_count": merged["c3_t1_trade_count"],
                    "slippage": merged["c3_t1_slippage"],
                }
            ),
            pd.DataFrame(
                {
                    "date": merged["date"],
                    "variant": STAGE103_VARIANT,
                    "label": "Stage103 same-day close",
                    "equity": merged["stage103_same_equity"],
                    "trade_count": merged["stage103_same_trade_count"],
                    "slippage": merged["stage103_same_slippage"],
                }
            ),
            pd.DataFrame(
                {
                    "date": merged["date"],
                    "variant": STAGE103_T1_VARIANT,
                    "label": "Stage103 C3 T+1 + frozen xsmom",
                    "equity": merged["stage103_t1_equity"],
                    "trade_count": merged["c3_t1_trade_count"] + merged["stage103_same_trade_count"] - merged["c3_same_trade_count"],
                    "slippage": merged["c3_t1_slippage"] + merged["stage103_satellite_slippage"],
                }
            ),
        ],
        ignore_index=True,
    )
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["equity"] = pd.to_numeric(curves["equity"], errors="coerce").ffill()
    return curves.dropna(subset=["date", "equity"]).sort_values(["variant", "date"]), merged


def _hard_gate(summary: pd.DataFrame, score: pd.DataFrame) -> pd.DataFrame:
    baseline = summary[summary["variant"].eq(BASELINE_VARIANT)].iloc[0]
    score_one = score.drop_duplicates(["variant", "label"])[
        ["variant", "label", "score_90d", "score_180d", "short_holding_score"]
    ]
    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        checks = {
            "total_return_not_lower_than_stage079_same": _safe_float(row["total_return_pct"]) >= _safe_float(baseline["total_return_pct"]) - 1e-4,
            "max_dd_not_worse_than_stage079_same": _safe_float(row["max_dd_pct"]) >= _safe_float(baseline["max_dd_pct"]) - 1e-4,
            "max_dd_below_30": _safe_float(row["max_dd_pct"]) >= -30.0,
            "sharpe_not_lower_than_stage079_same": _safe_float(row["sharpe"]) >= _safe_float(baseline["sharpe"]) - 1e-4,
            "ulcer_not_higher_than_stage079_same": _safe_float(row["ulcer_pct"]) <= _safe_float(baseline["ulcer_pct"]) + 1e-4,
            "rolling252_dd30_zero": _safe_float(row["rolling252_dd30_breach_rate"]) == 0.0,
            "rolling504_dd30_zero": _safe_float(row["rolling504_dd30_breach_rate"]) == 0.0,
            "annual_dd30_pass_100": _safe_float(row["annual_cold_start_dd30_pass_rate"]) == 1.0,
            "quarter_dd30_pass_100": _safe_float(row["quarter_cold_start_dd30_pass_rate"]) == 1.0,
        }
        rows.append(
            {
                "variant": row["variant"],
                "label": row["label"],
                **{name: int(flag) for name, flag in checks.items()},
                "hard_pass_vs_stage079_same": int(all(checks.values())),
                "failed_checks": ",".join(name for name, flag in checks.items() if not flag),
            }
        )
    return pd.DataFrame(rows).merge(score_one, on=["variant", "label"], how="left")


def _write_report(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    score: pd.DataFrame,
    gate: pd.DataFrame,
    delta: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    worst_delta = delta.nsmallest(15, "c3_t1_minus_same_net_pnl")[
        ["date", "c3_same_net_pnl", "c3_t1_net_pnl", "c3_t1_minus_same_net_pnl", "stage079_t1_minus_same_equity", "stage103_t1_minus_same_equity"]
    ]
    report = [
        "# Stage141 执行时序 / T+1开盘缺口审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：只读执行风险审计；不新增交易规则，不调参数，不改变 Stage079/Stage103。",
        "- 审计口径：C3 主体用真实引擎重跑 T+1 next open；Stage103 的 xsmom 腿保持 Stage403 冻结日度路径，用于隔离 C3 执行时序风险。",
        "",
        "## 决策",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 核心指标",
        "",
        _md_table(summary[["variant", "total_return_pct", "max_dd_pct", "sharpe", "ulcer_pct", "rolling252_dd30_breach_rate", "rolling504_dd30_breach_rate", "annual_cold_start_dd30_pass_rate", "quarter_cold_start_dd30_pass_rate"]]),
        "",
        "## 3个月/6个月体验",
        "",
        _md_table(horizon[["variant", "horizon_days", "return_p05_pct", "return_median_pct", "positive_return_rate", "annualized_below_5pct_rate", "max_dd_worst_pct", "dd20_breach_rate", "dd30_breach_rate", "ulcer_p95_pct", "longest_underwater_p95_days"]]),
        "",
        "## 体验评分",
        "",
        _md_table(score[["variant", "horizon_days", "experience_score", "score_90d", "score_180d", "short_holding_score"]]),
        "",
        "## 硬约束对照",
        "",
        _md_table(gate[["variant", "hard_pass_vs_stage079_same", "score_90d", "score_180d", "short_holding_score", "failed_checks"]]),
        "",
        "## 最差T+1相对同日成交日",
        "",
        _md_table(worst_delta, max_rows=15),
        "",
        "## 反过拟合说明",
        "",
        "- 本阶段不是新策略，只是执行模型压力测试。",
        "- 没有选择日期、品种、窗口或小数阈值；如果后续按这些缺口日做过滤，才会转为过拟合风险。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage403 = _load_stage403_full()
    c3_t1 = _run_c3_t1()
    curves, delta = _build_audit_curves(stage403, c3_t1)

    candidates: list[Any] = []
    for variant, frame in curves.groupby("variant", sort=False):
        label = str(frame["label"].iloc[0])
        equity = pd.Series(frame["equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
        note = "execution timing audit; not a promotion candidate"
        candidates.append(_candidate(variant, label, equity, note))

    summary = pd.DataFrame([s087._stats(candidate) for candidate in candidates])
    horizon = pd.DataFrame([s087._horizon_metrics(candidate, days) for candidate in candidates for days in (90, 180)])
    score = s087._score_horizons(horizon)
    gate = _hard_gate(summary, score)

    stage103_t1 = summary[summary["variant"].eq(STAGE103_T1_VARIANT)].iloc[0]
    stage079_same = summary[summary["variant"].eq(BASELINE_VARIANT)].iloc[0]
    stage079_t1 = summary[summary["variant"].eq(STAGE079_T1_VARIANT)].iloc[0]
    stage103_same = summary[summary["variant"].eq(STAGE103_VARIANT)].iloc[0]
    gate_stage103_t1 = gate[gate["variant"].eq(STAGE103_T1_VARIANT)].iloc[0]
    t1_delta = {
        "stage079_t1_return_delta_pp_vs_same": _safe_float(stage079_t1["total_return_pct"]) - _safe_float(stage079_same["total_return_pct"]),
        "stage079_t1_max_dd_delta_pp_vs_same": _safe_float(stage079_t1["max_dd_pct"]) - _safe_float(stage079_same["max_dd_pct"]),
        "stage103_t1_return_delta_pp_vs_same": _safe_float(stage103_t1["total_return_pct"]) - _safe_float(stage103_same["total_return_pct"]),
        "stage103_t1_max_dd_delta_pp_vs_same": _safe_float(stage103_t1["max_dd_pct"]) - _safe_float(stage103_same["max_dd_pct"]),
    }
    decision = {
        "stage": "Stage141",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "stage103_survives_c3_t1_open_audit"
        if int(gate_stage103_t1["hard_pass_vs_stage079_same"]) == 1
        else "stage103_needs_execution_timing_review",
        "audit_scope": "exact C3 T+1 next-open engine; Stage103 xsmom leg frozen from Stage403 daily path",
        "stage103_t1_hard_pass_vs_stage079_same": int(gate_stage103_t1["hard_pass_vs_stage079_same"]),
        "stage103_t1_failed_checks": str(gate_stage103_t1["failed_checks"]),
        "stage103_t1_total_return_pct": _safe_float(stage103_t1["total_return_pct"]),
        "stage103_t1_max_dd_pct": _safe_float(stage103_t1["max_dd_pct"]),
        "stage103_t1_sharpe": _safe_float(stage103_t1["sharpe"]),
        "stage103_t1_ulcer_pct": _safe_float(stage103_t1["ulcer_pct"]),
        "t1_delta": t1_delta,
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "horizon": str(HORIZON_PATH),
            "score": str(SCORE_PATH),
            "delta": str(DELTA_PATH),
            "c3_t1_daily": str(C3_T1_DAILY_PATH),
            "report": str(REPORT_PATH),
        },
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    delta.to_csv(DELTA_PATH, index=False, encoding="utf-8-sig")
    c3_t1.to_csv(C3_T1_DAILY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, horizon, score, gate, delta, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
