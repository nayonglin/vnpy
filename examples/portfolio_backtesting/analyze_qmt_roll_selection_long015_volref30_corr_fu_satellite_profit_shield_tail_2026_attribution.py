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

MODEL_TAG: str = "profit_shield_tail_2026_attribution_v1"
OUTPUT_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_tail_2026_attribution"

STAGE75_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_fu_satellite_post_signal_formal"
SHIELD_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_formal"

TAIL_START: pd.Timestamp = pd.Timestamp("2026-01-01")
KEY_PRODUCT: str = "SH.CZCE"
KEY_EVENT_DATES: tuple[str, ...] = ("2026-02-06", "2026-03-02")

STAGE75_DAILY_PATH: Path = OUTPUT_DIR / f"{STAGE75_PREFIX}_daily.csv"
SHIELD_DAILY_PATH: Path = OUTPUT_DIR / f"{SHIELD_PREFIX}_daily.csv"
STAGE75_POSITION_CHANGES_PATH: Path = OUTPUT_DIR / f"{STAGE75_PREFIX}_position_changes_2020_2026_04.csv"
SHIELD_POSITION_CHANGES_PATH: Path = OUTPUT_DIR / f"{SHIELD_PREFIX}_position_changes_2020_2026_04.csv"
STAGE75_ENTRY_SNAPSHOTS_PATH: Path = OUTPUT_DIR / f"{STAGE75_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv"
SHIELD_ENTRY_SNAPSHOTS_PATH: Path = OUTPUT_DIR / f"{SHIELD_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv"

PRODUCT_COMPARISON_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_comparison_{MODEL_TAG}.csv"
ENTRY_EVENT_COMPARISON_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_event_comparison_{MODEL_TAG}.csv"
KEY_EVENTS_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_key_events_{MODEL_TAG}.csv"
DAILY_COMPARISON_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_comparison_{MODEL_TAG}.csv"
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


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def load_daily(path: Path) -> pd.DataFrame:
    df = _load_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    for column in ("net_pnl", "balance", "drawdown", "ddpercent", "trade_count", "slippage"):
        df[column] = _numeric_series(df, column)
    return df.sort_values("date").reset_index(drop=True)


def summarize_period(daily: pd.DataFrame) -> dict[str, Any]:
    tail = daily[daily["date"] >= TAIL_START].copy()
    previous = daily[daily["date"] < TAIL_START].tail(1)
    start_balance = float(previous["balance"].iloc[0]) if not previous.empty else 200_000.0
    end_balance = float(tail["balance"].iloc[-1]) if not tail.empty else start_balance
    balances = pd.concat([pd.Series([start_balance]), tail["balance"].reset_index(drop=True)], ignore_index=True)
    high_water = balances.cummax()
    drawdown_pct = (balances - high_water) / high_water.replace(0.0, np.nan) * 100.0
    return {
        "start_balance": start_balance,
        "end_balance": end_balance,
        "net_pnl": float(tail["net_pnl"].sum()) if not tail.empty else 0.0,
        "return_pct": (end_balance / start_balance - 1.0) * 100.0 if start_balance else 0.0,
        "max_dd_percent": float(drawdown_pct.min()) if drawdown_pct.notna().any() else 0.0,
        "trade_count": int(round(float(tail["trade_count"].sum()))) if not tail.empty else 0,
        "slippage": float(tail["slippage"].sum()) if not tail.empty else 0.0,
    }


def load_product_daily(path: Path) -> pd.DataFrame:
    df = _load_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["product_vt_symbol"] = df["vt_symbol"].map(product_from_contract)
    for column in ("net_pnl", "trade_count", "slippage", "pos_change", "end_pos"):
        df[column] = _numeric_series(df, column)
    return (
        df[df["date"] >= TAIL_START]
        .groupby(["date", "product_vt_symbol"], as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            trade_count=("trade_count", "sum"),
            slippage=("slippage", "sum"),
            abs_pos_change=("pos_change", lambda values: float(pd.to_numeric(values, errors="coerce").abs().sum())),
            abs_end_pos=("end_pos", lambda values: float(pd.to_numeric(values, errors="coerce").abs().sum())),
        )
    )


