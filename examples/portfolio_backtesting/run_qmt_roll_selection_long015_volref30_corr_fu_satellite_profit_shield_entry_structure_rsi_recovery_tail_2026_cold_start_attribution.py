from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from analyze_qmt_roll_ai_product_suitability_walkforward import product_from_contract
from qmt_universe import END_DT
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
    to_markdown_table,
)
from run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_backtest import (
    CAPITAL,
    EXPERIMENT_NAME as STAGE86_EXPERIMENT_NAME,
    build_strategy_overrides as build_stage86_strategy_overrides,
)
from run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_backtest import (
    EXPERIMENT_NAME as STAGE78_EXPERIMENT_NAME,
    build_strategy_overrides as build_stage78_strategy_overrides,
)
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

EXPERIMENT_TAG: str = (
    "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_"
    "entry_structure_rsi_recovery_tail_2026_cold_start_attribution"
)
STAGE78_PREFIX: str = (
    "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_since_2026_cold_start"
)
STAGE86_PREFIX: str = (
    "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_"
    "entry_structure_rsi_recovery_since_2026_cold_start"
)

TAIL_START: datetime = datetime(2026, 1, 1)
HORIZONS: tuple[int, ...] = (5, 10, 20, 40)

SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.csv"
PRODUCT_ATTRIBUTION_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_product_attribution.csv"
DAILY_ATTRIBUTION_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_daily_attribution.csv"
ENTRY_EVENT_COMPARISON_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_entry_event_comparison.csv"
RECOVERY_EVENTS_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_recovery_events.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_report.md"


