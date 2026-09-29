"""Add stock BB(20,2) and frozen entry-signal evidence to the canonical recap.

Preserves the v1 bundle and all strategy/futures resources. This is an offline
display build, not a strategy replay. The base renderer remains the single
source of truth for existing charts and controls.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import sys

import pandas as pd

TOOLS = Path(__file__).resolve().parent
BASE_PATH = TOOLS / "stage014_stock_recap_html.py"
BASE_SHA = "631c2f800a06fe17ba3f9973e48bd076680492fc3ff50b7506a23c0f4318cda6"
UI_PATH = TOOLS / "stage015_stock_bollinger_ui.js"
CALC_PATH = TOOLS / "stage015_stock_bollinger.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load_module(BASE_PATH, "stock_recap_base")
PARENT = base.OUTPUT
OUTPUT = base.LINE / "outputs/stage015_commit4ac255e_stock_recap_bollinger_v3"


def load_parent(parent: Path) -> tuple[dict, list, dict]:
    summary_path = parent / "summary.json"
    summary = base.read_json(summary_path)
    if summary.get("status") != "COMPLETE":
        raise ValueError("Parent recap must be COMPLETE")
    if summary.get("adapter_sha256") != BASE_SHA or base.sha256(BASE_PATH) != BASE_SHA:
        raise ValueError("Parent stock adapter changed; review before rebuilding")
    hashes = {**summary["input_sha256"], str(summary_path): base.sha256(summary_path), str(BASE_PATH): BASE_SHA}
    for name in ("index.html", "records.json", "chart_manifest.csv"):
        path = parent / name
        expected = summary["artifact_sha256"][name]
        if base.sha256(path) != expected:
            raise ValueError(f"Parent artifact hash mismatch: {name}")
        hashes[str(path)] = expected
    for name, digest in hashes.items():
        if base.sha256(Path(name)) != digest:
            raise ValueError(f"Frozen input hash mismatch: {name}")
    return summary, json.loads((parent / "records.json").read_text(encoding="utf-8")), hashes


def render_bollinger_html(records: list, summary: dict, renderer) -> str:
    page = base.render_stock_html(records, summary, renderer)
    anchor = '<div class="panel"><div id="chart">'
    if page.count(anchor) != 1 or page.count("</body>") != 1:
        raise ValueError("Canonical page extension hook changed")
    page = page.replace(anchor, '<div id="stockSignalInfo" class="stock-signal-info" aria-live="polite"></div>' + anchor, 1)
    css = """<style>
