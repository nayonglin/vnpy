from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import stage008_fresh_baseline_breakout_quality_attribution as s008


LINE_ID = "futures_trend_tight_stop_quality_sizing"
STAGE = "Stage009"
MODEL_TAG = "stage009_minute_opening_structure_attribution_v1"
OUTPUT_PREFIX = "tight_stop_quality_stage009"

ROOT = Path(__file__).resolve().parents[4]
LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage009_minute_opening_structure_attribution"
STAGE009_TOOL_PATH = Path(__file__).resolve()
STAGE009_TEST_PATH = LINE_DIR / "tests" / "test_stage009_minute_opening_structure_attribution.py"
STAGE009_PREDECL_PATH = LINE_DIR / "stages" / "20260714_1606_stage009_minute_opening_structure_attribution_predecl.md"
BACKTEST_OUTPUT_DIR = ROOT / "examples" / "portfolio_backtesting" / "backtest_outputs"
ALL_CONTRACT_METADATA_PATH = BACKTEST_OUTPUT_DIR / "tqsdk_all_futures_contract_metadata.csv"
DEFAULT_CONTRACT_METADATA_PATH = BACKTEST_OUTPUT_DIR / "tqsdk_contract_metadata.csv"
CONTRACT_METADATA_PATH = (
    ALL_CONTRACT_METADATA_PATH if ALL_CONTRACT_METADATA_PATH.exists() else DEFAULT_CONTRACT_METADATA_PATH
)
MAIN_MAPPING_PATH = BACKTEST_OUTPUT_DIR / "tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv"
STAGE000_OUT = LINE_DIR / "outputs" / "stage000_complete_entry_session_minute_repair"
STAGE000_TAG = "stage000_complete_entry_session_minute_repair_v1"
STAGE000_PREFIX = "tight_stop_quality_stage000"
MINUTE_PATCH_PATH = STAGE000_OUT / f"{STAGE000_PREFIX}_entry_session_minute_patch_{STAGE000_TAG}.csv"
MINUTE_AUDIT_PATH = STAGE000_OUT / f"{STAGE000_PREFIX}_entry_session_coverage_audit_{STAGE000_TAG}.csv"
STAGE000_DECISION_PATH = STAGE000_OUT / f"{STAGE000_PREFIX}_decision_{STAGE000_TAG}.json"

DISCOVERY_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_discovery_minute_events_{MODEL_TAG}.csv.gz"
FEATURE_BINS_PATH = OUT / f"{OUTPUT_PREFIX}_discovery_feature_bins_{MODEL_TAG}.csv"
FIXED_STRUCTURE_PATH = OUT / f"{OUTPUT_PREFIX}_discovery_fixed_structure_{MODEL_TAG}.csv"
YEARLY_PATH = OUT / f"{OUTPUT_PREFIX}_discovery_yearly_{MODEL_TAG}.csv"
FUTURE_SEAL_PATH = OUT / f"{OUTPUT_PREFIX}_historical_locked_feature_seal_{MODEL_TAG}.json"
COVERAGE_PATH = OUT / f"{OUTPUT_PREFIX}_coverage_audit_{MODEL_TAG}.csv"
INPUT_MANIFEST_PATH = OUT / f"{OUTPUT_PREFIX}_input_manifest_{MODEL_TAG}.csv"
OUTPUT_MANIFEST_PATH = OUT / f"{OUTPUT_PREFIX}_output_manifest_{MODEL_TAG}.csv"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_discovery_feature_bins_{MODEL_TAG}.png"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

CONTINUOUS_FEATURES = (
    "or5_directional_return_original_r",
    "or5_close_location",
    "or5_path_efficiency",
    "or5_adverse_excursion_original_r",
    "or5_range_original_r",
    "minute6_entry_extension_original_r",
    "micro_stop_original_stop_ratio",
)

MINUTE_FEATURE_SEAL_COLUMNS = (
    "open_trade_id",
    "vt_symbol",
    "product",
    "direction",
    "entry_date",
    "sample_segment",
    "session_start",
    "feature_last_bar_time",
    "decision_time",
    "counterfactual_entry_time",
    "feature_bar_count",
    "session_bar_count",
    "planned_entry_price",
    "actual_entry_price",
    "planned_stop_distance",
    "counterfactual_entry_price",
    "structural_stop_price",
    "micro_stop_distance",
    "effective_pricetick",
    "pricetick_rule",
    *CONTINUOUS_FEATURES,
    "minute6_open_beyond_planned_entry",
    "or5_all_closes_directional_side",
    "feature_future_violation",
)

