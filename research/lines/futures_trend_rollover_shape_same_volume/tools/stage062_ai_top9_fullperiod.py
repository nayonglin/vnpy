from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Iterable
from uuid import uuid4

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
TOOLS_DIR = Path(__file__).resolve().parent
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
for directory in (TOOLS_DIR, PORTFOLIO_DIR):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import qmt_roll_candidate_stage062_ai_top9_config as candidate_cfg  # noqa: E402
from main_contract_mapping import load_product_universe_symbols  # noqa: E402
import stage061_ai_top10_to_top19_fullperiod as s61  # noqa: E402


LINE_ID = s61.LINE_ID
STAGE = "Stage062"
BASE_MASTER_COMMIT = s61.BASE_MASTER_COMMIT
BASE_RULESET_VERSION = s61.BASE_RULESET_VERSION
BASE_RELEASE_ID = s61.BASE_RELEASE_ID
BASE_SOURCE_COMMIT = s61.BASE_SOURCE_COMMIT
BASE_STAGE061_COMMIT = "6750783fe7aab92e6dbdd6820fa212e2e53ea353"
START = s61.START
EXPECTED_FIRST_TRADING_DAY = s61.EXPECTED_FIRST_TRADING_DAY
END = s61.END
FU_PRODUCT = s61.FU_PRODUCT
TOP_N = 9
NEW_ENGINE_TOP_NS = (TOP_N,)
REUSED_STAGE061_TOP_NS = tuple(range(10, 20))
TOP9_ARM = {
    "arm": "T9",
    "requested_top_n": 9,
    "actual_ranked_count": 9,
    "actual_total_count": 10,
    "profile": "stage062_top9_plus_fu",
    "label": "Top9+fu（实际10品种）",
    "plot_label": "Top9",
}

LINE_DIR = Path(__file__).resolve().parents[1]
STAGE061_DIR = s61.OUTPUT_DIR
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage062_ai_top9_fullperiod"
CHECKPOINT_DIR = PROJECT_DIR / ".tools" / "stage062_ai_top9_checkpoint"
ELIGIBILITY_PATH = CHECKPOINT_DIR / "stage062_top9_eligibility.csv"
RANKING_AUDIT_PATH = CHECKPOINT_DIR / "stage062_full_ranking_audit.csv"

SUMMARY_NAME = "stage062_summary.csv"
COMPARISON_NAME = "stage062_comparison.csv"
CURVE_NAME = "stage062_equity_curve.csv"
TRADES_NAME = "stage062_trades.csv"
ELIGIBILITY_NAME = "stage062_eligibility.csv"
MEMBERSHIP_AUDIT_NAME = "stage062_membership_audit.csv"
RANKING_AUDIT_NAME = "stage062_full_ranking_audit.csv"
DECISION_NAME = "stage062_decision.json"
REPORT_NAME = "stage062_report.md"
EQUITY_CHART_NAME = "stage062_equity_top9_top19.png"
RESPONSE_CHART_NAME = "stage062_metric_response.png"
PLOT_TITLE = "OFFLINE RESEARCH — Stage062 AI Top9–Top19 Full Period"
REPORT_BANNER = "> **离线研究，非当前实盘策略；不得据此发单或自动晋升。**"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=PROJECT_DIR, check=True, capture_output=True, text=True
    ).stdout.strip()


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_offline_identity_contract(
    checkout_identity: dict[str, Any],
    production_identity: dict[str, Any],
    remote_master: str,
) -> dict[str, Any]:
    expected = {
        "strategy_version": "official_live_stage847_c9_15w_stage819_05r_stop_retry_once",
        "ruleset_version": BASE_RULESET_VERSION,
        "material_release_id": BASE_RELEASE_ID,
        "source_commit": BASE_SOURCE_COMMIT,
    }
    actual = {key: checkout_identity.get(key) for key in expected}
    if actual != expected or remote_master != BASE_MASTER_COMMIT:
        raise RuntimeError(
            "stage062_stage037_identity_mismatch:"
            f"actual={actual}:expected={expected}:remote={remote_master}"
        )
    production_matches = all(
        production_identity.get(key) == value for key, value in expected.items()
    )
    return {
        "research_protocol": "explicit_stage037_ai_top9_offline_boundary_check",
        "checkout_stage037_identity_pass": True,
        "production_identity_matches_stage037": bool(production_matches),
        "stage061_source_commit": BASE_STAGE061_COMMIT,
        "formal_production_ac_compliant": False,
        "promotion_permitted": False,
    }


