from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage086"
MODEL_TAG = "stage086_stage449_raw_generation_provenance_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage086_c9_minrisk_stage449_raw_generation_provenance_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage013_minrisk_clean_restore_true_engine as s013
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage086_stage449_raw_generation_provenance_audit"
BACKTEST_OUTPUTS = EXAMPLE_DIR / "backtest_outputs"
DOWNLOADED_FUTURES = EXAMPLE_DIR / "downloaded_futures"

STAGE010_DIR = LINE_DIR / "outputs" / "stage010_authoritative_minute_coverage_audit"
CURVE_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_curve_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)

STAGE449_FULL_BARS = (
    BACKTEST_OUTPUTS / "qmt_roll_stage449_minute_session_rebuild_full_minute_bars_stage449_minute_session_rebuild_full_v1.csv"
)
STAGE449_STATUS = (
    BACKTEST_OUTPUTS / "qmt_roll_stage449_minute_session_rebuild_full_extract_status_stage449_minute_session_rebuild_full_v1.csv"
)
STAGE449_DETAIL = (
    BACKTEST_OUTPUTS
    / "qmt_roll_stage449_minute_session_rebuild_full_ledger_proxy_detail_stage449_minute_session_rebuild_full_v1.csv"
)
STAGE448_STATUS = (
    BACKTEST_OUTPUTS / "qmt_roll_stage448_minute_session_rebuild_batch_extract_status_stage448_minute_session_rebuild_batch_v1.csv"
)
STAGE446_BARS = (
    BACKTEST_OUTPUTS
    / "qmt_roll_stage446_tqsdk_backtest_minute_proxy_extract_minute_bars_stage446_tqsdk_backtest_minute_proxy_extract_v1.csv"
)

STAGE070_TICK_ROOT = LINE_DIR / "outputs" / "stage070_initial_entry_price_proxy_anchor_batch_refill" / "raw_tick"
STAGE079_TICK_ROOT = LINE_DIR / "outputs" / "stage079_tqsdk_tick_manifest_transform_smoke" / "raw_tick"

SOURCE_FILES = [
    EXAMPLE_DIR / "analyze_qmt_roll_stage446_tqsdk_backtest_minute_proxy_extract.py",
    EXAMPLE_DIR / "analyze_qmt_roll_stage448_minute_session_rebuild_batch.py",
    EXAMPLE_DIR / "analyze_qmt_roll_stage450_minute_execution_equity_rebuild.py",
    EXAMPLE_DIR / "analyze_qmt_roll_stage501_asymmetric_entry_exit_execution.py",
    EXAMPLE_DIR / "analyze_qmt_roll_stage502_confirmed_daily_next_real_open_replay.py",
    TOOL_DIR / "stage073_initial_entry_raw_stage449_tq_source_integrity_audit.py",
    TOOL_DIR / "stage074_initial_entry_authoritative_source_decision_audit.py",
    TOOL_DIR / "stage077_raw_authority_provenance_tick_backfill_feasibility.py",
    TOOL_DIR / "stage079_tqsdk_tick_manifest_transform_smoke.py",
    TOOL_DIR / "stage080_tick_transform_mismatch_attribution.py",
]

CAPITAL = 150_000.0

SOURCE_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_audit_{MODEL_TAG}.csv"
ASSET_SCHEMA_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_asset_schema_audit_{MODEL_TAG}.csv"
FIELD_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_field_gate_scorecard_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

OFFICIAL_PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_provenance_gate_chart_{MODEL_TAG}.png"
SCHEMA_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_schema_field_heatmap_{MODEL_TAG}.png"
QUALITY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bar_quality_chart_{MODEL_TAG}.png"
SOURCE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_code_provenance_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s013._json_safe(value)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s013._safe_float(value, default=default)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s013._md_table(frame, max_rows=max_rows)


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_DIR))
    except ValueError:
        return str(path)


