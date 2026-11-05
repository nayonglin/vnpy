"""Render the frozen 2026 cold start of S21 gold touch stops."""
from dataclasses import dataclass, replace
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import stage005_trade_recap as recap
import stage054_s21_gold_touch_halfyear as touch
from stage024_pool44 import product_of

ROOT = recap.LINE / "outputs/stage054_s21_gold_touch_halfyear_20261104"
RUN = ROOT / "2026-01-01"
DESTINATION = recap.FORENSICS / "outputs/stage054_s21_gold_touch_2026_recap_v1"
SOURCE_SHA = "2ff506be26280e4861dcda2d11b3b9f3baa6687845bf55017488e29cb7d13b20"
AUDIT_SHA = "3a68924629ec7e8767c111603ecad5107ec19db659ddf1c1a2eb24f7acc76dc4"
START, END = "2026-01-05", "2026-11-04"
PROFILE = replace(recap.STAGE025_S44_2022, start=START, end=END)
STOP_LABELS = {touch.OPEN_GAP: "黄金开盘跳空止损", touch.INTRADAY: "黄金盘中触价止损"}
ORDER_LABELS = {"fixed_entry": "普通开仓", "reversal": "反手开仓", "roll": "换月开新"}


@dataclass(frozen=True)
class Bundle:
    inputs: dict
    metrics: dict
    closed: pd.DataFrame
    residual: pd.DataFrame
    fills: pd.DataFrame
    stops: pd.DataFrame
    rejected: pd.DataFrame
    signals: pd.DataFrame
    sizing: pd.DataFrame


def load_frozen(run):
    if run.resolve() != RUN:
        raise ValueError("expected the frozen Stage054 January 2026 run")
    touch.base.verify_manifest(ROOT, SOURCE_SHA)
    recap.verify(recap.LINE / "reviews/stage054_gold_touch_audit.json", AUDIT_SHA)
    receipt = touch.prior.read_json(ROOT / "receipt.json")
    inputs = touch.prior.read_json(run / "inputs.json")
    metrics = touch.prior.read_json(run / "summary.json")
    if (inputs["products"] != receipt["products"] or len(inputs["products"]) != 21
            or inputs["inputs_sha256"] != receipt["market_sha256"]
            or inputs["gold_stop_rule"] != touch.RULE or inputs["fixed_one_margin_gate"] != touch.parent.GATE
            or inputs["initial"] != 150000 or inputs["start"] != "2026-01-01"
            or (metrics["start"], metrics["end"]) != (START, END)):
        raise ValueError("Stage054 identity mismatch")
    daily = pd.read_csv(run / "daily.csv")
    cycles = pd.read_csv(run / "cycles.csv", keep_default_na=False)
    fills = pd.read_csv(run / "fills.csv", keep_default_na=False)
    fills.insert(0, "fill_id", fills.index + 1)
    closed, residual = recap.partition_cycles(cycles, PROFILE)
    stops = pd.read_csv(run / "gold_touch_stops.csv", keep_default_na=False).set_index("cycle")
    sizing = pd.read_csv(run / "risk_sizing.csv", keep_default_na=False)
    rejected = sizing.loc[sizing.status.eq("margin_below_one_lot")].copy()
    signals = pd.read_csv(run / "signals.csv", keep_default_na=False)
    if (daily.date.iloc[[0, -1]].tolist() != [START, END]
            or len(daily) != metrics["days"] or daily.equity.iat[-1] != metrics["equity"]
            or len(fills) != metrics["fills"] or len(closed) != metrics["closed_cycles"]
            or len(residual) != metrics["open_positions"] or not fills.volume.eq(1).all()
            or set(cycles.cycle) != set(fills.cycle)
            or abs(cycles.net_pnl.sum() - metrics["net_pnl"]) > 1e-7
            or abs(residual.net_pnl.sum() - metrics["terminal_open_net_pnl"]) > 1e-7):
        raise ValueError("trade, daily and terminal ledgers do not reconcile")
    return Bundle(inputs, metrics, closed, residual, fills, stops, rejected, signals, sizing)


