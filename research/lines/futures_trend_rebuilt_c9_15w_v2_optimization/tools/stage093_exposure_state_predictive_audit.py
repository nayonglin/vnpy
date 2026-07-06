from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage093"
MODEL_TAG = "stage093_exposure_state_predictive_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage093_exposure_state_predictive_audit"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage093_exposure_state_predictive_audit"
STAGES_DIR = LINE_DIR / "stages"

BACKTEST_OUT = ROOT / "examples" / "portfolio_backtesting" / "backtest_outputs"
STAGE167_CURVES = BACKTEST_OUT / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_curves_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv"

PANEL_PATH = OUT / f"{OUTPUT_PREFIX}_daily_panel_{MODEL_TAG}.csv.gz"
FACTOR_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_factor_bucket_summary_{MODEL_TAG}.csv"
GATE_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_top_state_gate_summary_{MODEL_TAG}.csv"
BAD_WINDOW_PATH = OUT / f"{OUTPUT_PREFIX}_bad_window_factor_summary_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

START_MONTH_MIN = "2020-01"
START_MONTH_MAX = "2026-01"
REQUESTED_END = pd.Timestamp("2026-06-30")
BAD_WINDOW_START = pd.Timestamp("2022-07-15")
BAD_WINDOW_END = pd.Timestamp("2023-07-05")

EXTERNAL_RESEARCH = [
    {
        "source": "CAIA / Kaminski CTA risk management paper",
        "url": "https://caia.org/sites/default/files/AIAR_Q1_2016_04_Kaminsky_CTARiskManagement.pdf",
        "finding": "CTA risk management is framed through positions/exposures across markets; exposure sizing matters but must be evaluated as portfolio construction, not post-hoc drawdown trimming.",
    },
    {
        "source": "BNP Paribas trend following essentials",
        "url": "https://wealthmanagement.bnpparibas/en/insights/market-strategy/trend-following-2024.html",
        "finding": "Trend following needs diversification and risk management; positions are built as trends develop, so exposure controls can also suppress the intended right tail.",
    },
    {
        "source": "Diva thesis on CTA position sizing",
        "url": "https://www.diva-portal.org/smash/get/diva2%3A730028/fulltext01.pdf",
        "finding": "Position sizing and equal risk contribution are plausible CTA risk tools, but different sizing methods need direct performance testing.",
    },
]


