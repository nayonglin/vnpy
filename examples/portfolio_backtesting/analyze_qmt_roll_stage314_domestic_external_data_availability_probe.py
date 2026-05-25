from __future__ import annotations

import json
import multiprocessing as mp
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_VERSION
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage314_domestic_external_data_availability_probe_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage314_domestic_external_data_availability_probe"
LINE_ID: str = "futures_trend_drawdown30_preserve_return"

STAGE78_CANDIDATE_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_official_stage78_defensive_formal_entry_candidate_snapshots_2020_2026_04.csv"
)

SOURCE_CHECK_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_checks_{MODEL_TAG}.csv"
PRODUCT_COVERAGE_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_coverage_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

DEFAULT_TIMEOUT_SECONDS: int = 35


@dataclass(frozen=True)
class SourceCheck:
    source_id: str
    family: str
    source_name: str
    exchange: str
    products: tuple[str, ...]
    function_name: str
    kwargs: dict[str, Any]
    source_url: str
    point_in_time_rule: str
    feature_hypothesis: str
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS


SOURCE_CHECKS: tuple[SourceCheck, ...] = (
    SourceCheck(
        source_id="member_rank_shfe",
        family="member_rank",
        source_name="上期所会员成交持仓排名",
        exchange="SHFE",
        products=("RB", "RU", "FU", "AU", "CU", "HC", "SP"),
        function_name="get_shfe_rank_table",
        kwargs={"date": "20240102", "vars_list": ["RB", "RU", "FU", "AU", "CU", "HC", "SP"]},
        source_url="https://tsite.shfe.com.cn/statements/dataview.html?paramid=kx",
        point_in_time_rule="交易日16:30左右更新；只能用于下一交易日及之后的候选。",
        feature_hypothesis="前20会员多空净持仓、净持仓变化、集中度变化可作为开仓质量过滤或手数倍率。",
    ),
    SourceCheck(
        source_id="member_rank_czce",
        family="member_rank",
        source_name="郑商所会员成交持仓排名",
        exchange="CZCE",
        products=("AP", "CF", "FG", "MA", "OI", "SA", "SH", "SM"),
        function_name="get_rank_table_czce",
        kwargs={"date": "20240102"},
        source_url="https://www.czce.com.cn/cn/jysj/ccpm/H077003004index_1.htm",
        point_in_time_rule="官网说明当日数据需在收市结算完成后生成；只能用于下一交易日及之后的候选。",
        feature_hypothesis="前20会员多空净持仓、净持仓变化、成交集中度可作为国内盘开仓质量因子。",
    ),
    SourceCheck(
        source_id="member_rank_gfex",
        family="member_rank",
        source_name="广期所日成交持仓排名",
        exchange="GFEX",
        products=("LC", "SI"),
        function_name="futures_gfex_position_rank",
        kwargs={"date": "20240122", "vars_list": ["LC", "SI"]},
        source_url="https://www.gfex.com.cn/gfex/rcjccpm/hqsj_tjsj.shtml",
        point_in_time_rule="收市结算后生成；只能用于下一交易日及之后的候选。",
        feature_hypothesis="新能源金属会员多空变化可作为碳酸锂/工业硅趋势开仓质量参考。",
    ),
    SourceCheck(
        source_id="member_rank_dce",
        family="member_rank",
        source_name="大商所会员持仓排名",
        exchange="DCE",
        products=("JM", "LH"),
        function_name="futures_dce_position_rank",
        kwargs={"date": "20240102", "vars_list": ["JM", "LH"]},
        source_url="http://www.dce.com.cn/dalianshangpin/xqsj/tjsj26/rtj/rcjccpm/index.html",
        point_in_time_rule="收市结算后生成；只能用于下一交易日及之后的候选。",
        feature_hypothesis="焦煤/生猪会员多空变化可能比外盘COT更贴近国内供需和资金结构。",
    ),
    SourceCheck(
        source_id="warehouse_shfe",
        family="warehouse_receipt",
        source_name="上期所仓单日报",
        exchange="SHFE",
        products=("RB", "RU", "FU", "AU", "CU", "HC", "SP"),
        function_name="futures_shfe_warehouse_receipt",
        kwargs={"date": "20240102"},
        source_url="https://tsite.shfe.com.cn/statements/dataview.html?paramid=dailystock",
        point_in_time_rule="仓单日报发布后才可用；只用于下一交易日及之后。",
        feature_hypothesis="仓单趋势和仓单变化可解释库存压力，辅助过滤追涨追空质量。",
    ),
    SourceCheck(
        source_id="warehouse_czce",
        family="warehouse_receipt",
        source_name="郑商所仓单日报",
        exchange="CZCE",
        products=("AP", "CF", "FG", "MA", "OI", "SA", "SH", "SM"),
        function_name="futures_warehouse_receipt_czce",
        kwargs={"date": "20240102"},
        source_url="http://www.czce.com.cn/cn/jysj/cdrb/H770310index_1.htm",
        point_in_time_rule="仓单日报发布后才可用；只用于下一交易日及之后。",
        feature_hypothesis="仓单变化可作为供需压力和逼仓风险的低自由度代理。",
    ),
    SourceCheck(
        source_id="warehouse_gfex",
        family="warehouse_receipt",
        source_name="广期所仓单日报",
        exchange="GFEX",
        products=("LC", "SI"),
        function_name="futures_gfex_warehouse_receipt",
        kwargs={"date": "20240122"},
        source_url="http://www.gfex.com.cn/gfex/cdrb/hqsj_tjsj.shtml",
        point_in_time_rule="仓单日报发布后才可用；只用于下一交易日及之后。",
        feature_hypothesis="碳酸锂/工业硅仓单变化可作为库存压力和趋势持续性辅助指标。",
    ),
    SourceCheck(
        source_id="warehouse_dce",
        family="warehouse_receipt",
        source_name="大商所仓单日报",
        exchange="DCE",
        products=("JM", "LH"),
        function_name="futures_warehouse_receipt_dce",
        kwargs={"date": "20240102"},
        source_url="http://www.dce.com.cn/dce/channel/list/187.html",
        point_in_time_rule="仓单日报发布后才可用；只用于下一交易日及之后。",
        feature_hypothesis="仓单变化可作为库存压力辅助指标，但焦煤/生猪适配度需要单独确认。",
    ),
    SourceCheck(
        source_id="basis_100ppi",
        family="spot_basis",
        source_name="生意社现货与基差",
        exchange="ALL",
        products=("RB", "RU", "FU", "AU", "CU", "HC", "SP", "JM", "LH", "AP", "CF", "FG", "MA", "OI", "SA", "SH", "SM", "LC", "SI"),
        function_name="futures_spot_price",
        kwargs={
            "date": "20240102",
            "vars_list": ["RB", "RU", "FU", "AU", "CU", "HC", "SP", "JM", "LH", "AP", "CF", "FG", "MA", "OI", "SA", "SH", "SM", "LC", "SI"],
        },
        source_url="https://www.100ppi.com/sf/",
        point_in_time_rule="第三方现货/基差数据，必须按实际发布时间保守滞后到下一交易日使用。",
        feature_hypothesis="基差水平、基差变化和期限结构可辅助判断趋势是否被现货端确认。",
    ),
)


