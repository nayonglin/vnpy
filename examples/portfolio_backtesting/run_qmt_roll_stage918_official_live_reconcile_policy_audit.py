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
    STAGE901_PENDING_ORDERS_PATH,
)
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage918_official_live_reconcile_policy_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage918_official_live_reconcile_policy_audit"
STAGE260_MODEL_TAG = "stage260_official_live_daily_execution_gate_v1"
STAGE260_PREFIX = "qmt_roll_stage260_official_live_daily_execution_gate"
STAGE906_MODEL_TAG = "stage906_official_live_reconciliation_worker_v1"
STAGE906_PREFIX = "qmt_roll_stage906_official_live_reconciliation_worker"


def _date_key(target_date: str) -> str:
    return target_date.replace("-", "") if target_date else "latest"


def _paths(target_date: str) -> dict[str, Path]:
    date_key = _date_key(target_date)
    return {
        "divergence_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_divergence_{date_key}_{MODEL_TAG}.csv",
        "manual_plan_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_manual_plan_{date_key}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{date_key}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{date_key}_{MODEL_TAG}.md",
    }


def _stage260_decisions_path(target_date: str) -> Path:
    return OUTPUT_DIR / f"{STAGE260_PREFIX}_decisions_{_date_key(target_date)}_{STAGE260_MODEL_TAG}.csv"


def _stage906_position_diff_path(target_date: str) -> Path:
    return OUTPUT_DIR / f"{STAGE906_PREFIX}_position_diff_{_date_key(target_date)}_{STAGE906_MODEL_TAG}.csv"


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
    if text in {"close", "closetoday", "closeyesterday", "平", "平今", "平昨", "offset.close", "offset.closetoday", "offset.closeyesterday"}:
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


def _position_rows(frame: pd.DataFrame, *, source: str, shadow: bool) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["source", "vt_symbol", "direction", "volume", "avg_price"])
    rows: list[dict[str, Any]] = []
    for row in frame.drop_duplicates().to_dict(orient="records"):
        vt_symbol = _vt_symbol(row)
        direction = _normalize_direction(row.get("direction"))
        if shadow:
            volume = _to_float(row.get("end_pos", row.get("volume", row.get("position", 0.0))), 0.0)
            avg_price = _to_float(row.get("close_price", row.get("price", 0.0)), 0.0)
        else:
            volume = max(0.0, _to_float(row.get("volume", row.get("position", row.get("pos", 0.0))), 0.0) - _to_float(row.get("frozen", 0.0), 0.0))
            avg_price = _to_float(row.get("price", row.get("avg_price", 0.0)), 0.0)
        if not vt_symbol or direction not in {"long", "short"} or volume <= 0:
            continue
        rows.append({"source": source, "vt_symbol": vt_symbol, "direction": direction, "volume": volume, "avg_price": avg_price})
    if not rows:
        return pd.DataFrame(columns=["source", "vt_symbol", "direction", "volume", "avg_price"])
    out = pd.DataFrame(rows)
    grouped = out.groupby(["source", "vt_symbol", "direction"], as_index=False).agg({"volume": "sum", "avg_price": "last"})
    return grouped


def _opposite_direction(direction: str) -> str:
    if direction == "long":
        return "short"
    if direction == "short":
        return "long"
    return ""


def _pending_close_map(pending_orders: pd.DataFrame) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    if pending_orders.empty:
        return out
    for row in pending_orders.drop_duplicates().to_dict(orient="records"):
        vt_symbol = _clean(row.get("vt_symbol"))
        order_direction = _normalize_direction(row.get("direction"))
        offset = _normalize_offset(row.get("offset"))
        if not vt_symbol or order_direction not in {"long", "short"} or offset != "close":
            continue
        position_direction = _opposite_direction(order_direction)
        key = (vt_symbol, position_direction)
        out[key] = {
            "pending_direction": order_direction,
            "pending_offset": offset,
            "pending_volume": _to_float(row.get("volume"), 0.0),
            "pending_price": _to_float(row.get("price"), 0.0),
            "pending_status": _clean(row.get("status")),
            "pending_vt_orderid": _clean(row.get("vt_orderid")),
        }
    return out


