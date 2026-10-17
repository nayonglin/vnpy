"""Independent read-only review of the frozen Stage266 research reader.

Uses an actual clean contract and memory-only fault injection. No cleaner import,
training sample generation, feature calculation, label generation or model fit.
"""
from datetime import datetime
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

import stage266_independent_validate as audit
import stage266_training_reader as reader


def main():
    base = audit.LINE / "outputs/stage266_clean_daily"
    out = audit.BASE
    contract = audit.json_load(base / "contract.json")
    dbpath = Path(contract["db_path"])
    before = audit.sha(dbpath)
    reader_path = Path(reader.__file__)
    test_path = audit.LINE / "tools/test_stage266_training_reader.py"
    expected_sha = "eaa0b51a4e76ab139c4b9b64af005304a19c895b20529f7366b8b88b6ad86c2c"
    if audit.sha(reader_path) != expected_sha:
        raise ValueError("reader_changed_since_freeze")
    dates = [datetime.strptime(str(int(x)), "%Y%m%d").date() for x in np.load(contract["calendar_path"], allow_pickle=False)]
    with audit.read_only_connection(dbpath) as db:
        candidates = list(db.execute("SELECT contract_epoch_id,MAX(trade_date) AS last_day,SUM(legacy108_row_usable) AS usable FROM daily_bars GROUP BY contract_epoch_id HAVING usable>=120 ORDER BY usable DESC LIMIT 30"))
    selected = None
    for epoch, last_day, _ in candidates:
        frame = reader.load_contract_bars(dbpath, contract_epoch_id=epoch, candidate_date=last_day)
        report = reader.qualify_legacy108_window(frame, candidate_date=last_day, expected_trade_dates=dates)
        if report["eligible"]:
            selected = epoch, last_day, frame, report
            break
    if selected is None:
        raise ValueError("no_real_complete_120_day_fixture_found")
    epoch, candidate, frame, report = selected
    window = reader.require_legacy108_window(frame, candidate_date=candidate, expected_trade_dates=dates)
    if len(window) != 120 or not window.open_oi_status.eq("source_observed").all():
        raise AssertionError("real_120_day_window_failed")
    rejected = {}

    def must_reject(name, altered):
        try:
            reader.require_legacy108_window(altered, candidate_date=candidate, expected_trade_dates=dates)
        except reader.TrainingDataError:
            rejected[name] = True
        else:
            rejected[name] = False

    altered = frame.drop(frame.index[frame.date.eq(window.date.iloc[60])]).copy()
    # Pretending attrs certify 120 observations must not hide a calendar gap.
    altered.attrs["legacy108_window_qualified"] = True
    must_reject("one_expected_date_missing_despite_more_than_120_total_rows_and_forged_attrs", altered)
    for name, fields in (
        ("missing_open_oi_not_filled", {"open_oi": np.nan, "open_oi_status": "missing_not_imputed"}),
        ("close_oi_copied_to_open_but_not_observed", {"open_oi": window.close_oi.iloc[60], "open_oi_status": "missing_not_imputed"}),
        ("positive_flat_V0", {"open": 10., "high": 10., "low": 10., "close": 10., "volume": 0.}),
        ("OHLC_outside_range", {"close": window.high.iloc[60] + 1}),
        ("negative_open_oi", {"open_oi": -1.}),
        ("stored_row_eligibility_false", {"train_eligible": 0}),
    ):
        altered = frame.copy()
        for field, value in fields.items():
            altered.loc[altered.date.eq(window.date.iloc[60]), field] = value
        must_reject(name, altered)
    altered = frame.copy()
    altered.loc[altered.date.eq(window.date.iloc[60]), "contract_epoch_id"] = "DCE.X.202701"
    must_reject("mixed_contract_epochs", altered)
    # Selected-only historical bar with no opening observation stays NaN on read.
    with audit.read_only_connection(dbpath) as db:
        missing = db.execute("SELECT contract_epoch_id,trade_date,close_oi FROM daily_bars WHERE open_oi IS NULL LIMIT 1").fetchone()
    missing_frame = reader.load_contract_bars(dbpath, contract_epoch_id=missing[0], start_date=missing[1], candidate_date=missing[1])
    missing_preserved = len(missing_frame) == 1 and pd.isna(missing_frame.open_oi.iloc[0]) and not bool(missing_frame.legacy108_usable.iloc[0])
    tests = unittest.defaultTestLoader.discover(str(test_path.parent), pattern=test_path.name)
    with (out / "reader_tests.log").open("w") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(tests)
    same_bytes = before == audit.sha(dbpath) == contract["final_database_sha256"]
    passed = all(rejected.values()) and missing_preserved and result.wasSuccessful() and same_bytes
    report = {
        "generated_at": datetime.now().astimezone().isoformat(), "status": "PASS" if passed else "FAIL",
        "reader_sha256": expected_sha, "reader_tests_sha256": audit.sha(test_path), "review_script_sha256": audit.sha(__file__),
        "database_sha256": before, "database_unchanged": same_bytes, "tests_run": result.testsRun,
        "test_failures": len(result.failures), "test_errors": len(result.errors),
        "actual_default_120_window": {"contract_epoch_id": epoch, "candidate_date": candidate, "rows": len(window), "first": str(window.date.iloc[0].date()), "last": str(window.date.iloc[-1].date())},
        "memory_only_faults_rejected": rejected, "actual_missing_open_oi_preserved": missing_preserved,
        "review_findings": [],
        "limits": ["Public window_rows is configurable for diagnostics. A future training entry must freeze 120; reader attrs alone do not certify a model sample.",
                   "Only feature fields/calendar checked; 60 future source dates, point-in-time tradability, splits and model labels remain ungenerated/unqualified.",
                   "No 108 feature vectors or training observations generated by this review."],
        "main_database_writes": 0, "new_downloads": 0, "financial_backtests": 0, "model_fits": 0,
    }
    audit.json_save(out / "independent_reader_review.json", report)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
