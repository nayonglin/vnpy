from __future__ import annotations

from datetime import datetime
import hashlib
import inspect
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage089"
MODEL_TAG = "stage089_jd_margin_endpoint_probe_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage089_jd_margin_endpoint_probe"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage089_jd_margin_endpoint_probe"
STAGES_DIR = LINE_DIR / "stages"

SOURCE_PROBE_PATH = OUT / f"{OUTPUT_PREFIX}_source_probe_{MODEL_TAG}.csv"
GTJA_RULE_SAMPLE_PATH = OUT / f"{OUTPUT_PREFIX}_gtja_rule_sample_{MODEL_TAG}.csv"
GTJA_ADJUSTMENTS_PATH = OUT / f"{OUTPUT_PREFIX}_gtja_jd_adjustments_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

REQUIRED_START = pd.Timestamp("2020-01-02")
REQUIRED_END = pd.Timestamp("2026-06-30")

SAMPLE_DATES = (
    "20200102",
    "20200630",
    "20210104",
    "20210630",
    "20220104",
    "20220630",
    "20230103",
    "20230630",
    "20240102",
    "20240603",
    "20250102",
    "20250630",
    "20260102",
    "20260629",
)

EXTERNAL_RESEARCH = [
    {
        "source_id": "dce_daily_trading_parameters",
        "url": "https://www.dce.com.cn/dceg/channel/list/488.html",
        "use": "DCE has a Daily Trading Parameters page, but terminal direct access was not available in this run.",
    },
    {
        "source_id": "dce_egg_contract_page",
        "url": "https://www.dce.com.cn/dce/channel/list/127.html",
        "use": "DCE contract page states JD minimum trading margin and notes DCE may adjust margins by market conditions.",
    },
    {
        "source_id": "akshare_futures_docs",
        "url": "https://akshare-hh.readthedocs.io/en/latest/data/futures/futures.html",
        "use": "AKShare docs expose a static futures margin table updated on 2021-09-03; this is not a PIT daily series.",
    },
    {
        "source_id": "akshare_github_docs",
        "url": "https://github.com/akfamily/akshare/blob/main/docs/data/futures/futures.md",
        "use": "GitHub docs were checked for futures data surface area; margin history must still be source-audited.",
    },
]


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


def _call_source(name: str, func: Callable[[], pd.DataFrame]) -> tuple[str, pd.DataFrame, str]:
    try:
        data = func()
        return "ok", data if isinstance(data, pd.DataFrame) else pd.DataFrame(), ""
    except Exception as exc:  # noqa: BLE001 - this is an endpoint probe.
        return "error", pd.DataFrame(), f"{type(exc).__name__}: {str(exc)[:300]}"


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(str(value).strip().strip("%"))
    except (TypeError, ValueError):
        return None


def _contains_jd(data: pd.DataFrame) -> pd.Series:
    if data.empty:
        return pd.Series(dtype=bool)
    return data.astype(str).apply(lambda col: col.str.contains("鸡蛋|JD|jd", case=False, na=False)).any(axis=1)


