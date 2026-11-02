from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd
from . import base827 as s827
BROKER_MARGIN_MULTIPLIER=1.65
PROJECTED_BROKER10_MARGIN_TO_EQUITY_CAP=1.0


class QmtRollPortfolioStrategyStage830C2Broker10MarginCap(s827.QmtRollPortfolioStrategyStage827C2):
    enable_stage830_broker10_margin_cap: bool = False
    stage830_broker_margin_multiplier: float = BROKER_MARGIN_MULTIPLIER
    stage830_projected_broker10_margin_to_equity_cap: float = PROJECTED_BROKER10_MARGIN_TO_EQUITY_CAP

    parameters = s827.QmtRollPortfolioStrategyStage827C2.parameters + [
        "enable_stage830_broker10_margin_cap",
        "stage830_broker_margin_multiplier",
        "stage830_projected_broker10_margin_to_equity_cap",
    ]
    variables = s827.QmtRollPortfolioStrategyStage827C2.variables + [
        "stage830_margin_cap_reduce_count",
        "stage830_margin_cap_block_count",
    ]

    def __init__(self, strategy_engine, strategy_name: str, vt_symbols: list[str], setting: dict) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage830_margin_cap_events: list[dict[str, Any]] = []
        self.stage830_margin_cap_reduce_count: int = 0
        self.stage830_margin_cap_block_count: int = 0

    def _calculate_entry_sizing(
        self,
        vt_symbol: str,
        direction: str,
        bar: Any,
        history: pd.DataFrame,
        signal_data: dict[str, Any],
        risk_mode_override: str | None = None,
        entry_context: str = "flat_entry",
        apply_env_gate: bool = True,
        active_positions_before: int | None = None,
        correlation_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        sizing = dict(
            super()._calculate_entry_sizing(
                vt_symbol,
                direction,
                bar,
                history,
                signal_data,
                risk_mode_override=risk_mode_override,
                entry_context=entry_context,
                apply_env_gate=apply_env_gate,
                active_positions_before=active_positions_before,
                correlation_snapshot=correlation_snapshot,
            )
        )
        before = max(0, int(sizing.get("selected_volume") or 0))
        equity = float(getattr(self, "estimated_equity", 0.0) or sizing.get("sizing_equity") or self.base_capital or 0.0)
        reserved_margin = float(sizing.get("reserved_margin_before") or 0.0)
        margin_per_contract = float(sizing.get("margin_per_contract") or 0.0)
        multiplier = float(self.stage830_broker_margin_multiplier)
        cap_ratio = float(self.stage830_projected_broker10_margin_to_equity_cap)
        projected_before = (
            (reserved_margin + margin_per_contract * before) * multiplier / equity if equity > 0 else np.inf
        )
        sizing.update(
            {
                "stage830_broker10_margin_cap_enabled": int(bool(self.enable_stage830_broker10_margin_cap)),
                "stage830_broker10_margin_cap_applied": 0,
                "stage830_broker10_margin_cap_reason": "disabled",
                "stage830_broker10_margin_cap_ratio": cap_ratio,
                "stage830_broker_margin_multiplier": multiplier,
                "stage830_margin_cap_selected_volume_before": before,
                "stage830_margin_cap_selected_volume_after": before,
                "stage830_projected_broker10_margin_to_equity_before": projected_before,
                "stage830_projected_broker10_margin_to_equity_after": projected_before,
                "stage830_margin_cap_max_affordable_volume": before,
            }
        )
        if not bool(self.enable_stage830_broker10_margin_cap):
            return sizing
        if entry_context == "reverse_entry":
            sizing["selected_volume"] = 0
            sizing["stage830_broker10_margin_cap_applied"] = 1
            sizing["stage830_broker10_margin_cap_reason"] = "reverse_entry_fail_closed"
            sizing["stage830_margin_cap_selected_volume_after"] = 0
            sizing["stage830_projected_broker10_margin_to_equity_after"] = (
                reserved_margin * multiplier / equity if equity > 0 else np.inf
            )
            sizing["stage830_margin_cap_max_affordable_volume"] = 0
            if before > 0:
                self.stage830_margin_cap_reduce_count += 1
                self.stage830_margin_cap_block_count += 1
                product_vt_symbol = self.source_symbol_by_contract.get(vt_symbol, self._product_vt_symbol(vt_symbol))
                event = {
                    "datetime": bar.datetime,
                    "date": pd.Timestamp(bar.datetime).normalize().date().isoformat(),
                    "vt_symbol": vt_symbol,
                    "product_vt_symbol": product_vt_symbol,
                    "contract_vt_symbol": vt_symbol,
                    "position_direction": direction,
                    "direction": direction,
                    "offset": "RiskSizing",
                    "price": float(getattr(bar, "close_price", 0.0) or 0.0),
                    "volume": before,
                    "signal": str(signal_data.get("signal", "")),
                    "entry_context": entry_context,
                    "selected_volume_before": before,
                    "selected_volume_after": 0,
                    "reduced_volume": before,
                    "estimated_equity": equity,
                    "reserved_margin_before": reserved_margin,
                    "margin_per_contract": margin_per_contract,
                    "broker_margin_multiplier": multiplier,
                    "cap_ratio": cap_ratio,
                    "max_affordable_volume": 0,
                    "projected_broker10_margin_to_equity_before": projected_before,
                    "projected_broker10_margin_to_equity_after": sizing[
                        "stage830_projected_broker10_margin_to_equity_after"
                    ],
                    "reason": "broker10_margin_cap_reverse_entry_fail_closed",
                }
                self.stage830_margin_cap_events.append(event)
                diagnostics = getattr(self, "trade_event_diagnostics", None)
                if diagnostics is not None:
                    diagnostics.append(event)
            return sizing
        if entry_context != "flat_entry":
            sizing["stage830_broker10_margin_cap_reason"] = "not_flat_entry"
            return sizing
        if before <= 0:
            sizing["stage830_broker10_margin_cap_reason"] = "zero_selected_volume"
            return sizing
        if equity <= 0 or margin_per_contract <= 0 or multiplier <= 0 or cap_ratio <= 0:
            sizing["stage830_broker10_margin_cap_reason"] = "invalid_inputs"
            return sizing

        max_projected_margin = equity * cap_ratio / multiplier
        remaining_margin_budget = max_projected_margin - reserved_margin
        max_affordable = int(np.floor(remaining_margin_budget / margin_per_contract)) if remaining_margin_budget > 0 else 0
        after = min(before, max(0, max_affordable))
        if 0 < after < self.min_position_size:
            after = 0
        projected_after = (
            (reserved_margin + margin_per_contract * after) * multiplier / equity if equity > 0 else np.inf
        )
        reason = "within_broker10_margin_cap"
        if after < before:
            reason = "broker10_margin_cap_reduce" if after > 0 else "broker10_margin_cap_block"
            self.stage830_margin_cap_reduce_count += 1
            if after <= 0:
                self.stage830_margin_cap_block_count += 1
            product_vt_symbol = self.source_symbol_by_contract.get(vt_symbol, self._product_vt_symbol(vt_symbol))
            event = {
                "datetime": bar.datetime,
                "date": pd.Timestamp(bar.datetime).normalize().date().isoformat(),
                "vt_symbol": vt_symbol,
                "product_vt_symbol": product_vt_symbol,
                "contract_vt_symbol": vt_symbol,
                "position_direction": direction,
                "direction": direction,
                "offset": "RiskSizing",
                "price": float(getattr(bar, "close_price", 0.0) or 0.0),
                "volume": before - after,
                "signal": str(signal_data.get("signal", "")),
                "entry_context": entry_context,
                "selected_volume_before": before,
                "selected_volume_after": after,
                "reduced_volume": before - after,
                "estimated_equity": equity,
                "reserved_margin_before": reserved_margin,
                "margin_per_contract": margin_per_contract,
                "broker_margin_multiplier": multiplier,
                "cap_ratio": cap_ratio,
                "max_affordable_volume": max_affordable,
                "projected_broker10_margin_to_equity_before": projected_before,
                "projected_broker10_margin_to_equity_after": projected_after,
                "reason": reason,
            }
            self.stage830_margin_cap_events.append(event)
            diagnostics = getattr(self, "trade_event_diagnostics", None)
            if diagnostics is not None:
                diagnostics.append(event)

        sizing["selected_volume"] = after
        sizing["stage830_broker10_margin_cap_applied"] = int(after < before)
        sizing["stage830_broker10_margin_cap_reason"] = reason
        sizing["stage830_margin_cap_selected_volume_after"] = after
        sizing["stage830_projected_broker10_margin_to_equity_after"] = projected_after
        sizing["stage830_margin_cap_max_affordable_volume"] = max_affordable
        return sizing
