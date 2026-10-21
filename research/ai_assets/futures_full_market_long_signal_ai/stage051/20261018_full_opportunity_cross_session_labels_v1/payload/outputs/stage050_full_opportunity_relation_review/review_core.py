"""Independent Stage050 helpers; not executed against actual output at preflight.

No author calculation imports, source database reads, strategy simulation or fit.
Normalized saved peer observations establish mapping arithmetic; native-source
accuracy is separately checked only on bounded slices from the unique build.
"""
from __future__ import annotations

import hashlib
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import numpy as np
import pandas as pd


def require(condition, message):
    if not bool(condition):
        raise AssertionError(message)


def numeric(actual, expected, label, atol=1e-10, rtol=2e-10):
    a, b = np.asarray(actual, float), np.asarray(expected, float)
    require(a.shape == b.shape, label + ': shape')
    require(np.array_equal(np.isnan(a), np.isnan(b)), label + ': null pattern')
    require(np.array_equal(np.isfinite(a), np.isfinite(b)), label + ': finite pattern')
    finite = np.isfinite(a)
    require(np.allclose(a[finite], b[finite], atol=atol, rtol=rtol), label + ': numeric')
    return float(np.max(np.abs(a[finite]-b[finite]))) if finite.any() else 0.


def review_peer_mapping(feature, peers):
    """Reconstruct every saved peer assignment, summary and both q projections."""
    f, p = feature.reset_index(drop=True), peers.reset_index(drop=True)
    n, m = len(f), len(p)
    require(f.event_id.is_unique and not f.event_id.isna().any(), 'feature event IDs')
    require(np.array_equal(f.sequence_index.to_numpy(), np.arange(n)), 'feature sequence')
    require(not f.duplicated(['product_id', 'u_date']).any(), 'feature product/day')
    require((f.family_id == f.product_id.str.replace(r'_F$', '', regex=True)).all(), 'family identity')
    lookup = pd.Series(np.arange(n), index=f.event_id)
    seq = p.event_id.map(lookup)
    require(seq.notna().all(), 'peer outside full mother')
    ix = seq.to_numpy(np.int64)
    require(np.all(np.diff(ix) >= 0), 'peer mother order')
    counts = np.bincount(ix, minlength=n)
    starts = np.cumsum(counts)-counts
    require(np.array_equal(p.peer_index.to_numpy(), np.arange(m)-starts[ix]), 'peer ordinal')
    require(not p.duplicated(['event_id', 'peer_epoch']).any(), 'peer duplicate epoch')
    epoch = p.peer_epoch.astype(str).to_numpy()
    products = np.asarray([s.rsplit('.', 1)[0] for s in epoch])
    months = np.asarray([s.rsplit('.', 1)[1] for s in epoch])
    require(np.array_equal(products, f.product_id.to_numpy()[ix]), 'exact product/F isolation')
    require(np.all(epoch != f.reference_epoch.fillna('').to_numpy()[ix]), 'query exclusion')
    require(np.array_equal(months, p.nominal_month.astype(str).to_numpy()), 'nominal month identity')
    months_iso = np.asarray([s[:4]+'-'+s[4:]+'-01' for s in months], dtype='datetime64[D]')
    u_dates = np.asarray(f.u_date, dtype='datetime64[D]')
    tau = (months_iso-u_dates[ix]).astype('timedelta64[D]').astype(float)/365.
    require(np.all(tau > 0), 'positive immutable nominal tenor')
    errors = {'tau': numeric(p.tau_years, tau, 'tenor', 1e-14, 1e-14)}
    # Fixed tenor/epoch ordering is independent of which observation has a large r.
    tenor_order = np.lexsort((epoch, months, ix))
    require(np.array_equal(tenor_order, np.arange(m)), 'tenor/epoch order')
    new_month = np.ones(m, bool)
    if m > 1:
        new_month[1:] = (ix[1:] != ix[:-1]) | (months[1:] != months[:-1])
    distinct = np.bincount(ix, weights=new_month.astype(int), minlength=n).astype(int)
    require(np.array_equal(counts, f.peer_count.to_numpy()), 'peer count')
    require(np.array_equal(distinct, f.peer_distinct_month_count.to_numpy()), 'distinct-month count')
    r = p.log_return.to_numpy(float)
    require(np.isfinite(r).all(), 'peer returns finite')
    product_values, day_values = f.product_id.to_numpy(), f.u_date.to_numpy()
    hashes = np.asarray([
        hashlib.sha256(('stage046_maturity_relation_v1|'+str(product_values[j])+'|'
                        +str(day_values[j])+'|'+e).encode()).hexdigest()
        for j, e in zip(ix, epoch)
    ])
    source_order = np.lexsort((epoch, hashes, ix))
    require(np.array_equal(p.shuffled_source_epoch.astype(str).to_numpy(), epoch[source_order]), 'SHA256 return-source assignment')
    rank = np.empty(m, np.int64)
    rank[source_order] = np.arange(m)-starts[ix]
    require(np.array_equal(rank, p.shuffle_rank.to_numpy()), 'SHA256 original-peer rank')
    shuffled = r[source_order]
    require(np.array_equal(p.shuffled_log_return.to_numpy(float), shuffled), 'exact same return bag')
    valid = counts > 0
    mean_r = np.full(n, np.nan)
    mean_t = np.full(n, np.nan)
    mean_r[valid] = np.bincount(ix, weights=r, minlength=n)[valid]/counts[valid]
    mean_t[valid] = np.bincount(ix, weights=tau, minlength=n)[valid]/counts[valid]
    centered_r = r-mean_r[ix]
    centered_t = tau-mean_t[ix]
    std = np.full(n, np.nan)
    std[valid] = np.sqrt(np.bincount(ix, weights=centered_r**2, minlength=n)[valid]/counts[valid])
    rmin, rmax, tmin, tmax = [np.full(n, np.nan) for _ in range(4)]
    if m:
        first = starts[valid]
        rmin[valid] = np.minimum.reduceat(r, first)
        rmax[valid] = np.maximum.reduceat(r, first)
        tmin[valid] = np.minimum.reduceat(tau, first)
        tmax[valid] = np.maximum.reduceat(tau, first)
    for name, expected in [('return_mean', mean_r), ('return_std', std),
                           ('return_min', rmin), ('return_max', rmax),
                           ('tenor_span_years', tmax-tmin)]:
        errors[name] = numeric(f[name], expected, name)
    normalizer = f.normalizer.to_numpy(float)
    normalizer_ok = np.isfinite(normalizer) & (normalizer > 0)
    require(np.array_equal(f.normalizer_missing.to_numpy(), ~normalizer_ok), 'normalizer missing')
    q_ready = normalizer_ok & (distinct >= 3)
    require(np.array_equal(f.q_missing.to_numpy(), ~q_ready), 'q readiness from own N and peer months')
    require(np.array_equal(f.q_missing_reason.fillna('').ne('').to_numpy(), ~q_ready), 'q state reason')
    denominator = np.bincount(ix, weights=centered_t**2, minlength=n)
    require(np.all(denominator[q_ready] > 0), 'q nondegenerate tenor')
    for field, values in [('q_aligned', r), ('q_shuffled', shuffled)]:
        means = np.full(n, np.nan)
        means[valid] = np.bincount(ix, weights=values, minlength=n)[valid]/counts[valid]
        numerator = np.bincount(ix, weights=centered_t*(values-means[ix]), minlength=n)
        expected = np.full(n, np.nan)
        expected[q_ready] = numerator[q_ready]/denominator[q_ready]/normalizer[q_ready]
        errors[field] = numeric(f[field], expected, field, 1e-9, 3e-10)
    return {'feature_rows': n, 'peer_rows': m, 'q_ready': int(q_ready.sum()),
            'all_saved_mapping_and_bag_arithmetic': True,
            'native_peer_membership_and_log_returns_full_recomputed': False,
            'native_scope': 'bounded saved native cases separately; no SQL',
            'max_absolute_errors': errors}


