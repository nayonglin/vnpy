"""Neutral account-only snapshots and pure export for A_OFF / B_OFF.

No numerical/native/data imports at module scope. The caller owns engine and
input validation; a seal records those gates, never an economic review. Tiny
fixtures carry an explicit scope and can never enter a financial comparison.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import date, datetime
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import pickle
import re
import stat
from types import SimpleNamespace
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REQUIRED_SOURCES = tuple(HERE / name for name in (
    "stage065_account_checkpoint.py", "stage065_pairwise_off_policy.py",
    "stage022_run_c0_qualified_wait.py", "stage031_run_ordered_checkpoint.py",
    "stage028_ordered_strategy.py", "stage028_ordered_engine.py",
    "stage035_b_ts_strategy.py", "stage035_b_ts_pricing.py")) + tuple(
    ROOT / "examples/portfolio_backtesting" / name for name in (
        "qmt_roll_portfolio_strategy.py", "analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine.py"))
ENGINE_VALIDATION = dict(engine_returned=True, actual_settings_match_off_expected=True,
    parameters_match_reference_except_off_policy=True, pairwise_decision_dependency_absent=True,
    actual_daily_dates_equal_preflight_reference=True, captured_bar_failures=0,
    strict_minute_missing_bars=0, all_consumed_inputs_unchanged_during_run=True,
    frozen_correctness_code_unchanged=True, historical_shared_signal_input_empty=True)
RESULT_SCOPE = "offline_full_2020_2026_shared_pairwise_off_native_vs_stage035_package"
FIXTURE_SCOPE = "finite_native_fill_checkpoint_fixture"


def _safe(value):
    if isinstance(value, Mapping):return {str(k):_safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [_safe(v) for v in value]
    if isinstance(value,(date,datetime,Path)):return str(value)
    if hasattr(value,"item"):return _safe(value.item())
    if isinstance(value,float) and not math.isfinite(value):return None
    return value


def _json_bytes(value):
    return (json.dumps(_safe(value),ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+"\n").encode()


def _sha(raw):return hashlib.sha256(raw).hexdigest()


def _no_links(path):
    path=Path(path).absolute()
    if any(item.is_symlink() for item in (path,*path.parents)):
        raise ValueError("checkpoint_path_not_owned_symlink")
    return path


def _owned(output,arm=None):
    path=_no_links(output)
    if path.name not in ("A_OFF","B_OFF") or (arm is not None and path.name!=arm):
        raise ValueError("checkpoint_requires_exact_owned_arm_output")
    return path


def _read_regular(path):
    path=_no_links(path)
    try:
        descriptor=os.open(path,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
        with os.fdopen(descriptor,"rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise ValueError("checkpoint_not_regular_file")
            return handle.read()
    except OSError as error:
        raise ValueError("checkpoint_required_file_unavailable:"+str(path)) from error


def _atomic(path,raw):
    path=_no_links(path)
    if path.exists():raise FileExistsError("checkpoint_refusing_overwrite:"+str(path))
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
    with temporary.open("xb") as handle:
        handle.write(raw);handle.flush();os.fsync(handle.fileno())
    os.replace(temporary,path)
    descriptor=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)


def _write_json(path,value):_atomic(path,_json_bytes(value))


def _binding_map(value):
    if not isinstance(value,Mapping) or not value:raise ValueError("checkpoint_missing_bindings")
    result={}
    for name,row in value.items():
        if not isinstance(row,Mapping) or not re.fullmatch(r"[a-f0-9]{64}",str(row.get("sha256",""))):
            raise ValueError("checkpoint_invalid_binding")
        if type(row.get("bytes")) is not int or row["bytes"]<0:raise ValueError("checkpoint_invalid_binding_size")
        result[str(name)]=dict(sha256=row["sha256"],bytes=row["bytes"])
    return result


def _check_preflight(preflight,arm):
    from stage065_pairwise_off_policy import disabled_pairwise_preflight
    sources=_binding_map(preflight.get("source_bindings"))
    data=_binding_map(preflight.get("data_bindings"))
    if not all(str(path) in sources for path in REQUIRED_SOURCES):
        raise ValueError("checkpoint_required_source_binding_missing")
    fixture=preflight.get("fixture_only")
    days=preflight.get("reference_calendar")
    if type(fixture) is not bool or not isinstance(days,list) or not days or days!=sorted(set(days)):
        raise ValueError("checkpoint_reference_calendar_invalid")
    for day in days:date.fromisoformat(day)
    scope="tiny_fixture" if fixture else "full_2020_2026"
    if preflight.get("reference_calendar_scope")!=scope:raise ValueError("checkpoint_calendar_scope_mismatch")
    if not fixture and (len(days)!=1641 or days[0]<"2020-01-01" or days[-1]>"2026-10-14"):
        raise ValueError("checkpoint_full_reference_calendar_not_1641")
    if preflight.get("disabled_pairwise")!=disabled_pairwise_preflight():
        raise ValueError("checkpoint_pairwise_policy_mismatch")
    native_module="analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine"
    expected=(dict(strategy_module=native_module,strategy_name="QmtRollPortfolioStrategyStage847C9StopRetry",
        engine_module=native_module,engine_name="Stage847StopRetryEngine") if arm=="A_OFF" else
        dict(strategy_module="stage035_b_ts_strategy",strategy_name="Stage035IndependentB_TS",
        engine_module="stage028_ordered_engine",engine_name="Stage028OrderedStage847StopRetryEngine"))
    if preflight.get("account_classes")!=expected:raise ValueError("checkpoint_account_class_identity_mismatch")
    return sources,data


def new_run_context(output,*,arm,preflight,started_at):
    output=_owned(output,arm)
    sources,data=_check_preflight(preflight,arm)
    output.mkdir(parents=True,exist_ok=True)
    snapshots={}
    for index,(name,binding) in enumerate(sorted(sources.items())):
        raw=_read_regular(Path(name))
        if _sha(raw)!=binding["sha256"] or len(raw)!=binding["bytes"]:
            raise ValueError("checkpoint_source_changed_before_context")
        relative=f"sources/source_{index:03d}.bin"
        _atomic(output/relative,raw)
        snapshots[name]=dict(binding,snapshot=relative)
    preflight_raw=_json_bytes(preflight)
    _atomic(output/"preflight_used.json",preflight_raw)
    context=dict(schema="stage065_run_context_v1",run_id=uuid.uuid4().hex,arm=arm,attempt=1,
        output_directory=str(output),started_at=str(started_at),writer=Path(__file__).name,
        writer_source_sha256=sources[str(Path(__file__).resolve())]["sha256"],
        source_bindings=sources,source_snapshots=snapshots,source_bindings_sha256=_sha(_json_bytes(sources)),
        data_bindings_sha256=_sha(_json_bytes(data)),preflight_sha256=_sha(preflight_raw),
        policy_sha256=preflight["disabled_pairwise"]["eight_key_policy_sha256"],
        fixture_only=preflight["fixture_only"],reference_calendar_scope=preflight["reference_calendar_scope"],
        production_qualified=False)
    _write_json(output/"run_context.json",context)
    return context


def _context(output,arm=None,*,verify_sources=True):
    output=_owned(output,arm)
    context_raw=_read_regular(output/"run_context.json")
    preflight_raw=_read_regular(output/"preflight_used.json")
    context=json.loads(context_raw);preflight=json.loads(preflight_raw)
    if (context.get("schema")!="stage065_run_context_v1" or context.get("arm")!=output.name
        or context.get("attempt")!=1 or context.get("output_directory")!=str(output)
        or not context.get("run_id") or context.get("writer")!=Path(__file__).name
        or context.get("production_qualified") is not False):raise ValueError("checkpoint_context_identity_mismatch")
    sources,data=_check_preflight(preflight,output.name)
    if (context.get("preflight_sha256")!=_sha(preflight_raw) or context.get("source_bindings")!=sources
        or context.get("source_bindings_sha256")!=_sha(_json_bytes(sources))
        or context.get("data_bindings_sha256")!=_sha(_json_bytes(data))
        or context.get("fixture_only") is not preflight["fixture_only"]
        or context.get("reference_calendar_scope")!=preflight["reference_calendar_scope"]
        or context.get("policy_sha256")!=preflight["disabled_pairwise"]["eight_key_policy_sha256"]
        or context.get("writer_source_sha256")!=sources[str(Path(__file__).resolve())]["sha256"]):
        raise ValueError("checkpoint_context_binding_mismatch")
    snapshots=context.get("source_snapshots",{})
    if set(snapshots)!=set(sources):raise ValueError("checkpoint_source_snapshot_missing")
    for name,row in sources.items():
        snapshot=snapshots[name]
        if not re.fullmatch(r"sources/source_[0-9]{3}\.bin",str(snapshot.get("snapshot",""))):
            raise ValueError("checkpoint_source_snapshot_not_owned")
        if verify_sources:
            for path in (Path(name),output/snapshot["snapshot"]):
                raw=_read_regular(path)
                if _sha(raw)!=row["sha256"] or len(raw)!=row["bytes"]:
                    raise ValueError("checkpoint_source_binding_sha_mismatch")
        if snapshot!={**row,"snapshot":snapshot["snapshot"]}:raise ValueError("checkpoint_source_snapshot_binding_mismatch")
    return output,context,preflight,context_raw


def _account_only(value,_path=(),_strategy_id=None):
    if not _path and isinstance(value,Mapping):
        preflight=value.get("preflight")
        identity=preflight.get("active_parameter_identity") if isinstance(preflight,Mapping) else None
        _strategy_id=identity.get("strategy_version") if isinstance(identity,Mapping) else None
    if isinstance(value,Mapping):
        for key,item in value.items():
            path=(*_path,key)
            if key in ("engine","strategy","history","history_data","minute_cache","stage827_minute_by_symbol"):
                # This bound AI-pool audit field is an identity string, never
                # an engine strategy. No other path or value earns an exception.
                if not (path==("preflight","ai_pool_audit","strategy") and type(item) is str
                    and item==_strategy_id=="ai_top10_plus_fu_official_live_v1"):
                    raise ValueError("checkpoint_forbidden_engine_or_history")
            _account_only(item,path,_strategy_id)
    elif isinstance(value,(list,tuple)):
        for index,item in enumerate(value):_account_only(item,(*_path,index),_strategy_id)
    elif value is not None and not isinstance(value,(str,int,float,bool,date,datetime,Path)):
        module=type(value).__module__
        if not module.startswith(("pandas.","numpy")):
            raise ValueError("checkpoint_non_account_object:"+type(value).__name__)
        # Object cells / attrs can otherwise hide an engine or model inside a
        # perfectly ordinary DataFrame and make the "account-only" pickle huge.
        if hasattr(value,"select_dtypes"):
            _account_only(value.attrs,(*_path,"<attrs>"),_strategy_id)
            _account_only(value.index.tolist(),(*_path,"<index>"),_strategy_id)
            _account_only(value.columns.tolist(),(*_path,"<columns>"),_strategy_id)
            for index,item in enumerate(value.select_dtypes(include=["object"]).to_numpy().flat):
                _account_only(item,(*_path,"<object_cells>",index),_strategy_id)
        elif getattr(getattr(value,"dtype",None),"hasobject",False):
            for index,item in enumerate(value.tolist()):_account_only(item,(*_path,index),_strategy_id)


def save_failure_capture(output,payload,*,error):
    output,context,_,_=_context(output,verify_sources=False)
    _account_only(payload)
    raw=gzip.compress(pickle.dumps(dict(schema="stage065_partial_failure_capture_v1",partial=True,
        run_context=context,capture=payload),protocol=5),mtime=0)
    _atomic(output/"failure_capture.pkl.gz",raw)
    failure=dict(status="failed_partial_no_engine_seal",partial=True,arm=context["arm"],run_id=context["run_id"],
        error=str(error),failure_capture_sha256=_sha(raw),production_qualified=False)
    _write_json(output/"run_failure.json",failure)
    return failure


def save_raw_checkpoint(output,payload):
    required={"combined","frames","capture","actual_trade_identities","ordered","actual","parameters",
        "spec","preflight","input_fingerprints","run_context","engine_elapsed_seconds",
        "wait_audit","resolver_audit","qualification_audit"}
    if not required.issubset(payload) or payload.get("combined") is None or not payload.get("frames"):
        save_failure_capture(output,payload,error="engine_return_incomplete")
        raise ValueError("checkpoint_engine_return_incomplete")
    # Persist returned tables before checking code drift. Seal/load always check
    # current sources; a post-engine source failure must still leave raw evidence.
    output,context,preflight,context_raw=_context(output,verify_sources=False)
    if payload["run_context"]!=context or payload["preflight"]!=preflight:
        raise ValueError("checkpoint_payload_context_mismatch")
    if (context["arm"]=="A_OFF" and payload["ordered"] is not None) or (
        context["arm"]=="B_OFF" and (not isinstance(payload["ordered"],dict)
        or set(payload["ordered"])!={"decision","fill","execution","pending"})):
        raise ValueError("checkpoint_ordered_owner_mismatch")
    _account_only(payload)
    folder=output/"checkpoint";folder.mkdir(exist_ok=False)
    raw=gzip.compress(pickle.dumps(dict(payload,schema="stage065_raw_account_checkpoint_v1"),protocol=5),mtime=0)
    _atomic(folder/"raw_account.pkl.gz",raw)
    manifest=dict(schema="stage065_raw_checkpoint_manifest_v1",status="raw_evidence_not_validation_or_performance_pass",
        raw_filename="raw_account.pkl.gz",raw_sha256=_sha(raw),raw_bytes=len(raw),run_context_sha256=_sha(context_raw),
        output_directory=str(output),run_id=context["run_id"],arm=context["arm"],attempt=1,
        writer=context["writer"],writer_source_sha256=context["writer_source_sha256"],
        source_bindings_sha256=context["source_bindings_sha256"],data_bindings_sha256=context["data_bindings_sha256"],
        policy_sha256=context["policy_sha256"],account_exports_only=True,fixture_only=context["fixture_only"],
        reference_calendar_scope=context["reference_calendar_scope"],production_qualified=False)
    _write_json(folder/"raw_manifest.json",manifest)
    return manifest


def _validation(validation,context,preflight):
    if (any(type(validation.get(k)) is not type(v) or validation[k]!=v for k,v in ENGINE_VALIDATION.items())
        or validation.get("fixture_only") is not context["fixture_only"]
        or validation.get("reference_calendar_scope")!=context["reference_calendar_scope"]
        or type(validation.get("actual_daily_count")) is not int
        or validation["actual_daily_count"]!=len(preflight["reference_calendar"])):
        raise ValueError("checkpoint_engine_not_validated")


def _raw_envelope(output,arm=None):
    output,context,preflight,context_raw=_context(output,arm)
    folder=output/"checkpoint"
    manifest_raw=_read_regular(folder/"raw_manifest.json")
    manifest=json.loads(manifest_raw)
    expected=dict(schema="stage065_raw_checkpoint_manifest_v1",raw_filename="raw_account.pkl.gz",
        output_directory=str(output),run_id=context["run_id"],arm=context["arm"],attempt=1,
        writer=context["writer"],writer_source_sha256=context["writer_source_sha256"],
        source_bindings_sha256=context["source_bindings_sha256"],data_bindings_sha256=context["data_bindings_sha256"],
        policy_sha256=context["policy_sha256"],run_context_sha256=_sha(context_raw),account_exports_only=True,
        fixture_only=context["fixture_only"],reference_calendar_scope=context["reference_calendar_scope"],production_qualified=False)
    if any(manifest.get(k)!=v for k,v in expected.items()):raise ValueError("checkpoint_manifest_binding_mismatch")
    raw=_read_regular(folder/"raw_account.pkl.gz")
    if _sha(raw)!=manifest.get("raw_sha256") or len(raw)!=manifest.get("raw_bytes"):
        raise ValueError("checkpoint_raw_binding_sha_mismatch")
    return output,context,preflight,manifest,manifest_raw,raw


def seal_checkpoint(output,manifest,validation):
    output,context,preflight,observed,manifest_raw,_=_raw_envelope(output)
    if observed!=manifest:raise ValueError("checkpoint_manifest_changed_before_validation")
    _validation(validation,context,preflight)
    seal=dict(schema="stage065_engine_validation_seal_v1",status="engine_snapshot_validated_not_independent_economic_review",
        run_id=context["run_id"],arm=context["arm"],attempt=1,raw_sha256=manifest["raw_sha256"],
        manifest_sha256=_sha(manifest_raw),writer_source_sha256=context["writer_source_sha256"],
        validation=dict(validation),fixture_only=context["fixture_only"],reference_calendar_scope=context["reference_calendar_scope"],
        validated_at=str(datetime.now().astimezone()),production_qualified=False)
    raw=_json_bytes(seal)
    _atomic(output/"checkpoint/validation_seal.json",raw)
    _write_json(output/"checkpoint/seal_receipt.json",dict(schema="stage065_seal_receipt_v1",
        arm=context["arm"],run_id=context["run_id"],seal_sha256=_sha(raw)))
    return seal


def load_sealed_checkpoint(output,*,arm):
    """All file bindings are checked before decompress/unpickle, using one read."""
    output,context,preflight,manifest,manifest_raw,raw=_raw_envelope(output,arm)
    seal_raw=_read_regular(output/"checkpoint/validation_seal.json")
    receipt_raw=_read_regular(output/"checkpoint/seal_receipt.json")
    seal=json.loads(seal_raw);receipt=json.loads(receipt_raw)
    if receipt!=dict(schema="stage065_seal_receipt_v1",arm=arm,run_id=context["run_id"],seal_sha256=_sha(seal_raw)):
        raise ValueError("checkpoint_seal_binding_sha_mismatch")
    expected=dict(schema="stage065_engine_validation_seal_v1",status="engine_snapshot_validated_not_independent_economic_review",
        run_id=context["run_id"],arm=arm,attempt=1,raw_sha256=manifest["raw_sha256"],manifest_sha256=_sha(manifest_raw),
        writer_source_sha256=context["writer_source_sha256"],fixture_only=context["fixture_only"],
        reference_calendar_scope=context["reference_calendar_scope"],production_qualified=False)
    if any(seal.get(k)!=v for k,v in expected.items()):raise ValueError("checkpoint_seal_identity_mismatch")
    _validation(seal.get("validation",{}),context,preflight)
    payload=pickle.loads(gzip.decompress(raw))
    if (payload.get("schema")!="stage065_raw_account_checkpoint_v1" or payload.get("run_context")!=context
        or payload.get("preflight")!=preflight):raise ValueError("checkpoint_payload_identity_mismatch")
    if (arm=="A_OFF" and payload.get("ordered") is not None) or (arm=="B_OFF" and
        (not isinstance(payload.get("ordered"),dict) or set(payload["ordered"])!={"decision","fill","execution","pending"})):
        raise ValueError("checkpoint_ordered_owner_mismatch")
    return payload,dict(manifest=manifest,seal=seal,seal_sha256=_sha(seal_raw))


def _no_success(output):
    if (output/"summary.json").exists() or (output/"export_success.json").exists() or any((output/"exports").glob("export_*/summary.json")):
        raise FileExistsError("existing_success_refusing_export_overwrite")


def reserve_export_destination(output,*,arm):
    output=_owned(output,arm);_no_success(output)
    folder=_no_links(output/"exports");folder.mkdir(exist_ok=True)
    for index in range(1,10000):
        path=folder/f"export_{index:03d}"
        try:path.mkdir()
        except FileExistsError:continue
        return path
    raise RuntimeError("export_attempt_limit")


def export_checkpoint(output,destination,*,arm,metrics_function=None,export_only=False):
    import pandas as pd
    from stage022_run_c0_qualified_wait import canonical_trade_enums,attach_trading_dates
    from stage031_run_ordered_checkpoint import build_execution_clock
    output=_owned(output,arm);destination=_no_links(destination);_no_success(output)
    if destination!=output and (destination.parent!=output/"exports" or not re.fullmatch(r"export_[0-9]{3,4}",destination.name)):
        raise ValueError("export_destination_not_owned")
    if destination!=output and destination.exists() and any(destination.iterdir()):
        raise FileExistsError("export_attempt_refusing_overwrite")
    payload,binding=load_sealed_checkpoint(output,arm=arm)
    destination.mkdir(parents=True,exist_ok=True)
    context=payload["run_context"];capture=payload["capture"];ordered=payload["ordered"]
    fixture=context["fixture_only"];scope=FIXTURE_SCOPE if fixture else RESULT_SCOPE
    try:
        clock,usage=build_execution_clock(capture,payload["actual_trade_identities"])
        frames={name:frame.copy() for name,frame in payload["frames"].items()}
        trades=canonical_trade_enums(frames["trades"])
        if trades.empty:raise ValueError("no_trades_not_a_successful_candidate")
        if trades.trade_id.duplicated().any() or set(trades.trade_id)!=set(clock.trade_id):
            raise ValueError("account_trade_clock_identity_mismatch")
        sources=clock.trade_id.map(usage.set_index("trade_id").price_source).fillna("")
        synthetic=clock.offset.ne("开")&sources.str.startswith("stage")
        clock.loc[synthetic,"exit_reason"]=sources[synthetic]
        frames["trades"]=attach_trading_dates(trades,clock)
        def csv(name,frame):
            if frame.empty and not len(frame.columns):frame=pd.DataFrame(columns=["date","vt_symbol","event","reason"])
            frame=frame.copy();frame["research_arm"]=arm;frame["production_qualified"]=False
            target=_no_links(destination/name)
            if target.exists():raise FileExistsError("export_refusing_table_overwrite")
            frame.to_csv(target,index=False,encoding="utf-8-sig")
        for name,frame in frames.items():
            if not re.fullmatch(r"[A-Za-z0-9_]+",name):raise ValueError("account_frame_name_not_owned")
            csv(name+".csv",frame)
        for name,frame in (("daily.csv",payload["combined"]),("execution_clock.csv",clock),
            ("execution_proxy_usage.csv",usage),("actual_trade_identities.csv",pd.DataFrame(payload["actual_trade_identities"])),
            ("internal_equity_daily.csv",pd.DataFrame(capture.get("equity",[]))),
            ("minute_scan_requests.csv",pd.DataFrame(capture.get("minute_requests",[]))),
            ("execution_anchor_requests.csv",pd.DataFrame(capture.get("anchor_requests",[])))):csv(name,frame)
        counts=None
        if ordered is not None:
            for key,name in (("decision","ordered_gate_audit.csv"),("fill","ordered_fill_audit.csv"),
                    ("execution","ordered_execution_audit.csv"),("pending","ordered_pending_intents.csv")):
                csv(name,pd.DataFrame(ordered[key]))
            _write_json(destination/"ordered_audits.json",ordered)
            counts=dict(decision_rows=len(ordered["decision"]),decision_counts=dict(Counter(str(row.get("decision","")) for row in ordered["decision"])),
                fill_audit_rows=len(ordered["fill"]),execution_audit_rows=len(ordered["execution"]),pending_intents=len(ordered["pending"]))
        _write_json(destination/"qualified_wait_audit.json",dict(gate=payload["wait_audit"],resolver=payload["resolver_audit"],initial_qualification=payload["qualification_audit"]))
        if metrics_function is None:
            from analyze_qmt_roll_stage650_stage526_200k_capital_reality_check import _metrics
            metrics_function=_metrics
        statistics=metrics_function(payload["combined"],SimpleNamespace(**payload["spec"]["capital"]),1.0)
        statistics.update(result_scope=scope,fixture_only=fixture,production_qualified=False)
        provenance=dict(status="completed_pending_independent_review",arm=arm,attempt=1,run_id=context["run_id"],
            result_scope=scope,fixture_only=fixture,reference_calendar_scope=context["reference_calendar_scope"],
            ordered_applicable=ordered is not None,ordered_counts=counts,signal_machine_arm="B_TS" if ordered is not None else None,
            account_classes=payload["preflight"]["account_classes"],financial_replays=0 if fixture else 1,
            financial_replays_this_export_process=0 if export_only or fixture else 1,export_only=export_only,
            result_origin="same_engine_sealed_account_snapshot",production_qualified=False,checkpoint=binding,
            source_bindings=context["source_bindings"],data_bindings_sha256=context["data_bindings_sha256"],
            disabled_pairwise=payload["preflight"]["disabled_pairwise"],exported_at=str(datetime.now().astimezone()))
        for name,value in (("actual_strategy_settings.json",payload["actual"]),("effective_parameters.json",payload["parameters"]),
            ("input_manifest.json",payload["input_fingerprints"]),("effective_off_policy.json",payload["preflight"]["disabled_pairwise"]),
            ("metrics.json",statistics),("run_provenance.json",provenance)):_write_json(destination/name,value)
        summary={**provenance,"statistics":statistics,"output_directory":str(destination),"checkpoint_raw_sha256":binding["manifest"]["raw_sha256"]}
        summary_raw=_json_bytes(summary);_atomic(destination/"summary.json",summary_raw)
        _write_json(output/"export_success.json",dict(status=summary["status"],source=str(destination),summary_sha256=_sha(summary_raw),
            raw_sha256=binding["manifest"]["raw_sha256"],run_id=context["run_id"],arm=arm,fixture_only=fixture))
        return summary
    except Exception as error:
        if not (destination/"export_failure.json").exists():
            _write_json(destination/"export_failure.json",dict(status="pure_export_failed_snapshot_preserved",arm=arm,
                run_id=context["run_id"],error=repr(error),fixture_only=fixture,production_qualified=False))
        raise


def write_comparison_if_ready(root):
    """Only full sealed accounts qualify; fixture summaries never make a table."""
    root=_no_links(root);summaries={}
    for arm in ("A_OFF","B_OFF"):
        output=root/arm
        if not (output/"export_success.json").is_file():return None
        success=json.loads(_read_regular(output/"export_success.json"))
        if success.get("fixture_only") is not False:return None
        payload,binding=load_sealed_checkpoint(output,arm=arm)
        if payload["run_context"]["fixture_only"]:return None
        source=_no_links(success["source"])
        if source!=output and (source.parent!=output/"exports" or not re.fullmatch(r"export_[0-9]{3,4}",source.name)):
            raise ValueError("comparison_export_owner_mismatch")
        raw=_read_regular(source/"summary.json")
        if _sha(raw)!=success.get("summary_sha256"):raise ValueError("comparison_summary_binding_mismatch")
        summary=json.loads(raw)
        if (summary.get("arm")!=arm or summary.get("run_id")!=payload["run_context"]["run_id"]
            or summary.get("fixture_only") is not False or summary.get("result_scope")!=RESULT_SCOPE
            or summary.get("checkpoint_raw_sha256")!=binding["manifest"]["raw_sha256"]):
            raise ValueError("comparison_account_identity_mismatch")
        summaries[arm]=summary
    rows=[dict(arm="A0",status="restricted_fixed_pairwise_counterfactual",end_equity=2262595.,
        total_return_pct=1408.396667,max_dd_pct=-48.789850,sharpe=1.367364),
        dict(arm="original_B",status="failed_qualified_delivery_old_value_conflict",end_equity=None,
        total_return_pct=None,max_dd_pct=None,sharpe=None)]
    rows.extend(dict(arm=arm,status=value["status"],**{key:value["statistics"].get(key)
        for key in ("end_equity","total_return_pct","max_dd_pct","sharpe")}) for arm,value in summaries.items())
    result=dict(schema="stage065_pairwise_off_comparison_v1",status="pending_independent_review",rows=rows,
        result_scope=RESULT_SCOPE,production_qualified=False,original_goal_achieved=False)
    _write_json(root/"comparison.json",result)
    return result
