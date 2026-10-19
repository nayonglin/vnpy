import sys,json
from copy import deepcopy
sys.path.insert(0,'/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian/research/lines/futures_trend_full_market_noai_one_lot/tools')
from vnpy.trader.setting import SETTINGS
SETTINGS['log.file']=False
from test_stage085_pending_open_lifecycle import Final086PendingOpenLifecycleTests as Fixture
from qmt_roll_portfolio_strategy import ProductState
h=Fixture();e,s,vt,b,o,l,state=h.defer();avt='IF202112.CFFEX';prod='IF.CFFEX';ab=deepcopy(b);ab.symbol='IF202112';ab.vt_symbol=avt;ab.open_price=ab.high_price=ab.low_price=ab.close_price=100.
s.source_symbol_by_contract[avt]=prod;s.pos_data[avt]=5;s.set_target(avt,0);e.sizes[avt]=10;e.bars[avt]=ab;s.states[prod]=ProductState(product_vt_symbol=prod,contract_vt_symbol=avt,direction='long',layers=[]);s.pending_close_lots[avt]=[dict(volume=5,direction='long',entry_price=150,provisional_exit_price=100)]
s.risk_cluster_map='IC.CFFEX=shared;IF.CFFEX=shared';s.estimated_equity=10000.;s.base_capital=10000.;s.portfolio_drawdown_pct=.25;s.cluster_unrealized_pnl=s._estimate_unrealized_pnl_by_cluster({vt:b,avt:ab});s.cluster_margin_usage=s._estimate_margin_usage_by_cluster({vt:b,avt:ab});s.total_margin_in_use=sum(s.cluster_margin_usage.values())
pre=dict(s.cluster_unrealized_pnl);before=s._risk_cluster_heat_pressure_fields('shared',enabled=True)
s._apply_rollover_released_risk_snapshot({'rollover_released_margin':500.,'rollover_released_cluster':'shared','rollover_released_cluster_margin':500.,'rollover_released_cluster_unrealized_pnl':-2500.})
after=s._risk_cluster_heat_pressure_fields('shared',enabled=True)
r=dict(actual_position=s.get_pos(avt),pending_close=5,actual_pnl_function=s._estimate_unrealized_pnl_by_cluster({vt:b,avt:ab}),cached_before=pre,cached_after=s.cluster_unrealized_pnl,heat_before=before,heat_after=after)
print(json.dumps(r,indent=2));open('/private/tmp/stage088_rollover_pnl_cache_probe.json','w').write(json.dumps(r,indent=2))
