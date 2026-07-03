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

import stage009_dense_start_goal_audit as s009
import stage039_full_market_ai_top8_proxy as s039


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage052"
MODEL_TAG = "stage052_contract_oi_share_add_risk_proxy_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage052_contract_oi_share_add_risk_proxy"

SELECTOR = "contract_oi_share_ge50"
ADD_RISK_FRACTION = 0.25
CAPITAL = 150000.0
EPS = 1e-9

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage052_contract_oi_share_add_risk_proxy"
STAGES_DIR = LINE_DIR / "stages"

STAGE006_OUTPUT_DIR = LINE_DIR / "outputs" / "stage006_current_quality_feature_binder"
STAGE013_OUTPUT_DIR = LINE_DIR / "outputs" / "stage013_account_state_pilot_gate_engine"
STAGE019_OUTPUT_DIR = LINE_DIR / "outputs" / "stage019_stage018_regime_gate_failure_attribution"
STAGE051_OUTPUT_DIR = LINE_DIR / "outputs" / "stage051_contract_oi_repaired_rerun"

STAGE006_PREFIX = "rebuilt_c9_stage006_current_quality_feature_binder"
STAGE006_TAG = "stage006_current_quality_feature_binder_v1"
STAGE013_PREFIX = "rebuilt_c9_stage013_account_state_pilot_gate_engine"
STAGE013_TAG = "stage013_account_state_pilot_gate_engine_v1"
STAGE019_PREFIX = "rebuilt_c9_stage019_stage018_regime_gate_failure_attribution"
STAGE019_TAG = "stage019_stage018_regime_gate_failure_attribution_v1"
STAGE051_PREFIX = "rebuilt_c9_stage051_contract_oi_repaired_rerun"
STAGE051_TAG = "stage051_contract_oi_repaired_rerun_v1"

BASE_STAGE006_SUMMARY_PATH = STAGE006_OUTPUT_DIR / f"{STAGE006_PREFIX}_summary_{STAGE006_TAG}.csv"
STAGE013_CURVES_PATH = STAGE013_OUTPUT_DIR / f"{STAGE013_PREFIX}_curves_{STAGE013_TAG}.csv"
STAGE013_CLOSED_LOTS_PATH = STAGE019_OUTPUT_DIR / f"{STAGE019_PREFIX}_stage013_rebuilt_closed_lots_{STAGE019_TAG}.csv"
STAGE051_JOINED_PATH = STAGE051_OUTPUT_DIR / f"{STAGE051_PREFIX}_joined_feature_matrix_{STAGE051_TAG}.csv"

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


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _to_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    text = series.fillna(False).astype(str).str.lower()
    return text.isin({"1", "1.0", "true", "yes"})


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    return s039._drawdown_pct(equity)


def _sharpe_from_equity(equity: pd.Series) -> float:
    return s039._sharpe_from_equity(equity)


def select_contract_oi_share_ge50_entries(matrix: pd.DataFrame) -> pd.DataFrame:
    matched = _to_bool(matrix.get("contract_oi_matched", pd.Series(False, index=matrix.index)))
    selected = _to_bool(matrix.get(SELECTOR, pd.Series(False, index=matrix.index)))
    return matrix[matched & selected].copy().reset_index(drop=True)


