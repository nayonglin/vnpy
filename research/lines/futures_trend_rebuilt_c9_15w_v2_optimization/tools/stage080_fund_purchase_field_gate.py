from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage080"
MODEL_TAG = "stage080_fund_purchase_field_gate_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage080_fund_purchase_field_gate"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage080_fund_purchase_field_gate"
STAGES_DIR = LINE_DIR / "stages"

STAGE079_POOL_PATH = (
    LINE_DIR
    / "outputs"
    / "stage079_cash_source_status_gate"
    / "rebuilt_c9_v2_stage079_cash_source_status_gate_current_money_fund_candidate_pool_stage079_cash_source_status_gate_v1.csv"
)

TARGET_FUND_CODE = "000009"
TARGET_FUND_NAME = "易方达天天理财货币A"
RESERVE_CAPITAL = 150_000.0

PURCHASE_RAW_PATH = OUT / f"{OUTPUT_PREFIX}_fund_purchase_raw_{MODEL_TAG}.csv"
CANDIDATE_GATE_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_purchase_gate_{MODEL_TAG}.csv"
TARGET_GATE_PATH = OUT / f"{OUTPUT_PREFIX}_target_purchase_gate_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _read_stage079_pool() -> pd.DataFrame:
    pool = pd.read_csv(STAGE079_POOL_PATH, dtype={"fund_code": str})
    pool["fund_code"] = pool["fund_code"].astype(str).str.zfill(6)
    pool["latest_7d_yield_pct"] = pd.to_numeric(pool["latest_7d_yield_pct"], errors="coerce")
    return pool


def _fetch_purchase() -> pd.DataFrame:
    import akshare as ak

    raw = ak.fund_purchase_em()
    raw = raw.copy()
    raw["fund_code"] = raw["基金代码"].astype(str).str.zfill(6)
    raw["fund_name_purchase"] = raw["基金简称"].astype(str)
    raw["fund_type"] = raw["基金类型"].astype(str)
    raw["purchase_status"] = raw["申购状态"].astype(str)
    raw["redeem_status"] = raw["赎回状态"].astype(str)
    raw["purchase_min_yuan"] = pd.to_numeric(raw["购买起点"], errors="coerce")
    raw["daily_limit_yuan"] = pd.to_numeric(raw["日累计限定金额"], errors="coerce")
    raw["fee_pct"] = pd.to_numeric(raw["手续费"], errors="coerce")
    raw["nav_or_income"] = pd.to_numeric(raw["最新净值/万份收益"], errors="coerce")
    raw["nav_report_time"] = raw["最新净值/万份收益-报告时间"].astype(str)
    keep = [
        "fund_code",
        "fund_name_purchase",
        "fund_type",
        "nav_or_income",
        "nav_report_time",
        "purchase_status",
        "redeem_status",
        "下一开放日",
        "purchase_min_yuan",
        "daily_limit_yuan",
        "fee_pct",
    ]
    return raw[keep].copy()


