"""Targeted, independent Stage269 audit. Never writes source datasets.

The reviewer does not import either market or statistics implementation. Source
windows are reconstructed only at five frozen dates, not as a second full run.
"""
from __future__ import annotations

import hashlib
import json
import argparse
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd


LINE = Path(__file__).resolve().parents[1]
OUTPUT = LINE / "outputs/stage269_market_efficiency_validation"
REVIEW = OUTPUT / "review"
TARGET_DATES = ("2020-01-02", "2021-03-01", "2023-06-30", "2025-09-01", "2026-10-14")


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_fingerprints():
    frozen = json.loads((LINE / "outputs/stage268_market_efficiency_design/design_inputs.json").read_text())
    rows = []
    for item in frozen["source_files"]:
        path = Path(item["path"])
        actual = digest(path)
        rows.append(dict(logical_name=item["logical_name"], actual_sha256=actual,
                         matches_frozen=actual == item["sha256"], bytes=path.stat().st_size))
    item = frozen["market_clean_reference"]
    path = Path(item["path"])
    actual = digest(path)
    rows.append(dict(logical_name="stage266_clean_daily.sqlite", actual_sha256=actual,
                     matches_frozen=actual == item["sha256_from_accepted_stage266"], bytes=path.stat().st_size))
    return rows


def independent_market_sentinels():
    contract = json.loads((LINE / "outputs/stage266_clean_daily/contract.json").read_text())
    cal_path = Path(contract["calendar_path"])
    assert digest(cal_path) == contract["calendar_sha256"]
    calendar = pd.DatetimeIndex(pd.to_datetime(np.load(cal_path, allow_pickle=False).astype(str), format="%Y%m%d"))
    cal_position = {d: i for i, d in enumerate(calendar)}
    db = LINE / "outputs/stage266_clean_daily/clean_daily.sqlite"
    con = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    first = pd.read_sql_query("SELECT exchange,product,MIN(trade_date) first_date FROM daily_bars "
                              "WHERE quality_status='accepted' GROUP BY exchange,product", con)
    first = first.loc[~first["product"].str.endswith("_F")]
    first["product_id"] = first.exchange + "." + first["product"]
    first["first_index"] = pd.to_datetime(first.first_date).map(cal_position)
    first_index = first.set_index("product_id").first_index.to_dict()
    universe = sorted(first_index)
    records = []
    for target in TARGET_DATES:
        day = pd.Timestamp(target)
        at = cal_position[day]
        dates = calendar[at-120:at+1]
        bars = pd.read_sql_query("SELECT trade_date,exchange,product,contract_epoch_id,close,volume,close_oi "
                                 "FROM daily_bars WHERE trade_date BETWEEN ? AND ? AND quality_status='accepted'", con,
                                 params=(dates[0].strftime("%Y-%m-%d"), target))
        bars = bars.loc[~bars["product"].str.endswith("_F")].copy()
        bars["date"] = pd.to_datetime(bars.trade_date)
        bars["product_id"] = bars.exchange + "." + bars["product"]
        # Direct endpoint lookup uses an exact epoch; it never uses today's OI.
        endpoint = bars.set_index(["date", "contract_epoch_id"])["close"].to_dict()
        eligible = bars.loc[(bars.close > 0) & (bars.volume > 0) & np.isfinite(bars.close_oi) & (bars.close_oi >= 0)]
        selected = eligible.sort_values(["date", "product_id", "close_oi", "volume", "contract_epoch_id"],
                                        ascending=[True, True, False, False, True]).drop_duplicates(["date", "product_id"])
        selected = selected.loc[selected.close_oi > 0].set_index(["date", "product_id"])
        active_ids = set(bars.loc[bars.date.isin(dates[-20:]) & (bars.volume > 0), "product_id"])
        for pid in universe:
            r = []
            reference = ""
            status = ""
            for previous, current in zip(dates[:-1], dates[1:]):
                key = (previous, pid)
                if key not in selected.index:
                    value = np.nan
                    status = "missing_previous_reference"
                    reference = ""
                else:
                    source = selected.loc[key]
                    reference = source.contract_epoch_id
                    current_close = endpoint.get((current, reference), np.nan)
                    value = np.log(current_close / source.close) if np.isfinite(current_close) and current_close > 0 else np.nan
                    status = "ok" if np.isfinite(value) else "missing_current_bar"
                r.append(value)
            def er(window):
                values = np.asarray(r[-window:])
                if len(values) != window or not np.isfinite(values).all():
                    return np.nan
                den = abs(values).sum()
                return abs(values.sum()) / den if den else 0.0
            records.append(dict(date=target, product_id=pid, r=r[-1], er20=er(20), er60=er(60), er120=er(120),
                                active=pid in active_ids and at-first_index[pid] >= 61,
                                reference_epoch=reference, sentinel_return_status=status))
    con.close()
    return pd.DataFrame(records)