def _contract_oi_by_open_trade(matrix: pd.DataFrame) -> pd.DataFrame:
    features = matrix.copy()
    features["requested_start_month"] = features["requested_start_month"].astype(str)
    features["open_trade_id"] = features["open_trade_id"].astype(str)
    bool_cols = [
        "contract_oi_matched",
        "contract_oi_share_ge50",
        "contract_oi_share_ge33",
        "contract_oi_top1",
        "contract_oi_top2",
        "contract_oi_top2_concentration_ge70",
        "mapping_main_oi_share_ge40",
    ]
    for column in bool_cols:
        if column in features.columns:
            features[column] = _to_bool(features[column]).astype("int64")
    date_cols = ["contract_oi_feature_date", "contract_oi_asof_date"]
    for column in date_cols:
        if column in features.columns:
            features[column] = pd.to_datetime(features[column], errors="coerce").dt.normalize()
    keep = [
        "requested_start_month",
        "open_trade_id",
        "contract_oi_matched",
        "contract_oi_contract_vt",
        "contract_oi_feature_date",
        "contract_oi_asof_date",
        "contract_oi_share",
        "contract_oi_rank",
        "contract_count",
        "top1_oi_share",
        "top2_cumulative_oi_share",
        "mapping_main_oi_share",
        "contract_oi_feature_age_days",
        "contract_oi_state",
        "contract_oi_share_ge50",
        "contract_oi_share_ge33",
        "contract_oi_top1",
        "contract_oi_top2",
        "contract_oi_top2_concentration_ge70",
        "mapping_main_oi_share_ge40",
    ]
    use = [column for column in keep if column in features.columns]
    return (
        features[use]
        .sort_values(["requested_start_month", "open_trade_id"])
        .drop_duplicates(["requested_start_month", "open_trade_id"], keep="last")
        .reset_index(drop=True)
    )


def _build_lot_deltas_from_frames(closed_lots: pd.DataFrame, feature_matrix: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    closed = closed_lots.copy()
    closed["requested_start_month"] = closed["requested_start_month"].astype(str)
    closed["open_trade_id"] = closed["open_trade_id"].astype(str)
    closed["entry_date"] = pd.to_datetime(closed["entry_date"], errors="coerce").dt.normalize()
    closed["exit_date"] = pd.to_datetime(closed["exit_date"], errors="coerce").dt.normalize()
    closed["realized_pnl"] = pd.to_numeric(closed["realized_pnl"], errors="coerce").fillna(0.0)

    features = _contract_oi_by_open_trade(feature_matrix)
    merged = closed.merge(features, on=["requested_start_month", "open_trade_id"], how="left")
    merged["stage052_oi_feature_matched"] = merged["contract_oi_matched"].notna()
    merged["stage052_selected_for_contract_oi_proxy"] = (
        pd.to_numeric(merged.get("contract_oi_matched"), errors="coerce").fillna(0).astype(int).eq(1)
        & pd.to_numeric(merged.get(SELECTOR), errors="coerce").fillna(0).astype(int).eq(1)
    )
    merged["stage052_add_risk_fraction"] = ADD_RISK_FRACTION
    merged["stage052_proxy_delta_pnl"] = np.where(
        merged["stage052_selected_for_contract_oi_proxy"],
        merged["realized_pnl"] * ADD_RISK_FRACTION,
        0.0,
    )
    selected = merged[merged["stage052_selected_for_contract_oi_proxy"]].copy()
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
        "contract_oi_contract_vt",
        "contract_oi_feature_date",
        "contract_oi_asof_date",
        "contract_oi_share",
        "contract_oi_rank",
        "contract_count",
        "top1_oi_share",
        "top2_cumulative_oi_share",
        "mapping_main_oi_share",
        "contract_oi_feature_age_days",
        "contract_oi_state",
        "contract_oi_share_ge50",
        "contract_oi_top2_concentration_ge70",
        "stage052_oi_feature_matched",
        "stage052_selected_for_contract_oi_proxy",
        "stage052_add_risk_fraction",
        "stage052_proxy_delta_pnl",
    ]
    audit = {
        "stage013_closed_lot_count": int(len(closed)),
        "stage051_feature_key_count": int(len(features)),
        "oi_feature_matched_lot_count": int(merged["stage052_oi_feature_matched"].sum()),
        "oi_feature_match_rate_pct": float(merged["stage052_oi_feature_matched"].mean() * 100.0) if len(merged) else np.nan,
        "selected_lots": int(len(selected)),
        "selected_realized_pnl": float(selected["realized_pnl"].sum()) if len(selected) else 0.0,
        "total_proxy_delta_pnl": float(selected["stage052_proxy_delta_pnl"].sum()) if len(selected) else 0.0,
        "selected_source_count": int(selected["requested_start_month"].nunique()) if len(selected) else 0,
        "selected_product_count": int(selected["product"].nunique()) if "product" in selected.columns and len(selected) else 0,
        "selected_year_count": int(pd.to_datetime(selected["entry_date"], errors="coerce").dt.year.nunique()) if len(selected) else 0,
    }
    return selected[[column for column in keep if column in selected.columns]].reset_index(drop=True), audit


