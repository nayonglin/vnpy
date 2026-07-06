from __future__ import annotations

from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage110"
MODEL_TAG = "stage110_jd_minute_backfill_batch4_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage110_jd_minute_backfill_batch4"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage110_jd_minute_backfill_batch4"
STAGES_DIR = LINE_DIR / "stages"

STAGE052_SCRIPT = LINE_DIR / "tools" / "stage052_tqsdk_jd_minute_backfill.py"

BACKFILL_PLAN_PATH = OUT / f"{OUTPUT_PREFIX}_backfill_plan_{MODEL_TAG}.csv"
BACKFILL_STATUS_PATH = OUT / f"{OUTPUT_PREFIX}_backfill_status_{MODEL_TAG}.csv"
FILE_MANIFEST_PATH = OUT / f"{OUTPUT_PREFIX}_file_manifest_{MODEL_TAG}.csv"
BEFORE_COVERAGE_PATH = OUT / f"{OUTPUT_PREFIX}_before_minute_coverage_{MODEL_TAG}.csv"
AFTER_COVERAGE_PATH = OUT / f"{OUTPUT_PREFIX}_after_minute_coverage_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

ENABLE_DOWNLOAD = os.getenv("STAGE110_ENABLE_DOWNLOAD", "0").strip() == "1"
MAX_SYMBOLS = int(os.getenv("STAGE110_MAX_SYMBOLS", "6"))
MAX_SECONDS_PER_SYMBOL = int(os.getenv("STAGE110_MAX_SECONDS_PER_SYMBOL", "140"))

SOURCE_LINKS = {
    "tqsdk_reference": "https://tqsdk-python.readthedocs.io/en/stable/reference/",
    "tqsdk_backtest": "https://doc.shinnytech.com/tqsdk/latest/advanced/backtest.html",
    "trend_following_drawdown": "https://www.man.com/insights/is-this-time-different",
    "trend_following_diversification": "https://www.returnstacked.com/managed-futures-trend-following/",
    "github_pytrendfollow": "https://github.com/chrism2671/PyTrendFollow",
}