def select_top9_plus_fu(
    ranking: pd.DataFrame,
    *,
    locked_non_fu: Iterable[str] = (),
) -> pd.DataFrame:
    ranked = s61.s56._normalise_ranking(ranking)
    if ranked["eval_date"].nunique() != 1:
        raise RuntimeError("stage062_ranking_must_have_one_eval_date")
    if ranked["product_vt_symbol"].duplicated().any():
        raise RuntimeError("stage062_duplicate_ranking_product")
    non_fu = ranked[~ranked["product_vt_symbol"].eq(FU_PRODUCT)].copy()
    if len(non_fu) != s61.RANKED_UNIVERSE_COUNT:
        raise RuntimeError(f"stage062_ranked_universe_count:{len(non_fu)}")
    locked = tuple(dict.fromkeys(str(product) for product in locked_non_fu))
    if len(locked) > TOP_N or set(locked) - set(non_fu["product_vt_symbol"]):
        raise RuntimeError(f"stage062_invalid_locked_products:{locked}")
    indexed = non_fu.set_index("product_vt_symbol", drop=False)
    fill = non_fu[~non_fu["product_vt_symbol"].isin(locked)].head(TOP_N - len(locked))
    selected = pd.concat(
        [indexed.loc[list(locked)].copy() if locked else non_fu.iloc[0:0].copy(), fill],
        ignore_index=True,
    )
    if len(selected) != TOP_N or selected["product_vt_symbol"].nunique() != TOP_N:
        raise RuntimeError("stage062_selected_member_contract_failed")
    eval_date = str(ranked["eval_date"].iloc[0])
    score_type = (
        "membership_locked_top9_plus_fixed_fu"
        if locked
        else "ai_probability_top9_plus_fixed_fu"
    )
    rows = [
        {
            "strategy": candidate_cfg.STRATEGY,
            "score_type": score_type,
            "eval_date": eval_date,
            "product_vt_symbol": str(row.product_vt_symbol),
            "score": float(row.score),
            "score_rank": rank,
            "top_n": TOP_N + 1,
        }
        for rank, row in enumerate(selected.itertuples(index=False), start=1)
    ]
    min_score = min(row["score"] for row in rows)
    rows.append(
        {
            "strategy": candidate_cfg.STRATEGY,
            "score_type": score_type,
            "eval_date": eval_date,
            "product_vt_symbol": FU_PRODUCT,
            "score": min_score - 1e-6,
            "score_rank": TOP_N + 1,
            "top_n": TOP_N + 1,
        }
    )
    return pd.DataFrame(rows, columns=s61.s56.ELIGIBILITY_COLUMNS)


