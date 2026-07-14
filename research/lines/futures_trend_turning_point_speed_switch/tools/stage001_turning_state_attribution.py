#!/usr/bin/env python3
"""Strict T-1 turning-state attribution for the frozen current-C9 path."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_turning_point_speed_switch"
STAGE_ID = "stage001_turning_state_attribution"
MODEL_TAG = f"{STAGE_ID}_v1"
LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / STAGE_ID
TOOL_PATH = Path(__file__).resolve()

MRC_OUT = (
    ROOT
    / "research"
    / "lines"
    / "futures_trend_candidate_marginal_risk_contribution"
    / "outputs"
    / "stage001_candidate_marginal_risk_contribution_engine"
)
PREFIX = "candidate_mrc_stage001_candidate_marginal_risk_contribution_engine"
SUFFIX = "stage001_candidate_marginal_risk_contribution_engine_v1"
DAILY_PATH = MRC_OUT / f"{PREFIX}_202001_a_daily_{SUFFIX}.csv.gz"
TRADES_PATH = MRC_OUT / f"{PREFIX}_202001_a_trades_{SUFFIX}.csv.gz"
POSITIONS_PATH = MRC_OUT / f"{PREFIX}_202001_a_positions_{SUFFIX}.csv.gz"
CANDIDATES_PATH = MRC_OUT / f"{PREFIX}_202001_a_entry_candidates_{SUFFIX}.csv.gz"
PANEL_PATH = MRC_OUT / f"{PREFIX}_actual_contract_returns_{SUFFIX}.csv"

EXPECTED_INPUT_SHA256 = {
    DAILY_PATH: "c4b0615dd3b1aca78385b07265b3dbf049f17e7be6a537ac455302c0ef4ca2c3",
    TRADES_PATH: "99308e60f2eca5976c9e6faa6110f4255698028c09a8a9c07b4452fb83950907",
    POSITIONS_PATH: "eed8341159215b5f9e473294b7df3eccfb930fb2cd04531d8aa876fbb4719a39",
    CANDIDATES_PATH: "fba876eb645b1b0488bd30ac60e2c3c98d471ffcf91fb9490cd189352c8f45e1",
    PANEL_PATH: "f7309d2ea3709731c2cbcebd8bf6b57e92309ec20367a885426421da86b04da9",
}
EXPECTED_ROWS = {
    DAILY_PATH: 1_571,
    TRADES_PATH: 641,
    POSITIONS_PATH: 470_965,
    CANDIDATES_PATH: 839,
    PANEL_PATH: 116_445,
}

PREDECL_PATH = (
    LINE_DIR / "stages" / "20260712_2122_stage001_turning_state_attribution_predecl.md"
)
IMPLEMENTATION_PLAN_PATH = (
    LINE_DIR / "stages" / "20260712_2123_stage001_turning_state_attribution_implementation_plan.md"
)
TEST_PATH = ROOT / "tests" / "test_turning_point_speed_switch_stage001.py"

SOURCE_MANIFEST_PATH = OUT / f"{MODEL_TAG}_source_manifest.csv"
CODE_MANIFEST_PATH = OUT / f"{MODEL_TAG}_code_manifest.csv"
DATA_AUDIT_PATH = OUT / f"{MODEL_TAG}_data_audit.json"
PRODUCT_DAYS_PATH = OUT / f"{MODEL_TAG}_product_days.csv.gz"
STATE_ROWS_PATH = OUT / f"{MODEL_TAG}_position_state_rows.csv.gz"
EVENTS_PATH = OUT / f"{MODEL_TAG}_opposite_events.csv"
REFERENCES_PATH = OUT / f"{MODEL_TAG}_concordant_references.csv"
STATE_SUMMARY_PATH = OUT / f"{MODEL_TAG}_state_summary.csv"
EVENT_SUMMARY_PATH = OUT / f"{MODEL_TAG}_event_summary.csv"
GATES_PATH = OUT / f"{MODEL_TAG}_gate_matrix.csv"
DECISION_PATH = OUT / f"{MODEL_TAG}_decision.json"
REPORT_PATH = OUT / f"{MODEL_TAG}_report.md"

FAST_PERIODS = (3, 6, 12, 24)
SLOW_PERIODS = (5, 10, 20, 40)
MAX_LOOKBACK = 40
HORIZONS = (1, 5, 20)
BOOTSTRAP_SEED = 20_260_712
BOOTSTRAP_ITERATIONS = 20_000
BASELINE_VARIANT = "current_official_ai_c9_control"
FREEZE_END = pd.Timestamp("2026-06-29")

SEGMENTS = ("2018-2020", "2021-2023", "2024-freeze")
CONTRACT_PATTERN = re.compile(r"^([A-Za-z]+)[0-9]+\.([A-Za-z0-9_]+)$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_snapshot(path: Path) -> dict[str, Any]:
    source = Path(path)
    resolved = source.resolve(strict=True)
    if source.is_symlink() or resolved.is_symlink():
        raise RuntimeError(f"symlink input is forbidden: {source}")
    stat = resolved.stat()
    return {
        "path": str(resolved),
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "sha256": sha256_file(resolved),
    }


def capture_manifest(paths: Iterable[Path]) -> pd.DataFrame:
    rows = [file_snapshot(path) for path in sorted({Path(item) for item in paths}, key=str)]
    return pd.DataFrame(rows, columns=["path", "size", "mtime_ns", "sha256"])


def validate_frozen_inputs() -> pd.DataFrame:
    if PANEL_PATH.suffix != ".csv" or PANEL_PATH.name.endswith(".csv.gz"):
        raise RuntimeError("the stale gzip return panel is forbidden")
    manifest = capture_manifest(EXPECTED_INPUT_SHA256)
    expected = {str(path.resolve()): value for path, value in EXPECTED_INPUT_SHA256.items()}
    manifest["expected_sha256"] = manifest["path"].map(expected)
    manifest["sha256_match"] = manifest["sha256"].eq(manifest["expected_sha256"]).astype(int)
    if not manifest["sha256_match"].eq(1).all():
        bad = manifest.loc[
            manifest["sha256_match"].eq(0), ["path", "sha256", "expected_sha256"]
        ]
        raise RuntimeError(f"frozen input SHA mismatch:\n{bad.to_string(index=False)}")
    return manifest


def _normalise_date_column(frame: pd.DataFrame, column: str = "date") -> pd.DataFrame:
    result = frame.copy()
    result[column] = pd.to_datetime(result[column], errors="raise").dt.tz_localize(None).dt.normalize()
    return result


def truncate_analysis_frames(
    frames: dict[str, pd.DataFrame], freeze_end: pd.Timestamp = FREEZE_END
) -> dict[str, pd.DataFrame]:
    cutoff = pd.Timestamp(freeze_end).tz_localize(None).normalize()
    result: dict[str, pd.DataFrame] = {}
    for name, frame in frames.items():
        if "date" not in frame.columns:
            raise RuntimeError(f"analysis frame has no date column: {name}")
        data = _normalise_date_column(frame)
        data = data[data["date"].le(cutoff)].copy().reset_index(drop=True)
        if data.empty or data["date"].max() > cutoff:
            raise RuntimeError(f"failed to truncate analysis frame: {name}")
        result[name] = data
    return result


def validate_cross_day_position_conservation(
    positions: pd.DataFrame,
    *,
    market_dates: Iterable[Any],
) -> dict[str, int]:
    required = {"date", "vt_symbol", "start_pos", "end_pos"}
    missing = required.difference(positions.columns)
    if missing:
        raise RuntimeError(f"cross-day position schema missing: {sorted(missing)}")
    data = _normalise_date_column(positions).sort_values(["vt_symbol", "date"]).copy()
    dates = pd.DatetimeIndex(pd.to_datetime(list(market_dates))).tz_localize(None).normalize().unique().sort_values()
    previous_date = {dates[index]: dates[index - 1] for index in range(1, len(dates))}
    next_date = {dates[index]: dates[index + 1] for index in range(len(dates) - 1)}
    data["previous_row_date"] = data.groupby("vt_symbol")["date"].shift(1)
    data["previous_end_pos"] = data.groupby("vt_symbol")["end_pos"].shift(1)
    data["next_row_date"] = data.groupby("vt_symbol")["date"].shift(-1)
    data["expected_previous_date"] = data["date"].map(previous_date)
    data["expected_next_date"] = data["date"].map(next_date)
    consecutive = data["previous_row_date"].eq(data["expected_previous_date"])
    checked = data[consecutive]
    mismatched_value = checked[
        ~np.isclose(
            pd.to_numeric(checked["start_pos"], errors="raise"),
            pd.to_numeric(checked["previous_end_pos"], errors="raise"),
            atol=1e-9,
        )
    ]
    missing_prior = data[
        data["start_pos"].ne(0)
        & data["expected_previous_date"].notna()
        & ~consecutive
    ]
    missing_next = data[
        data["end_pos"].ne(0)
        & data["expected_next_date"].notna()
        & ~data["next_row_date"].eq(data["expected_next_date"])
    ]
    if not mismatched_value.empty or not missing_prior.empty or not missing_next.empty:
        raise RuntimeError(
            "cross-day position conservation failed: "
            f"value={len(mismatched_value)} prior={len(missing_prior)} next={len(missing_next)}"
        )
    return {
        "cross_day_checked_rows": len(checked),
        "cross_day_value_mismatches": 0,
        "cross_day_missing_prior_rows": 0,
        "cross_day_missing_next_rows": 0,
    }


def contract_to_product(contract: str) -> str:
    match = CONTRACT_PATTERN.fullmatch(str(contract))
    if not match:
        raise ValueError(f"invalid concrete contract: {contract}")
    return f"{match.group(1)}.{match.group(2)}"


def segment_for_date(value: Any) -> str:
    year = pd.Timestamp(value).year
    if year <= 2020:
        return "2018-2020"
    if year <= 2023:
        return "2021-2023"
    return "2024-freeze"


def half_release(volume: int) -> tuple[int, int]:
    value = int(volume)
    if value < 0 or float(volume) != value:
        raise ValueError("volume must be a non-negative integer")
    retained = int(math.ceil(value * 0.5))
    return retained, value - retained


def _classify_alignment(values: dict[int, float], periods: tuple[int, ...]) -> int:
    ordered = [float(values[period]) for period in periods]
    if all(left > right for left, right in zip(ordered, ordered[1:])):
        return 1
    if all(left < right for left, right in zip(ordered, ordered[1:])):
        return -1
    return 0


def _state_from_close_series(
    close_series: pd.Series,
    *,
    expected_dates: pd.DatetimeIndex,
    action_date: pd.Timestamp,
    position_direction: int,
) -> dict[str, Any]:
    if position_direction not in (-1, 1):
        raise ValueError("position direction must be -1 or 1")
    historical = close_series.reindex(expected_dates)
    if historical.isna().any():
        available_before = int(close_series.index.to_series().lt(action_date).sum())
        reason = "insufficient_history" if available_before < MAX_LOOKBACK else "nonconsecutive_history"
        return {
            "available": 0,
            "reason": reason,
            "asof_date": pd.NaT,
            "slow_aligned": 0,
            "fast_relation": "unavailable",
        }
    values = historical.astype(float).to_numpy()
    if len(values) != MAX_LOOKBACK or not np.isfinite(values).all() or (values <= 0.0).any():
        raise ValueError("invalid exact close history")
    ma_values = {
        period: float(values[-period:].mean())
        for period in sorted(set(FAST_PERIODS).union(SLOW_PERIODS))
    }
    fast_direction = _classify_alignment(ma_values, FAST_PERIODS)
    slow_direction = _classify_alignment(ma_values, SLOW_PERIODS)
    if fast_direction == position_direction:
        fast_relation = "concordant"
    elif fast_direction == -position_direction:
        fast_relation = "opposite"
    else:
        fast_relation = "neutral"
    digest_payload = "\n".join(
        f"{date.date().isoformat()}|{value:.12g}"
        for date, value in zip(expected_dates, values, strict=True)
    ).encode("ascii")
    result: dict[str, Any] = {
        "available": 1,
        "reason": "available",
        "asof_date": expected_dates[-1],
        "history_start": expected_dates[0],
        "history_end": expected_dates[-1],
        "history_count": MAX_LOOKBACK,
        "history_sha256": hashlib.sha256(digest_payload).hexdigest(),
        "fast_direction": fast_direction,
        "slow_direction": slow_direction,
        "slow_aligned": int(slow_direction == position_direction),
        "fast_relation": fast_relation,
    }
    result.update({f"ma{period}": value for period, value in ma_values.items()})
    return result


def prepare_close_index(panel: pd.DataFrame) -> dict[str, pd.Series]:
    required = {"date", "contract_vt_symbol", "close"}
    missing = required.difference(panel.columns)
    if missing:
        raise ValueError(f"close panel schema missing: {sorted(missing)}")
    data = _normalise_date_column(panel)
    if data.duplicated(["date", "contract_vt_symbol"]).any():
        raise ValueError("duplicate close panel key")
    data["close"] = pd.to_numeric(data["close"], errors="raise").astype(float)
    if (~np.isfinite(data["close"]) | data["close"].le(0.0)).any():
        raise ValueError("invalid close panel values")
    return {
        str(contract): group.sort_values("date").set_index("date")["close"]
        for contract, group in data.groupby("contract_vt_symbol", sort=False)
    }


def compute_t1_ma_state(
    panel: pd.DataFrame,
    *,
    contract: str,
    action_date: Any,
    market_dates: Iterable[Any],
    position_direction: int,
) -> dict[str, Any]:
    dates = pd.DatetimeIndex(pd.to_datetime(list(market_dates))).tz_localize(None).normalize().unique().sort_values()
    action = pd.Timestamp(action_date).tz_localize(None).normalize()
    matches = np.flatnonzero(dates == action)
    if len(matches) != 1:
        return {
            "available": 0,
            "reason": "action_date_not_in_market_calendar",
            "asof_date": pd.NaT,
            "slow_aligned": 0,
            "fast_relation": "unavailable",
        }
    action_index = int(matches[0])
    if action_index < MAX_LOOKBACK:
        return {
            "available": 0,
            "reason": "insufficient_history",
            "asof_date": pd.NaT,
            "slow_aligned": 0,
            "fast_relation": "unavailable",
        }
    close_index = prepare_close_index(panel)
    series = close_index.get(str(contract))
    if series is None:
        return {
            "available": 0,
            "reason": "missing_contract",
            "asof_date": pd.NaT,
            "slow_aligned": 0,
            "fast_relation": "unavailable",
        }
    return _state_from_close_series(
        series,
        expected_dates=dates[action_index - MAX_LOOKBACK : action_index],
        action_date=action,
        position_direction=position_direction,
    )


def mark_primary_events(rows: pd.DataFrame, *, market_dates: Iterable[Any]) -> pd.DataFrame:
    required = {
        "action_date",
        "episode_id",
        "actual_contract",
        "feature_available",
        "slow_aligned",
        "fast_relation",
    }
    missing = required.difference(rows.columns)
    if missing:
        raise ValueError(f"state rows schema missing: {sorted(missing)}")
    data = _normalise_date_column(rows, "action_date").sort_values(
        ["episode_id", "action_date", "actual_contract"]
    ).reset_index(drop=True)
    dates = pd.DatetimeIndex(pd.to_datetime(list(market_dates))).tz_localize(None).normalize().unique().sort_values()
    calendar_index = {date: index for index, date in enumerate(dates)}
    if not set(data["action_date"]).issubset(calendar_index):
        raise ValueError("state action date is outside market calendar")
    data["calendar_index"] = data["action_date"].map(calendar_index).astype(int)
    data["date_block20"] = (data["calendar_index"] // 20).astype(int)
    data["contract_first_state"] = 0
    data["is_primary_event"] = 0
    for _, indices in data.groupby("episode_id", sort=False).groups.items():
        previous_index: int | None = None
        opposite_seen = False
        for index in list(indices):
            current = data.loc[index]
            contract_first = previous_index is None
            if previous_index is not None:
                previous = data.loc[previous_index]
                contract_first = bool(
                    current["actual_contract"] != previous["actual_contract"]
                    or int(current["calendar_index"]) != int(previous["calendar_index"]) + 1
                )
            data.loc[index, "contract_first_state"] = int(contract_first)
            qualifying_opposite = bool(
                int(current["feature_available"]) == 1
                and int(current["slow_aligned"]) == 1
                and current["fast_relation"] == "opposite"
            )
            if qualifying_opposite and not opposite_seen and not contract_first and previous_index is not None:
                previous = data.loc[previous_index]
                prior_is_usable = bool(
                    int(previous["feature_available"]) == 1
                    and previous["actual_contract"] == current["actual_contract"]
                    and previous["fast_relation"] != "opposite"
                )
                if prior_is_usable:
                    data.loc[index, "is_primary_event"] = 1
            if qualifying_opposite:
                opposite_seen = True
            previous_index = index
    return data


def pigeonhole_bootstrap_mean_difference(
    frame: pd.DataFrame,
    *,
    iterations: int = BOOTSTRAP_ITERATIONS,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, float | int]:
    required = {"product", "date_block20", "group", "outcome"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"bootstrap schema missing: {sorted(missing)}")
    data = frame.dropna(subset=list(required)).copy()
    groups = set(data["group"].astype(str))
    if groups != {"opposite", "concordant"}:
        raise ValueError("bootstrap requires opposite and concordant groups")
    products = sorted(data["product"].astype(str).unique())
    blocks = sorted(data["date_block20"].astype(int).unique())
    if len(products) < 2:
        raise ValueError("bootstrap requires at least two products")
    if len(blocks) < 2:
        raise ValueError("bootstrap requires at least two date blocks")
    product_index = {value: index for index, value in enumerate(products)}
    block_index = {value: index for index, value in enumerate(blocks)}
    pidx = data["product"].astype(str).map(product_index).to_numpy(dtype=int)
    bidx = data["date_block20"].astype(int).map(block_index).to_numpy(dtype=int)
    values = pd.to_numeric(data["outcome"], errors="raise").to_numpy(dtype=float)
    is_opposite = data["group"].astype(str).eq("opposite").to_numpy()
    point = float(values[is_opposite].mean() - values[~is_opposite].mean())
    rng = np.random.default_rng(seed)
    probabilities_p = np.full(len(products), 1.0 / len(products))
    probabilities_b = np.full(len(blocks), 1.0 / len(blocks))
    draws: list[float] = []
    for _ in range(int(iterations)):
        product_counts = rng.multinomial(len(products), probabilities_p)
        block_counts = rng.multinomial(len(blocks), probabilities_b)
        weights = product_counts[pidx] * block_counts[bidx]
        opposite_weight = float(weights[is_opposite].sum())
        concordant_weight = float(weights[~is_opposite].sum())
        if opposite_weight <= 0.0 or concordant_weight <= 0.0:
            continue
        opposite_mean = float(np.dot(weights[is_opposite], values[is_opposite]) / opposite_weight)
        concordant_mean = float(np.dot(weights[~is_opposite], values[~is_opposite]) / concordant_weight)
        draws.append(opposite_mean - concordant_mean)
    minimum_valid = max(100, int(iterations * 0.8))
    if len(draws) < minimum_valid:
        raise RuntimeError(f"too few valid pigeonhole draws: {len(draws)} < {minimum_valid}")
    lower, upper = np.quantile(np.asarray(draws), [0.025, 0.975])
    return {
        "point_difference": point,
        "ci95_lower": float(lower),
        "ci95_upper": float(upper),
        "valid_iterations": len(draws),
        "requested_iterations": int(iterations),
        "product_count": len(products),
        "date_block_count": len(blocks),
        "seed": int(seed),
    }


def pigeonhole_bootstrap_total_lower_bound(
    frame: pd.DataFrame,
    *,
    value_column: str,
    iterations: int = BOOTSTRAP_ITERATIONS,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, float | int]:
    required = {"product", "date_block20", value_column}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"one-sample bootstrap schema missing: {sorted(missing)}")
    data = frame.dropna(subset=list(required)).copy()
    products = sorted(data["product"].astype(str).unique())
    blocks = sorted(data["date_block20"].astype(int).unique())
    if len(products) < 2 or len(blocks) < 2 or len(data) < 2:
        raise ValueError("one-sample bootstrap needs two products, two blocks and two rows")
    product_index = {value: index for index, value in enumerate(products)}
    block_index = {value: index for index, value in enumerate(blocks)}
    pidx = data["product"].astype(str).map(product_index).to_numpy(dtype=int)
    bidx = data["date_block20"].astype(int).map(block_index).to_numpy(dtype=int)
    values = pd.to_numeric(data[value_column], errors="raise").to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    probabilities_p = np.full(len(products), 1.0 / len(products))
    probabilities_b = np.full(len(blocks), 1.0 / len(blocks))
    draws: list[float] = []
    for _ in range(int(iterations)):
        product_counts = rng.multinomial(len(products), probabilities_p)
        block_counts = rng.multinomial(len(blocks), probabilities_b)
        weights = product_counts[pidx] * block_counts[bidx]
        weight_sum = float(weights.sum())
        if weight_sum <= 0.0:
            continue
        draws.append(float(np.dot(weights, values) / weight_sum * len(values)))
    minimum_valid = max(100, int(iterations * 0.8))
    if len(draws) < minimum_valid:
        raise RuntimeError(f"too few valid one-sample draws: {len(draws)} < {minimum_valid}")
    lower, upper = np.quantile(np.asarray(draws), [0.025, 0.975])
    return {
        "point_total": float(values.sum()),
        "ci95_lower_total": float(lower),
        "ci95_upper_total": float(upper),
        "valid_iterations": len(draws),
        "requested_iterations": int(iterations),
        "seed": int(seed),
    }


def mechanical_canary_decision(gates: pd.DataFrame) -> bool:
    required = {"gate", "passed", "detail"}
    missing = required.difference(gates.columns)
    if missing or gates.empty:
        raise ValueError(f"gate matrix schema missing or empty: {sorted(missing)}")
    if gates["gate"].astype(str).duplicated().any():
        raise ValueError("gate names must be unique")
    values = pd.to_numeric(gates["passed"], errors="raise").astype(int)
    if not values.isin([0, 1]).all():
        raise ValueError("gate pass values must be binary")
    return bool(values.eq(1).all())


def load_frozen_frames() -> dict[str, pd.DataFrame]:
    frames = {
        "daily": pd.read_csv(DAILY_PATH, encoding="utf-8-sig"),
        "trades": pd.read_csv(TRADES_PATH, encoding="utf-8-sig"),
        "positions": pd.read_csv(POSITIONS_PATH, encoding="utf-8-sig"),
        "candidates": pd.read_csv(CANDIDATES_PATH, encoding="utf-8-sig"),
        "panel": pd.read_csv(PANEL_PATH, encoding="utf-8-sig"),
    }
    for path, frame in zip(
        (DAILY_PATH, TRADES_PATH, POSITIONS_PATH, CANDIDATES_PATH, PANEL_PATH),
        frames.values(),
        strict=True,
    ):
        expected = EXPECTED_ROWS[path]
        if len(frame) != expected:
            raise RuntimeError(f"frozen row count mismatch for {path}: {len(frame)} != {expected}")
    return frames


def validate_baseline_frames(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    daily = _normalise_date_column(frames["daily"])
    trades = _normalise_date_column(frames["trades"])
    positions = _normalise_date_column(frames["positions"])
    candidates = _normalise_date_column(frames["candidates"])
    panel = _normalise_date_column(frames["panel"])
    required = {
        "daily": {"date", "net_pnl", "trade_count", "slippage", "variant", "account_equity"},
        "trades": {"date", "vt_symbol", "direction", "offset", "price", "volume", "signed_volume", "trade_id"},
        "positions": {
            "date",
            "vt_symbol",
            "start_pos",
            "end_pos",
            "pos_change",
            "trade_count",
            "commission",
            "slippage",
            "net_pnl",
            "close_price",
        },
        "candidates": {
            "date",
            "candidate_index",
            "product_vt_symbol",
            "contract_vt_symbol",
            "direction",
            "candidate_status",
            "target_risk_amount",
            "stop_distance",
            "size",
            "selected_volume",
        },
        "panel": {"date", "contract_vt_symbol", "close", "return_valid", "source"},
    }
    for name, columns in required.items():
        missing = columns.difference(frames[name].columns)
        if missing:
            raise RuntimeError(f"{name} schema missing: {sorted(missing)}")
    if set(daily["variant"].astype(str)) != {BASELINE_VARIANT}:
        raise RuntimeError("daily baseline identity mismatch")
    if positions.duplicated(["date", "vt_symbol"]).any():
        raise RuntimeError("duplicate position date-contract key")
    if trades["trade_id"].astype(str).duplicated().any():
        raise RuntimeError("duplicate trade id")
    if candidates["candidate_index"].duplicated().any():
        raise RuntimeError("duplicate candidate index")
    if panel.duplicated(["date", "contract_vt_symbol"]).any():
        raise RuntimeError("duplicate panel date-contract key")
    numeric_position_columns = [
        "start_pos",
        "end_pos",
        "pos_change",
        "trade_count",
        "commission",
        "slippage",
        "net_pnl",
        "close_price",
    ]
    positions[numeric_position_columns] = positions[numeric_position_columns].apply(
        pd.to_numeric, errors="raise"
    )
    if not np.allclose(
        positions["end_pos"] - positions["start_pos"], positions["pos_change"], atol=1e-9
    ):
        raise RuntimeError("position arithmetic does not conserve")
    cross_day_audit = validate_cross_day_position_conservation(
        positions,
        market_dates=pd.DatetimeIndex(sorted(positions["date"].unique())),
    )
    trades["signed_volume"] = pd.to_numeric(trades["signed_volume"], errors="raise")
    trades["volume"] = pd.to_numeric(trades["volume"], errors="raise")
    trade_changes = trades.groupby(["date", "vt_symbol"], as_index=False).agg(
        trade_pos_change=("signed_volume", "sum"),
        actual_trade_count=("trade_id", "size"),
    )
    position_changes = positions.loc[
        positions["pos_change"].ne(0) | positions["trade_count"].ne(0),
        ["date", "vt_symbol", "pos_change", "trade_count"],
    ]
    reconciliation = position_changes.merge(
        trade_changes, on=["date", "vt_symbol"], how="outer"
    ).fillna(0.0)
    if not np.allclose(
        reconciliation["pos_change"], reconciliation["trade_pos_change"], atol=1e-9
    ):
        raise RuntimeError("trades do not reconcile to position changes")
    if not np.allclose(
        reconciliation["trade_count"], reconciliation["actual_trade_count"], atol=1e-9
    ):
        raise RuntimeError("trade counts do not reconcile to positions")
    position_daily = positions.groupby("date", as_index=False).agg(
        position_net_pnl=("net_pnl", "sum"),
        position_trade_count=("trade_count", "sum"),
        position_slippage=("slippage", "sum"),
    )
    daily_compare = daily.merge(position_daily, on="date", how="left", validate="one_to_one")
    for left, right in (
        ("net_pnl", "position_net_pnl"),
        ("trade_count", "position_trade_count"),
        ("slippage", "position_slippage"),
    ):
        if not np.allclose(
            pd.to_numeric(daily_compare[left], errors="raise"),
            pd.to_numeric(daily_compare[right], errors="raise"),
            atol=1e-6,
        ):
            raise RuntimeError(f"daily/position aggregate mismatch: {left}")
    frames.update(
        {
            "daily": daily,
            "trades": trades,
            "positions": positions,
            "candidates": candidates,
            "panel": panel,
        }
    )
    audit = {
        "daily_rows": len(daily),
        "trade_rows": len(trades),
        "position_rows": len(positions),
        "candidate_rows": len(candidates),
        "panel_rows": len(panel),
        "daily_start": daily["date"].min().date().isoformat(),
        "daily_end": daily["date"].max().date().isoformat(),
        "position_reconciliation_rows": len(reconciliation),
        "position_net_pnl_sum": float(positions["net_pnl"].sum()),
        "daily_net_pnl_sum": float(pd.to_numeric(daily["net_pnl"], errors="raise").sum()),
    }
    audit.update(cross_day_audit)
    return audit


def _direction_of(values: pd.Series) -> int:
    nonzero = pd.to_numeric(values, errors="raise")
    nonzero = nonzero[nonzero.ne(0)]
    if nonzero.empty:
        return 0
    signs = set(np.sign(nonzero).astype(int))
    if len(signs) != 1:
        raise RuntimeError(f"mixed product direction: {sorted(signs)}")
    return int(next(iter(signs)))


def build_product_days(positions: pd.DataFrame, market_dates: pd.DatetimeIndex) -> pd.DataFrame:
    data = positions.copy()
    data["product"] = data["vt_symbol"].map(contract_to_product)
    active = data.loc[
        data["start_pos"].ne(0) | data["end_pos"].ne(0) | data["trade_count"].ne(0)
    ].copy()
    rows: list[dict[str, Any]] = []
    for (date, product), group in active.groupby(["date", "product"], sort=True):
        start = group[group["start_pos"].ne(0)]
        end = group[group["end_pos"].ne(0)]
        start_direction = _direction_of(start["start_pos"])
        end_direction = _direction_of(end["end_pos"])
        if start_direction and end_direction and start_direction != end_direction:
            raise RuntimeError(f"same-day direct product reversal is unsupported: {date} {product}")
        start_contracts = sorted(start["vt_symbol"].astype(str).unique())
        end_contracts = sorted(end["vt_symbol"].astype(str).unique())
        rows.append(
            {
                "date": date,
                "product": product,
                "start_direction": start_direction,
                "end_direction": end_direction,
                "start_volume": int(round(pd.to_numeric(start["start_pos"], errors="raise").abs().sum())),
                "end_volume": int(round(pd.to_numeric(end["end_pos"], errors="raise").abs().sum())),
                "start_contract_count": len(start_contracts),
                "end_contract_count": len(end_contracts),
                "start_contracts": ",".join(start_contracts),
                "end_contracts": ",".join(end_contracts),
                "actual_contract": start_contracts[0] if len(start_contracts) == 1 else "",
                "net_pnl": float(group["net_pnl"].sum()),
                "commission": float(group["commission"].sum()),
                "slippage": float(group["slippage"].sum()),
                "trade_count": int(round(group["trade_count"].sum())),
                "roll_transition": int(
                    bool(start_contracts)
                    and bool(end_contracts)
                    and start_direction == end_direction
                    and start_contracts != end_contracts
                ),
            }
        )
    product_days = pd.DataFrame(rows).sort_values(["product", "date"]).reset_index(drop=True)
    calendar_index = {date: index for index, date in enumerate(market_dates)}
    if not set(product_days["date"]).issubset(calendar_index):
        raise RuntimeError("position date missing from panel market calendar")
    product_days["calendar_index"] = product_days["date"].map(calendar_index).astype(int)
    product_days["episode_id"] = ""
    product_days["episode_left_censored"] = 0
    for product, indices in product_days.groupby("product", sort=False).groups.items():
        sequence = 0
        active_episode = ""
        active_direction = 0
        previous_calendar_index: int | None = None
        for index in list(indices):
            row = product_days.loc[index]
            start_direction = int(row["start_direction"])
            end_direction = int(row["end_direction"])
            current_calendar_index = int(row["calendar_index"])
            if start_direction:
                if active_episode:
                    if active_direction != start_direction:
                        raise RuntimeError(f"episode direction mismatch: {product} {row['date']}")
                    if previous_calendar_index is None or current_calendar_index != previous_calendar_index + 1:
                        raise RuntimeError(f"active position date gap: {product} {row['date']}")
                    episode_id = active_episode
                    left_censored = 0
                else:
                    sequence += 1
                    episode_id = f"{product}|{'long' if start_direction > 0 else 'short'}|{sequence:04d}"
                    left_censored = 1
            elif end_direction:
                if active_episode:
                    raise RuntimeError(f"new open while prior logical episode is active: {product} {row['date']}")
                sequence += 1
                episode_id = f"{product}|{'long' if end_direction > 0 else 'short'}|{sequence:04d}"
                left_censored = 0
            else:
                if active_episode:
                    raise RuntimeError(f"zero/zero product day inside active episode: {product} {row['date']}")
                episode_id = ""
                left_censored = 0
            product_days.loc[index, "episode_id"] = episode_id
            product_days.loc[index, "episode_left_censored"] = left_censored
            if end_direction:
                active_episode = episode_id
                active_direction = end_direction
            else:
                active_episode = ""
                active_direction = 0
            previous_calendar_index = current_calendar_index
    return product_days


def attach_episode_risk(
    product_days: pd.DataFrame,
    candidates: pd.DataFrame,
    trades: pd.DataFrame,
    market_dates: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    days = product_days.copy()
    calendar_index = {date: index for index, date in enumerate(market_dates)}
    opened = candidates[candidates["candidate_status"].astype(str).eq("opened")].copy()
    opened["direction_sign"] = opened["direction"].astype(str).str.lower().map({"long": 1, "short": -1})
    if opened["direction_sign"].isna().any():
        raise RuntimeError("unknown candidate direction")
    trade_data = trades.copy()
    trade_data["direction_sign"] = trade_data["direction"].astype(str).str.lower().map(
        {"long": 1, "short": -1}
    )
    if trade_data["direction_sign"].isna().any():
        raise RuntimeError("unknown trade direction")
    metadata_rows: list[dict[str, Any]] = []
    for episode_id, group in days[days["episode_id"].ne("")].groupby("episode_id", sort=False):
        group = group.sort_values("date")
        first = group.iloc[0]
        direction = int(first["end_direction"] if int(first["end_direction"]) else first["start_direction"])
        opening = group[(group["start_direction"].eq(0)) & (group["end_direction"].eq(direction))]
        risk_available = 0
        risk_reason = "left_censored_or_missing_open"
        entry_date = pd.NaT
        entry_contract = ""
        candidate_index: Any = np.nan
        target_risk_amount = np.nan
        stop_distance = np.nan
        contract_size = np.nan
        selected_volume = np.nan
        entry_end_volume = np.nan
        real_open_volume = np.nan
        selected_matches_entry_end = 0
        selected_matches_open_flow = 0
        if len(opening) == 1:
            opening_row = opening.iloc[0]
            entry_date = pd.Timestamp(opening_row["date"])
            entry_end_volume = float(opening_row["end_volume"])
            entry_contracts = [item for item in str(opening_row["end_contracts"]).split(",") if item]
            if len(entry_contracts) == 1 and int(opening_row["calendar_index"]) > 0:
                entry_contract = entry_contracts[0]
                signal_date = market_dates[int(opening_row["calendar_index"]) - 1]
                matches = opened[
                    opened["date"].eq(signal_date)
                    & opened["contract_vt_symbol"].astype(str).eq(entry_contract)
                    & opened["direction_sign"].eq(direction)
                ]
                real_open = trade_data[
                    trade_data["date"].eq(entry_date)
                    & trade_data["vt_symbol"].astype(str).eq(entry_contract)
                    & trade_data["offset"].astype(str).str.lower().eq("open")
                    & trade_data["direction_sign"].eq(direction)
                ]
                if len(matches) == 1 and not real_open.empty:
                    match = matches.iloc[0]
                    real_open_volume = float(pd.to_numeric(real_open["volume"], errors="raise").sum())
                    candidate_index = match["candidate_index"]
                    target_risk_amount = float(match["target_risk_amount"])
                    stop_distance = float(match["stop_distance"])
                    contract_size = float(match["size"])
                    selected_volume = float(match["selected_volume"])
                    if (
                        target_risk_amount > 0.0
                        and stop_distance > 0.0
                        and contract_size > 0.0
                        and selected_volume > 0.0
                    ):
                        risk_available = 1
                        risk_reason = "matched_candidate_and_real_open"
                        selected_matches_entry_end = int(
                            math.isclose(selected_volume, entry_end_volume, rel_tol=0.0, abs_tol=1e-9)
                        )
                        selected_matches_open_flow = int(
                            math.isclose(selected_volume, real_open_volume, rel_tol=0.0, abs_tol=1e-9)
                        )
                    else:
                        risk_reason = "invalid_candidate_risk_values"
                elif len(matches) != 1:
                    risk_reason = f"candidate_match_count_{len(matches)}"
                else:
                    risk_reason = "missing_real_open_trade"
            else:
                risk_reason = "ambiguous_entry_contract_or_calendar"
        elif len(opening) > 1:
            risk_reason = "multiple_opening_rows"
        exit_rows = group[
            group["start_direction"].eq(direction) & group["end_direction"].eq(0)
        ]
        natural_exit_date = exit_rows.iloc[0]["date"] if not exit_rows.empty else pd.NaT
        metadata_rows.append(
            {
                "episode_id": episode_id,
                "product": first["product"],
                "episode_direction": direction,
                "episode_start_date": group["date"].min(),
                "episode_last_observed_date": group["date"].max(),
                "natural_exit_date": natural_exit_date,
                "risk_available": risk_available,
                "risk_reason": risk_reason,
                "entry_date": entry_date,
                "entry_contract": entry_contract,
                "candidate_index": candidate_index,
                "target_risk_amount": target_risk_amount,
                "stop_distance": stop_distance,
                "contract_size": contract_size,
                "selected_volume": selected_volume,
                "entry_end_volume": entry_end_volume,
                "real_open_volume": real_open_volume,
                "selected_matches_entry_end": selected_matches_entry_end,
                "selected_matches_open_flow": selected_matches_open_flow,
            }
        )
    metadata = pd.DataFrame(metadata_rows)
    days = days.merge(metadata, on=["episode_id", "product"], how="left", validate="many_to_one")
    return days, metadata


def build_state_rows(
    product_days: pd.DataFrame,
    panel: pd.DataFrame,
    market_dates: pd.DatetimeIndex,
    *,
    panel_sha256: str,
) -> pd.DataFrame:
    close_index = prepare_close_index(panel)
    rows: list[dict[str, Any]] = []
    for day in product_days[product_days["start_direction"].ne(0)].itertuples(index=False):
        base = day._asdict()
        direction = int(day.start_direction)
        if int(day.start_contract_count) != 1 or not str(day.actual_contract):
            state = {
                "available": 0,
                "reason": "ambiguous_actual_contract",
                "asof_date": pd.NaT,
                "slow_aligned": 0,
                "fast_relation": "unavailable",
            }
        else:
            action_index = int(day.calendar_index)
            if action_index < MAX_LOOKBACK:
                state = {
                    "available": 0,
                    "reason": "insufficient_history",
                    "asof_date": pd.NaT,
                    "slow_aligned": 0,
                    "fast_relation": "unavailable",
                }
            else:
                series = close_index.get(str(day.actual_contract))
                if series is None:
                    state = {
                        "available": 0,
                        "reason": "missing_contract",
                        "asof_date": pd.NaT,
                        "slow_aligned": 0,
                        "fast_relation": "unavailable",
                    }
                else:
                    state = _state_from_close_series(
                        series,
                        expected_dates=market_dates[action_index - MAX_LOOKBACK : action_index],
                        action_date=pd.Timestamp(day.date),
                        position_direction=direction,
                    )
        base.update(
            {
                "action_date": day.date,
                "position_direction": direction,
                "feature_available": int(state["available"]),
                "feature_reason": state["reason"],
                "state_panel_sha256": panel_sha256,
            }
        )
        base.update({key: value for key, value in state.items() if key not in {"available", "reason"}})
        rows.append(base)
    states = pd.DataFrame(rows)
    if not states.empty:
        available = states[states["feature_available"].eq(1)]
        if not (pd.to_datetime(available["asof_date"]) < pd.to_datetime(available["action_date"])).all():
            raise RuntimeError("T-1 state violation")
    return states


def build_cost_model(positions: pd.DataFrame, trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    trade_volume = trades.groupby(["date", "vt_symbol"], as_index=False).agg(
        traded_volume=("volume", "sum")
    )
    costs = positions.loc[
        positions["trade_count"].gt(0), ["date", "vt_symbol", "commission", "slippage"]
    ].merge(trade_volume, on=["date", "vt_symbol"], how="inner", validate="one_to_one")
    costs["total_cost"] = costs["commission"] + costs["slippage"]
    costs["cost_per_contract"] = costs["total_cost"] / costs["traded_volume"]
    if (
        costs["traded_volume"].le(0).any()
        or (~np.isfinite(costs["cost_per_contract"])).any()
        or costs["cost_per_contract"].lt(0).any()
    ):
        raise RuntimeError("invalid observed execution cost")
    costs["product"] = costs["vt_symbol"].map(contract_to_product)
    contract_model = costs.groupby("vt_symbol", as_index=False).agg(
        contract_cost_per_contract=("cost_per_contract", "median"),
        contract_cost_observations=("cost_per_contract", "size"),
    )
    product_model = costs.groupby("product", as_index=False).agg(
        product_cost_per_contract=("cost_per_contract", "median"),
        product_cost_observations=("cost_per_contract", "size"),
    )
    return contract_model, product_model


def _exit_trade_price(
    trades: pd.DataFrame,
    *,
    date: pd.Timestamp,
    contract: str,
    position_direction: int,
) -> float | None:
    close_direction = -position_direction
    subset = trades[
        trades["date"].eq(date)
        & trades["vt_symbol"].astype(str).eq(contract)
        & trades["offset"].astype(str).str.lower().eq("close")
        & trades["direction_sign"].eq(close_direction)
    ].copy()
    if subset.empty:
        return None
    prices = pd.to_numeric(subset["price"], errors="raise").to_numpy(dtype=float)
    volumes = pd.to_numeric(subset["volume"], errors="raise").to_numpy(dtype=float)
    if (~np.isfinite(prices)).any() or (~np.isfinite(volumes)).any() or (volumes <= 0.0).any():
        raise RuntimeError("invalid close trade price or volume")
    return float(np.average(prices, weights=volumes))


def attach_outcomes(
    rows: pd.DataFrame,
    *,
    positions: pd.DataFrame,
    trades: pd.DataFrame,
    product_days: pd.DataFrame,
    panel: pd.DataFrame,
    market_dates: pd.DatetimeIndex,
    include_economics: bool,
) -> pd.DataFrame:
    if rows.empty:
        empty = rows.copy()
        for horizon in HORIZONS:
            empty[f"outcome_{horizon}d_available"] = pd.Series(dtype="int64")
            empty[f"outcome_{horizon}d_reason"] = pd.Series(dtype="object")
            empty[f"outcome_{horizon}d_r"] = pd.Series(dtype="float64")
            empty[f"outcome_{horizon}d_endpoint_date"] = pd.Series(dtype="datetime64[ns]")
            empty[f"outcome_{horizon}d_endpoint_price"] = pd.Series(dtype="float64")
            empty[f"outcome_{horizon}d_capped_at_exit"] = pd.Series(dtype="int64")
        empty["outcome_base_price"] = pd.Series(dtype="float64")
        empty["segment"] = pd.Series(dtype="object")
        empty["year"] = pd.Series(dtype="int64")
        if include_economics:
            for column, dtype in (
                ("retained_volume", "int64"),
                ("released_volume", "int64"),
                ("released_fraction", "float64"),
                ("economic_available", "int64"),
                ("economic_reason", "object"),
                ("action_cost_one_way", "float64"),
                ("action_cost_2x", "float64"),
                ("remaining_baseline_net_pnl", "float64"),
                ("static_gross_improvement", "float64"),
                ("static_net_improvement_after_2x_cost", "float64"),
                ("static_avoided_loss", "float64"),
                ("static_right_tail_sacrifice", "float64"),
            ):
                empty[column] = pd.Series(dtype=dtype)
        return empty
    data = rows.copy().reset_index(drop=True)
    close_index = prepare_close_index(panel)
    calendar_index = {date: index for index, date in enumerate(market_dates)}
    position_groups = {
        str(contract): group.sort_values("date")
        for contract, group in positions.groupby("vt_symbol", sort=False)
    }
    trade_data = trades.copy()
    trade_data["direction_sign"] = trade_data["direction"].astype(str).str.lower().map(
        {"long": 1, "short": -1}
    )
    contract_cost, product_cost = build_cost_model(positions, trades)
    contract_cost_map = contract_cost.set_index("vt_symbol")["contract_cost_per_contract"].to_dict()
    product_cost_map = product_cost.set_index("product")["product_cost_per_contract"].to_dict()
    episode_groups = {
        str(episode): group.sort_values("date")
        for episode, group in product_days[product_days["episode_id"].ne("")].groupby(
            "episode_id", sort=False
        )
    }
    output_rows: list[dict[str, Any]] = []
    for source in data.itertuples(index=False):
        result = source._asdict()
        action_date = pd.Timestamp(source.action_date)
        action_index = calendar_index[action_date]
        contract = str(source.actual_contract)
        direction = int(source.position_direction)
        stop_distance = float(source.stop_distance) if pd.notna(source.stop_distance) else np.nan
        series = close_index.get(contract)
        base_price = np.nan
        if series is not None and pd.notna(source.asof_date) and pd.Timestamp(source.asof_date) in series.index:
            base_price = float(series.loc[pd.Timestamp(source.asof_date)])
        contract_positions = position_groups.get(contract, pd.DataFrame())
        for horizon in HORIZONS:
            available = 0
            reason = "unavailable"
            endpoint_date = pd.NaT
            endpoint_price = np.nan
            capped_at_exit = 0
            target_index = action_index + horizon - 1
            last_scan_index = min(target_index, len(market_dates) - 1)
            scan_end = market_dates[last_scan_index]
            if not contract_positions.empty:
                path = contract_positions[
                    contract_positions["date"].between(action_date, scan_end)
                    & np.sign(contract_positions["start_pos"]).eq(direction)
                ].copy()
                exits = path[np.sign(path["end_pos"]).ne(direction)]
            else:
                exits = pd.DataFrame()
            if not exits.empty:
                exit_row = exits.iloc[0]
                endpoint_date = pd.Timestamp(exit_row["date"])
                exit_price = _exit_trade_price(
                    trade_data,
                    date=endpoint_date,
                    contract=contract,
                    position_direction=direction,
                )
                if exit_price is not None:
                    endpoint_price = exit_price
                    capped_at_exit = 1
                    available = 1
                    reason = "capped_at_actual_contract_exit"
                else:
                    reason = "missing_exit_trade_price"
            elif target_index < len(market_dates) and series is not None:
                endpoint_date = market_dates[target_index]
                if endpoint_date in series.index:
                    endpoint_price = float(series.loc[endpoint_date])
                    available = 1
                    reason = "full_horizon_close"
                else:
                    reason = "missing_horizon_close"
            else:
                reason = "right_censored_before_horizon"
            if not np.isfinite(base_price) or not np.isfinite(stop_distance) or stop_distance <= 0.0:
                available = 0
                reason = "risk_or_base_price_unavailable"
            outcome = (
                direction * (float(endpoint_price) - base_price) / stop_distance
                if available
                else np.nan
            )
            result.update(
                {
                    f"outcome_{horizon}d_available": available,
                    f"outcome_{horizon}d_reason": reason,
                    f"outcome_{horizon}d_r": outcome,
                    f"outcome_{horizon}d_endpoint_date": endpoint_date,
                    f"outcome_{horizon}d_endpoint_price": endpoint_price,
                    f"outcome_{horizon}d_capped_at_exit": capped_at_exit,
                }
            )
        result["outcome_base_price"] = base_price
        if include_economics:
            retained, released = half_release(int(source.start_volume))
            fraction = released / int(source.start_volume) if int(source.start_volume) > 0 else 0.0
            episode_path = episode_groups.get(str(source.episode_id), pd.DataFrame())
            natural_exit = pd.Timestamp(source.natural_exit_date) if pd.notna(source.natural_exit_date) else pd.NaT
            future_path = (
                episode_path[
                    episode_path["date"].gt(action_date)
                    & episode_path["date"].le(natural_exit)
                ]
                if pd.notna(natural_exit)
                else pd.DataFrame()
            )
            contract_cost_value = contract_cost_map.get(contract)
            cost_source = "contract_median"
            if contract_cost_value is None:
                contract_cost_value = product_cost_map.get(str(source.product))
                cost_source = "product_median"
            economic_available = int(
                released > 0
                and pd.notna(natural_exit)
                and not future_path.empty
                and pd.notna(source.target_risk_amount)
                and float(source.target_risk_amount) > 0.0
                and contract_cost_value is not None
                and np.isfinite(float(contract_cost_value))
            )
            remaining_net_pnl = float(future_path["net_pnl"].sum()) if not future_path.empty else np.nan
            target_risk = float(source.target_risk_amount) if pd.notna(source.target_risk_amount) else np.nan
            cumulative = future_path["net_pnl"].cumsum() if not future_path.empty else pd.Series(dtype=float)
            action_cost = (
                float(contract_cost_value) * released if contract_cost_value is not None else np.nan
            )
            gross_improvement = -fraction * remaining_net_pnl if economic_available else np.nan
            doubled_cost = 2.0 * action_cost if economic_available else np.nan
            net_improvement = gross_improvement - doubled_cost if economic_available else np.nan
            action_day_rows = episode_path[episode_path["date"].eq(action_date)]
            result.update(
                {
                    "retained_volume": retained,
                    "released_volume": released,
                    "released_fraction": fraction,
                    "economic_available": economic_available,
                    "economic_reason": "available" if economic_available else "risk_exit_cost_or_action_unavailable",
                    "cost_source": cost_source if contract_cost_value is not None else "unavailable",
                    "action_cost_one_way": action_cost,
                    "action_cost_2x": doubled_cost,
                    "action_day_baseline_net_pnl_diagnostic": float(action_day_rows["net_pnl"].sum())
                    if not action_day_rows.empty
                    else np.nan,
                    "remaining_baseline_net_pnl": remaining_net_pnl,
                    "remaining_baseline_pnl_r": remaining_net_pnl / target_risk
                    if economic_available
                    else np.nan,
                    "remaining_path_mae_r": float(cumulative.min()) / target_risk
                    if economic_available
                    else np.nan,
                    "remaining_path_mfe_r": float(cumulative.max()) / target_risk
                    if economic_available
                    else np.nan,
                    "static_gross_improvement": gross_improvement,
                    "static_net_improvement_after_2x_cost": net_improvement,
                    "static_avoided_loss": max(gross_improvement, 0.0)
                    if economic_available
                    else np.nan,
                    "static_right_tail_sacrifice": max(-gross_improvement, 0.0)
                    if economic_available
                    else np.nan,
                }
            )
        result["segment"] = segment_for_date(action_date)
        result["year"] = action_date.year
        output_rows.append(result)
    return pd.DataFrame(output_rows)


def select_concordant_references(states: pd.DataFrame) -> pd.DataFrame:
    references = states[
        states["feature_available"].eq(1)
        & states["slow_aligned"].eq(1)
        & states["fast_relation"].eq("concordant")
        & states["episode_id"].ne("")
    ].copy()
    return (
        references.sort_values("action_date")
        .groupby(["episode_id", "date_block20"], as_index=False, sort=False)
        .head(1)
        .reset_index(drop=True)
    )


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0.0:
        return math.inf if numerator > 0.0 else 0.0
    return numerator / denominator


def positive_top_n_share(values: pd.Series, *, n: int) -> float | None:
    if int(n) <= 0:
        raise ValueError("n must be positive")
    positive = pd.to_numeric(values, errors="raise").clip(lower=0.0).sort_values(ascending=False)
    total = float(positive.sum())
    if positive.empty or total <= 0.0:
        return None
    return float(positive.head(int(n)).sum() / total)


def build_gate_matrix(
    states: pd.DataFrame,
    events: pd.DataFrame,
    references: pd.DataFrame,
    bootstrap: dict[str, Any] | None,
    economic_bootstrap: dict[str, Any] | None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    valid_events = events[events["outcome_5d_available"].eq(1)].copy()
    valid_references = references[references["outcome_5d_available"].eq(1)].copy()
    feature_coverage = float(states["feature_available"].mean()) if len(states) else 0.0
    event_5_coverage = float(events["outcome_5d_available"].mean()) if len(events) else 0.0
    ref_5_coverage = float(references["outcome_5d_available"].mean()) if len(references) else 0.0
    event_20_coverage = float(events["outcome_20d_available"].mean()) if len(events) else 0.0
    ref_20_coverage = float(references["outcome_20d_available"].mean()) if len(references) else 0.0
    segment_coverages: list[float] = []
    for segment in SEGMENTS:
        for frame in (events, references):
            subset = frame[frame["segment"].eq(segment)]
            segment_coverages.append(
                float(subset["outcome_5d_available"].mean()) if len(subset) else 0.0
            )
            segment_coverages.append(
                float(subset["outcome_20d_available"].mean()) if len(subset) else 0.0
            )
    minimum_segment_coverage = min(segment_coverages) if segment_coverages else 0.0
    event_count = len(valid_events)
    unique_days = int(valid_events["action_date"].nunique()) if event_count else 0
    product_count = int(valid_events["product"].nunique()) if event_count else 0
    long_count = int(valid_events["position_direction"].eq(1).sum()) if event_count else 0
    short_count = int(valid_events["position_direction"].eq(-1).sum()) if event_count else 0
    max_product_share = (
        float(valid_events["product"].value_counts(normalize=True).max()) if event_count else 1.0
    )
    max_year_share = (
        float(valid_events["year"].value_counts(normalize=True).max()) if event_count else 1.0
    )
    actionable = valid_events[
        valid_events.get("economic_available", pd.Series(0, index=valid_events.index)).eq(1)
        & valid_events.get("released_volume", pd.Series(0, index=valid_events.index)).gt(0)
    ].copy()
    actionable_count = len(actionable)
    actionable_products = int(actionable["product"].nunique()) if actionable_count else 0
    segment_event_stats: dict[str, dict[str, Any]] = {}
    for segment in SEGMENTS:
        subset = valid_events[valid_events["segment"].eq(segment)]
        segment_event_stats[segment] = {
            "count": len(subset),
            "products": int(subset["product"].nunique()) if len(subset) else 0,
            "mean_5d_r": float(subset["outcome_5d_r"].mean()) if len(subset) else np.nan,
            "actionable_count": int(actionable["segment"].eq(segment).sum()) if actionable_count else 0,
        }
    qualifying_years = (
        valid_events.groupby("year")
        .agg(count=("outcome_5d_r", "size"), mean_5d_r=("outcome_5d_r", "mean"))
        .query("count >= 10")
        if event_count
        else pd.DataFrame(columns=["count", "mean_5d_r"])
    )
    qualifying_year_count = len(qualifying_years)
    adverse_year_fraction = (
        float(qualifying_years["mean_5d_r"].lt(0.0).mean()) if qualifying_year_count else 0.0
    )
    direction_means = (
        valid_events.groupby("position_direction")["outcome_5d_r"].mean().to_dict()
        if event_count
        else {}
    )
    mean_difference = (
        float(valid_events["outcome_5d_r"].mean() - valid_references["outcome_5d_r"].mean())
        if event_count and len(valid_references)
        else np.nan
    )
    median_difference = (
        float(valid_events["outcome_5d_r"].median() - valid_references["outcome_5d_r"].median())
        if event_count and len(valid_references)
        else np.nan
    )
    economic_segment_net = {
        segment: float(actionable.loc[actionable["segment"].eq(segment), "static_net_improvement_after_2x_cost"].sum())
        if actionable_count
        else 0.0
        for segment in SEGMENTS
    }
    total_2x_cost = float(actionable["action_cost_2x"].sum()) if actionable_count else 0.0
    avoided_loss = float(actionable["static_avoided_loss"].sum()) if actionable_count else 0.0
    right_tail = float(actionable["static_right_tail_sacrifice"].sum()) if actionable_count else 0.0
    loss_to_tail_ratio = _safe_ratio(avoided_loss, right_tail)
    top5_share = positive_top_n_share(
        actionable.get("static_gross_improvement", pd.Series(dtype=float)), n=5
    )
    gates: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        gates.append({"gate": name, "passed": int(bool(passed)), "detail": detail})

    add("feature_coverage", feature_coverage >= 0.95, f"{feature_coverage:.6f} >= 0.95")
    add(
        "outcome_5d_coverage",
        min(event_5_coverage, ref_5_coverage) >= 0.90,
        f"event={event_5_coverage:.6f}, reference={ref_5_coverage:.6f}",
    )
    add(
        "outcome_20d_coverage",
        min(event_20_coverage, ref_20_coverage) >= 0.90,
        f"event={event_20_coverage:.6f}, reference={ref_20_coverage:.6f}",
    )
    add(
        "segment_outcome_coverage",
        minimum_segment_coverage >= 0.85,
        f"minimum={minimum_segment_coverage:.6f}",
    )
    add(
        "group_coverage_balance",
        abs(event_5_coverage - ref_5_coverage) <= 0.05
        and abs(event_20_coverage - ref_20_coverage) <= 0.05,
        f"5d_diff={abs(event_5_coverage-ref_5_coverage):.6f}, 20d_diff={abs(event_20_coverage-ref_20_coverage):.6f}",
    )
    add(
        "event_sample",
        event_count >= 120 and unique_days >= 60 and product_count >= 12,
        f"events={event_count}, days={unique_days}, products={product_count}",
    )
    add(
        "direction_sample",
        long_count >= 30 and short_count >= 30,
        f"long={long_count}, short={short_count}",
    )
    add(
        "concentration",
        max_product_share <= 0.20 and max_year_share <= 0.25,
        f"max_product={max_product_share:.6f}, max_year={max_year_share:.6f}",
    )
    add(
        "actionable_sample",
        actionable_count >= 60
        and actionable_products >= 12
        and all(item["actionable_count"] >= 15 for item in segment_event_stats.values()),
        f"events={actionable_count}, products={actionable_products}, segments={ {k:v['actionable_count'] for k,v in segment_event_stats.items()} }",
    )
    add(
        "three_segment_sample",
        all(item["count"] >= 30 and item["products"] >= 6 for item in segment_event_stats.values()),
        str({key: {"count": value["count"], "products": value["products"]} for key, value in segment_event_stats.items()}),
    )
    add(
        "three_segment_adverse_mean",
        all(pd.notna(item["mean_5d_r"]) and item["mean_5d_r"] < 0.0 for item in segment_event_stats.values()),
        str({key: value["mean_5d_r"] for key, value in segment_event_stats.items()}),
    )
    add(
        "year_stability",
        qualifying_year_count >= 6 and adverse_year_fraction >= (5.0 / 6.0),
        f"qualifying_years={qualifying_year_count}, adverse_fraction={adverse_year_fraction:.6f}",
    )
    add(
        "direction_adverse_mean",
        1 in direction_means
        and -1 in direction_means
        and direction_means[1] < 0.0
        and direction_means[-1] < 0.0,
        str(direction_means),
    )
    add(
        "mean_difference",
        pd.notna(mean_difference) and mean_difference <= -0.25,
        f"{mean_difference}",
    )
    add(
        "median_difference",
        pd.notna(median_difference) and median_difference <= -0.10,
        f"{median_difference}",
    )
    add(
        "clustered_ci",
        bootstrap is not None and float(bootstrap["ci95_upper"]) < 0.0,
        str(bootstrap),
    )
    add(
        "three_segment_economics",
        all(value > 0.0 for value in economic_segment_net.values()),
        str(economic_segment_net),
    )
    add(
        "economic_lower_bound",
        economic_bootstrap is not None
        and float(economic_bootstrap["ci95_lower_total"]) > total_2x_cost,
        f"bootstrap={economic_bootstrap}, total_2x_cost={total_2x_cost}",
    )
    add(
        "loss_to_right_tail_ratio",
        loss_to_tail_ratio >= 1.5,
        f"ratio={loss_to_tail_ratio}, avoided={avoided_loss}, tail={right_tail}",
    )
    add(
        "top5_concentration",
        top5_share is not None and top5_share <= 0.40,
        f"top5_share={top5_share}",
    )
    gate_frame = pd.DataFrame(gates)
    metrics = {
        "feature_coverage": feature_coverage,
        "event_5d_coverage": event_5_coverage,
        "reference_5d_coverage": ref_5_coverage,
        "event_20d_coverage": event_20_coverage,
        "reference_20d_coverage": ref_20_coverage,
        "minimum_segment_coverage": minimum_segment_coverage,
        "valid_event_count": event_count,
        "valid_reference_count": len(valid_references),
        "unique_event_days": unique_days,
        "event_product_count": product_count,
        "long_event_count": long_count,
        "short_event_count": short_count,
        "max_product_share": max_product_share,
        "max_year_share": max_year_share,
        "actionable_event_count": actionable_count,
        "actionable_product_count": actionable_products,
        "segment_event_stats": segment_event_stats,
        "qualifying_year_count": qualifying_year_count,
        "adverse_year_fraction": adverse_year_fraction,
        "direction_means": direction_means,
        "mean_difference": mean_difference,
        "median_difference": median_difference,
        "economic_segment_net": economic_segment_net,
        "total_2x_cost": total_2x_cost,
        "avoided_loss": avoided_loss,
        "right_tail_sacrifice": right_tail,
        "loss_to_tail_ratio": loss_to_tail_ratio,
        "top5_positive_improvement_share": top5_share,
    }
    return gate_frame, metrics


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, (pd.Timestamp,)):
        return None if pd.isna(value) else value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    if pd.isna(value) if not isinstance(value, (str, bool)) else False:
        return None
    return value


def build_event_summary(events: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "dimension",
        "value",
        "raw_events",
        "valid_5d_events",
        "mean_1d_r",
        "mean_5d_r",
        "median_5d_r",
        "mean_20d_r",
        "actionable_events",
        "static_net_improvement_after_2x_cost",
    ]
    if events.empty:
        return pd.DataFrame(columns=columns)
    rows: list[dict[str, Any]] = []
    for dimension, column in (
        ("segment", "segment"),
        ("year", "year"),
        ("direction", "position_direction"),
        ("product", "product"),
    ):
        for value, group in events.groupby(column, dropna=False, sort=True):
            valid = group[group["outcome_5d_available"].eq(1)]
            rows.append(
                {
                    "dimension": dimension,
                    "value": value,
                    "raw_events": len(group),
                    "valid_5d_events": len(valid),
                    "mean_1d_r": valid["outcome_1d_r"].mean(),
                    "mean_5d_r": valid["outcome_5d_r"].mean(),
                    "median_5d_r": valid["outcome_5d_r"].median(),
                    "mean_20d_r": valid.loc[valid["outcome_20d_available"].eq(1), "outcome_20d_r"].mean(),
                    "actionable_events": int(group.get("economic_available", pd.Series(0, index=group.index)).eq(1).sum()),
                    "static_net_improvement_after_2x_cost": group.get(
                        "static_net_improvement_after_2x_cost", pd.Series(0.0, index=group.index)
                    ).sum(),
                }
            )
    return pd.DataFrame(rows, columns=columns)


def build_report(
    *,
    audit: dict[str, Any],
    metrics: dict[str, Any],
    gates: pd.DataFrame,
    decision: dict[str, Any],
    bootstrap: dict[str, Any] | None,
    economic_bootstrap: dict[str, Any] | None,
) -> str:
    failed = gates.loc[gates["passed"].eq(0), "gate"].tolist()
    return "\n".join(
        [
            "# Stage001 strict T-1 turning-state attribution",
            "",
            f"- decision: `{'ALLOW_CANARY' if decision['canary_allowed'] else 'CLOSE_LINE'}`",
            f"- failed gates: `{', '.join(failed) if failed else 'none'}`",
            f"- frozen A interval: `{audit['daily_start']}..{audit['daily_end']}`",
            f"- eligible state rows: `{decision['eligible_state_rows']}`",
            f"- raw opposite onsets: `{decision['raw_event_count']}`",
            f"- valid 5d opposite onsets: `{metrics['valid_event_count']}`",
            f"- actionable opposite onsets: `{metrics['actionable_event_count']}`",
            f"- mean 5d opposite-minus-concordant: `{metrics['mean_difference']}` R",
            f"- median 5d opposite-minus-concordant: `{metrics['median_difference']}` R",
            f"- clustered bootstrap: `{bootstrap}`",
            f"- economic bootstrap: `{economic_bootstrap}`",
            "",
            "## Interpretation",
            "",
            "This is a read-only attribution, not a strategy backtest. The static half-release proxy excludes action-day PnL and cannot replace a true engine run.",
            "Any failed frozen gate closes this line; periods, confirmation days, direction filters and the action must not be changed after seeing these results.",
            "",
            "## Overfitting reflection",
            "",
            "The run does not scan parameters or select periods. Residual risks are event dependence, entry-risk matching availability and the static economic proxy; the clustered interval and fail-close gates address but do not eliminate them.",
            "",
            "## Continue-value reflection",
            "",
            "Continue only if every frozen gate passes. Otherwise a real-engine canary has no predeclared evidentiary basis.",
            "",
        ]
    )


def run_attribution() -> dict[str, Any]:
    input_manifest_before = validate_frozen_inputs()
    frames = load_frozen_frames()
    audit = validate_baseline_frames(frames)
    audit["input_daily_start"] = audit["daily_start"]
    audit["input_daily_end"] = audit["daily_end"]
    frames = truncate_analysis_frames(frames, FREEZE_END)
    audit["daily_start"] = frames["daily"]["date"].min().date().isoformat()
    audit["daily_end"] = frames["daily"]["date"].max().date().isoformat()
    audit["freeze_end"] = FREEZE_END.date().isoformat()
    if any(frame["date"].max() > FREEZE_END for frame in frames.values()):
        raise RuntimeError("analysis frame crossed the frozen end date")
    market_dates = pd.DatetimeIndex(sorted(frames["panel"]["date"].unique()))
    product_days = build_product_days(frames["positions"], market_dates)
    product_days, episode_metadata = attach_episode_risk(
        product_days, frames["candidates"], frames["trades"], market_dates
    )
    states = build_state_rows(
        product_days,
        frames["panel"],
        market_dates,
        panel_sha256=EXPECTED_INPUT_SHA256[PANEL_PATH],
    )
    states = mark_primary_events(states, market_dates=market_dates)
    events = states[states["is_primary_event"].eq(1)].copy().reset_index(drop=True)
    references = select_concordant_references(states)
    events = attach_outcomes(
        events,
        positions=frames["positions"],
        trades=frames["trades"],
        product_days=product_days,
        panel=frames["panel"],
        market_dates=market_dates,
        include_economics=True,
    )
    references = attach_outcomes(
        references,
        positions=frames["positions"],
        trades=frames["trades"],
        product_days=product_days,
        panel=frames["panel"],
        market_dates=market_dates,
        include_economics=False,
    )
    comparison = pd.concat(
        [
            events.loc[events["outcome_5d_available"].eq(1), ["product", "date_block20", "outcome_5d_r"]]
            .rename(columns={"outcome_5d_r": "outcome"})
            .assign(group="opposite"),
            references.loc[
                references["outcome_5d_available"].eq(1),
                ["product", "date_block20", "outcome_5d_r"],
            ]
            .rename(columns={"outcome_5d_r": "outcome"})
            .assign(group="concordant"),
        ],
        ignore_index=True,
    )
    try:
        bootstrap = pigeonhole_bootstrap_mean_difference(comparison)
    except (ValueError, RuntimeError):
        bootstrap = None
    actionable = events[
        events.get("economic_available", pd.Series(0, index=events.index)).eq(1)
        & events.get("released_volume", pd.Series(0, index=events.index)).gt(0)
    ]
    try:
        economic_bootstrap = pigeonhole_bootstrap_total_lower_bound(
            actionable,
            value_column="static_gross_improvement",
        )
    except (ValueError, RuntimeError):
        economic_bootstrap = None
    gates, metrics = build_gate_matrix(states, events, references, bootstrap, economic_bootstrap)
    canary_allowed = mechanical_canary_decision(gates)
    decision = {
        "line_id": LINE_ID,
        "stage_id": STAGE_ID,
        "model_tag": MODEL_TAG,
        "canary_allowed": canary_allowed,
        "decision": "ALLOW_CANARY" if canary_allowed else "CLOSE_LINE",
        "eligible_state_rows": len(states),
        "feature_available_rows": int(states["feature_available"].sum()),
        "raw_event_count": len(events),
        "reference_count": len(references),
        "episode_count": int(product_days.loc[product_days["episode_id"].ne(""), "episode_id"].nunique()),
        "risk_matched_episode_count": int(episode_metadata["risk_available"].sum()),
        "risk_selected_matches_entry_end_count": int(
            episode_metadata["selected_matches_entry_end"].sum()
        ),
        "risk_selected_matches_open_flow_count": int(
            episode_metadata["selected_matches_open_flow"].sum()
        ),
        "failed_gates": gates.loc[gates["passed"].eq(0), "gate"].tolist(),
        "bootstrap": bootstrap,
        "economic_bootstrap": economic_bootstrap,
        "metrics": metrics,
    }
    audit.update(
        {
            "market_date_count": len(market_dates),
            "market_start": market_dates.min().date().isoformat(),
            "market_end": market_dates.max().date().isoformat(),
            "active_product_day_rows": len(product_days),
            "episode_count": decision["episode_count"],
            "risk_matched_episode_count": decision["risk_matched_episode_count"],
            "risk_selected_matches_entry_end_count": decision[
                "risk_selected_matches_entry_end_count"
            ],
            "risk_selected_matches_open_flow_count": decision[
                "risk_selected_matches_open_flow_count"
            ],
            "eligible_state_rows": len(states),
            "feature_available_rows": int(states["feature_available"].sum()),
            "raw_event_count": len(events),
            "reference_count": len(references),
        }
    )
    input_manifest_after = validate_frozen_inputs()
    before_compare = input_manifest_before.sort_values("path").reset_index(drop=True)
    after_compare = input_manifest_after.sort_values("path").reset_index(drop=True)
    pd.testing.assert_frame_equal(before_compare, after_compare)

    OUT.mkdir(parents=True, exist_ok=True)
    input_manifest_before.to_csv(SOURCE_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    capture_manifest([TOOL_PATH, TEST_PATH, PREDECL_PATH, IMPLEMENTATION_PLAN_PATH]).to_csv(
        CODE_MANIFEST_PATH, index=False, encoding="utf-8-sig"
    )
    product_days.to_csv(PRODUCT_DAYS_PATH, index=False, compression="gzip", encoding="utf-8-sig")
    states.to_csv(STATE_ROWS_PATH, index=False, compression="gzip", encoding="utf-8-sig")
    events.to_csv(EVENTS_PATH, index=False, encoding="utf-8-sig")
    references.to_csv(REFERENCES_PATH, index=False, encoding="utf-8-sig")
    (
        states.groupby(["feature_available", "slow_aligned", "fast_relation"], dropna=False)
        .agg(rows=("action_date", "size"), episodes=("episode_id", "nunique"), products=("product", "nunique"))
        .reset_index()
        .to_csv(STATE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    )
    build_event_summary(events).to_csv(EVENT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    with DATA_AUDIT_PATH.open("w", encoding="utf-8") as handle:
        json.dump(_json_ready(audit), handle, ensure_ascii=False, indent=2, allow_nan=False)
    with DECISION_PATH.open("w", encoding="utf-8") as handle:
        json.dump(_json_ready(decision), handle, ensure_ascii=False, indent=2, allow_nan=False)
    REPORT_PATH.write_text(
        build_report(
            audit=audit,
            metrics=metrics,
            gates=gates,
            decision=decision,
            bootstrap=bootstrap,
            economic_bootstrap=economic_bootstrap,
        ),
        encoding="utf-8",
    )
    return _json_ready(decision)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="run the frozen read-only attribution")
    args = parser.parse_args()
    if not args.run:
        parser.error("--run is required")
    print(json.dumps(run_attribution(), ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
