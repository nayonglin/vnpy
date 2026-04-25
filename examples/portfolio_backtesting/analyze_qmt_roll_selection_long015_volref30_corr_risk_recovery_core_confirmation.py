from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_ai_product_suitability_walkforward import product_from_contract
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH,
    AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
    FU_PRODUCT,
    to_markdown_table,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "risk_recovery_core_confirmation_v1"
OUTPUT_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_risk_recovery_core_confirmation"

STAGE75_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_fu_satellite_post_signal_formal"
SHIELD_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_formal"
STAGE80_DIVERGENCE_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_selection_long015_volref30_corr_portfolio_risk_state_attribution_risk_recovery_divergence_portfolio_risk_state_attribution_v1.csv"
)

LOOKBACKS: tuple[int, ...] = (5, 10, 20)

EVENT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_table_{MODEL_TAG}.csv"
CANDIDATE_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_summary_{MODEL_TAG}.csv"
PERIOD_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_period_summary_{MODEL_TAG}.csv"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(number) or math.isinf(number):
        return default
    return number


def _numeric_series(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(default)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def load_eligibility() -> pd.DataFrame:
    df = _read_csv(AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH)
    df = df[df["strategy"].astype(str) == AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME].copy()
    if df.empty:
        raise ValueError("AI satellite post-signal eligibility is empty")
    df["eval_date"] = pd.to_datetime(df["eval_date"]).dt.normalize()
    df["product_vt_symbol"] = df["product_vt_symbol"].astype(str)
    df["score_rank"] = _numeric_series(df, "score_rank")
    df["top_n"] = _numeric_series(df, "top_n")
    return df.sort_values(["eval_date", "score_rank", "product_vt_symbol"]).reset_index(drop=True)


def core_products_for_date(eligibility: pd.DataFrame, date: pd.Timestamp) -> list[str]:
    eligible = eligibility[eligibility["eval_date"] <= date]
    if eligible.empty:
        return []
    latest_date = eligible["eval_date"].max()
    latest = eligible[eligible["eval_date"] == latest_date].copy()
    latest = latest[latest["product_vt_symbol"] != FU_PRODUCT]
    top_n = int(_safe_float(latest["top_n"].max(), 0.0))
    if top_n <= 9:
        latest = latest[latest["score_rank"] <= 8]
    return latest["product_vt_symbol"].astype(str).tolist()


def load_product_daily(prefix: str) -> pd.DataFrame:
    path = OUTPUT_DIR / f"{prefix}_position_changes_2020_2026_04.csv"
    df = _read_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["product_vt_symbol"] = df["vt_symbol"].map(product_from_contract)
    for column in ("net_pnl", "total_pnl", "holding_pnl", "trading_pnl", "slippage", "trade_count", "pos_change"):
        df[column] = _numeric_series(df, column)
    grouped = (
        df.groupby(["date", "product_vt_symbol"], as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            total_pnl=("total_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            slippage=("slippage", "sum"),
            trade_count=("trade_count", "sum"),
            abs_pos_change=("pos_change", lambda values: float(pd.to_numeric(values, errors="coerce").abs().sum())),
        )
        .sort_values(["date", "product_vt_symbol"])
        .reset_index(drop=True)
    )
    return grouped


def load_strategy_daily(prefix: str) -> pd.DataFrame:
    path = OUTPUT_DIR / f"{prefix}_daily.csv"
    df = _read_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    for column in ("net_pnl", "balance", "drawdown", "ddpercent", "trade_count", "slippage"):
        df[column] = _numeric_series(df, column)
    return df.sort_values("date").reset_index(drop=True)


def build_product_pivot(product_daily: pd.DataFrame) -> pd.DataFrame:
    return (
        product_daily.pivot_table(
            index="date",
            columns="product_vt_symbol",
            values="net_pnl",
            aggfunc="sum",
            fill_value=0.0,
        )
        .sort_index()
        .astype("float64")
    )


def trailing_product_metrics(
    pivot: pd.DataFrame,
    date: pd.Timestamp,
    products: list[str],
    lookback: int,
) -> dict[str, float]:
    available = [product for product in products if product in pivot.columns]
    if not available:
        return {
            "net_pnl": 0.0,
            "positive_count": 0.0,
            "active_count": 0.0,
            "positive_breadth": 0.0,
        }
    window = pivot[pivot.index < date].tail(lookback)
    if window.empty:
        return {
            "net_pnl": 0.0,
            "positive_count": 0.0,
            "active_count": 0.0,
            "positive_breadth": 0.0,
        }
    product_pnl = window[available].sum(axis=0)
    active_mask = product_pnl.abs() > 1e-9
    active_count = int(active_mask.sum())
    positive_count = int((product_pnl[active_mask] > 0).sum())
    positive_breadth = float(positive_count / active_count) if active_count else 0.0
    return {
        "net_pnl": float(product_pnl.sum()),
        "positive_count": float(positive_count),
        "active_count": float(active_count),
        "positive_breadth": positive_breadth,
    }


def trailing_strategy_metrics(daily: pd.DataFrame, date: pd.Timestamp, lookback: int) -> dict[str, float]:
    window = daily[daily["date"] < date].tail(lookback)
    if window.empty:
        return {
            "net_pnl": 0.0,
            "last_ddpercent": 0.0,
            "ddpercent_change": 0.0,
        }
    first_dd = _safe_float(window.iloc[0].get("ddpercent"))
    last_dd = _safe_float(window.iloc[-1].get("ddpercent"))
    return {
        "net_pnl": float(window["net_pnl"].sum()),
        "last_ddpercent": last_dd,
        "ddpercent_change": last_dd - first_dd,
    }


def attach_core_confirmation_metrics(
    divergence: pd.DataFrame,
    eligibility: pd.DataFrame,
    product_pivots: dict[str, pd.DataFrame],
    strategy_daily: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in divergence.itertuples(index=False):
        date = pd.Timestamp(row.date).normalize()
        core_products = core_products_for_date(eligibility, date)
        event: dict[str, Any] = row._asdict()
        event["date"] = date.date().isoformat()
        event["core_pool_size"] = len(core_products)
        event["core_products"] = ";".join(core_products)
        event["restore_better_flag"] = int(_safe_float(event.get("delta_next20_product_net_pnl")) < 0.0)
        event["shield_better_flag"] = int(_safe_float(event.get("delta_next20_product_net_pnl")) > 0.0)
        event["outcome_label"] = "restore_better" if event["restore_better_flag"] else "shield_better"

        event_product = str(event.get("product_vt_symbol", ""))
        non_event_core_products = [product for product in core_products if product != event_product]
        for variant, pivot in product_pivots.items():
            for lookback in LOOKBACKS:
                core = trailing_product_metrics(pivot, date, core_products, lookback)
                non_event_core = trailing_product_metrics(pivot, date, non_event_core_products, lookback)
                product = trailing_product_metrics(pivot, date, [event_product], lookback)
                strategy = trailing_strategy_metrics(strategy_daily[variant], date, lookback)
                prefix = f"{variant}_prev{lookback}"
                event[f"{prefix}_core_net_pnl"] = core["net_pnl"]
                event[f"{prefix}_core_positive_count"] = core["positive_count"]
                event[f"{prefix}_core_active_count"] = core["active_count"]
                event[f"{prefix}_core_positive_breadth"] = core["positive_breadth"]
                event[f"{prefix}_non_event_core_net_pnl"] = non_event_core["net_pnl"]
                event[f"{prefix}_event_product_net_pnl"] = product["net_pnl"]
                event[f"{prefix}_strategy_net_pnl"] = strategy["net_pnl"]
                event[f"{prefix}_strategy_last_ddpercent"] = strategy["last_ddpercent"]
                event[f"{prefix}_strategy_ddpercent_change"] = strategy["ddpercent_change"]
        rows.append(event)
    return pd.DataFrame(rows)


def add_candidate_flags(event_table: pd.DataFrame) -> pd.DataFrame:
    result = event_table.copy()
    result["candidate_core_prev10_pnl_positive"] = (result["shield_prev10_core_net_pnl"] > 0.0).astype("int64")
    result["candidate_core_prev20_pnl_positive"] = (result["shield_prev20_core_net_pnl"] > 0.0).astype("int64")
    result["candidate_core_prev20_breadth_half"] = (
        (result["shield_prev20_core_active_count"] >= 3.0)
        & (result["shield_prev20_core_positive_breadth"] >= 0.5)
    ).astype("int64")
    result["candidate_core_prev20_pnl_and_breadth"] = (
        (result["shield_prev20_core_net_pnl"] > 0.0)
        & (result["shield_prev20_core_active_count"] >= 3.0)
        & (result["shield_prev20_core_positive_breadth"] >= 0.5)
    ).astype("int64")
    result["candidate_core_prev20_and_portfolio_prev10"] = (
        (result["shield_prev20_core_net_pnl"] > 0.0)
        & (result["shield_prev10_strategy_net_pnl"] > 0.0)
    ).astype("int64")
    result["candidate_core_prev20_non_event_positive"] = (
        result["shield_prev20_non_event_core_net_pnl"] > 0.0
    ).astype("int64")
    return result


def build_candidate_summary(event_table: pd.DataFrame) -> pd.DataFrame:
    candidate_columns = [column for column in event_table.columns if column.startswith("candidate_")]
    rows: list[dict[str, Any]] = []
    shield_total = float(event_table["shield_next20_product_net_pnl"].sum())
    restore_total = float(event_table["stage75_next20_product_net_pnl"].sum())

    for column in candidate_columns:
        restore_mask = event_table[column] > 0
        candidate_pnl = event_table["shield_next20_product_net_pnl"].where(
            ~restore_mask,
            event_table["stage75_next20_product_net_pnl"],
        )
        value_vs_shield = candidate_pnl - event_table["shield_next20_product_net_pnl"]
        rows.append(
            {
                "candidate": column.replace("candidate_", ""),
                "restore_event_count": int(restore_mask.sum()),
                "restore_better_event_count": int((restore_mask & (event_table["restore_better_flag"] > 0)).sum()),
                "false_restore_event_count": int((restore_mask & (event_table["shield_better_flag"] > 0)).sum()),
                "candidate_next20_product_net_pnl": float(candidate_pnl.sum()),
                "always_shield_next20_product_net_pnl": shield_total,
                "always_restore_next20_product_net_pnl": restore_total,
                "candidate_value_vs_shield": float(value_vs_shield.sum()),
                "candidate_value_vs_always_restore": float(candidate_pnl.sum() - restore_total),
                "restore_hit_rate": float(
                    (restore_mask & (event_table["restore_better_flag"] > 0)).sum() / restore_mask.sum()
                )
                if restore_mask.any()
                else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["candidate_value_vs_shield", "restore_hit_rate"],
        ascending=[False, False],
    )


def build_period_summary(event_table: pd.DataFrame) -> pd.DataFrame:
    return (
        event_table.groupby(["period", "outcome_label"], as_index=False)
        .agg(
            event_count=("date", "count"),
            product_count=("product_vt_symbol", "nunique"),
            stage75_next20_product_net_pnl=("stage75_next20_product_net_pnl", "sum"),
            shield_next20_product_net_pnl=("shield_next20_product_net_pnl", "sum"),
            delta_next20_product_net_pnl=("delta_next20_product_net_pnl", "sum"),
            avg_shield_prev20_core_net_pnl=("shield_prev20_core_net_pnl", "mean"),
            avg_shield_prev20_core_positive_breadth=("shield_prev20_core_positive_breadth", "mean"),
            avg_shield_prev10_strategy_net_pnl=("shield_prev10_strategy_net_pnl", "mean"),
        )
        .sort_values(["period", "outcome_label"])
        .reset_index(drop=True)
    )


def build_summary(
    event_table: pd.DataFrame,
    candidate_summary: pd.DataFrame,
    period_summary: pd.DataFrame,
) -> dict[str, Any]:
    best_candidate = candidate_summary.iloc[0].to_dict() if not candidate_summary.empty else {}
    return {
        "model_tag": MODEL_TAG,
        "event_count": int(len(event_table)),
        "product_count": int(event_table["product_vt_symbol"].nunique()),
        "restore_better_event_count": int(event_table["restore_better_flag"].sum()),
        "shield_better_event_count": int(event_table["shield_better_flag"].sum()),
        "stage75_next20_product_net_pnl": float(event_table["stage75_next20_product_net_pnl"].sum()),
        "shield_next20_product_net_pnl": float(event_table["shield_next20_product_net_pnl"].sum()),
        "delta_next20_product_net_pnl": float(event_table["delta_next20_product_net_pnl"].sum()),
        "best_candidate": best_candidate,
        "candidate_summary": candidate_summary.replace({np.nan: None}).to_dict(orient="records"),
        "period_summary": period_summary.replace({np.nan: None}).to_dict(orient="records"),
    }


def build_report(
    summary: dict[str, Any],
    event_table: pd.DataFrame,
    candidate_summary: pd.DataFrame,
    period_summary: pd.DataFrame,
) -> str:
    best = summary.get("best_candidate", {})
    display_candidates = candidate_summary[
        [
            "candidate",
            "restore_event_count",
            "restore_better_event_count",
            "false_restore_event_count",
            "candidate_next20_product_net_pnl",
            "candidate_value_vs_shield",
            "candidate_value_vs_always_restore",
            "restore_hit_rate",
        ]
    ].copy()
    key_events = event_table[
        [
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
            "shield_prev20_core_net_pnl",
            "shield_prev20_core_positive_breadth",
            "shield_prev10_strategy_net_pnl",
            "candidate_core_prev20_pnl_and_breadth",
            "candidate_core_prev20_and_portfolio_prev10",
        ]
    ].sort_values("delta_next20_product_net_pnl")

    lines = [
        f"# {MODEL_TAG}",
        "",
        "## 目的",
        "",
        "- 本阶段只做归因诊断，不修改交易规则、不新增回测。",
        "- 核心问题：第78阶段压低风险后，哪些分歧事件应该恢复风险，哪些应该继续屏蔽。",
        "- 诊断原则：只使用事件发生前的核心池和组合状态，不使用事件后的收益作为特征；事件后的20日产品级净损益只作为标签和评分。",
        "",
        "## 总览",
        "",
        f"- 风险恢复分歧事件`{int(summary.get('event_count', 0))}`笔，涉及产品`{int(summary.get('product_count', 0))}`个。",
        f"- 事后看应该恢复的事件`{int(summary.get('restore_better_event_count', 0))}`笔，继续屏蔽更好的事件`{int(summary.get('shield_better_event_count', 0))}`笔。",
        f"- 始终恢复的20日产品级前瞻净损益`{_safe_float(summary.get('stage75_next20_product_net_pnl')):,.0f}`；始终屏蔽为`{_safe_float(summary.get('shield_next20_product_net_pnl')):,.0f}`；屏蔽相对差额`{_safe_float(summary.get('delta_next20_product_net_pnl')):,.0f}`。",
        "",
        "## 候选确认条件评分",
        "",
        to_markdown_table(display_candidates),
        "",
        "## 分阶段结构",
        "",
        to_markdown_table(period_summary),
        "",
        "## 关键事件",
        "",
        to_markdown_table(key_events.head(12)),
        "",
        "## 判断",
        "",
        f"- 当前事件级最优候选为`{best.get('candidate', '')}`，相对第78阶段事件级净值贡献`{_safe_float(best.get('candidate_value_vs_shield')):,.0f}`。",
        "- 这只是事件级归因，不等于可直接升级成策略；真正升级前仍需要写入策略后做多周期、起始年份、滑点压力和品种留出。",
        "- 如果候选条件只在2024-2025有效、但不能解释2026保护事件，就不能升级；如果能同时减少2024-2025机会成本且保留2026屏蔽，才值得进入策略层。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    eligibility = load_eligibility()
    divergence = _read_csv(STAGE80_DIVERGENCE_PATH)
    divergence["date"] = pd.to_datetime(divergence["date"]).dt.normalize()

    product_pivots = {
        "stage75": build_product_pivot(load_product_daily(STAGE75_PREFIX)),
        "shield": build_product_pivot(load_product_daily(SHIELD_PREFIX)),
    }
    strategy_daily = {
        "stage75": load_strategy_daily(STAGE75_PREFIX),
        "shield": load_strategy_daily(SHIELD_PREFIX),
    }

    event_table = attach_core_confirmation_metrics(divergence, eligibility, product_pivots, strategy_daily)
    event_table = add_candidate_flags(event_table)
    candidate_summary = build_candidate_summary(event_table)
    period_summary = build_period_summary(event_table)
    summary = build_summary(event_table, candidate_summary, period_summary)
    report = build_report(summary, event_table, candidate_summary, period_summary)

    event_table.to_csv(EVENT_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    candidate_summary.to_csv(CANDIDATE_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    period_summary.to_csv(PERIOD_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_OUTPUT_PATH.write_text(report, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"wrote {REPORT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
