from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage851"
MODEL_TAG = "stage851_stage850_pdeg_proxy_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage851_stage850_pdeg_proxy_audit"

STAGE847_PREFIX = "qmt_roll_stage847_stage830_c4_stop_retry_engine"
STAGE847_TAG = "stage847_stage830_c4_stop_retry_engine_v1"
STAGE849_PREFIX = "qmt_roll_stage849_stage848_pressure_path_forensics"
STAGE849_TAG = "stage849_stage848_pressure_path_forensics_v1"

C9_VARIANT = "stage847_stage819_c4_05r_stop_retry_once_2018"

ENTRY_RISK_PATH = OUTPUT_DIR / f"{STAGE847_PREFIX}_entry_risk_{STAGE847_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{STAGE847_PREFIX}_trades_{STAGE847_TAG}.csv"
CURVE_PATH = OUTPUT_DIR / f"{STAGE847_PREFIX}_curve_{STAGE847_TAG}.csv"
CLOSED_LOTS_PATH = OUTPUT_DIR / f"{STAGE847_PREFIX}_closed_lots_{STAGE847_TAG}.csv"
PRESSURE_PAIRS_PATH = OUTPUT_DIR / f"{STAGE849_PREFIX}_episode_lot_pairs_{STAGE849_TAG}.csv"

ENTRY_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_audit_{MODEL_TAG}.csv"
PRESSURE_MATCH_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pressure_pair_match_{MODEL_TAG}.csv"
CLOSED_MATCH_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lot_match_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _normal_date(value: Any) -> pd.Timestamp:
    if pd.isna(value):
        return pd.NaT
    text = str(value)
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        ts = pd.to_datetime(text[:10], errors="coerce")
    else:
        ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    if getattr(ts, "tzinfo", None) is not None:
        ts = pd.Timestamp(ts).tz_convert("Asia/Shanghai").tz_localize(None)
    return pd.Timestamp(ts).normalize()


def _normal_dt(value: Any) -> pd.Timestamp:
    if pd.isna(value):
        return pd.NaT
    ts = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(ts):
        return pd.NaT
    return pd.Timestamp(ts).tz_convert("Asia/Shanghai").tz_localize(None)


def _product_from_vt(vt_symbol: Any) -> str:
    text = str(vt_symbol)
    if "." not in text:
        return text
    contract, exchange = text.split(".", 1)
    letters = "".join(ch for ch in contract if ch.isalpha())
    return f"{letters}.{exchange}" if letters else text


def _numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _prepare_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    entry = _load_csv(ENTRY_RISK_PATH)
    trades = _load_csv(TRADES_PATH)
    curve = _load_csv(CURVE_PATH)
    closed = _load_csv(CLOSED_LOTS_PATH)
    pairs = _load_csv(PRESSURE_PAIRS_PATH)

    entry = entry[entry["variant"].astype(str).eq(C9_VARIANT)].copy()
    trades = trades[trades["variant"].astype(str).eq(C9_VARIANT)].copy()
    curve = curve[curve["variant"].astype(str).eq(C9_VARIANT)].copy()
    closed = closed[closed["variant"].astype(str).eq(C9_VARIANT)].copy()

    for frame in (entry, trades, curve, closed, pairs):
        for column in ("date", "entry_date", "exit_date"):
            if column in frame.columns:
                frame[column] = frame[column].map(_normal_date)

    entry["datetime_norm"] = entry["datetime"].map(_normal_dt)
    trades["datetime_norm"] = trades["datetime"].map(_normal_dt)
    trades["product"] = trades["vt_symbol"].map(_product_from_vt)
    closed["product"] = closed["vt_symbol"].map(_product_from_vt)

    return entry, trades, curve, closed, pairs


def _build_size_map(closed: pd.DataFrame) -> dict[str, float]:
    if closed.empty or "size" not in closed.columns:
        return {}
    data = closed[["vt_symbol", "size"]].dropna().drop_duplicates("vt_symbol", keep="last")
    return {str(row.vt_symbol): float(row.size) for row in data.itertuples(index=False)}


