from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage039"
MODEL_TAG = "stage039_full_market_ai_top8_proxy_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage039_full_market_ai_top8_proxy"
DECISION_IF_IMPROVED = "stage039_full_market_ai_top8_proxy_improves_not_yet_goal"
DECISION_IF_MET = "stage039_full_market_ai_top8_proxy_meets_goal_requires_true_engine"
DECISION_IF_FAILED = "stage039_full_market_ai_top8_proxy_not_enough_no_param_rescue"

ADD_RISK_FRACTION = 0.25
CAPITAL = 150000.0
EPS = 1e-9

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage039_full_market_ai_top8_proxy"
STAGES_DIR = LINE_DIR / "stages"

STAGE006_OUTPUT_DIR = LINE_DIR / "outputs" / "stage006_current_quality_feature_binder"
STAGE013_OUTPUT_DIR = LINE_DIR / "outputs" / "stage013_account_state_pilot_gate_engine"
STAGE019_OUTPUT_DIR = LINE_DIR / "outputs" / "stage019_stage018_regime_gate_failure_attribution"
STAGE021_OUTPUT_DIR = LINE_DIR / "outputs" / "stage021_full_market_consensus_jd_proxy"

STAGE006_PREFIX = "rebuilt_c9_stage006_current_quality_feature_binder"
STAGE006_TAG = "stage006_current_quality_feature_binder_v1"
STAGE013_PREFIX = "rebuilt_c9_stage013_account_state_pilot_gate_engine"
STAGE013_TAG = "stage013_account_state_pilot_gate_engine_v1"
STAGE019_PREFIX = "rebuilt_c9_stage019_stage018_regime_gate_failure_attribution"
STAGE019_TAG = "stage019_stage018_regime_gate_failure_attribution_v1"
STAGE021_PREFIX = "rebuilt_c9_stage021_full_market_consensus_jd_proxy"
STAGE021_TAG = "stage021_full_market_consensus_jd_proxy_v1"

BASE_STAGE006_SUMMARY_PATH = STAGE006_OUTPUT_DIR / f"{STAGE006_PREFIX}_summary_{STAGE006_TAG}.csv"
STAGE013_CURVES_PATH = STAGE013_OUTPUT_DIR / f"{STAGE013_PREFIX}_curves_{STAGE013_TAG}.csv"
STAGE013_SUMMARY_PATH = STAGE013_OUTPUT_DIR / f"{STAGE013_PREFIX}_summary_{STAGE013_TAG}.csv"
STAGE013_CLOSED_LOTS_PATH = STAGE019_OUTPUT_DIR / f"{STAGE019_PREFIX}_stage013_rebuilt_closed_lots_{STAGE019_TAG}.csv"
PREDICTIONS_PATH = STAGE021_OUTPUT_DIR / f"{STAGE021_PREFIX}_full_market_predictions_ranked_{STAGE021_TAG}.csv"

LOT_DELTAS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_deltas_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
GOAL_AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_aggregate_{MODEL_TAG}.csv"
GOAL_TO_FINAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_to_final_windows_{MODEL_TAG}.csv"
GOAL_FIXED_HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_fixed_horizon_windows_{MODEL_TAG}.csv"
GOAL_WORST_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_worst_windows_{MODEL_TAG}.csv"
RETENTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_retention_{MODEL_TAG}.csv"
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
        return None if math.isnan(number) or math.isinf(number) else number
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


def _to_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").fillna(0).ne(0)
    text = series.fillna("").astype(str).str.strip().str.lower()
    return text.isin({"1", "1.0", "true", "yes", "y"})


def _product_key(value: Any) -> str:
    return str(value or "").strip().lower()


