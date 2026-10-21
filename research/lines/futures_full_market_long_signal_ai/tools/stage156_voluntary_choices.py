"""Fixed155 voluntary calendar selection from complete accepted130 main scores.

Import has no I/O. No price/native NPZ arrays, labels, model or SQL are read.
Only root launches the actual CLI once into a fresh output directory.
"""
from __future__ import annotations
import argparse
import bisect
from collections import Counter
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
import time
import traceback
from datetime import datetime, timezone

LINE = Path(__file__).resolve().parents[1]
PROTOCOL = LINE/'outputs/stage155_voluntary_calendar_protocol/protocol.json'
PROTOCOL_SHA = '7ec4f92b31b46b04e0a17812878acb7f6305c9c476f9350d84bb7d873fe11e47'
POLICY_VERSION = 'stage155_voluntary_reselect_lead_months_1_v1_not_certified'
IDENTITY = ['sequence_index', 'event_id', 'product_id', 'family_id', 'u_date', 'u_index', 'reference_epoch']
SCORE_FIELDS = ['sequence_index', 'action_id', 'mother_sequence_index', 'mother_event_id', 'product_id',
    'family_id', 'u_date', 'u_index', 'reference_epoch', 'anchor_epoch', 'u_action_eligible', 'score', 'scope', 'cutoff']
AUDIT_FIELDS = SCORE_FIELDS + ['action_sequence_index', 'D_index', 'D_date', 'D_state', 'K_target_date',
    'K_index', 'K_date', 'K_state', 'K_after_sample_end', 'original_positive_eligible', 'new_eligible', 'eligibility_state']


def integer(value):
    number = float(value)
    if not math.isfinite(number) or not number.is_integer():
        raise ValueError('integer identity required')
    return int(number)


def calendar_boundary(epoch, calendar, sample_end):
    """Nominal identity only; unavailable K is never clipped to a terminal bar."""
    month = epoch.rsplit('.', 1)[-1]
    if not re.fullmatch(r'\d{6}', month) or not 1 <= int(month[4:]) <= 12:
        raise ValueError('complete YYYYMM epoch required')
    year, m = int(month[:4]), int(month[4:])
    year, m = (year-1, 12) if m == 1 else (year, m-1)
    target = f'{year:04d}-{m:02d}-01'
    if target < calendar[0]:
        k, day, state = None, None, 'before_calendar_blocked'
    else:
        index = bisect.bisect_left(calendar, target)
        k, day, state = (None, None, 'after_calendar_pending') if index == len(calendar) else (index, calendar[index], 'in_calendar')
    return dict(K_target_date=target, K_index=k, K_date=day, K_state=state,
                K_after_sample_end=(day > sample_end) if day is not None else target > sample_end)


def cutoff_for(day):
    return '2020-01-01' if day < '2023-01-01' else '2023-01-01'


def rank_action(row):
    return (-float(row['score']), row['reference_epoch'], row['action_id'])


def family_winners(proposals):
    winners = {}
    ordered = sorted(proposals.values(), key=lambda r: (integer(r['u_index']), r['family_id'],
        r['product_id'].endswith('_F'), r['product_id'], r['reference_epoch'], r['action_id']))
    for row in ordered:
        winners.setdefault((row['family_id'], integer(row['u_index'])), row)
    return {integer(row['mother_sequence_index']): row for row in winners.values()}


