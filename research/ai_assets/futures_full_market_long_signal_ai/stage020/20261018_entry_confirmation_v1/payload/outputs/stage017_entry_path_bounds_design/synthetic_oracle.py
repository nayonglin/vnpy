"""Stage017: finite synthetic mathematics only; no market input or runtime import."""
from collections import deque
from fractions import Fraction as Q
from datetime import datetime, timezone
import json
from pathlib import Path


def oracle(o, h, l, c, b, r, fee):
    o, h, l, c, b, r, fee = map(Q, (o, h, l, c, b, r, fee))
    assert l <= min(o, c) <= max(o, c) <= h and r > 0
    f = o if o >= b else b
    s0, t0, s1, t1 = o-r, o+4*r, f-r, f+4*r
    nodes = sorted({o, h, l, c} | {p for p in (b, s0, t0, s1, t1) if l <= p <= h})
    # A: 0 active / 1 SL / 2 PT. K: 0 pending / 1 active / 2 SL / 3 PT.
    first = (nodes.index(o), 0, int(o >= b), o == l, o == h)
    queue, seen, payoff = deque([first]), {first}, set()
    while queue:
        i, a, k, low, high = queue.popleft()
        if nodes[i] == c and low and high:
            pa = {-1: None, 0: (c-o)/r, 1: Q(-1), 2: Q(4)}[a] - fee
            pk = {0: Q(0), 1: (c-f)/r-fee, 2: Q(-1)-fee, 3: Q(4)-fee}[k]
            payoff.add((pa, pk))
        for j in (i-1, i+1):
            if not 0 <= j < len(nodes):
                continue
            p, aa, kk = nodes[j], a, k
            if aa == 0:
                if p <= s0:
                    aa = 1
                elif p >= t0:
                    aa = 2
            if kk == 0 and p >= b:
                kk = 1
            if kk == 1:
                if p <= s1:
                    kk = 2
                elif p >= t1:
                    kk = 3
            state = (j, aa, kk, low or p == l, high or p == h)
            if state not in seen:
                seen.add(state)
                queue.append(state)
    assert payoff
    return payoff, len(seen)


def closed(o, h, l, c, b, r, fee):
    o, h, l, c, b, r, fee = map(Q, (o, h, l, c, b, r, fee))
    stop, profit = l <= o-r, h >= o+4*r
    if stop and profit:
        a = (Q(-1)-fee, Q(4)-fee)
    elif stop:
        a = (Q(-1)-fee,)*2
    elif profit:
        a = (Q(4)-fee,)*2
    else:
        a = ((c-o)/r-fee,)*2
    if o >= b:
        return a, a, (Q(0), Q(0))
    if h < b:
        k = (Q(0), Q(0))
    elif h >= b+4*r:
        k = (Q(-1)-fee, Q(4)-fee) if l <= b-r else (Q(4)-fee,)*2
    elif c <= b-r:
        k = (Q(-1)-fee,)*2
    elif l <= b-r:
        k = (Q(-1)-fee, (c-b)/r-fee)
    else:
        k = ((c-b)/r-fee,)*2
    return a, k, (k[0]-a[1], k[1]-a[0])


def fmt(value):
    if isinstance(value, Q):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [fmt(x) for x in value]
    return value


def run():
    start = datetime.now(timezone.utc).isoformat()
    cases = []
    for b in (99, 100, 101, 102, 104, 108, 110):
        for l in (96, 98, 100):
            for h in (100, 102, 104, 108, 110, 114, 118):
                for c in sorted({l, 100, h}):
                    for fee in (Q(1, 5), Q(1)):
                        cases.append((100, h, l, c, b, 2, fee))
    # Fixed semantic examples: pre-entry L; gap identity; no fill; equality touches.
    named = {
        "low_may_precede_entry": (100, 110, 99, 108, 105, 2, Q(1, 5)),
        "gap_same_policy": (100, 110, 90, 100, 99, 2, Q(1, 5)),
        "no_fill_no_fee": (100, 104, 99, 102, 105, 2, Q(1, 5)),
        "peak_exact_trigger": (100, 105, 99, 104, 105, 2, Q(1, 5)),
        "flat_gap_identity": (100, 100, 100, 100, 100, 2, Q(1, 5)),
    }
    rows, named_results, max_states = [], {}, 0
    marginal_mismatch = delta_mismatch = invalid_outer = 0
    for case in cases + list(named.values()):
        outcomes, states = oracle(*case)
        max_states = max(max_states, states)
        actual_a = (min(a for a, _ in outcomes), max(a for a, _ in outcomes))
        actual_k = (min(k for _, k in outcomes), max(k for _, k in outcomes))
        actual_d = (min(k-a for a, k in outcomes), max(k-a for a, k in outcomes))
        a, k, d = closed(*case)
        marginal_mismatch += (a != actual_a or k != actual_k)
        delta_mismatch += (d != actual_d)
        invalid_outer += not (d[0] <= actual_d[0] <= actual_d[1] <= d[1])
        rows.append({"case": fmt(case), "a": fmt(a), "k": fmt(k), "delta_outer": fmt(d), "delta_oracle": fmt(actual_d), "reachable_states": states})
    for name, case in named.items():
        outcomes, _ = oracle(*case)
        a, k, d = closed(*case)
        named_results[name] = {"input": fmt(case), "a": fmt(a), "k": fmt(k), "paired": fmt(d), "joint_payoffs": fmt(sorted(outcomes))}
    assert named_results["low_may_precede_entry"]["paired"] == ["-5", "-5/2"]
    assert named_results["gap_same_policy"]["paired"] == ["0", "0"]
    assert named_results["no_fill_no_fee"]["k"] == ["0", "0"]
    assert marginal_mismatch == 0, marginal_mismatch
    assert invalid_outer == 0, invalid_outer
    evidence = {
        "schema": "stage017_synthetic_only_v1",
        "start_utc": start, "finish_utc": datetime.now(timezone.utc).isoformat(),
        "real_market_rows_read": 0, "sql_queries": 0, "fits": 0, "financial_runs": 0,
        "finite_grid_cases_including_two_fee_budgets": len(cases), "named_extra_cases": len(named),
        "max_reachable_states": max_states, "marginal_mismatches": marginal_mismatch,
        "paired_outer_violations": invalid_outer, "paired_outer_not_equal_oracle_cases": delta_mismatch,
        "limits": "finite synthetic examples; not a global proof of sharpness; no actual market execution qualification",
        "named_examples": named_results, "cases": rows,
    }
    target = Path(__file__).with_name("synthetic_results.json")
    assert not target.exists(), "no overwrite"
    target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({k: v for k, v in evidence.items() if k not in ("cases", "named_examples")}, ensure_ascii=False))


if __name__ == "__main__":
    run()
