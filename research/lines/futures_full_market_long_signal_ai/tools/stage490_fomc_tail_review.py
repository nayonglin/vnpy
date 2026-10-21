"""Final bounded tail only: new choices, eight saved ledgers, one native cache.

Never calls review_source/review_models/review_forward or opens old COMMON,
scores,156,SQL,original129 Y or original CSV/H5. Completed phases are inherited.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import time
import traceback

import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
spec = importlib.util.spec_from_file_location('tail490_pure_helpers', TOOLS / 'stage490_fomc_economic_review.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def check_choices(r, fit, f, calendar, folder):
    art = fit['artifacts']
    mothers = r.table(art['forward_mothers_projection'])
    overlay = r.table(art['event_score_overlays'])
    for col in ['score_A', 'score_' + v.ARMS[0], 'score_' + v.ARMS[1]]:
        overlay[col] = v.float_tokens(overlay[col])
    choices = {(s, a): r.table(art['choices_' + s + '_' + a]) for s in v.SCOPES for a in ('A',) + v.ARMS}
    event_days = set(f.loc[f.u_date.ge('2020-01-01'), 'u_date'])
    counts = []
    bounds = {}
    for scope in v.SCOPES:
        parents = mothers if scope == 'main' else mothers.loc[mothers.family_id.map(v.family_hash).eq(int(scope[-1]))]
        rows = overlay.loc[overlay.scope.eq(scope)].copy()
        v.nums(rows, ['u_index', 'u_action_eligible', 'mother_sequence_index', 'sequence_index'])
        row_domains = np.array([v.domain(x.reference_epoch, int(x.u_index), calendar, bounds) for x in rows.itertuples()])
        baseline = choices[scope, 'A']
        for arm in ('A',) + v.ARMS:
            saved = choices[scope, arm]
            v.identities(saved, parents, list(mothers), 'tail full mother identity')
            event = saved.u_date.isin(event_days)
            if arm != 'A':
                for col in ['chosen_action_id', 'selected', 'chosen_epoch', 'anchor_epoch',
                            'chosen_action_sequence_index', 'selection_state', 'proposed_action_id', 'proposed_epoch']:
                    assert saved.loc[~event, col].tolist() == baseline.loc[~event, col].tolist(), ('non-event fallback', scope, arm, col)
                v.eq(v.float_tokens(saved.loc[~event, 'score']), v.float_tokens(baseline.loc[~event, 'score']),
                     'tail non-event exact policy score', 1e-12, 0.)
            score_column = 'score_A' if arm == 'A' else 'score_' + arm
            active = rows.copy()
            active['_s'] = active[score_column].to_numpy(float)
            positive = active.u_action_eligible.eq(1) & active._s.gt(0)
            observed = set(active.mother_sequence_index.astype(int))
            original_positive = set(active.loc[positive, 'mother_sequence_index'].astype(int))
            proposals = active.loc[positive & row_domains].sort_values(
                ['mother_sequence_index', '_s', 'reference_epoch', 'action_id'], ascending=[True, False, True, True],
                kind='stable').drop_duplicates('mother_sequence_index')
            proposals['_F'] = proposals.product_id.str.endswith('_F').astype(int)
            winners = proposals.sort_values(['u_index', 'family_id', '_F', 'product_id', 'reference_epoch', 'action_id'],
                                            kind='stable').drop_duplicates(['family_id', 'u_index'])
            proposals = proposals.set_index('mother_sequence_index')
            winners = winners.set_index('mother_sequence_index')
            for q in saved.loc[event].to_dict('records'):
                seq = int(q['sequence_index']); win = winners.loc[seq] if seq in winners.index else None
                prop = proposals.loc[seq] if seq in proposals.index else None
                assert q['chosen_action_id'] == (win.action_id if win is not None else '')
                assert int(q['selected']) == int(win is not None)
                assert q['chosen_epoch'] == (win.reference_epoch if win is not None else '')
                assert int(q['chosen_action_sequence_index']) == (int(win.sequence_index) if win is not None else -1)
                assert q['proposed_action_id'] == (prop.action_id if prop is not None else '')
                assert q['proposed_epoch'] == (prop.reference_epoch if prop is not None else '')
                state = ('selected' if win is not None else 'family_priority_suppressed' if prop is not None else
                         'no_observed_children' if seq not in observed else 'no_calendar_eligible_positive_action'
                         if seq in original_positive else 'no_original_eligible_positive_action')
                assert q['selection_state'] == state, ('tail event selection state', seq)
                v.eq(float(q['score']) if q['score'] else np.nan,
                     float(win._s) if win is not None else np.nan, 'tail event chosen score', 1e-12, 0.)
            counts.append(dict(scope=scope, arm=arm, complete_parents=len(saved), event_parents=int(event.sum()),
                               selected=int(pd.to_numeric(saved.selected).sum())))
    report = dict(all_nine_choice_tables_checked=True, scope_arm_counts=counts,
                  event_choices_from_previously_verified_new_overlays=True,
                  non_event_B_C_exactly_match_new_A=True, main_A_identity_inherits_completed_strict156_check=True,
                  held_non_event_A_historical_absolute_winner_independently_recertified=False,
                  held_non_event_A_boundary='inherited frozen accepted code; no second oldscore stream',
                  CSV_roundoff_tolerance=1e-12, identities_eligibility_chosen_actions_strict=True)
    v.write(folder / 'tail_choices_phase.json', report)
    return mothers, choices, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['protocol', 'source-manifest', 'fit-manifest', 'cash-manifest']:
        parser.add_argument('--' + name, required=True)
        parser.add_argument('--' + name + '-sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    folder = Path(args.output).resolve()
    assert LINE / 'outputs/stage490_fomc_economic_independent_review' in folder.parents
    folder.mkdir(parents=True, exist_ok=False)
    began = time.monotonic(); status = 'failed'; error = None
    r = v.Reader()
    v.write(folder / 'started.json', dict(started_at=datetime.now(timezone.utc).isoformat(), arguments=vars(args),
              exact_tail_only=True, old_COMMON_scores156_SQL_original129Y_CSV_H5_forbidden=True))
    try:
        docs = {}
        for name in ['protocol', 'source_manifest', 'fit_manifest', 'cash_manifest']:
            b = v.bind(getattr(args, name))
            assert b['sha256'] == getattr(args, name + '_sha256')
            docs[name] = r.doc(b)
        p, source, fit, cm = (docs[x] for x in ['protocol', 'source_manifest', 'fit_manifest', 'cash_manifest'])
        assert v.bind(args.protocol)['sha256'] == v.PROTO_SHA
        root = LINE / 'outputs/stage490_fomc_economic_independent_review'
        inherited = {}
        for name, rel, digest in [
            ('source', 'actual_review_run1/source_phase.json', 'c57aa3b166ff16dec8de183d973afa174fae36a569cb7c1dc470cd91bcaa7028'),
            ('partial', 'partial_review_receipt.json', 'c19ce0839d0574b85f120c532710bee5a6a37d99ee4519e15e66b708408e7c3b')]:
            b = v.bind(root / rel); assert b['sha256'] == digest; inherited[name] = dict(binding=b, receipt=r.doc(b))
        partial = inherited['partial']['receipt']
        assert partial['cumulative_old_input_reads'] == dict(pre_exact_SQL=1, original_COMMON=1,
                original156_identity_projection=1, original130_scores=1)
        assert not partial['completed'] and partial['native_cache_reads'] == 0
        phase = v.bind(root / 'actual_review_continue1/model_phase.json')
        model_receipt = r.doc(phase)
        assert model_receipt['heads_checked'] == 12 and model_receipt['projected_COMMON_scalars'] == 1406314
        inherited['model_phase'] = phase
        r.register(cm['artifacts'])
        calendar0 = np.load(io.BytesIO(r.read(p['input_bindings']['calendar'])), allow_pickle=False)
        calendar = [f'{int(x):08d}'[:4] + '-' + f'{int(x):08d}'[4:6] + '-' + f'{int(x):08d}'[6:] for x in calendar0]
        f = r.table(fit['artifacts']['event_features_labels'])
        v.nums(f, ['net_R_stress'])
        mothers, choices, choice_report = check_choices(r, fit, f, calendar, folder)
        causal = r.table(fit['artifacts']['causal_actions_projection'])
        economics = r.doc(p['source_fields']['inputs']['economics'])['instruments']
        cash_report = v.review_cash(r, p, fit, cm, mothers, causal, choices, f, calendar, economics, folder)
        assert v.READS == Counter(native_cache=1), dict(v.READS)
        # Only unfinished cash artifacts are closed here; source/models are inherited.
        r.finish()
        receipt = dict(schema='stage490_final_tail_review_v1', completed_source_model_maincash=True,
             completed_current_tail=True, actual_input_budget_current=dict(v.READS),
             cumulative_original_input_counts=dict(pre_exact_SQL=1, original_COMMON=1, original130_scores=1,
                                                   original156_identity_projection=1, native_cache=1),
             inherited_phases=inherited, choices=choice_report, cash=cash_report,
             max_abs_errors=v.ERRORS, prior_nonmaterial_CSV_roundoff=4.440892098500626e-16,
             reviewer_predictive_fits=0, reviewer_strategy_cash_replays=0, original129Y_CSV_H5_mother_rescans=0,
             source_model_maincash_material_findings=dict(P0=0, P1=0, P2=0),
             full_all_scope_independent_P0_P1_P2_claim=False,
             held_absolute_non_event_A_winner_scope_inherited=True,
             strict_historical_first_seen_PIT=False, alpha_proved=False, goal_complete=False)
        v.write(folder / 'review_receipt.json', receipt)
        status = 'completed'
        print(json.dumps(dict(status=status, completed_source_model_maincash=True, output=str(folder)), ensure_ascii=False), flush=True)
    except BaseException as exc:
        error = dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
        v.write(folder / 'failure.json', error)
        raise
    finally:
        v.write(folder / 'terminal.json', dict(status=status, elapsed_seconds=time.monotonic() - began,
                error=error, actual_input_budget_current=dict(v.READS), no_automatic_retry=True,
                reviewer_predictive_fits_cash_replays=0))


if __name__ == '__main__':
    main()
