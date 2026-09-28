"""Run the frozen Stage001 audit of the legacy formal AI scorer."""

from __future__ import annotations

import ast
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
import sqlite3
import sys
from typing import Any, Final

import numpy as np
import pandas as pd


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import pit_scorer_audit as core  # noqa: E402


LINE_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
BACKTEST_DIR = WORKSPACE_ROOT / "examples/portfolio_backtesting"
BACKTEST_OUTPUTS = BACKTEST_DIR / "backtest_outputs"
OUTPUT_DIR = LINE_DIR / "artifacts/stage001_legacy_scorer_pit_audit"

INPUT_PATHS: Final = {
    "legacy_scorer_source": BACKTEST_DIR
    / "analyze_qmt_roll_ai_product_suitability_walkforward.py",
    "current_universe_source": BACKTEST_DIR / "qmt_universe.py",
    "legacy_daily": BACKTEST_OUTPUTS
    / "qmt_roll_ai_product_suitability_walkforward_daily_product_suitability_wf_v1.csv",
    "legacy_samples": BACKTEST_OUTPUTS
    / "qmt_roll_ai_product_suitability_walkforward_samples_product_suitability_wf_v1.csv",
    "legacy_windows": BACKTEST_OUTPUTS
    / "qmt_roll_ai_product_suitability_walkforward_window_metrics_product_suitability_wf_v1.csv",
    "legacy_position_changes": BACKTEST_OUTPUTS
    / "qmt_roll_selection_long015_volref30_corr_formal_floor35_position_changes_2020_2026_04.csv",
    "main_contract_mapping": BACKTEST_OUTPUTS
    / "tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv",
    "mapping_exporter": BACKTEST_DIR
    / "export_tqsdk_all_futures_main_contract_mapping.py",
    "mapping_consumer": BACKTEST_DIR / "main_contract_mapping.py",
    "database": WORKSPACE_ROOT / ".vntrader/database.db",
    "prior_first_available_dates": WORKSPACE_ROOT
    / "research/lines/futures_trend_ai_pit_listing_eligibility"
    / "artifacts/stage001_pit_listing_membership/first_available_dates.csv",
    "spec": LINE_DIR
    / "stages/20260902_1234_stage000_legacy_scorer_pit_audit_preregistration.md",
    "core": LINE_DIR / "tools/pit_scorer_audit.py",
}
EXPECTED_SHA256: Final = {
    "legacy_scorer_source": "7734d1768728a4e591b80e98da2b5bac90636904dad82e0fed5f331a6eb45de4",
    "current_universe_source": "8a149c49075d85d25f27146a8f3c2de3bea1971e3bd0d20a36ed9104b636997f",
    "legacy_daily": "9af514a3a5ab7ca4d982a31bd758522c32c4dec792f1b1819abb5462a391efcd",
    "legacy_samples": "4cbc9952a1dac4373ac1901f958b914ac1d3495e56873c21cc6187548a60311d",
    "legacy_windows": "869d634e1e56b99cac6f28cf4e0108942c104648b4cedd91fc8ee9961fee0da3",
    "legacy_position_changes": "8117146732a165e9e61627e71a8b19044d3acddab9c7af1160ec20ac83fb7210",
    "main_contract_mapping": "89c8ae7e66e67def7f2b9626a166d0d6582c30fe2e08ee6cf39808951146d851",
    "mapping_exporter": "1dd8642c91898889acdedaae2933e163b778b9ffe0c45945fd4be37feb4a5d5b",
    "mapping_consumer": "86f4baa027e1a236616d749895e349840a3db305b7ca87a7401ff4afc47bc503",
    "database": "7e2633909f73d77c3b0b044199418d7c1ed2989afde480596aefbb18a83b724a",
    "prior_first_available_dates": "d2fa054e4184371a987976c20544c036b9361f8ccd8410dcdc081463c4c3e038",
    "spec": "12995bbd3f26ec88b5467cdf062cdcfca6f2cea53ae9b0f85a264af3503aa35c",
    "core": "eb4d2b83fdc460448c9c889a3a6265300ea11ff13ed1e837c7301e88c63d7570",
}

