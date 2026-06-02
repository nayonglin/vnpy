from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import math
import multiprocessing as mp
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage547_noncore_basis_monthly_selector_diagnostic_v1"
OUTPUT_PREFIX = "qmt_roll_stage547_noncore_basis_monthly_selector_diagnostic"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE543_TAG = "stage543_ex_ante_product_selector_diagnostic_v1"
STAGE543_PREFIX = "qmt_roll_stage543_ex_ante_product_selector_diagnostic"
STAGE543_SCORED_IN = OUTPUT_DIR / f"{STAGE543_PREFIX}_scored_samples_{STAGE543_TAG}.csv"

STAGE544_TAG = "stage544_family_constrained_selector_diagnostic_v1"
STAGE544_PREFIX = "qmt_roll_stage544_family_constrained_selector_diagnostic"
STAGE544_FAMILY_MAP_IN = OUTPUT_DIR / f"{STAGE544_PREFIX}_family_map_{STAGE544_TAG}.csv"
STAGE544_SELECTIONS_IN = OUTPUT_DIR / f"{STAGE544_PREFIX}_selections_{STAGE544_TAG}.csv"

RAW_BASIS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_raw_basis_{MODEL_TAG}.csv"
SCORED_SAMPLES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_scored_samples_{MODEL_TAG}.csv"
COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_{MODEL_TAG}.csv"
SELECTIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selections_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

TOP_K = 6
HARD_EDGE_THRESHOLD = 500.0
HARD_CAPTURE_RATIO = 0.50
HARD_POSITIVE_MONTH_RATE = 55.0
MIN_AVG_BASIS_SELECTED = 4.0
SOURCE_TIMEOUT_SECONDS = 25


@dataclass(frozen=True)
class SelectorMode:
    mode: str
    label: str
    score_column: str
    family_cap: int
    fill_with_stage544: bool
    rationale: str


