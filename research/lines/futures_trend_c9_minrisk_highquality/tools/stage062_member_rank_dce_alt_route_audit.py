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
STAGE = "Stage062"
MODEL_TAG = "stage062_member_rank_dce_alt_route_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage062_c9_minrisk_member_rank_dce_alt_route_audit"

INITIAL_CAPITAL = 150_000.0
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
OUTPUT_DIR = LINE_DIR / "outputs" / "stage062_member_rank_dce_alt_route_audit"

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

FUNCTION_INVENTORY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_function_inventory_{MODEL_TAG}.csv"
ENDPOINT_SMOKE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_endpoint_smoke_{MODEL_TAG}.csv"
EXCHANGE_GAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_exchange_gap_summary_{MODEL_TAG}.csv"
PRODUCT_GAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_gap_summary_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_COVERAGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_coverage_chart_{MODEL_TAG}.png"
MISSING_EXCHANGE_CONTRIB_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_missing_exchange_contribution_chart_{MODEL_TAG}.png"
DCE_ROUTE_STATUS_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dce_route_status_chart_{MODEL_TAG}.png"
PRODUCT_GAP_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_gap_chart_{MODEL_TAG}.png"


CHILD_PROBE_CODE = r"""
import inspect
import json
import sys
import traceback

import akshare as ak
import pandas as pd


def hit_product_in_frame(frame, products):
    hits = set()
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return hits
    for column in frame.columns:
        values = frame[column].astype(str).str.upper()
        for product in products:
            if values.str.contains(str(product).upper(), regex=False).any():
                hits.add(str(product).upper())
    return hits


def summarize_result(result, products):
    products = [str(item).upper() for item in products]
    if isinstance(result, dict):
        rows = 0
        columns = []
        hits = set()
        keys = [str(key) for key in result.keys()]
        for key, value in result.items():
            key_upper = str(key).upper()
            for product in products:
                if product in key_upper:
                    hits.add(product)
            if isinstance(value, pd.DataFrame):
                rows += int(len(value))
                columns.extend([str(column) for column in value.columns])
                hits |= hit_product_in_frame(value, products)
        return {
            "result_kind": "dict",
            "keys_count": len(keys),
            "sample_keys": "|".join(keys[:12]),
            "rows": rows,
            "columns": "|".join(sorted(set(columns))[:24]),
            "target_hit_count": len(hits),
            "target_hits": "|".join(sorted(hits)),
        }
    if isinstance(result, pd.DataFrame):
        hits = hit_product_in_frame(result, products)
        return {
            "result_kind": "dataframe",
            "keys_count": 0,
            "sample_keys": "",
            "rows": int(len(result)),
            "columns": "|".join([str(column) for column in result.columns[:24]]),
            "target_hit_count": len(hits),
            "target_hits": "|".join(sorted(hits)),
        }
    if isinstance(result, (list, tuple, set)):
        values = [str(item).upper() for item in result]
        hits = {product for product in products if any(product in value for value in values)}
        return {
            "result_kind": type(result).__name__,
            "keys_count": len(values),
            "sample_keys": "|".join(values[:12]),
            "rows": len(values),
            "columns": "",
            "target_hit_count": len(hits),
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
    out = summarize_result(result, spec.get("target_products", []))
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
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        out = float(value)
        return None if np.isnan(out) or np.isinf(out) else out
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    display = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    lines = [
        "| " + " | ".join(str(column) for column in display.columns) + " |",
        "| " + " | ".join(["---"] * len(display.columns)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in display.columns) + " |")
    return "\n".join(lines)


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    features = _read_csv(FEATURES_IN)
    curve = _read_csv(OFFICIAL_CURVE_IN)
    active = _read_csv(ACTIVE_SHARE_IN)

    for column in ["entry_date", "exit_date", "exit_day"]:
        if column in features.columns:
            features[column] = pd.to_datetime(features[column], errors="coerce").dt.normalize()
    features["entry_year"] = pd.to_numeric(features["entry_year"], errors="coerce")
    features["realized_pnl"] = pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0)
    features["member_ready"] = features["member_feature_ready_stage028"].fillna(False).astype(bool)
    features["member_missing"] = ~features["member_ready"]
    features["exchange"] = features["exchange"].fillna("UNKNOWN").astype(str)
    features["product_key_clean"] = features["product_key"].fillna(features["product"]).astype(str)

    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct", "slippage", "trade_count"]:
        curve[column] = pd.to_numeric(curve.get(column, 0.0), errors="coerce").fillna(0.0)

    active["date"] = pd.to_datetime(active["date"], errors="coerce").dt.normalize()
    for column in ["active_lot_count", "member_ready_share_pct", "member_missing_share_pct"]:
        active[column] = pd.to_numeric(active.get(column, 0.0), errors="coerce").fillna(0.0)
    return features, curve, active


def _probe_specs() -> list[dict[str, Any]]:
    return [
        {
            "probe_id": "dce_batch_zip_jm_20240603",
            "exchange": "DCE",
            "function_name": "futures_dce_position_rank",
            "args": ["20240603"],
            "kwargs": {"vars_list": ["JM"]},
            "target_products": ["JM"],
            "timeout_seconds": 12,
            "route_type": "dce_batch_zip",
        },
        {
            "probe_id": "dce_batch_zip_jm_20210301",
            "exchange": "DCE",
            "function_name": "futures_dce_position_rank",
            "args": ["20210301"],
            "kwargs": {"vars_list": ["JM"]},
            "target_products": ["JM"],
            "timeout_seconds": 12,
            "route_type": "dce_batch_zip",
        },
        {
            "probe_id": "dce_rank_table_jm_20240603",
            "exchange": "DCE",
            "function_name": "get_dce_rank_table",
            "args": ["20240603"],
            "kwargs": {"vars_list": ["JM"]},
            "target_products": ["JM"],
            "timeout_seconds": 12,
            "route_type": "dce_old_rank_table",
        },
        {
            "probe_id": "dce_rank_table_jm_20210301",
            "exchange": "DCE",
            "function_name": "get_dce_rank_table",
            "args": ["20210301"],
            "kwargs": {"vars_list": ["JM"]},
            "target_products": ["JM"],
            "timeout_seconds": 12,
            "route_type": "dce_old_rank_table",
        },
        {
            "probe_id": "dce_position_rank_other_20240603",
            "exchange": "DCE",
            "function_name": "futures_dce_position_rank_other",
            "args": ["20240603"],
            "kwargs": {},
            "target_products": ["JM", "I", "LH", "J"],
            "timeout_seconds": 12,
            "route_type": "dce_old_web_all_contracts",
        },
        {
            "probe_id": "dce_position_rank_other_20210301",
            "exchange": "DCE",
            "function_name": "futures_dce_position_rank_other",
            "args": ["20210301"],
            "kwargs": {},
            "target_products": ["JM", "I", "LH", "J"],
            "timeout_seconds": 12,
            "route_type": "dce_old_web_all_contracts",
        },
        {
            "probe_id": "czce_positive_control_20240603",
            "exchange": "CZCE",
            "function_name": "get_rank_table_czce",
            "args": ["20240603"],
            "kwargs": {},
            "target_products": ["OI", "MA", "FG", "AP", "SH"],
            "timeout_seconds": 12,
            "route_type": "positive_control",
        },
        {
            "probe_id": "shfe_positive_control_20240603",
            "exchange": "SHFE",
            "function_name": "get_shfe_rank_table",
            "args": ["20240603"],
            "kwargs": {"vars_list": ["RB", "RU", "AU", "FU", "HC"]},
            "target_products": ["RB", "RU", "AU", "FU", "HC"],
            "timeout_seconds": 12,
            "route_type": "positive_control",
        },
        {
            "probe_id": "gfex_positive_control_20240603",
            "exchange": "GFEX",
            "function_name": "futures_gfex_position_rank",
            "args": ["20240603"],
            "kwargs": {"vars_list": ["SI", "LC"]},
            "target_products": ["SI", "LC"],
            "timeout_seconds": 12,
            "route_type": "positive_control",
        },
    ]


def _function_inventory() -> pd.DataFrame:
    import akshare as ak

    rows = []
    for name in [
        "futures_dce_position_rank",
        "futures_dce_position_rank_other",
        "get_dce_rank_table",
        "get_rank_table_czce",
        "get_shfe_rank_table",
        "futures_gfex_position_rank",
        "get_rank_sum",
    ]:
        func = getattr(ak, name, None)
        rows.append(
            {
                "akshare_version": getattr(ak, "__version__", "unknown"),
                "function_name": name,
                "callable_present": bool(callable(func)),
                "signature": str(__import__("inspect").signature(func)) if callable(func) else "",
                "doc_head": ((__import__("inspect").getdoc(func) or "").splitlines()[0] if callable(func) else ""),
            }
        )
    return pd.DataFrame(rows)


def _run_smoke(skip: bool) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in _probe_specs():
        base = {
            "probe_id": spec["probe_id"],
            "exchange": spec["exchange"],
            "route_type": spec["route_type"],
            "function_name": spec["function_name"],
            "args_json": json.dumps(spec["args"], ensure_ascii=False),
            "kwargs_json": json.dumps(spec["kwargs"], ensure_ascii=False),
            "target_products": "|".join(spec["target_products"]),
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


def _exchange_gap(features: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for exchange, group in features.groupby("exchange", dropna=False):
        missing = group[group["member_missing"]]
        ready = group[group["member_ready"]]
        rows.append(
            {
                "exchange": str(exchange),
                "lot_count": int(len(group)),
                "member_ready_count": int(len(ready)),
                "member_missing_count": int(len(missing)),
                "member_ready_rate_pct": float(len(ready) / len(group) * 100.0) if len(group) else 0.0,
                "missing_2020_2022_count": int(missing[missing["entry_year"].between(2020, 2022, inclusive="both")].shape[0]),
                "ready_net_pnl": float(ready["realized_pnl"].sum()),
                "missing_net_pnl": float(missing["realized_pnl"].sum()),
                "missing_positive_pnl": float(missing["realized_pnl"].clip(lower=0.0).sum()),
                "missing_negative_pnl": float(missing["realized_pnl"].clip(upper=0.0).sum()),
                "missing_product_count": int(missing["product_key_clean"].nunique()),
            }
        )
    return pd.DataFrame(rows).sort_values(["member_missing_count", "missing_net_pnl"], ascending=[False, False])


def _product_gap(features: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (exchange, product), group in features.groupby(["exchange", "product_key_clean"], dropna=False):
        missing = group[group["member_missing"]]
        if missing.empty:
            continue
        rows.append(
            {
                "exchange": str(exchange),
                "product_key": str(product),
                "lot_count": int(len(group)),
                "member_missing_count": int(len(missing)),
                "missing_net_pnl": float(missing["realized_pnl"].sum()),
                "missing_positive_pnl": float(missing["realized_pnl"].clip(lower=0.0).sum()),
                "missing_negative_pnl": float(missing["realized_pnl"].clip(upper=0.0).sum()),
                "first_missing_entry_date": missing["entry_date"].min(),
                "last_missing_entry_date": missing["entry_date"].max(),
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["member_missing_count", "missing_net_pnl"], ascending=[False, False])
    return out


def _performance(curve: pd.DataFrame, features: pd.DataFrame) -> dict[str, float]:
    equity = pd.to_numeric(curve["account_equity"], errors="coerce").dropna()
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    sharpe = np.nan
    if len(returns) > 2 and returns.std(ddof=0) > 0:
        sharpe = float(returns.mean() / returns.std(ddof=0) * np.sqrt(TRADING_DAYS_PER_YEAR))
    pnl = pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0)
    return {
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / INITIAL_CAPITAL - 1.0) * 100.0),
        "max_dd_pct": float(pd.to_numeric(curve["drawdown_pct"], errors="coerce").min()),
        "daily_sharpe_proxy": sharpe,
        "total_slippage": float(pd.to_numeric(curve["slippage"], errors="coerce").sum()),
        "total_trade_count": float(pd.to_numeric(curve["trade_count"], errors="coerce").sum()),
        "closed_lot_win_rate_pct": float((pnl > 0).mean() * 100.0),
    }


def _plot_path_coverage(curve: pd.DataFrame, active: pd.DataFrame) -> None:
    merged = curve.merge(active, on="date", how="left")
    fig, axes = plt.subplots(4, 1, figsize=(15, 12), sharex=True)
    axes[0].plot(merged["date"], merged["account_equity"], color="#1f77b4", lw=1.4)
    axes[0].set_yscale("log")
    axes[0].set_title("Stage062 official equity and member-rank coverage gap")
    axes[0].axvspan(pd.Timestamp("2020-01-01"), pd.Timestamp("2022-12-31"), color="#f2c078", alpha=0.18)
    axes[1].plot(merged["date"], merged["drawdown_pct"], color="#d62728", lw=1.0)
    axes[1].axhline(-40, color="#777777", ls="--", lw=0.8)
    axes[1].axvspan(pd.Timestamp("2020-01-01"), pd.Timestamp("2022-12-31"), color="#f2c078", alpha=0.18)
    axes[2].plot(merged["date"], merged["broker10_margin_to_equity_pct"], color="#9467bd", lw=0.9)
    axes[2].axhline(100, color="#777777", ls="--", lw=0.8)
    axes[3].plot(merged["date"], merged["member_ready_share_pct"], color="#2ca02c", lw=1.0, label="member ready active share")
    axes[3].plot(merged["date"], merged["member_missing_share_pct"], color="#7f7f7f", lw=1.0, label="member missing active share")
    axes[3].set_ylim(-2, 102)
    axes[3].axvspan(pd.Timestamp("2020-01-01"), pd.Timestamp("2022-12-31"), color="#f2c078", alpha=0.18)
    axes[3].legend(loc="upper left", fontsize=8)
    for ax in axes:
        ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_COVERAGE_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_missing_exchange_contribution(features: pd.DataFrame) -> None:
    calendar = pd.date_range(features["exit_date"].min(), features["exit_date"].max(), freq="D")
    fig, ax = plt.subplots(figsize=(15, 7))
    all_daily = features.groupby("exit_date")["realized_pnl"].sum().reindex(calendar, fill_value=0.0).cumsum()
    ax.plot(calendar, all_daily, color="#1f77b4", lw=1.7, label="all closed lots")
    colors = {"DCE": "#d62728", "CZCE": "#ff7f0e", "SHFE": "#2ca02c", "GFEX": "#9467bd"}
    for exchange, color in colors.items():
        data = features[features["member_missing"] & features["exchange"].eq(exchange)]
        if data.empty:
            continue
        curve = data.groupby("exit_date")["realized_pnl"].sum().reindex(calendar, fill_value=0.0).cumsum()
        ax.plot(calendar, curve, lw=1.2, color=color, label=f"{exchange} member missing")
    ax.axhline(0, color="#555555", lw=0.8)
    ax.set_title("Stage062 member-rank missing PnL contribution by exchange")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(MISSING_EXCHANGE_CONTRIB_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_dce_route_status(smoke: pd.DataFrame) -> None:
    dce = smoke[smoke["exchange"].eq("DCE")].copy()
    if dce.empty:
        return
    status_score = {"ok": 1.0, "error": 0.0, "timeout": 0.0, "process_error": 0.0, "skipped": 0.5}
    dce["ok_score"] = dce["status"].map(status_score).fillna(0.0)
    dce["hit_score"] = pd.to_numeric(dce.get("target_hit_count", 0), errors="coerce").fillna(0.0).gt(0).astype(float)
    matrix = dce.set_index("probe_id")[["ok_score", "hit_score"]]
    fig, ax = plt.subplots(figsize=(8, max(4, 0.55 * len(matrix))))
    values = matrix.to_numpy(dtype=float)
    image = ax.imshow(values, aspect="auto", cmap="RdYlGn", vmin=0.0, vmax=1.0)
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    ax.set_xticks(np.arange(len(matrix.columns)))
    ax.set_xticklabels(["call ok", "target hit"])
    ax.set_title("Stage062 DCE alternative route smoke status")
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{values[i, j]:.0f}", ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.04, pad=0.02)
    fig.tight_layout()
    fig.savefig(DCE_ROUTE_STATUS_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_product_gap(product_gap: pd.DataFrame) -> None:
    data = product_gap.head(18).copy()
    if data.empty:
        return
    data = data.sort_values("member_missing_count", ascending=True)
    fig, ax = plt.subplots(figsize=(11, max(5, 0.35 * len(data))))
    labels = data["product_key"].astype(str)
    ax.barh(labels, data["member_missing_count"], color="#9ecae1", label="missing lot count")
    ax2 = ax.twiny()
    ax2.plot(data["missing_net_pnl"] / 10000.0, labels, color="#d62728", marker="o", lw=1.0, label="missing net PnL (w)")
    ax.set_xlabel("missing lot count")
    ax2.set_xlabel("missing net PnL, 10k")
    ax.set_title("Stage062 member-rank top product gaps")
    ax.grid(True, axis="x", alpha=0.25)
    handles, labels1 = ax.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(handles + handles2, labels1 + labels2, loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(PRODUCT_GAP_CHART_OUT, dpi=150)
    plt.close(fig)


def _build_decision(
    features: pd.DataFrame,
    smoke: pd.DataFrame,
    function_inventory: pd.DataFrame,
    exchange_gap: pd.DataFrame,
    metrics: dict[str, float],
) -> dict[str, Any]:
    ready = features["member_ready"].astype(bool)
    dce_smoke = smoke[smoke["exchange"].eq("DCE")].copy()
    dce_ok_hit = bool(
        (dce_smoke["status"].eq("ok") & pd.to_numeric(dce_smoke.get("target_hit_count", 0), errors="coerce").fillna(0).gt(0)).any()
    ) if not dce_smoke.empty else False
    positive_ok_count = int(
        (
            smoke[smoke["route_type"].eq("positive_control")]["status"].eq("ok")
            & pd.to_numeric(smoke[smoke["route_type"].eq("positive_control")].get("target_hit_count", 0), errors="coerce")
            .fillna(0)
            .gt(0)
        ).sum()
    ) if not smoke.empty else 0
    missing = features[~ready]
    gap_2020_2022 = missing[missing["entry_year"].between(2020, 2022, inclusive="both")]
    if dce_ok_hit:
        decision_name = "stage062_dce_alt_route_possible_requires_backfill_engine"
        next_action = "Implement a point-in-time DCE backfill collector before any member-score rebinding."
    else:
        decision_name = "stage062_dce_alternative_routes_blocked_no_strategy_rule"
        next_action = "Do not continue member-score parameter research; either repair DCE parser outside strategy research or use a different independent source."
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": decision_name,
        "candidate_like": False,
        "ab_triggered": False,
        "strategy_rule_created": False,
        "input_lot_count": int(len(features)),
        "member_ready_count": int(ready.sum()),
        "member_ready_rate_pct": float(ready.mean() * 100.0),
        "member_missing_count": int((~ready).sum()),
        "member_missing_net_pnl": float(missing["realized_pnl"].sum()),
        "missing_2020_2022_count": int(len(gap_2020_2022)),
        "missing_2020_2022_net_pnl": float(gap_2020_2022["realized_pnl"].sum()),
        "dce_alt_route_ok_with_target_hit": dce_ok_hit,
        "positive_control_ok_count": positive_ok_count,
        "akshare_functions": function_inventory.to_dict(orient="records"),
        "dce_smoke": dce_smoke.to_dict(orient="records"),
        "exchange_gap": exchange_gap.to_dict(orient="records"),
        "official_metrics": metrics,
        "judgment": (
            "Member-rank structure remains theoretically valuable, but current DCE alternatives do not prove a usable "
            "history backfill route. Point smoke on other exchanges is not enough for C9 drawdown research because the "
            "main 2020-2022 coverage gap still spans DCE/CZCE/SHFE."
        ),
        "next_action": next_action,
        "guardrails": {
            "no_trade_rule": True,
            "no_parameter_sweep": True,
            "no_ctp_or_order_api": True,
            "endpoint_smoke_not_history_backtest": True,
            "member_missing_keeps_official_path": True,
            "do_not_promote_current_member_rank_cache": True,
        },
        "outputs": {
            "function_inventory": FUNCTION_INVENTORY_OUT,
            "endpoint_smoke": ENDPOINT_SMOKE_OUT,
            "exchange_gap": EXCHANGE_GAP_OUT,
            "product_gap": PRODUCT_GAP_OUT,
            "summary": SUMMARY_OUT,
            "decision": DECISION_OUT,
            "report": REPORT_OUT,
            "path_coverage_chart": PATH_COVERAGE_CHART_OUT,
            "missing_exchange_contribution_chart": MISSING_EXCHANGE_CONTRIB_CHART_OUT,
            "dce_route_status_chart": DCE_ROUTE_STATUS_CHART_OUT,
            "product_gap_chart": PRODUCT_GAP_CHART_OUT,
        },
    }


def _write_report(
    decision: dict[str, Any],
    summary: pd.DataFrame,
    inventory: pd.DataFrame,
    smoke: pd.DataFrame,
    exchange_gap: pd.DataFrame,
    product_gap: pd.DataFrame,
) -> None:
    lines = [
        "# Stage062 member-rank DCE alternative route audit",
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- candidate_like: `{decision['candidate_like']}`",
        f"- strategy_rule_created: `{decision['strategy_rule_created']}`",
        f"- member ready: `{decision['member_ready_count']}/{decision['input_lot_count']}`",
        f"- DCE alternative route target hit: `{decision['dce_alt_route_ok_with_target_hit']}`",
        f"- positive control ok count: `{decision['positive_control_ok_count']}`",
        f"- next action: {decision['next_action']}",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Function Inventory",
        "",
        _md_table(inventory),
        "",
        "## Endpoint Smoke",
        "",
        _md_table(smoke),
        "",
        "## Exchange Gap",
        "",
        _md_table(exchange_gap),
        "",
        "## Product Gap Top",
        "",
        _md_table(product_gap.head(25)),
        "",
        "## Visual Outputs",
        "",
        f"- path coverage: `{PATH_COVERAGE_CHART_OUT}`",
        f"- missing exchange contribution: `{MISSING_EXCHANGE_CONTRIB_CHART_OUT}`",
        f"- DCE route status: `{DCE_ROUTE_STATUS_CHART_OUT}`",
        f"- product gap: `{PRODUCT_GAP_CHART_OUT}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-smoke", action="store_true")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features, curve, active = _load_inputs()
    inventory = _function_inventory()
    smoke = _run_smoke(skip=args.skip_smoke)
    exchange_gap = _exchange_gap(features)
    product_gap = _product_gap(features)
    metrics = _performance(curve, features)
    decision = _build_decision(features, smoke, inventory, exchange_gap, metrics)

    summary = pd.DataFrame(
        [
            {
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "input_lot_count": decision["input_lot_count"],
                "member_ready_count": decision["member_ready_count"],
                "member_ready_rate_pct": decision["member_ready_rate_pct"],
                "member_missing_count": decision["member_missing_count"],
                "member_missing_net_pnl": decision["member_missing_net_pnl"],
                "missing_2020_2022_count": decision["missing_2020_2022_count"],
                "missing_2020_2022_net_pnl": decision["missing_2020_2022_net_pnl"],
                "dce_alt_route_ok_with_target_hit": decision["dce_alt_route_ok_with_target_hit"],
                "positive_control_ok_count": decision["positive_control_ok_count"],
            }
        ]
    )

    inventory.to_csv(FUNCTION_INVENTORY_OUT, index=False, encoding="utf-8-sig")
    smoke.to_csv(ENDPOINT_SMOKE_OUT, index=False, encoding="utf-8-sig")
    exchange_gap.to_csv(EXCHANGE_GAP_OUT, index=False, encoding="utf-8-sig")
    product_gap.to_csv(PRODUCT_GAP_OUT, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    _plot_path_coverage(curve, active)
    _plot_missing_exchange_contribution(features)
    _plot_dce_route_status(smoke)
    _plot_product_gap(product_gap)
    _write_report(decision, summary, inventory, smoke, exchange_gap, product_gap)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
