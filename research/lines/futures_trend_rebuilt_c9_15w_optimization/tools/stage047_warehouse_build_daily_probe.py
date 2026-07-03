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

import stage013_account_state_pilot_gate_engine as s013
import stage041_selected_daily_cold_start_probe as s041
import stage042_expanded_daily_cold_start_probe as s042
import stage045_external_pit_basis_warehouse_audit as s045
import stage046_warehouse_build_add_risk_proxy as s046


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage047"
MODEL_TAG = "stage047_warehouse_build_daily_probe_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage047_warehouse_build_daily_probe"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage047_warehouse_build_daily_probe"
STAGES_DIR = LINE_DIR / "stages"

STAGE046_OUTPUT_DIR = LINE_DIR / "outputs" / "stage046_warehouse_build_add_risk_proxy"
STAGE046_PREFIX = "rebuilt_c9_stage046_warehouse_build_add_risk_proxy"
STAGE046_TAG = "stage046_warehouse_build_add_risk_proxy_v1"
STAGE046_WORST_WINDOWS_PATH = STAGE046_OUTPUT_DIR / f"{STAGE046_PREFIX}_goal_worst_windows_{STAGE046_TAG}.csv"

REQUESTED_END = pd.Timestamp("2026-06-30")
CAPITAL = 150000.0
ADD_RISK_FRACTION = 0.25
BUCKET_QUOTAS = {
    "stage046_worst": 20,
    "stage013_worst": 12,
}

PROBE_STARTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_probe_starts_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
LOT_DELTAS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_deltas_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s041._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s041._md_table(frame, max_rows=max_rows)


def _date_key(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _variant_bucket_frame(worst_windows: pd.DataFrame, variant: str) -> pd.DataFrame:
    data = worst_windows.copy()
    data["start_date"] = pd.to_datetime(data["start_date"], errors="coerce").dt.normalize()
    data["return_pct"] = pd.to_numeric(data["return_pct"], errors="coerce")
    data = data.dropna(subset=["start_date", "return_pct"])
    return data[data["variant"].eq(variant)].sort_values("return_pct")


def _append_unique_starts(
    rows: list[dict[str, Any]],
    seen: set[str],
    frame: pd.DataFrame,
    bucket: str,
    quota: int,
) -> None:
    added = 0
    for _, row in frame.iterrows():
        key = _date_key(row["start_date"])
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "probe_rank": len(rows) + 1,
                "requested_start": key,
                "probe_bucket": bucket,
                "source_variant": str(row.get("variant", "")),
                "source_start_month": str(row.get("source_start_month", "")),
                "source_window_type": str(row.get("window_type", "")),
                "source_end_date": _date_key(row["end_date"]) if pd.notna(row.get("end_date")) else "",
                "source_return_pct": float(row.get("return_pct", np.nan)),
            }
        )
        added += 1
        if added >= quota:
            return


def _select_probe_start_dates(
    worst_windows: pd.DataFrame,
    bucket_quotas: dict[str, int] = BUCKET_QUOTAS,
) -> pd.DataFrame:
    buckets = {
        "stage046_worst": _variant_bucket_frame(worst_windows, "stage046_warehouse_build_add_risk_proxy"),
        "stage013_worst": _variant_bucket_frame(worst_windows, "stage013_engine"),
    }
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for bucket, quota in bucket_quotas.items():
        _append_unique_starts(rows, seen, buckets.get(bucket, pd.DataFrame()), bucket, int(quota))
    result = pd.DataFrame(rows)
    if result.empty:
        return pd.DataFrame(
            columns=[
                "probe_rank",
                "requested_start",
                "probe_bucket",
                "source_variant",
                "source_start_month",
                "source_window_type",
                "source_end_date",
                "source_return_pct",
            ]
        )
    result["probe_rank"] = np.arange(1, len(result) + 1)
    return result


def _normalise_external_features(features: pd.DataFrame) -> pd.DataFrame:
    result = features.copy()
    rename = {}
    if "data_date" in result.columns and "feature_date" not in result.columns:
        rename["data_date"] = "feature_date"
    if "external_warehouse_change_20d_sum" in result.columns and "warehouse_change_20d_sum" not in result.columns:
        rename["external_warehouse_change_20d_sum"] = "warehouse_change_20d_sum"
    result = result.rename(columns=rename)
    if "product_code" in result.columns:
        result["product_code"] = result["product_code"].map(s045._normalise_product_code)
    elif "product" in result.columns:
        result["product_code"] = result["product"].map(s045._normalise_product_code)
    if "feature_date" in result.columns:
        result["feature_date"] = pd.to_datetime(result["feature_date"], errors="coerce").dt.normalize()
    if "asof_date" in result.columns:
        result["asof_date"] = pd.to_datetime(result["asof_date"], errors="coerce").dt.normalize()
    elif "feature_date" in result.columns:
        result["asof_date"] = result["feature_date"] + pd.Timedelta(days=1)
    return result