def chart_market(inputs):
    b, p = touch.base, touch.prior
    ref = p.read_json(touch.parent.baseline.parent.S26 / "receipt.json")
    original = b.extend(b.load(b.MARKET, control=True), b.TAIL)
    expanded = b.load(b.MARKET, control=False)
    full = p.add_tail((ref["products"], *expanded[1:]), original, p.TAIL)
    if {str(path): sha for path, sha in full[-1].items()} != inputs["inputs_sha256"]:
        raise ValueError("admitted chart market differs from the backtest")
    products = set(inputs["products"])
    bars = pd.DataFrame([bar._asdict() for bar in full[5].values()])
    bars = bars.loc[product_of(bars.vt_symbol).isin(products)].copy()
    bars["date"] = pd.to_datetime(bars.date)
    mapping = pd.DataFrame([(day, product, symbol) for (day, product), symbol in full[6].items()
                            if product in products and symbol],
                           columns=["date", "continuous_symbol_vt", "main_contract_vt"])
    mapping["date"] = pd.to_datetime(mapping.date)
    mapping[["product", "exchange"]] = mapping.continuous_symbol_vt.str.split(".", n=1, expand=True)
    return bars, mapping


def chart_record(episode, episodes, index, legs, exact, calendar, cache, bundle, reversals):
    held = {}
    for opened, closed in recap.closed_segments(legs, legs[0].side):
        for day in calendar.date.loc[calendar.date.between(opened.date, closed.date)]:
            held[day] = opened.contract
    for f in legs:
        bar = exact.loc[f.epoch, pd.Timestamp(f.date)]
        if bar.vt_symbol != f.contract or (f.reason != touch.INTRADAY and bar.open != f.price):
            raise ValueError(f"physical bar or price mismatch for fill {f.fill_id}")
    # Daily chart visibility can start before the monthly window. Load the
    # extra hidden bars needed to warm up long trading-day averages there.
    warmup = recap.renderer.TRADING_DAY_MA_WARMUP_DAYS + recap.renderer.DAILY_PRE
    with patch.object(recap.renderer, "TRADING_DAY_MA_WARMUP_DAYS", warmup):
        daily, window = recap.renderer._context_daily(
            episode, calendar, cache, allow_daily_download=False, allow_noncritical_daily_gaps=True,
            recover_local_minutes=False, data_end=pd.Timestamp(END), held_contract_by_day=held,
        )
    key = episode.open_trade_id
    result, manifest = recap.renderer._records(
        episodes.iloc[index:index + 1], {key: daily}, {key: window}, pd.DataFrame(columns=["vt_symbol"]),
    )
    record = result[0]
    recap.annotate(record, legs, None, exact, PROFILE, None, reversals)
    first, last = legs[0], legs[-1]
    meta = record["meta"]
    signal = bundle.signals.loc[
        bundle.signals.date.eq(first.signal_day) & bundle.signals["product"].eq(first.product)
        & bundle.signals.epoch.eq(first.epoch) & bundle.signals.action.eq("open_long" if first.side == 1 else "open_short")
    ]
    if len(signal) != 1:
        raise ValueError(f"no unique opening signal for cycle {key}")
    signal = signal.iloc[0]
    funding = bundle.sizing.loc[bundle.sizing.date.eq(first.date) & bundle.sizing["product"].eq(first.product)
                              & bundle.sizing.executed_lots.eq(1) & bundle.sizing.kind.isin(("fixed_entry", "reversal"))]
    if len(funding) != 1:
        raise ValueError(f"no unique opening funding check for cycle {key}")
    funding = funding.iloc[0]
    reason = recap.REASONS[last.reason]
    note = (f"｜开仓依据 {first.signal_day}：近三周收盘 {float(signal.older_close):g} → "
            f"{float(signal.prior_close):g} → {float(signal.close):g}"
            f"｜开仓可用 {funding.free_cash:,.2f} 元，需 {funding.margin_per_lot + funding.entry_cost_per_lot:,.2f} 元"
            f"｜平仓原因：{reason}，触发记录日 {last.signal_day}，成交日 {last.date}")
    if last.reason == "roll_funding_exit":
        rejection = bundle.rejected.loc[bundle.rejected.date.eq(last.date) & bundle.rejected["product"].eq(last.product)
                                       & bundle.rejected.kind.eq("roll")].iloc[0]
        note += (f"｜先平旧仓，{rejection.contract} 开新需 "
                 f"{rejection.margin_per_lot + rejection.entry_cost_per_lot:,.2f} 元，"
                 f"可用 {rejection.free_cash:,.2f} 元，拒绝开新")
    if last.reason in STOP_LABELS:
        stop = bundle.stops.loc[last.cycle]
        if (stop.date, stop.contract, stop.price, stop.reason, stop.anchor_day, stop.stop) != (
                last.date, last.contract, last.price, last.reason, last.signal_day, float(last.stop)):
            raise ValueError(f"gold touch stop evidence does not reconcile for {key}")
        meta["event_markers"] = [e for e in meta["event_markers"] if "周线退出触发价" not in e["label"]]
        x = dict(zip(record["daily"]["date"], record["daily"]["x"]))[last.date]
        meta["event_markers"].append(dict(x=x, price=stop.stop, symbol="diamond-open",
                                          label=f"{last.date} 黄金止损线 {stop.stop:g} 元/克"))
        note += (f"｜前周锚 {stop.anchor_day}，止损线 {stop.stop:g}，"
                 f"触价日开盘 {stop.open:g}、最高 {stop.high:g}、最低 {stop.low:g}，模拟成交 {stop.price:g}")
        if stop.date == "2026-02-02" and stop.contract == "au2604.SHFE":
            note += "｜分钟证据：北京时间 1 月 31 日 01:42 首根触线，区间 1107.00–1113.12，成交仍按日线代理"
    meta["episode_note"] += note
    meta["exit_reason"] = reason
    for field in ("episode_note", "exit_reason", "exit_contract", "exit_marker_price", "exit_volume"):
        manifest[field] = meta[field]
    return record, manifest


