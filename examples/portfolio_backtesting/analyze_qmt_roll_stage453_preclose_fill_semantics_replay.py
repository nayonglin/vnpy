from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage450_minute_execution_equity_rebuild as s450  # noqa: E402
import analyze_qmt_roll_stage451_true_path_1455_vwap_replay as s451  # noqa: E402
import analyze_qmt_roll_stage452_iterative_1455_proxy_backfill as s452  # noqa: E402


MODEL_TAG = "stage453_preclose_fill_semantics_replay_v1"
OUTPUT_PREFIX = "qmt_roll_stage453_preclose_fill_semantics_replay"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
BASELINE_VARIANT = "stage079"
RERUN_VARIANT = "stage079_rerun_same_day_close"
MAX_ITERATIONS = 4

DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
USAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_usage_{MODEL_TAG}.csv"
BACKFILL_STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_backfill_status_{MODEL_TAG}.csv"
PROXY_MAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_map_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class ProxySpec:
    variant: str
    label: str
    source_prefix: str
    value_func: Callable[[pd.DataFrame], float]
    deployability_note: str


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
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


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return view.to_markdown(index=False)


def _window_for(vt_symbol: str, date: pd.Timestamp) -> pd.DataFrame:
    bars = s452._load_raw_bars(vt_symbol)
    if bars.empty:
        return pd.DataFrame()
    start = pd.Timestamp(date).normalize() + pd.Timedelta(hours=14, minutes=55)
    end = pd.Timestamp(date).normalize() + pd.Timedelta(hours=15)
    window = bars[(bars["bar_datetime"] >= start) & (bars["bar_datetime"] < end)].copy()
    if window.empty:
        return window
    for column in ["open", "close", "volume"]:
        window[column] = pd.to_numeric(window[column], errors="coerce")
    return window.dropna(subset=["open", "close"]).sort_values("bar_datetime")


def _last5_vwap(window: pd.DataFrame) -> float:
    volume = pd.to_numeric(window["volume"], errors="coerce").fillna(0.0)
    close = pd.to_numeric(window["close"], errors="coerce")
    volume_sum = float(volume.sum())
    return float((close * volume).sum() / volume_sum) if volume_sum > 0 else float(close.mean())


def _first_open(window: pd.DataFrame) -> float:
    return float(window["open"].iloc[0])


def _last_close(window: pd.DataFrame) -> float:
    return float(window["close"].iloc[-1])


SPECS: tuple[ProxySpec, ...] = (
    ProxySpec(
        variant="stage079_true_path_1455_vwap_backfilled_rerun",
        label="Stage079 true path 14:55-14:59 VWAP rerun",
        source_prefix="stage453_1455_last5_vwap",
        value_func=_last5_vwap,
        deployability_note="Stage152 已硬失败；本阶段只作为复核锚点。",
    ),
    ProxySpec(
        variant="stage079_true_path_1455_first_open",
        label="Stage079 true path 14:55 first open",
        source_prefix="stage453_1455_first_open",
        value_func=_first_open,
        deployability_note="若能在14:55前冻结信号，可作为更早的收盘前执行近似。",
    ),
    ProxySpec(
        variant="stage079_true_path_1459_last_close",
        label="Stage079 true path 14:59 last close",
        source_prefix="stage453_1459_last_close",
        value_func=_last_close,
        deployability_note="最接近收盘价，但除非信号能在收盘前冻结，否则只能作为敏感性审计，不可直接部署。",
    ),
)


def _proxy_from_bars(vt_symbol: str, date: pd.Timestamp, spec: ProxySpec) -> dict[str, Any] | None:
    window = _window_for(vt_symbol, date)
    if window.empty:
        return None
    price = spec.value_func(window)
    if not np.isfinite(price) or price <= 0.0:
        return None
    return {
        "date": pd.Timestamp(date).normalize(),
        "vt_symbol": vt_symbol,
        "proxy_price": float(price),
        "proxy_source": spec.source_prefix,
        "proxy_bar_count": int(len(window)),
        "proxy_first_time": window["bar_datetime"].iloc[0],
        "proxy_last_time": window["bar_datetime"].iloc[-1],
    }


