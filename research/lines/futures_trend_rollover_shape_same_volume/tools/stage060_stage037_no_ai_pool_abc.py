from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import shutil
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
TOOLS_DIR = Path(__file__).resolve().parent
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
for directory in (TOOLS_DIR, PORTFOLIO_DIR):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import qmt_roll_candidate_stage060_stage037_no_ai_config as candidate_cfg  # noqa: E402
from main_contract_mapping import load_product_universe_symbols  # noqa: E402
import stage056_stage037_ai_top14_plus_fu_ac as s56  # noqa: E402


LINE_ID = "futures_trend_rollover_shape_same_volume"
STAGE = "Stage060"
BASE_MASTER_COMMIT = s56.BASE_MASTER_COMMIT
BASE_RULESET_VERSION = s56.BASE_RULESET_VERSION
BASE_RELEASE_ID = "m0016_20260829T034012+0800_374df2d52e4f"
BASE_SOURCE_COMMIT = "374df2d52e4f17220c5e2d4cae76f50d45bec47d"
START = pd.Timestamp("2018-01-01")
EXPECTED_FIRST_TRADING_DAY = pd.Timestamp("2018-01-02")
END = pd.Timestamp("2026-08-28")
TOTAL_PRODUCT_COUNT = 19

LINE_DIR = Path(__file__).resolve().parents[1]
STAGE056_DIR = s56.OUTPUT_DIR
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage060_stage037_no_ai_pool"
SUMMARY_NAME = "stage060_summary.csv"
COMPARISON_NAME = "stage060_comparison.csv"
CURVE_NAME = "stage060_equity_curve.csv"
TRADES_NAME = "stage060_candidate_trades.csv"
DECISION_NAME = "stage060_decision.json"
REPORT_NAME = "stage060_report.md"
CHART_NAME = "stage060_equity_abc.png"

ARMS: tuple[dict[str, str], ...] = (
    {
        "arm": "A",
        "profile": "stage060_A_stage037_top8_plus_fu",
        "label": "A: Stage037 AI Top8+fu（9品种）",
        "plot_label": "A Stage037 Top8+fu",
        "color": "#2563eb",
    },
    {
        "arm": "B",
        "profile": "stage060_B_stage056_top14_plus_fu",
        "label": "B: Stage056 AI Top14+fu（15品种）",
        "plot_label": "B Stage056 Top14+fu",
        "color": "#16a34a",
    },
    {
        "arm": "C",
        "profile": "stage060_C_stage037_no_ai_static18_plus_fu",
        "label": "C: Stage037 关闭AI选品（19品种）",
        "plot_label": "C Stage037 no AI pool (19)",
        "color": "#dc2626",
    },
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=PROJECT_DIR, check=True, capture_output=True, text=True
    ).stdout.strip()


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_offline_identity_contract(
    checkout_identity: dict[str, Any],
    production_identity: dict[str, Any],
    remote_master: str,
) -> dict[str, Any]:
    expected = {
        "strategy_version": "official_live_stage847_c9_15w_stage819_05r_stop_retry_once",
        "ruleset_version": BASE_RULESET_VERSION,
        "material_release_id": BASE_RELEASE_ID,
        "source_commit": BASE_SOURCE_COMMIT,
    }
    actual = {key: checkout_identity.get(key) for key in expected}
    if actual != expected or remote_master != BASE_MASTER_COMMIT:
        raise RuntimeError(
            "stage060_stage037_identity_mismatch:"
            f"actual={actual}:expected={expected}:remote={remote_master}"
        )
    production_matches = all(
        production_identity.get(key) == value for key, value in expected.items()
    )
    return {
        "research_protocol": "explicit_stage037_stage056_no_ai_offline_ablation",
        "checkout_stage037_identity_pass": True,
        "production_identity_matches_stage037": bool(production_matches),
        "formal_production_ac_compliant": False,
        "promotion_permitted": False,
    }


