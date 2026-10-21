"""Actual-fill fixed-initial-risk accounting; not signal/fill generation or a label.

Integer lots, one direction and one held contract at a time. Explicit rollover
close/open only. Decimal arithmetic; missing costs and marks stay unknown.
"""
from dataclasses import dataclass, asdict
from datetime import date
from decimal import Decimal, InvalidOperation


def dec(value, *, zero=False):
    if isinstance(value, bool):
        raise ValueError('boolean_is_not_number')
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError('invalid_number') from exc
    if not number.is_finite() or number < 0 or (not zero and number == 0):
        raise ValueError('nonfinite_or_invalid_sign')
    return number


@dataclass(frozen=True)
class Economics:
    multiplier: float
    tick: float
    open_per_lot: float | None = None
    open_rate: float | None = None
    close_per_lot: float | None = None
    close_rate: float | None = None
    close_today_per_lot: float | None = None
    close_today_rate: float | None = None
    historical_validated: bool = False


@dataclass(frozen=True)
class Fill:
    kind: str
    contract: str
    trading_day: str
    price: float
    qty: int
    economics: Economics
    extra_slippage_price: float | None = None
    rollover: bool = False


class FixedRiskLedger:
    def __init__(self, direction, initial_stop):
        if direction not in ('long', 'short'):
            raise ValueError('invalid_direction')
        self.sign = 1 if direction == 'long' else -1
        self.initial_stop = dec(initial_stop)
        self.risk_currency = None
        self.contract = None
        self.last_contract = None
        self.entry_price = self.multiplier = self.tick = None
        self.entry_day = None
        self.remaining = 0
        self.realized = Decimal(0)
        self.commission_known = self.slippage_known = Decimal(0)
        self.fees_complete = self.slippage_complete = True
        self.all_validated = True
        self.pending_roll = False
        self.last_day = None
        self.tape = []

    def apply(self, fill):
        """Validate entire event before mutation. Price must be actual external fill."""
        if fill.kind not in ('open', 'close') or not isinstance(fill.contract, str) or not fill.contract.strip():
            raise ValueError('invalid_fill_identity')
        d = date.fromisoformat(fill.trading_day)
        if d.isoformat() != fill.trading_day or self.last_day is not None and d < self.last_day:
            raise ValueError('out_of_order_trading_day')
        price, qty = dec(fill.price), dec(fill.qty)
        if qty != qty.to_integral_value():
            raise ValueError('integer_lots_required')
        qty = int(qty)
        economics = fill.economics
        multiplier, tick = dec(economics.multiplier), dec(economics.tick)
        if not isinstance(economics.historical_validated, bool) or not isinstance(fill.rollover, bool):
            raise ValueError('explicit_boolean_required')
        if price % tick:
            raise ValueError('fill_not_on_declared_tick_grid')
        for key, value in asdict(economics).items():
            if key not in ('multiplier', 'tick', 'historical_validated') and value is not None:
                dec(value, zero=True)
        extra = None if fill.extra_slippage_price is None else dec(fill.extra_slippage_price, zero=True) * multiplier * qty
        first = self.risk_currency is None
        if fill.kind == 'open':
            if self.remaining:
                raise ValueError('no_pyramiding_or_overlap')
            if first:
                if fill.rollover:
                    raise ValueError('first_entry_cannot_be_rollover')
                risk = self.sign * (price-self.initial_stop) * multiplier * qty
                if risk <= 0:
                    raise ValueError('wrong_side_initial_risk')
            elif not (self.pending_roll and fill.rollover and fill.contract != self.last_contract):
                raise ValueError('reentry_requires_explicit_new_contract_roll')
            prefix = 'open'
        else:
            if not self.remaining or fill.contract != self.contract or qty > self.remaining:
                raise ValueError('unmatched_or_oversized_close')
            if multiplier != self.multiplier or tick != self.tick:
                raise ValueError('held_contract_economics_changed')
            if fill.rollover and qty != self.remaining:
                raise ValueError('rollover_must_flatten_old_contract')
            prefix = 'close_today' if fill.trading_day == self.entry_day else 'close'
        per_lot, rate = getattr(economics, prefix+'_per_lot'), getattr(economics, prefix+'_rate')
        fee = None if per_lot is None or rate is None else (
            dec(per_lot, zero=True) * qty + price * multiplier * qty * dec(rate, zero=True))

        # All event checks succeeded. Commit the economic transition.
        if fill.kind == 'open':
            if first:
                self.risk_currency = risk
            self.contract = self.last_contract = fill.contract
            self.entry_price, self.multiplier, self.tick = price, multiplier, tick
            self.entry_day = fill.trading_day
            self.remaining = qty
            self.pending_roll = False
            gross_delta = Decimal(0)
        else:
            gross_delta = self.sign * (price-self.entry_price) * self.multiplier * qty
            self.realized += gross_delta
            self.remaining -= qty
            if not self.remaining:
                self.contract = None
                self.pending_roll = fill.rollover
        self.fees_complete = self.fees_complete and fee is not None
        self.slippage_complete = self.slippage_complete and extra is not None
        if fee is not None:
            self.commission_known += fee
        if extra is not None:
            self.slippage_known += extra
        self.all_validated = self.all_validated and economics.historical_validated
        self.last_day = d
        self.tape.append(dict(**asdict(fill), fee_category=prefix,
                              commission=None if fee is None else str(fee),
                              extra_slippage=None if extra is None else str(extra),
                              realized_gross_delta=str(gross_delta)))

    def mark(self, prices):
        if self.risk_currency is None:
            raise ValueError('no_actual_initial_entry')
        unrealized = Decimal(0)
        if self.remaining:
            value = prices.get(self.contract)
            unrealized = None if value is None else (
                self.sign * (dec(value)-self.entry_price) * self.multiplier * self.remaining)
        gross = None if unrealized is None else self.realized + unrealized
        commission = self.commission_known if self.fees_complete else None
        slippage = self.slippage_known if self.slippage_complete else None
        net = None if gross is None or commission is None or slippage is None else gross-commission-slippage
        status = ('economic_unknown' if net is None else 'computed_with_declared_validated_economics'
                  if self.all_validated else 'conditional_economics')
        def number(x):return None if x is None else float(x)
        return dict(status=status, risk_currency=number(self.risk_currency),
                    realized_gross=number(self.realized), unrealized_gross=number(unrealized),
                    commission=number(commission), extra_slippage=number(slippage),
                    gross=number(gross), net=number(net), gross_r=number(None if gross is None else gross/self.risk_currency),
                    net_r=number(None if net is None else net/self.risk_currency),
                    remaining_qty=self.remaining, contract=self.contract, pending_roll=self.pending_roll,
                    fills=len(self.tape), complete_strategy=False, net_60d_training_label=False,
                    historical_economics_only_declared=self.all_validated)
