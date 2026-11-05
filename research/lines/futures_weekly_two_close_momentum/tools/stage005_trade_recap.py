"""Adapt audited two-close weekly trades to the canonical Stage038 recap."""
import argparse
from dataclasses import dataclass, replace
import hashlib
from itertools import pairwise
import json
from math import isclose
from pathlib import Path
import sys

import pandas as pd

LINE = Path(__file__).resolve().parents[1]
FORENSICS = LINE.parent / "futures_trend_winner_trade_forensics"
sys.path.insert(0, str(FORENSICS / "tools"))
import stage038_c9_15w_big_winner_multiscale_html as renderer

RUN = "stage005_D_2015_20261103"
AUDIT_SHA = "4aaf096b4e5b2c32acf75c6bc9d7a83a95fdcdce3a2547e4ee813911d7d20ba5"
START, END = "2015-01-01", "2020-12-31"
DESTINATION = FORENSICS / "outputs/stage005_weekly_cash_half_pct_2015_2020_recap_v1"
REASONS = {"entry": "开仓", "weekly_stop": "周线止损", "roll_close": "换月平旧",
           "roll_open": "换月开新", "roll_funding_exit": "换月资金不足退出",
           "delivery_guard_exit": "到期保护平仓"}
FINAL_EXITS = ("weekly_stop", "roll_funding_exit", "delivery_guard_exit")


@dataclass(frozen=True)
class RecapProfile:
    run: str
    audit_sha: str | None
    start: str
    end: str
    risk_fraction: float | None
    week_body_filter: bool
    label: str
    title: str
    destination: Path
    max_fixed_adds: int = 0
    reverse_after_stop: bool = False
    manifest_sha: str | None = None
    block_four_up: bool = False
    include_overlap: bool = False
    delivery_guard_days: int | None = None


STAGE005 = RecapProfile(
    RUN, AUDIT_SHA, START, END, 0.005, False, "两周收盘动量 Stage005 D · 可用现金 0.5%",
    "2015–2020 逐笔交易复盘｜现金风险 0.5%", DESTINATION,
)
STAGE007_2022 = RecapProfile(
    "stage007_F_2015_20261103", "73885afb1f901318f8dcc17592ae871c5559994cc58f0d82a549ef32f4dad5fd",
    "2022-01-01", "2022-12-31", None, True, "两周收盘动量 Stage007 F · 双周实体 · 固定一手",
    "2022 年逐笔交易复盘｜双周实体 · 固定一手",
    FORENSICS / "outputs/stage007_weekly_fixed_one_2022_recap_v1",
)
STAGE013_2022 = RecapProfile(
    "stage013_L_2015_20261103", "d2b04fce246f7d4918d7c8554b65cb88753d422d189d4e6a91dea5fa02f4a8de",
    "2022-01-01", "2022-12-31", None, True, "两周收盘动量 Stage013 L · 断档后只加一次",
    "2022 年逐笔交易复盘｜断档后只加一次",
    FORENSICS / "outputs/stage013_weekly_fresh_one_add_2022_recap_v1", max_fixed_adds=1,
)
STAGE018_2022 = RecapProfile(
    "stage018_Q_2015_20261103", "3b7127012288115350ea06ea4616f69d5cee9e666d256350bdcf06647b8e9f18",
    "2022-01-01", "2022-12-31", None, True, "两周收盘动量 Stage018 Q · 19 品种 · 固定一手 · 同日反手",
    "2022 年逐笔交易复盘｜Q 固定一手 · 同日反手",
    FORENSICS / "outputs/stage018_Q_weekly_fixed_one_reversal_2022_recap_v1", reverse_after_stop=True,
)
STAGE022 = replace(
    STAGE018_2022, run="stage022_S_2015_20261103", audit_sha=None,
    manifest_sha="5b6ed72dfe25026b41546176df3873b7622796a104fafd5052c087f2108a5f84",
    label="两周收盘动量 Stage022 S · 固定一手 · 四周过滤", block_four_up=True,
)
STAGE025_S44_2022 = replace(
    STAGE022, run="stage025_delivery_guard/S44_guard_2015_20261103_attempt001",
    manifest_sha="406465f36de37935b4947fb68bf94a6b4caf3437916fdad639ff2269f0c2f361",
    label="两周收盘动量 Stage025 S44 · 44 品种 · 多空 · 固定一手 · 到期保护",
    title="2022 年逐笔交易复盘｜S44 双向 · 到期保护",
    destination=FORENSICS / "outputs/stage025_s44_long_short_2022_recap_v1",
    delivery_guard_days=5,
)

