from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage092"
MODEL_TAG = "stage092_margin_pressure_cap_proxy_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage092_margin_pressure_cap_proxy"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage092_margin_pressure_cap_proxy"
STAGES_DIR = LINE_DIR / "stages"

BACKTEST_OUT = ROOT / "examples" / "portfolio_backtesting" / "backtest_outputs"
STAGE167_CURVES = BACKTEST_OUT / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_curves_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv"

CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
PER_START_PATH = OUT / f"{OUTPUT_PREFIX}_per_start_summary_{MODEL_TAG}.csv"
VARIANT_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.csv"
RETENTION_PATH = OUT / f"{OUTPUT_PREFIX}_retention_vs_official_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
CHART_RETURN_DD_PATH = OUT / f"{OUTPUT_PREFIX}_return_dd_by_start_{MODEL_TAG}.png"
CHART_UNDERWATER_PATH = OUT / f"{OUTPUT_PREFIX}_underwater_by_start_{MODEL_TAG}.png"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

BASE_CAPITAL = 150_000.0
FOCUS_START_MIN = "2020-01"
REQUESTED_END = pd.Timestamp("2026-06-30")

VARIANT_SPECS = {
    "official_c9_15w_reference": {"label": "Official C9 15w", "cap": None},
    "broker10_cap80_proxy": {"label": "Broker10 cap 80 proxy", "cap": 80.0},
    "broker10_cap70_proxy": {"label": "Broker10 cap 70 proxy", "cap": 70.0},
    "broker10_cap60_proxy": {"label": "Broker10 cap 60 proxy", "cap": 60.0},
}

EXTERNAL_RESEARCH = [
    {
        "source": "UBS managed futures trend following guide",
        "url": "https://us-fund.ubs.com/doc/0FAF4CB8-A5AB-4ABD-A928-8871779E05F9",
        "finding": "Trend following strategies are commonly calibrated to target volatility/risk; investors choose allocation based on risk tolerance.",
    },
    {
        "source": "Quantpedia robust trend-following review",
        "url": "https://quantpedia.com/designing-robust-trend-following-system/",
        "finding": "Robust trend systems emphasize portfolio-level risk budgeting rather than single-window patches.",
    },
    {
        "source": "Alpha Architect conditional volatility targeting note",
        "url": "https://alphaarchitect.com/conditional-volatility-targeting/",
        "finding": "Conditional risk reduction during extreme volatility states is a known risk-management shape, but must be tested for return give-up.",
    },
]


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


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _daily_sharpe(equity: pd.Series) -> float:
    returns = pd.to_numeric(equity, errors="coerce").pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty:
        return 0.0
    std = float(returns.std(ddof=1))
    if std <= 0 or not np.isfinite(std):
        return 0.0
    return float(returns.mean() / std * np.sqrt(252.0))


def _max_consecutive_true(mask: pd.Series) -> int:
    best = 0
    current = 0
    for value in mask.astype(bool).tolist():
        if value:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return int(best)


def load_official_curves() -> pd.DataFrame:
    data = pd.read_csv(STAGE167_CURVES, encoding="utf-8-sig")
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data = data.dropna(subset=["date"])
    data = data[data["date"].le(REQUESTED_END)].copy()
    data["requested_start_month"] = data["requested_start_month"].astype(str)
    numeric_cols = [
        "account_equity",
        "broker10_margin_to_equity_pct",
        "slippage",
        "trade_count",
        "net_pnl",
    ]
    for column in numeric_cols:
        data[column] = pd.to_numeric(data.get(column, 0.0), errors="coerce").fillna(0.0)
    return data.sort_values(["requested_start_month", "date"]).reset_index(drop=True)


