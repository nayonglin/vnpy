"""Same warm CTP session -> source-verified weekly19 actor and durable bundle.

No gateway construction, connection, query, send, SMTP, market bootstrap or
qualification shortcut. The runner supplies native packets and completed same-
connection epochs; the controller supplies a process-local admitted authority.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime,timezone
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
from threading import RLock
import uuid
from vnpy.trader.constant import Exchange
from vnpy.trader.event import EVENT_TICK
from vnpy.trader.object import SubscribeRequest
import qmt_roll_weekly19_broker_evidence as broker
import qmt_roll_weekly19_funding as funds
import qmt_roll_weekly19_warm_evidence as warm
from qmt_roll_weekly19_controller import Weekly19ControllerAuthority
from qmt_roll_weekly19_pipeline_state import PipelineStateStore,digest,unique
from qmt_roll_weekly19_runtime import RuntimeContractError,_decode
from qmt_roll_weekly19_quote_spool import read_weekly19_quote_snapshot
from qmt_roll_official_execution_profile import WEEKLY19_15W_R150K_PROFILE as PROFILE
from qmt_roll_official_live_tick_stream import TickStreamPipeline,install_gateway_tick_ingress
from qmt_roll_official_live_tick_types import DurableTickCursor

class SessionBridgeError(ValueError):pass

def _require(value,reason):
    if not value:raise SessionBridgeError(reason)

def _sha(raw):return hashlib.sha256(raw).hexdigest()

def _private_directory(path):
    path=Path(path).expanduser().absolute()
    _require(not path.is_symlink(),'weekly19_bridge_private_symlink')
    path=path.resolve(strict=False)
    _require(not any((p/'.git').exists() for p in (path,*path.parents)),'weekly19_bridge_private_directory_outside_checkout_required')
    path.mkdir(mode=0o700,parents=True,exist_ok=True)
    _require(path.stat().st_uid==os.geteuid() and stat.S_IMODE(path.stat().st_mode)==0o700,'weekly19_bridge_private_directory_required')
    return path

def _read_private(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        info=os.fstat(fd)
        _require(stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid() and info.st_nlink==1 and stat.S_IMODE(info.st_mode)==0o600,'weekly19_bridge_private_file_required')
        fcntl.flock(fd,fcntl.LOCK_SH)
        with os.fdopen(fd,'rb',closefd=False) as stream:raw=stream.read(64_000_001)
        _require(len(raw)<=64_000_000,'weekly19_bridge_private_file_oversized')
        return raw
    finally:os.close(fd)

def _write_private(path,raw):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    directory=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(directory)
    finally:os.close(directory)
    return dict(path=str(path),sha256=_sha(raw))

def _envelope(raw):return json.loads(raw['raw_payload'],object_pairs_hook=unique)

def _event_key(kind,raw):
    return ('fill:'+str(raw['trade_id'])) if kind=='fill' else 'order:'+str(raw['event_id'])

CASH_WAIT={'day_roll_requires_reconciliation','unreconciled_cashflow_deposit','unreconciled_cashflow_withdrawal',
    'funding_pending','cashflow_baseline_missing'}

class Weekly19SessionBridge:
    def __init__(self,*,runtime_actor,bundle,data,authority,state_store,clock,private_root,
                 execution_ledger_path,reconcile_cash,session_provider,quote_reader=None,
                 require_production_qualification=True):
        _require(isinstance(authority,Weekly19ControllerAuthority),'weekly19_typed_controller_authority_required')
        _require(isinstance(state_store,PipelineStateStore),'weekly19_pipeline_state_store_required')
        _require(callable(reconcile_cash) and callable(session_provider),'weekly19_process_local_cash_session_providers_required')
        _require(type(require_production_qualification) is bool,'weekly19_bridge_mode_invalid')
        self.runtime_actor=runtime_actor;self.data=data;self.authority=authority;self.store=state_store;self.clock=clock
        self.reconcile_cash=reconcile_cash;self.session_provider=session_provider;self.quote_reader=quote_reader or read_weekly19_quote_snapshot
        self.production=require_production_qualification;self.actor_lock=RLock();self.service=None;self.native=None;self._poison_reason=None
        self.ledger_path=Path(execution_ledger_path).expanduser().absolute();self.cash_source_blocker=None;self.external_cash_source_blocker=None
        self.authority.assert_current(self.now())
        _require(authority.bindings.get('account_fingerprint')==runtime_actor.account and authority.bindings.get('material_release_id')==runtime_actor.release,'weekly19_bridge_authority_actor_mismatch')
        _require(bundle.get('runtime',{}).get('state_sha256')==runtime_actor.export_state()['state_sha256'],'weekly19_bridge_initial_actor_bundle_mismatch')
        _require(data['receipt']['material_release_id']==runtime_actor.release,'weekly19_bridge_data_release_mismatch')
        self.last_bundle=deepcopy(bundle)
        origin=_decode(bundle['decision_state']['runtime'])
        self.signal_origin_equity_fen=funds._money(_envelope(origin['broker_snapshot']['account'])['Balance'])
        if self.production:
            _require(isinstance(authority.capture_authority,broker.CaptureAuthority),'weekly19_preloaded_capture_authority_required')
        self._assert_authority()
        self.private_root=_private_directory(private_root)
        # A function clock remains a shared read-only dependency when the
        # runtime clones sizing state; never deepcopy this bridge or its locks.
        self.runtime_actor.clock=lambda: self.now()

    def now(self):return datetime.fromtimestamp(self.clock.epoch_ns()/1e9,tz=timezone.utc)

    def _assert_authority(self):
        _require(self._poison_reason is None,self._poison_reason)
        self.authority.assert_current(self.now())
        _require(self.authority.bindings.get('target_cutoff_date')==self.data['receipt']['trading_date'],'weekly19_bridge_authority_target_mismatch')
        expected=self.authority.bindings.get('source_data_receipt_sha256')
        if expected is not None:_require(expected==funds._hash(self.data['receipt']),'weekly19_bridge_authority_data_receipt_mismatch')

    def bind_service(self,service):
        _require(self.service in (None,service),'weekly19_bridge_service_replacement_forbidden')
        service.bind_actor(self.runtime_actor);self.service=service;self.actor_lock=service.actor_lock
        return self

    def authority_provider(self,*,now):self.authority.assert_current(now);return self.authority

    def _policy(self):
        policy=dict(self.authority.broker_policy,now=self.now(),require_production_qualification=self.production)
        policy.update(expected_account_key=self.runtime_actor.account,material_release_id=self.runtime_actor.release,execution_profile=PROFILE.profile_key)
        if self.authority.capture_authority is not None:policy['capture_authority_capability']=self.authority.capture_authority
        return policy

    def _typed_ledger(self,path=None):
        return broker.load_execution_order_intent_bindings(path or self.ledger_path,expected_account_key=self.runtime_actor.account,
            material_release_id=self.runtime_actor.release,execution_profile=PROFILE.profile_key)

    def _section(self,bundle):
        section=bundle.setdefault('session_bridge',dict(schema='weekly19.session-bridge-state.v1',deferred={},resolved_ids=[],event_sources={}))
        _require(section.get('schema')=='weekly19.session-bridge-state.v1' and isinstance(section.get('deferred'),dict),'weekly19_bridge_durable_schema_invalid')
        return section

    def _commit(self,operation):
        """Commit or reload actual disk state; uncertain durability is never success."""
        with self.actor_lock:
            _require(self._poison_reason is None,self._poison_reason)
            before=self.runtime_actor.export_state();result={}
            def advance(bundle):
                _require(bundle.get('runtime',{}).get('state_sha256')==before['state_sha256'],'weekly19_bridge_actor_store_diverged')
                section=self._section(bundle);result['value']=operation(section)
                bundle['runtime']=self.runtime_actor.export_state();bundle['funding']=deepcopy(self.runtime_actor.confirmed_cash_state)
                return bundle
            try:
                committed=self.store.transact(advance)
                self.last_bundle=committed
                return result.get('value'),committed
            except BaseException:
                # os.replace may have installed the new bundle before the
                # directory fsync failed. The actual checked store, rather
                # than the pre-operation snapshot, decides actor recovery.
                # This never converts an unacknowledged commit into success.
                try:
                    actual=self.store.read()
                    _require(isinstance(actual,dict) and isinstance(actual.get('runtime'),dict),'weekly19_bridge_commit_recovery_bundle_missing')
                    self.runtime_actor._restore(actual['runtime'])
                    self.last_bundle=deepcopy(actual)
                except BaseException as recovery_error:
                    self._poison_reason='weekly19_bridge_owner_poisoned_after_commit_failure:'+type(recovery_error).__name__
                raise

    def _receipt(self,bundle,*,status='applied',deferred_id=None):
        section=self._section(bundle)
        result=dict(status=status,state_sha256=bundle['runtime']['state_sha256'],durable_bundle_sha256=digest(bundle),
            pipeline_revision=bundle['revision'],production_qualified=False)
        if status=='deferred_durable':result['durable_deferred_id']=deferred_id
        else:result['resolved_deferred_ids']=list(section['resolved_ids'])
        return result

    def _known_order_fills(self,raw):
        oid=raw['signal_order_id'];plan=self.runtime_actor.engine.order_intents.get(oid)
        _require(plan is not None and raw.get('signal_identity')==plan['signal_identity'],'weekly19_bridge_order_original_identity_missing')
        if 'execution_batch_id' in raw or 'api_slot_batch_id' in raw:
            _,child,_=self.runtime_actor._child_batch(raw,plan)
            return child['filled']
        return self.runtime_actor.engine.order_filled[oid]

    def _apply_one(self,kind,envelope,section,source):
        raw=_envelope(envelope);key=_event_key(kind,raw)
        if kind=='order':
            known=self._known_order_fills(raw)
            if raw['traded']>known:
                deferred_id='W19DEFER:'+funds._hash([self.runtime_actor.account,self.runtime_actor.release,key])
                record=dict(kind='order',envelope=deepcopy(envelope),source=deepcopy(source),admitted_at=self.now().isoformat())
                old=section['deferred'].get(deferred_id)
                if old is not None:
                    _require(_envelope(old['envelope']).get('event_semantic_sha256')==raw.get('event_semantic_sha256'),'weekly19_bridge_deferred_identity_conflict')
                else:section['deferred'][deferred_id]=record
                return dict(status='deferred_durable',deferred_id=deferred_id,key=key)
            # An earlier nonterminal order fact cannot roll back consumed actual
            # fills. Record it durably as superseded; it releases no capacity.
            if raw['traded']<known and raw['status'] in ('accepted','working','partially_filled'):
                section['event_sources'][key]=dict(source=deepcopy(source),disposition='superseded_by_consumed_actual_fill')
                return dict(status='duplicate',key=key)
            duplicate=raw['event_id'] in self.runtime_actor.order_updates
            self.runtime_actor.apply_order_update(envelope)
        else:
            duplicate=raw['trade_id'] in self.runtime_actor.fills
            self.runtime_actor.apply_broker_fill(envelope,raw['signal_identity'])
        record=section['event_sources'].setdefault(key,dict(source=deepcopy(source),admitted_at=self.now().isoformat()))
        if kind=='fill':record.setdefault('envelope',deepcopy(envelope))
        return dict(status='duplicate' if duplicate else 'applied',key=key)

    def _replay_deferred(self,section):
        resolved=[]
        for identity,record in list(section['deferred'].items()):
            if record['kind']!='order':continue
            raw=_envelope(record['envelope'])
            if raw['traded']>self._known_order_fills(raw):continue
            result=self._apply_one('order',record['envelope'],section,record['source'])
            if result['status']!='deferred_durable':
                section['deferred'].pop(identity);resolved.append(identity)
        for identity in resolved:
            if identity not in section['resolved_ids']:section['resolved_ids'].append(identity)
        return resolved

    def _consume_batch(self,events,source):
        outcomes={}
        def operation(section):
            for fill in sorted(events.get('fills',[]),key=lambda e:(_envelope(e)['execution_datetime'],_envelope(e)['trade_id'])):
                result=self._apply_one('fill',fill,section,source);outcomes[result['key']]=result
            self._replay_deferred(section)
            for order in events.get('orders',[]):
                result=self._apply_one('order',order,section,source);outcomes[result['key']]=result
            self._replay_deferred(section)
            return outcomes
        _,bundle=self._commit(operation)
        return outcomes,bundle

    def event_consumer(self,kind,row,original,*,runtime_actor):
        with self.actor_lock:
            _require(runtime_actor is self.runtime_actor,'weekly19_bridge_actor_replacement_forbidden');self._assert_authority()
            _require(kind in ('order','trade','fill'),'weekly19_bridge_native_kind_invalid')
            proof=row.get('weekly19_native_proof')
            _require(isinstance(proof,dict) and isinstance(proof.get('capture_reference'),dict),'weekly19_bridge_native_capture_reference_required')
            reference=proof['capture_reference']
            _require(reference.get('admission_state')!='buffered','weekly19_bridge_startup_packet_not_yet_admitted')
            ledger=self._typed_ledger()
            events=broker.load_native_broker_events(reference,ledger,**self._policy())
            _require(not self.production or events.get('source_qualified') is True,'weekly19_bridge_native_source_not_qualified')
            actual_kind='order' if kind=='order' else 'fill';native_sha=funds._hash(proof['native'])
            candidates=[event for event in events['orders' if actual_kind=='order' else 'fills'] if _envelope(event).get('raw_native_sha256')==native_sha]
            _require(len(candidates)==1,'weekly19_bridge_normalized_native_reference_mismatch')
            raw=_envelope(candidates[0]);business=original.get('planned_intent_id') or original.get('intent_id')
            if business:_require(business==raw['intent_id'],'weekly19_bridge_delivery_original_mismatch')
            outcomes,bundle=self._consume_batch(events,dict(kind='native_push',capture_reference=deepcopy(reference)))
            result=outcomes[_event_key(actual_kind,raw)]
            return self._receipt(bundle,status=result['status'],deferred_id=result.get('deferred_id'))

    def _cash(self,snapshot):
        before=self.runtime_actor.confirmed_cash_state
        cash=self.reconcile_cash(deepcopy(before),snapshot,self.now());funds.validate_state(cash)
        cash_owner=getattr(self.reconcile_cash,'__self__',None)
        self.external_cash_source_blocker=getattr(cash_owner,'cash_source_blocker',None)
        self.cash_source_blocker=self.external_cash_source_blocker
        try:funds.assert_open_funding_ready(cash,snapshot['account'],self.now())
        except funds.FundingError as exc:
            if str(exc) not in CASH_WAIT:raise
            self.cash_source_blocker=str(exc)
        return cash

    def _snapshot(self,transport):
        self._assert_authority();snapshot=warm.load_warm_broker_snapshot(transport,**self._policy())
        _require(not self.production or snapshot.get('source_qualified') is True,'weekly19_bridge_warm_source_not_qualified')
        _require(snapshot['connection_generation']==transport['connection_generation'] and snapshot['service_generation']==transport['service_generation'],'weekly19_bridge_warm_connection_mismatch')
        return snapshot

    def _metadata(self,row,transport):
        symbol=row['vt_symbol'];contract=transport['main_engine'].get_contract(symbol)
        _require(contract is not None and contract.gateway_name=='CTP' and contract.vt_symbol==symbol,'weekly19_bridge_actual_contract_missing')
        for name in ('pricetick','size','min_volume','max_volume'):
            value=getattr(contract,name,None)
            _require(type(value) in (int,float) and value>0,'weekly19_bridge_contract_field_missing:'+name)
        _require(contract.size==self.runtime_actor.metadata['sizes'][symbol] and
            contract.pricetick==self.runtime_actor.metadata['priceticks'][symbol],'weekly19_bridge_contract_spec_drift')
        epoch=row.get('physical_epoch_id')
        _require(epoch and epoch in set(self.runtime_actor.physical_frame.loc[self.runtime_actor.physical_frame.vt_symbol==symbol,'contract_epoch_id']),'weekly19_bridge_physical_epoch_missing')
        rate=str(Decimal(str(self.runtime_actor.metadata['margin_ratios'][symbol]))*Decimal(str(self.runtime_actor.strategy.stage830_broker_margin_multiplier)))
        return dict(vt_symbol=symbol,physical_epoch_id=epoch,pricetick=contract.pricetick,size=contract.size,
            min_volume=contract.min_volume,max_volume=contract.max_volume,broker_margin_rate=rate,
            margin_rate_source='frozen_model_estimate_not_broker_receipt',final_broker_capacity_gate_required=True)

    def _journal(self):
        _require(self.native is not None and self.native.tick_pipeline is not None,'weekly19_bridge_same_session_md_missing')
        snapshot=self.native.tick_pipeline.durable_snapshot()
        _require(snapshot.stream_ready and snapshot.gap is None and snapshot.writer_fault is None and snapshot.durable_ingress_sequence>0,'weekly19_bridge_durable_md_not_ready')
        cursor=DurableTickCursor(snapshot.feed_session_id,snapshot.durable_ingress_sequence,snapshot.durable_journal_byte_offset,snapshot.journal_schema)
        return snapshot.journal_segment_path,cursor

    def _quote_session(self,row,transport,snapshot):
        session=self.session_provider(row,transport_context=transport,now=self.now())
        account=_envelope(snapshot['account']);day=account['trading_day']
        _require(isinstance(session,dict) and session.get('trading_date')==day,'weekly19_bridge_session_broker_day_mismatch')
        path,cursor=self._journal()
        quote=self.quote_reader(path,durable_through=cursor,symbol=row['vt_symbol'],clock=self.clock,trading_date=day,session=session)
        return quote,session

    def _accepted_business_fills(self,business_id):
        accepted=[]
        section=self._section(self.last_bundle)
        for record in section['event_sources'].values():
            evidence=record.get('envelope')
            if evidence is None:continue
            raw=_envelope(evidence)
            if raw.get('schema')!='weekly19.ctp-trade.v1' or raw.get('intent_id')!=business_id:continue
            actual=self.runtime_actor.fills.get(raw['trade_id'])
            _require(actual is not None,'weekly19_bridge_fill_not_in_actual_actor_ledger')
            keys=('account_key','material_release_id','trade_id','intent_id','signal_order_id','signal_identity',
                  'broker_order_id','vt_symbol','direction','offset','broker_offset','volume','price','trading_day','execution_datetime')
            semantic={key:raw[key] for key in keys}
            semantic['price']=float(raw['price']);semantic['execution_datetime']=funds._time(raw['execution_datetime']).astimezone(funds.SHANGHAI).isoformat()
            _require(funds._hash(semantic)==actual['semantic_sha256'],'weekly19_bridge_actual_fill_semantic_mismatch')
            accepted.append((raw,evidence))
        ids=[raw['trade_id'] for raw,_ in accepted]
        _require(len(ids)==len(set(ids)),'weekly19_bridge_actual_fill_evidence_duplicate')
        return accepted

    def _actual_fill_lifecycle(self,row,transport):
        parent=transport.get('weekly19_immutable_parent_intent')
        child=transport.get('weekly19_current_physical_child')
        if child is not None:_require(isinstance(parent,dict),'weekly19_bridge_immutable_delivery_parent_required')
        parent=parent or row
        for key in ('intent_id','planned_intent_id','signal_order_id','signal_identity'):
            _require(parent.get(key)==row.get(key),'weekly19_bridge_physical_parent_identity_mismatch')
        business=parent.get('planned_intent_id') or parent['intent_id']
        plan=next((p for p in self.runtime_actor.engine.order_intents.values() if p['intent_id']==business),None)
        _require(plan is not None,'weekly19_bridge_actual_lifecycle_plan_missing')
        oid=plan['signal_order_id'];approved=plan['planned_volume'];filled=self.runtime_actor.engine.order_filled[oid]
        parsed=Decimal(str(parent['planned_volume']))
        _require(parsed.is_finite() and parsed==parsed.to_integral_value() and 0<parsed<=approved,'weekly19_bridge_delivery_parent_volume_invalid')
        delivery_cap=int(parsed);delivery=parent['intent_id'] if parent.get('planned_intent_id') else None
        accepted=self._accepted_business_fills(business)
        _require(sum(raw['volume'] for raw,_ in accepted)==filled,'weekly19_bridge_actual_fill_source_evidence_incomplete')
        own=[raw for raw,_ in accepted if delivery is not None and raw.get('delivery_intent_id')==delivery]
        delivery_filled=sum(raw['volume'] for raw in own)
        _require(delivery_filled<=delivery_cap,'weekly19_bridge_delivery_actual_fill_exceeds_cap')
        if delivery is not None and filled:
            _require(bool(own),'weekly19_bridge_filled_business_belongs_to_another_delivery')
        batch=self.runtime_actor.child_batches.get(oid)
        children=[]
        if batch is not None:
            for descriptor in batch['expected_children']:
                actual=batch['children'][descriptor['child_order_id']]
                children.append(dict(descriptor,filled_volume=actual['filled'],status=actual['status'],broker_order_id=actual['broker_order_id']))
        return dict(schema='weekly19.actual-fill-lifecycle.v1',planned_intent_id=business,delivery_intent_id=delivery,
            signal_order_id=oid,business_approved_volume=approved,business_filled_volume=filled,business_remaining_volume=approved-filled,
            delivery_approved_volume=delivery_cap,delivery_filled_volume=delivery_filled,delivery_remaining_volume=delivery_cap-delivery_filled,
            delivery_trade_ids=sorted(raw['trade_id'] for raw in own),physical_batch_id=None if batch is None else batch['batch_id'],
            physical_children=children,durable_state_sha256=self.runtime_actor.export_state()['state_sha256'],production_qualified=False)

    def _completed_close_evidence(self,row):
        dependency=row.get('depends_on_close_intent_id')
        if not dependency:return []
        plan=next((p for p in self.runtime_actor.engine.order_intents.values() if p['intent_id']==dependency and p['offset']=='close'),None)
        if plan is None:return []
        oid=plan['signal_order_id'];filled=self.runtime_actor.engine.order_filled[oid]
        if self.runtime_actor.engine.order_terminal.get(oid)!='filled' or filled!=plan['planned_volume']:return []
        accepted=self._accepted_business_fills(dependency)
        if sum(raw['volume'] for raw,_ in accepted)!=filled:return []
        return [dict(intent_id=dependency,material_release_id=self.runtime_actor.release,account_fingerprint=self.runtime_actor.account,
            offset='close',vt_symbol=plan['vt_symbol'],requested_volume=plan['planned_volume'],filled_volume=filled,
            trade_ids=sorted(raw['trade_id'] for raw,_ in accepted),broker_fills=[deepcopy(evidence) for _,evidence in accepted])]

    def _reconcile_actual_source(self,snapshot,cash,*,quote_snapshot=None):
        try:
            self.runtime_actor.reconcile_broker_snapshot(snapshot,cash,quote_snapshot=quote_snapshot)
        except RuntimeContractError as exc:
            if str(exc)=='broker_strategy_position_mismatch':
                # A real push fill can advance the actor ahead of the last
                # signed four-query epoch. Never synthesize fresh positions.
                raise SessionBridgeError('weekly19_requires_source_reconciliation:broker_strategy_position_mismatch') from exc
            raise

    def fresh_context_provider(self,row,*,transport_context,runtime_actor):
        with self.actor_lock:
            _require(runtime_actor is self.runtime_actor,'weekly19_bridge_actor_replacement_forbidden')
            snapshot=self._snapshot(transport_context);ledger=self._typed_ledger();quote,session=self._quote_session(row,transport_context,snapshot)
            def reconcile(section):
                self._replay_deferred(section)
                _require(not section['deferred'],'weekly19_durable_broker_events_awaiting_replay')
                cash=self._cash(snapshot)
                self._reconcile_actual_source(snapshot,cash)
            self._commit(reconcile)
            original=row.get('planned_intent_id') or row['intent_id']
            proof=None
            if row['offset']=='open':
                _require(not self.external_cash_source_blocker,'weekly19_bridge_cash_source_blocked:'+str(self.external_cash_source_blocker))
                proof=self.runtime_actor.revalidate_open_intent(original,broker_snapshot=snapshot,confirmed_cash_state=self.runtime_actor.confirmed_cash_state,quote_snapshot=quote)
            return dict(material_release_id=self.runtime_actor.release,account_fingerprint=self.runtime_actor.account,
                trading_date=_envelope(snapshot['account'])['trading_day'],cold_start_date=self.runtime_actor.confirmed_cash_state['cold_start_date'],
                target_cutoff_date=self.data['receipt']['trading_date'],data_receipt_sha256=funds._hash(self.data['receipt']),
                confirmed_cash_state=deepcopy(self.runtime_actor.confirmed_cash_state),broker_snapshot=snapshot,quote=quote,session=session,
                metadata=self._metadata(row,transport_context),transport_context=transport_context,
                execution_ledger_rows=ledger,completed_close_intents=self._completed_close_evidence(row),open_risk_proof=proof,
                actual_fill_lifecycle=self._actual_fill_lifecycle(row,transport_context),
                durable_state_sha256=self.runtime_actor.export_state()['state_sha256'],cash_source_blocker=self.cash_source_blocker)

    def publication_inputs_provider(self,*,runtime_actor,bundle,data,now,transport_context):
        with self.actor_lock:
            _require(runtime_actor is self.runtime_actor,'weekly19_bridge_actor_replacement_forbidden')
            _require(data['receipt']==self.data['receipt'],'weekly19_bridge_market_generation_changed_requires_new_owner')
            snapshot=self._snapshot(transport_context);account=_envelope(snapshot['account']);day=account['trading_day']
            quotes={}
            for life in self.runtime_actor.close_lifecycles.values():
                if life['status']=='retry_required':
                    row=self.runtime_actor.engine.order_intents[life['order_ids'][-1]]
                    try:quotes[life['symbol']]=self._quote_session(row,transport_context,snapshot)[0]
                    except ValueError:pass
            def reconcile(section):
                self._replay_deferred(section)
                cash=self._cash(snapshot);self._reconcile_actual_source(snapshot,cash,quote_snapshot=quotes)
                if section['deferred'] or self.cash_source_blocker:return
                # At most one new source-bound admission per producer cycle;
                # all existing pending intents are still returned below.
                for admission,context in self.runtime_actor.admission_contexts.items():
                    if context['execution_day']!=day or self.runtime_actor.last_processed_day>=day:continue
                    has_transfer=cash['confirmed_topup_fen']>context['confirmed_topup_fen']
                    related=[plan for plan in self.runtime_actor.engine.order_intents.values()
                             if plan.get('original_funding_admission_id')==admission and plan['offset']=='open']
                    # Ordinary Friday-approved plans keep their original cap.
                    # Only funds-wait/zero-plan admission or real T is replanned.
                    if not has_transfer and related and self.signal_origin_equity_fen>=15000000:continue
                    if admission in self.runtime_actor.funding_replans:continue
                    if not has_transfer and funds._money(account['Balance'])<15000000:continue
                    try:
                        funds.assert_open_funding_ready(cash,snapshot['account'],self.now())
                        symbol=context['vt_symbol'];row=dict(vt_symbol=symbol,offset='open',physical_epoch_id=self.runtime_actor.epoch_lookup[(symbol,str(context['bar'].datetime)[:10])])
                        quote=self._quote_session(row,transport_context,snapshot)[0]
                        result=self.runtime_actor.replan_after_confirmed_funding(dict(admitted_entry_id=admission),snapshot,cash,quote)
                        if result.get('replanned'):break
                    except funds.FundingError as exc:
                        if str(exc) not in CASH_WAIT:raise
                    except RuntimeContractError as exc:
                        if str(exc) not in {'funding_replan_requires_flat_reconciled_position','cannot_enlarge_filled_or_broker_bound_plan','funded_signal_expired_or_receipt_missing'}:raise
                    except ValueError as exc:
                        if not str(exc).startswith('weekly19_quote_'):raise
            _,committed=self._commit(reconcile)
            section=self._section(committed)
            _require(not section['deferred'],'weekly19_durable_broker_events_awaiting_replay')
            path,cursor=self._journal()
            intents=[]
            for oid,plan in self.runtime_actor.engine.order_intents.items():
                if oid in self.runtime_actor.engine.order_terminal:continue
                item=deepcopy(plan);item.update(requires_funding_revision=self.runtime_actor.confirmed_cash_state['revision'],
                    broker_account_raw_sha256=snapshot['account']['raw_sha256'],
                    confirmed_funding_state_sha256=funds._hash(self.runtime_actor.confirmed_cash_state),
                    funding_receipt_set_sha256=funds._hash(self.runtime_actor.confirmed_cash_state['receipts']),
                    execution_profile=PROFILE.profile_key,official_live_version=PROFILE.official_version,
                    capital=PROFILE.capital,capital_label=PROFILE.capital_label,ruleset_version=PROFILE.ruleset_version)
                if item.get('depends_on_close_intent_id'):
                    dependency=next((p for p in self.runtime_actor.engine.order_intents.values() if p['intent_id']==item['depends_on_close_intent_id']),None)
                    _require(dependency is not None,'weekly19_bridge_roll_close_dependency_missing')
                    item['rollover_from_vt_symbol']=dependency['vt_symbol']
                intents.append(item)
            decision=deepcopy(committed['decision'])
            _require(isinstance(decision,dict),'weekly19_completed_decision_missing')
            decision.update(intents=intents,confirmed_cash_state=deepcopy(self.runtime_actor.confirmed_cash_state),
                current_runtime_state_sha256=committed['runtime']['state_sha256'])
            result=dict(decision=decision,journal_segment_path=path,durable_through=cursor)
            rollover=self.native.publication_rollover()
            if rollover is not None:result['feed_rollover_evidence']=rollover
            return result

    def native_capture_factory(self,*,transport_context):
        self._assert_authority()
        _require(self.native is None or self.native.closed,'weekly19_bridge_native_owner_already_installed')
        native=_NativeSession.__new__(_NativeSession)
        try:native.__init__(self,transport_context)
        except BaseException:
            native.abort_unadmitted_startup()
            raise
        self.native=native
        return self.native

    def close(self):
        if self.native is not None:self.native.close()

class _CTPIngress:
    def __init__(self,pipeline):self.pipeline=pipeline
    def capture_ingress(self,tick):
        if getattr(tick,'gateway_name',None)=='CTP':return self.pipeline.capture_ingress(tick)
    def __getattr__(self,name):return getattr(self.pipeline,name)

class _NativeSession:
    def __init__(self,owner,transport):
        self.owner=owner;self.transport=transport;self.lock=RLock();self.collector=None;self.sequence=0;self.closed=False
        self.identity=dict(account_key=owner.runtime_actor.account,material_release_id=owner.runtime_actor.release,execution_profile=PROFILE.profile_key)
        self.connection=transport['connection_generation'];self.service=transport['service_generation']
        previous=owner._section(owner.store.read()).get('md_sessions',[])
        if previous:
            prior=self._checked_md_checkpoint(previous[-1])
            _require(prior['state']=='closed' and prior['md_clean_shutdown'] is True,'weekly19_bridge_previous_md_not_clean')
        self.root=_private_directory(owner.private_root/('session-'+uuid.uuid4().hex));self.buffers=[];self.subscribed=set()
        for name in ('main_engine','event_engine','gateway','td_api'):_require(transport.get(name) is not None,'weekly19_bridge_same_transport_missing:'+name)
        self.feed='weekly19-'+uuid.uuid4().hex
        _write_private(self.root/'feed.json',funds._canonical(dict(self.identity,feed_session_id=self.feed,connection_generation=self.connection,service_generation=self.service)))
        self.tick_pipeline=TickStreamPipeline(feed_session_id=self.feed,journal_segment_path=self.root/'md.journal',clock=owner.clock,max_buffer_ticks=10000)
        self.tick_pipeline.start();_require(self.tick_pipeline.wait_until_journal_ready(timeout_seconds=2),'weekly19_bridge_md_header_not_durable')
        self.restore_tick=install_gateway_tick_ingress(transport['gateway'],_CTPIngress(self.tick_pipeline))
        transport['event_engine'].register(EVENT_TICK,self._tick_event)
        body,reference=self._md_heartbeat('running')
        def remember(section):
            section.setdefault('md_sessions',[]).append(dict(feed_session_id=self.feed,journal_segment_path=str(self.tick_pipeline.journal_segment_path),heartbeat_reference=reference))
        owner._commit(remember)

    def abort_unadmitted_startup(self):
        # Construction happens before gateway.connect. Never leave a writer or
        # ingress hook alive if the initial durable owner transaction failed.
        restore=getattr(self,'restore_tick',None)
        if callable(restore):restore()
        pipeline=getattr(self,'tick_pipeline',None)
        if pipeline is not None:
            try:self.transport['event_engine'].unregister(EVENT_TICK,self._tick_event)
            except (KeyError,ValueError):pass
            pipeline.shutdown(timeout_seconds=5)
        self.closed=True

    def _md_sessions(self):
        return self.owner._section(self.owner.store.read()).get('md_sessions',[])

    def _md_heartbeat(self,state,*,clean=False):
        snapshot=self.tick_pipeline.durable_snapshot()
        cursor=(DurableTickCursor(snapshot.feed_session_id,snapshot.durable_ingress_sequence,
            snapshot.durable_journal_byte_offset,snapshot.journal_schema) if snapshot.durable_ingress_sequence else None)
        from dataclasses import asdict
        revision=str(uuid.uuid4())
        body=dict(schema='weekly19.md-owner-heartbeat.v1',revision_uuid=revision,feed_session_id=self.feed,
            journal_segment_path=str(snapshot.journal_segment_path),connection_generation=self.connection,
            service_generation=self.service,state=state,md_clean_shutdown=clean,
            durable_cursor=None if cursor is None else asdict(cursor),observed_at=self.owner.now().isoformat(),
            dropped_tick_count=snapshot.dropped_tick_count,gap_present=snapshot.gap is not None,
            writer_fault_present=snapshot.writer_fault is not None,production_qualified=False)
        reference=_write_private(self.root/('heartbeat-'+revision+'.json'),funds._canonical(body))
        reference['revision_uuid']=revision
        self.heartbeat=reference
        return body,reference

    def _checked_md_checkpoint(self,checkpoint):
        ref=checkpoint['heartbeat_reference'];raw=_read_private(ref['path'])
        _require(_sha(raw)==ref['sha256'],'weekly19_bridge_md_heartbeat_changed')
        body=json.loads(raw,object_pairs_hook=unique)
        _require(body['feed_session_id']==checkpoint['feed_session_id'] and body['revision_uuid']==ref['revision_uuid']
            and body['journal_segment_path']==checkpoint['journal_segment_path'],'weekly19_bridge_md_checkpoint_identity_mismatch')
        return body

    def _rollover_evidence(self,previous_cursor):
        from qmt_roll_official_live_intent_spool import DetectorFeedRolloverEvidence
        sessions=self._md_sessions();old_index=next((i for i,row in enumerate(sessions) if row['feed_session_id']==previous_cursor.feed_session_id),None)
        _require(old_index is not None,'weekly19_bridge_previous_md_source_missing')
        old=sessions[old_index];body=self._checked_md_checkpoint(old)
        _require(body['state']=='closed' and body['md_clean_shutdown'] is True and not body['gap_present']
            and not body['writer_fault_present'] and body['dropped_tick_count']==0,'weekly19_bridge_previous_md_not_clean')
        from dataclasses import asdict
        _require(body['durable_cursor']==asdict(previous_cursor),'weekly19_bridge_previous_md_cursor_not_caught_up')
        empty=[]
        for other in sessions[old_index+1:]:
            if other['feed_session_id']==self.feed:continue
            check=self._checked_md_checkpoint(other)
            _require(check['state']=='closed' and check['md_clean_shutdown'] is True and check['durable_cursor'] is None,
                'weekly19_bridge_unacknowledged_md_feed_between_sessions')
            empty.append(other['feed_session_id'])
        return DetectorFeedRolloverEvidence(previous_cursor=previous_cursor,
            previous_journal_segment_path=old['journal_segment_path'],previous_heartbeat_revision_uuid=body['revision_uuid'],
            previous_clean_shutdown=True,recovery_previous_durable_cursor=previous_cursor,prior_uncommitted_gap_count=0,
            new_feed_session_id=self.feed,new_journal_segment_path=str(self.tick_pipeline.journal_segment_path),
            new_heartbeat_revision_uuid=self.heartbeat['revision_uuid'],bridged_empty_feed_sessions=tuple(empty))

    def publication_rollover(self):
        if self.owner.service is None:return None
        from qmt_roll_official_live_intent_spool import open_spool,read_detector_cursor
        connection=open_spool(self.owner.service.spool_path)
        try:previous=read_detector_cursor(connection,consumer_id='weekly19')
        finally:connection.close()
        self._md_heartbeat('running')
        if previous is None or previous.feed_session_id==self.feed:return None
        return self._rollover_evidence(previous)

    def _commit_md_tail(self,cursor):
        """Read every committed old MD row before an empty detector acknowledgement.

        Weekly alpha is completed-bar based. This acknowledges consumed quotes,
        creates no intent, and cannot backfill a historical opening signal.
        """
        if self.owner.service is None or cursor is None:return
        from qmt_roll_official_live_tick_reader import TickStreamJournalReader
        reader=TickStreamJournalReader(self.tick_pipeline.journal_segment_path);walk=None
        while True:
            batch=reader.read_after(walk,durable_through=cursor,limit=4096)
            _require(batch.gap is None,'weekly19_bridge_md_tail_gap')
            if batch.caught_up:break
            _require(batch.next_cursor is not None and batch.next_cursor!=walk,'weekly19_bridge_md_tail_no_progress');walk=batch.next_cursor
        from qmt_roll_official_live_intent_spool import open_spool,read_detector_cursor
        from qmt_roll_official_live_intent_spool import commit_detector_batch
        connection=open_spool(self.owner.service.spool_path)
        try:
            previous=read_detector_cursor(connection,consumer_id='weekly19')
            if previous==cursor:return
            rollover=None if previous is None or previous.feed_session_id==self.feed else self._rollover_evidence(previous)
            commit_detector_batch(connection,consumer_id='weekly19',expected_cursor=previous,next_cursor=cursor,intents=[],
                now_epoch_ns=self.owner.clock.epoch_ns(),now_monotonic_ns=self.owner.clock.monotonic_ns(),
                clock_domain_id=self.owner.clock.clock_domain_id(),feed_rollover_evidence=rollover)
        finally:connection.close()

    def _tick_event(self,event):
        if getattr(event.data,'gateway_name',None)=='CTP':self.tick_pipeline.observe_handler(event.data)

    def _ledger_snapshot(self):
        for _ in range(3):
            typed=self.owner._typed_ledger();raw=_read_private(self.owner.ledger_path)
            if _sha(raw)==typed._source['raw_sha256']:
                path=self.root/('ledger-'+_sha(raw)+'.jsonl')
                if not path.exists():_write_private(path,raw)
                return dict(path=str(path),sha256=_sha(raw))
        raise SessionBridgeError('weekly19_bridge_ledger_changed_during_capture')

    def capture_native(self,method,native,*,observed_at):
        with self.lock:
            _require(not self.closed,'weekly19_bridge_native_session_closed')
            _require(method in ('onRtnOrder','onRtnTrade') and type(native) is dict,'weekly19_bridge_native_dictionary_required')
            self.sequence+=1
            try:ledger_ref=self._ledger_snapshot();ledger_blocker=None
            except (OSError,broker.BrokerEvidenceError,SessionBridgeError) as exc:
                ledger_ref=None;ledger_blocker=type(exc).__name__+':'+str(exc)
            if self.collector is None or ledger_ref is None:
                body=dict(schema='weekly19.startup-native-buffer.v1',native=deepcopy(native),source_callback=method,
                    observed_at=funds._time(observed_at).isoformat(),connection_generation=self.connection,service_generation=self.service,
                    native_sha256=funds._hash(native),ledger_snapshot=ledger_ref,ledger_source_blocker=ledger_blocker,production_qualified=False)
                reference=_write_private(self.root/f'startup-{self.sequence:012d}.json',funds._canonical(body));self.buffers.append(reference)
                reference.update(schema=body['schema'],admission_state='buffered')
            else:
                self.collector.bind_execution_ledger_rows(self.owner._typed_ledger(ledger_ref['path']))
                event=self.collector.record(method,native,connection_generation=self.connection,observed_at=observed_at)
                reference=self._persist_native(after_sequence=event['sequence']-1)
            return dict(native=deepcopy(native),source_callback=method,native_sha256=funds._hash(native),capture_reference=reference,
                connection_generation=self.connection,service_generation=self.service)

    def _persist_native(self,*,after_sequence):
        path=self.root/('native-'+uuid.uuid4().hex+'.json')
        policy=self.owner._policy()
        kwargs=dict(now=self.owner.now(),after_sequence=after_sequence,capture_authority_registry=policy.get('capture_authority_registry'))
        if policy.get('capture_authority_capability') is not None:kwargs['capture_authority_capability']=policy['capture_authority_capability']
        return broker.persist_native_broker_capture(path,self.collector,**kwargs)

    def _subscribe(self,transport,snapshot):
        actor=self.owner.runtime_actor;target=self.owner.data['receipt']['trading_date']
        symbols=set(actor.metadata['daily_mapping'][target].values())
        symbols|={p['vt_symbol'] for p in _envelope(snapshot['positions'])['positions'] if p['volume']}
        symbols|={p['vt_symbol'] for oid,p in actor.engine.order_intents.items() if oid not in actor.engine.order_terminal}
        main=transport['main_engine']
        for symbol in sorted(symbols-self.subscribed):
            contract=main.get_contract(symbol)
            _require(contract is not None and contract.vt_symbol==symbol and contract.gateway_name=='CTP','weekly19_bridge_subscription_contract_not_ready:'+symbol)
            code,exchange=symbol.split('.');main.subscribe(SubscribeRequest(code,Exchange(exchange)),'CTP');self.subscribed.add(symbol)

    def _admit(self,*,transport_context):
        owner=self.owner
        with owner.actor_lock,self.lock:
            _require(transport_context['connection_generation']==self.connection and transport_context['service_generation']==self.service,'weekly19_bridge_connection_changed')
            policy=owner._policy();path=self.root/('warm-'+uuid.uuid4().hex+'.json')
            reference=warm.persist_warm_native_query_capture(path,transport_context,**policy)
            transport_context['weekly19_warm_capture_reference']=reference
            transport_context['rows']['_weekly19_warm_capture_reference']=deepcopy(reference)
            snapshot=owner._snapshot(transport_context);ledger=owner._typed_ledger()
            events=warm.load_warm_broker_events(transport_context,ledger,**policy)
            _,bundle=owner._consume_batch(events,dict(kind='warm_epoch_snapshot',capture_reference=reference))
            def reconcile(section):
                cash=owner._cash(snapshot)
                try:owner.runtime_actor.reconcile_broker_snapshot(snapshot,cash)
                except RuntimeContractError as exc:
                    if str(exc)!='broker_strategy_position_mismatch' or not section['deferred']:raise
                    section['pending_position_reconciliation']=dict(source_sha256=snapshot['native_source_sha256'],reason=str(exc))
                else:section.pop('pending_position_reconciliation',None)
            _,bundle=owner._commit(reconcile)
            if self.collector is None:
                self.collector=broker.NativeBrokerCallbackCollector(snapshot['account'],connection_generation=self.connection,service_generation=self.service,execution_ledger_rows=ledger)
                for ref in self.buffers:
                    raw=_read_private(ref['path']);_require(_sha(raw)==ref['sha256'],'weekly19_bridge_startup_buffer_changed')
                    saved=json.loads(raw,object_pairs_hook=unique)
                    _require(saved['connection_generation']==self.connection and saved['service_generation']==self.service and funds._hash(saved['native'])==saved['native_sha256'],'weekly19_bridge_startup_identity_mismatch')
                    _require(isinstance(saved.get('ledger_snapshot'),dict),'weekly19_bridge_startup_ledger_snapshot_missing')
                    _require(_sha(_read_private(saved['ledger_snapshot']['path']))==saved['ledger_snapshot']['sha256'],'weekly19_bridge_startup_ledger_changed')
                    self.collector.bind_execution_ledger_rows(owner._typed_ledger(saved['ledger_snapshot']['path']))
                    self.collector.record(saved['source_callback'],saved['native'],connection_generation=self.connection,observed_at=funds._time(saved['observed_at']))
                self.collector.bind_execution_ledger_rows(ledger)
                if self.buffers:
                    native_ref=self._persist_native(after_sequence=0)
                    native_events=broker.load_native_broker_events(native_ref,ledger,**owner._policy())
                    _,bundle=owner._consume_batch(native_events,dict(kind='native_startup_recovery',capture_reference=native_ref))
            else:
                self.collector.account_envelope=deepcopy(snapshot['account']);self.collector.account=_envelope(snapshot['account'])
                self.collector.bind_execution_ledger_rows(ledger)
            self._subscribe(transport_context,snapshot)
            # Restore transient send barriers from the durable actual-event queue.
            from run_qmt_roll_stage931_official_live_ctp_submit_adapter import weekly19_reconcile_deferred_events
            for identity in owner._section(bundle)['deferred']:
                weekly19_reconcile_deferred_events(transport_context['rows'],owner._receipt(bundle,status='deferred_durable',deferred_id=identity))
            receipt=owner._receipt(bundle)
            receipt.update(source_qualified=snapshot['source_qualified'],warm_capture_reference=reference)
            return receipt

    def admit_completed_startup(self,*,transport_context):return self._admit(transport_context=transport_context)
    def admit_completed_query_bundle(self,*,transport_context):return self._admit(transport_context=transport_context)

    def close(self):
        with self.owner.actor_lock,self.lock:
            if self.closed:return
            self.closed=True;self.restore_tick();self.transport['event_engine'].unregister(EVENT_TICK,self._tick_event)
            report=self.tick_pipeline.shutdown(timeout_seconds=5)
            clean=report.drained and report.writer_fault is None and report.gap is None and report.uncommitted_tick_count==0
            self._md_heartbeat('closing')
            try:
                _require(clean,'weekly19_bridge_md_shutdown_not_durable')
                self._commit_md_tail(report.durable_through)
            except BaseException:
                body,reference=self._md_heartbeat('fault',clean=False)
                def failed(section):
                    for row in section['md_sessions']:
                        if row['feed_session_id']==self.feed:row['heartbeat_reference']=reference
                self.owner._commit(failed)
                raise
            body,reference=self._md_heartbeat('closed',clean=True)
            def remember(section):
                for row in section['md_sessions']:
                    if row['feed_session_id']==self.feed:row['heartbeat_reference']=reference
            self.owner._commit(remember)


def build_weekly19_session_service(args,*,runtime_actor,bundle,data,authority,state_store,clock,**bridge_kwargs):
    """Build, never start/connect. LocalBackend owns source and lifecycle policy."""
    from qmt_roll_weekly19_execution_service import Weekly19ExecutionService
    bridge=Weekly19SessionBridge(runtime_actor=runtime_actor,bundle=bundle,data=data,authority=authority,state_store=state_store,clock=clock,**bridge_kwargs)
    service=Weekly19ExecutionService(args,authority_provider=bridge.authority_provider,
        fresh_context_provider=bridge.fresh_context_provider,event_consumer=bridge.event_consumer,
        native_capture_factory=bridge.native_capture_factory,publication_inputs_provider=bridge.publication_inputs_provider,clock=clock)
    bridge.bind_service(service)
    return service,bridge
