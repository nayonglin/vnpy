"""Plot two completed Stage042 research cash curves; never rerun the strategy.

Invoke only after root accepts the independent review and names the final source
directory. The PNG and its receipt are cache_or_visualization, not source assets.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, PercentFormatter
import pandas as pd


WINDOW_ID = "primary_2020"
SCENARIOS = ("base", "stress")
INITIAL_CAPITAL = 1_000_000.0
END_DATE = "2026-10-16"
MARK = "native_close_research_not_settlement"
PNG_NAME = "primary_2020_equity_drawdown.png"


def binding(path: Path) -> dict:
    content = path.read_bytes()
    return {
        "path": str(path.resolve()),
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def read_account(experiment: Path, scenario: str) -> tuple[pd.DataFrame, dict, list[dict]]:
    account_id = f"{scenario}__{WINDOW_ID}"
    directory = experiment / "cash" / account_id
    daily_path, summary_path = directory / "daily.csv.gz", directory / "summary.json"
    summary = json.loads(summary_path.read_text())
    expected = {
        "account_id": account_id,
        "window_id": WINDOW_ID,
        "scenario": scenario,
        "initial_capital": INITIAL_CAPITAL,
        "requested_start": "2020-01-01",
        "source_end": END_DATE,
        "mark": MARK,
        "production_qualified": False,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            raise ValueError(f"{account_id}: summary {key} differs from fixed plotting scope")
    frame = pd.read_csv(
        daily_path,
        usecols=["account_id", "window_id", "scenario", "date", "equity"],
        dtype={"account_id": str, "window_id": str, "scenario": str, "date": str},
    )
    if frame.empty or len(frame) != summary["source_dates"]:
        raise ValueError(f"{account_id}: missing daily rows or source_dates mismatch")
    for key, value in (("account_id", account_id), ("window_id", WINDOW_ID), ("scenario", scenario)):
        if not frame[key].eq(value).all():
            raise ValueError(f"{account_id}: mixed daily identities")
    dates = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="raise")
    if dates.duplicated().any() or not dates.is_monotonic_increasing:
        raise ValueError(f"{account_id}: dates must be unique and already ordered")
    if frame["date"].iloc[0] != summary["source_start"] or frame["date"].iloc[-1] != END_DATE:
        raise ValueError(f"{account_id}: daily date endpoints differ from summary")
    if (dates < pd.Timestamp("2020-01-01")).any() or (dates > pd.Timestamp(END_DATE)).any():
        raise ValueError(f"{account_id}: daily row outside primary scope")
    equity = pd.to_numeric(frame["equity"], errors="raise")
    if not equity.map(math.isfinite).all():
        raise ValueError(f"{account_id}: nonfinite equity")
    # Include initial capital in the running peak even if the first day loses.
    peaks = equity.cummax().clip(lower=INITIAL_CAPITAL)
    drawdown = equity / peaks - 1.0
    if not math.isclose(float(equity.iloc[-1]), float(summary["ending_equity"]), rel_tol=0, abs_tol=1e-6):
        raise ValueError(f"{account_id}: ending equity differs from summary")
    minimum_dd = min(0.0, float(drawdown.min())) * 100.0
    if not math.isclose(minimum_dd, float(summary["max_drawdown_pct"]), rel_tol=0, abs_tol=1e-7):
        raise ValueError(f"{account_id}: initial-capital-inclusive drawdown differs from summary")
    frame = frame.assign(plot_date=dates, equity=equity, drawdown=drawdown)
    return frame, summary, [binding(daily_path), binding(summary_path)]


def plot_completed(experiment: Path, output_dir: Path) -> dict:
    manifest_path = experiment / "manifest.json"
    terminal_path = experiment / "actual_terminal.json"
    manifest = json.loads(manifest_path.read_text())
    terminal = json.loads(terminal_path.read_text())
    if manifest.get("status") != "completed" or terminal.get("status") != "completed" or terminal.get("exit_code") != 0:
        raise ValueError("Stage042 has no completed manifest/terminal")
    if manifest.get("completed_research_cash_accounts") != 18:
        raise ValueError("Stage042 did not finish the fixed 18 accounts")
    frames, summaries, source_bindings = {}, {}, [binding(manifest_path), binding(terminal_path)]
    for scenario in SCENARIOS:
        frames[scenario], summaries[scenario], inputs = read_account(experiment, scenario)
        source_bindings.extend(inputs)
    if not frames["base"]["date"].equals(frames["stress"]["date"]):
        raise ValueError("Base and stress source dates differ")
    png_path, receipt_path = output_dir / PNG_NAME, output_dir / "plot_read_receipt.json"
    if png_path.exists() or receipt_path.exists():
        raise FileExistsError("Visualization already exists; do not silently overwrite a frozen plot")
    output_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    figure, (equity_ax, dd_ax) = plt.subplots(
        2, 1, figsize=(13, 7.8), sharex=True,
        gridspec_kw={"height_ratios": [2, 1], "hspace": 0.13},
    )
    colors = {"base": "#1c6ba0", "stress": "#d8781d"}
    for scenario in SCENARIOS:
        frame, summary = frames[scenario], summaries[scenario]
        label = f"{scenario.capitalize()} | final CNY {summary['ending_equity']:,.0f}"
        equity_ax.plot(frame["plot_date"], frame["equity"], color=colors[scenario], lw=1.65, label=label)
        dd_ax.plot(frame["plot_date"], frame["drawdown"], color=colors[scenario], lw=1.15,
                   label=f"{scenario.capitalize()} | max DD {summary['max_drawdown_pct']:.2f}%")
    equity_ax.axhline(INITIAL_CAPITAL, color="#6b7280", lw=0.8, ls="--", alpha=0.65)
    equity_ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value / 1_000_000:.2f}"))
    equity_ax.set_ylabel("Equity (CNY millions)")
    equity_ax.legend(loc="upper left", frameon=False)
    dd_ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    dd_ax.set_ylabel("Drawdown")
    dd_ax.axhline(0, color="#6b7280", lw=0.6)
    dd_ax.legend(loc="lower left", frameon=False)
    for axis in (equity_ax, dd_ax):
        axis.grid(axis="y", color="#d5dce3", alpha=0.6, lw=0.6)
        axis.set_axisbelow(True)
    dd_ax.xaxis.set_major_locator(mdates.YearLocator())
    dd_ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    dd_ax.set_xlim(pd.Timestamp("2020-01-01"), pd.Timestamp(END_DATE))
    figure.suptitle("Cross-day long-only reference accounts | 2020 onward", x=0.085, y=0.97, ha="left", fontsize=15, weight="bold")
    figure.text(0.085, 0.925,
                f"Research assumptions | Initial capital CNY 1,000,000 | Base and stress | Through {END_DATE}",
                ha="left", fontsize=10, color="#4b5563")
    footer = "Open positions use native-contract close research marks; not broker settlement. No AI or pyramiding."
    stale = {s: int(summaries[s].get("stale_positions", 0)) for s in SCENARIOS}
    if any(stale.values()):
        footer += f"  Final stale positions: base {stale['base']}, stress {stale['stress']} (last known marks)."
    figure.text(0.085, 0.035, footer, ha="left", fontsize=8.2, color="#4b5563", wrap=True)
    figure.subplots_adjust(left=0.085, right=0.975, bottom=0.105, top=0.875)
    figure.savefig(png_path, dpi=170, facecolor="white")
    plt.close(figure)
    receipt = {
        "schema": "stage044_research_curve_plot_read_receipt_v1",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "role": "cache_or_visualization", "reproducibility_required": False,
        "source_bindings": source_bindings, "source_code": binding(Path(__file__)),
        "plot": binding(png_path), "window_id": WINDOW_ID, "source_end": END_DATE,
        "initial_capital": INITIAL_CAPITAL, "drawdown_includes_initial_capital_peak": True,
        "mark": MARK, "production_qualified": False,
        "checks": {
            "completed_18_account_manifest": True, "unique_ordered_equal_dates": True,
            "ending_equity_matches_summaries": True, "drawdown_matches_summaries": True,
        },
        "curve_counts": {s: len(frames[s]) for s in SCENARIOS},
        "stale_positions": stale,
        "strategy_runs": 0, "model_fits": 0, "sql_queries": 0,
    }
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {"status": "completed", "role": "cache_or_visualization", "plot": binding(png_path), "receipt": binding(receipt_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", required=True, type=Path, help="Root-approved final Stage042 experiment directory")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "outputs/stage044_cross_session_decision/visualization")
    args = parser.parse_args()
    print(json.dumps(plot_completed(args.experiment.resolve(), args.output_dir.resolve()), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
