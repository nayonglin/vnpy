"""Replay Stage024's fixed pools with the approved five-session delivery guard."""
import argparse
from pathlib import Path

from run_weekly_portfolio import run, sha
from stage024_pool44 import load_expanded

DESIGN = Path(__file__).resolve().parents[1] / "stages/20261104_1418_stage025_delivery_guard.md"


def load(approved, control):
    *market, hashes = load_expanded(approved, control)
    return *market, {**hashes, DESIGN: sha(DESIGN), Path(__file__): sha(Path(__file__))}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pool", choices=("19", "44"))
    parser.add_argument("approved", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    run(args.output, week_body_filter=True, reverse_after_stop=True, block_four_up=True,
        delivery_guard=True, market_loader=lambda: load(args.approved.resolve(), args.pool == "19"))
