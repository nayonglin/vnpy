from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd


CAPITAL_KEYS = frozenset({"account_capital", "c3_capital"})
A_ARM = "A_15w"
C_ARM = "C_30w"

LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "outputs" / "stage229_c9_30w_capital_ab"
PRODUCTION_ROOT = Path(
    os.environ.get("VNPY_PRODUCTION_ROOT", "/Users/bytedance/Desktop/person/vnpy_production_live")
).expanduser().resolve()
PRODUCTION_EXAMPLES = PRODUCTION_ROOT / "examples" / "portfolio_backtesting"

STAGE = "Stage229"
MODEL_TAG = "stage229_c9_30w_from_current_live_capital_ab_v1"
CANDIDATE_VERSION = "research_candidate_stage229_c9_30w_from_current_live_v1"
ANALYSIS_START = pd.Timestamp("2018-01-01")
ANALYSIS_END = pd.Timestamp("2026-08-28")
START_YEARS = tuple(range(2020, 2026))
ARM_CAPITALS = {A_ARM: 150_000.0, C_ARM: 300_000.0}
ROLLING_HORIZONS = (63, 126, 252)
COST_MULTIPLIERS = (1.0, 2.0, 3.0)

SUMMARY_PATH = OUTPUT_DIR / "full_period_summary.csv"
COMPARISON_PATH = OUTPUT_DIR / "full_period_comparison.csv"
CURVES_PATH = OUTPUT_DIR / "full_period_curves.csv"
COST_PATH = OUTPUT_DIR / "cost_stress.csv"
ROLLING_PATH = OUTPUT_DIR / "rolling_windows.csv"
START_YEAR_PATH = OUTPUT_DIR / "start_year_summary.csv"
CHART_PATH = OUTPUT_DIR / "equity_nav_drawdown_margin_comparison.png"
MANIFEST_PATH = OUTPUT_DIR / "identity_manifest.json"
DECISION_PATH = OUTPUT_DIR / "decision.json"
REPORT_PATH = OUTPUT_DIR / "report.md"


def changed_keys(before: Mapping[str, Any], after: Mapping[str, Any]) -> set[str]:
    keys = set(before) | set(after)
    return {key for key in keys if before.get(key) != after.get(key)}


def build_capital_overrides(
    live_overrides: Mapping[str, Any],
    target_capital: float,
) -> dict[str, Any]:
    result = dict(live_overrides)
    result["account_capital"] = float(target_capital)
    result["c3_capital"] = float(target_capital)
    assert_capital_only_contract(live_overrides, result)
    return result


def assert_capital_only_contract(
    live_overrides: Mapping[str, Any],
    candidate_overrides: Mapping[str, Any],
) -> None:
    drift = changed_keys(live_overrides, candidate_overrides)
    if not drift.issubset(CAPITAL_KEYS):
        raise ValueError(f"noncapital_override_drift:{sorted(drift - CAPITAL_KEYS)}")
    missing = CAPITAL_KEYS - set(candidate_overrides)
    if missing:
        raise ValueError(f"capital_override_missing:{sorted(missing)}")


def add_curve_fields(
    daily: pd.DataFrame,
    initial_capital: float,
    arm: str,
) -> pd.DataFrame:
    result = daily.copy()
    result["date"] = pd.to_datetime(result["date"], errors="raise").dt.normalize()
    result["account_equity"] = pd.to_numeric(result["account_equity"], errors="raise")
    result["arm"] = str(arm)
    result["initial_capital"] = float(initial_capital)
    result["normalized_nav"] = result["account_equity"] / float(initial_capital)
    running_peak = result["account_equity"].cummax()
    result["drawdown_pct"] = (result["account_equity"] / running_peak - 1.0) * 100.0
    return result


def replace_capital_spec(
    source: Any,
    *,
    target_capital: float,
    variant: str,
    label: str,
    note_suffix: str,
) -> Any:
    note = str(getattr(source, "note", "")).strip()
    suffix = str(note_suffix).strip()
    combined_note = " | ".join(part for part in [note, suffix] if part)
    return replace(
        source,
        variant=str(variant),
        label=str(label),
        account_capital=float(target_capital),
        c3_capital=float(target_capital),
        note=combined_note,
    )


