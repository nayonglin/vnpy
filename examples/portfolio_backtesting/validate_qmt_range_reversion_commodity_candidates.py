from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

SCOUT_TAG: str = "range_reversion_full_market_universe_scout_v1"
TOP_INPUT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_full_market_universe_scout_top_candidates_{SCOUT_TAG}.csv"
YEAR_INPUT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_full_market_universe_scout_year_direction_{SCOUT_TAG}.csv"

MODEL_TAG: str = "range_reversion_commodity_candidate_validation_v1"
VALIDATION_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_commodity_candidate_validation_{MODEL_TAG}.csv"
WINDOW_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_commodity_candidate_windows_{MODEL_TAG}.csv"
UNIVERSE_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_commodity_candidate_universe_{MODEL_TAG}.csv"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_commodity_candidate_summary_{MODEL_TAG}.json"
REPORT_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_commodity_candidate_report_{MODEL_TAG}.md"

WINDOWS: dict[str, tuple[int, int]] = {
    "early_2020_2022": (2020, 2022),
    "mid_2023_2024": (2023, 2024),
    "stress_2024_2025": (2024, 2025),
    "recent_2025_2026": (2025, 2026),
}

EXCLUDED_EXCHANGES: set[str] = {"CFFEX"}
MIN_RECENT_BARS: int = 120
MIN_CORE_SIGNALS: int = 50
MIN_CORE_YEARS: int = 5
MIN_CORE_POSITIVE_YEAR_RATE: float = 0.75
MIN_CORE_AVG_FWD_5D_ATR: float = 0.25
MIN_CORE_POSITIVE_5D_RATE: float = 0.58
MAX_CORE_BAD_TAIL_5D_RATE: float = 0.22
MAX_CORE_YEAR_SIGNAL_SHARE: float = 0.40

MIN_WATCH_SIGNALS: int = 30
MIN_WATCH_YEARS: int = 4
MIN_WATCH_POSITIVE_YEAR_RATE: float = 0.66
MIN_WATCH_AVG_FWD_5D_ATR: float = 0.20
MAX_WATCH_BAD_TAIL_5D_RATE: float = 0.28


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def _weighted_average(frame: pd.DataFrame, value_col: str, weight_col: str = "signals") -> float:
    if frame.empty:
        return 0.0
    weights = pd.to_numeric(frame[weight_col], errors="coerce").fillna(0.0)
    values = pd.to_numeric(frame[value_col], errors="coerce").fillna(0.0)
    total = float(weights.sum())
    if total <= 0:
        return 0.0
    return _safe_float((values * weights).sum() / total)


def _window_metrics(years: pd.DataFrame, product_vt: str, direction: str, name: str, start: int, end: int) -> dict[str, Any]:
    frame = years[
        (years["product_vt"] == product_vt)
        & (years["direction"] == direction)
        & (years["year"] >= start)
        & (years["year"] <= end)
    ].copy()
    if frame.empty:
        return {
            "product_vt": product_vt,
            "direction": direction,
            "window": name,
            "start_year": start,
            "end_year": end,
            "signals": 0,
            "years": 0,
            "positive_years": 0,
            "avg_fwd_5d_atr": 0.0,
            "positive_5d_rate": 0.0,
            "bad_tail_5d_rate": 0.0,
        }

    avg = _weighted_average(frame, "avg_fwd_5d_atr")
    return {
        "product_vt": product_vt,
        "direction": direction,
        "window": name,
        "start_year": start,
        "end_year": end,
        "signals": int(pd.to_numeric(frame["signals"], errors="coerce").fillna(0).sum()),
        "years": int(frame["year"].nunique()),
        "positive_years": int((pd.to_numeric(frame["avg_fwd_5d_atr"], errors="coerce").fillna(0.0) > 0.0).sum()),
        "avg_fwd_5d_atr": avg,
        "positive_5d_rate": _weighted_average(frame, "positive_5d_rate"),
        "bad_tail_5d_rate": _weighted_average(frame, "bad_tail_5d_rate"),
    }


def _max_year_signal_share(years: pd.DataFrame, product_vt: str, direction: str) -> float:
    frame = years[(years["product_vt"] == product_vt) & (years["direction"] == direction)].copy()
    if frame.empty:
        return 1.0
    signals = pd.to_numeric(frame["signals"], errors="coerce").fillna(0.0)
    total = float(signals.sum())
    if total <= 0:
        return 1.0
    return _safe_float(signals.max() / total, 1.0)


