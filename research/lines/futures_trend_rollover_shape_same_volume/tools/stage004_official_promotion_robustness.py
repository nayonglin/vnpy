from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import stage001_rollover_shape_same_volume_ac as s1
import stage002_rollover_shape_shrink_to_allowed_abc as s2


LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage004"

SUMMARY_PATH = OUTPUT_DIR / "stage004_window_summary.csv"
COMPARISON_PATH = OUTPUT_DIR / "stage004_window_comparison.csv"
DECISION_PATH = OUTPUT_DIR / "stage004_decision.json"

DATA_END = pd.Timestamp("2026-05-29")

# These windows and gates are frozen before the Stage004 runs.  The start-year
# windows test independent cold starts; the one-year windows are the already
# known C9 weak/recent windows and are not selected from candidate PnL.
WINDOWS: tuple[dict[str, Any], ...] = (
    *(
        {
            "window_id": f"start_{year}",
            "group": "start_year",
            "start": pd.Timestamp(f"{year}-01-01"),
            "end": DATA_END,
        }
        for year in range(2019, 2026)
    ),
    {
        "window_id": "weak_2018_01_1y",
        "group": "weak_one_year",
        "start": pd.Timestamp("2018-01-01"),
        "end": pd.Timestamp("2018-12-31"),
    },
    {
        "window_id": "weak_2018_06_1y",
        "group": "weak_one_year",
        "start": pd.Timestamp("2018-06-01"),
        "end": pd.Timestamp("2019-05-31"),
    },
    {
        "window_id": "weak_2022_01_1y",
        "group": "weak_one_year",
        "start": pd.Timestamp("2022-01-01"),
        "end": pd.Timestamp("2022-12-31"),
    },
    {
        "window_id": "recent_2025_06_1y",
        "group": "weak_one_year",
        "start": pd.Timestamp("2025-06-01"),
        "end": DATA_END,
    },
)

ARMS: tuple[dict[str, Any], ...] = (
    {
        "arm": "A",
        "candidate": False,
        "history_mode": "target_contract_only",
        "label": "A: 当前正式 C9/15万",
    },
    {
        "arm": "C",
        "candidate": True,
        "history_mode": "backwards_ratio_continuous",
        "label": "C: 正式基线 + 换月连续历史形态续仓",
    },
)


def _run_window(
    metadata: dict[str, Any],
    window: dict[str, Any],
    arm: dict[str, Any],
) -> pd.DataFrame:
    old_start, old_end = s1.START, s1.END
    profile = f"stage004_{arm['arm']}_{window['window_id']}"
    try:
        s1.START = pd.Timestamp(window["start"])
        s1.END = pd.Timestamp(window["end"])
        summary, _, _ = s1._run_arm(
            profile_name=profile,
            candidate=bool(arm["candidate"]),
            metadata=metadata,
            volume_policy="shrink_to_allowed",
            history_mode=str(arm["history_mode"]),
            label=str(arm["label"]),
        )
    finally:
        s1.START, s1.END = old_start, old_end

    result = summary.copy()
    result["window_id"] = str(window["window_id"])
    result["window_group"] = str(window["group"])
    result["requested_start"] = str(pd.Timestamp(window["start"]).date())
    result["requested_end"] = str(pd.Timestamp(window["end"]).date())
    result["promotion_arm"] = str(arm["arm"])
    start_month = pd.Timestamp(window["start"]).strftime("%Y-%m")
    result["window_name"] = str(window["window_id"])
    result["window_label"] = (
        f"{pd.Timestamp(window['start']).date()} independent start to "
        f"{pd.Timestamp(window['end']).date()}"
    )
    result["requested_start_month"] = start_month
    result["start_month"] = start_month
    result["start_year"] = int(pd.Timestamp(window["start"]).year)
    result["start_month_num"] = int(pd.Timestamp(window["start"]).month)
    return result


