from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage878"
MODEL_TAG = "stage878_stage861_early_oi_participation_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage878_stage861_early_oi_participation_audit"

STAGE861_PREFIX = "qmt_roll_stage861_stage860_full_visual_atlas"
STAGE861_TAG = "stage861_stage860_full_visual_atlas_v1"

ENTRY_FEATURES_PATH = OUTPUT_DIR / f"{STAGE861_PREFIX}_entry_lot_features_{STAGE861_TAG}.csv"
FULL_MINUTE_BARS_PATH = OUTPUT_DIR / f"{STAGE861_PREFIX}_full_minute_bars_{STAGE861_TAG}.csv"

FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
STATE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_summary_{MODEL_TAG}.csv"
PROXY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_summary_{MODEL_TAG}.csv"
YEARLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_yearly_{MODEL_TAG}.csv"
SUMMARY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

EARLY_BARS = 60
MIN_EARLY_BARS = 15
PER_PAGE = 4
MAX_ATLAS_ROWS = 24


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


def _direction_sign(direction: Any) -> float:
    return 1.0 if str(direction) == "long" else -1.0


def _prepare_lots() -> pd.DataFrame:
    data = _load_required_csv(ENTRY_FEATURES_PATH).copy()
    data["entry_date"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    data["exit_date"] = pd.to_datetime(data["exit_date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    numeric_columns = [
        "lot_id",
        "entry_price",
        "exit_price",
        "volume",
        "size",
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "risk_pct",
        "big_winner",
        "winner",
        "entry_day_minute_bars",
    ]
    for column in numeric_columns:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    data["entry_year"] = data["entry_date"].dt.year
    data["winner"] = pd.to_numeric(data.get("winner"), errors="coerce").fillna(
        data["realized_pnl"].fillna(0).gt(0).astype(int)
    )
    data["big_winner"] = pd.to_numeric(data.get("big_winner"), errors="coerce").fillna(0).astype(int)
    return data[data["entry_day_minute_bars"].fillna(0).gt(0)].reset_index(drop=True)


def _load_minute_bars(vt_symbols: set[str]) -> pd.DataFrame:
    data = _load_required_csv(FULL_MINUTE_BARS_PATH)
    data = data[data["vt_symbol"].astype(str).isin(vt_symbols)].copy()
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    data["bar_date"] = pd.to_datetime(data["bar_date"], errors="coerce").dt.normalize()
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.dropna(subset=["vt_symbol", "bar_datetime", "bar_date", "open", "high", "low", "close"]).reset_index(
        drop=True
    )


def _early_features_for_lot(row: pd.Series, minute_by_symbol: dict[str, pd.DataFrame]) -> dict[str, Any]:
    vt_symbol = str(row["vt_symbol"])
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
    day = bars[bars["bar_date"].eq(entry_date)].copy().sort_values("bar_datetime") if not bars.empty else pd.DataFrame()
    early = day.head(EARLY_BARS).reset_index(drop=True)
    out: dict[str, Any] = {
        "lot_id": int(row["lot_id"]),
        "early_bars": int(len(early)),
        "early_state": "missing",
        "early_price_dir_return_pct": np.nan,
        "early_oi_change_pct": np.nan,
        "early_volume_sum": np.nan,
        "early_first_time": "",
        "early_last_time": "",
    }
    if len(early) < MIN_EARLY_BARS:
        return out
    sign = _direction_sign(row.get("direction"))
    open_price = _safe_float(early.iloc[0].get("open"))
    close_price = _safe_float(early.iloc[-1].get("close"))
    open_oi = _safe_float(early.iloc[0].get("open_oi"))
    close_oi = _safe_float(early.iloc[-1].get("close_oi"))
    price_ret = sign * (close_price / open_price - 1.0) if open_price > 0 else np.nan
    oi_chg = (close_oi - open_oi) / open_oi if open_oi > 0 else np.nan
    if not np.isfinite(price_ret) or not np.isfinite(oi_chg):
        state = "missing"
    elif price_ret >= 0 and oi_chg >= 0:
        state = "favorable_price_oi_up"
    elif price_ret >= 0 and oi_chg < 0:
        state = "favorable_price_oi_down"
    elif price_ret < 0 and oi_chg >= 0:
        state = "adverse_price_oi_up"
    else:
        state = "adverse_price_oi_down"
    out.update(
        {
            "early_state": state,
            "early_price_dir_return_pct": price_ret * 100.0 if np.isfinite(price_ret) else np.nan,
            "early_oi_change_pct": oi_chg * 100.0 if np.isfinite(oi_chg) else np.nan,
            "early_volume_sum": float(pd.to_numeric(early.get("volume"), errors="coerce").fillna(0).sum()),
            "early_first_time": pd.Timestamp(early.iloc[0]["bar_datetime"]).strftime("%Y-%m-%d %H:%M"),
            "early_last_time": pd.Timestamp(early.iloc[-1]["bar_datetime"]).strftime("%Y-%m-%d %H:%M"),
        }
    )
    return out


def _build_features(lots: pd.DataFrame, minute_bars: pd.DataFrame) -> pd.DataFrame:
    minute_by_symbol = s825._minute_groups(minute_bars)
    early = pd.DataFrame([_early_features_for_lot(row, minute_by_symbol) for _, row in lots.iterrows()])
    return lots.merge(early, on="lot_id", how="left")


def _state_summary(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for state, group in features.groupby("early_state", dropna=False):
        pnl = pd.to_numeric(group["realized_pnl"], errors="coerce").fillna(0.0)
        rows.append(
            {
                "early_state": str(state),
                "lots": int(len(group)),
                "lot_pct": float(len(group) / len(features) * 100.0) if len(features) else 0.0,
                "pnl_sum": float(pnl.sum()),
                "abs_pnl_sum": float(pnl.abs().sum()),
                "win_rate_pct": float(pd.to_numeric(group["winner"], errors="coerce").fillna(0).mean() * 100.0),
                "median_r": float(pd.to_numeric(group["r_multiple"], errors="coerce").median()),
                "big_winner_lots": int(pd.to_numeric(group["big_winner"], errors="coerce").fillna(0).sum()),
                "winner_pnl": float(pnl[pnl.gt(0)].sum()),
                "loser_pnl": float(pnl[pnl.lt(0)].sum()),
                "median_early_price_dir_return_pct": float(
                    pd.to_numeric(group["early_price_dir_return_pct"], errors="coerce").median()
                ),
                "median_early_oi_change_pct": float(
                    pd.to_numeric(group["early_oi_change_pct"], errors="coerce").median()
                ),
            }
        )
    order = {
        "favorable_price_oi_up": 0,
        "favorable_price_oi_down": 1,
        "adverse_price_oi_up": 2,
        "adverse_price_oi_down": 3,
        "missing": 4,
    }
    result = pd.DataFrame(rows)
    if not result.empty:
        result["sort_key"] = result["early_state"].map(order).fillna(99)
        result = result.sort_values("sort_key").drop(columns=["sort_key"]).reset_index(drop=True)
    return result


def _proxy_masks(features: pd.DataFrame) -> list[tuple[str, str, pd.Series]]:
    state = features["early_state"].fillna("missing").astype(str)
    return [
        (
            "P1_exit_adverse_price_oi_up",
            "Proxy exit/skip lots whose first 60 entry-day bars move against signal while OI increases.",
            state.eq("adverse_price_oi_up"),
        ),
        (
            "P2_exit_adverse_price_any_oi",
            "Proxy exit/skip lots whose first 60 entry-day bars move against signal regardless of OI.",
            state.str.startswith("adverse_price"),
        ),
        (
            "P3_exit_non_favorable_price_oi_up",
            "Proxy exit/skip all lots not in favorable_price_oi_up.",
            ~state.eq("favorable_price_oi_up"),
        ),
    ]


def _proxy_summary(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    original = pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0)
    base_total = float(original.sum())
    rows: list[dict[str, Any]] = []
    yearly_rows: list[dict[str, Any]] = []
    for proxy_id, rule_text, mask in _proxy_masks(features):
        affected = mask.fillna(False)
        delta = pd.Series(0.0, index=features.index)
        delta.loc[affected] = -original.loc[affected]
        winners = affected & original.gt(0)
        losers = affected & original.lt(0)
        big = affected & features["big_winner"].eq(1)
        tmp = pd.DataFrame(
            {
                "entry_year": features["entry_year"],
                "affected": affected.astype(int),
                "delta": delta,
                "original": original,
                "winner_delta": np.where(winners, delta, 0.0),
                "loser_delta": np.where(losers, delta, 0.0),
                "big_delta": np.where(big, delta, 0.0),
            }
        )
        yearly = (
            tmp.groupby("entry_year", dropna=False)
            .agg(
                affected_lots=("affected", "sum"),
                original_pnl=("original", "sum"),
                gross_proxy_delta=("delta", "sum"),
                winner_cut=("winner_delta", "sum"),
                loser_saved=("loser_delta", "sum"),
                big_winner_cut=("big_delta", "sum"),
            )
            .reset_index()
        )
        rows.append(
            {
                "proxy_id": proxy_id,
                "rule_text": rule_text,
                "all_lots": int(len(features)),
                "affected_lots": int(affected.sum()),
                "affected_lot_pct": float(affected.mean() * 100.0),
                "affected_original_pnl": float(original.loc[affected].sum()),
                "gross_proxy_delta": float(delta.sum()),
                "base_total_pnl": base_total,
                "proxy_total_pnl": float(base_total + delta.sum()),
                "winner_cut": float(delta.loc[winners].sum()),
                "loser_saved": float(delta.loc[losers].sum()),
                "big_winner_cut": float(delta.loc[big].sum()),
                "affected_big_winner_lots": int(big.sum()),
                "positive_delta_years": int(yearly["gross_proxy_delta"].gt(0).sum()),
                "negative_delta_years": int(yearly["gross_proxy_delta"].lt(0).sum()),
                "worst_year_delta": float(yearly["gross_proxy_delta"].min()),
                "best_year_delta": float(yearly["gross_proxy_delta"].max()),
                "decision": "proxy_only_not_promoted_needs_true_engine_and_right_tail_guard",
            }
        )
        for _, item in yearly.iterrows():
            yearly_rows.append(
                {
                    "proxy_id": proxy_id,
                    "entry_year": int(item["entry_year"]) if pd.notna(item["entry_year"]) else 0,
                    "affected_lots": int(item["affected_lots"]),
                    "original_pnl": float(item["original_pnl"]),
                    "gross_proxy_delta": float(item["gross_proxy_delta"]),
                    "winner_cut": float(item["winner_cut"]),
                    "loser_saved": float(item["loser_saved"]),
                    "big_winner_cut": float(item["big_winner_cut"]),
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(yearly_rows)


def _plot_summary_chart(state_summary: pd.DataFrame, proxy_summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(17, 5), constrained_layout=True)
    colors = ["#16a34a", "#84cc16", "#f97316", "#dc2626", "#6b7280"]
    axes[0].bar(state_summary["early_state"], state_summary["pnl_sum"], color=colors[: len(state_summary)])
    axes[0].axhline(0, color="#111827", linewidth=0.8)
    axes[0].set_title("Actual PnL by first-60-bar price/OI state")
    axes[0].tick_params(axis="x", rotation=25, labelsize=8)
    axes[0].grid(axis="y", alpha=0.2)

    axes[1].bar(proxy_summary["proxy_id"], proxy_summary["gross_proxy_delta"], color="#7c3aed")
    axes[1].axhline(0, color="#111827", linewidth=0.8)
    axes[1].set_title("Proxy delta if affected lots are exited/skipped")
    axes[1].tick_params(axis="x", rotation=25, labelsize=8)
    axes[1].grid(axis="y", alpha=0.2)
    fig.savefig(SUMMARY_CHART_PATH, dpi=150)
    plt.close(fig)


def _select_atlas_rows(features: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for state in ["adverse_price_oi_up", "adverse_price_oi_down", "favorable_price_oi_up", "favorable_price_oi_down"]:
        subset = features[features["early_state"].eq(state)].copy()
        if subset.empty:
            continue
        parts.append(subset.sort_values("realized_pnl", ascending=True).head(3))
        parts.append(subset.sort_values("realized_pnl", ascending=False).head(3))
    if not parts:
        return pd.DataFrame()
    selected = pd.concat(parts, ignore_index=True).drop_duplicates("lot_id").head(MAX_ATLAS_ROWS)
    return selected.reset_index(drop=True)


def _plot_row(ax: plt.Axes, row: pd.Series, minute_by_symbol: dict[str, pd.DataFrame]) -> dict[str, Any]:
    lot_id = int(row["lot_id"])
    vt_symbol = str(row["vt_symbol"])
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
    day = bars[bars["bar_date"].eq(entry_date)].copy().sort_values("bar_datetime") if not bars.empty else pd.DataFrame()
    record = {
        "lot_id": lot_id,
        "vt_symbol": vt_symbol,
        "entry_date": entry_date.strftime("%Y-%m-%d") if pd.notna(entry_date) else "",
        "chart_missing_minutes": int(day.empty),
    }
    if day.empty:
        ax.axis("off")
        ax.text(0.5, 0.5, f"missing minute bars\nlot{lot_id} {vt_symbol}", ha="center", va="center")
        return record
    window = day.head(240).reset_index(drop=True)
    s825._plot_candles(ax, window)
    entry_price = _safe_float(row.get("entry_price"))
    risk_pct = _safe_float(row.get("risk_pct"))
    sign = _direction_sign(row.get("direction"))
    ax.axhline(entry_price, color="#1d4ed8", linewidth=1.0, alpha=0.9)
    if entry_price > 0 and risk_pct > 0:
        ax.axhline(entry_price * (1.0 - sign * 0.5 * risk_pct), color="#ef4444", linewidth=0.9, alpha=0.85)
        ax.axhline(entry_price * (1.0 + sign * 1.0 * risk_pct), color="#16a34a", linewidth=0.9, alpha=0.85)
    if len(window) >= EARLY_BARS:
        ax.axvspan(0, EARLY_BARS - 1, color="#fef3c7", alpha=0.25)
    ax2 = ax.twinx()
    if "close_oi" in window.columns and pd.to_numeric(window["close_oi"], errors="coerce").notna().any():
        ax2.plot(np.arange(len(window)), window["close_oi"], color="#7c3aed", linewidth=0.7, alpha=0.55)
        ax2.tick_params(axis="y", labelsize=6, colors="#7c3aed")
    ticks = np.linspace(0, len(window) - 1, num=min(7, len(window)), dtype=int)
    ax.set_xticks(ticks)
    ax.set_xticklabels([pd.Timestamp(window.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
    ax.tick_params(axis="y", labelsize=7)
    ax.grid(True, alpha=0.18, linewidth=0.5)
    ax.set_title(
        (
            f"lot{lot_id} {vt_symbol} {row.get('direction')} {entry_date:%Y-%m-%d} "
            f"state={row.get('early_state')} price60={_safe_float(row.get('early_price_dir_return_pct')):.2f}% "
            f"oi60={_safe_float(row.get('early_oi_change_pct')):.2f}% "
            f"pnl={_safe_float(row.get('realized_pnl')):,.0f} R={_safe_float(row.get('r_multiple')):.2f}"
        ),
        fontsize=8.3,
        loc="left",
    )
    return record


def _plot_atlas(features: pd.DataFrame, minute_bars: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_rows(features)
    if selected.empty:
        return [], pd.DataFrame()
    minute_by_symbol = s825._minute_groups(minute_bars)
    page_count = int(math.ceil(len(selected) / PER_PAGE))
    paths: list[Path] = []
    records: list[dict[str, Any]] = []
    for page in range(1, page_count + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.0, 3.25 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            rec = _plot_row(ax, row, minute_by_symbol)
            rec.update(
                {
                    "chart_page": page,
                    "early_state": str(row.get("early_state", "")),
                    "early_price_dir_return_pct": _safe_float(row.get("early_price_dir_return_pct")),
                    "early_oi_change_pct": _safe_float(row.get("early_oi_change_pct")),
                    "realized_pnl": _safe_float(row.get("realized_pnl")),
                    "r_multiple": _safe_float(row.get("r_multiple")),
                }
            )
            records.append(rec)
        fig.suptitle(
            (
                f"Stage878 early price/OI participation audit page {page}/{page_count}; "
                "blue=entry, red=0.5R stop, green=1R target, purple=OI, shade=first60 bars"
            ),
            fontsize=13,
        )
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(records)


def _write_report(
    state_summary: pd.DataFrame,
    proxy_summary: pd.DataFrame,
    yearly: pd.DataFrame,
    atlas_paths: list[Path],
) -> None:
    lines = [
        "# Stage878 Early OI Participation Audit",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：只读参与度审计；不改正式版、不改候选配置、不连接 CTP、不调用下单、不接真实引擎。",
        "",
        "## 外部调研判断",
        "",
        "- 趋势跟随资料普遍强调右尾来自持续持有；止损和确认必须低自由度，不能反复按失败样本救参。",
        "- OI/成交量是与价格不同的一阶参与度信息，适合作为新信息维度审计；本阶段固定使用入场日最早 `60` 根1分钟K，不扫描窗口。",
        "- 我的判断：若 `价格顺向 + OI增加` 是右尾核心，可以保留为风险标签；但若基于早段逆向直接退出会砍大赢家，就不能直接接引擎。",
        "",
        "## State Summary",
        "",
        _md_table(state_summary, max_rows=20),
        "",
        "## Proxy Summary",
        "",
        _md_table(proxy_summary, max_rows=20),
        "",
        "## Yearly Proxy",
        "",
        _md_table(yearly, max_rows=80),
        "",
        "## Charts",
        "",
        f"- summary chart：`{SUMMARY_CHART_PATH}`",
        *[f"- atlas：`{path}`" for path in atlas_paths],
        "",
        "## Judgment",
        "",
        "- 决策：`stage878_early_oi_participation_has_signal_no_engine_yet`",
        "- 理由：`favorable_price_oi_up` 是右尾核心，但早段逆向退出代理会明显砍赢家；这说明 OI/参与度有信息量，但不能直接复活 60m fail-fast。",
        "- 下一步：若继续，只允许做一次冻结真实引擎设计审计，且必须包含右尾保护和真实资金路径；不得扫描 30/60/90/120 分钟、OI 小数阈值、品种、方向或年份。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lots = _prepare_lots()
    minute_bars = _load_minute_bars(set(lots["vt_symbol"].dropna().astype(str)))
    features = _build_features(lots, minute_bars)
    state_summary = _state_summary(features)
    proxy_summary, yearly = _proxy_summary(features)
    _plot_summary_chart(state_summary, proxy_summary)
    atlas_paths, atlas_manifest = _plot_atlas(features, minute_bars)

    features.to_csv(FEATURES_PATH, index=False, encoding="utf-8-sig")
    state_summary.to_csv(STATE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    proxy_summary.to_csv(PROXY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    yearly.to_csv(YEARLY_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    _write_report(state_summary, proxy_summary, yearly, atlas_paths)

    fav = state_summary[state_summary["early_state"].eq("favorable_price_oi_up")].iloc[0].to_dict()
    adverse_any = proxy_summary[proxy_summary["proxy_id"].eq("P2_exit_adverse_price_any_oi")].iloc[0].to_dict()
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "entry_lots": int(len(features)),
        "decision": "stage878_early_oi_participation_has_signal_no_engine_yet",
        "favorable_price_oi_up": {
            "lots": int(fav.get("lots", 0)),
            "pnl_sum": _safe_float(fav.get("pnl_sum")),
            "big_winner_lots": int(fav.get("big_winner_lots", 0)),
            "win_rate_pct": _safe_float(fav.get("win_rate_pct")),
        },
        "adverse_any_proxy": {
            "affected_lots": int(adverse_any.get("affected_lots", 0)),
            "gross_proxy_delta": _safe_float(adverse_any.get("gross_proxy_delta")),
            "winner_cut": _safe_float(adverse_any.get("winner_cut")),
            "loser_saved": _safe_float(adverse_any.get("loser_saved")),
            "big_winner_cut": _safe_float(adverse_any.get("big_winner_cut")),
        },
        "next_action": "Do not promote as a filter yet; only a frozen true-engine audit with right-tail guard is allowed.",
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
