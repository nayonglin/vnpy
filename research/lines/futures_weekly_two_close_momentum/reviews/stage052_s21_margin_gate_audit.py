"""Independently reconstruct the S21 margin-gated state machine and funding decisions."""
from bisect import bisect_left
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path

import pandas as pd

from stage040_s19_without_gold_audit import CAPITAL, DAY_COLUMNS, LINE, OPEN_COLUMNS, TARGET, cents, check_manifest, load_json, near, read_csv, sha
from stage043_s19_daily_one_audit import Holding, Signal
from stage044_s19_daily_halfyear_audit import STARTS, financial_metrics
from stage045_s19_weekly_shadow_filter_audit import completed_weeks
from stage046_s44_individual_2022_audit import table
from stage048_s26_full_audit import TAIL_CERT, extend_raw_market
from stage049_s26_halfyear_audit import check_values
from stage051_s21_halfyear_audit import RESULT as STAGE051

RESULT = LINE / "outputs/stage052_s21_margin_gate_20261104"
PRIOR_CERT = LINE / "reviews/stage051_s21_halfyear_audit.json"


def reconcile(folder, start, config, calendar, guard_calendar, mains, symbols, by_epoch, settings, weeks, week_index, weekly_bar):
    products = config["products"]
    dates = [day for day in calendar if day >= start]
    assert dates[0] >= start and dates[-1] == TARGET
    positions, orders, reversals = {}, {}, {}
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

    def fill(day, product, bar, side, number, reason, decision, stop):
        nonlocal cash, slip_total, fee_total
        size = settings["sizes"][bar.symbol]
        slip = cents(size * settings["slippages"][bar.symbol])
        fee = cents(size * (bar.op / 100) * settings["rates"][bar.symbol])
        flow = -side * size * bar.op - slip - fee
        cash += flow
        slip_total += slip
        fee_total += fee
        cycles[number]["flow"] += flow
        fills.append((day, product, bar.symbol, bar.epoch, number, side, 1, bar.op / 100, size, slip / 100,
                      fee / 100, reason, decision, stop / 100 if stop is not None else "", bar.high == bar.low))
        open_sizes[day] += 1
        snapshot(day, open_sizes[day], product, reason)

    def close_position(day, product, bar, reason, decision, stop=None):
        held = positions.pop(product)
        fill(day, product, bar, -held.side, held.number, reason, decision, stop)
        if reason != "roll_close":
            cycles[held.number]["exit"] = day

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
    return marks, pd.DataFrame(opening, columns=OPEN_COLUMNS), cycles, len(orders), len(reversals), branches, delayed, risk





OPEN_REASONS = {"entry", "roll_open"}
GATE = "available_equity_ge_one_lot_margin_and_entry_cost"


def old_opening_statistics(folder, settings):
    opening = table(folder, "opening_funding")
    fills = table(folder, "fills").copy()
    fills["fill_sequence"] = fills.groupby("date").cumcount() + 1
    fills.set_index(["date", "fill_sequence"], verify_integrity=True, inplace=True)
    opening["prior_free"] = opening.groupby("date").free_equity.shift()
    opening["prior_margin"] = opening.groupby("date").margin.shift()
    opening["prior_equity"] = opening.groupby("date").equity.shift()
    selected = opening.loc[opening.reason.isin(OPEN_REASONS)]
    assert len(selected) == fills.reason.isin(OPEN_REASONS).sum()
    before_negative, denied, previously_nonnegative = Counter(), Counter(), Counter()
    unique = set()
    for item in selected.itertuples(index=False):
        fill = fills.loc[(item.date, item.fill_sequence)]
        assert fill["product"] == item.product and fill.reason == item.reason and fill.volume == 1
        notional = Decimal(str(fill.price)) * int(fill["size"])
        margin = notional * Decimal(str(settings["margin_ratios"][fill.contract]))
        cost = Decimal(str(fill.slippage)) + Decimal(str(fill.commission))
        free = Decimal(str(item.prior_free))
        after = Decimal(str(item.free_equity))
        near(float(free - margin - cost), float(after))
        near(item.margin - item.prior_margin, float(margin))
        near(item.prior_equity - item.equity, float(cost))
        unaffordable = free < margin + cost
        assert unaffordable == (after < 0)
        if free < 0:
            before_negative[item.reason] += 1
        if unaffordable:
            denied[item.reason] += 1
            unique.add((item.date, item.product, item.reason, fill.epoch, int(fill.side)))
            if free >= 0:
                previously_nonnegative[item.reason] += 1
    return before_negative, denied, previously_nonnegative, unique


