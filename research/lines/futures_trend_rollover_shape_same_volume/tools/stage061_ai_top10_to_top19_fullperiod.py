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

import qmt_roll_candidate_stage061_ai_topn_width_config as candidate_cfg  # noqa: E402
from main_contract_mapping import load_product_universe_symbols  # noqa: E402
import stage056_stage037_ai_top14_plus_fu_ac as s56  # noqa: E402


LINE_ID = "futures_trend_rollover_shape_same_volume"
STAGE = "Stage061"
BASE_MASTER_COMMIT = s56.BASE_MASTER_COMMIT
BASE_RULESET_VERSION = s56.BASE_RULESET_VERSION
BASE_RELEASE_ID = "m0016_20260829T034012+0800_374df2d52e4f"
BASE_SOURCE_COMMIT = "374df2d52e4f17220c5e2d4cae76f50d45bec47d"
START = pd.Timestamp("2018-01-01")
EXPECTED_FIRST_TRADING_DAY = pd.Timestamp("2018-01-02")
END = pd.Timestamp("2026-08-28")
FU_PRODUCT = "fu.SHFE"
RANKED_UNIVERSE_COUNT = 18
TOP_NS = tuple(range(10, 20))
REUSED_TOP_NS = {14: "stage056_top14", 19: "stage061_top18_duplicate"}
ENGINE_RUN_TOP_NS = (10, 11, 12, 13, 15, 16, 17, 18)
MEMBERSHIP_ONLY_DATES = s56.MEMBERSHIP_ONLY_DATES

LINE_DIR = Path(__file__).resolve().parents[1]
STAGE056_DIR = s56.OUTPUT_DIR
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage061_ai_top10_to_top19_fullperiod"
CHECKPOINT_DIR = PROJECT_DIR / ".tools" / "stage061_ai_top10_to_top19_checkpoints"
ELIGIBILITY_WORK_DIR = CHECKPOINT_DIR / "eligibility"

SUMMARY_NAME = "stage061_summary.csv"
COMPARISON_NAME = "stage061_comparison.csv"
CURVE_NAME = "stage061_equity_curve.csv"
TRADES_NAME = "stage061_trades.csv"
ELIGIBILITY_NAME = "stage061_eligibility.csv"
MEMBERSHIP_AUDIT_NAME = "stage061_membership_audit.csv"
DECISION_NAME = "stage061_decision.json"
REPORT_NAME = "stage061_report.md"
EQUITY_CHART_NAME = "stage061_equity_top10_top19.png"
RESPONSE_CHART_NAME = "stage061_metric_response.png"
PLOT_TITLE = "OFFLINE RESEARCH — Stage061 AI Top10–Top19 Full Period"
REPORT_BANNER = "> **离线研究，非当前实盘策略；不得据此发单或自动晋升。**"
PRE_AI_FU_BOUNDARY_NOTE = (
    "`fu.SHFE`只在55个正式AI月度快照中固定放行；2019-12-31的static18前AI边界保持原18品种且不含fu。"
)


def _arm(top_n: int) -> dict[str, Any]:
    actual_ranked = min(top_n, RANKED_UNIVERSE_COUNT)
    return {
        "arm": f"T{top_n}",
        "requested_top_n": top_n,
        "actual_ranked_count": actual_ranked,
        "actual_total_count": actual_ranked + 1,
        "profile": f"stage061_top{top_n}_plus_fu",
        "label": f"Top{top_n}+fu（实际{actual_ranked + 1}品种）",
        "plot_label": f"Top{top_n}" + (" (=Top18)" if top_n == 19 else ""),
    }


ARMS = tuple(_arm(top_n) for top_n in TOP_NS)
REFERENCE = {
    "arm": "REF",
    "requested_top_n": 8,
    "actual_ranked_count": 8,
    "actual_total_count": 9,
    "profile": "stage061_reference_stage037_top8_plus_fu",
    "label": "参考：Stage037 Top8+fu（9品种）",
    "plot_label": "Stage037 Top8 reference",
}


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


def _strategy(top_n: int) -> str:
    return f"ai_top{top_n}_plus_fu_width_sweep"


