"""Redraw Stage063 charts from published CSVs without touching engine checkpoints."""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
TOOLS_DIR = Path(__file__).resolve().parent
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
for directory in (TOOLS_DIR, PORTFOLIO_DIR):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import stage063_stage037_top9_top10_multicycle as runner  # noqa: E402


RENDER_ARMS = tuple(
    {
        **arm,
        "plot_label": {
            "A": "Formal Stage037 Top8+fu",
            "B": "Top9+fu",
            "C": "Top10+fu",
        }[arm["arm"]],
    }
    for arm in runner.ARMS
)


def _load_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        pd.read_csv(runner.OUTPUT_DIR / runner.CURVE_NAME, low_memory=False),
        pd.read_csv(runner.OUTPUT_DIR / runner.COMPARISON_NAME, low_memory=False),
        pd.read_csv(runner.OUTPUT_DIR / runner.AGGREGATE_NAME, low_memory=False),
    )


def main() -> None:
    reuse_contract = runner._assert_reuse_sources_frozen()
    curve, comparison, aggregate = _load_frames()
    original_arms = runner.ARMS
    try:
        runner.ARMS = RENDER_ARMS
        charts = {
            runner.CHART_FILES["full_period"]: runner._plot_full(curve),
            runner.CHART_FILES["1y"]: runner._plot_grid(curve, comparison, 1),
            runner.CHART_FILES["2y"]: runner._plot_grid(curve, comparison, 2),
            runner.CHART_FILES["3y"]: runner._plot_grid(curve, comparison, 3),
            runner.CHART_FILES["aggregate"]: runner._plot_aggregate(aggregate),
        }
    finally:
        runner.ARMS = original_arms
    for name, payload in charts.items():
        destination = runner.OUTPUT_DIR / name
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
        temporary.write_bytes(payload)
        os.replace(temporary, destination)
        print(f"[stage063-render] wrote {name}", flush=True)

    decision_path = runner.OUTPUT_DIR / runner.DECISION_NAME
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["publication_reuse_contract"] = reuse_contract
    render_provenance = {
        "rendered_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "renderer": str(Path(__file__).resolve().relative_to(runner.PROJECT_DIR.resolve())),
        "renderer_sha256": runner._file_sha256(Path(__file__)),
        "chart_sha256": {
            name: runner._file_sha256(runner.OUTPUT_DIR / name)
            for name in runner.CHART_FILES.values()
        },
    }
    decision["render_provenance"] = render_provenance
    current_runner_hash = runner._runtime_contract_hash(
        {
            "B": runner.INPUT_DIR / "stage063_top9_eligibility.csv",
            "C": runner.INPUT_DIR / "stage063_top10_eligibility.csv",
        }
    )
    publication_payload = {
        "reuse_source_contract": reuse_contract,
        "renderer_sha256": render_provenance["renderer_sha256"],
        "chart_sha256": render_provenance["chart_sha256"],
    }
    decision["runtime_contracts"] = {
        "engine_checkpoint": {
            "sha256": decision["identity"]["runtime_contract_sha256"],
            "scope": "84 B/C engine checkpoints generated with the original runner, database and eligibility contract",
            "generated_before_reuse_hardening": True,
        },
        "current_runner": {
            "sha256": current_runner_hash,
            "scope": "future engine/checkpoint runs; includes all frozen Stage059/061/062 reuse source files",
            "matches_engine_checkpoint_contract": bool(
                current_runner_hash == decision["identity"]["runtime_contract_sha256"]
            ),
        },
        "publication": {
            "sha256": runner._json_sha256(publication_payload),
            "scope": "published reused evidence, renderer and five chart payloads",
            "covers_published_reuse_and_charts": True,
        },
    }
    temporary_decision = decision_path.with_name(f".{decision_path.name}.{uuid4().hex}.tmp")
    temporary_decision.write_text(
        json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary_decision, decision_path)
    print("[stage063-render] updated immutable render provenance", flush=True)


if __name__ == "__main__":
    main()
