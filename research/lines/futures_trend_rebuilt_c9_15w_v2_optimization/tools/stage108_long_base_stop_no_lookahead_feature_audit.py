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
STAGE = "Stage108"
MODEL_TAG = "stage108_long_base_stop_no_lookahead_feature_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage108_long_base_stop_no_lookahead_feature_audit"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage108_long_base_stop_no_lookahead_feature_audit"
STAGES_DIR = LINE_DIR / "stages"

STAGE096_OUT = LINE_DIR / "outputs" / "stage096_position_concentration_predictive_audit"
STAGE096_PREFIX = "rebuilt_c9_v2_stage096_position_concentration_predictive_audit"
STAGE096_TAG = "stage096_position_concentration_predictive_audit_v1"
POSITIONS_PATH = STAGE096_OUT / f"{STAGE096_PREFIX}_positions_{STAGE096_TAG}.csv.gz"

STAGE107_OUT = LINE_DIR / "outputs" / "stage107_long_base_stop_post_exit_continuation_audit"
STAGE107_PREFIX = "rebuilt_c9_v2_stage107_long_base_stop_post_exit_continuation_audit"
STAGE107_TAG = "stage107_long_base_stop_post_exit_continuation_audit_v2_reviewed_representative_sensitivity"
STAGE107_PANEL_PATH = STAGE107_OUT / f"{STAGE107_PREFIX}_event_panel_{STAGE107_TAG}.csv.gz"
STAGE107_DECISION_PATH = STAGE107_OUT / f"{STAGE107_PREFIX}_decision_{STAGE107_TAG}.json"

EVENT_FEATURE_PATH = OUT / f"{OUTPUT_PREFIX}_event_features_{MODEL_TAG}.csv.gz"
SIGNAL_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_signal_summary_{MODEL_TAG}.csv"
BY_START_SIGNAL_PATH = OUT / f"{OUTPUT_PREFIX}_by_start_signal_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

MAIN_HORIZON = 3

EXTERNAL_RESEARCH = [
    {
        "source": "Backtrader Stop Trading examples",
        "url": "https://www.backtrader.com/blog/posts/2018-02-01-stop-trading/stop-trading/",
        "finding": "Stop logic must be evaluated as executable order/path semantics, not only post-exit opportunity.",
    },
    {
        "source": "Rob Carver, Dynamic trend following",
        "url": "https://qoppac.blogspot.com/2020/12/dynamic-trend-following.html",
        "finding": "Trend exits can damage right-tail capture; changes need robust path tests, not single-window fixes.",
    },
    {
        "source": "pysystemtrade backtesting documentation",
        "url": "https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md",
        "finding": "Separate trading rule, position, accounting and attribution before promotion.",
    },
]

