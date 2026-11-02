"""Explicit immutable C9 material fixture, never the current formal default.

Load the historical builder itself. Tests retain its real frozen semantics
while production imports continue to select weekly19.
"""
from pathlib import Path
import importlib.util
import json
import hashlib
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
RELEASE=ROOT/'official_strategy_materials/ai_top10_plus_fu_official_live_v1/releases/m0008_20261008T204054+0800_2a7420a9f955'
HISTORICAL_MANIFEST_SHA256='94b6936ab4b338430981f4c2f7e0f4ff38f24534c32f1d16722c8d1367d89474'
HISTORICAL_CONFIG_SHA256='82faa02ebf4f782d6e2e2c531eafac0f95b6f8d10c62253dcc16b8922db74ac5'

def load_historical_c9_config():
    path=RELEASE/'payload/examples/portfolio_backtesting/qmt_roll_official_live_config.py'
    manifest=json.loads((RELEASE/'manifest.json').read_text())
    expected=next(row for row in manifest['files'] if row['payload_path']==str(path.relative_to(RELEASE)))
    if (manifest['manifest_sha256']!=HISTORICAL_MANIFEST_SHA256 or expected['sha256']!=HISTORICAL_CONFIG_SHA256
            or hashlib.sha256(path.read_bytes()).hexdigest()!=HISTORICAL_CONFIG_SHA256):
        raise AssertionError('historical C9 configuration differs from immutable material')
    spec=importlib.util.spec_from_file_location('weekly19_test_frozen_c9_config',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from qmt_roll_official_execution_profile import C9_15W_PROFILE as profile
    module.OFFICIAL_LIVE_ALIAS=profile.alias
    module.OFFICIAL_LIVE_VERSION=profile.official_version
    module.OFFICIAL_LIVE_MATERIAL_STRATEGY_VERSION='ai_top10_plus_fu_official_live_v1'
    module.OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE='2026-07-23'
    module.OFFICIAL_LIVE_MATERIAL_RELEASE_ID=RELEASE.name
    module.OFFICIAL_LIVE_MATERIAL_MANIFEST_SHA256=manifest['manifest_sha256']
    module.OFFICIAL_LIVE_STAGE901_PREFIX='qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow'
    module.OFFICIAL_LIVE_STAGE901_MODEL_TAG='stage901_stage847_c9_2026_ytd_live_shadow_v1'
    module.OFFICIAL_LIVE_SUMMARY_PATH=profile.summary_path
    module.OFFICIAL_LIVE_SIGNAL_PLAN_PATH=profile.signal_plan_path
    module.OFFICIAL_LIVE_CURRENT_POSITIONS_PATH=profile.current_positions_path
    module.OFFICIAL_LIVE_PENDING_ORDERS_PATH=profile.pending_orders_path
    module.OFFICIAL_LIVE_REPORT_PATH=profile.summary_path.with_name(profile.summary_path.name.replace('_decision_','_report_')).with_suffix('.md')
    module.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH=RELEASE/'payload/ai/stage182/combined_eligibility.csv'
    original=module.stage847_c9_cfg
    module.stage847_c9_cfg=SimpleNamespace(**vars(original))
    module.stage847_c9_cfg.build_official_candidate_stage847_c9_overrides=lambda:original._build_official_candidate_stage847_c9_overrides(
        Path('/offline/stage847-universe.csv'),Path('/offline/stage847-eligibility.csv'))
    return module
