#!/usr/bin/env python3
"""Stage056: overlap audit for valuable add-risk modules.

This stage is read-only. It compares frozen lot-level proxy artifacts before
any combined A/B/C run, so we do not accidentally stack same-family risk or
mistake a proxy sum for a true engine result.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
UPSTREAM_LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
LINE = ROOT / "research/lines" / LINE_ID
UPSTREAM_LINE = ROOT / "research/lines" / UPSTREAM_LINE_ID
OUT = LINE / "outputs/stage056_combination_overlap_audit"
MODEL_TAG = "stage056_combination_overlap_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage056_combination_overlap_audit"
RUN_NOW = datetime.now()
RUN_TS = RUN_NOW.strftime("%Y%m%d_%H%M")
RUN_TIME_LABEL = RUN_NOW.strftime("%Y-%m-%d %H:%M CST")
STAGE_RECORD = LINE / "stages" / f"{RUN_TS}_stage056_combination_overlap_audit.md"
EPS = 1e-9


@dataclass(frozen=True)
class ModuleSpec:
    module: str
    path: Path
    delta_col: str
    fraction_col: str
    source_family: str
    description: str
    condition_filter: str | None = None


MODULE_SPECS: tuple[ModuleSpec, ...] = (
    ModuleSpec(
        module="stage010_quality_25pct",
        path=LINE
        / "outputs/stage010_quality_add_risk_proxy/"
        / "rebuilt_c9_v2_stage010_quality_add_risk_proxy_lot_deltas_stage010_quality_add_risk_proxy_v1.csv.gz",
        delta_col="stage010_proxy_delta_pnl",
        fraction_col="stage010_add_risk_fraction",
        source_family="quality",
        description="AI rank 1-8 + selected_volume>1，固定 +25% closed-lot proxy。",
    ),
    ModuleSpec(
        module="stage013_guarded_quality_25pct",
        path=LINE
        / "outputs/stage013_guarded_quality_add_risk_proxy/"
        / "rebuilt_c9_v2_stage013_guarded_quality_add_risk_proxy_lot_deltas_stage013_guarded_quality_add_risk_proxy_v1.csv.gz",
        delta_col="stage013_proxy_delta_pnl",
        fraction_col="stage013_add_risk_fraction",
        source_family="quality",
        description="Stage010 排除 risk_multiplier>=2 后，固定 +25% proxy。",
    ),
    ModuleSpec(
        module="stage014_guarded_floor_integer",
        path=LINE
        / "outputs/stage014_integer_add_risk_feasibility_audit/"
        / "rebuilt_c9_v2_stage014_integer_add_risk_feasibility_audit_lot_deltas_stage014_integer_add_risk_feasibility_audit_v1.csv.gz",
        delta_col="stage014_floor_proxy_delta_pnl",
        fraction_col="stage014_floor_add_fraction",
        source_family="quality_integer",
        description="Stage013 guarded 的 floor 整数手实现版本。",
    ),
    ModuleSpec(
        module="stage014_guarded_ceil_integer",
        path=LINE
        / "outputs/stage014_integer_add_risk_feasibility_audit/"
        / "rebuilt_c9_v2_stage014_integer_add_risk_feasibility_audit_lot_deltas_stage014_integer_add_risk_feasibility_audit_v1.csv.gz",
        delta_col="stage014_ceil_proxy_delta_pnl",
        fraction_col="stage014_ceil_add_fraction",
        source_family="quality_integer",
        description="Stage013 guarded 的 ceil 整数手实现版本；会系统性超配小手数。",
    ),
    ModuleSpec(
        module="stage022_guarded_xsmom12_not_opposed_25pct",
        path=LINE
        / "outputs/stage022_xsmom_entry_confirmation_proxy/"
        / "rebuilt_c9_v2_stage022_xsmom_entry_confirmation_proxy_lot_deltas_stage022_xsmom_entry_confirmation_proxy_v1.csv.gz",
        delta_col="stage022_proxy_delta_pnl",
        fraction_col="stage022_add_risk_fraction",
        source_family="quality_xsmom",
        description="Stage013 guarded quality 且前一交易日 xsmom12 未反向，固定 +25% proxy。",
        condition_filter="stage013_guarded_quality_xsmom12_not_opposed",
    ),
    ModuleSpec(
        module="stage052_contract_oi_share_ge50_25pct",
        path=UPSTREAM_LINE
        / "outputs/stage052_contract_oi_share_add_risk_proxy/"
        / "rebuilt_c9_stage052_contract_oi_share_add_risk_proxy_lot_deltas_stage052_contract_oi_share_add_risk_proxy_v1.csv",
        delta_col="stage052_proxy_delta_pnl",
        fraction_col="stage052_add_risk_fraction",
        source_family="contract_oi",
        description="上游逐合约 OI share>=50%，固定 +25% proxy；与质量链是不同信息源。",
    ),
)

STAGE008_GATE_PATH = (
    LINE
    / "outputs/stage008_pit_entry_risk_release_gate_engine/"
    / "rebuilt_c9_v2_stage008_pit_entry_risk_release_gate_engine_pit_gate_events_stage008_pit_entry_risk_release_gate_engine_v1.csv"
)

EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_normalized_events_{MODEL_TAG}.csv.gz"
MODULE_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_module_summary_{MODEL_TAG}.csv"
PAIRWISE_PATH = OUT / f"{OUTPUT_PREFIX}_pairwise_overlap_{MODEL_TAG}.csv"
COMBO_PATH = OUT / f"{OUTPUT_PREFIX}_capped_combo_audit_{MODEL_TAG}.csv"
STAGE008_CONFLICT_PATH = OUT / f"{OUTPUT_PREFIX}_stage008_conflict_audit_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return value


def _md_table(frame: pd.DataFrame, max_rows: int = 20) -> str:
    if frame.empty:
        return "_空_"
    return frame.head(max_rows).to_markdown(index=False)


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _numeric(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _normalize_id(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        as_float = float(text)
    except ValueError:
        return text
    if np.isfinite(as_float) and abs(as_float - round(as_float)) < EPS:
        return str(int(round(as_float)))
    return text


def _date_string(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.normalize().dt.strftime("%Y-%m-%d").fillna("")


def _event_key(frame: pd.DataFrame) -> pd.Series:
    start = frame["requested_start_month"].map(_normalize_id)
    open_id = frame["open_trade_id"].map(_normalize_id)
    lot_id = frame["lot_id"].map(_normalize_id)
    return start + "|" + open_id + "|" + lot_id


def _semantic_key(frame: pd.DataFrame) -> pd.Series:
    realized = _numeric(frame, "realized_pnl", 0.0).round(6).astype(str)
    return (
        frame["requested_start_month"].map(_normalize_id)
        + "|"
        + frame["vt_symbol"].astype(str)
        + "|"
        + frame["direction"].astype(str).str.lower()
        + "|"
        + _date_string(frame["entry_date"])
        + "|"
        + _date_string(frame["exit_date"])
        + "|"
        + realized
    )


def _entry_trade_key(frame: pd.DataFrame) -> pd.Series:
    return (
        frame["requested_start_month"].map(_normalize_id)
        + "|"
        + _date_string(frame["entry_date"])
        + "|"
        + frame["vt_symbol"].astype(str)
        + "|"
        + frame["direction"].astype(str).str.lower()
    )


def normalize_module(spec: ModuleSpec) -> pd.DataFrame:
    raw = _read_csv(spec.path)
    if spec.condition_filter is not None:
        if "condition" not in raw.columns:
            raise ValueError(f"{spec.path} missing condition column for {spec.condition_filter}")
        raw = raw[raw["condition"].astype(str).eq(spec.condition_filter)].copy()
    required = {
        "requested_start_month",
        "lot_id",
        "open_trade_id",
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "exit_date",
        "realized_pnl",
        spec.delta_col,
        spec.fraction_col,
    }
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"{spec.module} missing columns: {sorted(missing)}")

    result = raw.copy()
    result["module"] = spec.module
    result["source_family"] = spec.source_family
    result["description"] = spec.description
    result["event_key"] = _event_key(result)
    result["semantic_key"] = _semantic_key(result)
    result["entry_trade_key"] = _entry_trade_key(result)
    result["entry_date"] = pd.to_datetime(result["entry_date"], errors="coerce").dt.normalize()
    result["exit_date"] = pd.to_datetime(result["exit_date"], errors="coerce").dt.normalize()
    result["requested_start_month"] = result["requested_start_month"].map(_normalize_id)
    result["direction"] = result["direction"].astype(str).str.lower()
    result["realized_pnl"] = _numeric(result, "realized_pnl", 0.0).fillna(0.0)
    result["selected_volume"] = _numeric(result, "selected_volume", np.nan)
    result["ai_product_pool_rank"] = _numeric(result, "ai_product_pool_rank", np.nan)
    result["rsi_value"] = _numeric(result, "rsi_value", np.nan)
    result["risk_multiplier"] = _numeric(result, "risk_multiplier", np.nan)
    result["add_fraction"] = _numeric(result, spec.fraction_col, 0.0).fillna(0.0)
    result["delta_pnl"] = _numeric(result, spec.delta_col, 0.0).fillna(0.0)
    result["delta_col"] = spec.delta_col
    result["fraction_col"] = spec.fraction_col

    keep = [
        "module",
        "source_family",
        "description",
        "event_key",
        "semantic_key",
        "entry_trade_key",
        "requested_start_month",
        "lot_id",
        "open_trade_id",
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "exit_date",
        "realized_pnl",
        "selected_volume",
        "ai_product_pool_rank",
        "rsi_value",
        "risk_multiplier",
        "add_fraction",
        "delta_pnl",
        "delta_col",
        "fraction_col",
    ]
    return result[keep].reset_index(drop=True)


def load_all_modules(specs: tuple[ModuleSpec, ...] = MODULE_SPECS) -> pd.DataFrame:
    frames = [normalize_module(spec) for spec in specs]
    events = pd.concat(frames, ignore_index=True, sort=False)
    duplicated = events.duplicated(["module", "event_key"], keep=False)
    if duplicated.any():
        grouped = (
            events.groupby(["module", "event_key"], as_index=False, dropna=False)
            .agg(
                {
                    "source_family": "first",
                    "description": "first",
                    "semantic_key": "first",
                    "entry_trade_key": "first",
                    "requested_start_month": "first",
                    "lot_id": "first",
                    "open_trade_id": "first",
                    "vt_symbol": "first",
                    "product": "first",
                    "direction": "first",
                    "entry_date": "first",
                    "exit_date": "first",
                    "realized_pnl": "first",
                    "selected_volume": "first",
                    "ai_product_pool_rank": "first",
                    "rsi_value": "first",
                    "risk_multiplier": "first",
                    "add_fraction": "sum",
                    "delta_pnl": "sum",
                    "delta_col": "first",
                    "fraction_col": "first",
                }
            )
            .reset_index(drop=True)
        )
        return grouped
    return events


def build_module_summary(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for module, g in events.groupby("module", sort=False):
        rows.append(
            {
                "module": module,
                "source_family": str(g["source_family"].iloc[0]),
                "event_count": int(g["event_key"].nunique()),
                "row_count": int(len(g)),
                "start_count": int(g["requested_start_month"].nunique()),
                "product_count": int(g["product"].nunique()),
                "first_entry_date": g["entry_date"].min().date().isoformat(),
                "last_exit_date": g["exit_date"].max().date().isoformat(),
                "selected_realized_pnl": float(g["realized_pnl"].sum()),
                "proxy_delta_pnl": float(g["delta_pnl"].sum()),
                "positive_event_count": int((g["realized_pnl"] > 0).sum()),
                "negative_event_count": int((g["realized_pnl"] < 0).sum()),
                "mean_add_fraction": float(g["add_fraction"].mean()),
                "median_add_fraction": float(g["add_fraction"].median()),
                "max_add_fraction": float(g["add_fraction"].max()),
                "description": str(g["description"].iloc[0]),
            }
        )
    return pd.DataFrame(rows).sort_values("module").reset_index(drop=True)


def _module_index(events: pd.DataFrame, module: str, key_col: str) -> dict[str, dict[str, Any]]:
    subset = events[events["module"].eq(module)].copy()
    subset[key_col] = subset[key_col].astype(str)
    return subset.set_index(key_col).to_dict("index")


def build_pairwise_overlap(events: pd.DataFrame) -> pd.DataFrame:
    modules = list(events["module"].drop_duplicates())
    rows: list[dict[str, Any]] = []
    for i, module_a in enumerate(modules):
        for module_b in modules[i + 1 :]:
            a_exact = _module_index(events, module_a, "event_key")
            b_exact = _module_index(events, module_b, "event_key")
            a_semantic = set(events.loc[events["module"].eq(module_a), "semantic_key"].astype(str))
            b_semantic = set(events.loc[events["module"].eq(module_b), "semantic_key"].astype(str))
            exact_overlap = set(a_exact) & set(b_exact)
            exact_union = set(a_exact) | set(b_exact)
            semantic_overlap = a_semantic & b_semantic
            semantic_union = a_semantic | b_semantic
            a_only = set(a_exact) - set(b_exact)
            b_only = set(b_exact) - set(a_exact)
            rows.append(
                {
                    "module_a": module_a,
                    "module_b": module_b,
                    "a_count": len(a_exact),
                    "b_count": len(b_exact),
                    "exact_overlap_count": len(exact_overlap),
                    "exact_overlap_a_pct": len(exact_overlap) / len(a_exact) * 100.0 if a_exact else np.nan,
                    "exact_overlap_b_pct": len(exact_overlap) / len(b_exact) * 100.0 if b_exact else np.nan,
                    "exact_jaccard_pct": len(exact_overlap) / len(exact_union) * 100.0 if exact_union else np.nan,
                    "semantic_overlap_count": len(semantic_overlap),
                    "semantic_jaccard_pct": len(semantic_overlap) / len(semantic_union) * 100.0
                    if semantic_union
                    else np.nan,
                    "a_overlap_delta_pnl": float(sum(a_exact[key]["delta_pnl"] for key in exact_overlap)),
                    "b_overlap_delta_pnl": float(sum(b_exact[key]["delta_pnl"] for key in exact_overlap)),
                    "a_only_count": len(a_only),
                    "b_only_count": len(b_only),
                    "a_only_delta_pnl": float(sum(a_exact[key]["delta_pnl"] for key in a_only)),
                    "b_only_delta_pnl": float(sum(b_exact[key]["delta_pnl"] for key in b_only)),
                }
            )
    return pd.DataFrame(rows).sort_values(["module_a", "module_b"]).reset_index(drop=True)


def build_capped_combo(
    events: pd.DataFrame,
    combo_name: str,
    modules: list[str],
    *,
    cap_fraction: float,
    method: str = "sum_cap",
) -> dict[str, Any]:
    pieces = events[events["module"].isin(modules)].copy()
    if pieces.empty:
        return {
            "combo": combo_name,
            "modules": ",".join(modules),
            "method": method,
            "cap_fraction": cap_fraction,
            "event_count": 0,
            "total_proxy_delta_pnl": 0.0,
        }
    rows: list[dict[str, Any]] = []
    for event_key, g in pieces.groupby("event_key", sort=False):
        fractions = pd.to_numeric(g["add_fraction"], errors="coerce").fillna(0.0)
        realized_pnl = float(pd.to_numeric(g["realized_pnl"], errors="coerce").dropna().iloc[0])
        raw_sum = float(fractions.sum())
        raw_max = float(fractions.max())
        if method == "max":
            combo_fraction = min(raw_max, cap_fraction)
        elif method == "sum_cap":
            combo_fraction = min(raw_sum, cap_fraction)
        else:
            raise ValueError(f"unknown combo method: {method}")
        rows.append(
            {
                "event_key": event_key,
                "realized_pnl": realized_pnl,
                "module_count": int(g["module"].nunique()),
                "raw_fraction_sum": raw_sum,
                "raw_fraction_max": raw_max,
                "combo_fraction": combo_fraction,
                "combo_delta_pnl": realized_pnl * combo_fraction,
            }
        )
    combo = pd.DataFrame(rows)
    raw_proxy_sum = float(pieces["delta_pnl"].sum())
    total_proxy = float(combo["combo_delta_pnl"].sum())
    overlapped = combo[combo["module_count"] > 1]
    return {
        "combo": combo_name,
        "modules": ",".join(modules),
        "method": method,
        "cap_fraction": float(cap_fraction),
        "event_count": int(len(combo)),
        "overlap_event_count": int((combo["module_count"] > 1).sum()),
        "overlap_event_pct": float((combo["module_count"] > 1).mean() * 100.0),
        "raw_proxy_delta_sum_before_cap": raw_proxy_sum,
        "total_proxy_delta_pnl": total_proxy,
        "cap_or_max_penalty_pnl": raw_proxy_sum - total_proxy,
        "selected_realized_pnl": float(combo["realized_pnl"].sum()),
        "positive_event_count": int((combo["realized_pnl"] > 0).sum()),
        "negative_event_count": int((combo["realized_pnl"] < 0).sum()),
        "max_combo_fraction": float(combo["combo_fraction"].max()),
        "mean_combo_fraction": float(combo["combo_fraction"].mean()),
        "overlap_raw_fraction_sum_max": float(overlapped["raw_fraction_sum"].max()) if len(overlapped) else 0.0,
        "overlap_delta_pnl": float(overlapped["combo_delta_pnl"].sum()) if len(overlapped) else 0.0,
    }


def build_combo_audit(events: pd.DataFrame) -> pd.DataFrame:
    combos = [
        ("stage010_plus_oi_sum_cap50", ["stage010_quality_25pct", "stage052_contract_oi_share_ge50_25pct"], "sum_cap", 0.50),
        ("stage013_plus_oi_sum_cap50", ["stage013_guarded_quality_25pct", "stage052_contract_oi_share_ge50_25pct"], "sum_cap", 0.50),
        (
            "stage014_floor_plus_oi_sum_cap50",
            ["stage014_guarded_floor_integer", "stage052_contract_oi_share_ge50_25pct"],
            "sum_cap",
            0.50,
        ),
        (
            "stage014_ceil_plus_oi_sum_cap50",
            ["stage014_guarded_ceil_integer", "stage052_contract_oi_share_ge50_25pct"],
            "sum_cap",
            0.50,
        ),
        (
            "stage022_xsmom_plus_oi_sum_cap50",
            ["stage022_guarded_xsmom12_not_opposed_25pct", "stage052_contract_oi_share_ge50_25pct"],
            "sum_cap",
            0.50,
        ),
        (
            "stage014_floor_or_oi_max25",
            ["stage014_guarded_floor_integer", "stage052_contract_oi_share_ge50_25pct"],
            "max",
            0.25,
        ),
        (
            "stage022_xsmom_or_oi_max25",
            ["stage022_guarded_xsmom12_not_opposed_25pct", "stage052_contract_oi_share_ge50_25pct"],
            "max",
            0.25,
        ),
    ]
    rows = [build_capped_combo(events, name, modules, method=method, cap_fraction=cap) for name, modules, method, cap in combos]
    return pd.DataFrame(rows).sort_values("total_proxy_delta_pnl", ascending=False).reset_index(drop=True)


def load_stage008_gate() -> pd.DataFrame:
    gate = _read_csv(STAGE008_GATE_PATH)
    required = {
        "requested_start_month",
        "date",
        "vt_symbol",
        "direction",
        "stage008_pit_gate_selected_volume_before",
        "stage008_pit_gate_selected_volume_after",
        "stage008_pit_gate_reduced_volume",
    }
    missing = required - set(gate.columns)
    if missing:
        raise ValueError(f"Stage008 gate missing columns: {sorted(missing)}")
    result = gate.copy()
    result["requested_start_month"] = result["requested_start_month"].map(_normalize_id)
    result["entry_date"] = pd.to_datetime(result["date"], errors="coerce").dt.normalize()
    result["direction"] = result["direction"].astype(str).str.lower()
    result["entry_trade_key"] = _entry_trade_key(result)
    result["stage008_pit_gate_reduced_volume"] = _numeric(result, "stage008_pit_gate_reduced_volume", 0.0).fillna(0.0)
    return result


def build_stage008_conflict_audit(events: pd.DataFrame, gate: pd.DataFrame) -> pd.DataFrame:
    gate_keys = set(gate["entry_trade_key"].astype(str))
    rows: list[dict[str, Any]] = []
    for module, g in events.groupby("module", sort=False):
        mask = g["entry_trade_key"].astype(str).isin(gate_keys)
        conflict = g.loc[mask]
        rank = pd.to_numeric(g.get("ai_product_pool_rank"), errors="coerce")
        rsi = pd.to_numeric(g.get("rsi_value"), errors="coerce")
        selected_volume = pd.to_numeric(g.get("selected_volume"), errors="coerce")
        direction = g["direction"].astype(str).str.lower()
        stage008_like_shape = (
            rank.ge(5)
            & rank.le(8)
            & selected_volume.gt(1)
            & ((direction.eq("long") & rsi.ge(75.0)) | (direction.eq("short") & rsi.le(25.0)))
        )
        shape_conflict = g.loc[stage008_like_shape.fillna(False)]
        rows.append(
            {
                "module": module,
                "event_count": int(g["event_key"].nunique()),
                "stage008_conflict_event_count": int(conflict["event_key"].nunique()),
                "stage008_conflict_event_pct": float(conflict["event_key"].nunique() / g["event_key"].nunique() * 100.0)
                if g["event_key"].nunique()
                else np.nan,
                "module_delta_pnl": float(g["delta_pnl"].sum()),
                "stage008_conflict_delta_pnl": float(conflict["delta_pnl"].sum()),
                "stage008_conflict_negative_delta_pnl": float(conflict.loc[conflict["delta_pnl"] < 0, "delta_pnl"].sum()),
                "stage008_conflict_positive_delta_pnl": float(conflict.loc[conflict["delta_pnl"] > 0, "delta_pnl"].sum()),
                "stage008_like_shape_event_count": int(shape_conflict["event_key"].nunique()),
                "stage008_like_shape_event_pct": float(shape_conflict["event_key"].nunique() / g["event_key"].nunique() * 100.0)
                if g["event_key"].nunique()
                else np.nan,
                "stage008_like_shape_delta_pnl": float(shape_conflict["delta_pnl"].sum()),
                "stage008_like_shape_negative_delta_pnl": float(
                    shape_conflict.loc[shape_conflict["delta_pnl"] < 0, "delta_pnl"].sum()
                ),
                "stage008_like_shape_positive_delta_pnl": float(
                    shape_conflict.loc[shape_conflict["delta_pnl"] > 0, "delta_pnl"].sum()
                ),
                "unique_stage008_gate_events": int(len(gate_keys)),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["stage008_like_shape_event_pct", "stage008_conflict_event_pct"], ascending=False
    ).reset_index(drop=True)


def _lookup_pair(pairwise: pd.DataFrame, module_a: str, module_b: str) -> dict[str, Any]:
    mask = (
        (pairwise["module_a"].eq(module_a) & pairwise["module_b"].eq(module_b))
        | (pairwise["module_a"].eq(module_b) & pairwise["module_b"].eq(module_a))
    )
    if not mask.any():
        return {}
    return pairwise.loc[mask].iloc[0].to_dict()


def build_decision(
    module_summary: pd.DataFrame,
    pairwise: pd.DataFrame,
    combo: pd.DataFrame,
    stage008_conflict: pd.DataFrame,
) -> dict[str, Any]:
    stage013_in_stage010 = _lookup_pair(pairwise, "stage010_quality_25pct", "stage013_guarded_quality_25pct")
    floor_in_stage013 = _lookup_pair(pairwise, "stage013_guarded_quality_25pct", "stage014_guarded_floor_integer")
    xsmom_in_stage013 = _lookup_pair(pairwise, "stage013_guarded_quality_25pct", "stage022_guarded_xsmom12_not_opposed_25pct")
    ceil_vs_oi = _lookup_pair(pairwise, "stage014_guarded_ceil_integer", "stage052_contract_oi_share_ge50_25pct")
    floor_vs_oi = _lookup_pair(pairwise, "stage014_guarded_floor_integer", "stage052_contract_oi_share_ge50_25pct")
    xsmom_vs_oi = _lookup_pair(pairwise, "stage022_guarded_xsmom12_not_opposed_25pct", "stage052_contract_oi_share_ge50_25pct")

    best_combo = combo.iloc[0].to_dict() if not combo.empty else {}
    conflict_top = stage008_conflict.iloc[0].to_dict() if not stage008_conflict.empty else {}
    quality_side_overlap_with_oi = float(
        np.nanmean(
            [
                floor_vs_oi.get("exact_overlap_a_pct", np.nan),
                ceil_vs_oi.get("exact_overlap_a_pct", np.nan),
                xsmom_vs_oi.get("exact_overlap_a_pct", np.nan),
            ]
        )
    )
    oi_side_overlap_with_quality = float(
        np.nanmean(
            [
                floor_vs_oi.get("exact_overlap_b_pct", np.nan),
                ceil_vs_oi.get("exact_overlap_b_pct", np.nan),
                xsmom_vs_oi.get("exact_overlap_b_pct", np.nan),
            ]
        )
    )
    mean_quality_oi_jaccard = float(
        np.nanmean(
            [
                floor_vs_oi.get("exact_jaccard_pct", np.nan),
                ceil_vs_oi.get("exact_jaccard_pct", np.nan),
                xsmom_vs_oi.get("exact_jaccard_pct", np.nan),
            ]
        )
    )

    if quality_side_overlap_with_oi < 45.0 or (oi_side_overlap_with_quality < 40.0 and mean_quality_oi_jaccard < 35.0):
        next_step = "allow_stage057_capped_quality_plus_oi_proxy_audit_with_overlap_warning"
    else:
        next_step = "hold_combo_until_more_independent_source"

    return {
        "stage": "Stage056",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "run_time": RUN_TIME_LABEL,
        "baseline": "Official C9/15w Stage847 remains formal baseline; this stage does not run a new true engine.",
        "hypothesis": "同源质量链只能择一；质量/动量确认与逐合约 OI 如果重合低，可以用统一风险预算做 capped combination。",
        "overfit_reflection_before": "否。本阶段只做预声明 overlap/risk-budget 审计，不新增阈值、品种黑名单或坏窗口修补。",
        "continued_value_before": "是。它直接回答用户关心的叠加问题，并避免把多个 proxy 曲线机械相加。",
        "stage013_overlap_pct_of_stage010": stage013_in_stage010.get("exact_overlap_a_pct"),
        "stage014_floor_overlap_pct_of_stage013": floor_in_stage013.get("exact_overlap_b_pct"),
        "stage022_overlap_pct_of_stage013": xsmom_in_stage013.get("exact_overlap_b_pct"),
        "stage014_floor_vs_oi_overlap_pct_of_floor": floor_vs_oi.get("exact_overlap_a_pct"),
        "stage014_ceil_vs_oi_overlap_pct_of_ceil": ceil_vs_oi.get("exact_overlap_a_pct"),
        "stage022_vs_oi_overlap_pct_of_xsmom": xsmom_vs_oi.get("exact_overlap_a_pct"),
        "mean_quality_side_overlap_with_oi_pct": quality_side_overlap_with_oi,
        "mean_oi_side_overlap_with_quality_pct": oi_side_overlap_with_quality,
        "mean_quality_oi_jaccard_pct": mean_quality_oi_jaccard,
        "best_proxy_combo_by_lot_delta": best_combo.get("combo"),
        "best_proxy_combo_delta_pnl": best_combo.get("total_proxy_delta_pnl"),
        "largest_stage008_exact_conflict_module": conflict_top.get("module"),
        "largest_stage008_exact_conflict_pct": conflict_top.get("stage008_conflict_event_pct"),
        "largest_stage008_like_shape_module": conflict_top.get("module"),
        "largest_stage008_like_shape_pct": conflict_top.get("stage008_like_shape_event_pct"),
        "decision": "no_promotion_readonly_overlap_audit",
        "next_step": next_step,
        "overfit_reflection_after": "否。结果仅用于缩小下一步候选集合，未根据收益曲线调参。",
        "continued_value_after": "是。若 OI 与质量链 overlap 足够低，下一阶段只允许 capped proxy/真实引擎验证；若 overlap 高则停止叠加。",
        "orders_api_called": 0,
        "ctp_connected": False,
        "live_or_email_touched": False,
    }


def write_report(
    module_summary: pd.DataFrame,
    pairwise: pd.DataFrame,
    combo: pd.DataFrame,
    stage008_conflict: pd.DataFrame,
    decision: dict[str, Any],
) -> str:
    quality_pairs = pairwise[
        pairwise["module_a"].str.contains("stage010|stage013|stage014|stage022", regex=True)
        & pairwise["module_b"].str.contains("stage010|stage013|stage014|stage022", regex=True)
    ].copy()
    oi_pairs = pairwise[pairwise["module_b"].eq("stage052_contract_oi_share_ge50_25pct")].copy()
    text = f"""# Stage056 组合重合/风险叠加审计

