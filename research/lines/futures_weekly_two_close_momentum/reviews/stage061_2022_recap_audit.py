"""Independently check Stage061's annual frozen-source recap; never rerun strategy."""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from stage040_s19_without_gold_audit import ADMITTED, cents
from stage048_s26_tail_audit import APPROVED
from stage055_all_touch_audit import TAIL_CERT, check_manifest, completed_weeks, extend_raw_market, load_json, sha, table

LINE = Path(__file__).resolve().parents[1]
ROOT = LINE / "outputs/stage060_s21_200k_touch_halfyear_20261104"
RUN = ROOT / "S21_20w/2022-01-01"
OUTPUT = LINE.parent / "futures_trend_winner_trade_forensics/outputs/stage061_s21_200k_touch_2022_recap_v1"
DESIGN = LINE / "stages/20261105_1336_stage061_2022_recap_design.md"
CERTIFICATE = LINE / "reviews/stage060_s21_200k_audit.json"
EXPECTED_MANIFEST = "c8bff538f87f7625fa446c4eb710d5e1e8d1d7f05a5b8926ccdee557150d18cf"
EXPECTED_AUDIT = "a378b07df043792469b5e3f07748ed153d1645c620e4d47b32b321a7f80450bb"
LABELS = {
    "touch_open_gap": "开盘跳空触价止损", "touch_intraday": "盘中触价止损",
    "touch_after_one_price": "一价后延迟止损", "delivery_guard_exit": "到期保护平仓",
    "roll_funding_exit": "换月资金不足退出",
}


def extract_json(page, token):
    begin = page.index(token) + len(token)
    return json.JSONDecoder().raw_decode(page[begin:])[0]


def raw_volumes(products):
    output = {}
    for path in (ADMITTED / "physical_epoch_daily.csv", APPROVED / "added_bars.csv"):
        data = pd.read_csv(path, usecols=["date", "vt_symbol", "volume"])
        data = data.loc[data.date.le("2023-12-31")]
        data = data.loc[data.vt_symbol.str.replace(r"\d+", "", regex=True).isin(products)]
        for row in data.itertuples(index=False):
            key = row.date, row.vt_symbol
            assert key not in output
            output[key] = row.volume
    return output


def audit_source():
    assert sha(ROOT / "SHA256SUMS") == EXPECTED_MANIFEST
    assert sha(CERTIFICATE) == EXPECTED_AUDIT
    manifest_count = check_manifest(ROOT)
    audit = load_json(CERTIFICATE)
    assert audit["verdict"] == "PASS_WITH_LIMITATIONS"
    assert audit["result_manifest_sha256"] == EXPECTED_MANIFEST
    inputs, summary = load_json(RUN / "inputs.json"), load_json(RUN / "summary.json")
    assert (inputs["initial"], inputs["start"], summary["start"], summary["end"], summary["days"]) == (
        200000, "2022-01-01", "2022-01-04", "2026-11-04", 1170,
    )
    assert summary["equity"] == 806115 and (summary["closed_cycles"], summary["open_positions"], summary["fills"]) == (1022, 12, 2376)
    cycles, fills, daily, sizing = (table(RUN, name) for name in ("cycles", "fills", "daily", "risk_sizing"))
    fills.insert(0, "fill_id", fills.index + 1)
    selected = cycles.loc[cycles.entry_day.between("2022-01-01", "2022-12-31")]
    assert (len(selected), selected.exit_day.eq("").sum(), selected.net_pnl.gt(0).sum(), selected.net_pnl.lt(0).sum()) == (167, 0, 52, 115)
    assert selected.net_pnl.sum() == 40080
    scope_fills = fills.loc[fills.cycle.isin(selected.cycle)]
    assert len(scope_fills) == 360
    assert sizing.loc[sizing.date.str.startswith("2022")].executed_lots.eq(1).all()
    assert (daily.loc[daily.date.str.startswith("2022"), "net_pnl"].sum(),
            daily.loc[daily.date.str.startswith("2022"), "equity"].iat[-1]) == (38980, 238980)
    market = extend_raw_market(load_json(TAIL_CERT))
    by_epoch = market[4]
    contributions, segment_counts = {}, {}
    for cycle in selected.itertuples(index=False):
        legs = scope_fills.loc[scope_fills.cycle.eq(cycle.cycle)]
        first, last = legs.iloc[0], legs.iloc[-1]
        assert first.date == cycle.entry_day and last.date == cycle.exit_day and first.reason == "entry"
        assert last.reason in LABELS and first.side == cycle.direction and last.side == -cycle.direction
        exposure, flow, annual_flow, year_exposure = 0, 0, 0, {}
        epoch, size, segments = None, None, 0
        for leg in legs.itertuples(index=False):
            bar = by_epoch[leg.date, leg.epoch]
            assert bar.symbol == leg.contract and leg.volume == 1 and not leg.one_price
            assert leg.size == market[5]["sizes"][leg.contract]
            if leg.reason in ("entry", "roll_open"):
                assert exposure == 0 and leg.side == cycle.direction
                epoch, size = leg.epoch, leg.size
                segments += 1
            else:
                assert exposure == cycle.direction and leg.epoch == epoch and leg.size == size
            exposure += leg.side
            assert exposure in (0, cycle.direction)
            money = -leg.side * leg.volume * cents(leg.price) * leg.size - cents(leg.slippage) - cents(leg.commission)
            flow += money
            if leg.date <= "2022-12-30":
                annual_flow += money
                year_exposure[leg.epoch] = year_exposure.get(leg.epoch, 0) + leg.side * leg.volume * leg.size
            if leg.reason != "touch_intraday":
                assert cents(leg.price) == bar.op
            else:
                assert bar.low <= cents(leg.price) <= bar.high
        assert exposure == 0 and flow == cents(cycle.net_pnl)
        contributions[cycle.cycle] = (annual_flow + sum(quantity * by_epoch["2022-12-30", epoch].close
                                                      for epoch, quantity in year_exposure.items() if quantity)) / 100
        segment_counts[cycle.cycle] = segments
    assert sum(contributions.values()) == 38980
    cross = selected.loc[selected.exit_day.gt("2022-12-31")].to_dict("records")
    assert {(row["cycle"], row["exit_day"]) for row in cross} == {(156, "2023-02-06"), (166, "2023-01-03")}
    return inputs, summary, selected, scope_fills, contributions, segment_counts, market, manifest_count


