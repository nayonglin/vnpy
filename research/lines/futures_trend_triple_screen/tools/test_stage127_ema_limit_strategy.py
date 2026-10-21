"""Finite real native fixtures for the independent EMA limit adapter."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta
import importlib
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
import stage022_run_c0_qualified_wait as runtime
_RUNTIME = tempfile.TemporaryDirectory(prefix="stage131_native_ema_")
_OLD_OUTPUT = runtime.OUTPUT
try:
    runtime.OUTPUT = Path(_RUNTIME.name)
    runtime.configure_runtime(Path(_RUNTIME.name) / "shared")
finally:
    runtime.OUTPUT = _OLD_OUTPUT

import pandas as pd
import joblib
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as native
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
from vnpy.trader.constant import Exchange
from vnpy.trader.object import BarData
from stage065_pairwise_off_policy import OFF_SETTINGS

NATIVE = native.QmtRollPortfolioStrategyStage847C9StopRetry
ENGINE = native.Stage847StopRetryEngine
DAY, NEXT = "2026-01-06", "2026-01-07"
PRODUCTS = ["AP.CZCE", "au.SHFE", "rb.SHFE"]
CONTRACTS = ["AP605.CZCE", "au2606.SHFE", "rb2605.SHFE"]


class Weekly:
    def __init__(self, direction=1):
        self.direction = direction

    def get(self, day, product):
        return dict(ready=True, direction=self.direction, weekly_asof="2026-01-02")


def bar(contract, stamp=DAY, opening=100., high=101., low=95., close=100.):
    name, exchange = contract.split(".")
    return BarData(symbol=name, exchange=Exchange(exchange), datetime=pd.Timestamp(stamp).to_pydatetime(),
        gateway_name="EMA_FIXTURE", open_price=opening, high_price=high, low_price=low,
        close_price=close, volume=300., open_interest=200.)


def metadata(contracts=CONTRACTS, products=PRODUCTS):
    return dict(vt_symbols=list(contracts), product_symbols=list(products),
        rates={c:.001 for c in contracts}, slippages={c:1. for c in contracts},
        sizes={c:10 for c in contracts}, priceticks={c:1. for c in contracts},
        margin_ratios={c:.1 for c in contracts})


def settings(root, *, contracts=CONTRACTS, products=PRODUCTS):
    mapping, universe = root / "mapping.csv", root / "universe.csv"
    pd.DataFrame([dict(date=d, continuous_symbol_vt=p, main_contract_vt=c)
        for d in ("2026-01-05", DAY, NEXT, "2026-01-08") for p,c in zip(products,contracts)]).to_csv(mapping,index=False)
    pd.DataFrame(dict(product_vt_symbol=products)).to_csv(universe,index=False)
    return dict(mapping_csv_path=str(mapping), product_universe_csv_path=str(universe),
        **OFF_SETTINGS, capital_base=100000., fixed_size=0, min_risk_per_trade=0.,
        stop_loss_pct=.1, risk_ratio_volume_open_interest_surge=.44, risk_ratio_of_total_assets=.44,
        max_position_size=500, max_concurrent_positions=3, max_capital_usage_ratio=.025,
        max_single_trade_capital_usage_ratio=1., enable_ai_product_pool_filter=False,
        enable_supply_demand_headwind_filter=False, enable_ai_path_damage_risk_discount=False,
        enable_stage830_broker10_margin_cap=True, stage830_broker_margin_multiplier=1.65,
        stage830_projected_broker10_margin_to_equity_cap=1.,
        enable_stage847_half_r_stop_retry=True, stage847_stop_retry_r=.5, stage847_max_retries=1,
        enable_stage827_intraday_c2_stop=True)


def instantiate(cls, engine_cls, setting, *, contracts=CONTRACTS):
    engine = engine_cls({})
    engine.capital = setting["capital_base"]
    engine.datetime = datetime.fromisoformat(DAY)
    meta = metadata(contracts)
    for name in ("sizes", "priceticks", "rates", "slippages"):
        setattr(engine, name, meta[name])
    engine.bars = {c:bar(c) for c in contracts}
    strategy = cls(engine, "finite-ema-limit", list(contracts), setting)
    engine.strategy = strategy
    engine.output = lambda message: None
    strategy.trading = True
    strategy.ema_limit_run_id = "fixture-only"
    for c in contracts:
        am = strategy.ams[c]
        for index in range(am.size):
            close = 70.+24.*index/am.size
            am.update_bar(bar(c, datetime.fromisoformat(DAY)-timedelta(days=am.size-index),
                             close, close+1, close-1, close))
    strategy._generate_signal = lambda manager,history: strategy._signal_result(
        "", True, False, 100.,100.,100.,100.,"regular",False,rsi_value=50.)
    return strategy, engine


def lookup(contracts=CONTRACTS):
    return {(DAY,c):dict(asof=DAY,contract=c,ready=True,ema=101.,ema_prev=101.,
        mean_down=1.,mean_up=1.,positive_down_count=2,positive_up_count=2,
        valid_ema_count=26,segment_start="2025-11-01",source_bindings={}, execution_tick=1.)
        for c in contracts}


def adapter():
    return importlib.import_module("stage127_ema_limit_strategy")


def native_fixture(root, *, direction=1, stop=95., multiple=False):
    """New tests' tiny native constructor; never calls prepare or a runner."""
    contracts,products=(CONTRACTS,PRODUCTS) if multiple else (CONTRACTS[:1],PRODUCTS[:1])
    setting=settings(root,contracts=contracts,products=products)
    setting.update(risk_ratio_volume_open_interest_surge=.1,risk_ratio_of_total_assets=.1,
        short_entry_enabled=True,ma5_extreme_filter_enabled=False,
        short_ma5_slope_filter_enabled=False,wick_chop_filter_enabled=False)
    features=lookup(contracts)
    if direction==-1:
        for feature in features.values():
            feature.update(ema=99.,ema_prev=99.)
    module=adapter()
    formal=runtime.capture_formal_profile(s901,metadata(contracts,products),
        pd.Timestamp(runtime.START),pd.Timestamp(runtime.END))
    profile,engine_cls=module.build_ema_account_profile(formal,NATIVE,ENGINE,weekly=Weekly(direction),
        fi={(DAY,c):dict(ready=True,fi2=-direction) for c in contracts},next_days={DAY:NEXT},
        ema_lookup=features,qualify=lambda *args:None)
    strategy,engine=instantiate(profile["strategy_cls"],engine_cls,setting,contracts=contracts)
    engine.bars={c:bar(c,high=101. if direction==1 else stop,
                      low=stop if direction==1 else 99.) for c in contracts}
    strategy.on_bars(engine.bars)
    engine.datetime=datetime.fromisoformat(NEXT)
    engine.bars={c:bar(c,NEXT,opening=100.,high=130.,low=70.,close=100.) for c in contracts}
    return strategy,engine


