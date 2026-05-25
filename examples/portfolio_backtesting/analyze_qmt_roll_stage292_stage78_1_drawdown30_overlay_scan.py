from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_CAPITAL
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage292_stage78_1_drawdown30_overlay_scan_v1"
OUTPUT_PREFIX = "qmt_roll_stage292_stage78_1_drawdown30_overlay_scan"
BASELINE_DAILY_PATH = OUTPUT_DIR / "qmt_roll_official_stage78_1_daily.csv"


@dataclass(frozen=True)
class OverlayProfile:
    name: str
    dd_start: float
    dd_full: float
    min_weight: float
    vol_target: float | None = None
    vol_lookback: int = 20
    vol_min_weight: float = 0.50
    vol_max_weight: float = 1.00


def _metrics(equity: pd.Series, daily_return: pd.Series, *, capital: float) -> dict[str, float]:
    equity = pd.to_numeric(equity, errors="coerce").ffill().fillna(capital).astype(float)
    daily_return = pd.to_numeric(daily_return, errors="coerce").fillna(0.0).astype(float)
    high = equity.cummax()
    drawdown_pct = (equity / high - 1.0) * 100.0
    total_return_pct = (float(equity.iloc[-1]) / capital - 1.0) * 100.0 if len(equity) else 0.0
    ret_std = float(daily_return.std(ddof=1))
    sharpe = float(daily_return.mean() / ret_std * np.sqrt(240.0)) if ret_std > 1e-12 else 0.0
    return {
        "end_balance": float(equity.iloc[-1]) if len(equity) else capital,
        "total_return_pct": total_return_pct,
        "max_dd_percent": float(drawdown_pct.min()) if len(drawdown_pct) else 0.0,
        "sharpe_ratio": sharpe,
    }


def _dd_weight(drawdown_ratio: float, *, start: float, full: float, min_weight: float) -> float:
    drawdown_ratio = max(0.0, float(drawdown_ratio))
    start = max(0.0, float(start))
    full = max(start + 1e-9, float(full))
    min_weight = min(1.0, max(0.0, float(min_weight)))
    if drawdown_ratio <= start:
        return 1.0
    if drawdown_ratio >= full:
        return min_weight
    raw = (full - drawdown_ratio) / (full - start)
    return min_weight + (1.0 - min_weight) * raw


