from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import zipfile

import numpy as np
import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/stage013_cffex_root_source"
OLD = ROOT.parent / "futures_trend_xgboost_cffex_macro_state_residual"
OLD_DATA = OLD / "artifacts/stage001_cffex_macro_contract"
HELPER = OLD / "tools/stage001_cffex_macro_contract.py"
ROOTS = ("IF", "IH", "IC", "T", "TF", "TS")
END = "2026-08-28"
EVENTS = ROOT / "artifacts/stage001_history_qualification/event_features.csv"
LIFECYCLE = ROOT / "artifacts/stage003_cancelled_lifecycle/event_lifecycles.csv"
CALENDAR = ROOT.parent / "futures_trend_xgboost_formal_signal_marginal_utility_v4/artifacts/stage004_counterfactual_validation/workers/A/daily.csv"
EVENT_COLUMNS = ["event_id", "decision_date", "product_vt_symbol", "contract_vt_symbol", "direction"]
FIXED = {
    HELPER: "cd9d9e4119b22af91b27febf6f8658455c48fb8e58424ec7ab7d90a4608ebfb3",
    OLD_DATA / "artifact_manifest.json": "d602121e9b6cd8c04bdbb466ef921d34494a96164ff5106e0de359535cfe111b",
    OLD_DATA / "summary.json": "b7467600b1432b1e5da21848c481fa9928b6f5f3365d32c15510dc574635d439",
    EVENTS: "33c48a4a3976e644365ceeccfadbf236f24bc327ae17413c363b43de7e69bcf1",
    LIFECYCLE: "d87652c9bb77612afbb03bf8cada3d63a00224a95e31be03cfd21495addee57b",
    CALENDAR: "ec4838ed9f67e263cbce59352b9d908f069374dd04cd88ea312b795a651dc981",
}
_helper = None


def identity(path):
    return {"path": str(path.resolve()), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def helper():
    global _helper
    if _helper is None:
        if identity(HELPER)["sha256"] != FIXED[HELPER]:
            raise RuntimeError("cffex_csv_helper_changed")
        spec = importlib.util.spec_from_file_location("root_cffex_csv_helpers", HELPER)
        _helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_helper)
    return _helper


def iso_dates(values):
    strings = values.astype(str)
    if not strings.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        raise RuntimeError("date_format_invalid")
    try:
        return pd.to_datetime(strings, format="%Y-%m-%d", errors="raise")
    except ValueError as exc:
        raise RuntimeError("date_invalid") from exc


def normalize(bars):
    frame = bars.copy()
    frame["date"] = iso_dates(frame.date).dt.strftime("%Y-%m-%d")
    if frame.duplicated(["date", "symbol"]).any():
        raise RuntimeError("duplicate_contract_day")
    parsed = frame.symbol.str.extract(r"^(IF|IH|IC|T|TF|TS)(\d{2})(\d{2})$")
    if parsed.isna().any().any() or not parsed[0].equals(frame.root):
        raise RuntimeError("contract_identity_invalid")
    months = parsed[2].astype(int)
    if not months.between(1, 12).all():
        raise RuntimeError("contract_month_invalid")
    for name in ("close", "volume", "open_interest"):
        frame[name] = pd.to_numeric(frame[name], errors="coerce")
    frame["delivery_month"] = "20" + parsed[1] + "-" + parsed[2]
    numeric = frame[["close", "volume", "open_interest"]]
    frame["quality_ok"] = (np.isfinite(numeric).all(axis=1) & frame.close.gt(0)
                           & frame.volume.ge(0) & frame.open_interest.gt(0)
                           & frame.delivery_month.ge(frame.date.str[:7]))
    return frame.sort_values(["date", "root", "symbol"]).reset_index(drop=True)


