from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from typing import Any, Iterable
from uuid import uuid4

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
PRIMARY_CHECKOUT = Path("/Users/bytedance/Desktop/person/vnpy")
PRODUCTION_ROOT = Path("/Users/bytedance/Desktop/person/vnpy_production_live")
sys.path.insert(0, str(PORTFOLIO_DIR))

import qmt_roll_candidate_stage056_stage037_ai_top14_plus_fu_config as candidate_cfg  # noqa: E402
import qmt_roll_official_live_config as live_cfg  # noqa: E402
from qmt_roll_official_baseline_identity import (  # noqa: E402
    assert_official_checkout_matches_active_material,
)
import stage028_q_delayed_rollover_abc as s28  # noqa: E402


LINE_ID = "futures_trend_rollover_shape_same_volume"
STAGE = "Stage056"
BASE_MASTER_COMMIT = "a7d8599e9d895aa6fc7c73b25ef7f2e48d4e4c14"
BASE_RULESET_VERSION = "stage037_stage034_long_short_mirror_hard_block_v1"
CANDIDATE_AI_STRATEGY = candidate_cfg.CANDIDATE_AI_STRATEGY
FU_PRODUCT = "fu.SHFE"
MODEL_NON_FU_COUNT = 14
TOTAL_PRODUCT_COUNT = 15
START = pd.Timestamp("2018-01-01")
EXPECTED_FIRST_TRADING_DAY = pd.Timestamp("2018-01-02")
END = pd.Timestamp("2026-08-28")

LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage056_stage037_ai_top14_plus_fu"
FORMAL_ELIGIBILITY_PATH = Path(live_cfg.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH).resolve()
MARKET_RANKING_PATH = (
    PRIMARY_CHECKOUT
    / "examples"
    / "portfolio_backtesting"
    / "backtest_outputs"
    / "qmt_roll_ai_product_suitability_market_walkforward_predictions_product_suitability_market_wf_v2.csv"
)
STAGE189_RANKING_PATH = (
    PRIMARY_CHECKOUT
    / "examples"
    / "portfolio_backtesting"
    / "backtest_outputs"
    / "qmt_roll_stage189_ai_product_pool_backfill_multimonth_pool_stage189_ai_product_pool_backfill_multimonth_v1.csv"
)
STAGE183_SOURCE_DIR = PRIMARY_CHECKOUT / "examples" / "portfolio_backtesting" / "backtest_outputs"
STAGE183_POSITION_CHANGES_PATH = (
    STAGE183_SOURCE_DIR / "qmt_roll_stage183_ai_source_floor35_position_changes_2020_2026_04.csv"
)
STAGE183_ENTRY_SNAPSHOTS_PATH = (
    STAGE183_SOURCE_DIR
    / "qmt_roll_stage183_ai_source_floor35_entry_candidate_snapshots_2020_2026_04.csv"
)
DATABASE_PATH = PROJECT_DIR / ".vntrader" / "database.db"
LATEST_RANKING_PATH = FORMAL_ELIGIBILITY_PATH.parent / "latest_pool.csv"
MAPPING_PATH = (
    PORTFOLIO_DIR
    / "backtest_outputs"
    / "tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv"
)
FULL_MINUTE_BARS_PATH = (
    PORTFOLIO_DIR
    / "backtest_outputs"
    / "qmt_roll_stage861_stage860_full_visual_atlas_full_minute_bars_stage861_stage860_full_visual_atlas_v1.csv"
)
JUNE_EVAL_DATE = "2026-06-30"
MEMBERSHIP_ONLY_DATES = {"2026-03-31", "2026-04-30", "2026-05-29"}

ELIGIBILITY_COLUMNS = [
    "strategy",
    "score_type",
    "eval_date",
    "product_vt_symbol",
    "score",
    "score_rank",
    "top_n",
]

ARMS = (
    {
        "arm": "A",
        "profile": "stage056_A_master_m0016_stage037_top8_plus_fu",
        "label": "A: master m0016 Stage037 Top8+fu（9品种）",
        "plot_label": "A master m0016 Stage037 Top8+fu",
        "color": "#2563eb",
    },
    {
        "arm": "C",
        "profile": "stage056_C_stage037_top14_plus_fu",
        "label": "C: Stage037 Top14+fu（15品种）",
        "plot_label": "C Stage037 Top14+fu",
        "color": "#16a34a",
    },
)

