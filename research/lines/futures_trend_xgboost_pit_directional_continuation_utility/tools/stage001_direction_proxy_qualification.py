from __future__ import annotations

import argparse
import csv
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
import gzip
import hashlib
import inspect
import json
import os
from pathlib import Path
import shutil
import sys
import uuid
from typing import Any, Mapping

import numpy as np
import pandas as pd

from directional_continuation_proxy import (
    DirectionProxyError,
    DirectionSettings,
    build_cost_metadata,
    evaluate_direction_proxy,
)


LINE_ID = "futures_trend_xgboost_pit_directional_continuation_utility"
STAGE = "Stage001"
PASS_DECISION = "stage001_direction_proxy_qualification_pass_allow_label_preregistration_only"
FAIL_DECISION = "stage001_direction_proxy_qualification_fail_close_no_future_labels"
FIXED_FU = "fu.SHFE"

LINE_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = LINE_DIR.parents[2]
EXAMPLES_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLES_DIR))

PANEL_PATH = (
    PROJECT_DIR
    / "research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/"
    "artifacts/stage001_daily_ranker_contract/model_feature_panel.csv.gz"
)
FORMAL_PLAN_PATH = (
    PROJECT_DIR
    / "research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/"
    "artifacts/stage001_daily_ranker_contract/formal_scoring_plan.csv"
)
FEATURE_MANIFEST_PATH = (
    PROJECT_DIR
    / "research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/"
    "artifacts/stage001_daily_ranker_contract/artifact_manifest.json"
)
SOURCE_DIR = (
    PROJECT_DIR
    / "research/lines/futures_trend_xgboost_pit_full_market_source_rebuild/"
    "artifacts/stage002_endofday_source_rebuild"
)
SOURCE_MANIFEST_PATH = SOURCE_DIR / "artifact_manifest.json"
SOURCE_SUMMARY_PATH = SOURCE_DIR / "stage002_summary.json"
PRODUCT_METADATA_PATH = SOURCE_DIR / "invariant_product_metadata.csv"
EXPIRY_DIR = (
    PROJECT_DIR
    / "research/lines/futures_trend_xgboost_pit_expiry_safe_roll_mapping/"
    "artifacts/stage001_expiry_safe_roll_mapping"
)
EXPIRY_PATHS_PATH = EXPIRY_DIR / "expiry_safe_paths.csv.gz"
EXPIRY_LEGS_PATH = EXPIRY_DIR / "expiry_safe_legs.csv.gz"
EXPIRY_MANIFEST_PATH = EXPIRY_DIR / "artifact_manifest.json"
EXPIRY_SUMMARY_PATH = EXPIRY_DIR / "summary.json"

OUTPUT_DIR = LINE_DIR / "artifacts/stage001_direction_proxy_qualification"
EXECUTION_EVENT_PATH = LINE_DIR / "artifacts/stage001_execution_event.json"
EXECUTION_CLAIM_PATH = LINE_DIR / "artifacts/stage001_execution_claim.json"
PREREG_PATH = LINE_DIR / "stages/20260905_0552_stage000_direction_proxy_preregistration.md"
PLAN_PATH = LINE_DIR / "plans/20260905_stage001_direction_proxy_qualification.md"
AUTHORIZATION_BINDING_PATHS = {
    "preregistration": PREREG_PATH,
    "plan": PLAN_PATH,
    "core": LINE_DIR / "tools/directional_continuation_proxy.py",
    "runner": Path(__file__).resolve(),
    "core_tests": LINE_DIR / "tests/test_directional_continuation_proxy.py",
    "runner_tests": LINE_DIR / "tests/test_stage001_direction_proxy_qualification.py",
}

EXPECTED_INPUT_SHA256 = {
    "panel": "1e4ebb1942dc066eb1164dc82e7e0412fe10d433e57aa5b8b8ab3b71822344ac",
    "formal_plan": "ed83264188655939cb1289d75f480174be3bdcc50e7ed2a9daf0731a48a73ed2",
    "feature_manifest": "0ec63c32cf8fbe33a85bed16d20a94aaeb7d2ee9a5906670819e91d3671e702a",
    "source_manifest": "e3894cd20114182e9b3a9e986ed5e0310fe264de06368b5efe1b5efb6903681a",
    "source_summary": "67dcdb174bf7e253e100138eff1ec0b644c6a7cc68c0806f71aff10c66f00939",
    "product_metadata": "23141510dc4b82f397db07f61d5bfce0cfe0621858f135f49c3044360dd46174",
    "expiry_paths": "a3f2c1249085b872372f8f0aca2d1cbaf77ecb8a7bc04056f9118f077c16748e",
    "expiry_legs": "db2fcffc24053cbb5c540a699bc47f19149d54eeb66aa2b57057707f346a92da",
    "expiry_manifest": "9f768fc6de7ccd3eb240c29f0444249bd333356d756b137197dc78e4f5f44d76",
    "expiry_summary": "6f994dd88896781a7f1af9e9760890540445dc8539a6349ae416b82bcf37283f",
    "strategy": "98008f3c5e821cc9d9a522cd20864ad004a1dbd910fb4989509ac3e22adbcaec",
    "next_open_engine": "b2fab80fcbb15766350408a2cfe1cb1b810b6f2ae2f28d4ce6e839dda4df6bfd",
    "exact_am_wrapper": "5fbfe1cd84909b0c71df7a5b8f2042b9870e188709f43781bdb3a72fd806c6f5",
    "stage804_wrapper": "ae33da36e944a50c9d8fdd48f7149555b30f1168c2d3b557cfd268b4f9535e57",
    "stage827_engine": "9a63510355854349385c2309654101eb99432ddddf81c13636bc3dbbbde136f0",
    "stage830_engine": "0adf455e167b8dbfde51a4687098dba91a6788b13b7a1a81020c260d0af32647",
    "stage840_engine": "c9d37be2560278b20eb358a4767f05a25d579f856b9940eac1feee6a0b5a4d7d",
    "stage847_engine": "47b460d6744edc43da53e867acc791a19d81f173e04c830b221f5f68bd18765c",
    "stage901_live_shadow": "9947d72f921cd6063a5acd524106d8e2eb06adb991435ef20b1728ed47dc09d0",
    "roll_setting": "38a016d6da5fe3b9d93868745b5e4f64ea12f499033bd301aba60cc09c6ee5fd",
    "stage777_config": "b7934ab7a54b033bb1b9a979f55c056571dad4c96aa95f229e51e6f6c93ae7e7",
    "stage813_config": "25c1e9cdf3ee79c49c7772ffdac58317e83afabced36c145780d7cf0bdb5854d",
    "stage819_config": "ef3e10f57eca5fd8e7f1d5dc9e01d8b392d2799c16c4f4d17f1b530e90ab36bd",
    "stage847_config": "588e97e899f2291617fd935e474133a974da4088972e50a634ad0281e6edf83c",
    "live_config": "0f4d0b524629f828915d2ee237faa9eacb176e29efc0b926efecd207199a14fc",
    "qmt_universe": "8a149c49075d85d25f27146a8f3c2de3bea1971e3bd0d20a36ed9104b636997f",
    "main_contract_mapping": "86f4baa027e1a236616d749895e349840a3db305b7ca87a7401ff4afc47bc503",
}