def verify_risk_table(folder, risk, opening):
    observed = table(folder, "risk_sizing")
    expected = []
    fields = ["date", "product", "contract", "epoch", "kind", "signal_day", "side", "price", "stop", "equity",
              "margin", "free_cash", "risk_budget", "risk_per_lot", "margin_per_lot", "entry_cost_per_lot",
              "requested_lots", "affordable_lots", "executed_lots", "status"]
    assert observed.columns.tolist() == fields
    statuses, equal = Counter(), Counter()
    admitted_surplus = []
    for decision in risk:
        role = "fixed_entry" if decision["role"] == "entry" else decision["role"]
        data = {**decision, "kind": role, "risk_budget": "", "risk_per_lot": ""}
        expected.append([data[field] for field in fields])
        statuses[(decision["status"], role)] += 1
        if decision["surplus"] == 0:
            equal[role] += 1
            assert decision["executed_lots"] == 1
        if decision["executed_lots"]:
            admitted_surplus.append(decision["surplus"])
    expected = pd.DataFrame(expected, columns=fields)
    for key in ("stop", "risk_budget", "risk_per_lot"):
        expected[key] = pd.to_numeric(expected[key].mask(expected[key].eq("")))
        observed[key] = pd.to_numeric(observed[key].mask(observed[key].eq("")))
    pd.testing.assert_frame_equal(expected, observed, check_dtype=False, check_exact=False, atol=1e-8, rtol=0)
    new_marks = opening.loc[opening.reason.isin(OPEN_REASONS)].free_equity.to_list()
    near(new_marks, admitted_surplus)
    assert (opening.loc[opening.reason.isin(OPEN_REASONS), "free_equity"].round(8) >= 0).all()
    assert len(new_marks) == sum(count for (status, _), count in statuses.items() if status == "filled")
    assert opening.reason.eq("roll_funding_exit").sum() == statuses["margin_below_one_lot", "roll"]
    return statuses, equal


