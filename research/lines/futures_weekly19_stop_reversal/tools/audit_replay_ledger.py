"""Reconcile Weekly19 physical-contract cycles and the A/C wealth bridge."""
import argparse
from collections import Counter
import json
from math import sqrt
from pathlib import Path

import pandas as pd

INITIAL = 300_000
TOLERANCE = 1e-6


def metrics(daily, cycles):
    equity = daily.total_account_equity
    returns = equity.pct_change().fillna(0)
    wins = cycles.loc[cycles.net > TOLERANCE, "net"]
    losses = -cycles.loc[cycles.net < -TOLERANCE, "net"]
    return dict(
        actual_start=daily.index[0], actual_end=daily.index[-1], days=len(daily),
        end_equity=equity.iloc[-1], trading_end_equity=daily.trading_account_equity.iloc[-1],
        reserve_end=daily.reserve_balance.iloc[-1], reserve_transferred=daily.cumulative_transfer.iloc[-1],
        return_pct=(equity.iloc[-1] / INITIAL - 1) * 100,
        max_drawdown_pct=(equity / equity.cummax().clip(lower=INITIAL) - 1).min() * 100,
        sharpe=returns.mean() / returns.std() * sqrt(252),
        slippage=daily.slippage.sum(), commission=daily.commission.sum(),
        fills=int(daily.trade_count.sum()), closed_cycles=len(cycles),
        wins=len(wins), losses=len(losses),
        win_rate_pct=len(wins) / len(cycles) * 100,
        average_payoff=wins.mean() / losses.mean(),
        profit_factor=wins.sum() / losses.sum(), net_pnl=daily.net_pnl.sum(),
    )


def physical_cycles(fills, inventory, sizes):
    active = {}
    closed = []
    for row in fills.itertuples(index=False):
        if row.offset not in {"open", "close"} or row.side not in {"long", "short"}:
            raise ValueError("unexpected trade direction/offset")
        sign = 1 if row.side == "long" else -1
        if row.symbol not in active:
            if row.offset != "open":
                raise ValueError(f"close without owner: {row.trade_id}")
            active[row.symbol] = dict(symbol=row.symbol, entry=row.date, direction=row.side, sleeve=row.sleeve,
                                      quantity=0, gross=0.0, commission=0.0, slippage=0.0)
        item = active[row.symbol]
        if row.sleeve != item["sleeve"]:
            raise ValueError(f"changed sleeve mid-cycle: {row.trade_id}")
        adding = (item["direction"] == row.side)
        if adding != (row.offset == "open"):
            raise ValueError(f"invalid offset: {row.trade_id}")
        item["quantity"] += sign * row.volume
        if item["quantity"] and (item["quantity"] > 0) != (item["direction"] == "long"):
            raise ValueError(f"overclose: {row.trade_id}")
        item["gross"] -= sign * row.price * row.volume * sizes[row.symbol]
        item["commission"] += row.commission
        item["slippage"] += row.slippage
        if not item["quantity"]:
            item["exit"] = row.date
            item["net"] = item["gross"] - item["commission"] - item["slippage"]
            closed.append(active.pop(row.symbol))

    if set(active) != set(inventory):
        raise ValueError("terminal inventory differs from fill inventory")
    for symbol, item in active.items():
        mark = inventory[symbol]
        if item["quantity"] != mark["volume"] or item["sleeve"] != mark["sleeve"]:
            raise ValueError("terminal position size/owner mismatch")
        item["gross"] += item["quantity"] * mark["close"] * sizes[symbol]
        item["net"] = item["gross"] - item["commission"] - item["slippage"]
    return pd.DataFrame(closed), list(active.values())


