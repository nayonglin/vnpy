from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from main_contract_mapping import build_contract_metadata, load_product_universe_symbols
from qmt_roll_official_stage78_config import build_official_stage78_manifest


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage248_rsi_partial_exit_trigger_attribution_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage248_rsi_partial_exit_trigger_attribution"

DEFAULT_ON_TRADES: Path = OUTPUT_DIR / "qmt_roll_official_stage78_1_trades_2020_2026_04.csv"
DEFAULT_OFF_TRADES: Path = OUTPUT_DIR / "qmt_roll_stage248_stage78_1_rsi_partial_exit_off_full_trades_2020_2026_04.csv"

REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
TRIGGERS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_triggers_{MODEL_TAG}.csv"
POSITION_SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_position_summary_{MODEL_TAG}.csv"
TAIL_SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tail_summary_{MODEL_TAG}.csv"


def _clean_scalar(value: Any) -> str:
    if value is None:
        return ""
    try:
        if isinstance(value, float) and pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _normalize_direction(value: Any) -> str:
    text = _clean_scalar(value).lower()
    if text in {"long", "l", "buy"}:
        return "long"
    if text in {"short", "s", "sell"}:
        return "short"
    return text


def _normalize_offset(value: Any) -> str:
    text = _clean_scalar(value).lower()
    if text in {"open"}:
        return "open"
    if text in {"close"}:
        return "close"
    return text


