from __future__ import annotations

from pathlib import Path

import analyze_qmt_roll_stage316_supply_demand_quality_probe as stage316


MODEL_TAG = "stage358_supply_demand_backfill_2020_2022_v1"
OUTPUT_PREFIX = "qmt_roll_stage358_supply_demand_backfill_2020_2022"
FETCH_START_DAY = "20200101"
FETCH_END_DAY = "20221231"


def _retarget_stage316() -> None:
    stage316.MODEL_TAG = MODEL_TAG
    stage316.OUTPUT_PREFIX = OUTPUT_PREFIX
    stage316.FETCH_START_DAY = FETCH_START_DAY
    stage316.FETCH_END_DAY = FETCH_END_DAY

    raw_dir: Path = stage316.RAW_DIR
    output_dir: Path = stage316.OUTPUT_DIR
    stage316.RAW_BASIS_PATH = raw_dir / f"supply_demand_basis_{FETCH_START_DAY}_{FETCH_END_DAY}.csv"
    stage316.RAW_WAREHOUSE_PATH = raw_dir / f"supply_demand_warehouse_{FETCH_START_DAY}_{FETCH_END_DAY}.csv"
    stage316.FEATURE_OUTPUT_PATH = output_dir / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
    stage316.EXTERNAL_SIGNAL_PATH = output_dir / f"{OUTPUT_PREFIX}_external_signals_{MODEL_TAG}.csv"
    stage316.JOINED_OUTPUT_PATH = output_dir / f"{OUTPUT_PREFIX}_joined_candidates_{MODEL_TAG}.csv"
    stage316.BUCKET_OUTPUT_PATH = output_dir / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
    stage316.COVERAGE_OUTPUT_PATH = output_dir / f"{OUTPUT_PREFIX}_coverage_{MODEL_TAG}.csv"
    stage316.SOURCE_SUMMARY_PATH = output_dir / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
    stage316.SUMMARY_JSON_PATH = output_dir / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
    stage316.REPORT_PATH = output_dir / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def main() -> None:
    _retarget_stage316()
    stage316.main()


if __name__ == "__main__":
    main()
