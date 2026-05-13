from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from run_qmt_alignment_backtest import OUTPUT_DIR
from vnpy.trader.constant import Direction, Exchange, Offset, OrderType
from vnpy.trader.object import OrderRequest


MODEL_TAG = "stage250_phaseb_vnpy_order_request_builder_v1"
APPROVAL_TAG = "stage243_phaseb_approval_v1"
APPROVAL_PREFIX = "qmt_roll_stage243_phaseb_approval"
CONTRACT_PATH = OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_contracts_stage174_ctp_vnpy_readonly_probe_v1.csv"
CONFIRM_TEXT = "I_UNDERSTAND_THIS_SENDS_REAL_ORDERS"


def _paths(trade_date: str, mode: str) -> dict[str, Path]:
    date_key = trade_date.replace("-", "")
    mode_key = mode.replace("-", "_")
    return {
        "approval_csv": OUTPUT_DIR / f"{APPROVAL_PREFIX}_ledger_{date_key}_{APPROVAL_TAG}.csv",
        "contracts_csv": CONTRACT_PATH,
        "result_csv": OUTPUT_DIR / f"qmt_roll_stage250_phaseb_vnpy_order_request_builder_{mode_key}_results_{date_key}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"qmt_roll_stage250_phaseb_vnpy_order_request_builder_{mode_key}_summary_{date_key}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"qmt_roll_stage250_phaseb_vnpy_order_request_builder_{mode_key}_report_{date_key}_{MODEL_TAG}.md",
    }


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


def _to_int_flag(value: Any) -> int:
    return 1 if int(_to_float(value, 0.0)) == 1 else 0


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _split_vt_symbol(vt_symbol: str) -> tuple[str, str]:
    if "." not in vt_symbol:
        return vt_symbol, ""
    symbol, exchange = vt_symbol.rsplit(".", 1)
    return symbol, exchange


def _normalize_direction(value: Any) -> Direction | None:
    text = _clean_scalar(value).lower()
    mapping = {
        "long": Direction.LONG,
        "多": Direction.LONG,
        "direction.long": Direction.LONG,
        "short": Direction.SHORT,
        "空": Direction.SHORT,
        "direction.short": Direction.SHORT,
    }
    return mapping.get(text)


def _normalize_offset(value: Any) -> Offset | None:
    text = _clean_scalar(value).lower()
    mapping = {
        "open": Offset.OPEN,
        "开": Offset.OPEN,
        "offset.open": Offset.OPEN,
        "close": Offset.CLOSE,
        "平": Offset.CLOSE,
        "offset.close": Offset.CLOSE,
        "closetoday": Offset.CLOSETODAY,
        "平今": Offset.CLOSETODAY,
        "offset.closetoday": Offset.CLOSETODAY,
        "closeyesterday": Offset.CLOSEYESTERDAY,
        "平昨": Offset.CLOSEYESTERDAY,
        "offset.closeyesterday": Offset.CLOSEYESTERDAY,
    }
    return mapping.get(text)


def _price_on_tick(price: float, pricetick: float) -> bool:
    if price <= 0 or pricetick <= 0:
        return False
    units = price / pricetick
    return math.isclose(units, round(units), rel_tol=0.0, abs_tol=1e-8)


def _contract_row(contracts: pd.DataFrame, symbol: str, exchange: str) -> dict[str, Any] | None:
    if contracts.empty:
        return None
    matched = contracts[
        contracts["symbol"].astype(str).eq(symbol)
        & contracts["exchange"].astype(str).eq(exchange)
    ]
    if matched.empty:
        return None
    return matched.iloc[0].to_dict()


def _read_csv_maybe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except EmptyDataError:
        return pd.DataFrame()