FACTOR_DEFINITIONS = {
    "broker10_margin_to_equity_pct": {"label": "broker10 margin/equity", "higher_is_risk": True},
    "total_margin_to_equity_pct": {"label": "exact margin/equity", "higher_is_risk": True},
    "c3_active_contracts": {"label": "active contracts", "higher_is_risk": True},
    "c3_active_products": {"label": "active products", "higher_is_risk": True},
    "drawdown_depth_pct": {"label": "current drawdown depth", "higher_is_risk": True},
    "recent_5d_loss_pct": {"label": "recent 5d loss pressure", "higher_is_risk": True},
    "recent_20d_loss_pct": {"label": "recent 20d loss pressure", "higher_is_risk": True},
    "recent_20d_abs_return_pct": {"label": "recent 20d realized movement", "higher_is_risk": True},
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    try:
        if pd.isna(value) and not isinstance(value, (str, bytes)):
            return None
    except Exception:
        pass
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _input_audit(paths: list[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.exists():
            stat = path.stat()
            rows.append(
                {
                    "path": str(path),
                    "exists": True,
                    "bytes": int(stat.st_size),
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    "sha256": _sha256(path),
                }
            )
        else:
            rows.append({"path": str(path), "exists": False, "bytes": 0, "mtime": "", "sha256": ""})
    return pd.DataFrame(rows)


def load_curves() -> pd.DataFrame:
    data = pd.read_csv(STAGE167_CURVES, encoding="utf-8-sig")
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data = data.dropna(subset=["date"]).copy()
    data["requested_start_month"] = data["requested_start_month"].astype(str)
    data = data[data["date"].le(REQUESTED_END)].copy()
    numeric_cols = [
        "account_equity",
        "account_capital",
        "net_pnl",
        "total_pnl",
        "trading_pnl",
        "holding_pnl",
        "total_margin_exact",
        "broker10_total_margin_exact",
        "broker10_margin_to_equity_pct",
        "c3_active_contracts",
        "c3_active_products",
        "trade_count",
        "drawdown_pct",
    ]
    for column in numeric_cols:
        data[column] = pd.to_numeric(data.get(column, 0.0), errors="coerce").fillna(0.0)
    return data.sort_values(["requested_start_month", "date"]).reset_index(drop=True)


def build_panel(curves: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for _, group in curves.groupby("requested_start_month", sort=True):
        frame = group.sort_values("date").reset_index(drop=True).copy()
        capital = frame["account_capital"].replace(0.0, np.nan)
        equity = frame["account_equity"].replace(0.0, np.nan)
        frame["total_margin_to_equity_pct"] = frame["total_margin_exact"] / equity * 100.0
        frame["drawdown_depth_pct"] = -frame["drawdown_pct"].clip(upper=0.0)
        frame["daily_return_on_capital_pct"] = frame["net_pnl"] / capital * 100.0
        frame["rolling_5d_return_pct"] = frame["daily_return_on_capital_pct"].rolling(5, min_periods=1).sum()
        frame["rolling_20d_return_pct"] = frame["daily_return_on_capital_pct"].rolling(20, min_periods=1).sum()
        frame["recent_5d_loss_pct"] = (-frame["rolling_5d_return_pct"]).clip(lower=0.0)
        frame["recent_20d_loss_pct"] = (-frame["rolling_20d_return_pct"]).clip(lower=0.0)
        frame["recent_20d_abs_return_pct"] = frame["daily_return_on_capital_pct"].abs().rolling(20, min_periods=1).sum()
        frame["next_date"] = frame["date"].shift(-1)
        frame["next_net_pnl"] = frame["net_pnl"].shift(-1)
        frame["next_return_on_capital_pct"] = frame["daily_return_on_capital_pct"].shift(-1)
        frame["next_drawdown_pct"] = frame["drawdown_pct"].shift(-1)
        frame["next_drawdown_delta_pp"] = frame["next_drawdown_pct"] - frame["drawdown_pct"]
        frame["next_loss"] = frame["next_net_pnl"] < -1e-9
        frame["next_drawdown_deepens"] = frame["next_drawdown_delta_pp"] < -1e-9
        frame["in_bad_window"] = frame["date"].between(BAD_WINDOW_START, BAD_WINDOW_END)
        rows.append(frame)
    panel = pd.concat(rows, ignore_index=True)
    focus = panel["requested_start_month"].between(START_MONTH_MIN, START_MONTH_MAX)
    panel = panel[focus & panel["next_date"].notna()].copy()
    for factor in FACTOR_DEFINITIONS:
        panel[factor] = pd.to_numeric(panel[factor], errors="coerce").replace([np.inf, -np.inf], np.nan)
    return panel.reset_index(drop=True)


def _bucket_values(values: pd.Series, buckets: int) -> pd.Series:
    clean = pd.to_numeric(values, errors="coerce")
    if clean.nunique(dropna=True) <= 1:
        return pd.Series(["all"] * len(clean), index=values.index)
    ranks = clean.rank(method="first")
    labels = [f"q{i + 1}" for i in range(buckets)]
    return pd.qcut(ranks, q=buckets, labels=labels, duplicates="drop").astype(str)


def build_factor_bucket_summary(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    base_loss_rate = float(panel["next_loss"].mean())
    base_deepen_rate = float(panel["next_drawdown_deepens"].mean())
    for factor, meta in FACTOR_DEFINITIONS.items():
        valid = panel.dropna(subset=[factor, "next_net_pnl"]).copy()
        if valid.empty:
            continue
        valid["bucket"] = _bucket_values(valid[factor], 5)
        for bucket, group in valid.groupby("bucket", sort=True):
            positive_sum = float(group.loc[group["next_net_pnl"].gt(0), "next_net_pnl"].sum())
            negative_sum = float(group.loc[group["next_net_pnl"].lt(0), "next_net_pnl"].sum())
            rows.append(
                {
                    "factor": factor,
                    "factor_label": meta["label"],
                    "bucket": bucket,
                    "rows": int(len(group)),
                    "factor_min": float(group[factor].min()),
                    "factor_median": float(group[factor].median()),
                    "factor_max": float(group[factor].max()),
                    "next_net_pnl_sum": float(group["next_net_pnl"].sum()),
                    "next_net_pnl_mean": float(group["next_net_pnl"].mean()),
                    "positive_next_pnl_sum": positive_sum,
                    "negative_next_pnl_sum": negative_sum,
                    "loss_rate": float(group["next_loss"].mean()),
                    "loss_rate_lift": float(group["next_loss"].mean() - base_loss_rate),
                    "drawdown_deepen_rate": float(group["next_drawdown_deepens"].mean()),
                    "drawdown_deepen_rate_lift": float(group["next_drawdown_deepens"].mean() - base_deepen_rate),
                    "bad_window_row_ratio": float(group["in_bad_window"].mean()),
                }
            )
    return pd.DataFrame(rows)


def build_top_state_gate_summary(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    total_positive = float(panel.loc[panel["next_net_pnl"].gt(0), "next_net_pnl"].sum())
    total_negative_abs = float(-panel.loc[panel["next_net_pnl"].lt(0), "next_net_pnl"].sum())
    base_loss_rate = float(panel["next_loss"].mean())
    base_deepen_rate = float(panel["next_drawdown_deepens"].mean())
    for factor, meta in FACTOR_DEFINITIONS.items():
        valid = panel.dropna(subset=[factor, "next_net_pnl"]).copy()
        if valid.empty:
            continue
        for tail_name, quantile in [("top10", 0.90), ("top20", 0.80)]:
            threshold = float(valid[factor].quantile(quantile))
            selected = valid[valid[factor].ge(threshold)].copy()
            if selected.empty:
                continue
            positive_sum = float(selected.loc[selected["next_net_pnl"].gt(0), "next_net_pnl"].sum())
            negative_abs_sum = float(-selected.loc[selected["next_net_pnl"].lt(0), "next_net_pnl"].sum())
            net_sum = float(selected["next_net_pnl"].sum())
            loss_share = negative_abs_sum / total_negative_abs if total_negative_abs > 0 else np.nan
            gain_share = positive_sum / total_positive if total_positive > 0 else np.nan
            rows.append(
                {
                    "factor": factor,
                    "factor_label": meta["label"],
                    "tail": tail_name,
                    "threshold": threshold,
                    "rows": int(len(selected)),
                    "row_share": float(len(selected) / len(valid)),
                    "next_net_pnl_sum": net_sum,
                    "positive_next_pnl_sum": positive_sum,
                    "negative_next_pnl_abs_sum": negative_abs_sum,
                    "loss_capture_share": float(loss_share),
                    "gain_sacrifice_share": float(gain_share),
                    "loss_minus_gain_share": float(loss_share - gain_share),
                    "loss_rate": float(selected["next_loss"].mean()),
                    "loss_rate_lift": float(selected["next_loss"].mean() - base_loss_rate),
                    "drawdown_deepen_rate": float(selected["next_drawdown_deepens"].mean()),
                    "drawdown_deepen_rate_lift": float(selected["next_drawdown_deepens"].mean() - base_deepen_rate),
                    "bad_window_row_ratio": float(selected["in_bad_window"].mean()),
                    "candidate_rule_viable": bool(
                        net_sum < 0
                        and loss_share > gain_share * 1.5
                        and selected["next_drawdown_deepens"].mean() > base_deepen_rate + 0.05
                    ),
                }
            )
    return pd.DataFrame(rows)


def build_bad_window_summary(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    bad = panel[panel["in_bad_window"]].copy()
    other = panel[~panel["in_bad_window"]].copy()
    for factor, meta in FACTOR_DEFINITIONS.items():
        if bad.empty or other.empty:
            continue
        bad_values = pd.to_numeric(bad[factor], errors="coerce").dropna()
        other_values = pd.to_numeric(other[factor], errors="coerce").dropna()
        if bad_values.empty or other_values.empty:
            continue
        p80 = float(panel[factor].quantile(0.80))
        p90 = float(panel[factor].quantile(0.90))
        rows.append(
            {
                "factor": factor,
                "factor_label": meta["label"],
                "bad_window_rows": int(len(bad_values)),
                "other_rows": int(len(other_values)),
                "bad_window_median": float(bad_values.median()),
                "other_median": float(other_values.median()),
                "median_lift": float(bad_values.median() - other_values.median()),
                "bad_window_top20_ratio": float((bad_values >= p80).mean()),
                "other_top20_ratio": float((other_values >= p80).mean()),
                "bad_window_top10_ratio": float((bad_values >= p90).mean()),
                "other_top10_ratio": float((other_values >= p90).mean()),
            }
        )
    return pd.DataFrame(rows)


def make_decision(gate_summary: pd.DataFrame) -> dict[str, Any]:
    viable = gate_summary[gate_summary["candidate_rule_viable"].astype(bool)].copy()
    if viable.empty:
        return {
            "stage": STAGE,
            "decision": "stage093_no_exposure_state_rule_candidate",
            "candidate_rule_count": 0,
            "best_candidate": "",
            "promote_to_true_engine": False,
            "next_step": "不要直接做高保证金/活跃合约/回撤深度硬 gate；若继续，先做逐合约真实持仓贡献分解或转独立收益腿。",
            "strategy_changed": False,
            "true_engine_run": False,
            "order_api_calls": 0,
            "ctp_connected": False,
            "overfit_after": "否。只读预测力审计，没有按坏窗口调阈值。",
            "continue_after": "有但需换层",
            "continue_reason": "日级聚合暴露状态不足以生成规则；下一步应下钻到逐合约贡献或外生低相关收益腿。",
        }
    viable = viable.sort_values(["loss_minus_gain_share", "drawdown_deepen_rate_lift"], ascending=[False, False])
    best = viable.iloc[0]
    return {
        "stage": STAGE,
        "decision": "stage093_exposure_state_rule_candidate_for_proxy",
        "candidate_rule_count": int(len(viable)),
        "best_candidate": f"{best['factor']}:{best['tail']}",
        "promote_to_true_engine": False,
        "next_step": "先做该因子的曲线级 no-lookahead proxy；只有 proxy 通过才允许 true engine。",
        "strategy_changed": False,
        "true_engine_run": False,
        "order_api_calls": 0,
        "ctp_connected": False,
        "overfit_after": "基本否。候选来自预声明 top10/top20，而非小数阈值。",
        "continue_after": "有",
        "continue_reason": "至少一个聚合暴露状态满足亏损捕获大于收益牺牲的预声明闸门。",
    }


def write_report(
    factor_summary: pd.DataFrame,
    gate_summary: pd.DataFrame,
    bad_window_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    research_rows = "\n".join(
        f"| {item['source']} | {item['url']} | {item['finding']} |" for item in EXTERNAL_RESEARCH
    )
    top_gate = gate_summary.sort_values(
        ["candidate_rule_viable", "loss_minus_gain_share", "drawdown_deepen_rate_lift"],
        ascending=[False, False, False],
    )
    report = f"""# {STAGE} Exposure State Predictive Audit

## 外部调研与判断

| source | url | finding |
| --- | --- | --- |
{research_rows}

我的判断：暴露治理只有在“事前可见状态”稳定捕获亏损且少牺牲右尾时才有价值。趋势系统的高暴露经常也是右尾来源，所以本阶段只做预测力审计，不直接上规则。

## Top State Gate Summary

{_md_table(top_gate, 80)}

## Factor Bucket Summary

{_md_table(factor_summary, 80)}

## Bad Window Factor Summary

{_md_table(bad_window_summary)}

## 决策

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## 过拟合反思

- 运行前：否。因子来自已有日级账户/暴露状态，不按坏窗口增加新品种或新阈值。
- 运行后：见决策。如果没有候选，不继续扫 `top15/top25` 或小数阈值。

## 继续价值反思

- 运行前：有。Stage086 指出坏窗口更像持仓/暴露压力问题，需要先做预测力审计。
- 运行后：见决策。聚合状态若不够，应下钻逐合约贡献或转低相关收益腿。

## 输出

- panel：`{PANEL_PATH}`
- factor_summary：`{FACTOR_SUMMARY_PATH}`
- gate_summary：`{GATE_SUMMARY_PATH}`
- bad_window_summary：`{BAD_WINDOW_PATH}`
- input_audit：`{INPUT_AUDIT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def write_stage_record(
    factor_summary: pd.DataFrame,
    gate_summary: pd.DataFrame,
    bad_window_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> Path:
    now = datetime.now()
    stage_path = STAGES_DIR / f"{now:%Y%m%d_%H%M}_stage093_exposure_state_predictive_audit.md"
    top_gate = gate_summary.sort_values(
        ["candidate_rule_viable", "loss_minus_gain_share", "drawdown_deepen_rate_lift"],
        ascending=[False, False, False],
    )
    text = f"""# Stage093 暴露状态预测力审计

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{now:%Y-%m-%d %H:%M} CST
- 工作区/分支：`{ROOT}`
- 阶段性质：只读暴露状态预测力审计
- 是否重要突破：否
- 是否触发A/B：否，本阶段不提出可合入候选

## 外部调研与判断

- 参考资料：CTA risk management、trend following diversification/risk management、CTA position sizing。
- 我的判断：暴露治理要从事前状态和亏损/右尾权衡出发；如果高暴露同时承担右尾，就不能按坏窗口硬切。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage093_exposure_state_predictive_audit.py`
- 修改脚本：无正式交易入口修改。
- 删除脚本：无。
- 新增参数：预声明 top10/top20 状态审计；不新增交易参数。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：Stage167 正式 C9/15w 多起点曲线，统一终点 `2026-06-30`。
- 账户规模：`150,000`
- 样本过滤：`2020-01` 至 `2026-01` 逐半年起点。
- 审计口径：用当日可见暴露/账户状态预测下一交易日 `net_pnl`、回撤是否加深；不前视，不生成订单。
- 坏窗口标记：`2022-07-15` 至 `2023-07-05`，仅用于解释，不用于阈值选择。

## Top State Gate Summary

{_md_table(top_gate, 80)}

## Factor Bucket Summary

{_md_table(factor_summary, 80)}

## Bad Window Factor Summary

{_md_table(bad_window_summary)}

## 结论

- 本阶段结论：`{decision['decision']}`。
- 是否进入下一步：`{decision['promote_to_true_engine']}`。
- 下一步：{decision['next_step']}

## 回测记录字段

- 本阶段不新增交易回测，因此无新增期末权益、总收益、最大回撤、Sharpe、滑点、交易次数或胜率；只读使用 Stage167 日线曲线。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：{decision['overfit_after']}
- 原因：因子和 top10/top20 审计预先固定；不按坏窗口调小数阈值。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：{decision['continue_after']}
- 原因：{decision['continue_reason']}

## 合入建议

- 是否更新本线 `LINE.md`：否，等独立 agent 审查。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段无重要突破。
"""
    stage_path.write_text(text, encoding="utf-8")
    return stage_path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    curves = load_curves()
    panel = build_panel(curves)
    factor_summary = build_factor_bucket_summary(panel)
    gate_summary = build_top_state_gate_summary(panel)
    bad_window_summary = build_bad_window_summary(panel)
    input_audit = _input_audit([STAGE167_CURVES])
    decision = make_decision(gate_summary)

    panel.to_csv(PANEL_PATH, index=False, encoding="utf-8-sig")
    factor_summary.to_csv(FACTOR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    gate_summary.to_csv(GATE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    bad_window_summary.to_csv(BAD_WINDOW_PATH, index=False, encoding="utf-8-sig")
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(factor_summary, gate_summary, bad_window_summary, decision)
    stage_path = write_stage_record(factor_summary, gate_summary, bad_window_summary, decision)

    print(
        json.dumps(
            _json_safe({"decision": decision, "stage_path": stage_path, "report_path": REPORT_PATH}),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
