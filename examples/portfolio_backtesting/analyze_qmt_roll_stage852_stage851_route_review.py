from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage852"
MODEL_TAG = "stage852_stage851_route_review_v1"
OUTPUT_PREFIX = "qmt_roll_stage852_stage851_route_review"

STAGE825_PREFIX = "qmt_roll_stage825_stage819_intraday_rule_forensics"
STAGE825_TAG = "stage825_stage819_intraday_rule_forensics_v1"
STAGE849_PREFIX = "qmt_roll_stage849_stage848_pressure_path_forensics"
STAGE849_TAG = "stage849_stage848_pressure_path_forensics_v1"
STAGE851_PREFIX = "qmt_roll_stage851_stage850_pdeg_proxy_audit"
STAGE851_TAG = "stage851_stage850_pdeg_proxy_audit_v1"

STAGE825_INTRADAY_PATH = OUTPUT_DIR / f"{STAGE825_PREFIX}_intraday_features_{STAGE825_TAG}.csv"
STAGE825_COVERAGE_PATH = OUTPUT_DIR / f"{STAGE825_PREFIX}_minute_coverage_{STAGE825_TAG}.csv"
STAGE849_MINUTE_PATH = OUTPUT_DIR / f"{STAGE849_PREFIX}_minute_features_{STAGE849_TAG}.csv"
STAGE849_PAIRS_PATH = OUTPUT_DIR / f"{STAGE849_PREFIX}_episode_lot_pairs_{STAGE849_TAG}.csv"
STAGE851_DECISION_PATH = OUTPUT_DIR / f"{STAGE851_PREFIX}_decision_{STAGE851_TAG}.json"

COVERAGE_BY_YEAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_by_year_{MODEL_TAG}.csv"
COVERAGE_BY_PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_by_product_{MODEL_TAG}.csv"
PRESSURE_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pressure_episode_coverage_{MODEL_TAG}.csv"
ROUTE_SCOREBOARD_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_scoreboard_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_gap_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _prepare_intraday() -> pd.DataFrame:
    data = _load_csv(STAGE825_INTRADAY_PATH).copy()
    data = _numeric(
        data,
        [
            "realized_pnl",
            "entry_year",
            "entry_day_minute_bars",
            "holding_window_minute_bars",
            "big_winner",
            "winner",
        ],
    )
    data["entry_year"] = data["entry_year"].astype("Int64")
    data["product"] = data["vt_symbol"].map(_product_from_vt)
    data["entry_day_covered"] = data["entry_day_minute_bars"].fillna(0).gt(0)
    data["holding_window_covered"] = data["holding_window_minute_bars"].fillna(0).gt(0)
    data["missing_entry_day"] = ~data["entry_day_covered"]
    data["abs_pnl"] = data["realized_pnl"].abs()
    data["big_winner_flag"] = data.get("big_winner", 0).fillna(0).astype(float).gt(0)
    return data


