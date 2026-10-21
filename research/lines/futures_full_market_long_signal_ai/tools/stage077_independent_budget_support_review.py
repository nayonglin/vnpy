"""One independent review of Stage076's small frozen audit; no author import.

All arithmetic below uses exact rational numbers from the saved print strings.
No market/model/financial replay dependency, score ranking, or outcome field is used.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timezone
from decimal import Decimal
from fractions import Fraction as F
import gzip
import hashlib
import io
import json
from pathlib import Path


ALLOWED = ('budget_id budget_kind account_id scenario event_id product_id family_id '
           'u_date u_index cutoff score potential label_history_ready20 u_equity '
           'existing_risk existing_buffered_margin unit_risk_u unit_margin_u '
           'unit_fee_reserve_u target_qty_unscaled joint_scale target_qty_prefloor '
           'qty_cap round_lot allocated_risk allocated_buffered_margin allocated_fee '
           'budget_state').split()
NUMERIC = ('u_equity existing_risk existing_buffered_margin unit_risk_u unit_margin_u '
           'unit_fee_reserve_u target_qty_unscaled joint_scale target_qty_prefloor '
           'allocated_risk allocated_buffered_margin allocated_fee').split()
SOURCE_SHA = '2f5cf420113c3a3356993d1260e42b8e94c2a1e7c60c9b3443251a5c18ef15d6'
PROTOCOL_SHA = '31b7db98dabc1ca2861ca9039e558dba2adb3a2daaaa49338e00510f449ab9ce'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def number(text):
    d = Decimal(text)
    require(d.is_finite() and len(d.as_tuple().digits) <= 60
            and abs(d.as_tuple().exponent) <= 60, 'invalid printed decimal')
    return F(d)


def integer(text):
    x = number(text)
    require(x.denominator == 1 and abs(x) <= 10**15, 'invalid integer')
    return x.numerator


def candidate(row, position):
    require(all(row[k].strip() for k in ALLOWED), 'incomplete candidate')
    v = {k: number(row[k]) for k in NUMERIC}
    day = date.fromisoformat(row['u_date'])
    require(day >= date(2020, 1, 1) and row['cutoff'] ==
            ('2020-01-01' if day < date(2023, 1, 1) else '2023-01-01'), 'cutoff')
    require(number(row['score']) > 0 and number(row['potential']) == 1
            and number(row['label_history_ready20']) == 1, 'original action')
    require(integer(row['u_index']) >= 0, 'u index')
    b, lot = integer(row['qty_cap']), integer(row['round_lot'])
    require(b >= 0 and lot > 0 and b % lot == 0, 'quantity/lot')
    require(v['u_equity'] > 0 and v['unit_risk_u'] > 0 and v['unit_margin_u'] > 0
            and all(x >= 0 for k, x in v.items() if k != 'u_equity')
            and v['joint_scale'] <= 1, 'resources')
    return dict(row=row, position=position, b=b, lot=lot, **v)


def quantities_valid(c, q, single, risk_cap, margin_cap):
    families = [a['row']['family_id'] for a, x in zip(c, q) if x > 0]
    return (all(x >= 0 and x % a['lot'] == 0 and a['unit_risk_u'] * x <= single
                for a, x in zip(c, q))
            and sum(a['unit_risk_u'] * x for a, x in zip(c, q)) <= risk_cap
            and sum(a['unit_margin_u'] * x for a, x in zip(c, q)) <= margin_cap
            and len(families) == len(set(families)))


def verify_proof(proof, c, q, single, risk_cap, margin_cap):
    require(proof['valid'] == quantities_valid(c, q, single, risk_cap, margin_cap), 'proof validity')
    r = sum(a['unit_risk_u'] * x for a, x in zip(c, q))
    m = sum(a['unit_margin_u'] * x for a, x in zip(c, q))
    for key, expected in [('total_risk', r), ('total_margin', m),
                          ('risk_slack', risk_cap - r), ('margin_slack', margin_cap - m)]:
        require(F(proof[key]) == expected, 'proof ' + key)
    require(len(proof['individual']) == len(c), 'individual proof count')
    for a, x, p in zip(c, q, proof['individual']):
        require(p['budget_id'] == a['row']['budget_id'] and p['quantity'] == x
                and p['lot'] == a['lot'] and F(p['risk']) == a['unit_risk_u'] * x
                and F(p['single_limit']) == single
                and p['valid'] == (x >= 0 and x % a['lot'] == 0 and a['unit_risk_u'] * x <= single),
                'individual proof')
    f = [a['row']['family_id'] for a, x in zip(c, q) if x > 0]
    require(proof['one_per_family'] == (len(f) == len(set(f))), 'proof family')


def verify_vector(vector, group, altered):
    require(len(vector) == len(group), 'complete vector length')
    for (pos, row), v in zip(group, vector):
        try:
            original = integer(row['qty_cap'])
        except Exception:
            original = None
        for key in ('budget_id', 'event_id', 'family_id', 'budget_kind'):
            require(v[key] == row[key], 'vector identity')
        require(v['row_position'] == pos and v['quantity'] == altered.get(pos, original)
                and v['unchanged_nonnew'] == (row['budget_kind'] != 'new_entry'), 'vector quantity')


def review(protocol_path, audit_dir, receipt_dir):
    receipt_dir.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema='stage077_actual_independent_review_v1', critical=0, important=0,
                   status='started', source_sha256=SOURCE_SHA, protocol_sha256=PROTOCOL_SHA,
                   author_core_imports=0, author_suite_runs=0, model_recomputations=0,
                   financial_replays=0, new_fits=0, new_cash=0, sql=0, price_reads=0,
                   large_file_hashes=0, reservation_physical_reads=0, goal_complete=False)
    try:
        protocol_raw = protocol_path.read_bytes()
        require(hashlib.sha256(protocol_raw).hexdigest() == PROTOCOL_SHA, 'protocol binding')
        protocol = json.loads(protocol_raw)
        require(protocol['allowed_columns'] == ALLOWED, 'protocol whitelist')
        manifest_raw = (audit_dir / 'manifest.json').read_bytes()
        manifest = json.loads(manifest_raw)
        require(manifest['source_sha256'] == SOURCE_SHA and manifest['protocol_sha256'] == PROTOCOL_SHA,
                'actual source/protocol binding')
        require(manifest['status'] == 'completed_pending_independent_review'
                and manifest['actual_starts'] == 1 and manifest['automatic_retry'] is False, 'actual terminal')
        payload = {}
        for name, binding in manifest['files'].items():
            raw = (audit_dir / name).read_bytes()
            require(len(raw) == binding['bytes'] and hashlib.sha256(raw).hexdigest() == binding['sha256'],
                    'audit artifact byte binding ' + name)
            payload[name] = raw
        terminal = json.loads(payload['terminal.json'])
        require(terminal['status'] == manifest['status'] and terminal['reservation_physical_reads'] == 1,
                'single author actual read')
        source_path = Path(__file__).with_name('stage076_budget_support_audit.py')
        require(hashlib.sha256(source_path.read_bytes()).hexdigest() == SOURCE_SHA, 'source remains frozen')
        binding = protocol['inputs']['reservations']
        raw = Path(binding['path']).read_bytes()
        receipt['reservation_physical_reads'] = 1
        require(len(raw) == binding['bytes'] and hashlib.sha256(raw).hexdigest() == binding['sha256'], 'ledger binding')
        reader = csv.DictReader(io.StringIO(gzip.decompress(raw).decode()))
        require(set(ALLOWED).issubset(reader.fieldnames), 'ledger columns')
        rows = [{k: r[k] for k in ALLOWED} for r in reader]
        saved = list(csv.DictReader(io.StringIO(payload['all_u_rows.csv'].decode())))
        require(rows == saved and all(r['account_id'] == protocol['account'] for r in rows), 'all u rows and whitelist')
        bounds = json.loads(payload['candidate_bounds.json'])
        summaries = json.loads(payload['u_summary.json'])
        certificates = json.loads(payload['certificates.json'])
        classifications = json.loads(payload['row_classifications.json'])
        total = json.loads(payload['summary.json'])
        groups = defaultdict(list)
        for pos, row in enumerate(rows, 1):
            groups[(row['account_id'], row['scenario'], row['u_date'])].append((pos, row))
        by_bound = {p['row_position']: p for p in bounds}
        by_class = {p['row_position']: p for p in classifications}
        require(len(by_bound) == len(bounds) and len(by_class) == len(rows) == len(classifications), 'all row counts')
        require(len(groups) == len(summaries) == len(certificates), 'all u counts')
        decisions, examined_bounds = Counter(), set()
        for (key, group), s, cert in zip(sorted(groups.items()), summaries, certificates):
            uid = '|'.join(key)
            require(s['u_id'] == cert['u_id'] == uid and s['rows'] == len(group), 'u identity')
            require(s['derisk_actions_remain_possible'] is True and 'derisking' in s['negative_scope'], 'negative scope')
            c, bad = [], not all(key)
            for pos, row in group:
                state = 'preserved_nonproposal'
                if row['budget_kind'] == 'new_entry':
                    try:
                        c.append(candidate(row, pos)); state = 'complete_original_candidate'
                    except Exception:
                        bad = True; state = 'unknown_new_entry'
                p = by_class[pos]
                require(p['u_id'] == uid and p['rowkind'] == state and all(p[k] == row[k]
                        for k in ('budget_id', 'event_id', 'budget_kind', 'budget_state')), 'row classification')
                bad |= not row['budget_id'] or not row['event_id']
            c.sort(key=lambda a: (a['row']['event_id'], a['row']['budget_id']))
            require(s['candidates'] == len(c), 'candidate count')
            for field in ('budget_id', 'event_id'):
                ids = [r[field] for _, r in group if r['budget_kind'] == 'new_entry']
                bad |= len(ids) != len(set(ids))
            bad |= len({a['row']['family_id'] for a in c}) != len(c)
            bad |= len({a['row']['u_index'] for a in c}) > 1
            verify_vector(cert['original_vector'], group, {})
            decision, q, kind, chosen = 'unknown', None, None, None
            if c:
                first = c[0]; e = first['u_equity']
                er, em = first['existing_risk'], first['existing_buffered_margin']
                single, risk_cap, margin_cap = e / 400, max(F(0), e / 50 - er), max(F(0), e / 4 - em)
                expected_limits = dict(equity=e, existing_risk=er, existing_buffered_margin=em,
                                       single_risk=single, available_risk=risk_cap, available_margin=margin_cap)
                require(all(F(cert['limits'][k]) == v for k, v in expected_limits.items()), 'limits')
                for _, row in group:
                    try:
                        bad |= any(number(row[k]) != expected_limits[k] for k in
                                   ('existing_risk', 'existing_buffered_margin')) or number(row['u_equity']) != e
                    except Exception:
                        bad = True
                for a in c:
                    lot, r, m = a['lot'], a['unit_risk_u'], a['unit_margin_u']
                    individual = lot * (single // (r * lot))
                    upper = lot * min(single // (r * lot), risk_cap // (r * lot), margin_cap // (m * lot))
                    a['upper'] = upper; p = by_bound[a['position']]; examined_bounds.add(a['position'])
                    require(p['u_id'] == uid and p['budget_id'] == a['row']['budget_id']
                            and p['original_qty'] == a['b'] and p['round_lot'] == lot
                            and p['single_risk_upper_qty'] == individual and p['upper_qty'] == upper
                            and p['can_coordinate_increase'] == (upper >= a['b'] + lot), 'candidate upper bound')
                    unreachable = individual < lot
                    fractional = unreachable and 0 < a['target_qty_unscaled'] < lot
                    require(p['individual_one_lot_unreachable'] == unreachable
                            and p['original_cap_below_one_lot'] == (a['b'] < lot)
                            and p['joint_scale_below_one'] == (a['joint_scale'] < 1)
                            and p['untradable_fractional_proposal'] == fractional
                            and F(p['untradable_proposal_risk']) == (a['target_qty_unscaled'] * r if fractional else 0)
                            and F(p['untradable_proposal_margin']) == (a['target_qty_unscaled'] * m if fractional else 0),
                            'candidate disclosure')
                base = [a['b'] for a in c]
                verify_proof(cert['original_proof'], c, base, single, risk_cap, margin_cap)
                bad |= not quantities_valid(c, base, single, risk_cap, margin_cap)
                if not bad:
                    decision = 'no_positive_quantity_support'
                    for i, a in enumerate(c):
                        trial = base.copy(); trial[i] += a['lot']
                        if quantities_valid(c, trial, single, risk_cap, margin_cap):
                            q, chosen, kind = trial, a, 'direct_add'; break
                    if q is None:
                        for i, a in enumerate(c):
                            if a['upper'] >= a['b'] + a['lot']:
                                q, chosen, kind = [0] * len(c), a, 'competition_reallocation'
                                q[i] = a['b'] + a['lot']; break
                    if q is not None:
                        decision = 'positive_quantity_support'
                        require(quantities_valid(c, q, single, risk_cap, margin_cap), 'witness feasible')
                        verify_proof(cert['alternative_proof'], c, q, single, risk_cap, margin_cap)
                        verify_vector(cert['alternative_vector'], group, {a['position']: x for a, x in zip(c, q)})
                        require(cert['increased_budget_id'] == chosen['row']['budget_id']
                                and cert['increased_event_id'] == chosen['row']['event_id'], 'fixed witness ID')
            elif not bad:
                decision = 'no_original_new_entry_candidates'
            require(s['decision'] == decision and cert['kind'] == kind, 'complete increase existence')
            if q is None:
                require(cert['alternative_vector'] is None and cert['alternative_proof'] is None, 'no invented witness')
            require(bool(s['errors']) == bool(bad), 'unknown boundary status')
            require(s['rounding_direct_slack'] == (kind == 'direct_add'), 'direct slack disclosure')
            require(s['joint_scale_below_one'] == any(a['joint_scale'] < 1 for a in c)
                    and s['at_least_two_tradable_competition'] ==
                    (any(a['joint_scale'] < 1 for a in c) and sum(a['upper'] >= a['lot'] for a in c) >= 2),
                    'competition disclosure')
            require(s['individual_one_lot_unreachable'] == sum(by_bound[a['position']]['individual_one_lot_unreachable'] for a in c)
                    and s['original_cap_below_one_lot'] == sum(a['b'] < a['lot'] for a in c)
                    and s['untradable_fractional_proposals'] == sum(by_bound[a['position']]['untradable_fractional_proposal'] for a in c),
                    'u disclosure counts')
            decisions[decision] += 1
        require(examined_bounds == set(by_bound), 'every candidate reviewed')
        require(total['rows'] == len(rows) and total['u_groups'] == len(groups)
                and total['candidates'] == len(bounds) and total['decisions'] == dict(decisions), 'aggregate counts')
        require(total['outcome_fields_used'] == total['financial_replays'] == total['new_fit'] == total['new_cash'] == 0
                and total['support_is_not_profit'] is True and total['goal_complete'] is False, 'financial scope')
        receipt.update(status='accepted', rows=len(rows), u_groups=len(groups), candidates=len(bounds),
                       decisions=dict(decisions), ledger_sha256=binding['sha256'],
                       artifact_manifest_sha256=hashlib.sha256(manifest_raw).hexdigest(),
                       reviewer_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                       numeric_scope='exact saved-print rational geometry; baseline inconsistency is unknown; no epsilon',
                       conclusion='All source rows, u groups, candidate bounds, and deterministic certificates verified independently; no profit or execution inference')
    except Exception as exc:
        receipt.update(status='failed', important=1, error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        receipt['finished_utc'] = datetime.now(timezone.utc).isoformat()
        (receipt_dir / 'review_receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--protocol', type=Path, required=True)
    p.add_argument('--audit', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(review(a.protocol, a.audit, a.output), ensure_ascii=False, sort_keys=True))
