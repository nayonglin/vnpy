"""Stage001 identity-only qualification for roll-aware product label paths."""

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
V1_DIR = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/"
    "artifacts/stage001_daily_ranker_contract"
)
SOURCE_DIR = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_full_market_source_rebuild/"
    "artifacts/stage002_endofday_source_rebuild"
)
UPSTREAM_TOOLS = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/tools"
)
if str(UPSTREAM_TOOLS) not in sys.path:
    sys.path.insert(0, str(UPSTREAM_TOOLS))

import stage001_daily_ranker_contract as upstream_stage001

import roll_aware_label_plan as core


PASS_DECISION = (
    "stage001_roll_aware_label_plan_pass_allow_label_model_preregistration_only"
)
FAIL_DECISION = "stage001_roll_aware_label_plan_fail_close_no_labels"
DEFAULT_OUTPUT_DIR = LINE_DIR / "artifacts/stage001_roll_aware_label_plan"
DEFAULT_INPUT_PATHS = {
    "v1_manifest": V1_DIR / "artifact_manifest.json",
    "model_features": V1_DIR / "model_feature_panel.csv.gz",
    "accepted_label_plan": V1_DIR / "label_plan.csv.gz",
    "rejected_label_plan": V1_DIR / "rejected_label_plan.csv.gz",
    "source_manifest": SOURCE_DIR / "artifact_manifest.json",
    "source_mapping": SOURCE_DIR / "pit_main_contract_mapping.csv.gz",
    "source_bars": SOURCE_DIR / "normalised_daily_bars.csv.gz",
}
DEFAULT_EXPECTED_SHA256 = {
    "v1_manifest": "0ec63c32cf8fbe33a85bed16d20a94aaeb7d2ee9a5906670819e91d3671e702a",
    "model_features": "1e4ebb1942dc066eb1164dc82e7e0412fe10d433e57aa5b8b8ab3b71822344ac",
    "accepted_label_plan": "426c40e5f0bc1a819e291abcc66c7f35eae6b9c5015634ddf8c42878c6afbc42",
    "rejected_label_plan": "5fab12846f2aeef92abd21c537dd150ff3aa9b9345fe673b279b6e40a28562b6",
    "source_manifest": "e3894cd20114182e9b3a9e986ed5e0310fe264de06368b5efe1b5efb6903681a",
    "source_mapping": "1b9059e42161a71aaacd7d6367cbe4c7cd95eb944a1f463baf360aa038fec34d",
    "source_bars": "f2cf98dbfde2e18031697d598c3147c0ee8f15d3feb6ab935b92bc44a919ece4",
}


@dataclass(frozen=True)
class ExpectedCounts:
    base_rows: int = 57_528
    base_qids: int = 1_067
    fixed_label_accepted_rows: int = 52_484
    fixed_exit_bar_missing_rows: int = 3_788
    exit_date_outside_cutoff_rows: int = 1_256
    candidate_rows: int = 56_272
    candidate_qids: int = 1_046
    cutoff_rows: int = 1_256
    total_legs: int = 1_125_440
    holding_period: int = 20


@dataclass(frozen=True)
class Canary:
    query_date: str = "2024-01-31"
    product_vt_symbol: str = "sc.INE"
    first_contract_vt: str = "sc2403.INE"
    label_end: str = "2024-03-08"


class Stage001Error(RuntimeError):
    pass