def build_candidate_eligibility(
    formal: pd.DataFrame,
    ranking_source: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    formal = formal.loc[:, s61.s56.ELIGIBILITY_COLUMNS].copy()
    formal["eval_date"] = (
        pd.to_datetime(formal["eval_date"], errors="raise").dt.date.astype(str)
    )
    ranking_source = s61.s56._normalise_ranking(ranking_source)
    pre_ai = s61.s56.preserve_pre_ai_boundary(formal)
    pre_ai["strategy"] = candidate_cfg.STRATEGY
    rows = [pre_ai]
    audits: list[dict[str, Any]] = []
    model_dates = sorted(
        date for date in formal["eval_date"].unique() if date != "2019-12-31"
    )
    for eval_date in model_dates:
        formal_month = formal[formal["eval_date"].eq(eval_date)].sort_values("score_rank")
        formal_non_fu = tuple(
            formal_month.loc[
                ~formal_month["product_vt_symbol"].eq(FU_PRODUCT),
                "product_vt_symbol",
            ].astype(str)
        )
        ranking_month = ranking_source[ranking_source["eval_date"].eq(eval_date)].copy()
        ranking_non_fu = ranking_month[
            ~ranking_month["product_vt_symbol"].eq(FU_PRODUCT)
        ].copy()
        ranking_non_fu["source_rank"] = range(1, len(ranking_non_fu) + 1)
        strict_model_top9 = tuple(
            ranking_non_fu.head(TOP_N)["product_vt_symbol"].astype(str)
        )
        locked = formal_non_fu if eval_date in s61.MEMBERSHIP_ONLY_DATES else ()
        selected = select_top9_plus_fu(ranking_month, locked_non_fu=locked)
        selected_non_fu = set(
            selected.loc[
                ~selected["product_vt_symbol"].eq(FU_PRODUCT),
                "product_vt_symbol",
            ].astype(str)
        )
        if not set(formal_non_fu).issubset(selected_non_fu):
            raise RuntimeError(f"stage062_formal_top8_not_preserved:{eval_date}")
        strict_model_top9_set = set(strict_model_top9)
        added_vs_strict = sorted(selected_non_fu - strict_model_top9_set)
        excluded_vs_strict = sorted(strict_model_top9_set - selected_non_fu)
        source_rank_by_product = dict(
            zip(
                ranking_non_fu["product_vt_symbol"].astype(str),
                ranking_non_fu["source_rank"].astype(int),
            )
        )
        ranking_provenance = sorted(
            set(ranking_month["ranking_provenance"].dropna().astype(str))
        )
        rows.append(selected)
        audits.append(
            {
                "requested_top_n": TOP_N,
                "eval_date": eval_date,
                "actual_ranked_count": len(selected_non_fu),
                "actual_total_count": int(selected["product_vt_symbol"].nunique()),
                "formal_top8_preserved": True,
                "fixed_fu_present": FU_PRODUCT
                in set(selected["product_vt_symbol"].astype(str)),
                "membership_policy": (
                    "formal_top8_locked_then_same_month_model_fill_to_9_plus_fixed_fu"
                    if locked
                    else "strict_model_top9_plus_fixed_fu"
                ),
                "strict_model_top9_match": not added_vs_strict
                and not excluded_vs_strict,
                "strict_model_top9_signature": ",".join(strict_model_top9),
                "selected_non_fu_signature": ",".join(sorted(selected_non_fu)),
                "added_vs_strict_top9": ",".join(added_vs_strict),
                "excluded_vs_strict_top9": ",".join(excluded_vs_strict),
                "selected_source_ranks": ",".join(
                    f"{product}:{source_rank_by_product[product]}"
                    for product in sorted(
                        selected_non_fu, key=lambda item: source_rank_by_product[item]
                    )
                ),
                "ranking_provenance": ",".join(ranking_provenance),
                "member_signature": ",".join(
                    sorted(selected["product_vt_symbol"].astype(str))
                ),
            }
        )
    result = pd.concat(rows, ignore_index=True)
    result["requested_top_n"] = TOP_N
    result.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    result.reset_index(drop=True, inplace=True)
    return result, pd.DataFrame(audits)


def _write_eligibility() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    formal = pd.read_csv(s61.s56.FORMAL_ELIGIBILITY_PATH)
    ranking_source, ranking_audit = s61.s56.build_full_ranking_source()
    eligibility, membership = build_candidate_eligibility(formal, ranking_source)
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    eligibility.drop(columns=["requested_top_n"]).to_csv(
        ELIGIBILITY_PATH, index=False, encoding="utf-8-sig"
    )
    ranking_audit.to_csv(RANKING_AUDIT_PATH, index=False, encoding="utf-8-sig")
    return eligibility, membership, ranking_audit


def _preflight() -> dict[str, Any]:
    checkout = asdict(s61.s56.assert_official_checkout_matches_active_material(PROJECT_DIR))
    production = asdict(
        s61.s56.assert_official_checkout_matches_active_material(s61.s56.PRODUCTION_ROOT)
    )
    remote_master = _git("rev-parse", "origin/master")
    evidence = _assert_offline_identity_contract(checkout, production, remote_master)
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASE_STAGE061_COMMIT, "HEAD"],
        cwd=PROJECT_DIR,
        check=True,
    )
    if set(candidate_cfg.override_diff(ELIGIBILITY_PATH)) != {
        "ai_product_pool_eligibility_path",
        "ai_product_pool_strategy",
    }:
        raise RuntimeError("stage062_override_scope_drift")
    universe_path = Path(
        s61.s56.live_cfg.build_official_live_strategy_overrides()[
            "product_universe_csv_path"
        ]
    )
    products = load_product_universe_symbols(universe_path)
    if len(products) != 19 or len(set(products)) != 19:
        raise RuntimeError(f"stage062_product_universe_contract_failed:{products}")
    source_hashes = {
        filename: _file_sha256(STAGE061_DIR / filename)
        for filename in (
            s61.SUMMARY_NAME,
            s61.CURVE_NAME,
            s61.TRADES_NAME,
            s61.DECISION_NAME,
        )
    }
    ranking_audit = pd.read_csv(RANKING_AUDIT_PATH)
    provenance_counts = {
        str(key): int(value)
        for key, value in ranking_audit["ranking_provenance"].value_counts().items()
    }
    if len(ranking_audit) != 990 or ranking_audit["eval_date"].nunique() != 55:
        raise RuntimeError("stage062_ranking_audit_coverage_drift")
    return {
        **evidence,
        "checkout_identity": checkout,
        "production_identity": production,
        "checkout_head": _git("rev-parse", "HEAD"),
        "remote_master": remote_master,
        "database_path": str(s61.s56.DATABASE_PATH.resolve()),
        "database_sha256": _file_sha256(s61.s56.DATABASE_PATH),
        "candidate_eligibility_path": str(ELIGIBILITY_PATH.resolve()),
        "candidate_eligibility_sha256": _file_sha256(ELIGIBILITY_PATH),
        "formal_eligibility_path": str(s61.s56.FORMAL_ELIGIBILITY_PATH),
        "formal_eligibility_sha256": _file_sha256(
            s61.s56.FORMAL_ELIGIBILITY_PATH
        ),
        "ranking_audit_path": str(RANKING_AUDIT_PATH.resolve()),
        "ranking_audit_sha256": _file_sha256(RANKING_AUDIT_PATH),
        "ranking_audit_row_count": len(ranking_audit),
        "ranking_provenance_counts": provenance_counts,
        "ranking_source_files": {
            "market_walkforward": {
                "path": str(s61.s56.MARKET_RANKING_PATH),
                "sha256": _file_sha256(s61.s56.MARKET_RANKING_PATH),
            },
            "stage189_membership_fill": {
                "path": str(s61.s56.STAGE189_RANKING_PATH),
                "sha256": _file_sha256(s61.s56.STAGE189_RANKING_PATH),
            },
            "formal_latest_pool": {
                "path": str(s61.s56.LATEST_RANKING_PATH),
                "sha256": _file_sha256(s61.s56.LATEST_RANKING_PATH),
            },
            "stage183_position_changes": {
                "path": str(s61.s56.STAGE183_POSITION_CHANGES_PATH),
                "sha256": _file_sha256(s61.s56.STAGE183_POSITION_CHANGES_PATH),
            },
            "stage183_entry_snapshots": {
                "path": str(s61.s56.STAGE183_ENTRY_SNAPSHOTS_PATH),
                "sha256": _file_sha256(s61.s56.STAGE183_ENTRY_SNAPSHOTS_PATH),
            },
        },
        "product_universe_path": str(universe_path.resolve()),
        "product_universe_sha256": _file_sha256(universe_path),
        "stage061_artifact_sha256": source_hashes,
    }


