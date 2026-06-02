from __future__ import annotations

from datetime import datetime
import json
import math
import multiprocessing as mp
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage546_external_state_noncore_coverage_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage546_external_state_noncore_coverage_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE543_TAG = "stage543_ex_ante_product_selector_diagnostic_v1"
STAGE543_PREFIX = "qmt_roll_stage543_ex_ante_product_selector_diagnostic"
STAGE543_SCORED_IN = OUTPUT_DIR / f"{STAGE543_PREFIX}_scored_samples_{STAGE543_TAG}.csv"

STAGE544_TAG = "stage544_family_constrained_selector_diagnostic_v1"
STAGE544_PREFIX = "qmt_roll_stage544_family_constrained_selector_diagnostic"
STAGE544_FAMILY_MAP_IN = OUTPUT_DIR / f"{STAGE544_PREFIX}_family_map_{STAGE544_TAG}.csv"

SUPPLY_316_IN = OUTPUT_DIR / "qmt_roll_stage316_supply_demand_quality_probe_features_stage316_supply_demand_quality_probe_v1.csv"
SUPPLY_358_IN = OUTPUT_DIR / "qmt_roll_stage358_supply_demand_backfill_2020_2022_features_stage358_supply_demand_backfill_2020_2022_v1.csv"
MEMBER_315_IN = OUTPUT_DIR / "qmt_roll_stage315_member_rank_quality_probe_features_stage315_member_rank_quality_probe_v1.csv"
BASIS_419_IN = OUTPUT_DIR / "qmt_roll_stage419_stage103_basis_momentum_overlay_basis_features_stage419_stage103_basis_momentum_overlay_v1.csv"
READINESS_530_IN = OUTPUT_DIR / "qmt_roll_stage530_external_data_execution_readiness_readiness_stage530_external_data_execution_readiness_v1.csv"

COVERAGE_BY_PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_by_product_{MODEL_TAG}.csv"
ROUTE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_summary_{MODEL_TAG}.csv"
LIVE_PROBE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_live_probe_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

LIVE_PROBE_DAY = "20260417"
LIVE_PROBE_TIMEOUT_SECONDS = 25
MAX_ASOF_AGE_DAYS = {
    "supply_basis_warehouse_existing": 7,
    "member_rank_existing": 7,
    "term_structure_existing": 30,
}


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


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _product_code(vt_symbol: str) -> str:
    return str(vt_symbol).split(".", 1)[0].upper()


def _load_samples() -> pd.DataFrame:
    samples = pd.read_csv(STAGE543_SCORED_IN, encoding="utf-8-sig")
    samples["eval_date"] = pd.to_datetime(samples["eval_date"], errors="coerce").dt.normalize()
    samples["product_vt_symbol"] = samples["product_vt_symbol"].astype(str)
    samples["is_oracle6"] = pd.to_numeric(samples["is_oracle6"], errors="coerce").fillna(0).astype(int)
    samples["product_code"] = samples["product_vt_symbol"].map(_product_code)

    family = pd.read_csv(STAGE544_FAMILY_MAP_IN, encoding="utf-8-sig")
    family["product_vt_symbol"] = family["product_vt_symbol"].astype(str)
    samples = samples.merge(family[["product_vt_symbol", "product_family", "family_note"]], on="product_vt_symbol", how="left")
    samples["product_family"] = samples["product_family"].fillna("unknown")
    samples["family_note"] = samples["family_note"].fillna("未分类")
    return samples


def _load_feature_dates(path: Path, route: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["route", "product_vt_symbol", "feature_date"])
    frame = pd.read_csv(path, encoding="utf-8-sig")
    if "product_vt_symbol" not in frame.columns:
        return pd.DataFrame(columns=["route", "product_vt_symbol", "feature_date"])
    date_col = "date_dt" if "date_dt" in frame.columns else "date"
    result = frame[["product_vt_symbol", date_col]].copy()
    result.rename(columns={date_col: "feature_date"}, inplace=True)
    result["feature_date"] = pd.to_datetime(result["feature_date"], errors="coerce").dt.normalize()
    result["product_vt_symbol"] = result["product_vt_symbol"].astype(str)
    result = result.dropna(subset=["feature_date"]).drop_duplicates()
    result["route"] = route
    return result[["route", "product_vt_symbol", "feature_date"]]


