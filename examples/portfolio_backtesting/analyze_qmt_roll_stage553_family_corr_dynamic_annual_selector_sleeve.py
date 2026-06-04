from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513  # noqa: E402
import analyze_qmt_roll_stage516_margin_aware_sizing_frontier as s516  # noqa: E402
import analyze_qmt_roll_stage519_product_margin_cap_frontier as s519  # noqa: E402
import analyze_qmt_roll_stage551_annual_persistence_sleeve_replay as s551  # noqa: E402
import analyze_qmt_roll_stage552_dynamic_annual_selector_sleeve as s552  # noqa: E402
from main_contract_mapping import build_contract_metadata, load_product_universe_symbols  # noqa: E402


MODEL_TAG = "stage553_family_corr_dynamic_annual_selector_sleeve_v1"
OUTPUT_PREFIX = "qmt_roll_stage553_family_corr_dynamic_annual_selector_sleeve"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE552_TAG = "stage552_dynamic_annual_selector_sleeve_v1"
STAGE552_PREFIX = "qmt_roll_stage552_dynamic_annual_selector_sleeve"
STAGE552_COMBINED_DAILY_IN = OUTPUT_DIR / f"{STAGE552_PREFIX}_combined_daily_{STAGE552_TAG}.csv"
STAGE552_SUMMARY_IN = OUTPUT_DIR / f"{STAGE552_PREFIX}_summary_{STAGE552_TAG}.csv"
STAGE552_COST_IN = OUTPUT_DIR / f"{STAGE552_PREFIX}_cost_stress_{STAGE552_TAG}.csv"
STAGE552_ROLLING_IN = OUTPUT_DIR / f"{STAGE552_PREFIX}_rolling_holding_{STAGE552_TAG}.csv"
STAGE552_SELECTION_IN = OUTPUT_DIR / f"{STAGE552_PREFIX}_annual_selection_{STAGE552_TAG}.csv"
STAGE552_SATELLITE_DAILY_IN = OUTPUT_DIR / f"{STAGE552_PREFIX}_satellite_daily_{STAGE552_TAG}.csv"

UNIVERSE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_noncore_commodity_universe_{MODEL_TAG}.csv"
ELIGIBILITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_eligibility_{MODEL_TAG}.csv"
SELECTION_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_selection_{MODEL_TAG}.csv"
COMBINED_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combined_daily_{MODEL_TAG}.csv"
SATELLITE_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_daily_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
SATELLITE_MARGIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_margin_daily_{MODEL_TAG}.csv"
SATELLITE_PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_product_harvest_{MODEL_TAG}.csv"
SATELLITE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_standalone_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_holding_{MODEL_TAG}.csv"
WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_metrics_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

CONTROL = s551.CONTROL
STAGE252_TOP6 = "dynamic_prevtop6_r050_pc15_maxpos3"
NEW_VARIANT = "dynamic_prevtop6_familycap1_lowcorr030_r050_pc15_maxpos3"
LOW_CORE_CORR_THRESHOLD = 0.30
TOP_K = 6


@dataclass(frozen=True)
class Spec:
    variant: str
    selector_mode: str
    label: str
    risk_multiplier: float
    product_cap_ratio: float
    max_concurrent_positions: int
    max_single_trade_capital_usage_ratio: float
    note: str


