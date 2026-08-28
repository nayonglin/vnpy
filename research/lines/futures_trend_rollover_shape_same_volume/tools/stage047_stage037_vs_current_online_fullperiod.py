from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from typing import Any
from uuid import uuid4

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
sys.path.insert(0, str(PORTFOLIO_DIR))

import qmt_roll_candidate_stage037_short_mirror_block_config as stage037_cfg  # noqa: E402
import qmt_roll_official_live_config as live_cfg  # noqa: E402
from qmt_roll_official_baseline_identity import (  # noqa: E402
    assert_official_checkout_matches_active_material,
)
import stage028_q_delayed_rollover_abc as s28  # noqa: E402
import stage029_stage028_multicycle_abc as s29  # noqa: E402
import stage037_stage034_short_mirror_block_abc as s37  # noqa: E402


LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage047_stage037_vs_live"
PRODUCTION_ROOT = Path("/Users/bytedance/Desktop/person/vnpy_production_live")
PRODUCTION_CONFIG = PRODUCTION_ROOT / "examples" / "portfolio_backtesting" / "qmt_roll_official_live_config.py"
PRODUCTION_STRATEGY = PRODUCTION_ROOT / "examples" / "portfolio_backtesting" / "qmt_roll_portfolio_strategy.py"
PRODUCTION_DATABASE = PRODUCTION_ROOT / ".vntrader" / "database.db"
START = pd.Timestamp("2018-01-01")
EXPECTED_FIRST_TRADING_DAY = pd.Timestamp("2018-01-02")
END = pd.Timestamp("2026-08-28")
METRICS = s28.METRICS

ARMS: tuple[dict[str, str], ...] = (
    {
        "arm": "A",
        "profile": "stage047_A_current_online_stage847_c9_15w_q",
        "label": "A: 当前线上 Stage847-C9-15w + Q",
        "plot_label": "A Current Online",
        "color": "#2563eb",
    },
    {
        "arm": "C",
        "profile": "stage047_C_stage037_long_short_mirror_block",
        "label": "C: Stage037 多空镜像硬拦截",
        "plot_label": "C Stage037",
        "color": "#16a34a",
    },
)

SUMMARY_NAME = "stage047_stage037_vs_live_summary.csv"
COMPARISON_NAME = "stage047_stage037_vs_live_comparison.csv"
CURVE_NAME = "stage047_stage037_vs_live_curve.csv"
FILTER_NAME = "stage047_stage037_filter_diagnostics.csv"
FILTER_CONTRACT_NAME = "stage047_stage037_filter_contract.csv"
TRADES_NAME = "stage047_stage037_vs_live_trades.csv"
DECISION_NAME = "stage047_stage037_vs_live_decision.json"
REPORT_NAME = "stage047_stage037_vs_live_report.md"
CHART_NAME = "stage047_stage037_vs_live_equity.png"


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_arm_overrides(arm: str) -> dict[str, Any]:
    if arm == "A":
        return live_cfg.build_official_live_strategy_overrides()
    if arm == "C":
        return stage037_cfg.build_candidate_overrides()
    raise ValueError(f"unknown_stage047_arm:{arm}")


def override_diff() -> dict[str, tuple[Any, Any]]:
    online = build_arm_overrides("A")
    candidate = build_arm_overrides("C")
    return {
        key: (online.get(key), candidate.get(key))
        for key in sorted(set(online) | set(candidate))
        if online.get(key) != candidate.get(key)
    }


def _expected_override_diff() -> dict[str, tuple[Any, Any]]:
    return {
        "enable_long_signal_range_atr_filter": (None, True),
        "enable_short_signal_range_atr_filter": (None, True),
        "long_signal_range_atr_entry_contexts": (
            None,
            "flat_entry,reverse_entry,rollover_reopen",
        ),
        "long_signal_range_atr_multiplier": (None, 3.0),
        "long_signal_range_atr_period": (None, 5),
        "long_signal_range_enable_ordered_drawdown_filter": (None, True),
        "long_signal_range_lookback": (None, 10),
        "long_signal_range_ordered_drawdown_atr_multiplier": (None, 4.0),
        "long_signal_range_recent_gain_atr_multiplier": (None, 0.5),
        "long_signal_range_recent_gain_lookback": (None, 3),
        "long_signal_range_require_recent_stall": (None, True),
        "rollover_delay_trading_days": (None, 5),
        "rollover_shape_history_mode": (
            "backwards_ratio_continuous",
            "target_contract_only",
        ),
    }