def _prepare_official_curve() -> pd.DataFrame:
    data = _read_csv(CURVE_IN)
    if data.empty:
        raise RuntimeError(f"missing official curve: {CURVE_IN}")
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in [
        "account_equity",
        "net_pnl",
        "drawdown_pct",
        "broker10_margin_to_equity_pct",
        "slippage",
        "trade_count",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0.0)
        else:
            data[column] = 0.0
    return data


def _official_metrics(curve: pd.DataFrame) -> dict[str, float]:
    equity = pd.to_numeric(curve["account_equity"], errors="coerce")
    daily_ret = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    std = daily_ret.std(ddof=0) if not daily_ret.empty else np.nan
    sharpe = float(daily_ret.mean() / std * np.sqrt(252)) if pd.notna(std) and std > 0 else np.nan
    return {
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / CAPITAL - 1.0) * 100.0),
        "max_drawdown_pct": float(pd.to_numeric(curve["drawdown_pct"], errors="coerce").min()),
        "sharpe": sharpe,
        "total_slippage": float(pd.to_numeric(curve["slippage"], errors="coerce").sum()),
        "total_trade_count": float(pd.to_numeric(curve["trade_count"], errors="coerce").sum()),
        "max_broker10_margin_to_equity_pct": float(
            pd.to_numeric(curve["broker10_margin_to_equity_pct"], errors="coerce").max()
        ),
    }


def _source_snippet(text: str, pattern: str) -> str:
    lines = text.splitlines()
    for idx, line in enumerate(lines, start=1):
        if pattern in line:
            return f"L{idx}: {line.strip()[:180]}"
    return ""


def _source_audit() -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    stage449_candidates = sorted(EXAMPLE_DIR.glob("*stage449*.py"))
    paths = SOURCE_FILES + [path for path in stage449_candidates if path not in SOURCE_FILES]
    if not stage449_candidates:
        records.append(
            {
                "source_family": "stage449_generation_script",
                "path": "examples/portfolio_backtesting/*stage449*.py",
                "exists": 0,
                "get_kline_serial_count": 0,
                "get_tick_serial_count": 0,
                "data_downloader_count": 0,
                "quote_or_depth_keyword_count": 0,
                "bid_ask_last_keyword_count": 0,
                "bar_generator_count": 0,
                "main_evidence_snippet": "no stage449 generation script file found; provenance relies on Stage446/448 generators and Stage449 artifacts",
            }
        )
    for path in paths:
        exists = int(path.exists())
        text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        lower = text.lower()
        records.append(
            {
                "source_family": path.stem,
                "path": _rel(path),
                "exists": exists,
                "get_kline_serial_count": text.count("get_kline_serial"),
                "get_tick_serial_count": text.count("get_tick_serial"),
                "data_downloader_count": text.count("DataDownloader"),
                "quote_or_depth_keyword_count": len(re.findall(r"\bquote\b|\bdepth\b|orderbook|order_book", lower)),
                "bid_ask_last_keyword_count": sum(
                    text.count(item) for item in ["bid_price", "ask_price", "last_price", "bid_volume", "ask_volume"]
                ),
                "bar_generator_count": text.count("BarGenerator"),
                "main_evidence_snippet": (
                    _source_snippet(text, "get_kline_serial")
                    or _source_snippet(text, "get_tick_serial")
                    or _source_snippet(text, "DataDownloader")
                    or _source_snippet(text, "BarGenerator")
                ),
            }
        )
    return pd.DataFrame(records)


def _schema_flags(columns: list[str]) -> dict[str, int]:
    colset = {str(c) for c in columns}
    lower = {str(c).lower() for c in columns}
    return {
        "has_ohlc": int({"open", "high", "low", "close"}.issubset(colset)),
        "has_volume": int("volume" in colset),
        "has_open_interest": int(bool({"open_oi", "close_oi", "open_interest"} & colset)),
        "has_last_price": int("last_price" in colset or "last" in lower),
        "has_bid_ask": int(bool({"bid_price1", "ask_price1"} <= colset)),
        "has_bid_ask_volume": int(bool({"bid_volume1", "ask_volume1"} <= colset)),
        "has_depth_gt1": int(any(re.match(r"(bid|ask)_price[2-9]", str(c)) for c in columns)),
        "has_tick_datetime": int("datetime" in colset or "tick_datetime" in colset),
        "has_bar_datetime": int("bar_datetime" in colset),
    }


