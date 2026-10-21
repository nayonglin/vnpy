"""Stage148: four new FX cash accounts; accepted131 B books are references only.

Import and synthetic tests perform no SQL, fitting, labeling or actual cash.
The accepted131 kernel, cash constants, anchor and capacity policy are unchanged.
Actual execution requires root's exact source/input authorization and fresh output.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
PROTOCOL_SHA = 'be0431bff87dc90d91a9f1b16940c9a6d8112a66d4309879abef46466ce4f270'
WINDOWS = ('primary_2020', 'cold_2023')
COSTS = ('base', 'stress')
FIXED_ROLES = ('actions', 'mothers', 'dataset_manifest', 'accepted_cash_manifest',
    'accepted_review_receipt', 'native_cache_manifest', 'native_cache', 'execution_protocol')
INPUT_ROLES = FIXED_ROLES + ('market_protocol', 'fit_manifest', 'choices_main', 'held_diagnostic', 'bridge_preflight')
IDENTITY = ['sequence_index', 'event_id', 'product_id', 'family_id', 'u_date', 'u_index', 'reference_epoch']
ACTION_FIELDS = ['action_id', 'event_id', 'action_sequence_index', 'mother_sequence_index',
    'mother_event_id', 'product_id', 'family_id', 'u_date', 'u_index', 'reference_epoch',
    'anchor_epoch', 'u_action_eligible', 'entry_capacity_qty', 'N_u', 'low20_u', 'u_close']
LEDGER_KEYS = dict(fills='fills', reservations='budgets', daily='daily', positions='position_days',
    closed='closed_episodes', open='open_episodes', capacity_audit='capacity_audit',
    entry_execution_unknown='entry_execution_unknown')


def load(name, identity):
    spec = importlib.util.spec_from_file_location(identity, TOOLS/name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


author = load('stage131_contract_choice_cash.py', 'cash148_accepted131')
cache_source = load('stage132_contract_choice_review.py', 'cash148_accepted132_cache')
kernel, ref = author.kernel, author.ref
helpers, report_helpers = author.helpers, author.report_helpers
diagnostics = helpers.diagnostics


def source_bundle():
    paths = {b['path'] for b in author.source_bundle()}
    paths.update(str(TOOLS/n) for n in ('stage148_fx_cash.py', 'test_stage148_fx_cash.py',
        'stage132_contract_choice_review.py', 'stage102_cash_adapter.py', 'stage102_cash_core.py',
        'stage102_cash_diagnostics.py'))
    return sorted((ref.file_binding(p) for p in paths), key=lambda b: b['path'])


def read_json(binding):
    return json.loads(ref.read_bound(binding))


def verify_file(binding):
    p = Path(binding['path'])
    if p.stat().st_size != binding['bytes']:
        raise ValueError('bound file size changed '+str(p))
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    if h.hexdigest() != binding['sha256']:
        raise ValueError('bound file hash changed '+str(p))


def numeric(frame, columns):
    for name in columns:
        if name in frame:
            frame[name] = pd.to_numeric(frame[name], errors='raise')
    return frame


class CachedMarket:
    """Expose accepted132 native arrays through the unchanged131 market API."""
    def __init__(self, store):
        self.store, self.dates, self.series = store, store.calendar, store.series

    def bar(self, epoch, k):
        j = self.store.locate(epoch, k)
        if j is None or not self.series[epoch]['valid'][j]:
            return None
        O, H, L, C, V = self.series[epoch]['values'][j]
        return dict(open=float(O), high=float(H), low=float(L), close=float(C), volume=float(V))

    def indicator(self, epoch, k):
        j = self.store.locate(epoch, k)
        if j is None or not self.series[epoch]['valid'][j]:
            return dict(N=math.nan, run_length=0, low20=math.nan, high55_before=math.nan)
        s = self.series[epoch]
        return dict(N=float(s['N'][j]), run_length=int(s['run'][j]),
            low20=float(s['low20'][j]), high55_before=math.nan)


def account_specs():
    return [dict(arm='FX', window=w, cost=c, account_id=f'NARROW_FX_{w}_{c}')
        for w in WINDOWS for c in COSTS]


def make_fx_signals(actions, mothers, choices, market, dates, economics):
    """Local schema alias only; FX selects from full147, never old B's pool."""
    picked = choices.loc[choices.arm.eq('FX')].copy()
    if picked.empty or set(picked.scope) != {'main'}:
        raise ValueError('complete new FX main choices required')
    picked['arm'] = 'B'
    result = author.make_signals(actions, mothers, picked, 'B', market, dates, economics)
    result['arm'], result['control_id'] = 'FX', 'FX'
    return result


