"""Independent Stage139 accepted-ledger attribution review; no replay or native API.

This module never imports the author or old qualification entrypoints. Its finite
helpers do no filesystem work. Actual CLI is exact-bound and requires root auth.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import time
import traceback

import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
PROTOCOL_SHA = '7d07e65db4dd4287b0245b535c19af76d6a23ffc9e9896defab7f1b278b2057d'
RANDOM = tuple(f'RANDOM_POS_{i:02d}' for i in range(20))
CONTROLS = ('MAX_VOLUME_POS',) + RANDOM
ATOL, RTOL = 1e-6, 1e-10
COMPONENTS = ('delta_CNY', 'risk_component', 'unit_component', 'participation_component')
MEASURES = COMPONENTS + ('gross_realized_difference', 'negative_fee_difference', 'unrealized_difference')
SIGNED = ('positive_delta_CNY','negative_delta_CNY')
BOOL_COLUMNS = {'opportunity','entered','entry_execution_unknown','terminal_open','ever_stale','terminal_stale',
                'capacity_unknown','affected','same_chosen_action','AI_entered','control_entered',
                'either_capacity_unknown','either_ever_stale','either_terminal_open','either_terminal_stale',
                'either_entry_execution_unknown'}
NUM_COLUMNS = set(MEASURES+SIGNED) | {'u_index','initial_qty','risk_per_lot','funded_initial_risk_CNY',
    'net_contribution','realized_gross','fees','unrealized','parent_rows','entered','opportunity',
    'growth_CNY','root_sum_CNY','ending_equity','capacity_unknown_roots','ever_stale_roots',
    'terminal_open_roots','entry_execution_unknown','AI_initial_risk_CNY','control_initial_risk_CNY',
    'AI_net_CNY','control_net_CNY','AI_unit_return','control_unit_return','control_count','rank'}


def number(value):
    assert not isinstance(value, (bool, np.bool_)), ('bool is not number', value)
    result = float(value)
    assert math.isfinite(result), ('nonfinite', value)
    return result


def close(actual, expected, label='amount'):
    a, b = number(actual), number(expected)
    assert abs(a-b) <= ATOL + RTOL * abs(b), (label, a, b, a-b)


def flag(value):
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    assert str(value).lower() in ('true', 'false', '1', '0'), ('invalid bool', value)
    return str(value).lower() in ('true', '1')


def root_accounting(row, fills, closed):
    """Independent fill net vs episode net; initial BUY risk, no repeated slip."""
    assert fills and all(f['root_id'] == row['root_id'] for f in fills)
    for field in ('event_id', 'epoch'):
        assert all(f[field] == row[field] for f in fills), ('fill identity', field)
    buys = [f for f in fills if f['side'] == 'BUY']
    sells = [f for f in fills if f['side'] == 'SELL']
    assert len(buys) == 1 and len(buys)+len(sells) == len(fills), 'one BUY per root'
    qty, risk = number(row['initial_qty']), number(row['risk_per_lot'])
    assert qty > 0 and qty.is_integer() and risk > 0
    balance = 0.
    for fill in fills:
        fill_qty = number(fill['qty'])
        assert fill_qty > 0 and fill_qty.is_integer(), 'positive integer fill quantity'
        balance += fill_qty if fill['side'] == 'BUY' else -fill_qty
        assert 0 <= balance <= qty, 'observed root quantity balance'
    close(buys[0]['qty'], qty, 'initial BUY qty')
    close(buys[0]['risk_per_lot'], risk, 'initial BUY risk')
    close(buys[0]['fee'], row['entry_fees'], 'initial BUY fee')
    close(math.fsum(number(f['fee']) for f in sells), row['exit_fees'], 'exit fees')
    gross = math.fsum(number(f['realized_gross']) for f in fills)
    close(gross, row['realized_gross'], 'realized gross')
    remaining = 0. if closed else number(row['qty'])
    assert 0 <= remaining <= qty and remaining.is_integer()
    close(row['qty'], remaining, 'terminal quantity')
    close(math.fsum(number(f['qty']) for f in sells)+remaining, qty, 'root quantity')
    unrealized = 0. if closed else number(row['unrealized'])
    negative_fee = -math.fsum(number(f['fee']) for f in fills)
    cash = math.fsum((gross, negative_fee, unrealized))
    episode_net = number(row['realized_gross'])-number(row['entry_fees'])-number(row['exit_fees'])+unrealized
    close(cash, episode_net, 'episode/fill net')
    if closed:
        close(cash, row['net_pnl'], 'saved closed net')
    frozen = qty*risk
    number(frozen); unit = number(cash/frozen)
    return dict(C=cash, F=frozen, Y=unit, gross_realized=gross,
                negative_fee=negative_fee, unrealized=unrealized)


def pair_math(CA, CB, FA, FB, enteredA, enteredB, same_action):
    enteredA, enteredB, same_action = flag(enteredA), flag(enteredB), flag(same_action)
    a, b = number(CA), number(CB)
    ya, yb = None, None
    for cash, risk, entered in ((a, FA, enteredA), (b, FB, enteredB)):
        if entered:
            assert risk is not None and number(risk) > 0
        else:
            assert risk is None and cash == 0., 'no entry cannot invent F/Y/C'
    if enteredA:
        ya = a/number(FA)
    if enteredB:
        yb = b/number(FB)
    risk_component = unit_component = participation = 0.
    if enteredA and enteredB:
        category = 'both_entered_same_action' if same_action else 'both_entered_different_action'
        risk_component = (FA-FB)*(ya+yb)/2.
        unit_component = (ya-yb)*(FA+FB)/2.
    elif enteredA:
        category, participation = 'AI_only_entered', a
    elif enteredB:
        category, participation = 'control_only_entered', -b
    else:
        category = 'neither_entered'
    close(risk_component+unit_component+participation, a-b, 'parent symmetric bridge')
    return dict(category=category, delta_CNY=a-b, risk_component=risk_component,
                unit_component=unit_component, participation_component=participation,
                Y_AI=ya, Y_control=yb)


def complete_grid(keys, accounts, parents):
    seen = set(keys)
    assert len(keys) == len(seen) == len(accounts)*len(parents), 'grid duplicate or missing'
    expected_parents, expected_accounts = set(parents), set(accounts)
    groups = defaultdict(set)
    for account, parent in keys:
        groups[account].add(parent)
    assert set(groups) == expected_accounts and all(x == expected_parents for x in groups.values()), 'full source parent grid'


def opportunity(u_index, start_index, end_index):
    return int(start_index)-1 <= int(u_index) <= int(end_index)-1


def calendar_dates(values):
    result = []
    for value in values:
        text = str(value)
        if len(text) == 8 and text.isdecimal():
            day = datetime.strptime(text, '%Y%m%d').strftime('%Y-%m-%d')
        else:
            day = datetime.strptime(text[:10], '%Y-%m-%d').strftime('%Y-%m-%d')
        result.append(day)
    assert result == sorted(set(result)), 'calendar chronological uniqueness'
    return result


def normalized_path(row, fills, closed):
    """Only normalized observed fills/terminal metadata, never full path proof."""
    initial = number(row['initial_qty'])
    trace = []
    for f in fills:
        trace.append([str(f.get(k, '')) for k in ('date','side','reason')] +
                     [round(number(f[k]), 12) for k in ('reference_price','fill_price')] +
                     [round(number(f[k])/initial, 12) for k in ('qty','fee','slippage','realized_gross')])
    terminal = {k:str(row.get(k, '')) for k in ('exit_date','exit_reason','anchor_request_date','anchor_request_reason','state')}
    terminal.update({k:flag(row[k]) if row.get(k, '') != '' else False
                     for k in ('stale','ever_stale','deferred','execution_capacity_unknown')})
    terminal.update(remaining_fraction=round(number(row['qty'])/initial, 12), last_mark=round(number(row['last_mark']), 12))
    return dict(fills=trace, terminal=terminal)


def mean20(rows):
    assert len(rows) == 20 and {r['control_id'] for r in rows} == set(RANDOM), 'all exact20 pairs required'
    return {k:math.fsum(number(r[k]) for r in rows)/20. for k in COMPONENTS}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def binding(path):
    p = Path(path).resolve(); raw = p.read_bytes()
    return dict(path=str(p), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def bound(item):
    raw = Path(item['path']).read_bytes()
    assert len(raw) == item['bytes'] and hashlib.sha256(raw).hexdigest() == item['sha256'], ('binding', item['path'])
    return raw


def same_binding(a, b):
    assert all(a[k] == b[k] for k in ('path','bytes','sha256')), ('exact identity', a, b)


def table(item):
    return pd.read_csv(io.BytesIO(bound(item)), compression='gzip', dtype=str, keep_default_na=False)


def signature_projection(raw, compression='gzip'):
    """Declared diagnostic hash uses pandas numeric CSV decoding, not CNY math.

    str→float and the default CSV decoder can differ by a few ULPs, enough to
    change a round12 digest. Monetary checks deliberately retain table().
    """
    return pd.read_csv(io.BytesIO(raw), compression=compression, keep_default_na=False)


def bundle():
    return sorted([binding(TOOLS/n) for n in ('stage141_funded_gap_review.py','test_stage141_funded_gap_review.py')], key=lambda b:b['path'])


def write(path, obj):
    with Path(path).open('x') as handle:
        json.dump(obj, handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        handle.write('\n')


def artifact(manifest, logical):
    found = [v for v in manifest['artifacts'] if v.get('logical_name') == logical]
    assert len(found) == 1, ('unique accepted artifact', logical)
    return {k:found[0][k] for k in ('path','bytes','sha256')}


def compare_frame(actual, expected, keys, name):
    assert not actual.duplicated(keys).any() and not expected.duplicated(keys).any(), ('duplicates', name)
    # Key text is normalized only for bool dimensions, not scientific identities.
    for key in keys:
        actual[key] = actual[key].map(flag).astype(str) if key in BOOL_COLUMNS else actual[key].astype(str)
        expected[key] = expected[key].map(flag).astype(str) if key in BOOL_COLUMNS else expected[key].astype(str)
    actual = actual.set_index(keys).sort_index(); expected = expected.set_index(keys).sort_index()
    assert actual.index.tolist() == expected.index.tolist(), ('full key domain', name)
    max_error = 0.
    for column in expected:
        assert column in actual, ('missing column', name, column)
        left, right = actual[column], expected[column]
        is_bool = column in BOOL_COLUMNS and (column not in ('entered','opportunity','entry_execution_unknown') or name == 'book_parent_contributions')
        if is_bool:
            assert left.map(flag).tolist() == right.map(flag).tolist(), ('bool', name, column)
        elif column in NUM_COLUMNS:
            a = pd.to_numeric(left.replace('', np.nan), errors='raise').to_numpy(float)
            b = pd.to_numeric(right.replace('', np.nan), errors='raise').to_numpy(float)
            assert np.array_equal(np.isnan(a), np.isnan(b)), ('null meaning', name, column)
            keep = ~np.isnan(b)
            assert np.isfinite(a[keep]).all() and np.isfinite(b[keep]).all(), ('nonfinite', name, column)
            difference = np.abs(a[keep]-b[keep])
            assert np.all(difference <= ATOL+RTOL*np.abs(b[keep])), ('numeric mismatch', name, column, float(difference.max()) if len(difference) else 0.)
            max_error = max(max_error, float(difference.max()) if len(difference) else 0.)
        else:
            assert left.astype(str).tolist() == right.astype(str).tolist(), ('identity/text', name, column)
    return dict(rows=len(expected), columns_checked=len(expected), max_absolute_numeric_error=max_error)


def choices_and_accounts(protocol, controls, old):
    choices = table(protocol['inputs']['choices_main'])
    source = choices.loc[choices.arm.eq('B') & choices.scope.eq('main')]
    assert len(source) == 161014 and source.event_id.is_unique, 'full source B main base'
    base = source.loc[pd.to_numeric(source.selected).eq(1), ['event_id','product_id','family_id','u_date','u_index','chosen_action_id','chosen_epoch']]
    base = base.rename(columns={'event_id':'mother_event_id'}).reset_index(drop=True)
    assert len(base) == 4917 and base.chosen_action_id.is_unique
    maps = {'AI':base}
    for control in CONTROLS:
        signal = table(controls['signals'][control])
        assert signal.mother_event_id.is_unique and signal.event_id.is_unique
        assert set(signal.mother_event_id) == set(base.mother_event_id)
        z = signal.set_index('mother_event_id').reindex(base.mother_event_id)
        for field in ('product_id','family_id','u_date','u_index','anchor_epoch'):
            if field in base:
                assert z[field].tolist() == base[field].tolist(), ('accepted signal identity', control, field)
        own = base.drop(columns=['chosen_action_id','chosen_epoch']).copy()
        own['chosen_action_id'], own['chosen_epoch'] = z.event_id.to_numpy(), z.reference_epoch.to_numpy()
        maps[control] = own
    accounts = list(controls['accounts'])
    for window in protocol['scope']['windows']:
        for cost in protocol['scope']['costs']:
            account = f'NARROW_B_{window}_{cost}'
            ledgers = {n:artifact(old, account+'/'+n+'.csv.gz') for n in ('closed','open','fills','reservations','entry_execution_unknown')}
            accounts.append(dict(account_id=account, control_id='AI', window=window, cost=cost,
                                 summary=artifact(old, account+'/summary.json'), ledgers=ledgers))
    assert len(accounts) == 88 and len({a['account_id'] for a in accounts}) == 88
    assert {(a['control_id'],a['window'],a['cost']) for a in accounts} == {
        (control,window,cost) for control in ('AI',)+CONTROLS for window in protocol['scope']['windows'] for cost in protocol['scope']['costs']}
    return base, maps, accounts


def independent_book(account, choice, dates, window):
    data = {n:table(account['ledgers'][n]) for n in ('closed','open','fills','reservations','entry_execution_unknown')}
    path_roots = pd.concat([signature_projection(bound(account['ledgers'][n])) for n in ('closed','open')],ignore_index=True)
    path_roots = path_roots.set_index('root_id').to_dict('index')
    path_fills = signature_projection(bound(account['ledgers']['fills']))
    path_fills = {root:g.to_dict('records') for root,g in path_fills.groupby('root_id',sort=False)}
    summary = json.loads(bound(account['summary']))
    assert number(summary['initial_capital']) == 1000000.
    start, end = (int(np.searchsorted(dates, day)) for day in window)
    expected_actions = set(choice.loc[choice.u_index.map(lambda v:opportunity(int(v), start, end)), 'chosen_action_id'])
    budgets = data['reservations']; entries = budgets.loc[budgets.budget_kind.ne('existing_position_reduction')]
    assert entries.event_id.is_unique and set(entries.event_id) == expected_actions, ('full entry decision domain', account['account_id'])
    decisions = entries.set_index('event_id').to_dict('index')
    unknown = set(data['entry_execution_unknown'].event_id)
    assert unknown <= expected_actions
    assert unknown == {action for action,row in decisions.items() if row['D_state'] == 'entry_execution_unknown'}
    fillgroups = {root:g.to_dict('records') for root,g in data['fills'].groupby('root_id', sort=False)}
    roots = {}; root_ids = set()
    for closed, name in ((True,'closed'), (False,'open')):
        for row in data[name].to_dict('records'):
            assert row['root_id'] not in root_ids and row['event_id'] not in roots, 'unique terminal root/action'
            root_ids.add(row['root_id']); roots[row['event_id']] = (row,closed)
    assert root_ids == set(fillgroups), 'fill/terminal root domain'
    assert set(roots) <= expected_actions, 'entered outside accepted decision window'
    rows = []
    for parent in choice.to_dict('records'):
        action = parent['chosen_action_id']; entered = action in roots
        decision = decisions.get(action); within = action in expected_actions
        row = dict(account_id=account['account_id'], control_id=account['control_id'], window=account['window'],
                   cost=account['cost'], **parent, cohort_year=parent['u_date'][:4], opportunity=within,
                   entered=entered, entry_execution_unknown=action in unknown,
                   entry_state=decision['D_state'] if within else 'outside_account_decision_window')
        if entered:
            root, closed = roots[action]; fs = fillgroups[root['root_id']]
            assert root['mother_event_id'] == parent['mother_event_id'] and root['epoch'] == parent['chosen_epoch']
            for field in ('family_id','product_id','u_date'):
                assert root[field] == parent[field], ('root parent identity', field)
            if decision.get('mother_event_id', ''):
                assert decision['mother_event_id'] == parent['mother_event_id']
            amount = root_accounting(root, fs, closed)
            close(decision['D_qty'], root['initial_qty'], 'entry decision/BUY')
            row.update(root_id=root['root_id'], initial_qty=number(root['initial_qty']), risk_per_lot=number(root['risk_per_lot']),
                       funded_initial_risk_CNY=amount['F'], net_contribution=amount['C'], realized_gross=amount['gross_realized'],
                       fees=-amount['negative_fee'], unrealized=amount['unrealized'], terminal_open=not closed,
                       ever_stale=flag(root['ever_stale']), terminal_stale=flag(root['stale']),
                       capacity_unknown=flag(root['execution_capacity_unknown']),
                       observed_path_signature=digest(normalized_path(path_roots[root['root_id']], path_fills[root['root_id']], closed)))
        else:
            if within:
                close(decision['D_qty'], 0., 'nonentered decision qty')
            row.update(root_id='', initial_qty=None, risk_per_lot=None, funded_initial_risk_CNY=None,
                       net_contribution=0., realized_gross=0., fees=0., unrealized=0., terminal_open=False,
                       ever_stale=False, terminal_stale=False, capacity_unknown=False, observed_path_signature='')
        row['affected'] = any(row[k] for k in ('entry_execution_unknown','terminal_open','ever_stale','capacity_unknown'))
        rows.append(row)
    result = pd.DataFrame(rows)
    root_sum = math.fsum(result.net_contribution)
    fill_net = math.fsum(number(f['realized_gross'])-number(f['fee']) for fs in fillgroups.values() for f in fs)
    fill_net += math.fsum(number(v) for v in data['open'].unrealized)
    growth = number(summary['ending_equity'])-1000000.
    close(root_sum, growth, 'book/equity growth'); close(root_sum, fill_net, 'book/fill net')
    record = dict(account_id=account['account_id'], control_id=account['control_id'], window=account['window'], cost=account['cost'],
                  parent_rows=len(result), entered=int(result.entered.sum()), opportunity=int(result.opportunity.sum()),
                  growth_CNY=growth, root_sum_CNY=root_sum, ending_equity=number(summary['ending_equity']),
                  capacity_unknown_roots=int(result.capacity_unknown.sum()), ever_stale_roots=int(result.ever_stale.sum()),
                  terminal_open_roots=int(result.terminal_open.sum()), entry_execution_unknown=int(result.entry_execution_unknown.sum()))
    return result, record


def independent_pair(ai, peer):
    assert ai.mother_event_id.tolist() == peer.mother_event_id.tolist()
    result = []
    for a,b in zip(ai.to_dict('records'),peer.to_dict('records')):
        same = a['chosen_action_id'] == b['chosen_action_id']
        # A DataFrame stores absent risk as NaN. Preserve semantic null at the
        # pure API boundary; a nonentered side has no risk or unit return.
        risk_a = a['funded_initial_risk_CNY'] if a['entered'] else None
        risk_b = b['funded_initial_risk_CNY'] if b['entered'] else None
        mathrow = pair_math(a['net_contribution'], b['net_contribution'], risk_a,
                            risk_b, a['entered'], b['entered'], same)
        path = 'not_both_entered'
        if a['entered'] and b['entered']:
            path = ('same_observed_fractional_path' if a['observed_path_signature'] == b['observed_path_signature'] else 'different_observed_fractional_path') if same else 'different_action_not_compared'
        row = {k:a[k] for k in ('mother_event_id','product_id','family_id','u_date','u_index','cohort_year','window','cost')}
        row.update(control_id=b['control_id'], category=mathrow['category'], path_diagnostic=path,
                   same_chosen_action=same, AI_entered=a['entered'], control_entered=b['entered'],
                   AI_action_id=a['chosen_action_id'], control_action_id=b['chosen_action_id'],
                   AI_initial_risk_CNY=a['funded_initial_risk_CNY'], control_initial_risk_CNY=b['funded_initial_risk_CNY'],
                   AI_net_CNY=a['net_contribution'], control_net_CNY=b['net_contribution'],
                   AI_entry_state=a['entry_state'], control_entry_state=b['entry_state'], affected=a['affected'] or b['affected'],
                   **{k:mathrow[k] for k in COMPONENTS}, AI_unit_return=mathrow['Y_AI'], control_unit_return=mathrow['Y_control'],
                   gross_realized_difference=a['realized_gross']-b['realized_gross'],
                   negative_fee_difference=b['fees']-a['fees'], unrealized_difference=a['unrealized']-b['unrealized'])
        for key in ('capacity_unknown','ever_stale','terminal_open','terminal_stale','entry_execution_unknown'):
            row['either_'+key] = a[key] or b[key]
        close(row['delta_CNY'], math.fsum(row[k] for k in ('gross_realized_difference','negative_fee_difference','unrealized_difference')), 'pair gross/fee/mark')
        result.append(row)
    return pd.DataFrame(result)


def rollup(frame, dimensions):
    keys = ['control_id','window','cost'] + dimensions
    result = []
    for key, group in frame.groupby(keys, sort=True, dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        sums = {n:math.fsum(number(v) for v in group[n]) for n in MEASURES}
        sums.update(positive_delta_CNY=math.fsum(max(number(v),0.) for v in group.delta_CNY),
                    negative_delta_CNY=math.fsum(min(number(v),0.) for v in group.delta_CNY))
        close(sums['positive_delta_CNY']+sums['negative_delta_CNY'], sums['delta_CNY'], 'signed contributions')
        close(sum(sums[n] for n in COMPONENTS[1:]), sums['delta_CNY'], 'group bridge')
        close(sum(sums[n] for n in MEASURES[-3:]), sums['delta_CNY'], 'group gross/fee/mark')
        result.append(dict(zip(keys,key), **sums, parent_rows=len(group)))
    return pd.DataFrame(result)


def expected_outputs(protocol, controls, old):
    parents, mappings, accounts = choices_and_accounts(protocol, controls, old)
    dates = calendar_dates(np.load(io.BytesIO(bound(protocol['inputs']['calendar'])), allow_pickle=False))
    assert len(dates) == 5587
    books, recs = {}, []
    for account in accounts:
        key = (account['control_id'], account['window'], account['cost'])
        book, reconciliation = independent_book(account, mappings[account['control_id']], dates, protocol['scope']['windows'][account['window']])
        books[key] = book; recs.append(reconciliation)
    book_frame = pd.concat(books.values(), ignore_index=True)
    parent_ids = parents.mother_event_id.tolist()
    complete_grid(list(zip(book_frame.account_id, book_frame.mother_event_id)), [a['account_id'] for a in accounts], parent_ids)
    assert len(book_frame) == 432696
    pieces = []
    for control in CONTROLS:
        for window in protocol['scope']['windows']:
            for cost in protocol['scope']['costs']:
                ai, peer = books[('AI',window,cost)], books[(control,window,cost)]
                pair = independent_pair(ai, peer)
                close(math.fsum(pair.delta_CNY), math.fsum(ai.net_contribution)-math.fsum(peer.net_contribution), 'pair/ending equity growth')
                pieces.append(pair)
    pair_frame = pd.concat(pieces, ignore_index=True)
    pair_ids = [(control,window,cost) for control in CONTROLS for window in protocol['scope']['windows'] for cost in protocol['scope']['costs']]
    keys = list(zip(list(zip(pair_frame.control_id,pair_frame.window,pair_frame.cost)),pair_frame.mother_event_id))
    complete_grid(keys, pair_ids, parent_ids)
    assert len(pair_frame) == 413028
    summaries = rollup(pair_frame, [])
    rec_map = {(r['control_id'],r['window'],r['cost']):r for r in recs}
    aggregates = []
    for window in protocol['scope']['windows']:
        for cost in protocol['scope']['costs']:
            group = summaries.loc[summaries.window.eq(window) & summaries.cost.eq(cost)]
            for contrast, controls0 in [('AI_minus_MAX_VOLUME_POS',('MAX_VOLUME_POS',)), ('AI_minus_RANDOM_POS_mean20',RANDOM)]:
                own = group.loc[group.control_id.isin(controls0)]
                assert len(own) == len(controls0) and set(own.control_id) == set(controls0)
                amounts = {k:math.fsum(number(v) for v in own[k])/len(controls0) for k in MEASURES+SIGNED}
                if len(controls0) == 20:
                    exact = mean20(own.to_dict('records'))
                    for key in COMPONENTS:
                        close(amounts[key], exact[key], 'mean20 exact pairs')
                expected_delta = rec_map[('AI',window,cost)]['ending_equity'] - math.fsum(rec_map[(c,window,cost)]['ending_equity'] for c in controls0)/len(controls0)
                close(amounts['delta_CNY'], expected_delta, 'aggregate arithmetic ending equity')
                close(amounts['positive_delta_CNY']+amounts['negative_delta_CNY'], expected_delta, 'aggregate signed amount')
                aggregates.append(dict(window=window,cost=cost,contrast=contrast,control_count=len(controls0),**amounts))
    result = dict(book_parent_contributions=book_frame, pair_parent_decomposition=pair_frame,
                  account_reconciliation=pd.DataFrame(recs), pair_summaries=summaries,
                  aggregate_summaries=pd.DataFrame(aggregates))
    for name, dims in [('category_components',['category']), ('family_components',['family_id']),
                       ('cohort_components',['cohort_year']), ('affected_components',['affected']),
                       ('path_components',['path_diagnostic'])]:
        result[name] = rollup(pair_frame, dims)
    top = []
    for window in protocol['scope']['windows']:
        for cost in protocol['scope']['costs']:
            group = pair_frame.loc[pair_frame.window.eq(window) & pair_frame.cost.eq(cost)]
            for contrast, control_ids in [('AI_minus_MAX_VOLUME_POS',('MAX_VOLUME_POS',)), ('AI_minus_RANDOM_POS_mean20',RANDOM)]:
                own = group.loc[group.control_id.isin(control_ids)]
                parent_means = []
                for key, rows in own.groupby(['mother_event_id','family_id','u_date'],sort=False):
                    assert len(rows) == len(control_ids) and set(rows.control_id) == set(control_ids)
                    parent_means.append(dict(zip(('mother_event_id','family_id','u_date'),key), delta_CNY=math.fsum(rows.delta_CNY)/len(control_ids)))
                means = pd.DataFrame(parent_means)
                for side, keep, ascending in [('positive',means.delta_CNY.gt(0),False),('negative',means.delta_CNY.lt(0),True)]:
                    ranked = means.loc[keep].sort_values('delta_CNY',ascending=ascending,kind='mergesort').head(5)
                    for rank, row in enumerate(ranked.to_dict('records'),1):
                        top.append(dict(window=window,cost=cost,contrast=contrast,side=side,rank=rank,**row))
    result['top_parent_contributions'] = pd.DataFrame(top)
    return result


def closure(args):
    pb, mb, authb = binding(args.protocol), binding(args.attribution_manifest), binding(args.authorization)
    assert pb['sha256'] == args.protocol_sha256 == PROTOCOL_SHA and pb['bytes'] == 9963
    assert mb['sha256'] == args.attribution_manifest_sha256
    assert authb['sha256'] == args.authorization_sha256
    protocol, manifest, auth = (json.loads(bound(b)) for b in (pb,mb,authb))
    assert protocol['schema'] == 'stage139_funded_gap_protocol_v1'
    assert manifest['schema'] == 'stage140_funded_gap_v1' and manifest['status'] == 'completed' and manifest['mode'] == 'actual'
    same_binding(manifest['protocol'], pb)
    assert set(manifest['input_bindings']) == set(protocol['inputs'])
    for key, expected in protocol['inputs'].items():
        same_binding(manifest['input_bindings'][key], expected)
    sources = bundle(); assert digest(sources) == args.source_bundle_sha256, 'exact141 source bundle'
    required = dict(schema='stage139_exact_root_authorization_v1', authorized_by='root', stage='review',
                    protocol_sha256=PROTOCOL_SHA, output=str(Path(args.output).resolve()), exact_source_authorized=True)
    assert all(auth.get(k) == value for k,value in required.items()), 'root review authorization fields'
    assert auth['source_bundle'] == sources and auth['input_bindings'] == protocol['inputs']
    same_binding(auth['attribution_manifest'], mb)
    for source in manifest['source_bundle']:
        bound(source)  # Verify new author source identity; never import its math.
    terminal = json.loads(bound(manifest['terminal']))
    assert terminal['status'] == 'completed' and terminal['exit_code'] == 0
    for key in ('new_SQL','new_fits','new_labels','new_cash','native_cache_reads'):
        assert terminal[key] == 0
    accepted = json.loads(bound(protocol['inputs']['accepted_review']))
    accepted_terminal = json.loads(bound(protocol['inputs']['accepted_review_terminal']))
    assert accepted['schema'] == 'stage137_incremental_month_ranking_review_v1'
    assert accepted['status'] == 'completed' and accepted['counts'] == dict(Critical=0,Important=0,Minor=0)
    assert accepted_terminal['status'] == 'completed' and accepted_terminal['exit_code'] == 0
    same_binding(accepted['exact_inputs']['cash'], protocol['inputs']['control_cash_manifest'])
    controls = json.loads(bound(protocol['inputs']['control_cash_manifest']))
    old = json.loads(bound(protocol['inputs']['AI_cash_manifest']))
    same_binding(controls['input_bindings']['baseline_cash_manifest'], protocol['inputs']['AI_cash_manifest'])
    same_binding(controls['input_bindings']['choices_main'], protocol['inputs']['choices_main'])
    return protocol, manifest, controls, old, dict(protocol=pb,attribution_manifest=mb,authorization=authb,sources=sources,inputs=protocol['inputs'])


def execute(args):
    protocol, manifest, controls, old, identity = closure(args)
    output = Path(args.output).resolve(); output.mkdir(parents=True,exist_ok=False)
    started = time.monotonic()
    try:
        expected = expected_outputs(protocol, controls, old)
        checks = {}
        for name, frame in expected.items():
            if name == 'book_parent_contributions':
                keys = ['account_id','mother_event_id']
            elif name == 'pair_parent_decomposition':
                keys = ['control_id','window','cost','mother_event_id']
            elif name == 'account_reconciliation':
                keys = ['account_id']
            elif name == 'aggregate_summaries':
                keys = ['window','cost','contrast']
            elif name == 'top_parent_contributions':
                keys = ['window','cost','contrast','side','rank']
            else:
                dimensions = {'category_components':['category'], 'family_components':['family_id'],
                              'cohort_components':['cohort_year'], 'affected_components':['affected'],
                              'path_components':['path_diagnostic']}
                keys = ['control_id','window','cost'] + dimensions.get(name,[])
            checks[name] = compare_frame(table(manifest[name]),frame,keys,name)
        diag = json.loads(bound(manifest['diagnostics']))
        diagnostic_expected = dict(schema='stage140_funded_gap_diagnostics_v1', account_count=88, pair_count=84,
            book_parent_rows=432696,pair_parent_rows=413028,all_roots_and_growth_reconciled=True,
            initial_funded_risk_not_loss_bound=True,unentered_Y_is_null=True,all20_seeds_preserved=True,
            new_SQL=0,new_fits=0,new_labels=0,new_cash=0,native_cache_reads=0,
            causal_AI_or_sizing_effect_identified=False,original138_verdict_unchanged=True,
            goal_complete=False,increased_betting_qualified=False,production_qualified=False)
        assert all(diag.get(k) == v for k,v in diagnostic_expected.items()), 'diagnostic science/limit fields'
        number(diag['accounting_max_absolute_error_CNY'])
        receipt = dict(schema='stage141_incremental_funded_gap_review_v1',status='completed',
                       counts=dict(Critical=0,Important=0,Minor=0),exact_inputs=identity,checks=checks,
                       account_count=88,pair_count=84,book_parent_rows=432696,pair_parent_rows=413028,
                       summary_groups=expected['aggregate_summaries'].to_dict('records'),
                       new_SQL=0,new_fits=0,new_labels=0,new_cash=0,native_cache_reads=0,
                       old_native_or_funding_requalified=False,old_review_entrypoints_called=False,
                       author_math_imported=False,original138_verdict_unchanged=True,
                       causal_AI_or_sizing_effect_identified=False,goal_complete=False,
                       increased_betting_qualified=False,production_qualified=False,
                       elapsed_seconds=time.monotonic()-started)
        write(output/'review_receipt.json',receipt)
        write(output/'actual_terminal.json',dict(status='completed',exit_code=0,
              elapsed_seconds=time.monotonic()-started,new_SQL=0,new_fits=0,new_labels=0,new_cash=0,native_cache_reads=0))
        print(json.dumps(dict(status='completed',counts=receipt['counts'],elapsed_seconds=receipt['elapsed_seconds']),ensure_ascii=False))
    except BaseException:
        write(output/'actual_terminal.json',dict(status='failed',exit_code=1,error=traceback.format_exc(),
              elapsed_seconds=time.monotonic()-started,new_SQL=0,new_fits=0,new_labels=0,new_cash=0,native_cache_reads=0))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('protocol','protocol-sha256','attribution-manifest','attribution-manifest-sha256',
                  'source-bundle-sha256','authorization','authorization-sha256','output'):
        parser.add_argument('--'+field,required=True)
    execute(parser.parse_args())
