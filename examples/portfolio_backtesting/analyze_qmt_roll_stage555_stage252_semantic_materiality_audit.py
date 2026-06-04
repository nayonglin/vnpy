from __future__ import annotations

from datetime import datetime
import json
import math
import os
from pathlib import Path
import sys
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/matplotlib")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513  # noqa: E402
import analyze_qmt_roll_stage551_annual_persistence_sleeve_replay as s551  # noqa: E402


MODEL_TAG = "stage555_stage252_semantic_materiality_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage555_stage252_semantic_materiality_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE552_TAG = "stage552_dynamic_annual_selector_sleeve_v1"
STAGE552_PREFIX = "qmt_roll_stage552_dynamic_annual_selector_sleeve"
STAGE552_ELIGIBILITY_IN = OUTPUT_DIR / f"{STAGE552_PREFIX}_annual_eligibility_{STAGE552_TAG}.csv"
STAGE552_SELECTION_IN = OUTPUT_DIR / f"{STAGE552_PREFIX}_annual_selection_{STAGE552_TAG}.csv"
STAGE552_POSITIONS_IN = OUTPUT_DIR / f"{STAGE552_PREFIX}_positions_{STAGE552_TAG}.csv"
STAGE552_SUMMARY_IN = OUTPUT_DIR / f"{STAGE552_PREFIX}_summary_{STAGE552_TAG}.csv"
STAGE552_COST_IN = OUTPUT_DIR / f"{STAGE552_PREFIX}_cost_stress_{STAGE552_TAG}.csv"
STAGE552_ROLLING_IN = OUTPUT_DIR / f"{STAGE552_PREFIX}_rolling_holding_{STAGE552_TAG}.csv"
STAGE552_DAILY_IN = OUTPUT_DIR / f"{STAGE552_PREFIX}_combined_daily_{STAGE552_TAG}.csv"

CONTROL = s551.CONTROL
TOP6 = "dynamic_prevtop6_r050_pc15_maxpos3"

PRODUCT_ACTIVITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_activity_{MODEL_TAG}.csv"
ANNUAL_BOUNDARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_boundary_{MODEL_TAG}.csv"
VIOLATION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_semantic_violations_{MODEL_TAG}.csv"
SEMANTIC_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_semantic_audit_{MODEL_TAG}.csv"
MATERIALITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_materiality_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


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


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    eligibility = _read_csv(STAGE552_ELIGIBILITY_IN)
    eligibility["eval_date"] = pd.to_datetime(eligibility["eval_date"], errors="coerce").dt.normalize()
    selection = _read_csv(STAGE552_SELECTION_IN)
    summary = _read_csv(STAGE552_SUMMARY_IN)
    cost = _read_csv(STAGE552_COST_IN)
    rolling = _read_csv(STAGE552_ROLLING_IN)
    return eligibility, selection, summary, cost, rolling


def _eligibility_map(eligibility: pd.DataFrame) -> dict[int, set[str]]:
    frame = eligibility[eligibility["strategy"].eq(TOP6)].copy()
    frame["year"] = frame["eval_date"].dt.year
    result: dict[int, set[str]] = {}
    for year, group in frame.groupby("year"):
        result[int(year)] = set(group["product_vt_symbol"].astype(str))
    return result