def _preflight() -> dict[str, Any]:
    checkout = asdict(s56.assert_official_checkout_matches_active_material(PROJECT_DIR))
    production = asdict(
        s56.assert_official_checkout_matches_active_material(s56.PRODUCTION_ROOT)
    )
    remote_master = _git("rev-parse", "origin/master")
    evidence = _assert_offline_identity_contract(checkout, production, remote_master)
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASE_MASTER_COMMIT, "HEAD"],
        cwd=PROJECT_DIR,
        check=True,
    )
    if candidate_cfg.override_diff() != {
        "enable_ai_product_pool_filter": (True, False)
    }:
        raise RuntimeError(f"stage060_override_scope_drift:{candidate_cfg.override_diff()}")
    universe_path = Path(
        candidate_cfg.build_candidate_overrides()["product_universe_csv_path"]
    )
    products = load_product_universe_symbols(universe_path)
    if len(products) != TOTAL_PRODUCT_COUNT or len(set(products)) != TOTAL_PRODUCT_COUNT:
        raise RuntimeError(f"stage060_universe_contract_failed:{products}")
    stage056_decision = STAGE056_DIR / s56.DECISION_NAME
    for path in (s56.DATABASE_PATH, universe_path, stage056_decision):
        if not path.exists():
            raise RuntimeError(f"stage060_missing_input:{path}")
    return {
        **evidence,
        "checkout_identity": checkout,
        "production_identity": production,
        "checkout_head": _git("rev-parse", "HEAD"),
        "remote_master": remote_master,
        "database_path": str(s56.DATABASE_PATH.resolve()),
        "database_sha256": _file_sha256(s56.DATABASE_PATH),
        "product_universe_path": str(universe_path.resolve()),
        "product_universe_sha256": _file_sha256(universe_path),
        "product_universe": products,
        "stage056_decision_sha256": _file_sha256(stage056_decision),
    }


def _relabel(frame: pd.DataFrame, source_arm: str, target: dict[str, str]) -> pd.DataFrame:
    result = frame[frame["experiment_arm"].astype(str).eq(source_arm)].copy()
    result["experiment_arm"] = target["arm"]
    for column in ("profile", "variant", "arm"):
        if column in result.columns:
            result[column] = target["profile"]
    if "label" in result.columns:
        result["label"] = target["label"]
    return result


def _load_reused_ab() -> tuple[pd.DataFrame, pd.DataFrame]:
    source_summary = pd.read_csv(STAGE056_DIR / s56.SUMMARY_NAME)
    source_curve = pd.read_csv(STAGE056_DIR / s56.CURVE_NAME)
    summaries = [
        _relabel(source_summary, "A", ARMS[0]),
        _relabel(source_summary, "C", ARMS[1]),
    ]
    curves = [
        _relabel(source_curve, "A", ARMS[0]),
        _relabel(source_curve, "C", ARMS[1]),
    ]
    summary = pd.concat(summaries, ignore_index=True, sort=False)
    curve = pd.concat(curves, ignore_index=True, sort=False)
    if len(summary) != 2 or set(summary["experiment_arm"].astype(str)) != {"A", "B"}:
        raise RuntimeError("stage060_reused_ab_identity_failed")
    return summary, curve