WINDOW_PROFILES = {}
for arm, base in (("q", STAGE018_2022), ("s", STAGE022)):
    for start, end in (("2020-01-02", "2020-06-05"), ("2022-06-27", "2023-01-20")):
        slug = f"{base.run.split('_')[0]}_{arm}_{start.replace('-', '')}_{end.replace('-', '')}_overlap_recap_v1"
        WINDOW_PROFILES[f"{arm}-{start[:4]}-drawdown"] = replace(
            base, start=start, end=end, include_overlap=True,
            title=f"{start} 至 {end} 逐笔交易复盘｜{arm.upper()}",
            destination=FORENSICS / "outputs" / slug,
        )


def verify(path, digest):
    with path.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != digest:
            raise ValueError(f"frozen hash mismatch: {path}")


def partition_cycles(cycles, profile=STAGE005):
    if profile.include_overlap:
        selected = cycles.loc[
            cycles.entry_day.le(profile.end) & (cycles.exit_day.eq("") | cycles.exit_day.ge(profile.start))
        ]
    else:
        selected = cycles.loc[cycles.entry_day.between(profile.start, profile.end)]
    return selected.loc[selected.exit_day.ne("")], selected.loc[selected.exit_day.eq("")]


def load(run, profile=STAGE005):
    if profile.manifest_sha is not None:
        manifest = run / "SHA256SUMS"
        verify(manifest, profile.manifest_sha)
        expected = {}
        for line in manifest.read_text().splitlines():
            digest, name = line.split(maxsplit=1)
            expected[name] = digest
        if not {"inputs.json", "summary.json", "daily.csv", "cycles.csv", "fills.csv"} <= expected.keys():
            raise ValueError("frozen manifest does not bind the recap source")
    else:
        audit_path = run / "independent_audit.json"
        verify(audit_path, profile.audit_sha)
        expected = json.loads(audit_path.read_text())["outputs_sha256"]
    for name, digest in expected.items():
        verify(run / name, digest)
    inputs = json.loads((run / "inputs.json").read_text())
    metrics = json.loads((run / "summary.json").read_text())
    if (inputs["cash_risk_fraction"] != profile.risk_fraction or not inputs["ma_slope_filter"]
            or inputs.get("week_body_filter", False) != profile.week_body_filter
            or inputs.get("max_fixed_adds", 0) != profile.max_fixed_adds
            or inputs.get("fresh_add_sequence", False) != bool(profile.max_fixed_adds)
            or inputs.get("reverse_after_stop", False) != profile.reverse_after_stop
            or inputs.get("block_four_up", False) != profile.block_four_up
            or inputs.get("delivery_guard_trading_days") != profile.delivery_guard_days
            or inputs.get("long_only", False)
            or inputs.get("max_active_products") is not None):
        raise ValueError(f"parameters do not match frozen profile: {profile.run}")
    paths = {Path(path): digest for path, digest in inputs["inputs_sha256"].items()}
    for path, digest in paths.items():
        verify(path, digest)
    for path, digest in inputs["source_sha256"].items():
        archive = run / "frozen_source" / Path(path).name
        verify(archive if archive.is_file() else Path(path), digest)
    daily = pd.read_csv(run / "daily.csv")
    cycles = pd.read_csv(run / "cycles.csv", keep_default_na=False)
    fills = pd.read_csv(run / "fills.csv", keep_default_na=False)
    fills.insert(0, "fill_id", fills.index + 1)
    sizing = None
    if profile.risk_fraction is None:
        entries = fills.reason.isin(["entry", "add"])
        if (not fills.loc[entries, "volume"].eq(1).all()
                or not fills.volume.between(1, 1 + profile.max_fixed_adds).all()
                or fills.loc[fills.reason.eq("add")].groupby("cycle").size().gt(profile.max_fixed_adds).any()):
            raise ValueError("fixed-lot ledger violates the profile's entry or position size")
    else:
        sizing = pd.read_csv(run / "risk_sizing.csv", keep_default_na=False)
    if (len(daily) != metrics["days"] or daily.date.iloc[-1] != inputs["end"]
            or daily.equity.iloc[-1] != metrics["equity"] or len(fills) != metrics["fills"]
            or cycles.exit_day.ne("").sum() != metrics["closed_cycles"]
            or not isclose(cycles.net_pnl.sum(), metrics["net_pnl"])):
        raise ValueError("frozen ledgers do not reconcile to summary")
    market_columns = [
        "vt_symbol", "date", "contract_epoch_id", "open", "high", "low", "close", "volume",
    ]
    if profile.delivery_guard_days is not None:
        # The Stage025 receipt pins both the original 19 and the admitted
        # 25-product extension. The upstream source archive is not the replay feed.
        base = LINE.parent / "futures_weekly19_stop_reversal/outputs/stage002_data/data_approved"
        extra = LINE / "outputs/stage024_market/approved_v1"
        bar_paths = [base / "physical_epoch_daily.csv", extra / "added_bars.csv"]
        map_paths = [base / "mapping.csv", extra / "added_mapping.csv"]
    else:
        by_name = {path.name: path for path in paths}
        bar_paths = [by_name["physical_epoch_daily.csv"]]
        map_paths = [by_name["mapping.csv"]]
    if not set(bar_paths + map_paths) <= paths.keys():
        raise ValueError("frozen receipt does not bind the recap market data")
    market = pd.concat([
        pd.read_csv(path, parse_dates=["date"], usecols=market_columns) for path in bar_paths
    ], ignore_index=True)
    if market.duplicated(["vt_symbol", "date"]).any() or market.duplicated(["contract_epoch_id", "date"]).any():
        raise ValueError("ambiguous physical contract bar")
    map_columns = ["date", "continuous_symbol_vt", "main_contract_vt"]
    mapping = pd.concat([
        pd.read_csv(path, parse_dates=["date"], keep_default_na=False, usecols=map_columns)
        for path in map_paths
    ], ignore_index=True)
    mapping[["product", "exchange"]] = mapping.continuous_symbol_vt.str.split(".", n=1, expand=True)
    if profile.delivery_guard_days is not None and (
        len(inputs["products"]) != 44
        or set(mapping.continuous_symbol_vt) != set(inputs["products"])
        or mapping.duplicated(["date", "continuous_symbol_vt"]).any()
    ):
        raise ValueError("frozen 44-product mapping mismatch")
    return inputs, metrics, cycles, fills, sizing, market, mapping


