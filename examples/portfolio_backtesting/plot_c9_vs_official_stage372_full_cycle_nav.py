from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


BASE_DIR = Path(__file__).resolve().parent / "backtest_outputs"
C9_PATH = (
    BASE_DIR
    / "qmt_roll_stage863_stage847_c10_budget_lock_engine_curve_stage863_stage847_c10_budget_lock_engine_v1.csv"
)
OFFICIAL_PATH = (
    BASE_DIR / "qmt_roll_stage744_official_monthly_start_audit_curves_stage744_official_monthly_start_audit_v1.csv"
)
OUT_PNG = BASE_DIR / "qmt_roll_c9_vs_official_stage372_full_cycle_nav_20260615.png"
OUT_CSV = BASE_DIR / "qmt_roll_c9_vs_official_stage372_full_cycle_nav_20260615.csv"

C9_VARIANT = "stage847_stage819_c4_05r_stop_retry_once_2018"
OFFICIAL_WINDOW = "mstart_2020_01"


def load_c9_curve() -> tuple[list[datetime], list[float]]:
    dates: list[datetime] = []
    navs: list[float] = []
    with C9_PATH.open(newline="") as f:
        reader = csv.DictReader(f)
        date_key = reader.fieldnames[0]
        for row in reader:
            if row["variant"] != C9_VARIANT:
                continue
            dates.append(datetime.strptime(row[date_key], "%Y-%m-%d"))
            navs.append(float(row["rebased_nav"]))
    return dates, navs


def load_official_curve() -> tuple[list[datetime], list[float]]:
    dates: list[datetime] = []
    navs: list[float] = []
    with OFFICIAL_PATH.open(newline="") as f:
        reader = csv.DictReader(f)
        date_key = reader.fieldnames[0]
        for row in reader:
            if row["window_name"] != OFFICIAL_WINDOW:
                continue
            dates.append(datetime.strptime(row[date_key], "%Y-%m-%d"))
            navs.append(float(row["rebased_nav"]))
    return dates, navs


def write_merged_csv(
    c9_dates: list[datetime],
    c9_navs: list[float],
    official_dates: list[datetime],
    official_navs: list[float],
) -> None:
    c9_map = {d.strftime("%Y-%m-%d"): v for d, v in zip(c9_dates, c9_navs)}
    official_map = {
        d.strftime("%Y-%m-%d"): v for d, v in zip(official_dates, official_navs)
    }
    all_dates = sorted(set(c9_map) | set(official_map))
    with OUT_CSV.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "c9_nav", "official_stage372_nav"])
        for date_str in all_dates:
            writer.writerow(
                [date_str, c9_map.get(date_str, ""), official_map.get(date_str, "")]
            )


def plot_curves(
    c9_dates: list[datetime],
    c9_navs: list[float],
    official_dates: list[datetime],
    official_navs: list[float],
) -> None:
    fig, ax = plt.subplots(figsize=(16, 8), dpi=160)
    ax.plot(
        c9_dates,
        c9_navs,
        label="Stage863 / C9",
        linewidth=2.2,
        color="#1f77b4",
    )
    ax.plot(
        official_dates,
        official_navs,
        label="Official Stage372 / 20w live default",
        linewidth=2.2,
        color="#d62728",
    )
    ax.set_title("C9 vs Official Stage372 Full-Cycle NAV")
    ax.set_ylabel("Normalized NAV")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left")
    ax.text(
        0.01,
        0.01,
        (
            "Both lines are rebased to NAV=1.0. "
            "C9 full cycle: 2018-01-02 to 2026-05-29. "
            "Official Stage372 full cycle: 2020-01-02 to 2026-04-30."
        ),
        transform=ax.transAxes,
        fontsize=9,
        va="bottom",
        ha="left",
        bbox={
            "boxstyle": "round,pad=0.3",
            "facecolor": "white",
            "alpha": 0.85,
            "edgecolor": "#cccccc",
        },
    )
    fig.tight_layout()
    fig.savefig(OUT_PNG, bbox_inches="tight")


def main() -> None:
    c9_dates, c9_navs = load_c9_curve()
    official_dates, official_navs = load_official_curve()
    if not c9_dates:
        raise RuntimeError("C9 curve not found in Stage863 output")
    if not official_dates:
        raise RuntimeError("Official Stage372 curve not found in Stage744 output")
    write_merged_csv(c9_dates, c9_navs, official_dates, official_navs)
    plot_curves(c9_dates, c9_navs, official_dates, official_navs)
    print(f"WROTE_PNG={OUT_PNG}")
    print(f"WROTE_CSV={OUT_CSV}")
    print(
        "C9_RANGE="
        f"{c9_dates[0].date()}..{c9_dates[-1].date()} LAST_NAV={c9_navs[-1]:.4f}"
    )
    print(
        "OFFICIAL_RANGE="
        f"{official_dates[0].date()}..{official_dates[-1].date()} "
        f"LAST_NAV={official_navs[-1]:.4f}"
    )


if __name__ == "__main__":
    main()