def _closed_lot_product_key(product: Any, vt_symbol: Any) -> str:
    product_text = str(product or "").strip()
    if "." in product_text:
        return product_text.lower()
    vt_text = str(vt_symbol or "").strip()
    if "." not in vt_text or not product_text:
        return product_text.lower()
    exchange = vt_text.rsplit(".", 1)[-1]
    return f"{product_text}.{exchange}".lower()


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


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def attach_predictions_to_lots(lots: pd.DataFrame, predictions: pd.DataFrame) -> pd.DataFrame:
    result = lots.copy()
    if result.empty:
        return result
    result["entry_date"] = pd.to_datetime(result["entry_date"], errors="coerce").dt.normalize()
    if "product_key" not in result.columns:
        result["product_key"] = [
            _closed_lot_product_key(product, vt_symbol)
            for product, vt_symbol in zip(result.get("product", ""), result.get("vt_symbol", ""), strict=False)
        ]
    preds = predictions.copy()
    preds["eval_date"] = pd.to_datetime(preds["eval_date"], errors="coerce").dt.normalize()
    preds["product_key"] = preds["product_vt_symbol"].map(_product_key)
    preds = preds.dropna(subset=["eval_date"]).sort_values(["product_key", "eval_date"])
    prediction_columns = [column for column in preds.columns if column != "product_key"]
    frames: list[pd.DataFrame] = []
    for product_key, group in result.sort_values(["product_key", "entry_date"]).groupby("product_key", sort=False):
        right = preds[preds["product_key"].eq(product_key)].sort_values("eval_date").drop(columns=["product_key"])
        if right.empty:
            out = group.copy()
            for column in prediction_columns:
                if column not in out.columns:
                    out[column] = np.nan
        else:
            out = pd.merge_asof(
                group.sort_values("entry_date"),
                right,
                left_on="entry_date",
                right_on="eval_date",
                direction="backward",
                allow_exact_matches=True,
            )
        frames.append(out)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def select_ai_top8_lots(lots: pd.DataFrame) -> pd.DataFrame:
    if "stage021_ai_top8" not in lots.columns:
        return lots.iloc[0:0].copy()
    selected = lots[_to_bool(lots["stage021_ai_top8"])].copy()
    return selected.reset_index(drop=True)


def _build_lot_deltas() -> tuple[pd.DataFrame, dict[str, Any]]:
    closed = _read_csv(STAGE013_CLOSED_LOTS_PATH, parse_dates=["entry_date", "exit_date"])
    predictions = _read_csv(PREDICTIONS_PATH, parse_dates=["eval_date"])
    closed["requested_start_month"] = closed["requested_start_month"].astype(str)
    closed["entry_date"] = pd.to_datetime(closed["entry_date"], errors="coerce").dt.normalize()
    closed["exit_date"] = pd.to_datetime(closed["exit_date"], errors="coerce").dt.normalize()
    closed["realized_pnl"] = pd.to_numeric(closed["realized_pnl"], errors="coerce").fillna(0.0)
    attached = attach_predictions_to_lots(closed, predictions)
    attached["stage039_prediction_matched"] = attached["eval_date"].notna()
    for column in ["stage021_ai_top8", "stage021_simple_top8", "stage021_consensus_top8"]:
        if column in attached.columns:
            attached[column] = _to_bool(attached[column])
        else:
            attached[column] = False
    attached["stage039_selected_for_ai_top8_proxy"] = attached["stage021_ai_top8"]
    attached["stage039_add_risk_fraction"] = ADD_RISK_FRACTION
    attached["stage039_proxy_delta_pnl"] = np.where(
        attached["stage039_selected_for_ai_top8_proxy"],
        attached["realized_pnl"] * ADD_RISK_FRACTION,
        0.0,
    )
    selected = select_ai_top8_lots(attached)
    keep = [
        "requested_start_month",
        "lot_id",
        "open_trade_id",
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "exit_date",
        "volume",
        "realized_pnl",
        "r_multiple",
        "ai_product_pool_rank",
        "ai_product_pool_score",
        "eval_date",
        "predicted_product_suitability_probability",
        "simple_trend_suitability_score",
        "ai_rank_desc",
        "simple_rank_desc",
        "stage021_ai_top8",
        "stage021_simple_top8",
        "stage021_consensus_top8",
        "stage039_prediction_matched",
        "stage039_add_risk_fraction",
        "stage039_proxy_delta_pnl",
    ]
    audit = {
        "stage013_closed_lot_count": int(len(closed)),
        "prediction_matched_lot_count": int(attached["stage039_prediction_matched"].sum()),
        "prediction_match_rate_pct": float(attached["stage039_prediction_matched"].mean() * 100.0) if len(attached) else np.nan,
        "selected_lots": int(len(selected)),
        "selected_realized_pnl": float(selected["realized_pnl"].sum()) if len(selected) else 0.0,
        "total_proxy_delta_pnl": float(selected["stage039_proxy_delta_pnl"].sum()) if len(selected) else 0.0,
        "selected_source_count": int(selected["requested_start_month"].nunique()) if len(selected) else 0,
        "selected_product_count": int(selected["product"].nunique()) if "product" in selected.columns and len(selected) else 0,
        "selected_year_count": int(pd.to_datetime(selected["entry_date"], errors="coerce").dt.year.nunique())
        if len(selected)
        else 0,
    }
    return selected[[column for column in keep if column in selected.columns]].reset_index(drop=True), audit


