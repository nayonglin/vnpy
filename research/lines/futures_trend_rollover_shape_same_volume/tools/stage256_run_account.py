"""Stage256: one frozen 2025-26 account replay using the accepted Stage251 C engine.

Only the monthly eligibility CSV and its research policy identifier vary by
account. The Stage251 source, frozen official material, prices and costs remain
unchanged. This deliberately produces diagnostic results with existing minutes.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any


LINE = "research/lines/futures_trend_rollover_shape_same_volume"
START, END, CAPITAL = "2025-01-01", "2026-10-14", 150000
OFFICIAL_POLICY = "ai_top10_plus_fu_official_live_v1"
RESEARCH_POLICIES = {"ai_initial_fixed": "stage256_ai_initial_fixed_v1",
                     "random_monthly": "stage256_random_monthly_v1"}
FIXED_PRODUCT = "fu.SHFE"
NON_FU_UNIVERSE = ["AP.CZCE", "CF.CZCE", "FG.CZCE", "MA.CZCE", "OI.CZCE",
                   "SA.CZCE", "SH.CZCE", "SM.CZCE", "jm.DCE", "lh.DCE",
                   "lc.GFEX", "si.GFEX", "au.SHFE", "cu.SHFE", "hc.SHFE",
                   "rb.SHFE", "ru.SHFE", "sp.SHFE"]
EVAL_DATES = ["2024-12-31", "2025-01-27", "2025-02-28", "2025-03-31",
              "2025-04-30", "2025-05-30", "2025-06-30", "2025-07-31",
              "2025-08-29", "2025-09-30", "2025-10-31", "2025-11-28",
              "2025-12-31", "2026-01-30", "2026-02-27", "2026-03-31",
              "2026-04-30", "2026-05-29", "2026-06-30", "2026-07-31",
              "2026-08-31", "2026-09-30"]
REQUIRED_COLUMNS = {"strategy", "score_type", "eval_date", "product_vt_symbol",
                    "score", "score_rank", "top_n"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def account_kind(account_id: str) -> str:
    if account_id == "AI_MONTHLY":
        return "ai_monthly"
    if account_id == "AI_INITIAL_FIXED":
        return "ai_initial_fixed"
    match = re.fullmatch(r"RANDOM_(\d{3})", account_id)
    if match and 1 <= int(match.group(1)) <= 199:
        return "random_monthly"
    raise ValueError(f"unregistered_account_id:{account_id}")


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not REQUIRED_COLUMNS.issubset(reader.fieldnames or []):
            raise ValueError("pool_columns_missing")
        rows = list(reader)
    if not rows or any(None in row for row in rows):
        raise ValueError("pool_rows_malformed_or_empty")
    return rows


def validate_pool_rows(rows: list[dict[str, str]], policy_id: str,
                       expected_eval_dates: list[str], universe: list[str]) -> dict[str, Any]:
    """Validate every frozen row and the exact 22-window width, without engine work."""
    if len(universe) != 18 or len(set(universe)) != 18 or FIXED_PRODUCT in universe:
        raise ValueError("non_fu_universe_invalid")
    if not expected_eval_dates or sorted(set(expected_eval_dates)) != expected_eval_dates:
        raise ValueError("expected_eval_dates_invalid")
    snapshots: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        if row.get("strategy") != policy_id:
            raise ValueError("pool_strategy_mismatch")
        try:
            evaluated = date.fromisoformat(row["eval_date"]).isoformat()
            score = float(row["score"])
            rank = int(row["score_rank"])
            top_n = int(row["top_n"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("pool_numeric_or_date_invalid") from exc
        if evaluated != row["eval_date"] or not math.isfinite(score):
            raise ValueError("pool_date_or_score_invalid")
        if not row.get("score_type") or not row.get("product_vt_symbol"):
            raise ValueError("pool_row_empty_field")
        if rank < 1 or top_n < 1 or str(rank) != str(row["score_rank"]).strip() or str(top_n) != str(row["top_n"]).strip():
            raise ValueError("pool_rank_or_top_n_invalid")
        snapshots.setdefault(evaluated, []).append(row)
    selected = {key: snapshots.get(key, []) for key in expected_eval_dates}
    for evaluated, group in selected.items():
        products = [row["product_vt_symbol"] for row in group]
        ranks = [int(row["score_rank"]) for row in group]
        if len(group) != 11 or len(set(products)) != 11:
            raise ValueError(f"snapshot_width_or_duplicate:{evaluated}")
        if len(set(products) - {FIXED_PRODUCT}) != 10 or not set(products).issubset(set(universe) | {FIXED_PRODUCT}):
            raise ValueError(f"snapshot_universe:{evaluated}")
        if sorted(ranks) != list(range(1, 12)) or {int(row["top_n"]) for row in group} != {11}:
            raise ValueError(f"snapshot_rank_or_top_n:{evaluated}")
        if next(int(row["score_rank"]) for row in group if row["product_vt_symbol"] == FIXED_PRODUCT) != 11:
            raise ValueError(f"fixed_fu_rank:{evaluated}")
    if len(selected) != len(expected_eval_dates):
        raise ValueError("selected_eval_dates_missing")
    return {"selected_eval_dates": list(selected), "selected_snapshot_count": len(selected),
            "all_eval_dates": sorted(snapshots), "all_snapshot_count": len(snapshots),
            "all_row_count": len(rows)}


def validate_registry_account(registry: dict[str, Any], account_id: str,
                              pool_file: Path) -> dict[str, Any]:
    kind = account_kind(account_id)
    entry = registry.get("accounts", {}).get(account_id)
    if not isinstance(entry, dict):
        raise ValueError("account_absent_from_registry")
    if not pool_file.is_absolute() or not Path(entry.get("pool_file", "")).is_absolute():
        raise ValueError("pool_file_not_absolute")
    if pool_file.resolve() != Path(entry["pool_file"]).resolve():
        raise ValueError("pool_file_registry_mismatch")
    if not pool_file.is_file() or sha256(pool_file) != entry.get("pool_sha256"):
        raise ValueError("pool_sha256_mismatch")
    policy = OFFICIAL_POLICY if kind == "ai_monthly" else RESEARCH_POLICIES[kind]
    if entry.get("policy_id") != policy or entry.get("kind") != kind:
        raise ValueError("policy_or_kind_mismatch")
    if kind == "random_monthly" and entry.get("path_id") != int(account_id[-3:]):
        raise ValueError("path_id_mismatch")
    if registry.get("start") != START or registry.get("end") != END:
        raise ValueError("registry_window_mismatch")
    return entry


def validate_history(rows: list[dict[str, str]], source_rows: list[dict[str, str]],
                     kind: str, policy_id: str) -> None:
    """All pre-window rows must be exact source snapshots except research tag."""
    if len(rows) != len(source_rows):
        raise ValueError("historical_row_count_mismatch")
    cutoff = EVAL_DATES[0]
    for row, original in zip(rows, source_rows):
        if row.get("eval_date") != original.get("eval_date"):
            raise ValueError("historical_date_order_mismatch")
        if kind == "ai_monthly" or row["eval_date"] < cutoff:
            comparison = dict(row)
            comparison["strategy"] = original["strategy"]
            if comparison != original or row["strategy"] != policy_id:
                raise ValueError("historical_pool_drift")


@contextmanager
def adapted_stage251(stage251: Any, pool_file: Path, policy_id: str,
                     reference_parameters_path: Path, expected_dates: list[str],
                     pool_audit: dict[str, Any], repo_root: Path,
                     baseline_root: Path):
    """Narrow in-process adaptation; all originals restored even on failure."""
    reference_parameters_path = reference_parameters_path.resolve()
    try:
        comparison_pool_path = baseline_root.resolve() / pool_file.resolve().relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError("pool_file_outside_repo_root") from exc
    original_declared = stage251.declared_ablation
    original_audit = stage251.audit_historical_ai_pool
    original_read_text = Path.read_text

    @contextmanager
    def declared(s901: Any, arm: str):
        if arm != "C":
            raise ValueError("stage256_requires_stage251_C")
        original_builder = s901.build_official_live_strategy_overrides

        def build() -> dict[str, Any]:
            settings = dict(original_builder())
            if settings.get("enable_stage847_half_r_stop_retry") is not True or settings.get("enable_ai_product_pool_filter") is not True:
                raise ValueError("official_base_flags_changed")
            if settings.get("ai_product_pool_strategy") != OFFICIAL_POLICY:
                raise ValueError("official_base_policy_changed")
            settings["enable_stage847_half_r_stop_retry"] = False
            settings["ai_product_pool_eligibility_path"] = str(pool_file)
            settings["ai_product_pool_strategy"] = policy_id
            return settings

        s901.build_official_live_strategy_overrides = build
        try:
            yield
        finally:
            s901.build_official_live_strategy_overrides = original_builder

    def audit(_official_path: Path, required_eval_dates: list[str]) -> dict[str, Any]:
        if required_eval_dates != expected_dates:
            raise ValueError("stage901_required_eval_dates_drift")
        official_audit = original_audit(_official_path, required_eval_dates)
        if official_audit.get("status") != "valid":
            raise ValueError("official_source_pool_audit_failed")
        return {"status": "valid", "strategy": policy_id,
                "eligibility_sha256": sha256(pool_file),
                "selected_eval_dates": expected_dates,
                "validated_snapshot_count": pool_audit["all_snapshot_count"],
                "validated_eval_dates": pool_audit["all_eval_dates"],
                "required_calendar_rule": "Stage901 month-start prior completed trade date",
                "official_source_sha256": official_audit["eligibility_sha256"],
                "scope": "Stage256 frozen research eligibility"}

    def read_text(path: Path, *args: Any, **kwargs: Any) -> str:
        content = original_read_text(path, *args, **kwargs)
        if path.resolve() != reference_parameters_path:
            return content
        parameters = json.loads(content)
        overrides = parameters["spec"]["overrides"]
        if overrides.get("enable_stage847_half_r_stop_retry") is not True or overrides.get("ai_product_pool_strategy") != OFFICIAL_POLICY:
            raise ValueError("accepted_A_reference_changed")
        # Stage251 normalizes actual paths against repo_root and reference
        # paths against baseline_root before comparing every cost/risk field.
        # This path exists only in the comparison JSON; runtime still receives
        # the true frozen pool_file through the builder above.
        overrides["ai_product_pool_eligibility_path"] = str(comparison_pool_path)
        overrides["ai_product_pool_strategy"] = policy_id
        return json.dumps(parameters, ensure_ascii=False)

    stage251.declared_ablation = declared
    stage251.audit_historical_ai_pool = audit
    Path.read_text = read_text
    try:
        yield
    finally:
        Path.read_text = original_read_text
        stage251.audit_historical_ai_pool = original_audit
        stage251.declared_ablation = original_declared


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--pool-file", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    root, pool_file, registry_file, output = (args.repo_root.resolve(), args.pool_file,
                                              args.registry.resolve(), args.output.resolve())
    if not args.output.is_absolute() or not args.registry.is_absolute():
        raise ValueError("registry_and_output_must_be_absolute")
    if output.exists() and any(output.iterdir()):
        raise ValueError("output_not_empty")
    registry = json.loads(registry_file.read_text())
    entry = validate_registry_account(registry, args.account_id, pool_file)
    kind = account_kind(args.account_id)
    if registry.get("capital") != CAPITAL or registry.get("master_seed") != 20261016 or registry.get("random_count") != 199:
        raise ValueError("registry_experiment_constants_changed")
    if registry.get("expected_eval_dates") != EVAL_DATES or sorted(registry.get("non_fu_universe", [])) != sorted(NON_FU_UNIVERSE):
        raise ValueError("registry_universe_or_dates_changed")
    minute_file = Path(registry["minute_csv"])
    if not minute_file.is_absolute() or not minute_file.is_file() or sha256(minute_file) != registry["minute_cache_sha256"]:
        raise ValueError("minute_cache_sha256_mismatch")
    source_pool = Path(registry["source_pool"])
    if not source_pool.is_absolute() or not source_pool.is_file():
        raise ValueError("source_pool_missing")
    if sha256(source_pool) != registry.get("source_pool_sha256"):
        raise ValueError("source_pool_sha256_mismatch")
    rows, source_rows = _read_rows(pool_file), _read_rows(source_pool)
    policy_id = entry["policy_id"]
    audit = validate_pool_rows(rows, policy_id, EVAL_DATES, NON_FU_UNIVERSE)
    validate_history(rows, source_rows, kind, policy_id)
    if kind == "ai_monthly" and pool_file.read_bytes() != source_pool.read_bytes():
        raise ValueError("AI_MONTHLY_not_official_byte_copy")
    if audit["all_snapshot_count"] != 58:
        raise ValueError("historical_snapshot_count_not_58")
    reference_settings = Path(registry["reference_settings_path"])
    reference_parameters = Path(registry["parameters_reference_path"])
    if not reference_settings.is_absolute() or not reference_settings.is_file() or not reference_parameters.is_absolute() or not reference_parameters.is_file():
        raise ValueError("reference_files_missing")
    expected_reference = root / LINE / "outputs/stage251_half_r_ab/C_final/effective_parameters.json"
    accepted_a_reference = root / LINE / "outputs/stage251_half_r_ab/accepted_A_parameters.json"
    if reference_parameters.resolve() != expected_reference.resolve() or not accepted_a_reference.is_file():
        raise ValueError("parameters_reference_path_mismatch")
    pre = {"registry": sha256(registry_file), "pool": sha256(pool_file),
           "minute": sha256(minute_file), "source_pool": sha256(source_pool),
           "reference_settings": sha256(reference_settings), "parameters_reference": sha256(reference_parameters),
           "accepted_A_parameters": sha256(accepted_a_reference),
           "adapter": sha256(Path(__file__))}
    if args.check_only:
        print(json.dumps({"status": "stage256_preflight_passed_no_engine", "account_id": args.account_id,
                          "policy_id": policy_id, "pool_audit": audit, "input_sha256": pre}, ensure_ascii=False))
        return
    output.mkdir(parents=True, exist_ok=True)
    import stage251_half_r_ablation as stage251
    original_argv = sys.argv
    started = datetime.now().astimezone().isoformat()
    try:
        with adapted_stage251(stage251, pool_file, policy_id, accepted_a_reference.resolve(),
                              EVAL_DATES, audit, root, args.baseline_root.resolve()):
            sys.argv = [str(Path(stage251.__file__)), "--repo-root", str(root),
                        "--baseline-root", str(args.baseline_root.resolve()), "--arm", "C",
                        "--start", START, "--end", END, "--output", str(output),
                        "--diagnostic-incomplete-minutes"]
            stage251.main()
    finally:
        sys.argv = original_argv
    post = {"registry": sha256(registry_file), "pool": sha256(pool_file),
            "minute": sha256(minute_file), "source_pool": sha256(source_pool),
            "reference_settings": sha256(reference_settings), "parameters_reference": sha256(reference_parameters),
            "accepted_A_parameters": sha256(accepted_a_reference),
            "adapter": sha256(Path(__file__))}
    if post != pre:
        raise ValueError("stage256_input_changed_during_replay")
    inherited_provenance = json.loads((output / "run_provenance.json").read_text())
    if inherited_provenance.get("minute_input_sha256") != pre["minute"]:
        raise ValueError("actual_minute_input_not_frozen_cache")
    settings = json.loads((output / "actual_strategy_settings.json").read_text())[0]["actual"]
    if (settings.get("enable_stage847_half_r_stop_retry") is not False
            or settings.get("enable_ai_product_pool_filter") is not True
            or settings.get("ai_product_pool_eligibility_path") != str(pool_file)
            or settings.get("ai_product_pool_strategy") != policy_id):
        raise ValueError("stage256_actual_settings_mismatch")
    provenance = {"status": "diagnostic_existing_minutes", "account_id": args.account_id,
                  "kind": kind, "path_id": entry.get("path_id"), "policy_id": policy_id,
                  "pool_file": str(pool_file), "registry": str(registry_file),
                  "registry_design_sha256": registry.get("design_sha256"),
                  "start": START, "end": END, "capital": CAPITAL,
                  "half_r_enabled": False, "ai_pool_enabled": True,
                  "input_sha256_before": pre, "input_sha256_after": post,
                  "pool_audit": audit, "started_at": started,
                  "completed_at": datetime.now().astimezone().isoformat(),
                  "source_runner": str(Path(stage251.__file__)),
                  "source_result_label": "Stage251 C inherited export; account identity is this Stage256 sidecar",
                  "production_qualified": False}
    (output / "stage256_account_provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": provenance["status"], "account_id": args.account_id,
                      "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
