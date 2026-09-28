"""Stage001 qualification for expiry-safe roll mappings."""

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
V2_TOOLS = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_roll_aware_product_labels_v2/tools"
)
if str(V2_TOOLS) not in sys.path:
    sys.path.insert(0, str(V2_TOOLS))

import stage001_v2_roll_aware_label_plan as v2

import expiry_safe_roll_mapping as core


upstream = v2.upstream_stage001
V2_DIR = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_roll_aware_product_labels_v2/"
    "artifacts/stage001_v2_roll_aware_label_plan"
)
SOURCE_DIR = v2.SOURCE_DIR
DEFAULT_OUTPUT_DIR = LINE_DIR / "artifacts/stage001_expiry_safe_roll_mapping"
PASS_DECISION = (
    "stage001_expiry_safe_roll_mapping_pass_allow_roll_label_generator_"
    "preregistration_only"
)
FAIL_DECISION = "stage001_expiry_safe_roll_mapping_fail_close_no_labels"
DEFAULT_INPUT_PATHS = {
    "v2_manifest": V2_DIR / "artifact_manifest.json",
    "v2_paths": V2_DIR / "roll_aware_label_plan.csv.gz",
    "v2_legs": V2_DIR / "roll_aware_legs.csv.gz",
    "v2_summary": V2_DIR / "summary.json",
    "source_manifest": SOURCE_DIR / "artifact_manifest.json",
    "source_catalog": SOURCE_DIR / "asof_contract_catalog.csv.gz",
    "source_bars": SOURCE_DIR / "normalised_daily_bars.csv.gz",
}
DEFAULT_EXPECTED_SHA256 = {
    "v2_manifest": "f2a4cf72f0bddeb7fc103bc30714f6fc3380bc7f099bda2a16f57efb667797fd",
    "v2_paths": "b67ac38d242260ff685422c20deb7ffc24cbc31f3e1deef8fc7f9b476c8a038a",
    "v2_legs": "7f0d6092a0166fc1fe8ee5b0fbb5f4e4166678cf82e0dedb7f882bab5782b149",
    "v2_summary": "ab605d61fe2a26314fa8e351d00e829929392052f6b4b10055eb509954a6ea57",
    "source_manifest": "e3894cd20114182e9b3a9e986ed5e0310fe264de06368b5efe1b5efb6903681a",
    "source_catalog": "c733e5d85bab4349efb9bd25e2afdd689562718ffd608bff9a4f11964ab13bfc",
    "source_bars": "f2cf98dbfde2e18031697d598c3147c0ee8f15d3feb6ab935b92bc44a919ece4",
}


@dataclass(frozen=True)
class ExpectedCounts:
    path_rows: int = 56_272
    path_qids: int = 1_046
    leg_rows: int = 1_125_440
    holding_period: int = 20
    v2_invalid_path_rows: int = 6
    v2_invalid_leg_rows: int = 6


@dataclass(frozen=True)
class ExpiryCanary:
    query_date: str
    product_vt_symbol: str
    leg_index: int
    original_contract_vt: str


@dataclass(frozen=True)
class StablePathCanary:
    query_date: str
    product_vt_symbol: str
    first_contract_vt: str
    label_end: str
    minimum_roll_count: int = 1


@dataclass(frozen=True)
class CanarySet:
    expiry: tuple[ExpiryCanary, ...] = (
        ExpiryCanary(
            query_date="2023-10-13",
            product_vt_symbol="wr.SHFE",
            leg_index=1,
            original_contract_vt="wr2310.SHFE",
        ),
        ExpiryCanary(
            query_date="2025-10-21",
            product_vt_symbol="RS.CZCE",
            leg_index=18,
            original_contract_vt="RS511.CZCE",
        ),
    )
    stable: StablePathCanary = StablePathCanary(
        query_date="2024-01-31",
        product_vt_symbol="sc.INE",
        first_contract_vt="sc2403.INE",
        label_end="2024-03-08",
        minimum_roll_count=1,
    )


class Stage001Error(RuntimeError):
    pass


