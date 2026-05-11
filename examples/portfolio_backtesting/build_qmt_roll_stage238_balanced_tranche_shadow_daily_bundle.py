from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_SHORT_ALIAS, OFFICIAL_STAGE78_VERSION, build_official_stage78_manifest
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage238_balanced_tranche_shadow_daily_bundle_v1"
OUTPUT_PREFIX = "qmt_roll_stage238_balanced_tranche_shadow_daily_bundle"

STAGE186_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_stage186_stage78_2026_50w_cold_start_summary_stage186_stage78_2026_50w_cold_start_v1.json"
STAGE186_SIGNAL_PLAN_PATH = OUTPUT_DIR / "qmt_roll_stage186_stage78_2026_50w_cold_start_signal_plan_stage186_stage78_2026_50w_cold_start_v1.csv"
STAGE186_DAILY_REPORT_PATH = OUTPUT_DIR / "qmt_roll_stage186_stage78_2026_50w_cold_start_daily_report_stage186_stage78_2026_50w_cold_start_v1.md"

STAGE237_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_stage237_balanced_tranche_shadow_ledger_summary_stage237_balanced_tranche_shadow_ledger_v1.csv"
STAGE237_LEDGER_PATH = OUTPUT_DIR / "qmt_roll_stage237_balanced_tranche_shadow_ledger_ledger_stage237_balanced_tranche_shadow_ledger_v1.csv"
STAGE237_TRANSFERS_PATH = OUTPUT_DIR / "qmt_roll_stage237_balanced_tranche_shadow_ledger_transfers_stage237_balanced_tranche_shadow_ledger_v1.csv"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _to_markdown(df: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
    if df.empty:
        return "_empty_"
    view = df.loc[:, [c for c in columns if c in df.columns]].head(max_rows).copy()
    for col in view.columns:
        if pd.api.types.is_numeric_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{float(x):,.4f}" if abs(float(x)) < 1000 else f"{float(x):,.0f}")
    return view.to_markdown(index=False)


def _build_deployment_judgement(cold_summary: pd.Series, risk_snapshot: dict[str, Any]) -> list[str]:
    gap = float(cold_summary.get("current_threshold_gap", 0.0))
    production = float(cold_summary.get("end_production_equity", 0.0))
    locked = float(cold_summary.get("end_locked_equity", 0.0))
    expansion = float(cold_summary.get("end_expansion_equity", 0.0))
    level = str(risk_snapshot.get("risk_level", ""))
    lines: list[str] = []
    if locked <= 0 and expansion <= 0:
        lines.append("当前仍处于纯生产账户阶段，尚未进入锁盈保护区间。")
    if gap > 0:
        lines.append(f"按 `balanced_tranche_v1` 口径，生产账户还需增加 `{gap:,.0f}` 才会首次触发提款。")
    if level in {"watch", "review", "stop"}:
        lines.append(f"当前影子盘风险等级为 `{level}`，应优先遵守风险闸门，不应因为未触发提款阈值而主动加杠杆。")
    if production > 0 and gap > production * 5:
        lines.append("从当前资本水平看，近期部署重点应是活下来并保持纪律，而不是讨论锁盈分配。")
    return lines or ["当前无额外部署判断。"]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    stage186_summary = _read_json(STAGE186_SUMMARY_PATH)
    signal_plan = pd.read_csv(STAGE186_SIGNAL_PLAN_PATH)
    stage237_summary = pd.read_csv(STAGE237_SUMMARY_PATH)
    stage237_ledger = pd.read_csv(STAGE237_LEDGER_PATH)
    stage237_transfers = pd.read_csv(STAGE237_TRANSFERS_PATH) if STAGE237_TRANSFERS_PATH.exists() else pd.DataFrame()

    target_date = str(stage186_summary.get("target_date", ""))
    risk_snapshot = stage186_summary.get("risk_snapshot", {})
    statistics = stage186_summary.get("statistics", {})
    cold_summary = stage237_summary[stage237_summary["scenario_name"].eq("cold_start_2026")].iloc[0]
    history_summary = stage237_summary[stage237_summary["scenario_name"].eq("full_history_2020_2026")].iloc[0]

    stage237_ledger["date"] = pd.to_datetime(stage237_ledger["date"], errors="coerce")
    cold_ledger = stage237_ledger[stage237_ledger["scenario_name"].eq("cold_start_2026")].copy()
    if target_date:
        cold_ledger = cold_ledger[cold_ledger["date"] <= pd.Timestamp(target_date)].copy()
    cold_tail = cold_ledger.tail(15).copy()

    history_transfers = stage237_transfers[stage237_transfers["scenario_name"].eq("full_history_2020_2026")].copy()
    deployment_judgement = _build_deployment_judgement(cold_summary, risk_snapshot)

    date_key = target_date.replace("-", "") if target_date else "latest"
    summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{date_key}_{MODEL_TAG}.json"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_report_{date_key}_{MODEL_TAG}.md"

    summary = {
        "model_tag": MODEL_TAG,
        "trade_date": target_date,
        "strategy_version": OFFICIAL_STAGE78_VERSION,
        "official_alias": OFFICIAL_STAGE78_SHORT_ALIAS,
        "signal_count": int(stage186_summary.get("target_signal_count", len(signal_plan))),
        "risk_snapshot": risk_snapshot,
        "statistics": statistics,
        "balanced_tranche_status": {
            "current_total_equity": float(cold_summary["end_total_equity"]),
            "current_production_equity": float(cold_summary["end_production_equity"]),
            "current_locked_equity": float(cold_summary["end_locked_equity"]),
            "current_expansion_equity": float(cold_summary["end_expansion_equity"]),
            "gap_to_first_sweep": float(cold_summary["current_threshold_gap"]),
            "historical_first_sweep_date": str(history_summary["first_sweep_date"]),
            "historical_total_swept": float(history_summary["total_swept"]),
            "historical_end_locked_equity": float(history_summary["end_locked_equity"]),
            "historical_end_expansion_equity": float(history_summary["end_expansion_equity"]),
        },
        "deployment_judgement": deployment_judgement,
        "source_artifacts": {
            "stage186_summary": str(STAGE186_SUMMARY_PATH.resolve()),
            "stage186_signal_plan": str(STAGE186_SIGNAL_PLAN_PATH.resolve()),
            "stage186_daily_report": str(STAGE186_DAILY_REPORT_PATH.resolve()),
            "stage237_summary": str(STAGE237_SUMMARY_PATH.resolve()),
            "stage237_ledger": str(STAGE237_LEDGER_PATH.resolve()),
            "stage237_transfers": str(STAGE237_TRANSFERS_PATH.resolve()),
        },
        "official_manifest": build_official_stage78_manifest(),
        "outputs": {
            "summary_json": str(summary_path.resolve()),
            "daily_report": str(report_path.resolve()),
        },
        "judgement": {
            "overfit_before": "否。不修改策略参数，只把信号日报和三账户账本拼成部署日报。",
            "continue_before": "是。部署日报比单一信号日报更接近实盘治理需要。",
            "overfit_after": "否。没有根据单日报结果调参或改变账户阈值。",
            "continue_after": "是。下一步可接真实QMT账户余额，实现从回放权益到账户实值的切换。",
        },
    }

    lines = [
        "# Stage238 balanced_tranche 三账户部署日报",
        "",
        f"- 交易日：`{target_date}`",
        f"- 策略版本：`{OFFICIAL_STAGE78_VERSION}`",
        f"- 策略别名：`{OFFICIAL_STAGE78_SHORT_ALIAS}`",
        "- 日报类型：`signal_daily + deployment_ledger_daily`",
        "- 部署制度：`balanced_tranche_v1`",
        "",
        "## 今日信号结论",
        "",
        f"- 风险级别：`{risk_snapshot.get('risk_level', '')}`",
        f"- 是否允许影子盘记录：`{risk_snapshot.get('allow_shadow_record', '')}`",
        f"- 是否允许真实新增开仓：`{risk_snapshot.get('allow_real_new_orders', '')}`",
        f"- 触发原因：`{', '.join(risk_snapshot.get('reasons', []))}`",
        f"- 当日理论信号数：`{int(stage186_summary.get('target_signal_count', len(signal_plan)))}`",
        f"- 期末权益：`{float(risk_snapshot.get('balance', 0.0)):,.0f}`",
        f"- 当前回撤：`{float(risk_snapshot.get('drawdown_pct_abs', 0.0)):.4f}%`",
        "",
        "## 信号计划",
        "",
        _to_markdown(
            signal_plan,
            [
                "shadow_session_id",
                "vt_symbol",
                "direction",
                "offset",
                "volume",
                "theoretical_price",
                "real_t1_open_proxy_price",
                "proxy_quality",
            ],
            max_rows=20,
        ),
        "",
        "## 三账户状态",
        "",
        f"- 生产账户：`{float(cold_summary['end_production_equity']):,.0f}`",
        f"- 锁盈账户：`{float(cold_summary['end_locked_equity']):,.0f}`",
        f"- 扩张储备：`{float(cold_summary['end_expansion_equity']):,.0f}`",
        f"- 总权益：`{float(cold_summary['end_total_equity']):,.0f}`",
        f"- 离首次提款阈值还差：`{float(cold_summary['current_threshold_gap']):,.0f}`",
        "",
        "## 历史部署锚点",
        "",
        f"- 历史首次提款日期：`{history_summary['first_sweep_date']}`",
        f"- 历史累计提款：`{float(history_summary['total_swept']):,.0f}`",
        f"- 历史期末锁盈：`{float(history_summary['end_locked_equity']):,.0f}`",
        f"- 历史期末扩张储备：`{float(history_summary['end_expansion_equity']):,.0f}`",
        "",
        "## 近期冷启动账本",
        "",
        _to_markdown(
            cold_tail,
            [
                "date",
                "source_balance",
                "production_equity",
                "locked_equity",
                "expansion_equity",
                "total_equity",
                "event",
                "threshold_gap_to_next_sweep",
            ],
            max_rows=15,
        ),
        "",
        "## 历史提款事件",
        "",
        _to_markdown(
            history_transfers,
            [
                "date",
                "event_type",
                "sweep_amount",
                "locked_add",
                "expansion_add",
                "production_after",
            ],
            max_rows=15,
        ),
        "",
        "## 部署判断",
        "",
    ]
    for item in deployment_judgement:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 输出文件",
            "",
            f"- summary_json: `{summary_path}`",
            f"- daily_report: `{report_path}`",
            "",
            "## 反思",
            "",
            f"- 运行前过拟合反思：{summary['judgement']['overfit_before']}",
            f"- 运行后过拟合反思：{summary['judgement']['overfit_after']}",
            f"- 运行前继续价值反思：{summary['judgement']['continue_before']}",
            f"- 运行后继续价值反思：{summary['judgement']['continue_after']}",
            "",
        ]
    )

    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary["outputs"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
