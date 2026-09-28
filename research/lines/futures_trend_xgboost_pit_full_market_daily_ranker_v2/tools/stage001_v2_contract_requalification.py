from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd


LINE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
UPSTREAM_LINE_DIR = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_full_market_daily_ranker"
)
UPSTREAM_TOOLS = UPSTREAM_LINE_DIR / "tools"
if str(UPSTREAM_TOOLS) not in sys.path:
    sys.path.insert(0, str(UPSTREAM_TOOLS))

import daily_ranker_contract as upstream_contract
import stage001_daily_ranker_contract as upstream_stage001


LINE_ID = "futures_trend_xgboost_pit_full_market_daily_ranker_v2"
PASS_DECISION = (
    "stage001_daily_ranker_v2_contract_pass_allow_stage002_preregistration_only"
)
FAIL_DECISION = "stage001_daily_ranker_v2_contract_fail_close_no_labels"
UPSTREAM_CORRECTED_PASS_DECISION = upstream_stage001.PASS_DECISION

UPSTREAM_DIR = UPSTREAM_LINE_DIR / "artifacts/stage001_daily_ranker_contract"
SOURCE_DIR = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_full_market_source_rebuild/"
    "artifacts/stage002_endofday_source_rebuild"
)
DEFAULT_OUTPUT_DIR = LINE_DIR / "artifacts/stage001_v2_contract_requalification"
DEFAULT_INPUT_PATHS = {
    "upstream_manifest": UPSTREAM_DIR / "artifact_manifest.json",
    "source_bars": SOURCE_DIR / "normalised_daily_bars.csv.gz",
    "source_mapping": SOURCE_DIR / "pit_main_contract_mapping.csv.gz",
    "upstream_contract_core": UPSTREAM_TOOLS / "daily_ranker_contract.py",
    "upstream_stage001_runner": UPSTREAM_TOOLS / "stage001_daily_ranker_contract.py",
}
DEFAULT_EXPECTED_SHA256 = {
    "upstream_manifest": "0ec63c32cf8fbe33a85bed16d20a94aaeb7d2ee9a5906670819e91d3671e702a",
    "source_bars": "f2cf98dbfde2e18031697d598c3147c0ee8f15d3feb6ab935b92bc44a919ece4",
    "source_mapping": "1b9059e42161a71aaacd7d6367cbe4c7cd95eb944a1f463baf360aa038fec34d",
    "upstream_contract_core": "2e48b80ee229ab6a40c72b945b6eaf64d3b7c05c42a609801a37146ea9dfbaf6",
    "upstream_stage001_runner": "6ea6d90fe74a7a5c4e36fd72c994ade9228961a149a3524417f8c52e8d53d541",
}
EXPECTED_LIQUIDITY_DIAGNOSTICS = {
    "volume": {
        "fail_20": 273,
        "fail_60": 420,
        "only_20": 40,
        "only_60": 187,
        "both": 233,
        "union": 460,
    },
    "open_interest": {
        "fail_20": 21,
        "fail_60": 80,
        "only_20": 0,
        "only_60": 59,
        "both": 21,
        "union": 80,
    },
}


class V2ContractError(RuntimeError):
    pass


def compute_liquidity_coverage_diagnostics(
    history: pd.DataFrame,
    base_panel: pd.DataFrame,
) -> dict[str, dict[str, int]]:
    required_history = {"date", "product_vt_symbol", "volume", "open_interest"}
    required_base = {"query_date", "product_vt_symbol"}
    if not required_history.issubset(history.columns):
        raise V2ContractError("history_columns_missing")
    if not required_base.issubset(base_panel.columns):
        raise V2ContractError("base_columns_missing")
    clean = history[list(required_history)].copy()
    clean["date"] = pd.to_datetime(clean["date"], errors="raise").dt.normalize()
    clean["product_vt_symbol"] = clean["product_vt_symbol"].astype(str)
    clean = clean.sort_values(
        ["product_vt_symbol", "date"], kind="mergesort"
    ).reset_index(drop=True)
    if clean.duplicated(["date", "product_vt_symbol"]).any():
        raise V2ContractError("duplicate_history_row")
    base = base_panel[["query_date", "product_vt_symbol"]].copy()
    base["query_date"] = pd.to_datetime(
        base["query_date"], errors="raise"
    ).dt.normalize()
    base["product_vt_symbol"] = base["product_vt_symbol"].astype(str)
    if base.duplicated().any():
        raise V2ContractError("duplicate_base_row")

    diagnostics: dict[str, dict[str, int]] = {}
    for source in ("volume", "open_interest"):
        values = pd.to_numeric(clean[source], errors="coerce").astype(float)
        clean[f"{source}_positive"] = (np.isfinite(values) & values.gt(0)).astype(
            int
        )
        grouped = clean.groupby("product_vt_symbol", sort=False)[
            f"{source}_positive"
        ]
        for window, required in ((20, 18), (60, 54)):
            clean[f"{source}_pass_{window}"] = grouped.transform(
                lambda series, window=window, required=required: series.rolling(
                    window, min_periods=window
                )
                .sum()
                .ge(required)
            )
        selected = base.merge(
            clean[
                [
                    "date",
                    "product_vt_symbol",
                    f"{source}_pass_20",
                    f"{source}_pass_60",
                ]
            ],
            how="left",
            left_on=["query_date", "product_vt_symbol"],
            right_on=["date", "product_vt_symbol"],
            validate="one_to_one",
        )
        if selected[[f"{source}_pass_20", f"{source}_pass_60"]].isna().any().any():
            raise V2ContractError(f"liquidity_query_missing:{source}")
        fail_20 = ~selected[f"{source}_pass_20"].astype(bool)
        fail_60 = ~selected[f"{source}_pass_60"].astype(bool)
        diagnostics[source] = {
            "fail_20": int(fail_20.sum()),
            "fail_60": int(fail_60.sum()),
            "only_20": int((fail_20 & ~fail_60).sum()),
            "only_60": int((~fail_20 & fail_60).sum()),
            "both": int((fail_20 & fail_60).sum()),
            "union": int((fail_20 | fail_60).sum()),
        }
    return diagnostics


