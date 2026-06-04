from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import re
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage633_independent_risk_slot_correlation_map_v1"
OUTPUT_PREFIX = "qmt_roll_stage633_independent_risk_slot_correlation_map"

TQSDK_DAILY_ROOT = PROJECT_DIR / "downloaded_futures" / "tqsdk_daily_2010_2026_04"
STAGE602_PRODUCT_MAP = (
    OUTPUT_DIR / "qmt_roll_stage602_full57_non_dce_new_family_scout_product_map_stage602_full57_non_dce_new_family_scout_v1.csv"
)
STAGE604_SLOT_INVENTORY = (
    OUTPUT_DIR / "qmt_roll_stage604_low_single_risk_slot_allocator_audit_slot_inventory_stage604_low_single_risk_slot_allocator_audit_v1.csv"
)
STAGE611_FAMILY_ADMISSION = (
    OUTPUT_DIR / "qmt_roll_stage611_risk_slot_admission_protocol_family_admission_stage611_risk_slot_admission_protocol_v1.csv"
)

PRODUCT_MAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_map_{MODEL_TAG}.csv"
FAMILY_MAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_map_{MODEL_TAG}.csv"
CORR_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_corr_matrix_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

MIN_TRADABLE_ROWS = 900
MIN_RECENT_TRADABLE_DAYS = 40
MIN_RECENT_MEDIAN_VOLUME = 1_000.0
MIN_CORR_OVERLAP_DAYS = 252
LOW_CORR_MAX_TO_P0 = 0.10
WATCH_CORR_MAX_TO_P0 = 0.15
LOW_TAIL_CORR_TO_CORE = 0.15
WATCH_TAIL_CORR_TO_CORE = 0.20
LOW_ROLLING_CORR_P75 = 0.20
TREND_SIGNAL_THRESHOLD = 1.25
TREND_MIN_YEARS = 3
TARGET_EFFECTIVE_SLOTS = 7
CURRENT_EFFECTIVE_SLOTS = 4

REFERENCES = [
    "Managed futures diversification overview: https://clearingcustody.fidelity.com/insights/topics/investing-ideas/managed-futures-as-a-powerful-portfolio-diversifier",
    "Hierarchical Risk Parity overview: https://en.wikipedia.org/wiki/Hierarchical_Risk_Parity",
    "pyhrp implementation: https://github.com/tschm/pyhrp",
    "ClusterPortfolios implementation: https://github.com/jpfitzinger/ClusterPortfolios",
    "PyTrendFollow futures trend following implementation: https://github.com/chrism2671/PyTrendFollow",
]


FALLBACK_PRODUCT_FAMILY: dict[str, tuple[str, str]] = {
    "ag.SHFE": ("precious_metals", "贵金属"),
    "au.SHFE": ("precious_metals", "贵金属"),
    "al.SHFE": ("base_metals", "有色金属"),
    "ao.SHFE": ("base_metals", "有色金属"),
    "bc.INE": ("base_metals", "有色金属"),
    "cu.SHFE": ("base_metals", "有色金属"),
    "lc.GFEX": ("base_metals", "新能源金属"),
    "ni.SHFE": ("base_metals", "有色金属"),
    "pb.SHFE": ("base_metals", "有色金属"),
    "si.GFEX": ("base_metals", "工业硅"),
    "sn.SHFE": ("base_metals", "有色金属"),
    "ss.SHFE": ("base_metals", "不锈钢"),
    "zn.SHFE": ("base_metals", "有色金属"),
    "i.DCE": ("black_ferrous", "黑色矿石"),
    "j.DCE": ("black_ferrous", "焦炭"),
    "jm.DCE": ("black_ferrous", "焦煤"),
    "rb.SHFE": ("black_ferrous", "螺纹钢"),
    "hc.SHFE": ("black_ferrous", "热卷"),
    "FG.CZCE": ("black_ferrous", "玻璃"),
    "SF.CZCE": ("black_ferrous", "硅铁"),
    "SM.CZCE": ("black_ferrous", "锰硅"),
    "lu.INE": ("energy_oil", "低硫燃油"),
    "fu.SHFE": ("energy_oil", "燃油"),
    "sc.INE": ("energy_oil", "原油"),
    "bu.SHFE": ("energy_oil", "沥青"),
    "pg.DCE": ("energy_oil", "LPG"),
    "v.DCE": ("petrochem", "PVC"),
    "TA.CZCE": ("petrochem", "PTA"),
    "PF.CZCE": ("petrochem", "短纤"),
    "PX.CZCE": ("petrochem", "对二甲苯"),
    "UR.CZCE": ("petrochem", "尿素"),
    "eb.DCE": ("petrochem", "苯乙烯"),
    "MA.CZCE": ("petrochem", "甲醇"),
    "SA.CZCE": ("petrochem", "纯碱"),
    "SH.CZCE": ("petrochem", "烧碱"),
    "a.DCE": ("grains_oilseeds", "豆一"),
    "c.DCE": ("grains_oilseeds", "玉米"),
    "cs.DCE": ("grains_oilseeds", "淀粉"),
    "m.DCE": ("grains_oilseeds", "豆粕"),
    "OI.CZCE": ("grains_oilseeds", "菜油"),
    "p.DCE": ("grains_oilseeds", "棕榈油"),
    "PK.CZCE": ("grains_oilseeds", "花生"),
    "rr.DCE": ("grains_oilseeds", "粳米"),
    "RM.CZCE": ("grains_oilseeds", "菜粕"),
    "y.DCE": ("grains_oilseeds", "豆油"),
    "AP.CZCE": ("soft_agri", "苹果"),
    "CF.CZCE": ("soft_agri", "棉花"),
    "CY.CZCE": ("soft_agri", "棉纱"),
    "SR.CZCE": ("soft_agri", "白糖"),
    "br.SHFE": ("rubber", "丁二烯橡胶"),
    "nr.INE": ("rubber", "20号胶"),
    "ru.SHFE": ("rubber", "橡胶"),
    "jd.DCE": ("livestock", "鸡蛋"),
    "lh.DCE": ("livestock", "生猪"),
    "fb.DCE": ("other", "纤维板"),
    "sp.SHFE": ("other", "纸浆"),
}


