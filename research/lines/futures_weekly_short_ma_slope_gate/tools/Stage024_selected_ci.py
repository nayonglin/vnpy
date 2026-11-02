"""Offline selected regression with byte locks; never production qualification."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,ast,hashlib,json,os,re,subprocess,xml.etree.ElementTree as ET

def main():
 p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);args=p.parse_args()
 if not re.fullmatch(r'[0-9]{3}',args.attempt):p.error('attempt must have exactly three digits')
 root=Path.cwd();stage=root/'research/lines/futures_weekly_short_ma_slope_gate/stages'
 prefix=stage/('Stage024_selected_attempt'+args.attempt)
 paths={key:Path(str(prefix)+suffix)for key,suffix in [('log','.log'),('xml','.xml'),('record','.json'),('before','.source_before.json')]}
 assert not any(path.exists()for path in paths.values()),'Existing attempt must be preserved'
 tree=ast.parse((root/'examples/portfolio_backtesting/build_qmt_roll_stage179_release_manifest.py').read_text());values={}
 for node in tree.body:
  if isinstance(node,ast.Assign):
   for target in node.targets:
    if isinstance(target,ast.Name)and target.id in {'PRODUCTION_REQUIRED_TEST_SUITES','DEFAULT_CRITICAL_FILES'}:
     values[target.id]=ast.literal_eval(node.value)
 suites=values['PRODUCTION_REQUIRED_TEST_SUITES'];critical=values['DEFAULT_CRITICAL_FILES']
 assert len(set(suites))==len(suites)and len(set(critical))==len(critical)
 assert set(str(path)for path in Path('tests').glob('test_weekly19_*.py'))<=set(suites)
 assert set(str(path)for path in Path('examples/portfolio_backtesting').glob('*weekly19*.py'))<=set(critical)
 def hashes():return {path:hashlib.sha256((root/path).read_bytes()).hexdigest()for path in critical}
 before=hashes();started=datetime.now(timezone.utc).isoformat();paths['before'].write_text(json.dumps(before,indent=2))
 with paths['log'].open('w')as output:
  run=subprocess.run([str(root/'.py311/bin/python'),'-m','pytest','-q',*suites,'--junitxml='+str(paths['xml'])],
   cwd=root,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),stdout=output,stderr=subprocess.STDOUT)
 after=hashes();changed=[path for path in before if after[path]!=before[path]]
 counts=dict(tests=0,failures=0,errors=0,skipped=0)
 if paths['xml'].exists():
  for suite in ET.parse(paths['xml']).getroot().iter('testsuite'):
   for key in counts:counts[key]+=int(suite.attrib.get(key,0))
 accepted=run.returncode==0 and not changed and counts['tests']>0 and not any(counts[key]for key in ('failures','errors','skipped'))
 record=dict(schema='weekly19.offline-selected-ci.v1',started_at_utc=started,finished_at_utc=datetime.now(timezone.utc).isoformat(),
  suite_count=len(suites),critical_file_count=len(critical),exit_code=run.returncode,counts=counts,critical_source_changed=changed,
  accepted_offline_only=accepted,production_qualified=False,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
  source_worktree_status='existing_account_cutover_candidate_hash_locked',log_path=str(paths['log']),junit_path=str(paths['xml']),
  financial_replay=False,ctp_protocol_login_attempted=False,actual_order_api_called_count=0,actual_send_order_api_called_count=0,
  actual_cancel_order_api_called_count=0,source_sha256_before=before,source_sha256_after=after)
 paths['record'].write_text(json.dumps(record,indent=2))
 print(paths['log'].read_text()[-10000:]);print(json.dumps({key:value for key,value in record.items()if key not in {'source_sha256_before','source_sha256_after'}},sort_keys=True))
 return 0 if accepted else 1

if __name__=='__main__':raise SystemExit(main())
