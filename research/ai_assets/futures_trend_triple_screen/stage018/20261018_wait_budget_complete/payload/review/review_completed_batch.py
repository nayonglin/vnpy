"""Offline bounded review of Stage018's exact 39-session completed batch."""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[5]
LINE = ROOT / "research/lines/futures_trend_triple_screen"
SOURCE = LINE / "outputs/stage018_provider_wait_budget"
ATTEMPT = SOURCE / "network_attempt1"
OUT = Path(__file__).resolve().parent
FIELDS = ("open", "high", "low", "close", "volume", "open_oi", "close_oi")
SAMPLES = (("AP210.CZCE", "2022-04-06"), ("AP205.CZCE", "2022-03-28"),
           ("MA205.CZCE", "2022-04-06"), ("au2206.SHFE", "2022-04-01"),
           ("cu2204.SHFE", "2022-03-28"))
# This fixed batch contains five ordinary night sessions followed by the
# Qingming closure. These explicit dates avoid reusing the producer grid helper.
NIGHT_START_DAY = {"2022-03-28": "2022-03-25", "2022-03-29": "2022-03-28",
                   "2022-03-30": "2022-03-29", "2022-03-31": "2022-03-30",
                   "2022-04-01": "2022-03-31", "2022-04-06": None}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def stamp(value):
    result = datetime.fromisoformat(value)
    assert result.tzinfo is None and result.second == result.microsecond == 0
    return result


def independent_grid(symbol, day):
    day_start = datetime.fromisoformat(day)
    grid = []
    product = "".join(char for char in symbol.split(".")[0] if char.isalpha()).lower()
    assert product in {"ap", "fg", "ma", "sa", "sm", "au", "cu"}
    prior = NIGHT_START_DAY[day]
    if prior is not None and product not in {"ap", "sm"}:
        length = 330 if product == "au" else 240 if product == "cu" else 120
        start = datetime.fromisoformat(prior) + timedelta(hours=21)
        grid.extend(start + timedelta(minutes=i) for i in range(length))
    for hours, minutes, length in ((9, 0, 75), (10, 30, 60), (13, 30, 90)):
        start = day_start + timedelta(hours=hours, minutes=minutes)
        grid.extend(start + timedelta(minutes=i) for i in range(length))
    return grid


def aggregate(data):
    return dict(zip(FIELDS, (data[0]["open"], max(x["high"] for x in data),
                            min(x["low"] for x in data), data[-1]["close"],
                            sum((x["volume"] for x in data), Decimal(0)),
                            data[0]["open_oi"], data[-1]["close_oi"])))


