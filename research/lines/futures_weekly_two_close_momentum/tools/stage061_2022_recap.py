"""Display the frozen Stage060 200k cold start's 2022 entry cohort."""
from dataclasses import dataclass, replace
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import stage054_trade_recap as adapter
import stage055_s21_all_touch_halfyear as touch

recap = adapter.recap
ROOT = recap.LINE / "outputs/stage060_s21_200k_touch_halfyear_20261104"
RUN = ROOT / "S21_20w/2022-01-01"
DESTINATION = recap.FORENSICS / "outputs/stage061_s21_200k_touch_2022_recap_v1"
SOURCE_SHA = "c8bff538f87f7625fa446c4eb710d5e1e8d1d7f05a5b8926ccdee557150d18cf"
AUDIT_SHA = "a378b07df043792469b5e3f07748ed153d1645c620e4d47b32b321a7f80450bb"
START, END = "2022-01-04", "2026-11-04"
SCOPE_START, SCOPE_END = "2022-01-01", "2022-12-31"
PROFILE = replace(recap.STAGE025_S44_2022, start=SCOPE_START, end=SCOPE_END)
STOP_LABELS = {
    touch.OPEN_GAP: "开盘跳空触价止损", touch.INTRADAY: "盘中触价止损",
    touch.DELAYED: "一价触发后延迟至可成交日开盘止损",
}


@dataclass(frozen=True)
class AnnualBundle(adapter.Bundle):
    calendar_year_pnl: float
    year_end_equity: float
    source_residual: pd.DataFrame


def load_frozen(run):
    if run.resolve() != RUN:
        raise ValueError("expected Stage060's frozen 200k January 2022 independent start")
    touch.base.verify_manifest(ROOT, SOURCE_SHA)
    recap.verify(recap.LINE / "reviews/stage060_s21_200k_audit.json", AUDIT_SHA)
    receipt = touch.prior.read_json(ROOT / "receipt.json")
    inputs = touch.prior.read_json(run / "inputs.json")
    metrics = touch.prior.read_json(run / "summary.json")
    if (inputs["products"] != receipt["products"] or len(inputs["products"]) != 21
            or inputs["inputs_sha256"] != receipt["market_sha256"]
            or inputs["all_products_stop_rule"] != touch.RULE
            or inputs["fixed_one_margin_gate"] != touch.gold.parent.GATE
            or inputs["initial"] != 200000 or inputs["start"] != SCOPE_START
            or (metrics["start"], metrics["end"]) != (START, END)):
        raise ValueError("frozen 200k source identity mismatch")
    daily = pd.read_csv(run / "daily.csv")
    cycles = pd.read_csv(run / "cycles.csv", keep_default_na=False)
    fills = pd.read_csv(run / "fills.csv", keep_default_na=False)
    fills.insert(0, "fill_id", fills.index + 1)
    all_closed = cycles.loc[cycles.exit_day.ne("")]
    source_residual = cycles.loc[cycles.exit_day.eq("")]
    if (daily.date.iloc[[0, -1]].tolist() != [START, END]
            or len(daily) != metrics["days"] or daily.equity.iat[-1] != metrics["equity"]
            or len(fills) != metrics["fills"] or len(all_closed) != metrics["closed_cycles"]
            or len(source_residual) != metrics["open_positions"] or not fills.volume.eq(1).all()
            or set(cycles.cycle) != set(fills.cycle)
            or abs(cycles.net_pnl.sum() - metrics["net_pnl"]) > 1e-7
            or abs(source_residual.net_pnl.sum() - metrics["terminal_open_net_pnl"]) > 1e-7):
        raise ValueError("source cycle, daily and terminal ledgers do not reconcile")
    closed, residual = recap.partition_cycles(cycles, PROFILE)
    sizing = pd.read_csv(run / "risk_sizing.csv", keep_default_na=False)
    rejected = sizing.loc[sizing.status.eq("margin_below_one_lot") & sizing.date.between(SCOPE_START, SCOPE_END)].copy()
    stops = pd.read_csv(run / "touch_stops.csv", keep_default_na=False).set_index("cycle")
    signals = pd.read_csv(run / "signals.csv", keep_default_na=False)
    calendar_year = daily.loc[daily.date.between(SCOPE_START, SCOPE_END)]
    annual = pd.read_csv(run / "annual.csv").set_index("date")
    year_pnl = float(calendar_year.net_pnl.sum())
    if year_pnl != float(annual.loc[2022, "net_pnl"]):
        raise ValueError("calendar-year contribution does not reconcile")
    return AnnualBundle(inputs, metrics, closed, residual, fills, stops, rejected, signals, sizing,
                        year_pnl, float(calendar_year.equity.iat[-1]), source_residual)


