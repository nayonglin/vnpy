"""Re-render the identity-closed Stage061 page with per-panel candle-aligned events."""
import csv
import hashlib
import json
from pathlib import Path
import shutil

import stage061_2022_recap as parent

LINE = Path(__file__).resolve().parents[1]
SOURCE = parent.DESTINATION
SOURCE_SHA = "d51586ebb2aa6f9c1cc9752f76ab5d5a4053cc97bca2a3f0519110c8f6c59e01"
DESTINATION = SOURCE.parent / "stage063_s21_200k_touch_2022_recap_aligned_v1"
PERIODS = ("day30", "day10", "monthly", "weekly", "daily")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def embedded(page):
    return json.JSONDecoder().raw_decode(page.split("const records=", 1)[1])[0]


def candle_index(record, period, day):
    data = record[period]
    if period == "daily":
        return data["date"].index(day)
    if period == "monthly":
        return data["label"].index(day[:7])
    for i, label in enumerate(data["label"]):
        # Actual frozen weekly labels are Saturday/Friday; fixed-day labels use first~last trading day.
        first, last = label[:10], label[11:21]
        if first <= day <= last:
            return i
    raise ValueError(f"missing event candle {record['meta']['open_trade_id']}/{period}/{day}")


def write():
    if DESTINATION.exists():
        raise FileExistsError(DESTINATION)
    assert sha(SOURCE / "SHA256SUMS") == SOURCE_SHA
    for row in (SOURCE / "SHA256SUMS").read_text().splitlines():
        digest, name = row.split("  ", 1)
        path = Path(name)
        if not path.is_absolute():
            path = SOURCE / path
        assert sha(path) == digest, path
    bundle = parent.load_frozen(parent.RUN)
    records = embedded((SOURCE / "index.html").read_text())
    summary = json.loads((SOURCE / "summary.json").read_text())
    assert len(records) == len(bundle.closed) == 167
    assert summary["backtest_metrics"] == bundle.metrics
    closed = bundle.closed.set_index("cycle")
    rows = []
    for record in records:
        meta = record["meta"]
        cycle = int(meta["open_trade_id"])
        assert (meta["entry_date"], meta["exit_date"], meta["realized_pnl"]) == (
            closed.loc[cycle, "entry_day"], closed.loc[cycle, "exit_day"], closed.loc[cycle, "net_pnl"])
        for period in PERIODS:
            for event in ("entry", "exit"):
                day = meta[event + "_date"]
                index = candle_index(record, period, day)
                data = record[period]
                rows.append(dict(cycle=cycle, period=period, event=event, date=day,
                                 actual_daily_x=meta[event + "_x"], candle_x=data["x"][index],
                                 candle_label=data["date" if period == "daily" else "label"][index]))
    assert len(rows) == 1670
    # Reuse the canonical renderer, then the existing source-specific ledger formatter.
    page = parent.adapter.append_ledgers(parent.recap.renderer._html(records, summary), bundle)
    assert embedded(page) == records  # No OHLC, MA, fill, dates, PnL, or source disclosures changed.
    assert "function candleX(" in page
    DESTINATION.mkdir(parents=True)
    (DESTINATION / "index.html").write_text(page)
    for name in ("summary.json", "chart_manifest.csv", "scoped_fills.csv", "annual_contributions.csv"):
        shutil.copyfile(SOURCE / name, DESTINATION / name)
    with (DESTINATION / "alignment.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    receipt = dict(parent_recap_manifest_sha256=SOURCE_SHA,
                   source_strategy_manifest_sha256=parent.SOURCE_SHA,
                   source_audit_sha256=parent.AUDIT_SHA,
                   renderer_sha256=sha(Path(parent.recap.renderer.__file__)),
                   adapter_sha256=sha(Path(__file__)),
                   chart_records_unchanged=True, summary_unchanged=True,
                   records=len(records), aligned_endpoints=len(rows),
                   strategy_rerun=False, market_download=False, production_access=False)
    (DESTINATION / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    manifest = "".join(sha(p) + "  " + p.name + "\n"
                       for p in sorted(DESTINATION.iterdir()) if p.is_file())
    (DESTINATION / "SHA256SUMS").write_text(manifest)
    print(json.dumps(receipt, ensure_ascii=False))
    print(DESTINATION / "index.html")


if __name__ == "__main__":
    write()
