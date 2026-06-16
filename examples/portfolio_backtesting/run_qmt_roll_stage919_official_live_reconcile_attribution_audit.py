from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CURRENT_POSITIONS_PATH,
    OFFICIAL_LIVE_VERSION,
)
from qmt_roll_official_live_phase_d_config import (
    READONLY_POSITIONS_PATH,
    STAGE901_ENTRY_RISK_PATH,
    STAGE901_PENDING_ORDERS_PATH,
    STAGE901_TRADES_PATH,
)
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage919_official_live_reconcile_attribution_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage919_official_live_reconcile_attribution_audit"
STAGE260_MODEL_TAG = "stage260_official_live_daily_execution_gate_v1"
STAGE260_PREFIX = "qmt_roll_stage260_official_live_daily_execution_gate"
STAGE905_MODEL_TAG = "stage905_official_live_executor_dry_run_v1"
STAGE905_PREFIX = "qmt_roll_stage905_official_live_executor_dry_run"
STAGE906_MODEL_TAG = "stage906_official_live_reconciliation_worker_v1"
STAGE906_PREFIX = "qmt_roll_stage906_official_live_reconciliation_worker"
STAGE918_MODEL_TAG = "stage918_official_live_reconcile_policy_audit_v1"
STAGE918_PREFIX = "qmt_roll_stage918_official_live_reconcile_policy_audit"
STAGE901_MODEL_TAG = "stage901_stage847_c9_2026_ytd_live_shadow_v1"
STAGE901_PREFIX = "qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow"

STAGE901_POSITIONS_PATH = OUTPUT_DIR / f"{STAGE901_PREFIX}_positions_{STAGE901_MODEL_TAG}.csv"
STAGE901_TRADE_EVENTS_PATH = OUTPUT_DIR / f"{STAGE901_PREFIX}_trade_events_{STAGE901_MODEL_TAG}.csv"


def _date_key(target_date: str) -> str:
    return target_date.replace("-", "") if target_date else "latest"


def _paths(target_date: str) -> dict[str, Path]:
    date_key = _date_key(target_date)
    return {
        "evidence_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_evidence_{date_key}_{MODEL_TAG}.csv",
        "attribution_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_attribution_{date_key}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{date_key}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{date_key}_{MODEL_TAG}.md",
    }


def _target_path(prefix: str, stem: str, target_date: str, model_tag: str) -> Path:
    return OUTPUT_DIR / f"{prefix}_{stem}_{_date_key(target_date)}_{model_tag}.csv"


def _read_csv_maybe(path: str | Path | None) -> pd.DataFrame:
    if not path:
        return pd.DataFrame()
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(p, encoding="utf-8-sig")
    except EmptyDataError:
        return pd.DataFrame()


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _to_float(value: Any, default: float = 0.0) -> float:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return float(number)


def _normalize_direction(value: Any) -> str:
    text = _clean(value).lower()
    if text in {"long", "多", "direction.long"}:
        return "long"
    if text in {"short", "空", "direction.short"}:
        return "short"
    return text


def _normalize_offset(value: Any) -> str:
    text = _clean(value).lower()
    if text in {"open", "开", "offset.open"}:
        return "open"
    if text in {
        "close",
        "closetoday",
        "closeyesterday",
        "平",
        "平今",
        "平昨",
        "offset.close",
        "offset.closetoday",
        "offset.closeyesterday",
    }:
        return "close"
    return text


def _vt_symbol(row: dict[str, Any]) -> str:
    vt_symbol = _clean(row.get("vt_symbol"))
    if vt_symbol:
        return vt_symbol
    symbol = _clean(row.get("symbol") or row.get("instrument") or row.get("instrument_id"))
    exchange = _clean(row.get("exchange"))
    if symbol and exchange and "." not in symbol:
        return f"{symbol}.{exchange}"
    return symbol


def _direction_for_shadow_position(row: dict[str, Any]) -> str:
    direction = _normalize_direction(row.get("direction"))
    if direction:
        return direction
    end_pos = _to_float(row.get("end_pos", row.get("volume", 0.0)), 0.0)
    if end_pos > 0:
        return "long"
    if end_pos < 0:
        return "short"
    return ""


