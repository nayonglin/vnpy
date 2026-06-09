from __future__ import annotations

import json
import math
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage703_stage407_loss_streak_source_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage703_stage407_loss_streak_source_audit"

SOURCE_PREFIX = "qmt_roll_stage702_stage407_local_failure_cooldown"
SOURCE_TAG = "stage702_stage407_local_failure_cooldown_v1"

BASE_VARIANT = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4"
STAGE407_VARIANT = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_original_ai_plus_jd_ai_rerank_top9_maxpos5"
STAGE415_VARIANT = (
    "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_original_ai_plus_jd_ai_rerank_top9_"
    "maxpos5_no_global_streak_local_fail3_cool90"
)
OFFICIAL_LOCAL_COOLDOWN_VARIANT = (
    "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_no_global_streak_local_fail3_cool90"
)
WATCH_VARIANTS = [
    BASE_VARIANT,
    STAGE407_VARIANT,
    STAGE415_VARIANT,
    OFFICIAL_LOCAL_COOLDOWN_VARIANT,
]

HIGHLIGHT_START = pd.Timestamp("2025-04-16")
HIGHLIGHT_END = pd.Timestamp("2025-07-25")

TRADE_USAGE_PATH = OUTPUT_DIR / f"{SOURCE_PREFIX}_trade_usage_{SOURCE_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{SOURCE_PREFIX}_entry_risk_{SOURCE_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{SOURCE_PREFIX}_entry_candidates_{SOURCE_TAG}.csv"
METADATA_PATH = OUTPUT_DIR / "tqsdk_all_futures_contract_metadata.csv"

LOSS_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_loss_events_{MODEL_TAG}.csv"
OPEN_STREAK_CONTEXT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_open_streak_context_{MODEL_TAG}.csv"
STREAK_TRIGGER_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trigger_summary_{MODEL_TAG}.csv"
WINDOW_ENTRY_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_entry_audit_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _product_from_contract(vt_symbol: Any) -> str:
    text = str(vt_symbol or "")
    if "." not in text:
        return ""
    symbol, exchange = text.split(".", 1)
    product = ""
    for char in symbol:
        if char.isalpha():
            product += char
        else:
            break
    return f"{product}.{exchange}" if product and exchange else ""


def _load_size_map() -> dict[str, float]:
    if not METADATA_PATH.exists():
        return {}
    meta = pd.read_csv(METADATA_PATH)
    meta = meta[meta.get("symbol_kind", "").astype(str).eq("product_cont")].copy()
    result: dict[str, float] = {}
    for row in meta.itertuples(index=False):
        product = str(getattr(row, "vt_symbol", "") or "")
        size = pd.to_numeric(getattr(row, "volume_multiple", 0.0), errors="coerce")
        if product and pd.notna(size) and float(size) > 0:
            result[product] = float(size)
    return result


def _normalize_trade_usage() -> pd.DataFrame:
    data = pd.read_csv(TRADE_USAGE_PATH)
    data = data[data["variant"].astype(str).isin(WATCH_VARIANTS)].copy()
    data["trade_id_num"] = (
        data["trade_id"].astype(str).str.extract(r"(\d+)$", expand=False).astype(float)
    )
    data["signal_date"] = pd.to_datetime(data["signal_date"], errors="coerce").dt.normalize()
    data["fill_date"] = pd.to_datetime(data["fill_date"], errors="coerce").dt.normalize()
    data["product_vt_symbol"] = data["vt_symbol"].map(_product_from_contract)
    for column in ["trade_price", "order_volume"]:
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0.0)
    data.sort_values(["variant", "trade_id_num", "signal_date", "fill_date"], inplace=True)
    return data


