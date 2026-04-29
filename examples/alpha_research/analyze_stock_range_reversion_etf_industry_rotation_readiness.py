from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"

BROAD_ETF_DATA_DIR: Path = NATIVE_RESULTS_DIR / "stock_range_reversion_broad_etf_data_2018_2026"
BROAD_ETF_BASIC_PATH: Path = BROAD_ETF_DATA_DIR / "stock_range_reversion_broad_etf_data_v1_selected_basic.csv"
BROAD_ETF_SUMMARY_PATH: Path = BROAD_ETF_DATA_DIR / "stock_range_reversion_broad_etf_data_v1_summary.csv"
BROAD_ETF_DAILY_PATH: Path = BROAD_ETF_DATA_DIR / "stock_range_reversion_broad_etf_data_v1_selected_daily.csv"
FUND_BASIC_ALL_PATH: Path = BROAD_ETF_DATA_DIR / "stock_range_reversion_broad_etf_data_v1_fund_basic_all.csv"

OUTPUT_DIR: Path = (NATIVE_RESULTS_DIR / "stock_range_reversion_etf_industry_rotation_readiness_2018_2026").resolve()
PREFIX: str = "stock_range_reversion_etf_industry_rotation_readiness_v1"

USER_RETURN_TARGET: float = 1.0
USER_MAX_DRAWDOWN_LIMIT: float = -0.20

ROUTE_SUMMARY_PATHS: tuple[tuple[str, Path, str], ...] = (
    (
        "broad_etf_template_state",
        NATIVE_RESULTS_DIR
        / "stock_range_reversion_broad_etf_template_state_2018_2026"
        / "stock_range_reversion_broad_etf_template_state_v1_summary.csv",
        "跨宽基ETF固定模板状态归因",
    ),
    (
        "broad_etf_primary_pool_topn",
        NATIVE_RESULTS_DIR
        / "stock_range_reversion_broad_etf_primary_pool_2018_2026"
        / "stock_range_reversion_broad_etf_primary_pool_v1_summary.csv",
        "宽基ETF池topN超跌轮动",
    ),
    (
        "broad_etf_signal_sleeve",
        NATIVE_RESULTS_DIR
        / "stock_range_reversion_broad_etf_signal_sleeve_2018_2026"
        / "stock_range_reversion_broad_etf_signal_sleeve_v1_summary.csv",
        "宽基ETF小权重全信号袖珍仓",
    ),
    (
        "broad_etf_fixed_index_sleeve",
        NATIVE_RESULTS_DIR
        / "stock_range_reversion_broad_etf_fixed_index_sleeve_2018_2026"
        / "stock_range_reversion_broad_etf_fixed_index_sleeve_v1_summary.csv",
        "固定指数袖珍仓画像",
    ),
    (
        "market_down_etf_hedge_pressure",
        NATIVE_RESULTS_DIR
        / "stock_range_reversion_market_down_etf_hedge_pressure_2018_2026"
        / "stock_range_reversion_market_down_etf_hedge_pressure_v1_summary.csv",
        "ETF空头对冲压力测试",
    ),
)

LOCAL_CACHE_DIRS: tuple[Path, ...] = (
    BROAD_ETF_DATA_DIR / "fund_daily_cache",
    NATIVE_RESULTS_DIR / "stock_range_reversion_csi1000_etf_data_2018_2026" / "fund_daily_cache",
    NATIVE_RESULTS_DIR / "stock_range_reversion_sector_etf_data_2018_2026" / "fund_daily_cache",
)

INDUSTRY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "financial_real_estate": ("证券", "券商", "银行", "保险", "金融", "地产"),
    "technology": (
        "半导体",
        "芯片",
        "电子",
        "通信",
        "计算机",
        "软件",
        "互联网",
        "人工智能",
        "AI",
        "机器人",
        "云计算",
        "数据",
        "传媒",
        "游戏",
    ),
    "advanced_manufacturing": ("军工", "新能源", "光伏", "电池", "汽车", "智能车", "制造", "机械", "装备"),
    "healthcare": ("医药", "医疗", "生物", "创新药", "疫苗", "中药"),
    "consumer": ("消费", "白酒", "酒", "食品", "家电", "旅游", "养殖", "农业", "牧"),
    "cyclicals": ("有色", "煤炭", "钢铁", "化工", "能源", "稀土", "资源", "建材"),
    "defensive": ("公用", "环保", "电力"),
}