def _product_code(product_vt_symbol: str) -> str:
    return product_vt_symbol.split(".", 1)[0].upper()


def _exchange(product_vt_symbol: str) -> str:
    if "." not in product_vt_symbol:
        return ""
    return product_vt_symbol.split(".", 1)[1].upper()


def _load_stage78_products() -> pd.DataFrame:
    if not STAGE78_CANDIDATE_PATH.exists():
        raise FileNotFoundError(STAGE78_CANDIDATE_PATH)
    candidates = pd.read_csv(STAGE78_CANDIDATE_PATH, usecols=["product_vt_symbol"])
    products = (
        candidates["product_vt_symbol"]
        .dropna()
        .astype(str)
        .drop_duplicates()
        .sort_values()
        .reset_index(drop=True)
    )
    return pd.DataFrame(
        {
            "product_vt_symbol": products,
            "product_code": products.map(_product_code),
            "exchange": products.map(_exchange),
        }
    )


def _summarize_result(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        frame_shapes: list[dict[str, Any]] = []
        total_rows = 0
        for key, value in result.items():
            shape = getattr(value, "shape", None)
            rows = int(shape[0]) if shape else 0
            total_rows += rows
            columns = list(value.columns) if hasattr(value, "columns") else []
            frame_shapes.append(
                {
                    "key": str(key),
                    "rows": rows,
                    "columns": columns[:12],
                }
            )
        return {
            "result_type": "dict",
            "frames": len(result),
            "rows": total_rows,
            "sample_keys": [str(key) for key in list(result.keys())[:10]],
            "sample_frames": frame_shapes[:5],
        }
    if isinstance(result, pd.DataFrame):
        return {
            "result_type": "dataframe",
            "frames": 1,
            "rows": int(len(result)),
            "columns": list(result.columns)[:16],
            "sample_symbols": sorted(result["symbol"].astype(str).unique().tolist())[:20]
            if "symbol" in result.columns
            else [],
        }
    return {
        "result_type": type(result).__name__,
        "frames": 0,
        "rows": 0,
        "repr": repr(result)[:500],
    }


def _akshare_worker(function_name: str, kwargs: dict[str, Any], queue: mp.Queue) -> None:
    try:
        import akshare as ak

        result = getattr(ak, function_name)(**kwargs)
        queue.put({"status": "ok", "summary": _summarize_result(result)})
    except Exception as exc:  # pragma: no cover - network/data source probe
        queue.put(
            {
                "status": "error",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "traceback_tail": traceback.format_exc().splitlines()[-5:],
            }
        )


def _run_source_check(check: SourceCheck) -> dict[str, Any]:
    ctx = mp.get_context("fork")
    queue: mp.Queue = ctx.Queue()
    process = ctx.Process(target=_akshare_worker, args=(check.function_name, check.kwargs, queue))
    process.start()
    process.join(check.timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join(5)
        payload: dict[str, Any] = {
            "status": "timeout",
            "error_type": "Timeout",
            "error_message": f"timeout_after_{check.timeout_seconds}s",
            "summary": {},
        }
    elif queue.empty():
        payload = {
            "status": "empty",
            "error_type": "NoResult",
            "error_message": "worker exited without result",
            "summary": {},
        }
    else:
        payload = queue.get()

    summary = payload.get("summary", {}) or {}
    return {
        **asdict(check),
        "products": ",".join(check.products),
        "status": payload.get("status", ""),
        "rows": int(summary.get("rows", 0) or 0),
        "frames": int(summary.get("frames", 0) or 0),
        "result_type": summary.get("result_type", ""),
        "sample_keys": json.dumps(summary.get("sample_keys", []), ensure_ascii=False),
        "sample_symbols": json.dumps(summary.get("sample_symbols", []), ensure_ascii=False),
        "sample_frames": json.dumps(summary.get("sample_frames", []), ensure_ascii=False),
        "error_type": payload.get("error_type", ""),
        "error_message": payload.get("error_message", ""),
        "usable_for_stage015": int(payload.get("status") == "ok" and int(summary.get("rows", 0) or 0) > 0),
    }


def _build_product_coverage(products: pd.DataFrame, checks_df: pd.DataFrame) -> pd.DataFrame:
    usable = checks_df[checks_df["usable_for_stage015"].astype(int).eq(1)].copy()
    rows: list[dict[str, Any]] = []
    for record in products.to_dict("records"):
        code = str(record["product_code"])
        exchange = str(record["exchange"])
        product_checks = usable[
            (usable["exchange"].isin([exchange, "ALL"]))
            & (usable["products"].astype(str).str.split(",").map(lambda items: code in items))
        ]
        families = sorted(product_checks["family"].dropna().astype(str).unique().tolist())
        source_ids = sorted(product_checks["source_id"].dropna().astype(str).unique().tolist())
        rows.append(
            {
                "product_vt_symbol": record["product_vt_symbol"],
                "product_code": code,
                "exchange": exchange,
                "usable_source_families": ",".join(families),
                "usable_source_count": len(source_ids),
                "member_rank_available": int("member_rank" in families),
                "warehouse_receipt_available": int("warehouse_receipt" in families),
                "spot_basis_available": int("spot_basis" in families),
                "recommended_first_probe": (
                    "member_rank_net_delta"
                    if "member_rank" in families
                    else "warehouse_or_basis_delta"
                    if ("warehouse_receipt" in families or "spot_basis" in families)
                    else "data_missing"
                ),
                "source_ids": ",".join(source_ids),
            }
        )
    return pd.DataFrame(rows)


def _decision(checks_df: pd.DataFrame, product_coverage: pd.DataFrame) -> str:
    covered_products = int((product_coverage["usable_source_count"] > 0).sum())
    member_rank_products = int(product_coverage["member_rank_available"].sum())
    if covered_products == 0:
        return "domestic_external_data_not_ready"
    if member_rank_products >= 10:
        return "domestic_member_rank_data_layer_ready_for_feature_build"
    return "domestic_external_data_partially_ready_need_source_specific_feature_build"


def _build_report(
    checks_df: pd.DataFrame,
    product_coverage: pd.DataFrame,
    decision: str,
) -> str:
    available = checks_df[checks_df["usable_for_stage015"].astype(int).eq(1)].copy()
    unavailable = checks_df[~checks_df["usable_for_stage015"].astype(int).eq(1)].copy()
    rows = [
        "# Stage314 国内外生数据可得性探针",
        "",
        "## 本阶段定位",
        "",
        "- 目标不是直接新增交易规则，而是找出哪些外生数据能点时化接入第78-1开仓候选。",
        "- 优先级高于 COT 的，是国内交易所会员持仓、仓单/库存和基差，因为它们更贴近中国盘。",
        "- 本阶段只检查数据可得性和产品覆盖，不做收益回测，不改78-1。",
        "",
        "## 可用数据源",
        "",
        to_markdown_table(available[[
            "source_id",
            "family",
            "source_name",
            "exchange",
            "products",
            "rows",
            "frames",
            "point_in_time_rule",
        ]])
        if not available.empty
        else "没有可用数据源。",
        "",
        "## 暂不可用或需修复的数据源",
        "",
        to_markdown_table(unavailable[[
            "source_id",
            "family",
            "source_name",
            "exchange",
            "products",
            "status",
            "error_type",
            "error_message",
        ]])
        if not unavailable.empty
        else "全部探针可用。",
        "",
        "## 第78-1品种覆盖",
        "",
        to_markdown_table(product_coverage),
        "",
        "## 判定",
        "",
        f"- `{decision}`",
        "",
        "## 下一步",
        "",
        "- 第一优先级：会员持仓净变化因子，不先碰舆情文本。",
        "- 第二优先级：仓单/库存变化因子。",
        "- 第三优先级：基差/期限结构因子。",
        "- 每个因子都必须先生成 `available_datetime`，沿用 Stage013 评估器做 valid/test 分桶；分桶不过，不进入 A/C 回测。",
    ]
    return "\n".join(rows) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    products = _load_stage78_products()
    check_rows = [_run_source_check(check) for check in SOURCE_CHECKS]
    checks_df = pd.DataFrame(check_rows)
    product_coverage = _build_product_coverage(products, checks_df)
    decision = _decision(checks_df, product_coverage)

    checks_df.to_csv(SOURCE_CHECK_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    product_coverage.to_csv(PRODUCT_COVERAGE_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    REPORT_PATH.write_text(_build_report(checks_df, product_coverage, decision), encoding="utf-8")
    summary = {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "base_version": OFFICIAL_STAGE78_VERSION,
        "analysis_type": "domestic_external_data_availability_probe_no_strategy_backtest",
        "decision": decision,
        "source_checks": check_rows,
        "product_coverage_rows": product_coverage.to_dict("records"),
        "usable_source_count": int(checks_df["usable_for_stage015"].sum()),
        "covered_product_count": int((product_coverage["usable_source_count"] > 0).sum()),
        "member_rank_product_count": int(product_coverage["member_rank_available"].sum()),
        "warehouse_product_count": int(product_coverage["warehouse_receipt_available"].sum()),
        "spot_basis_product_count": int(product_coverage["spot_basis_available"].sum()),
        "outputs": {
            "source_checks": str(SOURCE_CHECK_OUTPUT_PATH),
            "product_coverage": str(PRODUCT_COVERAGE_OUTPUT_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
