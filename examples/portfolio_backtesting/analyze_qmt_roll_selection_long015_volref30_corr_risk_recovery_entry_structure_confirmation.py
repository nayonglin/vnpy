from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    FU_PRODUCT,
    to_markdown_table,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "risk_recovery_entry_structure_confirmation_v1"
OUTPUT_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_risk_recovery_entry_structure_confirmation"

STAGE82_EVENT_TABLE_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_selection_long015_volref30_corr_risk_recovery_core_confirmation_event_table_risk_recovery_core_confirmation_v1.csv"
)

EVENT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_table_{MODEL_TAG}.csv"
CANDIDATE_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_summary_{MODEL_TAG}.csv"
PERIOD_CANDIDATE_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_period_candidate_summary_{MODEL_TAG}.csv"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

EARLY_CROSS_SIGNALS: frozenset[str] = frozenset({"long_case1a", "short_case1a"})
CASE2_SIGNALS: frozenset[str] = frozenset({"long_case2", "short_case2"})


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(number) or np.isinf(number):
        return default
    return number


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def _bool_series(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype(bool)


def add_structure_flags(events: pd.DataFrame) -> pd.DataFrame:
    result = events.copy()
    result["date"] = pd.to_datetime(result["date"]).dt.normalize()
    result["signal"] = result["signal"].astype(str)
    result["direction"] = result["direction"].astype(str)
    result["product_vt_symbol"] = result["product_vt_symbol"].astype(str)

    result["structure_flat_product"] = (_safe_numeric(result, "shield_active_positions_before") <= 0.0)
    result["structure_no_same_direction_position"] = (
        _safe_numeric(result, "shield_same_direction_correlation_active_count") <= 0.0
    )
    result["structure_low_same_direction_corr"] = (
        _safe_numeric(result, "shield_same_direction_correlation_max_corr") <= 0.30
    )
    result["structure_low_crowding"] = (
        result["structure_no_same_direction_position"] & result["structure_low_same_direction_corr"]
    )
    result["structure_clean_book"] = result["structure_flat_product"] & result["structure_low_crowding"]
    result["structure_early_cross"] = result["signal"].isin(EARLY_CROSS_SIGNALS)
    result["structure_not_case2"] = ~result["signal"].isin(CASE2_SIGNALS)
    result["structure_long_early_cross"] = result["signal"].eq("long_case1a")
    result["structure_short_early_cross"] = result["signal"].eq("short_case1a")
    result["structure_top_pair_rank"] = (
        (_safe_numeric(result, "shield_selection_pairwise_rank") <= 1.0)
        | (_safe_numeric(result, "shield_selection_pairwise_rank") <= 0.0)
    )
    result["structure_not_satellite"] = result["product_vt_symbol"] != FU_PRODUCT
    result["structure_low_drawdown"] = _safe_numeric(result, "shield_portfolio_drawdown_pct") <= 0.05
    return result


def _safe_numeric(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(0.0, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)


def add_candidate_flags(events: pd.DataFrame) -> pd.DataFrame:
    result = events.copy()
    clean = _bool_series(result["structure_clean_book"])
    early = _bool_series(result["structure_early_cross"])
    not_case2 = _bool_series(result["structure_not_case2"])
    top_rank = _bool_series(result["structure_top_pair_rank"])
    not_satellite = _bool_series(result["structure_not_satellite"])
    low_dd = _bool_series(result["structure_low_drawdown"])

    result["candidate_clean_book"] = clean.astype("int64")
    result["candidate_clean_book_not_case2"] = (clean & not_case2).astype("int64")
    result["candidate_early_cross_clean_book"] = (early & clean).astype("int64")
    result["candidate_early_cross_clean_book_top_rank"] = (early & clean & top_rank).astype("int64")
    result["candidate_early_cross_clean_book_not_satellite"] = (early & clean & not_satellite).astype("int64")
    result["candidate_long_early_cross_clean_book"] = (
        _bool_series(result["structure_long_early_cross"]) & clean
    ).astype("int64")
    result["candidate_short_early_cross_clean_book"] = (
        _bool_series(result["structure_short_early_cross"]) & clean
    ).astype("int64")
    result["candidate_clean_book_low_drawdown"] = (clean & low_dd).astype("int64")
    return result


def candidate_effect(events: pd.DataFrame, restore_mask: pd.Series) -> dict[str, Any]:
    restore_mask = _bool_series(restore_mask)
    candidate_pnl = events["shield_next20_product_net_pnl"].where(
        ~restore_mask,
        events["stage75_next20_product_net_pnl"],
    )
    value_vs_shield = candidate_pnl - events["shield_next20_product_net_pnl"]
    return {
        "restore_event_count": int(restore_mask.sum()),
        "restore_better_event_count": int((restore_mask & (events["restore_better_flag"] > 0)).sum()),
        "false_restore_event_count": int((restore_mask & (events["shield_better_flag"] > 0)).sum()),
        "candidate_next20_product_net_pnl": float(candidate_pnl.sum()),
        "candidate_value_vs_shield": float(value_vs_shield.sum()),
        "restore_hit_rate": float((restore_mask & (events["restore_better_flag"] > 0)).sum() / restore_mask.sum())
        if restore_mask.any()
        else 0.0,
    }


def build_candidate_summary(events: pd.DataFrame) -> pd.DataFrame:
    shield_total = float(events["shield_next20_product_net_pnl"].sum())
    restore_total = float(events["stage75_next20_product_net_pnl"].sum())
    rows: list[dict[str, Any]] = [
        {
            "candidate": "always_shield",
            "is_baseline": 1,
            "direction_specific": 0,
            "candidate_next20_product_net_pnl": shield_total,
            "always_shield_next20_product_net_pnl": shield_total,
            "always_restore_next20_product_net_pnl": restore_total,
            "candidate_value_vs_shield": 0.0,
            "candidate_value_vs_always_restore": shield_total - restore_total,
            "restore_event_count": 0,
            "restore_better_event_count": 0,
            "false_restore_event_count": 0,
            "restore_hit_rate": 0.0,
        },
        {
            "candidate": "always_restore",
            "is_baseline": 1,
            "direction_specific": 0,
            "candidate_next20_product_net_pnl": restore_total,
            "always_shield_next20_product_net_pnl": shield_total,
            "always_restore_next20_product_net_pnl": restore_total,
            "candidate_value_vs_shield": restore_total - shield_total,
            "candidate_value_vs_always_restore": 0.0,
            "restore_event_count": int(len(events)),
            "restore_better_event_count": int(events["restore_better_flag"].sum()),
            "false_restore_event_count": int(events["shield_better_flag"].sum()),
            "restore_hit_rate": float(events["restore_better_flag"].mean()),
        },
    ]

    for column in [column for column in events.columns if column.startswith("candidate_")]:
        effect = candidate_effect(events, events[column] > 0)
        candidate = column.replace("candidate_", "")
        rows.append(
            {
                "candidate": candidate,
                "is_baseline": 0,
                "direction_specific": int(candidate.startswith("long_") or candidate.startswith("short_")),
                "always_shield_next20_product_net_pnl": shield_total,
                "always_restore_next20_product_net_pnl": restore_total,
                "candidate_value_vs_always_restore": float(effect["candidate_next20_product_net_pnl"] - restore_total),
                **effect,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["candidate_value_vs_shield", "direction_specific", "restore_hit_rate"],
        ascending=[False, True, False],
    )


def build_period_candidate_summary(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    candidate_columns = [column for column in events.columns if column.startswith("candidate_")]
    for period, group in events.groupby("period", sort=True):
        for column in candidate_columns:
            effect = candidate_effect(group, group[column] > 0)
            rows.append(
                {
                    "period": period,
                    "candidate": column.replace("candidate_", ""),
                    **effect,
                }
            )
    return pd.DataFrame(rows).sort_values(["candidate", "period"]).reset_index(drop=True)


def build_summary(
    events: pd.DataFrame,
    candidate_summary: pd.DataFrame,
    period_candidate_summary: pd.DataFrame,
) -> dict[str, Any]:
    structural = candidate_summary[candidate_summary["is_baseline"] == 0].copy()
    best = structural.iloc[0].to_dict() if not structural.empty else {}
    best_name = str(best.get("candidate", ""))
    best_period = period_candidate_summary[period_candidate_summary["candidate"] == best_name].copy()
    return {
        "model_tag": MODEL_TAG,
        "event_count": int(len(events)),
        "product_count": int(events["product_vt_symbol"].nunique()),
        "restore_better_event_count": int(events["restore_better_flag"].sum()),
        "shield_better_event_count": int(events["shield_better_flag"].sum()),
        "stage75_next20_product_net_pnl": float(events["stage75_next20_product_net_pnl"].sum()),
        "shield_next20_product_net_pnl": float(events["shield_next20_product_net_pnl"].sum()),
        "best_structural_candidate": best,
        "best_structural_candidate_periods": best_period.replace({np.nan: None}).to_dict(orient="records"),
        "candidate_summary": candidate_summary.replace({np.nan: None}).to_dict(orient="records"),
    }


def build_report(
    summary: dict[str, Any],
    events: pd.DataFrame,
    candidate_summary: pd.DataFrame,
    period_candidate_summary: pd.DataFrame,
) -> str:
    best = summary.get("best_structural_candidate", {})
    display_candidates = candidate_summary[
        [
            "candidate",
            "is_baseline",
            "direction_specific",
            "restore_event_count",
            "restore_better_event_count",
            "false_restore_event_count",
            "candidate_next20_product_net_pnl",
            "candidate_value_vs_shield",
            "candidate_value_vs_always_restore",
            "restore_hit_rate",
        ]
    ].copy()
    best_name = str(best.get("candidate", ""))
    best_period = period_candidate_summary[period_candidate_summary["candidate"] == best_name].copy()
    key_event_columns = [
        "date",
        "period",
        "product_vt_symbol",
        "direction",
        "signal",
        "outcome_label",
        "stage75_selected_volume",
        "shield_selected_volume",
        "stage75_next20_product_net_pnl",
        "shield_next20_product_net_pnl",
        "delta_next20_product_net_pnl",
        "structure_clean_book",
        "structure_early_cross",
        "candidate_early_cross_clean_book",
        "candidate_clean_book_not_case2",
    ]
    key_events = events[key_event_columns].sort_values("delta_next20_product_net_pnl")

    lines = [
        f"# {MODEL_TAG}",
        "",
        "## 目的",
        "",
        "- 本阶段只做入场结构归因，不修改策略、不新增回测。",
        "- 诊断对象仍是第75阶段与第78阶段的风险恢复分歧事件。",
        "- 与第82阶段不同，本阶段不再看核心池历史盈利，而是看事件当下的入场结构：是否早期交叉、是否已有同向持仓、是否同向相关性拥挤。",
        "",
        "## 候选评分",
        "",
        to_markdown_table(display_candidates),
        "",
        "## 最优结构候选分阶段表现",
        "",
        to_markdown_table(best_period),
        "",
        "## 关键事件",
        "",
        to_markdown_table(key_events.head(14)),
        "",
        "## 判断",
        "",
        f"- 当前最优结构候选为`{best_name}`，相对第78阶段事件级贡献`{_safe_float(best.get('candidate_value_vs_shield')):,.0f}`，相对始终恢复贡献`{_safe_float(best.get('candidate_value_vs_always_restore')):,.0f}`。",
        "- 这说明入场结构比核心池历史盈利更接近风险恢复问题的本质，但它仍只是事件级归因，不等于策略回测结果。",
        "- 如果进入策略层，应优先测试非方向专属的`early_cross_clean_book`，因为它来自信号结构和持仓拥挤，而不是单独押注多头或某一年。",
        "- `long_early_cross_clean_book`虽然评分很高，但方向专属，必须视为过拟合风险较高的旁证，不能优先升级。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    events = _read_csv(STAGE82_EVENT_TABLE_PATH)
    events = add_structure_flags(events)
    events = add_candidate_flags(events)
    candidate_summary = build_candidate_summary(events)
    period_candidate_summary = build_period_candidate_summary(events)
    summary = build_summary(events, candidate_summary, period_candidate_summary)
    report = build_report(summary, events, candidate_summary, period_candidate_summary)

    events.to_csv(EVENT_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    candidate_summary.to_csv(CANDIDATE_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    period_candidate_summary.to_csv(PERIOD_CANDIDATE_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_OUTPUT_PATH.write_text(report, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"wrote {REPORT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
