from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
from pandas.errors import EmptyDataError

from qmt_roll_official_execution_profile import (
    ExecutionStrategyMode,
    OfficialExecutionProfile,
    assert_profile_identity,
    resolve_execution_profile,
)
from qmt_roll_official_live_phase_d_config import STAGE901_PENDING_ORDERS_PATH
from qmt_roll_official_pending_artifact import (
    ValidatedArtifactSnapshot,
    load_validated_artifact_snapshot,
    materialize_validated_artifact_snapshot,
)
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage260_official_live_daily_execution_gate_v1"
OUTPUT_PREFIX = "qmt_roll_stage260_official_live_daily_execution_gate"
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


@dataclass(frozen=True)
class Stage260RunResult:
    decisions: pd.DataFrame
    summary: dict[str, Any]
    paths: Mapping[str, Path]


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


def _build_risk_snapshot(summary: Mapping[str, Any]) -> dict[str, Any]:
    variant = summary.get("current_variant", {}) or {}
    if not isinstance(variant, Mapping):
        variant = {}
    deployable = int(_to_float(variant.get("deployable_pass"), 0.0)) == 1
    days_over_100 = int(_to_float(variant.get("days_over_100pct"), 0.0))
    days_over_90 = int(_to_float(variant.get("days_over_90pct"), 0.0))
    max_margin = _to_float(
        variant.get("max_broker10_margin_to_equity_pct"),
        999.0,
    )
    reasons: list[str] = []
    if not deployable:
        reasons.append("official_live_deployable_gate_failed")
    if days_over_100 > 0:
        reasons.append("broker10_margin_over_100")
    if days_over_90 > 0:
        reasons.append("broker10_margin_over_90")
    if max_margin >= 90:
        reasons.append("broker10_margin_watch")
    if not reasons:
        reasons.append("official_live_profile_normal")
    allow_real_new_orders = int(
        deployable and days_over_100 == 0 and max_margin < 90
    )
    return {
        "risk_level": "normal" if allow_real_new_orders else "review",
        "allow_shadow_record": 1,
        "allow_real_new_orders": allow_real_new_orders,
        "reasons": reasons,
        "drawdown_pct_abs": abs(_to_float(variant.get("max_dd_pct"), 0.0)),
        "daily_loss_cash": 0.0,
        "net_pnl": 0.0,
        "balance": _to_float(variant.get("end_equity"), 0.0),
        "execution_adverse_cash": 0.0,
    }


def _validate_explicit_summary_identity(
    profile: OfficialExecutionProfile,
    summary: Mapping[str, Any],
) -> None:
    identity_fields = {
        "execution_profile",
        "official_live_version",
        "capital",
        "capital_label",
    }
    if not identity_fields.issubset(summary):
        raise ValueError("execution_profile_identity_missing")
    if _clean_scalar(summary.get("execution_profile")) != profile.profile_key:
        raise ValueError("execution_profile_key_mismatch")
    assert_profile_identity(
        profile,
        official_version=summary.get("official_live_version"),
        capital=summary.get("capital"),
        capital_label=summary.get("capital_label"),
    )


