"""Independent finite Stage028 composition fixture; no historical account replay."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[5]
TOOLS = ROOT / "research/lines/futures_trend_triple_screen/tools"
sys.path.insert(0, str(TOOLS))
sys.dont_write_bytecode = True
import stage022_run_c0_qualified_wait as prior


def main():
    with tempfile.TemporaryDirectory(prefix="stage028_independent_composition_") as temp:
        temp = Path(temp)
        prior.OUTPUT = temp / "runtime"
        prior.configure_runtime(temp / "shared")
        import pandas as pd
        import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as native
        from vnpy.trader.constant import Exchange
        from vnpy.trader.object import BarData
        from qmt_roll_portfolio_strategy import DailyEntryContext
        from stage028_ordered_engine import build_ordered_engine
        from stage028_ordered_strategy import build_ordered_strategy

        product, symbol = "AP.CZCE", "AP605.CZCE"
        day, signal, preparation = "2026-01-07", "2026-01-06", "2026-01-05"
        dates = [preparation, signal, day, "2026-01-08"]
        mapping = temp / "mapping.csv"
        pd.DataFrame([dict(date=value, continuous_symbol_vt=product,
                           main_contract_vt=symbol) for value in dates]).to_csv(mapping, index=False)
        universe = temp / "universe.csv"
        pd.DataFrame([dict(product_vt_symbol=product)]).to_csv(universe, index=False)

        def bar(value, opening, high, low, close):
            return BarData(symbol="AP605", exchange=Exchange.CZCE,
                datetime=datetime.fromisoformat(value), gateway_name="FIXTURE",
                open_price=opening, high_price=high, low_price=low, close_price=close)

        checks = []
        for direction in (1, -1):
            for mode in ("survives", "samebar_stop_retry_fails"):
                qualified = []
                Engine = build_ordered_engine(native.Stage847StopRetryEngine,
                    lambda engine, item, actual: qualified.append(item["intent_id"]))
                target = Engine({})
                target.capital = 150000.
                target.datetime = datetime.fromisoformat(day)
                target.priceticks = {symbol: 1.}
                target.sizes = {symbol: 10}
                target.rates = {symbol: .001}
                target.slippages = {symbol: 1.}
                fill, stop = (111., 91.) if direction == 1 else (89., 109.)
                close = 112. if direction == 1 else 88.
                raw = bar(day, 100., 130., 80., close)
                target.bars = {symbol: raw}
                Strategy = build_ordered_strategy(native.QmtRollPortfolioStrategyStage847C9StopRetry,
                    None, {}, {})
                strategy = Strategy(target, "independent-composition", [symbol], dict(
                    mapping_csv_path=str(mapping), product_universe_csv_path=str(universe),
                    capital_base=150000., enable_ai_product_pool_filter=False,
                    enable_selection_pairwise_v2=False, enable_supply_demand_headwind_filter=False,
                    enable_ai_path_damage_risk_discount=False, trailing_stop_enabled=False,
                    enable_profit_giveback_stop=False, atr_2x_mid_stop_enabled=False,
                    enable_stage847_half_r_stop_retry=True, stage847_stop_retry_r=.5,
                    stage847_max_retries=1, enable_stage827_intraday_c2_stop=True))
                strategy.trading = True
                target.strategy = strategy
                for observed, following, native_signal in ((preparation, signal, None),
                    (signal, day, "long_case1a" if direction == 1 else "short_case1a")):
                    observation = strategy.ts_machine.on_close(product=product, contract=symbol,
                        day=observed, next_day=following, high=110., low=90., tick=1.,
                        weekly_ready=True, weekly_direction=direction, weekly_asof="2026-01-02",
                        fi_ready=True, fi2=-direction, eligible=True, position_open=False,
                        native_signal=native_signal)
                item = {**observation["intent"], "rank": 1, "plan": dict(volume=3,
                    target_contract=symbol, target_bar=bar(signal, 100., 110., 90., 100.),
                    history=pd.DataFrame({"close": [100.]}),
                    signal_data={"risk_mode": "regular"},
                    direction="long" if direction == 1 else "short",
                    signal="long_case1a" if direction == 1 else "short_case1a",
                    sizing=dict(selected_volume=3, stop_price=stop, risk_per_contract=90.,
                        margin_per_contract=100., margin_ratio=.1, risk_multiplier=1.))}
                strategy.ts_pending_intents = [item]
                grid = native.s827.execution.session_minutes(symbol, day, strategy.available_trade_dates)
                frame = pd.DataFrame(dict(bar_datetime=grid, open=100., high=100., low=100., close=100.))
                index = list(grid).index(pd.Timestamp(day + "T11:00:00"))
                if direction == 1:
                    first = [110., 113., 108., 111.] if mode == "survives" else [95., 125., 94., 110.]
                    second = [111., 114., 108., 112.] if mode == "survives" else [100., 112., 99., 111.]
                    remainder = [112., 114., 108., 112.]
                else:
                    first = [90., 92., 88., 89.] if mode == "survives" else [105., 106., 75., 90.]
                    second = [89., 92., 86., 88.] if mode == "survives" else [100., 101., 88., 89.]
                    remainder = [88., 92., 86., 88.]
                for offset, values in ((0, first), (1, second)):
                    frame.loc[index + offset, ["open", "high", "low", "close"]] = values
                frame.loc[index + 2:, ["open", "high", "low", "close"]] = remainder
                frame.loc[:index - 1, "low" if direction == 1 else "high"] = 80. if direction == 1 else 130.
                strategy.stage827_minute_by_symbol = {symbol: frame}
                before = frame.copy(deep=True)
                target.cross_delayed_orders()
                trades = list(target.trades.values())
                assert qualified == [item["intent_id"]]
                assert trades[0].price == fill and trades[0].volume == 3
                assert trades[0].signal_datetime == item["plan"]["target_bar"].datetime
                assert str(trades[0].signal_order_id) in strategy.ts_conditional_orders
                assert trades[0].vt_orderid == trades[0].signal_order_id
                assert pd.Timestamp(trades[0].datetime) == grid[index]
                assert strategy.ts_pending_intents == [] and len(strategy.ts_fill_audit) == 1
                assert target.active_limit_orders == {} and strategy.active_orderids == set()
                assert len(target.trade_usage_rows) == len(trades)
                assert frame.equals(before), "temporary after-open view mutated original minutes"
                expected_cost = sum(t.volume * 10 * (t.price * .001 + 1.) for t in trades)
                assert abs(strategy.trade_costs_total - expected_cost) < 1e-9
                expected_balance = 150000. + sum(
                    (1 if t.direction == native.s827.Direction.LONG else -1) * t.volume * 10 * (close - t.price)
                    - t.volume * 10 * (t.price * .001 + 1.) for t in trades)
                assert abs(strategy.settled_balance - expected_balance) < 1e-9
                state = strategy.states[product]
                if mode == "survives":
                    assert len(trades) == 1 and len(state.layers) == 1
                    assert strategy.get_pos(symbol) == direction * 3
                    assert strategy.get_target(symbol) == direction * 3
                    layer = state.layers[0]
                    assert layer.entry_price == fill and layer.entry_price_synced
                    # Native state stores compact YYYYMMDD; the semantic date
                    # must remain u rather than the actual D execution date.
                    assert layer.entry_date == signal.replace("-", "") and state.entry_date == signal.replace("-", "")
                    assert layer._stage827_signal_order_id == trades[0].signal_order_id
                    assert layer.highest_price == layer.lowest_price == fill
                    context = DailyEntryContext(product, state, symbol, raw, raw,
                        direction * 3, pd.DataFrame({"low": [80.], "high": [130.]}), {})
                    strategy._build_daily_env_gate_snapshot([context])
                    assert context.target_bar is not raw and raw.low_price == 80. and raw.high_price == 130.
                    assert context.history.iloc[0]["low"] == 80.
                    assert context.target_bar.open_price == fill
                    assert (context.target_bar.low_price, context.target_bar.high_price) == ((108., 114.) if direction == 1 else (86., 92.))
                    strategy._update_dynamic_stops(state, context.target_bar, context.history)
                    assert strategy._process_layer_stops(state, context.target_bar) == ""
                    assert len(state.layers) == 1 and strategy.get_target(symbol) == direction * 3
                    assert len(target.limit_orders) == 1, "target application sent duplicate order"
                else:
                    expected = [111., 101., 111., 101.] if direction == 1 else [89., 99., 89., 99.]
                    assert [t.price for t in trades] == expected
                    assert pd.Timestamp(trades[1].datetime) == grid[index]
                    assert pd.Timestamp(trades[2].datetime) == grid[index + 1]
                    assert pd.Timestamp(trades[3].datetime) == grid[index + 1]
                    assert state.layers == [] and strategy.get_pos(symbol) == strategy.get_target(symbol) == 0
                    assert len(target.limit_orders) == 1
                    assert strategy.stage847_stop_retry_event_count == 1
                checks.append(dict(direction=direction, mode=mode,
                    trade_prices=[t.price for t in trades], trade_count=len(trades),
                    cost=expected_cost, settled_balance=strategy.settled_balance,
                    remaining_layers=len(state.layers), target=strategy.get_target(symbol),
                    signal_date=signal, actual_entry=str(trades[0].datetime),
                    real_order_count=len(target.limit_orders), original_minutes_unchanged=True))
        payload = dict(status="passed_finite_native_composition_fixture", checks=checks,
            financial_replays=0, historical_market_replays=0, network_calls=0,
            production_qualified=False)
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