PRODUCTION_EXTRA_INPUT_PATHS = {
    "feature_manifest": FEATURE_MANIFEST_PATH,
    "source_summary": SOURCE_SUMMARY_PATH,
    "expiry_legs": EXPIRY_LEGS_PATH,
    "expiry_manifest": EXPIRY_MANIFEST_PATH,
    "expiry_summary": EXPIRY_SUMMARY_PATH,
    "strategy": EXAMPLES_DIR / "qmt_roll_portfolio_strategy.py",
    "next_open_engine": EXAMPLES_DIR / "analyze_qmt_roll_stage502_confirmed_daily_next_real_open_replay.py",
    "exact_am_wrapper": EXAMPLES_DIR / "analyze_qmt_roll_stage772_am40_80_120_oi_monthly.py",
    "stage804_wrapper": EXAMPLES_DIR / "analyze_qmt_roll_stage804_stage777_long_tighter_initial_stop_yearly.py",
    "stage827_engine": EXAMPLES_DIR / "analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac.py",
    "stage830_engine": EXAMPLES_DIR / "analyze_qmt_roll_stage830_stage827_c2_broker10_margin_cap.py",
    "stage840_engine": EXAMPLES_DIR / "analyze_qmt_roll_stage840_stage830_c4_120m_failfast_engine.py",
    "stage847_engine": EXAMPLES_DIR / "analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine.py",
    "stage901_live_shadow": EXAMPLES_DIR / "analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py",
    "roll_setting": EXAMPLES_DIR / "run_qmt_roll_backtest.py",
    "stage777_config": EXAMPLES_DIR / "qmt_roll_official_candidate_stage777_config.py",
    "stage813_config": EXAMPLES_DIR / "qmt_roll_official_candidate_stage813_config.py",
    "stage819_config": EXAMPLES_DIR / "qmt_roll_official_candidate_stage819_30w_config.py",
    "stage847_config": EXAMPLES_DIR / "qmt_roll_official_candidate_stage847_c9_config.py",
    "live_config": EXAMPLES_DIR / "qmt_roll_official_live_config.py",
    "qmt_universe": EXAMPLES_DIR / "qmt_universe.py",
    "main_contract_mapping": EXAMPLES_DIR / "main_contract_mapping.py",
}

FORBIDDEN_COUNTERS = (
    "future_close_value_read_count",
    "future_return_compute_count",
    "label_generate_count",
    "logistic_fit_count",
    "xgboost_fit_count",
    "model_predict_count",
    "strategy_backtest_count",
    "true_engine_run_count",
    "sealed_holdout_read_count",
    "ctp_call_count",
    "order_api_call_count",
    "production_write_count",
)


@dataclass(frozen=True)
class QualificationContract:
    expected_panel_rows: int = 57_528
    expected_panel_qids: int = 1_067
    expected_panel_products: int = 64
    expected_fixed_fu_rows: int = 1_067
    expected_model_rows: int = 56_461
    expected_model_qids: int = 1_067
    expected_model_products: int = 63
    expected_qid_width_min: int = 48
    expected_qid_width_median: float = 52.0
    expected_qid_width_max: int = 60
    expected_development_rows: int = 55_226
    expected_development_qids: int = 1_046
    expected_development_products: int = 62
    expected_inference_rows: int = 1_235
    expected_inference_qids: int = 21
    expected_formal_action_dates: int = 48
    expected_formal_development_dates: int = 47
    expected_formal_inference_dates: int = 1
    min_observable_per_development_qid: int = 10
    min_active_development_qids: int = 252
    required_direction_years: tuple[int, ...] = (2022, 2023, 2024, 2025, 2026)
    expected_explicit_cost_products: int = 17
    expected_fallback_cost_products: int = 46
    require_runtime_identity: bool = True


