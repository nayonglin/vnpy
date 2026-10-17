"""Bounded, offline independent confirmation of Stage017's zero-data failure."""
from __future__ import annotations

import ast
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[5]
LINE = ROOT / "research/lines/futures_trend_triple_screen"
SOURCE = LINE / "outputs/stage017_required_ap210_batch"
ATTEMPT = SOURCE / "network_attempt1"
OUT = Path(__file__).resolve().parent


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    parent = read(ATTEMPT / "parent_receipt.json")
    worker = read(ATTEMPT / "worker_receipt.json")
    quality = read(ATTEMPT / "quality.json")
    error = read(ATTEMPT / "safe_error.json")
    progress = read(ATTEMPT / "progress.json")
    started = read(ATTEMPT / "attempt_started.json")
    preflight = read(SOURCE / "preflight.json")
    manifest = read(SOURCE / "batch_manifest.json")
    assert parent["status"] == "worker_terminal" and parent["exit_code"] == 1
    assert parent["hard_kill"] is False and 0 < parent["elapsed_seconds"] < 600
    assert parent["all_inputs_unchanged"] is True
    assert parent["automatic_retry"] is False and parent["provider_attempts_max"] == 1
    assert worker["status"] == "provider_or_local_failed"
    assert worker["provider_attempts"] == 1 and worker["local_TqSim_created"] is True
    assert worker["tq_dl_permission"] is False and worker["tq_dl_check_readonly"] is True
    assert worker["download_interface_switched"] is False
    assert worker["completed_minutes"] == 0 and worker["target_minutes"] == 12945
    assert worker["accepted_sessions"] == 0 and worker["required_ap210_accepted"] is False
    assert error == dict(category="network_or_wait_timeout", exception_type="TimeoutError",
                         raw_exception_text_saved=False)
    assert started["provider_attempts_max"] == 1 and started["automatic_retry"] is False
    assert started["soft_seconds"] == 570 and started["hard_seconds"] == 600
    assert progress["completed_minutes"] == 0 and progress["target_minutes"] == 12945
    assert progress["network_attempts"] == 1
    assert quality["raw_rows"] == 0 and quality["accepted_sessions"] == 0
    assert quality["target_sessions"] == 39 and quality["all_sessions_accepted"] is False
    assert quality["required_ap210_accepted"] is False
    assert len(quality["sessions"]) == 39
    expected = {(t["vt_symbol"], t["execution_trade_date"]): t for t in manifest["targets"]}
    actual = {(t["vt_symbol"], t["execution_trade_date"]): t for t in quality["sessions"]}
    assert len(expected) == len(actual) == 39 and expected.keys() == actual.keys()
    assert len(manifest["contracts"]) == 8
    assert sum(t["expected_minutes"] for t in expected.values()) == 12945
    for key, item in actual.items():
        assert item["accepted"] is False and item["completion_evidence_complete"] is False
        assert item["status"] == "quarantined" and item["reason"] == "incomplete_session"
        assert item["actual_rows"] == item["new_minutes"] == item["base_overlap_minutes"] == 0
        assert item["expected_minutes"] == item["missing_minutes"] == expected[key]["expected_minutes"]
        assert item["aggregate"] == {} and item["daily_mismatch_fields"] == []
    ap = actual[("AP210.CZCE", "2022-04-06")]
    assert ap["expected_minutes"] == ap["missing_minutes"] == 225
    empty_csvs = {}
    for name in ("raw_completed_minutes.csv", "completion_evidence.csv"):
        path = ATTEMPT / name
        with path.open(newline="") as stream:
            reader = csv.DictReader(stream)
            fields = reader.fieldnames
            rows = list(reader)
        assert fields and not rows
        empty_csvs[name] = dict(rows=0, columns=fields, bytes=path.stat().st_size, sha256=sha(path))
    for key in ("financial_replays", "orders", "cancels", "broker_or_ctp_connections"):
        assert parent[key] == worker[key] == 0
    for key in ("raw_sdk_output_saved", "credential_values_saved", "cache_or_overlay_written", "production_qualified"):
        assert parent[key] is worker[key] is False
    assert worker["model_fits"] == 0
    assert preflight["status"] == "passed_offline_preflight_no_connection"
    assert preflight["credential_values_saved"] is False and preflight["auth_checks_unmodified"] is True
    frozen = preflight["source_fingerprints"]
    source_hashes = {}
    for path, expected_sha in frozen.items():
        assert sha(path) == expected_sha, path
        source_hashes[path] = expected_sha
    for path, expected_sha in manifest["input_sha256"].items():
        assert frozen[path] == expected_sha and sha(path) == expected_sha, path
    tool = LINE / "tools/stage017_required_ap210_batch.py"
    assert sha(tool) == "0e3da2f00677f4d6d9f722f44e92a86d404383d6e7b8de05c66b7ab4c5192f14"
    assert sha(SOURCE / "batch_manifest.json") == "a58a875df23d2dda6c797d94e7f46275f0b832377325ef7cf68423b7601a0219"
    dangerous = {"insert_order", "cancel_order", "send_order", "send_orders", "buy", "sell", "short", "cover"}
    direct_order_calls = []
    for path in (tool, LINE / "tools/stage012_provider_batch.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call):
                name = node.func.attr if isinstance(node.func, ast.Attribute) else (
                    node.func.id if isinstance(node.func, ast.Name) else "")
                if name in dangerous:
                    direct_order_calls.append(dict(path=str(path), line=node.lineno, call=name))
    assert not direct_order_calls
    parent_bound_artifacts = {}
    for name, expected_sha in parent["artifact_sha256"].items():
        assert sha(ATTEMPT / name) == expected_sha, name
        parent_bound_artifacts[name] = expected_sha
    assert set(parent_bound_artifacts) == {p.name for p in ATTEMPT.iterdir() if p.is_file()} - {"parent_receipt.json"}
    for path in [SOURCE / "preflight.json", SOURCE / "batch_manifest.json", *ATTEMPT.iterdir()]:
        if path.is_file():
            source_hashes[str(path)] = sha(path)
    checks = dict(
        reviewed_at=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        status="failed_provider_probe_confirmed_no_qualified_data",
        parent_exit_code=1, parent_elapsed_seconds=parent["elapsed_seconds"], hard_kill=False,
        worker_status=worker["status"], safe_error=error,
        provider_attempts_observed=1, required_sessions=39, target_minutes=12945,
        qualified_precise_sessions=0, qualified_minute_rows=0, required_AP210_accepted=False,
        AP210_missing_minutes=225, empty_csvs=empty_csvs,
        frozen_inputs_rehashed=len(frozen), manifest_input_hashes_checked=len(manifest["input_sha256"]),
        parent_artifact_hashes_checked=len(parent_bound_artifacts), all_inputs_unchanged=True,
        tq_dl_permission_observed=False, timeout_cause_attributed_to_permission=False,
        direct_order_calls_in_wrapper_and_collector=direct_order_calls,
        review_network_calls=0, review_financial_replays=0, full_session_grid_recomputed=False,
        source_fingerprints=source_hashes,
    )
    write(OUT / "failure_checks.json", checks)
    report = """# Stage017 零数据失败终态独立复核

本次仅核已有终态文件与冻结输入，没有复连、重试、金融回放或逐会话重算网格。冻结工具、batch manifest 与 preflight 31 个来源 SHA 均与当前字节相同；父 receipt 绑定的七个产物 SHA 全部相同。

父进程终态 exit=1，64.247055 秒，无硬杀；worker=provider_or_local_failed，provider_attempts=1。safe_error 只有 network_or_wait_timeout / TimeoutError / raw_exception_text_saved=false。raw 与 completion_evidence 均仅表头、零数据行。quality 的39个目标均为 incomplete_session、实际0行、缺失分钟数等于目标数，总计12945；AP210.CZCE/2022-04-06缺225分钟，未接受。

本次正常 TqApi 构造已返回并执行未改 SDK 的只读 tq_dl 布尔检查，观测为 false；此事实不能证明该权限观测导致超时，也不能推断所有历史接口都不可用。没有转下载接口。父子均记录零订单、撤单、CTP/券商连接、金融回放、cache/overlay写入及原始SDK输出/凭证保存；冻结 wrapper 与复用 collector 无直接订单调用，SDK/auth 字节仍与 preflight 绑定一致。

结论：qualified_precise_sessions=0、qualified_minute_rows=0、required_AP210_accepted=false。此次是已确认的失败探针，不能用作研究补数资格，更不能满足 Stage016 的 AP210 输入门。P0/P1=0仅表示失败终态及隔离记录未发现矛盾，绝不表示数据通过。保留原失败产物，不改旧数据。

累计金融attempt仍4、完成1，C0无alpha结论。过拟合：否，本次只审来源失败与资格。继续价值：保留失败证据有价值，但本次没有提供可继续构建Stage016的新数据，后续数据路线由root另行决定。
"""
    (OUT / "independent_review.md").write_text(report)
    receipt = dict(
        reviewed_at=checks["reviewed_at"], reviewer="first_screen_independent",
        status=checks["status"], review_scope="bounded_terminal_failure_only",
        p0_findings=0, p1_findings=0, qualified_research_data=False,
        qualified_precise_sessions=0, qualified_minute_rows=0, required_AP210_accepted=False,
        parent_exit_code=1, parent_elapsed_seconds=parent["elapsed_seconds"], worker_status=worker["status"],
        provider_attempts_observed=1, target_sessions=39, target_minutes=12945,
        all_inputs_unchanged=True, frozen_inputs_rehashed=len(frozen),
        source_fingerprints=source_hashes,
        raw_path=str(ATTEMPT / "raw_completed_minutes.csv"),
        evidence_path=str(ATTEMPT / "completion_evidence.csv"),
        quality_path=str(ATTEMPT / "quality.json"), parent_receipt_path=str(ATTEMPT / "parent_receipt.json"),
        worker_receipt_path=str(ATTEMPT / "worker_receipt.json"),
        review_artifact_sha256={name: sha(OUT / name) for name in ("review_failure.py", "failure_checks.json", "independent_review.md")},
        financial_replays=0, network_calls=0, retries=0, Stage016_build_authorized=False,
        C0_attempt3_authorized=False, execution_fallback_authorized=False, production_qualified=False,
        financial_attempts_cumulative_unchanged=4, financial_completed_cumulative_unchanged=1,
        C0_alpha_verdict="not_evaluable", overfitting=False,
        continued_value="failure evidence retained; AP210 replacement remains unavailable",
    )
    write(OUT / "review_receipt.json", receipt)
    print(json.dumps({k:receipt[k] for k in ("status", "qualified_precise_sessions", "qualified_minute_rows", "required_AP210_accepted", "parent_exit_code", "frozen_inputs_rehashed")}, ensure_ascii=False))
    print("review_receipt_sha256=" + sha(OUT / "review_receipt.json"))


if __name__ == "__main__":
    main()
