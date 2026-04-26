from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage145_extreme_loss_event_ledger_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage145_extreme_loss_event_ledger"
FORMAL_PREFIX: str = "qmt_roll_official_stage78_defensive_formal"

DAILY_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_daily.csv"
TRADES_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_trades_2020_2026_04.csv"
POSITION_CHANGES_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_position_changes_2020_2026_04.csv"
RISK_DIAGNOSTICS_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_entry_risk_diagnostics_2020_2026_04.csv"
SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_defensive_summary.json"

LEDGER_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ledger_{MODEL_TAG}.csv"
TAIL_EVENTS_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tail_events_{MODEL_TAG}.csv"
PRODUCT_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_summary_{MODEL_TAG}.csv"
YEAR_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_summary_{MODEL_TAG}.csv"
EXIT_REASON_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_exit_reason_summary_{MODEL_TAG}.csv"
SIGNAL_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_signal_summary_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"missing required artifact: {path}")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _fmt(value: Any, digits: int = 4) -> str:
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    numeric = _safe_float(value, default=float("nan"))
    if math.isnan(numeric):
        return str(value)
    if abs(numeric) >= 1000:
        return f"{numeric:,.0f}"
    return f"{numeric:.{digits}f}"


def _to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 20) -> str:
    if df.empty:
        return "_No rows._"
    view = df.copy()
    if columns is not None:
        view = view.loc[:, [column for column in columns if column in view.columns]]
    view = view.head(max_rows).copy()
    for column in view.columns:
        if column in {"close_year", "event_id"}:
            view[column] = view[column].map(lambda x: str(int(x)) if pd.notna(x) else "")
        elif pd.api.types.is_numeric_dtype(view[column]):
            view[column] = view[column].map(_fmt)
    return "\n".join(
        [
            "| " + " | ".join(view.columns) + " |",
            "| " + " | ".join(["---"] * len(view.columns)) + " |",
            *["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()],
        ]
    )


def _numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame


def _read_csv(path: Path) -> pd.DataFrame:
    _require(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _product_from_vt_symbol(vt_symbol: Any) -> str:
    raw = str(vt_symbol)
    if "." not in raw:
        return raw
    symbol, exchange = raw.split(".", 1)
    product = "".join(ch for ch in symbol if ch.isalpha())
    return f"{product}.{exchange}" if product else raw


def _normalize_date(frame: pd.DataFrame, column: str = "date") -> pd.DataFrame:
    frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.tz_localize(None).dt.normalize()
    return frame.dropna(subset=[column]).reset_index(drop=True)


def _load_inputs() -> dict[str, Any]:
    for path in (DAILY_PATH, TRADES_PATH, POSITION_CHANGES_PATH, RISK_DIAGNOSTICS_PATH, SUMMARY_PATH):
        _require(path)

    daily = _normalize_date(_read_csv(DAILY_PATH)).sort_values("date").reset_index(drop=True)
    _numeric(daily, ["net_pnl", "balance", "ddpercent", "trade_count", "slippage"])

    trades = _normalize_date(_read_csv(TRADES_PATH))
    _numeric(trades, ["price", "volume", "signed_volume"])
    trades["product_vt_symbol"] = trades["vt_symbol"].map(_product_from_vt_symbol)
    trades["exit_reason"] = trades["exit_reason"].fillna("open_or_unknown")
    trades["offset_norm"] = trades["offset"].astype(str).str.lower()
    trades["direction_norm"] = trades["direction"].astype(str).str.lower()

    positions = _normalize_date(_read_csv(POSITION_CHANGES_PATH))
    _numeric(
        positions,
        [
            "start_pos",
            "end_pos",
            "pos_change",
            "turnover",
            "commission",
            "slippage",
            "holding_pnl",
            "trading_pnl",
            "total_pnl",
            "net_pnl",
            "trade_count",
        ],
    )
    positions["product_vt_symbol"] = positions["vt_symbol"].map(_product_from_vt_symbol)

    risk = _normalize_date(_read_csv(RISK_DIAGNOSTICS_PATH))
    _numeric(
        risk,
        [
            "estimated_equity",
            "projected_total_margin_after",
            "actual_margin_amount",
            "selected_volume",
            "selected_volume_ungated",
            "risk_multiplier",
            "actual_risk_amount",
            "portfolio_drawdown_pct",
            "same_direction_correlation_active_count",
            "same_direction_correlation_max_corr",
            "loss_streak",
            "profit_recovery_streak",
        ],
    )
    risk["projected_margin_usage_pct"] = (
        risk["projected_total_margin_after"] / risk["estimated_equity"].replace(0.0, np.nan) * 100.0
    ).fillna(0.0)

    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    return {"daily": daily, "trades": trades, "positions": positions, "risk": risk, "summary": summary}


def _closed_direction(close_direction: str) -> str:
    return "Long" if close_direction.lower() == "short" else "Short"


def _find_entry_context(risk: pd.DataFrame, product: str, contract: str, open_date: pd.Timestamp) -> dict[str, Any]:
    match = risk[
        (risk["date"] == open_date)
        & (risk["product_vt_symbol"] == product)
        & (risk["contract_vt_symbol"] == contract)
    ].copy()
    if match.empty:
        match = risk[(risk["date"] == open_date) & (risk["product_vt_symbol"] == product)].copy()
    if match.empty:
        return {
            "entry_found": False,
            "entry_signal": "",
            "entry_layer_kind": "",
            "entry_risk_mode": "",
            "entry_selected_volume": 0.0,
            "entry_selected_volume_ungated": 0.0,
            "entry_actual_risk_amount": 0.0,
            "entry_projected_margin_usage_pct": 0.0,
            "entry_portfolio_drawdown_pct": 0.0,
            "entry_same_direction_active_count": 0.0,
            "entry_same_direction_max_corr": 0.0,
            "entry_loss_streak": 0.0,
        }
    row = match.iloc[-1]
    return {
        "entry_found": True,
        "entry_signal": row["signal"],
        "entry_layer_kind": row["layer_kind"],
        "entry_risk_mode": row["risk_mode"],
        "entry_selected_volume": row["selected_volume"],
        "entry_selected_volume_ungated": row["selected_volume_ungated"],
        "entry_actual_risk_amount": row["actual_risk_amount"],
        "entry_projected_margin_usage_pct": row["projected_margin_usage_pct"],
        "entry_portfolio_drawdown_pct": row["portfolio_drawdown_pct"],
        "entry_same_direction_active_count": row["same_direction_correlation_active_count"],
        "entry_same_direction_max_corr": row["same_direction_correlation_max_corr"],
        "entry_loss_streak": row["loss_streak"],
    }


def _build_lifecycle_ledger(inputs: dict[str, Any]) -> pd.DataFrame:
    trades = inputs["trades"].sort_values(["date", "trade_id"]).reset_index(drop=True)
    positions = inputs["positions"]
    risk = inputs["risk"]
    open_stacks: dict[tuple[str, str], list[pd.Series]] = defaultdict(list)
    rows: list[dict[str, Any]] = []

    for trade in trades.itertuples(index=False):
        if trade.offset_norm == "open":
            open_stacks[(trade.vt_symbol, trade.direction)].append(pd.Series(trade._asdict()))
            continue
        if trade.offset_norm != "close":
            continue

        open_direction = _closed_direction(str(trade.direction))
        key = (trade.vt_symbol, open_direction)
        open_row = open_stacks[key].pop() if open_stacks[key] else None
        if open_row is None:
            continue

        open_date = open_row["date"]
        close_date = trade.date
        lifecycle_mask = (
            (positions["vt_symbol"] == trade.vt_symbol)
            & (positions["date"] >= open_date)
            & (positions["date"] <= close_date)
        )
        lifecycle = positions[lifecycle_mask]
        entry = _find_entry_context(risk, trade.product_vt_symbol, trade.vt_symbol, open_date)
        lifecycle_net = float(lifecycle["net_pnl"].sum())
        actual_risk = _safe_float(entry.get("entry_actual_risk_amount"), 0.0)
        rows.append(
            {
                "event_id": len(rows) + 1,
                "product_vt_symbol": trade.product_vt_symbol,
                "contract_vt_symbol": trade.vt_symbol,
                "direction": open_direction,
                "open_date": open_date.date().isoformat(),
                "close_date": close_date.date().isoformat(),
                "close_year": int(close_date.year),
                "holding_calendar_days": int((close_date - open_date).days),
                "open_price": float(open_row["price"]),
                "close_price": float(trade.price),
                "volume": float(trade.volume),
                "exit_reason": trade.exit_reason,
                "lifecycle_net_pnl": lifecycle_net,
                "lifecycle_holding_pnl": float(lifecycle["holding_pnl"].sum()),
                "lifecycle_trading_pnl": float(lifecycle["trading_pnl"].sum()),
                "lifecycle_slippage": float(lifecycle["slippage"].sum()),
                "pnl_to_entry_risk": lifecycle_net / actual_risk if actual_risk else 0.0,
                **entry,
            }
        )

    ledger = pd.DataFrame(rows)
    if ledger.empty:
        return ledger
    values = ledger["lifecycle_net_pnl"].to_numpy()
    ledger["loss_percentile_low"] = ledger["lifecycle_net_pnl"].map(lambda x: float((values <= x).mean() * 100.0))
    ledger["tail_bucket"] = np.select(
        [
            ledger["lifecycle_net_pnl"] >= 0.0,
            ledger["loss_percentile_low"] <= 1.0,
            ledger["loss_percentile_low"] <= 5.0,
            ledger["loss_percentile_low"] <= 10.0,
        ],
        ["profit_or_flat", "catastrophic_bottom_1pct", "severe_bottom_5pct", "notable_bottom_10pct"],
        default="ordinary_loss",
    )
    return ledger.sort_values("lifecycle_net_pnl").reset_index(drop=True)


def _agg_list(values: pd.Series) -> str:
    return ",".join(str(v) for v in sorted(set(values.dropna().astype(str))))


def _build_product_summary(ledger: pd.DataFrame) -> pd.DataFrame:
    if ledger.empty:
        return pd.DataFrame()
    return (
        ledger.groupby("product_vt_symbol", as_index=False)
        .agg(
            event_count=("event_id", "count"),
            total_lifecycle_net_pnl=("lifecycle_net_pnl", "sum"),
            loss_count=("lifecycle_net_pnl", lambda s: int((s < 0.0).sum())),
            tail_5pct_count=("tail_bucket", lambda s: int(s.isin(["catastrophic_bottom_1pct", "severe_bottom_5pct"]).sum())),
            bottom_1pct_count=("tail_bucket", lambda s: int((s == "catastrophic_bottom_1pct").sum())),
            worst_lifecycle_net_pnl=("lifecycle_net_pnl", "min"),
            median_lifecycle_net_pnl=("lifecycle_net_pnl", "median"),
            years=("close_year", _agg_list),
        )
        .assign(
            loss_rate_pct=lambda df: df["loss_count"] / df["event_count"].replace(0, np.nan) * 100.0,
            tail_5pct_rate_pct=lambda df: df["tail_5pct_count"] / df["event_count"].replace(0, np.nan) * 100.0,
        )
        .fillna(0.0)
        .sort_values(["bottom_1pct_count", "tail_5pct_count", "worst_lifecycle_net_pnl"], ascending=[False, False, True])
        .reset_index(drop=True)
    )


def _build_year_summary(ledger: pd.DataFrame) -> pd.DataFrame:
    if ledger.empty:
        return pd.DataFrame()
    return (
        ledger.groupby("close_year", as_index=False)
        .agg(
            event_count=("event_id", "count"),
            total_lifecycle_net_pnl=("lifecycle_net_pnl", "sum"),
            loss_count=("lifecycle_net_pnl", lambda s: int((s < 0.0).sum())),
            tail_5pct_count=("tail_bucket", lambda s: int(s.isin(["catastrophic_bottom_1pct", "severe_bottom_5pct"]).sum())),
            bottom_1pct_count=("tail_bucket", lambda s: int((s == "catastrophic_bottom_1pct").sum())),
            worst_lifecycle_net_pnl=("lifecycle_net_pnl", "min"),
        )
        .sort_values("close_year")
        .reset_index(drop=True)
    )


def _build_group_summary(ledger: pd.DataFrame, group_col: str) -> pd.DataFrame:
    if ledger.empty:
        return pd.DataFrame()
    return (
        ledger.groupby(group_col, as_index=False)
        .agg(
            event_count=("event_id", "count"),
            total_lifecycle_net_pnl=("lifecycle_net_pnl", "sum"),
            loss_count=("lifecycle_net_pnl", lambda s: int((s < 0.0).sum())),
            tail_5pct_count=("tail_bucket", lambda s: int(s.isin(["catastrophic_bottom_1pct", "severe_bottom_5pct"]).sum())),
            bottom_1pct_count=("tail_bucket", lambda s: int((s == "catastrophic_bottom_1pct").sum())),
            worst_lifecycle_net_pnl=("lifecycle_net_pnl", "min"),
            median_lifecycle_net_pnl=("lifecycle_net_pnl", "median"),
        )
        .assign(
            loss_rate_pct=lambda df: df["loss_count"] / df["event_count"].replace(0, np.nan) * 100.0,
            tail_5pct_rate_pct=lambda df: df["tail_5pct_count"] / df["event_count"].replace(0, np.nan) * 100.0,
        )
        .fillna(0.0)
        .sort_values(["tail_5pct_count", "worst_lifecycle_net_pnl"], ascending=[False, True])
        .reset_index(drop=True)
    )


def _build_summary_payload(inputs: dict[str, Any], ledger: pd.DataFrame, product_summary: pd.DataFrame) -> dict[str, Any]:
    summary = inputs["summary"]
    stage78_full = summary["reference_metrics"]["full_2020_2026"]
    if ledger.empty:
        return {"model_tag": MODEL_TAG, "is_strategy_change": False, "decision": "empty_ledger"}
    thresholds = {
        "bottom_1pct_threshold": float(np.percentile(ledger["lifecycle_net_pnl"], 1)),
        "bottom_5pct_threshold": float(np.percentile(ledger["lifecycle_net_pnl"], 5)),
        "bottom_10pct_threshold": float(np.percentile(ledger["lifecycle_net_pnl"], 10)),
    }
    tail = ledger[ledger["tail_bucket"].isin(["catastrophic_bottom_1pct", "severe_bottom_5pct"])].copy()
    ma_row = product_summary[product_summary["product_vt_symbol"] == "MA.CZCE"]
    ma_tail_count = int(ma_row["tail_5pct_count"].iloc[0]) if not ma_row.empty else 0
    products_with_multi_tail = product_summary[product_summary["tail_5pct_count"] >= 2]["product_vt_symbol"].tolist()
    decision = "ledger_monitor_only_keep_stage78"
    return {
        "model_tag": MODEL_TAG,
        "is_strategy_change": False,
        "version_ab_skill_triggered": False,
        "stage78_reference": stage78_full,
        "event_count": int(len(ledger)),
        "loss_count": int((ledger["lifecycle_net_pnl"] < 0.0).sum()),
        "total_lifecycle_net_pnl": float(ledger["lifecycle_net_pnl"].sum()),
        "thresholds": thresholds,
        "tail_5pct_event_count": int(len(tail)),
        "bottom_1pct_event_count": int((ledger["tail_bucket"] == "catastrophic_bottom_1pct").sum()),
        "products_with_multi_tail_5pct": products_with_multi_tail,
        "ma_tail_5pct_count": ma_tail_count,
        "worst_event": ledger.head(1).to_dict(orient="records")[0],
        "decision": decision,
        "anti_overfit_boundary": (
            "This ledger monitors full lifecycle loss tails only. It must not create product blacklists, "
            "profit-giveback exits, or stop-loss patches from individual events."
        ),
    }


def _write_report(
    payload: dict[str, Any],
    ledger: pd.DataFrame,
    tail_events: pd.DataFrame,
    product_summary: pd.DataFrame,
    year_summary: pd.DataFrame,
    exit_reason_summary: pd.DataFrame,
    signal_summary: pd.DataFrame,
) -> None:
    stage78 = payload["stage78_reference"]
    thresholds = payload["thresholds"]
    event_cols = [
        "product_vt_symbol",
        "contract_vt_symbol",
        "direction",
        "open_date",
        "close_date",
        "holding_calendar_days",
        "exit_reason",
        "lifecycle_net_pnl",
        "pnl_to_entry_risk",
        "loss_percentile_low",
        "tail_bucket",
        "entry_signal",
    ]
    product_cols = [
        "product_vt_symbol",
        "event_count",
        "total_lifecycle_net_pnl",
        "loss_count",
        "loss_rate_pct",
        "tail_5pct_count",
        "bottom_1pct_count",
        "worst_lifecycle_net_pnl",
        "years",
    ]
    year_cols = ["close_year", "event_count", "total_lifecycle_net_pnl", "loss_count", "tail_5pct_count", "bottom_1pct_count", "worst_lifecycle_net_pnl"]
    group_cols = ["exit_reason", "event_count", "total_lifecycle_net_pnl", "loss_count", "tail_5pct_count", "bottom_1pct_count", "worst_lifecycle_net_pnl"]
    signal_cols = ["entry_signal", "event_count", "total_lifecycle_net_pnl", "loss_count", "tail_5pct_count", "bottom_1pct_count", "worst_lifecycle_net_pnl"]

    report = f"""# Stage145 Stage78极端单笔亏损事件账本

## 结论
- 本阶段不是策略版本，不改Stage78，不触发A/B技能。
- 当前决策：`{payload["decision"]}`。
- 过拟合判断：否。这里使用全历史完整交易生命周期构建尾部事件账本，不用最近单笔亏损反推参数、不设黑名单、不新增退出规则。
- 是否有价值继续：是。Stage144指出`MA.CZCE`是真实极端尾部失败单，本阶段验证这种尾部事件是否系统性、跨品种、跨年份重复。

## Stage78 正式基准
- 期末权益：{_fmt(stage78.get("end_balance"))}
- 总收益：{_fmt(stage78.get("total_return_pct"))}%
- 最大回撤：{_fmt(stage78.get("max_dd_percent"))}%
- Sharpe：{_fmt(stage78.get("sharpe_ratio"))}
- 总滑点：{_fmt(stage78.get("total_slippage"))}
- 总交易次数：{_fmt(stage78.get("total_trade_count"))}

## 全历史生命周期统计
- 完整交易事件数：{payload["event_count"]}
- 亏损事件数：{payload["loss_count"]}
- 生命周期净损益合计：{_fmt(payload["total_lifecycle_net_pnl"])}
- Bottom 1% 阈值：{_fmt(thresholds["bottom_1pct_threshold"])}
- Bottom 5% 阈值：{_fmt(thresholds["bottom_5pct_threshold"])}
- Bottom 10% 阈值：{_fmt(thresholds["bottom_10pct_threshold"])}
- Bottom 5% 事件数：{payload["tail_5pct_event_count"]}
- Bottom 1% 事件数：{payload["bottom_1pct_event_count"]}
- 多次进入Bottom 5%的品种：{", ".join(payload["products_with_multi_tail_5pct"]) or "无"}
- `MA.CZCE`进入Bottom 5%次数：{payload["ma_tail_5pct_count"]}

## 最差生命周期事件
{_to_markdown_table(ledger, event_cols, max_rows=15)}

## Bottom 5% 尾部事件
{_to_markdown_table(tail_events, event_cols, max_rows=30)}

## 品种尾部汇总
{_to_markdown_table(product_summary, product_cols, max_rows=30)}

## 年份汇总
{_to_markdown_table(year_summary, year_cols, max_rows=10)}

## 退出原因汇总
{_to_markdown_table(exit_reason_summary, group_cols, max_rows=20)}

## 入场信号汇总
{_to_markdown_table(signal_summary, signal_cols, max_rows=20)}

## 使用边界
- 本账本只回答“尾部亏损是否系统性出现”，不回答“如何优化参数”。
- 如果某类尾部事件跨品种、跨年份重复，优先进入组合层监控或风险预算研究。
- 禁止把单个品种的尾部事件直接变成黑名单、利润保护、止损微调。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    inputs = _load_inputs()
    ledger = _build_lifecycle_ledger(inputs)
    tail_events = ledger[ledger["tail_bucket"].isin(["catastrophic_bottom_1pct", "severe_bottom_5pct"])].copy()
    product_summary = _build_product_summary(ledger)
    year_summary = _build_year_summary(ledger)
    exit_reason_summary = _build_group_summary(ledger, "exit_reason")
    signal_summary = _build_group_summary(ledger, "entry_signal")
    payload = _build_summary_payload(inputs, ledger, product_summary)

    ledger.to_csv(LEDGER_PATH, index=False, encoding="utf-8-sig")
    tail_events.to_csv(TAIL_EVENTS_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    year_summary.to_csv(YEAR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    exit_reason_summary.to_csv(EXIT_REASON_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    signal_summary.to_csv(SIGNAL_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _write_report(payload, ledger, tail_events, product_summary, year_summary, exit_reason_summary, signal_summary)

    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