def parse_archive(month, content):
    if not re.fullmatch(r"\d{6}", month):
        raise RuntimeError("archive_month_invalid")
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise RuntimeError("archive_not_zip") from exc
    frames, days = [], []
    with archive:
        infos = archive.infolist()
        if sum(info.file_size for info in infos) > 100_000_000:
            raise RuntimeError("archive_unsafe_expanded_size")
        if any(PurePosixPath(info.filename).is_absolute() or ".." in PurePosixPath(info.filename).parts for info in infos):
            raise RuntimeError("archive_unsafe_path")
        names = [info.filename for info in infos if re.fullmatch(r"\d{8}_1\.csv", PurePosixPath(info.filename).name)]
        if not names or len({PurePosixPath(name).name for name in names}) != len(names):
            raise RuntimeError("archive_missing_or_duplicate_daily_files")
        support = helper()
        for name in sorted(names):
            token = PurePosixPath(name).name[:8]
            if token[:6] != month:
                raise RuntimeError("archive_daily_month_mismatch")
            day = pd.to_datetime(token, format="%Y%m%d", errors="raise").strftime("%Y-%m-%d")
            raw = support._read_cffex_csv(archive.read(name), name)
            aliases = {"symbol": ("\u5408\u7ea6\u4ee3\u7801", "\u5408\u7ea6", "instrument_id", "instrument", "symbol"),
                       "close": ("\u4eca\u6536\u76d8", "\u6536\u76d8\u4ef7", "close", "close_price"),
                       "volume": ("\u6210\u4ea4\u91cf", "volume"), "open_interest": ("\u6301\u4ed3\u91cf", "open_interest")}
            columns = {key: support._resolve_column(raw, choices, key) for key, choices in aliases.items()}
            symbols = raw[columns["symbol"]].astype(str).str.strip().str.upper()
            roots = symbols.str.extract(r"^([A-Z]+)", expand=False)
            keep = symbols.str.fullmatch(r"(?:IF|IH|IC|T|TF|TS)\d+") & roots.isin(ROOTS)
            part = pd.DataFrame({"date": day, "root": roots[keep], "symbol": symbols[keep]})
            for field in ("close", "volume", "open_interest"):
                part[field] = support._numeric(raw.loc[keep, columns[field]])
            frames.append(part)
            days.append(day)
    return normalize(pd.concat(frames, ignore_index=True)), days


def select_returns(bars):
    frame = normalize(bars)
    days = sorted(frame.date.unique())
    roots = sorted(frame.root.unique())
    groups = {key: part for key, part in frame.groupby(["date", "root"])}
    records, previous_selected = [], {}
    for index in range(1, len(days)):
        day, prior_day = days[index], days[index - 1]
        for root in roots:
            prior, current = groups.get((prior_day, root)), groups.get((day, root))
            if prior is None or current is None:
                raise RuntimeError(f"market_root_day_missing:{root}:{day}")
            eligible = prior.loc[prior.quality_ok].sort_values(
                ["open_interest", "volume", "symbol"], ascending=[False, False, True], kind="stable")
            if eligible.empty:
                raise RuntimeError(f"prior_eligible_empty:{root}:{prior_day}")
            chosen = eligible.iloc[0]
            endpoint = current.loc[current.symbol.eq(chosen.symbol)]
            if len(endpoint) != 1:
                raise RuntimeError(f"selected_current_missing:{root}:{day}:{chosen.symbol}")
            price = float(endpoint.iloc[0].close)
            if not np.isfinite(price) or price <= 0:
                raise RuntimeError(f"selected_current_price_invalid:{root}:{day}")
            records.append({"date": day, "root": root, "symbol": chosen.symbol, "selection_date": prior_day,
                            "prior_close": float(chosen.close), "close": price,
                            "selection_open_interest": float(chosen.open_interest), "selection_volume": float(chosen.volume),
                            "roll_event": root in previous_selected and previous_selected[root] != chosen.symbol,
                            "product_return": price / float(chosen.close) - 1})
            previous_selected[root] = chosen.symbol
    return pd.DataFrame(records)