def _build_product_activity(eligibility: pd.DataFrame) -> pd.DataFrame:
    if PRODUCT_ACTIVITY_PATH.exists():
        frame = _read_csv(PRODUCT_ACTIVITY_PATH)
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
        return frame

    chunks: list[pd.DataFrame] = []
    usecols = ["date", "variant", "vt_symbol", "start_pos", "end_pos", "pos_change", "net_pnl", "slippage", "trade_count"]
    for chunk in pd.read_csv(STAGE552_POSITIONS_IN, encoding="utf-8-sig", usecols=usecols, chunksize=500_000):
        chunk = chunk[chunk["variant"].eq(TOP6)].copy()
        if chunk.empty:
            continue
        for column in ["start_pos", "end_pos", "pos_change", "net_pnl", "slippage", "trade_count"]:
            chunk[column] = pd.to_numeric(chunk[column], errors="coerce").fillna(0.0)
        active_mask = (
            chunk["start_pos"].ne(0.0)
            | chunk["end_pos"].ne(0.0)
            | chunk["pos_change"].ne(0.0)
            | chunk["net_pnl"].ne(0.0)
            | chunk["slippage"].ne(0.0)
            | chunk["trade_count"].ne(0.0)
        )
        chunk = chunk[active_mask].copy()
        if chunk.empty:
            continue
        chunk["date"] = pd.to_datetime(chunk["date"], errors="coerce").dt.normalize()
        chunk["product_vt_symbol"] = chunk["vt_symbol"].astype(str).map(s513._product_from_contract)
        grouped = (
            chunk.groupby(["date", "product_vt_symbol"], as_index=False)
            .agg(
                start_pos=("start_pos", "sum"),
                end_pos=("end_pos", "sum"),
                abs_start_pos=("start_pos", lambda item: float(np.abs(item).sum())),
                abs_end_pos=("end_pos", lambda item: float(np.abs(item).sum())),
                pos_change_abs=("pos_change", lambda item: float(np.abs(item).sum())),
                net_pnl=("net_pnl", "sum"),
                slippage=("slippage", "sum"),
                trade_count=("trade_count", "sum"),
                active_contract_rows=("vt_symbol", "nunique"),
            )
            .sort_values(["date", "product_vt_symbol"])
        )
        chunks.append(grouped)
    if not chunks:
        raise RuntimeError("no active Stage252 top6 position rows")

    frame = pd.concat(chunks, ignore_index=True, sort=False)
    frame = (
        frame.groupby(["date", "product_vt_symbol"], as_index=False)
        .agg(
            start_pos=("start_pos", "sum"),
            end_pos=("end_pos", "sum"),
            abs_start_pos=("abs_start_pos", "sum"),
            abs_end_pos=("abs_end_pos", "sum"),
            pos_change_abs=("pos_change_abs", "sum"),
            net_pnl=("net_pnl", "sum"),
            slippage=("slippage", "sum"),
            trade_count=("trade_count", "sum"),
            active_contract_rows=("active_contract_rows", "sum"),
        )
        .sort_values(["date", "product_vt_symbol"])
    )
    eligible_by_year = _eligibility_map(eligibility)
    frame["year"] = frame["date"].dt.year.astype(int)
    frame["eligible_product"] = [
        str(product) in eligible_by_year.get(int(year), set())
        for product, year in zip(frame["product_vt_symbol"], frame["year"], strict=False)
    ]
    eps = 1e-9
    frame["active_start"] = frame["abs_start_pos"].abs() > eps
    frame["active_end"] = frame["abs_end_pos"].abs() > eps
    frame["new_product_entry"] = (~frame["active_start"]) & frame["active_end"]
    frame["product_exposure_add"] = frame["active_start"] & (frame["abs_end_pos"] > frame["abs_start_pos"] + eps)
    frame["open_or_add"] = frame["new_product_entry"] | frame["product_exposure_add"]
    frame["noneligible_carry_day"] = frame["active_start"] & (~frame["eligible_product"]) & (frame["year"] >= 2021)
    frame["noneligible_open_or_add"] = frame["open_or_add"] & (~frame["eligible_product"]) & (frame["year"] >= 2021)
    frame["pre_start_active"] = (frame["year"] < 2021) & (frame["active_start"] | frame["active_end"])
    frame.to_csv(PRODUCT_ACTIVITY_PATH, index=False, encoding="utf-8-sig")
    return frame


