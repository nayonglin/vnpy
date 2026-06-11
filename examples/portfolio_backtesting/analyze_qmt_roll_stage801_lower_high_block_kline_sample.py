from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage752_theoretical_winner_kline_atlas as s752
import analyze_qmt_roll_stage772_am40_80_120_oi_monthly as s772
import analyze_qmt_roll_stage777_am41_oi08_monthly as s777
import analyze_qmt_roll_stage778_stage777_2022_drawdown_forensics as s778
import analyze_qmt_roll_stage798_stage777_top20_loss_kline_atlas as s798


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
TUSHARE_DAILY_ROOT = PROJECT_DIR / "downloaded_futures" / "tushare_stage196_stage78_2015_2019"

MODEL_TAG = "stage801_lower_high_block_kline_sample_v1"
OUTPUT_PREFIX = "qmt_roll_stage801_lower_high_block_kline_sample"
LINE_ID = "futures_trend_2019_data_extension"

START = pd.Timestamp("2018-01-01")
RANDOM_SEED = 801
SAMPLE_N = 30
PRE_BARS = 50
POST_BARS = 50
PER_PAGE = 5
MA_LINES = (
    (5, "#f59e0b"),
    (10, "#2563eb"),
    (20, "#7c3aed"),
    (40, "#111827"),
)

VARIANT = "stage801_stage777_500k_am41_oi08_old_ai_long_two_lower_high_block_context_2018"
LABEL = "Stage801 Stage777 lower-high blocked signal context replay 2018"

BLOCKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_blocked_signals_{MODEL_TAG}.csv"
SAMPLE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_sample30_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_page{{page:02d}}_{MODEL_TAG}.png"


class QmtRollPortfolioStrategyLowerHighContext(s772.QmtRollPortfolioStrategyExactAm):
    """Research-only replay: block long lower-high signals and keep chart context."""

    block_long_two_lower_highs: bool = True
    parameters = [
        *s772.QmtRollPortfolioStrategyExactAm.parameters,
        "block_long_two_lower_highs",
    ]

    def on_bars(self, bars: dict[str, Any]) -> None:
        self._stage801_current_bars = bars
        self._stage801_am_vt_map = {id(am): vt_symbol for vt_symbol, am in self.ams.items()}
        return super().on_bars(bars)

    def _infer_product_vt_symbol(self, vt_symbol: str) -> str:
        if "." not in vt_symbol:
            return vt_symbol
        contract, exchange = vt_symbol.split(".", 1)
        product = ""
        for char in contract:
            if char.isalpha():
                product += char
            else:
                break
        return f"{product}.{exchange}" if product else vt_symbol

    def _generate_signal(self, am: Any, history: pd.DataFrame) -> dict[str, Any]:
        vt_symbol = getattr(self, "_stage801_am_vt_map", {}).get(id(am), "")
        bar = getattr(self, "_stage801_current_bars", {}).get(vt_symbol)
        self._stage801_filter_context = {
            "vt_symbol": vt_symbol,
            "product_vt_symbol": self._infer_product_vt_symbol(vt_symbol) if vt_symbol else "",
            "bar": bar,
        }
        return super()._generate_signal(am, history)

    def _long_two_lower_highs(self, history: pd.DataFrame) -> tuple[bool, dict[str, Any]]:
        if history is None or len(history) < 3 or "high" not in history.columns:
            return False, {}
        highs = pd.to_numeric(history["high"].tail(3), errors="coerce")
        if highs.isna().any():
            return False, {}
        high_t2, high_t1, high_t = [float(value) for value in highs.to_list()]
        blocked = bool(high_t < high_t1 < high_t2)
        return blocked, {
            "high_t": high_t,
            "high_t_minus_1": high_t1,
            "high_t_minus_2": high_t2,
        }

    def _passes_entry_filters(self, signal: str, history: pd.DataFrame) -> bool:
        if not s772.QmtRollPortfolioStrategyExactAm._passes_entry_filters(self, signal, history):
            return False
        if not bool(self.block_long_two_lower_highs):
            return True
        if not str(signal or "").startswith("long"):
            return True
        blocked, snapshot = self._long_two_lower_highs(history)
        if not blocked:
            return True

        context = dict(getattr(self, "_stage801_filter_context", {}) or {})
        bar = context.get("bar")
        event_dt = pd.NaT
        event_price = float("nan")
        if bar is not None:
            event_dt = pd.Timestamp(bar.datetime).tz_localize(None).normalize()
            event_price = float(bar.close_price)

        self.trade_event_diagnostics.append(
            {
                "datetime": event_dt,
                "date": event_dt,
                "vt_symbol": context.get("vt_symbol", ""),
                "product_vt_symbol": context.get("product_vt_symbol", ""),
                "position_direction": "long",
                "direction": "long",
                "offset": "SignalFilter",
                "reason": "long_two_lower_high_block",
                "volume": 0,
                "price": event_price,
                "signal": signal,
                **snapshot,
            }
        )
        return False


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _profile(metadata: dict[str, Any]) -> dict[str, Any]:
    base = next(profile for profile in s772._profile_specs(metadata) if profile["profile"] == "oi_restore_am40")
    spec = base["spec"]
    capital = replace(
        spec.capital,
        variant=VARIANT,
        label=LABEL,
        note=(
            f"{spec.capital.note} | Stage801 context replay for random K-line atlas of long two-lower-high blocks."
        ),
    )
    candidate = dict(base)
    candidate["profile"] = "stage801_oi_restore_am40_long_two_lower_high_block_context"
    candidate["strategy_cls"] = QmtRollPortfolioStrategyLowerHighContext
    candidate["spec"] = replace(
        spec,
        capital=capital,
        overrides={**spec.overrides, "block_long_two_lower_highs": True},
        profile=candidate["profile"],
    )
    candidate["note"] = "Context replay only. Same Stage800 lower-high block, with vt_symbol/date logging for charting."
    return candidate


