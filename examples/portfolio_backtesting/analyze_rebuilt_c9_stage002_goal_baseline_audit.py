from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage002"
MODEL_TAG = "stage002_rebuilt_c9_goal_baseline_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage002_goal_baseline_audit"

CURVES_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_curves_"
    "stage167_c9_live_15w_multiperiod_ai_audit_v1.csv"
)
SUMMARY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_summary_"
    "stage167_c9_live_15w_multiperiod_ai_audit_v1.csv"
)
AI_POOL_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_"
    "stage182_ai_product_pool_live_inference_v1.csv"
)
AI_LATEST_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage182_ai_product_pool_live_inference_latest_pool_stage182_ai_product_pool_live_inference_v1.csv"
)
UNIVERSE_PATH = OUTPUT_DIR / "qmt_roll_full_market_tradable_universe_eligible_full_market_tradable_universe_v1.csv"
ENTRY_CANDIDATES_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_entry_candidates_"
    "stage167_c9_live_15w_multiperiod_ai_audit_v1.csv"
)

ANNUAL_RETURNS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_returns_{MODEL_TAG}.csv"
ANNUAL_STATS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_stats_{MODEL_TAG}.csv"
PRODUCT_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_audit_{MODEL_TAG}.csv"
REQUIREMENT_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_requirement_audit_{MODEL_TAG}.json"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_return_heatmap_{MODEL_TAG}.png"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

JD_PRODUCT = "jd.DCE"
BASELINE_RETURN_RETENTION = 0.80


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def _annual_returns(curves: pd.DataFrame) -> pd.DataFrame:
    data = curves.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data["account_equity"] = pd.to_numeric(data["account_equity"], errors="coerce")
    data = data.dropna(subset=["date", "account_equity"]).sort_values(["requested_start_month", "date"])
    data["year"] = data["date"].dt.year.astype(int)
    rows: list[dict[str, Any]] = []
    for (start_month, year), group in data.groupby(["requested_start_month", "year"], sort=True):
        group = group.sort_values("date")
        first = group.iloc[0]
        last = group.iloc[-1]
        start_equity = float(first["account_equity"])
        end_equity = float(last["account_equity"])
        annual_return_pct = (end_equity / start_equity - 1.0) * 100.0 if start_equity else np.nan
        rows.append(
            {
                "stage": STAGE,
                "line_id": LINE_ID,
                "model_tag": MODEL_TAG,
                "requested_start_month": str(start_month),
                "year": int(year),
                "year_start_date": pd.Timestamp(first["date"]).date().isoformat(),
                "year_end_date": pd.Timestamp(last["date"]).date().isoformat(),
                "year_trading_days": int(len(group)),
                "start_equity": start_equity,
                "end_equity": end_equity,
                "annual_return_pct": float(annual_return_pct),
                "positive_year": int(annual_return_pct > 0.0),
            }
        )
    return pd.DataFrame(rows).sort_values(["requested_start_month", "year"]).reset_index(drop=True)


