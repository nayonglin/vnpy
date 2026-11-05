"""2017 overlap-year recap of Stage060's frozen 2015 continuous 200k account."""
from dataclasses import dataclass, replace
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import stage061_2022_recap as parent

adapter, recap, touch = parent.adapter, parent.recap, parent.touch
ROOT = parent.ROOT
RUN = ROOT / "S21_20w/2015-01-01"
DESTINATION = recap.FORENSICS / "outputs/stage064_s21_200k_continuous_2017_recap_v1"
YEAR = 2017
SCOPE_START, SCOPE_END = "2017-01-01", "2017-12-31"
PROFILE = replace(parent.PROFILE, start=SCOPE_START, end=SCOPE_END, include_overlap=True)


@dataclass(frozen=True)
class AnnualBundle(parent.AnnualBundle):
    year_open_equity: float


def load_frozen(run):
    if run.resolve() != RUN:
        raise ValueError("expected Stage060's 2015 continuous 200k account")
    touch.base.verify_manifest(ROOT, parent.SOURCE_SHA)
    recap.verify(recap.LINE / "reviews/stage060_s21_200k_audit.json", parent.AUDIT_SHA)
    receipt = touch.prior.read_json(ROOT / "receipt.json")
    inputs = touch.prior.read_json(run / "inputs.json")
    metrics = touch.prior.read_json(run / "summary.json")
    if (inputs["products"] != receipt["products"] or len(inputs["products"]) != 21
            or inputs["inputs_sha256"] != receipt["market_sha256"]
            or inputs["all_products_stop_rule"] != touch.RULE
            or inputs["fixed_one_margin_gate"] != touch.gold.parent.GATE
            or inputs["initial"] != 200000 or inputs["start"] != "2015-01-01"
            or (metrics["start"], metrics["end"]) != ("2015-01-05", parent.END)):
        raise ValueError("frozen continuous account identity mismatch")
    daily = pd.read_csv(run / "daily.csv")
    cycles = pd.read_csv(run / "cycles.csv", keep_default_na=False)
    fills = pd.read_csv(run / "fills.csv", keep_default_na=False)
    fills.insert(0, "fill_id", fills.index + 1)
    source_residual = cycles.loc[cycles.exit_day.eq("")]
    if (len(daily) != metrics["days"] or daily.equity.iat[-1] != metrics["equity"]
            or len(fills) != metrics["fills"] or not fills.volume.eq(1).all()
            or len(cycles.loc[cycles.exit_day.ne("")]) != metrics["closed_cycles"]
            or len(source_residual) != metrics["open_positions"]
            or abs(cycles.net_pnl.sum() - metrics["net_pnl"]) > 1e-7):
        raise ValueError("source cycle and daily ledgers do not reconcile")
    closed, residual = recap.partition_cycles(cycles, PROFILE)
    sizing = pd.read_csv(run / "risk_sizing.csv", keep_default_na=False)
    rejected = sizing.loc[sizing.status.eq("margin_below_one_lot")
                          & sizing.date.between(SCOPE_START, SCOPE_END)].copy()
    stops = pd.read_csv(run / "touch_stops.csv", keep_default_na=False).set_index("cycle")
    signals = pd.read_csv(run / "signals.csv", keep_default_na=False)
    year_daily = daily.loc[daily.date.between(SCOPE_START, SCOPE_END)]
    year_open = float(daily.loc[daily.date.lt(SCOPE_START)].equity.iat[-1])
    year_end = float(year_daily.equity.iat[-1])
    year_pnl = float(year_daily.net_pnl.sum())
    annual = pd.read_csv(run / "annual.csv").set_index("date")
    if year_end - year_open != year_pnl or float(annual.loc[YEAR, "net_pnl"]) != year_pnl:
        raise ValueError("annual daily PnL, opening/end equity do not conserve")
    return AnnualBundle(inputs=inputs, metrics=metrics, closed=closed, residual=residual,
                        fills=fills, stops=stops, rejected=rejected, signals=signals, sizing=sizing,
                        calendar_year_pnl=year_pnl, year_end_equity=year_end,
                        source_residual=source_residual, year_open_equity=year_open)


