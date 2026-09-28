"""Build the frozen, label-free account-context feature contract."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from typing import Final

import numpy as np
import pandas as pd


WINDOW_DAYS: Final = 120
MIN_DOWNSIDE_DAYS: Final = 20
CONTEXT_FEATURE_COLUMNS: Final = [
    "candidate_top9_aggregate_corr_120d_delta_vs_rank10",
    "candidate_top9_downside_corr_120d_delta_vs_rank10",
    "candidate_top9_active_overlap_rate_120d_delta_vs_rank10",
    "candidate_top9_joint_loss_rate_120d_delta_vs_rank10",
    "top9_plus_candidate_drawdown_improvement_ratio_120d_vs_rank10",
    "top9_plus_candidate_sharpe_improvement_120d_vs_rank10",
]
BASE_FEATURE_COLUMNS: Final = [
    "formal_probability_delta_vs_rank10",
    "formal_rank_distance",
    "pnl120_z_delta_vs_rank10",
    "pnl60_z_delta_vs_rank10",
    "sharpe60_z_delta_vs_rank10",
    "positive_day60_z_delta_vs_rank10",
    "opened60_z_delta_vs_rank10",
    "slippage60_z_delta_vs_rank10",
    "drawdown60_z_delta_vs_rank10",
]
MODEL_FEATURE_COLUMNS: Final = [
    *BASE_FEATURE_COLUMNS,
    *CONTEXT_FEATURE_COLUMNS,
]

LINE = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
UPSTREAM = (
    WORKSPACE_ROOT
    / "research/lines/futures_trend_ai_xgboost_ensemble"
)
INPUT_PATHS: Final = {
    "formal_full_ranking": (
        UPSTREAM
        / "artifacts/stage009_formal_full_ranking_recovery/"
        "formal_full_ranking.csv"
    ),
    "base_feature_panel": (
        UPSTREAM
        / "artifacts/stage014_prelabel_feature_contract/"
        "prelabel_feature_panel.csv"
    ),
    "position_changes": Path(
        "/Users/bytedance/Library/Application Support/"
        "qmt-roll-stage179/production-live/official-live/"
        "qmt_roll_stage183_ai_source_floor35_"
        "position_changes_2020_2026_04.csv"
    ),
    "spec": (
        LINE
        / "stages/20260902_1107_stage000_account_context_design.md"
    ),
}
EXPECTED_SHA256: Final = {
    "formal_full_ranking": (
        "b2cb417b6c57a7679ae43a1e564c1e79683ca9644b3434cb6a3bfc9e039fcfc0"
    ),
    "base_feature_panel": (
        "e8272438cd69fe784b236ac91763f4ec0da71d2b711cd38b576c5e66d237f5fd"
    ),
    "position_changes": (
        "17c81f2dbb30f836b544161c3fc4d4bd6415151d89b8f8937378739e868c21aa"
    ),
    "spec": (
        "1591494f782fd12c6d5fd4bb2da48d9d0b7c1d54b0bfedb7616d9cb61f565d34"
    ),
}
OUT = LINE / "artifacts/stage001_account_context_feature_contract"
DESIGN_FROZEN_AT: Final = "2026-09-02T11:07:00+08:00"


class Stage001ContractError(RuntimeError):
    """Raised when a frozen Stage001 contract condition is violated."""


def _vectors(*values: np.ndarray) -> tuple[np.ndarray, ...]:
    arrays = tuple(
        np.asarray(value, dtype=float).reshape(-1) for value in values
    )
    if any(array.size != WINDOW_DAYS for array in arrays):
        raise Stage001ContractError("context_window_length_not_120")
    if any(not np.isfinite(array).all() for array in arrays):
        raise Stage001ContractError("context_vector_nonfinite")
    return arrays


def _pearson(left: np.ndarray, right: np.ndarray, prefix: str) -> float:
    if (
        float(np.std(left, ddof=1)) <= 0.0
        or float(np.std(right, ddof=1)) <= 0.0
    ):
        raise Stage001ContractError(
            f"{prefix}_standard_deviation_zero"
        )
    value = float(np.corrcoef(left, right)[0, 1])
    if not math.isfinite(value):
        raise Stage001ContractError(f"{prefix}_correlation_nonfinite")
    return value


def _active_overlap(
    candidate: np.ndarray,
    top9: np.ndarray,
    prefix: str,
) -> float:
    active = candidate != 0.0
    active_days = int(active.sum())
    if active_days == 0:
        raise Stage001ContractError(f"{prefix}_activity_days_zero")
    return float(np.logical_and(active, top9 != 0.0).sum() / active_days)


def _drawdown(values: np.ndarray) -> float:
    cumulative = np.cumsum(values)
    return float(
        np.min(cumulative - np.maximum.accumulate(cumulative))
    )


def _sharpe(values: np.ndarray, prefix: str) -> float:
    scale = float(np.std(values, ddof=1))
    if scale <= 0.0:
        raise Stage001ContractError(
            f"{prefix}_portfolio_standard_deviation_zero"
        )
    return float(np.mean(values) / scale * math.sqrt(252.0))


def compute_context_feature_deltas(
    top9_aggregate: np.ndarray,
    rank10: np.ndarray,
    candidate: np.ndarray,
) -> dict[str, float]:
    top9, baseline, challenger = _vectors(
        top9_aggregate, rank10, candidate
    )
    downside = top9 < 0.0
    if int(downside.sum()) < MIN_DOWNSIDE_DAYS:
        raise Stage001ContractError("top9_downside_days_below_20")

    baseline_overlap = _active_overlap(baseline, top9, "rank10")
    challenger_overlap = _active_overlap(challenger, top9, "candidate")
    baseline_corr = _pearson(baseline, top9, "rank10_top9")
    challenger_corr = _pearson(challenger, top9, "candidate_top9")
    baseline_down_corr = _pearson(
        baseline[downside], top9[downside], "rank10_top9_downside"
    )
    challenger_down_corr = _pearson(
        challenger[downside],
        top9[downside],
        "candidate_top9_downside",
    )
    baseline_joint_loss = float(
        np.logical_and(baseline < 0.0, top9 < 0.0).sum()
        / WINDOW_DAYS
    )
    challenger_joint_loss = float(
        np.logical_and(challenger < 0.0, top9 < 0.0).sum()
        / WINDOW_DAYS
    )
    baseline_portfolio = top9 + baseline
    challenger_portfolio = top9 + challenger
    baseline_drawdown = _drawdown(baseline_portfolio)
    if not baseline_drawdown < 0.0:
        raise Stage001ContractError(
            "rank10_portfolio_drawdown_not_negative"
        )

    values = [
        challenger_corr - baseline_corr,
        challenger_down_corr - baseline_down_corr,
        challenger_overlap - baseline_overlap,
        challenger_joint_loss - baseline_joint_loss,
        (
            _drawdown(challenger_portfolio) - baseline_drawdown
        )
        / abs(baseline_drawdown),
        _sharpe(challenger_portfolio, "candidate")
        - _sharpe(baseline_portfolio, "rank10"),
    ]
    if not np.isfinite(np.asarray(values, dtype=float)).all():
        raise Stage001ContractError("context_feature_nonfinite")
    if np.array_equal(challenger, baseline):
        return {name: 0.0 for name in CONTEXT_FEATURE_COLUMNS}
    return {
        name: float(value)
        for name, value in zip(CONTEXT_FEATURE_COLUMNS, values)
    }


def product_from_contract(vt_symbol: object) -> str:
    raw = str(vt_symbol)
    if "." not in raw:
        return raw
    symbol, exchange = raw.split(".", 1)
    match = re.match(r"^([A-Za-z]+)", symbol)
    product = match.group(1) if match else symbol
    return f"{product}.{exchange}"


def build_product_daily(
    position_changes: pd.DataFrame,
    products: list[str],
) -> pd.DataFrame:
    required = {"date", "vt_symbol", "net_pnl"}
    if missing := sorted(required - set(position_changes.columns)):
        raise Stage001ContractError(
            f"position_change_columns_missing:{','.join(missing)}"
        )
    product_list = sorted(str(product) for product in products)
    if not product_list or len(product_list) != len(set(product_list)):
        raise Stage001ContractError("formal_product_universe_invalid")

    frame = position_changes.loc[
        :, ["date", "vt_symbol", "net_pnl"]
    ].copy()
    frame["date"] = pd.to_datetime(
        frame["date"], errors="raise"
    ).dt.normalize()
    frame["product_vt_symbol"] = frame["vt_symbol"].map(
        product_from_contract
    )
    frame["net_pnl"] = pd.to_numeric(
        frame["net_pnl"], errors="raise"
    ).astype(float)
    if not np.isfinite(frame["net_pnl"].to_numpy(float)).all():
        raise Stage001ContractError("position_change_net_pnl_nonfinite")

    grouped = (
        frame.groupby(
            ["date", "product_vt_symbol"], as_index=False
        )["net_pnl"]
        .sum()
    )
    dates = pd.DatetimeIndex(sorted(grouped["date"].unique()))
    if dates.empty:
        raise Stage001ContractError("position_change_dates_empty")
    index = pd.MultiIndex.from_product(
        [dates, product_list],
        names=["date", "product_vt_symbol"],
    )
    result = (
        grouped.set_index(["date", "product_vt_symbol"])
        .reindex(index)
        .reset_index()
    )
    result["net_pnl"] = result["net_pnl"].fillna(0.0).astype(float)
    return result


def _trailing_product_matrix(
    product_daily: pd.DataFrame,
    eval_date: pd.Timestamp,
    products: Sequence[str],
) -> pd.DataFrame:
    required = {"date", "product_vt_symbol", "net_pnl"}
    if missing := sorted(required - set(product_daily.columns)):
        raise Stage001ContractError(
            f"product_daily_columns_missing:{','.join(missing)}"
        )
    if product_daily.duplicated(
        ["date", "product_vt_symbol"]
    ).any():
        raise Stage001ContractError("product_daily_date_product_duplicate")

    cutoff = pd.Timestamp(eval_date).normalize()
    dates = pd.DatetimeIndex(
        sorted(
            product_daily.loc[
                product_daily["date"].le(cutoff), "date"
            ].unique()
        )
    )
    if len(dates) < WINDOW_DAYS:
        raise Stage001ContractError("context_window_dates_below_120")
    window_dates = dates[-WINDOW_DAYS:]
    window = product_daily[
        product_daily["date"].isin(window_dates)
        & product_daily["product_vt_symbol"].isin(products)
    ].pivot(
        index="date",
        columns="product_vt_symbol",
        values="net_pnl",
    )
    window = window.reindex(index=window_dates, columns=list(products))
    if (
        window.shape != (WINDOW_DAYS, len(products))
        or window.isna().any().any()
    ):
        raise Stage001ContractError(
            "context_window_product_grid_incomplete"
        )
    if not np.isfinite(window.to_numpy(float)).all():
        raise Stage001ContractError("context_window_product_nonfinite")
    if window.index.max() > cutoff:
        raise Stage001ContractError("context_window_future_date_used")
    return window


def build_context_feature_panel(
    base_panel: pd.DataFrame,
    formal_ranking: pd.DataFrame,
    product_daily: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    base_required = {
        "eval_date",
        "product_vt_symbol",
        "score_rank",
        *BASE_FEATURE_COLUMNS,
    }
    ranking_required = {
        "eval_date",
        "product_vt_symbol",
        "score_rank",
    }
    if missing := sorted(base_required - set(base_panel.columns)):
        raise Stage001ContractError(
            f"base_panel_columns_missing:{','.join(missing)}"
        )
    if missing := sorted(ranking_required - set(formal_ranking.columns)):
        raise Stage001ContractError(
            f"formal_ranking_columns_missing:{','.join(missing)}"
        )

    base = base_panel.copy()
    ranking = formal_ranking.copy()
    daily = product_daily.copy()
    base["eval_date"] = pd.to_datetime(
        base["eval_date"], errors="raise"
    ).dt.normalize()
    ranking["eval_date"] = pd.to_datetime(
        ranking["eval_date"], errors="raise"
    ).dt.normalize()
    daily["date"] = pd.to_datetime(
        daily["date"], errors="raise"
    ).dt.normalize()
    base["score_rank"] = pd.to_numeric(
        base["score_rank"], errors="raise"
    ).astype(int)
    ranking["score_rank"] = pd.to_numeric(
        ranking["score_rank"], errors="raise"
    ).astype(int)
    if base.duplicated(["eval_date", "score_rank"]).any():
        raise Stage001ContractError("base_panel_month_rank_duplicate")

    rows: list[dict[str, object]] = []
    audits: list[dict[str, object]] = []
    for eval_date, month_base in base.groupby("eval_date", sort=True):
        month_base = month_base.sort_values(
            "score_rank", kind="mergesort"
        )
        if month_base["score_rank"].tolist() != list(range(10, 19)):
            raise Stage001ContractError(
                "base_panel_month_ranks_not_10_to_18"
            )
        month_ranking = ranking[
            ranking["eval_date"].eq(eval_date)
        ].sort_values("score_rank", kind="mergesort")
        if month_ranking["score_rank"].tolist() != list(range(1, 19)):
            raise Stage001ContractError(
                "formal_ranking_month_ranks_not_1_to_18"
            )
        products = month_ranking[
            "product_vt_symbol"
        ].astype(str).tolist()
        if len(set(products)) != 18:
            raise Stage001ContractError(
                "formal_ranking_month_product_duplicate"
            )

        matrix = _trailing_product_matrix(daily, eval_date, products)
        top9_products = products[:9]
        rank10_product = products[9]
        top9 = matrix.loc[:, top9_products].sum(axis=1).to_numpy(float)
        baseline = matrix.loc[:, rank10_product].to_numpy(float)
        for source_row in month_base.to_dict("records"):
            product = str(source_row["product_vt_symbol"])
            expected_product = products[int(source_row["score_rank"]) - 1]
            if product != expected_product:
                raise Stage001ContractError(
                    "base_panel_formal_ranking_identity_mismatch"
                )
            context = compute_context_feature_deltas(
                top9,
                baseline,
                matrix.loc[:, product].to_numpy(float),
            )
            rows.append({**source_row, **context})

        audits.append(
            {
                "eval_date": eval_date,
                "window_start": matrix.index.min(),
                "window_end": matrix.index.max(),
                "window_days": int(len(matrix)),
                "top9_downside_days": int((top9 < 0.0).sum()),
                "rank_count": int(len(month_ranking)),
                "candidate_count": int(len(month_base)),
                "max_source_date_used": matrix.index.max(),
            }
        )

    panel = pd.DataFrame(rows).sort_values(
        ["eval_date", "score_rank"], kind="mergesort"
    )
    panel.reset_index(drop=True, inplace=True)
    context_values = panel.loc[
        :, CONTEXT_FEATURE_COLUMNS
    ].to_numpy(float)
    if not np.isfinite(context_values).all():
        raise Stage001ContractError("context_panel_nonfinite")
    rank10_rows = panel["score_rank"].eq(10)
    if not (
        panel.loc[
            rank10_rows, CONTEXT_FEATURE_COLUMNS
        ].to_numpy(float)
        == 0.0
    ).all():
        raise Stage001ContractError(
            "rank10_context_features_not_exact_zero"
        )
    audit = pd.DataFrame(audits).sort_values(
        "eval_date", kind="mergesort"
    )
    audit.reset_index(drop=True, inplace=True)
    return panel, audit


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_inputs(
    paths: Mapping[str, Path],
    expected: Mapping[str, str],
) -> None:
    if set(paths) != set(expected):
        raise Stage001ContractError("input_identity_keys_mismatch")
    for key in sorted(expected):
        path = Path(paths[key])
        if not path.is_file():
            raise Stage001ContractError(f"input_missing:{key}")
        if sha256_file(path) != expected[key]:
            raise Stage001ContractError(f"input_sha256_drift:{key}")


def _read_csv(
    path: Path,
    read_paths: list[str],
    **kwargs: Any,
) -> pd.DataFrame:
    read_paths.append(str(path))
    return pd.read_csv(path, **kwargs)


def _validate_published_panel(
    panel: pd.DataFrame,
    audit: pd.DataFrame,
) -> tuple[dict[str, int], dict[str, int], dict[str, Any]]:
    months = int(panel["eval_date"].nunique())
    if len(panel) != 459 or months != 51:
        raise Stage001ContractError(
            f"published_panel_shape:{len(panel)}:{months}"
        )
    ranks = panel.groupby("eval_date", sort=True)["score_rank"].apply(list)
    if not ranks.map(lambda values: values == list(range(10, 19))).all():
        raise Stage001ContractError("published_panel_rank_shape")
    month_split = panel.loc[:, ["eval_date", "split"]].drop_duplicates()
    if month_split.duplicated("eval_date").any():
        raise Stage001ContractError("published_panel_month_split_duplicate")
    split_counts = month_split["split"].value_counts().to_dict()
    expected_splits = {"development": 39, "sealed_holdout": 12}
    if split_counts != expected_splits:
        raise Stage001ContractError(
            f"published_panel_split_shape:{split_counts}"
        )

    context = panel.loc[:, CONTEXT_FEATURE_COLUMNS].to_numpy(float)
    context_nonfinite = int((~np.isfinite(context)).sum())
    rank10_nonzero = int(
        (
            panel.loc[
                panel["score_rank"].eq(10), CONTEXT_FEATURE_COLUMNS
            ].to_numpy(float)
            != 0.0
        ).sum()
    )
    quality = {
        "context_nonfinite_cells": context_nonfinite,
        "rank10_nonzero_context_cells": rank10_nonzero,
    }
    if quality != {
        "context_nonfinite_cells": 0,
        "rank10_nonzero_context_cells": 0,
    }:
        raise Stage001ContractError(f"published_panel_quality:{quality}")

    future_violations = int(
        audit["max_source_date_used"].gt(audit["eval_date"]).sum()
    )
    pit = {
        "window_days_min": int(audit["window_days"].min()),
        "window_days_max": int(audit["window_days"].max()),
        "minimum_top9_downside_days": int(
            audit["top9_downside_days"].min()
        ),
        "max_source_date_used": (
            audit["max_source_date_used"].max().date().isoformat()
        ),
        "future_date_violations": future_violations,
    }
    if (
        pit["window_days_min"] != WINDOW_DAYS
        or pit["window_days_max"] != WINDOW_DAYS
        or pit["minimum_top9_downside_days"] < MIN_DOWNSIDE_DAYS
        or pit["future_date_violations"] != 0
    ):
        raise Stage001ContractError(f"published_panel_pit:{pit}")
    panel_shape = {
        "rows": 459,
        "months": 51,
        "ranks_per_month": 9,
        "development_months": 39,
        "sealed_holdout_months": 12,
    }
    return panel_shape, quality, pit


def _write_artifacts(
    output_dir: Path,
    panel: pd.DataFrame,
    audit: pd.DataFrame,
    contract: dict[str, Any],
) -> None:
    output_dir = Path(output_dir)
    temp_dir = output_dir.with_name(f"{output_dir.name}.tmp")
    if output_dir.exists():
        raise Stage001ContractError("stage001_output_already_exists")
    if temp_dir.exists():
        raise Stage001ContractError("stage001_temp_output_already_exists")
    temp_dir.mkdir(parents=True, exist_ok=False)

    panel.to_csv(
        temp_dir / "prelabel_feature_panel.csv",
        index=False,
        encoding="utf-8-sig",
        float_format="%.17g",
        date_format="%Y-%m-%d",
    )
    audit.to_csv(
        temp_dir / "window_audit.csv",
        index=False,
        encoding="utf-8-sig",
        date_format="%Y-%m-%d",
    )
    (temp_dir / "feature_contract.json").write_text(
        json.dumps(
            contract,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    report = (
        "# Stage001 XGBoost账户组合上下文标签前特征合同\n\n"
        f"- 决策：`{contract['decision']}`。\n"
        "- 特征：15项（原9项+账户组合上下文6项）；"
        "面板：459行/51个月/rank10..18。\n"
        f"- PIT窗口：{contract['pit']['window_days_min']}日；"
        f"最少Top9下行日：{contract['pit']['minimum_top9_downside_days']}；"
        f"未来日期违规：{contract['pit']['future_date_violations']}。\n"
        f"- 上下文非有限单元：{contract['quality']['context_nonfinite_cells']}；"
        "rank10非零上下文单元："
        f"{contract['quality']['rank10_nonzero_context_cells']}。\n"
        "- 未读取账户标签、未训练模型、未回测、未连接CTP、"
        "未调用订单API。\n"
    )
    (temp_dir / "report.md").write_text(report, encoding="utf-8")

    manifest_names = [
        "feature_contract.json",
        "prelabel_feature_panel.csv",
        "report.md",
        "window_audit.csv",
    ]
    manifest = {
        name: sha256_file(temp_dir / name)
        for name in manifest_names
    }
    (temp_dir / "artifact_manifest.json").write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    temp_dir.rename(output_dir)


def run_stage001(
    output_dir: Path,
    input_paths: Mapping[str, Path] = INPUT_PATHS,
    expected_sha256: Mapping[str, str] = EXPECTED_SHA256,
) -> dict[str, Any]:
    _verify_inputs(input_paths, expected_sha256)
    read_paths: list[str] = []
    ranking = _read_csv(
        Path(input_paths["formal_full_ranking"]), read_paths
    )
    base_panel = _read_csv(
        Path(input_paths["base_feature_panel"]), read_paths
    )
    position_changes = _read_csv(
        Path(input_paths["position_changes"]),
        read_paths,
        usecols=["date", "vt_symbol", "net_pnl"],
    )

    eval_dates = set(
        pd.to_datetime(base_panel["eval_date"], errors="raise")
        .dt.normalize()
        .tolist()
    )
    ranking_dates = pd.to_datetime(
        ranking["eval_date"], errors="raise"
    ).dt.normalize()
    formal_products = sorted(
        ranking.loc[
            ranking_dates.isin(eval_dates), "product_vt_symbol"
        ].astype(str).unique()
    )
    if len(formal_products) != 18:
        raise Stage001ContractError(
            f"formal_product_count_not_18:{len(formal_products)}"
        )
    product_daily = build_product_daily(
        position_changes, formal_products
    )
    panel, audit = build_context_feature_panel(
        base_panel, ranking, product_daily
    )
    panel_shape, quality, pit = _validate_published_panel(panel, audit)

    contract: dict[str, Any] = {
        "line_id": "futures_trend_xgboost_account_context",
        "stage": "Stage001",
        "design_frozen_at": DESIGN_FROZEN_AT,
        "decision": "stage001_account_context_prelabel_contract_pass",
        "formal_release_id": (
            "m0005_20260901T165450+0800_1961d98ccb2b"
        ),
        "feature_count": len(MODEL_FEATURE_COLUMNS),
        "base_features": BASE_FEATURE_COLUMNS,
        "context_features": CONTEXT_FEATURE_COLUMNS,
        "model_features": MODEL_FEATURE_COLUMNS,
        "panel": panel_shape,
        "pit": pit,
        "quality": quality,
        "input_identities": {
            key: {
                "path": str(Path(input_paths[key])),
                "sha256": expected_sha256[key],
            }
            for key in sorted(expected_sha256)
        },
        "read_paths": sorted(read_paths),
        "account_label_files_read": [],
        "account_label_values_read": False,
        "runs_backtest": False,
        "trains_model": False,
        "ctp_connected": False,
        "order_api_called_count": 0,
    }
    _write_artifacts(output_dir, panel, audit, contract)
    return contract


def main() -> None:
    contract = run_stage001(OUT)
    print(
        json.dumps(
            contract,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
