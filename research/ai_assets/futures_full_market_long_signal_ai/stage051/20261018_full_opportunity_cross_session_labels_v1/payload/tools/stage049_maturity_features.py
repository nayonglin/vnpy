"""Pure Stage048/049 maturity features; no I/O, fits or cash execution.

Input is the already-loaded Stage042 Market. Its N is the causal first-TR,
20-TR seed/1-in-20 recursive series, not Stage009's rolling ATR. Historical
metadata lifecycle snapshots never select feature peers: nominal YYYYMM is
immutable epoch identity, and membership uses only accepted bars at u/u-1.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
import hashlib
import math

import numpy as np
import pandas as pd

HASH_PREFIX = "stage046_maturity_relation_v1"
FEATURE_COLUMNS = [
    "sequence_index", "event_id", "product_id", "family_id", "u_date", "u_index",
    "reference_epoch", "status", "normalizer", "normalizer_missing",
    "q_aligned", "q_shuffled", "q_missing", "q_missing_reason", "peer_count",
    "peer_distinct_month_count", "tenor_span_years", "return_mean", "return_std",
    "return_min", "return_max", "front_next_basis_u", "front_next_basis_prev",
    "front_next_tenor_span_years", "front_next_missing", "front_epoch", "next_epoch",
]
PEER_COLUMNS = [
    "event_id", "peer_index", "peer_epoch", "nominal_month", "tau_years",
    "log_return", "shuffle_rank", "shuffled_source_epoch", "shuffled_log_return",
]


def build_features(panel, market, dates, economics):
    """Return (one-row-per-panel features, one-to-many peer mapping, summary).

    feature_df preserves panel order and all missing observations. peer_df is
    ordered by panel event then increasing nominal month/epoch. shuffle_rank is
    the original peer's position in SHA256 order; at target tenor index j the
    shuffled_source_epoch is the original peer occupying SHA256 rank j.
    economics is an API-compatible argument deliberately unused for peer cuts.
    """
    required = {"event_id", "product_id", "u_date", "reference_epoch"}
    if not required.issubset(panel.columns):
        raise ValueError("feature panel lacks required identity fields")
    if panel.event_id.isna().any() or panel.event_id.duplicated().any():
        raise ValueError("missing or duplicate event identity")
    if panel.duplicated(["product_id", "u_date"]).any():
        raise ValueError("duplicate product/day in feature mother")
    dates = list(dates)
    if dates != list(market.dates) or dates != sorted(set(dates)):
        raise ValueError("Market and strictly ordered source dates must agree")
    lookup = {d: i for i, d in enumerate(dates)}
    date_ordinals = np.asarray(dates, dtype="datetime64[D]").astype(np.int64)
    # Do not duplicate the full input panel's unused raw price columns in RAM.
    identity_columns = ["event_id", "product_id", "u_date", "reference_epoch"]
    if "status" in panel.columns:
        identity_columns.append("status")
    records = panel[identity_columns].to_dict("records")
    needed = set()
    product_max_u = {}
    for row in records:
        if row["u_date"] not in lookup:
            raise ValueError("panel u_date outside bound source calendar")
        product, u = row["product_id"], lookup[row["u_date"]]
        needed.add((product, u))
        product_max_u[product] = max(u, product_max_u.get(product, -1))

    # Index accepted adjacent pairs once per epoch, not all epochs per query.
    # Only dates requested by this panel are cached, so future source rows and
    # their liquidity cannot affect a prefix request, its members or summary.
    cache = defaultdict(list)
    for epoch, series in market.series.items():
        product, nominal = epoch.rsplit(".", 1)
        if product not in product_max_u:
            continue
        if len(nominal) != 6 or not nominal.isdigit():
            raise ValueError("epoch lacks immutable YYYYMM")
        nominal_date = date(int(nominal[:4]), int(nominal[4:]), 1)
        nominal_ordinal = (nominal_date - date(1970, 1, 1)).days
        days = series.days
        if len(days) < 2:
            continue
        paired = (series.valid[1:] & series.valid[:-1] & (np.diff(days) == 1)
                  & (days[1:] <= product_max_u[product]))
        for j in np.flatnonzero(paired) + 1:
            u = int(days[j])
            if (product, u) not in needed or nominal_ordinal <= date_ordinals[u]:
                continue
            current, previous = float(series.values[j, 3]), float(series.values[j-1, 3])
            if not (math.isfinite(current) and math.isfinite(previous)
                    and current > 0 and previous > 0):
                raise ValueError("accepted Market pair has invalid close")
            cache[(product, u)].append((
                epoch, nominal, (nominal_ordinal-date_ordinals[u])/365.,
                math.log(current/previous), current, previous,
            ))
    cached_pairs = sum(map(len, cache.values()))
    cached_days = len(cache)
    feature_rows, peer_rows = [], []
    missing_reasons = Counter()
    for sequence_index, row in enumerate(records):
        event_id, product, u_date = row["event_id"], row["product_id"], row["u_date"]
        u = lookup[u_date]
        query = row["reference_epoch"]
        query = query if isinstance(query, str) else ""
        if query and query.rsplit(".", 1)[0] != product:
            raise ValueError("query epoch is not the exact complete product")
        pool = sorted(cache.pop((product, u), []), key=lambda p: (p[1], p[0]))
        peers = [p for p in pool if p[0] != query]
        n = len(peers)
        distinct_months = len({p[1] for p in peers})
        tau = np.asarray([p[2] for p in peers], dtype=np.float64)
        returns = np.asarray([p[3] for p in peers], dtype=np.float64)
        order = sorted(range(n), key=lambda i: (
            hashlib.sha256(f"{HASH_PREFIX}|{product}|{u_date}|{peers[i][0]}".encode("utf-8")).digest(),
            peers[i][0],
        ))
        ranks = np.empty(n, dtype=np.int64)
        if n:
            ranks[order] = np.arange(n)
        shuffled = returns[order]
        for j, peer in enumerate(peers):
            peer_rows.append((event_id, j, peer[0], peer[1], peer[2], peer[3],
                              int(ranks[j]), peers[order[j]][0], float(shuffled[j])))

        normalizer = math.nan
        reason = ""
        query_series = market.series.get(query)
        query_j = query_series.locate(u) if query_series is not None else None
        if not query:
            reason = "query_missing"
        elif query_j is None or not query_series.valid[query_j]:
            reason = "query_unobserved"
        else:
            close, N = float(query_series.values[query_j, 3]), float(query_series.N[query_j])
            if math.isfinite(N) and N > 0 and math.isfinite(close) and close > 0:
                normalizer = N/close
            else:
                reason = "normalizer_missing"
        normalizer_missing = int(not math.isfinite(normalizer))
        if not reason and distinct_months < 3:
            reason = "insufficient_peer_months"
        q_aligned = q_shuffled = math.nan
        if not reason:
            centered_tau = tau - tau.mean()
            denominator = float(centered_tau @ centered_tau)
            if denominator <= 0 or not math.isfinite(denominator):
                reason = "degenerate_tenor"
            else:
                # Centering returns removes the parallel component explicitly.
                q_aligned = float(centered_tau @ (returns-returns.mean()) / denominator / normalizer)
                q_shuffled = float(centered_tau @ (shuffled-shuffled.mean()) / denominator / normalizer)
        missing_reasons[reason or "ready"] += 1

        # The legacy front/next control includes query in the same pair-valid
        # pool and takes the earliest two distinct nominal delivery months.
        front = following = None
        for candidate in pool:
            if front is None:
                front = candidate
            elif candidate[1] != front[1]:
                following = candidate
                break
        front_missing = int(following is None)
        basis_u = basis_prev = front_span = math.nan
        if following is not None:
            basis_u = math.log(following[4]/front[4])
            basis_prev = math.log(following[5]/front[5])
            front_span = following[2]-front[2]
        feature_rows.append((
            sequence_index, event_id, product, product.removesuffix("_F"), u_date, u,
            query, row.get("status", ""), normalizer, normalizer_missing,
            q_aligned, q_shuffled, int(bool(reason)), reason, n, distinct_months,
            float(tau.max()-tau.min()) if n else math.nan,
            float(returns.mean()) if n else math.nan,
            float(returns.std(ddof=0)) if n else math.nan,
            float(returns.min()) if n else math.nan,
            float(returns.max()) if n else math.nan,
            basis_u, basis_prev, front_span, front_missing,
            front[0] if front is not None else "", following[0] if following is not None else "",
        ))
    feature_df = pd.DataFrame(feature_rows, columns=FEATURE_COLUMNS)
    peer_df = pd.DataFrame(peer_rows, columns=PEER_COLUMNS)
    if feature_df.event_id.tolist() != panel.event_id.tolist():
        raise AssertionError("feature output changed mother identity or ordering")
    summary = dict(
        schema="stage049_maturity_features_v1", mother_rows=len(panel),
        feature_rows=len(feature_df), peer_rows=len(peer_df),
        q_ready=int((feature_df.q_missing == 0).sum()),
        q_missing=int((feature_df.q_missing == 1).sum()),
        q_state_counts=dict(sorted(missing_reasons.items())),
        cached_observable_product_days=cached_days, cached_observable_pairs=cached_pairs,
        normalizer="Stage042 causal seeded_recursive_N(u)/C(u)",
        shuffle_key=HASH_PREFIX+"|product_id|u|epoch", min_distinct_nonquery_months=3,
        normalizer_uses_D=False, static_lifecycle_peer_filter=False,
        all_rows_preserved=True, module_native_queries=0, model_fit_calls=0,
        financial_backtests=0, production_qualified=False,
    )
    return feature_df, peer_df, summary
