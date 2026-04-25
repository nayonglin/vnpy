from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
    CYCLE_WINDOWS,
    build_ai_satellite_post_signal_eligibility,
    build_static18_plus_fu_universe,
    to_markdown_table,
)
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (
    BASE_RISK_RATIO,
    CORR20_06_08_FLOOR35_OVERRIDES,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

EXPERIMENT_TAG: str = "qmt_roll_selection_long015_volref30_corr_fu_satellite_confirmed_streak"
FORMAL_PREFIX: str = f"{EXPERIMENT_TAG}_formal"
EXPERIMENT_NAME: str = "ai_top8_plus_fu_satellite_post_signal_confirmed_streak"
RECOVERY_MODE: str = "confirm"
CONFIRM_WINS: int = 2

SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_cycle_summary.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_report.md"

CAPITAL: float = 200_000.0


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_strategy_overrides() -> tuple[dict[str, Any], Path, Path]:
    universe_path = build_static18_plus_fu_universe()
    eligibility_path = build_ai_satellite_post_signal_eligibility()
    strategy_overrides: dict[str, Any] = {
        **CORR20_06_08_FLOOR35_OVERRIDES,
        "product_universe_csv_path": str(universe_path),
        "enable_ai_product_pool_filter": True,
        "ai_product_pool_eligibility_path": str(eligibility_path),
        "ai_product_pool_strategy": AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
        "streak_profit_recovery_mode": RECOVERY_MODE,
        "streak_profit_recovery_confirm_wins": CONFIRM_WINS,
    }
    return strategy_overrides, universe_path, eligibility_path


def run_cycle_backtests() -> pd.DataFrame:
    strategy_overrides, universe_path, eligibility_path = build_strategy_overrides()
    rows: list[dict[str, Any]] = []

    for window in CYCLE_WINDOWS:
        window_name = str(window["window_name"])
        analysis_start = window["analysis_start"]
        analysis_end = window["analysis_end"]
        save_artifacts = window_name == "full_2020_2026"
        print(
            f"[fu-satellite-confirmed-streak] {window_name}: "
            f"{analysis_start.date()} -> {analysis_end.date()}"
        )
        _, _, statistics = run_backtest(
            risk_ratio=BASE_RISK_RATIO,
            strategy_overrides=strategy_overrides,
            analysis_start=analysis_start,
            analysis_end=analysis_end,
            capital=CAPITAL,
            save_artifacts=save_artifacts,
            include_start_year_sweep=False,
            file_prefix=FORMAL_PREFIX if save_artifacts else None,
            chart_title="QMT Roll AI Top8 + Fu Satellite Confirmed Streak" if save_artifacts else None,
        )
        rows.append(
            build_summary_row(
                statistics,
                analysis_start=analysis_start,
                analysis_end=analysis_end,
                experiment_name=EXPERIMENT_NAME,
                window_name=window_name,
                universe_path=str(universe_path),
                ai_product_pool_eligibility_path=str(eligibility_path),
                ai_product_pool_strategy=AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
                streak_profit_recovery_mode=RECOVERY_MODE,
                streak_profit_recovery_confirm_wins=CONFIRM_WINS,
                strategy_overrides_json=json.dumps(strategy_overrides, ensure_ascii=False, sort_keys=True),
                total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                total_slippage=float(statistics.get("total_slippage", 0) or 0),
                total_commission=float(statistics.get("total_commission", 0) or 0),
                profit_days=int(statistics.get("profit_days", 0) or 0),
                loss_days=int(statistics.get("loss_days", 0) or 0),
            )
        )

    return pd.DataFrame(rows)


def build_payload(summary: pd.DataFrame) -> dict[str, Any]:
    references = {
        "stage75_fu_satellite_post_signal": {
            "end_balance": 4_644_365,
            "total_return_pct": 2222.1825,
            "max_dd_percent": -36.990703,
            "sharpe_ratio": 1.2926,
            "total_slippage": 289_960,
            "total_trade_count": 791,
        },
        "stage68_71_ai_top8_product_pool": {
            "end_balance": 3_894_190,
            "total_return_pct": 1847.095,
            "max_dd_percent": -36.990703,
            "sharpe_ratio": 1.208030,
            "total_slippage": 257_880,
            "total_trade_count": 720,
        },
    }
    payload: dict[str, Any] = {
        "experiment_tag": EXPERIMENT_TAG,
        "experiment_name": EXPERIMENT_NAME,
        "base_risk_ratio": BASE_RISK_RATIO,
        "analysis_start": START_DT.date().isoformat(),
        "analysis_end": END_DT.date().isoformat(),
        "streak_profit_recovery_mode": RECOVERY_MODE,
        "streak_profit_recovery_confirm_wins": CONFIRM_WINS,
        "experiments": summary.to_dict(orient="records"),
        "references": references,
        "artifacts": {
            "summary_csv": str(SUMMARY_CSV_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
            "formal_file_prefix": FORMAL_PREFIX,
        },
    }
    full = summary[summary["window_name"].astype(str) == "full_2020_2026"]
    if not full.empty:
        row = full.iloc[0]
        for name, reference in references.items():
            payload[f"comparison_vs_{name}"] = {
                "end_balance_diff": float(row["end_balance"] - reference["end_balance"]),
                "total_return_pct_diff": float(row["total_return_pct"] - reference["total_return_pct"]),
                "max_dd_percent_diff": float(row["max_dd_percent"] - reference["max_dd_percent"]),
                "sharpe_ratio_diff": float(row["sharpe_ratio"] - reference["sharpe_ratio"]),
                "total_slippage_diff": float(row["total_slippage"] - reference["total_slippage"]),
                "total_trade_count_diff": int(row["total_trade_count"] - reference["total_trade_count"]),
            }
    return payload


def build_report(summary: pd.DataFrame, payload: dict[str, Any]) -> str:
    full = summary[summary["window_name"].astype(str) == "full_2020_2026"].copy()
    latest = summary[summary["window_name"].astype(str) == "latest_2026"].copy()
    stage75 = payload.get("comparison_vs_stage75_fu_satellite_post_signal", {})
    ai_top8 = payload.get("comparison_vs_stage68_71_ai_top8_product_pool", {})

    lines: list[str] = [
        "# AI Top8 + fu卫星：连续亏损状态确认恢复",
        "",
        "## 设计",
        "",
        f"- 新增参数验证：`streak_profit_recovery_mode={RECOVERY_MODE}`，`streak_profit_recovery_confirm_wins={CONFIRM_WINS}`",
        "- 含义：连续亏损后，盈利平仓需要连续确认2次才清零`loss_streak`。",
        "- 目标不是压低交易，而是避免单笔卫星盈利把组合从风险收缩状态直接拉回满风险。",
        "",
        "## 回测结果",
        "",
        to_markdown_table(
            summary[
                [
                    "window_name",
                    "end_balance",
                    "total_return_pct",
                    "max_dd_percent",
                    "sharpe_ratio",
                    "total_slippage",
                    "total_trade_count",
                ]
            ]
        ),
    ]
    if not full.empty:
        lines.extend(
            [
                "",
                "## 对比",
                "",
                f"- 相比第75阶段`fu`卫星正式候选：期末权益差额`{_safe_float(stage75.get('end_balance_diff')):,.0f}`，Sharpe差额`{_safe_float(stage75.get('sharpe_ratio_diff')):.4f}`，最大回撤差额`{_safe_float(stage75.get('max_dd_percent_diff')):.4f}`。",
                f"- 相比原18品种AI Top8：期末权益差额`{_safe_float(ai_top8.get('end_balance_diff')):,.0f}`，Sharpe差额`{_safe_float(ai_top8.get('sharpe_ratio_diff')):.4f}`，最大回撤差额`{_safe_float(ai_top8.get('max_dd_percent_diff')):.4f}`。",
            ]
        )
    if not latest.empty:
        row = latest.iloc[0]
        lines.extend(
            [
                "",
                "## 2026尾部",
                "",
                f"- `latest_2026`期末权益`{_safe_float(row['end_balance']):,.0f}`，总收益`{_safe_float(row['total_return_pct']):.2f}%`，最大回撤`{_safe_float(row['max_dd_percent']):.2f}%`，Sharpe`{_safe_float(row['sharpe_ratio']):.4f}`。",
            ]
        )
    lines.extend(
        [
            "",
            "## 判断",
            "",
            "- 该版本不升级正式候选：2026尾部改善明显，但全周期期末权益和Sharpe被大幅压低。",
            "- 结论是“全局确认恢复”仍然太保守，会让趋势系统错过长期主升段。",
            "- 后续应采用更聚焦的非对称治理：卫星盈利不能替核心池解除风险，但卫星亏损仍应计入风险。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = run_cycle_backtests()
    payload = build_payload(summary)
    report = build_report(summary, payload)

    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(report, encoding="utf-8")

    print(f"[fu-satellite-confirmed-streak] summary csv: {SUMMARY_CSV_PATH}")
    print(f"[fu-satellite-confirmed-streak] summary json: {SUMMARY_JSON_PATH}")
    print(f"[fu-satellite-confirmed-streak] report: {REPORT_PATH}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
