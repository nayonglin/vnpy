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

from stage063_early_adverse_precursor_audit import _json_safe, _md_table, _num, _read_csv


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage065"
MODEL_TAG = "stage065_full_sample_exit_path_proxy_audit_v1"
STAGE_SLUG = "stage065_full_sample_exit_path_proxy_audit"
OUTPUT_PREFIX = "rebuilt_c9_stage065_full_sample_exit_path_proxy_audit"

TOOLS_DIR = Path(__file__).resolve().parent
LINE_DIR = TOOLS_DIR.parent
OUTPUT_DIR = LINE_DIR / "outputs" / STAGE_SLUG
STAGES_DIR = LINE_DIR / "stages"

STAGE019_OUTPUT_DIR = LINE_DIR / "outputs" / "stage019_stage018_regime_gate_failure_attribution"
STAGE019_PREFIX = "rebuilt_c9_stage019_stage018_regime_gate_failure_attribution"
STAGE019_TAG = "stage019_stage018_regime_gate_failure_attribution_v1"
STAGE013_CLOSED_LOTS_PATH = (
    STAGE019_OUTPUT_DIR / f"{STAGE019_PREFIX}_stage013_rebuilt_closed_lots_{STAGE019_TAG}.csv"
)

STAGE059_OUTPUT_DIR = LINE_DIR / "outputs" / "stage059_trade_path_excursion_audit"
STAGE059_PREFIX = "rebuilt_c9_stage059_trade_path_excursion_audit"
STAGE059_TAG = "stage059_trade_path_excursion_audit_v1"
STAGE059_LOT_PATHS_PATH = STAGE059_OUTPUT_DIR / f"{STAGE059_PREFIX}_lot_paths_{STAGE059_TAG}.csv.gz"

LOT_FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_features_{MODEL_TAG}.csv.gz"
PRESSURE_FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pressure_features_{MODEL_TAG}.csv.gz"
PROXY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_summary_{MODEL_TAG}.csv"
MFE_BUCKET_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_mfe_bucket_summary_{MODEL_TAG}.csv"
YEARLY_PROXY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_yearly_proxy_summary_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

HARD_TAKE_PROFIT_R = [1.0, 2.0, 4.0, 8.0]
BREAKEVEN_AFTER_R = [1.0, 2.0, 4.0]
LOCK_SPECS = [(2.0, 1.0), (4.0, 1.0), (4.0, 2.0), (8.0, 2.0)]
MIN_FULL_RETENTION_PCT = 80.0

EXTERNAL_RESEARCH_SOURCES = [
    "Rob Carver dynamic trend following: https://qoppac.blogspot.com/2020/12/dynamic-trend-following.html",
    "Rob Carver stop losses: https://qoppac.blogspot.com/2020/02/what-is-right-way-to-set-stop-losses.html",
    "TradeStation MFE graph guide: https://help.tradestation.com/10_00/eng/tradestationhelp/subsystems/spr_topics/report/maximum_favorable_excursion__strategy_performance_report_.htm",
    "TradesViz MFE/MAE guide: https://www.tradesviz.com/blog/mfe-mae-charts/",
    "pysystemtrade GitHub: https://github.com/pst-group/pysystemtrade",
]
EXTERNAL_RESEARCH_JUDGMENT = (
    "Trailing exits and MFE-based profit locks are plausible exit diagnostics, but trend following depends on right-tail "
    "convexity. Stage065 treats these variants as optimistic closed-lot proxies and requires full-sample retention before "
    "any true-engine work."
)


def _variant_ids() -> list[tuple[str, str]]:
    variants: list[tuple[str, str]] = []
    for r in HARD_TAKE_PROFIT_R:
        variants.append((f"hard_takeprofit_{r:g}r", f"proxy_hard_tp_{r:g}r_pnl"))
    for r in BREAKEVEN_AFTER_R:
        variants.append((f"optimistic_breakeven_after_{r:g}r", f"proxy_be_after_{r:g}r_pnl"))
    for activate_r, lock_r in LOCK_SPECS:
        variants.append((f"optimistic_lock_{lock_r:g}r_after_{activate_r:g}r", f"proxy_lock_{lock_r:g}r_after_{activate_r:g}r_pnl"))
    return variants