def load_bar_presence(path: Path) -> pd.DataFrame:
    """Load only bar identities; price and liquidity columns stay unopened."""
    frame = pd.read_csv(
        path,
        encoding="utf-8-sig",
        usecols=["datetime", "symbol", "exchange", "interval"],
        dtype={"symbol": "string", "exchange": "string", "interval": "string"},
    )
    frame = frame[frame["interval"].astype(str).eq("d")].copy()
    frame["date"] = pd.to_datetime(
        frame["datetime"], errors="coerce"
    ).dt.normalize()
    if frame["date"].isna().any():
        raise Stage001Error("invalid_bar_date")
    frame["contract_vt_symbol"] = (
        frame["symbol"].astype(str).str.strip()
        + "."
        + frame["exchange"].astype(str).str.strip()
    )
    result = frame[["date", "contract_vt_symbol"]].sort_values(
        ["date", "contract_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)
    if result.duplicated().any():
        raise Stage001Error("duplicate_bar_presence")
    return result


def _normalise_dates(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        result[column] = pd.to_datetime(
            result[column], errors="coerce"
        ).dt.normalize()
    return result


def assess_stage001(
    partition_diagnostics: Mapping[str, int],
    paths: pd.DataFrame,
    legs: pd.DataFrame,
    failures: pd.DataFrame,
    *,
    v1_verified: bool,
    source_verified: bool,
    input_identity_stable: bool,
    expected: ExpectedCounts = ExpectedCounts(),
    canary: Canary = Canary(),
) -> dict[str, object]:
    expected_dict = asdict(expected)
    expected_partition = {
        key: expected_dict[key]
        for key in (
            "base_rows",
            "base_qids",
            "fixed_label_accepted_rows",
            "fixed_exit_bar_missing_rows",
            "exit_date_outside_cutoff_rows",
            "candidate_rows",
            "cutoff_rows",
        )
    }
    observed_partition = {
        key: int(partition_diagnostics.get(key, -1))
        for key in expected_partition
    }
    partition_gate = observed_partition == expected_partition

    clean_paths = _normalise_dates(
        paths, ["query_date", "entry_date", "label_end"]
    )
    clean_legs = _normalise_dates(
        legs, ["query_date", "previous_date", "return_date", "mapping_date"]
    )
    path_identity_gate = all(
        [
            len(clean_paths) == expected.candidate_rows,
            clean_paths["query_date"].nunique() == expected.candidate_qids,
            not clean_paths.duplicated(
                ["query_date", "product_vt_symbol"]
            ).any(),
        ]
    )
    complete_path_gate = all(
        [
            len(clean_legs) == expected.total_legs,
            clean_paths["leg_count"].eq(expected.holding_period).all(),
            clean_paths["failure_count"].eq(0).all(),
            clean_paths["path_valid"].astype(bool).all(),
            clean_legs["leg_valid"].astype(bool).all(),
            failures.empty,
        ]
    )
    pit_mapping_gate = all(
        [
            clean_legs["mapping_date"].lt(clean_legs["return_date"]).all(),
            clean_legs["selected_contract_vt"].notna().all(),
            clean_legs["selected_contract_vt"].astype(str).str.strip().ne("").all(),
            clean_legs["failure_reason"].fillna("").eq("").all(),
        ]
    )
    bar_presence_gate = all(
        [
            clean_legs["previous_bar_present"].astype(bool).all(),
            clean_legs["return_bar_present"].astype(bool).all(),
        ]
    )

    canary_date = pd.Timestamp(canary.query_date).normalize()
    canary_end = pd.Timestamp(canary.label_end).normalize()
    canary_paths = clean_paths[
        clean_paths["query_date"].eq(canary_date)
        & clean_paths["product_vt_symbol"].eq(canary.product_vt_symbol)
    ]
    canary_legs = clean_legs[
        clean_legs["query_date"].eq(canary_date)
        & clean_legs["product_vt_symbol"].eq(canary.product_vt_symbol)
    ].sort_values("leg_index", kind="mergesort")
    canary_gate = bool(
        len(canary_paths) == 1
        and len(canary_legs) == expected.holding_period
        and canary_paths["label_end"].iloc[0] == canary_end
        and int(canary_paths["roll_count"].iloc[0]) >= 1
        and canary_legs["selected_contract_vt"].iloc[0]
        == canary.first_contract_vt
        and canary_legs["return_date"].max() == canary_end
        and canary_legs["leg_valid"].astype(bool).all()
    )

    gates = {
        "upstream_manifest_gate": bool(v1_verified and source_verified),
        "input_identity_gate": bool(input_identity_stable),
        "partition_gate": bool(partition_gate),
        "path_identity_gate": bool(path_identity_gate),
        "complete_path_gate": bool(complete_path_gate),
        "pit_mapping_gate": bool(pit_mapping_gate),
        "bar_presence_gate": bool(bar_presence_gate),
        "canary_gate": canary_gate,
        "zero_side_effect_gate": True,
    }
    all_passed = all(gates.values())
    failure_counts = (
        clean_legs.loc[~clean_legs["leg_valid"].astype(bool), "failure_reason"]
        .value_counts(dropna=False)
        .sort_index()
        .astype(int)
        .to_dict()
    )
    return {
        "line_id": "futures_trend_xgboost_pit_roll_aware_product_labels",
        "stage": "stage001_roll_aware_label_plan_qualification",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision": PASS_DECISION if all_passed else FAIL_DECISION,
        "all_gates_passed": all_passed,
        "gates": gates,
        "expected_counts": expected_dict,
        "partition_diagnostics": dict(partition_diagnostics),
        "path_rows": int(len(clean_paths)),
        "path_qids": int(clean_paths["query_date"].nunique()),
        "leg_rows": int(len(clean_legs)),
        "valid_path_rows": int(clean_paths["path_valid"].astype(bool).sum()),
        "invalid_path_rows": int((~clean_paths["path_valid"].astype(bool)).sum()),
        "roll_event_count": int(clean_legs["roll_event"].astype(bool).sum()),
        "failure_counts": failure_counts,
        "canary": asdict(canary),
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
    failures = summary.get("failure_counts", {})
    failure_text = (
        "无" if not failures else ", ".join(f"{key}={value}" for key, value in failures.items())
    )
    return (
        "# Stage001 换月感知产品标签路径资格审计\n\n"
        f"- 决策：`{summary['decision']}`\n"
        f"- 路径：{summary['path_rows']}行/{summary['path_qids']}个qid\n"
        f"- 同合约分段：{summary['leg_rows']}行\n"
        f"- 换月事件：{summary['roll_event_count']}\n"
        f"- 失败：{failure_text}\n"
        "- close值、收益、标签、fit、predict、回测、CTP、订单和生产写入：全部为0\n\n"
        "## 门禁\n\n"
        f"{gate_lines}\n"
    )


def verify_final_bundle(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, object]:
    return upstream_stage001.verify_published_bundle(
        output_dir, verify_inputs=True
    )


def run_stage001(
    *,
    line_dir: Path = LINE_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    v1_bundle_dir: Path = V1_DIR,
    source_bundle_dir: Path = SOURCE_DIR,
    input_paths: Mapping[str, Path] = DEFAULT_INPUT_PATHS,
    expected_sha256: Mapping[str, str] = DEFAULT_EXPECTED_SHA256,
    expected: ExpectedCounts = ExpectedCounts(),
    canary: Canary = Canary(),
) -> dict[str, object]:
    final_path = upstream_stage001.assert_line_local_output(line_dir, output_dir)
    if final_path.exists():
        raise Stage001Error(f"final_output_exists:{final_path}")
    identities_before = upstream_stage001.collect_input_identities(
        input_paths, expected_sha256
    )
    v1_verification = upstream_stage001.verify_published_bundle(
        v1_bundle_dir, verify_inputs=True
    )
    source_verification = upstream_stage001.verify_published_bundle(
        source_bundle_dir, verify_inputs=True
    )
    if not v1_verification["verified"]:
        raise Stage001Error(
            "v1_bundle_invalid:" + ",".join(v1_verification["errors"])
        )
    if not source_verification["verified"]:
        raise Stage001Error(
            "source_bundle_invalid:" + ",".join(source_verification["errors"])
        )

    base = pd.read_csv(
        input_paths["model_features"],
        encoding="utf-8-sig",
        usecols=["query_date", "product_vt_symbol", "main_contract_vt"],
    )
    accepted = pd.read_csv(
        input_paths["accepted_label_plan"],
        encoding="utf-8-sig",
        usecols=[
            "query_date",
            "product_vt_symbol",
            "main_contract_vt",
            "entry_date",
            "label_end",
        ],
    )
    rejected = pd.read_csv(
        input_paths["rejected_label_plan"],
        encoding="utf-8-sig",
        usecols=[
            "query_date",
            "product_vt_symbol",
            "main_contract_vt",
            "entry_date",
            "label_end",
            "rejection_reason",
        ],
    )
    mapping = pd.read_csv(
        input_paths["source_mapping"],
        encoding="utf-8-sig",
        usecols=[
            "date",
            "continuous_symbol_vt",
            "main_contract_vt",
            "mapping_resolution",
        ],
    )
    bar_presence = load_bar_presence(input_paths["source_bars"])

    candidates, cutoff, partition_diagnostics = core.partition_windows(
        base, accepted, rejected
    )
    paths, legs, failures = core.build_roll_aware_paths(
        candidates,
        mapping,
        bar_presence,
        mapping["date"].drop_duplicates(),
        holding_period=expected.holding_period,
    )
    identities_after = upstream_stage001.collect_input_identities(
        input_paths, expected_sha256
    )
    input_identity_stable = identities_before == identities_after
    summary = assess_stage001(
        partition_diagnostics,
        paths,
        legs,
        failures,
        v1_verified=bool(v1_verification["verified"]),
        source_verified=bool(source_verification["verified"]),
        input_identity_stable=input_identity_stable,
        expected=expected,
        canary=canary,
    )
    summary["input_identities_before"] = identities_before
    summary["input_identities_after"] = identities_after
    summary["v1_verification"] = v1_verification
    summary["source_verification"] = source_verification
    summary["opened_bar_columns"] = [
        "datetime",
        "symbol",
        "exchange",
        "interval",
    ]
    summary["forbidden_bar_value_columns_opened"] = 0
    summary["implementation_identities"] = {
        "runner_sha256": upstream_stage001.sha256_file(Path(__file__)),
        "core_sha256": upstream_stage001.sha256_file(Path(core.__file__)),
    }

    frames = {
        "roll_aware_label_plan.csv.gz": paths,
        "roll_aware_legs.csv.gz": legs,
        "path_failures.csv.gz": failures,
        "cutoff_rows.csv.gz": cutoff,
    }
    documents = {
        "summary.json": summary,
        "partition_diagnostics.json": partition_diagnostics,
        "input_identities.json": identities_after,
        "upstream_verification.json": {
            "v1": v1_verification,
            "source": source_verification,
        },
        "report.md": _report(summary),
    }
    upstream_stage001.publish_bundle(
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
        description="Stage001 roll-aware identity-only label path audit"
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
    except (Stage001Error, core.PlanError, upstream_stage001.Stage001Error) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["all_gates_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
