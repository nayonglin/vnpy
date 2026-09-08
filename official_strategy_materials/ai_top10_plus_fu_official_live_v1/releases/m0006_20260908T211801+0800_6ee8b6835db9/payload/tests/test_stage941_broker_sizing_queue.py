import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples/portfolio_backtesting"))
import run_qmt_roll_stage941_official_live_c9_detector as detector


def test_reconciled_open_and_close_both_advance_snapshot_watermark():
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("CREATE TABLE intents(state TEXT, updated_epoch_ns INTEGER)")
        connection.executemany("INSERT INTO intents VALUES(?, ?)", [("reconciled", 100), ("reconciled", 200), ("ready", 300)])
        assert detector._broker_snapshot_watermark(connection) == 200
    finally:
        connection.close()


def test_sent_open_can_only_defer_to_explicit_broker_proof():
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("CREATE TABLE intents(intent_id TEXT, target_date TEXT, intent_kind TEXT, state TEXT, ledger_disposition TEXT)")
        connection.execute("INSERT INTO intents VALUES('sent', '2026-09-07', 'open', 'sent', 'sent')")
        assert detector._broker_open_queue_state(connection, target_date="2026-09-07")[1]
        assert detector._broker_open_queue_state(connection, target_date="2026-09-07", verify_sent=True) == ({"sent"}, "")
    finally:
        connection.close()


@pytest.mark.parametrize("state", ["ready", "leased", "sending", "side_effect_unknown", "sent"])
def test_outstanding_open_blocks_reusing_the_same_account_budget(state):
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("CREATE TABLE intents(intent_id TEXT, target_date TEXT, intent_kind TEXT, state TEXT, ledger_disposition TEXT)")
        connection.execute("INSERT INTO intents VALUES('old', '2026-09-07', 'open', ?, '')", (state,))
        existing, blocker = detector._broker_open_queue_state(connection, target_date="2026-09-07")
        assert existing == {"old"}
        assert blocker == "broker_sizing_unreconciled_open_intent"
    finally:
        connection.close()


def test_reconciled_open_is_not_resized_and_close_does_not_reserve_open_budget():
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("CREATE TABLE intents(intent_id TEXT, target_date TEXT, intent_kind TEXT, state TEXT, ledger_disposition TEXT)")
        connection.execute("INSERT INTO intents VALUES('done', '2026-09-07', 'open', 'reconciled', '')")
        connection.execute("INSERT INTO intents VALUES('stop', '2026-09-07', 'close', 'ready', '')")
        assert detector._broker_open_queue_state(connection, target_date="2026-09-07") == ({"done"}, "")
    finally:
        connection.close()