def _classify(row: pd.Series) -> tuple[str, str]:
    reasons: list[str] = []
    if str(row["exchange"]) in EXCLUDED_EXCHANGES:
        return "excluded_financial", "financial_exchange"
    if bool(row["is_static18"]):
        return "excluded_static18", "static18_trend_pool"
    if int(row["recent_bars"]) < MIN_RECENT_BARS:
        reasons.append("recent_inactive")

    recent_signals = int(row["recent_2025_2026_signals"])
    recent_avg = float(row["recent_2025_2026_avg_fwd_5d_atr"])
    stress_signals = int(row["stress_2024_2025_signals"])
    stress_avg = float(row["stress_2024_2025_avg_fwd_5d_atr"])
    recent_ok = (
        recent_signals >= 3
        and recent_avg > 0
    )
    stress_ok = (
        stress_signals >= 5
        and stress_avg > 0
    )
    concentration_ok = float(row["max_year_signal_share"]) <= MAX_CORE_YEAR_SIGNAL_SHARE

    core_checks = [
        int(row["signals"]) >= MIN_CORE_SIGNALS,
        int(row["years"]) >= MIN_CORE_YEARS,
        float(row["positive_year_rate"]) >= MIN_CORE_POSITIVE_YEAR_RATE,
        float(row["avg_fwd_5d_atr"]) >= MIN_CORE_AVG_FWD_5D_ATR,
        float(row["positive_5d_rate"]) >= MIN_CORE_POSITIVE_5D_RATE,
        float(row["bad_tail_5d_rate"]) <= MAX_CORE_BAD_TAIL_5D_RATE,
        recent_ok,
        stress_ok,
        concentration_ok,
        int(row["recent_bars"]) >= MIN_RECENT_BARS,
    ]
    if all(core_checks):
        return "core", ""

    watch_checks = [
        int(row["signals"]) >= MIN_WATCH_SIGNALS,
        int(row["years"]) >= MIN_WATCH_YEARS,
        float(row["positive_year_rate"]) >= MIN_WATCH_POSITIVE_YEAR_RATE,
        float(row["avg_fwd_5d_atr"]) >= MIN_WATCH_AVG_FWD_5D_ATR,
        float(row["bad_tail_5d_rate"]) <= MAX_WATCH_BAD_TAIL_5D_RATE,
        int(row["recent_bars"]) >= MIN_RECENT_BARS,
        recent_ok or stress_ok,
    ]
    if all(watch_checks):
        if not recent_ok:
            reasons.append("recent_window_thin" if recent_signals < 3 else "recent_window_nonpositive")
        if not stress_ok:
            reasons.append("stress_window_thin" if stress_signals < 5 else "stress_window_nonpositive")
        if not concentration_ok:
            reasons.append("year_signal_concentrated")
        return "watch", ",".join(reasons)

    if not recent_ok:
        reasons.append("recent_window_thin" if recent_signals < 3 else "recent_window_nonpositive")
    if not stress_ok:
        reasons.append("stress_window_thin" if stress_signals < 5 else "stress_window_nonpositive")
    if not concentration_ok:
        reasons.append("year_signal_concentrated")
    if int(row["signals"]) < MIN_WATCH_SIGNALS:
        reasons.append("thin_signal_count")
    if int(row["years"]) < MIN_WATCH_YEARS:
        reasons.append("thin_year_count")
    if float(row["positive_year_rate"]) < MIN_WATCH_POSITIVE_YEAR_RATE:
        reasons.append("low_positive_year_rate")
    if float(row["avg_fwd_5d_atr"]) < MIN_WATCH_AVG_FWD_5D_ATR:
        reasons.append("weak_avg_edge")
    if float(row["bad_tail_5d_rate"]) > MAX_WATCH_BAD_TAIL_5D_RATE:
        reasons.append("bad_tail_high")
    return "reject", ",".join(reasons)


