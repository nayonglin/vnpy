from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

from qmt_universe import MARGIN_RATIOS  # noqa: E402


LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage088"
MODEL_TAG = "stage088_jd_margin_source_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage088_jd_margin_source_audit"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage088_jd_margin_source_audit"
STAGES_DIR = LINE_DIR / "stages"

STAGE049_SPEC_AUDIT = LINE_DIR / "outputs/stage049_stage208_true_carry_replay_gate/rebuilt_c9_v2_stage049_stage208_true_carry_replay_gate_contract_spec_audit_stage049_stage208_true_carry_replay_gate_v1.csv"
STAGE050_CONTRACT = LINE_DIR / "outputs/stage050_jd_true_carry_data_manifest/rebuilt_c9_v2_stage050_jd_true_carry_data_manifest_source_contract_stage050_jd_true_carry_data_manifest_v1.csv"
TQSDK_METADATA = PORTFOLIO_DIR / "backtest_outputs/tqsdk_all_futures_contract_metadata.csv"
TQSDK_DAILY_DIR = PORTFOLIO_DIR / "downloaded_futures/tqsdk_daily_2010_2026_04/DCE"
STAGE901_PRODUCT_MARGIN = PORTFOLIO_DIR / "backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_product_margin_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv"
STAGE655_POSITIONS = PORTFOLIO_DIR / "backtest_outputs/qmt_roll_stage655_readonly_account_margin_probe_positions_stage655_readonly_account_margin_probe_v1.csv"

CANDIDATE_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_audit_{MODEL_TAG}.csv"
TQSDK_DAILY_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_tqsdk_daily_jd_audit_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

REQUIRED_START = pd.Timestamp("2020-01-02")
REQUIRED_END = pd.Timestamp("2026-06-30")

