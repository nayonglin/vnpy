#!/usr/bin/env python3
"""Stage001 current-C9 candidate component-risk sizing A/C experiment."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sqlite3
import sys
from typing import Any, Iterable, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
from sklearn.covariance import LedoitWolf


ROOT = Path(__file__).resolve().parents[4]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
SOURCE_TOOLS_DIR = ROOT / "research" / "lines" / "futures_trend_full_market_ai_filter_002risk" / "tools"
for item in (PORTFOLIO_DIR, SOURCE_TOOLS_DIR):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import stage006_current_ai_paired_bottom_veto_engine as s006  # noqa: E402
from main_contract_mapping import ALL_FUTURES_MAPPING_PATH  # noqa: E402
from qmt_roll_official_live_config import OFFICIAL_LIVE_AI_ELIGIBILITY_PATH  # noqa: E402


LINE_ID = "futures_trend_candidate_marginal_risk_contribution"
STAGE_ID = "stage001_candidate_marginal_risk_contribution_engine"
STAGE_LABEL = "Stage001"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"candidate_mrc_{STAGE_ID}"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / STAGE_ID
STAGES_DIR = LINE_DIR / "stages"
TOOL_PATH = Path(__file__).resolve()

CANARY_STARTS = ("2020-01", "2022-01", "2022-07", "2026-01")
REQUESTED_END = pd.Timestamp("2026-06-30")
CAPITAL = float(s006.base.CAPITAL)
BROKER10_MULTIPLIER = float(s006.base.s847.s513.s403.BROKER10_MULTIPLIER)
LOOKBACK_DAYS = 63
MIN_PRESERVED_VOLUME = 1
PANEL_START = pd.Timestamp("2018-01-01")

CURRENT_AI_PATH = Path(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH).resolve()
MAPPING_PATH = Path(ALL_FUTURES_MAPPING_PATH).resolve()
DATABASE_PATH = ROOT / ".vntrader" / "database.db"
STAGE137_SOURCE_MANIFEST_PATH = (
    ROOT
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_v2_optimization"
    / "outputs"
    / "stage137_current_c9_quality_one_way_satellite"
    / "source_manifest.csv"
)
STAGE462_DIR = (
    PORTFOLIO_DIR
    / "downloaded_futures"
    / "tqsdk_stage462_completed_preclose_full_dates_shard"
    / "SHFE"
)
STAGE462_PATHS = {
    "fu2005.SHFE": STAGE462_DIR / "fu2005_completed_minute_backtest.csv",
    "fu2009.SHFE": STAGE462_DIR / "fu2009_completed_minute_backtest.csv",
    "fu2605.SHFE": STAGE462_DIR / "fu2605_completed_minute_backtest.csv",
}

EXPECTED_SOURCE_SHA256 = {
    CURRENT_AI_PATH: "fc50e035cd66b65e94261ef70476747daa94ae73071d0f4d7206ff7b644271fc",
    MAPPING_PATH: "1b77f053991ea59c04f016439c17b9a0c00e70af140fb56abf1eaea68dd40428",
    DATABASE_PATH: "59f0bd364253d7ec029cc183d48f161c15b9ee9af01075956924b4dad958f723",
    STAGE462_PATHS["fu2005.SHFE"]: "f83b293716743fe06ca4bcaa469ab89b9fea12f6d1087eba90523b12a7592d45",
    STAGE462_PATHS["fu2009.SHFE"]: "cf8b826c0244776cd2684e04fe0b332da0d6df7710257ddadf89acadc18167d2",
    STAGE462_PATHS["fu2605.SHFE"]: "ecfb330c5b8b28cb11c39a3ed7b7175dbce16daf06d1786117deede30e7b3950",
}

PANEL_PATH = OUT / f"{OUTPUT_PREFIX}_actual_contract_returns_{MODEL_TAG}.csv"
SOURCE_MANIFEST_PATH = OUT / f"{OUTPUT_PREFIX}_source_manifest_{MODEL_TAG}.csv"
DATA_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_data_audit_{MODEL_TAG}.json"
BASELINE_BATCH_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_baseline_batch_readiness_{MODEL_TAG}.csv"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_ac_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
NORMALIZED_CHART_PATH = OUT / f"{OUTPUT_PREFIX}_normalized_equity_drawdown_{MODEL_TAG}.png"
ABSOLUTE_CHART_PATH = OUT / f"{OUTPUT_PREFIX}_absolute_equity_{MODEL_TAG}.png"
FOCUS_2022_CHART_PATH = OUT / f"{OUTPUT_PREFIX}_focus_2022_{MODEL_TAG}.png"
RUNTIME_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_runtime_audit_{MODEL_TAG}.csv"
GOLDEN_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_a_golden_reproduction_{MODEL_TAG}.csv"
CANARY_SOURCE_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_canary_source_audit_{MODEL_TAG}.csv"
ENVIRONMENT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_environment_audit_{MODEL_TAG}.json"
A_ELIGIBILITY_PATH = OUT / f"{OUTPUT_PREFIX}_a_eligibility_{MODEL_TAG}.csv"
C_ELIGIBILITY_PATH = OUT / f"{OUTPUT_PREFIX}_c_eligibility_{MODEL_TAG}.csv"
REVIEW_MANIFEST_PATH = STAGES_DIR / "stage001_precanary_review_manifest.csv"

A_VERSION = "current_official_ai_c9_control"
C_VERSION = "current_official_ai_c9_candidate_mrc"
A_STRATEGY = "current_official_ai_c9_control"
C_STRATEGY = "current_official_ai_c9_candidate_mrc"

STAGE006_OUTPUT_DIR = (
    ROOT
    / "research"
    / "lines"
    / "futures_trend_full_market_ai_filter_002risk"
    / "outputs"
    / "stage006_current_ai_paired_bottom_veto_engine"
)
STAGE006_CANDIDATES_PATH = (
    STAGE006_OUTPUT_DIR
    / "full_market_ai002_stage006_current_ai_paired_bottom_veto_engine_a0_entry_candidates_stage006_current_ai_paired_bottom_veto_engine_v1.csv.gz"
)
STAGE006_TRADES_PATH = (
    STAGE006_OUTPUT_DIR
    / "full_market_ai002_stage006_current_ai_paired_bottom_veto_engine_a0_trades_stage006_current_ai_paired_bottom_veto_engine_v1.csv.gz"
)
EXPECTED_SOURCE_SHA256.update(
    {
        STAGE006_CANDIDATES_PATH: "444ba01387f531e1ec4144875c1469496891caf29d5be870d06a33fba2abd98d",
        STAGE006_TRADES_PATH: "a323a8a90f48ba1cde20c331ef20d3a744d0277b495bb4abe88d393a74f69545",
    }
)

REVIEW_REQUIRED_PATHS = (
    ROOT / "AGENTS.md",
    ROOT / "skills" / "version-ab-experiment" / "SKILL.md",
    TOOL_PATH,
    ROOT / "tests" / "test_candidate_marginal_risk_contribution_stage001.py",
    STAGES_DIR / "20260712_1831_stage001_candidate_mrc_predecl.md",
    STAGES_DIR / "20260712_1832_stage001_candidate_mrc_implementation_plan.md",
    STAGES_DIR / "20260712_1840_stage001_data_contract_amendment.md",
    STAGES_DIR / "20260712_1908_stage001_static_audit_pass.md",
    STAGES_DIR / "20260712_1946_stage001_precanary_gate_review_repair.md",
    STAGES_DIR / "20260712_2011_stage001_runtime_evidence_gate_review_repair.md",
    STAGE137_SOURCE_MANIFEST_PATH,
    PANEL_PATH,
    SOURCE_MANIFEST_PATH,
    DATA_AUDIT_PATH,
    BASELINE_BATCH_AUDIT_PATH,
    CURRENT_AI_PATH,
    MAPPING_PATH,
    DATABASE_PATH,
    *STAGE462_PATHS.values(),
    STAGE006_CANDIDATES_PATH,
    STAGE006_TRADES_PATH,
)

GOLDEN_A = {
    "2020-01": {
        "end_equity": 5_996_631.0,
        "total_return_pct": 3_897.754000,
        "max_drawdown_pct": -55.370112,
        "sharpe": 1.396276,
        "total_slippage": 759_970.0,
        "total_trade_count": 641,
        "nonzero_daily_win_rate_pct": 52.830189,
        "longest_underwater_days": 662,
    },
    "2022-01": {
        "end_equity": 319_909.0,
        "total_return_pct": 113.272667,
        "max_drawdown_pct": -39.982046,
        "sharpe": 0.668189,
        "total_slippage": 27_950.0,
        "total_trade_count": 326,
        "nonzero_daily_win_rate_pct": 49.432739,
        "longest_underwater_days": 651,
    },
    "2022-07": {
        "end_equity": 462_813.7,
        "total_return_pct": 208.542467,
        "max_drawdown_pct": -55.183529,
        "sharpe": 0.939953,
        "total_slippage": 41_090.0,
        "total_trade_count": 292,
        "nonzero_daily_win_rate_pct": 50.0,
        "longest_underwater_days": 665,
    },
    "2026-01": {
        "end_equity": 154_651.6,
        "total_return_pct": 3.101067,
        "max_drawdown_pct": -14.247923,
        "sharpe": 0.371778,
        "total_slippage": 3_080.0,
        "total_trade_count": 38,
        "nonzero_daily_win_rate_pct": 53.424658,
        "longest_underwater_days": 98,
    },
}

CUSTOM_FIELDS = (
    "mrc_enabled",
    "mrc_available",
    "mrc_reason",
    "mrc_batch_id",
    "mrc_panel_sha256",
    "mrc_lookback_days",
    "mrc_observation_count",
    "mrc_observation_start",
    "mrc_observation_end",
    "mrc_observation_span_days",
    "mrc_active_count",
    "mrc_candidate_count",
    "mrc_asset_count",
    "mrc_contracts",
    "mrc_matrix_sha256",
    "mrc_covariance_sha256",
    "mrc_portfolio_volatility",
    "mrc_cash_exposure",
    "mrc_marginal_risk",
    "mrc_component_risk",
    "mrc_inherent_risk",
    "mrc_correlation_risk",
    "mrc_scale",
    "mrc_selected_volume_before",
    "mrc_selected_volume_after",
    "mrc_volume_reduced",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_snapshot(path: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    if resolved.is_symlink() or path.is_symlink():
        raise ValueError(f"symlink source is forbidden: {path}")
    stat = resolved.stat()
    return {
        "path": str(resolved),
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "sha256": sha256_file(resolved),
    }


def capture_source_manifest(paths: Iterable[Path]) -> pd.DataFrame:
    rows = [file_snapshot(Path(path)) for path in sorted({Path(item).resolve() for item in paths}, key=str)]
    return pd.DataFrame(rows, columns=["path", "size", "mtime_ns", "sha256"])


def validate_expected_sources() -> pd.DataFrame:
    manifest = capture_source_manifest(EXPECTED_SOURCE_SHA256)
    expected = {str(path.resolve()): value for path, value in EXPECTED_SOURCE_SHA256.items()}
    manifest["expected_sha256"] = manifest["path"].map(expected)
    manifest["sha256_match"] = manifest["sha256"].eq(manifest["expected_sha256"]).astype(int)
    if not manifest["sha256_match"].eq(1).all():
        bad = manifest.loc[manifest["sha256_match"].eq(0), ["path", "sha256", "expected_sha256"]]
        raise RuntimeError(f"frozen source hash mismatch:\n{bad.to_string(index=False)}")
    return manifest


def validate_review_manifest(
    manifest_path: Path,
    *,
    expected_manifest_sha256: str,
    required_paths: Iterable[Path] | None = None,
) -> pd.DataFrame:
    path = Path(manifest_path).resolve(strict=True)
    expected_manifest_sha = str(expected_manifest_sha256).strip().lower()
    if len(expected_manifest_sha) != 64 or any(character not in "0123456789abcdef" for character in expected_manifest_sha):
        raise RuntimeError("review manifest SHA must be a 64-character lowercase hex digest")
    actual_manifest_sha = sha256_file(path)
    if actual_manifest_sha != expected_manifest_sha:
        raise RuntimeError(
            f"review manifest SHA mismatch: expected={expected_manifest_sha} actual={actual_manifest_sha}"
        )
    manifest = pd.read_csv(path, encoding="utf-8-sig")
    required_columns = {"path", "size", "sha256"}
    missing_columns = required_columns.difference(manifest.columns)
    if missing_columns:
        raise RuntimeError(f"review manifest schema missing: {sorted(missing_columns)}")
    if manifest.empty or manifest["path"].astype(str).duplicated().any():
        raise RuntimeError("review manifest must be non-empty with unique paths")
    expected_paths = {
        str(Path(item).resolve(strict=True))
        for item in (REVIEW_REQUIRED_PATHS if required_paths is None else required_paths)
    }
    manifest_paths = {str(Path(value).resolve(strict=True)) for value in manifest["path"].astype(str)}
    if manifest_paths != expected_paths:
        missing = sorted(expected_paths.difference(manifest_paths))
        unexpected = sorted(manifest_paths.difference(expected_paths))
        raise RuntimeError(f"review manifest path set mismatch: missing={missing} unexpected={unexpected}")
    rows: list[dict[str, Any]] = []
    for source in manifest.itertuples(index=False):
        source_path = Path(str(source.path)).resolve(strict=True)
        current = file_snapshot(source_path)
        rows.append(
            {
                "path": str(source_path),
                "expected_size": int(source.size),
                "actual_size": int(current["size"]),
                "expected_sha256": str(source.sha256),
                "actual_sha256": str(current["sha256"]),
                "size_match": int(int(source.size) == int(current["size"])),
                "sha256_match": int(str(source.sha256) == str(current["sha256"])),
            }
        )
    audit = pd.DataFrame(rows)
    if not audit[["size_match", "sha256_match"]].eq(1).all().all():
        bad = audit.loc[
            ~audit[["size_match", "sha256_match"]].eq(1).all(axis=1),
            ["path", "expected_size", "actual_size", "expected_sha256", "actual_sha256"],
        ]
        raise RuntimeError(f"reviewed source drift:\n{bad.to_string(index=False)}")
    return audit


def _normalise_close_rows(frame: pd.DataFrame, *, source: str | None) -> pd.DataFrame:
    required = {"date", "contract_vt_symbol", "close"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"close source missing columns: {sorted(missing)}")
    data = frame.copy()
    data["date"] = pd.to_datetime(data["date"], errors="raise").dt.tz_localize(None).dt.normalize()
    data["contract_vt_symbol"] = data["contract_vt_symbol"].astype(str)
    data["close"] = pd.to_numeric(data["close"], errors="raise").astype(float)
    if (~np.isfinite(data["close"]) | data["close"].le(0.0)).any():
        raise ValueError(f"non-positive or non-finite close in {source}")
    if source is None:
        if "source" not in data.columns or data["source"].isna().any():
            raise ValueError("close source labels are required")
        data["source"] = data["source"].astype(str)
    else:
        data["source"] = source
    conflicts = data.groupby(["date", "contract_vt_symbol"])["close"].nunique()
    if conflicts.gt(1).any():
        raise ValueError(f"conflicting duplicate closes in {source or 'mixed'}")
    return (
        data.sort_values(["date", "contract_vt_symbol"])
        .drop_duplicates(["date", "contract_vt_symbol"], keep="last")
        [["date", "contract_vt_symbol", "close", "source"]]
        .reset_index(drop=True)
    )


def read_database_daily_closes(path: Path = DATABASE_PATH) -> pd.DataFrame:
    uri = f"file:{path.resolve()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.execute("PRAGMA query_only=ON")
        frame = pd.read_sql_query(
            "select symbol, exchange, datetime, close_price from dbbardata where interval='d'",
            connection,
        )
    frame["date"] = pd.to_datetime(frame["datetime"], errors="raise").dt.normalize()
    frame["contract_vt_symbol"] = frame["symbol"].astype(str) + "." + frame["exchange"].astype(str)
    frame["close"] = frame["close_price"]
    return _normalise_close_rows(frame, source="sqlite_daily")


def aggregate_stage462_day_closes(frame: pd.DataFrame, *, contract_vt_symbol: str) -> pd.DataFrame:
    required = {"vt_symbol", "bar_datetime", "close"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Stage462 source missing columns: {sorted(missing)}")
    data = frame.copy()
    symbols = set(data["vt_symbol"].dropna().astype(str))
    if symbols != {contract_vt_symbol}:
        raise ValueError(f"Stage462 symbol mismatch: {symbols} != {contract_vt_symbol}")
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="raise")
    day_session = data[data["bar_datetime"].dt.hour.between(14, 15, inclusive="left")].copy()
    if day_session.empty:
        raise ValueError(f"no day-session close bars: {contract_vt_symbol}")
    day_session["date"] = day_session["bar_datetime"].dt.normalize()
    daily = day_session.sort_values("bar_datetime").groupby("date", as_index=False).tail(1)
    daily["contract_vt_symbol"] = contract_vt_symbol
    daily["close"] = pd.to_numeric(daily["close"], errors="raise")
    return _normalise_close_rows(daily, source="stage462_day_close")


def read_stage462_day_closes(paths: dict[str, Path] = STAGE462_PATHS) -> list[pd.DataFrame]:
    result: list[pd.DataFrame] = []
    for contract, path in sorted(paths.items()):
        frame = pd.read_csv(path, encoding="utf-8-sig")
        result.append(aggregate_stage462_day_closes(frame, contract_vt_symbol=contract))
    return result


def merge_contract_close_sources(frames: Sequence[pd.DataFrame]) -> pd.DataFrame:
    cleaned = [_normalise_close_rows(frame, source=str(frame["source"].iloc[0])) for frame in frames if not frame.empty]
    if not cleaned:
        raise ValueError("no close sources")
    combined = pd.concat(cleaned, ignore_index=True, sort=False)
    overlap = combined.groupby(["date", "contract_vt_symbol"])["close"].agg(["count", "nunique"])
    if (overlap["nunique"] > 1).any():
        raise ValueError("conflicting close values across sources")
    priority = {"sqlite_daily": 0, "stage462_day_close": 1}
    combined["source_priority"] = combined["source"].map(priority).fillna(-1).astype(int)
    return (
        combined.sort_values(["date", "contract_vt_symbol", "source_priority"])
        .drop_duplicates(["date", "contract_vt_symbol"], keep="last")
        [["date", "contract_vt_symbol", "close", "source"]]
        .sort_values(["contract_vt_symbol", "date"])
        .reset_index(drop=True)
    )


def build_contract_return_panel(closes: pd.DataFrame) -> pd.DataFrame:
    data = _normalise_close_rows(closes, source=None)
    data = data[data["date"].between(PANEL_START, REQUESTED_END)].copy()
    dates = pd.Index(sorted(data["date"].drop_duplicates()))
    previous_by_date = {dates[index]: dates[index - 1] for index in range(1, len(dates))}
    data = data.sort_values(["contract_vt_symbol", "date"]).reset_index(drop=True)
    data["previous_date"] = data.groupby("contract_vt_symbol")["date"].shift(1)
    data["expected_previous_date"] = data["date"].map(previous_by_date)
    data["previous_close"] = data.groupby("contract_vt_symbol")["close"].shift(1)
    valid = (
        data["previous_date"].notna()
        & data["previous_date"].eq(data["expected_previous_date"])
        & data["previous_close"].gt(0.0)
        & data["close"].gt(0.0)
    )
    data["return_valid"] = valid.astype(int)
    data["invalid_reason"] = np.where(
        data["previous_date"].isna(),
        "first_contract_observation",
        np.where(~data["previous_date"].eq(data["expected_previous_date"]), "trading_date_gap", ""),
    )
    data["contract_return"] = np.nan
    data.loc[valid, "contract_return"] = (
        data.loc[valid, "close"] / data.loc[valid, "previous_close"] - 1.0
    )
    if data.loc[data["return_valid"].eq(1), "contract_return"].isna().any():
        raise ValueError("valid contract return is NaN")
    return data[
        [
            "date",
            "contract_vt_symbol",
            "close",
            "previous_date",
            "previous_close",
            "contract_return",
            "return_valid",
            "invalid_reason",
            "source",
        ]
    ].reset_index(drop=True)


def load_current_ai_contract_universe() -> tuple[list[str], list[str]]:
    ai = pd.read_csv(CURRENT_AI_PATH, encoding="utf-8-sig")
    required_ai = {"product_vt_symbol", "eval_date"}
    if required_ai.difference(ai.columns):
        raise ValueError("current AI snapshot schema mismatch")
    products = sorted(set(ai["product_vt_symbol"].dropna().astype(str)))
    if len(ai) != 504 or ai["eval_date"].nunique() != 55 or len(products) != 19:
        raise ValueError("current AI snapshot identity counts changed")
    mapping = pd.read_csv(MAPPING_PATH, encoding="utf-8-sig")
    required_mapping = {"date", "continuous_symbol_vt", "main_contract_vt"}
    if required_mapping.difference(mapping.columns):
        raise ValueError("main-contract mapping schema mismatch")
    mapping["date"] = pd.to_datetime(mapping["date"], errors="raise").dt.normalize()
    mapping = mapping[
        mapping["continuous_symbol_vt"].astype(str).isin(products)
        & mapping["date"].between(PANEL_START, REQUESTED_END)
    ].copy()
    contracts = sorted(
        {
            value
            for value in mapping["main_contract_vt"].fillna("").astype(str)
            if value
        }
        | set(STAGE462_PATHS)
    )
    if not contracts:
        raise ValueError("current AI contract universe is empty")
    return products, contracts


def build_frozen_return_panel() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    before = validate_expected_sources()
    products, contracts = load_current_ai_contract_universe()
    closes = merge_contract_close_sources([read_database_daily_closes(), *read_stage462_day_closes()])
    closes = closes[closes["contract_vt_symbol"].isin(contracts)].copy()
    panel = build_contract_return_panel(closes)
    after = validate_expected_sources()
    compare = before.merge(after, on="path", suffixes=("_before", "_after"), validate="one_to_one")
    compare["post_read_content_match"] = compare["sha256_before"].eq(compare["sha256_after"]).astype(int)
    if not compare["post_read_content_match"].eq(1).all():
        raise RuntimeError("source content changed while building return panel")
    audit = {
        "panel_rows": int(len(panel)),
        "panel_contracts": int(panel["contract_vt_symbol"].nunique()),
        "panel_dates": int(panel["date"].nunique()),
        "current_ai_products": len(products),
        "allowed_contracts": len(contracts),
        "covered_contracts": int(panel["contract_vt_symbol"].nunique()),
        "missing_allowed_contracts": sorted(set(contracts).difference(panel["contract_vt_symbol"])),
        "panel_start": panel["date"].min().date().isoformat(),
        "panel_end": panel["date"].max().date().isoformat(),
        "valid_return_rows": int(panel["return_valid"].sum()),
        "duplicate_key_count": int(panel.duplicated(["date", "contract_vt_symbol"]).sum()),
        "future_date_count": int(panel["date"].gt(REQUESTED_END).sum()),
        "source_post_read_mismatch_count": int(compare["post_read_content_match"].eq(0).sum()),
    }
    if audit["missing_allowed_contracts"]:
        raise RuntimeError(f"allowed contracts missing daily inputs: {audit['missing_allowed_contracts']}")
    return panel, compare, audit


def _local_date_series(values: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(values, errors="raise", utc=True)
    return parsed.dt.tz_convert("Asia/Shanghai").dt.tz_localize(None).dt.normalize()


def audit_baseline_batch_readiness(
    panel: pd.DataFrame,
    candidates: pd.DataFrame,
    trades: pd.DataFrame,
) -> pd.DataFrame:
    required_candidates = {
        "datetime",
        "candidate_status",
        "contract_vt_symbol",
        "selected_volume",
    }
    required_trades = {"datetime", "vt_symbol", "signed_volume"}
    if required_candidates.difference(candidates.columns) or required_trades.difference(trades.columns):
        raise ValueError("baseline readiness source schema mismatch")
    opened = candidates.copy()
    opened["local_date"] = _local_date_series(opened["datetime"])
    opened["selected_volume"] = pd.to_numeric(opened["selected_volume"], errors="raise").astype(int)
    opened = opened[
        opened["candidate_status"].astype(str).eq("opened") & opened["selected_volume"].gt(0)
    ].copy()
    trades = trades.copy()
    trades["local_date"] = _local_date_series(trades["datetime"])
    trades["signed_volume"] = pd.to_numeric(trades["signed_volume"], errors="raise").astype(float)
    trade_by_date = (
        trades.groupby(["local_date", "vt_symbol"], as_index=False)["signed_volume"].sum()
        .sort_values(["local_date", "vt_symbol"])
        .reset_index(drop=True)
    )
    position: dict[str, float] = {}
    trade_rows = list(trade_by_date.itertuples(index=False))
    trade_index = 0
    output: list[dict[str, Any]] = []
    for candidate_date, group in opened.sort_values("local_date").groupby("local_date", sort=True):
        while trade_index < len(trade_rows) and pd.Timestamp(trade_rows[trade_index].local_date) <= candidate_date:
            row = trade_rows[trade_index]
            symbol = str(row.vt_symbol)
            position[symbol] = position.get(symbol, 0.0) + float(row.signed_volume)
            trade_index += 1
        position = {symbol: value for symbol, value in position.items() if abs(value) > 1e-9}
        candidate_contracts = sorted(set(group["contract_vt_symbol"].astype(str)))
        active_contracts = sorted(position)
        contracts = sorted(set(candidate_contracts) | set(active_contracts))
        matrix, audit = select_t1_common_returns(panel, contracts, cutoff_date=candidate_date)
        output.append(
            {
                "candidate_date": candidate_date.date().isoformat(),
                "candidate_count": int(len(group)),
                "candidate_contracts": "/".join(candidate_contracts),
                "active_count": len(active_contracts),
                "active_contracts": "/".join(active_contracts),
                "contract_count": len(contracts),
                "contracts": "/".join(contracts),
                "available": int(audit["available"]),
                "reason": str(audit["reason"]),
                "observation_count": int(audit["observation_count"]),
                "observation_start": str(audit["observation_start"]),
                "observation_end": str(audit["observation_end"]),
                "observation_span_days": int(audit["observation_span_days"]),
                "matrix_sha256": _canonical_frame_sha256(matrix) if not matrix.empty else "",
            }
        )
    return pd.DataFrame(output)


def select_t1_common_returns(
    panel: pd.DataFrame,
    contracts: Sequence[str],
    *,
    cutoff_date: pd.Timestamp,
    lookback: int = LOOKBACK_DAYS,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    labels = sorted(set(map(str, contracts)))
    cutoff = pd.Timestamp(cutoff_date)
    if cutoff.tzinfo is not None:
        cutoff = cutoff.tz_localize(None)
    cutoff = cutoff.normalize()
    audit: dict[str, Any] = {
        "available": 0,
        "reason": "",
        "lookback": int(lookback),
        "contract_count": len(labels),
        "contracts": "/".join(labels),
        "observation_count": 0,
        "observation_start": "",
        "observation_end": "",
        "observation_span_days": 0,
        "current_or_future_row_count": 0,
        "missing_contracts": "",
    }
    if not labels:
        audit["reason"] = "no_contracts"
        return pd.DataFrame(), audit
    required = {"date", "contract_vt_symbol", "contract_return", "return_valid"}
    if required.difference(panel.columns):
        raise ValueError(f"return panel missing columns: {sorted(required.difference(panel.columns))}")
    data = panel.copy()
    data["date"] = pd.to_datetime(data["date"], errors="raise").dt.tz_localize(None).dt.normalize()
    if data.duplicated(["date", "contract_vt_symbol"]).any():
        raise ValueError("duplicate return panel key")
    existing = set(data["contract_vt_symbol"].astype(str))
    missing = sorted(set(labels).difference(existing))
    if missing:
        audit["reason"] = "missing_contract"
        audit["missing_contracts"] = "/".join(missing)
        return pd.DataFrame(), audit
    future_count = int(
        data["contract_vt_symbol"].isin(labels).mul(data["date"].ge(cutoff)).mul(data["return_valid"].eq(1)).sum()
    )
    audit["current_or_future_row_count"] = future_count
    eligible = data[
        data["contract_vt_symbol"].isin(labels)
        & data["date"].lt(cutoff)
        & pd.to_numeric(data["return_valid"], errors="raise").eq(1)
    ].copy()
    pivot = eligible.pivot(index="date", columns="contract_vt_symbol", values="contract_return")
    pivot = pivot.reindex(columns=labels).replace([np.inf, -np.inf], np.nan).dropna(how="any")
    selected = pivot.tail(int(lookback)).copy()
    audit["eligible_current_or_future_rows_ignored"] = future_count
    audit["observation_count"] = int(len(selected))
    if len(selected) < int(lookback):
        audit["reason"] = "insufficient_common_history"
        return pd.DataFrame(), audit
    if selected.index.max() >= cutoff:
        raise ValueError("current/future return leaked into T-1 matrix")
    audit.update(
        {
            "available": 1,
            "reason": "available",
            "observation_start": selected.index.min().date().isoformat(),
            "observation_end": selected.index.max().date().isoformat(),
            "observation_span_days": int((selected.index.max() - selected.index.min()).days),
        }
    )
    return selected, audit


def component_risk_contributions(
    covariance: np.ndarray,
    exposure: np.ndarray,
    labels: Sequence[str],
) -> tuple[pd.DataFrame, float]:
    cov = np.asarray(covariance, dtype=float)
    vector = np.asarray(exposure, dtype=float)
    names = list(map(str, labels))
    if cov.shape != (len(vector), len(vector)) or len(names) != len(vector):
        raise ValueError("covariance/exposure/label shape mismatch")
    if not np.isfinite(cov).all() or not np.isfinite(vector).all():
        raise ValueError("non-finite risk inputs")
    if not np.allclose(cov, cov.T, atol=1e-12, rtol=1e-10):
        raise ValueError("covariance is not symmetric")
    eigen_min = float(np.linalg.eigvalsh((cov + cov.T) / 2.0).min())
    if eigen_min < -1e-12:
        raise ValueError("covariance is not positive semidefinite")
    variance = float(vector @ cov @ vector)
    if not math.isfinite(variance) or variance <= 1e-18:
        raise ValueError("portfolio variance is not positive")
    sigma = math.sqrt(variance)
    marginal = cov @ vector / sigma
    component = vector * marginal
    inherent = vector * vector * np.diag(cov) / sigma
    correlation = component - inherent
    scale = np.ones(len(vector), dtype=float)
    mask = (component > inherent) & (inherent > 1e-18)
    scale[mask] = inherent[mask] / component[mask]
    scale = np.clip(scale, 0.0, 1.0)
    result = pd.DataFrame(
        {
            "label": names,
            "cash_exposure": vector,
            "marginal_risk": marginal,
            "component_risk": component,
            "inherent_risk": inherent,
            "correlation_risk": correlation,
            "scale": scale,
        }
    )
    if not math.isclose(float(result["component_risk"].sum()), sigma, rel_tol=1e-9, abs_tol=1e-10):
        raise ValueError("component risk does not add to portfolio volatility")
    return result, sigma


def reduced_integer_volume(before: int, scale: float, *, minimum: int = MIN_PRESERVED_VOLUME) -> int:
    baseline = int(before)
    if baseline <= 0:
        return 0
    value = float(scale)
    if not math.isfinite(value) or value < 0.0 or value > 1.0 + 1e-12:
        raise ValueError("scale must be finite and within [0, 1]")
    after = int(math.floor(baseline * min(1.0, max(0.0, value)) + 1e-12))
    return min(baseline, max(int(minimum), after))


def _canonical_frame_sha256(frame: pd.DataFrame) -> str:
    payload = frame.to_csv(index=True, lineterminator="\n", float_format="%.17g").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def compute_batch_adjustments(
    exposure_rows: pd.DataFrame,
    returns: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    required = {"role", "contract_vt_symbol", "cash_exposure", "baseline_volume"}
    missing = required.difference(exposure_rows.columns)
    if missing:
        raise ValueError(f"exposure rows missing columns: {sorted(missing)}")
    rows = exposure_rows.copy()
    rows["contract_vt_symbol"] = rows["contract_vt_symbol"].astype(str)
    rows["cash_exposure"] = pd.to_numeric(rows["cash_exposure"], errors="raise").astype(float)
    rows["baseline_volume"] = pd.to_numeric(rows["baseline_volume"], errors="raise").astype(int)
    candidates = rows[rows["role"].eq("candidate")].copy()
    if candidates.empty:
        raise ValueError("batch has no candidates")
    if candidates["contract_vt_symbol"].duplicated().any():
        raise ValueError("duplicate candidate contract")
    active_contracts = set(rows.loc[rows["role"].eq("active"), "contract_vt_symbol"])
    overlap = active_contracts.intersection(candidates["contract_vt_symbol"])
    if overlap:
        raise ValueError(f"candidate contract already active: {sorted(overlap)}")
    aggregate = rows.groupby("contract_vt_symbol", as_index=False)["cash_exposure"].sum()
    labels = sorted(aggregate["contract_vt_symbol"].astype(str))
    matrix = returns.reindex(columns=labels)
    if matrix.isna().any().any() or len(matrix) != LOOKBACK_DAYS:
        raise ValueError("risk matrix must contain exact complete lookback")
    covariance = LedoitWolf().fit(matrix.to_numpy(dtype=float)).covariance_
    exposure_by_label = aggregate.set_index("contract_vt_symbol")["cash_exposure"].reindex(labels)
    components, sigma = component_risk_contributions(covariance, exposure_by_label.to_numpy(), labels)
    candidate_meta = candidates.set_index("contract_vt_symbol")
    adjusted = components[components["label"].isin(candidate_meta.index)].copy()
    adjusted["baseline_volume"] = adjusted["label"].map(candidate_meta["baseline_volume"]).astype(int)
    adjusted["selected_volume_after"] = [
        reduced_integer_volume(before, scale)
        for before, scale in zip(adjusted["baseline_volume"], adjusted["scale"], strict=True)
    ]
    adjusted["volume_reduced"] = adjusted["baseline_volume"] - adjusted["selected_volume_after"]
    adjusted = adjusted.sort_values("label").reset_index(drop=True)
    if (adjusted["selected_volume_after"] > adjusted["baseline_volume"]).any():
        raise ValueError("MRC increased a candidate volume")
    if (adjusted["selected_volume_after"] <= 0).any():
        raise ValueError("MRC silently zeroed a candidate")
    covariance_bytes = np.asarray(covariance, dtype="<f8").tobytes(order="C")
    audit = {
        "asset_count": len(labels),
        "candidate_count": int(len(candidates)),
        "active_count": int(rows["role"].eq("active").sum()),
        "contracts": "/".join(labels),
        "portfolio_volatility": sigma,
        "matrix_sha256": _canonical_frame_sha256(matrix),
        "covariance_sha256": hashlib.sha256(covariance_bytes).hexdigest(),
    }
    return adjusted, audit


def _local_trading_date(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_localize(None)
    return timestamp.normalize()


def _direction_sign(direction: str) -> float:
    text = str(direction).strip().lower()
    if text == "long":
        return 1.0
    if text == "short":
        return -1.0
    raise ValueError(f"unknown direction: {direction}")


def _default_mrc_fields(*, before: int = 0, reason: str = "not_in_opened_batch") -> dict[str, Any]:
    return {
        "mrc_enabled": 1,
        "mrc_available": 0,
        "mrc_reason": reason,
        "mrc_batch_id": "",
        "mrc_panel_sha256": "",
        "mrc_lookback_days": LOOKBACK_DAYS,
        "mrc_observation_count": 0,
        "mrc_observation_start": "",
        "mrc_observation_end": "",
        "mrc_observation_span_days": 0,
        "mrc_active_count": 0,
        "mrc_candidate_count": 0,
        "mrc_asset_count": 0,
        "mrc_contracts": "",
        "mrc_matrix_sha256": "",
        "mrc_covariance_sha256": "",
        "mrc_portfolio_volatility": 0.0,
        "mrc_cash_exposure": 0.0,
        "mrc_marginal_risk": 0.0,
        "mrc_component_risk": 0.0,
        "mrc_inherent_risk": 0.0,
        "mrc_correlation_risk": 0.0,
        "mrc_scale": 1.0,
        "mrc_selected_volume_before": max(0, int(before)),
        "mrc_selected_volume_after": max(0, int(before)),
        "mrc_volume_reduced": 0,
    }


class QmtRollPortfolioStrategyCandidateMRC(s006.base.s847.QmtRollPortfolioStrategyStage847C9StopRetry):
    enable_candidate_mrc: bool = True
    candidate_mrc_return_panel_path: str = str(PANEL_PATH)
    candidate_mrc_return_panel_sha256: str = ""
    candidate_mrc_lookback_days: int = LOOKBACK_DAYS
    candidate_mrc_min_preserved_volume: int = MIN_PRESERVED_VOLUME

    parameters = s006.base.s847.QmtRollPortfolioStrategyStage847C9StopRetry.parameters + [
        "enable_candidate_mrc",
        "candidate_mrc_return_panel_path",
        "candidate_mrc_return_panel_sha256",
        "candidate_mrc_lookback_days",
        "candidate_mrc_min_preserved_volume",
    ]

    def __init__(self, strategy_engine, strategy_name: str, vt_symbols: list[str], setting: dict) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.candidate_mrc_batch_count = 0
        self.candidate_mrc_available_batch_count = 0
        self.candidate_mrc_unavailable_batch_count = 0
        self.candidate_mrc_reduced_count = 0
        self._candidate_mrc_panel = pd.DataFrame()
        self._candidate_mrc_panel_sha256 = ""
        if self.enable_candidate_mrc:
            panel_path = Path(str(self.candidate_mrc_return_panel_path)).resolve(strict=True)
            actual_sha = sha256_file(panel_path)
            expected_sha = str(self.candidate_mrc_return_panel_sha256 or "")
            if not expected_sha or actual_sha != expected_sha:
                raise RuntimeError("candidate MRC return panel SHA mismatch")
            panel = pd.read_csv(panel_path, encoding="utf-8-sig")
            panel["date"] = pd.to_datetime(panel["date"], errors="raise").dt.normalize()
            self._candidate_mrc_panel = panel
            self._candidate_mrc_panel_sha256 = actual_sha

    def _build_batch_exposures(
        self,
        day_contexts: list[Any],
        opened_plans: list[dict[str, Any]],
        candidate_date: pd.Timestamp,
    ) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        represented_active: set[str] = set()
        for context in day_contexts:
            current_pos = int(context.current_pos or 0)
            if current_pos == 0:
                continue
            contract = str(context.state.contract_vt_symbol or context.target_contract)
            bar = context.actual_bar if context.actual_bar is not None else context.target_bar
            if bar is None or _local_trading_date(bar.datetime) != candidate_date:
                raise ValueError(f"active contract lacks current-date price: {contract}")
            price = float(bar.close_price)
            size = float(self.get_size(contract))
            if not math.isfinite(price) or price <= 0.0 or not math.isfinite(size) or size <= 0.0:
                raise ValueError(f"invalid active exposure inputs: {contract}")
            rows.append(
                {
                    "role": "active",
                    "contract_vt_symbol": contract,
                    "cash_exposure": float(current_pos) * size * price,
                    "baseline_volume": abs(current_pos),
                }
            )
            represented_active.add(contract)
        actual_active = {
            str(state.contract_vt_symbol)
            for state in self.states.values()
            if state.contract_vt_symbol and int(self.get_pos(str(state.contract_vt_symbol))) != 0
        }
        if represented_active != actual_active:
            raise ValueError(
                f"active exposure set mismatch represented={sorted(represented_active)} actual={sorted(actual_active)}"
            )
        for plan in opened_plans:
            contract = str(plan["target_contract"])
            bar = plan["target_bar"]
            volume = max(0, int(plan["volume"]))
            price = float(bar.close_price)
            size = float(self.get_size(contract))
            if volume <= 0 or _local_trading_date(bar.datetime) != candidate_date:
                raise ValueError(f"invalid candidate volume/date: {contract}")
            if not math.isfinite(price) or price <= 0.0 or not math.isfinite(size) or size <= 0.0:
                raise ValueError(f"invalid candidate exposure inputs: {contract}")
            rows.append(
                {
                    "role": "candidate",
                    "contract_vt_symbol": contract,
                    "cash_exposure": _direction_sign(str(plan["direction"])) * volume * size * price,
                    "baseline_volume": volume,
                }
            )
        return pd.DataFrame(rows)

    def _mark_opened_batch_unavailable(
        self,
        plans: dict[str, dict[str, Any]],
        opened: list[dict[str, Any]],
        exposure_rows: pd.DataFrame,
        history_audit: dict[str, Any],
        *,
        batch_id: str,
    ) -> dict[str, dict[str, Any]]:
        self.candidate_mrc_unavailable_batch_count += 1
        for plan in opened:
            sizing = dict(plan["sizing"])
            fields = _default_mrc_fields(before=int(plan["volume"]), reason=str(history_audit.get("reason")))
            fields.update(
                {
                    "mrc_batch_id": batch_id,
                    "mrc_panel_sha256": self._candidate_mrc_panel_sha256,
                    "mrc_observation_count": int(history_audit.get("observation_count", 0)),
                    "mrc_observation_start": str(history_audit.get("observation_start", "")),
                    "mrc_observation_end": str(history_audit.get("observation_end", "")),
                    "mrc_observation_span_days": int(history_audit.get("observation_span_days", 0)),
                    "mrc_candidate_count": len(opened),
                    "mrc_active_count": int(exposure_rows["role"].eq("active").sum())
                    if not exposure_rows.empty
                    else 0,
                    "mrc_asset_count": int(history_audit.get("contract_count", 0)),
                    "mrc_contracts": str(history_audit.get("contracts", "")),
                }
            )
            sizing.update(fields)
            plan["sizing"] = sizing
        return plans

    def _plan_flat_entry_candidates(self, day_contexts: list[Any]) -> dict[str, dict[str, Any]]:
        plans = super()._plan_flat_entry_candidates(day_contexts)
        for plan in plans.values():
            sizing = dict(plan["sizing"])
            sizing.update(_default_mrc_fields(before=max(0, int(plan.get("volume") or 0))))
            plan["sizing"] = sizing
        if not self.enable_candidate_mrc:
            return plans
        opened = [
            plan
            for plan in plans.values()
            if str(plan.get("candidate_status")) == "opened" and int(plan.get("volume") or 0) > 0
        ]
        if not opened:
            return plans
        candidate_dates = {_local_trading_date(plan["target_bar"].datetime) for plan in opened}
        if len(candidate_dates) != 1:
            raise ValueError(f"opened batch spans multiple dates: {candidate_dates}")
        candidate_date = next(iter(candidate_dates))
        batch_id = f"{candidate_date.date().isoformat()}|" + "/".join(
            sorted(str(plan["target_contract"]) for plan in opened)
        )
        self.candidate_mrc_batch_count += 1
        try:
            exposure_rows = self._build_batch_exposures(day_contexts, opened, candidate_date)
            matrix, history_audit = select_t1_common_returns(
                self._candidate_mrc_panel,
                exposure_rows["contract_vt_symbol"].astype(str).tolist(),
                cutoff_date=candidate_date,
                lookback=int(self.candidate_mrc_lookback_days),
            )
        except (ValueError, KeyError) as exc:
            exposure_rows = pd.DataFrame()
            matrix = pd.DataFrame()
            history_audit = {
                "available": 0,
                "reason": f"exposure_error:{type(exc).__name__}:{exc}",
                "observation_count": 0,
                "observation_start": "",
                "observation_end": "",
                "observation_span_days": 0,
                "contract_count": 0,
                "contracts": "",
            }
        if not int(history_audit.get("available", 0)):
            return self._mark_opened_batch_unavailable(
                plans,
                opened,
                exposure_rows,
                history_audit,
                batch_id=batch_id,
            )
        try:
            adjustments, batch_audit = compute_batch_adjustments(exposure_rows, matrix)
        except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
            failed_audit = dict(history_audit)
            failed_audit.update(
                {
                    "available": 0,
                    "reason": f"risk_compute_error:{type(exc).__name__}:{exc}",
                }
            )
            return self._mark_opened_batch_unavailable(
                plans,
                opened,
                exposure_rows,
                failed_audit,
                batch_id=batch_id,
            )
        by_contract = adjustments.set_index("label")
        self.candidate_mrc_available_batch_count += 1
        for plan in opened:
            contract = str(plan["target_contract"])
            row = by_contract.loc[contract]
            before = int(plan["volume"])
            after = int(row["selected_volume_after"])
            if not (0 < after <= before):
                raise ValueError(f"invalid MRC volume {contract}: {before}->{after}")
            sizing = dict(plan["sizing"])
            fields = _default_mrc_fields(before=before, reason="available")
            fields.update(
                {
                    "mrc_available": 1,
                    "mrc_batch_id": batch_id,
                    "mrc_panel_sha256": self._candidate_mrc_panel_sha256,
                    "mrc_observation_count": int(history_audit["observation_count"]),
                    "mrc_observation_start": str(history_audit["observation_start"]),
                    "mrc_observation_end": str(history_audit["observation_end"]),
                    "mrc_observation_span_days": int(history_audit["observation_span_days"]),
                    "mrc_active_count": int(batch_audit["active_count"]),
                    "mrc_candidate_count": int(batch_audit["candidate_count"]),
                    "mrc_asset_count": int(batch_audit["asset_count"]),
                    "mrc_contracts": str(batch_audit["contracts"]),
                    "mrc_matrix_sha256": str(batch_audit["matrix_sha256"]),
                    "mrc_covariance_sha256": str(batch_audit["covariance_sha256"]),
                    "mrc_portfolio_volatility": float(batch_audit["portfolio_volatility"]),
                    "mrc_cash_exposure": float(row["cash_exposure"]),
                    "mrc_marginal_risk": float(row["marginal_risk"]),
                    "mrc_component_risk": float(row["component_risk"]),
                    "mrc_inherent_risk": float(row["inherent_risk"]),
                    "mrc_correlation_risk": float(row["correlation_risk"]),
                    "mrc_scale": float(row["scale"]),
                    "mrc_selected_volume_before": before,
                    "mrc_selected_volume_after": after,
                    "mrc_volume_reduced": before - after,
                }
            )
            sizing.update(fields)
            sizing["selected_volume"] = after
            plan["volume"] = after
            plan["sizing"] = sizing
            self.candidate_mrc_reduced_count += int(after < before)
        return plans

    def _record_entry_candidate_snapshot(self, **kwargs: Any) -> None:
        sizing_snapshot = dict(kwargs.get("sizing_snapshot") or {})
        super()._record_entry_candidate_snapshot(**kwargs)
        if not self.entry_candidate_snapshots:
            return
        self.entry_candidate_snapshots[-1].update(
            {field: sizing_snapshot.get(field, "" if field.endswith(("id", "sha256", "start", "end", "contracts", "reason")) else 0) for field in CUSTOM_FIELDS}
        )


@contextmanager
def anchor_scope(start_month: str):
    original = {
        "requested_start": s006.base.REQUESTED_START,
        "requested_end": s006.base.REQUESTED_END,
        "start_month": s006.base.START_MONTH,
    }
    try:
        s006.base.REQUESTED_START = pd.Timestamp(f"{start_month}-01")
        s006.base.REQUESTED_END = REQUESTED_END
        s006.base.START_MONTH = start_month
        yield
    finally:
        s006.base.REQUESTED_START = original["requested_start"]
        s006.base.REQUESTED_END = original["requested_end"]
        s006.base.START_MONTH = original["start_month"]


def build_profile(
    metadata: dict[str, Any],
    *,
    candidate: bool,
    eligibility_path: Path,
    panel_sha256: str,
) -> dict[str, Any]:
    version = C_VERSION if candidate else A_VERSION
    strategy_name = C_STRATEGY if candidate else A_STRATEGY
    profile = s006._profile(
        metadata,
        version=version,
        strategy_name=strategy_name,
        eligibility_path=eligibility_path,
        label=("current C9 + candidate MRC" if candidate else "current C9 control"),
    )
    if not candidate:
        return profile
    spec = profile["spec"]
    overrides = {
        **spec.overrides,
        "enable_candidate_mrc": True,
        "candidate_mrc_return_panel_path": str(PANEL_PATH),
        "candidate_mrc_return_panel_sha256": panel_sha256,
        "candidate_mrc_lookback_days": LOOKBACK_DAYS,
        "candidate_mrc_min_preserved_volume": MIN_PRESERVED_VOLUME,
    }
    result = dict(profile)
    result["strategy_cls"] = QmtRollPortfolioStrategyCandidateMRC
    result["spec"] = replace(spec, overrides=overrides, profile=version)
    result["profile"] = version
    return result


def run_arm(
    metadata: dict[str, Any],
    profile: dict[str, Any],
    *,
    start_month: str,
    version: str,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    with anchor_scope(start_month):
        daily, frames, _ = s006._run_profile(metadata, profile, version)
    daily = daily.copy()
    daily["requested_start_month"] = start_month
    daily["version"] = version
    daily["stage"] = STAGE_LABEL
    daily["model_tag"] = MODEL_TAG
    daily["line_id"] = LINE_ID
    for frame in frames.values():
        if frame.empty:
            continue
        frame["requested_start_month"] = start_month
        frame["version"] = version
        frame["stage"] = STAGE_LABEL
        frame["model_tag"] = MODEL_TAG
        frame["line_id"] = LINE_ID
    return daily, frames


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="raise").astype(float)
    if not np.isfinite(values).all():
        raise ValueError("non-finite equity")
    highs = np.maximum.accumulate(np.concatenate(([CAPITAL], values.to_numpy())))[1:]
    return pd.Series((values.to_numpy() / highs - 1.0) * 100.0, index=values.index)


def _longest_underwater_days(dates: pd.Series, equity: pd.Series) -> int:
    frame = pd.DataFrame(
        {"date": pd.to_datetime(dates, errors="raise").dt.normalize(), "equity": pd.to_numeric(equity, errors="raise")}
    ).sort_values("date")
    high = CAPITAL
    start: pd.Timestamp | None = None
    longest = 0
    for row in frame.itertuples(index=False):
        value = float(row.equity)
        if value >= high:
            high = max(high, value)
            if start is not None:
                longest = max(longest, int((pd.Timestamp(row.date) - start).days))
                start = None
        elif start is None:
            start = pd.Timestamp(row.date)
    if start is not None and not frame.empty:
        longest = max(longest, int((frame["date"].max() - start).days))
    return longest


def _daily_sharpe(equity: pd.Series) -> float:
    values = pd.to_numeric(equity, errors="raise").astype(float)
    previous = np.concatenate(([CAPITAL], values.to_numpy()[:-1]))
    if (previous <= 0.0).any():
        return math.nan
    returns = values.to_numpy() / previous - 1.0
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    return float(np.mean(returns) / std * math.sqrt(252.0)) if std > 1e-15 else 0.0


def build_closed_lots(frames: dict[str, pd.DataFrame], metadata: dict[str, Any]) -> pd.DataFrame:
    trades = frames.get("trades", pd.DataFrame()).copy()
    if trades.empty:
        return pd.DataFrame()
    return s006.base.s847.s719._build_closed_lots(
        trades,
        frames.get("entry_risk", pd.DataFrame()).copy(),
        frames.get("entry_candidates", pd.DataFrame()).copy(),
        metadata,
    )


def _max_absolute(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=float)
    return float(np.max(np.abs(array))) if array.size else 0.0


def arm_integrity_audit(
    daily: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    positions = frames.get("positions", pd.DataFrame()).copy()
    trades = frames.get("trades", pd.DataFrame()).copy()
    pending = frames.get("pending_orders", pd.DataFrame()).copy()
    result: dict[str, Any] = {
        "pending_order_count": int(len(pending)),
        "pending_order_invalid_count": 0,
        "pending_order_duplicate_count": 0,
        "position_duplicate_key_count": 0,
        "trade_duplicate_id_count": 0,
        "terminal_open_contract_count": 0,
        "position_continuity_max_error": 0.0,
        "position_row_identity_max_error": 0.0,
        "daily_position_change_reconciliation_max_error": 0.0,
        "terminal_position_reconciliation_max_error": 0.0,
        "margin_identity_max_error": 0.0,
        "position_margin_recalculation_max_error": 0.0,
        "broker10_ratio_identity_max_error": 0.0,
        "broker10_multiplier_max_error": 0.0,
    }

    if positions.empty:
        position_changes = pd.Series(dtype=float)
        terminal_positions = pd.Series(dtype=float)
    else:
        required_positions = {"date", "vt_symbol", "start_pos", "end_pos", "pos_change", "close_price"}
        missing = required_positions.difference(positions.columns)
        if missing:
            raise ValueError(f"position integrity schema missing: {sorted(missing)}")
        positions["date"] = pd.to_datetime(positions["date"], errors="raise").dt.normalize()
        positions["vt_symbol"] = positions["vt_symbol"].astype(str)
        for column in ("start_pos", "end_pos", "pos_change", "close_price"):
            positions[column] = pd.to_numeric(positions[column], errors="raise").astype(float)
            if not np.isfinite(positions[column]).all():
                raise ValueError(f"non-finite position integrity column: {column}")
        result["position_duplicate_key_count"] = int(positions.duplicated(["date", "vt_symbol"]).sum())
        result["position_row_identity_max_error"] = _max_absolute(
            positions["end_pos"] - positions["start_pos"] - positions["pos_change"]
        )
        continuity_errors: list[float] = []
        for _, group in positions.sort_values(["vt_symbol", "date"]).groupby("vt_symbol", sort=True):
            previous_end = 0.0
            for row in group.itertuples(index=False):
                continuity_errors.append(float(row.start_pos) - previous_end)
                previous_end = float(row.end_pos)
        result["position_continuity_max_error"] = _max_absolute(continuity_errors)
        position_changes = positions.groupby(["date", "vt_symbol"])["pos_change"].sum()
        terminal_positions = (
            positions.sort_values(["vt_symbol", "date"]).groupby("vt_symbol", sort=True).tail(1).set_index("vt_symbol")["end_pos"]
        )
        result["terminal_open_contract_count"] = int(terminal_positions.abs().gt(1e-12).sum())

    if trades.empty:
        trade_changes = pd.Series(dtype=float)
        terminal_from_trades = pd.Series(dtype=float)
    else:
        required_trades = {"trade_id", "vt_symbol", "signed_volume"}
        missing = required_trades.difference(trades.columns)
        if missing or not ({"date", "datetime"} & set(trades.columns)):
            raise ValueError(f"trade integrity schema missing: {sorted(missing)} or date/datetime")
        trade_date_source = trades["date"] if "date" in trades.columns else trades["datetime"]
        trades["date"] = pd.to_datetime(trade_date_source, errors="raise").dt.normalize()
        trades["vt_symbol"] = trades["vt_symbol"].astype(str)
        trades["signed_volume"] = pd.to_numeric(trades["signed_volume"], errors="raise").astype(float)
        if not np.isfinite(trades["signed_volume"]).all():
            raise ValueError("non-finite trade signed volume")
        result["trade_duplicate_id_count"] = int(trades["trade_id"].astype(str).duplicated().sum())
        trade_changes = trades.groupby(["date", "vt_symbol"])["signed_volume"].sum()
        terminal_from_trades = trades.groupby("vt_symbol")["signed_volume"].sum()

    daily_reconciliation = pd.concat(
        [position_changes.rename("position_change"), trade_changes.rename("trade_change")],
        axis=1,
    ).fillna(0.0)
    result["daily_position_change_reconciliation_max_error"] = _max_absolute(
        daily_reconciliation.get("position_change", 0.0) - daily_reconciliation.get("trade_change", 0.0)
    )
    terminal_reconciliation = pd.concat(
        [terminal_positions.rename("terminal_position"), terminal_from_trades.rename("trade_position")],
        axis=1,
    ).fillna(0.0)
    result["terminal_position_reconciliation_max_error"] = _max_absolute(
        terminal_reconciliation.get("terminal_position", 0.0) - terminal_reconciliation.get("trade_position", 0.0)
    )

    required_daily = {
        "date",
        "account_equity",
        "c3_margin_exact",
        "total_margin_exact",
        "broker10_total_margin_exact",
        "broker10_margin_to_equity_pct",
    }
    missing_daily = required_daily.difference(daily.columns)
    if missing_daily:
        raise ValueError(f"daily integrity schema missing: {sorted(missing_daily)}")
    daily_integrity = daily.copy()
    daily_integrity["date"] = pd.to_datetime(daily_integrity["date"], errors="raise").dt.normalize()
    numeric_daily: dict[str, pd.Series] = {}
    for column in sorted(required_daily.difference({"date"})):
        values = pd.to_numeric(daily_integrity[column], errors="raise").astype(float)
        if not np.isfinite(values).all():
            raise ValueError(f"non-finite daily integrity column: {column}")
        numeric_daily[column] = values
    result["margin_identity_max_error"] = _max_absolute(
        numeric_daily["total_margin_exact"] - numeric_daily["c3_margin_exact"]
    )
    if positions.empty:
        recalculated_margin = pd.DataFrame(
            {"date": daily_integrity["date"], "recalculated_c3_margin_exact": 0.0}
        )
    else:
        sizes = metadata.get("sizes", {})
        margin_ratios = metadata.get("margin_ratios", {})
        missing_sizes = sorted(set(positions["vt_symbol"]).difference(sizes))
        missing_ratios = sorted(set(positions["vt_symbol"]).difference(margin_ratios))
        if missing_sizes or missing_ratios:
            raise ValueError(
                f"position margin metadata missing: sizes={missing_sizes} margin_ratios={missing_ratios}"
            )
        positions["size"] = positions["vt_symbol"].map(sizes).astype(float)
        positions["margin_ratio"] = positions["vt_symbol"].map(margin_ratios).astype(float)
        if (
            ~np.isfinite(positions[["size", "margin_ratio"]]).all().all()
            or positions["size"].le(0.0).any()
            or positions["margin_ratio"].lt(0.0).any()
        ):
            raise ValueError("invalid position margin metadata")
        positions["recalculated_c3_margin_exact"] = (
            positions["end_pos"].abs()
            * positions["close_price"]
            * positions["size"]
            * positions["margin_ratio"]
        )
        recalculated_margin = (
            positions.groupby("date", as_index=False)["recalculated_c3_margin_exact"].sum()
        )
    margin_comparison = daily_integrity[["date", "c3_margin_exact"]].merge(
        recalculated_margin,
        on="date",
        how="left",
        validate="one_to_one",
    )
    margin_comparison["recalculated_c3_margin_exact"] = pd.to_numeric(
        margin_comparison["recalculated_c3_margin_exact"], errors="coerce"
    ).fillna(0.0)
    result["position_margin_recalculation_max_error"] = _max_absolute(
        margin_comparison["c3_margin_exact"] - margin_comparison["recalculated_c3_margin_exact"]
    )
    result["broker10_multiplier_max_error"] = _max_absolute(
        numeric_daily["broker10_total_margin_exact"]
        - numeric_daily["total_margin_exact"] * BROKER10_MULTIPLIER
    )
    equity = numeric_daily["account_equity"]
    if equity.eq(0.0).any():
        result["broker10_ratio_identity_max_error"] = math.inf
    else:
        expected_ratio = numeric_daily["broker10_total_margin_exact"] / equity * 100.0
        result["broker10_ratio_identity_max_error"] = _max_absolute(
            numeric_daily["broker10_margin_to_equity_pct"] - expected_ratio
        )

    if not pending.empty:
        required_pending = {"vt_orderid", "vt_symbol", "direction", "offset", "volume", "traded", "status"}
        missing_pending = required_pending.difference(pending.columns)
        if missing_pending:
            raise ValueError(f"pending order integrity schema missing: {sorted(missing_pending)}")
        volume = pd.to_numeric(pending["volume"], errors="coerce").astype(float)
        traded = pd.to_numeric(pending["traded"], errors="coerce").astype(float)
        invalid_numeric = (
            ~np.isfinite(volume)
            | ~np.isfinite(traded)
            | volume.le(0.0)
            | traded.lt(0.0)
            | traded.gt(volume)
            | ~np.isclose(volume, np.round(volume))
            | ~np.isclose(traded, np.round(traded))
        )
        invalid_text = pd.Series(False, index=pending.index)
        for column in ("vt_orderid", "vt_symbol", "direction", "offset", "status"):
            invalid_text |= pending[column].fillna("").astype(str).str.strip().eq("")
        result["pending_order_invalid_count"] = int((invalid_numeric | invalid_text).sum())
        result["pending_order_duplicate_count"] = int(pending["vt_orderid"].astype(str).duplicated().sum())
    return result


def summarize_arm(
    daily: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    metadata: dict[str, Any],
    *,
    start_month: str,
    version: str,
) -> dict[str, Any]:
    data = daily.copy()
    data["date"] = pd.to_datetime(data["date"], errors="raise").dt.normalize()
    data = data.sort_values("date").reset_index(drop=True)
    equity = pd.to_numeric(data["account_equity"], errors="raise").astype(float)
    net_pnl = pd.to_numeric(data.get("net_pnl", 0.0), errors="raise").fillna(0.0)
    nonzero = net_pnl.abs().gt(1e-12)
    closed = build_closed_lots(frames, metadata)
    realized = pd.to_numeric(closed.get("realized_pnl", pd.Series(dtype=float)), errors="coerce").dropna()
    account_identity_error = float((equity - (CAPITAL + net_pnl.cumsum())).abs().max())
    broker10 = pd.to_numeric(
        data.get("broker10_margin_to_equity_pct", pd.Series(index=data.index, dtype=float)),
        errors="coerce",
    )
    result = {
        "requested_start_month": start_month,
        "version": version,
        "actual_start": data["date"].min().date().isoformat(),
        "actual_end": data["date"].max().date().isoformat(),
        "trading_days": int(len(data)),
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / CAPITAL - 1.0) * 100.0),
        "max_drawdown_pct": float(_drawdown_pct(equity).min()),
        "sharpe": _daily_sharpe(equity),
        "total_slippage": float(pd.to_numeric(data.get("slippage", 0.0), errors="coerce").fillna(0.0).sum()),
        "total_commission": float(
            pd.to_numeric(data.get("commission", 0.0), errors="coerce").fillna(0.0).sum()
        ),
        "total_trade_count": int(round(float(pd.to_numeric(data.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()))),
        "nonzero_daily_win_rate_pct": float((net_pnl[nonzero] > 0.0).mean() * 100.0) if nonzero.any() else 0.0,
        "closed_lot_count": int(len(realized)),
        "closed_lot_win_rate_pct": float((realized > 0.0).mean() * 100.0) if len(realized) else 0.0,
        "longest_underwater_days": _longest_underwater_days(data["date"], equity),
        "max_broker10_margin_to_equity_pct": float(broker10.max()) if broker10.notna().any() else math.nan,
        "min_equity": float(equity.min()),
        "bankrupt_count": int(equity.le(0.0).sum()),
        "account_identity_max_error": account_identity_error,
        "pending_order_count": int(len(frames.get("pending_orders", pd.DataFrame()))),
    }
    result.update(arm_integrity_audit(data, frames, metadata))
    return result


def runtime_mrc_audit(candidates: pd.DataFrame, *, start_month: str) -> dict[str, Any]:
    def empty_result(*, evidence_missing: int, schema_error: int) -> dict[str, Any]:
        return {
            "requested_start_month": start_month,
            "runtime_evidence_missing_count": int(evidence_missing),
            "runtime_schema_error_count": int(schema_error),
            "opened_rows": 0,
            "batch_count": 0,
            "available_batch_count": 0,
            "unavailable_batch_count": 0,
            "batch_id_missing_count": 0,
            "batch_partition_mismatch_count": 0,
            "mrc_available_invalid_count": 0,
            "unavailable_batches": "",
            "reduced_candidate_count": 0,
            "reduced_volume": 0,
            "after_gt_before_count": 0,
            "zeroed_count": 0,
            "final_selected_mismatch_count": 0,
            "available_non63_count": 0,
            "t1_violation_count": 0,
            "panel_sha_mismatch_count": 0,
            "scale_min": 1.0,
            "scale_median": 1.0,
        }

    data = candidates.copy()
    if data.empty:
        return empty_result(evidence_missing=1, schema_error=0)
    required_columns = {
        "candidate_status",
        "datetime",
        "selected_volume",
        "mrc_available",
        "mrc_batch_id",
        "mrc_panel_sha256",
        "mrc_observation_count",
        "mrc_observation_end",
        "mrc_selected_volume_before",
        "mrc_selected_volume_after",
        "mrc_volume_reduced",
        "mrc_scale",
    }
    if required_columns.difference(data.columns):
        return empty_result(evidence_missing=1, schema_error=1)
    numeric_columns = (
        "selected_volume",
        "mrc_available",
        "mrc_observation_count",
        "mrc_selected_volume_before",
        "mrc_selected_volume_after",
        "mrc_volume_reduced",
    )
    for column in numeric_columns:
        numeric = pd.to_numeric(data[column], errors="coerce")
        if (
            numeric.isna().any()
            or not np.isfinite(numeric).all()
            or not np.isclose(numeric, np.round(numeric)).all()
        ):
            return empty_result(evidence_missing=1, schema_error=1)
        data[column] = numeric.astype(int)
    scale = pd.to_numeric(data["mrc_scale"], errors="coerce")
    if scale.isna().any() or not np.isfinite(scale).all():
        return empty_result(evidence_missing=1, schema_error=1)
    data["mrc_scale"] = scale.astype(float)
    opened = data[
        data["candidate_status"].astype(str).eq("opened") & data["mrc_selected_volume_before"].gt(0)
    ].copy()
    if opened.empty:
        return empty_result(evidence_missing=1, schema_error=0)
    opened["local_date"] = _local_date_series(opened["datetime"])
    opened["observation_end"] = pd.to_datetime(opened["mrc_observation_end"], errors="coerce").dt.normalize()
    available = opened[opened["mrc_available"].eq(1)].copy()
    unavailable = opened[opened["mrc_available"].eq(0)].copy()
    batch_ids = opened["mrc_batch_id"].fillna("").astype(str).str.strip()
    valid_batch_ids = batch_ids.replace("", np.nan)
    batch_count = int(valid_batch_ids.nunique())
    available_batch_count = int(available["mrc_batch_id"].replace("", np.nan).nunique())
    unavailable_batch_count = int(unavailable["mrc_batch_id"].replace("", np.nan).nunique())
    mixed_batch_count = int(
        opened.assign(_batch_id=batch_ids)
        .loc[batch_ids.ne("")]
        .groupby("_batch_id")["mrc_available"]
        .nunique()
        .gt(1)
        .sum()
    )
    panel_sha_mismatch = int(
        opened["mrc_panel_sha256"].astype(str).ne(sha256_file(PANEL_PATH)).sum()
    )
    return {
        "requested_start_month": start_month,
        "runtime_evidence_missing_count": 0,
        "runtime_schema_error_count": 0,
        "opened_rows": int(len(opened)),
        "batch_count": batch_count,
        "available_batch_count": available_batch_count,
        "unavailable_batch_count": unavailable_batch_count,
        "batch_id_missing_count": int(batch_ids.eq("").sum()),
        "batch_partition_mismatch_count": int(
            abs(batch_count - available_batch_count - unavailable_batch_count) + mixed_batch_count
        ),
        "mrc_available_invalid_count": int((~opened["mrc_available"].isin([0, 1])).sum()),
        "unavailable_batches": "/".join(sorted(set(unavailable["mrc_batch_id"].astype(str)))),
        "reduced_candidate_count": int(opened["mrc_volume_reduced"].gt(0).sum()),
        "reduced_volume": int(opened["mrc_volume_reduced"].sum()),
        "after_gt_before_count": int(
            opened["mrc_selected_volume_after"].gt(opened["mrc_selected_volume_before"]).sum()
        ),
        "zeroed_count": int(opened["mrc_selected_volume_after"].le(0).sum()),
        "final_selected_mismatch_count": int(
            opened["selected_volume"].ne(opened["mrc_selected_volume_after"]).sum()
        ),
        "available_non63_count": int(available["mrc_observation_count"].ne(LOOKBACK_DAYS).sum()),
        "t1_violation_count": int(
            (available["observation_end"].isna() | available["observation_end"].ge(available["local_date"])).sum()
        ),
        "panel_sha_mismatch_count": panel_sha_mismatch,
        "scale_min": float(pd.to_numeric(available.get("mrc_scale", 1.0), errors="coerce").min())
        if len(available)
        else 1.0,
        "scale_median": float(pd.to_numeric(available.get("mrc_scale", 1.0), errors="coerce").median())
        if len(available)
        else 1.0,
    }


def golden_reproduction_audit(summary: pd.DataFrame) -> pd.DataFrame:
    tolerances = {
        "end_equity": 1e-4,
        "total_return_pct": 1e-5,
        "max_drawdown_pct": 1e-5,
        "sharpe": 1e-5,
        "total_slippage": 1e-4,
        "total_trade_count": 0.0,
        "nonzero_daily_win_rate_pct": 1e-5,
        "longest_underwater_days": 0.0,
    }
    rows: list[dict[str, Any]] = []
    control = summary[summary["version"].eq(A_VERSION)].set_index("requested_start_month")
    for start, expected in GOLDEN_A.items():
        actual = control.loc[start]
        for field, expected_value in expected.items():
            actual_value = float(actual[field])
            error = abs(actual_value - float(expected_value))
            rows.append(
                {
                    "requested_start_month": start,
                    "field": field,
                    "expected": expected_value,
                    "actual": actual_value,
                    "absolute_error": error,
                    "tolerance": tolerances[field],
                    "pass": int(error <= tolerances[field]),
                }
            )
    return pd.DataFrame(rows)


def evaluate_canary(
    summary: pd.DataFrame,
    runtime_audit: pd.DataFrame,
    golden_audit: pd.DataFrame,
    *,
    source_pass: bool,
) -> dict[str, Any]:
    failed: list[str] = []
    retention: dict[str, float] = {}

    def decision() -> dict[str, Any]:
        unique_failed = list(dict.fromkeys(failed))
        return {
            "mode": "canary",
            "canary_pass": not unique_failed,
            "failed_checks": unique_failed,
            "return_retention_pct": retention,
            "full_allowed": not unique_failed,
            "cost_stress_allowed": not unique_failed,
            "promotion_allowed": False,
            "promotion_note": "canary success only permits full/cost validation; it never promotes directly",
        }

    if not source_pass:
        failed.append("source_identity_failed")
    if "pass" not in golden_audit.columns or golden_audit.empty:
        failed.append("golden_schema_failed")
    else:
        golden_pass = pd.to_numeric(golden_audit["pass"], errors="coerce")
        if not np.isfinite(golden_pass).all() or not golden_pass.eq(1).all():
            failed.append("a_golden_reproduction_failed")

    summary_numeric_columns = {
        "total_return_pct",
        "max_drawdown_pct",
        "longest_underwater_days",
        "max_broker10_margin_to_equity_pct",
        "bankrupt_count",
        "account_identity_max_error",
        "pending_order_count",
        "pending_order_invalid_count",
        "pending_order_duplicate_count",
        "position_duplicate_key_count",
        "trade_duplicate_id_count",
        "position_continuity_max_error",
        "position_row_identity_max_error",
        "daily_position_change_reconciliation_max_error",
        "terminal_position_reconciliation_max_error",
        "margin_identity_max_error",
        "position_margin_recalculation_max_error",
        "broker10_ratio_identity_max_error",
        "broker10_multiplier_max_error",
    }
    summary_required = {"requested_start_month", "version", *summary_numeric_columns}
    runtime_numeric_columns = {
        "runtime_evidence_missing_count",
        "runtime_schema_error_count",
        "opened_rows",
        "batch_count",
        "available_batch_count",
        "unavailable_batch_count",
        "batch_id_missing_count",
        "batch_partition_mismatch_count",
        "mrc_available_invalid_count",
        "after_gt_before_count",
        "zeroed_count",
        "final_selected_mismatch_count",
        "available_non63_count",
        "t1_violation_count",
        "panel_sha_mismatch_count",
    }
    runtime_required = {"requested_start_month", *runtime_numeric_columns}
    if summary_required.difference(summary.columns):
        failed.append("summary_schema_missing")
    if runtime_required.difference(runtime_audit.columns):
        failed.append("runtime_schema_missing")
    if "summary_schema_missing" in failed or "runtime_schema_missing" in failed:
        return decision()

    summary = summary.copy()
    runtime_audit = runtime_audit.copy()
    expected_arms = {(start, version) for start in CANARY_STARTS for version in (A_VERSION, C_VERSION)}
    summary_pairs = list(
        zip(
            summary["requested_start_month"].astype(str),
            summary["version"].astype(str),
            strict=True,
        )
    )
    if len(summary_pairs) != len(expected_arms) or len(set(summary_pairs)) != len(summary_pairs) or set(summary_pairs) != expected_arms:
        failed.append("summary_arm_coverage_failed")
    runtime_starts = runtime_audit["requested_start_month"].astype(str).tolist()
    if len(runtime_starts) != len(CANARY_STARTS) or len(set(runtime_starts)) != len(runtime_starts) or set(runtime_starts) != set(CANARY_STARTS):
        failed.append("runtime_anchor_coverage_failed")
    if "summary_arm_coverage_failed" in failed or "runtime_anchor_coverage_failed" in failed:
        return decision()

    for column in summary_numeric_columns:
        summary[column] = pd.to_numeric(summary[column], errors="coerce")
    for column in runtime_numeric_columns:
        runtime_audit[column] = pd.to_numeric(runtime_audit[column], errors="coerce")
    if not np.isfinite(summary[list(summary_numeric_columns)].to_numpy(dtype=float)).all():
        failed.append("summary_nonfinite")
    if not np.isfinite(runtime_audit[list(runtime_numeric_columns)].to_numpy(dtype=float)).all():
        failed.append("runtime_nonfinite")
    if "summary_nonfinite" in failed or "runtime_nonfinite" in failed:
        return decision()

    if not golden_audit.empty and len(golden_audit) != sum(len(values) for values in GOLDEN_A.values()):
        failed.append("a_golden_reproduction_failed")
    if (summary["bankrupt_count"] > 0).any():
        failed.append("bankruptcy")
    if (summary["account_identity_max_error"] > 1e-6).any():
        failed.append("account_identity_failed")
    if (summary["pending_order_count"] > 0).any():
        failed.append("pending_orders_not_closed")
    if summary[["pending_order_invalid_count", "pending_order_duplicate_count"]].gt(0).any().any():
        failed.append("pending_order_integrity_failed")
    if summary[["position_duplicate_key_count", "trade_duplicate_id_count"]].gt(0).any().any():
        failed.append("position_trade_key_integrity_failed")
    if (summary["position_continuity_max_error"] > 1e-6).any():
        failed.append("position_continuity_failed")
    if (summary["position_row_identity_max_error"] > 1e-6).any():
        failed.append("position_row_identity_failed")
    if (summary["daily_position_change_reconciliation_max_error"] > 1e-6).any():
        failed.append("daily_position_change_reconciliation_failed")
    if (summary["terminal_position_reconciliation_max_error"] > 1e-6).any():
        failed.append("terminal_position_reconciliation_failed")
    if (summary["margin_identity_max_error"] > 1e-6).any():
        failed.append("margin_reconciliation_failed")
    if (summary["position_margin_recalculation_max_error"] > 1e-6).any():
        failed.append("position_margin_recalculation_failed")
    if (summary["broker10_ratio_identity_max_error"] > 1e-6).any():
        failed.append("broker10_ratio_reconciliation_failed")
    if (summary["broker10_multiplier_max_error"] > 1e-6).any():
        failed.append("broker10_multiplier_reconciliation_failed")
    if (
        runtime_audit["runtime_evidence_missing_count"].gt(0).any()
        or runtime_audit["runtime_schema_error_count"].gt(0).any()
        or runtime_audit["opened_rows"].le(0).any()
        or runtime_audit["batch_count"].le(0).any()
    ):
        failed.append("mrc_runtime_evidence_missing")
    runtime_zero_columns = [
        "batch_id_missing_count",
        "batch_partition_mismatch_count",
        "mrc_available_invalid_count",
        "after_gt_before_count",
        "zeroed_count",
        "final_selected_mismatch_count",
        "available_non63_count",
        "t1_violation_count",
        "panel_sha_mismatch_count",
    ]
    if not runtime_audit[runtime_zero_columns].eq(0).all().all() or not (
        runtime_audit["available_batch_count"] + runtime_audit["unavailable_batch_count"]
    ).eq(runtime_audit["batch_count"]).all():
        failed.append("mrc_runtime_contract_failed")

    controls = summary[summary["version"].eq(A_VERSION)].set_index("requested_start_month")
    candidates = summary[summary["version"].eq(C_VERSION)].set_index("requested_start_month")
    for start in CANARY_STARTS:
        a = controls.loc[start]
        c = candidates.loc[start]
        control_return = float(a["total_return_pct"])
        ratio = float(c["total_return_pct"] / control_return * 100.0) if control_return > 0.0 else math.nan
        retention[start] = ratio
        if not math.isfinite(ratio):
            failed.append(f"return_retention_nonfinite:{start}")
        elif ratio < 70.0 - 1e-9:
            failed.append(f"return_retention_below_70:{start}")
        if float(c["max_broker10_margin_to_equity_pct"]) > float(a["max_broker10_margin_to_equity_pct"]) + 1e-9:
            failed.append(f"broker10_worse:{start}")
    for start in ("2020-01", "2022-01", "2022-07"):
        if float(candidates.loc[start, "max_drawdown_pct"]) <= float(controls.loc[start, "max_drawdown_pct"]) + 1e-9:
            failed.append(f"historical_drawdown_not_strictly_better:{start}")
    for start in ("2022-01", "2022-07"):
        if int(candidates.loc[start, "longest_underwater_days"]) >= int(
            controls.loc[start, "longest_underwater_days"]
        ):
            failed.append(f"2022_underwater_not_strictly_better:{start}")
    if float(candidates.loc["2026-01", "max_drawdown_pct"]) < float(
        controls.loc["2026-01", "max_drawdown_pct"]
    ) - 1.0:
        failed.append("latest_drawdown_worse_over_1pp")
    return decision()


def frame_output_path(start_month: str, version: str, name: str) -> Path:
    arm = "a" if version == A_VERSION else "c"
    start = start_month.replace("-", "")
    return OUT / f"{OUTPUT_PREFIX}_{start}_{arm}_{name}_{MODEL_TAG}.csv.gz"


def write_gzip_frame(frame: pd.DataFrame, path: Path) -> None:
    data = frame.copy()
    if data.empty and len(data.columns) == 0:
        data = pd.DataFrame({"_empty": pd.Series(dtype="int64")})
    data.to_csv(
        path,
        index=False,
        encoding="utf-8-sig",
        lineterminator="\n",
        float_format="%.17g",
        compression={"method": "gzip", "compresslevel": 6, "mtime": 0},
    )


def validate_stage137_source_manifest() -> pd.DataFrame:
    manifest = pd.read_csv(STAGE137_SOURCE_MANIFEST_PATH, encoding="utf-8-sig")
    required = {"path", "size", "sha256"}
    if required.difference(manifest.columns):
        raise ValueError("Stage137 source manifest schema mismatch")
    rows: list[dict[str, Any]] = []
    for source in manifest.itertuples(index=False):
        path = Path(str(source.path))
        current = file_snapshot(path)
        rows.append(
            {
                "path": str(path.resolve()),
                "expected_size": int(source.size),
                "actual_size": current["size"],
                "expected_sha256": str(source.sha256),
                "actual_sha256": current["sha256"],
                "size_match": int(int(source.size) == current["size"]),
                "sha256_match": int(str(source.sha256) == current["sha256"]),
            }
        )
    audit = pd.DataFrame(rows)
    if not audit[["size_match", "sha256_match"]].eq(1).all().all():
        raise RuntimeError("Stage137 frozen source manifest drifted")
    return audit


def environment_audit() -> dict[str, Any]:
    required_env = {
        "PYTHONHASHSEED": "0",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "TZ": "Asia/Shanghai",
    }
    values = {name: os.environ.get(name, "") for name in required_env}
    mismatch = {name: {"expected": expected, "actual": values[name]} for name, expected in required_env.items() if values[name] != expected}
    result = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "sklearn": sklearn.__version__,
        "required_env": required_env,
        "actual_env": values,
        "mismatch": mismatch,
        "pass": not mismatch,
    }
    if mismatch:
        raise RuntimeError(f"deterministic environment mismatch: {mismatch}")
    return result


def plot_canary(curves: dict[tuple[str, str], pd.DataFrame]) -> None:
    colors = {"2020-01": "#2563eb", "2022-01": "#dc2626", "2022-07": "#16a34a", "2026-01": "#9333ea"}
    fig, axes = plt.subplots(2, 1, figsize=(16, 10), sharex=True)
    for start in CANARY_STARTS:
        for version, style, label in ((A_VERSION, "-", "A"), (C_VERSION, "--", "C")):
            frame = curves[(start, version)].sort_values("date")
            equity = pd.to_numeric(frame["account_equity"], errors="raise")
            axes[0].plot(frame["date"], equity / CAPITAL, color=colors[start], linestyle=style, linewidth=1.2, label=f"{start} {label}")
            axes[1].plot(frame["date"], _drawdown_pct(equity), color=colors[start], linestyle=style, linewidth=1.1, label=f"{start} {label}")
    axes[0].axhline(1.0, color="#64748b", linestyle=":", linewidth=0.8)
    axes[0].set_title("Stage001 Candidate MRC: Normalized Equity")
    axes[0].set_ylabel("equity / 150k")
    axes[1].set_title("Drawdown")
    axes[1].set_ylabel("drawdown %")
    axes[1].set_xlabel("date")
    for axis in axes:
        axis.grid(alpha=0.25)
        axis.legend(ncol=4, fontsize=8)
    fig.tight_layout()
    fig.savefig(NORMALIZED_CHART_PATH, dpi=170)
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(16, 10), sharex=False)
    for axis, start in zip(axes.flat, CANARY_STARTS, strict=True):
        for version, style, label in ((A_VERSION, "-", "A"), (C_VERSION, "--", "C")):
            frame = curves[(start, version)].sort_values("date")
            axis.plot(frame["date"], frame["account_equity"], linestyle=style, linewidth=1.25, label=label)
        axis.axhline(CAPITAL, color="#64748b", linestyle=":", linewidth=0.8)
        axis.set_title(start)
        axis.grid(alpha=0.25)
        axis.legend()
    fig.suptitle("Stage001 Candidate MRC: Absolute Equity by Start")
    fig.tight_layout()
    fig.savefig(ABSOLUTE_CHART_PATH, dpi=170)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(16, 9), sharex=True)
    for start, color in (("2022-01", "#dc2626"), ("2022-07", "#16a34a")):
        for version, style, label in ((A_VERSION, "-", "A"), (C_VERSION, "--", "C")):
            frame = curves[(start, version)].sort_values("date")
            equity = pd.to_numeric(frame["account_equity"], errors="raise")
            axes[0].plot(frame["date"], equity / CAPITAL, color=color, linestyle=style, label=f"{start} {label}")
            axes[1].plot(frame["date"], _drawdown_pct(equity), color=color, linestyle=style, label=f"{start} {label}")
    axes[0].set_title("2022 Starts: Normalized Equity")
    axes[1].set_title("2022 Starts: Drawdown")
    for axis in axes:
        axis.grid(alpha=0.25)
        axis.legend()
    fig.tight_layout()
    fig.savefig(FOCUS_2022_CHART_PATH, dpi=170)
    plt.close(fig)


def write_report(summary: pd.DataFrame, runtime: pd.DataFrame, decision: dict[str, Any]) -> None:
    columns = [
        "requested_start_month",
        "version",
        "end_equity",
        "total_return_pct",
        "max_drawdown_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "closed_lot_win_rate_pct",
        "longest_underwater_days",
        "max_broker10_margin_to_equity_pct",
    ]
    lines = [
        "# Stage001 候选边际风险贡献四锚点 1x canary",
        "",
        f"- decision: `{decision['canary_pass']}`",
        f"- failed checks: `{decision['failed_checks']}`",
        f"- full allowed: `{decision['full_allowed']}`",
        f"- return retention: `{decision['return_retention_pct']}`",
        "- 手续费说明：当前 metadata rate 为0时，本结果是非负手续费下的收益上界。",
        "",
        "## 绩效",
        "",
        summary[columns].to_markdown(index=False, floatfmt=".6f"),
        "",
        "## MRC 运行审计",
        "",
        runtime.to_markdown(index=False, floatfmt=".6f"),
        "",
        "## 结论边界",
        "",
        "- canary 失败：路线立即关闭，不运行 full/2x/3x，不改63日、LedoitWolf、RC公式、floor/min1或产品规则。",
        "- canary 通过：只允许进入逐半年和成本压力，不直接晋级正式版。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_canary(*, expected_review_manifest_sha256: str) -> dict[str, Any]:
    env = environment_audit()
    review_before = validate_review_manifest(
        REVIEW_MANIFEST_PATH,
        expected_manifest_sha256=expected_review_manifest_sha256,
    )
    review_manifest_before = file_snapshot(REVIEW_MANIFEST_PATH)
    env.update(
        {
            "review_manifest_path": str(REVIEW_MANIFEST_PATH.resolve()),
            "review_manifest_expected_sha256": str(expected_review_manifest_sha256),
            "review_manifest_actual_sha256": str(review_manifest_before["sha256"]),
        }
    )
    OUT.mkdir(parents=True, exist_ok=True)
    ENVIRONMENT_AUDIT_PATH.write_text(json.dumps(env, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    static = prepare_static_inputs()
    panel_sha = str(static["panel_sha256"])
    source_before = validate_stage137_source_manifest()

    a_eligibility = s006._official_eligibility_for_strategy(A_STRATEGY, "current_official_ai_control")
    c_eligibility = s006._official_eligibility_for_strategy(C_STRATEGY, "current_official_ai_candidate_mrc")
    a_eligibility.to_csv(A_ELIGIBILITY_PATH, index=False, encoding="utf-8-sig", lineterminator="\n")
    c_eligibility.to_csv(C_ELIGIBILITY_PATH, index=False, encoding="utf-8-sig", lineterminator="\n")

    metadata = s006._metadata()
    a_profile = build_profile(metadata, candidate=False, eligibility_path=A_ELIGIBILITY_PATH, panel_sha256=panel_sha)
    c_profile = build_profile(metadata, candidate=True, eligibility_path=C_ELIGIBILITY_PATH, panel_sha256=panel_sha)
    summaries: list[dict[str, Any]] = []
    runtime_rows: list[dict[str, Any]] = []
    curves: dict[tuple[str, str], pd.DataFrame] = {}
    for start in CANARY_STARTS:
        for version, profile in ((A_VERSION, a_profile), (C_VERSION, c_profile)):
            print(f"RUN {start} {version}", flush=True)
            daily, frames = run_arm(metadata, profile, start_month=start, version=version)
            curves[(start, version)] = daily.copy()
            summaries.append(summarize_arm(daily, frames, metadata, start_month=start, version=version))
            write_gzip_frame(daily, frame_output_path(start, version, "daily"))
            for name in (
                "trades",
                "positions",
                "entry_risk",
                "entry_candidates",
                "trade_events",
                "intraday_events",
                "c2_events",
                "stop_retry_events",
                "pending_orders",
            ):
                write_gzip_frame(frames.get(name, pd.DataFrame()), frame_output_path(start, version, name))
            closed = build_closed_lots(frames, metadata)
            write_gzip_frame(closed, frame_output_path(start, version, "closed_lots"))
            if version == C_VERSION:
                runtime_rows.append(runtime_mrc_audit(frames.get("entry_candidates", pd.DataFrame()), start_month=start))
            print(f"DONE {start} {version}", flush=True)

    source_after = validate_stage137_source_manifest()
    review_after = validate_review_manifest(
        REVIEW_MANIFEST_PATH,
        expected_manifest_sha256=expected_review_manifest_sha256,
    )
    review_manifest_after = file_snapshot(REVIEW_MANIFEST_PATH)
    source_audit = source_before.merge(
        source_after[["path", "actual_size", "actual_sha256"]],
        on="path",
        suffixes=("_before", "_after"),
        validate="one_to_one",
    )
    source_audit = source_audit.rename(
        columns={"size_match": "size_match_before", "sha256_match": "sha256_match_before"}
    )
    source_audit["post_run_size_match"] = source_audit["actual_size_before"].eq(source_audit["actual_size_after"]).astype(int)
    source_audit["post_run_sha256_match"] = source_audit["actual_sha256_before"].eq(source_audit["actual_sha256_after"]).astype(int)
    review_audit = review_before.merge(
        review_after[["path", "actual_size", "actual_sha256"]],
        on="path",
        suffixes=("_before", "_after"),
        validate="one_to_one",
    )
    review_audit = review_audit.rename(
        columns={"size_match": "size_match_before", "sha256_match": "sha256_match_before"}
    )
    review_audit["post_run_size_match"] = review_audit["actual_size_before"].eq(
        review_audit["actual_size_after"]
    ).astype(int)
    review_audit["post_run_sha256_match"] = review_audit["actual_sha256_before"].eq(
        review_audit["actual_sha256_after"]
    ).astype(int)
    manifest_audit = pd.DataFrame(
        [
            {
                "path": str(REVIEW_MANIFEST_PATH.resolve()),
                "expected_size": int(review_manifest_before["size"]),
                "actual_size_before": int(review_manifest_before["size"]),
                "actual_size_after": int(review_manifest_after["size"]),
                "expected_sha256": str(expected_review_manifest_sha256),
                "actual_sha256_before": str(review_manifest_before["sha256"]),
                "actual_sha256_after": str(review_manifest_after["sha256"]),
                "size_match_before": 1,
                "sha256_match_before": int(
                    str(review_manifest_before["sha256"]) == str(expected_review_manifest_sha256)
                ),
                "post_run_size_match": int(review_manifest_before["size"] == review_manifest_after["size"]),
                "post_run_sha256_match": int(
                    review_manifest_before["sha256"] == review_manifest_after["sha256"]
                ),
            }
        ]
    )
    source_columns = [
        "path",
        "expected_size",
        "actual_size_before",
        "actual_size_after",
        "expected_sha256",
        "actual_sha256_before",
        "actual_sha256_after",
        "size_match_before",
        "sha256_match_before",
        "post_run_size_match",
        "post_run_sha256_match",
    ]
    source_audit = pd.concat(
        [source_audit[source_columns], review_audit[source_columns], manifest_audit[source_columns]],
        ignore_index=True,
    ).drop_duplicates("path", keep="last")
    source_audit.to_csv(CANARY_SOURCE_AUDIT_PATH, index=False, encoding="utf-8-sig", lineterminator="\n")
    source_pass = bool(
        source_audit[["size_match_before", "sha256_match_before", "post_run_size_match", "post_run_sha256_match"]]
        .eq(1)
        .all()
        .all()
    )

    summary = pd.DataFrame(summaries)
    runtime = pd.DataFrame(runtime_rows)
    golden = golden_reproduction_audit(summary)
    decision = evaluate_canary(summary, runtime, golden, source_pass=source_pass)
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig", lineterminator="\n", float_format="%.17g")
    runtime.to_csv(RUNTIME_AUDIT_PATH, index=False, encoding="utf-8-sig", lineterminator="\n", float_format="%.17g")
    golden.to_csv(GOLDEN_AUDIT_PATH, index=False, encoding="utf-8-sig", lineterminator="\n", float_format="%.17g")
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    plot_canary(curves)
    write_report(summary, runtime, decision)
    return {"summary": summary, "runtime": runtime, "golden": golden, "decision": decision}


def prepare_static_inputs() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    panel, manifest, audit = build_frozen_return_panel()
    panel.to_csv(PANEL_PATH, index=False, encoding="utf-8-sig", lineterminator="\n", float_format="%.17g")
    panel_sha = sha256_file(PANEL_PATH)
    audit["panel_sha256"] = panel_sha
    candidates = pd.read_csv(STAGE006_CANDIDATES_PATH, encoding="utf-8-sig")
    trades = pd.read_csv(STAGE006_TRADES_PATH, encoding="utf-8-sig")
    batch_audit = audit_baseline_batch_readiness(panel, candidates, trades)
    batch_audit.to_csv(BASELINE_BATCH_AUDIT_PATH, index=False, encoding="utf-8-sig", lineterminator="\n")
    audit.update(
        {
            "baseline_opened_candidate_rows": int(
                (
                    candidates["candidate_status"].astype(str).eq("opened")
                    & pd.to_numeric(candidates["selected_volume"], errors="raise").gt(0)
                ).sum()
            ),
            "baseline_batch_count": int(len(batch_audit)),
            "baseline_available_batch_count": int(batch_audit["available"].sum()),
            "baseline_unavailable_batch_count": int(batch_audit["available"].eq(0).sum()),
            "baseline_unavailable_batches": batch_audit.loc[
                batch_audit["available"].eq(0),
                ["candidate_date", "candidate_contracts", "observation_count", "reason"],
            ].to_dict("records"),
        }
    )
    manifest.to_csv(SOURCE_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    DATA_AUDIT_PATH.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "panel": panel,
        "manifest": manifest,
        "audit": audit,
        "batch_audit": batch_audit,
        "panel_sha256": panel_sha,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("static", "canary"), default="static")
    parser.add_argument("--review-manifest-sha256", default="")
    args = parser.parse_args()
    if args.mode == "static":
        outputs = prepare_static_inputs()
        print(json.dumps(outputs["audit"], ensure_ascii=False, indent=2))
        print(f"panel={PANEL_PATH}")
        return
    if not args.review_manifest_sha256:
        parser.error("--review-manifest-sha256 is required for canary mode")
    outputs = run_canary(expected_review_manifest_sha256=args.review_manifest_sha256)
    print(outputs["summary"].to_string(index=False))
    print(outputs["runtime"].to_string(index=False))
    print(json.dumps(outputs["decision"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