SUMMARY_NAME = "stage056_summary.csv"
COMPARISON_NAME = "stage056_comparison.csv"
CURVE_NAME = "stage056_equity_curve.csv"
TRADES_NAME = "stage056_trades.csv"
ATTRIBUTION_NAME = "stage056_added_product_trade_attribution.csv"
ELIGIBILITY_NAME = "stage056_candidate_eligibility.csv"
MEMBERSHIP_AUDIT_NAME = "stage056_membership_audit.csv"
RANKING_AUDIT_NAME = "stage056_full_ranking_audit.csv"
DECISION_NAME = "stage056_decision.json"
REPORT_NAME = "stage056_report.md"
CHART_NAME = "stage056_equity_ac.png"


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _database_latest_daily_date(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "select max(datetime) from dbbardata where interval='d'"
        ).fetchone()
    return str(row[0]).split(" ", 1)[0] if row and row[0] else ""


def _assert_identity_parity(
    checkout_identity: dict[str, Any],
    production_identity: dict[str, Any],
    *,
    checkout_head: str,
    production_head: str,
    remote_master: str,
) -> None:
    if (
        checkout_identity != production_identity
        or checkout_head != remote_master
        or production_head != remote_master
    ):
        raise RuntimeError(
            "stage056_formal_identity_mismatch_stop:"
            f"checkout={checkout_identity},production={production_identity},"
            f"checkout_head={checkout_head},production_head={production_head},"
            f"remote_master={remote_master}"
        )


