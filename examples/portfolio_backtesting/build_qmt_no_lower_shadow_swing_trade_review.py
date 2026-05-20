from __future__ import annotations

import html
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from run_qmt_no_lower_shadow_swing_backtest import DEFAULT_OUTPUT_PREFIX, OUTPUT_DIR, _load_bar_cache


TRADES_PATH = OUTPUT_DIR / f"{DEFAULT_OUTPUT_PREFIX}_trades.csv"
CANDIDATES_PATH = OUTPUT_DIR / f"{DEFAULT_OUTPUT_PREFIX}_candidates.csv"
ROUNDTRIPS_PATH = OUTPUT_DIR / f"{DEFAULT_OUTPUT_PREFIX}_roundtrips.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{DEFAULT_OUTPUT_PREFIX}_positions.csv"
DAILY_PATH = OUTPUT_DIR / f"{DEFAULT_OUTPUT_PREFIX}_daily.csv"
REVIEW_PATH = OUTPUT_DIR / f"{DEFAULT_OUTPUT_PREFIX}_trade_review.html"

LOOKBACK_BARS = 20
LOOKAHEAD_BARS = 20


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def _date(value: Any) -> pd.Timestamp:
    return pd.Timestamp(value).tz_localize(None).normalize()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result):
        return default
    return float(result)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _money(value: float) -> str:
    return f"{value:,.0f}"


def _load_sources() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    trades = _read_csv(TRADES_PATH)
    candidates = _read_csv(CANDIDATES_PATH)
    roundtrips = _read_csv(ROUNDTRIPS_PATH)
    positions = _read_csv(POSITIONS_PATH)
    daily = _read_csv(DAILY_PATH)

    for frame, columns in [
        (trades, ["datetime", "date"]),
        (candidates, ["date", "signal_date_1", "signal_date_2"]),
        (roundtrips, ["entry_date", "exit_date"]),
        (positions, ["date", "entry_date"]),
        (daily, ["date"]),
    ]:
        for column in columns:
            if column in frame.columns:
                frame[column] = pd.to_datetime(frame[column]).dt.tz_localize(None).dt.normalize()

    trades.sort_values(["datetime", "product_vt_symbol", "trade_index"], inplace=True)
    candidates.sort_values(["date", "product_vt_symbol", "candidate_index"], inplace=True)
    roundtrips.sort_values(["entry_date", "product_vt_symbol", "contract_vt_symbol"], inplace=True)
    positions.sort_values(["date", "product_vt_symbol", "contract_vt_symbol"], inplace=True)
    daily.sort_values("date", inplace=True)
    return trades, candidates, roundtrips, positions, daily


def _bar_list(cache: dict[str, dict[pd.Timestamp, Any]], contract: str) -> list[Any]:
    return [cache[contract][date] for date in sorted(cache.get(contract, {}))]


def _find_bar_index(bars: list[Any], target_date: pd.Timestamp) -> int:
    dates = [bar.date for bar in bars]
    if target_date in dates:
        return dates.index(target_date)
    insertion = 0
    for index, date in enumerate(dates):
        if date > target_date:
            break
        insertion = index
    return max(0, min(insertion, len(bars) - 1))


def _window_bars(bars: list[Any], center_date: pd.Timestamp) -> list[Any]:
    center = _find_bar_index(bars, center_date)
    left = max(0, center - LOOKBACK_BARS)
    right = min(len(bars), center + LOOKAHEAD_BARS + 1)
    return bars[left:right]


def _build_stop_line(
    window: list[Any],
    *,
    entry_date: pd.Timestamp,
    exit_date: pd.Timestamp,
    initial_stop: float,
) -> list[float | None]:
    line: list[float | None] = []
    trailing_stop = float(initial_stop)
    prior_low: float | None = None
    for bar in window:
        if bar.date < entry_date or bar.date > exit_date:
            line.append(None)
            prior_low = float(bar.low)
            continue
        if bar.date > entry_date and prior_low is not None:
            trailing_stop = max(trailing_stop, prior_low)
        line.append(round(trailing_stop, 4))
        prior_low = float(bar.low)
    return line