StrategyBuilder = Callable[[], tuple[dict[str, Any], Path, Path]]


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


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def run_variant(
    *,
    variant: str,
    experiment_name: str,
    file_prefix: str,
    strategy_builder: StrategyBuilder,
    chart_title: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    strategy_overrides, universe_path, eligibility_path = strategy_builder()
    _, _, statistics = run_backtest(
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=strategy_overrides,
        analysis_start=TAIL_START,
        analysis_end=END_DT,
        capital=CAPITAL,
        save_artifacts=True,
        include_start_year_sweep=False,
        file_prefix=file_prefix,
        chart_title=chart_title,
    )
    row = build_summary_row(
        statistics,
        analysis_start=TAIL_START,
        analysis_end=END_DT,
        variant=variant,
        experiment_name=experiment_name,
        universe_path=str(universe_path),
        ai_product_pool_eligibility_path=str(eligibility_path),
        ai_product_pool_strategy=AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
        strategy_overrides_json=json.dumps(strategy_overrides, ensure_ascii=False, sort_keys=True),
        total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
        total_slippage=float(statistics.get("total_slippage", 0) or 0),
        total_commission=float(statistics.get("total_commission", 0) or 0),
        profit_days=int(statistics.get("profit_days", 0) or 0),
        loss_days=int(statistics.get("loss_days", 0) or 0),
    )
    artifacts = {
        "daily": str(OUTPUT_DIR / f"{file_prefix}_daily.csv"),
        "trades": str(OUTPUT_DIR / f"{file_prefix}_trades_2020_2026_04.csv"),
        "positions": str(OUTPUT_DIR / f"{file_prefix}_position_changes_2020_2026_04.csv"),
        "entry_risk": str(OUTPUT_DIR / f"{file_prefix}_entry_risk_diagnostics_2020_2026_04.csv"),
        "entry_candidates": str(OUTPUT_DIR / f"{file_prefix}_entry_candidate_snapshots_2020_2026_04.csv"),
    }
    return row, artifacts


def load_daily(path: Path, prefix: str) -> pd.DataFrame:
    df = _load_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    keep = ["date", "net_pnl", "balance", "drawdown", "ddpercent", "trade_count", "slippage"]
    df = df[keep].copy()
    for column in keep:
        if column != "date":
            df[column] = _numeric_series(df, column)
    return df.rename(columns={column: f"{prefix}_{column}" for column in keep if column != "date"})


def build_daily_attribution(stage78_daily: pd.DataFrame, stage86_daily: pd.DataFrame) -> pd.DataFrame:
    comparison = stage86_daily.merge(stage78_daily, on="date", how="outer").sort_values("date").reset_index(drop=True)
    comparison = comparison.fillna(0.0)
    for column in ("net_pnl", "balance", "drawdown", "ddpercent", "trade_count", "slippage"):
        comparison[f"delta_{column}"] = comparison[f"stage86_{column}"] - comparison[f"stage78_{column}"]
    return comparison


def load_product_daily(path: Path) -> pd.DataFrame:
    df = _load_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["product_vt_symbol"] = df["vt_symbol"].map(product_from_contract)
    for column in ("net_pnl", "trade_count", "slippage", "pos_change", "end_pos"):
        df[column] = _numeric_series(df, column)
    return (
        df.groupby(["date", "product_vt_symbol"], as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            trade_count=("trade_count", "sum"),
            slippage=("slippage", "sum"),
            abs_pos_change=("pos_change", lambda values: float(pd.to_numeric(values, errors="coerce").abs().sum())),
            abs_end_pos=("end_pos", lambda values: float(pd.to_numeric(values, errors="coerce").abs().sum())),
        )
        .sort_values(["date", "product_vt_symbol"])
        .reset_index(drop=True)
    )


def summarize_product_daily(product_daily: pd.DataFrame, prefix: str) -> pd.DataFrame:
    if product_daily.empty:
        return pd.DataFrame(columns=["product_vt_symbol"])
    grouped = (
        product_daily.groupby("product_vt_symbol", as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            trade_count=("trade_count", "sum"),
            slippage=("slippage", "sum"),
            abs_pos_change=("abs_pos_change", "sum"),
            active_days=("abs_end_pos", lambda values: int((values > 0.0).sum())),
            worst_day_net_pnl=("net_pnl", "min"),
            best_day_net_pnl=("net_pnl", "max"),
        )
    )
    return grouped.rename(columns={column: f"{prefix}_{column}" for column in grouped.columns if column != "product_vt_symbol"})


def build_product_attribution(stage78_product: pd.DataFrame, stage86_product: pd.DataFrame) -> pd.DataFrame:
    stage78 = summarize_product_daily(stage78_product, "stage78")
    stage86 = summarize_product_daily(stage86_product, "stage86")
    comparison = stage86.merge(stage78, on="product_vt_symbol", how="outer").fillna(0.0)
    for column in ("net_pnl", "trade_count", "slippage", "abs_pos_change", "active_days", "worst_day_net_pnl"):
        comparison[f"delta_{column}"] = comparison[f"stage86_{column}"] - comparison[f"stage78_{column}"]
    return comparison.sort_values(["delta_net_pnl", "product_vt_symbol"]).reset_index(drop=True)


def load_opened_entries(path: Path, variant: str) -> pd.DataFrame:
    df = _load_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    for column in (
        "is_opened",
        "selected_volume",
        "selected_volume_ungated",
        "risk_multiplier",
        "loss_streak",
        "estimated_equity",
        "active_positions_before",
        "portfolio_drawdown_pct",
        "ai_product_pool_rank",
        "selection_pairwise_rank",
        "rsi_value",
        "same_direction_correlation_max_corr",
        "streak_entry_structure_risk_recovery_applied",
        "streak_entry_structure_risk_recovery_rsi_value",
    ):
        df[column] = _numeric_series(df, column)
    opened = df[(df["candidate_status"].astype(str) == "opened") | (df["is_opened"] > 0.0)].copy()
    opened["variant"] = variant
    return opened


def build_entry_event_comparison(stage78_entries: pd.DataFrame, stage86_entries: pd.DataFrame) -> pd.DataFrame:
    key_columns = ["date", "product_vt_symbol", "contract_vt_symbol", "direction", "signal"]
    metric_columns = [
        "selected_volume",
        "selected_volume_ungated",
        "risk_multiplier",
        "loss_streak",
        "estimated_equity",
        "active_positions_before",
        "portfolio_drawdown_pct",
        "ai_product_pool_rank",
        "selection_pairwise_rank",
        "rsi_value",
        "same_direction_correlation_max_corr",
        "streak_entry_structure_risk_recovery_applied",
        "streak_entry_structure_risk_recovery_rsi_value",
    ]
    text_columns = ["streak_entry_structure_risk_recovery_reason"]

    def view(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=key_columns)
        keep = key_columns + [column for column in metric_columns + text_columns if column in df.columns]
        result = df[keep].copy()
        rename = {column: f"{prefix}_{column}" for column in metric_columns + text_columns if column in result.columns}
        return result.rename(columns=rename)

    comparison = view(stage86_entries, "stage86").merge(
        view(stage78_entries, "stage78"),
        on=key_columns,
        how="outer",
    )
    comparison = comparison.sort_values(key_columns).reset_index(drop=True)
    for column in metric_columns:
        left = f"stage86_{column}"
        right = f"stage78_{column}"
        if left not in comparison.columns:
            comparison[left] = 0.0
        if right not in comparison.columns:
            comparison[right] = 0.0
        comparison[left] = pd.to_numeric(comparison[left], errors="coerce").fillna(0.0)
        comparison[right] = pd.to_numeric(comparison[right], errors="coerce").fillna(0.0)
        comparison[f"delta_{column}"] = comparison[left] - comparison[right]
    for column in text_columns:
        for prefix in ("stage86", "stage78"):
            name = f"{prefix}_{column}"
            if name in comparison.columns:
                comparison[name] = comparison[name].fillna("")
    return comparison


def forward_product_pnl(product_daily: pd.DataFrame, product: str, event_date: pd.Timestamp, horizon: int) -> float:
    product_df = product_daily[
        (product_daily["product_vt_symbol"] == product)
        & (product_daily["date"] >= event_date)
    ].sort_values("date")
    if product_df.empty:
        return 0.0
    return float(product_df.head(horizon)["net_pnl"].sum())


def build_recovery_events(
    entry_comparison: pd.DataFrame,
    stage78_product_daily: pd.DataFrame,
    stage86_product_daily: pd.DataFrame,
) -> pd.DataFrame:
    if entry_comparison.empty:
        return pd.DataFrame()
    events = entry_comparison[entry_comparison["stage86_streak_entry_structure_risk_recovery_applied"] > 0.0].copy()
    if events.empty:
        return events
    records: list[dict[str, Any]] = []
    for row in events.to_dict("records"):
        event_date = pd.Timestamp(row["date"]).normalize()
        product = str(row["product_vt_symbol"])
        record = {
            "date": event_date.date().isoformat(),
            "product_vt_symbol": product,
            "contract_vt_symbol": row["contract_vt_symbol"],
            "direction": row["direction"],
            "signal": row["signal"],
            "stage86_selected_volume": _safe_float(row.get("stage86_selected_volume")),
            "stage78_selected_volume": _safe_float(row.get("stage78_selected_volume")),
            "delta_selected_volume": _safe_float(row.get("delta_selected_volume")),
            "stage86_risk_multiplier": _safe_float(row.get("stage86_risk_multiplier")),
            "stage78_risk_multiplier": _safe_float(row.get("stage78_risk_multiplier")),
            "delta_risk_multiplier": _safe_float(row.get("delta_risk_multiplier")),
            "stage86_loss_streak": _safe_float(row.get("stage86_loss_streak")),
            "stage78_loss_streak": _safe_float(row.get("stage78_loss_streak")),
            "stage86_rsi_value": _safe_float(row.get("stage86_rsi_value")),
            "stage86_ai_rank": _safe_float(row.get("stage86_ai_product_pool_rank")),
            "stage86_pairwise_rank": _safe_float(row.get("stage86_selection_pairwise_rank")),
            "stage86_same_direction_max_corr": _safe_float(row.get("stage86_same_direction_correlation_max_corr")),
            "stage86_recovery_reason": row.get("stage86_streak_entry_structure_risk_recovery_reason", ""),
        }
        for horizon in HORIZONS:
            stage86_pnl = forward_product_pnl(stage86_product_daily, product, event_date, horizon)
            stage78_pnl = forward_product_pnl(stage78_product_daily, product, event_date, horizon)
            record[f"stage86_product_pnl_{horizon}d"] = stage86_pnl
            record[f"stage78_product_pnl_{horizon}d"] = stage78_pnl
            record[f"delta_product_pnl_{horizon}d"] = stage86_pnl - stage78_pnl
        records.append(record)
    return pd.DataFrame(records)


def build_payload(
    summary: pd.DataFrame,
    product_attribution: pd.DataFrame,
    daily_attribution: pd.DataFrame,
    recovery_events: pd.DataFrame,
    artifacts: dict[str, Any],
) -> dict[str, Any]:
    summary_by_variant = {str(row["variant"]): row for row in summary.to_dict("records")}
    stage78 = summary_by_variant.get("stage78_profit_shield_streak", {})
    stage86 = summary_by_variant.get("stage86_entry_structure_rsi_recovery", {})
    delta = {
        "end_balance": _safe_float(stage86.get("end_balance")) - _safe_float(stage78.get("end_balance")),
        "total_return_pct": _safe_float(stage86.get("total_return_pct")) - _safe_float(stage78.get("total_return_pct")),
        "max_dd_percent": _safe_float(stage86.get("max_dd_percent")) - _safe_float(stage78.get("max_dd_percent")),
        "sharpe_ratio": _safe_float(stage86.get("sharpe_ratio")) - _safe_float(stage78.get("sharpe_ratio")),
        "total_trade_count": int(_safe_float(stage86.get("total_trade_count")) - _safe_float(stage78.get("total_trade_count"))),
        "total_slippage": _safe_float(stage86.get("total_slippage")) - _safe_float(stage78.get("total_slippage")),
    }
    worst_products = product_attribution.head(10).to_dict("records")
    worst_days = daily_attribution.sort_values("delta_net_pnl").head(10).to_dict("records")
    return {
        "experiment_tag": EXPERIMENT_TAG,
        "analysis_start": TAIL_START.date().isoformat(),
        "analysis_end": END_DT.date().isoformat(),
        "capital": CAPITAL,
        "base_risk_ratio": BASE_RISK_RATIO,
        "summary": summary.to_dict("records"),
        "delta_stage86_vs_stage78": delta,
        "recovery_event_count": int(len(recovery_events)),
        "recovery_events": recovery_events.to_dict("records"),
        "worst_products_by_delta": worst_products,
        "worst_days_by_delta": worst_days,
        "artifacts": artifacts,
    }


def build_report(
    summary: pd.DataFrame,
    product_attribution: pd.DataFrame,
    daily_attribution: pd.DataFrame,
    entry_comparison: pd.DataFrame,
    recovery_events: pd.DataFrame,
    payload: dict[str, Any],
) -> str:
    delta = payload["delta_stage86_vs_stage78"]
    summary_view = summary[
        [
            "variant",
            "end_balance",
            "total_return_pct",
            "max_dd_percent",
            "sharpe_ratio",
            "total_slippage",
            "total_trade_count",
        ]
    ].copy()
    product_view = product_attribution[
        [
            "product_vt_symbol",
            "stage86_net_pnl",
            "stage78_net_pnl",
            "delta_net_pnl",
            "stage86_trade_count",
            "stage78_trade_count",
            "delta_trade_count",
            "stage86_abs_pos_change",
            "stage78_abs_pos_change",
            "delta_abs_pos_change",
        ]
    ].head(12)
    worst_day_view = daily_attribution[
        [
            "date",
            "stage86_net_pnl",
            "stage78_net_pnl",
            "delta_net_pnl",
            "stage86_balance",
            "stage78_balance",
            "delta_balance",
            "stage86_ddpercent",
            "stage78_ddpercent",
            "delta_ddpercent",
        ]
    ].sort_values("delta_net_pnl").head(12)
    recovery_view_columns = [
        "date",
        "product_vt_symbol",
        "contract_vt_symbol",
        "direction",
        "signal",
        "stage86_selected_volume",
        "stage78_selected_volume",
        "delta_selected_volume",
        "stage86_risk_multiplier",
        "stage78_risk_multiplier",
        "stage86_loss_streak",
        "stage86_rsi_value",
        "stage86_ai_rank",
        "stage86_pairwise_rank",
        "delta_product_pnl_5d",
        "delta_product_pnl_10d",
        "delta_product_pnl_20d",
        "delta_product_pnl_40d",
    ]
    recovery_view = recovery_events[recovery_view_columns] if not recovery_events.empty else recovery_events

    lines = [
        "# 第86阶段2026冷启动尾部归因",
        "",
        "## 设计",
        "",
        "- 重跑第78阶段和第86阶段的`since_2026`冷启动版本，并保存交易、持仓、入场候选与风险诊断明细。",
        "- 不新增策略参数，不扫描阈值，只解释第86相对第78在2026冷启动中为何恶化。",
        "- 归因层次为组合指标、产品净损益、最差日、以及第86恢复风险触发事件。",
        "",
        "## 组合对比",
        "",
        to_markdown_table(summary_view),
        "",
        "## 第86相对第78差额",
        "",
        f"- 期末权益差额：`{_safe_float(delta.get('end_balance')):,.0f}`",
        f"- 总收益差额：`{_safe_float(delta.get('total_return_pct')):.4f}`",
        f"- 最大回撤差额：`{_safe_float(delta.get('max_dd_percent')):.4f}`",
        f"- Sharpe差额：`{_safe_float(delta.get('sharpe_ratio')):.4f}`",
        f"- 总滑点差额：`{_safe_float(delta.get('total_slippage')):,.0f}`",
        f"- 总交易次数差额：`{int(_safe_float(delta.get('total_trade_count'))):,}`",
        "",
        "## 产品归因：第86相对第78最差产品",
        "",
        to_markdown_table(product_view),
        "",
        "## 最差日归因",
        "",
        to_markdown_table(worst_day_view),
        "",
        "## 第86恢复风险触发事件",
        "",
        to_markdown_table(recovery_view) if not recovery_view.empty else "无第86恢复风险触发事件。",
        "",
        "## 判断",
        "",
        "- 如果第86的损害集中在少数恢复风险事件或单一产品，下一步应做冷启动保护或触发后暂停，而不是修改RSI阈值。",
        "- 如果损害来自全市场普遍变差，则第86的恢复机制不应保留。",
        "- 本阶段只做归因，不给策略升级结论；策略变更必须建立在归因结果上。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    stage78_row, stage78_artifacts = run_variant(
        variant="stage78_profit_shield_streak",
        experiment_name=STAGE78_EXPERIMENT_NAME,
        file_prefix=STAGE78_PREFIX,
        strategy_builder=build_stage78_strategy_overrides,
        chart_title="QMT Roll Stage78 Profit Shield Streak Since 2026 Cold Start",
    )
    stage86_row, stage86_artifacts = run_variant(
        variant="stage86_entry_structure_rsi_recovery",
        experiment_name=STAGE86_EXPERIMENT_NAME,
        file_prefix=STAGE86_PREFIX,
        strategy_builder=build_stage86_strategy_overrides,
        chart_title="QMT Roll Stage86 Entry Structure RSI Recovery Since 2026 Cold Start",
    )

    summary = pd.DataFrame([stage78_row, stage86_row])

    stage78_daily = load_daily(Path(stage78_artifacts["daily"]), "stage78")
    stage86_daily = load_daily(Path(stage86_artifacts["daily"]), "stage86")
    daily_attribution = build_daily_attribution(stage78_daily, stage86_daily)

    stage78_product_daily = load_product_daily(Path(stage78_artifacts["positions"]))
    stage86_product_daily = load_product_daily(Path(stage86_artifacts["positions"]))
    product_attribution = build_product_attribution(stage78_product_daily, stage86_product_daily)

    stage78_entries = load_opened_entries(Path(stage78_artifacts["entry_candidates"]), "stage78")
    stage86_entries = load_opened_entries(Path(stage86_artifacts["entry_candidates"]), "stage86")
    entry_comparison = build_entry_event_comparison(stage78_entries, stage86_entries)
    recovery_events = build_recovery_events(entry_comparison, stage78_product_daily, stage86_product_daily)

    artifacts: dict[str, Any] = {
        "summary_csv": str(SUMMARY_CSV_PATH),
        "product_attribution_csv": str(PRODUCT_ATTRIBUTION_CSV_PATH),
        "daily_attribution_csv": str(DAILY_ATTRIBUTION_CSV_PATH),
        "entry_event_comparison_csv": str(ENTRY_EVENT_COMPARISON_CSV_PATH),
        "recovery_events_csv": str(RECOVERY_EVENTS_CSV_PATH),
        "summary_json": str(SUMMARY_JSON_PATH),
        "report": str(REPORT_PATH),
        "stage78": stage78_artifacts,
        "stage86": stage86_artifacts,
    }
    payload = build_payload(summary, product_attribution, daily_attribution, recovery_events, artifacts)
    report = build_report(summary, product_attribution, daily_attribution, entry_comparison, recovery_events, payload)

    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    product_attribution.to_csv(PRODUCT_ATTRIBUTION_CSV_PATH, index=False, encoding="utf-8-sig")
    daily_attribution.to_csv(DAILY_ATTRIBUTION_CSV_PATH, index=False, encoding="utf-8-sig")
    entry_comparison.to_csv(ENTRY_EVENT_COMPARISON_CSV_PATH, index=False, encoding="utf-8-sig")
    recovery_events.to_csv(RECOVERY_EVENTS_CSV_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    REPORT_PATH.write_text(report, encoding="utf-8")

    print(f"[stage86-tail-2026-cold-start] summary csv: {SUMMARY_CSV_PATH}")
    print(f"[stage86-tail-2026-cold-start] product attribution csv: {PRODUCT_ATTRIBUTION_CSV_PATH}")
    print(f"[stage86-tail-2026-cold-start] daily attribution csv: {DAILY_ATTRIBUTION_CSV_PATH}")
    print(f"[stage86-tail-2026-cold-start] entry comparison csv: {ENTRY_EVENT_COMPARISON_CSV_PATH}")
    print(f"[stage86-tail-2026-cold-start] recovery events csv: {RECOVERY_EVENTS_CSV_PATH}")
    print(f"[stage86-tail-2026-cold-start] summary json: {SUMMARY_JSON_PATH}")
    print(f"[stage86-tail-2026-cold-start] report: {REPORT_PATH}")
    print(summary.to_string(index=False))
    if not recovery_events.empty:
        print(recovery_events.to_string(index=False))


if __name__ == "__main__":
    main()
