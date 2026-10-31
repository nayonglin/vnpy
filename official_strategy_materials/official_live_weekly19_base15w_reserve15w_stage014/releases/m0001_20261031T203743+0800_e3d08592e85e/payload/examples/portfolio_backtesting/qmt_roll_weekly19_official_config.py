"""Frozen Stage014 policy for the requested weekly19 formal candidate.

This module defines a candidate. It does not change CURRENT, grant production
qualification or replace the existing formal default by being imported.
"""
from copy import deepcopy
import hashlib,json
from pathlib import Path
from qmt_roll_official_execution_profile import WEEKLY19_15W_R150K_PROFILE as PROFILE

HERE=Path(__file__).resolve().parent
ASSETS=HERE/'weekly19_assets'
STRATEGY_VERSION=PROFILE.official_version
RULESET_VERSION=PROFILE.ruleset_version
PROFILE_NAME=PROFILE.profile_key
CAPITAL=150000.0
EXTERNAL_RESERVE=150000.0
FROZEN_RESEARCH_FINANCIAL_SOURCE_COMMIT='688754057ba1dc07caa9edc537ceec486f678372'
FROZEN_RESEARCH_DELIVERY_SOURCE_COMMIT='e6f19df6dd41c3b2f4ad73b4f3a2c6cdf03dfbd0'
NATURAL_RESEARCH_VERDICT='NO_PROMOTION'
OPERATOR_REQUEST='replace_formal_master_and_local_production_after_qualification'
EXECUTION_POLICY=dict(execution_profile=PROFILE.profile_key,base_capital=CAPITAL,external_reserve=EXTERNAL_RESERVE,
 risk_capital='actual_trading_account_equity_including_mark_to_market',reserve_participates_in_equity=False,
 reserve_participates_in_margin=False,funding_recommendation='native_admission_before_sizing_friday_afternoon',
 funding_credit='actual_broker_cashflow_confirmed_only',funding_transfer_api_enabled=False,
 protection_timing='fresh_completed_week_close',intraday_stop_retry_enabled=False,
 signal_sources=sorted(PROFILE.allowed_intent_sources),ai_enabled=False,add_on_enabled=False)

def build_weekly19_strategy_overrides():
 from qmt_roll_weekly19_runtime import verify_frozen_sources
 manifest=verify_frozen_sources();path=ASSETS/'actual_settings.json'
 if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['settings_asset_sha256']:raise ValueError('weekly19_fixed_settings_drift')
 asset=json.loads(path.read_text());settings=deepcopy(asset['settings'])
 for key,value in list(settings.items()):
  if isinstance(value,str)and value.startswith('@ASSET/'):
   name=value.split('/',1)[1]
   if name not in asset['assets']or Path(name).name!=name:raise ValueError('weekly19_asset_contract_invalid')
   settings[key]=str(ASSETS/name)
 return settings

def build_weekly19_policy_manifest():
 return dict(strategy_version=STRATEGY_VERSION,ruleset_version=RULESET_VERSION,execution_profile=PROFILE_NAME,
  capital=CAPITAL,external_reserve=EXTERNAL_RESERVE,execution_policy=deepcopy(EXECUTION_POLICY),
  settings_sha256=hashlib.sha256((ASSETS/'actual_settings.json').read_bytes()).hexdigest(),
  research=dict(stage='Stage014 C_R150',start_dates=59,mature_starts=54,observation_starts=5,
   cutoff='2026-10-30',financial_source_commit=FROZEN_RESEARCH_FINANCIAL_SOURCE_COMMIT,
   delivery_source_commit=FROZEN_RESEARCH_DELIVERY_SOURCE_COMMIT,natural_verdict=NATURAL_RESEARCH_VERDICT,
   operator_request=OPERATOR_REQUEST,limitations=['zero_commission','not_complete_point_in_time_history',
    'not_new_out_of_sample','reserve_exhausted_in_5_starts','model_margin_pressure_in_37_starts']),
  production_qualified=False)