def _run_blocks() -> pd.DataFrame:
    if BLOCKS_PATH.exists():
        cached = pd.read_csv(BLOCKS_PATH, encoding="utf-8-sig")
        cached["date"] = pd.to_datetime(cached["date"], errors="coerce").dt.normalize()
        cached["datetime"] = pd.to_datetime(cached["datetime"], errors="coerce")
        cached = cached.dropna(subset=["date", "vt_symbol"]).reset_index(drop=True)
        if not cached.empty:
            return cached

    metadata = s513._metadata()
    profile = _profile(metadata)
    base_c3_overrides = dict(s513._c3_overrides(pd.Timestamp("2018-01-01").to_pydatetime()))
    _combined, frames = s778._run_profile(
        profile=profile,
        start=START,
        metadata=metadata,
        base_c3_overrides=base_c3_overrides,
    )
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    if trade_events.empty or "reason" not in trade_events.columns:
        return pd.DataFrame()
    blocks = trade_events[trade_events["reason"].eq("long_two_lower_high_block")].copy()
    blocks["date"] = pd.to_datetime(blocks["date"], errors="coerce").dt.normalize()
    blocks["datetime"] = pd.to_datetime(blocks["datetime"], errors="coerce")
    blocks = blocks.dropna(subset=["date", "vt_symbol"]).reset_index(drop=True)
    blocks["block_id"] = np.arange(1, len(blocks) + 1)
    return blocks


