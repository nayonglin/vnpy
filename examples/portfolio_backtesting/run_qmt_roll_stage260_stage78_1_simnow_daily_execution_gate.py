from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage260_stage78_1_simnow_daily_execution_gate_v1"
OUTPUT_PREFIX = "qmt_roll_stage260_stage78_1_simnow_daily_execution_gate"
STAGE188_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_stage188_stage78_2026_50w_latest_ai_pool_summary_stage188_stage78_2026_50w_latest_ai_pool_v1.json"
STAGE188_SIGNAL_PLAN_PATH = OUTPUT_DIR / "qmt_roll_stage188_stage78_2026_50w_latest_ai_pool_signal_plan_stage188_stage78_2026_50w_latest_ai_pool_v1.csv"
READONLY_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_summary_stage174_ctp_vnpy_readonly_probe_v1.json"

ACTIVE_ORDER_STATUSES = {
    "submitting",
    "submitted",
    "nottraded",
    "not traded",
    "parttraded",
    "part traded",
    "partial_filled",
    "提交中",
    "未成交",
    "部分成交",
}


def _paths(trade_date: str) -> dict[str, Path]:
    date_key = trade_date.replace("-", "")
    return {
        "decision_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_decisions_{date_key}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{date_key}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{date_key}_{MODEL_TAG}.md",
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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


def _parse_generated_at(value: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _clean_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def _to_float(value: Any, default: float = 0.0) -> float:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return float(number)


def _normalize_direction(value: Any) -> str:
    text = _clean_scalar(value).lower()
    mapping = {
        "long": "long",
        "多": "long",
        "direction.long": "long",
        "short": "short",
        "空": "short",
        "direction.short": "short",
    }
    return mapping.get(text, text)


def _normalize_offset(value: Any) -> str:
    text = _clean_scalar(value).lower()
    mapping = {
        "open": "open",
        "开": "open",
        "offset.open": "open",
        "close": "close",
        "平": "close",
        "offset.close": "close",
        "closetoday": "close",
        "平今": "close",
        "closeyesterday": "close",
        "平昨": "close",
    }
    return mapping.get(text, text)


def _column(df: pd.DataFrame, *candidates: str) -> pd.Series:
    for name in candidates:
        if name in df.columns:
            return df[name]
    return pd.Series([""] * len(df), index=df.index)


def _vt_symbol_series(df: pd.DataFrame) -> pd.Series:
    if "vt_symbol" in df.columns:
        vt_symbol = df["vt_symbol"].fillna("").astype(str).str.strip()
    else:
        vt_symbol = pd.Series([""] * len(df), index=df.index)
    if "symbol" in df.columns and "exchange" in df.columns:
        fallback = (
            df["symbol"].fillna("").astype(str).str.strip()
            + "."
            + df["exchange"].fillna("").astype(str).str.strip()
        )
    else:
        fallback = _column(df, "symbol")
    return vt_symbol.where(vt_symbol.ne(""), fallback)


def _latest_order_rows(orders: pd.DataFrame) -> pd.DataFrame:
    if orders.empty:
        return orders
    latest = orders.copy().reset_index(drop=False).rename(columns={"index": "_event_index"})
    if "vt_orderid" in latest.columns:
        key = latest["vt_orderid"].fillna("").astype(str).str.strip()
    else:
        key = pd.Series([""] * len(latest), index=latest.index)
    if "gateway_name" in latest.columns and "orderid" in latest.columns:
        fallback = (
            latest["gateway_name"].fillna("").astype(str).str.strip()
            + "."
            + latest["orderid"].fillna("").astype(str).str.strip()
        )
    else:
        fallback = _column(latest, "orderid")
    latest["_order_key"] = key.where(key.ne(""), fallback)
    latest = latest.sort_values("_event_index").groupby("_order_key", as_index=False, dropna=False).tail(1)
    return latest.drop(columns=["_event_index", "_order_key"], errors="ignore")


def _active_order_count(orders: pd.DataFrame) -> int:
    latest_orders = _latest_order_rows(orders)
    if latest_orders.empty or "status" not in latest_orders.columns:
        return 0
    status = latest_orders["status"].fillna("").astype(str).str.strip().str.lower()
    return int(status.isin(ACTIVE_ORDER_STATUSES).sum())


def _position_volume(positions: pd.DataFrame, vt_symbol: str, direction: str) -> float:
    if positions.empty:
        return 0.0
    pos_vt_symbol = _vt_symbol_series(positions).fillna("").astype(str).str.lower()
    pos_direction = _column(positions, "direction").map(_normalize_direction)
    pos_volume = pd.to_numeric(_column(positions, "volume", "pos", "position"), errors="coerce").fillna(0.0)
    return float(pos_volume[pos_vt_symbol.eq(vt_symbol.lower()) & pos_direction.eq(direction)].sum())


def _target_close_direction(signal_direction: str) -> str:
    if signal_direction == "short":
        return "long"
    if signal_direction == "long":
        return "short"
    return ""


def _decision_for_signal(
    row: dict[str, Any],
    risk_snapshot: dict[str, Any],
    readonly_gate: dict[str, Any],
    positions: pd.DataFrame,
    active_order_count: int,
) -> dict[str, Any]:
    reasons: list[str] = []
    action = "blocked"
    vt_symbol = _clean_scalar(row.get("vt_symbol"))
    direction = _normalize_direction(row.get("direction"))
    offset = _normalize_offset(row.get("offset"))
    volume = _to_float(row.get("volume"), 0.0)
    risk_level = _clean_scalar(risk_snapshot.get("risk_level"))
    allow_new_orders = int(_to_float(risk_snapshot.get("allow_real_new_orders"), 0.0))
    matching_position_volume = 0.0

    if not readonly_gate["passed"]:
        reasons.append("readonly_gate_not_passed")
    if active_order_count > 0:
        reasons.append(f"active_order_count={active_order_count}")
    if offset == "open" and risk_level == "review":
        reasons.append("review_blocks_new_open")
    if offset == "open" and allow_new_orders != 1:
        reasons.append("risk_snapshot_blocks_new_open")

    if offset == "close":
        target_position_direction = _target_close_direction(direction)
        matching_position_volume = _position_volume(positions, vt_symbol, target_position_direction)
        if matching_position_volume <= 0:
            reasons.append(f"no_matching_{target_position_direction}_position_to_close")
        elif matching_position_volume < volume:
            reasons.append(f"insufficient_position:{matching_position_volume:.4f}<{volume:.4f}")
    elif offset != "open":
        reasons.append(f"unsupported_offset={offset}")

    if not reasons:
        action = "simnow_executable"
    elif offset == "close" and all(reason.startswith("no_matching_") or reason.startswith("insufficient_position") for reason in reasons):
        action = "skip_broker_flat_for_close"

    return {
        "shadow_session_id": row.get("shadow_session_id", ""),
        "trade_id": row.get("trade_id", ""),
        "vt_symbol": vt_symbol,
        "direction": direction,
        "offset": offset,
        "planned_volume": volume,
        "theoretical_price": _to_float(row.get("theoretical_price"), 0.0),
        "exit_reason": row.get("exit_reason", ""),
        "risk_level": risk_level,
        "allow_real_new_orders": allow_new_orders,
        "readonly_gate_passed": int(bool(readonly_gate["passed"])),
        "broker_position_snapshot_state": readonly_gate.get("position_snapshot_state", ""),
        "broker_matching_position_volume": matching_position_volume,
        "broker_active_order_count": active_order_count,
        "execution_action": action,
        "execution_reason": ";".join(reasons),
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _to_markdown(df: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
    if df.empty:
        return "_empty_"
    view = df.loc[:, [col for col in columns if col in df.columns]].head(max_rows).copy()
    for col in view.columns:
        if pd.api.types.is_numeric_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{float(x):,.4f}" if abs(float(x)) < 1000 else f"{float(x):,.0f}")
    return view.to_markdown(index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage78-1 SimNow daily execution gate from latest shadow signal.")
    parser.add_argument("--max-snapshot-age-seconds", type=int, default=300)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage188_summary = _read_json(STAGE188_SUMMARY_PATH)
    signal_plan = _read_csv_maybe(STAGE188_SIGNAL_PLAN_PATH)
    readonly_summary = _read_json(READONLY_SUMMARY_PATH)
    readonly_outputs = readonly_summary.get("outputs", {})
    positions = _read_csv_maybe(readonly_outputs.get("positions"))
    orders = _read_csv_maybe(readonly_outputs.get("orders"))

    trade_date = str(stage188_summary.get("target_date", "latest"))
    paths = _paths(trade_date)
    generated_at = str(readonly_summary.get("generated_at", ""))
    generated_dt = _parse_generated_at(generated_at)
    snapshot_age_seconds = None
    if generated_dt:
        snapshot_age_seconds = round((datetime.now() - generated_dt).total_seconds(), 3)
    broker_snapshot = readonly_summary.get("broker_snapshot", {})
    position_state = str(broker_snapshot.get("position_snapshot_state", ""))
    readonly_gate = {
        "status": readonly_summary.get("status", ""),
        "position_snapshot_state": position_state,
        "generated_at": generated_at,
        "snapshot_age_seconds": snapshot_age_seconds,
        "passed": (
            readonly_summary.get("status") == "readonly_snapshots_received"
            and position_state in {"confirmed_flat", "positions_received"}
            and snapshot_age_seconds is not None
            and snapshot_age_seconds <= args.max_snapshot_age_seconds
        ),
    }
    active_orders = _active_order_count(orders)
    risk_snapshot = stage188_summary.get("risk_snapshot", {})
    decisions = pd.DataFrame(
        [
            _decision_for_signal(row, risk_snapshot, readonly_gate, positions, active_orders)
            for row in signal_plan.to_dict(orient="records")
        ]
    )
    executable_count = int(decisions["execution_action"].astype(str).eq("simnow_executable").sum()) if not decisions.empty else 0
    skipped_flat_count = int(decisions["execution_action"].astype(str).eq("skip_broker_flat_for_close").sum()) if not decisions.empty else 0
    blocked_count = int(decisions["execution_action"].astype(str).eq("blocked").sum()) if not decisions.empty else 0

    decisions.to_csv(paths["decision_csv"], index=False, encoding="utf-8-sig")
    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "trade_date": trade_date,
        "stage188_target_date": stage188_summary.get("target_date", ""),
        "stage188_generated_at": stage188_summary.get("generated_at", ""),
        "ai_pool_latest_eval_date": stage188_summary.get("ai_pool_audit", {}).get("max_eval_date", ""),
        "risk_snapshot": risk_snapshot,
        "readonly_gate": readonly_gate,
        "signal_count": int(len(signal_plan)),
        "executable_count": executable_count,
        "skipped_flat_count": skipped_flat_count,
        "blocked_count": blocked_count,
        "order_api_called_count": 0,
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "否。每日执行闸门只比较既有信号和SimNow持仓，不改策略参数。",
            "continue_before": "是。进入虚拟盘后必须把理论信号和真实账户状态逐笔对齐。",
            "overfit_after": "否。没有根据执行结果调整策略。",
            "continue_after": "是。若出现可执行信号，可进入SimNow委托草案和提交前复核。",
        },
    }
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    lines = [
        "# Stage260 Stage78-1 SimNow Daily Execution Gate",
        "",
        f"- 目标交易日：`{trade_date}`",
        f"- Stage188生成时间：`{stage188_summary.get('generated_at', '')}`",
        f"- AI池最新eval_date：`{summary['ai_pool_latest_eval_date']}`",
        f"- 风险级别：`{risk_snapshot.get('risk_level', '')}`",
        f"- 只读快照状态：`{readonly_gate['status']}` / `{readonly_gate['position_snapshot_state']}`",
        f"- 只读快照年龄秒数：`{readonly_gate['snapshot_age_seconds']}`",
        f"- 可执行信号数：`{executable_count}`",
        f"- 因账户空仓跳过平仓数：`{skipped_flat_count}`",
        f"- 阻断数：`{blocked_count}`",
        f"- 委托API调用次数：`0`",
        "",
        "## 执行判断",
        "",
        _to_markdown(
            decisions,
            [
                "vt_symbol",
                "direction",
                "offset",
                "planned_volume",
                "risk_level",
                "broker_position_snapshot_state",
                "broker_matching_position_volume",
                "broker_active_order_count",
                "execution_action",
                "execution_reason",
            ],
        ),
        "",
        "## 说明",
        "",
        "- 本阶段只做执行闸门，不发单。",
        "- `skip_broker_flat_for_close` 表示策略理论上要平仓，但SimNow账户没有对应持仓，不能对空仓发送平仓单。",
        "- `review` 风险级别允许降风险/平仓，但不允许新开仓。",
        "",
    ]
    paths["report_md"].write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
