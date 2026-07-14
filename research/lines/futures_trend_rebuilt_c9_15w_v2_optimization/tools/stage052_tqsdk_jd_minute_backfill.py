from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from vnpy.trader.setting import SETTINGS


PROJECT_DIR = Path(__file__).resolve().parents[4]
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage052"
MODEL_TAG = "stage052_tqsdk_jd_minute_backfill_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage052_tqsdk_jd_minute_backfill"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage052_tqsdk_jd_minute_backfill"
STAGES_DIR = LINE_DIR / "stages"

STAGE050_OUTPUT_DIR = LINE_DIR / "outputs" / "stage050_jd_true_carry_data_manifest"
STAGE050_PREFIX = "rebuilt_c9_v2_stage050_jd_true_carry_data_manifest"
STAGE050_TAG = "stage050_jd_true_carry_data_manifest_v1"
MINUTE_GAP_MANIFEST_PATH = STAGE050_OUTPUT_DIR / f"{STAGE050_PREFIX}_minute_gap_manifest_{STAGE050_TAG}.csv"

MINUTE_ROOT = PORTFOLIO_DIR / "downloaded_futures"
BACKFILL_ROOT = MINUTE_ROOT / "tqsdk_stage052_jd_minute_gap_backfill"

BACKFILL_PLAN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_backfill_plan_{MODEL_TAG}.csv"
BACKFILL_STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_backfill_status_{MODEL_TAG}.csv"
FILE_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_file_manifest_{MODEL_TAG}.csv"
BEFORE_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_before_minute_coverage_{MODEL_TAG}.csv"
AFTER_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_after_minute_coverage_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
STAGE_RECORD_PATH = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage052_tqsdk_jd_minute_backfill.md"

CHINA_TZ = ZoneInfo("Asia/Shanghai")
ENABLE_DOWNLOAD = os.getenv("STAGE052_ENABLE_DOWNLOAD", "0").strip() == "1"
MAX_SYMBOLS = int(os.getenv("STAGE052_MAX_SYMBOLS", "3"))
MAX_SECONDS_PER_SYMBOL = int(os.getenv("STAGE052_MAX_SECONDS_PER_SYMBOL", "180"))

OUTPUT_COLUMNS = [
    "vt_symbol",
    "tq_symbol",
    "bar_datetime",
    "bar_id",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "open_oi",
    "close_oi",
]

