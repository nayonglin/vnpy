"""Effective daily_trade parameters from QMT commit 4ac255e (not init defaults)."""
from dataclasses import dataclass
from pathlib import Path

from examples.stock_backtesting.qmt357.config import BacktestSettings as BaseSettings
from examples.stock_backtesting.qmt357.config import INDEX_SYMBOL, MIGRATION_NOTES as BASE_NOTES

ROOT = Path(__file__).resolve().parent
BASE_ROOT = ROOT.parent / 'qmt357'
VERSION = 'stock_qmt357_commit4ac255e_tiered_close_to_next_open_v1'
COMMIT = '4ac255ece55671bb74962f23b5d7fae22fa377e7'


@dataclass(frozen=True)
class BacktestSettings(BaseSettings):
    max_positions: int = 3
    position_size: float = .32
    day_position_size: float = .90
    stop_loss_pct: float = .02
    stop_profit_pct: float = .45


TRAILING_CONTRACT = {
    'enabled': True,
    'observed_peak': 'close_not_intraday_high',
    'initial_peak': 'actual_fill_price',
    'current_price_gate': 'close_strictly_above_buy_price',
    'peak_profit_to_locked_profit': [[.40, .15], [.30, .10], [.20, .06], [.10, .03]],
    'positive_profit_below_first_tier': 'raise_stop_to_buy_price',
    'source_unused_trailing_stop_flag': False,
    'special_limit_protection': 'source_order_preserved_can_lower_stored_stop',
    'corporate_actions': 'peak_adjusted_as_buy_price_by_explicit_cash_and_split',
}
MIGRATION_NOTES = [note.replace('30% daily', '90% daily') for note in BASE_NOTES] + [
    'Commit source is 震荡股高卖低买策略.py; its 357.py is unchanged from the old source.',
    'Tiered stops are active despite the unused False init flag in QMT source.',
    'Peak uses observed closes, not bar highs; stop signals still fill next open.',
    'Positive price profit is not net-of-fees breakeven; gaps can exceed stop thresholds.',
]
