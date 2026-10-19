import sys,json
sys.path.insert(0,'/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian/research/lines/futures_trend_full_market_noai_one_lot/tools')
from vnpy.trader.setting import SETTINGS
SETTINGS['log.file']=False
import test_stage070_fractional_integration as f
import stage079_run_fractional_risk as final
from dataclasses import asdict
e,s,vt,b,o,l=f.FractionalRunnerIntegration().fixture(price=90,direction='short')
e.__class__=final.FullMarketDailyEngine;s.__class__=final.FeeStrategy
state=s.states['IC.CFFEX'];original=asdict(l.stage068_signal_risk_budget);b.volume=2
e.cross_delayed_orders()
assert not e.trades and e.active_limit_orders and s.get_target(vt)==-3 and state.layers
s._reconcile_state_with_position(state,0,b)
r=dict(reproduced=True,sequence='real_cross_delay_volume2_for_qty3_then_native_reconcile_actual0',actual_position=s.get_pos(vt),target=s.get_target(vt),active_order_count=len(e.active_limit_orders),layers_after_reconcile=len(state.layers),original_authorized_volume=original['authorized_volume'],original_snapshot_id=original['snapshot_id'],actual_fills=len(e.trades),receipt_survived_on_state=bool(state.layers))
assert r['layers_after_reconcile']==0 and r['active_order_count']==1 and r['target']==-3
print(json.dumps(r));open('/private/tmp/stage080_delayed_intent_repro.json','w').write(json.dumps(r,indent=2))