def independent_source_trade_checks():
    source = LINE / "outputs/stage251_half_r_ab/A_final3"
    daily = pd.read_csv(source / "daily.csv")
    episodes = pd.read_csv(source / "statistics_audit/complete_episodes.csv")
    cycles = pd.read_csv(source / "statistics_audit/complete_cycles.csv")
    open_episodes = pd.read_csv(source / "statistics_audit/open_episodes.csv")
    result = dict(daily_rows=len(daily), fills=len(pd.read_csv(source / "trades.csv")),
                  closed_parent_episodes=len(episodes), closed_cycles=len(cycles),
                  retries=len(pd.read_csv(source / "statistics_audit/retry_links.csv")),
                  open_parent_episodes=len(open_episodes), open_parent_net_mtm=float(open_episodes.net_mtm.sum()),
                  source_equity_end=float(daily.account_equity.iloc[-1]),
                  daily_net_reconciles_to_equity=bool(np.allclose(daily.account_equity, 150000 + daily.net_pnl.cumsum())),
                  closed_cycles_reconcile_to_parent=bool(np.allclose(cycles.groupby("root_id").net_pnl.sum().reindex(episodes.root_id), episodes.net_pnl)))
    return result


def compare_market_artifacts():
    sentinels = pd.read_csv(REVIEW / "independent_market_sentinels.csv")
    features = pd.read_csv(OUTPUT / "market/product_features.csv.gz")
    daily = pd.read_csv(OUTPUT / "market/market_daily.csv", keep_default_na=False)
    mapping = json.loads((OUTPUT / "market/product_sectors.json").read_text())
    sectors = mapping["product_sectors"]
    merged = sentinels.merge(features, on=["date", "product_id"], suffixes=("_ind", "_impl"), validate="one_to_one")
    numerical = {}
    for column in ("r", "er20", "er60", "er120"):
        left, right = merged[column+"_ind"], merged[column+"_impl"]
        numerical[column] = dict(mismatches=int((~np.isclose(left, right, atol=1e-12, rtol=1e-11, equal_nan=True)).sum()),
                                 max_absolute_error=float(np.nanmax(abs(left-right))))
    numerical["active_mismatches"] = int((merged.active_ind != merged.active_impl).sum())
    numerical["reference_epoch_mismatches"] = int((merged.reference_epoch_ind.fillna("") != merged.reference_epoch_impl.fillna("")).sum())
    gate_rows = []
    for day, group in features.groupby("date", sort=True):
        active = group.loc[group.active]
        valid = active.loc[active.er60.notna()]
        act_sector = active.product_id.map(sectors).value_counts()
        val_sector = valid.product_id.map(sectors).value_counts().reindex(act_sector.index, fill_value=0)
        coverage = len(valid) / len(active) if len(active) else np.nan
        gate = (len(active) > 0 and coverage >= .9 and
                (~valid.product_id.str.startswith("CFFEX.")).sum() >= 15 and
                (val_sector > 0).sum() >= 5 and (val_sector / act_sector >= .8).all())
        gate_rows.append(dict(date=day, gate_pass=gate,
                              market_er60=float(valid.er60.median()) if gate else np.nan,
                              raw_market_er60=float(valid.er60.median()) if len(valid) else np.nan,
                              active_products=len(active), valid_products=len(valid), coverage_ratio=coverage))
    gates = pd.DataFrame(gate_rows)
    merged_gate = gates.merge(daily, on="date", suffixes=("_ind", "_impl"), validate="one_to_one")
    gate_checks = {}
    for column in ("market_er60", "raw_market_er60", "active_products", "valid_products", "coverage_ratio"):
        l = pd.to_numeric(merged_gate[column+"_ind"], errors="coerce")
        r = pd.to_numeric(merged_gate[column+"_impl"], errors="coerce")
        gate_checks[column] = int((~np.isclose(l, r, atol=1e-12, rtol=1e-11, equal_nan=True)).sum())
    gate_checks["gate_pass"] = int((merged_gate.gate_pass_ind != merged_gate.gate_pass_impl).sum())
    values = pd.to_numeric(daily.market_er60, errors="coerce").to_numpy()
    expected_pct, expected_regime, history = [], [], []
    for value in values:
        if np.isfinite(value) and len(history) >= 252:
            prior = np.asarray(history)
            rank = ((prior < value).sum() + .5 * (prior == value).sum()) / len(prior)
            expected_pct.append(rank)
            expected_regime.append("low" if rank <= 1/3 else "mid" if rank <= 2/3 else "high")
        else:
            expected_pct.append(np.nan)
            expected_regime.append("")
        if np.isfinite(value):
            history.append(value)
    pcts = pd.to_numeric(daily.er60_expanding_pct, errors="coerce").to_numpy()
    rank_checks = dict(percentile_mismatches=int((~np.isclose(expected_pct, pcts, atol=1e-12, equal_nan=True)).sum()),
                       regime_mismatches=int((np.asarray(expected_regime) != daily.regime.to_numpy()).sum()))
    summary = json.loads((OUTPUT / "market/market_summary.json").read_text())
    file_hash_checks = {name: digest(OUTPUT/"market"/name) == expected for name, expected in summary["output_sha256"].items()}
    return dict(source_sentinel_rows=len(merged), source_sentinel_numerics=numerical,
                all_calendar_aggregation_mismatches=gate_checks, prior_only_rank_checks=rank_checks,
                output_hash_checks=file_hash_checks, fixed_sector_count=len(mapping["sectors"]),
                mapping_has_94_products=len(sectors) == 94,
                main_source_days=int((daily.date >= "2020-01-02").sum()),
                main_gate_pass_days=int(daily.loc[daily.date >= "2020-01-02", "gate_pass"].sum()),
                main_classified_days=int(daily.loc[daily.date >= "2020-01-02", "regime"].ne("").sum()),
                first_classified=daily.loc[daily.regime.ne(""), "date"].min())