def build_warehouse_lot_deltas(
    closed: pd.DataFrame,
    external_features: pd.DataFrame,
    *,
    add_risk_fraction: float = ADD_RISK_FRACTION,
) -> pd.DataFrame:
    if closed.empty:
        return pd.DataFrame()
    entries = closed.copy()
    entries["requested_start_month"] = entries["requested_start_month"].astype(str)
    entries["entry_date"] = pd.to_datetime(entries["entry_date"], errors="coerce").dt.normalize()
    entries["exit_date"] = pd.to_datetime(entries["exit_date"], errors="coerce").dt.normalize()
    entries["realized_pnl"] = pd.to_numeric(entries["realized_pnl"], errors="coerce").fillna(0.0)
    external = _normalise_external_features(external_features)
    attached = s045.attach_t1_external_features(entries, external)
    attached["stage047_external_feature_matched"] = attached["external_warehouse_change_20d_sum"].notna()
    attached["stage047_selected_for_warehouse_build_proxy"] = pd.to_numeric(
        attached["external_warehouse_change_20d_sum"], errors="coerce"
    ).gt(0)
    attached["stage047_add_risk_fraction"] = float(add_risk_fraction)
    attached["stage047_proxy_delta_pnl"] = np.where(
        attached["stage047_selected_for_warehouse_build_proxy"],
        attached["realized_pnl"] * float(add_risk_fraction),
        0.0,
    )
    selected = attached[attached["stage047_selected_for_warehouse_build_proxy"]].copy()
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
        "external_feature_date",
        "external_asof_date",
        "external_warehouse_receipt_quantity",
        "external_warehouse_receipt_quantity_pctile",
        "external_warehouse_receipt_change",
        "external_warehouse_change_20d_sum",
        "external_warehouse_change_20d_sum_pctile",
        "external_dom_basis_rate",
        "external_dom_basis_rate_pctile",
        "stage047_external_feature_matched",
        "stage047_selected_for_warehouse_build_proxy",
        "stage047_add_risk_fraction",
        "stage047_proxy_delta_pnl",
    ]
    return selected[[column for column in keep if column in selected.columns]].reset_index(drop=True)