def _validate_summary(summary: pd.DataFrame) -> None:
    expected_pairs = {
        (str(window["window_id"]), str(arm["arm"]))
        for window in WINDOWS
        for arm in ARMS
    }
    actual_pairs = set(
        zip(
            summary.get("window_id", pd.Series(dtype="object")).astype(str),
            summary.get("promotion_arm", pd.Series(dtype="object")).astype(str),
            strict=False,
        )
    )
    if len(summary) != len(expected_pairs) or actual_pairs != expected_pairs:
        raise RuntimeError("stage004_window_arm_identity_mismatch")
    critical = [
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "account_survival_pass",
        "broker10_100_pass",
    ]
    if summary[critical].apply(pd.to_numeric, errors="coerce").isna().any().any():
        raise RuntimeError("stage004_critical_metric_missing")


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_id, group in summary.groupby("window_id", sort=False):
        by_arm = group.set_index("promotion_arm")
        a = by_arm.loc["A"]
        c = by_arm.loc["C"]
        rows.append(
            {
                "window_id": window_id,
                "window_group": str(c["window_group"]),
                "requested_start": str(c["requested_start"]),
                "requested_end": str(c["requested_end"]),
                "A_return_pct": float(a["total_return_pct"]),
                "C_return_pct": float(c["total_return_pct"]),
                "delta_return_pct": float(c["total_return_pct"] - a["total_return_pct"]),
                "A_max_dd_pct": float(a["max_dd_pct"]),
                "C_max_dd_pct": float(c["max_dd_pct"]),
                "dd_worsening_pp": max(0.0, float(a["max_dd_pct"] - c["max_dd_pct"])),
                "A_sharpe": float(a["sharpe"]),
                "C_sharpe": float(c["sharpe"]),
                "delta_sharpe": float(c["sharpe"] - a["sharpe"]),
                "A_slippage": float(a["total_slippage"]),
                "C_slippage": float(c["total_slippage"]),
                "A_trades": int(a["total_trade_count"]),
                "C_trades": int(c["total_trade_count"]),
                "A_survival_pass": int(a["account_survival_pass"]),
                "C_survival_pass": int(c["account_survival_pass"]),
                "A_broker100_pass": int(a["broker10_100_pass"]),
                "C_broker100_pass": int(c["broker10_100_pass"]),
                "return_win": int(float(c["total_return_pct"]) >= float(a["total_return_pct"])),
                "return_noninferior_5pp": int(
                    float(c["total_return_pct"]) >= float(a["total_return_pct"]) - 5.0
                ),
                "dd_noninferior_2pp": int(
                    max(0.0, float(a["max_dd_pct"] - c["max_dd_pct"])) <= 2.0
                ),
                "sharpe_noninferior_005": int(
                    float(c["sharpe"]) >= float(a["sharpe"]) - 0.05
                ),
            }
        )
    return pd.DataFrame(rows)


def _decision(comparison: pd.DataFrame) -> dict[str, Any]:
    start_year = comparison[comparison["window_group"].eq("start_year")]
    weak = comparison[comparison["window_group"].eq("weak_one_year")]
    gates = {
        "all_candidate_survival": bool(comparison["C_survival_pass"].eq(1).all()),
        "candidate_broker100_fail_count_not_above_A": int(
            comparison["C_broker100_pass"].eq(0).sum()
        )
        <= int(comparison["A_broker100_pass"].eq(0).sum()),
        "all_windows_dd_noninferior_2pp": bool(comparison["dd_noninferior_2pp"].eq(1).all()),
        "all_windows_sharpe_noninferior_005": bool(
            comparison["sharpe_noninferior_005"].eq(1).all()
        ),
        "start_year_return_win_rate_ge_50pct": bool(start_year["return_win"].mean() >= 0.50),
        "start_year_median_return_delta_nonnegative": bool(
            start_year["delta_return_pct"].median() >= 0.0
        ),
        "weak_windows_noninferior_5pp_at_least_3of4": bool(
            int(weak["return_noninferior_5pp"].sum()) >= 3
        ),
        "aggregate_slippage_not_above_5pct": bool(
            comparison["C_slippage"].sum() <= comparison["A_slippage"].sum() * 1.05
        ),
    }
    promotion_pass = bool(all(gates.values()))
    return {
        "line_id": "futures_trend_rollover_shape_same_volume",
        "stage": "Stage004",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "candidate": {
            "enable_rollover_shape_same_volume_reopen": True,
            "rollover_shape_history_mode": "backwards_ratio_continuous",
            "rollover_shape_volume_policy": "shrink_to_allowed",
        },
        "predeclared_windows": [
            {
                "window_id": str(item["window_id"]),
                "group": str(item["group"]),
                "start": str(pd.Timestamp(item["start"]).date()),
                "end": str(pd.Timestamp(item["end"]).date()),
            }
            for item in WINDOWS
        ],
        "predeclared_gates": gates,
        "promotion_pass": promotion_pass,
        "decision": (
            "promote_rollover_continuation_to_official_config"
            if promotion_pass
            else "do_not_promote_rollover_continuation"
        ),
        "window_comparison": comparison.to_dict(orient="records"),
        "order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    frames: list[pd.DataFrame] = []
    for index, window in enumerate(WINDOWS, start=1):
        for arm in ARMS:
            print(
                f"[stage004] {index}/{len(WINDOWS)} {window['window_id']} arm={arm['arm']}",
                flush=True,
            )
            frames.append(_run_window(metadata, window, arm))

    summary = pd.concat(frames, ignore_index=True, sort=False)
    _validate_summary(summary)
    comparison = _comparison(summary)
    decision = _decision(comparison)
    s2._publish_outputs_atomically(
        OUTPUT_DIR,
        {
            SUMMARY_PATH.name: summary,
            COMPARISON_PATH.name: comparison,
        },
        decision,
        decision_filename=DECISION_PATH.name,
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
