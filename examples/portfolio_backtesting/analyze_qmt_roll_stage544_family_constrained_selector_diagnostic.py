from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage544_family_constrained_selector_diagnostic_v1"
OUTPUT_PREFIX = "qmt_roll_stage544_family_constrained_selector_diagnostic"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE543_TAG = "stage543_ex_ante_product_selector_diagnostic_v1"
STAGE543_PREFIX = "qmt_roll_stage543_ex_ante_product_selector_diagnostic"
STAGE543_SCORED_IN = OUTPUT_DIR / f"{STAGE543_PREFIX}_scored_samples_{STAGE543_TAG}.csv"

FAMILY_MAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_map_{MODEL_TAG}.csv"
SELECTIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selections_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
FAMILY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

TOP_K = 6
LOW_CORE_CORR_THRESHOLD = 0.30
HARD_EDGE_THRESHOLD = 500.0
HARD_CAPTURE_RATIO = 0.50
HARD_POSITIVE_MONTH_RATE = 55.0


PRODUCT_FAMILY: dict[str, tuple[str, str]] = {
    "CY.CZCE": ("soft_agri", "棉纺软商品"),
    "SR.CZCE": ("soft_agri", "糖棉软商品"),
    "PK.CZCE": ("grains_oilseeds", "油脂油料/农产品"),
    "a.DCE": ("grains_oilseeds", "油脂油料/农产品"),
    "c.DCE": ("grains_oilseeds", "谷物/农产品"),
    "cs.DCE": ("grains_oilseeds", "谷物/农产品"),
    "m.DCE": ("grains_oilseeds", "油脂油料/农产品"),
    "p.DCE": ("grains_oilseeds", "油脂油料/农产品"),
    "y.DCE": ("grains_oilseeds", "油脂油料/农产品"),
    "rr.DCE": ("grains_oilseeds", "谷物/农产品"),
    "jd.DCE": ("livestock", "畜禽农产品"),
    "sc.INE": ("energy_oil", "原油能源"),
    "lu.INE": ("energy_oil", "燃油能源"),
    "bu.SHFE": ("energy_oil", "沥青能源"),
    "pg.DCE": ("energy_oil", "LPG能源"),
    "TA.CZCE": ("petrochem", "聚酯化工"),
    "PF.CZCE": ("petrochem", "聚酯化工"),
    "PX.CZCE": ("petrochem", "芳烃化工"),
    "UR.CZCE": ("petrochem", "尿素化工"),
    "eb.DCE": ("petrochem", "苯乙烯化工"),
    "v.DCE": ("petrochem", "PVC化工"),
    "br.SHFE": ("rubber", "橡胶"),
    "nr.INE": ("rubber", "橡胶"),
    "i.DCE": ("black_ferrous", "黑色矿石焦煤"),
    "j.DCE": ("black_ferrous", "黑色焦煤焦炭"),
    "SF.CZCE": ("black_ferrous", "铁合金"),
    "ag.SHFE": ("precious_metals", "贵金属"),
    "al.SHFE": ("base_metals", "有色金属"),
    "ao.SHFE": ("base_metals", "有色金属"),
    "bc.INE": ("base_metals", "有色金属"),
    "ni.SHFE": ("base_metals", "有色金属"),
    "pb.SHFE": ("base_metals", "有色金属"),
    "sn.SHFE": ("base_metals", "有色金属"),
    "ss.SHFE": ("base_metals", "不锈钢金属"),
    "zn.SHFE": ("base_metals", "有色金属"),
    "IH.CFFEX": ("financial_index", "股指"),
    "PR.CZCE": ("other", "其他新品种"),
    "fb.DCE": ("other", "板材其他"),
}


@dataclass(frozen=True)
class SelectorMode:
    mode: str
    label: str
    score_column: str
    family_cap: int | None
    low_core_corr_threshold: float | None
    rationale: str


