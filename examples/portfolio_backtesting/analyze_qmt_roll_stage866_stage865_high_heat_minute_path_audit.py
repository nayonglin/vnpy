from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import analyze_qmt_roll_stage864_stage863_broker10_peak_forensics as s864
import analyze_qmt_roll_stage865_stage864_sizing_brake_proxy_audit as s865
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage866"
MODEL_TAG = "stage866_stage865_high_heat_minute_path_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage866_stage865_high_heat_minute_path_audit"

ENTRY_PATH_FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_path_features_{MODEL_TAG}.csv"
PATH_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_summary_{MODEL_TAG}.csv"
PROXY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_summary_{MODEL_TAG}.csv"
YEARLY_PATH_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_yearly_path_summary_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
SUMMARY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

HALF_R = 0.5
FULL_R = 1.0
MAX_ATLAS_ROWS = 12
PER_PAGE = 3


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _load_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _direction_sign(direction: Any) -> int:
    return 1 if str(direction) == "long" else -1


def _prepare_entries() -> pd.DataFrame:
    data = _load_required_csv(s865.ENTRY_AUDIT_PATH).copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data["matched_entry_date"] = pd.to_datetime(data["matched_entry_date"], errors="coerce").dt.normalize()
    numeric_columns = [
        "entry_key",
        "entry_price",
        "stop_price",
        "stop_distance",
        "actual_risk_amount",
        "matched_pnl",
        "matched_risk",
        "matched_volume",
        "matched_lots",
        "matched_big_winner",
        "matched_winner",
        "projected_broker10_pct",
        "before_broker10_pct",
        "add_broker10_pct",
        "selected_volume",
        "flag_SBB0_projected90_heat_buffer",
        "flag_SBB1_nearcap90_largeadd20",
        "flag_WATCH_single_add20",
    ]
    for column in numeric_columns:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data[data["matched_lots"].fillna(0).gt(0)].copy()
    data["entry_year"] = data["matched_entry_date"].dt.year
    data["is_sbb0_high_heat"] = data["flag_SBB0_projected90_heat_buffer"].fillna(0).gt(0).astype(int)
    data["is_sbb1_nearcap_largeadd"] = data["flag_SBB1_nearcap90_largeadd20"].fillna(0).gt(0).astype(int)
    data["is_watch_single_add20"] = data["flag_WATCH_single_add20"].fillna(0).gt(0).astype(int)
    return data.reset_index(drop=True)


def _load_minute_groups(entries: pd.DataFrame) -> dict[str, pd.DataFrame]:
    vt_symbols = set(entries["contract_vt_symbol"].dropna().astype(str).unique())
    minute_bars = s864._load_full_minute_bars(vt_symbols)
    return s825._minute_groups(minute_bars)


def _day_bars(minute_by_symbol: dict[str, pd.DataFrame], vt_symbol: str, entry_date: Any) -> pd.DataFrame:
    bars = minute_by_symbol.get(str(vt_symbol), pd.DataFrame())
    if bars.empty:
        return pd.DataFrame()
    date = pd.Timestamp(entry_date).normalize()
    return bars[bars["bar_date"].eq(date)].copy().sort_values("bar_datetime").reset_index(drop=True)


def _price_levels(row: pd.Series) -> dict[str, float]:
    entry = _safe_float(row.get("entry_price"))
    distance = abs(_safe_float(row.get("stop_distance")))
    if not np.isfinite(distance) or distance <= 0:
        stop = _safe_float(row.get("stop_price"))
        distance = abs(entry - stop) if np.isfinite(entry) and np.isfinite(stop) else np.nan
    sign = _direction_sign(row.get("direction"))
    return {
        "entry": entry,
        "stop_05r": entry - sign * HALF_R * distance,
        "progress_05r": entry + sign * HALF_R * distance,
        "progress_10r": entry + sign * FULL_R * distance,
        "risk_distance": distance,
    }


def _touch_mask(bars: pd.DataFrame, direction: str, level: float, kind: str) -> pd.Series:
    if bars.empty or not np.isfinite(level):
        return pd.Series(dtype=bool)
    if kind == "adverse":
        if str(direction) == "long":
            return bars["low"].le(level)
        return bars["high"].ge(level)
    if kind == "favorable":
        if str(direction) == "long":
            return bars["high"].ge(level)
        return bars["low"].le(level)
    if kind == "reclaim_entry":
        if str(direction) == "long":
            return bars["high"].ge(level)
        return bars["low"].le(level)
    raise KeyError(kind)