def _load_stage052():
    spec = importlib.util.spec_from_file_location("stage052_tqsdk_jd_minute_backfill", STAGE052_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {STAGE052_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    if isinstance(value, (pd.Timestamp, datetime)):
        return "" if pd.isna(value) else value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows else frame.copy()
    return data.to_markdown(index=False)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _input_audit(paths: list[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.exists():
            stat = path.stat()
            rows.append(
                {
                    "path": str(path),
                    "exists": True,
                    "bytes": int(stat.st_size),
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    "sha256": _sha256(path),
                }
            )
        else:
            rows.append({"path": str(path), "exists": False, "bytes": 0, "mtime": "", "sha256": ""})
    return pd.DataFrame(rows)


def _empty_status() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "contract_vt",
            "tq_symbol",
            "download_start_datetime",
            "download_end_datetime",
            "status",
            "rows",
            "first_bar_datetime",
            "last_bar_datetime",
            "elapsed_seconds",
            "output_path",
            "sha256",
            "message",
        ]
    )


def _coverage_counts(coverage: pd.DataFrame) -> dict[str, Any]:
    if coverage.empty:
        return {"total": 0, "ready": 0, "missing": 0, "missing_by_product": {}}
    ready = coverage["minute_file_ready"].astype(bool)
    missing = coverage[~ready].copy()
    return {
        "total": int(len(coverage)),
        "ready": int(ready.sum()),
        "missing": int((~ready).sum()),
        "missing_by_product": {
            str(k): int(v) for k, v in missing.groupby("product_vt_symbol").size().sort_index().items()
        },
    }


def _make_decision(plan: pd.DataFrame, status: pd.DataFrame, before_coverage: pd.DataFrame, after_coverage: pd.DataFrame) -> dict[str, Any]:
    rows = pd.to_numeric(status.get("rows", pd.Series(dtype=float)), errors="coerce").fillna(0).astype(int)
    success_mask = status.get("status", pd.Series(dtype=object)).astype(str).eq("downloaded") & rows.gt(0)
    success_count = int(success_mask.sum())
    downloaded_rows = int(rows.sum())
    before_counts = _coverage_counts(before_coverage)
    after_counts = _coverage_counts(after_coverage)
    if not ENABLE_DOWNLOAD:
        decision = "stage110_jd_minute_backfill_batch4_dry_plan_only"
    elif success_count == int(len(plan)) and success_count > 0:
        decision = "stage110_jd_minute_backfill_batch4_success_margin_still_blocked"
    elif success_count > 0:
        decision = "stage110_jd_minute_backfill_batch4_partial_success_margin_still_blocked"
    else:
        decision = "stage110_jd_minute_backfill_batch4_no_success_keep_stage052_state"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "download_enabled": bool(ENABLE_DOWNLOAD),
        "max_symbols": int(MAX_SYMBOLS),
        "max_seconds_per_symbol": int(MAX_SECONDS_PER_SYMBOL),
        "planned_contract_count": int(len(plan)),
        "download_status_count": int(len(status)),
        "download_success_contract_count": success_count,
        "downloaded_minute_rows": downloaded_rows,
        "before_coverage": before_counts,
        "after_coverage": after_counts,
        "before_missing": int(before_counts["missing"]),
        "after_missing": int(after_counts["missing"]),
        "remaining_jd_missing": int(after_counts["missing_by_product"].get("jd.DCE", 0)),
        "remaining_blocker": "jd_contract_daily_margin_history",
        "ready_for_true_ledger_replay": False,
        "strategy_rule_created": False,
        "official_live_strategy_changed": False,
        "true_engine_run": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "formal_ab_triggered": False,
        "source_links": SOURCE_LINKS,
        "external_research_judgment": (
            "公开趋势跟随资料更支持分散与独立收益腿来处理长期水下，而不是止损补丁；"
            "本阶段只补 Stage208/xsmom 独立收益腿所需 jd 分钟数据，不将下载成功解释为策略 alpha。"
        ),
        "overfit_reflection_before": "否。本阶段只补 P0 鸡蛋分钟缺口，不按收益表现选择合约或参数。",
        "overfit_reflection_after": "否。下载成功只降低数据阻塞；保证金历史缺失前仍禁止 true ledger replay。",
        "continue_value_before": "有。Stage086 已排除低价值 stop/retry/预算锁路线，Stage208 真承载是更结构性的下一路。",
        "continue_value_after": "有，但下一步必须继续补剩余 jd 分钟线并寻找逐日保证金；不能跳过数据口径硬跑。",
        "outputs": {
            "backfill_plan": str(BACKFILL_PLAN_PATH),
            "backfill_status": str(BACKFILL_STATUS_PATH),
            "file_manifest": str(FILE_MANIFEST_PATH),
            "before_coverage": str(BEFORE_COVERAGE_PATH),
            "after_coverage": str(AFTER_COVERAGE_PATH),
            "input_audit": str(INPUT_AUDIT_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(decision: dict[str, Any], plan: pd.DataFrame, status: pd.DataFrame, before_coverage: pd.DataFrame, after_coverage: pd.DataFrame, file_manifest: pd.DataFrame) -> None:
    lines = [
        "# Stage110 jd minute backfill batch4",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：数据补齐；不回测收益，不改策略，不连接 CTP，不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- 外部资料对趋势跟随水下期的共同指向是分散/独立收益腿/风险预算，而不是继续调止损重进形状。",
        "- 本阶段判断：继续补 Stage208/xsmom 真承载数据阻塞有价值；但下载成功不是策略成功。",
        "",
        "## Coverage Delta",
        "",
        f"- before_missing：`{decision['before_missing']}`",
        f"- after_missing：`{decision['after_missing']}`",
        f"- remaining_jd_missing：`{decision['remaining_jd_missing']}`",
        f"- remaining_blocker：`{decision['remaining_blocker']}`",
        "",
        "## Backfill Plan",
        "",
        _md_table(plan, max_rows=80),
        "",
        "## Backfill Status",
        "",
        _md_table(status, max_rows=80),
        "",
        "## File Manifest",
        "",
        _md_table(file_manifest, max_rows=80),
        "",
        "## Coverage After Missing",
        "",
        _md_table(after_coverage[~after_coverage["minute_file_ready"].astype(bool)], max_rows=80),
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
        "",
        "## 输出",
        "",
        f"- backfill_plan：`{BACKFILL_PLAN_PATH}`",
        f"- backfill_status：`{BACKFILL_STATUS_PATH}`",
        f"- file_manifest：`{FILE_MANIFEST_PATH}`",
        f"- before_coverage：`{BEFORE_COVERAGE_PATH}`",
        f"- after_coverage：`{AFTER_COVERAGE_PATH}`",
        f"- input_audit：`{INPUT_AUDIT_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], plan: pd.DataFrame, status: pd.DataFrame, after_coverage: pd.DataFrame) -> Path:
    stage_path = STAGES_DIR / f"{datetime.now():%Y%m%d_%H%M}_stage110_jd_minute_backfill_batch4.md"
    lines = [
        "# Stage110 jd minute backfill batch4",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{decision['generated_at']}",
        "- 阶段性质：数据补齐；不回测收益，不改官方 live config、不连接 CTP、不调用下单",
        "- 是否重要突破：否",
        "- 是否触发A/B：否",
        "",
        "## 外部调研与判断",
        "",
        "- 外部趋势跟随资料与 GitHub 示例支持分散/独立收益腿/风险预算方向；本阶段选择 data-first 继续补 Stage208/xsmom 真承载数据。",
        "- 我的判断：下载分钟线只是在清阻塞，不代表策略收益改进；保证金历史未补前仍不能跑 true ledger replay。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage110_jd_minute_backfill_batch4.py`",
        "- 新增参数：`STAGE110_ENABLE_DOWNLOAD`、`STAGE110_MAX_SYMBOLS`、`STAGE110_MAX_SECONDS_PER_SYMBOL`。",
        "- 修改参数：无正式策略参数修改。",
        "- 删除参数：无。",
        "",
        "## 结果",
        "",
        f"- decision：`{decision['decision']}`",
        f"- download_enabled：`{decision['download_enabled']}`",
        f"- planned_contract_count：`{decision['planned_contract_count']}`",
        f"- download_success_contract_count：`{decision['download_success_contract_count']}`",
        f"- downloaded_minute_rows：`{decision['downloaded_minute_rows']}`",
        f"- before_missing：`{decision['before_missing']}`",
        f"- after_missing：`{decision['after_missing']}`",
        f"- remaining_jd_missing：`{decision['remaining_jd_missing']}`",
        "- ready_for_true_ledger_replay：`False`",
        f"- remaining_blocker：`{decision['remaining_blocker']}`",
        "- 策略变更：`False`",
        "- true engine run：`False`",
        "- order API：`0`",
        "- CTP：`False`",
        "",
        "## Backfill Plan",
        "",
        _md_table(plan, max_rows=80),
        "",
        "## Backfill Status",
        "",
        _md_table(status, max_rows=80),
        "",
        "## Remaining Missing",
        "",
        _md_table(after_coverage[~after_coverage["minute_file_ready"].astype(bool)], max_rows=80),
        "",
        "## 回测记录字段",
        "",
        "- 本阶段不新增回测，因此不新增期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率。",
        "",
        "## 过拟合反思",
        "",
        f"- 运行前：{decision['overfit_reflection_before']}",
        f"- 运行后：{decision['overfit_reflection_after']}",
        "",
        "## 继续价值反思",
        "",
        f"- 运行前：{decision['continue_value_before']}",
        f"- 运行后：{decision['continue_value_after']}",
        "",
        "## 输出文件",
        "",
        f"- report：`{REPORT_PATH}`",
        f"- backfill_plan：`{BACKFILL_PLAN_PATH}`",
        f"- backfill_status：`{BACKFILL_STATUS_PATH}`",
        f"- file_manifest：`{FILE_MANIFEST_PATH}`",
        f"- before_coverage：`{BEFORE_COVERAGE_PATH}`",
        f"- after_coverage：`{AFTER_COVERAGE_PATH}`",
        f"- input_audit：`{INPUT_AUDIT_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    stage_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return stage_path


def run() -> dict[str, Any]:
    mod = _load_stage052()
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    mod.BACKFILL_ROOT.mkdir(parents=True, exist_ok=True)

    manifest = mod._read_csv(mod.MINUTE_GAP_MANIFEST_PATH)
    before_index = mod.build_minute_file_index()
    before_coverage = mod.audit_manifest_coverage(manifest, before_index)
    plan = mod.build_backfill_plan(manifest, before_index, MAX_SYMBOLS)

    if ENABLE_DOWNLOAD and not plan.empty:
        status, _ = mod.run_backfill_download(plan, MAX_SECONDS_PER_SYMBOL)
    else:
        status = _empty_status()

    after_index = mod.build_minute_file_index()
    after_coverage = mod.audit_manifest_coverage(manifest, after_index)
    file_manifest = mod.build_file_manifest(status)
    input_audit = _input_audit([STAGE052_SCRIPT, mod.MINUTE_GAP_MANIFEST_PATH, *[Path(p) for p in plan.get("output_path", pd.Series(dtype=str)).astype(str).tolist()]])
    decision = _make_decision(plan, status, before_coverage, after_coverage)

    plan.to_csv(BACKFILL_PLAN_PATH, index=False, encoding="utf-8-sig")
    status.to_csv(BACKFILL_STATUS_PATH, index=False, encoding="utf-8-sig")
    file_manifest.to_csv(FILE_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    before_coverage.to_csv(BEFORE_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    after_coverage.to_csv(AFTER_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, plan, status, before_coverage, after_coverage, file_manifest)
    stage_path = _write_stage_record(decision, plan, status, after_coverage)
    decision["outputs"]["stage_record"] = str(stage_path)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"stage_record={stage_path}")
    return decision


if __name__ == "__main__":
    run()
