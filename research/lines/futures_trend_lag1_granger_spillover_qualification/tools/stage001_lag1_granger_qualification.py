from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests
from statsmodels.tsa.stattools import grangercausalitytests


ROOT_DIR = Path(__file__).resolve().parents[4]
LINE_DIR = ROOT_DIR / "research" / "lines" / "futures_trend_lag1_granger_spillover_qualification"
EVENTS_PATH = (
    ROOT_DIR
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_v2_optimization"
    / "outputs"
    / "stage131_c9_event_targeted_option_acquisition_manifest"
    / "rebuilt_c9_v2_stage131_c9_event_targeted_option_acquisition_manifest_query_events_"
    "stage131_c9_event_targeted_option_acquisition_manifest_v1.csv"
)
UNIVERSE_PATH = (
    ROOT_DIR
    / "examples"
    / "portfolio_backtesting"
    / "backtest_outputs"
    / "qmt_roll_full_market_tradable_universe_eligible_full_market_tradable_universe_v1.csv"
)
DB_PATH = ROOT_DIR / ".vntrader" / "database.db"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage001_lag1_granger_qualification"

EXPECTED_EVENTS_SHA256 = "7abf7a0414238517349e383a6ef7282b5f8d16921686ddc1edb6f2e70e5cc77a"
EXPECTED_UNIVERSE_SHA256 = "7d97dd4c112721a577eb89c4007606fc444fcc16173f1c11a9538a73490c2bac"
EXPECTED_EVENT_COUNT = 365
EXPECTED_UNIVERSE_COUNT = 57
LOOKBACK = 132
HALF_WINDOW = 66
FDR_ALPHA = 0.05
MIN_COMPLETE_LEADERS = 29
MIN_ALL_EVENT_RATE = 0.90
MIN_2022_EVENT_RATE = 0.90
MIN_YEAR_EVENT_RATE = 0.80


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)


