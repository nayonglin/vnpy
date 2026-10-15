"""只读汇总 Stage246 已平仓交易胜率，按引擎成交 ID 顺序做 FIFO 配对。

Stage847 合成成交会被赋予真实日内时间，常规后备成交则是 00:00；
run_qmt_alignment_backtest.build_trades_df 按 datetime 对外排序，不能以 CSV 行顺序
还原成交。Stage502/827/840/847 的填单路径均在创建 TradeData 前执行
trade_count += 1，再用 tradeid=str(trade_count)，所以 BACKTESTING.N 数字顺序
才是实际引擎生成顺序。若 ID 不连续/重复，本工具拒绝计算。

主胜率口径：同一 vt_symbol 从空仓开仓至再次空仓算 1 个完整持仓周期；
累计该周期全部 FIFO 已配对价差，扣除开平两侧手续费和滑点，净盈亏>0 为赢。
未平仓周期不进入分母；另导出 FIFO 配对分笔结果以便复核。

费用按本次 vendor/vnpy_portfoliostrategy/backtesting.py 的
ContractDailyResult.calculate_pnl：每笔 turnover=volume*size*price，
commission=turnover*rate，slippage=volume*size*slippage。仓位、费用、
成交笔数与 positions.csv 独立对账；全平仓时净盈亏也必须对账。
参考上游：https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py
"""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any


TOL = 1e-7


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def close_enough(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-10, abs_tol=1e-6)


def direction_sign(value: str) -> int:
    if value in {"多", "long", "LONG"}:
        return 1
    if value in {"空", "short", "SHORT"}:
        return -1
    raise ValueError(f"unknown_direction:{value}")


def offset_kind(value: str) -> str:
    if value in {"开", "Open", "OPEN", "open"}:
        return "open"
    if value in {"平", "Close", "CLOSE", "close"}:
        return "close"
    raise ValueError(f"unknown_offset:{value}")


def ordered_trades(path: Path) -> Any:
    import pandas as pd

    trades = pd.read_csv(path, encoding="utf-8-sig")
    required = {"trade_id", "datetime", "vt_symbol", "direction", "offset", "price", "volume", "signed_volume"}
    if not required.issubset(trades.columns):
        raise ValueError(f"trades_columns_missing:{sorted(required - set(trades.columns))}")
    numeric_ids = trades["trade_id"].astype(str).str.extract(r"^BACKTESTING\.(\d+)$")[0]
    if numeric_ids.isna().any():
        raise ValueError("non_numeric_backtesting_trade_id")
    trades["engine_sequence"] = numeric_ids.astype(int)
    if len(trades) != trades["engine_sequence"].nunique():
        raise ValueError("duplicate_engine_sequence")
    if set(trades["engine_sequence"]) != set(range(1, len(trades) + 1)):
        raise ValueError("engine_sequence_not_contiguous")
    return trades.sort_values("engine_sequence").reset_index(drop=True)


def positions_ledger(path: Path) -> dict[str, Any]:
    import pandas as pd

    totals = {key: 0.0 for key in ("trade_count", "turnover", "commission", "slippage", "net_pnl")}
    first_start: dict[str, float] = {}
    latest: dict[str, tuple[str, float]] = {}
    rows = 0
    for chunk in pd.read_csv(path, usecols=["date", "vt_symbol", "start_pos", "end_pos", *totals],
                             chunksize=100_000, encoding="utf-8-sig"):
        rows += len(chunk)
        for key in totals:
            values = pd.to_numeric(chunk[key], errors="coerce")
            if values.isna().any() or not values.map(math.isfinite).all():
                raise ValueError(f"positions_{key}_invalid")
            totals[key] += float(values.sum())
        for symbol, day, start, end in chunk[["vt_symbol", "date", "start_pos", "end_pos"]].itertuples(index=False, name=None):
            symbol, day = str(symbol), str(day)[:10]
            start, end = float(start), float(end)
            if not math.isfinite(start) or not math.isfinite(end):
                raise ValueError("positions_quantity_invalid")
            first_start.setdefault(symbol, start)
            if symbol not in latest or day >= latest[symbol][0]:
                latest[symbol] = (day, end)
    return {"rows": rows, "totals": totals, "first_start": first_start, "latest": latest}