def _strict_formal_identity_preflight() -> dict[str, Any]:
    checkout_identity = asdict(assert_official_checkout_matches_active_material(PROJECT_DIR))
    production_identity = asdict(
        assert_official_checkout_matches_active_material(PRODUCTION_ROOT)
    )
    checkout_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_DIR,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    production_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PRODUCTION_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    remote_master = subprocess.run(
        ["git", "rev-parse", "origin/master"],
        cwd=PROJECT_DIR,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    _assert_identity_parity(
        checkout_identity,
        production_identity,
        checkout_head=checkout_head,
        production_head=production_head,
        remote_master=remote_master,
    )
    return {
        "checkout": checkout_identity,
        "production": production_identity,
        "checkout_head": checkout_head,
        "production_head": production_head,
        "remote_master": remote_master,
    }


def _score_column(frame: pd.DataFrame) -> str:
    for column in ("score", "predicted_product_suitability_probability"):
        if column in frame.columns:
            return column
    raise RuntimeError("ranking_missing_score_column")


def _normalise_ranking(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"eval_date", "product_vt_symbol"}
    missing = required - set(frame.columns)
    if missing:
        raise RuntimeError(f"ranking_missing_columns:{sorted(missing)}")
    result = frame.copy()
    score_column = _score_column(result)
    result["eval_date"] = pd.to_datetime(result["eval_date"], errors="raise").dt.date.astype(str)
    result["product_vt_symbol"] = result["product_vt_symbol"].astype(str)
    result["score"] = pd.to_numeric(result[score_column], errors="raise")
    if "simple_trend_suitability_score" not in result.columns:
        result["simple_trend_suitability_score"] = 0.0
    result["simple_trend_suitability_score"] = pd.to_numeric(
        result["simple_trend_suitability_score"], errors="coerce"
    ).fillna(0.0)
    result.sort_values(
        ["eval_date", "score", "simple_trend_suitability_score", "product_vt_symbol"],
        ascending=[True, False, False, True],
        inplace=True,
    )
    result.reset_index(drop=True, inplace=True)
    return result


def select_top14_plus_fu(
    ranking: pd.DataFrame,
    *,
    locked_non_fu: Iterable[str] = (),
    provenance: str = "ai_probability_exact_top14_plus_fixed_fu",
) -> pd.DataFrame:
    """Select 14 unique non-fu products and append fu as a fixed fifteenth member."""

    ranked = _normalise_ranking(ranking)
    if ranked["eval_date"].nunique() != 1:
        raise RuntimeError("ranking_must_contain_exactly_one_eval_date")
    if ranked["product_vt_symbol"].duplicated().any():
        duplicates = sorted(
            ranked.loc[ranked["product_vt_symbol"].duplicated(False), "product_vt_symbol"].unique()
        )
        raise RuntimeError(f"duplicate_ranking_product:{duplicates}")

    non_fu = ranked[~ranked["product_vt_symbol"].eq(FU_PRODUCT)].copy()
    if len(non_fu) < MODEL_NON_FU_COUNT:
        raise RuntimeError(
            f"ranking_has_fewer_than_14_non_fu:{len(non_fu)}<{MODEL_NON_FU_COUNT}"
        )

    locked = tuple(dict.fromkeys(str(product) for product in locked_non_fu))
    if FU_PRODUCT in locked or len(locked) > MODEL_NON_FU_COUNT:
        raise RuntimeError(f"invalid_locked_non_fu:{locked}")
    missing_locked = sorted(set(locked) - set(non_fu["product_vt_symbol"]))
    if missing_locked:
        raise RuntimeError(f"locked_product_missing_from_ranking:{missing_locked}")

    indexed = non_fu.set_index("product_vt_symbol", drop=False)
    fill = non_fu[~non_fu["product_vt_symbol"].isin(locked)].head(
        MODEL_NON_FU_COUNT - len(locked)
    )
    selected = pd.concat(
        [indexed.loc[list(locked)].copy() if locked else non_fu.iloc[0:0].copy(), fill],
        ignore_index=True,
    )
    if len(selected) != MODEL_NON_FU_COUNT or selected["product_vt_symbol"].nunique() != MODEL_NON_FU_COUNT:
        raise RuntimeError("selected_non_fu_contract_failed")

    eval_date = str(ranked["eval_date"].iloc[0])
    rows = [
        {
            "strategy": CANDIDATE_AI_STRATEGY,
            "score_type": provenance,
            "eval_date": eval_date,
            "product_vt_symbol": str(row.product_vt_symbol),
            "score": float(row.score),
            "score_rank": rank,
            "top_n": TOTAL_PRODUCT_COUNT,
        }
        for rank, row in enumerate(selected.itertuples(index=False), start=1)
    ]
    min_score = min(row["score"] for row in rows)
    rows.append(
        {
            "strategy": CANDIDATE_AI_STRATEGY,
            "score_type": provenance,
            "eval_date": eval_date,
            "product_vt_symbol": FU_PRODUCT,
            "score": min_score - 1e-6,
            "score_rank": TOTAL_PRODUCT_COUNT,
            "top_n": TOTAL_PRODUCT_COUNT,
        }
    )
    return pd.DataFrame(rows, columns=ELIGIBILITY_COLUMNS)


def preserve_pre_ai_boundary(formal: pd.DataFrame) -> pd.DataFrame:
    preserved = formal[
        formal["score_type"].astype(str).eq("static18_pre_ai_boundary")
    ].copy()
    if len(preserved) != 18 or preserved["product_vt_symbol"].nunique() != 18:
        raise RuntimeError("static18_pre_ai_boundary_contract_failed")
    preserved["strategy"] = CANDIDATE_AI_STRATEGY
    return preserved.loc[:, ELIGIBILITY_COLUMNS].copy()


def _generate_june_ranking() -> pd.DataFrame:
    runner = PORTFOLIO_DIR / "build_qmt_roll_stage182_ai_product_pool_live_inference_runner.py"
    with tempfile.TemporaryDirectory(prefix="stage056-june-ranking-") as directory:
        output_dir = Path(directory)
        environment = dict(os.environ)
        environment["PYTHONPATH"] = f"{PROJECT_DIR}:{PORTFOLIO_DIR}"
        subprocess.run(
            [
                str(PROJECT_DIR / ".py311" / "bin" / "python"),
                str(runner),
                "--eval-date",
                JUNE_EVAL_DATE,
                "--source-prefix",
                "qmt_roll_stage183_ai_source_floor35",
                "--source-dir",
                str(STAGE183_SOURCE_DIR),
                "--output-dir",
                str(output_dir),
            ],
            cwd=PROJECT_DIR,
            env=environment,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        path = output_dir / "qmt_roll_stage182_ai_product_pool_live_inference_latest_pool_stage182_ai_product_pool_live_inference_v1.csv"
        result = pd.read_csv(path)
    return _normalise_ranking(result)


def build_full_ranking_source() -> tuple[pd.DataFrame, pd.DataFrame]:
    source_frames: list[pd.DataFrame] = []

    market = _normalise_ranking(pd.read_csv(MARKET_RANKING_PATH))
    market = market[market["eval_date"].le("2026-02-27")].copy()
    market["ranking_provenance"] = "frozen_market_walkforward_v2"
    source_frames.append(market)

    stage189 = _normalise_ranking(pd.read_csv(STAGE189_RANKING_PATH))
    stage189 = stage189[stage189["eval_date"].isin(MEMBERSHIP_ONLY_DATES)].copy()
    stage189["ranking_provenance"] = "stage189_rerun_membership_locked_fill"
    source_frames.append(stage189)

    june = _generate_june_ranking()
    june["ranking_provenance"] = "stage182_point_in_time_replay"
    source_frames.append(june)

    latest = _normalise_ranking(pd.read_csv(LATEST_RANKING_PATH))
    latest["ranking_provenance"] = "formal_m0016_latest_pool"
    source_frames.append(latest)

    combined = pd.concat(source_frames, ignore_index=True, sort=False)
    combined.sort_values(
        ["eval_date", "score", "simple_trend_suitability_score", "product_vt_symbol"],
        ascending=[True, False, False, True],
        inplace=True,
    )
    duplicate = combined.duplicated(["eval_date", "product_vt_symbol"], keep=False)
    if duplicate.any():
        raise RuntimeError("full_ranking_source_duplicate_product_month")
    counts = combined.groupby("eval_date")["product_vt_symbol"].nunique()
    if (counts < MODEL_NON_FU_COUNT).any():
        raise RuntimeError(f"full_ranking_source_incomplete:{counts[counts < MODEL_NON_FU_COUNT].to_dict()}")
    audit = combined[
        [
            "eval_date",
            "product_vt_symbol",
            "score",
            "simple_trend_suitability_score",
            "ranking_provenance",
        ]
    ].copy()
    audit["source_rank"] = audit.groupby("eval_date").cumcount() + 1
    return combined, audit


def build_candidate_eligibility(
    formal: pd.DataFrame,
    ranking_source: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    formal = formal.loc[:, ELIGIBILITY_COLUMNS].copy()
    formal["eval_date"] = pd.to_datetime(formal["eval_date"], errors="raise").dt.date.astype(str)
    ranking_source = _normalise_ranking(ranking_source)
    rows = [preserve_pre_ai_boundary(formal)]
    audits: list[dict[str, Any]] = []

    model_dates = sorted(
        date for date in formal["eval_date"].unique() if date != "2019-12-31"
    )
    ranking_dates = set(ranking_source["eval_date"].unique())
    missing_dates = sorted(set(model_dates) - ranking_dates)
    if missing_dates:
        raise RuntimeError(f"missing_ranking_month:{missing_dates}")

    for eval_date in model_dates:
        formal_month = formal[formal["eval_date"].eq(eval_date)].sort_values("score_rank")
        formal_non_fu = tuple(
            formal_month.loc[
                ~formal_month["product_vt_symbol"].eq(FU_PRODUCT), "product_vt_symbol"
            ].astype(str)
        )
        ranking_month = ranking_source[ranking_source["eval_date"].eq(eval_date)].copy()
        locked = formal_non_fu if eval_date in MEMBERSHIP_ONLY_DATES else ()
        provenance = (
            "membership_locked_score_fill"
            if locked
            else "ai_probability_exact_top14_plus_fixed_fu"
        )
        selected = select_top14_plus_fu(
            ranking_month,
            locked_non_fu=locked,
            provenance=provenance,
        )
        selected_non_fu = set(
            selected.loc[
                ~selected["product_vt_symbol"].eq(FU_PRODUCT), "product_vt_symbol"
            ].astype(str)
        )
        formal_preserved = set(formal_non_fu).issubset(selected_non_fu)
        if not formal_preserved:
            raise RuntimeError(f"formal_top8_not_preserved:{eval_date}")
        rows.append(selected)
        audits.append(
            {
                "eval_date": eval_date,
                "formal_product_count": int(formal_month["product_vt_symbol"].nunique()),
                "candidate_product_count": int(selected["product_vt_symbol"].nunique()),
                "formal_top8_preserved": formal_preserved,
                "selection_provenance": provenance,
                "added_products": ",".join(sorted(selected_non_fu - set(formal_non_fu))),
            }
        )

    result = pd.concat(rows, ignore_index=True)
    result.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    result.reset_index(drop=True, inplace=True)
    post_ai = result[~result["score_type"].eq("static18_pre_ai_boundary")]
    month_counts = post_ai.groupby("eval_date")["product_vt_symbol"].nunique()
    if not month_counts.eq(TOTAL_PRODUCT_COUNT).all():
        raise RuntimeError(f"candidate_month_count_contract_failed:{month_counts.to_dict()}")
    return result, pd.DataFrame(audits)


def _write_candidate_eligibility(candidate: pd.DataFrame) -> None:
    candidate_cfg.CANDIDATE_ELIGIBILITY_PATH.parent.mkdir(parents=True, exist_ok=True)
    candidate.to_csv(
        candidate_cfg.CANDIDATE_ELIGIBILITY_PATH,
        index=False,
        encoding="utf-8-sig",
    )


def build_arm_overrides(arm: str) -> dict[str, Any]:
    if arm == "A":
        return live_cfg.build_official_live_strategy_overrides()
    if arm == "C":
        return candidate_cfg.build_candidate_overrides()
    raise ValueError(f"unknown_stage056_arm:{arm}")


def _run_arm(
    arm: dict[str, str], metadata: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    original_builder = s28.s901.build_official_live_strategy_overrides
    try:
        s28.s901.build_official_live_strategy_overrides = lambda: build_arm_overrides(arm["arm"])
        combined, frames, live_spec = s28.s901._run_live_c9(metadata, START, END)
    finally:
        s28.s901.build_official_live_strategy_overrides = original_builder

    capital = replace(live_spec.capital, variant=arm["profile"], label=arm["label"])
    metric_spec = replace(live_spec, capital=capital, profile=arm["profile"])
    summary, curve = s28.s827._metric(
        {"profile": arm["profile"], "spec": metric_spec}, combined
    )
    summary["experiment_arm"] = arm["arm"]
    summary["window_name"] = "full_2018_20260828"
    summary["window_label"] = "2018-01-01 independent start to 2026-08-28"
    curve["experiment_arm"] = arm["arm"]
    for frame in frames.values():
        if not frame.empty:
            frame["experiment_arm"] = arm["arm"]
    return summary, curve, frames


def _assert_coverage(summary: pd.DataFrame, curve: pd.DataFrame) -> None:
    if len(summary) != 2 or set(summary["experiment_arm"].astype(str)) != {"A", "C"}:
        raise RuntimeError("stage056_arm_identity_failed")
    reference: pd.DatetimeIndex | None = None
    for arm in ("A", "C"):
        dates = pd.DatetimeIndex(
            pd.to_datetime(
                curve[curve["experiment_arm"].eq(arm)]["date"],
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
            raise RuntimeError(f"stage056_full_period_coverage_failed:{arm}")


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    indexed = summary.set_index("experiment_arm")
    a, c = indexed.loc["A"], indexed.loc["C"]
    metrics = (
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "max_broker10_margin_to_equity_pct",
        "days_over_100pct",
    )
    row: dict[str, Any] = {"comparison": "master_m0016_stage037_top8_fu_vs_top14_fu"}
    for metric in metrics:
        row[f"A_{metric}"] = float(a[metric])
        row[f"C_{metric}"] = float(c[metric])
        row[f"delta_{metric}"] = float(c[metric]) - float(a[metric])
    return pd.DataFrame([row])


def _trade_product(row: pd.Series) -> str:
    match = re.match(r"([A-Za-z]+)", str(row.get("vt_symbol", "")))
    if not match:
        return ""
    return f"{match.group(1)}.{row.get('exchange', '')}"


def _added_product_attribution(
    c_trades: pd.DataFrame,
    membership_audit: pd.DataFrame,
) -> pd.DataFrame:
    if c_trades.empty:
        return pd.DataFrame(columns=["product_vt_symbol", "open_fill_count", "open_lots"])
    added_by_date = {
        row.eval_date: set(filter(None, str(row.added_products).split(",")))
        for row in membership_audit.itertuples(index=False)
    }
    eval_dates = pd.DatetimeIndex(pd.to_datetime(sorted(added_by_date)))
    trades = c_trades.copy()
    trades["date"] = pd.to_datetime(trades["date"], errors="raise").dt.normalize()
    trades["product_vt_symbol"] = trades.apply(_trade_product, axis=1)
    trades = trades[trades["offset"].astype(str).eq("开")].copy()

    def is_added(row: pd.Series) -> bool:
        eligible_dates = eval_dates[eval_dates <= row["date"]]
        if eligible_dates.empty:
            return False
        key = str(eligible_dates[-1].date())
        return str(row["product_vt_symbol"]) in added_by_date.get(key, set())

    trades["is_added_product"] = trades.apply(is_added, axis=1)
    added = trades[trades["is_added_product"]].copy()
    if added.empty:
        return pd.DataFrame(columns=["product_vt_symbol", "open_fill_count", "open_lots"])
    return (
        added.groupby("product_vt_symbol", as_index=False)
        .agg(open_fill_count=("trade_id", "count"), open_lots=("volume", "sum"))
        .sort_values(["open_fill_count", "product_vt_symbol"], ascending=[False, True])
    )


def _plot(curve: pd.DataFrame) -> bytes:
    fig, ax = plt.subplots(figsize=(14, 6))
    for arm in ARMS:
        frame = curve[curve["experiment_arm"].eq(arm["arm"])].sort_values("date")
        ax.plot(
            pd.to_datetime(frame["date"]),
            pd.to_numeric(frame["account_equity"], errors="coerce") / 10_000.0,
            color=arm["color"],
            linewidth=1.4,
            label=arm["plot_label"],
        )
    ax.set_title("master m0016 Stage037 Offline: Top8+fu vs Top14+fu")
    ax.set_ylabel("Equity (10k CNY)")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=180)
    plt.close(fig)
    return buffer.getvalue()


def _report(
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    membership_audit: pd.DataFrame,
    attribution: pd.DataFrame,
    decision: dict[str, Any],
) -> str:
    indexed = summary.set_index("experiment_arm")
    delta = comparison.iloc[0]
    lines = [
        "# Stage056 Stage037 AI Top14+fu 全周期 A/C",
        "",
        f"区间：`{START.date()}` 至 `{END.date()}`。唯一变量为 AI 月度池从 Top8 非fu + fu 扩为 Top14 非fu + fu。",
        "",
        "| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 非零交易日胜率 | broker10峰值 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm, label in (("A", ARMS[0]["label"]), ("C", ARMS[1]["label"])):
        row = indexed.loc[arm]
        lines.append(
            f"| {label} | {row['end_equity']:,.2f} | {row['total_return_pct']:.4f}% | "
            f"{row['max_dd_pct']:.4f}% | {row['sharpe']:.6f} | {row['total_slippage']:,.0f} | "
            f"{int(row['total_trade_count'])} | {row['nonzero_daily_win_rate_pct']:.4f}% | "
            f"{row['max_broker10_margin_to_equity_pct']:.4f}% |"
        )
    lines.extend(
        [
            "",
            "## 结果差异",
            "",
            f"- C 相对 A：期末权益 `{delta['delta_end_equity']:+,.2f}`，总收益 `{delta['delta_total_return_pct']:+.4f}pp`，最大回撤 `{delta['delta_max_dd_pct']:+.4f}pp`，Sharpe `{delta['delta_sharpe']:+.6f}`。",
            f"- 交易数 `{delta['delta_total_trade_count']:+.0f}`，滑点 `{delta['delta_total_slippage']:+,.0f}`，非零交易日胜率 `{delta['delta_nonzero_daily_win_rate_pct']:+.4f}pp`。",
            "",
            "## 数据边界",
            "",
            f"- 共 `{len(membership_audit)}` 个 AI 月度快照；每月均为 14 个非fu + 固定fu，正式 Top8 全部保留。",
            "- `2026-03/04/05` 的原始第9–14名评分未被历史正式物料保存；这三个月采用 `membership_locked_score_fill`：锁住当时正式 Top8，再用同模型时点重放排名补6个。",
            "- 2019-12-31 的 static18 前AI边界原样保留，未把模型选择逻辑倒灌到AI上线前。",
            "",
            "## 新增品种开仓归因",
            "",
        ]
    )
    if attribution.empty:
        lines.append("- 候选期内没有新增池成员产生开仓成交。")
    else:
        for row in attribution.itertuples(index=False):
            lines.append(
                f"- `{row.product_vt_symbol}`：开仓成交 `{int(row.open_fill_count)}` 笔，合计 `{float(row.open_lots):.0f}` 手。"
            )
    lines.extend(
        [
            "",
            "## 决策边界",
            "",
            f"- 选择合同：`{decision['gates']['selector_contract_pass']}`；唯一变量合同：`{decision['gates']['only_ai_pool_path_and_strategy_changed']}`。",
            f"- 风险结果：回撤不劣于正式版 `{decision['gates']['candidate_max_drawdown_not_worse']}`，Sharpe不低于正式版 `{decision['gates']['candidate_sharpe_not_lower_than_formal']}`，broker10不超过100% `{decision['gates']['candidate_broker10_100_pass']}`。",
            "- 本阶段是研究回测，不连接 CTP、不调用订单API、不自动晋升正式版。",
            "",
        ]
    )
    return "\n".join(lines)


def _publish(
    frames: dict[str, pd.DataFrame], decision: dict[str, Any], report: str, chart: bytes
) -> None:
    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".stage056.tmp-", dir=OUTPUT_DIR.parent))
    backup = OUTPUT_DIR.with_name(f".stage056.backup-{uuid4().hex}")
    try:
        for filename, frame in frames.items():
            frame.to_csv(temporary / filename, index=False, encoding="utf-8-sig")
        (temporary / DECISION_NAME).write_text(
            json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (temporary / REPORT_NAME).write_text(report, encoding="utf-8")
        (temporary / CHART_NAME).write_bytes(chart)
        if OUTPUT_DIR.exists():
            OUTPUT_DIR.rename(backup)
        temporary.rename(OUTPUT_DIR)
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def main() -> None:
    formal_identity = _strict_formal_identity_preflight()
    tracked_master = subprocess.run(
        ["git", "rev-parse", "origin/master"],
        cwd=PROJECT_DIR,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if tracked_master != BASE_MASTER_COMMIT:
        raise RuntimeError(f"stage056_base_master_drift:{tracked_master}!={BASE_MASTER_COMMIT}")
    if live_cfg.OFFICIAL_LIVE_RULESET_VERSION != BASE_RULESET_VERSION:
        raise RuntimeError(
            f"stage056_base_ruleset_drift:{live_cfg.OFFICIAL_LIVE_RULESET_VERSION}!={BASE_RULESET_VERSION}"
        )
    required_inputs = (
        FORMAL_ELIGIBILITY_PATH,
        MARKET_RANKING_PATH,
        STAGE189_RANKING_PATH,
        LATEST_RANKING_PATH,
        MAPPING_PATH,
        FULL_MINUTE_BARS_PATH,
        STAGE183_POSITION_CHANGES_PATH,
        STAGE183_ENTRY_SNAPSHOTS_PATH,
        DATABASE_PATH,
    )
    missing_inputs = [str(path) for path in required_inputs if not path.exists()]
    if missing_inputs:
        raise RuntimeError(f"stage056_missing_required_input:{missing_inputs}")

    formal = pd.read_csv(FORMAL_ELIGIBILITY_PATH)
    ranking_source, ranking_audit = build_full_ranking_source()
    candidate, membership_audit = build_candidate_eligibility(formal, ranking_source)
    _write_candidate_eligibility(candidate)

    diff = candidate_cfg.override_diff()
    if set(diff) != {"ai_product_pool_eligibility_path", "ai_product_pool_strategy"}:
        raise RuntimeError(f"stage056_override_scope_drift:{diff}")

    metadata = s28.s513._metadata()
    summaries: list[pd.DataFrame] = []
    curves: list[pd.DataFrame] = []
    frames_by_arm: dict[str, dict[str, pd.DataFrame]] = {}
    for arm in ARMS:
        print(f"[stage056] running {arm['arm']} {START.date()}->{END.date()}", flush=True)
        summary, curve, frames = _run_arm(arm, metadata)
        summaries.append(summary)
        curves.append(curve)
        frames_by_arm[arm["arm"]] = frames

    summary = pd.concat(summaries, ignore_index=True, sort=False)
    curve = pd.concat(curves, ignore_index=True, sort=False)
    _assert_coverage(summary, curve)
    comparison = _comparison(summary)
    trades = pd.concat(
        [frames_by_arm[arm]["trades"] for arm in ("A", "C")],
        ignore_index=True,
        sort=False,
    )
    attribution = _added_product_attribution(frames_by_arm["C"]["trades"], membership_audit)

    indexed = summary.set_index("experiment_arm")
    a, c = indexed.loc["A"], indexed.loc["C"]
    selector_contract = bool(
        membership_audit["formal_top8_preserved"].all()
        and membership_audit["candidate_product_count"].eq(TOTAL_PRODUCT_COUNT).all()
        and candidate[candidate["eval_date"].ne("2019-12-31")]
        .groupby("eval_date")["product_vt_symbol"]
        .nunique()
        .eq(TOTAL_PRODUCT_COUNT)
        .all()
    )
    gates = {
        "selector_contract_pass": selector_contract,
        "only_ai_pool_path_and_strategy_changed": set(diff)
        == {"ai_product_pool_eligibility_path", "ai_product_pool_strategy"},
        "formal_top8_preserved_every_month": bool(membership_audit["formal_top8_preserved"].all()),
        "full_period_coverage_pass": True,
        "candidate_account_survival": float(c["min_equity"]) > 0,
        "candidate_has_real_effect": bool(
            float(c["end_equity"]) != float(a["end_equity"])
            or float(c["total_trade_count"]) != float(a["total_trade_count"])
        ),
        "candidate_max_drawdown_not_worse": float(c["max_dd_pct"]) >= float(a["max_dd_pct"]),
        "candidate_sharpe_not_lower_than_formal": float(c["sharpe"]) >= float(a["sharpe"]),
        "candidate_broker10_100_pass": int(c["days_over_100pct"]) == 0,
        "candidate_dd40_pass": bool(c["dd40_pass"]),
        "no_order_api": True,
    }
    decision = {
        "line_id": LINE_ID,
        "stage": STAGE,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "base_master_commit": BASE_MASTER_COMMIT,
        "base_ruleset_version": BASE_RULESET_VERSION,
        "candidate_version": candidate_cfg.CANDIDATE_VERSION,
        "period": {"start": str(START.date()), "end": str(END.date())},
        "hypothesis": "Stage037不变，仅把AI选品由Top8非fu+fu扩至Top14非fu+fu，检验容量和横截面分散效果。",
        "frozen_scope": {
            "model_non_fu_count": MODEL_NON_FU_COUNT,
            "fixed_fu": FU_PRODUCT,
            "total_product_count": TOTAL_PRODUCT_COUNT,
            "pre_ai_boundary": "static18 unchanged",
            "membership_only_dates": sorted(MEMBERSHIP_ONLY_DATES),
            "membership_only_policy": "lock formal Top8 then fill six by same-model point-in-time replay ranking",
        },
        "source_identity": {
            "formal_eligibility_path": str(FORMAL_ELIGIBILITY_PATH),
            "formal_eligibility_sha256": _file_sha256(FORMAL_ELIGIBILITY_PATH),
            "market_ranking_path": str(MARKET_RANKING_PATH),
            "market_ranking_sha256": _file_sha256(MARKET_RANKING_PATH),
            "stage189_ranking_path": str(STAGE189_RANKING_PATH),
            "stage189_ranking_sha256": _file_sha256(STAGE189_RANKING_PATH),
            "latest_ranking_path": str(LATEST_RANKING_PATH),
            "latest_ranking_sha256": _file_sha256(LATEST_RANKING_PATH),
            "main_contract_mapping_path": str(MAPPING_PATH.resolve()),
            "main_contract_mapping_sha256": _file_sha256(MAPPING_PATH),
            "full_minute_bars_path": str(FULL_MINUTE_BARS_PATH.resolve()),
            "full_minute_bars_sha256": _file_sha256(FULL_MINUTE_BARS_PATH),
            "database_path": str(DATABASE_PATH.resolve()),
            "database_sha256": _file_sha256(DATABASE_PATH),
            "database_latest_daily_date": _database_latest_daily_date(DATABASE_PATH),
            "stage183_position_changes_path": str(STAGE183_POSITION_CHANGES_PATH),
            "stage183_position_changes_sha256": _file_sha256(STAGE183_POSITION_CHANGES_PATH),
            "stage183_entry_snapshots_path": str(STAGE183_ENTRY_SNAPSHOTS_PATH),
            "stage183_entry_snapshots_sha256": _file_sha256(STAGE183_ENTRY_SNAPSHOTS_PATH),
            "candidate_eligibility_sha256": _file_sha256(candidate_cfg.CANDIDATE_ELIGIBILITY_PATH),
        },
        "formal_identity": formal_identity,
        "override_diff": {key: [str(values[0]), str(values[1])] for key, values in diff.items()},
        "gates": gates,
        "comparisons": comparison.to_dict(orient="records"),
        "promote_to_official": False,
        "decision": (
            "research_candidate_passes_full_period_risk_gates_review_robustness_before_any_promotion"
            if all(gates.values())
            else "research_candidate_full_period_risk_gate_failed_do_not_promote"
        ),
        "overfitting_assessment": "medium: one frozen breadth point, but selected after seeing prior Top8 behavior; no parameter scan in this stage",
        "continue_value_assessment": "yes: isolates breadth/capacity while holding Stage037 alpha and risk logic fixed",
        "order_api_called_count": 0,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
    }
    frames = {
        SUMMARY_NAME: summary,
        COMPARISON_NAME: comparison,
        CURVE_NAME: curve,
        TRADES_NAME: trades,
        ATTRIBUTION_NAME: attribution,
        ELIGIBILITY_NAME: candidate,
        MEMBERSHIP_AUDIT_NAME: membership_audit,
        RANKING_AUDIT_NAME: ranking_audit,
    }
    report = _report(summary, comparison, membership_audit, attribution, decision)
    _publish(frames, decision, report, _plot(curve))
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
