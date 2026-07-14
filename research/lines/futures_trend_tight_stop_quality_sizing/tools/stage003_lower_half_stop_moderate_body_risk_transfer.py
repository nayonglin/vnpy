from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import hashlib
import json
import math
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

import analyze_qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit as s167  # noqa: E402
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847  # noqa: E402
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901  # noqa: E402
import stage000_complete_entry_session_minute_repair as s000  # noqa: E402
from qmt_roll_official_live_config import (  # noqa: E402
    OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_CAPITAL_LABEL,
    OFFICIAL_LIVE_PROFILE_NAME,
    OFFICIAL_LIVE_VERSION,
    build_official_live_strategy_overrides,
)


LINE_ID = "futures_trend_tight_stop_quality_sizing"
STAGE = "Stage003"
MODEL_TAG = "stage003_lower_half_stop_moderate_body_risk_transfer_v1"
PROFILE_NAME = "stage003_lower_half_stop_moderate_body_risk_transfer"
OUTPUT_PREFIX = "tight_stop_quality_stage003"

STARTS = tuple(pd.Timestamp(value) for value in ("2020-01-01", "2021-01-01", "2022-01-01", "2024-01-01"))
END = pd.Timestamp("2026-06-30")
EXPECTED_CAPITAL = 150_000.0
EXPECTED_VERSION = "official_live_stage847_c9_15w_stage819_05r_stop_retry_once"

STOP_ATR_MAX = 0.515281
BODY_MIN_EXCLUSIVE = 0.312987012987013
BODY_MAX_INCLUSIVE = 0.5525550867323019
QUALITY_WEIGHT = 1.25
OTHER_WEIGHT = 0.75

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage003_lower_half_stop_moderate_body_risk_transfer"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMPARISON_PATH = OUT / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
TRADES_PATH = OUT / f"{OUTPUT_PREFIX}_ab_trades_{MODEL_TAG}.csv.gz"
ENTRY_CANDIDATES_PATH = OUT / f"{OUTPUT_PREFIX}_ab_entry_candidates_{MODEL_TAG}.csv.gz"
ENTRY_RISK_PATH = OUT / f"{OUTPUT_PREFIX}_ab_entry_risk_{MODEL_TAG}.csv.gz"
TRADE_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_ab_trade_events_{MODEL_TAG}.csv.gz"
STOP_RETRY_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_ab_stop_retry_events_{MODEL_TAG}.csv.gz"
STOP_RETRY_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_stop_retry_audit_{MODEL_TAG}.csv"
AI_MONTH_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_ai_month_audit_{MODEL_TAG}.csv"
CONFIG_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_config_audit_{MODEL_TAG}.csv"
FEATURE_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_feature_audit_{MODEL_TAG}.csv"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_four_anchor_equity_drawdown_{MODEL_TAG}.png"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
MANIFEST_PATH = OUT / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.csv"
INPUT_MANIFEST_PATH = OUT / f"{OUTPUT_PREFIX}_input_manifest_{MODEL_TAG}.csv"
REPAIRED_MINUTE_PATCH_PATH = s000.PATCH_PATH
REPAIRED_MINUTE_AUDIT_PATH = s000.AUDIT_PATH

_REPAIRED_MINUTE_GROUPS: dict[str, pd.DataFrame] | None = None
_REPAIRED_SESSION_KEYS: set[tuple[str, pd.Timestamp]] = set()
_REPAIRED_FIRST_OPEN: dict[tuple[str, pd.Timestamp], dict[str, Any]] = {}
_REPAIRED_RUNTIME_FAILURES: list[dict[str, Any]] = []
_STRICT_OPEN_RUNTIME_FAILURES: list[dict[str, Any]] = []

STAGE000_ACCOUNT_AUDIT_FIELDS = (
    "stage000_account_equity",
    "stage000_account_high_water",
    "stage000_account_drawdown_pct",
    "stage000_account_equity_source",
)

