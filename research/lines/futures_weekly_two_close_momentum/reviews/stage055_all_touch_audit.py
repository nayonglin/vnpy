"""Independently audit Stage055's all-product stops, ordered funding and financial ledgers."""
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
    touch_events, anchors, locked, lock_events = [], {}, {}, []
    carry_days, unavailable_days, wait_days = set(), set(), set()
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

    def touch_stop(day, product, held, bar, week_no, phase):
        if product in locked:
            if phase != "old_open":
                return "locked"
            event = locked[product]
            assert (held.number, held.bar.epoch) == (event["cycle"], event["epoch"])
            if bar is None or bar.low == bar.high:
                wait_days.add((day, product, held.bar.epoch))
                gaps.append((day, product, held.bar.symbol, "touch_exit_waiting_for_liquidity"))
                return "locked"
            reason = "touch_after_one_price"
            close_position(day, product, bar, reason, event["anchor_day"], event["stop_cents"],
                           bar.op, opening_phase=True)
            touch_events.append(dict(event, date=day, reason=reason, phase=phase, price=bar.op/100,
                                     open=bar.op/100, high=bar.high/100, low=bar.low/100,
                                     close=bar.close/100, one_price=False))
            del locked[product]
            branches[reason] += 1
            return "closed"

        reference = weekly_bar(held.bar.epoch, week_no-1)
        key = held.number, held.bar.epoch
        if reference is None:
            assert key in anchors, (day, held)
            stop, anchor_day = anchors[key]
            carry_days.add((day, product, held.bar.epoch))
        else:
            stop = reference.low if held.side==1 else reference.high
            anchor_day = weeks[week_no-1][-1]
            anchors[key] = (stop,anchor_day)
        if bar is None:
            unavailable_days.add((day, product, held.bar.epoch))
            if phase=="after_open":
                gaps.append((day, product, held.bar.symbol, "touch_stop_day_unavailable"))
            return "open"
        through = (bar.op-stop)*held.side <= 0
        extreme = bar.low if held.side==1 else bar.high
        touched = (extreme-stop)*held.side <= 0
        if not through and (phase=="old_open" or not touched):
            return "open"

        event = dict(trigger_day=day, product=product, contract=bar.symbol, epoch=bar.epoch,
                     cycle=held.number, side=held.side, anchor_day=anchor_day, stop=stop/100,
                     stop_cents=stop, trigger_open=bar.op/100, trigger_high=bar.high/100,
                     trigger_low=bar.low/100, trigger_close=bar.close/100,
                     trigger_phase=phase, trigger_one_price=bar.low==bar.high)
        if bar.low == bar.high:
            assert phase=="old_open", event
            locked[product] = event
            lock_events.append(event)
            branches["one_price_lock"] += 1
            gaps.append((day, product, held.bar.symbol, "touch_trigger_one_price"))
            return "locked"

        reason = "touch_open_gap" if phase=="old_open" else "touch_intraday"
        price = bar.op if through else stop
        if phase=="after_open" and through:
            branches["new_open_already_crossed"] += 1
        close_position(day, product, bar, reason, anchor_day, stop, price, opening_phase=phase=="old_open")
        touch_events.append(dict(event,date=day,reason=reason,phase=phase,price=price/100,
                                 open=bar.op/100, high=bar.high/100, low=bar.low/100,
                                 close=bar.close/100, one_price=False))
        branches[reason] += 1
        return "closed"

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
            if held:
                assert not order and not conditional
                status = touch_stop(day, product, held, old_bar, this_week, "old_open")
                if status == "locked":
                    continue
                if status == "closed":
                    held = old_bar = None

            guard_active = held and day >= guard(held.bar)
            if guard_active:
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

        for product in products:
            held = positions.get(product)
            if held:
                touch_stop(day, product, held, by_epoch.get((day,held.bar.epoch)), this_week, "after_open")

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
            if held:
                if not current or not weekly_bar(held.bar.epoch,this_week) or not weekly_bar(held.bar.epoch,this_week-1):
                    gaps.append((day, product, held.bar.symbol, "weekly_history_incomplete"))
                continue

            main = mains.get((day, product))
            if main is None:
                continue
            current = symbols.get((day, main))
            bars = [weekly_bar(current.epoch, this_week - offset) for offset in range(21)] if current else [None] * 21
            current, prev, older = bars[:3]
            if current is None or prev is None or older is None:
                gaps.append((day, product, main, "weekly_history_incomplete"))
                continue
            if current.close > prev.close > older.close:
                side, action = 1, "open_long"
            elif current.close < prev.close < older.close:
                side, action = -1, "open_short"
            else:
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
                four_up.append((*prefix[:4], "entry",
                                *(bar.close / 100 for bar in reversed(bars[:5]))))
                continue
            add_signal(day, product, action, current, prev, older, current.low if side == 1 else current.high,
                       orders)

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
    return marks, pd.DataFrame(opening, columns=OPEN_COLUMNS), cycles, len(orders), len(reversals), branches, delayed, risk, touch_events, lock_events, locked, carry_days, unavailable_days, wait_days


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--certificate", type=Path)
    args = parser.parse_args()
    baseline=line/"outputs/stage054_s21_gold_touch_halfyear_20261104"
    weekly=line/"outputs/stage052_s21_margin_gate_20261104"
    result=line/"outputs/stage055_s21_all_touch_halfyear_20261104"
    cert=load_json(result/"receipt.json")
    prior=load_json(baseline/"receipt.json")
    manifests={p.name:check_manifest(p) for p in (result,baseline,weekly)}
    assert cert["stage054_manifest_sha256"]==sha(baseline/"SHA256SUMS")
    assert cert["stage054_audit_sha256"]==sha(line/"reviews/stage054_gold_touch_audit.json")
    assert cert["stage054_entrypoint_sha256"]==sha(line/"tools/stage054_s21_gold_touch_halfyear.py")==prior["entrypoint_sha256"]
    assert cert["stage052_entrypoint_sha256"]==sha(line/"tools/stage052_s21_margin_gate.py")==prior["stage052_entrypoint_sha256"]
    assert cert["entrypoint_sha256"]==sha(line/"tools/stage055_s21_all_touch_halfyear.py")
    assert cert["engine_sha256"]==sha(line/"tools/run_weekly_portfolio.py")==prior["engine_sha256"]
    assert cert["design_sha256"]==sha(line/"stages/20261105_1237_stage055_all_touch_design.md")
    for k in ("market_sha256","cutoff","capital","products","starts","gate","attempted_runs","completed_runs","unknown_runs"):
        assert cert[k]==prior[k],k
    pins=cert["market_sha256"] | load_json(baseline/STARTS[0]/"inputs.json")["source_sha256"]
    assert len(pins)==42 and all(sha(Path(p))==h for p,h in pins.items())
    assert cert["starts"]==STARTS and len(STARTS)==24 and cert["completed_runs"]==24 and cert["unknown_runs"]==0
    market=extend_raw_market(load_json(TAIL_CERT))
    weeks=completed_weeks(market[1],market[4])
    combined=table(result,"window_metrics").set_index("calendar_start",verify_integrity=True)
    controls=table(baseline,"window_metrics").set_index("calendar_start",verify_integrity=True)
    assert combined.index.tolist()==controls.index.tolist()==STARTS
    total=Counter()
    decisions=Counter()
    stop_counts=Counter()
    branch_counts=Counter()
    cases=[]
    windows={}
    outcomes={"gold_touch":Counter(),"weekly":Counter()}
    for start in STARTS:
        folder=result/start
        cfg=load_json(folder/"inputs.json")
        expected_cfg=load_json(baseline/start/"inputs.json")
        expected_cfg.pop("gold_stop_rule")
        expected_cfg["all_products_stop_rule"]=cert["all_products_stop_rule"]
        assert cfg==expected_cfg
        data=reconcile(folder,start,cfg,*market,*weeks)
        marks,opening,cycles,pending,reversals,branches,delayed,risk,touch,locks,locked,carry,unavailable,waiting=data
        assert not pending and not reversals and not locked
        assert not table(folder,"fills").reason.eq("weekly_stop").any()
        performance,counts,_=financial_metrics(folder,marks,opening,pending)
        stat,equal=verify_risk_table(folder,risk,opening)
        decisions.update(stat)
        total.update(counts)
        branch_counts.update(branches)
        ob=table(folder,"touch_stops")
        pd.testing.assert_frame_equal(pd.DataFrame(touch,columns=ob.columns),ob,
                                      check_dtype=False,check_exact=False,rtol=0,atol=1e-8)
        assert len(touch)==len(ob) and not ob.one_price.any()
        assert (ob.anchor_day.lt(ob.trigger_day) & ob.trigger_day.le(ob.date)).all()
        assert ob.trigger_day.lt(ob.date).equals(ob.reason.eq("touch_after_one_price"))
        for trigger in locks:
            emitted=[x for x in touch if (x["cycle"],x["epoch"],x["trigger_day"])==(trigger["cycle"],trigger["epoch"],trigger["trigger_day"])]
            assert len(emitted)==1 and emitted[0]["date"]>trigger["trigger_day"]
            cases.append(dict(window=start,**trigger,exit_day=emitted[0]["date"],exit_price=emitted[0]["price"]))
        reasons=Counter(ob.reason)
        stop_counts.update(reasons)
        stats=dict(stop_count=len(touch),open_gap_count=reasons["touch_open_gap"],
                   intraday_count=reasons["touch_intraday"],delayed_count=reasons["touch_after_one_price"],
                   locked_count=len(locks),missing_bars=len(unavailable),
                   blocked_total=sum(v for (k,_),v in stat.items() if k!="filled"),
                   nonpositive_equity_days=counts["nonpositive_days"],
                   minimum_equity=min(marks.equity.min(),opening.equity.min()))
        expected={f"all_touch_{k}":v for k,v in (performance|stats).items()}
        expected.update({k.replace("touch_","gold_touch_",1) if k.startswith("touch_") else k:v for k,v in controls.loc[start].items()})
        assert set(expected)==set(combined.columns),(set(expected)-set(combined.columns),set(combined.columns)-set(expected))
        for k,v in expected.items(): check_values(combined.at[start,k],v,(start,k))
        for arm in outcomes:
            for metric in ("return_pct","max_dd_pct","sharpe"):
                a,b=combined.at[start,"all_touch_"+metric],combined.at[start,arm+"_"+metric]
                outcomes[arm][metric+("_better" if a>b else "_worse" if a<b else "_tied")]+=1
        windows[start]=dict(equity=float(performance["equity"]),net_pnl=float(performance["net_pnl"]),
                           gold_touch_pnl_delta=float(performance["net_pnl"]-combined.at[start,"gold_touch_net_pnl"]),
                           weekly_pnl_delta=float(performance["net_pnl"]-combined.at[start,"weekly_net_pnl"]),
                           touch_stops=len(touch),locks=len(locks),pending_at_end=0,
                           anchor_carry_days=len(carry),missing_bars=len(unavailable),waiting_days=len(waiting))
        print(start,windows[start],"funding",len(risk),flush=True)
    audit=dict(
        schema="stage055_independent_all_products_touch_audit_v1",
        verdict="PASS_WITH_LIMITATIONS",
        audited_at=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        audit_method="Independent integer-cent all-products state machine, physical weekly anchors and frozen one-price exit locks. No production runner invocation.",
        audit_script_sha256=sha(Path(__file__)),
        audit_parent_script_sha256=sha(line/"reviews/stage054_gold_touch_audit.py"),
        result_manifest_sha256=sha(result/"SHA256SUMS"),
        parent_manifest_sha256=sha(baseline/"SHA256SUMS"),
        checked_manifests=manifests,input_hashes=len(pins),
        windows=dict(attempted=24,verified=len(windows),unknown=0),
        ledger_rows=dict(total),gold_and_other_touch_exits=dict(stop_counts),
        funding=dict(decisions=sum(decisions.values()),
                     approved=sum(v for (k,_),v in decisions.items() if k=="filled"),
                     denied=sum(v for (k,_),v in decisions.items() if k!="filled"),
                     by_status_and_role={f"{k}:{r}":v for (k,r),v in decisions.items()}),
        branch_counts=dict(branch_counts),
        comparisons={k:dict(v) for k,v in outcomes.items()},
        one_price_cases=cases,by_window=windows,
        limitations=[
            "Daily OHLC proxy does not establish exact intraday timing, stop market price jumps, queue priority or fills.",
            "Opening margin gate only; no intraday margin or broker liquidation model and commissions remain zero.",
            "Overlapping windows and after-the-fact choice of exit scope limit economic generalization.",
            "One-price outcomes use first admitted non-one-price daily opening proxy.",
        ],
    )
    print("TOTALS",total,"FUNDING",decisions,"STOPS",stop_counts,"OUTCOMES",outcomes,"BRANCHES",branch_counts,flush=True)
    if args.certificate:
        with args.certificate.open("x") as file:
            json.dump(audit,file,indent=2,ensure_ascii=False)
            file.write("\n")

if __name__=="__main__":
    main()

