"""Stage001 causal universe qualification from trailing execution history."""

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
PRIOR_DYNAMIC_TOOLS = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_lagged_liquidity_roll_labels/tools"
)
if str(PRIOR_DYNAMIC_TOOLS) not in sys.path:
    sys.path.insert(0, str(PRIOR_DYNAMIC_TOOLS))

import stage001_lagged_liquidity_roll as dynamic_stage

import trailing_horizon_tradeability as core


dynamic_core = dynamic_stage.core
tradeability = dynamic_stage.tradeability
publisher = dynamic_stage.publisher
UPSTREAM_DIR = dynamic_stage.UPSTREAM_DIR
SOURCE_DIR = dynamic_stage.SOURCE_DIR
PRIOR_DYNAMIC_DIR = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_lagged_liquidity_roll_labels/"
    "artifacts/stage001_lagged_liquidity_roll"
)
UPSTREAM_PASS_DECISION = dynamic_stage.UPSTREAM_PASS_DECISION
PRIOR_DYNAMIC_FAIL_DECISION = dynamic_stage.FAIL_DECISION
PRIOR_DYNAMIC_CORE_SHA256 = (
    "03fd08ce0e04a7a779b57adb14a27a32b4a0544392bdffe896d8b81833089496"
)
PASS_DECISION = (
    "stage001_trailing_horizon_tradeability_pass_allow_label_value_"
    "preregistration_only"
)
FAIL_DECISION = (
    "stage001_trailing_horizon_tradeability_fail_close_no_label_values"
)
DEFAULT_OUTPUT_DIR = (
    LINE_DIR / "artifacts/stage001_trailing_horizon_tradeability"
)
DEFAULT_INPUT_PATHS = {
    "upstream_manifest": UPSTREAM_DIR / "artifact_manifest.json",
    "upstream_paths": UPSTREAM_DIR / "expiry_safe_paths.csv.gz",
    "upstream_summary": UPSTREAM_DIR / "summary.json",
    "source_manifest": SOURCE_DIR / "artifact_manifest.json",
    "source_catalog": SOURCE_DIR / "asof_contract_catalog.csv.gz",
    "source_bars": SOURCE_DIR / "normalised_daily_bars.csv.gz",
    "prior_dynamic_manifest": PRIOR_DYNAMIC_DIR / "artifact_manifest.json",
    "prior_dynamic_summary": PRIOR_DYNAMIC_DIR / "summary.json",
}
DEFAULT_EXPECTED_SHA256 = {
    "upstream_manifest": "9f768fc6de7ccd3eb240c29f0444249bd333356d756b137197dc78e4f5f44d76",
    "upstream_paths": "a3f2c1249085b872372f8f0aca2d1cbaf77ecb8a7bc04056f9118f077c16748e",
    "upstream_summary": "6f994dd88896781a7f1af9e9760890540445dc8539a6349ae416b82bcf37283f",
    "source_manifest": "e3894cd20114182e9b3a9e986ed5e0310fe264de06368b5efe1b5efb6903681a",
    "source_catalog": "c733e5d85bab4349efb9bd25e2afdd689562718ffd608bff9a4f11964ab13bfc",
    "source_bars": "f2cf98dbfde2e18031697d598c3147c0ee8f15d3feb6ab935b92bc44a919ece4",
    "prior_dynamic_manifest": "452bd28ff22f66dbd987426f23252df875e5c4011b702eca7d1e511d9330f4e1",
    "prior_dynamic_summary": "61c36ba8bedfa77ae4ac681fa151724db5235ff847f9b3dc9f243ccdd52be93e",
}


@dataclass(frozen=True)
class ExpectedCounts:
    path_rows: int = 56_272
    path_qids: int = 1_046
    holding_period: int = 20
    trailing_lookback: int = 20
    minimum_candidates_per_qid: int = 30
    minimum_volume: float = 100.0
    minimum_open_interest: float = 100.0


class Stage001Error(RuntimeError):
    pass