def _build_proxy_curves(base_curves: pd.DataFrame, lot_deltas: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    curves = base_curves.copy()
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["requested_start_month"] = curves["requested_start_month"].astype(str)
    curves["account_equity"] = pd.to_numeric(curves["account_equity"], errors="coerce")
    daily_delta = (
        lot_deltas.groupby(["requested_start_month", "exit_date"], dropna=False)["stage039_proxy_delta_pnl"]
        .sum()
        .reset_index()
        if not lot_deltas.empty
        else pd.DataFrame(columns=["requested_start_month", "exit_date", "stage039_proxy_delta_pnl"])
    )
    merged = curves.merge(
        daily_delta.rename(columns={"exit_date": "date", "stage039_proxy_delta_pnl": "stage039_daily_delta"}),
        on=["requested_start_month", "date"],
        how="left",
    )
    merged["stage039_daily_delta"] = pd.to_numeric(merged["stage039_daily_delta"], errors="coerce").fillna(0.0)
    frames: list[pd.DataFrame] = []
    for _, group in merged.groupby("requested_start_month", sort=True):
        g = group.sort_values("date").copy()
        g["stage039_cum_delta"] = g["stage039_daily_delta"].cumsum()
        g["stage039_account_equity"] = g["account_equity"] + g["stage039_cum_delta"]
        g["stage039_nav"] = g["stage039_account_equity"] / CAPITAL
        g["stage039_drawdown_pct"] = _drawdown_pct(g["stage039_account_equity"])
        frames.append(g)
    proxy = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    curve_dates = set(zip(curves["requested_start_month"].astype(str), curves["date"]))
    unmatched = 0
    for row in daily_delta.to_dict("records"):
        if (str(row["requested_start_month"]), row["exit_date"]) not in curve_dates:
            unmatched += 1
    return proxy, unmatched


def _summarize_curve(curve: pd.DataFrame, equity_column: str, variant: str) -> dict[str, Any]:
    data = curve.sort_values("date").copy()
    equity = pd.to_numeric(data[equity_column], errors="coerce")
    return {
        "variant": variant,
        "requested_start_month": str(data["requested_start_month"].iloc[0]),
        "actual_start": pd.Timestamp(data["date"].iloc[0]).date().isoformat(),
        "actual_end": pd.Timestamp(data["date"].iloc[-1]).date().isoformat(),
        "trading_days": int(len(data)),
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / CAPITAL - 1.0) * 100.0),
        "max_dd_pct": float(_drawdown_pct(equity).min()),
        "sharpe": _sharpe_from_equity(equity),
    }