def _parse_gtja_adjustments(trade_date: str, text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not text or text == "nan":
        return rows
    for code, percent in re.findall(r"(?i)(JD\d{4})合约交易保证金比例为([0-9.]+)%", text):
        rows.append(
            {
                "trade_date": pd.to_datetime(trade_date).date().isoformat(),
                "contract_vt": f"{code.lower()}.DCE",
                "broker_margin_ratio": float(percent) / 100.0,
                "raw_adjustment": text,
                "source_system": "akshare.futures_rule_gtja_calendar",
                "accepted_for_true_ledger": False,
                "reject_reason": "sample_only_not_full_pit_contract_daily_series",
            }
        )
    return rows


def _audit_akshare_sources() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    import akshare as ak

    probe_rows: list[dict[str, Any]] = []
    sample_rows: list[dict[str, Any]] = []
    adjustment_rows: list[dict[str, Any]] = []

    settle_status, settle_df, settle_error = _call_source(
        "akshare_futures_settle_dce_sample",
        lambda: ak.futures_settle(date="20240603", market="DCE"),
    )
    probe_rows.append(
        {
            "candidate_id": "akshare_futures_settle_dce",
            "source_type": "exchange_settlement_api_wrapper",
            "status": "empty_unsupported" if settle_status == "ok" and settle_df.empty else settle_status,
            "row_count": len(settle_df),
            "jd_row_count": int(_contains_jd(settle_df).sum()) if not settle_df.empty else 0,
            "has_margin_columns": bool(
                not settle_df.empty
                and any("margin" in str(col).lower() or "保证金" in str(col) for col in settle_df.columns)
            ),
            "has_contract_grain": bool(not settle_df.empty and "symbol" in settle_df.columns),
            "has_trade_date": bool(not settle_df.empty and "date" in settle_df.columns),
            "covers_required_range_probe": False,
            "accepted_for_jd_contract_daily_margin_history": False,
            "pit_acceptance": "rejected",
            "reject_reason": "current_akshare_wrapper_unsupported_dce",
            "detail": settle_error or "DCE returns empty because wrapper has no DCE branch in installed akshare.",
        }
    )

    contract_status, contract_df, contract_error = _call_source(
        "akshare_futures_contract_info_dce",
        ak.futures_contract_info_dce,
    )
    probe_rows.append(
        {
            "candidate_id": "akshare_futures_contract_info_dce",
            "source_type": "dce_contract_static_info",
            "status": contract_status,
            "row_count": len(contract_df),
            "jd_row_count": int(_contains_jd(contract_df).sum()) if not contract_df.empty else 0,
            "has_margin_columns": bool(any("margin" in str(col).lower() or "保证金" in str(col) for col in contract_df.columns)),
            "has_contract_grain": "合约" in contract_df.columns,
            "has_trade_date": False,
            "covers_required_range_probe": False,
            "accepted_for_jd_contract_daily_margin_history": False,
            "pit_acceptance": "rejected",
            "reject_reason": "contract_static_info_not_margin_history",
            "detail": contract_error or "Contract info endpoint is static product/contract metadata, not daily margin history.",
        }
    )

    for date in SAMPLE_DATES:
        status, data, error = _call_source(f"akshare_futures_rule_{date}", lambda d=date: ak.futures_rule(date=d))
        jd_rows = data[_contains_jd(data)].copy() if status == "ok" and not data.empty else pd.DataFrame()
        product_margin_pct = None
        adjustment_text = ""
        if not jd_rows.empty:
            futures_rows = jd_rows[jd_rows.get("代码", pd.Series(dtype=object)).astype(str).str.upper().eq("JD")]
            if futures_rows.empty:
                futures_rows = jd_rows.head(1)
            row = futures_rows.iloc[0]
            product_margin_pct = _safe_float(row.get("交易保证金比例"))
            adjustment_text = str(row.get("特殊合约参数调整", ""))
            adjustment_rows.extend(_parse_gtja_adjustments(date, adjustment_text))
        sample_rows.append(
            {
                "trade_date": pd.to_datetime(date, errors="coerce").date().isoformat(),
                "status": status,
                "row_count": len(data),
                "jd_row_count": len(jd_rows),
                "jd_product_broker_margin_ratio": product_margin_pct / 100.0 if product_margin_pct is not None else None,
                "raw_adjustment": adjustment_text,
                "error": error,
            }
        )

    sample_df = pd.DataFrame(sample_rows)
    ok_sample_count = int(sample_df["status"].eq("ok").sum()) if not sample_df.empty else 0
    jd_sample_count = int(sample_df["jd_row_count"].gt(0).sum()) if not sample_df.empty else 0
    earliest_ok = sample_df.loc[sample_df["status"].eq("ok"), "trade_date"].min() if ok_sample_count else ""
    latest_ok = sample_df.loc[sample_df["status"].eq("ok"), "trade_date"].max() if ok_sample_count else ""
    probe_rows.append(
        {
            "candidate_id": "akshare_futures_rule_gtja_jd_margin",
            "source_type": "broker_calendar_margin_probe",
            "status": "ok" if ok_sample_count else "error",
            "row_count": int(sample_df["row_count"].sum()) if not sample_df.empty else 0,
            "jd_row_count": jd_sample_count,
            "has_margin_columns": True,
            "has_contract_grain": False,
            "has_trade_date": True,
            "covers_required_range_probe": bool(earliest_ok <= REQUIRED_START.date().isoformat() and latest_ok >= REQUIRED_END.date().isoformat()) if ok_sample_count else False,
            "accepted_for_jd_contract_daily_margin_history": False,
            "pit_acceptance": "rebuild_candidate_not_accepted",
            "reject_reason": "sample_probe_only_needs_full_history_contract_expansion_publish_hash",
            "detail": (
                f"sample_dates={len(sample_df)} ok={ok_sample_count} jd={jd_sample_count}; "
                f"earliest_ok={earliest_ok} latest_ok={latest_ok}; "
                "provides broker-like product margin and special adjustment text, but not yet a full contract-daily PIT dataset."
            ),
        }
    )

    fees_status, fees_df, fees_error = _call_source("akshare_futures_fees_info_openctp", ak.futures_fees_info)
    fees_jd = fees_df[_contains_jd(fees_df)].copy() if fees_status == "ok" and not fees_df.empty else pd.DataFrame()
    fees_time = ""
    if not fees_jd.empty and "更新时间" in fees_jd.columns:
        fees_time = str(fees_jd["更新时间"].dropna().astype(str).max())
    probe_rows.append(
        {
            "candidate_id": "akshare_futures_fees_info_openctp_current",
            "source_type": "current_snapshot_openctp",
            "status": fees_status,
            "row_count": len(fees_df),
            "jd_row_count": len(fees_jd),
            "has_margin_columns": bool(any("保证金" in str(col) or "margin" in str(col).lower() for col in fees_df.columns)),
            "has_contract_grain": "合约代码" in fees_df.columns,
            "has_trade_date": False,
            "covers_required_range_probe": False,
            "accepted_for_jd_contract_daily_margin_history": False,
            "pit_acceptance": "rejected",
            "reject_reason": "current_snapshot_not_history",
            "detail": fees_error or f"current snapshot update_time={fees_time}",
        }
    )

    comm_status, comm_df, comm_error = _call_source(
        "akshare_futures_comm_info_9qihuo_dce",
        lambda: ak.futures_comm_info("大连商品交易所"),
    )
    comm_jd = comm_df[_contains_jd(comm_df)].copy() if comm_status == "ok" and not comm_df.empty else pd.DataFrame()
    price_time = ""
    if not comm_jd.empty and "价格更新时间" in comm_jd.columns:
        price_time = str(comm_jd["价格更新时间"].dropna().astype(str).max())
    probe_rows.append(
        {
            "candidate_id": "akshare_futures_comm_info_9qihuo_current",
            "source_type": "current_snapshot_9qihuo",
            "status": comm_status,
            "row_count": len(comm_df),
            "jd_row_count": len(comm_jd),
            "has_margin_columns": bool(any("保证金" in str(col) or "margin" in str(col).lower() for col in comm_df.columns)),
            "has_contract_grain": "合约代码" in comm_df.columns,
            "has_trade_date": False,
            "covers_required_range_probe": False,
            "accepted_for_jd_contract_daily_margin_history": False,
            "pit_acceptance": "rejected",
            "reject_reason": "current_snapshot_not_history",
            "detail": comm_error or f"current snapshot price_update_time={price_time}",
        }
    )

    source_files: list[Path] = []
    for func in [ak.futures_settle, ak.futures_rule, ak.futures_fees_info, ak.futures_comm_info, ak.futures_contract_info_dce]:
        path = inspect.getsourcefile(func)
        if path:
            source_files.append(Path(path))
    input_audit = _input_audit(sorted(set(source_files)))
    return pd.DataFrame(probe_rows), sample_df, pd.DataFrame(adjustment_rows), input_audit


def _input_audit(paths: list[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.exists() and path.is_file():
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


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    source_probe, gtja_sample, gtja_adjustments, input_audit = _audit_akshare_sources()

    accepted_count = int(source_probe["accepted_for_jd_contract_daily_margin_history"].astype(bool).sum())
    rebuild_candidate_count = int(source_probe["pit_acceptance"].eq("rebuild_candidate_not_accepted").sum())
    gtja_ok_count = int(gtja_sample["status"].eq("ok").sum()) if not gtja_sample.empty else 0
    gtja_jd_count = int(gtja_sample["jd_row_count"].gt(0).sum()) if not gtja_sample.empty else 0
    gtja_adjustment_count = int(len(gtja_adjustments))

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": "stage089_gtja_margin_route_candidate_but_no_accepted_daily_history",
        "accepted_candidate_count": accepted_count,
        "rebuild_candidate_count": rebuild_candidate_count,
        "gtja_sample_date_count": int(len(gtja_sample)),
        "gtja_ok_sample_count": gtja_ok_count,
        "gtja_jd_sample_count": gtja_jd_count,
        "gtja_contract_adjustment_count": gtja_adjustment_count,
        "ready_for_true_ledger_replay": False,
        "remaining_blocker": "jd_contract_daily_margin_history",
        "strategy_changed": False,
        "true_engine_run": False,
        "order_api_calls": 0,
        "ctp_connected": False,
        "next_step": "Stage090 can batch-probe GTJA futures_rule only as a broker-margin-history reconstruction route; DCE/vendor official data remains preferred.",
    }

    source_probe.to_csv(SOURCE_PROBE_PATH, index=False, encoding="utf-8-sig")
    gtja_sample.to_csv(GTJA_RULE_SAMPLE_PATH, index=False, encoding="utf-8-sig")
    gtja_adjustments.to_csv(GTJA_ADJUSTMENTS_PATH, index=False, encoding="utf-8-sig")
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    report_lines = [
        "# Stage089 jd margin endpoint probe",
        "",
        "## 结论",
        "",
        "- `akshare.futures_rule` / GTJA 交易日历样本能返回 JD 产品保证金和部分特殊合约保证金调整，是下一步可采集候选。",
        "- 但本阶段没有任何 accepted `jd_contract_daily_margin_history`：GTJA 仍缺全区间逐日覆盖、逐合约展开、发布时间/有效时间链和源哈希；OpenCTP/九期网只是当前快照；AKShare `futures_settle(market='DCE')` 当前 wrapper 不支持 DCE。",
        "- 因此 Stage208 true ledger 仍禁止，不能用这些样本直接回测。",
        "",
        "## 外部调研与判断",
        "",
    ]
    for item in EXTERNAL_RESEARCH:
        report_lines.append(f"- `{item['source_id']}`：{item['url']}；{item['use']}")
    report_lines.extend(
        [
            "",
            "## Source Probe",
            "",
            _md_table(source_probe),
            "",
            "## GTJA Rule Sample",
            "",
            _md_table(gtja_sample),
            "",
            "## Parsed JD Adjustments",
            "",
            _md_table(gtja_adjustments),
            "",
            "## 决策",
            "",
            f"- decision：`{decision['decision']}`",
            f"- accepted_candidate_count：`{accepted_count}`",
            f"- rebuild_candidate_count：`{rebuild_candidate_count}`",
            f"- ready_for_true_ledger_replay：`{decision['ready_for_true_ledger_replay']}`",
            f"- remaining_blocker：`{decision['remaining_blocker']}`",
            "",
            "## 反思",
            "",
            "- 运行前过拟合反思：否。本阶段只审计数据接口，不调整交易规则或收益目标。",
            "- 运行后过拟合反思：否。虽然发现 GTJA 样本可用，但没有把样本保证金直接当作策略输入。",
            "- 运行前继续价值反思：有。Stage088 已证明本地没有 accepted 源，需要判断外部接口路线。",
            "- 运行后继续价值反思：有条件。GTJA 路线值得做一次批量覆盖/解析验收，但 DCE/vendor 官方逐日参数仍是优先级更高的数据源。",
            "",
            "## 输出",
            "",
            f"- source_probe：`{SOURCE_PROBE_PATH}`",
            f"- gtja_rule_sample：`{GTJA_RULE_SAMPLE_PATH}`",
            f"- gtja_adjustments：`{GTJA_ADJUSTMENTS_PATH}`",
            f"- input_audit：`{INPUT_AUDIT_PATH}`",
            f"- decision：`{DECISION_PATH}`",
        ]
    )
    REPORT_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    stage_path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage089_jd_margin_endpoint_probe.md"
    stage_text = f"""# Stage089 jd margin endpoint probe

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{datetime.now().isoformat(timespec="seconds")}
- 阶段性质：只读接口/数据源探针；不回测收益，不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

{chr(10).join(f"- `{item['source_id']}`：{item['url']}；{item['use']}" for item in EXTERNAL_RESEARCH)}

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage089_jd_margin_endpoint_probe.py`
- 新增参数：`SAMPLE_DATES={SAMPLE_DATES}`
- 修改参数：无正式策略参数修改。
- 删除参数：无。

## 结果

- decision：`{decision['decision']}`
- accepted_candidate_count：`{accepted_count}`
- rebuild_candidate_count：`{rebuild_candidate_count}`
- gtja_sample_date_count：`{len(gtja_sample)}`
- gtja_ok_sample_count：`{gtja_ok_count}`
- gtja_jd_sample_count：`{gtja_jd_count}`
- gtja_contract_adjustment_count：`{gtja_adjustment_count}`
- ready_for_true_ledger_replay：`False`
- remaining_blocker：`jd_contract_daily_margin_history`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## Source Probe

{_md_table(source_probe)}

## GTJA Rule Sample

{_md_table(gtja_sample)}

## Parsed JD Adjustments

{_md_table(gtja_adjustments)}

## 回测记录字段

- 本阶段不新增回测，因此不新增期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率。

## 过拟合反思

- 运行前：否。本阶段只审计数据接口，不调整交易规则或收益目标。
- 运行后：否。虽然发现 GTJA 样本可用，但没有把样本保证金直接当作策略输入。

## 继续价值反思

- 运行前：有。Stage088 已证明本地没有 accepted 源，需要判断外部接口路线。
- 运行后：有条件。GTJA 路线值得做一次批量覆盖/解析验收，但 DCE/vendor 官方逐日参数仍是优先级更高的数据源。

## 输出文件

- report：`{REPORT_PATH}`
- source_probe：`{SOURCE_PROBE_PATH}`
- gtja_rule_sample：`{GTJA_RULE_SAMPLE_PATH}`
- gtja_adjustments：`{GTJA_ADJUSTMENTS_PATH}`
- input_audit：`{INPUT_AUDIT_PATH}`
- decision：`{DECISION_PATH}`
"""
    stage_path.write_text(stage_text, encoding="utf-8")
    print(json.dumps(_json_safe({"stage_record": stage_path, **decision}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
