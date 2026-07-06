from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage079"
MODEL_TAG = "stage079_cash_source_status_gate_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage079_cash_source_status_gate"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage079_cash_source_status_gate"
STAGES_DIR = LINE_DIR / "stages"

TARGET_FUND_CODE = "000009"
TARGET_FUND_NAME = "易方达天天理财货币A"
RESERVE_CAPITAL = 150_000.0
MIN_INCEPTION_DATE = pd.Timestamp("2020-01-01")
MIN_CURRENT_7D_YIELD_PCT = 1.0

STATUS_SOURCES_PATH = OUT / f"{OUTPUT_PREFIX}_status_sources_{MODEL_TAG}.csv"
CANDIDATE_POOL_PATH = OUT / f"{OUTPUT_PREFIX}_current_money_fund_candidate_pool_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

URLS = {
    "eastmoney_fundf10": "https://fundf10.eastmoney.com/000009.html",
    "eastmoney_jjgg": "https://fundf10.eastmoney.com/jjgg_000009_5.html",
    "efunds_official": "https://www.efunds.com.cn/fund/000009.shtml",
}


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


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _parse_percent(value: Any) -> float:
    text = str(value).replace("%", "").replace("---", "").strip()
    try:
        return float(text)
    except Exception:  # noqa: BLE001
        return float("nan")


def _fetch_akshare_daily() -> tuple[pd.DataFrame, dict[str, Any]]:
    import akshare as ak

    raw = ak.fund_money_fund_daily_em()
    frame = raw.copy()
    frame["fund_code"] = frame["基金代码"].astype(str).str.zfill(6)
    yield_cols = sorted([c for c in frame.columns if str(c).endswith("7日年化%")])
    latest_yield_col = yield_cols[-1] if yield_cols else None
    target = frame[frame["fund_code"].eq(TARGET_FUND_CODE)].tail(1)
    if target.empty:
        raise RuntimeError(f"{TARGET_FUND_CODE} missing in fund_money_fund_daily_em")
    row = target.iloc[0]
    latest_yield = _parse_percent(row.get(latest_yield_col)) if latest_yield_col else float("nan")
    status = {
        "source_id": "akshare_fund_money_fund_daily_em",
        "source_url": "https://fund.eastmoney.com/HBJJ_pjsyl.html",
        "fund_code": TARGET_FUND_CODE,
        "fund_name": str(row.get("基金简称", "")),
        "asof_hint": str(latest_yield_col).split("-7日年化%")[0] if latest_yield_col else "",
        "purchase_status_raw": str(row.get("可购全部", "")),
        "redeem_status_raw": "",
        "current_7d_yield_pct": latest_yield,
        "fee_raw": str(row.get("手续费", "")),
        "inception_date": str(row.get("成立日期", "")),
        "open_purchase_flag": str(row.get("可购全部", "")) == "购买",
        "open_redeem_flag": None,
        "limit_large_flag": False,
        "limit_amount_yuan": np.nan,
        "source_confidence": "medium",
        "notes": "Current Eastmoney money-fund table via AKShare; not a direct broker order check.",
    }
    return frame, status


def _fetch_akshare_info_tail() -> dict[str, Any]:
    import akshare as ak

    raw = ak.fund_money_fund_info_em(symbol=TARGET_FUND_CODE)
    frame = raw.rename(
        columns={"净值日期": "date", "每万份收益": "income_per_10k", "7日年化收益率": "annualized_rate_pct"}
    ).copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"]).sort_values("date")
    row = frame.tail(1).iloc[0]
    purchase_raw = str(row.get("申购状态", ""))
    redeem_raw = str(row.get("赎回状态", ""))
    return {
        "source_id": "akshare_fund_money_fund_info_em_tail",
        "source_url": "https://fundf10.eastmoney.com/jjjz_000009.html",
        "fund_code": TARGET_FUND_CODE,
        "fund_name": TARGET_FUND_NAME,
        "asof_hint": pd.Timestamp(row["date"]).date().isoformat(),
        "purchase_status_raw": purchase_raw,
        "redeem_status_raw": redeem_raw,
        "current_7d_yield_pct": float(pd.to_numeric(row.get("annualized_rate_pct"), errors="coerce")),
        "fee_raw": "",
        "inception_date": "",
        "open_purchase_flag": "开放申购" in purchase_raw or "购买" in purchase_raw,
        "open_redeem_flag": "开放赎回" in redeem_raw,
        "limit_large_flag": "限" in purchase_raw,
        "limit_amount_yuan": np.nan,
        "source_confidence": "medium_low",
        "notes": "Historical yield table status can lag or disagree with current fund pages.",
    }