def marked_value(legs, day, exact):
    """Cycle cumulative net cashflow plus any live contract mark at a year boundary."""
    legs = legs.loc[legs.date.le(day)].copy()
    if legs.empty:
        return 0.0
    cash = float((-legs.side * legs.volume * legs.price * legs["size"]
                  - legs.slippage - legs.commission).sum())
    positions = (legs.side * legs.volume).groupby(legs.epoch).sum()
    active = positions.loc[positions.ne(0)]
    if active.empty:
        return cash
    if len(active) != 1 or abs(active.iloc[0]) != 1:
        raise ValueError("unexpected cycle position at annual boundary")
    epoch = active.index[0]
    last = legs.loc[legs.epoch.eq(epoch)].iloc[-1]
    if last.reason not in ("entry", "roll_open"):
        raise ValueError("annual boundary holding lacks an opening leg")
    bar = exact.loc[epoch, pd.Timestamp(day)]
    return cash + float(active.iloc[0] * last["size"] * bar.close)


def year_contributions(bundle, exact):
    calendar = pd.read_csv(RUN / "daily.csv").date
    before = calendar.loc[calendar.lt(SCOPE_START)].iat[-1]
    ending = calendar.loc[calendar.le(SCOPE_END)].iat[-1]
    result = {}
    for cycle in pd.concat([bundle.closed, bundle.residual]).itertuples(index=False):
        legs = bundle.fills.loc[bundle.fills.cycle.eq(cycle.cycle)]
        result[int(cycle.cycle)] = marked_value(legs, ending, exact) - marked_value(legs, before, exact)
    if abs(sum(result.values()) - bundle.calendar_year_pnl) > 1e-7:
        raise ValueError("year-boundary marks do not conserve annual account PnL")
    return result