def _normalise_dates(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    return dynamic_stage._normalise_dates(frame, columns)


def _audit_complete_paths(
    legs: pd.DataFrame, liquidity: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    keys = ["query_date", "product_vt_symbol"]
    complete = (
        legs.groupby(keys, sort=False)["leg_valid"]
        .all()
        .rename("complete")
        .reset_index()
    )
    complete_legs = legs.merge(
        complete[complete["complete"]],
        how="inner",
        on=keys,
        validate="many_to_one",
    ).drop(columns="complete")
    audit = tradeability.audit_leg_endpoints(complete_legs, liquidity)
    raw_events = tradeability.build_execution_events(audit)
    events = tradeability.assess_event_capacity(
        raw_events, order_quantity=1, maximum_share_pct=1.0
    )
    return audit, events


def _mapping_calendar_gate(
    mapping: pd.DataFrame,
    global_dates: pd.DatetimeIndex,
    product_count: int,
) -> bool:
    execution_dates = pd.DatetimeIndex(
        mapping["execution_date"].drop_duplicates().sort_values()
    )
    positions = global_dates.get_indexer(execution_dates)
    if (
        (positions < 1).any()
        or (positions >= len(global_dates) - 1).any()
        or len(mapping) != len(execution_dates) * product_count
        or mapping.duplicated(["execution_date", "product_vt_symbol"]).any()
    ):
        return False
    expected_selection = pd.Series(
        global_dates.take(positions - 1), index=execution_dates
    )
    expected_return = pd.Series(
        global_dates.take(positions + 1), index=execution_dates
    )
    return bool(
        mapping["selection_date"].eq(
            mapping["execution_date"].map(expected_selection)
        ).all()
        and mapping["return_date"].eq(
            mapping["execution_date"].map(expected_return)
        ).all()
    )


def assess_stage001(
    windows: pd.DataFrame,
    trailing_windows: pd.DataFrame,
    daily_candidates: pd.DataFrame,
    daily_mapping: pd.DataFrame,
    historical_legs: pd.DataFrame,
    historical_audit: pd.DataFrame,
    historical_events: pd.DataFrame,
    universe_qualification: pd.DataFrame,
    selected_windows: pd.DataFrame,
    future_legs: pd.DataFrame,
    future_audit: pd.DataFrame,
    future_events: pd.DataFrame,
    future_path_qualification: pd.DataFrame,
    upstream_summary: Mapping[str, object],
    prior_dynamic_summary: Mapping[str, object],
    global_dates: pd.DatetimeIndex,
    *,
    upstream_verified: bool,
    source_verified: bool,
    prior_dynamic_verified: bool,
    input_identity_stable: bool,
    expected: ExpectedCounts = ExpectedCounts(),
) -> dict[str, object]:
    keys = ["query_date", "product_vt_symbol"]
    upstream_gate = bool(
        upstream_summary.get("decision") == UPSTREAM_PASS_DECISION
        and int(upstream_summary.get("path_rows", -1)) == expected.path_rows
        and int(upstream_summary.get("path_qids", -1)) == expected.path_qids
        and int(upstream_summary.get("invalid_path_rows", -1)) == 0
        and int(upstream_summary.get("invalid_leg_rows", -1)) == 0
    )
    prior_implementation = prior_dynamic_summary.get(
        "implementation_identities", {}
    )
    prior_dynamic_gate = bool(
        prior_dynamic_summary.get("decision") == PRIOR_DYNAMIC_FAIL_DECISION
        and prior_dynamic_summary.get("close_value_reads") == 0
        and prior_dynamic_summary.get("model_fit_count") == 0
        and prior_dynamic_summary.get("strategy_backtest_runs") == 0
        and isinstance(prior_implementation, dict)
        and prior_implementation.get("core_sha256")
        == PRIOR_DYNAMIC_CORE_SHA256
    )
    frozen_window_gate = bool(
        len(windows) == expected.path_rows
        and windows["query_date"].nunique() == expected.path_qids
        and windows["path_valid"].astype(bool).all()
        and not windows.duplicated(keys).any()
    )
    trailing_window_gate = bool(
        len(trailing_windows) == len(windows)
        and trailing_windows["history_return_leg_count"].eq(
            expected.trailing_lookback
        ).all()
        and trailing_windows["label_end"].eq(
            trailing_windows["query_date"]
        ).all()
    )
    mapping_calendar_gate = _mapping_calendar_gate(
        daily_mapping,
        global_dates,
        windows["product_vt_symbol"].nunique(),
    )
    selected_mapping_candidates = daily_candidates[
        daily_candidates["selected"].astype(bool)
    ]
    candidate_mapping_gate = bool(
        not daily_candidates["future_or_same_day_source"].astype(bool).any()
        and selected_mapping_candidates["raw_selection_eligible"]
        .astype(bool)
        .all()
        and selected_mapping_candidates["monotone_selection_eligible"]
        .astype(bool)
        .all()
    )
    historical_causality_gate = bool(
        historical_legs["selection_date"]
        .lt(historical_legs["previous_date"])
        .all()
        and historical_legs["return_date"]
        .le(historical_legs["query_date"])
        .all()
        and not universe_qualification[
            "historical_future_observation_violation"
        ]
        .astype(bool)
        .any()
    )
    eligible = universe_qualification[
        universe_qualification["universe_eligible"].astype(bool)
    ]
    universe_semantics_gate = bool(
        len(selected_windows) == len(eligible)
        and not selected_windows.duplicated(keys).any()
        and selected_windows[keys]
        .merge(eligible[keys], on=keys, how="outer", indicator=True)
        ["_merge"]
        .eq("both")
        .all()
        and eligible["historical_tradeability_valid"].astype(bool).all()
        and eligible["future_leg1_mapping_valid"].astype(bool).all()
    )
    query_dates = pd.DatetimeIndex(windows["query_date"].drop_duplicates())
    breadth = selected_windows.groupby("query_date", sort=False).size().reindex(
        query_dates, fill_value=0
    )
    candidate_breadth_gate = bool(
        len(breadth) == expected.path_qids
        and breadth.min() >= expected.minimum_candidates_per_qid
    )
    future_groups = future_legs.groupby(keys, sort=False)
    future_leg_structure_gate = bool(
        len(future_legs) == len(selected_windows) * expected.holding_period
        and future_groups.size().eq(expected.holding_period).all()
        and not future_legs.duplicated([*keys, "leg_index"]).any()
    )
    future_complete_mapping_gate = bool(
        future_legs["mapping_present"].astype(bool).all()
        and future_legs["mapping_valid"].fillna(False).astype(bool).all()
        and future_legs["selected_contract_vt"].notna().all()
    )
    future_strict_lag_gate = bool(
        future_legs["exact_previous_session"].astype(bool).all()
        and not future_legs["same_day_or_future_selection_violation"]
        .astype(bool)
        .any()
    )
    future_expiry_gate = bool(
        future_legs["expiry_valid"].astype(bool).all()
        and dynamic_stage._monotone_expiry(daily_mapping)
    )
    future_price_gate = bool(
        len(future_audit) == len(future_legs)
        and future_audit["price_observation_valid"].astype(bool).all()
    )
    future_event_structure_gate = bool(
        future_path_qualification["execution_event_structure_valid"]
        .astype(bool)
        .all()
    )
    future_capacity_gate = bool(
        future_event_structure_gate
        and future_events["capacity_valid"].astype(bool).all()
        and future_path_qualification["minimum_one_lot_capacity_valid"]
        .astype(bool)
        .all()
    )
    identity_gate = bool(
        len(universe_qualification) == len(windows)
        and not universe_qualification.duplicated(keys).any()
        and len(future_path_qualification) == len(selected_windows)
        and not future_path_qualification.duplicated(keys).any()
    )
    gates = {
        "upstream_manifest_gate": bool(upstream_verified),
        "source_manifest_gate": bool(source_verified),
        "prior_dynamic_manifest_gate": bool(prior_dynamic_verified),
        "input_identity_gate": bool(input_identity_stable),
        "upstream_decision_gate": upstream_gate,
        "prior_dynamic_identity_gate": prior_dynamic_gate,
        "frozen_window_gate": frozen_window_gate,
        "trailing_window_structure_gate": trailing_window_gate,
        "daily_mapping_calendar_gate": mapping_calendar_gate,
        "causal_mapping_candidate_gate": candidate_mapping_gate,
        "historical_causality_gate": historical_causality_gate,
        "universe_selection_semantics_gate": universe_semantics_gate,
        "candidate_breadth_gate": candidate_breadth_gate,
        "future_leg_structure_gate": future_leg_structure_gate,
        "future_complete_mapping_gate": future_complete_mapping_gate,
        "future_strict_lag_gate": future_strict_lag_gate,
        "future_monotone_expiry_gate": future_expiry_gate,
        "future_price_observation_quality_gate": future_price_gate,
        "future_execution_event_structure_gate": future_event_structure_gate,
        "future_minimum_one_lot_capacity_gate": future_capacity_gate,
        "identity_gate": identity_gate,
        "zero_side_effect_gate": True,
    }
    all_passed = all(gates.values())
    historical_rejections = universe_qualification.loc[
        ~universe_qualification["universe_eligible"].astype(bool),
        "universe_rejection_reason",
    ]
    future_valid = future_path_qualification["qualification_valid"].astype(bool)
    future_mapping_bad = future_path_qualification[
        "mapping_invalid_leg_count"
    ].gt(0)
    future_price_bad = ~future_path_qualification[
        "price_observation_valid"
    ].astype(bool)
    future_capacity_bad = ~future_path_qualification[
        "minimum_one_lot_capacity_valid"
    ].astype(bool)
    event_role_counts = (
        future_events["event_role"].value_counts().astype(int).to_dict()
    )
    return {
        "line_id": (
            "futures_trend_xgboost_pit_trailing_horizon_tradeability_universe"
        ),
        "stage": "stage001_trailing_horizon_tradeability_qualification",
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
        "daily_candidate_rows": int(len(daily_candidates)),
        "historical_leg_rows": int(len(historical_legs)),
        "historical_audited_leg_rows": int(len(historical_audit)),
        "historical_execution_event_rows": int(len(historical_events)),
        "historical_eligible_path_rows": int(
            universe_qualification["historical_tradeability_valid"]
            .astype(bool)
            .sum()
        ),
        "historical_rejected_path_rows": int(len(windows) - len(selected_windows)),
        "historical_future_observation_violation_rows": int(
            universe_qualification["historical_future_observation_violation"]
            .astype(bool)
            .sum()
        ),
        "historical_rejection_counts": historical_rejections.value_counts()
        .sort_index()
        .astype(int)
        .to_dict(),
        "selected_path_rows": int(len(selected_windows)),
        "selected_path_qids": int(selected_windows["query_date"].nunique()),
        "minimum_candidates_observed": int(breadth.min()),
        "median_candidates_observed": float(breadth.median()),
        "maximum_candidates_observed": int(breadth.max()),
        "future_dynamic_leg_rows": int(len(future_legs)),
        "future_roll_event_rows": int(
            future_legs["roll_event"].astype(bool).sum()
        ),
        "future_selection_after_query_rows": int(
            future_legs["selection_after_query"].astype(bool).sum()
        ),
        "future_same_day_or_future_selection_violation_rows": int(
            future_legs["same_day_or_future_selection_violation"]
            .astype(bool)
            .sum()
        ),
        "future_execution_event_rows": int(len(future_events)),
        "future_event_role_counts": {
            str(key): int(value) for key, value in event_role_counts.items()
        },
        "future_mapping_invalid_path_rows": int(future_mapping_bad.sum()),
        "future_mapping_invalid_leg_rows": int(
            future_path_qualification["mapping_invalid_leg_count"].sum()
        ),
        "future_price_invalid_path_rows": int(future_price_bad.sum()),
        "future_price_invalid_leg_rows": int(
            (~future_audit["price_observation_valid"].astype(bool)).sum()
        ),
        "future_capacity_invalid_path_rows": int(future_capacity_bad.sum()),
        "future_capacity_invalid_event_rows": int(
            (~future_events["capacity_valid"].astype(bool)).sum()
        ),
        "future_qualified_path_rows": int(future_valid.sum()),
        "future_unqualified_path_rows": int((~future_valid).sum()),
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
        "# Stage001历史镜像可成交宇宙资格审计\n\n"
        f"- 决策：`{summary['decision']}`\n"
        f"- 输入：{summary['input_path_rows']}条/"
        f"{summary['input_path_qids']}个qid\n"
        f"- 历史合格并入池：{summary['selected_path_rows']}条；每qid最小/"
        f"中位/最大：{summary['minimum_candidates_observed']}/"
        f"{summary['median_candidates_observed']}/"
        f"{summary['maximum_candidates_observed']}\n"
        f"- 未来合格：{summary['future_qualified_path_rows']}条；不合格："
        f"{summary['future_unqualified_path_rows']}条\n"
        f"- 未来映射失败：{summary['future_mapping_invalid_path_rows']}路径/"
        f"{summary['future_mapping_invalid_leg_rows']}leg\n"
        f"- 未来价格失败：{summary['future_price_invalid_path_rows']}路径/"
        f"{summary['future_price_invalid_leg_rows']}leg\n"
        f"- 未来容量失败：{summary['future_capacity_invalid_path_rows']}路径/"
        f"{summary['future_capacity_invalid_event_rows']}事件\n"
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
    prior_dynamic_bundle_dir: Path = PRIOR_DYNAMIC_DIR,
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
    source_verification = dynamic_stage.upstream_stage.v2.verify_path_manifest_bundle(
        source_bundle_dir
    )
    prior_dynamic_verification = publisher.verify_published_bundle(
        prior_dynamic_bundle_dir, verify_inputs=True
    )
    if not upstream_verification["verified"]:
        raise Stage001Error(
            "upstream_bundle_invalid:" + ",".join(upstream_verification["errors"])
        )
    if not source_verification["verified"]:
        raise Stage001Error(
            "source_bundle_invalid:" + ",".join(source_verification["errors"])
        )
    if not prior_dynamic_verification["verified"]:
        raise Stage001Error(
            "prior_dynamic_bundle_invalid:"
            + ",".join(prior_dynamic_verification["errors"])
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
    prior_dynamic_summary = json.loads(
        Path(input_paths["prior_dynamic_summary"]).read_text(encoding="utf-8")
    )
    catalog = dynamic_stage._load_catalog(input_paths["source_catalog"])
    liquidity = dynamic_stage.upstream_stage.load_bar_liquidity(
        input_paths["source_bars"]
    )
    global_dates = pd.DatetimeIndex(
        liquidity["date"].drop_duplicates().sort_values()
    )
    trailing_windows = core.build_trailing_windows(
        windows, global_dates, lookback=expected.trailing_lookback
    )
    execution_dates = global_dates[1:-1]
    daily_mapping, daily_candidates = dynamic_core.build_lagged_contract_map(
        execution_dates,
        windows["product_vt_symbol"].drop_duplicates(),
        catalog,
        liquidity,
        global_dates,
        minimum_volume=expected.minimum_volume,
        minimum_open_interest=expected.minimum_open_interest,
    )
    historical_legs = dynamic_core.build_dynamic_legs(
        trailing_windows,
        daily_mapping,
        global_dates,
        holding_period=expected.trailing_lookback,
    )
    historical_audit, historical_events = _audit_complete_paths(
        historical_legs, liquidity
    )
    universe_qualification, selected_windows = (
        core.build_universe_qualification(
            windows,
            historical_legs,
            historical_audit,
            historical_events,
            daily_mapping,
            lookback=expected.trailing_lookback,
        )
    )
    future_legs = dynamic_core.build_dynamic_legs(
        selected_windows,
        daily_mapping,
        global_dates,
        holding_period=expected.holding_period,
    )
    future_audit, future_events = _audit_complete_paths(
        future_legs, liquidity
    )
    future_path_qualification = dynamic_stage._build_path_qualification(
        selected_windows,
        future_legs,
        future_audit,
        future_events,
        holding_period=expected.holding_period,
    )
    identities_after = publisher.collect_input_identities(
        input_paths, expected_sha256
    )
    summary = assess_stage001(
        windows,
        trailing_windows,
        daily_candidates,
        daily_mapping,
        historical_legs,
        historical_audit,
        historical_events,
        universe_qualification,
        selected_windows,
        future_legs,
        future_audit,
        future_events,
        future_path_qualification,
        upstream_summary,
        prior_dynamic_summary,
        global_dates,
        upstream_verified=bool(upstream_verification["verified"]),
        source_verified=bool(source_verification["verified"]),
        prior_dynamic_verified=bool(prior_dynamic_verification["verified"]),
        input_identity_stable=identities_before == identities_after,
        expected=expected,
    )
    summary["input_identities_before"] = identities_before
    summary["input_identities_after"] = identities_after
    summary["upstream_verification"] = upstream_verification
    summary["source_verification"] = source_verification
    summary["prior_dynamic_verification"] = prior_dynamic_verification
    summary["upstream_summary_identity"] = {
        "decision": upstream_summary.get("decision"),
        "path_rows": upstream_summary.get("path_rows"),
        "path_qids": upstream_summary.get("path_qids"),
        "invalid_path_rows": upstream_summary.get("invalid_path_rows"),
        "invalid_leg_rows": upstream_summary.get("invalid_leg_rows"),
    }
    summary["prior_dynamic_summary_identity"] = {
        "decision": prior_dynamic_summary.get("decision"),
        "core_sha256": prior_dynamic_summary.get(
            "implementation_identities", {}
        ).get("core_sha256"),
        "close_value_reads": prior_dynamic_summary.get("close_value_reads"),
        "model_fit_count": prior_dynamic_summary.get("model_fit_count"),
        "strategy_backtest_runs": prior_dynamic_summary.get(
            "strategy_backtest_runs"
        ),
    }
    summary["implementation_identities"] = {
        "runner_sha256": publisher.sha256_file(Path(__file__)),
        "core_sha256": publisher.sha256_file(Path(core.__file__)),
        "dynamic_core_sha256": publisher.sha256_file(Path(dynamic_core.__file__)),
        "tradeability_core_sha256": publisher.sha256_file(
            Path(tradeability.__file__)
        ),
    }
    frames = {
        "daily_contract_candidates.csv.gz": daily_candidates,
        "daily_contract_mapping.csv.gz": daily_mapping,
        "historical_legs.csv.gz": historical_legs,
        "historical_leg_audit.csv.gz": historical_audit,
        "historical_execution_events.csv.gz": historical_events,
        "universe_qualification.csv.gz": universe_qualification,
        "selected_windows.csv.gz": selected_windows,
        "future_dynamic_legs.csv.gz": future_legs,
        "future_leg_audit.csv.gz": future_audit,
        "future_execution_events.csv.gz": future_events,
        "future_path_qualification.csv.gz": future_path_qualification,
    }
    documents = {
        "summary.json": summary,
        "input_identities.json": identities_after,
        "upstream_verification.json": {
            "upstream": upstream_verification,
            "source": source_verification,
            "prior_dynamic": prior_dynamic_verification,
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
        description="Stage001 trailing-horizon tradeability qualification"
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
        core.TrailingUniverseError,
        dynamic_core.LaggedRollError,
        tradeability.TradeabilityError,
        dynamic_stage.Stage001Error,
        publisher.Stage001Error,
    ) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["all_gates_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
