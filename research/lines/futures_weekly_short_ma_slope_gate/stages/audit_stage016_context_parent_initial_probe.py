import copy,json,os,sys,tempfile
from pathlib import Path
from unittest.mock import patch
R=Path('/Users/mac/.codex/worktrees/weekly19-official-20261031/fian');sys.path[:0]=[str(R/'examples/portfolio_backtesting')]
import qmt_roll_weekly19_context_update as updater
import qmt_roll_weekly19_local_backend as backend
with tempfile.TemporaryDirectory(dir='/private/tmp')as t:
 base=Path(t).resolve();parent=base/'private';parent.mkdir(mode=0o700);path=parent/'context.json'
 cfg=dict(schema='weekly19.live-context.v1',execution_profile='weekly19-15w-r150k',account_key='a'*64,material_release_id='fixture',cold_start_date='2026-10-30',state_path='private-state',target_date='2026-10-30',market_data={'asset_root':'old'},cash_sources={'version':'old_parent'})
 path.write_text(json.dumps(cfg));path.chmod(0o600);expected=copy.deepcopy(cfg);old=base/'moved-private';real=backend.private_json;swapped=[]
 def replaced(p):
  if not swapped:
   parent.rename(old);parent.mkdir(mode=0o700);foreign=copy.deepcopy(cfg);foreign['cash_sources']={'version':'new_parent'};path.write_text(json.dumps(foreign));path.chmod(0o600);swapped.append(True)
  return real(p)
 with patch.object(backend,'private_json',side_effect=replaced):
  result=updater.advance_market_context(path,expected=expected,new_market={'asset_root':'new_generation'},target_date='2026-11-02')
 visible=real(path);moved=real(old/'context.json');print(json.dumps(dict(returned_success=True,returned_market=result['market_data'],visible_market=visible['market_data'],moved_market=moved['market_data'],returned_cash=result['cash_sources'],visible_cash=visible['cash_sources'],moved_cash=moved['cash_sources']),indent=2))
