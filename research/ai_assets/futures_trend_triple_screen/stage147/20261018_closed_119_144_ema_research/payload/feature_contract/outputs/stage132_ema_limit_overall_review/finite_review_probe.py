"""Two bounded review probes; no runner, provider, model or financial replay."""
from copy import copy
from pathlib import Path
import json
import sys
import tempfile
from types import SimpleNamespace

sys.dont_write_bytecode = True
TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))
import test_stage127_ema_limit_strategy as fixture

result = {"fixture_only": True, "financial_replays": 0, "model_calls": 0,
          "provider_calls": 0, "network_calls": 0, "cases": []}

# The author's wrong-L checks call sizing directly. Exercise the complete native
# planner/snapshot with a lawful real u bar and an independently lower L instead.
with tempfile.TemporaryDirectory(prefix="stage132_invalid_L_") as folder:
    contracts, products = fixture.CONTRACTS[:1], fixture.PRODUCTS[:1]
    features = fixture.lookup(contracts)
    features[(fixture.DAY, contracts[0])].update(ema=95., ema_prev=95.)
    formal = fixture.runtime.capture_formal_profile(fixture.s901,
        fixture.metadata(contracts, products), fixture.pd.Timestamp(fixture.runtime.START),
        fixture.pd.Timestamp(fixture.runtime.END))
    profile, engine_cls = fixture.adapter().build_ema_account_profile(formal,
        fixture.NATIVE, fixture.ENGINE, weekly=fixture.Weekly(),
        fi={(fixture.DAY, contracts[0]): dict(ready=True, fi2=-1.)},
        next_days={fixture.DAY: fixture.NEXT}, ema_lookup=features,
        qualify=lambda *args: None)
    strategy, engine = fixture.instantiate(profile["strategy_cls"], engine_cls,
        fixture.settings(Path(folder), contracts=contracts, products=products), contracts=contracts)
    engine.bars = {contracts[0]: fixture.bar(contracts[0], low=95.)}
    strategy.on_bars(engine.bars)
    snapshot = strategy.entry_candidate_snapshots[-1]
    assert snapshot["planned_entry_price"] == 94.
    assert snapshot["selected_volume"] == 0
    assert snapshot["ema_limit_reject_reason"] == "invalid_stop_side"
    assert not strategy.ts_pending_intents and not engine.get_all_trades()
    assert strategy.pending_margin_reservation == 0.
    assert strategy.ts_machine._products[products[0]].setup is not None
    result["cases"].append(dict(name="wrong_L_full_planner_schema", limit=94., stop=95.,
        selected_volume=0, pending_intents=0, fills=0, reserved_margin=0., setup_retained=True))

# A short intrabar entry could otherwise inherit favorable pre-fill low95 into
# its layer's lifetime minimum. Exercise the real native holding update too.
with tempfile.TemporaryDirectory(prefix="stage132_short_holding_") as folder:
    strategy, engine = fixture.native_fixture(Path(folder), direction=-1, stop=104.)
    item = strategy.ts_pending_intents[0]
    symbol = item["contract"]
    raw = fixture.install_minutes(strategy, engine, [(97., 101., 95., 96., 1000.)])
    before = raw[symbol].copy(deep=True)
    engine.cross_delayed_orders()
    assert [trade.price for trade in engine.get_all_trades()] == [100.]
    assert not strategy.stage847_stop_retry_events
    daily = SimpleNamespace(current_pos=strategy.get_pos(symbol),
        product_vt_symbol=item["product"], target_contract=symbol,
        target_bar=copy(engine.bars[symbol]), actual_bar=copy(engine.bars[symbol]))
    strategy._build_daily_env_gate_snapshot([daily])
    assert daily.target_bar.low_price == 100.
    strategy._update_dynamic_stops(strategy.states[item["product"]], daily.target_bar,
                                   item["plan"]["history"])
    assert strategy.states[item["product"]].layers[0].lowest_price == 100.
    fixture.pd.testing.assert_frame_equal(raw[symbol], before)
    result["cases"].append(dict(name="short_actual_holding_consumer", fill=100.,
        raw_first_low=95., private_lifetime_low=daily.target_bar.low_price,
        actual_layer_low=strategy.states[item["product"]].layers[0].lowest_price,
        native_initial_fills=1, retry_events=0, raw_unchanged=True))

path = Path(__file__).with_name("finite_probe_evidence.json")
path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(result, ensure_ascii=False))
