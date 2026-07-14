from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[4]
LINE_DIR = ROOT_DIR / "research" / "lines" / "futures_trend_fu_sc_proxy_option_qualification"
BETA_TOOL_PATH = LINE_DIR / "tools" / "stage001_fu_sc_t1_beta_gate.py"
BETA_OUTPUT_DIR = LINE_DIR / "outputs" / "stage001_fu_sc_t1_beta_gate"
BETA_DECISION_PATH = BETA_OUTPUT_DIR / "stage001_decision.json"
BETA_SELECTION_PATH = BETA_OUTPUT_DIR / "stage001_contract_selection_ledger.csv.gz"
STAGE132_TOOL_PATH = (
    ROOT_DIR
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_v2_optimization"
    / "tools"
    / "stage132_c9_event_option_metadata_batches.py"
)
OUTPUT_DIR = LINE_DIR / "outputs" / "stage001_sc_option_chain_coverage"
EVENT_CACHE_DIRNAME = "event_cache"
ENABLE_NETWORK = os.environ.get("STAGE001_SC_CHAIN_ENABLE_NETWORK", "0") == "1"
MAX_SECONDS_PER_EVENT = 90
MIN_ALL_COVERAGE = 0.90
CORE_EXPECTED = 6

FetchResult = tuple[
    str,
    list[str],
    pd.DataFrame,
    pd.DataFrame,
    dict[str, Any],
    str,
    float,
]
Fetcher = Callable[[Mapping[str, Any], int], FetchResult]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _atomic_text(path: Path, text: str) -> None:
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)


def _atomic_csv(frame: pd.DataFrame, path: Path) -> None:
    temp = path.with_name(path.name + ".tmp")
    frame.to_csv(temp, index=False)
    temp.replace(path)


def build_query_plan() -> tuple[pd.DataFrame, dict[str, str]]:
    beta_module = _load_module(BETA_TOOL_PATH, "fu_sc_beta_for_chain")
    events, event_audit = beta_module.load_fu_events()
    beta_decision = json.loads(BETA_DECISION_PATH.read_text(encoding="utf-8"))
    if not bool(beta_decision.get("local_beta_gate_pass", False)):
        raise RuntimeError("local beta gate is not approved")
    selection = pd.read_csv(
        BETA_SELECTION_PATH,
        parse_dates=["selection_date", "return_date"],
    )
    sc = selection[
        selection["product_vt_symbol"].eq("sc.INE")
        & selection["status"].eq("ok")
    ][
        [
            "selection_date",
            "return_date",
            "selected_symbol",
            "selected_open_interest",
        ]
    ].copy()
    plan = events.merge(
        sc,
        left_on="entry_date",
        right_on="return_date",
        how="left",
        validate="one_to_one",
    )
    if plan["selected_symbol"].isna().any():
        raise RuntimeError("some FU events have no T-1 SC contract mapping")
    if not plan["selection_date"].lt(plan["entry_date"]).all():
        raise RuntimeError("SC mapping contains same-day or future OI")
    plan["tqsdk_underlying"] = "INE." + plan["selected_symbol"].astype(str)
    plan["query_start"] = plan["entry_date"].dt.strftime("%Y-%m-%d")
    plan["query_end"] = plan["entry_date"].dt.strftime("%Y-%m-%d 23:59:59")
    plan["is_core_window"] = plan["entry_date"].between(
        beta_module.CORE_START, beta_module.CORE_END
    ).astype(int)
    plan["query_id"] = plan.apply(
        lambda row: hashlib.sha256(
            f"{row['event_id']}|{row['tqsdk_underlying']}|{row['query_start']}".encode()
        ).hexdigest(),
        axis=1,
    )
    plan.sort_values(["is_core_window", "entry_date", "event_id"], ascending=[False, True, True], inplace=True)
    plan.reset_index(drop=True, inplace=True)
    if len(plan) != 32 or plan["event_id"].nunique() != 32:
        raise RuntimeError("SC chain plan must contain 32 unique FU events")
    if int(plan["is_core_window"].sum()) != CORE_EXPECTED:
        raise RuntimeError("SC chain canary must contain 6 core events")
    source_hashes = {
        "events_sha256": str(event_audit["events_sha256"]),
        "beta_tool_sha256": sha256_file(BETA_TOOL_PATH),
        "beta_decision_sha256": sha256_file(BETA_DECISION_PATH),
        "beta_selection_sha256": sha256_file(BETA_SELECTION_PATH),
        "chain_tool_sha256": sha256_file(Path(__file__).resolve()),
        "stage132_producer_sha256": sha256_file(STAGE132_TOOL_PATH),
    }
    return plan, source_hashes