def _log_path(frame):
    result = frame.copy()
    if 'ever_insolvent' in result:
        def boolean(value):
            if isinstance(value, (bool, np.bool_)):
                return bool(value)
            if str(value).lower() in ('true', '1'):
                return True
            if str(value).lower() in ('false', '0'):
                return False
            raise ValueError('unknown saved insolvency boolean')
        result['ever_insolvent'] = result.ever_insolvent.map(boolean)
    return diagnostics.daily_log_growth(result, ref.INITIAL)


def paired_statistics(active, control, indices):
    """Exact same source dates and old070 indices; no seed or log repair."""
    if active.date.tolist() != control.date.tolist():
        raise ValueError('paired source calendar differs')
    index = np.asarray(indices)
    if (index.ndim != 2 or index.shape != (2000, len(active)) or index.dtype.kind not in 'iu'
            or index.min() < 0 or index.max() >= len(active)):
        raise ValueError('original2000 source-calendar bootstrap indices required')
    al, ast = _log_path(active)
    bl, bst = _log_path(control)
    common = dict(active_log_status=ast, control_log_status=bst,
        bootstrap_repetitions=2000, block_length=252, indices_regenerated=False, epsilon_log_repair=False)
    if al is None or bl is None:
        return dict(common, status='survival_failure_no_log_repair', ci95_low=None, ci95_high=None,
            mean_daily_log_difference=None, cumulative_log_difference=None), np.full(2000, np.nan)
    difference = al-bl
    distribution = difference[index].mean(axis=1)
    lo, hi = np.quantile(distribution, [.025, .975])
    return dict(common, status='valid', mean_daily_log_difference=float(difference.mean()),
        cumulative_log_difference=float(difference.sum()), ci95_low=float(lo), ci95_high=float(hi)), distribution