def _prepare_lots(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    if "r_multiple" not in data.columns and "r_multiple_agg" in data.columns:
        data["r_multiple"] = data["r_multiple_agg"]
    for column in [
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "mfe_r",
        "mae_r",
        "days_to_mfe",
        "days_to_mae",
        "big_winner",
    ]:
        data[column] = _num(data, column, np.nan)
    if "entry_date" in data.columns:
        data["entry_date"] = pd.to_datetime(data["entry_date"], errors="coerce")
        data["entry_year"] = data["entry_date"].dt.year
    elif "entry_year" not in data.columns:
        data["entry_year"] = np.nan
    data["valid_proxy_sample"] = (
        data["risk_amount"].gt(0.0)
        & data["mfe_r"].notna()
        & data["realized_pnl"].notna()
        & data["r_multiple"].notna()
    )
    return data


def _apply_exit_proxy_variants(lots: pd.DataFrame) -> pd.DataFrame:
    data = _prepare_lots(lots)
    valid = data["valid_proxy_sample"].fillna(False)
    for r in HARD_TAKE_PROFIT_R:
        proxy_col = f"proxy_hard_tp_{r:g}r_pnl"
        delta_col = f"delta_hard_tp_{r:g}r"
        trigger_col = f"trigger_hard_tp_{r:g}r"
        trigger = valid & data["mfe_r"].ge(r)
        data[trigger_col] = trigger.astype(int)
        data[proxy_col] = data["realized_pnl"]
        data.loc[trigger, proxy_col] = data.loc[trigger, "risk_amount"] * r
        data[delta_col] = np.where(valid, data[proxy_col] - data["realized_pnl"], np.nan)
    for r in BREAKEVEN_AFTER_R:
        proxy_col = f"proxy_be_after_{r:g}r_pnl"
        delta_col = f"delta_be_after_{r:g}r"
        trigger_col = f"trigger_be_after_{r:g}r"
        trigger = valid & data["mfe_r"].ge(r) & data["r_multiple"].lt(0.0)
        data[trigger_col] = trigger.astype(int)
        data[proxy_col] = data["realized_pnl"]
        data.loc[trigger, proxy_col] = 0.0
        data[delta_col] = np.where(valid, data[proxy_col] - data["realized_pnl"], np.nan)
    for activate_r, lock_r in LOCK_SPECS:
        proxy_col = f"proxy_lock_{lock_r:g}r_after_{activate_r:g}r_pnl"
        delta_col = f"delta_lock_{lock_r:g}r_after_{activate_r:g}r"
        trigger_col = f"trigger_lock_{lock_r:g}r_after_{activate_r:g}r"
        trigger = valid & data["mfe_r"].ge(activate_r) & data["r_multiple"].lt(lock_r)
        data[trigger_col] = trigger.astype(int)
        data[proxy_col] = data["realized_pnl"]
        data.loc[trigger, proxy_col] = data.loc[trigger, "risk_amount"] * lock_r
        data[delta_col] = np.where(valid, data[proxy_col] - data["realized_pnl"], np.nan)
    return data


def _classify_stage065_proxy(
    *,
    full_retention_pct: float,
    winner_cut: float,
    loser_saved: float,
    pressure_delta: float,
) -> str:
    if pressure_delta <= 0.0:
        return "no_pressure_value"
    if full_retention_pct < MIN_FULL_RETENTION_PCT:
        return "right_tail_collision_or_retention_fail"
    if abs(min(winner_cut, 0.0)) > max(loser_saved, 0.0):
        return "right_tail_collision_or_retention_fail"
    return "proxy_candidate_needs_true_engine"


def _summarize_exit_proxy(full_lots: pd.DataFrame, pressure_lots: pd.DataFrame) -> pd.DataFrame:
    full = _apply_exit_proxy_variants(full_lots)
    pressure = _apply_exit_proxy_variants(pressure_lots)
    full_valid = full[full["valid_proxy_sample"].fillna(False)].copy()
    pressure_valid = pressure[pressure["valid_proxy_sample"].fillna(False)].copy()
    full_base_pnl = float(full_valid["realized_pnl"].sum())
    pressure_base_pnl = float(pressure_valid["realized_pnl"].sum()) if not pressure_valid.empty else 0.0
    rows: list[dict[str, Any]] = []
    for proxy_id, proxy_col in _variant_ids():
        if proxy_col not in full_valid.columns:
            continue
        full_delta = full_valid[proxy_col] - full_valid["realized_pnl"]
        pressure_delta_series = (
            pressure_valid[proxy_col] - pressure_valid["realized_pnl"] if proxy_col in pressure_valid.columns else pd.Series(dtype=float)
        )
        triggered = full_delta.ne(0.0)
        pressure_triggered = pressure_delta_series.ne(0.0) if not pressure_delta_series.empty else pd.Series(dtype=bool)
        proxy_pnl = float(full_valid[proxy_col].sum())
        full_retention = float(proxy_pnl / full_base_pnl * 100.0) if full_base_pnl else np.nan
        winner_cut = float(full_delta.where(full_delta < 0.0, 0.0).sum())
        loser_saved = float(full_delta.where(full_delta > 0.0, 0.0).sum())
        pressure_delta = float(pressure_delta_series.sum()) if not pressure_delta_series.empty else 0.0
        rows.append(
            {
                "proxy_id": proxy_id,
                "full_lots": int(len(full_valid)),
                "full_base_pnl": full_base_pnl,
                "full_proxy_pnl": proxy_pnl,
                "full_delta": float(full_delta.sum()),
                "full_retention_pct": full_retention,
                "full_triggered_lots": int(triggered.sum()),
                "full_triggered_big_winners": int((triggered & full_valid["big_winner"].fillna(0).gt(0)).sum()),
                "winner_cut": winner_cut,
                "loser_saved": loser_saved,
                "pressure_lots": int(len(pressure_valid)),
                "pressure_base_pnl": pressure_base_pnl,
                "pressure_proxy_pnl": float(pressure_valid[proxy_col].sum()) if proxy_col in pressure_valid.columns else np.nan,
                "pressure_delta": pressure_delta,
                "pressure_triggered_lots": int(pressure_triggered.sum()) if not pressure_delta_series.empty else 0,
                "proxy_class": _classify_stage065_proxy(
                    full_retention_pct=full_retention,
                    winner_cut=winner_cut,
                    loser_saved=loser_saved,
                    pressure_delta=pressure_delta,
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["proxy_class", "pressure_delta"], ascending=[True, False]).reset_index(drop=True)


def _mfe_bucket_summary(lots: pd.DataFrame) -> pd.DataFrame:
    data = _apply_exit_proxy_variants(lots)
    valid = data[data["valid_proxy_sample"].fillna(False)].copy()
    valid["mfe_bucket"] = pd.cut(
        valid["mfe_r"],
        bins=[-1.0, 0.0, 1.0, 2.0, 4.0, 8.0, np.inf],
        labels=["0", "0-1", "1-2", "2-4", "4-8", "8+"],
    )
    return (
        valid.groupby("mfe_bucket", observed=False)
        .agg(
            lots=("realized_pnl", "count"),
            pnl=("realized_pnl", "sum"),
            winner_pnl=("realized_pnl", lambda s: float(s[s > 0].sum())),
            loser_pnl=("realized_pnl", lambda s: float(s[s < 0].sum())),
            median_r_multiple=("r_multiple", "median"),
            median_mfe_r=("mfe_r", "median"),
            median_mae_r=("mae_r", "median"),
        )
        .reset_index()
    )


def _yearly_proxy_summary(full_lots: pd.DataFrame) -> pd.DataFrame:
    data = _apply_exit_proxy_variants(full_lots)
    valid = data[data["valid_proxy_sample"].fillna(False)].copy()
    rows: list[dict[str, Any]] = []
    for year, group in valid.groupby("entry_year", dropna=False):
        base = float(group["realized_pnl"].sum())
        row: dict[str, Any] = {
            "entry_year": int(year) if pd.notna(year) else 0,
            "lots": int(len(group)),
            "base_pnl": base,
        }
        for proxy_id, proxy_col in _variant_ids():
            row[f"{proxy_id}_pnl"] = float(group[proxy_col].sum())
            row[f"{proxy_id}_delta"] = float(group[proxy_col].sum() - base)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("entry_year").reset_index(drop=True)


def _stage065_decision(proxy_summary: pd.DataFrame) -> dict[str, Any]:
    candidates = proxy_summary[proxy_summary["proxy_class"].eq("proxy_candidate_needs_true_engine")].copy()
    if not candidates.empty:
        best = candidates.sort_values(["pressure_delta", "full_retention_pct"], ascending=[False, False]).iloc[0]
        decision_text = "stage065_exit_proxy_has_candidate_needs_true_engine"
        continue_after = "有。存在压力样本改善且全样本收益保留通过的 optimistic exit proxy，下一步只能做真实引擎验真。"
    else:
        best = proxy_summary.sort_values(["pressure_delta", "full_retention_pct"], ascending=[False, False]).iloc[0]
        decision_text = "stage065_exit_proxy_no_candidate_keep_readonly"
        continue_after = "有限。固定退出 proxy 要么收益保留失败，要么右尾错杀大于减亏；不应直接进入真引擎或扫止盈/锁盈参数。"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "audit_type": "full_sample_exit_path_proxy_readonly",
        "decision": decision_text,
        "strategy_changed": False,
        "official_live_config_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "best_proxy_id": str(best.get("proxy_id", "")),
        "best_proxy_class": str(best.get("proxy_class", "")),
        "best_full_retention_pct": float(best.get("full_retention_pct", np.nan)),
        "best_pressure_delta": float(best.get("pressure_delta", np.nan)),
        "best_winner_cut": float(best.get("winner_cut", np.nan)),
        "best_loser_saved": float(best.get("loser_saved", np.nan)),
        "external_research_sources": EXTERNAL_RESEARCH_SOURCES,
        "external_research_judgment": EXTERNAL_RESEARCH_JUDGMENT,
        "overfit_reflection_before": "否。Stage065 只审计低自由度退出 proxy 上界，不新增真引擎交易参数。",
        "continue_value_before": "有。Stage064 证明 giveback 只能作为退出路径诊断，需要确认全样本右尾冲突强度。",
        "overfit_reflection_after": "否。本阶段只读复用 closed-lot MFE/MAE，不根据结果调整止盈/锁盈阈值。",
        "continue_value_after": continue_after,
        "outputs": {
            "lot_features": str(LOT_FEATURES_PATH),
            "pressure_features": str(PRESSURE_FEATURES_PATH),
            "proxy_summary": str(PROXY_SUMMARY_PATH),
            "mfe_bucket_summary": str(MFE_BUCKET_SUMMARY_PATH),
            "yearly_proxy_summary": str(YEARLY_PROXY_SUMMARY_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _plot(proxy_summary: pd.DataFrame) -> None:
    shown = proxy_summary.sort_values("pressure_delta", ascending=False).head(10)
    fig, axes = plt.subplots(2, 1, figsize=(15, 10), constrained_layout=True)
    axes[0].bar(shown["proxy_id"], shown["pressure_delta"], color="#2563eb")
    axes[0].axhline(0.0, color="#111827", linewidth=1.0)
    axes[0].set_title("Stage065 Pressure-Sample Delta")
    axes[0].tick_params(axis="x", rotation=30)
    axes[0].grid(True, axis="y", alpha=0.25)
    colors = np.where(shown["full_retention_pct"].ge(MIN_FULL_RETENTION_PCT), "#16a34a", "#dc2626")
    axes[1].bar(shown["proxy_id"], shown["full_retention_pct"], color=colors)
    axes[1].axhline(MIN_FULL_RETENTION_PCT, color="#111827", linewidth=1.0, linestyle="--")
    axes[1].set_title("Full-Sample Return Retention")
    axes[1].tick_params(axis="x", rotation=30)
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    decision: dict[str, Any],
    proxy_summary: pd.DataFrame,
    mfe_summary: pd.DataFrame,
    yearly_summary: pd.DataFrame,
) -> None:
    report = f"""# Stage065 - 全样本退出路径 proxy 审计

- 生成时间：`{decision['generated_at']}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 决策：`{decision['decision']}`
- 阶段性质：只读 proxy 上界；不改官方 C9，不连接 CTP，不调用订单 API。

## 外部调研判断

- 参考：{'; '.join(EXTERNAL_RESEARCH_SOURCES)}
- 我的判断：固定止盈、保本和锁盈都必须先检查全样本右尾损失。closed-lot proxy 只能给上界，不能替代真实组合引擎。

## 输入

- Stage013 closed lots：`{STAGE013_CLOSED_LOTS_PATH}`
- Stage059 pressure lot paths：`{STAGE059_LOT_PATHS_PATH}`

## Proxy Summary

{_md_table(proxy_summary)}

## MFE Bucket Summary

{_md_table(mfe_summary)}

## Yearly Proxy Summary

{_md_table(yearly_summary, max_rows=20)}

## 判断

- best proxy：`{decision['best_proxy_id']}`
- proxy class：`{decision['best_proxy_class']}`
- full retention：`{decision['best_full_retention_pct']:.4f}%`
- pressure delta：`{decision['best_pressure_delta']:.2f}`
- winner cut：`{decision['best_winner_cut']:.2f}`
- loser saved：`{decision['best_loser_saved']:.2f}`
- 过拟合反思：{decision['overfit_reflection_after']}
- 继续价值反思：{decision['continue_value_after']}
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage065_full_sample_exit_path_proxy_audit.md"
    content = f"""# Stage065 - 全样本退出路径 proxy 审计

- line_id：`{LINE_ID}`
- 当前模式：`day`
- 记录时间：`{decision['generated_at']} CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读 proxy 上界，不改官方实盘配置。
- 是否重要突破：`否`
- 是否触发A/B：`否`

## 外部调研与判断

- 参考资料：Rob Carver dynamic trend following/stop losses、TradeStation MFE graph、TradesViz MFE/MAE、pysystemtrade。
- 我的判断：趋势跟随不能机械止盈，必须先检查全样本右尾冲突。本阶段所有 proxy 都是乐观上界，不是真实成交路径。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage065_full_sample_exit_path_proxy_audit.py`
- 新增测试：`tests/test_rebuilt_c9_stage065_exit_path_proxy.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：无交易参数；固定审计 `hard_takeprofit_1/2/4/8r`、`optimistic_breakeven_after_1/2/4r`、`optimistic_lock_1r_after_2r`、`optimistic_lock_1/2r_after_4/8r`。
- 修改参数：无。
- 删除参数：无。

## 结果

- 决策：`{decision['decision']}`。
- best proxy：`{decision['best_proxy_id']}`。
- proxy class：`{decision['best_proxy_class']}`。
- full retention：`{decision['best_full_retention_pct']:.4f}%`。
- pressure delta：`{decision['best_pressure_delta']:.2f}`。
- winner cut：`{decision['best_winner_cut']:.2f}`。
- loser saved：`{decision['best_loser_saved']:.2f}`。

## 回测指标说明

- 本阶段不是新增回测或真引擎 A/C，只读复用 Stage013 closed lots 与 Stage059 pressure lot paths，因此不产生新的期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数和胜率。
- 不连接 CTP，不调用订单 API，不改官方实盘配置。

## 输出文件

- report：`{REPORT_PATH}`
- proxy_summary：`{PROXY_SUMMARY_PATH}`
- chart：`{CHART_PATH}`

## 过拟合反思

- 运行前判断：否。只审计低自由度退出 proxy 上界，不新增真引擎交易参数。
- 运行后判断：{decision['overfit_reflection_after']}

## 继续价值反思

- 运行前判断：有。Stage064 证明 giveback 只能作为退出路径诊断，需要确认全样本右尾冲突强度。
- 运行后判断：{decision['continue_value_after']}
"""
    path.write_text(content, encoding="utf-8")
    return path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    full_lots_raw = _read_csv(STAGE013_CLOSED_LOTS_PATH)
    pressure_lots_raw = _read_csv(STAGE059_LOT_PATHS_PATH)
    full_lots = _apply_exit_proxy_variants(full_lots_raw)
    pressure_lots = _apply_exit_proxy_variants(pressure_lots_raw)
    proxy_summary = _summarize_exit_proxy(full_lots, pressure_lots)
    mfe_summary = _mfe_bucket_summary(full_lots)
    yearly_summary = _yearly_proxy_summary(full_lots)
    decision = _stage065_decision(proxy_summary)

    _plot(proxy_summary)
    full_lots.to_csv(LOT_FEATURES_PATH, index=False, encoding="utf-8-sig")
    pressure_lots.to_csv(PRESSURE_FEATURES_PATH, index=False, encoding="utf-8-sig")
    proxy_summary.to_csv(PROXY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    mfe_summary.to_csv(MFE_BUCKET_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    yearly_summary.to_csv(YEARLY_PROXY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, proxy_summary, mfe_summary, yearly_summary)
    stage_record = _write_stage_record(decision)
    decision["stage_record"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