def _extract_eastmoney_status(html: str) -> tuple[str, str, float, str]:
    around = ""
    purchase = ""
    redeem = ""
    m = re.search(r"交易状态：(.{0,260})", html, flags=re.S)
    if m:
        around = _clean_text(re.sub(r"<[^>]+>", " ", m.group(0)))
        if "开放申购" in around:
            purchase = "开放申购"
        elif "限大额" in around:
            purchase = around
        elif "暂停申购" in around:
            purchase = "暂停申购"
        if "开放赎回" in around:
            redeem = "开放赎回"
        elif "暂停赎回" in around:
            redeem = "暂停赎回"
    limit_amount = np.nan
    limit_match = re.search(r"上限\s*([0-9.]+)\s*万", around)
    if limit_match:
        limit_amount = float(limit_match.group(1)) * 10_000.0
    return purchase, redeem, limit_amount, around[:500]


def _fetch_html_source(source_id: str, url: str) -> dict[str, Any]:
    response = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    html = response.text
    purchase = ""
    redeem = ""
    limit_amount = np.nan
    snippet = ""
    if "eastmoney" in url:
        purchase, redeem, limit_amount, snippet = _extract_eastmoney_status(html)
    else:
        buy_button = "buy-btn" in html or re.search(r">\s*购买\s*<", html) is not None
        purchase = "购买入口可见" if buy_button else ""
        redeem = ""
        status_positions = []
        for pattern in ("暂停申购", "开放申购", "限大额", "开放赎回", "购买"):
            match = re.search(pattern, html)
            if match:
                status_positions.append((match.start(), pattern))
        if status_positions:
            pos, pattern = sorted(status_positions)[0]
            snippet = _clean_text(re.sub(r"<[^>]+>", " ", html[max(0, pos - 160) : pos + 260]))
    limit_large = "限大额" in purchase or "限制大额" in purchase or ("限大额" in snippet)
    open_purchase = ("开放申购" in purchase) or ("购买入口可见" in purchase) or (
        limit_large and (not np.isfinite(limit_amount) or limit_amount >= RESERVE_CAPITAL)
    )
    open_redeem = ("开放赎回" in redeem) if redeem else None
    return {
        "source_id": source_id,
        "source_url": url,
        "fund_code": TARGET_FUND_CODE,
        "fund_name": TARGET_FUND_NAME,
        "asof_hint": datetime.now().strftime("%Y-%m-%d"),
        "purchase_status_raw": purchase,
        "redeem_status_raw": redeem,
        "current_7d_yield_pct": np.nan,
        "fee_raw": "0.00%" if "0.00" in html and "费" in html else "",
        "inception_date": "2013-03-04" if "2013-03-04" in html else "",
        "open_purchase_flag": bool(open_purchase),
        "open_redeem_flag": open_redeem,
        "limit_large_flag": bool(limit_large),
        "limit_amount_yuan": limit_amount,
        "source_confidence": "medium_high" if "eastmoney" in url else "medium",
        "notes": snippet,
    }


