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
import analyze_qmt_roll_stage516_margin_aware_sizing_frontier as s516  # noqa: E402
import analyze_qmt_roll_stage551_annual_persistence_sleeve_replay as s551  # noqa: E402


MODEL_TAG = "stage554_stage252_leaveout_fragility_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage554_stage252_leaveout_fragility_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE552_TAG = "stage552_dynamic_annual_selector_sleeve_v1"
STAGE552_PREFIX = "qmt_roll_stage552_dynamic_annual_selector_sleeve"
STAGE552_COMBINED_DAILY_IN = OUTPUT_DIR / f"{STAGE552_PREFIX}_combined_daily_{STAGE552_TAG}.csv"
STAGE552_POSITIONS_IN = OUTPUT_DIR / f"{STAGE552_PREFIX}_positions_{STAGE552_TAG}.csv"

CONTROL = s551.CONTROL
TOP6 = "dynamic_prevtop6_r050_pc15_maxpos3"
ACCOUNT_CAPITAL = s551.ACCOUNT_CAPITAL
BROKER_MARGIN_MULTIPLIER = s551.BROKER_MARGIN_MULTIPLIER

PRODUCT_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_product_daily_{MODEL_TAG}.csv"
ANNUAL_CONTRIB_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_contribution_{MODEL_TAG}.csv"
PRODUCT_CONTRIB_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_contribution_{MODEL_TAG}.csv"
LEAVEOUT_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_leaveout_daily_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_holding_{MODEL_TAG}.csv"
WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_metrics_{MODEL_TAG}.csv"
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


def _load_stage252_daily() -> pd.DataFrame:
    frame = _read_csv(STAGE552_COMBINED_DAILY_IN)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[frame["variant"].isin([CONTROL, TOP6])].copy()
    for column in [
        "total_net_pnl",
        "total_slippage",
        "trade_count",
        "account_equity",
        "total_margin_exact",
        "broker10_total_margin_exact",
        "core_total_net_pnl",
        "core_total_slippage",
        "core_total_margin_exact",
        "satellite_net_pnl",
        "satellite_slippage",
        "satellite_trade_count",
        "satellite_margin_exact",
    ]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    return frame.sort_values(["variant", "date"])


def _build_product_daily() -> pd.DataFrame:
    if PRODUCT_DAILY_PATH.exists():
        frame = _read_csv(PRODUCT_DAILY_PATH)
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
        return frame

    metadata = s551._metadata_for_full_universe()
    size_map = metadata["sizes"]
    margin_map = metadata["margin_ratios"]
    chunks: list[pd.DataFrame] = []
    usecols = ["date", "variant", "vt_symbol", "end_pos", "close_price", "net_pnl", "slippage", "trade_count"]
    for chunk in pd.read_csv(STAGE552_POSITIONS_IN, encoding="utf-8-sig", usecols=usecols, chunksize=500_000):
        chunk = chunk[chunk["variant"].eq(TOP6)].copy()
        if chunk.empty:
            continue
        chunk["date"] = pd.to_datetime(chunk["date"], errors="coerce").dt.normalize()
        chunk["product_vt_symbol"] = chunk["vt_symbol"].astype(str).map(s513._product_from_contract)
        for column in ["end_pos", "close_price", "net_pnl", "slippage", "trade_count"]:
            chunk[column] = pd.to_numeric(chunk[column], errors="coerce").fillna(0.0)
        chunk["size"] = chunk["vt_symbol"].map(size_map).fillna(1.0).astype(float)
        chunk["margin_ratio"] = chunk["vt_symbol"].map(margin_map).fillna(0.15).astype(float)
        chunk["c3_margin_exact"] = (
            chunk["end_pos"].abs() * chunk["close_price"].clip(lower=0.0) * chunk["size"] * chunk["margin_ratio"]
        )
        grouped = (
            chunk.groupby(["date", "product_vt_symbol"], as_index=False)
            .agg(
                satellite_product_net_pnl=("net_pnl", "sum"),
                satellite_product_slippage=("slippage", "sum"),
                satellite_product_trade_count=("trade_count", "sum"),
                satellite_product_margin_exact=("c3_margin_exact", "sum"),
            )
            .sort_values(["date", "product_vt_symbol"])
        )
        chunks.append(grouped)
    if not chunks:
        raise RuntimeError("no Stage252 top6 position rows")
    frame = pd.concat(chunks, ignore_index=True, sort=False)
    frame = (
        frame.groupby(["date", "product_vt_symbol"], as_index=False)
        .agg(
            satellite_product_net_pnl=("satellite_product_net_pnl", "sum"),
            satellite_product_slippage=("satellite_product_slippage", "sum"),
            satellite_product_trade_count=("satellite_product_trade_count", "sum"),
            satellite_product_margin_exact=("satellite_product_margin_exact", "sum"),
        )
        .sort_values(["date", "product_vt_symbol"])
    )
    frame["year"] = frame["date"].dt.year
    frame["active_product"] = (frame["satellite_product_margin_exact"] > 0.0).astype(int)
    frame.to_csv(PRODUCT_DAILY_PATH, index=False, encoding="utf-8-sig")
    return frame


