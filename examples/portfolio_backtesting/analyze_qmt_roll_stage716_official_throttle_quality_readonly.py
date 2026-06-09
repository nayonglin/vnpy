from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from qmt_roll_official_live_config import OFFICIAL_LIVE_CAPITAL, OFFICIAL_LIVE_PROFILE_NAME


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
CONTRACT_ROOT = PROJECT_DIR / "downloaded_futures" / "tqsdk_daily_2010_2026_04"

MODEL_TAG = "stage716_official_throttle_quality_readonly_v1"
OUTPUT_PREFIX = "qmt_roll_stage716_official_throttle_quality_readonly"
LINE_ID = "futures_trend_drawdown30_preserve_return"

SOURCE_CANDIDATES_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage696_stage407_soft_streak_risk_entry_candidates_"
    "stage696_stage407_soft_streak_risk_v1.csv"
)
BASE_VARIANT = OFFICIAL_LIVE_PROFILE_NAME

LABELED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_labeled_candidates_{MODEL_TAG}.csv"
SCOPE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_scope_summary_{MODEL_TAG}.csv"
FEATURE_QUALITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_quality_{MODEL_TAG}.csv"
WALKFORWARD_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_walkforward_{MODEL_TAG}.csv"
BUCKET_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
PRODUCT_CONCENTRATION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_concentration_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_chart_{MODEL_TAG}.png"

HORIZONS = (20, 40)
FAVORABLE_R = 2.0
ADVERSE_R = 1.0
MIN_TRAIN_ROWS = 30
MIN_TEST_ROWS = 8
SHRINKAGE_ROWS = 20.0
EMBARGO_DAYS = 40