def _current_candidate_pool(daily: pd.DataFrame) -> pd.DataFrame:
    frame = daily.copy()
    yield_cols = sorted([c for c in frame.columns if str(c).endswith("7日年化%")])
    latest_yield_col = yield_cols[-1]
    frame["inception_ts"] = pd.to_datetime(frame.get("成立日期"), errors="coerce")
    frame["latest_7d_yield_pct"] = frame[latest_yield_col].map(_parse_percent)
    pool = frame[
        frame["fund_code"].astype(str).str.match(r"^\d{6}$", na=False)
        & frame["inception_ts"].le(MIN_INCEPTION_DATE)
        & frame["latest_7d_yield_pct"].ge(MIN_CURRENT_7D_YIELD_PCT)
        & frame.get("手续费").astype(str).eq("0费率")
        & frame.get("可购全部").astype(str).eq("购买")
    ].copy()
    result = pd.DataFrame(
        {
            "fund_code": pool["fund_code"].astype(str).str.zfill(6),
            "fund_name": pool.get("基金简称").astype(str),
            "inception_date": pool["inception_ts"].dt.date.astype(str),
            "latest_7d_yield_pct": pool["latest_7d_yield_pct"],
            "fee_raw": pool.get("手续费").astype(str),
            "purchase_raw": pool.get("可购全部").astype(str),
            "latest_yield_column": latest_yield_col,
        }
    )
    return result.sort_values(["inception_date", "fund_code"]).reset_index(drop=True)


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    daily, daily_status = _fetch_akshare_daily()
    statuses = [daily_status, _fetch_akshare_info_tail()]
    for source_id, url in URLS.items():
        try:
            statuses.append(_fetch_html_source(source_id, url))
        except Exception as exc:  # noqa: BLE001
            statuses.append(
                {
                    "source_id": source_id,
                    "source_url": url,
                    "fund_code": TARGET_FUND_CODE,
                    "fund_name": TARGET_FUND_NAME,
                    "asof_hint": datetime.now().strftime("%Y-%m-%d"),
                    "purchase_status_raw": "",
                    "redeem_status_raw": "",
                    "current_7d_yield_pct": np.nan,
                    "fee_raw": "",
                    "inception_date": "",
                    "open_purchase_flag": False,
                    "open_redeem_flag": False,
                    "limit_large_flag": False,
                    "limit_amount_yuan": np.nan,
                    "source_confidence": "failed",
                    "notes": f"{type(exc).__name__}: {exc}",
                }
            )

    status_df = pd.DataFrame(statuses)
    status_df.to_csv(STATUS_SOURCES_PATH, index=False)
    candidate_pool = _current_candidate_pool(daily)
    candidate_pool.to_csv(CANDIDATE_POOL_PATH, index=False)

    positive_sources = status_df[status_df["open_purchase_flag"].fillna(False).astype(bool)]
    negative_sources = status_df[
        status_df["purchase_status_raw"].astype(str).str.contains("暂停申购|暂停购买", regex=True, na=False)
    ]
    redeem_false = status_df[status_df["open_redeem_flag"].fillna(True).eq(False)]
    has_conflict = not negative_sources.empty and not positive_sources.empty
    open_source_count = int(len(positive_sources))
    high_conf_open_count = int(
        positive_sources["source_confidence"].astype(str).isin(["medium_high", "medium"]).sum()
    )
    eastmoney_open = bool(
        status_df[
            status_df["source_id"].astype(str).str.startswith("eastmoney")
            & status_df["open_purchase_flag"].fillna(False).astype(bool)
        ].shape[0]
    )
    daily_open = bool(
        status_df[
            status_df["source_id"].eq("akshare_fund_money_fund_daily_em")
            & status_df["open_purchase_flag"].fillna(False).astype(bool)
        ].shape[0]
    )
    can_accept = (
        not has_conflict
        and redeem_false.empty
        and open_source_count >= 2
        and high_conf_open_count >= 2
        and eastmoney_open
        and daily_open
    )
    decision_name = (
        "stage079_cash_source_status_accepted_for_replay"
        if can_accept
        else "stage079_cash_source_status_conflict_needs_channel_confirmation"
    )
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision_name,
        "target_fund_code": TARGET_FUND_CODE,
        "target_fund_name": TARGET_FUND_NAME,
        "open_source_count": open_source_count,
        "negative_source_count": int(len(negative_sources)),
        "has_status_conflict": bool(has_conflict),
        "current_candidate_pool_count": int(len(candidate_pool)),
        "status_sources_path": str(STATUS_SOURCES_PATH),
        "candidate_pool_path": str(CANDIDATE_POOL_PATH),
        "created_at": datetime.now().replace(microsecond=0).isoformat(),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(status_df, candidate_pool, decision)
    _write_stage_record(status_df, candidate_pool, decision)
    return decision