def calculate_outcomes(trades: Any, parameters: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, float]]:
    """开仓成本随 FIFO 手数分摊；平仓成本随该笔配对手数分摊。"""
    queues: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
    cycles: dict[str, dict[str, Any]] = {}
    matches: list[dict[str, Any]] = []
    completed: list[dict[str, Any]] = []
    trade_totals = {key: 0.0 for key in ("turnover", "commission", "slippage")}
    sizes, rates, slippages = (parameters[key] for key in ("contract_sizes", "rates", "slippages"))

    for row in trades.itertuples(index=False):
        symbol, trade_id = str(row.vt_symbol), str(row.trade_id)
        if symbol not in sizes or symbol not in rates or symbol not in slippages:
            raise ValueError(f"contract_cost_parameter_missing:{symbol}")
        size, rate, slip = float(sizes[symbol]), float(rates[symbol]), float(slippages[symbol])
        price, volume = float(row.price), float(row.volume)
        if not all(math.isfinite(value) for value in (size, rate, slip, price, volume)) or size <= 0 or price <= 0 or volume <= 0 or rate < 0 or slip < 0:
            raise ValueError(f"invalid_trade_or_cost_parameter:{trade_id}")
        sign, kind = direction_sign(str(row.direction)), offset_kind(str(row.offset))
        if not close_enough(float(row.signed_volume), sign * volume):
            raise ValueError(f"signed_volume_mismatch:{trade_id}")
        turnover = volume * size * price
        commission = turnover * rate
        slippage = volume * size * slip
        trade_totals["turnover"] += turnover
        trade_totals["commission"] += commission
        trade_totals["slippage"] += slippage
        queue = queues[symbol]

        if kind == "open":
            if queue and queue[0]["sign"] != sign:
                raise ValueError(f"open_opposite_to_existing_position:{trade_id}")
            if not queue:
                cycles[symbol] = {"vt_symbol": symbol, "first_trade_id": trade_id,
                                  "first_datetime": str(row.datetime), "direction": "long" if sign > 0 else "short",
                                  "open_trade_count": 0, "close_trade_count": 0, "opened_volume": 0.0,
                                  "closed_volume": 0.0, "gross_pnl": 0.0, "entry_commission": 0.0,
                                  "exit_commission": 0.0, "entry_slippage": 0.0, "exit_slippage": 0.0}
            cycle = cycles[symbol]
            cycle["open_trade_count"] += 1
            cycle["opened_volume"] += volume
            cycle["entry_commission"] += commission
            cycle["entry_slippage"] += slippage
            queue.append({"trade_id": trade_id, "datetime": str(row.datetime), "remaining": volume,
                          "price": price, "sign": sign, "entry_commission_per_unit": commission / volume,
                          "entry_slippage_per_unit": slippage / volume})
            continue

        if not queue or queue[0]["sign"] == sign:
            raise ValueError(f"unmatched_or_same_direction_close:{trade_id}")
        cycle = cycles[symbol]
        cycle["close_trade_count"] += 1
        cycle["closed_volume"] += volume
        cycle["exit_commission"] += commission
        cycle["exit_slippage"] += slippage
        remaining = volume
        while remaining > TOL:
            if not queue:
                raise ValueError(f"close_volume_exceeds_open:{trade_id}")
            entry = queue[0]
            matched = min(remaining, entry["remaining"])
            gross = (price - entry["price"]) * entry["sign"] * size * matched
            entry_commission = entry["entry_commission_per_unit"] * matched
            entry_slippage = entry["entry_slippage_per_unit"] * matched
            exit_commission = commission / volume * matched
            exit_slippage = slippage / volume * matched
            net = gross - entry_commission - entry_slippage - exit_commission - exit_slippage
            matches.append({"vt_symbol": symbol, "entry_trade_id": entry["trade_id"], "exit_trade_id": trade_id,
                            "entry_datetime": entry["datetime"], "exit_datetime": str(row.datetime),
                            "direction": "long" if entry["sign"] > 0 else "short", "volume": matched,
                            "entry_price": entry["price"], "exit_price": price, "gross_pnl": gross,
                            "entry_commission": entry_commission, "exit_commission": exit_commission,
                            "entry_slippage": entry_slippage, "exit_slippage": exit_slippage, "net_pnl": net,
                            "winning": int(net > TOL)})
            cycle["gross_pnl"] += gross
            entry["remaining"] -= matched
            remaining -= matched
            if entry["remaining"] <= TOL:
                queue.popleft()
        if not queue:
            cycle["last_trade_id"] = trade_id
            cycle["last_datetime"] = str(row.datetime)
            cycle["commission"] = cycle["entry_commission"] + cycle["exit_commission"]
            cycle["slippage"] = cycle["entry_slippage"] + cycle["exit_slippage"]
            cycle["net_pnl"] = cycle["gross_pnl"] - cycle["commission"] - cycle["slippage"]
            cycle["winning"] = int(cycle["net_pnl"] > TOL)
            completed.append(dict(cycle))
            del cycles[symbol]

    unclosed = []
    for symbol, queue in sorted(queues.items()):
        if queue:
            cycle = cycles[symbol]
            unclosed.append({"vt_symbol": symbol, "first_trade_id": cycle["first_trade_id"],
                             "direction": cycle["direction"],
                             "remaining_signed_volume": sum(item["remaining"] * item["sign"] for item in queue),
                             "remaining_abs_volume": sum(item["remaining"] for item in queue),
                             "open_lot_count": len(queue)})
    return matches, completed, unclosed, trade_totals


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--out", type=Path, help="默认写入 result 目录")
    args = parser.parse_args()
    root, result = args.repo_root.resolve(), args.result.resolve()
    out = args.out.resolve() if args.out else result
    out.mkdir(parents=True, exist_ok=True)
    trades_path, positions_path, parameters_path = [result / name for name in
                                                     ("trades.csv", "positions.csv", "effective_parameters.json")]
    trades = ordered_trades(trades_path)
    parameters = json.loads(parameters_path.read_text(encoding="utf-8"))
    ledger = positions_ledger(positions_path)
    matches, cycles, unclosed, trade_totals = calculate_outcomes(trades, parameters)

    errors: list[str] = []
    if not close_enough(ledger["totals"]["trade_count"], len(trades)):
        errors.append("positions_trade_count_mismatch")
    for key in ("turnover", "commission", "slippage"):
        if not close_enough(ledger["totals"][key], trade_totals[key]):
            errors.append(f"positions_{key}_mismatch")
    initial_nonzero = {symbol: value for symbol, value in ledger["first_start"].items() if abs(value) > TOL}
    if initial_nonzero:
        errors.append("initial_positions_nonzero")
    remaining = {row["vt_symbol"]: row["remaining_signed_volume"] for row in unclosed}
    endpoint_mismatch = {symbol: {"positions_end_pos": end, "fifo_end_pos": remaining.get(symbol, 0.0)}
                         for symbol, (_, end) in ledger["latest"].items()
                         if not close_enough(end, remaining.get(symbol, 0.0))}
    if endpoint_mismatch:
        errors.append("positions_endpoint_mismatch")
    cycle_net = sum(float(row["net_pnl"]) for row in cycles)
    fifo_match_net = sum(float(row["net_pnl"]) for row in matches)
    if not close_enough(cycle_net, fifo_match_net) and not unclosed:
        errors.append("fifo_cycle_net_mismatch")
    if not unclosed and not close_enough(cycle_net, ledger["totals"]["net_pnl"]):
        errors.append("positions_net_pnl_mismatch")
    wins = sum(row["winning"] for row in cycles)
    losses = sum(row["net_pnl"] < -TOL for row in cycles)
    breakeven = len(cycles) - wins - losses
    match_wins = sum(row["winning"] for row in matches)
    summary = {
        "status": "passed" if not errors else "failed", "errors": errors,
        "repo_root": str(root), "result": str(result),
        "method": "engine trade_id numeric sequence -> per-contract FIFO; primary win rate is complete flat-to-flat contract cycles, net of entry and exit costs",
        "profit_threshold": TOL,
        "trade_rows": len(trades), "trade_id_first": str(trades.iloc[0]["trade_id"]) if len(trades) else "",
        "trade_id_last": str(trades.iloc[-1]["trade_id"]) if len(trades) else "",
        "fifo_match_count": len(matches), "fifo_match_wins": match_wins,
        "fifo_match_win_rate_pct": 100 * match_wins / len(matches) if matches else None,
        "complete_cycle_count": len(cycles), "complete_cycle_wins": wins,
        "complete_cycle_losses": losses, "complete_cycle_breakeven": breakeven,
        "complete_cycle_win_rate_pct": 100 * wins / len(cycles) if cycles else None,
        "unclosed_cycle_count": len(unclosed),
        "unclosed_abs_contracts": sum(row["remaining_abs_volume"] for row in unclosed),
        "turnover": trade_totals["turnover"], "commission": trade_totals["commission"],
        "slippage": trade_totals["slippage"], "cycle_net_pnl": cycle_net,
        "fifo_matched_net_pnl": fifo_match_net, "positions_net_pnl": ledger["totals"]["net_pnl"],
        "positions_trade_count": ledger["totals"]["trade_count"],
        "positions_commission": ledger["totals"]["commission"],
        "positions_slippage": ledger["totals"]["slippage"],
        "positions_turnover": ledger["totals"]["turnover"],
        "initial_nonzero_positions": initial_nonzero, "endpoint_mismatch": endpoint_mismatch,
        "source_sha256": {"trades": sha256(trades_path), "positions": sha256(positions_path),
                          "effective_parameters": sha256(parameters_path)},
        "limitation": "FIFO allocates costs to closed quantity; incomplete cycles are excluded from the primary win-rate denominator. If positions remain open, total daily mark-to-market PnL is not a realized-PnL comparator.",
    }
    write_csv(out / "trade_outcomes_fifo_matches.csv", matches,
              ["vt_symbol", "entry_trade_id", "exit_trade_id", "entry_datetime", "exit_datetime", "direction",
               "volume", "entry_price", "exit_price", "gross_pnl", "entry_commission", "exit_commission",
               "entry_slippage", "exit_slippage", "net_pnl", "winning"])
    write_csv(out / "trade_outcomes_complete_cycles.csv", cycles,
              ["vt_symbol", "first_trade_id", "first_datetime", "last_trade_id", "last_datetime", "direction",
               "open_trade_count", "close_trade_count", "opened_volume", "closed_volume", "gross_pnl",
               "entry_commission", "exit_commission", "entry_slippage", "exit_slippage", "commission", "slippage",
               "net_pnl", "winning"])
    write_csv(out / "trade_outcomes_unclosed.csv", unclosed,
              ["vt_symbol", "first_trade_id", "direction", "remaining_signed_volume", "remaining_abs_volume", "open_lot_count"])
    (out / "trade_outcomes_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ("status", "trade_rows", "complete_cycle_count",
                                                   "complete_cycle_wins", "complete_cycle_win_rate_pct",
                                                   "unclosed_cycle_count", "slippage", "commission", "errors")}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
