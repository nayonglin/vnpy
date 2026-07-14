from __future__ import annotations

from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage136"
MODEL_TAG = "stage136_ap010_canary_fill_window_backfill_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage136_ap010_canary_fill_window_backfill"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage136_ap010_canary_fill_window_backfill"
TMP_ROOT = OUT / "tmp_downloads"
QUARANTINE_ROOT = OUT / "quarantine"
FINAL_ROOT = (
    ROOT
    / "examples"
    / "portfolio_backtesting"
    / "downloaded_futures"
    / "tqsdk_stage052_jd_minute_gap_backfill"
)

STAGE052_SCRIPT = LINE_DIR / "tools" / "stage052_tqsdk_jd_minute_backfill.py"
STAGE134_SCRIPT = LINE_DIR / "tools" / "stage134_tail_minute_session_semantics_repair.py"

PLAN_PATH = OUT / f"{OUTPUT_PREFIX}_plan_{MODEL_TAG}.csv"
STATUS_PATH = OUT / f"{OUTPUT_PREFIX}_status_{MODEL_TAG}.csv"
TEMP_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_temp_audit_{MODEL_TAG}.csv"
PUBLISH_PATH = OUT / f"{OUTPUT_PREFIX}_publish_{MODEL_TAG}.csv"
POST_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_post_audit_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

CONTRACT = "AP010.CZCE"
PRODUCT = "AP.CZCE"
DOWNLOAD_START = "2020-09-01 20:55:00"
DOWNLOAD_END = "2020-09-02 15:15:00"
EXPECTED_DATE = pd.Timestamp("2020-09-02")
GLOBAL_DATES = pd.DatetimeIndex(["2020-09-01", "2020-09-02"])
ENABLE_DOWNLOAD = os.getenv("STAGE136_ENABLE_DOWNLOAD", "0").strip() == "1"
MAX_SECONDS = int(os.getenv("STAGE136_MAX_SECONDS", "900"))


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def build_plan(temp_root: Path = TMP_ROOT, final_root: Path = FINAL_ROOT) -> pd.DataFrame:
    symbol, exchange = CONTRACT.split(".", 1)
    return pd.DataFrame(
        [
            {
                "contract_vt": CONTRACT,
                "product_vt_symbol": PRODUCT,
                "tq_symbol": f"{exchange}.{symbol}",
                "download_start_datetime": DOWNLOAD_START,
                "download_end_datetime": DOWNLOAD_END,
                "request_start_date": EXPECTED_DATE.date().isoformat(),
                "request_end_date": EXPECTED_DATE.date().isoformat(),
                "priority": "P0_stage135_canary_real_fill",
                "output_path": str(Path(temp_root) / exchange / f"{symbol}_minute_backtest.csv"),
                "final_output_path": str(Path(final_root) / exchange / f"{symbol}_minute_backtest.csv"),
            }
        ]
    )


def make_decision(
    status: pd.DataFrame,
    temp_audit: pd.DataFrame,
    publish: pd.DataFrame,
    post_audit: pd.DataFrame,
) -> dict[str, Any]:
    download_ready = bool(len(status) == 1 and status["status"].astype(str).eq("downloaded").all())
    temp_ready = bool(len(temp_audit) == 1 and temp_audit["strict_ready"].astype(bool).all())
    publish_ready = bool(
        len(publish) == 1
        and publish["action"].astype(str).isin(["published", "replaced"]).all()
        and publish["published_exists"].astype(bool).all()
    )
    post_ready = bool(len(post_audit) == 1 and post_audit["strict_ready"].astype(bool).all())
    sha_values = []
    for frame, column in (
        (status, "sha256"),
        (temp_audit, "sha256"),
        (publish, "published_sha256"),
        (post_audit, "sha256"),
    ):
        value = str(frame.iloc[0].get(column, "")) if len(frame) == 1 else ""
        sha_values.append(value)
    sha_chain_ready = bool(all(sha_values) and len(set(sha_values)) == 1)
    ready = download_ready and temp_ready and publish_ready and post_ready and sha_chain_ready
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "contract_vt": CONTRACT,
        "download_start_datetime": DOWNLOAD_START,
        "download_end_datetime": DOWNLOAD_END,
        "download_ready": download_ready,
        "temp_strict_ready": temp_ready,
        "publish_ready": publish_ready,
        "post_audit_ready": post_ready,
        "sha_chain_ready": sha_chain_ready,
        "sha256": sha_values[0] if sha_chain_ready else "",
        "ready_for_stage135_canary": ready,
        "decision": (
            "stage136_ap010_fill_window_ready_resume_stage135_canary"
            if ready
            else "stage136_ap010_fill_window_blocked_keep_stage135_paused"
        ),
        "strategy_rule_changed": False,
        "official_live_changed": False,
        "order_api_called": False,
        "ctp_connected": False,
    }