def _prepare_curve_frame(curve: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    result = s041._prepare_curve_frame(curve, start)
    result["stage"] = STAGE
    result["model_tag"] = MODEL_TAG
    return result


def _build_proxy_curve(base_curve: pd.DataFrame, lot_deltas: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    curves = base_curve.copy()
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["requested_start_month"] = curves["requested_start_month"].astype(str)
    curves["account_equity"] = pd.to_numeric(curves["account_equity"], errors="coerce")
    daily_delta = (
        lot_deltas.groupby(["requested_start_month", "exit_date"], dropna=False)["stage047_proxy_delta_pnl"]
        .sum()
        .reset_index()
        if not lot_deltas.empty
        else pd.DataFrame(columns=["requested_start_month", "exit_date", "stage047_proxy_delta_pnl"])
    )
    merged = curves.merge(
        daily_delta.rename(columns={"exit_date": "date", "stage047_proxy_delta_pnl": "stage047_daily_delta"}),
        on=["requested_start_month", "date"],
        how="left",
    )
    merged["stage047_daily_delta"] = pd.to_numeric(merged["stage047_daily_delta"], errors="coerce").fillna(0.0)
    frames: list[pd.DataFrame] = []
    for _, group in merged.groupby("requested_start_month", sort=True):
        g = group.sort_values("date").copy()
        g["stage047_cum_delta"] = g["stage047_daily_delta"].cumsum()
        g["stage047_account_equity"] = g["account_equity"] + g["stage047_cum_delta"]
        g["stage047_nav"] = g["stage047_account_equity"] / CAPITAL
        g["stage047_drawdown_pct"] = s046._drawdown_pct(g["stage047_account_equity"])
        frames.append(g)
    proxy = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    curve_dates = set(zip(curves["requested_start_month"].astype(str), curves["date"]))
    unmatched = 0
    for row in daily_delta.to_dict("records"):
        if (str(row["requested_start_month"]), row["exit_date"]) not in curve_dates:
            unmatched += 1
    return proxy, unmatched


def _load_external_features() -> pd.DataFrame:
    basis = s045._read_csvs(s045.BASIS_PATHS)
    warehouse = s045._read_csvs(s045.WAREHOUSE_PATHS)
    return s045.build_external_daily_features(basis, warehouse, min_history=s045.MIN_EXTERNAL_HISTORY)


def _run_probe() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    worst_windows = pd.read_csv(STAGE046_WORST_WINDOWS_PATH, encoding="utf-8-sig")
    probe_starts = _select_probe_start_dates(worst_windows)
    if probe_starts.empty:
        raise ValueError("no probe starts selected")
    metadata = s013.s901.s513._metadata()
    external_features = _load_external_features()
    curve_frames: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    lot_delta_frames: list[pd.DataFrame] = []
    for idx, row in probe_starts.iterrows():
        start = pd.Timestamp(row["requested_start"]).normalize()
        print(
            f"[stage047] running daily cold start {idx + 1}/{len(probe_starts)} "
            f"start={_date_key(start)} bucket={row['probe_bucket']}",
            flush=True,
        )
        combined, frames, _spec = s013._run_live_stage013(metadata, start, REQUESTED_END)
        base_curve = _prepare_curve_frame(combined, start)
        closed = s041._closed_lots_from_frames(frames, metadata, start)
        lot_deltas = build_warehouse_lot_deltas(closed, external_features, add_risk_fraction=ADD_RISK_FRACTION)
        proxy_curve, unmatched = _build_proxy_curve(base_curve, lot_deltas)
        proxy_curve["requested_start"] = _date_key(start)
        proxy_curve["probe_bucket"] = row["probe_bucket"]
        proxy_curve["stage047_unmatched_delta_dates"] = int(unmatched)
        curve_frames.append(proxy_curve)
        if not lot_deltas.empty:
            lot_deltas["requested_start"] = _date_key(start)
            lot_deltas["probe_bucket"] = row["probe_bucket"]
            lot_deltas["stage047_unmatched_delta_dates"] = int(unmatched)
            lot_delta_frames.append(lot_deltas)
        stage013_audit = s041._audit_curve_from_actual_start(
            _date_key(start),
            "stage013_daily_cold_start_engine",
            proxy_curve[["date", "account_equity"]].rename(columns={"account_equity": "equity"}),
        )
        stage047_audit = s041._audit_curve_from_actual_start(
            _date_key(start),
            "stage047_daily_cold_start_warehouse_build_proxy",
            proxy_curve[["date", "stage047_account_equity"]].rename(columns={"stage047_account_equity": "equity"}),
        )
        for audit in (stage013_audit, stage047_audit):
            audit["probe_bucket"] = row["probe_bucket"]
            audit["source_variant"] = row["source_variant"]
            audit["source_start_month"] = row["source_start_month"]
            audit["source_return_pct"] = row["source_return_pct"]
        summary_rows.extend([stage013_audit, stage047_audit])
    curves = pd.concat(curve_frames, ignore_index=True, sort=False) if curve_frames else pd.DataFrame()
    lot_deltas = pd.concat(lot_delta_frames, ignore_index=True, sort=False) if lot_delta_frames else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)
    aggregate = s042._aggregate_probe_summary(summary)
    return probe_starts, summary, aggregate, curves, lot_deltas


def _metric(aggregate: pd.DataFrame, variant: str, column: str, default: Any = np.nan) -> Any:
    rows = aggregate[aggregate["variant"].eq(variant)]
    if rows.empty or column not in rows.columns:
        return default
    return rows.iloc[0][column]


def _decision(
    probe_starts: pd.DataFrame,
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    lot_deltas: pd.DataFrame,
) -> dict[str, Any]:
    stage013_negative = int(_metric(aggregate, "stage013_daily_cold_start_engine", "negative_probe_start_count", 0))
    stage047_negative = int(
        _metric(aggregate, "stage047_daily_cold_start_warehouse_build_proxy", "negative_probe_start_count", 0)
    )
    if stage047_negative == 0 and stage013_negative > 0:
        decision = "stage047_warehouse_daily_probe_clears_probe_left_tail_requires_true_engine"
        continue_after = "有。探针层面清零负起点，但仍是 closed-lot proxy，下一步必须写真实组合引擎验真。"
    elif stage047_negative < stage013_negative:
        decision = "stage047_warehouse_daily_probe_partially_reduces_left_tail_not_goal"
        continue_after = "有但未达标。仓单 build 在日级探针上有部分缓冲，下一步只能真引擎验真或定位剩余负起点。"
    else:
        decision = "stage047_warehouse_daily_probe_not_left_tail_solution_no_param_rescue"
        continue_after = "有限。若日级探针不能减少负起点，应停止救仓单 build 参数，转新外生源或真实路径归因。"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "decision": decision,
        "audit_type": "expanded_exact_daily_cold_start_true_engine_probe_with_warehouse_build_closed_lot_proxy",
        "selector": "external_warehouse_build_20d",
        "add_risk_fraction": ADD_RISK_FRACTION,
        "probe_start_count": int(len(probe_starts)),
        "probe_bucket_counts": probe_starts["probe_bucket"].value_counts().sort_index().to_dict(),
        "stage013_negative_probe_start_count": stage013_negative,
        "stage047_negative_probe_start_count": stage047_negative,
        "stage013_min_return_pct": float(_metric(aggregate, "stage013_daily_cold_start_engine", "min_return_pct")),
        "stage047_min_return_pct": float(
            _metric(aggregate, "stage047_daily_cold_start_warehouse_build_proxy", "min_return_pct")
        ),
        "stage013_to_final_min_return_pct": float(
            _metric(aggregate, "stage013_daily_cold_start_engine", "to_final_min_return_pct")
        ),
        "stage047_to_final_min_return_pct": float(
            _metric(aggregate, "stage047_daily_cold_start_warehouse_build_proxy", "to_final_min_return_pct")
        ),
        "stage013_max_dd_min_pct": float(_metric(aggregate, "stage013_daily_cold_start_engine", "max_dd_min_pct")),
        "stage047_max_dd_min_pct": float(
            _metric(aggregate, "stage047_daily_cold_start_warehouse_build_proxy", "max_dd_min_pct")
        ),
        "selected_lots": int(len(lot_deltas)),
        "selected_realized_pnl": float(
            pd.to_numeric(lot_deltas.get("realized_pnl", pd.Series(dtype=float)), errors="coerce").sum()
        )
        if not lot_deltas.empty
        else 0.0,
        "stage047_proxy_delta_pnl": float(
            pd.to_numeric(lot_deltas.get("stage047_proxy_delta_pnl", pd.Series(dtype=float)), errors="coerce").sum()
        )
        if not lot_deltas.empty
        else 0.0,
        "strategy_changed": False,
        "true_engine_base_run": True,
        "proxy_overlay": True,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "库存、仓单、基差和 carry 具有商品期货经济含义，但资料也提示这类信号必须点时化、"
            "低自由度并通过组合路径验证。Stage047 因此只验证 Stage046 已冻结的仓单 build 条件在真实日级冷启动上的表现，"
            "不继续搜索仓单窗口、分位、品种或倍率。"
        ),
        "overfit_reflection_before": (
            "否。Stage047 只把 Stage046 固定条件搬到日级冷启动探针，不新增交易规则、不调阈值。"
        ),
        "overfit_reflection_after": (
            "否。本阶段仍是预声明 proxy；若根据结果改仓单窗口、分位、产品、年份、方向或倍率就是过拟合。"
        ),
        "continue_value_before": "有。Stage046 只在半年源曲线上部分改善，必须验证具体日级起点是否也改善。",
        "continue_value_after": continue_after,
        "outputs": {
            "probe_starts": str(PROBE_STARTS_PATH),
            "summary": str(SUMMARY_PATH),
            "aggregate": str(AGGREGATE_PATH),
            "curves": str(CURVES_PATH),
            "lot_deltas": str(LOT_DELTAS_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(
    decision: dict[str, Any],
    probe_starts: pd.DataFrame,
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    lot_deltas: pd.DataFrame,
) -> None:
    lot_preview_columns = [
        "requested_start",
        "probe_bucket",
        "product",
        "direction",
        "entry_date",
        "exit_date",
        "realized_pnl",
        "external_warehouse_change_20d_sum",
        "stage047_proxy_delta_pnl",
    ]
    lines = [
        "# Stage047 - 仓单 build 条件日级冷启动探针",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：真实 Stage013 日级冷启动 + Stage046 固定仓单 build closed-lot proxy；不改 C9，不连接 CTP，不调用下单。",
        f"- selector：`{decision['selector']}`",
        f"- 固定额外风险比例：`{ADD_RISK_FRACTION:.2%}`",
        "",
        "## 核心结果",
        "",
        f"- 探针起点数：`{decision['probe_start_count']}`；bucket 分布 `{decision['probe_bucket_counts']}`。",
        f"- Stage013 有负结束日的探针起点：`{decision['stage013_negative_probe_start_count']}`。",
        f"- Stage047 proxy 有负结束日的探针起点：`{decision['stage047_negative_probe_start_count']}`。",
        f"- Stage013 探针最差收益：`{decision['stage013_min_return_pct']:.4f}%`；到 2026-06-30 最差 `{decision['stage013_to_final_min_return_pct']:.4f}%`。",
        f"- Stage047 proxy 探针最差收益：`{decision['stage047_min_return_pct']:.4f}%`；到 2026-06-30 最差 `{decision['stage047_to_final_min_return_pct']:.4f}%`。",
        f"- Stage013 探针最差最大回撤：`{decision['stage013_max_dd_min_pct']:.4f}%`。",
        f"- Stage047 proxy 探针最差最大回撤：`{decision['stage047_max_dd_min_pct']:.4f}%`。",
        f"- Stage047 选中 lots：`{decision['selected_lots']}`；proxy delta `{decision['stage047_proxy_delta_pnl']:,.2f}`。",
        "",
        "## 探针起点",
        "",
        _md_table(probe_starts, max_rows=80),
        "",
        "## 聚合审计",
        "",
        _md_table(aggregate, max_rows=20),
        "",
        "## 探针审计",
        "",
        _md_table(summary, max_rows=80),
        "",
        "## lot delta 摘要",
        "",
        _md_table(
            lot_deltas[[column for column in lot_preview_columns if column in lot_deltas.columns]]
            if not lot_deltas.empty
            else lot_deltas,
            max_rows=50,
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


def _write_stage_record(decision: dict[str, Any], probe_starts: pd.DataFrame, aggregate: pd.DataFrame) -> Path:
    timestamp = datetime.now()
    path = STAGES_DIR / f"{timestamp:%Y%m%d_%H%M}_stage047_warehouse_build_daily_probe.md"
    lines = [
        "# Stage047 - 仓单 build 条件日级冷启动探针",
        "",
        f"- 记录时间：`{timestamp.isoformat(timespec='minutes')}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 是否重要突破版本：`否`",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 本次版本变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage047_warehouse_build_daily_probe.py`",
        f"- 新增参数：日级探针 bucket quota `{BUCKET_QUOTAS}`；交易侧仍只使用 `selector=external_warehouse_build_20d` 和 `ADD_RISK_FRACTION=0.25`。",
        "- 修改参数：无，Stage013/Stage046/官方 C9 配置未改。",
        "- 删除参数：无。",
        "- 新增回测结果：真实日级冷启动 Stage013 + Stage046 仓单 build closed-lot proxy。",
        "- 本阶段不连接 CTP，不调用订单 API，不触发 A/B。",
        "",
        "## 调研和判断结论",
        "",
        f"- {decision['external_research_judgment']}",
        "",
        "## 结果",
        "",
        f"- 探针起点数：`{decision['probe_start_count']}`。",
        f"- bucket 分布：`{decision['probe_bucket_counts']}`。",
        f"- Stage013 有负结束日的探针起点：`{decision['stage013_negative_probe_start_count']}`。",
        f"- Stage047 proxy 有负结束日的探针起点：`{decision['stage047_negative_probe_start_count']}`。",
        f"- Stage013 探针最差收益：`{decision['stage013_min_return_pct']:.4f}%`。",
        f"- Stage047 proxy 探针最差收益：`{decision['stage047_min_return_pct']:.4f}%`。",
        f"- Stage013 到 `2026-06-30` 最差收益：`{decision['stage013_to_final_min_return_pct']:.4f}%`。",
        f"- Stage047 到 `2026-06-30` 最差收益：`{decision['stage047_to_final_min_return_pct']:.4f}%`。",
        f"- Stage047 proxy delta：`{decision['stage047_proxy_delta_pnl']:,.2f}`。",
        "",
        "## 探针起点",
        "",
        _md_table(probe_starts, max_rows=80),
        "",
        "## 聚合审计",
        "",
        _md_table(aggregate, max_rows=20),
        "",
        "## 输出",
        "",
        f"- probe_starts：`{PROBE_STARTS_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- aggregate：`{AGGREGATE_PATH}`",
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
    probe_starts, summary, aggregate, curves, lot_deltas = _run_probe()
    decision = _decision(probe_starts, summary, aggregate, lot_deltas)
    probe_starts.to_csv(PROBE_STARTS_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    lot_deltas.to_csv(LOT_DELTAS_PATH, index=False, encoding="utf-8-sig")
    _write_report(decision, probe_starts, summary, aggregate, lot_deltas)
    stage_record = _write_stage_record(decision, probe_starts, aggregate)
    decision["stage_record_path"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