def fixed_gate(points, held, any_stale, *, wealth_positive, execution_unknown):
    """Stage145's strict primary DD improvement and explicit unknown states."""
    lookup = {(p['window'], p['cost']): p for p in points}
    if len(points) != 4 or set(lookup) != {(w,c) for w in WINDOWS for c in COSTS}:
        raise ValueError('all four fixed FX comparisons required')
    groups = held.get('groups', {})
    if not {'holdout_0', 'holdout_1'}.issubset(groups):
        raise ValueError('both full prospective held groups required')
    groups = {g: groups[g] for g in ('holdout_0', 'holdout_1')}
    finite = lambda x: x is not None and np.isfinite(x)
    own = all(finite(p.get('active_total_return_pct')) and p['active_total_return_pct'] > 0 for p in points)
    primary = lookup[('primary_2020','stress')]
    returns = all(finite(p.get('return_percentage_point_difference')) and
        (p['return_percentage_point_difference'] > 0 if p is primary else p['return_percentage_point_difference'] >= 0)
        for p in points)
    dd_known = all(finite(p.get('drawdown_percentage_point_difference')) for p in points)
    dd = all((p['drawdown_percentage_point_difference'] > 0 if p is primary else
        p['drawdown_percentage_point_difference'] >= 0) for p in points if finite(p.get('drawdown_percentage_point_difference')))
    ci = finite(primary.get('ci95_low')) and primary['ci95_low'] > 0
    hn = all(finite(g.get('known_u_equal_mean_increment_R')) and g['known_u_equal_mean_increment_R'] >= 0
        and g.get('nominal_pass') is True for g in groups.values())
    hu = any(g.get('unknown_differential_selected_events', 0) > 0 or g.get('status') == 'unknown' for g in groups.values())
    nominal = bool(own and returns and dd_known and dd and ci and wealth_positive)
    unknown = bool(any_stale or not dd_known or execution_unknown)
    if all(p.get('identification') == 'all_empty_unidentified' for p in points):
        status = 'all_empty_unidentified'
    elif not (own and returns and dd and ci and wealth_positive and hn):
        status = 'unsupported'
    elif not dd_known:
        status = 'unknown_empty_reference_DD'
    elif any_stale:
        status = 'unknown_historical_stale'
    elif execution_unknown:
        status = 'unknown_execution_capacity_or_entry'
    elif hu:
        status = 'unknown_differential_held_outcome'
    else:
        status = 'supported_limited_reconstruction_model_only'
    return dict(status=status, cash_nominal_pass=nominal, held_known_nominal_pass=bool(hn),
        nominal_pass=bool(nominal and hn and not hu and not unknown),
        FX_own_returns_positive_in_all_four=bool(own), primary_strict_return_and_DD_improvement=bool(returns and dd),
        actual_wealth_positive=bool(wealth_positive), financial_unknown=unknown, held_signal_unknown=bool(hu),
        execution_unknown=bool(execution_unknown), any_historical_stale=bool(any_stale),
        signal_label_uncertainty_is_not_cash_exposure=True, strict_first_release_PIT_established=False,
        independent_actual_review_required=True, no_automatic_promotion=True, goal_complete=False,
        production_qualified=False, increased_betting_qualified=False)


def authorize(args):
    out = Path(args.output).resolve()
    if out.exists():
        raise FileExistsError('fresh output required; failed attempts are retained '+str(out))
    if LINE/'outputs/stage148_fx_cash' not in out.parents:
        raise ValueError('fresh Stage148 output directory required')
    pb = ref.file_binding(args.protocol)
    if args.protocol_sha256 != PROTOCOL_SHA or pb['sha256'] != PROTOCOL_SHA:
        raise ValueError('exact final145 protocol SHA required')
    protocol = read_json(pb)
    if protocol.get('schema') != 'stage145_fx_information_protocol_v1' or protocol.get('line_id') != LINE.name:
        raise ValueError('Stage145 identity differs')
    ab = ref.file_binding(args.authorization)
    if ab['sha256'] != args.authorization_sha256:
        raise ValueError('authorization SHA differs')
    auth = read_json(ab)
    expected = dict(schema='stage145_exact_root_authorization_v1', authorized_by='root', stage='cash',
        exact_source_authorized=True, protocol_sha256=PROTOCOL_SHA, output=str(out))
    if any(auth.get(k) != v for k,v in expected.items()):
        raise ValueError('exact root cash authorization required')
    if sorted(auth.get('source_bundle', []), key=lambda b:b['path']) != source_bundle():
        raise ValueError('authorized source/test bundle differs')
    inputs = auth.get('input_bindings', {})
    if set(inputs) != set(INPUT_ROLES):
        raise ValueError('exact frozen source and new147 roles required')
    for role in FIXED_ROLES:
        author.same_binding(inputs[role], protocol['input_roles'][role], '145 '+role)
    b = protocol['execution']['budget']
    constants = (b['initial_equity'], b['single_family_risk'], b['total_risk'], b['buffered_margin_cap'], b['margin_buffer'])
    if constants != (ref.INITIAL,ref.SINGLE_RISK,ref.TOTAL_RISK,ref.MARGIN_CAP,ref.MARGIN_BUFFER):
        raise ValueError('accepted070 budget differs')
    if b['initial_stop_N'] != .25 or b['slippage_deducted_again'] is not False:
        raise ValueError('stop or slippage accounting differs')
    if protocol['budget']['new_cash_accounts_max'] != 4 or protocol['budget']['new_sql'] != 0:
        raise ValueError('fixed4 cash/zero SQL budget differs')
    return protocol, pb, auth, ab


