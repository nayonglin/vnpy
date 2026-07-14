from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[4]
LINE_DIR = ROOT_DIR / "research" / "lines" / "futures_trend_fu_sc_proxy_option_qualification"
STAGE132_TOOL_PATH = (
    ROOT_DIR
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_v2_optimization"
    / "tools"
    / "stage132_c9_event_option_metadata_batches.py"
)
CHAIN_DIR = LINE_DIR / "outputs" / "stage001_sc_option_chain_coverage"
CHAIN_PLAN_PATH = CHAIN_DIR / "stage001_sc_chain_query_plan.csv"
CHAIN_DECISION_PATH = CHAIN_DIR / "stage001_sc_chain_decision.json"
CHAIN_MANIFEST_PATH = CHAIN_DIR / "stage001_sc_chain_manifest.csv"
CHAIN_CACHE_ROOT = CHAIN_DIR / "event_cache"
BETA_DIR = LINE_DIR / "outputs" / "stage001_fu_sc_t1_beta_gate"
BETA_SELECTION_PATH = BETA_DIR / "stage001_contract_selection_ledger.csv.gz"
BETA_EVENT_PATH = BETA_DIR / "stage001_fu_event_beta_ledger.csv"
ACQUISITION_REQUIREMENTS_PATH = (
    ROOT_DIR
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_v2_optimization"
    / "outputs"
    / "stage131_c9_event_targeted_option_acquisition_manifest"
    / "rebuilt_c9_v2_stage131_c9_event_targeted_option_acquisition_manifest_acquisition_requirements_"
    "stage131_c9_event_targeted_option_acquisition_manifest_v1.csv"
)
OUTPUT_DIR = LINE_DIR / "outputs" / "stage002_execution_preflight"

CORE_START = pd.Timestamp("2022-03-09")
CORE_END = pd.Timestamp("2022-06-29")
CORE_EXPECTED = 6
MIN_ALL_PASS_RATE = 0.90
FU_MULTIPLIER = 10.0
SC_MULTIPLIER = 1000.0
ATM_DELTA_PROXY = 0.5
MIN_IDEAL_OPTION_LOTS = 2.0


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


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def validate_manifest(manifest_path: Path, root: Path) -> tuple[bool, int]:
    manifest = pd.read_csv(manifest_path)
    bad = 0
    for row in manifest.itertuples(index=False):
        path = root / str(row.name) if hasattr(row, "name") else Path(str(row.path))
        if not path.is_file():
            bad += 1
            continue
        if int(path.stat().st_size) != int(row.bytes) or sha256_file(path) != str(row.sha256):
            bad += 1
    return bad == 0, bad


