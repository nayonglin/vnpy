"""Read-only evidence checks for a failed replay. Never import/run a strategy."""
from pathlib import Path
from datetime import datetime
import ast
import hashlib
import json
import math
import subprocess
import sys

import pandas as pd

ROOT=Path(__file__).resolve().parents[4]
BASE=ROOT/'examples/stock_backtesting/qmt357'
NEW=ROOT/'examples/stock_backtesting/qmt357_commit4ac255e'
STAGE=Path(__file__).parent
SOURCE=Path('/tmp/qmt-commit-4ac255e.WqwflV')
DOWNLOAD=BASE/'data/downloads/history_20191001_20260928'
SNAP=BASE/'data/history_201910_20260928'

def j(path): return json.loads(path.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def equal(a,b): assert math.isclose(float(a),float(b),rel_tol=1e-12,abs_tol=1e-10),(a,b)

provenance=j(NEW/'provenance.json')
git_bytes=subprocess.check_output(['git','--git-dir',str(SOURCE/'repository.git'),'show',
    provenance['commit']+':'+provenance['source_file']])
assert hashlib.sha256(git_bytes).hexdigest()==provenance['source_sha256']==sha(SOURCE/provenance['source_file'])
base_manifest=j(BASE/'outputs/fixed_2020_20260924_v2data/manifest.json')
base_core={name:sha(BASE/name) for name in ['config.py','signals.py','strategy.py','engine.py']}
assert all(value==base_manifest['code_sha256'][name] for name,value in base_core.items())
config_tree=ast.parse((NEW/'config.py').read_text())
cls=next(x for x in config_tree.body if isinstance(x,ast.ClassDef) and x.name=='BacktestSettings')
defaults={x.target.id:ast.literal_eval(x.value) for x in cls.body if isinstance(x,ast.AnnAssign)}
assert defaults==dict(max_positions=3,position_size=.32,day_position_size=.9,stop_loss_pct=.02,stop_profit_pct=.45)
diagnostic=j(STAGE/'20260928_1915_stage008_failure_diagnostic.json')
for name,value in defaults.items(): equal(value,diagnostic['settings'][name])
assert diagnostic['status']=='FAILED_REPLAY_DIAGNOSTIC_ONLY_NOT_FULL_PERIOD_RESULT'
assert diagnostic['failure_date']=='2020-12-31' and diagnostic['last_completed_date']=='2020-12-30'
assert not diagnostic['published_full_period_results']
assert not (NEW/'outputs/fixed_2020_20260928_commit4ac255e_v1').exists()
snapshot=j(SNAP/'manifest.json')
assert sha(SNAP/'panel.parquet')==snapshot['panel_sha256']==diagnostic['snapshot_sha256']
assert sha(DOWNLOAD/'source_panel.parquet')==snapshot['source_sha256']
panel=pd.read_parquet(SNAP/'panel.parquet')
panel['date']=pd.to_datetime(panel.date)
part=panel[(panel.vt_symbol=='000001.SZSE') & panel.date.between('2020-12-28','2020-12-31')].set_index('date')
assert len(part)==4
failure=part.loc['2020-12-31']
for name,value in diagnostic['failure_row'].items():
    if name=='date': assert pd.Timestamp(value)==pd.Timestamp('2020-12-31')
    elif isinstance(value,(float,int)): equal(value,failure[name])
    else: assert value==failure[name]
entry=diagnostic['failed_symbol_trades']
assert len(entry)==1
entry=entry[0]
assert entry['direction']=='buy' and entry['shares']==4000
assert entry['signal_date']=='2020-12-28T00:00:00' and entry['date']=='2020-12-29T00:00:00'
calendar=pd.DatetimeIndex(panel[panel.vt_symbol=='000300.SSE'].date.sort_values())
assert calendar.get_loc(pd.Timestamp(entry['date']))-calendar.get_loc(pd.Timestamp(entry['signal_date']))==1
cfg=diagnostic['settings']
price=float(part.loc['2020-12-29','open'])+cfg['slippage_per_share']
notional=price*entry['shares']
fee=max(cfg['minimum_commission'],notional*cfg['commission_rate'])
for a,b in [(price,entry['price']),(notional,entry['turnover']),(fee,entry['commission']),
            (cfg['slippage_per_share']*entry['shares'],entry['slippage'])]: equal(a,b)
assert len(diagnostic['held_at_failure'])==1
holding=diagnostic['held_at_failure']['000001.SZSE']
assert holding['shares']==entry['shares'] and holding['buy_date']=='2020-12-29'
equal(holding['entry_cost'],notional+fee)
equal(holding['buy_price'],price)
equal(holding['stop_profit'],price*1.45)
equal(holding['adj_factor'],part.loc['2020-12-30','adj_factor'])
assert holding['dividends']==0 and all(part.cash_dividend==0) and all(part.split_ratio==1)
peak=price
stop=price*.98
trailing=[]
for dt in ['2020-12-29','2020-12-30']:
    close=float(part.loc[dt,'close'])
    peak=max(peak,close)
    if close>price:
        profit=(peak-price)/price
        locked=next((lock for threshold,lock in [(.4,.15),(.3,.1),(.2,.06),(.1,.03)] if profit>=threshold),0)
        stop=max(stop,price*(1+locked))
    trailing.append(dict(date=dt,peak=peak,stop=stop,observed_close=close))
assert len(diagnostic['failed_symbol_trailing'])==len(trailing)
for actual,expected in zip(diagnostic['failed_symbol_trailing'],trailing):
    assert actual['date'][:10]==expected['date']
    equal(actual['peak'],expected['peak']); equal(actual['new_stop'],expected['stop'])
    equal(actual['observed_close'],expected['observed_close'])
equal(holding['stop_loss'],stop)
# This is the exact disclosed accounting rejection predicate, not a replay.
unexplained=(not math.isclose(float(failure.adj_factor),holding['adj_factor'],rel_tol=1e-9)
             and failure.cash_dividend==0 and failure.split_ratio==1)
assert unexplained
oldf=BASE/'data/downloads/history_20191001_20260924/raw/factors_sz.000001_2026-09-24.parquet'
newf=DOWNLOAD/'raw/factors_sz.000001_2026-09-28.parquet'
assert sha(oldf)==sha(newf)
factors=pd.read_parquet(newf)
before=factors[factors.dividOperateDate=='2020-05-28'].iloc[0]
after=factors[factors.dividOperateDate=='2020-12-31'].iloc[0]
assert before.foreAdjustFactor==after.foreAdjustFactor=='0.781647'
equal(float(before.backAdjustFactor),holding['adj_factor'])
equal(float(after.backAdjustFactor),failure.adj_factor)
raw=pd.read_parquet(DOWNLOAD/'raw/bars_sz.000001_2020-01-01_2020-12-31.parquet').set_index('date')
equal(raw.loc['2020-12-31','preclose'],raw.loc['2020-12-30','close'])
for dt in part.index:
    day=str(dt.date())
    for field in ['open','high','low','close','volume']:
        equal(raw.loc[day,field],part.loc[dt,field])
for module in ('engine.py','strategy.py','config.py','run.py','runtime.py'):
    ast.parse((NEW/module).read_text())
assert not any(n.startswith(('vnpy','qmt_roll','qmt_range')) for n in sys.modules)
payload=dict(status='PASS_SCOPE_AND_FAIL_CLOSED_DECLINE_FULL_PERFORMANCE',
    reviewed_at=datetime.now().astimezone().isoformat(),source_commit=provenance['commit'],
    source_blob_sha256=provenance['source_sha256'],source_blob_verified_in_bare_git=True,
    baseline_core_sha256=base_core,new_current_code_sha256={p.name:sha(p) for p in sorted(NEW.glob('*.py'))},
    diagnostic_sha256=sha(STAGE/'20260928_1915_stage008_failure_diagnostic.json'),
    snapshot_sha256=snapshot['panel_sha256'],source_sha256=snapshot['source_sha256'],
    settings_verified=defaults,failure_date=diagnostic['failure_date'],last_completed_date=diagnostic['last_completed_date'],
    independent_entry=dict(price=price,shares=entry['shares'],notional=notional,commission=fee,
                           total_cost=notional+fee,signal_date=entry['signal_date'],date=entry['date']),
    independent_trailing=trailing,guard_predicate_true=bool(unexplained),
    factor_before=holding['adj_factor'],factor_after=float(failure.adj_factor),
    factor_delta_pct=(float(failure.adj_factor)/holding['adj_factor']-1)*100,
    fore_factor_unchanged=before.foreAdjustFactor,raw_preclose_equals_previous_close=True,
    old_and_new_factor_file_sha256=sha(newf),full_result_target_absent=True,
    processed_trades_99_is_producer_counter_not_independently_rebuilt=True,
    declared_limits=['No full trade/daily logs saved for aborted replay; other98 executions and entire partial ledger not reconstructed.',
                     'Failure diagnostic lacks execution-time code hashes; current hashes captured now, not backfilled into diagnostic.',
                     'No complete-period result, annual statistics, alpha, or official source correction conclusion.'])
out=Path(__file__).with_suffix('.json')
out.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(payload,ensure_ascii=False,indent=2))
