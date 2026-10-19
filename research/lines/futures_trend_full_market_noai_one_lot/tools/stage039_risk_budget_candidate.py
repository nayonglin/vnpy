"""Research-only native risk budget with a strict one-lot cap and signal receipt.

All native sizing, stop, environment, streak, margin and broker gates run first.
The final guard can only reduce selected volume; it never restores a rejected lot.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

from stage003_candidate import FullMarketNoAIOneLot, candidate_overrides as fixed_candidate_overrides


def one_lot_budget_allows(risk_per_contract: Any, target_risk_amount: Any) -> bool:
    """Exact inclusive comparison, with no minimum-one fallback or tolerance."""
    if isinstance(risk_per_contract, bool) or isinstance(target_risk_amount, bool):
        return False
    try:
        risk, budget = float(risk_per_contract), float(target_risk_amount)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(risk) and math.isfinite(budget) and risk > 0 and budget > 0 and risk <= budget


def candidate_overrides(universe_path: Path, product_count: int = 93) -> dict:
    if isinstance(product_count, bool) or int(product_count) != product_count or product_count <= 0:
        raise ValueError('product_count_must_be_positive_integer')
    return {**fixed_candidate_overrides(universe_path), 'fixed_size':0,
            'min_position_size':1, 'max_position_size':1,
            'max_concurrent_positions':int(product_count)}


@dataclass(frozen=True)
class SignalRiskBudgetSnapshot:
    snapshot_id: str
    contract_vt_symbol: str
    product_vt_symbol: str
    direction: str
    signal: str
    signal_datetime: str
    entry_context: str
    risk_mode: str
    target_risk_amount: float
    risk_per_contract: float
    stop_price: float
    risk_ratio: float
    risk_multiplier: float
    portfolio_overheat_cooldown_scale: float
    directional_30d_risk_boost_multiplier: float
    limited_balance: float
    min_risk_per_trade: float
    max_risk_per_trade: float
    effective_capital_usage_ratio: float
    sizing_equity: float
    single_trade_capital_limit: float
    reserved_margin_before: float


class NativeRiskBudgetSizingMixin:
    """Cooperative mixin: put before an existing research FeeStrategy in the MRO."""
    def _assert_stage039_policy(self):
        if self.fixed_size != 0 or self.max_position_size != 1:
            raise ValueError('stage039_requires_native_budget_and_max_one')

    def _calculate_entry_sizing(
        self, vt_symbol, direction, bar, history, signal_data,
        risk_mode_override=None, entry_context='flat_entry', apply_env_gate=True,
        active_positions_before=None, correlation_snapshot=None,
    ):
        self._assert_stage039_policy()
        sizing = dict(super()._calculate_entry_sizing(
            vt_symbol, direction, bar, history, signal_data,
            risk_mode_override=risk_mode_override, entry_context=entry_context,
            apply_env_gate=apply_env_gate, active_positions_before=active_positions_before,
            correlation_snapshot=correlation_snapshot,
        ))
        before = max(0, int(sizing.get('selected_volume') or 0))
        passed = one_lot_budget_allows(sizing.get('risk_per_contract'), sizing.get('risk_amount'))
        sizing.update(
            selected_volume=min(1, before) if passed else 0,
            stage039_native_selected_volume=before,
            stage039_budget_gate_enabled=1,
            stage039_budget_gate_passed=int(passed),
            stage039_target_risk_amount=sizing.get('risk_amount'),
            stage039_one_lot_risk_amount=sizing.get('risk_per_contract'),
            stage039_budget_gate_reason='within_original_budget' if passed else 'invalid_or_exceeded_original_budget',
        )
        return sizing

    def _open_position(self, state, contract_vt_symbol, direction, volume, bar, signal,
                       history, signal_data, sizing_snapshot=None):
        self._assert_stage039_policy()
        # Native _open_position uses max(1, volume); never let zero reach it.
        if isinstance(volume, bool) or volume != 1:
            return
        sizing = sizing_snapshot
        if sizing is None:
            sizing = self._calculate_entry_sizing(contract_vt_symbol,direction,bar,history,signal_data)
        if sizing.get('selected_volume') != 1 or not one_lot_budget_allows(sizing.get('risk_per_contract'),sizing.get('risk_amount')):
            return
        sequence = int(getattr(self, '_stage039_signal_budget_sequence', 0)) + 1
        receipt = SignalRiskBudgetSnapshot(
            snapshot_id=f'{self.strategy_name}:{contract_vt_symbol}:{direction}:{sequence}',
            contract_vt_symbol=contract_vt_symbol,
            product_vt_symbol=state.product_vt_symbol, direction=direction, signal=signal,
            signal_datetime=bar.datetime.isoformat(),
            entry_context=str(sizing['entry_context']), risk_mode=str(sizing['risk_mode']),
            target_risk_amount=float(sizing['risk_amount']), risk_per_contract=float(sizing['risk_per_contract']),
            stop_price=float(sizing['stop_price']), risk_ratio=float(sizing['risk_ratio']),
            risk_multiplier=float(sizing['risk_multiplier']),
            portfolio_overheat_cooldown_scale=float(sizing['portfolio_overheat_cooldown_scale']),
            directional_30d_risk_boost_multiplier=float(sizing['directional_30d_risk_boost_multiplier']),
            limited_balance=float(sizing['limited_balance']), min_risk_per_trade=float(self.min_risk_per_trade),
            max_risk_per_trade=float(self.max_risk_per_trade),
            effective_capital_usage_ratio=float(sizing['effective_capital_usage_ratio']),
            sizing_equity=float(sizing['sizing_equity']),
            single_trade_capital_limit=float(sizing['single_trade_capital_limit']),
            reserved_margin_before=float(sizing['reserved_margin_before']),
        )
        prior_ids = {id(layer) for layer in state.layers}
        result = super()._open_position(state,contract_vt_symbol,direction,volume,bar,signal,
                                      history,signal_data,sizing_snapshot=sizing)
        created = [layer for layer in state.layers if id(layer) not in prior_ids]
        if len(created) != 1:
            raise RuntimeError('stage039_pending_layer_identity_ambiguous')
        created[0].stage039_signal_risk_budget = receipt
        self._stage039_signal_budget_sequence = sequence
        return result


class FullMarketNativeRiskBudgetOneLot(NativeRiskBudgetSizingMixin, FullMarketNoAIOneLot):
    pass