def year_contributions(bundle, exact):
    calendar = pd.read_csv(RUN / "daily.csv").date
    year_end = calendar.loc[calendar.le(SCOPE_END)].iat[-1]
    result = {}
    for cycle in pd.concat([bundle.closed, bundle.residual]).itertuples(index=False):
        legs = bundle.fills.loc[bundle.fills.cycle.eq(cycle.cycle) & bundle.fills.date.le(SCOPE_END)]
        cash_flow = sum(-f.side * f.volume * f.price * f.size - f.slippage - f.commission
                        for f in legs.itertuples(index=False))
        mark = 0.0
        if not cycle.exit_day or cycle.exit_day > SCOPE_END:
            last = legs.iloc[-1]
            if last.reason not in ("entry", "roll_open"):
                raise ValueError(f"unexpected year-end holding leg: {cycle.cycle}")
            bar = exact.loc[last.epoch, pd.Timestamp(year_end)]
            mark = last.side * last.volume * last["size"] * bar.close
        result[int(cycle.cycle)] = float(cash_flow + mark)
    if abs(sum(result.values()) - bundle.calendar_year_pnl) > 1e-7:
        raise ValueError("per-cycle annual PnL does not conserve calendar-year contribution")
    return result


def chart_record(episode, episodes, index, legs, exact, calendar, cache, bundle, reversals, annual):
    record, manifest = adapter.chart_record(episode, episodes, index, legs, exact, calendar, cache, bundle, reversals)
    meta = record["meta"]
    last = legs[-1]
    if last.reason in STOP_LABELS:
        stop = bundle.stops.loc[last.cycle]
        original = f"触发记录日 {last.signal_day}，成交日 {last.date}"
        corrected = f"止损锚周 {stop.anchor_day}，触价日 {stop.trigger_day}，成交日 {last.date}"
        meta["episode_note"] = meta["episode_note"].replace(original, corrected)
        for event in meta["event_markers"]:
            event["label"] = event["label"].replace("黄金止损线", "止损线").replace(" 元/克", "")
        if last.reason == touch.DELAYED:
            meta["episode_note"] += f"｜{stop.trigger_day} 一价触发锁定，延迟至 {last.date} 非一价开盘退出"
    contribution = annual[int(episode.open_trade_id)]
    meta["calendar_year_pnl"] = contribution
    meta["episode_note"] += f"｜2022年贡献 {contribution:+,.0f} 元，完整周期净损益 {episode.realized_pnl:+,.0f} 元"
    manifest["calendar_year_pnl"] = contribution
    manifest["episode_note"] = meta["episode_note"]
    return record, manifest


