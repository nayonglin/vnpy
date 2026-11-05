"""Replay the frozen two-sided S44 and the fixed 50% weekly range filter."""
import argparse
import json
from pathlib import Path

from run_weekly_portfolio import run, sha
from stage025_delivery_guard import load

LINE = Path(__file__).resolve().parents[1]
MARKET = LINE / "outputs/stage024_market/approved_v1"
BASE = LINE / "outputs/stage025_delivery_guard/S44_guard_2015_20261103_attempt001"
BASE_MANIFEST_SHA = "406465f36de37935b4947fb68bf94a6b4caf3437916fdad639ff2269f0c2f361"
DESIGN = LINE / "stages/20261104_1519_stage028_s44_week_range_overlap.md"


def replay(output):
    manifest = BASE / "SHA256SUMS"
    if sha(manifest) != BASE_MANIFEST_SHA:
        raise ValueError("unexpected Stage025 baseline manifest")
    for line in manifest.read_text().splitlines():
        digest, filename = line.split(maxsplit=1)
        if sha(BASE / filename) != digest:
            raise ValueError(f"Stage025 baseline hash mismatch: {filename}")

    market = load(MARKET, control=False)
    output.mkdir(parents=True)
    for name, enabled in (("control", False), ("overlap50", True)):
        arm = output / name
        run(arm, week_body_filter=True, reverse_after_stop=True, block_four_up=True,
            delivery_guard=True, market_loader=lambda: market, block_week_range_overlap=enabled)

    control = output / "control"
    source_inputs = json.loads((BASE / "inputs.json").read_text())
    control_inputs = json.loads((control / "inputs.json").read_text())
    candidate_inputs = json.loads((output / "overlap50/inputs.json").read_text())
    for inputs in (source_inputs, control_inputs, candidate_inputs):
        inputs.pop("source_sha256")
    if source_inputs != control_inputs or candidate_inputs.pop("block_week_range_overlap_pct") != 50:
        raise ValueError("unexpected replay parameters")
    if candidate_inputs != control_inputs:
        raise ValueError("candidate differs from control in unrelated parameters")
    for file in sorted(control.iterdir()):
        if file.name != "inputs.json" and file.read_bytes() != (BASE / file.name).read_bytes():
            raise ValueError(f"control does not reproduce Stage025: {file.name}")

    receipt = {
        "baseline_manifest_sha256": BASE_MANIFEST_SHA,
        "design_sha256": sha(DESIGN),
        "entrypoint_sha256": sha(Path(__file__)),
        "control_reproduces_stage025": True,
    }
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    files = sorted(file for file in output.rglob("*") if file.is_file())
    (output / "SHA256SUMS").write_text("".join(f"{sha(file)}  {file.relative_to(output)}\n" for file in files))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    replay(parser.parse_args().output)
