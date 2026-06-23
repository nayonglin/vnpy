from __future__ import annotations

from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage107"
MODEL_TAG = "stage107_contract_month_oi_patched_root_reaudit_v1"
OUTPUT_PREFIX = "qmt_roll_stage107_c9_minrisk_contract_month_oi_patched_root_reaudit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage107_contract_month_oi_patched_root_reaudit"
PATCHED_ROOT = OUTPUT_DIR / "patched_tqsdk_daily_2010_2026_04_overlay"
PRIMARY_ROOT = REPO_DIR / "examples" / "portfolio_backtesting" / "downloaded_futures" / "tqsdk_daily_2010_2026_04"

STAGE104_SCRIPT = LINE_DIR / "tools" / "stage104_contract_month_oi_migration_readiness_audit.py"
STAGE105_DIR = LINE_DIR / "outputs" / "stage105_contract_month_oi_gap_repair_manifest"
STAGE106_DIR = LINE_DIR / "outputs" / "stage106_contract_month_oi_tqsdk_backtest_backfill_smoke"

REPAIR_MANIFEST_IN = (
    STAGE105_DIR
    / "qmt_roll_stage105_c9_minrisk_contract_month_oi_gap_repair_manifest_repair_manifest_"
    "stage105_contract_month_oi_gap_repair_manifest_v1.csv"
)
GAP_ROWS105_IN = (
    STAGE105_DIR
    / "qmt_roll_stage105_c9_minrisk_contract_month_oi_gap_repair_manifest_gap_rows_"
    "stage105_contract_month_oi_gap_repair_manifest_v1.csv"
)
SUMMARY106_IN = (
    STAGE106_DIR
    / "qmt_roll_stage106_c9_minrisk_contract_month_oi_tqsdk_backtest_backfill_smoke_summary_"
    "stage106_contract_month_oi_tqsdk_backtest_backfill_smoke_v1.csv"
)
PROVENANCE106_IN = (
    STAGE106_DIR
    / "qmt_roll_stage106_c9_minrisk_contract_month_oi_tqsdk_backtest_backfill_smoke_raw_provenance_"
    "stage106_contract_month_oi_tqsdk_backtest_backfill_smoke_v1.csv"
)
CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

OVERLAY_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_overlay_manifest_{MODEL_TAG}.csv"
FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
PRODUCT_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_coverage_{MODEL_TAG}.csv"
RANK_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rank_summary_{MODEL_TAG}.csv"
PROMOTION_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_adjusted_coverage_{MODEL_TAG}.png"
PRODUCT_YEAR_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_adjusted_heatmap_{MODEL_TAG}.png"
RANK_SHARE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rank_share_recomputed_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_{MODEL_TAG}.png"