def select_full_pool(mothers, scores, calendar, sample_end, audit_sink=None, strict_cutoff=True):
    if not calendar or calendar != sorted(set(calendar)):
        raise ValueError('unique sorted source calendar required')
    parents = {integer(p['sequence_index']): dict(p) for p in mothers}
    if len(parents) != len(mothers) or len({p['event_id'] for p in mothers}) != len(mothers):
        raise ValueError('duplicate parent identity')
    old, new, observed, boundaries = {}, {}, set(), {}
    seen_actions, seen_sequences, counts, fold_counts = set(), set(), Counter(), Counter()
    audit_rows = [] if audit_sink is None else None
    for raw in scores:
        if raw['scope'] != 'main':
            counts['non_main_rows_not_selected'] += 1
            continue
        row = {key: raw[key] for key in SCORE_FIELDS}
        seq, parent_seq, u = integer(row['sequence_index']), integer(row['mother_sequence_index']), integer(row['u_index'])
        if seq in seen_sequences or row['action_id'] in seen_actions:
            raise ValueError('duplicate main action identity')
        seen_sequences.add(seq); seen_actions.add(row['action_id'])
        p = parents.get(parent_seq)
        if p is None:
            raise ValueError('child outside complete forward parent domain')
        for key in ('product_id', 'family_id', 'u_date'):
            if row[key] != p[key]:
                raise ValueError('child mother identity differs '+key)
        if (row['mother_event_id'] != p['event_id'] or row['anchor_epoch'] != p['reference_epoch']
                or u != integer(p['u_index']) or not 0 <= u < len(calendar) or calendar[u] != row['u_date']):
            raise ValueError('child original anchor/calendar/parent mismatch')
        expected_cutoff = cutoff_for(row['u_date'])
        if strict_cutoff and row['cutoff'] != expected_cutoff:
            raise ValueError('forward cutoff mismatch')
        score = float(row['score'])
        original = integer(row['u_action_eligible'])
        if original not in (0, 1):
            raise ValueError('original binary eligibility required')
        observed.add(parent_seq); counts['main_actions'] += 1; fold_counts[row['cutoff']] += 1
        epoch = row['reference_epoch']
        if epoch.rsplit('.', 1)[0] != row['product_id']:
            raise ValueError('action exact product differs')
        if epoch not in boundaries:
            boundaries[epoch] = calendar_boundary(epoch, calendar, sample_end)
        b = boundaries[epoch]
        D = u+1 if u+1 < len(calendar) else None
        D_date = calendar[D] if D is not None else None
        positive = original == 1 and math.isfinite(score) and score > 0
        if b['K_state'] == 'before_calendar_blocked':
            gate, state = False, 'K_before_calendar_blocked'
        elif D is None:
            gate, state = None, 'next_source_session_unknown'
        elif b['K_index'] is None:
            # D is within the calendar and strictly before the target month;
            # any eventual K is on/after target. No exact future K is invented.
            gate, state = D_date < b['K_target_date'], 'K_after_calendar_D_before_target'
        else:
            gate = D < b['K_index']
            state = 'D_before_K' if gate else 'D_on_or_after_K'
        eligible = None if gate is None and positive else int(positive and gate is True)
        if not positive:
            state = 'original_ineligible_or_nonpositive_score'
        if positive and (parent_seq not in old or rank_action(row) < rank_action(old[parent_seq])):
            old[parent_seq] = row
        if eligible == 1 and (parent_seq not in new or rank_action(row) < rank_action(new[parent_seq])):
            new[parent_seq] = row
        audit = dict(row, action_sequence_index=seq, D_index=D, D_date=D_date,
            D_state='unknown' if D is None else 'after_sample_end' if D_date > sample_end else 'in_sample_calendar',
            **b, original_positive_eligible=int(positive), new_eligible=eligible, eligibility_state=state)
        counts['new_eligible_actions'] += eligible == 1
        counts['unknown_eligible_actions'] += eligible is None
        counts['original_positive_eligible_actions'] += positive
        counts['reason:'+state] += 1
        if audit_sink is None:
            audit_rows.append(audit)
        else:
            audit_sink(audit)
    old_winners, new_winners = family_winners(old), family_winners(new)
    choices = []
    for seq, p in sorted(parents.items()):
        proposal, winner, original_winner = new.get(seq), new_winners.get(seq), old_winners.get(seq)
        state = ('selected' if winner else 'family_priority_suppressed' if proposal else
                 'no_observed_children' if seq not in observed else 'no_calendar_eligible_positive_action' if seq in old else 'no_original_eligible_positive_action')
        chosen = dict(p, proposed_action_id=proposal['action_id'] if proposal else '',
            proposed_epoch=proposal['reference_epoch'] if proposal else '', proposed_score=float(proposal['score']) if proposal else None,
            chosen_action_id=winner['action_id'] if winner else '',
            chosen_action_sequence_index=integer(winner['sequence_index']) if winner else -1,
            chosen_epoch=winner['reference_epoch'] if winner else '', anchor_epoch=p['reference_epoch'],
            score=float(winner['score']) if winner else None, selected=int(winner is not None),
            selection_state=state, scope='main', cutoff=cutoff_for(p['u_date']), arm='VOLUNTARY_RESELECT', policy='NARROW',
            old_chosen_action_id=original_winner['action_id'] if original_winner else '',
            old_chosen_epoch=original_winner['reference_epoch'] if original_winner else '',
            voluntary_policy_version=POLICY_VERSION, account_deadline_certified=False)
        choices.append(chosen)
    counts['parent_rows'] = len(choices)
    counts['selected_parent_rows'] = sum(c['selected'] for c in choices)
    counts['old_selected_parent_rows_reconstructed_from_same_scores'] = len(old_winners)
    counts['changed_parent_choices'] = sum(c['chosen_action_id'] != c['old_chosen_action_id'] for c in choices)
    differences = Counter()
    for c in choices:
        old_id, new_id = c['old_chosen_action_id'], c['chosen_action_id']
        state = 'unchanged' if old_id == new_id else 'newly_selected' if not old_id else 'removed' if not new_id else 'different_action'
        differences[(c['cutoff'], state)] += 1
    return dict(choices=choices, audit=audit_rows, boundaries=boundaries,
                summary=dict(counts=counts, main_actions_per_cutoff=dict(fold_counts),
                    parent_states=dict(Counter(c['selection_state'] for c in choices)),
                    parents_per_cutoff=dict(Counter(c['cutoff'] for c in choices)),
                    selected_per_cutoff=dict(Counter(c['cutoff'] for c in choices if c['selected'])),
                    old_selected_per_cutoff=dict(Counter(c['cutoff'] for c in choices if c['old_chosen_action_id'])),
                    selection_differences=[dict(cutoff=k[0], state=k[1], parents=v) for k, v in sorted(differences.items())]))


