"""Independently audit Stage054's gold stops, ordered funding and financial ledgers."""
import argparse
import json
from bisect import bisect_left
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from stage040_s19_without_gold_audit import (
    CAPITAL, DAY_COLUMNS, OPEN_COLUMNS, TARGET, cents, check_manifest, load_json, near, read_csv, sha,
)
from stage043_s19_daily_one_audit import Holding, Signal
from stage044_s19_daily_halfyear_audit import STARTS, financial_metrics
from stage045_s19_weekly_shadow_filter_audit import completed_weeks
from stage046_s44_individual_2022_audit import table
from stage048_s26_full_audit import TAIL_CERT, extend_raw_market
from stage049_s26_halfyear_audit import check_values
from stage052_s21_margin_gate_audit import verify_risk_table

line = Path(__file__).resolve().parents[1]


def reconcile(folder, start, config, calendar, guard_calendar, mains, symbols, by_epoch, settings, weeks, week_index, weekly_bar):
    products = config["products"]
    dates = [day for day in calendar if day >= start]
    assert dates[0] >= start and dates[-1] == TARGET
    positions, orders, reversals = {}, {}, {}
    touch_events, anchors = [], {}
    fills, signals, bodies, ma, four_up, gaps, opening, daily_marks = [], [], [], [], [], [], [], []
    cycles, open_sizes = {}, Counter()
    branches = Counter()
    delayed, risk = [], []
    cash, slip_total, fee_total = CAPITAL * 100, 0, 0
    rates = {symbol: int(Decimal(str(value)) * 10_000) for symbol, value in settings["margin_ratios"].items()}

    def guard(bar):
        month = bar.epoch.rsplit(".", 1)[1]
        boundary = f"{month[:4]}-{month[4:]}-01"
        index = bisect_left(guard_calendar, boundary)
        return guard_calendar[index - 5] if 5 <= index < len(guard_calendar) else boundary

    def valuation(day, opening):
        value = margin = 0
        for position in positions.values():
            bar = by_epoch.get((day, position.bar.epoch))
            mark = position.mark if bar is None else bar.op if opening else bar.close
            notional = mark * settings["sizes"][position.bar.symbol]
            value += position.side * notional
            margin += notional * rates[position.bar.symbol]
        return value, margin

    def permit(day, product, bar, kind, role, decision, side, stop):
        size = settings["sizes"][bar.symbol]
        cost_cents = cents(size * settings["slippages"][bar.symbol])
        cost_cents += cents(size * (bar.op / 100) * settings["rates"][bar.symbol])
        value, margin_units = valuation(day, True)
        equity_cents = cash + value
        free_units = equity_cents * 10_000 - margin_units
        new_margin = bar.op * size * rates[bar.symbol]
        required = new_margin + cost_cents * 10_000
        assert required > 0
        affordable = max(0, free_units // required)
        allowed = free_units >= required
        risk.append(dict(
            date=day, product=product, contract=bar.symbol, epoch=bar.epoch, kind=kind, role=role,
            signal_day=decision, side=side, price=bar.op / 100, stop=stop / 100, equity=equity_cents / 100,
            margin=margin_units / 1_000_000, free_cash=free_units / 1_000_000,
            margin_per_lot=new_margin / 1_000_000, entry_cost_per_lot=cost_cents / 100,
            requested_lots=1, affordable_lots=affordable, executed_lots=int(allowed),
            status="filled" if allowed else "margin_below_one_lot",
            surplus=(free_units - required) / 1_000_000,
        ))
        return allowed

    def snapshot(day, sequence, product="", reason="before_fills"):
        value, margin = valuation(day, True)
        equity, margin = (cash + value) / 100, margin / 1_000_000
        opening.append((day, sequence, product, reason, equity, margin, equity - margin, len(positions)))

    def fill(day, product, bar, side, number, reason, decision, stop, price=None, opening_phase=True):
        nonlocal cash, slip_total, fee_total
        size = settings["sizes"][bar.symbol]
        slip = cents(size * settings["slippages"][bar.symbol])
        price = bar.op if price is None else price
        fee = cents(size * (price / 100) * settings["rates"][bar.symbol])
        flow = -side * size * price - slip - fee
        cash += flow
        slip_total += slip
        fee_total += fee
        cycles[number]["flow"] += flow
        fills.append((day, product, bar.symbol, bar.epoch, number, side, 1, price / 100, size, slip / 100,
                      fee / 100, reason, decision, stop / 100 if stop is not None else "", bar.high == bar.low))
        if opening_phase:
            open_sizes[day] += 1
            snapshot(day, open_sizes[day], product, reason)

    def close_position(day, product, bar, reason, decision, stop=None, price=None, opening_phase=True):
        held = positions.pop(product)
        fill(day, product, bar, -held.side, held.number, reason, decision, stop, price, opening_phase)
        if reason != "roll_close":
            cycles[held.number]["exit"] = day

    def gold_stop(day, product, held, bar, index, phase):
        assert product == "au.SHFE"
        reference = weekly_bar(held.bar.epoch, index - 1)
        if reference is not None:
            anchor = reference.low if held.side == 1 else reference.high
            anchor_day = weeks[index - 1][-1]
            anchors[held.number, held.bar.epoch] = (anchor, anchor_day)
        else:
            assert (held.number, held.bar.epoch) in anchors, (day, held)
            anchor, anchor_day = anchors[held.number, held.bar.epoch]
            branches["gold_anchor_carry_" + phase] += 1
        if bar is None:
            branches["gold_no_daily_bar_" + phase] += 1
            if phase=="after_open":
                gaps.append((day, product, held.bar.symbol, "gold_stop_day_unavailable"))
            return False
        gap = held.side * (bar.op - anchor) <= 0
        touched = held.side * ((bar.low if held.side == 1 else bar.high) - anchor) <= 0
        if not gap and (phase == "old_open" or not touched):
            return False
        price = bar.op if gap else anchor
        reason = "gold_touch_open_gap" if phase == "old_open" else "gold_touch_intraday"
        if phase=="after_open" and gap: branches["gold_new_open_already_crossed"] += 1
        close_position(day, product, bar, reason, anchor_day, anchor, price, phase == "old_open")
        touch_events.append(dict(date=day, product=product, contract=bar.symbol, epoch=bar.epoch,
                                 cycle=held.number, direction=held.side, phase=phase,
                                 reason=reason, anchor_day=anchor_day, stop=anchor/100,
                                 price=price/100, open=bar.op/100, high=bar.high/100,
                                 low=bar.low/100, close=bar.close/100,
                                 carried=reference is None, one_price=bar.high==bar.low))
        branches[phase,reason] += 1
        return True

    def add_signal(day, product, key, current, prev, older, stop, destination):
        order = Signal(key, day, current, stop)
        destination[product] = order
        signals.append((day, product, current.symbol, current.epoch, key, stop / 100, current.close / 100,
                        prev.close / 100, older.close / 100 if older else ""))

    for index in range(bisect_left(calendar, start), len(calendar)):
        day, yesterday = calendar[index], calendar[index - 1]
        this_week = week_index[day]
        snapshot(day, 0)
        for product in products:
            held = positions.get(product)
            order = orders.pop(product, None)
            conditional = reversals.pop(product, None)
            entry_role = "entry"
            old_bar = by_epoch.get((day, held.bar.epoch)) if held else None
            if held and product=="au.SHFE" and gold_stop(day, product, held, old_bar, this_week, "old_open"):
                assert not order and not conditional
                held = None
                old_bar = None
            guard_active = held and day >= guard(held.bar)
            if held and order and order.action.startswith("close_"):
                if old_bar is None:
                    gaps.append((day, product, held.bar.symbol, "exit_open_unavailable"))
                    orders[product] = order
                    branches["exit_missing_open"] += 1
                    if conditional:
                        branches["conditional_reverse_expired_after_missing_exit"] += 1
                    order = None
                else:
                    if order.day != yesterday:
                        assert all((calendar[prior], order.bar.epoch) not in by_epoch
                                   for prior in range(bisect_left(calendar, order.day) + 1, index))
                        delayed.append(dict(start=start, product=product, symbol=old_bar.symbol,
                                            signal=order.day, next_session=calendar[bisect_left(calendar, order.day) + 1],
                                            execution=day, open=old_bar.op / 100))
                    close_position(day, product, old_bar, "weekly_stop", order.day, order.stop)
                    held, order = None, conditional
                    if order:
                        entry_role = "reversal"
            elif guard_active:
                if old_bar is None:
                    gaps.append((day, product, held.bar.symbol, "delivery_guard_exit_open_unavailable"))
                    branches["guard_exit_missing_open"] += 1
                else:
                    close_position(day, product, old_bar, "delivery_guard_exit", guard(held.bar))
                    held = order = None

            if order:
                assert held is None and order.day == yesterday
                current = by_epoch.get((day, order.bar.epoch))
                if day >= guard(order.bar):
                    gaps.append((day, product, order.bar.symbol, "entry_delivery_guard"))
                elif current is None or current.high == current.low:
                    gaps.append((day, product, order.bar.symbol, "entry_open_unavailable"))
                    branches["entry_missing_open" if current is None else "entry_one_price_open"] += 1
                else:
                    side = 1 if order.action == "open_long" else -1
                    if permit(day, product, current, "entry", entry_role, order.day, side, order.stop):
                        number = len(cycles) + 1
                        cycles[number] = dict(product=product, direction=side, entry=day, exit="", flow=0)
                        positions[product] = Holding(current, side, number, day, current.op)
                        if product=="au.SHFE":
                            anchors[number,current.epoch] = (order.stop, order.day)
                        fill(day, product, current, side, number, "entry", order.day, order.stop)
            elif held and product not in orders and not guard_active:
                main = mains.get((yesterday, product))
                if main and main != held.bar.symbol:
                    current, old_main = symbols.get((day, main)), symbols.get((yesterday, main))
                    protection = weekly_bar(old_main.epoch, this_week - 1) if old_main else None
                    if current and day >= guard(current):
                        gaps.append((day, product, main, "roll_target_delivery_guard"))
                    elif (old_bar and current and protection and current.epoch == old_main.epoch
                          and current.high > current.low):
                        side, number, entered = held.side, held.number, held.entered
                        close_position(day, product, old_bar, "roll_close", yesterday)
                        stop = protection.low if side == 1 else protection.high
                        if permit(day, product, current, "roll", "roll", yesterday, side, stop):
                            positions[product] = Holding(current, side, number, entered, current.op)
                            if product=="au.SHFE":
                                anchors[number,current.epoch] = (stop,weeks[this_week-1][-1])
                            fill(day, product, current, side, number, "roll_open", yesterday, stop)
                        else:
                            cycles[number]["exit"] = day
                            closed = list(fills[-1])
                            closed[11] = "roll_funding_exit"
                            fills[-1] = tuple(closed)
                            observed = list(opening[-1])
                            observed[3] = "roll_funding_exit"
                            opening[-1] = tuple(observed)
                    else:
                        gaps.append((day, product, held.bar.symbol, "roll_open_pair_or_history_unavailable"))
                        branches["roll_pair_unavailable"] += 1

        held = positions.get("au.SHFE")
        if held:
            gold_stop(day, "au.SHFE", held, by_epoch.get((day,held.bar.epoch)), this_week, "after_open")

        for product in products:
            held = positions.get(product)
            current = None
            if held:
                assert day[:7].replace("-", "") <= held.bar.epoch.rsplit(".", 1)[1]
                current = by_epoch.get((day, held.bar.epoch))
                if current:
                    held.mark = current.close
                else:
                    gaps.append((day, product, held.bar.symbol, "held_close_stale"))
            if product in orders or day != weeks[this_week][-1]:
                continue
            reversing = None
            if held and product=="au.SHFE":
                if not current or not weekly_bar(held.bar.epoch,this_week) or not weekly_bar(held.bar.epoch,this_week-1):
                    gaps.append((day, product, held.bar.symbol, "weekly_history_incomplete"))
                continue
            if held:
                current = weekly_bar(held.bar.epoch, this_week) if current else None
                prev = weekly_bar(held.bar.epoch, this_week - 1)
                if current is None or prev is None:
                    gaps.append((day, product, held.bar.symbol, "weekly_history_incomplete"))
                    continue
                bound = prev.low if held.side == 1 else prev.high
                if held.side * (current.close - bound) > 0:
                    continue
                add_signal(day, product, "close_long" if held.side == 1 else "close_short",
                           current, prev, None, bound, orders)
                reversing = -held.side

            main = mains.get((day, product))
            if main is None:
                continue
            current = symbols.get((day, main))
            bars = [weekly_bar(current.epoch, this_week - offset) for offset in range(21)] if current else [None] * 21
            current, prev, older = bars[:3]
            if current is None or prev is None or older is None:
                if reversing is None:
                    gaps.append((day, product, main, "weekly_history_incomplete"))
                continue
            if current.close > prev.close > older.close:
                side, action = 1, "open_long"
            elif current.close < prev.close < older.close:
                side, action = -1, "open_short"
            else:
                continue
            if reversing and reversing != side:
                continue
            prefix = (day, product, current.symbol, current.epoch, action)
            same_body = all(side * (bar.close - bar.op) > 0 for bar in (current, prev))
            bodies.append((*prefix, "allowed" if same_body else "blocked",
                           current.op / 100, current.close / 100, prev.op / 100, prev.close / 100))
            if not same_body:
                continue
            slopes = [(current.close - bars[p].close) / (100 * p) for p in (5, 10, 20)] if all(bars) else None
            ma_block = slopes is not None and all(side * slope < 0 for slope in slopes)
            ma.append((*prefix, "blocked" if ma_block else "incomplete" if slopes is None else "allowed",
                       *(slopes if slopes is not None else ("", "", ""))))
            if ma_block:
                continue
            if side == 1 and all(bars[:5]) and all(x.close > y.close for x, y in zip(bars[:4], bars[1:5])):
                four_up.append((*prefix[:4], "reversal" if reversing else "entry",
                                *(bar.close / 100 for bar in reversed(bars[:5]))))
                continue
            add_signal(day, product, action, current, prev, older, current.low if side == 1 else current.high,
                       reversals if reversing else orders)

        value, margin = valuation(day, False)
        daily_marks.append(((cash + value) / 100, cash / 100, value / 100, margin / 1_000_000,
                            len(positions), slip_total / 100, fee_total / 100))

    for name, expected in (("fills", fills), ("signals", signals), ("gaps", gaps), ("entry_filter", ma),
                           ("week_body_filter", bodies), ("four_up_blocks", four_up), ("opening_funding", opening)):
        actual = table(folder, name)
        if actual.empty:
            assert not expected, (folder, name)
            continue
        generated = pd.DataFrame(expected, columns=actual.columns)
        nullable = {"stop", "older_close", "ma5_slope", "ma10_slope", "ma20_slope"}
        for field in nullable.intersection(actual.columns):
            actual[field] = pd.to_numeric(actual[field].mask(actual[field].eq("")))
            generated[field] = pd.to_numeric(generated[field].mask(generated[field].eq("")))
        pd.testing.assert_frame_equal(generated, actual, check_dtype=False, check_exact=False, rtol=0, atol=1e-8,
                                      obj=name)
    marks = pd.DataFrame(daily_marks, columns=DAY_COLUMNS)
    observed = read_csv(folder, "daily")
    assert observed.date.tolist() == dates
    near(observed[DAY_COLUMNS], marks)

    terminal = load_json(folder / "terminal.json")
    assert set(terminal["positions"]) == set(positions)
    terminal_value = {}
    for product, holding in positions.items():
        position = terminal["positions"][product]
        assert (position["symbol"], position["epoch"], position["side"], position["cycle"],
                position["entry_day"], cents(position["mark"])) == (
            holding.bar.symbol, holding.bar.epoch, holding.side, holding.number, holding.entered, holding.mark)
        assert by_epoch[TARGET, holding.bar.epoch].close == holding.mark
        terminal_value[holding.number] = holding.side * holding.mark * settings["sizes"][holding.bar.symbol]
    for section, expected in (("pending", orders), ("pending_reversals", reversals)):
        normalized = {product: (*order[:4], cents(float(order[4]))) for product, order in terminal[section].items()}
        assert normalized == {product: (order.action, TARGET, order.bar.symbol, order.bar.epoch, order.stop)
                              for product, order in expected.items()}
    cycle_csv = read_csv(folder, "cycles")
    assert len(cycle_csv) == len(cycles)
    for row in cycle_csv.itertuples(index=False):
        cycle = cycles[row.cycle]
        mark = terminal_value.get(row.cycle, 0)
        assert (row.product, row.direction, row.entry_day, row.exit_day, cents(row.cash_flow),
                cents(row.terminal_mark), cents(row.net_pnl)) == (
            cycle["product"], cycle["direction"], cycle["entry"], cycle["exit"], cycle["flow"],
            mark, cycle["flow"] + mark)
    return marks, pd.DataFrame(opening, columns=OPEN_COLUMNS), cycles, len(orders), len(reversals), branches, delayed, risk, touch_events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--certificate", type=Path)
    args = parser.parse_args()
    run = reconcile
    result=line/'outputs/stage054_s21_gold_touch_halfyear_20261104'
    stage052=line/'outputs/stage052_s21_margin_gate_20261104'
    config54=load_json(result/'receipt.json')
    config52=load_json(stage052/'receipt.json')
    result_manifest_entries, baseline_manifest_entries = map(check_manifest, (result, stage052))
    print("manifest entries", result_manifest_entries, baseline_manifest_entries, flush=True)
    assert config54['stage052_manifest_sha256']==sha(stage052/'SHA256SUMS')
    assert config54['stage052_audit_sha256']==sha(line/'reviews/stage052_s21_margin_gate_audit.json')
    assert config54['stage052_entrypoint_sha256']==config52['entrypoint_sha256']==sha(line/'tools/stage052_s21_margin_gate.py')
    assert config54['entrypoint_sha256']==sha(line/'tools/stage054_s21_gold_touch_halfyear.py')
    assert config54['engine_sha256']==config52['engine_sha256']==sha(line/'tools/run_weekly_portfolio.py')
    assert config54['design_sha256']==sha(line/'stages/20261105_1202_stage054_gold_touch_design.md')
    for k in ['market_sha256','cutoff','capital','products','starts','gate','attempted_runs','completed_runs','unknown_runs']:
        assert config54[k]==config52[k],k
    pinned=load_json(stage052/STARTS[0]/'inputs.json')
    pins=pinned['source_sha256']|config54['market_sha256']
    assert len(config54['market_sha256'])==35 and len(pins)==42
    assert all(sha(Path(path))==digest for path,digest in pins.items())
    assert (len(STARTS),STARTS)==(24,config54['starts'])
    market=extend_raw_market(load_json(TAIL_CERT))
    weeks=completed_weeks(market[1],market[4])
    combined=table(result,'window_metrics').set_index('calendar_start',verify_integrity=True)
    controls=table(stage052,'window_metrics').set_index('calendar_start',verify_integrity=True)
    assert combined.index.tolist()==controls.index.tolist()==STARTS
    counts_total=Counter()
    flags=Counter()
    stop_counts=Counter()
    branch_counts=Counter()
    outcomes=Counter()
    by_window={}
    for start in STARTS:
        old,new=stage052/start,result/start
        old_cfg=load_json(old/'inputs.json')
        cfg=load_json(new/'inputs.json')
        assert cfg=={**old_cfg, 'gold_stop_rule':config54['gold_stop_rule']}
        assert cfg['fixed_one_margin_gate']==config54['gate']
        marks,opening,cycles,pending,cond,branches,delayed,risk,touch=run(new,start,cfg,*market,*weeks)
        performance,counts,_=financial_metrics(new,marks,opening,pending)
        status,equal=verify_risk_table(new,risk,opening)
        assert not pending and not cond
        counts_total.update(counts)
        branch_counts.update(branches)
        ob=table(new,'gold_touch_stops')
        rows=[{**row,'side':row['direction']} for row in touch]
        pd.testing.assert_frame_equal(pd.DataFrame(rows,columns=ob.columns),ob,check_dtype=False,check_exact=False,rtol=0,atol=1e-8)
        assert not ob.one_price.any()
        reasons=Counter(ob.reason)
        stop_counts.update(reasons)
        reference=controls.loc[start]
        stats={
            'stop_count':len(touch),
            'open_gap_count':reasons['gold_touch_open_gap'],
            'intraday_count':reasons['gold_touch_intraday'],
            'one_price_count':int(ob.one_price.sum()),
            'blocked_total':sum(n for (flag,_),n in status.items() if flag!='filled'),
            'nonpositive_equity_days':counts['nonpositive_days'],
            'minimum_equity':min(marks.equity.min(),opening.equity.min()),
        }
        expected={f'touch_{k}':v for k,v in (performance|stats).items()}
        expected.update({k.replace('gated_','weekly_',1):v for k,v in reference.items() if k.startswith('gated_')})
        expected.update({k:reference[k] for k in ('first_session','last_session','days')})
        expected['weekly_blocked_total']=reference['blocked_total']
        assert set(expected)==set(combined.columns),(set(expected)-set(combined.columns),set(combined.columns)-set(expected))
        for k,v in expected.items(): check_values(combined.at[start,k],v,(start,k))
        flags.update(status)
        outcomes.update({k+'_better':int(combined.loc[start,'touch_'+k]>combined.loc[start,'weekly_'+k]) for k in ('net_pnl','max_dd_pct','sharpe')})
        pnl_delta=performance['net_pnl']-reference.gated_net_pnl
        gold_delta=performance['gold_net_pnl']-reference.gated_gold_net_pnl
        print(start, 'net',performance['net_pnl'],'delta',pnl_delta,'gold/other',gold_delta,pnl_delta-gold_delta,'risk',len(risk),'stops',len(touch),flush=True)
        by_window[start] = dict(portfolio_pnl_delta=float(pnl_delta), gold_pnl_delta=float(gold_delta),
                                other_products_pnl_delta=float(pnl_delta-gold_delta), touch_stops=len(touch))
    print('TOTALS',counts_total,'decisions',flags,'gold stop counts',stop_counts,'branches',branch_counts,'outcomes',outcomes,flush=True)
    certificate = dict(
        schema="stage054_independent_gold_touch_audit_v1",
        verdict="PASS_WITH_LIMITATIONS",
        audited_at=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        audit_method="Independent integer-cent state machine derived from the Stage052 independent reviewer; no production runner import or invocation.",
        audit_script_sha256=sha(Path(__file__)),
        audit_reference_sha256=sha(line/"reviews/stage052_s21_margin_gate_audit.py"),
        result_manifest_sha256=sha(result/"SHA256SUMS"),
        baseline_manifest_sha256=sha(stage052/"SHA256SUMS"),
        result_manifest_entries=result_manifest_entries,
        baseline_manifest_entries=baseline_manifest_entries,
        market_input_hashes=35,
        strategy_input_hashes=7,
        windows=dict(attempted=len(STARTS), verified=len(by_window), unknown=0),
        ledger_rows=dict(counts_total),
        funding=dict(decisions=sum(flags.values()), approved=sum(v for (k,_),v in flags.items() if k=="filled"),
                     denied=sum(v for (k,_),v in flags.items() if k!="filled"),
                     by_status_and_role={f"{k}:{role}": v for (k,role),v in flags.items()}),
        gold_exits=dict(stop_counts),
        gold_branches_not_reached_in_sample=["new or rolled position already through its stop at open",
                                             "incomplete prior weekly bar requiring anchor carry",
                                             "missing physical daily bar for held gold",
                                             "gold stop on a one-price daily bar"],
        comparisons=dict(return_better=outcomes["net_pnl_better"],
                         return_worse=sum(x["portfolio_pnl_delta"]<0 for x in by_window.values()),
                         return_tied=sum(x["portfolio_pnl_delta"]==0 for x in by_window.values()),
                         drawdown_better=outcomes["max_dd_pct_better"],
                         sharpe_better=outcomes["sharpe_better"]),
        limitations=["Daily OHLC proxy; exact intraday timestamp, price jumps, queue and executable fills are not established.",
                     "Opening margin threshold only; intraday margin, broker liquidation and actual commissions are not modeled.",
                     "Overlapping start windows and after-the-fact gold selection limit economic generalization."],
        by_window=by_window,
    )
    if args.certificate:
        with args.certificate.open("x") as file:
            json.dump(certificate, file, indent=2, ensure_ascii=False)
            file.write("\n")


if __name__ == "__main__":
    main()