def _position_rows(frame: pd.DataFrame, *, source: str, shadow: bool) -> pd.DataFrame:
    columns = ["source", "vt_symbol", "direction", "volume", "avg_price", "pnl"]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    rows: list[dict[str, Any]] = []
    for row in frame.drop_duplicates().to_dict(orient="records"):
        vt_symbol = _vt_symbol(row)
        direction = _direction_for_shadow_position(row) if shadow else _normalize_direction(row.get("direction"))
        if shadow:
            volume = abs(_to_float(row.get("end_pos", row.get("volume", 0.0)), 0.0))
            avg_price = _to_float(row.get("close_price", row.get("price", 0.0)), 0.0)
            pnl = _to_float(row.get("net_pnl", row.get("total_pnl", 0.0)), 0.0)
        else:
            volume = max(
                0.0,
                _to_float(row.get("volume", row.get("position", row.get("pos", 0.0))), 0.0)
                - _to_float(row.get("frozen", 0.0), 0.0),
            )
            avg_price = _to_float(row.get("price", row.get("avg_price", 0.0)), 0.0)
            pnl = _to_float(row.get("pnl", 0.0), 0.0)
        if not vt_symbol or direction not in {"long", "short"} or volume <= 0:
            continue
        rows.append(
            {
                "source": source,
                "vt_symbol": vt_symbol,
                "direction": direction,
                "volume": volume,
                "avg_price": avg_price,
                "pnl": pnl,
            }
        )
    if not rows:
        return pd.DataFrame(columns=columns)
    out = pd.DataFrame(rows)
    return (
        out.groupby(["source", "vt_symbol", "direction"], as_index=False)
        .agg({"volume": "sum", "avg_price": "last", "pnl": "sum"})
        .loc[:, columns]
    )


def _opposite_direction(direction: str) -> str:
    if direction == "long":
        return "short"
    if direction == "short":
        return "long"
    return ""


def _evidence_row(
    rows: list[dict[str, Any]],
    *,
    evidence_type: str,
    source_file: Path,
    vt_symbol: str,
    direction: str = "",
    offset: str = "",
    date: str = "",
    price: float | str = "",
    volume: float | str = "",
    status: str = "",
    detail: str = "",
) -> None:
    rows.append(
        {
            "evidence_type": evidence_type,
            "source_file": source_file.name,
            "date": date,
            "vt_symbol": vt_symbol,
            "direction": direction,
            "offset": offset,
            "price": price,
            "volume": volume,
            "status": status,
            "detail": detail,
        }
    )