def read_arm(root):
    manifest = json.loads((root / "contract_settings.json").read_text())
    inventory = json.loads((root / "terminal_inventory.json").read_text())
    fills = pd.read_csv(root / "trades.csv", keep_default_na=False)
    if "sleeve" not in fills:
        fills["sleeve"] = "native"
    daily = pd.read_csv(root / "daily.csv", index_col="date")
    cycles, marked = physical_cycles(fills, inventory, manifest["sizes"])
    report = metrics(daily, cycles)
    reconciled = cycles.net.sum() + sum(row["net"] for row in marked)
    if abs(reconciled - report["net_pnl"]) > TOLERANCE:
        raise ValueError(f"trade-to-daily PnL residual {reconciled - report['net_pnl']}")
    if abs(daily.net_pnl.sum() + INITIAL - daily.total_account_equity.iloc[-1]) > TOLERANCE:
        raise ValueError("daily wealth bridge residual")
    if fills.trade_id.duplicated().any() or len(fills) != report["fills"]:
        raise ValueError("fill inventory mismatch")
    report["closed_pnl"] = cycles.net.sum()
    report["terminal_mtm"] = sum(row["net"] for row in marked)
    return daily, fills, cycles, marked, report


def validate_reverse(root, fills, calendar):
    decisions = pd.read_csv(root / "reversal_decisions.csv", keep_default_na=False)
    if decisions.position_id.duplicated().any() or decisions.close_trade_id.duplicated().any():
        raise ValueError("duplicate reversal decision")
    next_day = dict(zip(calendar, calendar[1:]))
    lookup = fills.set_index("trade_id")
    accepted = decisions.loc[decisions.status == "filled"]
    for row in decisions.itertuples(index=False):
        close = lookup.loc[row.close_trade_id]
        if not (
            row.symbol == close.symbol and row.close_day == close.date
            and row.signal_day == close.signal_day and row.signal_reason == close.bound_stop_reason and row.position_id == close.bound_stop_position_id
            and close.offset == "close" and close.sleeve == "native"
            and next_day[row.close_day] == row.decision_day
        ):
            raise ValueError(f"invalid close dependency {row.position_id}")
        if row.status != "filled":
            continue
        opened = lookup.loc[row.open_trade_id]
        date_fields = [pd.Timestamp(d).isocalendar()[:2] for d in (row.close_day, row.decision_day)]
        stop = float(row.initial_stop)
        if not (
            date_fields[0] == date_fields[1] and opened.date > close.date
            and opened.offset == "open" and opened.symbol == close.symbol and opened.sleeve == "weekly19_stop_reversal"
            and opened.side == close.side == row.direction and opened.volume == int(float(row.volume))
            and opened.price == float(row.price) and opened.date == row.decision_day
            and ((opened.price < stop) if opened.side == "short" else (opened.price > stop))
        ):
            raise ValueError(f"invalid reversal opening {row.position_id}")
    actual = fills[(fills.sleeve == "weekly19_stop_reversal") & (fills.offset == "open")]
    if Counter(accepted.open_trade_id) != Counter(actual.trade_id):
        raise ValueError("reversal openings do not match decisions")
    return decisions


def compare(a, c):
    ad, _, _, _, ar = read_arm(a)
    cd, cf, cc, cm, cr = read_arm(c)
    if not ad.index.equals(cd.index):
        raise ValueError("A/C calendar mismatch")
    decisions = validate_reverse(c, cf, ad.index)
    sleeve = cc.loc[cc.sleeve == "weekly19_stop_reversal"]
    sleeve_mtm = sum(row["net"] for row in cm if row["sleeve"] == "weekly19_stop_reversal")
    direct = sleeve.net.sum() + sleeve_mtm
    delta = cr["net_pnl"] - ar["net_pnl"]
    annual = pd.DataFrame({"A": ad.net_pnl, "C": cd.net_pnl})
    annual = annual.groupby(annual.index.str[:4]).sum()
    annual["C_minus_A"] = annual.C - annual.A
    return dict(A=ar, C=cr, portfolio_delta=delta, direct_reversal_net=direct,
                other_path_delta=delta-direct, reversal_closed_pnl=sleeve.net.sum(),
                reversal_terminal_mtm=sleeve_mtm, reversal_closed_cycles=len(sleeve),
                reversal_slippage=sleeve.slippage.sum() + sum(
                    row["slippage"] for row in cm if row["sleeve"] == "weekly19_stop_reversal"
                ), reversal_outcomes=dict(Counter(decisions.status))), annual


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("a", type=Path)
    parser.add_argument("c", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    summary, annual = compare(args.a, args.c)
    args.output.mkdir(parents=True)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, default=lambda x: x.item()) + "\n")
    annual.to_csv(args.output / "annual.csv")
    print((args.output / "summary.json").read_text(), end="")


if __name__ == "__main__":
    main()