def _coverage_by_year(data: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for year, group in data.groupby("entry_year", dropna=False):
        lots = len(group)
        covered = int(group["entry_day_covered"].sum())
        missing = lots - covered
        missing_group = group[group["missing_entry_day"]]
        rows.append(
            {
                "entry_year": int(year) if pd.notna(year) else "",
                "lots": lots,
                "entry_day_covered_lots": covered,
                "entry_day_missing_lots": missing,
                "entry_day_coverage_rate": covered / lots if lots else 0.0,
                "total_pnl": float(group["realized_pnl"].sum()),
                "missing_pnl": float(missing_group["realized_pnl"].sum()),
                "missing_abs_pnl": float(missing_group["abs_pnl"].sum()),
                "big_winner_lots": int(group["big_winner_flag"].sum()),
                "missing_big_winner_lots": int(missing_group["big_winner_flag"].sum()),
            }
        )
    return pd.DataFrame(rows).sort_values("entry_year")


def _coverage_by_product(data: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for product, group in data.groupby("product", dropna=False):
        lots = len(group)
        covered = int(group["entry_day_covered"].sum())
        missing_group = group[group["missing_entry_day"]]
        rows.append(
            {
                "product": str(product),
                "lots": lots,
                "entry_day_covered_lots": covered,
                "entry_day_missing_lots": lots - covered,
                "entry_day_coverage_rate": covered / lots if lots else 0.0,
                "total_pnl": float(group["realized_pnl"].sum()),
                "missing_pnl": float(missing_group["realized_pnl"].sum()),
                "missing_abs_pnl": float(missing_group["abs_pnl"].sum()),
                "missing_big_winner_lots": int(missing_group["big_winner_flag"].sum()),
            }
        )
    return (
        pd.DataFrame(rows)
        .sort_values(["missing_abs_pnl", "entry_day_missing_lots", "product"], ascending=[False, False, True])
        .reset_index(drop=True)
    )


def _pressure_coverage() -> pd.DataFrame:
    minute = _load_csv(STAGE849_MINUTE_PATH).copy()
    pairs = _load_csv(STAGE849_PAIRS_PATH).copy()
    minute = _numeric(minute, ["minute_bars"])
    pairs = _numeric(
        pairs,
        [
            "volume_delta_C9_minus_C4",
            "risk_amount_delta_C9_minus_C4",
            "realized_pnl_delta_C9_minus_C4",
            "c9_to_c4_volume_ratio",
        ],
    )
    rows: list[dict[str, Any]] = []
    for episode_id, group in minute.groupby("episode_id", dropna=False):
        covered = group["minute_bars"].fillna(0).gt(0)
        pair_group = pairs[pairs["episode_id"].astype(str).eq(str(episode_id))]
        rows.append(
            {
                "episode_id": str(episode_id),
                "product_direction": (
                    f"{group['vt_symbol'].astype(str).map(_product_from_vt).mode().iloc[0]} "
                    f"{group['direction'].astype(str).mode().iloc[0]}"
                    if not group.empty
                    else ""
                ),
                "key_dates": int(len(group)),
                "covered_key_dates": int(covered.sum()),
                "coverage_rate": float(covered.mean()) if len(group) else 0.0,
                "pressure_pairs": int(len(pair_group)),
                "volume_delta_C9_minus_C4": float(pair_group["volume_delta_C9_minus_C4"].sum()),
                "risk_delta_C9_minus_C4": float(pair_group["risk_amount_delta_C9_minus_C4"].sum()),
                "pnl_delta_C9_minus_C4": float(pair_group["realized_pnl_delta_C9_minus_C4"].sum()),
                "median_c9_to_c4_volume_ratio": float(pair_group["c9_to_c4_volume_ratio"].median())
                if not pair_group.empty
                else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values(["coverage_rate", "episode_id"]).reset_index(drop=True)


def _product_from_vt(vt_symbol: Any) -> str:
    text = str(vt_symbol)
    if "." not in text:
        return text
    contract, exchange = text.split(".", 1)
    letters = "".join(ch for ch in contract if ch.isalpha())
    return f"{letters}.{exchange}" if letters else text


def _route_scoreboard(pdeg: dict[str, Any], full_coverage_rate: float, pressure_coverage_rate: float) -> pd.DataFrame:
    metrics = pdeg.get("metrics", {}) or {}
    rows = [
        {
            "route": "entry_day_stop_retry",
            "evidence": "Stage022/023",
            "positive_signal": "0.5R realtime stop + original-entry reclaim retry improves return and Sharpe.",
            "blocking_evidence": "C9 max drawdown worsens versus C4 and 2022 peak-trough path remains fragile.",
            "decision": "do_not_continue_r_multiple_or_retry_sweep",
        },
        {
            "route": "opening_range_confirmation",
            "evidence": "Stage010/834",
            "positive_signal": "Filters some stop_first left-tail lots.",
            "blocking_evidence": "Kills target_first right-tail; covered-lot deltas are negative.",
            "decision": "rejected",
        },
        {
            "route": "fail_fast_or_structure_break_exit",
            "evidence": "Stage016-021",
            "positive_signal": "Some gross lot-level repair exists.",
            "blocking_evidence": "Real engine kills recoverable winners or worsens broker10/Sharpe.",
            "decision": "rejected_no_more_bar_count_sweep",
        },
        {
            "route": "post_stop_cooldown_or_reuse_gate",
            "evidence": "Stage012/020/021",
            "positive_signal": "Reused capital after stop can be audited.",
            "blocking_evidence": "Incremental exposure after stops is often positive; blanket cooldown is contradicted.",
            "decision": "rejected",
        },
        {
            "route": "holding_product_direction_survival",
            "evidence": "Stage024-027",
            "positive_signal": (
                f"PDEG proxy catches {metrics.get('pressure_pairs_flagged', 0)}/"
                f"{metrics.get('pressure_pairs', 0)} pressure pairs."
            ),
            "blocking_evidence": (
                f"Trigger too broad: entry flag rate {float(metrics.get('entry_flag_rate', 0.0)):.4f}, "
                f"closed lot flag rate {float(metrics.get('closed_flag_rate', 0.0)):.4f}, "
                f"flagged big-winner pnl {float(metrics.get('closed_flagged_big_winner_pnl', 0.0)):.1f}."
            ),
            "decision": "reject_pdeg_v0_no_engine",
        },
        {
            "route": "minute_visual_evidence",
            "evidence": "Stage825/849",
            "positive_signal": "Atlas exists and some AP/fu pressure episodes have useful K-line evidence.",
            "blocking_evidence": (
                f"Full entry-day coverage {full_coverage_rate:.4f}; pressure key-date coverage "
                f"{pressure_coverage_rate:.4f}. Missing coverage is too large for a new rule."
            ),
            "decision": "continue_only_by_data_coverage_or_pause",
        },
    ]
    return pd.DataFrame(rows)


def _summary(
    intraday: pd.DataFrame,
    coverage_by_year: pd.DataFrame,
    pressure_coverage: pd.DataFrame,
    pdeg: dict[str, Any],
) -> pd.DataFrame:
    total_lots = len(intraday)
    covered_lots = int(intraday["entry_day_covered"].sum())
    missing_lots = total_lots - covered_lots
    pressure_dates = int(pressure_coverage["key_dates"].sum())
    pressure_covered = int(pressure_coverage["covered_key_dates"].sum())
    metrics = pdeg.get("metrics", {}) or {}
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "decision": "stage852_route_review_no_new_rule_until_minute_coverage_or_new_first_principle",
                "stage825_total_lots": total_lots,
                "stage825_entry_day_covered_lots": covered_lots,
                "stage825_entry_day_missing_lots": missing_lots,
                "stage825_entry_day_coverage_rate": covered_lots / total_lots if total_lots else 0.0,
                "stage825_missing_abs_pnl": float(intraday.loc[intraday["missing_entry_day"], "abs_pnl"].sum()),
                "stage825_missing_big_winner_lots": int(
                    intraday.loc[intraday["missing_entry_day"], "big_winner_flag"].sum()
                ),
                "pressure_key_dates": pressure_dates,
                "pressure_covered_key_dates": pressure_covered,
                "pressure_key_date_coverage_rate": pressure_covered / pressure_dates if pressure_dates else 0.0,
                "stage851_entry_flag_rate": float(metrics.get("entry_flag_rate", 0.0)),
                "stage851_closed_flag_rate": float(metrics.get("closed_flag_rate", 0.0)),
                "stage851_pressure_pairs_flagged": float(metrics.get("pressure_pairs_flagged", 0.0)),
                "stage851_pressure_pairs": float(metrics.get("pressure_pairs", 0.0)),
                "stage851_flagged_big_winner_pnl": float(metrics.get("closed_flagged_big_winner_pnl", 0.0)),
            }
        ]
    )


def _plot_coverage(coverage_by_year: pd.DataFrame, pressure_coverage: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    years = coverage_by_year["entry_year"].astype(str)
    axes[0].bar(years, coverage_by_year["entry_day_coverage_rate"], color="#2f6f9f")
    axes[0].set_ylim(0, 1.05)
    axes[0].set_title("Stage825 entry-day minute coverage")
    axes[0].set_ylabel("coverage rate")
    axes[0].tick_params(axis="x", rotation=45)

    episodes = pressure_coverage["episode_id"].astype(str)
    axes[1].barh(episodes, pressure_coverage["coverage_rate"], color="#b45f3c")
    axes[1].set_xlim(0, 1.05)
    axes[1].set_title("Stage849 pressure key-date coverage")
    axes[1].set_xlabel("coverage rate")
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=150)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    coverage_by_year: pd.DataFrame,
    coverage_by_product: pd.DataFrame,
    pressure_coverage: pd.DataFrame,
    route_scoreboard: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    row = summary.iloc[0]
    lines = [
        "# Stage852 Stage851后路线复盘与分钟K覆盖缺口审计",
        "",
        "## 阶段定位",
        "",
        "- 阶段性质：只读路线复盘；不新增策略规则、不接真实引擎、不连接 CTP、不调用下单。",
        "- 本阶段只回答两个问题：当前分支是否还能非过拟合推进；如果能，下一步应补什么证据。",
        "- 结论：不写新规则。Stage851 已证明 PDEG-v0 触发太宽，当前最可控的下一步是补分钟K覆盖和视觉证据；若不能补数据，应暂停持仓后 product-direction survival 分支。",
        "",
        "## 核心摘要",
        "",
        _md_table(summary),
        "",
        "## 全周期分钟K覆盖",
        "",
        _md_table(coverage_by_year),
        "",
        "## 缺口最大的产品",
        "",
        _md_table(coverage_by_product.head(12)),
        "",
        "## 压力段视觉证据覆盖",
        "",
        _md_table(pressure_coverage),
        "",
        "## 路线评分",
        "",
        _md_table(route_scoreboard),
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`",
        f"- 全周期入场日分钟覆盖：`{row['stage825_entry_day_covered_lots']}/{row['stage825_total_lots']} = {row['stage825_entry_day_coverage_rate']:.4%}`。",
        f"- 压力段关键日期分钟覆盖：`{row['pressure_covered_key_dates']}/{row['pressure_key_dates']} = {row['pressure_key_date_coverage_rate']:.4%}`。",
        f"- Stage851 PDEG-v0 entry flag rate：`{row['stage851_entry_flag_rate']:.4%}`，closed flag rate：`{row['stage851_closed_flag_rate']:.4%}`。",
        "- 不进入 A/B：没有新策略候选，只有路线复盘和数据覆盖审计。",
        "- 不更新 registry/back_log：本阶段不是正式候选、重要突破或跨线合并；只是研究线内部停止/收敛判断。",
        "",
        "## 后续 TODO",
        "",
        "1. 若继续，先补 Stage825 缺失的入场日分钟K，优先覆盖缺口最大且绝对 PnL 影响最大的产品/年份。",
        "2. 对 Stage849 缺失的 `fu_long` 与 `FG_short` 压力关键日期补分钟K后重画 episode atlas。",
        "3. 在视觉证据补足前，不再写 `0.4/0.6R`、OR、重试次数、产品方向阈值、年份/品种过滤等新规则。",
        "",
        "## 反思",
        "",
        "- 运行前过拟合判断：否。本阶段只读审计，不新增阈值，也不根据失败结果改策略。",
        "- 运行后过拟合判断：否。结论反而收敛研究自由度，禁止把 PDEG-v0 救成小参数补丁。",
        "- 运行前继续价值判断：有价值。它能决定本线是否应该继续投入分钟K数据补齐。",
        "- 运行后继续价值判断：有条件有价值。继续价值只在补数据/补视觉证据；如果不补分钟数据，当前规则分支继续写引擎的价值很低。",
        "",
        "## 输出",
        "",
        f"- coverage_by_year：`{COVERAGE_BY_YEAR_PATH}`",
        f"- coverage_by_product：`{COVERAGE_BY_PRODUCT_PATH}`",
        f"- pressure_coverage：`{PRESSURE_COVERAGE_PATH}`",
        f"- route_scoreboard：`{ROUTE_SCOREBOARD_PATH}`",
        f"- chart：`{CHART_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    intraday = _prepare_intraday()
    coverage_source = _load_csv(STAGE825_COVERAGE_PATH)
    # Keep the source read explicit; the detailed audit is recomputed from per-lot rows.
    if coverage_source.empty:
        raise RuntimeError(f"Empty required input: {STAGE825_COVERAGE_PATH}")
    pdeg = _load_json(STAGE851_DECISION_PATH)

    coverage_by_year = _coverage_by_year(intraday)
    coverage_by_product = _coverage_by_product(intraday)
    pressure_coverage = _pressure_coverage()
    full_rate = float(intraday["entry_day_covered"].mean()) if len(intraday) else 0.0
    pressure_dates = int(pressure_coverage["key_dates"].sum())
    pressure_covered = int(pressure_coverage["covered_key_dates"].sum())
    pressure_rate = pressure_covered / pressure_dates if pressure_dates else 0.0
    route_scoreboard = _route_scoreboard(pdeg, full_rate, pressure_rate)
    summary = _summary(intraday, coverage_by_year, pressure_coverage, pdeg)

    coverage_by_year.to_csv(COVERAGE_BY_YEAR_PATH, index=False, encoding="utf-8-sig")
    coverage_by_product.to_csv(COVERAGE_BY_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    pressure_coverage.to_csv(PRESSURE_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    route_scoreboard.to_csv(ROUTE_SCOREBOARD_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    _plot_coverage(coverage_by_year, pressure_coverage)

    decision = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "line_id": LINE_ID,
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": "stage852_route_review_no_new_rule_until_minute_coverage_or_new_first_principle",
        "new_rule_allowed": 0,
        "engine_allowed": 0,
        "next_step": "Fill missing minute bars for high-impact gaps and redraw visual atlases; otherwise pause the holding product-direction survival branch.",
        "metrics": summary.iloc[0].to_dict(),
        "inputs": {
            "stage825_intraday": str(STAGE825_INTRADAY_PATH),
            "stage825_coverage": str(STAGE825_COVERAGE_PATH),
            "stage849_minute_features": str(STAGE849_MINUTE_PATH),
            "stage849_pairs": str(STAGE849_PAIRS_PATH),
            "stage851_decision": str(STAGE851_DECISION_PATH),
        },
        "outputs": {
            "coverage_by_year": str(COVERAGE_BY_YEAR_PATH),
            "coverage_by_product": str(COVERAGE_BY_PRODUCT_PATH),
            "pressure_coverage": str(PRESSURE_COVERAGE_PATH),
            "route_scoreboard": str(ROUTE_SCOREBOARD_PATH),
            "summary": str(SUMMARY_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, coverage_by_year, coverage_by_product, pressure_coverage, route_scoreboard, decision)
    print(f"[{STAGE}] decision: {decision['decision']}")
    print(f"[{STAGE}] report: {REPORT_PATH}")
    print(f"[{STAGE}] decision json: {DECISION_PATH}")


if __name__ == "__main__":
    main()