def _build_curve_map(curve: pd.DataFrame) -> tuple[pd.DataFrame, dict[pd.Timestamp, float]]:
    data = curve.copy()
    data["date"] = data["date"].map(_normal_date)
    data = data.sort_values("date")
    return data, {pd.Timestamp(row.date): float(row.account_equity) for row in data.itertuples(index=False)}


def _equity_on(date_value: Any, curve: pd.DataFrame, curve_map: dict[pd.Timestamp, float]) -> float:
    date = _normal_date(date_value)
    if pd.isna(date):
        return np.nan
    if date in curve_map:
        return float(curve_map[date])
    prev = curve[curve["date"].le(date)]
    if prev.empty:
        return np.nan
    return float(prev.iloc[-1]["account_equity"])


def _build_pdeg_proxy_entry_audit(
    entry: pd.DataFrame,
    trades: pd.DataFrame,
    curve: pd.DataFrame,
    curve_map: dict[pd.Timestamp, float],
    size_map: dict[str, float],
) -> pd.DataFrame:
    trade_records = list(trades.sort_values("datetime_norm").itertuples(index=False))
    entry_sorted = entry.sort_values("datetime_norm").copy()

    positions: dict[str, float] = {}
    last_price: dict[str, float] = {}
    last_key_flat_equity: dict[str, float] = {}
    trade_index = 0
    rows: list[dict[str, Any]] = []

    def apply_trade(trade: Any) -> None:
        vt_symbol = str(trade.vt_symbol)
        product = _product_from_vt(vt_symbol)
        signed_volume = _safe_float(trade.signed_volume, 0.0)
        positions[vt_symbol] = positions.get(vt_symbol, 0.0) + signed_volume
        last_price[vt_symbol] = _safe_float(trade.price, 0.0)
        if abs(positions[vt_symbol]) < 1e-9:
            positions[vt_symbol] = 0.0

        equity = _equity_on(trade.date, curve, curve_map)
        for direction in ("long", "short"):
            has_key_position = False
            for other_vt, position in positions.items():
                if abs(position) <= 1e-9 or _product_from_vt(other_vt) != product:
                    continue
                if (direction == "long" and position > 0) or (direction == "short" and position < 0):
                    has_key_position = True
                    break
            if not has_key_position and np.isfinite(equity):
                last_key_flat_equity[f"{product}|{direction}"] = equity

    def exposure_after(entry_row: Any) -> tuple[int, float]:
        pos = dict(positions)
        prices = dict(last_price)
        vt_symbol = str(entry_row.contract_vt_symbol)
        direction = str(entry_row.direction)
        selected_volume = _safe_float(entry_row.selected_volume, 0.0)
        sign = 1.0 if direction == "long" else -1.0
        pos[vt_symbol] = pos.get(vt_symbol, 0.0) + sign * selected_volume
        prices[vt_symbol] = _safe_float(entry_row.entry_price, prices.get(vt_symbol, 0.0))

        exposure: dict[str, float] = {}
        for other_vt, position in pos.items():
            if abs(position) <= 1e-9:
                continue
            other_direction = "long" if position > 0 else "short"
            key = f"{_product_from_vt(other_vt)}|{other_direction}"
            price = abs(_safe_float(prices.get(other_vt), 0.0))
            size = _safe_float(size_map.get(other_vt, 1.0), 1.0)
            exposure[key] = exposure.get(key, 0.0) + abs(position) * price * size

        key = f"{_product_from_vt(vt_symbol)}|{direction}"
        if not exposure:
            return 0, 0.0
        key_exposure = exposure.get(key, 0.0)
        rank = 1 + sum(1 for value in exposure.values() if value > key_exposure)
        share = key_exposure / sum(exposure.values()) if sum(exposure.values()) > 0 else 0.0
        return int(rank), float(share)

    for entry_row in entry_sorted.itertuples(index=False):
        while (
            trade_index < len(trade_records)
            and pd.notna(trade_records[trade_index].datetime_norm)
            and trade_records[trade_index].datetime_norm < entry_row.datetime_norm
        ):
            apply_trade(trade_records[trade_index])
            trade_index += 1

        vt_symbol = str(entry_row.contract_vt_symbol)
        product = _product_from_vt(vt_symbol)
        direction = str(entry_row.direction)
        key = f"{product}|{direction}"
        estimated_equity = _safe_float(entry_row.estimated_equity)
        high_water = _safe_float(entry_row.portfolio_equity_high_water)
        last_flat = _safe_float(last_key_flat_equity.get(key))
        key_budget_equity = min(estimated_equity, last_flat) if np.isfinite(last_flat) else estimated_equity
        budget_equity_ratio = (
            key_budget_equity / estimated_equity
            if np.isfinite(key_budget_equity) and np.isfinite(estimated_equity) and estimated_equity > 0
            else np.nan
        )
        selected_volume = _safe_float(entry_row.selected_volume, 0.0)
        budget_volume = (
            math.floor(selected_volume * budget_equity_ratio + 1e-9)
            if np.isfinite(budget_equity_ratio)
            else selected_volume
        )
        volume_reduce = max(0.0, selected_volume - budget_volume)
        key_rank, key_share = exposure_after(entry_row)
        drawdown_mode = bool(np.isfinite(high_water) and np.isfinite(estimated_equity) and estimated_equity < high_water)
        flagged = bool(drawdown_mode and key_rank == 1 and volume_reduce > 0)

        rows.append(
            {
                "entry_risk_date": entry_row.date,
                "datetime": entry_row.datetime_norm,
                "vt_symbol": vt_symbol,
                "product": product,
                "direction": direction,
                "signal": getattr(entry_row, "signal", ""),
                "entry_price": _safe_float(entry_row.entry_price),
                "selected_volume": selected_volume,
                "budget_volume_proxy": budget_volume,
                "volume_reduce_proxy": volume_reduce,
                "estimated_equity": estimated_equity,
                "portfolio_equity_high_water": high_water,
                "last_key_flat_equity_proxy": last_flat,
                "key_budget_equity_proxy": key_budget_equity,
                "budget_equity_ratio": budget_equity_ratio,
                "portfolio_drawdown_pct": _safe_float(getattr(entry_row, "portfolio_drawdown_pct", np.nan)),
                "drawdown_mode": int(drawdown_mode),
                "key_rank_after_proxy": key_rank,
                "key_share_after_proxy": key_share,
                "key_is_top1_after_proxy": int(key_rank == 1),
                "flagged_pdeg_v0_proxy": int(flagged),
            }
        )

    return pd.DataFrame(rows)


