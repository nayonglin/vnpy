from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    AI_TOP8_ELIGIBILITY_PATH,
    CAPITAL,
    CYCLE_WINDOWS,
    STRUCTURAL_UNIVERSE_PATH,
    load_static_products,
)
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (
    BASE_RISK_RATIO,
    CORR20_06_08_FLOOR35_OVERRIDES,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

EXPERIMENT_TAG: str = "qmt_roll_stage192_manual_pool_add_one_validation"
UNIVERSE_DIR: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_universes"
ELIGIBILITY_DIR: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_eligibility"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_report.md"
EQUITY_CURVE_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_equity_curves.csv"
EQUITY_CURVE_HTML_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_equity_curves.html"

CANDIDATE_PRODUCTS: tuple[str, ...] = ("UR.CZCE", "pg.DCE", "sn.SHFE", "eb.DCE", "fu.SHFE")
BASE_EXPERIMENT_NAME: str = "manual18_no_fixed_satellite"
AI_BASE_STRATEGY: str = "ai_top8_entry_filter"
EXCLUSION_MODE: str = "profit_only"


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _full_window() -> dict[str, Any]:
    return next(window for window in CYCLE_WINDOWS if str(window["window_name"]) == "full_2020_2026")


def _load_structural_universe() -> pd.DataFrame:
    if not STRUCTURAL_UNIVERSE_PATH.exists():
        raise FileNotFoundError(STRUCTURAL_UNIVERSE_PATH)
    df = pd.read_csv(STRUCTURAL_UNIVERSE_PATH)
    df["product_vt_symbol"] = df["product_vt_symbol"].astype(str)
    df["is_static_strategy_product"] = pd.to_numeric(
        df["is_static_strategy_product"],
        errors="coerce",
    ).fillna(0).astype(int)
    return df


def build_universe(experiment_name: str, satellites: tuple[str, ...]) -> Path:
    structural = _load_structural_universe()
    selected_products = set(load_static_products()) | set(satellites)
    missing = sorted(selected_products - set(structural["product_vt_symbol"].astype(str)))
    if missing:
        raise ValueError(f"{experiment_name} missing products from structural universe: {missing}")
    universe = structural[structural["product_vt_symbol"].isin(selected_products)].copy()
    universe.sort_values(["exchange", "product_vt_symbol"], inplace=True)
    UNIVERSE_DIR.mkdir(parents=True, exist_ok=True)
    path = UNIVERSE_DIR / f"{EXPERIMENT_TAG}_{experiment_name}_universe.csv"
    universe.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def build_post_signal_eligibility(experiment_name: str, satellites: tuple[str, ...]) -> tuple[Path, str]:
    if not AI_TOP8_ELIGIBILITY_PATH.exists():
        raise FileNotFoundError(AI_TOP8_ELIGIBILITY_PATH)
    df = pd.read_csv(AI_TOP8_ELIGIBILITY_PATH)
    top8 = df[df["strategy"].astype(str) == AI_BASE_STRATEGY].copy()
    if top8.empty:
        raise ValueError(f"{AI_BASE_STRATEGY} eligibility is empty")

    strategy_name = f"{EXPERIMENT_TAG}_{experiment_name}_entry_filter"
    eligibility = top8.copy()
    eligibility["strategy"] = strategy_name
    eligibility["score_type"] = f"ai_top8_plus_{experiment_name}"
    eligibility["top_n"] = 8 + len(satellites)

    rows: list[dict[str, Any]] = []
    for eval_date, group in eligibility.groupby("eval_date", sort=True):
        existing = set(group["product_vt_symbol"].astype(str))
        min_score = pd.to_numeric(group["score"], errors="coerce").min()
        base_score = float(min_score) if pd.notna(min_score) else 0.0
        max_rank = int(pd.to_numeric(group["score_rank"], errors="coerce").fillna(0).max())
        for offset, product in enumerate(satellites, start=1):
            if product in existing:
                continue
            rows.append(
                {
                    "strategy": strategy_name,
                    "score_type": f"ai_top8_plus_{experiment_name}",
                    "eval_date": eval_date,
                    "product_vt_symbol": product,
                    "score": base_score - 1e-6 * offset,
                    "score_rank": max_rank + offset,
                    "top_n": 8 + len(satellites),
                }
            )

    static_products = load_static_products()
    pre_signal_rows = [
        {
            "strategy": strategy_name,
            "score_type": "static18_pre_ai_boundary",
            "eval_date": "2019-12-31",
            "product_vt_symbol": product,
            "score": 0.0,
            "score_rank": rank,
            "top_n": len(static_products),
        }
        for rank, product in enumerate(static_products, start=1)
    ]

    if rows:
        eligibility = pd.concat([eligibility, pd.DataFrame(rows)], ignore_index=True)
    eligibility = pd.concat([pd.DataFrame(pre_signal_rows), eligibility], ignore_index=True)
    eligibility.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    ELIGIBILITY_DIR.mkdir(parents=True, exist_ok=True)
    path = ELIGIBILITY_DIR / f"{EXPERIMENT_TAG}_{experiment_name}_eligibility.csv"
    eligibility.to_csv(path, index=False, encoding="utf-8-sig")
    return path, strategy_name


def experiment_specs() -> tuple[dict[str, Any], ...]:
    specs: list[dict[str, Any]] = [
        {
            "experiment_name": BASE_EXPERIMENT_NAME,
            "satellite_products": (),
            "role": "manual18_control",
        }
    ]
    for product in CANDIDATE_PRODUCTS:
        specs.append(
            {
                "experiment_name": f"manual18_plus_{product.replace('.', '_')}",
                "satellite_products": (product,),
                "role": "add_one_candidate",
            }
        )
    return tuple(specs)


def _strategy_overrides(universe_path: Path, eligibility_path: Path, strategy_name: str, satellites: tuple[str, ...]) -> dict[str, Any]:
    overrides = {
        **CORR20_06_08_FLOOR35_OVERRIDES,
        "product_universe_csv_path": str(universe_path),
        "enable_ai_product_pool_filter": True,
        "ai_product_pool_eligibility_path": str(eligibility_path),
        "ai_product_pool_strategy": strategy_name,
    }
    if satellites:
        overrides["streak_risk_state_excluded_products"] = ",".join(satellites)
        overrides["streak_risk_state_exclusion_mode"] = EXCLUSION_MODE
    return overrides


def run_experiments() -> pd.DataFrame:
    window = _full_window()
    rows: list[dict[str, Any]] = []
    for spec in experiment_specs():
        experiment_name = str(spec["experiment_name"])
        satellites = tuple(spec["satellite_products"])
        universe_path = build_universe(experiment_name, satellites)
        eligibility_path, strategy_name = build_post_signal_eligibility(experiment_name, satellites)
        overrides = _strategy_overrides(universe_path, eligibility_path, strategy_name, satellites)
        print(f"[stage192] running {experiment_name}: {','.join(satellites) if satellites else 'none'}")
        _, _, statistics = run_backtest(
            risk_ratio=BASE_RISK_RATIO,
            strategy_overrides=overrides,
            analysis_start=window["analysis_start"],
            analysis_end=window["analysis_end"],
            capital=CAPITAL,
            save_artifacts=True,
            include_start_year_sweep=False,
            file_prefix=f"{EXPERIMENT_TAG}_{experiment_name}",
            chart_title=f"Stage192 {experiment_name}",
        )
        rows.append(
            build_summary_row(
                statistics,
                analysis_start=window["analysis_start"],
                analysis_end=window["analysis_end"],
                experiment_name=experiment_name,
                role=str(spec["role"]),
                satellite_products=",".join(satellites),
                satellite_count=len(satellites),
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
    base = summary[summary["experiment_name"] == BASE_EXPERIMENT_NAME].iloc[0]
    fu_name = "manual18_plus_fu_SHFE"
    fu = summary[summary["experiment_name"] == fu_name]
    fu_row = fu.iloc[0] if not fu.empty else base
    rows: list[dict[str, Any]] = []
    for row in summary.to_dict(orient="records"):
        rows.append(
            {
                "experiment_name": row["experiment_name"],
                "satellite_products": row.get("satellite_products", ""),
                "end_balance": row["end_balance"],
                "total_return_pct": row["total_return_pct"],
                "max_dd_percent": row["max_dd_percent"],
                "sharpe_ratio": row["sharpe_ratio"],
                "total_trade_count": row["total_trade_count"],
                "win_ratio_pct": row["win_ratio_pct"],
                "end_balance_diff_vs_manual18": _safe_float(row["end_balance"]) - _safe_float(base["end_balance"]),
                "return_diff_vs_manual18": _safe_float(row["total_return_pct"]) - _safe_float(base["total_return_pct"]),
                "dd_diff_vs_manual18": _safe_float(row["max_dd_percent"]) - _safe_float(base["max_dd_percent"]),
                "sharpe_diff_vs_manual18": _safe_float(row["sharpe_ratio"]) - _safe_float(base["sharpe_ratio"]),
                "end_balance_diff_vs_fu": _safe_float(row["end_balance"]) - _safe_float(fu_row["end_balance"]),
                "return_diff_vs_fu": _safe_float(row["total_return_pct"]) - _safe_float(fu_row["total_return_pct"]),
                "dd_diff_vs_fu": _safe_float(row["max_dd_percent"]) - _safe_float(fu_row["max_dd_percent"]),
                "sharpe_diff_vs_fu": _safe_float(row["sharpe_ratio"]) - _safe_float(fu_row["sharpe_ratio"]),
            }
        )
    return pd.DataFrame(rows)


def _load_equity_curve(experiment_name: str) -> pd.DataFrame:
    path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_{experiment_name}_daily_equity.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    date_column = "date" if "date" in df.columns else df.columns[0]
    balance_column = "balance" if "balance" in df.columns else "end_balance"
    if balance_column not in df.columns:
        numeric_cols = [column for column in df.columns if column != date_column and pd.api.types.is_numeric_dtype(df[column])]
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
            fig.add_trace(
                go.Scatter(
                    x=group["date"],
                    y=group["balance"],
                    mode="lines",
                    name=str(name),
                )
            )
        fig.update_layout(
            title="Stage192 Manual Pool Add-One Equity Curves",
            xaxis_title="Date",
            yaxis_title="Balance",
            hovermode="x unified",
            template="plotly_white",
            width=1200,
            height=720,
        )
        fig.write_html(EQUITY_CURVE_HTML_PATH, include_plotlyjs="cdn")
    except Exception as exc:
        EQUITY_CURVE_HTML_PATH.write_text(
            "<html><body><h1>Stage192 Equity Curves</h1>"
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
        "satellite_products",
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
        "satellite_products",
        "end_balance_diff_vs_manual18",
        "return_diff_vs_manual18",
        "dd_diff_vs_manual18",
        "sharpe_diff_vs_manual18",
        "end_balance_diff_vs_fu",
        "return_diff_vs_fu",
        "dd_diff_vs_fu",
        "sharpe_diff_vs_fu",
    ]
    return "\n".join(
        [
            "# Stage192 Manual Pool Add-One Validation",
            "",
            "## Design",
            "",
            "- Control: manual 18 products with the original monthly AI top8 post-signal filter.",
            "- Candidates: add exactly one fixed satellite product after the monthly AI signal starts.",
            "- This is a candidate screen, not a promotion decision.",
            "",
            "## Results",
            "",
            _markdown_table(summary[result_columns]),
            "",
            "## Comparison",
            "",
            _markdown_table(comparison[compare_columns]),
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
    curves = build_equity_curves(summary)
    write_equity_curve_html(curves)

    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    payload = {
        "experiment_tag": EXPERIMENT_TAG,
        "candidate_products": list(CANDIDATE_PRODUCTS),
        "capital": CAPITAL,
        "base_risk_ratio": BASE_RISK_RATIO,
        "summary_csv": str(SUMMARY_CSV_PATH),
        "summary_json": str(SUMMARY_JSON_PATH),
        "report": str(REPORT_PATH),
        "equity_curve_csv": str(EQUITY_CURVE_CSV_PATH),
        "equity_curve_html": str(EQUITY_CURVE_HTML_PATH),
        "experiments": summary.to_dict(orient="records"),
        "comparison": comparison.to_dict(orient="records"),
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(build_report(summary, comparison), encoding="utf-8")
    print(f"[stage192] summary csv: {SUMMARY_CSV_PATH}")
    print(f"[stage192] summary json: {SUMMARY_JSON_PATH}")
    print(f"[stage192] report: {REPORT_PATH}")
    print(f"[stage192] equity html: {EQUITY_CURVE_HTML_PATH}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
