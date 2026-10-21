"""Finite synthetic C2 entry-session ledger, NOT a complete strategy or label source.

One explicit position, <=5 sessions, <=256 supplied Cartesian scenarios. Only C2
on entry session and subsequent MTM; no ordinary exits, fees, rollover or retry.
Bar positions are abstract ordered minute slots, not exchange time certification.
"""
from dataclasses import dataclass
from datetime import date
from itertools import product
import hashlib
import importlib.util
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
KERNEL = ROOT / 'examples/portfolio_backtesting/qmt_roll_intraday_execution.py'
spec = importlib.util.spec_from_file_location('stage018_bound_execution', KERNEL)
execution = importlib.util.module_from_spec(spec)
spec.loader.exec_module(execution)
KERNEL_SHA256 = hashlib.sha256(KERNEL.read_bytes()).hexdigest()


@dataclass(frozen=True)
class Bar:
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class Session:
    day: str
    alternatives: tuple[tuple[Bar, ...], ...] | None


@dataclass(frozen=True)
class Position:
    direction: str
    entry: float
    stop: float
    guard_tick: float
    fill_tick: float


def _number(value):
    if isinstance(value, bool):
        raise ValueError('boolean_price')
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError('invalid_positive_price_or_tick')
    return value


def _validate(position, sessions):
    if position.direction not in ('long', 'short'):
        raise ValueError('invalid_direction')
    e, stop, guard, tick = [_number(x) for x in
                            (position.entry, position.stop, position.guard_tick, position.fill_tick)]
    sign = 1 if position.direction == 'long' else -1
    risk = sign * (e - stop)
    if risk <= 0:
        raise ValueError('invalid_signed_initial_risk')
    if not 1 <= len(sessions) <= 5:
        raise ValueError('session_count_out_of_scope')
    previous = None
    count = 1
    for i, session in enumerate(sessions):
        d = date.fromisoformat(session.day)
        if d.isoformat() != session.day or previous is not None and d <= previous:
            raise ValueError('session_order_not_strict')
        previous = d
        alternatives = session.alternatives
        if alternatives is None:
            continue
        if not alternatives or any(not path for path in alternatives):
            raise ValueError('empty_supplied_path')
        count *= len(alternatives)
        if count > 256:
            raise ValueError('scenario_budget_exceeded_no_truncation')
        aggregates = []
        for path in alternatives:
            for bar in path:
                o, h, l, c = [_number(x) for x in (bar.open, bar.high, bar.low, bar.close)]
                if l > min(o, c) or h < max(o, c):
                    raise ValueError('invalid_OHLC')
            aggregate = (float(path[0].open), max(float(x.high) for x in path),
                         min(float(x.low) for x in path), float(path[-1].close))
            aggregates.append(aggregate)
            if i == 0 and not math.isclose(aggregate[0], e, rel_tol=0, abs_tol=1e-9):
                raise ValueError('entry_first_open_mismatch')
        if any(len(path) != len(alternatives[0]) for path in alternatives):
            raise ValueError('alternative_slot_grid_mismatch')
        if any(any(not math.isclose(a, b, rel_tol=0, abs_tol=1e-9)
                       for a, b in zip(agg, aggregates[0])) for agg in aggregates):
            raise ValueError('alternative_daily_OHLC_mismatch')
    return e, sign, risk, max(guard, 1e-9), tick


def enumerate_paths(position, sessions):
    """Return every supplied scenario, with no merging/pruning or reality claim."""
    e, sign, risk, guard, tick = _validate(position, sessions)
    rows = []
    choices = [range(len(s.alternatives)) if s.alternatives is not None else (None,)
               for s in sessions]
    for path_id, selected in enumerate(product(*choices)):
        opened, realized = True, 0.0
        status, c2 = 'known', 'pending_entry_session'
        trace = []
        for i, (session, choice) in enumerate(zip(sessions, selected)):
            path = None if choice is None else session.alternatives[choice]
            decision, fill = 'hold_mark', None
            unrealized, total = None, None
            if status != 'known':
                decision = 'prior_unknown_preserved'
            elif not opened:
                unrealized, total = 0.0, realized
                decision = 'permanently_flat_no_retry'
            elif path is None:
                status, decision = 'path_unknown', 'missing_path_while_open'
                if i == 0:
                    opened, realized, c2 = None, None, 'entry_path_unknown'
            else:
                if i == 0:
                    if risk < guard:
                        c2, decision = 'guard_inactive', 'risk_below_configured_tick'
                    else:
                        frame = pd.DataFrame([vars(bar) for bar in path])
                        index, note = execution.first_stop(frame, e-sign*risk, e+sign*risk,
                                                           long=sign == 1)
                        decision = note
                        if index >= 0:
                            try:
                                fill, fill_note = execution.stop_fill(frame.iloc[index], e-sign*risk,
                                                                     tick, buy=sign == -1)
                                realized = sign * (fill-e) / risk
                                opened, c2 = False, 'stopped'
                                decision += ':' + fill_note
                            except ValueError as exc:
                                opened, realized = None, None
                                status, c2 = 'execution_unknown', 'fill_unreachable'
                                decision = str(exc)
                        else:
                            c2 = 'entry_session_expired' if note == 'no_trigger' else 'confirmed'
                if status == 'known':
                    unrealized = sign * (float(path[-1].close)-e) / risk if opened else 0.0
                    total = realized + unrealized
            trace.append(dict(day=session.day, choice=choice, path_missing=path is None,
                              status=status, c2_state=c2, position_open=opened,
                              realized_r=realized, unrealized_r=unrealized, total_r=total,
                              decision=decision, reference_fill=fill))
        last = trace[-1]
        rows.append(dict(path_id=path_id, path_choices=list(selected), risk=risk,
                         status=last['status'], c2_state=last['c2_state'], position_open=last['position_open'],
                         realized_r=last['realized_r'], unrealized_r=last['unrealized_r'],
                         total_r=last['total_r'], trace=trace, synthetic_only=True,
                         complete_strategy=False, net_return_label=False,
                         universe='finite_supplied_scenarios_not_all_reality_paths',
                         kernel_sha256=KERNEL_SHA256))
    return rows