def binding(path):
    p = Path(path); h = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return dict(path=str(p.resolve()), bytes=p.stat().st_size, sha256=h.hexdigest())


def verify(b):
    if binding(b['path']) != {k: b[k] for k in ('path', 'bytes', 'sha256')}:
        raise ValueError('input identity differs '+b['path'])


def read_json(b):
    verify(b)
    return json.loads(Path(b['path']).read_text())


def write_json(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False); stream.write('\n')


def identity_rows(path, fields):
    with gzip.open(path, 'rt', newline='') as stream:
        reader = csv.reader(stream); header = next(reader); indices = [header.index(k) for k in fields]
        for cells in reader:
            yield {k: cells[i] for k, i in zip(fields, indices)}


def actual(output):
    output = Path(output); output.mkdir(parents=True, exist_ok=False); start = time.monotonic()
    write_json(output/'started.json', dict(schema='stage156_started_v1', policy_version=POLICY_VERSION,
        started_at=datetime.now(timezone.utc).isoformat(), auto_retry=False, fit=0, SQL=0, labels=0, prices=0))
    try:
        pb = binding(PROTOCOL)
        if pb['sha256'] != PROTOCOL_SHA:
            raise ValueError('frozen155 protocol changed')
        protocol = json.loads(PROTOCOL.read_text()); src = protocol['source_bindings']; inputs = {'protocol': pb}
        base = read_json(src['base_execution_protocol']); inputs['base_execution_protocol'] = src['base_execution_protocol']
        market_b = base['inputs']['market_protocol']; market = read_json(market_b); inputs['market_protocol'] = market_b
        cal_b = market['calendar']; verify(cal_b); inputs['calendar_only'] = cal_b
        import numpy as np
        a = np.load(io.BytesIO(Path(cal_b['path']).read_bytes()), allow_pickle=False)
        calendar = ([str(int(d))[:4]+'-'+str(int(d))[4:6]+'-'+str(int(d))[6:8] for d in a]
                    if a.dtype.kind in 'iu' else a.astype('datetime64[D]').astype(str).tolist())
        assert len(calendar) == 5587 and calendar == sorted(set(calendar))
        fit = read_json(src['fit_manifest']); inputs['fit_manifest'] = src['fit_manifest']
        if fit['actual_fit_calls_attempted'] != 6 or fit['actual_fit_calls_completed'] != 6:
            raise ValueError('accepted130 fit completion identity differs')
        records = read_json(fit['fit_records']); inputs['fit_records'] = fit['fit_records']
        expected = {r['cutoff']: r['prediction_children'] for r in records if r['scope'] == 'main'}
        for role in ('child_scores', 'mothers'):
            verify(src[role]); inputs[role] = src[role]
        mothers = list(identity_rows(src['mothers']['path'], IDENTITY))
        assert len(mothers) == 399252 and [integer(p['sequence_index']) for p in mothers] == list(range(399252))
        forward = [p for p in mothers if '2020-01-01' <= p['u_date'] <= '2026-10-16']
        assert len(forward) == 161014 and len({p['event_id'] for p in forward}) == 161014
        score_stream = identity_rows(src['child_scores']['path'], SCORE_FIELDS)
        with gzip.open(output/'action_eligibility.csv.gz', 'xt', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=AUDIT_FIELDS); writer.writeheader()
            result = select_full_pool(forward, score_stream, calendar, '2026-10-16', writer.writerow)
        summary = result['summary']
        assert summary['main_actions_per_cutoff'] == expected
        assert summary['counts']['main_actions'] == 966740 and summary['counts']['non_main_rows_not_selected'] == 966740
        assert Counter(c['cutoff'] for c in result['choices']) == {'2020-01-01': 71344, '2023-01-01': 89670}
        with gzip.open(output/'choices_main.csv.gz', 'xt', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(result['choices'][0])); writer.writeheader(); writer.writerows(result['choices'])
        write_json(output/'boundaries.json', dict(schema='stage156_voluntary_K_only_v1', policy_version=POLICY_VERSION,
            account_deadline_certified=False, calendar=cal_b, sample_end='2026-10-16', epochs=result['boundaries']))
        summary.update(schema='stage156_full_pool_choice_summary_v1', policy_version=POLICY_VERSION,
            fit=0, SQL=0, labels=0, prediction_recalculations=0, cash=0, price_arrays_read=0,
            account_deadline_certified=False, strict_cutoff_ready=False,
            sequence_alias_evidence='accepted130 line132 asserts sequence_index==action_sequence_index; line167 writes pred.sequence_index',
            zero_opportunities_stop_before_cash=summary['counts']['selected_parent_rows'] == 0)
        write_json(output/'summary.json', summary)
        terminal = dict(schema='stage156_terminal_v1', status='completed', exit_code=0,
            elapsed_seconds=time.monotonic()-start, main_actions=966740, parents=161014, fit=0, SQL=0, labels=0, cash=0)
        write_json(output/'terminal.json', terminal)
        artifacts = {role: binding(output/name) for role, name in [('choices_main', 'choices_main.csv.gz'),
            ('action_eligibility', 'action_eligibility.csv.gz'), ('boundaries', 'boundaries.json'),
            ('summary', 'summary.json'), ('started', 'started.json'), ('terminal', 'terminal.json')]}
        write_json(output/'manifest.json', dict(schema='stage156_voluntary_choices_manifest_v1', artifacts=artifacts,
            inputs=inputs, implementation=binding(__file__), sequence_alias_source=binding(Path(__file__).with_name('stage130_contract_choice_fit.py')),
            source_bundle=[binding(__file__), binding(Path(__file__).with_name('test_stage156_voluntary_choices.py'))],
            policy_version=POLICY_VERSION, not_certified=True, old_effective_boundary_owner='Stage157 cash author',
            parent_rows=161014, main_action_rows=966740, new_fit=0, new_cash=0, new_SQL=0, new_labels=0,
            production_qualified=False, increased_betting_qualified=False, cumulative_fit=397, cumulative_cash=206))
        return terminal
    except BaseException:
        if not (output/'terminal.json').exists():
            write_json(output/'terminal.json', dict(schema='stage156_terminal_v1', status='failed', exit_code=1,
                elapsed_seconds=time.monotonic()-start, traceback=traceback.format_exc(), auto_retry=False, fit=0, SQL=0, labels=0, cash=0))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); print(json.dumps(actual(args.output), ensure_ascii=False))


if __name__ == '__main__':
    main()