def validate_upstream(protocol, inputs):
    execution = read_json(inputs['execution_protocol'])
    author.same_binding(inputs['market_protocol'], execution['inputs']['market_protocol'], '128 market protocol')
    if execution['cash']['capacity'] != protocol['execution']['capacity']:
        raise ValueError('accepted131 capacity contract differs')
    baseline = read_json(inputs['accepted_cash_manifest'])
    if (baseline.get('schema') != 'stage131_contract_choice_cash_v1' or baseline.get('status') != 'completed'
            or baseline.get('mode') != 'actual' or baseline.get('new_cash_accounts') != 8):
        raise ValueError('accepted131 manifest required')
    author.same_binding(baseline['protocol'], inputs['execution_protocol'], 'accepted131 execution')
    if author.source_bundle() != baseline['source_bundle']:
        raise ValueError('accepted131 source/kernel must remain byte-identical')
    for role in ('actions','mothers','dataset_manifest','market_protocol'):
        author.same_binding(baseline['input_bindings'][role], inputs[role], 'accepted131 '+role)
    accepted = read_json(inputs['accepted_review_receipt'])
    if accepted.get('completed') is not True or accepted.get('research_arithmetic_accepted') is not True or (accepted.get('C'),accepted.get('I')) != (0,0):
        raise ValueError('accepted132 receipt required; no old review rerun')
    fit = read_json(inputs['fit_manifest'])
    if (fit.get('schema') != 'stage147_fx_fit_v1' or fit.get('status') != 'completed'
            or fit.get('cash_eligible') is not True or fit.get('protocol_sha256') != PROTOCOL_SHA):
        raise ValueError('completed cash-eligible147 required')
    for role in ('choices_main','held_diagnostic','bridge_preflight'):
        author.same_binding(fit[role], inputs[role], '147 '+role)
    terminal = read_json(fit['terminal'])
    if (terminal.get('status') != 'completed' or terminal.get('exit_code') != 0
            or terminal.get('actual_fit_calls_completed') != 6 or terminal.get('new_cash_accounts',0) != 0
            or terminal.get('native_source_queries',0) != 0):
        raise ValueError('147 terminal must complete6 fit/zero cash/SQL')
    bridge = read_json(inputs['bridge_preflight'])
    if bridge.get('status') != 'passed' or bridge.get('control_bridge_verified') is not True:
        raise ValueError('147 pre-fit zero-column control bridge required')
    meta = read_json(inputs['native_cache_manifest'])
    author.same_binding(meta['file'], inputs['native_cache'], '132 cached arrays')
    return execution, fit, baseline


def load_selected_inputs(inputs):
    verify_file(inputs['mothers'])
    mothers = pd.read_csv(inputs['mothers']['path'], dtype=str, keep_default_na=False, usecols=IDENTITY)
    numeric(mothers, ['sequence_index','u_index'])
    if len(mothers) != 399252 or mothers.event_id.duplicated().any() or mothers.product_id.nunique() != 98 or mothers.family_id.nunique() != 95:
        raise ValueError('complete unchanged129 mother universe required')
    verify_file(inputs['choices_main'])
    choices = pd.read_csv(inputs['choices_main']['path'], dtype=str, keep_default_na=False, float_precision='round_trip')
    numeric(choices, ['sequence_index','u_index','selected','chosen_action_sequence_index','score'])
    expected = set(mothers.loc[mothers.u_date.ge('2020-01-01'),'event_id'])
    if len(expected) != 161014 or len(choices) != 322028 or set(choices.arm) != {'CONTROL_REUSED','FX'} or set(choices.scope) != {'main'}:
        raise ValueError('full161014 main parent rows per FX/CONTROL arm required')
    for arm in ('CONTROL_REUSED','FX'):
        part = choices.loc[choices.arm.eq(arm)]
        if part.event_id.duplicated().any() or set(part.event_id) != expected:
            raise ValueError('new147 full parent identity lost '+arm)
    ids = set(choices.loc[choices.arm.eq('FX') & choices.selected.eq(1),'chosen_action_id'])
    verify_file(inputs['actions'])
    frames = []
    for chunk in pd.read_csv(inputs['actions']['path'], dtype=str, keep_default_na=False,
            compression='gzip', usecols=ACTION_FIELDS, chunksize=100000, float_precision='round_trip'):
        selected = chunk.loc[chunk.action_id.isin(ids)].copy()
        if len(selected):
            frames.append(selected)
    actions = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=ACTION_FIELDS)
    numeric(actions, ['action_sequence_index','mother_sequence_index','u_index','u_action_eligible',
        'entry_capacity_qty','N_u','low20_u','u_close'])
    if actions.action_id.duplicated().any() or set(actions.action_id) != ids:
        raise ValueError('every FX selected child must be an exact unique129 action')
    return mothers, choices, actions


