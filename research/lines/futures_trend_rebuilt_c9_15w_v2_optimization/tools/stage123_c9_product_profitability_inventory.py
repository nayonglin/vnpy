from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE_ID = "stage123_c9_product_profitability_inventory"
MODEL_TAG = f"{STAGE_ID}_v1"

SOURCE_CLOSED_LOTS_PATH = (
    ROOT_DIR
    / "examples"
    / "portfolio_backtesting"
    / "backtest_outputs"
    / "qmt_roll_stage847_stage830_c4_stop_retry_engine_closed_lots_stage847_stage830_c4_stop_retry_engine_v1.csv"
)
STAGE122_TREND_SUMMARY_PATH = (
    ROOT_DIR
    / "research"
    / "lines"
    / LINE_ID
    / "outputs"
    / "stage122_2022_full_market_trend_inventory"
    / "rebuilt_c9_v2_stage122_2022_full_market_trend_inventory_product_period_summary_stage122_2022_full_market_trend_inventory_v1.csv"
)

OUTPUT_DIR = ROOT_DIR / "research" / "lines" / LINE_ID / "outputs" / STAGE_ID
STAGE_RECORD_PATH = (
    ROOT_DIR
    / "research"
    / "lines"
    / LINE_ID
    / "stages"
    / "20260709_1341_stage123_c9_product_profitability_inventory.md"
)

PRODUCT_SUMMARY_PATH = OUTPUT_DIR / f"rebuilt_c9_v2_{STAGE_ID}_product_period_summary_{MODEL_TAG}.csv"
LOT_WITH_PERIOD_PATH = OUTPUT_DIR / f"rebuilt_c9_v2_{STAGE_ID}_closed_lots_with_period_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"rebuilt_c9_v2_{STAGE_ID}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"rebuilt_c9_v2_{STAGE_ID}_report_{MODEL_TAG}.md"
LOSS_WINDOW_CHART_PATH = OUTPUT_DIR / f"rebuilt_c9_v2_{STAGE_ID}_loss_window_exit_pnl_by_product_{MODEL_TAG}.png"
FULL_SAMPLE_CHART_PATH = OUTPUT_DIR / f"rebuilt_c9_v2_{STAGE_ID}_full_sample_pnl_by_product_{MODEL_TAG}.png"

LOSS_WINDOW_START = pd.Timestamp("2022-03-09")
LOSS_WINDOW_END = pd.Timestamp("2022-06-29")
FULL_2022_START = pd.Timestamp("2022-01-01")
FULL_2022_END = pd.Timestamp("2022-12-31")
MATERIAL_TRADE_COUNT = 3
MATERIAL_PROFIT_FACTOR = 1.10


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    return view.to_markdown(index=False, floatfmt=".4f")


def _canonical_product_from_vt(vt_symbol: object) -> str:
    text = str(vt_symbol or "").strip()
    if "." not in text:
        return text
    symbol, exchange = text.split(".", 1)
    match = re.match(r"([A-Za-z]+)", symbol)
    product = match.group(1) if match else symbol
    return f"{product}.{exchange}"


def _load_closed_lots() -> pd.DataFrame:
    lots = pd.read_csv(SOURCE_CLOSED_LOTS_PATH)
    required = {"vt_symbol", "entry_date", "exit_date", "realized_pnl", "r_multiple", "direction", "volume"}
    missing = sorted(required - set(lots.columns))
    if missing:
        raise ValueError(f"closed_lots missing required columns: {missing}")
    lots["entry_date"] = pd.to_datetime(lots["entry_date"], errors="coerce").dt.normalize()
    lots["exit_date"] = pd.to_datetime(lots["exit_date"], errors="coerce").dt.normalize()
    lots["product_vt_symbol"] = lots["vt_symbol"].map(_canonical_product_from_vt)
    for column in ["realized_pnl", "r_multiple", "volume", "risk_amount"]:
        if column in lots.columns:
            lots[column] = pd.to_numeric(lots[column], errors="coerce")
    lots["realized_pnl"] = lots["realized_pnl"].fillna(0.0)
    lots["r_multiple"] = lots["r_multiple"].fillna(0.0)
    lots["direction"] = lots["direction"].fillna("").astype(str)
    lots["winner"] = lots["realized_pnl"].gt(0.0)
    lots["exit_period_loss_window"] = lots["exit_date"].between(LOSS_WINDOW_START, LOSS_WINDOW_END, inclusive="both")
    lots["entry_period_loss_window"] = lots["entry_date"].between(LOSS_WINDOW_START, LOSS_WINDOW_END, inclusive="both")
    lots["exit_period_2022"] = lots["exit_date"].between(FULL_2022_START, FULL_2022_END, inclusive="both")
    lots["entry_period_2022"] = lots["entry_date"].between(FULL_2022_START, FULL_2022_END, inclusive="both")
    lots["exit_period_full_sample"] = lots["exit_date"].notna()
    return lots