def _load_stage061_artifacts() -> tuple[
    dict[int | str, pd.DataFrame],
    dict[int | str, pd.DataFrame],
    dict[int, pd.DataFrame],
]:
    summary = pd.read_csv(STAGE061_DIR / s61.SUMMARY_NAME)
    curve = pd.read_csv(STAGE061_DIR / s61.CURVE_NAME)
    trades = pd.read_csv(STAGE061_DIR / s61.TRADES_NAME)
    summaries: dict[int | str, pd.DataFrame] = {
        "REF": summary[summary["experiment_arm"].astype(str).eq("REF")].copy()
    }
    curves: dict[int | str, pd.DataFrame] = {
        "REF": curve[curve["experiment_arm"].astype(str).eq("REF")].copy()
    }
    arm_trades: dict[int, pd.DataFrame] = {}
    for top_n in REUSED_STAGE061_TOP_NS:
        arm = f"T{top_n}"
        summaries[top_n] = summary[summary["experiment_arm"].astype(str).eq(arm)].copy()
        curves[top_n] = curve[curve["experiment_arm"].astype(str).eq(arm)].copy()
        arm_trades[top_n] = trades[trades["experiment_arm"].astype(str).eq(arm)].copy()
        if len(summaries[top_n]) != 1 or len(curves[top_n]) != 2101:
            raise RuntimeError(f"stage062_stage061_reuse_incomplete:{top_n}")
    return summaries, curves, arm_trades


def _contract_hash() -> str:
    digest = sha256()
    for path in (
        Path(__file__),
        Path(candidate_cfg.__file__),
        Path(s61.__file__),
        Path(s61.s56.__file__),
        PROJECT_DIR / "examples" / "portfolio_backtesting" / "qmt_roll_portfolio_strategy.py",
        ELIGIBILITY_PATH,
    ):
        digest.update(path.read_bytes())
    digest.update(_file_sha256(s61.s56.DATABASE_PATH).encode())
    digest.update(f"{TOP_N}:{START.date()}:{END.date()}".encode())
    return digest.hexdigest()


def _load_checkpoint() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame] | None:
    metadata_path = CHECKPOINT_DIR / "metadata.json"
    if not metadata_path.exists():
        return None
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("contract_sha256") != _contract_hash():
        return None
    return (
        pd.read_csv(CHECKPOINT_DIR / "summary.csv"),
        pd.read_csv(CHECKPOINT_DIR / "curve.csv"),
        pd.read_csv(CHECKPOINT_DIR / "trades.csv"),
    )