def artifact(manifest, name):
    found = [b for b in manifest['artifacts'] if b.get('logical_name') == name]
    if len(found) != 1:
        raise ValueError('exact baseline artifact missing '+name)
    return {k:found[0][k] for k in ('path','bytes','sha256')}


def baseline_references(manifest):
    references, summaries, daily, reports = {}, {}, {}, {}
    diag_binding = artifact(manifest, 'diagnostics.json')
    all_reports = read_json(diag_binding)
    for spec in account_specs():
        w,c = spec['window'],spec['cost']; name = f'NARROW_B_{w}_{c}'
        sb,db = artifact(manifest,name+'/summary.json'),artifact(manifest,name+'/daily.csv.gz')
        summaries[(w,c)] = read_json(sb)
        daily[(w,c)] = pd.read_csv(io.BytesIO(ref.read_bound(db)), compression='gzip')
        reports[name] = all_reports[name]
        references[w+'_'+c] = dict(window=w,cost=c,arm='CONTROL_REUSED',source_account_id=name,
            source_arm='B',summary=sb,daily=db,diagnostics=diag_binding,diagnostic_key=name,
            source_only=True,replayed=False,identity='accepted131 B; zero-column bridge only; not promoted')
    return references,summaries,daily,reports


def write_ledgers(folder, book):
    folder.mkdir(parents=True,exist_ok=False)
    bindings = {}
    for role,key in LEDGER_KEYS.items():
        p = folder/(role+'.csv.gz')
        ref.write_table(p,book[key],author.EMPTY_COLUMNS.get(key,['account_id','scenario','date','equity','ever_insolvent']))
        bindings[role] = ref.file_binding(p)
    p = folder/'rejections.csv.gz'
    ref.write_table(p,[r for r in book['budgets'] if r.get('D_qty',0) == 0],helpers.EMPTY_COLUMNS['budgets'])
    bindings['rejections'] = ref.file_binding(p)
    return bindings


def extra_reports(book):
    """Descriptive realized/open attribution; do not alter ledger or net PnL."""
    roots = pd.DataFrame(book['closed_episodes']+book['open_episodes'])
    closed = pd.DataFrame(book['closed_episodes'])
    fills = pd.DataFrame(book['fills'])
    groups = []
    closed_ids = set(closed.root_id) if len(closed) else set()
    if len(roots):
        roots['market_sector'] = np.where(roots.product_id.str.startswith('CFFEX.'),'financial','commodity')
        roots['product_variant'] = np.where(roots.product_id.str.endswith('_F'),'F','ordinary')
    for dimension,names in (('market_sector',('financial','commodity')),('product_variant',('ordinary','F'))):
        for name in names:
            part = roots.loc[roots[dimension].eq(name)] if len(roots) else roots
            root_ids = set(part.root_id) if len(part) else set()
            f = fills.loc[fills.root_id.isin(root_ids)] if len(fills) else fills
            cl = closed.loc[closed.root_id.isin(root_ids)] if len(closed) else closed
            opened = part.loc[~part.root_id.isin(closed_ids)] if len(part) else part
            closed_net = float(cl.net_pnl.sum()) if len(cl) else 0.
            open_marked_net = float((opened.realized_gross-opened.entry_fees-opened.exit_fees+opened.unrealized).sum()) if len(opened) else 0.
            groups.append(dict(dimension=dimension,group=name,episodes=len(part),
                closed_episodes=len(cl),open_episodes=len(opened),closed_net_pnl=closed_net,
                open_marked_net_pnl=open_marked_net,net_equity_contribution=closed_net+open_marked_net,
                fees=float(f.fee.sum()) if len(f) else 0.,slippage_attribution=float(f.slippage.sum()) if len(f) else 0.,
                slippage_already_in_fill_price=True))
    tails = dict(largest_wins=[],largest_losses=[])
    if len(closed):
        columns = [c for c in ('root_id','event_id','product_id','family_id','epoch','entry_date','exit_date','net_pnl') if c in closed]
        tails['largest_wins'] = closed.loc[closed.net_pnl.gt(0)].nlargest(5,'net_pnl')[columns].to_dict('records')
        tails['largest_losses'] = closed.loc[closed.net_pnl.lt(0)].nsmallest(5,'net_pnl')[columns].to_dict('records')
    return groups,tails


