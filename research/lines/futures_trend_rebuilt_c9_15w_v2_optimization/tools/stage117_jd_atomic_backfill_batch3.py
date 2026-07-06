from __future__ import annotations

from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage117"
MODEL_TAG = "stage117_jd_atomic_backfill_batch3_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage117_jd_atomic_backfill_batch3"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage117_jd_atomic_backfill_batch3"
TMP_ROOT = OUT / "tmp_downloads"
QUARANTINE_ROOT = OUT / "quarantine_rejected_or_stale"
STAGES_DIR = LINE_DIR / "stages"

STAGE052_SCRIPT = LINE_DIR / "tools" / "stage052_tqsdk_jd_minute_backfill.py"
STAGE112_SCRIPT = LINE_DIR / "tools" / "stage112_strict_minute_content_gate.py"

PLAN_PATH = OUT / f"{OUTPUT_PREFIX}_plan_{MODEL_TAG}.csv"
STATUS_PATH = OUT / f"{OUTPUT_PREFIX}_download_status_{MODEL_TAG}.csv"
TEMP_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_temp_strict_audit_{MODEL_TAG}.csv"
PUBLISH_PATH = OUT / f"{OUTPUT_PREFIX}_publish_manifest_{MODEL_TAG}.csv"
BEFORE_STRICT_PATH = OUT / f"{OUTPUT_PREFIX}_before_strict_manifest_{MODEL_TAG}.csv"
AFTER_STRICT_PATH = OUT / f"{OUTPUT_PREFIX}_after_strict_manifest_{MODEL_TAG}.csv"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

ENABLE_DOWNLOAD = os.getenv("STAGE117_ENABLE_DOWNLOAD", "0").strip() == "1"
MAX_SYMBOLS = int(os.getenv("STAGE117_MAX_SYMBOLS", "2"))
MAX_SECONDS_PER_SYMBOL = int(os.getenv("STAGE117_MAX_SECONDS_PER_SYMBOL", "600"))

SOURCE_LINKS = {
    "tqsdk_data_downloader": "https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.tools.download.html",
    "tqsdk_backtest": "https://doc.shinnytech.com/tqsdk/latest/advanced/backtest.html",
    "vnpy_bardata": "https://github.com/vnpy/vnpy/blob/master/vnpy/trader/object.py",
}


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
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


def _contract_temp_path(contract_vt: str) -> Path:
    symbol, exchange = str(contract_vt).split(".", 1)
    return TMP_ROOT / exchange / f"{symbol}_minute_backtest.csv"


def _contract_final_path(mod052: Any, contract_vt: str) -> Path:
    return mod052._output_path_for_contract(str(contract_vt))


