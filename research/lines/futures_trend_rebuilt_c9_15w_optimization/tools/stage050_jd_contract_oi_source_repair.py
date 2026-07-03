from __future__ import annotations

from datetime import date, datetime
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
import pandas as pd
from tqsdk import TqAuth
from tqsdk.calendar import TqContCalendar

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import HistoryRequest
from vnpy.trader.setting import SETTINGS


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage050"
MODEL_TAG = "stage050_jd_contract_oi_source_repair_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage050_jd_contract_oi_source_repair"

PRODUCT_VT_SYMBOL = "jd.DCE"
REPAIR_START = pd.Timestamp("2026-03-27")
MAPPING_FETCH_START = pd.Timestamp("2026-05-01")
TARGET_END = pd.Timestamp("2026-06-30")
MONTHS_BEFORE = 2
MONTHS_AFTER = 12

TOOLS_DIR = Path(__file__).resolve().parent
LINE_DIR = TOOLS_DIR.parent
REPO_ROOT = LINE_DIR.parents[2]
OUTPUT_DIR = LINE_DIR / "outputs" / "stage050_jd_contract_oi_source_repair"
STAGES_DIR = LINE_DIR / "stages"

BACKTEST_OUTPUTS = REPO_ROOT / "examples" / "portfolio_backtesting" / "backtest_outputs"
BASE_MAPPING_PATH = BACKTEST_OUTPUTS / "tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv"
LOCAL_TQSDK_PATH = REPO_ROOT / "vnpy_tqsdk" / "tqsdk_datafeed.py"