def install_minutes(strategy,engine,rows, *, unfilled=False):
    execution=native.s827.execution
    frames={}
    for index,symbol in enumerate(engine.bars):
        grid=execution.session_minutes(symbol,NEXT,strategy.available_trade_dates)
        frame=pd.DataFrame(dict(bar_datetime=grid,open=100.,high=100.,low=100.,close=100.,volume=1000.))
        for row_index,values in enumerate(rows if index==0 or not unfilled else [(101.,102.,99.,100.,1.)]):
            frame.loc[row_index,["open","high","low","close","volume"]]=values
        frames[symbol]=frame
    strategy.stage827_minute_by_symbol=frames
    return frames


class EmaLimitStrategyTests(unittest.TestCase):
    def test_real_limit_budget_off_identity_and_reservation(self):
        # Break caught: wrong-side abs acceptance, close-based margin/risk,
        # recycled gross, planner-time/double reserve, model access or B owner.
        self.assertIsNotNone(importlib.util.find_spec("stage127_ema_limit_strategy"),
                             "missing independent native EMA adapter")
        module = adapter()
        formal = runtime.capture_formal_profile(s901, metadata(), pd.Timestamp(runtime.START),pd.Timestamp(runtime.END))
        before = asdict(formal["spec"])
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            stack.enter_context(patch.object(joblib,"load",side_effect=AssertionError("model load forbidden")))
            import qmt_roll_ai_selection_pairwise_runtime as pairwise
            stack.enter_context(patch.object(pairwise.SelectionPairwiseRuntimeModel,"__init__",
                                            side_effect=AssertionError("model runtime forbidden")))
            profile,engine_cls = module.build_ema_account_profile(formal,NATIVE,ENGINE,weekly=Weekly(),
                fi={(DAY,c):dict(ready=True,fi2=-1.) for c in CONTRACTS},next_days={DAY:NEXT},
                ema_lookup=lookup(),qualify=lambda *args:None)
            self.assertEqual(asdict(formal["spec"]),before)
            self.assertEqual(profile["spec"].overrides,{**formal["spec"].overrides,**OFF_SETTINGS})
            self.assertEqual(profile["research_mechanism"],"stage124_ema_limit_v1")
            self.assertFalse(profile["financial_ready"])
            self.assertNotIn("research_arm",profile)
            strategy,engine = instantiate(profile["strategy_cls"],engine_cls,settings(Path(folder)))
            # L differs from the raw close: a close-priced implementation would
            # produce different risk, margin and admitted quantities.
            engine.bars={c:bar(c,close=99.) for c in CONTRACTS}
            self.assertIn(NATIVE,type(strategy).__mro__)
            reservations=[]
            reserve=strategy._reserve_intrabar_entry
            def record(product,sizing,quantity,*,count_active_position):
                reservations.append((product,quantity))
                return reserve(product,sizing,quantity,count_active_position=count_active_position)
            strategy._reserve_intrabar_entry=record
            strategy.on_bars(engine.bars)
            audit=strategy.ema_limit_final_budget_audit
            self.assertEqual([x["ema_limit_final_budget_volume_before"] for x in audit],[22,22,22])
            self.assertEqual([x["ema_limit_final_budget_volume_after"] for x in audit],[22,3,0])
            self.assertEqual([x["ema_limit_final_budget_gross_margin_before"] for x in audit],[0.,2200.,4400.])
            self.assertEqual(reservations,[(PRODUCTS[0],22),(PRODUCTS[1],3)])
            self.assertEqual(strategy.pending_margin_reservation,2500.)
            self.assertEqual([x["plan"]["volume"] for x in strategy.ts_pending_intents],[22,3])
            self.assertEqual(engine.trades,{})
            for item in strategy.ts_pending_intents:
                sizing=item["plan"]["sizing"]
                self.assertEqual((item["limit_price"],sizing["stop_price"],sizing["risk_per_contract"],
                                  sizing["margin_per_contract"]),(100.,95.,50.,100.))
                self.assertEqual(item["mechanism_id"],module.MECHANISM_ID)
                self.assertEqual(item["plan"]["target_bar"].close_price,99.)
                self.assertNotIn("B_TS",str(item))
                self.assertFalse(any(key.startswith("b_ts_") for key in sizing))
            original = strategy._entry_stop_price
            for direction, stop in (("long",100.),("long",101.),("short",100.),("short",99.)):
                strategy._entry_stop_price=lambda *args, value=stop, **kwargs:value
                strategy.ema_limit_price_by_key[(DAY,CONTRACTS[0],direction)]=100.
                with patch.object(module,"_calculate_trigger_priced_entry",side_effect=AssertionError("abs reached")):
                    rejected=strategy._calculate_entry_sizing(CONTRACTS[0],direction,bar(CONTRACTS[0]),
                        pd.DataFrame(),dict(signal=direction+"_triple_screen",risk_mode="regular"))
                self.assertEqual(rejected["selected_volume"],0)
                self.assertEqual(rejected["ema_limit_reject_reason"],"invalid_stop_side")
            strategy._entry_stop_price=original
            native_add=strategy._calculate_entry_sizing(CONTRACTS[0],"long",bar(CONTRACTS[0],close=99.),
                strategy.ts_pending_intents[0]["plan"]["history"],
                dict(signal="long_triple_screen",risk_mode="regular"),entry_context="add")
            self.assertEqual(native_add["margin_per_contract"],99.)
            self.assertFalse(any(key.startswith("ema_limit_") for key in native_add))


if __name__ == "__main__":
    unittest.main()