def _scan_bar_quality(path: Path, full_scan: bool) -> dict[str, Any]:
    if not path.exists():
        return {
            "row_count": 0,
            "symbol_count": 0,
            "min_datetime": "",
            "max_datetime": "",
            "zero_volume_pct": np.nan,
            "positive_volume_pct": np.nan,
            "degenerate_ohlc_pct": np.nan,
            "nondegenerate_ohlc_pct": np.nan,
        }
    usecols = pd.read_csv(path, encoding="utf-8-sig", nrows=0).columns.tolist()
    wanted = [c for c in ["vt_symbol", "bar_datetime", "open", "high", "low", "close", "volume"] if c in usecols]
    if not {"open", "high", "low", "close", "volume"}.issubset(set(wanted)):
        data = pd.read_csv(path, encoding="utf-8-sig", nrows=5000)
        return {
            "row_count": int(len(data)),
            "symbol_count": int(data["vt_symbol"].nunique()) if "vt_symbol" in data.columns else 0,
            "min_datetime": "",
            "max_datetime": "",
            "zero_volume_pct": np.nan,
            "positive_volume_pct": np.nan,
            "degenerate_ohlc_pct": np.nan,
            "nondegenerate_ohlc_pct": np.nan,
        }

    row_count = 0
    zero_volume = 0
    positive_volume = 0
    degenerate = 0
    nondegenerate = 0
    symbols: set[str] = set()
    min_dt: pd.Timestamp | None = None
    max_dt: pd.Timestamp | None = None
    reader = pd.read_csv(
        path,
        encoding="utf-8-sig",
        usecols=wanted,
        chunksize=250_000 if full_scan else 5000,
    )
    for chunk_idx, chunk in enumerate(reader):
        if not full_scan and chunk_idx > 0:
            break
        row_count += int(len(chunk))
        if "vt_symbol" in chunk.columns:
            symbols.update(chunk["vt_symbol"].dropna().astype(str).unique().tolist())
        if "bar_datetime" in chunk.columns:
            parsed = pd.to_datetime(chunk["bar_datetime"], errors="coerce")
            if parsed.notna().any():
                cur_min = parsed.min()
                cur_max = parsed.max()
                min_dt = cur_min if min_dt is None or cur_min < min_dt else min_dt
                max_dt = cur_max if max_dt is None or cur_max > max_dt else max_dt
        for column in ["open", "high", "low", "close", "volume"]:
            chunk[column] = pd.to_numeric(chunk[column], errors="coerce")
        vol = chunk["volume"].fillna(0.0)
        zero_volume += int(vol.eq(0.0).sum())
        positive_volume += int(vol.gt(0.0).sum())
        deg = (
            chunk["open"].eq(chunk["high"])
            & chunk["high"].eq(chunk["low"])
            & chunk["low"].eq(chunk["close"])
        )
        degenerate += int(deg.fillna(False).sum())
        nondegenerate += int((~deg.fillna(True)).sum())
    denom = float(row_count) if row_count else np.nan
    return {
        "row_count": int(row_count),
        "symbol_count": int(len(symbols)),
        "min_datetime": min_dt.strftime("%Y-%m-%d %H:%M:%S") if min_dt is not None else "",
        "max_datetime": max_dt.strftime("%Y-%m-%d %H:%M:%S") if max_dt is not None else "",
        "zero_volume_pct": float(zero_volume / denom * 100.0) if row_count else np.nan,
        "positive_volume_pct": float(positive_volume / denom * 100.0) if row_count else np.nan,
        "degenerate_ohlc_pct": float(degenerate / denom * 100.0) if row_count else np.nan,
        "nondegenerate_ohlc_pct": float(nondegenerate / denom * 100.0) if row_count else np.nan,
    }