FORCE_REBUILD = os.getenv("STAGE107_FORCE_REBUILD", "1").strip() == "1"
MIN_TARGET_COVERAGE_PCT = 95.0


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


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _schema_hash(columns: list[str]) -> str:
    return hashlib.sha256(",".join(columns).encode("utf-8")).hexdigest()


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _import_stage104_module() -> Any:
    spec = importlib.util.spec_from_file_location("stage104_contract_month_oi_migration_readiness_audit", STAGE104_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {STAGE104_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _relative_primary_path(primary_expected_path: Any) -> Path:
    text = str(primary_expected_path)
    marker = "tqsdk_daily_2010_2026_04/"
    if marker not in text:
        raise RuntimeError(f"cannot derive primary relative path from {text}")
    return Path(text.split(marker, 1)[1])


def _reset_patched_root() -> None:
    if PATCHED_ROOT.exists() and FORCE_REBUILD:
        shutil.rmtree(PATCHED_ROOT)
    PATCHED_ROOT.mkdir(parents=True, exist_ok=True)


def _link_primary_files() -> int:
    count = 0
    for source in sorted(PRIMARY_ROOT.rglob("*.csv")):
        rel = source.relative_to(PRIMARY_ROOT)
        target = PATCHED_ROOT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            continue
        try:
            target.symlink_to(source.resolve())
        except OSError:
            shutil.copy2(source, target)
        count += 1
    return count


def _convert_raw_to_primary_schema(raw_path: Path) -> pd.DataFrame:
    raw = _read_csv(raw_path)
    required = ["trade_date", "bar_datetime", "open", "high", "low", "close", "volume", "open_oi", "close_oi"]
    missing = [column for column in required if column not in raw.columns]
    if missing:
        raise RuntimeError(f"raw file missing columns {missing}: {raw_path}")
    out = raw.copy()
    out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    out["datetime"] = pd.to_datetime(out["bar_datetime"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    columns = ["trade_date", "datetime", "open", "high", "low", "close", "volume", "open_oi", "close_oi"]
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    out = out.dropna(subset=["trade_date"])
    return out[columns].drop_duplicates(["trade_date"]).sort_values("trade_date").reset_index(drop=True)


def _materialize_overlay() -> pd.DataFrame:
    _reset_patched_root()
    linked_count = _link_primary_files()
    repair = _read_csv(REPAIR_MANIFEST_IN)
    provenance = _read_csv(PROVENANCE106_IN)
    merged = repair.merge(provenance, on=["vt_symbol", "download_symbol"], how="left", suffixes=("", "_stage106"))
    rows: list[dict[str, Any]] = []
    for item in merged.itertuples(index=False):
        rel = _relative_primary_path(item.primary_expected_path)
        target = PATCHED_ROOT / rel
        raw_path = Path(str(item.raw_path))
        converted = _convert_raw_to_primary_schema(raw_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            target.unlink()
        converted.to_csv(target, index=False, encoding="utf-8-sig")
        rows.append(
            {
                "vt_symbol": str(item.vt_symbol),
                "download_symbol": str(item.download_symbol),
                "exchange": str(item.exchange),
                "target_contract": str(item.target_contract),
                "primary_relative_path": str(rel),
                "stage106_raw_path": str(raw_path),
                "patched_path": str(target),
                "patched_rows": int(len(converted)),
                "patched_date_min": converted["trade_date"].min() if not converted.empty else "",
                "patched_date_max": converted["trade_date"].max() if not converted.empty else "",
                "patched_sha256": _sha256(target),
                "patched_schema_hash": _schema_hash(list(converted.columns)),
                "stage106_sha256": str(getattr(item, "sha256", "")),
                "stage106_schema_hash": str(getattr(item, "schema_hash", "")),
                "raw_merge_to_primary_root": 0,
                "primary_symlink_count_at_rebuild": linked_count,
            }
        )
    return pd.DataFrame(rows)


def _calendar_adjacent_candidate_set() -> set[int]:
    gap = _read_csv(GAP_ROWS105_IN)
    selected = gap[gap["repair_action"].eq("calendar_holiday_gap_accept_with_trading_day_gate")].copy()
    return set(pd.to_numeric(selected["candidate_index"], errors="coerce").dropna().astype(int))


def _build_adjusted_features(stage104: Any) -> pd.DataFrame:
    stage104.TQSDK_DAILY_DIR = PATCHED_ROOT
    if hasattr(stage104._load_product_panel, "cache_clear"):
        stage104._load_product_panel.cache_clear()
    rows = stage104._load_stage102_rows()
    features = stage104._build_features(rows)
    calendar_candidates = _calendar_adjacent_candidate_set()
    features["calendar_holiday_adjacent_accept"] = features["candidate_index"].astype(int).isin(calendar_candidates).astype(int)
    features["adjusted_panel_ready"] = np.where(
        features["panel_ready"].eq(1)
        | (
            features["calendar_holiday_adjacent_accept"].eq(1)
            & features["target_contract_found_active"].eq(1)
            & features["readiness_state"].eq("stale_source_date")
        ),
        1,
        0,
    )
    features["adjusted_readiness_state"] = features["readiness_state"]
    features.loc[
        features["panel_ready"].eq(0) & features["adjusted_panel_ready"].eq(1),
        "adjusted_readiness_state",
    ] = "panel_ready_calendar_adjacent"
    features["patched_root"] = str(PATCHED_ROOT)
    features["rule_allowed"] = 0
    features["true_engine_allowed"] = 0
    features["ab_allowed"] = 0
    return features


def _product_year(features: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        features.groupby(["stage104_product_key", "entry_year"], dropna=False)
        .agg(
            order_count=("candidate_index", "count"),
            strict_panel_ready_count=("panel_ready", "sum"),
            adjusted_panel_ready_count=("adjusted_panel_ready", "sum"),
            target_found_active_count=("target_contract_found_active", "sum"),
            right_tail_count=("right_tail_visual", "sum"),
            bottom_loss_count=("bottom_loss_visual", "sum"),
            pnl_sum=("order_realized_pnl", "sum"),
        )
        .reset_index()
    )
    grouped["strict_panel_ready_rate_pct"] = grouped["strict_panel_ready_count"] / grouped["order_count"] * 100.0
    grouped["adjusted_panel_ready_rate_pct"] = grouped["adjusted_panel_ready_count"] / grouped["order_count"] * 100.0
    return grouped.sort_values(["entry_year", "stage104_product_key"]).reset_index(drop=True)


def _rank_summary(features: pd.DataFrame) -> pd.DataFrame:
    frame = features.copy()
    frame["rank_bucket_adjusted"] = frame["target_rank_bucket"].where(
        frame["adjusted_panel_ready"].eq(1), frame["adjusted_readiness_state"]
    )
    grouped = (
        frame.groupby("rank_bucket_adjusted", dropna=False)
        .agg(
            order_count=("candidate_index", "count"),
            pnl_sum=("order_realized_pnl", "sum"),
            right_tail_count=("right_tail_visual", "sum"),
            bottom_loss_count=("bottom_loss_visual", "sum"),
            median_target_oi_share=("target_oi_share", "median"),
        )
        .reset_index()
        .sort_values("rank_bucket_adjusted")
    )
    return grouped.reset_index(drop=True)


def _nearest_curve_points(curve: pd.DataFrame, event_dates: pd.Series) -> pd.DataFrame:
    left = pd.DataFrame({"event_date": pd.to_datetime(event_dates, errors="coerce").dt.normalize()}).dropna()
    right = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].sort_values("date")
    return pd.merge_asof(left.sort_values("event_date"), right, left_on="event_date", right_on="date", direction="backward")


def _plot_path(curve: pd.DataFrame, features: pd.DataFrame) -> None:
    plot_features = features.copy()
    plot_features["official_open_date"] = pd.to_datetime(plot_features["official_open_date"], errors="coerce").dt.normalize()
    merged = _nearest_curve_points(curve, plot_features["official_open_date"])
    plot_features = plot_features.sort_values("official_open_date").reset_index(drop=True)
    merged = merged.reset_index(drop=True)
    if len(plot_features) == len(merged):
        plot_features = pd.concat(
            [plot_features, merged[["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]]], axis=1
        )
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#111827", lw=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[0].set_title("Stage107 patched-root adjusted OI panel coverage")
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#b91c1c", lw=1.0)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#0369a1", lw=1.0)
    axes[2].axhline(100, color="#991b1b", ls="--", lw=0.8)
    axes[2].set_ylabel("broker10 %")

    colors = {
        "panel_ready": "#15803d",
        "panel_ready_calendar_adjacent": "#65a30d",
        "stale_source_date": "#f97316",
        "target_contract_not_in_product_panel": "#dc2626",
        "target_contract_inactive_or_absent": "#f59e0b",
    }
    for state, group in plot_features.groupby("adjusted_readiness_state"):
        color = colors.get(state, "#6b7280")
        size = np.where(group["right_tail_visual"].eq(1), 58, 26)
        edge = np.where(group["bottom_loss_visual"].eq(1), "#111827", "white")
        for ax, column, scale in [
            (axes[0], "account_equity", 1_000_000),
            (axes[1], "drawdown_pct", 1),
            (axes[2], "broker10_margin_to_equity_pct", 1),
        ]:
            ax.scatter(
                group["official_open_date"],
                group[column] / scale,
                s=size,
                c=color,
                edgecolors=edge,
                linewidths=0.5,
                alpha=0.82,
                label=state if ax is axes[0] else None,
            )
    axes[0].legend(loc="upper left", fontsize=8, ncols=2)
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_product_year(product_year: pd.DataFrame) -> None:
    pivot = product_year.pivot(index="stage104_product_key", columns="entry_year", values="adjusted_panel_ready_rate_pct").sort_index()
    fig, ax = plt.subplots(figsize=(13, max(7, 0.35 * len(pivot))))
    image = ax.imshow(pivot.to_numpy(dtype=float), vmin=0, vmax=100, cmap="RdYlGn", aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([str(int(col)) for col in pivot.columns], rotation=45, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for y, product_key in enumerate(pivot.index):
        for x, year in enumerate(pivot.columns):
            value = pivot.loc[product_key, year]
            if pd.isna(value):
                continue
            row = product_year[
                (product_year["stage104_product_key"] == product_key) & (product_year["entry_year"] == year)
            ].iloc[0]
            ax.text(
                x,
                y,
                f"{int(row.adjusted_panel_ready_count)}/{int(row.order_count)}",
                ha="center",
                va="center",
                fontsize=7,
            )
    ax.set_title("Stage107 adjusted panel-ready rate by product-year")
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02, label="adjusted ready %")
    fig.tight_layout()
    fig.savefig(PRODUCT_YEAR_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_rank_share(features: pd.DataFrame, rank_summary: pd.DataFrame) -> None:
    fig, (ax_bar, ax_scatter) = plt.subplots(2, 1, figsize=(14, 9), gridspec_kw={"height_ratios": [1, 1.4]})
    colors = [
        "#15803d" if "rank_1" in str(bucket) else "#2563eb" if "rank_2" in str(bucket) else "#f59e0b"
        for bucket in rank_summary["rank_bucket_adjusted"]
    ]
    ax_bar.bar(rank_summary["rank_bucket_adjusted"], rank_summary["order_count"], color=colors, alpha=0.85)
    ax_bar.set_title("Stage107 recomputed target OI rank distribution; diagnostic only")
    ax_bar.set_ylabel("orders")
    ax_bar.tick_params(axis="x", rotation=20)
    ax_bar.grid(axis="y", alpha=0.25)

    ready = features[features["adjusted_panel_ready"].eq(1)].copy()
    color_map = {"rank_1_main": "#15803d", "rank_2_secondary": "#2563eb", "rank_3plus_tail": "#f59e0b"}
    for bucket, group in ready.groupby("target_rank_bucket"):
        ax_scatter.scatter(
            pd.to_datetime(group["official_open_date"], errors="coerce"),
            group["target_oi_share"] * 100.0,
            s=np.where(group["right_tail_visual"].eq(1), 75, 28),
            color=color_map.get(bucket, "#6b7280"),
            edgecolors=np.where(group["bottom_loss_visual"].eq(1), "#111827", "white"),
            linewidths=0.5,
            alpha=0.82,
            label=bucket,
        )
    ax_scatter.set_ylabel("target OI share %")
    ax_scatter.set_xlabel("entry date")
    ax_scatter.grid(alpha=0.25)
    ax_scatter.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(RANK_SHARE_CHART_OUT, dpi=160)
    plt.close(fig)


def _build_gate(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {
            "gate": "patched_root_overlay_materialized",
            "pass": int(summary["overlay_target_file_count"] == summary["stage106_raw_file_count"]),
            "detail": f"{summary['overlay_target_file_count']}/{summary['stage106_raw_file_count']}",
        },
        {
            "gate": "raw_and_overlay_provenance_complete",
            "pass": int(summary["overlay_provenance_complete_count"] == summary["overlay_target_file_count"]),
            "detail": f"{summary['overlay_provenance_complete_count']}/{summary['overlay_target_file_count']}",
        },
        {
            "gate": "target_contract_adjusted_coverage_ge95pct",
            "pass": int(summary["adjusted_panel_ready_rate_pct"] >= MIN_TARGET_COVERAGE_PCT),
            "detail": f"{summary['adjusted_panel_ready_count']}/{summary['timestamp_ready_order_count']}",
        },
        {
            "gate": "source_age_or_calendar_adjacent_all_orders",
            "pass": int(summary["source_age_le7_or_calendar_adjacent_count"] == summary["timestamp_ready_order_count"]),
            "detail": f"{summary['source_age_le7_or_calendar_adjacent_count']}/{summary['timestamp_ready_order_count']}",
        },
        {
            "gate": "right_tail_and_bottom_loss_full_adjusted_coverage",
            "pass": int(
                summary["right_tail_adjusted_ready_count"] == summary["right_tail_total_count"]
                and summary["bottom_loss_adjusted_ready_count"] == summary["bottom_loss_total_count"]
            ),
            "detail": f"rt={summary['right_tail_adjusted_ready_count']}/{summary['right_tail_total_count']}, bl={summary['bottom_loss_adjusted_ready_count']}/{summary['bottom_loss_total_count']}",
        },
        {
            "gate": "product_year_no_adjusted_hard_gap",
            "pass": int(summary["adjusted_product_year_hard_gap_cell_count"] == 0),
            "detail": f"hard_gap={summary['adjusted_product_year_hard_gap_cell_count']}",
        },
        {
            "gate": "primary_daily_root_mutated",
            "pass": 0,
            "detail": "intentionally_false_overlay_only",
        },
        {
            "gate": "true_engine_or_ab_allowed",
            "pass": 0,
            "detail": "data_contract_only",
        },
    ]
    return pd.DataFrame(rows)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 5.8))
    colors = np.where(gate["pass"].eq(1), "#15803d", "#dc2626")
    ax.barh(gate["gate"], gate["pass"], color=colors, alpha=0.9)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("pass")
    ax.set_title("Stage107 promotion gates")
    for y, (_, row) in enumerate(gate.iterrows()):
        ax.text(0.03, y, str(row["detail"]), va="center", fontsize=8, color="white" if int(row["pass"]) else "#111827")
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _summary(
    features: pd.DataFrame,
    overlay: pd.DataFrame,
    product_year: pd.DataFrame,
    summary106: pd.Series,
) -> dict[str, Any]:
    order_count = int(len(features))
    strict_ready = int(features["panel_ready"].sum())
    adjusted_ready = int(features["adjusted_panel_ready"].sum())
    source_adjacent = int(features["calendar_holiday_adjacent_accept"].sum())
    source_ok = int((features["source_age_days"].le(7) | features["calendar_holiday_adjacent_accept"].eq(1)).sum())
    right_tail_total = int(features["right_tail_visual"].sum())
    bottom_loss_total = int(features["bottom_loss_visual"].sum())
    right_tail_ready = int(features.loc[features["adjusted_panel_ready"].eq(1), "right_tail_visual"].sum())
    bottom_loss_ready = int(features.loc[features["adjusted_panel_ready"].eq(1), "bottom_loss_visual"].sum())
    comparable = features[features["adjusted_panel_ready"].eq(1)]
    overlay_complete = int(
        (
            overlay["patched_sha256"].astype(str).ne("")
            & overlay["patched_schema_hash"].astype(str).ne("")
            & overlay["stage106_sha256"].astype(str).ne("")
            & overlay["stage106_schema_hash"].astype(str).ne("")
        ).sum()
    )
    strict_hard_gap = int((product_year["strict_panel_ready_rate_pct"] < MIN_TARGET_COVERAGE_PCT).sum())
    adjusted_hard_gap = int((product_year["adjusted_panel_ready_rate_pct"] < MIN_TARGET_COVERAGE_PCT).sum())
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": "stage107_patched_root_contract_coverage_fixed_single_contract_panel_blocks_rule",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "primary_daily_root_mutated": 0,
        "primary_symlink_count": int(overlay["primary_symlink_count_at_rebuild"].max()) if not overlay.empty else 0,
        "stage106_raw_file_count": int(float(summary106["backtest_downloaded_or_cached_count"])),
        "overlay_target_file_count": int(len(overlay)),
        "overlay_provenance_complete_count": overlay_complete,
        "timestamp_ready_order_count": order_count,
        "strict_panel_ready_count": strict_ready,
        "strict_panel_ready_rate_pct": strict_ready / order_count * 100.0 if order_count else 0.0,
        "adjusted_panel_ready_count": adjusted_ready,
        "adjusted_panel_ready_rate_pct": adjusted_ready / order_count * 100.0 if order_count else 0.0,
        "target_contract_found_active_count": int(features["target_contract_found_active"].sum()),
        "target_contract_missing_count": int(features["target_contract_found_active"].eq(0).sum()),
        "source_age_le7_count": int(features["source_age_days"].le(7).sum()),
        "calendar_holiday_adjacent_accept_count": source_adjacent,
        "source_age_le7_or_calendar_adjacent_count": source_ok,
        "right_tail_total_count": right_tail_total,
        "right_tail_adjusted_ready_count": right_tail_ready,
        "bottom_loss_total_count": bottom_loss_total,
        "bottom_loss_adjusted_ready_count": bottom_loss_ready,
        "target_rank1_count": int(comparable["target_rank_bucket"].eq("rank_1_main").sum()),
        "target_rank2_count": int(comparable["target_rank_bucket"].eq("rank_2_secondary").sum()),
        "target_rank3plus_count": int(comparable["target_rank_bucket"].eq("rank_3plus_tail").sum()),
        "single_contract_panel_count": int(features["readiness_state"].eq("single_contract_panel").sum()),
        "strict_product_year_hard_gap_cell_count": strict_hard_gap,
        "adjusted_product_year_hard_gap_cell_count": adjusted_hard_gap,
        "promotion_gate_count": 8,
        "promotion_gate_pass_count": 0,
        "panel_feature_rule_allowed": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "end_equity": float(summary106["end_equity"]),
        "total_return_pct": float(summary106["total_return_pct"]),
        "max_drawdown_pct": float(summary106["max_drawdown_pct"]),
        "sharpe": float(summary106["sharpe"]),
        "total_slippage": float(summary106["total_slippage"]),
        "total_trade_count": float(summary106["total_trade_count"]),
        "closed_lot_win_rate_pct": float(summary106["closed_lot_win_rate_pct"]),
        "max_broker10_margin_to_equity_pct": float(summary106["max_broker10_margin_to_equity_pct"]),
    }


def _write_report(summary: dict[str, Any], overlay: pd.DataFrame, product_year: pd.DataFrame, rank: pd.DataFrame, gate: pd.DataFrame) -> None:
    lines = [
        "# Stage107 contract-month OI patched root reaudit",
        "",
        "## Decision",
        "",
        f"- decision: `{summary['decision']}`",
        "- This stage materializes an isolated patched daily root under this line output only. It does not mutate the primary daily root and does not create a trading rule.",
        "",
        "## Key Metrics",
        "",
        _md_table(pd.DataFrame([summary])),
        "",
        "## Promotion Gates",
        "",
        _md_table(gate),
        "",
        "## Overlay Manifest",
        "",
        _md_table(
            overlay[
                [
                    "download_symbol",
                    "primary_relative_path",
                    "patched_rows",
                    "patched_date_min",
                    "patched_date_max",
                    "patched_sha256",
                    "patched_schema_hash",
                ]
            ],
            max_rows=25,
        ),
        "",
        "## Product-Year Adjusted Coverage",
        "",
        _md_table(
            product_year[
                [
                    "stage104_product_key",
                    "entry_year",
                    "order_count",
                    "strict_panel_ready_count",
                    "adjusted_panel_ready_count",
                    "adjusted_panel_ready_rate_pct",
                ]
            ],
            max_rows=60,
        ),
        "",
        "## Rank Summary",
        "",
        _md_table(rank),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT}`",
        f"- `{PRODUCT_YEAR_CHART_OUT}`",
        f"- `{RANK_SHARE_CHART_OUT}`",
        f"- `{GATE_CHART_OUT}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    overlay = _materialize_overlay()
    overlay.to_csv(OVERLAY_MANIFEST_OUT, index=False, encoding="utf-8-sig")

    stage104 = _import_stage104_module()
    features = _build_adjusted_features(stage104)
    features.to_csv(FEATURES_OUT, index=False, encoding="utf-8-sig")

    product_year = _product_year(features)
    product_year.to_csv(PRODUCT_YEAR_OUT, index=False, encoding="utf-8-sig")

    rank = _rank_summary(features)
    rank.to_csv(RANK_SUMMARY_OUT, index=False, encoding="utf-8-sig")

    summary106 = _read_csv(SUMMARY106_IN).iloc[0]
    summary = _summary(features, overlay, product_year, summary106)
    gate = _build_gate(summary)
    summary["promotion_gate_pass_count"] = int(gate["pass"].sum())
    gate.to_csv(PROMOTION_GATE_OUT, index=False, encoding="utf-8-sig")

    pd.DataFrame([summary]).to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(summary), ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    curve = _load_curve()
    _plot_path(curve, features)
    _plot_product_year(product_year)
    _plot_rank_share(features, rank)
    _plot_gate(gate)
    _write_report(summary, overlay, product_year, rank, gate)
    print(json.dumps(_json_safe(summary), ensure_ascii=True, indent=2), flush=True)


if __name__ == "__main__":
    main()