def _trade_markers(window_trades: pd.DataFrame, selected_trade_indexes: set[int]) -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = []
    for trade in window_trades.to_dict("records"):
        is_open = str(trade["offset"]) == "Open"
        is_selected = int(trade["trade_index"]) in selected_trade_indexes
        if is_open:
            symbol = "triangle-up"
            color = "#166534" if is_selected else "#16a34a"
        else:
            symbol = "x"
            reason = str(trade.get("reason") or "")
            color = "#b91c1c" if "stop" in reason else "#2563eb"
        markers.append(
            {
                "x": _date(trade["date"]).strftime("%Y-%m-%d"),
                "y": _safe_float(trade["price"]),
                "symbol": symbol,
                "color": color,
                "size": 15 if is_selected else 10,
                "text": (
                    f"#{int(trade['trade_index'])}<br>"
                    f"{trade['direction']} {trade['offset']}<br>"
                    f"{trade['reason']}<br>"
                    f"价格: {_safe_float(trade['price']):,.2f}<br>"
                    f"手数: {_safe_float(trade['volume']):,.0f}<br>"
                    f"净盈亏: {_safe_float(trade.get('net_pnl')):,.0f}"
                ),
            }
        )
    return markers


def _candidate_marker(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "x": _date(candidate["signal_date_1"]).strftime("%Y-%m-%d"),
            "text": "信号1: open==low 且 close>open",
            "color": "#f59e0b",
        },
        {
            "x": _date(candidate["signal_date_2"]).strftime("%Y-%m-%d"),
            "text": "信号2: open==low 且 close>open",
            "color": "#d97706",
        },
    ]