def _build_request_row(row: dict[str, Any], contracts: pd.DataFrame, mode: str, confirm_text: str) -> dict[str, Any]:
    reasons: list[str] = []
    status = "request_ready"
    vt_symbol = _clean_scalar(row.get("vt_symbol"))
    symbol, exchange_value = _split_vt_symbol(vt_symbol)
    direction = _normalize_direction(row.get("direction"))
    offset = _normalize_offset(row.get("offset"))
    volume = _to_float(row.get("planned_volume"), 0.0)
    price = _to_float(row.get("draft_order_price"), 0.0)
    contract = _contract_row(contracts, symbol, exchange_value)

    if _clean_scalar(row.get("approval_status")) != "approved_waiting_precheck":
        reasons.append("approval_status_not_ready")
    if _to_int_flag(row.get("final_can_submit")) != 1:
        reasons.append("final_gate_not_passed")
    if _clean_scalar(row.get("submit_adapter_status")) != "dry_run_ready":
        reasons.append("submit_adapter_not_dry_run_ready")
    if not symbol or not exchange_value:
        reasons.append("invalid_vt_symbol")
    if direction is None:
        reasons.append("invalid_direction")
    if offset is None:
        reasons.append("invalid_offset")
    if contract is None:
        reasons.append("contract_not_found")

    pricetick = _to_float(contract.get("pricetick") if contract else None, 0.0)
    min_volume = _to_float(contract.get("min_volume") if contract else None, 0.0)
    max_volume = _to_float(contract.get("max_volume") if contract else None, 0.0)
    gateway_name = _clean_scalar(contract.get("gateway_name") if contract else "CTP") or "CTP"

    if volume <= 0:
        reasons.append("invalid_volume")
    if min_volume and volume < min_volume:
        reasons.append("volume_below_min")
    if max_volume and volume > max_volume:
        reasons.append("volume_above_max")
    if not float(volume).is_integer():
        reasons.append("volume_not_integer_lots")
    if price <= 0:
        reasons.append("invalid_price")
    if pricetick and not _price_on_tick(price, pricetick):
        reasons.append("price_not_on_tick")

    real_env_enabled = _env_enabled("PHASEB_REAL_ORDER_ENABLED")
    if mode == "real":
        if not real_env_enabled:
            reasons.append("phaseb_real_order_env_disabled")
        if confirm_text != CONFIRM_TEXT:
            reasons.append("real_submit_confirmation_missing")
        reasons.append("stage250_never_calls_send_order")

    if reasons:
        status = "blocked"

    order_request_payload: dict[str, Any] = {}
    if not reasons and direction and offset:
        exchange = Exchange(exchange_value)
        req = OrderRequest(
            symbol=symbol,
            exchange=exchange,
            direction=direction,
            type=OrderType.LIMIT,
            volume=volume,
            price=price,
            offset=offset,
            reference=f"Stage250PhaseB:{row.get('intent_id', '')}",
        )
        order_request_payload = {
            "symbol": req.symbol,
            "exchange": req.exchange.value,
            "direction": req.direction.value,
            "type": req.type.value,
            "volume": req.volume,
            "price": req.price,
            "offset": req.offset.value,
            "reference": req.reference,
            "vt_symbol": req.vt_symbol,
            "gateway_name": gateway_name,
        }

    return {
        "trade_date": row.get("trade_date", ""),
        "intent_id": row.get("intent_id", ""),
        "requested_mode": mode,
        "request_builder_status": status,
        "request_builder_reason": ";".join(reasons),
        "order_api_called": 0,
        "vt_symbol": vt_symbol,
        "symbol": symbol,
        "exchange": exchange_value,
        "direction": direction.name if direction else "",
        "offset": offset.name if offset else "",
        "order_type": OrderType.LIMIT.name,
        "volume": volume,
        "price": price,
        "pricetick": pricetick,
        "min_volume": min_volume,
        "max_volume": max_volume,
        "gateway_name": gateway_name,
        "order_request_json": json.dumps(order_request_payload, ensure_ascii=False, sort_keys=True),
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _to_markdown(df: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
    if df.empty:
        return "_empty_"
    view = df.loc[:, [column for column in columns if column in df.columns]].head(max_rows).copy()
    for col in view.columns:
        if pd.api.types.is_numeric_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{float(x):,.4f}" if abs(float(x)) < 1000 else f"{float(x):,.0f}")
    return view.to_markdown(index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build auditable vn.py OrderRequest payloads for Phase B intents.")
    parser.add_argument("--trade-date", required=True, help="Trade date, YYYY-MM-DD.")
    parser.add_argument("--mode", choices=["dry-run", "real"], default="dry-run")
    parser.add_argument("--confirm-real-submit", default="")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(args.trade_date, args.mode)
    approval = pd.read_csv(paths["approval_csv"], encoding="utf-8-sig")
    contracts = _read_csv_maybe(paths["contracts_csv"])
    candidates = approval[approval["approval_status"].astype(str).eq("approved_waiting_precheck")].copy()
    results = pd.DataFrame(
        [
            _build_request_row(row, contracts, args.mode, args.confirm_real_submit)
            for row in candidates.to_dict(orient="records")
        ]
    )
    results.to_csv(paths["result_csv"], index=False, encoding="utf-8-sig")

    ready_count = int(results["request_builder_status"].astype(str).eq("request_ready").sum()) if not results.empty else 0
    blocked_count = int(results["request_builder_status"].astype(str).eq("blocked").sum()) if not results.empty else 0
    order_api_called_count = int(pd.to_numeric(results["order_api_called"], errors="coerce").fillna(0).sum()) if not results.empty else 0
    summary = {
        "model_tag": MODEL_TAG,
        "trade_date": args.trade_date,
        "requested_mode": args.mode,
        "checked_intent_count": int(len(results)),
        "request_ready_count": ready_count,
        "blocked_count": blocked_count,
        "order_api_called_count": order_api_called_count,
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "否。OrderRequest 构造只验证执行字段，不改策略信号或参数。",
            "continue_before": "是。真实 submit 前必须先把合约、手数、价格、方向、开平映射成可审计请求。",
            "overfit_after": "否。本阶段不影响回测收益，也不生成新信号。",
            "continue_after": "是。dry-run 请求构造通过后，下一步才有资格做真实 submit 的最小实现。",
        },
    }
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    report_lines = [
        "# Stage250 Phase B vn.py OrderRequest Builder",
        "",
        f"- 交易日：`{args.trade_date}`",
        f"- 请求模式：`{args.mode}`",
        f"- request ready：`{ready_count}`",
        f"- blocked：`{blocked_count}`",
        f"- order API 调用次数：`{order_api_called_count}`",
        "",
        "## 结果",
        "",
        _to_markdown(
            results,
            [
                "intent_id",
                "requested_mode",
                "request_builder_status",
                "request_builder_reason",
                "order_api_called",
                "vt_symbol",
                "direction",
                "offset",
                "order_type",
                "volume",
                "price",
                "pricetick",
                "gateway_name",
                "checked_at",
            ],
        ),
        "",
        "## 说明",
        "",
        "- 本阶段只构造 vn.py `OrderRequest` payload，不导入 CTP gateway，不连接服务器，不调用 `send_order`。",
        "- `real` 模式在 Stage250 仍会阻断并记录 `stage250_never_calls_send_order`。",
        "- 只有 `request_builder_status=request_ready` 才代表字段映射、合约、价格 tick、手数边界全部通过。",
        "",
    ]
    paths["report_md"].write_text("\n".join(report_lines), encoding="utf-8")
    print(json.dumps(summary["outputs"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