def _select_rows(df: pd.DataFrame, vt_symbol: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    columns = set(df.columns)
    mask = pd.Series(False, index=df.index)
    if "vt_symbol" in columns:
        mask |= df["vt_symbol"].astype(str).eq(vt_symbol)
    if "contract_vt_symbol" in columns:
        mask |= df["contract_vt_symbol"].astype(str).eq(vt_symbol)
    return df.loc[mask].copy()


def _last_shadow_open(trades: pd.DataFrame, vt_symbol: str, direction: str) -> dict[str, Any]:
    selected = _select_rows(trades, vt_symbol)
    if selected.empty:
        return {}
    selected["_offset_norm"] = selected.get("offset", pd.Series(dtype=str)).map(_normalize_offset)
    selected["_direction_norm"] = selected.get("direction", pd.Series(dtype=str)).map(_normalize_direction)
    selected = selected[selected["_offset_norm"].eq("open") & selected["_direction_norm"].eq(direction)]
    if selected.empty:
        return {}
    return selected.sort_values("datetime" if "datetime" in selected.columns else "date").iloc[-1].to_dict()


def _latest_entry_risk(entry_risk: pd.DataFrame, vt_symbol: str, direction: str) -> dict[str, Any]:
    selected = _select_rows(entry_risk, vt_symbol)
    if selected.empty:
        return {}
    selected["_direction_norm"] = selected.get("direction", pd.Series(dtype=str)).map(_normalize_direction)
    selected = selected[selected["_direction_norm"].eq(direction)]
    if selected.empty:
        return {}
    return selected.sort_values("datetime" if "datetime" in selected.columns else "date").iloc[-1].to_dict()


def _pending_close(pending_orders: pd.DataFrame, vt_symbol: str, position_direction: str) -> dict[str, Any]:
    selected = _select_rows(pending_orders, vt_symbol)
    if selected.empty:
        return {}
    selected["_offset_norm"] = selected.get("offset", pd.Series(dtype=str)).map(_normalize_offset)
    selected["_direction_norm"] = selected.get("direction", pd.Series(dtype=str)).map(_normalize_direction)
    close_direction = _opposite_direction(position_direction)
    selected = selected[selected["_offset_norm"].eq("close") & selected["_direction_norm"].eq(close_direction)]
    if selected.empty:
        return {}
    return selected.sort_values("datetime" if "datetime" in selected.columns else "date").iloc[-1].to_dict()


def _near_broker_avg_market_rows(positions: pd.DataFrame, vt_symbol: str, broker_avg: float, tolerance: float = 1.0) -> pd.DataFrame:
    selected = _select_rows(positions, vt_symbol)
    if selected.empty or broker_avg <= 0:
        return pd.DataFrame()
    selected["_close_gap"] = (pd.to_numeric(selected.get("close_price"), errors="coerce") - broker_avg).abs()
    selected = selected[selected["_close_gap"].le(tolerance)]
    if selected.empty:
        return pd.DataFrame()
    return selected.sort_values(["_close_gap", "date"]).head(5)


def _stage260_decisions_path(target_date: str) -> Path:
    return _target_path(STAGE260_PREFIX, "decisions", target_date, STAGE260_MODEL_TAG)


def _stage905_intents_path(target_date: str) -> Path:
    return _target_path(STAGE905_PREFIX, "intents", target_date, STAGE905_MODEL_TAG)


def _stage906_position_diff_path(target_date: str) -> Path:
    return _target_path(STAGE906_PREFIX, "position_diff", target_date, STAGE906_MODEL_TAG)


def _stage918_divergence_path(target_date: str) -> Path:
    return _target_path(STAGE918_PREFIX, "divergence", target_date, STAGE918_MODEL_TAG)


def _build_attribution(target_date: str) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    shadow_positions = _position_rows(_read_csv_maybe(OFFICIAL_LIVE_CURRENT_POSITIONS_PATH), source="shadow", shadow=True)
    broker_positions = _position_rows(_read_csv_maybe(READONLY_POSITIONS_PATH), source="broker", shadow=False)
    trades = _read_csv_maybe(STAGE901_TRADES_PATH)
    entry_risk = _read_csv_maybe(STAGE901_ENTRY_RISK_PATH)
    pending_orders = _read_csv_maybe(STAGE901_PENDING_ORDERS_PATH)
    trade_events = _read_csv_maybe(STAGE901_TRADE_EVENTS_PATH)
    strategy_positions = _read_csv_maybe(STAGE901_POSITIONS_PATH)
    stage260 = _read_csv_maybe(_stage260_decisions_path(target_date))
    stage905 = _read_csv_maybe(_stage905_intents_path(target_date))
    stage906 = _read_csv_maybe(_stage906_position_diff_path(target_date))
    stage918 = _read_csv_maybe(_stage918_divergence_path(target_date))

    keys = sorted(
        set(zip(shadow_positions.get("vt_symbol", pd.Series(dtype=str)), shadow_positions.get("direction", pd.Series(dtype=str))))
        | set(zip(broker_positions.get("vt_symbol", pd.Series(dtype=str)), broker_positions.get("direction", pd.Series(dtype=str))))
    )
    attribution_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    for vt_symbol, direction in keys:
        shadow_match = shadow_positions[shadow_positions["vt_symbol"].eq(vt_symbol) & shadow_positions["direction"].eq(direction)]
        broker_match = broker_positions[broker_positions["vt_symbol"].eq(vt_symbol) & broker_positions["direction"].eq(direction)]
        shadow_volume = float(shadow_match["volume"].sum()) if not shadow_match.empty else 0.0
        broker_volume = float(broker_match["volume"].sum()) if not broker_match.empty else 0.0
        shadow_mark = float(shadow_match["avg_price"].iloc[-1]) if not shadow_match.empty else 0.0
        broker_avg = float(broker_match["avg_price"].iloc[-1]) if not broker_match.empty else 0.0
        broker_pnl = float(broker_match["pnl"].sum()) if not broker_match.empty else 0.0
        delta = broker_volume - shadow_volume

        open_trade = _last_shadow_open(trades, vt_symbol, direction)
        entry = _latest_entry_risk(entry_risk, vt_symbol, direction)
        pending = _pending_close(pending_orders, vt_symbol, direction)
        near_market = _near_broker_avg_market_rows(strategy_positions, vt_symbol, broker_avg)
        stage260_match = _select_rows(stage260, vt_symbol)
        stage905_match = _select_rows(stage905, vt_symbol)
        stage906_match = _select_rows(stage906, vt_symbol)
        stage918_match = _select_rows(stage918, vt_symbol)
        trade_event_match = _select_rows(trade_events, vt_symbol)

        if not broker_match.empty:
            _evidence_row(
                evidence_rows,
                evidence_type="broker_position",
                source_file=READONLY_POSITIONS_PATH,
                vt_symbol=vt_symbol,
                direction=direction,
                price=broker_avg,
                volume=broker_volume,
                status="positions_received",
                detail=f"pnl={broker_pnl}",
            )
        if not shadow_match.empty:
            _evidence_row(
                evidence_rows,
                evidence_type="shadow_current_position",
                source_file=OFFICIAL_LIVE_CURRENT_POSITIONS_PATH,
                vt_symbol=vt_symbol,
                direction=direction,
                date=_clean(shadow_match.get("date", pd.Series([""])).iloc[-1]) if "date" in shadow_match else "",
                price=shadow_mark,
                volume=shadow_volume,
                status="shadow_position",
            )
        if open_trade:
            _evidence_row(
                evidence_rows,
                evidence_type="shadow_open_trade",
                source_file=STAGE901_TRADES_PATH,
                vt_symbol=vt_symbol,
                direction=_normalize_direction(open_trade.get("direction")),
                offset=_normalize_offset(open_trade.get("offset")),
                date=_clean(open_trade.get("date")),
                price=_to_float(open_trade.get("price"), 0.0),
                volume=_to_float(open_trade.get("volume"), 0.0),
                status=_clean(open_trade.get("trade_id")),
                detail="last C9 open trade for current shadow direction",
            )
        if entry:
            _evidence_row(
                evidence_rows,
                evidence_type="shadow_entry_risk",
                source_file=STAGE901_ENTRY_RISK_PATH,
                vt_symbol=vt_symbol,
                direction=_normalize_direction(entry.get("direction")),
                date=_clean(entry.get("date")),
                price=_to_float(entry.get("planned_entry_price", entry.get("entry_price")), 0.0),
                volume=_to_float(entry.get("selected_volume", entry.get("volume")), 0.0),
                status=f"stop={_to_float(entry.get('stop_price'), 0.0)}",
                detail=f"risk_multiplier={_to_float(entry.get('risk_multiplier'), 0.0)}",
            )
        if pending:
            _evidence_row(
                evidence_rows,
                evidence_type="shadow_pending_close",
                source_file=STAGE901_PENDING_ORDERS_PATH,
                vt_symbol=vt_symbol,
                direction=_normalize_direction(pending.get("direction")),
                offset=_normalize_offset(pending.get("offset")),
                date=_clean(pending.get("datetime") or pending.get("date")),
                price=_to_float(pending.get("price"), 0.0),
                volume=_to_float(pending.get("volume"), 0.0),
                status=_clean(pending.get("status")),
                detail="theoretical pending close; not broker order",
            )
        for _, row in trade_event_match.tail(5).iterrows():
            _evidence_row(
                evidence_rows,
                evidence_type="shadow_trade_event",
                source_file=STAGE901_TRADE_EVENTS_PATH,
                vt_symbol=vt_symbol,
                direction=_clean(row.get("direction")),
                offset=_clean(row.get("offset")),
                date=_clean(row.get("date")),
                price=_to_float(row.get("price"), 0.0),
                volume=_to_float(row.get("volume"), 0.0),
                status=_clean(row.get("reason")),
                detail="stage901 trade event near target symbol",
            )
        for _, row in near_market.iterrows():
            _evidence_row(
                evidence_rows,
                evidence_type="near_broker_avg_market_bar_no_shadow_position",
                source_file=STAGE901_POSITIONS_PATH,
                vt_symbol=vt_symbol,
                date=_clean(row.get("date")),
                price=_to_float(row.get("close_price"), 0.0),
                volume=_to_float(row.get("end_pos"), 0.0),
                status=f"gap={_to_float(row.get('_close_gap'), 0.0)}",
                detail="broker avg is near a historical market close where C9 held no position",
            )
        if not stage260_match.empty:
            row = stage260_match.iloc[0]
            _evidence_row(
                evidence_rows,
                evidence_type="stage260_gate",
                source_file=_stage260_decisions_path(target_date),
                vt_symbol=vt_symbol,
                direction=_clean(row.get("direction")),
                offset=_clean(row.get("offset")),
                price=_to_float(row.get("theoretical_price"), 0.0),
                volume=_to_float(row.get("planned_volume"), 0.0),
                status=_clean(row.get("execution_action")),
                detail=_clean(row.get("execution_reason")),
            )
        if not stage905_match.empty:
            row = stage905_match.iloc[0]
            _evidence_row(
                evidence_rows,
                evidence_type="stage905_executor_intent",
                source_file=_stage905_intents_path(target_date),
                vt_symbol=vt_symbol,
                direction=_clean(row.get("direction")),
                offset=_clean(row.get("offset")),
                price=_to_float(row.get("limit_price"), 0.0),
                volume=_to_float(row.get("planned_volume"), 0.0),
                status=_clean(row.get("executor_status")),
                detail=_clean(row.get("executor_reason")),
            )
        if not stage906_match.empty:
            row = stage906_match.iloc[0]
            _evidence_row(
                evidence_rows,
                evidence_type="stage906_position_diff",
                source_file=_stage906_position_diff_path(target_date),
                vt_symbol=vt_symbol,
                direction=_clean(row.get("direction")),
                volume=_to_float(row.get("delta_broker_minus_shadow"), 0.0),
                status=f"aligned={_clean(row.get('aligned'))}",
                detail=f"shadow={_to_float(row.get('shadow_volume'), 0.0)};broker={_to_float(row.get('broker_volume'), 0.0)}",
            )
        if not stage918_match.empty:
            row = stage918_match.iloc[0]
            _evidence_row(
                evidence_rows,
                evidence_type="stage918_policy",
                source_file=_stage918_divergence_path(target_date),
                vt_symbol=vt_symbol,
                direction=_clean(row.get("direction")),
                volume=_to_float(row.get("max_reduce_only_volume_for_manual_review"), 0.0),
                status=_clean(row.get("policy_status")),
                detail=_clean(row.get("policy_reason")),
            )

        open_price = _to_float(open_trade.get("price"), 0.0) if open_trade else 0.0
        open_volume = _to_float(open_trade.get("volume"), 0.0) if open_trade else 0.0
        entry_price = _to_float(entry.get("planned_entry_price", entry.get("entry_price")), 0.0) if entry else 0.0
        pending_volume = _to_float(pending.get("volume"), 0.0) if pending else 0.0
        pending_price = _to_float(pending.get("price"), 0.0) if pending else 0.0
        broker_matches_c9_open_price = int(open_price > 0 and abs(broker_avg - open_price) < 1e-9)
        broker_matches_c9_open_volume = int(open_volume > 0 and abs(broker_volume - open_volume) < 1e-9)
        c9_trade_price_match_broker_avg = 0
        if not trades.empty and broker_avg > 0:
            price_match = _select_rows(trades, vt_symbol)
            if not price_match.empty:
                c9_trade_price_match_broker_avg = int(
                    (pd.to_numeric(price_match.get("price"), errors="coerce") == broker_avg).any()
                )
        near_market_count = int(len(near_market))
        near_market_zero_position_count = int(
            (pd.to_numeric(near_market.get("end_pos"), errors="coerce").fillna(0.0).abs() < 1e-9).sum()
        ) if not near_market.empty else 0

        if abs(delta) < 1e-9:
            account_origin_status = "broker_shadow_aligned"
            auto_submit_permitted = 0
            fail_closed_required = 0
            attribution_reason = "broker and shadow volumes are aligned"
        elif shadow_volume > 0 and broker_volume > 0 and shadow_volume > broker_volume:
            account_origin_status = "broker_position_not_attributable_to_current_c9_shadow_open_fail_closed"
            auto_submit_permitted = 0
            fail_closed_required = 1
            attribution_reason = (
                "broker volume is smaller than C9 shadow, and broker avg price does not match "
                "the current C9 open trade"
            )
        elif shadow_volume > 0 and broker_volume <= 0:
            account_origin_status = "broker_flat_shadow_position_fail_closed"
            auto_submit_permitted = 0
            fail_closed_required = 1
            attribution_reason = "broker has no matching position for shadow close/reconcile"
        else:
            account_origin_status = "unclassified_reconcile_divergence_fail_closed"
            auto_submit_permitted = 0
            fail_closed_required = 1
            attribution_reason = "broker/shadow divergence is not safe for unattended handling"

        attribution_rows.append(
            {
                "target_date": target_date,
                "vt_symbol": vt_symbol,
                "direction": direction,
                "shadow_volume": shadow_volume,
                "broker_volume": broker_volume,
                "delta_broker_minus_shadow": delta,
                "shadow_mark_price": shadow_mark,
                "broker_avg_price": broker_avg,
                "broker_pnl": broker_pnl,
                "c9_open_trade_date": _clean(open_trade.get("date")) if open_trade else "",
                "c9_open_trade_price": open_price,
                "c9_open_trade_volume": open_volume,
                "c9_entry_risk_date": _clean(entry.get("date")) if entry else "",
                "c9_entry_planned_price": entry_price,
                "c9_entry_stop_price": _to_float(entry.get("stop_price"), 0.0) if entry else 0.0,
                "c9_pending_close_volume": pending_volume,
                "c9_pending_close_price": pending_price,
                "broker_matches_c9_open_price": broker_matches_c9_open_price,
                "broker_matches_c9_open_volume": broker_matches_c9_open_volume,
                "c9_trade_price_match_broker_avg": c9_trade_price_match_broker_avg,
                "near_broker_avg_market_row_count": near_market_count,
                "near_broker_avg_zero_position_count": near_market_zero_position_count,
                "account_origin_status": account_origin_status,
                "attribution_reason": attribution_reason,
                "auto_submit_permitted": auto_submit_permitted,
                "fail_closed_required": fail_closed_required,
            }
        )

    summary_counts = {
        "attribution_count": len(attribution_rows),
        "divergent_count": sum(abs(row["delta_broker_minus_shadow"]) > 1e-9 for row in attribution_rows),
        "fail_closed_required_count": sum(int(row["fail_closed_required"]) for row in attribution_rows),
        "auto_submit_permitted_count": sum(int(row["auto_submit_permitted"]) for row in attribution_rows),
    }
    return pd.DataFrame(attribution_rows), pd.DataFrame(evidence_rows), summary_counts


def _to_markdown(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "_empty_"
    return df.loc[:, [column for column in columns if column in df.columns]].to_markdown(index=False)


def _build_report(summary: dict[str, Any], attribution: pd.DataFrame, evidence: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Stage919 Official Live Reconcile Attribution Audit",
            "",
            f"- Generated at: `{summary['generated_at']}`",
            f"- Official live: `{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- Target date: `{summary['target_date']}`",
            f"- Attribution status: `{summary['attribution_status']}`",
            f"- Divergent count: `{summary['divergent_count']}`",
            f"- Auto submit permitted: `{summary['auto_submit_permitted']}`",
            f"- Order API calls: `{summary['order_api_called_count']}`",
            "",
            "## Attribution",
            "",
            _to_markdown(
                attribution,
                [
                    "vt_symbol",
                    "direction",
                    "shadow_volume",
                    "broker_volume",
                    "broker_avg_price",
                    "c9_open_trade_date",
                    "c9_open_trade_price",
                    "c9_open_trade_volume",
                    "c9_pending_close_volume",
                    "account_origin_status",
                    "auto_submit_permitted",
                ],
            ),
            "",
            "## Evidence",
            "",
            _to_markdown(
                evidence,
                [
                    "evidence_type",
                    "date",
                    "vt_symbol",
                    "direction",
                    "offset",
                    "price",
                    "volume",
                    "status",
                    "detail",
                ],
            ),
            "",
            "## Notes",
            "",
            "- Stage919 is read-only. It does not connect CTP, submit orders, or cancel orders.",
            "- A broker/shadow divergence is attributed before any reconciliation mode can be promoted.",
            "- Current fail-closed attribution deliberately blocks unattended reduce-only handling.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live broker/shadow divergence attribution audit.")
    parser.add_argument("--target-date", required=True)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(args.target_date)
    attribution, evidence, counts = _build_attribution(args.target_date)
    divergent_count = int(counts["divergent_count"])
    fail_closed_count = int(counts["fail_closed_required_count"])
    auto_submit_permitted = int(counts["auto_submit_permitted_count"] > 0)
    if divergent_count == 0:
        attribution_status = "reconcile_attribution_aligned"
    elif fail_closed_count > 0 and auto_submit_permitted == 0:
        attribution_status = "reconcile_attribution_divergent_origin_unresolved_fail_closed"
    else:
        attribution_status = "reconcile_attribution_blocked_fail_closed"
    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_date": args.target_date,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "attribution_status": attribution_status,
        "attribution_count": int(counts["attribution_count"]),
        "divergent_count": divergent_count,
        "fail_closed_required_count": fail_closed_count,
        "auto_submit_permitted": auto_submit_permitted,
        "reconcile_attribution_allows_auto_progress": int(divergent_count == 0 and auto_submit_permitted == 0),
        "fully_automatic_proven": 0,
        "order_api_called_count": 0,
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "source_files": {
            "broker_positions": str(READONLY_POSITIONS_PATH),
            "shadow_positions": str(OFFICIAL_LIVE_CURRENT_POSITIONS_PATH),
            "shadow_trades": str(STAGE901_TRADES_PATH),
            "shadow_entry_risk": str(STAGE901_ENTRY_RISK_PATH),
            "shadow_pending_orders": str(STAGE901_PENDING_ORDERS_PATH),
            "shadow_positions_daily": str(STAGE901_POSITIONS_PATH),
            "shadow_trade_events": str(STAGE901_TRADE_EVENTS_PATH),
            "stage260_decisions": str(_stage260_decisions_path(args.target_date)),
            "stage905_intents": str(_stage905_intents_path(args.target_date)),
            "stage906_position_diff": str(_stage906_position_diff_path(args.target_date)),
            "stage918_divergence": str(_stage918_divergence_path(args.target_date)),
        },
        "judgement": {
            "overfit_before": "No. Stage919 is an execution attribution audit, not a strategy-parameter change.",
            "continue_before": "Yes. Full automation needs account-origin attribution before any reconcile mode.",
            "overfit_after": "No. The audit only compares broker/shadow evidence and keeps order APIs at zero.",
            "continue_after": "Yes. The real account origin must be manually reconciled before unattended execution.",
        },
    }
    attribution.to_csv(paths["attribution_csv"], index=False, encoding="utf-8-sig")
    evidence.to_csv(paths["evidence_csv"], index=False, encoding="utf-8-sig")
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary, attribution, evidence), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