def assess_v2_contract(
    corrected_contract: Mapping[str, object],
    liquidity_diagnostics: Mapping[str, Mapping[str, int]],
    *,
    upstream_verified: bool,
    input_identity_stable: bool,
) -> dict[str, object]:
    corrected_contract_gate = (
        corrected_contract.get("all_gates_passed") is True
        and corrected_contract.get("decision") == UPSTREAM_CORRECTED_PASS_DECISION
    )
    liquidity_union_gate = dict(liquidity_diagnostics) == dict(
        EXPECTED_LIQUIDITY_DIAGNOSTICS
    )
    zero_side_effect_gate = all(
        int(corrected_contract.get(field, -1)) == 0
        for field in (
            "future_close_value_reads",
            "future_return_calculations",
            "label_value_reads",
            "model_fit_count",
            "model_predict_count",
            "strategy_backtest_runs",
            "ctp_connection_count",
            "order_api_called_count",
            "production_files_written",
        )
    )
    gates = {
        "upstream_manifest_gate": bool(upstream_verified),
        "input_identity_gate": bool(input_identity_stable),
        "corrected_contract_gate": bool(corrected_contract_gate),
        "liquidity_union_gate": bool(liquidity_union_gate),
        "zero_side_effect_gate": bool(zero_side_effect_gate),
    }
    all_passed = all(gates.values())
    return {
        "line_id": LINE_ID,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "evidence_scope": "label_free_v1_contract_requalification_only",
        "decision": PASS_DECISION if all_passed else FAIL_DECISION,
        "all_gates_passed": all_passed,
        "gates": gates,
        "liquidity_diagnostics": dict(liquidity_diagnostics),
        "corrected_contract_decision": corrected_contract.get("decision"),
        "corrected_contract_gates": corrected_contract.get("gates", {}),
        "future_close_value_reads": 0,
        "future_return_calculations": 0,
        "label_value_reads": 0,
        "model_fit_count": 0,
        "model_predict_count": 0,
        "strategy_backtest_runs": 0,
        "ctp_connection_count": 0,
        "order_api_called_count": 0,
        "production_files_written": 0,
        "independent_reviewer_required": False,
        "independent_reviewer_reason": "no_backtest_result_produced",
    }


def _report(summary: Mapping[str, object]) -> str:
    diagnostics = summary["liquidity_diagnostics"]
    gate_lines = "\n".join(
        f"- `{name}`：{'通过' if passed else '失败'}"
        for name, passed in summary["gates"].items()
    )
    return (
        "# Stage001 日级排序V2无标签合同复资格\n\n"
        f"- 决策：`{summary['decision']}`\n"
        f"- volume 20/60/union：{diagnostics['volume']['fail_20']}/"
        f"{diagnostics['volume']['fail_60']}/{diagnostics['volume']['union']}\n"
        f"- open-interest 20/60/union："
        f"{diagnostics['open_interest']['fail_20']}/"
        f"{diagnostics['open_interest']['fail_60']}/"
        f"{diagnostics['open_interest']['union']}\n"
        "- 标签、训练、预测、回测、CTP、订单和生产写入：全部为0\n\n"
        "## 门禁\n\n"
        f"{gate_lines}\n"
    )