def _build_records(
    candidates: pd.DataFrame,
    trades: pd.DataFrame,
    roundtrips: pd.DataFrame,
    positions: pd.DataFrame,
) -> list[dict[str, Any]]:
    opened = candidates[candidates["candidate_status"].astype(str).eq("opened")].copy()
    contracts = sorted(set(opened["entry_contract_vt_symbol"].dropna().astype(str)))
    if not contracts:
        return []
    start = opened["signal_date_1"].min() - pd.Timedelta(days=90)
    end = roundtrips["exit_date"].max() + pd.Timedelta(days=90)
    cache = _load_bar_cache(contracts, start=start.to_pydatetime(), end=end.to_pydatetime())

    records: list[dict[str, Any]] = []
    for display_index, candidate in enumerate(opened.to_dict("records"), start=1):
        contract = str(candidate["entry_contract_vt_symbol"])
        bars = _bar_list(cache, contract)
        if not bars:
            continue
        entry_date = _date(candidate["date"])
        signal_date_1 = _date(candidate["signal_date_1"])
        signal_date_2 = _date(candidate["signal_date_2"])
        roundtrip_match = roundtrips[
            (roundtrips["product_vt_symbol"].astype(str) == str(candidate["product_vt_symbol"]))
            & (roundtrips["contract_vt_symbol"].astype(str) == contract)
            & (roundtrips["entry_date"] == entry_date)
        ]
        if roundtrip_match.empty:
            continue
        roundtrip = roundtrip_match.iloc[0].to_dict()
        exit_date = _date(roundtrip["exit_date"])
        center_date = exit_date if exit_date > entry_date else entry_date
        window = _window_bars(bars, center_date)
        window_start = window[0].date
        window_end = window[-1].date
        window_trades = trades[
            (trades["vt_symbol"].astype(str) == contract)
            & (trades["date"] >= window_start)
            & (trades["date"] <= window_end)
        ].copy()
        selected_trade_indexes = set(
            int(value)
            for value in window_trades[
                (window_trades["date"] >= entry_date)
                & (window_trades["date"] <= exit_date)
                & (window_trades["product_vt_symbol"].astype(str) == str(candidate["product_vt_symbol"]))
            ]["trade_index"].tolist()
        )
        position_trace = positions[
            (positions["contract_vt_symbol"].astype(str) == contract)
            & (positions["entry_date"] == entry_date)
            & (positions["date"] >= window_start)
            & (positions["date"] <= window_end)
        ].copy()

        bar_dates = [bar.date.strftime("%Y-%m-%d") for bar in window]
        stop_line = _build_stop_line(
            window,
            entry_date=entry_date,
            exit_date=exit_date,
            initial_stop=_safe_float(candidate["stop_price"]),
        )
        position_by_date = {
            _date(row["date"]).strftime("%Y-%m-%d"): {
                "volume": _safe_float(row["volume"]),
                "stop_price": _safe_float(row["stop_price"]),
                "unrealized_pnl": _safe_float(row["unrealized_pnl"]),
                "close_price": _safe_float(row["close_price"]),
            }
            for row in position_trace.to_dict("records")
        }
        position_line = [position_by_date.get(date, {}).get("stop_price") for date in bar_dates]

        records.append(
            {
                "record_index": display_index,
                "label": (
                    f"{display_index}. {entry_date.strftime('%Y-%m-%d')} | {contract} | "
                    f"vol {int(candidate['selected_volume'])} | {roundtrip['exit_reason']} | "
                    f"pnl {_money(_safe_float(roundtrip['net_pnl']))}"
                ),
                "candidate": {
                    "candidate_index": _safe_int(candidate["candidate_index"]),
                    "product_vt_symbol": str(candidate["product_vt_symbol"]),
                    "contract_vt_symbol": contract,
                    "entry_date": entry_date.strftime("%Y-%m-%d"),
                    "signal_date_1": signal_date_1.strftime("%Y-%m-%d"),
                    "signal_date_2": signal_date_2.strftime("%Y-%m-%d"),
                    "entry_price": _safe_float(candidate["entry_price"]),
                    "stop_price": _safe_float(candidate["stop_price"]),
                    "stop_distance": _safe_float(candidate["stop_distance"]),
                    "risk_amount": _safe_float(candidate["risk_amount"]),
                    "risk_per_contract": _safe_float(candidate["risk_per_contract"]),
                    "contracts_by_risk": _safe_int(candidate["contracts_by_risk"]),
                    "contracts_by_margin": _safe_int(candidate["contracts_by_margin"]),
                    "contracts_by_single_trade_cap": _safe_int(candidate["contracts_by_single_trade_cap"]),
                    "selected_volume": _safe_int(candidate["selected_volume"]),
                    "planned_half_exit_volume": _safe_int(candidate["planned_half_exit_volume"]),
                    "active_positions_before": _safe_int(candidate["active_positions_before"]),
                },
                "roundtrip": {
                    "exit_date": exit_date.strftime("%Y-%m-%d"),
                    "exit_reason": str(roundtrip["exit_reason"]),
                    "original_volume": _safe_int(roundtrip["original_volume"]),
                    "entry_price": _safe_float(roundtrip["entry_price"]),
                    "final_stop_price": _safe_float(roundtrip["final_stop_price"]),
                    "net_pnl": _safe_float(roundtrip["net_pnl"]),
                    "slippage": _safe_float(roundtrip["slippage"]),
                    "holding_days": _safe_int(roundtrip["holding_days"]),
                },
                "bars": {
                    "date": bar_dates,
                    "open": [round(float(bar.open), 4) for bar in window],
                    "high": [round(float(bar.high), 4) for bar in window],
                    "low": [round(float(bar.low), 4) for bar in window],
                    "close": [round(float(bar.close), 4) for bar in window],
                    "volume": [round(float(bar.volume), 4) for bar in window],
                },
                "signal_markers": _candidate_marker(candidate),
                "trade_markers": _trade_markers(window_trades, selected_trade_indexes),
                "initial_stop_line": [round(_safe_float(candidate["stop_price"]), 4)] * len(window),
                "trailing_stop_line": stop_line,
                "recorded_position_stop_line": position_line,
                "position_by_date": position_by_date,
            }
        )
    return records


