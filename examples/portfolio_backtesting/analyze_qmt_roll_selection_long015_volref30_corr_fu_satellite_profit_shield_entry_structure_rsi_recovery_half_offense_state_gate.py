from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_selection_long015_volref30_corr_entry_structure_recovery_trigger_attribution import (
    _numeric_series,
    _read_csv,
)
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "entry_structure_rsi_recovery_half_offense_state_gate_v1"
OUTPUT_PREFIX: str = (
    "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_"
    "entry_structure_rsi_recovery_half_offense_state_gate"
)

EVENT_TABLE_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_"
    "entry_structure_rsi_recovery_half_event_branch_event_table_"
    "entry_structure_rsi_recovery_half_event_branch_v1.csv"
)
STAGE78_DAILY_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_formal_daily.csv"
)

GATED_EVENT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_table_{MODEL_TAG}.csv"
GATE_SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_summary_{MODEL_TAG}.csv"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def load_stage78_daily_features() -> pd.DataFrame:
    daily = _read_csv(STAGE78_DAILY_PATH)
    daily["date"] = pd.to_datetime(daily["date"]).dt.normalize()
    for column in ("net_pnl", "balance", "ddpercent", "trade_count", "slippage"):
        daily[column] = _numeric_series(daily, column)
    daily = daily.sort_values("date").reset_index(drop=True)
    daily["observation_count"] = np.arange(len(daily), dtype="int64")
    daily["cum_net_pnl"] = daily["net_pnl"].cumsum()
    for window in (20, 60, 120):
        daily[f"prior{window}_net_pnl"] = daily["net_pnl"].rolling(window, min_periods=1).sum().shift(1)
        daily[f"prior{window}_trade_count"] = daily["trade_count"].rolling(window, min_periods=1).sum().shift(1)
        daily[f"prior{window}_positive_day_rate"] = (
            daily["net_pnl"].gt(0).astype("float64").rolling(window, min_periods=1).mean().shift(1)
        )
        daily[f"prior{window}_balance_ma"] = daily["balance"].rolling(window, min_periods=1).mean().shift(1)
        daily[f"balance_above_prior{window}_ma"] = (daily["balance"].shift(1) > daily[f"prior{window}_balance_ma"]).astype(
            "int64"
        )
    daily["prior_drawdown_pct_abs"] = daily["ddpercent"].shift(1).abs()
    daily["prior_cum_net_pnl"] = daily["cum_net_pnl"].shift(1)
    fill_columns = [
        column
        for column in daily.columns
        if column.startswith("prior") or column.startswith("balance_above_prior")
    ]
    daily[fill_columns] = daily[fill_columns].fillna(0.0)
    return daily


def load_events() -> pd.DataFrame:
    events = _read_csv(EVENT_TABLE_PATH)
    events["date"] = pd.to_datetime(events["date"]).dt.normalize()
    numeric_columns = [
        "stage90_vs_stage78_next20_product_net_pnl",
        "stage90_next20_product_net_pnl",
        "stage78_next20_product_net_pnl",
        "selected_volume_delta_vs_stage78",
        "portfolio_drawdown_pct",
        "same_direction_correlation_max_corr",
        "ai_product_pool_rank",
        "rsi_value",
    ]
    for column in numeric_columns:
        events[column] = _numeric_series(events, column)
    return events.sort_values("date").reset_index(drop=True)