EXTERNAL_RESEARCH = (
    {
        "source": "广州期货交易所碳酸锂上市资料",
        "url": "https://www.gfex.com.cn/gfex/tslpzzl/202307/db1ea6ce118342ba886e5ef5b667ebe1/files/e57713398e094ca8af27b7ba49f82259.pdf",
        "judgment": "碳酸锂上市时最小变动价位为 50 元/吨，不能用当前静态元数据覆盖历史交易日。",
    },
    {
        "source": "广期所调整碳酸锂期货最小变动价位通知转引",
        "url": "https://www.yicai.com/news/102390285.html",
        "judgment": "2024-12-17 结算后调整为 20 元/吨，因此 2024-12-18 交易日起使用 20 元/吨。",
    },
    {
        "source": "Structural Limits of OHLCV-Based Intraday Signals in MNQ Futures",
        "url": "https://arxiv.org/abs/2605.04004",
        "judgment": "开盘区间和分钟 OHLCV 形态在严格成本与 walk-forward 下很容易失效，必须先做覆盖和反证。",
    },
    {
        "source": "Is There an Intraday Momentum Effect in Commodity Futures and Options: Evidence from the Chinese Market",
        "url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4688712",
        "judgment": "中国商品高频样本存在日内反转证据，不能先验假定开盘推进一定延续。",
    },
    {
        "source": "A Profitable Day Trading Strategy For The U.S. Equity Market",
        "url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4729284",
        "judgment": "固定五分钟观察窗可提供可复现时点，但美股收益结论不能迁移到中国商品。",
    },
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _json_safe(value: Any) -> Any:
    return s008._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s008._md_table(frame, max_rows=max_rows)


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0:
        return np.nan, np.nan
    proportion = successes / total
    denominator = 1.0 + z * z / total
    centre = (proportion + z * z / (2.0 * total)) / denominator
    margin = z * math.sqrt(
        proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total)
    ) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def effective_pricetick(
    vt_symbol: str,
    entry_date: Any,
    current_pricetick: float,
) -> tuple[float, str]:
    """Resolve the tick that was effective on the event's trading date."""
    symbol, _, exchange = str(vt_symbol).partition(".")
    product = "".join(character for character in symbol if character.isalpha()).lower()
    trade_date = pd.Timestamp(entry_date).normalize()
    tick = _safe_float(current_pricetick)
    if tick <= 0:
        raise ValueError("current contract pricetick is invalid")
    if product == "lc" and exchange.upper() == "GFEX" and trade_date < pd.Timestamp("2024-12-18"):
        return 50.0, "gfex_lc_pre_2024_12_18"
    return tick, "current_metadata"


def _validate_session(session: pd.DataFrame) -> pd.DataFrame:
    required = {"bar_datetime", "open", "high", "low", "close"}
    missing = required - set(session.columns)
    if missing:
        raise ValueError(f"minute session missing columns: {sorted(missing)}")
    data = session.copy()
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce").dt.tz_localize(None)
    for column in ("open", "high", "low", "close", "volume"):
        if column not in data.columns:
            data[column] = 0.0
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=["bar_datetime", "open", "high", "low", "close"])
    data = data.sort_values("bar_datetime").reset_index(drop=True)
    if len(data) < 6:
        raise ValueError("minute session has fewer than six bars")
    if data["bar_datetime"].duplicated().any():
        raise ValueError("minute session has duplicate timestamps")
    first_six = data.iloc[:6]
    diffs = first_six["bar_datetime"].diff().dropna()
    if not diffs.eq(pd.Timedelta(minutes=1)).all():
        raise ValueError("first six minute bars are not contiguous")
    geometry_ok = (
        data["high"].ge(data[["open", "close"]].max(axis=1))
        & data["low"].le(data[["open", "close"]].min(axis=1))
        & data["high"].ge(data["low"])
    )
    if not geometry_ok.all():
        raise ValueError("minute session has invalid OHLC geometry")
    return data


def _first_touch(
    bars: pd.DataFrame,
    *,
    direction: str,
    entry_price: float,
    risk_distance: float,
    reward_multiple: float,
) -> tuple[str, int, pd.Timestamp | pd.NaT]:
    sign = 1.0 if direction == "long" else -1.0
    stop_price = entry_price - sign * risk_distance
    target_price = entry_price + sign * reward_multiple * risk_distance
    for index, row in enumerate(bars.itertuples(index=False)):
        if direction == "long":
            stop_hit = float(row.low) <= stop_price
            target_hit = float(row.high) >= target_price
        else:
            stop_hit = float(row.high) >= stop_price
            target_hit = float(row.low) <= target_price
        if stop_hit:
            return "stop_first", index, pd.Timestamp(row.bar_datetime)
        if target_hit:
            return "target_first", index, pd.Timestamp(row.bar_datetime)
    return "no_touch", -1, pd.NaT


