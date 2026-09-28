"""Run the frozen Stage001 PIT contract-return coverage audit."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
import sqlite3
import sys
from typing import Any, Final

import pandas as pd


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import pit_contract_returns as core  # noqa: E402


LINE_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
UPSTREAM = WORKSPACE_ROOT / "research/lines/futures_trend_ai_xgboost_ensemble"
OUTPUT_DIR = LINE_DIR / "artifacts/stage001_pit_contract_return_coverage"
INPUT_PATHS: Final = {
    "database": WORKSPACE_ROOT / ".vntrader/database.db",
    "formal_full_ranking": (
        UPSTREAM
        / "artifacts/stage009_formal_full_ranking_recovery/formal_full_ranking.csv"
    ),
    "base_feature_panel": (
        UPSTREAM
        / "artifacts/stage014_prelabel_feature_contract/prelabel_feature_panel.csv"
    ),
    "spec": (
        LINE_DIR
        / "stages/20260902_1146_stage000_pit_contract_return_design.md"
    ),
}
EXPECTED_SHA256: Final = {
    "database": "7e2633909f73d77c3b0b044199418d7c1ed2989afde480596aefbb18a83b724a",
    "formal_full_ranking": "b2cb417b6c57a7679ae43a1e564c1e79683ca9644b3434cb6a3bfc9e039fcfc0",
    "base_feature_panel": "e8272438cd69fe784b236ac91763f4ec0da71d2b711cd38b576c5e66d237f5fd",
    "spec": "6078e67c5ba041d027fb9b4a025e43a3c06c43675f8e51abc0cdb234104bdb9e",
}


class Stage001Error(RuntimeError):
    """Raised when the frozen Stage001 run must fail closed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_inputs(
    input_paths: Mapping[str, Path],
    expected_sha256: Mapping[str, str],
) -> dict[str, dict[str, Any]]:
    if set(input_paths) != set(expected_sha256):
        raise Stage001Error("input_identity_keys_mismatch")
    identities: dict[str, dict[str, Any]] = {}
    for key in sorted(input_paths):
        path = Path(input_paths[key])
        if not path.is_file():
            raise Stage001Error(f"input_missing:{key}")
        digest = sha256_file(path)
        if digest != str(expected_sha256[key]):
            raise Stage001Error(f"input_sha256_drift:{key}")
        identities[key] = {
            "path": str(path.resolve()),
            "size": int(path.stat().st_size),
            "sha256": digest,
        }
    return identities


def _read_inputs(
    input_paths: Mapping[str, Path],
    *,
    expected_candidate_rows: int,
    expected_product_count: int,
    expected_month_count: int,
    expected_split_counts: Mapping[str, int],
) -> tuple[pd.DataFrame, pd.DataFrame, list[str], pd.Timestamp]:
    formal_path = Path(input_paths["formal_full_ranking"])
    base_path = Path(input_paths["base_feature_panel"])
    formal = pd.read_csv(
        formal_path,
        usecols=["eval_date", "product_vt_symbol", "score_rank"],
    )
    base = pd.read_csv(
        base_path,
        usecols=["eval_date", "product_vt_symbol", "score_rank", "split"],
    )
    formal["eval_date"] = pd.to_datetime(formal["eval_date"], errors="raise").dt.normalize()
    base["eval_date"] = pd.to_datetime(base["eval_date"], errors="raise").dt.normalize()
    formal["score_rank"] = pd.to_numeric(formal["score_rank"], errors="raise").astype(int)
    base["score_rank"] = pd.to_numeric(base["score_rank"], errors="raise").astype(int)
    if len(base) != expected_candidate_rows:
        raise Stage001Error(f"base_candidate_row_count:{len(base)}")
    if base["eval_date"].nunique() != expected_month_count:
        raise Stage001Error(f"base_month_count:{base['eval_date'].nunique()}")
    month_split = base[["eval_date", "split"]].drop_duplicates()
    if month_split.duplicated("eval_date").any():
        raise Stage001Error("base_month_split_duplicate")
    split_counts = {str(key): int(value) for key, value in month_split["split"].value_counts().to_dict().items()}
    if split_counts != dict(expected_split_counts):
        raise Stage001Error(f"base_split_counts:{split_counts}")

    eval_dates = set(base["eval_date"])
    formal = formal[formal["eval_date"].isin(eval_dates)].copy()
    counts = formal.groupby("eval_date").size()
    if len(counts) != expected_month_count or not counts.eq(expected_product_count).all():
        raise Stage001Error("formal_month_product_shape")
    products = sorted(formal["product_vt_symbol"].astype(str).unique())
    if len(products) != expected_product_count:
        raise Stage001Error(f"formal_product_count:{len(products)}")
    return formal, base, products, pd.Timestamp(base["eval_date"].max())