def _profit_factor(pnl: pd.Series) -> float:
    profit = float(pnl[pnl > 0.0].sum())
    loss = float(-pnl[pnl < 0.0].sum())
    if loss <= 0.0:
        return math.inf if profit > 0.0 else 0.0
    return profit / loss


def _classify(row: pd.Series) -> str:
    net = float(row["net_pnl"])
    trades = int(row["trade_count"])
    pf = float(row["profit_factor"]) if pd.notna(row["profit_factor"]) else 0.0
    if net > 0.0 and trades >= MATERIAL_TRADE_COUNT and pf >= MATERIAL_PROFIT_FACTOR:
        return "material_profitable"
    if net > 0.0:
        return "thin_or_low_pf_positive"
    if net == 0.0:
        return "flat_no_edge"
    return "loss_making"


def _summarize_period(lots: pd.DataFrame, period: str, mask_column: str) -> pd.DataFrame:
    frame = lots[lots[mask_column]].copy()
    rows: list[dict[str, Any]] = []
    for product, group in frame.groupby("product_vt_symbol", sort=True):
        pnl = pd.to_numeric(group["realized_pnl"], errors="coerce").fillna(0.0)
        r = pd.to_numeric(group["r_multiple"], errors="coerce").fillna(0.0)
        long = group[group["direction"].eq("long")]
        short = group[group["direction"].eq("short")]
        gross_profit = float(pnl[pnl > 0.0].sum())
        gross_loss = float(pnl[pnl < 0.0].sum())
        rows.append(
            {
                "period": period,
                "period_mask": mask_column,
                "product_vt_symbol": product,
                "trade_count": int(len(group)),
                "net_pnl": float(pnl.sum()),
                "gross_profit": gross_profit,
                "gross_loss": gross_loss,
                "profit_factor": _profit_factor(pnl),
                "win_count": int((pnl > 0.0).sum()),
                "loss_count": int((pnl < 0.0).sum()),
                "win_rate": float((pnl > 0.0).mean()) if len(group) else 0.0,
                "avg_pnl": float(pnl.mean()) if len(group) else 0.0,
                "median_pnl": float(pnl.median()) if len(group) else 0.0,
                "max_win": float(pnl.max()) if len(group) else 0.0,
                "max_loss": float(pnl.min()) if len(group) else 0.0,
                "sum_r": float(r.sum()),
                "avg_r": float(r.mean()) if len(group) else 0.0,
                "long_trade_count": int(len(long)),
                "long_pnl": float(pd.to_numeric(long["realized_pnl"], errors="coerce").fillna(0.0).sum()),
                "short_trade_count": int(len(short)),
                "short_pnl": float(pd.to_numeric(short["realized_pnl"], errors="coerce").fillna(0.0).sum()),
                "first_entry_date": group["entry_date"].min().date().isoformat() if group["entry_date"].notna().any() else "",
                "last_exit_date": group["exit_date"].max().date().isoformat() if group["exit_date"].notna().any() else "",
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["profitability_class"] = out.apply(_classify, axis=1)
    out.sort_values(["period", "net_pnl"], ascending=[True, False], inplace=True)
    return out.reset_index(drop=True)


def _attach_trend_context(summary: pd.DataFrame) -> pd.DataFrame:
    if not STAGE122_TREND_SUMMARY_PATH.exists() or summary.empty:
        return summary
    trend = pd.read_csv(STAGE122_TREND_SUMMARY_PATH)
    trend_cols = [
        "period",
        "product_vt_symbol",
        "trend_direction",
        "signed_return_pct",
        "abs_return_pct",
        "whole_window_trend_eff",
        "mean_adx14",
        "trend_score",
        "trend_bucket",
    ]
    trend = trend[[c for c in trend_cols if c in trend.columns]].copy()
    loss_trend = trend[trend["period"].eq("loss_window_20220309_20220629")].drop(columns=["period"])
    loss_trend = loss_trend.add_prefix("loss_window_")
    loss_trend.rename(columns={"loss_window_product_vt_symbol": "product_vt_symbol"}, inplace=True)
    full_trend = trend[trend["period"].eq("full_2022")].drop(columns=["period"])
    full_trend = full_trend.add_prefix("full2022_")
    full_trend.rename(columns={"full2022_product_vt_symbol": "product_vt_symbol"}, inplace=True)
    out = summary.merge(loss_trend, on="product_vt_symbol", how="left")
    out = out.merge(full_trend, on="product_vt_symbol", how="left")
    return out


def _period_totals(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for period, group in summary.groupby("period", sort=False):
        rows.append(
            {
                "period": period,
                "product_count": int(group["product_vt_symbol"].nunique()),
                "profitable_count": int(group["net_pnl"].gt(0.0).sum()),
                "material_profitable_count": int(group["profitability_class"].eq("material_profitable").sum()),
                "loss_making_count": int(group["net_pnl"].lt(0.0).sum()),
                "total_net_pnl": float(group["net_pnl"].sum()),
                "top_profitable_products": "/".join(group[group["net_pnl"].gt(0.0)].nlargest(10, "net_pnl")["product_vt_symbol"].astype(str)),
                "top_loss_products": "/".join(group[group["net_pnl"].lt(0.0)].nsmallest(10, "net_pnl")["product_vt_symbol"].astype(str)),
            }
        )
    return pd.DataFrame(rows)


def _plot(summary: pd.DataFrame) -> None:
    def plot_period(period: str, path: Path, title: str) -> None:
        frame = summary[summary["period"].eq(period)].copy()
        if frame.empty:
            return
        frame = frame.sort_values("net_pnl", ascending=True)
        colors = np.where(frame["net_pnl"].ge(0.0), "#2ca02c", "#d62728")
        fig, ax = plt.subplots(figsize=(14, 9))
        ax.barh(frame["product_vt_symbol"], frame["net_pnl"], color=colors)
        ax.axvline(0, color="#111111", linewidth=1.0)
        ax.set_xlabel("realized pnl")
        ax.set_title(title)
        ax.grid(axis="x", alpha=0.24)
        fig.tight_layout()
        fig.savefig(path, dpi=180)
        plt.close(fig)

    plot_period(
        "loss_window_exit_20220309_20220629",
        LOSS_WINDOW_CHART_PATH,
        "C9 realized PnL by product: exits in 2022 loss window",
    )
    plot_period("full_sample_exit", FULL_SAMPLE_CHART_PATH, "C9 realized PnL by product: full sample exits")


def _write_report(summary: pd.DataFrame, totals: pd.DataFrame, decision: dict[str, Any]) -> None:
    display_cols = [
        "product_vt_symbol",
        "trade_count",
        "net_pnl",
        "profit_factor",
        "win_rate",
        "avg_r",
        "long_pnl",
        "short_pnl",
        "profitability_class",
        "loss_window_trend_direction",
        "loss_window_signed_return_pct",
        "loss_window_trend_score",
    ]
    lines = [
        "# Stage123 C9 品种盈利能力账本审计",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 口径：当前 C9/15w Stage847 stop/retry 真实引擎 closed_lots，按 `vt_symbol` 标准化为产品后聚合。",
        "- 注意：本阶段统计的是 C9 已实际交易过的品种；未被交易/未入池的品种不能从该账本直接判断盈利，需要单独逐品种真实引擎重跑。",
        "",
        "## Decision",
        "",
        f"- 结论：`{decision['conclusion']}`",
        f"- 判断：{decision['judgment']}",
        "",
        "## Period Totals",
        "",
        _md_table(totals, max_rows=10),
        "",
        "## Loss Window Exit Products",
        "",
        _md_table(
            summary[summary["period"].eq("loss_window_exit_20220309_20220629")][display_cols],
            max_rows=40,
        ),
        "",
        "## Full 2022 Exit Products",
        "",
        _md_table(summary[summary["period"].eq("full_2022_exit")][display_cols], max_rows=40),
        "",
        "## Full Sample Products",
        "",
        _md_table(summary[summary["period"].eq("full_sample_exit")][display_cols], max_rows=50),
        "",
        "## Outputs",
        "",
        f"- product_summary：`{PRODUCT_SUMMARY_PATH}`",
        f"- closed_lots_with_period：`{LOT_WITH_PERIOD_PATH}`",
        f"- chart_loss_window：`{LOSS_WINDOW_CHART_PATH}`",
        f"- chart_full_sample：`{FULL_SAMPLE_CHART_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], totals: pd.DataFrame) -> None:
    loss_row = totals[totals["period"].eq("loss_window_exit_20220309_20220629")].iloc[0]
    full2022_row = totals[totals["period"].eq("full_2022_exit")].iloc[0]
    full_row = totals[totals["period"].eq("full_sample_exit")].iloc[0]
    text = f"""# Stage123 C9 品种盈利能力账本审计

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：2026-07-09 13:41 CST
- 工作区：`{ROOT_DIR}`
- 阶段性质：只读归因；统计当前 C9/15w 已实际交易品种的盈利能力。
- 是否重要突破：否，归因证据，不是策略候选。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：pysystemtrade / PyTrendFollow / futures trend following 资料都支持在多市场系统里做 instrument-level performance attribution，不能只看价格趋势强度。
- 我的判断：先统计 C9 实际 closed_lots，回答“策略在这些品种上是否赚钱”；未交易的全市场品种需要另开逐品种真实引擎重跑，不能从本账本直接得出。

## 本次变更

- 新增脚本：`{Path(__file__).relative_to(ROOT_DIR)}`
- 修改脚本：无正式入口修改。
- 删除脚本：无。
- 新增参数：`LOSS_WINDOW=2022-03-09..2022-06-29`、`FULL_2022=2022-01-01..2022-12-31`、`MATERIAL_TRADE_COUNT=3`、`MATERIAL_PROFIT_FACTOR=1.10`。
- 修改参数：无策略参数。
- 删除参数：无。

## 回测/归因参数

- 数据区间：closed_lots 覆盖 `2018-01-15` 到 `2026-05-07`。
- 账户规模：沿用源账本 C9/15w，不重新回测。
- 成本口径：沿用源账本已实现盈亏。
- 样本过滤：按 exit_date 和 entry_date 分 period；主表以 exit_date 口径为准。
- 策略/归因口径：当前 C9/15w Stage847 stop/retry 真实引擎 closed_lots。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：源账本内已体现在 realized_pnl，未单独重算。
- 总交易次数：full sample `{int(full_row['product_count'])}` 个产品、closed lots 见明细。
- 胜率：见 product summary。
- 其他关键指标：loss window exit 产品 `{int(loss_row['product_count'])}` 个，正收益 `{int(loss_row['profitable_count'])}` 个，材料性正收益 `{int(loss_row['material_profitable_count'])}` 个，总净 PnL `{float(loss_row['total_net_pnl']):.2f}`；full 2022 exit 正收益 `{int(full2022_row['profitable_count'])}/{int(full2022_row['product_count'])}`；full sample 正收益 `{int(full_row['profitable_count'])}/{int(full_row['product_count'])}`。

## 输出文件

- report：`{REPORT_PATH}`
- summary：`{PRODUCT_SUMMARY_PATH}`
- orders：不适用。
- daily：不适用。
- quality：`{LOT_WITH_PERIOD_PATH}`

## 结论

- 本阶段结论：`{decision['conclusion']}`。
- 是否进入下一步：`False`。
- 下一步：若要回答未入池品种是否能赚钱，需要另开逐品种 C9 真实引擎重跑；本阶段不能直接扩池。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只读既有 closed_lots，不按结果改池子、改参数或生成交易规则。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有，但下一步应是逐品种真实引擎而非看趋势表。
- 原因：它能区分“有趋势”与“策略实际能赚钱”，但对未交易品种还没有证据。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录归因结论。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，非正式候选、非突破。
"""
    STAGE_RECORD_PATH.parent.mkdir(parents=True, exist_ok=True)
    STAGE_RECORD_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lots = _load_closed_lots()
    period_specs = [
        ("loss_window_exit_20220309_20220629", "exit_period_loss_window"),
        ("loss_window_entry_20220309_20220629", "entry_period_loss_window"),
        ("full_2022_exit", "exit_period_2022"),
        ("full_2022_entry", "entry_period_2022"),
        ("full_sample_exit", "exit_period_full_sample"),
    ]
    summaries = [_summarize_period(lots, period, mask) for period, mask in period_specs]
    summary = pd.concat([frame for frame in summaries if not frame.empty], ignore_index=True, sort=False)
    summary = _attach_trend_context(summary)
    totals = _period_totals(summary)

    loss_exit = totals[totals["period"].eq("loss_window_exit_20220309_20220629")].iloc[0]
    full_2022_exit = totals[totals["period"].eq("full_2022_exit")].iloc[0]
    full_sample = totals[totals["period"].eq("full_sample_exit")].iloc[0]
    decision = {
        "stage": "Stage123",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "conclusion": "c9_product_profitability_is_concentrated_not_equivalent_to_trend_inventory",
        "judgment": (
            "C9 did make money on several products, but profitability is concentrated and period-dependent. "
            "The 2022 loss window has both profitable and loss-making products in the existing strategy pool; "
            "untraded full-market trend products still require a separate single-product true-engine replay."
        ),
        "loss_window_exit": _json_safe(loss_exit.to_dict()),
        "full_2022_exit": _json_safe(full_2022_exit.to_dict()),
        "full_sample_exit": _json_safe(full_sample.to_dict()),
        "outputs": {
            "product_summary": str(PRODUCT_SUMMARY_PATH),
            "closed_lots_with_period": str(LOT_WITH_PERIOD_PATH),
            "report": str(REPORT_PATH),
            "loss_window_chart": str(LOSS_WINDOW_CHART_PATH),
            "full_sample_chart": str(FULL_SAMPLE_CHART_PATH),
            "stage_record": str(STAGE_RECORD_PATH),
        },
    }

    _plot(summary)
    lots.to_csv(LOT_WITH_PERIOD_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, totals, decision)
    _write_stage_record(decision, totals)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