def write(run, destination):
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError(destination)
    if destination != DESTINATION:
        raise ValueError("use the registered versioned 2017 recap destination")
    bundle = load_frozen(run)
    market, mapping = adapter.chart_market(bundle.inputs)
    exact = market.set_index(["contract_epoch_id", "date"], verify_integrity=True)
    annual = year_contributions(bundle, exact)
    cache = dict(tuple(market.groupby("vt_symbol", sort=False)))
    calendars = dict(tuple(mapping.groupby("continuous_symbol_vt", sort=False)))
    for symbol in mapping.main_contract_vt.unique():
        cache.setdefault(symbol, market.iloc[:0])
    records, manifests = [], []
    with (patch.dict(recap.REASONS, parent.STOP_LABELS),
          patch.object(recap, "FINAL_EXITS", (*recap.FINAL_EXITS, *parent.STOP_LABELS)),
          patch.object(adapter, "STOP_LABELS", parent.STOP_LABELS),
          patch.object(adapter, "PROFILE", PROFILE), patch.object(adapter, "END", parent.END),
          patch.object(adapter.touch, "INTRADAY", touch.INTRADAY)):
        episodes, by_cycle, _ = recap.episode_inputs(bundle.closed, bundle.fills, None)
        reversals = recap.reversal_links(bundle.fills)
        for index, episode in enumerate(episodes.itertuples(index=False)):
            record, manifest = parent.chart_record(
                episode, episodes, index, by_cycle[int(episode.open_trade_id)], exact,
                calendars[episode.product], cache, bundle, reversals, annual)
            record["meta"]["episode_note"] = record["meta"]["episode_note"].replace("2022年贡献", "2017年贡献")
            manifest["episode_note"] = record["meta"]["episode_note"]
            records.append(record)
            manifests.append(manifest)
    manifest = pd.concat(manifests, ignore_index=True)
    counts = episodes.result_type.value_counts()
    incoming = int(bundle.closed.entry_day.lt(SCOPE_START).sum())
    outgoing = int(bundle.closed.exit_day.gt(SCOPE_END).sum())
    scoped_fills = bundle.fills.loc[bundle.fills.cycle.isin(bundle.closed.cycle)]
    annual_frame = bundle.closed[["cycle", "product", "entry_day", "exit_day", "net_pnl"]].copy()
    annual_frame["calendar_year_pnl"] = annual_frame.cycle.map(annual)
    annual_frame["incoming"] = annual_frame.entry_day.lt(SCOPE_START)
    annual_frame["outgoing"] = annual_frame.exit_day.gt(SCOPE_END)
    summary = dict(
        episode_scope="all", source_label="S21 Stage060 · 20万元 · 固定一手 · 全品种触价止损",
        source_version="stage060_s21_200k_touch_halfyear_20261104/S21_20w/2015-01-01",
        page_title="2017 年逐笔交易复盘｜21品种 · 20万元 · 2015年连续账户",
        source_warning="来源是2015年起连续回测账户。开盘及盘中触价使用日OHLC代理。持仓段为实际合约，前后为未经价差调整的主力背景。",
        coverage_note=(f"展示所有与2017年重叠的交易，{incoming}笔从2016年带入，{outgoing}笔延续到2018年，均保留完整开平。"
                       f"2017年账户净损益 {bundle.calendar_year_pnl:+,.0f} 元；年初权益 {bundle.year_open_equity:,.0f} 元，"
                       f"年末权益 {bundle.year_end_equity:,.0f} 元。盈亏筛选按完整周期净损益，2017年贡献单列。冻结行情无15分钟数据。"),
        footer_scope=(f"{len(records)}个完整周期，{counts.get('profit', 0)}盈、{counts.get('loss', 0)}亏、{counts.get('flat', 0)}平；"
                      f"其中{incoming}笔跨年带入、{outgoing}笔年末仍持仓。完整周期净损益 {bundle.closed.net_pnl.sum():+,.0f} 元，"
                      f"2017年账户贡献 {bundle.calendar_year_pnl:+,.0f} 元。期末市值差异通过2016/2017年末双边估值核算。"),
        rank_basis="realized_pnl", chart_episodes=len(records), chart_profit_episodes=int(counts.get("profit", 0)),
        chart_loss_episodes=int(counts.get("loss", 0)), chart_flat_episodes=int(counts.get("flat", 0)),
        scoped_fills=len(scoped_fills), scoped_closed_pnl=float(bundle.closed.net_pnl.sum()),
        scope_start=SCOPE_START, scope_end=SCOPE_END, scope_mode="calendar_overlap",
        entry_before_scope=incoming, exit_after_scope=outgoing,
        calendar_year_pnl=bundle.calendar_year_pnl, calendar_year_open_equity=bundle.year_open_equity,
        calendar_year_end_equity=bundle.year_end_equity,
        calendar_year_return_pct=100 * bundle.calendar_year_pnl / bundle.year_open_equity,
        calendar_year_fills=int(bundle.fills.date.between(SCOPE_START, SCOPE_END).sum()),
        backtest_metrics=bundle.metrics, provenance=bundle.inputs, frozen_manifest_sha256=parent.SOURCE_SHA,
        independent_audit_sha256=parent.AUDIT_SHA, residual_open_positions=bundle.residual.to_dict("records"),
        source_residual_open_positions=bundle.source_residual.to_dict("records"),
        year_end_holding_cycles=annual_frame.loc[annual_frame.outgoing].to_dict("records"),
        rejected_opening_orders=len(bundle.rejected), bars_15m=0,
        missing_context_days=sum(len(r["meta"]["missing_context_dates"]) for r in records),
        context_fallback_days=int(manifest.context_fallback_days.sum()),
        period_picker={"options": ["day30", "day10", "monthly", "weekly", "daily"],
                       "default_selected": ["day30", "daily"]})
    page = adapter.append_ledgers(recap.renderer._html(records, summary), bundle)
    page = page.replace(f"期末未平仓 {len(bundle.residual)} 笔 · 按期末市价核算",
                        f"本页截至源回测终点仍未最终平仓 {len(bundle.residual)} 笔 · 2017年末另有{outgoing}笔仍持仓")
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "index.html").write_text(page)
    (destination / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    manifest.to_csv(destination / "chart_manifest.csv", index=False)
    scoped_fills.to_csv(destination / "scoped_fills.csv", index=False)
    annual_frame.to_csv(destination / "annual_contributions.csv", index=False)
    receipt = dict(source_manifest_sha256=parent.SOURCE_SHA, source_audit_sha256=parent.AUDIT_SHA,
                   entrypoint_sha256=touch.base.portfolio.sha(Path(__file__)),
                   parent_adapter_sha256=touch.base.portfolio.sha(Path(parent.__file__)),
                   renderer_sha256=touch.base.portfolio.sha(Path(recap.renderer.__file__)),
                   source_run=str(RUN), scope_mode="calendar_overlap",
                   strategy_rerun=False, market_download=False, production_access=False)
    (destination / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    touch.base.write_checksums(destination, (p for p in destination.rglob("*") if p.is_file()))
    print(json.dumps({key: summary[key] for key in ("chart_episodes", "chart_profit_episodes", "chart_loss_episodes",
          "scoped_closed_pnl", "calendar_year_pnl", "calendar_year_return_pct", "entry_before_scope", "exit_after_scope")}, ensure_ascii=False))
    return destination / "index.html"


if __name__ == "__main__":
    print(write(RUN, DESTINATION))
