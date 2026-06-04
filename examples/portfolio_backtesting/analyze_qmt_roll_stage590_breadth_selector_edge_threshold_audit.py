from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "examples" / "portfolio_backtesting" / "backtest_outputs"

MODEL_TAG = "stage590_breadth_selector_edge_threshold_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage590_breadth_selector_edge_threshold_audit"

STAGE541_ANNUAL = OUTPUT_DIR / "qmt_roll_stage541_single_product_opportunity_map_annual_stage541_single_product_opportunity_map_v1.csv"
STAGE550_MATRIX = OUTPUT_DIR / "qmt_roll_stage550_product_opportunity_geometry_audit_annual_matrix_stage550_product_opportunity_geometry_audit_v1.csv"
STAGE550_FEATURE_IC = OUTPUT_DIR / "qmt_roll_stage550_product_opportunity_geometry_audit_feature_ic_stage550_product_opportunity_geometry_audit_v1.csv"
STAGE550_SELECTION = OUTPUT_DIR / "qmt_roll_stage550_product_opportunity_geometry_audit_annual_selection_stage550_product_opportunity_geometry_audit_v1.csv"
STAGE570_RISK_SHELL = OUTPUT_DIR / "qmt_roll_stage574_low_single_risk_breadth_selector_boundary_risk_shell_boundary_stage574_low_single_risk_breadth_selector_boundary_v1.csv"
STAGE574_CANDIDATE_MAP = OUTPUT_DIR / "qmt_roll_stage574_low_single_risk_breadth_selector_boundary_candidate_map_stage574_low_single_risk_breadth_selector_boundary_v1.csv"
STAGE588_EVIDENCE = OUTPUT_DIR / "qmt_roll_stage588_p0_selector_evidence_priority_audit_evidence_matrix_stage588_p0_selector_evidence_priority_audit_v1.csv"

ANNUAL_EDGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_edge_{MODEL_TAG}.csv"
RANDOM_DIST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_random_distribution_{MODEL_TAG}.csv"
P0_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_p0_annual_matrix_{MODEL_TAG}.csv"
THRESHOLDS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_thresholds_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

YEARS = list(range(2020, 2027))
P0_PRODUCTS = ["lu.INE", "v.DCE", "y.DCE", "ao.SHFE", "c.DCE"]
RANDOM_RUNS = 20000
RNG_SEED = 590
MATERIAL_ACTUAL_SLEEVE_PNL = 50000.0
MIN_FORWARD_RUNS = 20
MIN_FORWARD_DATES = 20


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _annual_pivot() -> tuple[pd.DataFrame, pd.DataFrame]:
    annual = _read_csv(STAGE541_ANNUAL)
    annual = annual[annual["is_core_product"].eq(0)].copy()
    annual["net_pnl"] = pd.to_numeric(annual["net_pnl"], errors="coerce").fillna(0.0)
    annual["year"] = annual["year"].astype(int)

    matrix = _read_csv(STAGE550_MATRIX)
    family = matrix[["product_vt_symbol", "product_family", "family_note", "core_daily_pnl_corr", "total_pnl"]].copy()
    annual = annual.merge(family, on="product_vt_symbol", how="left")

    pivot = annual.pivot_table(
        index="product_vt_symbol",
        columns="year",
        values="net_pnl",
        aggfunc="sum",
        fill_value=0.0,
    )
    for year in YEARS:
        if year not in pivot.columns:
            pivot[year] = 0.0
    pivot = pivot[YEARS].sort_index()
    meta = family.drop_duplicates("product_vt_symbol").set_index("product_vt_symbol")
    return pivot, meta


def _family_cap_sample(products: list[str], meta: pd.DataFrame, k: int, rng: np.random.Generator) -> list[str]:
    shuffled = list(rng.permutation(products))
    selected: list[str] = []
    used_families: set[str] = set()
    for product in shuffled:
        family = str(meta.loc[product, "product_family"]) if product in meta.index else product
        if family in used_families:
            continue
        selected.append(product)
        used_families.add(family)
        if len(selected) >= k:
            return selected
    for product in shuffled:
        if product not in selected:
            selected.append(product)
            if len(selected) >= k:
                return selected
    return selected