def _window_return_micro_r(
    bars: pd.DataFrame,
    *,
    direction: str,
    entry_price: float,
    risk_distance: float,
    count: int,
) -> float:
    if len(bars) < count:
        return np.nan
    sign = 1.0 if direction == "long" else -1.0
    close = _safe_float(bars.iloc[count - 1]["close"])
    return sign * (close - entry_price) / risk_distance


def compute_minute_opening_event(
    event: Mapping[str, Any],
    session: pd.DataFrame,
    *,
    pricetick: float,
) -> dict[str, Any]:
    data = _validate_session(session)
    direction = str(event.get("direction", "")).lower()
    if direction not in {"long", "short"}:
        raise ValueError(f"unsupported direction: {direction}")
    tick = _safe_float(pricetick)
    planned_stop_distance = _safe_float(event.get("planned_stop_distance"))
    planned_entry_price = _safe_float(event.get("planned_entry_price"))
    actual_entry_price = _safe_float(event.get("actual_entry_price"))
    if tick <= 0 or planned_stop_distance <= 0 or planned_entry_price <= 0 or actual_entry_price <= 0:
        raise ValueError("invalid tick or original entry risk geometry")

    opening = data.iloc[:5]
    minute6 = data.iloc[5]
    after = data.iloc[5:].reset_index(drop=True)
    open1 = _safe_float(opening.iloc[0]["open"])
    close5 = _safe_float(opening.iloc[-1]["close"])
    high5 = float(opening["high"].max())
    low5 = float(opening["low"].min())
    range5 = high5 - low5
    sign = 1.0 if direction == "long" else -1.0
    counterfactual_entry_price = _safe_float(minute6["open"])
    structural_stop_price = low5 - tick if direction == "long" else high5 + tick
    micro_stop_distance = sign * (counterfactual_entry_price - structural_stop_price)
    if micro_stop_distance < tick - 1e-12:
        raise ValueError("minute6 entry is beyond the structural stop")

    close_path = np.concatenate(([open1], opening["close"].to_numpy(dtype=float)))
    path_length = float(np.abs(np.diff(close_path)).sum())
    directional_move = sign * (close5 - open1)
    close_location = (
        (close5 - low5) / range5
        if direction == "long" and range5 > 0
        else (high5 - close5) / range5
        if direction == "short" and range5 > 0
        else 0.5
    )
    adverse = max(0.0, open1 - low5) if direction == "long" else max(0.0, high5 - open1)
    closes = opening["close"].to_numpy(dtype=float)
    all_directional = bool(np.all(closes >= open1)) if direction == "long" else bool(np.all(closes <= open1))
    beyond_planned = (
        counterfactual_entry_price >= planned_entry_price
        if direction == "long"
        else counterfactual_entry_price <= planned_entry_price
    )

    first1, first1_index, first1_time = _first_touch(
        after,
        direction=direction,
        entry_price=counterfactual_entry_price,
        risk_distance=micro_stop_distance,
        reward_multiple=1.0,
    )
    first2, first2_index, first2_time = _first_touch(
        after,
        direction=direction,
        entry_price=counterfactual_entry_price,
        risk_distance=micro_stop_distance,
        reward_multiple=2.0,
    )
    feature_last_bar_time = pd.Timestamp(opening.iloc[-1]["bar_datetime"])
    entry_time = pd.Timestamp(minute6["bar_datetime"])

    return {
        "open_trade_id": str(event.get("open_trade_id", "")),
        "vt_symbol": str(event.get("vt_symbol", "")),
        "product": str(event.get("product", "")),
        "direction": direction,
        "entry_date": pd.Timestamp(event.get("entry_date")).normalize(),
        "sample_segment": str(event.get("sample_segment", "")),
        "session_start": pd.Timestamp(data.iloc[0]["bar_datetime"]),
        "session_end": pd.Timestamp(data.iloc[-1]["bar_datetime"]),
        "session_bar_count": int(len(data)),
        "feature_bar_count": 5,
        "feature_last_bar_time": feature_last_bar_time,
        "decision_time": entry_time,
        "counterfactual_entry_time": entry_time,
        "planned_entry_price": planned_entry_price,
        "actual_entry_price": actual_entry_price,
        "planned_stop_distance": planned_stop_distance,
        "counterfactual_entry_price": counterfactual_entry_price,
        "structural_stop_price": structural_stop_price,
        "micro_stop_distance": micro_stop_distance,
        "effective_pricetick": tick,
        "pricetick_rule": "provided",
        "or5_directional_return_original_r": directional_move / planned_stop_distance,
        "or5_close_location": float(np.clip(close_location, 0.0, 1.0)),
        "or5_path_efficiency": directional_move / path_length if path_length > 0 else 0.0,
        "or5_adverse_excursion_original_r": adverse / planned_stop_distance,
        "or5_range_original_r": range5 / planned_stop_distance,
        "minute6_entry_extension_original_r": sign
        * (counterfactual_entry_price - planned_entry_price)
        / planned_stop_distance,
        "micro_stop_original_stop_ratio": micro_stop_distance / planned_stop_distance,
        "minute6_open_beyond_planned_entry": int(beyond_planned),
        "or5_all_closes_directional_side": int(all_directional),
        "feature_future_violation": int(not feature_last_bar_time < entry_time),
        "micro_first_touch_1r": first1,
        "micro_first_touch_1r_bar_index": first1_index,
        "micro_first_touch_1r_time": first1_time,
        "micro_first_touch_2r": first2,
        "micro_first_touch_2r_bar_index": first2_index,
        "micro_first_touch_2r_time": first2_time,
        "return_5m_micro_r": _window_return_micro_r(
            after, direction=direction, entry_price=counterfactual_entry_price, risk_distance=micro_stop_distance, count=5
        ),
        "return_15m_micro_r": _window_return_micro_r(
            after, direction=direction, entry_price=counterfactual_entry_price, risk_distance=micro_stop_distance, count=15
        ),
        "return_60m_micro_r": _window_return_micro_r(
            after, direction=direction, entry_price=counterfactual_entry_price, risk_distance=micro_stop_distance, count=60
        ),
        "baseline_realized_pnl": _safe_float(event.get("baseline_realized_pnl")),
        "baseline_r_multiple": _safe_float(event.get("baseline_r_multiple")),
    }