def _database_latest_daily_date(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "select max(datetime) from dbbardata where interval='d'"
        ).fetchone()
    return str(row[0]).split(" ", 1)[0] if row and row[0] else ""


def _ai_pool_file_identity(path: Path) -> dict[str, Any]:
    frame = pd.read_csv(path)
    eval_dates = pd.to_datetime(frame["eval_date"], errors="raise").dt.normalize()
    return {
        "path": str(path.resolve()),
        "sha256": _file_sha256(path),
        "row_count": int(len(frame)),
        "min_eval_date": str(eval_dates.min().date()),
        "max_eval_date": str(eval_dates.max().date()),
        "eval_date_count": int(eval_dates.nunique()),
    }


def _ai_pool_identity() -> dict[str, Any]:
    local_path = Path(live_cfg.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH).resolve()
    relative_path = local_path.relative_to(PROJECT_DIR.resolve())
    production_path = (PRODUCTION_ROOT / relative_path).resolve()
    local = _ai_pool_file_identity(local_path)
    production = _ai_pool_file_identity(production_path)
    parity_fields = (
        "sha256",
        "row_count",
        "min_eval_date",
        "max_eval_date",
        "eval_date_count",
    )
    if any(local[field] != production[field] for field in parity_fields):
        raise RuntimeError(f"stage047_ai_pool_production_parity_failed:{local}!={production}")
    return {
        **local,
        "production_path": production["path"],
        "production_sha256": production["sha256"],
        "production_parity_pass": True,
    }


