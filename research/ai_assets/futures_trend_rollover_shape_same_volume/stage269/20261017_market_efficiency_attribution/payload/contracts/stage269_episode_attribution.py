"""Read-only mother-signal episode descriptions for Stage269.

Episodes retain their mother's first actual fill risk and previous source-day
market state.  Open episodes are censored descriptions, never closed wins or
losses.  This sparse classified subset is auxiliary and cannot rescue the main
predeclared twenty-day hypothesis.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from stage269_statistics import REGIME_ALIASES, REGIMES, stationary_indexes


def _read(base: Path, relative: str, required: tuple[str, ...]) -> pd.DataFrame:
    frame = pd.read_csv(base / relative)
    missing = set(required) - set(frame.columns)
    if missing:
        raise ValueError(f"{relative} missing required columns: {sorted(missing)}")
    if "root_id" in frame:
        frame["root_id"] = pd.to_numeric(frame["root_id"], errors="raise")
    return frame


def _keys(values: pd.Series) -> pd.Series:
    result = values.astype("string").str.strip()
    return result.mask(result.isin(["", "nan", "None", "<NA>"]))


def _unique(frame: pd.DataFrame, key: str, source: str) -> None:
    if frame.loc[frame[key].notna(), key].duplicated().any():
        raise ValueError(f"{source} has duplicate {key}; arbitrary row selection forbidden")


def _bool(values: pd.Series) -> pd.Series:
    return values.astype("string").str.lower().isin(["true", "1", "1.0"])


def _calendar(values) -> pd.DatetimeIndex:
    dates = pd.DatetimeIndex(pd.to_datetime(values, errors="raise")).normalize()
    if dates.hasnans or dates.has_duplicates:
        raise ValueError("source calendar must contain unique nonmissing dates")
    return dates.sort_values()


def build_episode_table(base_dir, market_daily: pd.DataFrame, calendar) -> pd.DataFrame:
    """Join all closed/open mother episodes without running financial replay.

    Initial risk = actual first fill.volume * its risk_per_contract, where the
    join is first_trade_id -> trades.trade_id -> order_id -> signal_order_id.
    ``actual_risk_amount`` is a separate cross-check, not a replacement for the
    actual first fill denominator.  Unmatched or nonpositive risk stays missing.
    The entry trading date comes from that actual fill, not its natural date.
    """
    base = Path(base_dir)
    closed = _read(base, "statistics_audit/complete_episodes.csv", ("root_id", "entry_date", "exit_date", "net_pnl", "cost", "cycle_count"))
    opened = _read(base, "statistics_audit/open_episodes.csv", ("root_id", "net_mtm"))
    cycle_required = ("root_id", "first_id", "first_trade_id", "is_retry", "entry_date", "signal_date", "opened_volume", "product", "direction")
    cycles = _read(base, "statistics_audit/complete_cycles.csv", (*cycle_required, "net_pnl"))
    positions = _read(base, "statistics_audit/open_positions.csv", (*cycle_required, "net_mtm"))
    trades = _read(base, "trades.csv", ("trade_id", "order_id", "volume", "trading_date"))
    risk = _read(base, "entry_risk.csv", ("signal_order_id", "risk_per_contract"))
    events = _read(base, "stop_retry_events.csv", ("trade_id", "first_stop_time"))
    links = _read(base, "statistics_audit/retry_links.csv", ("root_id",))
    closed = closed.rename(columns={"entry_date": "audit_entry_date"}).assign(is_closed=True, is_open=False, open_net_mtm=np.nan)
    opened = opened.rename(columns={"net_mtm": "open_net_mtm"}).assign(is_closed=False, is_open=True, net_pnl=np.nan)
    result = pd.concat([closed, opened], ignore_index=True, sort=False)
    _unique(result, "root_id", "combined closed/open mother episodes")

    all_cycles = pd.concat([cycles, positions], ignore_index=True, sort=False)
    first_id = pd.to_numeric(all_cycles["first_id"], errors="coerce")
    mothers = all_cycles.loc[first_id.eq(all_cycles["root_id"]), list(cycle_required)].copy()
    _unique(mothers, "root_id", "mother initial cycles")
    mothers = mothers.rename(columns={"entry_date": "mother_entry_date", "is_retry": "mother_is_retry"})
    mothers["first_trade_id"] = _keys(mothers["first_trade_id"])
    result = result.merge(mothers, how="left", on="root_id", validate="one_to_one", indicator="_mother_join")
    result["mother_unmatched"] = result.pop("_mother_join").ne("both")

    fills = trades[["trade_id", "order_id", "volume", "trading_date"]].copy()
    fills["trade_id"], fills["order_id"] = _keys(fills["trade_id"]), _keys(fills["order_id"])
    _unique(fills, "trade_id", "actual trades")
    fills = fills.rename(columns={"trade_id": "first_trade_id", "order_id": "signal_order_id", "volume": "first_fill_volume", "trading_date": "fill_trading_date"})
    result = result.merge(fills, how="left", on="first_trade_id", validate="many_to_one", indicator="_fill_join")
    result["fill_unmatched"] = result.pop("_fill_join").ne("both")
    result["entry_date"] = pd.to_datetime(result["fill_trading_date"], errors="coerce").dt.normalize()
    mother_date = pd.to_datetime(result["mother_entry_date"], errors="coerce").dt.normalize()
    result["entry_date_mismatch"] = result["entry_date"].notna() & mother_date.notna() & result["entry_date"].ne(mother_date)
    result["entry_date"] = result["entry_date"].fillna(mother_date)
    result["date"] = result["entry_date"]

    risk["signal_order_id"] = _keys(risk["signal_order_id"])
    risk = risk.loc[risk["signal_order_id"].notna()].copy()
    _unique(risk, "signal_order_id", "entry risk")
    if "actual_risk_amount" not in risk:
        risk["actual_risk_amount"] = np.nan
    result = result.merge(risk[["signal_order_id", "risk_per_contract", "actual_risk_amount"]], how="left", on="signal_order_id", validate="many_to_one", indicator="_risk_join")
    risk_joined = result.pop("_risk_join").eq("both")
    volume = pd.to_numeric(result["first_fill_volume"], errors="coerce")
    per_contract = pd.to_numeric(result["risk_per_contract"], errors="coerce")
    denominator = volume * per_contract
    good_risk = np.isfinite(volume) & volume.gt(0) & np.isfinite(per_contract) & per_contract.gt(0) & np.isfinite(denominator) & denominator.gt(0)
    result["initial_risk"] = denominator.where(good_risk)
    result["risk_unmatched"] = ~good_risk
    result["risk_status"] = np.select(
        [result["mother_unmatched"], result["fill_unmatched"], ~risk_joined, ~good_risk],
        ["mother_initial_unmatched", "first_fill_unmatched", "risk_order_unmatched", "invalid_initial_risk"], default="matched")
    actual = pd.to_numeric(result["actual_risk_amount"], errors="coerce")
    crosscheck = np.isfinite(actual) & good_risk
    match = np.isclose(actual, denominator, rtol=1e-8, atol=1e-6)
    result["actual_risk_matches"] = pd.array(np.where(crosscheck, match, None), dtype="boolean")
    result["actual_risk_mismatch"] = crosscheck & ~match
    result["net_R"] = pd.to_numeric(result["net_pnl"], errors="coerce") / result["initial_risk"]
    result["open_R"] = pd.to_numeric(result["open_net_mtm"], errors="coerce") / result["initial_risk"]

    source_days = _calendar(calendar)
    previous = pd.Series(source_days[:-1], index=source_days[1:])
    result["asof_date"] = result["entry_date"].map(previous)
    market = market_daily.copy()
    market["date"] = pd.to_datetime(market["date"], errors="raise").dt.normalize()
    _unique(market, "date", "market daily")
    market = market.rename(columns={"date": "asof_date"})
    columns = ["asof_date", *[c for c in ("market_er60", "er60_expanding_pct", "regime", "gate_pass", "coverage_ratio") if c in market]]
    result = result.merge(market[columns], how="left", on="asof_date", validate="many_to_one", indicator="_market_join")
    market_joined = result.pop("_market_join").eq("both")
    if "market_er60" not in result:
        result["market_er60"] = np.nan
    if "regime" not in result:
        result["regime"] = "unclassified"
    result["regime"] = result["regime"].replace(REGIME_ALIASES)
    result["regime"] = result["regime"].where(result["regime"].isin(REGIMES), "unclassified")
    result["market_state_status"] = np.select(
        [~result["entry_date"].isin(source_days), result["asof_date"].isna(), ~market_joined, result["regime"].eq("unclassified")],
        ["entry_outside_source_calendar", "no_previous_source_day", "market_day_missing", "market_unclassified"], default="classified")

    events["trade_id"] = _keys(events["trade_id"])
    has_stop = _keys(events["first_stop_time"]).notna()
    stops = has_stop.groupby(events["trade_id"]).any()
    result["half_r_stop"] = result["first_trade_id"].map(stops).eq(True)
    result["has_retry"] = result["root_id"].isin(links["root_id"])
    retry_closed = cycles.loc[_bool(cycles["is_retry"])].copy()
    retry_open = positions.loc[_bool(positions["is_retry"])].copy()
    retry_closed["net_pnl"] = pd.to_numeric(retry_closed["net_pnl"], errors="coerce")
    retry_open["net_mtm"] = pd.to_numeric(retry_open["net_mtm"], errors="coerce")
    closed_pnl = retry_closed.groupby("root_id")["net_pnl"].agg(lambda x: x.sum() if x.notna().all() else np.nan)
    open_pnl = retry_open.groupby("root_id")["net_mtm"].agg(lambda x: x.sum() if x.notna().all() else np.nan)
    result["retry_closed_pnl"] = result["root_id"].map(closed_pnl)
    result["retry_open_mtm"] = result["root_id"].map(open_pnl)
    result.loc[~result["root_id"].isin(closed_pnl.index), "retry_closed_pnl"] = 0.0
    result.loc[~result["root_id"].isin(open_pnl.index), "retry_open_mtm"] = 0.0
    retry_observed = result["root_id"].isin(pd.concat([retry_closed["root_id"], retry_open["root_id"]]))
    result["retry_link_mismatch"] = result["has_retry"].ne(retry_observed)
    result["retry_pnl"] = result["retry_closed_pnl"] + result["retry_open_mtm"]
    result.loc[result["retry_link_mismatch"], "retry_pnl"] = np.nan
    result.attrs["scope"] = "sparse classified historical subset; auxiliary description cannot rescue main hypothesis"
    result.attrs["risk_denominator"] = "mother first actual fill.volume * risk_per_contract; trade_id -> order_id -> signal_order_id"
    return result.sort_values(["entry_date", "root_id"], na_position="last").reset_index(drop=True)


def _sum(frame: pd.DataFrame, column: str) -> float:
    values = pd.to_numeric(frame[column], errors="coerce")
    return float(values.sum(min_count=1)) if len(values) else 0.0


def episode_group_stats(table: pd.DataFrame) -> pd.DataFrame:
    """All three buckets plus unclassified; closed wins exclude open MTM."""
    rows = []
    for regime in (*REGIMES, "unclassified"):
        group = table.loc[table["regime"].eq(regime)]
        closed = group.loc[group["is_closed"]]
        opened = group.loc[group["is_open"]]
        pnl = pd.to_numeric(closed["net_pnl"], errors="coerce")
        pnl = pnl[np.isfinite(pnl)]
        r = pd.to_numeric(closed["net_R"], errors="coerce")
        r = r[np.isfinite(r)]
        profits, losses = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
        rows.append({
            "regime": regime, "n": len(group), "nclosed": len(closed), "nopen": len(opened),
            "nclosed_pnl": len(pnl), "nclosed_R": len(r), "risk_unmatched": int(group["risk_unmatched"].sum()),
            "closednetpnl": _sum(closed, "net_pnl"), "winprob": float((pnl > 0).mean()) if len(pnl) else np.nan,
            "meanR": float(r.mean()) if len(r) else np.nan, "medianR": float(r.median()) if len(r) else np.nan,
            "profitfactor": float(profits / losses) if losses > 0 else (np.inf if profits > 0 else np.nan),
            "stoprate": float(group["half_r_stop"].mean()) if len(group) else np.nan,
            "retryrate": float(group["has_retry"].mean()) if len(group) else np.nan,
            "retryPNL": _sum(group, "retry_pnl"), "retryClosedPNL": _sum(group, "retry_closed_pnl"),
            "retryOpenMTM": _sum(group, "retry_open_mtm"), "openMTM": _sum(opened, "open_net_mtm"),
        })
    return pd.DataFrame(rows)


def _effect_from_totals(totals: np.ndarray) -> tuple[float, float]:
    r = totals[:, 0] / totals[:, 1] if (totals[:, 1] > 0).all() else np.array([np.nan, np.nan])
    p = totals[:, 2] / totals[:, 3] if (totals[:, 3] > 0).all() else np.array([np.nan, np.nan])
    return float(r[1] - r[0]), float(p[1] - p[0])


def _interval(values: np.ndarray) -> tuple[list[float], int]:
    valid = values[np.isfinite(values)]
    return (np.quantile(valid, [.025, .975]).astype(float).tolist(), len(valid)) if len(valid) else ([np.nan, np.nan], 0)


def episode_effect_with_bootstrap(table: pd.DataFrame, source_calendar, block: float = 60,
                                  repeats: int = 2000, seed: int = 42) -> dict:
    """Draw common source-day blocks of sumR/count/wins/closed-count.

    All mother episodes sharing an entry day travel together, including market
    shocks and simultaneous entries.  Days without episodes remain zero rows
    in the original source calendar.  Open episodes supply no closed wins or R.
    R and win denominators are separately reported because risk can be missing.
    No episode-level iid sampling or price-path reconstruction occurs.
    """
    calendar = _calendar(source_calendar)
    if not len(calendar):
        raise ValueError("source_calendar must not be empty")
    dates = pd.to_datetime(table["date"], errors="coerce").dt.normalize()
    if (dates.notna() & ~dates.isin(calendar)).any():
        raise ValueError("episode entry date lies outside source calendar")
    locations = calendar.get_indexer(dates)
    # [calendar day, low/high, sumR/countR/wins/closed count].
    daily = np.zeros((len(calendar), 2, 4), dtype=float)
    net_r = pd.to_numeric(table["net_R"], errors="coerce").to_numpy(dtype=float)
    pnl = pd.to_numeric(table["net_pnl"], errors="coerce").to_numpy(dtype=float)
    closed = table["is_closed"].to_numpy(dtype=bool)
    regimes = table["regime"].replace(REGIME_ALIASES).to_numpy(dtype=object)
    for group_index, regime in enumerate(("low", "high")):
        group = (locations >= 0) & closed & (regimes == regime)
        have_r, have_pnl = group & np.isfinite(net_r), group & np.isfinite(pnl)
        np.add.at(daily[:, group_index, 0], locations[have_r], net_r[have_r])
        np.add.at(daily[:, group_index, 1], locations[have_r], 1)
        np.add.at(daily[:, group_index, 2], locations[have_pnl], (pnl[have_pnl] > 0).astype(float))
        np.add.at(daily[:, group_index, 3], locations[have_pnl], 1)
    totals = daily.sum(axis=0)
    estimate_r, estimate_p = _effect_from_totals(totals)
    indexes = stationary_indexes(len(calendar), block, repeats, seed)
    r_draws, p_draws = np.full(repeats, np.nan), np.full(repeats, np.nan)
    for i, idx in enumerate(indexes):
        r_draws[i], p_draws[i] = _effect_from_totals(daily[idx].sum(axis=0))
    r_ci, nr = _interval(r_draws)
    p_ci, np_ = _interval(p_draws)
    return {
        "n_calendar": len(calendar), "n_episodes": len(table), "n_closed": int(closed.sum()),
        "n_open": int((~closed).sum()), "n_missing_entry_date": int(dates.isna().sum()),
        "n_classified": int(np.isin(regimes, REGIMES).sum()),
        "n_low_R": int(totals[0, 1]), "n_high_R": int(totals[1, 1]),
        "n_low_closed_pnl": int(totals[0, 3]), "n_high_closed_pnl": int(totals[1, 3]),
        "mean_R_difference": estimate_r, "closed_win_probability_difference": estimate_p,
        "mean_R_ci": r_ci, "win_probability_ci": p_ci,
        "bootstrap_valid_R_repeats": nr, "bootstrap_valid_win_repeats": np_,
        "bootstrap_invalid_R_repeats": repeats - nr, "bootstrap_invalid_win_repeats": repeats - np_,
        "block": block, "repeats": repeats, "seed": seed,
        "ci_method": "95% percentile stationary source-day block bootstrap of joint sumR/count/wins/closed-count; zero-episode days retained",
        "scope": "auxiliary sparse historical subset description; open episodes censored; cannot rescue main hypothesis",
    }
