import gzip
import hashlib
import importlib.util
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def module():
    path = Path(__file__).resolve().parents[1] / "tools/stage006_prefix_equivalence.py"
    spec = importlib.util.spec_from_file_location("stage006_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prefix_ignores_only_dates_after_frozen_end(module):
    full = pd.DataFrame({"date": ["2022-03-14", "2022-03-15", "2022-03-16"], "equity": [100, 101, 70]})
    short = pd.DataFrame({"date": ["2022-03-14", "2022-03-15"], "equity": [100.0, 101.0]})
    module.compare_prefix(full, short, "date", "2022-03-15")
    short.loc[1, "equity"] = 101.00000001
    with pytest.raises(AssertionError):
        module.compare_prefix(full, short, "date", "2022-03-15")


def test_archive_is_lossless_and_only_removes_its_own_csv(module, tmp_path):
    path = tmp_path / "daily.csv"
    payload = b"date,equity\n2022-03-15,123.00000000000001\n"
    path.write_bytes(payload)
    identity = {"sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload)}
    receipt = module.archive_csv(path, identity)
    assert not path.exists()
    archive = Path(receipt["archive"]["path"])
    assert gzip.decompress(archive.read_bytes()) == payload
    assert receipt["raw_sha256"] == identity["sha256"]


def test_archive_rejects_wrong_source_identity_without_deleting(module, tmp_path):
    path = tmp_path / "daily.csv"
    path.write_bytes(b"original")
    with pytest.raises(RuntimeError, match="archive_source_identity"):
        module.archive_csv(path, {"sha256": "0" * 64, "size": 8})
    assert path.read_bytes() == b"original"


def test_short_horizon_configuration_preserves_formal_identity(module):
    full = module.load_base().support().load_v1_runner()
    _, runner = module.configured()
    short = runner.load_v1_runner()
    assert str(short.END.date()) == "2022-03-15"
    assert str(full.END.date()) == "2026-08-28"
    assert short.START == full.START
    assert short._active_formal_identity() == full._active_formal_identity()
    assert len(runner.collect_input_files()) == 1516
