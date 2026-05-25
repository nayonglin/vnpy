from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_CAPITAL, OFFICIAL_STAGE78_VERSION
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage306_low_corr_satellite_scout_v1"
OUTPUT_PREFIX = "qmt_roll_stage306_low_corr_satellite_scout"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASE_CURVES_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage305_cash_buffer_multiperiod_validation_curves_"
    "stage305_cash_buffer_multiperiod_validation_v1.csv"
)

SATELLITE_PATTERNS: tuple[str, ...] = (
    "qmt_range_reversion_*daily*.csv",
    "qmt_boll_reversal*daily*.csv",
    "qmt_no_lower_shadow_swing*daily*.csv",
    "qmt_no_upper_shadow_short_swing*daily*.csv",
)

FULL_WINDOW = "full_2020_2026"
BASE_VARIANT = "C_pressure040"
BASELINE_VARIANT = "A_baseline_78_1"
BASE_WEIGHT = 0.85
SATELLITE_WEIGHT = 0.15

WINDOWS: tuple[tuple[str, str, str], ...] = (
    ("full_2020_2026", "2020-01-01", "2026-04-30"),
    ("since_2022", "2022-01-01", "2026-04-30"),
    ("since_2023", "2023-01-01", "2026-04-30"),
    ("since_2024", "2024-01-01", "2026-04-30"),
    ("phase_2022_2023", "2022-01-01", "2023-12-31"),
    ("phase_2024_2025", "2024-01-01", "2025-12-31"),
)


@dataclass(frozen=True)
class CandidateCurve:
    name: str
    path: Path
    nav: pd.Series


def _path_metrics(nav: pd.Series) -> dict[str, float]:
    nav = nav.dropna()
    if nav.empty:
        return {
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
        }
    arr = nav.to_numpy(dtype=float)
    high = np.maximum.accumulate(arr)
    drawdown_pct = np.divide(arr - high, high, out=np.zeros_like(arr), where=high != 0) * 100.0
    returns = pd.Series(arr, index=nav.index).pct_change().fillna(0.0).to_numpy(dtype=float)
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / std * np.sqrt(252)) if std > 0 else 0.0
    return {
        "total_return_pct": float((arr[-1] - 1.0) * 100.0),
        "max_dd_percent": float(drawdown_pct.min()),
        "sharpe_ratio": sharpe,
    }


def _load_base_curves() -> tuple[pd.Series, pd.Series]:
    df = pd.read_csv(BASE_CURVES_PATH)
    df["date"] = pd.to_datetime(df["date"])
    full = df[df["window_name"].eq(FULL_WINDOW)].copy()
    baseline = full[full["variant"].eq(BASELINE_VARIANT)].sort_values("date")
    base = full[full["variant"].eq(BASE_VARIANT)].sort_values("date")
    baseline_nav = pd.Series(
        baseline["balance"].to_numpy(dtype=float) / OFFICIAL_STAGE78_CAPITAL,
        index=pd.to_datetime(baseline["date"]),
        name=BASELINE_VARIANT,
    )
    base_nav = pd.Series(
        base["balance"].to_numpy(dtype=float) / OFFICIAL_STAGE78_CAPITAL,
        index=pd.to_datetime(base["date"]),
        name=BASE_VARIANT,
    )
    return baseline_nav, base_nav


def _candidate_paths() -> list[Path]:
    paths: set[Path] = set()
    for pattern in SATELLITE_PATTERNS:
        paths.update(OUTPUT_DIR.glob(pattern))
    blocked = {
        BASE_CURVES_PATH.name,
    }
    return sorted(path for path in paths if path.name not in blocked and path.is_file())


def _load_candidate(path: Path, base_index: pd.DatetimeIndex) -> CandidateCurve | None:
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    if "date" not in df.columns or "balance" not in df.columns:
        return None
    df = df[["date", "balance"]].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["balance"] = pd.to_numeric(df["balance"], errors="coerce")
    df = df.dropna(subset=["date", "balance"]).sort_values("date")
    if df.empty or float(df["balance"].iloc[0]) <= 0:
        return None
    df = df.drop_duplicates("date", keep="last")
    raw_nav = pd.Series(df["balance"].to_numpy(dtype=float) / float(df["balance"].iloc[0]), index=df["date"])
    nav = raw_nav.reindex(base_index).ffill().fillna(1.0)
    if nav.nunique(dropna=True) <= 2:
        return None
    return CandidateCurve(name=path.stem, path=path, nav=nav)


def _window_slice(series: pd.Series, start: str, end: str) -> pd.Series:
    return series[(series.index >= pd.Timestamp(start)) & (series.index <= pd.Timestamp(end))]