def load_sqlite_bars(
    database_path: Path,
    formal_products: list[str],
    max_date: pd.Timestamp,
) -> pd.DataFrame:
    clauses: list[str] = []
    params: list[str] = []
    for product in formal_products:
        code, separator, exchange = product.partition(".")
        if not separator:
            raise Stage001Error(f"formal_product_invalid:{product}")
        clauses.append("(exchange = ? and symbol glob ?)")
        params.extend([exchange, f"{code}[0-9]*"])
    params.append(f"{max_date.date().isoformat()} 23:59:59")
    query = f"""
        select datetime, symbol, exchange, close_price, open_interest, volume
        from dbbardata
        where interval = 'd'
          and ({' or '.join(clauses)})
          and datetime <= ?
        order by datetime, exchange, symbol
    """
    uri = f"file:{Path(database_path).resolve()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.execute("pragma query_only = on")
        bars = pd.read_sql_query(query, connection, params=params)
    if bars.empty:
        raise Stage001Error("sqlite_daily_bars_empty")
    return bars


def _source_summary(
    returns: pd.DataFrame,
    products: list[str],
) -> pd.DataFrame:
    rows = []
    for product in products:
        group = returns[returns["product_vt_symbol"].eq(product)].copy()
        ok = group["status"].eq("ok") if not group.empty else pd.Series(dtype=bool)
        rows.append(
            {
                "product_vt_symbol": product,
                "return_rows": int(len(group)),
                "ok_return_rows": int(ok.sum()),
                "missing_return_rows": int((~ok).sum()),
                "selected_contract_count": int(
                    group.loc[group["selected_contract_vt"].ne(""), "selected_contract_vt"].nunique()
                ),
                "first_return_date": group["return_date"].min() if not group.empty else pd.NaT,
                "last_return_date": group["return_date"].max() if not group.empty else pd.NaT,
            }
        )
    return pd.DataFrame(rows)


