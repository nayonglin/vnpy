from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

READINESS_SUMMARY_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_selection_pairwise_long015_volref30_corr_crowding_readiness_summary.json"
)
ROBUSTNESS_SUMMARY_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_selection_pairwise_long015_volref30_corr_crowding_robustness_summary.json"
)
MONITOR_SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_long015_volref30_corr_crowding_monitor_summary.json"

OUTPUT_PREFIX: str = "qmt_roll_selection_pairwise_long015_volref30_corr_crowding_risk_governance"

SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary.json"
REPORT_MD_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report.md"
CAPITAL_SCENARIOS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_capital_scenarios.csv"
GOVERNANCE_RULES_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rules.csv"

CAPITAL_SCENARIOS: tuple[float, ...] = (200_000.0, 500_000.0, 1_000_000.0, 2_000_000.0)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def percent_loss(capital: float, dd_percent: float) -> float:
    return capital * abs(dd_percent) / 100.0


def to_markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_无记录_"
    compact = df.copy()
    for column in compact.columns:
        if pd.api.types.is_float_dtype(compact[column]):
            compact[column] = compact[column].map(lambda value: f"{float(value):.2f}")
    headers = [str(column) for column in compact.columns]
    rows = compact.astype(str).to_numpy().tolist()
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def build_capital_scenarios(
    formal_dd: float,
    bootstrap_median_dd: float,
    bootstrap_p05_dd: float,
    slippage_5x_dd: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for capital in CAPITAL_SCENARIOS:
        rows.append(
            {
                "strategy_capital": capital,
                "formal_dd_percent": formal_dd,
                "formal_dd_loss": percent_loss(capital, formal_dd),
                "bootstrap_median_dd_percent": bootstrap_median_dd,
                "bootstrap_median_dd_loss": percent_loss(capital, bootstrap_median_dd),
                "slippage_5x_dd_percent": slippage_5x_dd,
                "slippage_5x_dd_loss": percent_loss(capital, slippage_5x_dd),
                "bootstrap_p05_dd_percent": bootstrap_p05_dd,
                "bootstrap_p05_dd_loss": percent_loss(capital, bootstrap_p05_dd),
            }
        )
    return pd.DataFrame(rows)


def build_governance_rules() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "level": "green",
                "trigger": "实时/准实盘回撤 < 30%",
                "action": "正常观察，不调参数",
                "rationale": "低于正式最大回撤区间，仍属普通波动",
            },
            {
                "level": "yellow_review",
                "trigger": "回撤 >= 35% 或 severe_watch 在20个交易日内出现>=2次",
                "action": "人工复盘；禁止新增参数优化",
                "rationale": "接近正式最大回撤，或出现趋势扩散误伤风险",
            },
            {
                "level": "orange_degrade",
                "trigger": "回撤 >= 45% 或 block bootstrap 中位回撤区间被突破",
                "action": "降低资金/暂停扩大规模；只允许继续记录",
                "rationale": "超过正式回撤并进入 bootstrap 常见深回撤区间",
            },
            {
                "level": "red_pause",
                "trigger": "回撤 >= 55% 或 实际滑点压力接近5x情景",
                "action": "暂停新资金；复核成交、滑点、品种映射和信号漂移",
                "rationale": "接近5x滑点压力下的最大回撤，不应继续裸跑",
            },
            {
                "level": "black_research_reset",
                "trigger": "回撤 >= 65% 或 20日severe_watch跟踪连续显著为负",
                "action": "停止准实盘；回到研究模式，禁止用同一参数继续解释",
                "rationale": "进入 bootstrap 5% 尾部风险区，说明环境可能失配",
            },
        ]
    )


