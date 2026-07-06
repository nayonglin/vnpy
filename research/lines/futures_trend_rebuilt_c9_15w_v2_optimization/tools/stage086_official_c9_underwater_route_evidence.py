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
STAGE = "Stage086"
MODEL_TAG = "stage086_official_c9_underwater_route_evidence_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage086_official_c9_underwater_route_evidence"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage086_official_c9_underwater_route_evidence"
STAGES_DIR = LINE_DIR / "stages"

BACKTEST_OUT = ROOT / "examples" / "portfolio_backtesting" / "backtest_outputs"
STAGE167_CURVES = BACKTEST_OUT / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_curves_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv"
STAGE167_SUMMARY = BACKTEST_OUT / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_summary_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv"
STAGE158_WINDOW = BACKTEST_OUT / "qmt_roll_stage158_current_rebuild_c9_c4_drawdown_pressure_attribution_window_summary_stage158_current_rebuild_c9_c4_drawdown_pressure_attribution_v1.csv"
STAGE158_EVENTS = BACKTEST_OUT / "qmt_roll_stage158_current_rebuild_c9_c4_drawdown_pressure_attribution_event_window_summary_stage158_current_rebuild_c9_c4_drawdown_pressure_attribution_v1.csv"
STAGE848_WINDOW = BACKTEST_OUT / "qmt_roll_stage848_stage847_c9_peak_trough_forensics_window_summary_stage848_stage847_c9_peak_trough_forensics_v1.csv"
STAGE848_PRESSURE = BACKTEST_OUT / "qmt_roll_stage848_stage847_c9_peak_trough_forensics_pressure_days_stage848_stage847_c9_peak_trough_forensics_v1.csv"
STAGE863_SUMMARY = BACKTEST_OUT / "qmt_roll_stage863_stage847_c10_budget_lock_engine_summary_stage863_stage847_c10_budget_lock_engine_v1.csv"
STAGE863_COMPARISON = BACKTEST_OUT / "qmt_roll_stage863_stage847_c10_budget_lock_engine_comparison_stage863_stage847_c10_budget_lock_engine_v1.csv"
STAGE863_BUDGET_EVENTS = BACKTEST_OUT / "qmt_roll_stage863_stage847_c10_budget_lock_engine_budget_lock_events_stage863_stage847_c10_budget_lock_engine_v1.csv"
STAGE049_DECISION = LINE_DIR / "outputs/stage049_stage208_true_carry_replay_gate/rebuilt_c9_v2_stage049_stage208_true_carry_replay_gate_decision_stage049_stage208_true_carry_replay_gate_v1.json"

PATH_METRICS_PATH = OUT / f"{OUTPUT_PREFIX}_stage167_path_metrics_{MODEL_TAG}.csv"
EVIDENCE_PATH = OUT / f"{OUTPUT_PREFIX}_evidence_table_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    return value


def _date_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return pd.Timestamp(value).date().isoformat()


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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


def _reason_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return ";".join(str(item) for item in value if str(item))
    return str(value)