def adverse_price(reference, tick, side, scenario):
    """Independent exact-decimal formulation of the frozen adverse-price rule."""
    x = Decimal(str(float(reference)))
    fraction, ticks = (Decimal('0.0001'), 1) if scenario == 'base' else (Decimal('0.0003'), 3)
    change = x.copy_abs()*fraction
    has_tick = np.isfinite(tick) and tick > 0
    if has_tick:
        step = Decimal(str(float(tick)))
        change = max(change, step*ticks)
    price = x+change if side == 'BUY' else x-change
    if has_tick:
        price = (price/step).to_integral_value(rounding=ROUND_CEILING if side == 'BUY' else ROUND_FLOOR)*step
    return float(price)


def review_labels(labels, features, mother, calendar):
    """Full saved-table identity, causal state clocks and closed-cash arithmetic."""
    l, f = labels.reset_index(drop=True), features.reset_index(drop=True)
    require(len(l) == len(mother) == len(f), 'full mother lengths')
    require(len(l) == 399252, 'fixed 004 mother length')
    identity = ['event_id', 'product_id', 'exchange', 'product', 'u_date',
                'reference_epoch', 'status', 'planned_execution_date', 'direction']
    for col in identity:
        require(l[col].fillna('').equals(mother[col].fillna('')), 'mother '+col)
    for col in ['event_id', 'product_id', 'u_date', 'reference_epoch', 'status', 'family_id']:
        require(l[col].fillna('').equals(f[col].fillna('')), 'feature/label '+col)
    require(np.array_equal(l.sequence_index, np.arange(len(l))), 'label sequence')
    date_to_index = {d: i for i, d in enumerate(calendar)}
    u = l.u_date.map(date_to_index).to_numpy(int)
    require(np.array_equal(u, l.u_index), 'label u source index')
    require(np.array_equal(u+1, l.D_index), 'strict source successor index')
    require(np.array_equal(u, f.u_index), 'feature u source index')
    require((l.family_id == l.product_id.str.replace(r'_F$', '', regex=True)).all(), 'label family')
    ready = ((l.history_run >= 20) & np.isfinite(l.N_u) & (l.N_u > 0)
             & np.isfinite(l.low20_u) & (l.low20_u > 0)).to_numpy()
    require(np.array_equal(ready, l.label_history_ready20), 'history20 no55 gate')
    closed = l.label_state.eq('closed_complete_bar_model').to_numpy()
    filled = l.filled.eq(1).to_numpy()
    nonpart = l.participation_state.eq('known_nonparticipation').to_numpy()
    require(np.array_equal(closed, l.trade_label_known.eq(1)), 'closed maturity flag')
    require(np.all(ready[filled]) and np.all(filled[closed]), 'ready then filled then closed')
    require(np.array_equal(l.policy_diagnostic_pnl.notna(), nonpart), 'only cancellation policy diagnostic')
    numeric(l.loc[nonpart, 'policy_diagnostic_pnl'], np.zeros(nonpart.sum()), 'known cancel zero')
    require(not l.loc[~closed, ['label_known_date', 'label_known_phase', 'exit_index', 'exit_date']].notna().any().any(), 'nonclosed no label clock/exit')
    require(not l.loc[nonpart, ['net_R_base', 'net_R_stress']].notna().any().any(), 'cancel is not trade zero')
    require(l.loc[closed, 'label_known_date'].equals(l.loc[closed, 'exit_date']), 'exit maturity date')
    require(l.loc[closed, 'label_known_phase'].eq('after_all_source_close').all(), 'maturity after all closes')
    numeric(l.loc[filled, 'entry_index'], u[filled]+1, 'filled entry successor')
    require((l.loc[closed, 'exit_index'] >= l.loc[closed, 'entry_index']).all(), 'exit after entry')
    numeric(l.loc[closed, 'holding_source_days'], l.loc[closed, 'exit_index']-l.loc[closed, 'entry_index']+1, 'closed inclusive source duration')
    for name in ['entry', 'exit', 'unknown']:
        active = l[name+'_index'].notna().to_numpy()
        idx = l.loc[active, name+'_index'].to_numpy(int)
        require(np.array_equal(l.loc[active, name+'_date'], np.asarray(calendar)[idx]), name+' source date')
    numeric(l.loc[filled, 'entry_boundary'], np.maximum(l.loc[filled, 'SL0'], l.loc[filled, 'low20_u']), 'entry previous low boundary')
    numeric(l.loc[filled, 'SL0'], l.loc[filled, 'entry_reference']-2*l.loc[filled, 'N_u'], 'SL0 ideal F minus2N')
    unknown_entry = l.label_state.eq('entry_execution_unknown').to_numpy()
    require(not filled[unknown_entry].any(), 'unknown entry unfilled')
    numeric(l.loc[unknown_entry, 'unknown_index'], u[unknown_entry]+1, 'unknown D strict successor')
    unknown_path = l.label_state.eq('path_or_execution_unknown').to_numpy()
    require(filled[unknown_path].all(), 'unknown held path filled')
    require(not l.loc[unknown_path, ['net_R_base', 'net_R_stress', 'exit_reference']].notna().any().any(), 'absorbing unknown null')
    open_mask = l.label_state.eq('open_right_censored').to_numpy()
    require(filled[open_mask].all(), 'open censor filled')
    end = int(u.max())
    numeric(l.loc[open_mask, 'last_path_index'], np.full(open_mask.sum(), end), 'open censor at report end')
    lifecycle_cancel = l.cancel_reason.eq('known_entry_ineligible_lifecycle').to_numpy()
    require((l.loc[lifecycle_cancel, 'D_index'] >= l.loc[lifecycle_cancel, 'lifecycle_index']).all(), 'known lifecycle boundary')
    require(l.loc[lifecycle_cancel, 'participation_known_date'].equals(l.loc[lifecycle_cancel, 'u_date']), 'lifecycle cancellation known at u')
    quote_cancel = (nonpart & ~lifecycle_cancel)
    require(l.loc[quote_cancel, 'participation_known_date'].equals(l.loc[quote_cancel, 'planned_execution_date']), 'quote cancellation known at D')
    errors = {}
    norm = np.full(len(l), np.nan)
    norm_ready = (np.isfinite(l.N_u) & (l.N_u > 0) & np.isfinite(l.u_close) & (l.u_close > 0)).to_numpy()
    norm[norm_ready] = (l.N_u/l.u_close).to_numpy()[norm_ready]
    errors['normalizer_N042_over_C'] = numeric(f.normalizer, norm, 'shared label/feature causal N normalization')
    c = l.loc[closed]
    errors['fixed_cash_risk_unit'] = numeric(c.cash_risk_unit, 2*c.N_u*c.multiplier, '2N*M denominator')
    errors['gross_reference'] = numeric(c.gross_R_reference, (c.exit_reference-c.entry_reference)/(2*c.N_u), 'gross R reference')
    for scenario in ['base', 'stress']:
        targets = ['net_R_'+scenario, 'net_pnl_'+scenario+'_per_lot']
        require(not l.loc[~closed, targets].notna().any().any(), scenario+' all unknown/censor/cancel targets null')
        require(np.isfinite(c[targets].to_numpy(float)).all(), scenario+' closed targets finite')
        for part, side in [('entry', 'BUY'), ('exit', 'SELL')]:
            fills = np.asarray([adverse_price(ref, tick, side, scenario)
                                for ref, tick in zip(c[part+'_reference'], c.tick_size)])
            errors[scenario+'_'+part+'_fill'] = numeric(c[scenario+'_'+part+'_fill'], fills, scenario+' adverse '+part, 1e-8)
            minfee, rate = (2., .0001) if scenario == 'base' else (6., .0003)
            fees = np.maximum(minfee, np.abs(fills)*c.multiplier.to_numpy()*rate)
            errors[scenario+'_'+part+'_fee'] = numeric(c[scenario+'_'+part+'_fee_per_lot'], fees, scenario+' '+part+' fee', 1e-8)
            slip = np.abs(fills-c[part+'_reference'].to_numpy())*c.multiplier.to_numpy()
            errors[scenario+'_'+part+'_slippage'] = numeric(c[scenario+'_'+part+'_slippage_per_lot'], slip, scenario+' '+part+' slippage', 1e-8)
        expected_fee = c[scenario+'_entry_fee_per_lot']+c[scenario+'_exit_fee_per_lot']
        expected_slip = c[scenario+'_entry_slippage_per_lot']+c[scenario+'_exit_slippage_per_lot']
        errors[scenario+'_total_fee'] = numeric(c[scenario+'_total_fee_per_lot'], expected_fee, scenario+' total fee')
        errors[scenario+'_total_slippage'] = numeric(c[scenario+'_total_slippage_per_lot'], expected_slip, scenario+' total slip')
        net = c.multiplier*(c[scenario+'_exit_fill']-c[scenario+'_entry_fill'])-expected_fee
        errors[scenario+'_net_CNY'] = numeric(c['net_pnl_'+scenario+'_per_lot'], net, scenario+' cash net', 1e-7)
        errors[scenario+'_net_R'] = numeric(c['net_R_'+scenario], net/(2*c.N_u*c.multiplier), scenario+' fixed risk R', 1e-10)
    return {'mother_rows': len(l), 'history_ready20': int(ready.sum()), 'filled': int(filled.sum()),
            'complete_trade_labels': int(closed.sum()), 'label_states': l.label_state.value_counts().to_dict(),
            'max_absolute_errors': errors, 'independent_events_not_accounts': True}


