"""Independent read-only candidate material/CI/clone/data proof; no test execution."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import csv,hashlib,json,os,re,subprocess,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[4];sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT)]
from build_qmt_roll_official_strategy_material_release import verify_release_tree
from qmt_roll_strategy_material_manifest import material_manifest_digest,material_tree_fingerprint
from qmt_roll_official_execution_profile import WEEKLY19_15W_R150K_PROFILE as PROFILE
SOURCE='e89fdcbb68260a647372f03626800110470f61dd';RELEASE='48839375c26081bf6aeb5610aab70c72c688c59c';RID='m0002_20261101T050816+0800_e89fdcbb6826';RAW_MANIFEST='1a23fda7a25051c4890d190c146ce33068ba1c478ce90fc3e0385e733ec5989c'
LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';STAGE=LINE/'stages';PREFIX='official_strategy_materials/official_live_weekly19_base15w_reserve15w_stage014';REL=PREFIX+'/releases/'+RID

def sha(raw):return hashlib.sha256(raw).hexdigest()
def fsha(p):
 h=hashlib.sha256()
 with p.open('rb') as stream:
  for b in iter(lambda:stream.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def git(repo,*args):return subprocess.check_output(['git',*args],cwd=repo)
def tree(repo,ref,paths):
 out={}
 for record in git(repo,'ls-tree','-r','-z',ref,'--',*paths).split(b'\0'):
  if not record:continue
  meta,path=record.split(b'\t',1);mode,kind,oid=meta.decode().split();out[path.decode()]=dict(mode=mode,kind=kind,oid=oid)
 return out
def blobs(repo,oids):
 p=subprocess.Popen(['git','cat-file','--batch'],cwd=repo,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
 raw,_=p.communicate(('\n'.join(oids)+'\n').encode());assert p.returncode==0
 pos=0;out={}
 for oid in oids:
  end=raw.index(b'\n',pos);got,kind,size=raw[pos:end].decode().split();assert got==oid and kind=='blob';start=end+1;stop=start+int(size);body=raw[start:stop];assert raw[stop:stop+1]==b'\n';pos=stop+1;out[oid]=body
 assert pos==len(raw);return out

def main():
 report=dict(schema='Stage018.m0002-independent-readback.v1',recorded_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),scope='source-material-offline-ci-clone-readback-only',source_commit=SOURCE,release_commit=RELEASE,release_id=RID,ctp_connections=0,order_api_calls=0,tests_executed=0,financial_replays=0,production_qualified=False)
 assert git(ROOT,'rev-parse',RELEASE+'^').decode().strip()==SOURCE
 manifest=verify_release_tree(ROOT/REL);assert manifest['source_commit']==SOURCE and manifest['release_id']==RID
 assert fsha(ROOT/REL/'manifest.json')==RAW_MANIFEST
 assert material_manifest_digest(manifest)==manifest['manifest_sha256'] and material_tree_fingerprint(manifest['files'])==manifest['tree_fingerprint']
 assert manifest['strategy_version']==PROFILE.official_version and manifest['capital']==PROFILE.capital and manifest['capital_label']==PROFILE.capital_label
 report['strategy_version']=PROFILE.official_version;report['ruleset_version']=PROFILE.ruleset_version;report['ruleset_binding_source']='source-and-payload execution profile bytes; generic manifest has no top-level ruleset field'
 assert manifest['qualification']['status']=='candidate' and manifest['qualification']['production_qualified'] is False
 assert not manifest['qualification']['evidence_ids'] and manifest['order_api_called_count']==manifest['cancel_order_api_called_count']==0
 files=manifest['files'];assert len(files)==378;bylogical={row['logical_path']:row for row in files};assert len(bylogical)==378
 names=[row['source_path'] for row in files];source_tree=tree(ROOT,SOURCE,names);assert len(source_tree)==378
 source_blobs=blobs(ROOT,list(dict.fromkeys(row['oid'] for row in source_tree.values())))
 release_tree=tree(ROOT,RELEASE,[REL+'/'+row['payload_path'] for row in files]);assert len(release_tree)==378
 for row in files:
  p=ROOT/REL/row['payload_path'];src=ROOT/row['source_path'];info=source_tree[row['source_path']]
  assert not p.is_symlink() and not src.is_symlink() and info['mode'] in ('100644','100755')
  assert row['storage']=='git' and row['size_bytes']==p.stat().st_size and fsha(p)==row['sha256']==fsha(src)
  assert sha(source_blobs[info['oid']])==row['sha256']
  assert release_tree[REL+'/'+row['payload_path']]['mode']==info['mode']
 changed=git(ROOT,'diff-tree','--no-commit-id','--name-only','-r',RELEASE).decode().splitlines()
 assert all(path.startswith(REL+'/') or path in (PREFIX+'/index.json','.gitattributes') for path in changed)
 index=json.loads((ROOT/PREFIX/'index.json').read_text());entry=next(x for x in index['releases'] if x['release_id']==RID)
 assert entry['manifest_sha256']==manifest['manifest_sha256'] and entry['source_commit']==SOURCE and entry['file_count']==378
 required=['examples/portfolio_backtesting/qmt_roll_weekly19_manual_cash.py','examples/portfolio_backtesting/run_qmt_roll_weekly19_manual_cash.py','research/lines/futures_weekly_short_ma_slope_gate/stages/Stage018_operator_manual_cash_runbook.md','skills/futures-live-execution-sop/SKILL.md','skills/futures-official-shadow/SKILL.md','examples/portfolio_backtesting/run_qmt_roll_stage945_official_live_production_session_launcher.py']
 assert all(name in bylogical for name in required)
 cfg=(ROOT/REL/'payload/examples/portfolio_backtesting/qmt_roll_weekly19_official_config.py').read_text();assert "cash_verification_mode='operator_manual_v1'" in cfg
 report['material']=dict(manifest_file_sha256=RAW_MANIFEST,manifest_embedded_digest=manifest['manifest_sha256'],tree_fingerprint=manifest['tree_fingerprint'],payloads_source_git_blob_and_current_bytes_match=378,inventory_checksums_verified=True,changed_commit_paths=len(changed),required_manual_launcher_skill_paths=required,manual_mode_declared=True,candidate_only=True,index_binding_verified=True)
 # A pre-commit HEAD label is preserved; tested critical bytes bind to SOURCE
 # through exact Git blob SHA, not a rewritten CI source_commit claim.
 cp=STAGE/'Stage018_selected_final_attempt002.json';ci=json.loads(cp.read_text());before=ci['source_sha256_before'];after=ci['source_sha256_after'];assert before==after and len(before)==288 and not ci['critical_source_changed']
 assert ci['counts']==dict(tests=2309,failures=0,errors=0,skipped=0) and ci['suite_count']==90 and ci['exit_code']==0 and ci['accepted_offline_only'] is True and ci['production_qualified'] is False
 assert not ci['financial_replay'] and not ci['ctp_protocol_login_attempted'] and ci['actual_order_api_called_count']==ci['actual_send_order_api_called_count']==ci['actual_cancel_order_api_called_count']==0
 assert set(before)<=set(bylogical)
 for name,want in before.items():assert want==bylogical[name]['sha256']==sha(source_blobs[source_tree[name]['oid']])
 xml=Path(ci['junit_path']);xml=xml if xml.is_absolute() else ROOT/xml;doc=ET.parse(xml).getroot();cases=doc.findall('.//testcase');assert len(cases)==2309 and not doc.findall('.//failure') and not doc.findall('.//error') and not doc.findall('.//skipped')
 modules=set()
 for case in cases:
  match=re.search(r'(?:^|\.)(test_[^.]+)',case.attrib.get('classname',''))
  if match:modules.add(match.group(1))
 assert len(modules)==90
 report['offline_ci']=dict(summary_sha256=fsha(cp),junit_sha256=fsha(xml),summary_original_source_commit=ci['source_commit'],source_binding_method='all_288_exact_tested_before_after_SHA_equal_SOURCE_Git_blobs_and_material_subset',source_bound_commit=SOURCE,critical_subset_verified=288,xml_tests=2309,xml_modules=90,failed=0,errors=0,skipped=0,production_qualified=False)
 # m1 immutable tree is identical to its original introduction, not merely
 # to the latest adjacent source snapshot.
 m1s=[p for p in (ROOT/PREFIX/'releases').iterdir() if p.name.startswith('m0001_')];assert len(m1s)==1;m1rel=str(m1s[0].relative_to(ROOT));intro=git(ROOT,'log',SOURCE,'--diff-filter=A','--format=%H','--',m1rel+'/manifest.json').decode().splitlines()[-1]
 m1tree=git(ROOT,'rev-parse',intro+':'+m1rel).decode().strip();assert all(git(ROOT,'rev-parse',ref+':'+m1rel).decode().strip()==m1tree for ref in (SOURCE,RELEASE,'HEAD'))
 verify_release_tree(m1s[0]);current_path=ROOT/'official_strategy_materials/CURRENT.json';current=json.loads(current_path.read_text());assert current['release_id'].startswith('m0008_') and current['release_id']!=RID
 assert git(ROOT,'show',SOURCE+':official_strategy_materials/CURRENT.json')==current_path.read_bytes()==git(ROOT,'show',RELEASE+':official_strategy_materials/CURRENT.json')
 report['m1_current']=dict(m1_introduction_commit=intro,m1_tree_oid=m1tree,m1_tree_unchanged=True,current_release_id=current['release_id'],current_sha256=fsha(current_path),candidate_activated=False)
 # Fresh clone proof is checked against actual filesystem/Git objects; flags
 # describing initial command/cache state remain receipt-only historical facts.
 receipt_path=Path('/private/tmp/weekly19_stage018_m0002_fresh_clone_receipt.json');receipt=json.loads(receipt_path.read_text());clone=Path(receipt['clone_path']);assert git(clone,'rev-parse','HEAD').decode().strip()==RELEASE and not git(clone,'status','--porcelain').strip()
 assert not (clone/'.git/objects/info/alternates').exists();objects=[p for p in (clone/'.git/objects').rglob('*') if p.is_file()];assert objects and all(p.stat().st_nlink==1 for p in objects)
 for row in files:
  payload=clone/REL/row['payload_path'];top=clone/row['logical_path'];mode=source_tree[row['source_path']]['mode']
  assert not payload.is_symlink() and not top.is_symlink() and payload.stat().st_size==row['size_bytes'] and fsha(payload)==fsha(top)==row['sha256']
  assert bool(payload.stat().st_mode&0o111)==bool(top.stat().st_mode&0o111)==(mode=='100755')
 clone_tree=tree(clone,RELEASE,[row['logical_path'] for row in files]+[REL+'/'+row['payload_path'] for row in files])
 assert all(clone_tree[row['logical_path']]['mode']==clone_tree[REL+'/'+row['payload_path']]['mode']==source_tree[row['source_path']]['mode'] for row in files)
 manual=clone/'examples/portfolio_backtesting/run_qmt_roll_weekly19_manual_cash.py';assert os.access(manual,os.X_OK)
 manifests=list((clone/'official_strategy_materials').glob('*/releases/*/manifest.json'))
 for path in manifests:verify_release_tree(path.parent)
 lfs=[]
 matches=git(clone,'grep','-l','-z','oid sha256:ba982708a476be74e30ed966883d1eae8ef52010bf8df3763a83d6fc5c719d66',RELEASE,'--').split(b'\0')
 for match in matches:
  if not match:continue
  refpath=match.decode();name=refpath.split(':',1)[1];pointer=git(clone,'show',refpath)
  if re.fullmatch(rb'version https://git-lfs.github.com/spec/v1\noid sha256:ba982708a476be74e30ed966883d1eae8ef52010bf8df3763a83d6fc5c719d66\nsize 2865\n',pointer):
   p=clone/name;assert p.stat().st_size==2865 and fsha(p)=='ba982708a476be74e30ed966883d1eae8ef52010bf8df3763a83d6fc5c719d66' and not p.read_bytes().startswith(b'version https://git-lfs')
   lfs.append(dict(path=name,sha256=fsha(p),bytes=p.stat().st_size,proof='exact_RELEASE_Git_LFS_pointer_oid_and_size_vs_actual_smudged_file'))
 assert len(lfs)==1
 assert receipt['source_commit']==SOURCE and receipt['release_commit']==RELEASE and receipt['material_release_id']==RID and receipt['manifest_sha256']==RAW_MANIFEST and receipt['payload_files_checked']==378
 assert receipt['production_qualified'] is False and receipt['remote_master_clone'] is False and receipt['clone_runtime_tests_run'] is False and receipt['current_is_new_candidate'] is False
 clone_current=json.loads((clone/'official_strategy_materials/CURRENT.json').read_text());assert clone_current==current
 report['fresh_clone']=dict(receipt_path=str(receipt_path),receipt_sha256=fsha(receipt_path),clone_path=str(clone),actual_head=RELEASE,actual_worktree_clean=True,actual_payload_and_top_files_verified=378,actual_git_and_filesystem_modes_match=True,manual_entry_executable=True,actual_alternates_absent=True,actual_git_object_files_single_link=True,historical_lfs_actual=lfs,all_release_manifests_verified=len(manifests),current_is_old_m8=True,no_local_clone_and_initial_empty_cache_flags='receipt_historical_claims_not_reexecuted_by_reviewer',remote_master_clone=False,runtime_tests_rerun=False,production_qualified=False)
 market_record=STAGE/'Stage018_signal_scope_complete_market_generation_receipt.json';market=json.loads(market_record.read_text());data_root=Path(market['asset_root']);verified={name:fsha(data_root/name)==want for name,want in market['market_data']['expected_hashes'].items()};assert all(verified.values()) and len(verified)==6
 for row in market['actual_calendar_sources']:assert fsha(Path(row['raw_path']))==row['raw_sha256']
 assert fsha(data_root/'calendar_generation_source_receipt.json')==market['calendar_generation_source_receipt_sha256']
 stable=Path('/Users/mac/Desktop/person/vnpy_production_live');stable_current=json.loads((stable/'official_strategy_materials/CURRENT.json').read_text());assert stable_current['release_id']==current['release_id']
 report['inactive_market_and_stable']=dict(asset_root=str(data_root),all_six_pins=verified,raw_calendar_source_pins_unchanged=True,stable_head=git(stable,'rev-parse','HEAD').decode().strip(),stable_worktree_clean=not bool(git(stable,'status','--porcelain').strip()),stable_current_release_id=stable_current['release_id'],production_qualified=False)
 report['verdict']='PASS_CANDIDATE_BINDINGS_ONLY_NOT_PRODUCTION_QUALIFICATION';report['source_script_sha256']=fsha(Path(__file__))
 (STAGE/'Stage018_review_m0002_readback_result.json').write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
 print(json.dumps(dict(verdict=report['verdict'],payload_files=378,CI_subset=288,offline_tests=2309,offline_modules=90,fresh_payload_files=378,manifests_in_clone=len(manifests),m1_unchanged=True,CURRENT=current['release_id'],market_six_pins=True,raw_manifest_file_sha256=RAW_MANIFEST,embedded_manifest_digest=manifest['manifest_sha256'],production_qualified=False),ensure_ascii=False))
if __name__=='__main__':main()