def _rebased_window(series: pd.Series, start: str, end: str) -> pd.Series:
    sliced = _window_slice(series, start, end).dropna()
    if sliced.empty:
        return sliced
    first = float(sliced.iloc[0])
    if first == 0:
        return sliced
    return sliced / first


def _retention(candidate_return: float, baseline_return: float) -> float:
    if baseline_return <= 0:
        return 0.0
    return candidate_return / baseline_return * 100.0


def _run_scout() -> tuple[pd.DataFrame, pd.DataFrame]:
    baseline_nav, base_nav = _load_base_curves()
    base_index = base_nav.index
    base_returns = base_nav.pct_change().fillna(0.0)
    baseline_metrics_by_window: dict[str, dict[str, float]] = {}
    base_metrics_by_window: dict[str, dict[str, float]] = {}
    for window_name, start, end in WINDOWS:
        baseline_metrics_by_window[window_name] = _path_metrics(_rebased_window(baseline_nav, start, end))
        base_metrics_by_window[window_name] = _path_metrics(_rebased_window(base_nav, start, end))

    rows: list[dict[str, Any]] = []
    combo_rows: list[dict[str, Any]] = []
    for path in _candidate_paths():
        candidate = _load_candidate(path, base_index)
        if candidate is None:
            continue
        sat_returns = candidate.nav.pct_change().fillna(0.0)
        corr_full = float(base_returns.corr(sat_returns))
        corr_2022_dd = float(
            base_returns.loc["2022-03-09":"2022-12-07"].corr(sat_returns.loc["2022-03-09":"2022-12-07"])
        )
        sat_full_metrics = _path_metrics(candidate.nav)
        combo_nav = BASE_WEIGHT * base_nav + SATELLITE_WEIGHT * candidate.nav
        if not combo_nav.empty:
            combo_nav = combo_nav / float(combo_nav.iloc[0])
        combo_full_metrics = _path_metrics(combo_nav)
        baseline_full = baseline_metrics_by_window[FULL_WINDOW]
        full_retention = _retention(
            combo_full_metrics["total_return_pct"],
            baseline_full["total_return_pct"],
        )
        rows.append(
            {
                "candidate": candidate.name,
                "path": str(path),
                "corr_full": corr_full,
                "corr_2022_dd": corr_2022_dd,
                "sat_total_return_pct": sat_full_metrics["total_return_pct"],
                "sat_max_dd_pct": sat_full_metrics["max_dd_percent"],
                "sat_sharpe": sat_full_metrics["sharpe_ratio"],
                "combo_total_return_pct": combo_full_metrics["total_return_pct"],
                "combo_return_retention_pct": full_retention,
                "combo_max_dd_pct": combo_full_metrics["max_dd_percent"],
                "combo_sharpe": combo_full_metrics["sharpe_ratio"],
                "combo_full_strict_pass": int(
                    combo_full_metrics["max_dd_percent"] >= -30.0 and full_retention >= 80.0
                ),
            }
        )
        for window_name, start, end in WINDOWS:
            baseline_metrics = baseline_metrics_by_window[window_name]
            base_metrics = base_metrics_by_window[window_name]
            sliced_base = _rebased_window(base_nav, start, end)
            sliced_satellite = _rebased_window(candidate.nav, start, end)
            sliced_combo = (BASE_WEIGHT * sliced_base + SATELLITE_WEIGHT * sliced_satellite).dropna()
            metrics = _path_metrics(sliced_combo)
            retention = _retention(metrics["total_return_pct"], baseline_metrics["total_return_pct"])
            combo_rows.append(
                {
                    "candidate": candidate.name,
                    "window_name": window_name,
                    "baseline_return_pct": baseline_metrics["total_return_pct"],
                    "base_pressure040_return_pct": base_metrics["total_return_pct"],
                    "combo_return_pct": metrics["total_return_pct"],
                    "return_retention_pct": retention,
                    "baseline_max_dd_pct": baseline_metrics["max_dd_percent"],
                    "base_pressure040_max_dd_pct": base_metrics["max_dd_percent"],
                    "combo_max_dd_pct": metrics["max_dd_percent"],
                    "combo_sharpe": metrics["sharpe_ratio"],
                    "strict_pass": int(metrics["max_dd_percent"] >= -30.0 and retention >= 80.0),
                    "research_pass": int(metrics["max_dd_percent"] >= -30.0 and retention >= 65.0),
                }
            )

    scout_df = pd.DataFrame(rows)
    combo_df = pd.DataFrame(combo_rows)
    if not scout_df.empty:
        scout_df = scout_df.sort_values(
            ["combo_full_strict_pass", "combo_max_dd_pct", "combo_return_retention_pct", "corr_full"],
            ascending=[False, False, False, True],
        )
    return scout_df, combo_df