def _simulate_overlay(baseline: pd.DataFrame, profile: OverlayProfile) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    equity = float(OFFICIAL_STAGE78_CAPITAL)
    high = equity
    returns = pd.to_numeric(baseline["return"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    dates = baseline["date"].astype(str).tolist()
    trailing_realized: list[float] = []

    for index, (date, base_return) in enumerate(zip(dates, returns, strict=False)):
        prior_high = max(high, equity)
        prior_dd = max(0.0, 1.0 - equity / prior_high) if prior_high > 0 else 0.0
        weight = _dd_weight(
            prior_dd,
            start=profile.dd_start,
            full=profile.dd_full,
            min_weight=profile.min_weight,
        )
        vol_weight = 1.0
        if profile.vol_target is not None and trailing_realized:
            recent = np.asarray(trailing_realized[-profile.vol_lookback :], dtype=float)
            realized_vol = float(recent.std(ddof=1) * np.sqrt(240.0)) if len(recent) >= 2 else 0.0
            if realized_vol > 1e-12:
                vol_weight = profile.vol_target / realized_vol
                vol_weight = min(profile.vol_max_weight, max(profile.vol_min_weight, vol_weight))
        final_weight = min(weight, vol_weight)
        overlay_return = float(base_return) * final_weight
        equity = equity * (1.0 + overlay_return)
        high = max(high, equity)
        trailing_realized.append(float(base_return))
        rows.append(
            {
                "date": date,
                "index": index,
                "baseline_return": float(base_return),
                "overlay_return": overlay_return,
                "weight": final_weight,
                "drawdown_weight": weight,
                "vol_weight": vol_weight,
                "prior_drawdown_pct": prior_dd * 100.0,
                "balance": equity,
                "highlevel": high,
                "drawdown_pct": (equity / high - 1.0) * 100.0 if high > 0 else 0.0,
                "profile": profile.name,
            }
        )
    return pd.DataFrame(rows)


def _profiles() -> list[OverlayProfile]:
    profiles: list[OverlayProfile] = []
    for dd_start in (0.08, 0.12, 0.16):
        for dd_full in (0.24, 0.30, 0.36):
            if dd_full <= dd_start:
                continue
            for min_weight in (0.35, 0.50, 0.65, 0.80):
                profiles.append(
                    OverlayProfile(
                        name=f"dd_{int(dd_start*100)}_{int(dd_full*100)}_min{int(min_weight*100)}",
                        dd_start=dd_start,
                        dd_full=dd_full,
                        min_weight=min_weight,
                    )
                )
    for vol_target in (0.30, 0.40, 0.50):
        profiles.append(
            OverlayProfile(
                name=f"vol_target_{int(vol_target*100)}",
                dd_start=0.99,
                dd_full=1.00,
                min_weight=1.0,
                vol_target=vol_target,
                vol_lookback=20,
                vol_min_weight=0.40,
                vol_max_weight=1.00,
            )
        )
    for min_weight in (0.50, 0.65, 0.80):
        profiles.append(
            OverlayProfile(
                name=f"dd12_30_min{int(min_weight*100)}_vol40",
                dd_start=0.12,
                dd_full=0.30,
                min_weight=min_weight,
                vol_target=0.40,
                vol_lookback=20,
                vol_min_weight=0.50,
                vol_max_weight=1.00,
            )
        )
    return profiles


def _load_baseline() -> pd.DataFrame:
    if not BASELINE_DAILY_PATH.exists():
        raise FileNotFoundError(f"missing baseline daily file: {BASELINE_DAILY_PATH}")
    df = pd.read_csv(BASELINE_DAILY_PATH)
    required = {"date", "balance", "return"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"baseline daily missing columns: {sorted(missing)}")
    return df.copy()


def _build_report(
    baseline_metrics: dict[str, float],
    summary_df: pd.DataFrame,
    pass_df: pd.DataFrame,
    paths: dict[str, str],
) -> str:
    top_cols = [
        "name",
        "end_balance",
        "total_return_pct",
        "return_retention_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "avg_weight",
        "min_weight_realized",
        "strict_pass",
        "research_pass",
    ]
    lines = [
        "# Stage292 78-1回撤30以内保收益：日收益覆盖层可行性扫描",
        "",
        "## 口径",
        "",
        "- A：78-1正式日收益曲线。",
        "- C：只用上一日权益/回撤/已实现波动率决定下一日风险权重的账户层覆盖曲线。",
        "- 本阶段是理论边界扫描，不是正式可上线回测；若有候选，必须落到真实策略引擎复跑。",
        "- 不使用未来收益，不改品种池，不做单品种黑名单。",
        "",
        "## A基准",
        "",
        f"- 期末权益：`{baseline_metrics['end_balance']:,.0f}`",
        f"- 总收益：`{baseline_metrics['total_return_pct']:.4f}%`",
        f"- 最大回撤：`{baseline_metrics['max_dd_percent']:.4f}%`",
        f"- Sharpe：`{baseline_metrics['sharpe_ratio']:.4f}`",
        "",
        "## 最优候选摘要",
        "",
        summary_df[top_cols].head(12).to_markdown(index=False),
        "",
        "## 达标候选",
        "",
        pass_df[top_cols].to_markdown(index=False) if not pass_df.empty else "无。",
        "",
        "## 判断",
        "",
        "- 若没有 `strict_pass=1`，说明单纯账户层降风险还没有证明能在回撤30以内同时保留80%以上收益。",
        "- `research_pass=1` 只能说明值得进入真实引擎验证，不等于可推广。",
        "",
        "## 输出文件",
        "",
    ]
    for name, path in paths.items():
        lines.append(f"- {name}: `{path}`")
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    baseline = _load_baseline()
    baseline_equity = pd.to_numeric(baseline["balance"], errors="coerce").ffill().fillna(OFFICIAL_STAGE78_CAPITAL)
    baseline_return = pd.to_numeric(baseline["return"], errors="coerce").fillna(0.0)
    baseline_metrics = _metrics(baseline_equity, baseline_return, capital=OFFICIAL_STAGE78_CAPITAL)

    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    for profile in _profiles():
        curve = _simulate_overlay(baseline, profile)
        metrics = _metrics(curve["balance"], curve["overlay_return"], capital=OFFICIAL_STAGE78_CAPITAL)
        weights = pd.to_numeric(curve["weight"], errors="coerce").fillna(1.0)
        row = {
            **asdict(profile),
            **metrics,
            "return_retention_pct": (
                metrics["total_return_pct"] / baseline_metrics["total_return_pct"] * 100.0
                if abs(baseline_metrics["total_return_pct"]) > 1e-9
                else 0.0
            ),
            "max_dd_improvement_pct": metrics["max_dd_percent"] - baseline_metrics["max_dd_percent"],
            "avg_weight": float(weights.mean()),
            "min_weight_realized": float(weights.min()),
            "strict_pass": int(metrics["max_dd_percent"] >= -30.0 and metrics["total_return_pct"] >= baseline_metrics["total_return_pct"] * 0.80),
            "research_pass": int(metrics["max_dd_percent"] >= -30.0 and metrics["total_return_pct"] >= baseline_metrics["total_return_pct"] * 0.65 and metrics["sharpe_ratio"] >= baseline_metrics["sharpe_ratio"]),
        }
        summary_rows.append(row)
        if row["strict_pass"] or row["research_pass"]:
            curve_frames.append(curve)

    summary_df = pd.DataFrame(summary_rows)
    summary_df = summary_df.sort_values(
        by=["strict_pass", "research_pass", "return_retention_pct", "max_dd_percent", "sharpe_ratio"],
        ascending=[False, False, False, False, False],
    )
    pass_df = summary_df[(summary_df["strict_pass"].eq(1)) | (summary_df["research_pass"].eq(1))].copy()
    curves_df = pd.concat(curve_frames, ignore_index=True) if curve_frames else pd.DataFrame()

    paths = {
        "summary": str(OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"),
        "passed_curves": str(OUTPUT_DIR / f"{OUTPUT_PREFIX}_passed_curves_{MODEL_TAG}.csv"),
        "report": str(OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"),
        "decision": str(OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"),
    }
    summary_df.to_csv(paths["summary"], index=False, encoding="utf-8-sig")
    curves_df.to_csv(paths["passed_curves"], index=False, encoding="utf-8-sig")
    report = _build_report(baseline_metrics, summary_df, pass_df, paths)
    Path(paths["report"]).write_text(report, encoding="utf-8")
    decision = {
        "model_tag": MODEL_TAG,
        "line_id": "futures_trend_drawdown30_preserve_return",
        "baseline_metrics": baseline_metrics,
        "strict_pass_count": int(summary_df["strict_pass"].sum()),
        "research_pass_count": int(summary_df["research_pass"].sum()),
        "best_rows": summary_df.head(12).to_dict(orient="records"),
        "paths": paths,
    }
    Path(paths["decision"]).write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
