from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_ai_product_suitability_walkforward import product_from_contract
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "portfolio_risk_state_attribution_v1"
OUTPUT_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_portfolio_risk_state_attribution"

STAGE75_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_fu_satellite_post_signal_formal"
SHIELD_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_formal"

HORIZONS: tuple[int, ...] = (5, 10, 20)
SATELLITE_PRODUCTS: frozenset[str] = frozenset({"fu.SHFE"})

PERIODS: tuple[tuple[str, str, str], ...] = (
    ("pre_ai_2020_2021", "2020-01-01", "2021-12-31"),
    ("early_ai_2022_2023", "2022-01-01", "2023-12-31"),
    ("trend_rich_2024_2025", "2024-01-01", "2025-12-31"),
    ("latest_2026", "2026-01-01", "2026-04-30"),
)

ENTRY_COLUMNS: tuple[str, ...] = (
    "date",
    "product_vt_symbol",
    "contract_vt_symbol",
    "entry_context",
    "direction",
    "signal",
    "candidate_status",
    "skip_reason",
    "estimated_equity",
    "risk_ratio",
    "risk_multiplier",
    "selected_volume",
    "selected_volume_ungated",
    "portfolio_drawdown_pct",
    "same_direction_correlation_active_count",
    "same_direction_correlation_max_corr",
    "same_direction_correlation_avg_corr",
    "selection_pairwise_score",
    "selection_pairwise_rank",
    "selection_pairwise_volume_tilt_applied",
    "selection_pairwise_volume_tilt_multiplier",
    "ai_product_pool_allowed",
    "ai_product_pool_signal_date",
    "ai_product_pool_score",
    "ai_product_pool_rank",
    "ai_product_pool_top_n",
    "active_positions_before",
    "remaining_position_slots",
    "bullish_alignment",
    "bearish_alignment",
    "breakout",
    "rsi_value",
    "is_opened",
    "loss_streak",
    "profit_recovery_streak",
)

POSITION_COLUMNS: tuple[str, ...] = (
    "date",
    "vt_symbol",
    "pos_change",
    "trade_count",
    "slippage",
    "holding_pnl",
    "trading_pnl",
    "total_pnl",
    "net_pnl",
)

DAILY_COLUMNS: tuple[str, ...] = (
    "date",
    "trade_count",
    "slippage",
    "net_pnl",
    "balance",
    "drawdown",
    "ddpercent",
)

EVENT_TABLE_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_table_{MODEL_TAG}.csv"
STATE_BUCKET_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_bucket_summary_{MODEL_TAG}.csv"
PAIR_COMPARISON_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage75_vs_stage78_pair_comparison_{MODEL_TAG}.csv"
RISK_RECOVERY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_risk_recovery_divergence_{MODEL_TAG}.csv"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _numeric_series(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(default)


def _read_csv(path: Path, *, usecols: tuple[str, ...] | None = None) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    if usecols is None:
        return pd.read_csv(path)
    wanted = set(usecols)
    return pd.read_csv(path, usecols=lambda column: column in wanted)


def _period_label(date: pd.Timestamp) -> str:
    for label, start, end in PERIODS:
        if pd.Timestamp(start) <= date <= pd.Timestamp(end):
            return label
    return "other"


def _loss_streak_bucket(value: float) -> str:
    if value <= 0:
        return "loss_0"
    if value <= 2:
        return "loss_1_2"
    if value <= 4:
        return "loss_3_4"
    return "loss_5_plus"


def _drawdown_bucket(value: float) -> str:
    drawdown = abs(float(value))
    if drawdown < 0.05:
        return "dd_lt_5pct"
    if drawdown < 0.15:
        return "dd_5_15pct"
    if drawdown < 0.25:
        return "dd_15_25pct"
    return "dd_ge_25pct"


def _crowding_bucket(active_count: float, max_corr: float) -> str:
    if active_count >= 4 or max_corr >= 0.75:
        return "crowding_high"
    if active_count >= 2 or max_corr >= 0.5:
        return "crowding_mid"
    return "crowding_low"


def _risk_bucket(value: float) -> str:
    if value >= 0.99:
        return "risk_full"
    if value >= 0.5:
        return "risk_mid"
    return "risk_low"


def _forward_sum(
    grouped_daily: dict[str, pd.DataFrame],
    product: str,
    date: pd.Timestamp,
    column: str,
    horizon: int,
) -> float:
    product_daily = grouped_daily.get(product)
    if product_daily is None or product_daily.empty:
        return 0.0
    dates = product_daily["date"].to_numpy(dtype="datetime64[ns]")
    idx = int(np.searchsorted(dates, np.datetime64(date), side="left"))
    if idx >= len(product_daily):
        return 0.0
    return float(product_daily.iloc[idx : idx + horizon][column].sum())


