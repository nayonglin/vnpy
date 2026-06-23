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
    READONLY_ORDERS_PATH,
    READONLY_POSITIONS_PATH,
    READONLY_SUMMARY_PATH,
    READONLY_TRADES_PATH,
    STAGE901_PENDING_ORDERS_PATH,
    build_phase_d_config,
)
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage906_official_live_reconciliation_worker_v1"
OUTPUT_PREFIX = "qmt_roll_stage906_official_live_reconciliation_worker"
STAGE905_MODEL_TAG = "stage905_official_live_executor_dry_run_v1"
STAGE905_PREFIX = "qmt_roll_stage905_official_live_executor_dry_run"


def _paths(target_date: str) -> dict[str, Path]:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return {
        "checks_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{date_key}_{MODEL_TAG}.csv",
        "position_diff_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_position_diff_{date_key}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{date_key}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{date_key}_{MODEL_TAG}.md",
    }


def _stage905_intents_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE905_PREFIX}_intents_{date_key}_{STAGE905_MODEL_TAG}.csv"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


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


def _to_int(value: Any, default: int = 0) -> int:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return int(number)


def _parse_generated_at(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _age_seconds(value: Any) -> float | None:
    generated_at = _parse_generated_at(value)
    if generated_at is None:
        return None
    return round((datetime.now() - generated_at).total_seconds(), 3)


def _normalize_direction(value: Any) -> str:
    text = _clean(value).lower()
    if text in {"long", "多", "direction.long"}:
        return "long"
    if text in {"short", "空", "direction.short"}:
        return "short"
    return text


def _normalize_offset(value: Any) -> str:
    text = _clean(value).lower()
    if text in {
        "open",
        "开",
        "offset.open",
    }:
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


def _position_volume(row: dict[str, Any], *, shadow: bool) -> float:
    if shadow:
        return _to_float(row.get("end_pos", row.get("volume", row.get("position", 0.0))), 0.0)
    volume = _to_float(row.get("volume", row.get("position", row.get("pos", 0.0))), 0.0)
    frozen = _to_float(row.get("frozen", row.get("frozen_volume", 0.0)), 0.0)
    return max(0.0, volume - frozen)


def _dedupe_position_snapshots(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    key_columns = [
        column
        for column in (
            "vt_symbol",
            "symbol",
            "exchange",
            "instrument",
            "instrument_id",
            "direction",
            "volume",
            "position",
            "pos",
            "frozen",
            "frozen_volume",
            "yd_volume",
            "price",
        )
        if column in frame.columns
    ]
    if not key_columns:
        return frame.drop_duplicates()
    return frame.drop_duplicates(subset=key_columns, keep="last")


def _normalize_positions(frame: pd.DataFrame, *, source: str, shadow: bool) -> pd.DataFrame:
    if not frame.empty:
        frame = _dedupe_position_snapshots(frame)
    rows: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        vt_symbol = _vt_symbol(row)
        direction = _normalize_direction(row.get("direction"))
        volume = _position_volume(row, shadow=shadow)
        if not vt_symbol or direction not in {"long", "short"} or volume <= 0:
            continue
        rows.append(
            {
                "source": source,
                "vt_symbol": vt_symbol,
                "direction": direction,
                "volume": volume,
            }
        )
    if not rows:
        return pd.DataFrame(columns=["source", "vt_symbol", "direction", "volume"])
    out = pd.DataFrame(rows)
    return out.groupby(["source", "vt_symbol", "direction"], as_index=False)["volume"].sum()


def _position_map(frame: pd.DataFrame) -> dict[tuple[str, str], float]:
    if frame.empty:
        return {}
    return {
        (str(row["vt_symbol"]), str(row["direction"])): float(row["volume"])
        for row in frame.to_dict(orient="records")
    }


def _opposite_direction(direction: str) -> str:
    if direction == "long":
        return "short"
    if direction == "short":
        return "long"
    return ""


def _active_orders(orders: pd.DataFrame) -> pd.DataFrame:
    if orders.empty:
        return pd.DataFrame()
    frame = orders.copy()
    if "status" not in frame.columns:
        return pd.DataFrame()
    frame["_row_seq"] = range(len(frame))
    key_columns = [column for column in ("vt_orderid", "orderid") if column in frame.columns]
    if key_columns:
        key = frame[key_columns[0]].fillna("").astype(str).str.strip()
        for column in key_columns[1:]:
            key = key.mask(key.eq(""), frame[column].fillna("").astype(str).str.strip())
        fallback = frame.index.astype(str)
        key = key.mask(key.eq(""), fallback)
        frame["_order_key"] = key
        sort_columns = [column for column in ("datetime", "_row_seq") if column in frame.columns]
        frame = frame.sort_values(sort_columns).groupby("_order_key", as_index=False, sort=False).tail(1)
    active_status = {
        "submitting",
        "submitted",
        "not traded",
        "nottraded",
        "part traded",
        "parttraded",
        "未成交",
        "提交中",
        "部分成交",
    }
    mask = frame["status"].fillna("").astype(str).str.strip().str.lower().isin(active_status)
    return frame[mask].drop(columns=[column for column in ("_row_seq", "_order_key") if column in frame.columns]).copy()


def _check_row(
    rows: list[dict[str, Any]],
    *,
    check: str,
    status: str,
    severity: str,
    observed: Any,
    expected: Any,
    blocker: str = "",
) -> None:
    rows.append(
        {
            "check": check,
            "status": status,
            "severity": severity,
            "observed": observed,
            "expected": expected,
            "blocker": "" if status == "passed" else blocker,
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )


def _build_position_diff(shadow_positions: pd.DataFrame, broker_positions: pd.DataFrame) -> pd.DataFrame:
    shadow = _position_map(shadow_positions)
    broker = _position_map(broker_positions)
    keys = sorted(set(shadow) | set(broker))
    rows = []
    for vt_symbol, direction in keys:
        shadow_volume = float(shadow.get((vt_symbol, direction), 0.0))
        broker_volume = float(broker.get((vt_symbol, direction), 0.0))
        delta = broker_volume - shadow_volume
        rows.append(
            {
                "vt_symbol": vt_symbol,
                "direction": direction,
                "shadow_volume": shadow_volume,
                "broker_volume": broker_volume,
                "delta_broker_minus_shadow": delta,
                "aligned": int(abs(delta) < 1e-9),
            }
        )
    return pd.DataFrame(rows)


def _intent_checks(
    rows: list[dict[str, Any]],
    intents: pd.DataFrame,
    broker_positions: pd.DataFrame,
    *,
    broker_ready: bool,
) -> None:
    broker = _position_map(broker_positions)
    if intents.empty:
        _check_row(
            rows,
            check="executor_intents_present",
            status="passed",
            severity="info",
            observed=0,
            expected="0 or dry-run intents",
        )
        return
    for intent in intents.to_dict(orient="records"):
        intent_id = _clean(intent.get("intent_id"))
        vt_symbol = _clean(intent.get("vt_symbol"))
        direction = _normalize_direction(intent.get("direction"))
        offset = _normalize_offset(intent.get("offset"))
        volume = _to_float(intent.get("planned_volume"), 0.0)
        executor_status = _clean(intent.get("executor_status"))
        if executor_status == "blocked":
            _check_row(
                rows,
                check=f"executor_intent_{intent_id}",
                status="blocked",
                severity="block",
                observed=_clean(intent.get("executor_reason")),
                expected="executor intent ready before any automation",
                blocker="executor_intent_blocked",
            )
            continue
        if not broker_ready:
            _check_row(
                rows,
                check=f"executor_intent_{intent_id}",
                status="blocked",
                severity="block",
                observed="broker snapshot not fresh",
                expected="fresh broker snapshot before intent reconciliation",
                blocker="broker_snapshot_unusable_for_intent",
            )
            continue
        if offset == "close":
            match_direction = _opposite_direction(direction)
            available = broker.get((vt_symbol, match_direction), 0.0)
            passed = available >= volume > 0
            _check_row(
                rows,
                check=f"executor_intent_{intent_id}_matching_close_position",
                status="passed" if passed else "blocked",
                severity="block",
                observed=f"available={available};needed={volume};{vt_symbol} {match_direction}",
                expected="broker matching position >= close volume",
                blocker="intent_close_position_not_reconciled",
            )


def _pending_order_checks(
    rows: list[dict[str, Any]],
    pending_orders: pd.DataFrame,
    active_orders: pd.DataFrame,
    intents: pd.DataFrame,
    *,
    broker_ready: bool,
) -> None:
    if pending_orders.empty:
        _check_row(
            rows,
            check="stage901_pending_orders",
            status="passed",
            severity="info",
            observed=0,
            expected="0 or reconciled with broker active orders",
        )
        return
    active_count = int(len(active_orders))
    if not broker_ready:
        _check_row(
            rows,
            check="stage901_pending_orders_broker_visibility",
            status="blocked",
            severity="block",
            observed=f"pending={len(pending_orders)};broker_snapshot_unusable",
            expected="fresh broker orders snapshot to reconcile pending",
            blocker="pending_order_broker_visibility_unknown",
        )
    elif active_count <= 0:
        ready_intents = intents.copy()
        if not ready_intents.empty and "executor_status" in ready_intents.columns:
            ready_intents = ready_intents[ready_intents["executor_status"].astype(str).eq("dry_run_order_request_payload_ready")]
        rebuilt_count = 0
        for pending in pending_orders.to_dict(orient="records"):
            pending_vt_symbol = _clean(pending.get("vt_symbol"))
            pending_direction = _normalize_direction(pending.get("direction"))
            pending_offset = _normalize_offset(pending.get("offset"))
            pending_volume = _to_float(pending.get("volume"), 0.0)
            if ready_intents.empty:
                continue
            intent_vt_symbol = ready_intents.get("vt_symbol", pd.Series([""] * len(ready_intents), index=ready_intents.index)).fillna("").astype(str)
            intent_direction = ready_intents.get("direction", pd.Series([""] * len(ready_intents), index=ready_intents.index)).map(_normalize_direction)
            intent_offset = ready_intents.get("offset", pd.Series([""] * len(ready_intents), index=ready_intents.index)).map(_normalize_offset)
            intent_volume = pd.to_numeric(
                ready_intents.get("planned_volume", pd.Series([0.0] * len(ready_intents), index=ready_intents.index)),
                errors="coerce",
            ).fillna(0.0)
            matched = ready_intents[
                intent_vt_symbol.eq(pending_vt_symbol)
                & intent_direction.eq(pending_direction)
                & intent_offset.eq(pending_offset)
                & (intent_volume >= pending_volume)
            ]
            if not matched.empty:
                rebuilt_count += 1
        if rebuilt_count == len(pending_orders):
            _check_row(
                rows,
                check="stage901_pending_orders_broker_visibility",
                status="passed",
                severity="block",
                observed=f"pending={len(pending_orders)};active_broker_orders=0;rebuilt_ready_intents={rebuilt_count}",
                expected="pending theoretical orders rebuilt as ready executor intents before submit",
            )
            return
        _check_row(
            rows,
            check="stage901_pending_orders_broker_visibility",
            status="blocked",
            severity="block",
            observed=f"pending={len(pending_orders)};active_broker_orders=0;rebuilt_ready_intents={rebuilt_count}",
            expected="pending theoretical orders must be visible or rebuilt through gate",
            blocker="shadow_pending_not_visible_at_broker",
        )
    else:
        _check_row(
            rows,
            check="stage901_pending_orders_broker_visibility",
            status="watch",
            severity="warn",
            observed=f"pending={len(pending_orders)};active_broker_orders={active_count}",
            expected="manual vt_orderid/order_ref reconciliation still required",
            blocker="pending_order_needs_id_level_reconciliation",
        )


def _build_report(summary: dict[str, Any], checks: pd.DataFrame, position_diff: pd.DataFrame) -> str:
    def table(df: pd.DataFrame, columns: list[str]) -> str:
        if df.empty:
            return "_empty_"
        return df.loc[:, [column for column in columns if column in df.columns]].head(80).to_markdown(index=False)

    blocking = checks[checks["severity"].eq("block") & ~checks["status"].eq("passed")]
    return "\n".join(
        [
            "# Stage906 Official Live Reconciliation Worker",
            "",
            f"- 生成时间：`{summary['generated_at']}`",
            f"- 当前官方实盘：`{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- 目标日期：`{summary['target_date']}`",
            f"- 对账状态：`{summary['reconciliation_status']}`",
            f"- 账户对齐：`{summary['account_state_alignment']}`",
            f"- order API 调用次数：`{summary['order_api_called_count']}`",
            "",
            "## Blocking Checks",
            "",
            table(blocking, ["check", "status", "observed", "expected", "blocker"]),
            "",
            "## Position Diff",
            "",
            table(position_diff, ["vt_symbol", "direction", "shadow_volume", "broker_volume", "delta_broker_minus_shadow", "aligned"]),
            "",
            "## 说明",
            "",
            "- Stage906 只做对账，不连接 CTP，不调用 `send_order` 或 `cancel_order`。",
            "- broker 快照缺失、陈旧或状态不明确时，所有 pending/intent 都按 fail-closed 处理。",
            "- shadow 持仓不能替代 broker 持仓；平仓必须能在 broker 持仓快照中找到相反方向可用仓位。",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live Phase D reconciliation worker.")
    parser.add_argument("--target-date", required=True)
    parser.add_argument("--max-snapshot-age-seconds", type=int, default=300)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(args.target_date)
    config = build_phase_d_config()
    readonly_summary = _read_json(READONLY_SUMMARY_PATH)
    shadow_positions_raw = _read_csv_maybe(OFFICIAL_LIVE_CURRENT_POSITIONS_PATH)
    broker_positions_raw = _read_csv_maybe(READONLY_POSITIONS_PATH)
    broker_orders = _read_csv_maybe(READONLY_ORDERS_PATH)
    broker_trades = _read_csv_maybe(READONLY_TRADES_PATH)
    pending_orders = _read_csv_maybe(STAGE901_PENDING_ORDERS_PATH)
    intents = _read_csv_maybe(_stage905_intents_path(args.target_date))

    readonly_age = _age_seconds(readonly_summary.get("generated_at"))
    broker_snapshot = readonly_summary.get("broker_snapshot", {}) if isinstance(readonly_summary.get("broker_snapshot"), dict) else {}
    position_state = _clean(broker_snapshot.get("position_snapshot_state"))
    broker_ready = (
        readonly_summary.get("status") == "readonly_snapshots_received"
        and position_state in {"confirmed_flat", "positions_received"}
        and readonly_age is not None
        and readonly_age <= args.max_snapshot_age_seconds
    )
    shadow_positions = _normalize_positions(shadow_positions_raw, source="shadow", shadow=True)
    broker_positions = _normalize_positions(broker_positions_raw, source="broker", shadow=False)
    position_diff = _build_position_diff(shadow_positions, broker_positions)
    active_orders = _active_orders(broker_orders)

    checks: list[dict[str, Any]] = []
    _check_row(
        checks,
        check="broker_readonly_snapshot_usable",
        status="passed" if broker_ready else "blocked",
        severity="block",
        observed=f"status={readonly_summary.get('status', '')};state={position_state};age={readonly_age}",
        expected=f"readonly_snapshots_received and age<={args.max_snapshot_age_seconds}s",
        blocker="broker_snapshot_missing_stale_or_ambiguous",
    )
    if broker_ready:
        diff_blocked = bool(not position_diff.empty and not position_diff["aligned"].astype(bool).all())
        _check_row(
            checks,
            check="shadow_vs_broker_position_alignment",
            status="blocked" if diff_blocked else "passed",
            severity="block",
            observed=f"diff_rows={len(position_diff)};misaligned={int((position_diff.get('aligned', pd.Series(dtype=int)) == 0).sum()) if not position_diff.empty else 0}",
            expected="broker positions equal official shadow positions before unattended automation",
            blocker="shadow_broker_position_divergence",
        )
    else:
        _check_row(
            checks,
            check="shadow_vs_broker_position_alignment",
            status="blocked",
            severity="block",
            observed=f"shadow_rows={len(shadow_positions)};broker_rows={len(broker_positions)};broker_unusable",
            expected="fresh broker snapshot before position alignment",
            blocker="position_alignment_unknown_without_broker_snapshot",
        )
    _check_row(
        checks,
        check="active_broker_orders_clear",
        status="passed" if broker_ready and active_orders.empty else "blocked",
        severity="block",
        observed=f"active_orders={len(active_orders)};broker_ready={broker_ready}",
        expected="0 active broker orders before new unattended submit",
        blocker="active_orders_or_unknown_order_state",
    )
    _intent_checks(checks, intents, broker_positions, broker_ready=broker_ready)
    _pending_order_checks(checks, pending_orders, active_orders, intents, broker_ready=broker_ready)
    _check_row(
        checks,
        check="broker_trade_snapshot_loaded",
        status="passed" if broker_ready else "watch",
        severity="info",
        observed=f"trade_rows={len(broker_trades)}",
        expected="trade rows loaded when available",
    )
    _check_row(
        checks,
        check="no_order_api_called_by_stage906",
        status="passed",
        severity="info",
        observed=0,
        expected=0,
    )

    checks_df = pd.DataFrame(checks)
    blocking = checks_df[checks_df["severity"].eq("block") & ~checks_df["status"].eq("passed")]
    if not broker_ready:
        reconciliation_status = "reconcile_fail_closed_broker_snapshot_unusable"
        account_state_alignment = "unknown_stale_or_missing_broker"
    elif not blocking.empty:
        reconciliation_status = "reconcile_divergent_fail_closed"
        account_state_alignment = "divergent"
    else:
        reconciliation_status = "reconcile_aligned"
        account_state_alignment = "aligned"

    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_date": args.target_date,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "reconciliation_status": reconciliation_status,
        "account_state_alignment": account_state_alignment,
        "broker_snapshot_ready": int(broker_ready),
        "readonly_status": readonly_summary.get("status", ""),
        "readonly_snapshot_age_seconds": readonly_age,
        "position_snapshot_state": position_state,
        "shadow_position_rows": int(len(shadow_positions)),
        "broker_position_rows": int(len(broker_positions)),
        "position_diff_rows": int(len(position_diff)),
        "active_broker_order_count": int(len(active_orders)),
        "pending_order_count": int(len(pending_orders)),
        "executor_intent_count": int(len(intents)),
        "blocking_failure_count": int(len(blocking)),
        "order_api_called_count": 0,
        "phase_d_hard_limits": config.hard_limits.__dict__,
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "否。Stage906 是账户/委托对账，不改策略参数或样本。",
            "continue_before": "是。全自动必须先证明 shadow、broker、intent 三者一致。",
            "overfit_after": "否。对账结果只影响执行闸门，不反馈优化 C9。",
            "continue_after": "是。下一步应把 Stage906 接入 Stage903，并补 read-only refresh/Stage260 自动刷新。",
        },
    }

    checks_df.to_csv(paths["checks_csv"], index=False, encoding="utf-8-sig")
    position_diff.to_csv(paths["position_diff_csv"], index=False, encoding="utf-8-sig")
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary, checks_df, position_diff), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