def main():
    parent = read(ATTEMPT / "parent_receipt.json")
    worker = read(ATTEMPT / "worker_receipt.json")
    quality = read(ATTEMPT / "quality.json")
    progress = read(ATTEMPT / "progress.json")
    started = read(ATTEMPT / "attempt_started.json")
    preflight = read(SOURCE / "preflight.json")
    manifest = read(SOURCE / "batch_manifest.json")
    assert parent["status"] == "worker_terminal" and parent["exit_code"] == 0
    assert parent["hard_kill"] is False and parent["all_inputs_unchanged"] is True
    assert 0 < parent["elapsed_seconds"] < 600
    assert worker["status"] == "all_target_minutes_completed"
    assert worker["provider_attempts"] == 1 and worker["local_TqSim_created"] is True
    assert worker["tq_dl_permission"] is False and worker["tq_dl_check_readonly"] is True
    assert worker["download_interface_switched"] is False
    assert worker["completed_minutes"] == worker["target_minutes"] == 12945
    assert worker["accepted_sessions"] == 39 and worker["required_ap210_accepted"] is True
    diagnostic = worker["diagnostic"]
    assert diagnostic == progress["diagnostic"]
    assert set(diagnostic) == {"phase", "elapsed_seconds", "idle_waits", "update_calls", "ready_serial_count"}
    assert diagnostic["phase"] == "all_target_minutes_completed"
    assert 0 < diagnostic["elapsed_seconds"] < 570
    assert diagnostic["idle_waits"] == 2 and diagnostic["update_calls"] == 4
    assert diagnostic["ready_serial_count"] == 8
    assert progress["completed_minutes"] == progress["target_minutes"] == 12945
    assert parent["provider_attempts_max"] == started["provider_attempts_max"] == 1
    assert parent["automatic_retry"] is started["automatic_retry"] is False
    assert started["soft_seconds"] == preflight["soft_seconds"] == 570
    assert started["hard_seconds"] == preflight["hard_seconds"] == 600
    for key in ("financial_replays", "orders", "cancels", "broker_or_ctp_connections"):
        assert parent[key] == worker[key] == 0
    for key in ("raw_sdk_output_saved", "credential_values_saved", "cache_or_overlay_written", "production_qualified"):
        assert parent[key] is worker[key] is False
    assert worker["model_fits"] == 0
    assert quality["accepted_sessions"] == quality["target_sessions"] == 39
    assert quality["all_sessions_accepted"] is quality["required_ap210_accepted"] is True
    assert quality["raw_rows"] == 12945

    assert sha(SOURCE / "preflight.json") == "c178b128b39f0a85999a2992f1730d9737d51cd5b5a0b170c649cc97caa738e9"
    assert sha(SOURCE / "batch_manifest.json") == "a58a875df23d2dda6c797d94e7f46275f0b832377325ef7cf68423b7601a0219"
    old = LINE / "outputs/stage017_required_ap210_batch"
    assert (SOURCE / "batch_manifest.json").read_bytes() == (old / "batch_manifest.json").read_bytes()
    source_hashes = {}
    for path, expected_sha in preflight["source_fingerprints"].items():
        assert sha(path) == expected_sha, path
        source_hashes[path] = expected_sha
    assert len(preflight["source_fingerprints"]) == 35
    for path, expected_sha in manifest["input_sha256"].items():
        assert source_hashes[path] == expected_sha
    for name, expected_sha in parent["artifact_sha256"].items():
        assert sha(ATTEMPT / name) == expected_sha, name
    actual_files = {p.name for p in ATTEMPT.iterdir() if p.is_file()}
    assert actual_files == set(parent["artifact_sha256"]) | {"parent_receipt.json"}
    assert not any("error" in name for name in actual_files)

    targets = {(x["vt_symbol"], x["execution_trade_date"]): x for x in manifest["targets"]}
    reviews = {(x["vt_symbol"], x["execution_trade_date"]): x for x in quality["sessions"]}
    assert len(targets) == len(reviews) == 39 and targets.keys() == reviews.keys()
    expected = {}
    grids = {}
    for key, target in targets.items():
        grid = independent_grid(*key)
        assert len(grid) == len(set(grid)) == target["expected_minutes"]
        assert grid == [stamp(x) for x in target["expected_timestamps"]]
        grids[key] = grid
        for moment in grid:
            row_key = key[0], moment
            assert row_key not in expected
            expected[row_key] = key
        check = reviews[key]
        assert check["accepted"] is check["completion_evidence_complete"] is True
        assert check["status"] == "accepted" and check["missing_minutes"] == 0
        assert check["expected_minutes"] == check["actual_rows"] == len(grid)
        assert check["daily_mismatch_fields"] == []
    assert len(expected) == 12945
    raw = {}
    for row in rows(ATTEMPT / "raw_completed_minutes.csv"):
        key = row["vt_symbol"], stamp(row["bar_datetime"])
        assert key in expected and key not in raw
        values = {field: Decimal(row[field]) for field in FIELDS}
        assert all(value.is_finite() for value in values.values())
        assert all(values[field] > 0 for field in ("open", "high", "low", "close"))
        assert values["low"] <= min(values["open"], values["close"]) <= max(values["open"], values["close"]) <= values["high"]
        assert all(values[field] >= 0 for field in ("volume", "open_oi", "close_oi"))
        raw[key] = values
    assert raw.keys() == expected.keys() and len(raw) == 12945
    proofs = {}
    minimum_successor_delta = None
    for row in rows(ATTEMPT / "completion_evidence.csv"):
        key = row["vt_symbol"], stamp(row["bar_datetime"])
        successor = stamp(row["successor_time"])
        assert key in raw and key not in proofs
        assert row["completed"] == "True" and row["method"] == "observed_later_serial_kline"
        delta = (successor - key[1]).total_seconds()
        assert delta >= 60
        minimum_successor_delta = delta if minimum_successor_delta is None else min(delta, minimum_successor_delta)
        proofs[key] = successor
    assert proofs.keys() == raw.keys() and len(proofs) == 12945

    samples = []
    for key in SAMPLES:
        symbol, day = key
        grid = grids[key]
        values = aggregate([raw[symbol, moment] for moment in grid])
        daily = [row for row in rows(targets[key]["daily_csv_path"]) if row["trade_date"][:10] == day]
        assert len(daily) == 1
        reference = {field: Decimal(daily[0][field]) for field in FIELDS}
        frozen_reference = {field: Decimal(str(targets[key]["daily_reference"][field])) for field in FIELDS}
        producer_aggregate = {field: Decimal(str(reviews[key]["aggregate"][field])) for field in FIELDS}
        assert values == reference == frozen_reference == producer_aggregate
        samples.append(dict(vt_symbol=symbol, execution_trade_date=day, rows=len(grid),
            exact_original_csv_seven_field_matches=7, aggregate={field: str(value) for field, value in values.items()},
            daily_csv_path=targets[key]["daily_csv_path"], first_time=grid[0].isoformat(),
            last_time=grid[-1].isoformat(), last_successor=proofs[symbol, grid[-1]].isoformat()))
    ap_key = ("AP210.CZCE", "2022-04-06")
    assert len(grids[ap_key]) == 225
    for path in [SOURCE / "preflight.json", SOURCE / "batch_manifest.json", *ATTEMPT.iterdir()]:
        if path.is_file():
            source_hashes[str(path)] = sha(path)
    accepted = [dict(vt_symbol=symbol, execution_trade_date=day, accepted=True,
                     expected_minutes=len(grids[symbol, day])) for symbol, day in sorted(targets)]
    checks = dict(
        reviewed_at=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        status="bounded_completed_batch_review_pass", p0_findings=0, p1_findings=0,
        qualified_precise_sessions=39, qualified_minute_rows=12945, required_AP210_accepted=True,
        all_raw_keys_unique_legal_exact_target_grid=True,
        independent_grid_source="explicit seven-product session segments and six fixed target dates; no producer helper",
        saved_forward_proofs_checked=12945, minimum_successor_delta_seconds=minimum_successor_delta,
        price_aggregation_independent_samples=samples, all_39_daily_aggregates_independently_repeated=False,
        parent_exit_code=0, parent_elapsed_seconds=parent["elapsed_seconds"], diagnostic=diagnostic,
        frozen_inputs_rehashed=35, parent_artifact_hashes_checked=len(parent["artifact_sha256"]),
        all_inputs_unchanged=True, source_fingerprints=source_hashes,
        timestamp_evidence_limit="saved CST bar/successor proof; original nanosecond serial snapshots not retained; UTC-to-CST conversion uses unchanged reviewed Stage012 collector",
        provider_attempts_observed=1, review_network_calls=0, review_financial_replays=0,
    )
    write(OUT / "completed_batch_checks.json", checks)
    report = """# Stage018 精确completed数据独立复核

研究线 futures_trend_triple_screen。仅审本次新增12945分钟/39会话；没有复连、重试、测试重跑、账户回放或旧数据全量审计。

父进程exit=0、117.012390秒，无硬杀且输入不变；worker/progress阶段均all_target_minutes_completed，worker预算114.597067秒，idle_waits=2、update_calls=4、ready_serial_count=8。35项冻结来源的当前SHA全部匹配，父receipt绑定的6项产物SHA全部匹配。017 manifest仍逐字节相同；原012 collector、017与SDK/auth等冻结输入未改。父子记录零订单/撤单/CTP/金融/原数据写入，原始SDK输出及凭证没有保存。

独立用固定日期和七类品种的交易时段重建本批39个网格：日盘225，普通夜盘FG/MA/SA总345、au总555、cu总465；清明后4月6日目标仅日盘。原始12945行全部唯一、正价且OHLC范围合法、成交量/OI非负，精确等于冻结目标网格；12945条保存的后继证明一一对应，后继至少晚60秒。没有接受各serial的最后形成行。保存文件只有CST bar/successor时间，没有另存provider纳秒serial快照；UTC转CST依赖未改、已审的Stage012 collector，不能把保存后继证明扩大为独立第三方行情真值。

独立Decimal聚合5个会话：强制AP210.CZCE/2022-04-06的225分钟，另AP205/3月28日、MA205/4月6日、au2206/4月1日、cu2204/3月28日。每个会话的OHLCV、首openOI、末closeOI全部与原CSV及冻结参考七字段精确相等。AP210为8888/8942/8696/8884、V218838、openOI118247、closeOI129669；其14:59的保存后继为4月7日09:00。本次不重复全部39会话的独立日聚合；其余会话的生产quality通过及输入SHA均已核。

资格结论：qualified_precise_sessions=39、qualified_minute_rows=12945、required_AP210_accepted=true，限receipt所列精确会话用于研究数据资格。可作为后续显式接入018的Stage016输入依据；本review不构建或覆盖任何base/cache，也不授权金融重放或生产。本次tq_dl布尔仍false但公开serial数据已返回，故不能用该布尔单独断言此接口不可用；不推断017超时的具体触发位置。

累计金融attempt仍4、完成1，C0无alpha结论。过拟合：否，本次修正SDK等待语义且未改变目标或策略参数。继续价值：是，取得受旧source859问题影响的AP210完整替代依据；后续仍需Stage016精确替换/追加及独立资格，不能把本次成功当作全路径数据就绪。
"""
    (OUT / "independent_review.md").write_text(report)
    receipt = dict(
        reviewed_at=checks["reviewed_at"], reviewer="first_screen_independent",
        status="bounded_stage018_completed_batch_review_pass", p0_findings=0, p1_findings=0,
        qualified_research_data=True, qualified_precise_sessions=39, qualified_minute_rows=12945,
        required_AP210_accepted=True, AP210_qualified_minutes=225, accepted_sessions=accepted,
        parent_exit_code=0, provider_attempts=1, all_inputs_unchanged=True,
        parent_elapsed_seconds=parent["elapsed_seconds"], worker_diagnostic=diagnostic,
        all_raw_keys_unique_legal_exact_target_grid=True, saved_forward_proofs_checked=12945,
        independent_daily_aggregate_samples=5, AP210_daily_seven_fields_exact=True,
        all_39_daily_aggregates_independently_repeated=False,
        raw_path=str(ATTEMPT / "raw_completed_minutes.csv"),
        evidence_path=str(ATTEMPT / "completion_evidence.csv"),
        quality_path=str(ATTEMPT / "quality.json"),
        parent_receipt_path=str(ATTEMPT / "parent_receipt.json"),
        worker_receipt_path=str(ATTEMPT / "worker_receipt.json"),
        preflight_path=str(SOURCE / "preflight.json"), batch_manifest_path=str(SOURCE / "batch_manifest.json"),
        source_fingerprints=source_hashes,
        review_artifact_sha256={name:sha(OUT / name) for name in ("review_completed_batch.py", "completed_batch_checks.json", "independent_review.md")},
        financial_replays=0, network_calls=0, retries=0, cache_or_base_written=False,
        Stage016_input_reference_qualified=True, Stage016_delta_already_qualified=False,
        C0_attempt3_authorized=False, execution_fallback_authorized=False, production_qualified=False,
        financial_attempts_cumulative_unchanged=4, financial_completed_cumulative_unchanged=1,
        C0_alpha_verdict="not_evaluable", overfitting=False, continued_value=True,
    )
    write(OUT / "review_receipt.json", receipt)
    print(json.dumps({key:receipt[key] for key in ("status", "qualified_precise_sessions", "qualified_minute_rows", "required_AP210_accepted", "parent_exit_code", "independent_daily_aggregate_samples")}, ensure_ascii=False))
    print("review_receipt_sha256=" + sha(OUT / "review_receipt.json"))


if __name__ == "__main__":
    main()