def _forward_strategy_sum(daily: pd.DataFrame, date: pd.Timestamp, column: str, horizon: int) -> float:
    dates = daily["date"].to_numpy(dtype="datetime64[ns]")
    idx = int(np.searchsorted(dates, np.datetime64(date), side="left"))
    if idx >= len(daily):
        return 0.0
    return float(daily.iloc[idx : idx + horizon][column].sum())


def load_product_daily(prefix: str) -> pd.DataFrame:
    path = OUTPUT_DIR / f"{prefix}_position_changes_2020_2026_04.csv"
    df = _read_csv(path, usecols=POSITION_COLUMNS)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["product_vt_symbol"] = df["vt_symbol"].map(product_from_contract)
    for column in POSITION_COLUMNS:
        if column not in {"date", "vt_symbol"}:
            df[column] = _numeric_series(df, column)
    return (
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
        .sort_values(["product_vt_symbol", "date"])
        .reset_index(drop=True)
    )


def load_strategy_daily(prefix: str) -> pd.DataFrame:
    path = OUTPUT_DIR / f"{prefix}_daily.csv"
    df = _read_csv(path, usecols=DAILY_COLUMNS)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    for column in DAILY_COLUMNS:
        if column != "date":
            df[column] = _numeric_series(df, column)
    return df.sort_values("date").reset_index(drop=True)


def load_opened_entries(prefix: str, variant: str) -> pd.DataFrame:
    path = OUTPUT_DIR / f"{prefix}_entry_candidate_snapshots_2020_2026_04.csv"
    df = _read_csv(path, usecols=ENTRY_COLUMNS)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    for column in ENTRY_COLUMNS:
        if column not in {
            "date",
            "product_vt_symbol",
            "contract_vt_symbol",
            "entry_context",
            "direction",
            "signal",
            "candidate_status",
            "skip_reason",
            "ai_product_pool_signal_date",
        }:
            df[column] = _numeric_series(df, column)
    opened = df[(df["candidate_status"].astype(str) == "opened") | (df["is_opened"] > 0.0)].copy()
    opened["variant"] = variant
    opened["period"] = opened["date"].map(_period_label)
    opened["year"] = opened["date"].dt.year
    opened["is_satellite_product"] = opened["product_vt_symbol"].isin(SATELLITE_PRODUCTS).astype("int64")
    opened["loss_streak_bucket"] = opened["loss_streak"].map(_loss_streak_bucket)
    opened["drawdown_bucket"] = opened["portfolio_drawdown_pct"].map(_drawdown_bucket)
    opened["crowding_bucket"] = opened.apply(
        lambda row: _crowding_bucket(
            _safe_float(row.get("same_direction_correlation_active_count")),
            _safe_float(row.get("same_direction_correlation_max_corr")),
        ),
        axis=1,
    )
    opened["risk_bucket"] = opened["risk_multiplier"].map(_risk_bucket)
    opened["state_key"] = (
        opened["loss_streak_bucket"]
        + "|"
        + opened["drawdown_bucket"]
        + "|"
        + opened["crowding_bucket"]
        + "|"
        + opened["risk_bucket"]
    )
    return opened.sort_values(["date", "product_vt_symbol", "direction", "signal"]).reset_index(drop=True)


def attach_forward_outcomes(
    entries: pd.DataFrame,
    product_daily: pd.DataFrame,
    strategy_daily: pd.DataFrame,
) -> pd.DataFrame:
    grouped = {
        product: group.sort_values("date").reset_index(drop=True)
        for product, group in product_daily.groupby("product_vt_symbol")
    }
    result = entries.copy()
    for horizon in HORIZONS:
        result[f"next{horizon}_product_net_pnl"] = [
            _forward_sum(grouped, row.product_vt_symbol, row.date, "net_pnl", horizon)
            for row in result.itertuples(index=False)
        ]
        result[f"next{horizon}_product_abs_pos_change"] = [
            _forward_sum(grouped, row.product_vt_symbol, row.date, "abs_pos_change", horizon)
            for row in result.itertuples(index=False)
        ]
        result[f"next{horizon}_strategy_net_pnl"] = [
            _forward_strategy_sum(strategy_daily, row.date, "net_pnl", horizon)
            for row in result.itertuples(index=False)
        ]
    result["next20_product_loss_flag"] = (result["next20_product_net_pnl"] < 0.0).astype("int64")
    result["next20_strategy_loss_flag"] = (result["next20_strategy_net_pnl"] < 0.0).astype("int64")
    return result


