from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
    CYCLE_WINDOWS,
    FU_PRODUCT,
    to_markdown_table,
)
from run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_backtest import (
    build_strategy_overrides as build_profit_shield_strategy_overrides,
)
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

EXPERIMENT_TAG: str = "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery"
FORMAL_PREFIX: str = f"{EXPERIMENT_TAG}_formal"
EXPERIMENT_NAME: str = "ai_top8_plus_fu_satellite_post_signal_profit_shield_entry_structure_rsi_recovery"

ENTRY_STRUCTURE_RECOVERY_SIGNALS: str = "long_case1a,short_case1a"
ENTRY_STRUCTURE_RECOVERY_MIN_MULTIPLIER: float = 1.0
ENTRY_STRUCTURE_RECOVERY_REQUIRE_FLAT_PORTFOLIO: bool = True
ENTRY_STRUCTURE_RECOVERY_MAX_SAME_DIRECTION_CORR: float = 0.30
ENTRY_STRUCTURE_RECOVERY_REQUIRE_RSI_CONFIRMATION: bool = True
ENTRY_STRUCTURE_RECOVERY_LONG_MIN_RSI: float = 60.0
ENTRY_STRUCTURE_RECOVERY_SHORT_MAX_RSI: float = 40.0
CAPITAL: float = 200_000.0

SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_cycle_summary.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_report.md"


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_strategy_overrides() -> tuple[dict[str, Any], Path, Path]:
    strategy_overrides, universe_path, eligibility_path = build_profit_shield_strategy_overrides()
    strategy_overrides = {
        **strategy_overrides,
        "enable_streak_entry_structure_risk_recovery": True,
        "streak_entry_structure_recovery_signals": ENTRY_STRUCTURE_RECOVERY_SIGNALS,
        "streak_entry_structure_recovery_min_multiplier": ENTRY_STRUCTURE_RECOVERY_MIN_MULTIPLIER,
        "streak_entry_structure_recovery_require_flat_portfolio": ENTRY_STRUCTURE_RECOVERY_REQUIRE_FLAT_PORTFOLIO,
        "streak_entry_structure_recovery_max_same_direction_corr": ENTRY_STRUCTURE_RECOVERY_MAX_SAME_DIRECTION_CORR,
        "streak_entry_structure_recovery_require_rsi_confirmation": ENTRY_STRUCTURE_RECOVERY_REQUIRE_RSI_CONFIRMATION,
        "streak_entry_structure_recovery_long_min_rsi": ENTRY_STRUCTURE_RECOVERY_LONG_MIN_RSI,
        "streak_entry_structure_recovery_short_max_rsi": ENTRY_STRUCTURE_RECOVERY_SHORT_MAX_RSI,
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
            f"[fu-satellite-profit-shield-entry-structure-rsi-recovery] {window_name}: "
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
            chart_title="QMT Roll AI Top8 + Fu Satellite Profit Shield Entry Structure RSI Recovery"
            if save_artifacts
            else None,
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
                streak_risk_state_excluded_products=FU_PRODUCT,
                streak_risk_state_exclusion_mode="profit_only",
                enable_streak_entry_structure_risk_recovery=True,
                streak_entry_structure_recovery_signals=ENTRY_STRUCTURE_RECOVERY_SIGNALS,
                streak_entry_structure_recovery_min_multiplier=ENTRY_STRUCTURE_RECOVERY_MIN_MULTIPLIER,
                streak_entry_structure_recovery_require_flat_portfolio=ENTRY_STRUCTURE_RECOVERY_REQUIRE_FLAT_PORTFOLIO,
                streak_entry_structure_recovery_max_same_direction_corr=ENTRY_STRUCTURE_RECOVERY_MAX_SAME_DIRECTION_CORR,
                streak_entry_structure_recovery_require_rsi_confirmation=ENTRY_STRUCTURE_RECOVERY_REQUIRE_RSI_CONFIRMATION,
                streak_entry_structure_recovery_long_min_rsi=ENTRY_STRUCTURE_RECOVERY_LONG_MIN_RSI,
                streak_entry_structure_recovery_short_max_rsi=ENTRY_STRUCTURE_RECOVERY_SHORT_MAX_RSI,
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
        "stage78_profit_shield": {
            "end_balance": 4_600_090,
            "total_return_pct": 2200.0450,
            "max_dd_percent": -36.990703,
            "sharpe_ratio": 1.2919,
            "total_slippage": 260_110,
            "total_trade_count": 779,
        },
        "stage84_entry_structure_recovery": {
            "end_balance": 4_585_520,
            "total_return_pct": 2192.7600,
            "max_dd_percent": -39.2924,
            "sharpe_ratio": 1.1193,
            "total_slippage": 289_290,
            "total_trade_count": 771,
        },
    }
    payload: dict[str, Any] = {
        "experiment_tag": EXPERIMENT_TAG,
        "experiment_name": EXPERIMENT_NAME,
        "base_risk_ratio": BASE_RISK_RATIO,
        "streak_risk_state_excluded_products": FU_PRODUCT,
        "streak_risk_state_exclusion_mode": "profit_only",
        "enable_streak_entry_structure_risk_recovery": True,
        "streak_entry_structure_recovery_signals": ENTRY_STRUCTURE_RECOVERY_SIGNALS,
        "streak_entry_structure_recovery_min_multiplier": ENTRY_STRUCTURE_RECOVERY_MIN_MULTIPLIER,
        "streak_entry_structure_recovery_require_flat_portfolio": ENTRY_STRUCTURE_RECOVERY_REQUIRE_FLAT_PORTFOLIO,
        "streak_entry_structure_recovery_max_same_direction_corr": ENTRY_STRUCTURE_RECOVERY_MAX_SAME_DIRECTION_CORR,
        "streak_entry_structure_recovery_require_rsi_confirmation": ENTRY_STRUCTURE_RECOVERY_REQUIRE_RSI_CONFIRMATION,
        "streak_entry_structure_recovery_long_min_rsi": ENTRY_STRUCTURE_RECOVERY_LONG_MIN_RSI,
        "streak_entry_structure_recovery_short_max_rsi": ENTRY_STRUCTURE_RECOVERY_SHORT_MAX_RSI,
        "experiments": summary.to_dict(orient="records"),
        "references": references,
        "artifacts": {
            "summary_csv": str(SUMMARY_CSV_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
            "report": str(REPORT_PATH),
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
    stage75 = payload.get("comparison_vs_stage75_fu_satellite_post_signal", {})
    stage78 = payload.get("comparison_vs_stage78_profit_shield", {})
    stage84 = payload.get("comparison_vs_stage84_entry_structure_recovery", {})

    lines: list[str] = [
        "# AI Top8 + fu卫星：盈利屏蔽 + 入场结构RSI确认恢复",
        "",
        "## 设计",
        "",
        "- 延续第78阶段：`fu.SHFE`盈利不恢复组合连亏风险。",
        "- 延续第84阶段的入场结构条件：早期交叉、组合无持仓、无同向相关拥挤时，允许本笔入场风险乘数临时恢复到至少`1.0`。",
        "- 新增RSI方向延续确认：多头要求`RSI >= 60`，空头要求`RSI <= 40`；该条件用于过滤早期交叉里的弱动量假启动。",
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
        "",
        "## 对比",
        "",
        f"- 相比第75阶段收益基准：期末权益差额`{_safe_float(stage75.get('end_balance_diff')):,.0f}`，Sharpe差额`{_safe_float(stage75.get('sharpe_ratio_diff')):.4f}`，滑点差额`{_safe_float(stage75.get('total_slippage_diff')):,.0f}`。",
        f"- 相比第78阶段风险治理候选：期末权益差额`{_safe_float(stage78.get('end_balance_diff')):,.0f}`，Sharpe差额`{_safe_float(stage78.get('sharpe_ratio_diff')):.4f}`，滑点差额`{_safe_float(stage78.get('total_slippage_diff')):,.0f}`。",
        f"- 相比第84阶段无RSI确认恢复：期末权益差额`{_safe_float(stage84.get('end_balance_diff')):,.0f}`，Sharpe差额`{_safe_float(stage84.get('sharpe_ratio_diff')):.4f}`，最大回撤差额`{_safe_float(stage84.get('max_dd_percent_diff')):.4f}`。",
        "",
        "## 判断",
        "",
        "- 这个版本验证的是第85阶段归因里的RSI方向延续线索是否能在完整组合回测里成立。",
        "- 若完整回测仍弱于第78阶段，说明事件级归因存在路径重叠或长尾回吐，不能升级。",
        "- 若它能改善第84的回撤与Sharpe，同时不牺牲第78的尾部保护，再进入起始年份和滑点压力反证。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = run_cycle_backtests()
    payload = build_payload(summary)
    report = build_report(summary, payload)

    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(report, encoding="utf-8")

    print(f"[fu-satellite-profit-shield-entry-structure-rsi-recovery] summary csv: {SUMMARY_CSV_PATH}")
    print(f"[fu-satellite-profit-shield-entry-structure-rsi-recovery] summary json: {SUMMARY_JSON_PATH}")
    print(f"[fu-satellite-profit-shield-entry-structure-rsi-recovery] report: {REPORT_PATH}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
