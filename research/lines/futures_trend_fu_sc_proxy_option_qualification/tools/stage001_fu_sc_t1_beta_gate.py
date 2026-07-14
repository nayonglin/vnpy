from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[4]
LINE_DIR = ROOT_DIR / "research" / "lines" / "futures_trend_fu_sc_proxy_option_qualification"
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
DB_PATH = ROOT_DIR / ".vntrader" / "database.db"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage001_fu_sc_t1_beta_gate"
EXPECTED_EVENTS_SHA256 = "7abf7a0414238517349e383a6ef7282b5f8d16921686ddc1edb6f2e70e5cc77a"

SC_OPTION_LIST_DATE = pd.Timestamp("2021-06-21")
CORE_START = pd.Timestamp("2022-03-09")
CORE_END = pd.Timestamp("2022-06-29")
LOOKBACK = 126
HALF_WINDOW = 63
MIN_CORRELATION = 0.50
MIN_ALL_EVENT_RATE = 0.90

PRODUCT_SPECS = {
    "fu.SHFE": {"prefix": "fu", "exchange": "SHFE"},
    "sc.INE": {"prefix": "sc", "exchange": "INE"},
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_text(path: Path, text: str) -> None:
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)


def _atomic_csv(frame: pd.DataFrame, path: Path, *, gzip: bool = False) -> None:
    temp = path.with_name(path.name + ".tmp")
    frame.to_csv(temp, index=False, compression="gzip" if gzip else None)
    temp.replace(path)


def load_fu_events(path: Path = EVENTS_PATH) -> tuple[pd.DataFrame, dict[str, Any]]:
    source_hash = sha256_file(path)
    events = pd.read_csv(path)
    events["entry_date"] = pd.to_datetime(events["entry_date"], errors="raise").dt.normalize()
    if len(events) != 365 or events["event_id"].nunique() != 365:
        raise RuntimeError("Stage131 must contain 365 unique events")
    selected = events[
        events["product_vt_symbol"].eq("fu.SHFE")
        & events["entry_date"].ge(SC_OPTION_LIST_DATE)
    ].copy()
    selected.sort_values(["entry_date", "event_id"], inplace=True)
    selected.reset_index(drop=True, inplace=True)
    if selected.empty:
        raise RuntimeError("no post-listing FU events")
    audit = {
        "events_sha256": source_hash,
        "events_hash_ok": source_hash == EXPECTED_EVENTS_SHA256,
        "all_event_rows": int(len(events)),
        "fu_event_rows": int(len(selected)),
        "fu_unique_events": int(selected["event_id"].nunique()),
        "fu_first_entry_date": selected["entry_date"].min().date().isoformat(),
        "fu_last_entry_date": selected["entry_date"].max().date().isoformat(),
        "core_event_count": int(selected["entry_date"].between(CORE_START, CORE_END).sum()),
    }
    return selected, audit


def load_contract_bars(
    db_path: Path,
    *,
    prefix: str,
    exchange: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
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
    with sqlite3.connect(db_path) as conn:
        bars = pd.read_sql_query(
            query,
            conn,
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
            previous["close"].gt(0)
            & previous["close"].map(np.isfinite)
            & previous["open_interest"].gt(0)
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
        top_oi = float(selected["open_interest"])
        tie_count = int(candidates["open_interest"].eq(top_oi).sum())
        current = by_date[return_date]
        current = current[current["symbol"].astype(str).eq(selected_symbol)]
        status = "ok"
        current_close = np.nan
        product_return = np.nan
        if len(current) != 1:
            status = "selected_contract_missing_on_return_date"
        else:
            current_close = float(current.iloc[0]["close"])
            prior_close = float(selected["close"])
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
                "candidate_count": int(len(candidates)),
                "top_oi_tie_count": tie_count,
                "selected_open_interest": top_oi,
                "prior_close": float(selected["close"]),
                "current_close": current_close,
                "return": product_return,
                "status": status,
            }
        )

    ledger = pd.DataFrame(rows)
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
        "empty_selected_symbol_on_ok": int(ok["selected_symbol"].eq("").sum()),
        "nonpositive_selected_oi_on_ok": int(ok["selected_open_interest"].le(0).sum()),
        "nonfinite_return_on_ok": int((~np.isfinite(ok["return"])).sum()),
    }
    return ledger, audit


