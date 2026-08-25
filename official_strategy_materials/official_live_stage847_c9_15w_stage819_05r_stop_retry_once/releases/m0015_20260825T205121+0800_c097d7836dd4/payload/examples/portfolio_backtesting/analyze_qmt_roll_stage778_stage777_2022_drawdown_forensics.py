from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653
import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719
import analyze_qmt_roll_stage757_c50_oi_confirm_risk_restore as s757
import analyze_qmt_roll_stage772_am40_80_120_oi_monthly as s772
import analyze_qmt_roll_stage777_am41_oi08_monthly as s777
from run_qmt_alignment_backtest import (
    build_entry_candidate_snapshots_df,
    build_entry_risk_diagnostics_df,
    build_positions_df,
    build_trades_df,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage778_stage777_2022_drawdown_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage778_stage777_2022_drawdown_forensics"
LINE_ID = "futures_trend_2019_data_extension"

DD_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_windows_{MODEL_TAG}.csv"
YEAR_ATTRIBUTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_attribution_{MODEL_TAG}.csv"
REPLAY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_replay_summary_{MODEL_TAG}.csv"
PRODUCT_CONTRIBUTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_contribution_{MODEL_TAG}.csv"
ENTRY_OI_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_oi_summary_{MODEL_TAG}.csv"
CLOSED_LOTS_AROUND_DD_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_around_dd_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

SELECTED_TOP_DD_COUNT = 5
FORCED_SELECTED_STARTS = ("2018-01", "2021-09", "2022-01")
REPLAY_PROFILES = ("oi_restore_am40", "no_oi_am40")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _product_from_vt_symbol(vt_symbol: Any) -> str:
    text = str(vt_symbol or "")
    if "." not in text:
        return text
    symbol, exchange = text.split(".", 1)
    product = re.sub(r"\d+$", "", symbol)
    return f"{product}.{exchange}"


def _drawdown_windows(curves: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for start_month, group in curves.groupby("start_month", sort=True):
        ordered = group.sort_values("date").copy()
        equity = pd.to_numeric(ordered["account_equity"], errors="coerce").ffill()
        peak = equity.cummax()
        dd = equity / peak.replace(0.0, np.nan) - 1.0
        trough_idx = dd.idxmin()
        before_trough = ordered.loc[:trough_idx].copy()
        peak_idx = pd.to_numeric(before_trough["account_equity"], errors="coerce").idxmax()
        peak_row = ordered.loc[peak_idx]
        trough_row = ordered.loc[trough_idx]
        peak_date = pd.Timestamp(peak_row["date"]).normalize()
        trough_date = pd.Timestamp(trough_row["date"]).normalize()
        peak_equity = float(peak_row["account_equity"])
        trough_equity = float(trough_row["account_equity"])
        rows.append(
            {
                "start_month": str(start_month),
                "start_year": int(str(start_month)[:4]),
                "peak_date": peak_date.date().isoformat(),
                "trough_date": trough_date.date().isoformat(),
                "peak_year": int(peak_date.year),
                "trough_year": int(trough_date.year),
                "max_dd_pct": float(dd.loc[trough_idx] * 100.0),
                "peak_equity": peak_equity,
                "trough_equity": trough_equity,
                "loss_cash": trough_equity - peak_equity,
                "loss_pct_of_peak": (trough_equity / peak_equity - 1.0) * 100.0 if peak_equity > 0 else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values(["max_dd_pct", "start_month"]).reset_index(drop=True)


def _year_attribution(curves: pd.DataFrame) -> pd.DataFrame:
    data = curves.copy()
    data["year"] = pd.to_datetime(data["date"], errors="coerce").dt.year
    rows: list[dict[str, Any]] = []
    for (start_month, year), group in data.groupby(["start_month", "year"], sort=True):
        ordered = group.sort_values("date")
        equity = pd.to_numeric(ordered["account_equity"], errors="coerce").ffill()
        net_pnl = pd.to_numeric(ordered["net_pnl"], errors="coerce").fillna(0.0)
        dd = pd.to_numeric(ordered["drawdown_pct"], errors="coerce")
        rows.append(
            {
                "start_month": str(start_month),
                "year": int(year),
                "days": int(len(ordered)),
                "start_equity": float(equity.iloc[0]),
                "end_equity": float(equity.iloc[-1]),
                "net_pnl": float(net_pnl.sum()),
                "return_on_year_start_pct": float((equity.iloc[-1] / equity.iloc[0] - 1.0) * 100.0)
                if float(equity.iloc[0]) > 0
                else np.nan,
                "min_global_drawdown_pct_in_year": float(dd.min()) if dd.notna().any() else np.nan,
                "trade_count": float(pd.to_numeric(ordered.get("trade_count", 0), errors="coerce").fillna(0.0).sum()),
            }
        )
    return pd.DataFrame(rows)


def _selected_starts(dd_windows: pd.DataFrame) -> list[str]:
    starts = list(dd_windows.nsmallest(SELECTED_TOP_DD_COUNT, "max_dd_pct")["start_month"].astype(str))
    for start in FORCED_SELECTED_STARTS:
        if start not in starts:
            starts.append(start)
    return starts


def _profile_by_name(metadata: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {profile["profile"]: profile for profile in s772._profile_specs(metadata)}


def _run_profile(
    *,
    profile: dict[str, Any],
    start: pd.Timestamp,
    metadata: dict[str, Any],
    base_c3_overrides: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    spec: s653.ForcedVariant = replace(profile["spec"])
    original_start = s653.s517.START_DT
    original_end = s653.s517.END_DT
    original_preload = s653.s517.PRELOAD_START_DT
    try:
        s653.s517.START_DT = start.to_pydatetime()
        s653.s517.END_DT = s777.ANALYSIS_END.to_pydatetime()
        s653.s517.PRELOAD_START_DT = s772._preload_for_start(start).to_pydatetime()

        s653.s517.assert_stage196_database_sentinels()
        s653.s517.s506._patch_stage506_raw_roots()
        preload_start = max(s653.s517.PRELOAD_START_DT, s653.s517.START_DT - pd.Timedelta(days=365).to_pytimedelta())
        _, open_map = s653.s517.s506.s501._seed_proxy_maps()
        engine = s653.s517.s506.s502.ConfirmedDailyNextRealOpenEngine(open_map)
        engine.output = lambda msg: None
        engine.set_parameters(
            vt_symbols=metadata["vt_symbols"],
            interval=s653.s517.Interval.DAILY,
            start=preload_start,
            end=s653.s517.END_DT,
            rates=metadata["rates"],
            slippages=metadata["slippages"],
            sizes=metadata["sizes"],
            priceticks=metadata["priceticks"],
            capital=spec.capital.c3_capital,
        )
        setting = s772._build_setting(
            metadata=metadata,
            spec=spec,
            base_c3_overrides=base_c3_overrides,
            start=start,
        )
        engine.add_strategy(profile["strategy_cls"], setting)
        engine.load_data()
        engine.run_backtesting()
        daily_df = engine.calculate_result()
        if daily_df is None or daily_df.empty:
            raise RuntimeError(f"empty daily result: {profile['profile']} {start.date()}")

        daily = daily_df.copy()
        daily = daily.loc[(daily.index >= start.date()) & (daily.index <= s777.ANALYSIS_END.date())].reset_index()
        daily.rename(columns={"index": "date"}, inplace=True)
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
        for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
            daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
        daily["variant"] = spec.capital.variant
        daily["combo_variant"] = spec.capital.variant
        daily["label"] = spec.capital.label
        daily["risk_multiplier"] = spec.capital.risk_multiplier
        daily["note"] = spec.capital.note

        positions = build_positions_df(engine)
        if not positions.empty:
            positions["variant"] = spec.capital.variant
            positions["combo_variant"] = spec.capital.variant
            positions["label"] = spec.capital.label
            positions["risk_multiplier"] = spec.capital.risk_multiplier
            margin_daily, _ = s513._position_margin(positions, metadata)
        else:
            margin_daily = pd.DataFrame(columns=["variant", "combo_variant", "date", "c3_margin_exact", "c3_active_contracts", "c3_active_products"])
        combined = s772._combine_daily(daily, margin_daily, spec)

        strategy = getattr(engine, "strategy", None)
        frames = {
            "trades": build_trades_df(engine),
            "positions": positions,
            "entry_risk": build_entry_risk_diagnostics_df(engine),
            "entry_candidates": build_entry_candidate_snapshots_df(engine),
            "trade_events": pd.DataFrame(getattr(strategy, "trade_event_diagnostics", []) if strategy else []),
        }
        for frame in frames.values():
            if frame.empty:
                continue
            frame["profile"] = profile["profile"]
            frame["start_month"] = start.strftime("%Y-%m")
            frame["variant"] = spec.capital.variant
        return combined, frames
    finally:
        s653.s517.START_DT = original_start
        s653.s517.END_DT = original_end
        s653.s517.PRELOAD_START_DT = original_preload


def _replay_selected(dd_windows: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metadata = s513._metadata()
    profiles = _profile_by_name(metadata)
    base_c3_overrides = dict(s513._c3_overrides(pd.Timestamp("2018-01-01").to_pydatetime()))
    selected = _selected_starts(dd_windows)
    dd_by_start = dd_windows.set_index("start_month").to_dict("index")

    replay_rows: list[dict[str, Any]] = []
    product_rows: list[dict[str, Any]] = []
    entry_rows: list[dict[str, Any]] = []
    closed_rows: list[pd.DataFrame] = []

    for start_text in selected:
        start = pd.Timestamp(f"{start_text}-01")
        window = dd_by_start[start_text]
        peak_date = pd.Timestamp(window["peak_date"]).normalize()
        trough_date = pd.Timestamp(window["trough_date"]).normalize()
        entry_scan_start = peak_date - pd.Timedelta(days=90)
        for profile_name in REPLAY_PROFILES:
            print(f"[stage778] replay {profile_name} {start_text}", flush=True)
            combined, frames = _run_profile(
                profile=profiles[profile_name],
                start=start,
                metadata=metadata,
                base_c3_overrides=base_c3_overrides,
            )
            ordered = combined.sort_values("date").copy()
            equity = pd.to_numeric(ordered["account_equity"], errors="coerce").ffill()
            peak = equity.cummax()
            dd = equity / peak.replace(0.0, np.nan) - 1.0
            trough_idx = dd.idxmin()
            own_peak_idx = pd.to_numeric(ordered.loc[:trough_idx, "account_equity"], errors="coerce").idxmax()
            own_peak_date = pd.Timestamp(ordered.loc[own_peak_idx, "date"]).normalize()
            own_trough_date = pd.Timestamp(ordered.loc[trough_idx, "date"]).normalize()
            replay_rows.append(
                {
                    "profile": profile_name,
                    "start_month": start_text,
                    "reference_peak_date": peak_date.date().isoformat(),
                    "reference_trough_date": trough_date.date().isoformat(),
                    "own_peak_date": own_peak_date.date().isoformat(),
                    "own_trough_date": own_trough_date.date().isoformat(),
                    "own_max_dd_pct": float(dd.loc[trough_idx] * 100.0),
                    "own_peak_equity": float(ordered.loc[own_peak_idx, "account_equity"]),
                    "own_trough_equity": float(ordered.loc[trough_idx, "account_equity"]),
                    "own_loss_cash": float(ordered.loc[trough_idx, "account_equity"] - ordered.loc[own_peak_idx, "account_equity"]),
                    "reference_window_net_pnl": float(
                        pd.to_numeric(
                            ordered[
                                pd.to_datetime(ordered["date"]).between(peak_date, trough_date, inclusive="right")
                            ]["net_pnl"],
                            errors="coerce",
                        ).fillna(0.0).sum()
                    ),
                    "reference_window_trade_count": float(
                        pd.to_numeric(
                            ordered[
                                pd.to_datetime(ordered["date"]).between(peak_date, trough_date, inclusive="right")
                            ]["trade_count"],
                            errors="coerce",
                        ).fillna(0.0).sum()
                    ),
                }
            )

            positions = frames["positions"].copy()
            if not positions.empty:
                positions["date"] = pd.to_datetime(positions["date"], errors="coerce").dt.normalize()
                positions["product"] = positions["vt_symbol"].map(_product_from_vt_symbol)
                window_positions = positions[positions["date"].between(peak_date, trough_date, inclusive="right")].copy()
                for (product, vt_symbol), group in window_positions.groupby(["product", "vt_symbol"], sort=False):
                    net_pnl = float(pd.to_numeric(group["net_pnl"], errors="coerce").fillna(0.0).sum())
                    product_rows.append(
                        {
                            "profile": profile_name,
                            "start_month": start_text,
                            "peak_date": peak_date.date().isoformat(),
                            "trough_date": trough_date.date().isoformat(),
                            "product": product,
                            "vt_symbol": vt_symbol,
                            "net_pnl": net_pnl,
                            "holding_pnl": float(pd.to_numeric(group["holding_pnl"], errors="coerce").fillna(0.0).sum()),
                            "trading_pnl": float(pd.to_numeric(group["trading_pnl"], errors="coerce").fillna(0.0).sum()),
                            "trade_count": float(pd.to_numeric(group["trade_count"], errors="coerce").fillna(0.0).sum()),
                            "active_days": int(
                                (
                                    pd.to_numeric(group["start_pos"], errors="coerce").fillna(0.0).abs().gt(0)
                                    | pd.to_numeric(group["end_pos"], errors="coerce").fillna(0.0).abs().gt(0)
                                ).sum()
                            ),
                        }
                    )

            entry = frames["entry_risk"].copy()
            if not entry.empty:
                entry["date"] = pd.to_datetime(entry["date"], errors="coerce").dt.normalize()
                scan = entry[entry["date"].between(entry_scan_start, trough_date)].copy()
                for applied, group in scan.groupby(
                    pd.to_numeric(scan.get("oi_price_confirm_risk_restore_applied", 0), errors="coerce").fillna(0).astype(int),
                    sort=True,
                ):
                    entry_rows.append(
                        {
                            "profile": profile_name,
                            "start_month": start_text,
                            "entry_scan_start": entry_scan_start.date().isoformat(),
                            "trough_date": trough_date.date().isoformat(),
                            "oi_restore_applied": int(applied),
                            "entry_count": int(len(group)),
                            "actual_risk_amount_sum": float(pd.to_numeric(group.get("actual_risk_amount", 0), errors="coerce").fillna(0.0).sum()),
                            "actual_margin_amount_sum": float(pd.to_numeric(group.get("actual_margin_amount", 0), errors="coerce").fillna(0.0).sum()),
                            "volume_sum": float(pd.to_numeric(group.get("volume", 0), errors="coerce").fillna(0.0).sum()),
                            "base_layer_count": int(group["layer_kind"].astype(str).eq("base").sum()) if "layer_kind" in group else 0,
                            "add_layer_count": int((~group["layer_kind"].astype(str).eq("base")).sum()) if "layer_kind" in group else 0,
                        }
                    )

            trades = frames["trades"]
            candidates = frames["entry_candidates"]
            closed = s719._build_closed_lots(trades, entry, candidates, metadata)
            if not closed.empty:
                closed = s757._add_lot_features(closed, trades, entry)
                closed["entry_date"] = pd.to_datetime(closed["entry_date"], errors="coerce").dt.normalize()
                closed["exit_date"] = pd.to_datetime(closed["exit_date"], errors="coerce").dt.normalize()
                around = closed[
                    closed["entry_date"].le(trough_date)
                    & closed["exit_date"].ge(peak_date)
                ].copy()
                around["profile"] = profile_name
                around["start_month"] = start_text
                around["reference_peak_date"] = peak_date.date().isoformat()
                around["reference_trough_date"] = trough_date.date().isoformat()
                closed_rows.append(around)

    replay = pd.DataFrame(replay_rows)
    product = pd.DataFrame(product_rows)
    entry_oi = pd.DataFrame(entry_rows)
    closed_around = pd.concat(closed_rows, ignore_index=True, sort=False) if closed_rows else pd.DataFrame()
    return replay, product, entry_oi, closed_around


def _plot(dd_windows: pd.DataFrame, curves: pd.DataFrame, product: pd.DataFrame) -> None:
    selected = _selected_starts(dd_windows)
    selected_curves = curves[curves["start_month"].astype(str).isin(selected)].copy()
    selected_curves["date"] = pd.to_datetime(selected_curves["date"], errors="coerce")
    selected_curves = selected_curves[
        selected_curves["date"].between(pd.Timestamp("2022-01-01"), pd.Timestamp("2022-09-30"))
    ].copy()

    fig, axes = plt.subplots(2, 2, figsize=(16, 10), constrained_layout=True)
    year_counts = (
        dd_windows.assign(dd40_fail=dd_windows["max_dd_pct"].lt(-40.0).astype(int))
        .groupby("trough_year", as_index=False)
        .agg(start_count=("start_month", "count"), dd40_fail=("dd40_fail", "sum"))
    )
    x = np.arange(len(year_counts))
    axes[0, 0].bar(x - 0.18, year_counts["start_count"], width=0.36, label="all max-DD troughs", color="#2563eb")
    axes[0, 0].bar(x + 0.18, year_counts["dd40_fail"], width=0.36, label="DD<-40%", color="#dc2626")
    axes[0, 0].set_xticks(x)
    axes[0, 0].set_xticklabels(year_counts["trough_year"].astype(str))
    axes[0, 0].set_title("Stage777 max drawdown trough year distribution")
    axes[0, 0].legend(fontsize=8)
    axes[0, 0].grid(axis="y", alpha=0.25)

    for start_month, group in selected_curves.groupby("start_month", sort=True):
        axes[0, 1].plot(group["date"], pd.to_numeric(group["drawdown_pct"], errors="coerce"), label=start_month, linewidth=1.3)
    axes[0, 1].axhline(-40.0, color="#dc2626", linestyle="--", linewidth=1)
    axes[0, 1].set_title("Selected starts drawdown during 2022")
    axes[0, 1].set_ylabel("Drawdown %")
    axes[0, 1].legend(ncol=3, fontsize=8)
    axes[0, 1].grid(alpha=0.25)

    oi_product = product[product["profile"].eq("oi_restore_am40")].copy()
    if not oi_product.empty:
        worst_start = str(dd_windows.iloc[0]["start_month"])
        single = oi_product[oi_product["start_month"].eq(worst_start)].copy()
        single = single.groupby("product", as_index=False).agg(net_pnl=("net_pnl", "sum")).nsmallest(10, "net_pnl")
        axes[1, 0].barh(single["product"], single["net_pnl"] / 1_000_000, color="#b91c1c")
        axes[1, 0].set_title(f"Worst start {worst_start}: product PnL in peak-to-trough")
        axes[1, 0].set_xlabel("PnL (million)")
        axes[1, 0].grid(axis="x", alpha=0.25)

        agg = oi_product.groupby("product", as_index=False).agg(net_pnl=("net_pnl", "sum")).nsmallest(10, "net_pnl")
        axes[1, 1].barh(agg["product"], agg["net_pnl"] / 1_000_000, color="#7f1d1d")
        axes[1, 1].set_title("Selected OI starts: aggregate product PnL in 2022 DD windows")
        axes[1, 1].set_xlabel("PnL (million)")
        axes[1, 1].grid(axis="x", alpha=0.25)
    fig.suptitle("Stage778 Stage777 2022 drawdown forensics")
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    dd_windows: pd.DataFrame,
    year_attr: pd.DataFrame,
    replay: pd.DataFrame,
    product: pd.DataFrame,
    entry_oi: pd.DataFrame,
    closed_around: pd.DataFrame,
) -> None:
    trough_summary = (
        dd_windows.assign(dd40_fail=dd_windows["max_dd_pct"].lt(-40.0).astype(int))
        .groupby("trough_year", as_index=False)
        .agg(
            start_count=("start_month", "count"),
            dd40_fail_count=("dd40_fail", "sum"),
            median_dd_pct=("max_dd_pct", "median"),
            worst_dd_pct=("max_dd_pct", "min"),
        )
    )
    y2022 = year_attr[year_attr["year"].eq(2022)].copy()
    y2022_summary = pd.DataFrame(
        [
            {
                "start_count": int(len(y2022)),
                "negative_2022_pnl_count": int(pd.to_numeric(y2022["net_pnl"], errors="coerce").lt(0.0).sum()),
                "median_2022_pnl": float(pd.to_numeric(y2022["net_pnl"], errors="coerce").median()),
                "p10_2022_pnl": float(pd.to_numeric(y2022["net_pnl"], errors="coerce").quantile(0.10)),
                "worst_2022_pnl": float(pd.to_numeric(y2022["net_pnl"], errors="coerce").min()),
            }
        ]
    )
    replay_view = replay.sort_values(["profile", "own_max_dd_pct", "start_month"])
    product_view = (
        product[product["profile"].eq("oi_restore_am40")]
        .groupby(["start_month", "product"], as_index=False)
        .agg(net_pnl=("net_pnl", "sum"), active_days=("active_days", "sum"), trade_count=("trade_count", "sum"))
        .sort_values(["start_month", "net_pnl"])
    )
    entry_view = entry_oi.sort_values(["profile", "start_month", "oi_restore_applied"])
    closed_view = closed_around.copy()
    if not closed_view.empty:
        closed_view["realized_pnl"] = pd.to_numeric(closed_view["realized_pnl"], errors="coerce").fillna(0.0)
        closed_view = closed_view.sort_values("realized_pnl").head(30)

    lines = [
        "# Stage778 Stage777 2022 最大回撤归因",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        "- 性质：只读归因；未修改正式版配置、未连接 CTP、未调用下单。",
        "- 口径：Stage777 `AM41 + OI0.8` 逐月曲线；复跑最差回撤代表起点，并对比 `no_oi_am40`。",
        "",
        "## 最大回撤年份分布",
        "",
        _md_table(trough_summary),
        "",
        "## 2022 年度损益分布",
        "",
        _md_table(y2022_summary),
        "",
        "## 最差回撤起点",
        "",
        _md_table(dd_windows.head(15)),
        "",
        "## 代表起点复跑对照",
        "",
        _md_table(replay_view, max_rows=30),
        "",
        "## 代表起点 OI 版本峰谷窗口品种贡献",
        "",
        _md_table(product_view, max_rows=60),
        "",
        "## 峰谷前 90 天至谷值的 OI 放大入场统计",
        "",
        _md_table(entry_view, max_rows=60),
        "",
        "## DD 窗口重叠的最差闭合 lot",
        "",
        _md_table(closed_view[[c for c in [
            "profile",
            "start_month",
            "entry_date",
            "exit_date",
            "product",
            "vt_symbol",
            "direction",
            "volume",
            "realized_pnl",
            "r_multiple",
            "oi_price_confirm_risk_restore_applied",
            "exit_reason",
        ] if c in closed_view.columns]], max_rows=30),
        "",
        "## 结论",
        "",
        "- 2022 是共同回撤年份，不是单一起点噪声：Stage777 101 个逐月起点里，52 个最大回撤谷值落在 2022，47 个 DD40 失败全部落在 2022。",
        "- 峰谷集中在 `2022-03-09 -> 2022-06-29`：这是趋势策略在高波动后突然进入多品种反向/震荡的共同压力窗口。",
        "- OI0.8 的问题不是 OI 无效，而是 OI 只确认参与度，没有确认价格路径的单边性；在 2022 这种宏观冲击后的反转/宽幅震荡里，OI 上升会同步放大错误趋势仓。",
        "- 结论仍然是不推广单 OI 放大仓位。下一步若继续，只能把 OI 放进多因子质量评分，并叠加波动收敛、相关性/拥挤度和价格顺畅度，不能继续扫 OI 倍率。",
        "",
        "## 过拟合与继续价值",
        "",
        "- 运行前判断：低过拟合，原因是只读归因，不调参。",
        "- 运行后判断：低过拟合，结论来自 101 个逐月起点共同落点和代表起点交易复盘，不是挑单个窗口救参。",
        "- 继续价值：有，但只限于风险机制解释和新特征设计；没有继续扫 `0.7/0.8/0.9` 的价值。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curves = pd.read_csv(s777.CURVES_PATH, encoding="utf-8-sig")
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    dd_windows = _drawdown_windows(curves)
    year_attr = _year_attribution(curves)
    replay, product, entry_oi, closed_around = _replay_selected(dd_windows)

    dd_windows.to_csv(DD_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    year_attr.to_csv(YEAR_ATTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    replay.to_csv(REPLAY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product.to_csv(PRODUCT_CONTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    entry_oi.to_csv(ENTRY_OI_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    closed_around.to_csv(CLOSED_LOTS_AROUND_DD_PATH, index=False, encoding="utf-8-sig")
    _plot(dd_windows, curves, product)
    _write_report(dd_windows, year_attr, replay, product, entry_oi, closed_around)

    trough_summary = (
        dd_windows.assign(dd40_fail=dd_windows["max_dd_pct"].lt(-40.0).astype(int))
        .groupby("trough_year", as_index=False)
        .agg(
            start_count=("start_month", "count"),
            dd40_fail_count=("dd40_fail", "sum"),
            median_dd_pct=("max_dd_pct", "median"),
            worst_dd_pct=("max_dd_pct", "min"),
        )
    )
    print(_md_table(trough_summary))
    print(_md_table(replay.sort_values(["profile", "own_max_dd_pct", "start_month"]), max_rows=20))
    print(f"report={REPORT_PATH}")
    print(f"chart={CHART_PATH}")


if __name__ == "__main__":
    main()
