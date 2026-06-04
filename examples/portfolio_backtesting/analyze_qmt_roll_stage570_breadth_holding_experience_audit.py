from __future__ import annotations

from datetime import datetime
import json
import math
import os
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage544_family_constrained_selector_diagnostic as s544


MODEL_TAG = "stage570_breadth_holding_experience_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage570_breadth_holding_experience_audit"

STAGE557_TAG = "stage557_breadth_low_single_risk_pool_audit_v1"
STAGE557_PREFIX = "qmt_roll_stage557_breadth_low_single_risk_pool_audit"
COMBINED_DAILY_IN = OUTPUT_DIR / f"{STAGE557_PREFIX}_combined_daily_{STAGE557_TAG}.csv"
SUMMARY_IN = OUTPUT_DIR / f"{STAGE557_PREFIX}_summary_{STAGE557_TAG}.csv"
SAT_PRODUCT_IN = OUTPUT_DIR / f"{STAGE557_PREFIX}_satellite_product_harvest_{STAGE557_TAG}.csv"
SAT_FAMILY_IN = OUTPUT_DIR / f"{STAGE557_PREFIX}_satellite_family_harvest_{STAGE557_TAG}.csv"
ENTRY_SNAPSHOTS_IN = OUTPUT_DIR / f"{STAGE557_PREFIX}_entry_snapshots_{STAGE557_TAG}.csv"
ANNUAL_SELECTION_IN = OUTPUT_DIR / f"{STAGE557_PREFIX}_annual_selection_{STAGE557_TAG}.csv"

STAGE556_TAG = "stage556_stage252_whitelist_guard_fixed_replay_v1"
STAGE556_PREFIX = "qmt_roll_stage556_stage252_whitelist_guard_fixed_replay"
STAGE556_SAT_PRODUCT_IN = OUTPUT_DIR / f"{STAGE556_PREFIX}_satellite_product_harvest_{STAGE556_TAG}.csv"

STAGE526_POSITIONS_IN = (
    OUTPUT_DIR / "qmt_roll_stage526_productcap25_breadth_frontier_positions_stage526_productcap25_breadth_frontier_v1.csv"
)

HOLDING_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_holding_detail_{MODEL_TAG}.csv"
HOLDING_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_holding_summary_{MODEL_TAG}.csv"
CONTRIB_ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contribution_annual_{MODEL_TAG}.csv"
CONTRIB_PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contribution_product_{MODEL_TAG}.csv"
CONTRIB_FAMILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contribution_family_{MODEL_TAG}.csv"
CONTRIB_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contribution_summary_{MODEL_TAG}.csv"
CROWDING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_crowding_summary_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

BASE_VARIANT = "stage526_r080_pc25_maxpos4"
STAGE256_VARIANT = "dynamic_prevtop6_r050_pc15_maxpos3"
WIDTH_VARIANTS = (
    "breadth_all_noncore_r020_famcap20_corr5075_maxpos8",
    "breadth_prevpos_r020_famcap20_corr5075_maxpos8",
    "breadth_prevpos_r015_famcap15_corr5075_maxpos10",
)
VARIANTS = (BASE_VARIANT, STAGE256_VARIANT, *WIDTH_VARIANTS)
CORE_POSITION_VARIANT = "r080_pc25_maxpos4"
START_DATE = pd.Timestamp("2020-01-02")

LABELS = {
    BASE_VARIANT: "Stage526",
    STAGE256_VARIANT: "Stage256 upper",
    "breadth_all_noncore_r020_famcap20_corr5075_maxpos8": "All noncore r020",
    "breadth_prevpos_r020_famcap20_corr5075_maxpos8": "Prev+ r020",
    "breadth_prevpos_r015_famcap15_corr5075_maxpos10": "Prev+ r015",
}