def write(run, destination):
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError(destination)
    if destination != DESTINATION:
        raise ValueError("output must use the versioned Stage061 recap directory")
    bundle = load_frozen(run)
    market, mapping = adapter.chart_market(bundle.inputs)
    exact = market.set_index(["contract_epoch_id", "date"], verify_integrity=True)
    annual = year_contributions(bundle, exact)
    cache = dict(tuple(market.groupby("vt_symbol", sort=False)))
    calendars = dict(tuple(mapping.groupby("continuous_symbol_vt", sort=False)))
    for symbol in mapping.main_contract_vt.unique():
        cache.setdefault(symbol, market.iloc[:0])
    records, manifests = [], []
    with (patch.dict(recap.REASONS, STOP_LABELS),
          patch.object(recap, "FINAL_EXITS", (*recap.FINAL_EXITS, *STOP_LABELS)),
          patch.object(adapter, "STOP_LABELS", STOP_LABELS),
          patch.object(adapter, "PROFILE", PROFILE), patch.object(adapter, "END", END),
          patch.object(adapter.touch, "INTRADAY", touch.INTRADAY)):
        episodes, by_cycle, _ = recap.episode_inputs(bundle.closed, bundle.fills, None)
        reversals = recap.reversal_links(bundle.fills)
        for index, episode in enumerate(episodes.itertuples(index=False)):
            record, manifest = chart_record(
                episode, episodes, index, by_cycle[int(episode.open_trade_id)], exact,
                calendars[episode.product], cache, bundle, reversals, annual,
            )
            records.append(record)
            manifests.append(manifest)
    manifest = pd.concat(manifests, ignore_index=True)
    counts = episodes.result_type.value_counts()
    cross_year = int(bundle.closed.exit_day.gt(SCOPE_END).sum())
    scoped_fills = bundle.fills.loc[bundle.fills.cycle.isin(bundle.closed.cycle)]
    summary = dict(
        episode_scope="all", source_label="S21 Stage060 · 20万元 · 固定一手 · 全品种触价止损",
        source_version="stage060_s21_200k_touch_halfyear_20261104/S21_20w/2022-01-01",
        page_title="2022 年逐笔交易复盘｜21品种 · 20万元 · 触价止损",
        source_warning="2022年初独立空仓启动。开盘成交与盘中触价使用日OHLC代理。持仓段为实际合约，前后为未经价差调整的主力背景。",
        coverage_note=(f"按2022年开仓筛选，跨年周期保持完整。2022年账户净损益 {bundle.calendar_year_pnl:+,.0f} 元，"
                       f"年末权益 {bundle.year_end_equity:,.0f} 元。冻结行情无15分钟数据。"),
        footer_scope=(f"{len(records)} 个完整周期，{counts.get('profit', 0)} 盈、{counts.get('loss', 0)} 亏、"
                      f"{counts.get('flat', 0)} 平，其中 {cross_year} 个跨年平仓。完整周期净损益 "
                      f"{bundle.closed.net_pnl.sum():+,.0f} 元，2022年贡献 {bundle.calendar_year_pnl:+,.0f} 元。"
                      f"源回测截至2026-11-04另有 {len(bundle.source_residual)} 个晚期开仓未完成周期。"),
        rank_basis="realized_pnl", chart_episodes=len(records), chart_profit_episodes=int(counts.get("profit", 0)),
        chart_loss_episodes=int(counts.get("loss", 0)), chart_flat_episodes=int(counts.get("flat", 0)),
        scoped_fills=len(scoped_fills), scoped_closed_pnl=float(bundle.closed.net_pnl.sum()),
        scope_entry_start=SCOPE_START, scope_entry_end=SCOPE_END, exit_after_scope=cross_year,
        calendar_year_pnl=bundle.calendar_year_pnl, calendar_year_end_equity=bundle.year_end_equity,
        calendar_year_return_pct=100 * bundle.calendar_year_pnl / bundle.inputs["initial"],
        calendar_year_fills=int(bundle.fills.date.between(SCOPE_START, SCOPE_END).sum()),
        backtest_metrics=bundle.metrics, provenance=bundle.inputs, frozen_manifest_sha256=SOURCE_SHA,
        independent_audit_sha256=AUDIT_SHA, residual_open_positions=bundle.residual.to_dict("records"),
        source_residual_open_positions=bundle.source_residual.to_dict("records"),
        rejected_opening_orders=len(bundle.rejected), bars_15m=0,
        missing_context_days=sum(len(r["meta"]["missing_context_dates"]) for r in records),
        context_fallback_days=int(manifest.context_fallback_days.sum()),
        period_picker={"options": ["day30", "day10", "monthly", "weekly", "daily"],
                       "default_selected": ["day30", "daily"]},
    )
    page = adapter.append_ledgers(recap.renderer._html(records, summary), bundle)
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "index.html").write_text(page)
    (destination / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    manifest.to_csv(destination / "chart_manifest.csv", index=False)
    scoped_fills.to_csv(destination / "scoped_fills.csv", index=False)
    annual_frame = bundle.closed[["cycle", "product", "entry_day", "exit_day", "net_pnl"]].copy()
    annual_frame["calendar_year_pnl"] = annual_frame.cycle.map(annual)
    annual_frame.to_csv(destination / "annual_contributions.csv", index=False)
    receipt = dict(source_manifest_sha256=SOURCE_SHA, source_audit_sha256=AUDIT_SHA,
                   entrypoint_sha256=touch.base.portfolio.sha(Path(__file__)),
                   prior_adapter_sha256=touch.base.portfolio.sha(Path(adapter.__file__)),
                   renderer_sha256=touch.base.portfolio.sha(Path(recap.renderer.__file__)),
                   strategy_rerun=False, market_download=False, production_access=False)
    (destination / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    touch.base.write_checksums(destination, (p for p in destination.rglob("*") if p.is_file()))
    return destination / "index.html"


if __name__ == "__main__":
    print(write(RUN, DESTINATION))