def _build_divergence(target_date: str) -> pd.DataFrame:
    shadow = _position_rows(_read_csv_maybe(OFFICIAL_LIVE_CURRENT_POSITIONS_PATH), source="shadow", shadow=True)
    broker = _position_rows(_read_csv_maybe(READONLY_POSITIONS_PATH), source="broker", shadow=False)
    pending_map = _pending_close_map(_read_csv_maybe(STAGE901_PENDING_ORDERS_PATH))
    stage260 = _read_csv_maybe(_stage260_decisions_path(target_date))
    stage906_diff = _read_csv_maybe(_stage906_position_diff_path(target_date))
    keys = sorted(
        set(zip(shadow.get("vt_symbol", pd.Series(dtype=str)), shadow.get("direction", pd.Series(dtype=str))))
        | set(zip(broker.get("vt_symbol", pd.Series(dtype=str)), broker.get("direction", pd.Series(dtype=str))))
    )
    rows: list[dict[str, Any]] = []
    for vt_symbol, direction in keys:
        shadow_match = shadow[shadow["vt_symbol"].eq(vt_symbol) & shadow["direction"].eq(direction)]
        broker_match = broker[broker["vt_symbol"].eq(vt_symbol) & broker["direction"].eq(direction)]
        shadow_volume = float(shadow_match["volume"].sum()) if not shadow_match.empty else 0.0
        broker_volume = float(broker_match["volume"].sum()) if not broker_match.empty else 0.0
        shadow_price = float(shadow_match["avg_price"].iloc[-1]) if not shadow_match.empty else 0.0
        broker_price = float(broker_match["avg_price"].iloc[-1]) if not broker_match.empty else 0.0
        pending = pending_map.get((vt_symbol, direction), {})
        stage260_match = stage260[stage260.get("vt_symbol", pd.Series(dtype=str)).astype(str).eq(vt_symbol)] if not stage260.empty else pd.DataFrame()
        stage260_action = _clean(stage260_match.get("execution_action", pd.Series([""])).iloc[0]) if not stage260_match.empty else ""
        stage260_reason = _clean(stage260_match.get("execution_reason", pd.Series([""])).iloc[0]) if not stage260_match.empty else ""
        delta = broker_volume - shadow_volume
        aligned = abs(delta) < 1e-9
        has_pending_close = bool(pending)
        max_reduce_only_volume = min(broker_volume, _to_float(pending.get("pending_volume"), 0.0)) if has_pending_close else 0.0
        if aligned:
            policy_status = "aligned_no_manual_action"
            auto_submit_permitted = 0
            manual_action_required = 0
            policy_reason = "broker_shadow_aligned"
        elif has_pending_close and broker_volume > 0 and shadow_volume > broker_volume:
            policy_status = "manual_review_reduce_only_candidate"
            auto_submit_permitted = 0
            manual_action_required = 1
            policy_reason = "broker_position_less_than_shadow_pending_close"
        elif shadow_volume > 0 and broker_volume <= 0:
            policy_status = "blocked_broker_flat_shadow_position"
            auto_submit_permitted = 0
            manual_action_required = 1
            policy_reason = "broker_flat_while_shadow_has_position"
        elif broker_volume > shadow_volume:
            policy_status = "blocked_broker_extra_position"
            auto_submit_permitted = 0
            manual_action_required = 1
            policy_reason = "broker_position_greater_than_shadow"
        else:
            policy_status = "blocked_unclassified_divergence"
            auto_submit_permitted = 0
            manual_action_required = 1
            policy_reason = "unclassified_shadow_broker_divergence"
        if not stage906_diff.empty:
            diff_match = stage906_diff[
                stage906_diff.get("vt_symbol", pd.Series(dtype=str)).astype(str).eq(vt_symbol)
                & stage906_diff.get("direction", pd.Series(dtype=str)).astype(str).str.lower().eq(direction)
            ]
            stage906_delta = _to_float(diff_match.get("delta_broker_minus_shadow", pd.Series([delta])).iloc[0], delta) if not diff_match.empty else delta
        else:
            stage906_delta = delta
        rows.append(
            {
                "target_date": target_date,
                "vt_symbol": vt_symbol,
                "direction": direction,
                "shadow_volume": shadow_volume,
                "broker_volume": broker_volume,
                "delta_broker_minus_shadow": delta,
                "stage906_delta_broker_minus_shadow": stage906_delta,
                "aligned": int(aligned),
                "shadow_price_or_mark": shadow_price,
                "broker_avg_price": broker_price,
                "pending_close_present": int(has_pending_close),
                "pending_direction": pending.get("pending_direction", ""),
                "pending_volume": pending.get("pending_volume", 0.0),
                "pending_price": pending.get("pending_price", 0.0),
                "pending_status": pending.get("pending_status", ""),
                "stage260_action": stage260_action,
                "stage260_reason": stage260_reason,
                "policy_status": policy_status,
                "policy_reason": policy_reason,
                "manual_action_required": manual_action_required,
                "auto_submit_permitted": auto_submit_permitted,
                "max_reduce_only_volume_for_manual_review": max_reduce_only_volume,
            }
        )
    return pd.DataFrame(rows)