OFFICIAL_LISTING_DATES: Final = {
    "lh.DCE": "2021-01-08",
    "si.GFEX": "2022-12-22",
    "lc.GFEX": "2023-07-21",
    "SH.CZCE": "2023-09-15",
}
OFFICIAL_LISTING_SOURCES: Final = {
    "lh.DCE": "https://www.csrc.gov.cn/csrc/c100024/c1492179/1492179/files/7bc8658d6c8a444a98d4e10655b136b9.pdf",
    "si.GFEX": "https://www.csrc.gov.cn/csrc/c100028/c6902408/content.shtml",
    "lc.GFEX": "https://www.gfex.com.cn/gfex/bsyw/list_yw_11.shtml",
    "SH.CZCE": "https://www.czce.com.cn/cn/rootfiles/2023/10/18/1697226838884489-1697226838904727.pdf",
}

CONDITIONAL_PASS_DECISION = (
    "stage001_legacy_pit_audit_complete_allow_fixed_universe_conditional_rebuild"
)
FULL_PASS_DECISION = "stage001_legacy_pit_audit_complete_allow_full_asof_rebuild"
FAIL_DECISION = "stage001_legacy_pit_audit_fail_stop_no_training"


class Stage001Error(RuntimeError):
    """Raised when the frozen Stage001 audit must fail closed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_inputs(
    input_paths: Mapping[str, Path],
    expected_sha256: Mapping[str, str],
) -> dict[str, dict[str, Any]]:
    if set(input_paths) != set(expected_sha256):
        raise Stage001Error("input_identity_keys_mismatch")
    identities: dict[str, dict[str, Any]] = {}
    for name in sorted(input_paths):
        path = Path(input_paths[name])
        if not path.is_file():
            raise Stage001Error(f"input_missing:{name}")
        digest = sha256_file(path)
        if digest != expected_sha256[name]:
            raise Stage001Error(f"input_sha256_drift:{name}")
        identities[name] = {
            "path": str(path.resolve()),
            "size": int(path.stat().st_size),
            "sha256": digest,
        }
    return identities


def load_current_products_ast(path: Path) -> set[str]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=str(path))
    product_list: ast.List | ast.Tuple | None = None
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == "PRODUCT_SPECS" for target in targets):
            continue
        value = node.value
        if isinstance(value, (ast.List, ast.Tuple)):
            product_list = value
        break
    if product_list is None:
        raise Stage001Error("product_specs_ast_missing")

    products: set[str] = set()
    for item in product_list.elts:
        if not isinstance(item, ast.Call) or len(item.args) < 2:
            raise Stage001Error("product_spec_ast_invalid")
        code_node, exchange_node = item.args[:2]
        if not isinstance(code_node, ast.Constant) or not isinstance(code_node.value, str):
            raise Stage001Error("product_code_ast_invalid")
        if not isinstance(exchange_node, ast.Attribute):
            raise Stage001Error("product_exchange_ast_invalid")
        products.add(f"{code_node.value}.{exchange_node.attr}")
    if not products:
        raise Stage001Error("current_products_empty")
    return products


def load_daily_bars(database: Path, products: set[str]) -> pd.DataFrame:
    clauses: list[str] = []
    parameters: list[str] = []
    for product in sorted(products):
        code, separator, exchange = product.partition(".")
        if not separator:
            raise Stage001Error(f"product_invalid:{product}")
        clauses.append("(exchange = ? and lower(symbol) glob ?)")
        parameters.extend([exchange, f"{code.lower()}[0-9]*"])
    query = f"""
        select datetime, symbol, exchange,
               open_price, high_price, low_price, close_price
        from dbbardata
        where interval = 'd'
          and ({' or '.join(clauses)})
        order by datetime, exchange, symbol
    """
    uri = f"file:{Path(database).resolve()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.execute("pragma query_only = on")
        frame = pd.read_sql_query(query, connection, params=parameters)
    if frame.empty:
        raise Stage001Error("daily_bars_empty")
    return frame


def valid_bar_keys(bars: pd.DataFrame) -> set[tuple[str, str]]:
    price_columns = ["open_price", "high_price", "low_price", "close_price"]
    frame = bars.copy()
    frame["date"] = pd.to_datetime(frame["datetime"], errors="raise").dt.tz_localize(None).dt.normalize()
    for column in price_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    valid = np.isfinite(frame[price_columns]).all(axis=1) & frame[price_columns].gt(0.0).all(axis=1)
    frame = frame[valid].copy()
    frame["vt_symbol"] = frame["symbol"].astype(str) + "." + frame["exchange"].astype(str)
    return {
        (row.date.date().isoformat(), str(row.vt_symbol))
        for row in frame[["date", "vt_symbol"]].itertuples(index=False)
    }


def audit_mapping_bar_coverage(
    mapping: pd.DataFrame,
    *,
    valid_bar_keys: set[tuple[str, str]],
    effective_listing_dates: Mapping[str, pd.Timestamp],
    analysis_dates: pd.DatetimeIndex,
) -> dict[str, Any]:
    required = {"date", "continuous_symbol_vt", "main_contract_vt"}
    missing = sorted(required - set(mapping.columns))
    if missing:
        raise Stage001Error(f"mapping_columns_missing:{','.join(missing)}")
    frame = mapping[list(required)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
    frame["continuous_symbol_vt"] = frame["continuous_symbol_vt"].astype(str)
    frame["main_contract_vt"] = frame["main_contract_vt"].fillna("").astype(str)
    date_set = set(pd.DatetimeIndex(analysis_dates).normalize())
    frame = frame[
        frame["date"].isin(date_set)
        & frame["continuous_symbol_vt"].isin(set(effective_listing_dates))
    ].copy()
    frame["listing_date"] = frame["continuous_symbol_vt"].map(effective_listing_dates)
    eligible = frame[frame["date"].ge(frame["listing_date"])].copy()
    nonempty = eligible[eligible["main_contract_vt"].ne("")].copy()
    same_day = [
        (row.date.date().isoformat(), str(row.main_contract_vt)) in valid_bar_keys
        for row in nonempty.itertuples(index=False)
    ]
    same_day_count = int(sum(same_day))
    denominator = int(len(nonempty))
    return {
        "analysis_mapping_rows": int(len(frame)),
        "eligible_mapping_rows": int(len(eligible)),
        "eligible_nonempty_mapping_rows": denominator,
        "same_day_valid_ohlc_rows": same_day_count,
        "same_day_valid_ohlc_coverage": (
            float(same_day_count / denominator) if denominator else 0.0
        ),
        "mapping_products": int(frame["continuous_symbol_vt"].nunique()),
        "mapping_dates": int(frame["date"].nunique()),
    }


def build_decision(summary: Mapping[str, Any]) -> str:
    technical_gates = [
        bool(summary.get("input_identity_stable")),
        bool(summary.get("legacy_future_pnl_reproduction_pass")),
        int(summary.get("legacy_fold_count", 0)) == 9,
        int(summary.get("legacy_overlap_fold_count", 0)) == 9,
        int(summary.get("legacy_partial_horizon_rows", 0)) > 0,
        int(summary.get("legacy_unlisted_sample_rows", 0)) > 0,
        bool(summary.get("effective_listing_dates_complete")),
        int(summary.get("minimum_eligible_cross_section", 0)) >= 8,
        float(summary.get("mapping_same_day_bar_coverage", 0.0)) >= 0.95,
    ]
    if not all(technical_gates):
        return FAIL_DECISION
    if bool(summary.get("historical_asof_universe_reconstructable")):
        return FULL_PASS_DECISION
    return CONDITIONAL_PASS_DECISION


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(
        path,
        index=False,
        encoding="utf-8-sig",
        float_format="%.17g",
        lineterminator="\n",
    )


def publish_artifacts(
    output_dir: Path,
    *,
    label_audit: pd.DataFrame,
    fold_audit: pd.DataFrame,
    listing_audit: pd.DataFrame,
    universe_audit: dict[str, Any],
    summary: dict[str, Any],
) -> None:
    output_dir = Path(output_dir)
    temp_dir = output_dir.with_name(f"{output_dir.name}.tmp")
    if output_dir.exists():
        raise Stage001Error("output_already_exists")
    if temp_dir.exists():
        raise Stage001Error("temp_output_already_exists")
    temp_dir.mkdir(parents=True, exist_ok=False)

    _write_csv(label_audit, temp_dir / "sample_label_boundary_audit.csv")
    _write_csv(fold_audit, temp_dir / "fold_label_overlap_audit.csv")
    _write_csv(listing_audit, temp_dir / "listing_eligibility_audit.csv")
    (temp_dir / "universe_provenance_audit.json").write_text(
        json.dumps(universe_audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (temp_dir / "stage001_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = (
        "# Stage001 旧正式评分器PIT审计\n\n"
        f"- 决策：`{summary['decision']}`。\n"
        f"- 旧fold：`{summary['legacy_fold_count']}`；标签越界fold："
        f"`{summary['legacy_overlap_fold_count']}`，越界训练行："
        f"`{summary['legacy_overlap_train_rows']}`。\n"
        f"- 非完整60日标签：`{summary['legacy_partial_horizon_rows']}`行；"
        f"未上市样本：`{summary['legacy_unlisted_sample_rows']}`行。\n"
        f"- 历史批准宇宙可重建：`{summary['historical_asof_universe_reconstructable']}`；"
        "下一阶段证据仅限固定当前设计宇宙条件下的PIT基线。\n"
        "- 本阶段训练0、回测0、sealed holdout读取0、CTP/订单调用0。\n"
    )
    (temp_dir / "report.md").write_text(report, encoding="utf-8")
    payload_names = [
        "sample_label_boundary_audit.csv",
        "fold_label_overlap_audit.csv",
        "listing_eligibility_audit.csv",
        "universe_provenance_audit.json",
        "stage001_summary.json",
        "report.md",
    ]
    manifest = {name: sha256_file(temp_dir / name) for name in payload_names}
    (temp_dir / "artifact_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp_dir.rename(output_dir)


def run_stage001(
    output_dir: Path = OUTPUT_DIR,
    *,
    input_paths: Mapping[str, Path] = INPUT_PATHS,
    expected_sha256: Mapping[str, str] = EXPECTED_SHA256,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise Stage001Error("output_already_exists")
    before = verify_inputs(input_paths, expected_sha256)

    daily = pd.read_csv(input_paths["legacy_daily"], usecols=["date", core.PRODUCT_COLUMN, "net_pnl"])
    samples = pd.read_csv(input_paths["legacy_samples"])
    windows = pd.read_csv(input_paths["legacy_windows"])
    position_changes = pd.read_csv(input_paths["legacy_position_changes"], usecols=["vt_symbol"])
    mapping = pd.read_csv(
        input_paths["main_contract_mapping"],
        usecols=["date", "continuous_symbol_vt", "main_contract_vt"],
    )

    current_products = load_current_products_ast(input_paths["current_universe_source"])
    sample_products = set(samples[core.PRODUCT_COLUMN].astype(str))
    observed_position_products = {
        core.product_from_contract(value) for value in position_changes["vt_symbol"].dropna()
    }
    mapping_products = set(mapping["continuous_symbol_vt"].dropna().astype(str))
    bars = load_daily_bars(input_paths["database"], current_products)
    first_valid = core.derive_first_valid_ohlc_dates(bars, sorted(current_products))
    effective = core.build_effective_listing_dates(
        sorted(current_products), OFFICIAL_LISTING_DATES, first_valid
    )

    label_audit_full = core.recover_label_boundaries(daily, samples, horizon=60)
    fold_audit = core.audit_fold_label_overlap(label_audit_full, windows)
    eligible, listing_audit = core.apply_listing_filter_before_target(
        label_audit_full, effective
    )
    compact_columns = [
        core.DATE_COLUMN,
        core.PRODUCT_COLUMN,
        core.FUTURE_PNL_COLUMN,
        core.TARGET_COLUMN,
        "future_label_start_date",
        "future_label_end_date",
        "future_observation_count",
        "full_horizon_label",
        "recomputed_future_net_pnl",
        "legacy_future_net_pnl_abs_diff",
    ]
    label_audit = label_audit_full[compact_columns].copy()
    label_audit["pit_listing_date"] = label_audit[core.PRODUCT_COLUMN].map(effective)
    label_audit["pit_listing_eligible"] = label_audit[core.DATE_COLUMN].ge(
        label_audit["pit_listing_date"]
    )

    universe_audit = core.classify_universe_provenance(
        sample_products=sample_products,
        current_products=current_products,
        observed_position_products=observed_position_products,
        mapping_products=mapping_products,
        historical_approval_source=None,
    )
    prior_first = pd.read_csv(input_paths["prior_first_available_dates"])
    prior_first_map = dict(
        zip(
            prior_first[core.PRODUCT_COLUMN].astype(str),
            prior_first["first_available_date"].astype(str),
            strict=True,
        )
    )
    universe_audit.update(
        {
            "official_listing_dates": dict(OFFICIAL_LISTING_DATES),
            "official_listing_sources": dict(OFFICIAL_LISTING_SOURCES),
            "first_valid_positive_ohlc_dates": {
                product: value.date().isoformat()
                for product, value in sorted(first_valid.items())
            },
            "effective_listing_dates": {
                product: value.date().isoformat()
                for product, value in sorted(effective.items())
            },
            "prior_key_only_first_dates": prior_first_map,
            "mapping_provenance": {
                "source": "TqContCalendar historical export",
                "consumer_uses_same_date_mapping": True,
                "local_open_interest_selection_algorithm_present": False,
                "historical_causal_identity_verifiable_locally": False,
                "classification": "vendor_calendar_snapshot_not_locally_reconstructable",
            },
        }
    )

    daily_dates = pd.DatetimeIndex(pd.to_datetime(daily["date"], errors="raise").unique())
    mapping_coverage = audit_mapping_bar_coverage(
        mapping,
        valid_bar_keys=valid_bar_keys(bars),
        effective_listing_dates=effective,
        analysis_dates=daily_dates,
    )
    universe_audit["mapping_bar_coverage"] = mapping_coverage

    max_reproduction_diff = core.finite_max_abs(
        label_audit_full["legacy_future_net_pnl_abs_diff"]
    )
    before_after_probe = verify_inputs(input_paths, expected_sha256)
    input_identity_stable = before == before_after_probe
    preliminary: dict[str, Any] = {
        "input_identity_stable": input_identity_stable,
        "legacy_future_pnl_reproduction_pass": bool(max_reproduction_diff <= 1e-9),
        "legacy_fold_count": int(len(fold_audit)),
        "legacy_overlap_fold_count": int((fold_audit["overlap_rows"] > 0).sum()),
        "legacy_partial_horizon_rows": int((~label_audit_full["full_horizon_label"]).sum()),
        "legacy_unlisted_sample_rows": int(listing_audit["ineligible_sample_rows"].sum()),
        "effective_listing_dates_complete": set(effective) == current_products,
        "minimum_eligible_cross_section": int(listing_audit["eligible_cross_section_count"].min()),
        "historical_asof_universe_reconstructable": bool(
            universe_audit["historical_asof_universe_reconstructable"]
        ),
        "mapping_same_day_bar_coverage": float(
            mapping_coverage["same_day_valid_ohlc_coverage"]
        ),
    }
    decision = build_decision(preliminary)
    summary: dict[str, Any] = {
        "line_id": "futures_trend_ai_pit_scorer_rebuild",
        "stage": "Stage001",
        "decision": decision,
        **preliminary,
        "legacy_model_pit_valid": False,
        "conditional_pit_rebuild_feasible": decision
        in {CONDITIONAL_PASS_DECISION, FULL_PASS_DECISION},
        "legacy_sample_rows": int(len(samples)),
        "legacy_sample_months": int(pd.to_datetime(samples[core.DATE_COLUMN]).nunique()),
        "legacy_sample_products": int(len(sample_products)),
        "legacy_future_pnl_max_abs_diff": max_reproduction_diff,
        "legacy_overlap_train_rows": int(fold_audit["overlap_rows"].sum()),
        "legacy_overlap_train_months_sum": int(fold_audit["overlap_months"].sum()),
        "legacy_partial_horizon_months": int(
            label_audit_full.loc[
                ~label_audit_full["full_horizon_label"], core.DATE_COLUMN
            ].nunique()
        ),
        "legacy_eligible_target_changed_rows": int(
            listing_audit["eligible_target_changed_rows"].sum()
        ),
        "conditional_eligible_rows": int(len(eligible)),
        "first_valid_positive_ohlc_dates": universe_audit[
            "first_valid_positive_ohlc_dates"
        ],
        "effective_listing_dates": universe_audit["effective_listing_dates"],
        "mapping_bar_coverage": mapping_coverage,
        "mapping_historical_causal_identity_verifiable_locally": False,
        "inputs_before": before,
        "inputs_after": before_after_probe,
        "model_training_runs": 0,
        "strategy_backtest_runs": 0,
        "sealed_xgboost_holdout_rows_read": 0,
        "ctp_connected": False,
        "order_api_called_count": 0,
    }
    publish_artifacts(
        output_dir,
        label_audit=label_audit,
        fold_audit=fold_audit,
        listing_audit=listing_audit,
        universe_audit=universe_audit,
        summary=summary,
    )
    return summary


def main() -> None:
    print(json.dumps(run_stage001(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