def _save_checkpoint(
    summary: pd.DataFrame,
    curve: pd.DataFrame,
    trades: pd.DataFrame,
) -> None:
    temporary = Path(tempfile.mkdtemp(prefix=".stage062-top9-", dir=CHECKPOINT_DIR.parent))
    backup = CHECKPOINT_DIR.with_name(f".stage062.backup-{uuid4().hex}")
    try:
        summary.to_csv(temporary / "summary.csv", index=False, encoding="utf-8-sig")
        curve.to_csv(temporary / "curve.csv", index=False, encoding="utf-8-sig")
        trades.to_csv(temporary / "trades.csv", index=False, encoding="utf-8-sig")
        shutil.copy2(ELIGIBILITY_PATH, temporary / ELIGIBILITY_PATH.name)
        shutil.copy2(RANKING_AUDIT_PATH, temporary / RANKING_AUDIT_PATH.name)
        (temporary / "metadata.json").write_text(
            json.dumps(
                {
                    "top_n": TOP_N,
                    "contract_sha256": _contract_hash(),
                    "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        if CHECKPOINT_DIR.exists():
            CHECKPOINT_DIR.rename(backup)
        temporary.rename(CHECKPOINT_DIR)
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def _run_top9(metadata: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cached = _load_checkpoint()
    if cached is not None:
        print("[stage062] reuse checkpoint Top9", flush=True)
        return cached
    original_builder = s61.s56.s28.s901.build_official_live_strategy_overrides
    try:
        s61.s56.s28.s901.build_official_live_strategy_overrides = (
            lambda: candidate_cfg.build_candidate_overrides(ELIGIBILITY_PATH)
        )
        combined, frames, live_spec = s61.s56.s28.s901._run_live_c9(
            metadata, START, END
        )
    finally:
        s61.s56.s28.s901.build_official_live_strategy_overrides = original_builder
    capital = replace(
        live_spec.capital,
        variant=TOP9_ARM["profile"],
        label=TOP9_ARM["label"],
    )
    metric_spec = replace(live_spec, capital=capital, profile=TOP9_ARM["profile"])
    summary, curve = s61.s56.s28.s827._metric(
        {"profile": TOP9_ARM["profile"], "spec": metric_spec}, combined
    )
    summary = s61._relabel(summary, TOP9_ARM)
    summary["window_name"] = "full_2018_20260828"
    summary["window_label"] = "2018-01-01 independent start to 2026-08-28"
    curve = s61._relabel(curve, TOP9_ARM)
    trades = s61._relabel(frames.get("trades", pd.DataFrame()), TOP9_ARM)
    _save_checkpoint(summary, curve, trades)
    return summary, curve, trades


def _assert_coverage(summary: pd.DataFrame, curve: pd.DataFrame) -> None:
    expected_arms = {"REF", *(f"T{top_n}" for top_n in range(9, 20))}
    if len(summary) != len(expected_arms) or set(summary["experiment_arm"].astype(str)) != expected_arms:
        raise RuntimeError("stage062_arm_identity_failed")
    reference: pd.DatetimeIndex | None = None
    for arm in ["REF", *(f"T{top_n}" for top_n in range(9, 20))]:
        dates = pd.DatetimeIndex(
            pd.to_datetime(
                curve[curve["experiment_arm"].astype(str).eq(arm)]["date"],
                errors="raise",
                format="mixed",
            ).dt.normalize()
        )
        if reference is None:
            reference = dates
        if (
            dates.duplicated().any()
            or not dates.equals(reference)
            or dates.min() != EXPECTED_FIRST_TRADING_DAY
            or dates.max() != END
        ):
            raise RuntimeError(f"stage062_full_period_coverage_failed:{arm}")


def _full_period_gates(values: dict[str, Any]) -> dict[str, bool]:
    return s61._full_period_gates(values)


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    indexed = summary.set_index("experiment_arm")
    baseline = indexed.loc["REF"]
    rows = []
    for top_n in range(9, 20):
        candidate = indexed.loc[f"T{top_n}"]
        values = {
            "candidate_total_return_pct": float(candidate["total_return_pct"]),
            "baseline_total_return_pct": float(baseline["total_return_pct"]),
            "candidate_max_dd_pct": float(candidate["max_dd_pct"]),
            "baseline_max_dd_pct": float(baseline["max_dd_pct"]),
            "candidate_sharpe": float(candidate["sharpe"]),
            "baseline_sharpe": float(baseline["sharpe"]),
            "candidate_total_slippage": float(candidate["total_slippage"]),
            "baseline_total_slippage": float(baseline["total_slippage"]),
            "candidate_account_survival_pass": int(candidate["account_survival_pass"]),
            "candidate_days_over_100pct": int(candidate["days_over_100pct"]),
            "baseline_days_over_100pct": int(baseline["days_over_100pct"]),
        }
        gates = _full_period_gates(values)
        rows.append(
            {
                "requested_top_n": top_n,
                "actual_ranked_count": min(top_n, s61.RANKED_UNIVERSE_COUNT),
                "actual_total_count": min(top_n, s61.RANKED_UNIVERSE_COUNT) + 1,
                "duplicate_of_top_n": 18 if top_n == 19 else "",
                "end_equity": float(candidate["end_equity"]),
                "total_return_pct": float(candidate["total_return_pct"]),
                "max_dd_pct": float(candidate["max_dd_pct"]),
                "sharpe": float(candidate["sharpe"]),
                "total_slippage": float(candidate["total_slippage"]),
                "total_trade_count": float(candidate["total_trade_count"]),
                "nonzero_daily_win_rate_pct": float(candidate["nonzero_daily_win_rate_pct"]),
                "max_broker10_margin_to_equity_pct": float(
                    candidate["max_broker10_margin_to_equity_pct"]
                ),
                "days_over_100pct": int(candidate["days_over_100pct"]),
                "delta_return_vs_stage037_pp": float(candidate["total_return_pct"])
                - float(baseline["total_return_pct"]),
                "delta_dd_vs_stage037_pp": float(candidate["max_dd_pct"])
                - float(baseline["max_dd_pct"]),
                "delta_sharpe_vs_stage037": float(candidate["sharpe"])
                - float(baseline["sharpe"]),
                "slippage_ratio_vs_stage037": float(candidate["total_slippage"])
                / float(baseline["total_slippage"]),
                **{f"gate_{key}": value for key, value in gates.items()},
                "all_full_period_gates_pass": all(gates.values()),
            }
        )
    return pd.DataFrame(rows)


def _equity_line_style(top_n: int, default_color: Any) -> dict[str, Any]:
    base = {
        "color": default_color,
        "linewidth": 1.25,
        "linestyle": "-",
        "alpha": 0.9,
        "zorder": 2,
    }
    highlights = {
        9: {"color": "#dc2626", "linewidth": 2.8, "alpha": 1.0, "zorder": 5},
        10: {"color": "#2563eb", "linewidth": 2.8, "alpha": 1.0, "zorder": 5},
    }
    return {**base, **highlights.get(top_n, {})}


def _plot_equity(curve: pd.DataFrame) -> bytes:
    fig, ax = plt.subplots(figsize=(15, 7))
    reference = curve[curve["experiment_arm"].astype(str).eq("REF")].sort_values("date")
    ax.plot(
        pd.to_datetime(reference["date"]),
        pd.to_numeric(reference["account_equity"]) / 10_000,
        color="black",
        linewidth=2.2,
        linestyle="--",
        label="Stage037 Top8 reference",
    )
    colors = plt.cm.viridis(np.linspace(0.05, 0.95, 11))
    for top_n, color in zip(range(9, 20), colors):
        frame = curve[curve["experiment_arm"].astype(str).eq(f"T{top_n}")].sort_values("date")
        label = f"Top{top_n}" + (" (=Top18)" if top_n == 19 else "")
        ax.plot(
            pd.to_datetime(frame["date"]),
            pd.to_numeric(frame["account_equity"]) / 10_000,
            label=label,
            **_equity_line_style(top_n, color),
        )
    ax.set_title(PLOT_TITLE)
    ax.set_ylabel("Equity (10k CNY)")
    ax.grid(alpha=0.22)
    ax.legend(ncol=3, fontsize=8)
    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=180)
    plt.close(fig)
    return buffer.getvalue()


def _plot_response(comparison: pd.DataFrame, baseline: pd.Series) -> bytes:
    x = comparison["requested_top_n"]
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), sharex=True)
    specs = (
        ("total_return_pct", "Total return (%)", float(baseline["total_return_pct"])),
        ("max_dd_pct", "Max drawdown (%)", float(baseline["max_dd_pct"])),
        ("sharpe", "Sharpe", float(baseline["sharpe"])),
        ("slippage_ratio_vs_stage037", "Slippage / Stage037", 1.0),
    )
    for ax, (column, title, reference) in zip(axes.flat, specs):
        ax.plot(x, comparison[column], marker="o", color="#2563eb")
        ax.axhline(reference, color="black", linestyle="--", linewidth=1, label="Stage037")
        top9_value = comparison.loc[comparison["requested_top_n"].eq(9), column].iloc[0]
        ax.scatter([9], [top9_value], marker="*", s=130, color="#dc2626", label="New Top9")
        ax.set_title(title)
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8)
    axes[-1, 0].set_xlabel("Requested AI TopN (fu fixed separately)")
    axes[-1, 1].set_xlabel("Requested AI TopN (fu fixed separately)")
    fig.suptitle("OFFLINE RESEARCH — Stage062 Top9 Boundary Check", fontsize=14)
    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=180)
    plt.close(fig)
    return buffer.getvalue()