SOURCE_LINKS = {
    "dce_egg_contract": "https://www.dce.com.cn/dceg/channel/list/428.html",
    "dce_egg_business_rules": "https://www.dce.com.cn/dalianshangpin/fgfz/6142914/6142926/6146560/index.html",
    "dce_egg_cn": "https://www.dce.com.cn/dalianshangpin/sspz/487261/index.html",
}


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


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _input_audit(paths: list[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.exists() and path.is_file():
            stat = path.stat()
            rows.append(
                {
                    "path": str(path),
                    "exists": True,
                    "kind": "file",
                    "bytes": int(stat.st_size),
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    "sha256": _sha256(path),
                }
            )
        elif path.exists() and path.is_dir():
            rows.append(
                {
                    "path": str(path),
                    "exists": True,
                    "kind": "dir",
                    "bytes": 0,
                    "mtime": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
                    "sha256": "",
                }
            )
        else:
            rows.append({"path": str(path), "exists": False, "kind": "", "bytes": 0, "mtime": "", "sha256": ""})
    return pd.DataFrame(rows)


def _date_span(data: pd.DataFrame) -> tuple[str, str]:
    if data.empty:
        return "", ""
    for column in ["trade_date", "date", "datetime", "bar_datetime"]:
        if column in data.columns:
            dates = pd.to_datetime(data[column], errors="coerce").dropna()
            if not dates.empty:
                return dates.min().date().isoformat(), dates.max().date().isoformat()
    return "", ""


def audit_tqsdk_daily_dir() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in sorted(TQSDK_DAILY_DIR.glob("jd*.csv")):
        data = _read_csv(path)
        start, end = _date_span(data)
        start_ts = pd.to_datetime(start, errors="coerce")
        end_ts = pd.to_datetime(end, errors="coerce")
        covers_required = bool(
            pd.notna(start_ts)
            and pd.notna(end_ts)
            and start_ts <= REQUIRED_START
            and end_ts >= REQUIRED_END
        )
        rows.append(
            {
                "contract_vt": f"{path.stem}.DCE",
                "path": str(path),
                "rows": int(len(data)),
                "start_date": start,
                "end_date": end,
                "covers_required_range": covers_required,
                "columns": ",".join(data.columns.astype(str).tolist()),
                "has_daily_margin_ratio": any("margin" in str(col).lower() for col in data.columns),
                "sha256": _sha256(path) if path.exists() else "",
            }
        )
    return pd.DataFrame(rows)


def _candidate_row(
    candidate_id: str,
    source_type: str,
    path: str,
    row_count: int,
    jd_row_count: int,
    start_date: str,
    end_date: str,
    has_contract_vt: bool,
    has_trade_date: bool,
    has_daily_margin_ratio: bool,
    has_static_minimum_margin: bool,
    covers_required_range: bool,
    pit_acceptance: str,
    reject_reason: str,
    detail: str,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "source_type": source_type,
        "path": path,
        "row_count": int(row_count),
        "jd_row_count": int(jd_row_count),
        "start_date": start_date,
        "end_date": end_date,
        "has_contract_vt": bool(has_contract_vt),
        "has_trade_date": bool(has_trade_date),
        "has_daily_margin_ratio": bool(has_daily_margin_ratio),
        "has_static_minimum_margin": bool(has_static_minimum_margin),
        "covers_required_range": bool(covers_required_range),
        "accepted_for_jd_contract_daily_margin_history": pit_acceptance == "accepted",
        "pit_acceptance": pit_acceptance,
        "reject_reason": reject_reason,
        "detail": detail,
    }


def build_candidate_audit(tqsdk_daily_audit: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    rows.append(
        _candidate_row(
            "dce_public_contract_minimum",
            "external_public_static_rule",
            ";".join(SOURCE_LINKS.values()),
            1,
            1,
            "",
            "",
            False,
            False,
            False,
            True,
            False,
            "rejected",
            "static_minimum_margin_not_contract_daily_history",
            "DCE pages state minimum margin is 5% and may be adjusted by market conditions; not PIT daily contract history.",
        )
    )

    stage049 = _read_csv(STAGE049_SPEC_AUDIT)
    jd049 = stage049[stage049.get("product_vt_symbol", pd.Series(dtype=object)).astype(str).eq("jd.DCE")] if not stage049.empty else pd.DataFrame()
    start, end = _date_span(stage049)
    rows.append(
        _candidate_row(
            "stage049_contract_spec_audit",
            "derived_readiness_audit",
            str(STAGE049_SPEC_AUDIT),
            len(stage049),
            len(jd049),
            start,
            end,
            False,
            False,
            "margin_ratio" in stage049.columns,
            False,
            False,
            "rejected",
            "audit_snapshot_says_jd_margin_missing",
            f"jd_margin_ratio={jd049['margin_ratio'].iloc[0] if not jd049.empty and 'margin_ratio' in jd049.columns else ''}",
        )
    )

    metadata = _read_csv(TQSDK_METADATA)
    jd_meta = metadata[metadata.get("vt_symbol", pd.Series(dtype=object)).astype(str).eq("jd.DCE")] if not metadata.empty else pd.DataFrame()
    start, end = _date_span(metadata)
    end_ts = pd.to_datetime(end, errors="coerce")
    meta_margin_available = bool(
        not jd_meta.empty
        and "margin_ratio" in jd_meta.columns
        and pd.to_numeric(jd_meta["margin_ratio"], errors="coerce").notna().any()
    )
    rows.append(
        _candidate_row(
            "tqsdk_all_futures_contract_metadata",
            "latest_metadata_snapshot",
            str(TQSDK_METADATA),
            len(metadata),
            len(jd_meta),
            start,
            end,
            "vt_symbol" in metadata.columns,
            False,
            "margin_ratio" in metadata.columns,
            False,
            bool(pd.notna(end_ts) and end_ts >= REQUIRED_END),
            "rejected",
            "latest_snapshot_not_daily_history_and_jd_margin_nan" if not meta_margin_available else "latest_snapshot_not_daily_history",
            f"fetched_at={jd_meta['fetched_at'].iloc[0] if not jd_meta.empty and 'fetched_at' in jd_meta.columns else ''}",
        )
    )

    if tqsdk_daily_audit.empty:
        daily_start, daily_end, jd_rows, has_margin = "", "", 0, False
    else:
        daily_start = str(tqsdk_daily_audit["start_date"].dropna().min())
        daily_end = str(tqsdk_daily_audit["end_date"].dropna().max())
        jd_rows = int(len(tqsdk_daily_audit))
        has_margin = bool(tqsdk_daily_audit["has_daily_margin_ratio"].astype(bool).any())
        covers_required = bool(tqsdk_daily_audit["covers_required_range"].astype(bool).any())
    rows.append(
        _candidate_row(
            "tqsdk_daily_2010_2026_04_jd_files",
            "daily_price_files",
            str(TQSDK_DAILY_DIR),
            int(tqsdk_daily_audit["rows"].sum()) if not tqsdk_daily_audit.empty else 0,
            jd_rows,
            daily_start,
            daily_end,
            True,
            True,
            has_margin,
            False,
            covers_required,
            "rejected",
            "daily_price_oi_files_without_margin_ratio",
            "Useful for prices/OI, but columns do not contain exchange/broker margin ratios.",
        )
    )

    stage901 = _read_csv(STAGE901_PRODUCT_MARGIN)
    jd901 = stage901[stage901.get("product_vt_symbol", pd.Series(dtype=object)).astype(str).eq("jd.DCE")] if not stage901.empty else pd.DataFrame()
    start, end = _date_span(stage901)
    start_ts = pd.to_datetime(start, errors="coerce")
    end_ts = pd.to_datetime(end, errors="coerce")
    rows.append(
        _candidate_row(
            "stage901_2026_ytd_live_shadow_product_margin",
            "derived_strategy_margin_path",
            str(STAGE901_PRODUCT_MARGIN),
            len(stage901),
            len(jd901),
            start,
            end,
            "active_contracts" in stage901.columns,
            "date" in stage901.columns,
            any("margin" in str(col).lower() for col in stage901.columns),
            False,
            bool(
                pd.notna(start_ts)
                and pd.notna(end_ts)
                and start_ts <= REQUIRED_START
                and end_ts >= REQUIRED_END
            ),
            "rejected",
            "derived_shadow_margin_not_contract_daily_spec_and_no_jd_rows",
            "This is product margin usage from live shadow path, not margin-ratio source history.",
        )
    )

    stage655 = _read_csv(STAGE655_POSITIONS)
    jd655 = stage655[stage655.get("instrument", pd.Series(dtype=object)).astype(str).str.lower().str.startswith("jd")] if not stage655.empty else pd.DataFrame()
    start, end = _date_span(stage655)
    start_ts = pd.to_datetime(start, errors="coerce")
    end_ts = pd.to_datetime(end, errors="coerce")
    rows.append(
        _candidate_row(
            "stage655_readonly_account_margin_probe_positions",
            "single_live_account_snapshot",
            str(STAGE655_POSITIONS),
            len(stage655),
            len(jd655),
            start,
            end,
            "instrument" in stage655.columns,
            "snapshot_at" in stage655.columns,
            "use_margin" in stage655.columns,
            False,
            bool(
                pd.notna(start_ts)
                and pd.notna(end_ts)
                and start_ts <= REQUIRED_START
                and end_ts >= REQUIRED_END
            ),
            "rejected",
            "single_account_snapshot_not_daily_contract_history_and_no_jd_rows",
            "Broker account use_margin snapshot is not exchange/broker margin ratio time series.",
        )
    )

    qmt_jd_margin = MARGIN_RATIOS.get("jd.DCE")
    rows.append(
        _candidate_row(
            "qmt_universe_static_margin_ratios",
            "static_code_constant",
            "examples/portfolio_backtesting/qmt_universe.py",
            len(MARGIN_RATIOS),
            1 if qmt_jd_margin is not None else 0,
            "",
            "",
            False,
            False,
            qmt_jd_margin is not None,
            False,
            False,
            "rejected",
            "static_constant_not_contract_daily_history" if qmt_jd_margin is not None else "jd_margin_missing",
            f"jd.DCE={qmt_jd_margin}",
        )
    )

    return pd.DataFrame(rows)


def make_decision(candidate_audit: pd.DataFrame, tqsdk_daily_audit: pd.DataFrame) -> dict[str, Any]:
    accepted = candidate_audit[candidate_audit["accepted_for_jd_contract_daily_margin_history"].astype(bool)].copy()
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": "stage088_jd_margin_source_audit_no_accepted_daily_history",
        "accepted_candidate_count": int(len(accepted)),
        "candidate_count": int(len(candidate_audit)),
        "tqsdk_daily_jd_file_count": int(len(tqsdk_daily_audit)),
        "tqsdk_daily_has_margin_columns": bool(tqsdk_daily_audit["has_daily_margin_ratio"].astype(bool).any()) if not tqsdk_daily_audit.empty else False,
        "tqsdk_daily_covers_required_range_count": int(tqsdk_daily_audit["covers_required_range"].astype(bool).sum()) if not tqsdk_daily_audit.empty else 0,
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
            "DCE 鸡蛋合约页给出最低保证金 5%，但同时说明交易所可按市场情况调整保证金；"
            "因此 Stage208 真承载不能使用静态最低保证金、当前 metadata 快照或 live/shadow margin usage 替代逐日合约保证金历史。"
        ),
        "overfit_reflection_before": "否。本阶段只读审计数据源，不补交易规则、不看收益曲线。",
        "overfit_reflection_after": "否。结论是继续阻塞，不用静态/快照字段冒充历史序列。",
        "continue_value_before": "有。Stage087 已继续减少分钟缺口，但保证金历史是更硬的真承载 blocker。",
        "continue_value_after": "有。下一步应寻找 broker/vendor/DCE daily parameters 级别的 PIT 保证金历史，或继续补分钟线但不能跑 true ledger。",
        "outputs": {
            "candidate_audit": str(CANDIDATE_AUDIT_PATH),
            "tqsdk_daily_audit": str(TQSDK_DAILY_AUDIT_PATH),
            "input_audit": str(INPUT_AUDIT_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(decision: dict[str, Any], candidate_audit: pd.DataFrame, tqsdk_daily_audit: pd.DataFrame) -> None:
    lines = [
        "# Stage088 jd margin source audit",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：只读数据源审计；不回测收益，不改策略，不连接 CTP，不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- DCE 鸡蛋合约公开页给出最低交易保证金为合约价值 5%。",
        "- DCE 同时说明交易所可根据市场情况调整各合约保证金；所以 5% 只是静态最低要求，不是 2020-2026 逐日合约保证金历史。",
        "- 我的判断：当前仓库没有 accepted `jd_contract_daily_margin_history`，Stage208 true ledger 仍禁止。",
        "",
        "## Candidate Audit",
        "",
        _md_table(candidate_audit, max_rows=80),
        "",
        "## TqSdk Daily JD Audit",
        "",
        _md_table(tqsdk_daily_audit, max_rows=120),
        "",
        "## 回测记录字段",
        "",
        "- 本阶段不新增回测，因此不新增期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率。",
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
        f"- candidate_audit：`{CANDIDATE_AUDIT_PATH}`",
        f"- tqsdk_daily_audit：`{TQSDK_DAILY_AUDIT_PATH}`",
        f"- input_audit：`{INPUT_AUDIT_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], candidate_audit: pd.DataFrame, tqsdk_daily_audit: pd.DataFrame) -> Path:
    stage_path = STAGES_DIR / f"{datetime.now():%Y%m%d_%H%M}_stage088_jd_margin_source_audit.md"
    lines = [
        "# Stage088 jd margin source audit",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{decision['generated_at']}",
        "- 阶段性质：只读数据源审计；不回测收益，不改官方 live config、不连接 CTP、不调用下单",
        "- 是否重要突破：否",
        "- 是否触发A/B：否",
        "",
        "## 外部调研与判断",
        "",
        "- DCE 鸡蛋合约公开页给出最低交易保证金 `5%`，并说明交易所可按市场情况调整交易保证金。",
        "- 我的判断：5% 静态最低保证金、当前 TqSdk metadata 快照、live/shadow margin usage 都不能替代 `2020-01-02` 到 `2026-06-30` 的 PIT 逐日/逐合约保证金历史。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage088_jd_margin_source_audit.py`",
        "- 新增参数：无交易参数。",
        "- 修改参数：无正式策略参数修改。",
        "- 删除参数：无。",
        "",
        "## 结果",
        "",
        f"- decision：`{decision['decision']}`",
        f"- candidate_count：`{decision['candidate_count']}`",
        f"- accepted_candidate_count：`{decision['accepted_candidate_count']}`",
        f"- tqsdk_daily_jd_file_count：`{decision['tqsdk_daily_jd_file_count']}`",
        f"- tqsdk_daily_has_margin_columns：`{decision['tqsdk_daily_has_margin_columns']}`",
        "- ready_for_true_ledger_replay：`False`",
        f"- remaining_blocker：`{decision['remaining_blocker']}`",
        "- 策略变更：`False`",
        "- true engine run：`False`",
        "- order API：`0`",
        "- CTP：`False`",
        "",
        "## Candidate Audit",
        "",
        _md_table(candidate_audit, max_rows=80),
        "",
        "## TqSdk Daily JD Audit",
        "",
        _md_table(tqsdk_daily_audit, max_rows=120),
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
        f"- candidate_audit：`{CANDIDATE_AUDIT_PATH}`",
        f"- tqsdk_daily_audit：`{TQSDK_DAILY_AUDIT_PATH}`",
        f"- input_audit：`{INPUT_AUDIT_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    stage_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return stage_path


def run() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    tqsdk_daily_audit = audit_tqsdk_daily_dir()
    candidate_audit = build_candidate_audit(tqsdk_daily_audit)
    input_audit = _input_audit(
        [
            STAGE049_SPEC_AUDIT,
            STAGE050_CONTRACT,
            TQSDK_METADATA,
            TQSDK_DAILY_DIR,
            STAGE901_PRODUCT_MARGIN,
            STAGE655_POSITIONS,
            PORTFOLIO_DIR / "qmt_universe.py",
        ]
    )
    decision = make_decision(candidate_audit, tqsdk_daily_audit)

    candidate_audit.to_csv(CANDIDATE_AUDIT_PATH, index=False, encoding="utf-8-sig")
    tqsdk_daily_audit.to_csv(TQSDK_DAILY_AUDIT_PATH, index=False, encoding="utf-8-sig")
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, candidate_audit, tqsdk_daily_audit)
    stage_path = _write_stage_record(decision, candidate_audit, tqsdk_daily_audit)
    decision["outputs"]["stage_record"] = str(stage_path)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"stage_record={stage_path}")
    return decision


if __name__ == "__main__":
    run()