FETCHED_MAPPING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fetched_mapping_{MODEL_TAG}.csv"
COMBINED_MAPPING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combined_mapping_{MODEL_TAG}.csv"
CONTRACT_BARS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contract_bars_{MODEL_TAG}.csv"
CONTRACT_STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contract_status_{MODEL_TAG}.csv"
SOURCE_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_coverage_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无数据_"
    shown = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in shown.columns:
        if pd.api.types.is_float_dtype(shown[column]):
            shown[column] = shown[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return shown.to_markdown(index=False)


def _split_product_vt(product_vt_symbol: str) -> tuple[str, str]:
    product, exchange = product_vt_symbol.split(".", 1)
    return product, exchange


def _split_contract_vt(vt_symbol: str) -> tuple[str, Exchange]:
    symbol, exchange = vt_symbol.split(".", 1)
    return symbol, Exchange(exchange)


def _normalise_product(product: str, exchange: str) -> str:
    return product.upper() if exchange in {"CZCE", "CFFEX"} else product.lower()


def _tq_to_vt_symbol(tq_symbol: str) -> str:
    if not tq_symbol or "." not in tq_symbol:
        return ""
    exchange, symbol = tq_symbol.split(".", 1)
    return f"{symbol}.{exchange}"


def _credential_status() -> dict[str, Any]:
    username = str(SETTINGS["datafeed.username"] or "")
    password = str(SETTINGS["datafeed.password"] or "")
    return {
        "datafeed_name": str(SETTINGS["datafeed.name"] or ""),
        "username_configured": bool(username),
        "username_length": len(username) if username else 0,
        "password_configured": bool(password),
        "password_length": len(password) if password else 0,
    }


def _month_iter(start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    current = pd.Timestamp(year=start.year, month=start.month, day=1)
    last = pd.Timestamp(year=end.year, month=end.month, day=1)
    months: list[pd.Timestamp] = []
    while current <= last:
        months.append(current)
        current = current + pd.DateOffset(months=1)
    return months


def candidate_contract_vt_symbols(
    product_vt_symbol: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    *,
    months_before: int = MONTHS_BEFORE,
    months_after: int = MONTHS_AFTER,
) -> list[str]:
    product, exchange = _split_product_vt(product_vt_symbol)
    start_month = pd.Timestamp(start).normalize().replace(day=1) - pd.DateOffset(months=months_before)
    end_month = pd.Timestamp(end).normalize().replace(day=1) + pd.DateOffset(months=months_after)
    symbols: list[str] = []
    for month in _month_iter(start_month, end_month):
        suffix = f"{month.year % 100:02d}{month.month:02d}"
        symbols.append(f"{_normalise_product(product, exchange)}{suffix}.{exchange}")
    return symbols


def merge_mapping_rows(existing: pd.DataFrame, fetched: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "date",
        "product",
        "exchange",
        "continuous_symbol_tq",
        "continuous_symbol_vt",
        "main_contract_tq",
        "main_contract_vt",
    ]
    frames: list[pd.DataFrame] = []
    for frame in (existing, fetched):
        if frame.empty:
            continue
        current = frame.copy()
        for column in columns:
            if column not in current.columns:
                current[column] = ""
        current = current[columns]
        current["date"] = pd.to_datetime(current["date"], errors="coerce").dt.normalize()
        current = current.dropna(subset=["date"])
        current["continuous_symbol_vt"] = current["continuous_symbol_vt"].fillna("").astype(str)
        current["main_contract_tq"] = current["main_contract_tq"].fillna("").astype(str)
        current["main_contract_vt"] = current["main_contract_vt"].fillna("").astype(str)
        frames.append(current)
    if not frames:
        return pd.DataFrame(columns=columns)
    combined = pd.concat(frames, ignore_index=True)
    combined.sort_values(["date", "continuous_symbol_vt"], inplace=True)
    combined.drop_duplicates(["date", "continuous_symbol_vt"], keep="last", inplace=True)
    return combined.sort_values("date").reset_index(drop=True)


def build_jd_source_coverage(mapping: pd.DataFrame, bars: pd.DataFrame, *, target_end: pd.Timestamp) -> dict[str, Any]:
    target_end = pd.Timestamp(target_end).normalize()
    mapping_frame = mapping.copy()
    bar_frame = bars.copy()
    if not mapping_frame.empty:
        mapping_frame["date"] = pd.to_datetime(mapping_frame["date"], errors="coerce").dt.normalize()
        mapping_frame = mapping_frame[mapping_frame["continuous_symbol_vt"].fillna("").astype(str).eq(PRODUCT_VT_SYMBOL)]
        mapping_frame = mapping_frame[mapping_frame["main_contract_vt"].fillna("").astype(str).ne("")]
    if not bar_frame.empty:
        if "datetime" in bar_frame.columns:
            bar_frame["date"] = pd.to_datetime(bar_frame["datetime"], errors="coerce").dt.normalize()
        else:
            bar_frame["date"] = pd.to_datetime(bar_frame["date"], errors="coerce").dt.normalize()
        bar_frame["open_interest"] = pd.to_numeric(bar_frame["open_interest"], errors="coerce")
        bar_frame = bar_frame[bar_frame["open_interest"].fillna(0.0).gt(0)].copy()

    mapping_start = mapping_frame["date"].min() if not mapping_frame.empty else pd.NaT
    mapping_end = mapping_frame["date"].max() if not mapping_frame.empty else pd.NaT
    bar_start = bar_frame["date"].min() if not bar_frame.empty else pd.NaT
    bar_end = bar_frame["date"].max() if not bar_frame.empty else pd.NaT
    return {
        "product_vt_symbol": PRODUCT_VT_SYMBOL,
        "mapping_rows": int(len(mapping_frame)),
        "mapping_start": mapping_start.date().isoformat() if pd.notna(mapping_start) else "",
        "mapping_end": mapping_end.date().isoformat() if pd.notna(mapping_end) else "",
        "mapping_contract_count": int(mapping_frame["main_contract_vt"].nunique()) if not mapping_frame.empty else 0,
        "bar_rows": int(len(bar_frame)),
        "bar_start": bar_start.date().isoformat() if pd.notna(bar_start) else "",
        "bar_end": bar_end.date().isoformat() if pd.notna(bar_end) else "",
        "bar_contract_count": int(bar_frame["contract_vt_symbol"].nunique()) if "contract_vt_symbol" in bar_frame.columns and not bar_frame.empty else 0,
        "mapping_covers_target_end": bool(pd.notna(mapping_end) and mapping_end >= target_end),
        "bars_cover_target_tminus1": bool(pd.notna(bar_end) and bar_end >= target_end - pd.Timedelta(days=1)),
    }


def _load_tqsdk_datafeed_class() -> Any:
    spec = importlib.util.spec_from_file_location("local_vnpy_tqsdk_datafeed", LOCAL_TQSDK_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load TqSdk datafeed from {LOCAL_TQSDK_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.TqsdkDatafeed


def fetch_mapping_rows(product_vt_symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    status = _credential_status()
    if not status["username_configured"] or not status["password_configured"]:
        raise RuntimeError("missing TqSdk credentials in vn.py settings")
    product, exchange = _split_product_vt(product_vt_symbol)
    product_tq = _normalise_product(product, exchange)
    continuous_symbol_tq = f"KQ.m@{exchange}.{product_tq}"
    auth = TqAuth(str(SETTINGS["datafeed.username"]), str(SETTINGS["datafeed.password"]))
    auth.login()
    calendar = TqContCalendar(
        start_dt=pd.Timestamp(start).date(),
        end_dt=pd.Timestamp(end).date(),
        symbols=[continuous_symbol_tq],
        headers=auth._base_headers,
    )
    frame = calendar.df.copy()
    rows: list[dict[str, str]] = []
    for _, row in frame.iterrows():
        trade_date = row["date"].date() if hasattr(row["date"], "date") else row["date"]
        main_contract_tq = str(row[continuous_symbol_tq] or "")
        rows.append(
            {
                "date": trade_date.isoformat(),
                "product": product,
                "exchange": exchange,
                "continuous_symbol_tq": continuous_symbol_tq,
                "continuous_symbol_vt": product_vt_symbol,
                "main_contract_tq": main_contract_tq,
                "main_contract_vt": _tq_to_vt_symbol(main_contract_tq) if main_contract_tq else "",
            }
        )
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def fetch_contract_bars(contract_symbols: list[str], start: pd.Timestamp, end: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    TqsdkDatafeed = _load_tqsdk_datafeed_class()
    datafeed = TqsdkDatafeed()
    rows: list[dict[str, Any]] = []
    status_rows: list[dict[str, Any]] = []
    start_dt = pd.Timestamp(start).to_pydatetime()
    end_dt = pd.Timestamp(end).to_pydatetime()
    for vt_symbol in contract_symbols:
        status = "unknown"
        message = ""
        count = 0
        min_date = ""
        max_date = ""
        try:
            symbol, exchange = _split_contract_vt(vt_symbol)
            req = HistoryRequest(
                symbol=symbol,
                exchange=exchange,
                interval=Interval.DAILY,
                start=start_dt,
                end=end_dt,
            )
            bars = datafeed.query_bar_history(req)
            count = len(bars) if bars else 0
            if not bars:
                status = "empty"
                message = "no bars returned"
            else:
                for bar in bars:
                    bar_date = pd.Timestamp(bar.datetime).tz_localize(None).normalize()
                    rows.append(
                        {
                            "symbol": symbol,
                            "exchange": exchange.value,
                            "contract_vt_symbol": vt_symbol,
                            "datetime": bar_date.date().isoformat(),
                            "open_price": float(bar.open_price),
                            "high_price": float(bar.high_price),
                            "low_price": float(bar.low_price),
                            "close_price": float(bar.close_price),
                            "volume": float(bar.volume or 0.0),
                            "open_interest": float(bar.open_interest or 0.0),
                            "source": "tqsdk_line_local_stage050",
                        }
                    )
                dates = [row["datetime"] for row in rows if row["contract_vt_symbol"] == vt_symbol]
                min_date = min(dates) if dates else ""
                max_date = max(dates) if dates else ""
                status = "fetched"
        except Exception as exc:
            status = "failed"
            message = repr(exc)
        status_rows.append(
            {
                "contract_vt_symbol": vt_symbol,
                "status": status,
                "bar_count": count,
                "min_date": min_date,
                "max_date": max_date,
                "message": message,
            }
        )
        print(f"[stage050] {vt_symbol} {status} bars={count} {min_date}->{max_date}", flush=True)
    bars_df = pd.DataFrame(rows)
    if not bars_df.empty:
        bars_df.drop_duplicates(["datetime", "contract_vt_symbol"], keep="last", inplace=True)
        bars_df.sort_values(["contract_vt_symbol", "datetime"], inplace=True)
    status_df = pd.DataFrame(status_rows).sort_values(["status", "contract_vt_symbol"]).reset_index(drop=True)
    return bars_df.reset_index(drop=True), status_df


def _existing_jd_mapping() -> pd.DataFrame:
    mapping = pd.read_csv(BASE_MAPPING_PATH, encoding="utf-8-sig")
    mapping["date"] = pd.to_datetime(mapping["date"], errors="coerce").dt.normalize()
    return mapping[mapping["continuous_symbol_vt"].astype(str).eq(PRODUCT_VT_SYMBOL)].copy()


def _decision(coverage: dict[str, Any], status_df: pd.DataFrame) -> dict[str, Any]:
    failed_count = int(status_df["status"].eq("failed").sum()) if not status_df.empty else 0
    empty_count = int(status_df["status"].eq("empty").sum()) if not status_df.empty else 0
    fetched_count = int(status_df["status"].eq("fetched").sum()) if not status_df.empty else 0
    covers = bool(coverage["mapping_covers_target_end"] and coverage["bars_cover_target_tminus1"])
    if covers and failed_count == 0:
        decision = "stage050_jd_contract_oi_source_gap_repaired_line_local"
        next_stage = "rerun_stage049_with_line_local_jd_repair_then_freeze_one_proxy"
    elif covers:
        decision = "stage050_jd_contract_oi_source_repaired_with_some_empty_or_failed_contracts_review_before_proxy"
        next_stage = "inspect_failed_contracts_before_stage049_rerun"
    else:
        decision = "stage050_jd_contract_oi_source_gap_still_open"
        next_stage = "retry_tqsdk_or_find_alternate_domestic_pit_source"
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": decision,
        "next_stage": next_stage,
        "product_vt_symbol": PRODUCT_VT_SYMBOL,
        "repair_start": REPAIR_START.date().isoformat(),
        "mapping_fetch_start": MAPPING_FETCH_START.date().isoformat(),
        "target_end": TARGET_END.date().isoformat(),
        "candidate_contract_count": int(len(status_df)),
        "fetched_count": fetched_count,
        "empty_count": empty_count,
        "failed_count": failed_count,
        "coverage": coverage,
        "strategy_changed": False,
        "shared_mapping_changed": False,
        "shared_database_changed": False,
        "true_engine": False,
        "ab_triggered": False,
        "ctp_connected": False,
        "order_api_called": False,
        "objective_completion_proven": False,
        "credential_status": _credential_status(),
        "external_research_judgment": (
            "TqSdk documentation supports daily futures K-line requests with open interest and KQ.m main-continuous "
            "symbols, while continuous/main contract rules are data-vendor constructions rather than alpha. Stage050 "
            "therefore repairs jd source coverage line-locally before any Stage049 proxy or true-engine test."
        ),
        "overfit_reflection_before": (
            "否。Stage050 只修复 jd.DCE 数据源覆盖，不根据收益选择合约、日期或阈值。"
        ),
        "continue_value_before": (
            "有。Stage049 已出现低自由度 OI 集中度候选，但 jd 缺口阻止目标品种池扩展验证。"
        ),
        "overfit_reflection_after": (
            "否。本阶段只判断数据源是否覆盖目标终点；若据此直接交易或扫 OI 阈值才是过拟合。"
        ),
        "continue_value_after": (
            "有条件。若 jd 映射和逐合约 OI 覆盖到 2026-06-30，下一步才允许重跑 Stage049/冻结一个 proxy。"
        ),
        "outputs": {
            "fetched_mapping": str(FETCHED_MAPPING_PATH),
            "combined_mapping": str(COMBINED_MAPPING_PATH),
            "contract_bars": str(CONTRACT_BARS_PATH),
            "contract_status": str(CONTRACT_STATUS_PATH),
            "source_coverage": str(SOURCE_COVERAGE_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(decision: dict[str, Any], status_df: pd.DataFrame, coverage_df: pd.DataFrame, stage_record_path: Path) -> None:
    report = f"""# Stage050 - jd.DCE 逐合约 OI 数据源线内修复

- 记录时间：`{datetime.now().strftime('%Y-%m-%dT%H:%M')}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 决策：`{decision['decision']}`

## 外部调研与判断

- TqSdk 文档支持用日线 K 线获取期货合约 `open_interest`，也支持 `KQ.m@DCE.jd` 这类主连/主力连续符号。
- 主力/连续合约是数据商规则，不是策略 alpha；Stage050 只修复点时数据覆盖，不把 OI 集中度直接交易化。

## 口径

- 产品：`{PRODUCT_VT_SYMBOL}`
- OI 修复起点：`{REPAIR_START.date().isoformat()}`
- 主力映射拉取起点：`{MAPPING_FETCH_START.date().isoformat()}`
- 目标终点：`{TARGET_END.date().isoformat()}`
- 输出只写本研究线，不修改共享 mapping CSV，不写 SQLite 数据库，不改 C9/15w 配置。

## 覆盖

{_md_table(coverage_df)}

## 合约拉取状态

{_md_table(status_df, max_rows=80)}

## 输出

- fetched_mapping：`{FETCHED_MAPPING_PATH}`
- combined_mapping：`{COMBINED_MAPPING_PATH}`
- contract_bars：`{CONTRACT_BARS_PATH}`
- contract_status：`{CONTRACT_STATUS_PATH}`
- source_coverage：`{SOURCE_COVERAGE_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`
- stage_record：`{stage_record_path}`

## 反思

- 运行前过拟合反思：{decision['overfit_reflection_before']}
- 运行后过拟合反思：{decision['overfit_reflection_after']}
- 运行前继续价值反思：{decision['continue_value_before']}
- 运行后继续价值反思：{decision['continue_value_after']}
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], coverage_df: pd.DataFrame, status_df: pd.DataFrame) -> Path:
    timestamp = datetime.now()
    stage_path = STAGES_DIR / f"{timestamp:%Y%m%d_%H%M}_stage050_jd_contract_oi_source_repair.md"
    lines = [
        "# Stage050 - jd.DCE 逐合约 OI 数据源线内修复",
        "",
        f"- 记录时间：`{timestamp.isoformat(timespec='minutes')}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 是否重要突破版本：`否`",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 本次版本变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage050_jd_contract_oi_source_repair.py`",
        "- 新增测试：`tests/test_rebuilt_c9_stage050_jd_oi_source_repair.py`",
        f"- 新增参数：`REPAIR_START={REPAIR_START.date().isoformat()}`、`MAPPING_FETCH_START={MAPPING_FETCH_START.date().isoformat()}`、`TARGET_END={TARGET_END.date().isoformat()}`、`MONTHS_BEFORE={MONTHS_BEFORE}`、`MONTHS_AFTER={MONTHS_AFTER}`。",
        "- 修改参数：无，官方 C9/15w 配置未改。",
        "- 删除参数：无。",
        "- 新增回测结果：无，本阶段不是收益回测，只做 jd 数据源修复/覆盖审计。",
        "- 共享 mapping CSV 未改；共享 SQLite 数据库未写；不连接 CTP，不调用订单 API，不触发 A/B。",
        "",
        "## 调研和判断结论",
        "",
        "- TqSdk 支持期货合约日线和 open interest，`KQ.m@DCE.jd` 可用于主力映射；主力规则是数据源构造，不能直接当 alpha。",
        "- 因此 Stage050 先做线内 jd 数据源修复包，为 Stage049 重跑和后续 proxy/true-engine 做准备。",
        "",
        "## 覆盖结果",
        "",
        _md_table(coverage_df),
        "",
        "## 合约状态",
        "",
        _md_table(status_df, max_rows=80),
        "",
        "## 输出",
        "",
        f"- fetched_mapping：`{FETCHED_MAPPING_PATH}`",
        f"- combined_mapping：`{COMBINED_MAPPING_PATH}`",
        f"- contract_bars：`{CONTRACT_BARS_PATH}`",
        f"- contract_status：`{CONTRACT_STATUS_PATH}`",
        f"- source_coverage：`{SOURCE_COVERAGE_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- report：`{REPORT_PATH}`",
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
        "",
        "## 后续规划和 TODO",
        "",
        f"- 下一步：`{decision['next_stage']}`。",
        "- 若覆盖完整，下一步重跑 Stage049，使用线内 jd 修复包检查数据源缺口是否清除。",
        "- 仍不得直接把 OI 集中度接入 AI 选品、开仓过滤或加风险。",
    ]
    stage_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return stage_path


def run() -> dict[str, Any]:
    started_at = time.time()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    existing_mapping = _existing_jd_mapping()
    fetched_mapping = fetch_mapping_rows(PRODUCT_VT_SYMBOL, MAPPING_FETCH_START, TARGET_END)
    combined_mapping = merge_mapping_rows(existing_mapping, fetched_mapping)
    contract_symbols = candidate_contract_vt_symbols(PRODUCT_VT_SYMBOL, REPAIR_START, TARGET_END)
    bars_df, status_df = fetch_contract_bars(contract_symbols, REPAIR_START, TARGET_END)
    coverage = build_jd_source_coverage(combined_mapping, bars_df, target_end=TARGET_END)
    coverage_df = pd.DataFrame([coverage])
    decision = _decision(coverage, status_df)
    decision["elapsed_seconds"] = round(time.time() - started_at, 2)

    fetched_mapping.to_csv(FETCHED_MAPPING_PATH, index=False, encoding="utf-8-sig")
    combined_mapping.to_csv(COMBINED_MAPPING_PATH, index=False, encoding="utf-8-sig")
    bars_df.to_csv(CONTRACT_BARS_PATH, index=False, encoding="utf-8-sig")
    status_df.to_csv(CONTRACT_STATUS_PATH, index=False, encoding="utf-8-sig")
    coverage_df.to_csv(SOURCE_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    stage_record = _write_stage_record(decision, coverage_df, status_df)
    _write_report(decision, status_df, coverage_df, stage_record)
    decision["stage_record_path"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return decision


def main() -> None:
    decision = run()
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