CORE_EXTRA_FAMILY: dict[str, tuple[str, str]] = {
    "AP.CZCE": ("soft_agri", "apple soft/agri"),
    "CF.CZCE": ("soft_agri", "cotton soft/agri"),
    "FG.CZCE": ("black_ferrous", "glass construction chain"),
    "MA.CZCE": ("petrochem", "methanol petrochem"),
    "OI.CZCE": ("grains_oilseeds", "rapeseed oil"),
    "SA.CZCE": ("petrochem", "soda ash chemical"),
    "SH.CZCE": ("petrochem", "caustic soda chemical"),
    "SM.CZCE": ("black_ferrous", "silicomanganese"),
    "au.SHFE": ("precious_metals", "gold"),
    "cu.SHFE": ("base_metals", "copper"),
    "fu.SHFE": ("energy_oil", "fuel oil"),
    "hc.SHFE": ("black_ferrous", "hot rolled coil"),
    "rb.SHFE": ("black_ferrous", "rebar"),
    "ru.SHFE": ("rubber", "rubber"),
    "sp.SHFE": ("other", "pulp"),
    "jm.DCE": ("black_ferrous", "coking coal"),
    "lh.DCE": ("livestock", "live hog"),
    "lc.GFEX": ("base_metals", "battery metal"),
    "si.GFEX": ("base_metals", "industrial silicon"),
}


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default).astype(float)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _variant_label(variant: str) -> str:
    return LABELS.get(variant, variant)


def _to_markdown_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 20) -> str:
    if frame.empty:
        return "_empty_"
    view = frame.copy()
    if columns is not None:
        view = view[[col for col in columns if col in view.columns]]
    if len(view) > max_rows:
        view = view.head(max_rows)
    return view.to_markdown(index=False)


def _family_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for key, (family, _) in {**s544.PRODUCT_FAMILY, **CORE_EXTRA_FAMILY}.items():
        lookup[key] = family
        if "." in key:
            product, exchange = key.split(".", 1)
            lookup[f"{product.lower()}.{exchange.upper()}"] = family
            lookup[f"{product.upper()}.{exchange.upper()}"] = family
    return lookup


def _product_family(product_vt_symbol: str, lookup: dict[str, str]) -> str:
    key = str(product_vt_symbol)
    if key in lookup:
        return lookup[key]
    if "." in key:
        product, exchange = key.split(".", 1)
        for candidate in (f"{product}.{exchange.upper()}", f"{product.lower()}.{exchange.upper()}", f"{product.upper()}.{exchange.upper()}"):
            if candidate in lookup:
                return lookup[candidate]
        return exchange.upper()
    return "unknown"