def _load_trades(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"missing trades csv: {path}")
    df = pd.read_csv(path, encoding="utf-8-sig")
    # Normalize common columns across different exporters.
    if "vt_symbol" not in df.columns and {"symbol", "exchange"}.issubset(df.columns):
        df["vt_symbol"] = df["symbol"].astype(str) + "." + df["exchange"].astype(str)
    df["direction"] = df.get("direction", "").map(_normalize_direction)
    df["offset"] = df.get("offset", "").map(_normalize_offset)
    df["exit_reason"] = df.get("exit_reason", "").map(_clean_scalar)
    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    else:
        # Fallback to date+time fields if present.
        date_s = df.get("date", "").astype(str)
        time_s = df.get("time", "").astype(str)
        df["datetime"] = pd.to_datetime(date_s + " " + time_s, errors="coerce")
    df["_row_order"] = np.arange(len(df))
    df.sort_values(["datetime", "_row_order"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    df["price"] = pd.to_numeric(df.get("price", 0.0), errors="coerce").fillna(0.0)
    df["volume"] = pd.to_numeric(df.get("volume", 0.0), errors="coerce").fillna(0.0)
    return df


@dataclass
class PositionState:
    position_id: str
    vt_symbol: str
    direction: str  # long/short
    open_volume: float = 0.0
    realized_pnl: float = 0.0
    opened_at: pd.Timestamp | None = None
    closed_at: pd.Timestamp | None = None

    partial_exit_triggered: bool = False
    partial_exit_volume: float = 0.0
    partial_exit_price: float = 0.0
    partial_exit_time: pd.Timestamp | None = None

    later_close_volume: float = 0.0
    later_close_value: float = 0.0  # sum(price * vol) after partial exit

    def later_avg_close_price(self) -> float:
        if self.later_close_volume <= 0:
            return 0.0
        return self.later_close_value / self.later_close_volume


def _is_partial_exit_reason(reason: str) -> bool:
    r = reason.lower()
    return "rsi_partial_exit" in r


def _compute_positions(trades: pd.DataFrame, size_map: dict[str, float]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build position-level aggregates and trigger events.

    Assumptions:
    - A "position" is tracked per (vt_symbol, direction) until volume returns to 0.
    - RSI partial exit triggers at most once per position (true in strategy code).
    - Counterfactual giveback estimation:
        For the volume closed by RSI partial exit, assume it would have been closed at
        the volume-weighted average close price AFTER the trigger within the same position.
    """
    # IMPORTANT:
    # In vn.py trades, "direction" describes trade action (buy/sell), while "offset" describes open/close.
    # A short position is opened by a "short open" trade, but closed by a "long close" trade.
    # Therefore we must derive the POSITION side from (direction, offset), not reuse trade direction.
    positions: dict[tuple[str, str], PositionState] = {}
    open_queues: dict[tuple[str, str], list[dict[str, float]]] = {}
    triggers: list[dict[str, Any]] = []
    pos_rows: list[dict[str, Any]] = []

    def ensure_position(vt_symbol: str, position_side: str, when: pd.Timestamp) -> PositionState:
        key = (vt_symbol, position_side)
        state = positions.get(key)
        if state is None or state.open_volume <= 1e-9:
            pid = f"{vt_symbol}|{position_side}|{when.strftime('%Y%m%dT%H%M%S')}|{len(pos_rows):06d}"
            state = PositionState(position_id=pid, vt_symbol=vt_symbol, direction=position_side, opened_at=when)
            positions[key] = state
        return state

    for row in trades.itertuples(index=False):
        vt_symbol = _clean_scalar(getattr(row, "vt_symbol", ""))
        trade_side = _normalize_direction(getattr(row, "direction", ""))
        offset = _normalize_offset(getattr(row, "offset", ""))
        dt: pd.Timestamp = getattr(row, "datetime", pd.NaT)
        price = float(getattr(row, "price", 0.0) or 0.0)
        volume = float(getattr(row, "volume", 0.0) or 0.0)
        reason = _clean_scalar(getattr(row, "exit_reason", ""))
        if not vt_symbol or trade_side not in {"long", "short"} or offset not in {"open", "close"}:
            continue
        if pd.isna(dt) or price <= 0 or volume <= 0:
            continue

        # Derive the position side.
        if offset == "open":
            position_side = trade_side
        else:
            # closing a long => trade_side is short; closing a short => trade_side is long
            position_side = "long" if trade_side == "short" else "short"

        key = (vt_symbol, position_side)
        size = float(size_map.get(vt_symbol, 1.0))
        pos = ensure_position(vt_symbol, position_side, dt)

        if offset == "open":
            open_queues.setdefault(key, []).append({"price": price, "volume": volume})
            pos.open_volume += volume
            continue

        # Close: FIFO consume opens to compute realized pnl.
        remain = volume
        queue = open_queues.setdefault(key, [])
        while remain > 1e-9 and queue:
            lot = queue[0]
            matched = min(remain, float(lot["volume"]))
            entry_price = float(lot["price"])
            if position_side == "long":
                pnl = (price - entry_price) * matched * size
            else:
                pnl = (entry_price - price) * matched * size
            pos.realized_pnl += float(pnl)
            lot["volume"] = float(lot["volume"]) - matched
            remain -= matched
            if float(lot["volume"]) <= 1e-9:
                queue.pop(0)

        # Track partial-exit trigger and later close prices for giveback estimation.
        if _is_partial_exit_reason(reason):
            # Record only the first trigger per position.
            if not pos.partial_exit_triggered:
                pos.partial_exit_triggered = True
                pos.partial_exit_volume = float(volume)
                pos.partial_exit_price = float(price)
                pos.partial_exit_time = dt
            triggers.append(
                {
                    "position_id": pos.position_id,
                    "vt_symbol": vt_symbol,
                    "position_side": position_side,
                    "trade_side": trade_side,
                    "datetime": dt.isoformat(),
                    "price": price,
                    "volume": volume,
                    "exit_reason": reason,
                }
            )
        elif pos.partial_exit_triggered and pos.partial_exit_time is not None and dt > pos.partial_exit_time:
            pos.later_close_volume += float(volume)
            pos.later_close_value += float(price * volume)

        pos.open_volume = max(0.0, pos.open_volume - volume)
        if pos.open_volume <= 1e-9:
            pos.closed_at = dt
            later_avg = pos.later_avg_close_price()
            giveback_cash = 0.0
            if pos.partial_exit_triggered and pos.partial_exit_volume > 0 and later_avg > 0:
                # Counterfactual: hold the early-closed volume to later closes.
                if pos.direction == "long":
                    giveback_cash = (later_avg - pos.partial_exit_price) * pos.partial_exit_volume * size
                else:
                    giveback_cash = (pos.partial_exit_price - later_avg) * pos.partial_exit_volume * size
            pos_rows.append(
                {
                    "position_id": pos.position_id,
                    "vt_symbol": pos.vt_symbol,
                    "direction": pos.direction,
                    "opened_at": pos.opened_at.isoformat() if pos.opened_at is not None else "",
                    "closed_at": pos.closed_at.isoformat() if pos.closed_at is not None else "",
                    "realized_pnl": pos.realized_pnl,
                    "partial_exit_triggered": int(pos.partial_exit_triggered),
                    "partial_exit_volume": pos.partial_exit_volume,
                    "partial_exit_price": pos.partial_exit_price,
                    "later_avg_close_price": later_avg,
                    "estimated_giveback_cash": giveback_cash,
                }
            )
            # Reset state for the next position on the same contract+position side.
            positions[key] = PositionState(position_id="", vt_symbol=vt_symbol, direction=position_side)

    pos_df = pd.DataFrame(pos_rows)
    trig_df = pd.DataFrame(triggers)
    return pos_df, trig_df


def _tail_metrics(pos_df: pd.DataFrame, variant: str) -> dict[str, Any]:
    pnl = pd.to_numeric(pos_df["realized_pnl"], errors="coerce").fillna(0.0)
    winners = pnl[pnl > 0].sort_values(ascending=False)
    total = float(pnl.sum())
    total_win = float(winners.sum())
    if winners.empty:
        return {
            "variant": variant,
            "positions": int(len(pos_df)),
            "total_pnl": total,
            "winner_pnl": total_win,
            "p90": 0.0,
            "p95": 0.0,
            "p99": 0.0,
            "top1_share_of_winners_pct": 0.0,
            "top5_share_of_winners_pct": 0.0,
            "top10_share_of_winners_pct": 0.0,
        }
    p90 = float(winners.quantile(0.90))
    p95 = float(winners.quantile(0.95))
    p99 = float(winners.quantile(0.99))
    n = len(winners)
    top1 = winners.head(max(1, int(np.ceil(n * 0.01))))
    top5 = winners.head(max(1, int(np.ceil(n * 0.05))))
    top10 = winners.head(max(1, int(np.ceil(n * 0.10))))
    return {
        "variant": variant,
        "positions": int(len(pos_df)),
        "total_pnl": total,
        "winner_pnl": total_win,
        "p90": p90,
        "p95": p95,
        "p99": p99,
        "top1_share_of_winners_pct": float(top1.sum() / total_win * 100.0) if total_win != 0 else 0.0,
        "top5_share_of_winners_pct": float(top5.sum() / total_win * 100.0) if total_win != 0 else 0.0,
        "top10_share_of_winners_pct": float(top10.sum() / total_win * 100.0) if total_win != 0 else 0.0,
    }


def _build_report(summary: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Stage248 RSI>95 分批止盈触发归因",
        "",
        f"- 生成时间：`{summary['generated_at']}`",
        f"- ON(trades)：`{summary['inputs']['on_trades']}`",
        f"- OFF(trades)：`{summary['inputs']['off_trades']}`",
        "",
        "## 触发次数",
        "",
        f"- ON 触发条数（trade-level）：`{summary['on']['trigger_trade_count']}`",
        f"- ON 触发涉及的持仓数（position-level）：`{summary['on']['trigger_position_count']}`",
        f"- ON 触发后估算被截断收益（giveback，现金）：`{summary['on']['estimated_giveback_cash_sum']:,.0f}`",
        "",
        "## 是否截断大赢家（证据）",
        "",
        "- 证据A：ON 版本中，触发后的后续平均退出价通常高于触发价（多头）/低于触发价（空头），则代表提前减仓截断右尾。",
        "- 证据B：ON vs OFF 的右尾分布（p90/p95/p99，及 top 1%/5%/10% 对赢家贡献占比）差异。",
        "",
        "### ON 触发持仓统计",
        "",
        summary["tables"]["on_trigger_positions"],
        "",
        "### 右尾分布对比",
        "",
        summary["tables"]["tail_metrics"],
        "",
        "## 输出文件",
        "",
        f"- report：`{summary['outputs']['report']}`",
        f"- summary：`{summary['outputs']['summary_json']}`",
        f"- triggers：`{summary['outputs']['triggers_csv']}`",
        f"- position_summary：`{summary['outputs']['position_summary_csv']}`",
        f"- tail_summary：`{summary['outputs']['tail_summary_csv']}`",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze RSI partial exit triggers and tail truncation evidence.")
    parser.add_argument("--on-trades", default=str(DEFAULT_ON_TRADES))
    parser.add_argument("--off-trades", default=str(DEFAULT_OFF_TRADES))
    args = parser.parse_args()

    on_path = Path(str(args.on_trades)).expanduser().resolve()
    off_path = Path(str(args.off_trades)).expanduser().resolve()

    manifest = build_official_stage78_manifest()
    universe_path = str(manifest.get("product_universe_csv_path", ""))
    symbols = load_product_universe_symbols(universe_path)
    metadata = build_contract_metadata(supported_symbols=symbols)
    size_map = {str(k): float(v) for k, v in (metadata.get("sizes", {}) or {}).items()}

    on_trades = _load_trades(on_path)
    off_trades = _load_trades(off_path)

    on_pos, on_trig = _compute_positions(on_trades, size_map)
    off_pos, _ = _compute_positions(off_trades, size_map)

    on_trigger_positions = on_pos[on_pos["partial_exit_triggered"].astype(int) == 1].copy()
    on_trigger_trade_count = int(len(on_trig))
    on_trigger_position_count = int(len(on_trigger_positions))
    on_est_giveback = float(pd.to_numeric(on_trigger_positions["estimated_giveback_cash"], errors="coerce").fillna(0.0).sum())

    # Aggregate tail metrics for ON/OFF.
    tail_rows = [_tail_metrics(off_pos, "OFF"), _tail_metrics(on_pos, "ON")]
    tail_df = pd.DataFrame(tail_rows)

    # Small readable trigger-position summary table.
    on_trigger_view = (
        on_trigger_positions.sort_values("estimated_giveback_cash", ascending=False)
        .head(30)
        .loc[
            :,
            [
                "vt_symbol",
                "direction",
                "opened_at",
                "closed_at",
                "realized_pnl",
                "partial_exit_volume",
                "partial_exit_price",
                "later_avg_close_price",
                "estimated_giveback_cash",
            ],
        ]
        .copy()
    )
    # format
    for col in ["realized_pnl", "partial_exit_volume", "partial_exit_price", "later_avg_close_price", "estimated_giveback_cash"]:
        on_trigger_view[col] = pd.to_numeric(on_trigger_view[col], errors="coerce").fillna(0.0)
    on_trigger_md = on_trigger_view.to_markdown(index=False)
    tail_md = tail_df.to_markdown(index=False, floatfmt=".4f")

    summary: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "inputs": {"on_trades": str(on_path), "off_trades": str(off_path)},
        "on": {
            "trigger_trade_count": on_trigger_trade_count,
            "trigger_position_count": on_trigger_position_count,
            "estimated_giveback_cash_sum": on_est_giveback,
        },
        "tables": {"on_trigger_positions": on_trigger_md, "tail_metrics": tail_md},
        "outputs": {
            "report": str(REPORT_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
            "triggers_csv": str(TRIGGERS_CSV_PATH),
            "position_summary_csv": str(POSITION_SUMMARY_CSV_PATH),
            "tail_summary_csv": str(TAIL_SUMMARY_CSV_PATH),
        },
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    on_trig.to_csv(TRIGGERS_CSV_PATH, index=False, encoding="utf-8-sig")
    on_pos.to_csv(POSITION_SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    tail_df.to_csv(TAIL_SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(summary), encoding="utf-8")

    print(json.dumps(summary["on"], ensure_ascii=False, indent=2))
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