def _now_cst() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def _fmt_cst(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S CST")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return (
        pd.to_numeric(frame[column], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(default)
        .astype(float)
    )


def _str(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series("", index=frame.index, dtype=str)
    return frame[column].fillna("").astype(str).str.strip()


def _date_string(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 40) -> str:
    if frame.empty:
        return "_empty_"
    view = frame.copy()
    if columns is not None:
        view = view[[column for column in columns if column in view.columns]]
    if len(view) > max_rows:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _product_root(path: Path) -> str:
    match = re.match(r"^[A-Za-z]+", path.stem)
    return match.group(0) if match else path.stem


def _load_metadata() -> tuple[pd.DataFrame, pd.DataFrame, set[str], set[str], set[str], set[str]]:
    product_map = _read_csv(STAGE602_PRODUCT_MAP)
    slot_inventory = _read_csv(STAGE604_SLOT_INVENTORY)
    family_admission = _read_csv(STAGE611_FAMILY_ADMISSION)
    product_map["product_vt_symbol"] = _str(product_map, "product_vt_symbol")
    product_map["product_family"] = _str(product_map, "product_family")
    slot_inventory["slot_role"] = _str(slot_inventory, "slot_role")
    slot_inventory["product_family"] = _str(slot_inventory, "product_family")
    slot_inventory["slot_products"] = _str(slot_inventory, "slot_products")
    p0_products: set[str] = set()
    current_families: set[str] = set()
    p1_families: set[str] = set()
    p2_families: set[str] = set()
    for _, row in slot_inventory.iterrows():
        products = [item.strip() for item in str(row["slot_products"]).split(",") if item.strip()]
        if row["slot_role"] == "current_p0_structural_slot":
            p0_products.update(products)
            current_families.add(str(row["product_family"]))
        if row["slot_role"] == "p1_new_family_blocked":
            p1_families.add(str(row["product_family"]))
        if row["slot_role"] == "source_rich_no_edge_monitor":
            p2_families.add(str(row["product_family"]))
    return product_map, family_admission, p0_products, current_families, p1_families, p2_families


def _build_file_index() -> dict[str, list[Path]]:
    groups: dict[str, list[Path]] = defaultdict(list)
    for path in sorted(TQSDK_DAILY_ROOT.glob("*/*.csv")):
        exchange = path.parent.name
        product = _product_root(path)
        vt_symbol = f"{product}.{exchange}"
        groups[vt_symbol].append(path)
    return dict(groups)


def _load_product_proxy(product_vt_symbol: str, files: list[Path]) -> tuple[pd.DataFrame, dict[str, Any]]:
    parts: list[pd.DataFrame] = []
    non_empty_files = 0
    for path in files:
        try:
            frame = pd.read_csv(path, encoding="utf-8-sig")
        except Exception:
            continue
        if frame.empty:
            continue
        non_empty_files += 1
        frame["contract"] = path.stem
        frame["trade_date"] = pd.to_datetime(frame.get("trade_date"), errors="coerce")
        frame["close"] = _num(frame, "close", np.nan)
        frame["volume"] = _num(frame, "volume", 0.0)
        frame["close_oi"] = _num(frame, "close_oi", 0.0)
        frame = frame.dropna(subset=["trade_date", "close"])
        frame = frame[frame["close"].gt(0)]
        if not frame.empty:
            parts.append(frame[["trade_date", "contract", "close", "volume", "close_oi"]])
    if not parts:
        return pd.DataFrame(), {
            "product_vt_symbol": product_vt_symbol,
            "files_count": len(files),
            "non_empty_files": non_empty_files,
            "raw_rows": 0,
            "proxy_rows": 0,
            "tradable_rows": 0,
            "first_trade_date": "",
            "last_trade_date": "",
            "last_tradable_date": "",
            "recent_tradable_days": 0,
            "recent_median_volume": 0.0,
            "recent_p25_volume": 0.0,
            "recent_median_oi": 0.0,
        }

    raw = pd.concat(parts, ignore_index=True)
    raw["tradable_proxy"] = (raw["volume"].gt(0) | raw["close_oi"].gt(0)).astype(int)
    proxy = (
        raw.sort_values(["trade_date", "tradable_proxy", "volume", "close_oi"], ascending=[True, False, False, False])
        .drop_duplicates("trade_date", keep="first")
        .sort_values("trade_date")
        .reset_index(drop=True)
    )
    tradable = proxy[proxy["tradable_proxy"].eq(1)].copy()
    recent = tradable.tail(60)
    summary = {
        "product_vt_symbol": product_vt_symbol,
        "files_count": len(files),
        "non_empty_files": non_empty_files,
        "raw_rows": int(len(raw)),
        "proxy_rows": int(len(proxy)),
        "tradable_rows": int(len(tradable)),
        "first_trade_date": _date_string(proxy["trade_date"].min()),
        "last_trade_date": _date_string(proxy["trade_date"].max()),
        "last_tradable_date": _date_string(tradable["trade_date"].max()) if not tradable.empty else "",
        "recent_tradable_days": int(len(recent)),
        "recent_median_volume": float(recent["volume"].median()) if not recent.empty else 0.0,
        "recent_p25_volume": float(recent["volume"].quantile(0.25)) if not recent.empty else 0.0,
        "recent_median_oi": float(recent["close_oi"].median()) if not recent.empty else 0.0,
    }
    return tradable[["trade_date", "close", "volume", "close_oi", "contract"]].copy(), summary


def _safe_corr(left: pd.Series, right: pd.Series, min_overlap: int = MIN_CORR_OVERLAP_DAYS) -> float:
    pair = pd.concat([left, right], axis=1).dropna()
    if len(pair) < min_overlap:
        return np.nan
    return float(pair.iloc[:, 0].corr(pair.iloc[:, 1]))


def _rolling_abs_corr_p75(left: pd.Series, right: pd.Series) -> float:
    pair = pd.concat([left, right], axis=1).dropna()
    if len(pair) < MIN_CORR_OVERLAP_DAYS:
        return np.nan
    rolling = pair.iloc[:, 0].rolling(252, min_periods=126).corr(pair.iloc[:, 1]).abs().dropna()
    if rolling.empty:
        return np.nan
    return float(rolling.quantile(0.75))


def _trend_opportunity_stats(close: pd.Series) -> dict[str, Any]:
    close = close.dropna()
    if len(close) < 260:
        return {
            "trend_years": 0,
            "trend_total_years": 0,
            "trend_year_rate_pct": 0.0,
            "trend_signal_median": 0.0,
            "trend_signal_max": 0.0,
        }
    log_price = np.log(close)
    daily = log_price.diff()
    window_return = log_price.diff(63)
    window_vol = daily.rolling(63, min_periods=40).std() * math.sqrt(63)
    signal = (window_return.abs() / window_vol.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
    annual = signal.groupby(signal.index.year).max().dropna()
    if annual.empty:
        return {
            "trend_years": 0,
            "trend_total_years": 0,
            "trend_year_rate_pct": 0.0,
            "trend_signal_median": 0.0,
            "trend_signal_max": 0.0,
        }
    trend_years = int(annual.ge(TREND_SIGNAL_THRESHOLD).sum())
    total_years = int(len(annual))
    return {
        "trend_years": trend_years,
        "trend_total_years": total_years,
        "trend_year_rate_pct": float(trend_years / total_years * 100.0) if total_years else 0.0,
        "trend_signal_median": float(annual.median()),
        "trend_signal_max": float(annual.max()),
    }


def _corr_components(corr: pd.DataFrame, threshold: float = 0.30) -> dict[str, int]:
    graph: dict[str, set[str]] = {item: set() for item in corr.index}
    for left in corr.index:
        for right in corr.columns:
            if left >= right:
                continue
            value = corr.loc[left, right]
            if pd.notna(value) and abs(float(value)) >= threshold:
                graph[left].add(right)
                graph[right].add(left)
    components: dict[str, int] = {}
    visited: set[str] = set()
    component_id = 0
    for node in corr.index:
        if node in visited:
            continue
        component_id += 1
        queue: deque[str] = deque([node])
        visited.add(node)
        while queue:
            current = queue.popleft()
            components[current] = component_id
            for neighbor in graph[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
    return components


def _classify(
    row: pd.Series,
    p0_products: set[str],
    current_families: set[str],
    p1_families: set[str],
    p2_families: set[str],
) -> tuple[str, str]:
    product = str(row["product_vt_symbol"])
    family = str(row["product_family"])
    exchange = str(row["exchange"])
    if product in p0_products:
        return "p0_reference_existing_slot", "现有P0结构槽，不新增风险槽。"
    if exchange == "CFFEX":
        return "reject_out_of_commodity_scope", "金融期货不在当前商品期货扩池范围。"
    if family in p1_families:
        return "p1_existing_worklist_source_tca_blocked", "已有P1新槽工作流，仍被source/TCA阻塞。"
    if family in p2_families:
        return "p2_existing_forward_monitor", "已有P2 forward monitor，先累计PIT/outcome/TCA。"
    if int(row["data_pass"]) == 0 or int(row["liquidity_pass"]) == 0:
        return "reject_data_or_liquidity", "价格覆盖或近期流动性不足，低单笔风险不能靠低流动性实现。"
    if int(row["low_corr_pass"]) == 0 and int(row["watch_corr_pass"]) == 0:
        return "reject_high_core_corr", "与现有P0或核心尾部相关性过高，不能降低独立单槽风险。"
    if family in current_families:
        return "same_family_depth_not_slot", "现有P0同族深度，只能做同族替补或tie-break，不增加独立槽。"
    if int(row["low_corr_pass"]) == 1 and int(row["trend_opportunity_pass"]) == 1:
        return "new_structural_monitor_candidate", "低相关且有价格趋势机会，只能进入source/TCA监控候选。"
    if int(row["watch_corr_pass"]) == 1:
        return "observe_low_corr_but_weak_trend", "相关性可观察，但趋势机会或样本稳定性不足。"
    return "observe_only", "结构证据不足，观察。"


def _build_product_map() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    product_map, family_admission, p0_products, current_families, p1_families, p2_families = _load_metadata()
    meta = product_map.set_index("product_vt_symbol").to_dict("index")

    file_index = _build_file_index()
    proxies: dict[str, pd.DataFrame] = {}
    rows: list[dict[str, Any]] = []
    for product_vt_symbol, files in file_index.items():
        exchange = product_vt_symbol.split(".")[-1]
        product = product_vt_symbol.rsplit(".", 1)[0]
        proxy, summary = _load_product_proxy(product_vt_symbol, files)
        proxies[product_vt_symbol] = proxy
        known = meta.get(product_vt_symbol, {})
        family = str(known.get("product_family", "") or FALLBACK_PRODUCT_FAMILY.get(product_vt_symbol, ("unknown", ""))[0])
        family_note = str(known.get("family_note", "") or FALLBACK_PRODUCT_FAMILY.get(product_vt_symbol, ("", "未分类"))[1])
        row = {
            **summary,
            "exchange": exchange,
            "product": product,
            "product_family": family,
            "family_note": family_note,
            "stage602_status": str(known.get("full57_status", "")),
            "stage602_slot_judgement": str(known.get("slot_judgement", "")),
            "stage602_source_rich": int(float(known.get("source_rich", 0) or 0)),
            "stage602_positive_material": int(float(known.get("positive_material", 0) or 0)),
            "stage602_low_corr_pass": int(float(known.get("low_corr_pass", 0) or 0)),
            "stage602_deployable_new_slot_now": int(float(known.get("deployable_new_slot_now", 0) or 0)),
            "stage602_whitelist_allowed": int(float(known.get("whitelist_allowed", 0) or 0)),
            "is_p0_product": int(product_vt_symbol in p0_products),
            "is_current_slot_family": int(family in current_families),
            "is_p1_family": int(family in p1_families),
            "is_p2_family": int(family in p2_families),
        }
        rows.append(row)

    local = pd.DataFrame(rows).sort_values(["exchange", "product"]).reset_index(drop=True)
    close_parts = []
    for product_vt_symbol, proxy in proxies.items():
        if proxy.empty:
            continue
        series = proxy.set_index("trade_date")["close"].sort_index()
        close_parts.append(series.rename(product_vt_symbol))
    close = pd.concat(close_parts, axis=1).sort_index()
    returns = np.log(close).diff().replace([np.inf, -np.inf], np.nan)
    corr = returns.corr(min_periods=MIN_CORR_OVERLAP_DAYS)
    components = _corr_components(corr.fillna(0.0))

    p0_available = [item for item in p0_products if item in returns.columns]
    core_composite = returns[p0_available].mean(axis=1, skipna=True) if p0_available else pd.Series(index=returns.index, dtype=float)
    tail_threshold = core_composite.abs().quantile(0.90) if core_composite.notna().sum() else np.nan
    tail_core = core_composite[core_composite.abs().ge(tail_threshold)] if pd.notna(tail_threshold) else pd.Series(dtype=float)

    corr_rows = []
    trend_rows = []
    for product_vt_symbol in local["product_vt_symbol"]:
        product_return = returns.get(product_vt_symbol, pd.Series(index=returns.index, dtype=float))
        p0_corrs = [_safe_corr(product_return, returns[item]) for item in p0_available if item != product_vt_symbol]
        p0_corrs = [item for item in p0_corrs if pd.notna(item)]
        corr_to_core = _safe_corr(product_return, core_composite)
        tail_corr = _safe_corr(product_return.loc[tail_core.index], tail_core, min_overlap=60) if not tail_core.empty else np.nan
        rolling_p75 = _rolling_abs_corr_p75(product_return, core_composite)
        corr_rows.append(
            {
                "product_vt_symbol": product_vt_symbol,
                "max_abs_corr_to_p0": float(np.nanmax(np.abs(p0_corrs))) if p0_corrs else np.nan,
                "avg_abs_corr_to_p0": float(np.nanmean(np.abs(p0_corrs))) if p0_corrs else np.nan,
                "corr_to_p0_composite": corr_to_core,
                "tail_abs_corr_to_p0_composite": abs(tail_corr) if pd.notna(tail_corr) else np.nan,
                "rolling_abs_corr_p75_to_p0": rolling_p75,
                "corr_component_id": int(components.get(product_vt_symbol, 0)),
            }
        )
        close_series = close.get(product_vt_symbol, pd.Series(index=close.index, dtype=float))
        trend_rows.append({"product_vt_symbol": product_vt_symbol, **_trend_opportunity_stats(close_series)})

    product = (
        local.merge(pd.DataFrame(corr_rows), on="product_vt_symbol", how="left")
        .merge(pd.DataFrame(trend_rows), on="product_vt_symbol", how="left")
        .reset_index(drop=True)
    )
    max_last_tradable = pd.to_datetime(product["last_tradable_date"], errors="coerce").max()
    product["days_behind_latest_tradable"] = (
        max_last_tradable - pd.to_datetime(product["last_tradable_date"], errors="coerce")
    ).dt.days.fillna(9999).astype(int)
    product["data_pass"] = (
        product["tradable_rows"].ge(MIN_TRADABLE_ROWS)
        & product["recent_tradable_days"].ge(MIN_RECENT_TRADABLE_DAYS)
        & product["days_behind_latest_tradable"].le(45)
    ).astype(int)
    product["liquidity_pass"] = product["recent_median_volume"].ge(MIN_RECENT_MEDIAN_VOLUME).astype(int)
    product["low_corr_pass"] = (
        product["max_abs_corr_to_p0"].fillna(1.0).le(LOW_CORR_MAX_TO_P0)
        & product["tail_abs_corr_to_p0_composite"].fillna(1.0).le(LOW_TAIL_CORR_TO_CORE)
        & product["rolling_abs_corr_p75_to_p0"].fillna(1.0).le(LOW_ROLLING_CORR_P75)
    ).astype(int)
    product["watch_corr_pass"] = (
        product["max_abs_corr_to_p0"].fillna(1.0).le(WATCH_CORR_MAX_TO_P0)
        & product["tail_abs_corr_to_p0_composite"].fillna(1.0).le(WATCH_TAIL_CORR_TO_CORE)
    ).astype(int)
    product["trend_opportunity_pass"] = (
        product["trend_years"].ge(TREND_MIN_YEARS)
        & product["trend_year_rate_pct"].ge(40.0)
    ).astype(int)
    product["commodity_scope"] = product["exchange"].ne("CFFEX").astype(int)
    buckets = product.apply(lambda row: _classify(row, p0_products, current_families, p1_families, p2_families), axis=1)
    product["structural_bucket"] = [item[0] for item in buckets]
    product["action_reason"] = [item[1] for item in buckets]
    product["structural_score"] = (
        0.20 * product["data_pass"]
        + 0.20 * product["liquidity_pass"]
        + 0.25 * product["low_corr_pass"]
        + 0.10 * product["watch_corr_pass"]
        + 0.20 * product["trend_opportunity_pass"]
        + 0.05 * product["stage602_source_rich"]
    )
    product["deployable_new_slot_now"] = 0
    product["paper_allowed_now"] = 0
    product["trading_whitelist_allowed_now"] = 0
    product = product.sort_values(
        ["structural_bucket", "structural_score", "trend_years", "recent_median_volume"],
        ascending=[True, False, False, False],
    ).reset_index(drop=True)
    return product, corr, family_admission


def _build_family_map(product: pd.DataFrame, family_admission: pd.DataFrame) -> pd.DataFrame:
    admission = family_admission.copy()
    admission["product_family"] = _str(admission, "product_family")
    admission_lookup = admission.set_index("product_family").to_dict("index") if not admission.empty else {}
    rows: list[dict[str, Any]] = []
    for family, group in product.groupby("product_family"):
        ranked = group.sort_values(["structural_score", "trend_years", "recent_median_volume"], ascending=False)
        best = ranked.iloc[0]
        buckets = group["structural_bucket"].value_counts().to_dict()
        known = admission_lookup.get(family, {})
        structural_new_count = int(group["structural_bucket"].eq("new_structural_monitor_candidate").sum())
        p1_count = int(group["structural_bucket"].eq("p1_existing_worklist_source_tca_blocked").sum())
        p2_count = int(group["structural_bucket"].eq("p2_existing_forward_monitor").sum())
        rows.append(
            {
                "product_family": family,
                "products": ",".join(group["product_vt_symbol"].tolist()),
                "product_count": int(len(group)),
                "best_structural_product": best["product_vt_symbol"],
                "best_structural_score": float(best["structural_score"]),
                "data_pass_count": int(group["data_pass"].sum()),
                "liquidity_pass_count": int(group["liquidity_pass"].sum()),
                "low_corr_pass_count": int(group["low_corr_pass"].sum()),
                "watch_corr_pass_count": int(group["watch_corr_pass"].sum()),
                "trend_opportunity_pass_count": int(group["trend_opportunity_pass"].sum()),
                "structural_new_monitor_candidates": structural_new_count,
                "p1_worklist_products": p1_count,
                "p2_monitor_products": p2_count,
                "max_best_core_corr": float(ranked["max_abs_corr_to_p0"].iloc[0]) if pd.notna(ranked["max_abs_corr_to_p0"].iloc[0]) else np.nan,
                "best_tail_corr": float(ranked["tail_abs_corr_to_p0_composite"].iloc[0]) if pd.notna(ranked["tail_abs_corr_to_p0_composite"].iloc[0]) else np.nan,
                "stage611_admission_bucket": str(known.get("admission_bucket", "")),
                "stage611_deployable_now": int(float(known.get("deployable_now", 0) or 0)) if known else 0,
                "family_bucket_counts": json.dumps(buckets, ensure_ascii=False, sort_keys=True),
                "deployable_new_slot_now": 0,
                "paper_allowed_now": 0,
                "trading_whitelist_allowed_now": 0,
            }
        )
    family = pd.DataFrame(rows).sort_values(
        ["structural_new_monitor_candidates", "p1_worklist_products", "p2_monitor_products", "best_structural_score"],
        ascending=False,
    ).reset_index(drop=True)
    return family


def _build_gates(product: pd.DataFrame, family: pd.DataFrame) -> pd.DataFrame:
    deployable = int(product["deployable_new_slot_now"].sum())
    paper = int(product["paper_allowed_now"].sum())
    whitelist = int(product["trading_whitelist_allowed_now"].sum())
    structural_new_families = int(family["structural_new_monitor_candidates"].gt(0).sum())
    p1_families = int(family["p1_worklist_products"].gt(0).sum())
    p2_families = int(family["p2_monitor_products"].gt(0).sum())
    data_pass_products = int(product["data_pass"].sum())
    low_corr_products = int(product["low_corr_pass"].sum())
    rows = [
        {
            "gate": "local_daily_files_loaded",
            "passed": int(len(product) >= 50),
            "current": len(product),
            "required": ">=50 products",
            "note": "Stage633 reads all local TQSDK product roots.",
        },
        {
            "gate": "p0_reference_products_present",
            "passed": int(product["is_p0_product"].sum() >= 5),
            "current": int(product["is_p0_product"].sum()),
            "required": ">=5",
            "note": "P0 reference products must exist before correlation audit.",
        },
        {
            "gate": "data_pass_products_documented",
            "passed": int(data_pass_products > 0),
            "current": data_pass_products,
            "required": ">0",
            "note": "Coverage/liquidity gates are documented.",
        },
        {
            "gate": "low_corr_products_documented",
            "passed": int(low_corr_products > 0),
            "current": low_corr_products,
            "required": ">0",
            "note": "Low-correlation products exist structurally, but not necessarily deployable.",
        },
        {
            "gate": "structural_new_monitor_candidates_only",
            "passed": int(structural_new_families >= 0),
            "current": structural_new_families,
            "required": "tracked",
            "note": "New candidates are monitor-only until source/TCA/outcome gates pass.",
        },
        {
            "gate": "p1_p2_worklists_preserved",
            "passed": int(p1_families >= 1 and p2_families >= 2),
            "current": f"P1={p1_families},P2={p2_families}",
            "required": "P1>=1,P2>=2",
            "note": "Existing black_ferrous P1 and precious/soft P2 worklists remain visible.",
        },
        {
            "gate": "deployable_new_slots_zero",
            "passed": int(deployable == 0),
            "current": deployable,
            "required": 0,
            "note": "No new product is promoted to deployable selector slot.",
        },
        {
            "gate": "paper_and_whitelist_zero",
            "passed": int(paper == 0 and whitelist == 0),
            "current": f"paper={paper},whitelist={whitelist}",
            "required": "0/0",
            "note": "No paper or trading whitelist is generated.",
        },
        {
            "gate": "target_7_slots_not_met_fail_closed",
            "passed": int(CURRENT_EFFECTIVE_SLOTS < TARGET_EFFECTIVE_SLOTS and deployable == 0),
            "current": CURRENT_EFFECTIVE_SLOTS,
            "required": TARGET_EFFECTIVE_SLOTS,
            "note": "Current deployable effective slots still fail the target; keep budget locked.",
        },
    ]
    return pd.DataFrame(rows)


def _write_chart(product: pd.DataFrame, family: pd.DataFrame, corr: pd.DataFrame, gates: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(17, 11))
    fig.suptitle("Stage633 independent risk slot correlation map: structure first, no whitelist", fontsize=16)

    ax = axes[0, 0]
    family_view = family.head(12).copy()
    x = np.arange(len(family_view))
    ax.bar(x - 0.25, family_view["data_pass_count"], width=0.25, label="data pass")
    ax.bar(x, family_view["low_corr_pass_count"], width=0.25, label="low corr")
    ax.bar(x + 0.25, family_view["trend_opportunity_pass_count"], width=0.25, label="trend proxy")
    ax.set_xticks(x)
    ax.set_xticklabels(family_view["product_family"], rotation=45, ha="right")
    ax.set_title("Family structural qualification counts")
    ax.set_ylabel("products")
    ax.legend(loc="upper right", fontsize=8)

    ax = axes[0, 1]
    scatter = product[product["commodity_scope"].eq(1)].copy()
    bucket_colors = {
        "p0_reference_existing_slot": "#2b6cb0",
        "same_family_depth_not_slot": "#68d391",
        "p1_existing_worklist_source_tca_blocked": "#ed8936",
        "p2_existing_forward_monitor": "#9f7aea",
        "new_structural_monitor_candidate": "#38a169",
        "reject_high_core_corr": "#e53e3e",
        "reject_data_or_liquidity": "#4a5568",
        "observe_low_corr_but_weak_trend": "#a0aec0",
        "observe_only": "#cbd5e0",
    }
    colors = scatter["structural_bucket"].map(bucket_colors).fillna("#cbd5e0")
    sizes = 20 + scatter["trend_years"].fillna(0).astype(float) * 12
    ax.scatter(scatter["max_abs_corr_to_p0"], scatter["trend_years"], s=sizes, c=colors, alpha=0.78, edgecolor="white", linewidth=0.5)
    ax.axvline(LOW_CORR_MAX_TO_P0, color="tab:green", linestyle="--", linewidth=1, label="low corr 0.10")
    ax.axvline(WATCH_CORR_MAX_TO_P0, color="tab:orange", linestyle="--", linewidth=1, label="watch 0.15")
    ax.set_title("Product map: core correlation vs trend opportunity years")
    ax.set_xlabel("max abs corr to P0 products")
    ax.set_ylabel("trend opportunity years")
    ax.set_ylim(0.5, max(10.5, float(scatter["trend_years"].max()) + 1.4))
    ax.legend(loc="upper right", fontsize=8)
    label_products = [
        "rr.DCE",
        "PM.CZCE",
        "CJ.CZCE",
        "au.SHFE",
        "lh.DCE",
        "i.DCE",
        "SR.CZCE",
        "CY.CZCE",
        "bu.SHFE",
        "TA.CZCE",
    ]
    labels = scatter[scatter["product_vt_symbol"].isin(label_products)].copy()
    for offset, (_, row) in enumerate(labels.iterrows()):
        dy = 0.10 + (offset % 4) * 0.16
        ax.text(row["max_abs_corr_to_p0"], row["trend_years"] + dy, row["product_vt_symbol"], fontsize=7)

    ax = axes[1, 0]
    selected_products = []
    for bucket in [
        "p0_reference_existing_slot",
        "p1_existing_worklist_source_tca_blocked",
        "p2_existing_forward_monitor",
        "new_structural_monitor_candidate",
        "observe_low_corr_but_weak_trend",
    ]:
        selected_products.extend(product.loc[product["structural_bucket"].eq(bucket), "product_vt_symbol"].head(4).tolist())
    selected_products = list(dict.fromkeys([item for item in selected_products if item in corr.index]))[:18]
    if selected_products:
        heat = corr.loc[selected_products, selected_products].fillna(0.0)
        image = ax.imshow(heat.values, cmap="coolwarm", vmin=-1, vmax=1, aspect="auto")
        ax.set_xticks(np.arange(len(selected_products)))
        ax.set_xticklabels(selected_products, rotation=60, ha="right", fontsize=7)
        ax.set_yticks(np.arange(len(selected_products)))
        ax.set_yticklabels(selected_products, fontsize=7)
        ax.set_title("Correlation matrix: P0/P1/P2/new monitor candidates")
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    else:
        ax.text(0.5, 0.5, "No selected products", ha="center", va="center")
        ax.set_axis_off()

    ax = axes[1, 1]
    colors = ["tab:green" if int(item) == 1 else "tab:red" for item in gates["passed"]]
    ax.barh(gates["gate"], gates["passed"], color=colors)
    ax.set_xlim(0, 1)
    ax.set_title("Hard gates: green includes fail-closed locks")
    ax.tick_params(axis="y", labelsize=8)
    for i, row in gates.iterrows():
        ax.text(0.02, i, str(row["current"]), va="center", ha="left", fontsize=8, color="white")

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    generated_at: datetime,
    product: pd.DataFrame,
    family: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage633 Independent Risk Slot Correlation Map Report",
        "",
        f"- generated_at_cst: `{_fmt_cst(generated_at)}`",
        f"- decision: `{decision['decision']}`",
        f"- tq_sdk_daily_root: `{TQSDK_DAILY_ROOT}`",
        "",
        "## External Research Judgement",
        "",
        "扩池的第一性原理不是增加产品数量，而是增加独立风险来源。Managed futures 的分散价值来自跨市场、低相关、可双向跟随趋势；HRP/HERC/cluster risk parity 的共同点是先识别相关结构，再分配风险。因此本阶段只做价格覆盖、流动性、P0相关性、尾部相关性和趋势机会代理审计，不使用策略收益排名生成白名单。",
        "",
        "References:",
        *[f"- {item}" for item in REFERENCES],
        "",
        "## Key Numbers",
        "",
        f"- local product roots: `{decision['local_product_roots']}`",
        f"- data pass products: `{decision['data_pass_products']}`",
        f"- liquidity pass products: `{decision['liquidity_pass_products']}`",
        f"- low corr pass products: `{decision['low_corr_pass_products']}`",
        f"- watch corr pass products: `{decision['watch_corr_pass_products']}`",
        f"- trend opportunity pass products: `{decision['trend_opportunity_pass_products']}`",
        f"- new structural monitor products: `{decision['new_structural_monitor_products']}`",
        f"- new structural monitor families: `{decision['new_structural_monitor_families']}`",
        f"- deployable new slots now: `{decision['deployable_new_slots_now']}`",
        f"- paper rows: `{decision['paper_rows']}`",
        f"- trading whitelist rows: `{decision['trading_whitelist_rows']}`",
        f"- hard gates: `{decision['hard_gates_passed']}/{decision['hard_gates_total']}`",
        "",
        "## Family Map",
        "",
        _md_table(
            family,
            columns=[
                "product_family",
                "product_count",
                "best_structural_product",
                "best_structural_score",
                "data_pass_count",
                "low_corr_pass_count",
                "trend_opportunity_pass_count",
                "structural_new_monitor_candidates",
                "p1_worklist_products",
                "p2_monitor_products",
                "deployable_new_slot_now",
            ],
        ),
        "",
        "## Top Product Structure",
        "",
        _md_table(
            product.sort_values(["structural_score", "trend_years"], ascending=False),
            columns=[
                "product_vt_symbol",
                "product_family",
                "exchange",
                "structural_bucket",
                "structural_score",
                "tradable_rows",
                "last_tradable_date",
                "recent_median_volume",
                "max_abs_corr_to_p0",
                "tail_abs_corr_to_p0_composite",
                "rolling_abs_corr_p75_to_p0",
                "trend_years",
                "trend_year_rate_pct",
                "action_reason",
            ],
            max_rows=30,
        ),
        "",
        "## New Structural Monitor Candidates",
        "",
        _md_table(
            product[product["structural_bucket"].eq("new_structural_monitor_candidate")],
            columns=[
                "product_vt_symbol",
                "product_family",
                "exchange",
                "structural_score",
                "max_abs_corr_to_p0",
                "tail_abs_corr_to_p0_composite",
                "trend_years",
                "recent_median_volume",
                "action_reason",
            ],
        ),
        "",
        "## Gates",
        "",
        _md_table(gates),
        "",
        "## Interpretation",
        "",
        "- 本阶段没有产生任何 deployable selector slot、paper 或交易白名单。",
        "- 新结构候选即使存在，也只代表相关性/价格结构值得做 source/TCA/outcome monitor，不代表可交易收益。",
        "- 当前目标仍是从 4 个有效槽推进到 7 个有效槽；未闭合 source、TCA、真实执行和 outcome 前，单槽风险不能实际降到目标。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    generated_at = _now_cst()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    product, corr, family_admission = _build_product_map()
    family = _build_family_map(product, family_admission)
    gates = _build_gates(product, family)

    new_monitor = product[product["structural_bucket"].eq("new_structural_monitor_candidate")]
    decision = {
        "decision": "risk_slot_correlation_map_built_no_new_deployable_slot",
        "generated_at_cst": _fmt_cst(generated_at),
        "line_id": LINE_ID,
        "local_product_roots": int(len(product)),
        "data_pass_products": int(product["data_pass"].sum()),
        "liquidity_pass_products": int(product["liquidity_pass"].sum()),
        "low_corr_pass_products": int(product["low_corr_pass"].sum()),
        "watch_corr_pass_products": int(product["watch_corr_pass"].sum()),
        "trend_opportunity_pass_products": int(product["trend_opportunity_pass"].sum()),
        "new_structural_monitor_products": int(len(new_monitor)),
        "new_structural_monitor_families": int(new_monitor["product_family"].nunique()) if not new_monitor.empty else 0,
        "p1_worklist_products": int(product["structural_bucket"].eq("p1_existing_worklist_source_tca_blocked").sum()),
        "p2_monitor_products": int(product["structural_bucket"].eq("p2_existing_forward_monitor").sum()),
        "deployable_new_slots_now": int(product["deployable_new_slot_now"].sum()),
        "paper_rows": int(product["paper_allowed_now"].sum()),
        "trading_whitelist_rows": int(product["trading_whitelist_allowed_now"].sum()),
        "current_effective_slots": CURRENT_EFFECTIVE_SLOTS,
        "target_effective_slots": TARGET_EFFECTIVE_SLOTS,
        "hard_gates_passed": int(gates["passed"].sum()),
        "hard_gates_total": int(len(gates)),
        "product_map_path": str(PRODUCT_MAP_PATH),
        "family_map_path": str(FAMILY_MAP_PATH),
        "corr_matrix_path": str(CORR_MATRIX_PATH),
        "chart_path": str(CHART_PATH),
    }

    product.to_csv(PRODUCT_MAP_PATH, index=False, encoding="utf-8-sig")
    family.to_csv(FAMILY_MAP_PATH, index=False, encoding="utf-8-sig")
    corr.to_csv(CORR_MATRIX_PATH, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_report(generated_at, product, family, gates, decision)
    _write_chart(product, family, corr, gates)
    print(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