def build_state_bucket_summary(event_table: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        event_table.groupby(["variant", "period", "state_key"], as_index=False)
        .agg(
            event_count=("date", "count"),
            product_count=("product_vt_symbol", "nunique"),
            satellite_event_count=("is_satellite_product", "sum"),
            avg_risk_multiplier=("risk_multiplier", "mean"),
            avg_loss_streak=("loss_streak", "mean"),
            avg_drawdown_pct=("portfolio_drawdown_pct", "mean"),
            avg_correlation_max=("same_direction_correlation_max_corr", "mean"),
            total_selected_volume=("selected_volume", "sum"),
            next5_product_net_pnl=("next5_product_net_pnl", "sum"),
            next10_product_net_pnl=("next10_product_net_pnl", "sum"),
            next20_product_net_pnl=("next20_product_net_pnl", "sum"),
            avg_next20_product_net_pnl=("next20_product_net_pnl", "mean"),
            next20_loss_rate=("next20_product_loss_flag", "mean"),
            next20_strategy_net_pnl=("next20_strategy_net_pnl", "sum"),
        )
        .sort_values(["variant", "period", "next20_product_net_pnl", "event_count"])
        .reset_index(drop=True)
    )
    return grouped


def build_pair_comparison(event_table: pd.DataFrame) -> pd.DataFrame:
    key_columns = ["date", "product_vt_symbol", "contract_vt_symbol", "direction", "signal"]
    metric_columns = [
        "period",
        "selected_volume",
        "selected_volume_ungated",
        "risk_multiplier",
        "loss_streak",
        "portfolio_drawdown_pct",
        "same_direction_correlation_active_count",
        "same_direction_correlation_max_corr",
        "active_positions_before",
        "ai_product_pool_rank",
        "selection_pairwise_rank",
        "next5_product_net_pnl",
        "next10_product_net_pnl",
        "next20_product_net_pnl",
        "next20_strategy_net_pnl",
    ]

    def variant_view(variant: str, prefix: str) -> pd.DataFrame:
        df = event_table[event_table["variant"] == variant].copy()
        keep = key_columns + metric_columns
        return df[keep].rename(columns={column: f"{prefix}_{column}" for column in metric_columns})

    comparison = variant_view("stage78_profit_shield", "shield").merge(
        variant_view("stage75_post_signal", "stage75"),
        on=key_columns,
        how="outer",
    )
    comparison["period"] = comparison["shield_period"].where(comparison["shield_period"].notna(), comparison["stage75_period"])
    numeric_metric_columns = [column for column in metric_columns if column != "period"]
    for column in numeric_metric_columns:
        comparison[f"shield_{column}"] = _numeric_series(comparison, f"shield_{column}")
        comparison[f"stage75_{column}"] = _numeric_series(comparison, f"stage75_{column}")
        comparison[f"delta_{column}"] = comparison[f"shield_{column}"] - comparison[f"stage75_{column}"]
    comparison["is_satellite_product"] = comparison["product_vt_symbol"].isin(SATELLITE_PRODUCTS).astype("int64")
    comparison["stage75_only_flag"] = (comparison["shield_period"].isna() & comparison["stage75_period"].notna()).astype("int64")
    comparison["shield_only_flag"] = (comparison["stage75_period"].isna() & comparison["shield_period"].notna()).astype("int64")
    comparison["risk_recovery_divergence_flag"] = (
        (comparison["stage75_risk_multiplier"] > comparison["shield_risk_multiplier"])
        & (comparison["stage75_selected_volume"] > comparison["shield_selected_volume"])
    ).astype("int64")
    return comparison.sort_values(["date", "product_vt_symbol", "direction", "signal"]).reset_index(drop=True)


def build_risk_recovery_divergence(pair_comparison: pd.DataFrame) -> pd.DataFrame:
    divergence = pair_comparison[pair_comparison["risk_recovery_divergence_flag"] > 0].copy()
    if divergence.empty:
        return divergence
    divergence["stage75_extra_volume"] = divergence["stage75_selected_volume"] - divergence["shield_selected_volume"]
    divergence["stage75_extra_risk_multiplier"] = divergence["stage75_risk_multiplier"] - divergence["shield_risk_multiplier"]
    return divergence.sort_values(["delta_next20_product_net_pnl", "date"]).reset_index(drop=True)


