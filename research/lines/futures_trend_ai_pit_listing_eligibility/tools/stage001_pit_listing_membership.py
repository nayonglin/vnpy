"""Run the frozen PIT listing membership audit for the formal AI pool."""

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

import pit_listing_eligibility as core  # noqa: E402


LINE_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
UPSTREAM = WORKSPACE_ROOT / "research/lines/futures_trend_ai_xgboost_ensemble"
PRODUCTION_ROOT = Path("/Users/bytedance/Desktop/person/vnpy_production_live")
FORMAL_RELEASE_ID = "m0005_20260901T165450+0800_1961d98ccb2b"
OUTPUT_DIR = LINE_DIR / "artifacts/stage001_pit_listing_membership"
INPUT_PATHS: Final = {
    "database": WORKSPACE_ROOT / ".vntrader/database.db",
    "formal_full_ranking": (
        UPSTREAM
        / "artifacts/stage009_formal_full_ranking_recovery/formal_full_ranking.csv"
    ),
    "formal_eligibility": (
        PRODUCTION_ROOT
        / "official_strategy_materials/ai_top10_plus_fu_official_live_v1/releases"
        / FORMAL_RELEASE_ID
        / "payload/ai/stage182/combined_eligibility.csv"
    ),
    "spec": (
        LINE_DIR
        / "stages/20260902_1209_stage000_pit_listing_eligibility_preregistration.md"
    ),
    "core": LINE_DIR / "tools/pit_listing_eligibility.py",
}
EXPECTED_SHA256: Final = {
    "database": "7e2633909f73d77c3b0b044199418d7c1ed2989afde480596aefbb18a83b724a",
    "formal_full_ranking": "b2cb417b6c57a7679ae43a1e564c1e79683ca9644b3434cb6a3bfc9e039fcfc0",
    "formal_eligibility": "fafe6fbaf9836706e2d70d40c799dd4ea4db279fb283fda76d18a797f126d018",
    "spec": "b4a5a371016aea42a62dc37080aba31fa719684c81f5fe6f86fe9729a1bbbc5d",
    "core": "1f1757910532a3e47daf9fd90d31ddd13754d54970eca9f1e5cdaf83dbde78c2",
}
PASS_DECISION = "stage001_pit_listing_membership_pass_allow_frozen_ac_design"
FAIL_DECISION = "stage001_pit_listing_membership_fail_stop_no_backtest"


class Stage001Error(RuntimeError):
    """Raised when the frozen Stage001 audit must fail closed."""


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
    for name in sorted(input_paths):
        path = Path(input_paths[name])
        if not path.is_file():
            raise Stage001Error(f"input_missing:{name}")
        digest = sha256_file(path)
        if digest != expected_sha256[name]:
            raise Stage001Error(f"input_sha256_drift:{name}")
        identities[name] = {
            "path": str(path.resolve()),
            "size": int(path.stat().st_size),
            "sha256": digest,
        }
    return identities


def _load_daily_bar_keys(database: Path, products: list[str]) -> pd.DataFrame:
    clauses: list[str] = []
    parameters: list[str] = []
    for product in products:
        code, separator, exchange = product.partition(".")
        if not separator:
            raise Stage001Error(f"product_invalid:{product}")
        clauses.append("(exchange = ? and symbol glob ?)")
        parameters.extend([exchange, f"{code}[0-9]*"])
    query = f"""
        select datetime, symbol, exchange
        from dbbardata
        where interval = 'd'
          and ({' or '.join(clauses)})
        order by datetime, exchange, symbol
    """
    uri = f"file:{Path(database).resolve()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.execute("pragma query_only = on")
        frame = pd.read_sql_query(query, connection, params=parameters)
    if frame.empty:
        raise Stage001Error("daily_bar_keys_empty")
    return frame