STAGE003_AUDIT_FIELDS = (
    "stage003_enabled",
    "stage003_feature_source",
    "stage003_feature_date",
    "stage003_feature_available",
    "stage003_feature_bar_count",
    "stage003_atr14",
    "stage003_stop_atr14",
    "stage003_body_ratio",
    "stage003_quality_hit",
    "stage003_recovery_exempt",
    "stage003_budget_weight",
    "stage003_reason",
    "stage003_stop_atr_max",
    "stage003_body_min_exclusive",
    "stage003_body_max_inclusive",
    "stage003_quality_weight",
    "stage003_other_weight",
    "stage003_risk_amount_before",
    "stage003_risk_amount_after",
    "stage003_contracts_by_risk_before",
    "stage003_contracts_by_risk_after",
    "stage003_selected_volume_after",
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
        return float(value) if np.isfinite(value) else None
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _md_table(frame: pd.DataFrame) -> str:
    return "_无记录_" if frame.empty else frame.to_markdown(index=False)


def is_ai_derived_field(column: str) -> bool:
    normalized = str(column).strip().lower()
    return normalized.startswith("ai_") or normalized == "ai" or "_ai_" in normalized or normalized.endswith("_ai")


def preview_entry_stop_price(direction: str, bar: Any, stop_loss_pct: float) -> float:
    close_price = float(bar.close_price)
    if direction == "long":
        return max(close_price * (1.0 - float(stop_loss_pct)), float(bar.low_price))
    return min(close_price * (1.0 + float(stop_loss_pct)), float(bar.high_price))


def t1_quality_snapshot(
    history: pd.DataFrame,
    stop_distance: float,
    *,
    feature_date: Any = None,
    stop_atr_max: float = STOP_ATR_MAX,
    body_min_exclusive: float = BODY_MIN_EXCLUSIVE,
    body_max_inclusive: float = BODY_MAX_INCLUSIVE,
) -> dict[str, Any]:
    fields = {
        "feature_date": feature_date,
        "feature_available": 0,
        "feature_bar_count": 0,
        "atr14": np.nan,
        "stop_atr14": np.nan,
        "body_ratio": np.nan,
        "quality_hit": 0,
    }
    if history is None or len(history) < 15:
        return fields
    # Engine history ends on the signal date, which is T-1 relative to the next-session fill.
    past = history.copy()
    fields["feature_bar_count"] = int(len(past))
    for column in ("open", "high", "low", "close"):
        past[column] = pd.to_numeric(past[column], errors="coerce")
    past = past.dropna(subset=["open", "high", "low", "close"])
    if len(past) < 15:
        return fields

    atr_values = talib.ATR(
        past["high"].to_numpy(dtype=float),
        past["low"].to_numpy(dtype=float),
        past["close"].to_numpy(dtype=float),
        timeperiod=14,
    )
    atr14 = _safe_float(atr_values[-1])
    last = past.iloc[-1]
    bar_range = _safe_float(last["high"] - last["low"])
    body_ratio = abs(_safe_float(last["close"]) - _safe_float(last["open"])) / bar_range if bar_range > 0 else np.nan
    stop_atr14 = float(stop_distance) / atr14 if atr14 > 0 and np.isfinite(stop_distance) else np.nan
    quality = bool(
        np.isfinite(stop_atr14)
        and np.isfinite(body_ratio)
        and stop_atr14 <= float(stop_atr_max)
        and body_ratio > float(body_min_exclusive)
        and body_ratio <= float(body_max_inclusive)
    )
    fields.update(
        {
            "feature_available": int(np.isfinite(stop_atr14) and np.isfinite(body_ratio)),
            "atr14": atr14,
            "stop_atr14": stop_atr14,
            "body_ratio": body_ratio,
            "quality_hit": int(quality),
        }
    )
    return fields


def choose_budget_weight(
    snapshot: dict[str, Any],
    *,
    enabled: bool,
    entry_context: str,
    recovery_exempt: bool,
    quality_weight: float = QUALITY_WEIGHT,
    other_weight: float = OTHER_WEIGHT,
) -> tuple[float, str]:
    if not enabled:
        return 1.0, "disabled"
    if entry_context != "flat_entry":
        return 1.0, "non_flat_entry"
    if recovery_exempt:
        return 1.0, "recovery_sleeve_exempt"
    if not int(snapshot.get("feature_available") or 0):
        return 1.0, "feature_unavailable_fail_unchanged"
    if int(snapshot.get("quality_hit") or 0):
        return float(quality_weight), "quality_risk_increase"
    return float(other_weight), "other_risk_decrease"


def _stage003_audit_payload(sizing_snapshot: dict[str, Any]) -> dict[str, Any]:
    return {key: sizing_snapshot.get(key) for key in STAGE003_AUDIT_FIELDS}


def install_repaired_minute_sessions(metadata: dict[str, Any]) -> dict[str, Any]:
    global _REPAIRED_MINUTE_GROUPS, _REPAIRED_SESSION_KEYS, _REPAIRED_FIRST_OPEN

    if not REPAIRED_MINUTE_PATCH_PATH.exists() or not REPAIRED_MINUTE_AUDIT_PATH.exists():
        raise RuntimeError("repaired entry-session minute evidence is missing")
    if _REPAIRED_MINUTE_GROUPS is None:
        minute = pd.read_csv(REPAIRED_MINUTE_PATCH_PATH, encoding="utf-8-sig")
        minute["bar_datetime"] = pd.to_datetime(minute["bar_datetime"], errors="coerce").dt.tz_localize(None)
        minute["bar_date"] = pd.to_datetime(minute["bar_date"], errors="coerce").dt.tz_localize(None).dt.normalize()
        for column in ("open", "high", "low", "close", "volume"):
            minute[column] = pd.to_numeric(minute[column], errors="coerce")
        minute = minute.dropna(
            subset=["vt_symbol", "bar_datetime", "bar_date", "open", "high", "low", "close"]
        )
        duplicates = int(minute.duplicated(["vt_symbol", "bar_date", "bar_datetime"]).sum())
        if minute.empty or duplicates:
            raise RuntimeError(f"invalid repaired minute patch: rows={len(minute)} duplicates={duplicates}")
        audit = pd.read_csv(REPAIRED_MINUTE_AUDIT_PATH)
        audit["trade_date"] = pd.to_datetime(audit["trade_date"], errors="coerce").dt.normalize()
        if audit.empty or audit["trade_date"].isna().any() or not audit["daily_ohlc_exact"].eq(1).all():
            raise RuntimeError("repaired minute audit is incomplete")
        decision = json.loads(Path(s000.DECISION_PATH).read_text(encoding="utf-8"))
        if decision.get("patch_sha256") != _sha256(REPAIRED_MINUTE_PATCH_PATH):
            raise RuntimeError("repaired minute patch hash does not match Stage000 decision")
        if decision.get("audit_sha256") != _sha256(REPAIRED_MINUTE_AUDIT_PATH):
            raise RuntimeError("repaired minute audit hash does not match Stage000 decision")
        grouped = minute.groupby(["vt_symbol", "bar_date"], sort=False)
        counts = grouped.size()
        if not set(counts.astype(int).unique()).issubset(s000.ALLOWED_SESSION_BAR_COUNTS):
            raise RuntimeError("repaired minute patch contains a non-standard session length")
        if not grouped["minute_source"].nunique().eq(1).all():
            raise RuntimeError("repaired minute patch mixes sources within a session")
        if not grouped["volume"].sum().gt(0.0).all():
            raise RuntimeError("repaired minute patch contains a zero-volume session")
        geometry_ok = (
            minute["high"].ge(minute[["open", "close"]].max(axis=1))
            & minute["low"].le(minute[["open", "close"]].min(axis=1))
            & minute["high"].ge(minute["low"])
        )
        if not geometry_ok.all():
            raise RuntimeError("repaired minute patch contains invalid OHLC geometry")
        patch_keys = set(zip(minute["vt_symbol"].astype(str), minute["bar_date"]))
        audit_keys = set(zip(audit["vt_symbol"].astype(str), audit["trade_date"]))
        if patch_keys != audit_keys or len(patch_keys) != int(decision.get("covered_symbol_dates", -1)):
            raise RuntimeError("repaired minute patch/audit key set mismatch")
        audit_counts = audit.set_index(["vt_symbol", "trade_date"])["session_bars"].astype(int)
        if any(int(counts.loc[key]) != int(audit_counts.loc[key]) for key in patch_keys):
            raise RuntimeError("repaired minute patch/audit session count mismatch")
        _REPAIRED_MINUTE_GROUPS = s847.s825._minute_groups(minute)
        _REPAIRED_SESSION_KEYS = patch_keys
        _REPAIRED_FIRST_OPEN = {}
        for key, session in grouped:
            first = session.sort_values("bar_datetime").iloc[0]
            _REPAIRED_FIRST_OPEN[(str(key[0]), pd.Timestamp(key[1]).normalize())] = {
                "price": float(first["open"]),
                "bar_datetime": pd.Timestamp(first["bar_datetime"]),
                "minute_source": str(first["minute_source"]),
            }
    s847.s827._GLOBAL_MINUTE_BY_SYMBOL = _REPAIRED_MINUTE_GROUPS
    requested = set(str(item) for item in metadata.get("vt_symbols", []))
    loaded = set((_REPAIRED_MINUTE_GROUPS or {}).keys())
    return {
        "source": str(REPAIRED_MINUTE_PATCH_PATH),
        "source_exists": True,
        "requested_symbol_count": int(len(requested)),
        "loaded_symbol_count": int(len(loaded)),
        "missing_symbol_count": int(len(requested - loaded)),
        "repaired_session_count": int(len(_REPAIRED_SESSION_KEYS)),
    }


def validate_repaired_entry_session(
    *,
    vt_symbol: str,
    trade_date: pd.Timestamp,
    entry_price: float,
    price_tick: float,
    bars: pd.DataFrame,
) -> pd.DataFrame:
    normalized_date = pd.Timestamp(trade_date).tz_localize(None).normalize()
    key = (str(vt_symbol), normalized_date)
    if key not in _REPAIRED_SESSION_KEYS:
        raise RuntimeError(f"missing repaired entry-session minute coverage: {vt_symbol} {normalized_date.date()}")
    session = bars[bars["bar_date"].eq(normalized_date)].copy().sort_values("bar_datetime")
    if session.empty:
        raise RuntimeError(f"empty repaired entry session: {vt_symbol} {normalized_date.date()}")
    tolerance = max(abs(float(price_tick)) * 0.51, 1e-9)
    session_low = float(pd.to_numeric(session["low"], errors="coerce").min())
    session_high = float(pd.to_numeric(session["high"], errors="coerce").max())
    if (
        not np.isfinite(session_low)
        or not np.isfinite(session_high)
        or float(entry_price) < session_low - tolerance
        or float(entry_price) > session_high + tolerance
    ):
        raise RuntimeError(
            f"entry price outside repaired session range: {vt_symbol} {normalized_date.date()} "
            f"trade={entry_price} low={session_low} high={session_high} tick={price_tick}"
        )
    return session


class Stage000StrictOpenStopRetryEngine(s847.Stage847StopRetryEngine):
    def _resolve_trade_price(self, order: Any, bar: Any) -> tuple[float, str, dict[str, Any]]:
        offset = str(getattr(getattr(order, "offset", ""), "value", getattr(order, "offset", "")))
        if offset.lower() != "open":
            return super()._resolve_trade_price(order, bar)
        fill_date = pd.Timestamp(self.datetime).tz_localize(None).normalize()
        key = (str(order.vt_symbol), fill_date)
        strict = _REPAIRED_FIRST_OPEN.get(key)
        if strict is None:
            _STRICT_OPEN_RUNTIME_FAILURES.append(
                {
                    "vt_symbol": str(order.vt_symbol),
                    "trade_date": fill_date.date().isoformat(),
                    "error": "missing strict first-open price",
                }
            )
            return super()._resolve_trade_price(order, bar)
        proxy = {
            "proxy_price": float(strict["price"]),
            "price_source": "stage000_strict_entry_session_first_open",
            "proxy_bar_count": 1,
            "proxy_first_time": strict["bar_datetime"],
            "proxy_last_time": strict["bar_datetime"],
            "minute_source": strict["minute_source"],
        }
        return float(strict["price"]), str(proxy["price_source"]), proxy


def _run_profile_with_repaired_engine(
    profile: dict[str, Any],
    metadata: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    original_engine = s847.Stage847StopRetryEngine
    s847.Stage847StopRetryEngine = Stage000StrictOpenStopRetryEngine
    try:
        return s847._run_profile(profile, metadata)
    finally:
        s847.Stage847StopRetryEngine = original_engine


def _annotate_and_validate_strict_open_trades(trades: pd.DataFrame) -> dict[str, int]:
    if trades.empty:
        raise RuntimeError("strict first-open audit has no trades")
    root = trades[
        trades["offset"].astype(str).str.lower().eq("open")
        & ~trades["order_id"].astype(str).str.contains(".stage847_c9.", regex=False)
    ].copy()
    root["trade_date"] = pd.to_datetime(root["date"], errors="coerce").dt.normalize()
    root["strict_open_expected"] = [
        _REPAIRED_FIRST_OPEN.get((str(symbol), pd.Timestamp(date)), {}).get("price", np.nan)
        for symbol, date in zip(root["vt_symbol"], root["trade_date"])
    ]
    root["strict_open_match"] = np.isclose(
        pd.to_numeric(root["price"], errors="coerce"),
        pd.to_numeric(root["strict_open_expected"], errors="coerce"),
        rtol=0.0,
        atol=1e-12,
    )
    if root.empty or root["strict_open_expected"].isna().any() or not root["strict_open_match"].all():
        bad = root[root["strict_open_expected"].isna() | ~root["strict_open_match"]]
        raise RuntimeError(
            "root open trade does not use strict session first open: "
            + repr(bad[["vt_symbol", "date", "price", "strict_open_expected"]].head(20).to_dict("records"))
        )
    key_to_expected = {
        (str(row.vt_symbol), pd.Timestamp(row.trade_date)): float(row.strict_open_expected)
        for row in root.itertuples(index=False)
    }
    trades["strict_open_expected"] = [
        key_to_expected.get((str(symbol), pd.Timestamp(date).normalize()), np.nan)
        if str(offset).lower() == "open" and ".stage847_c9." not in str(order_id)
        else np.nan
        for symbol, date, offset, order_id in zip(
            trades["vt_symbol"], trades["date"], trades["offset"], trades["order_id"]
        )
    ]
    trades["strict_open_match"] = np.where(
        trades["strict_open_expected"].notna(),
        np.isclose(trades["price"], trades["strict_open_expected"], rtol=0.0, atol=1e-12).astype(int),
        np.nan,
    )
    return {"root_open_count": int(len(root)), "strict_open_match_count": int(root["strict_open_match"].sum())}


class QmtRollPortfolioStrategyStage000RepairedStopRetry(s847.QmtRollPortfolioStrategyStage847C9StopRetry):
    def __init__(self, strategy_engine: Any, strategy_name: str, vt_symbols: list[str], setting: dict[str, Any]) -> None:
        self.stage000_account_equity = 0.0
        self.stage000_account_high_water = 0.0
        self.stage000_account_drawdown_pct = 0.0
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage000_account_equity = float(self.base_capital)
        self.stage000_account_high_water = float(self.base_capital)

    def _engine_account_equity(self) -> float:
        engine = self.strategy_engine
        bars = getattr(engine, "bars", {}) or {}
        base_capital = float(getattr(self, "base_capital", 1_000_000.0) or 1_000_000.0)
        equity = float(getattr(engine, "capital", base_capital) or base_capital)
        for trade in (getattr(engine, "trades", {}) or {}).values():
            current_bar = bars.get(str(trade.vt_symbol))
            if current_bar is None:
                raise RuntimeError(f"missing mark bar for strict account equity: {trade.vt_symbol}")
            size_value = getattr(engine, "sizes", {}).get(trade.vt_symbol)
            size = float(size_value if size_value is not None else self.get_size(trade.vt_symbol))
            rate = float(getattr(engine, "rates", {}).get(trade.vt_symbol, 0.0))
            slippage = float(getattr(engine, "slippages", {}).get(trade.vt_symbol, 0.0))
            sign = 1.0 if str(getattr(trade.direction, "value", trade.direction)).lower() == "long" else -1.0
            volume = float(trade.volume)
            equity += sign * volume * (float(current_bar.close_price) - float(trade.price)) * size
            equity -= volume * size * float(trade.price) * rate + volume * size * slippage
        return float(equity)

    def _refresh_risk_state(self, bars: dict[str, Any]) -> None:
        super()._refresh_risk_state(bars)
        try:
            equity = self._engine_account_equity()
        except RuntimeError as exc:
            _REPAIRED_RUNTIME_FAILURES.append(
                {
                    "vt_symbol": "<account>",
                    "trade_date": str(getattr(self, "current_bar_date", "")),
                    "entry_price": np.nan,
                    "error": str(exc),
                }
            )
            equity = float(self.base_capital)
        self.stage000_account_equity = equity
        self.stage000_account_high_water = max(
            float(self.stage000_account_high_water or self.base_capital),
            equity,
            float(self.base_capital),
        )
        self.stage000_account_drawdown_pct = max(
            0.0,
            (self.stage000_account_high_water - equity) / self.stage000_account_high_water,
        )

    def _calculate_entry_sizing(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        result = super()._calculate_entry_sizing(*args, **kwargs)
        result.update(
            {
                "stage000_account_equity": float(self.stage000_account_equity),
                "stage000_account_high_water": float(self.stage000_account_high_water),
                "stage000_account_drawdown_pct": float(self.stage000_account_drawdown_pct),
                "stage000_account_equity_source": "engine_trades_marked_to_signal_close",
            }
        )
        return result

    def _record_entry_candidate_snapshot(self, *args: Any, **kwargs: Any) -> None:
        sizing_snapshot = kwargs.get("sizing_snapshot")
        super()._record_entry_candidate_snapshot(*args, **kwargs)
        if isinstance(sizing_snapshot, dict) and self.entry_candidate_snapshots:
            self.entry_candidate_snapshots[-1].update(
                {key: sizing_snapshot.get(key) for key in STAGE000_ACCOUNT_AUDIT_FIELDS}
            )

    def _record_entry_risk_diagnostic(self, *args: Any, **kwargs: Any) -> None:
        sizing_snapshot = kwargs.get("sizing_snapshot")
        super()._record_entry_risk_diagnostic(*args, **kwargs)
        if isinstance(sizing_snapshot, dict) and self.entry_risk_diagnostics:
            self.entry_risk_diagnostics[-1].update(
                {key: sizing_snapshot.get(key) for key in STAGE000_ACCOUNT_AUDIT_FIELDS}
            )

    def _stage847_stop_retry_event_after_open_trade(self, trade: Any) -> dict[str, Any] | None:
        trade_date = s847.s827._normalize_date(trade.datetime)
        bars = self.stage827_minute_by_symbol.get(str(trade.vt_symbol), pd.DataFrame())
        try:
            session = validate_repaired_entry_session(
                vt_symbol=str(trade.vt_symbol),
                trade_date=trade_date,
                entry_price=float(trade.price),
                price_tick=float(self.get_pricetick(trade.vt_symbol)),
                bars=bars,
            )
        except RuntimeError as exc:
            _REPAIRED_RUNTIME_FAILURES.append(
                {
                    "vt_symbol": str(trade.vt_symbol),
                    "trade_date": pd.Timestamp(trade_date).tz_localize(None).date().isoformat(),
                    "entry_price": float(trade.price),
                    "error": str(exc),
                }
            )
            return None
        normalized_date = pd.Timestamp(trade_date).tz_localize(None).normalize()
        engine_bars = bars.copy()
        mask = engine_bars["bar_date"].eq(normalized_date)
        engine_bars.loc[mask, "bar_datetime"] = normalized_date + pd.to_timedelta(
            np.arange(len(session)), unit="min"
        )
        self.stage827_minute_by_symbol[str(trade.vt_symbol)] = engine_bars
        try:
            return super()._stage847_stop_retry_event_after_open_trade(trade)
        finally:
            self.stage827_minute_by_symbol[str(trade.vt_symbol)] = bars


class QmtRollPortfolioStrategyStage003RiskTransfer(QmtRollPortfolioStrategyStage000RepairedStopRetry):
    enable_stage003_risk_transfer: bool = False
    stage003_stop_atr_max: float = STOP_ATR_MAX
    stage003_body_min_exclusive: float = BODY_MIN_EXCLUSIVE
    stage003_body_max_inclusive: float = BODY_MAX_INCLUSIVE
    stage003_quality_weight: float = QUALITY_WEIGHT
    stage003_other_weight: float = OTHER_WEIGHT

    parameters = s847.QmtRollPortfolioStrategyStage847C9StopRetry.parameters + [
        "enable_stage003_risk_transfer",
        "stage003_stop_atr_max",
        "stage003_body_min_exclusive",
        "stage003_body_max_inclusive",
        "stage003_quality_weight",
        "stage003_other_weight",
    ]

    def __init__(self, strategy_engine: Any, strategy_name: str, vt_symbols: list[str], setting: dict[str, Any]) -> None:
        self._stage003_active_budget_weight = 1.0
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)

    def _risk_amount_from_ratio(
        self,
        risk_ratio: float,
        limited_balance: float,
        risk_multiplier_override: float | None = None,
    ) -> float:
        base = super()._risk_amount_from_ratio(
            risk_ratio,
            limited_balance,
            risk_multiplier_override=risk_multiplier_override,
        )
        return max(0.0, base * float(self._stage003_active_budget_weight))

    def _calculate_entry_sizing(
        self,
        vt_symbol: str,
        direction: str,
        bar: Any,
        history: pd.DataFrame,
        signal_data: dict[str, Any],
        risk_mode_override: str | None = None,
        entry_context: str = "flat_entry",
        apply_env_gate: bool = True,
        active_positions_before: int | None = None,
        correlation_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        stop_price = preview_entry_stop_price(direction, bar, float(self.stop_loss_pct))
        feature_date = pd.Timestamp(bar.datetime).tz_localize(None).normalize()
        snapshot = t1_quality_snapshot(
            history,
            abs(float(bar.close_price) - float(stop_price)),
            feature_date=feature_date,
            stop_atr_max=float(self.stage003_stop_atr_max),
            body_min_exclusive=float(self.stage003_body_min_exclusive),
            body_max_inclusive=float(self.stage003_body_max_inclusive),
        )
        recovery_exempt = bool(
            self.enable_recovery_sleeve
            and self._current_streak_multiplier() <= float(self.recovery_sleeve_base_multiplier_max) + 1e-12
        )
        weight, reason = choose_budget_weight(
            snapshot,
            enabled=bool(self.enable_stage003_risk_transfer),
            entry_context=entry_context,
            recovery_exempt=recovery_exempt,
            quality_weight=float(self.stage003_quality_weight),
            other_weight=float(self.stage003_other_weight),
        )
        previous_weight = self._stage003_active_budget_weight
        self._stage003_active_budget_weight = weight
        try:
            result = super()._calculate_entry_sizing(
                vt_symbol,
                direction,
                bar,
                history,
                signal_data,
                risk_mode_override=risk_mode_override,
                entry_context=entry_context,
                apply_env_gate=apply_env_gate,
                active_positions_before=active_positions_before,
                correlation_snapshot=correlation_snapshot,
            )
        finally:
            self._stage003_active_budget_weight = previous_weight

        risk_after = _safe_float(result.get("risk_amount"))
        risk_before = risk_after / weight if np.isfinite(risk_after) and weight > 0 else np.nan
        risk_per_contract = _safe_float(result.get("risk_per_contract"))
        contracts_before = (
            int(risk_before // risk_per_contract)
            if np.isfinite(risk_before) and risk_per_contract > 0
            else None
        )
        result.update(
            {
                "stage003_enabled": int(bool(self.enable_stage003_risk_transfer)),
                "stage003_feature_source": "engine_history_t_minus_1",
                "stage003_feature_date": snapshot["feature_date"],
                "stage003_feature_available": int(snapshot["feature_available"]),
                "stage003_feature_bar_count": int(snapshot["feature_bar_count"]),
                "stage003_atr14": snapshot["atr14"],
                "stage003_stop_atr14": snapshot["stop_atr14"],
                "stage003_body_ratio": snapshot["body_ratio"],
                "stage003_quality_hit": int(snapshot["quality_hit"]),
                "stage003_recovery_exempt": int(recovery_exempt),
                "stage003_budget_weight": float(weight),
                "stage003_reason": reason,
                "stage003_stop_atr_max": float(self.stage003_stop_atr_max),
                "stage003_body_min_exclusive": float(self.stage003_body_min_exclusive),
                "stage003_body_max_inclusive": float(self.stage003_body_max_inclusive),
                "stage003_quality_weight": float(self.stage003_quality_weight),
                "stage003_other_weight": float(self.stage003_other_weight),
                "stage003_risk_amount_before": risk_before,
                "stage003_risk_amount_after": risk_after,
                "stage003_contracts_by_risk_before": contracts_before,
                "stage003_contracts_by_risk_after": result.get("contracts_by_risk"),
                "stage003_selected_volume_after": result.get("selected_volume"),
            }
        )
        return result

    def _record_entry_candidate_snapshot(self, *args: Any, **kwargs: Any) -> None:
        sizing_snapshot = kwargs.get("sizing_snapshot")
        super()._record_entry_candidate_snapshot(*args, **kwargs)
        if isinstance(sizing_snapshot, dict) and self.entry_candidate_snapshots:
            self.entry_candidate_snapshots[-1].update(_stage003_audit_payload(sizing_snapshot))

    def _record_entry_risk_diagnostic(self, *args: Any, **kwargs: Any) -> None:
        sizing_snapshot = kwargs.get("sizing_snapshot")
        super()._record_entry_risk_diagnostic(*args, **kwargs)
        if isinstance(sizing_snapshot, dict) and self.entry_risk_diagnostics:
            self.entry_risk_diagnostics[-1].update(_stage003_audit_payload(sizing_snapshot))


def _official_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s847._c9_profile(metadata)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=OFFICIAL_LIVE_PROFILE_NAME,
        label=f"{OFFICIAL_LIVE_CAPITAL_LABEL} {OFFICIAL_LIVE_ALIAS} live default",
        account_capital=OFFICIAL_LIVE_CAPITAL,
        c3_capital=OFFICIAL_LIVE_CAPITAL,
    )
    result = dict(profile)
    result["profile"] = OFFICIAL_LIVE_PROFILE_NAME
    result["strategy_cls"] = QmtRollPortfolioStrategyStage000RepairedStopRetry
    result["spec"] = replace(
        spec,
        capital=capital,
        overrides={**spec.overrides, **build_official_live_strategy_overrides()},
        profile=OFFICIAL_LIVE_PROFILE_NAME,
    )
    return result


def _candidate_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    base = _official_profile(metadata)
    spec = base["spec"]
    overrides = {
        **spec.overrides,
        "enable_stage003_risk_transfer": True,
        "stage003_stop_atr_max": STOP_ATR_MAX,
        "stage003_body_min_exclusive": BODY_MIN_EXCLUSIVE,
        "stage003_body_max_inclusive": BODY_MAX_INCLUSIVE,
        "stage003_quality_weight": QUALITY_WEIGHT,
        "stage003_other_weight": OTHER_WEIGHT,
    }
    result = dict(base)
    result["profile"] = PROFILE_NAME
    result["strategy_cls"] = QmtRollPortfolioStrategyStage003RiskTransfer
    result["spec"] = replace(spec, overrides=overrides, profile=PROFILE_NAME)
    return result


def config_audit(metadata: dict[str, Any]) -> pd.DataFrame:
    base = _official_profile(metadata)
    candidate = _candidate_profile(metadata)
    base_overrides = dict(base["spec"].overrides)
    candidate_overrides = dict(candidate["spec"].overrides)
    allowed = {
        "enable_stage003_risk_transfer",
        "stage003_stop_atr_max",
        "stage003_body_min_exclusive",
        "stage003_body_max_inclusive",
        "stage003_quality_weight",
        "stage003_other_weight",
    }
    rows = []
    for key in sorted(set(base_overrides) | set(candidate_overrides)):
        a = base_overrides.get(key, "<missing>")
        c = candidate_overrides.get(key, "<missing>")
        changed = a != c
        rows.append({"key": key, "A": a, "C": c, "changed": int(changed), "allowed": int(key in allowed)})
        if changed and key not in allowed:
            raise RuntimeError(f"unexpected A/C override difference: {key}")
    return pd.DataFrame(rows)


def _begin_repaired_minute_run() -> None:
    _REPAIRED_RUNTIME_FAILURES.clear()
    _STRICT_OPEN_RUNTIME_FAILURES.clear()


def _assert_repaired_minute_run_complete() -> None:
    if not _REPAIRED_RUNTIME_FAILURES and not _STRICT_OPEN_RUNTIME_FAILURES:
        return
    current = pd.DataFrame([*_REPAIRED_RUNTIME_FAILURES, *_STRICT_OPEN_RUNTIME_FAILURES])
    if s000.RUNTIME_GAPS_PATH.exists():
        previous = pd.read_csv(s000.RUNTIME_GAPS_PATH)
        current = pd.concat([previous, current], ignore_index=True, sort=False)
    current = current.drop_duplicates(["vt_symbol", "trade_date"], keep="last").sort_values(
        ["trade_date", "vt_symbol"]
    )
    current.to_csv(s000.RUNTIME_GAPS_PATH, index=False)
    raise RuntimeError(
        "repaired minute coverage failed; backtest rejected and gaps persisted: "
        + str(current[["vt_symbol", "trade_date", "error"]].tail(20).to_dict("records"))
    )


def _run_candidate(metadata: dict[str, Any], start: pd.Timestamp) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    original_start = s847.START
    original_end = s847.END
    original_minute = s847.s827._GLOBAL_MINUTE_BY_SYMBOL
    install_repaired_minute_sessions(metadata)
    try:
        _begin_repaired_minute_run()
        s847.START = start.normalize()
        s847.END = END.normalize()
        profile = _candidate_profile(metadata)
        combined, frames = _run_profile_with_repaired_engine(profile, metadata)
        _assert_repaired_minute_run_complete()
        strict_open_audit = _annotate_and_validate_strict_open_trades(frames.get("trades", pd.DataFrame()))
        spec = profile["spec"]
    finally:
        s847.START = original_start
        s847.END = original_end
        s847.s827._GLOBAL_MINUTE_BY_SYMBOL = original_minute
    combined["account_capital"] = spec.capital.account_capital
    combined["profile"] = spec.profile
    combined["strict_root_open_count"] = strict_open_audit["root_open_count"]
    combined["strict_open_match_count"] = strict_open_audit["strict_open_match_count"]
    for frame in frames.values():
        if not frame.empty:
            frame["account_capital"] = spec.capital.account_capital
            frame["profile"] = spec.profile
    return combined, frames


def _run_official_repaired(
    metadata: dict[str, Any],
    start: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    original_start = s847.START
    original_end = s847.END
    original_minute = s847.s827._GLOBAL_MINUTE_BY_SYMBOL
    minute_audit = install_repaired_minute_sessions(metadata)
    try:
        _begin_repaired_minute_run()
        s847.START = start.normalize()
        s847.END = END.normalize()
        profile = _official_profile(metadata)
        combined, frames = _run_profile_with_repaired_engine(profile, metadata)
        _assert_repaired_minute_run_complete()
        strict_open_audit = _annotate_and_validate_strict_open_trades(frames.get("trades", pd.DataFrame()))
        spec = profile["spec"]
    finally:
        s847.START = original_start
        s847.END = original_end
        s847.s827._GLOBAL_MINUTE_BY_SYMBOL = original_minute
    combined["account_capital"] = spec.capital.account_capital
    combined["profile"] = spec.profile
    combined["minute_source"] = minute_audit["source"]
    combined["minute_loaded_symbol_count"] = minute_audit["loaded_symbol_count"]
    combined["minute_repaired_session_count"] = minute_audit["repaired_session_count"]
    combined["strict_root_open_count"] = strict_open_audit["root_open_count"]
    combined["strict_open_match_count"] = strict_open_audit["strict_open_match_count"]
    for frame in frames.values():
        if not frame.empty:
            frame["account_capital"] = spec.capital.account_capital
            frame["profile"] = spec.profile
            frame["minute_source"] = minute_audit["source"]
    return combined, frames


def summarize_curve(curve: pd.DataFrame, start: pd.Timestamp, variant: str) -> dict[str, Any]:
    frame = curve.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    equity = pd.to_numeric(frame["account_equity"], errors="coerce").ffill()
    drawdown = equity / equity.cummax().replace(0.0, np.nan) - 1.0
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    sharpe = float(returns.mean() / returns.std(ddof=1) * np.sqrt(252.0)) if len(returns) and returns.std(ddof=1) > 0 else 0.0
    underwater = drawdown.lt(0.0)
    longest = current = 0
    for value in underwater:
        current = current + 1 if bool(value) else 0
        longest = max(longest, current)
    return {
        "variant": variant,
        "requested_start": start.date().isoformat(),
        "requested_start_month": start.strftime("%Y-%m"),
        "requested_end": END.date().isoformat(),
        "actual_start": frame["date"].iloc[0].date().isoformat(),
        "actual_end": frame["date"].iloc[-1].date().isoformat(),
        "trading_days": int(len(frame)),
        "capital": EXPECTED_CAPITAL,
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / EXPECTED_CAPITAL - 1.0) * 100.0),
        "max_dd_pct": float(drawdown.min() * 100.0),
        "sharpe": sharpe,
        "total_slippage": float(pd.to_numeric(frame.get("slippage", 0.0), errors="coerce").fillna(0.0).sum()),
        "total_trade_count": float(pd.to_numeric(frame.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
        "longest_underwater_trading_days": int(longest),
    }


def _tag_curve(curve: pd.DataFrame, start: pd.Timestamp, variant: str) -> pd.DataFrame:
    frame = curve.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    frame["variant"] = variant
    frame["requested_start_month"] = start.strftime("%Y-%m")
    equity = pd.to_numeric(frame["account_equity"], errors="coerce").ffill()
    frame["nav"] = equity / EXPECTED_CAPITAL
    frame["drawdown_pct"] = (equity / equity.cummax().replace(0.0, np.nan) - 1.0) * 100.0
    return frame


def _tag_evidence(frame: pd.DataFrame, start: pd.Timestamp, variant: str) -> pd.DataFrame:
    result = frame.copy()
    result["requested_start_month"] = start.strftime("%Y-%m")
    result["variant"] = variant
    return result


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    a = summary[summary["variant"].eq("A_official")].set_index("requested_start_month")
    c = summary[summary["variant"].eq("C_stage003")].set_index("requested_start_month")
    rows = []
    for start in sorted(set(a.index) & set(c.index)):
        ar = a.loc[start]
        cr = c.loc[start]
        retention = float(cr["total_return_pct"] / ar["total_return_pct"]) if ar["total_return_pct"] > 0 else np.nan
        dd_improvement = float(cr["max_dd_pct"] - ar["max_dd_pct"])
        rows.append(
            {
                "requested_start_month": start,
                "A_return_pct": ar["total_return_pct"],
                "C_return_pct": cr["total_return_pct"],
                "return_retention_ratio": retention,
                "A_max_dd_pct": ar["max_dd_pct"],
                "C_max_dd_pct": cr["max_dd_pct"],
                "dd_improvement_pp": dd_improvement,
                "A_sharpe": ar["sharpe"],
                "C_sharpe": cr["sharpe"],
                "A_slippage": ar["total_slippage"],
                "C_slippage": cr["total_slippage"],
                "A_trade_count": ar["total_trade_count"],
                "C_trade_count": cr["total_trade_count"],
                "positive_return_pass": int(cr["total_return_pct"] > 0),
                "retention_70_pass": int(np.isfinite(retention) and retention >= 0.70),
                "dd_improve_3pp_pass": int(dd_improvement >= 3.0),
                "dd_not_worse_1pp_pass": int(dd_improvement >= -1.0),
            }
        )
    return pd.DataFrame(rows)


def _plot(curves: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(18, 14), sharex=True, constrained_layout=True)
    colors = {start: color for start, color in zip(sorted(curves["requested_start_month"].unique()), plt.cm.tab10.colors)}
    for (start, variant), group in curves.groupby(["requested_start_month", "variant"]):
        group = group.sort_values("date")
        style = "-" if variant == "A_official" else "--"
        label = f"{start} {variant}"
        axes[0].plot(group["date"], group["account_equity"], color=colors[start], linestyle=style, linewidth=1.15, label=label)
        axes[1].plot(group["date"], group["nav"], color=colors[start], linestyle=style, linewidth=1.05, label=label)
        axes[2].plot(group["date"], group["drawdown_pct"], color=colors[start], linestyle=style, linewidth=1.0, label=label)
    axes[0].axhline(EXPECTED_CAPITAL, color="#111827", linewidth=0.8, linestyle=":")
    axes[0].set_title("Stage003 A/C absolute equity (solid=A, dashed=C)")
    axes[0].set_ylabel("equity")
    axes[1].set_title("Normalized NAV by start")
    axes[1].set_ylabel("NAV")
    axes[2].set_title("Drawdown")
    axes[2].set_ylabel("drawdown %")
    axes[2].set_xlabel("date")
    for axis in axes:
        axis.grid(alpha=0.2)
    axes[0].legend(ncol=4, fontsize=8)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _feature_audit(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame()
    return (
        candidates.groupby(["requested_start_month", "stage003_reason"], dropna=False)
        .agg(
            candidate_count=("candidate_index", "size"),
            opened_count=("is_opened", lambda values: int(pd.to_numeric(values, errors="coerce").fillna(0).sum())),
            feature_available_count=("stage003_feature_available", "sum"),
            quality_hit_count=("stage003_quality_hit", "sum"),
            average_budget_weight=("stage003_budget_weight", "mean"),
        )
        .reset_index()
        .sort_values(["requested_start_month", "stage003_reason"])
    )


def validate_feature_evidence(candidates: pd.DataFrame) -> dict[str, Any]:
    missing = sorted(set(STAGE003_AUDIT_FIELDS) - set(candidates.columns))
    if candidates.empty or missing:
        raise RuntimeError(f"Stage003 feature evidence missing: rows={len(candidates)}, columns={missing}")
    if not candidates["stage003_enabled"].eq(1).all():
        raise RuntimeError("Stage003 candidate evidence contains disabled rows")
    if not candidates["stage003_feature_source"].astype(str).eq("engine_history_t_minus_1").all():
        raise RuntimeError("Stage003 feature source drift")

    candidate_date = pd.to_datetime(candidates["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    feature_date = pd.to_datetime(candidates["stage003_feature_date"], errors="coerce", utc=True)
    feature_date = feature_date.dt.tz_convert(None).dt.normalize()
    if candidate_date.isna().any() or feature_date.isna().any() or not candidate_date.eq(feature_date).all():
        raise RuntimeError("Stage003 feature date is not the engine signal date/T-1")

    available = pd.to_numeric(candidates["stage003_feature_available"], errors="coerce").fillna(0).astype(int)
    coverage = float(available.mean())
    if coverage < 0.99:
        raise RuntimeError(f"Stage003 feature coverage below 99%: {coverage}")

    weights = pd.to_numeric(candidates["stage003_budget_weight"], errors="coerce")
    reasons = candidates["stage003_reason"].astype(str)
    expected = reasons.map(
        {
            "quality_risk_increase": QUALITY_WEIGHT,
            "other_risk_decrease": OTHER_WEIGHT,
            "recovery_sleeve_exempt": 1.0,
            "feature_unavailable_fail_unchanged": 1.0,
        }
    )
    if expected.isna().any() or not np.allclose(weights, expected, rtol=0.0, atol=1e-12):
        raise RuntimeError("Stage003 reason/weight evidence mismatch")
    quality_count = int(reasons.eq("quality_risk_increase").sum())
    other_count = int(reasons.eq("other_risk_decrease").sum())
    if quality_count <= 0 or other_count <= 0:
        raise RuntimeError("Stage003 did not exercise both risk-transfer branches")

    before = pd.to_numeric(candidates["stage003_risk_amount_before"], errors="coerce")
    after = pd.to_numeric(candidates["stage003_risk_amount_after"], errors="coerce")
    comparable = before.notna() & after.notna()
    if not comparable.any() or not np.allclose(
        after[comparable],
        before[comparable] * weights[comparable],
        rtol=0.0,
        atol=1e-8,
    ):
        raise RuntimeError("Stage003 risk amount before/after does not reconcile to weight")

    return {
        "candidate_count": int(len(candidates)),
        "feature_coverage_ratio": coverage,
        "quality_count": quality_count,
        "other_count": other_count,
        "recovery_exempt_count": int(reasons.eq("recovery_sleeve_exempt").sum()),
        "missing_feature_count": int((available == 0).sum()),
        "feature_date_mismatch_count": int((~candidate_date.eq(feature_date)).sum()),
    }


def validate_account_equity_evidence(candidates: pd.DataFrame, curves: pd.DataFrame) -> dict[str, Any]:
    required = set(STAGE000_ACCOUNT_AUDIT_FIELDS)
    missing = sorted(required - set(candidates.columns))
    if candidates.empty or missing:
        raise RuntimeError(f"strict account-equity evidence missing: rows={len(candidates)}, columns={missing}")
    if not candidates["stage000_account_equity_source"].astype(str).eq(
        "engine_trades_marked_to_signal_close"
    ).all():
        raise RuntimeError("strict account-equity source drift")
    curve = curves[["requested_start_month", "variant", "date", "account_equity"]].copy()
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve = curve.sort_values(["requested_start_month", "variant", "date"])
    curve["expected_high_water"] = curve.groupby(["requested_start_month", "variant"])["account_equity"].cummax()
    curve["expected_drawdown"] = (
        curve["expected_high_water"] - curve["account_equity"]
    ) / curve["expected_high_water"].replace(0.0, np.nan)
    evidence = candidates.copy()
    evidence["date"] = pd.to_datetime(evidence["date"], errors="coerce").dt.normalize()
    merged = evidence.merge(
        curve,
        on=["requested_start_month", "variant", "date"],
        how="left",
        validate="many_to_one",
    )
    if merged["account_equity"].isna().any():
        raise RuntimeError("strict account-equity evidence has no matching daily curve")
    equity_error = (
        pd.to_numeric(merged["stage000_account_equity"], errors="coerce")
        - pd.to_numeric(merged["account_equity"], errors="coerce")
    ).abs()
    high_error = (
        pd.to_numeric(merged["stage000_account_high_water"], errors="coerce")
        - pd.to_numeric(merged["expected_high_water"], errors="coerce")
    ).abs()
    drawdown_error = (
        pd.to_numeric(merged["stage000_account_drawdown_pct"], errors="coerce")
        - pd.to_numeric(merged["expected_drawdown"], errors="coerce")
    ).abs()
    if equity_error.isna().any() or high_error.isna().any() or drawdown_error.isna().any():
        raise RuntimeError("strict account-equity evidence contains NaN")
    if float(equity_error.max()) > 1e-6 or float(high_error.max()) > 1e-6 or float(drawdown_error.max()) > 1e-10:
        raise RuntimeError(
            "strict account-equity evidence does not match engine daily curve: "
            f"equity={equity_error.max()} high={high_error.max()} drawdown={drawdown_error.max()}"
        )
    return {
        "candidate_count": int(len(merged)),
        "max_equity_error": float(equity_error.max()),
        "max_high_water_error": float(high_error.max()),
        "max_drawdown_error": float(drawdown_error.max()),
    }


def stop_retry_audit(trades: pd.DataFrame, stop_events: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (start, variant), trade_group in trades.groupby(["requested_start_month", "variant"]):
        stop_group = stop_events[
            stop_events["requested_start_month"].astype(str).eq(str(start))
            & stop_events["variant"].astype(str).eq(str(variant))
        ].copy()
        retry_opens = trade_group[
            trade_group["offset"].astype(str).str.lower().eq("open")
            & trade_group["order_id"].astype(str).str.contains(".stage847_c9.2", regex=False)
        ].copy()
        expected_trade_count = float(
            summary[
                summary["requested_start_month"].astype(str).eq(str(start))
                & summary["variant"].astype(str).eq(str(variant))
            ]["total_trade_count"].iloc[0]
        )
        invalid_stop = int(
            (~pd.to_numeric(stop_group.get("stop_r", pd.Series(dtype=float)), errors="coerce").eq(0.5)).sum()
        )
        invalid_retries = int(
            (~pd.to_numeric(stop_group.get("max_retries", pd.Series(dtype=float)), errors="coerce").eq(1)).sum()
        )
        reentered = int(pd.to_numeric(stop_group.get("retry_reentered", 0), errors="coerce").fillna(0).sum())
        volume_mismatch = 0
        trade_by_id = trade_group.set_index("trade_id").to_dict("index")
        retry_by_order = retry_opens.set_index("order_id").to_dict("index") if not retry_opens.empty else {}
        for event in stop_group[stop_group.get("retry_reentered", 0).astype(bool)].to_dict("records"):
            root_trade = trade_by_id.get(str(event.get("trade_id")), {})
            retry = retry_by_order.get(f"{root_trade.get('order_id', '')}.stage847_c9.2", {})
            if not retry or abs(_safe_float(retry.get("volume"), -1.0) - _safe_float(event.get("volume"), -2.0)) > 1e-9:
                volume_mismatch += 1
        trade_count_mismatch = int(abs(float(len(trade_group)) - expected_trade_count) > 1e-9)
        retry_count_mismatch = int(len(retry_opens) != reentered)
        rows.append(
            {
                "requested_start_month": start,
                "variant": variant,
                "trade_row_count": int(len(trade_group)),
                "summary_trade_count": expected_trade_count,
                "trade_count_mismatch": trade_count_mismatch,
                "stop_retry_event_count": int(len(stop_group)),
                "retry_reentered_count": reentered,
                "retry_open_trade_count": int(len(retry_opens)),
                "retry_count_mismatch": retry_count_mismatch,
                "retry_volume_mismatch_count": int(volume_mismatch),
                "invalid_stop_r_count": invalid_stop,
                "invalid_max_retries_count": invalid_retries,
            }
        )
    result = pd.DataFrame(rows)
    failure_columns = [
        "trade_count_mismatch",
        "retry_count_mismatch",
        "retry_volume_mismatch_count",
        "invalid_stop_r_count",
        "invalid_max_retries_count",
    ]
    if result.empty or int(result[failure_columns].sum().sum()) != 0:
        raise RuntimeError("A/C trade or stop-retry reconciliation failed")
    return result


def _ai_audit(candidates: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    pool, _ = s167._load_ai_pool()
    audit = s167._ai_month_audit(candidates, summary, pool)
    audit["variant"] = "C_stage003"
    return audit


def main() -> None:
    if OFFICIAL_LIVE_VERSION != EXPECTED_VERSION or abs(float(OFFICIAL_LIVE_CAPITAL) - EXPECTED_CAPITAL) > 1e-9:
        raise RuntimeError("official version/capital drift")
    OUT.mkdir(parents=True, exist_ok=True)
    metadata = s901.s513._metadata()
    minute_audit = install_repaired_minute_sessions(metadata)
    config = config_audit(metadata)
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    risk_frames: list[pd.DataFrame] = []
    event_frames: list[pd.DataFrame] = []
    stop_retry_frames: list[pd.DataFrame] = []

    def append_evidence(frames: dict[str, pd.DataFrame], start: pd.Timestamp, variant: str) -> None:
        for name, target in (
            ("trades", trade_frames),
            ("entry_candidates", candidate_frames),
            ("entry_risk", risk_frames),
            ("trade_events", event_frames),
            ("stop_retry_events", stop_retry_frames),
        ):
            source = frames.get(name, pd.DataFrame())
            if not source.empty:
                target.append(_tag_evidence(source, start, variant))

    for index, start in enumerate(STARTS, start=1):
        print(f"[stage003] {index}/{len(STARTS)} A start={start.date()}", flush=True)
        a_curve, a_frames = _run_official_repaired(metadata, start)
        summary_rows.append(summarize_curve(a_curve, start, "A_official"))
        curve_frames.append(_tag_curve(a_curve, start, "A_official"))
        append_evidence(a_frames, start, "A_official")

        print(f"[stage003] {index}/{len(STARTS)} C start={start.date()}", flush=True)
        c_curve, c_frames = _run_candidate(metadata, start)
        summary_rows.append(summarize_curve(c_curve, start, "C_stage003"))
        curve_frames.append(_tag_curve(c_curve, start, "C_stage003"))
        append_evidence(c_frames, start, "C_stage003")

    summary = pd.DataFrame(summary_rows).sort_values(["requested_start_month", "variant"]).reset_index(drop=True)
    curves = pd.concat(curve_frames, ignore_index=True, sort=False)
    trades = pd.concat(trade_frames, ignore_index=True, sort=False) if trade_frames else pd.DataFrame()
    candidates = pd.concat(candidate_frames, ignore_index=True, sort=False) if candidate_frames else pd.DataFrame()
    risks = pd.concat(risk_frames, ignore_index=True, sort=False) if risk_frames else pd.DataFrame()
    events = pd.concat(event_frames, ignore_index=True, sort=False) if event_frames else pd.DataFrame()
    stop_retry_events = pd.concat(stop_retry_frames, ignore_index=True, sort=False) if stop_retry_frames else pd.DataFrame()
    candidate_evidence = candidates[candidates["variant"].astype(str).eq("C_stage003")].copy()
    comparison = _comparison(summary)
    feature_evidence_summary = validate_feature_evidence(candidate_evidence)
    account_equity_summary = validate_account_equity_evidence(candidates, curves)
    feature_audit = _feature_audit(candidate_evidence)
    ai_audit = _ai_audit(candidate_evidence, summary[summary["variant"].eq("C_stage003")].copy())
    retry_audit = stop_retry_audit(trades, stop_retry_events, summary)

    three_dd = int(comparison["dd_improve_3pp_pass"].sum()) >= 3
    start_2022 = comparison[comparison["requested_start_month"].eq("2022-01")]
    gate = bool(
        len(comparison) == len(STARTS)
        and comparison["positive_return_pass"].eq(1).all()
        and comparison["retention_70_pass"].eq(1).all()
        and comparison["dd_not_worse_1pp_pass"].eq(1).all()
        and three_dd
        and not start_2022.empty
        and int(start_2022["dd_improve_3pp_pass"].iloc[0]) == 1
    )
    ai_fail = int(ai_audit["status"].eq("FAIL").sum()) if not ai_audit.empty else 1
    if ai_fail:
        raise RuntimeError(f"candidate AI month audit failed: {ai_fail}")
    stage_columns = [column for column in candidate_evidence.columns if column.startswith("stage003_")]
    if not stage_columns:
        raise RuntimeError("Stage003 audit fields are absent")
    if any(is_ai_derived_field(column) for column in stage_columns):
        raise RuntimeError("Stage003 introduced an AI-derived field")

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "ai_pool_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "minute_evidence": minute_audit,
        "candidate_new_ai_feature_count": 0,
        "feature_evidence_summary": feature_evidence_summary,
        "strict_account_equity_reconciliation": account_equity_summary,
        "strict_root_open_reconciliation_pass": True,
        "stop_retry_reconciliation_pass": True,
        "four_anchor_gate_pass": gate,
        "decision": "pending_independent_review" if gate else "failed_four_anchor_gate_pending_independent_review",
        "extend_half_year_allowed": False,
        "overfit_before": "高；规则由当前样本归因形成，仅做隔离验证。",
        "overfit_after": "待独立 agent 复核；本轮没有扫描阈值或倍率。",
        "continue_before": "有；机制透明且固定事件审计满足基础样本门。",
        "continue_after": "待独立 agent 根据四锚点硬门和实现审计判断。",
    }

    summary.to_csv(SUMMARY_PATH, index=False)
    comparison.to_csv(COMPARISON_PATH, index=False)
    curves.to_csv(CURVES_PATH, index=False, compression="gzip")
    trades.to_csv(TRADES_PATH, index=False, compression="gzip")
    candidates.to_csv(ENTRY_CANDIDATES_PATH, index=False, compression="gzip")
    risks.to_csv(ENTRY_RISK_PATH, index=False, compression="gzip")
    events.to_csv(TRADE_EVENTS_PATH, index=False, compression="gzip")
    stop_retry_events.to_csv(STOP_RETRY_EVENTS_PATH, index=False, compression="gzip")
    retry_audit.to_csv(STOP_RETRY_AUDIT_PATH, index=False)
    ai_audit.to_csv(AI_MONTH_AUDIT_PATH, index=False)
    config.to_csv(CONFIG_AUDIT_PATH, index=False)
    feature_audit.to_csv(FEATURE_AUDIT_PATH, index=False)
    _plot(curves)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Stage003 较小止损中等实体风险转移真实引擎 A/B",
                "",
                f"- 生成时间：`{decision['generated_at']}`",
                f"- 决策：`{decision['decision']}`",
                f"- 四锚点硬门：`{gate}`",
                "- 规则新增 AI 特征：`0`；正式 AI 月池仅作为 A/C 共同原路径。",
                "- A/C 均使用交易日会话修复分钟证据，并对未覆盖开仓 fail-close。",
                "",
                "## A/C 摘要",
                "",
                _md_table(summary),
                "",
                "## 硬门对比",
                "",
                _md_table(comparison),
                "",
                "## 特征命中审计",
                "",
                _md_table(feature_audit),
                "",
                "## 成交与 0.5R 重试守恒",
                "",
                _md_table(retry_audit),
                "",
                "## AI 月覆盖审计",
                "",
                _md_table(ai_audit),
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
        ROOT / ".vntrader" / "database.db",
        Path(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        REPAIRED_MINUTE_PATCH_PATH,
        REPAIRED_MINUTE_AUDIT_PATH,
        Path(s000.DECISION_PATH),
        PORTFOLIO_DIR / "qmt_roll_official_live_config.py",
        Path(s847.__file__),
    ]
    missing_inputs = [str(path) for path in input_paths if not path.exists()]
    if missing_inputs:
        raise RuntimeError(f"Stage003 input manifest missing files: {missing_inputs}")
    pd.DataFrame(
        [{"path": str(path), "bytes": path.stat().st_size, "sha256": _sha256(path)} for path in input_paths]
    ).to_csv(INPUT_MANIFEST_PATH, index=False)
    manifest_paths = [
        SUMMARY_PATH,
        COMPARISON_PATH,
        CURVES_PATH,
        TRADES_PATH,
        ENTRY_CANDIDATES_PATH,
        ENTRY_RISK_PATH,
        TRADE_EVENTS_PATH,
        STOP_RETRY_EVENTS_PATH,
        STOP_RETRY_AUDIT_PATH,
        AI_MONTH_AUDIT_PATH,
        CONFIG_AUDIT_PATH,
        FEATURE_AUDIT_PATH,
        INPUT_MANIFEST_PATH,
        CHART_PATH,
        DECISION_PATH,
        REPORT_PATH,
    ]
    pd.DataFrame(
        [{"path": str(path), "bytes": path.stat().st_size, "sha256": _sha256(path)} for path in manifest_paths]
    ).to_csv(MANIFEST_PATH, index=False)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), flush=True)
    print(comparison.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