def build_holding_metrics(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for variant, group in daily[daily["variant"].isin(VARIANTS)].groupby("variant"):
        group = group.sort_values("date").copy()
        equity = _num(group, "account_equity").to_numpy(dtype=float)
        dates = pd.to_datetime(group["date"]).to_numpy()
        for horizon in (63, 126):
            horizon_rows: list[dict[str, Any]] = []
            for idx in range(0, max(0, len(group) - horizon)):
                start_equity = equity[idx]
                end_equity = equity[idx + horizon]
                if start_equity <= 0:
                    continue
                window = equity[idx : idx + horizon + 1]
                final_return = (end_equity / start_equity - 1.0) * 100.0
                max_adverse = (np.nanmin(window) / start_equity - 1.0) * 100.0
                row = {
                    "variant": variant,
                    "label": _variant_label(variant),
                    "horizon_days": horizon,
                    "start_date": pd.Timestamp(dates[idx]).date().isoformat(),
                    "end_date": pd.Timestamp(dates[idx + horizon]).date().isoformat(),
                    "start_equity": float(start_equity),
                    "end_equity": float(end_equity),
                    "final_return_pct": float(final_return),
                    "max_adverse_pct": float(max_adverse),
                }
                rows.append(row)
                horizon_rows.append(row)
            hframe = pd.DataFrame(horizon_rows)
            if hframe.empty:
                continue
            worst = hframe.sort_values("final_return_pct").iloc[0]
            adverse = hframe.sort_values("max_adverse_pct").iloc[0]
            summary_rows.append(
                {
                    "variant": variant,
                    "label": _variant_label(variant),
                    "horizon_days": horizon,
                    "sample_count": int(len(hframe)),
                    "mean_return_pct": float(hframe["final_return_pct"].mean()),
                    "median_return_pct": float(hframe["final_return_pct"].median()),
                    "p10_return_pct": float(hframe["final_return_pct"].quantile(0.10)),
                    "p05_return_pct": float(hframe["final_return_pct"].quantile(0.05)),
                    "min_return_pct": float(hframe["final_return_pct"].min()),
                    "negative_rate_pct": float((hframe["final_return_pct"] < 0).mean() * 100.0),
                    "mae_p10_pct": float(hframe["max_adverse_pct"].quantile(0.10)),
                    "mae_p05_pct": float(hframe["max_adverse_pct"].quantile(0.05)),
                    "mae_min_pct": float(hframe["max_adverse_pct"].min()),
                    "mae_below_10pct_rate": float((hframe["max_adverse_pct"] <= -10.0).mean() * 100.0),
                    "worst_return_start_date": str(worst["start_date"]),
                    "worst_return_end_date": str(worst["end_date"]),
                    "worst_adverse_start_date": str(adverse["start_date"]),
                    "worst_adverse_end_date": str(adverse["end_date"]),
                }
            )
    detail = pd.DataFrame(rows)
    summary = pd.DataFrame(summary_rows)
    base = summary[summary["variant"].eq(BASE_VARIANT)].set_index("horizon_days")
    delta_cols = ["p10_return_pct", "p05_return_pct", "min_return_pct", "negative_rate_pct", "mae_p05_pct", "mae_min_pct"]
    for idx, row in summary.iterrows():
        horizon = int(row["horizon_days"])
        if horizon not in base.index:
            continue
        for col in delta_cols:
            summary.loc[idx, f"{col}_delta_vs_stage526"] = float(row[col] - base.loc[horizon, col])
    return detail, summary


def _core_product_contribution() -> pd.DataFrame:
    positions = _read_csv(
        STAGE526_POSITIONS_IN,
        usecols=["date", "vt_symbol", "net_pnl", "variant"],
    )
    positions = positions[positions["variant"].eq(CORE_POSITION_VARIANT)].copy()
    positions["date"] = pd.to_datetime(positions["date"], errors="coerce")
    positions = positions[positions["date"].ge(START_DATE)].copy()
    positions["net_pnl"] = _num(positions, "net_pnl")
    positions["product"] = positions["vt_symbol"].astype(str).str.extract(r"^([A-Za-z]+)")[0]
    positions["exchange"] = positions["vt_symbol"].astype(str).str.split(".").str[-1].str.upper()
    positions["product_vt_symbol"] = positions["product"].astype(str) + "." + positions["exchange"].astype(str)
    positions["year"] = positions["date"].dt.year.astype(int)
    core = (
        positions.groupby(["year", "product_vt_symbol"], as_index=False)["net_pnl"]
        .sum()
        .rename(columns={"net_pnl": "core_product_net_pnl"})
    )
    return core


def _satellite_product_contribution() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if STAGE556_SAT_PRODUCT_IN.exists():
        top6 = _read_csv(STAGE556_SAT_PRODUCT_IN)
        frames.append(top6)
    if SAT_PRODUCT_IN.exists():
        width = _read_csv(SAT_PRODUCT_IN)
        frames.append(width)
    if not frames:
        return pd.DataFrame(columns=["variant", "year", "product_vt_symbol", "satellite_product_net_pnl"])
    frame = pd.concat(frames, ignore_index=True)
    frame = frame[frame["variant"].isin([STAGE256_VARIANT, *WIDTH_VARIANTS])].copy()
    frame["year"] = _num(frame, "year").astype(int)
    frame["satellite_product_net_pnl"] = _num(frame, "satellite_product_net_pnl")
    return frame[["variant", "year", "product_vt_symbol", "satellite_product_net_pnl"]]


def build_contribution_metrics() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    lookup = _family_lookup()
    core = _core_product_contribution()
    sat = _satellite_product_contribution()
    product_rows: list[pd.DataFrame] = []
    for variant in VARIANTS:
        current = core.copy()
        current["variant"] = variant
        if variant != BASE_VARIANT and not sat.empty:
            add = sat[sat["variant"].eq(variant)].copy()
            if not add.empty:
                current = current.merge(
                    add,
                    on=["variant", "year", "product_vt_symbol"],
                    how="outer",
                )
        if "satellite_product_net_pnl" not in current.columns:
            current["satellite_product_net_pnl"] = 0.0
        current["core_product_net_pnl"] = _num(current, "core_product_net_pnl")
        current["satellite_product_net_pnl"] = _num(current, "satellite_product_net_pnl")
        current["product_net_pnl"] = _num(current, "core_product_net_pnl") + _num(current, "satellite_product_net_pnl")
        current["label"] = _variant_label(variant)
        current["product_family"] = current["product_vt_symbol"].astype(str).map(lambda item: _product_family(item, lookup))
        product_rows.append(current)
    product = pd.concat(product_rows, ignore_index=True)
    product = (
        product.groupby(["variant", "label", "year", "product_vt_symbol", "product_family"], as_index=False)
        .agg(
            core_product_net_pnl=("core_product_net_pnl", "sum"),
            satellite_product_net_pnl=("satellite_product_net_pnl", "sum"),
            product_net_pnl=("product_net_pnl", "sum"),
        )
        .sort_values(["variant", "year", "product_net_pnl"], ascending=[True, True, False])
    )
    family = (
        product.groupby(["variant", "label", "year", "product_family"], as_index=False)
        .agg(
            family_net_pnl=("product_net_pnl", "sum"),
            product_count=("product_vt_symbol", "nunique"),
        )
        .sort_values(["variant", "year", "family_net_pnl"], ascending=[True, True, False])
    )

    annual_rows: list[dict[str, Any]] = []
    for (variant, year), group in product.groupby(["variant", "year"]):
        label = _variant_label(str(variant))
        positive = group[group["product_net_pnl"] > 0.0].sort_values("product_net_pnl", ascending=False)
        negative = group[group["product_net_pnl"] < 0.0].sort_values("product_net_pnl")
        pos_sum = float(positive["product_net_pnl"].sum())
        top1 = positive.head(1)
        top3 = positive.head(3)
        fgroup = family[(family["variant"].eq(variant)) & (family["year"].eq(year))]
        fpos = fgroup[fgroup["family_net_pnl"] > 0.0].sort_values("family_net_pnl", ascending=False)
        fpos_sum = float(fpos["family_net_pnl"].sum())
        annual_rows.append(
            {
                "variant": variant,
                "label": label,
                "year": int(year),
                "total_product_pnl": float(group["product_net_pnl"].sum()),
                "positive_product_pnl": pos_sum,
                "negative_product_pnl": float(negative["product_net_pnl"].sum()),
                "positive_product_count": int(len(positive)),
                "negative_product_count": int(len(negative)),
                "top_product": str(top1["product_vt_symbol"].iloc[0]) if not top1.empty else "",
                "top_product_pnl": float(top1["product_net_pnl"].iloc[0]) if not top1.empty else 0.0,
                "top1_product_positive_share_pct": float(top1["product_net_pnl"].sum() / pos_sum * 100.0) if pos_sum > 0 else 0.0,
                "top3_product_positive_share_pct": float(top3["product_net_pnl"].sum() / pos_sum * 100.0) if pos_sum > 0 else 0.0,
                "top_family": str(fpos["product_family"].iloc[0]) if not fpos.empty else "",
                "top_family_pnl": float(fpos["family_net_pnl"].iloc[0]) if not fpos.empty else 0.0,
                "positive_family_count": int(len(fpos)),
                "top1_family_positive_share_pct": float(fpos["family_net_pnl"].iloc[0] / fpos_sum * 100.0) if fpos_sum > 0 else 0.0,
            }
        )
    annual = pd.DataFrame(annual_rows)
    summary = (
        annual.groupby(["variant", "label"], as_index=False)
        .agg(
            avg_top1_product_share_pct=("top1_product_positive_share_pct", "mean"),
            max_top1_product_share_pct=("top1_product_positive_share_pct", "max"),
            years_top1_product_over35=("top1_product_positive_share_pct", lambda s: int((s > 35.0).sum())),
            avg_top3_product_share_pct=("top3_product_positive_share_pct", "mean"),
            avg_top1_family_share_pct=("top1_family_positive_share_pct", "mean"),
            max_top1_family_share_pct=("top1_family_positive_share_pct", "max"),
            years_top1_family_over50=("top1_family_positive_share_pct", lambda s: int((s > 50.0).sum())),
            avg_positive_product_count=("positive_product_count", "mean"),
            min_positive_product_count=("positive_product_count", "min"),
            avg_positive_family_count=("positive_family_count", "mean"),
            total_combined_product_pnl=("total_product_pnl", "sum"),
        )
        .sort_values("variant")
    )
    base = summary[summary["variant"].eq(BASE_VARIANT)].iloc[0]
    summary["avg_top1_product_share_delta_vs_stage526"] = summary["avg_top1_product_share_pct"] - float(
        base["avg_top1_product_share_pct"]
    )
    summary["avg_top1_family_share_delta_vs_stage526"] = summary["avg_top1_family_share_pct"] - float(
        base["avg_top1_family_share_pct"]
    )
    return annual, product, family, summary


def build_crowding_summary() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if ENTRY_SNAPSHOTS_IN.exists():
        snapshots = _read_csv(ENTRY_SNAPSHOTS_IN)
        snapshots = snapshots[snapshots["variant"].isin(WIDTH_VARIANTS)].copy()
        snapshots["same_direction_correlation_gate_weight"] = _num(snapshots, "same_direction_correlation_gate_weight", 1.0)
        snapshots["same_direction_correlation_max_corr"] = _num(snapshots, "same_direction_correlation_max_corr")
        snapshots["same_direction_correlation_avg_corr"] = _num(snapshots, "same_direction_correlation_avg_corr")
        snapshots["is_opened_num"] = _num(snapshots, "is_opened").astype(int)
        for variant, group in snapshots.groupby("variant"):
            opened = group[group["is_opened_num"].eq(1)]
            rows.append(
                {
                    "variant": variant,
                    "label": _variant_label(variant),
                    "candidate_count": int(len(group)),
                    "opened_count": int(len(opened)),
                    "corr_scaled_candidate_count": int((group["same_direction_correlation_gate_weight"] < 0.999).sum()),
                    "corr_scaled_opened_count": int((opened["same_direction_correlation_gate_weight"] < 0.999).sum()),
                    "candidate_corr_gt50_count": int((group["same_direction_correlation_max_corr"] > 0.50).sum()),
                    "candidate_corr_gt75_count": int((group["same_direction_correlation_max_corr"] > 0.75).sum()),
                    "opened_corr_gt50_count": int((opened["same_direction_correlation_max_corr"] > 0.50).sum()),
                    "opened_corr_gt75_count": int((opened["same_direction_correlation_max_corr"] > 0.75).sum()),
                    "max_same_direction_corr": float(group["same_direction_correlation_max_corr"].max()) if len(group) else 0.0,
                    "avg_same_direction_corr_opened": float(opened["same_direction_correlation_avg_corr"].mean())
                    if len(opened)
                    else 0.0,
                    "avg_corr_gate_weight_opened": float(opened["same_direction_correlation_gate_weight"].mean())
                    if len(opened)
                    else 0.0,
                }
            )
    crowding = pd.DataFrame(rows)
    if ANNUAL_SELECTION_IN.exists() and not crowding.empty:
        selection = _read_csv(ANNUAL_SELECTION_IN)
        selection = selection[selection["variant"].isin(WIDTH_VARIANTS)].copy()
        sel_summary = (
            selection.groupby("variant", as_index=False)
            .agg(
                avg_selected_count=("selected_count", "mean"),
                avg_family_count=("family_count", "mean"),
                avg_family_max_count=("family_max_count", "mean"),
                max_family_max_count=("family_max_count", "max"),
                avg_abs_core_corr=("avg_abs_core_corr", "mean"),
                max_abs_core_corr=("max_abs_core_corr", "max"),
            )
        )
        crowding = crowding.merge(sel_summary, on="variant", how="left")
    return crowding


def build_gates(summary: pd.DataFrame, holding: pd.DataFrame, contrib: pd.DataFrame, crowding: pd.DataFrame) -> pd.DataFrame:
    base_summary = summary[summary["variant"].eq(BASE_VARIANT)].iloc[0]
    base_holding = holding[holding["variant"].eq(BASE_VARIANT)].set_index("horizon_days")
    rows: list[dict[str, Any]] = []
    for variant in VARIANTS:
        label = _variant_label(variant)
        srow = summary[summary["variant"].eq(variant)].iloc[0]
        crow = contrib[contrib["variant"].eq(variant)].iloc[0]
        deployable = variant not in {STAGE256_VARIANT}
        is_width = variant in WIDTH_VARIANTS
        for metric, passed, actual, threshold in [
            (
                "return_no_material_loss",
                float(srow["return_vs_stage526_pct"]) >= 98.0,
                f"{float(srow['return_vs_stage526_pct']):.4f}%",
                ">=98% vs Stage526",
            ),
            (
                "max_dd_no_degrade",
                float(srow["max_dd_pct"]) >= float(base_summary["max_dd_pct"]),
                f"{float(srow['max_dd_pct']):.4f}% vs {float(base_summary['max_dd_pct']):.4f}%",
                ">= Stage526 max DD",
            ),
            (
                "ulcer_no_degrade",
                float(srow["ulcer_pct"]) <= float(base_summary["ulcer_pct"]),
                f"{float(srow['ulcer_pct']):.4f} vs {float(base_summary['ulcer_pct']):.4f}",
                "<= Stage526 Ulcer",
            ),
            (
                "product_concentration_not_worse",
                float(crow["avg_top1_product_share_pct"]) <= float(
                    contrib[contrib["variant"].eq(BASE_VARIANT)]["avg_top1_product_share_pct"].iloc[0]
                ),
                f"{float(crow['avg_top1_product_share_pct']):.4f}%",
                "<= Stage526 avg top1 product share",
            ),
            (
                "family_concentration_not_worse",
                float(crow["avg_top1_family_share_pct"]) <= float(
                    contrib[contrib["variant"].eq(BASE_VARIANT)]["avg_top1_family_share_pct"].iloc[0]
                ),
                f"{float(crow['avg_top1_family_share_pct']):.4f}%",
                "<= Stage526 avg top1 family share",
            ),
            (
                "deployable_selector",
                deployable,
                "not hindsight upper bound" if deployable else "hindsight/fixed historical upper bound",
                "must be point-in-time deployable",
            ),
        ]:
            rows.append(
                {
                    "variant": variant,
                    "label": label,
                    "gate": metric,
                    "actual": actual,
                    "threshold": threshold,
                    "passed": int(bool(passed)),
                }
            )
        for horizon in (63, 126):
            current = holding[(holding["variant"].eq(variant)) & (holding["horizon_days"].eq(horizon))].iloc[0]
            base = base_holding.loc[horizon]
            checks = [
                float(current["negative_rate_pct"]) < float(base["negative_rate_pct"]),
                float(current["p10_return_pct"]) > float(base["p10_return_pct"]),
                float(current["min_return_pct"]) > float(base["min_return_pct"]),
                float(current["mae_p05_pct"]) > float(base["mae_p05_pct"]),
            ]
            passed_count = int(sum(checks))
            rows.append(
                {
                    "variant": variant,
                    "label": label,
                    "gate": f"holding_{horizon}d_experience_improves",
                    "actual": (
                        f"improved={passed_count}/4; neg={float(current['negative_rate_pct']):.2f}%; "
                        f"p10={float(current['p10_return_pct']):.2f}%; min={float(current['min_return_pct']):.2f}%; "
                        f"mae_p05={float(current['mae_p05_pct']):.2f}%"
                    ),
                    "threshold": ">=2 of neg-rate/p10/min/mae-p05 improve vs Stage526",
                    "passed": int(passed_count >= 2),
                }
            )
        if is_width and not crowding.empty:
            cc = crowding[crowding["variant"].eq(variant)]
            if not cc.empty:
                ccrow = cc.iloc[0]
                rows.append(
                    {
                        "variant": variant,
                        "label": label,
                        "gate": "corr_crowding_shell_active",
                        "actual": (
                            f"opened_corr_gt75={int(ccrow['opened_corr_gt75_count'])}; "
                            f"max_corr={float(ccrow['max_same_direction_corr']):.4f}; "
                            f"avg_family_max={float(ccrow.get('avg_family_max_count', 0.0)):.2f}"
                        ),
                        "threshold": "no opened corr >0.75 and family max bounded",
                        "passed": int(int(ccrow["opened_corr_gt75_count"]) == 0),
                    }
                )
    return pd.DataFrame(rows)


def _make_chart(summary: pd.DataFrame, holding: pd.DataFrame, contrib: pd.DataFrame, crowding: pd.DataFrame) -> None:
    order = [v for v in VARIANTS if v in summary["variant"].values]
    labels = [_variant_label(v) for v in order]
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    ax = axes[0, 0]
    pivot63 = holding[holding["horizon_days"].eq(63)].set_index("variant").reindex(order)
    ax.bar(labels, pivot63["p10_return_pct_delta_vs_stage526"], color="#4C78A8")
    ax.axhline(0.0, color="black", linestyle="--", linewidth=1)
    ax.set_title("63d p10 improvement vs Stage526")
    ax.set_ylabel("pp")
    ax.tick_params(axis="x", rotation=25)

    ax = axes[0, 1]
    pivot126 = holding[holding["horizon_days"].eq(126)].set_index("variant").reindex(order)
    ax.bar(labels, pivot126["p10_return_pct_delta_vs_stage526"], color="#59A14F")
    ax.axhline(0.0, color="black", linestyle="--", linewidth=1)
    ax.set_title("126d p10 improvement vs Stage526")
    ax.set_ylabel("pp")
    ax.tick_params(axis="x", rotation=25)

    ax = axes[0, 2]
    x = np.arange(len(order))
    width = 0.38
    ax.bar(x - width / 2, -pivot63["negative_rate_pct_delta_vs_stage526"], width=width, label="63d", color="#F28E2B")
    ax.bar(x + width / 2, -pivot126["negative_rate_pct_delta_vs_stage526"], width=width, label="126d", color="#E15759")
    ax.axhline(0.0, color="black", linestyle="--", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25)
    ax.set_title("Negative-rate improvement vs Stage526")
    ax.set_ylabel("pp")
    ax.legend()

    ax = axes[1, 0]
    contrib_view = contrib.set_index("variant").reindex(order)
    ax.bar(x - width / 2, contrib_view["avg_top1_product_share_pct"], width=width, label="product", color="#B07AA1")
    ax.bar(x + width / 2, contrib_view["avg_top1_family_share_pct"], width=width, label="family", color="#FF9DA7")
    ax.axhline(35.0, color="#B07AA1", linestyle=":", linewidth=1)
    ax.axhline(50.0, color="#FF9DA7", linestyle=":", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25)
    ax.set_title("Annual top contribution share")
    ax.set_ylabel("% of positive pnl")
    ax.legend()

    ax = axes[1, 1]
    sview = summary.set_index("variant").reindex(order)
    ax.scatter(sview["max_dd_pct"], sview["total_return_pct"], s=80, color="#76B7B2")
    for variant in order:
        ax.annotate(_variant_label(variant), (float(sview.loc[variant, "max_dd_pct"]), float(sview.loc[variant, "total_return_pct"])))
    ax.axvline(float(sview.loc[BASE_VARIANT, "max_dd_pct"]), color="black", linestyle="--", linewidth=1)
    ax.set_title("Return vs max drawdown")
    ax.set_xlabel("Max drawdown %")
    ax.set_ylabel("Total return %")

    ax = axes[1, 2]
    if not crowding.empty:
        corder = [v for v in WIDTH_VARIANTS if v in crowding["variant"].values]
        cview = crowding.set_index("variant").reindex(corder)
        ax.bar([_variant_label(v) for v in corder], cview["opened_corr_gt75_count"], color="#9C755F")
        ax.set_title("Opened events with same-direction corr > 0.75")
        ax.set_ylabel("count")
        ax.tick_params(axis="x", rotation=25)
    else:
        ax.text(0.5, 0.5, "No crowding data", ha="center", va="center")
        ax.axis("off")

    fig.suptitle("Stage570 breadth risk shell: holding experience and concentration", fontsize=14)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _make_report(
    summary: pd.DataFrame,
    holding: pd.DataFrame,
    contrib: pd.DataFrame,
    crowding: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> str:
    holding_view = holding[
        [
            "label",
            "horizon_days",
            "p10_return_pct",
            "p05_return_pct",
            "min_return_pct",
            "negative_rate_pct",
            "mae_p05_pct",
            "mae_min_pct",
            "worst_return_start_date",
        ]
    ].copy()
    contrib_view = contrib[
        [
            "label",
            "avg_top1_product_share_pct",
            "max_top1_product_share_pct",
            "years_top1_product_over35",
            "avg_top1_family_share_pct",
            "years_top1_family_over50",
            "avg_positive_product_count",
            "avg_positive_family_count",
        ]
    ].copy()
    summary_view = summary[
        [
            "label",
            "total_return_pct",
            "return_vs_stage526_pct",
            "max_dd_pct",
            "ulcer_pct",
            "sharpe",
            "total_trade_count",
            "satellite_cumulative_pnl",
        ]
    ].copy()
    gate_view = gates.groupby(["label"], as_index=False).agg(passed_count=("passed", "sum"), total=("passed", "count"))
    lines = [
        "# Stage570 Breadth Holding Experience Audit",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Decision",
        "",
        f"`{decision['decision']}`",
        "",
        "## Key Takeaways",
        "",
        *[f"- {item}" for item in decision["key_takeaways"]],
        "",
        "## Summary",
        "",
        _to_markdown_table(summary_view),
        "",
        "## 63/126日持有体验",
        "",
        _to_markdown_table(holding_view, max_rows=20),
        "",
        "## 年度贡献集中度",
        "",
        _to_markdown_table(contrib_view),
        "",
        "## 相关性拥挤",
        "",
        _to_markdown_table(crowding) if not crowding.empty else "_empty_",
        "",
        "## Gate Summary",
        "",
        _to_markdown_table(gate_view),
        "",
        "## Outputs",
        "",
        f"- chart: `{CHART_PATH}`",
        f"- holding summary: `{HOLDING_SUMMARY_PATH}`",
        f"- contribution summary: `{CONTRIB_SUMMARY_PATH}`",
        f"- gates: `{GATES_PATH}`",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    daily = _read_csv(COMBINED_DAILY_IN)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
    daily = daily[daily["date"].ge(START_DATE)].copy()
    daily["account_equity"] = _num(daily, "account_equity")
    summary = _read_csv(SUMMARY_IN)
    summary = summary[summary["variant"].isin(VARIANTS) & summary["cost_multiplier"].eq(1.0)].copy()
    summary["label"] = summary["variant"].map(_variant_label)

    holding_detail, holding_summary = build_holding_metrics(daily)
    annual_contrib, product_contrib, family_contrib, contrib_summary = build_contribution_metrics()
    crowding = build_crowding_summary()
    gates = build_gates(summary, holding_summary, contrib_summary, crowding)

    deployable = gates[~gates["variant"].eq(BASE_VARIANT)].copy()
    deployable = deployable[deployable["variant"].ne(STAGE256_VARIANT)]
    width_gate = deployable.groupby("variant")["passed"].agg(["sum", "count"]).reset_index()
    stage256_gates = gates[gates["variant"].eq(STAGE256_VARIANT)]
    stage256_pass = int(stage256_gates["passed"].sum())

    if not width_gate.empty and (width_gate["sum"] >= width_gate["count"]).any():
        decision_code = "breadth_fixed_shell_candidate_needs_selector_review"
    elif stage256_pass >= int(len(stage256_gates) * 0.70):
        decision_code = "hindsight_upper_bound_improves_experience_selector_required"
    else:
        decision_code = "breadth_shell_does_not_improve_holding_experience_selector_required"

    h63 = holding_summary[holding_summary["horizon_days"].eq(63)].set_index("variant")
    h126 = holding_summary[holding_summary["horizon_days"].eq(126)].set_index("variant")
    base63 = h63.loc[BASE_VARIANT]
    base126 = h126.loc[BASE_VARIANT]
    best63 = h63.sort_values(["p10_return_pct", "negative_rate_pct"], ascending=[False, True]).iloc[0]
    best126 = h126.sort_values(["p10_return_pct", "negative_rate_pct"], ascending=[False, True]).iloc[0]
    key_takeaways = [
        (
            f"Stage526 63日p10={base63['p10_return_pct']:.4f}%, 负收益率={base63['negative_rate_pct']:.4f}%; "
            f"126日p10={base126['p10_return_pct']:.4f}%, 负收益率={base126['negative_rate_pct']:.4f}%."
        ),
        (
            f"63日p10最好为 {_variant_label(str(best63.name))}: {best63['p10_return_pct']:.4f}%; "
            f"126日p10最好为 {_variant_label(str(best126.name))}: {best126['p10_return_pct']:.4f}%."
        ),
        (
            "Stage256 是历史白名单/上限，不可直接部署；若它改善体验，只能说明 selector 有价值，不能说明当前已可实盘。"
        ),
        (
            "宽池变体必须同时通过收益、回撤、Ulcer、63/126日体验、贡献集中度和相关性拥挤；任一失败都不能晋级。"
        ),
    ]
    decision = {
        "model_tag": MODEL_TAG,
        "decision": decision_code,
        "base_variant": BASE_VARIANT,
        "variant_count": int(len(VARIANTS)),
        "width_gate_summary": width_gate.to_dict(orient="records"),
        "stage256_passed_gates": stage256_pass,
        "stage256_total_gates": int(len(stage256_gates)),
        "key_takeaways": key_takeaways,
        "outputs": {
            "chart": str(CHART_PATH),
            "holding_summary": str(HOLDING_SUMMARY_PATH),
            "contribution_summary": str(CONTRIB_SUMMARY_PATH),
            "crowding_summary": str(CROWDING_PATH),
            "gates": str(GATES_PATH),
            "report": str(REPORT_PATH),
        },
    }

    HOLDING_DETAIL_PATH.parent.mkdir(parents=True, exist_ok=True)
    holding_detail.to_csv(HOLDING_DETAIL_PATH, index=False, encoding="utf-8-sig")
    holding_summary.to_csv(HOLDING_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    annual_contrib.to_csv(CONTRIB_ANNUAL_PATH, index=False, encoding="utf-8-sig")
    product_contrib.to_csv(CONTRIB_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    family_contrib.to_csv(CONTRIB_FAMILY_PATH, index=False, encoding="utf-8-sig")
    contrib_summary.to_csv(CONTRIB_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    crowding.to_csv(CROWDING_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_make_report(summary, holding_summary, contrib_summary, crowding, gates, decision), encoding="utf-8")
    _make_chart(summary, holding_summary, contrib_summary, crowding)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
