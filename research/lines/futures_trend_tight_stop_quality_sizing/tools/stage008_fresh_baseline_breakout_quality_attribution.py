from __future__ import annotations

from collections import deque
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import talib


ROOT = Path(__file__).resolve().parents[4]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import stage001_baseline_technical_attribution as legacy  # noqa: E402
import stage003_lower_half_stop_moderate_body_risk_transfer as strict  # noqa: E402
from qmt_roll_official_live_config import (  # noqa: E402
    OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_PROFILE_NAME,
    OFFICIAL_LIVE_VERSION,
)


LINE_ID = "futures_trend_tight_stop_quality_sizing"
STAGE = "Stage008"
MODEL_TAG = "stage008_fresh_baseline_breakout_quality_attribution_v1"
OUTPUT_PREFIX = "tight_stop_quality_stage008"
START = pd.Timestamp("2020-01-01")
END = pd.Timestamp("2026-06-30")
EXPECTED_CAPITAL = 150_000.0
EXPECTED_VERSION = "official_live_stage847_c9_15w_stage819_05r_stop_retry_once"
VARIANT = "A_official_fresh"
MIN_CORE_COVERAGE = 0.95

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage008_fresh_baseline_breakout_quality_attribution"
DATABASE_PATH = ROOT / ".vntrader" / "database.db"

DAILY_PATH = OUT / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv.gz"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
TRADES_PATH = OUT / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv.gz"
ATTRIBUTION_TRADES_PATH = OUT / f"{OUTPUT_PREFIX}_attribution_trades_natural_order_{MODEL_TAG}.csv.gz"
ENTRY_RISK_PATH = OUT / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv.gz"
ENTRY_CANDIDATES_PATH = OUT / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv.gz"
TRADE_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv.gz"
STOP_RETRY_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_stop_retry_events_{MODEL_TAG}.csv.gz"
STOP_RETRY_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_stop_retry_audit_{MODEL_TAG}.csv"
AI_MONTH_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_ai_month_audit_{MODEL_TAG}.csv"
AI_FULL_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_ai_full_membership_audit_{MODEL_TAG}.csv"
CLOSED_LOTS_PATH = OUT / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv.gz"
TERMINAL_OPEN_LOTS_PATH = OUT / f"{OUTPUT_PREFIX}_terminal_open_lots_{MODEL_TAG}.csv"
OPEN_LINEAGE_PATH = OUT / f"{OUTPUT_PREFIX}_open_lineage_{MODEL_TAG}.csv.gz"
LEGACY_ENTRY_EVENTS_PRIVATE_PATH = OUT / f"{OUTPUT_PREFIX}_entry_events_private_{MODEL_TAG}.csv.gz"
DISCOVERY_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_discovery_events_{MODEL_TAG}.csv.gz"
FUTURE_FEATURE_SEAL_PATH = OUT / f"{OUTPUT_PREFIX}_future_feature_seal_{MODEL_TAG}.json"
THRESHOLDS_PATH = OUT / f"{OUTPUT_PREFIX}_discovery_distribution_thresholds_{MODEL_TAG}.csv"
FEATURE_BIN_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_discovery_feature_bins_{MODEL_TAG}.csv"
ANNUAL_PATH = OUT / f"{OUTPUT_PREFIX}_annual_path_{MODEL_TAG}.csv"
DRAWDOWN_EPISODES_PATH = OUT / f"{OUTPUT_PREFIX}_drawdown_episodes_{MODEL_TAG}.csv"
SOURCE_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_contract_source_audit_{MODEL_TAG}.csv"
SOURCE_VOLUME_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_source_volume_mismatch_audit_{MODEL_TAG}.csv"
INPUT_MANIFEST_PATH = OUT / f"{OUTPUT_PREFIX}_input_manifest_{MODEL_TAG}.csv"
OUTPUT_MANIFEST_PATH = OUT / f"{OUTPUT_PREFIX}_output_manifest_{MODEL_TAG}.csv"
BASELINE_CHART_PATH = OUT / f"{OUTPUT_PREFIX}_baseline_path_{MODEL_TAG}.png"
DISCOVERY_CHART_PATH = OUT / f"{OUTPUT_PREFIX}_discovery_feature_bins_{MODEL_TAG}.png"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

NEW_FEATURE_COLUMNS = (
    "atr14",
    "prior20_high",
    "prior20_low",
    "breakout_margin20_atr",
    "close_margin20_atr",
    "directional_efficiency20",
    "atr14_to_prior60_median",
    "directional_clv",
    "adverse_wick_ratio",
)
BIN_FEATURES = (
    "stop_atr14",
    "breakout_margin20_atr",
    "directional_efficiency20",
    "atr14_to_prior60_median",
)
FUTURE_FEATURE_SEAL_COLUMNS = (
    "open_trade_id",
    "vt_symbol",
    "product",
    "direction",
    "entry_date",
    "feature_date",
    "feature_bar_count",
    "planned_stop_distance",
    "stop_atr14",
    *NEW_FEATURE_COLUMNS,
    "entry_year",
    "sample_segment",
    "feature_future_violation",
)
FRAME_HASH_CONTRACT = {
    "format": "csv_utf8",
    "column_order": "lexicographic",
    "row_order": "input_stable",
    "float_format": "%.17g",
    "date_format": "%Y-%m-%dT%H:%M:%S.%f",
    "na_rep": "<NA>",
    "lineterminator": "\\n",
}

EXTERNAL_RESEARCH = (
    {
        "source": "A Century of Evidence on Trend-Following Investing",
        "url": "https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing",
        "judgment": "趋势跟随跨市场和长样本有稳健证据，但不能据此直接证明本策略的加仓规则。",
    },
    {
        "source": "Time Series Momentum and Volatility States",
        "url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2515685",
        "judgment": "波动状态可能影响趋势收益质量，因此把短期 ATR 相对历史状态作为解释变量。",
    },
    {
        "source": "pysystemtrade backtesting documentation",
        "url": "https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md",
        "judgment": "研究与真实执行必须保留成本、仓位和成交语义，不能只做信号收益代理。",
    },
    {
        "source": "Backtrader Donchian Channel reference implementation",
        "url": "https://gist.github.com/mementum/1adc2aea1102f222bfa8b93ef892aae8",
        "judgment": "通道计算必须排除当前信号 K 线，避免把当日高低点写入比较基准。",
    },
)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return number if np.isfinite(number) else None
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    try:
        if pd.isna(value) and not isinstance(value, (str, bytes)):
            return None
    except Exception:
        pass
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _frame_sha256(frame: pd.DataFrame) -> str:
    normalized = frame.copy()
    normalized = normalized.reindex(sorted(normalized.columns), axis=1)
    payload = normalized.to_csv(
        index=False,
        float_format=FRAME_HASH_CONTRACT["float_format"],
        date_format=FRAME_HASH_CONTRACT["date_format"],
        na_rep=FRAME_HASH_CONTRACT["na_rep"],
        lineterminator="\n",
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def prepare_output_directory(output: Path, *, legacy_paths: list[Path] | tuple[Path, ...] = ()) -> None:
    output.mkdir(parents=True, exist_ok=True)
    output_root = output.resolve()
    for path in legacy_paths:
        resolved = path.resolve()
        if resolved.parent != output_root:
            raise ValueError(f"legacy output is outside Stage008 directory: {path}")
        resolved.unlink(missing_ok=True)


def partition_event_outputs(events: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    if "sample_segment" not in events.columns:
        raise ValueError("events missing sample_segment")
    discovery = events.loc[events["sample_segment"].astype(str).eq("discovery")].copy()
    seal_columns = [column for column in FUTURE_FEATURE_SEAL_COLUMNS if column in events.columns]
    future_features = events.loc[
        ~events["sample_segment"].astype(str).eq("discovery"), seal_columns
    ].copy()
    seal = {
        "row_count": int(len(future_features)),
        "feature_only_sha256": _frame_sha256(future_features),
        "feature_hash_contract": FRAME_HASH_CONTRACT,
        "segments": future_features["sample_segment"].value_counts().sort_index().to_dict(),
        "outcome_columns_removed": True,
        "feature_allowlist_enforced": True,
        "feature_columns": seal_columns,
        "future_row_data_exported": False,
        "purpose": (
            "Stage009 规则预声明前不联表后段特征与收益；完整基准结果已单独持久化，"
            "因此该 seal 不是未见 OOS 证明。"
        ),
        "true_oos_claim": False,
        "full_period_baseline_outcomes_persisted": True,
    }
    return discovery, seal


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    value = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return value.to_markdown(index=False)


def _prepare_bars(bars: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "open", "high", "low", "close"}
    missing = required - set(bars.columns)
    if missing:
        raise ValueError(f"bars missing required columns: {sorted(missing)}")
    frame = bars.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    for column in ("open", "high", "low", "close", "volume"):
        if column not in frame.columns:
            frame[column] = np.nan
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["date", "open", "high", "low", "close"])
    frame = frame.drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)
    geometry = (
        frame["high"].ge(frame[["open", "close"]].max(axis=1))
        & frame["low"].le(frame[["open", "close"]].min(axis=1))
        & frame["high"].ge(frame["low"])
    )
    if not geometry.all():
        raise ValueError("bars contain invalid OHLC geometry")
    return frame