def partition_minute_outputs(events: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    if "sample_segment" not in events.columns:
        raise ValueError("minute events missing sample_segment")
    discovery = events.loc[events["sample_segment"].astype(str).eq("discovery")].copy()
    future = events.loc[~events["sample_segment"].astype(str).eq("discovery")].copy()
    future_features = future.reindex(columns=MINUTE_FEATURE_SEAL_COLUMNS)
    seal = {
        "row_count": int(len(future_features)),
        "feature_only_sha256": s008._frame_sha256(future_features),
        "feature_hash_contract": s008.FRAME_HASH_CONTRACT,
        "segments": future_features["sample_segment"].value_counts().sort_index().to_dict(),
        "feature_columns": list(MINUTE_FEATURE_SEAL_COLUMNS),
        "feature_allowlist_enforced": True,
        "future_row_data_exported": False,
        "full_period_baseline_outcomes_persisted": True,
        "true_oos_claim": False,
        "purpose": "后段仅作分钟新特征预声明后的历史锁定评估，不构成真正未见 OOS。",
    }
    return discovery, seal


def _group_summary(group: pd.DataFrame) -> dict[str, Any]:
    touch1 = group["micro_first_touch_1r"].astype(str)
    touch2 = group["micro_first_touch_2r"].astype(str)

    def touch_summary(touch: pd.Series, suffix: str) -> dict[str, Any]:
        resolved = touch.isin(["target_first", "stop_first"])
        target = touch.eq("target_first")
        resolved_count = int(resolved.sum())
        target_count = int(target.sum())
        low, high = wilson_interval(target_count, resolved_count)
        return {
            f"resolved_{suffix}_count": resolved_count,
            f"target_first_{suffix}_count": target_count,
            f"stop_first_{suffix}_count": int(touch.eq("stop_first").sum()),
            f"no_touch_{suffix}_count": int(touch.eq("no_touch").sum()),
            f"target_first_{suffix}_rate": target_count / resolved_count if resolved_count else np.nan,
            f"target_first_{suffix}_wilson_low": low,
            f"target_first_{suffix}_wilson_high": high,
        }

    return {
        "candidate_count": int(len(group)),
        "product_count": int(group["product"].nunique()),
        "direction_count": int(group["direction"].nunique()),
        "year_count": int(pd.to_datetime(group["entry_date"]).dt.year.nunique()),
        **touch_summary(touch1, "1r"),
        **touch_summary(touch2, "2r"),
        "baseline_total_pnl": float(pd.to_numeric(group["baseline_realized_pnl"], errors="coerce").sum()),
        "baseline_total_r": float(pd.to_numeric(group["baseline_r_multiple"], errors="coerce").sum()),
        "baseline_median_r": float(pd.to_numeric(group["baseline_r_multiple"], errors="coerce").median()),
        "median_return_5m_micro_r": float(pd.to_numeric(group["return_5m_micro_r"], errors="coerce").median()),
        "median_return_15m_micro_r": float(pd.to_numeric(group["return_15m_micro_r"], errors="coerce").median()),
        "median_return_60m_micro_r": float(pd.to_numeric(group["return_60m_micro_r"], errors="coerce").median()),
    }


def discovery_feature_bins(events: pd.DataFrame) -> pd.DataFrame:
    discovery = events.loc[events["sample_segment"].astype(str).eq("discovery")].copy()
    rows: list[dict[str, Any]] = []
    for feature, feature_bin, group in _feature_bin_groups(discovery):
        values_in_bin = pd.to_numeric(group[feature], errors="coerce")
        rows.append(
            {
                "feature": feature,
                "feature_bin": feature_bin,
                "feature_min": float(values_in_bin.min()),
                "feature_max": float(values_in_bin.max()),
                **_group_summary(group),
            }
        )
    return pd.DataFrame(rows)


def _feature_bin_groups(discovery: pd.DataFrame):
    for feature in CONTINUOUS_FEATURES:
        values = pd.to_numeric(discovery[feature], errors="coerce")
        valid = discovery.loc[values.notna()].copy()
        if valid.empty:
            continue
        valid["_feature_bin_code"] = pd.qcut(
            pd.to_numeric(valid[feature], errors="coerce"),
            q=4,
            labels=False,
            duplicates="drop",
        )
        for bin_index, group in valid.groupby("_feature_bin_code", sort=True):
            yield feature, f"Q{int(bin_index) + 1}", group.drop(columns=["_feature_bin_code"])


def discovery_fixed_structure(events: pd.DataFrame) -> pd.DataFrame:
    discovery = events.loc[events["sample_segment"].astype(str).eq("discovery")].copy()
    masks = {
        "all_discovery": pd.Series(True, index=discovery.index),
        "minute6_favourable_and_micro_stop_not_wider_than_original": (
            pd.to_numeric(discovery["minute6_open_beyond_planned_entry"], errors="coerce").eq(1)
            & pd.to_numeric(discovery["micro_stop_original_stop_ratio"], errors="coerce").le(1.0)
        ),
    }
    rows = []
    for structure, mask in masks.items():
        group = discovery.loc[mask].copy()
        rows.append({"structure": structure, **_group_summary(group)})
    return pd.DataFrame(rows)


def discovery_yearly(events: pd.DataFrame) -> pd.DataFrame:
    discovery = events.loc[events["sample_segment"].astype(str).eq("discovery")].copy()
    discovery["entry_year"] = pd.to_datetime(discovery["entry_date"]).dt.year
    rows: list[dict[str, Any]] = []

    def append_years(
        frame: pd.DataFrame,
        *,
        scope_type: str,
        scope_id: str,
        feature: str = "",
        feature_bin: str = "",
    ) -> None:
        for year, group in frame.groupby("entry_year", sort=True):
            rows.append(
                {
                    "scope_type": scope_type,
                    "scope_id": scope_id,
                    "feature": feature,
                    "feature_bin": feature_bin,
                    "entry_year": int(year),
                    **_group_summary(group),
                }
            )

    append_years(discovery, scope_type="all_discovery", scope_id="all_discovery")
    fixed_mask = (
        pd.to_numeric(discovery["minute6_open_beyond_planned_entry"], errors="coerce").eq(1)
        & pd.to_numeric(discovery["micro_stop_original_stop_ratio"], errors="coerce").le(1.0)
    )
    append_years(
        discovery.loc[fixed_mask],
        scope_type="fixed_structure",
        scope_id="minute6_favourable_and_micro_stop_not_wider_than_original",
    )
    for feature, feature_bin, group in _feature_bin_groups(discovery):
        append_years(
            group,
            scope_type="feature_bin",
            scope_id=f"{feature}:{feature_bin}",
            feature=feature,
            feature_bin=feature_bin,
        )
    return pd.DataFrame(rows)


def _plot_feature_bins(bins: pd.DataFrame) -> None:
    features = list(CONTINUOUS_FEATURES)
    fig, axes = plt.subplots(len(features), 2, figsize=(14, 3.1 * len(features)), constrained_layout=True)
    for row_index, feature in enumerate(features):
        part = bins.loc[bins["feature"].eq(feature)].copy()
        x = np.arange(len(part))
        axes[row_index, 0].bar(x, part["target_first_1r_rate"], color="#1565c0")
        axes[row_index, 0].set_xticks(x, part["feature_bin"])
        axes[row_index, 0].set_ylim(0.0, 1.0)
        axes[row_index, 0].axhline(0.5, color="#6b7280", linestyle="--", linewidth=0.8)
        axes[row_index, 0].set_ylabel("target-first rate")
        axes[row_index, 0].set_title(feature)
        axes[row_index, 1].bar(x, part["baseline_total_r"], color="#2e7d32")
        axes[row_index, 1].set_xticks(x, part["feature_bin"])
        axes[row_index, 1].axhline(0.0, color="#111827", linewidth=0.8)
        axes[row_index, 1].set_ylabel("baseline total R")
        axes[row_index, 1].set_title("same parent events, baseline R")
        for axis in axes[row_index]:
            axis.grid(alpha=0.2, axis="y")
    fig.suptitle("Stage009 discovery only: minute structure attribution", fontsize=14)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _manifest(paths: list[Path]) -> pd.DataFrame:
    rows = []
    for path in paths:
        if not path.exists():
            raise RuntimeError(f"manifest input/output missing: {path}")
        rows.append({"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": _sha256(path)})
    return pd.DataFrame(rows)


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any], dict[str, Any]]:
    required = [
        s008.CLOSED_LOTS_PATH,
        s008.OPEN_LINEAGE_PATH,
        s008.DECISION_PATH,
        MINUTE_PATCH_PATH,
        MINUTE_AUDIT_PATH,
        STAGE000_DECISION_PATH,
    ]
    for path in required:
        if not path.exists():
            raise RuntimeError(f"missing Stage009 input: {path}")
    stage008_decision = json.loads(s008.DECISION_PATH.read_text(encoding="utf-8"))
    if stage008_decision.get("decision") != "stage008_baseline_verified_historical_path_no_true_oos_claim":
        raise RuntimeError("Stage008 verified historical baseline decision is missing")
    if not bool(stage008_decision.get("stage009_historical_locked_evaluation_allowed")):
        raise RuntimeError("Stage008 did not allow historical locked evaluation")
    stage000_decision = json.loads(STAGE000_DECISION_PATH.read_text(encoding="utf-8"))
    if stage000_decision.get("decision") != "complete_entry_session_minute_patch_ready":
        raise RuntimeError("Stage000 minute patch is not ready")
    if _sha256(MINUTE_PATCH_PATH) != stage000_decision.get("patch_sha256"):
        raise RuntimeError("Stage000 minute patch hash mismatch")
    if _sha256(MINUTE_AUDIT_PATH) != stage000_decision.get("audit_sha256"):
        raise RuntimeError("Stage000 minute audit hash mismatch")
    closed = pd.read_csv(s008.CLOSED_LOTS_PATH)
    lineage = pd.read_csv(s008.OPEN_LINEAGE_PATH)
    minute = pd.read_csv(MINUTE_PATCH_PATH, encoding="utf-8-sig")
    return closed, lineage, minute, stage008_decision, stage000_decision