def _write_report(status_df: pd.DataFrame, candidate_pool: pd.DataFrame, decision: dict[str, Any]) -> None:
    status_cols = [
        "source_id",
        "asof_hint",
        "purchase_status_raw",
        "redeem_status_raw",
        "open_purchase_flag",
        "open_redeem_flag",
        "limit_large_flag",
        "limit_amount_yuan",
        "current_7d_yield_pct",
        "fee_raw",
        "source_confidence",
        "notes",
        "source_url",
    ]
    text = f"""# Stage079 cash source status gate

## 结论

- 决策：`{decision['decision']}`。
- 目标现金源：`{TARGET_FUND_CODE}` `{TARGET_FUND_NAME}`。
- 当前 open source count：`{decision['open_source_count']}`；negative source count：`{decision['negative_source_count']}`；status conflict：`{decision['has_status_conflict']}`。
- 当前全市场初筛候选池：`{decision['current_candidate_pool_count']}` 只货币基金，条件为成立早于 2020、0费率、当前可购、最新 7日年化不低于 1%。

## Status Sources

{_md_table(status_df[status_cols])}

## Candidate Pool Sample

{_md_table(candidate_pool.head(80))}

## 输出

- status_sources: `{STATUS_SOURCES_PATH}`
- candidate_pool: `{CANDIDATE_POOL_PATH}`
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def _write_stage_record(status_df: pd.DataFrame, candidate_pool: pd.DataFrame, decision: dict[str, Any]) -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = STAGES_DIR / f"{stamp}_stage079_cash_source_status_gate.md"
    status_cols = [
        "source_id",
        "asof_hint",
        "purchase_status_raw",
        "redeem_status_raw",
        "open_purchase_flag",
        "open_redeem_flag",
        "limit_large_flag",
        "limit_amount_yuan",
        "current_7d_yield_pct",
        "fee_raw",
        "source_confidence",
        "source_url",
    ]
    text = f"""# Stage079 cash source status gate

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{datetime.now().replace(microsecond=0).isoformat()}
- 阶段性质：现金收益源当前状态/限额只读验收
- 是否重要突破：{'是，000009 当前状态通过多源验收' if decision['decision'] == 'stage079_cash_source_status_accepted_for_replay' else '否，000009 状态仍需交易渠道确认'}

## 外部调研与判断

- 货币基金可以作为账户层现金收益源候选，但必须通过当前可申购、可赎回、额度足够、历史收益可重放和真实账户可买的验收。
- 本阶段不把单一基金历史收益当 alpha，不改 C9，不连接 CTP，不触发订单。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage079_cash_source_status_gate.py`
- 新增参数：`TARGET_FUND_CODE={TARGET_FUND_CODE}`、`RESERVE_CAPITAL={RESERVE_CAPITAL}`、`MIN_CURRENT_7D_YIELD_PCT={MIN_CURRENT_7D_YIELD_PCT}`。
- 修改参数：无正式交易参数。
- 删除参数：无。

## Status Sources

{_md_table(status_df[status_cols])}

## 当前候选池

- 初筛候选数：`{len(candidate_pool)}`
- 条件：成立早于 `2020-01-01`、0费率、当前可购、最新 7日年化不低于 `1%`。
- 样例：

{_md_table(candidate_pool.head(30))}

## 结论

- 决策：`{decision['decision']}`。
- 回测指标：本阶段不回测，不新增订单，因此无期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数或胜率。
- 运行前过拟合反思：否。验收当前状态和限额是 Stage078 的必要外部状态确认，不按历史坏窗口挑收益率。
- 运行后过拟合反思：否。状态源冲突时不直接 accepted；后续若按当前最高收益率挑单只基金，就是过拟合/选择偏差。
- 继续价值：有。下一步应固定非收益排序的候选篮子或确认真实交易渠道，再做历史收益回放。

## 输出文件

- report：`{REPORT_PATH}`
- decision：`{DECISION_PATH}`
- status_sources：`{STATUS_SOURCES_PATH}`
- candidate_pool：`{CANDIDATE_POOL_PATH}`
"""
    path.write_text(text, encoding="utf-8")


def main() -> None:
    decision = build()
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
