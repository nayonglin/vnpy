"""Complete the frozen 2015–2026 half-year grid with the missing July 2015 pair."""
import argparse
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import stage040_s19_without_gold as stage040

PRIOR = stage040.LINE / "outputs/stage040_s19_without_gold_20261104"
PRIOR_SHA = "411e7c894aaa138441616610cd7074765d8b6140c8996a6b78adad49821b1bb8"
DESIGN = stage040.LINE / "stages/20261104_1818_stage041_complete_halfyear_design.md"
START = "2015-07-01"


def run(output):
    stage040.verify_manifest(PRIOR, PRIOR_SHA)
    prior_receipt = json.loads((PRIOR / "receipt.json").read_text())
    pins = prior_receipt["market_sha256"] | prior_receipt["source_sha256"]
    if any(stage040.portfolio.sha(Path(path)) != digest for path, digest in pins.items()):
        raise ValueError("frozen inputs changed")
    market = stage040.extend(stage040.load(stage040.MARKET, control=True), stage040.TAIL)
    if {str(path): digest for path, digest in market[-1].items()} != prior_receipt["market_sha256"]:
        raise ValueError("loaded market differs from Stage040")
    products = [product for product in market[0] if product != stage040.GOLD]
    if products != prior_receipt["products"]:
        raise ValueError("unexpected product pool")

    control = output / START / "s19"
    with patch.object(stage040.portfolio, "INITIAL", stage040.CAPITAL), patch.object(
        stage040.portfolio, "START", START
    ), redirect_stdout(StringIO()):
        stage040.portfolio.run(
            control, week_body_filter=True, reverse_after_stop=True, block_four_up=True,
            delivery_guard=True, market_loader=lambda: market,
        )

    previous_control = json.loads((stage040.PARENT / "inputs.json").read_text())
    if json.loads((control / "inputs.json").read_text()) != {**previous_control, "start": START}:
        raise ValueError("control config differs beyond start date")
    daily = pd.read_csv(control / "daily.csv")
    fills = pd.read_csv(control / "fills.csv")
    if fills.date.min() <= daily.date.iat[0] or fills.signal_day.min() < daily.date.iat[0]:
        raise ValueError("control inherited an order or trade before its start")
    opening = stage040.reconstruct_opening(daily, fills, market)
    opening.to_csv(control / "opening_funding.csv", index=False)
    added = stage040.replay(output / START / "no_gold", START, (products, *market[1:]), control)
    prior = pd.read_csv(PRIOR / "window_metrics.csv", keep_default_na=False)
    windows = pd.concat([prior, pd.DataFrame([added])], ignore_index=True).sort_values("calendar_start")
    expected = tuple(f"{year}-{month}-01" for year in range(2015, 2027) for month in ("01", "07"))
    if tuple(windows.calendar_start) != expected:
        raise ValueError("incomplete half-year start grid")
    windows.to_csv(output / "window_metrics.csv", index=False)
    receipt = dict(
        stage040_manifest_sha256=PRIOR_SHA, cutoff=stage040.TARGET, capital=stage040.CAPITAL,
        starts=expected, newly_replayed=[START], reused=list(prior.calendar_start),
        completed_pairs=len(windows), unknown_pairs=0,
        design_sha256=stage040.portfolio.sha(DESIGN),
        entrypoint_sha256=stage040.portfolio.sha(Path(__file__)),
    )
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    stage040.write_checksums(output, (path for path in output.rglob("*") if path.is_file()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