def _normalise_empty_frames(
    missing: pd.DataFrame,
) -> pd.DataFrame:
    columns = ["eval_date", "return_date", "product_vt_symbol", "role", "status"]
    return missing.reindex(columns=columns)


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
    returns: pd.DataFrame,
    coverage: pd.DataFrame,
    missing: pd.DataFrame,
    audit: pd.DataFrame,
    source_summary: pd.DataFrame,
    summary: dict[str, Any],
) -> None:
    output_dir = Path(output_dir)
    temp_dir = output_dir.with_name(f"{output_dir.name}.tmp")
    if output_dir.exists():
        raise Stage001Error("stage001_output_already_exists")
    if temp_dir.exists():
        raise Stage001Error("stage001_temp_output_already_exists")
    temp_dir.mkdir(parents=True, exist_ok=False)

    _write_csv(returns, temp_dir / "product_daily_returns.csv.gz", gzip=True)
    _write_csv(coverage, temp_dir / "coverage_by_eval_product.csv")
    _write_csv(_normalise_empty_frames(missing), temp_dir / "missing_required_cells.csv")
    _write_csv(audit, temp_dir / "window_audit.csv")
    _write_csv(source_summary, temp_dir / "source_product_summary.csv")
    (temp_dir / "stage001_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = (
        "# Stage001 PIT逐合约收益覆盖审计\n\n"
        f"- 决策：`{summary['decision']}`。\n"
        f"- 正式候选样本：`{summary['candidate_rows']}`；完整候选窗口："
        f"`{summary['complete_candidate_windows']}`。\n"
        f"- 完整Top窗口：`{summary['complete_top_windows']}` / "
        f"`{summary['expected_top_windows']}`。\n"
        f"- required missing cells：`{summary['missing_required_cells']}`。\n"
        f"- PIT/fallback/跨合约违规：`{summary['pit_violations']}` / "
        f"`{summary['fallback_rows']}` / `{summary['cross_contract_rows']}`。\n"
        "- 本阶段只审计标签前市场数据，不读取账户边际标签，不训练模型，"
        "不运行回测，不连接CTP，不调用订单API。\n"
    )
    (temp_dir / "report.md").write_text(report, encoding="utf-8")
    names = [
        "coverage_by_eval_product.csv",
        "missing_required_cells.csv",
        "product_daily_returns.csv.gz",
        "report.md",
        "source_product_summary.csv",
        "stage001_summary.json",
        "window_audit.csv",
    ]
    manifest = {name: sha256_file(temp_dir / name) for name in names}
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
    window_days: int = 120,
    top_rank_count: int = 9,
    expected_candidate_rows: int = 459,
    expected_product_count: int = 18,
    expected_month_count: int = 51,
    expected_split_counts: Mapping[str, int] = {
        "development": 39,
        "sealed_holdout": 12,
    },
) -> dict[str, Any]:
    if Path(output_dir).exists():
        raise Stage001Error("stage001_output_already_exists")
    before = _verify_inputs(input_paths, expected_sha256)
    formal, base, products, max_date = _read_inputs(
        input_paths,
        expected_candidate_rows=expected_candidate_rows,
        expected_product_count=expected_product_count,
        expected_month_count=expected_month_count,
        expected_split_counts=expected_split_counts,
    )
    bars = load_sqlite_bars(Path(input_paths["database"]), products, max_date)
    returns = core.build_lagged_oi_returns(bars, products)
    coverage, missing, audit = core.audit_feature_windows(
        base,
        formal,
        returns,
        window_days=window_days,
        top_rank_count=top_rank_count,
    )
    summary = core.assess_coverage(
        coverage,
        missing,
        audit,
        returns,
        expected_candidate_rows=expected_candidate_rows,
        window_days=window_days,
    )
    after = _verify_inputs(input_paths, expected_sha256)
    if before != after:
        raise Stage001Error("input_identity_changed_during_run")
    summary.update(
        {
            "line_id": "futures_trend_xgboost_pit_contract_returns",
            "stage": "Stage001",
            "formal_release_id": "m0005_20260901T165450+0800_1961d98ccb2b",
            "window_days": int(window_days),
            "top_rank_count": int(top_rank_count),
            "formal_product_count": int(len(products)),
            "formal_products": products,
            "eval_months": int(base["eval_date"].nunique()),
            "daily_bar_rows_read": int(len(bars)),
            "daily_return_rows": int(len(returns)),
            "ok_daily_return_rows": int(returns["status"].eq("ok").sum()),
            "input_identities_before": before,
            "input_identities_after": after,
            "input_identity_stable": True,
            "read_paths": sorted(str(Path(path).resolve()) for path in input_paths.values()),
            "label_files_read": [],
            "label_values_read": False,
            "trains_model": False,
            "runs_backtest": False,
            "ctp_connected": False,
            "order_api_called_count": 0,
        }
    )
    _publish(
        Path(output_dir),
        returns=returns,
        coverage=coverage,
        missing=missing,
        audit=audit,
        source_summary=_source_summary(returns, products),
        summary=summary,
    )
    return summary


def main() -> None:
    print(json.dumps(run_stage001(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