def _eligible_flags(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    purchase_status = data["purchase_status"].fillna("").astype(str)
    data["is_money_fund"] = data["fund_type"].fillna("").astype(str).str.contains("货币")
    data["purchase_open_or_capacity_ok"] = purchase_status.str.contains("开放申购", regex=False) | (
        purchase_status.str.contains("限大额", regex=False)
        & pd.to_numeric(data["daily_limit_yuan"], errors="coerce").ge(RESERVE_CAPITAL)
    )
    data["redeem_open"] = data["redeem_status"].fillna("").astype(str).str.contains("开放赎回", regex=False)
    data["min_purchase_ok"] = pd.to_numeric(data["purchase_min_yuan"], errors="coerce").le(RESERVE_CAPITAL)
    data["daily_limit_ok"] = pd.to_numeric(data["daily_limit_yuan"], errors="coerce").ge(RESERVE_CAPITAL)
    data["fee_ok"] = pd.to_numeric(data["fee_pct"], errors="coerce").fillna(999.0).le(0.0)
    data["public_platform_purchase_field_eligible"] = (
        data["is_money_fund"]
        & data["purchase_open_or_capacity_ok"]
        & data["redeem_open"]
        & data["min_purchase_ok"]
        & data["daily_limit_ok"]
        & data["fee_ok"]
    )
    data["eligibility_note"] = np.where(
        data["public_platform_purchase_field_eligible"],
        "purchase fields pass on public Eastmoney/Tiantian source; user trading channel still must confirm",
        "purchase fields not fully eligible",
    )
    return data


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    pool = _read_stage079_pool()
    purchase = _fetch_purchase()
    purchase.to_csv(PURCHASE_RAW_PATH, index=False)

    merged = pool.merge(purchase, on="fund_code", how="left")
    gated = _eligible_flags(merged)
    target = _eligible_flags(purchase[purchase["fund_code"].eq(TARGET_FUND_CODE)].copy())

    eligible = gated[gated["public_platform_purchase_field_eligible"].astype(bool)].copy()
    non_yield_ranked_basket = eligible.sort_values(["inception_date", "fund_code"]).head(12).copy()
    target.to_csv(TARGET_GATE_PATH, index=False)
    gated.to_csv(CANDIDATE_GATE_PATH, index=False)

    target_eligible = bool(target["public_platform_purchase_field_eligible"].any())
    if target_eligible:
        decision_name = "stage080_target_purchase_fields_confirmed_public_platform"
    elif not eligible.empty:
        decision_name = "stage080_candidate_purchase_fields_ready_target_unconfirmed"
    else:
        decision_name = "stage080_no_purchase_field_eligible_cash_source"
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision_name,
        "target_fund_code": TARGET_FUND_CODE,
        "target_public_platform_eligible": target_eligible,
        "stage079_candidate_count": int(len(pool)),
        "purchase_joined_count": int(gated["fund_name_purchase"].notna().sum()),
        "purchase_field_eligible_count": int(len(eligible)),
        "non_yield_ranked_basket_count": int(len(non_yield_ranked_basket)),
        "target_gate_path": str(TARGET_GATE_PATH),
        "candidate_gate_path": str(CANDIDATE_GATE_PATH),
        "created_at": datetime.now().replace(microsecond=0).isoformat(),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(target, gated, non_yield_ranked_basket, decision)
    _write_stage_record(target, gated, non_yield_ranked_basket, decision)
    return decision


def _write_report(
    target: pd.DataFrame,
    gated: pd.DataFrame,
    basket: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    target_cols = [
        "fund_code",
        "fund_name_purchase",
        "fund_type",
        "purchase_status",
        "redeem_status",
        "purchase_min_yuan",
        "daily_limit_yuan",
        "fee_pct",
        "public_platform_purchase_field_eligible",
        "eligibility_note",
    ]
    basket_cols = [
        "fund_code",
        "fund_name",
        "inception_date",
        "latest_7d_yield_pct",
        "purchase_status",
        "redeem_status",
        "purchase_min_yuan",
        "daily_limit_yuan",
        "fee_pct",
        "public_platform_purchase_field_eligible",
    ]
    summary = pd.DataFrame(
        [
            {
                "metric": "stage079_candidate_count",
                "value": decision["stage079_candidate_count"],
            },
            {
                "metric": "purchase_joined_count",
                "value": decision["purchase_joined_count"],
            },
            {
                "metric": "purchase_field_eligible_count",
                "value": decision["purchase_field_eligible_count"],
            },
            {
                "metric": "target_public_platform_eligible",
                "value": decision["target_public_platform_eligible"],
            },
        ]
    )
    text = f"""# Stage080 fund purchase field gate

## 结论

- 决策：`{decision['decision']}`。
- `fund_purchase_em` 显示目标 `{TARGET_FUND_CODE}` `{TARGET_FUND_NAME}` 在公开东方财富/天天基金申购状态字段上通过：`{decision['target_public_platform_eligible']}`。
- 这仍不是用户真实交易渠道确认；上线前还需要用户实际账户/券商/银行渠道确认。

## Summary

{_md_table(summary)}

## Target

{_md_table(target[target_cols])}

## Non-yield-ranked Basket Sample

{_md_table(basket[basket_cols])}

## 输出

- target_gate: `{TARGET_GATE_PATH}`
- candidate_gate: `{CANDIDATE_GATE_PATH}`
- purchase_raw: `{PURCHASE_RAW_PATH}`
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def _write_stage_record(
    target: pd.DataFrame,
    gated: pd.DataFrame,
    basket: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = STAGES_DIR / f"{stamp}_stage080_fund_purchase_field_gate.md"
    target_cols = [
        "fund_code",
        "fund_name_purchase",
        "fund_type",
        "purchase_status",
        "redeem_status",
        "purchase_min_yuan",
        "daily_limit_yuan",
        "fee_pct",
        "public_platform_purchase_field_eligible",
    ]
    basket_cols = [
        "fund_code",
        "fund_name",
        "inception_date",
        "latest_7d_yield_pct",
        "purchase_status",
        "redeem_status",
        "purchase_min_yuan",
        "daily_limit_yuan",
        "fee_pct",
    ]
    text = f"""# Stage080 fund purchase field gate

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{datetime.now().replace(microsecond=0).isoformat()}
- 阶段性质：公开销售平台申赎/限额字段验收
- 是否重要突破：{'否，公开平台通过但仍需用户真实交易渠道确认' if decision['target_public_platform_eligible'] else '否，目标现金源公开平台字段未通过'}

## 外部调研与判断

- `fund_purchase_em` 是东方财富/天天基金“基金申购状态”字段，比 Stage079 的网页文本和历史净值状态更适合做当前申赎/限额验收。
- 但公开销售平台字段仍不是用户真实账户可买证明，不能直接接入实盘默认路径。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage080_fund_purchase_field_gate.py`
- 新增参数：`RESERVE_CAPITAL={RESERVE_CAPITAL}`、目标基金 `{TARGET_FUND_CODE}`。
- 修改参数：无正式交易参数。
- 删除参数：无。

## Target

{_md_table(target[target_cols])}

## 结果

- Stage079 初筛候选数：`{decision['stage079_candidate_count']}`
- 成功 join `fund_purchase_em`：`{decision['purchase_joined_count']}`
- 公开平台字段通过候选数：`{decision['purchase_field_eligible_count']}`
- 非收益排序篮子样例：按成立日期、基金代码排序取前 `12` 只，不按收益率排序。

{_md_table(basket[basket_cols])}

## 结论

- 决策：`{decision['decision']}`。
- 回测指标：本阶段不回测，不新增订单，因此无期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数或胜率。
- 运行前过拟合反思：否。补申赎/限额字段是可实现性验收，不按历史收益挑选。
- 运行后过拟合反思：否。公开平台通过仍不直接上线，下一步若做历史回放也应使用非收益排序或固定规则篮子。
- 继续价值：有。下一步可对固定篮子做历史每万份收益回放，或先让用户确认真实交易渠道。

## 输出文件

- report：`{REPORT_PATH}`
- decision：`{DECISION_PATH}`
- target_gate：`{TARGET_GATE_PATH}`
- candidate_gate：`{CANDIDATE_GATE_PATH}`
"""
    path.write_text(text, encoding="utf-8")


def main() -> None:
    decision = build()
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
