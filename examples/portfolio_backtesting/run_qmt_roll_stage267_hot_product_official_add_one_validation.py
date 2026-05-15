from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_PROFIT_SHIELD_MODE,
    OFFICIAL_STAGE78_REFERENCE_METRICS,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_paths,
)
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (
    BASE_RISK_RATIO,
    CORR20_06_08_FLOOR35_OVERRIDES,
)
from qmt_universe import END_DT, START_DT


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

EXPERIMENT_TAG: str = "qmt_roll_stage267_hot_product_official_add_one_validation"
UNIVERSE_DIR: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_universes"
ELIGIBILITY_DIR: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_eligibility"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.json"
COMPARISON_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_comparison.csv"
REPORT_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_report.md"
EQUITY_CURVE_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_equity_curves.csv"
EQUITY_CURVE_HTML_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_equity_curves.html"

TRADABLE_UNIVERSE_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_full_market_tradable_universe_eligible_full_market_tradable_universe_v1.csv"
)
HOT_AUDIT_PATH: Path = OUTPUT_DIR / "qmt_roll_stage264_hot_product_gap_audit_audit_stage264_hot_product_gap_audit_v1.csv"

OFFICIAL_BASELINE_NAME: str = "official_stage78_1_static18_plus_fu"
OFFICIAL_AI_STRATEGY_NAME: str = "ai_top8_plus_fu_satellite_post_signal_entry_filter"
FIXED_FU_PRODUCT: str = "fu.SHFE"

