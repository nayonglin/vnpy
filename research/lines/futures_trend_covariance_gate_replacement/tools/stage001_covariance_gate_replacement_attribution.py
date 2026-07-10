#!/usr/bin/env python3
"""Read-only attribution for the Stage001 correlation-gate replacement A/B/C."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
OUT = (
    ROOT
    / "research"
    / "lines"
    / "futures_trend_covariance_gate_replacement"
    / "outputs"
    / "stage001_covariance_gate_replacement_engine"
)
PREFIX = "cov_gate_replacement_stage001_covariance_gate_replacement_engine"
TAG = "stage001_covariance_gate_replacement_engine_v1"

VERSIONS = (
    "a_current_c9_legacy_corr_gate",
    "b_current_c9_no_corr_gate",
    "c_current_c9_marginal_cov_replacement",
)


def _path(version: str, suffix: str) -> Path:
    return OUT / f"{PREFIX}_{version}_{suffix}_{TAG}.csv.gz"


def _annual_equity_change() -> pd.DataFrame:
    curves = pd.read_csv(OUT / f"{PREFIX}_curves_{TAG}.csv.gz", encoding="utf-8-sig")
    curves["date"] = pd.to_datetime(curves["date"], errors="raise")
    curves["year"] = curves["date"].dt.year
    rows: list[dict[str, float | int | str]] = []
    for version, data in curves.groupby("version", sort=False):
        data = data.sort_values("date")
        prior_equity = 150_000.0
        for year, part in data.groupby("year", sort=True):
            end_equity = float(pd.to_numeric(part["account_equity_for_metrics"], errors="raise").iloc[-1])
            rows.append(
                {
                    "version": version,
                    "year": int(year),
                    "start_equity": prior_equity,
                    "end_equity": end_equity,
                    "equity_change": end_equity - prior_equity,
                    "return_on_year_start_pct": (end_equity / prior_equity - 1.0) * 100.0,
                }
            )
            prior_equity = end_equity
    result = pd.DataFrame(rows)
    pivot = result.pivot(index="year", columns="version", values="equity_change").reset_index()
    pivot["c_minus_a_equity_change"] = (
        pivot["c_current_c9_marginal_cov_replacement"]
        - pivot["a_current_c9_legacy_corr_gate"]
    )
    pivot["b_minus_a_equity_change"] = (
        pivot["b_current_c9_no_corr_gate"] - pivot["a_current_c9_legacy_corr_gate"]
    )
    return result.merge(
        pivot[["year", "c_minus_a_equity_change", "b_minus_a_equity_change"]],
        on="year",
        how="left",
    )


def _closed_product_pnl() -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for version in VERSIONS:
        frame = pd.read_csv(_path(version, "closed_lots"), encoding="utf-8-sig")
        frame["realized_pnl"] = pd.to_numeric(frame["realized_pnl"], errors="coerce").fillna(0.0)
        grouped = frame.groupby("product", as_index=False).agg(
            realized_pnl=("realized_pnl", "sum"),
            closed_lots=("lot_id", "count"),
        )
        grouped["version"] = version
        parts.append(grouped)
    long = pd.concat(parts, ignore_index=True, sort=False)
    pnl = long.pivot(index="product", columns="version", values="realized_pnl").fillna(0.0)
    lots = long.pivot(index="product", columns="version", values="closed_lots").fillna(0.0)
    result = pnl.add_suffix("_pnl").join(lots.add_suffix("_closed_lots")).reset_index()
    result["c_minus_a_realized_pnl"] = (
        result[f"{VERSIONS[2]}_pnl"] - result[f"{VERSIONS[0]}_pnl"]
    )
    result["b_minus_a_realized_pnl"] = (
        result[f"{VERSIONS[1]}_pnl"] - result[f"{VERSIONS[0]}_pnl"]
    )
    return result.sort_values("c_minus_a_realized_pnl")


def _entry_reduction(version: str, mode: str) -> pd.DataFrame:
    frame = pd.read_csv(_path(version, "entry_candidates"), encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    frame["year"] = frame["date"].dt.year
    opened = pd.to_numeric(frame["is_opened"], errors="coerce").fillna(0).eq(1)
    if mode == "legacy":
        weight = pd.to_numeric(
            frame["same_direction_correlation_gate_weight"], errors="coerce"
        ).fillna(1.0)
        before = pd.to_numeric(frame["selected_volume_ungated"], errors="coerce").fillna(0.0)
        after = pd.to_numeric(frame["selected_volume"], errors="coerce").fillna(0.0)
        reduced = weight.lt(1.0 - 1e-12)
    else:
        before = pd.to_numeric(
            frame["marginal_covariance_selected_volume_before"], errors="coerce"
        ).fillna(0.0)
        after = pd.to_numeric(
            frame["marginal_covariance_selected_volume_after"], errors="coerce"
        ).fillna(0.0)
        reduced = pd.to_numeric(
            frame["marginal_covariance_volume_reduced"], errors="coerce"
        ).fillna(0).gt(0)
    data = frame[opened & reduced].copy()
    data["volume_before"] = before[opened & reduced]
    data["volume_after"] = after[opened & reduced]
    data["volume_reduction"] = data["volume_before"] - data["volume_after"]
    result = (
        data.groupby(["year", "product_vt_symbol"], as_index=False)
        .agg(
            reduced_open_rows=("date", "count"),
            volume_before=("volume_before", "sum"),
            volume_after=("volume_after", "sum"),
            volume_reduction=("volume_reduction", "sum"),
        )
        .sort_values(["year", "volume_reduction"], ascending=[True, False])
    )
    result["version"] = version
    result["mode"] = mode
    return result


def build() -> None:
    annual = _annual_equity_change()
    products = _closed_product_pnl()
    reductions = pd.concat(
        [
            _entry_reduction(VERSIONS[0], "legacy"),
            _entry_reduction(VERSIONS[2], "marginal"),
        ],
        ignore_index=True,
        sort=False,
    )
    annual.to_csv(OUT / f"{PREFIX}_annual_attribution_{TAG}.csv", index=False, encoding="utf-8-sig")
    products.to_csv(OUT / f"{PREFIX}_product_attribution_{TAG}.csv", index=False, encoding="utf-8-sig")
    reductions.to_csv(OUT / f"{PREFIX}_entry_reduction_attribution_{TAG}.csv", index=False, encoding="utf-8-sig")
    print(annual.to_string(index=False))
    print(products.head(15).to_string(index=False))
    print(reductions[reductions["year"].eq(2022)].to_string(index=False))


if __name__ == "__main__":
    build()
