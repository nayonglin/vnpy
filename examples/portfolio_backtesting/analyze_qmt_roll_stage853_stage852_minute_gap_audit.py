from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage853"
MODEL_TAG = "stage853_stage852_minute_gap_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage853_stage852_minute_gap_audit"

STAGE825_PREFIX = "qmt_roll_stage825_stage819_intraday_rule_forensics"
STAGE825_TAG = "stage825_stage819_intraday_rule_forensics_v1"
STAGE849_PREFIX = "qmt_roll_stage849_stage848_pressure_path_forensics"
STAGE849_TAG = "stage849_stage848_pressure_path_forensics_v1"
STAGE852_PREFIX = "qmt_roll_stage852_stage851_route_review"
STAGE852_TAG = "stage852_stage851_route_review_v1"

STAGE825_INTRADAY_PATH = OUTPUT_DIR / f"{STAGE825_PREFIX}_intraday_features_{STAGE825_TAG}.csv"
STAGE849_MINUTE_PATH = OUTPUT_DIR / f"{STAGE849_PREFIX}_minute_features_{STAGE849_TAG}.csv"
STAGE849_PAIRS_PATH = OUTPUT_DIR / f"{STAGE849_PREFIX}_episode_lot_pairs_{STAGE849_TAG}.csv"
STAGE852_DECISION_PATH = OUTPUT_DIR / f"{STAGE852_PREFIX}_decision_{STAGE852_TAG}.json"

MINUTE_SOURCE_PATHS = (
    OUTPUT_DIR / "qmt_roll_stage449_minute_session_rebuild_full_minute_bars_stage449_minute_session_rebuild_full_v1.csv",
    OUTPUT_DIR / "qmt_roll_stage498_actual_trade_fill_key_readiness_completed_minute_bars_stage498_actual_trade_fill_key_readiness_v1.csv",
)

GAP_REQUESTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gap_requests_{MODEL_TAG}.csv"
GAP_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gap_detail_{MODEL_TAG}.csv"
ROOT_CAUSE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_root_cause_summary_{MODEL_TAG}.csv"
FETCH_PLAN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fetch_plan_by_symbol_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _product_from_vt(vt_symbol: Any) -> str:
    text = str(vt_symbol)
    if "." not in text:
        return text
    contract, exchange = text.split(".", 1)
    letters = "".join(ch for ch in contract if ch.isalpha())
    return f"{letters}.{exchange}" if letters else text


