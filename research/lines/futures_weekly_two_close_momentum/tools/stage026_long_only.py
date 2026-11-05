"""Replay the original S19 and the guarded S44 with short entries disabled."""
import argparse
from pathlib import Path

from run_weekly_portfolio import run
from stage025_delivery_guard import load

LINE = Path(__file__).resolve().parents[1]
MARKET = LINE / "outputs/stage024_market/approved_v1"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pool", choices=("19", "44"))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    guarded = args.pool == "44"

    run(args.output, week_body_filter=True, reverse_after_stop=True, block_four_up=True,
        long_only=True, delivery_guard=guarded,
        market_loader=(lambda: load(MARKET, control=False)) if guarded else None)
