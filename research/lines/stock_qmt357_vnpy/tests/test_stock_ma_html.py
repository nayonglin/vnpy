"""MA visibility changes only presentation, not frozen prices or other overlays."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

LINE = Path(__file__).resolve().parents[1]
MODULE = LINE / "tools/stage016_stock_ma_html.py"
UI = LINE / "tools/stage016_stock_ma_ui.js"
BASE = LINE / "tools/stage015_stock_bollinger_html.py"


@pytest.fixture
def adapter():
    class Lazy:
        def __getattr__(self, name):
            assert MODULE.exists(), "MA display adapter is not implemented"
            spec = importlib.util.spec_from_file_location("ma_html", MODULE)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return getattr(module, name)
    return Lazy()


def apply_visibility(traces, settings):
    assert UI.exists(), "MA display toggle is not implemented"
    script = """const fs=require('fs'),vm=require('vm'),s={};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),s);
const input=JSON.parse(process.argv[2]);let result=input;
for(const enabled of JSON.parse(process.argv[3]))result=s.stockMovingAverageVisibility(result,enabled);
console.log(JSON.stringify({input,result}));"""
    proc = subprocess.run(["node", "-e", script, str(UI), json.dumps(traces), json.dumps(settings)],
                          capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


@pytest.mark.parametrize("period", ["日K", "周K", "月K", "30日K", "10日K", "15分钟K"])
def test_off_hides_all_four_ma_lines_without_mutating_data(period):
    traces = [{"type": "scatter", "mode": "lines", "legendgroup": f"ma{n}",
               "name": f"{period} MA{n}", "x": [1, 2], "y": [None, 12.3]}
              for n in [5, 10, 20, 40]]
    actual = apply_visibility(traces, [False])
    assert actual["input"] == traces
    assert actual["result"] == [dict(t, visible=False) for t in traces]


def test_off_does_not_hide_bollinger_candles_volume_or_signal_and_fill_markers():
    traces = [
        {"type": "scatter", "mode": "lines", "legendgroup": "stock-bollinger", "name": "BB20 中轨", "y": [12]},
        {"type": "candlestick", "open": [10], "close": [12]},
        {"type": "bar", "name": "日成交量", "y": [100]},
        {"type": "scatter", "mode": "markers", "name": "信号日收盘", "y": [11]},
        {"type": "scatter", "mode": "markers", "name": "同源成交价格", "y": [12, 13]},
        {"type": "scatter", "mode": "lines", "legendgroup": "other", "visible": "legendonly"},
    ]
    assert apply_visibility(traces, [False])["result"] == traces


def test_on_restores_all_ma_after_global_off_or_individual_legend_hide():
    traces = [{"type": "scatter", "mode": "lines", "legendgroup": "ma20", "visible": "legendonly", "y": [12]}]
    assert apply_visibility(traces, [False, True])["result"] == [dict(traces[0], visible=True)]


def parent_fixture(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("frozen")
    parent = tmp_path / "parent"
    parent.mkdir()
    content = {"records.json": '[{"meta":{"open_trade_id":"stock-0001"}}]',
               "index.html": "<html></html>", "chart_manifest.csv": "open_trade_id\nstock-0001\n",
               "indicator_audit.json": '{"entries_checked":1}'}
    for name, data in content.items():
        (parent / name).write_text(data)
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    summary = {"status": "COMPLETE", "completed_episodes": 1, "adapter_sha256": digest(BASE),
               "frozen_metrics": {"closed_round_trips": 1},
               "input_sha256": {str(source): digest(source), str(BASE): digest(BASE)},
               "artifact_sha256": {name: digest(parent / name) for name in content}}
    (parent / "summary.json").write_text(json.dumps(summary))
    return parent, source, summary


def test_load_parent_preserves_records_and_checks_every_input_and_artifact(adapter, tmp_path):
    parent, source, before = parent_fixture(tmp_path)
    summary, records, hashes = adapter.load_parent(parent)
    assert summary == before
    assert records == [{"meta": {"open_trade_id": "stock-0001"}}]
    assert all(str(parent / name) in hashes for name in before["artifact_sha256"])
    assert str(parent / "summary.json") in hashes
    assert source.read_text() == "frozen"


@pytest.mark.parametrize("mutation", ["incomplete", "source_tamper", "artifact_tamper", "adapter_tamper",
                                     "missing_artifact_hash", "wrong_episode_count"])
def test_load_parent_fails_closed_on_unverified_evidence(adapter, tmp_path, mutation):
    parent, source, summary = parent_fixture(tmp_path)
    if mutation == "incomplete":
        summary["status"] = "RUNNING"
    elif mutation == "source_tamper":
        source.write_text("changed")
    elif mutation == "artifact_tamper":
        (parent / "indicator_audit.json").write_text("{}")
    elif mutation == "adapter_tamper":
        summary["adapter_sha256"] = "wrong"
    elif mutation == "missing_artifact_hash":
        del summary["artifact_sha256"]["records.json"]
    else:
        summary["completed_episodes"] = 2
    (parent / "summary.json").write_text(json.dumps(summary))
    with pytest.raises(ValueError):
        adapter.load_parent(parent)
