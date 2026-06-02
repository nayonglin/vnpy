from __future__ import annotations

from datetime import datetime
import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage530_external_data_execution_readiness_v1"
OUTPUT_PREFIX = "qmt_roll_stage530_external_data_execution_readiness"

READINESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readiness_{MODEL_TAG}.csv"
PRIOR_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_prior_coverage_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

STAGE316_COVERAGE = OUTPUT_DIR / "qmt_roll_stage316_supply_demand_quality_probe_coverage_stage316_supply_demand_quality_probe_v1.csv"
STAGE358_COVERAGE = OUTPUT_DIR / "qmt_roll_stage358_supply_demand_backfill_2020_2022_coverage_stage358_supply_demand_backfill_2020_2022_v1.csv"
STAGE374_SUMMARY = OUTPUT_DIR / "qmt_roll_stage374_supply_demand_2015_2019_coverage_audit_summary_stage374_supply_demand_2015_2019_coverage_audit_v1.csv"


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
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _package_probe() -> dict[str, Any]:
    result: dict[str, Any] = {
        "akshare_installed": False,
        "akshare_version": "",
        "akshare_functions": {},
        "tushare_installed": False,
        "tushare_version": "",
        "tushare_token_present": bool(os.environ.get("TUSHARE_TOKEN")),
        "tushare_smoke_status": "not_run",
        "tushare_smoke_error": "",
    }
    try:
        import akshare as ak  # type: ignore

        result["akshare_installed"] = True
        result["akshare_version"] = str(getattr(ak, "__version__", "unknown"))
        for name in [
            "futures_spot_price",
            "futures_shfe_warehouse_receipt",
            "futures_warehouse_receipt_czce",
            "futures_warehouse_receipt_dce",
            "futures_gfex_warehouse_receipt",
        ]:
            result["akshare_functions"][name] = bool(hasattr(ak, name))
    except Exception as exc:  # pragma: no cover - diagnostic script
        result["akshare_error"] = f"{type(exc).__name__}: {str(exc)[:240]}"
    try:
        import tushare as ts  # type: ignore

        result["tushare_installed"] = True
        result["tushare_version"] = str(getattr(ts, "__version__", "unknown"))
        token = os.environ.get("TUSHARE_TOKEN")
        if token:
            try:
                pro = ts.pro_api(token)
                sample = pro.fut_basic(exchange="DCE", fields="ts_code,symbol,name,list_date,delist_date")
                result["tushare_smoke_status"] = "ok"
                result["tushare_fut_basic_rows"] = int(len(sample))
            except Exception as exc:  # pragma: no cover - depends on live credential
                result["tushare_smoke_status"] = "failed"
                result["tushare_smoke_error"] = f"{type(exc).__name__}: {str(exc)[:240]}"
        else:
            result["tushare_smoke_status"] = "missing_token"
    except Exception as exc:  # pragma: no cover - diagnostic script
        result["tushare_error"] = f"{type(exc).__name__}: {str(exc)[:240]}"
    return result


def _prior_coverage() -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for label, path in [
        ("stage316_2023_2026_supply_probe", STAGE316_COVERAGE),
        ("stage358_2020_2022_backfill", STAGE358_COVERAGE),
        ("stage374_2015_2019_sample", STAGE374_SUMMARY),
    ]:
        if not path.exists():
            rows.append(pd.DataFrame([{"source_stage": label, "file": str(path), "status": "missing"}]))
            continue
        frame = pd.read_csv(path, encoding="utf-8-sig")
        frame.insert(0, "source_stage", label)
        frame.insert(1, "file", path.name)
        frame["status"] = "loaded"
        rows.append(frame)
    return pd.concat(rows, ignore_index=True, sort=False)