def write_cash_progress(out, started, completed, account):
    # Accepted042 writes exclusively; each started account keeps its own receipt.
    path = out/f'cash_progress_{started:02d}.json'
    ref.write_json(path,dict(cash_accounts_started=started,new_cash_accounts=completed,current_account=account))


def execute(args):
    protocol,pb,auth,ab = authorize(args)
    inputs = auth['input_bindings']; out = Path(args.output).resolve()
    out.mkdir(parents=True,exist_ok=False)
    began,clock = datetime.now(timezone.utc).isoformat(),time.monotonic()
    before = source_bundle(); status,error,started,completed = 'failed',None,0,0
    accounts,summaries,daily,reports,family_tables,capacities = [],{},{},{},[],[]
    ref.write_json(out/'actual_started.json',dict(stage='cash',status='started',started_at=began,
        protocol=pb,authorization=ab,source_bundle=before,fixture=False))
    try:
        execution,fit,baseline_manifest = validate_upstream(protocol,inputs)
        mothers,choices,actions = load_selected_inputs(inputs)
        held = read_json(inputs['held_diagnostic'])
        store,native_receipt,_ = cache_source.restore_native_cache(inputs['native_cache_manifest'])
        if native_receipt['native_source_queries'] != 0 or ref.NATIVE_QUERIES != 0:
            raise ValueError('no native SQL authorized')
        market,dates = CachedMarket(store),store.calendar
        market_protocol = read_json(inputs['market_protocol'])
        economics = read_json(market_protocol['economic_projection'])['instruments']
        if set(economics) != set(store.series):
            raise ValueError('exact cached economics required')
        families = sorted(mothers.family_id.unique())
        indices = {w:np.load(io.BytesIO(ref.read_bound(protocol['bootstrap_indices'][w])),allow_pickle=False) for w in WINDOWS}
        baseline_books,control_summaries,control_daily,control_reports = baseline_references(baseline_manifest)
        signals = make_fx_signals(actions,mothers,choices,market,dates,economics)
        ref.write_table(out/'signals_FX.csv.gz',signals,[])
        prepared = author.organize(signals,mothers,dates)
        ref.write_json(out/'source_read_receipt.json',dict(native_receipt,actual_model_fit_calls=0,
            new_labels=0,old_baseline_replays=0,selected_FX_source_children=len(actions),
            full_forward_parent_rows_per_arm=161014,full_mother_rows=len(mothers)))
        all_groups,all_tails = [],{}
        for spec in account_specs():
            w,c,name = spec['window'],spec['cost'],spec['account_id']
            bounds = execution['cash']['windows'][w]
            start,end = (int(np.searchsorted(dates,v)) for v in bounds)
            if end >= len(dates) or dates[end] != bounds[1] or indices[w].shape != (2000,end-start+1):
                raise ValueError('fixed source calendar/window/index width differs')
            if started >= 4:
                raise ValueError('four FX cash budget exhausted')
            started += 1
            write_cash_progress(out,started,completed,name)
            book = kernel.run_cash_account(signals,market,dates,economics,c,name,start,end,prepared=prepared)
            completed += 1
            folder = out/name; ledgers = write_ledgers(folder,book)
            summary,report,fy = helpers.cash_report(book,families,ref.INITIAL)
            capacity = dict(account=name,arm='FX',control_id='FX',window=w,cost=c,execution_unknown=book['execution_unknown'],
                unknown_capacity_fills=sum(r['capacity_state']=='execution_capacity_unknown' for r in book['capacity_audit']),
                capacity_unknown_roots=len(book['capacity_unknown_roots']),entry_execution_unknown=len(book['entry_execution_unknown']))
            summary.update(capacity,any_historical_stale=report['stale_days']>0); report.update(capacity)
            summaries[(w,c)],daily[(w,c)],reports[name] = summary,pd.DataFrame(book['daily']),report
            capacities.append(capacity)
            family_tables.append(report_helpers.add_family_costs(fy,book).assign(arm='FX',window=w,cost=c))
            groups,tails = extra_reports(book)
            all_groups.extend(dict(account=name,window=w,cost=c,**r) for r in groups); all_tails[name] = tails
            ref.write_json(folder/'summary.json',kernel.original.safe(summary))
            accounts.append(dict(spec,directory=str(folder),summary=ref.file_binding(folder/'summary.json'),ledgers=ledgers))
            print(json.dumps(dict(phase='account_complete',account=name,cash_accounts_started=started,new_cash_accounts=completed)),flush=True)
        if started != 4 or completed != 4 or ref.NATIVE_QUERIES != 0:
            raise ValueError('exactly4 FX accounts/zero SQL required')
        points,distributions = [],{}
        for spec in account_specs():
            w,c = spec['window'],spec['cost']; key=(w,c)
            stats,dist = paired_statistics(daily[key],control_daily[key],indices[w])
            point = dict(window=w,cost=c,contrast='FX_minus_CONTROL_REUSED',
                active_total_return_pct=summaries[key]['total_return_pct'],reference_total_return_pct=control_summaries[key]['total_return_pct'],
                **helpers.compare_points(summaries[key],control_summaries[key]),**stats)
            points.append(point); distributions[w+'_'+c+'_FX_minus_CONTROL_REUSED'] = dist
        stale = any(r['stale_days']>0 for r in list(reports.values())+list(control_reports.values()))
        unknown = any(s['execution_unknown'] for s in list(summaries.values())+list(control_summaries.values()))
        wealth = all(_log_path(f)[0] is not None for f in list(daily.values())+list(control_daily.values()))
        gate = fixed_gate(points,held,stale,wealth_positive=wealth,execution_unknown=unknown)
        fy = pd.concat(family_tables,ignore_index=True)
        ref.write_table(out/'comparisons.csv.gz',points,[])
        ref.write_table(out/'bootstrap_distributions.csv.gz',pd.DataFrame(distributions),[])
        ref.write_table(out/'family_year_including_zero.csv.gz',fy,[])
        ref.write_table(out/'family_total_including_zero.csv.gz',fy.groupby(['arm','window','cost','family_id'])[
            ['net_equity_contribution','fee','slippage','fill_count','filled_qty']].sum().reset_index(),[])
        ref.write_table(out/'annual_slices.csv.gz',[dict(account=a,**r) for a,p in reports.items() for r in p['annual_slices']],[])
        ref.write_table(out/'account_summaries.csv.gz',[dict(summaries[(s['window'],s['cost'])]) for s in account_specs()],[])
        ref.write_table(out/'capacity_summary.csv.gz',capacities,[])
        ref.write_table(out/'sector_variant_attribution.csv.gz',all_groups,['account','window','cost','dimension','group','episodes','closed_net_pnl'])
        ref.write_json(out/'largest_wins_losses.json',kernel.original.safe(all_tails))
        ref.write_json(out/'diagnostics.json',kernel.original.safe(reports))
        ref.write_json(out/'baseline_references.json',baseline_books)
        ref.write_json(out/'continuation_gate.json',kernel.original.safe(gate))
        ref.write_json(out/'signal_identification.json',dict(full_mother_rows=399252,full_main_parent_rows_per_arm=161014,
            selected_FX_actions=len(signals),full_choices_binding=inputs['choices_main'],held_binding=inputs['held_diagnostic'],
            held_groups=held['groups'],old_B_selection_used_as_admission_gate=False,future_label_state_used_as_admission_gate=False,
            local_B_schema_alias_only=True,old_global_ARMS_changed=False))
        ref.write_json(out/'budget_and_tick_disclosure.json',dict(policy='NARROW',kernel='unchanged accepted131',
            budget=protocol['execution']['budget'],capacity=protocol['execution']['capacity'],anchor=protocol['execution']['anchor_and_execution'],
            bootstrap_indices=protocol['bootstrap_indices'],bootstrap_indices_regenerated=False,fees_already_in_cash=True,
            slippage_in_fill_price_already=True,slippage_deducted_again=False,no_gap_loss_cap=True,
            no_actual_orderbook_execution_proof=True,strict_first_release_PIT_established=False,
            source_archive_is_final_reconstruction=True,goal_complete=False,production_qualified=False,increased_betting_qualified=False))
        if source_bundle() != before:
            raise ValueError('authorized148 source changed during actual')
        if cache_source.database_state(read_json(inputs['native_cache_manifest'])['database']['path']) != native_receipt['database_after']:
            raise ValueError('cached database stat changed during actual')
        status = 'completed'
    except BaseException as exc:
        error = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        ref.write_json(out/'actual_terminal.json',dict(status=status,stage='cash',started_at=began,
            finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-clock,
            exit_code=0 if status=='completed' else 1,error=error,cash_accounts_started=started,new_cash_accounts=completed,
            native_source_queries=ref.NATIVE_QUERIES,actual_model_fit_calls=0,new_labels=0,downloads=0,
            whole_database_hashes=0,old_baseline_replays=0,old_control_cash_replays=0,fixture=False,python=sys.executable))
    artifacts = [dict(ref.file_binding(p),logical_name=str(p.relative_to(out)),role='decision_asset',
        feature_schema='stage148_fx_cash_v1',raw_ohlc=False,reproducibility_required=True)
        for p in sorted(out.rglob('*')) if p.is_file()]
    manifest = dict(schema='stage148_fx_cash_v1',status=status,mode='actual',protocol=pb,protocol_sha256=PROTOCOL_SHA,
        authorization=ab,source_bundle=before,input_bindings=inputs,terminal=ref.file_binding(out/'actual_terminal.json'),
        artifacts=artifacts,accounts=accounts,signals=ref.file_binding(out/'signals_FX.csv.gz'),baseline_books=baseline_books,
        bootstrap_indices=protocol['bootstrap_indices'],new_cash_accounts=completed,native_source_queries=0,
        actual_model_fit_calls=0,new_labels=0,old_baseline_replays=0,old_control_cash_replays=0,
        goal_complete=False,production_qualified=False,increased_betting_qualified=False)
    for name in ('comparisons','bootstrap_distributions','account_summaries','family_year_including_zero',
        'family_total_including_zero','annual_slices','capacity_summary','sector_variant_attribution','largest_wins_losses',
        'diagnostics','continuation_gate','signal_identification','budget_and_tick_disclosure','source_read_receipt'):
        suffix = '.json' if name in ('largest_wins_losses','diagnostics','continuation_gate','signal_identification',
            'budget_and_tick_disclosure','source_read_receipt') else '.csv.gz'
        manifest[name] = ref.file_binding(out/(name+suffix))
    ref.write_json(out/'manifest.json',manifest)
    return dict(status=status,output=str(out),new_cash_accounts=completed,native_source_queries=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','protocol-sha256','authorization','authorization-sha256','output'):
        parser.add_argument('--'+name,required=True)
    print(json.dumps(execute(parser.parse_args()),ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()