def _eligibility_path(top_n: int) -> Path:
    return ELIGIBILITY_WORK_DIR / f"stage061_top{top_n}_eligibility.csv"


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
            "stage061_stage037_identity_mismatch:"
            f"actual={actual}:expected={expected}:remote={remote_master}"
        )
    production_matches = all(
        production_identity.get(key) == value for key, value in expected.items()
    )
    return {
        "research_protocol": "explicit_stage037_ai_top10_to_top19_offline_width_sweep",
        "checkout_stage037_identity_pass": True,
        "production_identity_matches_stage037": bool(production_matches),
        "formal_production_ac_compliant": False,
        "promotion_permitted": False,
    }


def select_topn_plus_fu(
    ranking: pd.DataFrame,
    *,
    requested_top_n: int,
    locked_non_fu: Iterable[str] = (),
) -> pd.DataFrame:
    if requested_top_n not in TOP_NS:
        raise ValueError(f"stage061_top_n_out_of_range:{requested_top_n}")
    ranked = s56._normalise_ranking(ranking)
    if ranked["eval_date"].nunique() != 1:
        raise RuntimeError("stage061_ranking_must_have_one_eval_date")
    if ranked["product_vt_symbol"].duplicated().any():
        raise RuntimeError("stage061_duplicate_ranking_product")
    non_fu = ranked[~ranked["product_vt_symbol"].eq(FU_PRODUCT)].copy()
    if len(non_fu) != RANKED_UNIVERSE_COUNT:
        raise RuntimeError(f"stage061_ranked_universe_count:{len(non_fu)}")
    actual_ranked = min(requested_top_n, RANKED_UNIVERSE_COUNT)
    locked = tuple(dict.fromkeys(str(product) for product in locked_non_fu))
    if len(locked) > actual_ranked or set(locked) - set(non_fu["product_vt_symbol"]):
        raise RuntimeError(f"stage061_invalid_locked_products:{locked}")
    indexed = non_fu.set_index("product_vt_symbol", drop=False)
    fill = non_fu[~non_fu["product_vt_symbol"].isin(locked)].head(
        actual_ranked - len(locked)
    )
    selected = pd.concat(
        [indexed.loc[list(locked)].copy() if locked else non_fu.iloc[0:0].copy(), fill],
        ignore_index=True,
    )
    if len(selected) != actual_ranked or selected["product_vt_symbol"].nunique() != actual_ranked:
        raise RuntimeError("stage061_selected_member_contract_failed")
    eval_date = str(ranked["eval_date"].iloc[0])
    score_type = (
        f"membership_locked_top{requested_top_n}_plus_fixed_fu"
        if locked
        else f"ai_probability_top{requested_top_n}_plus_fixed_fu"
    )
    rows = [
        {
            "strategy": _strategy(requested_top_n),
            "score_type": score_type,
            "eval_date": eval_date,
            "product_vt_symbol": str(row.product_vt_symbol),
            "score": float(row.score),
            "score_rank": rank,
            "top_n": actual_ranked + 1,
        }
        for rank, row in enumerate(selected.itertuples(index=False), start=1)
    ]
    min_score = min(row["score"] for row in rows)
    rows.append(
        {
            "strategy": _strategy(requested_top_n),
            "score_type": score_type,
            "eval_date": eval_date,
            "product_vt_symbol": FU_PRODUCT,
            "score": min_score - 1e-6,
            "score_rank": actual_ranked + 1,
            "top_n": actual_ranked + 1,
        }
    )
    return pd.DataFrame(rows, columns=s56.ELIGIBILITY_COLUMNS)