def _report(summary: pd.DataFrame, comparison: pd.DataFrame, decision: dict[str, Any]) -> str:
    baseline = summary.set_index("experiment_arm").loc["REF"]
    lines = [
        "# Stage062 Stage037 AI Top9 全周期边界比较",
        "",
        REPORT_BANNER,
        "",
        f"区间：`{START.date()}` 至 `{END.date()}`。只新增Top9真引擎；Stage037参考与Top10–19逐值复用Stage061。",
        f"边界例外：{s61.PRE_AI_FU_BOUNDARY_NOTE}",
        "",
        f"参考 Stage037 Top8+fu：期末权益 `{baseline['end_equity']:,.2f}`，总收益 `{baseline['total_return_pct']:.4f}%`，最大回撤 `{baseline['max_dd_pct']:.4f}%`，Sharpe `{baseline['sharpe']:.6f}`。",
        "",
        "| 名义TopN | 实际总品种 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 交易数 | 胜率 | broker10峰值 | 全周期门 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: |",
    ]
    for row in comparison.itertuples(index=False):
        duplicate = "（与Top18重复）" if row.requested_top_n == 19 else ""
        lines.append(
            f"| {row.requested_top_n}{duplicate} | {row.actual_total_count} | {row.end_equity:,.2f} | "
            f"{row.total_return_pct:.4f}% | {row.max_dd_pct:.4f}% | {row.sharpe:.6f} | "
            f"{row.total_slippage:,.0f} | {int(row.total_trade_count)} | "
            f"{row.nonzero_daily_win_rate_pct:.4f}% | {row.max_broker10_margin_to_equity_pct:.4f}% | "
            f"{'PASS' if row.all_full_period_gates_pass else 'FAIL'} |"
        )
    top9 = comparison.loc[comparison["requested_top_n"].eq(9)].iloc[0]
    failed_gates = decision["top9_failed_gates"]
    lines.extend(
        [
            "",
            "## 审计边界",
            "",
            "- Top9是本阶段唯一新增真引擎；Top10–19与Stage037参考均逐值复用Stage061，不重新计算。",
            "- 55个正式AI月份中，53个月是严格模型Top9+fu；2026-03-31与2026-05-29为保留正式Top8，采用“锁定正式Top8，再按同月模型排名补足到9，最后加fu”。2026-04-30虽走同一锁定政策，但成员恰好等同严格Top9。全部使用同一eval_date评分，无未来数据。",
            "- 2026-03-31相对严格Top9纳入lh/sp并排除au/si；2026-05-29纳入rb并排除ru。完整source rank、ranking provenance与SHA见membership/ranking audit和decision。",
            f"- Top9相对Stage037收益差 `{top9['delta_return_vs_stage037_pp']:+.4f}pp`、回撤差 `{top9['delta_dd_vs_stage037_pp']:+.4f}pp`、Sharpe差 `{top9['delta_sharpe_vs_stage037']:+.6f}`、滑点比 `{top9['slippage_ratio_vs_stage037']:.4f}`。",
            f"- Top9失败门：`{failed_gates}`。冻结门不变，不因补测边界而事后放宽。",
            f"- 最终决策：`{decision['decision']}`。",
            "- 未连接CTP，未调用订单、发单或撤单API，未修改正式AI池、master或生产。",
            "",
            "## 反思",
            "",
            f"- 过拟合：{decision['overfitting_assessment']}",
            f"- 继续价值：{decision['continue_value_assessment']}",
            "",
        ]
    )
    return "\n".join(lines)