def closed_segments(legs, direction):
    segments = []
    opened = None
    for fill in legs:
        if opened is None:
            expected = "roll_open" if segments else "entry"
            if fill.reason != expected or fill.side != direction:
                raise ValueError(f"wrong segment open: {fill.fill_id}")
            opened, volume = fill, fill.volume
        elif fill.reason == "add":
            if fill.side != direction or fill.epoch != opened.epoch:
                raise ValueError(f"addition does not match open segment: {fill.fill_id}")
            volume += fill.volume
        else:
            if (fill.reason not in ("roll_close", *FINAL_EXITS)
                    or fill.side != -direction or fill.epoch != opened.epoch or fill.volume != volume):
                raise ValueError(f"segment does not flatten: {fill.fill_id}")
            segments.append((opened, fill))
            opened = None
    if opened is not None:
        raise ValueError(f"unclosed segment: {opened.fill_id}")
    return segments


def episode_inputs(cycles, fills, sizing):
    by_cycle = {key: list(g.itertuples(index=False)) for key, g in fills.groupby("cycle", sort=False)}
    entry_sizing = None
    if sizing is not None:
        entry_sizing = sizing.loc[sizing.kind.eq("entry") & sizing.executed_lots.gt(0)].set_index(
            ["date", "product"], verify_integrity=True,
        )
    rows = []
    segment_counts = {}
    for c in cycles.itertuples(index=False):
        legs = by_cycle[c.cycle]
        first, last = legs[0], legs[-1]
        if (first.reason != "entry" or last.reason not in FINAL_EXITS
                or first.date != c.entry_day or last.date != c.exit_day):
            raise ValueError(f"invalid entry or final exit in cycle {c.cycle}")
        risk_per_lot = first.side * (first.price - float(first.stop)) * first.size
        if entry_sizing is not None:
            risk = entry_sizing.loc[first.date, first.product]
            if risk.executed_lots != first.volume or risk.price != first.price or risk.stop != float(first.stop):
                raise ValueError(f"invalid sizing in cycle {c.cycle}")
            risk_per_lot = float(risk.risk_per_lot)
        segment_counts[str(c.cycle)] = len(closed_segments(legs, c.direction))
        cash = sum(-f.side * f.volume * f.price * f.size - f.slippage - f.commission for f in legs)
        if not isclose(cash, c.net_pnl, abs_tol=1e-7):
            raise ValueError(f"cycle PnL mismatch: {c.cycle}")
        rows.append(dict(
            lot_id=str(c.cycle), open_trade_id=str(c.cycle), close_trade_id=str(last.fill_id),
            vt_symbol=first.contract, product=c.product, direction="long" if c.direction == 1 else "short",
            entry_date=first.date, exit_date=last.date, entry_price=first.price, exit_price=last.price,
            exit_reason=REASONS[last.reason], volume=first.volume, realized_pnl=c.net_pnl,
            risk_amount=risk_per_lot * first.volume if risk_per_lot > 0 else float("nan"),
            signal=first.signal_day,
        ))
    episodes = renderer._all_trade_episodes(pd.DataFrame(rows))
    episodes["draw_intraday"] = 0
    episodes["lot_count"] = episodes.open_trade_id.map(segment_counts)
    for row in episodes.itertuples():
        if row.lot_count > 1:
            episodes.loc[row.Index, ["price_change_pct", "price_change_label"]] = [
                float("nan"), "换月周期，首末价格不可直接比较",
            ]
    return episodes, by_cycle, entry_sizing