def attach_defense_state(events: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    merge_columns = [
        "date",
        "observation_count",
        "prior_cum_net_pnl",
        "prior_drawdown_pct_abs",
        "prior20_net_pnl",
        "prior60_net_pnl",
        "prior120_net_pnl",
        "prior20_positive_day_rate",
        "prior60_positive_day_rate",
        "prior120_positive_day_rate",
        "prior20_trade_count",
        "prior60_trade_count",
        "prior120_trade_count",
        "balance_above_prior20_ma",
        "balance_above_prior60_ma",
        "balance_above_prior120_ma",
    ]
    state = daily[merge_columns].copy()
    return pd.merge_asof(
        events.sort_values("date"),
        state.sort_values("date"),
        on="date",
        direction="backward",
        allow_exact_matches=False,
    ).fillna(0.0)


def add_gate_flags(events: pd.DataFrame) -> pd.DataFrame:
    result = events.copy()
    result["gate_all_events"] = 1
    result["gate_not_cold_120d"] = (_numeric_series(result, "observation_count") >= 120.0).astype("int64")
    result["gate_prior_cum_pnl_gt0"] = (_numeric_series(result, "prior_cum_net_pnl") > 0.0).astype("int64")
    result["gate_prior20_pnl_gt0"] = (_numeric_series(result, "prior20_net_pnl") > 0.0).astype("int64")
    result["gate_prior60_pnl_gt0"] = (_numeric_series(result, "prior60_net_pnl") > 0.0).astype("int64")
    result["gate_prior120_pnl_gt0"] = (_numeric_series(result, "prior120_net_pnl") > 0.0).astype("int64")
    result["gate_prior20_60_120_pnl_gt0"] = (
        (result["gate_prior20_pnl_gt0"] > 0)
        & (result["gate_prior60_pnl_gt0"] > 0)
        & (result["gate_prior120_pnl_gt0"] > 0)
    ).astype("int64")
    result["gate_balance_above_60ma"] = (_numeric_series(result, "balance_above_prior60_ma") > 0.0).astype("int64")
    result["gate_balance_above_120ma"] = (_numeric_series(result, "balance_above_prior120_ma") > 0.0).astype("int64")
    result["gate_prior60_positive_day_rate_gt50"] = (
        _numeric_series(result, "prior60_positive_day_rate") > 0.50
    ).astype("int64")
    result["gate_prior120_positive_day_rate_gt50"] = (
        _numeric_series(result, "prior120_positive_day_rate") > 0.50
    ).astype("int64")
    result["gate_defense_mature_and_prior60_pnl_gt0"] = (
        (result["gate_not_cold_120d"] > 0) & (result["gate_prior60_pnl_gt0"] > 0)
    ).astype("int64")
    result["gate_defense_mature_prior60_pnl_and_balance_gt60ma"] = (
        (result["gate_not_cold_120d"] > 0)
        & (result["gate_prior60_pnl_gt0"] > 0)
        & (result["gate_balance_above_60ma"] > 0)
    ).astype("int64")
    result["gate_prior_drawdown_lte20"] = (_numeric_series(result, "prior_drawdown_pct_abs") <= 20.0).astype("int64")
    result["gate_prior_drawdown_lte30"] = (_numeric_series(result, "prior_drawdown_pct_abs") <= 30.0).astype("int64")
    return result


def gate_effect(events: pd.DataFrame, keep_mask: pd.Series) -> dict[str, Any]:
    keep = keep_mask.fillna(False).astype(bool)
    kept = events[keep]
    all_positive = events["stage90_vs_stage78_next20_product_net_pnl"] > 0.0
    delta = events["stage90_vs_stage78_next20_product_net_pnl"].where(keep, 0.0)
    return {
        "event_count": int(keep.sum()),
        "stage90_better_event_count": int((keep & all_positive).sum()),
        "stage78_better_event_count": int(
            (keep & (events["stage90_vs_stage78_next20_product_net_pnl"] < 0.0)).sum()
        ),
        "stage90_next20_product_net_pnl": float(kept["stage90_next20_product_net_pnl"].sum()) if not kept.empty else 0.0,
        "stage78_next20_product_net_pnl": float(kept["stage78_next20_product_net_pnl"].sum()) if not kept.empty else 0.0,
        "stage90_value_vs_stage78": float(delta.sum()),
        "negative_delta_cost": float(delta.where(delta < 0.0, 0.0).sum()),
        "missed_positive_delta": float(
            events["stage90_vs_stage78_next20_product_net_pnl"].where((~keep) & all_positive, 0.0).sum()
        ),
        "hit_rate": float((keep & all_positive).sum() / keep.sum()) if keep.any() else 0.0,
        "avg_prior60_net_pnl": float(kept["prior60_net_pnl"].mean()) if not kept.empty else 0.0,
        "avg_prior_drawdown_pct_abs": float(kept["prior_drawdown_pct_abs"].mean()) if not kept.empty else 0.0,
    }


def build_gate_summary(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for column in events.columns:
        if not column.startswith("gate_"):
            continue
        values = pd.to_numeric(events[column], errors="coerce").dropna()
        if values.empty:
            continue
        unique_values = set(values.astype("int64").unique().tolist())
        if unique_values.issubset({0, 1}):
            rows.append({"gate": column.replace("gate_", ""), **gate_effect(events, events[column] > 0)})
    return (
        pd.DataFrame(rows)
        .sort_values(["stage90_value_vs_stage78", "event_count", "hit_rate"], ascending=[False, False, False])
        .reset_index(drop=True)
    )


def build_payload(events: pd.DataFrame, gate_summary: pd.DataFrame) -> dict[str, Any]:
    best_gate = gate_summary.iloc[0].to_dict() if not gate_summary.empty else {}
    all_gate = gate_summary[gate_summary["gate"] == "all_events"]
    all_gate_payload = all_gate.iloc[0].to_dict() if not all_gate.empty else {}
    return {
        "model_tag": MODEL_TAG,
        "event_count": int(len(events)),
        "all_events": all_gate_payload,
        "best_gate": best_gate,
        "gate_summary": gate_summary.replace({np.nan: None}).to_dict(orient="records"),
        "artifacts": {
            "gated_event_table": str(GATED_EVENT_OUTPUT_PATH),
            "gate_summary": str(GATE_SUMMARY_OUTPUT_PATH),
            "summary": str(SUMMARY_OUTPUT_PATH),
            "report": str(REPORT_OUTPUT_PATH),
        },
    }


def build_report(events: pd.DataFrame, gate_summary: pd.DataFrame, payload: dict[str, Any]) -> str:
    best = payload.get("best_gate", {})
    event_view = events[
        [
            "date",
            "period",
            "product_vt_symbol",
            "direction",
            "signal",
            "stage90_vs_stage78_next20_product_net_pnl",
            "prior20_net_pnl",
            "prior60_net_pnl",
            "prior120_net_pnl",
            "prior_cum_net_pnl",
            "prior_drawdown_pct_abs",
            "prior60_positive_day_rate",
            "balance_above_prior60_ma",
        ]
    ].sort_values("stage90_vs_stage78_next20_product_net_pnl")
    lines = [
        f"# {MODEL_TAG}",
        "",
        "## 目的",
        "",
        "- 不直接使用年份、产品或事后收益标签。",
        "- 用第78防守版本在事件发生前已经形成的组合状态，评估是否存在可用于进攻/防守切换的低自由度状态门。",
        "- 所有状态特征都用事件日前的日度结果计算，避免同日和未来信息。",
        "",
        "## 状态门评分",
        "",
        to_markdown_table(gate_summary),
        "",
        "## 事件状态明细",
        "",
        to_markdown_table(event_view),
        "",
        "## 判断",
        "",
        f"- 当前最优状态门为`{best.get('gate', '')}`，保留事件`{int(best.get('event_count', 0) or 0)}`笔，相对第78贡献`{float(best.get('stage90_value_vs_stage78', 0.0) or 0.0):,.0f}`。",
        "- 状态门只是一层研究假设；若它只是筛掉少数历史坏事件，仍可能过拟合。",
        "- 下一步只有在薄弱起点和滑点压力下仍能改善，才值得写入策略层。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    events = load_events()
    daily = load_stage78_daily_features()
    events = attach_defense_state(events, daily)
    events = add_gate_flags(events)
    gate_summary = build_gate_summary(events)
    payload = build_payload(events, gate_summary)
    report = build_report(events, gate_summary, payload)

    events.to_csv(GATED_EVENT_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    gate_summary.to_csv(GATE_SUMMARY_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_OUTPUT_PATH.write_text(report, encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"wrote {REPORT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