def _asof_product_coverage(samples: pd.DataFrame, features: pd.DataFrame, route: str, max_age_days: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    route_features = features[features["route"].eq(route)].copy()
    for product, product_samples in samples.groupby("product_vt_symbol", sort=True):
        product_features = route_features[route_features["product_vt_symbol"].eq(product)]["feature_date"].sort_values().to_numpy()
        matched = 0
        latest_age_values: list[float] = []
        for eval_date in product_samples["eval_date"].sort_values():
            pos = np.searchsorted(product_features, np.datetime64(eval_date), side="right") - 1
            if pos < 0:
                continue
            feature_date = pd.Timestamp(product_features[pos])
            age = (pd.Timestamp(eval_date) - feature_date).days
            if 0 <= age <= max_age_days:
                matched += 1
                latest_age_values.append(float(age))
        meta = product_samples.iloc[0]
        rows.append(
            {
                "route": route,
                "product_vt_symbol": product,
                "product_code": meta["product_code"],
                "product_family": meta["product_family"],
                "is_oracle6": int(meta["is_oracle6"]),
                "eval_months": int(product_samples["eval_date"].nunique()),
                "matched_months": int(matched),
                "coverage_rate_pct": float(matched / max(product_samples["eval_date"].nunique(), 1) * 100.0),
                "avg_asof_age_days": float(np.mean(latest_age_values)) if latest_age_values else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _build_existing_coverage(samples: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    feature_frames = [
        _load_feature_dates(SUPPLY_316_IN, "supply_basis_warehouse_existing"),
        _load_feature_dates(SUPPLY_358_IN, "supply_basis_warehouse_existing"),
        _load_feature_dates(MEMBER_315_IN, "member_rank_existing"),
        _load_feature_dates(BASIS_419_IN, "term_structure_existing"),
    ]
    features = pd.concat(feature_frames, ignore_index=True) if feature_frames else pd.DataFrame()
    if not features.empty:
        features = features.drop_duplicates(["route", "product_vt_symbol", "feature_date"])
    coverage = pd.concat(
        [
            _asof_product_coverage(samples, features, route, max_age)
            for route, max_age in MAX_ASOF_AGE_DAYS.items()
        ],
        ignore_index=True,
    )

    summary_rows: list[dict[str, Any]] = []
    for route, frame in coverage.groupby("route", sort=True):
        product_has = frame["matched_months"].gt(0)
        oracle = frame[frame["is_oracle6"].eq(1)].copy()
        summary_rows.append(
            {
                "route": route,
                "product_count": int(frame["product_vt_symbol"].nunique()),
                "products_with_any_coverage": int(product_has.sum()),
                "product_coverage_rate_pct": float(product_has.mean() * 100.0),
                "row_coverage_rate_pct": float(frame["matched_months"].sum() / max(frame["eval_months"].sum(), 1) * 100.0),
                "oracle6_products": int(oracle["product_vt_symbol"].nunique()),
                "oracle6_with_any_coverage": int(oracle["matched_months"].gt(0).sum()),
                "oracle6_row_coverage_rate_pct": float(
                    oracle["matched_months"].sum() / max(oracle["eval_months"].sum(), 1) * 100.0
                ),
                "families_with_any_coverage": int(frame.loc[product_has, "product_family"].nunique()),
            }
        )
    summary = pd.DataFrame(summary_rows).sort_values("route")
    return coverage, summary


def _run_probe(function_name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
    def worker(queue: mp.Queue) -> None:
        try:
            import akshare as ak

            func = getattr(ak, function_name)
            result = func(*args, **kwargs)
            if isinstance(result, pd.DataFrame):
                queue.put(
                    {
                        "status": "ok",
                        "rows": int(len(result)),
                        "columns": list(result.columns),
                        "head": result.head(20).to_dict("records"),
                    }
                )
            else:
                queue.put({"status": "ok", "rows": 0, "columns": [], "head": str(result)[:500]})
        except Exception as exc:  # pragma: no cover - external source instability
            queue.put({"status": "error", "error_type": type(exc).__name__, "error_message": str(exc)[:500]})

    ctx = mp.get_context("fork")
    queue: mp.Queue = ctx.Queue()
    process = ctx.Process(target=worker, args=(queue,))
    process.start()
    process.join(LIVE_PROBE_TIMEOUT_SECONDS)
    if process.is_alive():
        process.terminate()
        process.join(2)
        return {"status": "timeout", "error_type": "Timeout", "error_message": f">{LIVE_PROBE_TIMEOUT_SECONDS}s"}
    if queue.empty():
        return {"status": "empty", "error_type": "EmptyResult", "error_message": "worker returned no message"}
    return queue.get()


def _live_probe(samples: pd.DataFrame) -> pd.DataFrame:
    products = (
        samples[["product_vt_symbol", "product_code", "product_family", "is_oracle6"]]
        .drop_duplicates()
        .sort_values("product_vt_symbol")
    )
    oracle_codes = sorted(products.loc[products["is_oracle6"].eq(1), "product_code"].unique())

    basis_probe = _run_probe("futures_spot_price", LIVE_PROBE_DAY, oracle_codes)
    returned_basis_codes: set[str] = set()
    if basis_probe.get("status") == "ok":
        returned_basis_codes = {str(row.get("symbol", "")).upper() for row in basis_probe.get("head", [])}

    member_probe = _run_probe(
        "get_rank_sum_daily",
        start_day=LIVE_PROBE_DAY,
        end_day=LIVE_PROBE_DAY,
        vars_list=oracle_codes,
    )
    member_returned_codes: set[str] = set()
    if member_probe.get("status") == "ok":
        member_returned_codes = {str(row.get("variety", "")).upper() for row in member_probe.get("head", [])}

    warehouse_probes = {
        "shfe": _run_probe("futures_shfe_warehouse_receipt", LIVE_PROBE_DAY),
        "dce": _run_probe("futures_warehouse_receipt_dce", LIVE_PROBE_DAY),
        "gfex": _run_probe("futures_gfex_warehouse_receipt", LIVE_PROBE_DAY),
        "czce": _run_probe("futures_warehouse_receipt_czce", LIVE_PROBE_DAY),
    }
    rows: list[dict[str, Any]] = []
    for _, row in products[products["is_oracle6"].eq(1)].iterrows():
        code = str(row["product_code"])
        exchange = str(row["product_vt_symbol"]).split(".", 1)[1].upper()
        if exchange == "SHFE":
            warehouse_key = "shfe"
        elif exchange == "DCE":
            warehouse_key = "dce"
        elif exchange == "GFEX":
            warehouse_key = "gfex"
        elif exchange == "CZCE":
            warehouse_key = "czce"
        else:
            warehouse_key = "unsupported_exchange"
        warehouse_status = warehouse_probes.get(warehouse_key, {"status": "unsupported"}).get("status", "unsupported")
        warehouse_error = warehouse_probes.get(warehouse_key, {}).get("error_type", "")
        rows.append(
            {
                "probe_day": LIVE_PROBE_DAY,
                "product_vt_symbol": row["product_vt_symbol"],
                "product_code": code,
                "product_family": row["product_family"],
                "basis_spot_price_status": basis_probe.get("status", ""),
                "basis_returned_for_product": int(code in returned_basis_codes),
                "member_rank_status": member_probe.get("status", ""),
                "member_returned_for_product": int(code in member_returned_codes),
                "warehouse_probe_key": warehouse_key,
                "warehouse_status": warehouse_status,
                "warehouse_error_type": warehouse_error,
                "basis_error_type": basis_probe.get("error_type", ""),
                "member_error_type": member_probe.get("error_type", ""),
                "basis_returned_codes": ",".join(sorted(returned_basis_codes)),
                "member_returned_codes": ",".join(sorted(member_returned_codes)),
            }
        )
    return pd.DataFrame(rows)


def _decision(route_summary: pd.DataFrame, live_probe: pd.DataFrame) -> dict[str, Any]:
    oracle_existing_any = int(route_summary["oracle6_with_any_coverage"].max()) if not route_summary.empty else 0
    basis_live_count = int(live_probe["basis_returned_for_product"].sum()) if not live_probe.empty else 0
    oracle_count = int(live_probe["product_vt_symbol"].nunique()) if not live_probe.empty else 0
    member_ok_count = int(live_probe["member_returned_for_product"].sum()) if not live_probe.empty else 0
    warehouse_ok_count = int(live_probe["warehouse_status"].eq("ok").sum()) if not live_probe.empty else 0

    if oracle_existing_any == 0 and 0 < basis_live_count < oracle_count:
        decision = "existing_external_state_unusable_for_noncore_selection_basis_partial_backfill_needed"
    elif oracle_existing_any == 0 and basis_live_count == 0:
        decision = "existing_external_state_unusable_no_live_oracle_probe"
    else:
        decision = "external_state_has_some_existing_noncore_coverage_needs_selector_test"
    return {
        "stage": "Stage246",
        "script_stage": "Stage546",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision,
        "existing_external_routes": route_summary.to_dict("records"),
        "oracle6_live_probe": {
            "probe_day": LIVE_PROBE_DAY,
            "oracle6_product_count": oracle_count,
            "basis_returned_count": basis_live_count,
            "member_returned_count": member_ok_count,
            "warehouse_ok_count": warehouse_ok_count,
        },
        "overfit_boundary": (
            "No product is promoted and no selector return is optimized. This stage only audits point-in-time data coverage "
            "and a fixed one-day source probe for the Stage241 Oracle6 upper-bound products."
        ),
        "next_step": (
            "Do not run an external-state selector on the current cache because it has no Oracle6/noncore coverage. "
            "If continuing, build a dedicated noncore basis backfill first; treat AO/LU, member rank, warehouse, and sentiment as separate data-engineering blockers."
        ),
    }


def _plot(coverage: pd.DataFrame, route_summary: pd.DataFrame, live_probe: pd.DataFrame, decision: dict[str, Any]) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(16, 9))
    ax_route, ax_oracle, ax_family, ax_gap = axes.flatten()

    if not route_summary.empty:
        x = np.arange(len(route_summary))
        ax_route.bar(x - 0.18, route_summary["row_coverage_rate_pct"], width=0.36, label="All noncore row coverage", color="#2563eb")
        ax_route.bar(
            x + 0.18,
            route_summary["oracle6_row_coverage_rate_pct"],
            width=0.36,
            label="Oracle6 row coverage",
            color="#dc2626",
        )
        ax_route.set_xticks(x)
        ax_route.set_xticklabels(route_summary["route"], rotation=25, ha="right", fontsize=8)
        ax_route.set_ylim(0, 105)
        ax_route.set_title("Existing external feature coverage")
        ax_route.grid(axis="y", alpha=0.25)
        ax_route.legend(fontsize=8)

    if not live_probe.empty:
        oracle = live_probe.set_index("product_vt_symbol")
        matrix = oracle[["basis_returned_for_product", "member_returned_for_product"]].copy()
        matrix["warehouse_source_ok"] = oracle["warehouse_status"].eq("ok").astype(int)
        image = ax_oracle.imshow(matrix.to_numpy(dtype=float), aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
        ax_oracle.set_yticks(np.arange(len(matrix.index)))
        ax_oracle.set_yticklabels(matrix.index)
        ax_oracle.set_xticks(np.arange(len(matrix.columns)))
        ax_oracle.set_xticklabels(["basis", "member", "warehouse"], rotation=30, ha="right")
        ax_oracle.set_title(f"Oracle6 live source probe {LIVE_PROBE_DAY}")
        fig.colorbar(image, ax=ax_oracle, fraction=0.046, pad=0.04)

    family_cov = (
        coverage.groupby(["route", "product_family"], as_index=False)
        .agg(any_covered_products=("matched_months", lambda item: int((item > 0).sum())))
        .pivot(index="product_family", columns="route", values="any_covered_products")
        .fillna(0)
    )
    if not family_cov.empty:
        family_cov.sum(axis=1).sort_values().plot(kind="barh", ax=ax_family, color="#0f766e")
        ax_family.set_title("Families with existing external-covered noncore products")
        ax_family.grid(axis="x", alpha=0.25)

    gap_counts = []
    if not live_probe.empty:
        gap_counts = [
            ("basis_missing_oracle6", int(live_probe["basis_returned_for_product"].eq(0).sum())),
            ("member_missing_or_error", int(live_probe["member_returned_for_product"].eq(0).sum())),
            ("warehouse_missing_or_error", int((~live_probe["warehouse_status"].eq("ok")).sum())),
        ]
    if gap_counts:
        labels, values = zip(*gap_counts)
        ax_gap.barh(labels, values, color=["#f97316", "#ef4444", "#ef4444"])
        ax_gap.set_xlim(0, max(values) + 1)
        ax_gap.set_title("Oracle6 live data blockers")
        ax_gap.grid(axis="x", alpha=0.25)

    fig.suptitle(f"Stage546 decision: {decision['decision']}", fontsize=12)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(coverage: pd.DataFrame, route_summary: pd.DataFrame, live_probe: pd.DataFrame, decision: dict[str, Any]) -> None:
    oracle_view = live_probe[
        [
            "product_vt_symbol",
            "product_family",
            "basis_returned_for_product",
            "member_rank_status",
            "member_error_type",
            "warehouse_probe_key",
            "warehouse_status",
            "warehouse_error_type",
        ]
    ].copy()
    gap_view = coverage[coverage["is_oracle6"].eq(1)][
        ["route", "product_vt_symbol", "product_family", "matched_months", "coverage_rate_pct"]
    ].sort_values(["route", "product_vt_symbol"])
    readiness_text = ""
    if READINESS_530_IN.exists():
        readiness = pd.read_csv(READINESS_530_IN, encoding="utf-8-sig")
        readiness_text = _md_table(readiness[["route", "execution_grade", "blocker"]])
    lines = [
        "# Stage546 外生状态非核心覆盖审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 决策：`{decision['decision']}`。",
        "- 阶段性质：数据覆盖/可执行性审计；不做收益回测，不生成交易候选。",
        "- 核心问题：现有基差、仓单/库存、会员持仓、期限结构数据能否覆盖 Stage543 非核心扩池样本和 Stage241 Oracle6 上限产品。",
        "",
        "## 现有缓存覆盖摘要",
        "",
        _md_table(route_summary),
        "",
        "## Oracle6 现有覆盖缺口",
        "",
        _md_table(gap_view),
        "",
        "## Oracle6 实时源探针",
        "",
        _md_table(oracle_view),
        "",
        "## Stage530 通道边界复读",
        "",
        readiness_text or "未找到 Stage530 readiness。",
        "",
        "## 判断",
        "",
        "- 当前现有外生特征缓存不能用于非核心选品诊断，因为它基本只覆盖 Stage78 核心池，Oracle6 覆盖为 0。",
        "- AKShare `futures_spot_price` 对 Oracle6 中 `AL/C/V/Y` 有样例返回，但 `AO/LU` 未返回；这说明非核心基差补齐有部分可行性，但不是一次性覆盖完整。",
        "- 会员持仓和仓单源在本次固定日期探针中报错或不支持，不能作为当前 live 选择器输入。",
        "- 舆情没有点时化接收账本，仍不具备回测资格。",
        "",
        "## 输出文件",
        "",
        f"- coverage by product：`{COVERAGE_BY_PRODUCT_PATH}`",
        f"- route summary：`{ROUTE_SUMMARY_PATH}`",
        f"- live probe：`{LIVE_PROBE_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- chart：`{CHART_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    samples = _load_samples()
    coverage, route_summary = _build_existing_coverage(samples)
    live_probe = _live_probe(samples)
    decision = _decision(route_summary, live_probe)

    coverage.to_csv(COVERAGE_BY_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    route_summary.to_csv(ROUTE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    live_probe.to_csv(LIVE_PROBE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(coverage, route_summary, live_probe, decision)
    _write_report(coverage, route_summary, live_probe, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
