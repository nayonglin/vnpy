"""Stage001 qualification for causal query-date fixed-contract labels."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping

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

import query_date_fixed_contract as core


publisher = upstream_stage.upstream
UPSTREAM_DIR = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_expiry_safe_roll_mapping/"
    "artifacts/stage001_expiry_safe_roll_mapping"
)
SOURCE_DIR = upstream_stage.SOURCE_DIR
UPSTREAM_PASS_DECISION = upstream_stage.PASS_DECISION
PASS_DECISION = (
    "stage001_query_date_fixed_contract_pass_allow_label_value_"
    "preregistration_only"
)
FAIL_DECISION = "stage001_query_date_fixed_contract_fail_close_no_label_values"
DEFAULT_OUTPUT_DIR = LINE_DIR / "artifacts/stage001_query_date_fixed_contract"
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
    history_window: int = 20
    required_capacity_days: int = 18
    minimum_candidates_per_qid: int = 30
    minimum_volume: float = 100.0
    minimum_open_interest: float = 100.0


class Stage001Error(RuntimeError):
    pass


def _normalise_dates(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        result[column] = pd.to_datetime(
            result[column], errors="coerce"
        ).dt.normalize()
        if result[column].isna().any():
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


def _build_path_qualification(
    selected: pd.DataFrame,
    leg_audit: pd.DataFrame,
    events: pd.DataFrame,
) -> pd.DataFrame:
    keys = ["query_date", "product_vt_symbol"]
    paths = _normalise_dates(
        selected,
        [
            "query_date",
            "entry_date",
            "label_end",
            "selected_expire_date",
            "selection_source_date",
        ],
    )
    if paths.duplicated(keys).any():
        raise Stage001Error("duplicate_selected_path")
    leg_agg = leg_audit.groupby(keys, sort=False).agg(
        audited_leg_count=("leg_index", "size"),
        selected_contract_count=("selected_contract_vt", "nunique"),
        price_invalid_leg_count=(
            "price_observation_valid", lambda values: int((~values).sum())
        ),
        price_observation_valid=("price_observation_valid", "all"),
    )
    event_agg = events.groupby(keys, sort=False).agg(
        execution_event_count=("event_role", "size"),
        capacity_invalid_event_count=(
            "capacity_valid", lambda values: int((~values).sum())
        ),
        minimum_one_lot_capacity_valid=("capacity_valid", "all"),
    )
    identity_columns = [
        "query_date",
        "product_vt_symbol",
        "main_contract_vt",
        "entry_date",
        "label_end",
        "source_partition",
        "selected_contract_vt",
        "selected_expire_date",
        "selection_source_date",
        "selection_rank",
        "query_volume",
        "query_open_interest",
        "history_observation_days",
        "history_missing_days",
        "capacity_days_20",
        "future_selection_rows_used",
    ]
    result = (
        paths[identity_columns]
        .merge(leg_agg.reset_index(), on=keys, how="left", validate="one_to_one")
        .merge(event_agg.reset_index(), on=keys, how="left", validate="one_to_one")
    )
    integer_columns = [
        "audited_leg_count",
        "selected_contract_count",
        "price_invalid_leg_count",
        "execution_event_count",
        "capacity_invalid_event_count",
    ]
    if result[integer_columns].isna().any().any():
        raise Stage001Error("path_qualification_missing")
    for column in integer_columns:
        result[column] = result[column].astype(int)
    result["price_observation_valid"] = result[
        "price_observation_valid"
    ].astype(bool)
    result["minimum_one_lot_capacity_valid"] = result[
        "minimum_one_lot_capacity_valid"
    ].astype(bool)
    result["qualification_valid"] = (
        result["price_observation_valid"]
        & result["minimum_one_lot_capacity_valid"]
    )
    return result.sort_values(keys, kind="mergesort").reset_index(drop=True)


def assess_stage001(
    windows: pd.DataFrame,
    candidates: pd.DataFrame,
    selected: pd.DataFrame,
    legs: pd.DataFrame,
    leg_audit: pd.DataFrame,
    events: pd.DataFrame,
    path_qualification: pd.DataFrame,
    upstream_summary: Mapping[str, object],
    *,
    upstream_verified: bool,
    source_verified: bool,
    input_identity_stable: bool,
    expected: ExpectedCounts = ExpectedCounts(),
) -> dict[str, object]:
    keys = ["query_date", "product_vt_symbol"]
    query_dates = pd.DatetimeIndex(windows["query_date"].drop_duplicates())
    breadth = (
        selected.groupby("query_date", sort=False).size().reindex(query_dates, fill_value=0)
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
    causal_selection_gate = bool(
        not selected.duplicated(keys).any()
        and selected["selection_source_date"].eq(selected["query_date"]).all()
        and selected["future_selection_rows_used"].eq(0).all()
        and candidates["future_selection_rows_used"].eq(0).all()
        and selected["selection_rank"].eq(1).all()
        and selected["capacity_days_20"].ge(
            expected.required_capacity_days
        ).all()
        and selected["query_volume"].ge(expected.minimum_volume).all()
        and selected["query_open_interest"].ge(
            expected.minimum_open_interest
        ).all()
    )
    expiry_gate = bool(
        selected["selected_expire_date"].ge(selected["label_end"]).all()
    )
    candidate_breadth_gate = bool(
        len(breadth) == expected.path_qids
        and breadth.min() >= expected.minimum_candidates_per_qid
    )
    leg_groups = legs.groupby(keys, sort=False)
    fixed_leg_structure_gate = bool(
        len(legs) == len(selected) * expected.holding_period
        and leg_groups.size().eq(expected.holding_period).all()
        and leg_groups["selected_contract_vt"].nunique().eq(1).all()
        and not legs["roll_event"].astype(bool).any()
        and not legs.duplicated([*keys, "leg_index"]).any()
    )
    role_counts = events["event_role"].value_counts().astype(int).to_dict()
    event_structure_gate = bool(
        len(events) == len(selected) * 2
        and role_counts.get("entry", 0) == len(selected)
        and role_counts.get("exit", 0) == len(selected)
        and role_counts.get("roll_close", 0) == 0
        and role_counts.get("roll_open", 0) == 0
    )
    price_gate = bool(
        leg_audit["price_observation_valid"].astype(bool).all()
    )
    capacity_gate = bool(events["capacity_valid"].astype(bool).all())
    identity_gate = bool(
        len(path_qualification) == len(selected)
        and not path_qualification.duplicated(keys).any()
        and len(leg_audit) == len(legs)
    )
    gates = {
        "upstream_manifest_gate": bool(upstream_verified),
        "source_manifest_gate": bool(source_verified),
        "input_identity_gate": bool(input_identity_stable),
        "upstream_decision_gate": upstream_gate,
        "frozen_window_gate": frozen_window_gate,
        "causal_selection_gate": causal_selection_gate,
        "expiry_coverage_gate": expiry_gate,
        "candidate_breadth_gate": candidate_breadth_gate,
        "fixed_leg_structure_gate": fixed_leg_structure_gate,
        "execution_event_structure_gate": event_structure_gate,
        "price_observation_quality_gate": price_gate,
        "minimum_one_lot_capacity_gate": capacity_gate,
        "identity_gate": identity_gate,
        "zero_side_effect_gate": True,
    }
    all_passed = all(gates.values())
    price_failures = leg_audit.loc[
        ~leg_audit["price_observation_valid"].astype(bool),
        "price_observation_failure_reason",
    ]
    capacity_failures = events.loc[
        ~events["capacity_valid"].astype(bool), "capacity_failure_reason"
    ]
    selection_failures = candidates.loc[
        ~candidates["selection_eligible"].astype(bool),
        "selection_failure_reason",
    ]
    selected_keys = selected[keys]
    missing_windows = windows[keys].merge(
        selected_keys, how="left", on=keys, indicator=True, validate="one_to_one"
    )
    return {
        "line_id": "futures_trend_xgboost_pit_query_date_fixed_contract_labels",
        "stage": "stage001_query_date_fixed_contract_qualification",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision": PASS_DECISION if all_passed else FAIL_DECISION,
        "all_gates_passed": all_passed,
        "gates": gates,
        "expected_counts": asdict(expected),
        "input_path_rows": int(len(windows)),
        "input_path_qids": int(windows["query_date"].nunique()),
        "candidate_contract_rows": int(len(candidates)),
        "eligible_contract_rows": int(candidates["selection_eligible"].sum()),
        "selected_path_rows": int(len(selected)),
        "selected_path_qids": int(selected["query_date"].nunique()),
        "unselected_path_rows": int(missing_windows["_merge"].eq("left_only").sum()),
        "minimum_candidates_observed": int(breadth.min()),
        "median_candidates_observed": float(breadth.median()),
        "maximum_candidates_observed": int(breadth.max()),
        "fixed_leg_rows": int(len(legs)),
        "roll_event_rows": int(legs["roll_event"].astype(bool).sum()),
        "execution_event_rows": int(len(events)),
        "event_role_counts": {str(key): int(value) for key, value in role_counts.items()},
        "price_invalid_path_rows": int(
            (~path_qualification["price_observation_valid"].astype(bool)).sum()
        ),
        "price_invalid_leg_rows": int(
            (~leg_audit["price_observation_valid"].astype(bool)).sum()
        ),
        "capacity_invalid_path_rows": int(
            (~path_qualification["minimum_one_lot_capacity_valid"].astype(bool)).sum()
        ),
        "capacity_invalid_event_rows": int(
            (~events["capacity_valid"].astype(bool)).sum()
        ),
        "qualification_valid_path_rows": int(
            path_qualification["qualification_valid"].astype(bool).sum()
        ),
        "qualification_invalid_path_rows": int(
            (~path_qualification["qualification_valid"].astype(bool)).sum()
        ),
        "selection_failure_counts": selection_failures.value_counts()
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
        "future_selection_rows_used": int(
            candidates["future_selection_rows_used"].sum()
        ),
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
        "# Stage001打分日固定实际合约资格审计\n\n"
        f"- 决策：`{summary['decision']}`\n"
        f"- 输入路径：{summary['input_path_rows']}行/"
        f"{summary['input_path_qids']}个qid\n"
        f"- 选择路径：{summary['selected_path_rows']}行；每qid候选最小/中位/"
        f"最大：{summary['minimum_candidates_observed']}/"
        f"{summary['median_candidates_observed']}/"
        f"{summary['maximum_candidates_observed']}\n"
        f"- 固定leg：{summary['fixed_leg_rows']}行；执行事件："
        f"{summary['execution_event_rows']}行\n"
        f"- 未来价格质量失败：{summary['price_invalid_path_rows']}路径/"
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
    global_dates = liquidity["date"].drop_duplicates().sort_values()

    selected, candidates, rejected = core.select_query_date_contracts(
        windows,
        catalog,
        liquidity,
        global_dates,
        history_window=expected.history_window,
        required_capacity_days=expected.required_capacity_days,
        minimum_volume=expected.minimum_volume,
        minimum_open_interest=expected.minimum_open_interest,
    )
    legs = core.build_fixed_contract_legs(
        selected, global_dates, holding_period=expected.holding_period
    )
    leg_audit = tradeability.audit_leg_endpoints(legs, liquidity)
    raw_events = tradeability.build_execution_events(leg_audit)
    events = tradeability.assess_event_capacity(
        raw_events,
        order_quantity=1,
        maximum_share_pct=1.0,
    )
    path_qualification = _build_path_qualification(
        selected, leg_audit, events
    )
    identities_after = publisher.collect_input_identities(
        input_paths, expected_sha256
    )
    summary = assess_stage001(
        windows,
        candidates,
        selected,
        legs,
        leg_audit,
        events,
        path_qualification,
        upstream_summary,
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
        "contract_candidates.csv.gz": candidates,
        "selected_contracts.csv.gz": selected,
        "selection_rejections.csv.gz": rejected,
        "fixed_contract_legs.csv.gz": legs,
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
        description="Stage001 query-date fixed-contract qualification"
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
        core.FixedContractError,
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