def evaluate_candidate(full_summary: pd.DataFrame, start_year_summary: pd.DataFrame) -> dict[str, Any]:
    full = full_summary.set_index("arm")
    baseline = full.loc[A_ARM]
    candidate = full.loc[C_ARM]
    failed: list[str] = []
    if int(candidate["days_over_100pct"]) > 0:
        failed.append("candidate_broker100_failure")
    if float(candidate["max_dd_pct"]) < -40.0:
        failed.append("candidate_dd40_failure")
    if float(candidate["max_dd_pct"]) < float(baseline["max_dd_pct"]) - 5.0:
        failed.append("candidate_drawdown_worse_by_more_than_5pp")
    if float(candidate["sharpe"]) < float(baseline["sharpe"]) - 0.10:
        failed.append("candidate_sharpe_worse_by_more_than_0_10")

    if not start_year_summary.empty:
        aggregations: dict[str, tuple[str, str]] = {
            "positive_count": ("positive_return", "sum"),
            "dd50_pass_count": ("dd50_pass", "sum"),
            "window_count": ("positive_return", "size"),
        }
        if "broker10_100_pass" in start_year_summary.columns:
            aggregations["broker100_pass_count"] = ("broker10_100_pass", "sum")
        grouped = start_year_summary.groupby("arm", sort=False).agg(**aggregations)
        if C_ARM in grouped.index and A_ARM in grouped.index:
            if int(grouped.loc[C_ARM, "positive_count"]) < int(grouped.loc[A_ARM, "positive_count"]):
                failed.append("candidate_fewer_positive_start_years")
            if int(grouped.loc[C_ARM, "dd50_pass_count"]) < int(grouped.loc[A_ARM, "dd50_pass_count"]):
                failed.append("candidate_more_dd50_start_year_failures")
            if (
                "broker100_pass_count" in grouped.columns
                and int(grouped.loc[C_ARM, "broker100_pass_count"])
                < int(grouped.loc[A_ARM, "broker100_pass_count"])
            ):
                failed.append("candidate_more_broker100_start_year_failures")

    return {
        "decision": "accept_30w_as_research_deployment_candidate" if not failed else "reject_30w_capital_scaling",
        "failed_gates": failed,
        "auto_promote_to_live": False,
    }


def _load_production_modules() -> SimpleNamespace:
    if not PRODUCTION_EXAMPLES.exists():
        raise FileNotFoundError(f"production_examples_missing:{PRODUCTION_EXAMPLES}")
    path_text = str(PRODUCTION_EXAMPLES)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

    import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
    import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847
    import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
    import qmt_roll_official_live_config as live_cfg

    for module in [s650, s847, s901, live_cfg]:
        module_path = Path(module.__file__).resolve()
        if PRODUCTION_ROOT not in module_path.parents:
            raise RuntimeError(f"nonproduction_module_loaded:{module.__name__}:{module_path}")
    return SimpleNamespace(s650=s650, s847=s847, s901=s901, live_cfg=live_cfg)


def _run_git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(PRODUCTION_ROOT), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _run_arm(
    modules: SimpleNamespace,
    metadata: dict[str, Any],
    *,
    arm: str,
    target_capital: float,
    analysis_start: pd.Timestamp,
    analysis_end: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], Any, dict[str, Any]]:
    s847 = modules.s847
    s901 = modules.s901
    live_cfg = modules.live_cfg
    original_start = s847.START
    original_end = s847.END
    original_minute_by_symbol = s847.s827._GLOBAL_MINUTE_BY_SYMBOL
    minute_audit = s901._ensure_c9_minute_bars(metadata)
    try:
        s847.START = pd.Timestamp(analysis_start).normalize()
        s847.END = pd.Timestamp(analysis_end).normalize()
        source_profile = s847._c9_profile(metadata)
        source_spec = source_profile["spec"]
        live_overrides = live_cfg.build_official_live_strategy_overrides()
        variant_overrides = build_capital_overrides(live_overrides, target_capital)
        assert_capital_only_contract(live_overrides, variant_overrides)
        profile_name = (
            live_cfg.OFFICIAL_LIVE_PROFILE_NAME if arm == A_ARM else CANDIDATE_VERSION
        )
        capital_spec = replace_capital_spec(
            source_spec.capital,
            target_capital=target_capital,
            variant=profile_name,
            label=f"{arm} C9 capital-only A/C",
            note_suffix=(
                f"{STAGE} derived from {live_cfg.OFFICIAL_LIVE_VERSION}; "
                "only account_capital/c3_capital and engine initial capital change."
            ),
        )
        profile = dict(source_profile)
        profile["profile"] = profile_name
        profile["spec"] = replace(
            source_spec,
            capital=capital_spec,
            overrides={**source_spec.overrides, **variant_overrides},
            profile=profile_name,
        )
        combined, frames = s847._run_profile(profile, metadata)
        live_spec = profile["spec"]
    finally:
        s847.START = original_start
        s847.END = original_end
        s847.s827._GLOBAL_MINUTE_BY_SYMBOL = original_minute_by_symbol

    daily = combined.copy()
    daily["account_capital"] = float(target_capital)
    daily["c3_capital"] = float(target_capital)
    daily["profile"] = live_spec.profile
    daily["arm"] = arm
    for frame in frames.values():
        if frame.empty:
            continue
        frame["account_capital"] = float(target_capital)
        frame["c3_capital"] = float(target_capital)
        frame["profile"] = live_spec.profile
        frame["arm"] = arm
    return daily, frames, live_spec, minute_audit