def _event_dir(cache_root: Path, event_id: str) -> Path:
    return cache_root / event_id


def _write_event_cache(
    cache_root: Path,
    event: Mapping[str, Any],
    source_hashes: Mapping[str, str],
    fetch_result: FetchResult,
) -> Path:
    event_id = str(event["event_id"])
    final_dir = _event_dir(cache_root, event_id)
    if final_dir.exists():
        raise RuntimeError(f"event cache already exists: {final_dir}")
    cache_root.mkdir(parents=True, exist_ok=True)
    temp_dir = cache_root / f".tmp_{event_id}_{os.getpid()}_{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=False, exist_ok=False)
    terminal, symbols, untouched, normalized, audit, message, elapsed = fetch_result
    request = {
        "event_id": event_id,
        "query_id": str(event["query_id"]),
        "fu_vt_symbol": str(event["vt_symbol"]),
        "entry_date": pd.Timestamp(event["entry_date"]).date().isoformat(),
        "selection_date": pd.Timestamp(event["selection_date"]).date().isoformat(),
        "sc_selected_symbol": str(event["selected_symbol"]),
        "tqsdk_underlying": str(event["tqsdk_underlying"]),
        "query_start": str(event["query_start"]),
        "query_end": str(event["query_end"]),
        "query_options": {"expired": False},
        "source_hashes": dict(source_hashes),
        "credential_values_persisted": False,
    }
    status = {
        "event_id": event_id,
        "terminal_status": str(terminal),
        "symbol_count": int(len(symbols)),
        "untouched_row_count": int(len(untouched)),
        "normalized_row_count": int(len(normalized)),
        "metadata_audit": dict(audit),
        "message": str(message),
        "elapsed_seconds": float(elapsed),
        "credential_values_persisted": False,
    }
    try:
        (temp_dir / "request.json").write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (temp_dir / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (temp_dir / "symbols.json").write_text(json.dumps(list(symbols), indent=2) + "\n", encoding="utf-8")
        if str(terminal) == "extracted":
            untouched.to_csv(temp_dir / "untouched_metadata.csv", index=False)
            normalized.to_csv(temp_dir / "normalized_metadata.csv", index=False)
        manifest_rows = []
        for path in sorted(temp_dir.iterdir()):
            if path.is_file():
                manifest_rows.append(
                    {
                        "name": path.name,
                        "bytes": path.stat().st_size,
                        "sha256": sha256_file(path),
                    }
                )
        pd.DataFrame(manifest_rows).to_csv(temp_dir / "manifest.csv", index=False)
        temp_dir.replace(final_dir)
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    return final_dir


def validate_event_cache(
    event_dir: Path,
    event: Mapping[str, Any],
    source_hashes: Mapping[str, str],
) -> dict[str, Any]:
    required = {"request.json", "status.json", "symbols.json", "manifest.csv"}
    missing = sorted(name for name in required if not (event_dir / name).is_file())
    if missing:
        return {"cache_valid": False, "reason": f"missing:{','.join(missing)}"}
    try:
        request = json.loads((event_dir / "request.json").read_text(encoding="utf-8"))
        status = json.loads((event_dir / "status.json").read_text(encoding="utf-8"))
        manifest = pd.read_csv(event_dir / "manifest.csv")
    except Exception as exc:
        return {"cache_valid": False, "reason": f"parse:{type(exc).__name__}"}
    hashes_ok = True
    for row in manifest.itertuples(index=False):
        path = event_dir / str(row.name)
        hashes_ok = bool(
            hashes_ok
            and path.is_file()
            and int(path.stat().st_size) == int(row.bytes)
            and sha256_file(path) == str(row.sha256)
        )
    identity_ok = bool(
        request.get("event_id") == str(event["event_id"])
        and request.get("query_id") == str(event["query_id"])
        and request.get("tqsdk_underlying") == str(event["tqsdk_underlying"])
        and request.get("selection_date") == pd.Timestamp(event["selection_date"]).date().isoformat()
        and request.get("query_options", {}).get("expired") is False
        and request.get("source_hashes") == dict(source_hashes)
        and request.get("credential_values_persisted") is False
        and status.get("credential_values_persisted") is False
    )
    terminal = str(status.get("terminal_status", ""))
    metadata_ok = True
    if terminal == "extracted":
        metadata_ok = bool(
            (event_dir / "untouched_metadata.csv").is_file()
            and (event_dir / "normalized_metadata.csv").is_file()
            and int(status.get("symbol_count", 0)) > 0
            and int(status.get("untouched_row_count", 0)) > 0
            and int(status.get("normalized_row_count", 0)) > 0
        )
    cache_valid = bool(hashes_ok and identity_ok and metadata_ok)
    return {
        "cache_valid": cache_valid,
        "reason": "" if cache_valid else "hash_identity_or_metadata_failed",
        "terminal_status": terminal,
        "symbol_count": int(status.get("symbol_count", 0)),
        "untouched_row_count": int(status.get("untouched_row_count", 0)),
        "normalized_row_count": int(status.get("normalized_row_count", 0)),
        "elapsed_seconds": float(status.get("elapsed_seconds", 0.0)),
        "event_cache_path": str(event_dir),
    }


def _real_fetcher(event: Mapping[str, Any], max_seconds: int) -> FetchResult:
    stage132 = _load_module(STAGE132_TOOL_PATH, "stage132_for_fu_sc_chain")
    return stage132.fetch_option_metadata_network(event, max_seconds)


def run(
    *,
    output_dir: Path = OUTPUT_DIR,
    enable_network: bool = ENABLE_NETWORK,
    fetcher: Fetcher | None = None,
) -> dict[str, Any]:
    plan, source_hashes = build_query_plan()
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_root = output_dir / EVENT_CACHE_DIRNAME
    if fetcher is None:
        fetcher = _real_fetcher

    fetch_calls = 0
    if enable_network:
        canary = plan[plan["is_core_window"].eq(1)]
        for event in canary.to_dict(orient="records"):
            event_dir = _event_dir(cache_root, str(event["event_id"]))
            validation = validate_event_cache(event_dir, event, source_hashes) if event_dir.exists() else {"cache_valid": False}
            if not validation.get("cache_valid", False):
                _write_event_cache(cache_root, event, source_hashes, fetcher(event, MAX_SECONDS_PER_EVENT))
                fetch_calls += 1
        canary_status = []
        for event in canary.to_dict(orient="records"):
            canary_status.append(validate_event_cache(_event_dir(cache_root, str(event["event_id"])), event, source_hashes))
        canary_pass = bool(
            len(canary_status) == CORE_EXPECTED
            and all(row.get("cache_valid") and row.get("terminal_status") == "extracted" for row in canary_status)
        )
        if canary_pass:
            remaining = plan[plan["is_core_window"].ne(1)]
            for event in remaining.to_dict(orient="records"):
                event_dir = _event_dir(cache_root, str(event["event_id"]))
                validation = validate_event_cache(event_dir, event, source_hashes) if event_dir.exists() else {"cache_valid": False}
                if not validation.get("cache_valid", False):
                    _write_event_cache(cache_root, event, source_hashes, fetcher(event, MAX_SECONDS_PER_EVENT))
                    fetch_calls += 1
    else:
        canary_pass = False

    ledger_rows = []
    normalized_frames = []
    for event in plan.to_dict(orient="records"):
        event_dir = _event_dir(cache_root, str(event["event_id"]))
        if event_dir.exists():
            validation = validate_event_cache(event_dir, event, source_hashes)
        else:
            validation = {
                "cache_valid": False,
                "reason": "not_run",
                "terminal_status": "not_run",
                "symbol_count": 0,
                "untouched_row_count": 0,
                "normalized_row_count": 0,
                "elapsed_seconds": 0.0,
                "event_cache_path": "",
            }
        ledger_rows.append(
            {
                "event_id": str(event["event_id"]),
                "entry_date": pd.Timestamp(event["entry_date"]),
                "fu_vt_symbol": str(event["vt_symbol"]),
                "selection_date": pd.Timestamp(event["selection_date"]),
                "sc_selected_symbol": str(event["selected_symbol"]),
                "tqsdk_underlying": str(event["tqsdk_underlying"]),
                "is_core_window": int(event["is_core_window"]),
                **validation,
            }
        )
        if validation.get("cache_valid") and validation.get("terminal_status") == "extracted":
            frame = pd.read_csv(event_dir / "normalized_metadata.csv")
            frame.insert(0, "event_id", str(event["event_id"]))
            frame.insert(1, "entry_date", pd.Timestamp(event["entry_date"]).date().isoformat())
            frame.insert(2, "requested_underlying", str(event["tqsdk_underlying"]))
            normalized_frames.append(frame)
    ledger = pd.DataFrame(ledger_rows).sort_values(["entry_date", "event_id"])
    combined = pd.concat(normalized_frames, ignore_index=True) if normalized_frames else pd.DataFrame()

    completed = int(ledger["cache_valid"].astype(bool).sum())
    extracted = int(
        (ledger["cache_valid"].astype(bool) & ledger["terminal_status"].eq("extracted")).sum()
    )
    core = ledger[ledger["is_core_window"].eq(1)]
    core_extracted = int(
        (core["cache_valid"].astype(bool) & core["terminal_status"].eq("extracted")).sum()
    )
    coverage = extracted / len(ledger)
    if not enable_network:
        decision_label = "PLAN_ONLY_NETWORK_DISABLED"
    elif core_extracted != CORE_EXPECTED or completed != len(ledger) or coverage < MIN_ALL_COVERAGE:
        decision_label = "CLOSE_LINE_OPTION_CHAIN_INELIGIBLE"
    else:
        decision_label = "ALLOW_STAGE002_EXECUTION_DATA_PREDECL_ONLY"
    decision = {
        "decision": decision_label,
        "network_enabled": bool(enable_network),
        "fetch_calls_this_run": fetch_calls,
        "event_count": int(len(ledger)),
        "core_event_count": int(len(core)),
        "cache_valid_count": completed,
        "extracted_event_count": extracted,
        "extracted_coverage_ratio": coverage,
        "core_extracted_event_count": core_extracted,
        "canary_pass": bool(core_extracted == CORE_EXPECTED),
        "minimum_all_coverage": MIN_ALL_COVERAGE,
        "ready_for_stage002_execution_data_predecl": decision_label == "ALLOW_STAGE002_EXECUTION_DATA_PREDECL_ONLY",
        "ready_for_option_strategy_ab": False,
        "ready_for_live": False,
        "premium_or_bar_downloaded": False,
        "source_hashes": source_hashes,
    }
    plan_path = output_dir / "stage001_sc_chain_query_plan.csv"
    ledger_path = output_dir / "stage001_sc_chain_event_ledger.csv"
    combined_path = output_dir / "stage001_sc_chain_normalized_metadata.csv"
    decision_path = output_dir / "stage001_sc_chain_decision.json"
    report_path = output_dir / "stage001_sc_chain_report.md"
    manifest_path = output_dir / "stage001_sc_chain_manifest.csv"
    _atomic_csv(plan, plan_path)
    _atomic_csv(ledger, ledger_path)
    _atomic_csv(combined, combined_path)
    _atomic_text(decision_path, json.dumps(decision, indent=2, sort_keys=True) + "\n")
    report = "\n".join(
        [
            "# Stage001 SC historical option-chain coverage",
            "",
            f"- decision: `{decision_label}`",
            f"- valid cache: `{completed}/{len(ledger)}`",
            f"- extracted: `{extracted}/{len(ledger)}` (`{coverage:.6%}`)",
            f"- core extracted: `{core_extracted}/{CORE_EXPECTED}`",
            f"- fetch calls this run: `{fetch_calls}`",
            "- premium/bar/tick downloaded: `False`",
            "- option strategy A/B allowed: `False`",
        ]
    )
    _atomic_text(report_path, report + "\n")
    manifest_rows = []
    for path in [plan_path, ledger_path, combined_path, decision_path, report_path]:
        manifest_rows.append(
            {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        )
    if cache_root.is_dir():
        for path in sorted(cache_root.glob("*/manifest.csv")):
            manifest_rows.append(
                {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
            )
    _atomic_csv(pd.DataFrame(manifest_rows), manifest_path)
    return {
        "decision": decision,
        "plan": plan,
        "ledger": ledger,
        "combined": combined,
        "paths": {
            "plan": plan_path,
            "ledger": ledger_path,
            "combined": combined_path,
            "decision": decision_path,
            "report": report_path,
            "manifest": manifest_path,
        },
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps({"decision": result["decision"], "paths": {k: str(v) for k, v in result["paths"].items()}}, sort_keys=True))