def indicator_panel(bars: pd.DataFrame) -> pd.DataFrame:
    """Build causal daily indicators; every channel boundary uses completed prior bars."""
    frame = _prepare_bars(bars)
    if frame.empty:
        return frame
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    close = frame["close"].to_numpy(dtype=float)
    frame["atr14"] = talib.ATR(high, low, close, timeperiod=14)
    frame["prior20_high"] = frame["high"].shift(1).rolling(20, min_periods=20).max()
    frame["prior20_low"] = frame["low"].shift(1).rolling(20, min_periods=20).min()
    absolute_path = frame["close"].diff().abs().rolling(20, min_periods=20).sum().replace(0.0, np.nan)
    frame["efficiency20"] = (frame["close"] - frame["close"].shift(20)) / absolute_path
    frame["prior60_atr_median"] = frame["atr14"].shift(1).rolling(60, min_periods=60).median()
    bar_range = (frame["high"] - frame["low"]).replace(0.0, np.nan)
    upper_body = frame[["open", "close"]].max(axis=1)
    lower_body = frame[["open", "close"]].min(axis=1)
    frame["clv"] = (frame["close"] - frame["low"]) / bar_range
    frame["upper_wick_ratio"] = (frame["high"] - upper_body) / bar_range
    frame["lower_wick_ratio"] = (lower_body - frame["low"]) / bar_range
    return frame


def features_before_entry(panel: pd.DataFrame, entry_date: Any, direction: str) -> dict[str, Any]:
    entry = pd.Timestamp(entry_date)
    if entry.tzinfo is not None:
        entry = entry.tz_localize(None)
    entry = entry.normalize()
    dates = pd.to_datetime(panel.get("date"), errors="coerce").dt.tz_localize(None).dt.normalize()
    history = panel.loc[dates.lt(entry)].copy()
    empty = {"feature_date": pd.NaT, "feature_bar_count": 0, **{name: np.nan for name in NEW_FEATURE_COLUMNS}}
    if history.empty:
        return empty
    row = history.iloc[-1]
    atr14 = _safe_float(row.get("atr14"))
    prior_high = _safe_float(row.get("prior20_high"))
    prior_low = _safe_float(row.get("prior20_low"))
    direction_text = str(direction).strip().lower()
    if direction_text not in {"long", "short"}:
        raise ValueError(f"unsupported direction: {direction}")
    sign = 1.0 if direction_text == "long" else -1.0
    if direction_text == "long":
        breakout = (_safe_float(row.get("high")) - prior_high) / atr14 if atr14 > 0 else np.nan
        close_margin = (_safe_float(row.get("close")) - prior_high) / atr14 if atr14 > 0 else np.nan
        directional_clv = _safe_float(row.get("clv"))
        adverse_wick = _safe_float(row.get("upper_wick_ratio"))
    else:
        breakout = (prior_low - _safe_float(row.get("low"))) / atr14 if atr14 > 0 else np.nan
        close_margin = (prior_low - _safe_float(row.get("close"))) / atr14 if atr14 > 0 else np.nan
        clv = _safe_float(row.get("clv"))
        directional_clv = 1.0 - clv if np.isfinite(clv) else np.nan
        adverse_wick = _safe_float(row.get("lower_wick_ratio"))
    prior_median = _safe_float(row.get("prior60_atr_median"))
    return {
        "feature_date": pd.Timestamp(row["date"]).normalize(),
        "feature_bar_count": int(len(history)),
        "atr14": atr14,
        "prior20_high": prior_high,
        "prior20_low": prior_low,
        "breakout_margin20_atr": breakout,
        "close_margin20_atr": close_margin,
        "directional_efficiency20": sign * _safe_float(row.get("efficiency20")),
        "atr14_to_prior60_median": atr14 / prior_median if atr14 > 0 and prior_median > 0 else np.nan,
        "directional_clv": directional_clv,
        "adverse_wick_ratio": adverse_wick,
    }


def assert_no_new_ai_features(frame: pd.DataFrame) -> None:
    forbidden = []
    for column in frame.columns:
        normalized = str(column).strip().lower()
        if normalized == "ai" or normalized.startswith("ai_") or normalized.endswith("_ai") or "_ai_" in normalized:
            forbidden.append(str(column))
    if forbidden:
        raise ValueError(f"AI-derived fields are forbidden: {sorted(forbidden)}")