def build_common_return_panel(selection_ledger: pd.DataFrame) -> pd.DataFrame:
    ok = selection_ledger[selection_ledger["status"].eq("ok")].copy()
    fu = ok[ok["product_vt_symbol"].eq("fu.SHFE")][
        ["return_date", "selection_date", "selected_symbol", "return"]
    ].rename(
        columns={
            "selection_date": "fu_selection_date",
            "selected_symbol": "fu_selected_symbol",
            "return": "fu_return",
        }
    )
    sc = ok[ok["product_vt_symbol"].eq("sc.INE")][
        ["return_date", "selection_date", "selected_symbol", "return"]
    ].rename(
        columns={
            "selection_date": "sc_selection_date",
            "selected_symbol": "sc_selected_symbol",
            "return": "sc_return",
        }
    )
    panel = fu.merge(sc, on="return_date", how="inner", validate="one_to_one")
    panel.sort_values("return_date", inplace=True)
    panel.reset_index(drop=True, inplace=True)
    panel["fu_selection_is_t1"] = panel["fu_selection_date"].lt(panel["return_date"]).astype(int)
    panel["sc_selection_is_t1"] = panel["sc_selection_date"].lt(panel["return_date"]).astype(int)
    return panel


def regression_stats(frame: pd.DataFrame) -> tuple[float, float]:
    if len(frame) < 2:
        return np.nan, np.nan
    x = frame["sc_return"].to_numpy(dtype=float)
    y = frame["fu_return"].to_numpy(dtype=float)
    if not np.isfinite(x).all() or not np.isfinite(y).all() or float(np.var(x)) <= 0:
        return np.nan, np.nan
    design = np.column_stack([np.ones(len(x)), x])
    _, beta = np.linalg.lstsq(design, y, rcond=None)[0]
    correlation = float(np.corrcoef(x, y)[0, 1])
    return float(beta), correlation