def _quarantine_path(path: Path, reason: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = QUARANTINE_ROOT / reason / path.parent.name / f"{path.stem}_{stamp}{path.suffix}"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def build_atomic_plan(mod052: Any, mod112: Any, before_strict: pd.DataFrame) -> pd.DataFrame:
    data = before_strict.copy()
    data = data[
        data["product_vt_symbol"].astype(str).eq("jd.DCE")
        & data["priority"].astype(str).str.startswith("P0")
        & ~data["strict_ready"].astype(bool)
    ].copy()
    if data.empty:
        return pd.DataFrame()
    data["request_start_ts"] = pd.to_datetime(data["request_start_date"], errors="coerce")
    data["request_end_ts"] = pd.to_datetime(data["request_end_date"], errors="coerce")
    data["observed_price_rows"] = pd.to_numeric(data["observed_price_rows"], errors="coerce").fillna(0).astype(int)
    data = data.dropna(subset=["request_start_ts", "request_end_ts"]).copy()
    data = data.sort_values(["observed_price_rows", "request_start_ts", "contract_vt"], ascending=[True, False, True])
    if MAX_SYMBOLS > 0:
        data = data.head(MAX_SYMBOLS).copy()
    data["tq_symbol"] = data["contract_vt"].map(mod052.to_tqsdk_symbol)
    data["download_start_datetime"] = data["request_start_ts"].map(mod052._download_start).astype(str)
    data["download_end_datetime"] = data["request_end_ts"].map(mod052._download_end).astype(str)
    data["final_output_path"] = data["contract_vt"].map(lambda value: str(_contract_final_path(mod052, str(value))))
    data["output_path"] = data["contract_vt"].map(lambda value: str(_contract_temp_path(str(value))))
    data["stage112_expected_jd_day_rows"] = data["expected_jd_day_rows"]
    columns = [
        "contract_vt",
        "product_vt_symbol",
        "tq_symbol",
        "request_start_date",
        "request_end_date",
        "download_start_datetime",
        "download_end_datetime",
        "observed_price_rows",
        "stage112_expected_jd_day_rows",
        "priority",
        "output_path",
        "final_output_path",
    ]
    return data[columns].reset_index(drop=True)


def quarantine_stale_temp(plan: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in plan.itertuples(index=False):
        path = Path(str(row.output_path))
        if path.exists():
            target = _quarantine_path(path, "stale_pre_run")
            shutil.move(str(path), str(target))
            rows.append(
                {
                    "contract_vt": str(row.contract_vt),
                    "source_path": str(path),
                    "quarantine_path": str(target),
                    "reason": "stale_pre_run",
                }
            )
    return pd.DataFrame(rows)


def audit_temp_downloads(mod112: Any, plan: pd.DataFrame, status: pd.DataFrame) -> pd.DataFrame:
    status_index = status.set_index("contract_vt").to_dict("index") if not status.empty else {}
    rows: list[dict[str, Any]] = []
    for row in plan.itertuples(index=False):
        contract = str(row.contract_vt)
        temp_path = Path(str(row.output_path))
        audit = mod112._audit_one(row, temp_path if temp_path.exists() else None, {})
        status_row = status_index.get(contract, {})
        rows.append(
            {
                "contract_vt": contract,
                "download_status": str(status_row.get("status", "")),
                "download_rows": int(pd.to_numeric(pd.Series([status_row.get("rows", 0)]), errors="coerce").fillna(0).iloc[0]),
                "download_message": str(status_row.get("message", "")),
                "temp_path": str(temp_path),
                "final_output_path": str(row.final_output_path),
                "temp_exists": temp_path.exists(),
                "strict_ready": bool(audit.get("strict_ready", False)),
                "strict_rows": int(audit.get("rows", 0) or 0),
                "expected_jd_day_rows": int(audit.get("expected_jd_day_rows", 0) or 0),
                "blocking_reason": str(audit.get("blocking_reason", "")),
                "first_bar_datetime": str(audit.get("first_bar_datetime", "")),
                "last_bar_datetime": str(audit.get("last_bar_datetime", "")),
                "sha256": str(audit.get("sha256", "")),
            }
        )
    return pd.DataFrame(rows)


def publish_strict_ready(temp_audit: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in temp_audit.itertuples(index=False):
        temp_path = Path(str(row.temp_path))
        final_path = Path(str(row.final_output_path))
        strict_ready = bool(row.strict_ready)
        download_ok = str(row.download_status) == "downloaded"
        old_final_quarantine_path = ""
        temp_quarantine_path = ""
        publish_device_match = False
        if strict_ready and download_ok and temp_path.exists():
            final_path.parent.mkdir(parents=True, exist_ok=True)
            if final_path.exists():
                old_final_target = _quarantine_path(final_path, "existing_final_replaced")
                shutil.move(str(final_path), str(old_final_target))
                old_final_quarantine_path = str(old_final_target)
            publish_device_match = temp_path.stat().st_dev == final_path.parent.stat().st_dev
            if publish_device_match:
                os.replace(str(temp_path), str(final_path))
                action = "published"
            else:
                temp_target = _quarantine_path(temp_path, "cross_device_publish_blocked")
                shutil.move(str(temp_path), str(temp_target))
                temp_quarantine_path = str(temp_target)
                action = "quarantined"
        elif temp_path.exists():
            reason = "strict_rejected" if not strict_ready else "publish_blocked"
            quarantine_target = _quarantine_path(temp_path, reason)
            shutil.move(str(temp_path), str(quarantine_target))
            action = "quarantined"
            temp_quarantine_path = str(quarantine_target)
        else:
            action = "no_temp_file"
        rows.append(
            {
                "contract_vt": str(row.contract_vt),
                "download_status": str(row.download_status),
                "strict_ready": strict_ready,
                "action": action,
                "temp_path": str(row.temp_path),
                "final_output_path": str(final_path),
                "old_final_quarantine_path": old_final_quarantine_path,
                "temp_quarantine_path": temp_quarantine_path,
                "publish_device_match": publish_device_match,
                "published_exists": final_path.exists(),
                "strict_rows": int(row.strict_rows),
                "sha256": str(row.sha256),
                "blocking_reason": str(row.blocking_reason),
            }
        )
    return pd.DataFrame(rows)


def build_summary(before_strict: pd.DataFrame, after_strict: pd.DataFrame, publish: pd.DataFrame, stale: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "before_strict_ready": int(before_strict["strict_ready"].astype(bool).sum()),
                "before_minute_missing": int((~before_strict["minute_file_ready"].astype(bool)).sum()),
                "before_remaining_jd_not_ready": int(
                    (before_strict["product_vt_symbol"].astype(str).eq("jd.DCE") & ~before_strict["strict_ready"].astype(bool)).sum()
                ),
                "published_count": int(publish["action"].astype(str).eq("published").sum()) if not publish.empty else 0,
                "quarantined_count": int(publish["action"].astype(str).eq("quarantined").sum()) if not publish.empty else 0,
                "stale_quarantined_count": int(len(stale)),
                "after_strict_ready": int(after_strict["strict_ready"].astype(bool).sum()),
                "after_minute_missing": int((~after_strict["minute_file_ready"].astype(bool)).sum()),
                "after_remaining_jd_not_ready": int(
                    (after_strict["product_vt_symbol"].astype(str).eq("jd.DCE") & ~after_strict["strict_ready"].astype(bool)).sum()
                ),
            }
        ]
    )


def make_decision(plan: pd.DataFrame, status: pd.DataFrame, temp_audit: pd.DataFrame, publish: pd.DataFrame, summary: pd.DataFrame) -> dict[str, Any]:
    published = int(publish["action"].astype(str).eq("published").sum()) if not publish.empty else 0
    quarantined = int(publish["action"].astype(str).eq("quarantined").sum()) if not publish.empty else 0
    strict_ready_temp = int(temp_audit["strict_ready"].astype(bool).sum()) if not temp_audit.empty else 0
    status_downloaded = int(status["status"].astype(str).eq("downloaded").sum()) if not status.empty else 0
    published_rows = int(pd.to_numeric(publish.loc[publish["action"].astype(str).eq("published"), "strict_rows"], errors="coerce").fillna(0).sum()) if not publish.empty else 0
    if not ENABLE_DOWNLOAD:
        decision = "stage117_jd_atomic_batch3_plan_only"
    elif published == len(plan) and published > 0:
        decision = "stage117_jd_atomic_batch3_success_margin_still_blocked"
    elif published > 0:
        decision = "stage117_jd_atomic_batch3_partial_success_margin_still_blocked"
    else:
        decision = "stage117_jd_atomic_batch3_no_publish_keep_blocked"
    row = summary.iloc[0].to_dict() if not summary.empty else {}
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
        "downloaded_status_count": status_downloaded,
        "temp_strict_ready_count": strict_ready_temp,
        "published_count": published,
        "quarantined_count": quarantined,
        "published_minute_rows": published_rows,
        "before_remaining_jd_not_ready": int(row.get("before_remaining_jd_not_ready", 0) or 0),
        "after_remaining_jd_not_ready": int(row.get("after_remaining_jd_not_ready", 0) or 0),
        "after_minute_missing": int(row.get("after_minute_missing", 0) or 0),
        "ready_for_true_ledger_replay": False,
        "remaining_blocker": "jd_contract_daily_margin_history",
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
            "TqSdk 官方 DataDownloader 文档确认历史数据下载会直接写 CSV；Stage117 因此不让下载器直接写入回测可发现目录，"
            "而是先落临时文件、用 Stage112 strict gate 验收后再发布。"
        ),
        "overfit_reflection_before": "否。本阶段只修下载发布口径和补缺失分钟线，不看收益曲线、不调策略参数。",
        "overfit_reflection_after": "否。atomic publish 只减少脏数据进入回测的概率，不会制造绩效。",
        "continue_value_before": "有。Stage114 证明超时半成品会污染存在性口径，必须先把下载流程改成严格验收发布。",
        "continue_value_after": "有。若发布成功可继续补剩余 jd；若未成功，应继续降低批量或延长单合约超时，而不是跑 true ledger。",
        "outputs": {
            "plan": str(PLAN_PATH),
            "status": str(STATUS_PATH),
            "temp_audit": str(TEMP_AUDIT_PATH),
            "publish_manifest": str(PUBLISH_PATH),
            "before_strict": str(BEFORE_STRICT_PATH),
            "after_strict": str(AFTER_STRICT_PATH),
            "summary": str(SUMMARY_PATH),
            "input_audit": str(INPUT_AUDIT_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(decision: dict[str, Any], plan: pd.DataFrame, status: pd.DataFrame, temp_audit: pd.DataFrame, publish: pd.DataFrame, summary: pd.DataFrame) -> None:
    lines = [
        "# Stage117 jd atomic retry backfill",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：数据补齐流程修正；先临时下载、strict gate 验收、再发布；不回测收益、不改策略、不连接 CTP、不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- TqSdk 下载工具会直接写出 CSV；Stage114 已出现超时半成品，因此本阶段把下载输出和回测可发现目录隔离。",
        "- 我的判断：这不是 alpha 优化，而是为了让后续 true ledger 只消费完整分钟文件。",
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=20),
        "",
        "## Plan",
        "",
        _md_table(plan, max_rows=20),
        "",
        "## Download Status",
        "",
        _md_table(status, max_rows=20),
        "",
        "## Temp Strict Audit",
        "",
        _md_table(temp_audit, max_rows=20),
        "",
        "## Publish Manifest",
        "",
        _md_table(publish, max_rows=20),
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], plan: pd.DataFrame, status: pd.DataFrame, temp_audit: pd.DataFrame, publish: pd.DataFrame, summary: pd.DataFrame) -> Path:
    stage_path = STAGES_DIR / f"{datetime.now():%Y%m%d_%H%M}_stage117_jd_atomic_backfill_batch3.md"
    lines = [
        "# Stage117 jd atomic retry backfill",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{decision['generated_at']}",
        "- 阶段性质：数据补齐流程修正；先临时下载、strict gate 验收、再发布；不回测收益、不改官方 live config、不连接 CTP、不调用下单",
        "- 是否重要突破：否",
        "- 是否触发A/B：否",
        "",
        "## 外部调研与判断",
        "",
        "- 参考：TqSdk DataDownloader/TqBacktest 文档、vn.py BarData 语义。",
        "- 我的判断：Stage114 的超时半成品说明“下载器输出目录”和“回测可发现目录”必须隔离；Stage117 只解决数据准入，不代表策略收益提升。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage117_jd_atomic_backfill_batch3.py`",
        "- 新增参数：`STAGE117_ENABLE_DOWNLOAD`、`STAGE117_MAX_SYMBOLS`、`STAGE117_MAX_SECONDS_PER_SYMBOL`。",
        "- 修改参数：无正式策略参数修改。",
        "- 删除参数：无。",
        "",
        "## 结果",
        "",
        f"- decision：`{decision['decision']}`",
        f"- download_enabled：`{decision['download_enabled']}`",
        f"- planned_contract_count：`{decision['planned_contract_count']}`",
        f"- downloaded_status_count：`{decision['downloaded_status_count']}`",
        f"- temp_strict_ready_count：`{decision['temp_strict_ready_count']}`",
        f"- published_count：`{decision['published_count']}`",
        f"- quarantined_count：`{decision['quarantined_count']}`",
        f"- published_minute_rows：`{decision['published_minute_rows']}`",
        f"- before_remaining_jd_not_ready：`{decision['before_remaining_jd_not_ready']}`",
        f"- after_remaining_jd_not_ready：`{decision['after_remaining_jd_not_ready']}`",
        f"- after_minute_missing：`{decision['after_minute_missing']}`",
        "- ready_for_true_ledger_replay：`False`",
        f"- remaining_blocker：`{decision['remaining_blocker']}`",
        "- 策略变更：`False`",
        "- true engine run：`False`",
        "- order API：`0`",
        "- CTP：`False`",
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=20),
        "",
        "## Plan",
        "",
        _md_table(plan, max_rows=20),
        "",
        "## Download Status",
        "",
        _md_table(status, max_rows=20),
        "",
        "## Temp Strict Audit",
        "",
        _md_table(temp_audit, max_rows=20),
        "",
        "## Publish Manifest",
        "",
        _md_table(publish, max_rows=20),
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
        f"- plan：`{PLAN_PATH}`",
        f"- status：`{STATUS_PATH}`",
        f"- temp_audit：`{TEMP_AUDIT_PATH}`",
        f"- publish_manifest：`{PUBLISH_PATH}`",
        f"- before_strict：`{BEFORE_STRICT_PATH}`",
        f"- after_strict：`{AFTER_STRICT_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- input_audit：`{INPUT_AUDIT_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    stage_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return stage_path