.stock-signal-info{margin:0 0 10px;padding:10px 12px;border:1px solid #ddd6e4;background:#fff;border-radius:8px;display:flex;gap:9px;align-items:center;flex-wrap:wrap;font-size:13px}
.stock-condition{padding:4px 8px;border-radius:5px}.stock-condition.hit{background:#ecfdf3;color:#067647}.stock-condition.miss{background:#f2f4f7;color:#667085}
.stock-signal-note{flex-basis:100%;color:#667085;font-size:12px}.stock-bb-toggle{border-color:#e5b1d4;color:#a31567}
</style>"""
    if page.count("</head>") != 1:
        raise ValueError("Canonical document head hook changed")
    page = page.replace("</head>", '<link rel="icon" href="data:,">' + css + "</head>", 1)
    extension = UI_PATH.read_text(encoding="utf-8")
    return page.replace("</body>", f"<script>{extension}\ninstallStockBollinger();</script></body>", 1)


def generate(output: Path = OUTPUT) -> dict:
    output = base.validate_output_path(output)
    parent_summary, parent_records, hashes = load_parent(PARENT)
    source = base.verify_bundle(base.RUN, base.PANEL)
    if parent_summary["frozen_metrics"] != source["summary"] or parent_summary["source_run_id"] != source["manifest"]["run_id"]:
        raise ValueError("Parent recap is not bound to this frozen run")
    for path, digest in source["input_sha256"].items():
        if hashes.get(path) != digest:
            raise ValueError(f"Parent recap uses different input: {path}")
    signals_path = base.RUN / "signals.csv"
    for path in (signals_path, CALC_PATH, UI_PATH, Path(__file__)):
        hashes[str(path)] = base.sha256(path)
    calculator = load_module(CALC_PATH, "stock_bollinger_data")
    records, audit = calculator.enrich_records(parent_records, pd.read_parquet(base.PANEL),
                                               pd.read_csv(signals_path), source["manifest"]["signal_settings"])
    if len(records) != len(parent_records) or len(records) != len(source["episodes"]):
        raise ValueError("Bollinger enhancement changed episode count")
    for old, new in zip(parent_records, records):
        for period, payload in old.items():
            if any(new[period][key] != value for key, value in payload.items()):
                raise ValueError(f"Bollinger enhancement changed existing {period} data")
    summary = deepcopy(parent_summary)
    summary.pop("artifact_sha256", None)
    summary.update(page_title="QMT357 · commit4ac255e 股票逐笔复盘 · 布林信号版｜2020—2026-09-28",
                   source_warning="收盘信号→次日开盘，不是QMT14:50回放。日K布林按策略复权口径计算并换算到各日原价尺度；K线与实际成交价仍未复权。净盈亏含分红并扣费；原价涨跌不是账户收益。",
                   coverage_note="全部226笔闭合交易：39笔布林条件成立，187笔由RSI+MACD触发。布林BB(20,2)只叠加日K，青色菱形为信号日而非买入日。15分钟无数据。",
                   parent_recap=str(PARENT), parent_adapter_sha256=BASE_SHA,
                   adapter_sha256=base.sha256(Path(__file__)), input_sha256=hashes,
                   indicator_audit=audit, bollinger={"period": 20, "std_multiplier": 2, "ddof": 1,
                                                     "period_scope": "daily_only", "default_visible": True,
                                                     "price_basis": "asof_each_day_raw_equivalent"},
                   created_at=datetime.now().astimezone().isoformat())
    renderer = base.load_renderer()
    page = render_bollinger_html(records, summary, renderer)
    chart_manifest = pd.read_csv(PARENT / "chart_manifest.csv")
    for i, record in enumerate(records):
        signal = record["meta"]["entry_signal"]
        if chart_manifest.loc[i, "open_trade_id"] != record["meta"]["open_trade_id"]:
            raise ValueError("Parent chart manifest episode order changed")
        for key, value in signal.items():
            chart_manifest.loc[i, f"signal_{key}"] = value
    for path, digest in hashes.items():
        if base.sha256(Path(path)) != digest:
            raise ValueError(f"Input changed during display build: {path}")
    output.mkdir(parents=True, exist_ok=False)
    (output / "index.html").write_text(page, encoding="utf-8")
    (output / "records.json").write_text(json.dumps(renderer._json_safe(records), ensure_ascii=False, allow_nan=False), encoding="utf-8")
    (output / "indicator_audit.json").write_text(json.dumps(renderer._json_safe(audit), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    chart_manifest.to_csv(output / "chart_manifest.csv", index=False, encoding="utf-8-sig")
    summary["artifact_sha256"] = {name: base.sha256(output / name) for name in
                                  ("index.html", "records.json", "chart_manifest.csv", "indicator_audit.json")}
    (output / "summary.json").write_text(json.dumps(renderer._json_safe(summary), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = generate(args.output)
    forbidden = [name for name in sys.modules if name.startswith(("vnpy", "tqsdk", "qmt_roll", "analyze_qmt"))]
    if forbidden:
        raise RuntimeError(f"Unexpected trading imports: {forbidden}")
    print(json.dumps({"output": str(args.output), "episodes": result["completed_episodes"],
                      "indicator_audit": result["indicator_audit"], "futures_imports": forbidden}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