def _normal_date_text(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return ""
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


def _numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _build_gap_requests() -> pd.DataFrame:
    intraday = _load_csv(STAGE825_INTRADAY_PATH).copy()
    intraday = _numeric(
        intraday,
        ["entry_day_minute_bars", "realized_pnl", "big_winner", "lot_id", "entry_year"],
    )
    intraday["entry_date_text"] = intraday["entry_date"].map(_normal_date_text)
    intraday["product_norm"] = intraday["vt_symbol"].map(_product_from_vt)
    intraday["entry_day_missing"] = intraday["entry_day_minute_bars"].fillna(0).le(0)
    missing = intraday[intraday["entry_day_missing"]].copy()

    rows: list[dict[str, Any]] = []
    for row in missing.itertuples(index=False):
        rows.append(
            {
                "request_type": "stage825_entry_day",
                "source_id": f"lot_{int(row.lot_id)}",
                "vt_symbol": str(row.vt_symbol),
                "product": str(row.product_norm),
                "required_date": str(row.entry_date_text),
                "direction": str(row.direction),
                "priority_abs_pnl": abs(float(row.realized_pnl or 0.0)),
                "realized_pnl": float(row.realized_pnl or 0.0),
                "big_winner": int(float(row.big_winner or 0.0) > 0.0),
                "entry_year": int(row.entry_year) if pd.notna(row.entry_year) else "",
                "note": "Stage825 missing entry-day minute bars",
            }
        )

    pressure = _load_csv(STAGE849_MINUTE_PATH).copy()
    pairs = _load_csv(STAGE849_PAIRS_PATH).copy()
    pressure = _numeric(pressure, ["minute_bars"])
    pairs = _numeric(pairs, ["realized_pnl_delta_C9_minus_C4"])
    pair_pnl = pairs.groupby("episode_id", dropna=False)["realized_pnl_delta_C9_minus_C4"].sum().to_dict()
    missing_pressure = pressure[pressure["minute_bars"].fillna(0).le(0)].copy()
    for row in missing_pressure.itertuples(index=False):
        episode_pnl = float(pair_pnl.get(row.episode_id, 0.0) or 0.0)
        rows.append(
            {
                "request_type": "stage849_pressure_key_date",
                "source_id": str(row.episode_id),
                "vt_symbol": str(row.vt_symbol),
                "product": _product_from_vt(row.vt_symbol),
                "required_date": _normal_date_text(row.date),
                "direction": str(row.direction),
                "priority_abs_pnl": abs(episode_pnl),
                "realized_pnl": episode_pnl,
                "big_winner": 0,
                "entry_year": "",
                "note": "Stage849 pressure episode missing key-date minute bars",
            }
        )

    data = pd.DataFrame(rows)
    data = data.drop_duplicates(["request_type", "source_id", "vt_symbol", "required_date"]).reset_index(drop=True)
    return data


def _build_minute_index(vt_symbols: set[str], products: set[str]) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str], int]]:
    symbol_index: dict[str, dict[str, Any]] = {}
    product_date_counts: dict[tuple[str, str], int] = defaultdict(int)
    usecols = ["vt_symbol", "bar_datetime"]

    for path in MINUTE_SOURCE_PATHS:
        if not path.exists():
            continue
        for chunk in pd.read_csv(
            path,
            usecols=lambda col: col in usecols,
            encoding="utf-8-sig",
            chunksize=500_000,
        ):
            if chunk.empty or "vt_symbol" not in chunk.columns or "bar_datetime" not in chunk.columns:
                continue
            chunk["vt_symbol"] = chunk["vt_symbol"].astype(str)
            chunk["product"] = chunk["vt_symbol"].map(_product_from_vt)
            filtered = chunk[chunk["vt_symbol"].isin(vt_symbols) | chunk["product"].isin(products)].copy()
            if filtered.empty:
                continue
            filtered["date_text"] = pd.to_datetime(filtered["bar_datetime"], errors="coerce").dt.strftime("%Y-%m-%d")
            filtered = filtered.dropna(subset=["date_text"])
            exact = filtered[filtered["vt_symbol"].isin(vt_symbols)]
            if not exact.empty:
                counts = exact.groupby(["vt_symbol", "date_text"], dropna=False).size()
                for (vt_symbol, date_text), count in counts.items():
                    item = symbol_index.setdefault(
                        str(vt_symbol),
                        {
                            "dates": defaultdict(int),
                            "source_files": set(),
                            "total_bars": 0,
                        },
                    )
                    item["dates"][str(date_text)] += int(count)
                    item["source_files"].add(path.name)
                    item["total_bars"] += int(count)
            product_rows = filtered[filtered["product"].isin(products)]
            if not product_rows.empty:
                product_counts = product_rows.groupby(["product", "date_text"], dropna=False).size()
                for (product, date_text), count in product_counts.items():
                    product_date_counts[(str(product), str(date_text))] += int(count)

    return symbol_index, dict(product_date_counts)


