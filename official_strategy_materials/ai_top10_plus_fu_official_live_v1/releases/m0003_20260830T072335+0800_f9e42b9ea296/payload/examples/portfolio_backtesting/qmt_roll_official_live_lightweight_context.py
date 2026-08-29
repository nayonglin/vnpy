from __future__ import annotations

import os
from pathlib import Path

from qmt_roll_official_ai_pool_policy import OFFICIAL_AI_PRODUCT_POOL_STRATEGY
from qmt_roll_official_strategy_material_resolver import (
    load_active_material_release,
    resolve_active_material,
)


PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parents[1]
DATA_ASSET_DIR = PROJECT_DIR / "backtest_outputs"
CONTROL_OUTPUT_DIR = Path(
    os.environ.get("OFFICIAL_LIVE_OUTPUT_DIR", str(DATA_ASSET_DIR))
).expanduser().resolve(strict=False)
SIGNAL_INPUT_DIR = Path(
    os.environ.get(
        "OFFICIAL_LIVE_SIGNAL_INPUT_DIR",
        os.environ.get("OFFICIAL_LIVE_OUTPUT_DIR", str(DATA_ASSET_DIR)),
    )
).expanduser().resolve(strict=False)

OFFICIAL_LIVE_ALIAS = "Stage847-C9-15w"
OFFICIAL_LIVE_VERSION = (
    "official_live_stage847_c9_15w_stage819_05r_stop_retry_once"
)
OFFICIAL_LIVE_MATERIAL_STRATEGY_VERSION = OFFICIAL_AI_PRODUCT_POOL_STRATEGY
OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE = "2026-07-23"
OFFICIAL_LIVE_AI_LOGICAL_PATH = "ai/stage182/combined_eligibility.csv"
OFFICIAL_LIVE_AI_LATEST_POOL_LOGICAL_PATH = "ai/stage182/latest_pool.csv"
OFFICIAL_LIVE_AI_LIVE_ELIGIBILITY_LOGICAL_PATH = "ai/stage182/live_eligibility.csv"
OFFICIAL_LIVE_AI_SUMMARY_LOGICAL_PATH = "ai/stage182/summary.json"
OFFICIAL_LIVE_AI_REPORT_LOGICAL_PATH = "ai/stage182/report.md"
OFFICIAL_LIVE_MATERIAL_CURRENT_PATH = (
    REPO_ROOT / "official_strategy_materials/CURRENT.json"
)
OFFICIAL_LIVE_MATERIAL_RELEASE = load_active_material_release(
    OFFICIAL_LIVE_MATERIAL_CURRENT_PATH,
    repo_root=REPO_ROOT,
)
if (
    OFFICIAL_LIVE_MATERIAL_RELEASE.strategy_version
    != OFFICIAL_LIVE_MATERIAL_STRATEGY_VERSION
):
    raise RuntimeError("official_live_material_strategy_version_mismatch")
OFFICIAL_LIVE_MATERIAL_RELEASE_ID = OFFICIAL_LIVE_MATERIAL_RELEASE.release_id
OFFICIAL_LIVE_MATERIAL_RELEASE_COMMIT = OFFICIAL_LIVE_MATERIAL_RELEASE.release_commit
OFFICIAL_LIVE_MATERIAL_MANIFEST_SHA256 = str(
    OFFICIAL_LIVE_MATERIAL_RELEASE.manifest["manifest_sha256"]
)

OFFICIAL_LIVE_STAGE901_PREFIX = (
    "qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow"
)
OFFICIAL_LIVE_STAGE901_MODEL_TAG = (
    "stage901_stage847_c9_2026_ytd_live_shadow_v1"
)
OFFICIAL_LIVE_SUMMARY_PATH = (
    SIGNAL_INPUT_DIR
    / f"{OFFICIAL_LIVE_STAGE901_PREFIX}_decision_"
    f"{OFFICIAL_LIVE_STAGE901_MODEL_TAG}.json"
)
OFFICIAL_LIVE_AI_ELIGIBILITY_PATH = (
    resolve_active_material(
        OFFICIAL_LIVE_MATERIAL_RELEASE,
        logical_path=OFFICIAL_LIVE_AI_LOGICAL_PATH,
    )
)
OFFICIAL_LIVE_AI_LATEST_POOL_PATH = resolve_active_material(
    OFFICIAL_LIVE_MATERIAL_RELEASE,
    logical_path=OFFICIAL_LIVE_AI_LATEST_POOL_LOGICAL_PATH,
)
OFFICIAL_LIVE_AI_LIVE_ELIGIBILITY_PATH = resolve_active_material(
    OFFICIAL_LIVE_MATERIAL_RELEASE,
    logical_path=OFFICIAL_LIVE_AI_LIVE_ELIGIBILITY_LOGICAL_PATH,
)
OFFICIAL_LIVE_AI_SUMMARY_PATH = resolve_active_material(
    OFFICIAL_LIVE_MATERIAL_RELEASE,
    logical_path=OFFICIAL_LIVE_AI_SUMMARY_LOGICAL_PATH,
)
OFFICIAL_LIVE_AI_REPORT_PATH = resolve_active_material(
    OFFICIAL_LIVE_MATERIAL_RELEASE,
    logical_path=OFFICIAL_LIVE_AI_REPORT_LOGICAL_PATH,
)

STAGE173_PREFIX = "qmt_roll_stage173_forward_main_contract_data_update"
STAGE173_MODEL_TAG = "stage173_forward_main_contract_data_update_v1"
STAGE173_SUMMARY_PATH = (
    DATA_ASSET_DIR / f"{STAGE173_PREFIX}_summary_{STAGE173_MODEL_TAG}.json"
)
STAGE173_STATUS_PATH = (
    DATA_ASSET_DIR
    / f"{STAGE173_PREFIX}_contract_bar_status_{STAGE173_MODEL_TAG}.csv"
)
ALL_FUTURES_MAPPING_PATH = (
    DATA_ASSET_DIR / "tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv"
)