def build_candidate_eligibility(
    formal: pd.DataFrame,
    ranking_source: pd.DataFrame,
    *,
    requested_top_n: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    formal = formal.loc[:, s56.ELIGIBILITY_COLUMNS].copy()
    formal["eval_date"] = pd.to_datetime(formal["eval_date"], errors="raise").dt.date.astype(str)
    ranking_source = s56._normalise_ranking(ranking_source)
    pre_ai = s56.preserve_pre_ai_boundary(formal)
    pre_ai["strategy"] = _strategy(requested_top_n)
    rows = [pre_ai]
    audits: list[dict[str, Any]] = []
    model_dates = sorted(date for date in formal["eval_date"].unique() if date != "2019-12-31")
    for eval_date in model_dates:
        formal_month = formal[formal["eval_date"].eq(eval_date)].sort_values("score_rank")
        formal_non_fu = tuple(
            formal_month.loc[
                ~formal_month["product_vt_symbol"].eq(FU_PRODUCT), "product_vt_symbol"
            ].astype(str)
        )
        ranking_month = ranking_source[ranking_source["eval_date"].eq(eval_date)].copy()
        locked = formal_non_fu if eval_date in MEMBERSHIP_ONLY_DATES else ()
        selected = select_topn_plus_fu(
            ranking_month,
            requested_top_n=requested_top_n,
            locked_non_fu=locked,
        )
        selected_non_fu = set(
            selected.loc[
                ~selected["product_vt_symbol"].eq(FU_PRODUCT), "product_vt_symbol"
            ].astype(str)
        )
        formal_preserved = set(formal_non_fu).issubset(selected_non_fu)
        if not formal_preserved:
            raise RuntimeError(f"stage061_formal_top8_not_preserved:{requested_top_n}:{eval_date}")
        rows.append(selected)
        audits.append(
            {
                "requested_top_n": requested_top_n,
                "eval_date": eval_date,
                "actual_ranked_count": len(selected_non_fu),
                "actual_total_count": int(selected["product_vt_symbol"].nunique()),
                "formal_top8_preserved": formal_preserved,
                "fixed_fu_present": FU_PRODUCT in set(selected["product_vt_symbol"]),
                "member_signature": ",".join(sorted(selected["product_vt_symbol"].astype(str))),
            }
        )
    result = pd.concat(rows, ignore_index=True)
    result["requested_top_n"] = requested_top_n
    result.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    result.reset_index(drop=True, inplace=True)
    return result, pd.DataFrame(audits)


def _write_eligibilities() -> tuple[pd.DataFrame, pd.DataFrame, dict[int, Path]]:
    formal = pd.read_csv(s56.FORMAL_ELIGIBILITY_PATH)
    ranking_source, _ = s56.build_full_ranking_source()
    ELIGIBILITY_WORK_DIR.mkdir(parents=True, exist_ok=True)
    eligibilities, audits, paths = [], [], {}
    for top_n in TOP_NS:
        eligibility, audit = build_candidate_eligibility(
            formal, ranking_source, requested_top_n=top_n
        )
        path = _eligibility_path(top_n)
        eligibility.drop(columns=["requested_top_n"]).to_csv(
            path, index=False, encoding="utf-8-sig"
        )
        paths[top_n] = path
        eligibilities.append(eligibility)
        audits.append(audit)
    combined = pd.concat(eligibilities, ignore_index=True, sort=False)
    membership = pd.concat(audits, ignore_index=True, sort=False)
    signatures = membership.pivot(index="eval_date", columns="requested_top_n", values="member_signature")
    if not signatures[18].equals(signatures[19]):
        raise RuntimeError("stage061_top18_top19_membership_not_identical")
    return combined, membership, paths


def _preflight(paths: dict[int, Path]) -> dict[str, Any]:
    checkout = asdict(s56.assert_official_checkout_matches_active_material(PROJECT_DIR))
    production = asdict(
        s56.assert_official_checkout_matches_active_material(s56.PRODUCTION_ROOT)
    )
    remote_master = _git("rev-parse", "origin/master")
    evidence = _assert_offline_identity_contract(checkout, production, remote_master)
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASE_MASTER_COMMIT, "HEAD"],
        cwd=PROJECT_DIR,
        check=True,
    )
    for top_n, path in paths.items():
        if set(candidate_cfg.override_diff(top_n, path)) != {
            "ai_product_pool_eligibility_path",
            "ai_product_pool_strategy",
        }:
            raise RuntimeError(f"stage061_override_scope_drift:{top_n}")
    universe_path = Path(
        s56.live_cfg.build_official_live_strategy_overrides()["product_universe_csv_path"]
    )
    products = load_product_universe_symbols(universe_path)
    if len(products) != 19 or len(set(products)) != 19:
        raise RuntimeError(f"stage061_product_universe_contract_failed:{products}")
    return {
        **evidence,
        "checkout_identity": checkout,
        "production_identity": production,
        "checkout_head": _git("rev-parse", "HEAD"),
        "remote_master": remote_master,
        "database_path": str(s56.DATABASE_PATH.resolve()),
        "database_sha256": _file_sha256(s56.DATABASE_PATH),
        "product_universe_path": str(universe_path.resolve()),
        "product_universe_sha256": _file_sha256(universe_path),
        "ranked_non_fu_count": RANKED_UNIVERSE_COUNT,
        "configured_total_product_count": len(products),
    }