def coverage(decisions, selected, calendar):
    iso_dates(decisions)
    iso_dates(pd.Series(calendar))
    if len(set(calendar)) != len(calendar) or list(calendar) != sorted(calendar):
        raise RuntimeError("calendar_inventory_invalid")
    if selected.duplicated(["date", "root"]).any():
        raise RuntimeError("selected_duplicate_root_day")
    if set(selected.root.unique()) != set(ROOTS):
        raise RuntimeError("selected_root_inventory_invalid")
    pivot = selected.pivot(index="date", columns="root", values="product_return").reindex(columns=ROOTS).sort_index()
    expected = sorted(set(calendar) | {day for day in pivot.index if day < calendar[0]})
    output = []
    for day in decisions:
        if day not in expected:
            raise RuntimeError("decision_outside_calendar")
        prior_days = [value for value in expected if value < day]
        source = prior_days[-1] if prior_days else None
        if source not in pivot.index:
            status = "missing_prior_day"
        elif len(prior_days) < 120:
            status = "insufficient_history"
        elif not np.isfinite(pivot.reindex(prior_days[-120:]).to_numpy()).all():
            status = "incomplete_window"
        else:
            status = "available"
        output.append({"decision_date": day, "source_date": source, "coverage_status": status,
                       "expected_prior_observations": min(len(prior_days), 120)})
    return pd.DataFrame(output)


