"""Stage014 original-method runtime adapter; an offline intent producer only.

No CTP, order submission, data downloads, bank transfer or synthetic fills.
Broker account equity is authoritative. All output is production_qualified=False;
source hashes prove byte identity, not authenticity of a broker capture provider.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from contextlib import contextmanager
from dataclasses import is_dataclass
from datetime import datetime, date
from enum import Enum
import hashlib
import base64
import zlib
import importlib
import json
import math
from pathlib import Path
import threading
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from vnpy.trader.constant import Direction, Exchange, Interval, Offset, Status, OrderType
from vnpy.trader.object import BarData, OrderData, TradeData
from vnpy.trader.utility import ArrayManager
import qmt_roll_weekly19_funding as funding

HERE = Path(__file__).resolve().parent
ASSETS = HERE / 'weekly19_assets'
DEFAULT_SETTINGS_ASSET = ASSETS / 'actual_settings.json'
FROZEN_MANIFEST_SHA256 = 'b473e88f21d2d139615e638c9df0e0fac5358596d919624f55411438926a303c'
_CONSTRUCTOR_LOCK = threading.RLock()
SHANGHAI = ZoneInfo('Asia/Shanghai')


class RuntimeContractError(ValueError):
    """Deterministic fail-closed runtime boundary violation."""


def _fail(reason):
    raise RuntimeContractError(reason)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _hash(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _state_digest(body):
    # Cached after_state_sha256 is a derived pointer to this digest. Exclude only
    # that annotation to avoid a cryptographic self-reference; all decision
    # inputs, quantities, identities and other state remain covered.
    def clean(value):
        if isinstance(value, list):
            return [clean(v) for v in value]
        if isinstance(value, dict):
            if value.get('@') in ('dict','defaultdict'):
                return dict(value, value=[[k, None if k=='after_state_sha256' else clean(v)]
                                          for k,v in value['value']])
            return {k:(None if k=='after_state_sha256' else clean(v)) for k,v in value.items()}
        return value
    return _hash(clean(body))


def _filehash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_frozen_sources():
    path = ASSETS / 'source_manifest.json'
    if _filehash(path) != FROZEN_MANIFEST_SHA256:
        _fail('frozen_manifest_hash_mismatch')
    manifest = json.loads(path.read_text())
    for name,digest in manifest.get('package_files',{}).items():
        if _filehash(HERE/'weekly19_frozen'/name)!=digest:
            _fail('frozen_package_hash_mismatch:'+name)
    for name, row in manifest['files'].items():
        if _filehash(HERE / 'weekly19_frozen' / name) != row['copy_sha256']:
            _fail('frozen_source_hash_mismatch:' + name)
    for name, row in manifest['external_sources'].items():
        if _filehash(HERE / (name + '.py')) != row['sha256']:
            _fail('external_source_hash_mismatch:' + name)
    for module, row in manifest.get('external_module_sources', {}).items():
        spec = importlib.util.find_spec(module)
        if spec is None or _filehash(spec.origin) != row['sha256']:
            _fail('external_module_hash_mismatch:' + module)
    return manifest


def _classes():
    # Integrity verification precedes importing decision source. No old live config.
    verify_frozen_sources()
    package = importlib.import_module('weekly19_frozen.qmt_roll_portfolio_strategy')
    return package


def _encode(value, *, shared=None):
    """Tagged JSON, no pickle/code execution. Unknown state is never dropped."""
    enc = lambda obj: _encode(obj, shared=shared)
    if shared is not None and value is shared['weeks']:
        return {'@':'sharedref','name':'weeks','sha256':shared['weeks_sha256']}
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, Enum):
        return {'@': 'enum', 'class': type(value).__name__, 'value': value.value}
    if isinstance(value, (float, np.floating)):
        n = float(value)
        return n if math.isfinite(n) else {'@': 'float', 'value': 'nan' if math.isnan(n) else 'inf' if n > 0 else '-inf'}
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return {'@': type(value).__name__, 'value': value.isoformat()}
    if isinstance(value, np.ndarray):
        return {'@': 'ndarray', 'dtype': str(value.dtype), 'value': enc(value.tolist())}
    if isinstance(value, pd.DataFrame):
        return {'@': 'DataFrame', 'value': enc(value.to_dict('split')), 'dtypes': [str(x) for x in value.dtypes]}
    if isinstance(value, dict):
        return {'@': 'defaultdict' if isinstance(value, defaultdict) else 'dict',
                'value': [[enc(k), enc(v)] for k, v in sorted(value.items(),key=lambda item:_json(enc(item[0])))]}
    if isinstance(value, (list, tuple, set)):
        rows = sorted(value, key=repr) if isinstance(value, set) else value
        return {'@': type(value).__name__, 'value': [enc(v) for v in rows]}
    allowed = {'ProductState', 'PositionLayer', 'ArrayManager', 'ThreeMaWeeklyArrayManager',
               'WeeklyArrayManager', 'BarData', 'OrderData', 'TradeData'}
    if type(value).__name__ in allowed:
        return {'@': 'object', 'class': type(value).__name__, 'value': enc(vars(value))}
    _fail('unsupported_durable_state_type:' + type(value).__name__)


def _decode(value, *, shared=None):
    dec = lambda obj: _decode(obj, shared=shared)
    if not isinstance(value, dict) or '@' not in value:
        return value
    tag = value['@']
    if tag == 'sharedref':
        if (set(value)!={'@','name','sha256'} or value.get('name')!='weeks' or shared is None
                or value.get('sha256')!=shared['weeks_sha256']):
            _fail('shared_calendar_reference_invalid')
        return shared['weeks']
    if tag == 'zjson':
        return dec(_unpack_section(value))
    if tag in ('dict', 'defaultdict'):

        out = defaultdict(int) if tag == 'defaultdict' else {}
        out.update((dec(k), dec(v)) for k, v in value['value'])
        return out
    if tag in ('list', 'tuple', 'set'):
        return {'list': list, 'tuple': tuple, 'set': set}[tag](dec(v) for v in value['value'])
    if tag == 'float':
        return {'nan': float('nan'), 'inf': float('inf'), '-inf': -float('inf')}[value['value']]
    if tag in ('Timestamp', 'datetime', 'date'):
        return {'Timestamp': pd.Timestamp, 'datetime': datetime.fromisoformat, 'date': date.fromisoformat}[tag](value['value'])
    if tag == 'enum':
        types = {x.__name__: x for x in (Direction, Exchange, Interval, Offset, Status, OrderType)}
        return types[value['class']](value['value'])
    if tag == 'ndarray':
        return np.array(dec(value['value']), dtype=value['dtype'])
    if tag == 'DataFrame':
        frame = pd.DataFrame(**dec(value['value']))
        for column, dtype in zip(frame.columns, value['dtypes']):
            frame[column] = frame[column].astype(dtype)
        return frame
    if tag == 'object':
        from weekly19_frozen.qmt_roll_portfolio_strategy import ProductState, PositionLayer
        from weekly19_frozen.stage008_three_ma import ThreeMaWeeklyArrayManager
        from weekly19_frozen.weekly_adapter import WeeklyArrayManager
        types = {x.__name__: x for x in (ProductState, PositionLayer, ArrayManager, ThreeMaWeeklyArrayManager,
                                         WeeklyArrayManager, BarData, OrderData, TradeData)}
        if value['class'] not in types:
            _fail('unknown_durable_class')
        obj = types[value['class']].__new__(types[value['class']])
        obj.__dict__.update(dec(value['value']))
        return obj
    _fail('unknown_durable_tag')


def _pack_section(value):
    raw=_json(value).encode()
    if len(raw)<8192:
        return value
    return {'@':'zjson','encoding':'zlib-base64-v1','raw_bytes':len(raw),
            'raw_sha256':hashlib.sha256(raw).hexdigest(),
            'value':base64.b64encode(zlib.compress(raw,6)).decode('ascii')}


def _unpack_section(value):
    if (set(value)!={'@','encoding','raw_bytes','raw_sha256','value'} or
            value.get('encoding')!='zlib-base64-v1' or type(value.get('raw_bytes')) is not int
            or not 0<=value['raw_bytes']<=128*1024*1024 or not isinstance(value.get('value'),str)
            or len(value['value'])>64*1024*1024):
        _fail('compressed_state_bounds_invalid')
    try:
        packed=base64.b64decode(value['value'],validate=True)
        decoder=zlib.decompressobj()
        raw=decoder.decompress(packed,value['raw_bytes']+1)
        if (len(raw)!=value['raw_bytes'] or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail
                or hashlib.sha256(raw).hexdigest()!=value['raw_sha256']):
            _fail('compressed_state_digest_or_size_invalid')
        return json.loads(raw)
    except (ValueError,zlib.error) as exc:
        _fail('compressed_state_invalid:'+type(exc).__name__)


class IntentEngine:
    """StrategyTemplate facade. send/cancel collect plans and never call APIs."""
    def __init__(self, runtime, metadata):
        self.runtime = runtime
        self.sizes = metadata['sizes']
        self.priceticks = metadata['priceticks']
        self.rates = metadata.get('rates', {})
        self.slippages = metadata.get('slippages', {})
        self.bars = {}
        self.datetime = None
        self.intents = []
        self.order_intents = {}
        self.order_filled = {}
        self.order_terminal = {}
        self.sequence = 0
        self.intraday_execution_failure = ''

    def get_size(self, strategy, symbol):
        return self.sizes[symbol]

    def get_pricetick(self, strategy, symbol):
        return self.priceticks[symbol]

    def write_log(self, message, strategy=None):
        pass

    def put_strategy_event(self, strategy):
        pass

    def send_order(self, strategy, symbol, direction, offset, price, volume, lock=False, net=False):
        rt = self.runtime
        self.sequence += 1
        signal_day = pd.Timestamp(self.datetime).strftime('%Y-%m-%d')
        future = [d for d in rt.calendar if d > signal_day]
        if not future:
            _fail('next_session_calendar_missing')
        day = future[0]
        reason = next((str(x.get('reason', '')) for x in reversed(strategy.trade_event_diagnostics)
                       if x.get('contract_vt_symbol') == symbol or x.get('vt_symbol') == symbol), '')
        opening_context=rt.sizing_contexts.get((symbol,direction.name.lower()),{}).get('entry_context')
        kind = ('rollover_reopen' if opening_context=='rollover_reopen' else 'native_entry') if offset == Offset.OPEN else ('rollover_close' if reason == 'rollover_close' else 'risk_close')
        epoch = rt.epoch_lookup.get((symbol, signal_day))
        if not epoch:
            _fail('intent_physical_epoch_missing')
        identity = rt._position_identity(symbol,kind,signal_day)
        body = dict(material_release_id=rt.release, account_fingerprint=rt.account,
            target_date=signal_day, completed_target_date=signal_day,next_execution_day=day,
            position_epoch_id=identity['position_epoch_id'],root_position_id=identity['root_position_id'],
            position_cycle_id=identity['position_cycle_id'],intent_role='weekly19_'+kind,
            state_generation=f"{identity['position_epoch_id']}:{rt.revision+1}",
            trading_date=day, vt_symbol=symbol, direction=direction.name.lower(), offset=offset.name.lower(),
            planned_volume=int(volume), volume=int(volume), limit_price=float(price), price=float(price),
            physical_epoch_id=epoch, source='weekly19_pending_order' if offset == Offset.OPEN else 'weekly19_risk_reduce',
            intent_kind=kind, signal_datetime=signal_day + 'T00:00:00', sequence=self.sequence,
            data_receipt_sha256=rt.current_receipt_hash,
            protection_timing='fresh_completed_week_close',
            completed_week_end=rt._latest_week(symbol),
            requires_funding_revision=rt.confirmed_cash_state['revision'],
            broker_account_raw_sha256=rt.broker_snapshot['account']['raw_sha256'],
            confirmed_funding_state_sha256=_hash(rt.confirmed_cash_state),
            funding_receipt_set_sha256=_hash(rt.confirmed_cash_state['receipts']),
            original_funding_admission_id=rt.sizing_contexts.get((symbol,direction.name.lower()),{}).get('original_funding_admission_id'),
            production_qualified=False)
        iid = _hash(body)
        order_id = 'W19.' + iid
        body.update(intent_id=iid, signal_order_id=order_id)
        body['signal_identity'] = dict(intent_id=iid, signal_order_id=order_id,
            signal_datetime=body['signal_datetime'], trading_date=day)
        body['executable'] = rt._open_ready() if offset == Offset.OPEN else True
        body['blocked_reason'] = rt.open_block_reason if offset == Offset.OPEN and not body['executable'] else ''
        if kind == 'rollover_reopen':
            dependency = next((x['intent_id'] for x in reversed(self.intents) if x.get('intent_kind') == 'rollover_close' and rt.metadata['source_symbol_by_contract'].get(x.get('vt_symbol'))==rt.metadata['source_symbol_by_contract'][symbol]), None)
            if dependency is None:
                _fail('rollover_close_dependency_missing')
            body['depends_on_close_intent_id'] = dependency
        self.intents.append(body)
        self.order_intents[order_id] = deepcopy(body)
        self.order_filled[order_id] = 0
        if offset == Offset.CLOSE:
            rt._attach_close_intent(order_id)
            body['close_lifecycle_id'] = self.order_intents[order_id]['close_lifecycle_id']
        else:
            rt.open_contexts[iid] = deepcopy(rt.sizing_contexts.get((symbol, direction.name.lower()), {}))
        code, exchange = symbol.split('.')
        order = OrderData(symbol=code, exchange=Exchange(exchange), orderid=iid, direction=direction,
            offset=offset, price=float(price), volume=int(volume), datetime=self.datetime,
            gateway_name='W19', status=Status.SUBMITTING)
        strategy.update_order(order)
        return [order_id]

    def cancel_order(self, strategy, order_id):
        # A cancel intent is not an exchange acknowledgement or a fill.
        if order_id in self.order_intents and order_id not in self.order_terminal:
            self.intents.append(dict(intent_id=_hash(['cancel', order_id, self.sequence]), action='cancel',
                signal_order_id=order_id, source='weekly19_risk_reduce', executable=False,
                blocked_reason='cancel_requires_execution_adapter', production_qualified=False))


def _live_boundary(base):
    class ConfirmedBrokerBoundaryStrategy(base):
        def _estimate_equity(self, bars):
            return self._weekly19_runtime.broker_equity

        def _trade_to_close_pnl(self, trade):
            # Broker Balance already contains actual variation margin/costs.
            return 0.0

        def _trade_cost(self, trade):
            # Original research model costs are not actual broker cash deductions.
            return 0.0

        def _sizing_equity_snapshot(self):
            result = super()._sizing_equity_snapshot()
            if self._weekly19_runtime.broker_equity <= 0:
                result = dict(result, sizing_equity=0.0, effective_sizing_equity_cap=0.0)
            return result

        def _calculate_entry_sizing(self, vt_symbol, direction, bar, history, signal_data,
                risk_mode_override=None, entry_context='flat_entry', apply_env_gate=True,
                active_positions_before=None, correlation_snapshot=None):
            rt = self._weekly19_runtime
            signal = str(signal_data.get('signal', ''))
            native = entry_context in {'flat_entry', 'reverse_entry'} and signal in ({'long_case1a', 'long_case2'} if direction == 'long' else {'short_case1a'})
            admitted = None
            if native and not rt.revalidating:
                stop, valid, context = self._weekly_initial_stop_qualification(vt_symbol, direction, bar)
                blocked_range = direction == 'short' and rt.range_history.snapshot(vt_symbol, str(bar.datetime)[:10], bar.close_price)['would_block']
                if valid and not blocked_range:
                    admitted = _hash([str(bar.datetime)[:10], vt_symbol, direction, signal, entry_context])
                    rt._admit(admitted, str(bar.datetime)[:10])
            result = super()._calculate_entry_sizing(vt_symbol, direction, bar, history, signal_data,
                risk_mode_override=risk_mode_override, entry_context=entry_context, apply_env_gate=apply_env_gate,
                active_positions_before=active_positions_before, correlation_snapshot=correlation_snapshot)
            # Preserve all parent's sizing gates, then add the real cash boundary.
            rt.sizing_contexts[(vt_symbol, direction)] = dict(vt_symbol=vt_symbol, direction=direction,
                bar=_decode(_encode(bar)), history=history.copy(), signal_data=deepcopy(signal_data),
                risk_mode_override=risk_mode_override, entry_context=entry_context, apply_env_gate=apply_env_gate,
                active_positions_before=active_positions_before, correlation_snapshot=deepcopy(correlation_snapshot))
            ctx = rt.sizing_contexts[(vt_symbol,direction)]
            day = pd.Timestamp(bar.datetime).strftime('%Y-%m-%d')
            ctx.update(execution_day=next(d for d in rt.calendar if d>day),
                history_sha256=_hash(_encode(history)),data_receipt_sha256=rt.current_receipt_hash,
                confirmed_topup_fen=rt.confirmed_cash_state['confirmed_topup_fen'])
            if admitted is not None:
                ctx['original_funding_admission_id'] = admitted
                rt.admission_contexts[admitted] = deepcopy(ctx)
            life=rt._pending_close()
            if entry_context=='rollover_reopen' and life is not None:
                saved=deepcopy(ctx)
                saved.update(close_lifecycle_id=life['lifecycle_id'],previous_volume=life['volume'],roll_status='waiting_close')
                rt.pending_rollovers[life['product']]=saved
            before = int(result['selected_volume'])
            margin = float(result.get('margin_per_contract', 0)) * float(self.stage830_broker_margin_multiplier)
            available = max(0.0, rt.broker_available - rt.pending_broker_margin)
            cap = max(0, int(available // margin)) if margin > 0 else 0
            after = min(before, cap) if rt._open_ready() else 0
            if after:
                rt.pending_broker_margin += margin * after
            return dict(result, selected_volume=after, weekly19_parent_selected_volume=before,
                        weekly19_cash_selected_volume=after, weekly19_funding_ready=not bool(rt.open_block_reason))

        def _queue_pending_close_lot(self, symbol, layer, exit_price, volume):
            rt = self._weekly19_runtime
            if rt.close_capture is not None:
                capture = rt.close_capture
                try:
                    index = capture['layer_ids'].index(id(layer))
                except ValueError:
                    _fail('close_layer_ownership_unproven')
                capture['lots'].append(dict(layer_index=index, volume=int(volume), remaining=int(volume),
                    entry_price=float(layer.entry_price), direction=layer.direction, realized_pnl=0.0))
            return super()._queue_pending_close_lot(symbol, layer, exit_price, volume)

        def _record_product_direction_outcome(self, product, direction, pnl):
            rt = self._weekly19_runtime
            if rt.close_capture is not None:
                return None
            return super()._record_product_direction_outcome(product, direction, pnl)

        def _update_streak_risk_state(self, pnl, product_vt_symbol=None, *, exit_reason=None, profit_giveback_context=False):
            rt = self._weekly19_runtime
            if rt.close_capture is not None:
                rt.close_capture['risk_events'].append(dict(product=product_vt_symbol,
                    exit_reason=exit_reason, profit_giveback_context=profit_giveback_context))
                return None
            return super()._update_streak_risk_state(pnl, product_vt_symbol,
                exit_reason=exit_reason, profit_giveback_context=profit_giveback_context)

        def _close_layers(self, state, indexes, exit_price, *, exit_reason=None, profit_giveback_context=False):
            rt = self._weekly19_runtime
            with rt._capture_close(state):
                return super()._close_layers(state, indexes, exit_price, exit_reason=exit_reason,
                    profit_giveback_context=profit_giveback_context)

        def _reduce_position_to_target(self, state, target_volume, exit_price):
            if target_volume >= state.active_volume():
                return None
            with self._weekly19_runtime._capture_close(state):
                return super()._reduce_position_to_target(state, target_volume, exit_price)

        def _sync_close_trade(self, trade):
            # Preserve original pending-lot/reason consumption, but realized PnL
            # is now committed from actual fill lots, never model price deltas.
            super()._sync_close_trade(trade)
            return 0.0

        def _reconcile_state_with_position(self, state, current_pos, bar):
            if current_pos and not state.layers:
                _fail('unprotected_broker_position')
            return super()._reconcile_state_with_position(state, current_pos, bar)
    return ConfirmedBrokerBoundaryStrategy


class Runtime:
    def __init__(self, settings_asset, metadata, session_calendar, physical_epoch_daily,
                 broker_snapshot, durable_state, confirmed_cash_state, *, clock=None, recovery_events=()):
        recovery_events=tuple(recovery_events)
        if recovery_events and durable_state is None:
            _fail('recovery_events_require_durable_state')
        self.clock = clock or (lambda: datetime.now(SHANGHAI))
        funding.validate_state(confirmed_cash_state)
        self.confirmed_cash_state = deepcopy(confirmed_cash_state)
        self.account = confirmed_cash_state['account_key']
        self.release = confirmed_cash_state['material_release_id']
        self.calendar = sorted(set(session_calendar))
        self.metadata = deepcopy(metadata)
        self.source_manifest = verify_frozen_sources()
        core = _classes()
        from weekly19_frozen.weekly_adapter import completed_weeks
        from weekly19_frozen.stage032_daily_addon import daily_addon_strategy_class
        from weekly19_frozen.stage005_short_bottom20 import RangeHistory, range_strategy_class
        from weekly19_frozen.stage022_historical_safety import historical_strategy_class
        from weekly19_frozen.base847 import QmtRollPortfolioStrategyStage847C9StopRetry
        frame = physical_epoch_daily.copy()
        self.range_history = RangeHistory(frame)
        # The original RangeHistory intentionally retains only close/range fields.
        # Keep the complete immutable admitted row for the execution boundary.
        self.approved_bar_lookup=frame.assign(date=frame.date.astype(str)).set_index(['vt_symbol','date'],verify_integrity=True)
        self.epoch_lookup = {(str(r.vt_symbol), str(r.date)):str(r.contract_epoch_id) for r in frame.itertuples()}
        self.input_hash = _hash(dict(calendar=self.calendar, metadata=_encode(self.metadata), physical=_encode(frame)))
        asset_path = Path(settings_asset)
        if _filehash(asset_path) != self.source_manifest['settings_asset_sha256']:
            _fail('fixed_settings_hash_mismatch')
        asset = json.loads(asset_path.read_text())
        if asset['schema'] != 'weekly19.fixed-settings.v1' or asset['production_qualified'] is not False:
            _fail('fixed_settings_asset_invalid')
        for name, row in asset['assets'].items():
            if _filehash(asset_path.parent / name) != row['sha256']:
                _fail('fixed_asset_hash_mismatch:' + name)
        settings = deepcopy(asset['settings'])
        self.settings_sha256 = _filehash(asset_path)
        self.settings_asset_path = asset_path
        self.physical_frame = frame.copy()
        self._input_prefix_cache = {}
        for key, value in list(settings.items()):
            if isinstance(value, str) and value.startswith('@ASSET/'):
                settings[key] = str(asset_path.parent / value.split('/', 1)[1])
            elif isinstance(value, str) and value.startswith(('@EMPTY/', '@DISABLED/')):
                settings[key] = str(asset_path.parent / 'never_read' / value.split('/', 1)[1])
        if (asset_path.parent / 'never_read').exists():
            _fail('disabled_or_empty_asset_path_exists')
        settings['trade_start_date'] = confirmed_cash_state['cold_start_date']
        self.fixed_settings=deepcopy(settings)
        if set(metadata['product_symbols']) != set(pd.read_csv(asset_path.parent / 'static19.csv').product_vt_symbol.astype(str)):
            _fail('fixed19_product_universe_mismatch')
        self.weeks = completed_weeks(self.calendar)
        base = daily_addon_strategy_class(QmtRollPortfolioStrategyStage847C9StopRetry, self.weeks,
                                          self.calendar, self.epoch_lookup, enabled=False)
        cls = _live_boundary(historical_strategy_class(range_strategy_class(base, self.range_history, True),
                                                      confirmed_cash_state['cold_start_date']))
        self.engine = IntentEngine(self, metadata)
        self.broker_equity = 0.0
        self.broker_available = 0.0
        self.open_block_reason = ''
        self.pending_broker_margin = 0.0
        self.admitted_ids = []
        self.funding_recommendation = None
        self.last_processed_day = ''
        self.warmup_cursor = ''
        self.current_receipt_hash = ''
        self.days = {}
        self.fills = {}
        self.order_updates = {}
        self.close_capture = None
        self.close_lifecycles = {}
        self.queued_days = []
        self.open_contexts = {}
        self.sizing_contexts = {}
        self.pending_rollovers = {}
        self.admission_contexts = {}
        self.position_identities = {}
        self.broker_order_bindings = {}
        self.child_batches = {}
        self.revision = 0
        self.revalidating = False
        self.physical_epoch_state = {}
        self.physical_epoch_transitions = []
        self.expired_signal_days = []
        self.funding_replans = {}
        # Only the frozen constructor sees these functions, under a lock. The
        # constructor's original method stays byte/AST-identical; no filesystem
        # market/default metadata or old config is read through this bridge.
        with _CONSTRUCTOR_LOCK:
            old = (core.build_daily_mapping, core.build_contract_metadata)
            core.build_daily_mapping = lambda *a, **kw: deepcopy(metadata['daily_mapping'])
            core.build_contract_metadata = lambda *a, **kw: deepcopy(metadata)
            try:
                self.strategy = cls(self.engine, 'weekly19-original-stage014', metadata['vt_symbols'], settings)
            finally:
                core.build_daily_mapping, core.build_contract_metadata = old
        self.strategy._weekly19_runtime = self
        self.strategy.inited = True
        self.strategy.trading = True
        if durable_state is not None:
            self._restore(durable_state)
        self._recover_events(recovery_events)
        self.reconcile_broker_snapshot(broker_snapshot, confirmed_cash_state)
        self._assert_fixed_parameters()

    def _recover_events(self,events):
        if any(not isinstance(event,dict) or event.get('kind') not in ('fill','order') for event in events):
            _fail('recovery_event_kind_invalid')
        fills=[]
        for event in events:
            if event['kind']!='fill':
                continue
            raw=funding._parse(event['envelope'],'weekly19.ctp-trade.v1','ctp_trade_callback')
            supplied=event.get('signal_identity') or raw.get('signal_identity') or {}
            order_id=raw.get('signal_order_id') or supplied.get('signal_order_id')
            plan=self.engine.order_intents.get(order_id)
            if plan is None or (supplied and supplied!=plan['signal_identity']):
                _fail('recovery_fill_original_plan_missing_or_mismatched')
            fills.append((funding._time(raw['execution_datetime']),str(raw['trade_id']),event['envelope'],plan['signal_identity']))
        # Cumulative order status is never accepted as a substitute for fills.
        # Query arrival order may differ from physical fill order.
        for _,_,envelope,identity in sorted(fills,key=lambda item:(item[0],item[1])):
            self.apply_broker_fill(envelope,identity)
        for event in events:
            if event['kind']=='order':
                self.apply_order_update(event['envelope'])

    def _assert_fixed_parameters(self):
        for key,expected in self.fixed_settings.items():
            actual=getattr(self.strategy,key,None)
            if actual!=expected or (isinstance(expected,bool) and type(actual) is not bool):
                _fail('fixed_strategy_parameter_changed:'+key)
        for key,expected in {'research_daily_addon_enabled':False,'research_macd_disabled':True,
                'research_short_ma_slope_gate_enabled':False,'research_long_ma_slope_gate_enabled':False,
                'research_short_price_range_gate_enabled':True,'research_long_price_range_gate_enabled':False}.items():
            if getattr(self.strategy,key,False) is not expected:
                _fail('fixed_strategy_parameter_changed:'+key)

    def _latest_week(self, symbol):
        rows = self.strategy.ams[symbol].completed
        return rows[-1]['week_end'] if rows else None

    def _admit(self, entry_id, day):
        if entry_id not in self.admitted_ids:
            self.admitted_ids.append(entry_id)
        if date.fromisoformat(day).weekday() != 4:
            if self.broker_equity < 150000 and self.confirmed_cash_state['reserve_remaining_fen']:
                self.open_block_reason = 'funding_recommendation_deferred_to_friday'
            return
        # Account/schema/identity errors remain fatal. Only known cash-continuity
        # gaps may block openings while the original loop retains risk reductions.
        funding.validate_state(self.confirmed_cash_state)
        funding._broker(self.broker_snapshot['account'], self.confirmed_cash_state, self.clock())
        try:
            result = funding.recommend_topup(self.confirmed_cash_state, self.broker_snapshot['account'], day,
                self.admitted_ids, self.current_receipt_hash, self.clock())
        except funding.FundingError as exc:
            reason = str(exc)
            if reason not in {'day_roll_requires_reconciliation',
                    'unreconciled_cashflow_withdrawal', 'unreconciled_cashflow_deposit'}:
                raise
            self.open_block_reason = reason
            self.funding_recommendation = dict(status='funding_evidence_blocked', amount_fen=0,
                request_id=None, actionable=False, blocked_reason=reason, production_qualified=False)
            return
        self.confirmed_cash_state = result['state']
        self.funding_recommendation = result['recommendation']

    def _open_ready(self):
        try:
            if self._pending_close() is not None:
                _fail('close_lifecycle_pending')
            funding.assert_open_funding_ready(self.confirmed_cash_state, self.broker_snapshot['account'], self.clock())
            if self.broker_equity <= 0:
                _fail('nonpositive_equity')
            if (self.open_block_reason == 'funding_recommendation_deferred_to_friday'
                    and self.broker_equity<150000 and self.confirmed_cash_state['reserve_remaining_fen']>0):
                return False
            self.open_block_reason = ''
            return True
        except (funding.FundingError, RuntimeContractError) as exc:
            self.open_block_reason = str(exc)
            return False

    def _positions(self, snapshot):
        raw = funding._parse(snapshot['positions'], 'weekly19.ctp-positions.v1', 'ctp_position_query')
        funding._binding(raw, self.confirmed_cash_state)
        age = (self.clock() - funding._time(raw['observed_at'])).total_seconds()
        if raw.get('query_complete') is not True or not 0 <= age <= funding.MAX_SNAPSHOT_AGE_SECONDS:
            _fail('positions_snapshot_stale_or_incomplete')
        account_raw = funding._parse(snapshot['account'], 'weekly19.ctp-account.v1', 'ctp_account_callback')
        if any(raw.get(k) != account_raw.get(k) for k in ('trading_day', 'generation_uuid')):
            _fail('account_position_cohort_mismatch')
        result = {}
        for row in raw['positions']:
            symbol = row['vt_symbol']
            if symbol not in self.metadata['vt_symbols'] or row['direction'] not in ('long', 'short') or type(row['volume']) is not int or row['volume'] <= 0:
                _fail('unsupported_broker_position')
            if symbol in result:
                _fail('duplicate_or_hedged_broker_position')
            result[symbol] = row['volume'] * (1 if row['direction'] == 'long' else -1)
        return result

    def reconcile_broker_snapshot(self,snapshot,confirmed_cash_state,*,quote_snapshot=None):
        before=self.export_state() if hasattr(self,'broker_snapshot') else None
        try:
            result=self._reconcile_broker_snapshot(snapshot,confirmed_cash_state,quote_snapshot=quote_snapshot)
            if before is not None and self.revision==before['revision'] and self.export_state()['state_sha256']!=before['state_sha256']:
                self.revision+=1
            result.update(revision=self.revision,durable_state_sha256=self.export_state()['state_sha256'])
            return result
        except BaseException:
            if before is not None:
                self._restore(before)
            raise

    def _reconcile_broker_snapshot(self, snapshot, confirmed_cash_state, *, quote_snapshot=None):
        funding.validate_state(confirmed_cash_state)
        if any(confirmed_cash_state[k] != self.confirmed_cash_state[k] for k in ('account_key', 'material_release_id', 'cold_start_date')):
            _fail('funding_state_identity_mismatch')
        if confirmed_cash_state['revision'] < self.confirmed_cash_state['revision']:
            _fail('funding_state_rollback')
        previous=self.confirmed_cash_state
        if (confirmed_cash_state['reserve_remaining_fen']>previous['reserve_remaining_fen']
                or confirmed_cash_state['confirmed_topup_fen']<previous['confirmed_topup_fen']
                or any(confirmed_cash_state['receipts'].get(k)!=v for k,v in previous['receipts'].items())
                or any(confirmed_cash_state['admitted_entries'].get(k)!=v for k,v in previous['admitted_entries'].items())):
            _fail('funding_ledger_rollback')
        account = funding._broker(snapshot['account'], confirmed_cash_state, self.clock())
        raw = funding._parse(snapshot['account'], 'weekly19.ctp-account.v1', 'ctp_account_callback')
        available = funding._money(raw['Available']) / 100
        positions = self._positions(snapshot)
        actual = {s:int(v) for s,v in self.strategy.pos_data.items() if v}
        if positions != actual:
            if positions and not actual and not self.last_processed_day:
                _fail('unprotected_broker_position')
            _fail('broker_strategy_position_mismatch')
        for symbol, pos in positions.items():
            state = self.strategy._find_state_by_contract(symbol)
            if state is None or not state.layers or state.direction != ('long' if pos > 0 else 'short'):
                _fail('unprotected_broker_position')
            filled = sum(l.volume for l in state.layers if l.entry_price_synced)
            if filled != abs(pos) and symbol not in self.strategy.pending_close_lots:
                _fail('broker_protected_volume_mismatch')
        self.confirmed_cash_state = deepcopy(confirmed_cash_state)
        self.broker_snapshot = deepcopy(snapshot)
        self.broker_equity = account['balance_fen'] / 100
        self.broker_available = available
        self.strategy.settled_balance = self.broker_equity
        self.strategy.estimated_equity = self.broker_equity
        retries = self._retry_closes(quote_snapshot)
        rollovers = self._resume_rollovers(quote_snapshot)
        return dict(reconciled=True, broker_equity=self.broker_equity, broker_available=available,
                    retry_intents=retries, rollover_intents=rollovers, reduce_only=self._pending_close() is not None, production_qualified=False)

    def _validate_bars(self, batch, *, expected_day=None):
        if not batch:
            _fail('real_bar_batch_missing')
        days = set()
        for symbol, bar in batch.items():
            day = pd.Timestamp(bar.datetime).strftime('%Y-%m-%d')
            at=funding._time(self.clock()).astimezone(SHANGHAI)
            if day>at.date().isoformat() or (day==at.date().isoformat() and (at.hour,at.minute)<(15,0)):
                _fail('bar_trading_day_not_completed')
            days.add(day)
            fields=(('open','open_price'),('high','high_price'),('low','low_price'),('close','close_price'),
                    ('volume','volume'),('close_oi','open_interest'))
            try:
                if any(isinstance(getattr(bar,attribute),(bool,np.bool_)) for _,attribute in fields):
                    _fail('real_bar_numeric_fields_invalid')
                observed=[float(getattr(bar,attribute)) for _,attribute in fields]
            except (TypeError,ValueError,AttributeError):_fail('real_bar_numeric_fields_invalid')
            prices=observed[:4];volume,oi=observed[4:]
            if symbol != bar.vt_symbol or symbol not in self.metadata['vt_symbols'] or day not in self.calendar or bar.interval != Interval.DAILY:
                _fail('bar_identity_or_interval_invalid')
            if (not all(math.isfinite(x) for x in observed) or min(prices)<=0 or volume<=0 or oi<0
                    or prices[2]>min(prices[0],prices[3]) or prices[1]<max(prices[0],prices[3])):
                _fail('real_bar_ohlcvoi_invalid')
            if (symbol,day) not in self.epoch_lookup:
                _fail('physical_epoch_missing')
            source = self.approved_bar_lookup.loc[(symbol, day)]
            if not all(field in source for field,_ in fields):_fail('approved_physical_ohlcvoi_required')
            try:approved=[float(source[field]) for field,_ in fields]
            except (TypeError,ValueError):_fail('approved_physical_ohlcvoi_invalid')
            if (not all(math.isfinite(x) for x in approved) or min(approved[:5])<=0 or approved[5]<0
                    or approved[2]>min(approved[0],approved[3]) or approved[1]<max(approved[0],approved[3])):
                _fail('approved_physical_ohlcvoi_invalid')
            for (field,_),actual,expected in zip(fields,observed,approved):
                if not math.isclose(actual,expected,rel_tol=0,abs_tol=1e-9):
                    _fail('approved_bar_value_mismatch:'+field)
        if len(days) != 1 or (expected_day is not None and days != {expected_day}):
            _fail('bar_batch_day_mismatch')
        return next(iter(days))

    def warmup(self, real_bar_batches):
        if self.last_processed_day or any(self.strategy.pos_data.values()):
            _fail('warmup_after_live_state_forbidden')
        for batch in real_bar_batches:
            day = self._validate_bars(batch)
            if day <= self.warmup_cursor or day >= self.confirmed_cash_state['cold_start_date']:
                _fail('warmup_order_or_cold_start_violation')
            self._accept_epoch_batch(batch)
            for symbol, bar in batch.items():
                self.strategy.ams[symbol].update_bar(bar)
            self.warmup_cursor = day
        return dict(warmup_cursor=self.warmup_cursor, intents=0, production_qualified=False)

    def _accept_epoch_batch(self,bars):
        pending = deepcopy(self.physical_epoch_state)
        events = []
        for symbol,bar in bars.items():
            day = pd.Timestamp(bar.datetime).strftime('%Y-%m-%d')
            epoch = self.epoch_lookup[(symbol,day)]
            old = pending.get(symbol)
            if old and epoch != old['epoch']:
                gap = (date.fromisoformat(day)-date.fromisoformat(old['last_real_day'])).days
                state = self.strategy._find_state_by_contract(symbol)
                active = any(p['vt_symbol']==symbol and oid not in self.engine.order_terminal
                             for oid,p in self.engine.order_intents.items())
                if gap<=366 or self.strategy.get_pos(symbol) or (state and state.layers) or active:
                    _fail('physical_epoch_transition_not_safely_flat')
                events.append(dict(symbol=symbol,old_epoch=old['epoch'],new_epoch=epoch,date=day,gap_days=gap))
            pending[symbol] = dict(epoch=epoch,last_real_day=day)
        self.physical_epoch_state = pending
        self.physical_epoch_transitions.extend(events)

    def _queue_pending_day(self,trading_date,bars,data_receipt,broker_snapshot,confirmed_cash_state,request_hash):
        before = self.export_state()
        try:
            # The latest completed operational receipt also binds close retries.
            # This advances no original dayloop or historical opening signal.
            self.current_receipt_hash=_hash(data_receipt)
            self.last_processed_day=trading_date
            self.reconcile_broker_snapshot(broker_snapshot,confirmed_cash_state)
            self._accept_epoch_batch(bars)
            for symbol,bar in bars.items():
                self.strategy.ams[symbol].update_bar(bar)
            self.queued_days.append(dict(trading_date=trading_date,bars=dict(bars),receipt=deepcopy(data_receipt)))
            self.last_processed_day=trading_date
            self.revision+=1
            decision=dict(schema='weekly19.runtime-decision.v1',trading_date=trading_date,
                material_release_id=self.release,account_fingerprint=self.account,
                targets=dict(self.strategy.target_data),intents=[],cancel_requests=[],funding_admitted_ids=[],
                funding_admissions=[],funding_recommendation=None,confirmed_cash_state=deepcopy(self.confirmed_cash_state),
                reduce_only=True,bars_queued=True,blocked_reason='unresolved_execution_lifecycle',
                before_state_sha256=before['state_sha256'],after_state_sha256='',
                data_receipt_sha256=_hash(data_receipt),production_qualified=False)
            self.days[trading_date]=dict(request_hash=request_hash,decision=deepcopy(decision))
            decision['after_state_sha256']=self.export_state()['state_sha256']
            self.days[trading_date]['decision']['after_state_sha256']=decision['after_state_sha256']
            return decision
        except BaseException:
            self._restore(before)
            raise

    def _finish_queued_clock(self):
        # Never replay queued on_bars: those historical entries are expired.
        # Only original day-count bookkeeping is advanced for surviving holdings.
        for item in self.queued_days:
            day=item['trading_date']
            for product,state in self.strategy.states.items():
                if not state.layers or not self.strategy.get_pos(state.contract_vt_symbol):
                    continue
                if state.entry_date and pd.Timestamp(state.entry_date).strftime('%Y-%m-%d')!=day:
                    state.bars_since_entry+=1
                target=self.metadata['daily_mapping'].get(day,{}).get(product,'')
                if target and self.strategy._rollover_delay_applies(state,target,self.strategy.get_pos(state.contract_vt_symbol)):
                    self.strategy._rollover_delay_due(state=state,target_contract=target,current_date=day)
        self.expired_signal_days.extend(x['trading_date'] for x in self.queued_days)
        self.queued_days=[]

    def process_completed_day(self, trading_date, bars, data_receipt, broker_snapshot, confirmed_cash_state):
        self._assert_fixed_parameters()
        if (data_receipt.get('schema') != 'weekly19.data-receipt.v1' or data_receipt.get('complete') is not True
                or data_receipt.get('trading_date') != trading_date or data_receipt.get('material_release_id') != self.release):
            _fail('data_receipt_invalid')
        request_hash = _hash(dict(receipt=data_receipt, bars=_encode(bars)))
        if trading_date in self.days:
            if self.days[trading_date]['request_hash'] != request_hash:
                _fail('day_receipt_conflict')
            return deepcopy(self.days[trading_date]['decision'])
        if trading_date <= max(self.last_processed_day, self.warmup_cursor) or trading_date < self.confirmed_cash_state['cold_start_date']:
            _fail('day_order_or_cold_start_violation')
        self._validate_bars(bars, expected_day=trading_date)
        if self._pending_close() is not None or any(oid not in self.engine.order_terminal for oid in self.engine.order_intents):
            return self._queue_pending_day(trading_date,bars,data_receipt,broker_snapshot,confirmed_cash_state,request_hash)
        before = self.export_state()
        try:
            self.reconcile_broker_snapshot(broker_snapshot, confirmed_cash_state)
            self._finish_queued_clock()
            self._accept_epoch_batch(bars)
            self.current_receipt_hash = _hash(data_receipt)
            self.admitted_ids = []
            self.funding_recommendation = None
            self.pending_broker_margin = 0.0
            start = len(self.engine.intents)
            self.engine.bars = dict(bars)
            self.engine.datetime = pd.Timestamp(trading_date).to_pydatetime()
            self.strategy.on_bars(bars)
            if self.engine.intraday_execution_failure:
                _fail('original_strategy_failed:' + self.engine.intraday_execution_failure)
            self.last_processed_day = trading_date
            self.revision += 1
            self.strategy.settled_balance = self.broker_equity
            self.strategy.estimated_equity = self.broker_equity
            protection = []
            for state in self.strategy.states.values():
                for layer in state.layers:
                    protection.append(dict(vt_symbol=state.contract_vt_symbol, direction=layer.direction,
                        volume=layer.volume, stop_price=layer.stop_price, entry_price=layer.entry_price,
                        entry_price_synced=layer.entry_price_synced, completed_week_end=self._latest_week(state.contract_vt_symbol),
                        protection_timing='fresh_completed_week_close'))
            decision = dict(schema='weekly19.runtime-decision.v1', trading_date=trading_date,
                material_release_id=self.release, account_fingerprint=self.account,
                targets=dict(self.strategy.target_data), intents=deepcopy([x for x in self.engine.intents[start:] if 'offset' in x]),
                cancel_requests=deepcopy([x for x in self.engine.intents[start:] if x.get('action') == 'cancel']),
                protection=protection, funding_admitted_ids=list(self.admitted_ids),
                funding_recommendation=deepcopy(self.funding_recommendation),
                funding_admissions=[dict(admitted_entry_id=e,original_funding_admission_id=e,signal_identity=dict(admitted_entry_id=e),
                    vt_symbol=self.admission_contexts[e]['vt_symbol'],
                    execution_day=self.admission_contexts[e]['execution_day']) for e in self.admitted_ids],
                confirmed_cash_state=deepcopy(self.confirmed_cash_state), data_receipt_sha256=self.current_receipt_hash,
                before_state_sha256=before['state_sha256'], after_state_sha256=self.export_state()['state_sha256'],
                production_qualified=False)
            self.days[trading_date] = dict(request_hash=request_hash, decision=deepcopy(decision))
            decision['after_state_sha256'] = self.export_state()['state_sha256']
            self.days[trading_date]['decision']['after_state_sha256'] = decision['after_state_sha256']
            return decision
        except BaseException:
            self._restore(before)
            raise

    def _child_batch(self,raw,plan):
        order_id=plan['signal_order_id']
        required={'api_slot_batch_count','expected_children','expected_children_sha256',
                  'approved_parent_volume','child_order_id'}
        if not required<=set(raw):_fail('physical_child_batch_proof_required')
        batch_id=raw.get('execution_batch_id',raw.get('api_slot_batch_id'))
        if 'execution_batch_id' in raw and 'api_slot_batch_id' in raw and raw['execution_batch_id']!=raw['api_slot_batch_id']:
            _fail('physical_child_batch_id_alias_mismatch')
        children=raw['expected_children'];count=raw['api_slot_batch_count']
        if (not isinstance(batch_id,str) or len(batch_id)!=24 or any(c not in '0123456789abcdef' for c in batch_id)
                or type(count) is not int or not 1<=count<=100 or not isinstance(children,list) or len(children)!=count
                or _hash(children)!=raw['expected_children_sha256']):_fail('physical_child_manifest_invalid')
        required_child={'child_order_id','child_order_index','volume','broker_offset','vt_symbol','direction','trading_date'}
        ids=set();total=0
        for index,child in enumerate(children):
            if (set(child)!=required_child or not isinstance(child['child_order_id'],str) or not child['child_order_id']
                    or child['child_order_id'] in ids or type(child['child_order_index']) is not int or child['child_order_index']!=index
                    or type(child['volume']) is not int or child['volume']<=0
                    or any(child[k]!=plan[k] for k in ('vt_symbol','direction','trading_date'))
                    or child['broker_offset'] not in ('open','close','closetoday','closeyesterday')
                    or ('open' if child['broker_offset']=='open' else 'close')!=plan['offset']):
                _fail('physical_child_descriptor_invalid')
            ids.add(child['child_order_id']);total+=child['volume']
        if (type(raw['approved_parent_volume']) is not int or total!=raw['approved_parent_volume']
                or not 0<total<=plan['planned_volume'] or (plan['offset']=='close' and total!=plan['planned_volume'])):
            _fail('physical_child_parent_volume_mismatch')
        descriptor=next((c for c in children if c['child_order_id']==raw['child_order_id']),None)
        if descriptor is None or descriptor['broker_offset']!=raw.get('broker_offset'):
            _fail('physical_child_native_binding_mismatch')
        existing=self.child_batches.get(order_id)
        identity=dict(batch_id=batch_id,expected_children=children,manifest_sha256=raw['expected_children_sha256'],approved_parent_volume=total)
        if existing is None:
            if self.engine.order_filled[order_id] or order_id in self.broker_order_bindings:
                _fail('cannot_adopt_child_batch_after_unbound_activity')
            batch=dict(identity,children={c['child_order_id']:dict(filled=0,status='unknown',reported_traded=0,broker_order_id=None) for c in children},status='pending')
        else:
            if any(existing[k]!=v for k,v in identity.items()):_fail('physical_child_manifest_changed')
            batch=deepcopy(existing)
        child=batch['children'][raw['child_order_id']]
        broker_id=raw.get('broker_order_id')
        if not isinstance(broker_id,str) or not broker_id:_fail('physical_child_actual_broker_id_required')
        if child['broker_order_id'] not in (None,broker_id) or any(k!=raw['child_order_id'] and c['broker_order_id']==broker_id for k,c in batch['children'].items()):
            _fail('physical_child_broker_binding_mismatch')
        if any(oid!=order_id and binding==broker_id for oid,binding in self.broker_order_bindings.items()) or any(
                oid!=order_id and any(c['broker_order_id']==broker_id for c in other['children'].values())
                for oid,other in self.child_batches.items()):_fail('physical_broker_id_owned_by_another_parent')
        child['broker_order_id']=broker_id
        return batch,child,descriptor

    def _aggregate_child_parent(self,plan,batch):
        terminal={'filled','cancelled','rejected'}
        if not all(c['status'] in terminal for c in batch['children'].values()):return
        order_id=plan['signal_order_id'];filled=sum(c['filled'] for c in batch['children'].values())
        if filled!=self.engine.order_filled[order_id]:_fail('physical_child_parent_fill_conservation_failed')
        batch['status']='complete'
        if filled==plan['planned_volume']:
            self.engine.order_terminal[order_id]='filled';self.strategy.active_orderids.discard(order_id);return
        status='rejected' if not filled and all(c['status']=='rejected' for c in batch['children'].values()) else 'cancelled'
        if plan['offset']=='close':
            life=self._pending_close(plan['vt_symbol'])
            if life is None:_fail('close_cancel_lifecycle_missing')
            life['status']='retry_required';self._sync_close_inventory(life)
        else:
            state=self.strategy._find_state_by_contract(plan['vt_symbol']);remaining=plan['planned_volume']-filled
            pending=[] if state is None else [l for l in state.layers if not l.entry_price_synced and l.direction==plan['direction']
                and pd.Timestamp(l.entry_date).strftime('%Y-%m-%d')==plan['signal_datetime'][:10]]
            if sum(l.volume for l in pending)!=remaining:_fail('cancelled_open_plan_ownership_mismatch')
            if state is not None:
                state.layers=[l for l in state.layers if all(l is not q for q in pending)]
                if not state.layers:state.reset()
            self.strategy.set_target(plan['vt_symbol'],self.strategy.get_pos(plan['vt_symbol']))
            order=self.strategy.get_order(order_id)
            if order is not None:
                order.status=Status.REJECTED if status=='rejected' else Status.CANCELLED;order.traded=filled
                self.strategy.update_order(order)
        self.engine.order_terminal[order_id]=status;self.strategy.active_orderids.discard(order_id)

    def apply_order_update(self,event):
        raw=funding._parse(event,'weekly19.ctp-order.v1','ctp_order_callback');funding._binding(raw,self.confirmed_cash_state)
        order_id=raw.get('signal_order_id');plan=self.engine.order_intents.get(order_id)
        if plan is None:_fail('unknown_order_identity')
        if 'api_slot_batch_id' not in raw and 'execution_batch_id' not in raw:
            if order_id in self.child_batches:_fail('physical_child_batch_proof_required')
            return self._apply_single_order_update(event)
        batch,child,descriptor=self._child_batch(raw,plan)
        if (raw.get('source_callback') not in ('onRtnOrder','onRspQryOrder') or raw.get('intent_id')!=plan['intent_id']
                or raw.get('signal_identity')!=plan['signal_identity']
                or any(raw.get(k)!=plan[k] for k in ('vt_symbol','direction','offset'))
                or raw.get('volume')!=descriptor['volume']):_fail('physical_child_order_signal_mismatch')
        traded=raw.get('traded');status=raw.get('status')
        if (type(traded) is not int or not 0<=traded<=descriptor['volume'] or traded>child['filled']
                or status not in ('accepted','working','partially_filled','filled','cancelled','rejected')
                or (status=='filled' and traded!=descriptor['volume'])
                or (status in ('cancelled','rejected') and traded!=child['filled'])):
            _fail('physical_child_order_fill_total_mismatch')
        keys=('account_key','material_release_id','intent_id','signal_order_id','signal_identity','broker_order_id','vt_symbol','direction','offset','broker_offset','volume','traded','status')
        digest=_hash({k:raw[k] for k in keys})
        if raw.get('event_semantic_sha256')!=digest or raw.get('event_id')!='ctp-order:'+digest:_fail('order_semantic_identity_mismatch')
        key=raw['event_id']
        if key in self.order_updates:
            if self.order_updates[key]['semantic_sha256']!=digest:_fail('order_event_identity_reused')
            return self.export_state()
        if child['status'] in ('filled','cancelled','rejected') and status in ('filled','cancelled','rejected') and child['status']!=status:
            _fail('physical_child_terminal_conflict')
        before=self.export_state()
        try:
            if traded>=child['reported_traded'] and child['status'] not in ('filled','cancelled','rejected'):
                child.update(status=status,reported_traded=traded)
            self.child_batches[order_id]=batch
            self.broker_order_bindings[order_id]='batch:'+batch['batch_id']
            self.order_updates[key]=dict(semantic_sha256=digest,first_raw_sha256=event['raw_sha256'])
            self._aggregate_child_parent(plan,batch);self.revision+=1
            return self.export_state()
        except BaseException:
            self._restore(before);raise

    def apply_broker_fill(self,fill,signal_identity):
        raw=funding._parse(fill,'weekly19.ctp-trade.v1','ctp_trade_callback');funding._binding(raw,self.confirmed_cash_state)
        order_id=signal_identity.get('signal_order_id');plan=self.engine.order_intents.get(order_id)
        if plan is None:_fail('fill_signal_identity_mismatch')
        if 'api_slot_batch_id' not in raw and 'execution_batch_id' not in raw:
            if order_id in self.child_batches:_fail('physical_child_batch_proof_required')
            return self._apply_single_broker_fill(fill,signal_identity)
        batch,child,descriptor=self._child_batch(raw,plan)
        if (raw.get('source_callback') not in ('onRtnTrade','onRspQryTrade') or raw.get('intent_id')!=plan['intent_id']
                or raw.get('signal_identity')!=plan['signal_identity'] or raw.get('signal_order_id')!=order_id
                or 'native_offset_flag' not in raw):_fail('physical_child_trade_signal_mismatch')
        duplicate=str(raw.get('trade_id')) in self.fills
        if not duplicate and (type(raw.get('volume')) is not int or raw['volume']<=0 or raw['volume']>descriptor['volume']-child['filled']
                or child['status'] in ('cancelled','rejected')):_fail('physical_child_fill_exceeds_or_after_terminal')
        before=self.export_state()
        try:
            self.child_batches[order_id]=batch
            result=self._apply_single_broker_fill(fill,signal_identity,_transaction_state=before,_defer_export=True)
            if not duplicate:
                child['filled']+=raw['volume']
                if child['filled']==descriptor['volume']:child['status']='filled'
                self._aggregate_child_parent(plan,batch)
            self.broker_order_bindings[order_id]='batch:'+batch['batch_id']
            return self.export_state()
        except BaseException:
            self._restore(before);raise

    def _apply_single_order_update(self, event):
        raw = funding._parse(event, 'weekly19.ctp-order.v1', 'ctp_order_callback')
        funding._binding(raw, self.confirmed_cash_state)
        order_id = raw['signal_order_id']
        if order_id not in self.engine.order_intents:
            _fail('unknown_order_identity')
        if raw.get('broker_order_id'):
            known = self.broker_order_bindings.get(order_id)
            if known is not None and known != str(raw['broker_order_id']):
                _fail('broker_order_binding_mismatch')
        plan = self.engine.order_intents[order_id]
        if raw.get('source_callback') not in (None,'onRtnOrder','onRspQryOrder'):
            _fail('order_source_callback_invalid')
        if (('intent_id' in raw and raw['intent_id']!=plan['intent_id'])
                or ('signal_identity' in raw and raw['signal_identity']!=plan['signal_identity'])
                or any(k in raw and raw[k]!=plan[k] for k in ('vt_symbol','direction','offset','volume'))):
            _fail('raw_order_signal_binding_mismatch')
        if type(raw.get('traded')) is not int or raw['traded']<0:
            _fail('order_traded_integer_required')
        native=raw.get('broker_offset',raw.get('offset',plan['offset']))
        if native not in ('open','close','closetoday','closeyesterday') or ('open' if native=='open' else 'close')!=plan['offset']:
            _fail('order_native_offset_binding_mismatch')
        semantic=dict(account_key=self.account,material_release_id=self.release,intent_id=plan['intent_id'],
            signal_order_id=order_id,signal_identity=plan['signal_identity'],broker_order_id=raw['broker_order_id'],
            vt_symbol=plan['vt_symbol'],direction=plan['direction'],offset=plan['offset'],broker_offset=native,
            volume=plan['volume'],traded=raw['traded'],status=raw['status'])
        digest=_hash(semantic) if 'event_semantic_sha256' in raw else event['raw_sha256']
        if 'event_semantic_sha256' in raw and (raw['event_semantic_sha256']!=digest or raw['event_id']!='ctp-order:'+digest):
            _fail('order_semantic_identity_mismatch')
        evidence=dict(semantic_sha256=digest,first_raw_sha256=event['raw_sha256'])
        key = str(raw['event_id'])
        if key in self.order_updates:
            if self.order_updates[key].get('semantic_sha256') != digest:
                _fail('order_event_identity_reused')
            return self.export_state()
        if raw.get('traded') != self.engine.order_filled[order_id]:
            _fail('order_fill_total_mismatch')
        if raw['status'] not in ('accepted', 'working', 'partially_filled', 'filled', 'cancelled', 'rejected'):
            _fail('order_status_unknown')
        if raw['status'] == 'filled' and raw['traded'] != plan['planned_volume']:
            _fail('order_fill_total_mismatch')
        if raw['status'] in ('cancelled', 'rejected'):
            # Opening plans are separated from confirmed layers by the original
            # entry_price_synced marker. A cancelled close also changed original
            # episode outcome memory; it needs a richer proven reconciliation.
            if plan['offset'] != 'open':
                life = self._pending_close(plan['vt_symbol'])
                if life is None:
                    _fail('close_cancel_lifecycle_missing')
                self.engine.order_terminal[order_id] = raw['status']
                self.strategy.active_orderids.discard(order_id)
                life['status'] = 'retry_required'
                self._sync_close_inventory(life)
                self.order_updates[key] = deepcopy(evidence)
                self.broker_order_bindings[order_id] = str(raw['broker_order_id'])
                self.revision += 1
                return self.export_state()
            before = self.export_state()
            try:
                state = self.strategy._find_state_by_contract(plan['vt_symbol'])
                remaining = plan['planned_volume'] - self.engine.order_filled[order_id]
                pending = [] if state is None else [l for l in state.layers
                    if not l.entry_price_synced and l.direction == plan['direction']
                    and pd.Timestamp(l.entry_date).strftime('%Y-%m-%d') == plan['signal_datetime'][:10]]
                if sum(l.volume for l in pending) != remaining:
                    _fail('cancelled_open_plan_ownership_mismatch')
                if state is not None:
                    state.layers = [l for l in state.layers if all(l is not q for q in pending)]
                    if not state.layers:
                        state.reset()
                self.strategy.set_target(plan['vt_symbol'], self.strategy.get_pos(plan['vt_symbol']))
                self.strategy.active_orderids.discard(order_id)
                self.engine.order_terminal[order_id] = raw['status']
                order = self.strategy.get_order(order_id)
                if order is not None:
                    order.status = Status.CANCELLED if raw['status'] == 'cancelled' else Status.REJECTED
                    order.traded = raw['traded']
                    self.strategy.update_order(order)
                self.order_updates[key] = deepcopy(evidence)
                self.broker_order_bindings[order_id] = str(raw['broker_order_id'])
                self.revision += 1
                return self.export_state()
            except BaseException:
                self._restore(before)
                raise
        self.order_updates[key] = deepcopy(evidence)
        self.broker_order_bindings[order_id] = str(raw['broker_order_id'])
        self.revision += 1
        return self.export_state()

    def _apply_single_broker_fill(self, fill, signal_identity, *, _transaction_state=None, _defer_export=False):
        raw = funding._parse(fill, 'weekly19.ctp-trade.v1', 'ctp_trade_callback')
        funding._binding(raw, self.confirmed_cash_state)
        native_offset=raw.get('broker_offset',raw.get('offset'))
        flags={'open':'0','close':'1','closetoday':'3','closeyesterday':'4'}
        if native_offset not in flags:
            _fail('native_offset_unknown')
        business_offset='open' if native_offset=='open' else 'close'
        if (raw.get('business_offset',business_offset)!=business_offset
                or raw.get('offset') not in (business_offset,native_offset)
                or ('native_offset_flag' in raw and raw['native_offset_flag']!=flags[native_offset])):
            _fail('native_offset_business_binding_mismatch')
        if raw.get('source_callback') not in (None,'onRtnTrade','onRspQryTrade'):
            _fail('trade_source_callback_invalid')
        trade_id = str(raw['trade_id'])
        order_id = signal_identity.get('signal_order_id')
        plan = self.engine.order_intents.get(order_id)
        if plan is None or signal_identity != plan['signal_identity']:
            _fail('fill_signal_identity_mismatch')
        if (('signal_identity' in raw and raw['signal_identity']!=signal_identity)
                or ('intent_id' in raw and raw['intent_id']!=plan['intent_id'])
                or ('signal_order_id' in raw and raw['signal_order_id']!=order_id)):
            _fail('raw_fill_signal_binding_mismatch')
        bound = self.broker_order_bindings.get(order_id)
        if order_id not in self.child_batches and bound is not None and bound != str(raw.get('broker_order_id', '')):
            _fail('broker_order_binding_mismatch')
        if any(raw.get(k) != plan[k] for k in ('vt_symbol','direction')) or business_offset!=plan['offset'] or raw['trading_day'] != plan['trading_date']:
            _fail('fill_plan_mismatch')
        volume = raw['volume']
        if type(volume) is not int or volume<=0:
            _fail('fill_volume_integer_required')
        price = float(raw['price'])
        if not math.isfinite(price) or price <= 0:
            _fail('fill_price_invalid')
        execution = funding._time(raw['execution_datetime'])
        if execution > self.clock():
            _fail('fill_execution_in_future')
        semantic=dict(account_key=self.account,material_release_id=self.release,trade_id=trade_id,
            intent_id=plan['intent_id'],signal_order_id=order_id,signal_identity=signal_identity,
            broker_order_id=raw['broker_order_id'],vt_symbol=raw['vt_symbol'],direction=raw['direction'],
            offset=business_offset,broker_offset=native_offset,volume=volume,price=price,
            trading_day=raw['trading_day'],execution_datetime=execution.astimezone(SHANGHAI).isoformat())
        digest=_hash(semantic)
        if trade_id in self.fills:
            if self.fills[trade_id].get('semantic_sha256') != digest:
                _fail('trade_identity_reused')
            return None if _defer_export else self.export_state()
        if volume>plan['planned_volume']-self.engine.order_filled[order_id]:
            _fail('fill_volume_exceeds_plan')
        if order_id in self.engine.order_terminal:
            _fail('fill_after_terminal_order')
        code, exchange = raw['vt_symbol'].split('.')
        trade = TradeData(symbol=code, exchange=Exchange(exchange), orderid=order_id.split('.',1)[1],
            tradeid=trade_id, direction=Direction[raw['direction'].upper()], offset=Offset[business_offset.upper()],
            price=price, volume=volume, datetime=execution, gateway_name='W19')
        trade.broker_offset=native_offset
        trade.native_offset_flag=flags[native_offset]
        trade.trading_date = date.fromisoformat(raw['trading_day'])
        trade.signal_datetime = pd.Timestamp(plan['signal_datetime']).to_pydatetime()
        trade.signal_order_id = order_id
        before = self.export_state() if _transaction_state is None else _transaction_state
        try:
            self.strategy.update_trade(trade)
            if plan['offset'] == 'close':
                self._close_fill(plan, volume, price, raw['trading_day'])
            self.engine.order_filled[order_id] += volume
            if self.engine.order_filled[order_id] == plan['planned_volume']:
                self.engine.order_terminal[order_id] = 'filled'
                self.strategy.active_orderids.discard(order_id)
            self.fills[trade_id] = dict(semantic_sha256=digest,first_raw_sha256=fill['raw_sha256'])
            self.broker_order_bindings[order_id] = str(raw['broker_order_id'])
            self.revision += 1
            self.strategy.settled_balance = self.broker_equity
            self.strategy.estimated_equity = self.broker_equity
            return None if _defer_export else self.export_state()
        except BaseException:
            self._restore(before)
            raise

    def _position_identity(self, symbol, kind, signal_day):
        product = self.metadata['source_symbol_by_contract'][symbol]
        prior = self.position_identities.get(symbol)
        if kind in ('risk_close', 'rollover_close'):
            if prior is None:
                _fail('confirmed_position_identity_missing')
            return prior
        if prior is not None and prior['entry_signal_day'] == signal_day:
            return prior
        root = None
        if kind == 'rollover_reopen':
            root = next((v['root_position_id'] for s,v in self.position_identities.items()
                         if self.metadata['source_symbol_by_contract'].get(s) == product), None)
        root = root or 'w19-root-' + _hash([self.account,self.release,product,signal_day])
        cycle = 'w19-cycle-' + _hash([root,symbol,self.epoch_lookup[(symbol,signal_day)]])
        row = dict(root_position_id=root, position_cycle_id=cycle,
                   position_epoch_id='w19-pos-'+_hash([root,cycle]), entry_signal_day=signal_day)
        self.position_identities[symbol] = row
        return row

    def execution_state(self, intent_id):
        plan = next((p for p in self.engine.order_intents.values() if p['intent_id']==intent_id), None)
        if plan is None:
            _fail('unknown_intent')
        identity = self.position_identities[plan['vt_symbol']]
        return dict(identity, state_generation=f"{identity['position_epoch_id']}:{self.revision}",
                    revision=self.revision, account_key=self.account, account_fingerprint=self.account,
                    material_release_id=self.release, durable_state_sha256=self.export_state()['state_sha256'],
                    position_state='confirmed' if self.strategy.get_pos(plan['vt_symbol']) else 'planned_or_flat',
                    production_qualified=False)

    def _clone_for_sizing(self, broker_snapshot, confirmed_cash_state):
        # Keep the complete cross-product risk/position state. Historical source
        # inputs and completed AM records are read-only in this sizing-only path.
        # No constructor, on_bars, AM update, bank reserve or live actor mutation.
        clone=type(self).__new__(type(self))
        strategy=type(self.strategy).__new__(type(self.strategy))
        engine=type(self.engine).__new__(type(self.engine))
        memo={id(self):clone,id(self.strategy):strategy,id(self.engine):engine}
        for name in ('metadata','calendar','weeks','physical_frame','epoch_lookup','range_history','approved_bar_lookup',
                     'source_manifest','_input_prefix_cache'):
            value=getattr(self,name);memo[id(value)]=value
        # WeeklyArrayManager.__getattr__ delegates to inner; preallocation avoids
        # deepcopy probing an uninitialized wrapper and recursing indefinitely.
        for am in self.strategy.ams.values():
            memo[id(am)]=type(am).__new__(type(am))
            for name in ('weeks','completed','rejected'):
                value=getattr(am,name);memo[id(value)]=value
        for am in self.strategy.ams.values():
            memo[id(am)].__dict__.update(deepcopy(vars(am),memo))
        strategy.__dict__.update(deepcopy(vars(self.strategy),memo))
        engine.__dict__.update(deepcopy(vars(self.engine),memo))
        clone.__dict__.update(deepcopy(vars(self),memo))
        clone.strategy=strategy;clone.engine=engine;clone.revalidating=True
        clone._reconcile_broker_snapshot(broker_snapshot,confirmed_cash_state)
        clone._assert_fixed_parameters()
        return clone

    def _current_sizing(self, context, broker_snapshot, confirmed_cash_state, quote_snapshot):
        self._assert_fixed_parameters()
        symbol = context['vt_symbol']
        bid, ask = self._validate_quote(quote_snapshot,symbol,context['execution_day'])
        account=funding._broker(broker_snapshot['account'],confirmed_cash_state,self.clock())
        if account['trading_day']!=context['execution_day']:
            _fail('execution_broker_day_mismatch')
        clone = self._clone_for_sizing(broker_snapshot,confirmed_cash_state)
        for state in clone.strategy.states.values():
            state.layers=[l for l in state.layers if l.entry_price_synced]
            if not state.layers:
                state.reset()
        clone.strategy._reset_intrabar_reservations()
        clone.pending_broker_margin=0.0
        if clone.confirmed_cash_state['confirmed_topup_fen']>context['confirmed_topup_fen']:
            clone.open_block_reason=''
        bar = _decode(_encode(context['bar']))
        bar.close_price = ask if context['direction']=='long' else bid
        clone.strategy.current_bar_date = pd.Timestamp(bar.datetime).normalize()
        clone.strategy.estimated_equity = clone.broker_equity
        # Refresh current ratios only, not volatility/overheat time-series or AM.
        clone.strategy.total_margin_in_use = clone.strategy._estimate_margin_usage(clone.engine.bars)
        clone.strategy.cluster_margin_usage = clone.strategy._estimate_margin_usage_by_cluster(clone.engine.bars)
        clone.strategy.cluster_unrealized_pnl = clone.strategy._estimate_unrealized_pnl_by_cluster(clone.engine.bars)
        clone.strategy._refresh_portfolio_drawdown_state()
        clone.strategy._refresh_portfolio_margin_deleverage_state()
        clone.strategy._refresh_risk_cluster_heat_pressure_snapshot()
        kwargs = {k:context[k] for k in ('risk_mode_override','entry_context','apply_env_gate',
                                        'active_positions_before','correlation_snapshot')}
        sizing = clone.strategy._calculate_entry_sizing(symbol,context['direction'],bar,
                    context['history'],context['signal_data'],**kwargs)
        return clone,bar,sizing

    def revalidate_open_intent(self,intent_id,*,broker_snapshot,confirmed_cash_state,quote_snapshot):
        plan = next((p for p in self.engine.order_intents.values() if p['intent_id']==intent_id), None)
        if plan is None or plan['offset']!='open' or intent_id not in self.open_contexts:
            _fail('open_intent_context_missing')
        context = self.open_contexts[intent_id]
        if self.last_processed_day >= context['execution_day'] or self.queued_days:
            _fail('signal_expired_no_historical_open')
        clone,bar,sizing = self._current_sizing(context,broker_snapshot,confirmed_cash_state,quote_snapshot)
        selected = min(plan['planned_volume']-self.engine.order_filled[plan['signal_order_id']],int(sizing['selected_volume']))
        return dict(schema='weekly19.open-risk-proof.v1', intent_id=intent_id,
            selected_volume=selected, approved_volume_cap=plan['planned_volume'], current_equity=clone.broker_equity,
            current_available=clone.broker_available, execution_reference=float(bar.close_price),
            stop_price=float(sizing['stop_price']), parent_selected_volume=sizing['weekly19_parent_selected_volume'],
            source_history_sha256=context['history_sha256'], source_data_receipt_sha256=context['data_receipt_sha256'],
            durable_state_sha256=self.export_state()['state_sha256'],
            account_raw_sha256=broker_snapshot['account']['raw_sha256'], quote_sha256=_hash(quote_snapshot),
            quote_session_id=quote_snapshot['session_id'], confirmed_funding_revision=confirmed_cash_state['revision'],
            blocked_reason=clone.open_block_reason if selected==0 else '', production_qualified=False)

    def replan_after_confirmed_funding(self,signal_identity,broker_snapshot,confirmed_cash_state,quote_snapshot):
        entry_id = signal_identity.get('admitted_entry_id')
        context = self.admission_contexts.get(entry_id)
        if context is None:
            _fail('admitted_signal_identity_missing')
        if self.last_processed_day >= context['execution_day'] or self.queued_days:
            _fail('funded_signal_expired_or_receipt_missing')
        symbol = context['vt_symbol']
        self._validate_quote(quote_snapshot,symbol,context['execution_day'])
        account=funding._broker(broker_snapshot['account'],confirmed_cash_state,self.clock())
        funding.assert_open_funding_ready(confirmed_cash_state,broker_snapshot['account'],self.clock())
        has_confirmed_transfer=confirmed_cash_state['confirmed_topup_fen']>context['confirmed_topup_fen']
        if not has_confirmed_transfer and account['balance_fen']<15000000:
            _fail('funded_signal_expired_or_receipt_missing')
        ready_reason='confirmed_transfer' if has_confirmed_transfer else 'equity_recovered_without_transfer'
        # Once this original admission has a current approved cap, later quotes
        # revalidate that cap. They do not turn market fluctuations into new T.
        cash_source=_hash([ready_reason,confirmed_cash_state['confirmed_topup_fen'],confirmed_cash_state['receipts']])
        cached=self.funding_replans.get(entry_id)
        if cached and cached['cash_source']==cash_source:
            plans=[deepcopy(p) for p in self.engine.order_intents.values() if p['intent_id'] in cached['intent_ids']]
            return dict(replanned=True,selected_volume=cached['selected_volume'],intents=plans,
                superseded_intent_ids=cached['superseded_intent_ids'],
                confirmed_funding_revision=cached['funding_revision'],funding_ready_reason=cached.get('funding_ready_reason','confirmed_transfer'),
                durable_state_sha256=self.export_state()['state_sha256'],production_qualified=False)
        if self.strategy.get_pos(symbol) or self._pending_close() is not None:
            _fail('funding_replan_requires_flat_reconciled_position')
        related = [(oid,p) for oid,p in self.engine.order_intents.items() if p['vt_symbol']==symbol and p['offset']=='open']
        if any(self.engine.order_filled[oid] or oid in self.broker_order_bindings for oid,p in related):
            _fail('cannot_enlarge_filled_or_broker_bound_plan')
        clone,bar,sizing = self._current_sizing(context,broker_snapshot,confirmed_cash_state,quote_snapshot)
        volume = int(sizing['selected_volume'])
        if volume <= 0:
            return dict(replanned=False,selected_volume=0,blocked_reason=clone.open_block_reason,
                        production_qualified=False)
        before = self.export_state()
        try:
            self.reconcile_broker_snapshot(broker_snapshot,confirmed_cash_state)
            self.open_block_reason=''
            # Local unsent plans may be explicitly superseded. Broker-bound ones
            # were rejected above; no fake cancel acknowledgement is invented.
            for oid,plan in related:
                self.engine.order_terminal[oid] = 'superseded_before_send'
                self.strategy.active_orderids.discard(oid)
            state = self.strategy.states[self.metadata['source_symbol_by_contract'][symbol]]
            if state.layers and any(l.entry_price_synced for l in state.layers):
                _fail('funding_replan_has_confirmed_layer')
            state.reset()
            self.strategy.set_target(symbol,0)
            self.strategy.current_bar_date = pd.Timestamp(context['bar'].datetime)
            self.engine.datetime = context['bar'].datetime
            self.current_receipt_hash = context['data_receipt_sha256']
            self.strategy._open_position(state,symbol,context['direction'],volume,bar,
                context['signal_data']['signal'],context['history'],context['signal_data'],sizing_snapshot=sizing)
            self.strategy._reserve_intrabar_entry(state.product_vt_symbol,sizing,volume,count_active_position=True)
            self.strategy._apply_state_target(state)
            self.sizing_contexts[(symbol,context['direction'])] = deepcopy(context)
            start = len(self.engine.intents)
            self.strategy.rebalance_portfolio({symbol:bar})
            emitted = [x for x in self.engine.intents[start:] if x.get('offset')=='open']
            self.revision += 1
            self.funding_replans[entry_id]=dict(cash_source=cash_source,intent_ids=[p['intent_id'] for p in emitted],
                selected_volume=volume,superseded_intent_ids=[p['intent_id'] for oid,p in related],
                funding_revision=confirmed_cash_state['revision'],funding_ready_reason=ready_reason)
            return dict(replanned=True,selected_volume=volume,intents=deepcopy(emitted),
                superseded_intent_ids=[p['intent_id'] for oid,p in related],
                confirmed_funding_revision=confirmed_cash_state['revision'],funding_ready_reason=ready_reason,
                durable_state_sha256=self.export_state()['state_sha256'],production_qualified=False)
        except BaseException:
            self._restore(before)
            raise

    @contextmanager
    def _capture_close(self, state):
        if self.close_capture is not None:
            yield
            return
        symbol = state.contract_vt_symbol
        if any(x['symbol'] == symbol and x['status'] != 'completed' for x in self.close_lifecycles.values()):
            _fail('duplicate_close_lifecycle')
        actual = abs(int(self.strategy.get_pos(symbol)))
        if actual <= 0 or any(not l.entry_price_synced for l in state.layers):
            _fail('close_without_confirmed_inventory')
        capture = dict(symbol=symbol, product=state.product_vt_symbol, before_state=_encode(state),
            layer_ids=[id(l) for l in state.layers], lots=[], risk_events=[],
            realized_before=float(self.strategy.realized_pnl))
        self.close_capture = capture
        try:
            yield
            if not capture['lots']:
                return
            volume = sum(x['volume'] for x in capture['lots'])
            if volume > actual:
                _fail('close_plan_exceeds_actual_inventory')
            lid = _hash([self.account, self.release, str(self.engine.datetime), symbol,
                         len(self.close_lifecycles)])
            self.close_lifecycles[lid] = dict(lifecycle_id=lid, symbol=symbol, product=capture['product'],
                before_state=capture['before_state'], planned_state=None, lots=capture['lots'],
                risk_events=capture['risk_events'], volume=volume, filled=0, realized_pnl=0.0,
                status='pending', order_ids=[], risk_committed=False)
            self.strategy.realized_pnl = capture['realized_before']
        finally:
            self.close_capture = None

    def _pending_close(self, symbol=None):
        return next((x for x in self.close_lifecycles.values()
                     if x['status'] != 'completed' and (symbol is None or x['symbol'] == symbol)), None)

    def _attach_close_intent(self, order_id):
        plan = self.engine.order_intents[order_id]
        life = self._pending_close(plan['vt_symbol'])
        if life is None:
            _fail('close_intent_without_owned_lifecycle')
        if life['planned_state'] is None:
            life['planned_state'] = _encode(self.strategy.states[life['product']])
        life['order_ids'].append(order_id)
        life['status'] = 'pending'
        plan['close_lifecycle_id'] = life['lifecycle_id']
        self._sync_close_inventory(life)

    def _sync_close_inventory(self, life):
        protected = _decode(life['before_state'])
        by_index = {}
        for lot in life['lots']:
            by_index[lot['layer_index']] = by_index.get(lot['layer_index'], 0) + lot['volume'] - lot['remaining']
        remaining = []
        for index, layer in enumerate(protected.layers):
            layer.volume -= by_index.get(index, 0)
            if layer.volume < 0:
                _fail('negative_protected_inventory')
            if layer.volume:
                remaining.append(layer)
        protected.layers = remaining
        if not remaining:
            protected.reset()
        self.strategy.states[life['product']] = protected
        return protected

    def _close_fill(self, plan, volume, price, trading_day):
        life = self._pending_close(plan['vt_symbol'])
        if life is None or volume > life['volume'] - life['filled']:
            _fail('close_fill_ownership_mismatch')
        left = volume
        realized = 0.0
        for lot in life['lots']:
            n = min(left, lot['remaining'])
            if not n:
                continue
            delta = (price-lot['entry_price']) * self.metadata['sizes'][life['symbol']] * n
            if lot['direction'] == 'short':
                delta = -delta
            lot['remaining'] -= n
            lot['realized_pnl'] += delta
            realized += delta
            left -= n
            if not left:
                break
        if left:
            _fail('close_fill_ownership_mismatch')
        life['filled'] += volume
        life['realized_pnl'] += realized
        self.strategy.realized_pnl += realized
        self._sync_close_inventory(life)
        if life['filled'] == life['volume']:
            if life['risk_committed']:
                _fail('close_risk_committed_twice')
            saved_day = self.strategy.current_bar_date
            self.strategy.current_bar_date = pd.Timestamp(trading_day)
            try:
                for lot in life['lots']:
                    self.strategy._record_product_direction_outcome(life['product'], lot['direction'], lot['realized_pnl'])
                events = life['risk_events']
                if len(events) != 1:
                    _fail('close_risk_event_count_unproven')
                event = events[0]
                self.strategy._update_streak_risk_state(life['realized_pnl'], event['product'],
                    exit_reason=event['exit_reason'], profit_giveback_context=event['profit_giveback_context'])
                life['risk_committed'] = True
                life['status'] = 'completed'
            finally:
                self.strategy.current_bar_date = saved_day
        return life

    def _validate_quote(self, quote, symbol, trading_day):
        if isinstance(quote,dict) and quote.get('symbol') and quote.get('vt_symbol') and quote['symbol']!=quote['vt_symbol']:
            _fail('quote_symbol_alias_mismatch')
        if (not isinstance(quote, dict) or quote.get('symbol',quote.get('vt_symbol')) != symbol
                or quote.get('trading_date') != trading_day or not quote.get('session_id')):
            _fail('quote_identity_invalid')
        age = (self.clock()-funding._time(quote['observed_at'])).total_seconds()
        if not 0 <= age <= 15:
            _fail('quote_stale_or_future')
        bid, ask = float(quote['bid']), float(quote['ask'])
        if not all(math.isfinite(x) and x > 0 for x in (bid, ask)) or bid > ask:
            _fail('quote_prices_invalid')
        return bid, ask

    def _resume_rollovers(self,quote_snapshot):
        emitted=[]
        for product,context in self.pending_rollovers.items():
            if context.get('roll_status') in ('emitted','expired'):
                continue
            life=self.close_lifecycles[context['close_lifecycle_id']]
            if life['status']!='completed' or self.strategy.get_pos(life['symbol']):
                continue
            if self.last_processed_day>=context['execution_day'] or self.queued_days:
                context['roll_status']='expired'
                context['blocked_reason']='signal_expired_no_historical_open'
                continue
            quote=quote_snapshot.get(context['vt_symbol']) if isinstance(quote_snapshot,dict) and 'symbol' not in quote_snapshot and 'vt_symbol' not in quote_snapshot else quote_snapshot
            if quote is None or quote.get('symbol',quote.get('vt_symbol'))!=context['vt_symbol']:
                continue
            clone,bar,sizing=self._current_sizing(context,self.broker_snapshot,self.confirmed_cash_state,quote)
            volume=min(context['previous_volume'],int(sizing['selected_volume']))
            if volume<=0:
                context['blocked_reason']=clone.open_block_reason or 'fresh_original_sizing_zero'
                continue
            state=self.strategy.states[product]
            self.strategy.current_bar_date=pd.Timestamp(context['bar'].datetime)
            self.engine.datetime=context['bar'].datetime
            self.current_receipt_hash=context['data_receipt_sha256']
            self.strategy._reset_intrabar_reservations()
            self.strategy._open_position(state,context['vt_symbol'],context['direction'],volume,bar,
                'rollover_reopen',context['history'],context['signal_data'],sizing_snapshot=sizing)
            state.risk_mode=context['risk_mode_override'] or state.risk_mode
            state.rollover_opened_today=self.strategy._bar_date(context['bar'])
            self.strategy._reserve_intrabar_entry(product,sizing,volume,count_active_position=False)
            self.strategy._apply_state_target(state)
            self.sizing_contexts[(context['vt_symbol'],context['direction'])]=deepcopy(context)
            start=len(self.engine.intents)
            self.strategy.rebalance_portfolio({context['vt_symbol']:bar})
            new=[x for x in self.engine.intents[start:] if x.get('offset')=='open']
            if len(new)!=1:
                _fail('rollover_reopen_intent_count_unproven')
            self.revision+=1
            context['roll_status']='emitted'
            context['reopen_intent_id']=new[0]['intent_id']
            emitted.extend(new)
        return emitted

    def _retry_closes(self, quote_snapshot):
        result = []
        for life in self.close_lifecycles.values():
            if life['status'] != 'retry_required':
                continue
            template = self.engine.order_intents[life['order_ids'][-1]]
            day = funding._parse(self.broker_snapshot['account'], 'weekly19.ctp-account.v1', 'ctp_account_callback')['trading_day']
            quote = quote_snapshot.get(life['symbol']) if isinstance(quote_snapshot, dict) and 'symbol' not in quote_snapshot and 'vt_symbol' not in quote_snapshot else quote_snapshot
            operational=dict(target_date=self.last_processed_day or template['target_date'],
                completed_target_date=self.last_processed_day or template['completed_target_date'],
                data_receipt_sha256=self.current_receipt_hash or template['data_receipt_sha256'],
                lifecycle_origin_signal_receipt=template.get('lifecycle_origin_signal_receipt',template['data_receipt_sha256']),
                lifecycle_origin_completed_target_date=template.get('lifecycle_origin_completed_target_date',template['completed_target_date']))
            if quote is None:
                result.append(dict(template, **operational, executable=False, requires_fresh_quote=True,
                    blocked_reason='pending_retry_quote_required', planned_volume=life['volume']-life['filled'],
                    volume=life['volume']-life['filled']))
                continue
            bid, ask = self._validate_quote(quote, life['symbol'], day)
            retry = dict(template, planned_volume=life['volume']-life['filled'], volume=life['volume']-life['filled'],
                trading_date=day,next_execution_day=day,
                **operational,
                state_generation=f"{template['position_epoch_id']}:{self.revision+1}",
                requires_funding_revision=self.confirmed_cash_state['revision'],
                broker_account_raw_sha256=self.broker_snapshot['account']['raw_sha256'],
                limit_price=ask if template['direction']=='long' else bid,
                price=ask if template['direction']=='long' else bid, requires_fresh_quote=False,
                quote_sha256=_hash(quote), executable=True, blocked_reason='', retry_of=template['intent_id'])
            retry['intent_id'] = _hash([template['intent_id'], self.broker_snapshot['account']['raw_sha256'], _hash(quote), len(life['order_ids'])])
            retry['signal_order_id'] = 'W19.' + retry['intent_id']
            retry['signal_identity'] = dict(template['signal_identity'], intent_id=retry['intent_id'],
                signal_order_id=retry['signal_order_id'], trading_date=day)
            self.engine.order_intents[retry['signal_order_id']] = deepcopy(retry)
            self.engine.order_filled[retry['signal_order_id']] = 0
            self.engine.intents.append(deepcopy(retry))
            life['order_ids'].append(retry['signal_order_id'])
            life['status'] = 'pending'
            self.revision+=1
            result.append(retry)
        return result

    def _accepted_scope(self):
        return dict(contracts=sorted(self.metadata['vt_symbols']),physical_columns=list(self.physical_frame.columns))

    def _input_prefix(self, cutoff, scope=None):
        key=(cutoff,_json(scope))
        if key in self._input_prefix_cache:
            return self._input_prefix_cache[key]
        physical = self.physical_frame.loc[self.physical_frame['date'].astype(str) <= cutoff].copy()
        if scope is not None:
            if (set(scope)!={'contracts','physical_columns'} or scope['contracts']!=sorted(set(scope['contracts']))
                    or not set(scope['contracts'])<=set(self.metadata['vt_symbols'])
                    or not set(scope['physical_columns'])<=set(physical.columns)):
                _fail('accepted_input_scope_invalid')
            physical=physical.loc[physical.vt_symbol.isin(scope['contracts']),scope['physical_columns']]
        physical = physical.sort_values(['vt_symbol','date']).reset_index(drop=True)
        mapping = {d:self.metadata['daily_mapping'][d] for d in sorted(self.metadata['daily_mapping']) if d<=cutoff}
        symbols = (scope['contracts'] if scope is not None else sorted({symbol for row in mapping.values() for symbol in row.values()} |
                         set(physical['vt_symbol'].astype(str))))
        specs = {field:{symbol:self.metadata.get(field,{}).get(symbol) for symbol in symbols}
                 for field in ('sizes','priceticks','margin_ratios','rates','slippages','source_symbol_by_contract')}
        digest=_hash(dict(calendar=[d for d in self.calendar if d<=cutoff],mapping=mapping,
                          physical=_encode(physical),specs=_encode(specs),products=self.metadata['product_symbols']))
        self._input_prefix_cache[key]=digest
        return digest

    def export_state(self):
        strategy = {k:v for k,v in vars(self.strategy).items() if k not in {'strategy_engine','_weekly19_runtime'}}
        engine = {k:v for k,v in vars(self.engine).items() if k != 'runtime'}
        runtime = {k:getattr(self,k) for k in ('confirmed_cash_state','broker_equity','broker_available','broker_snapshot',
            'open_block_reason','pending_broker_margin','admitted_ids','funding_recommendation','last_processed_day',
            'warmup_cursor','current_receipt_hash','days','fills','order_updates',
            'close_lifecycles','queued_days','open_contexts','sizing_contexts','pending_rollovers',
            'admission_contexts','position_identities','broker_order_bindings','child_batches','revision',
            'physical_epoch_state','physical_epoch_transitions','expired_signal_days','funding_replans') if hasattr(self,k)}
        shared=dict(weeks=self.weeks,weeks_sha256=_hash(_encode(self.weeks)))
        body = dict(schema='weekly19.runtime-state.v1', revision=self.revision,
            shared_inputs=dict(weeks=dict(calendar=list(self.calendar),sha256=shared['weeks_sha256'])),
            position_identities=deepcopy(self.position_identities),account_key=self.account, material_release_id=self.release,
            input_sha256=self.input_hash, input_cursor=max(self.last_processed_day,self.warmup_cursor),
            input_prefix_sha256=self._input_prefix(max(self.last_processed_day,self.warmup_cursor),self._accepted_scope()),
            accepted_scope=self._accepted_scope(),
            settings_sha256=self.settings_sha256,
            strategy=_pack_section(_encode(strategy,shared=shared)), engine=_pack_section(_encode(engine,shared=shared)),
            runtime=_encode(runtime,shared=shared), production_qualified=False)
        return dict(body, state_sha256=_state_digest(body))

    def _restore(self, saved):
        body = {k:v for k,v in saved.items() if k != 'state_sha256'}
        if saved.get('state_sha256') != _state_digest(body):
            _fail('state_checksum_mismatch')
        if any(saved.get(k) != v for k,v in dict(schema='weekly19.runtime-state.v1',account_key=self.account,
                material_release_id=self.release,settings_sha256=self.settings_sha256,
                production_qualified=False).items()):
            _fail('state_identity_or_input_mismatch')
        extended = saved.get('input_sha256') != self.input_hash
        if extended and saved.get('input_prefix_sha256') != self._input_prefix(saved.get('input_cursor',''),saved.get('accepted_scope')):
            _fail('accepted_input_prefix_changed')
        shared=None
        if 'shared_inputs' in saved:
            from weekly19_frozen.weekly_adapter import completed_weeks
            table=saved['shared_inputs']
            if set(table)!={'weeks'} or set(table['weeks'])!={'calendar','sha256'}:
                _fail('shared_calendar_table_invalid')
            old_calendar=table['weeks']['calendar']
            if (not isinstance(old_calendar,list) or old_calendar!=sorted(set(old_calendar))
                    or [d for d in old_calendar if d<=saved.get('input_cursor','')]!=
                       [d for d in self.calendar if d<=saved.get('input_cursor','')]):
                _fail('shared_calendar_prefix_changed')
            weeks=completed_weeks(old_calendar);digest=_hash(_encode(weeks))
            if digest!=table['weeks']['sha256']:_fail('shared_calendar_digest_mismatch')
            if digest==_hash(_encode(self.weeks)):weeks=self.weeks
            shared=dict(weeks=weeks,weeks_sha256=digest)
        current_ams = self.strategy.ams
        strategy = _decode(saved['strategy'],shared=shared)
        engine = _decode(saved['engine'],shared=shared)
        rt = _decode(saved['runtime'],shared=shared)
        if saved.get('revision') != rt.get('revision') or saved.get('position_identities') != rt.get('position_identities'):
            _fail('durable_revision_or_position_identity_mismatch')
        self.strategy.__dict__.clear()
        self.strategy.__dict__.update(strategy, strategy_engine=self.engine, _weekly19_runtime=self)
        self.engine.__dict__.clear()
        self.engine.__dict__.update(engine, runtime=self)
        self.__dict__.update(rt)
        self.child_batches=rt.get('child_batches',{})
        if extended:
            new_symbols=set(current_ams)-set(self.strategy.ams)
            self._validate_new_contract_history(saved,new_symbols)
            self.strategy.ams.update({k:v for k,v in current_ams.items() if k in new_symbols})
            for am in self.strategy.ams.values():
                am.weeks = self.weeks
            self.strategy.daily_mapping = deepcopy(self.metadata['daily_mapping'])
            self.strategy.available_trade_dates = sorted(pd.Timestamp(d) for d in self.metadata['daily_mapping'])
            self.strategy.vt_symbols = list(self.metadata['vt_symbols'])
            self.strategy.source_symbol_by_contract = deepcopy(self.metadata['source_symbol_by_contract'])
            self.engine.sizes = deepcopy(self.metadata['sizes'])
            self.engine.priceticks = deepcopy(self.metadata['priceticks'])
            self.engine.rates = deepcopy(self.metadata.get('rates',{}))
            self.engine.slippages = deepcopy(self.metadata.get('slippages',{}))
            self._prewarm_new_contract_history(saved,new_symbols)

    def _validate_new_contract_history(self,saved,symbols):
        if not symbols:return
        # Older v1 snapshots lack a declared scope; they cannot silently admit
        # retrospective contracts. Existing actor fields remain fully preserved.
        if 'accepted_scope' not in saved:_fail('new_contract_requires_accepted_scope')
        owned={s for s,v in self.strategy.pos_data.items() if v}
        owned|={s.contract_vt_symbol for s in self.strategy.states.values() if s.layers}
        owned|={p['vt_symbol'] for p in self.engine.order_intents.values()}
        owned|={c['vt_symbol'] for c in self.open_contexts.values()}
        owned|={c['vt_symbol'] for c in self.admission_contexts.values()}
        if owned&symbols:_fail('new_contract_previously_owned_or_signalled')
        admissions=self.metadata.get('new_contract_history_admissions',[])
        for symbol in symbols:
            selected=[a for a in admissions if a.get('vt_symbol')==symbol]
            if len(selected)!=1:_fail('new_contract_history_admission_required:'+symbol)
            row=selected[0]
            required={'schema','vt_symbol','contract_epoch_id','contract_yyyymm','listed_date','delisted_date',
                      'available_history_complete','source_sha256','metadata_sha256'}
            if not required<=set(row) or row['schema']!='weekly19.new-contract-history-admission.v1' or row['available_history_complete'] is not True:
                _fail('new_contract_history_admission_invalid:'+symbol)
            funding._sha(row['source_sha256']);funding._sha(row['metadata_sha256'])
            code,exchange=symbol.split('.');import re
            match=re.fullmatch(r'([A-Za-z]+)([0-9]{3,4})',code);month=row['contract_yyyymm']
            if (not isinstance(month,str) or not re.fullmatch(r'[0-9]{4}(0[1-9]|1[0-2])',month) or match is None
                    or month[-(3 if exchange=='CZCE' else 4):]!=match[2]
                    or row['contract_epoch_id']!=exchange+'.'+match[1].upper()+'.'+month):
                _fail('new_contract_physical_identity_invalid:'+symbol)
            if row['listed_date']:
                first=date.fromisoformat(row['listed_date'])
            elif row.get('listed_unknown') is True and row.get('available_history_ids_contiguous') is True:
                first=date.fromisoformat(row['observed_available_min'])
            else:_fail('new_contract_available_series_bounds_required:'+symbol)
            last=date.fromisoformat(row['delisted_date'])
            frame=self.physical_frame.loc[(self.physical_frame.vt_symbol==symbol)&(self.physical_frame.date<=saved['input_cursor'])]
            if frame.empty and first.isoformat()<=saved['input_cursor']:_fail('new_contract_completed_history_missing:'+symbol)
            if not frame.empty and (set(frame.contract_epoch_id)!={row['contract_epoch_id']} or frame.date.min()<first.isoformat()
                    or frame.date.max()>last.isoformat()):_fail('new_contract_history_lifecycle_mismatch:'+symbol)
            bars=self.metadata.get('new_contract_history_bars',{}).get(symbol)
            if not isinstance(bars,list):_fail('new_contract_actual_dto_history_required:'+symbol)
            supplied={pd.Timestamp(b.datetime).strftime('%Y-%m-%d'):b for b in bars
                      if pd.Timestamp(b.datetime).strftime('%Y-%m-%d')<=saved['input_cursor']}
            if len(supplied)!=sum(pd.Timestamp(b.datetime).strftime('%Y-%m-%d')<=saved['input_cursor'] for b in bars) or set(supplied)!=set(frame.date):
                _fail('new_contract_actual_dto_coverage_mismatch:'+symbol)
            for source in frame.itertuples():
                bar=supplied[str(source.date)]
                self._validate_bars({symbol:bar},expected_day=str(source.date))
                for field,attribute in [('open','open_price'),('high','high_price'),('low','low_price'),('close','close_price'),('volume','volume'),('close_oi','open_interest')]:
                    if not hasattr(source,field) or not math.isclose(float(getattr(source,field)),float(getattr(bar,attribute)),rel_tol=0,abs_tol=1e-9):
                        _fail('new_contract_actual_dto_value_mismatch:'+symbol)

    def _prewarm_new_contract_history(self,saved,symbols):
        for symbol in sorted(symbols):
            bars=[b for b in self.metadata['new_contract_history_bars'][symbol]
                  if pd.Timestamp(b.datetime).strftime('%Y-%m-%d')<=saved['input_cursor']]
            for bar in sorted(bars,key=lambda b:b.datetime):self.strategy.ams[symbol].update_bar(bar)
            if not bars:continue
            last=max(pd.Timestamp(b.datetime).strftime('%Y-%m-%d') for b in bars)
            self.physical_epoch_state[symbol]=dict(epoch=self.epoch_lookup[(symbol,last)],last_real_day=last)


def build_weekly19_runtime(settings_asset, metadata, session_calendar, physical_epoch_daily,
                           broker_snapshot, durable_state, confirmed_cash_state, *, clock=None, recovery_events=()):
    return Runtime(settings_asset, metadata, session_calendar, physical_epoch_daily,
                   broker_snapshot, durable_state, confirmed_cash_state, clock=clock, recovery_events=recovery_events)