def _preflight() -> dict[str, Any]:
    if override_diff() != _expected_override_diff():
        raise RuntimeError(f"stage047_override_scope_drift:{override_diff()}")
    if live_cfg.OFFICIAL_LIVE_VERSION != "official_live_stage847_c9_15w_stage819_05r_stop_retry_once":
        raise RuntimeError(f"stage047_unexpected_live_version:{live_cfg.OFFICIAL_LIVE_VERSION}")
    if float(live_cfg.OFFICIAL_LIVE_CAPITAL) != 150_000.0:
        raise RuntimeError(f"stage047_unexpected_live_capital:{live_cfg.OFFICIAL_LIVE_CAPITAL}")

    local_config_sha = _file_sha256(Path(live_cfg.__file__).resolve())
    production_config_sha = _file_sha256(PRODUCTION_CONFIG)
    if local_config_sha != production_config_sha:
        raise RuntimeError(
            f"stage047_online_config_mismatch:{local_config_sha}!={production_config_sha}"
        )

    production_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PRODUCTION_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tracking_master = subprocess.run(
        ["git", "rev-parse", "origin/master"],
        cwd=PROJECT_DIR,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    remote_line = subprocess.run(
        ["git", "ls-remote", "origin", "refs/heads/master"],
        cwd=PROJECT_DIR,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    remote_master = remote_line.split()[0] if remote_line else ""
    if production_head != remote_master or production_head != tracking_master:
        raise RuntimeError(
            "stage047_production_not_remote_master:"
            f"production={production_head},remote={remote_master},tracking={tracking_master}"
        )

    runtime = s29._assert_runtime_database_binding()
    runtime_database = Path(runtime["database_path"])
    runtime_sha = _file_sha256(runtime_database)
    production_database_sha = _file_sha256(PRODUCTION_DATABASE)
    if runtime_sha != production_database_sha:
        raise RuntimeError(
            f"stage047_database_snapshot_mismatch:{runtime_sha}!={production_database_sha}"
        )
    latest_daily_date = _database_latest_daily_date(runtime_database)
    if latest_daily_date != str(END.date()):
        raise RuntimeError(
            f"stage047_latest_daily_date_mismatch:{latest_daily_date}!={END.date()}"
        )

    production_identity = asdict(
        assert_official_checkout_matches_active_material(PRODUCTION_ROOT)
    )
    if production_identity["strategy_version"] != live_cfg.OFFICIAL_LIVE_VERSION:
        raise RuntimeError("stage047_material_live_version_mismatch")

    return {
        "production_head": production_head,
        "remote_master": remote_master,
        "origin_master_tracking": tracking_master,
        "production_identity": production_identity,
        "online_alias": live_cfg.OFFICIAL_LIVE_ALIAS,
        "online_version": live_cfg.OFFICIAL_LIVE_VERSION,
        "online_source_stage": live_cfg.OFFICIAL_LIVE_SOURCE_STAGE,
        "online_capital": float(live_cfg.OFFICIAL_LIVE_CAPITAL),
        "online_config_sha256": local_config_sha,
        "production_config_sha256": production_config_sha,
        "online_to_stage037_override_diff": override_diff(),
        "runtime_binding": {
            **runtime,
            "database_sha256": runtime_sha,
            "production_database_sha256": production_database_sha,
            "latest_daily_date": latest_daily_date,
        },
        "ai_pool": _ai_pool_identity(),
        "source_sha256": {
            "stage037_strategy": _file_sha256(PORTFOLIO_DIR / "qmt_roll_portfolio_strategy.py"),
            "production_strategy": _file_sha256(PRODUCTION_STRATEGY),
            "stage037_config": _file_sha256(Path(stage037_cfg.__file__).resolve()),
            "runner": _file_sha256(Path(__file__).resolve()),
        },
    }


_PRODUCTION_A_HELPER = r"""
from dataclasses import replace
from pathlib import Path
import sys

import pandas as pd

output_path = Path(sys.argv[1])
profile = sys.argv[2]
label = sys.argv[3]
start = pd.Timestamp(sys.argv[4])
end = pd.Timestamp(sys.argv[5])
production_root = Path.cwd().resolve()
portfolio_dir = production_root / "examples" / "portfolio_backtesting"
sys.path.insert(0, str(portfolio_dir))

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac as s827
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
import qmt_roll_official_live_config as live_cfg
import qmt_roll_portfolio_strategy as strategy_module

modules = {
    "s513": s513,
    "s827": s827,
    "s901": s901,
    "live_config": live_cfg,
    "strategy": strategy_module,
}
module_paths = {name: str(Path(module.__file__).resolve()) for name, module in modules.items()}
for name, path in module_paths.items():
    if not Path(path).is_relative_to(portfolio_dir):
        raise RuntimeError(f"stage047_production_module_escape:{name}:{path}")

metadata = s513._metadata()
original_builder = s901.build_official_live_strategy_overrides
try:
    s901.build_official_live_strategy_overrides = live_cfg.build_official_live_strategy_overrides
    combined, frames, live_spec = s901._run_live_c9(metadata, start, end)
finally:
    s901.build_official_live_strategy_overrides = original_builder

capital = replace(live_spec.capital, variant=profile, label=label)
metric_spec = replace(live_spec, capital=capital, profile=profile)
summary, curve = s827._metric({"profile": profile, "spec": metric_spec}, combined)
summary["experiment_arm"] = "A"
summary["window_name"] = "full_2018_20260828"
summary["window_label"] = "2018-01-01 independent start to 2026-08-28"
curve["experiment_arm"] = "A"
for frame in frames.values():
    if not frame.empty:
        frame["experiment_arm"] = "A"
pd.to_pickle(
    {
        "summary": summary,
        "curve": curve,
        "frames": frames,
        "module_paths": module_paths,
    },
    output_path,
)
"""


def _validate_production_engine_binding(module_paths: dict[str, str]) -> dict[str, Any]:
    expected = {
        "s513": PRODUCTION_ROOT / "examples" / "portfolio_backtesting" / "analyze_qmt_roll_stage513_stage208_exact_position_margin_audit.py",
        "s827": PRODUCTION_ROOT / "examples" / "portfolio_backtesting" / "analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac.py",
        "s901": PRODUCTION_ROOT / "examples" / "portfolio_backtesting" / "analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py",
        "live_config": PRODUCTION_CONFIG,
        "strategy": PRODUCTION_STRATEGY,
    }
    resolved = {name: str(Path(path).resolve()) for name, path in module_paths.items()}
    expected_resolved = {name: str(path.resolve()) for name, path in expected.items()}
    if resolved != expected_resolved:
        raise RuntimeError(
            f"stage047_production_engine_binding_failed:{resolved}!={expected_resolved}"
        )
    return {
        "all_modules_from_production_checkout": True,
        "module_paths": resolved,
        "module_sha256": {
            name: _file_sha256(Path(path)) for name, path in resolved.items()
        },
    }


def _run_production_online_arm(
    arm: dict[str, str],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame], dict[str, Any]]:
    production_python = PRODUCTION_ROOT / ".py311" / "bin" / "python"
    with tempfile.TemporaryDirectory(prefix="stage047-production-a-") as directory:
        output_path = Path(directory) / "production_a.pkl"
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(PRODUCTION_ROOT)
        subprocess.run(
            [
                str(production_python),
                "-c",
                _PRODUCTION_A_HELPER,
                str(output_path),
                arm["profile"],
                arm["label"],
                str(START.date()),
                str(END.date()),
            ],
            cwd=PRODUCTION_ROOT,
            env=environment,
            check=True,
        )
        payload = pd.read_pickle(output_path)
    binding = _validate_production_engine_binding(payload["module_paths"])
    return payload["summary"], payload["curve"], payload["frames"], binding


def _run_arm(
    arm: dict[str, str],
    metadata: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    original_builder = s28.s901.build_official_live_strategy_overrides
    try:
        s28.s901.build_official_live_strategy_overrides = lambda: build_arm_overrides(arm["arm"])
        combined, frames, live_spec = s28.s901._run_live_c9(metadata, START, END)
    finally:
        s28.s901.build_official_live_strategy_overrides = original_builder

    capital = replace(live_spec.capital, variant=arm["profile"], label=arm["label"])
    metric_spec = replace(live_spec, capital=capital, profile=arm["profile"])
    summary, curve = s28.s827._metric(
        {"profile": arm["profile"], "spec": metric_spec}, combined
    )
    summary["experiment_arm"] = arm["arm"]
    summary["window_name"] = "full_2018_20260828"
    summary["window_label"] = "2018-01-01 independent start to 2026-08-28"
    curve["experiment_arm"] = arm["arm"]
    for frame in frames.values():
        if not frame.empty:
            frame["experiment_arm"] = arm["arm"]
    return summary, curve, frames


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    indexed = summary.set_index("experiment_arm")
    online = indexed.loc["A"]
    candidate = indexed.loc["C"]
    row: dict[str, Any] = {
        "comparison": "A_current_online_vs_C_stage037",
        "baseline": str(online["profile"]),
        "candidate": str(candidate["profile"]),
    }
    for metric in METRICS:
        row[f"A_{metric}"] = float(online[metric])
        row[f"C_{metric}"] = float(candidate[metric])
        row[f"delta_{metric}"] = float(candidate[metric]) - float(online[metric])
    return pd.DataFrame([row])


def _assert_coverage(summary: pd.DataFrame, curve: pd.DataFrame) -> None:
    if len(summary) != 2 or set(summary["experiment_arm"].astype(str)) != {"A", "C"}:
        raise RuntimeError("stage047_arm_identity_failed")
    reference_dates: pd.DatetimeIndex | None = None
    for arm in ("A", "C"):
        row = summary[summary["experiment_arm"].astype(str).eq(arm)].iloc[0]
        dates = pd.DatetimeIndex(
            pd.to_datetime(
                curve[curve["experiment_arm"].astype(str).eq(arm)]["date"],
                errors="raise",
                format="mixed",
            ).dt.normalize()
        )
        if reference_dates is None:
            reference_dates = dates
        if (
            dates.duplicated().any()
            or not dates.equals(reference_dates)
            or dates.min() != EXPECTED_FIRST_TRADING_DAY
            or dates.max() != END
            or pd.Timestamp(row["analysis_start"]).normalize() != EXPECTED_FIRST_TRADING_DAY
            or pd.Timestamp(row["analysis_end"]).normalize() != END
        ):
            raise RuntimeError(f"stage047_full_period_coverage_failed:{arm}")


def _plot(curve: pd.DataFrame) -> bytes:
    fig, ax = plt.subplots(figsize=(14, 6))
    for arm in ARMS:
        frame = curve[curve["experiment_arm"].astype(str).eq(arm["arm"])].sort_values("date")
        ax.plot(
            pd.to_datetime(frame["date"]),
            pd.to_numeric(frame["account_equity"], errors="coerce") / 10_000.0,
            color=arm["color"],
            linewidth=1.45,
            label=arm["plot_label"],
        )
    ax.set_title("Full Period: Current Online vs Stage037")
    ax.set_ylabel("Equity (10k CNY)")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=180)
    plt.close(fig)
    return buffer.getvalue()


def _report(summary: pd.DataFrame, comparison: pd.DataFrame, decision: dict[str, Any]) -> str:
    indexed = summary.set_index("experiment_arm")
    delta = comparison.iloc[0]
    lines = [
        "# Stage047 Stage037 与当前线上版本全周期对比",
        "",
        f"数据区间：`{START.date()}` 至 `{END.date()}`；当前线上：`{decision['identity']['online_version']}`。",
        "",
        "| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 非零交易日胜率 | broker10峰值 | 超100%天数 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in ("A", "C"):
        row = indexed.loc[arm]
        lines.append(
            f"| {ARMS[0 if arm == 'A' else 1]['label']} | {row['end_equity']:,.2f} | "
            f"{row['total_return_pct']:.4f}% | {row['max_dd_pct']:.4f}% | "
            f"{row['sharpe']:.6f} | {row['total_slippage']:,.0f} | "
            f"{int(row['total_trade_count'])} | {row['nonzero_daily_win_rate_pct']:.4f}% | "
            f"{row['max_broker10_margin_to_equity_pct']:.4f}% | {int(row['days_over_100pct'])} |"
        )
    lines.extend(
        [
            "",
            "## 差异",
            "",
            f"- Stage037相对线上：期末权益 `{delta['delta_end_equity']:+,.2f}`，总收益 `{delta['delta_total_return_pct']:+.4f}pp`，最大回撤 `{delta['delta_max_dd_pct']:+.4f}pp`，Sharpe `{delta['delta_sharpe']:+.6f}`。",
            f"- 滑点 `{delta['delta_total_slippage']:+,.0f}`，交易数 `{delta['delta_total_trade_count']:+.0f}`，非零交易日胜率 `{delta['delta_nonzero_daily_win_rate_pct']:+.4f}pp`。",
            f"- Stage037过滤合同：`{decision['filter_contract']['all_pass']}`；实际多头/空头硬拦截 `{decision['filter_contract']['long_incremental_block_count']}/{decision['filter_contract']['short_incremental_block_count']}`。",
            "- 本阶段只做全周期复核，不因单一起点结果自动晋升；没有连接CTP或调用订单API。",
            "",
        ]
    )
    return "\n".join(lines)


def _publish(
    frames: dict[str, pd.DataFrame],
    decision: dict[str, Any],
    report: str,
    chart: bytes,
) -> None:
    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".stage047.tmp-", dir=OUTPUT_DIR.parent))
    backup = OUTPUT_DIR.with_name(f".stage047.backup-{uuid4().hex}")
    try:
        for filename, frame in frames.items():
            frame.to_csv(temporary / filename, index=False, encoding="utf-8-sig")
        (temporary / DECISION_NAME).write_text(
            json.dumps(decision, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (temporary / REPORT_NAME).write_text(report, encoding="utf-8")
        (temporary / CHART_NAME).write_bytes(chart)
        if OUTPUT_DIR.exists():
            backup.unlink(missing_ok=True) if backup.is_file() else None
            OUTPUT_DIR.rename(backup)
        temporary.rename(OUTPUT_DIR)
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def main() -> None:
    identity = _preflight()
    metadata = s28.s513._metadata()
    summaries: list[pd.DataFrame] = []
    curves: list[pd.DataFrame] = []
    all_frames: dict[str, dict[str, pd.DataFrame]] = {}
    for arm in ARMS:
        print(f"[stage047] running {arm['arm']} {START.date()}->{END.date()}", flush=True)
        if arm["arm"] == "A":
            summary, curve, frames, production_binding = _run_production_online_arm(arm)
            identity["production_engine_binding"] = production_binding
        else:
            summary, curve, frames = _run_arm(arm, metadata)
        summaries.append(summary)
        curves.append(curve)
        all_frames[arm["arm"]] = frames

    summary = pd.concat(summaries, ignore_index=True, sort=False)
    curve = pd.concat(curves, ignore_index=True, sort=False)
    _assert_coverage(summary, curve)
    comparison = _comparison(summary)

    c_frames = all_frames["C"]
    filter_diagnostics = c_frames["long_signal_range_atr"].copy()
    filter_contract = s37._filter_contract(filter_diagnostics)
    history_contract = s28._history_contract(c_frames["rollover_shape_same_volume"], "C")
    delay_contract = s28._delay_contract(
        c_frames["rollover_delay"],
        c_frames["rollover_shape_same_volume"],
        c_frames["trade_events"],
    )
    if not filter_contract["all_pass"]:
        raise RuntimeError(f"stage047_filter_contract_failed:{filter_contract}")
    if not history_contract["all_pass"] or not delay_contract["all_pass"]:
        raise RuntimeError("stage047_rollover_contract_failed")

    indexed = summary.set_index("experiment_arm")
    online, candidate = indexed.loc["A"], indexed.loc["C"]
    delta = comparison.iloc[0]
    gates = {
        "current_online_identity_pass": bool(
            identity["production_engine_binding"]["all_modules_from_production_checkout"]
            and identity["ai_pool"]["production_parity_pass"]
            and identity["production_head"] == identity["remote_master"]
            and identity["production_head"] == identity["origin_master_tracking"]
        ),
        "production_engine_binding_pass": bool(
            identity["production_engine_binding"]["all_modules_from_production_checkout"]
        ),
        "ai_pool_production_parity_pass": bool(
            identity["ai_pool"]["production_parity_pass"]
        ),
        "scope_exact_stage037_vs_online": override_diff() == _expected_override_diff(),
        "coverage_through_latest_daily_data": True,
        "filter_rollover_contracts_pass": bool(
            filter_contract["all_pass"]
            and history_contract["all_pass"]
            and delay_contract["all_pass"]
        ),
        "account_survival": float(candidate["min_equity"]) > 0,
        "stage037_end_equity_above_online": float(candidate["end_equity"]) >= float(online["end_equity"]),
        "stage037_max_drawdown_not_worse": float(delta["delta_max_dd_pct"]) >= 0,
        "stage037_sharpe_not_lower": float(delta["delta_sharpe"]) >= 0,
        "stage037_slippage_not_above_105pct_online": float(candidate["total_slippage"]) <= 1.05 * float(online["total_slippage"]),
        "stage037_broker100_days_not_above_online": int(candidate["days_over_100pct"]) <= int(online["days_over_100pct"]),
    }
    full_period_comparison_pass = bool(all(gates.values()))
    decision = {
        "line_id": "futures_trend_rollover_shape_same_volume",
        "stage": "Stage047",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "identity": identity,
        "period": {"start": str(START.date()), "end": str(END.date())},
        "arms": {arm["arm"]: arm["profile"] for arm in ARMS},
        "candidate_version": stage037_cfg.CANDIDATE_VERSION,
        "candidate_hypothesis": "只读复核Stage037相对当前线上Stage847-C9-15w+Q的完整历史路径，不新增或扫描参数。",
        "overfitting_risk_predeclared": "本次复跑低；Stage037作为历史筛选版本仍保留后验选择风险。",
        "history_contract_C": history_contract,
        "delay_contract_C": delay_contract,
        "filter_contract": filter_contract,
        "gates": gates,
        "full_period_comparison_pass": full_period_comparison_pass,
        "promote_to_official": False,
        "decision": (
            "stage047_stage037_beats_current_online_full_period_only_no_automatic_promotion"
            if full_period_comparison_pass
            else "stage047_stage037_does_not_beat_current_online_full_period"
        ),
        "comparisons": comparison.to_dict(orient="records"),
        "order_api_called_count": 0,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
    }

    trades = pd.concat(
        [all_frames[arm]["trades"] for arm in ("A", "C")],
        ignore_index=True,
        sort=False,
    )
    frames = {
        SUMMARY_NAME: summary,
        COMPARISON_NAME: comparison,
        CURVE_NAME: curve,
        FILTER_NAME: filter_diagnostics,
        FILTER_CONTRACT_NAME: pd.DataFrame([filter_contract]),
        TRADES_NAME: trades,
    }
    _publish(frames, decision, _report(summary, comparison, decision), _plot(curve))
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