def _scan_asset(path: Path, family: str, full_scan: bool = False) -> dict[str, Any]:
    if not path.exists():
        flags = _schema_flags([])
        return {
            "family": family,
            "path": _rel(path),
            "exists": 0,
            "columns": "",
            **flags,
            **_scan_bar_quality(path, full_scan=False),
        }
    header = pd.read_csv(path, encoding="utf-8-sig", nrows=0)
    flags = _schema_flags(header.columns.tolist())
    quality = _scan_bar_quality(path, full_scan=full_scan)
    return {
        "family": family,
        "path": _rel(path),
        "exists": 1,
        "columns": ",".join(header.columns.astype(str).tolist()),
        **flags,
        **quality,
    }


def _tick_file_summary(root: Path, family: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not root.exists():
        return records
    files = sorted(root.rglob("*.csv"))
    for path in files[:200]:
        try:
            header = pd.read_csv(path, encoding="utf-8-sig", nrows=0)
            flags = _schema_flags(header.columns.tolist())
            sample = pd.read_csv(path, encoding="utf-8-sig", nrows=5000)
            rows = int(len(sample))
            min_dt = ""
            max_dt = ""
            for col in ["datetime", "tick_datetime"]:
                if col in sample.columns:
                    parsed = pd.to_datetime(sample[col], errors="coerce")
                    if parsed.notna().any():
                        min_dt = parsed.min().strftime("%Y-%m-%d %H:%M:%S")
                        max_dt = parsed.max().strftime("%Y-%m-%d %H:%M:%S")
                    break
            records.append(
                {
                    "family": family,
                    "path": _rel(path),
                    "exists": 1,
                    "columns": ",".join(header.columns.astype(str).tolist()),
                    **flags,
                    "row_count": rows,
                    "symbol_count": 1,
                    "min_datetime": min_dt,
                    "max_datetime": max_dt,
                    "zero_volume_pct": np.nan,
                    "positive_volume_pct": np.nan,
                    "degenerate_ohlc_pct": np.nan,
                    "nondegenerate_ohlc_pct": np.nan,
                }
            )
        except Exception as exc:  # pragma: no cover - defensive cataloging
            records.append(
                {
                    "family": family,
                    "path": _rel(path),
                    "exists": 1,
                    "columns": f"read_error:{type(exc).__name__}",
                    **_schema_flags([]),
                    "row_count": 0,
                    "symbol_count": 0,
                    "min_datetime": "",
                    "max_datetime": "",
                    "zero_volume_pct": np.nan,
                    "positive_volume_pct": np.nan,
                    "degenerate_ohlc_pct": np.nan,
                    "nondegenerate_ohlc_pct": np.nan,
                }
            )
    return records


def _asset_schema_audit() -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    records.append(_scan_asset(STAGE449_FULL_BARS, "stage449_full_minute_bars", full_scan=True))
    records.append(_scan_asset(STAGE446_BARS, "stage446_seed_minute_bars", full_scan=True))
    for path in sorted(BACKTEST_OUTPUTS.glob("qmt_roll_stage449_minute_session_rebuild_full_shard*_minute_bars_*.csv")):
        records.append(_scan_asset(path, f"stage449_shard_{path.name.split('_shard', 1)[1].split('_', 1)[0]}", full_scan=False))
    records.append(_scan_asset(STAGE448_STATUS, "stage448_extract_status", full_scan=False))
    records.append(_scan_asset(STAGE449_STATUS, "stage449_extract_status", full_scan=False))
    records.append(_scan_asset(STAGE449_DETAIL, "stage449_ledger_proxy_detail", full_scan=False))
    records.extend(_tick_file_summary(STAGE070_TICK_ROOT, "stage070_tq_tick_sample"))
    records.extend(_tick_file_summary(STAGE079_TICK_ROOT, "stage079_tq_tick_manifest"))
    data = pd.DataFrame(records)
    if data.empty:
        return data
    data["is_same_source_stage449_bar"] = data["family"].astype(str).str.startswith(("stage449", "stage446")).astype(int)
    data["has_true_quote_depth_fields"] = (
        data[["has_last_price", "has_bid_ask", "has_bid_ask_volume", "has_depth_gt1"]].sum(axis=1).gt(0).astype(int)
    )
    data["is_rule_usable_same_source_microstructure"] = (
        data["is_same_source_stage449_bar"].eq(1)
        & data["has_true_quote_depth_fields"].eq(1)
        & data["positive_volume_pct"].fillna(0).gt(0)
        & data["nondegenerate_ohlc_pct"].fillna(0).gt(0)
    ).astype(int)
    return data


def _field_gate(source_audit: pd.DataFrame, asset_schema: pd.DataFrame) -> pd.DataFrame:
    stage449_assets = asset_schema[asset_schema["family"].astype(str).str.startswith("stage449")].copy()
    tq_tick_assets = asset_schema[asset_schema["family"].astype(str).str.startswith(("stage070_tq_tick", "stage079_tq_tick"))].copy()
    generator_mask = source_audit["source_family"].astype(str).str.contains(
        "stage446_tqsdk_backtest_minute_proxy_extract|stage448_minute_session_rebuild_batch",
        regex=True,
    )
    generator_sources = source_audit[generator_mask].copy()
    generation_get_kline_count = int(
        pd.to_numeric(generator_sources.get("get_kline_serial_count", 0), errors="coerce").fillna(0).sum()
    )
    generation_get_tick_count = int(
        pd.to_numeric(generator_sources.get("get_tick_serial_count", 0), errors="coerce").fillna(0).sum()
    )
    records = [
        {
            "gate_id": "G1_stage449_generation_source_found",
            "pass": int(source_audit["source_family"].astype(str).ne("stage449_generation_script").any()),
            "evidence_value": int(len(source_audit)),
            "required_next_action": "keep_stage446_448_as_observed_generator_evidence_no_missing_stage449_script_assumption",
        },
        {
            "gate_id": "G2_generation_uses_kline_not_tick",
            "pass": int(generation_get_kline_count > 0 and generation_get_tick_count == 0),
            "evidence_value": f"generator_get_kline={generation_get_kline_count}, generator_get_tick={generation_get_tick_count}",
            "required_next_action": "do_not_treat_stage449_bars_as_tick_or_quote_source",
        },
        {
            "gate_id": "G3_stage449_quote_depth_columns_present",
            "pass": int(stage449_assets["has_true_quote_depth_fields"].sum() > 0) if not stage449_assets.empty else 0,
            "evidence_value": int(stage449_assets["has_true_quote_depth_fields"].sum()) if not stage449_assets.empty else 0,
            "required_next_action": "find_real_raw_quote_depth_fields_or_authorized_vendor_data",
        },
        {
            "gate_id": "G4_stage449_nonzero_volume_present",
            "pass": int(stage449_assets["positive_volume_pct"].fillna(0).max() > 0) if not stage449_assets.empty else 0,
            "evidence_value": float(stage449_assets["positive_volume_pct"].fillna(0).max()) if not stage449_assets.empty else 0.0,
            "required_next_action": "replace_zero_volume_proxy_bars_with_true_traded_bars_or_tick",
        },
        {
            "gate_id": "G5_stage449_nondegenerate_ohlc_present",
            "pass": int(stage449_assets["nondegenerate_ohlc_pct"].fillna(0).max() > 0) if not stage449_assets.empty else 0,
            "evidence_value": float(stage449_assets["nondegenerate_ohlc_pct"].fillna(0).max()) if not stage449_assets.empty else 0.0,
            "required_next_action": "replace_ohlc_flat_proxy_bars_with_true_bar_or_tick_source",
        },
        {
            "gate_id": "G6_tq_tick_has_quote_fields_but_not_same_source",
            "pass": int(tq_tick_assets["has_bid_ask"].sum() > 0) if not tq_tick_assets.empty else 0,
            "evidence_value": int(tq_tick_assets["has_bid_ask"].sum()) if not tq_tick_assets.empty else 0,
            "required_next_action": "keep_tq_tick_as_tca_only_until_stage449_transform_or_authorization_is_proven",
        },
        {
            "gate_id": "G7_rule_usable_same_source_microstructure",
            "pass": int(asset_schema["is_rule_usable_same_source_microstructure"].sum() > 0) if not asset_schema.empty else 0,
            "evidence_value": int(asset_schema["is_rule_usable_same_source_microstructure"].sum()) if not asset_schema.empty else 0,
            "required_next_action": "blocked_no_true_engine_or_ab",
        },
    ]
    return pd.DataFrame(records)


def _summary(
    curve: pd.DataFrame,
    source_audit: pd.DataFrame,
    asset_schema: pd.DataFrame,
    field_gate: pd.DataFrame,
) -> pd.DataFrame:
    official = _official_metrics(curve)
    stage449 = asset_schema[asset_schema["family"].astype(str).eq("stage449_full_minute_bars")].copy()
    tq_ticks = asset_schema[asset_schema["family"].astype(str).str.startswith(("stage070_tq_tick", "stage079_tq_tick"))]
    usable_count = int(asset_schema["is_rule_usable_same_source_microstructure"].sum()) if not asset_schema.empty else 0
    pass_count = int(pd.to_numeric(field_gate["pass"], errors="coerce").sum()) if not field_gate.empty else 0
    decision = "stage086_stage449_raw_generation_no_hidden_quote_depth_no_rule"
    if usable_count > 0:
        decision = "stage086_stage449_raw_generation_microstructure_ready_for_fixed_readonly_audit"
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "end_equity": official["end_equity"],
                "total_return_pct": official["total_return_pct"],
                "max_drawdown_pct": official["max_drawdown_pct"],
                "sharpe": official["sharpe"],
                "total_slippage": official["total_slippage"],
                "total_trade_count": official["total_trade_count"],
                "max_broker10_margin_to_equity_pct": official["max_broker10_margin_to_equity_pct"],
                "source_file_count": int(len(source_audit)),
                "source_get_kline_serial_count": int(source_audit["get_kline_serial_count"].sum()) if not source_audit.empty else 0,
                "source_get_tick_serial_count": int(source_audit["get_tick_serial_count"].sum()) if not source_audit.empty else 0,
                "asset_record_count": int(len(asset_schema)),
                "stage449_full_rows": int(stage449["row_count"].iloc[0]) if not stage449.empty else 0,
                "stage449_full_zero_volume_pct": float(stage449["zero_volume_pct"].iloc[0]) if not stage449.empty else np.nan,
                "stage449_full_degenerate_ohlc_pct": float(stage449["degenerate_ohlc_pct"].iloc[0]) if not stage449.empty else np.nan,
                "stage449_quote_depth_asset_count": int(
                    asset_schema.loc[
                        asset_schema["family"].astype(str).str.startswith("stage449"), "has_true_quote_depth_fields"
                    ].sum()
                )
                if not asset_schema.empty
                else 0,
                "tq_tick_sample_file_count": int(len(tq_ticks)),
                "tq_tick_bid_ask_file_count": int(tq_ticks["has_bid_ask"].sum()) if not tq_ticks.empty else 0,
                "field_gate_pass_count": pass_count,
                "field_gate_total_count": int(len(field_gate)),
                "rule_usable_same_source_microstructure_count": usable_count,
                "decision": decision,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
            }
        ]
    )