def _run_c(metadata: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    arm = ARMS[2]
    original_builder = s56.s28.s901.build_official_live_strategy_overrides
    try:
        s56.s28.s901.build_official_live_strategy_overrides = (
            lambda: candidate_cfg.build_candidate_overrides()
        )
        combined, frames, live_spec = s56.s28.s901._run_live_c9(metadata, START, END)
    finally:
        s56.s28.s901.build_official_live_strategy_overrides = original_builder
    capital = replace(live_spec.capital, variant=arm["profile"], label=arm["label"])
    metric_spec = replace(live_spec, capital=capital, profile=arm["profile"])
    summary, curve = s56.s28.s827._metric(
        {"profile": arm["profile"], "spec": metric_spec}, combined
    )
    summary["experiment_arm"] = "C"
    summary["window_name"] = "full_2018_20260828"
    summary["window_label"] = "2018-01-01 independent start to 2026-08-28"
    curve["experiment_arm"] = "C"
    for frame in frames.values():
        if not frame.empty:
            frame["experiment_arm"] = "C"
    return summary, curve, frames


def _assert_coverage(summary: pd.DataFrame, curve: pd.DataFrame) -> None:
    if len(summary) != 3 or set(summary["experiment_arm"].astype(str)) != {"A", "B", "C"}:
        raise RuntimeError("stage060_arm_identity_failed")
    reference: pd.DatetimeIndex | None = None
    for arm in ("A", "B", "C"):
        dates = pd.DatetimeIndex(
            pd.to_datetime(
                curve[curve["experiment_arm"].astype(str).eq(arm)]["date"],
                errors="raise",
                format="mixed",
            ).dt.normalize()
        )
        if reference is None:
            reference = dates
        if (
            dates.duplicated().any()
            or not dates.equals(reference)
            or dates.min() != EXPECTED_FIRST_TRADING_DAY
            or dates.max() != END
        ):
            raise RuntimeError(f"stage060_full_period_coverage_failed:{arm}")


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    indexed = summary.set_index("experiment_arm")
    metrics = (
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "max_broker10_margin_to_equity_pct",
        "days_over_100pct",
        "account_survival_pass",
    )
    row: dict[str, Any] = {"comparison": "stage037_vs_stage056_vs_stage037_no_ai"}
    for arm in ("A", "B", "C"):
        for metric in metrics:
            row[f"{arm}_{metric}"] = float(indexed.loc[arm, metric])
    for reference in ("A", "B"):
        for metric in metrics:
            row[f"delta_C_minus_{reference}_{metric}"] = (
                row[f"C_{metric}"] - row[f"{reference}_{metric}"]
            )
    return pd.DataFrame([row])


def _full_period_gates(values: dict[str, Any]) -> dict[str, bool]:
    return {
        "return_not_lower_than_stage037": bool(
            values["C_total_return_pct"] >= values["A_total_return_pct"]
        ),
        "drawdown_worsening_le_2pp": bool(
            values["A_max_dd_pct"] - values["C_max_dd_pct"] <= 2.0
        ),
        "sharpe_not_lower_by_more_than_002": bool(
            values["C_sharpe"] >= values["A_sharpe"] - 0.02
        ),
        "slippage_le_105pct_of_stage037": bool(
            values["C_total_slippage"] <= values["A_total_slippage"] * 1.05
        ),
        "account_survival_pass": bool(values["C_account_survival_pass"]),
        "broker10_days_over_100_not_worse": bool(
            values["C_days_over_100pct"] <= values["A_days_over_100pct"]
        ),
    }


def _plot(curve: pd.DataFrame) -> bytes:
    fig, ax = plt.subplots(figsize=(14, 6))
    for arm in ARMS:
        frame = curve[curve["experiment_arm"].astype(str).eq(arm["arm"])].sort_values("date")
        ax.plot(
            pd.to_datetime(frame["date"]),
            pd.to_numeric(frame["account_equity"], errors="coerce") / 10_000.0,
            color=arm["color"],
            linewidth=1.35,
            label=arm["plot_label"],
        )
    ax.set_title("Stage060 Full Period: Stage037 vs Stage056 vs No AI Pool")
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
    lines = [
        "# Stage060 Stage037 关闭 AI 选品全周期 A/B/C",
        "",
        f"区间：`{START.date()}` 至 `{END.date()}`。C 相对 A 的唯一变量是关闭 AI 选品过滤；底层策略、风险参数、19品种配置全集均不变。",
        "",
        "| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 非零交易日胜率 | broker10峰值 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in ARMS:
        row = indexed.loc[arm["arm"]]
        lines.append(
            f"| {arm['label']} | {row['end_equity']:,.2f} | {row['total_return_pct']:.4f}% | "
            f"{row['max_dd_pct']:.4f}% | {row['sharpe']:.6f} | {row['total_slippage']:,.0f} | "
            f"{int(row['total_trade_count'])} | {row['nonzero_daily_win_rate_pct']:.4f}% | "
            f"{row['max_broker10_margin_to_equity_pct']:.4f}% |"
        )
    values = comparison.iloc[0]
    lines.extend(
        [
            "",
            "## 单变量与门禁",
            "",
            "- C 仅把 `enable_ai_product_pool_filter` 从 `True` 改为 `False`，AI 文件仍保留但不参与准入判断。",
            f"- C 相对 A：总收益 `{values['delta_C_minus_A_total_return_pct']:+.4f}pp`，最大回撤 `{values['delta_C_minus_A_max_dd_pct']:+.4f}pp`，Sharpe `{values['delta_C_minus_A_sharpe']:+.6f}`，滑点 `{values['delta_C_minus_A_total_slippage']:+,.0f}`。",
            f"- 全周期预声明门禁：`{decision['gates']}`。",
            "- 这是离线消融，不连接 CTP、不调用订单 API，也不允许凭单次全周期结果晋升正式版。",
            "",
            "## 反思",
            "",
            f"- 过拟合：{decision['overfitting_assessment']}",
            f"- 继续价值：{decision['continue_value_assessment']}",
            "",
        ]
    )
    return "\n".join(lines)


def _publish(
    frames: dict[str, pd.DataFrame], decision: dict[str, Any], report: str, chart: bytes
) -> None:
    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".stage060.tmp-", dir=OUTPUT_DIR.parent))
    backup = OUTPUT_DIR.with_name(f".stage060.backup-{uuid4().hex}")
    try:
        for filename, frame in frames.items():
            frame.to_csv(temporary / filename, index=False, encoding="utf-8-sig")
        (temporary / DECISION_NAME).write_text(
            json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (temporary / REPORT_NAME).write_text(report, encoding="utf-8")
        (temporary / CHART_NAME).write_bytes(chart)
        if OUTPUT_DIR.exists():
            OUTPUT_DIR.rename(backup)
        temporary.rename(OUTPUT_DIR)
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def main() -> None:
    identity = _preflight()
    reused_summary, reused_curve = _load_reused_ab()
    print(f"[stage060] running C {START.date()}->{END.date()}", flush=True)
    c_summary, c_curve, c_frames = _run_c(s56.s28.s513._metadata())
    summary = pd.concat([reused_summary, c_summary], ignore_index=True, sort=False)
    curve = pd.concat([reused_curve, c_curve], ignore_index=True, sort=False)
    _assert_coverage(summary, curve)
    comparison = _comparison(summary)
    gates = _full_period_gates(comparison.iloc[0].to_dict())
    decision = {
        "line_id": LINE_ID,
        "stage": STAGE,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "base_master_commit": BASE_MASTER_COMMIT,
        "base_ruleset_version": BASE_RULESET_VERSION,
        "candidate_version": candidate_cfg.CANDIDATE_VERSION,
        "period": {"start": str(START.date()), "end": str(END.date())},
        "hypothesis": "Stage037关闭AI选品后，19品种全量准入能否提升收益且不显著恶化风险、成本和容量。",
        "frozen_scope": {
            "only_override": {"enable_ai_product_pool_filter": [True, False]},
            "configured_product_count": TOTAL_PRODUCT_COUNT,
            "ai_files_preserved_but_not_used_for_entry": True,
        },
        "source_identity": identity,
        "gates": gates,
        "all_full_period_gates_pass": all(gates.values()),
        "formal_production_ac_compliant": False,
        "promotion_permitted": False,
        "promote": False,
        "decision": (
            "offline_no_ai_fullperiod_passes_run_multicycle_before_any_promotion"
            if all(gates.values())
            else "offline_no_ai_fullperiod_hard_fail_keep_stage037"
        ),
        "overfitting_assessment": "中等：这是预先冻结的单变量消融，不做参数扫描，但仍是在已有研究结果后提出。",
        "continue_value_assessment": "有：能直接检验AI选品是否贡献了净风险调整收益；若全周期硬门禁失败则不再扩展。",
        "order_api_called_count": 0,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
    }
    trades = c_frames.get("trades", pd.DataFrame()).copy()
    frames = {
        SUMMARY_NAME: summary,
        COMPARISON_NAME: comparison,
        CURVE_NAME: curve,
        TRADES_NAME: trades,
    }
    report = _report(summary, comparison, decision)
    _publish(frames, decision, report, _plot(curve))
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