def download(month, destination):
    if month not in ("202606", "202607", "202608"):
        raise RuntimeError("download_month_outside_contract")
    path = destination / f"{month}.response"
    receipt = destination / f"{month}.request.json"
    if path.exists() or receipt.exists():
        raise RuntimeError("download_attempt_already_exists")
    url = f"https://www.cffex.com.cn/sj/historysj/{month}/zip/{month}.zip"
    record = {"month": month, "url": url, "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "http_status": None, "attempts": 1, "retries": 0}
    try:
        response = requests.get(url, headers={"User-Agent": "vnpy-research-source-audit/1.0",
                               "Accept": "application/zip,application/octet-stream", "Referer": "https://www.cffex.com.cn/lssjxz/"},
                                timeout=(5, 20), allow_redirects=False)
        path.write_bytes(response.content)
        record.update(http_status=response.status_code, response=identity(path))
        if response.status_code != 200:
            raise RuntimeError(f"source_http_failure:{month}:{response.status_code}")
        return response.content
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}:{exc}"
        raise
    finally:
        record["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        save(receipt, record)


def source_identities():
    files = {str(path): identity(path) for path in FIXED}
    for path, digest in FIXED.items():
        if files[str(path)]["sha256"] != digest:
            raise RuntimeError(f"frozen_input_changed:{path.name}")
    old_manifest = json.loads((OLD_DATA / "artifact_manifest.json").read_text())["files"]
    months = pd.period_range("2019-06", "2026-05", freq="M").strftime("%Y%m").tolist()
    names = {f"raw_archives/{month}.zip" for month in months}
    if {key for key in old_manifest if key.startswith("raw_archives/")} != names:
        raise RuntimeError("old_archive_inventory_mismatch")
    for name in sorted(names):
        path = OLD_DATA / name
        actual, expected = identity(path), old_manifest[name]
        if actual["bytes"] != expected["size"] or actual["sha256"] != expected["sha256"]:
            raise RuntimeError(f"old_archive_changed:{name}")
        files[str(path)] = actual
    paths = [Path(__file__), ROOT / "tests/test_stage013_cffex_root_source.py",
             ROOT / "stages/20260906_0317_stage013_cffex_root_source_contract.md",
             ROOT / "tools/stage011_basis_source_audit.py"]
    files.update({str(path): identity(path) for path in paths})
    return files, months


def run():
    if OUTPUT.exists():
        raise RuntimeError("cffex_root_source_output_already_exists")
    files, months = source_identities()
    OUTPUT.mkdir(parents=True)
    save(OUTPUT / "input_manifest.json", files)
    raw_dir = OUTPUT / "raw_extension"
    raw_dir.mkdir()
    frames, inventory, outputs = [], [], {}
    summary = {"status": "source_not_qualified", "new_historical_models": 0, "new_labels": 0,
               "new_backtests": 0, "reviewers": 0, "error": None}
    try:
        for month in months + ["202606", "202607", "202608"]:
            content = ((OLD_DATA / f"raw_archives/{month}.zip").read_bytes() if month in months else download(month, raw_dir))
            frame, days = parse_archive(month, content)
            frames.append(frame)
            inventory.append({"month": month, "days": len(days), "core_rows": len(frame),
                              "prior_eligible_rows": int(frame.quality_ok.sum()), "first_date": min(days), "last_date": max(days),
                              "archive_sha256": hashlib.sha256(content).hexdigest(), "source": "frozen" if month in months else "download"})
            save(OUTPUT / "month_inventory.json", inventory)
        all_bars = pd.concat(frames, ignore_index=True)
        summary["post_analysis_end_rows_excluded"] = int(all_bars.date.gt(END).sum())
        bars = all_bars.loc[all_bars.date.le(END)].copy()
        if set(bars.root.unique()) != set(ROOTS):
            raise RuntimeError("source_six_roots_incomplete")
        bars.to_csv(OUTPUT / "core_bars.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
        selected = select_returns(bars)
        selected.to_csv(OUTPUT / "same_contract_returns.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
        calendar = pd.read_csv(CALENDAR, usecols=["date"]).date.tolist()
        if calendar[0] != "2020-01-02" or calendar[-1] != END:
            raise RuntimeError("frozen_calendar_endpoints_changed")
        ev = pd.read_csv(EVENTS, usecols=EVENT_COLUMNS)
        if len(ev) != 276 or ev.event_id.duplicated().any():
            raise RuntimeError("frozen_event_inventory_changed")
        covered = coverage(ev.decision_date, selected, calendar)
        covered = pd.concat([ev.reset_index(drop=True), covered.drop(columns="decision_date")], axis=1)
        full_calendar = coverage(pd.Series(calendar), selected, calendar)
        spec = importlib.util.spec_from_file_location("cffex_root_maturity_helpers", ROOT / "tools/stage011_basis_source_audit.py")
        maturity_helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(maturity_helper)
        maturity = maturity_helper.maturity_counts(covered, pd.read_csv(LIFECYCLE, usecols=["event_id", "end_date", "status"]),
            pd.date_range("2020-01-01", "2026-08-01", freq="MS").strftime("%Y-%m-%d").tolist())
        for name, frame in {"event_coverage.csv": covered, "calendar_coverage.csv": full_calendar, "monthly_maturity.csv": maturity}.items():
            frame.to_csv(OUTPUT / name, index=False)
        ready = covered.coverage_status.eq("available").all() and full_calendar.coverage_status.eq("available").all()
        first = maturity.loc[maturity.available_mature_count.ge(60), "cutoff"]
        summary.update(status="source_qualified_for_feature_contract" if ready else "source_coverage_incomplete",
                       core_rows=len(bars), source_dates=bars.date.nunique(), source_start=bars.date.min(), source_end=bars.date.max(),
                       source_months=len(inventory), selected_rows=len(selected), roll_observations=int(selected.roll_event.sum()),
                       event_count=len(covered), event_coverage=covered.coverage_status.value_counts().to_dict(),
                       calendar_count=len(full_calendar), calendar_coverage=full_calendar.coverage_status.value_counts().to_dict(),
                       first_month_60_available_mature=first.iloc[0] if len(first) else None,
                       historical_vintage_verified=False, pit_rule="exact_previous_trading_day_same_contract_returns_120_observations")
    except Exception as exc:
        summary["error"] = f"{type(exc).__name__}:{exc}"
    if any(identity(Path(path)) != expected for path, expected in files.items()):
        raise RuntimeError("source_inputs_changed_during_run")
    outputs = {str(path.relative_to(OUTPUT)): identity(path) for path in sorted(OUTPUT.rglob("*")) if path.is_file()}
    summary.update(input_count=len(files), verified_old_archives=len(months), outputs=outputs,
                   created_at_utc=datetime.now(timezone.utc).isoformat())
    save(OUTPUT / "summary.json", summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, allow_nan=False))
