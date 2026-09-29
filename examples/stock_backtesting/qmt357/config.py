"""Frozen migration defaults, independent from all futures profiles."""
from dataclasses import dataclass, asdict
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION = 'stock_qmt357_v1_close_to_next_open'
INDEX_SYMBOL = '000300.SSE'


@dataclass(frozen=True)
class BacktestSettings:
    capital: float = 300_000.
    max_positions: int = 10
    position_size: float = .5
    day_position_size: float = .30
    cash_buffer: float = .05
    stop_loss_pct: float = .02
    stop_profit_pct: float = .12
    commission_rate: float = .0003
    minimum_commission: float = 5.
    stamp_duty_rate: float = .001
    slippage_per_share: float = .01
    annual_days: int = 252

    def __post_init__(self):
        if not all(math.isfinite(float(v)) for v in asdict(self).values()):
            raise ValueError('Settings must be finite')
        if self.capital <= 0 or self.max_positions < 1 or self.annual_days < 1:
            raise ValueError('Capital, position count and annual_days must be positive')
        if not (0 < self.position_size <= 1 and 0 < self.day_position_size <= 1):
            raise ValueError('Position fractions must be in (0, 1]')
        if not 0 <= self.cash_buffer < 1 or not 0 < self.stop_loss_pct < 1 or self.stop_profit_pct <= 0:
            raise ValueError('Invalid cash buffer / exit thresholds')
        if min(self.commission_rate, self.minimum_commission, self.stamp_duty_rate, self.slippage_per_share) < 0:
            raise ValueError('Costs must be non-negative')


MIGRATION_NOTES = [
    'Signals retain the 60-bar QMT window, simple rolling RSI and flexible 2-of-3 rule.',
    'Daily close decision -> next observed market session open; not a 14:50 replay.',
    'Raw prices / cash shares for fills; point-in-time adjusted prices for signals.',
    '30% daily opening budget enforced, original repeated cash debits removed.',
    '100-share buys, T+1 sells, no leverage/shorting, absent bars never matched.',
    'Open at upper/lower limit is conservatively unfillable for buy/sell respectively.',
    'Fees are explicit fixed research assumptions, not a historical broker-fee reconstruction.',
    'Source universe/ST declarations are not independent point-in-time verification.',
    'Corporate actions while held require cash_dividend/split_ratio; unexplained factor changes fail.',
]