def run() -> dict[str, Any]:
    mod052 = _load_module(STAGE052_SCRIPT, "stage052_tqsdk_jd_minute_backfill")
    mod112 = _load_module(STAGE112_SCRIPT, "stage112_strict_minute_content_gate")
    OUT.mkdir(parents=True, exist_ok=True)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    QUARANTINE_ROOT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    before_strict = mod112.build_strict_manifest()
    plan = build_atomic_plan(mod052, mod112, before_strict)
    stale = quarantine_stale_temp(plan)
    if ENABLE_DOWNLOAD and not plan.empty:
        status, _ = mod052.run_backfill_download(plan, MAX_SECONDS_PER_SYMBOL)
    else:
        status = _empty_status()
    temp_audit = audit_temp_downloads(mod112, plan, status)
    publish = publish_strict_ready(temp_audit)
    after_strict = mod112.build_strict_manifest()
    summary = build_summary(before_strict, after_strict, publish, stale)
    input_audit = _input_audit(
        [
            STAGE052_SCRIPT,
            STAGE112_SCRIPT,
            mod052.MINUTE_GAP_MANIFEST_PATH,
            *[Path(p) for p in plan.get("output_path", pd.Series(dtype=str)).astype(str).tolist()],
            *[Path(p) for p in plan.get("final_output_path", pd.Series(dtype=str)).astype(str).tolist()],
        ]
    )
    decision = make_decision(plan, status, temp_audit, publish, summary)

    plan.to_csv(PLAN_PATH, index=False, encoding="utf-8-sig")
    status.to_csv(STATUS_PATH, index=False, encoding="utf-8-sig")
    temp_audit.to_csv(TEMP_AUDIT_PATH, index=False, encoding="utf-8-sig")
    publish.to_csv(PUBLISH_PATH, index=False, encoding="utf-8-sig")
    before_strict.to_csv(BEFORE_STRICT_PATH, index=False, encoding="utf-8-sig")
    after_strict.to_csv(AFTER_STRICT_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    _write_report(decision, plan, status, temp_audit, publish, summary)
    stage_path = _write_stage_record(decision, plan, status, temp_audit, publish, summary)
    decision["outputs"]["stage_record"] = str(stage_path)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"stage_record={stage_path}")
    return decision


if __name__ == "__main__":
    run()