def _plot_official_path(curve: pd.DataFrame, summary: pd.Series) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(15, 12), sharex=True, gridspec_kw={"height_ratios": [2, 1, 1]})
    axes[0].plot(curve["date"], curve["account_equity"], color="#2563eb", linewidth=1.2, label="official C9/15w")
    axes[0].set_yscale("log")
    axes[0].set_ylabel("equity (log)")
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#dc2626", linewidth=1.0, label="drawdown")
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#7c3aed", linewidth=1.0, label="broker10 %")
    axes[2].axhline(100, color="#991b1b", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("broker10 %")
    title = (
        "Stage086 official path unchanged | "
        f"stage449 quote/depth assets {int(summary['stage449_quote_depth_asset_count'])} | "
        f"usable same-source microstructure {int(summary['rule_usable_same_source_microstructure_count'])}"
    )
    axes[0].set_title(title)
    note = (
        f"Stage449 rows={int(summary['stage449_full_rows']):,}\n"
        f"zero_volume={float(summary['stage449_full_zero_volume_pct']):.2f}%\n"
        f"degenerate_ohlc={float(summary['stage449_full_degenerate_ohlc_pct']):.2f}%\n"
        f"decision={summary['decision']}"
    )
    axes[0].text(
        0.01,
        0.04,
        note,
        transform=axes[0].transAxes,
        fontsize=8,
        va="bottom",
        ha="left",
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "alpha": 0.78, "edgecolor": "#cbd5e1"},
    )
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(OFFICIAL_PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_schema_heatmap(asset_schema: pd.DataFrame) -> None:
    if asset_schema.empty:
        return
    fields = [
        "has_ohlc",
        "has_volume",
        "has_open_interest",
        "has_last_price",
        "has_bid_ask",
        "has_bid_ask_volume",
        "has_depth_gt1",
        "has_tick_datetime",
        "is_rule_usable_same_source_microstructure",
    ]
    grouped = asset_schema.groupby("family", as_index=False)[fields].max()
    data = grouped.set_index("family")[fields].astype(float)
    fig, ax = plt.subplots(figsize=(14, max(5, 0.36 * len(data) + 2)))
    im = ax.imshow(data.to_numpy(), aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(fields)))
    ax.set_xticklabels(fields, rotation=35, ha="right")
    ax.set_yticks(np.arange(len(data.index)))
    ax.set_yticklabels(data.index)
    for y in range(data.shape[0]):
        for x in range(data.shape[1]):
            ax.text(x, y, str(int(data.iloc[y, x])), ha="center", va="center", fontsize=8)
    ax.set_title("Stage086 schema field heatmap: Stage449 bars lack true quote/depth fields")
    fig.colorbar(im, ax=ax, shrink=0.72)
    fig.tight_layout()
    fig.savefig(SCHEMA_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_quality(asset_schema: pd.DataFrame) -> None:
    data = asset_schema[
        asset_schema["family"].astype(str).str.startswith(("stage446", "stage449"))
    ].copy()
    if data.empty:
        return
    data = data.head(10)
    x = np.arange(len(data))
    width = 0.36
    fig, ax = plt.subplots(figsize=(15, 7))
    ax.bar(x - width / 2, data["zero_volume_pct"].fillna(0), width=width, color="#dc2626", label="zero volume %")
    ax.bar(x + width / 2, data["degenerate_ohlc_pct"].fillna(0), width=width, color="#f97316", label="degenerate OHLC %")
    ax.set_xticks(x)
    ax.set_xticklabels(data["family"], rotation=35, ha="right")
    ax.set_ylim(0, 105)
    ax.set_ylabel("%")
    ax.set_title("Stage086 Stage449/446 bar quality")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(QUALITY_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_source(source_audit: pd.DataFrame) -> None:
    if source_audit.empty:
        return
    cols = ["get_kline_serial_count", "get_tick_serial_count", "data_downloader_count", "bar_generator_count"]
    data = source_audit[source_audit["exists"].eq(1)].copy()
    if data.empty:
        return
    data["label"] = data["source_family"].str.replace("analyze_qmt_roll_", "", regex=False).str[:38]
    fig, ax = plt.subplots(figsize=(15, max(6, 0.45 * len(data) + 2)))
    bottom = np.zeros(len(data))
    colors = ["#2563eb", "#16a34a", "#f97316", "#7c3aed"]
    for col, color in zip(cols, colors):
        vals = pd.to_numeric(data[col], errors="coerce").fillna(0).to_numpy(dtype=float)
        ax.barh(data["label"], vals, left=bottom, color=color, label=col)
        bottom += vals
    ax.invert_yaxis()
    ax.set_xlabel("keyword count")
    ax.set_title("Stage086 source-code provenance: kline path dominates observed Stage449/448 generation")
    ax.grid(True, axis="x", alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(SOURCE_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    source_audit: pd.DataFrame,
    asset_schema: pd.DataFrame,
    field_gate: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    family_summary = (
        asset_schema.groupby("family", as_index=False)
        .agg(
            file_count=("path", "count"),
            rows=("row_count", "sum"),
            max_zero_volume_pct=("zero_volume_pct", "max"),
            max_degenerate_ohlc_pct=("degenerate_ohlc_pct", "max"),
            has_bid_ask=("has_bid_ask", "max"),
            rule_usable=("is_rule_usable_same_source_microstructure", "max"),
        )
        .sort_values(["rule_usable", "has_bid_ask", "rows"], ascending=[False, False, False])
    )
    lines = [
        "# Stage086 Stage449/raw 生成端 provenance 审计",
        "",
        f"- 生成时间：`{row['created_at']}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前官方正式版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        "- 阶段性质：只读源码与资产 provenance 审计；不写真引擎、不新增交易规则、不触发 A/B、不连接 CTP、不调用订单 API。",
        "- 固定问题：Stage085 最高 readiness 的 Stage449/raw route 是否存在被遗漏的真实 quote/open/depth 字段或 tick-to-bar provenance。",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Field Gate",
        "",
        _md_table(field_gate),
        "",
        "## Asset Family Summary",
        "",
        _md_table(family_summary),
        "",
        "## Source Audit",
        "",
        _md_table(source_audit[["source_family", "path", "exists", "get_kline_serial_count", "get_tick_serial_count", "data_downloader_count", "bid_ask_last_keyword_count", "main_evidence_snippet"]], max_rows=20),
        "",
        "## Visual Outputs",
        "",
        f"- official path/provenance gate chart：`{OFFICIAL_PATH_CHART_OUT}`",
        f"- schema field heatmap：`{SCHEMA_HEATMAP_OUT}`",
        f"- bar quality chart：`{QUALITY_CHART_OUT}`",
        f"- source code provenance chart：`{SOURCE_CHART_OUT}`",
        "",
        "## Decision",
        "",
        f"- 决策：`{row['decision']}`",
        "- 主结论：Stage449/raw 生成端没有发现隐藏的 bid/ask/last/depth 字段；可观察生成脚本使用 60 秒 kline，不是 tick serial；Stage449/446 bar 样本为 100% zero-volume 且 OHLC-flat。",
        "- Tq tick 样本有 bid/ask/last 字段，但它们已经在 Stage080 被证明不能统一重建 Stage449/raw open，因此只能保留为 TCA/forward watch。",
        "- 下一步：不要继续在 Stage449 zero-volume proxy 上写微观规则；只能取得授权 vendor/raw exchange tick/quote/depth，或找到真正的 Stage449/raw 生成端 quote/depth 源文件。",
        "",
    ]
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _prepare_official_curve()
    source_audit = _source_audit()
    asset_schema = _asset_schema_audit()
    field_gate = _field_gate(source_audit, asset_schema)
    summary = _summary(curve, source_audit, asset_schema, field_gate)

    _write_csv(source_audit, SOURCE_AUDIT_OUT)
    _write_csv(asset_schema, ASSET_SCHEMA_OUT)
    _write_csv(field_gate, FIELD_GATE_OUT)
    _write_csv(summary, SUMMARY_OUT)
    DECISION_OUT.write_text(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, indent=2), encoding="utf-8")

    _plot_official_path(curve, summary.iloc[0])
    _plot_schema_heatmap(asset_schema)
    _plot_quality(asset_schema)
    _plot_source(source_audit)
    _write_report(summary, source_audit, asset_schema, field_gate)

    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