def _build_lot_deltas() -> tuple[pd.DataFrame, dict[str, Any]]:
    closed = _read_csv(STAGE013_CLOSED_LOTS_PATH, parse_dates=["entry_date", "exit_date"])
    matrix = _read_csv(STAGE051_JOINED_PATH, parse_dates=["entry_date", "exit_date"])
    return _build_lot_deltas_from_frames(closed, matrix)


def _build_proxy_curves(base_curves: pd.DataFrame, lot_deltas: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    curves = base_curves.copy()
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["requested_start_month"] = curves["requested_start_month"].astype(str)
    curves["account_equity"] = pd.to_numeric(curves["account_equity"], errors="coerce")
    daily_delta = (
        lot_deltas.groupby(["requested_start_month", "exit_date"], dropna=False)["stage052_proxy_delta_pnl"]
        .sum()
        .reset_index()
        if not lot_deltas.empty
        else pd.DataFrame(columns=["requested_start_month", "exit_date", "stage052_proxy_delta_pnl"])
    )
    merged = curves.merge(
        daily_delta.rename(columns={"exit_date": "date", "stage052_proxy_delta_pnl": "stage052_daily_delta"}),
        on=["requested_start_month", "date"],
        how="left",
    )
    merged["stage052_daily_delta"] = pd.to_numeric(merged["stage052_daily_delta"], errors="coerce").fillna(0.0)
    frames: list[pd.DataFrame] = []
    for _, group in merged.groupby("requested_start_month", sort=True):
        g = group.sort_values("date").copy()
        g["stage052_cum_delta"] = g["stage052_daily_delta"].cumsum()
        g["stage052_account_equity"] = g["account_equity"] + g["stage052_cum_delta"]
        g["stage052_nav"] = g["stage052_account_equity"] / CAPITAL
        g["stage052_drawdown_pct"] = _drawdown_pct(g["stage052_account_equity"])
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
        rows.append(
            _summarize_curve(
                group,
                "stage052_account_equity",
                "stage052_contract_oi_share_ge50_add_risk_proxy",
            )
        )
    return pd.DataFrame(rows).sort_values(["variant", "requested_start_month"]).reset_index(drop=True)


def _wide_summary(summary: pd.DataFrame) -> pd.DataFrame:
    pivots = []
    for metric in ["end_equity", "total_return_pct", "max_dd_pct", "sharpe"]:
        pivot = summary.pivot(index="requested_start_month", columns="variant", values=metric)
        pivot.columns = [f"{metric}_{column}" for column in pivot.columns]
        pivots.append(pivot)
    wide = pd.concat(pivots, axis=1).reset_index()
    wide["return_delta_pp_stage052_vs_stage013"] = (
        wide["total_return_pct_stage052_contract_oi_share_ge50_add_risk_proxy"]
        - wide["total_return_pct_stage013_engine"]
    )
    wide["maxdd_delta_pp_stage052_vs_stage013"] = (
        wide["max_dd_pct_stage052_contract_oi_share_ge50_add_risk_proxy"]
        - wide["max_dd_pct_stage013_engine"]
    )
    return wide.sort_values("requested_start_month").reset_index(drop=True)


def _goal_audit(proxy_curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    parts = []
    for variant, column in [
        ("stage013_engine", "account_equity"),
        ("stage052_contract_oi_share_ge50_add_risk_proxy", "stage052_account_equity"),
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
    merged["stage052_vs_base_stage006_return_ratio"] = (
        merged["total_return_pct_stage052_contract_oi_share_ge50_add_risk_proxy"]
        / pd.to_numeric(merged["total_return_pct_base_stage006"], errors="coerce").replace(0.0, np.nan)
    )
    merged["stage052_vs_stage013_return_ratio"] = (
        merged["total_return_pct_stage052_contract_oi_share_ge50_add_risk_proxy"]
        / pd.to_numeric(merged["total_return_pct_stage013_engine"], errors="coerce").replace(0.0, np.nan)
    )
    merged["passes_80pct_retention_vs_base_stage006"] = merged["stage052_vs_base_stage006_return_ratio"].ge(0.80).astype("int64")
    merged["passes_80pct_retention_vs_stage013"] = merged["stage052_vs_stage013_return_ratio"].ge(0.80).astype("int64")
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
        "selector": SELECTOR,
        "add_risk_fraction": ADD_RISK_FRACTION,
        "audit_type": "stage013_closed_lot_read_only_contract_oi_share_add_risk_proxy",
        **audit,
        "unmatched_delta_dates": int(unmatched_delta_dates),
        "sample_count": int(wide["requested_start_month"].nunique()),
        "stage052_min_return_pct": float(wide["total_return_pct_stage052_contract_oi_share_ge50_add_risk_proxy"].min()),
        "stage052_median_return_pct": float(wide["total_return_pct_stage052_contract_oi_share_ge50_add_risk_proxy"].median()),
        "stage052_worst_max_dd_pct": float(wide["max_dd_pct_stage052_contract_oi_share_ge50_add_risk_proxy"].min()),
        "stage052_median_max_dd_pct": float(wide["max_dd_pct_stage052_contract_oi_share_ge50_add_risk_proxy"].median()),
        "return_improved_count_vs_stage013": int(wide["return_delta_pp_stage052_vs_stage013"].gt(EPS).sum()),
        "return_unchanged_count_vs_stage013": int(wide["return_delta_pp_stage052_vs_stage013"].abs().le(EPS).sum()),
        "return_worse_count_vs_stage013": int(wide["return_delta_pp_stage052_vs_stage013"].lt(-EPS).sum()),
        "maxdd_improved_count_vs_stage013": int(wide["maxdd_delta_pp_stage052_vs_stage013"].gt(EPS).sum()),
        "maxdd_unchanged_count_vs_stage013": int(wide["maxdd_delta_pp_stage052_vs_stage013"].abs().le(EPS).sum()),
        "maxdd_worse_count_vs_stage013": int(wide["maxdd_delta_pp_stage052_vs_stage013"].lt(-EPS).sum()),
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
            "CME/CFTC/Databento 资料都把 open interest 视作市场参与度、持仓集中和换月/连续合约构造的重要信息。"
            "Stage052 因此只把 `contract_oi_share_ge50` 当流动性/换月质量条件做 fixed proxy，不把它直接视为 alpha。"
        ),
        "overfit_reflection_before": (
            "否。Stage052 冻结 Stage051 第一稳定条件 `contract_oi_share_ge50` 和固定 25% 非挤占风险，不扫 OI 阈值。"
        ),
        "continue_value_before": (
            "有。Stage051 已清源缺口，必须验证 OI 集中度从候选级 PnL lift 落到组合目标路径后是否仍有价值。"
        ),
        "overfit_reflection_after": (
            "否。本阶段仍是只读 proxy；若失败后改 `0.33/0.50/0.70`、品种、年份或方向就是过拟合。"
        ),
    }
    result.update(_strict_metrics(aggregate, "stage013_engine"))
    result.update(_strict_metrics(aggregate, "stage052_contract_oi_share_ge50_add_risk_proxy"))
    strict_negative = result["stage052_contract_oi_share_ge50_add_risk_proxy_all_gt1y_negative_count"]
    stage013_negative = result["stage013_engine_all_gt1y_negative_count"]
    retention_full = result["retention_vs_base_stage006_pass_count"] == result["retention_rows"]
    if strict_negative == 0 and retention_full:
        decision = "stage052_contract_oi_share_proxy_meets_goal_requires_true_engine"
        continue_after = "有。proxy 达到目标形状，下一步必须写真实引擎验真，不能直接上线。"
    elif strict_negative < stage013_negative and retention_full:
        decision = "stage052_contract_oi_share_proxy_partially_improves_not_goal"
        continue_after = "有但未达标。OI 集中度可保留为候选，下一步做日级冷启动探针或真实引擎验真。"
    else:
        decision = "stage052_contract_oi_share_proxy_not_enough_no_param_rescue"
        continue_after = "有限。若没有改善严格负窗口或收益保留失败，就停止该 proxy，不做阈值救参。"
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
        aggregate["variant"].eq("stage052_contract_oi_share_ge50_add_risk_proxy")
        & aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")
    ]
    wide = _wide_summary(summary)
    lines = [
        "# Stage052 - contract_oi_share_ge50 非挤占加风险 proxy",
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
        f"- Stage052 严格任意 `>1` 年负窗口：`{decision['stage052_contract_oi_share_ge50_add_risk_proxy_all_gt1y_negative_count']}` / `{decision['stage052_contract_oi_share_ge50_add_risk_proxy_all_gt1y_window_count']}`；最差 `{decision['stage052_contract_oi_share_ge50_add_risk_proxy_all_gt1y_min_return_pct']:.4f}%`。",
        f"- Stage013 严格任意 `>1` 年负窗口：`{decision['stage013_engine_all_gt1y_negative_count']}`。",
        f"- 到 `2026-06-30` 负窗口：`{decision['stage052_contract_oi_share_ge50_add_risk_proxy_to_final_negative_count']}`；最差 `{decision['stage052_contract_oi_share_ge50_add_risk_proxy_to_final_min_return_pct']:.4f}%`。",
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
                    "total_return_pct_stage052_contract_oi_share_ge50_add_risk_proxy",
                    "return_delta_pp_stage052_vs_stage013",
                    "max_dd_pct_stage013_engine",
                    "max_dd_pct_stage052_contract_oi_share_ge50_add_risk_proxy",
                    "maxdd_delta_pp_stage052_vs_stage013",
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
                    "stage052_vs_base_stage006_return_ratio",
                    "stage052_vs_stage013_return_ratio",
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


def _write_stage_record(decision: dict[str, Any]) -> Path:
    timestamp = datetime.now()
    path = STAGES_DIR / f"{timestamp:%Y%m%d_%H%M}_stage052_contract_oi_share_add_risk_proxy.md"
    report = REPORT_PATH.read_text(encoding="utf-8")
    header = f"""# Stage052 - contract_oi_share_ge50 非挤占加风险 proxy

- 记录时间：`{timestamp.isoformat(timespec='minutes')}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 是否重要突破版本：`否`
- 决策：`{decision['decision']}`

## 本次版本变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage052_contract_oi_share_add_risk_proxy.py`
- 新增测试：`tests/test_rebuilt_c9_stage052_contract_oi_proxy.py`
- 新增参数：`selector=contract_oi_share_ge50`、`ADD_RISK_FRACTION=0.25`。
- 修改参数：无，Stage013/Stage006/官方 C9 配置未改。
- 删除参数：无。
- 新增回测结果：closed-lot 只读 proxy 目标审计；不是真实组合引擎。
- 本阶段不连接 CTP，不调用订单 API，不触发 A/B。

## 调研和判断结论

- {decision['external_research_judgment']}

"""
    path.write_text(header + report, encoding="utf-8")
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
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, summary, aggregate, retention)
    stage_record = _write_stage_record(decision)
    decision["stage_record_path"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return decision


if __name__ == "__main__":
    print(json.dumps(_json_safe(run()), ensure_ascii=False, indent=2))