@dataclass(frozen=True)
class ExecutionLease:
    nonce: str
    event_path: Path
    consumed_at: str
    lease_id: str
    authorization_digest: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_identity(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return pd.Timestamp(value).isoformat()
    if value is pd.NA:
        return None
    return value


def _tq_to_vt_symbol(tq_symbol: str) -> str:
    parts = str(tq_symbol).split(".", 1)
    if len(parts) != 2 or not all(parts):
        raise ValueError(f"source_tq_symbol_invalid:{tq_symbol}")
    return f"{parts[1]}.{parts[0]}"


def _runtime_identity() -> dict[str, Any]:
    from pathlib import Path as RuntimePath

    import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847
    import qmt_roll_official_candidate_stage819_30w_config as cfg819
    import qmt_roll_official_candidate_stage847_c9_config as cfg847
    import qmt_roll_official_stage78_config as cfg78
    from run_qmt_roll_backtest import build_roll_setting
    from run_qmt_roll_stage310_stage78_1_drawdown_gate_engine_validation import _pressure040_overrides
    from run_qmt_roll_stage318_supply_demand_headwind_engine_validation import _supply_demand_headwind_overrides

    fake_universe = RuntimePath("/FROZEN/static18_plus_fu.csv")
    fake_eligibility = RuntimePath("/FROZEN/old_ai_eligibility.csv")
    base819 = cfg819._build_official_candidate_stage819_30w_overrides(fake_universe, fake_eligibility)
    module_cfg = s847.s827.s825.stage819_cfg
    original_builder = module_cfg.build_official_candidate_stage819_30w_overrides
    try:
        module_cfg.build_official_candidate_stage819_30w_overrides = lambda: dict(base819)
        profile = s847._c9_profile({"vt_symbols": ["rb2401.SHFE"]})
    finally:
        module_cfg.build_official_candidate_stage819_30w_overrides = original_builder

    spec = profile["spec"]
    c3_overrides = {
        **cfg78._build_official_stage78_overrides(fake_universe, fake_eligibility),
        "trade_start_date": "2018-01-01",
        **_pressure040_overrides(),
        **_supply_demand_headwind_overrides(),
    }
    setting = build_roll_setting({}, strategy_overrides=c3_overrides)
    setting["capital_base"] = spec.capital.c3_capital
    setting.update(spec.overrides)
    live = cfg847._build_official_candidate_stage847_c9_overrides(fake_universe, fake_eligibility)
    live.update(
        {
            "account_capital": 150_000.0,
            "c3_capital": 150_000.0,
            "ai_product_pool_eligibility_path": "/FROZEN/current_live_ai_eligibility.csv",
        }
    )
    setting.update(live)

    relevant_keys = (
        "ma_short",
        "ma_mid",
        "ma_long",
        "ma_extra_long",
        "long_entry_enabled",
        "short_entry_enabled",
        "rollover_reopen_enabled",
        "reverse_on_opposite_signal",
        "ma5_extreme_filter_enabled",
        "ma5_extreme_compare_days",
        "ma5_angle_reversal_filter_enabled",
        "ma5_angle_reversal_lookback_days",
        "ma5_angle_reversal_angle_threshold_deg",
        "short_ma5_slope_filter_enabled",
        "wick_chop_filter_enabled",
        "wick_chop_filter_lookback",
        "wick_chop_filter_max_days",
        "enable_rsi_filter",
        "rsi_length",
        "donchian_entry_period",
        "array_manager_size_floor",
        "research_exact_array_manager_size",
        "enable_ai_product_pool_filter",
        "max_concurrent_positions",
        "account_capital",
        "c3_capital",
    )
    strategy_cls = profile["strategy_cls"]
    engine_cls = s847.Stage847StopRetryEngine

    def owner(cls: type, name: str) -> str:
        item = next(base for base in cls.mro() if name in base.__dict__)
        return f"{item.__module__}.{item.__name__}"

    actual = {key: setting.get(key) for key in relevant_keys}
    frozen = DirectionSettings()
    expected = {
        **{key: value for key, value in asdict(frozen).items() if key != "exact_am_size"},
        "array_manager_size_floor": 40,
        "research_exact_array_manager_size": frozen.exact_am_size,
        "enable_ai_product_pool_filter": True,
        "max_concurrent_positions": 4,
        "account_capital": 150_000.0,
        "c3_capital": 150_000.0,
    }
    expected = {key: expected[key] for key in relevant_keys}
    strategy_mro = [item.__name__ for item in strategy_cls.mro()[:6]]
    engine_mro = [item.__name__ for item in engine_cls.mro()[:5]]
    expected_strategy_mro = [
        "QmtRollPortfolioStrategyStage847C9StopRetry",
        "QmtRollPortfolioStrategyStage830C2Broker10MarginCap",
        "QmtRollPortfolioStrategyStage827C2",
        "QmtRollPortfolioStrategyLongTighterInitialStop",
        "QmtRollPortfolioStrategyExactAm",
        "QmtRollPortfolioStrategy",
    ]
    expected_engine_mro = [
        "Stage847StopRetryEngine",
        "Stage840IntradayEngine",
        "Stage827IntradayC2Engine",
        "ConfirmedDailyNextRealOpenEngine",
        "SameDayCloseBacktestingEngine",
    ]
    owners = {
        "engine_new_bars": owner(engine_cls, "new_bars"),
        "strategy_rollover_reopen_allowed": owner(strategy_cls, "_rollover_reopen_allowed"),
        "strategy_passes_entry_filters": owner(strategy_cls, "_passes_entry_filters"),
    }
    expected_owners = {
        "engine_new_bars": (
            "analyze_qmt_roll_stage502_confirmed_daily_next_real_open_replay."
            "ConfirmedDailyNextRealOpenEngine"
        ),
        "strategy_rollover_reopen_allowed": "qmt_roll_portfolio_strategy.QmtRollPortfolioStrategy",
        "strategy_passes_entry_filters": "qmt_roll_portfolio_strategy.QmtRollPortfolioStrategy",
    }
    return {
        "profile": profile["profile"],
        "strategy_class": f"{strategy_cls.__module__}.{strategy_cls.__name__}",
        "actual_settings": actual,
        "expected_settings": expected,
        "settings_match": actual == expected,
        "strategy_mro": strategy_mro,
        "expected_strategy_mro": expected_strategy_mro,
        "strategy_mro_match": strategy_mro == expected_strategy_mro,
        "engine_mro": engine_mro,
        "expected_engine_mro": expected_engine_mro,
        "engine_mro_match": engine_mro == expected_engine_mro,
        "owners": owners,
        "expected_owners": expected_owners,
        "owners_match": owners == expected_owners,
        "source_files": {
            "new_bars": str(inspect.getsourcefile(engine_cls.new_bars) or ""),
            "rollover_reopen_allowed": str(inspect.getsourcefile(strategy_cls._rollover_reopen_allowed) or ""),
        },
        "runtime_identity_pass": bool(
            actual == expected
            and strategy_mro == expected_strategy_mro
            and engine_mro == expected_engine_mro
            and owners == expected_owners
        ),
    }


def _normalise_inputs(
    panel_path: Path,
    formal_plan_path: Path,
    expiry_paths_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    panel = pd.read_csv(panel_path, encoding="utf-8-sig")
    required_panel = {"query_date", "product_vt_symbol", "main_contract_vt"}
    if not required_panel.issubset(panel.columns):
        raise ValueError(f"panel_columns_missing:{sorted(required_panel - set(panel.columns))}")
    panel["query_date"] = pd.to_datetime(panel["query_date"], errors="raise").dt.normalize()
    panel["product_vt_symbol"] = panel["product_vt_symbol"].astype(str)
    panel["main_contract_vt"] = panel["main_contract_vt"].astype(str)

    formal = pd.read_csv(formal_plan_path, encoding="utf-8-sig")
    required_formal = {"test_eval_date", "product_vt_symbol"}
    if not required_formal.issubset(formal.columns):
        raise ValueError(f"formal_columns_missing:{sorted(required_formal - set(formal.columns))}")
    formal["test_eval_date"] = pd.to_datetime(formal["test_eval_date"], errors="raise").dt.normalize()
    formal["product_vt_symbol"] = formal["product_vt_symbol"].astype(str)

    expiry = pd.read_csv(
        expiry_paths_path,
        usecols=["query_date", "product_vt_symbol", "main_contract_vt"],
        encoding="utf-8-sig",
    )
    expiry["query_date"] = pd.to_datetime(expiry["query_date"], errors="raise").dt.normalize()
    expiry["product_vt_symbol"] = expiry["product_vt_symbol"].astype(str)
    expiry["main_contract_vt"] = expiry["main_contract_vt"].astype(str)
    return panel, formal, expiry


def _identity_set(frame: pd.DataFrame) -> set[tuple[pd.Timestamp, str, str]]:
    return set(
        frame[["query_date", "product_vt_symbol", "main_contract_vt"]]
        .itertuples(index=False, name=None)
    )


def _empty_direction_row(row: Any, partition: str, reason: str, technical_error: str = "") -> dict[str, Any]:
    return {
        "query_date": pd.Timestamp(row.query_date).date().isoformat(),
        "product_vt_symbol": str(row.product_vt_symbol),
        "main_contract_vt": str(row.main_contract_vt),
        "partition": partition,
        "proxy_observable": False,
        "proxy_unobservable_reason": reason,
        "direction_proxy": None,
        "long_allowed": None,
        "short_allowed": None,
        "formula_mismatch": False,
        "post_query_bar_usage_count": 0,
        "flat_fill_bar_usage_count": 0,
        "technical_error": technical_error,
    }


def _stream_query_evaluations(
    path: Path,
    vt_symbol: str,
    query_dates: list[pd.Timestamp],
) -> tuple[dict[pd.Timestamp, dict[str, Any] | DirectionProxyError], dict[str, Any]]:
    queries = sorted(set(pd.Timestamp(item).normalize() for item in query_dates))
    evaluations: dict[pd.Timestamp, dict[str, Any] | DirectionProxyError] = {}
    history_rows: deque[dict[str, Any]] = deque(maxlen=DirectionSettings().exact_am_size)
    available_count = 0
    ohlc_numeric_parse_count = 0
    future_ohlc_field_access_count = 0
    future_ohlc_numeric_parse_count = 0
    date_only_future_row_count = 0
    query_index = 0
    previous_source_date: pd.Timestamp | None = None
    first_ingested_date: pd.Timestamp | None = None
    last_ingested_date: pd.Timestamp | None = None

    def evaluate(query: pd.Timestamp) -> None:
        frame = pd.DataFrame(list(history_rows), columns=["trade_date", "open", "high", "low", "close"])
        frame.attrs["vt_symbol"] = vt_symbol
        try:
            result = evaluate_direction_proxy(frame, query)
            result["available_bar_count"] = available_count
            evaluations[query] = result
        except DirectionProxyError as exc:
            evaluations[query] = exc

    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as handle:
        header_line = handle.readline()
        fieldnames = next(csv.reader([header_line])) if header_line else []
        required = {"trade_date", "open", "high", "low", "close"}
        missing = sorted(required - set(fieldnames))
        if missing:
            raise DirectionProxyError(f"raw_bar_columns_missing:{vt_symbol}:{','.join(missing)}")
        if not fieldnames or fieldnames[0] != "trade_date":
            raise DirectionProxyError(f"raw_bar_trade_date_not_first:{vt_symbol}")
        field_index = {name: index for index, name in enumerate(fieldnames)}

        for source_line in handle:
            date_token = source_line.split(",", 1)[0].strip().strip('"')
            source_date = pd.to_datetime(date_token, errors="coerce")
            if pd.isna(source_date):
                raise DirectionProxyError(f"raw_bar_date_invalid:{vt_symbol}")
            source_date = pd.Timestamp(source_date).normalize()
            if previous_source_date is not None and source_date <= previous_source_date:
                reason = "raw_bar_date_duplicate" if source_date == previous_source_date else "raw_bar_date_not_sorted"
                raise DirectionProxyError(f"{reason}:{vt_symbol}")
            previous_source_date = source_date

            while query_index < len(queries) and queries[query_index] < source_date:
                evaluate(queries[query_index])
                query_index += 1
            if query_index >= len(queries):
                date_only_future_row_count += 1
                break

            if source_date > queries[query_index]:
                future_ohlc_field_access_count += 1
                raise DirectionProxyError(
                    f"future_ohlc_field_access:{vt_symbol}:{source_date.date().isoformat()}"
                )
            source_values = next(csv.reader([source_line]))
            numeric: dict[str, float] = {}
            for column in ("open", "high", "low", "close"):
                if source_date > queries[query_index]:
                    future_ohlc_numeric_parse_count += 1
                    raise DirectionProxyError(
                        f"future_ohlc_numeric_parse:{vt_symbol}:{source_date.date().isoformat()}"
                    )
                numeric[column] = float(source_values[field_index[column]])
                ohlc_numeric_parse_count += 1
            history_rows.append({"trade_date": source_date, **numeric})
            available_count += 1
            first_ingested_date = first_ingested_date or source_date
            last_ingested_date = source_date

            if queries[query_index] == source_date:
                evaluate(queries[query_index])
                query_index += 1

    while query_index < len(queries):
        evaluate(queries[query_index])
        query_index += 1

    return evaluations, {
        "ingested_row_count": available_count,
        "ohlc_numeric_parse_count": ohlc_numeric_parse_count,
        "future_ohlc_field_access_count": future_ohlc_field_access_count,
        "future_ohlc_numeric_parse_count": future_ohlc_numeric_parse_count,
        "date_only_future_row_count": date_only_future_row_count,
        "query_evaluation_count": len(evaluations),
        "first_ingested_date": first_ingested_date.date().isoformat() if first_ingested_date is not None else "",
        "last_ingested_date": last_ingested_date.date().isoformat() if last_ingested_date is not None else "",
    }


def _evaluate_panel(
    model_panel: pd.DataFrame,
    development_dates: set[pd.Timestamp],
    source_manifest_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    payload = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_rows = payload.get("source_files", [])
    source_by_vt: dict[str, dict[str, Any]] = {}
    manifest_errors = 0
    for entry in source_rows:
        try:
            vt_symbol = _tq_to_vt_symbol(str(entry.get("tq_symbol", "")))
        except ValueError:
            manifest_errors += 1
            continue
        if vt_symbol in source_by_vt:
            manifest_errors += 1
        source_by_vt[vt_symbol] = dict(entry)

    output_rows: list[dict[str, Any]] = []
    source_audit: list[dict[str, Any]] = []
    stats = {
        "source_manifest_parse_error_count": manifest_errors,
        "source_contract_missing_count": 0,
        "source_sha_mismatch_count": 0,
        "source_sha_after_mismatch_count": 0,
        "source_read_error_count": 0,
        "used_ohlc_invalid_count": 0,
        "direction_formula_error_count": 0,
        "future_ohlc_field_access_count": 0,
        "future_ohlc_numeric_parse_count": 0,
    }

    for vt_symbol, group in model_panel.groupby("main_contract_vt", sort=True):
        entry = source_by_vt.get(str(vt_symbol))
        partition_by_date = {
            pd.Timestamp(date): "development" if pd.Timestamp(date) in development_dates else "inference_only"
            for date in group["query_date"].unique()
        }
        if entry is None:
            stats["source_contract_missing_count"] += 1
            for row in group.itertuples(index=False):
                output_rows.append(
                    _empty_direction_row(
                        row,
                        partition_by_date[pd.Timestamp(row.query_date)],
                        "source_contract_missing",
                        "source_contract_missing",
                    )
                )
            source_audit.append(
                {
                    "main_contract_vt": str(vt_symbol),
                    "source_resolved": False,
                    "query_row_count": int(len(group)),
                    "technical_error": "source_contract_missing",
                }
            )
            continue

        path = Path(str(entry.get("path", "")))
        expected_sha = str(entry.get("sha256", ""))
        base_audit = {
            "main_contract_vt": str(vt_symbol),
            "tq_symbol": str(entry.get("tq_symbol", "")),
            "source_kind": str(entry.get("source_kind", "")),
            "source_path": str(path),
            "source_resolved": True,
            "query_row_count": int(len(group)),
            "expected_sha256": expected_sha,
        }
        if not path.is_file():
            stats["source_contract_missing_count"] += 1
            for row in group.itertuples(index=False):
                output_rows.append(
                    _empty_direction_row(
                        row,
                        partition_by_date[pd.Timestamp(row.query_date)],
                        "source_file_missing",
                        "source_file_missing",
                    )
                )
            source_audit.append({**base_audit, "source_resolved": False, "technical_error": "source_file_missing"})
            continue

        before_sha = sha256_file(path)
        if before_sha != expected_sha:
            stats["source_sha_mismatch_count"] += 1
            for row in group.itertuples(index=False):
                output_rows.append(
                    _empty_direction_row(
                        row,
                        partition_by_date[pd.Timestamp(row.query_date)],
                        "source_sha_mismatch",
                        "source_sha_mismatch",
                    )
                )
            source_audit.append(
                {**base_audit, "source_sha256_before": before_sha, "technical_error": "source_sha_mismatch"}
            )
            continue

        try:
            evaluations, stream_diagnostics = _stream_query_evaluations(
                path,
                str(vt_symbol),
                [pd.Timestamp(item) for item in group["query_date"].tolist()],
            )
        except Exception as exc:
            stats["source_read_error_count"] += 1
            error = f"{type(exc).__name__}:{exc}"
            for row in group.itertuples(index=False):
                output_rows.append(
                    _empty_direction_row(
                        row,
                        partition_by_date[pd.Timestamp(row.query_date)],
                        "source_read_error",
                        error,
                    )
                )
            source_audit.append(
                {**base_audit, "source_sha256_before": before_sha, "technical_error": error}
            )
            continue

        stats["future_ohlc_numeric_parse_count"] += int(
            stream_diagnostics["future_ohlc_numeric_parse_count"]
        )
        stats["future_ohlc_field_access_count"] += int(
            stream_diagnostics["future_ohlc_field_access_count"]
        )
        for row in group.sort_values("query_date", kind="mergesort").itertuples(index=False):
            partition = partition_by_date[pd.Timestamp(row.query_date)]
            result_or_error = evaluations[pd.Timestamp(row.query_date)]
            if not isinstance(result_or_error, DirectionProxyError):
                result = result_or_error
                output_rows.append(
                    {
                        "query_date": pd.Timestamp(row.query_date).date().isoformat(),
                        "product_vt_symbol": str(row.product_vt_symbol),
                        "main_contract_vt": str(row.main_contract_vt),
                        "partition": partition,
                        **result,
                        "technical_error": "",
                    }
                )
            else:
                error = str(result_or_error)
                if error.startswith("used_ohlc_invalid"):
                    stats["used_ohlc_invalid_count"] += 1
                else:
                    stats["direction_formula_error_count"] += 1
                output_rows.append(_empty_direction_row(row, partition, "technical_error", error))

        after_sha = sha256_file(path)
        if after_sha != before_sha:
            stats["source_sha_after_mismatch_count"] += 1
        source_audit.append(
            {
                **base_audit,
                "source_sha256_before": before_sha,
                "source_sha256_after": after_sha,
                "source_sha_match": before_sha == expected_sha and after_sha == expected_sha,
                **stream_diagnostics,
                "technical_error": "",
            }
        )

    audit = pd.DataFrame(output_rows).sort_values(
        ["query_date", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)
    return audit, pd.DataFrame(source_audit).sort_values("main_contract_vt", kind="mergesort"), stats


def _qid_diagnostics(
    audit: pd.DataFrame,
    formal_dates: set[pd.Timestamp],
) -> pd.DataFrame:
    frame = audit.copy()
    frame["query_date"] = pd.to_datetime(frame["query_date"], errors="raise").dt.normalize()
    frame["observable"] = frame["proxy_observable"].fillna(False).astype(bool)
    direction = pd.to_numeric(frame["direction_proxy"], errors="coerce")
    frame["long_count"] = (frame["observable"] & direction.eq(1)).astype(int)
    frame["short_count"] = (frame["observable"] & direction.eq(-1)).astype(int)
    frame["neutral_count"] = (frame["observable"] & direction.eq(0)).astype(int)
    frame["unobservable_count"] = (~frame["observable"]).astype(int)
    rows: list[dict[str, Any]] = []
    for date, group in frame.groupby("query_date", sort=True):
        partitions = sorted(set(group["partition"].astype(str)))
        rows.append(
            {
                "query_date": pd.Timestamp(date).date().isoformat(),
                "partition": partitions[0] if len(partitions) == 1 else "mixed_error",
                "total_rows": int(len(group)),
                "observable_rows": int(group["observable"].sum()),
                "unobservable_rows": int(group["unobservable_count"].sum()),
                "long_rows": int(group["long_count"].sum()),
                "short_rows": int(group["short_count"].sum()),
                "neutral_rows": int(group["neutral_count"].sum()),
                "active_direction_rows": int(group["long_count"].sum() + group["short_count"].sum()),
                "is_formal_action_date": bool(pd.Timestamp(date) in formal_dates),
            }
        )
    return pd.DataFrame(rows)


def _add_gate(gates: list[dict[str, Any]], name: str, passed: bool, observed: Any, expected: str) -> None:
    gates.append(
        {
            "gate": name,
            "passed": bool(passed),
            "observed": _json_safe(observed),
            "expected": expected,
        }
    )


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_bundle(
    output_dir: Path,
    *,
    audit: pd.DataFrame,
    qids: pd.DataFrame,
    costs: pd.DataFrame,
    source_audit: pd.DataFrame,
    summary: dict[str, Any],
    input_identities: dict[str, Any],
    upstream_verification: dict[str, Any],
    authorization_receipt: Mapping[str, Any] | None,
) -> None:
    if output_dir.exists():
        raise FileExistsError(f"output_already_exists:{output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_dir.parent / f".{output_dir.name}.tmp-{uuid.uuid4().hex}"
    temporary.mkdir(parents=False, exist_ok=False)
    try:
        audit.to_csv(temporary / "direction_proxy_audit.csv.gz", index=False, encoding="utf-8-sig")
        qids.to_csv(temporary / "qid_direction_diagnostics.csv.gz", index=False, encoding="utf-8-sig")
        costs.to_csv(temporary / "cost_metadata.csv", index=False, encoding="utf-8-sig")
        source_audit.to_csv(temporary / "source_contract_audit.csv.gz", index=False, encoding="utf-8-sig")
        _write_json(temporary / "summary.json", summary)
        _write_json(temporary / "input_identities.json", input_identities)
        _write_json(temporary / "upstream_verification.json", upstream_verification)
        if authorization_receipt is not None:
            _write_json(temporary / "authorization_receipt.json", dict(authorization_receipt))

        report_lines = [
            "# Stage001方向代理无标签资格报告",
            "",
            f"- 决策：`{summary['decision']}`",
            f"- 硬门失败数：`{summary['gate_fail_count']}`",
            f"- 模型排名层：`{summary['model_row_count']}`行 / `{summary['model_qid_count']}`个qid / `{summary['model_product_count']}`个产品",
            f"- 可观测：`{summary['proxy_observable_row_count']}`；不可观测：`{summary['proxy_unobservable_row_count']}`",
            f"- long/short/neutral：`{summary['direction_long_count']}` / `{summary['direction_short_count']}` / `{summary['direction_neutral_count']}`",
            f"- 公式不一致：`{summary['formula_mismatch_count']}`；post-query bar使用：`{summary['post_query_bar_usage_count']}`；平填AM bar使用：`{summary['flat_fill_bar_usage_count']}`",
            f"- future OHLC字段访问/数值解析：`{summary['future_ohlc_field_access_count']}` / `{summary['future_ohlc_numeric_parse_count']}`",
            f"- 成本来源：显式`{summary['explicit_cost_product_count']}` / 研究fallback`{summary['fallback_cost_product_count']}`",
            "- 本阶段未来close、收益、标签、模型、回测、holdout、CTP、订单和生产写入均为0。",
            "",
            "## 硬门",
            "",
        ]
        for gate in summary["gates"]:
            report_lines.append(
                f"- {'PASS' if gate['passed'] else 'FAIL'} `{gate['gate']}`：observed={gate['observed']}；expected={gate['expected']}"
            )
        report_lines.extend(
            [
                "",
                "## 口径",
                "",
                "- `counterfactual_rollover_continuation_direction_proxy`不是实际信号、持仓、换月动作或成交。",
                "- 成本字段是`research_code_defined_cost_proxy`，不是历史真实费用或生产成交成本。",
                "- 通过只允许另行预注册未来标签，不代表XGBoost有效、收益提升或回撤下降。",
            ]
        )
        (temporary / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

        artifacts: dict[str, Any] = {}
        for path in sorted(temporary.iterdir()):
            if path.name == "artifact_manifest.json":
                continue
            artifacts[path.name] = {
                "path": path.name,
                "sha256": sha256_file(path),
                "size": int(path.stat().st_size),
            }
        _write_json(
            temporary / "artifact_manifest.json",
            {
                "line_id": LINE_ID,
                "stage": STAGE,
                "artifacts": artifacts,
            },
        )
        os.replace(temporary, output_dir)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def verify_bundle(output_dir: Path) -> dict[str, Any]:
    manifest_path = output_dir / "artifact_manifest.json"
    errors: list[str] = []
    checked = 0
    if not manifest_path.is_file():
        return {"error_count": 1, "errors": ["artifact_manifest_missing"], "checked_count": 0}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error_count": 1, "errors": [f"artifact_manifest_invalid:{exc}"], "checked_count": 0}
    for name, identity in sorted(manifest.get("artifacts", {}).items()):
        path = output_dir / str(identity.get("path", name))
        checked += 1
        if not path.is_file():
            errors.append(f"artifact_missing:{name}")
            continue
        if int(path.stat().st_size) != int(identity.get("size", -1)):
            errors.append(f"artifact_size_mismatch:{name}")
        if sha256_file(path) != str(identity.get("sha256", "")):
            errors.append(f"artifact_sha_mismatch:{name}")
    return {"error_count": len(errors), "errors": errors, "checked_count": checked}


def _run_qualification_core(
    *,
    panel_path: Path,
    formal_plan_path: Path,
    source_manifest_path: Path,
    product_metadata_path: Path,
    expiry_paths_path: Path,
    output_dir: Path,
    contract: QualificationContract,
    rates: Mapping[str, float],
    slippages: Mapping[str, float],
    sizes: Mapping[str, int],
    priceticks: Mapping[str, float],
    extra_input_paths: Mapping[str, Path] | None = None,
    expected_input_sha256: Mapping[str, str] | None = None,
    authorization_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    direct_paths = {
        "panel": Path(panel_path),
        "formal_plan": Path(formal_plan_path),
        "source_manifest": Path(source_manifest_path),
        "product_metadata": Path(product_metadata_path),
        "expiry_paths": Path(expiry_paths_path),
        **{key: Path(value) for key, value in (extra_input_paths or {}).items()},
    }
    input_identities_before = {key: _file_identity(path) for key, path in direct_paths.items()}
    expected_sha = dict(expected_input_sha256 or {})
    input_sha_mismatches = {
        key: {
            "expected": expected,
            "actual": input_identities_before.get(key, {}).get("sha256"),
        }
        for key, expected in expected_sha.items()
        if input_identities_before.get(key, {}).get("sha256") != expected
    }

    panel, formal, expiry = _normalise_inputs(panel_path, formal_plan_path, expiry_paths_path)
    duplicate_panel_count = int(panel.duplicated(["query_date", "product_vt_symbol"]).sum())
    fixed_fu = panel.loc[panel["product_vt_symbol"].eq(FIXED_FU)].copy()
    model_panel = panel.loc[~panel["product_vt_symbol"].eq(FIXED_FU)].copy()
    model_panel = model_panel.sort_values(["query_date", "product_vt_symbol"], kind="mergesort").reset_index(drop=True)
    widths = model_panel.groupby("query_date").size()

    expiry_non_fu = expiry.loc[~expiry["product_vt_symbol"].eq(FIXED_FU)].copy()
    development_dates = set(pd.Timestamp(item) for item in expiry_non_fu["query_date"].unique())
    development = model_panel.loc[model_panel["query_date"].isin(development_dates)].copy()
    inference = model_panel.loc[~model_panel["query_date"].isin(development_dates)].copy()
    development_identity_delta = len(_identity_set(development) ^ _identity_set(expiry_non_fu))
    expiry_duplicate_count = int(expiry_non_fu.duplicated(["query_date", "product_vt_symbol"]).sum())

    model_date_product = set(
        model_panel[["query_date", "product_vt_symbol"]].itertuples(index=False, name=None)
    )
    formal_date_product = set(
        formal[["test_eval_date", "product_vt_symbol"]].itertuples(index=False, name=None)
    )
    formal_identity_missing_count = len(formal_date_product - model_date_product)
    formal_dates = set(pd.Timestamp(item) for item in formal["test_eval_date"].unique())
    formal_development_dates = formal_dates & development_dates
    formal_inference_dates = formal_dates - development_dates

    audit, source_audit, source_stats = _evaluate_panel(
        model_panel,
        development_dates,
        Path(source_manifest_path),
    )
    qids = _qid_diagnostics(audit, formal_dates)

    metadata = pd.read_csv(product_metadata_path, encoding="utf-8-sig")
    cost_error = ""
    try:
        costs = build_cost_metadata(
            sorted(model_panel["product_vt_symbol"].unique()),
            metadata,
            rates=rates,
            slippages=slippages,
            sizes=sizes,
            priceticks=priceticks,
        )
    except DirectionProxyError as exc:
        cost_error = str(exc)
        costs = pd.DataFrame(
            columns=[
                "product_vt_symbol",
                "cost_contract_name",
                "cost_source",
                "rate",
                "slippage",
                "size",
                "pricetick",
            ]
        )

    runtime = _runtime_identity() if contract.require_runtime_identity else {"runtime_identity_pass": True, "skipped_for_fixture": True}

    observable = audit["proxy_observable"].fillna(False).astype(bool)
    direction = pd.to_numeric(audit["direction_proxy"], errors="coerce")
    formula_mismatch_count = int(audit["formula_mismatch"].fillna(False).astype(bool).sum())
    post_query_count = int(pd.to_numeric(audit["post_query_bar_usage_count"], errors="coerce").fillna(0).sum())
    flat_fill_count = int(pd.to_numeric(audit["flat_fill_bar_usage_count"], errors="coerce").fillna(0).sum())
    technical_error_count = int(audit["technical_error"].fillna("").astype(str).ne("").sum())

    development_qids = qids.loc[qids["partition"].eq("development")].copy()
    formal_qids = qids.loc[qids["is_formal_action_date"].astype(bool)].copy()
    active_development_qids = int(development_qids["active_direction_rows"].gt(0).sum())
    audit_dates = pd.to_datetime(audit["query_date"], errors="raise")
    development_mask = audit["partition"].eq("development") & observable
    yearly_direction: dict[str, dict[str, int]] = {}
    for year in contract.required_direction_years:
        year_mask = development_mask & audit_dates.dt.year.eq(year)
        yearly_direction[str(year)] = {
            "long": int((year_mask & direction.eq(1)).sum()),
            "short": int((year_mask & direction.eq(-1)).sum()),
        }

    explicit_cost_count = int(costs.get("cost_source", pd.Series(dtype=str)).eq("formal_explicit_legacy_universe").sum())
    fallback_cost_count = int(costs.get("cost_source", pd.Series(dtype=str)).eq("research_metadata_fallback").sum())
    forbidden = {key: 0 for key in FORBIDDEN_COUNTERS}
    input_identities_after = {key: _file_identity(path) for key, path in direct_paths.items()}
    identity_fields = ("path", "sha256", "size", "mtime_ns")
    input_identity_drift = {
        key: {
            "changed_fields": [
                field
                for field in identity_fields
                if input_identities_before[key][field] != input_identities_after[key][field]
            ],
            "before": input_identities_before[key],
            "after": input_identities_after[key],
        }
        for key in sorted(direct_paths)
        if input_identities_before[key] != input_identities_after[key]
    }
    input_identities = {
        "before": input_identities_before,
        "after": input_identities_after,
        "drift": input_identity_drift,
    }

    gates: list[dict[str, Any]] = []
    _add_gate(
        gates,
        "input_identity_contract",
        not input_sha_mismatches and not input_identity_drift,
        {
            "expected_sha_mismatches": input_sha_mismatches,
            "run_identity_drift": input_identity_drift,
        },
        "all declared input SHA256 values match and every direct input is unchanged during the run",
    )
    panel_observed = {
        "rows": len(panel),
        "qids": panel["query_date"].nunique(),
        "products": panel["product_vt_symbol"].nunique(),
        "fixed_fu_rows": len(fixed_fu),
        "model_rows": len(model_panel),
        "model_qids": model_panel["query_date"].nunique(),
        "model_products": model_panel["product_vt_symbol"].nunique(),
        "width_min": int(widths.min()) if len(widths) else 0,
        "width_median": float(widths.median()) if len(widths) else 0.0,
        "width_max": int(widths.max()) if len(widths) else 0,
        "duplicate_panel_count": duplicate_panel_count,
    }
    panel_expected = {
        "rows": contract.expected_panel_rows,
        "qids": contract.expected_panel_qids,
        "products": contract.expected_panel_products,
        "fixed_fu_rows": contract.expected_fixed_fu_rows,
        "model_rows": contract.expected_model_rows,
        "model_qids": contract.expected_model_qids,
        "model_products": contract.expected_model_products,
        "width_min": contract.expected_qid_width_min,
        "width_median": contract.expected_qid_width_median,
        "width_max": contract.expected_qid_width_max,
        "duplicate_panel_count": 0,
    }
    _add_gate(gates, "model_scope_identity", panel_observed == panel_expected, panel_observed, str(panel_expected))

    development_observed = {
        "rows": len(development),
        "qids": development["query_date"].nunique(),
        "products": development["product_vt_symbol"].nunique(),
        "inference_rows": len(inference),
        "inference_qids": inference["query_date"].nunique(),
        "identity_delta": development_identity_delta,
        "expiry_duplicate_count": expiry_duplicate_count,
    }
    development_expected = {
        "rows": contract.expected_development_rows,
        "qids": contract.expected_development_qids,
        "products": contract.expected_development_products,
        "inference_rows": contract.expected_inference_rows,
        "inference_qids": contract.expected_inference_qids,
        "identity_delta": 0,
        "expiry_duplicate_count": 0,
    }
    _add_gate(
        gates,
        "development_identity",
        development_observed == development_expected,
        development_observed,
        str(development_expected),
    )
    _add_gate(
        gates,
        "formal_plan_identity",
        len(formal_dates) == contract.expected_formal_action_dates
        and len(formal_development_dates) == contract.expected_formal_development_dates
        and len(formal_inference_dates) == contract.expected_formal_inference_dates
        and formal_identity_missing_count == 0,
        {
            "dates": len(formal_dates),
            "development_dates": len(formal_development_dates),
            "inference_dates": len(formal_inference_dates),
            "missing_identity_count": formal_identity_missing_count,
        },
        (
            f"dates={contract.expected_formal_action_dates}, "
            f"development={contract.expected_formal_development_dates}, "
            f"inference={contract.expected_formal_inference_dates}, missing_identity_count=0"
        ),
    )
    _add_gate(
        gates,
        "runtime_identity",
        bool(runtime.get("runtime_identity_pass")),
        runtime,
        "frozen Stage847 strategy MRO, engine new_bars owner, and merged direction settings",
    )
    source_identity_pass = all(value == 0 for value in source_stats.values()) and technical_error_count == 0
    _add_gate(
        gates,
        "source_contract_identity",
        source_identity_pass,
        {**source_stats, "technical_error_row_count": technical_error_count},
        "all query contracts resolve uniquely; source SHA/read/OHLC errors=0",
    )
    _add_gate(
        gates,
        "ohlc_and_causality",
        post_query_count == 0 and flat_fill_count == 0,
        {"post_query_bar_usage_count": post_query_count, "flat_fill_bar_usage_count": flat_fill_count},
        "both counts=0",
    )
    _add_gate(
        gates,
        "formula_parity",
        formula_mismatch_count == 0,
        formula_mismatch_count,
        "0",
    )
    min_development_observable = int(development_qids["observable_rows"].min()) if len(development_qids) else 0
    _add_gate(
        gates,
        "development_qid_observable_width",
        len(development_qids) == contract.expected_development_qids
        and min_development_observable >= contract.min_observable_per_development_qid,
        {"qid_count": len(development_qids), "min_observable_rows": min_development_observable},
        (
            f"qid_count={contract.expected_development_qids}, "
            f"min_observable_rows>={contract.min_observable_per_development_qid}"
        ),
    )
    min_formal_observable = int(formal_qids["observable_rows"].min()) if len(formal_qids) else 0
    min_formal_active = int(formal_qids["active_direction_rows"].min()) if len(formal_qids) else 0
    _add_gate(
        gates,
        "formal_action_direction_coverage",
        len(formal_qids) == contract.expected_formal_action_dates
        and min_formal_observable >= contract.min_observable_per_development_qid
        and min_formal_active >= 1,
        {
            "date_count": len(formal_qids),
            "min_observable_rows": min_formal_observable,
            "min_active_direction_rows": min_formal_active,
        },
        (
            f"date_count={contract.expected_formal_action_dates}, "
            f"min_observable_rows>={contract.min_observable_per_development_qid}, min_active_direction_rows>=1"
        ),
    )
    yearly_pass = all(item["long"] > 0 and item["short"] > 0 for item in yearly_direction.values())
    _add_gate(
        gates,
        "direction_non_degenerate",
        active_development_qids >= contract.min_active_development_qids and yearly_pass,
        {"active_development_qids": active_development_qids, "yearly_direction": yearly_direction},
        (
            f"active_development_qids>={contract.min_active_development_qids}; "
            "each required year has long>0 and short>0"
        ),
    )
    _add_gate(
        gates,
        "cost_metadata_contract",
        not cost_error
        and len(costs) == contract.expected_model_products
        and explicit_cost_count == contract.expected_explicit_cost_products
        and fallback_cost_count == contract.expected_fallback_cost_products,
        {
            "rows": len(costs),
            "explicit": explicit_cost_count,
            "fallback": fallback_cost_count,
            "error": cost_error,
        },
        (
            f"rows={contract.expected_model_products}, explicit={contract.expected_explicit_cost_products}, "
            f"fallback={contract.expected_fallback_cost_products}, error empty"
        ),
    )
    _add_gate(
        gates,
        "forbidden_operation_zero",
        all(value == 0 for value in forbidden.values()),
        forbidden,
        "all forbidden operation counters=0",
    )

    failed_gates = [str(gate["gate"]) for gate in gates if not gate["passed"]]
    summary: dict[str, Any] = {
        "line_id": LINE_ID,
        "stage": STAGE,
        "generated_at": datetime.now().astimezone().isoformat(),
        "decision": PASS_DECISION if not failed_gates else FAIL_DECISION,
        "gate_fail_count": len(failed_gates),
        "failed_gates": failed_gates,
        "gates": gates,
        "panel_row_count": int(len(panel)),
        "model_row_count": int(len(model_panel)),
        "model_qid_count": int(model_panel["query_date"].nunique()),
        "model_product_count": int(model_panel["product_vt_symbol"].nunique()),
        "development_row_count": int(len(development)),
        "development_qid_count": int(development["query_date"].nunique()),
        "inference_only_row_count": int(len(inference)),
        "inference_only_qid_count": int(inference["query_date"].nunique()),
        "proxy_observable_row_count": int(observable.sum()),
        "proxy_unobservable_row_count": int((~observable).sum()),
        "direction_long_count": int((observable & direction.eq(1)).sum()),
        "direction_short_count": int((observable & direction.eq(-1)).sum()),
        "direction_neutral_count": int((observable & direction.eq(0)).sum()),
        "active_development_qid_count": active_development_qids,
        "yearly_direction_counts": yearly_direction,
        "formula_mismatch_count": formula_mismatch_count,
        "post_query_bar_usage_count": post_query_count,
        "flat_fill_bar_usage_count": flat_fill_count,
        "future_ohlc_numeric_parse_count": int(source_stats["future_ohlc_numeric_parse_count"]),
        "future_ohlc_field_access_count": int(source_stats["future_ohlc_field_access_count"]),
        "technical_error_row_count": technical_error_count,
        "source_contract_count": int(model_panel["main_contract_vt"].nunique()),
        "explicit_cost_product_count": explicit_cost_count,
        "fallback_cost_product_count": fallback_cost_count,
        "cost_contract_name": "research_code_defined_cost_proxy",
        "historical_real_fee_claimed": False,
        "production_cost_claimed": False,
        "runtime_identity": runtime,
        "contract": asdict(contract),
        "input_identity_drift_count": len(input_identity_drift),
        **forbidden,
    }
    upstream_verification = {
        "input_sha_mismatches": input_sha_mismatches,
        "input_identity_drift": input_identity_drift,
        "source_stats": source_stats,
        "development_identity_delta": development_identity_delta,
        "formal_identity_missing_count": formal_identity_missing_count,
        "runtime_identity_pass": bool(runtime.get("runtime_identity_pass")),
    }
    _write_bundle(
        Path(output_dir),
        audit=audit,
        qids=qids,
        costs=costs,
        source_audit=source_audit,
        summary=summary,
        input_identities=input_identities,
        upstream_verification=upstream_verification,
        authorization_receipt=authorization_receipt,
    )
    return summary


def _require_fixture_path(fixture_root: Path, path: Path, label: str) -> Path:
    root = fixture_root.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"fixture_path_outside_root:{label}:{resolved}") from exc
    return resolved


def run_fixture_qualification(
    *,
    fixture_root: Path,
    panel_path: Path,
    formal_plan_path: Path,
    source_manifest_path: Path,
    product_metadata_path: Path,
    expiry_paths_path: Path,
    output_dir: Path,
    contract: QualificationContract,
    rates: Mapping[str, float],
    slippages: Mapping[str, float],
    sizes: Mapping[str, int],
    priceticks: Mapping[str, float],
) -> dict[str, Any]:
    root = Path(fixture_root).resolve()
    if not root.is_dir():
        raise ValueError(f"fixture_root_invalid:{root}")
    if contract.require_runtime_identity:
        raise ValueError("fixture_runtime_identity_must_be_disabled")

    direct_paths = {
        "panel": Path(panel_path),
        "formal_plan": Path(formal_plan_path),
        "source_manifest": Path(source_manifest_path),
        "product_metadata": Path(product_metadata_path),
        "expiry_paths": Path(expiry_paths_path),
        "output": Path(output_dir),
    }
    checked = {
        key: _require_fixture_path(root, path, key)
        for key, path in direct_paths.items()
    }
    source_payload = json.loads(checked["source_manifest"].read_text(encoding="utf-8"))
    for index, entry in enumerate(source_payload.get("source_files", [])):
        _require_fixture_path(root, Path(str(entry.get("path", ""))), f"source_file_{index}")

    return _run_qualification_core(
        panel_path=checked["panel"],
        formal_plan_path=checked["formal_plan"],
        source_manifest_path=checked["source_manifest"],
        product_metadata_path=checked["product_metadata"],
        expiry_paths_path=checked["expiry_paths"],
        output_dir=checked["output"],
        contract=contract,
        rates=rates,
        slippages=slippages,
        sizes=sizes,
        priceticks=priceticks,
        extra_input_paths=None,
        expected_input_sha256=None,
        authorization_receipt=None,
    )


def run_qualification(
    *,
    execution_lease: ExecutionLease,
    authorization_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(execution_lease, ExecutionLease):
        raise TypeError("production_execution_lease_required")
    _validate_authorization_scope(authorization_receipt)
    _validate_authorization_bindings(authorization_receipt, AUTHORIZATION_BINDING_PATHS)
    _validate_execution_lease(execution_lease, authorization_receipt)
    _claim_execution_lease(execution_lease)

    from qmt_universe import PRICETICKS, RATES, SIZES, SLIPPAGES

    authorization_input_paths = {
        f"authorization_{key}": value
        for key, value in AUTHORIZATION_BINDING_PATHS.items()
    }
    bound_sha256 = authorization_receipt.get("bound_sha256", {})
    authorization_expected_sha256 = {
        f"authorization_{key}": str(bound_sha256[key])
        for key in AUTHORIZATION_BINDING_PATHS
    }
    return _run_qualification_core(
        panel_path=PANEL_PATH,
        formal_plan_path=FORMAL_PLAN_PATH,
        source_manifest_path=SOURCE_MANIFEST_PATH,
        product_metadata_path=PRODUCT_METADATA_PATH,
        expiry_paths_path=EXPIRY_PATHS_PATH,
        output_dir=OUTPUT_DIR,
        contract=QualificationContract(),
        rates=RATES,
        slippages=SLIPPAGES,
        sizes=SIZES,
        priceticks=PRICETICKS,
        extra_input_paths={
            **PRODUCTION_EXTRA_INPUT_PATHS,
            **authorization_input_paths,
        },
        expected_input_sha256={
            **EXPECTED_INPUT_SHA256,
            **authorization_expected_sha256,
        },
        authorization_receipt=authorization_receipt,
    )


def _validate_authorization_bindings(
    payload: Mapping[str, Any],
    binding_paths: Mapping[str, Path],
) -> None:
    bound = payload.get("bound_sha256", {})
    mismatches: dict[str, dict[str, Any]] = {}
    for key, value in binding_paths.items():
        actual = sha256_file(Path(value))
        expected = str(bound.get(key, ""))
        if expected != actual:
            mismatches[key] = {"expected": expected or None, "actual": actual}
    if mismatches:
        raise ValueError(f"authorization_binding_mismatch:{mismatches}")


def _validate_authorization_scope(payload: Mapping[str, Any]) -> None:
    if payload.get("line_id") != LINE_ID or payload.get("stage") != STAGE:
        raise ValueError("authorization_scope_mismatch")
    if int(payload.get("allowed_run_count", 0)) != 1:
        raise ValueError("authorization_run_count_invalid")
    nonce = str(payload.get("nonce", "")).strip()
    if not nonce:
        raise ValueError("authorization_nonce_missing")


def _load_authorization(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _validate_authorization_scope(payload)
    _validate_authorization_bindings(payload, AUTHORIZATION_BINDING_PATHS)
    return payload


def _authorization_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        _json_safe(dict(payload)),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_exclusive_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(_json_safe(dict(payload)), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(path.parent)
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        path.unlink(missing_ok=True)
        raise


def _consume_execution_lease(authorization: Mapping[str, Any]) -> ExecutionLease:
    _validate_authorization_scope(authorization)
    consumed_at = datetime.now().astimezone().isoformat()
    lease = ExecutionLease(
        nonce=str(authorization["nonce"]),
        event_path=EXECUTION_EVENT_PATH.resolve(),
        consumed_at=consumed_at,
        lease_id=uuid.uuid4().hex,
        authorization_digest=_authorization_digest(authorization),
    )
    _write_exclusive_json(
        EXECUTION_EVENT_PATH,
        {
            "line_id": LINE_ID,
            "stage": STAGE,
            "nonce": lease.nonce,
            "lease_id": lease.lease_id,
            "authorization_digest": lease.authorization_digest,
            "started_at": lease.consumed_at,
            "status": "started",
        },
    )
    return lease


def _claim_execution_lease(lease: ExecutionLease) -> dict[str, Any]:
    claim = {
        "line_id": LINE_ID,
        "stage": STAGE,
        "nonce": lease.nonce,
        "lease_id": lease.lease_id,
        "authorization_digest": lease.authorization_digest,
        "event_path": str(lease.event_path),
        "claimed_at": datetime.now().astimezone().isoformat(),
        "status": "claimed",
    }
    _write_exclusive_json(EXECUTION_CLAIM_PATH, claim)
    return claim


def _validate_execution_lease(
    lease: ExecutionLease,
    authorization: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if lease.event_path.resolve() != EXECUTION_EVENT_PATH.resolve():
        raise ValueError("production_execution_event_path_mismatch")
    event = json.loads(EXECUTION_EVENT_PATH.read_text(encoding="utf-8"))
    expected = {
        "line_id": LINE_ID,
        "stage": STAGE,
        "nonce": lease.nonce,
        "lease_id": lease.lease_id,
        "authorization_digest": lease.authorization_digest,
        "started_at": lease.consumed_at,
        "status": "started",
    }
    mismatches = {
        key: {"expected": value, "actual": event.get(key)}
        for key, value in expected.items()
        if event.get(key) != value
    }
    if authorization is not None:
        authorization_mismatches = {
            "nonce": {
                "expected": lease.nonce,
                "actual": str(authorization.get("nonce", "")),
            },
            "authorization_digest": {
                "expected": lease.authorization_digest,
                "actual": _authorization_digest(authorization),
            },
        }
        mismatches.update(
            {
                key: value
                for key, value in authorization_mismatches.items()
                if value["expected"] != value["actual"]
            }
        )
    if mismatches:
        raise ValueError(f"production_execution_lease_mismatch:{mismatches}")
    return event


def _replace_execution_event(lease: ExecutionLease, updates: Mapping[str, Any]) -> None:
    event = _validate_execution_lease(lease)
    immutable = {
        "line_id",
        "stage",
        "nonce",
        "lease_id",
        "authorization_digest",
        "started_at",
    }
    invalid_updates = sorted(immutable & set(updates))
    if invalid_updates:
        raise ValueError(f"execution_event_immutable_update:{','.join(invalid_updates)}")

    payload = {**event, **dict(updates)}
    temporary = EXECUTION_EVENT_PATH.with_name(
        f".{EXECUTION_EVENT_PATH.name}.tmp-{uuid.uuid4().hex}"
    )
    try:
        _write_exclusive_json(temporary, payload)
        os.replace(temporary, EXECUTION_EVENT_PATH)
        _fsync_directory(EXECUTION_EVENT_PATH.parent)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _record_execution_failure(lease: ExecutionLease, error: BaseException) -> None:
    _replace_execution_event(
        lease,
        {
            "finished_at": datetime.now().astimezone().isoformat(),
            "status": "failed_exception",
            "error": f"{type(error).__name__}:{error}",
        },
    )


def _record_execution_completion(lease: ExecutionLease, summary: Mapping[str, Any]) -> None:
    _replace_execution_event(
        lease,
        {
            "finished_at": datetime.now().astimezone().isoformat(),
            "status": "completed",
            "decision": summary["decision"],
            "gate_fail_count": int(summary["gate_fail_count"]),
        },
    )


def _execute_production_qualification(
    authorization: Mapping[str, Any],
) -> dict[str, Any]:
    lease = _consume_execution_lease(authorization)
    try:
        if OUTPUT_DIR.exists():
            raise FileExistsError(f"output_already_exists:{OUTPUT_DIR}")
        summary = run_qualification(
            execution_lease=lease,
            authorization_receipt=authorization,
        )
    except Exception as exc:
        _record_execution_failure(lease, exc)
        raise
    _record_execution_completion(lease, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage001 direction proxy qualification")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    parser.add_argument("--authorization", type=Path)
    args = parser.parse_args()

    if args.verify_only:
        result = verify_bundle(OUTPUT_DIR)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        raise SystemExit(0 if result["error_count"] == 0 else 1)

    if args.authorization is None:
        raise SystemExit("--authorization is required for --run")
    authorization = _load_authorization(args.authorization)
    summary = _execute_production_qualification(authorization)
    print(json.dumps({"decision": summary["decision"], "gate_fail_count": summary["gate_fail_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