def review_front_support(features, peers, labels):
    """Full front/next identity/span support; absolute price levels use native cases."""
    n = len(features)
    lookup = pd.Series(np.arange(n), index=features.event_id)
    ix = peers.event_id.map(lookup).to_numpy(int)
    epochs = peers.peer_epoch.astype(str).to_numpy()
    months = np.asarray([s.rsplit('.', 1)[1] for s in epochs])
    query = features.reference_epoch.fillna('').astype(str).to_numpy()
    qmonth = np.asarray([s.rsplit('.', 1)[-1] if s else '' for s in query])
    qdate = np.asarray([s[:4]+'-'+s[4:]+'-01' if len(s) == 6 else '' for s in qmonth])
    own_pair = (labels.history_run.to_numpy() >= 2) & (qdate > features.u_date.to_numpy())
    all_ix = np.concatenate([ix, np.flatnonzero(own_pair)])
    all_epoch = np.concatenate([epochs, query[own_pair]])
    all_month = np.concatenate([months, qmonth[own_pair]])
    order = np.lexsort((all_epoch, all_month, all_ix))
    group, month, epoch = all_ix[order], all_month[order], all_epoch[order]
    distinct = np.ones(len(group), bool)
    if len(group) > 1:
        distinct[1:] = (group[1:] != group[:-1]) | (month[1:] != month[:-1])
    group, month, epoch = group[distinct], month[distinct], epoch[distinct]
    count = np.bincount(group, minlength=n)
    starts = np.cumsum(count)-count
    rank = np.arange(len(group))-starts[group]
    front, following = np.full(n, '', object), np.full(n, '', object)
    first_month, second_month = np.full(n, '', object), np.full(n, '', object)
    first = rank == 0
    second = rank == 1
    front[group[first]], first_month[group[first]] = epoch[first], month[first]
    following[group[second]], second_month[group[second]] = epoch[second], month[second]
    require(np.array_equal(features.front_epoch.fillna('').to_numpy(), front), 'full front identity with query')
    require(np.array_equal(features.next_epoch.fillna('').to_numpy(), following), 'full next distinct month identity')
    complete = following != ''
    require(np.array_equal(features.front_next_missing.to_numpy(), ~complete), 'front control support/null')
    for field in ['front_next_basis_u', 'front_next_basis_prev', 'front_next_tenor_span_years']:
        require(np.array_equal(np.isfinite(features[field].to_numpy(float)), complete), field+' support')
    expected = np.full(n, np.nan)
    for i in np.flatnonzero(complete):
        a, b = first_month[i], second_month[i]
        da = np.datetime64(a[:4]+'-'+a[4:]+'-01')
        db = np.datetime64(b[:4]+'-'+b[4:]+'-01')
        expected[i] = float((db-da)/np.timedelta64(1, 'D'))/365.
    error = numeric(features.front_next_tenor_span_years, expected, 'full front-next tenor span', 1e-14, 1e-14)
    return {'rows': n, 'front_next_available': int(complete.sum()), 'identity_span_and_missing_full': True,
            'absolute_log_levels_full_source_recomputed': False, 'absolute_log_levels_scope': 'bounded native case',
            'tenor_span_max_absolute_error': error}