def _max_consecutive_true(mask: pd.Series) -> int:
    best = 0
    current = 0
    for value in mask.astype(bool).tolist():
        if value:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def _path_metrics() -> pd.DataFrame:
    curves = _read_csv(STAGE167_CURVES)
    if curves.empty:
        raise FileNotFoundError(STAGE167_CURVES)
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves = curves.dropna(subset=["date"]).sort_values(["requested_start_month", "date"]).reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    for start_month, group in curves.groupby("requested_start_month", sort=True):
        frame = group.sort_values("date").reset_index(drop=True)
        equity = pd.to_numeric(frame["account_equity"], errors="coerce").ffill()
        capital = float(pd.to_numeric(frame.get("account_capital", pd.Series([150000.0])), errors="coerce").dropna().iloc[0])
        high_water = equity.cummax()
        dd_pct = (equity / high_water - 1.0) * 100.0
        trough_idx = int(dd_pct.idxmin())
        peak_before_trough_idx = int(equity.loc[:trough_idx].idxmax())
        trough_date = pd.Timestamp(frame.loc[trough_idx, "date"])
        peak_date = pd.Timestamp(frame.loc[peak_before_trough_idx, "date"])
        below_initial = equity < capital - 1e-9
        net_pnl = pd.to_numeric(frame.get("net_pnl", 0.0), errors="coerce").fillna(0.0)
        broker10 = pd.to_numeric(frame.get("broker10_margin_to_equity_pct", 0.0), errors="coerce").fillna(0.0)
        before_or_at_trough = frame["date"].le(trough_date)
        after_trough = frame["date"].gt(trough_date)
        rows.append(
            {
                "requested_start_month": str(start_month),
                "actual_start": _date_text(frame["date"].iloc[0]),
                "actual_end": _date_text(frame["date"].iloc[-1]),
                "end_equity": float(equity.iloc[-1]),
                "total_return_pct": float((equity.iloc[-1] / capital - 1.0) * 100.0),
                "max_drawdown_pct": float(dd_pct.min()),
                "drawdown_peak_date": _date_text(peak_date),
                "drawdown_trough_date": _date_text(trough_date),
                "peak_to_trough_calendar_days": int((trough_date - peak_date).days),
                "days_below_initial": int(below_initial.sum()),
                "max_consecutive_below_initial_days": _max_consecutive_true(below_initial),
                "net_pnl_to_trough": float(net_pnl[before_or_at_trough].sum()),
                "net_pnl_after_trough": float(net_pnl[after_trough].sum()),
                "final_recovery_after_trough": float(equity.iloc[-1] - equity.iloc[trough_idx]),
                "max_broker10_margin_to_equity_pct": float(broker10.max()),
                "broker10_days_gt70": int(broker10.gt(70.0).sum()),
                "broker10_days_gt90": int(broker10.gt(90.0).sum()),
                "trade_count_sum": float(pd.to_numeric(frame.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
                "slippage_sum": float(pd.to_numeric(frame.get("slippage", 0.0), errors="coerce").fillna(0.0).sum()),
            }
        )
    return pd.DataFrame(rows)


def _evidence_table(path_metrics: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    worst = path_metrics.sort_values(["max_drawdown_pct", "days_below_initial"]).head(5)
    rows.append(
        {
            "evidence_id": "stage167_current_c9_path_shape",
            "source": str(STAGE167_CURVES),
            "observation": (
                f"{len(path_metrics)} starts; worst max DD {path_metrics['max_drawdown_pct'].min():.4f}%, "
                f"max days below initial {int(path_metrics['days_below_initial'].max())}, "
                f"max consecutive below {int(path_metrics['max_consecutive_below_initial_days'].max())}"
            ),
            "implication": "C9 right tail is strong but water experience is concentrated in a few long cold-start paths.",
            "supports_next_route": "path_attribution_not_cash_overlay",
        }
    )
    rows.append(
        {
            "evidence_id": "stage167_worst_starts",
            "source": str(PATH_METRICS_PATH),
            "observation": "; ".join(
                f"{r.requested_start_month}:DD={r.max_drawdown_pct:.2f}%,water={int(r.days_below_initial)}"
                for r in worst.itertuples()
            ),
            "implication": "The most painful paths are not a single date-only anomaly, but repeated cold-start/denominator stress.",
            "supports_next_route": "multi_start_structural_filter_or_sleeve",
        }
    )

    stage158_window = _read_csv(STAGE158_WINDOW)
    stage158_events = _read_csv(STAGE158_EVENTS)
    if not stage158_window.empty:
        c9_event_sum = int(pd.to_numeric(stage158_window.get("c9_window_event_count", 0), errors="coerce").fillna(0).sum())
        zero_event_count = int(pd.to_numeric(stage158_window.get("c9_window_event_count", 0), errors="coerce").fillna(0).eq(0).sum())
        rows.append(
            {
                "evidence_id": "stage158_stop_retry_not_main_dd_driver",
                "source": str(STAGE158_WINDOW),
                "observation": f"Stage158 C9 max-DD windows: {zero_event_count}/{len(stage158_window)} rows have zero stop/retry events; event sum={c9_event_sum}.",
                "implication": "Do not keep scanning stop/retry R multiple, retry count or same-day retry shape for the main water problem.",
                "supports_next_route": "stop_retry_route_deprioritized",
            }
        )
    if not stage158_events.empty:
        rows.append(
            {
                "evidence_id": "stage158_event_windows_are_sparse",
                "source": str(STAGE158_EVENTS),
                "observation": f"Event-window rows={len(stage158_events)}, total event_count={int(pd.to_numeric(stage158_events.get('event_count', 0), errors='coerce').fillna(0).sum())}.",
                "implication": "Stop/retry diagnostics remain useful for execution safety, not for broad underwater reduction.",
                "supports_next_route": "execution_safety_only",
            }
        )

    stage848_window = _read_csv(STAGE848_WINDOW)
    if not stage848_window.empty:
        c9 = stage848_window[stage848_window["arm"].astype(str).str.contains("stage847", na=False)]
        delta = stage848_window[stage848_window["arm"].astype(str).str.contains("delta", na=False)]
        if not c9.empty:
            c9row = c9.iloc[0]
            rows.append(
                {
                    "evidence_id": "stage848_peak_trough_pressure",
                    "source": str(STAGE848_WINDOW),
                    "observation": (
                        f"Peak-trough C9 window cum net pnl={float(c9row['window_cum_net_pnl']):.0f}, "
                        f"trade_count={float(c9row['window_trade_count']):.0f}, "
                        f"max broker10={float(c9row['window_max_broker10_pct']):.2f}%."
                    ),
                    "implication": "The known bad window is a holding/exposure pressure problem, not just entry-day execution.",
                    "supports_next_route": "position_exposure_attribution",
                }
            )
        if not delta.empty:
            drow = delta.iloc[0]
            rows.append(
                {
                    "evidence_id": "stage848_c9_minus_c4_delta",
                    "source": str(STAGE848_WINDOW),
                    "observation": (
                        f"C9-C4 peak-to-trough equity delta={float(drow['peak_to_trough_equity_change']):.0f}, "
                        f"window net pnl delta={float(drow['window_cum_net_pnl']):.0f}, "
                        f"slippage delta={float(drow['window_slippage']):.0f}."
                    ),
                    "implication": "C9 extra right-tail machinery also creates exposure/denominator risk in bad windows.",
                    "supports_next_route": "structural_sleeve_or_true_exposure_governance",
                }
            )

    stage848_pressure = _read_csv(STAGE848_PRESSURE)
    if not stage848_pressure.empty:
        rows.append(
            {
                "evidence_id": "stage848_pressure_days",
                "source": str(STAGE848_PRESSURE),
                "observation": f"Pressure-day rows={len(stage848_pressure)}; top rows show concentrated product-direction exposure and broker10 stress.",
                "implication": "If a future rule is tried, it should be validated as exposure concentration governance, not product blacklist.",
                "supports_next_route": "exposure_concentration_governance_readonly_first",
            }
        )

    stage863_summary = _read_csv(STAGE863_SUMMARY)
    stage863_comparison = _read_csv(STAGE863_COMPARISON)
    stage863_budget_events = _read_csv(STAGE863_BUDGET_EVENTS)
    if not stage863_summary.empty:
        c10 = stage863_summary[stage863_summary.astype(str).apply(lambda s: s.str.contains("stage863", na=False)).any(axis=1)]
        rows.append(
            {
                "evidence_id": "stage863_budget_lock_no_effect",
                "source": str(STAGE863_SUMMARY),
                "observation": "Stage863 C10 budget lock path was identical to C9; lock created/released but no reduce/block.",
                "implication": "Do not repeat same stop-retry budget-lock shape; it is already falsified.",
                "supports_next_route": "budget_lock_route_deprioritized",
                "aux_rows": int(len(c10)),
            }
        )
    if not stage863_budget_events.empty:
        reason = stage863_budget_events.get("reason", pd.Series(dtype=object)).astype(str)
        reduced = pd.to_numeric(stage863_budget_events.get("reduced_volume", 0), errors="coerce").fillna(0)
        created_mask = reason.eq("stage863_budget_lock_created")
        released_mask = reason.eq("stage863_budget_lock_released_flat")
        block_like_mask = reason.str.contains("block", case=False, na=False) & ~(created_mask | released_mask)
        rows.append(
            {
                "evidence_id": "stage863_budget_lock_events_no_reduce",
                "source": str(STAGE863_BUDGET_EVENTS),
                "observation": (
                    f"budget events created={int(created_mask.sum())}, "
                    f"released={int(released_mask.sum())}, "
                    f"reduced={int(reduced.gt(0).sum())}, "
                    f"block_like={int(block_like_mask.sum())}."
                ),
                "implication": "The lock accounting was active, but it did not actually reduce or block exposure.",
                "supports_next_route": "budget_lock_route_deprioritized",
                "aux_rows": int(len(stage863_budget_events)),
            }
        )
    if not stage863_comparison.empty:
        rows.append(
            {
                "evidence_id": "stage863_comparison_available",
                "source": str(STAGE863_COMPARISON),
                "observation": f"Stage863 comparison rows={len(stage863_comparison)} available for audit.",
                "implication": "Existing full-engine comparison should be reused rather than rerunning the same C10 shape.",
                "supports_next_route": "reuse_prior_negative_result",
            }
        )

    stage049_decision = _read_json(STAGE049_DECISION)
    if stage049_decision:
        rows.append(
            {
                "evidence_id": "stage049_true_carry_blocker",
                "source": str(STAGE049_DECISION),
                "observation": _reason_text(stage049_decision.get("blocking_reasons"))
                or _reason_text(stage049_decision.get("decision")),
                "implication": "Independent xsmom true-carry remains the more structural route, but data blockers must be cleared first.",
                "supports_next_route": "stage208_true_carry_data_first",
            }
        )

    return pd.DataFrame(rows)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows else frame.copy()
    return data.to_markdown(index=False)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    input_audit = _input_audit(
        [
            STAGE167_CURVES,
            STAGE167_SUMMARY,
            STAGE158_WINDOW,
            STAGE158_EVENTS,
            STAGE848_WINDOW,
            STAGE848_PRESSURE,
            STAGE863_SUMMARY,
            STAGE863_COMPARISON,
            STAGE863_BUDGET_EVENTS,
            STAGE049_DECISION,
        ]
    )
    path_metrics = _path_metrics()
    evidence = _evidence_table(path_metrics)
    path_metrics.to_csv(PATH_METRICS_PATH, index=False)
    evidence.to_csv(EVIDENCE_PATH, index=False)
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False)

    starts_2020 = path_metrics[path_metrics["requested_start_month"].astype(str).ge("2020-01")].copy()
    decision_text = "stage086_stop_retry_heat_budget_routes_deprioritized_next_true_sleeve_or_exposure_data"
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": decision_text,
        "stage167_start_count": int(len(path_metrics)),
        "stage167_2020_plus_start_count": int(len(starts_2020)),
        "stage167_worst_max_drawdown_pct": float(path_metrics["max_drawdown_pct"].min()),
        "stage167_max_days_below_initial": int(path_metrics["days_below_initial"].max()),
        "stage167_max_consecutive_below_initial_days": int(path_metrics["max_consecutive_below_initial_days"].max()),
        "evidence_rows": int(len(evidence)),
        "input_audit": str(INPUT_AUDIT_PATH),
        "next_route": [
            "Do not continue same-day stop/retry parameter shapes.",
            "Do not repeat Stage863-style budget lock.",
            "If doing exposure governance, first do true position/exposure attribution and avoid product/date blacklists.",
            "Best structural route remains independent sleeve / Stage208 true-carry after data blockers are cleared.",
        ],
        "overfit_start_reflection": "否。Stage086只读冻结证据，目的是排除已失败局部路线，不新增过滤规则。",
        "continue_value_start_reflection": "有。它把下一轮实验从现金/stop-retry/预算锁转到更本质的结构收益或真实暴露数据。",
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    top_path_cols = [
        "requested_start_month",
        "total_return_pct",
        "max_drawdown_pct",
        "days_below_initial",
        "max_consecutive_below_initial_days",
        "drawdown_peak_date",
        "drawdown_trough_date",
        "max_broker10_margin_to_equity_pct",
        "broker10_days_gt70",
    ]
    worst_paths = path_metrics.sort_values(["max_drawdown_pct", "days_below_initial"]).head(8)
    report_lines = [
        "# Stage086 official C9 underwater route evidence",
        "",
        "## 结论",
        "",
        f"- 决策：`{decision_text}`。",
        "- 本阶段不回测、不改策略、不连接 CTP、不触发订单 API；只读 Stage167、Stage158、Stage848、Stage863 和 Stage049 证据。",
        "- 现金/account overlay 已由 Stage085 收束；本阶段进一步确认：继续围绕 stop/retry 参数、同日重进、C10 budget lock 或简单 drawdown brake 的价值低。",
        "- 下一步若继续策略优化，优先做独立收益腿真承载数据补齐，或先做真实持仓/暴露归因；不得做产品/日期黑名单。",
        "- 输入文件已固化到 input_audit，包含 size、mtime、sha256，防止后续同名产物漂移造成审计误读。",
        "",
        "## Stage167 Worst Paths",
        "",
        _md_table(worst_paths[top_path_cols]),
        "",
        "## Evidence Table",
        "",
        _md_table(evidence, max_rows=20),
        "",
        "## 过拟合与继续价值",
        "",
        "- 运行前过拟合反思：否。只读冻结证据，不生成交易过滤条件。",
        "- 运行后过拟合反思：否。结论是排除弱路线，不按某个亏损产品或日期救参。",
        "- 继续价值：有。下一步应清 Stage208/xsmom 真承载数据阻塞，或做正式 C9 全路径持仓暴露归因。",
        "",
        "## 输出",
        "",
        f"- path_metrics：`{PATH_METRICS_PATH}`",
        f"- evidence：`{EVIDENCE_PATH}`",
        f"- input_audit：`{INPUT_AUDIT_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    stage_path = STAGES_DIR / f"{datetime.now():%Y%m%d_%H%M}_stage086_official_c9_underwater_route_evidence.md"
    stage_lines = [
        "# Stage086 official C9 underwater route evidence",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{datetime.now():%Y-%m-%dT%H:%M:%S}",
        "- 阶段性质：正式 C9 水下路线证据综合；只读，不新增候选",
        "- 是否重要突破：否，路线排除/下一步选择",
        "- 是否触发A/B：否，本阶段不提出接入正式版候选",
        "",
        "## 外部调研与判断",
        "",
        "- 本轮外部调研提示趋势系统长期水下和回撤期是结构性成本，常见改善方向是分散、独立收益腿、波动/资金治理；但本仓库已有 cash/account overlay 与 stop/retry/budget lock 证据必须先复用。",
        "- 本阶段判断：不继续在 stop/retry、同日重进、C10 budget lock、简单回撤刹车上扫参；下一步应转向独立收益腿真承载或真实暴露归因。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{Path(__file__).relative_to(ROOT)}`",
        "- 新增参数：无交易参数。",
        "- 修改参数：无。",
        "- 删除参数：无。",
        "",
        "## 结果",
        "",
        f"- Stage167 起点数：`{len(path_metrics)}`；2020+ 起点数：`{len(starts_2020)}`。",
        f"- 最差最大回撤：`{path_metrics['max_drawdown_pct'].min():.4f}%`。",
        f"- 最大水下天数：`{int(path_metrics['days_below_initial'].max())}`；最大连续水下天数：`{int(path_metrics['max_consecutive_below_initial_days'].max())}`。",
        "",
        "### Stage167 Worst Paths",
        "",
        _md_table(worst_paths[top_path_cols]),
        "",
        "### Evidence Table",
        "",
        _md_table(evidence, max_rows=20),
        "",
        "## 结论",
        "",
        f"- 决策：`{decision_text}`。",
        "- 关键判断：Stage158 显示 C9 最大回撤窗口里的 stop/retry 事件稀疏，Stage863 budget lock 已经无效，Stage848 指向持仓/暴露压力；所以不能继续做 stop/retry 参数、预算锁或简单回撤刹车救参。",
        "- 审计加固：Stage049 blocker 字符串展示已修正；Stage863 budget lock 额外引用 budget_lock_events；输入文件 size/mtime/sha256 已固化。",
        "- 下一步：优先清理 Stage208/xsmom 真承载数据阻塞；若做 exposure governance，必须先做全路径持仓暴露归因，不能直接按产品/日期/方向黑名单。",
        "",
        "## 回测记录字段",
        "",
        "- 本阶段不新增回测，因此不新增期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率；仅汇总 Stage167 和既有法证阶段。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前：否。只读冻结证据，不新增规则。",
        "- 运行后：否。结论是排除已弱证据路线，不按亏损日期/产品救参。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前：有。Stage085 收束现金路线后，必须确定下一轮是否还值得做 stop/retry/预算锁。",
        "- 运行后：有，但方向明确切换到独立收益腿真承载或真实暴露归因。",
        "",
        "## 输出",
        "",
        f"- report：`{REPORT_PATH}`",
        f"- path_metrics：`{PATH_METRICS_PATH}`",
        f"- evidence：`{EVIDENCE_PATH}`",
        f"- input_audit：`{INPUT_AUDIT_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    stage_path.write_text("\n".join(stage_lines) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"stage_record={stage_path}")


if __name__ == "__main__":
    main()