def _relabel(frame: pd.DataFrame, arm: dict[str, Any]) -> pd.DataFrame:
    result = frame.copy()
    result["experiment_arm"] = arm["arm"]
    result["requested_top_n"] = arm["requested_top_n"]
    result["actual_ranked_count"] = arm["actual_ranked_count"]
    result["actual_total_count"] = arm["actual_total_count"]
    for column in ("profile", "variant", "arm"):
        if column in result.columns:
            result[column] = arm["profile"]
    if "label" in result.columns:
        result["label"] = arm["label"]
    return result


def _assert_relabel_preserves_payload(
    source: pd.DataFrame,
    target: pd.DataFrame,
    *,
    context: str,
) -> None:
    identity_columns = {
        "experiment_arm",
        "requested_top_n",
        "actual_ranked_count",
        "actual_total_count",
        "profile",
        "variant",
        "arm",
        "label",
    }
    payload_columns = [
        column for column in source.columns if column not in identity_columns
    ]
    missing_payload_columns = sorted(set(payload_columns) - set(target.columns))
    if missing_payload_columns:
        raise RuntimeError(
            f"stage061_reuse_payload_columns_drift:{context}:"
            f"{missing_payload_columns}"
        )
    left = source[payload_columns].reset_index(drop=True)
    right = target[payload_columns].reset_index(drop=True)
    if not left.equals(right):
        raise RuntimeError(f"stage061_reuse_payload_drift:{context}")


def _load_reference_and_top14() -> tuple[dict[int | str, pd.DataFrame], dict[int | str, pd.DataFrame], dict[int, pd.DataFrame]]:
    source_summary = pd.read_csv(STAGE056_DIR / s56.SUMMARY_NAME)
    source_curve = pd.read_csv(STAGE056_DIR / s56.CURVE_NAME)
    source_trades = pd.read_csv(STAGE056_DIR / s56.TRADES_NAME)
    source_reference_summary = source_summary[
        source_summary["experiment_arm"].astype(str).eq("A")
    ]
    source_reference_curve = source_curve[
        source_curve["experiment_arm"].astype(str).eq("A")
    ]
    reference_summary = _relabel(source_reference_summary, REFERENCE)
    reference_curve = _relabel(source_reference_curve, REFERENCE)
    top14_arm = ARMS[4]
    source_top14_summary = source_summary[
        source_summary["experiment_arm"].astype(str).eq("C")
    ]
    source_top14_curve = source_curve[
        source_curve["experiment_arm"].astype(str).eq("C")
    ]
    source_top14_trades = source_trades[
        source_trades["experiment_arm"].astype(str).eq("C")
    ]
    top14_summary = _relabel(source_top14_summary, top14_arm)
    top14_curve = _relabel(source_top14_curve, top14_arm)
    top14_trades = _relabel(source_top14_trades, top14_arm)
    for source, target, context in (
        (source_reference_summary, reference_summary, "reference_summary"),
        (source_reference_curve, reference_curve, "reference_curve"),
        (source_top14_summary, top14_summary, "top14_summary"),
        (source_top14_curve, top14_curve, "top14_curve"),
        (source_top14_trades, top14_trades, "top14_trades"),
    ):
        _assert_relabel_preserves_payload(source, target, context=context)
    return (
        {"REF": reference_summary, 14: top14_summary},
        {"REF": reference_curve, 14: top14_curve},
        {14: top14_trades},
    )


def _contract_hash(top_n: int, eligibility_path: Path) -> str:
    digest = sha256()
    for path in (
        Path(__file__),
        Path(candidate_cfg.__file__),
        Path(s56.__file__),
        PROJECT_DIR / "examples" / "portfolio_backtesting" / "qmt_roll_portfolio_strategy.py",
        eligibility_path,
    ):
        digest.update(path.read_bytes())
    digest.update(_file_sha256(s56.DATABASE_PATH).encode())
    digest.update(f"{top_n}:{START.date()}:{END.date()}".encode())
    return digest.hexdigest()


def _checkpoint_dir(top_n: int) -> Path:
    return CHECKPOINT_DIR / f"top{top_n}"


