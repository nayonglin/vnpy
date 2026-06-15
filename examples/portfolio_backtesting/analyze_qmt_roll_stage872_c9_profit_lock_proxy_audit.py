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
import analyze_qmt_roll_stage870_stage847_progress_confirm_recovery_engine as s870
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage872"
MODEL_TAG = "stage872_c9_profit_lock_proxy_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage872_c9_profit_lock_proxy_audit"

C9_ARM = s870.C9_ARM
STAGE870_PREFIX = s870.OUTPUT_PREFIX
STAGE870_TAG = s870.MODEL_TAG

CLOSED_LOTS_IN = OUTPUT_DIR / f"{STAGE870_PREFIX}_closed_lots_{STAGE870_TAG}.csv"
DECISION_IN = OUTPUT_DIR / f"{STAGE870_PREFIX}_decision_{STAGE870_TAG}.json"

LOT_FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_features_{MODEL_TAG}.csv"
PROXY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_summary_{MODEL_TAG}.csv"
MFE_BUCKET_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_mfe_bucket_summary_{MODEL_TAG}.csv"
YEARLY_PROXY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_yearly_proxy_summary_{MODEL_TAG}.csv"
SUMMARY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

HARD_TAKE_PROFIT_R = [1.0, 2.0, 4.0, 8.0]
BREAKEVEN_AFTER_R = [1.0, 2.0, 4.0]
LOCK_SPECS = [(2.0, 1.0), (4.0, 1.0), (4.0, 2.0), (8.0, 2.0)]
PER_PAGE_LOTS = 3
MAX_ATLAS_LOTS = 12


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


