"""Stage251：关闭0.5R模块的离线A/C消融，A/C共用已验收正确性修复。

允许经过独立复核的权益与分钟撮合补丁；冻结发布物料不改写。
不是生产部署入口，所有输出标记offline_half_r_ablation。
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
import subprocess
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

    # Stage901 的原日历来源与逐月要求照旧；只把首个历史月池前的月份
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


ALLOWED_PATCHES = {
    "examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py",
    "examples/portfolio_backtesting/analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac.py",
    "examples/portfolio_backtesting/analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine.py",
}
BASE_HEAD = "77538e394167c290d5f2923f4d08931b9bbd7c4f"
ALLOWED_TEST_UPDATES = {"tests/test_qmt_entry_context_diagnostics.py"}
CORRECTNESS_HELPERS = {"examples/portfolio_backtesting/qmt_roll_intraday_execution.py"}


def audit_correctness_overlay(root: Path, baseline: Path, active: Any) -> dict[str, Any]:
    from qmt_roll_official_strategy_material_resolver import (
        load_active_material_release, assert_runtime_materials_match_checkout,
        verify_material_file,
    )
    reference = load_active_material_release(baseline / "official_strategy_materials/CURRENT.json", repo_root=baseline)
    assert_runtime_materials_match_checkout(reference)
    if active.manifest != reference.manifest:
        raise ValueError("frozen_material_manifest_changed")
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    branch = subprocess.check_output(["git", "-C", str(root), "branch", "--show-current"], text=True).strip()
    if head != "0e9d34b72f6c68c7c06a68902d4b01f12a9e9254" or branch != "codex/stage251-disable-half-r-stop":
        raise ValueError("stage251_branch_base_mismatch")
    manifest_path = root / "research/lines/futures_trend_rollover_shape_same_volume/outputs/stage251_half_r_ab/accepted_common_patch_manifest.json"
    expected = json.loads(manifest_path.read_text())
    for name, digest in expected["source_files"].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"accepted_common_patch_changed:{name}")
    for row in active.manifest.get("files", []):
        source = str(row.get("source_path", ""))
        if row.get("role") not in {"runtime_code", "strategy_config", "operational_config"} or source.startswith("promotion_source:"):
            continue
        # HEAD already redacted two documentation examples after Stage249 base.
        # This non-executable file is unchanged by Stage251; pin its exact HEAD bytes.
        if source == "skills/futures-live-execution-sop/SKILL.md":
            if hashlib.sha256((root/source).read_bytes()).hexdigest() != "4af05968961a5a7b26b3c134e2d8c74bdd484d82fe714b509e8f2f6e7170cb95":
                raise ValueError("committed_sop_documentation_changed")
        elif source not in ALLOWED_PATCHES:
            verify_material_file(root / source, row)
    changes = subprocess.check_output(["git", "-C", str(root), "diff", "--name-only", "HEAD"], text=True).splitlines()
    unexpected = [name for name in changes if name not in ALLOWED_PATCHES | ALLOWED_TEST_UPDATES
                  and not name.startswith("research/lines/futures_trend_rollover_shape_same_volume/")]
    if unexpected:
        raise ValueError(f"unexpected_runtime_changes:{unexpected}")
    patch = subprocess.check_output(["git", "-C", str(root), "diff", "HEAD", "--", *sorted(ALLOWED_PATCHES)], text=True)
    return {"status": "verified_accepted_stage249_overlay", "base_head": head, "branch": branch,
            "frozen_baseline_root": str(baseline), "published_material_unchanged": True,
            "committed_documentation_only_overlay": {"path": "skills/futures-live-execution-sop/SKILL.md", "sha256": "4af05968961a5a7b26b3c134e2d8c74bdd484d82fe714b509e8f2f6e7170cb95", "scope": "two redacted documentation examples; not executed by replay"},
            "production_qualified": False, "accepted_source_files": expected["source_files"],
            "accepted_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(), "patch": patch}


@contextmanager
def declared_ablation(s901: Any, arm: str):
    """只包装最终合并的正式 overrides；异常退出也恢复原函数。"""
    if arm not in {"A", "C"}:
        raise ValueError(f"invalid_arm:{arm}")
    original = s901.build_official_live_strategy_overrides
    def build():
        settings = dict(original())
        if settings.get("enable_stage847_half_r_stop_retry") is not True:
            raise ValueError("formal_half_r_flag_not_true")
        if arm == "C":
            settings["enable_stage847_half_r_stop_retry"] = False
        return settings
    s901.build_official_live_strategy_overrides = build
    try:
        yield
    finally:
        s901.build_official_live_strategy_overrides = original


@contextmanager
def capture_actual_settings(engine_class: type):
    local = "add_strategy" in engine_class.__dict__
    original = engine_class.add_strategy
    rows = []
    def wrapped(engine, strategy_class, setting):
        result = original(engine, strategy_class, setting)
        actual = {key: getattr(engine.strategy, key) for key in setting if hasattr(engine.strategy, key)}
        non_strategy = {key: value for key, value in setting.items()
                        if key not in actual and key in {"account_capital", "c3_capital"}}
        if any(value != engine.capital for value in non_strategy.values()):
            raise ValueError("engine_capital_metadata_mismatch")
        expected = {key: value for key, value in setting.items() if key not in non_strategy}
        if actual != expected:
            raise ValueError("actual_strategy_settings_mismatch:" + repr({key: {"requested": expected[key], "actual": actual.get(key, "MISSING")} for key in expected if key not in actual or actual[key] != expected[key]}))
        rows.append({"strategy_class": strategy_class.__name__, "setting": dict(setting), "actual": actual,
                     "non_strategy_fields": non_strategy, "engine_capital": engine.capital,
                     "supply_demand_signal_rows": len(engine.strategy.supply_demand_signals)
                         if hasattr(engine.strategy, "supply_demand_signals") else None})
        return result
    engine_class.add_strategy = wrapped
    try:
        yield rows
    finally:
        if local:
            engine_class.add_strategy = original
        else:
            delattr(engine_class, "add_strategy")


@contextmanager
def capture_execution_proxy_usage(engine_class: type) -> Any:
    names = ["calculate_result", "new_bars"]
    originals = {name: (name in engine_class.__dict__, getattr(engine_class, name)) for name in names}
    captured = {"usage": [], "equity": [], "trades": [], "minute_requests": [], "anchor_requests": [], "failures": []}
    failure_causes: list[Exception] = []
    def capture_bar(engine: Any, dt: Any) -> Any:
        try:
            result = originals["new_bars"][1](engine, dt)
            strategy = getattr(engine, "strategy", None)
            if strategy is not None and getattr(strategy, "trading", False):
                captured["equity"].append({"date": pd_date(dt),
                    "estimated_equity": float(strategy.estimated_equity),
                    "settled_balance": float(strategy.settled_balance)})
            return result
        except Exception as error:
            # Frozen vendor catches new_bars errors and returns normally. Preserve
            # them before that catch, then fail the research scope on normal exit.
            captured["failures"].append({"datetime": str(dt), "error": repr(error)})
            failure_causes.append(error)
            raise
    def capture_result(engine: Any, *args: Any, **kwargs: Any) -> Any:
        result = originals["calculate_result"][1](engine, *args, **kwargs)
        captured["usage"][:] = [dict(row) for row in getattr(engine, "trade_usage_rows", [])]
        captured["anchor_requests"][:] = [dict(row) for row in getattr(engine, "execution_anchor_requests", [])]
        strategy = getattr(engine, "strategy", None)
        captured["minute_requests"][:] = [dict(row) for obj in [engine, strategy] if obj is not None
            for row in getattr(obj, "minute_scan_requests", [])]
        captured["trades"][:] = [{"trade_id": trade.vt_tradeid, "vt_symbol": trade.vt_symbol,
            "engine_datetime": str(trade.datetime),
            "trading_date": str(getattr(trade, "trading_date", trade.datetime.date())),
            "execution_datetime": str(getattr(trade, "execution_datetime", trade.datetime)),
            "exit_reason": getattr(strategy, "trade_reason_by_trade_id", {}).get(trade.vt_tradeid)
                           or getattr(trade, "exit_reason", ""),
            "direction": trade.direction.value, "offset": trade.offset.value,
            "price": float(trade.price), "volume": float(trade.volume)} for trade in engine.get_all_trades()]
        return result
    engine_class.new_bars = capture_bar
    engine_class.calculate_result = capture_result
    try:
        yield captured
        if failure_causes:
            raise RuntimeError(f"backtest_bar_failed:{captured['failures'][0]}") from failure_causes[0]
    finally:
        for name, (local, original) in originals.items():
            if local:
                setattr(engine_class, name, original)
            else:
                delattr(engine_class, name)


def pd_date(value: Any) -> str:
    import pandas as pd
    return pd.Timestamp(value).date().isoformat()


def attach_trading_dates(trades: Any, clock: Any) -> Any:
    """报告以交易日归属，保留物理时间；拒绝遗漏/重复成交身份。"""
    if trades.empty and clock.empty:
        return trades.copy()
    if (trades.trade_id.duplicated().any() or clock.trade_id.duplicated().any()
            or set(trades.trade_id) != set(clock.trade_id)):
        raise ValueError("trade_clock_identity_mismatch")
    result = trades.copy()
    dates = clock.set_index("trade_id").trading_date
    result["natural_date"] = result["datetime"].astype(str).str[:10]
    result["trading_date"] = result.trade_id.map(dates)
    result["date"] = result["trading_date"]
    if "exit_reason" in clock:
        reasons = clock.set_index("trade_id").exit_reason.fillna("")
        mapped = result.trade_id.map(reasons)
        previous = result.get("exit_reason", mapped).fillna("")
        result["exit_reason"] = mapped.where(mapped.ne(""), previous)
    return result


def canonical_trade_enums(frame: Any) -> Any:
    """本地翻译包不影响报告字段与开平判定。"""
    result = frame.copy()
    mappings = {
        "direction": {"Long": "多", "Short": "空", "多": "多", "空": "空"},
        "offset": {"Open": "开", "Close": "平", "Close Today": "平今", "Close Yesterday": "平昨",
                   "开": "开", "平": "平", "平今": "平今", "平昨": "平昨"},
    }
    for column, mapping in mappings.items():
        if column not in result:
            raise ValueError(f"trade_enum_column_missing:{column}")
        canonical = result[column].map(mapping)
        if canonical.isna().any():
            raise ValueError(f"unknown_trade_enum:{column}")
        result[column] = canonical
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--arm", required=True, choices=["A", "C"])
    parser.add_argument("--baseline-root", required=True, type=Path)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--diagnostic-incomplete-minutes", action="store_true",
                        help="只用于收集新路径数据缺口，结果不得作为已验收绩效")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    if not (root / ".vntrader/database.db").is_file():
        raise SystemExit("missing .vntrader/database.db")
    os.chdir(root)
    project = root / "examples/portfolio_backtesting"
    sys.path[:0] = [str(root), str(BUNDLE / "vendor"), str(project)]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    shared_signals = root / "research/lines/futures_trend_rollover_shape_same_volume/outputs/stage251_half_r_ab/shared_signal_inputs"
    if shared_signals.exists() and any(shared_signals.iterdir()):
        raise SystemExit("shared_signal_input_must_remain_empty_for_accepted_historical_baseline")
    os.environ["OFFICIAL_LIVE_SIGNAL_INPUT_DIR"] = str(shared_signals)
    # Stage318 legacy supply input derives from alignment OUTPUT_DIR, while
    # newer readers use SIGNAL_INPUT_DIR. Keep both identical for both arms.
    # This research adapter writes all artifacts explicitly to args.output.
    os.environ["OFFICIAL_LIVE_OUTPUT_DIR"] = str(shared_signals)
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
    overlay = audit_correctness_overlay(root, args.baseline_root.resolve(), OFFICIAL_LIVE_MATERIAL_RELEASE)
    (output / "correctness.patch").write_text(overlay.pop("patch"))
    (output / "code_overlay.json").write_text(json.dumps(overlay, ensure_ascii=False, indent=2))
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
    external_signal_path = Path(s901.s513._c3_overrides(start.to_pydatetime())["supply_demand_signal_path"])
    if external_signal_path.parent != shared_signals or external_signal_path.exists():
        raise SystemExit("historical_supply_demand_input_preflight_mismatch")
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
        "historical_ai_boundary": "2019-12-31 static18 through 2022-01-28; historical monthly pools from next trade date; not a strict out-of-sample claim",
        "order_api_count": 0,
        "shared_missing_supply_demand_input": str(external_signal_path),
        "check": "passed",
    }
    (output / "data_check.json").write_text(json.dumps(check, ensure_ascii=False, indent=2) + "\n")
    if args.check_only:
        print(json.dumps(check, ensure_ascii=False))
        return

    started_at = datetime.now().astimezone().isoformat()
    adapter_hash_before = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
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
    correctness_code_hashes = {name: hashlib.sha256((root/name).read_bytes()).hexdigest()
                              for name in ALLOWED_PATCHES | CORRECTNESS_HELPERS}
    s901.s847.QmtRollPortfolioStrategyStage847C9StopRetry.stage827_require_complete_minutes = not args.diagnostic_incomplete_minutes
    try:
        with declared_ablation(s901, args.arm), capture_actual_settings(s901.s847.Stage847StopRetryEngine) as actual_settings, capture_execution_proxy_usage(s901.s847.Stage847StopRetryEngine) as execution_proxy_rows:
            combined, frames, spec = s901._run_live_c9(metadata, start, end)
        if len(actual_settings) != 1 or actual_settings[0]["actual"]["enable_stage847_half_r_stop_retry"] is not (args.arm == "A"):
            raise ValueError("actual_ablation_flag_mismatch")
        if actual_settings[0]["supply_demand_signal_rows"] != 0:
            raise ValueError("unexpected_historical_supply_demand_signals")
        supply_path = Path(actual_settings[0]["actual"]["supply_demand_signal_path"])
        if supply_path.parent != shared_signals or supply_path.exists():
            raise ValueError("shared_supply_demand_input_state_changed")
        (output / "actual_strategy_settings.json").write_text(json.dumps(s901._json_safe(actual_settings), ensure_ascii=False, indent=2))
    except Exception as error:
        (output / 'run_failure.json').write_text(json.dumps({
            'status': 'failed_closed_no_performance_result', 'error': repr(error),
            'started_at': started_at, 'failed_at': datetime.now().astimezone().isoformat(),
            'diagnostic_incomplete_minutes': args.diagnostic_incomplete_minutes,
            'correctness_code_sha256': correctness_code_hashes,
            'input_manifest_sha256': hashlib.sha256((output / 'input_manifest.json').read_bytes()).hexdigest(),
            'order_api_count': 0,
        }, ensure_ascii=False, indent=2))
        raise
    if any(hashlib.sha256((root/name).read_bytes()).hexdigest() != digest
           for name, digest in correctness_code_hashes.items()):
        raise SystemExit('correctness code changed during replay')
    if input_manifest() != inputs_before:
        raise SystemExit('research data/model inputs changed during replay')
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != adapter_hash_before:
        raise SystemExit('research adapter changed during replay')
    if hashlib.sha256(s901.s861.FULL_MINUTE_BARS_PATH.read_bytes()).hexdigest() != minute_input_sha256:
        raise SystemExit('minute input changed during replay')
    parameters = {'spec': asdict(spec), 'contract_sizes': metadata['sizes'],
                  'rates': metadata['rates'], 'slippages': metadata['slippages'], 'priceticks': metadata['priceticks']}
    baseline_parameters = json.loads((root / 'research/lines/futures_trend_rollover_shape_same_volume/outputs/stage251_half_r_ab/accepted_A_parameters.json').read_text())
    if baseline_parameters['spec']['overrides']['enable_stage847_half_r_stop_retry'] is not True:
        raise ValueError('accepted_A_flag_not_true')
    if args.arm == 'C':
        baseline_parameters['spec']['overrides']['enable_stage847_half_r_stop_retry'] = False
    def normalize_parameters(value, checkout):
        if isinstance(value, dict):
            return {key: normalize_parameters(item, checkout) for key, item in value.items()}
        if isinstance(value, list):
            return [normalize_parameters(item, checkout) for item in value]
        if isinstance(value, str):
            return value.replace(str(checkout), '{repo}').replace('/Users/mac/.codex/worktrees/formal-correctness-replay/fian', '{repo}')
        return value
    effective_original_fields = {key: value for key, value in parameters.items() if key in baseline_parameters}
    if normalize_parameters(s901._json_safe(effective_original_fields), root) != normalize_parameters(baseline_parameters, args.baseline_root.resolve()):
        (output / 'effective_parameters_mismatch.json').write_text(json.dumps(s901._json_safe(parameters), ensure_ascii=False, indent=2))
        raise SystemExit('official alpha/risk/cost parameters drifted from baseline')
    (output / 'effective_parameters.json').write_text(json.dumps(s901._json_safe(parameters), ensure_ascii=False, indent=2))
    (output / 'run_provenance.json').write_text(json.dumps({
        'argv': sys.argv, 'python_executable': sys.executable,
        'started_at': started_at, 'completed_at': datetime.now().astimezone().isoformat(),
        'minute_input_sha256': minute_input_sha256, 'minute_input_unchanged_during_run': True,
        'input_file_count': len(inputs_before), 'all_data_and_model_inputs_unchanged_during_run': True,
        'input_manifest_sha256': hashlib.sha256((output / 'input_manifest.json').read_bytes()).hexdigest(),
        'research_adapter_sha256': adapter_hash_before,
        'source_scope': 'Offline single-factor half-R ablation on accepted Stage249 correctness overlay.',
        'arm': args.arm, 'declared_ablation_delta': ({'spec.overrides.enable_stage847_half_r_stop_retry': {'A': True, 'C': False}} if args.arm == 'C' else {}),
        'code_overlay': overlay, 'production_qualified': False,
        'correctness_code_sha256': correctness_code_hashes,
        'official_parameters_match_baseline': args.arm == 'A',
        'all_other_parameters_match_baseline': True,
        'shared_signal_input_dir': str(shared_signals),
        'supply_demand_history': {'enabled': actual_settings[0]['actual']['enable_supply_demand_headwind_filter'],
                                 'file_exists': False, 'loaded_rows': 0,
                                 'scope': 'accepted historical baseline has no external supply-demand signal file; no_signal weight 1 in both arms'},
        'exported_enum_locale': 'canonical_Chinese_independent_of_installed_translation',
        'diagnostic_incomplete_minutes': args.diagnostic_incomplete_minutes,
        'vendor_swallowed_bar_exception_guard': True,
        'captured_bar_failure_count': len(execution_proxy_rows['failures']),
    }, ensure_ascii=False, indent=2))
    metrics = s901.s650._metrics(combined, spec.capital, 1.0)
    validation_status = "diagnostic_incomplete_minutes" if args.diagnostic_incomplete_minutes else "strict_engine_completed_pending_independent_review"
    metrics.update({"start": args.start, "end": args.end, "order_api_count": 0,
                    "result_scope": "offline_half_r_ablation", "production_qualified": False,
                    "validation_status": validation_status,
                    "source_official_variant": metrics.get("variant"),
                    "variant": f"stage251_{args.arm}_half_r_ablation",
                    "label": f"Stage251 {args.arm}：正式基准" if args.arm == "A" else "Stage251 C：关闭0.5R模块",
                    "source_official_note": metrics.get("note"),
                    "note": "共用Stage249正确性修复；C仅关闭0.5R止损及依赖重试。未发布，非生产资格。"})
    clock = canonical_trade_enums(pd.DataFrame(execution_proxy_rows["trades"]))
    frames["trades"] = canonical_trade_enums(frames["trades"])
    usage = pd.DataFrame(execution_proxy_rows["usage"])
    sources = usage.set_index("trade_id")["price_source"]
    source_reason = clock.trade_id.map(sources).fillna("")
    synthetic_close = clock.offset.ne("开") & source_reason.str.startswith("stage")
    clock.loc[synthetic_close, "exit_reason"] = source_reason[synthetic_close]
    frames["trades"] = attach_trading_dates(frames["trades"], clock)
    for name, frame in frames.items():
        if frame.empty and len(frame.columns) == 0:
            frames[name] = pd.DataFrame(columns=["date", "vt_symbol", "event", "order_id", "reason"])
    for frame in [combined, *frames.values()]:
        frame["result_scope"] = "offline_half_r_ablation"
        frame["validation_status"] = validation_status
        frame["source_official_profile"] = OFFICIAL_PROFILE
        frame["profile"] = f"stage251_{args.arm}_half_r_ablation"
        if "variant" in frame:
            frame["source_official_variant"] = frame["variant"]
            frame["variant"] = f"stage251_{args.arm}_half_r_ablation"
        if "label" in frame:
            frame["label"] = f"Stage251 {args.arm}：正式基准" if args.arm == "A" else "Stage251 C：关闭0.5R模块"
        if "combo_variant" in frame:
            frame["source_official_combo_variant"] = frame["combo_variant"]
            frame["combo_variant"] = f"stage251_{args.arm}_half_r_ablation"
        if "note" in frame:
            frame["source_official_note"] = frame["note"]
            frame["note"] = metrics["note"]
    combined.to_csv(output / "daily.csv", index=False, encoding="utf-8-sig")
    for name, frame in frames.items():
        if frame.empty and len(frame.columns) == 0:
            frame = pd.DataFrame(columns=["date", "vt_symbol", "event", "order_id", "result_scope"])
        frame.to_csv(output / f"{name}.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(execution_proxy_rows["equity"]).to_csv(output / "internal_equity_daily.csv", index=False)
    clock.to_csv(output / "execution_clock.csv", index=False)
    pd.DataFrame(execution_proxy_rows["minute_requests"], columns=["vt_symbol", "trading_date", "execution_datetime", "session_start", "session_end_exclusive", "requested_start", "expected_bar_count", "actual_bar_count", "missing_bar_count", "actual_first_time", "actual_last_time", "coverage_status", "execution_policy"]).to_csv(output / "minute_scan_requests.csv", index=False) if not execution_proxy_rows["minute_requests"] else pd.DataFrame(execution_proxy_rows["minute_requests"]).to_csv(output / "minute_scan_requests.csv", index=False)
    pd.DataFrame(execution_proxy_rows["anchor_requests"]).to_csv(output / "execution_anchor_requests.csv", index=False)
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