def semantic_revalidate_event(
    event_dir: Path,
    *,
    requested_underlying: str,
    stage132: Any,
) -> tuple[dict[str, Any], pd.DataFrame]:
    required = {
        "request.json",
        "status.json",
        "symbols.json",
        "untouched_metadata.csv",
        "normalized_metadata.csv",
        "manifest.csv",
    }
    missing = sorted(name for name in required if not (event_dir / name).is_file())
    if missing:
        return {"semantic_pass": False, "reason": f"missing:{','.join(missing)}"}, pd.DataFrame()
    manifest_ok, manifest_bad = validate_manifest(event_dir / "manifest.csv", event_dir)
    request = json.loads((event_dir / "request.json").read_text(encoding="utf-8"))
    status = json.loads((event_dir / "status.json").read_text(encoding="utf-8"))
    symbols = json.loads((event_dir / "symbols.json").read_text(encoding="utf-8"))
    untouched = pd.read_csv(event_dir / "untouched_metadata.csv")
    persisted = pd.read_csv(event_dir / "normalized_metadata.csv")
    recomputed = stage132.normalize_option_metadata(untouched)
    audit = stage132.audit_extracted_metadata(
        symbols,
        untouched,
        recomputed,
        requested_underlying=requested_underlying,
    )
    comparison = stage132.compare_normalized_metadata(persisted, recomputed)
    status_audit = dict(status.get("metadata_audit", {}))
    status_audit_match = status_audit == audit
    identity_ok = bool(
        request.get("tqsdk_underlying") == requested_underlying
        and request.get("query_options", {}).get("expired") is False
        and status.get("terminal_status") == "extracted"
        and request.get("credential_values_persisted") is False
        and status.get("credential_values_persisted") is False
    )
    semantic_pass = bool(
        manifest_ok
        and identity_ok
        and bool(audit.get("integrity_pass", False))
        and bool(comparison.get("normalized_recompute_pass", False))
        and status_audit_match
    )
    result = {
        "semantic_pass": semantic_pass,
        "reason": "" if semantic_pass else "manifest_identity_audit_or_recompute_failed",
        "manifest_bad_count": manifest_bad,
        "identity_ok": int(identity_ok),
        "metadata_integrity_pass": int(bool(audit.get("integrity_pass", False))),
        "normalized_recompute_pass": int(bool(comparison.get("normalized_recompute_pass", False))),
        "normalized_value_mismatch_count": int(comparison.get("normalized_value_mismatch_count", -1)),
        "status_audit_match": int(status_audit_match),
        "symbol_count": int(len(symbols)),
        "untouched_rows": int(len(untouched)),
        "persisted_rows": int(len(persisted)),
        "recomputed_rows": int(len(recomputed)),
    }
    return result, recomputed


def rank_atm_candidates(
    metadata: pd.DataFrame,
    *,
    event_id: str,
    entry_date: pd.Timestamp,
    requested_underlying: str,
    option_class: str,
    sc_t1_close: float,
) -> pd.DataFrame:
    required = {
        "option_symbol",
        "underlying_symbol",
        "option_class",
        "expire_datetime",
        "strike_price",
        "expired",
        "volume_multiple",
        "price_tick",
    }
    missing = sorted(required.difference(metadata.columns))
    if missing:
        raise RuntimeError(f"metadata missing selection columns: {missing}")
    data = metadata.copy()
    data["option_class"] = data["option_class"].astype(str).str.upper()
    data["expire_datetime"] = pd.to_datetime(data["expire_datetime"], errors="coerce")
    data["strike_price"] = pd.to_numeric(data["strike_price"], errors="coerce")
    data["volume_multiple"] = pd.to_numeric(data["volume_multiple"], errors="coerce")
    data["price_tick"] = pd.to_numeric(data["price_tick"], errors="coerce")
    cutoff = pd.Timestamp(entry_date).normalize() + pd.Timedelta(days=1)
    valid = data[
        data["underlying_symbol"].astype(str).eq(requested_underlying)
        & data["option_class"].eq(option_class)
        & data["expire_datetime"].ge(cutoff)
        & data["strike_price"].gt(0)
        & data["strike_price"].map(np.isfinite)
        & data["expired"].map(lambda value: not _as_bool(value))
        & data["volume_multiple"].eq(SC_MULTIPLIER)
        & data["price_tick"].gt(0)
    ].copy()
    if valid.empty:
        return valid
    valid["distance_to_sc_t1_close"] = (valid["strike_price"] - float(sc_t1_close)).abs()
    valid.sort_values(
        ["distance_to_sc_t1_close", "strike_price", "option_symbol"],
        kind="mergesort",
        inplace=True,
    )
    valid.reset_index(drop=True, inplace=True)
    valid.insert(0, "event_id", event_id)
    valid.insert(1, "rank", np.arange(1, len(valid) + 1, dtype=int))
    valid.insert(2, "selected", valid["rank"].eq(1).astype(int))
    valid.insert(3, "entry_date", pd.Timestamp(entry_date).date().isoformat())
    valid.insert(4, "sc_t1_close", float(sc_t1_close))
    return valid


