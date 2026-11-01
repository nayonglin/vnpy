"""Pure Friday portfolio-batch funding advice; never credits or sends money.

The caller must admit the real account source, persist the returned cash state
with its runtime actor in one CAS, then render/send. The original committed
strategy decision and its AM/state snapshot are deliberately left untouched.
"""
from copy import deepcopy
from datetime import date,datetime
import hashlib,json
from qmt_roll_weekly19_pipeline_state import PipelineStateStore
import qmt_roll_weekly19_funding as funding

class FridayAdviceError(ValueError):pass

def _require(condition,reason):
    if not condition:raise FridayAdviceError(reason)

def _digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def _source(bundle,friday):
    _require(isinstance(bundle,dict),'friday_bundle_required')
    # Reuse the existing read-only validator, including the immutable decision
    # origin and funding-forward ledger. Construction performs no filesystem IO.
    validator=PipelineStateStore('/__weekly19_advice_validation__/state.json',bundle['account_key'],bundle['material_release_id'])
    validator._validate(bundle)
    decision=bundle['decision']
    _require(isinstance(decision,dict)and decision.get('production_qualified')is False,'friday_original_decision_required')
    target=date.fromisoformat(decision['trading_date'])
    _require(target<=friday and target.isocalendar()[:2]==friday.isocalendar()[:2],'friday_original_target_not_current_week')
    source=funding._sha(decision['data_receipt_sha256'])
    ids=decision.get('funding_admitted_ids')
    _require(isinstance(ids,list)and len(ids)<=1000 and all(isinstance(x,str)and x and x.strip()==x for x in ids)
             and len(ids)==len(set(ids)),'friday_original_admitted_ids_invalid')
    records=decision.get('funding_admissions')
    _require(isinstance(records,list)and len(records)==len(ids),'friday_original_admission_records_missing')
    found=[]
    for row in records:
        identity=row['admitted_entry_id'];execution=date.fromisoformat(row['execution_day'])
        _require(row.get('original_funding_admission_id')==identity
            and row.get('signal_identity',{}).get('admitted_entry_id')==identity
            and isinstance(row.get('vt_symbol'),str)and bool(row['vt_symbol'])and execution>target,
            'friday_original_admission_record_invalid')
        found.append(identity)
    _require(len(found)==len(set(found))and set(found)==set(ids),'friday_original_admission_binding_mismatch')
    return dict(account_key=bundle['account_key'],material_release_id=bundle['material_release_id'],
        original_target_date=target.isoformat(),canonical_friday=friday.isoformat(),data_receipt_sha256=source,
        original_admitted_ids=deepcopy(ids),decision_snapshot_sha256=_digest(decision),
        decision_origin_state_sha256=bundle['decision_state']['state_sha256'])

def refresh_friday_advice(bundle,broker_account,now):
    """Return funding/recommendation/source bindings without mutating inputs.

    Any invalid source/cash continuity returns the ORIGINAL cash with zero
    actionable amount. A paid part of one original portfolio batch never lets
    unregistered remaining IDs create a second offer for that batch.
    """
    original=deepcopy(bundle.get('funding'))if isinstance(bundle,dict)else None
    def blocked(reason,status='blocked'):
        return dict(schema='weekly19.friday-advice.v1',status=status,funding=deepcopy(original),
            recommendation=dict(status=status,amount_fen=0,request_id=None,actionable=False,
                blocked_reason=reason,production_qualified=False),source_bindings=None,advice_id=None,
            blockers=[reason],production_qualified=False,order_api_called_count=0)
    try:
        _require(isinstance(now,datetime)and now.tzinfo is not None and now.utcoffset()is not None,'friday_aware_clock_required')
        local=now.astimezone(funding.SHANGHAI)
        if local.weekday()!=4:return blocked('friday_advice_only','not_friday')
        bindings=_source(bundle,local.date());cash=deepcopy(original)
        _require(cash['cashflow_checkpoint']is not None,'friday_cashflow_observation_missing')
        snapshot=funding._broker(broker_account,cash,now)
        week=bindings['canonical_friday'];source=bindings['data_receipt_sha256'];ids=bindings['original_admitted_ids']
        batch=[row for row in cash['requests'].values()if row['target_week_end']==week and row['source_sha256']==source]
        _require(all(set(row['admitted_entry_ids']).issubset(set(ids))for row in batch),'friday_request_original_batch_mismatch')
        consumed=any(row['confirmed_fen']>0 or cash['retirements'].get(row['request_id'],{}).get('reason')in
                     {'equity_recovered','expired_superseded'}for row in batch)
        active=next((row for row in cash['requests'].values()if row['status']in{'pending','partially_confirmed'}),None)
        desired=min(max(funding.INITIAL_FEN-snapshot['balance_fen'],0),cash['reserve_remaining_fen'])
        original_remaining=active['amount_fen']-active['confirmed_fen']if active else 0
        current_active=bool(active and active['target_week_end']==week and active['source_sha256']==source)
        if active:
            _require(active['target_week_end']<week or current_active,'friday_active_offer_has_different_source')
            reason=None
            if snapshot['balance_fen']>=funding.INITIAL_FEN:reason='equity_recovered'
            elif now>=datetime.fromisoformat(active['expires_at']):reason='expired_superseded'
            elif desired>0 and desired!=original_remaining and not(current_active and active['confirmed_fen']>0):reason='superseded_current_gap'
            if reason:
                cash=funding.retire_topup_request(cash,active['request_id'],broker_account,now,reason=reason)
                if current_active and reason in {'equity_recovered','expired_superseded'}:consumed=True
                active=None
        # Empty IDs still ask the public boundary to prove known Deposit,
        # Withdraw and day-close continuity, without reopening a consumed batch.
        result=funding.recommend_topup(cash,broker_account,week,[]if consumed and active is None else ids,source,now)
        proposed=result['state'];recommendation=deepcopy(result['recommendation'])
        if consumed and active is None:
            recommendation=dict(status='equity_at_or_above_floor'if snapshot['balance_fen']>=funding.INITIAL_FEN else'duplicate_admission',
                amount_fen=0,request_id=None,actionable=False,production_qualified=False)
        elif current_active and active is not None and active['confirmed_fen']>0 and desired!=original_remaining:
            recommendation.update(status='confirmed_batch_no_additional_offer',amount_fen=0,request_id=None,actionable=False,
                blocked_reason='original_batch_has_confirmed_cash',historical_request_remaining_fen=original_remaining)
        # Creation and its immediate replay describe the same durable offer.
        if recommendation['status']=='topup_recommended':recommendation['status']='funding_pending'
        offers=[row for row in proposed['requests'].values()if row['target_week_end']==week and row['source_sha256']==source]
        latest=max(offers,key=lambda row:(row.get('attempt',0),row['created_at'],row['request_id']))if offers else active
        offered_remaining=latest['amount_fen']-latest['confirmed_fen']if latest is not None else 0
        stable=dict(source_bindings=bindings,recommendation=recommendation,funding_state_sha256=_digest(proposed))
        return dict(schema='weekly19.friday-advice.v1',status='ready',funding=proposed,recommendation=recommendation,
            source_bindings=bindings,advice_id=_digest(stable),original_offer_remaining_fen=offered_remaining,
            before_funding_sha256=_digest(original),after_funding_sha256=_digest(proposed),
            broker_account_raw_sha256=broker_account['raw_sha256'],blockers=[],production_qualified=False,order_api_called_count=0)
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError)as exc:
        return blocked(str(exc))