SPECS: tuple[Spec, ...] = (
    Spec(
        NEW_VARIANT,
        "prev_year_top6_familycap1_lowcorr030",
        "Stage526 + dynamic annual prev-year top6 family-cap1 low-core-corr sleeve r050 pc15 maxpos3",
        0.50,
        0.15,
        3,
        0.35,
        "连续动态宇宙：上一年真实账本按PnL排序，优先选择低核心相关且同产品族最多1个的6个非核心商品；已有持仓自然退出。",
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


def _as_float(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    return pd.to_numeric(frame.get(column, default), errors="coerce").fillna(default).astype(float)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _select_family_corr_products(table: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    ranked = table.sort_values(["prev_year_pnl", "abs_core_corr", "product_vt_symbol"], ascending=[False, True, True]).copy()
    chosen: list[int] = []
    used_families: set[str] = set()

    def take(enforce_corr: bool, enforce_family: bool) -> None:
        nonlocal chosen, used_families
        for idx, row in ranked.iterrows():
            if idx in chosen:
                continue
            family = str(row["product_family"])
            if enforce_corr and float(row["abs_core_corr"]) > LOW_CORE_CORR_THRESHOLD:
                continue
            if enforce_family and family in used_families:
                continue
            chosen.append(idx)
            used_families.add(family)
            if len(chosen) >= TOP_K:
                return

    take(enforce_corr=True, enforce_family=True)
    relax_stage = "strict_lowcorr_familycap1"
    if len(chosen) < TOP_K:
        relax_stage = "relax_lowcorr_keep_familycap1"
        take(enforce_corr=False, enforce_family=True)
    if len(chosen) < TOP_K:
        relax_stage = "relax_family_keep_lowcorr"
        take(enforce_corr=True, enforce_family=False)
    if len(chosen) < TOP_K:
        relax_stage = "relax_all_fill_top6"
        take(enforce_corr=False, enforce_family=False)

    selected = ranked.loc[chosen].copy()
    selected["selected_rank"] = range(1, len(selected) + 1)
    selected["selection_relax_stage"] = relax_stage
    return selected, relax_stage


def _build_universe_and_eligibility() -> tuple[pd.DataFrame, pd.DataFrame]:
    universe, summary, annual, family = s551._load_inputs()
    noncore = s551._noncore_commodity_products(universe, summary)
    universe_out = universe[universe["product_vt_symbol"].isin(noncore)].copy()
    universe_out.sort_values(["exchange", "product_vt_symbol"], inplace=True)
    universe_out.to_csv(UNIVERSE_PATH, index=False, encoding="utf-8-sig")

    base = summary[summary["product_vt_symbol"].isin(noncore)][
        ["product_vt_symbol", "exchange", "product", "core_daily_pnl_corr"]
    ].copy()
    family_map = family[["product_vt_symbol", "product_family", "family_note"]].drop_duplicates("product_vt_symbol")

    selection_rows: list[dict[str, Any]] = []
    eligibility_rows: list[dict[str, Any]] = []
    for year in s551.YEARS:
        prev_year = int(year) - 1
        previous = annual[
            annual["product_vt_symbol"].isin(noncore) & annual["year"].eq(prev_year)
        ][["product_vt_symbol", "net_pnl"]].rename(columns={"net_pnl": "prev_year_pnl"})
        current = annual[
            annual["product_vt_symbol"].isin(noncore) & annual["year"].eq(year)
        ][["product_vt_symbol", "net_pnl"]].rename(columns={"net_pnl": "future_year_single_product_pnl"})
        table = base.merge(previous, on="product_vt_symbol", how="left").merge(current, on="product_vt_symbol", how="left")
        table = table.merge(family_map, on="product_vt_symbol", how="left")
        table["prev_year_pnl"] = _as_float(table, "prev_year_pnl")
        table["future_year_single_product_pnl"] = _as_float(table, "future_year_single_product_pnl")
        table["core_daily_pnl_corr"] = _as_float(table, "core_daily_pnl_corr")
        table["abs_core_corr"] = table["core_daily_pnl_corr"].abs()
        table["product_family"] = table["product_family"].fillna(table["exchange"].astype(str))
        table["family_note"] = table["family_note"].fillna("")

        selected, relax_stage = _select_family_corr_products(table)
        selected_products = selected["product_vt_symbol"].astype(str).tolist()
        selected_families = selected["product_family"].astype(str).tolist()
        family_counts = selected["product_family"].astype(str).value_counts()
        for _, row in selected.iterrows():
            eligibility_rows.append(
                {
                    "strategy": NEW_VARIANT,
                    "eval_date": f"{int(year)}-01-01",
                    "product_vt_symbol": row["product_vt_symbol"],
                    "score": float(TOP_K - int(row["selected_rank"]) + 1),
                    "score_rank": int(row["selected_rank"]),
                    "top_n": int(len(selected)),
                    "selector_mode": "prev_year_top6_familycap1_lowcorr030",
                    "source_prev_year": prev_year,
                    "product_family": row["product_family"],
                    "prev_year_pnl": float(row["prev_year_pnl"]),
                    "abs_core_corr": float(row["abs_core_corr"]),
                    "selection_relax_stage": relax_stage,
                }
            )
        selection_rows.append(
            {
                "variant": NEW_VARIANT,
                "selector_mode": "prev_year_top6_familycap1_lowcorr030",
                "year": int(year),
                "prev_year": prev_year,
                "selected_count": int(len(selected)),
                "selected_products": ",".join(selected_products),
                "family_count": int(selected["product_family"].nunique()) if not selected.empty else 0,
                "family_max_count": int(family_counts.max()) if not family_counts.empty else 0,
                "selected_families_ordered": ",".join(selected_families),
                "prev_year_pnl_sum": float(selected["prev_year_pnl"].sum()) if not selected.empty else 0.0,
                "future_year_single_product_pnl_sum": float(selected["future_year_single_product_pnl"].sum())
                if not selected.empty
                else 0.0,
                "positive_selected_count": int((selected["future_year_single_product_pnl"] > 0.0).sum())
                if not selected.empty
                else 0,
                "oracle6_overlap": int(selected["product_vt_symbol"].isin(s551.ORACLE6).sum()) if not selected.empty else 0,
                "avg_abs_core_corr": float(selected["abs_core_corr"].mean()) if not selected.empty else 0.0,
                "max_abs_core_corr": float(selected["abs_core_corr"].max()) if not selected.empty else 0.0,
                "relax_stage": relax_stage,
            }
        )

    eligibility = pd.DataFrame(eligibility_rows)
    selection = pd.DataFrame(selection_rows)
    eligibility.to_csv(ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")
    selection.to_csv(SELECTION_AUDIT_PATH, index=False, encoding="utf-8-sig")
    return universe_out, selection


def _patch_stage552_paths() -> None:
    s552.UNIVERSE_PATH = UNIVERSE_PATH
    s552.ELIGIBILITY_PATH = ELIGIBILITY_PATH
    s552.SPECS = SPECS


def _load_stage252_comparisons() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    combined = _read_csv(STAGE552_COMBINED_DAILY_IN)
    combined["date"] = pd.to_datetime(combined["date"], errors="coerce").dt.normalize()
    combined = combined[combined["variant"].isin([CONTROL, STAGE252_TOP6])].copy()
    satellite = _read_csv(STAGE552_SATELLITE_DAILY_IN)
    satellite["date"] = pd.to_datetime(satellite["date"], errors="coerce").dt.normalize()
    satellite = satellite[satellite["variant"].eq(STAGE252_TOP6)].copy()
    summary = _read_csv(STAGE552_SUMMARY_IN)
    summary = summary[summary["variant"].isin([CONTROL, STAGE252_TOP6])].copy()
    cost = _read_csv(STAGE552_COST_IN)
    cost = cost[cost["variant"].isin([CONTROL, STAGE252_TOP6])].copy()
    rolling = _read_csv(STAGE552_ROLLING_IN)
    rolling = rolling[rolling["variant"].isin([CONTROL, STAGE252_TOP6])].copy()
    return combined, satellite, summary, cost, rolling


def _selection_comparison(new_selection: pd.DataFrame) -> pd.DataFrame:
    old = _read_csv(STAGE552_SELECTION_IN)
    old = old[old["variant"].eq(STAGE252_TOP6)].copy()
    old["family_max_count"] = old["selected_families"].astype(str).map(
        lambda _: np.nan
    )
    rows: list[dict[str, Any]] = []
    for source, frame in [("stage252_top6", old), ("stage253_family_corr", new_selection)]:
        for _, row in frame.iterrows():
            products = [item for item in str(row.get("selected_products", "")).split(",") if item]
            rows.append(
                {
                    "source": source,
                    "year": int(row["year"]),
                    "selected_count": int(row.get("selected_count", len(products))),
                    "family_count": int(row.get("family_count", 0)),
                    "family_max_count": int(row.get("family_max_count", 0)) if pd.notna(row.get("family_max_count", np.nan)) else np.nan,
                    "avg_abs_core_corr": float(row.get("avg_abs_core_corr", np.nan)) if pd.notna(row.get("avg_abs_core_corr", np.nan)) else np.nan,
                    "future_year_single_product_pnl_sum": float(row.get("future_year_single_product_pnl_sum", 0.0)),
                    "oracle6_overlap": int(row.get("oracle6_overlap", 0)),
                    "selected_products": ",".join(products),
                }
            )
    return pd.DataFrame(rows)


def _plot(
    comparison_daily: pd.DataFrame,
    satellite_daily: pd.DataFrame,
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    rolling: pd.DataFrame,
    selection_compare: pd.DataFrame,
    product_harvest: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    color_map = {
        CONTROL: "#111827",
        STAGE252_TOP6: "#7c3aed",
        NEW_VARIANT: "#059669",
    }
    fig, axes = plt.subplots(3, 2, figsize=(17, 13))
    ax_equity, ax_dd, ax_sat, ax_hold, ax_select, ax_cost = axes.flatten()

    for variant, frame in comparison_daily.groupby("variant", sort=False):
        ordered = frame.sort_values("date")
        ax_equity.plot(ordered["date"], ordered["account_equity"], label=variant, linewidth=0.9, color=color_map.get(variant))
        dd = s551._drawdown_pct(pd.Series(ordered["account_equity"].to_numpy(dtype=float), index=pd.to_datetime(ordered["date"])))
        ax_dd.plot(dd.index, dd.values, label=variant, linewidth=0.8, color=color_map.get(variant))
    ax_equity.set_title("账户权益：Stage252 top6 vs family/corr 约束")
    ax_equity.grid(alpha=0.25)
    ax_equity.legend(fontsize=7)
    ax_dd.axhline(-40, color="#111827", linestyle="--", linewidth=1)
    ax_dd.set_title("账户回撤")
    ax_dd.grid(alpha=0.25)

    for variant, frame in satellite_daily.groupby("variant", sort=False):
        ordered = frame.sort_values("date")
        ax_sat.plot(ordered["date"], ordered["net_pnl"].cumsum(), label=variant, linewidth=0.9, color=color_map.get(variant))
    ax_sat.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_sat.set_title("卫星仓累计PnL")
    ax_sat.grid(alpha=0.25)
    ax_sat.legend(fontsize=7)

    h = rolling[rolling["holding_days"].isin([63, 126])].copy()
    pivot = h.pivot(index="variant", columns="holding_days", values="p05_return_pct")
    pivot = pivot.reindex([CONTROL, STAGE252_TOP6, NEW_VARIANT])
    pivot.plot(kind="barh", ax=ax_hold, color=["#f97316", "#0891b2"])
    ax_hold.axvline(0, color="#111827", linestyle="--", linewidth=1)
    ax_hold.set_title("任意启动持有3/6个月 p05收益")
    ax_hold.set_xlabel("%")
    ax_hold.grid(axis="x", alpha=0.25)

    family_view = selection_compare.pivot(index="year", columns="source", values="family_count").fillna(0.0)
    family_view.plot(kind="bar", ax=ax_select, color=["#7c3aed", "#059669"])
    ax_select.set_title("年度白名单产品族数量")
    ax_select.grid(axis="y", alpha=0.25)

    cost_view = cost.pivot(index="variant", columns="cost_multiplier", values="max_dd_pct")
    cost_view = cost_view.reindex([CONTROL, STAGE252_TOP6, NEW_VARIANT])
    cost_view.plot(kind="barh", ax=ax_cost, color=["#0f172a", "#ea580c", "#b91c1c"])
    ax_cost.axvline(-40, color="#111827", linestyle="--", linewidth=1)
    ax_cost.set_title("1x/2x/3x成本压力最大回撤")
    ax_cost.set_xlabel("%")
    ax_cost.grid(axis="x", alpha=0.25)

    fig.suptitle(f"Stage253 decision: {decision['decision']}", fontsize=12)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _decision(summary: pd.DataFrame, cost: pd.DataFrame, rolling: pd.DataFrame, satellite_summary: pd.DataFrame, product_harvest: pd.DataFrame) -> dict[str, Any]:
    row_map = {str(row["variant"]): row for _, row in summary.iterrows()}
    control = row_map[CONTROL]
    old = row_map[STAGE252_TOP6]
    new = row_map[NEW_VARIANT]
    new_cost = cost[cost["variant"].eq(NEW_VARIANT)].set_index("cost_multiplier")
    old_cost = cost[cost["variant"].eq(STAGE252_TOP6)].set_index("cost_multiplier")
    rolling_pivot = rolling.pivot(index="variant", columns="holding_days", values="p05_return_pct")
    sat = satellite_summary[satellite_summary["variant"].eq(NEW_VARIANT)].iloc[0].to_dict()
    new_product = product_harvest[product_harvest["variant"].eq(NEW_VARIANT)].copy()
    total_product_pnl = float(new_product["satellite_product_net_pnl"].sum()) if not new_product.empty else 0.0
    total_abs_product_pnl = float(new_product["satellite_product_net_pnl"].abs().sum()) if not new_product.empty else 0.0
    top_product_share = 0.0
    if total_abs_product_pnl > 1e-9 and not new_product.empty:
        top_product_share = float(new_product["satellite_product_net_pnl"].abs().max() / total_abs_product_pnl * 100.0)

    no_degrade_vs_stage526 = (
        float(new["total_return_pct"]) >= float(control["total_return_pct"])
        and float(new["max_dd_pct"]) >= float(control["max_dd_pct"])
        and float(new["ulcer_pct"]) <= float(control["ulcer_pct"])
        and float(new["max_broker10_margin_to_equity_pct"]) <= 100.0
        and float(new_cost.loc[2.0, "max_dd_pct"]) >= -40.0
    )
    improves_vs_stage252 = (
        float(new["total_return_pct"]) >= float(old["total_return_pct"])
        and float(new["max_dd_pct"]) >= float(old["max_dd_pct"])
        and float(rolling_pivot.loc[NEW_VARIANT, 63]) >= float(rolling_pivot.loc[STAGE252_TOP6, 63])
        and float(rolling_pivot.loc[NEW_VARIANT, 126]) >= float(rolling_pivot.loc[STAGE252_TOP6, 126])
    )
    decision = "family_corr_dynamic_selector_next_validation_candidate" if no_degrade_vs_stage526 and improves_vs_stage252 else "family_corr_dynamic_selector_not_promotion"
    return {
        "stage": "Stage253",
        "model_tag": MODEL_TAG,
        "decision": decision,
        "baseline": CONTROL,
        "stage252_reference": STAGE252_TOP6,
        "candidate": NEW_VARIANT,
        "hypothesis": "年度top6如果只是同族/同风险因子集中，加入产品族上限和低核心相关优先后应改善路径；若edge消失，则选品收益主要来自集中抓少数品种。",
        "predeclared_gates": {
            "dd40_normal_cost": True,
            "broker10_under_100": True,
            "cost2x_dd40": True,
            "no_degrade_vs_stage526": "return/max_dd/ulcer not worse",
            "beat_stage252_top6": "return/max_dd/63d_p05/126d_p05 not worse",
        },
        "pass_flags": {
            "no_degrade_vs_stage526": bool(no_degrade_vs_stage526),
            "improves_vs_stage252_top6": bool(improves_vs_stage252),
            "cost3x_dd40": bool(float(new_cost.loc[3.0, "max_dd_pct"]) >= -40.0),
        },
        "candidate_metrics": _json_safe(new.to_dict()),
        "stage252_metrics": _json_safe(old.to_dict()),
        "satellite_summary": _json_safe(sat),
        "top_product_abs_share_pct": top_product_share,
        "visual_review": (
            "需要人工查看图：若绿线与紫线几乎重合但卫星PnL更低，说明约束提高了分散但牺牲材料性；"
            "若绿线在2023弱年回撤更浅且3/6个月p05改善，才说明相关性约束有实际路径价值。"
        ),
        "next_step": (
            "若不晋级，年度top6保持paper参考但不再叠加 family/corr 小条件；"
            "若晋级，只做单年/单品种剔除和白名单生效时点复核，不扫TopN或相关阈值。"
        ),
    }


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    rolling: pd.DataFrame,
    window: pd.DataFrame,
    satellite_summary: pd.DataFrame,
    selection: pd.DataFrame,
    selection_compare: pd.DataFrame,
    product_harvest: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage253 年度动态选品产品族/相关性约束审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 研究线：`{LINE_ID}`",
        f"- A：`{CONTROL}`。",
        f"- C0：Stage252 参考 `{STAGE252_TOP6}`。",
        f"- C1：`{NEW_VARIANT}`。",
        "- 新增规则：上一年单品种真实账本按PnL排序；优先选 `abs(core_corr)<=0.30` 且同产品族最多1个；不足6个时按预声明顺序放宽，不看未来收益。",
        "- 固定参数：`risk050/product_cap15/maxpos3/max_single_trade_capital_usage_ratio0.35`；不扫 TopN、risk、cap、相关阈值。",
        f"- 决策：`{decision['decision']}`。",
        "",
        "## 账户总览",
        "",
        s551._md_table(
            summary[
                [
                    "variant",
                    "total_return_pct",
                    "return_vs_stage526_pct",
                    "max_dd_pct",
                    "ulcer_pct",
                    "sharpe",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                    "satellite_cumulative_pnl",
                    "total_slippage",
                    "total_trade_count",
                    "nonzero_daily_win_rate_pct",
                ]
            ]
        ),
        "",
        "## 成本压力",
        "",
        s551._md_table(cost[["variant", "cost_multiplier", "total_return_pct", "max_dd_pct", "ulcer_pct", "sharpe"]]),
        "",
        "## 任意启动3/6个月体验",
        "",
        s551._md_table(
            rolling[rolling["holding_days"].isin([63, 126])][
                [
                    "variant",
                    "holding_days",
                    "p05_return_pct",
                    "median_return_pct",
                    "positive_rate_pct",
                    "min_window_dd_pct",
                    "worst_return_start",
                    "worst_return_end",
                ]
            ]
        ),
        "",
        "## 新年度选择",
        "",
        s551._md_table(selection, max_rows=80),
        "",
        "## Stage252 与 Stage253 选择对照",
        "",
        s551._md_table(selection_compare, max_rows=80),
        "",
        "## 多窗口",
        "",
        s551._md_table(
            window[
                [
                    "variant",
                    "window_name",
                    "window_return_pct",
                    "window_max_dd_pct",
                    "window_ulcer_pct",
                    "window_max_broker10_margin_to_equity_pct",
                    "window_days_over_100pct",
                ]
            ],
            max_rows=80,
        ),
        "",
        "## 卫星 standalone",
        "",
        s551._md_table(satellite_summary),
        "",
        "## 卫星产品年度贡献",
        "",
        s551._md_table(product_harvest, max_rows=80),
        "",
        "## 决策JSON",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    _build_universe_and_eligibility()
    _patch_stage552_paths()
    supported_symbols = load_product_universe_symbols(str(UNIVERSE_PATH))
    metadata = build_contract_metadata(supported_symbols=supported_symbols)
    identity_map = s519._product_identity_cluster_map(metadata)

    satellite_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    snapshot_frames: list[pd.DataFrame] = []
    for spec in SPECS:
        print(f"[stage553] running {spec.variant}", flush=True)
        daily, positions, snapshots = s552._run_dynamic_sleeve(spec, metadata, identity_map)
        satellite_frames.append(daily)
        position_frames.append(positions)
        if not snapshots.empty:
            snapshot_frames.append(snapshots)

    satellite_daily = pd.concat(satellite_frames, ignore_index=True, sort=False)
    positions = pd.concat(position_frames, ignore_index=True, sort=False)
    full_metadata = s551._metadata_for_full_universe()
    satellite_margin_daily, satellite_product_margin = s513._position_margin(positions, full_metadata)
    control_daily = s551._load_control_daily()
    combo_daily = s552._combine_with_core(control_daily, satellite_daily, satellite_margin_daily)

    new_summary, new_cost = s551._summary_and_cost(combo_daily)
    new_rolling = s516._rolling_holding(combo_daily)
    window = s551._window_metrics(combo_daily)
    satellite_summary = s551._satellite_standalone_summary(satellite_daily, satellite_margin_daily)
    product_harvest = s551._satellite_product_harvest(satellite_product_margin)

    old_daily, old_satellite, old_summary, old_cost, old_rolling = _load_stage252_comparisons()
    summary = pd.concat(
        [
            old_summary[old_summary["variant"].isin([CONTROL, STAGE252_TOP6])],
            new_summary[new_summary["variant"].eq(NEW_VARIANT)],
        ],
        ignore_index=True,
        sort=False,
    )
    cost = pd.concat(
        [
            old_cost[old_cost["variant"].isin([CONTROL, STAGE252_TOP6])],
            new_cost[new_cost["variant"].eq(NEW_VARIANT)],
        ],
        ignore_index=True,
        sort=False,
    )
    rolling = pd.concat(
        [
            old_rolling[old_rolling["variant"].isin([CONTROL, STAGE252_TOP6])],
            new_rolling[new_rolling["variant"].eq(NEW_VARIANT)],
        ],
        ignore_index=True,
        sort=False,
    )
    comparison_daily = pd.concat(
        [
            old_daily[old_daily["variant"].isin([CONTROL, STAGE252_TOP6])],
            combo_daily[combo_daily["variant"].eq(NEW_VARIANT)],
        ],
        ignore_index=True,
        sort=False,
    )
    comparison_satellite = pd.concat([old_satellite, satellite_daily], ignore_index=True, sort=False)
    selection = _read_csv(SELECTION_AUDIT_PATH)
    selection_compare = _selection_comparison(selection)
    decision = _decision(summary, cost, rolling, satellite_summary, product_harvest)

    _plot(comparison_daily, comparison_satellite, summary, cost, rolling, selection_compare, product_harvest, decision)
    _write_report(summary, cost, rolling, window, satellite_summary, selection, selection_compare, product_harvest, decision)

    combo_daily.to_csv(COMBINED_DAILY_PATH, index=False, encoding="utf-8-sig")
    satellite_daily.to_csv(SATELLITE_DAILY_PATH, index=False, encoding="utf-8-sig")
    positions.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    satellite_margin_daily.to_csv(SATELLITE_MARGIN_PATH, index=False, encoding="utf-8-sig")
    product_harvest.to_csv(SATELLITE_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    satellite_summary.to_csv(SATELLITE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    window.to_csv(WINDOW_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