def _first_idx(mask: pd.Series) -> int | None:
    if mask.empty or not bool(mask.any()):
        return None
    return int(mask[mask].index[0])


def _path_for_entry(row: pd.Series, minute_by_symbol: dict[str, pd.DataFrame]) -> dict[str, Any]:
    vt_symbol = str(row["contract_vt_symbol"])
    entry_date = row["matched_entry_date"]
    bars = _day_bars(minute_by_symbol, vt_symbol, entry_date)
    levels = _price_levels(row)
    result: dict[str, Any] = {
        "entry_key": row["entry_key"],
        "path_vt_symbol": vt_symbol,
        "path_entry_date": pd.Timestamp(entry_date).date().isoformat() if pd.notna(entry_date) else "",
        "entry_day_minute_bars": int(len(bars)),
        "entry_level": levels["entry"],
        "stop05_level": levels["stop_05r"],
        "progress05_level": levels["progress_05r"],
        "progress10_level": levels["progress_10r"],
        "risk_distance": levels["risk_distance"],
    }
    if bars.empty or not np.isfinite(levels["entry"]) or not np.isfinite(levels["risk_distance"]) or levels["risk_distance"] <= 0:
        result.update(
            {
                "first_05_event": "missing",
                "minute_path_state": "missing",
                "first_stop_time": "",
                "first_progress05_time": "",
                "first_progress10_time": "",
                "reclaim_entry_time_after_stop": "",
                "retry_failed_time_after_reclaim": "",
                "entry_day_mfe_r": np.nan,
                "entry_day_mae_r": np.nan,
                "entry_day_close_r": np.nan,
            }
        )
        return result

    direction = str(row["direction"])
    stop_mask = _touch_mask(bars, direction, levels["stop_05r"], "adverse")
    progress05_mask = _touch_mask(bars, direction, levels["progress_05r"], "favorable")
    progress10_mask = _touch_mask(bars, direction, levels["progress_10r"], "favorable")
    first_stop_idx = _first_idx(stop_mask)
    first_progress05_idx = _first_idx(progress05_mask)
    first_progress10_idx = _first_idx(progress10_mask)

    if first_stop_idx is None and first_progress05_idx is None:
        first_event = "none"
    elif first_stop_idx is None:
        first_event = "progress_first"
    elif first_progress05_idx is None:
        first_event = "stop_first"
    elif first_stop_idx < first_progress05_idx:
        first_event = "stop_first"
    elif first_progress05_idx < first_stop_idx:
        first_event = "progress_first"
    else:
        first_event = "same_bar_ambiguous"

    reclaim_idx: int | None = None
    retry_failed_idx: int | None = None
    if first_stop_idx is not None and first_event in {"stop_first", "same_bar_ambiguous"}:
        after_stop = bars.loc[first_stop_idx + 1 :].copy()
        if not after_stop.empty:
            reclaim_mask = _touch_mask(after_stop, direction, levels["entry"], "reclaim_entry")
            reclaim_idx = _first_idx(reclaim_mask)
            if reclaim_idx is not None:
                after_reclaim = bars.loc[reclaim_idx + 1 :].copy()
                if not after_reclaim.empty:
                    retry_mask = _touch_mask(after_reclaim, direction, levels["stop_05r"], "adverse")
                    retry_failed_idx = _first_idx(retry_mask)

    if first_event == "progress_first":
        path_state = "progress_first"
    elif first_event == "none":
        path_state = "no_05r_event"
    elif first_event == "same_bar_ambiguous":
        path_state = "same_bar_ambiguous"
    elif reclaim_idx is None:
        path_state = "stop_no_reclaim"
    elif retry_failed_idx is None:
        path_state = "stop_reclaim_no_second_stop"
    else:
        path_state = "stop_reclaim_retry_failed"

    sign = _direction_sign(direction)
    if direction == "long":
        mfe_r = (bars["high"].max() - levels["entry"]) / levels["risk_distance"]
        mae_r = (levels["entry"] - bars["low"].min()) / levels["risk_distance"]
        close_r = (bars["close"].iloc[-1] - levels["entry"]) / levels["risk_distance"]
    else:
        mfe_r = (levels["entry"] - bars["low"].min()) / levels["risk_distance"]
        mae_r = (bars["high"].max() - levels["entry"]) / levels["risk_distance"]
        close_r = (levels["entry"] - bars["close"].iloc[-1]) / levels["risk_distance"]
    mfe_r = max(0.0, float(mfe_r)) if np.isfinite(mfe_r) else np.nan
    mae_r = max(0.0, float(mae_r)) if np.isfinite(mae_r) else np.nan

    result.update(
        {
            "first_05_event": first_event,
            "minute_path_state": path_state,
            "first_stop_time": pd.Timestamp(bars.loc[first_stop_idx, "bar_datetime"]).isoformat()
            if first_stop_idx is not None
            else "",
            "first_progress05_time": pd.Timestamp(bars.loc[first_progress05_idx, "bar_datetime"]).isoformat()
            if first_progress05_idx is not None
            else "",
            "first_progress10_time": pd.Timestamp(bars.loc[first_progress10_idx, "bar_datetime"]).isoformat()
            if first_progress10_idx is not None
            else "",
            "reclaim_entry_time_after_stop": pd.Timestamp(bars.loc[reclaim_idx, "bar_datetime"]).isoformat()
            if reclaim_idx is not None
            else "",
            "retry_failed_time_after_reclaim": pd.Timestamp(bars.loc[retry_failed_idx, "bar_datetime"]).isoformat()
            if retry_failed_idx is not None
            else "",
            "entry_day_mfe_r": mfe_r,
            "entry_day_mae_r": mae_r,
            "entry_day_close_r": float(close_r) if np.isfinite(close_r) else np.nan,
        }
    )
    return result