SOURCE_LINKS = {
    "tqsdk_reference": "https://tqsdk-python.readthedocs.io/en/stable/reference/",
    "tqsdk_data_downloader": "https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.tools.download.html",
    "tqsdk_backtest": "https://doc.shinnytech.com/tqsdk/latest/advanced/backtest.html",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        if np.isnan(result) or np.isinf(result):
            return None
        return result
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return ""
        return value.isoformat()
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


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _safe_float(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return result


def to_tqsdk_symbol(vt_symbol: str) -> str:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return f"{exchange}.{symbol}"


def build_minute_file_index(root: Path = MINUTE_ROOT) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in root.glob("*/*/*minute_backtest.csv"):
        exchange = path.parent.name
        contract = path.name.replace("_completed_minute_backtest.csv", "").replace("_minute_backtest.csv", "")
        if contract:
            index.setdefault(f"{contract}.{exchange}", path)
    return index


def _download_start(value: Any) -> pd.Timestamp:
    return pd.Timestamp(pd.Timestamp(value).date())


def _download_end(value: Any) -> pd.Timestamp:
    return pd.Timestamp(pd.Timestamp(value).date() + timedelta(days=1))


def _output_path_for_contract(contract_vt: str) -> Path:
    symbol, exchange = str(contract_vt).split(".", 1)
    return BACKFILL_ROOT / exchange / f"{symbol}_minute_backtest.csv"


def build_backfill_plan(
    minute_manifest: pd.DataFrame,
    existing_minute_files: dict[str, Path] | None = None,
    max_symbols: int = 3,
) -> pd.DataFrame:
    existing = {} if existing_minute_files is None else dict(existing_minute_files)
    data = minute_manifest.copy()
    data = data[
        data["product_vt_symbol"].astype(str).eq("jd.DCE")
        & data["priority"].astype(str).str.startswith("P0")
    ].copy()
    if data.empty:
        return pd.DataFrame()
    data = data[~data["contract_vt"].astype(str).isin(existing.keys())].copy()
    if data.empty:
        return pd.DataFrame()
    data["request_start_ts"] = pd.to_datetime(data["request_start_date"], errors="coerce")
    data["request_end_ts"] = pd.to_datetime(data["request_end_date"], errors="coerce")
    data["observed_price_rows"] = pd.to_numeric(data["observed_price_rows"], errors="coerce").fillna(0).astype(int)
    data = data.dropna(subset=["request_start_ts", "request_end_ts"]).copy()
    data = data.sort_values(["observed_price_rows", "request_start_ts", "contract_vt"], ascending=[True, False, True])
    if max_symbols > 0:
        data = data.head(max_symbols).copy()
    data["tq_symbol"] = data["contract_vt"].map(to_tqsdk_symbol)
    data["download_start_datetime"] = data["request_start_ts"].map(_download_start).astype(str)
    data["download_end_datetime"] = data["request_end_ts"].map(_download_end).astype(str)
    data["output_path"] = data["contract_vt"].map(lambda value: str(_output_path_for_contract(str(value))))
    columns = [
        "contract_vt",
        "product_vt_symbol",
        "tq_symbol",
        "request_start_date",
        "request_end_date",
        "download_start_datetime",
        "download_end_datetime",
        "observed_price_rows",
        "priority",
        "output_path",
    ]
    return data[columns].reset_index(drop=True)


def normalize_downloaded_bars(raw_bars: pd.DataFrame) -> pd.DataFrame:
    if raw_bars.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    data = raw_bars.copy()
    if "vt_symbol" not in data.columns and "contract_vt" in data.columns:
        data["vt_symbol"] = data["contract_vt"]
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce").dt.tz_localize(None)
    data = data.dropna(subset=["bar_datetime"]).copy()
    data = data.sort_values(["vt_symbol", "bar_datetime"]).drop_duplicates(["vt_symbol", "bar_datetime"])
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data["bar_id"] = pd.to_numeric(data["bar_id"], errors="coerce").fillna(-1).astype(int)
    data["bar_datetime"] = data["bar_datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return data[OUTPUT_COLUMNS].reset_index(drop=True)


def _normalize_tqsdk_datetime(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, unit="ns", errors="coerce", utc=True)
    if pd.isna(ts):
        return pd.NaT
    return ts.tz_convert(CHINA_TZ).tz_localize(None)


def upsert_bar_snapshot(
    snapshots: dict[int, dict[str, Any]],
    row_dict: dict[str, Any],
    *,
    contract_vt: str,
    tq_symbol: str,
    start_dt: pd.Timestamp,
    end_dt: pd.Timestamp,
) -> bool:
    bar_id = int(row_dict.get("id", -1))
    bar_dt = _normalize_tqsdk_datetime(row_dict.get("datetime"))
    if bar_id < 0 or pd.isna(bar_dt) or bar_dt < pd.Timestamp(start_dt) or bar_dt >= pd.Timestamp(end_dt):
        return False
    snapshots[bar_id] = {
        "contract_vt": contract_vt,
        "tq_symbol": tq_symbol,
        "bar_datetime": bar_dt,
        "bar_id": bar_id,
        "open": _safe_float(row_dict.get("open")),
        "high": _safe_float(row_dict.get("high")),
        "low": _safe_float(row_dict.get("low")),
        "close": _safe_float(row_dict.get("close")),
        "volume": _safe_float(row_dict.get("volume")),
        "open_oi": _safe_float(row_dict.get("open_oi")),
        "close_oi": _safe_float(row_dict.get("close_oi")),
    }
    return True


def download_contract_minutes(row: Any, username: str, password: str, max_seconds: int) -> tuple[dict[str, Any], pd.DataFrame]:
    from tqsdk import BacktestFinished, TqApi, TqAuth, TqBacktest, TqSim

    contract_vt = str(row.contract_vt)
    tq_symbol = str(row.tq_symbol)
    start_dt = pd.Timestamp(row.download_start_datetime).to_pydatetime()
    end_dt = pd.Timestamp(row.download_end_datetime).to_pydatetime()
    output_path = Path(str(row.output_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)

    status = {
        "contract_vt": contract_vt,
        "tq_symbol": tq_symbol,
        "download_start_datetime": pd.Timestamp(start_dt),
        "download_end_datetime": pd.Timestamp(end_dt),
        "status": "unknown",
        "rows": 0,
        "first_bar_datetime": "",
        "last_bar_datetime": "",
        "elapsed_seconds": 0.0,
        "output_path": str(output_path),
        "sha256": "",
        "message": "",
    }
    started = time.time()
    snapshots: dict[int, dict[str, Any]] = {}
    api = None
    try:
        api = TqApi(TqSim(), backtest=TqBacktest(start_dt=start_dt, end_dt=end_dt), auth=TqAuth(username, password))
        klines = api.get_kline_serial(tq_symbol, duration_seconds=60, data_length=500)

        def capture_latest_snapshots() -> None:
            for _, kline_row in klines.iterrows():
                upsert_bar_snapshot(
                    snapshots,
                    kline_row.to_dict(),
                    contract_vt=contract_vt,
                    tq_symbol=tq_symbol,
                    start_dt=pd.Timestamp(start_dt),
                    end_dt=pd.Timestamp(end_dt),
                )

        while True:
            if time.time() - started > max_seconds:
                status["status"] = "timeout"
                status["message"] = f"timeout_after_{max_seconds}s"
                break
            try:
                changed = api.wait_update(deadline=time.time() + 1.0)
            except BacktestFinished:
                capture_latest_snapshots()
                status["status"] = "downloaded"
                break
            if not changed:
                continue
            capture_latest_snapshots()
    except Exception as exc:
        status["status"] = "failed"
        status["message"] = repr(exc)
    finally:
        if api is not None:
            api.close()

    bars = normalize_downloaded_bars(pd.DataFrame(snapshots.values()))
    if not bars.empty:
        bars.to_csv(output_path, index=False, encoding="utf-8-sig")
        status["rows"] = int(len(bars))
        status["first_bar_datetime"] = str(bars["bar_datetime"].iloc[0])
        status["last_bar_datetime"] = str(bars["bar_datetime"].iloc[-1])
        status["sha256"] = hashlib.sha256(output_path.read_bytes()).hexdigest()
    if status["status"] == "unknown":
        status["status"] = "downloaded" if not bars.empty else "empty"
    status["elapsed_seconds"] = round(time.time() - started, 2)
    return status, bars


def run_backfill_download(plan: pd.DataFrame, max_seconds_per_symbol: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    username = str(SETTINGS.get("datafeed.username", "")).strip()
    password = str(SETTINGS.get("datafeed.password", "")).strip()
    if not username or not password:
        raise RuntimeError("TqSdk credentials are missing in vn.py SETTINGS.")
    status_rows: list[dict[str, Any]] = []
    all_bars: list[pd.DataFrame] = []
    for row in plan.itertuples(index=False):
        status, bars = download_contract_minutes(row, username, password, max_seconds_per_symbol)
        status_rows.append(status)
        if not bars.empty:
            all_bars.append(bars)
    bars_frame = pd.concat(all_bars, ignore_index=True) if all_bars else pd.DataFrame(columns=OUTPUT_COLUMNS)
    return pd.DataFrame(status_rows), bars_frame


def audit_manifest_coverage(minute_manifest: pd.DataFrame, minute_files: dict[str, Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in minute_manifest.itertuples(index=False):
        contract = str(row.contract_vt)
        path = minute_files.get(contract)
        rows.append(
            {
                "contract_vt": contract,
                "product_vt_symbol": str(row.product_vt_symbol),
                "minute_file_ready": path is not None,
                "minute_file": str(path) if path is not None else "",
            }
        )
    return pd.DataFrame(rows)


def build_file_manifest(status: pd.DataFrame) -> pd.DataFrame:
    if status.empty:
        return pd.DataFrame(columns=["contract_vt", "output_path", "rows", "sha256", "stage049_discoverable"])
    data = status.copy()
    data["stage049_discoverable"] = data["output_path"].astype(str).str.contains("/downloaded_futures/") & data[
        "output_path"
    ].astype(str).str.endswith("_minute_backtest.csv")
    return data[["contract_vt", "output_path", "rows", "sha256", "stage049_discoverable"]].reset_index(drop=True)


def make_stage052_decision(plan: pd.DataFrame, status: pd.DataFrame) -> dict[str, Any]:
    if status.empty:
        success_count = 0
        downloaded_rows = 0
    else:
        rows = pd.to_numeric(status["rows"], errors="coerce").fillna(0).astype(int)
        success_count = int((status["status"].astype(str).eq("downloaded") & rows.gt(0)).sum())
        downloaded_rows = int(rows.sum())
    if success_count == 0:
        decision = "stage052_tqsdk_jd_minute_backfill_no_download_keep_stage051_ready"
    else:
        decision = "stage052_tqsdk_jd_minute_backfill_partial_success_margin_still_blocked"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "download_enabled": bool(ENABLE_DOWNLOAD),
        "planned_contract_count": int(len(plan)),
        "download_status_count": int(len(status)),
        "download_success_contract_count": success_count,
        "downloaded_minute_rows": downloaded_rows,
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
        "external_research_judgment": (
            "TqSdk DataDownloader 是更合适的长期批量历史数据工具但属于专业版能力；"
            "本阶段基于 Stage051 已验证的 TqBacktest/get_kline_serial 路线做受控补数，不把数据下载结果解释成策略 alpha。"
        ),
        "overfit_reflection_before": "否。本阶段补的是 Stage049 缺失的 jd 分钟源，不根据收益表现筛选参数。",
        "overfit_reflection_after": "否。下载成功只减少数据阻塞；保证金未补前仍禁止 true ledger replay。",
        "continue_value_before": "有。Stage051 已证明 TqSdk 可读 jd 1m K，下一步应把小窗口成功转成可被 Stage049 发现的文件。",
        "continue_value_after": (
            "有。若批次成功，继续扩大到剩余 jd 合约；并行寻找 jd 逐日保证金，二者缺一不可。"
        ),
        "source_links": SOURCE_LINKS,
        "outputs": {
            "backfill_plan": str(BACKFILL_PLAN_PATH),
            "backfill_status": str(BACKFILL_STATUS_PATH),
            "file_manifest": str(FILE_MANIFEST_PATH),
            "before_coverage": str(BEFORE_COVERAGE_PATH),
            "after_coverage": str(AFTER_COVERAGE_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
            "stage_record": str(STAGE_RECORD_PATH),
        },
    }


def _write_report(
    decision: dict[str, Any],
    plan: pd.DataFrame,
    status: pd.DataFrame,
    file_manifest: pd.DataFrame,
    before_coverage: pd.DataFrame,
    after_coverage: pd.DataFrame,
) -> None:
    before_missing = int((~before_coverage["minute_file_ready"].astype(bool)).sum()) if not before_coverage.empty else 0
    after_missing = int((~after_coverage["minute_file_ready"].astype(bool)).sum()) if not after_coverage.empty else 0
    lines = [
        "# Stage052 TqSdk jd 分钟缺口受控补数",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：数据补齐；不回测收益，不改策略，不连接 CTP，不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- TqSdk `DataDownloader` 是专业版历史下载工具，适合长期批量下载；当前本机走 Stage051 已验证的 `TqBacktest + get_kline_serial` 路线做受控补数。",
        "- 我的判断：这是数据源修复，不是策略优化；不能把补数成功当作 alpha 成功。",
        "",
        "## Coverage Delta",
        "",
        f"- before_missing：`{before_missing}`",
        f"- after_missing：`{after_missing}`",
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
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], plan: pd.DataFrame, status: pd.DataFrame, before_coverage: pd.DataFrame, after_coverage: pd.DataFrame) -> None:
    before_missing = int((~before_coverage["minute_file_ready"].astype(bool)).sum()) if not before_coverage.empty else 0
    after_missing = int((~after_coverage["minute_file_ready"].astype(bool)).sum()) if not after_coverage.empty else 0
    text = f"""# Stage052 TqSdk jd 分钟缺口受控补数

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision['generated_at']}
- 阶段性质：数据补齐；不回测收益，不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：TqSdk 官方参考、DataDownloader 文档、TqBacktest 文档。
- 我的判断：DataDownloader 更适合长期批量历史下载但属于专业版；本阶段用 Stage051 已验证的 TqBacktest 路线做受控补数。补数只减少数据阻塞，不代表策略有效。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage052_tqsdk_jd_minute_backfill.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage052_tqsdk_jd_minute_backfill.py`
- 新增参数：`STAGE052_ENABLE_DOWNLOAD`、`STAGE052_MAX_SYMBOLS`、`STAGE052_MAX_SECONDS_PER_SYMBOL`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`{decision['decision']}`
- download_enabled：`{decision['download_enabled']}`
- planned_contract_count：`{decision['planned_contract_count']}`
- download_success_contract_count：`{decision['download_success_contract_count']}`
- downloaded_minute_rows：`{decision['downloaded_minute_rows']}`
- before_missing：`{before_missing}`
- after_missing：`{after_missing}`
- ready_for_true_ledger_replay：`False`
- remaining_blocker：`{decision['remaining_blocker']}`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## Backfill Plan

{_md_table(plan, max_rows=80)}

## Backfill Status

{_md_table(status, max_rows=80)}

## 过拟合反思

- 运行前判断：{decision['overfit_reflection_before']}
- 运行后判断：{decision['overfit_reflection_after']}

## 继续价值反思

- 运行前判断：{decision['continue_value_before']}
- 运行后判断：{decision['continue_value_after']}

## 输出文件

- backfill_plan：`{BACKFILL_PLAN_PATH}`
- backfill_status：`{BACKFILL_STATUS_PATH}`
- file_manifest：`{FILE_MANIFEST_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`
"""
    STAGE_RECORD_PATH.write_text(text, encoding="utf-8")


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    BACKFILL_ROOT.mkdir(parents=True, exist_ok=True)

    manifest = _read_csv(MINUTE_GAP_MANIFEST_PATH)
    before_index = build_minute_file_index()
    before_coverage = audit_manifest_coverage(manifest, before_index)
    plan = build_backfill_plan(manifest, before_index, MAX_SYMBOLS)
    if ENABLE_DOWNLOAD and not plan.empty:
        status, _ = run_backfill_download(plan, MAX_SECONDS_PER_SYMBOL)
    else:
        status = pd.DataFrame(columns=[
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
        ])
    after_index = build_minute_file_index()
    after_coverage = audit_manifest_coverage(manifest, after_index)
    file_manifest = build_file_manifest(status)
    decision = make_stage052_decision(plan, status)

    plan.to_csv(BACKFILL_PLAN_PATH, index=False, encoding="utf-8-sig")
    status.to_csv(BACKFILL_STATUS_PATH, index=False, encoding="utf-8-sig")
    file_manifest.to_csv(FILE_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    before_coverage.to_csv(BEFORE_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    after_coverage.to_csv(AFTER_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, plan, status, file_manifest, before_coverage, after_coverage)
    _write_stage_record(decision, plan, status, before_coverage, after_coverage)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
