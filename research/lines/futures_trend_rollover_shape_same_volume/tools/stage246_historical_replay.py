"""Stage246：冻结正式策略的离线历史回放适配器。

只修正研究预检的 pre-AI 生效日历：2019-12-31 的静态18池覆盖首个
2022-01-28 OOS 月池之前的历史。策略、CURRENT、AI 物料和交易成本均不改动。
来源：交接包 tools/research_backtest.py；Stage004 原始 AI 边界法证；Stage065 正式晋升。
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import contextmanager
import csv
from datetime import date
from datetime import datetime
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any, Mapping


OFFICIAL_STRATEGY = "ai_top10_plus_fu_official_live_v1"
OFFICIAL_RULESET = "stage037_stage034_long_short_mirror_hard_block_v1"
OFFICIAL_RELEASE = "m0008_20261008T204054+0800_2a7420a9f955"
OFFICIAL_PROFILE = "official_live_stage847_c9_15w_stage819_05r_stop_retry_once"
PRE_AI_EVAL_DATE = "2019-12-31"
FIRST_OOS_EVAL_DATE = "2022-01-28"
BUNDLE = Path("/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014")


def audit_historical_ai_pool(path: Path, required_eval_dates: list[str]) -> dict[str, Any]:
    """校验全部正式快照，再按历史生效政策检查本窗口必需快照。"""
    from qmt_roll_official_ai_pool_policy import official_ai_pool_snapshot_blockers

    if not required_eval_dates:
        raise ValueError("trading_calendar_unavailable")
    if not path.is_file():
        raise ValueError(f"eligibility_file_missing:{path}")
    payload = path.read_bytes()
    reader = csv.DictReader(payload.decode("utf-8-sig").splitlines())
    required_columns = {
        "strategy", "score_type", "eval_date", "product_vt_symbol", "score", "score_rank", "top_n"
    }
    if not required_columns.issubset(reader.fieldnames or []):
        raise ValueError(f"eligibility_columns_missing:{sorted(required_columns - set(reader.fieldnames or []))}")
    snapshots: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in reader:
        if row["strategy"] != OFFICIAL_STRATEGY:
            continue
        try:
            eval_date = date.fromisoformat(row["eval_date"]).isoformat()
            score = float(row["score"])
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_official_row") from exc
        if not math.isfinite(score):
            raise ValueError(f"invalid_score:{eval_date}")
        snapshots[eval_date].append(row)
    if not snapshots:
        raise ValueError("official_strategy_rows_missing")
    eval_dates = sorted(snapshots)
    if eval_dates[0] != PRE_AI_EVAL_DATE:
        raise ValueError("pre_ai_boundary_missing")
    if len(eval_dates) < 2 or eval_dates[1] != FIRST_OOS_EVAL_DATE:
        raise ValueError("first_oos_boundary_mismatch")

    for eval_date in eval_dates:
        rows = snapshots[eval_date]
        blockers = official_ai_pool_snapshot_blockers(
            products=[row["product_vt_symbol"] for row in rows],
            ranks=[row["score_rank"] for row in rows],
            top_ns=[row["top_n"] for row in rows],
            eval_date=eval_date,
            score_types=[row["score_type"] for row in rows],
        )
        if blockers:
            raise ValueError(f"invalid_snapshot:{eval_date}:{','.join(blockers)}")

    # Stage901 的原日历来源与逐月要求照旧；只把首个 OOS 前的月份
    # 明确映射到唯一静态边界，而不合成或提前训练历史月池。
    pre_ai_required: list[str] = []
    monthly_required: list[str] = []
    for value in required_eval_dates:
        required_date = date.fromisoformat(value).isoformat()
        if required_date < FIRST_OOS_EVAL_DATE:
            pre_ai_required.append(required_date)
        else:
            monthly_required.append(required_date)
            if required_date not in snapshots:
                raise ValueError(f"missing_required_eval_date:{required_date}")
    return {
        "status": "valid",
        "strategy": OFFICIAL_STRATEGY,
        "eligibility_sha256": hashlib.sha256(payload).hexdigest(),
        "pre_ai_eval_date": PRE_AI_EVAL_DATE,
        "first_oos_eval_date": FIRST_OOS_EVAL_DATE,
        "validated_snapshot_count": len(eval_dates),
        "validated_eval_dates": eval_dates,
        "pre_ai_required_dates": pre_ai_required,
        "monthly_required_dates": monthly_required,
        "required_calendar_rule": "Stage901 month-start prior completed trade date",
    }


def opening_minute_coverage(trades: Any, minutes: Mapping[str, Any] | Any) -> Any:
    """回放后按实际开仓核对 Stage861 可见分钟；不介入策略读取或决策。"""
    import pandas as pd

    columns = [
        "trade_id", "datetime", "vt_symbol", "entry_date", "minute_row_count",
        "first_minute", "last_minute", "coverage_status",
    ]
    if trades.empty:
        return pd.DataFrame(columns=columns)
    if isinstance(minutes, pd.DataFrame):
        minute_by_symbol = {str(symbol): group for symbol, group in minutes.groupby("vt_symbol", sort=False)}
    else:
        minute_by_symbol = minutes
    rows: list[dict[str, Any]] = []
    for trade in trades.to_dict("records"):
        if str(trade.get("offset", "")).strip().casefold() not in {"开", "open"}:
            continue
        vt_symbol = str(trade.get("vt_symbol", ""))
        entry_date = pd.Timestamp(trade["datetime"]).date().isoformat()
        bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
        day = bars[pd.to_datetime(bars["bar_date"], errors="coerce").dt.date.astype(str).eq(entry_date)] if not bars.empty else bars
        times = pd.to_datetime(day["bar_datetime"], errors="coerce").dropna() if not day.empty else pd.Series(dtype="datetime64[ns]")
        rows.append({
            "trade_id": str(trade.get("trade_id", "")),
            "datetime": str(trade["datetime"]),
            "vt_symbol": vt_symbol,
            "entry_date": entry_date,
            "minute_row_count": int(len(times)),
            "first_minute": str(times.min()) if len(times) else "",
            "last_minute": str(times.max()) if len(times) else "",
            "coverage_status": "present_unverified" if len(times) else "missing",
        })
    return pd.DataFrame(rows, columns=columns)


@contextmanager
def capture_execution_proxy_usage(engine_class: type) -> Any:
    """只在本次研究回放中截取完整引擎成交代理记录，退出即恢复类。"""
    local_original = engine_class.__dict__.get("calculate_result")
    inherited = "calculate_result" not in engine_class.__dict__
    calculate_result = engine_class.calculate_result
    captured: list[dict[str, Any]] = []

    def capture_after_calculation(engine: Any, *args: Any, **kwargs: Any) -> Any:
        result = calculate_result(engine, *args, **kwargs)
        # Stage847._run_profile 在 run_backtesting 后、读取 frames 前仅调用一次。
        # 逐行复制，避免持有引擎或随后被修改的列表引用。
        captured[:] = [dict(row) for row in getattr(engine, "trade_usage_rows", [])]
        return result

    engine_class.calculate_result = capture_after_calculation
    try:
        yield captured
    finally:
        if inherited:
            delattr(engine_class, "calculate_result")
        else:
            engine_class.calculate_result = local_original


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    if not (root / ".vntrader/database.db").is_file():
        raise SystemExit("missing .vntrader/database.db")
    os.chdir(root)
    project = root / "examples/portfolio_backtesting"
    sys.path[:0] = [str(root), str(BUNDLE / "vendor"), str(project)]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    os.environ["OFFICIAL_LIVE_OUTPUT_DIR"] = str(output)
    os.environ["OFFICIAL_LIVE_SIGNAL_INPUT_DIR"] = str(output)
    os.environ["OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED"] = "0"
    os.environ["OFFICIAL_LIVE_PHASE_D_SESSION_DAEMON_ENABLED"] = "0"
    if hasattr(time, "tzset"):
        os.environ["TZ"] = "Asia/Shanghai"
        time.tzset()
    if time.localtime(0).tm_hour != 8:
        raise SystemExit("process timezone must be Asia/Shanghai")

    import pandas as pd
    import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
    import vnpy
    import vnpy_portfoliostrategy
    import vnpy_sqlite
    from qmt_backtest_runtime_guard import assert_stage196_database_sentinels
    from qmt_roll_official_strategy_material_resolver import assert_runtime_materials_match_checkout
    from qmt_roll_official_live_lightweight_context import OFFICIAL_LIVE_MATERIAL_RELEASE
    from qmt_roll_official_live_config import OFFICIAL_LIVE_RULESET_VERSION

    assert_stage196_database_sentinels()
    assert_runtime_materials_match_checkout(OFFICIAL_LIVE_MATERIAL_RELEASE)
    if (
        OFFICIAL_LIVE_MATERIAL_RELEASE.release_id != OFFICIAL_RELEASE
        or OFFICIAL_LIVE_MATERIAL_RELEASE.strategy_version != OFFICIAL_STRATEGY
        or OFFICIAL_LIVE_RULESET_VERSION != OFFICIAL_RULESET
        or s901.OFFICIAL_LIVE_VERSION != OFFICIAL_PROFILE
    ):
        raise SystemExit("official identity mismatch")
    required = [
        project / "backtest_outputs/tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv",
        project / "backtest_outputs/tqsdk_all_futures_contract_metadata.csv",
        s901.s861.FULL_MINUTE_BARS_PATH,
        project / "downloaded_futures/tqsdk_daily_2010_2026_04",
        project / "downloaded_futures/tqsdk_stage448_minute_session_rebuild_batch",
        project / "downloaded_futures/tqsdk_stage452_true_path_fallback_1455",
        project / "downloaded_futures/tqsdk_stage506_next_real_forward_risk_signal_frontier",
    ]
    if missing := [str(path) for path in required if not path.exists()]:
        raise SystemExit(f"missing data inputs: {missing}")
    with sqlite3.connect(f"file:{root / '.vntrader/database.db'}?mode=ro", uri=True) as database:
        if database.execute("pragma integrity_check").fetchone()[0] != "ok":
            raise SystemExit("database integrity_check failed")
        data_stats = database.execute(
            "select interval,count(*),min(datetime),max(datetime) from dbbardata group by interval"
        ).fetchall()
    start, end = pd.Timestamp(args.start).normalize(), pd.Timestamp(args.end).normalize()
    if start > end:
        raise SystemExit("start must be <= end")
    ai_audit = audit_historical_ai_pool(
        s901.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
        s901._required_ai_eval_dates(start, end),
    )
    (output / "ai_pool_audit.json").write_text(json.dumps(ai_audit, ensure_ascii=False, indent=2) + "\n")
    check = {
        "repo_root": str(root),
        "database": str(root / ".vntrader/database.db"),
        "data_stats": data_stats,
        "profile": s901.OFFICIAL_LIVE_VERSION,
        "material": OFFICIAL_LIVE_MATERIAL_RELEASE.release_id,
        "ruleset": OFFICIAL_LIVE_RULESET_VERSION,
        "ai_strategy": OFFICIAL_STRATEGY,
        "runtime_sources": {
            "vnpy": vnpy.__file__,
            "vnpy_portfoliostrategy": vnpy_portfoliostrategy.__file__,
            "vnpy_sqlite": vnpy_sqlite.__file__,
        },
        "process_timezone": "Asia/Shanghai",
        "historical_ai_boundary": "2019-12-31 static18 through 2022-01-28; OOS from next trade date",
        "order_api_count": 0,
        "check": "passed",
    }
    (output / "data_check.json").write_text(json.dumps(check, ensure_ascii=False, indent=2) + "\n")
    if args.check_only:
        print(json.dumps(check, ensure_ascii=False))
        return

    started_at = datetime.now().astimezone().isoformat()
    def input_manifest():
        paths = {root / '.vntrader/database.db', s901.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH}
        wal = root / '.vntrader/database.db-wal'
        if wal.exists():
            paths.add(wal)
        for folder in (project / 'backtest_outputs', project / 'downloaded_futures', root / 'official_strategy_materials'):
            paths.update(path for path in folder.rglob('*') if path.is_file() and path.suffix.lower() in {'.csv', '.json', '.joblib'})
        result = {}
        for path in sorted(paths):
            digest = hashlib.sha256()
            with path.open('rb') as source:
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    digest.update(block)
            result[str(path.relative_to(root))] = digest.hexdigest()
        return result
    inputs_before = input_manifest()
    (output / 'input_manifest.json').write_text(json.dumps(inputs_before, ensure_ascii=False, indent=2))
    minute_input_sha256 = hashlib.sha256(s901.s861.FULL_MINUTE_BARS_PATH.read_bytes()).hexdigest()
    metadata = s901.s513._metadata()
    with capture_execution_proxy_usage(s901.s847.Stage847StopRetryEngine) as execution_proxy_rows:
        combined, frames, spec = s901._run_live_c9(metadata, start, end)
    if input_manifest() != inputs_before:
        raise SystemExit('research data/model inputs changed during replay')
    if hashlib.sha256(s901.s861.FULL_MINUTE_BARS_PATH.read_bytes()).hexdigest() != minute_input_sha256:
        raise SystemExit('minute input changed during replay')
    parameters = {'spec': asdict(spec), 'contract_sizes': metadata['sizes'],
                  'rates': metadata['rates'], 'slippages': metadata['slippages']}
    (output / 'effective_parameters.json').write_text(json.dumps(s901._json_safe(parameters), ensure_ascii=False, indent=2))
    (output / 'run_provenance.json').write_text(json.dumps({
        'started_at': started_at, 'completed_at': datetime.now().astimezone().isoformat(),
        'minute_input_sha256': minute_input_sha256, 'minute_input_unchanged_during_run': True,
        'input_file_count': len(inputs_before), 'all_data_and_model_inputs_unchanged_during_run': True,
        'input_manifest_sha256': hashlib.sha256((output / 'input_manifest.json').read_bytes()).hexdigest(),
        'research_adapter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'source_scope': 'Frozen official engine; data-only supplementation and historical AI preflight adaptation.',
    }, ensure_ascii=False, indent=2))
    metrics = s901.s650._metrics(combined, spec.capital, 1.0)
    metrics.update({"start": args.start, "end": args.end, "order_api_count": 0, "result_scope": "offline_research_replay"})
    combined.to_csv(output / "daily.csv", index=False, encoding="utf-8-sig")
    for name, frame in frames.items():
        frame.to_csv(output / f"{name}.csv", index=False, encoding="utf-8-sig")
    usage = pd.DataFrame(execution_proxy_rows)
    usage.to_csv(output / "execution_proxy_usage.csv", index=False, encoding="utf-8-sig")
    trade_ids = set(frames["trades"]["trade_id"].astype(str))
    usage_ids = set(usage.get("trade_id", pd.Series(dtype=str)).astype(str))
    (output / "execution_proxy_usage_summary.json").write_text(json.dumps({
        "usage_rows": int(len(usage)), "trade_rows": int(len(frames["trades"])),
        "trade_ids_match": trade_ids == usage_ids and len(usage) == len(frames['trades']) and len(usage_ids) == len(usage),
        "missing_trade_ids": sorted(trade_ids - usage_ids),
        "unmatched_usage_ids": sorted(usage_ids - trade_ids),
        "price_source_counts": usage.get("price_source", pd.Series(dtype=str)).value_counts().to_dict(),
        "capture_method": "temporary Stage847StopRetryEngine.calculate_result wrapper after original result; restored in finally",
    }, ensure_ascii=False, indent=2) + "\n")
    coverage = opening_minute_coverage(frames["trades"], s901._FULL_MINUTE_BY_SYMBOL_CACHE or {})
    coverage.to_csv(output / "opening_minute_coverage.csv", index=False, encoding="utf-8-sig")
    coverage_summary = {
        "opening_trades": int(len(coverage)),
        "missing_entry_day_minutes": int(coverage["coverage_status"].eq("missing").sum()),
        "present_unverified": int(coverage["coverage_status"].eq("present_unverified").sum()),
        "limitation": "Source rows on entry natural date only; neither session completeness nor exact intraday branch consumption is proven.",
        "minute_source": str(s901.s861.FULL_MINUTE_BARS_PATH),
    }
    (output / "opening_minute_coverage_summary.json").write_text(
        json.dumps(coverage_summary, ensure_ascii=False, indent=2) + "\n"
    )
    result = s901._json_safe(metrics)
    (output / "metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