def _manual_plan(divergence: pd.DataFrame) -> pd.DataFrame:
    if divergence.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for row in divergence.to_dict(orient="records"):
        if _clean(row.get("policy_status")) != "manual_review_reduce_only_candidate":
            continue
        rows.append(
            {
                "target_date": row.get("target_date", ""),
                "vt_symbol": row.get("vt_symbol", ""),
                "manual_only": 1,
                "auto_submit_permitted": 0,
                "draft_direction": row.get("pending_direction", ""),
                "draft_offset": "close",
                "draft_volume_cap": row.get("max_reduce_only_volume_for_manual_review", 0.0),
                "draft_price_reference": row.get("pending_price", 0.0),
                "reason": row.get("policy_reason", ""),
                "required_review": "confirm account origin and decide whether to reduce broker actual position only",
            }
        )
    return pd.DataFrame(rows)


def _to_markdown(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "_empty_"
    return df.loc[:, [column for column in columns if column in df.columns]].to_markdown(index=False)


def _build_report(summary: dict[str, Any], divergence: pd.DataFrame, manual_plan: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Stage918 Official Live Reconcile Policy Audit",
            "",
            f"- Generated at: `{summary['generated_at']}`",
            f"- Official live: `{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- Target date: `{summary['target_date']}`",
            f"- Policy status: `{summary['policy_status']}`",
            f"- Auto submit permitted: `{summary['auto_submit_permitted']}`",
            f"- Manual action candidates: `{summary['manual_action_candidate_count']}`",
            f"- Order API calls: `{summary['order_api_called_count']}`",
            "",
            "## Divergence",
            "",
            _to_markdown(
                divergence,
                [
                    "vt_symbol",
                    "direction",
                    "shadow_volume",
                    "broker_volume",
                    "delta_broker_minus_shadow",
                    "pending_volume",
                    "stage260_action",
                    "policy_status",
                    "auto_submit_permitted",
                    "max_reduce_only_volume_for_manual_review",
                ],
            ),
            "",
            "## Manual-Only Drafts",
            "",
            _to_markdown(
                manual_plan,
                [
                    "vt_symbol",
                    "manual_only",
                    "draft_direction",
                    "draft_offset",
                    "draft_volume_cap",
                    "draft_price_reference",
                    "required_review",
                ],
            ),
            "",
            "## Notes",
            "",
            "- Stage918 does not connect CTP, submit orders, or cancel orders.",
            "- A manual-only reduce candidate is not an unattended order permission.",
            "- Any broker/shadow volume mismatch keeps `auto_submit_permitted=0` until reconciliation policy is explicitly promoted.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live broker/shadow reconcile policy audit.")
    parser.add_argument("--target-date", required=True)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(args.target_date)
    divergence = _build_divergence(args.target_date)
    manual_plan = _manual_plan(divergence)
    auto_submit_permitted = int(not divergence.empty and divergence["auto_submit_permitted"].astype(int).min() == 1)
    divergent_count = int((divergence.get("aligned", pd.Series(dtype=int)).astype(int) == 0).sum()) if not divergence.empty else 0
    manual_count = int(len(manual_plan))
    if divergent_count == 0:
        policy_status = "reconcile_policy_aligned_no_action"
    elif manual_count > 0 and auto_submit_permitted == 0:
        policy_status = "reconcile_policy_manual_only_reduce_candidate_fail_closed"
    else:
        policy_status = "reconcile_policy_blocked_fail_closed"
    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_date": args.target_date,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "policy_status": policy_status,
        "divergent_count": divergent_count,
        "manual_action_candidate_count": manual_count,
        "auto_submit_permitted": auto_submit_permitted,
        "order_api_called_count": 0,
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "否。Stage918 是执行对账策略审计，不改 C9 参数。",
            "continue_before": "是。全自动前必须把 broker/shadow 差异归因并形成可审计 policy。",
            "overfit_after": "否。对账 policy 不反馈历史回测。",
            "continue_after": "是。下一步应人工确认真实账户起点与差异来源，再决定是否引入 reduce-only reconciliation mode。",
        },
    }
    divergence.to_csv(paths["divergence_csv"], index=False, encoding="utf-8-sig")
    manual_plan.to_csv(paths["manual_plan_csv"], index=False, encoding="utf-8-sig")
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary, divergence, manual_plan), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
