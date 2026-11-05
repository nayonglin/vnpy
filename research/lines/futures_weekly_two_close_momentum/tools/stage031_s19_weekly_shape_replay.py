"""Replay the Stage030 rules on the frozen Stage025 19-product pool."""
import argparse
import json
from pathlib import Path

from run_weekly_portfolio import run, sha
from stage025_delivery_guard import load
from stage030_weekly_shape_replay import ARMS, LINE, MARKET

BASE = LINE / "outputs/stage025_delivery_guard/S19_guard_2015_20261103_attempt001"
BASE_MANIFEST_SHA = "290d78eff428edbc8e1fe12047d69325aa26ffa65e9dc3f83d11f8d34f2624b8"
DESIGN = LINE / "stages/20261104_1552_stage031_s19_weekly_shape_replay_design.md"


def replay(output):
    manifest = BASE / "SHA256SUMS"
    if sha(manifest) != BASE_MANIFEST_SHA:
        raise ValueError("unexpected Stage025 S19 manifest")
    for line in manifest.read_text().splitlines():
        digest, filename = line.split(maxsplit=1)
        if sha(BASE / filename) != digest:
            raise ValueError(f"S19 baseline hash mismatch: {filename}")

    market = load(MARKET, control=True)
    baseline = json.loads((BASE / "inputs.json").read_text())
    baseline.pop("source_sha256")
    if len(market[0]) != 19 or market[0] != baseline["products"]:
        raise ValueError("unexpected S19 universe")

    output.mkdir(parents=True)
    for name, mode in ARMS.items():
        arm = output / name
        run(arm, week_body_filter=True, reverse_after_stop=True, block_four_up=True,
            delivery_guard=True, market_loader=lambda: market, weekly_shape_entry=mode)
        inputs = json.loads((arm / "inputs.json").read_text())
        inputs.pop("source_sha256")
        if inputs.pop("weekly_shape_entry", None) != mode or inputs != baseline:
            raise ValueError(f"unexpected S19 inputs for {name}")
        if mode is None:
            for file in arm.iterdir():
                if file.name != "inputs.json" and file.read_bytes() != (BASE / file.name).read_bytes():
                    raise ValueError(f"control does not reproduce Stage025 S19: {file.name}")
    receipt = {"baseline_manifest_sha256": BASE_MANIFEST_SHA, "design_sha256": sha(DESIGN),
               "entrypoint_sha256": sha(Path(__file__)), "products": market[0],
               "control_reproduces_stage025_s19": True, "arms": ARMS}
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    files = sorted(file for file in output.rglob("*") if file.is_file())
    (output / "SHA256SUMS").write_text("".join(f"{sha(file)}  {file.relative_to(output)}\n" for file in files))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    replay(parser.parse_args().output)