def _seed_targets() -> pd.DataFrame:
    paths = [
        s452.PROXY_MAP_PATH,
        s451.STAGE149_DETAIL_PATH,
    ]
    rows: list[pd.DataFrame] = []
    for path in paths:
        frame = pd.read_csv(path, encoding="utf-8-sig")
        if "date" not in frame.columns or "vt_symbol" not in frame.columns:
            continue
        part = frame[["date", "vt_symbol"]].copy()
        part["date"] = pd.to_datetime(part["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
        rows.append(part.dropna(subset=["date", "vt_symbol"]))
    if not rows:
        return pd.DataFrame(columns=["date", "vt_symbol"])
    return pd.concat(rows, ignore_index=True).drop_duplicates(["date", "vt_symbol"]).reset_index(drop=True)


def _fill_proxy_map_for_targets(
    proxy_map: dict[tuple[pd.Timestamp, str], dict[str, Any]],
    targets: pd.DataFrame,
    spec: ProxySpec,
    *,
    allow_fetch: bool,
) -> list[dict[str, Any]]:
    status_rows: list[dict[str, Any]] = []
    unresolved: dict[str, list[pd.Timestamp]] = {}
    if targets.empty:
        return status_rows
    for row in targets.itertuples(index=False):
        vt_symbol = str(row.vt_symbol)
        date = pd.Timestamp(row.date).normalize()
        key = (date, vt_symbol)
        if key in proxy_map:
            continue
        proxy = _proxy_from_bars(vt_symbol, date, spec)
        if proxy is not None:
            proxy_map[key] = proxy
            status_rows.append(
                {"variant": spec.variant, "vt_symbol": vt_symbol, "date": date, "status": "cached_raw", "message": ""}
            )
        else:
            unresolved.setdefault(vt_symbol, []).append(date)

    if not allow_fetch:
        for vt_symbol, dates in unresolved.items():
            for date in sorted(set(dates)):
                status_rows.append(
                    {
                        "variant": spec.variant,
                        "vt_symbol": vt_symbol,
                        "date": date,
                        "status": "missing_not_fetched",
                        "message": "",
                    }
                )
        return status_rows

    for vt_symbol, dates in sorted(unresolved.items()):
        status = s452._extract_symbol_windows(vt_symbol, sorted(set(dates)))
        for date in sorted(set(dates)):
            proxy = _proxy_from_bars(vt_symbol, date, spec)
            if proxy is not None:
                proxy_map[(date, vt_symbol)] = proxy
                row_status = "backfilled"
                message = str(status.get("status", ""))
            else:
                row_status = "still_missing"
                message = str(status.get("message", status.get("status", "")))
            status_rows.append(
                {
                    "variant": spec.variant,
                    "vt_symbol": vt_symbol,
                    "date": date,
                    "status": row_status,
                    "message": message,
                    "extract_status": status.get("status", ""),
                    "extract_rows": status.get("rows", 0),
                    "extract_elapsed_seconds": status.get("elapsed_seconds", 0.0),
                }
            )
    return status_rows


def _run_variant(spec: ProxySpec, seed_targets: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    proxy_map: dict[tuple[pd.Timestamp, str], dict[str, Any]] = {}
    status_rows: list[dict[str, Any]] = []
    for row in _fill_proxy_map_for_targets(proxy_map, seed_targets, spec, allow_fetch=False):
        row["iteration"] = 0
        status_rows.append(row)

    usage = pd.DataFrame()
    daily = pd.DataFrame()
    for iteration in range(1, MAX_ITERATIONS + 1):
        daily, usage = s452._run_engine(proxy_map)
        fallback = s452._fallback_targets(usage)
        fallback_count = int(usage["proxy_source"].eq("fallback_order_price").sum()) if not usage.empty else 0
        status_rows.append(
            {
                "variant": spec.variant,
                "iteration": iteration,
                "vt_symbol": "__iteration__",
                "date": "",
                "status": "iteration_summary",
                "message": f"fallback_trade_count={fallback_count};fallback_key_count={len(fallback)}",
            }
        )
        if fallback.empty:
            break
        before = len(proxy_map)
        rows = _fill_proxy_map_for_targets(proxy_map, fallback, spec, allow_fetch=True)
        for row in rows:
            row["iteration"] = iteration
        status_rows.extend(rows)
        if len(proxy_map) == before:
            break

    daily = daily[["date", "account_equity", "slippage", "trade_count", "net_pnl"]].copy()
    daily["variant"] = spec.variant
    daily["label"] = spec.label
    if not usage.empty:
        usage = usage.copy()
        usage["variant"] = spec.variant
        usage["label"] = spec.label
    proxy_frame = pd.DataFrame(list(proxy_map.values()))
    if not proxy_frame.empty:
        proxy_frame["variant"] = spec.variant
    return daily, usage, pd.DataFrame(status_rows), proxy_frame


def _build_baseline_daily(baseline: pd.DataFrame, rerun_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    base = baseline[["date", "equity", "c3_slippage", "c3_trade_count", "c3_net_pnl"]].copy()
    base.rename(
        columns={
            "equity": "account_equity",
            "c3_slippage": "slippage",
            "c3_trade_count": "trade_count",
            "c3_net_pnl": "net_pnl",
        },
        inplace=True,
    )
    base["variant"] = BASELINE_VARIANT
    base["label"] = "Stage079 baseline from Stage403"
    rows.append(base)
    rerun = rerun_daily[["date", "account_equity", "slippage", "trade_count", "net_pnl"]].copy()
    rerun["variant"] = RERUN_VARIANT
    rerun["label"] = "Stage079 same-day engine rerun"
    rows.append(rerun)
    return pd.concat(rows, ignore_index=True)


def _calendar_equity(daily: pd.DataFrame, equity_col: str) -> pd.Series:
    series = daily.sort_values("date").set_index("date")[equity_col].astype(float)
    calendar = pd.date_range(series.index.min(), series.index.max(), freq="D")
    return series.reindex(calendar).ffill()


def _evaluate(long_daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    horizon_rows: list[dict[str, Any]] = []
    labels = long_daily.drop_duplicates("variant").set_index("variant")["label"].to_dict()
    for variant, frame in long_daily.groupby("variant", sort=False):
        equity = _calendar_equity(frame, "account_equity")
        summary_rows.append(s450._summary_for(variant, labels.get(variant, variant), equity, ACCOUNT_CAPITAL))
        for horizon_days in (90, 180):
            horizon_rows.append(s450._horizon_for(variant, labels.get(variant, variant), equity, horizon_days))
    summary = pd.DataFrame(summary_rows)
    horizon = pd.DataFrame(horizon_rows)
    score = s450._score_horizons(horizon)
    cost = s451._cost_stress(long_daily)
    gate = s450._gate(summary, horizon, score, cost)
    return summary, horizon, score, cost, gate


def _plot(long_daily: pd.DataFrame) -> None:
    colors = {
        BASELINE_VARIANT: "#4c78a8",
        RERUN_VARIANT: "#72b7b2",
        SPECS[0].variant: "#e45756",
        SPECS[1].variant: "#f58518",
        SPECS[2].variant: "#54a24b",
    }
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    for variant, frame in long_daily.groupby("variant", sort=False):
        label = str(frame["label"].iloc[0])
        x = pd.to_datetime(frame["date"])
        nav = frame["account_equity"].astype(float) / ACCOUNT_CAPITAL
        axes[0].plot(x, nav, label=label, color=colors.get(variant), linewidth=1.15)
        axes[1].plot(x, (nav / nav.cummax() - 1.0) * 100.0, label=label, color=colors.get(variant), linewidth=0.95)
    axes[0].set_title("Stage079 true path replay: fixed pre-close fill semantics")
    axes[0].set_ylabel("NAV")
    axes[0].legend(fontsize=8)
    axes[1].set_title("Underwater drawdown")
    axes[1].set_ylabel("Drawdown %")
    axes[1].axhline(-30.0, color="#222222", linestyle="--", linewidth=1.0)
    axes[1].grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    cost: pd.DataFrame,
    gate: pd.DataFrame,
    usage: pd.DataFrame,
    backfill_status: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    summary_cols = [
        "variant",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "ulcer_pct",
        "rolling252_dd30_breach_rate",
        "rolling504_dd30_breach_rate",
        "annual_cold_start_dd30_pass_rate",
        "quarter_cold_start_dd30_pass_rate",
    ]
    horizon_cols = [
        "variant",
        "horizon_days",
        "return_p05_pct",
        "return_median_pct",
        "positive_return_rate",
        "annualized_below_5pct_rate",
        "max_dd_worst_pct",
        "dd20_breach_rate",
        "dd30_breach_rate",
        "ulcer_p95_pct",
        "longest_underwater_p95_days",
    ]
    gate_cols = [
        "variant",
        "hard_constraint_pass",
        "score_90d",
        "score_180d",
        "short_holding_score",
        "improved_count_90d",
        "improved_count_180d",
        "promotion_gate_pass",
        "failed_hard_constraints",
    ]
    spec_notes = pd.DataFrame(
        [{"variant": spec.variant, "label": spec.label, "deployability_note": spec.deployability_note} for spec in SPECS]
    )
    fallback = (
        usage[usage["proxy_source"].eq("fallback_order_price")]
        if not usage.empty and "proxy_source" in usage.columns
        else pd.DataFrame()
    )
    report = [
        "# Stage153 Stage079 预收盘成交语义真实路径回放",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：执行模型敏感性审计；不新增策略、不修改 C3/Stage079 交易规则。",
        "- 方法：预先固定三种 14:55-14:59 窗口成交语义，逐笔进入真实回放路径；不得按收益挑成交价。",
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 硬约束通过项：`{decision['hard_constraint_pass_variants']}`。",
        f"- 晋级通过项：`{decision['promotion_gate_pass_variants']}`。",
        f"- 最小fallback数：`{decision['min_final_fallback_trade_count']}`。",
        "",
        "## 语义说明",
        "",
        _md_table(spec_notes),
        "",
        "## 全周期指标",
        "",
        _md_table(summary[summary_cols]),
        "",
        "## 3个月/6个月体验",
        "",
        _md_table(horizon[horizon_cols].sort_values(["variant", "horizon_days"])),
        "",
        "## 分数与门禁",
        "",
        _md_table(gate[gate_cols]),
        "",
        "## 成本压力",
        "",
        _md_table(
            cost[["variant", "slippage_multiplier", "max_dd_pct", "baseline_stage079_max_dd_pct", "not_worse_than_stage079_stress"]]
        ),
        "",
        "## 补齐状态",
        "",
        _md_table(backfill_status.groupby(["variant", "status"], dropna=False).size().reset_index(name="count")),
        "",
        "## 剩余fallback样本",
        "",
        _md_table(
            fallback[["variant", "date", "vt_symbol", "direction", "offset", "order_price", "trade_price", "order_volume"]].head(80)
            if not fallback.empty
            else pd.DataFrame()
        ),
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行前过拟合反思：否。三种成交语义在运行前固定，且都来自同一个收盘前窗口。",
        "- 运行后过拟合反思：若只选择最漂亮曲线晋级会过拟合；本阶段只做执行模型审计，不把敏感性结果直接变成策略规则。",
        "- 运行前继续价值反思：是。Stage152 只否决了 14:55 VWAP，还需要判断是否存在更合理的收盘前语义。",
        "- 运行后继续价值反思：若只有 close-like 语义通过，则后续价值在信号冻结/实时化验证，而不是继续调 alpha 参数。",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    seed_targets = _seed_targets()
    baseline = s451._load_stage079_baseline()
    rerun_daily, _ = s452._run_engine(None)
    daily_frames = [_build_baseline_daily(baseline, rerun_daily)]
    usage_frames: list[pd.DataFrame] = []
    status_frames: list[pd.DataFrame] = []
    proxy_frames: list[pd.DataFrame] = []
    variant_meta: dict[str, dict[str, Any]] = {}

    for spec in SPECS:
        daily, usage, status, proxy = _run_variant(spec, seed_targets)
        daily_frames.append(daily)
        usage_frames.append(usage)
        status_frames.append(status)
        proxy_frames.append(proxy)
        fallback_count = int(usage["proxy_source"].eq("fallback_order_price").sum()) if not usage.empty else 0
        variant_meta[spec.variant] = {
            "label": spec.label,
            "final_fallback_trade_count": fallback_count,
            "trade_count": int(len(usage)),
            "proxy_key_count": int(len(proxy)),
            "deployability_note": spec.deployability_note,
        }

    long_daily = pd.concat(daily_frames, ignore_index=True).sort_values(["variant", "date"]).reset_index(drop=True)
    usage_all = pd.concat(usage_frames, ignore_index=True) if usage_frames else pd.DataFrame()
    status_all = pd.concat(status_frames, ignore_index=True) if status_frames else pd.DataFrame()
    proxy_all = pd.concat(proxy_frames, ignore_index=True) if proxy_frames else pd.DataFrame()
    summary, horizon, score, cost, gate = _evaluate(long_daily)
    _plot(long_daily)

    hard_pass = gate[gate["hard_constraint_pass"].eq(1)]["variant"].tolist()
    promotion = gate[gate["promotion_gate_pass"].eq(1)]["variant"].tolist()
    tested_variants = [spec.variant for spec in SPECS]
    tested_gate = gate[gate["variant"].isin(tested_variants)].copy()
    tested_hard_pass = tested_gate[tested_gate["hard_constraint_pass"].eq(1)]["variant"].tolist()
    tested_promotion = tested_gate[tested_gate["promotion_gate_pass"].eq(1)]["variant"].tolist()
    close_like_pass = "stage079_true_path_1459_last_close" in tested_hard_pass
    only_close_like = close_like_pass and all(v == "stage079_true_path_1459_last_close" for v in tested_hard_pass)
    if tested_promotion and only_close_like:
        decision_label = "close_like_sensitivity_pass_requires_signal_freeze_not_promotion"
    elif tested_promotion:
        decision_label = "preclose_semantics_promotion_candidate_requires_deployability_review"
    elif tested_hard_pass:
        decision_label = "preclose_semantics_hard_pass_no_target_promotion"
    else:
        decision_label = "preclose_semantics_all_hard_fail_keep_execution_pause"

    decision = {
        "stage": "Stage153",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_label,
        "seed_target_count": int(len(seed_targets)),
        "hard_constraint_pass_variants": hard_pass,
        "tested_hard_constraint_pass_variants": tested_hard_pass,
        "promotion_gate_pass_variants": promotion,
        "tested_promotion_gate_pass_variants": tested_promotion,
        "variant_meta": variant_meta,
        "min_final_fallback_trade_count": int(
            min((meta["final_fallback_trade_count"] for meta in variant_meta.values()), default=0)
        ),
        "outputs": {
            "daily": str(DAILY_PATH),
            "trade_usage": str(USAGE_PATH),
            "backfill_status": str(BACKFILL_STATUS_PATH),
            "proxy_map": str(PROXY_MAP_PATH),
            "summary": str(SUMMARY_PATH),
            "horizon": str(HORIZON_PATH),
            "score": str(SCORE_PATH),
            "cost": str(COST_PATH),
            "gate": str(GATE_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": "若只有14:59 close-like通过，必须先验证信号能否收盘前冻结/实时化；否则不得作为部署候选。",
    }

    long_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    usage_all.to_csv(USAGE_PATH, index=False, encoding="utf-8-sig")
    status_all.to_csv(BACKFILL_STATUS_PATH, index=False, encoding="utf-8-sig")
    proxy_all.to_csv(PROXY_MAP_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, horizon, cost, gate, usage_all, status_all, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
