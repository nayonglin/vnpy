"""Bollinger presentation behavior; no strategy/backtest invocation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

LINE = Path(__file__).resolve().parents[1]
MODULE = LINE / "tools/stage015_stock_bollinger_html.py"
UI = LINE / "tools/stage015_stock_bollinger_ui.js"


@pytest.fixture
def adapter():
    class Lazy:
        def __getattr__(self, name):
            assert MODULE.exists(), "Bollinger HTML adapter is not implemented"
            spec = importlib.util.spec_from_file_location("bb_html", MODULE)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return getattr(module, name)
    return Lazy()


def record():
    return {"daily": {"x": [1.5, 2.5], "date": ["2020-01-02", "2020-01-03"],
                      "bb_middle": [10., 11.], "bb_upper": [12., 13.], "bb_lower": [8., 9.]},
            "meta": {"entry_date": "2020-01-03", "entry_signal": {
                "date": "2020-01-02", "x": 1.5, "raw_close": 10.2,
                "bollinger": False, "rsi": True, "macd": True, "condition_count": 2}}}


def js_traces(rec, period="daily", enabled=True):
    assert UI.exists(), "Bollinger UI extension is not implemented"
    script = """const fs=require('fs'),vm=require('vm');const sandbox={};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),sandbox);
const traces=sandbox.stockBollingerTraces(JSON.parse(process.argv[2]),{id:process.argv[3]},1,process.argv[4]==='true');
console.log(JSON.stringify(traces));"""
    proc = subprocess.run(["node", "-e", script, str(UI), json.dumps(rec), period,
                           str(enabled).lower()], check=True, capture_output=True, text=True)
    return json.loads(proc.stdout)


def test_daily_bollinger_traces_include_band_shade_and_distinct_signal_marker():
    traces = js_traces(record())
    assert len(traces) == 4
    assert traces[0]["y"] == [8., 9.]
    assert traces[1]["y"] == [12., 13.]
    assert traces[1]["fill"] == "tonexty"
    assert traces[2]["y"] == [10., 11.]
    assert traces[2]["line"]["width"] > traces[0]["line"]["width"]
    assert traces[3]["x"] == [1.5]  # Signal bar, not next-open entry at x=2.5.
    assert traces[3]["y"] == [10.2]
    assert traces[3]["marker"]["symbol"] == "diamond"
    assert all(t["xaxis"] == "x2" and t["yaxis"] == "y3" for t in traces)


def test_bollinger_toggle_keeps_signal_marker_but_hides_bands():
    traces = js_traces(record(), enabled=False)
    assert len(traces) == 1
    assert traces[0]["name"] == "信号日收盘"


@pytest.mark.parametrize("period", ["day30", "day10", "weekly", "monthly", "intraday"])
def test_non_daily_panels_never_claim_daily_bollinger(period):
    assert js_traces(record(), period=period) == []


def parent_fixture(tmp_path):
    source = tmp_path / "frozen_source.txt"
    source.write_text("immutable")
    parent = tmp_path / "parent"
    parent.mkdir()
    files = {"records.json": "[]", "chart_manifest.csv": "entry_date\n", "index.html": "<html></html>"}
    for name, content in files.items():
        (parent / name).write_text(content)
    summary = {"status": "COMPLETE", "adapter_sha256": "631c2f800a06fe17ba3f9973e48bd076680492fc3ff50b7506a23c0f4318cda6",
               "input_sha256": {str(source): hashlib.sha256(source.read_bytes()).hexdigest()},
               "artifact_sha256": {name: hashlib.sha256(content.encode()).hexdigest() for name, content in files.items()}}
    (parent / "summary.json").write_text(json.dumps(summary))
    return parent, source


def test_parent_bundle_is_read_only_and_hash_verified(adapter, tmp_path):
    parent, source = parent_fixture(tmp_path)
    summary, records, hashes = adapter.load_parent(parent)
    assert summary["status"] == "COMPLETE" and records == []
    assert str(parent / "summary.json") in hashes
    assert source.read_text() == "immutable"


@pytest.mark.parametrize("mutation", ["incomplete", "source_tamper", "artifact_tamper", "adapter_tamper"])
def test_parent_incomplete_or_tampered_evidence_is_rejected(adapter, tmp_path, mutation):
    parent, source = parent_fixture(tmp_path)
    summary = json.loads((parent / "summary.json").read_text())
    if mutation == "incomplete":
        summary["status"] = "RUNNING"
    elif mutation == "adapter_tamper":
        summary["adapter_sha256"] = "wrong"
    elif mutation == "source_tamper":
        source.write_text("changed")
    else:
        (parent / "records.json").write_text("[{}]")
    (parent / "summary.json").write_text(json.dumps(summary))
    with pytest.raises(ValueError):
        adapter.load_parent(parent)