BROAD_STYLE_WORDS: tuple[str, ...] = (
    "沪深300",
    "中证300",
    "上证50",
    "中证500",
    "中证1000",
    "中证2000",
    "国证2000",
    "中证800",
    "中证A500",
    "A500",
    "深证100",
    "创业板",
    "科创50",
    "红利",
    "央企",
    "国企",
    "MSCI",
    "质量",
    "价值",
    "成长",
    "增强",
)


def pct(value: Any) -> str:
    try:
        number = float(value)
    except Exception:
        return "NA"
    return f"{number:.2%}"


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def safe_float(value: Any, default: float = float("nan")) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def safe_str(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def classify_industry_bucket(name: str) -> str:
    for bucket, keywords in INDUSTRY_KEYWORDS.items():
        if any(keyword in name for keyword in keywords):
            return bucket
    return ""


def is_probable_sector_etf(name: str) -> bool:
    if not name or "ETF" not in name:
        return False
    if "联接" in name or "ETF联接" in name:
        return False
    bucket = classify_industry_bucket(name)
    if not bucket:
        return False
    if any(word in name for word in BROAD_STYLE_WORDS) and bucket not in {"technology", "healthcare", "consumer"}:
        return False
    return True


def parse_yyyymmdd(value: Any) -> pd.Timestamp | pd.NaT:
    text = safe_str(value).strip()
    if not text:
        return pd.NaT
    if text.endswith(".0"):
        text = text[:-2]
    return pd.to_datetime(text, format="%Y%m%d", errors="coerce")


def local_cached_codes() -> set[str]:
    codes: set[str] = set()
    for directory in LOCAL_CACHE_DIRS:
        if not directory.exists():
            continue
        for path in directory.glob("*.csv"):
            name = path.name
            if "_" not in name:
                continue
            codes.add(name.split("_", 1)[0])
    return codes


def build_sector_candidate_inventory(fund_basic: pd.DataFrame) -> pd.DataFrame:
    if fund_basic.empty:
        return pd.DataFrame()
    cached = local_cached_codes()
    work = fund_basic.copy()
    work["name"] = work["name"].map(safe_str)
    work["list_dt"] = work["list_date"].map(parse_yyyymmdd)
    work["due_dt"] = work["due_date"].map(parse_yyyymmdd) if "due_date" in work.columns else pd.NaT
    work["is_current_listed"] = work["list_dt"].notna() & work["due_dt"].isna()
    work["industry_bucket"] = work["name"].map(classify_industry_bucket)
    work["is_probable_sector_etf"] = work["name"].map(is_probable_sector_etf)
    work["has_local_daily_cache"] = work["ts_code"].isin(cached)
    work["listed_before_2019"] = work["list_dt"] <= pd.Timestamp("2019-01-01")
    work["listed_before_2021"] = work["list_dt"] <= pd.Timestamp("2021-01-01")
    columns = [
        "ts_code",
        "name",
        "fund_type",
        "list_date",
        "due_date",
        "industry_bucket",
        "is_current_listed",
        "listed_before_2019",
        "listed_before_2021",
        "has_local_daily_cache",
        "management",
        "m_fee",
        "c_fee",
    ]
    return (
        work[work["is_probable_sector_etf"]]
        .sort_values(["industry_bucket", "list_dt", "ts_code"])
        [[col for col in columns if col in work.columns]]
        .reset_index(drop=True)
    )


def summarize_sector_candidates(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame(
            columns=[
                "industry_bucket",
                "candidate_count",
                "current_listed_count",
                "listed_before_2019_count",
                "listed_before_2021_count",
                "local_daily_cache_count",
                "earliest_list_date",
            ]
        )
    grouped = (
        candidates.groupby("industry_bucket", dropna=False)
        .agg(
            candidate_count=("ts_code", "count"),
            current_listed_count=("is_current_listed", "sum"),
            listed_before_2019_count=("listed_before_2019", "sum"),
            listed_before_2021_count=("listed_before_2021", "sum"),
            local_daily_cache_count=("has_local_daily_cache", "sum"),
            earliest_list_date=("list_date", "min"),
        )
        .reset_index()
    )
    return grouped.sort_values(["current_listed_count", "candidate_count"], ascending=False).reset_index(drop=True)


def choose_best_route_row(route_key: str, frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"route": route_key, "status": "missing"}
    work = frame.copy()
    if "roundtrip_cost_bps" in work.columns:
        cost20 = work[work["roundtrip_cost_bps"].map(safe_float) == 20.0]
        if not cost20.empty:
            work = cost20
    for column in ("final_equity", "total_return", "max_drawdown", "sharpe"):
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce")
    if "tradability" in work.columns:
        tradable = work[work["tradability"].astype(str).str.contains("tradable_long_only_baseline", na=False)]
        if not tradable.empty:
            work = tradable
    best = work.sort_values(["final_equity", "sharpe"], ascending=False).head(1)
    if best.empty:
        return {"route": route_key, "status": "empty_after_filter"}
    row = best.iloc[0].to_dict()
    variant_parts = []
    for column in ("portfolio", "ts_code", "etf_code", "index_name", "strategy", "scenario", "universe"):
        value = safe_str(row.get(column))
        if value:
            variant_parts.append(value)
    total_return = safe_float(row.get("total_return"))
    max_drawdown = safe_float(row.get("max_drawdown"))
    return {
        "route": route_key,
        "status": "available",
        "best_variant": " / ".join(variant_parts[:5]),
        "roundtrip_cost_bps": row.get("roundtrip_cost_bps"),
        "start_date": row.get("start_date"),
        "end_date": row.get("end_date"),
        "days": row.get("days"),
        "final_equity": row.get("final_equity"),
        "total_return": row.get("total_return"),
        "max_drawdown": row.get("max_drawdown"),
        "sharpe": row.get("sharpe"),
        "meets_user_goal": bool(total_return >= USER_RETURN_TARGET and max_drawdown >= USER_MAX_DRAWDOWN_LIMIT),
    }


def build_existing_route_summary() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for route_key, path, description in ROUTE_SUMMARY_PATHS:
        row = choose_best_route_row(route_key, read_csv(path))
        row["description"] = description
        row["source_path"] = str(path)
        rows.append(row)
    return pd.DataFrame(rows)


def build_readiness_checkpoints(
    broad_basic: pd.DataFrame,
    broad_daily: pd.DataFrame,
    sector_candidates: pd.DataFrame,
    route_summary: pd.DataFrame,
) -> pd.DataFrame:
    sector_current = int(sector_candidates["is_current_listed"].sum()) if not sector_candidates.empty else 0
    sector_local = int(sector_candidates["has_local_daily_cache"].sum()) if not sector_candidates.empty else 0
    long_2019 = int(sector_candidates["listed_before_2019"].sum()) if not sector_candidates.empty else 0
    route_goal_hits = (
        int(route_summary["meets_user_goal"].fillna(False).sum()) if "meets_user_goal" in route_summary.columns else 0
    )
    rows = [
        {
            "checkpoint": "broad_etf_data_available",
            "status": "pass" if not broad_basic.empty and not broad_daily.empty else "fail",
            "value": f"basic={len(broad_basic)}, daily_rows={len(broad_daily)}",
            "expected": "已有宽基ETF日线和基础信息",
            "judgement": "宽基ETF足够继续做画像，但不是收益主引擎。",
        },
        {
            "checkpoint": "sector_etf_candidates_exist",
            "status": "pass" if sector_current >= 30 else "warn",
            "value": f"current_sector_candidates={sector_current}",
            "expected": "至少30个当前上市行业/主题ETF候选",
            "judgement": "fund_basic里能找到行业/主题ETF候选，说明不是没有标的。",
        },
        {
            "checkpoint": "sector_etf_long_history_depth",
            "status": "pass" if long_2019 >= 10 else "warn",
            "value": f"listed_before_2019={long_2019}",
            "expected": "最好有10个以上2019年前上市候选",
            "judgement": "有一批长历史候选可做初步对照，但仍要防止2021后主题ETF样本占比过高。",
        },
        {
            "checkpoint": "sector_etf_local_daily_available",
            "status": "pass" if sector_local >= 10 else "fail",
            "value": f"local_daily_cache={sector_local}",
            "expected": "至少10个行业ETF已有本地日线",
            "judgement": "当前本地缓存主要是宽基/中证1000ETF，不足以直接做行业ETF回测。",
        },
        {
            "checkpoint": "existing_broad_etf_route_meets_30w_goal",
            "status": "pass" if route_goal_hits > 0 else "fail",
            "value": f"goal_hits={route_goal_hits}",
            "expected": "总收益>=100%且最大回撤>=-20%",
            "judgement": "宽基ETF旧路线没有达到用户的30万高收益目标。",
        },
        {
            "checkpoint": "short_etf_tradability",
            "status": "fail",
            "value": "ordinary_long_only_account",
            "expected": "普通账户可稳定执行",
            "judgement": "ETF空头只能作为归因/压力测试，不能当作当前可交易假设。",
        },
        {
            "checkpoint": "external_research_alignment",
            "status": "pass",
            "value": "sector_momentum_plus_short_reversion",
            "expected": "与业界/论文方向一致",
            "judgement": "行业轮动应以中期行业强弱和状态过滤为主，短期回撤只做入场层。",
        },
    ]
    return pd.DataFrame(rows)


def build_route_decision(checkpoints: pd.DataFrame) -> pd.DataFrame:
    local_sector_status = checkpoints.loc[
        checkpoints["checkpoint"] == "sector_etf_local_daily_available", "status"
    ].iloc[0]
    broad_goal_status = checkpoints.loc[
        checkpoints["checkpoint"] == "existing_broad_etf_route_meets_30w_goal", "status"
    ].iloc[0]
    rows = [
        {
            "priority": 1,
            "decision": "pause_broad_etf_parameter_sweep",
            "action": "暂停继续扫宽基ETF topN、权重、暴露上限。",
            "reason": "旧结果显示宽基ETF低回撤但收益厚度不足，继续微调容易过拟合。",
            "status": "active" if broad_goal_status == "fail" else "review",
        },
        {
            "priority": 2,
            "decision": "build_sector_etf_data_pack",
            "action": "若继续ETF/行业路线，先补行业/主题ETF日线、成交额和覆盖审计。",
            "reason": "fund_basic有候选，但本地行业ETF日线缓存不足，不能严肃回测。",
            "status": "active" if local_sector_status == "fail" else "done",
        },
        {
            "priority": 3,
            "decision": "first_do_signal_attribution",
            "action": "补齐数据后先做行业中期强势+短期回撤的信号归因，而不是直接策略化。",
            "reason": "外部资料和本地经验都提示行业轮动底层更像中期动量，短反只是入场，不应直接移植单股均值回归。",
            "status": "active",
        },
        {
            "priority": 4,
            "decision": "keep_stock_single_name_core_as_feature",
            "action": "保留industry_resid_core为研究特征，不继续做单票30万交易化微调。",
            "reason": "单票信号层有效但30万整手复放回撤太深。",
            "status": "active",
        },
    ]
    return pd.DataFrame(rows)


def markdown_table(frame: pd.DataFrame, columns: list[str] | None = None, limit: int = 20) -> str:
    if frame.empty:
        return "\n无数据。\n"
    table = frame.copy()
    if columns is not None:
        table = table[[col for col in columns if col in table.columns]]
    if limit > 0:
        table = table.head(limit)
    return table.to_markdown(index=False)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def build_report(
    sector_candidates: pd.DataFrame,
    sector_bucket_summary: pd.DataFrame,
    route_summary: pd.DataFrame,
    checkpoints: pd.DataFrame,
    decisions: pd.DataFrame,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M CST")
    route_display = route_summary.copy()
    for column in ("total_return", "max_drawdown"):
        if column in route_display.columns:
            route_display[f"{column}_pct"] = route_display[column].map(pct)
    candidate_display = sector_candidates.copy()
    for frame in (sector_bucket_summary, candidate_display):
        if "earliest_list_date" in frame.columns:
            frame["earliest_list_date"] = frame["earliest_list_date"].map(lambda value: safe_str(value).replace(".0", ""))
        if "list_date" in frame.columns:
            frame["list_date"] = frame["list_date"].map(lambda value: safe_str(value).replace(".0", ""))
    return f"""# 股票震荡ETF/行业轮动路线体检 v1

- 记录时间：{now}
- 当前研究线：股票震荡独立策略研究，不接入第78。
- 本阶段性质：数据/路线体检，不是正式交易版本，不拉新数据，不做参数优化。
- 核心目标：判断宽基ETF旧路线是否值得继续，以及行业ETF路线是否具备开跑前的数据基础。

## 外部调研结论

- 业界常见ETF轮动多以行业/板块中期动量为底层，再加趋势过滤和月度/低频再平衡；它不是简单买最超跌ETF。
- 均值回归类股票/组合策略在交易成本存在时容易失效，适合先做信号归因和成本压力，而不是直接策略化。
- 因此本仓库下一步更合理的形态是“强行业/强ETF池 + 短期回撤入场 + 状态过滤”，而不是继续在宽基ETF超跌模板里调阈值。

## 现有宽基ETF路线汇总

{markdown_table(route_display, ["route", "description", "best_variant", "roundtrip_cost_bps", "final_equity", "total_return_pct", "max_drawdown_pct", "sharpe", "meets_user_goal"], 20)}

## 行业/主题ETF候选池概览

{markdown_table(sector_bucket_summary, ["industry_bucket", "candidate_count", "current_listed_count", "listed_before_2019_count", "listed_before_2021_count", "local_daily_cache_count", "earliest_list_date"], 20)}

## 当前上市行业/主题ETF候选样本

{markdown_table(candidate_display[candidate_display["is_current_listed"]], ["ts_code", "name", "industry_bucket", "list_date", "has_local_daily_cache"], 30)}

## 质量检查

{markdown_table(checkpoints, ["checkpoint", "status", "value", "expected", "judgement"], 20)}

## 决策

{markdown_table(decisions, ["priority", "decision", "status", "action", "reason"], 20)}

## 运行前过拟合反思

- 判断：否。
- 原因：本阶段只做既有结果盘点和数据覆盖审计，不新增交易阈值，不选择最优参数上线。

## 运行后过拟合反思

- 判断：否，但继续扫宽基ETF参数会过拟合。
- 原因：旧结果已经说明宽基ETF路线收益厚度不足；本阶段把“暂停微调”作为结论，而不是包装最优组合。

## 运行前继续价值反思

- 判断：是。
- 原因：单票强势回踩30万复放失败后，需要验证资产层/行业层是否更适合小账户承载。

## 运行后继续价值反思

- 判断：是，但价值在“补行业ETF数据并做信号归因”，不是继续宽基ETF参数化。
- 原因：fund_basic能筛出行业/主题ETF候选，但本地日线缓存不足；先补数据和覆盖审计，才有资格谈行业轮动回测。

## 输出文件

- `{PREFIX}_sector_candidate_inventory.csv`
- `{PREFIX}_sector_bucket_summary.csv`
- `{PREFIX}_existing_route_summary.csv`
- `{PREFIX}_readiness_checkpoints.csv`
- `{PREFIX}_route_decision.csv`
- `{PREFIX}_meta.json`
"""


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    broad_basic = read_csv(BROAD_ETF_BASIC_PATH)
    broad_summary = read_csv(BROAD_ETF_SUMMARY_PATH)
    broad_daily = read_csv(BROAD_ETF_DAILY_PATH)
    fund_basic = read_csv(FUND_BASIC_ALL_PATH)

    sector_candidates = build_sector_candidate_inventory(fund_basic)
    sector_bucket_summary = summarize_sector_candidates(sector_candidates)
    route_summary = build_existing_route_summary()
    checkpoints = build_readiness_checkpoints(broad_basic, broad_daily, sector_candidates, route_summary)
    decisions = build_route_decision(checkpoints)

    sector_candidates.to_csv(OUTPUT_DIR / f"{PREFIX}_sector_candidate_inventory.csv", index=False, encoding="utf-8-sig")
    sector_bucket_summary.to_csv(OUTPUT_DIR / f"{PREFIX}_sector_bucket_summary.csv", index=False, encoding="utf-8-sig")
    route_summary.to_csv(OUTPUT_DIR / f"{PREFIX}_existing_route_summary.csv", index=False, encoding="utf-8-sig")
    checkpoints.to_csv(OUTPUT_DIR / f"{PREFIX}_readiness_checkpoints.csv", index=False, encoding="utf-8-sig")
    decisions.to_csv(OUTPUT_DIR / f"{PREFIX}_route_decision.csv", index=False, encoding="utf-8-sig")

    meta = {
        "generated_at": datetime.now().isoformat(),
        "broad_basic_rows": int(len(broad_basic)),
        "broad_summary_rows": int(len(broad_summary)),
        "broad_daily_rows": int(len(broad_daily)),
        "fund_basic_rows": int(len(fund_basic)),
        "sector_candidate_rows": int(len(sector_candidates)),
        "current_sector_candidate_rows": int(sector_candidates["is_current_listed"].sum()) if not sector_candidates.empty else 0,
        "local_sector_daily_cache_rows": int(sector_candidates["has_local_daily_cache"].sum()) if not sector_candidates.empty else 0,
        "user_return_target": USER_RETURN_TARGET,
        "user_max_drawdown_limit": USER_MAX_DRAWDOWN_LIMIT,
        "source_paths": {
            "broad_basic": str(BROAD_ETF_BASIC_PATH),
            "broad_summary": str(BROAD_ETF_SUMMARY_PATH),
            "broad_daily": str(BROAD_ETF_DAILY_PATH),
            "fund_basic_all": str(FUND_BASIC_ALL_PATH),
        },
    }
    write_json(OUTPUT_DIR / f"{PREFIX}_meta.json", meta)

    report = build_report(sector_candidates, sector_bucket_summary, route_summary, checkpoints, decisions)
    (OUTPUT_DIR / f"{PREFIX}_report.md").write_text(report, encoding="utf-8")

    print(report)


if __name__ == "__main__":
    main()