SIGNAL_DEFINITIONS = {
    "pretrend_positive": "退出前一日收盘在 MA20 上方，MA20 五日前向上，且退出前 20 日收益为正。",
    "exit_close_above_ma20_prev": "触发日收盘仍在退出前 MA20 上方。",
    "mild_exit_shock": "触发日 close-to-close 跌幅不超过 1.5 个退出前 20 日波动。",
    "whipsaw_core": "pretrend_positive + exit_close_above_ma20_prev + mild_exit_shock。",
    "profitable_base_stop": "base_stop 平仓本身仍为正收益，说明更像保护利润后的回撤。",
    "profitable_pretrend": "profitable_base_stop + pretrend_positive。",
    "not_deep_loss": "base_stop 平仓 R 倍数大于 -1，不是深亏止损。",
    "quality_rank_top8": "入场时 AI rank 在 1-8。",
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


def _numeric(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column in frame.columns:
        return pd.to_numeric(frame[column], errors="coerce")
    return pd.Series(default, index=frame.index, dtype=float)


def _safe_div(numerator: float, denominator: float) -> float:
    if not np.isfinite(numerator) or not np.isfinite(denominator) or abs(denominator) < 1e-12:
        return np.nan
    return float(numerator / denominator)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    decision = json.loads(STAGE107_DECISION_PATH.read_text(encoding="utf-8"))
    if decision.get("decision") != "stage107_long_base_stop_post_exit_positive_but_representative_sensitive_followup_only":
        raise ValueError(f"Unexpected Stage107 decision: {decision.get('decision')}")
    panel = pd.read_csv(STAGE107_PANEL_PATH, encoding="utf-8-sig")
    prices = pd.read_csv(
        POSITIONS_PATH,
        usecols=["requested_start_month", "vt_symbol", "date", "close_price", "pre_close"],
        encoding="utf-8-sig",
    )
    panel = panel[panel["horizon_days"].eq(MAIN_HORIZON) & panel["has_future_price"].astype(bool)].copy()
    panel["exit_date"] = pd.to_datetime(panel["exit_date"], errors="coerce").dt.normalize()
    panel["entry_date"] = pd.to_datetime(panel["entry_date"], errors="coerce").dt.normalize()
    panel["future_date"] = pd.to_datetime(panel["future_date"], errors="coerce").dt.normalize()
    panel["requested_start_month"] = panel["requested_start_month"].astype(str)
    panel["vt_symbol"] = panel["vt_symbol"].astype(str)
    for column in [
        "entry_price",
        "exit_price",
        "exit_close_price",
        "future_close_price",
        "volume",
        "size",
        "realized_pnl",
        "r_multiple",
        "holding_calendar_days",
        "ai_product_pool_rank",
        "rsi_value",
        "portfolio_drawdown_pct",
        "active_positions_before",
        "post_exit_continuation_pnl",
        "post_exit_continuation_pnl_from_exit_close",
    ]:
        panel[column] = _numeric(panel, column)

    prices["date"] = pd.to_datetime(prices["date"], errors="coerce").dt.normalize()
    prices["requested_start_month"] = prices["requested_start_month"].astype(str)
    prices["vt_symbol"] = prices["vt_symbol"].astype(str)
    prices["close_price"] = _numeric(prices, "close_price")
    prices["pre_close"] = _numeric(prices, "pre_close")
    prices = prices.dropna(subset=["date", "close_price"]).copy()
    prices = prices.drop_duplicates(["requested_start_month", "vt_symbol", "date"])
    return panel, prices, decision


def build_price_features(prices: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for (_start, _symbol), group in prices.groupby(["requested_start_month", "vt_symbol"], sort=False):
        data = group.sort_values("date").copy()
        data["prev_close_calc"] = data["close_price"].shift(1)
        data["prev_close"] = data["pre_close"].where(data["pre_close"].gt(0), data["prev_close_calc"])
        data["ret1"] = data["close_price"].div(data["prev_close"]).sub(1.0)
        ma5 = data["close_price"].rolling(5, min_periods=5).mean()
        ma20 = data["close_price"].rolling(20, min_periods=20).mean()
        data["ma5_prev"] = ma5.shift(1)
        data["ma20_prev"] = ma20.shift(1)
        data["ma20_prev_5ago"] = ma20.shift(6)
        data["ma20_slope5_prev"] = data["ma20_prev"].div(data["ma20_prev_5ago"]).sub(1.0)
        data["ret5_prev"] = data["close_price"].shift(1).div(data["close_price"].shift(6)).sub(1.0)
        data["ret20_prev"] = data["close_price"].shift(1).div(data["close_price"].shift(21)).sub(1.0)
        data["vol20_prev"] = data["ret1"].rolling(20, min_periods=10).std().shift(1)
        data["exit_ret_z"] = data["ret1"].div(data["vol20_prev"])
        data["exit_close_vs_ma20_prev"] = data["close_price"].div(data["ma20_prev"]).sub(1.0)
        data["prev_close_vs_ma20_prev"] = data["prev_close"].div(data["ma20_prev"]).sub(1.0)
        frames.append(data)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def build_event_features(panel: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    price_features = build_price_features(prices)
    feature_cols = [
        "requested_start_month",
        "vt_symbol",
        "date",
        "close_price",
        "prev_close",
        "ret1",
        "ma5_prev",
        "ma20_prev",
        "ma20_slope5_prev",
        "ret5_prev",
        "ret20_prev",
        "vol20_prev",
        "exit_ret_z",
        "exit_close_vs_ma20_prev",
        "prev_close_vs_ma20_prev",
    ]
    data = panel.merge(
        price_features[feature_cols].rename(columns={"date": "exit_date", "close_price": "stage096_exit_close_price"}),
        on=["requested_start_month", "vt_symbol", "exit_date"],
        how="left",
        validate="many_to_one",
    )
    if int(data["stage096_exit_close_price"].isna().sum()):
        raise ValueError("Stage108 missing exit-day price features")
    data["pretrend_positive"] = (
        data["prev_close_vs_ma20_prev"].gt(0.0)
        & data["ma20_slope5_prev"].gt(0.0)
        & data["ret20_prev"].gt(0.0)
    )
    data["exit_close_above_ma20_prev"] = data["exit_close_vs_ma20_prev"].ge(0.0)
    data["mild_exit_shock"] = data["exit_ret_z"].ge(-1.5)
    data["whipsaw_core"] = (
        data["pretrend_positive"] & data["exit_close_above_ma20_prev"] & data["mild_exit_shock"]
    )
    data["profitable_base_stop"] = data["realized_pnl"].gt(0.0)
    data["profitable_pretrend"] = data["profitable_base_stop"] & data["pretrend_positive"]
    data["not_deep_loss"] = data["r_multiple"].gt(-1.0)
    data["quality_rank_top8"] = data["ai_product_pool_rank"].between(1, 8, inclusive="both")
    data["h3_help_exit_close"] = data["post_exit_continuation_pnl_from_exit_close"].gt(0.0)
    data["h3_help_actual_fill"] = data["post_exit_continuation_pnl"].gt(0.0)
    return data


def representative_sensitivity(data: pd.DataFrame, value_col: str) -> dict[str, float | int]:
    if data.empty:
        return {
            f"{value_col}_first_start_representative_sum": 0.0,
            f"{value_col}_last_start_representative_sum": 0.0,
            f"{value_col}_min_representative_sum": 0.0,
            f"{value_col}_max_representative_sum": 0.0,
            f"{value_col}_mean_per_physical_key_sum": 0.0,
        }
    ordered = data.sort_values(["physical_event_key", "requested_start_month"]).copy()
    by_key = ordered.groupby("physical_event_key")[value_col]
    return {
        f"{value_col}_first_start_representative_sum": float(by_key.first().sum()),
        f"{value_col}_last_start_representative_sum": float(by_key.last().sum()),
        f"{value_col}_min_representative_sum": float(by_key.min().sum()),
        f"{value_col}_max_representative_sum": float(by_key.max().sum()),
        f"{value_col}_mean_per_physical_key_sum": float(by_key.mean().sum()),
    }


def summarize_slice(data: pd.DataFrame, signal_name: str, selected_value: bool) -> dict[str, Any]:
    selected = data[data[signal_name].astype(bool).eq(selected_value)].copy()
    pnl_actual = selected["post_exit_continuation_pnl"]
    pnl_close = selected["post_exit_continuation_pnl_from_exit_close"]
    by_start_close = selected.groupby("requested_start_month")["post_exit_continuation_pnl_from_exit_close"].sum()
    positive_close = float(pnl_close[pnl_close.gt(0.0)].sum()) if len(pnl_close) else 0.0
    negative_close_abs = float(-pnl_close[pnl_close.lt(0.0)].sum()) if len(pnl_close) else 0.0
    top_positive_close = float(pnl_close.max()) if len(pnl_close) else np.nan
    row = {
        "signal_name": signal_name,
        "signal_definition": SIGNAL_DEFINITIONS.get(signal_name, ""),
        "selected_value": bool(selected_value),
        "events": int(len(selected)),
        "start_count": int(selected["requested_start_month"].nunique()) if len(selected) else 0,
        "unique_physical_events": int(selected["physical_event_key"].nunique()) if len(selected) else 0,
        "symbol_count": int(selected["vt_symbol"].nunique()) if len(selected) else 0,
        "actual_fill_pnl_sum": float(pnl_actual.sum()) if len(pnl_actual) else 0.0,
        "exit_close_pnl_sum": float(pnl_close.sum()) if len(pnl_close) else 0.0,
        "exit_close_positive_sum": positive_close,
        "exit_close_negative_abs_sum": negative_close_abs,
        "exit_close_negative_to_positive": _safe_div(negative_close_abs, positive_close),
        "help_rate_exit_close": float(selected["h3_help_exit_close"].mean()) if len(selected) else np.nan,
        "help_rate_actual_fill": float(selected["h3_help_actual_fill"].mean()) if len(selected) else np.nan,
        "positive_start_count": int(by_start_close.gt(0.0).sum()) if len(by_start_close) else 0,
        "positive_start_rate": _safe_div(float(by_start_close.gt(0.0).sum()), float(len(by_start_close))),
        "start_pnl_min": float(by_start_close.min()) if len(by_start_close) else np.nan,
        "start_pnl_median": float(by_start_close.median()) if len(by_start_close) else np.nan,
        "start_pnl_max": float(by_start_close.max()) if len(by_start_close) else np.nan,
        "top_event_positive_share": _safe_div(top_positive_close, positive_close) if positive_close > 0 else np.nan,
        "mean_exit_ret_z": float(selected["exit_ret_z"].mean()) if len(selected) else np.nan,
        "mean_ret20_prev": float(selected["ret20_prev"].mean()) if len(selected) else np.nan,
        "mean_exit_close_vs_ma20_prev": float(selected["exit_close_vs_ma20_prev"].mean()) if len(selected) else np.nan,
    }
    row.update(representative_sensitivity(selected, "exit_close_pnl_sum_proxy"))
    return row


def build_signal_summary(events: pd.DataFrame) -> pd.DataFrame:
    data = events.copy()
    data["exit_close_pnl_sum_proxy"] = data["post_exit_continuation_pnl_from_exit_close"]
    rows: list[dict[str, Any]] = []
    for signal in SIGNAL_DEFINITIONS:
        rows.append(summarize_slice(data, signal, True))
        rows.append(summarize_slice(data, signal, False))
    summary = pd.DataFrame(rows)
    true_rows = summary[summary["selected_value"].eq(True)].copy()
    all_close_sum = float(data["post_exit_continuation_pnl_from_exit_close"].sum())
    true_rows["share_of_all_exit_close_pnl"] = true_rows["exit_close_pnl_sum"].map(
        lambda value: _safe_div(float(value), all_close_sum)
    )
    gate = (
        true_rows["events"].ge(40)
        & true_rows["start_count"].ge(8)
        & true_rows["unique_physical_events"].ge(20)
        & true_rows["exit_close_pnl_sum"].ge(1_000_000.0)
        & true_rows["positive_start_rate"].ge(0.70)
        & true_rows["exit_close_negative_to_positive"].le(0.60)
        & true_rows["top_event_positive_share"].le(0.35)
        & true_rows["exit_close_pnl_sum_proxy_min_representative_sum"].ge(0.0)
    )
    true_rows["mechanism_gate_pass"] = gate.fillna(False)
    false_rows = summary[summary["selected_value"].eq(False)].copy()
    false_rows["share_of_all_exit_close_pnl"] = np.nan
    false_rows["mechanism_gate_pass"] = False
    result = pd.concat([true_rows, false_rows], ignore_index=True, sort=False)
    return result.sort_values(["selected_value", "exit_close_pnl_sum"], ascending=[False, False])


def build_by_start_signal(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for signal in SIGNAL_DEFINITIONS:
        for (start, selected_value), group in events.groupby(["requested_start_month", signal], dropna=False):
            pnl_close = group["post_exit_continuation_pnl_from_exit_close"]
            rows.append(
                {
                    "signal_name": signal,
                    "requested_start_month": start,
                    "selected_value": bool(selected_value),
                    "events": int(len(group)),
                    "exit_close_pnl_sum": float(pnl_close.sum()),
                    "help_rate_exit_close": float(group["h3_help_exit_close"].mean()) if len(group) else np.nan,
                    "symbol_count": int(group["vt_symbol"].nunique()) if len(group) else 0,
                }
            )
    return pd.DataFrame(rows).sort_values(["signal_name", "requested_start_month", "selected_value"])


def make_decision(events: pd.DataFrame, signal_summary: pd.DataFrame, stage107_decision: dict[str, Any]) -> dict[str, Any]:
    candidates = signal_summary[
        signal_summary["selected_value"].eq(True) & signal_summary["mechanism_gate_pass"].astype(bool)
    ].copy()
    candidates = candidates.sort_values("exit_close_pnl_sum", ascending=False)
    best = candidates.iloc[0].to_dict() if not candidates.empty else {}
    if not candidates.empty:
        decision = "stage108_no_lookahead_feature_feasible_for_predeclared_ab"
        next_step = (
            "必须先预声明 A/B/C，再做一个最小真实引擎候选；不得调整本阶段阈值或叠加新条件。"
        )
        continue_after = "有"
        continue_reason = "存在固定无前视特征通过 exit-close 宽样本闸门，可进入严格 A/B 预声明。"
        overfit_after = "否但风险升高。特征族预声明且阈值固定；下一步必须只验证最优通过项，不能救参。"
    else:
        decision = "stage108_no_lookahead_feature_not_sufficient_for_base_stop_delay"
        next_step = "停止把 long_base_stop 后延续收益直接转成延迟退出规则；转回账户层或外生信息源。"
        continue_after = "有但不沿 base_stop 延迟"
        continue_reason = "post-exit 有恢复，但当前无前视状态无法稳定识别可等待事件。"
        overfit_after = "否。固定特征族没有通过宽样本与代表值闸门，按预设停止。"
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "stage107_decision": str(stage107_decision.get("decision", "")),
        "candidate_rule_count": int(len(candidates)),
        "best_candidate_signal": str(best.get("signal_name", "")),
        "best_candidate_exit_close_pnl_sum": float(best.get("exit_close_pnl_sum", 0.0) or 0.0),
        "best_candidate_events": int(best.get("events", 0) or 0),
        "best_candidate_start_count": int(best.get("start_count", 0) or 0),
        "main_horizon": MAIN_HORIZON,
        "event_rows": int(len(events)),
        "start_count": int(events["requested_start_month"].nunique()) if len(events) else 0,
        "unique_physical_events": int(events["physical_event_key"].nunique()) if len(events) else 0,
        "all_exit_close_pnl_sum": float(events["post_exit_continuation_pnl_from_exit_close"].sum()),
        "all_actual_fill_pnl_sum": float(events["post_exit_continuation_pnl"].sum()),
        "predeclared_signal_count": int(len(SIGNAL_DEFINITIONS)),
        "promote_to_proxy": False,
        "promote_to_true_engine": False,
        "strategy_changed": False,
        "true_engine_run": False,
        "order_api_calls": 0,
        "ctp_connected": False,
        "next_step": next_step,
        "overfit_after": overfit_after,
        "continue_after": continue_after,
        "continue_reason": continue_reason,
    }


def write_report(events: pd.DataFrame, signal_summary: pd.DataFrame, by_start: pd.DataFrame, decision: dict[str, Any]) -> None:
    research_rows = "\n".join(
        f"| {item['source']} | {item['url']} | {item['finding']} |" for item in EXTERNAL_RESEARCH
    )
    signal_rows = "\n".join(f"| `{name}` | {desc} |" for name, desc in SIGNAL_DEFINITIONS.items())
    report = f"""# {STAGE} Long Base Stop No-Lookahead Feature Audit

## 外部调研与判断

| source | url | finding |
| --- | --- | --- |
{research_rows}

我的判断：Stage107 证明了 long_base_stop 后存在恢复机会，但它是事后路径。Stage108 只检验触发当日收盘时已经可见的状态是否足以识别 whipsaw；不能把 post-exit 3 日收益直接改成延迟退出。

## 预声明状态

| signal | definition |
| --- | --- |
{signal_rows}

## Decision

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## Signal Summary

{_md_table(signal_summary, 80)}

## By Start Signal

{_md_table(by_start, 160)}

## Event Feature Sample

{_md_table(events.head(80), 80)}

## 统计口径

- 样本：Stage107 v2 主 horizon `3` 的 `long_base_stop` 事件。
- 标签：`post_exit_continuation_pnl_from_exit_close` 为主标签，因为真实“延迟退出”只能从触发日收盘后评估；`post_exit_continuation_pnl` 只作实际成交价机会参考。
- 特征：只使用触发日及触发日前价格、入场时已有字段、持仓到触发日已经可知的路径字段；不使用 future close 以外的未来信息构造信号。
- 闸门：事件数 `>=40`、起点数 `>=8`、物理事件 `>=20`、exit-close PnL `>=1,000,000`、正起点率 `>=70%`、负/正损益比 `<=0.60`、单事件正贡献 `<=35%`、min representative 非负。

## 过拟合反思

- 运行前：否。特征族和阈值在运行前固定，目标是机制可行性，不是救参。
- 运行后：{decision['overfit_after']}

## 继续价值反思

- 运行前：有。它决定 Stage107 是否能从事后机会降维成可执行状态。
- 运行后：{decision['continue_after']}。{decision['continue_reason']}

## 输出

- event_features：`{EVENT_FEATURE_PATH}`
- signal_summary：`{SIGNAL_SUMMARY_PATH}`
- by_start_signal：`{BY_START_SIGNAL_PATH}`
- input_audit：`{INPUT_AUDIT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def write_stage_record(events: pd.DataFrame, signal_summary: pd.DataFrame, by_start: pd.DataFrame, decision: dict[str, Any]) -> Path:
    now = datetime.now()
    path = STAGES_DIR / f"{now:%Y%m%d_%H%M}_stage108_long_base_stop_no_lookahead_feature_audit.md"
    text = f"""# Stage108 long_base_stop 无前视状态可行性审计

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{now:%Y-%m-%d %H:%M} CST
- 工作区：`{ROOT}`
- 阶段性质：只读 no-lookahead feature audit；不改策略、不跑 true engine
- 是否重要突破：{'待复核；有固定特征通过机制闸门' if decision['candidate_rule_count'] else '否；未发现足够稳定的无前视识别条件'}
- 是否触发A/B：否，本阶段不是可合入策略；若后续进入真实引擎，已读取 `skills/version-ab-experiment/SKILL.md`

## 外部调研与判断

- 参考资料：Backtrader stop trading、Rob Carver dynamic trend following、pysystemtrade backtesting docs。
- 我的判断：Stage107 是事后机会，Stage108 必须回答触发日当时能不能识别 whipsaw。若不能，就停止 base_stop 延迟退出路线。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage108_long_base_stop_no_lookahead_feature_audit.py`
- 修改脚本：无正式交易入口修改。
- 删除脚本：无。
- 新增参数：主 horizon `{MAIN_HORIZON}`；预声明状态 `{list(SIGNAL_DEFINITIONS)}`；机制闸门固定为事件数/起点数/物理事件/exit-close PnL/正起点率/负正比/单事件占比/min representative。
- 修改参数：无正式策略参数。
- 删除参数：无。

## 审计参数

- Stage107 event panel：`{STAGE107_PANEL_PATH}`
- Stage107 decision：`{decision['stage107_decision']}`
- Stage096 positions：`{POSITIONS_PATH}`
- true engine：未运行。
- 订单 API：`0`
- CTP：未连接。

## 结果摘要

- 决策：`{decision['decision']}`
- 候选规则数：`{decision['candidate_rule_count']}`
- 最佳候选信号：`{decision['best_candidate_signal'] or '无'}`
- event rows：`{decision['event_rows']}`
- 起点数：`{decision['start_count']}`
- 物理事件数：`{decision['unique_physical_events']}`
- 全样本 exit-close continuation：`{decision['all_exit_close_pnl_sum']:,.2f}`
- 全样本 actual-fill continuation：`{decision['all_actual_fill_pnl_sum']:,.2f}`
- 预声明状态数：`{decision['predeclared_signal_count']}`

## Signal Summary

{_md_table(signal_summary, 80)}

## By Start Signal

{_md_table(by_start, 160)}

## 标准回测指标

- 期末权益：不适用，本阶段只读归因未重跑策略。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 决策

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## 后续规划和 TODO

- {decision['next_step']}

## 过拟合反思

- 运行前：否，预声明状态和闸门固定，不扫产品、方向、日期或小数阈值。
- 运行后：{decision['overfit_after']}

## 继续价值反思

- 运行前：有，判断 base_stop 事后恢复是否能转成当时可执行状态。
- 运行后：{decision['continue_after']}。{decision['continue_reason']}

## 输出

- 报告：`{REPORT_PATH}`
- event_features：`{EVENT_FEATURE_PATH}`
- signal_summary：`{SIGNAL_SUMMARY_PATH}`
- by_start_signal：`{BY_START_SIGNAL_PATH}`
- input_audit：`{INPUT_AUDIT_PATH}`
"""
    path.write_text(text, encoding="utf-8")
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    input_audit = _input_audit([STAGE107_PANEL_PATH, STAGE107_DECISION_PATH, POSITIONS_PATH])
    if not bool(input_audit["exists"].all()):
        raise FileNotFoundError("Stage108 input missing")
    panel, prices, stage107_decision = load_inputs()
    events = build_event_features(panel, prices)
    signal_summary = build_signal_summary(events)
    by_start = build_by_start_signal(events)
    decision = make_decision(events, signal_summary, stage107_decision)

    events.to_csv(EVENT_FEATURE_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    signal_summary.to_csv(SIGNAL_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    by_start.to_csv(BY_START_SIGNAL_PATH, index=False, encoding="utf-8-sig")
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(events, signal_summary, by_start, decision)
    stage_path = write_stage_record(events, signal_summary, by_start, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"[stage108] report={REPORT_PATH}")
    print(f"[stage108] stage_record={stage_path}")


if __name__ == "__main__":
    main()