def _metrics(
    modules: SimpleNamespace,
    daily: pd.DataFrame,
    spec: Any,
    *,
    arm: str,
    cost_multiplier: float,
    window: str,
) -> dict[str, Any]:
    result = modules.s650._metrics(daily, spec.capital, cost_multiplier=cost_multiplier)
    result.update(
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "arm": arm,
            "window": window,
            "cost_multiplier": float(cost_multiplier),
            "actual_start": pd.to_datetime(daily["date"]).min().date().isoformat(),
            "actual_end": pd.to_datetime(daily["date"]).max().date().isoformat(),
            "trading_days": int(len(daily)),
            "positive_return": int(float(result["total_return_pct"]) > 0.0),
            "dd50_pass": int(float(result["max_dd_pct"]) >= -50.0),
        }
    )
    return result


def _rolling_metrics(curves: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for arm, group in curves.groupby("arm", sort=False):
        ordered = group.sort_values("date").reset_index(drop=True)
        equity = ordered["account_equity"].to_numpy(dtype=float)
        dates = pd.to_datetime(ordered["date"])
        for horizon in ROLLING_HORIZONS:
            for start_idx in range(0, max(0, len(ordered) - horizon)):
                end_idx = start_idx + horizon
                values = equity[start_idx : end_idx + 1]
                peaks = np.maximum.accumulate(values)
                rows.append(
                    {
                        "arm": arm,
                        "holding_days": horizon,
                        "start": dates.iloc[start_idx].date().isoformat(),
                        "end": dates.iloc[end_idx].date().isoformat(),
                        "return_pct": (values[-1] / values[0] - 1.0) * 100.0,
                        "max_dd_pct": np.min(values / np.maximum(peaks, 1e-9) - 1.0) * 100.0,
                    }
                )
    return pd.DataFrame(rows)


def _comparison_table(summary: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "end_equity",
        "total_return_pct",
        "cagr_pct",
        "max_dd_pct",
        "ulcer_pct",
        "sharpe",
        "min_equity",
        "max_broker10_margin_to_equity_pct",
        "p95_broker10_margin_to_equity_pct",
        "days_over_100pct",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
    ]
    indexed = summary.set_index("arm")
    rows: list[dict[str, Any]] = []
    for metric in metrics:
        a_value = float(indexed.loc[A_ARM, metric])
        c_value = float(indexed.loc[C_ARM, metric])
        rows.append(
            {
                "metric": metric,
                "A_15w": a_value,
                "C_30w": c_value,
                "C_minus_A": c_value - a_value,
                "C_over_A": c_value / a_value if abs(a_value) > 1e-12 else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _plot_curves(curves: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {A_ARM: "#2f6bff", C_ARM: "#e1812c"}
    fig, axes = plt.subplots(4, 1, figsize=(14, 16), sharex=True)
    for arm, group in curves.groupby("arm", sort=False):
        ordered = group.sort_values("date")
        color = colors.get(str(arm), None)
        axes[0].plot(ordered["date"], ordered["account_equity"], label=arm, color=color, linewidth=1.5)
        axes[1].plot(ordered["date"], ordered["normalized_nav"], label=arm, color=color, linewidth=1.5)
        axes[2].plot(ordered["date"], ordered["drawdown_pct"], label=arm, color=color, linewidth=1.2)
        axes[3].plot(
            ordered["date"],
            ordered["broker10_margin_to_equity_pct"],
            label=arm,
            color=color,
            linewidth=1.2,
        )
    axes[0].set_title("C9 Current Live Capital A/C - Absolute Equity")
    axes[0].set_ylabel("Equity (CNY)")
    axes[1].set_title("Normalized NAV")
    axes[1].set_ylabel("NAV")
    axes[1].set_yscale("log")
    axes[2].set_title("Drawdown")
    axes[2].set_ylabel("Drawdown (%)")
    axes[3].set_title("Broker10 Margin / Equity")
    axes[3].set_ylabel("Margin (%)")
    axes[3].axhline(100.0, color="#b00020", linestyle="--", linewidth=1.0, label="100% gate")
    for axis in axes:
        axis.grid(alpha=0.22)
        axis.legend(loc="best")
    axes[-1].set_xlabel("Date")
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _markdown_table(frame: pd.DataFrame, columns: list[str] | None = None) -> str:
    view = frame.loc[:, columns].copy() if columns else frame.copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return view.to_markdown(index=False)


def _write_report(
    *,
    modules: SimpleNamespace,
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    start_years: pd.DataFrame,
    rolling: pd.DataFrame,
    decision: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    rolling_aggregate = (
        rolling.groupby(["arm", "holding_days"], as_index=False)
        .agg(
            sample_count=("return_pct", "size"),
            min_return_pct=("return_pct", "min"),
            p05_return_pct=("return_pct", lambda values: float(np.quantile(values, 0.05))),
            median_return_pct=("return_pct", "median"),
            positive_rate_pct=("return_pct", lambda values: float((values > 0).mean() * 100.0)),
            worst_window_dd_pct=("max_dd_pct", "min"),
        )
    )
    lines = [
        "# Stage229 当前正式 C9：15万 vs 30万资金 A/C",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}`",
        f"- 正式基准：`{modules.live_cfg.OFFICIAL_LIVE_VERSION}` / `{modules.live_cfg.OFFICIAL_LIVE_ALIAS}`。",
        f"- A：`{A_ARM}`，初始资金 `150,000`。",
        f"- C：`{C_ARM}` / `{CANDIDATE_VERSION}`，初始资金 `300,000`。",
        f"- 区间：`{ANALYSIS_START.date()}` 至 `{ANALYSIS_END.date()}`。",
        "- 唯一变更：`account_capital`、`c3_capital` 和由其驱动的回测引擎初始资金；策略、AI池、品种池、成本与规则保持正式版一致。",
        "- 生产目录只读；未连接 CTP，订单 API 调用数为 0。",
        "",
        "## 全周期结果",
        "",
        _markdown_table(
            summary,
            [
                "arm",
                "account_capital",
                "end_equity",
                "total_return_pct",
                "max_dd_pct",
                "sharpe",
                "total_slippage",
                "total_trade_count",
                "nonzero_daily_win_rate_pct",
                "max_broker10_margin_to_equity_pct",
                "days_over_100pct",
            ],
        ),
        "",
        "## C 相对 A",
        "",
        _markdown_table(comparison),
        "",
        "## 独立起点",
        "",
        _markdown_table(
            start_years,
            [
                "start_year",
                "arm",
                "end_equity",
                "total_return_pct",
                "max_dd_pct",
                "sharpe",
                "max_broker10_margin_to_equity_pct",
                "positive_return",
                "dd50_pass",
            ],
        ),
        "",
        "## 滚动窗口",
        "",
        _markdown_table(rolling_aggregate),
        "",
        "## 决策",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 失败门：`{decision['failed_gates']}`。",
        "- 自动切换实盘：否。研究候选即使通过，也必须另行审批和执行闸门。",
        f"- 过拟合反思：{decision['overfit_reflection_after']}",
        f"- 继续价值反思：{decision['continue_value_after']}",
        "",
        "## 输入身份",
        "",
        f"- production HEAD：`{manifest['production_head']}`",
        f"- material release：`{manifest['material_release_id']}`",
        f"- material manifest SHA256：`{manifest['material_manifest_sha256']}`",
        f"- AI eligibility SHA256：`{manifest['ai_eligibility_sha256']}`",
        "",
        "## 数据覆盖限制",
        "",
        f"- {decision['minute_coverage_limitation']}",
        "",
        "## 输出",
        "",
    ]
    for key, value in decision["outputs"].items():
        lines.append(f"- {key}: `{value}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    modules = _load_production_modules()
    live_cfg = modules.live_cfg
    if float(live_cfg.OFFICIAL_LIVE_CAPITAL) != ARM_CAPITALS[A_ARM]:
        raise RuntimeError(f"official_live_capital_drift:{live_cfg.OFFICIAL_LIVE_CAPITAL}")

    metadata = modules.s901.s513._metadata()
    print(
        f"[{STAGE}] official={live_cfg.OFFICIAL_LIVE_VERSION} "
        f"window={ANALYSIS_START.date()}..{ANALYSIS_END.date()} arms={ARM_CAPITALS}",
        flush=True,
    )

    full_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    full_specs: dict[str, Any] = {}
    minute_audits: dict[str, Any] = {}
    for arm, capital in ARM_CAPITALS.items():
        print(f"[{STAGE}] full-period start arm={arm} capital={capital:.0f}", flush=True)
        daily, _frames, spec, minute_audit = _run_arm(
            modules,
            metadata,
            arm=arm,
            target_capital=capital,
            analysis_start=ANALYSIS_START,
            analysis_end=ANALYSIS_END,
        )
        full_specs[arm] = spec
        minute_audits[arm] = minute_audit
        metrics = _metrics(
            modules,
            daily,
            spec,
            arm=arm,
            cost_multiplier=1.0,
            window="full",
        )
        full_rows.append(metrics)
        for multiplier in COST_MULTIPLIERS:
            cost_rows.append(
                _metrics(
                    modules,
                    daily,
                    spec,
                    arm=arm,
                    cost_multiplier=multiplier,
                    window="full",
                )
            )
        curve = add_curve_fields(daily, capital, arm)
        curve["broker10_margin_to_equity_pct"] = (
            pd.to_numeric(curve["broker10_total_margin_exact"], errors="coerce").fillna(0.0)
            / np.maximum(curve["account_equity"].to_numpy(dtype=float), 1e-9)
            * 100.0
        )
        curve_frames.append(curve)
        print(
            f"[{STAGE}] full-period done arm={arm} end_equity={metrics['end_equity']:.2f} "
            f"return={metrics['total_return_pct']:.4f}% dd={metrics['max_dd_pct']:.4f}%",
            flush=True,
        )

    summary = pd.DataFrame(full_rows)
    cost = pd.DataFrame(cost_rows)
    curves = pd.concat(curve_frames, ignore_index=True)
    comparison = _comparison_table(summary)
    rolling = _rolling_metrics(curves)

    start_rows: list[dict[str, Any]] = []
    for start_year in START_YEARS:
        start = pd.Timestamp(year=start_year, month=1, day=1)
        for arm, capital in ARM_CAPITALS.items():
            print(f"[{STAGE}] start-year start year={start_year} arm={arm}", flush=True)
            daily, _frames, spec, _minute_audit = _run_arm(
                modules,
                metadata,
                arm=arm,
                target_capital=capital,
                analysis_start=start,
                analysis_end=ANALYSIS_END,
            )
            metrics = _metrics(
                modules,
                daily,
                spec,
                arm=arm,
                cost_multiplier=1.0,
                window=f"since_{start_year}",
            )
            metrics["start_year"] = start_year
            start_rows.append(metrics)
            print(
                f"[{STAGE}] start-year done year={start_year} arm={arm} "
                f"return={metrics['total_return_pct']:.4f}% dd={metrics['max_dd_pct']:.4f}%",
                flush=True,
            )
    start_years = pd.DataFrame(start_rows)

    decision = evaluate_candidate(summary, start_years)
    continue_value_after = (
        "作为替换15万正式版的方向没有继续价值；保留可复验负向基准，不扫描资金金额或按窗口救参。"
        if decision["decision"] == "reject_30w_capital_scaling"
        else "有条件。可保留为独立研究部署候选，但仍不能自动替换当前15万实盘。"
    )
    minute_coverage_limitation = (
        "分钟审计请求801个合约、加载502个、缺失299个；两臂覆盖完全相同，"
        "不破坏资本A/C相对比较，但绝对绩效不是801个合约全分钟覆盖口径。"
    )
    decision.update(
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "candidate_version": CANDIDATE_VERSION,
            "official_live_version": live_cfg.OFFICIAL_LIVE_VERSION,
            "official_live_alias": live_cfg.OFFICIAL_LIVE_ALIAS,
            "analysis_start": ANALYSIS_START.date().isoformat(),
            "analysis_end": ANALYSIS_END.date().isoformat(),
            "order_api_called": False,
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
            "ctp_connected": False,
            "overfit_reflection_before": (
                "否。资金规模是部署层单变量，规则、样本、AI池与成本在看结果前冻结。"
            ),
            "continue_value_before": (
                "是。整数手、并发上限和保证金闸门可能使30万相对15万呈非线性路径。"
            ),
            "overfit_reflection_after": (
                "否。本次没有按结果调整阈值、年份、品种或规则；后续若为救某个窗口而调资金或规则才会产生后验过拟合。"
            ),
            "continue_value_after": continue_value_after,
            "minute_coverage_limitation": minute_coverage_limitation,
            "outputs": {
                "summary": str(SUMMARY_PATH),
                "comparison": str(COMPARISON_PATH),
                "curves": str(CURVES_PATH),
                "cost_stress": str(COST_PATH),
                "rolling_windows": str(ROLLING_PATH),
                "start_year_summary": str(START_YEAR_PATH),
                "chart": str(CHART_PATH),
                "identity_manifest": str(MANIFEST_PATH),
                "decision": str(DECISION_PATH),
                "report": str(REPORT_PATH),
            },
        }
    )

    official_config = PRODUCTION_EXAMPLES / "qmt_roll_official_live_config.py"
    strategy_engine = PRODUCTION_EXAMPLES / "analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine.py"
    ai_path = Path(live_cfg.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH).resolve()
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "production_root": str(PRODUCTION_ROOT),
        "production_head": _run_git("rev-parse", "HEAD"),
        "production_status_porcelain": _run_git("status", "--porcelain"),
        "official_live_version": live_cfg.OFFICIAL_LIVE_VERSION,
        "official_live_alias": live_cfg.OFFICIAL_LIVE_ALIAS,
        "official_live_capital": float(live_cfg.OFFICIAL_LIVE_CAPITAL),
        "candidate_version": CANDIDATE_VERSION,
        "candidate_capital": ARM_CAPITALS[C_ARM],
        "changed_strategy_override_keys": sorted(CAPITAL_KEYS),
        "official_config_path": str(official_config),
        "official_config_sha256": _sha256(official_config),
        "strategy_engine_path": str(strategy_engine),
        "strategy_engine_sha256": _sha256(strategy_engine),
        "material_release_id": live_cfg.OFFICIAL_LIVE_MATERIAL_RELEASE_ID,
        "material_release_commit": live_cfg.OFFICIAL_LIVE_MATERIAL_RELEASE_COMMIT,
        "material_manifest_sha256": live_cfg.OFFICIAL_LIVE_MATERIAL_MANIFEST_SHA256,
        "ai_eligibility_path": str(ai_path),
        "ai_eligibility_sha256": _sha256(ai_path),
        "analysis_start": ANALYSIS_START.date().isoformat(),
        "analysis_end": ANALYSIS_END.date().isoformat(),
        "minute_audits": minute_audits,
        "external_research": [
            "https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/backtesting.py",
            "https://github.com/vnpy/vnpy/blob/master/docs/community/app/cta_backtester.md",
        ],
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    start_years.to_csv(START_YEAR_PATH, index=False, encoding="utf-8-sig")
    _plot_curves(curves)
    MANIFEST_PATH.write_text(
        json.dumps(_json_safe(manifest), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    DECISION_PATH.write_text(
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_report(
        modules=modules,
        summary=summary,
        comparison=comparison,
        start_years=start_years,
        rolling=rolling,
        decision=decision,
        manifest=manifest,
    )
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
