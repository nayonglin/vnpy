"""Stage257：独立窗口/账户回放薄适配；现有分钟诊断，不下载、不训练。

经济引擎复用已审 Stage251 C。只改变冻结池、窗口及私有构造文件路径，
不修改正式模块。--check-only 仅验注册、池、源身份，不创建回测引擎。
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
from datetime import date, datetime
import importlib
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any

from stage256_run_account import (FIXED_PRODUCT, NON_FU_UNIVERSE, OFFICIAL_POLICY,
                                  _read_rows, sha256)

LINE = "research/lines/futures_trend_rollover_shape_same_volume"
DEFAULT_BASELINE = Path("/Users/mac/.codex/worktrees/formal-2020-replay/fian")
PRE_AI, FIRST_AI = "2019-12-31", "2022-01-28"
BUILDER_MODULE = "run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest"
BUILDER_PATHS = ("UNIVERSE_PATH", "AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH",
                 "AI_SATELLITE_ELIGIBILITY_PATH")


def validate_pool_rows(rows, policy_id, universe, snapshot_contracts=None,
                       legacy_pre_ai=False):
    universe = set(universe)
    if len(universe) != 18 or FIXED_PRODUCT in universe:
        raise ValueError("non_fu_universe_invalid")
    groups = {}
    for row in rows:
        if row.get("strategy") != policy_id:
            raise ValueError("pool_strategy_mismatch")
        try:
            d = date.fromisoformat(row["eval_date"]).isoformat()
            score, rank, top = float(row["score"]), int(row["score_rank"]), int(row["top_n"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("pool_numeric_or_date_invalid") from exc
        if (d != row["eval_date"] or not math.isfinite(score) or not row.get("score_type")
                or str(rank) != str(row["score_rank"]).strip()
                or str(top) != str(row["top_n"]).strip()):
            raise ValueError("pool_row_invalid")
        groups.setdefault(d, []).append(row)
    if not groups or min(groups) != PRE_AI:
        raise ValueError("pre_ai_boundary_missing")
    for d, group in groups.items():
        products = [r["product_vt_symbol"] for r in group]
        members = set(products)
        n = len(group)
        if (len(members) != n or not members <= universe | {FIXED_PRODUCT}
                or sorted(int(r["score_rank"]) for r in group) != list(range(1, n + 1))
                or {int(r["top_n"]) for r in group} != {n}):
            raise ValueError(f"snapshot_width_rank_or_universe:{d}")
        if d == PRE_AI:
            expected = universe if legacy_pre_ai else universe | {FIXED_PRODUCT}
            if members != expected:
                raise ValueError("pre_ai_membership_mismatch")
        elif d < FIRST_AI:
            raise ValueError("synthetic_pre_ai_month_not_permitted")
        if not (d == PRE_AI and legacy_pre_ai):
            if FIXED_PRODUCT not in members or group[products.index(FIXED_PRODUCT)]["score_rank"] != str(n):
                raise ValueError(f"fixed_fu_rank_or_membership:{d}")
        contract = (snapshot_contracts or {}).get(d)
        if contract:
            nonfu = members - {FIXED_PRODUCT}
            if len(nonfu) != int(contract["K"]) or not nonfu <= set(contract["U_members"]):
                raise ValueError(f"snapshot_contract_width_or_universe:{d}")
            if "members" in contract and members != set(contract["members"]):
                raise ValueError(f"snapshot_contract_members:{d}")
    if snapshot_contracts and set(snapshot_contracts) - groups.keys():
        raise ValueError("snapshot_contract_month_missing")
    return {"all_eval_dates": sorted(groups), "all_snapshot_count": len(groups),
            "all_row_count": len(rows), "widths": {d: len(groups[d]) for d in sorted(groups)},
            "legacy_pre_ai_static18": bool(legacy_pre_ai)}


def validate_registry_account(manifest, account_id):
    if account_id in manifest.get("aliases", {}):
        raise ValueError(f"alias_must_not_execute:{account_id}")
    entry = manifest.get("accounts", {}).get(account_id)
    if not isinstance(entry, dict):
        raise ValueError("account_absent_from_registry")
    windows = {w["window_id"]: w for w in manifest["windows"]}
    window = windows.get(entry.get("window_id"))
    if (not window or any(entry.get(k) != window.get(k) for k in ("start", "end"))
            or date.fromisoformat(entry["start"]) > date.fromisoformat(entry["end"])):
        raise ValueError("account_window_mismatch")
    policy = manifest.get("policies", {}).get(entry.get("pool_id"))
    if not policy or any(entry.get(k) != policy.get(k) for k in
                         ("pool_file", "pool_sha256", "policy_id", "kind", "path_id")):
        raise ValueError("account_policy_mismatch")
    pool = Path(entry["pool_file"])
    if not pool.is_absolute() or not pool.is_file() or sha256(pool) != entry["pool_sha256"]:
        raise ValueError("pool_sha256_or_path_mismatch")
    if manifest.get("capital") != 150000:
        raise ValueError("frozen_capital_changed")
    return dict(entry)


def require_window_snapshots(available, required):
    if not required:
        raise ValueError("trading_calendar_unavailable")
    selected = sorted({PRE_AI if d < FIRST_AI else d for d in required})
    missing = set(selected) - set(available)
    if missing:
        raise ValueError(f"missing_required_eval_date:{sorted(missing)}")
    return selected


@contextmanager
def private_builder_paths(module, destination):
    """已导入的函数共享源模块globals，因此重定向覆盖所有import引用。"""
    destination.mkdir(parents=True, exist_ok=True)
    original = {name: getattr(module, name) for name in BUILDER_PATHS}
    private = {name: destination / path.name for name, path in original.items()}
    try:
        for name, path in private.items():
            setattr(module, name, path)
        yield private
    finally:
        for name, path in original.items():
            setattr(module, name, path)


@contextmanager
def capture_supported_products(engine_class):
    local = "add_strategy" in engine_class.__dict__
    original = engine_class.add_strategy
    captured = []
    def add(engine, strategy_class, setting):
        result = original(engine, strategy_class, setting)
        products = sorted(engine.strategy.product_symbols)
        if products != sorted(NON_FU_UNIVERSE + [FIXED_PRODUCT]):
            raise ValueError(f"actual_loaded_universe_not_19:{products}")
        states = sorted(engine.strategy.states)
        positions = dict(engine.strategy.pos_data)
        if states != products or any(float(v) != 0 for v in positions.values()) or engine.capital != 150000:
            raise ValueError("initial_account_not_fresh_150000_or_state_keys_mismatch")
        captured.append(dict(actual_supported_symbols=products, actual_product_state_keys=states,
                             initial_positions=positions, initial_capital=engine.capital))
        return result
    engine_class.add_strategy = add
    try:
        yield captured
    finally:
        if local:
            engine_class.add_strategy = original
        else:
            delattr(engine_class, "add_strategy")


@contextmanager
def adapted_stage251(stage251, pool_file, policy_id, reference_parameters_path,
                     pool_audit, repo_root, baseline_root, private_universe):
    reference_parameters_path = reference_parameters_path.resolve()
    replacements = {"ai_product_pool_eligibility_path": pool_file,
                    "product_universe_csv_path": private_universe}
    compared = {k: str(baseline_root.resolve() / p.resolve().relative_to(repo_root.resolve()))
                for k, p in replacements.items()}
    original_declared, original_audit = stage251.declared_ablation, stage251.audit_historical_ai_pool
    original_read = Path.read_text

    @contextmanager
    def declared(s901, arm):
        if arm != "C":
            raise ValueError("stage257_requires_stage251_C")
        original_builder = s901.build_official_live_strategy_overrides
        def build():
            settings = dict(original_builder())
            if (settings.get("enable_stage847_half_r_stop_retry") is not True
                    or settings.get("enable_ai_product_pool_filter") is not True
                    or settings.get("ai_product_pool_strategy") != OFFICIAL_POLICY):
                raise ValueError("official_base_flags_or_policy_changed")
            settings.update({k: str(v) for k, v in replacements.items()})
            settings["enable_stage847_half_r_stop_retry"] = False
            settings["ai_product_pool_strategy"] = policy_id
            return settings
        s901.build_official_live_strategy_overrides = build
        try:
            yield
        finally:
            s901.build_official_live_strategy_overrides = original_builder

    def audit(official_path, required_dates):
        selected = require_window_snapshots(pool_audit["all_eval_dates"], required_dates)
        official = original_audit(official_path, required_dates)
        if official.get("status") != "valid":
            raise ValueError("official_source_pool_audit_failed")
        return {"status": "valid", "strategy": policy_id, "eligibility_sha256": sha256(pool_file),
                "selected_eval_dates": selected, "required_eval_dates": required_dates,
                "validated_snapshot_count": pool_audit["all_snapshot_count"],
                "validated_eval_dates": pool_audit["all_eval_dates"],
                "official_source_sha256": official["eligibility_sha256"],
                "required_calendar_rule": "Stage901 month-start prior completed trade date",
                "scope": "Stage257 frozen research eligibility"}

    def read_text(path, *args, **kwargs):
        content = original_read(path, *args, **kwargs)
        if path.resolve() != reference_parameters_path:
            return content
        parameters = json.loads(content)
        overrides = parameters["spec"]["overrides"]
        if (overrides.get("enable_stage847_half_r_stop_retry") is not True
                or overrides.get("ai_product_pool_strategy") != OFFICIAL_POLICY):
            raise ValueError("accepted_A_reference_changed")
        overrides.update(compared)
        overrides["ai_product_pool_strategy"] = policy_id
        return json.dumps(parameters, ensure_ascii=False)

    stage251.declared_ablation, stage251.audit_historical_ai_pool = declared, audit
    Path.read_text = read_text
    try:
        yield
    finally:
        Path.read_text = original_read
        stage251.declared_ablation, stage251.audit_historical_ai_pool = original_declared, original_audit


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def relabel_exports(output, account_id, entry):
    """只改身份文本；CSV数值保持原字符串，原JSON来源另存。"""
    variant = f"stage257_{account_id}"
    scope = "offline_stage257_multicycle_pool_randomization"
    label = f"Stage257 {account_id}：现有分钟诊断"
    note = "冻结月池；独立窗口空仓15万；0.5R关闭，C2保留；零手续费及原模型滑点。数据缺口不满足严格验收。"
    for name in ("metrics", "run_provenance"):
        path = output / f"{name}.json"
        value = json.loads(path.read_text())
        dump(output / f"inherited_stage251_{name}.json", value)
        value.update(stage=257, account_id=account_id, window_id=entry["window_id"], pool_id=entry["pool_id"],
                     result_scope=scope, production_qualified=False)
        if name == "metrics":
            value.update(variant=variant, label=label, note=note)
        else:
            value.update(source_scope=scope, inherited_runner_stage=251,
                         arm="Stage257", declared_ablation_delta={
                             "half_r_enabled": False, "pool_id": entry["pool_id"],
                             "window_id": entry["window_id"], "private_universe_content_identical": True})
        dump(path, value)
    values = dict(profile=variant, variant=variant, combo_variant=variant,
                  label=label, note=note, result_scope=scope)
    for path in output.glob("*.csv"):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = reader.fieldnames
            if not columns or not set(columns) & values.keys():
                continue
            rows = list(reader)
        for row in rows:
            for key in set(columns) & values.keys():
                row[key] = values[key]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader(); writer.writerows(rows)


def bootstrap(root):
    """与Stage251相同的导入环境；必须先于任何旧config模块导入。"""
    import stage251_half_r_ablation as stage251
    os.chdir(root)
    sys.path[:0] = [str(root), str(stage251.BUNDLE / "vendor"), str(root / "examples/portfolio_backtesting")]
    signals = root / LINE / "outputs/stage251_half_r_ab/shared_signal_inputs"
    if signals.exists() and any(signals.iterdir()):
        raise ValueError("accepted_missing_signal_input_changed")
    for name in ("OFFICIAL_LIVE_SIGNAL_INPUT_DIR", "OFFICIAL_LIVE_OUTPUT_DIR"):
        os.environ[name] = str(signals)
    os.environ["OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED"] = "0"
    os.environ["OFFICIAL_LIVE_PHASE_D_SESSION_DAEMON_ENABLED"] = "0"
    os.environ["TZ"] = "Asia/Shanghai"
    if hasattr(time, "tzset"):
        time.tzset()
    return stage251


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", required=True, type=Path)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--baseline-root", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if not args.experiment.is_absolute() or not args.output.is_absolute():
        raise ValueError("experiment_and_output_must_be_absolute")
    experiment, output = args.experiment.resolve(), args.output.resolve()
    manifest_path = experiment / "experiment_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("stage") != 257:
        raise ValueError("manifest_stage_not_257")
    root = Path(manifest["root"]).resolve()
    output.relative_to(root / LINE / "outputs")
    entry = validate_registry_account(manifest, args.account_id)
    if entry.get("output") and Path(entry["output"]).resolve() != output:
        raise ValueError("account_output_mismatch")
    if output.exists() and any(output.iterdir()):
        raise ValueError("output_not_empty")
    pool_file = Path(entry["pool_file"])
    universe = manifest.get("non_fu_universe", NON_FU_UNIVERSE)
    if set(universe) != set(NON_FU_UNIVERSE):
        raise ValueError("frozen_universe_changed")
    qualification = Path(manifest["qualification_path"])
    if sha256(qualification) != manifest["qualification_sha256"]:
        raise ValueError("qualification_sha256_mismatch")
    contracts = json.loads(qualification.read_text())
    legacy = entry["kind"] == "legacy_ai"
    common = entry["kind"] == "common_pre_ai"
    if entry["kind"] == "ai_fair":
        contracts = {d: dict(v, members=v["AI_members"] + [FIXED_PRODUCT]) for d, v in contracts.items()}
    audit = validate_pool_rows(_read_rows(pool_file), entry["policy_id"], universe,
                               None if legacy or common else contracts, legacy_pre_ai=legacy)
    if common and (audit["all_snapshot_count"] != 1 or entry["end"] >= "2022-02-07"):
        raise ValueError("common_pre_ai_window_out_of_scope")
    source = Path(manifest["source_pool"])
    if legacy and pool_file.read_bytes() != source.read_bytes():
        raise ValueError("legacy_pool_not_source_byte_copy")
    reference_parameters = Path(manifest["parameters_reference_path"])
    if any(float(v) != 0 for v in json.loads(reference_parameters.read_text())["rates"].values()):
        raise ValueError("reference_commission_not_zero")
    accepted = root / LINE / "outputs/stage251_half_r_ab/accepted_A_parameters.json"
    files = {"manifest": manifest_path, "pool": pool_file, "source_pool": source,
             "minute": Path(manifest["minute_csv"]), "qualification": qualification,
             "reference_settings": Path(manifest["reference_settings_path"]),
             "parameters_reference": reference_parameters, "accepted_A_parameters": accepted,
             "universe_source": Path(manifest["universe_source"]), "adapter": Path(__file__)}
    pre = {k: sha256(p) for k, p in files.items()}
    for key, expected in (("minute", "minute_cache_sha256"), ("source_pool", "source_pool_sha256"),
                          ("universe_source", "universe_source_sha256")):
        if pre[key] != manifest[expected]:
            raise ValueError(f"{key}_sha256_mismatch")
    if args.check_only:
        print(json.dumps(dict(status="stage257_preflight_passed_no_engine", account_id=args.account_id,
                              entry=entry, pool_audit=audit, input_sha256=pre), ensure_ascii=False))
        return
    output.mkdir(parents=True, exist_ok=True)
    stage251 = bootstrap(root)
    builder = importlib.import_module(BUILDER_MODULE)
    s901 = importlib.import_module("analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow")
    shared_paths = {name: Path(getattr(builder, name)) for name in BUILDER_PATHS}
    shared_hashes = {name: sha256(path) for name, path in shared_paths.items() if path.is_file()}
    original_argv = sys.argv[:]
    started = datetime.now().astimezone().isoformat()
    private_hashes = {}
    try:
        with private_builder_paths(builder, output / "_legacy_builder_inputs") as paths:
            builder.build_static18_plus_fu_universe()
            builder.build_ai_satellite_post_signal_eligibility()
            private_hashes = {name: sha256(paths[name]) for name in BUILDER_PATHS if paths[name].exists()}
            for name, digest in private_hashes.items():
                if digest != shared_hashes.get(name):
                    raise ValueError(f"private_builder_bytes_differ:{name}")
            if private_hashes["UNIVERSE_PATH"] != manifest["universe_source_sha256"]:
                raise ValueError("private_universe_not_frozen")
            with adapted_stage251(stage251, pool_file, entry["policy_id"], accepted, audit,
                                  root, args.baseline_root.resolve(), paths["UNIVERSE_PATH"]), \
                    capture_supported_products(s901.s847.Stage847StopRetryEngine) as supported:
                sys.argv = [str(Path(stage251.__file__)), "--repo-root", str(root),
                            "--baseline-root", str(args.baseline_root.resolve()), "--arm", "C",
                            "--start", entry["start"], "--end", entry["end"], "--output", str(output),
                            "--diagnostic-incomplete-minutes"]
                stage251.main()
            for name, digest in private_hashes.items():
                if sha256(paths[name]) != digest:
                    raise ValueError(f"private_builder_changed:{name}")
    except BaseException as exc:
        dump(output / "stage257_account_failure.json", dict(stage=257, account_id=args.account_id,
             window_id=entry["window_id"], pool_id=entry["pool_id"], error=repr(exc),
             status="failed_preserved_not_accepted", input_sha256=pre, started_at=started))
        raise
    finally:
        sys.argv = original_argv
    post = {k: sha256(p) for k, p in files.items()}
    if pre != post or any(sha256(shared_paths[k]) != v for k, v in shared_hashes.items()):
        raise ValueError("stage257_shared_input_changed")
    inherited = json.loads((output / "run_provenance.json").read_text())
    actual_rows = json.loads((output / "actual_strategy_settings.json").read_text())
    if len(actual_rows) != 1 or len(supported) != 1:
        raise ValueError("one_fresh_engine_required")
    actual = actual_rows[0]["actual"]
    expected = dict(enable_stage847_half_r_stop_retry=False, enable_ai_product_pool_filter=True,
                    ai_product_pool_strategy=entry["policy_id"], ai_product_pool_eligibility_path=str(pool_file),
                    product_universe_csv_path=str(output / "_legacy_builder_inputs" / shared_paths["UNIVERSE_PATH"].name))
    if any(actual.get(k) != v for k, v in expected.items()):
        raise ValueError("actual_stage257_settings_mismatch")
    if inherited["minute_input_sha256"] != pre["minute"] or not inherited["diagnostic_incomplete_minutes"]:
        raise ValueError("actual_data_identity_or_diagnostic_mode_mismatch")
    parameters = json.loads((output / "effective_parameters.json").read_text())
    if any(float(v) != 0 for v in parameters["rates"].values()):
        raise ValueError("actual_commission_not_zero")
    relabel_exports(output, args.account_id, entry)
    provenance = dict(stage=257, status="diagnostic_existing_minutes", account_id=args.account_id,
        run_id=args.account_id, manifest_sha256=pre["manifest"], pool_sha256=pre["pool"],
        **{k: entry[k] for k in ("window_id", "pool_id", "kind", "path_id", "start", "end", "policy_id")},
        pool_file=str(pool_file), experiment_manifest=str(manifest_path), capital=manifest["capital"],
        fresh_engine_and_account=True, fresh_engine=True, **supported[0],
        half_r_enabled=False, ai_pool_enabled=True, commission_rate=0,
        input_sha256_before=pre, input_sha256_after=post, pool_audit=audit,
        private_builder_sha256=private_hashes, shared_builder_sha256_unchanged=shared_hashes,
        started_at=started, completed_at=datetime.now().astimezone().isoformat(), argv=original_argv,
        source_runner=str(Path(stage251.__file__)), production_qualified=False)
    dump(output / "stage257_account_provenance.json", provenance)
    check_path = output / "data_check.json"
    check = json.loads(check_path.read_text())
    check.update(stage=257, ai_strategy=entry["policy_id"],
                 historical_ai_boundary="Stage257 frozen membership; shared pre-AI static18+fu except explicit legacy source control")
    dump(check_path, check)
    print(json.dumps(dict(status=provenance["status"], account_id=args.account_id, output=str(output)), ensure_ascii=False))


if __name__ == "__main__":
    main()
