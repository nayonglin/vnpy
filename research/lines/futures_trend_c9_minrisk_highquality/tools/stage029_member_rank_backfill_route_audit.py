from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage029"
MODEL_TAG = "stage029_member_rank_backfill_route_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage029_c9_minrisk_member_rank_backfill_route_audit"
ACCOUNT_CAPITAL = 150_000.0
TRADING_DAYS_PER_YEAR = 252

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE005_DIR = LINE_DIR / "outputs" / "stage005_signal_quality_visual_forensics"
STAGE028_DIR = LINE_DIR / "outputs" / "stage028_member_rank_position_forensics"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage029_member_rank_backfill_route_audit"
BACKTEST_OUTPUT_DIR = EXAMPLE_DIR / "backtest_outputs"

FEATURES_IN = (
    STAGE028_DIR
    / "qmt_roll_stage028_c9_minrisk_member_rank_position_forensics_features_"
    "stage028_member_rank_position_forensics_v1.csv"
)
ACTIVE_SHARE_IN = (
    STAGE028_DIR
    / "qmt_roll_stage028_c9_minrisk_member_rank_position_forensics_daily_active_share_"
    "stage028_member_rank_position_forensics_v1.csv"
)
OFFICIAL_CURVE_IN = (
    STAGE005_DIR
    / "qmt_roll_stage005_c9_minrisk_signal_quality_visual_forensics_official_curve_"
    "stage005_signal_quality_visual_forensics_v1.csv"
)
STAGE548_ROUTE_SUMMARY_IN = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_stage548_external_source_alternative_probe_route_summary_"
    "stage548_external_source_alternative_probe_v1.csv"
)
STAGE548_PROBE_DETAIL_IN = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_stage548_external_source_alternative_probe_probe_detail_"
    "stage548_external_source_alternative_probe_v1.csv"
)
STAGE599_ROUTE_READINESS_IN = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_stage599_dce_official_route_parser_forensic_route_readiness_"
    "stage599_dce_official_route_parser_forensic_v1.csv"
)
STAGE599_AKSHARE_PROBE_IN = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_stage599_dce_official_route_parser_forensic_akshare_probe_"
    "stage599_dce_official_route_parser_forensic_v1.csv"
)
STAGE620_CONTRACT_IN = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_stage620_forward_source_collector_contract_collector_contract_"
    "stage620_forward_source_collector_contract_v1.csv"
)

GAP_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gap_by_year_{MODEL_TAG}.csv"
GAP_PRODUCT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gap_by_product_{MODEL_TAG}.csv"
GAP_EXCHANGE_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gap_by_exchange_year_{MODEL_TAG}.csv"
ROUTE_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_audit_{MODEL_TAG}.csv"
SMOKE_PROBE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_endpoint_smoke_probe_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_coverage_gap_chart_{MODEL_TAG}.png"
GAP_CONTRIBUTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gap_contribution_chart_{MODEL_TAG}.png"
EXCHANGE_YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_exchange_year_gap_heatmap_{MODEL_TAG}.png"
PRODUCT_GAP_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_gap_priority_chart_{MODEL_TAG}.png"
ROUTE_READINESS_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_readiness_heatmap_{MODEL_TAG}.png"


CHILD_PROBE_CODE = r"""
import json
import sys
import traceback

import akshare as ak
import pandas as pd


def hit_product_in_frame(frame, product):
    product = str(product).upper()
    for column in frame.columns:
        values = frame[column].astype(str).str.upper()
        if values.str.contains(product, regex=False).any():
            return True
    return False


def summarize(result, targets):
    if isinstance(result, dict):
        keys = [str(key) for key in result.keys()]
        row_count = 0
        columns = []
        hits = {}
        for key, value in result.items():
            if isinstance(value, pd.DataFrame):
                row_count += int(len(value))
                columns.extend([str(column) for column in value.columns])
                for target in targets:
                    target_upper = str(target).upper()
                    if target_upper in str(key).upper() or hit_product_in_frame(value, target_upper):
                        hits[target_upper] = 1
        return {
            "result_kind": "dict",
            "keys_count": len(keys),
            "sample_keys": "|".join(keys[:12]),
            "rows": row_count,
            "columns": "|".join(sorted(set(columns))[:20]),
            "target_hit_count": int(sum(hits.values())),
            "target_hits": "|".join(sorted(hits)),
        }
    if isinstance(result, pd.DataFrame):
        hits = {}
        for target in targets:
            target_upper = str(target).upper()
            if hit_product_in_frame(result, target_upper):
                hits[target_upper] = 1
        return {
            "result_kind": "dataframe",
            "keys_count": 0,
            "sample_keys": "",
            "rows": int(len(result)),
            "columns": "|".join([str(column) for column in result.columns[:20]]),
            "target_hit_count": int(sum(hits.values())),
            "target_hits": "|".join(sorted(hits)),
        }
    return {
        "result_kind": type(result).__name__,
        "keys_count": 0,
        "sample_keys": "",
        "rows": 0,
        "columns": "",
        "target_hit_count": 0,
        "target_hits": "",
    }


spec = json.loads(sys.argv[1])
try:
    func = getattr(ak, spec["function_name"])
    result = func(*spec.get("args", []), **spec.get("kwargs", {}))
    out = summarize(result, spec.get("target_products", []))
    out.update(
        {
            "status": "ok",
            "error_type": "",
            "error_message": "",
            "akshare_version": getattr(ak, "__version__", "unknown"),
        }
    )
except Exception as exc:
    out = {
        "status": "error",
        "result_kind": "",
        "keys_count": 0,
        "sample_keys": "",
        "rows": 0,
        "columns": "",
        "target_hit_count": 0,
        "target_hits": "",
        "error_type": type(exc).__name__,
        "error_message": str(exc),
        "traceback_tail": "\n".join(traceback.format_exc().splitlines()[-4:]),
        "akshare_version": getattr(ak, "__version__", "unknown"),
    }
print(json.dumps(out, ensure_ascii=False))
"""


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _read_csv(path: Path, required: bool = True) -> pd.DataFrame:
    if not path.exists():
        if required:
            raise RuntimeError(f"missing required input: {path}")
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    display = data.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    headers = [str(column) for column in display.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in display.columns) + " |")
    return "\n".join(lines)


