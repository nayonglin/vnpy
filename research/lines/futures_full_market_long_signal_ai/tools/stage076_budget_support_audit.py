"""Stage075's finite, outcome-blind integer support audit; import is pure.

No author kernels, market data, optimizer, fitting or cash replay are imported.
Saved decimals are treated exactly; an infeasible printed baseline is UNKNOWN,
never repaired with tolerance. A witness establishes an action, never a profit.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timezone
from decimal import Decimal, Inexact, localcontext
import gzip
import hashlib
import io
import json
from pathlib import Path


FROZEN_PROTOCOL_SHA = '31b7db98dabc1ca2861ca9039e558dba2adb3a2daaaa49338e00510f449ab9ce'
ALLOWED_COLUMNS = (
    'budget_id budget_kind account_id scenario event_id product_id family_id '
    'u_date u_index cutoff score potential label_history_ready20 u_equity '
    'existing_risk existing_buffered_margin unit_risk_u unit_margin_u '
    'unit_fee_reserve_u target_qty_unscaled joint_scale target_qty_prefloor '
    'qty_cap round_lot allocated_risk allocated_buffered_margin allocated_fee '
    'budget_state').split()
NUMERIC = ('u_equity existing_risk existing_buffered_margin unit_risk_u '
           'unit_margin_u unit_fee_reserve_u target_qty_unscaled joint_scale '
           'target_qty_prefloor allocated_risk allocated_buffered_margin '
           'allocated_fee').split()
NEGATIVE_SCOPE = ('No coordinate can increase within the original complete u '
                  'new-entry candidate domain; derisking, other candidate '
                  'domains and other information mechanisms are not rejected.')


class AuthorizationError(ValueError):
    pass


def _d(value):
    result = Decimal(str(value))
    if not result.is_finite() or len(result.as_tuple().digits) > 60 or abs(result.as_tuple().exponent) > 60:
        raise ValueError('missing/nonfinite/excessive saved decimal')
    return result


def _integer(value):
    result = _d(value)
    if result != result.to_integral_value() or abs(result) > 10**15:
        raise ValueError('quantity/index is not a bounded integer')
    return int(result)


def _floor_ratio(a, b):
    # Integer ratios avoid a rounded Decimal division moving a floor boundary.
    an, ad = a.as_integer_ratio()
    bn, bd = b.as_integer_ratio()
    return (an * bd) // (ad * bn)


def _jsonable(value):
    if isinstance(value, Decimal):
        text = format(value, 'f')
        return text.rstrip('0').rstrip('.') if '.' in text else text
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _candidate(row, position):
    if any(not row.get(key, '').strip() for key in ALLOWED_COLUMNS):
        raise ValueError('new_entry has missing required saved u field')
    values = {key: _d(row[key]) for key in NUMERIC}
    day = date.fromisoformat(row['u_date'])
    expected_cutoff = '2020-01-01' if day < date(2023, 1, 1) else '2023-01-01'
    if day < date(2020, 1, 1) or row['cutoff'] != expected_cutoff:
        raise ValueError('saved forward-block cutoff/u_date mismatch')
    if _d(row['score']) <= 0 or _d(row['potential']) != 1 or _d(row['label_history_ready20']) != 1:
        raise ValueError('new_entry is not an original ready20 positive-score action')
    if _integer(row['u_index']) < 0:
        raise ValueError('negative u index')
    b, lot = _integer(row['qty_cap']), _integer(row['round_lot'])
    if b < 0 or lot <= 0 or b % lot:
        raise ValueError('invalid original quantity or round lot')
    if (values['u_equity'] <= 0 or values['unit_risk_u'] <= 0 or values['unit_margin_u'] <= 0
            or any(value < 0 for key, value in values.items() if key != 'u_equity')
            or values['joint_scale'] > 1):
        raise ValueError('invalid nonnegative saved resource or scale')
    return dict(row=row, position=position, b=b, lot=lot, **values)


def _proof(candidates, quantities, limits):
    risk = sum((c['unit_risk_u'] * q for c, q in zip(candidates, quantities)), Decimal(0))
    margin = sum((c['unit_margin_u'] * q for c, q in zip(candidates, quantities)), Decimal(0))
    individual = [dict(budget_id=c['row']['budget_id'], quantity=q,
                       risk=c['unit_risk_u'] * q,
                       single_limit=limits['single_risk'],
                       lot=c['lot'], valid=(q >= 0 and q % c['lot'] == 0
                           and c['unit_risk_u'] * q <= limits['single_risk']))
                  for c, q in zip(candidates, quantities)]
    families = [c['row']['family_id'] for c, q in zip(candidates, quantities) if q > 0]
    valid = (all(x['valid'] for x in individual) and risk <= limits['available_risk']
             and margin <= limits['available_margin'] and len(families) == len(set(families)))
    return dict(valid=valid, individual=individual, total_risk=risk,
                total_margin=margin, risk_slack=limits['available_risk'] - risk,
                margin_slack=limits['available_margin'] - margin,
                one_per_family=(len(families) == len(set(families))))


def _vector(group, quantities):
    result = []
    for position, row in group:
        try:
            original = _integer(row.get('qty_cap', ''))
        except (ValueError, ArithmeticError):
            original = None
        result.append(dict(row_position=position, budget_id=row.get('budget_id', ''),
                           event_id=row.get('event_id', ''), family_id=row.get('family_id', ''),
                           budget_kind=row.get('budget_kind', ''),
                           rowkind=('new_entry' if row.get('budget_kind') == 'new_entry'
                                    else row.get('budget_kind') or 'nonproposal_or_rejection'),
                           quantity=quantities.get(position, original),
                           unchanged_nonnew=(row.get('budget_kind') != 'new_entry')))
    return result


def audit_rows(rows):
    """Pure synthetic/accepted-byte analysis; projects away all future columns."""
    with localcontext() as context:
        context.prec = 256
        context.traps[Inexact] = True
        clean = [{key: str(row.get(key, '') or '') for key in ALLOWED_COLUMNS} for row in rows]
        groups = defaultdict(list)
        for position, row in enumerate(clean, 1):
            groups[(row['account_id'], row['scenario'], row['u_date'])].append((position, row))
        bounds, summaries, certificates, classifications = [], [], [], []
        for key, group in sorted(groups.items()):
            u_id = '|'.join(key)
            errors, candidates = [], []
            for position, row in group:
                state, reason = 'preserved_nonproposal', ''
                if row['budget_kind'] == 'new_entry':
                    try:
                        candidates.append(_candidate(row, position))
                        state = 'complete_original_candidate'
                    except (ValueError, ArithmeticError) as exc:
                        state, reason = 'unknown_new_entry', str(exc)
                        errors.append(f'row {position}: {reason}')
                classifications.append(dict(u_id=u_id, row_position=position,
                    budget_id=row['budget_id'], event_id=row['event_id'],
                    budget_kind=row['budget_kind'], budget_state=row['budget_state'],
                    rowkind=state, reason=reason))
            candidates.sort(key=lambda c: (c['row']['event_id'], c['row']['budget_id']))
            summary = dict(u_id=u_id, rows=len(group), candidates=len(candidates),
                decision='unknown', errors=errors, joint_scale_below_one=False,
                at_least_two_tradable_competition=False, rounding_direct_slack=False,
                individual_one_lot_unreachable=0, original_cap_below_one_lot=0,
                untradable_fractional_proposals=0, derisk_actions_remain_possible=True,
                negative_scope=NEGATIVE_SCOPE)
            certificate = dict(u_id=u_id, kind=None, limits=None,
                original_vector=_vector(group, {}), alternative_vector=None,
                original_proof=None, alternative_proof=None,
                printed_baseline_policy='Any exact saved-decimal violation is unknown; no epsilon.')
            if not all(key) or any(not r['budget_id'] or not r['event_id'] for _, r in group):
                errors.append('missing original u/account/scenario or row identity')
            for field in ('budget_id', 'event_id'):
                identities = [r[field] for _, r in group if r['budget_kind'] == 'new_entry']
                if len(identities) != len(set(identities)):
                    errors.append('duplicate new-entry ' + field)
            if len({c['row']['family_id'] for c in candidates}) != len(candidates):
                errors.append('multiple original candidates in one family')
            if len({c['row']['u_index'] for c in candidates}) > 1:
                errors.append('inconsistent saved u index')
            if candidates:
                first = candidates[0]
                E = first['u_equity']
                risk, margin = first['existing_risk'], first['existing_buffered_margin']
                # Nonproposal/reduction rows never release or add to these frozen resources.
                for _, row in group:
                    for field, expected in [('u_equity', E), ('existing_risk', risk),
                                             ('existing_buffered_margin', margin)]:
                        try:
                            if _d(row[field]) != expected:
                                errors.append('inconsistent frozen u resource ' + field)
                        except (ValueError, ArithmeticError):
                            errors.append('missing frozen u resource ' + field)
                limits = dict(equity=E, existing_risk=risk, existing_buffered_margin=margin,
                    single_risk=Decimal('.0025') * E,
                    available_risk=max(Decimal(0), Decimal('.02') * E - risk),
                    available_margin=max(Decimal(0), Decimal('.25') * E - margin))
                certificate['limits'] = limits
                for c in candidates:
                    r, m, lot = c['unit_risk_u'], c['unit_margin_u'], c['lot']
                    single = lot * _floor_ratio(limits['single_risk'], r * lot)
                    upper = lot * min(single // lot,
                        _floor_ratio(limits['available_risk'], r * lot),
                        _floor_ratio(limits['available_margin'], m * lot))
                    c['upper'] = upper
                    impossible = single < lot
                    fractional = impossible and 0 < c['target_qty_unscaled'] < lot
                    bounds.append(dict(u_id=u_id, row_position=c['position'],
                        event_id=c['row']['event_id'], budget_id=c['row']['budget_id'],
                        family_id=c['row']['family_id'], original_qty=c['b'], round_lot=lot,
                        single_risk_upper_qty=single, upper_qty=upper,
                        can_coordinate_increase=(upper >= c['b'] + lot),
                        individual_one_lot_unreachable=impossible,
                        original_cap_below_one_lot=(c['b'] < lot),
                        joint_scale_below_one=(c['joint_scale'] < 1),
                        untradable_fractional_proposal=fractional,
                        untradable_proposal_risk=(c['target_qty_unscaled'] * r if fractional else Decimal(0)),
                        untradable_proposal_margin=(c['target_qty_unscaled'] * m if fractional else Decimal(0))))
                    summary['individual_one_lot_unreachable'] += impossible
                    summary['original_cap_below_one_lot'] += c['b'] < lot
                    summary['untradable_fractional_proposals'] += fractional
                summary['joint_scale_below_one'] = any(c['joint_scale'] < 1 for c in candidates)
                summary['at_least_two_tradable_competition'] = (summary['joint_scale_below_one']
                    and sum(c['upper'] >= c['lot'] for c in candidates) >= 2)
                baseline = [c['b'] for c in candidates]
                certificate['original_proof'] = _proof(candidates, baseline, limits)
                if not certificate['original_proof']['valid']:
                    errors.append('printed_decimal_baseline_not_feasible_unknown')
                if not errors:
                    chosen, quantities, kind = None, None, None
                    for i, c in enumerate(candidates):
                        trial = baseline.copy()
                        trial[i] += c['lot']
                        if _proof(candidates, trial, limits)['valid']:
                            chosen, quantities, kind = c, trial, 'direct_add'
                            break
                    if quantities is None:
                        for i, c in enumerate(candidates):
                            if c['upper'] >= c['b'] + c['lot']:
                                chosen, quantities, kind = c, [0] * len(candidates), 'competition_reallocation'
                                quantities[i] = c['b'] + c['lot']
                                break
                    if quantities is None:
                        summary['decision'] = 'no_positive_quantity_support'
                    else:
                        proof = _proof(candidates, quantities, limits)
                        if not proof['valid']:
                            raise ValueError('internal witness violates exact constraints')
                        certificate.update(kind=kind, increased_budget_id=chosen['row']['budget_id'],
                            increased_event_id=chosen['row']['event_id'],
                            alternative_vector=_vector(group, {c['position']: q for c, q in zip(candidates, quantities)}),
                            alternative_proof=proof)
                        summary['decision'] = 'positive_quantity_support'
                        summary['rounding_direct_slack'] = kind == 'direct_add'
            elif not errors:
                summary['decision'] = 'no_original_new_entry_candidates'
            certificates.append(certificate)
            summaries.append(summary)
        counts = Counter(s['decision'] for s in summaries)
        return _jsonable(dict(all_u_rows=clean, candidate_bounds=bounds,
            row_classifications=classifications, u_summary=summaries, certificates=certificates,
            summary=dict(rows=len(clean), u_groups=len(summaries), candidates=len(bounds),
                decisions=dict(counts), financial_replays=0, new_fit=0, new_cash=0,
                outcome_fields_used=0, goal_complete=False,
                fractional_proposal_disclosure='Saved proposal resource consumption is descriptive; no counterfactual benefit or causal drag is claimed.',
                support_is_not_profit=True, negative_scope=NEGATIVE_SCOPE)))


def _write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def run_actual(protocol_path, protocol_sha256, authorize_source_sha256, output):
    """Only actual entrypoint. Root must bind this exact script and frozen protocol."""
    if protocol_sha256 != FROZEN_PROTOCOL_SHA:
        raise AuthorizationError('root must authorize the exact frozen Stage075 protocol')
    source = Path(__file__).read_bytes()
    script_sha = hashlib.sha256(source).hexdigest()
    if authorize_source_sha256 != script_sha:
        raise AuthorizationError('root source SHA does not match this exact script')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    terminal = dict(status='started', actual_starts=1, reservation_physical_reads=0,
                    source_sha256=script_sha, protocol_sha256=protocol_sha256,
                    automatic_retry=False, new_fit=0, new_cash=0)
    try:
        protocol_bytes = Path(protocol_path).read_bytes()
        if hashlib.sha256(protocol_bytes).hexdigest() != protocol_sha256:
            raise ValueError('protocol bytes changed')
        protocol = json.loads(protocol_bytes)
        if protocol['allowed_columns'] != ALLOWED_COLUMNS:
            raise ValueError('frozen u whitelist mismatch')
        binding = protocol['inputs']['reservations']
        terminal['reservation_physical_reads'] = 1
        raw = Path(binding['path']).read_bytes()  # the sole physical ledger read
        if len(raw) != binding['bytes'] or hashlib.sha256(raw).hexdigest() != binding['sha256']:
            raise ValueError('accepted reservation byte binding mismatch')
        reader = csv.DictReader(io.StringIO(gzip.decompress(raw).decode('utf-8')))
        if not set(ALLOWED_COLUMNS).issubset(reader.fieldnames or []):
            raise ValueError('accepted CSV lacks frozen u columns')
        result = audit_rows(reader)
        if any(r['account_id'] != protocol['account'] for r in result['all_u_rows']):
            raise ValueError('ledger is not the single frozen account')
        with (output / 'all_u_rows.csv').open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=ALLOWED_COLUMNS)
            writer.writeheader()
            writer.writerows(result.pop('all_u_rows'))
        for name, value in result.items():
            _write_json(output / (name + '.json'), value)
        terminal['status'] = 'completed_pending_independent_review'
        terminal['reservation_sha256'] = binding['sha256']
    except Exception as exc:
        terminal.update(status='failed_no_retry', error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        terminal['finished_utc'] = datetime.now(timezone.utc).isoformat()
        _write_json(output / 'terminal.json', terminal)
        files = {p.name: dict(bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                 for p in sorted(output.iterdir()) if p.is_file() and p.name != 'manifest.json'}
        _write_json(output / 'manifest.json', dict(schema='stage076_budget_support_manifest_v1',
            source_sha256=script_sha, protocol_sha256=protocol_sha256, files=files,
            status=terminal['status'], actual_starts=1, automatic_retry=False))
    return terminal


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--protocol-sha256', required=True)
    parser.add_argument('--authorize-source-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(run_actual(args.protocol, args.protocol_sha256,
                               args.authorize_source_sha256, args.output), ensure_ascii=False))


if __name__ == '__main__':
    main()