def build_product_comparison(stage75_product: pd.DataFrame, shield_product: pd.DataFrame) -> pd.DataFrame:
    def summarize(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
        grouped = (
            df.groupby("product_vt_symbol", as_index=False)
            .agg(
                net_pnl_2026=("net_pnl", "sum"),
                trade_count_2026=("trade_count", "sum"),
                slippage_2026=("slippage", "sum"),
                abs_pos_change_2026=("abs_pos_change", "sum"),
                active_days_2026=("abs_end_pos", lambda values: int((values > 0.0).sum())),
                worst_day_net_pnl=("net_pnl", "min"),
            )
        )
        return grouped.add_prefix(f"{prefix}_").rename(columns={f"{prefix}_product_vt_symbol": "product_vt_symbol"})

    stage75 = summarize(stage75_product, "stage75")
    shield = summarize(shield_product, "shield")
    comparison = shield.merge(stage75, on="product_vt_symbol", how="outer").fillna(0.0)
    for column in ("net_pnl_2026", "trade_count_2026", "slippage_2026", "abs_pos_change_2026"):
        comparison[f"delta_{column}"] = comparison[f"shield_{column}"] - comparison[f"stage75_{column}"]
    return comparison.sort_values(["delta_net_pnl_2026", "product_vt_symbol"]).reset_index(drop=True)


def load_opened_entries(path: Path, variant: str) -> pd.DataFrame:
    df = _load_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df = df[df["date"] >= TAIL_START].copy()
    if df.empty:
        return df
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
    ):
        df[column] = _numeric_series(df, column)
    opened = df[(df["candidate_status"].astype(str) == "opened") | (df["is_opened"] > 0.0)].copy()
    opened["variant"] = variant
    return opened


def build_entry_event_comparison(stage75_entries: pd.DataFrame, shield_entries: pd.DataFrame) -> pd.DataFrame:
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
    ]

    def view(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=key_columns)
        keep = key_columns + metric_columns
        result = df[keep].copy()
        return result.rename(columns={column: f"{prefix}_{column}" for column in metric_columns})

    comparison = view(shield_entries, "shield").merge(
        view(stage75_entries, "stage75"),
        on=key_columns,
        how="outer",
    ).sort_values(key_columns).reset_index(drop=True)
    comparison = comparison.fillna(0.0)
    for column in metric_columns:
        comparison[f"delta_{column}"] = comparison[f"shield_{column}"] - comparison[f"stage75_{column}"]
    return comparison


def build_daily_comparison(stage75_daily: pd.DataFrame, shield_daily: pd.DataFrame) -> pd.DataFrame:
    keep = ["date", "net_pnl", "balance", "drawdown", "ddpercent", "trade_count", "slippage"]
    stage75 = stage75_daily[stage75_daily["date"] >= TAIL_START][keep].copy()
    shield = shield_daily[shield_daily["date"] >= TAIL_START][keep].copy()
    comparison = shield.rename(columns={column: f"shield_{column}" for column in keep if column != "date"}).merge(
        stage75.rename(columns={column: f"stage75_{column}" for column in keep if column != "date"}),
        on="date",
        how="outer",
    ).sort_values("date").reset_index(drop=True).fillna(0.0)
    for column in ("net_pnl", "trade_count", "slippage"):
        comparison[f"delta_{column}"] = comparison[f"shield_{column}"] - comparison[f"stage75_{column}"]
    return comparison


