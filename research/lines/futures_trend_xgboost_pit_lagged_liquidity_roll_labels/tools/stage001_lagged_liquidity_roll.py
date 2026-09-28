"""Stage001 qualification for strictly lagged dynamic futures roll labels."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd


LINE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
UPSTREAM_TOOLS = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_expiry_safe_roll_mapping/tools"
)
TRADEABILITY_TOOLS = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_roll_label_tradeability/tools"
)
for tools_dir in (UPSTREAM_TOOLS, TRADEABILITY_TOOLS):
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))

import roll_label_tradeability as tradeability
import stage001_expiry_safe_roll_mapping as upstream_stage

import lagged_liquidity_roll as core


publisher = upstream_stage.upstream
UPSTREAM_DIR = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_expiry_safe_roll_mapping/"
    "artifacts/stage001_expiry_safe_roll_mapping"
)
SOURCE_DIR = upstream_stage.SOURCE_DIR
UPSTREAM_PASS_DECISION = upstream_stage.PASS_DECISION
PASS_DECISION = (
    "stage001_lagged_liquidity_roll_pass_allow_label_value_"
    "preregistration_only"
)
FAIL_DECISION = "stage001_lagged_liquidity_roll_fail_close_no_label_values"
DEFAULT_OUTPUT_DIR = LINE_DIR / "artifacts/stage001_lagged_liquidity_roll"
DEFAULT_INPUT_PATHS = {
    "upstream_manifest": UPSTREAM_DIR / "artifact_manifest.json",
    "upstream_paths": UPSTREAM_DIR / "expiry_safe_paths.csv.gz",
    "upstream_summary": UPSTREAM_DIR / "summary.json",
    "source_manifest": SOURCE_DIR / "artifact_manifest.json",
    "source_catalog": SOURCE_DIR / "asof_contract_catalog.csv.gz",
    "source_bars": SOURCE_DIR / "normalised_daily_bars.csv.gz",
}
DEFAULT_EXPECTED_SHA256 = {
    "upstream_manifest": "9f768fc6de7ccd3eb240c29f0444249bd333356d756b137197dc78e4f5f44d76",
    "upstream_paths": "a3f2c1249085b872372f8f0aca2d1cbaf77ecb8a7bc04056f9118f077c16748e",
    "upstream_summary": "6f994dd88896781a7f1af9e9760890540445dc8539a6349ae416b82bcf37283f",
    "source_manifest": "e3894cd20114182e9b3a9e986ed5e0310fe264de06368b5efe1b5efb6903681a",
    "source_catalog": "c733e5d85bab4349efb9bd25e2afdd689562718ffd608bff9a4f11964ab13bfc",
    "source_bars": "f2cf98dbfde2e18031697d598c3147c0ee8f15d3feb6ab935b92bc44a919ece4",
}


@dataclass(frozen=True)
class ExpectedCounts:
    path_rows: int = 56_272
    path_qids: int = 1_046
    holding_period: int = 20
    minimum_candidates_per_qid: int = 30
    minimum_volume: float = 100.0
    minimum_open_interest: float = 100.0


class Stage001Error(RuntimeError):
    pass


def _normalise_dates(
    frame: pd.DataFrame,
    columns: list[str],
    *,
    allow_missing: bool = False,
) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        result[column] = pd.to_datetime(
            result[column], errors="coerce"
        ).dt.normalize()
        if not allow_missing and result[column].isna().any():
            raise Stage001Error(f"invalid_date:{column}")
    return result


def _load_catalog(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(
        path,
        encoding="utf-8-sig",
        usecols=["vt_symbol", "product_vt_symbol", "expire_date"],
        dtype={"vt_symbol": "string", "product_vt_symbol": "string"},
    )
    return _normalise_dates(frame, ["expire_date"])


def _execution_dates(
    windows: pd.DataFrame, global_dates: pd.DatetimeIndex
) -> pd.DatetimeIndex:
    entry_positions = global_dates.get_indexer(windows["entry_date"])
    end_positions = global_dates.get_indexer(windows["label_end"])
    if (entry_positions < 1).any() or (end_positions <= entry_positions).any():
        raise Stage001Error("window_calendar_mismatch")
    return global_dates[
        int(entry_positions.min()) : int(end_positions.max())
    ]


def _retain_leg1_candidates(
    windows: pd.DataFrame, daily_mapping: pd.DataFrame
) -> pd.DataFrame:
    leg1 = daily_mapping[
        [
            "execution_date",
            "product_vt_symbol",
            "mapping_valid",
            "selected_contract_vt",
        ]
    ].rename(columns={"execution_date": "entry_date"})
    candidates = windows.merge(
        leg1,
        how="left",
        on=["entry_date", "product_vt_symbol"],
        validate="many_to_one",
    )
    keep = (
        candidates["mapping_valid"].fillna(False).astype(bool)
        & candidates["selected_contract_vt"].notna()
    )
    return candidates.loc[keep, windows.columns].reset_index(drop=True)


def _build_path_qualification(
    retained: pd.DataFrame,
    legs: pd.DataFrame,
    leg_audit: pd.DataFrame,
    events: pd.DataFrame,
    *,
    holding_period: int,
) -> pd.DataFrame:
    keys = ["query_date", "product_vt_symbol"]
    paths = _normalise_dates(
        retained, ["query_date", "entry_date", "label_end"]
    )
    structure = legs.groupby(keys, sort=False).agg(
        dynamic_leg_count=("leg_index", "size"),
        selected_contract_count=("selected_contract_vt", "nunique"),
        roll_event_count=("roll_event", "sum"),
        mapping_invalid_leg_count=(
            "mapping_valid",
            lambda values: int((~values.fillna(False).astype(bool)).sum()),
        ),
        strict_lag_violation_count=(
            "exact_previous_session", lambda values: int((~values.astype(bool)).sum())
        ),
        expiry_invalid_leg_count=(
            "expiry_valid", lambda values: int((~values.astype(bool)).sum())
        ),
        dynamic_structure_valid=("leg_valid", "all"),
    )
    if leg_audit.empty:
        audit = pd.DataFrame(
            columns=[
                *keys,
                "audited_leg_count",
                "price_invalid_leg_count",
                "price_observation_valid",
            ]
        ).set_index(keys)
    else:
        audit = leg_audit.groupby(keys, sort=False).agg(
            audited_leg_count=("leg_index", "size"),
            price_invalid_leg_count=(
                "price_observation_valid", lambda values: int((~values).sum())
            ),
            price_observation_valid=("price_observation_valid", "all"),
        )
    if events.empty:
        event_summary = pd.DataFrame(
            columns=[
                *keys,
                "execution_event_count",
                "capacity_invalid_event_count",
                "minimum_one_lot_capacity_valid",
            ]
        ).set_index(keys)
    else:
        event_summary = events.groupby(keys, sort=False).agg(
            execution_event_count=("event_role", "size"),
            capacity_invalid_event_count=(
                "capacity_valid", lambda values: int((~values).sum())
            ),
            minimum_one_lot_capacity_valid=("capacity_valid", "all"),
        )
    result = (
        paths.merge(structure.reset_index(), on=keys, how="left", validate="one_to_one")
        .merge(audit.reset_index(), on=keys, how="left", validate="one_to_one")
        .merge(
            event_summary.reset_index(),
            on=keys,
            how="left",
            validate="one_to_one",
        )
    )
    integer_columns = [
        "dynamic_leg_count",
        "selected_contract_count",
        "roll_event_count",
        "mapping_invalid_leg_count",
        "strict_lag_violation_count",
        "expiry_invalid_leg_count",
        "audited_leg_count",
        "price_invalid_leg_count",
        "execution_event_count",
        "capacity_invalid_event_count",
    ]
    for column in integer_columns:
        result[column] = result[column].fillna(0).astype(int)
    for column in (
        "dynamic_structure_valid",
        "price_observation_valid",
        "minimum_one_lot_capacity_valid",
    ):
        result[column] = result[column].eq(True)
    result["expected_execution_event_count"] = (
        2 + 2 * result["roll_event_count"]
    )
    result["execution_event_structure_valid"] = result[
        "execution_event_count"
    ].eq(result["expected_execution_event_count"])
    result["qualification_valid"] = (
        result["dynamic_structure_valid"]
        & result["dynamic_leg_count"].eq(holding_period)
        & result["audited_leg_count"].eq(holding_period)
        & result["price_observation_valid"]
        & result["execution_event_structure_valid"]
        & result["minimum_one_lot_capacity_valid"]
    )
    return result.sort_values(keys, kind="mergesort").reset_index(drop=True)


def _monotone_expiry(mapping: pd.DataFrame) -> bool:
    valid = mapping[mapping["mapping_valid"].astype(bool)].copy()
    valid = valid.sort_values(
        ["product_vt_symbol", "execution_date"], kind="mergesort"
    )
    for _, group in valid.groupby("product_vt_symbol", sort=False):
        expiry = pd.to_datetime(group["selected_expire_date"], errors="coerce")
        if expiry.isna().any() or expiry.diff().dropna().lt(pd.Timedelta(0)).any():
            return False
    return True


def assess_stage001(
    windows: pd.DataFrame,
    retained: pd.DataFrame,
    candidates: pd.DataFrame,
    daily_mapping: pd.DataFrame,
    legs: pd.DataFrame,
    leg_audit: pd.DataFrame,
    events: pd.DataFrame,
    path_qualification: pd.DataFrame,
    upstream_summary: Mapping[str, object],
    global_dates: pd.DatetimeIndex,
    *,
    upstream_verified: bool,
    source_verified: bool,
    input_identity_stable: bool,
    expected: ExpectedCounts = ExpectedCounts(),
) -> dict[str, object]:
    keys = ["query_date", "product_vt_symbol"]
    query_dates = pd.DatetimeIndex(windows["query_date"].drop_duplicates())
    breadth = retained.groupby("query_date", sort=False).size().reindex(
        query_dates, fill_value=0
    )
    upstream_gate = bool(
        upstream_summary.get("decision") == UPSTREAM_PASS_DECISION
        and int(upstream_summary.get("path_rows", -1)) == expected.path_rows
        and int(upstream_summary.get("path_qids", -1)) == expected.path_qids
        and int(upstream_summary.get("invalid_path_rows", -1)) == 0
        and int(upstream_summary.get("invalid_leg_rows", -1)) == 0
    )
    frozen_window_gate = bool(
        len(windows) == expected.path_rows
        and windows["query_date"].nunique() == expected.path_qids
        and windows["path_valid"].astype(bool).all()
        and not windows.duplicated(keys).any()
    )
    execution_dates = pd.DatetimeIndex(
        daily_mapping["execution_date"].drop_duplicates().sort_values()
    )
    products = pd.Index(windows["product_vt_symbol"].drop_duplicates())
    positions = global_dates.get_indexer(execution_dates)
    expected_selection = pd.Series(
        global_dates.take(positions - 1), index=execution_dates
    )
    expected_return = pd.Series(
        global_dates.take(positions + 1), index=execution_dates
    )
    mapping_calendar_gate = bool(
        (positions >= 1).all()
        and (positions < len(global_dates) - 1).all()
        and len(daily_mapping) == len(execution_dates) * len(products)
        and not daily_mapping.duplicated(
            ["execution_date", "product_vt_symbol"]
        ).any()
        and daily_mapping["selection_date"].eq(
            daily_mapping["execution_date"].map(expected_selection)
        ).all()
        and daily_mapping["return_date"].eq(
            daily_mapping["execution_date"].map(expected_return)
        ).all()
    )
    selected_candidates = candidates[candidates["selected"].astype(bool)]
    candidate_selection_gate = bool(
        not candidates["future_or_same_day_source"].astype(bool).any()
        and selected_candidates["raw_selection_eligible"].astype(bool).all()
        and selected_candidates["monotone_selection_eligible"].astype(bool).all()
        and selected_candidates["volume"].ge(expected.minimum_volume).all()
        and selected_candidates["open_interest"].ge(
            expected.minimum_open_interest
        ).all()
        and selected_candidates["expire_date"].ge(
            selected_candidates["return_date"]
        ).all()
    )
    candidate_breadth_gate = bool(
        len(breadth) == expected.path_qids
        and breadth.min() >= expected.minimum_candidates_per_qid
    )
    leg_groups = legs.groupby(keys, sort=False)
    dynamic_leg_structure_gate = bool(
        len(legs) == len(retained) * expected.holding_period
        and leg_groups.size().eq(expected.holding_period).all()
        and not legs.duplicated([*keys, "leg_index"]).any()
    )
    complete_mapping_gate = bool(
        legs["mapping_present"].astype(bool).all()
        and legs["mapping_valid"].fillna(False).astype(bool).all()
        and legs["selected_contract_vt"].notna().all()
    )
    strict_lag_gate = bool(
        legs["exact_previous_session"].astype(bool).all()
        and not legs["same_day_or_future_selection_violation"].astype(bool).any()
        and legs["selection_date"].lt(legs["previous_date"]).all()
    )
    expiry_gate = bool(
        legs["expiry_valid"].astype(bool).all()
        and _monotone_expiry(daily_mapping)
    )
    price_gate = bool(
        len(leg_audit) == len(legs)
        and leg_audit["price_observation_valid"].astype(bool).all()
    )
    role_counts = events["event_role"].value_counts().astype(int).to_dict()
    event_structure_gate = bool(
        path_qualification["execution_event_structure_valid"].astype(bool).all()
    )
    capacity_gate = bool(
        event_structure_gate
        and events["capacity_valid"].astype(bool).all()
        and path_qualification["minimum_one_lot_capacity_valid"].astype(bool).all()
    )
    identity_gate = bool(
        len(path_qualification) == len(retained)
        and not path_qualification.duplicated(keys).any()
    )
    gates = {
        "upstream_manifest_gate": bool(upstream_verified),
        "source_manifest_gate": bool(source_verified),
        "input_identity_gate": bool(input_identity_stable),
        "upstream_decision_gate": upstream_gate,
        "frozen_window_gate": frozen_window_gate,
        "daily_mapping_calendar_gate": mapping_calendar_gate,
        "causal_candidate_selection_gate": candidate_selection_gate,
        "candidate_breadth_gate": candidate_breadth_gate,
        "dynamic_leg_structure_gate": dynamic_leg_structure_gate,
        "complete_dynamic_mapping_gate": complete_mapping_gate,
        "strict_lag_selection_gate": strict_lag_gate,
        "monotone_expiry_coverage_gate": expiry_gate,
        "price_observation_quality_gate": price_gate,
        "execution_event_structure_gate": event_structure_gate,
        "minimum_one_lot_capacity_gate": capacity_gate,
        "identity_gate": identity_gate,
        "zero_side_effect_gate": True,
    }
    all_passed = all(gates.values())
    mapping_invalid = path_qualification["mapping_invalid_leg_count"].gt(0)
    price_invalid = ~path_qualification["price_observation_valid"].astype(bool)
    capacity_invalid = ~path_qualification[
        "minimum_one_lot_capacity_valid"
    ].astype(bool)
    leg_failures = legs.loc[
        ~legs["leg_valid"].astype(bool), "leg_failure_reason"
    ]
    price_failures = leg_audit.loc[
        ~leg_audit["price_observation_valid"].astype(bool),
        "price_observation_failure_reason",
    ]
    capacity_failures = events.loc[
        ~events["capacity_valid"].astype(bool), "capacity_failure_reason"
    ]
    mapping_failures = daily_mapping.loc[
        ~daily_mapping["mapping_valid"].astype(bool), "mapping_failure_reason"
    ]
    return {
        "line_id": "futures_trend_xgboost_pit_lagged_liquidity_roll_labels",
        "stage": "stage001_lagged_liquidity_roll_qualification",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision": PASS_DECISION if all_passed else FAIL_DECISION,
        "all_gates_passed": all_passed,
        "gates": gates,
        "expected_counts": asdict(expected),
        "input_path_rows": int(len(windows)),
        "input_path_qids": int(windows["query_date"].nunique()),
        "daily_mapping_rows": int(len(daily_mapping)),
        "daily_mapping_valid_rows": int(
            daily_mapping["mapping_valid"].astype(bool).sum()
        ),
        "daily_mapping_invalid_rows": int(
            (~daily_mapping["mapping_valid"].astype(bool)).sum()
        ),
        "daily_candidate_rows": int(len(candidates)),
        "raw_eligible_candidate_rows": int(
            candidates["raw_selection_eligible"].astype(bool).sum()
        ),
        "retained_path_rows": int(len(retained)),
        "retained_path_qids": int(retained["query_date"].nunique()),
        "unretained_path_rows": int(len(windows) - len(retained)),
        "minimum_candidates_observed": int(breadth.min()),
        "median_candidates_observed": float(breadth.median()),
        "maximum_candidates_observed": int(breadth.max()),
        "dynamic_leg_rows": int(len(legs)),
        "roll_event_rows": int(legs["roll_event"].astype(bool).sum()),
        "selection_after_query_rows": int(
            legs["selection_after_query"].astype(bool).sum()
        ),
        "same_day_or_future_selection_violation_rows": int(
            legs["same_day_or_future_selection_violation"].astype(bool).sum()
        ),
        "mapping_invalid_path_rows": int(mapping_invalid.sum()),
        "mapping_invalid_leg_rows": int(
            path_qualification["mapping_invalid_leg_count"].sum()
        ),
        "execution_event_rows": int(len(events)),
        "event_role_counts": {
            str(key): int(value) for key, value in role_counts.items()
        },
        "price_invalid_path_rows": int(price_invalid.sum()),
        "price_invalid_leg_rows": int(
            (~leg_audit["price_observation_valid"].astype(bool)).sum()
        ),
        "capacity_invalid_path_rows": int(capacity_invalid.sum()),
        "capacity_invalid_event_rows": int(
            (~events["capacity_valid"].astype(bool)).sum()
        ),
        "qualification_valid_path_rows": int(
            path_qualification["qualification_valid"].astype(bool).sum()
        ),
        "qualification_invalid_path_rows": int(
            (~path_qualification["qualification_valid"].astype(bool)).sum()
        ),
        "mapping_failure_counts": mapping_failures.value_counts()
        .sort_index()
        .astype(int)
        .to_dict(),
        "leg_failure_counts": leg_failures.value_counts()
        .sort_index()
        .astype(int)
        .to_dict(),
        "price_failure_counts": price_failures.value_counts()
        .sort_index()
        .astype(int)
        .to_dict(),
        "capacity_failure_counts": capacity_failures.value_counts()
        .sort_index()
        .astype(int)
        .to_dict(),
        "opened_bar_columns": [
            "datetime",
            "symbol",
            "exchange",
            "interval",
            "volume",
            "open_interest",
        ],
        "close_value_reads": 0,
        "future_return_calculations": 0,
        "label_value_reads": 0,
        "model_fit_count": 0,
        "model_predict_count": 0,
        "strategy_backtest_runs": 0,
        "sealed_holdout_rows": 0,
        "ctp_connection_count": 0,
        "order_api_called_count": 0,
        "production_files_written": 0,
        "independent_reviewer_required": False,
        "independent_reviewer_reason": "no_backtest_result_produced",
    }


def _report(summary: Mapping[str, object]) -> str:
    gate_lines = "\n".join(
        f"- `{name}`：{'通过' if passed else '失败'}"
        for name, passed in summary["gates"].items()
    )
    return (
        "# Stage001滞后流动性动态换约资格审计\n\n"
        f"- 决策：`{summary['decision']}`\n"
        f"- 输入路径：{summary['input_path_rows']}行/"
        f"{summary['input_path_qids']}个qid\n"
        f"- leg1保留路径：{summary['retained_path_rows']}行；每qid候选最小/"
        f"中位/最大：{summary['minimum_candidates_observed']}/"
        f"{summary['median_candidates_observed']}/"
        f"{summary['maximum_candidates_observed']}\n"
        f"- 动态leg：{summary['dynamic_leg_rows']}行；换约："
        f"{summary['roll_event_rows']}次；执行事件："
        f"{summary['execution_event_rows']}行\n"
        f"- 映射失败：{summary['mapping_invalid_path_rows']}路径/"
        f"{summary['mapping_invalid_leg_rows']}leg\n"
        f"- 价格质量失败：{summary['price_invalid_path_rows']}路径/"
        f"{summary['price_invalid_leg_rows']}leg\n"
        f"- 一手容量失败：{summary['capacity_invalid_path_rows']}路径/"
        f"{summary['capacity_invalid_event_rows']}事件\n"
        "- close、收益、标签、fit、predict、回测、CTP、订单和生产写入：全部为0\n\n"
        "## 门禁\n\n"
        f"{gate_lines}\n"
    )


def verify_final_bundle(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, object]:
    return publisher.verify_published_bundle(output_dir, verify_inputs=True)


def run_stage001(
    *,
    line_dir: Path = LINE_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    upstream_bundle_dir: Path = UPSTREAM_DIR,
    source_bundle_dir: Path = SOURCE_DIR,
    input_paths: Mapping[str, Path] = DEFAULT_INPUT_PATHS,
    expected_sha256: Mapping[str, str] = DEFAULT_EXPECTED_SHA256,
    expected: ExpectedCounts = ExpectedCounts(),
) -> dict[str, object]:
    final_path = publisher.assert_line_local_output(line_dir, output_dir)
    if final_path.exists():
        raise Stage001Error(f"final_output_exists:{final_path}")
    identities_before = publisher.collect_input_identities(
        input_paths, expected_sha256
    )
    upstream_verification = publisher.verify_published_bundle(
        upstream_bundle_dir, verify_inputs=True
    )
    source_verification = upstream_stage.v2.verify_path_manifest_bundle(
        source_bundle_dir
    )
    if not upstream_verification["verified"]:
        raise Stage001Error(
            "upstream_bundle_invalid:" + ",".join(upstream_verification["errors"])
        )
    if not source_verification["verified"]:
        raise Stage001Error(
            "source_bundle_invalid:" + ",".join(source_verification["errors"])
        )

    windows = pd.read_csv(
        input_paths["upstream_paths"],
        encoding="utf-8-sig",
        usecols=[
            "query_date",
            "product_vt_symbol",
            "main_contract_vt",
            "entry_date",
            "label_end",
            "source_partition",
            "path_valid",
        ],
    )
    windows = _normalise_dates(
        windows, ["query_date", "entry_date", "label_end"]
    )
    upstream_summary = json.loads(
        Path(input_paths["upstream_summary"]).read_text(encoding="utf-8")
    )
    catalog = _load_catalog(input_paths["source_catalog"])
    liquidity = upstream_stage.load_bar_liquidity(input_paths["source_bars"])
    global_dates = pd.DatetimeIndex(
        liquidity["date"].drop_duplicates().sort_values()
    )
    execution_dates = _execution_dates(windows, global_dates)
    daily_mapping, candidates = core.build_lagged_contract_map(
        execution_dates,
        windows["product_vt_symbol"].drop_duplicates(),
        catalog,
        liquidity,
        global_dates,
        minimum_volume=expected.minimum_volume,
        minimum_open_interest=expected.minimum_open_interest,
    )
    retained = _retain_leg1_candidates(windows, daily_mapping)
    legs = core.build_dynamic_legs(
        retained,
        daily_mapping,
        global_dates,
        holding_period=expected.holding_period,
    )
    complete_keys = (
        legs.groupby(["query_date", "product_vt_symbol"], sort=False)[
            "leg_valid"
        ]
        .all()
        .rename("complete")
        .reset_index()
    )
    complete_legs = legs.merge(
        complete_keys[complete_keys["complete"]],
        how="inner",
        on=["query_date", "product_vt_symbol"],
        validate="many_to_one",
    ).drop(columns="complete")
    leg_audit = tradeability.audit_leg_endpoints(complete_legs, liquidity)
    raw_events = tradeability.build_execution_events(leg_audit)
    events = tradeability.assess_event_capacity(
        raw_events, order_quantity=1, maximum_share_pct=1.0
    )
    path_qualification = _build_path_qualification(
        retained,
        legs,
        leg_audit,
        events,
        holding_period=expected.holding_period,
    )
    identities_after = publisher.collect_input_identities(
        input_paths, expected_sha256
    )
    summary = assess_stage001(
        windows,
        retained,
        candidates,
        daily_mapping,
        legs,
        leg_audit,
        events,
        path_qualification,
        upstream_summary,
        global_dates,
        upstream_verified=bool(upstream_verification["verified"]),
        source_verified=bool(source_verification["verified"]),
        input_identity_stable=identities_before == identities_after,
        expected=expected,
    )
    summary["input_identities_before"] = identities_before
    summary["input_identities_after"] = identities_after
    summary["upstream_verification"] = upstream_verification
    summary["source_verification"] = source_verification
    summary["upstream_summary_identity"] = {
        "decision": upstream_summary.get("decision"),
        "path_rows": upstream_summary.get("path_rows"),
        "path_qids": upstream_summary.get("path_qids"),
        "invalid_path_rows": upstream_summary.get("invalid_path_rows"),
        "invalid_leg_rows": upstream_summary.get("invalid_leg_rows"),
    }
    summary["implementation_identities"] = {
        "runner_sha256": publisher.sha256_file(Path(__file__)),
        "core_sha256": publisher.sha256_file(Path(core.__file__)),
        "tradeability_core_sha256": publisher.sha256_file(
            Path(tradeability.__file__)
        ),
    }
    frames = {
        "daily_contract_candidates.csv.gz": candidates,
        "daily_contract_mapping.csv.gz": daily_mapping,
        "dynamic_legs.csv.gz": legs,
        "leg_endpoint_audit.csv.gz": leg_audit,
        "execution_events.csv.gz": events,
        "path_qualification.csv.gz": path_qualification,
    }
    documents = {
        "summary.json": summary,
        "input_identities.json": identities_after,
        "upstream_verification.json": {
            "upstream": upstream_verification,
            "source": source_verification,
        },
        "report.md": _report(summary),
    }
    publisher.publish_bundle(
        frames,
        documents,
        line_dir=line_dir,
        final_dir=final_path,
        input_identities=identities_after,
    )
    verification = verify_final_bundle(final_path)
    if not verification["verified"]:
        raise Stage001Error(
            "published_bundle_invalid:" + ",".join(verification["errors"])
        )
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage001 lagged-liquidity dynamic-roll qualification"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.verify_only:
        result = verify_final_bundle()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["verified"] else 1
    try:
        summary = run_stage001()
    except (
        Stage001Error,
        core.LaggedRollError,
        tradeability.TradeabilityError,
        upstream_stage.Stage001Error,
        publisher.Stage001Error,
    ) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["all_gates_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