def audit_closed_state_quality(data: pd.DataFrame) -> dict[str, Any]:
    required = {"open", "high", "low", "close", "volume"}
    missing = sorted(required - set(data.columns))
    if missing or data.empty:
        return {
            "closed_state_ready": False,
            "flat_ohlc_row_count": 0,
            "nonflat_ohlc_row_count": 0,
            "positive_volume_row_count": 0,
            "closed_state_blocking_reason": "missing_or_empty:" + ",".join(missing),
        }
    values = data.copy()
    for column in required:
        values[column] = pd.to_numeric(values[column], errors="coerce")
    flat = (
        values["open"].eq(values["high"])
        & values["open"].eq(values["low"])
        & values["open"].eq(values["close"])
    )
    positive_volume = values["volume"].gt(0.0)
    ready = bool((~flat).any() and positive_volume.any())
    return {
        "closed_state_ready": ready,
        "flat_ohlc_row_count": int(flat.sum()),
        "nonflat_ohlc_row_count": int((~flat).sum()),
        "positive_volume_row_count": int(positive_volume.sum()),
        "closed_state_blocking_reason": "" if ready else "all_open_snapshots_or_zero_volume",
    }


def _audit(s134: Any, row: Any, path: Path) -> dict[str, Any]:
    result = s134.audit_session_file(
        row,
        path,
        pd.DatetimeIndex([EXPECTED_DATE]),
        GLOBAL_DATES,
    )
    if path.exists():
        try:
            quality = audit_closed_state_quality(pd.read_csv(path, encoding="utf-8-sig"))
        except Exception as exc:
            quality = {
                "closed_state_ready": False,
                "flat_ohlc_row_count": 0,
                "nonflat_ohlc_row_count": 0,
                "positive_volume_row_count": 0,
                "closed_state_blocking_reason": f"closed_state_read_error:{exc!r}",
            }
    else:
        quality = audit_closed_state_quality(pd.DataFrame())
    result.update(quality)
    if not bool(quality["closed_state_ready"]):
        result["strict_ready"] = False
        reason = str(result.get("blocking_reason", ""))
        suffix = "closed_state_quality"
        result["blocking_reason"] = f"{reason},{suffix}" if reason else f"strict_failed:{suffix}"
    return result


def _write_report(decision: dict[str, Any], status: pd.DataFrame, audit: pd.DataFrame, publish: pd.DataFrame, post: pd.DataFrame) -> None:
    lines = [
        "# Stage136 AP010 canary 成交窗口原子补数",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- 决策：`{decision['decision']}`",
        f"- Stage135 恢复条件：`{decision['ready_for_stage135_canary']}`",
        "- 固定窗口：`2020-09-01 20:55 <= t < 2020-09-02 15:15`；不允许 fallback。",
        "- 本阶段不修改策略、正式实盘、CTP、邮件或订单入口。",
        "",
        "## 下载",
        "",
        status.to_markdown(index=False) if not status.empty else "_无记录_",
        "",
        "## Temp audit",
        "",
        audit.to_markdown(index=False) if not audit.empty else "_无记录_",
        "",
        "## Publish",
        "",
        publish.to_markdown(index=False) if not publish.empty else "_无记录_",
        "",
        "## Post audit",
        "",
        post.to_markdown(index=False) if not post.empty else "_无记录_",
        "",
        "## 反思",
        "",
        "- 运行后过拟合判断：否。补数窗口由第一笔真实成交缺口机械确定，没有读取收益。",
        "- 继续价值：只有 post audit 通过才恢复 Stage135；否则保持暂停。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    plan = build_plan()
    plan.to_csv(PLAN_PATH, index=False, encoding="utf-8-sig")
    s052 = _load_module(STAGE052_SCRIPT, "stage052_for_stage136")
    s134 = _load_module(STAGE134_SCRIPT, "stage134_for_stage136")
    if ENABLE_DOWNLOAD:
        status, _bars = s052.run_backfill_download(plan, MAX_SECONDS)
    else:
        status = plan[["contract_vt", "tq_symbol", "output_path"]].copy()
        status["status"] = "planned_download_disabled"
        status["rows"] = 0
        status["message"] = "set_STAGE136_ENABLE_DOWNLOAD_1"
    status.to_csv(STATUS_PATH, index=False, encoding="utf-8-sig")

    audit_rows: list[dict[str, Any]] = []
    for row in plan.itertuples(index=False):
        result = _audit(s134, row, Path(row.output_path))
        status_value = str(status.iloc[0].get("status", "")) if not status.empty else ""
        if status_value != "downloaded":
            result["strict_ready"] = False
            reason = str(result.get("blocking_reason", ""))
            result["blocking_reason"] = (reason + "," if reason else "strict_failed:") + "download_status"
        audit_rows.append(result)
    temp_audit = pd.DataFrame(audit_rows)
    temp_audit.to_csv(TEMP_AUDIT_PATH, index=False, encoding="utf-8-sig")
    publish = s134.publish_verified(temp_audit, quarantine_root=QUARANTINE_ROOT)
    publish.to_csv(PUBLISH_PATH, index=False, encoding="utf-8-sig")

    post_rows: list[dict[str, Any]] = []
    for row in plan.itertuples(index=False):
        post_rows.append(_audit(s134, row, Path(row.final_output_path)))
    post = pd.DataFrame(post_rows)
    post.to_csv(POST_AUDIT_PATH, index=False, encoding="utf-8-sig")
    decision = make_decision(status, temp_audit, publish, post)
    decision["outputs"] = {
        "plan": str(PLAN_PATH),
        "status": str(STATUS_PATH),
        "temp_audit": str(TEMP_AUDIT_PATH),
        "publish": str(PUBLISH_PATH),
        "post_audit": str(POST_AUDIT_PATH),
        "decision": str(DECISION_PATH),
        "report": str(REPORT_PATH),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, status, temp_audit, publish, post)
    return decision


def main() -> None:
    print(json.dumps(_json_safe(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
