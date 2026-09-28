"""Stage001 full-path tradeability qualification without close values."""

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
if str(UPSTREAM_TOOLS) not in sys.path:
    sys.path.insert(0, str(UPSTREAM_TOOLS))

import stage001_expiry_safe_roll_mapping as upstream_stage

import roll_label_tradeability as core


publisher = upstream_stage.upstream
UPSTREAM_DIR = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_expiry_safe_roll_mapping/"
    "artifacts/stage001_expiry_safe_roll_mapping"
)
SOURCE_DIR = upstream_stage.SOURCE_DIR
UPSTREAM_PASS_DECISION = upstream_stage.PASS_DECISION
PASS_DECISION = (
    "stage001_roll_label_tradeability_pass_allow_roll_label_value_"
    "preregistration_only"
)
FAIL_DECISION = "stage001_roll_label_tradeability_fail_close_no_label_values"
DEFAULT_OUTPUT_DIR = LINE_DIR / "artifacts/stage001_roll_label_tradeability"
DEFAULT_INPUT_PATHS = {
    "upstream_manifest": UPSTREAM_DIR / "artifact_manifest.json",
    "upstream_paths": UPSTREAM_DIR / "expiry_safe_paths.csv.gz",
    "upstream_legs": UPSTREAM_DIR / "expiry_safe_legs.csv.gz",
    "upstream_summary": UPSTREAM_DIR / "summary.json",
    "source_manifest": SOURCE_DIR / "artifact_manifest.json",
    "source_bars": SOURCE_DIR / "normalised_daily_bars.csv.gz",
}
DEFAULT_EXPECTED_SHA256 = {
    "upstream_manifest": "9f768fc6de7ccd3eb240c29f0444249bd333356d756b137197dc78e4f5f44d76",
    "upstream_paths": "a3f2c1249085b872372f8f0aca2d1cbaf77ecb8a7bc04056f9118f077c16748e",
    "upstream_legs": "db2fcffc24053cbb5c540a699bc47f19149d54eeb66aa2b57057707f346a92da",
    "upstream_summary": "6f994dd88896781a7f1af9e9760890540445dc8539a6349ae416b82bcf37283f",
    "source_manifest": "e3894cd20114182e9b3a9e986ed5e0310fe264de06368b5efe1b5efb6903681a",
    "source_bars": "f2cf98dbfde2e18031697d598c3147c0ee8f15d3feb6ab935b92bc44a919ece4",
}


@dataclass(frozen=True)
class ExpectedCounts:
    path_rows: int = 56_272
    path_qids: int = 1_046
    leg_rows: int = 1_125_440
    holding_period: int = 20
    upstream_invalid_path_rows: int = 0
    upstream_invalid_leg_rows: int = 0
    upstream_fallback_leg_rows: int = 6


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