def _summary_payload(
    candidates: pd.DataFrame,
    trades: pd.DataFrame,
    roundtrips: pd.DataFrame,
    daily: pd.DataFrame,
) -> dict[str, Any]:
    candidate_status = candidates["candidate_status"].fillna("").astype(str)
    skip_reason = candidates["skip_reason"].fillna("").astype(str)
    opened_count = int(candidate_status.eq("opened").sum())
    skipped_count = int(candidate_status.eq("skipped").sum())
    skip_summary = (
        candidates[candidate_status.eq("skipped")]
        .assign(skip_reason=skip_reason[candidate_status.eq("skipped")])
        .groupby("skip_reason")
        .size()
        .sort_values(ascending=False)
        .to_dict()
    )
    exit_summary = (
        roundtrips.groupby("exit_reason")
        .agg(count=("net_pnl", "size"), net_pnl=("net_pnl", "sum"))
        .reset_index()
        .sort_values("net_pnl")
        .to_dict("records")
    )
    equity_column = "equity" if "equity" in daily.columns else "balance"
    end_equity = _safe_float(daily[equity_column].iloc[-1]) if equity_column in daily.columns and not daily.empty else 0.0
    return {
        "candidate_count": int(len(candidates)),
        "opened_count": opened_count,
        "skipped_count": skipped_count,
        "trade_count": int(len(trades)),
        "roundtrip_count": int(len(roundtrips)),
        "position_snapshot_count": int(_read_csv(POSITIONS_PATH).shape[0]),
        "start_date": _date(daily["date"].min()).strftime("%Y-%m-%d") if not daily.empty else "",
        "end_date": _date(daily["date"].max()).strftime("%Y-%m-%d") if not daily.empty else "",
        "end_equity": end_equity,
        "total_return_pct": (end_equity / 500_000.0 - 1.0) * 100.0 if end_equity else 0.0,
        "skip_summary": {str(key): int(value) for key, value in skip_summary.items()},
        "exit_summary": [
            {
                "exit_reason": str(row["exit_reason"]),
                "count": int(row["count"]),
                "net_pnl": float(row["net_pnl"]),
            }
            for row in exit_summary
        ],
    }