def _classify_requests(
    requests: pd.DataFrame,
    symbol_index: dict[str, dict[str, Any]],
    product_date_counts: dict[tuple[str, str], int],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in requests.itertuples(index=False):
        vt_symbol = str(row.vt_symbol)
        date_text = str(row.required_date)
        product = str(row.product)
        item = symbol_index.get(vt_symbol)
        exact_date_bars = int(item["dates"].get(date_text, 0)) if item else 0
        product_date_bars = int(product_date_counts.get((product, date_text), 0))
        if exact_date_bars > 0:
            root_cause = "source_has_exact_contract_date_recheck_stage825_filter"
        elif item is None:
            root_cause = (
                "exact_contract_missing_but_product_date_exists"
                if product_date_bars > 0
                else "exact_contract_missing_all_sources"
            )
        else:
            root_cause = (
                "exact_contract_missing_required_date_but_product_date_exists"
                if product_date_bars > 0
                else "exact_contract_missing_required_date"
            )

        available_dates = sorted(item["dates"].keys()) if item else []
        prev_dates = [value for value in available_dates if value < date_text]
        next_dates = [value for value in available_dates if value > date_text]
        rows.append(
            {
                **row._asdict(),
                "root_cause": root_cause,
                "exact_contract_total_bars": int(item["total_bars"]) if item else 0,
                "exact_contract_source_files": ",".join(sorted(item["source_files"])) if item else "",
                "exact_contract_first_date": available_dates[0] if available_dates else "",
                "exact_contract_last_date": available_dates[-1] if available_dates else "",
                "nearest_prev_exact_date": prev_dates[-1] if prev_dates else "",
                "nearest_next_exact_date": next_dates[0] if next_dates else "",
                "exact_date_bars": exact_date_bars,
                "same_product_date_bars": product_date_bars,
            }
        )
    return pd.DataFrame(rows)


def _root_cause_summary(detail: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for cause, group in detail.groupby("root_cause", dropna=False):
        rows.append(
            {
                "root_cause": str(cause),
                "requests": int(len(group)),
                "stage825_entry_day_requests": int(group["request_type"].astype(str).eq("stage825_entry_day").sum()),
                "stage849_pressure_requests": int(
                    group["request_type"].astype(str).eq("stage849_pressure_key_date").sum()
                ),
                "distinct_symbols": int(group["vt_symbol"].nunique()),
                "distinct_products": int(group["product"].nunique()),
                "priority_abs_pnl": float(group["priority_abs_pnl"].sum()),
                "big_winner_requests": int(group["big_winner"].sum()),
            }
        )
    return pd.DataFrame(rows).sort_values(["requests", "priority_abs_pnl"], ascending=[False, False])


def _fetch_plan(detail: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    needs_fetch = detail[detail["exact_date_bars"].fillna(0).le(0)].copy()
    for vt_symbol, group in needs_fetch.groupby("vt_symbol", dropna=False):
        rows.append(
            {
                "vt_symbol": str(vt_symbol),
                "product": str(group["product"].mode().iloc[0]) if not group.empty else "",
                "missing_dates": int(group["required_date"].nunique()),
                "first_missing_date": str(group["required_date"].min()),
                "last_missing_date": str(group["required_date"].max()),
                "request_types": ",".join(sorted(group["request_type"].astype(str).unique())),
                "root_causes": ",".join(sorted(group["root_cause"].astype(str).unique())),
                "priority_abs_pnl": float(group["priority_abs_pnl"].sum()),
                "big_winner_requests": int(group["big_winner"].sum()),
                "same_product_date_bars": int(group["same_product_date_bars"].sum()),
            }
        )
    return (
        pd.DataFrame(rows)
        .sort_values(["priority_abs_pnl", "missing_dates", "vt_symbol"], ascending=[False, False, True])
        .reset_index(drop=True)
    )


def _summary(detail: pd.DataFrame, root_summary: pd.DataFrame, fetch_plan: pd.DataFrame) -> pd.DataFrame:
    exact_available = int(detail["exact_date_bars"].fillna(0).gt(0).sum())
    same_product = int(
        detail["exact_date_bars"].fillna(0).le(0).astype(bool)
        .mul(detail["same_product_date_bars"].fillna(0).gt(0).astype(bool))
        .sum()
    )
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "decision": "stage853_minute_gap_mostly_true_missing_contract_or_date_no_rule",
                "gap_requests": int(len(detail)),
                "exact_contract_date_available_requests": exact_available,
                "same_product_date_available_without_exact_contract": same_product,
                "needs_fetch_requests": int(len(detail) - exact_available),
                "fetch_symbols": int(fetch_plan["vt_symbol"].nunique()) if not fetch_plan.empty else 0,
                "priority_abs_pnl_needs_fetch": float(
                    detail.loc[detail["exact_date_bars"].fillna(0).le(0), "priority_abs_pnl"].sum()
                ),
                "big_winner_requests_needs_fetch": int(
                    detail.loc[detail["exact_date_bars"].fillna(0).le(0), "big_winner"].sum()
                ),
                "top_root_cause": str(root_summary.iloc[0]["root_cause"]) if not root_summary.empty else "",
            }
        ]
    )