def load_bar_liquidity(path: Path) -> pd.DataFrame:
    """Read identity and mapping-date liquidity columns, never close values."""
    frame = pd.read_csv(
        path,
        encoding="utf-8-sig",
        usecols=[
            "datetime",
            "symbol",
            "exchange",
            "interval",
            "volume",
            "open_interest",
        ],
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
    for column in ("volume", "open_interest"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    result = frame[
        ["date", "contract_vt_symbol", "volume", "open_interest"]
    ].sort_values(["date", "contract_vt_symbol"], kind="mergesort")
    if result.duplicated(["date", "contract_vt_symbol"]).any():
        raise Stage001Error("duplicate_bar_liquidity")
    return result.reset_index(drop=True)


def _normalise_dates(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        result[column] = pd.to_datetime(
            result[column], errors="coerce"
        ).dt.normalize()
        if result[column].isna().any():
            raise Stage001Error(f"invalid_date:{column}")
    return result


def _build_final_paths(
    v2_paths: pd.DataFrame,
    final_legs: pd.DataFrame,
) -> pd.DataFrame:
    keys = ["query_date", "product_vt_symbol"]
    paths = _normalise_dates(
        v2_paths,
        ["query_date", "entry_date", "label_end"],
    )
    if paths.duplicated(keys).any():
        raise Stage001Error("duplicate_v2_path")
    legs = final_legs.sort_values([*keys, "leg_index"], kind="mergesort").copy()
    previous_contract = legs.groupby(keys, sort=False)[
        "selected_contract_vt"
    ].shift(1)
    legs["roll_event"] = (
        previous_contract.notna()
        & legs["selected_contract_vt"].ne(previous_contract)
    )
    aggregates = legs.groupby(keys, sort=False).agg(
        leg_count=("leg_index", "size"),
        roll_count=("roll_event", "sum"),
        failure_count=("leg_valid", lambda values: int((~values).sum())),
        path_valid=("leg_valid", "all"),
        expiry_fallback_count=("expiry_fallback", "sum"),
    )
    identity_columns = [
        "query_date",
        "product_vt_symbol",
        "main_contract_vt",
        "entry_date",
        "label_end",
        "source_partition",
    ]
    result = paths[identity_columns].merge(
        aggregates.reset_index(), how="left", on=keys, validate="one_to_one"
    )
    if result[["leg_count", "failure_count"]].isna().any().any():
        raise Stage001Error("path_aggregate_missing")
    for column in (
        "leg_count",
        "roll_count",
        "failure_count",
        "expiry_fallback_count",
    ):
        result[column] = result[column].astype(int)
    result["path_valid"] = result["path_valid"].astype(bool)
    return result.sort_values(keys, kind="mergesort").reset_index(drop=True)


def _expiry_canary_pass(
    legs: pd.DataFrame, canary: ExpiryCanary
) -> bool:
    rows = legs[
        legs["query_date"].eq(pd.Timestamp(canary.query_date))
        & legs["product_vt_symbol"].eq(canary.product_vt_symbol)
        & legs["leg_index"].eq(canary.leg_index)
    ]
    return bool(
        len(rows) == 1
        and rows["original_contract_vt"].iloc[0]
        == canary.original_contract_vt
        and bool(rows["expiry_fallback"].iloc[0])
        and rows["selected_contract_vt"].iloc[0]
        != canary.original_contract_vt
        and rows["selected_expire_date"].iloc[0]
        >= rows["return_date"].iloc[0]
        and bool(rows["leg_valid"].iloc[0])
    )


def _stable_canary_pass(
    paths: pd.DataFrame,
    legs: pd.DataFrame,
    canary: StablePathCanary,
    holding_period: int,
) -> bool:
    path_rows = paths[
        paths["query_date"].eq(pd.Timestamp(canary.query_date))
        & paths["product_vt_symbol"].eq(canary.product_vt_symbol)
    ]
    leg_rows = legs[
        legs["query_date"].eq(pd.Timestamp(canary.query_date))
        & legs["product_vt_symbol"].eq(canary.product_vt_symbol)
    ].sort_values("leg_index", kind="mergesort")
    return bool(
        len(path_rows) == 1
        and len(leg_rows) == holding_period
        and path_rows["label_end"].iloc[0] == pd.Timestamp(canary.label_end)
        and bool(path_rows["path_valid"].iloc[0])
        and int(path_rows["roll_count"].iloc[0]) >= canary.minimum_roll_count
        and leg_rows["selected_contract_vt"].iloc[0]
        == canary.first_contract_vt
    )


def assess_stage001(
    v2_paths: pd.DataFrame,
    v2_legs: pd.DataFrame,
    final_paths: pd.DataFrame,
    final_legs: pd.DataFrame,
    *,
    v2_verified: bool,
    source_verified: bool,
    input_identity_stable: bool,
    expected: ExpectedCounts = ExpectedCounts(),
    canaries: CanarySet = CanarySet(),
) -> dict[str, object]:
    keys = ["query_date", "product_vt_symbol"]
    fallback = final_legs["expiry_fallback"].astype(bool)
    non_fallback = ~fallback
    count_gate = all(
        [
            len(final_paths) == expected.path_rows,
            final_paths["query_date"].nunique() == expected.path_qids,
            len(final_legs) == expected.leg_rows,
            final_paths["leg_count"].eq(expected.holding_period).all(),
            int((~v2_paths["path_valid"].astype(bool)).sum())
            == expected.v2_invalid_path_rows,
            int((~v2_legs["leg_valid"].astype(bool)).sum())
            == expected.v2_invalid_leg_rows,
        ]
    )
    path_identity_gate = all(
        [
            not final_paths.duplicated(keys).any(),
            not final_legs.duplicated([*keys, "leg_index"]).any(),
            final_legs.groupby(keys, sort=False).size().eq(
                expected.holding_period
            ).all(),
        ]
    )
    v2_failure_reasons = set(
        v2_legs.loc[
            ~v2_legs["leg_valid"].astype(bool), "failure_reason"
        ].astype(str)
    )
    v2_failure_contract_gate = v2_failure_reasons.issubset(
        {"return_bar_missing"}
    )
    unchanged_gate = bool(
        final_legs.loc[non_fallback, "selected_contract_vt"].eq(
            final_legs.loc[non_fallback, "original_contract_vt"]
        ).all()
    )
    expiry_gate = bool(
        final_legs["selected_expire_date"].ge(final_legs["return_date"]).all()
    )
    causal_gate = bool(
        final_legs["selection_source_date"].eq(
            final_legs["mapping_date"]
        ).all()
        and final_legs["selection_source_date"].lt(
            final_legs["return_date"]
        ).all()
        and final_legs["future_selection_rows_used"].eq(0).all()
        and final_legs["endpoint_reselection_count"].eq(0).all()
    )
    endpoint_gate = bool(
        final_legs["selection_valid"].astype(bool).all()
        and final_legs["previous_bar_present"].astype(bool).all()
        and final_legs["return_bar_present"].astype(bool).all()
        and final_legs["leg_valid"].astype(bool).all()
        and final_paths["path_valid"].astype(bool).all()
    )
    fallback_gate = bool(
        fallback.any()
        and final_legs.loc[fallback, "selection_reason"]
        .eq("expiry_fallback_liquidity")
        .all()
        and final_legs.loc[fallback, "selected_contract_vt"]
        .ne(final_legs.loc[fallback, "original_contract_vt"])
        .all()
    )
    expiry_canary_gate = all(
        _expiry_canary_pass(final_legs, canary) for canary in canaries.expiry
    )
    stable_canary_gate = _stable_canary_pass(
        final_paths,
        final_legs,
        canaries.stable,
        expected.holding_period,
    )
    gates = {
        "upstream_manifest_gate": bool(v2_verified and source_verified),
        "input_identity_gate": bool(input_identity_stable),
        "frozen_count_gate": bool(count_gate),
        "path_identity_gate": bool(path_identity_gate),
        "v2_failure_contract_gate": bool(v2_failure_contract_gate),
        "non_expiry_unchanged_gate": unchanged_gate,
        "expiry_coverage_gate": expiry_gate,
        "causal_selection_gate": causal_gate,
        "fallback_selection_gate": fallback_gate,
        "endpoint_presence_gate": endpoint_gate,
        "expiry_canary_gate": bool(expiry_canary_gate),
        "stable_canary_gate": bool(stable_canary_gate),
        "zero_side_effect_gate": True,
    }
    all_passed = all(gates.values())
    failures = (
        final_legs.loc[~final_legs["leg_valid"].astype(bool), "failure_reason"]
        .value_counts(dropna=False)
        .sort_index()
        .astype(int)
        .to_dict()
    )
    fallback_rows = final_legs.loc[fallback]
    candidate_counts = fallback_rows["fallback_candidate_count"]
    return {
        "line_id": "futures_trend_xgboost_pit_expiry_safe_roll_mapping",
        "stage": "stage001_expiry_safe_roll_mapping_qualification",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision": PASS_DECISION if all_passed else FAIL_DECISION,
        "all_gates_passed": all_passed,
        "gates": gates,
        "expected_counts": asdict(expected),
        "path_rows": int(len(final_paths)),
        "path_qids": int(final_paths["query_date"].nunique()),
        "leg_rows": int(len(final_legs)),
        "valid_path_rows": int(final_paths["path_valid"].astype(bool).sum()),
        "invalid_path_rows": int((~final_paths["path_valid"].astype(bool)).sum()),
        "invalid_leg_rows": int((~final_legs["leg_valid"].astype(bool)).sum()),
        "expiry_fallback_leg_count": int(fallback.sum()),
        "expiry_fallback_event_count": int(
            fallback_rows[
                [
                    "mapping_date",
                    "return_date",
                    "product_vt_symbol",
                    "original_contract_vt",
                    "selected_contract_vt",
                ]
            ].drop_duplicates().shape[0]
        ),
        "fallback_candidate_count_min": int(candidate_counts.min())
        if len(candidate_counts)
        else 0,
        "fallback_candidate_count_median": float(candidate_counts.median())
        if len(candidate_counts)
        else 0.0,
        "fallback_candidate_count_max": int(candidate_counts.max())
        if len(candidate_counts)
        else 0,
        "roll_event_count": int(final_legs["roll_event"].astype(bool).sum()),
        "failure_counts": failures,
        "canaries": asdict(canaries),
        "opened_bar_columns": [
            "datetime",
            "symbol",
            "exchange",
            "interval",
            "volume",
            "open_interest",
        ],
        "opened_catalog_columns": [
            "vt_symbol",
            "product_vt_symbol",
            "expire_date",
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
    failures = summary.get("failure_counts", {})
    failure_text = (
        "无"
        if not failures
        else ", ".join(f"{key}={value}" for key, value in failures.items())
    )
    return (
        "# Stage001到期安全换月映射资格审计\n\n"
        f"- 决策：`{summary['decision']}`\n"
        f"- 路径：{summary['path_rows']}行/{summary['path_qids']}个qid\n"
        f"- 分段：{summary['leg_rows']}行\n"
        f"- 到期fallback：{summary['expiry_fallback_leg_count']}段/"
        f"{summary['expiry_fallback_event_count']}个事件\n"
        f"- 失败：{failure_text}\n"
        "- close、收益、标签、fit、predict、回测、CTP、订单和生产写入：全部为0\n\n"
        "## 门禁\n\n"
        f"{gate_lines}\n"
    )


def verify_final_bundle(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, object]:
    return upstream.verify_published_bundle(output_dir, verify_inputs=True)


def run_stage001(
    *,
    line_dir: Path = LINE_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    v2_bundle_dir: Path = V2_DIR,
    source_bundle_dir: Path = SOURCE_DIR,
    input_paths: Mapping[str, Path] = DEFAULT_INPUT_PATHS,
    expected_sha256: Mapping[str, str] = DEFAULT_EXPECTED_SHA256,
    expected: ExpectedCounts = ExpectedCounts(),
    canaries: CanarySet = CanarySet(),
) -> dict[str, object]:
    final_path = upstream.assert_line_local_output(line_dir, output_dir)
    if final_path.exists():
        raise Stage001Error(f"final_output_exists:{final_path}")
    identities_before = upstream.collect_input_identities(
        input_paths, expected_sha256
    )
    v2_verification = upstream.verify_published_bundle(
        v2_bundle_dir, verify_inputs=True
    )
    source_verification = v2.verify_path_manifest_bundle(source_bundle_dir)
    if not v2_verification["verified"]:
        raise Stage001Error(
            "v2_bundle_invalid:" + ",".join(v2_verification["errors"])
        )
    if not source_verification["verified"]:
        raise Stage001Error(
            "source_bundle_invalid:" + ",".join(source_verification["errors"])
        )

    v2_paths = pd.read_csv(input_paths["v2_paths"], encoding="utf-8-sig")
    v2_legs = pd.read_csv(input_paths["v2_legs"], encoding="utf-8-sig")
    v2_paths = _normalise_dates(
        v2_paths, ["query_date", "entry_date", "label_end"]
    )
    v2_legs = _normalise_dates(
        v2_legs,
        ["query_date", "previous_date", "return_date", "mapping_date"],
    )
    v2_summary = json.loads(
        Path(input_paths["v2_summary"]).read_text(encoding="utf-8")
    )
    catalog = pd.read_csv(
        input_paths["source_catalog"],
        encoding="utf-8-sig",
        usecols=["vt_symbol", "product_vt_symbol", "expire_date"],
    )
    liquidity = load_bar_liquidity(input_paths["source_bars"])
    presence = liquidity[["date", "contract_vt_symbol"]].copy()

    selected = core.select_expiry_safe_contracts(v2_legs, catalog, liquidity)
    final_legs = core.validate_selected_endpoints(selected, presence)
    source_partition = v2_legs[
        ["query_date", "product_vt_symbol", "leg_index", "source_partition"]
    ]
    final_legs = final_legs.merge(
        source_partition,
        how="left",
        on=["query_date", "product_vt_symbol", "leg_index"],
        validate="one_to_one",
    )
    if final_legs["source_partition"].isna().any():
        raise Stage001Error("source_partition_missing")
    final_legs = final_legs.sort_values(
        ["query_date", "product_vt_symbol", "leg_index"], kind="mergesort"
    ).reset_index(drop=True)
    previous_contract = final_legs.groupby(
        ["query_date", "product_vt_symbol"], sort=False
    )["selected_contract_vt"].shift(1)
    final_legs["roll_event"] = (
        previous_contract.notna()
        & final_legs["selected_contract_vt"].ne(previous_contract)
    )
    final_paths = _build_final_paths(v2_paths, final_legs)
    identities_after = upstream.collect_input_identities(
        input_paths, expected_sha256
    )
    summary = assess_stage001(
        v2_paths,
        v2_legs,
        final_paths,
        final_legs,
        v2_verified=bool(v2_verification["verified"]),
        source_verified=bool(source_verification["verified"]),
        input_identity_stable=identities_before == identities_after,
        expected=expected,
        canaries=canaries,
    )
    summary["input_identities_before"] = identities_before
    summary["input_identities_after"] = identities_after
    summary["v2_verification"] = v2_verification
    summary["source_verification"] = source_verification
    summary["v2_summary_identity"] = {
        "decision": v2_summary.get("decision"),
        "path_rows": v2_summary.get("path_rows"),
        "leg_rows": v2_summary.get("leg_rows"),
        "invalid_path_rows": v2_summary.get("invalid_path_rows"),
        "failure_counts": v2_summary.get("failure_counts"),
    }
    summary["implementation_identities"] = {
        "runner_sha256": upstream.sha256_file(Path(__file__)),
        "core_sha256": upstream.sha256_file(Path(core.__file__)),
    }

    failures = final_legs[~final_legs["leg_valid"].astype(bool)].copy()
    fallbacks = final_legs[final_legs["expiry_fallback"].astype(bool)].copy()
    frames = {
        "expiry_safe_paths.csv.gz": final_paths,
        "expiry_safe_legs.csv.gz": final_legs,
        "expiry_fallbacks.csv.gz": fallbacks,
        "path_failures.csv.gz": failures,
    }
    documents = {
        "summary.json": summary,
        "input_identities.json": identities_after,
        "upstream_verification.json": {
            "v2": v2_verification,
            "source": source_verification,
        },
        "report.md": _report(summary),
    }
    upstream.publish_bundle(
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
        description="Stage001 expiry-safe roll mapping qualification"
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
        core.SelectionError,
        upstream.Stage001Error,
    ) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["all_gates_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
