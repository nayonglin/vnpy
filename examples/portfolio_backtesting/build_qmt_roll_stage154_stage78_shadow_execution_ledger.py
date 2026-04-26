from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database

from main_contract_mapping import build_contract_metadata, load_product_universe_symbols
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_REFERENCE_METRICS,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_paths,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage154_stage78_shadow_execution_ledger_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage154_stage78_shadow_execution_ledger"
FORMAL_PREFIX: str = "qmt_roll_official_stage78_defensive_formal"

TRADES_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_trades_2020_2026_04.csv"
DAILY_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_daily.csv"
RISK_DIAGNOSTICS_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_entry_risk_diagnostics_2020_2026_04.csv"
CANDIDATE_SNAPSHOTS_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv"

TRADE_LEDGER_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_ledger_{MODEL_TAG}.csv"
DAILY_LEDGER_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_ledger_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

DAILY_ADVERSE_WARN_CASH: float = 20_000.0
DAILY_ADVERSE_ALERT_CASH: float = 50_000.0
MARGIN_USAGE_WATCH_PCT: float = 80.0
MARGIN_USAGE_ALERT_PCT: float = 100.0


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
        if pd.api.types.is_numeric_dtype(view[column]):
            view[column] = view[column].map(_fmt)
    return "\n".join(
        [
            "| " + " | ".join(view.columns) + " |",
            "| " + " | ".join(["---"] * len(view.columns)) + " |",
            *["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()],
        ]
    )


def _read_csv(path: Path) -> pd.DataFrame:
    _require(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _parse_vt_symbol(vt_symbol: str) -> tuple[str, Exchange]:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return symbol, Exchange(exchange)


def _product_from_contract(vt_symbol: Any, exchange: Any) -> str:
    symbol = str(vt_symbol).split(".", 1)[0]
    product = "".join(ch for ch in symbol if ch.isalpha())
    return f"{product}.{exchange}" if product else str(vt_symbol)


def _numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame


def _load_contract_bars(vt_symbols: list[str], start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    database = get_database()
    rows: list[dict[str, Any]] = []
    start_dt = start.to_pydatetime()
    end_dt = end.to_pydatetime()

    for vt_symbol in sorted(set(vt_symbols)):
        if not vt_symbol or vt_symbol == "nan":
            continue
        symbol, exchange = _parse_vt_symbol(vt_symbol)
        bars = database.load_bar_data(symbol, exchange, Interval.DAILY, start_dt, end_dt)
        for bar in bars:
            rows.append(
                {
                    "date": pd.Timestamp(bar.datetime).tz_localize(None).normalize(),
                    "vt_symbol": vt_symbol,
                    "open": float(bar.open_price),
                    "high": float(bar.high_price),
                    "low": float(bar.low_price),
                    "close": float(bar.close_price),
                    "volume": float(getattr(bar, "volume", 0.0) or 0.0),
                    "open_interest": float(getattr(bar, "open_interest", 0.0) or 0.0),
                }
            )
    if not rows:
        return pd.DataFrame(columns=["date", "vt_symbol", "open", "high", "low", "close", "volume", "open_interest"])
    return pd.DataFrame(rows).drop_duplicates(subset=["date", "vt_symbol"]).sort_values(["vt_symbol", "date"])


def _load_inputs() -> dict[str, Any]:
    trades = _read_csv(TRADES_PATH)
    daily = _read_csv(DAILY_PATH)
    risk = _read_csv(RISK_DIAGNOSTICS_PATH)
    candidates = _read_csv(CANDIDATE_SNAPSHOTS_PATH)

    trades["date"] = pd.to_datetime(trades["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    risk["date"] = pd.to_datetime(risk["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    candidates["date"] = pd.to_datetime(candidates["date"], errors="coerce").dt.tz_localize(None).dt.normalize()

    _numeric(trades, ["price", "volume", "signed_volume"])
    _numeric(daily, ["trade_count", "turnover", "commission", "slippage", "net_pnl", "balance", "ddpercent"])
    _numeric(
        risk,
        [
            "estimated_equity",
            "total_margin_in_use_before",
            "projected_total_margin_after",
            "actual_margin_amount",
            "volume",
            "margin_ratio",
            "same_direction_correlation_active_count",
            "same_direction_correlation_max_corr",
            "portfolio_drawdown_pct",
        ],
    )
    _numeric(
        candidates,
        [
            "estimated_equity",
            "total_margin_in_use_before",
            "projected_total_margin_after",
            "selected_volume",
            "ai_product_pool_allowed",
            "same_direction_correlation_max_corr",
            "portfolio_drawdown_pct",
        ],
    )

    trades = trades.dropna(subset=["date"]).sort_values(["date", "trade_id"]).reset_index(drop=True)
    trades["product_vt_symbol"] = [
        _product_from_contract(vt_symbol, exchange)
        for vt_symbol, exchange in zip(trades["vt_symbol"], trades["exchange"], strict=False)
    ]

    universe_path, _ = build_official_stage78_paths()
    supported_symbols = load_product_universe_symbols(universe_path)
    metadata = build_contract_metadata(supported_symbols=supported_symbols)
    return {
        "trades": trades,
        "daily": daily.dropna(subset=["date"]).sort_values("date").reset_index(drop=True),
        "risk": risk.dropna(subset=["date"]).sort_values("date").reset_index(drop=True),
        "candidates": candidates.dropna(subset=["date"]).sort_values("date").reset_index(drop=True),
        "metadata": metadata,
    }


def _build_bar_lookup(bars: pd.DataFrame) -> dict[str, pd.DataFrame]:
    lookup: dict[str, pd.DataFrame] = {}
    for vt_symbol, group in bars.groupby("vt_symbol", sort=False):
        lookup[str(vt_symbol)] = group.sort_values("date").reset_index(drop=True)
    return lookup


def _bar_at_or_after(group: pd.DataFrame, trade_date: pd.Timestamp, *, strictly_after: bool) -> dict[str, Any]:
    if group.empty:
        return {}
    dates = pd.DatetimeIndex(group["date"])
    side = "right" if strictly_after else "left"
    index = int(dates.searchsorted(trade_date, side=side))
    if index >= len(group):
        return {}
    return group.iloc[index].to_dict()


def _adverse_price_diff(direction: str, executable_price: float, theoretical_price: float) -> float:
    raw_diff = executable_price - theoretical_price
    return raw_diff if str(direction) == "Long" else -raw_diff


def _execution_impact(
    *,
    direction: str,
    executable_price: float,
    theoretical_price: float,
    volume: float,
    size: float,
) -> float:
    adverse = _adverse_price_diff(direction, executable_price, theoretical_price)
    return adverse * volume * size


def _build_trade_ledger(inputs: dict[str, Any]) -> pd.DataFrame:
    trades = inputs["trades"].copy()
    metadata = inputs["metadata"]
    start = trades["date"].min() - pd.Timedelta(days=2)
    end = trades["date"].max() + pd.Timedelta(days=10)
    bars = _load_contract_bars(trades["vt_symbol"].dropna().astype(str).unique().tolist(), start, end)
    bar_lookup = _build_bar_lookup(bars)
    sizes = metadata["sizes"]
    priceticks = metadata["priceticks"]
    margin_ratios = metadata["margin_ratios"]

    rows: list[dict[str, Any]] = []
    for row in trades.itertuples(index=False):
        vt_symbol = str(row.vt_symbol)
        trade_date = pd.Timestamp(row.date).normalize()
        group = bar_lookup.get(vt_symbol, pd.DataFrame())
        same_bar = _bar_at_or_after(group, trade_date, strictly_after=False)
        if same_bar and pd.Timestamp(same_bar.get("date")).normalize() != trade_date:
            same_bar = {}
        next_bar = _bar_at_or_after(group, trade_date, strictly_after=True)

        size = float(sizes.get(vt_symbol, 1) or 1)
        pricetick = float(priceticks.get(vt_symbol, 1.0) or 1.0)
        margin_ratio = float(margin_ratios.get(vt_symbol, 0.0) or 0.0)
        theoretical_price = float(row.price)
        volume = float(row.volume)
        theoretical_notional = theoretical_price * volume * size
        theoretical_margin = theoretical_notional * margin_ratio if str(row.offset) == "Open" else 0.0

        next_open = _safe_float(next_bar.get("open") if next_bar else 0.0)
        next_close = _safe_float(next_bar.get("close") if next_bar else 0.0)
        next_volume = _safe_float(next_bar.get("volume") if next_bar else 0.0)
        next_high = _safe_float(next_bar.get("high") if next_bar else 0.0)
        next_low = _safe_float(next_bar.get("low") if next_bar else 0.0)
        next_open_available = int(bool(next_bar) and next_open > 0.0 and next_volume > 0.0)
        next_close_available = int(bool(next_bar) and next_close > 0.0 and next_volume > 0.0)
        zero_volume = int(bool(next_bar) and next_volume <= 0.0)
        no_range = int(bool(next_bar) and next_high > 0.0 and abs(next_high - next_low) <= 1e-9)

        next_open_adverse_price = (
            _adverse_price_diff(str(row.direction), next_open, theoretical_price) if next_open_available else 0.0
        )
        next_close_adverse_price = (
            _adverse_price_diff(str(row.direction), next_close, theoretical_price) if next_close_available else 0.0
        )
        rows.append(
            {
                "trade_id": row.trade_id,
                "date": trade_date.date().isoformat(),
                "next_trade_date": pd.Timestamp(next_bar.get("date")).date().isoformat() if next_bar else "",
                "product_vt_symbol": row.product_vt_symbol,
                "vt_symbol": vt_symbol,
                "direction": row.direction,
                "offset": row.offset,
                "exit_reason": "" if pd.isna(row.exit_reason) else row.exit_reason,
                "theoretical_price": theoretical_price,
                "volume": volume,
                "size": size,
                "price_tick": pricetick,
                "margin_ratio": margin_ratio,
                "theoretical_notional": theoretical_notional,
                "theoretical_margin": theoretical_margin,
                "same_day_close": _safe_float(same_bar.get("close") if same_bar else 0.0),
                "same_day_volume": _safe_float(same_bar.get("volume") if same_bar else 0.0),
                "next_open": next_open,
                "next_close": next_close,
                "next_high": next_high,
                "next_low": next_low,
                "next_volume": next_volume,
                "next_open_available": next_open_available,
                "next_close_available": next_close_available,
                "next_bar_missing": int(not bool(next_bar)),
                "next_zero_volume": zero_volume,
                "next_no_range": no_range,
                "next_open_adverse_price": next_open_adverse_price,
                "next_open_adverse_ticks": next_open_adverse_price / pricetick if pricetick else 0.0,
                "next_open_adverse_cash": _execution_impact(
                    direction=str(row.direction),
                    executable_price=next_open,
                    theoretical_price=theoretical_price,
                    volume=volume,
                    size=size,
                )
                if next_open_available
                else 0.0,
                "next_close_adverse_price": next_close_adverse_price,
                "next_close_adverse_ticks": next_close_adverse_price / pricetick if pricetick else 0.0,
                "next_close_adverse_cash": _execution_impact(
                    direction=str(row.direction),
                    executable_price=next_close,
                    theoretical_price=theoretical_price,
                    volume=volume,
                    size=size,
                )
                if next_close_available
                else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _build_daily_ledger(inputs: dict[str, Any], trade_ledger: pd.DataFrame) -> pd.DataFrame:
    daily = inputs["daily"].copy()
    risk = inputs["risk"].copy()
    candidates = inputs["candidates"].copy()
    ledger = trade_ledger.copy()
    ledger["date_ts"] = pd.to_datetime(ledger["date"]).dt.normalize()

    trade_daily = (
        ledger.groupby("date_ts", as_index=False)
        .agg(
            audited_trade_count=("trade_id", "count"),
            open_trade_count=("offset", lambda s: int((s == "Open").sum())),
            close_trade_count=("offset", lambda s: int((s == "Close").sum())),
            next_bar_missing_count=("next_bar_missing", "sum"),
            next_zero_volume_count=("next_zero_volume", "sum"),
            next_no_range_count=("next_no_range", "sum"),
            next_open_unavailable_count=("next_open_available", lambda s: int((s == 0).sum())),
            next_close_unavailable_count=("next_close_available", lambda s: int((s == 0).sum())),
            theoretical_notional=("theoretical_notional", "sum"),
            theoretical_margin=("theoretical_margin", "sum"),
            next_open_adverse_cash=("next_open_adverse_cash", "sum"),
            next_close_adverse_cash=("next_close_adverse_cash", "sum"),
            max_abs_next_open_adverse_ticks=("next_open_adverse_ticks", lambda s: float(np.nanmax(np.abs(s))) if len(s) else 0.0),
            max_abs_next_close_adverse_ticks=("next_close_adverse_ticks", lambda s: float(np.nanmax(np.abs(s))) if len(s) else 0.0),
        )
        .rename(columns={"date_ts": "date"})
    )

    risk_daily = (
        risk.groupby("date", as_index=False)
        .agg(
            entry_risk_count=("entry_index", "count"),
            max_estimated_equity=("estimated_equity", "max"),
            max_projected_total_margin_after=("projected_total_margin_after", "max"),
            max_actual_margin_amount=("actual_margin_amount", "max"),
            max_same_direction_corr=("same_direction_correlation_max_corr", "max"),
            max_portfolio_drawdown_pct=("portfolio_drawdown_pct", "min"),
        )
    )
    risk_daily["max_projected_margin_usage_pct"] = np.where(
        risk_daily["max_estimated_equity"] > 0,
        risk_daily["max_projected_total_margin_after"] / risk_daily["max_estimated_equity"] * 100.0,
        0.0,
    )

    candidate_daily = (
        candidates.groupby("date", as_index=False)
        .agg(
            candidate_count=("candidate_index", "count"),
            opened_candidate_count=("is_opened", "sum"),
            ai_allowed_count=("ai_product_pool_allowed", "sum"),
            max_candidate_projected_margin_after=("projected_total_margin_after", "max"),
        )
    )
    candidate_daily["ai_allowed_rate_pct"] = np.where(
        candidate_daily["candidate_count"] > 0,
        candidate_daily["ai_allowed_count"] / candidate_daily["candidate_count"] * 100.0,
        0.0,
    )

    result = daily.merge(trade_daily, on="date", how="left")
    result = result.merge(risk_daily, on="date", how="left")
    result = result.merge(candidate_daily, on="date", how="left")
    fill_columns = [column for column in result.columns if column not in {"date"}]
    for column in fill_columns:
        if pd.api.types.is_numeric_dtype(result[column]):
            result[column] = result[column].fillna(0.0)
        else:
            result[column] = result[column].fillna("")

    result["execution_status"] = "normal"
    result.loc[
        (result["next_bar_missing_count"] > 0)
        | (result["next_zero_volume_count"] > 0)
        | (result["next_open_unavailable_count"] > 0),
        "execution_status",
    ] = "execution_data_gap"
    result.loc[
        result["next_open_adverse_cash"] >= DAILY_ADVERSE_WARN_CASH,
        "execution_status",
    ] = "watch_next_open_adverse"
    result.loc[
        result["next_open_adverse_cash"] >= DAILY_ADVERSE_ALERT_CASH,
        "execution_status",
    ] = "alert_next_open_adverse"
    result.loc[
        result["max_projected_margin_usage_pct"] >= MARGIN_USAGE_WATCH_PCT,
        "execution_status",
    ] = "watch_margin_usage"
    result.loc[
        result["max_projected_margin_usage_pct"] >= MARGIN_USAGE_ALERT_PCT,
        "execution_status",
    ] = "alert_margin_usage"

    result["required_action"] = np.where(
        result["execution_status"].eq("normal"),
        "按影子盘常规记录，无需修改Stage78。",
        "复核当日成交价、成交量、保证金和持仓偏差；禁止直接改策略参数。",
    )
    return result


def _build_summary(trade_ledger: pd.DataFrame, daily_ledger: pd.DataFrame) -> dict[str, Any]:
    audited_trade_count = int(len(trade_ledger))
    open_available_rate = (
        float(trade_ledger["next_open_available"].mean() * 100.0) if audited_trade_count else 0.0
    )
    close_available_rate = (
        float(trade_ledger["next_close_available"].mean() * 100.0) if audited_trade_count else 0.0
    )
    status_counts = daily_ledger["execution_status"].value_counts().to_dict()
    worst_open_days = (
        daily_ledger.sort_values("next_open_adverse_cash", ascending=False)
        .head(10)[["date", "next_open_adverse_cash", "audited_trade_count", "execution_status"]]
        .to_dict(orient="records")
    )
    worst_margin_days = (
        daily_ledger.sort_values("max_projected_margin_usage_pct", ascending=False)
        .head(10)[["date", "max_projected_margin_usage_pct", "max_projected_total_margin_after", "execution_status"]]
        .to_dict(orient="records")
    )
    return {
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "is_strategy_change": False,
        "is_backtest": False,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "reference_metrics": OFFICIAL_STAGE78_REFERENCE_METRICS,
        "audited_trade_count": audited_trade_count,
        "next_open_available_rate_pct": open_available_rate,
        "next_close_available_rate_pct": close_available_rate,
        "next_bar_missing_count": int(trade_ledger["next_bar_missing"].sum()),
        "next_zero_volume_count": int(trade_ledger["next_zero_volume"].sum()),
        "next_no_range_count": int(trade_ledger["next_no_range"].sum()),
        "total_next_open_adverse_cash": float(trade_ledger["next_open_adverse_cash"].sum()),
        "total_next_close_adverse_cash": float(trade_ledger["next_close_adverse_cash"].sum()),
        "median_next_open_adverse_ticks": float(trade_ledger["next_open_adverse_ticks"].median()),
        "p95_abs_next_open_adverse_ticks": float(trade_ledger["next_open_adverse_ticks"].abs().quantile(0.95)),
        "max_daily_next_open_adverse_cash": float(daily_ledger["next_open_adverse_cash"].max()),
        "max_projected_margin_usage_pct": float(daily_ledger["max_projected_margin_usage_pct"].max()),
        "execution_status_counts": {str(key): int(value) for key, value in status_counts.items()},
        "worst_open_adverse_days": worst_open_days,
        "worst_margin_days": worst_margin_days,
        "judgement": {
            "overfit_before": "否。Stage154固定Stage78正式信号，只审计理论成交能否转成影子盘可执行记录。",
            "continue_before": "是。Stage153已经提示执行速度和资金路径左尾是主要风险，必须落到ledger。",
            "overfit_after": "否。本阶段没有引入交易规则，也没有根据执行审计反向调参。",
            "continue_after": "是。若ledger能稳定生成，下一步可接入真实每日行情和模拟盘回报，形成前向OOS闭环。",
        },
        "outputs": {
            "trade_ledger": str(TRADE_LEDGER_PATH),
            "daily_ledger": str(DAILY_LEDGER_PATH),
            "summary": str(SUMMARY_JSON_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(summary: dict[str, Any], trade_ledger: pd.DataFrame, daily_ledger: pd.DataFrame) -> None:
    reference = OFFICIAL_STAGE78_REFERENCE_METRICS["full_2020_2026"]
    status_df = pd.DataFrame(
        [{"execution_status": key, "days": value} for key, value in summary["execution_status_counts"].items()]
    )
    worst_open_df = pd.DataFrame(summary["worst_open_adverse_days"])
    worst_margin_df = pd.DataFrame(summary["worst_margin_days"])
    unavailable = trade_ledger[
        (trade_ledger["next_bar_missing"] > 0)
        | (trade_ledger["next_zero_volume"] > 0)
        | (trade_ledger["next_open_available"] == 0)
    ].head(20)

    lines = [
        "# Stage154 Stage78影子盘执行Ledger与可成交价审计",
        "",
        "## 定位",
        "",
        "- 本阶段不是新策略版本，不修改Stage78正式参数。",
        "- 目标是把Stage78正式回测成交拆成影子盘ledger，审计次日可成交价、成交量、执行冲击和保证金状态。",
        "",
        "## Stage78冻结基准",
        "",
        f"- 版本：`{OFFICIAL_STAGE78_VERSION}`",
        f"- 角色：`{OFFICIAL_STAGE78_ROLE}`",
        (
            f"- 全周期：期末权益 `{reference['end_balance']:,.0f}`，"
            f"总收益 `{reference['total_return_pct']:.4f}%`，"
            f"最大回撤 `{reference['max_dd_percent']:.4f}%`，"
            f"Sharpe `{reference['sharpe_ratio']:.4f}`，"
            f"总滑点 `{reference['total_slippage']:,.0f}`，"
            f"交易 `{reference['total_trade_count']:,.0f}`。"
        ),
        "",
        "## 汇总",
        "",
        f"- 审计成交数：`{summary['audited_trade_count']:,}`",
        f"- 次日开盘可成交率：`{summary['next_open_available_rate_pct']:.4f}%`",
        f"- 次日收盘可成交率：`{summary['next_close_available_rate_pct']:.4f}%`",
        f"- 次日bar缺失：`{summary['next_bar_missing_count']:,}`",
        f"- 次日零成交量：`{summary['next_zero_volume_count']:,}`",
        f"- 次日无波幅bar：`{summary['next_no_range_count']:,}`",
        f"- 次日开盘总执行冲击：`{summary['total_next_open_adverse_cash']:,.0f}`",
        f"- 次日收盘总执行冲击：`{summary['total_next_close_adverse_cash']:,.0f}`",
        f"- 次日开盘不利tick中位数：`{summary['median_next_open_adverse_ticks']:.4f}`",
        f"- 次日开盘不利tick绝对值P95：`{summary['p95_abs_next_open_adverse_ticks']:.4f}`",
        f"- 单日最大次日开盘不利冲击：`{summary['max_daily_next_open_adverse_cash']:,.0f}`",
        f"- 最大计划保证金占用率：`{summary['max_projected_margin_usage_pct']:.4f}%`",
        "",
        "## 日状态分布",
        "",
        _to_markdown_table(status_df, ["execution_status", "days"], max_rows=20),
        "",
        "## 次日开盘冲击最大日期",
        "",
        _to_markdown_table(
            worst_open_df,
            ["date", "next_open_adverse_cash", "audited_trade_count", "execution_status"],
            max_rows=10,
        ),
        "",
        "## 保证金占用最高日期",
        "",
        _to_markdown_table(
            worst_margin_df,
            ["date", "max_projected_margin_usage_pct", "max_projected_total_margin_after", "execution_status"],
            max_rows=10,
        ),
        "",
        "## 不可成交样本",
        "",
        _to_markdown_table(
            unavailable,
            ["trade_id", "date", "vt_symbol", "direction", "offset", "next_bar_missing", "next_zero_volume", "next_open_available"],
            max_rows=20,
        ),
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{summary['judgement']['overfit_before']}",
        f"- 运行前继续价值反思：{summary['judgement']['continue_before']}",
        f"- 运行后过拟合反思：{summary['judgement']['overfit_after']}",
        f"- 运行后继续价值反思：{summary['judgement']['continue_after']}",
        "",
        "## 后续TODO",
        "",
        "- 把本ledger从历史回测成交扩展到每日真实信号生成后的影子盘落表。",
        "- 加入真实订单回报、成交回报、撤单和持仓对账字段。",
        "- 对`alert_margin_usage`日期设计资金管理SOP，但不修改Stage78信号。",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    inputs = _load_inputs()
    trade_ledger = _build_trade_ledger(inputs)
    daily_ledger = _build_daily_ledger(inputs, trade_ledger)
    summary = _build_summary(trade_ledger, daily_ledger)

    trade_ledger.to_csv(TRADE_LEDGER_PATH, index=False, encoding="utf-8-sig")
    daily_ledger.to_csv(DAILY_LEDGER_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _write_report(summary, trade_ledger, daily_ledger)

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