def build_summary(
    stage75_daily: pd.DataFrame,
    shield_daily: pd.DataFrame,
    product_comparison: pd.DataFrame,
    entry_event_comparison: pd.DataFrame,
) -> dict[str, Any]:
    stage75 = summarize_period(stage75_daily)
    shield = summarize_period(shield_daily)
    key_product = product_comparison[product_comparison["product_vt_symbol"] == KEY_PRODUCT].copy()
    key_product_summary: dict[str, Any] = {}
    if not key_product.empty:
        row = key_product.iloc[0]
        key_product_summary = {
            "stage75_net_pnl_2026": float(row["stage75_net_pnl_2026"]),
            "shield_net_pnl_2026": float(row["shield_net_pnl_2026"]),
            "delta_net_pnl_2026": float(row["delta_net_pnl_2026"]),
            "stage75_abs_pos_change_2026": float(row["stage75_abs_pos_change_2026"]),
            "shield_abs_pos_change_2026": float(row["shield_abs_pos_change_2026"]),
            "delta_abs_pos_change_2026": float(row["delta_abs_pos_change_2026"]),
        }

    key_dates = set(pd.to_datetime(list(KEY_EVENT_DATES)).normalize())
    key_events = entry_event_comparison[
        (entry_event_comparison["product_vt_symbol"] == KEY_PRODUCT)
        & (entry_event_comparison["date"].isin(key_dates))
    ].copy()
    key_event_records = []
    for row in key_events.itertuples(index=False):
        key_event_records.append(
            {
                "date": str(row.date.date()),
                "direction": row.direction,
                "signal": row.signal,
                "stage75_selected_volume": float(row.stage75_selected_volume),
                "shield_selected_volume": float(row.shield_selected_volume),
                "delta_selected_volume": float(row.delta_selected_volume),
                "stage75_risk_multiplier": float(row.stage75_risk_multiplier),
                "shield_risk_multiplier": float(row.shield_risk_multiplier),
                "delta_risk_multiplier": float(row.delta_risk_multiplier),
                "stage75_loss_streak": float(row.stage75_loss_streak),
                "shield_loss_streak": float(row.shield_loss_streak),
            }
        )

    return {
        "model_tag": MODEL_TAG,
        "tail_start": str(TAIL_START.date()),
        "stage75_period": stage75,
        "shield_period": shield,
        "delta_period": {
            "end_balance": shield["end_balance"] - stage75["end_balance"],
            "net_pnl": shield["net_pnl"] - stage75["net_pnl"],
            "return_pct": shield["return_pct"] - stage75["return_pct"],
            "max_dd_percent": shield["max_dd_percent"] - stage75["max_dd_percent"],
            "trade_count": shield["trade_count"] - stage75["trade_count"],
            "slippage": shield["slippage"] - stage75["slippage"],
        },
        "key_product": KEY_PRODUCT,
        "key_product_summary": key_product_summary,
        "key_event_records": key_event_records,
    }


