"""Run the frozen Stage001 full-market PIT coverage audit exactly once."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path
import sqlite3
import sys
from typing import Any, Final

import pandas as pd


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import full_market_coverage as core  # noqa: E402


LINE_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
PRODUCTION_RELEASE = Path(
    "/Users/bytedance/Desktop/person/vnpy_production_live/official_strategy_materials/"
    "ai_top10_plus_fu_official_live_v1/releases/"
    "m0005_20260901T165450+0800_1961d98ccb2b"
)
OUTPUT_DIR = LINE_DIR / "artifacts/stage001_full_market_coverage"
INPUT_PATHS: Final = {
    "formal_ranking": WORKSPACE_ROOT
    / "research/lines/futures_trend_ai_xgboost_ensemble/artifacts/"
    "stage009_formal_full_ranking_recovery/formal_full_ranking.csv",
    "mapping": WORKSPACE_ROOT
    / "examples/portfolio_backtesting/backtest_outputs/"
    "tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv",
    "metadata": WORKSPACE_ROOT
    / "examples/portfolio_backtesting/backtest_outputs/tqsdk_all_futures_contract_metadata.csv",
    "database": WORKSPACE_ROOT / ".vntrader/database.db",
    "spec": LINE_DIR
    / "stages/20260903_2033_stage000_full_market_one_slot_coverage_preregistration.md",
    "core": TOOL_DIR / "full_market_coverage.py",
}
EXPECTED_SHA256: Final = {
    "formal_ranking": "b2cb417b6c57a7679ae43a1e564c1e79683ca9644b3434cb6a3bfc9e039fcfc0",
    "mapping": "1fa32afab0bc9a490711aa66a716fa78fd52ebbb2c1680d77ce20eadcad617c2",
    "metadata": "24a3573e847e024411b13a3a3b775791ded57563b0a68b717d1065078201635a",
    "database": "7e2633909f73d77c3b0b044199418d7c1ed2989afde480596aefbb18a83b724a",
    "spec": "812847cef66f0923c2d1a4f6bd80b8c28a99a95d38fc9fbf79bc04c0df21e930",
    "core": "f5751bea61b736d89848b228eee03959465a0be82ee007614eb4e80ecf072194",
}
DEFAULT_CONFIG = core.CoverageConfig(
    eval_start=pd.Timestamp("2022-01-28"),
    eval_end=pd.Timestamp("2026-06-30"),
    expected_months=54,
    expected_ranks_per_month=18,
    expected_static_products=18,
    replacement_rank=10,
    minimum_mapping_days=252,
    minimum_valid_close_days=241,
    activity_window_days=60,
    minimum_activity_ratio=0.90,
    minimum_curve_contracts=2,
    minimum_total_eligible=30,
    minimum_action_months=36,
    minimum_challengers=10,
    capital=150_000.0,
    conservative_margin_ratio=0.15,
)

FORMAL_COLUMNS: Final = ["eval_date", "product_vt_symbol", "score_rank", "score_type"]
MAPPING_COLUMNS: Final = ["date", "continuous_symbol_vt", "main_contract_vt", "exchange"]
METADATA_COLUMNS: Final = ["vt_symbol", "symbol_kind", "price_tick", "volume_multiple"]
DATABASE_COLUMNS: Final = [
    "symbol",
    "exchange",
    "datetime",
    "interval",
    "close_price",
    "volume",
    "open_interest",
]


class Stage001Error(RuntimeError):
    """Raised when the frozen Stage001 audit must stop without publishing."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_inputs(
    input_paths: Mapping[str, Path], expected_sha256: Mapping[str, str]
) -> dict[str, dict[str, Any]]:
    if set(input_paths) != set(expected_sha256):
        raise Stage001Error("input_identity_keys_mismatch")
    identities: dict[str, dict[str, Any]] = {}
    for name in sorted(input_paths):
        path = Path(input_paths[name])
        if not path.is_file():
            raise Stage001Error(f"input_missing:{name}")
        digest = sha256_file(path)
        if digest != str(expected_sha256[name]):
            raise Stage001Error(f"input_sha256_drift:{name}")
        identities[name] = {
            "path": str(path.resolve()),
            "size": int(path.stat().st_size),
            "sha256": digest,
        }
    return identities