def build_event_beta_ledger(events: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for event in events.itertuples(index=False):
        entry_date = pd.Timestamp(event.entry_date).normalize()
        history = panel[panel["return_date"].lt(entry_date)].tail(LOOKBACK).copy()
        history_complete = len(history) == LOOKBACK
        row: dict[str, Any] = {
            "event_id": str(event.event_id),
            "vt_symbol": str(event.vt_symbol),
            "entry_date": entry_date,
            "directions": str(event.directions),
            "total_original_risk_amount": float(event.total_original_risk_amount),
            "is_core_window": int(CORE_START <= entry_date <= CORE_END),
            "history_count": int(len(history)),
            "history_complete": int(history_complete),
            "history_first_date": history["return_date"].min() if len(history) else pd.NaT,
            "history_last_date": history["return_date"].max() if len(history) else pd.NaT,
            "history_date_not_before_entry_count": int(history["return_date"].ge(entry_date).sum()),
            "fu_t1_violation_count": int(history["fu_selection_is_t1"].ne(1).sum()),
            "sc_t1_violation_count": int(history["sc_selection_is_t1"].ne(1).sum()),
        }
        windows = {
            "full126": history,
            "early63": history.head(HALF_WINDOW),
            "late63": history.tail(HALF_WINDOW),
        }
        window_passes: list[bool] = []
        for name, window in windows.items():
            beta, correlation = regression_stats(window) if history_complete else (np.nan, np.nan)
            passed = bool(
                history_complete
                and len(window) == (LOOKBACK if name == "full126" else HALF_WINDOW)
                and math.isfinite(beta)
                and math.isfinite(correlation)
                and beta > 0
                and correlation >= MIN_CORRELATION
            )
            row[f"{name}_count"] = int(len(window))
            row[f"{name}_beta"] = beta
            row[f"{name}_correlation"] = correlation
            row[f"{name}_pass"] = int(passed)
            window_passes.append(passed)
        row["event_beta_pass"] = int(
            history_complete
            and all(window_passes)
            and row["history_date_not_before_entry_count"] == 0
            and row["fu_t1_violation_count"] == 0
            and row["sc_t1_violation_count"] == 0
        )
        rows.append(row)
    result = pd.DataFrame(rows)
    result.sort_values(["entry_date", "event_id"], inplace=True)
    result.reset_index(drop=True, inplace=True)
    return result


def evaluate(events_path: Path = EVENTS_PATH, db_path: Path = DB_PATH) -> dict[str, Any]:
    events, event_audit = load_fu_events(events_path)
    db_hash_before = sha256_file(db_path)
    query_start = events["entry_date"].min() - pd.Timedelta(days=800)
    query_end = events["entry_date"].max()
    ledgers: list[pd.DataFrame] = []
    product_audits: list[dict[str, Any]] = []
    for product, spec in PRODUCT_SPECS.items():
        bars = load_contract_bars(
            db_path,
            prefix=str(spec["prefix"]),
            exchange=str(spec["exchange"]),
            start=query_start,
            end=query_end,
        )
        ledger, audit = build_t1_product_returns(bars, product)
        ledgers.append(ledger)
        product_audits.append(audit)
    selection_ledger = pd.concat(ledgers, ignore_index=True)
    panel = build_common_return_panel(selection_ledger)
    event_beta = build_event_beta_ledger(events, panel)
    db_hash_after = sha256_file(db_path)

    core = event_beta[event_beta["is_core_window"].eq(1)]
    integrity_ok = bool(
        event_audit["events_hash_ok"]
        and event_audit["fu_unique_events"] == event_audit["fu_event_rows"]
        and event_audit["core_event_count"] == 6
        and all(audit["source_duplicate_contract_date_rows"] == 0 for audit in product_audits)
        and all(audit["selection_date_not_before_return_date"] == 0 for audit in product_audits)
        and not panel.duplicated(["return_date"]).any()
        and int(panel["fu_selection_is_t1"].ne(1).sum()) == 0
        and int(panel["sc_selection_is_t1"].ne(1).sum()) == 0
        and db_hash_before == db_hash_after
    )
    all_count = int(len(event_beta))
    complete_count = int(event_beta["history_complete"].sum())
    pass_count = int(event_beta["event_beta_pass"].sum())
    core_complete = int(core["history_complete"].sum())
    core_pass = int(core["event_beta_pass"].sum())
    complete_rate = complete_count / all_count
    pass_rate = pass_count / all_count

    gates = pd.DataFrame(
        [
            {
                "gate_id": "input_and_return_integrity",
                "threshold": "all invariants true",
                "evidence": int(integrity_ok),
                "passed": int(integrity_ok),
            },
            {
                "gate_id": "core_history_complete_6_of_6",
                "threshold": "6",
                "evidence": core_complete,
                "passed": int(core_complete == 6),
            },
            {
                "gate_id": "all_history_complete_rate_ge_90pct",
                "threshold": MIN_ALL_EVENT_RATE,
                "evidence": complete_rate,
                "passed": int(complete_rate >= MIN_ALL_EVENT_RATE),
            },
            {
                "gate_id": "core_three_window_beta_corr_pass_6_of_6",
                "threshold": "6",
                "evidence": core_pass,
                "passed": int(core_pass == 6),
            },
            {
                "gate_id": "all_three_window_beta_corr_pass_rate_ge_90pct",
                "threshold": MIN_ALL_EVENT_RATE,
                "evidence": pass_rate,
                "passed": int(pass_rate >= MIN_ALL_EVENT_RATE),
            },
        ]
    )
    local_gate_pass = bool(gates["passed"].eq(1).all())
    decision_label = (
        "LOCAL_BETA_GATE_PASS_REQUIRES_OPTION_CHAIN"
        if local_gate_pass
        else "CLOSE_LINE_BASIS_RISK_INELIGIBLE"
    )
    decision = {
        "decision": decision_label,
        "local_beta_gate_pass": local_gate_pass,
        "option_chain_network_called": False,
        "option_chain_coverage_evaluated": False,
        "ready_for_option_strategy_ab": False,
        "ready_for_live": False,
        "event_count": all_count,
        "core_event_count": int(len(core)),
        "history_complete_count": complete_count,
        "history_complete_rate": complete_rate,
        "event_beta_pass_count": pass_count,
        "event_beta_pass_rate": pass_rate,
        "core_history_complete_count": core_complete,
        "core_event_beta_pass_count": core_pass,
        "failed_gate_ids": gates.loc[gates["passed"].ne(1), "gate_id"].tolist(),
        "events_sha256": event_audit["events_sha256"],
        "events_hash_ok": event_audit["events_hash_ok"],
        "database_sha256_before": db_hash_before,
        "database_sha256_after": db_hash_after,
        "database_hash_stable": db_hash_before == db_hash_after,
        "query_start": query_start.date().isoformat(),
        "query_end": query_end.date().isoformat(),
        "lookback": LOOKBACK,
        "half_window": HALF_WINDOW,
        "minimum_correlation": MIN_CORRELATION,
        "minimum_all_event_rate": MIN_ALL_EVENT_RATE,
        "reason": (
            "FU-SC basis qualification failed; option-chain and performance work are forbidden."
            if not local_gate_pass
            else "Local basis qualification passed; only historical SC option-chain coverage may proceed."
        ),
    }
    lineage = {
        "events_path": str(events_path),
        "database_path": str(db_path),
        "event_audit": event_audit,
        "product_audits": product_audits,
        "panel_rows": int(len(panel)),
        "panel_first_date": panel["return_date"].min().date().isoformat(),
        "panel_last_date": panel["return_date"].max().date().isoformat(),
        "future_or_same_day_event_history_rows": int(
            event_beta["history_date_not_before_entry_count"].sum()
        ),
        "fu_t1_violation_rows": int(event_beta["fu_t1_violation_count"].sum()),
        "sc_t1_violation_rows": int(event_beta["sc_t1_violation_count"].sum()),
    }
    return {
        "events": events,
        "selection_ledger": selection_ledger,
        "panel": panel,
        "event_beta": event_beta,
        "gates": gates,
        "decision": decision,
        "lineage": lineage,
    }


def write_outputs(output_dir: Path = OUTPUT_DIR) -> dict[str, Path]:
    result = evaluate()
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "selection": output_dir / "stage001_contract_selection_ledger.csv.gz",
        "panel": output_dir / "stage001_product_return_panel.csv.gz",
        "event_beta": output_dir / "stage001_fu_event_beta_ledger.csv",
        "gates": output_dir / "stage001_gate_matrix.csv",
        "decision": output_dir / "stage001_decision.json",
        "lineage": output_dir / "stage001_lineage.json",
        "report": output_dir / "stage001_report.md",
        "manifest": output_dir / "stage001_manifest.csv",
    }
    _atomic_csv(result["selection_ledger"], paths["selection"], gzip=True)
    _atomic_csv(result["panel"], paths["panel"], gzip=True)
    _atomic_csv(result["event_beta"], paths["event_beta"])
    _atomic_csv(result["gates"], paths["gates"])
    _atomic_text(paths["decision"], json.dumps(result["decision"], indent=2, sort_keys=True) + "\n")
    _atomic_text(paths["lineage"], json.dumps(result["lineage"], indent=2, sort_keys=True) + "\n")
    decision = result["decision"]
    worst = result["event_beta"].sort_values(
        ["event_beta_pass", "full126_correlation", "entry_date"], ascending=[True, True, True]
    )
    report_lines = [
        "# Stage001 FU-SC T-1 beta gate",
        "",
        f"- decision: `{decision['decision']}`",
        f"- events: `{decision['event_count']}`; core: `{decision['core_event_count']}`",
        f"- history complete: `{decision['history_complete_count']}/{decision['event_count']}`",
        f"- beta/corr pass: `{decision['event_beta_pass_count']}/{decision['event_count']}`",
        f"- core beta/corr pass: `{decision['core_event_beta_pass_count']}/6`",
        f"- option-chain network called: `{decision['option_chain_network_called']}`",
        "",
        "## Gate matrix",
        "",
        result["gates"].to_markdown(index=False),
        "",
        "## Lowest full-window correlations",
        "",
        worst[
            [
                "entry_date",
                "vt_symbol",
                "history_count",
                "full126_beta",
                "full126_correlation",
                "early63_correlation",
                "late63_correlation",
                "event_beta_pass",
            ]
        ].head(12).to_markdown(index=False, floatfmt=".6f"),
    ]
    _atomic_text(paths["report"], "\n".join(report_lines) + "\n")

    manifest_rows = []
    for name, path in paths.items():
        if name == "manifest":
            continue
        manifest_rows.append(
            {"artifact": name, "path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        )
    _atomic_csv(pd.DataFrame(manifest_rows).sort_values("artifact"), paths["manifest"])
    return paths


if __name__ == "__main__":
    written = write_outputs()
    decision = json.loads(written["decision"].read_text(encoding="utf-8"))
    print(json.dumps({"decision": decision["decision"], "outputs": {k: str(v) for k, v in written.items()}}, sort_keys=True))