def independent_outcomes_and_main_effect():
    source = pd.read_csv(LINE / "outputs/stage251_half_r_ab/A_final3/daily.csv")
    market = pd.read_csv(OUTPUT / "market/market_daily.csv", keep_default_na=False)
    # Source-calendar completeness was separately established from the frozen
    # source-calendar file, not assumed by silently deleting equity rows.
    contract = json.loads((LINE / "outputs/stage266_clean_daily/contract.json").read_text())
    calendar = pd.to_datetime(np.load(contract["calendar_path"], allow_pickle=False).astype(str), format="%Y%m%d")
    expected_dates = calendar[(calendar >= pd.Timestamp(source.date.min())) & (calendar <= pd.Timestamp(source.date.max()))]
    assert list(source.date) == list(expected_dates.strftime("%Y-%m-%d"))
    eq = source.account_equity.to_numpy()
    cash = source.net_pnl.to_numpy()
    slip = source.slippage.to_numpy()
    prior_eq = np.r_[150000.0, eq[:-1]]
    simple = eq/prior_eq - 1
    expected = pd.DataFrame(dict(date=source.date, future20_return=np.nan, future20_cash=np.nan,
                                 future20_profit=np.nan, future20_slippage=np.nan,
                                 past60_vol=np.nan, label_end=""))
    for i in range(len(source)):
        if i >= 59:
            expected.loc[i, "past60_vol"] = np.std(simple[i-59:i+1], ddof=1)
        if i + 20 < len(source):
            y = eq[i+20]/eq[i] - 1
            expected.loc[i, ["future20_return", "future20_cash", "future20_profit", "future20_slippage", "label_end"]] = [
                y, cash[i+1:i+21].sum(), float(y > 0), slip[i+1:i+21].sum(), source.date.iloc[i+20]]
    expected["normalized_future20_return"] = expected.future20_return / (expected.past60_vol.where(expected.past60_vol > 0)*np.sqrt(20))
    expected["future20_return_extra_slippage"] = expected.future20_return - expected.future20_slippage/eq
    expected = expected.merge(market[["date", "regime", "market_er60"]], on="date", how="left", validate="one_to_one")
    expected.to_csv(REVIEW / "independent_outcome_sentinels.csv", index=False)
    group_records = []
    for regime in ("low", "mid", "high"):
        g = expected.loc[expected.regime.eq(regime) & expected.future20_return.notna()]
        group_records.append(dict(regime=regime, n=len(g), mean=g.future20_return.mean(),
                                  profit_probability=g.future20_profit.mean(), min_date=g.date.min(), max_date=g.date.max()))
    groups = pd.DataFrame(group_records).set_index("regime")
    point = dict(return_difference=float(groups.loc["high", "mean"]-groups.loc["low", "mean"]),
                 profit_probability_difference=float(groups.loc["high", "profit_probability"]-groups.loc["low", "profit_probability"]))
    # A second implementation draws geometric run lengths, independently for
    # each replicate. This preserves the same distribution, but intentionally
    # does not duplicate the implementer's RNG-consumption order.
    ci_records = []
    n = len(expected)
    y = expected.future20_return.to_numpy(dtype=float)
    regime = expected.regime.to_numpy()
    for block in (60, 120):
        rng = np.random.default_rng(42)
        draws = []
        for _ in range(2000):
            chunks = []
            length = 0
            while length < n:
                start = rng.integers(n)
                run = min(int(rng.geometric(1/block)), n-length)
                chunks.append((start + np.arange(run)) % n)
                length += run
            idx = np.concatenate(chunks)
            yy, rr = y[idx], regime[idx]
            low = yy[(rr == "low") & np.isfinite(yy)]
            high = yy[(rr == "high") & np.isfinite(yy)]
            if len(low) and len(high):
                draws.append((high.mean()-low.mean(), (high > 0).mean()-(low > 0).mean()))
        draws = np.asarray(draws)
        ci_records.append(dict(block=block, repeats=2000, valid_repeats=len(draws),
                               return_ci=np.quantile(draws[:, 0], [.025, .975]).tolist(),
                               profit_probability_ci=np.quantile(draws[:, 1], [.025, .975]).tolist(),
                               method="independent geometric-run stationary bootstrap, same fixed full calendar and seed42; RNG consumption intentionally differs"))
    return dict(calendar_completeness=True, calendar_days=len(expected), mature_labels=int(expected.future20_return.notna().sum()),
                immature_tail=int(expected.future20_return.isna().sum()),
                classified_mature_rows=int((expected.regime.ne("") & expected.future20_return.notna()).sum()),
                groups=group_records, **point, bootstrap_sentinels=ci_records)


