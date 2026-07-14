from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "research" / "lines" / "futures_trend_tight_stop_quality_sizing" / "outputs" / "stage004_underwater_only_quality_transfer"
TAG = "stage004_underwater_only_quality_transfer_v1"
CURVES = OUT / f"tight_stop_quality_stage004_curves_{TAG}.csv.gz"
SUMMARY = OUT / f"tight_stop_quality_stage004_summary_{TAG}.csv"
CHART = OUT / f"tight_stop_quality_stage004_repaired_four_anchor_detail_{TAG}.png"


def main() -> None:
    curves = pd.read_csv(CURVES)
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce")
    summary = pd.read_csv(SUMMARY).set_index(["requested_start_month", "variant"])
    starts = sorted(curves["requested_start_month"].astype(str).unique())
    with plt.style.context("default"):
        fig, axes = plt.subplots(len(starts), 2, figsize=(18, 13), constrained_layout=True)
        fig.patch.set_facecolor("white")
        for row_index, start in enumerate(starts):
            official = curves[(curves["requested_start_month"].astype(str) == start) & curves["variant"].eq("A_official")].sort_values("date")
            candidate = curves[(curves["requested_start_month"].astype(str) == start) & curves["variant"].eq("C_stage004")].sort_values("date")
            a_summary = summary.loc[(start, "A_official")]
            c_summary = summary.loc[(start, "C_stage004")]
            nav_axis, dd_axis = axes[row_index]
            for axis in (nav_axis, dd_axis):
                axis.set_facecolor("white")
                axis.grid(color="#d1d5db", alpha=0.55, linewidth=0.7)
                axis.tick_params(labelsize=8)
            nav_axis.plot(official["date"], official["nav"], color="#374151", linewidth=1.5, label="Official")
            nav_axis.plot(candidate["date"], candidate["nav"], color="#0f766e", linewidth=1.5, label="Stage004")
            nav_axis.axhline(1.0, color="#9ca3af", linestyle=":", linewidth=0.8)
            nav_axis.set_ylabel(f"{start}\nNAV", fontsize=9)
            nav_axis.set_title(
                f"Return: {a_summary.total_return_pct:.1f}% -> {c_summary.total_return_pct:.1f}%",
                fontsize=10,
            )
            dd_axis.plot(official["date"], official["drawdown_pct"], color="#374151", linewidth=1.3, label="Official")
            dd_axis.plot(candidate["date"], candidate["drawdown_pct"], color="#0f766e", linewidth=1.3, label="Stage004")
            dd_axis.axhline(0.0, color="#9ca3af", linestyle=":", linewidth=0.8)
            dd_axis.set_ylabel("Drawdown %", fontsize=9)
            dd_axis.set_title(
                f"Max DD: {a_summary.max_dd_pct:.1f}% -> {c_summary.max_dd_pct:.1f}%",
                fontsize=10,
            )
        axes[0, 0].legend(loc="upper left", frameon=False, ncol=2, fontsize=9)
        axes[0, 1].legend(loc="lower left", frameon=False, ncol=2, fontsize=9)
        axes[-1, 0].set_xlabel("Date")
        axes[-1, 1].set_xlabel("Date")
        fig.suptitle(
            "Stage004 repaired execution: four-anchor NAV and drawdown (exploratory, not promotion-ready)",
            fontsize=15,
        )
        fig.savefig(CHART, dpi=170, facecolor="white", transparent=False)
        plt.close(fig)
    image = Image.open(CHART).convert("RGB")
    image.save(CHART)
    print(CHART)


if __name__ == "__main__":
    main()
