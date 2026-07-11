#!/usr/bin/env python3
"""Stage011: attribute the Stage010 2021-anchor account-history failure."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parents[4]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage009_gate_opportunity_cost_attribution as s9  # noqa: E402
import stage010_drawdown_recovery_progress_ramp as s10  # noqa: E402


STAGE = "Stage011"
STAGE_ID = "stage011_2021_anchor_path_feedback_attribution"
MODEL_TAG = "stage011_2021_anchor_path_feedback_attribution_v1"
LINE_ID = "futures_trend_stage013_current_ai_revalidation"
SOURCE_START = "2021-01"
WINDOW_START = pd.Timestamp("2022-01-01")
WINDOW_END = pd.Timestamp("2022-12-31")
PATH_START = pd.Timestamp("2021-10-01")
OUT = TOOLS_DIR.parent / "outputs" / STAGE_ID
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = f"stage013_current_ai_{STAGE_ID}"

PEAK_TROUGH_PATH = OUT / f"{PREFIX}_peak_trough_{MODEL_TAG}.csv"
DAILY_PATH = OUT / f"{PREFIX}_daily_path_{MODEL_TAG}.csv.gz"
SIGNAL_PATH = OUT / f"{PREFIX}_signal_attribution_{MODEL_TAG}.csv.gz"
SIGNAL_GROUP_PATH = OUT / f"{PREFIX}_signal_groups_{MODEL_TAG}.csv"
SIZING_PATH = OUT / f"{PREFIX}_sizing_equity_audit_{MODEL_TAG}.csv.gz"
SIZING_STATS_PATH = OUT / f"{PREFIX}_sizing_equity_stats_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{PREFIX}_decision_{MODEL_TAG}.json"
LINEAGE_PATH = OUT / f"{PREFIX}_lineage_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUT / f"{PREFIX}_equity_and_legacy_error_{MODEL_TAG}.png"
MANIFEST_PATH = OUT / f"{PREFIX}_manifest_{MODEL_TAG}.csv"
TEST_PATH = TOOLS_DIR / "test_stage011_2021_anchor_path_feedback_attribution.py"

ARM_FILES = {
    "a": s10.A_VERSION,
    "c": s10.C_VERSION,
}
SIGNAL_COLUMNS = ["date", "contract_vt_symbol", "direction", "signal"]


def _source_path(arm: str, kind: str) -> Path:
    version = ARM_FILES[arm]
    prefix = f"{s10.OUTPUT_PREFIX}_{SOURCE_START}_{version}"
    return s10.OUT / f"{prefix}_{kind}_{s10.MODEL_TAG}.csv.gz"


def _load(arm: str, kind: str) -> pd.DataFrame:
    path = _source_path(arm, kind)
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def _normalize_date(value: Any) -> pd.Timestamp:
    result = pd.Timestamp(value)
    if result.tzinfo is not None:
        result = result.tz_localize(None)
    return result.normalize()


def _signal_key(row: pd.Series) -> tuple[str, str, str, str]:
    return (
        _normalize_date(row["date"]).date().isoformat(),
        str(row["contract_vt_symbol"]),
        str(row["direction"]).lower(),
        str(row.get("signal") or ""),
    )


def _account_history_peak_trough(
    daily: pd.DataFrame,
    *,
    window_start: str | pd.Timestamp,
    window_end: str | pd.Timestamp,
) -> dict[str, Any]:
    data = daily.copy()
    data["date"] = pd.to_datetime(data["date"], errors="raise").map(_normalize_date)
    data["account_equity"] = pd.to_numeric(data["account_equity"], errors="raise")
    data = data.sort_values("date").reset_index(drop=True)
    data["account_history_hwm"] = data["account_equity"].cummax()
    data["account_history_drawdown"] = (
        data["account_equity"] / data["account_history_hwm"] - 1.0
    )
    start = _normalize_date(window_start)
    end = _normalize_date(window_end)
    window = data[data["date"].between(start, end)].copy()
    if window.empty:
        raise ValueError("drawdown window is empty")
    trough = window.loc[window["account_history_drawdown"].idxmin()]
    history_to_trough = data[data["date"].le(trough["date"])]
    peak = history_to_trough.loc[history_to_trough["account_equity"].idxmax()]
    window_start_row = window.iloc[0]
    return {
        "window_start": window.iloc[0]["date"].date().isoformat(),
        "window_end": window.iloc[-1]["date"].date().isoformat(),
        "window_start_equity": float(window_start_row["account_equity"]),
        "peak_date": peak["date"].date().isoformat(),
        "peak_equity": float(peak["account_equity"]),
        "trough_date": trough["date"].date().isoformat(),
        "trough_equity": float(trough["account_equity"]),
        "peak_to_trough_cash": float(trough["account_equity"] - peak["account_equity"]),
        "start_to_trough_cash": float(
            trough["account_equity"] - window_start_row["account_equity"]
        ),
        "max_drawdown_pct": float(trough["account_history_drawdown"] * 100.0),
    }


def _pretrade_equity_audit(
    candidates: pd.DataFrame, daily: pd.DataFrame
) -> pd.DataFrame:
    candidate_data = candidates.copy()
    candidate_data["date"] = pd.to_datetime(
        candidate_data["date"], errors="raise"
    ).map(_normalize_date)
    candidate_data["estimated_equity"] = pd.to_numeric(
        candidate_data["estimated_equity"], errors="raise"
    )
    estimates = (
        candidate_data.groupby("date", as_index=False)["estimated_equity"]
        .agg(["first", "min", "max"])
        .reset_index()
        .rename(
            columns={
                "first": "legacy_estimated_equity",
                "min": "legacy_estimated_equity_min",
                "max": "legacy_estimated_equity_max",
            }
        )
    )

    official = daily.copy()
    official["date"] = pd.to_datetime(official["date"], errors="raise").map(
        _normalize_date
    )
    official = official.sort_values("date").reset_index(drop=True)
    official["account_equity"] = pd.to_numeric(
        official["account_equity"], errors="raise"
    )
    official["holding_pnl"] = pd.to_numeric(
        official["holding_pnl"], errors="raise"
    )
    for column in ("trading_pnl", "commission", "slippage"):
        official[column] = pd.to_numeric(official[column], errors="raise")
    official["account_capital"] = pd.to_numeric(
        official["account_capital"], errors="raise"
    )
    official["previous_official_equity"] = official["account_equity"].shift(1)
    official["previous_official_equity"] = official[
        "previous_official_equity"
    ].fillna(official["account_capital"])
    official["official_daily_identity_equity"] = (
        official["previous_official_equity"]
        + official["holding_pnl"]
        + official["trading_pnl"]
        - official["commission"]
        - official["slippage"]
    )
    official["official_same_day_equity"] = official["account_equity"]
    official["official_daily_identity_error"] = (
        official["official_same_day_equity"]
        - official["official_daily_identity_equity"]
    )
    result = estimates.merge(
        official[
            [
                "date",
                "account_equity",
                "holding_pnl",
                "trading_pnl",
                "commission",
                "slippage",
                "previous_official_equity",
                "official_daily_identity_equity",
                "official_same_day_equity",
                "official_daily_identity_error",
            ]
        ],
        on="date",
        how="left",
        validate="one_to_one",
    )
    if result["official_same_day_equity"].isna().any():
        raise ValueError("candidate date is missing from official daily equity")
    result["legacy_minus_official_same_day"] = (
        result["legacy_estimated_equity"] - result["official_same_day_equity"]
    )
    result["within_day_estimated_equity_range"] = (
        result["legacy_estimated_equity_max"]
        - result["legacy_estimated_equity_min"]
    )
    return result


def _unexplained_equity_residual(
    *, c_minus_a_equity: float, explained_realized_pnl: float
) -> float:
    return float(c_minus_a_equity) - float(explained_realized_pnl)


def _opened_signal_keys(candidates: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    data = candidates.copy()
    data["date"] = pd.to_datetime(data["date"], errors="raise").map(_normalize_date)
    status = data["candidate_status"].fillna("").astype(str).str.lower()
    data = data[
        data["date"].between(WINDOW_START, cutoff) & status.eq("opened")
    ].copy()
    result = data[SIGNAL_COLUMNS].drop_duplicates().copy()
    if result.duplicated(SIGNAL_COLUMNS).any():
        raise ValueError("duplicate opened signal key")
    return result


def _map_signal_union(
    frames: dict[tuple[str, str], pd.DataFrame],
    ramp_events: pd.DataFrame,
    cutoff: pd.Timestamp,
) -> pd.DataFrame:
    union = pd.concat(
        [
            _opened_signal_keys(frames[(arm, "entry_candidates")], cutoff)
            for arm in ARM_FILES
        ],
        ignore_index=True,
    ).drop_duplicates(SIGNAL_COLUMNS)
    union = union.sort_values(SIGNAL_COLUMNS).reset_index(drop=True)

    direct_keys = {
        _signal_key(row)
        for _, row in ramp_events[
            pd.to_datetime(ramp_events["date"], errors="raise")
            .map(_normalize_date)
            .between(WINDOW_START, cutoff)
        ].iterrows()
    }
    rows: list[dict[str, Any]] = []
    for _, raw_event in union.iterrows():
        event = raw_event.copy()
        event["vt_symbol"] = event["contract_vt_symbol"]
        row: dict[str, Any] = {
            column: event[column] for column in SIGNAL_COLUMNS
        }
        row["direct_ramp_signal"] = _signal_key(event) in direct_keys
        for arm in ARM_FILES:
            row.update(
                s9._map_event_to_arm(
                    event,
                    candidates=frames[(arm, "entry_candidates")],
                    trades=frames[(arm, "trades")],
                    closed_lots=frames[(arm, "closed_lots")],
                    arm_prefix=arm,
                    trading_dates=frames[(arm, "daily")]["date"],
                )
            )
        rows.append(row)
    result = pd.DataFrame(rows)
    allowed_statuses = {"mapped", "missing_opened_candidate"}
    for arm in ARM_FILES:
        invalid = ~result[f"{arm}_mapping_status"].isin(allowed_statuses)
        if invalid.any():
            values = result.loc[invalid, f"{arm}_mapping_status"].value_counts().to_dict()
            raise ValueError(f"invalid {arm} mapping status: {values}")
        mapped = result[f"{arm}_mapping_status"].eq("mapped")
        result[f"{arm}_realized_pnl_zero_if_absent"] = pd.to_numeric(
            result.get(f"{arm}_realized_pnl"), errors="coerce"
        ).where(mapped, 0.0)
        result[f"{arm}_opened_volume_zero_if_absent"] = pd.to_numeric(
            result.get(f"{arm}_opened_volume_sum"), errors="coerce"
        ).where(mapped, 0.0)
    if (
        result["a_mapping_status"].eq("missing_opened_candidate")
        & result["c_mapping_status"].eq("missing_opened_candidate")
    ).any():
        raise ValueError("signal union cannot be absent from both arms")
    result["c_minus_a_realized_pnl"] = (
        result["c_realized_pnl_zero_if_absent"]
        - result["a_realized_pnl_zero_if_absent"]
    )
    result["c_minus_a_opened_volume"] = (
        result["c_opened_volume_zero_if_absent"]
        - result["a_opened_volume_zero_if_absent"]
    )
    cutoff_date = cutoff.date().isoformat()
    for arm in ARM_FILES:
        mapped = result[f"{arm}_mapping_status"].eq("mapped")
        exit_date = pd.to_datetime(result.get(f"{arm}_last_exit_date"), errors="coerce")
        result[f"{arm}_closed_by_cutoff"] = (~mapped) | exit_date.le(cutoff_date)
    result["both_closed_by_cutoff"] = (
        result["a_closed_by_cutoff"] & result["c_closed_by_cutoff"]
    )
    return result


def _signal_groups(signals: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for closed_scope, part in (
        ("all_final_outcomes", signals),
        ("both_closed_by_c_trough", signals[signals["both_closed_by_cutoff"]]),
    ):
        for direct, group in part.groupby("direct_ramp_signal", dropna=False):
            rows.append(
                {
                    "scope": closed_scope,
                    "path_bucket": "direct_ramp" if bool(direct) else "indirect_path_feedback",
                    "signal_count": int(len(group)),
                    "a_realized_pnl": float(group["a_realized_pnl_zero_if_absent"].sum()),
                    "c_realized_pnl": float(group["c_realized_pnl_zero_if_absent"].sum()),
                    "c_minus_a_realized_pnl": float(group["c_minus_a_realized_pnl"].sum()),
                    "a_opened_volume": float(group["a_opened_volume_zero_if_absent"].sum()),
                    "c_opened_volume": float(group["c_opened_volume_zero_if_absent"].sum()),
                }
            )
    return pd.DataFrame(rows)


def _daily_path(a_daily: pd.DataFrame, c_daily: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for arm, raw in (("a", a_daily), ("c", c_daily)):
        data = raw.copy()
        data["date"] = pd.to_datetime(data["date"], errors="raise").map(_normalize_date)
        data = data.sort_values("date")
        data[f"{arm}_hwm"] = pd.to_numeric(data["account_equity"], errors="raise").cummax()
        data[f"{arm}_drawdown_pct"] = (
            pd.to_numeric(data["account_equity"], errors="raise") / data[f"{arm}_hwm"] - 1.0
        ) * 100.0
        frames.append(
            data[
                ["date", "account_equity", "net_pnl", f"{arm}_hwm", f"{arm}_drawdown_pct"]
            ].rename(
                columns={
                    "account_equity": f"{arm}_account_equity",
                    "net_pnl": f"{arm}_net_pnl",
                }
            )
        )
    result = frames[0].merge(frames[1], on="date", how="inner", validate="one_to_one")
    result = result[result["date"].between(PATH_START, WINDOW_END)].copy()
    result["c_minus_a_equity"] = result["c_account_equity"] - result["a_account_equity"]
    result["c_minus_a_daily_pnl"] = result["c_net_pnl"] - result["a_net_pnl"]
    return result


def _sizing_stats(audit: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for arm, part in audit.groupby("arm"):
        values = pd.to_numeric(part["legacy_minus_official_same_day"], errors="raise")
        rows.append(
            {
                "arm": arm,
                "candidate_day_count": int(len(part)),
                "nonzero_error_day_count": int(values.abs().gt(1e-8).sum()),
                "min_legacy_error": float(values.min()),
                "mean_legacy_error": float(values.mean()),
                "median_legacy_error": float(values.median()),
                "max_legacy_error": float(values.max()),
                "max_within_day_estimated_equity_range": float(
                    pd.to_numeric(
                        part["within_day_estimated_equity_range"], errors="raise"
                    ).abs().max()
                ),
                "max_official_daily_identity_abs_error": float(
                    pd.to_numeric(
                        part["official_daily_identity_error"], errors="raise"
                    ).abs().max()
                ),
            }
        )
    return pd.DataFrame(rows)


def _plot(daily: pd.DataFrame, sizing: pd.DataFrame, peak_trough: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True)
    axes[0].plot(daily["date"], daily["a_account_equity"], label="A current C9", linewidth=1.4)
    axes[0].plot(daily["date"], daily["c_account_equity"], label="C Stage010 ramp", linewidth=1.4)
    for _, row in peak_trough.iterrows():
        color = "tab:blue" if row["arm"] == "a" else "tab:orange"
        axes[0].scatter(pd.Timestamp(row["peak_date"]), row["peak_equity"], color=color, marker="^")
        axes[0].scatter(pd.Timestamp(row["trough_date"]), row["trough_equity"], color=color, marker="v")
    axes[0].set_ylabel("account equity")
    axes[0].set_title("2021 anchor: 2022 account-history peak/trough")
    axes[0].grid(alpha=0.25)
    axes[0].legend()

    for arm, part in sizing.groupby("arm"):
        label = "A legacy minus official same-day" if arm == "a" else "C legacy minus official same-day"
        axes[1].plot(part["date"], part["legacy_minus_official_same_day"], label=label, linewidth=1.1)
    axes[1].axhline(0.0, color="black", linewidth=0.8)
    axes[1].set_ylabel("equity ledger error")
    axes[1].set_title("Candidate-day legacy estimated equity vs official same-day equity")
    axes[1].grid(alpha=0.25)
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _manifest() -> pd.DataFrame:
    rows = []
    for path in sorted(OUT.iterdir()):
        if not path.is_file() or path == MANIFEST_PATH:
            continue
        rows.append(
            {
                "file": path.name,
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return pd.DataFrame(rows)


def build() -> dict[str, Any]:
    source_manifest = s9._verify_manifest(s10.OUT, s10.MANIFEST_PATH)
    if not source_manifest["pass"]:
        raise RuntimeError(f"Stage010 source manifest failed: {source_manifest}")

    frames: dict[tuple[str, str], pd.DataFrame] = {}
    for arm in ARM_FILES:
        for kind in ("daily", "entry_candidates", "trades", "closed_lots"):
            frames[(arm, kind)] = _load(arm, kind)
    ramp_events = _load("c", "stage010_ramp_events")

    peak_rows = []
    for arm in ARM_FILES:
        row = _account_history_peak_trough(
            frames[(arm, "daily")],
            window_start=WINDOW_START,
            window_end=WINDOW_END,
        )
        row["arm"] = arm
        peak_rows.append(row)
    peak_trough = pd.DataFrame(peak_rows)
    c_trough = pd.Timestamp(peak_trough.loc[peak_trough["arm"].eq("c"), "trough_date"].iloc[0])

    daily = _daily_path(frames[("a", "daily")], frames[("c", "daily")])
    signals = _map_signal_union(frames, ramp_events, c_trough)
    signal_groups = _signal_groups(signals)

    sizing_parts = []
    for arm in ARM_FILES:
        part = _pretrade_equity_audit(
            frames[(arm, "entry_candidates")], frames[(arm, "daily")]
        )
        part = part[part["date"].between(WINDOW_START, c_trough)].copy()
        part["arm"] = arm
        sizing_parts.append(part)
    sizing = pd.concat(sizing_parts, ignore_index=True)
    sizing_stats = _sizing_stats(sizing)

    peak_trough.to_csv(PEAK_TROUGH_PATH, index=False, encoding="utf-8-sig")
    daily.to_csv(DAILY_PATH, index=False, compression="gzip")
    signals.to_csv(SIGNAL_PATH, index=False, compression="gzip")
    signal_groups.to_csv(SIGNAL_GROUP_PATH, index=False, encoding="utf-8-sig")
    sizing.to_csv(SIZING_PATH, index=False, compression="gzip")
    sizing_stats.to_csv(SIZING_STATS_PATH, index=False, encoding="utf-8-sig")
    _plot(daily, sizing, peak_trough)

    closed = signal_groups[signal_groups["scope"].eq("both_closed_by_c_trough")]
    direct = closed[closed["path_bucket"].eq("direct_ramp")].iloc[0]
    indirect = closed[closed["path_bucket"].eq("indirect_path_feedback")].iloc[0]
    a_peak = peak_trough[peak_trough["arm"].eq("a")].iloc[0]
    c_peak = peak_trough[peak_trough["arm"].eq("c")].iloc[0]
    stats_by_arm = sizing_stats.set_index("arm")
    mapping_status = signals.groupby(
        ["a_mapping_status", "c_mapping_status"], dropna=False
    ).size().to_dict()
    c_minus_a_equity_at_trough = float(
        daily.loc[daily["date"].eq(c_trough), "c_minus_a_equity"].iloc[0]
    )
    explained_closed_lot_pnl = float(
        direct["c_minus_a_realized_pnl"] + indirect["c_minus_a_realized_pnl"]
    )
    unexplained_residual = _unexplained_equity_residual(
        c_minus_a_equity=c_minus_a_equity_at_trough,
        explained_realized_pnl=explained_closed_lot_pnl,
    )
    decision = {
        "stage": STAGE,
        "stage_id": STAGE_ID,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "source_start": SOURCE_START,
        "source_stage010_manifest_pass": True,
        "c_trough_date": c_peak["trough_date"],
        "a_account_history_2022_drawdown_pct": float(a_peak["max_drawdown_pct"]),
        "c_account_history_2022_drawdown_pct": float(c_peak["max_drawdown_pct"]),
        "c_minus_a_drawdown_pp": float(
            c_peak["max_drawdown_pct"] - a_peak["max_drawdown_pct"]
        ),
        "a_peak_date": a_peak["peak_date"],
        "c_peak_date": c_peak["peak_date"],
        "a_trough_date": a_peak["trough_date"],
        "c_trough_date": c_peak["trough_date"],
        "a_trough_equity": float(a_peak["trough_equity"]),
        "c_trough_equity": float(c_peak["trough_equity"]),
        "c_minus_a_equity_at_c_trough": c_minus_a_equity_at_trough,
        "direct_ramp_closed_by_trough_c_minus_a_realized_pnl": float(
            direct["c_minus_a_realized_pnl"]
        ),
        "indirect_path_closed_by_trough_c_minus_a_realized_pnl": float(
            indirect["c_minus_a_realized_pnl"]
        ),
        "explained_closed_lot_realized_pnl": explained_closed_lot_pnl,
        "unexplained_equity_residual": unexplained_residual,
        "signal_mapping_status_counts": {
            f"{a}|{c}": int(value) for (a, c), value in mapping_status.items()
        },
        "a_candidate_day_legacy_error_median": float(
            stats_by_arm.loc["a", "median_legacy_error"]
        ),
        "c_candidate_day_legacy_error_median": float(
            stats_by_arm.loc["c", "median_legacy_error"]
        ),
        "a_candidate_day_legacy_error_max": float(
            stats_by_arm.loc["a", "max_legacy_error"]
        ),
        "c_candidate_day_legacy_error_max": float(
            stats_by_arm.loc["c", "max_legacy_error"]
        ),
        "max_official_daily_identity_abs_error": float(
            stats_by_arm["max_official_daily_identity_abs_error"].max()
        ),
        "stage012_global_authoritative_sizing_test_allowed": bool(
            float(direct["c_minus_a_realized_pnl"]) > 0.0
            and float(indirect["c_minus_a_realized_pnl"]) < 0.0
            and int(stats_by_arm["nonzero_error_day_count"].min()) > 0
            and float(stats_by_arm["max_official_daily_identity_abs_error"].max())
            <= 1e-8
        ),
        "rule_selection_from_signal_outcomes_allowed": False,
        "realized_pnl_is_executable_counterfactual": False,
        "closed_lot_realized_pnl_includes_costs": False,
        "decision": "stage011_global_legacy_equity_sizing_bug_stage012_correctness_test_allowed",
    }
    DECISION_PATH.write_text(
        json.dumps(s9._json_safe(decision), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lineage = {
        "stage": STAGE,
        "source_manifest": str(s10.MANIFEST_PATH),
        "source_manifest_audit": source_manifest,
        "source_files": {
            f"{arm}_{kind}": str(_source_path(arm, kind))
            for arm in ARM_FILES
            for kind in ("daily", "entry_candidates", "trades", "closed_lots")
        },
        "ramp_events": str(_source_path("c", "stage010_ramp_events")),
        "stage011_tool": {
            "path": str(Path(__file__).resolve()),
            "sha256": s9._sha256(Path(__file__).resolve()),
        },
        "stage011_test": {
            "path": str(TEST_PATH),
            "sha256": s9._sha256(TEST_PATH),
        },
        "history_database_snapshot_complete": False,
    }
    LINEAGE_PATH.write_text(
        json.dumps(s9._json_safe(lineage), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report = f"""# Stage011 2021锚点路径反馈归因