def _atomic_csv(frame: pd.DataFrame, path: Path, *, gzip: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    frame.to_csv(temp, index=False, compression="gzip" if gzip else None)
    temp.replace(path)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if value is None or (not isinstance(value, (str, bytes)) and pd.isna(value)):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    display = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return display.to_markdown(index=False, floatfmt=".6f")


def load_events(path: Path = EVENTS_PATH) -> tuple[pd.DataFrame, dict[str, Any]]:
    source_hash = sha256_file(path)
    events = pd.read_csv(path)
    required = {"event_id", "entry_date", "product_vt_symbol"}
    missing = required.difference(events.columns)
    if missing:
        raise RuntimeError(f"Stage131 events missing columns: {sorted(missing)}")
    events["entry_date"] = pd.to_datetime(events["entry_date"], errors="raise").dt.normalize()
    events["event_id"] = events["event_id"].astype(str)
    events["product_vt_symbol"] = events["product_vt_symbol"].astype(str)
    events.sort_values(["entry_date", "event_id"], inplace=True)
    events.reset_index(drop=True, inplace=True)
    duplicate_events = int(events["event_id"].duplicated(keep=False).sum())
    duplicate_product_dates = int(events.duplicated(["product_vt_symbol", "entry_date"], keep=False).sum())
    audit = {
        "events_sha256": source_hash,
        "events_hash_ok": source_hash == EXPECTED_EVENTS_SHA256,
        "event_rows": int(len(events)),
        "unique_events": int(events["event_id"].nunique()),
        "duplicate_event_rows": duplicate_events,
        "duplicate_product_date_rows": duplicate_product_dates,
        "event_first_date": events["entry_date"].min().date().isoformat(),
        "event_last_date": events["entry_date"].max().date().isoformat(),
        "event_2022_count": int(events["entry_date"].dt.year.eq(2022).sum()),
    }
    return events, audit


def load_universe(path: Path = UNIVERSE_PATH) -> tuple[list[str], dict[str, Any]]:
    source_hash = sha256_file(path)
    frame = pd.read_csv(path)
    required = {"product_vt_symbol", "eligible"}
    missing = required.difference(frame.columns)
    if missing:
        raise RuntimeError(f"universe missing columns: {sorted(missing)}")
    eligible = frame[pd.to_numeric(frame["eligible"], errors="coerce").fillna(0).astype(int).eq(1)].copy()
    products = sorted(eligible["product_vt_symbol"].dropna().astype(str).unique().tolist())
    audit = {
        "universe_sha256": source_hash,
        "universe_hash_ok": source_hash == EXPECTED_UNIVERSE_SHA256,
        "universe_source_rows": int(len(frame)),
        "eligible_product_count": int(len(products)),
        "duplicate_eligible_product_rows": int(eligible["product_vt_symbol"].duplicated(keep=False).sum()),
    }
    return products, audit


def load_contract_bars(
    db_path: Path,
    *,
    product: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    prefix, exchange = product.split(".", 1)
    query = """
        select
            symbol,
            exchange,
            datetime as date,
            close_price as close,
            open_interest
        from dbbardata
        where interval = 'd'
          and exchange = ?
          and lower(symbol) like ?
          and datetime between ? and ?
        order by datetime, symbol
    """
    with sqlite3.connect(db_path) as connection:
        bars = pd.read_sql_query(
            query,
            connection,
            params=(
                exchange,
                prefix.lower() + "%",
                start.strftime("%Y-%m-%d"),
                end.strftime("%Y-%m-%d 23:59:59"),
            ),
        )
    exact = re.compile(rf"^{re.escape(prefix)}\d{{3,4}}$", re.IGNORECASE)
    bars = bars[bars["symbol"].astype(str).map(lambda value: bool(exact.fullmatch(value)))].copy()
    bars["date"] = pd.to_datetime(bars["date"], errors="raise").dt.normalize()
    bars["close"] = pd.to_numeric(bars["close"], errors="coerce")
    bars["open_interest"] = pd.to_numeric(bars["open_interest"], errors="coerce")
    bars.sort_values(["date", "symbol"], inplace=True)
    bars.reset_index(drop=True, inplace=True)
    return bars


def build_t1_product_returns(bars: pd.DataFrame, product: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    required = {"symbol", "exchange", "date", "close", "open_interest"}
    missing = required.difference(bars.columns)
    if missing:
        raise RuntimeError(f"missing bar columns: {sorted(missing)}")
    data = bars.copy()
    data["date"] = pd.to_datetime(data["date"], errors="raise").dt.normalize()
    duplicate_count = int(data.duplicated(["symbol", "date"], keep=False).sum())
    if duplicate_count:
        raise RuntimeError(f"duplicate contract-date rows for {product}: {duplicate_count}")

    by_date = {date: frame.copy() for date, frame in data.groupby("date", sort=True)}
    dates = sorted(by_date)
    rows: list[dict[str, Any]] = []
    for index in range(1, len(dates)):
        selection_date = pd.Timestamp(dates[index - 1])
        return_date = pd.Timestamp(dates[index])
        previous = by_date[selection_date]
        candidates = previous[
            previous["open_interest"].gt(0)
            & previous["open_interest"].map(np.isfinite)
        ].copy()
        candidates.sort_values(["open_interest", "symbol"], ascending=[False, True], inplace=True)
        if candidates.empty:
            rows.append(
                {
                    "product_vt_symbol": product,
                    "selection_date": selection_date,
                    "return_date": return_date,
                    "selected_symbol": "",
                    "current_symbol": "",
                    "candidate_count": 0,
                    "top_oi_tie_count": 0,
                    "selected_open_interest": np.nan,
                    "prior_close": np.nan,
                    "current_close": np.nan,
                    "return": np.nan,
                    "status": "no_t1_candidate",
                }
            )
            continue

        selected = candidates.iloc[0]
        selected_symbol = str(selected["symbol"])
        selected_open_interest = float(selected["open_interest"])
        prior_close = float(selected["close"])
        current = by_date[return_date]
        current = current[current["symbol"].astype(str).eq(selected_symbol)]
        status = "ok"
        current_symbol = ""
        current_close = np.nan
        product_return = np.nan
        if not math.isfinite(prior_close) or prior_close <= 0:
            status = "invalid_prior_close"
        elif len(current) != 1:
            status = "selected_contract_missing_on_return_date"
        else:
            current_symbol = str(current.iloc[0]["symbol"])
            current_close = float(current.iloc[0]["close"])
            if not math.isfinite(current_close) or current_close <= 0:
                status = "invalid_current_close"
            else:
                product_return = current_close / prior_close - 1.0
                if not math.isfinite(product_return):
                    status = "nonfinite_return"
                    product_return = np.nan
        rows.append(
            {
                "product_vt_symbol": product,
                "selection_date": selection_date,
                "return_date": return_date,
                "selected_symbol": selected_symbol,
                "current_symbol": current_symbol,
                "candidate_count": int(len(candidates)),
                "top_oi_tie_count": int(candidates["open_interest"].eq(selected_open_interest).sum()),
                "selected_open_interest": selected_open_interest,
                "prior_close": prior_close,
                "current_close": current_close,
                "return": product_return,
                "status": status,
            }
        )

    ledger = pd.DataFrame(rows)
    if ledger.empty:
        ledger = pd.DataFrame(
            columns=[
                "product_vt_symbol",
                "selection_date",
                "return_date",
                "selected_symbol",
                "current_symbol",
                "candidate_count",
                "top_oi_tie_count",
                "selected_open_interest",
                "prior_close",
                "current_close",
                "return",
                "status",
            ]
        )
    ok = ledger[ledger["status"].eq("ok")].copy()
    audit = {
        "product_vt_symbol": product,
        "source_rows": int(len(data)),
        "source_symbols": int(data["symbol"].nunique()),
        "source_first_date": data["date"].min().date().isoformat() if len(data) else "",
        "source_last_date": data["date"].max().date().isoformat() if len(data) else "",
        "source_duplicate_contract_date_rows": duplicate_count,
        "selection_rows": int(len(ledger)),
        "ok_return_rows": int(len(ok)),
        "invalid_return_rows": int(len(ledger) - len(ok)),
        "selection_date_not_before_return_date": int(
            ledger["selection_date"].ge(ledger["return_date"]).sum()
        ),
        "cross_contract_direct_return_count": int(
            ok["selected_symbol"].astype(str).ne(ok["current_symbol"].astype(str)).sum()
        ),
        "invalid_prior_close_rows": int(ledger["status"].eq("invalid_prior_close").sum()),
        "nonfinite_return_on_ok": int((~np.isfinite(ok["return"])).sum()),
    }
    return ledger, audit


def build_return_panel(selection_ledger: pd.DataFrame) -> pd.DataFrame:
    ok = selection_ledger[selection_ledger["status"].eq("ok")].copy()
    duplicate_count = int(ok.duplicated(["product_vt_symbol", "return_date"], keep=False).sum())
    if duplicate_count:
        raise RuntimeError(f"duplicate product return rows: {duplicate_count}")
    panel = ok.pivot(index="return_date", columns="product_vt_symbol", values="return").reset_index()
    panel.columns.name = None
    panel.sort_values("return_date", inplace=True)
    panel.reset_index(drop=True, inplace=True)
    return panel


def extract_pair_history(
    panel: pd.DataFrame,
    *,
    target: str,
    leader: str,
    entry_date: pd.Timestamp,
    lookback: int = LOOKBACK,
) -> pd.DataFrame:
    if target not in panel.columns or leader not in panel.columns:
        return pd.DataFrame(columns=["return_date", target, leader])
    history = panel[
        pd.to_datetime(panel["return_date"], errors="raise").dt.normalize().lt(
            pd.Timestamp(entry_date).normalize()
        )
    ][["return_date", target, leader]].dropna().tail(lookback).copy()
    history.sort_values("return_date", inplace=True)
    history.reset_index(drop=True, inplace=True)
    return history


def _lag1_coefficient(frame: pd.DataFrame, target_col: str, leader_col: str) -> float:
    values = frame[[target_col, leader_col]].to_numpy(dtype=float)
    if len(values) < 4 or not np.isfinite(values).all():
        return np.nan
    target = values[:, 0]
    leader = values[:, 1]
    design = np.column_stack([np.ones(len(values) - 1), target[:-1], leader[:-1]])
    response = target[1:]
    if np.linalg.matrix_rank(design) < design.shape[1]:
        return np.nan
    coefficients = np.linalg.lstsq(design, response, rcond=None)[0]
    return float(coefficients[2])


def fit_lag1_granger(frame: pd.DataFrame, *, target_col: str, leader_col: str) -> dict[str, Any]:
    clean = frame[[target_col, leader_col]].apply(pd.to_numeric, errors="coerce").dropna().copy()
    if len(clean) != LOOKBACK or not np.isfinite(clean.to_numpy(dtype=float)).all():
        return {
            "full_pvalue": np.nan,
            "full_leader_coef": np.nan,
            "early_leader_coef": np.nan,
            "late_leader_coef": np.nan,
            "granger_status": "incomplete_history",
        }
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="verbose is deprecated since functions should not print results",
                category=FutureWarning,
            )
            tests = grangercausalitytests(
                clean[[target_col, leader_col]], maxlag=[1], verbose=False
            )
        full_pvalue = float(tests[1][0]["ssr_ftest"][1])
        full_coefficient = _lag1_coefficient(clean, target_col, leader_col)
        early_coefficient = _lag1_coefficient(clean.head(HALF_WINDOW), target_col, leader_col)
        late_coefficient = _lag1_coefficient(clean.tail(HALF_WINDOW), target_col, leader_col)
    except (ValueError, np.linalg.LinAlgError, ZeroDivisionError):
        return {
            "full_pvalue": np.nan,
            "full_leader_coef": np.nan,
            "early_leader_coef": np.nan,
            "late_leader_coef": np.nan,
            "granger_status": "model_error",
        }
    finite = all(
        math.isfinite(value)
        for value in [full_pvalue, full_coefficient, early_coefficient, late_coefficient]
    )
    return {
        "full_pvalue": full_pvalue,
        "full_leader_coef": full_coefficient,
        "early_leader_coef": early_coefficient,
        "late_leader_coef": late_coefficient,
        "granger_status": "ok" if finite else "nonfinite_result",
    }


def apply_global_fdr_and_stability(pairs: pd.DataFrame, *, alpha: float = FDR_ALPHA) -> pd.DataFrame:
    audited = pairs.copy()
    audited["fdr_qvalue"] = np.nan
    audited["fdr_reject"] = 0
    valid = (
        pd.to_numeric(audited["history_complete"], errors="coerce").fillna(0).astype(int).eq(1)
        & audited["granger_status"].astype(str).eq("ok")
        & pd.to_numeric(audited["full_pvalue"], errors="coerce").between(0.0, 1.0, inclusive="both")
    )
    if valid.any():
        reject, corrected, _, _ = multipletests(
            audited.loc[valid, "full_pvalue"].to_numpy(dtype=float),
            alpha=alpha,
            method="fdr_bh",
            is_sorted=False,
            returnsorted=False,
        )
        audited.loc[valid, "fdr_qvalue"] = corrected
        audited.loc[valid, "fdr_reject"] = reject.astype(int)

    coefficients = audited[["full_leader_coef", "early_leader_coef", "late_leader_coef"]].apply(
        pd.to_numeric, errors="coerce"
    )
    finite = np.isfinite(coefficients).all(axis=1)
    all_positive = coefficients.gt(0.0).all(axis=1)
    all_negative = coefficients.lt(0.0).all(axis=1)
    audited["half_sign_stable"] = (finite & (all_positive | all_negative)).astype(int)
    audited["stable_incoming_edge"] = (
        audited["fdr_reject"].eq(1) & audited["half_sign_stable"].eq(1)
    ).astype(int)
    return audited


def build_event_pair_ledger(
    events: pd.DataFrame,
    panel: pd.DataFrame,
    products: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    panel_dates = pd.to_datetime(panel["return_date"], errors="raise").dt.normalize()
    rows: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    for event in events.itertuples(index=False):
        event_id = str(event.event_id)
        entry_date = pd.Timestamp(event.entry_date).normalize()
        target = str(event.product_vt_symbol)
        target_history_count = 0
        target_history_last_date = pd.NaT
        if target in panel.columns:
            target_mask = panel_dates.lt(entry_date) & pd.to_numeric(panel[target], errors="coerce").notna()
            target_history = panel.loc[target_mask, ["return_date", target]].tail(LOOKBACK)
            target_history_count = int(len(target_history))
            if len(target_history):
                target_history_last_date = pd.Timestamp(target_history["return_date"].max())
        contexts.append(
            {
                "event_id": event_id,
                "entry_date": entry_date,
                "event_year": int(entry_date.year),
                "target_product": target,
                "target_in_universe": int(target in products),
                "target_history_count": target_history_count,
                "target_history_complete": int(target_history_count == LOOKBACK),
                "target_history_last_date": target_history_last_date,
                "target_history_not_before_entry": int(
                    pd.notna(target_history_last_date) and target_history_last_date >= entry_date
                ),
            }
        )
        for leader in products:
            if leader == target:
                continue
            history = extract_pair_history(
                panel,
                target=target,
                leader=leader,
                entry_date=entry_date,
                lookback=LOOKBACK,
            )
            history_complete = len(history) == LOOKBACK
            if history_complete:
                model_input = history.rename(columns={target: "target", leader: "leader"})
                model = fit_lag1_granger(model_input, target_col="target", leader_col="leader")
            else:
                model = {
                    "full_pvalue": np.nan,
                    "full_leader_coef": np.nan,
                    "early_leader_coef": np.nan,
                    "late_leader_coef": np.nan,
                    "granger_status": "incomplete_history",
                }
            history_last_date = pd.Timestamp(history["return_date"].max()) if len(history) else pd.NaT
            rows.append(
                {
                    "event_id": event_id,
                    "entry_date": entry_date,
                    "event_year": int(entry_date.year),
                    "target_product": target,
                    "leader_product": leader,
                    "history_count": int(len(history)),
                    "history_complete": int(history_complete),
                    "history_first_date": pd.Timestamp(history["return_date"].min()) if len(history) else pd.NaT,
                    "history_last_date": history_last_date,
                    "history_not_before_entry": int(pd.notna(history_last_date) and history_last_date >= entry_date),
                    **model,
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(contexts)


def summarize_events(pair_ledger: pd.DataFrame, contexts: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    grouped = (
        pair_ledger.groupby("event_id", as_index=False)
        .agg(
            pair_count=("leader_product", "size"),
            complete_leader_count=("history_complete", "sum"),
            stable_incoming_edge_count=("stable_incoming_edge", "sum"),
            history_not_before_entry_count=("history_not_before_entry", "sum"),
            granger_ok_count=("granger_status", lambda values: int(pd.Series(values).eq("ok").sum())),
        )
    )
    event_summary = contexts.merge(grouped, on="event_id", how="left", validate="one_to_one")
    for column in [
        "pair_count",
        "complete_leader_count",
        "stable_incoming_edge_count",
        "history_not_before_entry_count",
        "granger_ok_count",
    ]:
        event_summary[column] = pd.to_numeric(event_summary[column], errors="coerce").fillna(0).astype(int)
    event_summary["leader_coverage_pass"] = event_summary["complete_leader_count"].ge(
        MIN_COMPLETE_LEADERS
    ).astype(int)
    event_summary["stable_edge_pass"] = event_summary["stable_incoming_edge_count"].ge(1).astype(int)
    event_summary["event_qualified"] = (
        event_summary["target_in_universe"].eq(1)
        & event_summary["target_history_complete"].eq(1)
        & event_summary["leader_coverage_pass"].eq(1)
        & event_summary["stable_edge_pass"].eq(1)
        & event_summary["target_history_not_before_entry"].eq(0)
        & event_summary["history_not_before_entry_count"].eq(0)
    ).astype(int)
    event_summary.sort_values(["entry_date", "event_id"], inplace=True)
    event_summary.reset_index(drop=True, inplace=True)

    year_summary = (
        event_summary.groupby("event_year", as_index=False)
        .agg(
            event_count=("event_id", "size"),
            target_history_complete_count=("target_history_complete", "sum"),
            leader_coverage_pass_count=("leader_coverage_pass", "sum"),
            stable_edge_pass_count=("stable_edge_pass", "sum"),
            qualified_event_count=("event_qualified", "sum"),
        )
    )
    year_summary["target_history_complete_rate"] = (
        year_summary["target_history_complete_count"] / year_summary["event_count"]
    )
    year_summary["qualified_event_rate"] = year_summary["qualified_event_count"] / year_summary["event_count"]
    return event_summary, year_summary


def evaluate(
    events_path: Path = EVENTS_PATH,
    universe_path: Path = UNIVERSE_PATH,
    db_path: Path = DB_PATH,
) -> dict[str, Any]:
    events, event_audit = load_events(events_path)
    products, universe_audit = load_universe(universe_path)
    target_products = set(events["product_vt_symbol"].astype(str))
    targets_missing_universe = sorted(target_products.difference(products))

    db_hash_before = sha256_file(db_path)
    query_start = events["entry_date"].min() - pd.Timedelta(days=1200)
    query_end = events["entry_date"].max()
    ledgers: list[pd.DataFrame] = []
    product_audits: list[dict[str, Any]] = []
    for product in products:
        bars = load_contract_bars(
            db_path,
            product=product,
            start=query_start,
            end=query_end,
        )
        ledger, audit = build_t1_product_returns(bars, product)
        ledgers.append(ledger)
        product_audits.append(audit)
    selection_ledger = pd.concat(ledgers, ignore_index=True)
    product_audit = pd.DataFrame(product_audits).sort_values("product_vt_symbol")
    panel = build_return_panel(selection_ledger)
    pair_ledger_raw, contexts = build_event_pair_ledger(events, panel, products)
    pair_ledger = apply_global_fdr_and_stability(pair_ledger_raw, alpha=FDR_ALPHA)
    event_summary, year_summary = summarize_events(pair_ledger, contexts)
    db_hash_after = sha256_file(db_path)

    events_2022 = event_summary[event_summary["event_year"].eq(2022)]
    target_complete_rate = float(event_summary["target_history_complete"].mean())
    target_complete_rate_2022 = float(events_2022["target_history_complete"].mean())
    qualified_rate = float(event_summary["event_qualified"].mean())
    qualified_rate_2022 = float(events_2022["event_qualified"].mean())
    minimum_year_rate = float(year_summary["qualified_event_rate"].min())
    valid_bh = pair_ledger[
        pair_ledger["history_complete"].eq(1)
        & pair_ledger["granger_status"].eq("ok")
        & pd.to_numeric(pair_ledger["full_pvalue"], errors="coerce").between(
            0.0, 1.0, inclusive="both"
        )
    ]
    valid_q = pd.to_numeric(valid_bh["fdr_qvalue"], errors="coerce").dropna()

    source_gate = bool(
        event_audit["events_hash_ok"]
        and event_audit["event_rows"] == EXPECTED_EVENT_COUNT
        and event_audit["unique_events"] == EXPECTED_EVENT_COUNT
        and event_audit["duplicate_event_rows"] == 0
        and event_audit["duplicate_product_date_rows"] == 0
        and event_audit["event_2022_count"] == 48
        and universe_audit["universe_hash_ok"]
        and universe_audit["eligible_product_count"] == EXPECTED_UNIVERSE_COUNT
        and universe_audit["duplicate_eligible_product_rows"] == 0
        and not targets_missing_universe
        and db_hash_before == db_hash_after
    )
    t1_gate = bool(
        int(product_audit["source_duplicate_contract_date_rows"].sum()) == 0
        and int(product_audit["selection_date_not_before_return_date"].sum()) == 0
        and int(product_audit["cross_contract_direct_return_count"].sum()) == 0
        and int(product_audit["nonfinite_return_on_ok"].sum()) == 0
        and int(event_summary["target_history_not_before_entry"].sum()) == 0
        and int(event_summary["history_not_before_entry_count"].sum()) == 0
    )
    target_coverage_gate = bool(
        target_complete_rate >= MIN_ALL_EVENT_RATE
        and target_complete_rate_2022 >= MIN_2022_EVENT_RATE
    )
    network_gate = bool(
        qualified_rate >= MIN_ALL_EVENT_RATE
        and qualified_rate_2022 >= MIN_2022_EVENT_RATE
        and minimum_year_rate >= MIN_YEAR_EVENT_RATE
    )
    passed = source_gate and t1_gate and target_coverage_gate and network_gate
    decision_label = (
        "ALLOW_STAGE002_NETWORK_SIGNAL_PREDECL_ONLY"
        if passed
        else "CLOSE_LINE_LAG1_GRANGER_NETWORK_INELIGIBLE"
    )

    gate_matrix = pd.DataFrame(
        [
            {"gate_id": "source_identity_and_counts", "evidence": int(source_gate), "threshold": 1, "passed": int(source_gate)},
            {"gate_id": "t1_same_contract_integrity", "evidence": int(t1_gate), "threshold": 1, "passed": int(t1_gate)},
            {"gate_id": "all_target_history_complete_rate", "evidence": target_complete_rate, "threshold": MIN_ALL_EVENT_RATE, "passed": int(target_complete_rate >= MIN_ALL_EVENT_RATE)},
            {"gate_id": "2022_target_history_complete_rate", "evidence": target_complete_rate_2022, "threshold": MIN_2022_EVENT_RATE, "passed": int(target_complete_rate_2022 >= MIN_2022_EVENT_RATE)},
            {"gate_id": "all_qualified_event_rate", "evidence": qualified_rate, "threshold": MIN_ALL_EVENT_RATE, "passed": int(qualified_rate >= MIN_ALL_EVENT_RATE)},
            {"gate_id": "2022_qualified_event_rate", "evidence": qualified_rate_2022, "threshold": MIN_2022_EVENT_RATE, "passed": int(qualified_rate_2022 >= MIN_2022_EVENT_RATE)},
            {"gate_id": "minimum_year_qualified_event_rate", "evidence": minimum_year_rate, "threshold": MIN_YEAR_EVENT_RATE, "passed": int(minimum_year_rate >= MIN_YEAR_EVENT_RATE)},
        ]
    )
    decision = {
        "stage": "Stage001",
        "line_id": "futures_trend_lag1_granger_spillover_qualification",
        "decision": decision_label,
        "event_count": int(len(event_summary)),
        "event_2022_count": int(len(events_2022)),
        "universe_product_count": int(len(products)),
        "target_product_count": int(len(target_products)),
        "target_products_missing_universe": targets_missing_universe,
        "selection_ledger_rows": int(len(selection_ledger)),
        "ok_product_return_rows": int(selection_ledger["status"].eq("ok").sum()),
        "return_panel_rows": int(len(panel)),
        "pair_test_rows": int(len(pair_ledger)),
        "complete_pair_rows": int(pair_ledger["history_complete"].sum()),
        "valid_global_bh_rows": int(len(valid_bh)),
        "raw_pvalue_min": float(valid_bh["full_pvalue"].min()) if len(valid_bh) else np.nan,
        "fdr_qvalue_min": float(valid_q.min()) if len(valid_q) else np.nan,
        "fdr_reject_rows": int(pair_ledger["fdr_reject"].sum()),
        "half_sign_stable_rows": int(pair_ledger["half_sign_stable"].sum()),
        "stable_incoming_edge_rows": int(pair_ledger["stable_incoming_edge"].sum()),
        "target_history_complete_count": int(event_summary["target_history_complete"].sum()),
        "target_history_complete_rate": target_complete_rate,
        "target_history_complete_2022_count": int(events_2022["target_history_complete"].sum()),
        "target_history_complete_2022_rate": target_complete_rate_2022,
        "qualified_event_count": int(event_summary["event_qualified"].sum()),
        "qualified_event_rate": qualified_rate,
        "qualified_event_2022_count": int(events_2022["event_qualified"].sum()),
        "qualified_event_2022_rate": qualified_rate_2022,
        "minimum_year_qualified_event_rate": minimum_year_rate,
        "lookback": LOOKBACK,
        "half_window": HALF_WINDOW,
        "lag": 1,
        "fdr_method": "fdr_bh_global",
        "fdr_interpretation": (
            "predeclared_mechanical_gate_only; overlapping_event_windows_mean_formal_"
            "independence_or_positive_dependence_guarantee_was_not_established"
        ),
        "fdr_alpha": FDR_ALPHA,
        "minimum_complete_leaders": MIN_COMPLETE_LEADERS,
        "invalid_prior_close_rows": int(product_audit["invalid_prior_close_rows"].sum()),
        "network_called": False,
        "strategy_pnl_read": False,
        "backtest_run": False,
        "ready_for_stage002_signal_predecl": bool(passed),
        "ready_for_strategy_ab": False,
        "ready_for_live": False,
        "source_hashes": {
            "events": sha256_file(events_path),
            "universe": sha256_file(universe_path),
            "database_before": db_hash_before,
            "database_after": db_hash_after,
            "producer": sha256_file(Path(__file__)),
        },
    }
    return {
        "decision": decision,
        "gate_matrix": gate_matrix,
        "event_audit": event_audit,
        "universe_audit": universe_audit,
        "product_audit": product_audit,
        "selection_ledger": selection_ledger,
        "return_panel": panel,
        "pair_ledger": pair_ledger,
        "event_summary": event_summary,
        "year_summary": year_summary,
    }


def write_outputs(result: dict[str, Any], output_dir: Path = OUTPUT_DIR) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "decision": output_dir / "stage001_decision.json",
        "gates": output_dir / "stage001_gate_matrix.csv",
        "product_audit": output_dir / "stage001_product_data_audit.csv",
        "selection": output_dir / "stage001_t1_selection_ledger.csv.gz",
        "panel": output_dir / "stage001_t1_return_panel.csv.gz",
        "pairs": output_dir / "stage001_event_leader_granger_ledger.csv.gz",
        "events": output_dir / "stage001_event_network_qualification.csv",
        "years": output_dir / "stage001_year_qualification.csv",
        "report": output_dir / "stage001_report.md",
        "manifest": output_dir / "stage001_manifest.csv",
    }
    _atomic_text(paths["decision"], json.dumps(_json_safe(result["decision"]), ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _atomic_csv(result["gate_matrix"], paths["gates"])
    _atomic_csv(result["product_audit"], paths["product_audit"])
    _atomic_csv(result["selection_ledger"], paths["selection"], gzip=True)
    _atomic_csv(result["return_panel"], paths["panel"], gzip=True)
    _atomic_csv(result["pair_ledger"], paths["pairs"], gzip=True)
    _atomic_csv(result["event_summary"], paths["events"])
    _atomic_csv(result["year_summary"], paths["years"])

    decision = result["decision"]
    failed_events = result["event_summary"][result["event_summary"]["event_qualified"].eq(0)]
    report = "\n".join(
        [
            "# Stage001 Lag-1 Granger Network Qualification",
            "",
            f"- decision: `{decision['decision']}`",
            f"- events: `{decision['event_count']}`; 2022: `{decision['event_2022_count']}`",
            f"- universe: `{decision['universe_product_count']}`; targets: `{decision['target_product_count']}`",
            f"- pair tests: `{decision['pair_test_rows']}`; complete: `{decision['complete_pair_rows']}`",
            f"- valid global BH rows: `{decision['valid_global_bh_rows']}`; pmin/qmin: `{decision['raw_pvalue_min']:.12g}/{decision['fdr_qvalue_min']:.12g}`",
            f"- global BH rejects: `{decision['fdr_reject_rows']}`; stable incoming edges: `{decision['stable_incoming_edge_rows']}`",
            "- BH interpretation: predeclared mechanical gate only; formal dependence guarantee not established because event windows overlap",
            f"- target history complete: `{decision['target_history_complete_count']}/{decision['event_count']}`",
            f"- qualified events: `{decision['qualified_event_count']}/{decision['event_count']}`; 2022 `{decision['qualified_event_2022_count']}/{decision['event_2022_count']}`",
            f"- minimum year qualified rate: `{decision['minimum_year_qualified_event_rate']:.6f}`",
            "- strategy PnL read: `false`; backtest: `false`; live: `false`",
            "",
            "## Gates",
            "",
            _md_table(result["gate_matrix"]),
            "",
            "## Year qualification",
            "",
            _md_table(result["year_summary"]),
            "",
            "## First failed events",
            "",
            _md_table(
                failed_events[
                    [
                        "event_id",
                        "entry_date",
                        "target_product",
                        "target_history_count",
                        "complete_leader_count",
                        "stable_incoming_edge_count",
                        "event_qualified",
                    ]
                ],
                max_rows=30,
            ),
            "",
        ]
    )
    _atomic_text(paths["report"], report)

    manifest_rows: list[dict[str, Any]] = []
    for source_id, path in [
        ("events", EVENTS_PATH),
        ("universe", UNIVERSE_PATH),
        ("database", DB_PATH),
        ("producer", Path(__file__)),
    ]:
        manifest_rows.append(
            {
                "artifact_id": source_id,
                "artifact_role": "source",
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    for artifact_id, path in paths.items():
        if artifact_id == "manifest":
            continue
        manifest_rows.append(
            {
                "artifact_id": artifact_id,
                "artifact_role": "output",
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    _atomic_csv(pd.DataFrame(manifest_rows), paths["manifest"])
    return {key: str(path) for key, path in paths.items()}


def main() -> None:
    result = evaluate()
    paths = write_outputs(result)
    print(json.dumps({"decision": _json_safe(result["decision"]), "paths": paths}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