def _build_validation() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    top = _read_csv(TOP_INPUT_PATH)
    years = _read_csv(YEAR_INPUT_PATH)
    years["year"] = pd.to_numeric(years["year"], errors="coerce").fillna(0).astype(int)

    candidate_rows: list[dict[str, Any]] = []
    window_rows: list[dict[str, Any]] = []
    for source_row in top.itertuples(index=False):
        product_vt = str(source_row.product_vt)
        direction = str(source_row.direction)
        row = source_row._asdict()
        max_share = _max_year_signal_share(years, product_vt, direction)
        row["max_year_signal_share"] = max_share

        for name, (start, end) in WINDOWS.items():
            metrics = _window_metrics(years, product_vt, direction, name, start, end)
            window_rows.append(metrics)
            row[f"{name}_signals"] = metrics["signals"]
            row[f"{name}_years"] = metrics["years"]
            row[f"{name}_avg_fwd_5d_atr"] = metrics["avg_fwd_5d_atr"]
            row[f"{name}_positive_5d_rate"] = metrics["positive_5d_rate"]
            row[f"{name}_bad_tail_5d_rate"] = metrics["bad_tail_5d_rate"]

        status, reason = _classify(pd.Series(row))
        row["validation_status"] = status
        row["validation_reason"] = reason
        candidate_rows.append(row)

    validation = pd.DataFrame(candidate_rows)
    windows = pd.DataFrame(window_rows)
    validation = validation.sort_values(
        ["validation_status", "score", "avg_fwd_5d_atr"],
        ascending=[True, False, False],
    ).reset_index(drop=True)

    universe = validation[validation["validation_status"] == "core"].copy()
    if not universe.empty:
        universe = universe.sort_values(["score", "avg_fwd_5d_atr"], ascending=[False, False]).reset_index(drop=True)
        universe["eligible"] = 1
        universe["product_vt_symbol"] = universe["product_vt"]
        universe["direction_hint"] = universe["direction"]
        universe = universe[
            [
                "product_vt_symbol",
                "direction_hint",
                "eligible",
                "exchange",
                "signals",
                "years",
                "positive_year_rate",
                "avg_fwd_5d_atr",
                "positive_5d_rate",
                "bad_tail_5d_rate",
                "recent_2025_2026_avg_fwd_5d_atr",
                "stress_2024_2025_avg_fwd_5d_atr",
                "score",
            ]
        ].copy()

    summary = {
        "model_tag": MODEL_TAG,
        "input_top_candidates": str(TOP_INPUT_PATH),
        "total_input_candidates": int(len(top)),
        "excluded_financial": int((validation["validation_status"] == "excluded_financial").sum()),
        "excluded_static18": int((validation["validation_status"] == "excluded_static18").sum()),
        "core_candidates": int((validation["validation_status"] == "core").sum()),
        "watch_candidates": int((validation["validation_status"] == "watch").sum()),
        "rejected_candidates": int((validation["validation_status"] == "reject").sum()),
        "core_products": universe["product_vt_symbol"].tolist() if not universe.empty else [],
    }
    return validation, windows, universe, summary


def _write_report(validation: pd.DataFrame, universe: pd.DataFrame, summary: dict[str, Any]) -> None:
    lines: list[str] = [
        "# QMT Range Reversion Commodity Candidate Validation",
        "",
        "## 结论",
        f"- 输入候选方向：`{summary['total_input_candidates']}`。",
        f"- 排除金融期货方向：`{summary['excluded_financial']}`。",
        f"- 排除原18趋势池方向：`{summary['excluded_static18']}`。",
        f"- 核心商品候选：`{summary['core_candidates']}`。",
        f"- 观察商品候选：`{summary['watch_candidates']}`。",
        f"- 拒绝商品候选：`{summary['rejected_candidates']}`。",
        "- 本阶段仍不是交易回测，生成的宇宙只允许用于后续独立震荡回测，不得接入第78趋势策略。",
        "",
        "## 核心候选宇宙",
    ]
    if universe.empty:
        lines.append("- 无核心候选通过固定分段验证。")
    else:
        lines.append(
            universe[
                [
                    "product_vt_symbol",
                    "direction_hint",
                    "signals",
                    "years",
                    "positive_year_rate",
                    "avg_fwd_5d_atr",
                    "positive_5d_rate",
                    "bad_tail_5d_rate",
                    "recent_2025_2026_avg_fwd_5d_atr",
                    "stress_2024_2025_avg_fwd_5d_atr",
                    "score",
                ]
            ].to_markdown(index=False)
        )

    watch = validation[validation["validation_status"] == "watch"].copy()
    lines.extend(["", "## 观察候选"])
    if watch.empty:
        lines.append("- 无观察候选。")
    else:
        cols = [
            "product_vt",
            "direction",
            "signals",
            "years",
            "positive_year_rate",
            "avg_fwd_5d_atr",
            "recent_2025_2026_avg_fwd_5d_atr",
            "stress_2024_2025_avg_fwd_5d_atr",
            "validation_reason",
        ]
        lines.append(watch[cols].head(30).to_markdown(index=False))

    lines.extend(
        [
            "",
            "## 方法",
            "- 只保留非CFFEX、非原18趋势池的商品候选进入验证。",
            "- 固定窗口：2020-2022、2023-2024、2024-2025、2025-2026。",
            "- 核心候选要求样本数、年份数、正年份率、5日ATR收益、近期窗口、压力窗口、坏尾率同时过关。",
            "- 该宇宙是后续独立震荡回测的研究输入，不是正式策略配置。",
            "",
            "## 输出文件",
            f"- validation: `{VALIDATION_OUTPUT_PATH}`",
            f"- windows: `{WINDOW_OUTPUT_PATH}`",
            f"- universe: `{UNIVERSE_OUTPUT_PATH}`",
            f"- summary: `{SUMMARY_OUTPUT_PATH}`",
        ]
    )
    REPORT_OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    validation, windows, universe, summary = _build_validation()
    validation.to_csv(VALIDATION_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    windows.to_csv(WINDOW_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    universe.to_csv(UNIVERSE_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(validation, universe, summary)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"validation: {VALIDATION_OUTPUT_PATH}")
    print(f"windows: {WINDOW_OUTPUT_PATH}")
    print(f"universe: {UNIVERSE_OUTPUT_PATH}")
    print(f"report: {REPORT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