def append_ledgers(page, bundle):
    rejected = bundle.rejected.assign(
        required=bundle.rejected.margin_per_lot + bundle.rejected.entry_cost_per_lot,
        direction=bundle.rejected.side.map({1: "多", -1: "空"}),
    )
    rejected = rejected.assign(kind=rejected.kind.map(ORDER_LABELS))
    rejected = rejected[["date", "product", "kind", "contract", "direction", "signal_day", "price", "free_cash", "required"]]
    rejected.columns = ["日期", "品种", "类型", "合约", "方向", "信号日", "开盘价", "可用资金", "本单所需"]
    residual = bundle.residual[["cycle", "product", "direction", "entry_day", "net_pnl"]].copy()
    residual["direction"] = residual.direction.map({1: "多", -1: "空"})
    residual.columns = ["周期", "品种", "方向", "开仓日", "截至期末净损益"]
    details = (
        '<style>.recap-ledger{background:#fff;border:1px solid #d9dee7;border-radius:8px;padding:10px 12px;'
        'margin:0 0 10px;overflow:auto;font-size:13px}.recap-ledger summary{cursor:pointer;font-weight:600}'
        '.recap-ledger table{border-collapse:collapse;margin-top:10px;width:100%}'
        '.recap-ledger th,.recap-ledger td{padding:5px 8px;border-bottom:1px solid #edf0f4;white-space:nowrap}'
        '.recap-ledger th{text-align:left;background:#f4f6f8}</style>'
        f'<details class="recap-ledger" id="residual-ledger"><summary>期末未平仓 {len(residual)} 笔 · 按期末市价核算</summary>'
        f'{residual.to_html(index=False, float_format=lambda v: f"{v:,.2f}")}</details>'
        f'<details class="recap-ledger" id="rejected-ledger"><summary>资金不足拒单 {len(rejected)} 次 · 无开仓成交</summary>'
        f'{rejected.to_html(index=False, float_format=lambda v: f"{v:,.2f}")}</details>'
    )
    anchor = '<div class="toolbar">'
    if page.count(anchor) != 1:
        raise ValueError("canonical recap toolbar anchor changed")
    return page.replace(anchor, details + anchor)