- 运行时间：{RUN_TIME_LABEL}
- 研究线：`{LINE_ID}`
- 基准：当前正式基准仍是 C9/15w Stage847；本阶段不改正式版、不跑真实引擎、不触发订单 API。
- 候选假设：同源质量链只能择一；只有质量/动量确认与逐合约 OI 在交易事件上有足够互补，才允许进入 capped combination 的下一阶段。
- 外部调研判断：meta-labeling/二级 sizing 的本质是过滤或调节主信号，而不是无上限叠加；trend-following 的长期价值依赖跨市场右尾和风险预算，组合要先审计相关性与风险贡献。

## 模块汇总

{_md_table(module_summary, 20)}

## 同源质量链重合

{_md_table(quality_pairs, 30)}

## OI 与质量链重合

{_md_table(oi_pairs, 20)}

## capped 组合只读估算

{_md_table(combo, 20)}

## Stage008 风险释放冲突审计

{_md_table(stage008_conflict, 20)}

## 结论

- 决策：`{decision['decision']}`，不晋级、不改实盘。
- 下一步：`{decision['next_step']}`。
- 过拟合反思：{decision['overfit_reflection_after']}
- 继续价值反思：{decision['continued_value_after']}
"""
    REPORT_PATH.write_text(text, encoding="utf-8")
    STAGE_RECORD.write_text(text, encoding="utf-8")
    return text


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    events = load_all_modules()
    module_summary = build_module_summary(events)
    pairwise = build_pairwise_overlap(events)
    combo = build_combo_audit(events)
    gate = load_stage008_gate()
    stage008_conflict = build_stage008_conflict_audit(events, gate)
    decision = build_decision(module_summary, pairwise, combo, stage008_conflict)

    events.to_csv(EVENTS_PATH, index=False)
    module_summary.to_csv(MODULE_SUMMARY_PATH, index=False)
    pairwise.to_csv(PAIRWISE_PATH, index=False)
    combo.to_csv(COMBO_PATH, index=False)
    stage008_conflict.to_csv(STAGE008_CONFLICT_PATH, index=False)
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2, default=_json_safe) + "\n", encoding="utf-8")
    write_report(module_summary, pairwise, combo, stage008_conflict, decision)

    print(json.dumps(decision, ensure_ascii=False, indent=2, default=_json_safe))


if __name__ == "__main__":
    main()