def _prepare_c9_lots() -> pd.DataFrame:
    data = _load_required_csv(CLOSED_LOTS_IN)
    data = data[data["arm"].astype(str).eq(C9_ARM)].copy()
    data["entry_date"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.normalize()
    data["exit_date"] = pd.to_datetime(data["exit_date"], errors="coerce").dt.normalize()
    numeric_columns = [
        "lot_id",
        "holding_calendar_days",
        "entry_price",
        "exit_price",
        "volume",
        "size",
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "stop_distance",
        "mfe_cash",
        "mae_cash",
        "mfe_r",
        "mae_r",
        "days_to_mfe",
        "days_to_mae",
        "big_winner",
    ]
    for column in numeric_columns:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    data["valid_proxy_sample"] = (
        data["risk_amount"].gt(0)
        & data["mfe_r"].notna()
        & data["r_multiple"].notna()
        & data["realized_pnl"].notna()
    )
    data["realized_efficiency"] = np.where(data["mfe_r"].gt(0), data["r_multiple"] / data["mfe_r"], np.nan)
    data["entry_year"] = data["entry_date"].dt.year
    data["risk_price"] = data["stop_distance"].abs()
    missing_risk = ~data["risk_price"].gt(0)
    data.loc[missing_risk, "risk_price"] = np.where(
        data.loc[missing_risk, "volume"].gt(0) & data.loc[missing_risk, "size"].gt(0),
        data.loc[missing_risk, "risk_amount"] / (data.loc[missing_risk, "volume"] * data.loc[missing_risk, "size"]),
        np.nan,
    )
    return data.reset_index(drop=True)


def _proxy_columns(lots: pd.DataFrame) -> pd.DataFrame:
    data = lots.copy()
    valid = data["valid_proxy_sample"].fillna(False)
    for r in HARD_TAKE_PROFIT_R:
        proxy_col = f"proxy_hard_tp_{r:g}r_pnl"
        delta_col = f"delta_hard_tp_{r:g}r"
        trigger_col = f"trigger_hard_tp_{r:g}r"
        trigger = valid & data["mfe_r"].ge(r)
        data[trigger_col] = trigger.astype(int)
        data[proxy_col] = data["realized_pnl"]
        data.loc[trigger, proxy_col] = data.loc[trigger, "risk_amount"] * r
        data[delta_col] = np.where(valid, data[proxy_col] - data["realized_pnl"], np.nan)
    for r in BREAKEVEN_AFTER_R:
        proxy_col = f"proxy_be_after_{r:g}r_pnl"
        delta_col = f"delta_be_after_{r:g}r"
        trigger_col = f"trigger_be_after_{r:g}r"
        trigger = valid & data["mfe_r"].ge(r) & data["r_multiple"].lt(0)
        data[trigger_col] = trigger.astype(int)
        data[proxy_col] = data["realized_pnl"]
        data.loc[trigger, proxy_col] = 0.0
        data[delta_col] = np.where(valid, data[proxy_col] - data["realized_pnl"], np.nan)
    for activate_r, lock_r in LOCK_SPECS:
        proxy_col = f"proxy_lock_{lock_r:g}r_after_{activate_r:g}r_pnl"
        delta_col = f"delta_lock_{lock_r:g}r_after_{activate_r:g}r"
        trigger_col = f"trigger_lock_{lock_r:g}r_after_{activate_r:g}r"
        trigger = valid & data["mfe_r"].ge(activate_r) & data["r_multiple"].lt(lock_r)
        data[trigger_col] = trigger.astype(int)
        data[proxy_col] = data["realized_pnl"]
        data.loc[trigger, proxy_col] = data.loc[trigger, "risk_amount"] * lock_r
        data[delta_col] = np.where(valid, data[proxy_col] - data["realized_pnl"], np.nan)
    return data


def _summarize_proxy(data: pd.DataFrame) -> pd.DataFrame:
    valid = data[data["valid_proxy_sample"].fillna(False)].copy()
    base_pnl = float(valid["realized_pnl"].sum())
    rows: list[dict[str, Any]] = []

    def add_row(proxy_id: str, trigger_col: str, proxy_col: str, family: str, note: str) -> None:
        delta = valid[proxy_col] - valid["realized_pnl"]
        trigger = valid[trigger_col].fillna(0).gt(0)
        rows.append(
            {
                "proxy_id": proxy_id,
                "family": family,
                "note": note,
                "triggered_lots": int(trigger.sum()),
                "triggered_big_winners": int((trigger & valid["big_winner"].fillna(0).gt(0)).sum()),
                "triggered_winners": int((trigger & valid["realized_pnl"].gt(0)).sum()),
                "triggered_losers": int((trigger & valid["realized_pnl"].lt(0)).sum()),
                "base_pnl": base_pnl,
                "proxy_pnl": float(valid[proxy_col].sum()),
                "delta": float(delta.sum()),
                "winner_cut": float(delta.where(delta < 0, 0.0).sum()),
                "loser_saved": float(delta.where(delta > 0, 0.0).sum()),
                "median_trigger_mfe_r": float(valid.loc[trigger, "mfe_r"].median()) if trigger.any() else np.nan,
                "median_trigger_r_multiple": float(valid.loc[trigger, "r_multiple"].median()) if trigger.any() else np.nan,
            }
        )

    for r in HARD_TAKE_PROFIT_R:
        add_row(
            f"hard_takeprofit_{r:g}r_if_mfe_ge_{r:g}r",
            f"trigger_hard_tp_{r:g}r",
            f"proxy_hard_tp_{r:g}r_pnl",
            "hard_takeprofit",
            "若盘中/持仓路径触及固定 R 目标则直接止盈；用于检验固定止盈是否会砍右尾。",
        )
    for r in BREAKEVEN_AFTER_R:
        add_row(
            f"optimistic_breakeven_after_{r:g}r_only_final_losers",
            f"trigger_be_after_{r:g}r",
            f"proxy_be_after_{r:g}r_pnl",
            "optimistic_profit_lock_upper_bound",
            "乐观上限：只把最终亏损且曾达到目标 R 的交易拉到保本，不计入途中洗出赢家的代价。",
        )
    for activate_r, lock_r in LOCK_SPECS:
        add_row(
            f"optimistic_lock_{lock_r:g}r_after_{activate_r:g}r_if_final_below_lock",
            f"trigger_lock_{lock_r:g}r_after_{activate_r:g}r",
            f"proxy_lock_{lock_r:g}r_after_{activate_r:g}r_pnl",
            "optimistic_profit_lock_upper_bound",
            "乐观上限：达到较高 R 后若最终低于锁定位，则按锁定位出场；不计入途中回撤后再创新高的误杀。",
        )
    return pd.DataFrame(rows).sort_values("delta", ascending=False).reset_index(drop=True)


def _mfe_bucket_summary(data: pd.DataFrame) -> pd.DataFrame:
    valid = data[data["valid_proxy_sample"].fillna(False)].copy()
    valid["mfe_bucket"] = pd.cut(
        valid["mfe_r"],
        bins=[-1.0, 0.0, 1.0, 2.0, 4.0, 8.0, np.inf],
        labels=["0", "0-1", "1-2", "2-4", "4-8", "8+"],
    )
    return (
        valid.groupby("mfe_bucket", observed=False)
        .agg(
            lots=("lot_id", "count"),
            pnl=("realized_pnl", "sum"),
            winner_pnl=("realized_pnl", lambda s: float(s[s > 0].sum())),
            loser_pnl=("realized_pnl", lambda s: float(s[s < 0].sum())),
            big_winners=("big_winner", "sum"),
            median_r_multiple=("r_multiple", "median"),
            median_mfe_r=("mfe_r", "median"),
            median_mae_r=("mae_r", "median"),
        )
        .reset_index()
    )


def _yearly_proxy(data: pd.DataFrame) -> pd.DataFrame:
    valid = data[data["valid_proxy_sample"].fillna(False)].copy()
    proxy_ids = [
        ("hard_takeprofit_1r", "proxy_hard_tp_1r_pnl"),
        ("hard_takeprofit_2r", "proxy_hard_tp_2r_pnl"),
        ("hard_takeprofit_4r", "proxy_hard_tp_4r_pnl"),
        ("hard_takeprofit_8r", "proxy_hard_tp_8r_pnl"),
        ("optimistic_lock_1r_after_2r", "proxy_lock_1r_after_2r_pnl"),
        ("optimistic_be_after_1r", "proxy_be_after_1r_pnl"),
    ]
    rows: list[dict[str, Any]] = []
    for year, group in valid.groupby("entry_year", dropna=False):
        base = float(group["realized_pnl"].sum())
        row: dict[str, Any] = {"entry_year": int(year) if pd.notna(year) else 0, "lots": int(len(group)), "base_pnl": base}
        for proxy_id, column in proxy_ids:
            row[f"{proxy_id}_pnl"] = float(group[column].sum())
            row[f"{proxy_id}_delta"] = float(group[column].sum() - base)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("entry_year").reset_index(drop=True)


def _plot_summary(proxy_summary: pd.DataFrame, mfe_summary: pd.DataFrame) -> None:
    if proxy_summary.empty:
        return
    fig, axes = plt.subplots(2, 1, figsize=(16, 9), constrained_layout=True)
    ordered = proxy_summary.sort_values("delta", ascending=True).copy()
    colors = np.where(ordered["delta"].ge(0), "#0f766e", "#dc2626")
    axes[0].barh(ordered["proxy_id"], ordered["delta"] / 1_000_000.0, color=colors)
    axes[0].axvline(0, color="#111827", linewidth=0.8)
    axes[0].set_title("Stage872 proxy delta vs C9 valid sample")
    axes[0].set_xlabel("delta million")
    axes[0].grid(True, axis="x", alpha=0.25)

    if not mfe_summary.empty:
        x = np.arange(len(mfe_summary))
        axes[1].bar(x, mfe_summary["winner_pnl"] / 1_000_000.0, label="winner pnl", color="#2563eb")
        axes[1].bar(x, mfe_summary["loser_pnl"] / 1_000_000.0, label="loser pnl", color="#d97706")
        axes[1].plot(x, mfe_summary["big_winners"], marker="o", color="#7c3aed", label="big winners")
        axes[1].set_xticks(x)
        axes[1].set_xticklabels(mfe_summary["mfe_bucket"].astype(str).tolist())
        axes[1].set_title("C9 PnL by MFE bucket")
        axes[1].set_xlabel("MFE R bucket")
        axes[1].set_ylabel("PnL million / big winner count")
        axes[1].legend(loc="best")
        axes[1].grid(True, alpha=0.25)
    fig.savefig(SUMMARY_CHART_PATH, dpi=150)
    plt.close(fig)


def _load_minute_groups(lots: pd.DataFrame) -> dict[str, pd.DataFrame]:
    vt_symbols = set(lots["vt_symbol"].dropna().astype(str).unique())
    minute_bars = s864._load_full_minute_bars(vt_symbols)
    return s825._minute_groups(minute_bars)


def _day_bars(minute_by_symbol: dict[str, pd.DataFrame], vt_symbol: str, day: Any) -> pd.DataFrame:
    bars = minute_by_symbol.get(str(vt_symbol), pd.DataFrame())
    if bars.empty or pd.isna(day):
        return pd.DataFrame()
    focus = pd.Timestamp(day).normalize()
    return bars[bars["bar_date"].eq(focus)].copy().sort_values("bar_datetime").reset_index(drop=True)


def _level(row: pd.Series, r: float) -> float:
    entry = _safe_float(row.get("entry_price"))
    risk = _safe_float(row.get("risk_price"))
    if not np.isfinite(entry) or not np.isfinite(risk):
        return np.nan
    return entry + _direction_sign(row.get("direction")) * r * risk


def _plot_day(ax: plt.Axes, bars: pd.DataFrame, row: pd.Series, title: str) -> int:
    if bars.empty:
        ax.text(0.5, 0.5, f"missing minute bars\n{title}", ha="center", va="center")
        ax.set_axis_off()
        return 0
    s825._plot_candles(ax, bars)
    lines = [
        ("entry", row.get("entry_price"), "#2563eb", "-"),
        ("exit", row.get("exit_price"), "#dc2626", ":"),
        ("+1R", _level(row, 1.0), "#0f766e", "--"),
        ("+2R", _level(row, 2.0), "#7c3aed", "--"),
        ("+4R", _level(row, 4.0), "#d97706", "--"),
    ]
    for label, price, color, linestyle in lines:
        value = _safe_float(price)
        if np.isfinite(value):
            ax.axhline(value, color=color, linestyle=linestyle, linewidth=0.85, label=label)
    ticks = np.linspace(0, len(bars) - 1, num=min(8, len(bars)), dtype=int)
    ax.set_xticks(ticks)
    ax.set_xticklabels([pd.Timestamp(bars.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        dedup = dict(zip(labels, handles, strict=False))
        ax.legend(dedup.values(), dedup.keys(), loc="best", fontsize=7)
    ax.grid(True, alpha=0.18)
    return int(len(bars))


def _select_atlas_lots(data: pd.DataFrame, minute_by_symbol: dict[str, pd.DataFrame]) -> pd.DataFrame:
    valid = data[data["valid_proxy_sample"].fillna(False)].copy()
    if not valid.empty:
        entry_counts: list[int] = []
        exit_counts: list[int] = []
        for _, row in valid.iterrows():
            entry_counts.append(len(_day_bars(minute_by_symbol, str(row["vt_symbol"]), row["entry_date"])))
            exit_counts.append(len(_day_bars(minute_by_symbol, str(row["vt_symbol"]), row["exit_date"])))
        valid["entry_day_minute_bars_for_atlas"] = entry_counts
        valid["exit_day_minute_bars_for_atlas"] = exit_counts
        valid["complete_entry_exit_minute_visual"] = (
            valid["entry_day_minute_bars_for_atlas"].gt(0) & valid["exit_day_minute_bars_for_atlas"].gt(0)
        ).astype(int)
    valid["atlas_reason"] = ""
    valid["atlas_abs_delta"] = 0.0

    hard_cut = valid[valid["delta_hard_tp_8r"].lt(0)].copy()
    hard_cut["atlas_reason"] = "hard_tp8_cuts_right_tail"
    hard_cut["atlas_abs_delta"] = hard_cut["delta_hard_tp_8r"].abs()

    lock_save = valid[valid["delta_lock_1r_after_2r"].gt(0)].copy()
    lock_save["atlas_reason"] = "optimistic_lock1_after2_saves_giveback"
    lock_save["atlas_abs_delta"] = lock_save["delta_lock_1r_after_2r"].abs()

    low_mfe_losers = valid[valid["mfe_r"].lt(1.0) & valid["realized_pnl"].lt(0)].copy()
    low_mfe_losers["atlas_reason"] = "low_mfe_loser_not_solved_by_profit_lock"
    low_mfe_losers["atlas_abs_delta"] = low_mfe_losers["realized_pnl"].abs()

    selected = pd.concat(
        [
            hard_cut.sort_values(["complete_entry_exit_minute_visual", "atlas_abs_delta"], ascending=[False, False]).head(4),
            lock_save.sort_values(["complete_entry_exit_minute_visual", "atlas_abs_delta"], ascending=[False, False]).head(5),
            low_mfe_losers.sort_values(["complete_entry_exit_minute_visual", "atlas_abs_delta"], ascending=[False, False]).head(3),
        ],
        ignore_index=True,
        sort=False,
    )
    return selected.drop_duplicates(["lot_id", "vt_symbol", "entry_date", "exit_date"]).head(MAX_ATLAS_LOTS).reset_index(drop=True)


def _plot_atlas(data: pd.DataFrame, minute_by_symbol: dict[str, pd.DataFrame]) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_lots(data, minute_by_symbol)
    if selected.empty:
        return [], pd.DataFrame()
    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    for page_start in range(0, len(selected), PER_PAGE_LOTS):
        page_rows = selected.iloc[page_start : page_start + PER_PAGE_LOTS]
        page = page_start // PER_PAGE_LOTS + 1
        fig, axes = plt.subplots(len(page_rows), 2, figsize=(18, 4.2 * len(page_rows)), constrained_layout=True)
        axes_arr = np.asarray(axes).reshape(len(page_rows), 2)
        for row_index, (_, row) in enumerate(page_rows.iterrows()):
            vt_symbol = str(row["vt_symbol"])
            entry_bars = _day_bars(minute_by_symbol, vt_symbol, row["entry_date"])
            exit_bars = _day_bars(minute_by_symbol, vt_symbol, row["exit_date"])
            entry_count = _plot_day(
                axes_arr[row_index, 0],
                entry_bars,
                row,
                f"entry {vt_symbol} {pd.Timestamp(row['entry_date']).date()}",
            )
            exit_count = _plot_day(
                axes_arr[row_index, 1],
                exit_bars,
                row,
                f"exit {vt_symbol} {pd.Timestamp(row['exit_date']).date()}",
            )
            subtitle = (
                f"{row.get('atlas_reason')} | {vt_symbol} {row.get('direction')} "
                f"PnL {row.get('realized_pnl'):.0f} R {row.get('r_multiple'):.2f} MFE {row.get('mfe_r'):.2f}"
            )
            axes_arr[row_index, 0].set_title("entry day | " + subtitle, fontsize=8)
            axes_arr[row_index, 1].set_title("exit day | " + subtitle, fontsize=8)
            manifest.append(
                {
                    "page": page,
                    "atlas_reason": row.get("atlas_reason"),
                    "lot_id": int(row.get("lot_id")) if pd.notna(row.get("lot_id")) else 0,
                    "vt_symbol": vt_symbol,
                    "direction": row.get("direction"),
                    "entry_date": pd.Timestamp(row["entry_date"]).date().isoformat(),
                    "exit_date": pd.Timestamp(row["exit_date"]).date().isoformat(),
                    "realized_pnl": _safe_float(row.get("realized_pnl")),
                    "risk_amount": _safe_float(row.get("risk_amount")),
                    "r_multiple": _safe_float(row.get("r_multiple")),
                    "mfe_r": _safe_float(row.get("mfe_r")),
                    "mae_r": _safe_float(row.get("mae_r")),
                    "delta_hard_tp_8r": _safe_float(row.get("delta_hard_tp_8r")),
                    "delta_lock_1r_after_2r": _safe_float(row.get("delta_lock_1r_after_2r")),
                    "entry_day_minute_bars": entry_count,
                    "exit_day_minute_bars": exit_count,
                }
            )
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.suptitle("Stage872 C9 profit-lock proxy minute-K atlas", fontsize=13)
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest)


def _decision(proxy_summary: pd.DataFrame) -> str:
    hard = proxy_summary[proxy_summary["family"].eq("hard_takeprofit")]
    lock = proxy_summary[proxy_summary["proxy_id"].eq("optimistic_lock_1r_after_2r_if_final_below_lock")]
    if not hard.empty and hard["delta"].max() < 0 and not lock.empty and float(lock["delta"].iloc[0]) > 0:
        return "stage872_fixed_takeprofit_rejected_profit_lock_upper_bound_promising_needs_real_engine"
    if not hard.empty and hard["delta"].max() < 0:
        return "stage872_fixed_takeprofit_rejected_no_engine"
    return "stage872_profit_lock_proxy_mixed_needs_followup"


def _write_report(
    lots: pd.DataFrame,
    proxy_summary: pd.DataFrame,
    mfe_summary: pd.DataFrame,
    yearly_proxy: pd.DataFrame,
    atlas_paths: list[Path],
    decision: str,
) -> None:
    valid = lots[lots["valid_proxy_sample"].fillna(False)].copy()
    big = valid[valid["big_winner"].fillna(0).gt(0)].copy()
    top_winners = valid.sort_values("realized_pnl", ascending=False).head(15)
    top_lock_saves = valid.sort_values("delta_lock_1r_after_2r", ascending=False).head(15)
    lines = [
        "# Stage872 C9 右尾保护代理审计",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：只读代理审计和分钟K视觉复盘；不改正式版、不改候选配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- Turtle Trading 原始规则强调让趋势奔跑，并用止损/加仓纪律管理风险：https://oxfordstrat.com/coasdfASD32/uploads/2016/01/turtle-rules.pdf",
        "- Backtrader stop / StopTrail 文档说明追踪止损是可执行订单语义，但回测必须验证是否误杀后续趋势：https://www.backtrader.com/blog/posts/2018-02-01-stop-trading/stop-trading/",
        "- Backtrader order execution docs：https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/",
        "- 我的判断：先不要写真实引擎；先用 C9 全周期逐笔验证固定止盈和锁盈上限，判断保护是否会砍掉右尾。",
        "",
        "## Sample",
        "",
        f"- C9 lots：`{len(lots)}`",
        f"- valid proxy sample：`{len(valid)}`",
        f"- valid sample PnL：`{valid['realized_pnl'].sum():,.1f}`",
        f"- big winners：`{len(big)}`，big winner PnL：`{big['realized_pnl'].sum():,.1f}`",
        "",
        "## Proxy Summary",
        "",
        _md_table(proxy_summary, max_rows=20),
        "",
        "## MFE Bucket Summary",
        "",
        _md_table(mfe_summary, max_rows=20),
        "",
        "## Yearly Proxy Summary",
        "",
        _md_table(yearly_proxy, max_rows=20),
        "",
        "## Top Winners",
        "",
        _md_table(
            top_winners[
                [
                    "lot_id",
                    "vt_symbol",
                    "direction",
                    "entry_date",
                    "exit_date",
                    "realized_pnl",
                    "risk_amount",
                    "r_multiple",
                    "mfe_r",
                    "mae_r",
                    "exit_reason",
                    "big_winner",
                ]
            ],
            max_rows=15,
        ),
        "",
        "## Top Optimistic Lock Saves",
        "",
        _md_table(
            top_lock_saves[
                [
                    "lot_id",
                    "vt_symbol",
                    "direction",
                    "entry_date",
                    "exit_date",
                    "realized_pnl",
                    "risk_amount",
                    "r_multiple",
                    "mfe_r",
                    "mae_r",
                    "delta_lock_1r_after_2r",
                    "exit_reason",
                ]
            ],
            max_rows=15,
        ),
        "",
        "## Visuals",
        "",
        f"- summary chart：`{SUMMARY_CHART_PATH}`",
        *[f"- atlas page：`{path}`" for path in atlas_paths],
        "",
        "## Judgment",
        "",
        f"- 决策：`{decision}`。",
        "- 固定止盈如果全为负，说明不能用简单 take-profit 增强 C9；锁盈上限若为正，只能说明存在值得真实引擎验证的空间，不能直接宣传为收益。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not DECISION_IN.exists():
        raise RuntimeError(f"missing Stage870 decision: {DECISION_IN}")

    lots = _proxy_columns(_prepare_c9_lots())
    proxy_summary = _summarize_proxy(lots)
    mfe_summary = _mfe_bucket_summary(lots)
    yearly_proxy = _yearly_proxy(lots)
    minute_by_symbol = _load_minute_groups(lots)
    atlas_paths, atlas_manifest = _plot_atlas(lots, minute_by_symbol)
    _plot_summary(proxy_summary, mfe_summary)
    decision = _decision(proxy_summary)

    lots.to_csv(LOT_FEATURES_PATH, index=False, encoding="utf-8-sig")
    proxy_summary.to_csv(PROXY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    mfe_summary.to_csv(MFE_BUCKET_PATH, index=False, encoding="utf-8-sig")
    yearly_proxy.to_csv(YEARLY_PROXY_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    _write_report(lots, proxy_summary, mfe_summary, yearly_proxy, atlas_paths, decision)

    payload = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_stage870_decision": json.loads(DECISION_IN.read_text(encoding="utf-8")),
        "decision": decision,
        "c9_lots": int(len(lots)),
        "valid_proxy_sample": int(lots["valid_proxy_sample"].sum()),
        "valid_proxy_pnl": float(lots.loc[lots["valid_proxy_sample"], "realized_pnl"].sum()),
        "proxy_summary": proxy_summary.to_dict("records"),
        "outputs": {
            "report": str(REPORT_PATH),
            "lot_features": str(LOT_FEATURES_PATH),
            "proxy_summary": str(PROXY_SUMMARY_PATH),
            "mfe_bucket": str(MFE_BUCKET_PATH),
            "yearly_proxy": str(YEARLY_PROXY_PATH),
            "summary_chart": str(SUMMARY_CHART_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "atlas_pages": [str(path) for path in atlas_paths],
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