def _annual_stats(annual: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for year, group in annual.groupby("year", sort=True):
        returns = pd.to_numeric(group["annual_return_pct"], errors="coerce")
        rows.append(
            {
                "year": int(year),
                "window_count": int(len(group)),
                "positive_count": int((returns > 0.0).sum()),
                "negative_count": int((returns <= 0.0).sum()),
                "min_return_pct": float(returns.min()),
                "median_return_pct": float(returns.median()),
                "max_return_pct": float(returns.max()),
                "worst_start_month": str(group.loc[returns.idxmin(), "requested_start_month"]),
            }
        )
    return pd.DataFrame(rows)


def _product_audit() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    ai = _read_csv(AI_POOL_PATH)
    universe = _read_csv(UNIVERSE_PATH)
    candidates = _read_csv(ENTRY_CANDIDATES_PATH)
    latest = _read_csv(AI_LATEST_PATH)

    ai_products = set(ai["product_vt_symbol"].astype(str))
    latest_products = set(latest["product_vt_symbol"].astype(str))
    universe_products = set(universe["product_vt_symbol"].astype(str))
    candidate_products = set(candidates["product_vt_symbol"].astype(str))

    jd_universe = universe[universe["product_vt_symbol"].astype(str).eq(JD_PRODUCT)].copy()
    jd_universe_record = jd_universe.iloc[0].to_dict() if not jd_universe.empty else {}
    rows.append(
        {
            "item": "jd_in_full_market_universe",
            "status": "PASS" if JD_PRODUCT in universe_products else "FAIL",
            "value": int(JD_PRODUCT in universe_products),
            "detail": json.dumps(_json_safe(jd_universe_record), ensure_ascii=False),
        }
    )
    rows.append(
        {
            "item": "jd_in_current_stage182_ai_pool",
            "status": "FAIL" if JD_PRODUCT not in ai_products else "PASS",
            "value": int(JD_PRODUCT in ai_products),
            "detail": "Current rebuilt Stage182 eligibility does not include jd.DCE.",
        }
    )
    rows.append(
        {
            "item": "jd_in_latest_stage182_pool",
            "status": "FAIL" if JD_PRODUCT not in latest_products else "PASS",
            "value": int(JD_PRODUCT in latest_products),
            "detail": "Latest monthly Stage182 pool membership.",
        }
    )
    rows.append(
        {
            "item": "jd_in_stage167_entry_candidates",
            "status": "FAIL" if JD_PRODUCT not in candidate_products else "PASS",
            "value": int((candidates["product_vt_symbol"].astype(str) == JD_PRODUCT).sum()),
            "detail": "Current Stage167 baseline produced no jd.DCE entry candidates because jd is not in the live pool.",
        }
    )
    rows.append(
        {
            "item": "current_ai_product_count",
            "status": "INFO",
            "value": int(len(ai_products)),
            "detail": ",".join(sorted(ai_products)),
        }
    )
    rows.append(
        {
            "item": "full_market_universe_product_count",
            "status": "INFO",
            "value": int(len(universe_products)),
            "detail": ",".join(sorted(universe_products)),
        }
    )
    return pd.DataFrame(rows)


def _plot_heatmap(annual: pd.DataFrame) -> None:
    pivot = annual.pivot(index="requested_start_month", columns="year", values="annual_return_pct").sort_index()
    fig, ax = plt.subplots(figsize=(16, 9), constrained_layout=True)
    values = pivot.to_numpy(dtype=float)
    finite = values[np.isfinite(values)]
    limit = max(10.0, min(200.0, float(np.nanpercentile(np.abs(finite), 90)) if finite.size else 10.0))
    image = ax.imshow(values, aspect="auto", cmap="RdYlGn", vmin=-limit, vmax=limit)
    ax.set_title("Stage167 Rebuilt C9/15w Annual Return By Cold Start")
    ax.set_xlabel("calendar year")
    ax.set_ylabel("cold start")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([str(item) for item in pivot.columns], rotation=45, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels([str(item) for item in pivot.index])
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            value = values[i, j]
            if not np.isfinite(value):
                continue
            ax.text(j, i, f"{value:.0f}", ha="center", va="center", fontsize=7, color="#111827")
    fig.colorbar(image, ax=ax, label="annual return %")
    fig.savefig(CHART_PATH, dpi=150)
    plt.close(fig)


def _requirement_audit(summary: pd.DataFrame, annual: pd.DataFrame, products: pd.DataFrame) -> dict[str, Any]:
    returns = pd.to_numeric(summary["total_return_pct"], errors="coerce")
    baseline_median_return = float(returns.median())
    baseline_retention_floor = baseline_median_return * BASELINE_RETURN_RETENTION
    negative_years = annual[pd.to_numeric(annual["annual_return_pct"], errors="coerce") <= 0.0].copy()
    jd_rows = products.set_index("item")
    audit = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "objective": (
            "Any cold start should have positive returns each year, full-cycle return retention >=80%, "
            "base product pool plus jd.DCE, optimized AI selection, identify ultra-high-quality signals, "
            "and increase risk allocation."
        ),
        "baseline": {
            "stage167_summary_path": str(SUMMARY_PATH),
            "sample_count": int(len(summary)),
            "median_total_return_pct": baseline_median_return,
            "return_retention_floor_pct": baseline_retention_floor,
            "min_total_return_pct": float(returns.min()),
            "max_total_return_pct": float(returns.max()),
        },
        "requirements": {
            "every_start_every_year_positive": {
                "status": "FAIL" if not negative_years.empty else "PASS",
                "negative_year_row_count": int(len(negative_years)),
                "worst_negative_return_pct": float(
                    pd.to_numeric(negative_years["annual_return_pct"], errors="coerce").min()
                )
                if not negative_years.empty
                else 0.0,
                "worst_rows": negative_years.sort_values("annual_return_pct").head(20).to_dict(orient="records"),
            },
            "full_cycle_return_retention_80pct": {
                "status": "BASELINE_ONLY",
                "note": "No candidate yet; future candidates must retain at least 80% of Stage167 baseline return by the declared metric.",
                "baseline_median_return_pct": baseline_median_return,
                "retention_floor_pct": baseline_retention_floor,
            },
            "base_pool_plus_jd": {
                "status": "DATA_READY_BUT_NOT_IN_BASELINE"
                if int(jd_rows.loc["jd_in_full_market_universe", "value"]) == 1
                and int(jd_rows.loc["jd_in_current_stage182_ai_pool", "value"]) == 0
                else "CHECK",
                "jd_in_full_market_universe": int(jd_rows.loc["jd_in_full_market_universe", "value"]),
                "jd_in_current_ai_pool": int(jd_rows.loc["jd_in_current_stage182_ai_pool", "value"]),
                "jd_in_stage167_candidates": int(jd_rows.loc["jd_in_stage167_entry_candidates", "value"]),
            },
            "ai_selection_optimization": {
                "status": "NOT_STARTED",
                "note": "Requires a new selector design and purged/multi-start validation. Existing Stage407 history warns that shared AI reranking with jd can destroy core right tail.",
            },
            "ultra_high_quality_signal_and_higher_risk": {
                "status": "NOT_STARTED",
                "note": "Must first define ex-ante high-quality signal labels and prove stability before increasing risk.",
            },
        },
        "decision": "stage002_goal_baseline_audit_not_ready_for_strategy_change",
        "overfit_reflection_before": "否。只读审计当前基准和数据可得性，不挑参数。",
        "overfit_reflection_after": "否。没有生成候选策略；结论是先做归因和选择器设计。",
        "continue_value_before": "是。目标很大，必须先固定差距和数据边界。",
        "continue_value_after": "是。当前已确认 jd 数据可用但未入基准，且年度正收益目标当前未满足。",
    }
    return audit


def _write_report(annual: pd.DataFrame, annual_stats: pd.DataFrame, products: pd.DataFrame, audit: dict[str, Any]) -> None:
    negative = annual[pd.to_numeric(annual["annual_return_pct"], errors="coerce") <= 0.0].copy()
    lines = [
        "# Stage002 重建版 C9/15w 目标基准审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 基准：Stage167 当前重建 C9/15w。",
        "- 本阶段只读，不重跑策略、不改 AI 池、不改实盘配置。",
        "",
        "## 目标拆解",
        "",
        "- 任意起点开始，每一年都能正收益。",
        "- 全周期收益保留 80% 以上。",
        "- 基础品种池加上鸡蛋 `jd.DCE`。",
        "- AI 选品进一步优化，能识别超高质量信号。",
        "- 对超高质量信号加大风险投入。",
        "",
        "## 当前基准缺口",
        "",
        f"- 年度负收益行数：`{audit['requirements']['every_start_every_year_positive']['negative_year_row_count']}`。",
        f"- 当前 Stage167 中位总收益：`{audit['baseline']['median_total_return_pct']:.4f}%`。",
        f"- 后续候选 80% 收益保留参考线：`{audit['baseline']['return_retention_floor_pct']:.4f}%`。",
        f"- 鸡蛋在 full-market universe：`{audit['requirements']['base_pool_plus_jd']['jd_in_full_market_universe']}`。",
        f"- 鸡蛋在当前 Stage182 AI 池：`{audit['requirements']['base_pool_plus_jd']['jd_in_current_ai_pool']}`。",
        f"- 鸡蛋在 Stage167 候选：`{audit['requirements']['base_pool_plus_jd']['jd_in_stage167_candidates']}`。",
        "",
        "## 年度统计",
        "",
        _md_table(annual_stats, max_rows=20),
        "",
        "## 年度负收益样本 Top20",
        "",
        _md_table(negative.sort_values("annual_return_pct").head(20), max_rows=20),
        "",
        "## 产品与 AI 池审计",
        "",
        _md_table(products, max_rows=20),
        "",
        "## 判断",
        "",
        "- 当前基准还没有满足“任意起点每年正收益”。",
        "- `jd.DCE` 数据可用，但没有进入当前 Stage182 AI 池，也没有进入 Stage167 候选。",
        "- 旧 Stage407/Stage418 经验显示，鸡蛋进入共享 AI 重排会破坏核心右尾；后续不能直接做共享 topN rerank 救参，应优先考虑非挤占式风险槽或账户级 selector。",
        "- 高质量信号加大风险必须先定义事前标签并验证稳定性，不能用最终盈亏或红框窗口倒推。",
        "",
        "## 输出文件",
        "",
        f"- annual_returns：`{ANNUAL_RETURNS_PATH}`",
        f"- annual_stats：`{ANNUAL_STATS_PATH}`",
        f"- product_audit：`{PRODUCT_AUDIT_PATH}`",
        f"- requirement_audit：`{REQUIREMENT_AUDIT_PATH}`",
        f"- chart：`{CHART_PATH}`",
        f"- report：`{REPORT_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curves = _read_csv(CURVES_PATH)
    summary = _read_csv(SUMMARY_PATH)
    annual = _annual_returns(curves)
    annual_stats = _annual_stats(annual)
    products = _product_audit()
    audit = _requirement_audit(summary, annual, products)

    annual.to_csv(ANNUAL_RETURNS_PATH, index=False, encoding="utf-8-sig")
    annual_stats.to_csv(ANNUAL_STATS_PATH, index=False, encoding="utf-8-sig")
    products.to_csv(PRODUCT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    REQUIREMENT_AUDIT_PATH.write_text(json.dumps(_json_safe(audit), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot_heatmap(annual)
    _write_report(annual, annual_stats, products, audit)
    print(json.dumps(_json_safe(audit), ensure_ascii=False, indent=2))
    print("annual_stats")
    print(annual_stats.to_string(index=False))
    print("product_audit")
    print(products.to_string(index=False))


if __name__ == "__main__":
    main()