def build_report(
    summary: dict[str, Any],
    product_comparison: pd.DataFrame,
    key_events: pd.DataFrame,
    daily_comparison: pd.DataFrame,
) -> str:
    stage75 = summary["stage75_period"]
    shield = summary["shield_period"]
    delta = summary["delta_period"]
    key_product = summary["key_product_summary"]

    lines = [
        f"# {MODEL_TAG}",
        "",
        "## 结论",
        "",
        f"- 第78阶段相对第75阶段在2026尾部净损益改善`{_safe_float(delta.get('net_pnl')):,.0f}`。",
        f"- 2026尾部期初权益差额为`{shield['start_balance'] - stage75['start_balance']:,.0f}`，期末权益差额为`{_safe_float(delta.get('end_balance')):,.0f}`；因此该归因优先看区间净损益，而不是绝对期末权益。",
        f"- 2026尾部最大回撤差额`{_safe_float(delta.get('max_dd_percent')):.2f}`个百分点，交易次数变化`{int(_safe_float(delta.get('trade_count'))):,}`，滑点变化`{_safe_float(delta.get('slippage')):,.0f}`。",
        f"- `{KEY_PRODUCT}`净损益差额为`{_safe_float(key_product.get('delta_net_pnl_2026')):,.0f}`，绝对持仓变化差额为`{_safe_float(key_product.get('delta_abs_pos_change_2026')):,.0f}`。",
        "- 若关键事件中风险乘数从`1.00`降到`0.10`或手数显著下降，说明第78阶段确实修复了卫星盈利误恢复组合风险状态的问题。",
        "",
        "## 2026尾部表现",
        "",
        "| 版本 | 起始权益 | 期末权益 | 净损益 | 区间收益 | 最大回撤 | 总滑点 | 总交易次数 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| 第75阶段 | `{stage75['start_balance']:,.0f}` | `{stage75['end_balance']:,.0f}` | `{stage75['net_pnl']:,.0f}` | `{stage75['return_pct']:.2f}%` | `{stage75['max_dd_percent']:.2f}%` | `{stage75['slippage']:,.0f}` | `{stage75['trade_count']:,}` |",
        f"| 第78阶段 | `{shield['start_balance']:,.0f}` | `{shield['end_balance']:,.0f}` | `{shield['net_pnl']:,.0f}` | `{shield['return_pct']:.2f}%` | `{shield['max_dd_percent']:.2f}%` | `{shield['slippage']:,.0f}` | `{shield['trade_count']:,}` |",
        "",
        "## 产品差异",
        "",
        to_markdown_table(
            product_comparison[
                [
                    "product_vt_symbol",
                    "shield_net_pnl_2026",
                    "stage75_net_pnl_2026",
                    "delta_net_pnl_2026",
                    "shield_trade_count_2026",
                    "stage75_trade_count_2026",
                    "delta_abs_pos_change_2026",
                ]
            ].head(12)
        ),
        "",
        "## 关键事件",
        "",
        to_markdown_table(
            key_events[
                [
                    "date",
                    "product_vt_symbol",
                    "direction",
                    "signal",
                    "shield_selected_volume",
                    "stage75_selected_volume",
                    "delta_selected_volume",
                    "shield_risk_multiplier",
                    "stage75_risk_multiplier",
                    "delta_risk_multiplier",
                    "shield_loss_streak",
                    "stage75_loss_streak",
                ]
            ].copy()
        ),
        "",
        "## 最差差异日",
        "",
        to_markdown_table(
            daily_comparison.sort_values("delta_net_pnl").head(10)[
                [
                    "date",
                    "shield_net_pnl",
                    "stage75_net_pnl",
                    "delta_net_pnl",
                    "shield_trade_count",
                    "stage75_trade_count",
                    "delta_slippage",
                ]
            ].assign(date=lambda df: df["date"].dt.strftime("%Y-%m-%d"))
        ),
        "",
        "## 判断",
        "",
        "- 该归因用于确认第78阶段的改善是否来自风险状态治理，而不是偶然产品盈亏抵消。",
        "- 如果关键事件手数和风险乘数被压低，同时全局起始年份测试不过度恶化，才允许继续把第78阶段推进为正式候选。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    stage75_daily = load_daily(STAGE75_DAILY_PATH)
    shield_daily = load_daily(SHIELD_DAILY_PATH)
    stage75_product = load_product_daily(STAGE75_POSITION_CHANGES_PATH)
    shield_product = load_product_daily(SHIELD_POSITION_CHANGES_PATH)
    stage75_entries = load_opened_entries(STAGE75_ENTRY_SNAPSHOTS_PATH, "stage75")
    shield_entries = load_opened_entries(SHIELD_ENTRY_SNAPSHOTS_PATH, "shield")

    product_comparison = build_product_comparison(stage75_product, shield_product)
    entry_event_comparison = build_entry_event_comparison(stage75_entries, shield_entries)
    key_dates = set(pd.to_datetime(list(KEY_EVENT_DATES)).normalize())
    key_events = entry_event_comparison[
        (entry_event_comparison["product_vt_symbol"] == KEY_PRODUCT)
        & (entry_event_comparison["date"].isin(key_dates))
    ].copy()
    daily_comparison = build_daily_comparison(stage75_daily, shield_daily)
    summary = build_summary(stage75_daily, shield_daily, product_comparison, entry_event_comparison)
    report = build_report(summary, product_comparison, key_events, daily_comparison)

    product_comparison.to_csv(PRODUCT_COMPARISON_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    entry_event_comparison.assign(date=lambda df: df["date"].dt.strftime("%Y-%m-%d")).to_csv(
        ENTRY_EVENT_COMPARISON_OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )
    key_events.assign(date=lambda df: df["date"].dt.strftime("%Y-%m-%d")).to_csv(
        KEY_EVENTS_OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )
    daily_comparison.assign(date=lambda df: df["date"].dt.strftime("%Y-%m-%d")).to_csv(
        DAILY_COMPARISON_OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )
    SUMMARY_OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_OUTPUT_PATH.write_text(report, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"wrote {REPORT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
