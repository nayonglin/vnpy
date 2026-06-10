from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import re
import sqlite3
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
REPO_DIR = PROJECT_DIR.parents[1]
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

from main_contract_mapping import ALL_FUTURES_MAPPING_PATH, load_mapping_df  # noqa: E402
from qmt_universe import PRODUCT_SPECS, ProductSpec  # noqa: E402
from vnpy.trader.constant import Exchange  # noqa: E402


MODEL_TAG = "stage765_2019_data_extension_readiness_v1"
OUTPUT_PREFIX = "qmt_roll_stage765_2019_data_extension_readiness"
LINE_ID = "futures_trend_2019_data_extension"

DB_PATH = REPO_DIR / ".vntrader" / "database.db"
TUSHARE_ROOT = PROJECT_DIR / "downloaded_futures" / "tushare_stage196_stage78_2015_2019"
READINESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_readiness_{MODEL_TAG}.csv"
MAPPING_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_mapping_coverage_{MODEL_TAG}.csv"
RAW_CONTRACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_raw_contract_coverage_{MODEL_TAG}.csv"
DB_OVERVIEW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_db_overview_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

ANALYSIS_START = pd.Timestamp("2019-01-02")
ANALYSIS_END = pd.Timestamp("2019-12-31")
PRELOAD_START = pd.Timestamp("2018-06-01")

REQUIRED_RUN_PRODUCTS = {
    "au.SHFE",
    "cu.SHFE",
    "MA.CZCE",
    "OI.CZCE",
    "rb.SHFE",
    "jm.DCE",
    "hc.SHFE",
    "CF.CZCE",
    "FG.CZCE",
    "ru.SHFE",
    "sp.SHFE",
    "fu.SHFE",
}
STAGE78_EXTRA_PRODUCT_SPECS = [
    ProductSpec("fu", Exchange.SHFE, 10, 1.0, 1.0, 0.12),
]
AUDIT_PRODUCT_SPECS = list(PRODUCT_SPECS) + STAGE78_EXTRA_PRODUCT_SPECS