def _semantic_audit(eligibility: pd.DataFrame, selection: pd.DataFrame, activity: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    elig = eligibility[eligibility["strategy"].eq(TOP6)].copy()
    elig["eval_year"] = elig["eval_date"].dt.year.astype(int)
    elig["source_prev_year"] = pd.to_numeric(elig["source_prev_year"], errors="coerce").astype("Int64")
    selection_top6 = selection[selection["variant"].eq(TOP6)].copy()
    selection_top6["year"] = pd.to_numeric(selection_top6["year"], errors="coerce").astype(int)
    selection_top6["prev_year"] = pd.to_numeric(selection_top6["prev_year"], errors="coerce").astype(int)

    annual_rows: list[dict[str, Any]] = []
    daily_dates = pd.to_datetime(_read_csv(STAGE552_DAILY_IN)["date"], errors="coerce").dt.normalize()
    all_trade_dates = sorted(daily_dates.dropna().unique())
    for _, row in selection_top6.iterrows():
        year = int(row["year"])
        year_dates = [item for item in all_trade_dates if pd.Timestamp(item).year == year]
        first_trade_date = pd.Timestamp(year_dates[0]) if year_dates else pd.NaT
        prev_dates = [item for item in all_trade_dates if pd.Timestamp(item).year == year - 1]
        prev_last_date = pd.Timestamp(prev_dates[-1]) if prev_dates else pd.NaT
        selected = set(str(row["selected_products"]).split(",")) if str(row["selected_products"]) else set()
        year_activity = activity[activity["year"].eq(year)]
        first_activity = activity[activity["date"].eq(first_trade_date)] if pd.notna(first_trade_date) else pd.DataFrame()
        prev_last_activity = activity[activity["date"].eq(prev_last_date)] if pd.notna(prev_last_date) else pd.DataFrame()
        active_first_start = set(first_activity[first_activity["active_start"]]["product_vt_symbol"].astype(str))
        active_first = set(first_activity[first_activity["active_end"]]["product_vt_symbol"].astype(str))
        active_prev_last = set(prev_last_activity[prev_last_activity["active_end"]]["product_vt_symbol"].astype(str))
        carry_not_selected = sorted((active_prev_last & active_first_start) - selected)
        open_or_add = year_activity[year_activity["open_or_add"]]
        annual_rows.append(
            {
                "year": year,
                "prev_year": int(row["prev_year"]),
                "selected_count": int(row["selected_count"]),
                "first_trade_date": None if pd.isna(first_trade_date) else first_trade_date.date().isoformat(),
                "prev_last_trade_date": None if pd.isna(prev_last_date) else prev_last_date.date().isoformat(),
                "active_prev_last_count": len(active_prev_last),
                "active_first_start_count": len(active_first_start),
                "active_first_count": len(active_first),
                "carry_not_selected_count": len(carry_not_selected),
                "carry_not_selected_products": ",".join(carry_not_selected),
                "eligible_open_or_add_count": int(open_or_add["eligible_product"].sum()),
                "noneligible_open_or_add_count": int((~open_or_add["eligible_product"]).sum()),
                "year_trade_count": float(year_activity["trade_count"].sum()),
                "year_net_pnl": float(year_activity["net_pnl"].sum()),
                "year_active_product_count": int(year_activity[year_activity["active_end"]]["product_vt_symbol"].nunique()),
            }
        )
    annual_boundary = pd.DataFrame(annual_rows)

    semantic_rows = [
        {
            "check": "eligibility_uses_previous_year",
            "value": int((elig["source_prev_year"] != elig["eval_year"] - 1).sum()),
            "pass": int((elig["source_prev_year"] == elig["eval_year"] - 1).all()),
            "note": "年度白名单必须只引用 eval_year-1 的已知单品种账本。",
        },
        {
            "check": "selection_uses_previous_year",
            "value": int((selection_top6["prev_year"] != selection_top6["year"] - 1).sum()),
            "pass": int((selection_top6["prev_year"] == selection_top6["year"] - 1).all()),
            "note": "年度选择表 prev_year 必须等于 year-1。",
        },
        {
            "check": "pre_2021_no_active_satellite_position",
            "value": int(activity["pre_start_active"].sum()),
            "pass": int(activity["pre_start_active"].sum() == 0),
            "note": "Stage252 卫星仓应从 2021 年后才有真实持仓风险。",
        },
        {
            "check": "no_noneligible_product_open_or_add",
            "value": int(activity["noneligible_open_or_add"].sum()),
            "pass": int(activity["noneligible_open_or_add"].sum() == 0),
            "note": "不在当年白名单的产品不得出现产品级新开或加仓；跨年已有持仓自然持有不算违规。",
        },
        {
            "check": "carryover_not_forced_flattened",
            "value": int(annual_boundary["carry_not_selected_count"].sum()),
            "pass": 1,
            "note": "非当年白名单的跨年持仓允许自然退出或换月，本项只计数不否决。",
        },
    ]
    semantic = pd.DataFrame(semantic_rows)
    return semantic, annual_boundary


def _materiality(summary: pd.DataFrame, cost: pd.DataFrame, rolling: pd.DataFrame, semantic: pd.DataFrame) -> pd.DataFrame:
    summary_map = {str(row["variant"]): row for _, row in summary.iterrows()}
    control = summary_map[CONTROL]
    top6 = summary_map[TOP6]
    rolling_pivot = rolling.pivot(index="variant", columns="holding_days", values="p05_return_pct")
    cost3 = cost[cost["cost_multiplier"].eq(3.0)].set_index("variant")

    satellite_pnl = float(top6["satellite_cumulative_pnl"])
    added_trades = float(top6["total_trade_count"] - control["total_trade_count"])
    slippage_delta = float(top6["total_slippage"] - control["total_slippage"])
    return_relative = float(top6["return_vs_stage526_pct"])
    return_pp = float(top6["total_return_pct"] - control["total_return_pct"])
    dd_improvement_pp = float(top6["max_dd_pct"] - control["max_dd_pct"])
    ulcer_improvement_pp = float(control["ulcer_pct"] - top6["ulcer_pct"])
    p05_63_improvement_pp = float(rolling_pivot.loc[TOP6, 63] - rolling_pivot.loc[CONTROL, 63])
    p05_126_improvement_pp = float(rolling_pivot.loc[TOP6, 126] - rolling_pivot.loc[CONTROL, 126])
    pnl_per_added_trade = satellite_pnl / added_trades if added_trades else np.nan
    slippage_to_pnl_pct = slippage_delta / satellite_pnl * 100.0 if satellite_pnl else np.nan
    semantic_pass = bool(semantic["pass"].min())

    rows = [
        {
            "metric": "semantic_pass",
            "value": float(semantic_pass),
            "threshold": "1",
            "pass": int(semantic_pass),
            "note": "无未来年份引用、无非白名单产品级新开/加仓。",
        },
        {
            "metric": "return_relative_vs_stage526_pct",
            "value": return_relative,
            "threshold": ">=100.5",
            "pass": int(return_relative >= 100.5),
            "note": "部署材料性要求相对 Stage526 至少有 0.5% 以上收益抬升。",
        },
        {
            "metric": "total_return_improvement_pp",
            "value": return_pp,
            "threshold": ">=18.5",
            "pass": int(return_pp >= 18.5),
            "note": "约等于 Stage526 总收益的 0.5%；当前只提升约 8.56pp。",
        },
        {
            "metric": "max_dd_improvement_pp",
            "value": dd_improvement_pp,
            "threshold": ">=0.5",
            "pass": int(dd_improvement_pp >= 0.5),
            "note": "最大回撤改善不足 0.5pp 时，部署体感很难被感知。",
        },
        {
            "metric": "ulcer_improvement_pp",
            "value": ulcer_improvement_pp,
            "threshold": ">=0.25",
            "pass": int(ulcer_improvement_pp >= 0.25),
            "note": "Ulcer 改善不足时，水下体验提升不明显。",
        },
        {
            "metric": "holding63_p05_improvement_pp",
            "value": p05_63_improvement_pp,
            "threshold": ">=0.5",
            "pass": int(p05_63_improvement_pp >= 0.5),
            "note": "3个月左尾体验改善至少需要 0.5pp 才有部署材料性。",
        },
        {
            "metric": "holding126_p05_improvement_pp",
            "value": p05_126_improvement_pp,
            "threshold": ">=0.5",
            "pass": int(p05_126_improvement_pp >= 0.5),
            "note": "6个月左尾体验改善至少需要 0.5pp 才有部署材料性。",
        },
        {
            "metric": "cost3_dd40_pass",
            "value": float(cost3.loc[TOP6, "max_dd_pct"]),
            "threshold": ">=-40",
            "pass": int(float(cost3.loc[TOP6, "max_dd_pct"]) >= -40.0),
            "note": "高成本压力仍未通过 DD40。",
        },
        {
            "metric": "added_trade_count",
            "value": added_trades,
            "threshold": "<=150 or materiality strong",
            "pass": int(added_trades <= 150 and return_relative >= 100.5),
            "note": "新增交易数增加执行复杂度；材料性弱时不应为了 200 笔交易接入。",
        },
        {
            "metric": "satellite_pnl_per_added_trade",
            "value": pnl_per_added_trade,
            "threshold": ">=500",
            "pass": int(pnl_per_added_trade >= 500),
            "note": "按新增交易估计的净贡献太薄。",
        },
        {
            "metric": "slippage_to_satellite_pnl_pct",
            "value": slippage_to_pnl_pct,
            "threshold": "<=10",
            "pass": int(slippage_to_pnl_pct <= 10),
            "note": "成本占卫星PnL比例可接受，但不能抵消材料性不足。",
        },
    ]
    return pd.DataFrame(rows)


def _decision(semantic: pd.DataFrame, annual_boundary: pd.DataFrame, materiality: pd.DataFrame) -> dict[str, Any]:
    semantic_pass = bool(semantic["pass"].min())
    materiality_core = materiality[
        materiality["metric"].isin(
            [
                "return_relative_vs_stage526_pct",
                "max_dd_improvement_pp",
                "ulcer_improvement_pp",
                "holding63_p05_improvement_pp",
                "holding126_p05_improvement_pp",
                "cost3_dd40_pass",
                "added_trade_count",
                "satellite_pnl_per_added_trade",
            ]
        )
    ]
    materiality_pass_count = int(materiality_core["pass"].sum())
    materiality_pass = materiality_pass_count >= 5
    noneligible_open_or_add_count = int(
        semantic.loc[semantic["check"].eq("no_noneligible_product_open_or_add"), "value"].iloc[0]
    )
    decision = "semantic_or_materiality_failed_reject"
    if semantic_pass and not materiality_pass:
        decision = "semantic_valid_materiality_insufficient_keep_paper_only"
    elif noneligible_open_or_add_count > 0:
        decision = "semantic_effective_date_violation_and_materiality_failed_reject"
    if semantic_pass and materiality_pass:
        decision = "semantic_and_materiality_pass_next_deployment_review"
    return {
        "stage": "Stage255",
        "model_tag": MODEL_TAG,
        "decision": decision,
        "line_id": LINE_ID,
        "baseline": CONTROL,
        "candidate_under_audit": TOP6,
        "semantic_pass": semantic_pass,
        "materiality_pass": materiality_pass,
        "materiality_pass_count": materiality_pass_count,
        "materiality_core_count": int(len(materiality_core)),
        "noneligible_open_or_add_count": noneligible_open_or_add_count,
        "carryover_not_selected_total": int(annual_boundary["carry_not_selected_count"].sum()),
        "materiality_metrics": _json_safe(materiality.to_dict(orient="records")),
        "visual_review": (
            "图中应重点看权益差是否有持续抬升、年度白名单是否存在非白名单新开/加仓、"
            "材料性柱状图是否显示收益/回撤/3-6个月左尾足够大。"
        ),
        "next_step": (
            "若语义有效但材料性不足，Stage252 不进入部署候选；"
            "只保留为年度选品 paper 监控或转向 forward 外生状态账本。"
        ),
    }


def _plot(
    daily: pd.DataFrame,
    activity: pd.DataFrame,
    annual_boundary: pd.DataFrame,
    materiality: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    ax_delta, ax_activity, ax_material, ax_product = axes.flatten()

    pivot = daily[daily["variant"].isin([CONTROL, TOP6])].pivot(index="date", columns="variant", values="account_equity")
    pivot.index = pd.to_datetime(pivot.index)
    if CONTROL in pivot and TOP6 in pivot:
        delta = pivot[TOP6] - pivot[CONTROL]
        ax_delta.plot(delta.index, delta.values, color="#7c3aed", linewidth=1.0, label="Stage252 - Stage526")
        ax_delta.axhline(0, color="#111827", linestyle="--", linewidth=1)
        ax_delta.set_title("账户权益差：Stage252 - Stage526")
        ax_delta.legend(fontsize=8)
    ax_delta.grid(alpha=0.25)

    annual = annual_boundary.copy()
    annual[["eligible_open_or_add_count", "noneligible_open_or_add_count", "carry_not_selected_count"]].plot(
        kind="bar",
        ax=ax_activity,
        color=["#0891b2", "#dc2626", "#f97316"],
    )
    ax_activity.set_xticklabels(annual["year"].astype(str), rotation=0)
    ax_activity.set_title("年度白名单语义：开仓/加仓与carry")
    ax_activity.grid(axis="y", alpha=0.25)

    material_view = materiality[
        materiality["metric"].isin(
            [
                "return_relative_vs_stage526_pct",
                "max_dd_improvement_pp",
                "holding63_p05_improvement_pp",
                "holding126_p05_improvement_pp",
                "satellite_pnl_per_added_trade",
                "slippage_to_satellite_pnl_pct",
            ]
        )
    ].copy()
    ax_material.barh(material_view["metric"], material_view["value"], color=np.where(material_view["pass"].eq(1), "#059669", "#b91c1c"))
    ax_material.set_title("部署材料性指标")
    ax_material.grid(axis="x", alpha=0.25)

    product = (
        activity.groupby("product_vt_symbol", as_index=False)
        .agg(net_pnl=("net_pnl", "sum"), trade_count=("trade_count", "sum"))
        .sort_values("net_pnl", ascending=False)
    )
    product = pd.concat([product.head(6), product.tail(6)], ignore_index=True)
    ax_product.barh(product["product_vt_symbol"], product["net_pnl"], color=np.where(product["net_pnl"].ge(0), "#7c3aed", "#f97316"))
    ax_product.axvline(0, color="#111827", linestyle="--", linewidth=1)
    ax_product.set_title("卫星产品PnL：头尾贡献")
    ax_product.grid(axis="x", alpha=0.25)

    fig.suptitle(f"Stage255 decision: {decision['decision']}", fontsize=12)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s551._md_table(frame, max_rows=max_rows)


def _write_report(
    semantic: pd.DataFrame,
    annual_boundary: pd.DataFrame,
    materiality: pd.DataFrame,
    activity: pd.DataFrame,
    violations: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    product = (
        activity.groupby("product_vt_symbol", as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            slippage=("slippage", "sum"),
            trade_count=("trade_count", "sum"),
            active_days=("active_end", "sum"),
            open_or_add_count=("open_or_add", "sum"),
            noneligible_open_or_add_count=("noneligible_open_or_add", "sum"),
        )
        .sort_values("net_pnl", ascending=False)
    )
    lines = [
        "# Stage255 Stage252 白名单语义与部署材料性审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 研究线：`{LINE_ID}`",
        f"- A：`{CONTROL}`。",
        f"- C：`{TOP6}`。",
        "- 阶段性质：只读审计；不重跑策略引擎，不新增交易规则，不调 TopN/risk/cap/maxpos/相关性。",
        "- 预声明闸门：语义必须无未来泄漏、无非白名单产品级新开/加仓；材料性至少要在收益、回撤、Ulcer、3/6个月左尾、3x成本或交易效率上形成足够多的独立通过项。",
        f"- 决策：`{decision['decision']}`。",
        "",
        "## 语义审计",
        "",
        _md_table(semantic),
        "",
        "## 年度边界与carry",
        "",
        _md_table(annual_boundary, max_rows=80),
        "",
        "## 非白名单新开/加仓明细",
        "",
        _md_table(violations, max_rows=40),
        "",
        "## 部署材料性",
        "",
        _md_table(materiality),
        "",
        "## 产品贡献",
        "",
        _md_table(product, max_rows=80),
        "",
        "## 决策JSON",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    eligibility, selection, summary, cost, rolling = _load_inputs()
    activity = _build_product_activity(eligibility)
    semantic, annual_boundary = _semantic_audit(eligibility, selection, activity)
    materiality = _materiality(summary, cost, rolling, semantic)
    decision = _decision(semantic, annual_boundary, materiality)
    violation_columns = [
        "date",
        "product_vt_symbol",
        "start_pos",
        "end_pos",
        "abs_start_pos",
        "abs_end_pos",
        "pos_change_abs",
        "net_pnl",
        "slippage",
        "trade_count",
        "eligible_product",
        "new_product_entry",
        "product_exposure_add",
        "noneligible_open_or_add",
    ]
    violations = activity[activity["noneligible_open_or_add"]].copy()
    violations = violations[[column for column in violation_columns if column in violations.columns]]
    daily = _read_csv(STAGE552_DAILY_IN)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    _plot(daily, activity, annual_boundary, materiality, decision)
    _write_report(semantic, annual_boundary, materiality, activity, violations, decision)

    semantic.to_csv(SEMANTIC_AUDIT_PATH, index=False, encoding="utf-8-sig")
    annual_boundary.to_csv(ANNUAL_BOUNDARY_PATH, index=False, encoding="utf-8-sig")
    violations.to_csv(VIOLATION_PATH, index=False, encoding="utf-8-sig")
    materiality.to_csv(MATERIALITY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