def _decision_id(
    profile: OfficialExecutionProfile,
    *,
    trade_date: str,
    row: Mapping[str, Any],
) -> str:
    payload = {
        "execution_profile": profile.profile_key,
        "official_live_version": profile.official_version,
        "pending_cohort_id": _clean_scalar(row.get("pending_cohort_id")),
        "trade_date": trade_date,
        "vt_symbol": _clean_scalar(row.get("vt_symbol")),
        "direction": _normalize_direction(row.get("direction")),
        "offset": _normalize_offset(row.get("offset")),
        "volume": _to_float(row.get("planned_volume", row.get("volume")), 0.0),
        "theoretical_price": _to_float(row.get("theoretical_price"), 0.0),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
    positions = positions.drop_duplicates().copy()
    pos_vt_symbol = _vt_symbol_series(positions).fillna("").astype(str).str.lower()
    pos_direction = _column(positions, "direction").map(_normalize_direction)
    pos_volume = pd.to_numeric(_column(positions, "volume", "pos", "position"), errors="coerce").fillna(0.0)
    return float(pos_volume[pos_vt_symbol.eq(vt_symbol.lower()) & pos_direction.eq(direction)].sum())


def _shadow_position_volume(current_positions: pd.DataFrame, vt_symbol: str, direction: str) -> float:
    if current_positions.empty or "vt_symbol" not in current_positions.columns:
        return 0.0
    frame = current_positions.copy()
    pos_vt_symbol = frame["vt_symbol"].fillna("").astype(str).str.lower()
    pos_direction = _column(frame, "direction").map(_normalize_direction)
    if "end_pos" in frame.columns:
        pos_volume = pd.to_numeric(frame["end_pos"], errors="coerce").fillna(0.0).abs()
    else:
        pos_volume = pd.to_numeric(_column(frame, "volume", "pos", "position"), errors="coerce").fillna(0.0).abs()
    return float(pos_volume[pos_vt_symbol.eq(vt_symbol.lower()) & pos_direction.eq(direction)].sum())


def _target_close_direction(signal_direction: str) -> str:
    if signal_direction == "short":
        return "long"
    if signal_direction == "long":
        return "short"
    return ""


def _execution_candidates(signal_plan: pd.DataFrame, pending_orders: pd.DataFrame) -> pd.DataFrame:
    if not pending_orders.empty:
        rows: list[dict[str, Any]] = []
        for row in pending_orders.to_dict(orient="records"):
            rows.append(
                {
                    "execution_source": "stage901_pending_order",
                    "shadow_session_id": "",
                    "trade_id": _clean_scalar(row.get("vt_orderid") or row.get("orderid")),
                    "vt_symbol": _clean_scalar(row.get("vt_symbol")),
                    "direction": row.get("direction", ""),
                    "offset": row.get("offset", ""),
                    "volume": row.get("volume", 0.0),
                    "theoretical_price": row.get("price", 0.0),
                    "exit_reason": row.get("status", ""),
                }
            )
        return pd.DataFrame(rows)
    if signal_plan.empty:
        return signal_plan
    out = signal_plan.copy()
    out["execution_source"] = "stage901_signal_plan"
    return out


def _decision_for_signal(
    row: dict[str, Any],
    risk_snapshot: dict[str, Any],
    readonly_gate: dict[str, Any],
    positions: pd.DataFrame,
    current_positions: pd.DataFrame,
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
    shadow_matching_position_volume = 0.0

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
    elif _clean_scalar(row.get("execution_source")) in {
        "stage901_signal_plan",
        "stage372_signal_plan",
    }:
        shadow_matching_position_volume = _shadow_position_volume(current_positions, vt_symbol, direction)
        if shadow_matching_position_volume >= volume > 0:
            reasons.append(f"shadow_position_already_contains_signal_open:{shadow_matching_position_volume:.4f}")

    if not reasons:
        action = "simnow_executable"
    elif offset == "close" and all(reason.startswith("no_matching_") for reason in reasons):
        action = "skip_broker_flat_for_close"
    elif offset == "close" and all(reason.startswith("no_matching_") or reason.startswith("insufficient_position") for reason in reasons):
        action = "skip_broker_position_mismatch_for_close"

    return {
        "execution_source": row.get("execution_source", "stage901_signal_plan"),
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
        "shadow_matching_position_volume": shadow_matching_position_volume,
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


def _build_report(
    summary: Mapping[str, Any],
    decisions: pd.DataFrame,
) -> str:
    risk_snapshot = summary["risk_snapshot"]
    readonly_gate = summary["readonly_gate"]
    lines = [
        "# Stage260 Official Live Daily Execution Gate",
        "",
        f"- 目标交易日：`{summary['trade_date']}`",
        f"- Execution profile：`{summary['execution_profile']}`",
        f"- 官方实盘版本：`{summary['official_live_version']}`",
        f"- 官方实盘别名：`{summary['official_live_alias']}`",
        f"- 官方影子生成时间：`{summary['official_summary_generated_at']}`",
        f"- AI池最新eval_date：`{summary['ai_pool_latest_eval_date']}`",
        f"- 风险级别：`{risk_snapshot.get('risk_level', '')}`",
        f"- signal_plan 行数：`{summary['signal_count']}`",
        f"- pending_order 行数：`{summary['pending_order_count']}`",
        f"- 执行候选来源：`{summary['execution_candidate_source']}`",
        f"- 只读快照状态：`{readonly_gate['status']}` / `{readonly_gate['position_snapshot_state']}`",
        f"- 只读快照年龄秒数：`{readonly_gate['snapshot_age_seconds']}`",
        f"- 可执行信号数：`{summary['executable_count']}`",
        f"- 因账户空仓跳过平仓数：`{summary['skipped_flat_count']}`",
        f"- 因账户持仓数量不匹配跳过平仓数：`{summary['skipped_position_mismatch_count']}`",
        f"- 阻断数：`{summary['blocked_count']}`",
        f"- 委托API调用次数：`0`",
        "",
        "## 执行判断",
        "",
        _to_markdown(
            decisions,
            [
                "execution_source",
                "vt_symbol",
                "direction",
                "offset",
                "planned_volume",
                "risk_level",
                "broker_position_snapshot_state",
                "broker_matching_position_volume",
                "shadow_matching_position_volume",
                "broker_active_order_count",
                "execution_action",
                "execution_reason",
            ],
        ),
        "",
        "## 说明",
        "",
        "- 本阶段只做执行闸门，不发单。",
        "- 本阶段优先读取当前 execution profile 的 pending orders；只有 pending 为空时才读取 `signal_plan`，避免漏掉最后一天 engine pending order 或重复执行已体现在 shadow 持仓里的历史开仓。",
        "- `skip_broker_flat_for_close` 表示策略理论上要平仓，但 broker 账户没有对应持仓，不能对空仓发送平仓单。",
        "- `skip_broker_position_mismatch_for_close` 表示 broker 账户有对应持仓但数量不足，不能按理论数量平仓。",
        "- `review` 风险级别允许降风险/平仓，但不允许新开仓。",
        "",
    ]
    return "\n".join(lines)


def run_daily_execution_gate(
    profile: OfficialExecutionProfile,
    *,
    official_summary: Mapping[str, Any] | None = None,
    signal_plan: pd.DataFrame | None = None,
    pending_orders: pd.DataFrame | None = None,
    current_positions: pd.DataFrame | None = None,
    artifact_snapshot: ValidatedArtifactSnapshot | None = None,
    readonly_summary: Mapping[str, Any],
    positions: pd.DataFrame,
    orders: pd.DataFrame,
    max_snapshot_age_seconds: int = 300,
    now: datetime | None = None,
    write_outputs: bool = True,
) -> Stage260RunResult:
    artifact_hashes: Mapping[str, str] = {}
    pending_cohort_id = ""
    if not profile.intraday_stop_retry_enabled:
        materialized = materialize_validated_artifact_snapshot(
            profile,
            artifact_snapshot,
        )
        official_summary = materialized.official_summary
        signal_plan = materialized.signal_plan
        current_positions = materialized.current_positions
        pending_orders = materialized.pending_orders
        artifact_hashes = materialized.artifact_hashes
        pending_cohort_id = _clean_scalar(
            materialized.audit.get("cohort_id")
        )
    else:
        official_summary = dict(official_summary or {})
        signal_plan = (
            signal_plan if signal_plan is not None else pd.DataFrame()
        )
        current_positions = (
            current_positions
            if current_positions is not None
            else pd.DataFrame()
        )
        pending_orders = (
            pending_orders if pending_orders is not None else pd.DataFrame()
        )
    _validate_explicit_summary_identity(profile, official_summary)
    trade_date = _clean_scalar(official_summary.get("analysis_end"))
    if not trade_date:
        raise ValueError("official_summary_analysis_end_missing")
    observed_now = now or datetime.now()
    candidates = _execution_candidates(signal_plan, pending_orders)
    if not profile.intraday_stop_retry_enabled and not candidates.empty:
        candidates = candidates.copy()
        candidates["execution_source"] = candidates["execution_source"].replace(
            {
                "stage901_pending_order": "stage372_pending_order",
                "stage901_signal_plan": "stage372_signal_plan",
            }
        )
    paths = _paths(trade_date)
    generated_at = str(readonly_summary.get("generated_at", ""))
    generated_dt = _parse_generated_at(generated_at)
    snapshot_age_seconds = None
    if generated_dt:
        snapshot_age_seconds = round(
            (observed_now - generated_dt).total_seconds(),
            3,
        )
    broker_snapshot = readonly_summary.get("broker_snapshot", {})
    if not isinstance(broker_snapshot, Mapping):
        broker_snapshot = {}
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
            and 0 <= snapshot_age_seconds <= max_snapshot_age_seconds
        ),
    }
    active_orders = _active_order_count(orders)
    risk_snapshot = _build_risk_snapshot(official_summary)
    decision_rows: list[dict[str, Any]] = []
    for raw in candidates.to_dict(orient="records"):
        row = _decision_for_signal(
            raw,
            risk_snapshot,
            readonly_gate,
            positions,
            current_positions,
            active_orders,
        )
        row.update(
            {
                "execution_profile": profile.profile_key,
                "official_live_version": profile.official_version,
                "capital": profile.capital,
                "capital_label": profile.capital_label,
                "trade_date": trade_date,
                "pending_cohort_id": pending_cohort_id,
                "upstream_execution_source": row.get("execution_source", ""),
                "intent_source": (
                    "stage260_stage372_daily"
                    if profile.profile_key
                    == ExecutionStrategyMode.STAGE372_20W.value
                    else row.get("execution_source", "")
                ),
            }
        )
        row["decision_id"] = _decision_id(
            profile,
            trade_date=trade_date,
            row=row,
        )
        decision_rows.append(row)
    decisions = pd.DataFrame(decision_rows)
    action = decisions.get("execution_action", pd.Series(dtype=str)).astype(str)
    executable_count = int(action.eq("simnow_executable").sum())
    skipped_flat_count = int(action.eq("skip_broker_flat_for_close").sum())
    skipped_position_mismatch_count = int(
        action.eq("skip_broker_position_mismatch_for_close").sum()
    )
    blocked_count = int(action.eq("blocked").sum())
    ai_pool_audit = official_summary.get("ai_pool_audit", {})
    if not isinstance(ai_pool_audit, Mapping):
        ai_pool_audit = {}
    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": observed_now.strftime("%Y-%m-%d %H:%M:%S"),
        "trade_date": trade_date,
        "execution_profile": profile.profile_key,
        "official_live_version": profile.official_version,
        "official_live_alias": profile.alias,
        "capital": profile.capital,
        "capital_label": profile.capital_label,
        "pending_cohort_id": pending_cohort_id,
        "pending_artifact_hashes": dict(artifact_hashes or {}),
        "official_summary_analysis_end": official_summary.get("analysis_end", ""),
        "official_summary_generated_at": official_summary.get("generated_at", ""),
        "ai_pool_latest_eval_date": ai_pool_audit.get("max_eval_date", ""),
        "risk_snapshot": risk_snapshot,
        "readonly_gate": readonly_gate,
        "signal_count": int(len(signal_plan)),
        "pending_order_count": int(len(pending_orders)),
        "execution_candidate_count": int(len(candidates)),
        "execution_candidate_source": (
            (
                "stage901_pending_order"
                if profile.intraday_stop_retry_enabled
                else "stage372_pending_order"
            )
            if not pending_orders.empty
            else (
                "stage901_signal_plan"
                if profile.intraday_stop_retry_enabled
                else "stage372_signal_plan"
            )
        ),
        "executable_count": executable_count,
        "skipped_flat_count": skipped_flat_count,
        "skipped_position_mismatch_count": skipped_position_mismatch_count,
        "blocked_count": blocked_count,
        "order_api_called_count": 0,
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "否。每日执行闸门只比较既有信号和 broker 持仓，不改策略参数。",
            "continue_before": "是。自动执行前必须把理论信号和真实账户状态逐笔对齐。",
            "overfit_after": "否。没有根据执行结果调整策略。",
            "continue_after": "是。可执行 decision 仍需进入 Stage905、账本和提交授权。",
        },
    }
    if write_outputs:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        decisions.to_csv(
            paths["decision_csv"],
            index=False,
            encoding="utf-8-sig",
        )
        paths["summary_json"].write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        paths["report_md"].write_text(
            _build_report(summary, decisions),
            encoding="utf-8",
        )
    return Stage260RunResult(
        decisions=decisions,
        summary=summary,
        paths=paths,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Official live daily execution gate from latest official live signal."
    )
    parser.add_argument("--max-snapshot-age-seconds", type=int, default=300)
    parser.add_argument(
        "--execution-profile",
        choices=[item.value for item in ExecutionStrategyMode],
        default=ExecutionStrategyMode.STAGE372_20W.value,
    )
    args = parser.parse_args()
    profile = resolve_execution_profile(args.execution_profile)
    readonly_summary = _read_json(READONLY_SUMMARY_PATH)
    readonly_outputs = readonly_summary.get("outputs", {})
    if not isinstance(readonly_outputs, Mapping):
        readonly_outputs = {}
    result = run_daily_execution_gate(
        profile,
        official_summary=(
            _read_json(profile.summary_path)
            if profile.intraday_stop_retry_enabled
            else None
        ),
        signal_plan=(
            _read_csv_maybe(profile.signal_plan_path)
            if profile.intraday_stop_retry_enabled
            else None
        ),
        pending_orders=(
            _read_csv_maybe(profile.pending_orders_path)
            if profile.intraday_stop_retry_enabled
            else None
        ),
        current_positions=(
            _read_csv_maybe(profile.current_positions_path)
            if profile.intraday_stop_retry_enabled
            else None
        ),
        artifact_snapshot=(
            None
            if profile.intraday_stop_retry_enabled
            else load_validated_artifact_snapshot(profile)
        ),
        readonly_summary=readonly_summary,
        positions=_read_csv_maybe(readonly_outputs.get("positions")),
        orders=_read_csv_maybe(readonly_outputs.get("orders")),
        max_snapshot_age_seconds=args.max_snapshot_age_seconds,
        write_outputs=True,
    )
    print(json.dumps(result.summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