def _match_audit_row(
    audit: pd.DataFrame,
    vt_symbol: str,
    direction: str,
    entry_date: pd.Timestamp,
    volume: float,
    entry_price: float,
) -> dict[str, Any]:
    candidates = audit[
        audit["vt_symbol"].astype(str).eq(str(vt_symbol))
        & audit["direction"].astype(str).eq(str(direction))
        & audit["entry_risk_date"].le(entry_date)
    ].copy()
    if candidates.empty:
        return {"matched": 0}
    candidates["days_to_entry"] = (entry_date - candidates["entry_risk_date"]).dt.days
    candidates = candidates[candidates["days_to_entry"].between(0, 5, inclusive="both")].copy()
    if candidates.empty:
        return {"matched": 0}
    candidates["volume_gap"] = (pd.to_numeric(candidates["selected_volume"], errors="coerce") - volume).abs()
    # `entry_price` in entry_risk can be planned/signal price, so price is a tie-breaker only.
    candidates["price_gap"] = np.nan
    if "entry_price" in candidates.columns:
        candidates["price_gap"] = (pd.to_numeric(candidates["entry_price"], errors="coerce") - entry_price).abs()
    candidates = candidates.sort_values(["volume_gap", "days_to_entry", "price_gap"], na_position="last")
    row = candidates.iloc[0].to_dict()
    row["matched"] = 1
    return row