def _publish(
    frames: dict[str, pd.DataFrame],
    decision: dict[str, Any],
    report: str,
    equity_chart: bytes,
    response_chart: bytes,
) -> None:
    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".stage062.tmp-", dir=OUTPUT_DIR.parent))
    backup = OUTPUT_DIR.with_name(f".stage062.backup-{uuid4().hex}")
    try:
        for filename, frame in frames.items():
            frame.to_csv(temporary / filename, index=False, encoding="utf-8-sig")
        (temporary / DECISION_NAME).write_text(
            json.dumps(decision, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (temporary / REPORT_NAME).write_text(report, encoding="utf-8")
        (temporary / EQUITY_CHART_NAME).write_bytes(equity_chart)
        (temporary / RESPONSE_CHART_NAME).write_bytes(response_chart)
        if OUTPUT_DIR.exists():
            OUTPUT_DIR.rename(backup)
        temporary.rename(OUTPUT_DIR)
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def main() -> None:
    eligibility, membership, ranking_audit = _write_eligibility()
    identity = _preflight()
    summaries, curves, trades = _load_stage061_artifacts()
    metadata = s61.s56.s28.s513._metadata()
    print(f"[stage062] running Top9 {START.date()}->{END.date()}", flush=True)
    summaries[9], curves[9], trades[9] = _run_top9(metadata)
    summary = pd.concat(
        [summaries["REF"], *(summaries[top_n] for top_n in range(9, 20))],
        ignore_index=True,
        sort=False,
    )
    curve = pd.concat(
        [curves["REF"], *(curves[top_n] for top_n in range(9, 20))],
        ignore_index=True,
        sort=False,
    )
    all_trades = pd.concat(
        [trades[top_n] for top_n in range(9, 20)],
        ignore_index=True,
        sort=False,
    )
    _assert_coverage(summary, curve)
    comparison = _comparison(summary)
    top9 = comparison.loc[comparison["requested_top_n"].eq(9)].iloc[0]
    gate_columns = [column for column in comparison.columns if column.startswith("gate_")]
    failed_gates = [
        column.removeprefix("gate_")
        for column in gate_columns
        if not bool(top9[column])
    ]
    top9_pass = bool(top9["all_full_period_gates_pass"])
    if top9_pass:
        decision_name = "offline_top9_fullperiod_pass_requires_multicycle_not_promotion"
        continue_value = "有限：Top9通过全周期冻结门，只允许一次预声明多周期验证；不再继续向更窄TopN扫描。"
    elif failed_gates == ["slippage_le_105pct_of_stage037"]:
        decision_name = "offline_top9_cost_only_fail_keep_stage037"
        continue_value = "有限：Top9仅成本门失败，只能另立容量/成本归一化验证；不再继续扫TopN。"
    else:
        decision_name = "offline_top9_fullperiod_fail_keep_stage037"
        continue_value = "无：Top9未通过冻结全周期门，本轮边界补测结束，不再继续扫TopN。"
    decision = {
        "line_id": LINE_ID,
        "stage": STAGE,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "base_master_commit": BASE_MASTER_COMMIT,
        "base_ruleset_version": BASE_RULESET_VERSION,
        "base_stage061_commit": BASE_STAGE061_COMMIT,
        "candidate_version": candidate_cfg.CANDIDATE_VERSION,
        "period": {"start": str(START.date()), "end": str(END.date())},
        "hypothesis": "在Stage061宽度响应左边界补充Top9，判断Top10的优势是局部平台还是边界偶然。",
        "frozen_scope": {
            "requested_top_ns": list(range(9, 20)),
            "new_engine_top_ns": list(NEW_ENGINE_TOP_NS),
            "reused_stage061_top_ns": list(REUSED_STAGE061_TOP_NS),
            "fixed_fu": FU_PRODUCT,
            "top19_duplicate_of_top18": True,
            "membership_only_dates": sorted(s61.MEMBERSHIP_ONLY_DATES),
            "membership_only_policy": "lock formal Top8 then fill to 9 from same-eval-date model ranking, then append fu",
            "strict_model_top9_match_month_count": int(
                membership["strict_model_top9_match"].astype(bool).sum()
            ),
            "strict_model_top9_mismatch_dates": membership.loc[
                ~membership["strict_model_top9_match"].astype(bool), "eval_date"
            ].astype(str).tolist(),
        },
        "source_identity": identity,
        "top9_all_full_period_gates_pass": top9_pass,
        "top9_failed_gates": failed_gates,
        "formal_production_ac_compliant": False,
        "promotion_permitted": False,
        "promote": False,
        "decision": decision_name,
        "overfitting_assessment": "高：Top9是在看到Top10位于上一轮最优边界后追加，存在明显后验边界扩展；只能作为一次性敏感性证据。",
        "continue_value_assessment": continue_value,
        "order_api_called_count": 0,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
    }
    frames = {
        SUMMARY_NAME: summary,
        COMPARISON_NAME: comparison,
        CURVE_NAME: curve,
        TRADES_NAME: all_trades,
        ELIGIBILITY_NAME: eligibility,
        MEMBERSHIP_AUDIT_NAME: membership,
        RANKING_AUDIT_NAME: ranking_audit,
    }
    baseline = summary.set_index("experiment_arm").loc["REF"]
    report = _report(summary, comparison, decision)
    _publish(
        frames,
        decision,
        report,
        _plot_equity(curve),
        _plot_response(comparison, baseline),
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