def run_stage001_v2(
    *,
    line_dir: Path = LINE_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    input_paths: Mapping[str, Path] = DEFAULT_INPUT_PATHS,
    expected_sha256: Mapping[str, str] = DEFAULT_EXPECTED_SHA256,
) -> dict[str, object]:
    final_path = upstream_stage001.assert_line_local_output(line_dir, output_dir)
    if final_path.exists():
        raise V2ContractError(f"final_output_exists:{final_path}")
    identities_before = upstream_stage001.collect_input_identities(
        input_paths, expected_sha256
    )
    upstream_verification = upstream_stage001.verify_published_bundle(
        UPSTREAM_DIR, verify_inputs=True
    )
    if not upstream_verification["verified"]:
        raise V2ContractError(
            "upstream_bundle_invalid:"
            + ",".join(upstream_verification["errors"])
        )

    upstream_summary = json.loads(
        (UPSTREAM_DIR / "summary.json").read_text(encoding="utf-8")
    )
    raw_features = pd.read_csv(UPSTREAM_DIR / "raw_feature_panel.csv.gz")
    model_features = pd.read_csv(UPSTREAM_DIR / "model_feature_panel.csv.gz")
    label_plan = pd.read_csv(UPSTREAM_DIR / "label_plan.csv.gz")
    rejected_label_plan = pd.read_csv(
        UPSTREAM_DIR / "rejected_label_plan.csv.gz"
    )
    formal_scoring = pd.read_csv(UPSTREAM_DIR / "formal_scoring_plan.csv")
    fold_plan = pd.read_csv(UPSTREAM_DIR / "fold_plan.csv")
    base_panel = raw_features[
        ["query_date", "product_vt_symbol", "main_contract_vt"]
    ].copy()

    bars = pd.read_csv(input_paths["source_bars"], encoding="utf-8-sig")
    mapping = pd.read_csv(input_paths["source_mapping"], encoding="utf-8-sig")
    contract_bars = upstream_contract.build_contract_bar_table(bars)
    history, mapping_diagnostics = upstream_contract.build_mapped_product_history(
        mapping, contract_bars
    )
    liquidity_diagnostics = compute_liquidity_coverage_diagnostics(
        history, base_panel
    )
    observed = upstream_stage001._build_observed_summary(
        base_panel=base_panel,
        raw_features=raw_features,
        model_features=model_features,
        label_plan=label_plan,
        rejected_label_plan=rejected_label_plan,
        formal_scoring_plan=formal_scoring,
        fold_plan=fold_plan,
        source_manifest_valid=bool(upstream_summary["source_manifest_valid"]),
        formal_rank10_identity_valid=bool(
            upstream_summary["formal_rank10_identity_valid"]
        ),
        input_identity_stable=True,
        mapping_diagnostics=mapping_diagnostics,
    )
    corrected_expected = replace(
        upstream_stage001.ExpectedCounts(), volume_ratio_missing=460
    )
    corrected_contract = upstream_stage001.assess_gates(
        observed, expected_counts=corrected_expected
    )
    identities_after = upstream_stage001.collect_input_identities(
        input_paths, expected_sha256
    )
    input_identity_stable = identities_before == identities_after
    summary = assess_v2_contract(
        corrected_contract,
        liquidity_diagnostics,
        upstream_verified=bool(upstream_verification["verified"]),
        input_identity_stable=input_identity_stable,
    )
    summary["corrected_contract_observed"] = corrected_contract
    summary["input_identities_before"] = identities_before
    summary["input_identities_after"] = identities_after
    summary["upstream_verification"] = upstream_verification
    summary["implementation_identities"] = {
        "v2_runner": upstream_stage001.sha256_file(Path(__file__)),
        "upstream_contract_core": identities_after["upstream_contract_core"][
            "sha256"
        ],
        "upstream_stage001_runner": identities_after[
            "upstream_stage001_runner"
        ]["sha256"],
    }
    documents = {
        "summary.json": summary,
        "liquidity_diagnostics.json": liquidity_diagnostics,
        "input_identities.json": identities_after,
        "report.md": _report(summary),
    }
    upstream_stage001.publish_bundle(
        {},
        documents,
        line_dir=line_dir,
        final_dir=final_path,
        input_identities=identities_after,
    )
    verification = upstream_stage001.verify_published_bundle(
        final_path, verify_inputs=True
    )
    if not verification["verified"]:
        raise V2ContractError(
            "published_bundle_invalid:" + ",".join(verification["errors"])
        )
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage001 V2 label-free audit")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.verify_only:
        result = upstream_stage001.verify_published_bundle(
            DEFAULT_OUTPUT_DIR, verify_inputs=True
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["verified"] else 1
    try:
        summary = run_stage001_v2()
    except (V2ContractError, upstream_stage001.Stage001Error) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["all_gates_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
