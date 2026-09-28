"""Audit point-in-time physical and positioning feature coverage before labels."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd


LINE_ID: Final = "futures_trend_xgboost_pit_physical_positioning_context"
STAGE: Final = "Stage001"
FORMAL_RELEASE_ID: Final = "m0005_20260901T165450+0800_1961d98ccb2b"
LINE_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
OUTPUT_DIR = LINE_DIR / "artifacts/stage001_physical_positioning_coverage"
SOURCE_LINE = WORKSPACE_ROOT / "research/lines/futures_trend_rebuilt_c9_15w_optimization"
RANKING_LINE = WORKSPACE_ROOT / "research/lines/futures_trend_xgboost_pit_market_context_after_listing"
SUPPLY_DIR = WORKSPACE_ROOT / "examples/portfolio_backtesting/backtest_outputs/external_supply_demand_cache"

INPUT_PATHS: Final = {
    "ranked_panel": RANKING_LINE / "artifacts/stage001_market_context_coverage/ranked_a_panel.csv",
    "basis_2020_2022": SUPPLY_DIR / "supply_demand_basis_20200101_20221231.csv",
    "basis_2023_2026": SUPPLY_DIR / "supply_demand_basis_20230101_20260417.csv",
    "warehouse_2020_2022": SUPPLY_DIR / "supply_demand_warehouse_20200101_20221231.csv",
    "warehouse_2023_2026": SUPPLY_DIR / "supply_demand_warehouse_20230101_20260417.csv",
    "member_rank_raw": SOURCE_LINE
    / "outputs/stage080_member_rank_2022_backfill_feasibility/"
    "rebuilt_c9_stage080_member_rank_2022_backfill_feasibility_combined_raw_"
    "stage080_member_rank_2022_backfill_feasibility_v1.csv",
    "spec": LINE_DIR / "stages/20260903_0250_stage000_physical_positioning_preregistration.md",
}
EXPECTED_SHA256: Final = {
    "ranked_panel": "1c841acc3a76a1ecd0f5f3572013c3c97cf4092ac456657f1b87ad3031c14df2",
    "basis_2020_2022": "d32bac39fd9c4ce057291768bbb9032520469127c90b9ef13caf810611c6796a",
    "basis_2023_2026": "150b1f13c07bb02a3ce410e46fec4d4b5c491930c77a9133fd601f3f93f19170",
    "warehouse_2020_2022": "86d6964ee422c909376faf130ae53a1bac9800d59a8e7a0180ab52835b39349f",
    "warehouse_2023_2026": "1385b1ff9effad4c0bf103d042123d46b20694a84e2df582be18fb6b4643796c",
    "member_rank_raw": "9b22de83f4530859bcb440e016ab89017d5e453f1660dd4b841aa792ce43afbf",
    "spec": "ac11ccf708407958a4d26e968c259f520522ccd188ef684738473b51e1195303",
}

PANEL_COLUMNS: Final = [
    "eval_date",
    "product_vt_symbol",
    "pit_logistic_probability",
    "window_id",
    "a_rank",
    "role",
]
BASIS_COLUMNS: Final = ["date", "symbol", "dom_basis_rate", "near_basis_rate"]
WAREHOUSE_COLUMNS: Final = [
    "date",
    "product_code",
    "warehouse_receipt_quantity",
    "warehouse_receipt_change",
]
MEMBER_COLUMNS: Final = [
    "date",
    "symbol",
    "variety",
    "vol_top20",
    "long_open_interest_top20",
    "short_open_interest_top20",
    "long_open_interest_chg_top20",
    "short_open_interest_chg_top20",
]
FAMILY_AVAILABLE_COLUMNS: Final = {
    "basis": "basis_available",
    "warehouse": "warehouse_available",
    "member": "member_available",
}


class Stage001Error(RuntimeError):
    """Raised when the frozen coverage audit must fail closed."""


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


def _date_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, (int, np.integer)):
        return f"{int(value):08d}"
    if isinstance(value, (float, np.floating)) and np.isfinite(value) and float(value).is_integer():
        return f"{int(value):08d}"
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        return f"{int(float(text)):08d}"
    return text


def _parse_dates(series: pd.Series) -> pd.Series:
    text = series.map(_date_text)
    compact = text.str.fullmatch(r"\d{8}")
    parsed = pd.to_datetime(text, errors="coerce")
    if compact.any():
        parsed.loc[compact] = pd.to_datetime(text.loc[compact], format="%Y%m%d", errors="coerce")
    return parsed.dt.normalize()


def _product_code(value: Any) -> str:
    text = str(value).strip()
    if "." in text:
        text = text.split(".", 1)[0]
    return "".join(character for character in text if character.isalpha()).upper()


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce")


def _normalise_panel(panel: pd.DataFrame) -> pd.DataFrame:
    missing = set(PANEL_COLUMNS).difference(panel.columns)
    if missing:
        raise Stage001Error(f"panel_columns_missing:{','.join(sorted(missing))}")
    result = panel[PANEL_COLUMNS].copy()
    result["eval_date"] = _parse_dates(result["eval_date"])
    result["product_vt_symbol"] = result["product_vt_symbol"].astype(str).str.strip()
    result["product_code"] = result["product_vt_symbol"].map(_product_code)
    result["pit_logistic_probability"] = _numeric(result, "pit_logistic_probability")
    result["a_rank"] = _numeric(result, "a_rank").astype("Int64")
    if result[["eval_date", "pit_logistic_probability", "a_rank"]].isna().any().any():
        raise Stage001Error("panel_required_value_missing")
    if result["product_code"].eq("").any():
        raise Stage001Error("panel_product_code_empty")
    if result.duplicated(["eval_date", "product_vt_symbol"]).any():
        raise Stage001Error("panel_duplicate_eval_product")
    return result.sort_values(["eval_date", "a_rank", "product_vt_symbol"], kind="mergesort").reset_index(drop=True)


def _normalise_basis(basis: pd.DataFrame) -> pd.DataFrame:
    missing = set(BASIS_COLUMNS).difference(basis.columns)
    if missing:
        raise Stage001Error(f"basis_columns_missing:{','.join(sorted(missing))}")
    result = basis[BASIS_COLUMNS].copy()
    result["feature_date"] = _parse_dates(result.pop("date"))
    result["product_code"] = result.pop("symbol").map(_product_code)
    result["basis_dom_rate"] = _numeric(result, "dom_basis_rate")
    result["basis_near_rate"] = _numeric(result, "near_basis_rate")
    result = result.drop(columns=["dom_basis_rate", "near_basis_rate"])
    result = result.dropna(subset=["feature_date"])
    result = result[result["product_code"].ne("")]
    return (
        result.sort_values(["product_code", "feature_date"], kind="mergesort")
        .groupby(["product_code", "feature_date"], as_index=False)
        .last()
    )


def _normalise_warehouse(warehouse: pd.DataFrame) -> pd.DataFrame:
    missing = set(WAREHOUSE_COLUMNS).difference(warehouse.columns)
    if missing:
        raise Stage001Error(f"warehouse_columns_missing:{','.join(sorted(missing))}")
    result = warehouse[WAREHOUSE_COLUMNS].copy()
    result["feature_date"] = _parse_dates(result.pop("date"))
    result["product_code"] = result["product_code"].map(_product_code)
    result["warehouse_receipt_quantity"] = _numeric(result, "warehouse_receipt_quantity")
    result["warehouse_receipt_change"] = _numeric(result, "warehouse_receipt_change")
    result = result.dropna(subset=["feature_date"])
    result = result[result["product_code"].ne("")]
    grouped = (
        result.groupby(["product_code", "feature_date"], as_index=False)
        .agg(
            warehouse_receipt_quantity=("warehouse_receipt_quantity", "sum"),
            warehouse_receipt_change=("warehouse_receipt_change", "sum"),
        )
        .sort_values(["product_code", "feature_date"], kind="mergesort")
    )
    grouped["warehouse_change_20d_sum"] = (
        grouped.groupby("product_code", sort=False)["warehouse_receipt_change"]
        .rolling(20, min_periods=1)
        .sum()
        .reset_index(level=0, drop=True)
    )
    return grouped.reset_index(drop=True)


def _normalise_member(member: pd.DataFrame) -> pd.DataFrame:
    missing = set(MEMBER_COLUMNS).difference(member.columns)
    if missing:
        raise Stage001Error(f"member_columns_missing:{','.join(sorted(missing))}")
    frame = member[MEMBER_COLUMNS].copy()
    frame["feature_date"] = _parse_dates(frame.pop("date"))
    frame["symbol_text"] = frame["symbol"].fillna("").astype(str).str.strip().str.upper()
    variety = frame["variety"].map(_product_code)
    symbol_product = frame["symbol"].map(_product_code)
    frame["product_code"] = variety.mask(variety.eq(""), symbol_product)
    for column in MEMBER_COLUMNS[3:]:
        frame[column] = _numeric(frame, column).fillna(0.0)
    frame = frame.dropna(subset=["feature_date"])
    frame = frame[frame["product_code"].ne("")]

    rows: list[dict[str, Any]] = []
    for (product_code, feature_date), group in frame.groupby(
        ["product_code", "feature_date"], sort=True
    ):
        product_rows = group[group["symbol_text"].eq(product_code)]
        selected = product_rows if not product_rows.empty else group
        long_oi = float(selected["long_open_interest_top20"].sum())
        short_oi = float(selected["short_open_interest_top20"].sum())
        long_change = float(selected["long_open_interest_chg_top20"].sum())
        short_change = float(selected["short_open_interest_chg_top20"].sum())
        volume = float(selected["vol_top20"].sum())
        denominator = max(long_oi + short_oi, 1.0)
        rows.append(
            {
                "product_code": product_code,
                "feature_date": pd.Timestamp(feature_date),
                "member_net_position_ratio": (long_oi - short_oi) / denominator,
                "member_net_position_change_ratio": (long_change - short_change) / denominator,
                "member_turnover_pressure_ratio": volume / denominator,
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=[
                "product_code",
                "feature_date",
                "member_net_position_ratio",
                "member_net_position_change_ratio",
                "member_turnover_pressure_ratio",
            ]
        )
    return pd.DataFrame(rows).sort_values(["product_code", "feature_date"], kind="mergesort").reset_index(drop=True)


def _attach_source(
    panel: pd.DataFrame,
    source: pd.DataFrame,
    *,
    prefix: str,
    metric_columns: list[str],
    max_source_age_days: int,
) -> pd.DataFrame:
    result = panel.copy()
    feature_date_column = f"{prefix}_feature_date"
    age_column = f"{prefix}_source_age_days"
    available_column = f"{prefix}_available"
    result[feature_date_column] = pd.NaT
    result[age_column] = np.nan
    result[available_column] = False
    for column in metric_columns:
        result[column] = np.nan
    if result.empty or source.empty:
        return result

    right = source[["product_code", "feature_date", *metric_columns]].copy()
    right["available_date"] = right["feature_date"] + pd.Timedelta(days=1)
    for product_code, left_index in result.groupby("product_code", sort=False).groups.items():
        source_group = right[right["product_code"].eq(product_code)].sort_values(
            "available_date", kind="mergesort"
        )
        if source_group.empty:
            continue
        left = result.loc[left_index, ["eval_date"]].sort_values("eval_date", kind="mergesort")
        attached = pd.merge_asof(
            left.reset_index(),
            source_group.drop(columns=["product_code"]),
            left_on="eval_date",
            right_on="available_date",
            direction="backward",
        ).set_index("index")
        age = (attached["eval_date"] - attached["feature_date"]).dt.days
        valid = age.between(1, int(max_source_age_days), inclusive="both")
        result.loc[attached.index, feature_date_column] = attached["feature_date"]
        result.loc[attached.index, age_column] = age.astype(float)
        result.loc[attached.index, available_column] = valid.astype(bool)
        for column in metric_columns:
            result.loc[attached.index, column] = pd.to_numeric(
                attached[column], errors="coerce"
            ).where(valid)
    result[available_column] = result[available_column].astype(bool)
    return result


def build_physical_feature_panel(
    panel: pd.DataFrame,
    basis: pd.DataFrame,
    warehouse: pd.DataFrame,
    member: pd.DataFrame,
    *,
    max_source_age_days: int = 7,
) -> pd.DataFrame:
    if int(max_source_age_days) < 1:
        raise Stage001Error("max_source_age_days_must_be_positive")
    result = _normalise_panel(panel)
    result = _attach_source(
        result,
        _normalise_basis(basis),
        prefix="basis",
        metric_columns=["basis_dom_rate", "basis_near_rate"],
        max_source_age_days=max_source_age_days,
    )
    result = _attach_source(
        result,
        _normalise_warehouse(warehouse),
        prefix="warehouse",
        metric_columns=[
            "warehouse_receipt_quantity",
            "warehouse_receipt_change",
            "warehouse_change_20d_sum",
        ],
        max_source_age_days=max_source_age_days,
    )
    result = _attach_source(
        result,
        _normalise_member(member),
        prefix="member",
        metric_columns=[
            "member_net_position_ratio",
            "member_net_position_change_ratio",
            "member_turnover_pressure_ratio",
        ],
        max_source_age_days=max_source_age_days,
    )
    return result.sort_values(
        ["eval_date", "a_rank", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)


def _audit_family_coverage(
    feature_panel: pd.DataFrame,
    *,
    development_months: int,
    minimum_family_row_coverage: float,
    minimum_active_months: int,
    minimum_development_active_months: int,
    minimum_active_months_per_year: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    eval_dates = list(pd.DatetimeIndex(sorted(feature_panel["eval_date"].unique())))
    development_dates = set(eval_dates[: int(development_months)])
    unique_years = sorted(set(pd.DatetimeIndex(eval_dates).year.astype(int).tolist()))
    month_rows: list[dict[str, Any]] = []
    family_rows: list[dict[str, Any]] = []
    for family, available_column in FAMILY_AVAILABLE_COLUMNS.items():
        available = feature_panel[available_column].astype(bool)
        family_month_rows: list[dict[str, Any]] = []
        for eval_date, group in feature_panel.assign(_available=available).groupby(
            "eval_date", sort=True
        ):
            rank10 = group[group["a_rank"].eq(10)]
            challengers = group[group["a_rank"].gt(10)]
            rank10_available = bool(len(rank10) == 1 and rank10["_available"].iloc[0])
            challenger_available_rows = int(challengers["_available"].sum())
            active = bool(rank10_available and challenger_available_rows >= 2)
            row = {
                "family": family,
                "eval_date": pd.Timestamp(eval_date),
                "panel_rows": int(len(group)),
                "available_rows": int(group["_available"].sum()),
                "rank10_available": rank10_available,
                "challenger_rows": int(len(challengers)),
                "challenger_available_rows": challenger_available_rows,
                "active_month": active,
                "development_month": bool(pd.Timestamp(eval_date) in development_dates),
            }
            month_rows.append(row)
            family_month_rows.append(row)
        family_months = pd.DataFrame(family_month_rows)
        active_by_year = (
            family_months.assign(year=family_months["eval_date"].dt.year)
            .groupby("year")["active_month"]
            .sum()
            .reindex(unique_years, fill_value=0)
        )
        row_coverage = float(available.mean())
        active_month_count = int(family_months["active_month"].sum())
        development_active_count = int(
            family_months.loc[family_months["development_month"], "active_month"].sum()
        )
        minimum_year_count = int(active_by_year.min()) if len(active_by_year) else 0
        checks = {
            "row_coverage": row_coverage >= float(minimum_family_row_coverage),
            "active_months": active_month_count >= int(minimum_active_months),
            "development_active_months": development_active_count
            >= int(minimum_development_active_months),
            "active_months_per_year": minimum_year_count >= int(minimum_active_months_per_year),
        }
        failed = [name for name, passed in checks.items() if not passed]
        family_rows.append(
            {
                "family": family,
                "available_rows": int(available.sum()),
                "panel_rows": int(len(feature_panel)),
                "row_coverage": row_coverage,
                "active_months": active_month_count,
                "development_active_months": development_active_count,
                "minimum_active_months_in_any_year": minimum_year_count,
                "active_months_by_year_json": json.dumps(
                    {str(int(year)): int(count) for year, count in active_by_year.items()},
                    sort_keys=True,
                ),
                "eligible_for_feature_preregistration": bool(all(checks.values())),
                "failed_gates": ";".join(failed),
            }
        )
    return (
        pd.DataFrame(family_rows).sort_values("family", kind="mergesort").reset_index(drop=True),
        pd.DataFrame(month_rows)
        .sort_values(["family", "eval_date"], kind="mergesort")
        .reset_index(drop=True),
    )


def _source_summary(
    basis: pd.DataFrame, warehouse: pd.DataFrame, member: pd.DataFrame
) -> pd.DataFrame:
    rows = []
    for family, frame in [
        ("basis", _normalise_basis(basis)),
        ("warehouse", _normalise_warehouse(warehouse)),
        ("member", _normalise_member(member)),
    ]:
        rows.append(
            {
                "family": family,
                "normalised_rows": int(len(frame)),
                "product_count": int(frame["product_code"].nunique()),
                "feature_date_min": frame["feature_date"].min() if not frame.empty else pd.NaT,
                "feature_date_max": frame["feature_date"].max() if not frame.empty else pd.NaT,
            }
        )
    return pd.DataFrame(rows)


def _assess(
    feature_panel: pd.DataFrame,
    family_coverage: pd.DataFrame,
    *,
    expected_rows: int,
    expected_months: int,
    expected_products: int,
    minimum_any_row_coverage: float,
    minimum_eligible_families: int,
    max_source_age_days: int,
) -> dict[str, Any]:
    eligible = sorted(
        family_coverage.loc[
            family_coverage["eligible_for_feature_preregistration"].astype(bool), "family"
        ].astype(str)
    )
    diagnostic = sorted(set(FAMILY_AVAILABLE_COLUMNS).difference(eligible))
    any_available = feature_panel[list(FAMILY_AVAILABLE_COLUMNS.values())].any(axis=1)
    violations = 0
    for family in FAMILY_AVAILABLE_COLUMNS:
        mask = feature_panel[f"{family}_available"].astype(bool)
        feature_dates = pd.to_datetime(feature_panel[f"{family}_feature_date"], errors="coerce")
        ages = pd.to_numeric(feature_panel[f"{family}_source_age_days"], errors="coerce")
        violations += int(
            (
                mask
                & (
                    feature_dates.ge(feature_panel["eval_date"])
                    | ~ages.between(1, int(max_source_age_days), inclusive="both")
                )
            ).sum()
        )
    gates = {
        "expected_rows": len(feature_panel) == int(expected_rows),
        "expected_months": feature_panel["eval_date"].nunique() == int(expected_months),
        "expected_products": feature_panel["product_vt_symbol"].nunique()
        == int(expected_products),
        "any_row_coverage": float(any_available.mean()) >= float(minimum_any_row_coverage),
        "minimum_eligible_families": len(eligible) >= int(minimum_eligible_families),
        "basis_family_required": "basis" in eligible,
        "pit_source_date": violations == 0,
    }
    passed = bool(all(gates.values()))
    return {
        "decision": (
            "stage001_physical_positioning_coverage_pass_ready_for_feature_preregistration"
            if passed
            else "stage001_physical_positioning_coverage_fail_stop_no_features"
        ),
        "panel_rows": int(len(feature_panel)),
        "panel_months": int(feature_panel["eval_date"].nunique()),
        "panel_products": int(feature_panel["product_vt_symbol"].nunique()),
        "any_physical_available_rows": int(any_available.sum()),
        "any_physical_row_coverage": float(any_available.mean()),
        "eligible_family_count": int(len(eligible)),
        "eligible_families": eligible,
        "diagnostic_only_families": diagnostic,
        "pit_source_date_violation_rows": int(violations),
        "gate_results": gates,
        "gate_pass_count": int(sum(bool(value) for value in gates.values())),
        "gate_count": int(len(gates)),
        "coverage_gate_pass": passed,
    }


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
    feature_panel: pd.DataFrame,
    family_coverage: pd.DataFrame,
    month_coverage: pd.DataFrame,
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
    _write_csv(feature_panel, temp_dir / "physical_feature_panel.csv.gz", gzip=True)
    _write_csv(family_coverage, temp_dir / "family_coverage.csv")
    _write_csv(month_coverage, temp_dir / "month_family_coverage.csv")
    _write_csv(source_summary, temp_dir / "source_summary.csv")
    (temp_dir / "stage001_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = (
        "# Stage001 物理供需与会员持仓PIT覆盖审计\n\n"
        f"- 决策：`{summary['decision']}`。\n"
        f"- 面板：`{summary['panel_rows']}`行 / `{summary['panel_months']}`月 / "
        f"`{summary['panel_products']}`品种。\n"
        f"- 任一外生源覆盖：`{summary['any_physical_available_rows']}/{summary['panel_rows']}`；"
        f"合格家族：`{', '.join(summary['eligible_families']) or '无'}`。\n"
        f"- PIT日期违规：`{summary['pit_source_date_violation_rows']}`。\n"
        "- 本阶段未读取收益或回撤标签，未训练、未回测、未连接CTP、未调用订单API。\n"
    )
    (temp_dir / "report.md").write_text(report, encoding="utf-8")
    artifact_names = [
        "family_coverage.csv",
        "month_family_coverage.csv",
        "physical_feature_panel.csv.gz",
        "report.md",
        "source_summary.csv",
        "stage001_summary.json",
    ]
    manifest = {name: sha256_file(temp_dir / name) for name in artifact_names}
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
    expected_rows: int = 797,
    expected_months: int = 47,
    expected_products: int = 18,
    development_months: int = 18,
    max_source_age_days: int = 7,
    minimum_family_row_coverage: float = 0.50,
    minimum_any_row_coverage: float = 0.95,
    minimum_active_months: int = 24,
    minimum_development_active_months: int = 12,
    minimum_active_months_per_year: int = 4,
    minimum_eligible_families: int = 2,
) -> dict[str, Any]:
    if Path(output_dir).exists():
        raise Stage001Error("stage001_output_already_exists")
    before = _verify_inputs(input_paths, expected_sha256)
    panel = pd.read_csv(Path(input_paths["ranked_panel"]), usecols=PANEL_COLUMNS)
    basis = pd.concat(
        [
            pd.read_csv(Path(input_paths["basis_2020_2022"]), usecols=BASIS_COLUMNS),
            pd.read_csv(Path(input_paths["basis_2023_2026"]), usecols=BASIS_COLUMNS),
        ],
        ignore_index=True,
    )
    warehouse = pd.concat(
        [
            pd.read_csv(Path(input_paths["warehouse_2020_2022"]), usecols=WAREHOUSE_COLUMNS),
            pd.read_csv(Path(input_paths["warehouse_2023_2026"]), usecols=WAREHOUSE_COLUMNS),
        ],
        ignore_index=True,
    )
    member = pd.read_csv(Path(input_paths["member_rank_raw"]), usecols=MEMBER_COLUMNS)

    first = build_physical_feature_panel(
        panel, basis, warehouse, member, max_source_age_days=max_source_age_days
    )
    second = build_physical_feature_panel(
        panel, basis, warehouse, member, max_source_age_days=max_source_age_days
    )
    pd.testing.assert_frame_equal(first, second, check_exact=True)
    family_coverage, month_coverage = _audit_family_coverage(
        first,
        development_months=development_months,
        minimum_family_row_coverage=minimum_family_row_coverage,
        minimum_active_months=minimum_active_months,
        minimum_development_active_months=minimum_development_active_months,
        minimum_active_months_per_year=minimum_active_months_per_year,
    )
    summary = _assess(
        first,
        family_coverage,
        expected_rows=expected_rows,
        expected_months=expected_months,
        expected_products=expected_products,
        minimum_any_row_coverage=minimum_any_row_coverage,
        minimum_eligible_families=minimum_eligible_families,
        max_source_age_days=max_source_age_days,
    )
    after = _verify_inputs(input_paths, expected_sha256)
    if before != after:
        raise Stage001Error("input_identity_changed_during_run")
    summary.update(
        {
            "line_id": LINE_ID,
            "stage": STAGE,
            "formal_release_id": FORMAL_RELEASE_ID,
            "evidence_scope": "fixed_current_design_universe_only",
            "max_source_age_days": int(max_source_age_days),
            "development_months": int(development_months),
            "minimum_family_row_coverage": float(minimum_family_row_coverage),
            "minimum_any_row_coverage": float(minimum_any_row_coverage),
            "minimum_active_months": int(minimum_active_months),
            "minimum_development_active_months": int(minimum_development_active_months),
            "minimum_active_months_per_year": int(minimum_active_months_per_year),
            "minimum_eligible_families": int(minimum_eligible_families),
            "input_identities_before": before,
            "input_identities_after": after,
            "input_identity_stable": True,
            "repeat_exact": True,
            "panel_columns_read": list(PANEL_COLUMNS),
            "basis_columns_read": list(BASIS_COLUMNS),
            "warehouse_columns_read": list(WAREHOUSE_COLUMNS),
            "member_columns_read": list(MEMBER_COLUMNS),
            "label_columns_read": [],
            "label_values_read": False,
            "sealed_holdout_files_read": [],
            "trains_model": False,
            "model_fit_count": 0,
            "strategy_backtest_runs": 0,
            "ctp_connected": False,
            "order_api_called_count": 0,
        }
    )
    _publish(
        Path(output_dir),
        feature_panel=first,
        family_coverage=family_coverage,
        month_coverage=month_coverage,
        source_summary=_source_summary(basis, warehouse, member),
        summary=summary,
    )
    return summary


def main() -> None:
    print(json.dumps(run_stage001(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