def independent_episode_sentinels():
    source = LINE / "outputs/stage251_half_r_ab/A_final3"
    closed = pd.read_csv(source / "statistics_audit/complete_episodes.csv")
    opened = pd.read_csv(source / "statistics_audit/open_episodes.csv")
    cycles = pd.read_csv(source / "statistics_audit/complete_cycles.csv")
    positions = pd.read_csv(source / "statistics_audit/open_positions.csv")
    all_cycles = pd.concat([cycles, positions], ignore_index=True)
    mothers = all_cycles.loc[all_cycles.first_id.eq(all_cycles.root_id)].set_index("root_id")
    fills = pd.read_csv(source / "trades.csv").set_index("trade_id")
    risk = pd.read_csv(source / "entry_risk.csv").dropna(subset=["signal_order_id"]).set_index("signal_order_id")
    events = pd.read_csv(source / "stop_retry_events.csv")
    stop_mothers = set(events.loc[events.first_stop_time.notna(), "trade_id"])
    retry_roots = set(pd.read_csv(source / "statistics_audit/retry_links.csv").root_id)
    daily = pd.read_csv(source / "daily.csv")
    previous = dict(zip(daily.date.iloc[1:], daily.date.iloc[:-1]))
    market = pd.read_csv(OUTPUT / "market/market_daily.csv", keep_default_na=False).set_index("date")
    records = []
    for is_closed, data in [(True, closed), (False, opened)]:
        for _, episode in data.iterrows():
            root_id = int(episode.root_id)
            mother = mothers.loc[root_id]
            fill = fills.loc[mother.first_trade_id]
            initial = risk.loc[fill.order_id]
            denominator = float(fill.volume * initial.risk_per_contract)
            entry_date = fill.trading_date
            asof = previous.get(entry_date, "")
            regime = market.loc[asof, "regime"] if asof in market.index else ""
            regime = regime if regime else "unclassified"
            retry_closed = cycles.loc[cycles.root_id.eq(root_id) & cycles.is_retry.eq(True), "net_pnl"].sum()
            retry_open = positions.loc[positions.root_id.eq(root_id) & positions.is_retry.eq(True), "net_mtm"].sum()
            records.append(dict(root_id=root_id, first_trade_id=mother.first_trade_id,
                                signal_order_id=fill.order_id, entry_date=entry_date, asof_date=asof,
                                initial_risk=denominator, is_closed=is_closed, is_open=not is_closed,
                                net_pnl=float(episode.net_pnl) if is_closed else np.nan,
                                net_R=float(episode.net_pnl)/denominator if is_closed else np.nan,
                                open_net_mtm=np.nan if is_closed else float(episode.net_mtm),
                                half_r_stop=mother.first_trade_id in stop_mothers,
                                has_retry=root_id in retry_roots, retry_pnl=float(retry_closed+retry_open), regime=regime))
    table = pd.DataFrame(records).sort_values("root_id")
    table.to_csv(REVIEW / "independent_episode_sentinels.csv", index=False)
    return dict(n=len(table), n_closed=int(table.is_closed.sum()), n_open=int(table.is_open.sum()),
                classified=int(table.regime.ne("unclassified").sum()),
                risk_matches_actual_field=bool(np.allclose(table.initial_risk,
                    [risk.loc[x, "actual_risk_amount"] for x in table.signal_order_id])),
                half_r_stopped=int(table.half_r_stop.sum()), retries=int(table.has_retry.sum()),
                root814=table.loc[table.root_id.eq(814)].replace({np.nan:None}).to_dict(orient="records"))