def _aggregate_contributions(product_daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    annual = (
        product_daily.groupby("year", as_index=False)
        .agg(
            satellite_net_pnl=("satellite_product_net_pnl", "sum"),
            satellite_slippage=("satellite_product_slippage", "sum"),
            satellite_trade_count=("satellite_product_trade_count", "sum"),
            max_satellite_margin=("satellite_product_margin_exact", "max"),
            active_products=("active_product", "sum"),
        )
        .sort_values("year")
    )
    product = (
        product_daily.groupby("product_vt_symbol", as_index=False)
        .agg(
            satellite_net_pnl=("satellite_product_net_pnl", "sum"),
            satellite_slippage=("satellite_product_slippage", "sum"),
            satellite_trade_count=("satellite_product_trade_count", "sum"),
            max_satellite_margin=("satellite_product_margin_exact", "max"),
            active_days=("active_product", "sum"),
        )
        .sort_values("satellite_net_pnl", ascending=False)
    )
    annual.to_csv(ANNUAL_CONTRIB_PATH, index=False, encoding="utf-8-sig")
    product.to_csv(PRODUCT_CONTRIB_PATH, index=False, encoding="utf-8-sig")
    return annual, product


def _remove_daily(product_daily: pd.DataFrame, *, years: set[int] | None = None, products: set[str] | None = None) -> pd.DataFrame:
    frame = product_daily.copy()
    mask = pd.Series(True, index=frame.index)
    if years is not None:
        mask &= frame["year"].astype(int).isin(years)
    if products is not None:
        mask &= frame["product_vt_symbol"].astype(str).isin(products)
    removed = (
        frame[mask]
        .groupby("date", as_index=False)
        .agg(
            removed_net_pnl=("satellite_product_net_pnl", "sum"),
            removed_slippage=("satellite_product_slippage", "sum"),
            removed_trade_count=("satellite_product_trade_count", "sum"),
            removed_margin_exact=("satellite_product_margin_exact", "sum"),
        )
    )
    return removed


def _make_ablation(base_top6: pd.DataFrame, removed: pd.DataFrame, *, variant: str, label: str, note: str) -> pd.DataFrame:
    frame = base_top6.copy().sort_values("date")
    frame = frame.merge(removed, on="date", how="left")
    for column in ["removed_net_pnl", "removed_slippage", "removed_trade_count", "removed_margin_exact"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    frame["satellite_net_pnl"] = pd.to_numeric(frame["satellite_net_pnl"], errors="coerce").fillna(0.0) - frame[
        "removed_net_pnl"
    ]
    frame["satellite_slippage"] = pd.to_numeric(frame["satellite_slippage"], errors="coerce").fillna(0.0) - frame[
        "removed_slippage"
    ]
    frame["satellite_trade_count"] = pd.to_numeric(frame["satellite_trade_count"], errors="coerce").fillna(0.0) - frame[
        "removed_trade_count"
    ]
    frame["satellite_margin_exact"] = (
        pd.to_numeric(frame["satellite_margin_exact"], errors="coerce").fillna(0.0) - frame["removed_margin_exact"]
    ).clip(lower=0.0)
    frame["total_net_pnl"] = pd.to_numeric(frame["core_total_net_pnl"], errors="coerce").fillna(0.0) + frame[
        "satellite_net_pnl"
    ]
    frame["total_slippage"] = pd.to_numeric(frame["core_total_slippage"], errors="coerce").fillna(0.0) + frame[
        "satellite_slippage"
    ]
    frame["trade_count"] = pd.to_numeric(frame["trade_count"], errors="coerce").fillna(0.0) - frame["removed_trade_count"]
    frame["account_equity"] = ACCOUNT_CAPITAL + frame["total_net_pnl"].cumsum()
    frame["total_margin_exact"] = pd.to_numeric(frame["core_total_margin_exact"], errors="coerce").fillna(0.0) + frame[
        "satellite_margin_exact"
    ]
    frame["broker10_total_margin_exact"] = frame["total_margin_exact"] * BROKER_MARGIN_MULTIPLIER
    frame["broker10_margin_to_equity_pct"] = (
        frame["broker10_total_margin_exact"] / frame["account_equity"].replace(0.0, np.nan) * 100.0
    ).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    frame["variant"] = variant
    frame["combo_variant"] = variant
    frame["label"] = label
    frame["note"] = note
    return frame.drop(columns=["removed_net_pnl", "removed_slippage", "removed_trade_count", "removed_margin_exact"])


def _build_leaveouts(stage_daily: pd.DataFrame, product_daily: pd.DataFrame, annual: pd.DataFrame, product: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    control = stage_daily[stage_daily["variant"].eq(CONTROL)].copy()
    top6 = stage_daily[stage_daily["variant"].eq(TOP6)].copy()
    rows: list[pd.DataFrame] = [control, top6]
    specs: list[dict[str, Any]] = []

    positive_years = annual[annual["satellite_net_pnl"] > 0.0].sort_values("satellite_net_pnl", ascending=False)
    negative_years = annual[annual["satellite_net_pnl"] < 0.0].sort_values("satellite_net_pnl", ascending=True)
    positive_products = product[product["satellite_net_pnl"] > 0.0].sort_values("satellite_net_pnl", ascending=False)
    negative_products = product[product["satellite_net_pnl"] < 0.0].sort_values("satellite_net_pnl", ascending=True)

    for _, row in positive_years.head(3).iterrows():
        year = int(row["year"])
        specs.append({"kind": "remove_year", "value": str(year), "years": {year}, "products": None})
    if not negative_years.empty:
        year = int(negative_years.iloc[0]["year"])
        specs.append({"kind": "remove_worst_year", "value": str(year), "years": {year}, "products": None})
    for _, row in positive_products.head(5).iterrows():
        product_symbol = str(row["product_vt_symbol"])
        specs.append({"kind": "remove_product", "value": product_symbol, "years": None, "products": {product_symbol}})
    if not negative_products.empty:
        product_symbol = str(negative_products.iloc[0]["product_vt_symbol"])
        specs.append({"kind": "remove_worst_product", "value": product_symbol, "years": None, "products": {product_symbol}})
    if len(positive_products) >= 2:
        products = set(positive_products.head(2)["product_vt_symbol"].astype(str))
        specs.append({"kind": "remove_top2_products", "value": "+".join(sorted(products)), "years": None, "products": products})
    if len(positive_years) >= 2:
        years = set(positive_years.head(2)["year"].astype(int))
        specs.append({"kind": "remove_top2_years", "value": "+".join(str(item) for item in sorted(years)), "years": years, "products": None})

    seen: set[tuple[str, str]] = set()
    clean_specs: list[dict[str, Any]] = []
    for spec in specs:
        key = (spec["kind"], spec["value"])
        if key in seen:
            continue
        seen.add(key)
        clean_specs.append(spec)

    audit_rows: list[dict[str, Any]] = []
    for spec in clean_specs:
        variant = f"stage252_leaveout_{spec['kind']}_{spec['value'].replace('.', '').replace('+', '_')}"
        label = f"Stage252 top6 leaveout {spec['kind']} {spec['value']}"
        note = "只读反事实：从Stage252真实成交卫星PnL中剔除指定年份/产品贡献，不改变真实回测交易规则。"
        removed = _remove_daily(product_daily, years=spec["years"], products=spec["products"])
        ablated = _make_ablation(top6, removed, variant=variant, label=label, note=note)
        removed_total = float(pd.to_numeric(removed.get("removed_net_pnl", 0.0), errors="coerce").fillna(0.0).sum())
        audit_rows.append(
            {
                "variant": variant,
                "kind": spec["kind"],
                "value": spec["value"],
                "removed_satellite_net_pnl": removed_total,
                "removed_slippage": float(pd.to_numeric(removed.get("removed_slippage", 0.0), errors="coerce").fillna(0.0).sum()),
                "removed_trade_count": float(pd.to_numeric(removed.get("removed_trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
            }
        )
        rows.append(ablated)

    leaveout = pd.concat(rows, ignore_index=True, sort=False)
    return leaveout, audit_rows


def _decision(summary: pd.DataFrame, cost: pd.DataFrame, rolling: pd.DataFrame, audit: pd.DataFrame, annual: pd.DataFrame, product: pd.DataFrame) -> dict[str, Any]:
    summary_map = {str(row["variant"]): row for _, row in summary.iterrows()}
    control = summary_map[CONTROL]
    top6 = summary_map[TOP6]
    positive_years = annual[annual["satellite_net_pnl"] > 0.0].sort_values("satellite_net_pnl", ascending=False)
    positive_products = product[product["satellite_net_pnl"] > 0.0].sort_values("satellite_net_pnl", ascending=False)
    best_year = int(positive_years.iloc[0]["year"]) if not positive_years.empty else None
    best_product = str(positive_products.iloc[0]["product_vt_symbol"]) if not positive_products.empty else None
    best_year_variant = None
    best_product_variant = None
    for _, row in audit.iterrows():
        if row["kind"] == "remove_year" and str(row["value"]) == str(best_year):
            best_year_variant = str(row["variant"])
        if row["kind"] == "remove_product" and str(row["value"]) == str(best_product):
            best_product_variant = str(row["variant"])
    no_best_year = summary_map.get(best_year_variant)
    no_best_product = summary_map.get(best_product_variant)
    rolling_pivot = rolling.pivot(index="variant", columns="holding_days", values="p05_return_pct")
    fragile_year = no_best_year is not None and float(no_best_year["total_return_pct"]) <= float(control["total_return_pct"])
    fragile_product = no_best_product is not None and float(no_best_product["total_return_pct"]) <= float(control["total_return_pct"])
    cost3 = cost[cost["cost_multiplier"].eq(3.0)].set_index("variant")
    return {
        "stage": "Stage254",
        "model_tag": MODEL_TAG,
        "decision": "stage252_top6_fragile_keep_paper_not_promotion" if fragile_year or fragile_product else "stage252_top6_survives_leaveout_next_validation",
        "baseline": CONTROL,
        "candidate_under_audit": TOP6,
        "best_year": best_year,
        "best_product": best_product,
        "fragile_to_best_year": fragile_year,
        "fragile_to_best_product": fragile_product,
        "stage252_metrics": _json_safe(top6.to_dict()),
        "no_best_year_metrics": _json_safe({} if no_best_year is None else no_best_year.to_dict()),
        "no_best_product_metrics": _json_safe({} if no_best_product is None else no_best_product.to_dict()),
        "stage252_63d_p05": float(rolling_pivot.loc[TOP6, 63]),
        "stage252_126d_p05": float(rolling_pivot.loc[TOP6, 126]),
        "stage252_3x_dd": float(cost3.loc[TOP6, "max_dd_pct"]),
        "visual_review": (
            "需要人工查看图：若移除最佳年/最佳产品后曲线回到或低于Stage526，说明年度top6的paper edge不具备部署材料性；"
            "若只移除最差年/最差产品才显著改善，则该结果是 hindsight 归因，不能交易。"
        ),
        "next_step": (
            "若判定 fragile，Stage252 top6 不再做晋级准备，只保留为paper经验；"
            "若仍存活，才允许白名单生效时点和持仓连续性复核。"
        ),
    }


def _plot(daily: pd.DataFrame, summary: pd.DataFrame, rolling: pd.DataFrame, annual: pd.DataFrame, product: pd.DataFrame, decision: dict[str, Any]) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(3, 2, figsize=(17, 13))
    ax_equity, ax_dd, ax_sat, ax_scatter, ax_annual, ax_hold = axes.flatten()

    focus = [CONTROL, TOP6]
    best_year = decision.get("best_year")
    best_product = decision.get("best_product")
    if best_year is not None:
        match = summary[summary["variant"].str.contains(f"remove_year_{best_year}", regex=False)]
        if not match.empty:
            focus.append(str(match.iloc[0]["variant"]))
    if best_product:
        match = summary[summary["variant"].str.contains(f"remove_product_{str(best_product).replace('.', '')}", regex=False)]
        if not match.empty:
            focus.append(str(match.iloc[0]["variant"]))
    focus = list(dict.fromkeys(focus))
    color_map = {CONTROL: "#111827", TOP6: "#7c3aed"}
    for variant in focus:
        frame = daily[daily["variant"].eq(variant)].sort_values("date")
        if frame.empty:
            continue
        ax_equity.plot(frame["date"], frame["account_equity"], label=variant, linewidth=0.9, color=color_map.get(variant))
        equity = pd.Series(frame["account_equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
        dd = s551._drawdown_pct(equity)
        ax_dd.plot(dd.index, dd.values, label=variant, linewidth=0.8, color=color_map.get(variant))
        if variant != CONTROL:
            ax_sat.plot(frame["date"], frame["satellite_net_pnl"].cumsum(), label=variant, linewidth=0.9, color=color_map.get(variant))
    ax_equity.set_title("账户权益：Stage252与关键剔除反事实")
    ax_equity.grid(alpha=0.25)
    ax_equity.legend(fontsize=7)
    ax_dd.axhline(-40, color="#111827", linestyle="--", linewidth=1)
    ax_dd.set_title("账户回撤")
    ax_dd.grid(alpha=0.25)
    ax_sat.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_sat.set_title("卫星累计PnL：关键剔除")
    ax_sat.grid(alpha=0.25)
    ax_sat.legend(fontsize=7)

    view = summary[summary["variant"].ne(CONTROL)].copy()
    ax_scatter.scatter(view["max_dd_pct"], view["total_return_pct"], s=40, alpha=0.8)
    for _, row in view.iterrows():
        if row["variant"] in focus or row["variant"] == TOP6:
            ax_scatter.annotate(str(row["variant"]).replace("stage252_leaveout_", ""), (row["max_dd_pct"], row["total_return_pct"]), fontsize=6)
    ax_scatter.axvline(-40, color="#111827", linestyle="--", linewidth=1)
    ax_scatter.axhline(float(summary[summary["variant"].eq(CONTROL)]["total_return_pct"].iloc[0]), color="#9ca3af", linestyle="--", linewidth=1)
    ax_scatter.set_title("剔除反事实：收益 vs 回撤")
    ax_scatter.set_xlabel("max DD %")
    ax_scatter.set_ylabel("total return %")
    ax_scatter.grid(alpha=0.25)

    annual.plot(kind="bar", x="year", y="satellite_net_pnl", ax=ax_annual, color="#7c3aed", legend=False)
    ax_annual.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_annual.set_title("Stage252卫星年度贡献")
    ax_annual.grid(axis="y", alpha=0.25)

    h = rolling[rolling["holding_days"].isin([63, 126]) & rolling["variant"].isin(focus)].copy()
    pivot = h.pivot(index="variant", columns="holding_days", values="p05_return_pct").reindex(focus)
    pivot.plot(kind="barh", ax=ax_hold, color=["#f97316", "#0891b2"])
    ax_hold.axvline(0, color="#111827", linestyle="--", linewidth=1)
    ax_hold.set_title("关键版本任意启动3/6个月 p05收益")
    ax_hold.grid(axis="x", alpha=0.25)

    fig.suptitle(f"Stage254 decision: {decision['decision']}", fontsize=12)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s551._md_table(frame, max_rows=max_rows)


def _write_report(summary: pd.DataFrame, cost: pd.DataFrame, rolling: pd.DataFrame, window: pd.DataFrame, annual: pd.DataFrame, product: pd.DataFrame, audit: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage254 Stage252 年度top6 剔除脆弱性审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 研究线：`{LINE_ID}`",
        f"- A：`{CONTROL}`。",
        f"- C：`{TOP6}`。",
        "- 阶段性质：只读候选脆弱性审计；从 Stage252 真实成交后逐合约 positions 聚合产品/年份PnL，再做 leave-one 反事实。",
        "- 反过拟合边界：不改交易规则、不调年度选择、不把剔除负贡献产品当成可交易黑名单。",
        f"- 决策：`{decision['decision']}`。",
        "",
        "## 账户总览",
        "",
        _md_table(
            summary[
                [
                    "variant",
                    "total_return_pct",
                    "return_vs_stage526_pct",
                    "max_dd_pct",
                    "ulcer_pct",
                    "sharpe",
                    "satellite_cumulative_pnl",
                    "total_slippage",
                    "total_trade_count",
                    "nonzero_daily_win_rate_pct",
                ]
            ],
            max_rows=80,
        ),
        "",
        "## 成本压力",
        "",
        _md_table(cost[["variant", "cost_multiplier", "total_return_pct", "max_dd_pct", "ulcer_pct", "sharpe"]], max_rows=120),
        "",
        "## 任意启动3/6个月体验",
        "",
        _md_table(
            rolling[rolling["holding_days"].isin([63, 126])][
                ["variant", "holding_days", "p05_return_pct", "median_return_pct", "positive_rate_pct", "min_window_dd_pct"]
            ],
            max_rows=120,
        ),
        "",
        "## 年度贡献",
        "",
        _md_table(annual, max_rows=40),
        "",
        "## 产品贡献",
        "",
        _md_table(product, max_rows=80),
        "",
        "## 剔除审计清单",
        "",
        _md_table(audit, max_rows=80),
        "",
        "## 多窗口",
        "",
        _md_table(
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
            max_rows=120,
        ),
        "",
        "## 决策JSON",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    stage_daily = _load_stage252_daily()
    product_daily = _build_product_daily()
    annual, product = _aggregate_contributions(product_daily)
    leaveout_daily, audit_rows = _build_leaveouts(stage_daily, product_daily, annual, product)
    audit = pd.DataFrame(audit_rows)
    summary, cost = s551._summary_and_cost(leaveout_daily)
    rolling = s516._rolling_holding(leaveout_daily)
    window = s551._window_metrics(leaveout_daily)
    decision = _decision(summary, cost, rolling, audit, annual, product)
    _plot(leaveout_daily, summary, rolling, annual, product, decision)
    _write_report(summary, cost, rolling, window, annual, product, audit, decision)

    leaveout_daily.to_csv(LEAVEOUT_DAILY_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    window.to_csv(WINDOW_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