def _match_pressure_pairs(audit: pd.DataFrame, pairs: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for pair in pairs.itertuples(index=False):
        matched = _match_audit_row(
            audit,
            str(pair.vt_symbol),
            str(pair.direction),
            _normal_date(pair.entry_date),
            _safe_float(pair.volume_C9, 0.0),
            _safe_float(pair.entry_price, np.nan),
        )
        row = {
            "pair_key": pair.pair_key,
            "episode_id": pair.episode_id,
            "vt_symbol": pair.vt_symbol,
            "product": pair.product,
            "direction": pair.direction,
            "pair_entry_date": _normal_date(pair.entry_date),
            "pair_exit_date": _normal_date(pair.exit_date),
            "pair_volume_C4": _safe_float(pair.volume_C4, 0.0),
            "pair_volume_C9": _safe_float(pair.volume_C9, 0.0),
            "pair_realized_pnl_delta_C9_minus_C4": _safe_float(pair.realized_pnl_delta_C9_minus_C4, 0.0),
        }
        for key, value in matched.items():
            row[f"audit_{key}"] = value
        rows.append(row)
    return pd.DataFrame(rows)


def _match_closed_lots(audit: pd.DataFrame, closed: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for lot in closed.itertuples(index=False):
        matched = _match_audit_row(
            audit,
            str(lot.vt_symbol),
            str(lot.direction),
            _normal_date(lot.entry_date),
            _safe_float(lot.volume, 0.0),
            _safe_float(lot.entry_price, np.nan),
        )
        row = {
            "lot_id": lot.lot_id,
            "vt_symbol": lot.vt_symbol,
            "product": lot.product,
            "direction": lot.direction,
            "entry_date": _normal_date(lot.entry_date),
            "exit_date": _normal_date(lot.exit_date),
            "volume": _safe_float(lot.volume, 0.0),
            "realized_pnl": _safe_float(lot.realized_pnl, 0.0),
            "r_multiple": _safe_float(lot.r_multiple, np.nan),
            "winner": int(_safe_float(getattr(lot, "winner", 0.0), 0.0)),
            "big_winner": int(_safe_float(getattr(lot, "big_winner", 0.0), 0.0)),
        }
        for key, value in matched.items():
            row[f"audit_{key}"] = value
        rows.append(row)
    return pd.DataFrame(rows)


def _summarize(entry_audit: pd.DataFrame, pressure_match: pd.DataFrame, closed_match: pd.DataFrame) -> pd.DataFrame:
    pressure_matched = pressure_match[pressure_match["audit_matched"].fillna(0).astype(int).eq(1)].copy()
    pressure_flagged = pressure_matched[pressure_matched["audit_flagged_pdeg_v0_proxy"].fillna(0).astype(int).eq(1)].copy()
    closed_matched = closed_match[closed_match["audit_matched"].fillna(0).astype(int).eq(1)].copy()
    closed_flagged = closed_matched[closed_matched["audit_flagged_pdeg_v0_proxy"].fillna(0).astype(int).eq(1)].copy()
    closed_unflagged = closed_matched[closed_matched["audit_flagged_pdeg_v0_proxy"].fillna(0).astype(int).eq(0)].copy()

    rows = [
        {
            "metric": "entry_risk_rows",
            "value": float(len(entry_audit)),
        },
        {
            "metric": "entry_flagged_rows",
            "value": float(entry_audit["flagged_pdeg_v0_proxy"].sum()),
        },
        {
            "metric": "entry_flag_rate",
            "value": float(entry_audit["flagged_pdeg_v0_proxy"].mean()) if not entry_audit.empty else np.nan,
        },
        {
            "metric": "pressure_pairs",
            "value": float(len(pressure_match)),
        },
        {
            "metric": "pressure_pairs_matched",
            "value": float(len(pressure_matched)),
        },
        {
            "metric": "pressure_pairs_flagged",
            "value": float(len(pressure_flagged)),
        },
        {
            "metric": "pressure_flagged_pair_pnl_delta",
            "value": float(pressure_flagged["pair_realized_pnl_delta_C9_minus_C4"].sum()) if not pressure_flagged.empty else 0.0,
        },
        {
            "metric": "pressure_unflagged_pair_pnl_delta",
            "value": float(
                pressure_matched[pressure_matched["audit_flagged_pdeg_v0_proxy"].fillna(0).astype(int).eq(0)][
                    "pair_realized_pnl_delta_C9_minus_C4"
                ].sum()
            )
            if not pressure_matched.empty
            else 0.0,
        },
        {
            "metric": "pressure_flagged_volume_reduce_proxy",
            "value": float(pressure_flagged["audit_volume_reduce_proxy"].sum()) if not pressure_flagged.empty else 0.0,
        },
        {
            "metric": "closed_lots",
            "value": float(len(closed_match)),
        },
        {
            "metric": "closed_lots_matched",
            "value": float(len(closed_matched)),
        },
        {
            "metric": "closed_lots_flagged",
            "value": float(len(closed_flagged)),
        },
        {
            "metric": "closed_flag_rate",
            "value": float(len(closed_flagged) / len(closed_matched)) if len(closed_matched) else np.nan,
        },
        {
            "metric": "closed_flagged_pnl",
            "value": float(closed_flagged["realized_pnl"].sum()) if not closed_flagged.empty else 0.0,
        },
        {
            "metric": "closed_unflagged_pnl",
            "value": float(closed_unflagged["realized_pnl"].sum()) if not closed_unflagged.empty else 0.0,
        },
        {
            "metric": "closed_flagged_big_winner_count",
            "value": float(closed_flagged["big_winner"].sum()) if not closed_flagged.empty else 0.0,
        },
        {
            "metric": "closed_unflagged_big_winner_count",
            "value": float(closed_unflagged["big_winner"].sum()) if not closed_unflagged.empty else 0.0,
        },
        {
            "metric": "closed_flagged_big_winner_pnl",
            "value": float(closed_flagged.loc[closed_flagged["big_winner"].eq(1), "realized_pnl"].sum())
            if not closed_flagged.empty
            else 0.0,
        },
        {
            "metric": "closed_unflagged_big_winner_pnl",
            "value": float(closed_unflagged.loc[closed_unflagged["big_winner"].eq(1), "realized_pnl"].sum())
            if not closed_unflagged.empty
            else 0.0,
        },
    ]
    return pd.DataFrame(rows)


def _decision(summary: pd.DataFrame) -> dict[str, Any]:
    values = {str(row.metric): float(row.value) for row in summary.itertuples(index=False)}
    pressure_pairs = int(values.get("pressure_pairs", 0.0))
    pressure_flagged = int(values.get("pressure_pairs_flagged", 0.0))
    entry_flag_rate = values.get("entry_flag_rate", np.nan)
    closed_flag_rate = values.get("closed_flag_rate", np.nan)
    closed_flagged_big_winners = values.get("closed_flagged_big_winner_count", 0.0)
    closed_flagged_pnl = values.get("closed_flagged_pnl", 0.0)

    catches_pressure = pressure_pairs > 0 and pressure_flagged >= max(1, pressure_pairs - 1)
    too_broad = (
        (np.isfinite(entry_flag_rate) and entry_flag_rate > 0.35)
        or (np.isfinite(closed_flag_rate) and closed_flag_rate > 0.35)
        or closed_flagged_big_winners > 0
        or closed_flagged_pnl > 0
    )
    if catches_pressure and too_broad:
        label = "stage851_pdeg_proxy_catches_pressure_but_too_broad_no_engine"
        next_step = "Do not implement PDEG-v0 as designed. Either stop this branch or redesign from a stronger first-principles budget anchor without new thresholds."
    elif catches_pressure:
        label = "stage851_pdeg_proxy_candidate_can_enter_engine_design_review"
        next_step = "Only then consider a frozen engine implementation."
    else:
        label = "stage851_pdeg_proxy_does_not_catch_pressure_stop_branch"
        next_step = "Stop product-direction exposure guard branch."

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "line_id": LINE_ID,
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": label,
        "catches_pressure": int(catches_pressure),
        "too_broad": int(too_broad),
        "metrics": values,
        "next_step": next_step,
        "inputs": {
            "entry_risk": str(ENTRY_RISK_PATH),
            "trades": str(TRADES_PATH),
            "curve": str(CURVE_PATH),
            "closed_lots": str(CLOSED_LOTS_PATH),
            "pressure_pairs": str(PRESSURE_PAIRS_PATH),
        },
        "outputs": {
            "entry_audit": str(ENTRY_AUDIT_PATH),
            "pressure_match": str(PRESSURE_MATCH_PATH),
            "closed_match": str(CLOSED_MATCH_PATH),
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _write_report(
    summary: pd.DataFrame,
    pressure_match: pd.DataFrame,
    closed_match: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    pressure_view_cols = [
        "episode_id",
        "vt_symbol",
        "direction",
        "pair_entry_date",
        "pair_volume_C4",
        "pair_volume_C9",
        "audit_selected_volume",
        "audit_budget_volume_proxy",
        "audit_volume_reduce_proxy",
        "audit_drawdown_mode",
        "audit_key_rank_after_proxy",
        "audit_budget_equity_ratio",
        "audit_flagged_pdeg_v0_proxy",
        "pair_realized_pnl_delta_C9_minus_C4",
    ]
    pressure_view = pressure_match[[column for column in pressure_view_cols if column in pressure_match.columns]].copy()
    closed_groups = (
        closed_match.assign(flagged=closed_match["audit_flagged_pdeg_v0_proxy"].fillna(0).astype(int))
        .groupby("flagged", dropna=False)
        .agg(
            lots=("lot_id", "count"),
            pnl=("realized_pnl", "sum"),
            winners=("winner", "sum"),
            big_winners=("big_winner", "sum"),
            volume=("volume", "sum"),
        )
        .reset_index()
    )
    lines = [
        "# Stage851 Stage850 PDEG-v0 只读反事实审计",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- line_id：`{LINE_ID}`",
        f"- 决策标签：`{decision['decision']}`",
        "- 性质：只读代理审计；不改策略、不接引擎、不连接 CTP、不调用下单。",
        "",
        "## 方法",
        "",
        "- 读取 Stage847 C9 的 `entry_risk/trades/curve/closed_lots` 与 Stage849 pressure paired lots。",
        "- 用交易流水近似重建每个 `product+direction` 的最近 flat 权益和下单后产品方向敞口排名。",
        "- PDEG-v0 代理触发条件：账户离开权益高水位、该 key 下单后为最大产品方向敞口、按最近 flat 权益预算会压低手数。",
        "- 这是代理反事实，不是成交级真实引擎；它只检验规则形状是否值得进入引擎。",
        "",
        "## 聚合指标",
        "",
        _md_table(summary),
        "",
        "## Stage849 压力 paired lots 命中",
        "",
        _md_table(pressure_view, max_rows=40),
        "",
        "## 全样本 closed lots 粗分组",
        "",
        _md_table(closed_groups),
        "",
        "## 结论",
        "",
    ]
    if decision["decision"] == "stage851_pdeg_proxy_catches_pressure_but_too_broad_no_engine":
        lines.extend(
            [
                "- PDEG-v0 代理可以命中大多数 Stage849 压力 paired lots，但触发面过宽。",
                "- 触发组仍包含大量全样本 closed lots、正 PnL 和 big winner，这说明当前形状更像机械降风险，而不是精准的持仓后生存线。",
                "- 不应直接写真实引擎；如果继续，必须先重新定义更强的预算锚，但不能新增产品/年份/小数阈值。",
            ]
        )
    elif decision["decision"] == "stage851_pdeg_proxy_does_not_catch_pressure_stop_branch":
        lines.append("- PDEG-v0 代理不能命中 Stage849 压力 paired lots，应停止该分支。")
    else:
        lines.append("- PDEG-v0 代理初步通过只读审计，但仍需冻结引擎语义后再验证。")
    lines.extend(["", f"- 下一步：{decision['next_step']}"])
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    entry, trades, curve_raw, closed, pairs = _prepare_inputs()
    curve, curve_map = _build_curve_map(curve_raw)
    size_map = _build_size_map(closed)
    entry_audit = _build_pdeg_proxy_entry_audit(entry, trades, curve, curve_map, size_map)
    pressure_match = _match_pressure_pairs(entry_audit, pairs)
    closed_match = _match_closed_lots(entry_audit, closed)
    summary = _summarize(entry_audit, pressure_match, closed_match)
    decision = _decision(summary)

    entry_audit.to_csv(ENTRY_AUDIT_PATH, index=False, encoding="utf-8-sig")
    pressure_match.to_csv(PRESSURE_MATCH_PATH, index=False, encoding="utf-8-sig")
    closed_match.to_csv(CLOSED_MATCH_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, pressure_match, closed_match, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
