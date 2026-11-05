"""Replay S19 with the existing 0.5% available-cash sizing rule."""
import argparse
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path

import pandas as pd

import run_weekly_portfolio as portfolio
from run_stage021_multicycle import write_checksums
from stage033_s19_annual_starts import LINE, MARKET, TARGET, extend, load

PARENT = LINE / "outputs/stage033_s19_annual_starts_20261104"
PARENT_SHA = "db8dc6230079ae1972e5011fed9c1607e5597cdcf4bedf0a61275611766f8fba"
TAIL = LINE / "outputs/stage033_s19_data/attempt002"
DESIGN = LINE / "stages/20261104_1718_stage035_s19_half_pct_design.md"
PARENT_AUDIT = LINE / "reviews/stage033_s19_annual_starts_audit.json"
PARENT_AUDIT_SHA = "81971ec62626e096c816a9533320436b893124ac96f7122875abeed1788b99c6"


def run(output):
    manifest = PARENT / "SHA256SUMS"
    if portfolio.sha(manifest) != PARENT_SHA or portfolio.sha(PARENT_AUDIT) != PARENT_AUDIT_SHA:
        raise ValueError("unexpected Stage033 parent or audit")
    for line in manifest.read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        if portfolio.sha(PARENT / name) != digest:
            raise ValueError(f"Stage033 parent mismatch: {name}")
    market = extend(load(MARKET, control=True), TAIL)
    parent_inputs = json.loads((PARENT / "2015/inputs.json").read_text())
    market_hashes = {str(path): digest for path, digest in market[-1].items()}
    if parent_inputs["inputs_sha256"] != market_hashes or len(market[0]) != 19:
        raise ValueError("market data differ from Stage033")
    reference, candidate = output / "fixed_one", output / "cash_risk_0_5pct"
    for destination, dynamic in ((reference, False), (candidate, True)):
        with redirect_stdout(StringIO()):
            portfolio.run(destination, week_body_filter=True, reverse_after_stop=True,
                          block_four_up=True, delivery_guard=True, market_loader=lambda: market,
                          cash_risk=dynamic, risk_fraction=portfolio.CASH_RISK_HALF_PCT)
        inputs = json.loads((destination / "inputs.json").read_text())
        expected = {**parent_inputs, "cash_risk_fraction": 0.005 if dynamic else None}
        for document in (inputs, expected):
            document.pop("source_sha256")
        if inputs != expected:
            raise ValueError(f"unexpected configuration drift in {destination.name}")
        daily = pd.read_csv(destination / "daily.csv")
        if daily.date.tolist() != [day for day in market[1] if day >= portfolio.START]:
            raise ValueError(f"unexpected trading calendar in {destination.name}")
        terminal = json.loads((destination / "terminal.json").read_text())
        if any((TARGET, position["epoch"]) not in market[5] for position in terminal["positions"].values()):
            raise ValueError(f"missing final mark in {destination.name}")
        gaps = pd.read_csv(destination / "gaps.csv")
        if gaps.date.eq(TARGET).any():
            raise ValueError(f"latest session coverage gap in {destination.name}")
    if {path.name for path in reference.iterdir()} != {path.name for path in (PARENT / "2015").iterdir()}:
        raise ValueError("control file set differs")
    for path in reference.iterdir():
        if path.name != "inputs.json" and path.read_bytes() != (PARENT / "2015" / path.name).read_bytes():
            raise ValueError(f"control does not reproduce {path.name}")
    receipt = dict(parent_manifest_sha256=PARENT_SHA, parent_audit_sha256=PARENT_AUDIT_SHA,
                   design_sha256=portfolio.sha(DESIGN), entrypoint_sha256=portfolio.sha(Path(__file__)),
                   matched_control=True, cutoff=TARGET, inputs_sha256=market_hashes)
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    write_checksums(output, (path for path in output.rglob("*") if path.is_file()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
