from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from run_qmt_alignment_backtest import OUTPUT_DIR


PROJECT_DIR = Path(__file__).resolve().parent
STAGE391_SCRIPT = PROJECT_DIR / "analyze_qmt_roll_stage391_stage079_overheat_cooldown_true_engine_validation.py"
MODEL_TAG = "stage392_stage079_overheat_cooldown_mechanism_ablation_v1"
OUTPUT_PREFIX = "qmt_roll_stage392_stage079_overheat_cooldown_mechanism_ablation"
LINE_ID = "futures_trend_drawdown30_preserve_return"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
SCALE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_scale_history_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _load_stage391_module():
    spec = importlib.util.spec_from_file_location("stage391_for_stage392", STAGE391_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {STAGE391_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["stage391_for_stage392"] = module
    spec.loader.exec_module(module)
    return module


s391 = _load_stage391_module()
s087 = s391.s087


def _merge(*items: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for item in items:
        merged.update(item)
    return merged


def _hot20(*, deleverage: bool, recovery_scale: float) -> dict[str, Any]:
    overrides = s391._overheat_overrides(hot60_threshold=-1.0)
    overrides["enable_portfolio_overheat_cooldown_deleverage"] = bool(deleverage)
    overrides["portfolio_overheat_cooldown_recovery_scale"] = float(recovery_scale)
    return overrides


PROFILES: tuple[Any, ...] = (
    s391.Profile(
        s391.BASELINE_VARIANT,
        "Stage079真实引擎基准",
        {},
        "基准。",
    ),
    s391.Profile(
        "hot20_full_deleverage_recovery",
        "hot20完整：新仓缩放+已有仓位减仓+恢复加风险",
        _hot20(deleverage=True, recovery_scale=1.10),
        "Stage091 hot20 版本复核，用于机制对照。",
    ),
    s391.Profile(
        "hot20_entry_recovery_no_deleverage",
        "hot20仅新仓/加仓缩放+恢复加风险",
        _hot20(deleverage=False, recovery_scale=1.10),
        "不主动平已有仓位，检验真实减仓是否是主要伤害来源。",
    ),
    s391.Profile(
        "hot20_deleverage_brake_only",
        "hot20新仓缩放+已有仓位减仓，不恢复加风险",
        _hot20(deleverage=True, recovery_scale=1.00),
        "去掉恢复加风险，检验恢复段频繁加风险是否造成路径扰动。",
    ),
    s391.Profile(
        "hot20_entry_brake_only",
        "hot20仅新仓/加仓缩放，不恢复加风险",
        _hot20(deleverage=False, recovery_scale=1.00),
        "最低干预机制，只检验过热后新风险预算冷却。",
    ),
)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4f}" if pd.notna(x) else "")
    return view.to_markdown(index=False)


def _gate(summary: pd.DataFrame, score: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    base = summary[summary["variant"].eq(s391.BASELINE_VARIANT)].iloc[0]
    score_one = score.drop_duplicates(["variant", "label"])
    base_score = score_one[score_one["variant"].eq(s391.BASELINE_VARIANT)].iloc[0]
    for _, row in summary.iterrows():
        one_score = score_one[score_one["variant"].eq(row["variant"])].iloc[0]
        checks = {
            "total_return_not_lower": float(row["total_return_pct"]) >= float(base["total_return_pct"]) - 1e-4,
            "max_dd_not_worse": float(row["max_dd_pct"]) >= float(base["max_dd_pct"]) - 1e-4,
            "max_dd_below_30": float(row["max_dd_pct"]) >= -30.0,
            "sharpe_not_lower": float(row["sharpe"]) >= float(base["sharpe"]) - 1e-4,
            "ulcer_not_higher": float(row["ulcer_pct"]) <= float(base["ulcer_pct"]) + 1e-4,
            "rolling252_dd30_zero": float(row["rolling252_dd30_breach_rate"]) == 0.0,
            "rolling504_dd30_zero": float(row["rolling504_dd30_breach_rate"]) == 0.0,
            "score90_improve_ge10pct": float(one_score["score_90d"]) >= float(base_score["score_90d"]) * 1.10,
            "score180_improve_ge10pct": float(one_score["score_180d"]) >= float(base_score["score_180d"]) * 1.10,
        }
        rows.append(
            {
                "variant": row["variant"],
                "label": row["label"],
                **{key: int(value) for key, value in checks.items()},
                "normal_gate_pass": int(all(checks.values())),
                "failed_checks": ",".join([key for key, value in checks.items() if not value]),
                "score_90d": float(one_score["score_90d"]),
                "score_180d": float(one_score["score_180d"]),
                "short_holding_score": float(one_score["short_holding_score"]),
            }
        )
    return pd.DataFrame(rows).sort_values(["normal_gate_pass", "short_holding_score"], ascending=[False, False])


def _write_report(summary: pd.DataFrame, horizon: pd.DataFrame, score: pd.DataFrame, gate: pd.DataFrame, scale: pd.DataFrame, decision: dict[str, Any]) -> None:
    focus_summary = ["variant", "total_return_pct", "max_dd_pct", "sharpe", "ulcer_pct", "rolling252_dd30_breach_rate", "rolling504_dd30_breach_rate"]
    focus_horizon = ["variant", "horizon_days", "return_p05_pct", "return_median_pct", "positive_return_rate", "annualized_below_5pct_rate", "max_dd_worst_pct", "dd20_breach_rate", "dd30_breach_rate", "ulcer_p95_pct", "longest_underwater_p95_days"]
    focus_score = ["variant", "score_90d", "score_180d", "short_holding_score"]
    focus_gate = ["variant", "normal_gate_pass", "score_90d", "score_180d", "short_holding_score", "failed_checks"]
    if not scale.empty:
        scale_summary = (
            scale.groupby("variant", as_index=False)
            .agg(
                scaled_days=("scale", lambda x: int((pd.to_numeric(x, errors="coerce") != 1.0).sum())),
                brake_days=("scale", lambda x: int((pd.to_numeric(x, errors="coerce") < 0.999).sum())),
                recovery_days=("scale", lambda x: int((pd.to_numeric(x, errors="coerce") > 1.001).sum())),
                min_scale=("scale", "min"),
                max_scale=("scale", "max"),
                deleverage_count=("deleverage_count", "max"),
            )
        )
    else:
        scale_summary = pd.DataFrame()

    report = [
        "# Stage092 Stage079过热冷却机制拆解",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：机制归因，不扫阈值；只拆新仓缩放、已有仓位减仓、恢复加风险。",
        "",
        "## 决策",
        "",
        "```json",
        json.dumps(s391._to_builtin(decision), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 全周期",
        "",
        _md_table(summary[focus_summary]),
        "",
        "## 3个月/6个月",
        "",
        _md_table(horizon[focus_horizon].sort_values(["variant", "horizon_days"])),
        "",
        "## 评分",
        "",
        _md_table(score[focus_score].drop_duplicates("variant")),
        "",
        "## 正常成本门禁",
        "",
        _md_table(gate[focus_gate]),
        "",
        "## 触发摘要",
        "",
        _md_table(scale_summary),
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    daily_parts: list[pd.DataFrame] = []
    scale_parts: list[pd.DataFrame] = []
    stats_by_variant: dict[str, dict[str, Any]] = {}

    for profile in PROFILES:
        analysis_df, statistics, scale = s391._run_engine(profile, 1.0)
        daily = s391._daily_equity(profile, analysis_df, 1.0)
        daily_parts.append(daily)
        stats_by_variant[profile.variant] = statistics
        if not scale.empty:
            scale_parts.append(scale)

    daily = pd.concat(daily_parts, ignore_index=True)
    scale = pd.concat(scale_parts, ignore_index=True) if scale_parts else pd.DataFrame()
    candidates = [
        s391._as_stage087_candidate(profile, s391._calendar_equity(daily, profile.variant))
        for profile in PROFILES
    ]
    summary = pd.DataFrame([s087._stats(candidate) for candidate in candidates])
    for profile in PROFILES:
        stats = stats_by_variant.get(profile.variant, {})
        mask = summary["variant"].eq(profile.variant)
        summary.loc[mask, "total_slippage"] = float(stats.get("total_slippage", 0.0) or 0.0)
        summary.loc[mask, "total_trade_count"] = int(stats.get("total_trade_count", 0) or 0)
        summary.loc[mask, "win_ratio"] = float(stats.get("win_ratio", 0.0) or 0.0)
    horizon = pd.DataFrame([s087._horizon_metrics(candidate, horizon) for candidate in candidates for horizon in (90, 180)])
    score = s087._score_horizons(horizon)
    gate = _gate(summary, score)
    passed = gate[gate["normal_gate_pass"].eq(1) & ~gate["variant"].eq(s391.BASELINE_VARIANT)]
    decision = {
        "stage": "Stage092",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "normal_gate_candidate_found_requires_stress" if not passed.empty else "no_normal_gate_candidate",
        "normal_gate_variants": passed["variant"].tolist(),
        "best_by_short_holding_score": gate.iloc[0]["variant"] if not gate.empty else "",
        "note": "机制归因；若无正常成本候选，不进入成本压力复跑。",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    if not scale.empty:
        scale.to_csv(SCALE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(s391._to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, horizon, score, gate, scale, decision)
    print(json.dumps(s391._to_builtin(decision), ensure_ascii=False, indent=2), flush=True)
    print(f"[stage392] report={REPORT_PATH}", flush=True)


if __name__ == "__main__":
    main()
