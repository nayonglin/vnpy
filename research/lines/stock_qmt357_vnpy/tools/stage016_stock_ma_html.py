"""Add an independent MA display toggle to the frozen stock Bollinger recap.

Re-render with the pinned canonical renderer; preserve all previous artifacts,
prices, indicators and strategy resources. No replay or market download.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import shutil
import sys

TOOLS = Path(__file__).resolve().parent
BASE_PATH = TOOLS / "stage015_stock_bollinger_html.py"
UI_PATH = TOOLS / "stage016_stock_ma_ui.js"
spec = importlib.util.spec_from_file_location("stock_bollinger_recap", BASE_PATH)
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
base = previous.base
PARENT = previous.OUTPUT
OUTPUT = base.LINE / "outputs/stage016_commit4ac255e_stock_recap_ma_v1"
ARTIFACTS = ("index.html", "records.json", "chart_manifest.csv", "indicator_audit.json")


def load_parent(parent: Path) -> tuple[dict, list, dict]:
    summary_path = parent / "summary.json"
    summary = base.read_json(summary_path)
    if summary.get("status") != "COMPLETE":
        raise ValueError("Parent recap must be COMPLETE")
    adapter_hash = base.sha256(BASE_PATH)
    if summary.get("adapter_sha256") != adapter_hash or summary.get("input_sha256", {}).get(str(BASE_PATH)) != adapter_hash:
        raise ValueError("Parent adapter hash mismatch")
    hashes = dict(summary["input_sha256"])
    hashes[str(summary_path)] = base.sha256(summary_path)
    for name in ARTIFACTS:
        expected = summary.get("artifact_sha256", {}).get(name)
        if not expected:
            raise ValueError(f"Missing parent artifact hash: {name}")
        hashes[str(parent / name)] = expected
    for name, expected in hashes.items():
        if base.sha256(Path(name)) != expected:
            raise ValueError(f"Frozen input hash mismatch: {name}")
    records = json.loads((parent / "records.json").read_text(encoding="utf-8"))
    if len(records) != summary["completed_episodes"] or len(records) != summary["frozen_metrics"]["closed_round_trips"]:
        raise ValueError("Frozen episode count mismatch")
    return summary, records, hashes


def generate(output: Path = OUTPUT) -> dict:
    output = base.validate_output_path(output)
    parent_summary, records, hashes = load_parent(PARENT)
    source = base.verify_bundle(base.RUN, base.PANEL)
    if (parent_summary["frozen_metrics"] != source["summary"]
            or parent_summary["source_run_id"] != source["manifest"]["run_id"]
            or any(hashes.get(path) != digest for path, digest in source["input_sha256"].items())):
        raise ValueError("Parent recap differs from this frozen stock run")
    for path in (UI_PATH, Path(__file__)):
        hashes[str(path)] = base.sha256(path)
    summary = deepcopy(parent_summary)
    summary.pop("artifact_sha256", None)
    summary.update(
        page_title="QMT357 · commit4ac255e 股票逐笔复盘 · 布林与均线开关｜2020—2026-09-28",
        coverage_note=parent_summary["coverage_note"] + " 各周期MA5/10/20/40默认显示，可独立开关。",
        parent_recap=str(PARENT), parent_adapter_sha256=parent_summary["adapter_sha256"],
        adapter_sha256=base.sha256(Path(__file__)), input_sha256=hashes,
        moving_averages={"periods": [5, 10, 20, 40], "scope": "all_periods", "default_visible": True,
                         "persistence": "current_page_across_trade_and_period_changes"},
        created_at=datetime.now().astimezone().isoformat(),
    )
    page = previous.render_bollinger_html(records, summary, base.load_renderer())
    if page.count("</body>") != 1:
        raise ValueError("Canonical document extension hook changed")
    page = page.replace("</body>", "<script>" + UI_PATH.read_text(encoding="utf-8")
                        + "\ninstallStockMovingAverages();</script></body>", 1)
    for name, expected in hashes.items():
        if base.sha256(Path(name)) != expected:
            raise ValueError(f"Input changed during display build: {name}")
    output.mkdir(parents=True, exist_ok=False)
    (output / "index.html").write_text(page, encoding="utf-8")
    for name in ARTIFACTS[1:]:
        shutil.copyfile(PARENT / name, output / name)
    summary["artifact_sha256"] = {name: base.sha256(output / name) for name in ARTIFACTS}
    for name in ARTIFACTS[1:]:
        if summary["artifact_sha256"][name] != parent_summary["artifact_sha256"][name]:
            raise ValueError(f"Display-only build changed frozen data: {name}")
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    summary = generate(args.output)
    forbidden = [name for name in sys.modules if name.startswith(("vnpy", "tqsdk", "qmt_roll", "analyze_qmt"))]
    if forbidden:
        raise RuntimeError(f"Unexpected trading imports: {forbidden}")
    print(json.dumps({"output": str(args.output), "episodes": summary["completed_episodes"],
                      "moving_averages": summary["moving_averages"], "futures_imports": forbidden}, ensure_ascii=False))


if __name__ == "__main__":
    main()