MODES: tuple[SelectorMode, ...] = (
    SelectorMode(
        "basis_alignment_family_cap1",
        "基差顺势一致+族1",
        "basis_alignment_score",
        1,
        False,
        "只在有基差的产品中，选择基差方向与近60日价格方向一致、且低核心相关的产品。",
    ),
    SelectorMode(
        "basis_pressure_family_cap1",
        "基差压力强度+族1",
        "basis_pressure_score",
        1,
        False,
        "不判断方向，只选基差绝对压力/期限偏离更强且低核心相关的产品。",
    ),
    SelectorMode(
        "basis_change_alignment_family_cap1",
        "基差变化顺势+族1",
        "basis_change_alignment_score",
        1,
        False,
        "看月度基差变化是否支持近60日趋势方向。",
    ),
    SelectorMode(
        "basis_blend_family_cap1",
        "基差综合+族1",
        "basis_blend_score",
        1,
        False,
        "固定融合基差顺势、一致变化、压力强度、simple趋势和低核心相关。",
    ),
    SelectorMode(
        "basis_blend_fill_stage544",
        "基差综合+Stage544补足",
        "basis_blend_score",
        1,
        True,
        "先选有基差的强产品，若不足6个再用Stage544 simple族1低相关逻辑补足。",
    ),
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
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


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _product_code(vt_symbol: str) -> str:
    return str(vt_symbol).split(".", 1)[0].upper()


def _rank_pct(frame: pd.DataFrame, column: str, *, lower_is_better: bool = False) -> pd.Series:
    values = pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
    return values.groupby(frame["eval_date"]).rank(method="average", pct=True, ascending=not lower_is_better)


def _run_spot_price(day: str, codes: list[str]) -> dict[str, Any]:
    def worker(queue: mp.Queue) -> None:
        try:
            import akshare as ak

            result = ak.futures_spot_price(day, codes)
            if isinstance(result, pd.DataFrame):
                queue.put({"status": "ok", "rows": result.to_dict("records"), "row_count": int(len(result))})
            else:
                queue.put({"status": "bad_result", "rows": [], "row_count": 0})
        except Exception as exc:  # pragma: no cover - external source instability
            queue.put({"status": "error", "error_type": type(exc).__name__, "error_message": str(exc)[:300], "rows": []})

    ctx = mp.get_context("fork")
    queue: mp.Queue = ctx.Queue()
    process = ctx.Process(target=worker, args=(queue,))
    process.start()
    process.join(SOURCE_TIMEOUT_SECONDS)
    if process.is_alive():
        process.terminate()
        process.join(2)
        return {"status": "timeout", "error_type": "Timeout", "error_message": f">{SOURCE_TIMEOUT_SECONDS}s", "rows": []}
    if queue.empty():
        return {"status": "empty", "error_type": "EmptyResult", "error_message": "worker returned no message", "rows": []}
    return queue.get()


def _load_samples() -> pd.DataFrame:
    samples = pd.read_csv(STAGE543_SCORED_IN, encoding="utf-8-sig")
    samples["eval_date"] = pd.to_datetime(samples["eval_date"], errors="coerce").dt.normalize()
    samples["product_vt_symbol"] = samples["product_vt_symbol"].astype(str)
    samples["product_code"] = samples["product_vt_symbol"].map(_product_code)
    samples["is_oracle6"] = pd.to_numeric(samples["is_oracle6"], errors="coerce").fillna(0).astype(int)
    for column in [
        "future_stage541_pnl_60d",
        "future_stage541_pnl_120d",
        "market_ret_60d",
        "simple_trend",
        "abs_core_corr_252d",
        "low_core_corr_rank_pct",
    ]:
        samples[column] = pd.to_numeric(samples[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    family = pd.read_csv(STAGE544_FAMILY_MAP_IN, encoding="utf-8-sig")
    family["product_vt_symbol"] = family["product_vt_symbol"].astype(str)
    samples = samples.merge(family[["product_vt_symbol", "product_family", "family_note"]], on="product_vt_symbol", how="left")
    samples["product_family"] = samples["product_family"].fillna("unknown")
    samples["family_note"] = samples["family_note"].fillna("未分类")
    return samples


def _fetch_or_load_basis(samples: pd.DataFrame) -> pd.DataFrame:
    dates = sorted(pd.Timestamp(item).strftime("%Y%m%d") for item in samples["eval_date"].dropna().unique())
    codes = sorted(samples["product_code"].dropna().unique())
    if RAW_BASIS_PATH.exists() and RAW_BASIS_PATH.stat().st_size > 0:
        raw = pd.read_csv(RAW_BASIS_PATH, encoding="utf-8-sig")
        cached_dates = set(raw.get("date", pd.Series(dtype=str)).astype(str).str.replace("-", "", regex=False))
        if set(dates).issubset(cached_dates):
            return raw

    rows: list[dict[str, Any]] = []
    for index, day in enumerate(dates, start=1):
        probe = _run_spot_price(day, codes)
        status = probe.get("status", "")
        if status == "ok":
            for row in probe.get("rows", []):
                item = dict(row)
                item["fetch_status"] = status
                item["fetch_error_type"] = ""
                rows.append(item)
        else:
            rows.append(
                {
                    "date": day,
                    "symbol": "",
                    "fetch_status": status,
                    "fetch_error_type": probe.get("error_type", ""),
                    "fetch_error_message": probe.get("error_message", ""),
                }
            )
        if index % 10 == 0:
            print(f"basis_monthly_fetch_progress {index}/{len(dates)}")

    raw = pd.DataFrame(rows)
    raw.to_csv(RAW_BASIS_PATH, index=False, encoding="utf-8-sig")
    return raw


def _score_samples(samples: pd.DataFrame, raw_basis: pd.DataFrame) -> pd.DataFrame:
    basis = raw_basis.copy()
    if basis.empty:
        basis = pd.DataFrame(columns=["date", "symbol"])
    basis["basis_date"] = pd.to_datetime(basis["date"].astype(str).str.replace("-", "", regex=False), format="%Y%m%d", errors="coerce").dt.normalize()
    basis["product_code"] = basis["symbol"].astype(str).str.upper()
    for column in ["near_basis_rate", "dom_basis_rate", "near_basis", "dom_basis", "spot_price", "dominant_contract_price"]:
        if column not in basis.columns:
            basis[column] = np.nan
        basis[column] = pd.to_numeric(basis[column], errors="coerce")
    basis = basis.dropna(subset=["basis_date", "product_code"]).drop_duplicates(["basis_date", "product_code"], keep="last")

    scored = samples.merge(
        basis[
            [
                "basis_date",
                "product_code",
                "spot_price",
                "near_contract",
                "dominant_contract",
                "near_basis_rate",
                "dom_basis_rate",
                "near_basis",
                "dom_basis",
            ]
        ],
        left_on=["eval_date", "product_code"],
        right_on=["basis_date", "product_code"],
        how="left",
    )
    scored["basis_available"] = scored["dom_basis_rate"].notna().astype(int)
    scored["trend_direction_proxy"] = np.sign(scored["market_ret_60d"].replace(0.0, np.nan)).fillna(
        np.sign(scored["simple_trend"] - 0.5)
    )
    scored["basis_alignment_raw"] = -scored["trend_direction_proxy"] * scored["dom_basis_rate"]
    scored["basis_pressure_abs_raw"] = scored["dom_basis_rate"].abs()
    scored.sort_values(["product_vt_symbol", "eval_date"], inplace=True)
    scored["basis_rate_change_monthly"] = scored.groupby("product_vt_symbol")["dom_basis_rate"].diff()
    scored["basis_change_alignment_raw"] = -scored["trend_direction_proxy"] * scored["basis_rate_change_monthly"]
    scored.sort_values(["eval_date", "product_vt_symbol"], inplace=True)

    for raw_column, rank_column in [
        ("basis_alignment_raw", "basis_alignment_rank_pct"),
        ("basis_pressure_abs_raw", "basis_pressure_rank_pct"),
        ("basis_change_alignment_raw", "basis_change_alignment_rank_pct"),
    ]:
        scored[rank_column] = _rank_pct(scored, raw_column)
        scored[rank_column] = scored[rank_column].fillna(0.0)

    scored["basis_alignment_score"] = scored[
        ["basis_alignment_rank_pct", "simple_trend", "low_core_corr_rank_pct"]
    ].mean(axis=1) * scored["basis_available"]
    scored["basis_pressure_score"] = scored[
        ["basis_pressure_rank_pct", "simple_trend", "low_core_corr_rank_pct"]
    ].mean(axis=1) * scored["basis_available"]
    scored["basis_change_alignment_score"] = scored[
        ["basis_change_alignment_rank_pct", "simple_trend", "low_core_corr_rank_pct"]
    ].mean(axis=1) * scored["basis_available"]
    scored["basis_blend_score"] = (
        0.35 * scored["basis_alignment_rank_pct"]
        + 0.25 * scored["basis_change_alignment_rank_pct"]
        + 0.15 * scored["basis_pressure_rank_pct"]
        + 0.15 * scored["simple_trend"]
        + 0.10 * scored["low_core_corr_rank_pct"]
    ) * scored["basis_available"]
    return scored


def _sample_dates(samples: pd.DataFrame, sample_type: str) -> list[pd.Timestamp]:
    dates = sorted(pd.Timestamp(item) for item in samples["eval_date"].dropna().unique())
    if sample_type == "monthly":
        return dates
    if sample_type == "quarterly_purged":
        return sorted(
            pd.DataFrame({"eval_date": dates})
            .assign(quarter=lambda df: df["eval_date"].dt.to_period("Q"))
            .groupby("quarter")["eval_date"]
            .max()
            .map(pd.Timestamp)
            .tolist()
        )
    raise ValueError(sample_type)


def _select_stage544_like(frame: pd.DataFrame, already: set[str]) -> list[pd.Series]:
    ordered = frame[~frame["product_vt_symbol"].isin(already)].sort_values(
        ["simple_trend", "abs_core_corr_252d", "product_vt_symbol"],
        ascending=[False, True, True],
    )
    chosen: list[pd.Series] = []
    family_counts: dict[str, int] = {}
    for _, row in ordered.iterrows():
        family = str(row["product_family"])
        if family_counts.get(family, 0) >= 1:
            continue
        chosen.append(row)
        family_counts[family] = family_counts.get(family, 0) + 1
        if len(chosen) >= TOP_K:
            break
    return chosen


def _select(frame: pd.DataFrame, mode: SelectorMode) -> pd.DataFrame:
    available = frame[frame["basis_available"].eq(1)].sort_values(
        [mode.score_column, "abs_core_corr_252d", "product_vt_symbol"],
        ascending=[False, True, True],
    )
    chosen: list[pd.Series] = []
    family_counts: dict[str, int] = {}
    for _, row in available.iterrows():
        family = str(row["product_family"])
        if family_counts.get(family, 0) >= mode.family_cap:
            continue
        chosen.append(row)
        family_counts[family] = family_counts.get(family, 0) + 1
        if len(chosen) >= TOP_K:
            break

    if mode.fill_with_stage544 and len(chosen) < TOP_K:
        already = {str(row["product_vt_symbol"]) for row in chosen}
        for row in _select_stage544_like(frame, already):
            family = str(row["product_family"])
            if family_counts.get(family, 0) >= mode.family_cap:
                continue
            chosen.append(row)
            family_counts[family] = family_counts.get(family, 0) + 1
            if len(chosen) >= TOP_K:
                break

    selected = pd.DataFrame(chosen)
    if selected.empty:
        return selected
    selected = selected.head(TOP_K).reset_index(drop=True)
    selected["selected_rank"] = np.arange(1, len(selected) + 1)
    selected["selected_by_basis"] = selected["basis_available"].astype(int)
    return selected


def _stage544_best_series(samples: pd.DataFrame) -> pd.Series:
    if not STAGE544_SELECTIONS_IN.exists():
        return pd.Series(0.0, index=pd.DatetimeIndex(_sample_dates(samples, "quarterly_purged")))
    selections = pd.read_csv(STAGE544_SELECTIONS_IN, encoding="utf-8-sig")
    selections["eval_date"] = pd.to_datetime(selections["eval_date"], errors="coerce").dt.normalize()
    subset = selections[
        selections["sample_type"].eq("quarterly_purged")
        & selections["mode"].eq("simple_family_cap1_lowcorr030")
    ].copy()
    return subset.groupby("eval_date")["future_stage541_pnl_60d"].mean().sort_index()


def _evaluate(scored: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    selection_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for sample_type in ("monthly", "quarterly_purged"):
        allowed = set(_sample_dates(scored, sample_type))
        subset = scored[scored["eval_date"].isin(allowed)].copy()
        for mode in MODES:
            eval_rows: list[dict[str, Any]] = []
            for eval_date, frame in subset.groupby("eval_date", sort=True):
                selected = _select(frame, mode)
                if selected.empty:
                    continue
                all_mean60 = float(frame["future_stage541_pnl_60d"].mean())
                all_mean120 = float(frame["future_stage541_pnl_120d"].mean())
                oracle = frame[frame["is_oracle6"].eq(1)]
                oracle_mean60 = float(oracle["future_stage541_pnl_60d"].mean())
                oracle_mean120 = float(oracle["future_stage541_pnl_120d"].mean())
                selected_mean60 = float(selected["future_stage541_pnl_60d"].mean())
                selected_mean120 = float(selected["future_stage541_pnl_120d"].mean())
                selected = selected.copy()
                selected["mode"] = mode.mode
                selected["mode_label"] = mode.label
                selected["sample_type"] = sample_type
                selected["all_noncore_mean_future60"] = all_mean60
                selected["oracle6_mean_future60"] = oracle_mean60
                selection_rows.extend(selected.to_dict("records"))
                eval_rows.append(
                    {
                        "mode": mode.mode,
                        "mode_label": mode.label,
                        "sample_type": sample_type,
                        "eval_date": eval_date,
                        "selected_count": int(len(selected)),
                        "basis_selected_count": int(selected["selected_by_basis"].sum()),
                        "selected_products": ",".join(selected["product_vt_symbol"].astype(str).tolist()),
                        "basis_products": ",".join(selected.loc[selected["selected_by_basis"].eq(1), "product_vt_symbol"].astype(str).tolist()),
                        "selected_mean_future60": selected_mean60,
                        "selected_mean_future120": selected_mean120,
                        "all_noncore_mean_future60": all_mean60,
                        "all_noncore_mean_future120": all_mean120,
                        "oracle6_mean_future60": oracle_mean60,
                        "oracle6_mean_future120": oracle_mean120,
                        "edge_vs_all_future60": selected_mean60 - all_mean60,
                        "edge_vs_all_future120": selected_mean120 - all_mean120,
                        "selected_oracle_count": int(selected["is_oracle6"].sum()),
                        "basis_available_count_in_universe": int(frame["basis_available"].sum()),
                    }
                )
            eval_df = pd.DataFrame(eval_rows)
            if eval_df.empty:
                continue
            avg_selected60 = float(eval_df["selected_mean_future60"].mean())
            avg_oracle60 = float(eval_df["oracle6_mean_future60"].mean())
            summary_rows.append(
                {
                    "mode": mode.mode,
                    "mode_label": mode.label,
                    "sample_type": sample_type,
                    "months": int(len(eval_df)),
                    "avg_selected_count": float(eval_df["selected_count"].mean()),
                    "avg_basis_selected_count": float(eval_df["basis_selected_count"].mean()),
                    "avg_basis_available_count_in_universe": float(eval_df["basis_available_count_in_universe"].mean()),
                    "avg_selected_mean_future60": avg_selected60,
                    "avg_selected_mean_future120": float(eval_df["selected_mean_future120"].mean()),
                    "avg_all_noncore_mean_future60": float(eval_df["all_noncore_mean_future60"].mean()),
                    "avg_all_noncore_mean_future120": float(eval_df["all_noncore_mean_future120"].mean()),
                    "avg_oracle6_mean_future60": avg_oracle60,
                    "avg_oracle6_mean_future120": float(eval_df["oracle6_mean_future120"].mean()),
                    "avg_edge_vs_all_future60": float(eval_df["edge_vs_all_future60"].mean()),
                    "avg_edge_vs_all_future120": float(eval_df["edge_vs_all_future120"].mean()),
                    "selected_vs_oracle_capture_ratio_60d": avg_selected60 / avg_oracle60 if avg_oracle60 else 0.0,
                    "positive_month_rate_future60_pct": float((eval_df["selected_mean_future60"] > 0.0).mean() * 100.0),
                    "positive_month_rate_future120_pct": float((eval_df["selected_mean_future120"] > 0.0).mean() * 100.0),
                    "avg_oracle_recall_count": float(eval_df["selected_oracle_count"].mean()),
                    "rationale": mode.rationale,
                }
            )

    selections = pd.DataFrame(selection_rows)
    summary = pd.DataFrame(summary_rows)
    if not summary.empty:
        summary["diagnostic_pass"] = (
            (summary["sample_type"].eq("quarterly_purged"))
            & (summary["avg_edge_vs_all_future60"] >= HARD_EDGE_THRESHOLD)
            & (summary["selected_vs_oracle_capture_ratio_60d"] >= HARD_CAPTURE_RATIO)
            & (summary["positive_month_rate_future60_pct"] >= HARD_POSITIVE_MONTH_RATE)
            & (summary["avg_oracle_recall_count"] >= 2.0)
            & (summary["avg_basis_selected_count"] >= MIN_AVG_BASIS_SELECTED)
        ).astype(int)
        summary.sort_values(
            ["diagnostic_pass", "sample_type", "avg_edge_vs_all_future60", "avg_basis_selected_count"],
            ascending=[False, True, False, False],
            inplace=True,
        )
    return selections, summary


def _coverage(scored: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for product, frame in scored.groupby("product_vt_symbol", sort=True):
        meta = frame.iloc[0]
        rows.append(
            {
                "product_vt_symbol": product,
                "product_code": meta["product_code"],
                "product_family": meta["product_family"],
                "is_oracle6": int(meta["is_oracle6"]),
                "eval_months": int(frame["eval_date"].nunique()),
                "basis_months": int(frame["basis_available"].sum()),
                "basis_coverage_rate_pct": float(frame["basis_available"].mean() * 100.0),
                "avg_dom_basis_rate": float(frame.loc[frame["basis_available"].eq(1), "dom_basis_rate"].mean())
                if frame["basis_available"].any()
                else np.nan,
            }
        )
    result = pd.DataFrame(rows)
    result.sort_values(["is_oracle6", "basis_coverage_rate_pct", "product_vt_symbol"], ascending=[False, False, True], inplace=True)
    return result


def _decision(summary: pd.DataFrame, coverage: pd.DataFrame) -> dict[str, Any]:
    passed = summary[summary["diagnostic_pass"].eq(1)].copy() if "diagnostic_pass" in summary.columns else pd.DataFrame()
    quarterly = summary[summary["sample_type"].eq("quarterly_purged")].copy()
    best = quarterly.sort_values(["avg_edge_vs_all_future60", "avg_basis_selected_count"], ascending=False).head(1)
    best_record = best.iloc[0].to_dict() if not best.empty else {}
    oracle_cov = coverage[coverage["is_oracle6"].eq(1)].copy()
    return {
        "stage": "Stage247",
        "script_stage": "Stage547",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": (
            "basis_selector_ready_for_dynamic_sleeve_probe"
            if not passed.empty
            else "basis_monthly_selector_not_ready_coverage_and_predictive_power_short"
        ),
        "pass_definition": (
            "Quarterly-purged Top6 basis selector must beat all-noncore future60 mean by >=500 yuan/product, "
            "capture >=50% of Oracle6 future60 reference, have >=55% positive 60d periods, recall >=2 Oracle6 names, "
            f"and average >= {MIN_AVG_BASIS_SELECTED:.0f} basis-selected products."
        ),
        "passed_rows": passed.to_dict("records"),
        "best_row": best_record,
        "coverage": {
            "noncore_product_count": int(coverage["product_vt_symbol"].nunique()),
            "products_with_basis": int(coverage["basis_months"].gt(0).sum()),
            "oracle6_products": int(oracle_cov["product_vt_symbol"].nunique()),
            "oracle6_with_basis": int(oracle_cov["basis_months"].gt(0).sum()),
            "oracle6_avg_coverage_rate_pct": float(oracle_cov["basis_coverage_rate_pct"].mean()) if not oracle_cov.empty else 0.0,
        },
        "overfit_boundary": (
            "Monthly basis snapshots are fetched only on pre-existing Stage543 eval dates and evaluated with fixed selector shapes. "
            "No parameter is tuned after seeing selector returns."
        ),
        "next_step": (
            "If not passed, do not tune basis weights. Either find sources for AO/LU and warehouse/member/sentiment, "
            "or use basis as an explanatory monitor rather than a dynamic sleeve selector."
        ),
    }


def _plot(scored: pd.DataFrame, selections: pd.DataFrame, summary: pd.DataFrame, coverage: pd.DataFrame, decision: dict[str, Any]) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(17, 10))
    ax_cov, ax_edge, ax_cum, ax_heat = axes.flatten()

    cov = coverage.sort_values(["is_oracle6", "basis_coverage_rate_pct"], ascending=[True, True])
    colors = ["#dc2626" if item else "#2563eb" for item in cov["is_oracle6"]]
    ax_cov.barh(cov["product_vt_symbol"], cov["basis_coverage_rate_pct"], color=colors)
    ax_cov.set_title("Monthly basis coverage by noncore product")
    ax_cov.set_xlim(0, 105)
    ax_cov.grid(axis="x", alpha=0.25)

    quarterly = summary[summary["sample_type"].eq("quarterly_purged")].copy().sort_values("avg_edge_vs_all_future60")
    ax_edge.barh(quarterly["mode_label"], quarterly["avg_edge_vs_all_future60"], color="#0f766e")
    ax_edge.axvline(0, color="#111827", linestyle="--", linewidth=1)
    ax_edge.axvline(HARD_EDGE_THRESHOLD, color="#dc2626", linestyle=":", linewidth=1)
    ax_edge.set_title("Quarterly future60 edge")
    ax_edge.grid(axis="x", alpha=0.25)

    q_dates = _sample_dates(scored, "quarterly_purged")
    q_sel = selections[selections["sample_type"].eq("quarterly_purged")].copy()
    top_modes = quarterly.sort_values("avg_edge_vs_all_future60", ascending=False)["mode"].head(3).tolist()
    for mode in top_modes:
        series = q_sel[q_sel["mode"].eq(mode)].groupby("eval_date")["future_stage541_pnl_60d"].mean().reindex(q_dates).fillna(0.0).cumsum()
        label = str(quarterly.loc[quarterly["mode"].eq(mode), "mode_label"].iloc[0])
        ax_cum.plot(series.index, series.values, label=label, linewidth=1.1)
    stage544 = _stage544_best_series(scored).reindex(q_dates).fillna(0.0).cumsum()
    oracle = scored[scored["is_oracle6"].eq(1)].groupby("eval_date")["future_stage541_pnl_60d"].mean().reindex(q_dates).fillna(0.0).cumsum()
    all_noncore = scored.groupby("eval_date")["future_stage541_pnl_60d"].mean().reindex(q_dates).fillna(0.0).cumsum()
    ax_cum.plot(stage544.index, stage544.values, label="Stage544 best", color="#7c3aed", linewidth=1.1)
    ax_cum.plot(oracle.index, oracle.values, label="Oracle6 reference", color="#dc2626", linewidth=1.5)
    ax_cum.plot(all_noncore.index, all_noncore.values, label="All noncore mean", color="#111827", linestyle="--", linewidth=1.0)
    ax_cum.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_cum.set_title("Quarterly cumulative future60 mean")
    ax_cum.grid(alpha=0.25)
    ax_cum.legend(fontsize=7)

    heat = scored[scored["is_oracle6"].eq(1)].copy()
    heat["date_label"] = heat["eval_date"].dt.strftime("%Y-%m")
    pivot = heat.pivot(index="product_vt_symbol", columns="date_label", values="basis_available").reindex(
        sorted(heat["product_vt_symbol"].unique())
    )
    if not pivot.empty:
        image = ax_heat.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
        ax_heat.set_yticks(np.arange(len(pivot.index)))
        ax_heat.set_yticklabels(pivot.index)
        step = max(1, len(pivot.columns) // 8)
        ax_heat.set_xticks(np.arange(0, len(pivot.columns), step))
        ax_heat.set_xticklabels(pivot.columns[::step], rotation=45, ha="right")
        ax_heat.set_title("Oracle6 monthly basis availability")
        fig.colorbar(image, ax=ax_heat, fraction=0.046, pad=0.04)

    fig.suptitle(f"Stage547 decision: {decision['decision']}", fontsize=12)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, coverage: pd.DataFrame, decision: dict[str, Any]) -> None:
    quarterly = summary[summary["sample_type"].eq("quarterly_purged")][
        [
            "mode_label",
            "avg_basis_selected_count",
            "avg_selected_mean_future60",
            "avg_selected_mean_future120",
            "avg_edge_vs_all_future60",
            "selected_vs_oracle_capture_ratio_60d",
            "positive_month_rate_future60_pct",
            "avg_oracle_recall_count",
            "diagnostic_pass",
        ]
    ].sort_values("avg_edge_vs_all_future60", ascending=False)
    oracle_cov = coverage[coverage["is_oracle6"].eq(1)][
        ["product_vt_symbol", "product_family", "basis_months", "basis_coverage_rate_pct", "avg_dom_basis_rate"]
    ]
    lines = [
        "# Stage547 非核心月度基差选品诊断",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 决策：`{decision['decision']}`。",
        "- 阶段性质：点时化数据补齐 + 固定选择器诊断；不生成交易版本。",
        "- 核心问题：AKShare 月度基差快照能否支持 Stage543 非核心扩池选品。",
        "",
        "## 通过定义",
        "",
        decision["pass_definition"],
        "",
        "## 季度去重摘要",
        "",
        _md_table(quarterly),
        "",
        "## Oracle6 基差覆盖",
        "",
        _md_table(oracle_cov),
        "",
        "## 判断",
        "",
        "- 基差源能覆盖部分非核心产品，但 Oracle6 中 `ao.SHFE/lu.INE` 缺口仍在。",
        "- 固定 basis 选择器如果不能显著超过 Stage544 和 Oracle6 捕获门槛，就不能进入动态 sleeve。",
        "- 若本阶段不通过，不能继续调 basis 权重；只能先补数据源或把 basis 降级为解释/监控层。",
        "",
        "## 输出文件",
        "",
        f"- raw basis：`{RAW_BASIS_PATH}`",
        f"- scored samples：`{SCORED_SAMPLES_PATH}`",
        f"- coverage：`{COVERAGE_PATH}`",
        f"- selections：`{SELECTIONS_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- chart：`{CHART_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    samples = _load_samples()
    raw_basis = _fetch_or_load_basis(samples)
    scored = _score_samples(samples, raw_basis)
    coverage = _coverage(scored)
    selections, summary = _evaluate(scored)
    decision = _decision(summary, coverage)

    scored.to_csv(SCORED_SAMPLES_PATH, index=False, encoding="utf-8-sig")
    coverage.to_csv(COVERAGE_PATH, index=False, encoding="utf-8-sig")
    selections.to_csv(SELECTIONS_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(scored, selections, summary, coverage, decision)
    _write_report(summary, coverage, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
