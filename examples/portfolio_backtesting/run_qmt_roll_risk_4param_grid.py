from __future__ import annotations

from itertools import product
from pathlib import Path
from typing import Any

import pandas as pd

from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_backtest import run_backtest

SAVE_ARTIFACTS: bool = False
CAPITAL: float = 200_000

# First-round coarse grid. Constrained to preserve the intended risk ladder.
BASE_GRID: list[float] = [0.03, 0.04, 0.05]
OPEN_INTEREST_SURGE_GRID: list[float] = [0.05, 0.06]
VOLUME_OPEN_INTEREST_SURGE_GRID: list[float] = [0.06, 0.08]
OPEN_INTEREST_DECLINE_GRID: list[float] = [0.01, 0.02, 0.03]


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _valid_combo(
    *,
    base_risk: float,
    oi_surge_risk: float,
    vol_oi_surge_risk: float,
    oi_decline_risk: float,
) -> bool:
    if not (vol_oi_surge_risk >= oi_surge_risk >= base_risk >= oi_decline_risk > 0):
        return False

    # Keep the ladder smooth during the first-round scan.
    if (vol_oi_surge_risk - oi_surge_risk) > 0.03:
        return False
    if (oi_surge_risk - base_risk) > 0.03:
        return False
    if (base_risk - oi_decline_risk) > 0.03:
        return False
    return True


def _compute_score(row: dict[str, Any]) -> float:
    sharpe_ratio: float = _safe_float(row.get("sharpe_ratio"))
    return_drawdown_ratio: float = _safe_float(row.get("return_drawdown_ratio"))
    total_return_pct: float = _safe_float(row.get("total_return_pct"))
    max_dd_percent: float = abs(_safe_float(row.get("max_dd_percent")))
    win_ratio_pct: float = _safe_float(row.get("win_ratio_pct"))

    # Favor robust risk-adjusted performance, with a mild preference for return and win rate.
    return (
        0.45 * return_drawdown_ratio
        + 0.30 * sharpe_ratio
        + 0.15 * (total_return_pct / 100.0)
        + 0.10 * (win_ratio_pct / 100.0)
        - 0.12 * (max_dd_percent / 100.0)
    )


def _extract_risk_mode_counts(engine: Any) -> dict[str, int]:
    strategy = getattr(engine, "strategy", None)
    diagnostics: list[dict[str, Any]] = getattr(strategy, "entry_risk_diagnostics", []) if strategy else []
    if not diagnostics:
        return {
            "count_regular": 0,
            "count_breakout": 0,
            "count_ma_cross_breakout": 0,
            "count_active_base": 0,
            "count_oi_surge": 0,
            "count_vol_oi_surge": 0,
            "count_oi_decline": 0,
        }

    df = pd.DataFrame(diagnostics)
    risk_mode_counts = df["risk_mode"].value_counts().to_dict()
    count_regular: int = int(risk_mode_counts.get("regular", 0))
    count_breakout: int = int(risk_mode_counts.get("breakout", 0))
    count_ma_cross_breakout: int = int(risk_mode_counts.get("ma_cross_breakout", 0))
    return {
        # The strategy's base/default branch is labeled "regular", not "default".
        "count_regular": count_regular,
        "count_breakout": count_breakout,
        "count_ma_cross_breakout": count_ma_cross_breakout,
        "count_active_base": count_regular + count_breakout + count_ma_cross_breakout,
        "count_oi_surge": int(risk_mode_counts.get("open_interest_surge", 0)),
        "count_vol_oi_surge": int(risk_mode_counts.get("volume_open_interest_surge", 0)),
        "count_oi_decline": int(risk_mode_counts.get("open_interest_decline", 0)),
    }


def run_grid() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
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

    print(f"[grid] valid combos: {len(combos)}")

    for index, (base_risk, oi_surge_risk, vol_oi_surge_risk, oi_decline_risk) in enumerate(combos, start=1):
        combo_label: str = (
            f"base{base_risk:.2f}_"
            f"oi{oi_surge_risk:.2f}_"
            f"voloi{vol_oi_surge_risk:.2f}_"
            f"down{oi_decline_risk:.2f}"
        ).replace(".", "p")
        print(
            "[grid] "
            f"{index}/{len(combos)} "
            f"base={base_risk:.2f}, oi_up={oi_surge_risk:.2f}, "
            f"vol_oi={vol_oi_surge_risk:.2f}, oi_down={oi_decline_risk:.2f}"
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
            file_prefix=f"qmt_roll_grid_{combo_label}",
            chart_title=f"QMT Roll 4-Param Grid {combo_label}",
        )

        row: dict[str, Any] = {
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
    summary_path: Path = (OUTPUT_DIR / "qmt_roll_risk_4param_grid_summary.csv").resolve()
    result_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    print(f"[grid] summary csv: {summary_path}")
    print("[grid] top10:")
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
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
