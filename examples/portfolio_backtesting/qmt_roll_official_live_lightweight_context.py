from __future__ import annotations

import os
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
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
OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE = "2026-07-23"

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
    DATA_ASSET_DIR
    / "qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_"
    "eligibility_stage182_ai_product_pool_live_inference_v1.csv"
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
