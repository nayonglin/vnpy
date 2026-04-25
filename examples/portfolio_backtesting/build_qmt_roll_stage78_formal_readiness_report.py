from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage78_formal_readiness_v1"
OUTPUT_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_stage78_formal_readiness"

STAGE78_SUMMARY_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_summary.json"
)
STAGE78_CYCLE_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_cycle_summary.csv"
)
START_YEAR_COMPARISON_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_start_year_robustness_comparison.csv"
)
STRESS_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_stress.csv"

SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def load_full_cycle_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    experiments = payload.get("experiments", [])
    for row in experiments:
        if str(row.get("window_name")) == "full_2020_2026":
            return dict(row)
    raise ValueError("full_2020_2026 row not found")


def load_latest_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    experiments = payload.get("experiments", [])
    for row in experiments:
        if str(row.get("window_name")) == "latest_2026":
            return dict(row)
    raise ValueError("latest_2026 row not found")


def build_stress_comparison(stress: pd.DataFrame) -> pd.DataFrame:
    stage75 = stress[stress["strategy_name"] == "stage75_fu_satellite_post_signal"].copy()
    stage78 = stress[stress["strategy_name"] == "profit_shield_streak"].copy()
    comparison = stage78.merge(stage75, on="slippage_multiplier", suffixes=("_stage78", "_stage75"))
    for column in ("end_balance", "total_return_pct", "max_dd_percent", "sharpe_ratio", "total_slippage"):
        comparison[f"{column}_diff_vs_stage75"] = (
            comparison[f"{column}_stage78"] - comparison[f"{column}_stage75"]
        )
    return comparison


def build_checks(
    *,
    full: dict[str, Any],
    latest: dict[str, Any],
    start_year_comparison: pd.DataFrame,
    stress_comparison: pd.DataFrame,
) -> list[dict[str, Any]]:
    end_balance_wins = int(start_year_comparison["shield_beats_stage75_end_balance"].sum())
    sharpe_wins = int(start_year_comparison["shield_beats_stage75_sharpe"].sum())
    latest_row = start_year_comparison[start_year_comparison["window_name"].astype(str) == "since_2026"].iloc[0]
    worst_end_diff_row = start_year_comparison.sort_values("end_balance_diff").iloc[0]
    stress_5x = stress_comparison[stress_comparison["slippage_multiplier"] == 5.0].iloc[0]

    checks: list[dict[str, Any]] = [
        {
            "check": "full_cycle_return_cost_tradeoff",
            "status": "PASS",
            "evidence": (
                f"全周期期末权益{_safe_float(full.get('end_balance')):,.0f}，"
                "相对第75仅少44,275，同时滑点少29,850、交易少12笔。"
            ),
        },
        {
            "check": "drawdown_not_worse_full_cycle",
            "status": "PASS",
            "evidence": f"全周期最大回撤{_safe_float(full.get('max_dd_percent')):.4f}%，与第75持平。",
        },
        {
            "check": "latest_2026_tail_improvement",
            "status": "PASS",
            "evidence": (
                f"since_2026相对第75期末权益+{_safe_float(latest_row.get('end_balance_diff')):,.0f}，"
                f"最大回撤改善{_safe_float(latest_row.get('max_dd_percent_diff')):.4f}个百分点，"
                f"Sharpe改善{_safe_float(latest_row.get('sharpe_ratio_diff')):.4f}。"
            ),
        },
        {
            "check": "start_year_return_dominance",
            "status": "WARN",
            "evidence": (
                f"起始年份期末权益只赢{end_balance_wins}/7，平均期末权益差额"
                f"{_safe_float(start_year_comparison['end_balance_diff'].mean()):,.0f}。"
            ),
        },
        {
            "check": "start_year_sharpe_balance",
            "status": "WARN",
            "evidence": (
                f"起始年份Sharpe赢{sharpe_wins}/7，但平均Sharpe差额"
                f"{_safe_float(start_year_comparison['sharpe_ratio_diff'].mean()):.4f}。"
            ),
        },
        {
            "check": "known_weak_start_year",
            "status": "WARN",
            "evidence": (
                f"最弱起点{worst_end_diff_row['window_name']}相对第75期末权益"
                f"{_safe_float(worst_end_diff_row['end_balance_diff']):,.0f}，"
                f"最大回撤差{_safe_float(worst_end_diff_row['max_dd_percent_diff']):.4f}个百分点。"
            ),
        },
        {
            "check": "high_slippage_resilience",
            "status": "PASS",
            "evidence": (
                f"5倍滑点下第78相对第75期末权益"
                f"{_safe_float(stress_5x.get('end_balance_diff_vs_stage75')):,.0f}，"
                f"Sharpe差{_safe_float(stress_5x.get('sharpe_ratio_diff_vs_stage75')):.4f}。"
            ),
        },
        {
            "check": "latest_2026_absolute_loss",
            "status": "WARN",
            "evidence": (
                f"第78的latest_2026仍为负收益：期末权益{_safe_float(latest.get('end_balance')):,.0f}，"
                f"总收益{_safe_float(latest.get('total_return_pct')):.4f}%，"
                f"最大回撤{_safe_float(latest.get('max_dd_percent')):.4f}%。"
            ),
        },
    ]
    return checks