def _summary(proxy_curves: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, group in proxy_curves.groupby("requested_start_month"):
        rows.append(_summarize_curve(group, "account_equity", "stage013_engine"))
        rows.append(_summarize_curve(group, "stage039_account_equity", "stage039_full_market_ai_top8_proxy"))
    return pd.DataFrame(rows).sort_values(["variant", "requested_start_month"]).reset_index(drop=True)


def _wide_summary(summary: pd.DataFrame) -> pd.DataFrame:
    pivots = []
    for metric in ["end_equity", "total_return_pct", "max_dd_pct", "sharpe"]:
        pivot = summary.pivot(index="requested_start_month", columns="variant", values=metric)
        pivot.columns = [f"{metric}_{column}" for column in pivot.columns]
        pivots.append(pivot)
    wide = pd.concat(pivots, axis=1).reset_index()
    wide["return_delta_pp_stage039_vs_stage013"] = (
        wide["total_return_pct_stage039_full_market_ai_top8_proxy"] - wide["total_return_pct_stage013_engine"]
    )
    wide["maxdd_delta_pp_stage039_vs_stage013"] = (
        wide["max_dd_pct_stage039_full_market_ai_top8_proxy"] - wide["max_dd_pct_stage013_engine"]
    )
    return wide.sort_values("requested_start_month").reset_index(drop=True)


def _goal_audit(proxy_curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    import stage009_dense_start_goal_audit as s009

    parts = []
    for variant, column in [
        ("stage013_engine", "account_equity"),
        ("stage039_full_market_ai_top8_proxy", "stage039_account_equity"),
    ]:
        frame = proxy_curves[["requested_start_month", "date", column]].copy()
        frame.rename(columns={column: "equity"}, inplace=True)
        frame["variant"] = variant
        parts.append(frame)
    curves = pd.concat(parts, ignore_index=True, sort=False)
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["equity"] = pd.to_numeric(curves["equity"], errors="coerce")
    curves = curves.dropna(subset=["date", "equity"]).sort_values(["variant", "requested_start_month", "date"])
    return s009._run_audit(curves)


def _retention(summary: pd.DataFrame) -> pd.DataFrame:
    base = _read_csv(BASE_STAGE006_SUMMARY_PATH)
    base = base[["requested_start_month", "total_return_pct"]].rename(
        columns={"total_return_pct": "total_return_pct_base_stage006"}
    )
    wide = _wide_summary(summary)
    merged = base.merge(wide, on="requested_start_month", how="inner")
    merged["stage039_vs_base_stage006_return_ratio"] = (
        merged["total_return_pct_stage039_full_market_ai_top8_proxy"]
        / pd.to_numeric(merged["total_return_pct_base_stage006"], errors="coerce").replace(0.0, np.nan)
    )
    merged["stage039_vs_stage013_return_ratio"] = (
        merged["total_return_pct_stage039_full_market_ai_top8_proxy"]
        / pd.to_numeric(merged["total_return_pct_stage013_engine"], errors="coerce").replace(0.0, np.nan)
    )
    merged["passes_80pct_retention_vs_base_stage006"] = merged["stage039_vs_base_stage006_return_ratio"].ge(0.80).astype("int64")
    merged["passes_80pct_retention_vs_stage013"] = merged["stage039_vs_stage013_return_ratio"].ge(0.80).astype("int64")
    return merged


def _strict_metrics(aggregate: pd.DataFrame, variant: str) -> dict[str, Any]:
    all_gt1y = aggregate[aggregate["variant"].eq(variant) & aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")]
    final = aggregate[aggregate["variant"].eq(variant) & aggregate["audit_scope"].eq("start_to_2026_06_30_only")]
    return {
        f"{variant}_all_gt1y_window_count": int(all_gt1y["window_count"].sum()) if not all_gt1y.empty else 0,
        f"{variant}_all_gt1y_negative_count": int(all_gt1y["negative_count"].sum()) if not all_gt1y.empty else 0,
        f"{variant}_all_gt1y_min_return_pct": float(all_gt1y["min_return_pct"].min()) if not all_gt1y.empty else np.nan,
        f"{variant}_to_final_negative_count": int(final["negative_count"].sum()) if not final.empty else 0,
        f"{variant}_to_final_min_return_pct": float(final["min_return_pct"].min()) if not final.empty else np.nan,
    }


def _decision(
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    retention: pd.DataFrame,
    audit: dict[str, Any],
    unmatched_delta_dates: int,
) -> dict[str, Any]:
    wide = _wide_summary(summary)
    result: dict[str, Any] = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "selector": "full_market_ai_top8",
        "add_risk_fraction": ADD_RISK_FRACTION,
        "audit_type": "stage013_closed_lot_read_only_full_market_ai_top8_add_risk_proxy",
        **audit,
        "unmatched_delta_dates": int(unmatched_delta_dates),
        "sample_count": int(wide["requested_start_month"].nunique()),
        "stage039_min_return_pct": float(wide["total_return_pct_stage039_full_market_ai_top8_proxy"].min()),
        "stage039_median_return_pct": float(wide["total_return_pct_stage039_full_market_ai_top8_proxy"].median()),
        "stage039_worst_max_dd_pct": float(wide["max_dd_pct_stage039_full_market_ai_top8_proxy"].min()),
        "stage039_median_max_dd_pct": float(wide["max_dd_pct_stage039_full_market_ai_top8_proxy"].median()),
        "return_improved_count_vs_stage013": int(wide["return_delta_pp_stage039_vs_stage013"].gt(EPS).sum()),
        "return_unchanged_count_vs_stage013": int(wide["return_delta_pp_stage039_vs_stage013"].abs().le(EPS).sum()),
        "return_worse_count_vs_stage013": int(wide["return_delta_pp_stage039_vs_stage013"].lt(-EPS).sum()),
        "maxdd_improved_count_vs_stage013": int(wide["maxdd_delta_pp_stage039_vs_stage013"].gt(EPS).sum()),
        "maxdd_unchanged_count_vs_stage013": int(wide["maxdd_delta_pp_stage039_vs_stage013"].abs().le(EPS).sum()),
        "maxdd_worse_count_vs_stage013": int(wide["maxdd_delta_pp_stage039_vs_stage013"].lt(-EPS).sum()),
        "retention_vs_base_stage006_pass_count": int(retention["passes_80pct_retention_vs_base_stage006"].sum()),
        "retention_vs_stage013_pass_count": int(retention["passes_80pct_retention_vs_stage013"].sum()),
        "retention_rows": int(len(retention)),
        "strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "金融 ML / commodity ML 文献支持用 OOS 稳定的二级质量信号做 bet sizing；PBO/DSR 警告禁止多次扫 topN 和阈值。"
            "Stage039 因此只验证 Stage038 排名第一的 full_market_ai_top8，固定 25% 非挤占风险。"
        ),
        "overfit_reflection_before": (
            "否。只冻结 Stage038 排名第一且 OOS 通过的 `full_market_ai_top8`，不扫 topN、simple 共识、倍率或年份。"
        ),
        "continue_value_before": (
            "有。用户目标包含 AI 选品优化和超高质量信号加风险，必须用目标窗口审计确认该信号是否有策略价值。"
        ),
        "overfit_reflection_after": (
            "否。本阶段无参数搜索；若失败后改 topN、组合 OI、筛年份或按产品救参就是过拟合。"
        ),
    }
    result.update(_strict_metrics(aggregate, "stage013_engine"))
    result.update(_strict_metrics(aggregate, "stage039_full_market_ai_top8_proxy"))
    strict_negative = result["stage039_full_market_ai_top8_proxy_all_gt1y_negative_count"]
    stage013_negative = result["stage013_engine_all_gt1y_negative_count"]
    retention_full = result["retention_vs_base_stage006_pass_count"] == result["retention_rows"]
    if strict_negative == 0 and retention_full:
        decision = DECISION_IF_MET
        continue_after = "有。proxy 达到目标形状，下一步也必须写真实引擎验真，不能直接上线。"
    elif strict_negative < stage013_negative and retention_full:
        decision = DECISION_IF_IMPROVED
        continue_after = "有但未达标。该 proxy 可作为候选信息源保留，下一步要归因剩余负窗口，不能调参救援。"
    else:
        decision = DECISION_IF_FAILED
        continue_after = "有限。若没有改善严格负窗口或收益保留失败，就不应继续在 full_market_ai_top8 上调参。"
    result["decision"] = decision
    result["continue_value_after"] = continue_after
    result["outputs"] = {
        "lot_deltas": str(LOT_DELTAS_PATH),
        "curves": str(CURVES_PATH),
        "summary": str(SUMMARY_PATH),
        "goal_aggregate": str(GOAL_AGGREGATE_PATH),
        "goal_to_final": str(GOAL_TO_FINAL_PATH),
        "goal_fixed_horizon": str(GOAL_FIXED_HORIZON_PATH),
        "goal_worst_windows": str(GOAL_WORST_WINDOWS_PATH),
        "retention": str(RETENTION_PATH),
        "decision": str(DECISION_PATH),
        "report": str(REPORT_PATH),
    }
    return result


def _write_report(decision: dict[str, Any], summary: pd.DataFrame, aggregate: pd.DataFrame, retention: pd.DataFrame) -> None:
    strict = aggregate[
        aggregate["variant"].eq("stage039_full_market_ai_top8_proxy")
        & aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")
    ]
    wide = _wide_summary(summary)
    lines = [
        "# Stage039 - full-market AI top8 非挤占加风险 proxy",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：closed-lot 只读上界 proxy；不是真实组合引擎，不改 C9，不连接 CTP，不调用下单。",
        f"- selector：`{decision['selector']}`",
        f"- 固定额外风险比例：`{ADD_RISK_FRACTION:.2%}`",
        "",
        "## 核心结果",
        "",
        f"- 选中 lots：`{decision['selected_lots']}`；selected realized PnL `{decision['selected_realized_pnl']:,.2f}`；proxy delta `{decision['total_proxy_delta_pnl']:,.2f}`。",
        f"- Stage039 严格任意 `>1` 年负窗口：`{decision['stage039_full_market_ai_top8_proxy_all_gt1y_negative_count']}` / `{decision['stage039_full_market_ai_top8_proxy_all_gt1y_window_count']}`；最差 `{decision['stage039_full_market_ai_top8_proxy_all_gt1y_min_return_pct']:.4f}%`。",
        f"- Stage013 严格任意 `>1` 年负窗口：`{decision['stage013_engine_all_gt1y_negative_count']}`。",
        f"- 到 `2026-06-30` 负窗口：`{decision['stage039_full_market_ai_top8_proxy_to_final_negative_count']}`；最差 `{decision['stage039_full_market_ai_top8_proxy_to_final_min_return_pct']:.4f}%`。",
        f"- 80% 收益保留 vs Stage006：`{decision['retention_vs_base_stage006_pass_count']}/{decision['retention_rows']}`；vs Stage013：`{decision['retention_vs_stage013_pass_count']}/{decision['retention_rows']}`。",
        f"- 收益改善/不变/变差 vs Stage013：`{decision['return_improved_count_vs_stage013']}/{decision['return_unchanged_count_vs_stage013']}/{decision['return_worse_count_vs_stage013']}`。",
        f"- 回撤改善/不变/变差 vs Stage013：`{decision['maxdd_improved_count_vs_stage013']}/{decision['maxdd_unchanged_count_vs_stage013']}/{decision['maxdd_worse_count_vs_stage013']}`。",
        "",
        "## 多起点摘要",
        "",
        _md_table(
            wide[
                [
                    "requested_start_month",
                    "total_return_pct_stage013_engine",
                    "total_return_pct_stage039_full_market_ai_top8_proxy",
                    "return_delta_pp_stage039_vs_stage013",
                    "max_dd_pct_stage013_engine",
                    "max_dd_pct_stage039_full_market_ai_top8_proxy",
                    "maxdd_delta_pp_stage039_vs_stage013",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## 严格目标审计",
        "",
        _md_table(strict, max_rows=30),
        "",
        "## 收益保留",
        "",
        _md_table(
            retention[
                [
                    "requested_start_month",
                    "stage039_vs_base_stage006_return_ratio",
                    "stage039_vs_stage013_return_ratio",
                    "passes_80pct_retention_vs_base_stage006",
                    "passes_80pct_retention_vs_stage013",
                ]
            ],
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


def _write_stage_record(decision: dict[str, Any], summary: pd.DataFrame, aggregate: pd.DataFrame, retention: pd.DataFrame) -> Path:
    timestamp = datetime.now()
    path = STAGES_DIR / f"{timestamp:%Y%m%d_%H%M}_stage039_full_market_ai_top8_proxy.md"
    strict = aggregate[
        aggregate["variant"].eq("stage039_full_market_ai_top8_proxy")
        & aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")
    ]
    wide = _wide_summary(summary)
    lines = [
        "# Stage039 - full-market AI top8 非挤占加风险 proxy",
        "",
        f"- 记录时间：`{timestamp.isoformat(timespec='minutes')}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 是否重要突破版本：`否`",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 本次版本变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage039_full_market_ai_top8_proxy.py`",
        "- 新增参数：`selector=full_market_ai_top8`、`ADD_RISK_FRACTION=0.25`。",
        "- 修改参数：无，Stage013/Stage006/官方 C9 配置未改。",
        "- 删除参数：无。",
        "- 新增回测结果：closed-lot 只读 proxy 目标审计；不是真实组合引擎。",
        "- 本阶段不连接 CTP，不调用订单 API，不触发 A/B。",
        "",
        "## 调研和判断结论",
        "",
        f"- {decision['external_research_judgment']}",
        "",
        "## 结果",
        "",
        f"- 选中 lots：`{decision['selected_lots']}`。",
        f"- selected realized PnL：`{decision['selected_realized_pnl']:,.2f}`。",
        f"- proxy delta：`{decision['total_proxy_delta_pnl']:,.2f}`。",
        f"- Stage039 严格任意 `>1` 年负窗口：`{decision['stage039_full_market_ai_top8_proxy_all_gt1y_negative_count']}` / `{decision['stage039_full_market_ai_top8_proxy_all_gt1y_window_count']}`。",
        f"- Stage039 严格最差收益：`{decision['stage039_full_market_ai_top8_proxy_all_gt1y_min_return_pct']:.4f}%`。",
        f"- 到 `2026-06-30` 负窗口：`{decision['stage039_full_market_ai_top8_proxy_to_final_negative_count']}`，最差 `{decision['stage039_full_market_ai_top8_proxy_to_final_min_return_pct']:.4f}%`。",
        f"- 收益保留 vs Stage006：`{decision['retention_vs_base_stage006_pass_count']}/{decision['retention_rows']}`；vs Stage013：`{decision['retention_vs_stage013_pass_count']}/{decision['retention_rows']}`。",
        f"- 收益改善/不变/变差 vs Stage013：`{decision['return_improved_count_vs_stage013']}/{decision['return_unchanged_count_vs_stage013']}/{decision['return_worse_count_vs_stage013']}`。",
        f"- 回撤改善/不变/变差 vs Stage013：`{decision['maxdd_improved_count_vs_stage013']}/{decision['maxdd_unchanged_count_vs_stage013']}/{decision['maxdd_worse_count_vs_stage013']}`。",
        "",
        "## 多起点摘要",
        "",
        _md_table(
            wide[
                [
                    "requested_start_month",
                    "total_return_pct_stage013_engine",
                    "total_return_pct_stage039_full_market_ai_top8_proxy",
                    "return_delta_pp_stage039_vs_stage013",
                    "max_dd_pct_stage013_engine",
                    "max_dd_pct_stage039_full_market_ai_top8_proxy",
                ]
            ],
            max_rows=24,
        ),
        "",
        "## 严格目标摘要",
        "",
        _md_table(strict, max_rows=24),
        "",
        "## 输出",
        "",
        f"- lot_deltas：`{LOT_DELTAS_PATH}`",
        f"- curves：`{CURVES_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- goal_aggregate：`{GOAL_AGGREGATE_PATH}`",
        f"- retention：`{RETENTION_PATH}`",
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
    lot_deltas, audit = _build_lot_deltas()
    base_curves = _read_csv(STAGE013_CURVES_PATH, parse_dates=["date"])
    proxy_curves, unmatched = _build_proxy_curves(base_curves, lot_deltas)
    summary = _summary(proxy_curves)
    aggregate, to_final, fixed, worst = _goal_audit(proxy_curves)
    retention = _retention(summary)
    decision = _decision(summary, aggregate, retention, audit, unmatched)

    lot_deltas.to_csv(LOT_DELTAS_PATH, index=False, encoding="utf-8-sig")
    proxy_curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(GOAL_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    to_final.to_csv(GOAL_TO_FINAL_PATH, index=False, encoding="utf-8-sig")
    fixed.to_csv(GOAL_FIXED_HORIZON_PATH, index=False, encoding="utf-8-sig")
    worst.to_csv(GOAL_WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")
    _write_report(decision, summary, aggregate, retention)
    stage_record = _write_stage_record(decision, summary, aggregate, retention)
    decision["stage_record_path"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return decision


def main() -> None:
    print(json.dumps(_json_safe(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