def _readiness_rows(package: dict[str, Any]) -> pd.DataFrame:
    ak_funcs = package.get("akshare_functions", {})
    tushare_ok = package.get("tushare_smoke_status") == "ok"
    rows = [
        {
            "route": "basis",
            "source": "AKShare futures_spot_price",
            "package_ready": bool(ak_funcs.get("futures_spot_price")),
            "credential_ready": True,
            "prior_evidence": "2015-2019、2020-2022、2023-2026 多段均有覆盖；旧因子样本外排序不稳定。",
            "execution_grade": "paper_explain_or_low_degree_filter_only",
            "blocker": "不能继续调基差权重/窗口；若接入，只能服务固定坏窗口解释或单次强逆风防守验证。",
        },
        {
            "route": "warehouse_receipt",
            "source": "AKShare exchange warehouse receipt",
            "package_ready": all(
                bool(ak_funcs.get(name))
                for name in [
                    "futures_shfe_warehouse_receipt",
                    "futures_warehouse_receipt_czce",
                    "futures_warehouse_receipt_dce",
                    "futures_gfex_warehouse_receipt",
                ]
            ),
            "credential_ready": True,
            "prior_evidence": "CZCE较可用；SHFE/DCE/GFEX 历史解析存在空值或 JSONDecodeError，黑色链不能声称三组件完整。",
            "execution_grade": "not_ready_for_core_signal",
            "blocker": "需要先解决 SHFE/DCE 历史仓单解析或替代数据源。",
        },
        {
            "route": "member_holding",
            "source": "Tushare fut_holding / exchange member rank",
            "package_ready": bool(package.get("tushare_installed")),
            "credential_ready": bool(tushare_ok),
            "prior_evidence": "Stage016 会员净多变化样本外不单调；当前 Tushare token 冒烟失败。",
            "execution_grade": "not_ready_for_live_pipeline",
            "blocker": "先修复 Tushare token 或使用交易所/AKShare替代；不继续调会员净多窗口/TopN。",
        },
        {
            "route": "cot",
            "source": "CFTC COT",
            "package_ready": True,
            "credential_ready": True,
            "prior_evidence": "Stage014 已反证，COT 对中国商品开仓质量 test 桶不稳定。",
            "execution_grade": "explain_only",
            "blocker": "外盘周频持仓不能直接映射国内日频执行候选。",
        },
        {
            "route": "news_sentiment",
            "source": "news/social sentiment",
            "package_ready": False,
            "credential_ready": False,
            "prior_evidence": "当前仓库无带接收时间戳、历史可回放、品种映射的舆情账本。",
            "execution_grade": "not_ready_even_for_backtest",
            "blocker": "必须先建立实时采集和发布/接收时间账本；否则2020-2026回测存在信息泄漏。",
        },
    ]
    return pd.DataFrame(rows)


def _decision(readiness: pd.DataFrame, package: dict[str, Any]) -> dict[str, Any]:
    basis_ready = bool(readiness[readiness["route"].eq("basis")]["package_ready"].iloc[0])
    member_ready = bool(readiness[readiness["route"].eq("member_holding")]["credential_ready"].iloc[0])
    sentiment_ready = bool(readiness[readiness["route"].eq("news_sentiment")]["credential_ready"].iloc[0])
    if basis_ready and not member_ready and not sentiment_ready:
        label = "basis_explain_ready_member_and_sentiment_not_live_ready"
    else:
        label = "external_data_readiness_mixed"
    return {
        "decision": label,
        "package_probe": package,
        "readiness": readiness.to_dict(orient="records"),
        "next_allowed_use": [
            "basis 可作为坏窗口解释和一次固定强逆风防守验证的候选输入",
            "仓单需先修复 SHFE/DCE 历史覆盖，不能直接进入核心信号",
            "会员持仓需先修复 Tushare token 或替代源，且不救 Stage016 小参数",
            "舆情必须先建设点时化接收账本，当前不进回测",
        ],
    }


def _write_report(readiness: pd.DataFrame, coverage: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage530 外生数据实盘可执行性审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        "- 性质：数据工程可执行性审计；不新增交易规则，不做回测。",
        f"- 决策：`{decision.get('decision', '')}`。",
        "",
        "## Readiness",
        "",
        _md_table(readiness),
        "",
        "## Prior Coverage",
        "",
        _md_table(coverage.head(40)),
        "",
        "## Decision",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    package = _package_probe()
    coverage = _prior_coverage()
    readiness = _readiness_rows(package)
    decision = _decision(readiness, package)
    _write_report(readiness, coverage, decision)
    readiness.to_csv(READINESS_PATH, index=False, encoding="utf-8-sig")
    coverage.to_csv(PRIOR_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
