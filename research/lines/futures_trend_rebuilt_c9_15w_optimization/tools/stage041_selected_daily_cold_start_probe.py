from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
TOOLS_DIR = Path(__file__).resolve().parent
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
for path in (str(TOOLS_DIR), str(PORTFOLIO_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import analyze_qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit as s167
import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719
import stage013_account_state_pilot_gate_engine as s013
import stage039_full_market_ai_top8_proxy as s039


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage041"
MODEL_TAG = "stage041_selected_daily_cold_start_probe_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage041_selected_daily_cold_start_probe"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage041_selected_daily_cold_start_probe"
STAGES_DIR = LINE_DIR / "stages"

STAGE040_OUTPUT_DIR = LINE_DIR / "outputs" / "stage040_stage039_negative_window_delta_attribution"
STAGE040_PREFIX = "rebuilt_c9_stage040_stage039_negative_window_delta_attribution"
STAGE040_TAG = "stage040_stage039_negative_window_delta_attribution_v1"
STAGE040_TOP_WINDOWS_PATH = STAGE040_OUTPUT_DIR / f"{STAGE040_PREFIX}_top_windows_{STAGE040_TAG}.csv"

REQUESTED_END = pd.Timestamp("2026-06-30")
MIN_PERIOD_CALENDAR_DAYS = 366
CAPITAL = 150000.0
ADD_RISK_FRACTION = 0.25
PROBE_START_LIMIT = 8

PROBE_STARTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_probe_starts_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
LOT_DELTAS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_deltas_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


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
        number = float(value)
        return None if np.isnan(number) or np.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return None if pd.isna(value) else value.isoformat()
    if pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无数据_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return data.to_markdown(index=False)


def _date_key(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _sharpe_from_equity(equity: pd.Series) -> float:
    values = pd.to_numeric(equity, errors="coerce").dropna()
    returns = values.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty or float(returns.std(ddof=1)) == 0.0:
        return 0.0
    return float(returns.mean() / returns.std(ddof=1) * np.sqrt(252.0))


def _select_probe_start_dates(top_windows: pd.DataFrame, limit: int = PROBE_START_LIMIT) -> list[pd.Timestamp]:
    if top_windows.empty:
        return []
    data = top_windows.copy()
    data["start_date"] = pd.to_datetime(data["start_date"], errors="coerce").dt.normalize()
    data["stage039_return_pct"] = pd.to_numeric(data["stage039_return_pct"], errors="coerce")
    data["stage039_absolute_end_ge_stage013"] = pd.to_numeric(
        data.get("stage039_absolute_end_ge_stage013", 0), errors="coerce"
    ).fillna(0)
    data = data.dropna(subset=["start_date", "stage039_return_pct"])
    groups = [
        data[data["window_class"].eq("both_negative")].sort_values("stage039_return_pct"),
        data[
            data["window_class"].eq("added_negative_by_stage039")
            & data["stage039_absolute_end_ge_stage013"].eq(0)
        ].sort_values("stage039_return_pct"),
        data[data["window_class"].eq("added_negative_by_stage039")].sort_values("stage039_return_pct"),
    ]
    starts: list[pd.Timestamp] = []
    seen: set[str] = set()
    for group in groups:
        for value in group["start_date"]:
            key = _date_key(value)
            if key in seen:
                continue
            starts.append(pd.Timestamp(value).normalize())
            seen.add(key)
            if len(starts) >= limit:
                return starts
    return starts


def _audit_curve_from_actual_start(requested_start: str, variant: str, curve: pd.DataFrame) -> dict[str, Any]:
    data = curve.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data["equity"] = pd.to_numeric(data["equity"], errors="coerce")
    data = data.dropna(subset=["date", "equity"]).sort_values("date").drop_duplicates("date").reset_index(drop=True)
    if data.empty:
        return {
            "requested_start": requested_start,
            "variant": variant,
            "window_count": 0,
            "negative_count": 0,
            "min_return_pct": np.nan,
            "worst_end_date": "",
        }
    start_date = pd.Timestamp(data["date"].iloc[0]).normalize()
    start_equity = float(data["equity"].iloc[0])
    min_end = start_date + pd.Timedelta(days=MIN_PERIOD_CALENDAR_DAYS)
    ends = data[data["date"].ge(min_end)].copy()
    if ends.empty or abs(start_equity) <= 1e-12:
        return {
            "requested_start": requested_start,
            "variant": variant,
            "actual_start": _date_key(start_date),
            "actual_end": _date_key(data["date"].iloc[-1]),
            "window_count": 0,
            "negative_count": 0,
            "min_return_pct": np.nan,
            "worst_end_date": "",
            "to_final_return_pct": float((data["equity"].iloc[-1] / start_equity - 1.0) * 100.0),
            "end_equity": float(data["equity"].iloc[-1]),
            "max_dd_pct": float(_drawdown_pct(data["equity"]).min()),
            "sharpe": _sharpe_from_equity(data["equity"]),
        }
    returns = (pd.to_numeric(ends["equity"], errors="coerce") / start_equity - 1.0) * 100.0
    worst_idx = returns.idxmin()
    return {
        "requested_start": requested_start,
        "variant": variant,
        "actual_start": _date_key(start_date),
        "actual_end": _date_key(data["date"].iloc[-1]),
        "window_count": int(len(returns)),
        "negative_count": int(returns.lt(0.0).sum()),
        "negative_rate_pct": float(returns.lt(0.0).mean() * 100.0) if len(returns) else np.nan,
        "min_return_pct": float(returns.loc[worst_idx]),
        "worst_end_date": _date_key(ends.loc[worst_idx, "date"]),
        "to_final_return_pct": float((data["equity"].iloc[-1] / start_equity - 1.0) * 100.0),
        "end_equity": float(data["equity"].iloc[-1]),
        "max_dd_pct": float(_drawdown_pct(data["equity"]).min()),
        "sharpe": _sharpe_from_equity(data["equity"]),
    }


def _prepare_curve_frame(curve: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    result = curve.copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce").dt.normalize()
    result = result.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    result["requested_start"] = _date_key(start)
    result["requested_start_month"] = _date_key(start)
    result["requested_end"] = _date_key(REQUESTED_END)
    result["stage"] = STAGE
    result["model_tag"] = MODEL_TAG
    result["line_id"] = LINE_ID
    result["nav"] = pd.to_numeric(result["account_equity"], errors="coerce") / CAPITAL
    result["drawdown_pct"] = _drawdown_pct(result["account_equity"])
    return result


def _closed_lots_from_frames(frames: dict[str, pd.DataFrame], metadata: dict[str, Any], start: pd.Timestamp) -> pd.DataFrame:
    closed = s719._build_closed_lots(
        frames.get("trades", pd.DataFrame()),
        frames.get("entry_risk", pd.DataFrame()),
        frames.get("entry_candidates", pd.DataFrame()),
        metadata,
    )
    if closed.empty:
        return closed
    closed["requested_start"] = _date_key(start)
    closed["requested_start_month"] = _date_key(start)
    closed["entry_date"] = pd.to_datetime(closed["entry_date"], errors="coerce").dt.normalize()
    closed["exit_date"] = pd.to_datetime(closed["exit_date"], errors="coerce").dt.normalize()
    closed["realized_pnl"] = pd.to_numeric(closed["realized_pnl"], errors="coerce").fillna(0.0)
    return closed


def _stage039_lot_deltas(closed: pd.DataFrame, predictions: pd.DataFrame) -> pd.DataFrame:
    if closed.empty:
        return pd.DataFrame()
    attached = s039.attach_predictions_to_lots(closed, predictions)
    if "stage021_ai_top8" not in attached.columns:
        attached["stage021_ai_top8"] = False
    attached["stage021_ai_top8"] = s039._to_bool(attached["stage021_ai_top8"])
    attached["stage041_prediction_matched"] = attached["eval_date"].notna() if "eval_date" in attached.columns else False
    attached["stage041_selected_for_ai_top8_proxy"] = attached["stage021_ai_top8"]
    attached["stage039_proxy_delta_pnl"] = np.where(
        attached["stage041_selected_for_ai_top8_proxy"],
        pd.to_numeric(attached["realized_pnl"], errors="coerce").fillna(0.0) * ADD_RISK_FRACTION,
        0.0,
    )
    return attached[attached["stage041_selected_for_ai_top8_proxy"]].copy()


def _run_probe() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    top_windows = pd.read_csv(STAGE040_TOP_WINDOWS_PATH, encoding="utf-8-sig")
    starts = _select_probe_start_dates(top_windows, PROBE_START_LIMIT)
    if not starts:
        raise ValueError("no probe starts selected")
    metadata = s013.s901.s513._metadata()
    predictions = pd.read_csv(s039.PREDICTIONS_PATH, encoding="utf-8-sig", parse_dates=["eval_date"])
    probe_starts = pd.DataFrame(
        [{"probe_rank": idx, "requested_start": _date_key(start)} for idx, start in enumerate(starts, start=1)]
    )
    curve_frames: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    lot_delta_frames: list[pd.DataFrame] = []
    for idx, start in enumerate(starts, start=1):
        print(f"[stage041] running daily cold start {idx}/{len(starts)} start={_date_key(start)}", flush=True)
        combined, frames, _spec = s013._run_live_stage013(metadata, start, REQUESTED_END)
        base_curve = _prepare_curve_frame(combined, start)
        closed = _closed_lots_from_frames(frames, metadata, start)
        lot_deltas = _stage039_lot_deltas(closed, predictions)
        proxy_curve, unmatched = s039._build_proxy_curves(
            base_curve[["requested_start_month", "date", "account_equity"]].copy(),
            lot_deltas,
        )
        proxy_curve["requested_start"] = _date_key(start)
        proxy_curve["stage041_unmatched_delta_dates"] = int(unmatched)
        curve_frames.append(proxy_curve)
        if not lot_deltas.empty:
            lot_deltas["requested_start"] = _date_key(start)
            lot_deltas["stage041_unmatched_delta_dates"] = int(unmatched)
            lot_delta_frames.append(lot_deltas)
        stage013_audit = _audit_curve_from_actual_start(
            _date_key(start),
            "stage013_daily_cold_start_engine",
            proxy_curve[["date", "account_equity"]].rename(columns={"account_equity": "equity"}),
        )
        stage041_audit = _audit_curve_from_actual_start(
            _date_key(start),
            "stage041_daily_cold_start_stage039_ai_top8_proxy",
            proxy_curve[["date", "stage039_account_equity"]].rename(columns={"stage039_account_equity": "equity"}),
        )
        summary_rows.extend([stage013_audit, stage041_audit])
    curves = pd.concat(curve_frames, ignore_index=True, sort=False) if curve_frames else pd.DataFrame()
    lot_deltas = pd.concat(lot_delta_frames, ignore_index=True, sort=False) if lot_delta_frames else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)
    return probe_starts, summary, curves, lot_deltas


def _decision(probe_starts: pd.DataFrame, summary: pd.DataFrame, lot_deltas: pd.DataFrame) -> dict[str, Any]:
    stage013 = summary[summary["variant"].eq("stage013_daily_cold_start_engine")]
    stage041 = summary[summary["variant"].eq("stage041_daily_cold_start_stage039_ai_top8_proxy")]
    stage013_negative_starts = int(stage013["negative_count"].gt(0).sum()) if not stage013.empty else 0
    stage041_negative_starts = int(stage041["negative_count"].gt(0).sum()) if not stage041.empty else 0
    if stage013_negative_starts > 0:
        decision = "stage041_selected_daily_cold_start_confirms_left_tail_not_only_subwindow_artifact"
        continue_after = "有。独立日级冷启动探针也有负结束日，下一步应扩大日级 start 样本或转账户外层/外生源。"
    else:
        decision = "stage041_selected_daily_cold_start_does_not_confirm_stage013_left_tail_on_probe_dates"
        continue_after = "有。探针日期未复现 Stage013 左尾，下一步应重新定义目标审计为真实日级冷启动，而不是半年曲线子窗口。"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "decision": decision,
        "audit_type": "selected_exact_daily_cold_start_true_engine_probe_with_stage039_closed_lot_proxy",
        "probe_start_count": int(len(probe_starts)),
        "stage013_negative_probe_start_count": stage013_negative_starts,
        "stage041_negative_probe_start_count": stage041_negative_starts,
        "stage013_min_return_pct": float(stage013["min_return_pct"].min()) if not stage013.empty else np.nan,
        "stage041_min_return_pct": float(stage041["min_return_pct"].min()) if not stage041.empty else np.nan,
        "stage013_to_final_min_return_pct": float(stage013["to_final_return_pct"].min()) if not stage013.empty else np.nan,
        "stage041_to_final_min_return_pct": float(stage041["to_final_return_pct"].min()) if not stage041.empty else np.nan,
        "selected_lots": int(len(lot_deltas)),
        "selected_realized_pnl": float(pd.to_numeric(lot_deltas.get("realized_pnl", pd.Series(dtype=float)), errors="coerce").sum())
        if not lot_deltas.empty
        else 0.0,
        "stage041_proxy_delta_pnl": float(
            pd.to_numeric(lot_deltas.get("stage039_proxy_delta_pnl", pd.Series(dtype=float)), errors="coerce").sum()
        )
        if not lot_deltas.empty
        else 0.0,
        "strategy_changed": False,
        "true_engine": True,
        "proxy_overlay": True,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "趋势跟随和 managed futures 文献都强调滚动回撤会持续较久；因此 Stage041 不做参数修复，"
            "先用精确日级冷启动确认严格子窗口失败是否是真实可复验问题。"
        ),
        "overfit_reflection_before": (
            "否。探针日期来自 Stage040 失败窗口，不新增交易规则、不按日期优化，只检验审计口径。"
        ),
        "overfit_reflection_after": (
            "否。本阶段结果不能用于按这些日期写规则；只能决定是否扩大真实日级冷启动审计。"
        ),
        "continue_value_before": "有。若子窗口失败不是日级冷启动失败，后续优化方向会完全不同。",
        "continue_value_after": continue_after,
        "outputs": {
            "probe_starts": str(PROBE_STARTS_PATH),
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "lot_deltas": str(LOT_DELTAS_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(decision: dict[str, Any], probe_starts: pd.DataFrame, summary: pd.DataFrame, lot_deltas: pd.DataFrame) -> None:
    lines = [
        "# Stage041 - 关键日期独立日级冷启动探针",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：选定日期真实 Stage013 引擎冷启动 + Stage039 closed-lot proxy；不改 C9，不连接 CTP，不调用下单。",
        "",
        "## 核心结果",
        "",
        f"- 探针起点数：`{decision['probe_start_count']}`。",
        f"- Stage013 有负结束日的探针起点：`{decision['stage013_negative_probe_start_count']}`。",
        f"- Stage041 proxy 有负结束日的探针起点：`{decision['stage041_negative_probe_start_count']}`。",
        f"- Stage013 探针最差收益：`{decision['stage013_min_return_pct']:.4f}%`；到 2026-06-30 最差 `{decision['stage013_to_final_min_return_pct']:.4f}%`。",
        f"- Stage041 proxy 探针最差收益：`{decision['stage041_min_return_pct']:.4f}%`；到 2026-06-30 最差 `{decision['stage041_to_final_min_return_pct']:.4f}%`。",
        f"- Stage041 选中 lots：`{decision['selected_lots']}`；proxy delta `{decision['stage041_proxy_delta_pnl']:,.2f}`。",
        "",
        "## 探针起点",
        "",
        _md_table(probe_starts, max_rows=30),
        "",
        "## 探针审计",
        "",
        _md_table(summary, max_rows=40),
        "",
        "## lot delta 摘要",
        "",
        _md_table(
            lot_deltas[
                [
                    "requested_start",
                    "product",
                    "direction",
                    "entry_date",
                    "exit_date",
                    "realized_pnl",
                    "stage039_proxy_delta_pnl",
                ]
            ]
            if not lot_deltas.empty
            else lot_deltas,
            max_rows=30,
        ),
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], probe_starts: pd.DataFrame, summary: pd.DataFrame) -> Path:
    timestamp = datetime.now()
    path = STAGES_DIR / f"{timestamp:%Y%m%d_%H%M}_stage041_selected_daily_cold_start_probe.md"
    lines = [
        "# Stage041 - 关键日期独立日级冷启动探针",
        "",
        f"- 记录时间：`{timestamp.isoformat(timespec='minutes')}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 是否重要突破版本：`否`",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 本次版本变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage041_selected_daily_cold_start_probe.py`",
        f"- 新增参数：`PROBE_START_LIMIT={PROBE_START_LIMIT}`；诊断常量 `MIN_PERIOD_CALENDAR_DAYS=366`。",
        "- 修改参数：无，Stage013/Stage039/官方 C9 配置未改。",
        "- 删除参数：无。",
        "- 新增回测结果：关键日期 Stage013 真实日级冷启动探针 + Stage039 top8 closed-lot proxy。",
        "- 本阶段不连接 CTP，不调用订单 API，不触发 A/B。",
        "",
        "## 调研和判断结论",
        "",
        f"- {decision['external_research_judgment']}",
        "",
        "## 结果",
        "",
        f"- 探针起点数：`{decision['probe_start_count']}`。",
        f"- Stage013 有负结束日的探针起点：`{decision['stage013_negative_probe_start_count']}`。",
        f"- Stage041 proxy 有负结束日的探针起点：`{decision['stage041_negative_probe_start_count']}`。",
        f"- Stage013 探针最差收益：`{decision['stage013_min_return_pct']:.4f}%`。",
        f"- Stage041 proxy 探针最差收益：`{decision['stage041_min_return_pct']:.4f}%`。",
        f"- Stage041 proxy delta：`{decision['stage041_proxy_delta_pnl']:,.2f}`。",
        "",
        "## 探针起点",
        "",
        _md_table(probe_starts, max_rows=30),
        "",
        "## 探针审计",
        "",
        _md_table(summary, max_rows=40),
        "",
        "## 输出",
        "",
        f"- probe_starts：`{PROBE_STARTS_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- curves：`{CURVES_PATH}`",
        f"- lot_deltas：`{LOT_DELTAS_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- report：`{REPORT_PATH}`",
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    probe_starts, summary, curves, lot_deltas = _run_probe()
    decision = _decision(probe_starts, summary, lot_deltas)
    probe_starts.to_csv(PROBE_STARTS_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    lot_deltas.to_csv(LOT_DELTAS_PATH, index=False, encoding="utf-8-sig")
    _write_report(decision, probe_starts, summary, lot_deltas)
    stage_record = _write_stage_record(decision, probe_starts, summary)
    decision["stage_record_path"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