def held_sources(legs, calendar, exact):
    held = {}
    for opened, closed in closed_segments(legs, legs[0].side):
        start, end = pd.Timestamp(opened.date), pd.Timestamp(closed.date)
        for day in calendar[calendar.between(start, end)]:
            held[day] = opened.contract
    for f in legs:
        bar = exact.loc[f.epoch, pd.Timestamp(f.date)]
        if bar.vt_symbol != f.contract or bar.open != f.price:
            raise ValueError(f"fill and physical opening bar differ: {f.fill_id}")
    return held


def reversal_links(fills):
    """Pair consecutive close and open fills with a shared stop-week signal."""
    by_fill_id = {}
    for old, new in pairwise(fills.itertuples(index=False)):
        if (old.reason == "weekly_stop" and new.reason == "entry"
                and old.date == new.date and old.product == new.product
                and old.signal_day == new.signal_day and old.side == new.side and old.cycle != new.cycle):
            by_fill_id[old.fill_id] = new
            by_fill_id[new.fill_id] = old
    return by_fill_id


def annotate(record, legs, risk, exact, profile, add_sequences, reversals):
    meta = record["meta"]
    daily = record["daily"]
    x_by_date = dict(zip(daily["date"], daily["x"]))
    first, last = legs[0], legs[-1]
    if meta["entry_source"] != first.contract or meta["exit_source"] != last.contract:
        raise ValueError(f"wrong contract at endpoint: {meta['open_trade_id']}")
    meta["exit_marker_price"] = last.price
    meta["exit_contract"] = last.contract
    meta["exit_volume"] = last.volume
    events = []
    add_notes = []
    for f in legs:
        if f.reason in ("roll_open", "roll_close"):
            events.append(dict(x=x_by_date[f.date], price=f.price, symbol="diamond",
                               label=f"{f.date} {REASONS[f.reason]} {f.contract} ×{f.volume:g}手"))
        elif f.reason == "add":
            sequence = add_sequences.loc[f.cycle, f.signal_day]
            expected_action = "add_long" if f.side == 1 else "add_short"
            if (sequence["product"] != f.product or sequence["contract"] != f.contract
                    or sequence["action"] != expected_action
                    or not sequence["break_day"] < sequence["first_confirm_day"] < f.signal_day < f.date):
                raise ValueError(f"addition sequence mismatch: {f.fill_id}")
            detail = f"断档 {sequence['break_day']}，确认 {sequence['first_confirm_day']} 和 {f.signal_day}"
            label = f"{f.date} 加仓 {f.contract} @{f.price:g} ×{f.volume:g} 手"
            events.append(dict(x=x_by_date[f.date], price=f.price, symbol="square",
                               label=f"{label}（{detail}）"))
            add_notes.append(f"｜{label}（{detail}）")
    for f, label in ((first, "信号周初始止损"), (last, "周线退出触发价")):
        if f.stop != "" and f.signal_day in x_by_date:
            bar = exact.loc[f.epoch, pd.Timestamp(f.signal_day)]
            if bar.vt_symbol != f.contract:
                raise ValueError(f"wrong contract at signal: {f.fill_id}")
            events.append(dict(x=x_by_date[f.signal_day], price=float(f.stop), symbol="diamond-open",
                               label=f"{f.signal_day} {label} {f.contract}"))
    meta["event_markers"] = events
    meta["add_count"] = len(add_notes)
    reversal_notes = []
    for fill, field, caption in ((first, "reverse_from_cycle", "平旧后反手开仓"),
                                 (last, "reverse_to_cycle", "平仓后同日反手")):
        other = reversals.get(fill.fill_id)
        if other is not None:
            meta[field] = int(other.cycle)
            label = f"{caption} · 关联周期 {other.cycle} · {other.contract} {other.price:g}"
            events.append(dict(x=x_by_date[fill.date], price=fill.price, symbol="diamond",
                               label=f"{fill.date} {label}"))
            reversal_notes.append(f"｜{label}")
    crosses = ""
    if profile.include_overlap:
        if first.date < profile.start:
            crosses += "｜区间开始前已开仓"
        if last.date > profile.end:
            crosses += "｜区间结束后才平仓"
    elif last.date > profile.end:
        crosses = f"｜{profile.end[:4]} 年末仍持仓"
    exit_note = ""
    if (profile.include_overlap or profile.delivery_guard_days is not None) and last.reason == "weekly_stop":
        bar = exact.loc[last.epoch, pd.Timestamp(last.signal_day)]
        stop = float(last.stop)
        if bar.vt_symbol != last.contract or first.side * (bar.close - stop) > 0:
            raise ValueError(f"weekly exit evidence mismatch: {last.fill_id}")
        side_note = "≤ 前周最低价" if first.side == 1 else "≥ 前周最高价"
        exit_note = f"｜周线止损 {last.signal_day} 周收盘 {bar.close:g} {side_note} {stop:g}，{last.date} 开盘成交"
    elif last.reason == "delivery_guard_exit":
        if last.stop != "" or not last.signal_day <= last.date:
            raise ValueError(f"delivery guard exit evidence mismatch: {last.fill_id}")
        exit_note = f"｜到期保护窗口自 {last.signal_day} 起，{last.date} 首个有效开盘成交"
    one_price = "｜含一价成交代理" if any(f.one_price for f in legs) else ""
    if risk is None:
        nominal = first.side * (first.price - float(first.stop)) * first.size * first.volume
        risk_note = (
            f"｜初始名义风险 {nominal:,.2f} 元"
            if nominal > 0 else "｜开盘触及或越过初始止损，R 不可用"
        )
    else:
        risk_note = (
            f"｜开仓前可用现金 {float(risk.free_cash):,.2f} 元"
            f"｜风险预算 {float(risk.risk_budget):,.2f} 元"
            f"｜初始名义风险 {meta['volume'] * float(risk.risk_per_lot):,.2f} 元"
        )
    meta["episode_note"] = (
        f"周期 {first.cycle}｜{first.contract} 开仓 {first.price:g} ×{first.volume:g} 手"
        f"｜{first.signal_day} 信号周初始止损 {float(first.stop):g}{risk_note}{''.join(add_notes)}"
        f"｜换月 {meta['lot_count']-1} 次｜{last.contract} 平仓 {last.price:g} ×{last.volume:g} 手"
        f"{exit_note}{''.join(reversal_notes)}{crosses}{one_price}"
    )


