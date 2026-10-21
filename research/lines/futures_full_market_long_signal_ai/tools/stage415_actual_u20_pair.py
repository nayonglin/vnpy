"""One explicit u20 paired paper step through the unchanged 382/376 bridges."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import time

LINE = Path(__file__).resolve().parent.parent
OUT = LINE / 'outputs/stage415_u20_paired_actual/actual_run1'
DECISION = LINE / 'outputs/stage363_u20_observation_acceptance/decision.json'
MANIFEST = LINE / 'outputs/stage361_u20_forward_actual/actual_batch002_network_corrected/manifest.json'


def binding(path):
    path = Path(path)
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def write(name, value):
    path = OUT / name
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')
    return binding(path)


def main():
    if OUT.exists():
        raise FileExistsError('one fresh415 actual directory required; never rerun a partial pair')
    decision = json.loads(DECISION.read_text())
    if (decision['status'] != 'accepted_for_causal_paired_research_with_acquisition_deviation'
            or decision['authorized_paired_calls'] != 1
            or decision['accepted_manifest'] != binding(MANIFEST)):
        raise ValueError('root363 exact corrected source acceptance required')
    OUT.mkdir(parents=True)
    started = datetime.now(timezone.utc).isoformat()
    tick = time.monotonic()
    write('started.json', dict(started_at=started, decision=binding(DECISION),
        entrypoint=binding(__file__), no_collection=True, no_refit=True,
        strict_original_single_acquisition_adherence=False))
    phase = 'load_unchanged_bridge'
    try:
        spec = importlib.util.spec_from_file_location('stage415_original382', LINE / 'tools/stage382_shared_input_restore.py')
        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)
        profiles = bridge.profiles()
        caller = profiles.components().caller
        phase = 'restore_actual_composed_once'
        composed = bridge.restore_composed(binding(MANIFEST))
        composed_id = profiles.composed_identity(composed)
        acceptance = dict(schema=profiles.ACCEPTANCE_SCHEMA, accepted_by='root', status='accepted',
            target_u='2026-10-20', completed361=True, passed362=True, accepted363=True,
            composed_identity=composed_id, clock_domains_sha256=caller._hash(composed['clock_domains']),
            evidence=dict(terminal361=decision['accepted_terminal'], review362=decision['accepted_review'],
                decision363=binding(DECISION)),
            legacy_phase_labels='361/362 denote collection/review phases. Their original run1 failed; only separately bound corrected batch002/run2 are accepted.',
            original_attempt_failed=True, operational_amendment=decision['operational_amendment'],
            strict_original_single_acquisition_adherence=False,
            no_prior_empty_unfunded_seal_reuse=True)
        acceptance_b = write('same_composed_acceptance.json', acceptance)
        write('restoration_receipt.json', caller._clean(dict(restoration=composed['restoration'],
            composed_identity=composed_id, clock_domains=composed['clock_domains'],
            source_manifest=binding(MANIFEST), new_appends=0, model_inference=0)))
        phase = 'load_two_existing_contexts'
        previous = json.loads((LINE / 'outputs/stage384_shared_input_wiring_decision/actual_context_binding.json').read_text())
        contexts = dict(baseline=bridge.load_baseline_context(binding(
            LINE / 'outputs/stage370_paper_initialization_actual/actual_run1/manifest.json')),
            latest=profiles.load_context(previous['contexts']['latest']['initialization_envelope']))
        before = {name: caller._hash(context['states']) for name, context in contexts.items()}
        write('context_before.json', dict(states_sha256=before,
            T_init={name: c['T_init'] for name,c in contexts.items()},
            T_model={name: c['profile']['T_model'] for name,c in contexts.items()},
            created_accounts=0, reused_original_own_accounts=True))
        phase = 'process_pair_once_no_reentry'
        result = profiles.process_pair(composed, acceptance_b, contexts)
        phase = 'persist_complete_pair'
        result_b = write('profile_results.json', caller._clean(result))
        checkpoints = {}
        for name,value in result['profiles'].items():
            checkpoints[name] = {}
            for scenario,state in value['states'].items():
                checkpoints[name][scenario] = write(name + '_' + scenario + '_state.json', caller._clean(state))
        summary = dict(schema='stage415_actual_paired_u20_terminal_v1', status='completed',
            started_at=started, finished_at=datetime.now(timezone.utc).isoformat(),
            elapsed_seconds=time.monotonic()-tick, composed_identity=composed_id,
            same_composed_unchanged=profiles.composed_identity(composed)==composed_id,
            acceptance=acceptance_b, results=result_b, state_checkpoints=checkpoints,
            profiles={name: dict(status=v['status'], active=v['active'],
                actual_training_cutoff=v['actual_training_cutoff'],
                account_ids={s:st['account_id'] for s,st in v['states'].items()})
                for name,v in result['profiles'].items()},
            calls=dict(actual_restore=1, existing_context_loads=2, pair=1,
                market_API=0, SQL=0, fit=0, completed_cash_backtests=0, new_account=0),
            strict_original_single_acquisition_adherence=False,
            causal_paper_only=True, no_real_orders=True, whole_goal_achieved=False)
        write('terminal.json', summary)
        print(json.dumps({k:summary[k] for k in ('status','elapsed_seconds','profiles','same_composed_unchanged')},ensure_ascii=False))
    except Exception as error:
        write('failure.json', dict(status='failed_no_automatic_retry', phase=phase,
            error_type=type(error).__name__, message=str(error),
            finished_at=datetime.now(timezone.utc).isoformat(),
            journals_may_have_appended=phase in ('process_pair_once_no_reentry','persist_complete_pair')))
        raise


if __name__ == '__main__':
    main()