def full_ai_pool_membership_audit(candidates: pd.DataFrame, pool: pd.DataFrame) -> dict[str, Any]:
    candidate_required = {
        "candidate_index",
        "date",
        "product_vt_symbol",
        "skip_reason",
        "ai_product_pool_enabled",
        "ai_product_pool_allowed",
        "ai_product_pool_strategy",
        "ai_product_pool_signal_date",
        "ai_product_pool_score",
        "ai_product_pool_rank",
        "ai_product_pool_top_n",
    }
    pool_required = {"strategy", "eval_date", "product_vt_symbol", "score", "score_rank", "top_n"}
    missing_candidates = candidate_required - set(candidates.columns)
    missing_pool = pool_required - set(pool.columns)
    if missing_candidates or missing_pool:
        raise ValueError(
            f"AI audit fields missing: candidates={sorted(missing_candidates)} pool={sorted(missing_pool)}"
        )
    evidence = candidates.copy()
    evidence["candidate_date"] = pd.to_datetime(evidence["date"], errors="coerce").dt.normalize()
    evidence["signal_date"] = pd.to_datetime(
        evidence["ai_product_pool_signal_date"], errors="coerce"
    ).dt.normalize()
    pool_data = pool.copy()
    pool_data["eval_date"] = pd.to_datetime(pool_data["eval_date"], errors="coerce").dt.normalize()
    pool_key = ["strategy", "eval_date", "product_vt_symbol"]
    if pool_data.duplicated(pool_key).any():
        raise RuntimeError("AI pool contains duplicate strategy/date/product rows")
    pool_data = pool_data.rename(
        columns={
            "strategy": "pool_strategy",
            "eval_date": "pool_eval_date",
            "score": "pool_score",
            "score_rank": "pool_rank",
            "top_n": "pool_top_n",
        }
    )
    merged = evidence.merge(
        pool_data,
        left_on=["ai_product_pool_strategy", "signal_date", "product_vt_symbol"],
        right_on=["pool_strategy", "pool_eval_date", "product_vt_symbol"],
        how="left",
        validate="many_to_one",
    )
    enabled = pd.to_numeric(merged["ai_product_pool_enabled"], errors="coerce").fillna(0).eq(1)
    allowed = pd.to_numeric(merged["ai_product_pool_allowed"], errors="coerce").fillna(0).eq(1)
    blocked = merged["skip_reason"].astype(str).eq("ai_product_pool_blocked")
    member = merged["pool_rank"].notna()
    score_error = (
        pd.to_numeric(merged["ai_product_pool_score"], errors="coerce")
        - pd.to_numeric(merged["pool_score"], errors="coerce")
    ).abs()
    rank_error = (
        pd.to_numeric(merged["ai_product_pool_rank"], errors="coerce")
        - pd.to_numeric(merged["pool_rank"], errors="coerce")
    ).abs()
    top_n_error = (
        pd.to_numeric(merged["ai_product_pool_top_n"], errors="coerce")
        - pd.to_numeric(merged["pool_top_n"], errors="coerce")
    ).abs()
    allowed_value_mismatch = allowed & (
        ~member
        | score_error.isna()
        | score_error.gt(1e-12)
        | rank_error.isna()
        | rank_error.gt(1e-12)
        | top_n_error.isna()
        | top_n_error.gt(1e-12)
    )
    blocked_member_mismatch = blocked & member
    signal_date_invalid = merged["signal_date"].isna() | merged["candidate_date"].isna() | merged["signal_date"].ge(
        merged["candidate_date"]
    )
    audit = {
        "candidate_count": int(len(merged)),
        "enabled_count": int(enabled.sum()),
        "allowed_count": int(allowed.sum()),
        "blocked_count": int(blocked.sum()),
        "allowed_pool_member_count": int((allowed & member).sum()),
        "disabled_count": int((~enabled).sum()),
        "allowed_value_mismatch_count": int(allowed_value_mismatch.sum()),
        "blocked_member_mismatch_count": int(blocked_member_mismatch.sum()),
        "signal_date_invalid_count": int(signal_date_invalid.sum()),
        "max_allowed_score_error": float(score_error.loc[allowed & member].max()) if (allowed & member).any() else 0.0,
        "max_allowed_rank_error": float(rank_error.loc[allowed & member].max()) if (allowed & member).any() else 0.0,
        "max_allowed_top_n_error": float(top_n_error.loc[allowed & member].max()) if (allowed & member).any() else 0.0,
    }
    failure_count = (
        audit["disabled_count"]
        + audit["allowed_value_mismatch_count"]
        + audit["blocked_member_mismatch_count"]
        + audit["signal_date_invalid_count"]
    )
    if failure_count:
        raise RuntimeError(f"full AI pool membership audit failed: {audit}")
    return audit


def _sample_segment(entry_date: Any) -> str:
    year = pd.Timestamp(entry_date).year
    if year <= 2022:
        return "discovery"
    if year <= 2024:
        return "validation"
    return "holdout"


def discovery_distribution_thresholds(frame: pd.DataFrame) -> dict[str, float]:
    discovery = frame.loc[frame["sample_segment"].astype(str).eq("discovery")].copy()
    if discovery.empty:
        raise ValueError("discovery segment is empty")

    def quantile(column: str, value: float) -> float:
        values = pd.to_numeric(discovery[column], errors="coerce").dropna()
        if values.empty:
            raise ValueError(f"discovery feature is empty: {column}")
        return float(values.quantile(value))

    return {
        "stop_atr14_q50": quantile("stop_atr14", 0.50),
        "breakout_margin20_atr_q75": quantile("breakout_margin20_atr", 0.75),
        "directional_efficiency20_q50": quantile("directional_efficiency20", 0.50),
        "atr14_to_prior60_median_q50": quantile("atr14_to_prior60_median", 0.50),
    }


def discovery_feature_bin_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Summarize only discovery outcomes; future segments are impossible inputs here."""
    discovery = frame.loc[frame["sample_segment"].astype(str).eq("discovery")].copy()
    if discovery.empty:
        raise ValueError("discovery segment is empty")
    rows: list[dict[str, Any]] = []
    for feature in BIN_FEATURES:
        values = pd.to_numeric(discovery[feature], errors="coerce")
        valid = discovery.loc[values.notna()].copy()
        if len(valid) < 4:
            continue
        valid["feature_value"] = values.loc[valid.index]
        valid["feature_bin"] = pd.qcut(
            valid["feature_value"].rank(method="first"),
            q=4,
            labels=["Q1", "Q2", "Q3", "Q4"],
        )
        for label, group in valid.groupby("feature_bin", observed=False):
            pnl = pd.to_numeric(group["realized_pnl"], errors="coerce")
            r_multiple = pd.to_numeric(group["r_multiple"], errors="coerce")
            rows.append(
                {
                    "feature": feature,
                    "sample_segment": "discovery",
                    "feature_bin": str(label),
                    "candidate_count": int(len(group)),
                    "product_count": int(group["product"].astype(str).nunique()),
                    "direction_count": int(group["direction"].astype(str).nunique()),
                    "year_count": int(pd.to_datetime(group["entry_date"]).dt.year.nunique()),
                    "feature_min": float(group["feature_value"].min()),
                    "feature_max": float(group["feature_value"].max()),
                    "total_pnl": float(pnl.sum()),
                    "total_r": float(r_multiple.sum()),
                    "mean_r": float(r_multiple.mean()) if r_multiple.notna().any() else np.nan,
                    "winner_rate": float(r_multiple.gt(0.0).mean()) if r_multiple.notna().any() else np.nan,
                }
            )
    result = pd.DataFrame(rows)
    return result.sort_values(["feature", "feature_bin"]).reset_index(drop=True) if not result.empty else result


def canonical_attribution_trades(trades: pd.DataFrame) -> pd.DataFrame:
    """Encode the engine's numeric trade sequence so downstream string sorts stay chronological."""
    frame = trades.copy()
    if frame.empty:
        return frame
    required = {"datetime", "vt_symbol", "trade_id"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"trades missing canonical order fields: {sorted(missing)}")
    source_ids = frame.get("trade_id_source", frame["trade_id"]).astype(str)
    current_ids = frame["trade_id"].astype(str)
    parts = current_ids.str.extract(r"^(.*?)(\d+)$")
    if parts.isna().any(axis=None):
        bad = current_ids.loc[parts.isna().any(axis=1)].tolist()
        raise RuntimeError(f"trade id has no numeric engine sequence: {bad}")
    sequence = pd.to_numeric(parts[1], errors="raise").astype("int64")
    canonical_ids = parts[0].astype(str) + sequence.map(lambda value: f"{int(value):020d}")
    if canonical_ids.duplicated().any():
        raise RuntimeError(f"canonical trade id collision: {canonical_ids.loc[canonical_ids.duplicated(False)].tolist()}")
    frame["trade_id_source"] = source_ids
    frame["trade_sequence"] = sequence
    frame["trade_id"] = canonical_ids
    frame["datetime"] = pd.to_datetime(frame["datetime"], errors="coerce")
    if frame["datetime"].isna().any():
        raise RuntimeError("trade datetime parse failed during canonical ordering")
    frame = frame.sort_values(["datetime", "vt_symbol", "trade_sequence", "trade_id"]).reset_index(drop=True)
    return frame