def _reconstruct_close_events(trades: pd.DataFrame, size_map: dict[str, float]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for variant, frame in trades.groupby("variant", sort=False):
        queues: dict[tuple[str, str], deque[dict[str, Any]]] = defaultdict(deque)
        loss_streak = 0
        for trade in frame.itertuples(index=False):
            vt_symbol = str(trade.vt_symbol)
            product = str(trade.product_vt_symbol)
            side_text = str(trade.direction)
            offset = str(trade.offset)
            volume_left = float(trade.order_volume or 0.0)
            price = float(trade.trade_price or 0.0)
            event_date = pd.Timestamp(trade.signal_date)
            trade_id = str(trade.trade_id)
            size = float(size_map.get(product, 1.0) or 1.0)

            if offset == "Open":
                position_side = "long" if side_text == "Long" else "short"
                queues[(vt_symbol, position_side)].append(
                    {
                        "entry_date": event_date,
                        "entry_price": price,
                        "volume": volume_left,
                        "trade_id": trade_id,
                        "product_vt_symbol": product,
                    }
                )
                continue
            if offset != "Close":
                continue

            position_side = "long" if side_text == "Short" else "short"
            key = (vt_symbol, position_side)
            matched_volume = 0.0
            realized = 0.0
            matched_entries: list[str] = []
            while volume_left > 1e-9 and queues[key]:
                layer = queues[key][0]
                close_volume = min(volume_left, float(layer["volume"]))
                entry_price = float(layer["entry_price"])
                if position_side == "long":
                    layer_realized = (price - entry_price) * close_volume * size
                else:
                    layer_realized = (entry_price - price) * close_volume * size
                realized += layer_realized
                matched_volume += close_volume
                matched_entries.append(
                    f"{pd.Timestamp(layer['entry_date']).date()}@{entry_price:g}x{close_volume:g}"
                )
                layer["volume"] = float(layer["volume"]) - close_volume
                volume_left -= close_volume
                if float(layer["volume"]) <= 1e-9:
                    queues[key].popleft()

            streak_before = loss_streak
            if realized < 0:
                loss_streak += 1
            elif realized > 0:
                loss_streak = 0
            streak_after = loss_streak
            rows.append(
                {
                    "variant": variant,
                    "trade_id": trade_id,
                    "signal_date": event_date.date().isoformat(),
                    "fill_date": pd.Timestamp(trade.fill_date).date().isoformat()
                    if pd.notna(trade.fill_date)
                    else "",
                    "vt_symbol": vt_symbol,
                    "product_vt_symbol": product,
                    "position_side": position_side,
                    "close_direction": side_text,
                    "close_price": price,
                    "matched_volume": matched_volume,
                    "unmatched_volume": max(0.0, volume_left),
                    "contract_size": size,
                    "realized_pnl_approx": realized,
                    "is_loss": int(realized < 0),
                    "loss_streak_before": streak_before,
                    "loss_streak_after": streak_after,
                    "matched_entries": ";".join(matched_entries),
                }
            )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result["signal_date"] = pd.to_datetime(result["signal_date"], errors="coerce").dt.normalize()
    result["fill_date"] = pd.to_datetime(result["fill_date"], errors="coerce").dt.normalize()
    return result


def _open_streak_context(close_events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    entries = pd.read_csv(ENTRY_RISK_PATH)
    entries = entries[entries["variant"].astype(str).isin(WATCH_VARIANTS)].copy()
    entries["date"] = pd.to_datetime(entries["date"], errors="coerce").dt.normalize()
    for column in [
        "loss_streak",
        "risk_multiplier",
        "target_risk_amount",
        "risk_per_contract",
        "contracts_by_risk",
        "contracts_by_margin",
        "selected_volume",
        "portfolio_drawdown_pct",
    ]:
        if column in entries.columns:
            entries[column] = pd.to_numeric(entries[column], errors="coerce")
    severe = entries[entries["loss_streak"].fillna(0).ge(3)].copy()
    severe["in_highlight_window"] = severe["date"].between(HIGHLIGHT_START, HIGHLIGHT_END).astype(int)

    context_rows: list[dict[str, Any]] = []
    for entry in severe.itertuples(index=False):
        variant = str(entry.variant)
        entry_date = pd.Timestamp(entry.date)
        prior = close_events[
            (close_events["variant"].astype(str).eq(variant))
            & (close_events["signal_date"] <= entry_date)
        ].sort_values("signal_date")
        losing_tail = prior.tail(8).copy()
        consecutive: list[dict[str, Any]] = []
        for close in reversed(losing_tail.to_dict("records")):
            if int(close.get("is_loss", 0)) != 1:
                break
            consecutive.append(close)
        consecutive = list(reversed(consecutive))
        tail_text = " | ".join(
            (
                f"{pd.Timestamp(item['signal_date']).date()} "
                f"{item['product_vt_symbol']} {item['position_side']} "
                f"{float(item['realized_pnl_approx']):.0f}"
            )
            for item in consecutive[-5:]
        )
        products = ",".join(str(item["product_vt_symbol"]) for item in consecutive)
        sides = ",".join(str(item["position_side"]) for item in consecutive)
        context_rows.append(
            {
                "variant": variant,
                "entry_date": entry_date.date().isoformat(),
                "product_vt_symbol": str(entry.product_vt_symbol),
                "contract_vt_symbol": str(entry.contract_vt_symbol),
                "entry_direction": str(entry.direction),
                "signal": str(entry.signal),
                "loss_streak_at_entry": int(entry.loss_streak),
                "risk_multiplier": float(entry.risk_multiplier),
                "target_risk_amount": float(entry.target_risk_amount),
                "risk_per_contract": float(entry.risk_per_contract),
                "contracts_by_risk": int(entry.contracts_by_risk),
                "contracts_by_margin": int(entry.contracts_by_margin),
                "selected_volume": int(entry.selected_volume),
                "portfolio_drawdown_pct": float(entry.portfolio_drawdown_pct),
                "in_highlight_window": int(entry_date >= HIGHLIGHT_START and entry_date <= HIGHLIGHT_END),
                "consecutive_loss_count_reconstructed": len(consecutive),
                "consecutive_loss_products": products,
                "consecutive_loss_sides": sides,
                "consecutive_loss_tail": tail_text,
                "same_product_in_loss_tail": int(str(entry.product_vt_symbol) in set(products.split(","))),
                "same_direction_in_loss_tail": int(str(entry.direction) in set(sides.split(","))),
            }
        )
    context = pd.DataFrame(context_rows)

    if context.empty:
        trigger_summary = pd.DataFrame()
    else:
        trigger_summary = (
            context.groupby(["variant", "in_highlight_window"], dropna=False)
            .agg(
                severe_entry_rows=("entry_date", "count"),
                opened_volume=("selected_volume", "sum"),
                median_target_risk_amount=("target_risk_amount", "median"),
                median_selected_volume=("selected_volume", "median"),
                same_product_tail_rate=("same_product_in_loss_tail", "mean"),
                same_direction_tail_rate=("same_direction_in_loss_tail", "mean"),
            )
            .reset_index()
        )

    candidates = pd.read_csv(ENTRY_CANDIDATES_PATH)
    candidates = candidates[candidates["variant"].astype(str).isin(WATCH_VARIANTS)].copy()
    candidates["date"] = pd.to_datetime(candidates["date"], errors="coerce").dt.normalize()
    window = candidates[candidates["date"].between(HIGHLIGHT_START, HIGHLIGHT_END)].copy()
    for column in [
        "loss_streak",
        "risk_multiplier",
        "target_risk_amount",
        "contracts_by_risk",
        "contracts_by_margin",
        "selected_volume",
        "is_opened",
    ]:
        if column in window.columns:
            window[column] = pd.to_numeric(window[column], errors="coerce")
    window_audit = (
        window.groupby(["variant", "product_vt_symbol", "skip_reason"], dropna=False)
        .agg(
            rows=("date", "count"),
            opened=("is_opened", "sum"),
            selected_volume_sum=("selected_volume", "sum"),
            median_loss_streak=("loss_streak", "median"),
            median_risk_multiplier=("risk_multiplier", "median"),
            median_target_risk_amount=("target_risk_amount", "median"),
            median_contracts_by_risk=("contracts_by_risk", "median"),
            median_contracts_by_margin=("contracts_by_margin", "median"),
        )
        .reset_index()
        .sort_values(["variant", "opened", "selected_volume_sum"], ascending=[True, False, False])
    )
    return context, trigger_summary, window_audit


def _decision(
    close_events: pd.DataFrame,
    context: pd.DataFrame,
    trigger_summary: pd.DataFrame,
    window_audit: pd.DataFrame,
) -> dict[str, Any]:
    stage407_window = context[
        context["variant"].astype(str).eq(STAGE407_VARIANT)
        & context["in_highlight_window"].eq(1)
    ].copy()
    stage407_all = context[context["variant"].astype(str).eq(STAGE407_VARIANT)].copy()
    source = {
        "stage": "Stage416",
        "script_stage": "Stage703",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": "loss_streak_source_audit_completed_no_new_candidate_yet",
        "change": {
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "source_outputs": SOURCE_TAG,
            "audit_type": "read_only_trade_usage_fifo_approximation",
        },
        "stage407_highlight_severe_entries": int(len(stage407_window)),
        "stage407_highlight_same_product_tail_rate": float(stage407_window["same_product_in_loss_tail"].mean())
        if not stage407_window.empty
        else 0.0,
        "stage407_highlight_same_direction_tail_rate": float(stage407_window["same_direction_in_loss_tail"].mean())
        if not stage407_window.empty
        else 0.0,
        "stage407_all_severe_entries": int(len(stage407_all)),
        "outputs": {
            "loss_events": str(LOSS_EVENTS_PATH),
            "open_streak_context": str(OPEN_STREAK_CONTEXT_PATH),
            "trigger_summary": str(STREAK_TRIGGER_SUMMARY_PATH),
            "window_entry_audit": str(WINDOW_ENTRY_AUDIT_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }
    if not stage407_window.empty:
        source["stage407_highlight_context_rows"] = stage407_window[
            [
                "entry_date",
                "product_vt_symbol",
                "entry_direction",
                "signal",
                "loss_streak_at_entry",
                "selected_volume",
                "consecutive_loss_tail",
                "same_product_in_loss_tail",
                "same_direction_in_loss_tail",
            ]
        ].to_dict("records")
    return source


def _write_report(
    close_events: pd.DataFrame,
    context: pd.DataFrame,
    trigger_summary: pd.DataFrame,
    window_audit: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    stage407_context = context[
        context["variant"].astype(str).eq(STAGE407_VARIANT)
        & context["in_highlight_window"].eq(1)
    ].copy()
    loss_tail_cols = [
        "entry_date",
        "product_vt_symbol",
        "entry_direction",
        "signal",
        "loss_streak_at_entry",
        "risk_multiplier",
        "target_risk_amount",
        "selected_volume",
        "consecutive_loss_count_reconstructed",
        "consecutive_loss_tail",
        "same_product_in_loss_tail",
        "same_direction_in_loss_tail",
    ]
    lines = [
        "# Stage416 / Script703 Stage407 Loss-Streak Source Audit",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- 本阶段不跑新回测，只读取 Stage702 的 `trade_usage`、`entry_risk`、`entry_candidates`。",
        "- 目标：把 `loss_streak>=3` 的开仓往前对应到连续亏损平仓来源，判断全局 0.1 是同品种/同方向风险，还是跨品种全局噪声。",
        "- PnL 为 FIFO 近似，不含手续费滑点；只用于来源归因，不作为正式绩效数字。",
        "",
        "## Trigger Summary",
        "",
        _md_table(trigger_summary, max_rows=80),
        "",
        "## Stage407 Highlight Severe Entry Context",
        "",
        _md_table(stage407_context[loss_tail_cols] if not stage407_context.empty else pd.DataFrame(), max_rows=80),
        "",
        "## Highlight Window Candidate Audit",
        "",
        _md_table(window_audit, max_rows=120),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        "- 只读审计结论用于下一步机制选择，不直接形成交易规则。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    size_map = _load_size_map()
    trades = _normalize_trade_usage()
    close_events = _reconstruct_close_events(trades, size_map)
    context, trigger_summary, window_audit = _open_streak_context(close_events)

    close_events.to_csv(LOSS_EVENTS_PATH, index=False, encoding="utf-8-sig")
    context.to_csv(OPEN_STREAK_CONTEXT_PATH, index=False, encoding="utf-8-sig")
    trigger_summary.to_csv(STREAK_TRIGGER_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    window_audit.to_csv(WINDOW_ENTRY_AUDIT_PATH, index=False, encoding="utf-8-sig")

    decision = _decision(close_events, context, trigger_summary, window_audit)
    DECISION_PATH.write_text(
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_report(close_events, context, trigger_summary, window_audit, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
