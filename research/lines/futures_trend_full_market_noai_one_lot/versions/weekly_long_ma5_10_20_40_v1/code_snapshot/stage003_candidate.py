"""Isolated Stage037 research delta. No official universe builders or production I/O."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[4]
FROZEN_SITE=Path('/Users/mac/Documents/Codex/fian-research-20261014/.py311/lib/python3.11/site-packages')
if FROZEN_SITE.is_dir():sys.path.append(str(FROZEN_SITE))
sys.path.insert(0,str(ROOT/'examples/portfolio_backtesting'))
from analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine import QmtRollPortfolioStrategyStage847C9StopRetry
from qmt_roll_official_candidate_stage847_c9_config import _build_official_candidate_stage847_c9_overrides
from qmt_roll_official_stage037_ruleset_config import apply_stage037_ruleset

CAPITAL=1_000_000
SHORT_SIGNALS=frozenset({'short_case1a','short_case2','short_case3'})


def candidate_overrides(universe_path: Path) -> dict:
    # The pure internal builder takes already-selected inputs and does not create
    # the legacy 19-product universe or rebuild any AI eligibility assets.
    overrides=apply_stage037_ruleset(_build_official_candidate_stage847_c9_overrides(universe_path,Path('/unused/no_ai_eligibility.csv')))
    overrides.update(account_capital=CAPITAL,c3_capital=CAPITAL,capital_base=CAPITAL,
        product_universe_csv_path=str(universe_path),fixed_size=1,min_position_size=1,max_position_size=1,
        enable_ai_product_pool_filter=False,ai_product_pool_eligibility_path='',
        enable_selection_pairwise_v2=False,enable_selection_pairwise_v2_catastrophic_veto=False,
        enable_selection_pairwise_v2_catastrophic_hard_filter=False,enable_selection_pairwise_v2_volume_tilt=False,
        enable_add_position=False,enable_donchian_add_position=False,enable_post_entry_quality_add=False,
        stage827_require_complete_minutes=True)
    return overrides


class FullMarketNoAIOneLot(QmtRollPortfolioStrategyStage847C9StopRetry):
    def _can_open_short_signal(self,signal: str) -> bool:
        return signal in SHORT_SIGNALS

    def _resolve_actual_position(self,state,target_contract,bars):
        # Sparse history cannot erase a broker-style position fact.
        held=[vt for vt,qty in self.pos_data.items() if qty and self.source_symbol_by_contract.get(vt)==state.product_vt_symbol]
        if len(held)>1:raise RuntimeError('multiple_actual_contracts_for_product')
        if held:
            vt=held[0]
            return vt,int(self.get_pos(vt)),bars.get(vt)
        return super()._resolve_actual_position(state,target_contract,bars)

    def _count_active_positions(self):
        held={self.source_symbol_by_contract[vt] for vt,qty in self.pos_data.items() if qty}
        return len(held|self.pending_active_products)

    def _pending_actual_close(self,state):
        vt=state.contract_vt_symbol
        qty=abs(int(self.get_pos(vt))) if vt else 0
        pending=sum(int(x.get('volume',0)) for x in getattr(self,'pending_close_lots',{}).get(vt,[]))
        return qty>0 and pending>=qty

    def _reconcile_state_with_position(self,state,current_pos,bar):
        if current_pos and self._pending_actual_close(state):return
        return super()._reconcile_state_with_position(state,current_pos,bar)

    def _close_position_when_target_unavailable(self,product_vt,*,state,target_contract,bars,reason):
        vt,qty,_=self._resolve_actual_position(state,target_contract,bars)
        pending=sum(int(x.get('volume',0)) for x in getattr(self,'pending_close_lots',{}).get(vt,[]))
        if qty and pending>=abs(qty):
            state.contract_vt_symbol=vt
            self.set_target(vt,0)
            return
        return super()._close_position_when_target_unavailable(product_vt,state=state,target_contract=target_contract,bars=bars,reason=reason)

    def _handle_rollover(self,state,target_contract,bars):
        if self._pending_actual_close(state):
            self.set_target(state.contract_vt_symbol,0)
            return
        return super()._handle_rollover(state,target_contract,bars)

    def _estimate_equity(self,bars):
        # Execution-only quotes may value existing positions, never indicators.
        values=dict(bars)
        cached=getattr(self.strategy_engine,'bars',{})
        held=set(getattr(self,'equity_start_positions',{}))|{vt for vt,q in self.pos_data.items() if q}
        for vt in held:
            if vt in cached:values[vt]=cached[vt]
        return super()._estimate_equity(values)

    def _apply_rollover_released_risk_snapshot(self,snapshot):
        super()._apply_rollover_released_risk_snapshot(snapshot)
        actual=self._actual_margin_by_cluster(getattr(self.strategy_engine,'bars',{}))
        self.total_margin_in_use=max(self.total_margin_in_use,sum(actual.values()))
        for cluster,margin in actual.items():self.cluster_margin_usage[cluster]=max(self.cluster_margin_usage.get(cluster,0.0),margin)

    def _actual_margin_by_cluster(self,bars):
        usage={}
        cached=getattr(self.strategy_engine,'bars',{})
        for vt,qty in self.pos_data.items():
            if not qty:continue
            bar=bars.get(vt) or cached.get(vt)
            if bar is None:raise RuntimeError('actual_position_margin_unknown:'+vt)
            product=self.source_symbol_by_contract[vt]
            cluster=self._risk_cluster_for_symbol(product)
            margin=abs(qty)*float(bar.close_price)*self.get_size(vt)*self._margin_ratio_for_symbol(vt)
            usage[cluster]=usage.get(cluster,0.0)+margin
        return usage

    def _estimate_margin_usage(self,bars):
        return max(super()._estimate_margin_usage(bars),sum(self._actual_margin_by_cluster(bars).values()))

    def _estimate_margin_usage_by_cluster(self,bars):
        usage=super()._estimate_margin_usage_by_cluster(bars)
        for cluster,margin in self._actual_margin_by_cluster(bars).items():usage[cluster]=max(usage.get(cluster,0.0),margin)
        return usage


def research_fee(meta: dict, *, price: float, volume: int, offset: str, same_day: bool) -> float:
    """Static disclosed fee schedule; no claim of historical daily fee accuracy."""
    field='fee_open' if offset=='open' else ('fee_close_today' if same_day else 'fee_close')
    fee=float(meta[field])
    if fee < 0:raise ValueError('negative commission')
    if meta['fee_method']=='by_volume':return fee*volume
    if meta['fee_method']=='by_money':return fee*price*float(meta['size'])*volume
    raise ValueError(f"unsupported fee method: {meta['fee_method']}")