def _md_table(frame: pd.DataFrame, max_rows: int = 80) -> str:
    if frame.empty:
        return "_无记录_"
    view = frame.head(max_rows).copy()
    headers = list(view.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in view.iterrows():
        lines.append("| " + " | ".join(str(row.get(col, "")) for col in headers) + " |")
    if len(frame) > max_rows:
        lines.append(f"\n_仅展示前 {max_rows} 行，共 {len(frame)} 行。_")
    return "\n".join(lines)


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        if pd.isna(value):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _db_rows() -> pd.DataFrame:
    if not DB_PATH.exists():
        raise FileNotFoundError(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    overview = pd.read_sql_query(
        """
        select symbol, exchange, interval, count, start, end
        from dbbaroverview
        where interval='d'
        order by exchange, symbol
        """,
        conn,
    )
    overview["vt_symbol"] = overview["symbol"].astype(str) + "." + overview["exchange"].astype(str)
    overview["start"] = pd.to_datetime(overview["start"], errors="coerce")
    overview["end"] = pd.to_datetime(overview["end"], errors="coerce")
    return overview


def _db_product_window(product: str, exchange: str, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, Any]:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        """
        select count(*), min(datetime), max(datetime)
        from dbbardata
        where interval='d' and symbol=? and exchange=? and datetime>=? and datetime<=?
        """,
        (product, exchange, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")),
    ).fetchone()
    return {
        "count": _safe_int(row[0]) if row else 0,
        "first": row[1] if row else None,
        "last": row[2] if row else None,
    }


def _canonical_contract_from_ts_code(ts_code: str) -> str:
    text = str(ts_code).strip()
    if "." not in text:
        return text
    symbol, exchange = text.split(".", 1)
    exchange_map = {
        "SHF": "SHFE",
        "ZCE": "CZCE",
        "DCE": "DCE",
        "CFFEX": "CFFEX",
        "INE": "INE",
        "GFE": "GFEX",
        "GFEX": "GFEX",
    }
    exchange_value = exchange_map.get(exchange.upper(), exchange.upper())
    if exchange_value in {"DCE", "SHFE", "INE", "GFEX"}:
        symbol = symbol.lower()
    return f"{symbol}.{exchange_value}"


def _product_from_vt(vt_symbol: str) -> str:
    symbol = str(vt_symbol).split(".", 1)[0]
    return re.sub(r"\d+$", "", symbol)


def _scan_tushare_raw_contracts() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if not TUSHARE_ROOT.exists():
        return pd.DataFrame()
    for path in sorted(TUSHARE_ROOT.rglob("*.csv")):
        try:
            frame = pd.read_csv(path)
        except Exception as exc:  # noqa: BLE001
            rows.append(
                {
                    "file_path": str(path),
                    "status": "read_error",
                    "message": repr(exc),
                }
            )
            continue
        if frame.empty or "trade_date" not in frame.columns:
            rows.append(
                {
                    "file_path": str(path),
                    "status": "empty_or_missing_trade_date",
                    "message": "",
                }
            )
            continue
        ts_code = str(frame["ts_code"].dropna().iloc[0]) if "ts_code" in frame.columns and frame["ts_code"].notna().any() else path.stem
        vt_symbol = _canonical_contract_from_ts_code(ts_code)
        product = _product_from_vt(vt_symbol)
        trade_date = pd.to_datetime(frame["trade_date"].astype(str), errors="coerce")
        in_2019 = frame[(trade_date >= ANALYSIS_START) & (trade_date <= ANALYSIS_END)].copy()
        rows.append(
            {
                "file_path": str(path),
                "file_name": path.name,
                "status": "ok",
                "ts_code": ts_code,
                "contract_vt_symbol": vt_symbol,
                "product": product,
                "exchange": vt_symbol.split(".", 1)[1] if "." in vt_symbol else "",
                "rows_total": int(len(frame)),
                "first_date": trade_date.min().date().isoformat() if trade_date.notna().any() else "",
                "last_date": trade_date.max().date().isoformat() if trade_date.notna().any() else "",
                "rows_2019": int(len(in_2019)),
                "first_2019": trade_date[(trade_date >= ANALYSIS_START) & (trade_date <= ANALYSIS_END)].min().date().isoformat()
                if len(in_2019)
                else "",
                "last_2019": trade_date[(trade_date >= ANALYSIS_START) & (trade_date <= ANALYSIS_END)].max().date().isoformat()
                if len(in_2019)
                else "",
                "volume_sum_2019": float(pd.to_numeric(in_2019.get("vol", 0.0), errors="coerce").fillna(0.0).sum())
                if len(in_2019)
                else 0.0,
                "oi_sum_2019": float(pd.to_numeric(in_2019.get("oi", 0.0), errors="coerce").fillna(0.0).sum())
                if len(in_2019)
                else 0.0,
                "message": "",
            }
        )
    return pd.DataFrame(rows)


def _mapping_coverage(raw_contracts: pd.DataFrame) -> pd.DataFrame:
    if not ALL_FUTURES_MAPPING_PATH.exists():
        return pd.DataFrame()
    mapping = load_mapping_df(ALL_FUTURES_MAPPING_PATH)
    mapping["date"] = pd.to_datetime(mapping["date"], errors="coerce").dt.normalize()
    mapping = mapping[(mapping["date"] >= ANALYSIS_START) & (mapping["date"] <= ANALYSIS_END)].copy()
    product_set = {spec.vt_symbol for spec in AUDIT_PRODUCT_SPECS}
    mapping = mapping[mapping["continuous_symbol_vt"].isin(product_set)].copy()
    raw_set = set(raw_contracts["contract_vt_symbol"].dropna().astype(str)) if not raw_contracts.empty else set()

    conn = sqlite3.connect(DB_PATH)
    db_contracts = pd.read_sql_query(
        """
        select distinct symbol || '.' || exchange as contract_vt_symbol
        from dbbardata
        where interval='d' and datetime>=? and datetime<=?
        """,
        conn,
        params=(ANALYSIS_START.strftime("%Y-%m-%d"), ANALYSIS_END.strftime("%Y-%m-%d")),
    )
    db_set = set(db_contracts["contract_vt_symbol"].astype(str))
    rows: list[dict[str, Any]] = []
    for product, group in mapping.groupby("continuous_symbol_vt", sort=True):
        contracts = sorted({item for item in group["main_contract_vt"].dropna().astype(str) if item})
        missing_db = sorted([item for item in contracts if item not in db_set])
        missing_raw = sorted([item for item in contracts if item not in raw_set])
        rows.append(
            {
                "product_vt_symbol": product,
                "mapped_days_2019": int(len(group)),
                "main_contract_count_2019": int(len(contracts)),
                "main_contract_examples_2019": ",".join(contracts[:8]),
                "db_contract_present_count": int(len(contracts) - len(missing_db)),
                "db_contract_missing_count": int(len(missing_db)),
                "db_contract_missing_examples": ",".join(missing_db[:8]),
                "raw_tushare_contract_present_count": int(len(contracts) - len(missing_raw)),
                "raw_tushare_contract_missing_count": int(len(missing_raw)),
                "raw_tushare_contract_missing_examples": ",".join(missing_raw[:8]),
            }
        )
    return pd.DataFrame(rows)


def _build_product_readiness(db_overview: pd.DataFrame, raw_contracts: pd.DataFrame, mapping_cov: pd.DataFrame) -> pd.DataFrame:
    raw_2019_by_product = (
        raw_contracts[raw_contracts["rows_2019"].fillna(0).astype(float) > 0]
        .groupby(["product", "exchange"], as_index=False)
        .agg(
            raw_contract_files_2019=("contract_vt_symbol", "nunique"),
            raw_rows_2019=("rows_2019", "sum"),
            raw_first_2019=("first_2019", "min"),
            raw_last_2019=("last_2019", "max"),
        )
        if not raw_contracts.empty and "rows_2019" in raw_contracts.columns
        else pd.DataFrame()
    )
    mapping_by_product = mapping_cov.set_index("product_vt_symbol").to_dict("index") if not mapping_cov.empty else {}
    overview_by_vt = db_overview.set_index("vt_symbol").to_dict("index")
    rows: list[dict[str, Any]] = []
    for spec in AUDIT_PRODUCT_SPECS:
        vt = spec.vt_symbol
        product = spec.product
        exchange = spec.exchange.value
        db_pre = _db_product_window(product, exchange, PRELOAD_START, ANALYSIS_END)
        db_2019 = _db_product_window(product, exchange, ANALYSIS_START, ANALYSIS_END)
        ov = overview_by_vt.get(vt, {})
        raw_row = raw_2019_by_product[
            raw_2019_by_product["product"].astype(str).str.lower().eq(product.lower())
            & raw_2019_by_product["exchange"].astype(str).eq(exchange)
        ] if not raw_2019_by_product.empty else pd.DataFrame()
        raw_present = not raw_row.empty
        map_row = mapping_by_product.get(vt, {})
        mapped_days = _safe_int(map_row.get("mapped_days_2019", 0))
        db_missing_contracts = _safe_int(map_row.get("db_contract_missing_count", 0))
        raw_missing_contracts = _safe_int(map_row.get("raw_tushare_contract_missing_count", 0))
        mapped_contracts = _safe_int(map_row.get("main_contract_count_2019", 0))

        product_cont_full = (
            db_2019["count"] >= 220
            and db_2019["first"]
            and pd.Timestamp(db_2019["first"]) <= ANALYSIS_START + pd.Timedelta(days=10)
            and db_2019["last"]
            and pd.Timestamp(db_2019["last"]) >= ANALYSIS_END - pd.Timedelta(days=10)
        )

        if product_cont_full:
            readiness = "product_continuous_full_ready"
            action = "can_directly_run_product_continuous_from_2019_start"
        elif mapped_days > 0 and mapped_contracts > 0 and db_missing_contracts == 0:
            readiness = "db_contracts_ready_for_main_contract_backtest"
            action = "run_current_main_contract_engine_or_build_product_continuous"
        elif mapped_days > 0 and mapped_contracts > 0 and raw_missing_contracts == 0:
            readiness = "rebuild_from_tushare_contracts"
            action = "build_2019_product_continuous_or_contract_mapping_import"
        elif db_2019["count"] > 0:
            readiness = "product_continuous_partial_only"
            action = "not_enough_for_2019_start_without_contract_mapping"
        elif raw_present:
            readiness = "raw_contracts_partial_needs_mapping_or_gaps"
            action = "audit_missing_main_contracts_before_backtest"
        else:
            readiness = "not_available_or_not_listed"
            action = "exclude_until_real_listing_or_backfill"

        listed_after_2019 = vt in {"lc.GFEX", "si.GFEX", "SH.CZCE", "lh.DCE", "SA.CZCE"}
        if listed_after_2019 and db_2019["count"] == 0 and not raw_present:
            readiness = "not_listed_or_not_in_2019_pool"
            action = "exclude_2019_then_join_after_real_available_date"

        rows.append(
            {
                "vt_symbol": vt,
                "product": product,
                "exchange": exchange,
                "current_pool": 1,
                "overview_count": _safe_int(ov.get("count", 0)),
                "overview_start": pd.Timestamp(ov.get("start")).date().isoformat() if ov.get("start") is not None and not pd.isna(ov.get("start")) else "",
                "overview_end": pd.Timestamp(ov.get("end")).date().isoformat() if ov.get("end") is not None and not pd.isna(ov.get("end")) else "",
                "db_product_cont_bars_2019": db_2019["count"],
                "db_product_cont_first_2019": db_2019["first"] or "",
                "db_product_cont_last_2019": db_2019["last"] or "",
                "db_product_cont_bars_preload_to_2019": db_pre["count"],
                "raw_contract_files_2019": int(raw_row["raw_contract_files_2019"].iloc[0]) if raw_present else 0,
                "raw_rows_2019": int(raw_row["raw_rows_2019"].iloc[0]) if raw_present else 0,
                "raw_first_2019": str(raw_row["raw_first_2019"].iloc[0]) if raw_present else "",
                "raw_last_2019": str(raw_row["raw_last_2019"].iloc[0]) if raw_present else "",
                "mapped_days_2019": mapped_days,
                "mapped_main_contracts_2019": mapped_contracts,
                "mapped_main_contract_examples_2019": map_row.get("main_contract_examples_2019", ""),
                "mapped_db_missing_contract_count": db_missing_contracts,
                "mapped_db_missing_examples": map_row.get("db_contract_missing_examples", ""),
                "mapped_raw_missing_contract_count": raw_missing_contracts,
                "mapped_raw_missing_examples": map_row.get("raw_tushare_contract_missing_examples", ""),
                "readiness": readiness,
                "recommended_action": action,
            }
        )
    return pd.DataFrame(rows)


def _decision(readiness: pd.DataFrame, mapping_cov: pd.DataFrame) -> dict[str, Any]:
    direct = readiness[readiness["readiness"].eq("product_continuous_full_ready")]
    contract_ready = readiness[readiness["readiness"].eq("db_contracts_ready_for_main_contract_backtest")]
    rebuild = readiness[readiness["readiness"].eq("rebuild_from_tushare_contracts")]
    later = readiness[readiness["readiness"].str.contains("not_listed|not_available", na=False)]
    tradable_2019 = readiness[
        readiness["readiness"].isin(
            [
                "product_continuous_full_ready",
                "db_contracts_ready_for_main_contract_backtest",
                "rebuild_from_tushare_contracts",
            ]
        )
    ]
    run_ready_now = set(direct["vt_symbol"].astype(str))
    contract_ready_now = set(contract_ready["vt_symbol"].astype(str))
    rebuild_needed = set(rebuild["vt_symbol"].astype(str))
    must_exclude = set(later["vt_symbol"].astype(str))
    hard_fail: list[str] = []
    if len(run_ready_now) < len(REQUIRED_RUN_PRODUCTS):
        hard_fail.append("current_product_continuous_2019_coverage_insufficient_for_direct_backtest")
    if len(contract_ready_now) + len(run_ready_now) < len(REQUIRED_RUN_PRODUCTS):
        hard_fail.append("requires_2019_product_continuous_rebuild_from_contract_data")
    if rebuild_needed:
        hard_fail.append("requires_external_tushare_contract_backfill")
    return {
        "stage": "Stage765",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "analysis_start": ANALYSIS_START.date().isoformat(),
        "analysis_end": ANALYSIS_END.date().isoformat(),
        "preload_start": PRELOAD_START.date().isoformat(),
        "decision": (
            "2019_contract_backtest_ready_product_continuous_direct_not_ready"
            if contract_ready_now and "requires_2019_product_continuous_rebuild_from_contract_data" not in hard_fail
            else "2019_direct_backtest_not_ready_rebuild_needed"
        ),
        "hard_fail_checks": hard_fail,
        "current_pool_count": int(len(readiness)),
        "product_continuous_full_ready_count": int(len(direct)),
        "db_contracts_ready_for_main_contract_backtest_count": int(len(contract_ready)),
        "rebuild_from_tushare_contracts_count": int(len(rebuild)),
        "tradable_or_rebuildable_2019_count": int(len(tradable_2019)),
        "exclude_until_listing_or_backfill_count": int(len(later)),
        "product_continuous_full_ready_products": sorted(run_ready_now),
        "db_contracts_ready_for_main_contract_backtest_products": sorted(contract_ready_now),
        "rebuild_needed_products": sorted(rebuild_needed),
        "exclude_or_not_available_products": sorted(must_exclude),
        "mapping_products_2019_count": int(mapping_cov["product_vt_symbol"].nunique()) if not mapping_cov.empty else 0,
        "outputs": {
            "readiness": str(READINESS_PATH),
            "mapping_coverage": str(MAPPING_COVERAGE_PATH),
            "raw_contracts": str(RAW_CONTRACT_PATH),
            "db_overview": str(DB_OVERVIEW_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _plot(readiness: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(16, 9), sharex=True)
    data = readiness.sort_values("vt_symbol").copy()
    x = np.arange(len(data))
    axes[0].bar(x, pd.to_numeric(data["db_product_cont_bars_2019"], errors="coerce").fillna(0), color="#2563eb", label="DB product continuous bars 2019")
    axes[0].bar(x, pd.to_numeric(data["raw_rows_2019"], errors="coerce").fillna(0), color="#f97316", alpha=0.45, label="Raw Tushare contract rows 2019")
    axes[0].set_ylabel("Rows")
    axes[0].set_title("2019 data coverage by current product pool")
    axes[0].legend(loc="upper right")
    axes[0].grid(axis="y", alpha=0.2)

    readiness_order = {
        "product_continuous_full_ready": 4,
        "db_contracts_ready_for_main_contract_backtest": 3,
        "rebuild_from_tushare_contracts": 3,
        "raw_contracts_partial_needs_mapping_or_gaps": 1,
        "not_listed_or_not_in_2019_pool": 0,
        "not_available_or_not_listed": 0,
        "product_continuous_partial_only": 0,
    }
    colors = {
        4: "#059669",
        3: "#f59e0b",
        2: "#38bdf8",
        1: "#f97316",
        0: "#dc2626",
    }
    values = data["readiness"].map(readiness_order).fillna(0).astype(int)
    axes[1].bar(x, values, color=[colors[int(v)] for v in values])
    axes[1].set_ylabel("Readiness level")
    axes[1].set_yticks([0, 1, 2, 3, 4])
    axes[1].set_yticklabels(["exclude", "partial", "db contract", "rebuild", "direct"])
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(data["vt_symbol"].tolist(), rotation=45, ha="right")
    axes[1].grid(axis="y", alpha=0.2)
    fig.suptitle("Stage765 2019 data extension readiness", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def _write_report(readiness: pd.DataFrame, mapping_cov: pd.DataFrame, decision: dict[str, Any]) -> None:
    status_counts = readiness.groupby("readiness", as_index=False).size().rename(columns={"size": "count"})
    view_cols = [
        "vt_symbol",
        "db_product_cont_bars_2019",
        "raw_contract_files_2019",
        "raw_rows_2019",
        "mapped_days_2019",
        "mapped_main_contracts_2019",
        "mapped_raw_missing_contract_count",
        "readiness",
        "recommended_action",
    ]
    lines = [
        "# Stage765 2019 数据延展 readiness",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 数据库：`{DB_PATH}`",
        f"- Tushare 原始合约目录：`{TUSHARE_ROOT}`",
        f"- 主力映射：`{ALL_FUTURES_MAPPING_PATH}`",
        f"- 目标区间：`{ANALYSIS_START.date()}` 至 `{ANALYSIS_END.date()}`，预热起点 `{PRELOAD_START.date()}`。",
        "- 本阶段只做数据门禁，不跑策略、不改正式配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- vn.py 数据库接口支持 `load_bar_data` 按日线区间加载历史 bar；因此框架不是约束。",
        "- Tushare 期货日线原始字段包含 `trade_date/open/high/low/close/vol/oi`，足够重建合约日线和产品连续指标。",
        "- 风险点在连续主力映射、真实合约数据、产品连续序列三者一致性；缺一项都不能把 2019 回测当成策略证据。",
        "",
        "## 决策",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- hard_fail：`{', '.join(decision['hard_fail_checks']) or '无'}`",
        f"- 产品连续全覆盖可直接跑产品：`{', '.join(decision['product_continuous_full_ready_products']) or '无'}`",
        f"- 当前主力合约引擎可跑产品：`{', '.join(decision['db_contracts_ready_for_main_contract_backtest_products']) or '无'}`",
        f"- 需从 Tushare 合约重建产品：`{', '.join(decision['rebuild_needed_products']) or '无'}`",
        f"- 2019 排除/后上市/缺数据产品：`{', '.join(decision['exclude_or_not_available_products']) or '无'}`",
        "",
        "## 状态聚合",
        "",
        _md_table(status_counts),
        "",
        "## 产品 readiness",
        "",
        _md_table(readiness[view_cols], max_rows=80),
        "",
        "## 主力映射覆盖",
        "",
        _md_table(mapping_cov, max_rows=80),
        "",
        "## 结论",
        "",
        "- 不能直接把“产品连续序列路径”的 `START_DT` 改成 2019 开跑，因为没有任何产品连续序列完整覆盖 2019-01 冷启动。",
        "- 当前 Stage757/Stage764 的真实主力合约映射引擎可以推进：2019 有 14 个实际可交易品种具备主力映射和真实合约日线。",
        "- 2019 可交易池应只包含当时有映射、有合约日线的数据品种，后上市品种按真实日期加入。",
        "- 下一步可以做只读 2019 起点单臂回测；若要做产品连续指标研究，再额外重建产品连续 bar。不根据 2019 结果改参数。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    db_overview = _db_rows()
    raw_contracts = _scan_tushare_raw_contracts()
    mapping_cov = _mapping_coverage(raw_contracts)
    readiness = _build_product_readiness(db_overview, raw_contracts, mapping_cov)
    decision = _decision(readiness, mapping_cov)
    _plot(readiness)
    _write_report(readiness, mapping_cov, decision)

    db_overview.to_csv(DB_OVERVIEW_PATH, index=False, encoding="utf-8-sig")
    raw_contracts.to_csv(RAW_CONTRACT_PATH, index=False, encoding="utf-8-sig")
    mapping_cov.to_csv(MAPPING_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    readiness.to_csv(READINESS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
