from __future__ import annotations

from itertools import product
from pathlib import Path

import pandas as pd

from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_risk_4param_grid import (
    CAPITAL,
    SAVE_ARTIFACTS,
    _compute_score,
    _extract_risk_mode_counts,
    _safe_float,
    _valid_combo,
)

# Second-round refined grid for the current 1.2 / 0.9 open-interest regime.
# After the latest threshold change, base risk is active again and coarse-grid
# results concentrate around base=0.04, oi_up=0.05~0.06, vol_oi=0.06~0.08,
# oi_down=0.02~0.03.
BASE_GRID: list[float] = [0.040, 0.045]
OPEN_INTEREST_SURGE_GRID: list[float] = [0.050, 0.055, 0.060]
VOLUME_OPEN_INTEREST_SURGE_GRID: list[float] = [0.060, 0.070, 0.080]
OPEN_INTEREST_DECLINE_GRID: list[float] = [0.020, 0.025, 0.030]


def run_grid() -> pd.DataFrame:
    rows: list[dict[str, float | int]] = []
    combos: list[tuple[float, float, float, float]] = []
    for base_risk, oi_surge_risk, vol_oi_surge_risk, oi_decline_risk in product(
        BASE_GRID,
        OPEN_INTEREST_SURGE_GRID,
        VOLUME_OPEN_INTEREST_SURGE_GRID,
        OPEN_INTEREST_DECLINE_GRID,
    ):
        if not _valid_combo(
            base_risk=base_risk,
            oi_surge_risk=oi_surge_risk,
            vol_oi_surge_risk=vol_oi_surge_risk,
            oi_decline_risk=oi_decline_risk,
        ):
            continue
        combos.append((base_risk, oi_surge_risk, vol_oi_surge_risk, oi_decline_risk))

    print(f"[grid-refined] valid combos: {len(combos)}")

    for index, (base_risk, oi_surge_risk, vol_oi_surge_risk, oi_decline_risk) in enumerate(combos, start=1):
        combo_label: str = (
            f"base{base_risk:.3f}_"
            f"oi{oi_surge_risk:.3f}_"
            f"voloi{vol_oi_surge_risk:.3f}_"
            f"down{oi_decline_risk:.3f}"
        ).replace(".", "p")
        print(
            "[grid-refined] "
            f"{index}/{len(combos)} "
            f"base={base_risk:.3f}, oi_up={oi_surge_risk:.3f}, "
            f"vol_oi={vol_oi_surge_risk:.3f}, oi_down={oi_decline_risk:.3f}"
        )
        engine, _, statistics = run_backtest(
            risk_ratio=base_risk,
            risk_overrides={
                "risk_ratio_of_total_assets": base_risk,
                "risk_ratio_breakout": base_risk,
                "risk_ratio_ma_cross_breakout": base_risk,
                "risk_ratio_open_interest_surge": oi_surge_risk,
                "risk_ratio_volume_open_interest_surge": vol_oi_surge_risk,
                "risk_ratio_open_interest_decline": oi_decline_risk,
            },
            capital=CAPITAL,
            save_artifacts=SAVE_ARTIFACTS,
            file_prefix=f"qmt_roll_grid_refined_{combo_label}",
            chart_title=f"QMT Roll 4-Param Refined Grid {combo_label}",
        )

        row: dict[str, float | int] = {
            "base_risk": base_risk,
            "oi_surge_risk": oi_surge_risk,
            "vol_oi_surge_risk": vol_oi_surge_risk,
            "oi_decline_risk": oi_decline_risk,
            "end_balance": _safe_float(statistics.get("end_balance")),
            "total_return_pct": _safe_float(statistics.get("total_return")),
            "annual_return_pct": _safe_float(statistics.get("annual_return")),
            "max_dd_percent": _safe_float(statistics.get("max_ddpercent")),
            "max_drawdown": _safe_float(statistics.get("max_drawdown")),
            "sharpe_ratio": _safe_float(statistics.get("sharpe_ratio")),
            "return_drawdown_ratio": _safe_float(statistics.get("return_drawdown_ratio")),
            "win_ratio_pct": _safe_float(statistics.get("win_ratio")),
            "win_count": int(_safe_float(statistics.get("win_count"))),
            "round_trip_count": int(_safe_float(statistics.get("round_trip_count"))),
            "total_trade_count": int(_safe_float(statistics.get("total_trade_count"))),
        }
        row.update(_extract_risk_mode_counts(engine))
        row["score"] = _compute_score(row)
        rows.append(row)
        del engine

    result_df = pd.DataFrame(rows)
    result_df.sort_values(["score", "sharpe_ratio", "return_drawdown_ratio"], ascending=False, inplace=True)
    result_df["rank"] = range(1, len(result_df) + 1)
    ordered_columns = [
        "rank",
        "base_risk",
        "oi_surge_risk",
        "vol_oi_surge_risk",
        "oi_decline_risk",
        "score",
        "sharpe_ratio",
        "return_drawdown_ratio",
        "max_dd_percent",
        "total_return_pct",
        "annual_return_pct",
        "win_ratio_pct",
        "win_count",
        "round_trip_count",
        "total_trade_count",
        "count_regular",
        "count_breakout",
        "count_ma_cross_breakout",
        "count_active_base",
        "count_oi_surge",
        "count_vol_oi_surge",
        "count_oi_decline",
        "end_balance",
        "max_drawdown",
    ]
    return result_df[ordered_columns]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result_df = run_grid()
    summary_path: Path = (OUTPUT_DIR / "qmt_roll_risk_4param_grid_refined_summary.csv").resolve()
    result_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    print(f"[grid-refined] summary csv: {summary_path}")
    print("[grid-refined] top10:")
    print(
        result_df.head(10)[
            [
                "rank",
                "base_risk",
                "oi_surge_risk",
                "vol_oi_surge_risk",
                "oi_decline_risk",
                "score",
                "sharpe_ratio",
                "return_drawdown_ratio",
                "max_dd_percent",
                "total_return_pct",
                "win_ratio_pct",
                "count_active_base",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