def audit():
    manifests = {folder.name: check_manifest(folder) for folder in (RESULT, STAGE051)}
    receipt = load_json(RESULT / "receipt.json")
    prior_receipt = load_json(STAGE051 / "receipt.json")
    prior = load_json(PRIOR_CERT)
    assert prior["verdict"] == "PASS_WITH_LIMITATIONS"
    assert receipt["stage051_manifest_sha256"] == prior["manifest_sha256"] == sha(STAGE051 / "SHA256SUMS")
    assert receipt["stage051_audit_sha256"] == sha(PRIOR_CERT)
    assert receipt["entrypoint_sha256"] == sha(LINE / "tools/stage052_s21_margin_gate.py")
    design = list((LINE / "stages").glob("*_stage052_*design.md"))
    assert len(design) == 1 and receipt["design_sha256"] == sha(design[0])
    assert receipt["engine_sha256"] == sha(LINE / "tools/run_weekly_portfolio.py")
    assert (receipt["starts"], receipt["attempted_runs"], receipt["completed_runs"], receipt["unknown_runs"]) == (STARTS, 24, 24, 0)
    assert (receipt["cutoff"], receipt["capital"], receipt["gate"]) == (TARGET, CAPITAL, GATE)
    assert receipt["products"] == prior_receipt["products"] and len(receipt["products"]) == 21
    assert receipt["market_sha256"] == prior_receipt["market_sha256"]
    prior_config = load_json(STAGE051 / STARTS[0] / "inputs.json")
    pins = prior_config["inputs_sha256"] | prior_config["source_sha256"]
    assert all(sha(Path(name)) == digest for name, digest in pins.items())
    assert {path.name for path in RESULT.iterdir() if path.is_dir()} == set(STARTS)
    control = table(STAGE051, "window_metrics").set_index("calendar_start", verify_integrity=True)
    combined = table(RESULT, "window_metrics").set_index("calendar_start", verify_integrity=True)
    assert combined.index.tolist() == control.index.tolist() == STARTS
    market = extend_raw_market(load_json(TAIL_CERT))
    settings = market[-1]
    weeks = completed_weeks(market[1], market[4])
    counts_total, decisions_total, equality_total = Counter(), Counter(), Counter()
    old_before, old_after, old_positive_but_short = Counter(), Counter(), Counter()
    old_unique = set()
    unchanged, windows = [], []
    for start in STARTS:
        folder, old = RESULT / start, STAGE051 / start
        baseline = control.loc[start]
        config = load_json(folder / "inputs.json")
        assert config == {**prior_config, "start": start, "fixed_one_margin_gate": GATE}
        assert load_json(old / "inputs.json") == {**prior_config, "start": start}
        before, after, positive_but_short, unique = old_opening_statistics(old, settings)
        old_before.update(before)
        old_after.update(after)
        old_positive_but_short.update(positive_but_short)
        old_unique.update(unique)
        marks, opening, cycles, pending, conditional, branches, delayed, risk = reconcile(
            folder, start, config, *market, *weeks)
        performance, counts, zero_close = financial_metrics(folder, marks, opening, pending)
        statuses, equal = verify_risk_table(folder, risk, opening)
        counts_total.update(counts)
        decisions_total.update(statuses)
        equality_total.update(equal)
        assert not pending and not conditional
        day = table(folder, "daily")
        assert day.date.iat[-1] == TARGET and day.date.equals(table(old, "daily").date)
        assert (day.iloc[0][["equity", "cash", "positions", "margin"]] == [CAPITAL, CAPITAL, 0, 0]).all()
        denied = {role: statuses["margin_below_one_lot", role] for role in ("fixed_entry", "reversal", "roll")}
        if sum(denied.values()) == 0:
            for name in ("daily.csv", "fills.csv", "cycles.csv", "signals.csv", "terminal.json", "opening_funding.csv"):
                assert (folder / name).read_bytes() == (old / name).read_bytes(), (start, name)
            unchanged.append(start)
        assert (sum(denied.values()) > 0) == bool(sum(after.values()))
        minimum_equity = min(marks.equity.min(), opening.equity.min())
        row = combined.loc[start]
        expected = {key: value for key, value in baseline.items() if key.startswith("s21_")}
        expected.update(first_session=day.date.iat[0], last_session=TARGET, days=len(day))
        expected.update({f"gated_{key}": value for key, value in performance.items()})
        expected.update(gated_nonpositive_equity_days=counts["nonpositive_days"], gated_minimum_equity=minimum_equity)
        expected.update(
            old_open_fills_with_negative_free_before=sum(before.values()),
            old_open_fills_with_negative_free_after=sum(after.values()),
            blocked_total=sum(denied.values()), blocked_entry=denied["fixed_entry"],
            blocked_reversal=denied["reversal"], blocked_roll=denied["roll"],
        )
        assert set(row.index) == set(expected), (start, set(row.index) ^ set(expected))
        for key, value in expected.items():
            check_values(row[key], value, (start, key))
        close_free = (marks.equity - marks.margin).round(8)
        open_free = opening.free_equity.round(8)
        worst_open = opening.loc[open_free.idxmin()].to_dict()
        worst_close = day.loc[close_free.idxmin(), ["date", "equity", "margin", "positions"]].to_dict()
        worst_open["free_equity"] = float(open_free.min())
        worst_close.update(free_equity=float(close_free.min()), reason="close_mark")
        worst = min((worst_open, worst_close), key=lambda item: item["free_equity"])
        for key in ("equity", "margin"):
            worst[key] = round(float(worst[key]), 8)
        windows.append(dict(
            start=start, s21_equity=float(baseline.s21_equity), gated_equity=float(performance["equity"]),
            s21_deficit_days=int(baseline.s21_deficit_days), gated_deficit_days=performance["deficit_days"],
            gated_nonpositive_days=counts["nonpositive_days"], gated_zero_equity_close_dates=zero_close,
            gated_minimum_equity=float(minimum_equity), gated_worst=worst, old_already_negative=dict(before),
            old_unaffordable_fills=dict(after), denied=denied,
        ))
        print(start, "equity", baseline.s21_equity, performance["equity"], "gap days", baseline.s21_deficit_days,
              performance["deficit_days"], "denied", denied, flush=True)

    verdict = dict(
        verdict="PASS_WITH_LIMITATIONS", attempted=24, completed=len(windows), unknown=0,
        manifest_entries=manifests, manifest_sha256=sha(RESULT / "SHA256SUMS"), pinned_inputs=len(pins),
        checked_rows=dict(counts_total), no_rejection_exact_ledger_windows=unchanged,
        checked_gate_decisions={status: {kind: decisions_total[status, kind] for kind in ("fixed_entry", "reversal", "roll")}
                                for status in ("filled", "margin_below_one_lot")},
        exact_funding_equalities=dict(equality_total), old_before_already_negative=dict(old_before),
        old_unaffordable_open_fills=dict(old_after), old_nonnegative_but_below_requirement=dict(old_positive_but_short),
        old_unaffordable_unique_date_product_reason_epoch_side=len(old_unique),
        funding_deficit_windows=dict(s21=sum(row["s21_deficit_days"] > 0 for row in windows),
                                     gated=sum(row["gated_deficit_days"] > 0 for row in windows)),
        gated_nonpositive_equity_windows=sum(row["gated_nonpositive_days"] > 0 for row in windows),
        windows=windows,
        limitations=[
            "Gate applies at each ordinary entry, conditional reversal entry and roll open; exits remain allowed.",
            "Static margin and daily opening prices, with last available close when an existing position lacks an opening price.",
            "Funding deficits can arise on existing holdings after price changes; no forced liquidation is modeled.",
            "Zero commissions and opening prints without a queue model.",
            "Overlapping windows reuse historical events.",
        ],
    )
    Path(__file__).with_suffix(".json").write_text(json.dumps(verdict, indent=2, allow_nan=False) + "\n")
    print({key: value for key, value in verdict.items() if key != "windows"}, flush=True)


if __name__ == "__main__":
    audit()