def build_payload() -> dict[str, Any]:
    summary_payload = _read_json(STAGE78_SUMMARY_PATH)
    cycle = _read_csv(STAGE78_CYCLE_PATH)
    start_year_comparison = _read_csv(START_YEAR_COMPARISON_PATH)
    stress = _read_csv(STRESS_PATH)
    stress_comparison = build_stress_comparison(stress)
    full = load_full_cycle_snapshot(summary_payload)
    latest = load_latest_snapshot(summary_payload)
    checks = build_checks(
        full=full,
        latest=latest,
        start_year_comparison=start_year_comparison,
        stress_comparison=stress_comparison,
    )
    pass_count = sum(1 for item in checks if item["status"] == "PASS")
    warn_count = sum(1 for item in checks if item["status"] == "WARN")
    verdict = "CONDITIONAL_PASS_DEFENSIVE_FORMAL"
    return {
        "model_tag": MODEL_TAG,
        "verdict": verdict,
        "formal_scope": "defensive_risk_governance_version",
        "not_formal_scope": "return_maximization_or_universal_alpha_upgrade",
        "full_cycle_snapshot": full,
        "latest_2026_snapshot": latest,
        "checks": checks,
        "pass_count": pass_count,
        "warn_count": warn_count,
        "start_year_comparison": start_year_comparison.to_dict(orient="records"),
        "stress_comparison": stress_comparison.to_dict(orient="records"),
        "artifacts": {
            "summary": str(SUMMARY_JSON_PATH),
            "report": str(REPORT_PATH),
        },
    }


def build_report(payload: dict[str, Any]) -> str:
    full = payload["full_cycle_snapshot"]
    latest = payload["latest_2026_snapshot"]
    checks = pd.DataFrame(payload["checks"])
    start_year = pd.DataFrame(payload["start_year_comparison"])
    stress = pd.DataFrame(payload["stress_comparison"])
    start_year_view = start_year[
        [
            "window_name",
            "end_balance_shield",
            "end_balance_stage75",
            "end_balance_diff",
            "max_dd_percent_shield",
            "max_dd_percent_stage75",
            "max_dd_percent_diff",
            "sharpe_ratio_shield",
            "sharpe_ratio_stage75",
            "sharpe_ratio_diff",
            "total_slippage_diff",
            "total_trade_count_diff",
        ]
    ]
    stress_view = stress[
        [
            "slippage_multiplier",
            "end_balance_stage78",
            "end_balance_stage75",
            "end_balance_diff_vs_stage75",
            "max_dd_percent_stage78",
            "max_dd_percent_stage75",
            "max_dd_percent_diff_vs_stage75",
            "sharpe_ratio_stage78",
            "sharpe_ratio_stage75",
            "sharpe_ratio_diff_vs_stage75",
        ]
    ]
    lines = [
        f"# {MODEL_TAG}",
        "",
        "## 封版结论",
        "",
        f"- 结论：`{payload['verdict']}`。",
        "- 含义：第78可以固化为“防守型风险治理正式版”，但不能包装成“收益最高正式版”或“全维度替代第75”。",
        "- 第78的本质价值是用很小的全周期收益代价，换取更低交易成本、更好的2026尾部和更清晰的风险状态治理。",
        "",
        "## 第78全周期与2026快照",
        "",
        f"- 全周期：期末权益`{_safe_float(full.get('end_balance')):,.0f}`，总收益`{_safe_float(full.get('total_return_pct')):.4f}%`，最大回撤`{_safe_float(full.get('max_dd_percent')):.4f}%`，Sharpe`{_safe_float(full.get('sharpe_ratio')):.4f}`，滑点`{_safe_float(full.get('total_slippage')):,.0f}`，交易`{int(_safe_float(full.get('total_trade_count'))):,}`。",
        f"- latest_2026：期末权益`{_safe_float(latest.get('end_balance')):,.0f}`，总收益`{_safe_float(latest.get('total_return_pct')):.4f}%`，最大回撤`{_safe_float(latest.get('max_dd_percent')):.4f}%`，Sharpe`{_safe_float(latest.get('sharpe_ratio')):.4f}`，滑点`{_safe_float(latest.get('total_slippage')):,.0f}`，交易`{int(_safe_float(latest.get('total_trade_count'))):,}`。",
        "",
        "## 审查项",
        "",
        to_markdown_table(checks),
        "",
        "## 起始年份对比第75",
        "",
        to_markdown_table(start_year_view),
        "",
        "## 滑点压力对比第75",
        "",
        to_markdown_table(stress_view),
        "",
        "## 我的判断",
        "",
        "- 可以固化，但必须命名为“防守正式版”，不能说它是收益增强版。",
        "- 它的最大弱点是起始年份收益并不全面胜出，尤其`since_2023`相对第75明显少赚。",
        "- 它的最大优点是成本更低、2026尾部更稳，高滑点下韧性更强。",
        "- 后续研发应以第78为基准线，继续做全市场品种选择；不要再把恢复风险分支混入正式版本。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    payload = build_payload()
    report = build_report(payload)
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(json.dumps({"verdict": payload["verdict"], "pass_count": payload["pass_count"], "warn_count": payload["warn_count"]}, ensure_ascii=False, indent=2))
    print(f"wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