- 来源：Stage010 冻结产物，起点 `{SOURCE_START}`。
- Stage010 manifest：`{source_manifest['manifest_rows']}/{source_manifest['manifest_rows']}` 通过。
- A 2022 account-history 峰谷：`{a_peak['peak_date']}` `{a_peak['peak_equity']:,.2f}` -> `{a_peak['trough_date']}` `{a_peak['trough_equity']:,.2f}`，回撤 `{a_peak['max_drawdown_pct']:.4f}%`。
- C 2022 account-history 峰谷：`{c_peak['peak_date']}` `{c_peak['peak_equity']:,.2f}` -> `{c_peak['trough_date']}` `{c_peak['trough_equity']:,.2f}`，回撤 `{c_peak['max_drawdown_pct']:.4f}%`。
- C 谷底相对 A 同日权益差：`{decision['c_minus_a_equity_at_c_trough']:,.2f}`。

## 已结束信号归因（截至C谷底）

- 直接 ramp 信号 C-A realized PnL：`{direct['c_minus_a_realized_pnl']:,.2f}`；ramp 直接压缩在谷底前总体有利。
- 非 ramp 路径反馈 C-A realized PnL：`{indirect['c_minus_a_realized_pnl']:,.2f}`；间接路径分叉覆盖了直接防守收益。
- 已结束 closed-lot 毛损益合计只能解释 `{decision['explained_closed_lot_realized_pnl']:,.2f}`；相对谷底权益差仍有 `{decision['unexplained_equity_residual']:,.2f}` 残差。
- 映射状态：`{decision['signal_mapping_status_counts']}`。
- realized PnL 是未扣佣金/滑点的 closed-lot 毛损益，不含谷底尚未结束仓位 MTM、成本和其他路径状态，也不重建可执行反事实，只作路径解释。