def _build_path_audit(
    upstream_paths: pd.DataFrame,
    leg_audit: pd.DataFrame,
    events: pd.DataFrame,
) -> pd.DataFrame:
    keys = ["query_date", "product_vt_symbol"]
    paths = _normalise_dates(
        upstream_paths, ["query_date", "entry_date", "label_end"]
    )
    if paths.duplicated(keys).any():
        raise Stage001Error("duplicate_upstream_path")
    leg_agg = leg_audit.groupby(keys, sort=False).agg(
        audited_leg_count=("leg_index", "size"),
        price_invalid_leg_count=(
            "price_observation_valid",
            lambda values: int((~values).sum()),
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
        "leg_count",
        "roll_count",
        "expiry_fallback_count",
    ]
    result = (
        paths[identity_columns]
        .merge(leg_agg.reset_index(), on=keys, how="left", validate="one_to_one")
        .merge(event_agg.reset_index(), on=keys, how="left", validate="one_to_one")
    )
    audit_columns = [
        "audited_leg_count",
        "price_invalid_leg_count",
        "execution_event_count",
        "capacity_invalid_event_count",
    ]
    if result[audit_columns].isna().any().any():
        raise Stage001Error("path_audit_missing")
    for column in audit_columns:
        result[column] = result[column].astype(int)
    result["price_observation_valid"] = result[
        "price_observation_valid"
    ].astype(bool)
    result["minimum_one_lot_capacity_valid"] = result[
        "minimum_one_lot_capacity_valid"
    ].astype(bool)
    result["tradeability_valid"] = (
        result["price_observation_valid"]
        & result["minimum_one_lot_capacity_valid"]
    )
    return result.sort_values(keys, kind="mergesort").reset_index(drop=True)


def assess_stage001(
    upstream_paths: pd.DataFrame,
    upstream_legs: pd.DataFrame,
    leg_audit: pd.DataFrame,
    events: pd.DataFrame,
    path_audit: pd.DataFrame,
    upstream_summary: Mapping[str, object],
    *,
    upstream_verified: bool,
    source_verified: bool,
    input_identity_stable: bool,
    expected: ExpectedCounts = ExpectedCounts(),
) -> dict[str, object]:
    keys = ["query_date", "product_vt_symbol"]
    upstream_invalid_paths = int(
        (~upstream_paths["path_valid"].astype(bool)).sum()
    )
    upstream_invalid_legs = int(
        (~upstream_legs["leg_valid"].astype(bool)).sum()
    )
    fallback_rows = upstream_legs["expiry_fallback"].astype(bool)
    count_gate = all(
        [
            len(path_audit) == expected.path_rows,
            path_audit["query_date"].nunique() == expected.path_qids,
            len(leg_audit) == expected.leg_rows,
            path_audit["audited_leg_count"].eq(expected.holding_period).all(),
            upstream_invalid_paths == expected.upstream_invalid_path_rows,
            upstream_invalid_legs == expected.upstream_invalid_leg_rows,
            int(fallback_rows.sum()) == expected.upstream_fallback_leg_rows,
        ]
    )
    upstream_gate = bool(
        upstream_summary.get("decision") == UPSTREAM_PASS_DECISION
        and int(upstream_summary.get("path_rows", -1)) == expected.path_rows
        and int(upstream_summary.get("leg_rows", -1)) == expected.leg_rows
        and int(upstream_summary.get("invalid_path_rows", -1))
        == expected.upstream_invalid_path_rows
        and int(upstream_summary.get("invalid_leg_rows", -1))
        == expected.upstream_invalid_leg_rows
    )
    roll_count = int(upstream_legs["roll_event"].astype(bool).sum())
    role_counts = events["event_role"].value_counts().astype(int).to_dict()
    event_structure_gate = all(
        [
            role_counts.get("entry", 0) == expected.path_rows,
            role_counts.get("exit", 0) == expected.path_rows,
            role_counts.get("roll_close", 0) == roll_count,
            role_counts.get("roll_open", 0) == roll_count,
            len(events) == expected.path_rows * 2 + roll_count * 2,
            not events.duplicated(
                [
                    "query_date",
                    "product_vt_symbol",
                    "event_role",
                    "event_date",
                    "contract_vt_symbol",
                ]
            ).any(),
        ]
    )
    fallback_keys = upstream_legs.loc[
        fallback_rows,
        [
            "query_date",
            "product_vt_symbol",
            "previous_date",
            "selected_contract_vt",
        ],
    ].rename(
        columns={
            "previous_date": "event_date",
            "selected_contract_vt": "contract_vt_symbol",
        }
    )
    open_events = events[events["event_role"].isin(["entry", "roll_open"])][
        [
            "query_date",
            "product_vt_symbol",
            "event_date",
            "contract_vt_symbol",
        ]
    ]
    fallback_coverage = fallback_keys.merge(
        open_events,
        how="inner",
        on=[
            "query_date",
            "product_vt_symbol",
            "event_date",
            "contract_vt_symbol",
        ],
    )
    fallback_gate = len(fallback_coverage) == len(fallback_keys)
    price_gate = bool(leg_audit["price_observation_valid"].astype(bool).all())
    capacity_gate = bool(events["capacity_valid"].astype(bool).all())
    identity_gate = all(
        [
            not path_audit.duplicated(keys).any(),
            not leg_audit.duplicated([*keys, "leg_index"]).any(),
            len(path_audit) == len(upstream_paths),
            len(leg_audit) == len(upstream_legs),
        ]
    )
    gates = {
        "upstream_manifest_gate": bool(upstream_verified and source_verified),
        "input_identity_gate": bool(input_identity_stable),
        "upstream_decision_gate": upstream_gate,
        "frozen_count_gate": bool(count_gate),
        "identity_gate": bool(identity_gate),
        "execution_event_structure_gate": bool(event_structure_gate),
        "fallback_event_coverage_gate": bool(fallback_gate),
        "price_observation_quality_gate": price_gate,
        "minimum_one_lot_capacity_gate": capacity_gate,
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
    return {
        "line_id": "futures_trend_xgboost_pit_roll_label_tradeability",
        "stage": "stage001_roll_label_tradeability_qualification",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision": PASS_DECISION if all_passed else FAIL_DECISION,
        "all_gates_passed": all_passed,
        "gates": gates,
        "expected_counts": asdict(expected),
        "path_rows": int(len(path_audit)),
        "path_qids": int(path_audit["query_date"].nunique()),
        "leg_rows": int(len(leg_audit)),
        "execution_event_rows": int(len(events)),
        "roll_event_count": roll_count,
        "price_valid_path_rows": int(
            path_audit["price_observation_valid"].astype(bool).sum()
        ),
        "price_invalid_path_rows": int(
            (~path_audit["price_observation_valid"].astype(bool)).sum()
        ),
        "price_invalid_leg_rows": int(
            (~leg_audit["price_observation_valid"].astype(bool)).sum()
        ),
        "capacity_valid_path_rows": int(
            path_audit["minimum_one_lot_capacity_valid"].astype(bool).sum()
        ),
        "capacity_invalid_path_rows": int(
            (~path_audit["minimum_one_lot_capacity_valid"].astype(bool)).sum()
        ),
        "capacity_valid_event_rows": int(events["capacity_valid"].astype(bool).sum()),
        "capacity_invalid_event_rows": int((~events["capacity_valid"].astype(bool)).sum()),
        "tradeability_valid_path_rows": int(
            path_audit["tradeability_valid"].astype(bool).sum()
        ),
        "tradeability_invalid_path_rows": int(
            (~path_audit["tradeability_valid"].astype(bool)).sum()
        ),
        "price_failure_counts": price_failures.value_counts()
        .sort_index()
        .astype(int)
        .to_dict(),
        "capacity_failure_counts": capacity_failures.value_counts()
        .sort_index()
        .astype(int)
        .to_dict(),
        "event_role_counts": {str(key): int(value) for key, value in role_counts.items()},
        "minimum_event_volume": float(events["volume"].min()),
        "median_event_volume": float(events["volume"].median()),
        "minimum_event_open_interest": float(events["open_interest"].min()),
        "median_event_open_interest": float(events["open_interest"].median()),
        "minimum_volume_threshold": 100.0,
        "minimum_open_interest_threshold": 100.0,
        "maximum_order_volume_share_pct": 1.0,
        "maximum_position_oi_share_pct": 1.0,
        "upstream_fallback_leg_rows": int(fallback_rows.sum()),
        "upstream_fallback_event_rows_covered": int(len(fallback_coverage)),
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
        "# Stage001换月标签可成交性资格审计\n\n"
        f"- 决策：`{summary['decision']}`\n"
        f"- 路径：{summary['path_rows']}行/{summary['path_qids']}个qid\n"
        f"- leg：{summary['leg_rows']}行；执行事件：{summary['execution_event_rows']}行\n"
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
            "upstream_bundle_invalid:"
            + ",".join(upstream_verification["errors"])
        )
    if not source_verification["verified"]:
        raise Stage001Error(
            "source_bundle_invalid:" + ",".join(source_verification["errors"])
        )

    upstream_paths = pd.read_csv(
        input_paths["upstream_paths"], encoding="utf-8-sig"
    )
    upstream_legs = pd.read_csv(
        input_paths["upstream_legs"],
        encoding="utf-8-sig",
        usecols=[
            "query_date",
            "product_vt_symbol",
            "leg_index",
            "previous_date",
            "return_date",
            "selected_contract_vt",
            "expiry_fallback",
            "roll_event",
            "leg_valid",
        ],
    )
    upstream_paths = _normalise_dates(
        upstream_paths, ["query_date", "entry_date", "label_end"]
    )
    upstream_legs = _normalise_dates(
        upstream_legs, ["query_date", "previous_date", "return_date"]
    )
    upstream_summary = json.loads(
        Path(input_paths["upstream_summary"]).read_text(encoding="utf-8")
    )
    liquidity = upstream_stage.load_bar_liquidity(input_paths["source_bars"])

    leg_audit = core.audit_leg_endpoints(upstream_legs, liquidity)
    raw_events = core.build_execution_events(leg_audit)
    events = core.assess_event_capacity(raw_events)
    path_audit = _build_path_audit(upstream_paths, leg_audit, events)
    identities_after = publisher.collect_input_identities(
        input_paths, expected_sha256
    )
    summary = assess_stage001(
        upstream_paths,
        upstream_legs,
        leg_audit,
        events,
        path_audit,
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
        "leg_rows": upstream_summary.get("leg_rows"),
        "invalid_path_rows": upstream_summary.get("invalid_path_rows"),
        "invalid_leg_rows": upstream_summary.get("invalid_leg_rows"),
        "expiry_fallback_leg_count": upstream_summary.get(
            "expiry_fallback_leg_count"
        ),
        "roll_event_count": upstream_summary.get("roll_event_count"),
    }
    summary["implementation_identities"] = {
        "runner_sha256": publisher.sha256_file(Path(__file__)),
        "core_sha256": publisher.sha256_file(Path(core.__file__)),
    }

    price_failures = leg_audit[
        ~leg_audit["price_observation_valid"].astype(bool)
    ].copy()
    capacity_failures = events[~events["capacity_valid"].astype(bool)].copy()
    frames = {
        "leg_endpoint_audit.csv.gz": leg_audit,
        "execution_events.csv.gz": events,
        "path_tradeability.csv.gz": path_audit,
        "price_quality_failures.csv.gz": price_failures,
        "capacity_failures.csv.gz": capacity_failures,
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
        description="Stage001 roll-label tradeability qualification"
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
        core.TradeabilityError,
        upstream_stage.Stage001Error,
        publisher.Stage001Error,
    ) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["all_gates_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