def _build_report(scout_df: pd.DataFrame, combo_df: pd.DataFrame) -> str:
    top = scout_df.head(30).copy()
    robust_rows: list[dict[str, Any]] = []
    if not combo_df.empty:
        for candidate, group in combo_df.groupby("candidate", sort=False):
            positive = group[group["baseline_return_pct"] > 0]
            robust_rows.append(
                {
                    "candidate": candidate,
                    "positive_window_count": int(len(positive)),
                    "strict_pass_count": int(positive["strict_pass"].sum()),
                    "research_pass_count": int(positive["research_pass"].sum()),
                    "min_return_retention_pct": float(positive["return_retention_pct"].min()) if not positive.empty else 0.0,
                    "worst_max_dd_pct": float(positive["combo_max_dd_pct"].min()) if not positive.empty else 0.0,
                }
            )
    robust_df = pd.DataFrame(robust_rows).sort_values(
        ["strict_pass_count", "research_pass_count", "min_return_retention_pct", "worst_max_dd_pct"],
        ascending=[False, False, False, False],
    ) if robust_rows else pd.DataFrame()

    lines = [
        "# Stage306 低相关卫星策略侦察",
        "",
        "## 目标",
        "",
        "- A：第78-1正式基准。",
        "- C底座：Stage007 最强单策略防守线索 `C_full_delev_pressure040`。",
        "- 卫星：仓库已有震荡/反转/波段日权益曲线。",
        f"- 组合：`{BASE_WEIGHT:.0%}` C底座 + `{SATELLITE_WEIGHT:.0%}` 卫星，替代 Stage009 的15%现金缓冲。",
        "- 本阶段是侦察，不直接推广任何卫星策略。",
        "",
        "## 外部调研判断",
        "",
        "- CTA/管理期货研究普遍强调低相关子策略和跨风格组合可以降低组合尾部回撤。",
        "- 但低相关本身不够；卫星策略必须在78-1弱窗口提供正贡献，否则只是摊薄收益。",
        "",
        "## 全样本排名前30",
        "",
    ]
    if top.empty:
        lines.append("- 未找到可用候选曲线。")
    else:
        lines.append(
            top[
                [
                    "candidate",
                    "corr_full",
                    "corr_2022_dd",
                    "sat_total_return_pct",
                    "sat_max_dd_pct",
                    "combo_total_return_pct",
                    "combo_return_retention_pct",
                    "combo_max_dd_pct",
                    "combo_sharpe",
                    "combo_full_strict_pass",
                ]
            ].to_markdown(index=False)
        )
    lines.extend(["", "## 多周期稳健排名", ""])
    if robust_df.empty:
        lines.append("- 未形成稳健性统计。")
    else:
        lines.append(robust_df.head(30).to_markdown(index=False))
    lines.extend(
        [
            "",
            "## 阶段判断",
            "",
        ]
    )
    if robust_df.empty or int(robust_df.iloc[0]["strict_pass_count"]) == 0:
        lines.append("- 没有卫星候选在多周期层面显示出足够强的严格通过迹象。")
    else:
        best = robust_df.iloc[0]
        lines.append(
            f"- 最强候选为 `{best['candidate']}`，正收益窗口严格通过 `{int(best['strict_pass_count'])}/{int(best['positive_window_count'])}`。"
        )
        lines.append("- 若进入下一步，必须只选排名前列且具备独立策略逻辑的候选做真实多周期组合验证。")
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    scout_df, combo_df = _run_scout()

    scout_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_scout_{MODEL_TAG}.csv"
    combo_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combo_windows_{MODEL_TAG}.csv"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

    scout_df.to_csv(scout_path, index=False, encoding="utf-8-sig")
    combo_df.to_csv(combo_path, index=False, encoding="utf-8-sig")
    report_path.write_text(_build_report(scout_df, combo_df), encoding="utf-8")

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "base_variant": BASE_VARIANT,
        "base_weight": BASE_WEIGHT,
        "satellite_weight": SATELLITE_WEIGHT,
        "candidate_count": int(len(scout_df)),
        "top_full": scout_df.head(10).to_dict(orient="records"),
        "paths": {
            "scout": str(scout_path),
            "combo": str(combo_path),
            "report": str(report_path),
        },
    }
    decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[stage306] scout={scout_path}")
    print(f"[stage306] combo={combo_path}")
    print(f"[stage306] report={report_path}")
    print(f"[stage306] decision={decision_path}")
    print(report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