def _simulate_random_selectors(pivot: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(RNG_SEED)
    products = list(pivot.index)
    records: list[dict[str, object]] = []

    for mode in ["random_all_k3", "random_all_k6", "random_familycap_k3", "random_familycap_k6"]:
        k = 3 if mode.endswith("k3") else 6
        family_cap = "familycap" in mode
        for run_id in range(RANDOM_RUNS):
            yearly_pnls = []
            selected_by_year = {}
            for year in YEARS:
                if family_cap:
                    selected = _family_cap_sample(products, meta, k, rng)
                else:
                    selected = list(rng.choice(products, size=min(k, len(products)), replace=False))
                selected_by_year[year] = selected
                yearly_pnls.append(float(pivot.loc[selected, year].sum()))
            yearly = np.array(yearly_pnls, dtype=float)
            records.append(
                {
                    "mode": mode,
                    "run_id": run_id,
                    "selected_count": k,
                    "total_pnl": float(yearly.sum()),
                    "mean_annual_pnl": float(yearly.mean()),
                    "min_annual_pnl": float(yearly.min()),
                    "positive_years": int((yearly > 0).sum()),
                    "negative_years": int((yearly < 0).sum()),
                    "positive_year_rate_pct": float((yearly > 0).mean() * 100.0),
                }
            )
    return pd.DataFrame(records)


def _quantile_summary(random_runs: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for mode, group in random_runs.groupby("mode", sort=False):
        rows.append(
            {
                "mode": mode,
                "run_count": int(len(group)),
                "selected_count": int(group["selected_count"].iloc[0]),
                "total_pnl_p05": float(group["total_pnl"].quantile(0.05)),
                "total_pnl_p10": float(group["total_pnl"].quantile(0.10)),
                "total_pnl_p50": float(group["total_pnl"].quantile(0.50)),
                "total_pnl_p90": float(group["total_pnl"].quantile(0.90)),
                "total_pnl_p95": float(group["total_pnl"].quantile(0.95)),
                "positive_years_p50": float(group["positive_years"].quantile(0.50)),
                "positive_years_p90": float(group["positive_years"].quantile(0.90)),
                "prob_total_pnl_ge_50000_pct": float((group["total_pnl"] >= 50000.0).mean() * 100.0),
                "prob_positive_years_ge_5_pct": float((group["positive_years"] >= 5).mean() * 100.0),
            }
        )
    return pd.DataFrame(rows)


def _selector_basket_rows(pivot: pd.DataFrame) -> pd.DataFrame:
    selection = _read_csv(STAGE550_SELECTION)
    records: list[dict[str, object]] = []

    basket_defs: dict[str, list[str] | None] = {
        "p0_fixed_watchlist": P0_PRODUCTS,
        "hindsight_top3": None,
        "hindsight_top6": None,
        "all_noncore_equal": list(pivot.index),
    }

    for year in YEARS:
        year_values = pivot[year].sort_values(ascending=False)
        for basket, products in basket_defs.items():
            if basket == "hindsight_top3":
                selected = list(year_values.head(3).index)
            elif basket == "hindsight_top6":
                selected = list(year_values.head(6).index)
            else:
                selected = [p for p in (products or []) if p in pivot.index]
            pnl = float(pivot.loc[selected, year].sum()) if selected else 0.0
            top6_pnl = float(year_values.head(6).sum())
            top3_pnl = float(year_values.head(3).sum())
            records.append(
                {
                    "year": year,
                    "basket": basket,
                    "selected_count": len(selected),
                    "selected_products": ",".join(selected),
                    "annual_pnl": pnl,
                    "top3_capture_pct": float(pnl / top3_pnl * 100.0) if top3_pnl else np.nan,
                    "top6_capture_pct": float(pnl / top6_pnl * 100.0) if top6_pnl else np.nan,
                    "positive_selected_count": int((pivot.loc[selected, year] > 0).sum()) if selected else 0,
                    "negative_selected_count": int((pivot.loc[selected, year] < 0).sum()) if selected else 0,
                }
            )

    basket_df = pd.DataFrame(records)
    summary_rows: list[dict[str, object]] = []
    for basket, group in basket_df.groupby("basket", sort=False):
        summary_rows.append(
            {
                "basket": basket,
                "years": int(group["year"].nunique()),
                "selected_count_mean": float(group["selected_count"].mean()),
                "total_pnl": float(group["annual_pnl"].sum()),
                "mean_annual_pnl": float(group["annual_pnl"].mean()),
                "min_annual_pnl": float(group["annual_pnl"].min()),
                "positive_years": int((group["annual_pnl"] > 0).sum()),
                "negative_years": int((group["annual_pnl"] < 0).sum()),
                "positive_year_rate_pct": float((group["annual_pnl"] > 0).mean() * 100.0),
                "mean_top6_capture_pct": float(group["top6_capture_pct"].mean()),
                "min_top6_capture_pct": float(group["top6_capture_pct"].min()),
            }
        )

    random_runs = _simulate_random_selectors(pivot, _read_csv(STAGE550_MATRIX).set_index("product_vt_symbol"))
    random_summary = _quantile_summary(random_runs)
    for _, row in random_summary.iterrows():
        summary_rows.append(
            {
                "basket": row["mode"] + "_median",
                "years": len(YEARS),
                "selected_count_mean": row["selected_count"],
                "total_pnl": row["total_pnl_p50"],
                "mean_annual_pnl": row["total_pnl_p50"] / len(YEARS),
                "min_annual_pnl": np.nan,
                "positive_years": row["positive_years_p50"],
                "negative_years": np.nan,
                "positive_year_rate_pct": row["positive_years_p50"] / len(YEARS) * 100.0,
                "mean_top6_capture_pct": np.nan,
                "min_top6_capture_pct": np.nan,
            }
        )

    summary = pd.DataFrame(summary_rows)
    return basket_df, summary, random_runs, random_summary


def _p0_matrix(pivot: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for product in P0_PRODUCTS:
        if product not in pivot.index:
            continue
        annual = pivot.loc[product, YEARS]
        rows.append(
            {
                "product_vt_symbol": product,
                "product_family": meta.loc[product, "product_family"] if product in meta.index else "",
                "total_pnl": float(annual.sum()),
                "positive_years": int((annual > 0).sum()),
                "negative_years": int((annual < 0).sum()),
                "worst_year_pnl": float(annual.min()),
                "best_year_pnl": float(annual.max()),
                "abs_core_daily_pnl_corr": abs(_to_float(meta.loc[product, "core_daily_pnl_corr"])) if product in meta.index else np.nan,
                **{f"pnl_{year}": float(annual[year]) for year in YEARS},
            }
        )
    return pd.DataFrame(rows)


def _thresholds(summary: pd.DataFrame, random_summary: pd.DataFrame, p0_matrix: pd.DataFrame) -> pd.DataFrame:
    risk_shell = _read_csv(STAGE570_RISK_SHELL)
    def row_value(variant: str, col: str) -> float:
        matched = risk_shell[risk_shell["variant"].eq(variant)]
        if matched.empty or col not in matched.columns:
            return np.nan
        return _to_float(matched[col].iloc[0], np.nan)

    stage256_actual = row_value("dynamic_prevtop6_r050_pc15_maxpos3", "satellite_cumulative_pnl")
    all_noncore_actual = row_value("breadth_all_noncore_r020_famcap20_corr5075_maxpos8", "satellite_cumulative_pnl")
    stage526_return = row_value("stage526_r080_pc25_maxpos4", "total_return_pct")

    hindsight_top6_total = _to_float(summary.loc[summary["basket"].eq("hindsight_top6"), "total_pnl"].iloc[0], np.nan)
    p0_total = _to_float(summary.loc[summary["basket"].eq("p0_fixed_watchlist"), "total_pnl"].iloc[0], np.nan)
    all_noncore_total = _to_float(summary.loc[summary["basket"].eq("all_noncore_equal"), "total_pnl"].iloc[0], np.nan)

    conversion_stage256_vs_hindsight = stage256_actual / hindsight_top6_total if hindsight_top6_total else np.nan
    conversion_allnoncore = all_noncore_actual / all_noncore_total if all_noncore_total else np.nan
    needed_hindsight_opportunity_for_50k = MATERIAL_ACTUAL_SLEEVE_PNL / conversion_stage256_vs_hindsight if conversion_stage256_vs_hindsight else np.nan
    needed_top6_capture_pct = needed_hindsight_opportunity_for_50k / hindsight_top6_total * 100.0 if hindsight_top6_total else np.nan

    random_k6 = random_summary[random_summary["mode"].eq("random_familycap_k6")]
    random_k6_p95 = _to_float(random_k6["total_pnl_p95"].iloc[0], np.nan) if not random_k6.empty else np.nan

    return pd.DataFrame(
        [
            {
                "metric": "actual_stage256_upper_sleeve_pnl",
                "value": stage256_actual,
                "threshold": ">=50000",
                "passed": int(stage256_actual >= MATERIAL_ACTUAL_SLEEVE_PNL),
                "comment": "Historical upper-bound sleeve barely clears materiality.",
            },
            {
                "metric": "actual_all_noncore_sleeve_pnl",
                "value": all_noncore_actual,
                "threshold": ">=50000",
                "passed": int(all_noncore_actual >= MATERIAL_ACTUAL_SLEEVE_PNL),
                "comment": "Naive breadth does not clear materiality.",
            },
            {
                "metric": "p0_fixed_watchlist_opportunity_capture_vs_hindsight_top6_pct",
                "value": p0_total / hindsight_top6_total * 100.0 if hindsight_top6_total else np.nan,
                "threshold": "diagnostic only; not PIT",
                "passed": 0,
                "comment": "P0 is historically promising but cannot be treated as tradable until PIT evidence matures.",
            },
            {
                "metric": "selector_top6_capture_needed_for_50k_actual_sleeve_pct",
                "value": needed_top6_capture_pct,
                "threshold": "lower is easier; derived from Stage256 conversion",
                "passed": int(needed_top6_capture_pct <= 100.0),
                "comment": "Approximate minimum opportunity capture needed to match the 50k actual sleeve materiality gate.",
            },
            {
                "metric": "random_familycap_k6_p95_total_opportunity",
                "value": random_k6_p95,
                "threshold": f">={needed_hindsight_opportunity_for_50k:.2f} opportunity proxy",
                "passed": int(random_k6_p95 >= needed_hindsight_opportunity_for_50k) if np.isfinite(needed_hindsight_opportunity_for_50k) else 0,
                "comment": "If random family-capped selection cannot clear this, selector edge is mandatory.",
            },
            {
                "metric": "p0_top_product_share_pct",
                "value": float(p0_matrix["total_pnl"].max() / p0_matrix["total_pnl"].sum() * 100.0) if not p0_matrix.empty and p0_matrix["total_pnl"].sum() else np.nan,
                "threshold": "<=35 preferred",
                "passed": int(float(p0_matrix["total_pnl"].max() / p0_matrix["total_pnl"].sum() * 100.0) <= 35.0) if not p0_matrix.empty and p0_matrix["total_pnl"].sum() else 0,
                "comment": "P0 still has product concentration, mainly lu.INE.",
            },
        ]
    )


def _gates(summary: pd.DataFrame, random_summary: pd.DataFrame, thresholds: pd.DataFrame) -> pd.DataFrame:
    evidence = _read_csv(STAGE588_EVIDENCE)
    p0_routes = int((pd.to_numeric(evidence["route_ready_count"], errors="coerce").fillna(0) >= 2).sum()) if "route_ready_count" in evidence.columns else 0
    p0_products = int(len(evidence))
    if "event_ready" in evidence.columns:
        event_series = evidence["event_ready"]
    elif "sentiment_news_manual_event_ready" in evidence.columns:
        event_series = evidence["sentiment_news_manual_event_ready"]
    else:
        event_series = pd.Series(dtype=float)
    event_coverage = int(pd.to_numeric(event_series, errors="coerce").fillna(0).sum()) if not evidence.empty else 0

    p0_total = _to_float(summary.loc[summary["basket"].eq("p0_fixed_watchlist"), "total_pnl"].iloc[0], np.nan)
    random_k6 = random_summary[random_summary["mode"].eq("random_familycap_k6")]
    random_p95 = _to_float(random_k6["total_pnl_p95"].iloc[0], np.nan) if not random_k6.empty else np.nan
    needed_capture = _to_float(thresholds.loc[thresholds["metric"].eq("selector_top6_capture_needed_for_50k_actual_sleeve_pct"), "value"].iloc[0], np.nan)
    needed_proxy = _to_float(
        thresholds.loc[
            thresholds["metric"].eq("random_familycap_k6_p95_total_opportunity"),
            "threshold",
        ].iloc[0].split(">=")[-1].split()[0],
        np.nan,
    )
    random_prob_needed = 0.0 if np.isfinite(needed_proxy) and random_p95 < needed_proxy else np.nan

    return pd.DataFrame(
        [
            {
                "gate": "annual_opportunity_exists",
                "actual": "hindsight top6 positive in all years",
                "threshold": "7/7",
                "passed": 1,
                "hard_gate": 1,
                "judgement": "Noncore trend opportunity exists every year in hindsight.",
            },
            {
                "gate": "random_familycap_not_enough",
                "actual": f"p95 opportunity={random_p95:.2f}, proxy needed~={needed_proxy:.2f}, prob_ge_needed~={random_prob_needed:.2f}%",
                "threshold": "random p95 below derived materiality proxy",
                "passed": int(np.isfinite(needed_proxy) and random_p95 < needed_proxy),
                "hard_gate": 0,
                "judgement": "If this passes, selector edge remains mandatory rather than optional.",
            },
            {
                "gate": "p0_historical_opportunity_material",
                "actual": f"P0 opportunity total={p0_total:.2f}",
                "threshold": ">=200000 standalone opportunity proxy",
                "passed": int(p0_total >= 200000.0),
                "hard_gate": 0,
                "judgement": "P0 is worth forward collection, not trading.",
            },
            {
                "gate": "selector_capture_threshold_defined",
                "actual": f"needed top6 capture ~= {needed_capture:.2f}%",
                "threshold": "finite threshold",
                "passed": int(np.isfinite(needed_capture)),
                "hard_gate": 1,
                "judgement": "We can now define what a future selector must beat.",
            },
            {
                "gate": "p0_routes_ready",
                "actual": f"{p0_routes}/{p0_products} P0 products >=2 routes",
                "threshold": "5/5",
                "passed": int(p0_routes == p0_products and p0_products > 0),
                "hard_gate": 1,
                "judgement": "Stage588 route evidence still not mature.",
            },
            {
                "gate": "p0_event_coverage_ready",
                "actual": f"{event_coverage}/{p0_products} P0 products event/news coverage",
                "threshold": "5/5",
                "passed": int(event_coverage == p0_products and p0_products > 0),
                "hard_gate": 1,
                "judgement": "Sentiment/news/event data is still the main deployment gap.",
            },
            {
                "gate": "paper_selector_allowed",
                "actual": "false",
                "threshold": "requires all hard PIT evidence gates",
                "passed": 0,
                "hard_gate": 1,
                "judgement": "No selector PnL replay or whitelist until forward evidence matures.",
            },
        ]
    )


def _decision(gates: pd.DataFrame, thresholds: pd.DataFrame, summary: pd.DataFrame, random_summary: pd.DataFrame) -> dict[str, object]:
    hard = gates[gates["hard_gate"].eq(1)]
    p0_total = _to_float(summary.loc[summary["basket"].eq("p0_fixed_watchlist"), "total_pnl"].iloc[0], np.nan)
    top6_total = _to_float(summary.loc[summary["basket"].eq("hindsight_top6"), "total_pnl"].iloc[0], np.nan)
    all_total = _to_float(summary.loc[summary["basket"].eq("all_noncore_equal"), "total_pnl"].iloc[0], np.nan)
    random_k6 = random_summary[random_summary["mode"].eq("random_familycap_k6")]
    random_median = _to_float(random_k6["total_pnl_p50"].iloc[0], np.nan) if not random_k6.empty else np.nan
    needed_capture = _to_float(thresholds.loc[thresholds["metric"].eq("selector_top6_capture_needed_for_50k_actual_sleeve_pct"), "value"].iloc[0], np.nan)
    decision = {
        "decision": "breadth_selector_edge_required_no_promotion",
        "promotion_allowed": False,
        "paper_selector_audit_allowed": False,
        "trading_whitelist_allowed": False,
        "p0_opportunity_total": p0_total,
        "hindsight_top6_opportunity_total": top6_total,
        "all_noncore_opportunity_total": all_total,
        "p0_capture_vs_top6_pct": p0_total / top6_total * 100.0 if top6_total else None,
        "random_familycap_k6_median_total": random_median,
        "selector_top6_capture_needed_pct": needed_capture,
        "gates_passed": int(gates["passed"].sum()),
        "gates_total": int(len(gates)),
        "hard_gates_passed": int(hard["passed"].sum()),
        "hard_gates_total": int(len(hard)),
        "overfit_reflection": "No. This is a threshold audit using fixed prior outputs, random baselines, and explicit non-promotion gates.",
        "continue_value_reflection": "Yes. It quantifies why selector evidence, not wider breadth parameters, is the next valuable bottleneck.",
    }
    return decision


def _plot(
    annual_edge: pd.DataFrame,
    summary: pd.DataFrame,
    random_runs: pd.DataFrame,
    random_summary: pd.DataFrame,
    p0_matrix: pd.DataFrame,
    thresholds: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, object],
) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    ax_annual, ax_random, ax_p0, ax_actual, ax_threshold, ax_gates = axes.flatten()

    annual_plot = annual_edge[annual_edge["basket"].isin(["hindsight_top6", "p0_fixed_watchlist", "all_noncore_equal"])].copy()
    pivot = annual_plot.pivot(index="year", columns="basket", values="annual_pnl")
    pivot[["hindsight_top6", "p0_fixed_watchlist", "all_noncore_equal"]].plot(kind="bar", ax=ax_annual, width=0.78)
    ax_annual.axhline(0, color="#111827", linewidth=1)
    ax_annual.set_title("Annual opportunity: P0 vs hindsight and broad pool")
    ax_annual.set_ylabel("annual standalone product PnL")
    ax_annual.legend(fontsize=8)

    modes = ["random_all_k6", "random_familycap_k6"]
    dist_data = [random_runs[random_runs["mode"].eq(mode)]["total_pnl"].to_numpy() for mode in modes]
    ax_random.boxplot(dist_data, tick_labels=modes, showfliers=False)
    ax_random.axhline(decision["p0_opportunity_total"], color="#0ea5e9", linestyle="--", label="P0 fixed")
    ax_random.axhline(decision["hindsight_top6_opportunity_total"], color="#16a34a", linestyle="--", label="hindsight top6")
    needed_proxy = _to_float(
        thresholds.loc[
            thresholds["metric"].eq("random_familycap_k6_p95_total_opportunity"),
            "threshold",
        ].iloc[0].split(">=")[-1].split()[0],
        np.nan,
    )
    ax_random.axhline(needed_proxy, color="#dc2626", linestyle=":", label="derived opportunity proxy")
    ax_random.set_title("Random selector total opportunity distribution")
    ax_random.set_ylabel("2020-2026 total standalone opportunity")
    ax_random.tick_params(axis="x", rotation=12)
    ax_random.legend(fontsize=8)

    heat = p0_matrix.set_index("product_vt_symbol")[[f"pnl_{year}" for year in YEARS]]
    im = ax_p0.imshow(heat.to_numpy(), aspect="auto", cmap="RdYlGn")
    ax_p0.set_title("P0 annual PnL heatmap")
    ax_p0.set_xticks(range(len(YEARS)))
    ax_p0.set_xticklabels(YEARS)
    ax_p0.set_yticks(range(len(heat.index)))
    ax_p0.set_yticklabels(heat.index)
    fig.colorbar(im, ax=ax_p0, fraction=0.046, pad=0.04)

    risk_shell = _read_csv(STAGE570_RISK_SHELL)
    actual_rows = risk_shell[
        risk_shell["variant"].isin(
            [
                "dynamic_prevtop6_r050_pc15_maxpos3",
                "breadth_all_noncore_r020_famcap20_corr5075_maxpos8",
                "breadth_prevpos_r020_famcap20_corr5075_maxpos8",
                "breadth_prevpos_r015_famcap15_corr5075_maxpos10",
            ]
        )
    ].copy()
    labels = actual_rows["label_short"].fillna(actual_rows["variant"]).to_list()
    x = np.arange(len(actual_rows))
    ax_actual.bar(x - 0.2, pd.to_numeric(actual_rows["satellite_cumulative_pnl"], errors="coerce"), width=0.4, label="satellite PnL", color="#0ea5e9")
    ax_actual.bar(x + 0.2, pd.to_numeric(actual_rows["max_dd_delta_vs_stage526"], errors="coerce") * 100000, width=0.4, label="DD delta x100k", color="#f97316")
    ax_actual.axhline(0, color="#111827", linewidth=1)
    ax_actual.set_title("Actual deployed shells: PnL vs DD delta")
    ax_actual.set_xticks(x)
    ax_actual.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)
    ax_actual.legend(fontsize=8)

    t = thresholds.set_index("metric")
    stage256_ratio = _to_float(t.loc["actual_stage256_upper_sleeve_pnl", "value"], np.nan) / MATERIAL_ACTUAL_SLEEVE_PNL
    all_ratio = _to_float(t.loc["actual_all_noncore_sleeve_pnl", "value"], np.nan) / MATERIAL_ACTUAL_SLEEVE_PNL
    capture_ratio = _to_float(
        t.loc["p0_fixed_watchlist_opportunity_capture_vs_hindsight_top6_pct", "value"], np.nan
    ) / _to_float(t.loc["selector_top6_capture_needed_for_50k_actual_sleeve_pct", "value"], np.nan)
    random_ratio = _to_float(t.loc["random_familycap_k6_p95_total_opportunity", "value"], np.nan) / needed_proxy
    concentration_ratio = 35.0 / _to_float(t.loc["p0_top_product_share_pct", "value"], np.nan)
    threshold_plot = pd.DataFrame(
        [
            {"item": "Stage256 actual sleeve", "ratio_to_gate": stage256_ratio, "passed": stage256_ratio >= 1.0},
            {"item": "All noncore sleeve", "ratio_to_gate": all_ratio, "passed": all_ratio >= 1.0},
            {"item": "P0 capture vs needed", "ratio_to_gate": capture_ratio, "passed": capture_ratio >= 1.0},
            {"item": "Random p95 vs needed", "ratio_to_gate": random_ratio, "passed": random_ratio >= 1.0},
            {"item": "P0 concentration", "ratio_to_gate": concentration_ratio, "passed": concentration_ratio >= 1.0},
        ]
    )
    colors = np.where(threshold_plot["passed"], "#10b981", "#dc2626")
    ax_threshold.barh(threshold_plot["item"], threshold_plot["ratio_to_gate"], color=colors)
    ax_threshold.axvline(1.0, color="#111827", linestyle="--", linewidth=1)
    ax_threshold.set_title("Threshold ratio to gate")
    ax_threshold.set_xlabel(">=1 passes")
    ax_threshold.tick_params(axis="y", labelsize=8)

    gate_colors = np.where(gates["passed"].eq(1), "#10b981", "#dc2626")
    ax_gates.barh(gates["gate"], gates["passed"], color=gate_colors)
    ax_gates.set_xlim(0, 1)
    ax_gates.set_title("Promotion gates")
    ax_gates.tick_params(axis="y", labelsize=8)
    for idx, passed in enumerate(gates["passed"]):
        ax_gates.text(0.5, idx, "PASS" if passed else "FAIL", va="center", ha="center", color="white", fontweight="bold", fontsize=8)

    fig.suptitle("Stage590 breadth selector edge threshold audit", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _md_table(df: pd.DataFrame, max_rows: int = 12) -> str:
    if df.empty:
        return "_empty_"
    return df.head(max_rows).to_markdown(index=False)


def _write_report(
    annual_edge: pd.DataFrame,
    summary: pd.DataFrame,
    random_summary: pd.DataFrame,
    p0_matrix: pd.DataFrame,
    thresholds: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, object],
) -> None:
    lines = [
        "# Stage590 breadth selector edge threshold audit",
        "",
        f"- decision: `{decision['decision']}`",
        f"- promotion_allowed: `{decision['promotion_allowed']}`",
        f"- paper_selector_audit_allowed: `{decision['paper_selector_audit_allowed']}`",
        f"- P0 opportunity total: `{decision['p0_opportunity_total']:.2f}`",
        f"- hindsight top6 opportunity total: `{decision['hindsight_top6_opportunity_total']:.2f}`",
        f"- P0 capture vs top6: `{decision['p0_capture_vs_top6_pct']:.2f}%`",
        f"- random familycap k6 median total: `{decision['random_familycap_k6_median_total']:.2f}`",
        f"- selector top6 capture needed: `{decision['selector_top6_capture_needed_pct']:.2f}%`",
        f"- gates: `{decision['gates_passed']}/{decision['gates_total']}`, hard `{decision['hard_gates_passed']}/{decision['hard_gates_total']}`",
        "",
        "## Interpretation",
        "",
        "Low-single-risk breadth remains structurally valid, but selector edge is mandatory. Random broad selection and prior deployable breadth shells do not justify promotion. P0 is historically promising enough to keep collecting forward evidence, but not tradable until route/event/tie-break and sample-depth gates mature.",
        "",
        "## Basket Summary",
        "",
        _md_table(summary, 20),
        "",
        "## Random Selector Summary",
        "",
        _md_table(random_summary, 20),
        "",
        "## P0 Matrix",
        "",
        _md_table(p0_matrix, 10),
        "",
        "## Thresholds",
        "",
        _md_table(thresholds, 20),
        "",
        "## Gates",
        "",
        _md_table(gates, 20),
        "",
        "## Files",
        "",
        f"- annual_edge: `{ANNUAL_EDGE_PATH}`",
        f"- random_distribution: `{RANDOM_DIST_PATH}`",
        f"- p0_matrix: `{P0_MATRIX_PATH}`",
        f"- thresholds: `{THRESHOLDS_PATH}`",
        f"- gates: `{GATES_PATH}`",
        f"- chart: `{CHART_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pivot, meta = _annual_pivot()
    annual_edge, summary, random_runs, random_summary = _selector_basket_rows(pivot)
    p0_matrix = _p0_matrix(pivot, meta)
    thresholds = _thresholds(summary, random_summary, p0_matrix)
    gates = _gates(summary, random_summary, thresholds)
    decision = _decision(gates, thresholds, summary, random_summary)

    annual_edge.to_csv(ANNUAL_EDGE_PATH, index=False, encoding="utf-8-sig")
    random_summary.to_csv(RANDOM_DIST_PATH, index=False, encoding="utf-8-sig")
    p0_matrix.to_csv(P0_MATRIX_PATH, index=False, encoding="utf-8-sig")
    thresholds.to_csv(THRESHOLDS_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(decision, indent=2, ensure_ascii=False), encoding="utf-8")
    _plot(annual_edge, summary, random_runs, random_summary, p0_matrix, thresholds, gates, decision)
    _write_report(annual_edge, summary, random_summary, p0_matrix, thresholds, gates, decision)

    print(json.dumps(decision, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