def build_summary(
    event_table: pd.DataFrame,
    state_bucket_summary: pd.DataFrame,
    pair_comparison: pd.DataFrame,
    divergence: pd.DataFrame,
) -> dict[str, Any]:
    variant_summary: dict[str, Any] = {}
    for variant, group in event_table.groupby("variant"):
        variant_summary[variant] = {
            "event_count": int(len(group)),
            "product_count": int(group["product_vt_symbol"].nunique()),
            "satellite_event_count": int(group["is_satellite_product"].sum()),
            "avg_risk_multiplier": float(group["risk_multiplier"].mean()),
            "avg_loss_streak": float(group["loss_streak"].mean()),
            "next20_product_net_pnl": float(group["next20_product_net_pnl"].sum()),
            "next20_loss_rate": float(group["next20_product_loss_flag"].mean()),
        }

    divergence_summary = {
        "event_count": int(len(divergence)),
        "product_count": int(divergence["product_vt_symbol"].nunique()) if not divergence.empty else 0,
        "stage75_selected_volume": float(divergence["stage75_selected_volume"].sum()) if not divergence.empty else 0.0,
        "shield_selected_volume": float(divergence["shield_selected_volume"].sum()) if not divergence.empty else 0.0,
        "stage75_extra_volume": float(divergence["stage75_extra_volume"].sum()) if not divergence.empty else 0.0,
        "stage75_next20_product_net_pnl": float(divergence["stage75_next20_product_net_pnl"].sum()) if not divergence.empty else 0.0,
        "shield_next20_product_net_pnl": float(divergence["shield_next20_product_net_pnl"].sum()) if not divergence.empty else 0.0,
        "delta_next20_product_net_pnl": float(divergence["delta_next20_product_net_pnl"].sum()) if not divergence.empty else 0.0,
    }

    period_divergence = []
    if not divergence.empty:
        for row in (
            divergence.groupby("period", as_index=False)
            .agg(
                event_count=("date", "count"),
                stage75_extra_volume=("stage75_extra_volume", "sum"),
                stage75_next20_product_net_pnl=("stage75_next20_product_net_pnl", "sum"),
                shield_next20_product_net_pnl=("shield_next20_product_net_pnl", "sum"),
                delta_next20_product_net_pnl=("delta_next20_product_net_pnl", "sum"),
            )
            .sort_values("period")
            .itertuples(index=False)
        ):
            period_divergence.append(row._asdict())

    worst_state_buckets = (
        state_bucket_summary.sort_values("next20_product_net_pnl")
        .head(10)
        .replace({np.nan: None})
        .to_dict(orient="records")
    )

    return {
        "model_tag": MODEL_TAG,
        "horizons": list(HORIZONS),
        "variant_summary": variant_summary,
        "pair_event_count": int(len(pair_comparison)),
        "risk_recovery_divergence": divergence_summary,
        "period_risk_recovery_divergence": period_divergence,
        "worst_state_buckets": worst_state_buckets,
    }