def _simulate_cap_proxy(group: pd.DataFrame, cap: float | None) -> pd.DataFrame:
    frame = group.sort_values("date").reset_index(drop=True)
    official_equity = frame["account_equity"].astype(float).to_numpy()
    pressure = frame["broker10_margin_to_equity_pct"].astype(float).to_numpy()
    slippage = frame["slippage"].astype(float).to_numpy()
    trade_count = frame["trade_count"].astype(float).to_numpy()
    if cap is None:
        multiplier = np.ones(len(frame), dtype=float)
        simulated_equity = official_equity.copy()
    else:
        multiplier = np.ones(len(frame), dtype=float)
        simulated_equity = np.empty(len(frame), dtype=float)
        simulated_equity[0] = official_equity[0]
        for idx in range(1, len(frame)):
            prev_pressure = max(0.0, float(pressure[idx - 1]))
            day_multiplier = min(1.0, cap / prev_pressure) if prev_pressure > cap else 1.0
            day_multiplier = max(0.0, float(day_multiplier))
            multiplier[idx] = day_multiplier
            official_delta = float(official_equity[idx] - official_equity[idx - 1])
            simulated_equity[idx] = simulated_equity[idx - 1] + official_delta * day_multiplier
    version = "official_c9_15w_reference" if cap is None else f"broker10_cap{int(cap)}_proxy"
    out = pd.DataFrame(
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "version": version,
            "variant_label": VARIANT_SPECS[version]["label"],
            "requested_start_month": frame["requested_start_month"].iloc[0],
            "date": frame["date"],
            "account_capital": BASE_CAPITAL,
            "account_equity": simulated_equity,
            "official_equity": official_equity,
            "broker10_margin_to_equity_pct": pressure,
            "previous_day_broker10_pressure": pd.Series(pressure).shift(1).fillna(0.0),
            "proxy_multiplier": multiplier,
            "proxy_active": (multiplier < 0.999999).astype(int),
            "proxy_slippage": slippage * multiplier,
            "proxy_trade_count": trade_count,
            "note": "curve-level no-lookahead proxy: previous-day broker10 pressure caps next-day PnL",
        }
    )
    out["nav"] = out["account_equity"] / BASE_CAPITAL
    out["drawdown_pct"] = _drawdown_pct(out["account_equity"])
    return out


def build_curves(official: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for _, group in official.groupby("requested_start_month", sort=True):
        for spec in VARIANT_SPECS.values():
            rows.append(_simulate_cap_proxy(group, spec["cap"]))
    return pd.concat(rows, ignore_index=True)


def summarize_curve(frame: pd.DataFrame) -> dict[str, Any]:
    frame = frame.sort_values("date").reset_index(drop=True)
    equity = pd.to_numeric(frame["account_equity"], errors="coerce").ffill()
    capital = float(frame["account_capital"].iloc[0])
    below = equity < capital - 1e-9
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "version": frame["version"].iloc[0],
        "variant_label": frame["variant_label"].iloc[0],
        "requested_start_month": frame["requested_start_month"].iloc[0],
        "actual_start": frame["date"].iloc[0].date().isoformat(),
        "actual_end": frame["date"].iloc[-1].date().isoformat(),
        "trading_days": int(len(frame)),
        "account_capital": capital,
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / capital - 1.0) * 100.0),
        "max_drawdown_pct": float(_drawdown_pct(equity).min()),
        "sharpe": _daily_sharpe(equity),
        "min_equity": float(equity.min()),
        "days_below_initial": int(below.sum()),
        "max_consecutive_below_initial_days": _max_consecutive_true(below),
        "total_slippage": float(pd.to_numeric(frame["proxy_slippage"], errors="coerce").fillna(0.0).sum()),
        "total_trade_count": float(pd.to_numeric(frame["proxy_trade_count"], errors="coerce").fillna(0.0).sum()),
        "active_days": int(pd.to_numeric(frame["proxy_active"], errors="coerce").fillna(0).sum()),
        "mean_multiplier": float(pd.to_numeric(frame["proxy_multiplier"], errors="coerce").fillna(1.0).mean()),
        "min_multiplier": float(pd.to_numeric(frame["proxy_multiplier"], errors="coerce").fillna(1.0).min()),
        "max_broker10_margin_to_equity_pct": float(pd.to_numeric(frame["broker10_margin_to_equity_pct"], errors="coerce").max()),
    }