def compare_analysis_artifacts():
    analysis = OUTPUT / "analysis"
    hashes = json.loads((analysis / "analysis_file_hashes.json").read_text())
    hash_checks = {name: digest(analysis / name) == expected for name, expected in hashes.items()}
    expected = pd.read_csv(REVIEW / "independent_outcome_sentinels.csv", keep_default_na=False)
    actual = pd.read_csv(analysis / "joined_daily.csv", keep_default_na=False)
    result = dict(output_hash_checks=hash_checks, joined_rows=len(actual), joined_unique_dates=not actual.date.duplicated().any())
    assert expected.date.equals(actual.date)
    columns = ("future20_return", "future20_cash", "future20_profit", "future20_slippage", "past60_vol",
               "normalized_future20_return", "future20_return_extra_slippage")
    outcome_checks = {}
    for name in columns:
        a = pd.to_numeric(expected[name], errors="coerce")
        b = pd.to_numeric(actual[name], errors="coerce")
        outcome_checks[name] = int((~np.isclose(a, b, atol=1e-10, rtol=1e-10, equal_nan=True)).sum())
    outcome_checks["regime"] = int((expected.regime.fillna("") != actual.regime.fillna("")).sum())
    outcome_checks["label_end"] = int((expected.label_end.fillna("") != actual.label_end.fillna("")).sum())
    result["outcome_mismatches"] = outcome_checks
    primary = json.loads((analysis / "primary_block60.json").read_text())
    independent = json.loads((REVIEW / "independent_statistics_sentinels.json").read_text())
    result["main_point_estimate_mismatches"] = {
        name: not bool(np.isclose(primary[name], independent[name], atol=1e-12))
        for name in ("return_difference", "profit_probability_difference")}
    result["main_group_mismatches"] = {
        row["regime"]: {
            name: not bool(np.isclose(row[name], next(x for x in independent["groups"] if x["regime"] == row["regime"])[name], atol=1e-12))
            for name in ("n", "mean", "profit_probability")}
        for row in primary["groups"]}
    split_checks = []
    y = pd.to_numeric(expected.future20_return, errors="coerce")
    start = pd.to_datetime(expected.date)
    end = pd.to_datetime(expected.label_end, errors="coerce")
    def effect(keep):
        low = y.loc[keep & expected.regime.eq("low") & y.notna()]
        middle = y.loc[keep & expected.regime.eq("mid") & y.notna()]
        high = y.loc[keep & expected.regime.eq("high") & y.notna()]
        return dict(n_labeled=len(low)+len(middle)+len(high), n_low=len(low), n_mid=len(middle), n_high=len(high),
                    return_difference=high.mean()-low.mean(),
                    profit_probability_difference=(high > 0).mean()-(low > 0).mean())
    def compare_split(row, keep, label):
        own = effect(keep)
        split_checks.append(dict(split=label, mismatches=[name for name, value in own.items()
                            if not np.isclose(value, row[name], atol=1e-12, equal_nan=True)]))
    for _, row in pd.read_csv(analysis / "annual_effects.csv").iterrows():
        yr = int(row.year)
        compare_split(row, start.between(f"{yr}-01-01", f"{yr}-12-31") & end.between(f"{yr}-01-01", f"{yr}-12-31"), f"year_{yr}")
    for _, row in pd.read_csv(analysis / "leave_year_out.csv").iterrows():
        yr = int(row.excluded_year)
        keep = ~((start <= pd.Timestamp(f"{yr}-12-31")) & (end >= pd.Timestamp(f"{yr}-01-01"))) & end.notna()
        compare_split(row, keep, f"leave_{yr}")
    for _, row in pd.read_csv(analysis / "period_effects.csv").iterrows():
        lo, hi = {"2020-2022":("2020-01-01","2022-12-31"), "2023-2024":("2023-01-01","2024-12-31"), "2025+":("2025-01-01","2026-12-31")}[row.period]
        compare_split(row, start.between(lo, hi) & end.between(lo, hi), row.period)
    result["cross_boundary_split_checks"] = split_checks
    ep_expected = pd.read_csv(REVIEW / "independent_episode_sentinels.csv").sort_values("root_id").reset_index(drop=True)
    ep_actual = pd.read_csv(analysis / "episodes.csv").sort_values("root_id").reset_index(drop=True)
    assert ep_expected.root_id.equals(ep_actual.root_id)
    ep_checks = {}
    for column in ("initial_risk", "net_pnl", "net_R", "open_net_mtm", "retry_pnl"):
        ep_checks[column] = int((~np.isclose(ep_expected[column], ep_actual[column], atol=1e-10, equal_nan=True)).sum())
    for column in ("entry_date", "asof_date", "first_trade_id", "signal_order_id", "is_closed", "is_open", "half_r_stop", "has_retry", "regime"):
        ep_checks[column] = int((ep_expected[column].fillna("") != ep_actual[column].fillna("")).sum())
    result["episode_mismatches"] = ep_checks
    result["bootstrap_crosscheck"] = []
    for block, filename in [(60,"primary_block60.json"),(120,"sensitivity_block120.json")]:
        formal = json.loads((analysis / filename).read_text())
        alternate = next(x for x in independent["bootstrap_sentinels"] if x["block"] == block)
        result["bootstrap_crosscheck"].append(dict(block=block, formal_return_ci=formal["return_ci"],
            independent_return_ci=alternate["return_ci"], formal_probability_ci=formal["profit_probability_ci"],
            independent_probability_ci=alternate["profit_probability_ci"],
            formal_valid_repeats=formal["bootstrap_valid_repeats"], independent_valid_repeats=alternate["valid_repeats"],
            both_methods_return_cross_zero=bool(formal["return_ci"][0] < 0 < formal["return_ci"][1] and alternate["return_ci"][0] < 0 < alternate["return_ci"][1]),
            both_methods_probability_cross_zero=bool(formal["profit_probability_ci"][0] < 0 < formal["profit_probability_ci"][1] and alternate["profit_probability_ci"][0] < 0 < alternate["profit_probability_ci"][1])))
    # Frisch-Waugh-Lovell residual regression independently checks the reported
    # percentile slope using the fixed controls and observed-year dummies.
    models = json.loads((analysis / "regression_summary.json").read_text())
    numeric = actual.copy()
    numeric["year"] = pd.to_datetime(numeric.date).dt.year
    regressions = []
    for model in models:
        names = ["future20_return", model["x"], *model["controls"]]
        sample = numeric[names].apply(pd.to_numeric, errors="coerce").dropna()
        nuisance = pd.DataFrame({"intercept":np.ones(len(sample))}, index=sample.index)
        for name in model["controls"]:
            vals = sample[name]
            if vals.std(ddof=0) > 0:
                nuisance[name] = (vals-vals.mean())/vals.std(ddof=0)
        if model["year_fe"]:
            years = numeric.loc[sample.index,"year"]
            for yr in sorted(years.unique())[1:]:
                nuisance[f"y{yr}"] = years.eq(yr).astype(float)
        xx = sample[model["x"]].to_numpy()
        yy = sample.future20_return.to_numpy()
        zz = nuisance.to_numpy()
        rx = xx-zz@np.linalg.lstsq(zz,xx,rcond=None)[0]
        ry = yy-zz@np.linalg.lstsq(zz,yy,rcond=None)[0]
        own_beta = float(rx@ry/(rx@rx))
        regressions.append(dict(model=model["model"], sample_matches=len(sample) == model["n"],
                                formal_beta=model["beta"], independent_fwl_beta=own_beta,
                                beta_matches=bool(np.isclose(own_beta,model["beta"],atol=1e-10))))
    result["regression_fwl_checks"] = regressions
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compare-only", action="store_true")
    parser.add_argument("--statistics-only", action="store_true")
    parser.add_argument("--episodes-only", action="store_true")
    parser.add_argument("--analysis-only", action="store_true")
    args = parser.parse_args()
    REVIEW.mkdir(parents=True, exist_ok=True)
    if args.analysis_only:
        summary = compare_analysis_artifacts()
        (REVIEW / "independent_analysis_comparison.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    if args.episodes_only:
        summary = independent_episode_sentinels()
        (REVIEW / "independent_episode_checks.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    if args.statistics_only:
        summary = independent_outcomes_and_main_effect()
        (REVIEW / "independent_statistics_sentinels.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    if args.compare_only:
        summary = compare_market_artifacts()
        (REVIEW / "independent_market_comparison.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    fingerprints = source_fingerprints()
    (REVIEW / "preliminary_source_fingerprints.json").write_text(json.dumps(fingerprints, ensure_ascii=False, indent=2) + "\n")
    sentinels = independent_market_sentinels()
    sentinels.to_csv(REVIEW / "independent_market_sentinels.csv", index=False)
    summary = dict(source_fingerprints_match=all(x["matches_frozen"] for x in fingerprints),
                   source_trade_checks=independent_source_trade_checks(),
                   sentinel_dates=list(TARGET_DATES), sentinel_rows=len(sentinels),
                   scope="five fixed-date cross sections, read-only source windows; no financial replay or training")
    (REVIEW / "independent_preliminary_review.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