def write(run, destination, profile=STAGE005):
    if destination.exists():
        raise FileExistsError(destination)
    inputs, metrics, cycles, fills, sizing, market, mapping = load(run, profile)
    closed, residual = partition_cycles(cycles, profile)
    episodes, by_cycle, risk_by_entry = episode_inputs(closed, fills, sizing)
    reversals = reversal_links(fills) if profile.reverse_after_stop else {}
    add_sequences = None
    if profile.max_fixed_adds:
        add_sequences = pd.read_csv(run / "add_sequences.csv", keep_default_na=False).set_index(
            ["cycle", "signal_day"], verify_integrity=True,
        )
    products = {product: g for product, g in mapping.groupby("continuous_symbol_vt", sort=False)}
    cache = {symbol: g for symbol, g in market.groupby("vt_symbol", sort=False)}
    empty_daily = market.iloc[:0]
    for symbol in mapping.main_contract_vt.unique():
        cache.setdefault(symbol, empty_daily)
    exact = market.set_index(["contract_epoch_id", "date"], verify_integrity=True)
    records, manifests = [], []
    empty_minutes = pd.DataFrame(columns=["vt_symbol"])
    for i, row in enumerate(episodes.itertuples(index=False)):
        key = row.open_trade_id
        legs = by_cycle[int(key)]
        calendar = products[row.product]
        held = held_sources(legs, calendar.date, exact)
        daily, window = renderer._context_daily(
            row, calendar, cache, allow_daily_download=False, allow_noncritical_daily_gaps=True,
            recover_local_minutes=False, data_end=pd.Timestamp(inputs["end"]), held_contract_by_day=held,
        )
        result, manifest = renderer._records(episodes.iloc[i:i+1], {key: daily}, {key: window}, empty_minutes)
        risk = risk_by_entry.loc[legs[0].date, legs[0].product] if risk_by_entry is not None else None
        annotate(result[0], legs, risk, exact, profile, add_sequences, reversals)
        meta = result[0]["meta"]
        for column in ("exit_contract", "exit_marker_price", "episode_note", "exit_volume", "add_count"):
            manifest[column] = meta[column]
        if profile.reverse_after_stop:
            for column in ("reverse_from_cycle", "reverse_to_cycle"):
                manifest[column] = meta.get(column, "")
        manifests.append(manifest)
        records.extend(result)
    manifest = pd.concat(manifests, ignore_index=True)
    counts = episodes.result_type.value_counts()
    gains, losses, flats = [int(counts.get(key, 0)) for key in ("profit", "loss", "flat")]
    cross = int(closed.exit_day.gt(profile.end).sum())
    carry_in = int(closed.entry_day.lt(profile.start).sum())
    selected_fills = fills.loc[fills.cycle.isin(closed.cycle)]
    add_count = int(selected_fills.reason.eq("add").sum())
    add_text = f"加仓成交 {add_count} 笔。" if profile.max_fixed_adds else ""
    reversal_count = int(manifest["reverse_from_cycle"].ne("").sum()) if profile.reverse_after_stop else 0
    reversal_text = f"其中 {reversal_count} 个周期由同日反手开仓。" if profile.reverse_after_stop else ""
    summary = dict(
        episode_scope="all", source_label=profile.label, source_version=profile.run, page_title=profile.title,
        source_warning="成交为日开盘代理。持仓前后为未经价差调整的主力背景，持仓段使用实际合约，换月日 K 线采用新合约。",
        coverage_note="按开仓年份筛选。提供 30日K、10日K、月K、周K、日K。冻结行情无15分钟数据，早期背景和均线预热按可用行情显示。",
        footer_scope=f"{len(records)} 个完整周期，{gains} 盈、{losses} 亏、{flats} 平，其中 {cross} 个跨统计期平仓。"
                     f"{add_text}{reversal_text}整周期净盈亏 {closed.net_pnl.sum():,.0f} 元。R 的分母为底仓初始名义风险。",
        rank_basis="realized_pnl", chart_episodes=len(records), chart_profit_episodes=gains,
        chart_loss_episodes=losses, chart_flat_episodes=flats, scoped_fills=len(selected_fills),
        scoped_add_fills=add_count,
        **({"scoped_reversal_entries": reversal_count} if profile.reverse_after_stop else {}),
        exit_after_scope=cross,
        scoped_closed_pnl=float(closed.net_pnl.sum()), residual_open_positions=residual.to_dict("records"),
        backtest_metrics=metrics, provenance=inputs, independent_audit_sha256=profile.audit_sha,
        bars_15m=0, intraday_draw_episodes=0,
        missing_context_days=sum(len(r["meta"]["missing_context_dates"]) for r in records),
        context_fallback_days=int(manifest.context_fallback_days.sum()),
        period_picker={"options": ["day30", "day10", "monthly", "weekly", "daily"],
                       "default_selected": ["day30", "daily"]},
    )
    if profile.include_overlap:
        daily = pd.read_csv(run / "daily.csv")
        scope = daily.loc[daily.date.between(profile.start, profile.end)]
        change = float(scope.net_pnl.sum())
        fills_in_window = int(fills.date.between(profile.start, profile.end).sum())
        summary.update(
            scope_overlap_start=profile.start, scope_overlap_end=profile.end,
            entries_before_scope=carry_in, scope_trading_days=len(scope), fills_in_window=fills_in_window,
            scope_equity_before=float(scope.equity.iloc[0] - scope.net_pnl.iloc[0]),
            scope_equity_end=float(scope.equity.iloc[-1]), scope_equity_change=change,
            coverage_note=f"按持仓区间与红框重叠筛选，含区间前开仓及区间后平仓。"
                          f"区间内权益变化 {change:+,.0f} 元，成交 {fills_in_window} 笔（含换月）。"
                          "图上盈亏和标记对应完整持仓周期。冻结行情无15分钟数据。",
            footer_scope=f"{len(records)} 个完整周期，{gains} 盈、{losses} 亏、{flats} 平。"
                         f"{carry_in} 个区间前开仓，{cross} 个区间后平仓。"
                         f"未完成周期 {len(residual)} 个。{reversal_text}"
                         f"完整周期净盈亏 {closed.net_pnl.sum():+,.0f} 元。"
                         "R 的分母为底仓初始名义风险。",
        )
    else:
        summary.update(scope_entry_start=profile.start, scope_entry_end=profile.end)
    if profile.delivery_guard_days is not None:
        calendar_pnl = float(pd.read_csv(run / "annual.csv").set_index("date").loc[int(profile.start[:4]), "net_pnl"])
        long_count = int(closed.direction.eq(1).sum())
        guard_count = int(selected_fills.reason.eq("delivery_guard_exit").sum())
        summary.update(
            scoped_long_cycles=long_count, scoped_short_cycles=len(closed) - long_count,
            scoped_delivery_guard_exits=guard_count, calendar_year_pnl=calendar_pnl,
        )
        summary["footer_scope"] += (
            f"做多 {long_count} 笔，做空 {len(closed) - long_count} 笔，"
            f"到期保护平仓 {guard_count} 笔。另按日历年计算，2022 年组合权益变化 {calendar_pnl:+,.0f} 元。"
        )
    if profile.manifest_sha:
        summary["frozen_manifest_sha256"] = profile.manifest_sha
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "index.html").write_text(renderer._html(records, summary))
    (destination / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    manifest.to_csv(destination / "chart_manifest.csv", index=False)
    selected_fills.to_csv(destination / "scoped_fills.csv", index=False)
    return destination / "index.html"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    profiles = {"stage005": STAGE005, "stage007-2022": STAGE007_2022,
                "stage013-2022": STAGE013_2022, "stage018-2022": STAGE018_2022,
                "stage025-s44-2022": STAGE025_S44_2022, **WINDOW_PROFILES}
    parser.add_argument("--profile", choices=profiles, default="stage005")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    profile = profiles[args.profile]
    print(write(LINE / "outputs" / profile.run, args.output or profile.destination, profile))
