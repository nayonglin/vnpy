"""One finite real 847/B/028 accounting composition; no market replay or model."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/lines/futures_trend_triple_screen/tools"))
sys.dont_write_bytecode = True
import stage022_run_c0_qualified_wait as runtime


def main():
    with tempfile.TemporaryDirectory(prefix="stage035_independent_native_") as temp:
        temp = Path(temp)
        runtime.OUTPUT = temp / "runtime"
        runtime.configure_runtime(temp / "shared")
        import pandas as pd
        import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as native
        from vnpy.trader.constant import Exchange
        from vnpy.trader.object import BarData
        from stage028_ordered_engine import build_ordered_engine
        from stage035_b_ts_strategy import build_b_strategy
        import stage036_run_b_ts_checkpoint as runner

        symbol, product = "AP605.CZCE", "AP.CZCE"
        signal, day = "2026-01-06", "2026-01-07"
        dates = ["2026-01-05", signal, day, "2026-01-08"]
        mapping, universe = temp / "mapping.csv", temp / "universe.csv"
        pd.DataFrame([dict(date=d, continuous_symbol_vt=product, main_contract_vt=symbol)
                      for d in dates]).to_csv(mapping, index=False)
        pd.DataFrame([dict(product_vt_symbol=product)]).to_csv(universe, index=False)

        def bar(stamp, opening, high, low, close, volume=100., oi=100.):
            return BarData(symbol="AP605", exchange=Exchange.CZCE,
                datetime=pd.Timestamp(stamp).to_pydatetime(), gateway_name="FIXTURE",
                open_price=opening, high_price=high, low_price=low, close_price=close,
                volume=volume, open_interest=oi)

        class Weekly:
            def __init__(self, direction):
                self.direction, self.calls = direction, []
            def get(self, stamp, market):
                self.calls.append((stamp, market))
                return dict(ready=True, direction=self.direction, weekly_asof="2026-01-02")

        observations = []
        for direction, unknown in ((1, False), (-1, False), (1, True)):
            qualified = []
            Engine = build_ordered_engine(native.Stage847StopRetryEngine,
                lambda target, item, actual: qualified.append(item["intent_id"]))
            target = Engine({})
            target.capital = 100000.
            target.datetime = datetime.fromisoformat(signal)
            target.priceticks, target.sizes = {symbol: 1.}, {symbol: 10}
            target.rates, target.slippages = {symbol: .001}, {symbol: 1.}
            high, low, trigger, stop = ((110., 99., 111., 99.) if direction == 1
                                       else (101., 90., 89., 101.))
            ubar = bar(signal, 100., high, low, 100., 300., 200.)
            target.bars = {symbol: ubar}
            weekly = Weekly(direction)
            fi = {(signal, symbol): dict(ready=not unknown, fi2=-direction if not unknown else None)}
            Strategy = build_b_strategy(native.QmtRollPortfolioStrategyStage847C9StopRetry,
                weekly, fi, {signal: day})
            strategy = Strategy(target, "independent-real-B", [symbol], dict(
                mapping_csv_path=str(mapping), product_universe_csv_path=str(universe),
                capital_base=100000., fixed_size=0, min_risk_per_trade=0.,
                short_entry_enabled=True, max_position_size=500,
                max_capital_usage_ratio=1., max_single_trade_capital_usage_ratio=1.,
                risk_ratio_volume_open_interest_surge=.012,
                enable_ai_product_pool_filter=False, enable_selection_pairwise_v2=False,
                enable_supply_demand_headwind_filter=False, enable_ai_path_damage_risk_discount=False,
                ma5_extreme_filter_enabled=True, short_ma5_slope_filter_enabled=True,
                wick_chop_filter_enabled=True, enable_stage830_broker10_margin_cap=True,
                stage830_broker_margin_multiplier=1.65,
                stage830_projected_broker10_margin_to_equity_cap=1.,
                enable_stage847_half_r_stop_retry=True, stage847_stop_retry_r=.5,
                stage847_max_retries=1, enable_stage827_intraday_c2_stop=True))
            strategy.trading = True
            target.strategy = strategy
            # Seed only synthetic indicator bars; never load_data/run_backtesting.
            am = strategy.ams[symbol]
            for index in range(am.size):
                close = 80. + 20. * index / am.size if direction == 1 else 120. - 20. * index / am.size
                stamp = datetime.fromisoformat(signal) - timedelta(days=am.size-index)
                am.update_bar(bar(stamp, close, close+1., close-1., close,
                                  300. if index == am.size-1 else 100.,
                                  200. if index == am.size-1 else 100.))
            assert am.inited
            generated = []
            def no_native_signal(manager, history):
                # Only native alpha generation is replaced with a literal
                # absence (or an unknown-day native trap). All downstream
                # filters/OI/sizing/planner/reservation/accounting are real.
                row = strategy._signal_result("long_case1a" if unknown else "",
                    direction == 1, direction == -1, 100., 100., 100., 100.,
                    "regular", False, rsi_value=50.)
                generated.append(row)
                return row
            strategy._generate_signal = no_native_signal
            reserve_calls = []
            original_reserve = strategy._reserve_intrabar_entry
            def reserve(product_vt, sizing, quantity, *, count_active_position):
                reserve_calls.append((product_vt, quantity, sizing["margin_per_contract"], count_active_position))
                return original_reserve(product_vt, sizing, quantity,
                    count_active_position=count_active_position)
            strategy._reserve_intrabar_entry = reserve
            # This is the real full on_bars product loop, not a planner stub.
            strategy.on_bars({symbol: ubar})
            assert len(weekly.calls) == len(strategy.ts_decision_audit) == len(generated) == 1
            assert generated[0]["signal"] == ("long_case1a" if unknown else "")
            assert all(row["arm"] == "B_TS" and not row["baseline_fallback"] for row in strategy.ts_decision_audit)
            if unknown:
                assert strategy.ts_pending_intents == [] and reserve_calls == []
                assert target.limit_orders == {} and target.trades == {} and strategy.states[product].layers == []
                observations.append(dict(direction=direction, unknown=True, native_trap_cleared=True,
                    decisions=1, reserves=0, orders=0, fills=0))
                continue
            assert len(strategy.ts_pending_intents) == 1, dict(
                decision=strategy.ts_decision_audit, snapshots=strategy.entry_candidate_snapshots,
                machine=strategy.ts_machine._products, filter=generated)
            item = strategy.ts_pending_intents[0]
            sizing = item["plan"]["sizing"]
            label = "long_triple_screen" if direction == 1 else "short_triple_screen"
            assert item["arm"] == "B_TS" and item["native_signal"] == item["plan"]["signal"] == label
            assert item["plan"]["signal_data"]["risk_mode"] == "volume_open_interest_surge"
            assert (item["trigger"], sizing["stop_price"], sizing["risk_per_contract"], sizing["contracts_by_risk"]) == (trigger, stop, 120., 10)
            assert item["plan"]["volume"] == sizing["selected_volume"] == sizing["b_ts_final_budget_volume_after"] == 10
            assert sizing["margin_per_contract"] == trigger
            assert reserve_calls == [(product, 10, trigger, True)]
            assert strategy.pending_margin_reservation == 10*trigger
            assert target.limit_orders == {} and target.trades == {} and strategy.states[product].layers == []
            snapshot = strategy.entry_candidate_snapshots[-1]
            assert snapshot["arm"] == "B_TS" and snapshot["signal_close"] == 100.
            assert snapshot["planned_entry_price"] == trigger and snapshot["b_ts_final_budget_predicted_risk_T"] == 1200.
            assert not strategy._can_open_short_signal("short_other")
            # Freeze evidence before the real after-open accounting mutates live diagnostics.
            frozen_before = deepcopy(item["plan"]["sizing"])
            target.datetime = datetime.fromisoformat(day)
            target.bars = {symbol: bar(day, 100., 130., 70., 100.)}
            grid = native.s827.execution.session_minutes(symbol, day, strategy.available_trade_dates)
            frame = pd.DataFrame(dict(bar_datetime=grid, open=100., high=100., low=100., close=100.))
            first = list(grid).index(pd.Timestamp(day + "T11:00:00"))
            values = ([100., 120., 100., 110.], [105., 112., 104., 111.]) if direction == 1 else (
                [100., 100., 80., 90.], [95., 96., 88., 89.])
            for offset, prices in enumerate(values):
                frame.loc[first+offset, ["open", "high", "low", "close"]] = prices
            original_minutes = frame.copy(deep=True)
            strategy.stage827_minute_by_symbol = {symbol: frame}
            target.cross_delayed_orders()
            trades = target.get_all_trades()
            wanted = [111., 105., 111., 105.] if direction == 1 else [89., 95., 89., 95.]
            assert [trade.price for trade in trades] == wanted
            assert [pd.Timestamp(trade.datetime) for trade in trades] == [grid[first], grid[first], grid[first+1], grid[first+1]]
            assert len(qualified) == 1 and len(strategy.ts_fill_audit) == 1
            assert strategy.ts_fill_audit[0]["arm"] == "B_TS"
            assert strategy.ts_fill_audit[0]["b_ts_final_budget_predicted_risk_T"] == 1200.
            assert item["plan"]["sizing"] == frozen_before
            assert strategy.ts_machine._products[product].setup is None
            assert len(target.limit_orders) == 1 and len(reserve_calls) == 1
            assert strategy.get_pos(symbol) == strategy.get_target(symbol) == 0
            assert strategy.states[product].layers == [] and frame.equals(original_minutes)
            actual = runner.actual_trade_identities(trades)
            captured = [dict(trade_id=t.vt_tradeid,vt_symbol=t.vt_symbol,direction=t.direction.value,
                offset=t.offset.value,price=float(t.price),volume=float(t.volume),
                engine_datetime=str(t.datetime),execution_datetime=str(t.execution_datetime),
                trading_date=str(t.trading_date),exit_reason=getattr(t,"exit_reason","")) for t in trades]
            capture = dict(trades=captured, usage=deepcopy(target.trade_usage_rows))
            assert "signal_datetime" not in capture["usage"][1]
            clock, usage = runner.build_execution_clock(capture, actual)
            assert len(clock) == 4 and clock.signal_order_id.nunique() == 1
            assert clock.signal_datetime.tolist() == [signal + "T00:00:00"]*4
            assert all(row["intraday_episode_id"] == trades[0].vt_tradeid for row in actual[1:])
            expected_cost = sum(t.volume*10*(t.price*.001+1.) for t in trades)
            assert abs(strategy.trade_costs_total-expected_cost) < 1e-9
            observations.append(dict(direction=direction, unknown=False, native_signal_absent=True,
                B_label=label,T=trigger,S=stop,rho_T=120.,final_q=10,decisions=1,reserves=1,
                real_orders=len(target.limit_orders),real_fill_prices=wanted,
                actual_signal_identity_and_synthetic_parent_checked=True,
                predicted_risk_preserved=1200.,original_minutes_unchanged=True,cost=expected_cost))
        result = dict(status="passed_limited_real_B_native_composition",cases=observations,
            financial_replays=0,network_calls=0,model_inference=0,production_qualified=False,
            scope="real on_bars/planner/T-pricing/804-stop/final-budget/single-reserve plus native 827 fills and B-runner clock; only native alpha generation is an explicit fixture literal")
        path = Path(__file__).with_name("native_b_composition_result.json")
        path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
        print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