def build_report(
    readiness: dict[str, Any],
    formal_dd: float,
    bootstrap_median_dd: float,
    bootstrap_p05_dd: float,
    slippage_5x_dd: float,
    monitor: dict[str, Any],
    capital_scenarios: pd.DataFrame,
    governance_rules: pd.DataFrame,
) -> str:
    lines = [
        "# QMT Roll 风险治理报告",
        "",
        "## 定位",
        "",
        "- 本报告用于准实盘/纸面跟踪的风险治理。",
        "- 它不是收益优化器，也不是自动交易开关。",
        "- 当前候选仍处于 `paper_trading_review` 阶段，不是无人值守实盘版本。",
        "",
        "## 当前候选",
        "",
        f"- 候选：`{readiness['candidate_name']}`",
        f"- 状态：`{readiness['readiness_status']}`",
        "",
        "## 核心风险刻度",
        "",
        f"- 正式最大回撤：`{formal_dd:.2f}%`",
        f"- Bootstrap 中位回撤代表值：`{bootstrap_median_dd:.2f}%`",
        f"- Bootstrap 5% 尾部回撤代表值：`{bootstrap_p05_dd:.2f}%`",
        f"- 5x 滑点压力最大回撤：`{slippage_5x_dd:.2f}%`",
        f"- severe_watch 20日胜率：`{float(monitor['severe_watch_hit_rate_fwd20']):.2%}`",
        "",
        "## 资金情景",
        "",
        to_markdown_table(capital_scenarios),
        "",
        "## 降级/暂停规则",
        "",
        to_markdown_table(governance_rules),
        "",
        "## 使用原则",
        "",
        "- 触发规则后先降风险和复盘，不允许现场调参数。",
        "- `severe_watch` 只用于复盘优先级，不用于自动关停。",
        "- 回撤超过规则线时，先检查数据、成交、滑点、换月映射，再讨论策略逻辑。",
        "- 若进入 `black_research_reset`，必须重新做正式回测和 back_log 记录。",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    readiness = load_json(READINESS_SUMMARY_PATH)
    robustness = load_json(ROBUSTNESS_SUMMARY_PATH)
    monitor = load_json(MONITOR_SUMMARY_PATH)

    formal_dd = float(readiness["candidate_metrics"]["max_dd_percent"])
    bootstrap_median_dd = min(float(row["max_dd_median"]) for row in robustness["candidate_block_bootstrap_summary"])
    bootstrap_p05_dd = min(float(row["max_dd_p05"]) for row in robustness["candidate_block_bootstrap_summary"])
    slippage_5x = next(row for row in robustness["slippage_stress"] if float(row["slippage_multiplier"]) == 5.0)
    slippage_5x_dd = float(slippage_5x["max_dd_percent"])

    capital_scenarios = build_capital_scenarios(
        formal_dd=formal_dd,
        bootstrap_median_dd=bootstrap_median_dd,
        bootstrap_p05_dd=bootstrap_p05_dd,
        slippage_5x_dd=slippage_5x_dd,
    )
    governance_rules = build_governance_rules()

    capital_scenarios.to_csv(CAPITAL_SCENARIOS_CSV_PATH, index=False, encoding="utf-8-sig")
    governance_rules.to_csv(GOVERNANCE_RULES_CSV_PATH, index=False, encoding="utf-8-sig")
    REPORT_MD_PATH.write_text(
        build_report(
            readiness=readiness,
            formal_dd=formal_dd,
            bootstrap_median_dd=bootstrap_median_dd,
            bootstrap_p05_dd=bootstrap_p05_dd,
            slippage_5x_dd=slippage_5x_dd,
            monitor=monitor,
            capital_scenarios=capital_scenarios,
            governance_rules=governance_rules,
        ),
        encoding="utf-8",
    )

    payload: dict[str, Any] = {
        "analysis": OUTPUT_PREFIX,
        "candidate_name": readiness["candidate_name"],
        "readiness_status": readiness["readiness_status"],
        "formal_dd_percent": formal_dd,
        "bootstrap_median_dd_percent": bootstrap_median_dd,
        "bootstrap_p05_dd_percent": bootstrap_p05_dd,
        "slippage_5x_dd_percent": slippage_5x_dd,
        "severe_watch_hit_rate_fwd20": float(monitor["severe_watch_hit_rate_fwd20"]),
        "risk_levels": governance_rules.to_dict(orient="records"),
        "capital_scenarios": capital_scenarios.to_dict(orient="records"),
        "artifacts": {
            "summary_json": str(SUMMARY_JSON_PATH),
            "report_md": str(REPORT_MD_PATH),
            "capital_scenarios_csv": str(CAPITAL_SCENARIOS_CSV_PATH),
            "governance_rules_csv": str(GOVERNANCE_RULES_CSV_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print(f"risk governance report md: {REPORT_MD_PATH}")
    print(f"risk governance summary json: {SUMMARY_JSON_PATH}")
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    print("\n[capital scenarios]")
    print(capital_scenarios.to_string(index=False))
    print("\n[governance rules]")
    print(governance_rules.to_string(index=False))


if __name__ == "__main__":
    main()