def build_summaries(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    per_start = pd.DataFrame(
        [
            summarize_curve(group)
            for _, group in curves.groupby(["version", "requested_start_month"], sort=True)
        ]
    )
    official = per_start[per_start["version"].eq("official_c9_15w_reference")][
        ["requested_start_month", "total_return_pct", "max_drawdown_pct", "days_below_initial", "max_consecutive_below_initial_days"]
    ].rename(
        columns={
            "total_return_pct": "official_return_pct",
            "max_drawdown_pct": "official_max_drawdown_pct",
            "days_below_initial": "official_days_below_initial",
            "max_consecutive_below_initial_days": "official_max_consecutive_below_initial_days",
        }
    )
    retention = per_start.merge(official, on="requested_start_month", how="left")
    retention = retention[~retention["version"].eq("official_c9_15w_reference")].copy()
    retention["return_retention_ratio"] = np.where(
        retention["official_return_pct"].abs() > 1e-12,
        retention["total_return_pct"] / retention["official_return_pct"],
        np.nan,
    )
    retention["drawdown_improvement_pp"] = retention["max_drawdown_pct"] - retention["official_max_drawdown_pct"]
    retention["days_below_delta"] = retention["days_below_initial"] - retention["official_days_below_initial"]
    retention["max_consecutive_below_delta"] = (
        retention["max_consecutive_below_initial_days"] - retention["official_max_consecutive_below_initial_days"]
    )

    rows: list[dict[str, Any]] = []
    for version, group in per_start.groupby("version", sort=False):
        focus = group[group["requested_start_month"].ge(FOCUS_START_MIN)].copy()
        ret_focus = retention[retention["version"].eq(version) & retention["requested_start_month"].ge(FOCUS_START_MIN)]
        if version == "official_c9_15w_reference":
            min_retention = 1.0
            median_retention = 1.0
            passes = False
        else:
            min_retention = float(ret_focus["return_retention_ratio"].min()) if not ret_focus.empty else np.nan
            median_retention = float(ret_focus["return_retention_ratio"].median()) if not ret_focus.empty else np.nan
            official_focus = group[group["version"].eq("official_c9_15w_reference")]
            passes = False
        rows.append(
            {
                "sample": "starts_2020_2026",
                "version": version,
                "variant_label": group["variant_label"].iloc[0],
                "start_count": int(len(focus)),
                "positive_count": int(focus["total_return_pct"].gt(0).sum()),
                "min_return_pct": float(focus["total_return_pct"].min()),
                "median_return_pct": float(focus["total_return_pct"].median()),
                "max_return_pct": float(focus["total_return_pct"].max()),
                "min_return_retention_ratio": min_retention,
                "median_return_retention_ratio": median_retention,
                "worst_drawdown_pct": float(focus["max_drawdown_pct"].min()),
                "median_drawdown_pct": float(focus["max_drawdown_pct"].median()),
                "max_days_below_initial": int(focus["days_below_initial"].max()),
                "median_days_below_initial": float(focus["days_below_initial"].median()),
                "max_consecutive_below_initial_days": int(focus["max_consecutive_below_initial_days"].max()),
                "median_active_days": float(focus["active_days"].median()),
                "min_mean_multiplier": float(focus["mean_multiplier"].min()),
                "total_slippage_sum": float(focus["total_slippage"].sum()),
                "total_trade_count_sum": float(focus["total_trade_count"].sum()),
            }
        )
    variant_summary = pd.DataFrame(rows)
    official_row = variant_summary[variant_summary["version"].eq("official_c9_15w_reference")].iloc[0]
    for idx, row in variant_summary.iterrows():
        if row["version"] == "official_c9_15w_reference":
            variant_summary.loc[idx, "passes_new_goal_vs_official"] = False
            continue
        variant_summary.loc[idx, "passes_new_goal_vs_official"] = bool(
            row["min_return_retention_ratio"] >= 0.5
            and row["worst_drawdown_pct"] > official_row["worst_drawdown_pct"]
            and row["max_days_below_initial"] <= official_row["max_days_below_initial"]
            and row["max_consecutive_below_initial_days"] <= official_row["max_consecutive_below_initial_days"]
        )
    return per_start, variant_summary, retention


def write_charts(per_start: pd.DataFrame) -> None:
    focus = per_start[per_start["requested_start_month"].ge(FOCUS_START_MIN)].copy()
    versions = list(VARIANT_SPECS.keys())

    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True)
    for version in versions:
        data = focus[focus["version"].eq(version)].sort_values("requested_start_month")
        axes[0].plot(data["requested_start_month"], data["total_return_pct"], marker="o", label=VARIANT_SPECS[version]["label"])
        axes[1].plot(data["requested_start_month"], data["max_drawdown_pct"], marker="o", label=VARIANT_SPECS[version]["label"])
    axes[0].set_title("Stage092 return by start")
    axes[0].set_ylabel("total return %")
    axes[0].grid(alpha=0.25)
    axes[1].set_title("Stage092 max drawdown by start")
    axes[1].set_ylabel("max drawdown %")
    axes[1].tick_params(axis="x", rotation=45)
    axes[1].grid(alpha=0.25)
    axes[0].legend(ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(CHART_RETURN_DD_PATH, dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True)
    for version in versions:
        data = focus[focus["version"].eq(version)].sort_values("requested_start_month")
        axes[0].plot(data["requested_start_month"], data["days_below_initial"], marker="o", label=VARIANT_SPECS[version]["label"])
        axes[1].plot(data["requested_start_month"], data["max_consecutive_below_initial_days"], marker="o", label=VARIANT_SPECS[version]["label"])
    axes[0].set_title("Stage092 days below initial")
    axes[0].set_ylabel("days")
    axes[0].grid(alpha=0.25)
    axes[1].set_title("Stage092 max consecutive days below initial")
    axes[1].set_ylabel("days")
    axes[1].tick_params(axis="x", rotation=45)
    axes[1].grid(alpha=0.25)
    axes[0].legend(ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(CHART_UNDERWATER_PATH, dpi=160)
    plt.close(fig)


def write_report(variant_summary: pd.DataFrame, retention: pd.DataFrame, decision: dict[str, Any]) -> None:
    top_retention = retention.sort_values(
        ["version", "requested_start_month"]
    )[
        [
            "requested_start_month",
            "version",
            "return_retention_ratio",
            "drawdown_improvement_pp",
            "days_below_delta",
            "max_consecutive_below_delta",
        ]
    ]
    research_rows = "\n".join(
        f"| {item['source']} | {item['url']} | {item['finding']} |" for item in EXTERNAL_RESEARCH
    )
    report = f"""# {STAGE} Margin Pressure Cap Proxy

## 外部调研与判断

| source | url | finding |
| --- | --- | --- |
{research_rows}

我的判断：组合层风险预算/波动目标是趋势系统常见治理思路，但简单权益回撤刹车已被本线反证。本阶段只测试前一日保证金压力上限这一低自由度代理；若收益保留或水下指标不过，不继续扫阈值。

## 结果汇总

{_md_table(variant_summary)}

## Retention vs Official

{_md_table(top_retention, 60)}

## 决策

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## 过拟合反思

- 运行前：否。只测试固定风险预算上限 `80/70/60`，来自部署风险口径，不按亏损日期或品种调参。
- 运行后：见决策。若没有通过，不继续扫 `65/75/85` 或更复杂组合。

## 继续价值反思

- 运行前：有。Stage086 显示高 broker10 压力参与了最痛窗口，值得先做 proxy 闸门。
- 运行后：取决于是否能同时改善回撤、水下和 50% 收益保留；若只降低收益或拉长水下，则该路线降优先级。

## 输出

- curves：`{CURVES_PATH}`
- per_start：`{PER_START_PATH}`
- variant_summary：`{VARIANT_SUMMARY_PATH}`
- retention：`{RETENTION_PATH}`
- input_audit：`{INPUT_AUDIT_PATH}`
- chart_return_dd：`{CHART_RETURN_DD_PATH}`
- chart_underwater：`{CHART_UNDERWATER_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def write_stage_record(variant_summary: pd.DataFrame, decision: dict[str, Any]) -> Path:
    now = datetime.now()
    stage_path = STAGES_DIR / f"{now:%Y%m%d_%H%M}_stage092_margin_pressure_cap_proxy.md"
    text = f"""# Stage092 保证金压力上限代理

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{now:%Y-%m-%d %H:%M} CST
- 工作区/分支：`{ROOT}`
- 阶段性质：资金/保证金治理曲线级 proxy，A/C 前置筛查
- 是否重要突破：否
- 是否触发A/B：否；已读取 A/B 纪律，但本阶段没有形成可合入候选，仅为正式 A/B 前置筛查

## 外部调研与判断

- 参考资料：UBS managed futures risk targeting、Quantpedia robust trend-following、conditional volatility targeting 资料。
- 我的判断：风险预算/压力上限是结构性思路，但本线已反证简单回撤后刹车；本阶段只筛查前一日保证金压力上限，失败就停止，不按具体坏窗口救参。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage092_margin_pressure_cap_proxy.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`broker10_cap80_proxy`、`broker10_cap70_proxy`、`broker10_cap60_proxy`
- 修改参数：无正式交易参数
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage167 正式 C9/15w 多起点曲线，统一终点 `2026-06-30`。
- 账户规模：`150,000`
- 成本口径：沿用 Stage167 曲线；proxy 按风险缩放日 PnL 与 slippage，不生成真实成交。
- 样本过滤：重点 `2020-01` 至 `2026-01` 逐半年起点。
- 策略/归因口径：前一日 `broker10_margin_to_equity_pct` 超过 cap 时，下一交易日 PnL 乘以 `cap / pressure`；不前视，但不是正式真实引擎。

## 结果

{_md_table(variant_summary)}

## 输出文件

- report：`{REPORT_PATH}`
- summary：`{VARIANT_SUMMARY_PATH}`
- orders：不适用
- daily：`{CURVES_PATH}`
- quality：`{RETENTION_PATH}`

## 结论

- 本阶段结论：`{decision['decision']}`。
- 是否进入下一步：`{decision['promote_to_true_engine']}`。
- 下一步：{decision['next_step']}

## 过拟合反思

- 运行前判断：否。
- 运行后判断：{decision['overfit_after']}
- 原因：固定 3 个粗粒度 cap 做筛查；不按单一坏窗口、品种或日期救参。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：{decision['continue_after']}
- 原因：{decision['continue_reason']}

## 合入建议

- 是否更新本线 `LINE.md`：否，等待独立审查后再决定。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段未形成正式 A/B 候选或重要突破。
"""
    stage_path.write_text(text, encoding="utf-8")
    return stage_path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    official = load_official_curves()
    curves = build_curves(official)
    per_start, variant_summary, retention = build_summaries(curves)
    input_audit = _input_audit([STAGE167_CURVES])

    passing = variant_summary[variant_summary["passes_new_goal_vs_official"].astype(bool)].copy()
    if passing.empty:
        decision = {
            "stage": STAGE,
            "decision": "stage092_margin_pressure_cap_proxy_not_promoted",
            "passing_variant_count": 0,
            "best_candidate": "",
            "promote_to_true_engine": False,
            "next_step": "停止保证金压力 cap proxy 救参，转向真实暴露归因或外生收益腿。",
            "strategy_changed": False,
            "true_engine_run": False,
            "order_api_calls": 0,
            "ctp_connected": False,
            "overfit_after": "否。负结果后不继续扫更细 cap。",
            "continue_after": "有限",
            "continue_reason": "若 proxy 未能同时改善水下、回撤和收益保留，真实引擎优先级不足。",
        }
    else:
        passing = passing.sort_values(["worst_drawdown_pct", "median_return_retention_ratio"], ascending=[False, False])
        best = passing.iloc[0]
        decision = {
            "stage": STAGE,
            "decision": "stage092_margin_pressure_cap_proxy_candidate_for_true_engine",
            "passing_variant_count": int(len(passing)),
            "best_candidate": str(best["version"]),
            "promote_to_true_engine": True,
            "next_step": "实现 best candidate 的真实引擎 A/C，确认整数手、保证金、AI 池和交易成本。",
            "strategy_changed": False,
            "true_engine_run": False,
            "order_api_calls": 0,
            "ctp_connected": False,
            "overfit_after": "基本否。仅允许最优粗粒度 cap 进入真实引擎，不继续扫小数。",
            "continue_after": "有",
            "continue_reason": "proxy 同时满足收益保留、回撤和水下指标，值得真实引擎证伪。",
        }

    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    per_start.to_csv(PER_START_PATH, index=False, encoding="utf-8-sig")
    variant_summary.to_csv(VARIANT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    write_charts(per_start)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(variant_summary, retention, decision)
    stage_path = write_stage_record(variant_summary, decision)

    print(json.dumps(_json_safe({"decision": decision, "stage_path": stage_path, "report_path": REPORT_PATH}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