def _normalise_inputs(
    input_paths: Mapping[str, Path],
    *,
    expected_ranked_products: int,
    expected_ranking_months: int,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    ranking = pd.read_csv(Path(input_paths["formal_full_ranking"]))
    formal = pd.read_csv(Path(input_paths["formal_eligibility"]))
    ranking_dates = pd.to_datetime(ranking["eval_date"], errors="raise").dt.normalize()
    products = sorted(ranking["product_vt_symbol"].astype(str).unique())
    if len(products) != expected_ranked_products:
        raise Stage001Error(f"ranked_product_count:{len(products)}")
    if ranking_dates.nunique() != expected_ranking_months:
        raise Stage001Error(f"ranking_month_count:{ranking_dates.nunique()}")
    return formal, ranking, products


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(
        path,
        index=False,
        encoding="utf-8-sig",
        float_format="%.17g",
        lineterminator="\n",
    )


def _publish(
    output_dir: Path,
    *,
    candidate: pd.DataFrame,
    first_dates: pd.DataFrame,
    audit: pd.DataFrame,
    summary: dict[str, Any],
) -> None:
    output_dir = Path(output_dir)
    temp_dir = output_dir.with_name(f"{output_dir.name}.tmp")
    if output_dir.exists():
        raise Stage001Error("stage001_output_already_exists")
    if temp_dir.exists():
        raise Stage001Error("stage001_temp_output_already_exists")
    temp_dir.mkdir(parents=True, exist_ok=False)

    _write_csv(candidate, temp_dir / "candidate_eligibility.csv")
    _write_csv(first_dates, temp_dir / "first_available_dates.csv")
    _write_csv(audit, temp_dir / "membership_audit.csv")
    (temp_dir / "stage001_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    changed_dates = audit.loc[audit["membership_changed"].astype(bool), "eval_date"].tolist()
    report = (
        "# Stage001 PIT上市资格成员审计\n\n"
        f"- 决策：`{summary['decision']}`。\n"
        f"- 完整正式排序月：`{summary['ranking_months']}`；发生成员修正："
        f"`{summary['changed_months']}`。\n"
        f"- 正式Top10不可见席位：`{summary['unavailable_formal_top10_slots']}`；"
        f"候选不可见席位：`{summary['candidate_unavailable_count']}`。\n"
        f"- 首个/最后一个修正月：`{changed_dates[0] if changed_dates else '无'}` / "
        f"`{changed_dates[-1] if changed_dates else '无'}`。\n"
        "- 本阶段不读取账户边际标签或sealed holdout，不训练模型、不运行回测，"
        "不连接CTP、不调用订单API。\n"
    )
    (temp_dir / "report.md").write_text(report, encoding="utf-8")
    payload_names = [
        "candidate_eligibility.csv",
        "first_available_dates.csv",
        "membership_audit.csv",
        "report.md",
        "stage001_summary.json",
    ]
    manifest = {name: sha256_file(temp_dir / name) for name in payload_names}
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
    expected_ranked_products: int = 18,
    expected_ranking_months: int = 55,
    unchanged_from: pd.Timestamp = pd.Timestamp("2023-09-28"),
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise Stage001Error("stage001_output_already_exists")
    before = _verify_inputs(input_paths, expected_sha256)
    formal, ranking, products = _normalise_inputs(
        input_paths,
        expected_ranked_products=expected_ranked_products,
        expected_ranking_months=expected_ranking_months,
    )
    bars = _load_daily_bar_keys(Path(input_paths["database"]), products)
    first_available = core.derive_first_available_dates(bars, products)
    candidate, audit = core.build_pit_listing_candidate(
        formal,
        ranking,
        first_available,
        expected_ranked_products=expected_ranked_products,
    )
    contract = core.validate_membership_contract(
        formal,
        candidate,
        audit,
        first_available,
        unchanged_from=unchanged_from,
    )
    after = _verify_inputs(input_paths, expected_sha256)
    if before != after:
        raise Stage001Error("input_identity_changed_during_run")

    first_dates = pd.DataFrame(
        [
            {
                "product_vt_symbol": product,
                "first_available_date": first_available[product].strftime("%Y-%m-%d"),
                "source": "sqlite_regular_contract_daily_bar_min_date",
            }
            for product in sorted(first_available)
        ]
    )
    gates = {
        "input_identity_stable": before == after,
        "ranking_month_count_exact": contract["ranking_months"] == expected_ranking_months,
        "first_available_complete": len(first_available) == expected_ranked_products,
        "candidate_unavailable_zero": contract["unavailable_candidate_count"] == 0,
        "post_boundary_membership_unchanged": contract["post_boundary_changed_months"] == 0,
        "future_outcome_rows_used_zero": contract["future_rows_used"] == 0,
        "candidate_row_count_preserved": len(candidate) == len(formal),
    }
    passed = all(gates.values())
    changed = audit[audit["membership_changed"].astype(bool)]
    summary: dict[str, Any] = {
        "line_id": "futures_trend_ai_pit_listing_eligibility",
        "stage": "Stage001",
        "decision": PASS_DECISION if passed else FAIL_DECISION,
        "all_gates_passed": bool(passed),
        "gates": gates,
        "formal_release_id": FORMAL_RELEASE_ID,
        "ranking_months": int(contract["ranking_months"]),
        "changed_months": int(contract["changed_months"]),
        "changed_eval_dates": changed["eval_date"].astype(str).tolist(),
        "unavailable_formal_top10_slots": int(
            audit["formal_unavailable_top10_count"].sum()
        ),
        "candidate_unavailable_count": int(contract["unavailable_candidate_count"]),
        "first_available_dates": {
            product: value.strftime("%Y-%m-%d")
            for product, value in sorted(first_available.items())
        },
        "database_query_only": True,
        "daily_bar_key_rows_read": int(len(bars)),
        "formal_eligibility_rows": int(len(formal)),
        "candidate_eligibility_rows": int(len(candidate)),
        "inputs_before": before,
        "inputs_after": after,
        "account_marginal_label_rows_read": 0,
        "sealed_holdout_rows_read": 0,
        "model_training_runs": 0,
        "strategy_backtest_runs": 0,
        "ctp_connected": False,
        "order_api_called_count": 0,
    }
    _publish(
        output_dir,
        candidate=candidate,
        first_dates=first_dates,
        audit=audit,
        summary=summary,
    )
    return summary


def main() -> None:
    summary = run_stage001()
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
