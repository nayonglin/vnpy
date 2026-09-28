import gzip
import hashlib
import importlib.util
from pathlib import Path

import pytest


PATH = Path(__file__).resolve().parents[1] / "tools/stage005_label_collection.py"


def module():
    assert PATH.exists(), "label collector implementation missing"
    spec = importlib.util.spec_from_file_location("label_collection_test", PATH)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def archived(tmp_path):
    raw = b"date,equity\n2020-01-02,150000\n"
    path = tmp_path / "daily.csv.gz"
    path.write_bytes(gzip.compress(raw, mtime=0))
    identity = {"archive": {"path": str(path), "size": path.stat().st_size,
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
                "raw_size": len(raw), "raw_sha256": hashlib.sha256(raw).hexdigest()}
    return path, identity


def test_archive_checks_decoded_identity(tmp_path):
    path, identity = archived(tmp_path)
    module().verify_archive(path, identity)


@pytest.mark.parametrize("field,value", [("raw_size", 0), ("raw_sha256", "bad")])
def test_archive_rejects_wrong_decoded_identity(tmp_path, field, value):
    path, identity = archived(tmp_path)
    identity[field] = value
    with pytest.raises(RuntimeError, match="decoded_archive_changed"):
        module().verify_archive(path, identity)


def test_archive_rejects_changed_compressed_bytes(tmp_path):
    path, identity = archived(tmp_path)
    path.write_bytes(gzip.compress(b"other", mtime=0))
    with pytest.raises(RuntimeError, match="archive_changed"):
        module().verify_archive(path, identity)


def plan():
    return {"jobs": [{"event_id": "a", "status": "mature", "end_date": "2020-01-03"},
                     {"event_id": "b", "status": "mature_cancelled_unfilled", "end_date": "2020-01-04"}],
            "censored": [{"event_id": "c", "status": "right_censored_open", "end_date": None}]}


def label():
    return {"event_id": "a", "status": "passed", "marginal": {"return_marginal": -0.01,
                                                                  "drawdown_marginal": 0.02}}


def test_pending_and_censored_labels_stay_missing():
    rows, ready = module().label_rows(plan(), {"a": label()})
    assert not ready
    assert [row["label_status"] for row in rows] == ["verified", "pending", "censored"]
    assert rows[0]["return_marginal"] == -0.01
    assert all(row["return_marginal"] is None and row["drawdown_marginal"] is None for row in rows[1:])


def test_only_complete_closed_inventory_unlocks_training():
    other = {**label(), "event_id": "b"}
    rows, ready = module().label_rows(plan(), {"a": label(), "b": other})
    assert ready
    assert rows[-1]["label_status"] == "censored"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), None])
def test_invalid_label_is_not_silently_dropped(value):
    item = label()
    item["marginal"]["return_marginal"] = value
    with pytest.raises(RuntimeError, match="invalid_marginal"):
        module().label_rows(plan(), {"a": item})


def test_unknown_or_duplicate_event_rejected():
    m = module()
    with pytest.raises(RuntimeError, match="label_inventory_invalid"):
        m.label_rows(plan(), {"unknown": label()})
    p = plan()
    p["censored"][0]["event_id"] = "a"
    with pytest.raises(RuntimeError, match="label_inventory_invalid"):
        m.label_rows(p, {})


def test_censored_event_cannot_receive_label():
    with pytest.raises(RuntimeError, match="label_inventory_invalid"):
        module().label_rows(plan(), {"c": {**label(), "event_id": "c"}})