def _read_tushare_contract_bars(vt_symbol: Any) -> pd.DataFrame:
    text = str(vt_symbol or "")
    if "." not in text:
        return pd.DataFrame()
    contract_symbol, exchange = text.split(".", 1)
    exchange_dir = TUSHARE_DAILY_ROOT / exchange
    paths = list(exchange_dir.glob(f"{contract_symbol}__*.csv"))
    if not paths:
        paths = list(exchange_dir.glob(f"{contract_symbol.lower()}__*.csv"))
    if not paths:
        paths = list(exchange_dir.glob(f"{contract_symbol.upper()}__*.csv"))
    if not paths:
        return pd.DataFrame()

    frame = pd.read_csv(paths[0], encoding="utf-8-sig")
    if frame.empty:
        return pd.DataFrame()
    if "trade_date" not in frame.columns:
        return pd.DataFrame()
    trade_text = frame["trade_date"].astype(str).str.replace(r"\.0$", "", regex=True)
    parsed_date = pd.to_datetime(trade_text, format="%Y%m%d", errors="coerce")
    if parsed_date.isna().all():
        parsed_date = pd.to_datetime(trade_text, errors="coerce")
    else:
        parsed_fallback = pd.to_datetime(trade_text, errors="coerce")
        parsed_date = parsed_date.fillna(parsed_fallback)
    frame["date"] = parsed_date.dt.normalize()
    frame.rename(columns={"vol": "volume", "oi": "close_oi"}, inplace=True)
    for column in ["open", "high", "low", "close", "volume", "close_oi"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return (
        frame.dropna(subset=["date", "open", "high", "low", "close"])
        .drop_duplicates("date")
        .sort_values("date")
        .reset_index(drop=True)
    )


def _read_plot_bars(vt_symbol: Any) -> tuple[pd.DataFrame, str]:
    bars, source = s798._read_plot_bars(vt_symbol)
    if not bars.empty:
        return bars, source
    tushare_bars = _read_tushare_contract_bars(vt_symbol)
    if not tushare_bars.empty:
        return tushare_bars, "tushare_daily"
    return pd.DataFrame(), "missing"


def _sample(blocks: pd.DataFrame) -> pd.DataFrame:
    if blocks.empty:
        return blocks.copy()
    eligible = blocks[pd.to_datetime(blocks["date"], errors="coerce").ge(START)].copy()
    if eligible.empty:
        eligible = blocks.copy()
    n = min(SAMPLE_N, len(eligible))
    sample = eligible.sample(n=n, random_state=RANDOM_SEED).sort_values("date").reset_index(drop=True)
    sample["sample_rank"] = np.arange(1, len(sample) + 1)
    return sample


def _plot_one(price_ax: plt.Axes, volume_ax: plt.Axes, row: pd.Series) -> dict[str, Any]:
    bars, bar_source = _read_plot_bars(row["vt_symbol"])
    if bars.empty:
        price_ax.axis("off")
        volume_ax.axis("off")
        price_ax.text(
            0.5,
            0.5,
            f"missing bars\n#{int(row['sample_rank'])} block{int(row['block_id'])}\n{row['vt_symbol']}\n{row['date']}",
            ha="center",
            va="center",
            fontsize=11,
            color="#991b1b",
        )
        return {"block_id": int(row["block_id"]), "bar_source": "missing", "missing_bars": 1}

    event_date = pd.Timestamp(row["date"]).normalize()
    event_idx = s752._event_index(bars, event_date)
    start = max(0, event_idx - PRE_BARS)
    end = min(len(bars), event_idx + POST_BARS + 1)
    window = bars.iloc[start:end].copy().reset_index(drop=True)
    local_event_idx = event_idx - start

    s752._plot_candles(price_ax, window)
    for ma, color in MA_LINES:
        price_ax.plot(window["close"].rolling(ma).mean().to_numpy(), color=color, linewidth=0.9, alpha=0.82)

    for idx in [local_event_idx - 2, local_event_idx - 1, local_event_idx]:
        if 0 <= idx < len(window):
            price_ax.axvspan(idx - 0.5, idx + 0.5, color="#fde68a", alpha=0.22)
    price_ax.axvline(local_event_idx, color="#1d4ed8", linewidth=1.25, alpha=0.95)
    close_value = float(window.loc[local_event_idx, "close"])
    price_ax.scatter([local_event_idx], [close_value], marker="x", s=44, color="#1d4ed8", zorder=5)

    tick_positions = np.linspace(0, max(0, len(window) - 1), num=min(8, len(window)), dtype=int)
    tick_labels = [pd.Timestamp(window.loc[pos, "date"]).strftime("%Y-%m-%d") for pos in tick_positions]
    price_ax.set_xticks(tick_positions)
    price_ax.set_xticklabels([])
    price_ax.grid(True, alpha=0.18, linewidth=0.6)
    price_ax.tick_params(axis="y", labelsize=8)
    price_ax.tick_params(axis="x", length=0)

    s752._plot_volume_oi(volume_ax, window)
    volume_ax.set_xticks(tick_positions)
    volume_ax.set_xticklabels(tick_labels, rotation=32, ha="right", fontsize=7)
    volume_ax.tick_params(axis="x", labelsize=7)

    title = (
        f"#{int(row['sample_rank'])} block{int(row['block_id'])} {row['vt_symbol']} "
        f"{row.get('signal', '')} {event_date:%Y-%m-%d} source={bar_source}"
    )
    subtitle = (
        f"blocked long because high[t-2]>{row['high_t_minus_2']:.2f}, "
        f"high[t-1]={row['high_t_minus_1']:.2f}, high[t]={row['high_t']:.2f}"
    )
    price_ax.set_title(title + "\n" + subtitle, fontsize=8.5, loc="left")
    price_ax.text(
        0.01,
        0.02,
        "blue x=blocked signal day | yellow=3-bar lower-high window | MA5/10/20/40 | lower: volume bars + OI line",
        transform=price_ax.transAxes,
        fontsize=7,
        color="#475569",
    )
    return {
        "block_id": int(row["block_id"]),
        "bar_source": bar_source,
        "missing_bars": 0,
        "chart_start": pd.Timestamp(window["date"].iloc[0]).strftime("%Y-%m-%d"),
        "chart_end": pd.Timestamp(window["date"].iloc[-1]).strftime("%Y-%m-%d"),
        "pre_bars_available": int(local_event_idx),
        "post_bars_available": int(len(window) - local_event_idx - 1),
    }


def _plot_pages(sample: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    paths: list[Path] = []
    records: list[dict[str, Any]] = []
    total_pages = int(np.ceil(len(sample) / PER_PAGE)) if len(sample) else 1
    for page in range(1, total_pages + 1):
        page_rows = sample.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig = plt.figure(figsize=(19, 4.75 * max(1, len(page_rows))), constrained_layout=True)
        outer = fig.add_gridspec(max(1, len(page_rows)), 1)
        for idx, (_, row) in enumerate(page_rows.iterrows()):
            inner = outer[idx].subgridspec(2, 1, height_ratios=[3.2, 1.0], hspace=0.02)
            price_ax = fig.add_subplot(inner[0])
            volume_ax = fig.add_subplot(inner[1], sharex=price_ax)
            record = _plot_one(price_ax, volume_ax, row)
            record["chart_page"] = page
            records.append(record)
        fig.suptitle(
            (
                "Stage801 random sample of Stage800 long lower-high blocked signals "
                f"(2018-start path, page {page}/{total_pages}, seed={RANDOM_SEED})"
            ),
            fontsize=15,
        )
        path = Path(str(CHART_PATH_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=170)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(records)


def _write_report(summary: pd.DataFrame, chart_paths: list[Path]) -> None:
    lines = [
        "# Stage801 lower-high拦截信号随机30笔K线图",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 起点：`{START:%Y-%m}`",
        f"- 随机种子：`{RANDOM_SEED}`",
        "- 样本来源：Stage800 lower-high block，使用最长 2018-01 起点重放并补齐合约/日期上下文。",
        "- 画图：每笔前后50根K线，含 MA5/10/20/40、成交量、OI。",
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=5),
        "",
        "## Charts",
        "",
        *[f"- `{path}`" for path in chart_paths],
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    blocks = _run_blocks()
    if blocks.empty:
        raise RuntimeError("no lower-high blocked signals with context")
    sample = _sample(blocks)
    chart_paths, chart_records = _plot_pages(sample)
    sample_with_chart = sample.merge(chart_records, on="block_id", how="left")

    blocks.to_csv(BLOCKS_PATH, index=False, encoding="utf-8-sig")
    sample_with_chart.to_csv(SAMPLE_PATH, index=False, encoding="utf-8-sig")

    summary = pd.DataFrame(
        [
            {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "source_version": "Stage800 long two-lower-high block",
                "source_start": START.strftime("%Y-%m"),
                "blocked_signal_count": int(len(blocks)),
                "eligible_signal_count": int(pd.to_datetime(blocks["date"], errors="coerce").ge(START).sum()),
                "sample_n": int(len(sample)),
                "random_seed": RANDOM_SEED,
                "missing_bar_count": int(chart_records["missing_bars"].sum()) if not chart_records.empty else 0,
                "daily_bar_source_count": int(chart_records["bar_source"].eq("daily").sum()) if not chart_records.empty else 0,
                "minute_aggregated_count": int(chart_records["bar_source"].eq("minute_aggregated").sum())
                if not chart_records.empty
                else 0,
                "tushare_daily_count": int(chart_records["bar_source"].eq("tushare_daily").sum())
                if not chart_records.empty
                else 0,
                "chart_paths": " | ".join(str(path) for path in chart_paths),
            }
        ]
    )
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")

    decision = {
        "stage": "Stage801",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "task": "random 30 K-line atlas for lower-high blocked signals",
        "strategy_changed": False,
        "backtest_changed": False,
        "source_start": START.strftime("%Y-%m"),
        "blocked_signal_count": int(len(blocks)),
        "sample_n": int(len(sample)),
        "random_seed": RANDOM_SEED,
        "overfit_reflection": (
            "Low for chart generation because this only visualizes pre-existing blocked signals. "
            "Any new rule derived from these charts would need predeclared multi-start validation."
        ),
        "continue_value": (
            "Useful as visual forensics to understand whether the blocked signals are obviously bad or include right-tail restarts."
        ),
        "outputs": {
            "blocks": str(BLOCKS_PATH),
            "sample": str(SAMPLE_PATH),
            "summary": str(SUMMARY_PATH),
            "charts": [str(path) for path in chart_paths],
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, chart_paths)

    print(summary.to_string(index=False))
    print(sample_with_chart[["sample_rank", "block_id", "date", "vt_symbol", "signal", "high_t_minus_2", "high_t_minus_1", "high_t", "chart_page"]].to_string(index=False))
    for path in chart_paths:
        print(f"chart={path}")


if __name__ == "__main__":
    main()