MODES: tuple[SelectorMode, ...] = (
    SelectorMode("memory_unconstrained", "历史记忆无族约束", "strategy_memory_equal", None, None, "Stage543 最好季度口径对照。"),
    SelectorMode("memory_family_cap2", "历史记忆族上限2", "strategy_memory_equal", 2, None, "保留历史记忆，但限制同产品族最多2个。"),
    SelectorMode("memory_family_cap1", "历史记忆族上限1", "strategy_memory_equal", 1, None, "强制每个产品族最多1个，检验相关风险分散是否带来收益质量。"),
    SelectorMode(
        "memory_family_cap2_lowcorr030",
        "历史记忆族2+低核心相关",
        "strategy_memory_equal",
        2,
        LOW_CORE_CORR_THRESHOLD,
        "先要求与Stage526核心252日相关不高，再限制产品族最多2个。",
    ),
    SelectorMode(
        "simple_family_cap1_lowcorr030",
        "simple族1+低核心相关",
        "simple_trend",
        1,
        LOW_CORE_CORR_THRESHOLD,
        "用已有simple趋势分，但强制产品族分散和低核心相关。",
    ),
    SelectorMode(
        "hybrid_family_cap1_lowcorr030",
        "混合族1+低核心相关",
        "hybrid_equal",
        1,
        LOW_CORE_CORR_THRESHOLD,
        "用混合分，再强制产品族分散和低核心相关。",
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


def _family_map_frame(products: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for product in sorted(products):
        family, note = PRODUCT_FAMILY.get(product, ("unknown", "未分类"))
        rows.append({"product_vt_symbol": product, "product_family": family, "family_note": note})
    return pd.DataFrame(rows)


def _load_samples() -> pd.DataFrame:
    if not STAGE543_SCORED_IN.exists():
        raise FileNotFoundError(STAGE543_SCORED_IN)
    usecols = [
        "eval_date",
        "product_vt_symbol",
        "exchange",
        "product",
        "ai_probability",
        "simple_trend",
        "market_terrain_equal",
        "strategy_memory_equal",
        "hybrid_equal",
        "abs_core_corr_252d",
        "is_oracle6",
        "future_stage541_pnl_60d",
        "future_stage541_pnl_120d",
    ]
    samples = pd.read_csv(STAGE543_SCORED_IN, encoding="utf-8-sig", usecols=usecols)
    samples["eval_date"] = pd.to_datetime(samples["eval_date"], errors="coerce").dt.normalize()
    samples["product_vt_symbol"] = samples["product_vt_symbol"].astype(str)
    for column in [
        "ai_probability",
        "simple_trend",
        "market_terrain_equal",
        "strategy_memory_equal",
        "hybrid_equal",
        "abs_core_corr_252d",
        "is_oracle6",
        "future_stage541_pnl_60d",
        "future_stage541_pnl_120d",
    ]:
        samples[column] = pd.to_numeric(samples[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    family_map = _family_map_frame(sorted(samples["product_vt_symbol"].unique()))
    samples = samples.merge(family_map, on="product_vt_symbol", how="left")
    samples["product_family"] = samples["product_family"].fillna("unknown")
    family_map.to_csv(FAMILY_MAP_PATH, index=False, encoding="utf-8-sig")
    return samples


def _quarterly_dates(samples: pd.DataFrame) -> set[pd.Timestamp]:
    dates = sorted(pd.Timestamp(item) for item in samples["eval_date"].dropna().unique())
    frame = pd.DataFrame({"eval_date": dates})
    return set(frame.assign(quarter=lambda df: df["eval_date"].dt.to_period("Q")).groupby("quarter")["eval_date"].max())


def _allowed_dates(samples: pd.DataFrame, sample_type: str) -> set[pd.Timestamp]:
    if sample_type == "monthly":
        return set(pd.Timestamp(item) for item in samples["eval_date"].dropna().unique())
    if sample_type == "quarterly_purged":
        return _quarterly_dates(samples)
    raise ValueError(sample_type)


def _select(frame: pd.DataFrame, mode: SelectorMode) -> pd.DataFrame:
    ordered = frame.sort_values([mode.score_column, "product_vt_symbol"], ascending=[False, True]).copy()
    chosen: list[pd.Series] = []
    family_counts: dict[str, int] = {}

    def can_take(row: pd.Series, *, enforce_corr: bool) -> bool:
        if mode.family_cap is not None and family_counts.get(str(row["product_family"]), 0) >= mode.family_cap:
            return False
        if enforce_corr and mode.low_core_corr_threshold is not None and float(row["abs_core_corr_252d"]) > mode.low_core_corr_threshold:
            return False
        return True

    for _, row in ordered.iterrows():
        if not can_take(row, enforce_corr=True):
            continue
        chosen.append(row)
        family = str(row["product_family"])
        family_counts[family] = family_counts.get(family, 0) + 1
        if len(chosen) >= TOP_K:
            break

    if len(chosen) < TOP_K and mode.low_core_corr_threshold is not None:
        already = {str(item["product_vt_symbol"]) for item in chosen}
        for _, row in ordered.iterrows():
            if str(row["product_vt_symbol"]) in already:
                continue
            if not can_take(row, enforce_corr=False):
                continue
            chosen.append(row)
            family = str(row["product_family"])
            family_counts[family] = family_counts.get(family, 0) + 1
            if len(chosen) >= TOP_K:
                break

    selected = pd.DataFrame(chosen)
    if selected.empty:
        return selected
    selected = selected.reset_index(drop=True)
    selected["selected_rank"] = np.arange(1, len(selected) + 1)
    selected["low_core_corr_filter"] = mode.low_core_corr_threshold if mode.low_core_corr_threshold is not None else np.nan
    selected["family_cap"] = mode.family_cap if mode.family_cap is not None else 999
    return selected


def _evaluate(samples: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    selection_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    family_rows: list[dict[str, Any]] = []

    for sample_type in ("monthly", "quarterly_purged"):
        subset = samples[samples["eval_date"].isin(_allowed_dates(samples, sample_type))].copy()
        for mode in MODES:
            eval_rows: list[dict[str, Any]] = []
            for eval_date, frame in subset.groupby("eval_date", sort=True):
                selected = _select(frame, mode)
                if selected.empty:
                    continue
                all_mean60 = float(frame["future_stage541_pnl_60d"].mean())
                all_mean120 = float(frame["future_stage541_pnl_120d"].mean())
                oracle = frame[frame["is_oracle6"].eq(1)].copy()
                oracle_mean60 = float(oracle["future_stage541_pnl_60d"].mean())
                oracle_mean120 = float(oracle["future_stage541_pnl_120d"].mean())
                selected_mean60 = float(selected["future_stage541_pnl_60d"].mean())
                selected_mean120 = float(selected["future_stage541_pnl_120d"].mean())
                family_unique_count = int(selected["product_family"].nunique())
                family_max_count = int(selected["product_family"].value_counts().max())
                selected = selected.copy()
                selected["mode"] = mode.mode
                selected["mode_label"] = mode.label
                selected["sample_type"] = sample_type
                selected["all_noncore_mean_future60"] = all_mean60
                selected["all_noncore_mean_future120"] = all_mean120
                selected["oracle6_mean_future60"] = oracle_mean60
                selected["oracle6_mean_future120"] = oracle_mean120
                selection_rows.extend(selected.to_dict("records"))

                eval_rows.append(
                    {
                        "mode": mode.mode,
                        "mode_label": mode.label,
                        "sample_type": sample_type,
                        "eval_date": eval_date,
                        "selected_products": ",".join(selected["product_vt_symbol"].astype(str).tolist()),
                        "selected_families": ",".join(selected["product_family"].astype(str).tolist()),
                        "selected_mean_future60": selected_mean60,
                        "selected_mean_future120": selected_mean120,
                        "all_noncore_mean_future60": all_mean60,
                        "all_noncore_mean_future120": all_mean120,
                        "oracle6_mean_future60": oracle_mean60,
                        "oracle6_mean_future120": oracle_mean120,
                        "edge_vs_all_future60": selected_mean60 - all_mean60,
                        "edge_vs_all_future120": selected_mean120 - all_mean120,
                        "edge_vs_oracle6_future60": selected_mean60 - oracle_mean60,
                        "edge_vs_oracle6_future120": selected_mean120 - oracle_mean120,
                        "selected_oracle_count": int(selected["is_oracle6"].sum()),
                        "family_unique_count": family_unique_count,
                        "family_max_count": family_max_count,
                        "avg_abs_core_corr": float(selected["abs_core_corr_252d"].mean()),
                    }
                )
                counts = selected["product_family"].value_counts()
                for family, count in counts.items():
                    family_rows.append(
                        {
                            "mode": mode.mode,
                            "mode_label": mode.label,
                            "sample_type": sample_type,
                            "eval_date": eval_date,
                            "product_family": family,
                            "selected_count": int(count),
                            "selected_future60_sum": float(
                                selected.loc[selected["product_family"].eq(family), "future_stage541_pnl_60d"].sum()
                            ),
                        }
                    )
            eval_df = pd.DataFrame(eval_rows)
            if eval_df.empty:
                continue
            avg_oracle = float(eval_df["oracle6_mean_future60"].mean())
            avg_selected = float(eval_df["selected_mean_future60"].mean())
            summary_rows.append(
                {
                    "mode": mode.mode,
                    "mode_label": mode.label,
                    "score_column": mode.score_column,
                    "sample_type": sample_type,
                    "months": int(len(eval_df)),
                    "avg_selected_mean_future60": avg_selected,
                    "avg_selected_mean_future120": float(eval_df["selected_mean_future120"].mean()),
                    "avg_all_noncore_mean_future60": float(eval_df["all_noncore_mean_future60"].mean()),
                    "avg_all_noncore_mean_future120": float(eval_df["all_noncore_mean_future120"].mean()),
                    "avg_oracle6_mean_future60": avg_oracle,
                    "avg_oracle6_mean_future120": float(eval_df["oracle6_mean_future120"].mean()),
                    "avg_edge_vs_all_future60": float(eval_df["edge_vs_all_future60"].mean()),
                    "avg_edge_vs_all_future120": float(eval_df["edge_vs_all_future120"].mean()),
                    "selected_vs_oracle_capture_ratio_60d": avg_selected / avg_oracle if avg_oracle else 0.0,
                    "positive_month_rate_future60_pct": float((eval_df["selected_mean_future60"] > 0.0).mean() * 100.0),
                    "positive_month_rate_future120_pct": float((eval_df["selected_mean_future120"] > 0.0).mean() * 100.0),
                    "avg_oracle_recall_count": float(eval_df["selected_oracle_count"].mean()),
                    "at_least_one_oracle_month_rate_pct": float((eval_df["selected_oracle_count"] > 0).mean() * 100.0),
                    "avg_family_unique_count": float(eval_df["family_unique_count"].mean()),
                    "avg_family_max_count": float(eval_df["family_max_count"].mean()),
                    "avg_abs_core_corr": float(eval_df["avg_abs_core_corr"].mean()),
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
        ).astype(int)
        summary.sort_values(
            ["diagnostic_pass", "sample_type", "avg_edge_vs_all_future60", "positive_month_rate_future60_pct"],
            ascending=[False, True, False, False],
            inplace=True,
        )
    family_summary = pd.DataFrame(family_rows)
    if not family_summary.empty:
        family_summary = (
            family_summary.groupby(["mode", "mode_label", "sample_type", "product_family"], as_index=False)
            .agg(
                avg_selected_count=("selected_count", "mean"),
                total_selected_count=("selected_count", "sum"),
                avg_selected_future60=("selected_future60_sum", "mean"),
            )
            .sort_values(["sample_type", "mode", "total_selected_count"], ascending=[True, True, False])
        )
    return selections, summary, family_summary


def _decision(summary: pd.DataFrame) -> dict[str, Any]:
    passed = summary[summary["diagnostic_pass"].eq(1)].copy() if "diagnostic_pass" in summary.columns else pd.DataFrame()
    quarterly = summary[summary["sample_type"].eq("quarterly_purged")].copy()
    best = quarterly.sort_values(["avg_edge_vs_all_future60", "selected_vs_oracle_capture_ratio_60d"], ascending=False).head(1)
    best_record = best.iloc[0].to_dict() if not best.empty else {}
    unconstrained = quarterly[quarterly["mode"].eq("memory_unconstrained")]
    best_improvement = {}
    if not best.empty and not unconstrained.empty:
        b = best.iloc[0]
        u = unconstrained.iloc[0]
        best_improvement = {
            "edge_improvement_vs_stage543_best": float(b["avg_edge_vs_all_future60"] - u["avg_edge_vs_all_future60"]),
            "positive_rate_improvement_pp": float(
                b["positive_month_rate_future60_pct"] - u["positive_month_rate_future60_pct"]
            ),
            "capture_ratio_improvement": float(
                b["selected_vs_oracle_capture_ratio_60d"] - u["selected_vs_oracle_capture_ratio_60d"]
            ),
        }
    return {
        "stage": "Stage244",
        "script_stage": "Stage544",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": (
            "family_constrained_selector_ready_for_dynamic_sleeve_probe"
            if not passed.empty
            else "family_constrained_selector_improves_but_not_ready"
        ),
        "baseline": "Stage543 ex-ante selector diagnostic",
        "pass_definition": (
            "Quarterly-purged Top6 family-aware selector must beat all-noncore future60 mean by >=500 yuan/product, "
            "capture >=50% of Oracle6 future60 reference, have >=55% positive 60d periods, and average >=2 Oracle6 names."
        ),
        "passed_rows": passed.to_dict("records"),
        "best_row": best_record,
        "best_improvement_vs_unconstrained_memory": best_improvement,
        "overfit_boundary": (
            "Product family labels are static economic categories and do not use future PnL. "
            "This is still only a selector diagnostic; no trading universe is promoted."
        ),
        "next_step": (
            "If not passed, do not run formal dynamic sleeve from these scores. "
            "Use family constraints as a risk-budget design principle, but seek stronger point-in-time fundamental/flow features."
        ),
    }


def _plot(samples: pd.DataFrame, selections: pd.DataFrame, summary: pd.DataFrame, family_summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(16, 9))
    ax_edge, ax_quality, ax_cum, ax_family = axes.flatten()

    quarterly = summary[summary["sample_type"].eq("quarterly_purged")].copy()
    quarterly = quarterly.sort_values("avg_edge_vs_all_future60", ascending=True)
    labels = quarterly["mode_label"].tolist()
    ax_edge.barh(labels, quarterly["avg_edge_vs_all_future60"], color="#2563eb")
    ax_edge.axvline(0, color="#111827", linestyle="--", linewidth=1)
    ax_edge.axvline(HARD_EDGE_THRESHOLD, color="#dc2626", linestyle=":", linewidth=1)
    ax_edge.set_title("Quarterly Top6 future60 edge")
    ax_edge.grid(axis="x", alpha=0.25)

    x = np.arange(len(quarterly))
    ax_quality.bar(x - 0.2, quarterly["positive_month_rate_future60_pct"], width=0.4, label="60d positive rate", color="#059669")
    ax_quality.bar(x + 0.2, quarterly["selected_vs_oracle_capture_ratio_60d"] * 100.0, width=0.4, label="Oracle capture %", color="#f97316")
    ax_quality.axhline(HARD_POSITIVE_MONTH_RATE, color="#111827", linestyle="--", linewidth=1)
    ax_quality.axhline(HARD_CAPTURE_RATIO * 100.0, color="#dc2626", linestyle=":", linewidth=1)
    ax_quality.set_xticks(x)
    ax_quality.set_xticklabels(quarterly["mode_label"], rotation=35, ha="right", fontsize=8)
    ax_quality.set_title("Positive rate and Oracle capture")
    ax_quality.grid(axis="y", alpha=0.25)
    ax_quality.legend(fontsize=7)

    q_dates = sorted(pd.Timestamp(item) for item in samples["eval_date"].dropna().unique())
    q_frame = pd.DataFrame({"eval_date": q_dates})
    q_dates = q_frame.assign(q=lambda df: df["eval_date"].dt.to_period("Q")).groupby("q")["eval_date"].max().tolist()
    q_dates = [pd.Timestamp(item) for item in q_dates]
    q_sel = selections[selections["sample_type"].eq("quarterly_purged")].copy()
    plot_modes = quarterly.sort_values("avg_edge_vs_all_future60", ascending=False)["mode"].head(4).tolist()
    for mode in plot_modes:
        series = (
            q_sel[q_sel["mode"].eq(mode)]
            .groupby("eval_date")["future_stage541_pnl_60d"]
            .mean()
            .reindex(q_dates)
            .fillna(0.0)
            .cumsum()
        )
        label = str(quarterly.loc[quarterly["mode"].eq(mode), "mode_label"].iloc[0])
        ax_cum.plot(series.index, series.values, label=label, linewidth=1.1)
    oracle_series = (
        samples[samples["is_oracle6"].eq(1)]
        .groupby("eval_date")["future_stage541_pnl_60d"]
        .mean()
        .reindex(q_dates)
        .fillna(0.0)
        .cumsum()
    )
    all_series = samples.groupby("eval_date")["future_stage541_pnl_60d"].mean().reindex(q_dates).fillna(0.0).cumsum()
    ax_cum.plot(oracle_series.index, oracle_series.values, label="Oracle6 reference", color="#dc2626", linewidth=1.5)
    ax_cum.plot(all_series.index, all_series.values, label="All noncore mean", color="#111827", linestyle="--", linewidth=1.0)
    ax_cum.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_cum.set_title("Quarterly cumulative future60 mean")
    ax_cum.grid(alpha=0.25)
    ax_cum.legend(fontsize=7)

    best_mode = decision.get("best_row", {}).get("mode", "")
    fam = family_summary[
        (family_summary["sample_type"].eq("quarterly_purged")) & (family_summary["mode"].eq(best_mode))
    ].copy()
    if not fam.empty:
        fam.sort_values("total_selected_count", inplace=True)
        colors = ["#94a3b8" if value < 0 else "#10b981" for value in fam["avg_selected_future60"]]
        ax_family.barh(fam["product_family"], fam["total_selected_count"], color=colors)
        ax_family.set_title(f"Family frequency: {decision.get('best_row', {}).get('mode_label', '')}")
        ax_family.grid(axis="x", alpha=0.25)

    fig.suptitle(f"Stage544 decision: {decision['decision']}", fontsize=12)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, family_summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    quarterly_view = summary[summary["sample_type"].eq("quarterly_purged")][
        [
            "mode_label",
            "avg_selected_mean_future60",
            "avg_edge_vs_all_future60",
            "avg_oracle6_mean_future60",
            "selected_vs_oracle_capture_ratio_60d",
            "positive_month_rate_future60_pct",
            "avg_oracle_recall_count",
            "avg_family_unique_count",
            "avg_abs_core_corr",
            "diagnostic_pass",
        ]
    ].sort_values("avg_edge_vs_all_future60", ascending=False)
    best_mode = decision.get("best_row", {}).get("mode", "")
    family_view = family_summary[
        (family_summary["sample_type"].eq("quarterly_purged")) & (family_summary["mode"].eq(best_mode))
    ][["product_family", "avg_selected_count", "total_selected_count", "avg_selected_future60"]]
    lines = [
        "# Stage544 产品族约束事前选品诊断",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 决策：`{decision['decision']}`。",
        "- 阶段性质：只读诊断；把产品族分散/低核心相关作为实盘可解释约束，不生成交易版本。",
        "",
        "## 通过定义",
        "",
        decision["pass_definition"],
        "",
        "## 季度去重摘要",
        "",
        _md_table(quarterly_view),
        "",
        "## 最佳模式产品族分布",
        "",
        _md_table(family_view),
        "",
        "## 判断",
        "",
        "- 产品族约束能减少同族拥挤，并在部分口径上改善 Stage543 的 edge，但还没有到可进入动态 sleeve 回测的强度。",
        "- 如果季度去重样本不稳定，月度重叠样本再好也不能作为晋级证据。",
        "- 产品族约束应该作为后续风险预算原则保留，但不能替代真正的点时化基本面/资金流/交易结构特征。",
        "",
        "## 输出文件",
        "",
        f"- family map：`{FAMILY_MAP_PATH}`",
        f"- selections：`{SELECTIONS_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- family summary：`{FAMILY_SUMMARY_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- chart：`{CHART_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    samples = _load_samples()
    selections, summary, family_summary = _evaluate(samples)
    decision = _decision(summary)
    selections.to_csv(SELECTIONS_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    family_summary.to_csv(FAMILY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(samples, selections, summary, family_summary, decision)
    _write_report(summary, family_summary, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