def _load_checkpoint(top_n: int, eligibility_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame] | None:
    directory = _checkpoint_dir(top_n)
    metadata_path = directory / "metadata.json"
    if not metadata_path.exists():
        return None
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("contract_sha256") != _contract_hash(top_n, eligibility_path):
        return None
    return (
        pd.read_csv(directory / "summary.csv"),
        pd.read_csv(directory / "curve.csv"),
        pd.read_csv(directory / "trades.csv"),
    )


def _save_checkpoint(
    top_n: int,
    eligibility_path: Path,
    summary: pd.DataFrame,
    curve: pd.DataFrame,
    trades: pd.DataFrame,
) -> None:
    directory = _checkpoint_dir(top_n)
    temporary = Path(tempfile.mkdtemp(prefix=f".stage061-top{top_n}-", dir=CHECKPOINT_DIR))
    backup = directory.with_name(f".{directory.name}.backup-{uuid4().hex}")
    try:
        summary.to_csv(temporary / "summary.csv", index=False, encoding="utf-8-sig")
        curve.to_csv(temporary / "curve.csv", index=False, encoding="utf-8-sig")
        trades.to_csv(temporary / "trades.csv", index=False, encoding="utf-8-sig")
        (temporary / "metadata.json").write_text(
            json.dumps(
                {
                    "top_n": top_n,
                    "contract_sha256": _contract_hash(top_n, eligibility_path),
                    "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        if directory.exists():
            directory.rename(backup)
        temporary.rename(directory)
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def _run_arm(
    top_n: int, eligibility_path: Path, metadata: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cached = _load_checkpoint(top_n, eligibility_path)
    if cached is not None:
        print(f"[stage061] reuse checkpoint Top{top_n}", flush=True)
        return cached
    arm = ARMS[top_n - TOP_NS[0]]
    original_builder = s56.s28.s901.build_official_live_strategy_overrides
    try:
        s56.s28.s901.build_official_live_strategy_overrides = lambda: candidate_cfg.build_candidate_overrides(
            top_n, eligibility_path
        )
        combined, frames, live_spec = s56.s28.s901._run_live_c9(metadata, START, END)
    finally:
        s56.s28.s901.build_official_live_strategy_overrides = original_builder
    capital = replace(live_spec.capital, variant=arm["profile"], label=arm["label"])
    metric_spec = replace(live_spec, capital=capital, profile=arm["profile"])
    summary, curve = s56.s28.s827._metric(
        {"profile": arm["profile"], "spec": metric_spec}, combined
    )
    summary = _relabel(summary, arm)
    summary["window_name"] = "full_2018_20260828"
    summary["window_label"] = "2018-01-01 independent start to 2026-08-28"
    curve = _relabel(curve, arm)
    trades = _relabel(frames.get("trades", pd.DataFrame()), arm)
    _save_checkpoint(top_n, eligibility_path, summary, curve, trades)
    return summary, curve, trades


def _duplicate_top19(
    top18_summary: pd.DataFrame,
    top18_curve: pd.DataFrame,
    top18_trades: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    arm = ARMS[-1]
    duplicated = (
        _relabel(top18_summary, arm),
        _relabel(top18_curve, arm),
        _relabel(top18_trades, arm),
    )
    for source, target, context in zip(
        (top18_summary, top18_curve, top18_trades),
        duplicated,
        ("top19_summary", "top19_curve", "top19_trades"),
    ):
        _assert_relabel_preserves_payload(source, target, context=context)
    return duplicated


def _assert_coverage(summary: pd.DataFrame, curve: pd.DataFrame) -> None:
    expected_arms = {"REF", *(f"T{top_n}" for top_n in TOP_NS)}
    if len(summary) != len(expected_arms) or set(summary["experiment_arm"].astype(str)) != expected_arms:
        raise RuntimeError("stage061_arm_identity_failed")
    reference: pd.DatetimeIndex | None = None
    for arm in ["REF", *(f"T{top_n}" for top_n in TOP_NS)]:
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
            raise RuntimeError(f"stage061_full_period_coverage_failed:{arm}")


def _full_period_gates(values: dict[str, Any]) -> dict[str, bool]:
    return {
        "return_not_lower_than_stage037": bool(
            values["candidate_total_return_pct"] >= values["baseline_total_return_pct"]
        ),
        "drawdown_worsening_le_2pp": bool(
            values["baseline_max_dd_pct"] - values["candidate_max_dd_pct"] <= 2.0
        ),
        "sharpe_not_lower_by_more_than_002": bool(
            values["candidate_sharpe"] >= values["baseline_sharpe"] - 0.02
        ),
        "slippage_le_105pct_of_stage037": bool(
            values["candidate_total_slippage"] <= values["baseline_total_slippage"] * 1.05
        ),
        "account_survival_pass": bool(values["candidate_account_survival_pass"]),
        "broker10_days_over_100_not_worse": bool(
            values["candidate_days_over_100pct"] <= values["baseline_days_over_100pct"]
        ),
    }


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    indexed = summary.set_index("experiment_arm")
    baseline = indexed.loc["REF"]
    rows = []
    for arm in ARMS:
        candidate = indexed.loc[arm["arm"]]
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
                "requested_top_n": arm["requested_top_n"],
                "actual_ranked_count": arm["actual_ranked_count"],
                "actual_total_count": arm["actual_total_count"],
                "duplicate_of_top_n": 18 if arm["requested_top_n"] == 19 else "",
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


def _cost_only_fail_top_ns(comparison: pd.DataFrame) -> list[int]:
    non_cost_gate_columns = [
        column
        for column in comparison.columns
        if column.startswith("gate_")
        and column != "gate_slippage_le_105pct_of_stage037"
    ]
    mask = (
        comparison[non_cost_gate_columns].all(axis=1)
        & ~comparison["gate_slippage_le_105pct_of_stage037"]
    )
    return comparison.loc[mask, "requested_top_n"].astype(int).tolist()


def _continue_value_assessment(comparison: pd.DataFrame) -> str:
    passing = comparison.loc[
        comparison["all_full_period_gates_pass"] & comparison["requested_top_n"].ne(19),
        "requested_top_n",
    ].astype(int).tolist()
    if passing:
        return "有限：通过全周期硬门且处于相邻稳定平台的TopN才值得进入预声明多周期。"
    cost_only = _cost_only_fail_top_ns(comparison)
    if cost_only:
        return (
            f"有限：TopN {cost_only} 仅失败绝对总滑点预算，允许另立预声明的容量/成本归一化验证；"
            "冻结105%门不变、不得继续扫TopN或直接晋升。"
        )
    return "无：没有TopN接近通过全周期硬门，不应再扫描宽度或进入多周期。"


def _plot_equity(curve: pd.DataFrame) -> bytes:
    fig, ax = plt.subplots(figsize=(15, 7))
    reference = curve[curve["experiment_arm"].astype(str).eq("REF")].sort_values("date")
    ax.plot(
        pd.to_datetime(reference["date"]),
        pd.to_numeric(reference["account_equity"]) / 10_000,
        color="black",
        linewidth=2.2,
        linestyle="--",
        label=REFERENCE["plot_label"],
    )
    colors = plt.cm.viridis(np.linspace(0.05, 0.95, len(ARMS)))
    for arm, color in zip(ARMS, colors):
        frame = curve[curve["experiment_arm"].astype(str).eq(arm["arm"])].sort_values("date")
        ax.plot(
            pd.to_datetime(frame["date"]),
            pd.to_numeric(frame["account_equity"]) / 10_000,
            color=color,
            linewidth=1.25,
            alpha=0.9,
            label=arm["plot_label"],
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
        ax.scatter([19], [comparison.loc[comparison["requested_top_n"].eq(19), column].iloc[0]],
                   marker="x", s=90, color="#dc2626", label="Top19=Top18")
        ax.set_title(title)
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8)
    axes[-1, 0].set_xlabel("Requested AI TopN (fu fixed separately)")
    axes[-1, 1].set_xlabel("Requested AI TopN (fu fixed separately)")
    fig.suptitle("OFFLINE RESEARCH — Stage061 TopN Width Response", fontsize=14)
    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=180)
    plt.close(fig)
    return buffer.getvalue()


def _report(summary: pd.DataFrame, comparison: pd.DataFrame, decision: dict[str, Any]) -> str:
    indexed = summary.set_index("experiment_arm")
    baseline = indexed.loc["REF"]
    lines = [
        "# Stage061 Stage037 AI Top10–Top19 全周期宽度比较",
        "",
        REPORT_BANNER,
        "",
        f"区间：`{START.date()}` 至 `{END.date()}`。AI过滤保持开启，唯一行为变量是月度AI排名池宽度；正式AI月度快照固定放行 `fu.SHFE`。",
        f"边界例外：{PRE_AI_FU_BOUNDARY_NOTE}",
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
    passing = comparison.loc[comparison["all_full_period_gates_pass"], "requested_top_n"].tolist()
    cost_only = _cost_only_fail_top_ns(comparison)
    lines.extend(
        [
            "",
            "## 审计边界",
            "",
            "- Top19的历史排名输入只有18个非fu，因此逐月成员与Top18完全相同；Top19复用Top18，不计作独立证据。",
            "- Top14逐值复用Stage056已验证全周期结果；其余TopN均使用同一Stage037真引擎和独立15万元冷启动。",
            f"- 通过单版本全周期硬门的名义TopN：`{passing}`。即使存在PASS，也只进入多周期候选清单，不允许从10个结果里直接挑冠军晋升。",
            f"- 仅失败绝对总滑点门的TopN：`{cost_only}`。这表示冻结成本预算失败，不表示其收益、回撤或Sharpe劣化；只能另立容量/成本归一化问题，不能事后改门。",
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
    temporary = Path(tempfile.mkdtemp(prefix=".stage061.tmp-", dir=OUTPUT_DIR.parent))
    backup = OUTPUT_DIR.with_name(f".stage061.backup-{uuid4().hex}")
    try:
        for filename, frame in frames.items():
            frame.to_csv(temporary / filename, index=False, encoding="utf-8-sig")
        (temporary / DECISION_NAME).write_text(
            json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
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
    eligibility, membership, paths = _write_eligibilities()
    identity = _preflight(paths)
    summaries, curves, trades = _load_reference_and_top14()
    metadata = s56.s28.s513._metadata()
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    for top_n in ENGINE_RUN_TOP_NS:
        print(f"[stage061] running Top{top_n} {START.date()}->{END.date()}", flush=True)
        summary, curve, arm_trades = _run_arm(top_n, paths[top_n], metadata)
        summaries[top_n], curves[top_n], trades[top_n] = summary, curve, arm_trades
    summaries[19], curves[19], trades[19] = _duplicate_top19(
        summaries[18], curves[18], trades[18]
    )
    summary = pd.concat(
        [summaries["REF"], *(summaries[top_n] for top_n in TOP_NS)],
        ignore_index=True,
        sort=False,
    )
    curve = pd.concat(
        [curves["REF"], *(curves[top_n] for top_n in TOP_NS)],
        ignore_index=True,
        sort=False,
    )
    all_trades = pd.concat(
        [trades[top_n] for top_n in TOP_NS], ignore_index=True, sort=False
    )
    _assert_coverage(summary, curve)
    comparison = _comparison(summary)
    passing = comparison.loc[
        comparison["all_full_period_gates_pass"] & comparison["requested_top_n"].ne(19),
        "requested_top_n",
    ].astype(int).tolist()
    decision = {
        "line_id": LINE_ID,
        "stage": STAGE,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "base_master_commit": BASE_MASTER_COMMIT,
        "base_ruleset_version": BASE_RULESET_VERSION,
        "candidate_version": candidate_cfg.CANDIDATE_VERSION,
        "period": {"start": str(START.date()), "end": str(END.date())},
        "hypothesis": "在保持Stage037与AI排序模型不变时，观察TopN扩大后的风险收益和容量响应是否形成稳定平台。",
        "frozen_scope": {
            "requested_top_ns": list(TOP_NS),
            "fixed_fu": FU_PRODUCT,
            "ranked_non_fu_available": RANKED_UNIVERSE_COUNT,
            "top19_duplicate_of_top18": True,
            "engine_run_top_ns": list(ENGINE_RUN_TOP_NS),
            "reused_top_ns": REUSED_TOP_NS,
        },
        "source_identity": identity,
        "full_period_gate_pass_top_ns_excluding_duplicate": passing,
        "cost_only_fail_top_ns": _cost_only_fail_top_ns(comparison),
        "formal_production_ac_compliant": False,
        "promotion_permitted": False,
        "promote": False,
        "decision": (
            "offline_width_sweep_has_fullperiod_shortlist_requires_multicycle"
            if passing
            else "offline_width_sweep_no_fullperiod_candidate_keep_stage037"
        ),
        "overfitting_assessment": "高：同时观察10个相邻TopN存在多重比较；结果只能用于判断宽度响应平台，不能后验挑单点冠军。",
        "continue_value_assessment": _continue_value_assessment(comparison),
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