def _query_start_date(
    mapping: pd.DataFrame, ranking: pd.DataFrame, config: core.CoverageConfig
) -> pd.Timestamp:
    frame = mapping.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
    frame["main_contract_vt"] = frame["main_contract_vt"].fillna("").astype(str).str.strip()
    frame = frame[
        frame["date"].le(pd.Timestamp(config.eval_end)) & frame["main_contract_vt"].ne("")
    ].copy()
    eval_dates = pd.DatetimeIndex(
        sorted(
            pd.to_datetime(ranking["eval_date"], errors="raise")
            .dt.normalize()
            .loc[
                lambda values: values.between(config.eval_start, config.eval_end)
            ]
            .unique()
        )
    )
    starts: list[pd.Timestamp] = []
    for _, product in frame.groupby("continuous_symbol_vt", sort=False):
        product = product.sort_values("date", kind="mergesort")
        for eval_date in eval_dates:
            history = product[product["date"].le(eval_date)]
            if len(history) >= config.minimum_mapping_days:
                starts.append(pd.Timestamp(history.tail(config.minimum_mapping_days)["date"].min()))
                break
    if not starts:
        raise Stage001Error("database_query_start_unavailable")
    return min(starts)


def _read_database(
    database: Path,
    *,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    allowed_exchanges: tuple[str, ...],
) -> pd.DataFrame:
    exchange_placeholders = ",".join("?" for _ in allowed_exchanges)
    query = f"""
        SELECT {", ".join(DATABASE_COLUMNS)}
        FROM dbbardata
        WHERE interval = 'd'
          AND date(datetime) >= ?
          AND date(datetime) <= ?
          AND exchange IN ({exchange_placeholders})
        ORDER BY datetime, exchange, symbol
    """
    uri = f"file:{Path(database).resolve()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.execute("PRAGMA query_only = ON")
        return pd.read_sql_query(
            query,
            connection,
            params=[
                pd.Timestamp(start_date).date().isoformat(),
                pd.Timestamp(end_date).date().isoformat(),
                *allowed_exchanges,
            ],
        )


def _assert_repeat_exact(first: core.CoverageResult, second: core.CoverageResult) -> None:
    pd.testing.assert_frame_equal(first.coverage, second.coverage, check_exact=True)
    pd.testing.assert_frame_equal(first.monthly, second.monthly, check_exact=True)
    pd.testing.assert_frame_equal(first.rejected, second.rejected, check_exact=True)
    if first.diagnostics != second.diagnostics:
        raise Stage001Error("repeat_diagnostics_mismatch")


def _write_csv(frame: pd.DataFrame, path: Path, *, gzip: bool = False) -> None:
    options: dict[str, Any] = {
        "index": False,
        "encoding": "utf-8-sig",
        "date_format": "%Y-%m-%d",
        "float_format": "%.17g",
    }
    if gzip:
        options["compression"] = {"method": "gzip", "compresslevel": 6, "mtime": 0}
    frame.to_csv(path, **options)


