import hashlib,json,os,subprocess,ast
from pathlib import Path
R=Path('/Users/mac/.codex/worktrees/weekly19-official-20261031/fian');D=R/'research/lines/futures_weekly_short_ma_slope_gate/stages';PY=str(R/'.py311/bin/python')
expected={'qmt_roll_weekly19_runtime.py':'5a7a911af89a1319fa9b7ed752e6f42aef67bb9fbb5d7faf3678b2c5a76e6d1c','qmt_roll_weekly19_data.py':'3cf9ab9d1822390dfd32e1d8cb5bdfe7f8dc3bf621d1e05da1b375e6ad730eb5','qmt_roll_weekly19_data_update.py':'e2afe228f787b7a694cdb78b7fcd075eb3079f90f4acf6ec26edc63cd01fa4d2','qmt_roll_weekly19_broker_evidence.py':'9ac93d98cbcde43652941239e2284ce69f1b6dcdbabddfcfd9b11524c8f6bed1','qmt_roll_weekly19_warm_evidence.py':'4e306946c842c74111b6bbb1ee0d0206feb09b6ad43edf57078c3de8b079886f','qmt_roll_official_live_execution_ledger.py':'4cb3671209c9cc6363cee53fb085a714779f6f9f6c61fb2f4cb0d85353559f66'}
names=['test_weekly19_runtime.py','test_weekly19_data.py','test_weekly19_data_update.py','test_weekly19_strategy_equivalence.py','test_weekly19_broker_evidence.py','test_weekly19_warm_evidence.py','test_weekly19_external_funding.py','test_official_live_execution_ledger_cycles.py','test_stage174_query_bundle.py','test_official_live_broker_account_snapshot.py']
files=[R/'examples/portfolio_backtesting'/n for n in list(expected)+['run_qmt_roll_stage931_official_live_ctp_submit_adapter.py','qmt_roll_weekly19_pipeline_state.py']]+[R/'tests'/n for n in names]
def pins():return {str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest()for p in files}
before=pins()
for n,h in expected.items():assert before['examples/portfolio_backtesting/'+n]==h,n
rows=[]
for name in names:
 cmd=[PY,'-B','-c',"from vnpy.trader.setting import SETTINGS; SETTINGS['log.file']=False; SETTINGS['log.console']=False; import unittest; unittest.main(module=None)",'discover','-s','tests','-p',name]
 result=subprocess.run(cmd,cwd=R,capture_output=True,text=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'));log=D/('stage016_v6_runtime_independent_'+name.removesuffix('.py')+'_attempt002.log');assert not log.exists();log.write_text(result.stdout+result.stderr);item=dict(name=name,returncode=result.returncode,tail=(result.stdout+result.stderr).splitlines()[-5:],log_sha256=hashlib.sha256(log.read_bytes()).hexdigest());rows.append(item);print(json.dumps(item),flush=True)
after=pins();payload=dict(locked_component_source_expected=expected,source_before=before,source_after=after,source_drift={n:[before[n],after[n]]for n in before if before[n]!=after[n]},suites=rows,financial_replays=0,real_ctp=False,production_qualified=False,source_qualification=False,old_v6_931_byte_equivalence_proven=False)
(D/'stage016_v6_runtime_independent_verification_attempt002.json').write_text(json.dumps(payload,indent=2)+'\n')