def ideal_option_lots(
    *,
    fu_volume: float,
    fu_multiplier: float,
    fu_weighted_entry_price: float,
    beta: float,
    sc_multiplier: float,
    sc_t1_close: float,
    atm_delta_proxy: float,
) -> float:
    numerator = fu_volume * fu_multiplier * fu_weighted_entry_price * beta
    denominator = sc_multiplier * sc_t1_close * atm_delta_proxy
    if not math.isfinite(numerator) or not math.isfinite(denominator) or denominator <= 0:
        return float("nan")
    return numerator / denominator


def evaluate() -> dict[str, Any]:
    stage132 = _load_module(STAGE132_TOOL_PATH, "stage132_for_stage002_preflight")
    plan = pd.read_csv(
        CHAIN_PLAN_PATH,
        parse_dates=["entry_date", "selection_date", "return_date"],
    )
    chain_decision = json.loads(CHAIN_DECISION_PATH.read_text(encoding="utf-8"))
    if chain_decision.get("decision") != "ALLOW_STAGE002_EXECUTION_DATA_PREDECL_ONLY":
        raise RuntimeError("Stage001 chain is not approved for Stage002 preflight")
    if len(plan) != 32 or plan["event_id"].nunique() != 32 or int(plan["is_core_window"].sum()) != 6:
        raise RuntimeError("Stage001 query plan drift")

    semantic_rows: list[dict[str, Any]] = []
    metadata_frames: dict[str, pd.DataFrame] = {}
    for event in plan.to_dict(orient="records"):
        event_id = str(event["event_id"])
        result, recomputed = semantic_revalidate_event(
            CHAIN_CACHE_ROOT / event_id,
            requested_underlying=str(event["tqsdk_underlying"]),
            stage132=stage132,
        )
        semantic_rows.append(
            {
                "event_id": event_id,
                "entry_date": pd.Timestamp(event["entry_date"]),
                "requested_underlying": str(event["tqsdk_underlying"]),
                "is_core_window": int(event["is_core_window"]),
                **result,
            }
        )
        metadata_frames[event_id] = recomputed
    semantic = pd.DataFrame(semantic_rows).sort_values(["entry_date", "event_id"])

    beta_selection = pd.read_csv(
        BETA_SELECTION_PATH,
        parse_dates=["selection_date", "return_date"],
    )
    sc_selection = beta_selection[
        beta_selection["product_vt_symbol"].eq("sc.INE")
        & beta_selection["status"].eq("ok")
    ][
        ["return_date", "selection_date", "selected_symbol", "prior_close"]
    ].copy()
    sc_selection.rename(
        columns={
            "selection_date": "sc_selection_date",
            "selected_symbol": "sc_selected_symbol_check",
            "prior_close": "sc_t1_close",
        },
        inplace=True,
    )
    beta_events = pd.read_csv(BETA_EVENT_PATH, parse_dates=["entry_date"])[
        ["event_id", "full126_beta", "event_beta_pass"]
    ]
    requirements = pd.read_csv(ACQUISITION_REQUIREMENTS_PATH)
    requirements = requirements[requirements["event_id"].isin(plan["event_id"])].copy()
    requirements["volume"] = pd.to_numeric(requirements["volume"], errors="coerce")
    requirements["entry_price"] = pd.to_numeric(requirements["entry_price"], errors="coerce")
    requirements["size"] = pd.to_numeric(requirements["size"], errors="coerce")

    context_rows: list[dict[str, Any]] = []
    for event_id, group in requirements.groupby("event_id", sort=False):
        directions = sorted(group["direction"].dropna().astype(str).str.lower().unique())
        sizes = sorted(group["size"].dropna().unique())
        if len(directions) != 1 or len(sizes) != 1:
            raise RuntimeError(f"ambiguous FU context for {event_id}")
        volume = float(group["volume"].sum())
        weighted_entry = float((group["volume"] * group["entry_price"]).sum() / volume)
        direction = directions[0]
        option_class = "PUT" if direction == "long" else "CALL" if direction == "short" else ""
        if not option_class:
            raise RuntimeError(f"invalid FU direction for {event_id}")
        context_rows.append(
            {
                "event_id": str(event_id),
                "fu_direction": direction,
                "option_class": option_class,
                "fu_total_volume": volume,
                "fu_multiplier": float(sizes[0]),
                "fu_weighted_entry_price": weighted_entry,
                "fu_lot_count": int(len(group)),
            }
        )
    context = pd.DataFrame(context_rows)
    event_context = (
        plan.merge(sc_selection, left_on="entry_date", right_on="return_date", how="left", validate="one_to_one")
        .merge(beta_events, on="event_id", how="left", validate="one_to_one")
        .merge(context, on="event_id", how="left", validate="one_to_one")
    )
    event_context["context_integrity_pass"] = (
        event_context["selection_date"].eq(event_context["sc_selection_date"])
        & event_context["selected_symbol"].eq(event_context["sc_selected_symbol_check"])
        & event_context["sc_t1_close"].gt(0)
        & event_context["event_beta_pass"].eq(1)
        & event_context["fu_multiplier"].eq(FU_MULTIPLIER)
    ).astype(int)

    candidate_frames: list[pd.DataFrame] = []
    selected_rows: list[dict[str, Any]] = []
    for event in event_context.to_dict(orient="records"):
        event_id = str(event["event_id"])
        metadata = metadata_frames[event_id]
        candidates = rank_atm_candidates(
            metadata,
            event_id=event_id,
            entry_date=pd.Timestamp(event["entry_date"]),
            requested_underlying=str(event["tqsdk_underlying"]),
            option_class=str(event["option_class"]),
            sc_t1_close=float(event["sc_t1_close"]),
        )
        if not candidates.empty:
            candidate_frames.append(candidates)
            selected = candidates.iloc[0]
            selected_option = str(selected["option_symbol"])
            selected_strike = float(selected["strike_price"])
            selected_expiry = pd.Timestamp(selected["expire_datetime"])
            selected_multiplier = float(selected["volume_multiple"])
            selected_tick = float(selected["price_tick"])
        else:
            selected_option = ""
            selected_strike = float("nan")
            selected_expiry = pd.NaT
            selected_multiplier = float("nan")
            selected_tick = float("nan")
        selection_pass = not candidates.empty
        ideal = ideal_option_lots(
            fu_volume=float(event["fu_total_volume"]),
            fu_multiplier=float(event["fu_multiplier"]),
            fu_weighted_entry_price=float(event["fu_weighted_entry_price"]),
            beta=float(event["full126_beta"]),
            sc_multiplier=SC_MULTIPLIER,
            sc_t1_close=float(event["sc_t1_close"]),
            atm_delta_proxy=ATM_DELTA_PROXY,
        )
        rounded = int(math.floor(ideal + 0.5)) if math.isfinite(ideal) else 0
        relative_rounding_error = abs(rounded - ideal) / ideal if ideal > 0 else float("nan")
        selected_rows.append(
            {
                "event_id": event_id,
                "entry_date": pd.Timestamp(event["entry_date"]),
                "is_core_window": int(event["is_core_window"]),
                "fu_vt_symbol": str(event["vt_symbol"]),
                "fu_direction": str(event["fu_direction"]),
                "option_class": str(event["option_class"]),
                "sc_selection_date": pd.Timestamp(event["sc_selection_date"]),
                "requested_underlying": str(event["tqsdk_underlying"]),
                "sc_t1_close": float(event["sc_t1_close"]),
                "full126_beta": float(event["full126_beta"]),
                "fu_total_volume": float(event["fu_total_volume"]),
                "fu_multiplier": float(event["fu_multiplier"]),
                "fu_weighted_entry_price": float(event["fu_weighted_entry_price"]),
                "candidate_count": int(len(candidates)),
                "selected_option_symbol": selected_option,
                "selected_strike": selected_strike,
                "selected_expiry": selected_expiry,
                "selected_multiplier": selected_multiplier,
                "selected_price_tick": selected_tick,
                "distance_to_sc_t1_close": abs(selected_strike - float(event["sc_t1_close"])) if math.isfinite(selected_strike) else float("nan"),
                "ideal_option_lots": ideal,
                "nearest_integer_option_lots": rounded,
                "relative_rounding_error": relative_rounding_error,
                "metadata_semantic_pass": int(
                    semantic.loc[semantic["event_id"].eq(event_id), "semantic_pass"].iloc[0]
                ),
                "context_integrity_pass": int(event["context_integrity_pass"]),
                "selection_pass": int(selection_pass),
                "granularity_pass": int(
                    selection_pass and math.isfinite(ideal) and ideal >= MIN_IDEAL_OPTION_LOTS
                ),
            }
        )
    candidates_all = pd.concat(candidate_frames, ignore_index=True) if candidate_frames else pd.DataFrame()
    selection = pd.DataFrame(selected_rows).sort_values(["entry_date", "event_id"])

    metadata_pass_count = int(semantic["semantic_pass"].sum())
    selection_pass_count = int(selection["selection_pass"].sum())
    granularity_pass_count = int(selection["granularity_pass"].sum())
    core = selection[selection["is_core_window"].eq(1)]
    core_granularity_pass = int(core["granularity_pass"].sum())
    granularity_rate = granularity_pass_count / len(selection)
    metadata_gate = metadata_pass_count == 32
    selection_gate = bool(
        selection_pass_count == 32
        and int(selection["context_integrity_pass"].sum()) == 32
        and int(selection["metadata_semantic_pass"].sum()) == 32
    )
    granularity_gate = bool(
        len(core) == CORE_EXPECTED
        and core_granularity_pass == CORE_EXPECTED
        and granularity_rate >= MIN_ALL_PASS_RATE
    )
    if not metadata_gate:
        decision_label = "CLOSE_LINE_METADATA_SEMANTICS_INVALID"
    elif not selection_gate:
        decision_label = "CLOSE_LINE_SELECTION_INELIGIBLE"
    elif not granularity_gate:
        decision_label = "CLOSE_LINE_INTEGER_GRANULARITY_INELIGIBLE"
    else:
        decision_label = "PREFLIGHT_PASS_REQUIRES_INDEPENDENT_REVIEW"

    gates = pd.DataFrame(
        [
            {"gate_id": "metadata_semantic_revalidation_32_of_32", "evidence": metadata_pass_count, "threshold": 32, "passed": int(metadata_gate)},
            {"gate_id": "atm_adverse_selection_32_of_32", "evidence": selection_pass_count, "threshold": 32, "passed": int(selection_gate)},
            {"gate_id": "core_ideal_option_lots_ge_2_6_of_6", "evidence": core_granularity_pass, "threshold": 6, "passed": int(core_granularity_pass == 6)},
            {"gate_id": "all_ideal_option_lots_ge_2_rate_ge_90pct", "evidence": granularity_rate, "threshold": MIN_ALL_PASS_RATE, "passed": int(granularity_rate >= MIN_ALL_PASS_RATE)},
        ]
    )
    decision = {
        "decision": decision_label,
        "network_called": False,
        "event_count": int(len(selection)),
        "core_event_count": int(len(core)),
        "metadata_semantic_pass_count": metadata_pass_count,
        "selection_pass_count": selection_pass_count,
        "granularity_pass_count": granularity_pass_count,
        "granularity_pass_rate": granularity_rate,
        "core_granularity_pass_count": core_granularity_pass,
        "ideal_option_lots_min": float(selection["ideal_option_lots"].min()),
        "ideal_option_lots_median": float(selection["ideal_option_lots"].median()),
        "ideal_option_lots_max": float(selection["ideal_option_lots"].max()),
        "minimum_ideal_option_lots": MIN_IDEAL_OPTION_LOTS,
        "atm_delta_proxy": ATM_DELTA_PROXY,
        "ready_for_entry_day_data_canary": decision_label == "PREFLIGHT_PASS_REQUIRES_INDEPENDENT_REVIEW",
        "ready_for_option_strategy_ab": False,
        "ready_for_live": False,
        "source_hashes": {
            "chain_plan": sha256_file(CHAIN_PLAN_PATH),
            "chain_decision": sha256_file(CHAIN_DECISION_PATH),
            "chain_manifest": sha256_file(CHAIN_MANIFEST_PATH),
            "beta_selection": sha256_file(BETA_SELECTION_PATH),
            "beta_event": sha256_file(BETA_EVENT_PATH),
            "acquisition_requirements": sha256_file(ACQUISITION_REQUIREMENTS_PATH),
            "stage132_producer": sha256_file(STAGE132_TOOL_PATH),
            "stage002_tool": sha256_file(Path(__file__).resolve()),
        },
    }
    return {
        "semantic": semantic,
        "event_context": event_context,
        "candidates": candidates_all,
        "selection": selection,
        "gates": gates,
        "decision": decision,
    }