def _load_features() -> pd.DataFrame:
    frame = _read_csv(FEATURES_IN)
    frame["entry_date"] = pd.to_datetime(frame["entry_date"], errors="coerce").dt.normalize()
    frame["exit_date"] = pd.to_datetime(frame["exit_date"], errors="coerce").dt.normalize()
    frame["entry_year"] = pd.to_numeric(frame["entry_year"], errors="coerce").astype("Int64")
    frame["realized_pnl"] = pd.to_numeric(frame["realized_pnl"], errors="coerce").fillna(0.0)
    frame["member_ready"] = frame["member_feature_ready_stage028"].fillna(False).astype(bool)
    frame["member_missing"] = ~frame["member_ready"]
    frame["exchange"] = frame["exchange"].fillna("UNKNOWN").astype(str)
    frame["product"] = frame["product"].fillna("").astype(str)
    return frame


def _load_official_curve() -> pd.DataFrame:
    curve = _read_csv(OFFICIAL_CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in [
        "account_equity",
        "drawdown_pct",
        "slippage",
        "trade_count",
        "broker10_margin_to_equity_pct",
    ]:
        curve[column] = pd.to_numeric(curve.get(column, 0.0), errors="coerce").fillna(0.0)
    prev_equity = curve["account_equity"].shift(1)
    prev_equity.iloc[0] = ACCOUNT_CAPITAL
    curve["daily_return"] = (curve["account_equity"] / prev_equity - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return curve


def _official_metrics(curve: pd.DataFrame, features: pd.DataFrame) -> dict[str, float]:
    returns = pd.to_numeric(curve["daily_return"], errors="coerce").fillna(0.0)
    std = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    start = float(curve["account_equity"].iloc[0]) if not curve.empty else ACCOUNT_CAPITAL
    end = float(curve["account_equity"].iloc[-1]) if not curve.empty else ACCOUNT_CAPITAL
    pnl = pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0)
    return {
        "end_equity": end,
        "total_return_pct": (end / start - 1.0) * 100.0 if start else np.nan,
        "max_drawdown_pct": float(pd.to_numeric(curve["drawdown_pct"], errors="coerce").min()),
        "sharpe": float(returns.mean() / std * np.sqrt(TRADING_DAYS_PER_YEAR)) if std > 0 else 0.0,
        "total_slippage": float(pd.to_numeric(curve["slippage"], errors="coerce").sum()),
        "total_trade_count": float(pd.to_numeric(curve["trade_count"], errors="coerce").sum()),
        "closed_lot_win_rate_pct": float((pnl > 0.0).mean() * 100.0),
        "closed_lot_count": float(len(features)),
    }


def _aggregate_gap_by_year(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for year, group in features.groupby("entry_year", dropna=False, sort=True):
        missing = group[group["member_missing"]]
        ready = group[group["member_ready"]]
        rows.append(
            {
                "entry_year": int(year) if not pd.isna(year) else -1,
                "lot_count": int(len(group)),
                "member_ready_count": int(len(ready)),
                "member_missing_count": int(len(missing)),
                "member_ready_rate_pct": float(len(ready) / len(group) * 100.0) if len(group) else 0.0,
                "ready_net_pnl": float(ready["realized_pnl"].sum()),
                "missing_net_pnl": float(missing["realized_pnl"].sum()),
                "missing_positive_pnl": float(missing["realized_pnl"].clip(lower=0.0).sum()),
                "missing_negative_pnl": float(missing["realized_pnl"].clip(upper=0.0).sum()),
                "missing_product_count": int(missing["product"].nunique()),
                "missing_exchange_count": int(missing["exchange"].nunique()),
            }
        )
    return pd.DataFrame(rows)


def _aggregate_gap_by_product(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (exchange, product), group in features.groupby(["exchange", "product"], dropna=False, sort=True):
        missing = group[group["member_missing"]]
        ready = group[group["member_ready"]]
        if group.empty:
            continue
        rows.append(
            {
                "exchange": str(exchange),
                "product": str(product),
                "lot_count": int(len(group)),
                "member_ready_count": int(len(ready)),
                "member_missing_count": int(len(missing)),
                "member_ready_rate_pct": float(len(ready) / len(group) * 100.0) if len(group) else 0.0,
                "ready_net_pnl": float(ready["realized_pnl"].sum()),
                "missing_net_pnl": float(missing["realized_pnl"].sum()),
                "missing_abs_net_pnl": float(abs(missing["realized_pnl"].sum())),
                "missing_positive_pnl": float(missing["realized_pnl"].clip(lower=0.0).sum()),
                "missing_negative_pnl": float(missing["realized_pnl"].clip(upper=0.0).sum()),
                "missing_year_count": int(missing["entry_year"].nunique()),
                "first_missing_entry_date": missing["entry_date"].min(),
                "last_missing_entry_date": missing["entry_date"].max(),
                "priority_score": float(abs(missing["realized_pnl"].sum()) + len(missing) * 100_000.0),
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["member_missing_count", "priority_score"], ascending=[False, False])
    return out


def _aggregate_gap_by_exchange_year(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (exchange, year), group in features.groupby(["exchange", "entry_year"], dropna=False, sort=True):
        missing = group[group["member_missing"]]
        rows.append(
            {
                "exchange": str(exchange),
                "entry_year": int(year) if not pd.isna(year) else -1,
                "lot_count": int(len(group)),
                "member_missing_count": int(len(missing)),
                "missing_net_pnl": float(missing["realized_pnl"].sum()),
                "missing_positive_pnl": float(missing["realized_pnl"].clip(lower=0.0).sum()),
                "missing_negative_pnl": float(missing["realized_pnl"].clip(upper=0.0).sum()),
                "missing_product_count": int(missing["product"].nunique()),
            }
        )
    return pd.DataFrame(rows)


def _probe_specs() -> list[dict[str, Any]]:
    return [
        {
            "probe_id": "dce_futures_dce_position_rank_20240603",
            "exchange": "DCE",
            "route": "member_detail",
            "function_name": "futures_dce_position_rank",
            "args": ["20240603"],
            "kwargs": {"vars_list": ["J", "JM", "I", "LH"]},
            "target_products": ["J", "JM", "I", "LH"],
            "timeout_seconds": 16,
            "purpose": "DCE key missing products in the C9 member-rank gap",
        },
        {
            "probe_id": "dce_get_dce_rank_table_20240603",
            "exchange": "DCE",
            "route": "member_detail",
            "function_name": "get_dce_rank_table",
            "args": ["20240603"],
            "kwargs": {"vars_list": ["J", "JM", "I", "LH"]},
            "target_products": ["J", "JM", "I", "LH"],
            "timeout_seconds": 16,
            "purpose": "DCE alternate rank-table parser smoke probe",
        },
        {
            "probe_id": "czce_get_rank_table_czce_20240603",
            "exchange": "CZCE",
            "route": "member_detail",
            "function_name": "get_rank_table_czce",
            "args": ["20240603"],
            "kwargs": {},
            "target_products": ["SR", "CY", "OI", "MA", "FG", "AP", "SH"],
            "timeout_seconds": 16,
            "purpose": "CZCE rank table parser smoke probe",
        },
        {
            "probe_id": "shfe_get_shfe_rank_table_20240603",
            "exchange": "SHFE",
            "route": "member_detail",
            "function_name": "get_shfe_rank_table",
            "args": ["20240603"],
            "kwargs": {"vars_list": ["RB", "RU", "AU", "FU", "HC"]},
            "target_products": ["RB", "RU", "AU", "FU", "HC"],
            "timeout_seconds": 16,
            "purpose": "SHFE rank table parser smoke probe",
        },
        {
            "probe_id": "gfex_futures_gfex_position_rank_20240603",
            "exchange": "GFEX",
            "route": "member_detail",
            "function_name": "futures_gfex_position_rank",
            "args": ["20240603"],
            "kwargs": {"vars_list": ["SI", "LC"]},
            "target_products": ["SI", "LC"],
            "timeout_seconds": 16,
            "purpose": "GFEX rank table parser smoke probe for post-2023 products",
        },
    ]


def _run_smoke_probes(skip: bool) -> pd.DataFrame:
    specs = _probe_specs()
    rows: list[dict[str, Any]] = []
    for spec in specs:
        base = {
            "probe_id": spec["probe_id"],
            "exchange": spec["exchange"],
            "route": spec["route"],
            "function_name": spec["function_name"],
            "args_json": json.dumps(spec.get("args", []), ensure_ascii=False),
            "kwargs_json": json.dumps(spec.get("kwargs", {}), ensure_ascii=False),
            "target_products": "|".join(spec.get("target_products", [])),
            "purpose": spec["purpose"],
            "timeout_seconds": spec["timeout_seconds"],
        }
        if skip:
            rows.append({**base, "status": "skipped", "error_type": "", "error_message": ""})
            continue
        try:
            result = subprocess.run(
                [sys.executable, "-c", CHILD_PROBE_CODE, json.dumps(spec, ensure_ascii=False)],
                cwd=str(REPO_DIR),
                text=True,
                capture_output=True,
                timeout=int(spec["timeout_seconds"]),
                check=False,
            )
        except subprocess.TimeoutExpired:
            rows.append({**base, "status": "timeout", "error_type": "Timeout", "error_message": f">{spec['timeout_seconds']}s"})
            continue
        if result.returncode != 0:
            stderr = (result.stderr or "").strip().splitlines()
            rows.append(
                {
                    **base,
                    "status": "process_error",
                    "error_type": f"returncode_{result.returncode}",
                    "error_message": stderr[-1] if stderr else "",
                }
            )
            continue
        stdout = (result.stdout or "").strip().splitlines()
        if not stdout:
            rows.append({**base, "status": "empty_stdout", "error_type": "EmptyStdout", "error_message": ""})
            continue
        try:
            parsed = json.loads(stdout[-1])
        except json.JSONDecodeError as exc:
            rows.append({**base, "status": "bad_json", "error_type": type(exc).__name__, "error_message": str(exc)})
            continue
        rows.append({**base, **parsed})
    return pd.DataFrame(rows)


def _build_route_audit(
    features: pd.DataFrame,
    gap_product: pd.DataFrame,
    smoke: pd.DataFrame,
    stage548_route: pd.DataFrame,
    stage548_probe: pd.DataFrame,
    stage599_readiness: pd.DataFrame,
    stage599_probe: pd.DataFrame,
    stage620_contract: pd.DataFrame,
) -> pd.DataFrame:
    exchanges = sorted(features["exchange"].dropna().astype(str).unique())
    callable_map = {
        "DCE": "futures_dce_position_rank|get_dce_rank_table",
        "CZCE": "get_rank_table_czce",
        "SHFE": "get_shfe_rank_table",
        "GFEX": "futures_gfex_position_rank",
    }
    doc_history = {
        "DCE": "AKShare docs say futures_dce_position_rank can fetch from 2000, but recent BadZipFile evidence remains.",
        "CZCE": "AKShare get_rank_table_czce is the renamed current CZCE rank-table interface.",
        "SHFE": "AKShare get_shfe_rank_table exists and prior probes show partial live readiness.",
        "GFEX": "AKShare docs say futures_gfex_position_rank starts from 2023-11-10, so it cannot cover 2020-2022.",
    }
    rows: list[dict[str, Any]] = []
    route_summary = {row["route"]: row.to_dict() for _, row in stage548_route.iterrows()} if not stage548_route.empty else {}
    member_live = route_summary.get("member_detail_live_ready", {})
    depth = route_summary.get("inventory_backtest_depth_ready", {})
    all_core = route_summary.get("all_core_external_state_ready", {})
    for exchange in exchanges:
        exchange_lots = features[features["exchange"].eq(exchange)]
        exchange_missing = exchange_lots[exchange_lots["member_missing"]]
        exchange_gap_products = gap_product[gap_product["exchange"].eq(exchange)].copy() if not gap_product.empty else pd.DataFrame()
        smoke_exchange = smoke[smoke["exchange"].eq(exchange)].copy() if not smoke.empty else pd.DataFrame()
        smoke_status = "|".join(smoke_exchange["status"].astype(str).tolist()) if not smoke_exchange.empty else ""
        smoke_ok = int((smoke_exchange["status"].eq("ok") & pd.to_numeric(smoke_exchange.get("target_hit_count", 0), errors="coerce").fillna(0).gt(0)).any()) if not smoke_exchange.empty else 0
        contract_exchange = stage620_contract[
            stage620_contract.get("exchange", pd.Series(dtype=str)).astype(str).eq(exchange)
            & stage620_contract.get("route_group", pd.Series(dtype=str)).astype(str).eq("member_detail")
        ].copy() if not stage620_contract.empty else pd.DataFrame()
        history_selector_allowed = int(pd.to_numeric(contract_exchange.get("history_selector_allowed", pd.Series(dtype=float)), errors="coerce").fillna(0).max()) if not contract_exchange.empty else 0
        collector_implemented = int(pd.to_numeric(contract_exchange.get("collector_implemented", pd.Series(dtype=float)), errors="coerce").fillna(0).max()) if not contract_exchange.empty else 0
        callable_present_contract = int(pd.to_numeric(contract_exchange.get("callable_present", pd.Series(dtype=float)), errors="coerce").fillna(0).max()) if not contract_exchange.empty else 0
        stage548_exchange = stage548_probe[
            stage548_probe.get("route", pd.Series(dtype=str)).astype(str).str.contains("member_detail", na=False)
            & stage548_probe.get("exchange_group", pd.Series(dtype=str)).astype(str).str.contains(exchange, na=False)
        ].copy() if not stage548_probe.empty else pd.DataFrame()
        stage548_status = "|".join(stage548_exchange["status"].astype(str).unique().tolist()) if not stage548_exchange.empty else ""
        dce_readiness = stage599_readiness if exchange == "DCE" else pd.DataFrame()
        dce_probe = stage599_probe if exchange == "DCE" else pd.DataFrame()
        dce_errors = "|".join(dce_readiness["latest_akshare_error"].dropna().astype(str).unique().tolist()) if not dce_readiness.empty else ""
        dce_probe_status = "|".join(dce_probe["status"].astype(str).unique().tolist()) if not dce_probe.empty else ""
        missing_2020_2022 = exchange_missing[exchange_missing["entry_year"].between(2020, 2022, inclusive="both")]
        readiness_score = 0
        readiness_score += 20 if callable_present_contract or callable_map.get(exchange) else 0
        readiness_score += 20 if collector_implemented else 0
        readiness_score += 25 if history_selector_allowed else 0
        readiness_score += 20 if smoke_ok else 0
        readiness_score -= 25 if exchange == "DCE" and dce_errors else 0
        readiness_score -= 20 if exchange == "GFEX" and not missing_2020_2022.empty else 0
        readiness_score = int(max(0, min(100, readiness_score)))
        if readiness_score >= 70 and history_selector_allowed:
            route_status = "history_route_ready"
        elif smoke_ok:
            route_status = "live_or_point_smoke_only_not_backtest_ready"
        elif exchange == "DCE" and dce_errors:
            route_status = "blocked_by_known_dce_parser_errors"
        elif exchange == "GFEX" and not missing_2020_2022.empty:
            route_status = "listed_after_main_drawdown_years"
        else:
            route_status = "not_history_ready"
        rows.append(
            {
                "exchange": exchange,
                "callable_names": callable_map.get(exchange, ""),
                "doc_history_note": doc_history.get(exchange, ""),
                "lot_count": int(len(exchange_lots)),
                "member_missing_count": int(len(exchange_missing)),
                "missing_2020_2022_count": int(len(missing_2020_2022)),
                "missing_product_count": int(exchange_missing["product"].nunique()),
                "missing_net_pnl": float(exchange_missing["realized_pnl"].sum()),
                "top_missing_products": "|".join(exchange_gap_products.sort_values("member_missing_count", ascending=False)["product"].head(8).astype(str).tolist()) if not exchange_gap_products.empty else "",
                "stage548_member_live_ready_applicable_rate_pct": float(member_live.get("applicable_ready_rate_pct", np.nan)),
                "stage548_inventory_backtest_depth_ready_rate_pct": float(depth.get("applicable_ready_rate_pct", np.nan)),
                "stage548_all_core_external_state_ready_rate_pct": float(all_core.get("applicable_ready_rate_pct", np.nan)),
                "stage548_exchange_member_status": stage548_status,
                "stage599_dce_errors": dce_errors,
                "stage599_dce_probe_status": dce_probe_status,
                "stage620_member_contract_rows": int(len(contract_exchange)),
                "stage620_callable_present": callable_present_contract,
                "stage620_collector_implemented": collector_implemented,
                "stage620_history_selector_allowed": history_selector_allowed,
                "current_smoke_status": smoke_status,
                "current_smoke_target_hit": smoke_ok,
                "readiness_score": readiness_score,
                "route_status": route_status,
            }
        )
    return pd.DataFrame(rows).sort_values(["readiness_score", "member_missing_count"], ascending=[True, False])


def _build_summary(features: pd.DataFrame, gap_year: pd.DataFrame, route_audit: pd.DataFrame) -> pd.DataFrame:
    missing = features[features["member_missing"]]
    ready = features[features["member_ready"]]
    main_gap_years = gap_year[gap_year["entry_year"].between(2020, 2022, inclusive="both")]
    return pd.DataFrame(
        [
            {
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "closed_lot_count": int(len(features)),
                "member_ready_count": int(len(ready)),
                "member_ready_rate_pct": float(len(ready) / len(features) * 100.0) if len(features) else 0.0,
                "member_missing_count": int(len(missing)),
                "member_missing_net_pnl": float(missing["realized_pnl"].sum()),
                "missing_2020_2022_count": int(main_gap_years["member_missing_count"].sum()),
                "missing_2020_2022_net_pnl": float(main_gap_years["missing_net_pnl"].sum()),
                "missing_exchange_count": int(missing["exchange"].nunique()),
                "missing_product_count": int(missing["product"].nunique()),
                "history_ready_exchange_count": int(route_audit["route_status"].eq("history_route_ready").sum()) if not route_audit.empty else 0,
                "not_history_ready_exchange_count": int((~route_audit["route_status"].eq("history_route_ready")).sum()) if not route_audit.empty else 0,
            }
        ]
    )


def _build_decision(
    features: pd.DataFrame,
    gap_year: pd.DataFrame,
    gap_product: pd.DataFrame,
    route_audit: pd.DataFrame,
    smoke: pd.DataFrame,
    metrics: dict[str, float],
) -> dict[str, Any]:
    ready_count = int(features["member_ready"].sum())
    lot_count = int(len(features))
    ready_rate = ready_count / lot_count * 100.0 if lot_count else 0.0
    missing = features[features["member_missing"]]
    gap_2020_2022 = gap_year[gap_year["entry_year"].between(2020, 2022, inclusive="both")]
    missing_2020_2022_count = int(gap_2020_2022["member_missing_count"].sum()) if not gap_2020_2022.empty else 0
    history_ready_count = int(route_audit["route_status"].eq("history_route_ready").sum()) if not route_audit.empty else 0
    dce_row = route_audit[route_audit["exchange"].eq("DCE")].head(1)
    gfex_row = route_audit[route_audit["exchange"].eq("GFEX")].head(1)
    dce_blocked = bool((~dce_row.empty) and str(dce_row.iloc[0]["route_status"]).startswith("blocked"))
    gfex_late = bool((~gfex_row.empty) and str(gfex_row.iloc[0]["route_status"]).startswith("listed_after"))
    if ready_rate < 50.0 and history_ready_count == 0:
        decision = "stage029_member_rank_backfill_not_history_ready_endpoint_repair_required"
        reason = (
            "Stage028 member-rank coverage is far below a usable C9 backtest threshold, and existing "
            "route evidence does not prove any exchange-level history selector is ready."
        )
    elif ready_rate < 50.0:
        decision = "stage029_member_rank_backfill_required_before_rule_retest"
        reason = "Coverage is too low for rule research; route repair/backfill must precede any new read-only binding."
    else:
        decision = "stage029_member_rank_backfill_watch_only_no_trade_rule"
        reason = "Coverage audit is improved enough for future read-only binding, but this stage still creates no trade rule."
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": decision,
        "candidate_ready": 0,
        "ab_triggered": 0,
        "reason": reason,
        "lot_count": lot_count,
        "member_ready_count": ready_count,
        "member_ready_rate_pct": ready_rate,
        "member_missing_count": int(len(missing)),
        "member_missing_net_pnl": float(missing["realized_pnl"].sum()),
        "missing_2020_2022_count": missing_2020_2022_count,
        "missing_2020_2022_net_pnl": float(gap_2020_2022["missing_net_pnl"].sum()) if not gap_2020_2022.empty else 0.0,
        "missing_exchange_count": int(missing["exchange"].nunique()),
        "missing_product_count": int(missing["product"].nunique()),
        "history_ready_exchange_count": history_ready_count,
        "dce_route_blocked_by_prior_errors": int(dce_blocked),
        "gfex_route_intrinsically_late_for_2020_2022": int(gfex_late),
        "smoke_ok_count": int(smoke["status"].eq("ok").sum()) if not smoke.empty else 0,
        "top_missing_products": gap_product.head(12).to_dict(orient="records") if not gap_product.empty else [],
        "route_audit": route_audit.to_dict(orient="records") if not route_audit.empty else [],
        "official_metrics": metrics,
        "guardrails": {
            "no_trade_rule": True,
            "no_parameter_sweep": True,
            "no_ctp_or_order_api": True,
            "do_not_promote_current_member_rank_cache": True,
            "missing_member_state_keeps_official_path": True,
            "endpoint_smoke_is_not_history_backfill": True,
            "registry_not_updated": True,
        },
        "outputs": {
            "gap_by_year": str(GAP_YEAR_OUT),
            "gap_by_product": str(GAP_PRODUCT_OUT),
            "gap_by_exchange_year": str(GAP_EXCHANGE_YEAR_OUT),
            "route_audit": str(ROUTE_AUDIT_OUT),
            "smoke_probe": str(SMOKE_PROBE_OUT),
            "summary": str(SUMMARY_OUT),
            "report": str(REPORT_OUT),
            "path_chart": str(PATH_CHART_OUT),
            "gap_contribution_chart": str(GAP_CONTRIBUTION_CHART_OUT),
            "exchange_year_heatmap": str(EXCHANGE_YEAR_HEATMAP_OUT),
            "product_gap_chart": str(PRODUCT_GAP_CHART_OUT),
            "route_readiness_chart": str(ROUTE_READINESS_CHART_OUT),
        },
    }


def _plot_path(curve: pd.DataFrame, active_share: pd.DataFrame) -> None:
    daily = active_share.copy()
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    merged = curve.merge(daily, on="date", how="left")
    fig, axes = plt.subplots(4, 1, figsize=(15, 12), sharex=True)
    axes[0].plot(merged["date"], merged["account_equity"], color="#1f77b4", linewidth=1.5)
    axes[0].axvspan(pd.Timestamp("2020-01-01"), pd.Timestamp("2022-12-31"), color="#f2c078", alpha=0.18)
    axes[0].set_title("Official C9/15w equity with 2020-2022 member-rank gap window")
    axes[0].grid(True, alpha=0.25)
    axes[1].plot(merged["date"], merged["drawdown_pct"], color="#d62728", linewidth=1.1)
    axes[1].axvspan(pd.Timestamp("2020-01-01"), pd.Timestamp("2022-12-31"), color="#f2c078", alpha=0.18)
    axes[1].set_title("Official drawdown pct")
    axes[1].grid(True, alpha=0.25)
    axes[2].plot(merged["date"], merged["broker10_margin_to_equity_pct"], color="#9467bd", linewidth=1.1)
    axes[2].axhline(100.0, color="#555555", linestyle="--", linewidth=0.8)
    axes[2].set_title("Broker10 margin pressure")
    axes[2].grid(True, alpha=0.25)
    axes[3].plot(merged["date"], merged["member_ready_share_pct"], color="#2ca02c", linewidth=1.0, label="member ready")
    axes[3].plot(merged["date"], merged["member_missing_share_pct"], color="#7f7f7f", linewidth=1.0, label="member missing")
    axes[3].axvspan(pd.Timestamp("2020-01-01"), pd.Timestamp("2022-12-31"), color="#f2c078", alpha=0.18)
    axes[3].set_ylim(-2, 102)
    axes[3].set_title("Active-lot member rank coverage")
    axes[3].legend(loc="upper left")
    axes[3].grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_gap_contribution(features: pd.DataFrame) -> None:
    calendar = pd.date_range(features["exit_date"].min(), features["exit_date"].max(), freq="D")
    fig, ax = plt.subplots(figsize=(15, 7))
    all_daily = features.groupby("exit_date")["realized_pnl"].sum().reindex(calendar, fill_value=0.0).cumsum()
    ready_daily = features[features["member_ready"]].groupby("exit_date")["realized_pnl"].sum().reindex(calendar, fill_value=0.0).cumsum()
    missing_daily = (
        features[features["member_missing"]].groupby("exit_date")["realized_pnl"].sum().reindex(calendar, fill_value=0.0).cumsum()
    )
    ax.plot(calendar, all_daily, color="#1f77b4", linewidth=1.8, label="all closed lots")
    ax.plot(calendar, ready_daily, color="#2ca02c", linewidth=1.3, label="member ready")
    ax.plot(calendar, missing_daily, color="#7f7f7f", linewidth=1.3, label="member missing")
    ax.axhline(0.0, color="#555555", linewidth=0.8)
    ax.set_title("Realized PnL contribution: ready vs missing member-rank state")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(GAP_CONTRIBUTION_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_exchange_year_heatmap(gap_exchange_year: pd.DataFrame) -> None:
    if gap_exchange_year.empty:
        return
    matrix = gap_exchange_year.pivot_table(
        index="exchange",
        columns="entry_year",
        values="member_missing_count",
        aggfunc="sum",
        fill_value=0,
    ).sort_index()
    values = matrix.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(11, max(4, 0.7 * len(matrix))))
    image = ax.imshow(values, aspect="auto", cmap="YlOrRd", vmin=0, vmax=max(float(np.nanmax(values)), 1.0))
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    ax.set_xticks(np.arange(len(matrix.columns)))
    ax.set_xticklabels([str(int(column)) for column in matrix.columns], rotation=45, ha="right")
    ax.set_title("Member-rank missing lot count by exchange and entry year")
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{values[i, j]:.0f}", ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(EXCHANGE_YEAR_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_product_gap(gap_product: pd.DataFrame) -> None:
    if gap_product.empty:
        return
    data = gap_product[gap_product["member_missing_count"].gt(0)].copy().head(18)
    if data.empty:
        return
    data = data.sort_values("member_missing_count", ascending=True)
    fig, ax = plt.subplots(figsize=(11, max(5, 0.38 * len(data))))
    labels = data["product"].astype(str)
    ax.barh(labels, data["member_missing_count"], color="#9ecae1", label="missing lot count")
    ax2 = ax.twiny()
    ax2.plot(data["missing_net_pnl"] / 10000.0, labels, color="#d62728", marker="o", linewidth=1.0, label="missing net PnL (w)")
    ax.set_title("Top member-rank backfill product gaps")
    ax.set_xlabel("missing lot count")
    ax2.set_xlabel("missing net PnL, 10k CNY")
    ax.grid(True, axis="x", alpha=0.25)
    lines, line_labels = ax.get_legend_handles_labels()
    lines2, line_labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines + lines2, line_labels + line_labels2, loc="lower right")
    fig.tight_layout()
    fig.savefig(PRODUCT_GAP_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_route_readiness(route_audit: pd.DataFrame) -> None:
    if route_audit.empty:
        return
    data = route_audit.set_index("exchange")[
        [
            "stage620_callable_present",
            "stage620_collector_implemented",
            "stage620_history_selector_allowed",
            "current_smoke_target_hit",
            "readiness_score",
        ]
    ].copy()
    values = data.to_numpy(dtype=float)
    values[:, -1] = values[:, -1] / 100.0
    fig, ax = plt.subplots(figsize=(10, max(4, 0.7 * len(data))))
    image = ax.imshow(values, aspect="auto", cmap="RdYlGn", vmin=0.0, vmax=1.0)
    ax.set_yticks(np.arange(len(data.index)))
    ax.set_yticklabels(data.index)
    ax.set_xticks(np.arange(len(data.columns)))
    ax.set_xticklabels(["callable", "collector", "history selector", "smoke hit", "score"], rotation=35, ha="right")
    ax.set_title("Member-rank route readiness audit")
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            text = f"{values[i, j]:.2f}" if j == values.shape[1] - 1 else f"{values[i, j]:.0f}"
            ax.text(j, i, text, ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(ROUTE_READINESS_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    features: pd.DataFrame,
    gap_year: pd.DataFrame,
    gap_product: pd.DataFrame,
    gap_exchange_year: pd.DataFrame,
    route_audit: pd.DataFrame,
    smoke: pd.DataFrame,
    summary: pd.DataFrame,
    decision: dict[str, Any],
    metrics: dict[str, float],
) -> None:
    missing = features[features["member_missing"]]
    ready = features[features["member_ready"]]
    report = f"""# {STAGE} 会员持仓覆盖缺口与接口可行性视觉审计

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} CST
- 阶段性质：覆盖缺口 / 数据源路线审计；不新增交易规则、不改正式配置、不连接 CTP、不调用下单。
- 是否重要突破：否
- 是否触发A/B：否
- 当前官方正式版：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`

## 外部调研与判断

- AKShare 期货文档显示 `futures_dce_position_rank` 可获取 DCE 指定交易日会员持仓排名，并标注 DCE 接口理论上可取 2000 年以来数据；同页还显示 `futures_gfex_position_rank` 只能从 `2023-11-10` 开始。
- AKShare GitHub issue `#7002` 在 2026-01-26 报告 `futures_dce_position_rank` 出现 `BadZipFile: File is not a zip file`，与本仓 Stage599 的 DCE 探针错误一致。
- AKShare changelog 显示 2025-11-03 `get_czce_rank_table` 更名为 `get_rank_table_czce`，且修复过 CZCE rank table；这说明接口名和解析器会变，不宜直接把函数存在当成历史回测可用。
- AKShare README 说明它是开源财经数据接口库，推荐升级到最新版；本地版本为脚本 smoke 中记录的版本，但本阶段不升级依赖、不改变环境，只做现状审计。
- 我的判断：会员持仓仍是有研究价值的外生源，但当前路线不是 alpha 规则问题，而是历史覆盖和解析器问题。补齐前继续扫 TopN、rolling、权重、阈值，只会把 17% 覆盖样本过拟合。

## 官方基准指标

- 期末权益：`{metrics['end_equity']:,.2f}`
- 总收益：`{metrics['total_return_pct']:.4f}%`
- 最大回撤：`{metrics['max_drawdown_pct']:.4f}%`
- Sharpe：`{metrics['sharpe']:.4f}`
- 总滑点：`{metrics['total_slippage']:,.0f}`
- 总交易次数：`{metrics['total_trade_count']:,.0f}`
- closed-lot 胜率：`{metrics['closed_lot_win_rate_pct']:.4f}%`

## 缺口总览

- official closed lots：`{len(features)}`
- member ready：`{len(ready)}`，覆盖率 `{len(ready) / len(features) * 100.0 if len(features) else 0.0:.4f}%`
- member missing：`{len(missing)}`，missing net PnL `{missing['realized_pnl'].sum():,.2f}`
- missing exchanges：`{missing['exchange'].nunique()}`
- missing products：`{missing['product'].nunique()}`
- `2020-2022` missing lots：`{decision['missing_2020_2022_count']}`，missing net PnL `{decision['missing_2020_2022_net_pnl']:,.2f}`

## Summary

{_md_table(summary)}

## Year Gap

{_md_table(gap_year)}

## Product Gap Top

{_md_table(gap_product.head(25))}

## Exchange-Year Gap

{_md_table(gap_exchange_year)}

## Route Audit

{_md_table(route_audit)}

## Endpoint Smoke Probe

{_md_table(smoke)}

## 视觉观察

- 资金/回撤/覆盖路径：`{PATH_CHART_OUT}`
  - `2020-2022` 深回撤底座上 active member coverage 基本不可用，说明当前缓存不能解释主回撤。
- ready vs missing 贡献曲线：`{GAP_CONTRIBUTION_CHART_OUT}`
  - missing 组承担大量正净贡献，补数是为了提升外生状态可见性，不是为了直接削掉 missing。
- 交易所-年份缺口热图：`{EXCHANGE_YEAR_HEATMAP_OUT}`
  - 缺口横跨 DCE/CZCE/SHFE/GFEX，其中 2020-2022 的 DCE/CZCE/SHFE 是关键。
- 产品缺口排行：`{PRODUCT_GAP_CHART_OUT}`
  - 缺口产品不是单一坏品种，不能写产品黑名单；只能作为数据工程优先级。
- route readiness：`{ROUTE_READINESS_CHART_OUT}`
  - callable/collector 存在不等于 history selector 可用；Stage620 中 member_detail 的 `history_selector_allowed` 仍是核心闸门。

## 决策

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## 过拟合反思

- 运行前判断：否。Stage029 不写交易规则，不根据亏损交易筛产品/年份/方向，只做覆盖缺口和接口可行性。
- 运行后判断：否。本阶段结论是“不具备历史回测数据基础”，不是从小样本抽象出削仓规则；如果继续调会员持仓分数参数才是过拟合。

## 继续价值反思

- 运行前判断：有价值。Stage028 证明当前缓存覆盖太低，必须先决定是否补数。
- 运行后判断：有价值但换任务性质。会员持仓路线只有在修复 DCE/CZCE/SHFE/GFEX 历史覆盖、并重新点时绑定后才值得回到策略规则研究；在这之前只适合 forward watch 和数据工程修复。
"""
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-smoke", action="store_true", help="skip live AKShare endpoint smoke probes")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features = _load_features()
    official_curve = _load_official_curve()
    active_share = _read_csv(ACTIVE_SHARE_IN)
    stage548_route = _read_csv(STAGE548_ROUTE_SUMMARY_IN, required=False)
    stage548_probe = _read_csv(STAGE548_PROBE_DETAIL_IN, required=False)
    stage599_readiness = _read_csv(STAGE599_ROUTE_READINESS_IN, required=False)
    stage599_probe = _read_csv(STAGE599_AKSHARE_PROBE_IN, required=False)
    stage620_contract = _read_csv(STAGE620_CONTRACT_IN, required=False)

    gap_year = _aggregate_gap_by_year(features)
    gap_product = _aggregate_gap_by_product(features)
    gap_exchange_year = _aggregate_gap_by_exchange_year(features)
    smoke = _run_smoke_probes(skip=args.skip_smoke)
    route_audit = _build_route_audit(
        features,
        gap_product,
        smoke,
        stage548_route,
        stage548_probe,
        stage599_readiness,
        stage599_probe,
        stage620_contract,
    )
    summary = _build_summary(features, gap_year, route_audit)
    metrics = _official_metrics(official_curve, features)
    decision = _build_decision(features, gap_year, gap_product, route_audit, smoke, metrics)

    gap_year.to_csv(GAP_YEAR_OUT, index=False, encoding="utf-8-sig")
    gap_product.to_csv(GAP_PRODUCT_OUT, index=False, encoding="utf-8-sig")
    gap_exchange_year.to_csv(GAP_EXCHANGE_YEAR_OUT, index=False, encoding="utf-8-sig")
    smoke.to_csv(SMOKE_PROBE_OUT, index=False, encoding="utf-8-sig")
    route_audit.to_csv(ROUTE_AUDIT_OUT, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    _plot_path(official_curve, active_share)
    _plot_gap_contribution(features)
    _plot_exchange_year_heatmap(gap_exchange_year)
    _plot_product_gap(gap_product)
    _plot_route_readiness(route_audit)
    _write_report(features, gap_year, gap_product, gap_exchange_year, route_audit, smoke, summary, decision, metrics)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