## 基础 sizing 账本

- A 候选日旧 estimated equity 偏差中位/最大：`{decision['a_candidate_day_legacy_error_median']:,.2f}` / `{decision['a_candidate_day_legacy_error_max']:,.2f}`。
- C 候选日旧 estimated equity 偏差中位/最大：`{decision['c_candidate_day_legacy_error_median']:,.2f}` / `{decision['c_candidate_day_legacy_error_max']:,.2f}`。
- 引擎在 `on_bars` 前先撮合旧订单；候选生成时正式权益使用同日 `account_equity`，并校验恒等式 `昨权益 + holding_pnl + trading_pnl - commission - slippage`，最大误差 `{decision['max_official_daily_identity_abs_error']:.3g}`。
- 候选日内 estimated equity 必须唯一；Stage012 只能对齐同日 Stage006 authoritative equity / 正式 account equity。

## 决策

- `stage011_global_legacy_equity_sizing_bug_stage012_correctness_test_allowed`。
- 不允许从赢家/输家、品种、方向、日期或信号结果挑规则。
- 只允许 Stage012 全局权威权益 sizing 正确性 A/C；不救 Stage010，不改 heat 或风险参数。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")
    _manifest().to_csv(MANIFEST_PATH, index=False, encoding="utf-8-sig")
    return decision


if __name__ == "__main__":
    result = build()
    print(json.dumps(s9._json_safe(result), ensure_ascii=False, indent=2))