def write_outputs(output_dir: Path = OUTPUT_DIR) -> dict[str, Path]:
    result = evaluate()
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "semantic": output_dir / "stage002_metadata_semantic_revalidation.csv",
        "context": output_dir / "stage002_event_context.csv",
        "candidates": output_dir / "stage002_atm_candidate_ranking.csv",
        "selection": output_dir / "stage002_atm_selection_and_granularity.csv",
        "gates": output_dir / "stage002_preflight_gate_matrix.csv",
        "decision": output_dir / "stage002_preflight_decision.json",
        "report": output_dir / "stage002_preflight_report.md",
        "manifest": output_dir / "stage002_preflight_manifest.csv",
    }
    _atomic_csv(result["semantic"], paths["semantic"])
    _atomic_csv(result["event_context"], paths["context"])
    _atomic_csv(result["candidates"], paths["candidates"])
    _atomic_csv(result["selection"], paths["selection"])
    _atomic_csv(result["gates"], paths["gates"])
    _atomic_text(paths["decision"], json.dumps(result["decision"], indent=2, sort_keys=True) + "\n")
    d = result["decision"]
    core = result["selection"][result["selection"]["is_core_window"].eq(1)]
    report = "\n".join(
        [
            "# Stage002 execution-data preflight",
            "",
            f"- decision: `{d['decision']}`",
            f"- metadata semantic pass: `{d['metadata_semantic_pass_count']}/32`",
            f"- ATM adverse selection: `{d['selection_pass_count']}/32`",
            f"- ideal lots pass: `{d['granularity_pass_count']}/32`; core `{d['core_granularity_pass_count']}/6`",
            f"- ideal lots min/median/max: `{d['ideal_option_lots_min']:.6f}/{d['ideal_option_lots_median']:.6f}/{d['ideal_option_lots_max']:.6f}`",
            "- network called: `False`",
            "",
            "## Gates",
            "",
            result["gates"].to_markdown(index=False),
            "",
            "## Core selection",
            "",
            core[
                [
                    "entry_date",
                    "fu_vt_symbol",
                    "fu_direction",
                    "requested_underlying",
                    "sc_t1_close",
                    "selected_option_symbol",
                    "selected_strike",
                    "ideal_option_lots",
                    "granularity_pass",
                ]
            ].to_markdown(index=False, floatfmt=".6f"),
        ]
    )
    _atomic_text(paths["report"], report + "\n")
    manifest_rows = []
    for name, path in paths.items():
        if name == "manifest":
            continue
        manifest_rows.append(
            {"artifact": name, "path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        )
    _atomic_csv(pd.DataFrame(manifest_rows).sort_values("artifact"), paths["manifest"])
    return paths


if __name__ == "__main__":
    paths = write_outputs()
    decision = json.loads(paths["decision"].read_text(encoding="utf-8"))
    print(json.dumps({"decision": decision, "paths": {key: str(path) for key, path in paths.items()}}, sort_keys=True))