def _publish(
    output_dir: Path,
    *,
    result: core.CoverageResult,
    summary: dict[str, Any],
) -> None:
    output_dir = Path(output_dir)
    temp_dir = output_dir.with_name(f"{output_dir.name}.tmp")
    if output_dir.exists():
        raise Stage001Error("stage001_output_already_exists")
    if temp_dir.exists():
        raise Stage001Error("stage001_temp_output_already_exists")
    temp_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
    os.chmod(temp_dir, 0o700)

    _write_csv(
        result.coverage,
        temp_dir / "coverage_by_eval_product.csv.gz",
        gzip=True,
    )
    _write_csv(result.monthly, temp_dir / "monthly_coverage.csv")
    _write_csv(result.rejected, temp_dir / "rejected_rows.csv.gz", gzip=True)
    (temp_dir / "stage001_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = (
        "# Stage001 全市场PIT单槽替换覆盖审计\n\n"
        f"- 决策：`{summary['decision']}`。\n"
        f"- 评估月：`{summary['eval_months']}`；覆盖行/合格行/池外挑战行："
        f"`{summary['coverage_rows']}/{summary['eligible_rows']}/{summary['challenger_rows']}`。\n"
        f"- 每月合格品种最小/中位/最大：`{summary['minimum_eligible_products']}` / "
        f"`{summary['median_eligible_products']:.1f}` / `{summary['maximum_eligible_products']}`。\n"
        f"- A-rank10合格月/动作就绪月：`{summary['formal_replacement_eligible_months']}` / "
        f"`{summary['action_ready_months']}`；合格月池外挑战者最小值："
        f"`{summary['minimum_challengers_on_eligible_baseline_month']}`。\n"
        f"- 拒绝原因：`{json.dumps(summary['rejection_counts'], ensure_ascii=False, sort_keys=True)}`。\n"
        "- 本阶段未读取收益标签、未fit/predict、未回测、未连接CTP、未调用订单API。\n"
        "- 通过仅允许下一阶段特征预注册，不授权标签、模型或真实引擎。\n"
    )
    (temp_dir / "report.md").write_text(report, encoding="utf-8")

    artifact_names = [
        "coverage_by_eval_product.csv.gz",
        "monthly_coverage.csv",
        "rejected_rows.csv.gz",
        "report.md",
        "stage001_summary.json",
    ]
    manifest = {name: sha256_file(temp_dir / name) for name in sorted(artifact_names)}
    (temp_dir / "artifact_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp_dir.rename(output_dir)


def run_stage001(
    output_dir: Path = OUTPUT_DIR,
    *,
    input_paths: Mapping[str, Path] = INPUT_PATHS,
    expected_sha256: Mapping[str, str] = EXPECTED_SHA256,
    config: core.CoverageConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise Stage001Error("stage001_output_already_exists")
    if output_dir.with_name(f"{output_dir.name}.tmp").exists():
        raise Stage001Error("stage001_temp_output_already_exists")

    before = _verify_inputs(input_paths, expected_sha256)
    ranking = pd.read_csv(Path(input_paths["formal_ranking"]), usecols=FORMAL_COLUMNS)
    mapping = pd.read_csv(Path(input_paths["mapping"]), usecols=MAPPING_COLUMNS)
    metadata = pd.read_csv(Path(input_paths["metadata"]), usecols=METADATA_COLUMNS)
    query_start = _query_start_date(mapping, ranking, config)
    bars = _read_database(
        Path(input_paths["database"]),
        start_date=query_start,
        end_date=pd.Timestamp(config.eval_end),
        allowed_exchanges=config.allowed_exchanges,
    )

    first = core.build_coverage(ranking, mapping, bars, metadata, config)
    second = core.build_coverage(ranking, mapping, bars, metadata, config)
    _assert_repeat_exact(first, second)
    summary = core.assess_coverage(first, config)
    after = _verify_inputs(input_paths, expected_sha256)
    if before != after:
        raise Stage001Error("input_identity_changed_during_run")

    summary.update(
        {
            "line_id": "futures_trend_xgboost_pit_full_market_one_slot",
            "stage": "Stage001",
            "formal_release_id": "m0005_20260901T165450+0800_1961d98ccb2b",
            "formal_strategy_id": "ai_top10_plus_fu_official_live_v1",
            "evidence_scope": "coverage_only_all_history_is_design_data",
            "config": {
                "eval_start": pd.Timestamp(config.eval_start).date().isoformat(),
                "eval_end": pd.Timestamp(config.eval_end).date().isoformat(),
                "expected_months": config.expected_months,
                "expected_ranks_per_month": config.expected_ranks_per_month,
                "expected_static_products": config.expected_static_products,
                "replacement_rank": config.replacement_rank,
                "minimum_mapping_days": config.minimum_mapping_days,
                "minimum_valid_close_days": config.minimum_valid_close_days,
                "activity_window_days": config.activity_window_days,
                "minimum_activity_ratio": config.minimum_activity_ratio,
                "minimum_curve_contracts": config.minimum_curve_contracts,
                "minimum_total_eligible": config.minimum_total_eligible,
                "minimum_action_months": config.minimum_action_months,
                "minimum_challengers": config.minimum_challengers,
                "capital": config.capital,
                "conservative_margin_ratio": config.conservative_margin_ratio,
                "allowed_exchanges": list(config.allowed_exchanges),
                "fixed_satellite": config.fixed_satellite,
            },
            "input_identities_before": before,
            "input_identities_after": after,
            "input_identity_stable": True,
            "repeat_exact": True,
            "formal_columns_read": list(FORMAL_COLUMNS),
            "mapping_columns_read": list(MAPPING_COLUMNS),
            "metadata_columns_read": list(METADATA_COLUMNS),
            "database_columns_read": list(DATABASE_COLUMNS),
            "database_query_start": query_start.date().isoformat(),
            "database_query_end": pd.Timestamp(config.eval_end).date().isoformat(),
            "database_rows_read": int(len(bars)),
            "database_open_mode": "read_only",
            "label_columns_read": [],
            "label_values_read": False,
            "sealed_holdout_files_read": [],
            "model_fit_count": 0,
            "model_predict_count": 0,
            "strategy_backtest_runs": 0,
            "ctp_connected": False,
            "order_api_called_count": 0,
            "production_files_written": 0,
            "diagnostics": first.diagnostics,
        }
    )
    _publish(output_dir, result=first, summary=summary)
    return summary


def main() -> None:
    print(json.dumps(run_stage001(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