def _event_inputs(closed: pd.DataFrame, lineage: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    events, aggregate_audit = s008.legacy.aggregate_entry_events(closed)
    roots = lineage.loc[lineage["attempt_kind"].astype(str).eq("flat_entry")].copy()
    if roots["open_trade_id"].duplicated().any():
        raise RuntimeError("flat root open ids are not unique")
    root_columns = [
        "open_trade_id",
        "planned_entry_price",
        "actual_entry_price",
        "planned_stop_distance",
        "stop_price",
    ]
    roots = roots[root_columns].rename(
        columns={"planned_stop_distance": "lineage_planned_stop_distance"}
    )
    merged = events.merge(roots, on="open_trade_id", how="left", validate="one_to_one")
    lineage_columns = [
        "planned_entry_price",
        "actual_entry_price",
        "lineage_planned_stop_distance",
        "stop_price",
    ]
    missing = merged[lineage_columns].isna().any(axis=1)
    if missing.any():
        ids = merged.loc[missing, "open_trade_id"].astype(str).tolist()
        raise RuntimeError(f"closed event missing root lineage: {ids[:10]}")
    event_stop = pd.to_numeric(merged["planned_stop_distance"], errors="coerce")
    lineage_stop = pd.to_numeric(merged["lineage_planned_stop_distance"], errors="coerce")
    if not np.allclose(event_stop, lineage_stop, rtol=0.0, atol=1e-8):
        raise RuntimeError("event and root-lineage planned stop distances disagree")
    merged["planned_stop_distance"] = lineage_stop
    merged.drop(columns=["lineage_planned_stop_distance"], inplace=True)
    merged.rename(
        columns={"realized_pnl": "baseline_realized_pnl", "r_multiple": "baseline_r_multiple"},
        inplace=True,
    )
    merged["entry_date"] = pd.to_datetime(merged["entry_date"], errors="coerce").dt.normalize()
    merged["sample_segment"] = merged["entry_date"].map(s008._sample_segment)
    return merged, aggregate_audit


def _compute_all_events(
    events: pd.DataFrame,
    minute: pd.DataFrame,
    priceticks: Mapping[str, float],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    minute = minute.copy()
    minute["bar_date"] = pd.to_datetime(minute["bar_date"], errors="coerce").dt.normalize()
    minute["bar_datetime"] = pd.to_datetime(minute["bar_datetime"], errors="coerce").dt.tz_localize(None)
    groups = {
        (str(symbol), pd.Timestamp(date).normalize()): group.copy()
        for (symbol, date), group in minute.groupby(["vt_symbol", "bar_date"], sort=False)
    }
    rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    for event in events.to_dict("records"):
        key = (str(event["vt_symbol"]), pd.Timestamp(event["entry_date"]).normalize())
        session = groups.get(key)
        status = "pass"
        error = ""
        if session is None:
            status = "missing_session"
            error = "no Stage000 minute session"
        elif key[0] not in priceticks:
            status = "missing_pricetick"
            error = "contract pricetick missing"
        else:
            try:
                tick, tick_rule = effective_pricetick(key[0], key[1], float(priceticks[key[0]]))
                result = compute_minute_opening_event(event, session, pricetick=tick)
                result["effective_pricetick"] = tick
                result["pricetick_rule"] = tick_rule
                first_open = _safe_float(session.sort_values("bar_datetime").iloc[0]["open"])
                if not np.isclose(first_open, _safe_float(event["actual_entry_price"]), rtol=0.0, atol=1e-8):
                    raise ValueError("root fill does not equal first session minute open")
                rows.append(result)
            except Exception as exc:
                status = "invalid_session_or_feature"
                error = str(exc)
        coverage_rows.append(
            {
                "open_trade_id": str(event["open_trade_id"]),
                "vt_symbol": key[0],
                "entry_date": key[1],
                "sample_segment": str(event["sample_segment"]),
                "effective_pricetick": result.get("effective_pricetick", np.nan) if status == "pass" else np.nan,
                "pricetick_rule": result.get("pricetick_rule", "") if status == "pass" else "",
                "status": status,
                "error": error,
            }
        )
    coverage = pd.DataFrame(coverage_rows)
    if not coverage["status"].eq("pass").all():
        failures = coverage.loc[~coverage["status"].eq("pass")]
        raise RuntimeError(f"Stage009 minute coverage failed: {failures.head(10).to_dict('records')}")
    result = pd.DataFrame(rows)
    if len(result) != len(events) or result["open_trade_id"].nunique() != len(events):
        raise RuntimeError("Stage009 event count is not conserved")
    if pd.to_numeric(result["feature_future_violation"], errors="coerce").fillna(1).ne(0).any():
        raise RuntimeError("Stage009 minute feature uses a future bar")
    return result, coverage


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("[stage009] minute opening structure attribution start", flush=True)
    closed, lineage, minute, stage008_decision, stage000_decision = _load_inputs()
    metadata = s008.strict.s901.s513._metadata()
    events, aggregate_audit = _event_inputs(closed, lineage)
    minute_events, coverage = _compute_all_events(events, minute, metadata["priceticks"])
    discovery, future_seal = partition_minute_outputs(minute_events)
    bins = discovery_feature_bins(minute_events)
    fixed = discovery_fixed_structure(minute_events)
    yearly = discovery_yearly(minute_events)

    expected_segments = {"discovery": 171, "validation": 78, "holdout": 51}
    actual_segments = minute_events["sample_segment"].value_counts().sort_index().to_dict()
    if actual_segments != expected_segments:
        raise RuntimeError(f"unexpected Stage009 segment counts: {actual_segments}")
    coverage_ratio = float(coverage["status"].eq("pass").mean())
    if coverage_ratio != 1.0:
        raise RuntimeError(f"Stage009 minute coverage is not complete: {coverage_ratio}")

    input_paths = [
        s008.CLOSED_LOTS_PATH,
        s008.OPEN_LINEAGE_PATH,
        s008.DECISION_PATH,
        MINUTE_PATCH_PATH,
        MINUTE_AUDIT_PATH,
        STAGE000_DECISION_PATH,
        STAGE009_TOOL_PATH,
        STAGE009_TEST_PATH,
        STAGE009_PREDECL_PATH,
        CONTRACT_METADATA_PATH,
        MAIN_MAPPING_PATH,
    ]
    universe_path = Path(
        str(
            s008.strict.s901.s513._c3_overrides(s008.strict.s901.s513.START_DT).get(
                "product_universe_csv_path", ""
            )
        )
    ).expanduser()
    if str(universe_path):
        input_paths.append(universe_path)
    _manifest(input_paths).to_csv(INPUT_MANIFEST_PATH, index=False)
    discovery.to_csv(DISCOVERY_EVENTS_PATH, index=False, compression="gzip")
    bins.to_csv(FEATURE_BINS_PATH, index=False)
    fixed.to_csv(FIXED_STRUCTURE_PATH, index=False)
    yearly.to_csv(YEARLY_PATH, index=False)
    FUTURE_SEAL_PATH.write_text(json.dumps(_json_safe(future_seal), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    coverage.to_csv(COVERAGE_PATH, index=False)
    _plot_feature_bins(bins)

    fixed_candidate = fixed.loc[
        fixed["structure"].eq("minute6_favourable_and_micro_stop_not_wider_than_original")
    ].iloc[0].to_dict()
    historical_tick_rows = coverage.loc[
        coverage["pricetick_rule"].astype(str).eq("gfex_lc_pre_2024_12_18"),
        ["open_trade_id", "vt_symbol", "entry_date", "effective_pricetick"],
    ]
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision": "stage009_pending_independent_review_no_strategy_change",
        "stage010_allowed": False,
        "strategy_changed": False,
        "new_ai_feature_count": 0,
        "minute_window_bars": 5,
        "counterfactual_entry_bar": 6,
        "structural_stop_buffer_ticks": 1,
        "historical_pricetick_rule": {
            "lc.GFEX_before_2024_12_18": 50.0,
            "lc.GFEX_from_2024_12_18": 20.0,
            "effective_trade_date": "2024-12-18",
        },
        "pricetick_rule_counts": coverage["pricetick_rule"].value_counts().sort_index().to_dict(),
        "historical_pricetick_corrected_events": historical_tick_rows.to_dict("records"),
        "same_bar_ordering": "stop_first",
        "event_count": int(len(minute_events)),
        "segment_counts": actual_segments,
        "minute_coverage_ratio": coverage_ratio,
        "aggregate_audit": aggregate_audit,
        "future_feature_seal": future_seal,
        "fixed_structure_discovery_summary": fixed_candidate,
        "stage008_decision": stage008_decision.get("decision"),
        "stage000_decision": stage000_decision.get("decision"),
        "true_oos_available": False,
        "evaluation_scope": "predeclared historical locked evaluation for a new minute feature family",
        "external_research": EXTERNAL_RESEARCH,
        "overfit_before": "高：分钟形态自由度大；已冻结五分钟观察、第六分钟开盘、一个 tick 结构止损和分段。",
        "overfit_after": "待独立 agent 复核；Stage009 只开放 2020-2022 discovery，未产生交易参数或组合收益。",
        "continue_before": "有价值：先验证分钟小止损结构是否有足够跨品种、跨方向、跨年份覆盖。",
        "continue_after": "待独立 agent 复核覆盖、因果时序和统计后，才决定是否预声明唯一 Stage010。",
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Stage009 分钟级开盘结构与紧止损机会归因",
                "",
                f"- 生成时间：`{decision['generated_at']}`",
                f"- 决策：`{decision['decision']}`",
                "- 本阶段不改变策略、不新增 AI 特征、不输出组合候选收益。",
                "- 2023-2026 仅为后续历史锁定评估，不构成真正未见 OOS。",
                "",
                "## 数据与时序",
                "",
                f"- 事件：`{len(minute_events)}`；分段：`{json.dumps(actual_segments, ensure_ascii=False)}`。",
                f"- 分钟覆盖：`{coverage_ratio:.4%}`；特征未来引用：`0`。",
                "- 仅用最先完成的 5 根一分钟 K；第 6 根真实 open 为最早反事实成交；同 bar 止损优先。",
                f"- 历史 tick 规则计数：`{json.dumps(_json_safe(decision['pricetick_rule_counts']), ensure_ascii=False)}`。",
                f"- 历史 lc 修正事件：`{json.dumps(_json_safe(decision['historical_pricetick_corrected_events']), ensure_ascii=False)}`。",
                "",
                "## 固定结构覆盖",
                "",
                _md_table(fixed),
                "",
                "## Discovery 年度分解",
                "",
                _md_table(yearly),
                "",
                "## Discovery 特征四分位",
                "",
                _md_table(bins),
                "",
                "## 完整性审计",
                "",
                f"- 闭合事件守恒：`{json.dumps(_json_safe(aggregate_audit), ensure_ascii=False)}`",
                f"- 后段特征 seal：`{json.dumps(_json_safe(future_seal), ensure_ascii=False)}`",
                "",
                "## 调研判断",
                "",
                "- 分钟开盘形态不能独立创造方向；中国商品还存在日内反转证据。",
                "- 本阶段只判断分钟确认是否值得进入真实引擎，不把代理 first-touch 当作策略收益。",
                "",
                "## 反思",
                "",
                f"- 过拟合：`{decision['overfit_after']}`",
                f"- 继续价值：`{decision['continue_after']}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    output_paths = [
        DISCOVERY_EVENTS_PATH,
        FEATURE_BINS_PATH,
        FIXED_STRUCTURE_PATH,
        YEARLY_PATH,
        FUTURE_SEAL_PATH,
        COVERAGE_PATH,
        INPUT_MANIFEST_PATH,
        CHART_PATH,
        DECISION_PATH,
        REPORT_PATH,
    ]
    _manifest(output_paths).to_csv(OUTPUT_MANIFEST_PATH, index=False)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