def _build_path_features(entries: pd.DataFrame, minute_by_symbol: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = [_path_for_entry(row, minute_by_symbol) for _, row in entries.iterrows()]
    path = pd.DataFrame(rows)
    data = entries.merge(path, on="entry_key", how="left")
    data["stop05_cash_proxy"] = -HALF_R * pd.to_numeric(data["actual_risk_amount"], errors="coerce").fillna(0.0)
    data["entry_path_proxy_no_retry_delta"] = data["stop05_cash_proxy"] - pd.to_numeric(
        data["matched_pnl"], errors="coerce"
    ).fillna(0.0)
    return data


def _cohort_summary(features: pd.DataFrame) -> pd.DataFrame:
    cohorts = [
        ("ALL", pd.Series(True, index=features.index)),
        ("SBB0_high_heat", features["is_sbb0_high_heat"].eq(1)),
        ("SBB1_nearcap_largeadd", features["is_sbb1_nearcap_largeadd"].eq(1)),
        ("WATCH_single_add20", features["is_watch_single_add20"].eq(1)),
    ]
    rows: list[dict[str, Any]] = []
    for cohort, mask in cohorts:
        subset = features[mask].copy()
        for state, group in subset.groupby("minute_path_state", dropna=False):
            pnl = pd.to_numeric(group["matched_pnl"], errors="coerce").fillna(0.0)
            rows.append(
                {
                    "cohort": cohort,
                    "minute_path_state": state,
                    "entries": int(len(group)),
                    "entry_rate_pct_in_cohort": len(group) / len(subset) * 100.0 if len(subset) else 0.0,
                    "matched_pnl": float(pnl.sum()),
                    "win_rate_pct": float(pnl.gt(0).mean() * 100.0) if len(group) else 0.0,
                    "big_winner_entries": int(pd.to_numeric(group["matched_big_winner"], errors="coerce").fillna(0).gt(0).sum()),
                    "median_projected_broker10_pct": float(group["projected_broker10_pct"].median()) if len(group) else np.nan,
                    "median_mfe_r": float(group["entry_day_mfe_r"].median()) if len(group) else np.nan,
                    "median_mae_r": float(group["entry_day_mae_r"].median()) if len(group) else np.nan,
                }
            )
    return pd.DataFrame(rows).sort_values(["cohort", "matched_pnl"], ascending=[True, True])


def _proxy_summary(features: pd.DataFrame) -> pd.DataFrame:
    pnl = pd.to_numeric(features["matched_pnl"], errors="coerce").fillna(0.0)
    specs = [
        (
            "HH_NR0_all_stop_first_no_retry",
            features["is_sbb0_high_heat"].eq(1) & features["first_05_event"].isin(["stop_first", "same_bar_ambiguous"]),
            "If SBB0 high-heat entry touches -0.5R before +0.5R, do not retry; proxy exits at -0.5R.",
        ),
        (
            "HH_NR1_retry_failed_only_no_retry",
            features["is_sbb0_high_heat"].eq(1) & features["minute_path_state"].eq("stop_reclaim_retry_failed"),
            "If SBB0 high-heat entry reclaims entry then fails again, no retry proxy exits at first -0.5R.",
        ),
        (
            "HH_DIAG_block_non_progress_first",
            features["is_sbb0_high_heat"].eq(1) & ~features["minute_path_state"].eq("progress_first"),
            "Diagnostic only: remove high-heat entries that do not reach +0.5R before -0.5R.",
        ),
    ]
    rows: list[dict[str, Any]] = []
    for proxy_id, mask, rule_text in specs:
        adjusted = pnl.copy()
        if proxy_id == "HH_DIAG_block_non_progress_first":
            adjusted.loc[mask] = 0.0
        else:
            adjusted.loc[mask] = pd.to_numeric(features.loc[mask, "stop05_cash_proxy"], errors="coerce").fillna(0.0)
        delta = adjusted - pnl
        affected = features[mask].copy()
        loser = affected[pd.to_numeric(affected["matched_pnl"], errors="coerce").fillna(0).lt(0)]
        winner = affected[pd.to_numeric(affected["matched_pnl"], errors="coerce").fillna(0).gt(0)]
        big = affected[pd.to_numeric(affected["matched_big_winner"], errors="coerce").fillna(0).gt(0)]
        rows.append(
            {
                "proxy_id": proxy_id,
                "rule_text": rule_text,
                "affected_entries": int(mask.sum()),
                "affected_pnl": float(pnl.loc[mask].sum()),
                "proxy_pnl_delta": float(delta.loc[mask].sum()),
                "loser_saved_proxy": float((adjusted.loc[loser.index] - pnl.loc[loser.index]).sum()) if not loser.empty else 0.0,
                "winner_cut_proxy": float((adjusted.loc[winner.index] - pnl.loc[winner.index]).sum()) if not winner.empty else 0.0,
                "big_winner_cut_proxy": float((adjusted.loc[big.index] - pnl.loc[big.index]).sum()) if not big.empty else 0.0,
                "affected_big_winner_entries": int(len(big)),
                "judgment": "diagnostic_only_no_engine",
            }
        )
    return pd.DataFrame(rows)


def _yearly_summary(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for year, group in features.groupby("entry_year", dropna=False):
        high = group[group["is_sbb0_high_heat"].eq(1)]
        row = {
            "entry_year": int(year) if pd.notna(year) else -1,
            "entries": int(len(group)),
            "matched_pnl": float(group["matched_pnl"].sum()),
            "sbb0_high_heat_entries": int(len(high)),
            "sbb0_high_heat_pnl": float(high["matched_pnl"].sum()),
            "sbb0_progress_first_entries": int(high["minute_path_state"].eq("progress_first").sum()),
            "sbb0_stop_reclaim_retry_failed_entries": int(high["minute_path_state"].eq("stop_reclaim_retry_failed").sum()),
        }
        rows.append(row)
    return pd.DataFrame(rows).sort_values("entry_year")


def _plot_summary(features: pd.DataFrame, path_summary: pd.DataFrame, proxy_summary: pd.DataFrame) -> None:
    high = features[features["is_sbb0_high_heat"].eq(1)].copy()
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    ax = axes[0, 0]
    colors = np.where(high["matched_big_winner"].fillna(0).gt(0), "#16a34a", "#64748b")
    ax.scatter(high["entry_day_mfe_r"], high["entry_day_mae_r"], s=65, c=colors, alpha=0.75)
    ax.axvline(0.5, color="#16a34a", linestyle="--", linewidth=1.0)
    ax.axhline(0.5, color="#dc2626", linestyle="--", linewidth=1.0)
    ax.set_title("SBB0 high-heat entry-day MFE/MAE")
    ax.set_xlabel("entry-day MFE (R)")
    ax.set_ylabel("entry-day MAE (R)")
    ax.grid(True, alpha=0.2)

    ax = axes[0, 1]
    high_state = (
        high.groupby("minute_path_state", dropna=False)["matched_pnl"].sum().sort_values()
        if not high.empty
        else pd.Series(dtype=float)
    )
    ax.barh(high_state.index.astype(str), high_state.values, color=np.where(high_state.values >= 0, "#16a34a", "#dc2626"))
    ax.axvline(0, color="#171717", linewidth=0.8)
    ax.set_title("SBB0 high-heat PnL by minute path")
    ax.grid(True, axis="x", alpha=0.2)

    ax = axes[1, 0]
    ax.scatter(
        features["projected_broker10_pct"],
        features["entry_day_mfe_r"] - features["entry_day_mae_r"],
        s=np.clip(features["add_broker10_pct"].fillna(0) * 2.0, 12, 120),
        c=np.where(features["is_sbb0_high_heat"].eq(1), "#f97316", "#94a3b8"),
        alpha=0.65,
    )
    ax.axvline(90, color="#dc2626", linestyle="--", linewidth=1.0)
    ax.axhline(0, color="#171717", linewidth=0.8)
    ax.set_title("Projected broker10 vs entry-day path balance")
    ax.set_xlabel("projected broker10 (%)")
    ax.set_ylabel("MFE - MAE (R)")
    ax.grid(True, alpha=0.2)

    ax = axes[1, 1]
    ax.barh(
        proxy_summary["proxy_id"],
        proxy_summary["proxy_pnl_delta"],
        color=np.where(proxy_summary["proxy_pnl_delta"] >= 0, "#16a34a", "#dc2626"),
    )
    ax.axvline(0, color="#171717", linewidth=0.8)
    ax.set_title("High-heat minute-path proxy deltas")
    ax.grid(True, axis="x", alpha=0.2)
    fig.tight_layout()
    fig.savefig(SUMMARY_CHART_PATH, dpi=160)
    plt.close(fig)


def _plot_atlas(features: pd.DataFrame, minute_by_symbol: dict[str, pd.DataFrame]) -> tuple[list[Path], pd.DataFrame]:
    high = features[features["is_sbb0_high_heat"].eq(1)].copy()
    if high.empty:
        return [], pd.DataFrame()
    high["abs_pnl"] = pd.to_numeric(high["matched_pnl"], errors="coerce").abs()
    selected = pd.concat(
        [
            high.sort_values("projected_broker10_pct", ascending=False).head(4),
            high.sort_values("matched_pnl", ascending=True).head(4),
            high.sort_values("matched_pnl", ascending=False).head(4),
        ],
        ignore_index=True,
        sort=False,
    ).drop_duplicates("entry_key").head(MAX_ATLAS_ROWS)
    paths: list[Path] = []
    manifest_rows: list[dict[str, Any]] = []
    for start in range(0, len(selected), PER_PAGE):
        page_rows = selected.iloc[start : start + PER_PAGE].reset_index(drop=True)
        page = len(paths) + 1
        fig, axes = plt.subplots(len(page_rows), 1, figsize=(13, 3.8 * len(page_rows)), squeeze=False)
        for idx, row in page_rows.iterrows():
            levels = {
                "entry": _safe_float(row.get("entry_level")),
                "stop": _safe_float(row.get("stop05_level")),
                "progress": _safe_float(row.get("progress05_level")),
            }
            bars = s864._plot_day(
                axes[idx, 0],
                minute_by_symbol,
                str(row["contract_vt_symbol"]),
                row["matched_entry_date"],
                (
                    f"{row['contract_vt_symbol']} {row['direction']} {pd.Timestamp(row['matched_entry_date']):%Y-%m-%d} "
                    f"{row['minute_path_state']} proj={_safe_float(row.get('projected_broker10_pct')):.1f}% "
                    f"PnL={_safe_float(row.get('matched_pnl')):.0f}"
                ),
                levels=levels,
            )
            manifest_rows.append(
                {
                    "page": page,
                    "entry_key": row["entry_key"],
                    "vt_symbol": row["contract_vt_symbol"],
                    "direction": row["direction"],
                    "entry_date": pd.Timestamp(row["matched_entry_date"]).date().isoformat(),
                    "minute_path_state": row["minute_path_state"],
                    "projected_broker10_pct": _safe_float(row.get("projected_broker10_pct")),
                    "matched_pnl": _safe_float(row.get("matched_pnl")),
                    "matched_big_winner": int(_safe_float(row.get("matched_big_winner"), 0) > 0),
                    "bars": bars,
                }
            )
        fig.tight_layout()
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=160)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest_rows)