def _html_template(records: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    records_json = json.dumps(records, ensure_ascii=False).replace("</", "<\\/")
    summary_json = json.dumps(summary, ensure_ascii=False).replace("</", "<\\/")
    title = "期货无下影线波段 v1 - 交易复盘"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(title)}</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    :root {{
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #1f2933;
      --muted: #667085;
      --line: #d9dee7;
      --red: #c2410c;
      --green: #047857;
      --blue: #2563eb;
    }}
    body {{ margin: 0; background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .page {{ max-width: 1540px; margin: 0 auto; padding: 18px; }}
    h1 {{ margin: 0 0 12px; font-size: 24px; line-height: 1.25; }}
    .summary {{ display: grid; grid-template-columns: repeat(6, minmax(140px, 1fr)); gap: 10px; margin-bottom: 12px; }}
    .metric {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; }}
    .metric .label {{ font-size: 12px; color: var(--muted); }}
    .metric .value {{ margin-top: 4px; font-size: 19px; font-weight: 700; }}
    .toolbar {{ display: grid; grid-template-columns: 220px 220px 1fr auto auto; gap: 10px; align-items: center; margin-bottom: 12px; }}
    select, input, button {{ height: 38px; border: 1px solid var(--line); border-radius: 7px; padding: 0 10px; background: #fff; font-size: 13px; color: var(--text); }}
    button {{ cursor: pointer; }}
    .layout {{ display: grid; grid-template-columns: minmax(0, 1fr) 380px; gap: 12px; align-items: start; }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; }}
    #chart {{ min-height: 660px; padding: 8px; }}
    .side {{ display: grid; gap: 12px; }}
    .card {{ padding: 12px; }}
    .card h2 {{ margin: 0 0 8px; font-size: 15px; }}
    .kv {{ display: grid; grid-template-columns: 128px 1fr; gap: 6px 8px; font-size: 13px; }}
    .kv div:nth-child(odd) {{ color: var(--muted); }}
    .tables {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 6px 8px; text-align: left; white-space: nowrap; }}
    th {{ color: var(--muted); background: #fafafa; }}
    .footer {{ margin-top: 10px; color: var(--muted); font-size: 12px; }}
    @media (max-width: 1180px) {{
      .summary {{ grid-template-columns: repeat(2, 1fr); }}
      .toolbar {{ grid-template-columns: 1fr; }}
      .layout {{ grid-template-columns: 1fr; }}
      .tables {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <h1>{html.escape(title)}</h1>
    <div id="summary" class="summary"></div>
    <div class="toolbar">
      <select id="product-filter"></select>
      <select id="reason-filter"></select>
      <select id="record-select"></select>
      <button id="prev-btn">上一笔</button>
      <button id="next-btn">下一笔</button>
    </div>
    <div class="layout">
      <div id="chart" class="panel"></div>
      <div class="side">
        <div class="panel card"><h2>候选与开仓</h2><div id="candidate-kv" class="kv"></div></div>
        <div class="panel card"><h2>出场与盈亏</h2><div id="roundtrip-kv" class="kv"></div></div>
        <div class="panel card"><h2>窗口说明</h2><div id="window-kv" class="kv"></div></div>
      </div>
    </div>
    <div class="tables">
      <div class="panel card"><h2>跳过原因</h2><div id="skip-table"></div></div>
      <div class="panel card"><h2>退出原因</h2><div id="exit-table"></div></div>
    </div>
    <div class="footer">每笔记录围绕入场/出场截取前后日线；橙色竖线为两根信号K，绿色三角为开仓，叉号为平仓，橙色虚线为初始止损，酒红虚线为回放得到的移动止损。</div>
  </div>
  <script>
    const records = {records_json};
    const summary = {summary_json};
    const productFilter = document.getElementById("product-filter");
    const reasonFilter = document.getElementById("reason-filter");
    const recordSelect = document.getElementById("record-select");
    const prevBtn = document.getElementById("prev-btn");
    const nextBtn = document.getElementById("next-btn");
    let filtered = [];
    let active = 0;

    function fmt(value, digits = 2) {{
      if (value === null || value === undefined || value === "") return "-";
      return Number(value).toLocaleString("zh-CN", {{ maximumFractionDigits: digits, minimumFractionDigits: digits }});
    }}
    function pct(value) {{ return `${{fmt(value, 2)}}%`; }}
    function kv(items) {{ return items.map(([k, v]) => `<div>${{k}}</div><div>${{v ?? "-"}}</div>`).join(""); }}
    function table(rows, columns) {{
      if (!rows.length) return "<div>-</div>";
      return `<table><thead><tr>${{columns.map(c => `<th>${{c[0]}}</th>`).join("")}}</tr></thead><tbody>` +
        rows.map(row => `<tr>${{columns.map(c => `<td>${{c[1](row)}}</td>`).join("")}}</tr>`).join("") +
        "</tbody></table>";
    }}
    function renderSummary() {{
      const metrics = [
        ["候选", summary.candidate_count],
        ["实际开仓", summary.opened_count],
        ["跳过", summary.skipped_count],
        ["成交行", summary.trade_count],
        ["完整回合", summary.roundtrip_count],
        ["期末收益", pct(summary.total_return_pct)],
      ];
      document.getElementById("summary").innerHTML = metrics.map(([label, value]) =>
        `<div class="metric"><div class="label">${{label}}</div><div class="value">${{value}}</div></div>`
      ).join("");
      const skipRows = Object.entries(summary.skip_summary).map(([reason, count]) => ({{ reason, count }}));
      document.getElementById("skip-table").innerHTML = table(skipRows, [
        ["原因", r => r.reason],
        ["数量", r => r.count],
      ]);
      document.getElementById("exit-table").innerHTML = table(summary.exit_summary, [
        ["原因", r => r.exit_reason],
        ["笔数", r => r.count],
        ["净盈亏", r => fmt(r.net_pnl, 0)],
      ]);
    }}
    function initFilters() {{
      const products = ["全部品种", ...new Set(records.map(r => r.candidate.product_vt_symbol))].sort();
      const reasons = ["全部退出", ...new Set(records.map(r => r.roundtrip.exit_reason))].sort();
      productFilter.innerHTML = products.map(v => `<option value="${{v}}">${{v}}</option>`).join("");
      reasonFilter.innerHTML = reasons.map(v => `<option value="${{v}}">${{v}}</option>`).join("");
      productFilter.addEventListener("change", refreshRecords);
      reasonFilter.addEventListener("change", refreshRecords);
      recordSelect.addEventListener("change", () => {{ active = Number(recordSelect.value); renderRecord(); }});
      prevBtn.addEventListener("click", () => {{ active = Math.max(0, active - 1); renderRecord(); }});
      nextBtn.addEventListener("click", () => {{ active = Math.min(filtered.length - 1, active + 1); renderRecord(); }});
      refreshRecords();
    }}
    function refreshRecords() {{
      const product = productFilter.value;
      const reason = reasonFilter.value;
      filtered = records
        .map((record, index) => ({{ record, index }}))
        .filter(item => product === "全部品种" || item.record.candidate.product_vt_symbol === product)
        .filter(item => reason === "全部退出" || item.record.roundtrip.exit_reason === reason)
        .map(item => item.index);
      recordSelect.innerHTML = filtered.map((recordIndex, idx) => `<option value="${{idx}}">${{records[recordIndex].label}}</option>`).join("");
      active = 0;
      renderRecord();
    }}
    function renderRecord() {{
      if (!filtered.length) {{
        Plotly.newPlot("chart", [], {{ title: "无记录" }}, {{ responsive: true, displaylogo: false }});
        return;
      }}
      recordSelect.value = String(active);
      const record = records[filtered[active]];
      document.getElementById("candidate-kv").innerHTML = kv([
        ["候选编号", record.candidate.candidate_index],
        ["品种/合约", `${{record.candidate.product_vt_symbol}} / ${{record.candidate.contract_vt_symbol}}`],
        ["信号日", `${{record.candidate.signal_date_1}} / ${{record.candidate.signal_date_2}}`],
        ["入场日", record.candidate.entry_date],
        ["入场/止损", `${{fmt(record.candidate.entry_price)}} / ${{fmt(record.candidate.stop_price)}}`],
        ["止损距离", fmt(record.candidate.stop_distance)],
        ["风险预算", fmt(record.candidate.risk_amount)],
        ["单手风险", fmt(record.candidate.risk_per_contract)],
        ["风控/保证金/单笔上限", `${{record.candidate.contracts_by_risk}} / ${{record.candidate.contracts_by_margin}} / ${{record.candidate.contracts_by_single_trade_cap}}`],
        ["实际手数/半仓", `${{record.candidate.selected_volume}} / ${{record.candidate.planned_half_exit_volume}}`],
        ["开仓前持仓", record.candidate.active_positions_before],
      ]);
      document.getElementById("roundtrip-kv").innerHTML = kv([
        ["退出日", record.roundtrip.exit_date],
        ["退出原因", record.roundtrip.exit_reason],
        ["原始手数", record.roundtrip.original_volume],
        ["入场价", fmt(record.roundtrip.entry_price)],
        ["最终止损", fmt(record.roundtrip.final_stop_price)],
        ["持仓天数", record.roundtrip.holding_days],
        ["净盈亏", fmt(record.roundtrip.net_pnl, 0)],
        ["滑点", fmt(record.roundtrip.slippage, 0)],
      ]);
      document.getElementById("window-kv").innerHTML = kv([
        ["窗口", `${{record.bars.date[0]}} 到 ${{record.bars.date[record.bars.date.length - 1]}}`],
        ["当前筛选", `${{active + 1}} / ${{filtered.length}}`],
        ["全体记录", `${{record.record_index}} / ${{records.length}}`],
        ["窗口成交点", record.trade_markers.length],
        ["持仓快照天数", Object.keys(record.position_by_date).length],
      ]);
      renderChart(record);
    }}
    function renderChart(record) {{
      const traces = [
        {{
          type: "candlestick",
          x: record.bars.date,
          open: record.bars.open,
          high: record.bars.high,
          low: record.bars.low,
          close: record.bars.close,
          name: "日线",
          increasing: {{ line: {{ color: "#dc2626" }}, fillcolor: "#dc2626" }},
          decreasing: {{ line: {{ color: "#059669" }}, fillcolor: "#059669" }},
        }},
        {{
          type: "scatter",
          mode: "markers",
          x: record.trade_markers.map(m => m.x),
          y: record.trade_markers.map(m => m.y),
          text: record.trade_markers.map(m => m.text),
          hovertemplate: "%{{text}}<extra></extra>",
          marker: {{
            symbol: record.trade_markers.map(m => m.symbol),
            color: record.trade_markers.map(m => m.color),
            size: record.trade_markers.map(m => m.size),
            line: {{ width: 1, color: "#111827" }},
          }},
          name: "成交",
        }},
        {{
          type: "scatter",
          mode: "lines",
          x: record.bars.date,
          y: record.initial_stop_line,
          name: "初始止损",
          line: {{ color: "#f59e0b", width: 1.8, dash: "dash" }},
        }},
        {{
          type: "scatter",
          mode: "lines",
          x: record.bars.date,
          y: record.trailing_stop_line,
          name: "移动止损回放",
          line: {{ color: "#7f1d1d", width: 2.1, dash: "dash" }},
        }},
      ];
      if (record.recorded_position_stop_line.some(v => v !== null && v !== undefined)) {{
        traces.push({{
          type: "scatter",
          mode: "lines",
          x: record.bars.date,
          y: record.recorded_position_stop_line,
          name: "持仓快照止损",
          line: {{ color: "#2563eb", width: 1.4, dash: "dot" }},
        }});
      }}
      const shapes = record.signal_markers.map(marker => ({{
        type: "line",
        xref: "x",
        yref: "paper",
        x0: marker.x,
        x1: marker.x,
        y0: 0,
        y1: 1,
        line: {{ color: marker.color, width: 1.4, dash: "dot" }},
      }}));
      const annotations = record.signal_markers.map((marker, idx) => ({{
        x: marker.x,
        yref: "paper",
        y: 1,
        text: idx === 0 ? "信号1" : "信号2",
        showarrow: true,
        arrowhead: 2,
        ax: 0,
        ay: -28,
        font: {{ size: 11, color: marker.color }},
      }}));
      Plotly.newPlot("chart", traces, {{
        title: record.label,
        height: 660,
        margin: {{ l: 52, r: 24, t: 54, b: 42 }},
        xaxis: {{ rangeslider: {{ visible: false }}, type: "category" }},
        yaxis: {{ fixedrange: false }},
        shapes,
        annotations,
        legend: {{ orientation: "h", y: -0.08 }},
        hovermode: "x unified",
      }}, {{ responsive: true, displaylogo: false }});
    }}
    renderSummary();
    initFilters();
  </script>
</body>
</html>
"""


def main() -> None:
    trades, candidates, roundtrips, positions, daily = _load_sources()
    records = _build_records(candidates, trades, roundtrips, positions)
    if not records:
        raise RuntimeError("No opened records available for trade review.")
    summary = _summary_payload(candidates, trades, roundtrips, daily)
    REVIEW_PATH.write_text(_html_template(records, summary), encoding="utf-8")
    print(json.dumps({"records": len(records), "html": str(REVIEW_PATH.resolve()), "summary": summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
