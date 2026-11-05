"""Replay the frozen S44 with two fixed weekly OHLC admission rules."""
import argparse
import json
from pathlib import Path

from run_weekly_portfolio import run, sha
from stage025_delivery_guard import load
from stage028_week_range_overlap import BASE, BASE_MANIFEST_SHA, LINE, MARKET

DESIGN = LINE / "stages/20261104_1539_stage030_s44_weekly_shape_replay_design.md"
ARMS = {"control": None, "expansion": "expansion", "expansion_break3": "expansion_break3"}


def replay(output):
    manifest = BASE / "SHA256SUMS"
    if sha(manifest) != BASE_MANIFEST_SHA:
        raise ValueError("unexpected Stage025 manifest")
    for line in manifest.read_text().splitlines():
        digest, filename = line.split(maxsplit=1)
        if sha(BASE / filename) != digest:
            raise ValueError(f"baseline hash mismatch: {filename}")

    market = load(MARKET, control=False)
    output.mkdir(parents=True)
    baseline = json.loads((BASE / "inputs.json").read_text())
    baseline.pop("source_sha256")
    for name, mode in ARMS.items():
        arm = output / name
        run(arm, week_body_filter=True, reverse_after_stop=True, block_four_up=True,
            delivery_guard=True, market_loader=lambda: market, weekly_shape_entry=mode)
        inputs = json.loads((arm / "inputs.json").read_text())
        inputs.pop("source_sha256")
        if inputs.pop("weekly_shape_entry", None) != mode or inputs != baseline:
            raise ValueError(f"unexpected inputs for {name}")
        if mode is None:
            for file in arm.iterdir():
                if file.name != "inputs.json" and file.read_bytes() != (BASE / file.name).read_bytes():
                    raise ValueError(f"control does not reproduce Stage025: {file.name}")
    receipt = {"baseline_manifest_sha256": BASE_MANIFEST_SHA, "design_sha256": sha(DESIGN),
               "control_reproduces_stage025": True, "arms": ARMS}
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    files = sorted(file for file in output.rglob("*") if file.is_file())
    (output / "SHA256SUMS").write_text("".join(f"{sha(file)}  {file.relative_to(output)}\n" for file in files))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    replay(parser.parse_args().output)