def write(run, destination):
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError(destination)
    if destination != DESTINATION:
        raise ValueError("recap output must use the Stage054 versioned destination")
    bundle = load_frozen(run)
    market, mapping = chart_market(bundle.inputs)
    exact = market.set_index(["contract_epoch_id", "date"], verify_integrity=True)
    cache = dict(tuple(market.groupby("vt_symbol", sort=False)))
    calendars = dict(tuple(mapping.groupby("continuous_symbol_vt", sort=False)))
    for symbol in mapping.main_contract_vt.unique():
        cache.setdefault(symbol, market.iloc[:0])
    records, manifests = [], []
    with patch.dict(recap.REASONS, STOP_LABELS), patch.object(recap, "FINAL_EXITS", (*recap.FINAL_EXITS, *STOP_LABELS)):
        episodes, legs, _ = recap.episode_inputs(bundle.closed, bundle.fills, None)
        reversals = recap.reversal_links(bundle.fills)
        for index, episode in enumerate(episodes.itertuples(index=False)):
            record, manifest = chart_record(
                episode, episodes, index, legs[int(episode.open_trade_id)], exact,
                calendars[episode.product], cache, bundle, reversals,
            )
            records.append(record)
            manifests.append(manifest)
    manifest = pd.concat(manifests, ignore_index=True)
    counts = episodes.result_type.value_counts()
    if (int(counts.get("profit", 0)), int(counts.get("loss", 0))) != (bundle.metrics["wins"], bundle.metrics["losses"]):
        raise ValueError("completed episode results differ from frozen metrics")
    summary = dict(
        episode_scope="all", source_label="S21 Stage054 黄金盘中触价止损 · 固定一手 · 开仓资金检查",
        source_version="stage054_s21_gold_touch_halfyear_20261104/2026-01-01",
        page_title="2026 年逐笔交易复盘｜S21 黄金触价止损",
        source_warning="多数成交为日开盘代理。黄金盘中触价按日线模拟成交。持仓段使用实际合约，持仓前后是未经价差调整的主力背景。",
        coverage_note=f" {START} 至 {END}，15 万元空仓起跑，期末权益 160,295 元，收益 +6.86%。图表未绘制 15 分钟 K。",
        footer_scope=(f"{len(records)} 个完整开平仓周期，{counts.get('profit', 0)} 盈、{counts.get('loss', 0)} 亏、"
                      f"{counts.get('flat', 0)} 平，已平仓净损益 {bundle.closed.net_pnl.sum():+,.0f} 元。"
                      f"期末未平仓 {len(bundle.residual)} 笔，净损益 {bundle.residual.net_pnl.sum():+,.0f} 元。"),
        rank_basis="realized_pnl", chart_episodes=len(records), chart_profit_episodes=int(counts.get("profit", 0)),
        chart_loss_episodes=int(counts.get("loss", 0)), chart_flat_episodes=int(counts.get("flat", 0)),
        backtest_metrics=bundle.metrics, provenance=bundle.inputs, frozen_manifest_sha256=SOURCE_SHA,
        independent_audit_sha256=AUDIT_SHA, scoped_closed_pnl=float(bundle.closed.net_pnl.sum()),
        residual_open_positions=bundle.residual.to_dict("records"), rejected_opening_orders=len(bundle.rejected),
        bars_15m=0, missing_context_days=sum(len(r["meta"]["missing_context_dates"]) for r in records),
        context_fallback_days=int(manifest.context_fallback_days.sum()),
        period_picker={"options": ["day30", "day10", "monthly", "weekly", "daily"],
                       "default_selected": ["day30", "daily"]},
    )
    page = append_ledgers(recap.renderer._html(records, summary), bundle)
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "index.html").write_text(page, encoding="utf-8")
    manifest.to_csv(destination / "chart_manifest.csv", index=False)
    bundle.fills.to_csv(destination / "scoped_fills.csv", index=False)
    (destination / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return destination / "index.html"


if __name__ == "__main__":
    print(write(RUN, DESTINATION))
