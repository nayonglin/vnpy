"""Replay frozen S19 arms with a previous-calendar-month volume roster."""
import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import h5py

from run_weekly_portfolio import START, run, sha
from stage025_delivery_guard import load
from stage031_s19_weekly_shape_replay import ARMS, LINE, MARKET

BASE = LINE / "outputs/stage031_s19_weekly_shape_replay_v1"
BASE_SHA = "c57ab11953ce8292cca7eb41558ed7fe0dc7087585ca9aed429baeeb323d9175"
DESIGN = LINE / "stages/20261104_1604_stage032_s19_monthly_volume_top10_design.md"
RAW = LINE.parents[3] / (
    "research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/rqalpha/futures.h5"
)
RAW_SHA = "d288f6e4c7468981e95fbb0c1c9e2e1e66bfb99f5ba607843728aec535c8bfee"


def write_csv(path, rows):
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def previous_month(month):
    return (date.fromisoformat(month + "-01") - timedelta(days=1)).isoformat()[:7]


def build_roster(market, raw):
    products, days, _, _, rows, _, mains, _, _ = market
    days_by_month = defaultdict(list)
    for day in days:
        days_by_month[day[:7]].append(day)

    @lru_cache(maxsize=None)
    def observations(key):
        if key not in raw:
            return {}
        data = raw[key].fields(["datetime", "volume"])[...]
        return {int(row["datetime"]) // 1_000_000: int(row["volume"]) for row in data}

    def recover(day, symbol):
        code, exchange = symbol.upper().split(".")
        prefix, delivery = re.fullmatch(r"([A-Z]+)([0-9]+)", code).groups()
        day_number = int(day.replace("-", ""))
        if exchange == "CZCE" and len(delivery) == 3:
            year = int(day[:4])
            full_year, = (candidate for candidate in range(year - 1, year + 3)
                          if str(candidate)[-1] == delivery[0])
            code = f"{prefix}{full_year % 100:02}{delivery[1:]}"
        if symbol == "MA501.CZCE" and "2014-12-01" <= day <= "2014-12-08":
            raw_volume = observations("ME1501")[day_number]
            if raw_volume <= 0 or raw_volume % 2:
                raise ValueError(f"invalid historical double-sided volume: {day}")
            return raw_volume // 2, "legacy_double_sided", "ME1501"
        if observations(code).get(day_number) == 0:
            return 0, "raw_confirmed_zero", code
        if symbol == "fu1805.SHFE" and "2018-05-02" <= day <= "2018-05-10":
            return None, "expired_mapping_bounded", code
        if symbol == "fu1905.SHFE" and "2018-06-28" <= day < "2018-07-16":
            return 0, "exchange_market_closed", code
        raise ValueError(f"unresolved mapped volume: {day} {symbol}")

    # Raw volumes are unscaled here, which is conservative for an upper bound.
    fu_may_upper = sum(
        volume for key in raw if re.fullmatch(r"FU[0-9]{4}", key)
        for day, volume in observations(key).items() if 20180501 <= day <= 20180531
    )
    roster, rankings, daily = {}, [], []
    had_mapping = set()
    for month, effective_days in days_by_month.items():
        if effective_days[-1] < START:
            continue
        source_month = previous_month(month)
        source_days = days_by_month[source_month]
        totals, covered, gaps = Counter(), Counter(), Counter()
        for day in source_days:
            for product in products:
                symbol = mains.get((day, product))
                if not symbol:
                    if product in had_mapping:
                        raise ValueError(f"missing main mapping after listing: {day} {product}")
                    continue
                had_mapping.add(product)
                bar = rows.get((day, symbol))
                if bar is not None:
                    volume, status, source = int(bar.volume), "admitted", symbol
                else:
                    volume, status, source = recover(day, symbol)
                if volume is None:
                    gaps[product] += 1
                else:
                    totals[product] += volume
                    covered[product] += 1
                daily.append(dict(date=day, product=product, mapped_contract=symbol,
                                  volume=volume, status=status, source_contract=source))
        ordered = sorted((product for product in products if totals[product] > 0),
                         key=lambda product: (-totals[product], product))
        selected = ordered[:10]
        if len(selected) != 10:
            raise ValueError(f"fewer than ten ranked products: {month}")
        cutoff = totals[selected[-1]]
        if gaps and (month != "2018-06" or gaps != {"fu.SHFE": 7}
                     or not totals["fu.SHFE"] <= fu_may_upper < cutoff):
            raise ValueError(f"uncertain Top10: {month} {gaps} cutoff={cutoff}")
        roster[month] = set(selected)
        ranks = {product: i for i, product in enumerate(ordered, 1)}
        for product in sorted(products, key=lambda product: (ranks.get(product, 20), product)):
            rankings.append(dict(effective_month=month, effective_day=effective_days[0],
                                 source_month=source_month, source_first_day=source_days[0],
                                 source_last_day=source_days[-1], product=product,
                                 known_volume=totals[product], covered_days=covered[product],
                                 unresolved_days=gaps[product], rank=ranks.get(product),
                                 selected=int(product in roster[month]), cutoff_volume=cutoff))
    return roster, rankings, daily, fu_may_upper


def verify_baseline():
    manifest = BASE / "SHA256SUMS"
    if sha(manifest) != BASE_SHA:
        raise ValueError("unexpected Stage031 manifest")
    for line in manifest.read_text().splitlines():
        digest, filename = line.split(maxsplit=1)
        if sha(BASE / filename) != digest:
            raise ValueError(f"Stage031 hash mismatch: {filename}")


def replay(output):
    verify_baseline()
    if sha(RAW) != RAW_SHA:
        raise ValueError("unexpected historical volume archive")
    market = load(MARKET, control=True)
    with h5py.File(RAW, "r") as raw:
        roster, rankings, daily, fu_bound = build_roster(market, raw)
    output.mkdir(parents=True)
    write_csv(output / "monthly_rankings.csv", rankings)
    write_csv(output / "rank_volume_daily.csv", daily)
    for arm, mode in ARMS.items():
        baseline = json.loads((BASE / arm / "inputs.json").read_text())
        baseline.pop("source_sha256")
        if len(market[0]) != 19 or market[0] != baseline["products"]:
            raise ValueError("unexpected Stage031 universe")
        for group, pool in (("full_pool", None), ("monthly_top10", roster)):
            destination = output / group / arm
            run(destination, week_body_filter=True, reverse_after_stop=True, block_four_up=True,
                delivery_guard=True, market_loader=lambda: market, weekly_shape_entry=mode,
                monthly_entry_products=pool)
            inputs = json.loads((destination / "inputs.json").read_text())
            inputs.pop("source_sha256")
            actual_pool = inputs.pop("monthly_entry_products", None)
            expected_pool = {month: sorted(products) for month, products in pool.items()} if pool else None
            if inputs != baseline or actual_pool != expected_pool:
                raise ValueError(f"unexpected inputs: {group}/{arm}")
            if pool is None:
                expected_files = {file.name for file in (BASE / arm).iterdir() if file.name != "inputs.json"}
                actual_files = {file.name for file in destination.iterdir() if file.name != "inputs.json"}
                if actual_files != expected_files:
                    raise ValueError(f"unexpected outputs: {arm}")
                for name in expected_files:
                    if (destination / name).read_bytes() != (BASE / arm / name).read_bytes():
                        raise ValueError(f"Stage031 control drift: {arm}/{name}")
    receipt = dict(baseline_manifest_sha256=BASE_SHA, design_sha256=sha(DESIGN),
                   entrypoint_sha256=sha(Path(__file__)), raw_path=str(RAW), raw_sha256=RAW_SHA,
                   products=market[0], months=len(roster), source_status_counts=Counter(row["status"] for row in daily),
                   fu_2018_05_raw_all_contract_upper_bound=fu_bound, arms=ARMS,
                   full_pool_matches_stage031=True)
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    files = sorted(file for file in output.rglob("*") if file.is_file())
    (output / "SHA256SUMS").write_text("".join(f"{sha(file)}  {file.relative_to(output)}\n" for file in files))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    replay(parser.parse_args().output)