FEATURE_COLUMNS = (
    "direction",
    "signal",
    "risk_mode",
    "entry_context",
    "status_scope",
    "ai_rank_bucket",
    "rsi_direction_bucket",
    "corr_bucket",
    "drawdown_bucket",
    "active_positions_bucket",
    "pairwise_rank_bucket",
    "contracts_by_risk_bucket",
    "target_risk_bucket",
    "stop_distance_pct_bucket",
    "breakout_bucket",
)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if np.isnan(result) or np.isinf(result):
        return default
    return result


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int = 20) -> str:
    if frame.empty:
        return ""
    data = frame.head(max_rows).copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    headers = [str(column) for column in data.columns]
    rows = [[str(value) for value in row] for row in data.to_numpy()]
    widths = [len(header) for header in headers]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    header_line = "| " + " | ".join(header.ljust(width) for header, width in zip(headers, widths)) + " |"
    sep_line = "| " + " | ".join("-" * width for width in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |" for row in rows]
    return "\n".join([header_line, sep_line, *body])


def _truthy(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin({"true", "1", "1.0", "yes"})


def _vt_product(vt_symbol: Any) -> str:
    text = str(vt_symbol or "")
    return text.split(".", 1)[0]


def _contract_product(vt_symbol: Any) -> str:
    first = str(vt_symbol or "").split(".", 1)[0]
    product = ""
    for char in first:
        if char.isalpha():
            product += char
        else:
            break
    return product


def _load_official_candidates() -> pd.DataFrame:
    if not SOURCE_CANDIDATES_PATH.exists():
        raise FileNotFoundError(f"missing source candidates: {SOURCE_CANDIDATES_PATH}")
    data = pd.read_csv(SOURCE_CANDIDATES_PATH, encoding="utf-8-sig")
    if "variant" not in data.columns:
        raise ValueError("source candidates missing variant column")
    data = data[data["variant"].astype(str).eq(BASE_VARIANT)].copy()
    if data.empty:
        raise RuntimeError(f"no official candidate rows for {BASE_VARIANT}")
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    for column in [
        "streak_entry_structure_risk_recovery_base_multiplier",
        "streak_entry_structure_risk_recovery_effective_multiplier",
        "risk_multiplier",
        "loss_streak",
        "selected_volume",
        "contracts_by_risk",
        "contracts_by_margin",
        "target_risk_amount",
        "planned_entry_price",
        "stop_price",
        "stop_distance",
        "risk_per_contract",
        "estimated_equity",
        "limited_balance",
        "portfolio_drawdown_pct",
        "same_direction_correlation_max_corr",
        "same_direction_correlation_active_count",
        "selection_pairwise_rank",
        "ai_product_pool_rank",
        "rsi_value",
        "active_positions_before",
        "breakout",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    data["skip_reason"] = data.get("skip_reason", "").fillna("").astype(str)
    data["candidate_status"] = data.get("candidate_status", "").fillna("").astype(str)
    data["direction"] = data.get("direction", "").fillna("").astype(str)
    data["signal"] = data.get("signal", "").fillna("").astype(str)
    data["risk_mode"] = data.get("risk_mode", "").fillna("").astype(str)
    data["entry_context"] = data.get("entry_context", "").fillna("").astype(str)

    base_multiplier = data["streak_entry_structure_risk_recovery_base_multiplier"]
    data["base_floor_01"] = base_multiplier.le(0.1000001) | data["loss_streak"].ge(3.0)
    data["effective_floor_01"] = data["risk_multiplier"].le(0.1000001)
    data["passed_initial_filter_bool"] = _truthy(data.get("passed_initial_filter", pd.Series(False, index=data.index)))
    data["ai_allowed_bool"] = _truthy(data.get("ai_product_pool_allowed", pd.Series(False, index=data.index)))
    data["status_scope"] = np.select(
        [
            data["candidate_status"].eq("opened"),
            data["skip_reason"].eq("sizing_zero_volume"),
            data["skip_reason"].eq("concurrent_limit"),
            data["skip_reason"].eq("ai_product_pool_blocked"),
            data["skip_reason"].eq("short_signal_rejected"),
        ],
        ["opened", "sizing_zero_volume", "concurrent_limit", "ai_blocked", "short_rejected"],
        default=data["skip_reason"].where(data["skip_reason"].ne(""), "other_skipped"),
    )
    data["actionable_throttle"] = (
        data["base_floor_01"]
        & data["passed_initial_filter_bool"]
        & data["ai_allowed_bool"]
        & data["status_scope"].isin({"opened", "sizing_zero_volume"})
    )
    return data.sort_values(["date", "candidate_index"]).reset_index(drop=True)


_BAR_CACHE: dict[str, pd.DataFrame] = {}


def _read_contract_bars(vt_symbol: Any) -> pd.DataFrame:
    text = str(vt_symbol or "")
    if "." not in text:
        return pd.DataFrame()
    if text in _BAR_CACHE:
        return _BAR_CACHE[text]
    contract_symbol, exchange = text.split(".", 1)
    path = CONTRACT_ROOT / exchange / f"{contract_symbol}.csv"
    if not path.exists():
        _BAR_CACHE[text] = pd.DataFrame()
        return _BAR_CACHE[text]
    frame = pd.read_csv(path, encoding="utf-8-sig")
    if frame.empty:
        _BAR_CACHE[text] = pd.DataFrame()
        return _BAR_CACHE[text]
    frame["date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()
    for column in ["open", "high", "low", "close", "volume"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["date", "high", "low", "close"]).sort_values("date")
    frame["contract_vt_symbol"] = text
    _BAR_CACHE[text] = frame[["date", "contract_vt_symbol", "open", "high", "low", "close", "volume"]].copy()
    return _BAR_CACHE[text]


def _path_label_for_horizon(row: pd.Series, horizon: int) -> dict[str, Any]:
    entry_price = _safe_float(row.get("planned_entry_price"))
    stop_distance = _safe_float(row.get("stop_distance"))
    direction = str(row.get("direction") or "")
    date = pd.Timestamp(row.get("date"))
    bars = _read_contract_bars(row.get("contract_vt_symbol"))
    prefix = f"h{horizon}"
    if bars.empty or not np.isfinite(entry_price) or not np.isfinite(stop_distance) or stop_distance <= 0.0:
        return {
            f"{prefix}_label_status": "missing_or_invalid",
            f"{prefix}_mfe_r": np.nan,
            f"{prefix}_mae_r": np.nan,
            f"{prefix}_path_score_r": np.nan,
            f"{prefix}_first_barrier": "",
            f"{prefix}_barrier_good": np.nan,
            f"{prefix}_barrier_bad": np.nan,
            f"{prefix}_days_observed": 0,
        }
    future = bars[bars["date"].gt(date)].head(horizon).copy()
    if future.empty:
        return {
            f"{prefix}_label_status": "no_future_bars",
            f"{prefix}_mfe_r": np.nan,
            f"{prefix}_mae_r": np.nan,
            f"{prefix}_path_score_r": np.nan,
            f"{prefix}_first_barrier": "",
            f"{prefix}_barrier_good": np.nan,
            f"{prefix}_barrier_bad": np.nan,
            f"{prefix}_days_observed": 0,
        }
    if direction == "short":
        favorable = (entry_price - future["low"]) / stop_distance
        adverse = (future["high"] - entry_price) / stop_distance
    else:
        favorable = (future["high"] - entry_price) / stop_distance
        adverse = (entry_price - future["low"]) / stop_distance
    mfe_r = float(pd.to_numeric(favorable, errors="coerce").max())
    mae_r = float(pd.to_numeric(adverse, errors="coerce").max())
    first_barrier = "none"
    for fav, adv in zip(favorable, adverse):
        fav_hit = bool(pd.notna(fav) and fav >= FAVORABLE_R)
        adv_hit = bool(pd.notna(adv) and adv >= ADVERSE_R)
        if fav_hit and adv_hit:
            first_barrier = "adverse_same_day"
            break
        if adv_hit:
            first_barrier = "adverse"
            break
        if fav_hit:
            first_barrier = "favorable"
            break
    return {
        f"{prefix}_label_status": "ok",
        f"{prefix}_mfe_r": mfe_r,
        f"{prefix}_mae_r": mae_r,
        f"{prefix}_path_score_r": mfe_r - mae_r,
        f"{prefix}_first_barrier": first_barrier,
        f"{prefix}_barrier_good": 1 if first_barrier == "favorable" else 0,
        f"{prefix}_barrier_bad": 1 if first_barrier in {"adverse", "adverse_same_day"} else 0,
        f"{prefix}_days_observed": int(len(future)),
    }


def _label_candidates(candidates: pd.DataFrame) -> pd.DataFrame:
    data = candidates.copy()
    label_rows: list[dict[str, Any]] = []
    for _, row in data.iterrows():
        labels: dict[str, Any] = {}
        for horizon in HORIZONS:
            labels.update(_path_label_for_horizon(row, horizon))
        label_rows.append(labels)
    labeled = pd.concat([data.reset_index(drop=True), pd.DataFrame(label_rows)], axis=1)
    labeled["product"] = labeled["product_vt_symbol"].map(_vt_product)
    labeled["contract_product"] = labeled["contract_vt_symbol"].map(_contract_product)
    labeled["year"] = labeled["date"].dt.year
    return labeled


def _bucket_rank(value: Any) -> str:
    rank = _safe_float(value)
    if not np.isfinite(rank) or rank <= 0:
        return "rank_missing"
    if rank <= 3:
        return "rank_1_3"
    if rank <= 6:
        return "rank_4_6"
    if rank <= 9:
        return "rank_7_9"
    return "rank_10_plus"


def _bucket_directional_rsi(row: pd.Series) -> str:
    rsi = _safe_float(row.get("rsi_value"))
    if not np.isfinite(rsi):
        return "rsi_missing"
    sign = -1.0 if str(row.get("direction")) == "short" else 1.0
    directional = (rsi - 50.0) * sign
    if directional <= 0.0:
        return "rsi_not_confirmed"
    if directional <= 10.0:
        return "rsi_mild"
    return "rsi_strong"


def _bucket_corr(row: pd.Series) -> str:
    active_count = _safe_float(row.get("same_direction_correlation_active_count"), 0.0)
    corr = _safe_float(row.get("same_direction_correlation_max_corr"), 0.0)
    if active_count <= 0:
        return "corr_none"
    if corr <= 0.30:
        return "corr_low"
    if corr <= 0.60:
        return "corr_mid"
    return "corr_high"


def _bucket_drawdown(value: Any) -> str:
    dd = _safe_float(value, 0.0)
    if abs(dd) <= 1.0:
        dd *= 100.0
    if dd <= 5.0:
        return "dd_0_5"
    if dd <= 15.0:
        return "dd_5_15"
    return "dd_15_plus"


def _bucket_active(value: Any) -> str:
    active = _safe_float(value, 0.0)
    if active <= 0:
        return "active_0"
    if active <= 2:
        return "active_1_2"
    return "active_3_plus"


def _bucket_pairwise(value: Any) -> str:
    rank = _safe_float(value)
    if not np.isfinite(rank) or rank <= 0:
        return "pair_missing"
    if rank <= 2:
        return "pair_top2"
    if rank <= 4:
        return "pair_3_4"
    return "pair_5_plus"


def _bucket_contracts(value: Any) -> str:
    contracts = _safe_float(value, 0.0)
    if contracts <= 0:
        return "contracts_0"
    if contracts <= 1:
        return "contracts_1"
    if contracts <= 3:
        return "contracts_2_3"
    return "contracts_4_plus"


def _bucket_target_risk(value: Any) -> str:
    amount = _safe_float(value, 0.0)
    if amount <= 0:
        return "risk_0"
    if amount < 1000:
        return "risk_lt1k"
    if amount < 2500:
        return "risk_1k_2k5"
    return "risk_ge2k5"


def _bucket_stop_distance_pct(row: pd.Series) -> str:
    entry_price = _safe_float(row.get("planned_entry_price"))
    stop_distance = _safe_float(row.get("stop_distance"))
    if not np.isfinite(entry_price) or entry_price <= 0 or not np.isfinite(stop_distance):
        return "stop_missing"
    pct = abs(stop_distance / entry_price)
    if pct <= 0.03:
        return "stop_tight"
    if pct <= 0.08:
        return "stop_mid"
    return "stop_wide"


def _add_feature_buckets(labeled: pd.DataFrame) -> pd.DataFrame:
    data = labeled.copy()
    data["ai_rank_bucket"] = data["ai_product_pool_rank"].map(_bucket_rank)
    data["rsi_direction_bucket"] = data.apply(_bucket_directional_rsi, axis=1)
    data["corr_bucket"] = data.apply(_bucket_corr, axis=1)
    data["drawdown_bucket"] = data["portfolio_drawdown_pct"].map(_bucket_drawdown)
    data["active_positions_bucket"] = data["active_positions_before"].map(_bucket_active)
    data["pairwise_rank_bucket"] = data["selection_pairwise_rank"].map(_bucket_pairwise)
    data["contracts_by_risk_bucket"] = data["contracts_by_risk"].map(_bucket_contracts)
    data["target_risk_bucket"] = data["target_risk_amount"].map(_bucket_target_risk)
    data["stop_distance_pct_bucket"] = data.apply(_bucket_stop_distance_pct, axis=1)
    data["breakout_bucket"] = np.where(pd.to_numeric(data.get("breakout", 0.0), errors="coerce").fillna(0.0).gt(0), "breakout_yes", "breakout_no")
    for column in FEATURE_COLUMNS:
        data[column] = data[column].fillna("missing").astype(str)
    return data


def _scope_summary(labeled: pd.DataFrame) -> pd.DataFrame:
    data = labeled.copy()
    rows: list[dict[str, Any]] = []
    scopes = {
        "official_all_candidates": pd.Series(True, index=data.index),
        "base_floor_01_passed": data["base_floor_01"] & data["passed_initial_filter_bool"],
        "base_floor_01_ai_allowed": data["base_floor_01"] & data["passed_initial_filter_bool"] & data["ai_allowed_bool"],
        "actionable_throttle": data["actionable_throttle"],
    }
    for name, mask in scopes.items():
        group = data[mask].copy()
        rows.append(
            {
                "scope": name,
                "rows": int(len(group)),
                "opened": int(group["status_scope"].eq("opened").sum()),
                "sizing_zero_volume": int(group["status_scope"].eq("sizing_zero_volume").sum()),
                "ai_blocked": int(group["status_scope"].eq("ai_blocked").sum()),
                "short_rejected": int(group["status_scope"].eq("short_rejected").sum()),
                "labeled_h40_ok": int(group["h40_label_status"].eq("ok").sum()) if "h40_label_status" in group.columns else 0,
                "h40_good_rate": float(group.loc[group["h40_label_status"].eq("ok"), "h40_barrier_good"].mean())
                if "h40_label_status" in group.columns and group["h40_label_status"].eq("ok").any()
                else np.nan,
                "h40_avg_path_score_r": float(group.loc[group["h40_label_status"].eq("ok"), "h40_path_score_r"].mean())
                if "h40_label_status" in group.columns and group["h40_label_status"].eq("ok").any()
                else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _train_feature_quality(train: pd.DataFrame, target_col: str = "h40_barrier_good") -> pd.DataFrame:
    base_mean = float(pd.to_numeric(train[target_col], errors="coerce").mean())
    rows: list[dict[str, Any]] = []
    for feature in FEATURE_COLUMNS:
        for value, group in train.groupby(feature, dropna=False):
            count = int(len(group))
            raw_rate = float(pd.to_numeric(group[target_col], errors="coerce").mean())
            score = (raw_rate * count + base_mean * SHRINKAGE_ROWS) / (count + SHRINKAGE_ROWS)
            rows.append(
                {
                    "feature": feature,
                    "feature_value": str(value),
                    "train_rows": count,
                    "train_good_rate": raw_rate,
                    "global_good_rate": base_mean,
                    "shrunk_quality_score": float(score),
                    "lift_vs_global": float(score - base_mean),
                }
            )
    return pd.DataFrame(rows)


def _score_with_feature_table(test: pd.DataFrame, table: pd.DataFrame, global_score: float) -> pd.Series:
    lookup = {
        (str(row.feature), str(row.feature_value)): float(row.shrunk_quality_score)
        for row in table.itertuples(index=False)
    }
    scores: list[float] = []
    for _, row in test.iterrows():
        pieces = []
        for feature in FEATURE_COLUMNS:
            pieces.append(lookup.get((feature, str(row.get(feature))), global_score))
        scores.append(float(np.mean(pieces)) if pieces else float(global_score))
    return pd.Series(scores, index=test.index)


def _assign_buckets(scores: pd.Series) -> pd.Series:
    clean = pd.to_numeric(scores, errors="coerce")
    if clean.nunique(dropna=True) < 3:
        ranks = clean.rank(method="first")
        tertile = pd.qcut(ranks, q=min(3, len(ranks)), labels=False, duplicates="drop")
    else:
        tertile = pd.qcut(clean, q=3, labels=False, duplicates="drop")
    mapping = {0: "low", 1: "mid", 2: "high"}
    return tertile.map(mapping).fillna("unbucketed").astype(str)


def _walkforward_quality(labeled: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    universe = labeled[
        labeled["actionable_throttle"]
        & labeled["h40_label_status"].eq("ok")
        & labeled["h20_label_status"].eq("ok")
    ].copy()
    universe = universe.sort_values("date").reset_index(drop=True)
    if universe.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    scored_frames: list[pd.DataFrame] = []
    feature_tables: list[pd.DataFrame] = []
    for test_year in sorted(int(year) for year in universe["year"].dropna().unique()):
        test_start = pd.Timestamp(f"{test_year}-01-01")
        train_cutoff = test_start - pd.Timedelta(days=EMBARGO_DAYS)
        train = universe[universe["date"].le(train_cutoff)].copy()
        test = universe[universe["year"].eq(test_year)].copy()
        if len(train) < MIN_TRAIN_ROWS or len(test) < MIN_TEST_ROWS:
            continue
        table = _train_feature_quality(train)
        global_score = float(pd.to_numeric(train["h40_barrier_good"], errors="coerce").mean())
        test["quality_score_wf"] = _score_with_feature_table(test, table, global_score)
        test["quality_bucket_wf"] = _assign_buckets(test["quality_score_wf"])
        test["test_year"] = test_year
        table["test_year"] = test_year
        table["train_start"] = train["date"].min().date().isoformat()
        table["train_end"] = train["date"].max().date().isoformat()
        table["test_rows"] = int(len(test))
        scored_frames.append(test)
        feature_tables.append(table)

    scored = pd.concat(scored_frames, ignore_index=True) if scored_frames else pd.DataFrame()
    features = pd.concat(feature_tables, ignore_index=True) if feature_tables else pd.DataFrame()
    if scored.empty:
        return scored, features, pd.DataFrame()

    scored["h40_big_winner"] = pd.to_numeric(scored["h40_mfe_r"], errors="coerce").ge(3.0).astype(int)
    summary = (
        scored.groupby(["test_year", "quality_bucket_wf"], sort=True)
        .agg(
            rows=("candidate_index", "size"),
            opened=("status_scope", lambda series: int(series.eq("opened").sum())),
            sizing_zero_volume=("status_scope", lambda series: int(series.eq("sizing_zero_volume").sum())),
            h20_good_rate=("h20_barrier_good", "mean"),
            h40_good_rate=("h40_barrier_good", "mean"),
            h40_bad_rate=("h40_barrier_bad", "mean"),
            avg_h40_mfe_r=("h40_mfe_r", "mean"),
            avg_h40_mae_r=("h40_mae_r", "mean"),
            avg_h40_path_score_r=("h40_path_score_r", "mean"),
            big_winner_count=("h40_big_winner", "sum"),
            avg_quality_score=("quality_score_wf", "mean"),
        )
        .reset_index()
    )
    return scored, features, summary


def _product_concentration(scored: pd.DataFrame) -> pd.DataFrame:
    if scored.empty:
        return pd.DataFrame()
    high = scored[scored["quality_bucket_wf"].eq("high")].copy()
    if high.empty:
        return pd.DataFrame()
    concentration = (
        high.groupby(["product", "direction"], sort=True)
        .agg(
            rows=("candidate_index", "size"),
            h40_good_rate=("h40_barrier_good", "mean"),
            avg_h40_path_score_r=("h40_path_score_r", "mean"),
            big_winner_count=("h40_big_winner", "sum"),
        )
        .reset_index()
    )
    concentration["row_share"] = concentration["rows"] / max(float(len(high)), 1.0)
    return concentration.sort_values(["rows", "avg_h40_path_score_r"], ascending=[False, False]).reset_index(drop=True)


def _decision(scored: pd.DataFrame, bucket_summary: pd.DataFrame, product_concentration: pd.DataFrame) -> dict[str, Any]:
    if scored.empty or bucket_summary.empty:
        return {
            "decision": "throttled_quality_selector_not_ready",
            "reason": "walkforward sample is too small after embargo/min-row gates",
            "promote_to_strategy_backtest": False,
        }
    wide_rows: list[dict[str, Any]] = []
    for year, group in bucket_summary.groupby("test_year", sort=True):
        high = group[group["quality_bucket_wf"].eq("high")]
        low = group[group["quality_bucket_wf"].eq("low")]
        if high.empty or low.empty:
            continue
        high_row = high.iloc[0]
        low_row = low.iloc[0]
        wide_rows.append(
            {
                "test_year": int(year),
                "high_rows": int(high_row["rows"]),
                "low_rows": int(low_row["rows"]),
                "good_rate_delta": float(high_row["h40_good_rate"] - low_row["h40_good_rate"]),
                "path_score_delta": float(high_row["avg_h40_path_score_r"] - low_row["avg_h40_path_score_r"]),
            }
        )
    comparison = pd.DataFrame(wide_rows)
    years = int(len(comparison))
    good_years = int(comparison["good_rate_delta"].gt(0.10).sum()) if not comparison.empty else 0
    path_years = int(comparison["path_score_delta"].gt(0.0).sum()) if not comparison.empty else 0
    sample_rows = int(len(scored))
    high_rows = int(scored["quality_bucket_wf"].eq("high").sum())
    high_share = float(high_rows / sample_rows) if sample_rows else 0.0
    high_big_winners = int(scored.loc[scored["quality_bucket_wf"].eq("high"), "h40_big_winner"].sum())
    all_big_winners = int(scored["h40_big_winner"].sum())
    high_big_winner_capture = float(high_big_winners / all_big_winners) if all_big_winners else 0.0
    max_product_share = float(product_concentration["row_share"].max()) if not product_concentration.empty else 1.0

    gates = {
        "sample_rows_ge_120": sample_rows >= 120,
        "walkforward_years_ge_4": years >= 4,
        "high_good_rate_beats_low_by_10pp_in_3_years": good_years >= 3,
        "high_path_score_beats_low_in_3_years": path_years >= 3,
        "high_bucket_not_overconcentrated": max_product_share <= 0.35,
        "high_bucket_captures_big_winners": high_big_winner_capture >= max(high_share, 0.40),
    }
    promote = all(gates.values())
    return {
        "decision": "throttled_quality_selector_backtest_candidate" if promote else "throttled_quality_selector_not_promoted",
        "promote_to_strategy_backtest": bool(promote),
        "gates": gates,
        "sample_rows": sample_rows,
        "high_rows": high_rows,
        "high_share": high_share,
        "walkforward_years": years,
        "good_years": good_years,
        "path_years": path_years,
        "high_big_winner_capture": high_big_winner_capture,
        "max_high_product_share": max_product_share,
        "year_delta": comparison.to_dict(orient="records"),
    }


def _plot_bucket_summary(bucket_summary: pd.DataFrame) -> None:
    if bucket_summary.empty:
        return
    order = ["low", "mid", "high"]
    years = sorted(bucket_summary["test_year"].unique())
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    x = np.arange(len(years))
    width = 0.25
    colors = {"low": "#d55e00", "mid": "#0072b2", "high": "#009e73"}
    for idx, bucket in enumerate(order):
        group = bucket_summary[bucket_summary["quality_bucket_wf"].eq(bucket)].set_index("test_year")
        vals_good = [float(group.loc[year, "h40_good_rate"]) if year in group.index else np.nan for year in years]
        vals_path = [float(group.loc[year, "avg_h40_path_score_r"]) if year in group.index else np.nan for year in years]
        axes[0].bar(x + (idx - 1) * width, vals_good, width=width, label=bucket, color=colors[bucket], alpha=0.85)
        axes[1].bar(x + (idx - 1) * width, vals_path, width=width, label=bucket, color=colors[bucket], alpha=0.85)
    axes[0].set_ylabel("H40 +2R first rate")
    axes[1].set_ylabel("H40 MFE-MAE (R)")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([str(year) for year in years])
    for ax in axes:
        ax.grid(True, axis="y", alpha=0.25)
        ax.legend(loc="best")
    fig.suptitle("Stage716 read-only quality buckets for official 0.1-throttled actionable candidates")
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    *,
    scope_summary: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    feature_quality: pd.DataFrame,
    product_concentration: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    top_features = pd.DataFrame()
    if not feature_quality.empty:
        latest_year = int(feature_quality["test_year"].max())
        top_features = (
            feature_quality[feature_quality["test_year"].eq(latest_year)]
            .sort_values(["lift_vs_global", "train_rows"], ascending=[False, False])
            .head(20)
            .copy()
        )
    lines = [
        "# Stage716 正式版 0.1 连败档高质量机会只读审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- line_id：`{LINE_ID}`",
        f"- 基准变体：`{BASE_VARIANT}`",
        f"- 数据来源：`{SOURCE_CANDIDATES_PATH.name}`",
        f"- 决策：`{decision.get('decision')}`",
        f"- 是否进入策略回测：`{decision.get('promote_to_strategy_backtest')}`",
        "",
        "## 方法",
        "",
        (
            "- 只读读取 Stage696 的正式版候选快照，不改正式配置、不连接 CTP、不下单。"
            "候选若处于 `streak_entry_structure_risk_recovery_base_multiplier<=0.1` 或 `loss_streak>=3`，"
            "且通过初筛与 AI 池、状态为已开仓或 `sizing_zero_volume`，定义为本次可行动的 0.1 风险档样本。"
        ),
        (
            f"- 对每个候选使用同一合约后续 `{HORIZONS[0]}/{HORIZONS[1]}` 个交易日 high/low 标注路径，"
            f"保守判断先触及 `+{FAVORABLE_R:.0f}R` 还是 `-{ADVERSE_R:.0f}R`；同日同时触发按不利先到处理。"
        ),
        (
            "- 质量打分只用候选当时已知字段的粗桶：方向、信号、AI rank 桶、RSI 方向确认、同向相关、账户回撤、"
            "已有持仓、风险/止损尺度等；按年份滚动训练，测试年只用以前年度，前 40 天 embargo。"
        ),
        "",
        "## 样本范围",
        "",
        _md_table(scope_summary, 20),
        "",
        "## Walk-forward 分桶结果",
        "",
        _md_table(bucket_summary, 40),
        "",
        "## 最新训练窗强特征",
        "",
        _md_table(top_features, 20),
        "",
        "## high 桶产品集中度",
        "",
        _md_table(product_concentration, 30),
        "",
        "## 闸门",
        "",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "",
        "## 解释",
        "",
        (
            "- 这个审计不是用真实交易 PnL 回看打标签，而是用候选入场后的固定路径标签；"
            "它能判断候选形态有没有事前可识别的路径质量，但不能替代真实策略回测。"
        ),
        (
            "- 若 high 桶不能在多年度稳定领先 low 桶，或样本集中在少数品种，就不应该把它接入正式版；"
            "否则很容易变成针对 2025 红框右尾的形态补丁。"
        ),
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = _load_official_candidates()
    labeled = _add_feature_buckets(_label_candidates(candidates))
    scope_summary = _scope_summary(labeled)
    scored, feature_quality, bucket_summary = _walkforward_quality(labeled)
    product_concentration = _product_concentration(scored)
    decision = _decision(scored, bucket_summary, product_concentration)

    labeled.to_csv(LABELED_PATH, index=False, encoding="utf-8-sig")
    scope_summary.to_csv(SCOPE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    feature_quality.to_csv(FEATURE_QUALITY_PATH, index=False, encoding="utf-8-sig")
    scored.to_csv(WALKFORWARD_PATH, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(BUCKET_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product_concentration.to_csv(PRODUCT_CONCENTRATION_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot_bucket_summary(bucket_summary)
    _write_report(
        scope_summary=scope_summary,
        bucket_summary=bucket_summary,
        feature_quality=feature_quality,
        product_concentration=product_concentration,
        decision=decision,
    )

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")
    print(f"labeled={LABELED_PATH}")
    print(f"chart={CHART_PATH if CHART_PATH.exists() else ''}")


if __name__ == "__main__":
    main()