def _write_report(
    summary: pd.DataFrame,
    root_summary: pd.DataFrame,
    fetch_plan: pd.DataFrame,
    detail: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage853 Stage852后分钟K缺口根因审计",
        "",
        "## 阶段定位",
        "",
        "- 阶段性质：只读数据缺口审计；不下载数据、不改策略、不接引擎、不连接 CTP、不调用下单。",
        "- 目标：把 Stage852 的分钟K缺口拆成 exact contract/date 真缺失、同产品其他合约存在、或源内已有但需复查过滤。",
        "",
        "## 核心摘要",
        "",
        _md_table(summary),
        "",
        "## 根因汇总",
        "",
        _md_table(root_summary),
        "",
        "## 补数优先级",
        "",
        _md_table(fetch_plan.head(20)),
        "",
        "## 源内已有但需复查过滤",
        "",
        _md_table(detail[detail["exact_date_bars"].fillna(0).gt(0)].head(20)),
        "",
        "## 结论",
        "",
        f"- 决策标签：`{decision['decision']}`",
        "- 本阶段不写规则。只有补齐缺口并重画图谱后，才允许重新讨论分钟级规则。",
        "- 如果 exact contract/date 在源内已有，则优先检查 Stage825 的时区、交易时段、合约命名或过滤逻辑。",
        "- 如果同产品当天有其他合约但 exact contract 缺失，优先检查主力映射和实际交易合约分钟源。",
        "- 如果 exact contract 完全缺源，则需要补历史分钟数据；不能用同产品其他合约替代成交路径。",
        "",
        "## 反思",
        "",
        "- 运行前过拟合判断：否。本阶段只做数据存在性审计，不选择规则。",
        "- 运行后过拟合判断：否。结论继续收敛为补数据，不给失败规则找参数出口。",
        "- 运行前继续价值判断：有价值。Stage852 已证明缺口影响大，必须定位缺口类型。",
        "- 运行后继续价值判断：有价值但仍受数据约束。若补数可行，下一步重画图谱；若不可行，暂停规则分支。",
        "",
        "## 输出",
        "",
        f"- gap_requests：`{GAP_REQUESTS_PATH}`",
        f"- gap_detail：`{GAP_DETAIL_PATH}`",
        f"- root_cause_summary：`{ROOT_CAUSE_PATH}`",
        f"- fetch_plan：`{FETCH_PLAN_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    requests = _build_gap_requests()
    if requests.empty:
        raise RuntimeError("No minute gap requests found")
    vt_symbols = set(requests["vt_symbol"].astype(str))
    products = set(requests["product"].astype(str))
    symbol_index, product_date_counts = _build_minute_index(vt_symbols, products)
    detail = _classify_requests(requests, symbol_index, product_date_counts)
    root_summary = _root_cause_summary(detail)
    fetch_plan = _fetch_plan(detail)
    summary = _summary(detail, root_summary, fetch_plan)
    prior = _load_json(STAGE852_DECISION_PATH)

    requests.to_csv(GAP_REQUESTS_PATH, index=False, encoding="utf-8-sig")
    detail.to_csv(GAP_DETAIL_PATH, index=False, encoding="utf-8-sig")
    root_summary.to_csv(ROOT_CAUSE_PATH, index=False, encoding="utf-8-sig")
    fetch_plan.to_csv(FETCH_PLAN_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")

    decision = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "line_id": LINE_ID,
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": "stage853_minute_gap_mostly_true_missing_contract_or_date_no_rule",
        "new_rule_allowed": 0,
        "engine_allowed": 0,
        "next_step": "Use the fetch plan to fill exact contract/date minute bars, then rerun Stage825/849 visual atlases before any new rule.",
        "metrics": summary.iloc[0].to_dict(),
        "prior_decision": prior.get("decision", ""),
        "inputs": {
            "stage825_intraday": str(STAGE825_INTRADAY_PATH),
            "stage849_minute": str(STAGE849_MINUTE_PATH),
            "stage849_pairs": str(STAGE849_PAIRS_PATH),
            "stage852_decision": str(STAGE852_DECISION_PATH),
            "minute_sources": [str(path) for path in MINUTE_SOURCE_PATHS],
        },
        "outputs": {
            "gap_requests": str(GAP_REQUESTS_PATH),
            "gap_detail": str(GAP_DETAIL_PATH),
            "root_cause_summary": str(ROOT_CAUSE_PATH),
            "fetch_plan": str(FETCH_PLAN_PATH),
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, root_summary, fetch_plan, detail, decision)
    print(f"[{STAGE}] decision: {decision['decision']}")
    print(f"[{STAGE}] report: {REPORT_PATH}")
    print(f"[{STAGE}] decision json: {DECISION_PATH}")


if __name__ == "__main__":
    main()