CANDIDATE_PRODUCTS: tuple[str, ...] = (
    "TA.CZCE",
    "ag.SHFE",
    "sc.INE",
    "m.DCE",
    "p.DCE",
    "y.DCE",
    "i.DCE",
    "v.DCE",
    "c.DCE",
    "ao.SHFE",
)


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _load_product_universe(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    df["product_vt_symbol"] = df["product_vt_symbol"].astype(str)
    return df


def _official_products() -> tuple[set[str], Path, Path]:
    official_universe_path, official_eligibility_path = build_official_stage78_paths()
    official_universe = _load_product_universe(official_universe_path)
    return set(official_universe["product_vt_symbol"].astype(str)), official_universe_path, official_eligibility_path


def _hot_audit_tiers() -> dict[str, str]:
    if not HOT_AUDIT_PATH.exists():
        return {}
    df = pd.read_csv(HOT_AUDIT_PATH)
    return dict(zip(df["product_vt_symbol"].astype(str), df["test_tier"].astype(str), strict=False))


def _experiment_name(product: str | None) -> str:
    if not product:
        return OFFICIAL_BASELINE_NAME
    return f"official_stage78_1_plus_{product.replace('.', '_')}"


def _candidate_role(product: str | None, tiers: dict[str, str]) -> str:
    if not product:
        return "A_official_stage78_1_baseline"
    tier = tiers.get(product, "")
    if tier == "direct_add_one_ready":
        return "C_direct_add_one_candidate"
    return "C_counterfactual_add_one_candidate"


def build_universe(experiment_name: str, selected_products: set[str]) -> Path:
    tradable = _load_product_universe(TRADABLE_UNIVERSE_PATH)
    missing = sorted(selected_products - set(tradable["product_vt_symbol"].astype(str)))
    if missing:
        raise ValueError(f"{experiment_name} missing products from tradable universe: {missing}")
    universe = tradable[tradable["product_vt_symbol"].isin(selected_products)].copy()
    universe.sort_values(["exchange", "product_vt_symbol"], inplace=True)
    UNIVERSE_DIR.mkdir(parents=True, exist_ok=True)
    path = UNIVERSE_DIR / f"{EXPERIMENT_TAG}_{experiment_name}_universe.csv"
    universe.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def build_candidate_eligibility(
    experiment_name: str,
    official_eligibility_path: Path,
    extra_products: tuple[str, ...],
) -> tuple[Path, str]:
    if not extra_products:
        return official_eligibility_path, OFFICIAL_AI_STRATEGY_NAME

    official = pd.read_csv(official_eligibility_path)
    strategy_name = f"{EXPERIMENT_TAG}_{experiment_name}_entry_filter"
    eligibility = official.copy()
    eligibility["strategy"] = strategy_name
    eligibility["score_type"] = eligibility["score_type"].astype(str)

    rows: list[dict[str, Any]] = []
    monthly = eligibility[eligibility["eval_date"].astype(str) != "2019-12-31"].copy()
    for eval_date, group in monthly.groupby("eval_date", sort=True):
        existing = set(group["product_vt_symbol"].astype(str))
        min_score = pd.to_numeric(group["score"], errors="coerce").min()
        base_score = float(min_score) if pd.notna(min_score) else 0.0
        max_rank = int(pd.to_numeric(group["score_rank"], errors="coerce").fillna(0).max())
        max_top_n = int(pd.to_numeric(group["top_n"], errors="coerce").fillna(max_rank).max())
        offset = 0
        for product in extra_products:
            if product in existing:
                continue
            offset += 1
            rows.append(
                {
                    "strategy": strategy_name,
                    "score_type": f"stage267_fixed_add_one_{product.replace('.', '_')}",
                    "eval_date": eval_date,
                    "product_vt_symbol": product,
                    "score": base_score - 1e-6 * offset,
                    "score_rank": max_rank + offset,
                    "top_n": max_top_n + len(extra_products),
                }
            )

    if rows:
        eligibility = pd.concat([eligibility, pd.DataFrame(rows)], ignore_index=True)
    eligibility.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    ELIGIBILITY_DIR.mkdir(parents=True, exist_ok=True)
    path = ELIGIBILITY_DIR / f"{EXPERIMENT_TAG}_{experiment_name}_eligibility.csv"
    eligibility.to_csv(path, index=False, encoding="utf-8-sig")
    return path, strategy_name


def _strategy_overrides(
    universe_path: Path,
    eligibility_path: Path,
    strategy_name: str,
    risk_state_products: tuple[str, ...],
) -> dict[str, Any]:
    return {
        **CORR20_06_08_FLOOR35_OVERRIDES,
        "product_universe_csv_path": str(universe_path),
        "sizing_equity_cap": 0.0,
        "enable_ai_product_pool_filter": True,
        "ai_product_pool_eligibility_path": str(eligibility_path),
        "ai_product_pool_strategy": strategy_name,
        "streak_risk_state_excluded_products": ",".join(risk_state_products),
        "streak_risk_state_exclusion_mode": OFFICIAL_STAGE78_PROFIT_SHIELD_MODE,
    }


def run_experiments() -> pd.DataFrame:
    official_products, _, official_eligibility_path = _official_products()
    tiers = _hot_audit_tiers()
    rows: list[dict[str, Any]] = []
    experiment_products: tuple[str | None, ...] = (None, *CANDIDATE_PRODUCTS)

    for product in experiment_products:
        experiment_name = _experiment_name(product)
        selected_products = set(official_products)
        extra_products: tuple[str, ...] = ()
        if product:
            selected_products.add(product)
            extra_products = (product,)

        universe_path = build_universe(experiment_name, selected_products)
        eligibility_path, strategy_name = build_candidate_eligibility(
            experiment_name,
            official_eligibility_path,
            extra_products,
        )
        risk_state_products = tuple(sorted({FIXED_FU_PRODUCT, *extra_products}))
        overrides = _strategy_overrides(universe_path, eligibility_path, strategy_name, risk_state_products)
        print(f"[stage267] running {experiment_name}", flush=True)
        _, _, statistics = run_backtest(
            risk_ratio=BASE_RISK_RATIO,
            strategy_overrides=overrides,
            analysis_start=START_DT,
            analysis_end=END_DT,
            capital=OFFICIAL_STAGE78_CAPITAL,
            save_artifacts=True,
            include_start_year_sweep=False,
            file_prefix=f"{EXPERIMENT_TAG}_{experiment_name}",
            chart_title=f"Stage267 {experiment_name}",
        )
        rows.append(
            build_summary_row(
                statistics,
                analysis_start=START_DT,
                analysis_end=END_DT,
                experiment_name=experiment_name,
                role=_candidate_role(product, tiers),
                candidate_product=product or "",
                test_tier=tiers.get(product or FIXED_FU_PRODUCT, "baseline_revalidation" if not product else ""),
                official_version=OFFICIAL_STAGE78_VERSION,
                universe_path=str(universe_path),
                ai_eligibility_path=str(eligibility_path),
                ai_strategy=strategy_name,
                strategy_overrides_json=json.dumps(overrides, ensure_ascii=False, sort_keys=True),
                total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                total_slippage=float(statistics.get("total_slippage", 0) or 0),
                total_commission=float(statistics.get("total_commission", 0) or 0),
                profit_days=int(statistics.get("profit_days", 0) or 0),
                loss_days=int(statistics.get("loss_days", 0) or 0),
            )
        )
    return pd.DataFrame(rows)


def build_comparison(summary: pd.DataFrame) -> pd.DataFrame:
    base = summary[summary["experiment_name"] == OFFICIAL_BASELINE_NAME].iloc[0]
    rows: list[dict[str, Any]] = []
    for row in summary.to_dict(orient="records"):
        rows.append(
            {
                "experiment_name": row["experiment_name"],
                "role": row.get("role", ""),
                "candidate_product": row.get("candidate_product", ""),
                "test_tier": row.get("test_tier", ""),
                "end_balance": row["end_balance"],
                "total_return_pct": row["total_return_pct"],
                "max_dd_percent": row["max_dd_percent"],
                "sharpe_ratio": row["sharpe_ratio"],
                "total_trade_count": row["total_trade_count"],
                "win_ratio_pct": row["win_ratio_pct"],
                "end_balance_diff_vs_A": _safe_float(row["end_balance"]) - _safe_float(base["end_balance"]),
                "return_diff_vs_A": _safe_float(row["total_return_pct"]) - _safe_float(base["total_return_pct"]),
                "dd_diff_vs_A": _safe_float(row["max_dd_percent"]) - _safe_float(base["max_dd_percent"]),
                "sharpe_diff_vs_A": _safe_float(row["sharpe_ratio"]) - _safe_float(base["sharpe_ratio"]),
                "trade_count_diff_vs_A": int(row["total_trade_count"] - base["total_trade_count"]),
            }
        )
    comparison = pd.DataFrame(rows)
    comparison.sort_values(["role", "end_balance_diff_vs_A"], ascending=[True, False], inplace=True)
    return comparison.reset_index(drop=True)


def _load_equity_curve(experiment_name: str) -> pd.DataFrame:
    path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_{experiment_name}_daily_equity.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    date_column = "date" if "date" in df.columns else df.columns[0]
    balance_column = "balance" if "balance" in df.columns else "end_balance"
    if balance_column not in df.columns:
        numeric_cols = [
            column for column in df.columns if column != date_column and pd.api.types.is_numeric_dtype(df[column])
        ]
        if not numeric_cols:
            raise ValueError(f"cannot find balance column in {path}")
        balance_column = numeric_cols[-1]
    return pd.DataFrame(
        {
            "date": pd.to_datetime(df[date_column]),
            "experiment_name": experiment_name,
            "balance": pd.to_numeric(df[balance_column], errors="coerce"),
        }
    ).dropna(subset=["balance"])


def build_equity_curves(summary: pd.DataFrame) -> pd.DataFrame:
    frames = [_load_equity_curve(str(name)) for name in summary["experiment_name"]]
    long_df = pd.concat(frames, ignore_index=True)
    wide = long_df.pivot_table(index="date", columns="experiment_name", values="balance", aggfunc="last").sort_index()
    wide.to_csv(EQUITY_CURVE_CSV_PATH, encoding="utf-8-sig")
    return long_df


def write_equity_curve_html(curves: pd.DataFrame) -> None:
    try:
        import plotly.graph_objects as go

        fig = go.Figure()
        for name, group in curves.groupby("experiment_name", sort=False):
            fig.add_trace(go.Scatter(x=group["date"], y=group["balance"], mode="lines", name=str(name)))
        fig.update_layout(
            title="Stage267 Stage78-1 Hot Product Add-One Equity Curves",
            xaxis_title="Date",
            yaxis_title="Balance",
            hovermode="x unified",
            template="plotly_white",
            width=1320,
            height=760,
        )
        fig.write_html(EQUITY_CURVE_HTML_PATH, include_plotlyjs="cdn")
    except Exception as exc:
        EQUITY_CURVE_HTML_PATH.write_text(
            "<html><body><h1>Stage267 Equity Curves</h1>"
            f"<p>Plotly render failed: {exc}</p>"
            f"<p>CSV: {EQUITY_CURVE_CSV_PATH}</p></body></html>",
            encoding="utf-8",
        )


def _markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_empty_"
    view = df.copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    return "\n".join(
        [
            "| " + " | ".join(view.columns) + " |",
            "| " + " | ".join(["---"] * len(view.columns)) + " |",
            *["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()],
        ]
    )


def build_report(summary: pd.DataFrame, comparison: pd.DataFrame) -> str:
    result_columns = [
        "experiment_name",
        "role",
        "candidate_product",
        "test_tier",
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_slippage",
        "total_trade_count",
        "win_ratio_pct",
    ]
    compare_columns = [
        "experiment_name",
        "candidate_product",
        "test_tier",
        "end_balance_diff_vs_A",
        "return_diff_vs_A",
        "dd_diff_vs_A",
        "sharpe_diff_vs_A",
        "trade_count_diff_vs_A",
    ]
    return "\n".join(
        [
            "# Stage267 Stage78-1 Hot Product Official Add-One Validation",
            "",
            "## Design",
            "",
            f"- A baseline: `{OFFICIAL_STAGE78_VERSION}` with static18 + `fu.SHFE`, capital `500000`, no sizing cap.",
            "- C candidates: add exactly one hot product to the official baseline and append it to monthly post-signal eligibility.",
            "- Structural-blocked products are treated as counterfactual tests, not promotion candidates.",
            "- This is a candidate screen; promotion requires start-year, quarter cold-start, weak-window and slippage stress validation.",
            "",
            "## Results",
            "",
            _markdown_table(summary[result_columns]),
            "",
            "## Comparison Vs A",
            "",
            _markdown_table(comparison[compare_columns]),
            "",
            "## Reference",
            "",
            f"- Frozen reference metrics: `{OFFICIAL_STAGE78_REFERENCE_METRICS.get('full_2020_2026', {})}`",
            "",
            "## Equity Curve",
            "",
            f"- HTML: `{EQUITY_CURVE_HTML_PATH}`",
            f"- CSV: `{EQUITY_CURVE_CSV_PATH}`",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = run_experiments()
    comparison = build_comparison(summary)
    comparison.to_csv(COMPARISON_CSV_PATH, index=False, encoding="utf-8-sig")
    curves = build_equity_curves(summary)
    write_equity_curve_html(curves)

    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    payload = {
        "experiment_tag": EXPERIMENT_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "candidate_products": list(CANDIDATE_PRODUCTS),
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "base_risk_ratio": BASE_RISK_RATIO,
        "summary_csv": str(SUMMARY_CSV_PATH),
        "summary_json": str(SUMMARY_JSON_PATH),
        "comparison_csv": str(COMPARISON_CSV_PATH),
        "report": str(REPORT_PATH),
        "equity_curve_csv": str(EQUITY_CURVE_CSV_PATH),
        "equity_curve_html": str(EQUITY_CURVE_HTML_PATH),
        "experiments": summary.to_dict(orient="records"),
        "comparison": comparison.to_dict(orient="records"),
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(build_report(summary, comparison), encoding="utf-8")
    print(f"[stage267] summary csv: {SUMMARY_CSV_PATH}")
    print(f"[stage267] summary json: {SUMMARY_JSON_PATH}")
    print(f"[stage267] comparison csv: {COMPARISON_CSV_PATH}")
    print(f"[stage267] report: {REPORT_PATH}")
    print(f"[stage267] equity html: {EQUITY_CURVE_HTML_PATH}")
    print(summary.to_string(index=False))
    print(comparison.to_string(index=False))


if __name__ == "__main__":
    main()