def period_frames(frame):
    result = {"daily": frame.copy()}
    for name, key in (("weekly", frame.date.dt.to_period("W-FRI").astype(str)),
                      ("monthly", frame.date.dt.to_period("M").astype(str)),
                      ("day10", frame.calendar_index // 10), ("day30", frame.calendar_index // 30)):
        grouped = frame.assign(bucket=key).groupby("bucket", sort=True)
        result[name] = grouped.agg(date_start=("date", "first"), date_end=("date", "last"),
                                   open=("open", "first"), high=("high", "max"), low=("low", "min"),
                                   close=("close", "last"), volume=("volume", "sum"), day_count=("date", "size"))
    for name, values in result.items():
        for length in (5, 10, 20, 40):
            values[f"ma{length}"] = values.close.rolling(length, min_periods=length).mean()
    return result


def audit_chart(record, legs, market, volumes):
    meta, observed = record["meta"], record["daily"]
    product = meta["product"]
    # The admitted display feed starts in 2014. Its fixed 10/30-day buckets
    # use that frozen product calendar, rather than pre-2014 mapping-only rows.
    calendar = sorted(day for day, item in market[2]
                      if item == product and "2014-01-01" <= day <= "2026-11-04")
    entry, exit_day = meta["entry_date"], meta["exit_date"]
    expected_visible = calendar[max(0, calendar.index(entry) - 300):calendar.index(exit_day) + 51]
    held, opened = {}, None
    for leg in legs.itertuples(index=False):
        if leg.reason in ("entry", "roll_open"):
            opened = leg
        else:
            assert opened is not None
            for day in calendar:
                if opened.date <= day <= leg.date:
                    held[day] = opened.contract
            opened = None
    assert opened is None
    start = record["day30"]["label"][0].split("~")[0]
    end = record["day30"]["label"][-1].split("~")[1][:10]
    raw_rows, missing, fallback = [], [], []
    for number, day in enumerate(calendar):
        if day > end:
            continue
        source = held.get(day, market[2][day, product])
        bar = market[3].get((day, source))
        if bar is None:
            if day in expected_visible:
                missing.append(day)
            continue
        raw_rows.append(dict(date=pd.Timestamp(day), calendar_index=number, source=source,
                             open=bar.op / 100, high=bar.high / 100, low=bar.low / 100, close=bar.close / 100,
                             volume=volumes[day, source]))
        if day not in held and day in expected_visible:
            fallback.append(day)
    all_history = pd.DataFrame(raw_rows)
    frame = all_history.loc[all_history.date.ge(start)].reset_index(drop=True)
    assert observed["date"] == [day for day in expected_visible if day not in missing]
    assert meta["context_fallback_dates"] == fallback
    assert set(missing) <= set(meta["missing_context_dates"])
    frames = period_frames(frame)
    complete_history_frames = period_frames(all_history)
    checks = Counter()
    for name in ("daily", "weekly", "monthly", "day10", "day30"):
        values = frames[name]
        if name == "daily":
            index = values.date.dt.strftime("%Y-%m-%d")
        elif name in ("weekly", "monthly"):
            index = values.index.astype(str)
        else:
            length = 10 if name == "day10" else 30
            index = [f"{row.date_start.date()}~{row.date_end.date()} {row.day_count}/{length}日"
                     for row in values.itertuples()]
        indexed = values.set_index(pd.Index(index), verify_integrity=True)
        payload = record[name]
        labels = payload["date"] if name == "daily" else payload["label"]
        assert set(labels) <= set(indexed.index), (meta["open_trade_id"], name, list(set(labels) - set(indexed.index))[:5], start, end)
        selected = indexed.loc[labels]
        for field in ("open", "high", "low", "close", "volume", "ma5", "ma10", "ma20", "ma40"):
            expected = selected[field].to_numpy(dtype=float)
            actual = np.array([np.nan if value is None else value for value in payload[field]])
            np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-7, equal_nan=True,
                                       err_msg=f"{meta['open_trade_id']} {name} {field}")
            checks[f"{name}_values"] += len(actual)
        assert len(payload["x"]) == len(labels)
        if name == "daily":
            assert selected.source.tolist() == payload["source"]
            x_by_date = dict(zip(labels, payload["x"]))
            assert meta["entry_x"] == x_by_date[entry] and meta["exit_x"] == x_by_date[exit_day]
        else:
            assert len(payload["width"]) == len(labels)
        visible = [i for i, x in enumerate(payload["x"]) if meta["chart_x_start"] <= x <= meta["chart_x_end"]]
        checks[f"{name}_visible_ma40_nulls"] += sum(payload["ma40"][i] is None for i in visible)
        full = complete_history_frames[name].copy()
        full_index = full.date if name == "daily" else full.date_end
        full = full.set_index(pd.Index(full_index), verify_integrity=True)
        date_keys = selected.date if name == "daily" else selected.date_end
        full = full.loc[date_keys.iloc[visible]]
        for length in (5, 10, 20, 40):
            actual = np.array([np.nan if payload[f"ma{length}"][i] is None else payload[f"ma{length}"][i]
                               for i in visible])
            np.testing.assert_allclose(actual, full[f"ma{length}"], rtol=0, atol=1e-7, equal_nan=True,
                                       err_msg=f"{meta['open_trade_id']} {name} avoidable warmup truncation")
            checks["visible_ma_values_against_all_history"] += len(actual)
    assert not record["intraday"]["x"] and meta["draw_intraday"] == 0
    assert meta["monthly_start"] == str(pd.Timestamp(entry).to_period("M") - 10)
    assert meta["monthly_end"] == str(pd.Timestamp(exit_day).to_period("M") + 10)
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--certificate", type=Path)
    args = parser.parse_args()
    inputs, source_metrics, selected, fills, contributions, segments, market, manifest_count = audit_source()
    print("SOURCE", len(selected), len(fills), selected.net_pnl.sum(), sum(contributions.values()), flush=True)
    if args.source_only:
        return
    page = (OUTPUT / "index.html").read_text()
    output_files_checked = check_manifest(OUTPUT)
    receipt = load_json(OUTPUT / "receipt.json")
    assert receipt["source_manifest_sha256"] == EXPECTED_MANIFEST
    assert receipt["source_audit_sha256"] == EXPECTED_AUDIT
    assert receipt["entrypoint_sha256"] == sha(LINE / "tools/stage061_2022_recap.py")
    assert receipt["prior_adapter_sha256"] == sha(LINE / "tools/stage054_trade_recap.py")
    assert receipt["renderer_sha256"] == sha(LINE.parent / "futures_trend_winner_trade_forensics/tools/stage038_c9_15w_big_winner_multiscale_html.py")
    assert not any(receipt[name] for name in ("strategy_rerun", "market_download", "production_access"))
    records, embedded_summary = extract_json(page, "const records="), extract_json(page, "const summary=")
    summary = load_json(OUTPUT / "summary.json")
    assert embedded_summary == summary
    assert summary["backtest_metrics"] == source_metrics and summary["provenance"] == inputs
    assert summary["frozen_manifest_sha256"] == EXPECTED_MANIFEST
    assert summary["independent_audit_sha256"] == EXPECTED_AUDIT
    assert summary["chart_episodes"] == 167 and (summary["chart_profit_episodes"], summary["chart_loss_episodes"], summary["chart_flat_episodes"]) == (52, 115, 0)
    assert summary["scoped_closed_pnl"] == 40080 and summary["bars_15m"] == 0
    assert (summary["calendar_year_pnl"], summary["calendar_year_end_equity"], summary["exit_after_scope"], summary["scoped_fills"], summary["rejected_opening_orders"]) == (38980, 238980, 2, 360, 0)
    assert summary["residual_open_positions"] == [] and len(summary["source_residual_open_positions"]) == 12
    assert summary["calendar_year_return_pct"] == 19.49
    expected_residual = table(RUN, "cycles").loc[lambda frame: frame.exit_day.eq("")].to_dict("records")
    assert summary["source_residual_open_positions"] == expected_residual
    assert summary["period_picker"] == {"options": ["day30", "day10", "monthly", "weekly", "daily"], "default_selected": ["day30", "daily"]}
    pd.testing.assert_frame_equal(table(OUTPUT, "scoped_fills"), fills.reset_index(drop=True), check_dtype=False)
    manifest = table(OUTPUT, "chart_manifest").set_index("open_trade_id", verify_integrity=True)
    annual = table(OUTPUT, "annual_contributions").set_index("cycle", verify_integrity=True)
    assert len(annual) == 167 and annual.calendar_year_pnl.sum() == 38980
    assert len(records) == len(manifest) == 167
    assert {int(record["meta"]["open_trade_id"]) for record in records} == set(selected.cycle)
    volumes, counts = raw_volumes(inputs["products"]), Counter()
    weeks, week_index, weekly_bar = completed_weeks(market[1], market[4])
    source_stops = table(RUN, "touch_stops").set_index("cycle", verify_integrity=True)
    signals, sizing = table(RUN, "signals"), table(RUN, "risk_sizing")
    for record in records:
        meta = record["meta"]
        number = int(meta["open_trade_id"])
        cycle = selected.loc[selected.cycle.eq(number)].iloc[0]
        legs = fills.loc[fills.cycle.eq(number)]
        first, last = legs.iloc[0], legs.iloc[-1]
        expected = dict(product=cycle["product"], direction="long" if cycle.direction == 1 else "short",
                        entry_date=first.date, exit_date=last.date, entry_price=first.price, exit_price=last.price,
                        realized_pnl=cycle.net_pnl, volume=1, lot_count=segments[number],
                        entry_source=first.contract, exit_source=last.contract, entry_marker_price=first.price,
                        exit_marker_price=last.price, exit_contract=last.contract, exit_volume=1,
                        calendar_year_pnl=contributions[number])
        for field, value in expected.items():
            assert meta[field] == value, (number, field, meta[field], value)
            assert manifest.at[number, field] == value, (number, "manifest", field)
        assert meta["result_type"] == ("profit" if cycle.net_pnl > 0 else "loss")
        nominal = first.side * (first.price - float(first.stop)) * first["size"]
        if nominal > 0:
            assert abs(meta["r_multiple"] - cycle.net_pnl / nominal) < 1e-8
        else:
            assert meta["r_multiple"] is None
        if segments[number] == 1:
            assert abs(meta["price_change_pct"] - (last.price / first.price - 1) * 100) < 1e-8
        else:
            assert meta["price_change_pct"] is None
        signal = signals.loc[signals.date.eq(first.signal_day) & signals["product"].eq(first["product"])
                             & signals.epoch.eq(first.epoch) & signals.action.eq("open_long" if first.side == 1 else "open_short")]
        funding = sizing.loc[sizing.date.eq(first.date) & sizing["product"].eq(first["product"])
                            & sizing.executed_lots.eq(1) & sizing.kind.isin(("fixed_entry", "reversal"))]
        assert len(signal) == len(funding) == 1
        signal = signal.iloc[0]
        index = week_index[first.signal_day]
        assert weeks[index][-1] == first.signal_day
        source_weeks = [weekly_bar(first.epoch, index - offset) for offset in range(3)]
        assert all(source_weeks)
        current, prior, older = source_weeks
        assert [cents(signal[field]) for field in ("close", "prior_close", "older_close")] == [current.close, prior.close, older.close]
        assert first.side * (current.close - prior.close) > 0 and first.side * (prior.close - older.close) > 0
        assert all(first.side * (bar.close - bar.op) > 0 for bar in (current, prior))
        assert cents(float(first.stop)) == (current.low if first.side == 1 else current.high)
        note = meta["episode_note"]
        assert annual.at[number, "calendar_year_pnl"] == contributions[number]
        assert annual.at[number, "net_pnl"] == cycle.net_pnl
        assert f"2022年贡献 {contributions[number]:+,.0f}" in note
        assert f"完整周期净损益 {cycle.net_pnl:+,.0f}" in note
        for field in ("older_close", "prior_close", "close"):
            assert f"{signal[field]:g}" in note
        assert f"{funding.iloc[0].free_cash:,.2f}" in note
        assert f"{funding.iloc[0].margin_per_lot + funding.iloc[0].entry_cost_per_lot:,.2f}" in note
        assert first.signal_day in note and first.contract in note and last.contract in note and last.date in note
        assert meta["exit_reason"] and "周线止损" not in meta["exit_reason"]
        if last.reason.startswith("touch_"):
            stop = source_stops.loc[number]
            assert (stop.date, stop.contract, stop.price, stop.reason, stop.anchor_day, stop.stop) == (
                last.date, last.contract, last.price, last.reason, last.signal_day, float(last.stop))
            assert stop.anchor_day < stop.trigger_day <= stop.date
            reference = weekly_bar(last.epoch, week_index[stop.anchor_day])
            assert reference and cents(stop.stop) == (reference.low if first.side == 1 else reference.high)
            assert weeks[week_index[stop.anchor_day]][-1] == stop.anchor_day
            actual_bar = market[4][stop.date, stop.epoch]
            assert [cents(stop[field]) for field in ("open", "high", "low")] == [actual_bar.op, actual_bar.high, actual_bar.low]
            through = first.side * (actual_bar.op - cents(stop.stop)) <= 0
            extreme = actual_bar.low if first.side == 1 else actual_bar.high
            assert first.side * (extreme - cents(stop.stop)) <= 0
            assert cents(stop.price) == (actual_bar.op if through or last.reason == "touch_after_one_price" else cents(stop.stop))
            assert stop.anchor_day in note and stop.trigger_day in note
            for field in ("stop", "open", "high", "low", "price"):
                assert f"{stop[field]:g}" in note
            assert any(event["price"] == stop.stop and stop.date in event["label"]
                       for event in meta["event_markers"])
            if first["product"] != "au.SHFE":
                assert "黄金" not in note and "元/克" not in note
        counts.update(audit_chart(record, legs, market, volumes))
        counts[f"exit:{last.reason}"] += 1
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", page, re.S)
    checked_scripts = 0
    for script in scripts:
        if not script.strip():
            continue
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js") as stream:
            stream.write(script)
            stream.flush()
            node = shutil.which("node") or "/opt/homebrew/bin/node"
            subprocess.run([node, "--check", stream.name], check=True, capture_output=True, text=True)
        checked_scripts += 1
    assert "selectedPeriods" in page and "plotly_relayout" in page and "xaxis" in page
    result = dict(
        schema="stage061_independent_2022_recap_audit_v1", verdict="PASS_WITH_LIMITATIONS",
        audited_at=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        audit_script_sha256=sha(Path(__file__)), source_manifest_sha256=EXPECTED_MANIFEST,
        source_audit_sha256=EXPECTED_AUDIT, source_manifest_files_checked=manifest_count,
        output_manifest_files_checked=output_files_checked, design_sha256=sha(DESIGN),
        source_run=str(RUN), output=str(OUTPUT), source_metrics=source_metrics,
        verified_episodes=167, verified_fills=360, profit_loss_flat=[52, 115, 0],
        scoped_full_pnl=40080, calendar_2022_pnl=38980, calendar_year_end_equity=238980,
        by_cycle_calendar_contribution=contributions, cross_year_cycles=[156, 166],
        output_hashes={str(path.relative_to(OUTPUT)): sha(path) for path in OUTPUT.iterdir() if path.is_file()},
        chart_checks=dict(counts), scripts_syntax_checked=checked_scripts,
        limitations=["Display-only audit; no new strategy replay, market download or production access.",
                     "Daily OHLC touch exits are simulation proxies; no minute execution proof.",
                     "Background uses unadjusted daily-main prices and does not define strategy rules.",
                     "Real browser navigation and zoom validation is performed separately by the producer."],
    )
    print("CHARTS", counts, "SCRIPTS", checked_scripts, flush=True)
    if args.certificate:
        with args.certificate.open("x") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2, default=lambda value: value.item())
            stream.write("\n")


if __name__ == "__main__":
    main()