def terminal_open_inventory(
    trades: pd.DataFrame,
    positions: pd.DataFrame,
    metadata: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """FIFO mark remaining lots to the engine's terminal close and reconcile positions."""
    trade_data = canonical_attribution_trades(trades)
    if trade_data.empty:
        trade_data = pd.DataFrame(columns=["datetime", "vt_symbol", "trade_id", "offset", "direction", "price", "volume"])
    required_trade = {"datetime", "vt_symbol", "trade_id", "offset", "direction", "price", "volume"}
    missing_trade = required_trade - set(trade_data.columns)
    if missing_trade:
        raise ValueError(f"trades missing terminal inventory fields: {sorted(missing_trade)}")
    trade_data["datetime"] = pd.to_datetime(trade_data["datetime"], errors="coerce")
    trade_data["price"] = pd.to_numeric(trade_data["price"], errors="coerce")
    trade_data["volume"] = pd.to_numeric(trade_data["volume"], errors="coerce")
    trade_data = trade_data.dropna(subset=["datetime", "price", "volume"])
    trade_data = trade_data.sort_values(["datetime", "vt_symbol", "trade_sequence", "trade_id"])

    queues: dict[tuple[str, str], deque[dict[str, Any]]] = {}
    for trade in trade_data.to_dict("records"):
        offset = str(trade["offset"]).strip().lower()
        direction = str(trade["direction"]).strip().lower()
        if direction not in {"long", "short"}:
            raise RuntimeError(f"unsupported trade direction: {trade['direction']}")
        position_direction = direction if offset == "open" else ("short" if direction == "long" else "long")
        key = (str(trade["vt_symbol"]), position_direction)
        volume = _safe_float(trade.get("volume"), 0.0)
        if volume <= 0:
            continue
        if offset == "open":
            queues.setdefault(key, deque()).append(
                {
                    "open_trade_id": str(trade["trade_id"]),
                    "entry_datetime": pd.Timestamp(trade["datetime"]),
                    "entry_price": _safe_float(trade["price"]),
                    "remaining_volume": volume,
                }
            )
            continue
        queue = queues.setdefault(key, deque())
        remaining = volume
        while remaining > 1e-8 and queue:
            lot = queue[0]
            matched = min(float(lot["remaining_volume"]), remaining)
            lot["remaining_volume"] = float(lot["remaining_volume"]) - matched
            remaining -= matched
            if float(lot["remaining_volume"]) <= 1e-8:
                queue.popleft()
        if remaining > 1e-8:
            raise RuntimeError(f"terminal inventory close exceeds FIFO opens: {key} residual={remaining}")

    position_data = positions.copy()
    required_position = {"date", "vt_symbol", "end_pos", "close_price"}
    missing_position = required_position - set(position_data.columns)
    if missing_position:
        raise ValueError(f"positions missing terminal inventory fields: {sorted(missing_position)}")
    position_data["date"] = pd.to_datetime(position_data["date"], errors="coerce").dt.normalize()
    position_data["end_pos"] = pd.to_numeric(position_data["end_pos"], errors="coerce").fillna(0.0)
    position_data["close_price"] = pd.to_numeric(position_data["close_price"], errors="coerce")
    position_data = position_data.dropna(subset=["date", "vt_symbol", "close_price"])
    terminal_date = position_data["date"].max() if not position_data.empty else pd.NaT
    terminal = position_data.loc[position_data["date"].eq(terminal_date)].copy() if pd.notna(terminal_date) else position_data
    actual_by_symbol = terminal.groupby("vt_symbol")["end_pos"].sum().to_dict()
    close_by_symbol = terminal.drop_duplicates("vt_symbol", keep="last").set_index("vt_symbol")["close_price"].to_dict()

    expected_by_symbol: dict[str, float] = {}
    for (vt_symbol, position_direction), queue in queues.items():
        volume = float(sum(float(lot["remaining_volume"]) for lot in queue))
        expected_by_symbol[vt_symbol] = expected_by_symbol.get(vt_symbol, 0.0) + (volume if position_direction == "long" else -volume)
    all_symbols = sorted(set(actual_by_symbol) | set(expected_by_symbol))
    mismatches = {
        symbol: {"fifo": expected_by_symbol.get(symbol, 0.0), "engine": _safe_float(actual_by_symbol.get(symbol), 0.0)}
        for symbol in all_symbols
        if abs(expected_by_symbol.get(symbol, 0.0) - _safe_float(actual_by_symbol.get(symbol), 0.0)) > 1e-8
    }
    if mismatches:
        raise RuntimeError(f"terminal position mismatch: {mismatches}")

    sizes = metadata.get("sizes", {})
    rows: list[dict[str, Any]] = []
    for (vt_symbol, position_direction), queue in sorted(queues.items()):
        if not queue:
            continue
        terminal_close = _safe_float(close_by_symbol.get(vt_symbol))
        size = _safe_float(sizes.get(vt_symbol))
        if not np.isfinite(terminal_close) or not np.isfinite(size) or size <= 0:
            raise RuntimeError(f"terminal mark input missing: {vt_symbol} close={terminal_close} size={size}")
        for lot in queue:
            entry_price = _safe_float(lot["entry_price"])
            volume = _safe_float(lot["remaining_volume"])
            pnl = (
                (terminal_close - entry_price) * size * volume
                if position_direction == "long"
                else (entry_price - terminal_close) * size * volume
            )
            rows.append(
                {
                    "vt_symbol": vt_symbol,
                    "position_direction": position_direction,
                    "open_trade_id": lot["open_trade_id"],
                    "entry_datetime": lot["entry_datetime"],
                    "entry_price": entry_price,
                    "remaining_volume": volume,
                    "size": size,
                    "terminal_date": terminal_date,
                    "terminal_close_price": terminal_close,
                    "unrealized_pnl": pnl,
                }
            )
    result = pd.DataFrame(rows)
    terminal_unrealized = float(pd.to_numeric(result.get("unrealized_pnl", pd.Series(dtype=float)), errors="coerce").sum())
    audit = {
        "terminal_date": terminal_date,
        "open_lot_count": int(len(result)),
        "open_symbol_count": int(result["vt_symbol"].nunique()) if not result.empty else 0,
        "terminal_unrealized_pnl": terminal_unrealized,
        "position_reconciliation_pass": True,
        "position_mismatch_count": 0,
    }
    return result, audit


def audit_source_volume_mismatches(lineage: pd.DataFrame, trade_events: pd.DataFrame) -> dict[str, Any]:
    required = {
        "open_trade_id",
        "vt_symbol",
        "direction",
        "source_datetime",
        "volume",
        "source_selected_volume",
        "attempt_kind",
    }
    missing = required - set(lineage.columns)
    if missing:
        raise ValueError(f"lineage missing source-volume fields: {sorted(missing)}")
    event_required = {"date", "vt_symbol", "position_direction", "reason", "volume"}
    missing_events = event_required - set(trade_events.columns)
    if missing_events:
        raise ValueError(f"trade events missing forced-deleverage fields: {sorted(missing_events)}")
    roots = lineage[lineage["attempt_kind"].astype(str).isin(["flat_entry", "rollover_reopen"])].copy()
    roots["actual_volume"] = pd.to_numeric(roots["volume"], errors="coerce")
    roots["planned_volume"] = pd.to_numeric(roots["source_selected_volume"], errors="coerce")
    roots["volume_difference"] = roots["planned_volume"] - roots["actual_volume"]
    mismatch = roots[roots["volume_difference"].abs().gt(1e-8)].copy()
    forced = trade_events.copy()
    forced["event_date"] = pd.to_datetime(forced["date"], errors="coerce").dt.normalize()
    forced["event_direction"] = forced["position_direction"].astype(str).str.lower()
    forced["event_volume"] = pd.to_numeric(forced["volume"], errors="coerce")
    forced = forced.loc[forced["reason"].astype(str).eq("forced_margin_deleverage")].copy()
    forced.reset_index(drop=False, inplace=True)
    forced.rename(columns={"index": "forced_event_source_index"}, inplace=True)
    forced["forced_event_id"] = np.arange(len(forced), dtype=int)

    evidence_rows: list[dict[str, Any]] = []
    explained_flags: list[bool] = []
    used_forced_event_ids: set[int] = set()
    for row in mismatch.to_dict("records"):
        source_date = pd.to_datetime(row.get("source_datetime"), errors="coerce", utc=True)
        if pd.notna(source_date):
            source_date = source_date.tz_convert("Asia/Shanghai").tz_localize(None).normalize()
        matching = forced[
            forced["event_date"].eq(source_date)
            & forced["vt_symbol"].astype(str).eq(str(row.get("vt_symbol", "")))
            & forced["event_direction"].eq(str(row.get("direction", "")).lower())
            & ~forced["forced_event_id"].isin(used_forced_event_ids)
        ]
        difference = _safe_float(row.get("volume_difference"))
        exact_rows = matching.loc[(matching["event_volume"] - difference).abs().le(1e-8)].copy()
        exact = bool(difference > 0 and len(exact_rows) == 1)
        selected_event_id: int | None = None
        forced_volume = 0.0
        forced_event_source_index: int | None = None
        if exact:
            selected = exact_rows.sort_values(["forced_event_id"]).iloc[0]
            selected_event_id = int(selected["forced_event_id"])
            used_forced_event_ids.add(selected_event_id)
            forced_volume = float(selected["event_volume"])
            forced_event_source_index = int(selected["forced_event_source_index"])
        explained_flags.append(exact)
        evidence_rows.append(
            {
                "open_trade_id": str(row.get("open_trade_id", "")),
                "vt_symbol": str(row.get("vt_symbol", "")),
                "direction": str(row.get("direction", "")).lower(),
                "source_date": source_date,
                "planned_volume": _safe_float(row.get("planned_volume")),
                "actual_volume": _safe_float(row.get("actual_volume")),
                "planned_minus_actual_volume": difference,
                "eligible_unused_forced_event_count": int(len(matching)),
                "exact_unused_forced_event_count": int(len(exact_rows)),
                "forced_event_id": selected_event_id,
                "forced_event_source_index": forced_event_source_index,
                "forced_event_volume": forced_volume,
                "exact_causal_match": exact,
            }
        )
    mismatch["explained"] = explained_flags
    unexplained = mismatch[~mismatch["explained"]]
    audit = {
        "root_open_count": int(len(roots)),
        "mismatch_count": int(len(mismatch)),
        "explained_mismatch_count": int(mismatch["explained"].sum()) if not mismatch.empty else 0,
        "unexplained_mismatch_count": int(len(unexplained)),
        "exact_causal_event_count": int(sum(explained_flags)),
        "consumed_forced_event_count": int(len(used_forced_event_ids)),
        "max_planned_minus_actual_volume": float(mismatch["volume_difference"].max()) if not mismatch.empty else 0.0,
        "mismatch_open_trade_ids": mismatch["open_trade_id"].astype(str).tolist(),
        "unexplained_open_trade_ids": unexplained["open_trade_id"].astype(str).tolist(),
        "causal_event_matches": evidence_rows,
    }
    if not unexplained.empty:
        raise RuntimeError(f"unexplained source volume mismatch: {audit}")
    return audit


def _attach_features(events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if events.empty:
        return events.copy(), pd.DataFrame()
    cache: dict[str, pd.DataFrame] = {}
    rows: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    database_sha256 = _sha256(DATABASE_PATH)
    for event in events.to_dict("records"):
        vt_symbol = str(event["vt_symbol"])
        if vt_symbol not in cache:
            bars = legacy.load_contract_bars_from_database(vt_symbol, DATABASE_PATH)
            cache[vt_symbol] = indicator_panel(bars) if not bars.empty else pd.DataFrame()
            sources.append(
                {
                    "vt_symbol": vt_symbol,
                    "database_path": str(DATABASE_PATH),
                    "database_sha256": database_sha256,
                    "bar_count": int(len(bars)),
                    "first_bar_date": bars["date"].min() if not bars.empty else pd.NaT,
                    "last_bar_date": bars["date"].max() if not bars.empty else pd.NaT,
                    "feature_source_exists": int(not bars.empty),
                }
            )
        panel = cache[vt_symbol]
        features = features_before_entry(panel, event["entry_date"], event["direction"]) if not panel.empty else {
            "feature_date": pd.NaT,
            "feature_bar_count": 0,
            **{name: np.nan for name in NEW_FEATURE_COLUMNS},
        }
        stop_distance = _safe_float(event.get("stop_distance"))
        atr14 = _safe_float(features.get("atr14"))
        feature_date = features.get("feature_date")
        entry_date = pd.Timestamp(event["entry_date"]).normalize()
        rows.append(
            {
                **event,
                **features,
                "stop_atr14": stop_distance / atr14 if stop_distance > 0 and atr14 > 0 else np.nan,
                "entry_year": int(entry_date.year),
                "sample_segment": _sample_segment(entry_date),
                "feature_future_violation": int(
                    pd.notna(feature_date) and pd.Timestamp(feature_date).normalize() >= entry_date
                ),
            }
        )
    result = pd.DataFrame(rows)
    assert_no_new_ai_features(result.loc[:, [column for column in result.columns if column in NEW_FEATURE_COLUMNS]])
    source_frame = pd.DataFrame(sources).sort_values("vt_symbol").reset_index(drop=True)
    return result, source_frame


def _annual_path(daily: pd.DataFrame, capital: float = EXPECTED_CAPITAL) -> pd.DataFrame:
    frame = daily.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    frame = frame.dropna(subset=["date"]).sort_values("date")
    frame["year"] = frame["date"].dt.year
    rows: list[dict[str, Any]] = []
    previous_year_end = float(capital)
    for year, group in frame.groupby("year"):
        equity = pd.to_numeric(group["account_equity"], errors="coerce").ffill()
        base = previous_year_end
        equity_with_base = pd.concat([pd.Series([base]), equity.reset_index(drop=True)], ignore_index=True)
        drawdown = equity_with_base / equity_with_base.cummax().replace(0.0, np.nan) - 1.0
        rows.append(
            {
                "year": int(year),
                "start_date": group["date"].iloc[0],
                "end_date": group["date"].iloc[-1],
                "start_equity": base,
                "end_equity": float(equity.iloc[-1]),
                "year_pnl": float(pd.to_numeric(group["net_pnl"], errors="coerce").fillna(0.0).sum()),
                "year_return_pct_on_start_equity": float((equity.iloc[-1] / base - 1.0) * 100.0) if base else np.nan,
                "within_year_max_dd_pct": float(drawdown.min() * 100.0),
                "trade_count": float(pd.to_numeric(group.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
                "slippage": float(pd.to_numeric(group.get("slippage", 0.0), errors="coerce").fillna(0.0).sum()),
            }
        )
        previous_year_end = float(equity.iloc[-1])
    return pd.DataFrame(rows)


def _drawdown_episodes(daily: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    frame = daily.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    frame = frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    equity = pd.to_numeric(frame["account_equity"], errors="coerce").ffill()
    drawdown = equity / equity.cummax().replace(0.0, np.nan) - 1.0
    event_data = events.copy()
    if not event_data.empty:
        event_data["entry_date"] = pd.to_datetime(event_data["entry_date"], errors="coerce").dt.normalize()
    rows: list[dict[str, Any]] = []
    episode_start: int | None = None
    for index, value in enumerate(drawdown.to_numpy(dtype=float)):
        below = bool(np.isfinite(value) and value < -1e-12)
        if below and episode_start is None:
            episode_start = max(0, index - 1)
        is_last = index == len(frame) - 1
        if episode_start is None or (below and not is_last):
            continue
        recovered = not below
        episode_end = index
        episode_equity = equity.iloc[episode_start : episode_end + 1]
        episode_drawdown = drawdown.iloc[episode_start : episode_end + 1]
        trough_index = int(episode_equity.idxmin())
        peak_date = pd.Timestamp(frame.loc[episode_start, "date"]).normalize()
        trough_date = pd.Timestamp(frame.loc[trough_index, "date"]).normalize()
        recovery_date = pd.Timestamp(frame.loc[episode_end, "date"]).normalize() if recovered else pd.NaT
        if event_data.empty:
            selected = event_data
        else:
            selected = event_data[
                event_data["entry_date"].gt(peak_date) & event_data["entry_date"].le(trough_date)
            ]
        rows.append(
            {
                "peak_date": peak_date,
                "trough_date": trough_date,
                "recovery_date": recovery_date,
                "peak_equity": float(equity.iloc[episode_start]),
                "trough_equity": float(equity.iloc[trough_index]),
                "drawdown_pct": float(drawdown.iloc[trough_index] * 100.0),
                "underwater_trading_days": int(episode_drawdown.lt(-1e-12).sum()),
                "entry_event_count_peak_to_trough": int(len(selected)),
                "entry_event_pnl_peak_to_trough": float(
                    pd.to_numeric(selected.get("realized_pnl", pd.Series(dtype=float)), errors="coerce").sum()
                ),
                "entry_event_r_sum_peak_to_trough": float(
                    pd.to_numeric(selected.get("r_multiple", pd.Series(dtype=float)), errors="coerce").sum()
                ),
                "recovered": int(recovered),
            }
        )
        episode_start = None
    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values("drawdown_pct").reset_index(drop=True)
        result.insert(0, "episode_rank", np.arange(1, len(result) + 1))
    return result


def _plot_baseline(daily: pd.DataFrame, annual: pd.DataFrame) -> None:
    frame = daily.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    frame = frame.dropna(subset=["date"]).sort_values("date")
    equity = pd.to_numeric(frame["account_equity"], errors="coerce").ffill()
    nav = equity / EXPECTED_CAPITAL
    drawdown = (equity / equity.cummax().replace(0.0, np.nan) - 1.0) * 100.0
    fig, axes = plt.subplots(3, 1, figsize=(18, 14), constrained_layout=True)
    axes[0].plot(frame["date"], equity, color="#1f77b4", linewidth=1.25)
    axes[0].axhline(EXPECTED_CAPITAL, color="#111827", linestyle=":", linewidth=0.9)
    axes[0].set_title("Stage008 fresh official baseline: absolute equity")
    axes[0].set_ylabel("account equity")
    axes[1].plot(frame["date"], nav, color="#2ca02c", linewidth=1.15)
    axes[1].set_title("Normalized NAV and drawdown")
    axes[1].set_ylabel("NAV")
    drawdown_axis = axes[1].twinx()
    drawdown_axis.fill_between(frame["date"], drawdown, 0.0, color="#d62728", alpha=0.20)
    drawdown_axis.set_ylabel("drawdown %")
    colors = ["#2ca02c" if value >= 0 else "#d62728" for value in annual["year_pnl"]]
    axes[2].bar(annual["year"].astype(str), annual["year_pnl"], color=colors, alpha=0.85)
    axes[2].axhline(0.0, color="#111827", linewidth=0.8)
    axes[2].set_title("Annual net PnL")
    axes[2].set_ylabel("net PnL")
    for axis in axes:
        axis.grid(alpha=0.2)
    fig.savefig(BASELINE_CHART_PATH, dpi=170)
    plt.close(fig)


def _plot_discovery_bins(bins: pd.DataFrame) -> None:
    features = list(BIN_FEATURES)
    fig, axes = plt.subplots(2, 2, figsize=(16, 11), constrained_layout=True)
    for axis, feature in zip(axes.flat, features):
        part = bins.loc[bins["feature"].eq(feature)].copy()
        axis.bar(part["feature_bin"], part["total_r"], color="#4c78a8", alpha=0.9)
        axis.axhline(0.0, color="#111827", linewidth=0.8)
        axis.set_title(f"Discovery only: {feature}")
        axis.set_ylabel("total R")
        axis.grid(axis="y", alpha=0.2)
    fig.savefig(DISCOVERY_CHART_PATH, dpi=170)
    plt.close(fig)


def _write_manifest(paths: list[Path], destination: Path) -> pd.DataFrame:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise RuntimeError(f"manifest inputs missing: {missing}")
    frame = pd.DataFrame(
        [{"path": str(path), "bytes": path.stat().st_size, "sha256": _sha256(path)} for path in paths]
    )
    frame.to_csv(destination, index=False)
    return frame


def _repo_runtime_module_paths() -> list[Path]:
    paths: set[Path] = set()
    for module in sys.modules.values():
        file_name = getattr(module, "__file__", None)
        if not file_name:
            continue
        path = Path(file_name).resolve()
        if path.is_relative_to(ROOT / ".py311"):
            continue
        if path.exists() and path.is_file() and path.is_relative_to(ROOT) and path.suffix in {".py", ".pyi"}:
            paths.add(path)
    return sorted(paths)


def _tag(frame: pd.DataFrame) -> pd.DataFrame:
    return strict._tag_evidence(frame, START, VARIANT) if not frame.empty else frame.copy()


def _run_fresh_strict_baseline() -> tuple[pd.DataFrame, dict[str, pd.DataFrame], dict[str, Any]]:
    if OFFICIAL_LIVE_VERSION != EXPECTED_VERSION:
        raise RuntimeError(f"official live version drift: {OFFICIAL_LIVE_VERSION}")
    if abs(float(OFFICIAL_LIVE_CAPITAL) - EXPECTED_CAPITAL) > 1e-9:
        raise RuntimeError(f"official capital drift: {OFFICIAL_LIVE_CAPITAL}")
    metadata = strict.s901.s513._metadata()
    daily, frames = strict._run_official_repaired(metadata, START)
    if daily.empty:
        raise RuntimeError("strict fresh baseline returned no daily rows")
    return daily, frames, metadata


def main() -> None:
    prepare_output_directory(OUT, legacy_paths=[LEGACY_ENTRY_EVENTS_PRIVATE_PATH])
    database_sha256_before = _sha256(DATABASE_PATH)
    print("[stage008] strict fresh baseline start", flush=True)
    daily, frames, metadata = _run_fresh_strict_baseline()
    summary_row = strict.summarize_curve(daily, START, VARIANT)
    summary = pd.DataFrame([summary_row])
    tagged_daily = strict._tag_curve(daily, START, VARIANT)
    trades = _tag(frames.get("trades", pd.DataFrame()))
    entry_risk = _tag(frames.get("entry_risk", pd.DataFrame()))
    entry_candidates = _tag(frames.get("entry_candidates", pd.DataFrame()))
    trade_events = _tag(frames.get("trade_events", pd.DataFrame()))
    stop_retry_events = _tag(frames.get("stop_retry_events", pd.DataFrame()))

    account_audit = strict.validate_account_equity_evidence(entry_candidates, tagged_daily)
    retry_audit = strict.stop_retry_audit(trades, stop_retry_events, summary)
    pool, _ = strict.s167._load_ai_pool()
    ai_audit = strict.s167._ai_month_audit(entry_candidates, summary, pool)
    if ai_audit.empty or ai_audit["status"].astype(str).eq("FAIL").any():
        raise RuntimeError("official AI monthly pool audit failed")
    ai_full_audit = full_ai_pool_membership_audit(entry_candidates, pool)

    raw_frames = frames
    attribution_trades = canonical_attribution_trades(raw_frames.get("trades", pd.DataFrame()))
    closed_raw = legacy.s719._build_closed_lots(
        attribution_trades,
        raw_frames.get("entry_risk", pd.DataFrame()),
        raw_frames.get("entry_candidates", pd.DataFrame()),
        metadata,
    )
    closed_raw = legacy.s719._finalize_path_efficiency(closed_raw)
    available = [column for column in legacy.SANITIZED_CLOSED_LOT_COLUMNS if column in closed_raw.columns]
    closed = closed_raw.loc[:, available].copy()
    closed, open_lineage, lineage_audit = legacy.build_complete_closed_lot_lineage(
        closed,
        attribution_trades,
        raw_frames.get("entry_risk", pd.DataFrame()),
        raw_frames.get("entry_candidates", pd.DataFrame()),
        priceticks=metadata.get("priceticks", {}),
    )
    risk_bearing = open_lineage[open_lineage["attempt_kind"].astype(str).isin(["flat_entry", "stop_retry"])]
    missing_actual_risk = risk_bearing[risk_bearing["actual_risk_recomputed"].ne(1)]
    if not missing_actual_risk.empty:
        raise RuntimeError(
            "risk-bearing opens missing actual fill risk: "
            + repr(missing_actual_risk["open_trade_id"].astype(str).tolist())
        )
    risk_source_audit = lineage_audit["risk_source_audit"]
    candidate_source_audit = lineage_audit["candidate_source_audit"]
    if int(risk_source_audit.get("unmatched_root_open_count", 1)) != 0:
        raise RuntimeError(f"root opens missing exact risk source: {risk_source_audit}")
    source_volume_audit = audit_source_volume_mismatches(open_lineage, trade_events)
    events, aggregation_audit = legacy.aggregate_entry_events(closed)
    if aggregation_audit["inconsistent_group_count"]:
        raise RuntimeError(f"inconsistent entry event groups: {aggregation_audit['inconsistent_open_trade_ids']}")
    daily_gross_pnl = float(
        (
            pd.to_numeric(daily["net_pnl"], errors="coerce").fillna(0.0)
            + pd.to_numeric(daily.get("slippage", 0.0), errors="coerce").fillna(0.0)
            + pd.to_numeric(daily.get("commission", 0.0), errors="coerce").fillna(0.0)
        ).sum()
    )
    event_gross_pnl = float(pd.to_numeric(events["realized_pnl"], errors="coerce").sum())
    terminal_open_lots, terminal_inventory_audit = terminal_open_inventory(
        raw_frames.get("trades", pd.DataFrame()),
        raw_frames.get("positions", pd.DataFrame()),
        metadata,
    )
    gross_reconciled = event_gross_pnl + float(terminal_inventory_audit["terminal_unrealized_pnl"])
    aggregation_audit.update(
        {
            "lineage_audit": lineage_audit,
            "daily_gross_pnl": daily_gross_pnl,
            "entry_event_gross_pnl": event_gross_pnl,
            "terminal_inventory_audit": terminal_inventory_audit,
            "closed_plus_terminal_unrealized_pnl": gross_reconciled,
            "daily_gross_minus_closed_and_terminal": daily_gross_pnl - gross_reconciled,
        }
    )
    if abs(daily_gross_pnl - gross_reconciled) > 1e-6:
        raise RuntimeError(
            "closed plus terminal unrealized PnL does not reconcile to daily gross PnL: "
            + json.dumps(_json_safe(aggregation_audit), ensure_ascii=False)
        )

    events, source_audit = _attach_features(events)
    expected_products = events["vt_symbol"].map(legacy._canonical_product_vt_symbol)
    product_mismatch = ~events["product"].astype(str).eq(expected_products.astype(str))
    if product_mismatch.any():
        raise RuntimeError(
            "entry-event product lineage mismatch: "
            + repr(events.loc[product_mismatch, ["open_trade_id", "vt_symbol", "product"]].head(20).to_dict("records"))
        )
    if int(events["feature_future_violation"].sum()) != 0:
        raise RuntimeError("feature timestamp is not strictly before entry date")
    core = ["stop_atr14", *NEW_FEATURE_COLUMNS]
    core_coverage = float(events[core].notna().all(axis=1).mean()) if len(events) else 0.0
    assert_no_new_ai_features(events)
    if core_coverage < MIN_CORE_COVERAGE:
        raise RuntimeError(f"core feature coverage below {MIN_CORE_COVERAGE:.0%}: {core_coverage:.6f}")
    thresholds = pd.DataFrame([discovery_distribution_thresholds(events)])
    bins = discovery_feature_bin_summary(events)
    annual = _annual_path(daily)
    episodes = _drawdown_episodes(daily, events)

    discovery_events, future_seal = partition_event_outputs(events)

    database_sha256_after = _sha256(DATABASE_PATH)
    if database_sha256_before != database_sha256_after:
        raise RuntimeError("history database changed during Stage008")
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_profile": OFFICIAL_LIVE_PROFILE_NAME,
        "capital": EXPECTED_CAPITAL,
        "fresh_baseline": True,
        "old_stage_outputs_read": False,
        "strategy_changed": False,
        "new_ai_feature_count": 0,
        "ai_pool_shared_official_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "core_feature_coverage_ratio": core_coverage,
        "strict_account_equity_audit": account_audit,
        "full_ai_pool_membership_audit": ai_full_audit,
        "source_volume_mismatch_audit": source_volume_audit,
        "aggregation_audit": aggregation_audit,
        "database_sha256_before": database_sha256_before,
        "database_sha256_after": database_sha256_after,
        "database_unchanged": True,
        "future_feature_seal": future_seal,
        "baseline_summary": summary_row,
        "decision": "stage008_baseline_verified_historical_path_no_true_oos_claim",
        "stage009_allowed": False,
        "stage009_historical_locked_evaluation_allowed": True,
        "true_oos_available": False,
        "overfit_before": "中高但受控：沿用昨晚机制方向，旧结果清零；特征、切分和阈值生成方式在重跑前冻结。",
        "overfit_after": (
            "高：独立复核确认基准数字可信，但全期基准结果已持久化；后段只能作为"
            "分钟新特征预声明后的历史锁定评估，不能称为真正 OOS。"
        ),
        "continue_before": "有价值：先确认主策略真实路径、亏损阶段和紧止损趋势位置是否存在稳定统计结构。",
        "continue_after": (
            "有价值：允许继续分钟新特征的历史锁定评估，但降低证据等级；最终晋级仍需"
            "2026-06-30 后 forward 数据。"
        ),
        "external_research": EXTERNAL_RESEARCH,
    }

    tagged_daily.to_csv(DAILY_PATH, index=False, compression="gzip")
    summary.to_csv(SUMMARY_PATH, index=False)
    trades.to_csv(TRADES_PATH, index=False, compression="gzip")
    attribution_trades.to_csv(ATTRIBUTION_TRADES_PATH, index=False, compression="gzip")
    entry_risk.to_csv(ENTRY_RISK_PATH, index=False, compression="gzip")
    entry_candidates.to_csv(ENTRY_CANDIDATES_PATH, index=False, compression="gzip")
    trade_events.to_csv(TRADE_EVENTS_PATH, index=False, compression="gzip")
    stop_retry_events.to_csv(STOP_RETRY_EVENTS_PATH, index=False, compression="gzip")
    retry_audit.to_csv(STOP_RETRY_AUDIT_PATH, index=False)
    ai_audit.to_csv(AI_MONTH_AUDIT_PATH, index=False)
    pd.DataFrame([ai_full_audit]).to_csv(AI_FULL_AUDIT_PATH, index=False)
    closed.to_csv(CLOSED_LOTS_PATH, index=False, compression="gzip")
    terminal_open_lots.to_csv(TERMINAL_OPEN_LOTS_PATH, index=False)
    open_lineage.to_csv(OPEN_LINEAGE_PATH, index=False, compression="gzip")
    discovery_events.to_csv(DISCOVERY_EVENTS_PATH, index=False, compression="gzip")
    FUTURE_FEATURE_SEAL_PATH.write_text(json.dumps(_json_safe(future_seal), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    thresholds.to_csv(THRESHOLDS_PATH, index=False)
    bins.to_csv(FEATURE_BIN_SUMMARY_PATH, index=False)
    annual.to_csv(ANNUAL_PATH, index=False)
    episodes.to_csv(DRAWDOWN_EPISODES_PATH, index=False)
    source_audit.to_csv(SOURCE_AUDIT_PATH, index=False)
    pd.DataFrame([source_volume_audit]).to_csv(SOURCE_VOLUME_AUDIT_PATH, index=False)
    _plot_baseline(daily, annual)
    _plot_discovery_bins(bins)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Stage008 主策略独立基线与突破质量归因",
                "",
                f"- 生成时间：`{decision['generated_at']}`",
                f"- 正式版本：`{OFFICIAL_LIVE_VERSION}`",
                f"- 决策：`{decision['decision']}`",
                "- 本轮未改变策略，未读取 Stage001-004 旧输出，未新增 AI 特征。",
                (
                    "- 后段新特征逐行数据不落盘，仅保存白名单特征 hash；完整基准 daily/trades/closed-lots "
                    "结果已持久化，因此后段只属于历史锁定评估，不构成真正未见 OOS。"
                ),
                "",
                "## 主策略基线",
                "",
                _md_table(summary),
                "",
                "## 年度路径",
                "",
                _md_table(annual),
                "",
                "## 最大回撤阶段",
                "",
                _md_table(episodes.head(12)),
                "",
                "## Discovery 分布阈值",
                "",
                _md_table(thresholds),
                "",
                "## Discovery 特征分箱",
                "",
                _md_table(bins),
                "",
                "## 严格执行审计",
                "",
                f"- 账户权益证据：`{json.dumps(_json_safe(account_audit), ensure_ascii=False)}`",
                f"- 闭合交易守恒：`{json.dumps(_json_safe(aggregation_audit), ensure_ascii=False)}`",
                f"- 核心特征覆盖率：`{core_coverage:.4%}`",
                f"- AI 池成员全量联表：`{json.dumps(_json_safe(ai_full_audit), ensure_ascii=False)}`",
                f"- source 计划/成交手数解释：`{json.dumps(_json_safe(source_volume_audit), ensure_ascii=False)}`",
                "",
                "## 外部调研判断",
                "",
                *[f"- [{item['source']}]({item['url']})：{item['judgment']}" for item in EXTERNAL_RESEARCH],
                "",
                "## 反思",
                "",
                f"- 过拟合：{decision['overfit_after']}",
                f"- 继续价值：{decision['continue_after']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    input_paths = [
        Path(__file__),
        Path(legacy.__file__),
        Path(strict.__file__),
        Path(strict.s000.__file__),
        Path(strict.s847.__file__),
        Path(strict.s901.__file__),
        PORTFOLIO_DIR / "qmt_roll_official_live_config.py",
        PORTFOLIO_DIR / "qmt_roll_portfolio_strategy.py",
        DATABASE_PATH,
        Path(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        strict.REPAIRED_MINUTE_PATCH_PATH,
        strict.REPAIRED_MINUTE_AUDIT_PATH,
        Path(strict.s000.DECISION_PATH),
        ROOT / "research" / "registry.md",
        LINE_DIR / "LINE.md",
        LINE_DIR / "stages" / "20260714_1400_stage008_fresh_baseline_breakout_quality_predecl.md",
        LINE_DIR / "tests" / "test_stage001_baseline_technical_attribution.py",
        LINE_DIR / "tests" / "test_stage008_fresh_baseline_breakout_quality_attribution.py",
    ]
    input_paths = sorted(set(input_paths) | set(_repo_runtime_module_paths()))
    _write_manifest(input_paths, INPUT_MANIFEST_PATH)
    output_paths = [
        DAILY_PATH,
        SUMMARY_PATH,
        TRADES_PATH,
        ATTRIBUTION_TRADES_PATH,
        ENTRY_RISK_PATH,
        ENTRY_CANDIDATES_PATH,
        TRADE_EVENTS_PATH,
        STOP_RETRY_EVENTS_PATH,
        STOP_RETRY_AUDIT_PATH,
        AI_MONTH_AUDIT_PATH,
        AI_FULL_AUDIT_PATH,
        CLOSED_LOTS_PATH,
        TERMINAL_OPEN_LOTS_PATH,
        OPEN_LINEAGE_PATH,
        DISCOVERY_EVENTS_PATH,
        FUTURE_FEATURE_SEAL_PATH,
        THRESHOLDS_PATH,
        FEATURE_BIN_SUMMARY_PATH,
        ANNUAL_PATH,
        DRAWDOWN_EPISODES_PATH,
        SOURCE_AUDIT_PATH,
        SOURCE_VOLUME_AUDIT_PATH,
        BASELINE_CHART_PATH,
        DISCOVERY_CHART_PATH,
        DECISION_PATH,
        REPORT_PATH,
        INPUT_MANIFEST_PATH,
    ]
    _write_manifest(output_paths, OUTPUT_MANIFEST_PATH)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