def build_report(
    summary: dict[str, Any],
    state_bucket_summary: pd.DataFrame,
    divergence: pd.DataFrame,
) -> str:
    stage75 = summary["variant_summary"].get("stage75_post_signal", {})
    shield = summary["variant_summary"].get("stage78_profit_shield", {})
    divergence_summary = summary["risk_recovery_divergence"]

    divergence_columns = [
        "date",
        "period",
        "product_vt_symbol",
        "direction",
        "signal",
        "stage75_selected_volume",
        "shield_selected_volume",
        "stage75_risk_multiplier",
        "shield_risk_multiplier",
        "stage75_loss_streak",
        "shield_loss_streak",
        "stage75_next20_product_net_pnl",
        "shield_next20_product_net_pnl",
        "delta_next20_product_net_pnl",
    ]
    divergence_cost = divergence.sort_values("delta_next20_product_net_pnl").head(8).copy()
    divergence_protection = divergence.sort_values("delta_next20_product_net_pnl", ascending=False).head(8).copy()
    if not divergence_cost.empty:
        divergence_cost = divergence_cost[divergence_columns]
    if not divergence_protection.empty:
        divergence_protection = divergence_protection[divergence_columns]

    if divergence.empty:
        period_divergence = pd.DataFrame()
    else:
        period_divergence = (
            divergence.groupby("period", as_index=False)
            .agg(
                event_count=("date", "count"),
                product_count=("product_vt_symbol", "nunique"),
                stage75_extra_volume=("stage75_extra_volume", "sum"),
                stage75_next20_product_net_pnl=("stage75_next20_product_net_pnl", "sum"),
                shield_next20_product_net_pnl=("shield_next20_product_net_pnl", "sum"),
                delta_next20_product_net_pnl=("delta_next20_product_net_pnl", "sum"),
            )
            .sort_values("period")
        )

    worst_buckets = (
        state_bucket_summary[state_bucket_summary["event_count"] >= 2]
        .sort_values("next20_product_net_pnl")
        .head(12)
    )
    worst_buckets = worst_buckets.copy()
    if not worst_buckets.empty:
        worst_buckets["state_key"] = worst_buckets["state_key"].astype(str).str.replace("|", " / ", regex=False)
    worst_bucket_columns = [
        "variant",
        "period",
        "state_key",
        "event_count",
        "product_count",
        "avg_risk_multiplier",
        "avg_loss_streak",
        "avg_drawdown_pct",
        "total_selected_volume",
        "next20_product_net_pnl",
        "avg_next20_product_net_pnl",
        "next20_loss_rate",
    ]

    lines = [
        f"# {MODEL_TAG}",
        "",
        "## 结论",
        "",
        "- 本阶段只做诊断，不修改策略规则，避免在第78阶段基础上继续围绕单个品种过拟合。",
        f"- 第75阶段开仓事件数`{int(stage75.get('event_count', 0))}`，第78阶段开仓事件数`{int(shield.get('event_count', 0))}`。",
        f"- 风险恢复分歧事件数`{int(divergence_summary.get('event_count', 0))}`，第75阶段相对第78阶段额外手数`{_safe_float(divergence_summary.get('stage75_extra_volume')):,.0f}`。",
        f"- 分歧事件20日产品级前瞻净损益：第75阶段`{_safe_float(divergence_summary.get('stage75_next20_product_net_pnl')):,.0f}`，第78阶段`{_safe_float(divergence_summary.get('shield_next20_product_net_pnl')):,.0f}`，差额`{_safe_float(divergence_summary.get('delta_next20_product_net_pnl')):,.0f}`。",
        "- 如果分歧事件集中在少数年份或单一品种，本阶段不能直接推出新规则；如果跨周期、跨品种重复出现，才值得抽象成统一风险恢复规则。",
        "",
        "## 最差状态桶",
        "",
        to_markdown_table(worst_buckets[worst_bucket_columns]),
        "",
        "## 分歧阶段分布",
        "",
        to_markdown_table(period_divergence),
        "",
        "## 第78阶段代价最大的分歧",
        "",
        to_markdown_table(divergence_cost),
        "",
        "## 第78阶段保护最有效的分歧",
        "",
        to_markdown_table(divergence_protection),
        "",
        "## 下一步规则边界",
        "",
        "- 不能再写`fu.SHFE`专属补丁。",
        "- 候选方向应是：低权重卫星盈利不能单独恢复组合风险状态，必须由核心池或组合权益共同确认。",
        "- 规则验证必须继续使用起始年份、多周期、滑点压力和品种留出。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    stage75_product_daily = load_product_daily(STAGE75_PREFIX)
    shield_product_daily = load_product_daily(SHIELD_PREFIX)
    stage75_daily = load_strategy_daily(STAGE75_PREFIX)
    shield_daily = load_strategy_daily(SHIELD_PREFIX)

    stage75_entries = attach_forward_outcomes(
        load_opened_entries(STAGE75_PREFIX, "stage75_post_signal"),
        stage75_product_daily,
        stage75_daily,
    )
    shield_entries = attach_forward_outcomes(
        load_opened_entries(SHIELD_PREFIX, "stage78_profit_shield"),
        shield_product_daily,
        shield_daily,
    )
    event_table = pd.concat([stage75_entries, shield_entries], ignore_index=True).sort_values(
        ["variant", "date", "product_vt_symbol", "direction", "signal"]
    )

    state_bucket_summary = build_state_bucket_summary(event_table)
    pair_comparison = build_pair_comparison(event_table)
    divergence = build_risk_recovery_divergence(pair_comparison)
    summary = build_summary(event_table, state_bucket_summary, pair_comparison, divergence)
    report = build_report(summary, state_bucket_summary, divergence)

    event_table.to_csv(EVENT_TABLE_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    state_bucket_summary.to_csv(STATE_BUCKET_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    pair_comparison.to_csv(PAIR_COMPARISON_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    divergence.to_csv(RISK_RECOVERY_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_OUTPUT_PATH.write_text(report, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"wrote {REPORT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