def _write_report(
    features: pd.DataFrame,
    path_summary: pd.DataFrame,
    proxy_summary: pd.DataFrame,
    yearly: pd.DataFrame,
    atlas_paths: list[Path],
) -> None:
    high = features[features["is_sbb0_high_heat"].eq(1)].copy()
    top_high = high.sort_values("projected_broker10_pct", ascending=False).head(20)
    lines = [
        "# Stage866 高热入场分钟路径只读审计",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：只读分钟路径审计与视觉复盘；不写新规则、不改正式版、不改候选配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- Backtrader stop order documentation：https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/",
        "- Backtrader stop/bracket examples：https://www.backtrader.com/blog/posts/2018-02-01-stop-trading/stop-trading/",
        "- 我的判断：止损/ bracket 类规则的工程关键是逐 bar 触发顺序和执行语义。本阶段只验证分钟K路径能否解释 Stage865 的高热误伤，不做参数优化。",
        "",
        "## Cohort Path Summary",
        "",
        _md_table(path_summary, max_rows=80),
        "",
        "## Proxy Summary",
        "",
        _md_table(proxy_summary, max_rows=None),
        "",
        "## Top High-Heat Entries",
        "",
        _md_table(
            top_high[
                [
                    "entry_key",
                    "matched_entry_date",
                    "contract_vt_symbol",
                    "direction",
                    "projected_broker10_pct",
                    "minute_path_state",
                    "first_05_event",
                    "entry_day_mfe_r",
                    "entry_day_mae_r",
                    "matched_pnl",
                    "matched_big_winner",
                    "matched_exit_reasons",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## Yearly Summary",
        "",
        _md_table(yearly, max_rows=None),
        "",
        "## Visuals",
        "",
        f"- summary chart：`{SUMMARY_CHART_PATH}`",
    ]
    for path in atlas_paths:
        lines.append(f"- atlas page：`{path}`")
    lines.extend(
        [
            "",
            "## Judgment",
            "",
            "- Stage866 不产生新策略。高热入场中 `progress_first` 仍贡献正右尾，`stop_reclaim_retry_failed` 才更像错误路径；但样本太少，且部分高热止损路径仍不干净，不能直接进入真实引擎。",
            "- 下一步如果继续，应只把 `高热 + 先0.5R止损 + 重回后再次失败` 作为候选纪律设计草案，而不是扫时间窗、R倍数或账户热度阈值；进入引擎前还要明确成交语义和对右尾的影响。",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    entries = _prepare_entries()
    minute_by_symbol = _load_minute_groups(entries)
    features = _build_path_features(entries, minute_by_symbol)
    path_summary = _cohort_summary(features)
    proxy_summary = _proxy_summary(features)
    yearly = _yearly_summary(features)
    _plot_summary(features, path_summary, proxy_summary)
    atlas_paths, atlas_manifest = _plot_atlas(features, minute_by_symbol)

    features.to_csv(ENTRY_PATH_FEATURES_PATH, index=False, encoding="utf-8-sig")
    path_summary.to_csv(PATH_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    proxy_summary.to_csv(PROXY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    yearly.to_csv(YEARLY_PATH_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    _write_report(features, path_summary, proxy_summary, yearly, atlas_paths)

    high = features[features["is_sbb0_high_heat"].eq(1)].copy()
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "formal_ab_triggered": False,
        "inputs": {
            "stage865_entry_audit": str(s865.ENTRY_AUDIT_PATH),
            "stage861_full_minute_bars": str(s864.s861.FULL_MINUTE_BARS_PATH),
            "entries": int(len(features)),
            "sbb0_high_heat_entries": int(len(high)),
            "missing_minute_entries": int(features["minute_path_state"].eq("missing").sum()),
        },
        "high_heat_state_counts": high["minute_path_state"].value_counts(dropna=False).to_dict(),
        "path_summary": path_summary.to_dict("records"),
        "proxy_summary": proxy_summary.to_dict("records"),
        "decision": "stage866_high_heat_minute_path_no_engine_yet",
        "overfit_reflection": (
            "不是正式策略过拟合。本阶段固定使用 C9 既有 0.5R stop/retry 语义和 Stage865 高热标记，只做路径归因；"
            "没有扫分钟窗、R倍数、品种、方向或年份。"
        ),
        "continue_value": (
            "有继续价值，但下一步只能把 high-heat + stop-first + reclaim + retry-failed 写成一次冻结规则草案；"
            "不能继续扩大为账户热度或品种方向过滤。"
        ),
        "outputs": {
            "entry_path_features": str(ENTRY_PATH_FEATURES_PATH),
            "path_summary": str(PATH_SUMMARY_PATH),
            "proxy_summary": str(PROXY_SUMMARY_PATH),
            "yearly_path_summary": str(YEARLY_PATH_PATH),
            "summary_chart": str(SUMMARY_CHART_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "atlas_pages": [str(path) for path in atlas_paths],
            "report": str(REPORT_PATH),
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("proxy_summary")
    print(proxy_summary.to_string(index=False))


if __name__ == "__main__":
    main()
