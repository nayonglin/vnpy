"""Fresh --no-local m3 material acceptance. No strategy/CI/CTP/SMTP execution."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,re,stat,subprocess,sys,tempfile,time,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[4];STAGE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate/stages'
sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT)]
from build_qmt_roll_official_strategy_material_release import verify_release_tree
from qmt_roll_strategy_material_manifest import material_manifest_digest,material_tree_fingerprint
from qmt_roll_official_execution_profile import WEEKLY19_15W_R150K_PROFILE as PROFILE
SOURCE='39913bc2821c47a485913f6d7b2d2631c19e19ab';CODE='52b825c4efe88b20b8a9a33116c755003f1c9ab9';RELEASE='65594f6320f4c625892be534f750275c9667e315';RID='m0003_20261102T001414+0800_39913bc2821c'
RAW='e1e6fb3a560f9bbaa2981b1ea347d424bddd9de6463ac0936ebb2906fa84b8a6';CANON='d93332a5adbfc39b0b4fd808bfba33c0cde97c8e463c4e0db4a93fe73002defe';TREE='53cf50f356c4f53347e0cbb76e314105076f92c619ad279507ff2efe65107e6b'
CISHA='5879ee6f20bbc021e86ecc9c56aa96e8f70ae3ef0b3f06c57f3d2bcc49231f78';REVSHA='77acbddd8f90ce4013fee1980026c361daea496220ba1bf88e6f517dc7c97ac8'
LFS=Path('/Users/mac/.codex/tools/git-lfs-3.8.1-arm64/git-lfs');LFSSHA='74af139fc6f9b039e50e5b860597881e19a2901c126a2ba301173cf784459269'
PREFIX='official_strategy_materials/official_live_weekly19_base15w_reserve15w_stage014';REL=PREFIX+'/releases/'+RID

def sha(b):return hashlib.sha256(b).hexdigest()
def fsha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def git(repo,*args):return subprocess.check_output(['git',*args],cwd=repo,env=ENV,stderr=subprocess.PIPE)
def tree(repo,ref,paths):
 out={}
 for item in git(repo,'ls-tree','-r','-z',ref,'--',*paths).split(b'\0'):
  if not item:continue
  meta,path=item.split(b'\t',1);mode,kind,oid=meta.decode().split();out[path.decode()]=dict(mode=mode,kind=kind,oid=oid)
 return out
def blobs(repo,oids):
 p=subprocess.Popen(['git','cat-file','--batch'],cwd=repo,env=ENV,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 raw,err=p.communicate(('\n'.join(oids)+'\n').encode());assert p.returncode==0
 out={};pos=0
 for oid in oids:
  end=raw.index(b'\n',pos);got,kind,length=raw[pos:end].decode().split();assert got==oid and kind=='blob';stop=end+1+int(length);out[oid]=raw[end+1:stop];assert raw[stop:stop+1]==b'\n';pos=stop+1
 assert pos==len(raw);return out
ENV=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',GIT_LFS_SKIP_SMUDGE='1',GIT_TERMINAL_PROMPT='0',GIT_TRACE='0',GIT_SSH_COMMAND='ssh -oBatchMode=yes -oConnectTimeout=15 -oStrictHostKeyChecking=yes')
ENV['PATH']=str(LFS.parent)+os.pathsep+ENV.get('PATH','')
report=dict(schema='Stage022.m3-fresh-clone-acceptance.v1',started_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),source_commit=SOURCE,code_commit=CODE,release_commit=RELEASE,material_release_id=RID,status='running',production_qualified=False,remote_master_clone=False,activation_performed=False,production_accesses=0,ctp_connections=0,smtp_sends=0,order_api_calls=0,runtime_tests_run=False,financial_replays=0,phases=[])

def command(label,args,cwd=ROOT,timeout=120):
 print('PHASE',label,flush=True);start=time.monotonic();r=subprocess.run(args,cwd=cwd,env=ENV,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
 # No trace/debug/auth headers are requested; keep ordinary Git transport
 # output in this dedicated audit log, never dump environment or credentials.
 text=r.stdout.decode(errors='replace');text=re.sub(r'(?im)^(Authorization:|Proxy-Authorization:).*$',r'\1 REDACTED',text)
 if text:print(text.rstrip(),flush=True)
 report['phases'].append(dict(name=label,returncode=r.returncode,seconds=time.monotonic()-start))
 if r.returncode:raise RuntimeError(label+'_failed')
 return r

def main():
 assert not LFS.is_symlink() and fsha(LFS)==LFSSHA and os.access(LFS,os.X_OK)
 assert git(ROOT,'rev-parse','HEAD').decode().strip()==RELEASE and git(ROOT,'rev-parse',RELEASE+'^').decode().strip()==SOURCE and git(ROOT,'rev-parse',SOURCE+'^').decode().strip()==CODE
 lock_path=STAGE/'Stage022_implementation_lock_attempt002.json';lock=json.loads(lock_path.read_text());pins=lock['critical_files_sha256'];assert len(pins)==291 and lock['suite_count']==92 and not lock['frozen_alpha_changed']
 assert all(fsha(ROOT/p)==v for p,v in pins.items());report['implementation_lock_sha256']=fsha(lock_path)
 ci_path=STAGE/'Stage022_selected_attempt002.json';rev_path=STAGE/'Stage022_review_acceptance.json';assert fsha(ci_path)==CISHA and fsha(rev_path)==REVSHA
 ci=json.loads(ci_path.read_text());review=json.loads(rev_path.read_text());assert ci['source_sha256_before']==ci['source_sha256_after']==pins==review['critical_files_sha256']
 assert ci['suite_count']==92 and ci['critical_file_count']==291 and ci['counts']==dict(tests=2348,failures=0,errors=0,skipped=0) and ci['exit_code']==0 and not ci['critical_source_changed'] and ci['accepted_offline_only'] and not ci['production_qualified']
 assert review['accepted'] and review['status']=='PASS_WITH_LIMITATIONS' and not any(review['severity_findings'].values()) and not review['production_qualified'] and not review['source_qualified'] and not review['actual_SMTP_delivery_verified']
 manifest=verify_release_tree(ROOT/REL);assert len(manifest['files'])==381 and manifest['release_id']==RID and manifest['source_commit']==SOURCE
 assert fsha(ROOT/REL/'manifest.json')==RAW and manifest['manifest_sha256']==material_manifest_digest(manifest)==CANON and manifest['tree_fingerprint']==material_tree_fingerprint(manifest['files'])==TREE
 assert manifest['strategy_version']==PROFILE.official_version and manifest['capital']==150000 and manifest['capital_label']=='15w' and manifest['qualification']['status']=='candidate' and manifest['qualification']['production_qualified'] is False and not manifest['qualification']['evidence_ids']
 rows=manifest['files'];bylogical={r['logical_path']:r for r in rows};assert set(pins)<=set(bylogical) and set(lock['new_critical_files'])<=set(bylogical)
 src_tree=tree(ROOT,SOURCE,[r['source_path'] for r in rows]);src_blobs=blobs(ROOT,list(dict.fromkeys(x['oid'] for x in src_tree.values())));code_tree=tree(ROOT,CODE,list(pins));code_blobs=blobs(ROOT,list(dict.fromkeys(x['oid'] for x in code_tree.values())))
 for row in rows:
  info=src_tree[row['source_path']];p=ROOT/REL/row['payload_path'];assert info['mode'] in ('100644','100755') and not p.is_symlink() and not (ROOT/row['source_path']).is_symlink()
  assert row['size_bytes']==p.stat().st_size and row['sha256']==fsha(p)==fsha(ROOT/row['source_path'])==sha(src_blobs[info['oid']])
 for name,want in pins.items():assert want==bylogical[name]['sha256']==sha(src_blobs[src_tree[name]['oid']])==sha(code_blobs[code_tree[name]['oid']])
 xml_path=Path(ci['junit_path']);doc=ET.parse(xml_path).getroot();cases=doc.findall('.//testcase');assert len(cases)==2348 and not any(doc.findall('.//'+t) for t in ('failure','error','skipped'))
 modules={re.search(r'(?:^|\.)(test_[^.]+)',x.attrib.get('classname','')).group(1) for x in cases if re.search(r'(?:^|\.)(test_[^.]+)',x.attrib.get('classname',''))};assert len(modules)==92
 report['source_binding']=dict(payloads=381,critical_subset=291,implementation_lock_current_git_code_source_and_payload_all_equal=True,ci_original_source_commit=ci['source_commit'],ci_summary_sha256=CISHA,ci_junit_sha256=fsha(xml_path),xml_testcases=2348,xml_modules=92,ci_failed=0,ci_errors=0,ci_skipped=0,independent_review_sha256=REVSHA,independent_review_scope=review['admissible_scope'],manifest_file_sha256=RAW,manifest_canonical_digest=CANON,tree_fingerprint=TREE,strategy_version=PROFILE.official_version,ruleset_version=PROFILE.ruleset_version)
 before_current=(ROOT/'official_strategy_materials/CURRENT.json').read_bytes();current=json.loads(before_current);assert current['release_id'].startswith('m0008_')
 old={}
 for path in sorted((ROOT/PREFIX/'releases').iterdir()):
  if path.name.startswith(('m0001_','m0002_')):
   rel=str(path.relative_to(ROOT));oid=git(ROOT,'rev-parse',SOURCE+':'+rel).decode().strip();assert git(ROOT,'rev-parse',RELEASE+':'+rel).decode().strip()==oid;old[rel]=oid
 assert len(old)==2
 # Only now create the clone: all identities and locked source bytes passed.
 holder=Path(tempfile.mkdtemp(prefix='weekly19-stage022-m3-fresh-',dir='/private/tmp'));holder.chmod(0o700);clone=holder/'clone';report['clone_path']=str(clone)
 command('clone_no_local_no_checkout',['git','clone','--no-local','--no-checkout',str(ROOT),str(clone)],timeout=180)
 command('checkout_exact_release_skip_lfs_smudge',['git','-C',str(clone),'checkout','--detach',RELEASE])
 assert git(clone,'rev-parse','HEAD').decode().strip()==RELEASE
 cache=clone/'.git/lfs';initial=[p for p in (cache/'objects').rglob('*') if p.is_file()] if (cache/'objects').exists() else [];assert not initial
 report['clone_creation']=dict(command=['git','clone','--no-local','--no-checkout',str(ROOT),str(clone)],exact_checkout=RELEASE,lfs_cache_path=str(cache),lfs_object_files_before_fetch=0,lfs_binary_path=str(LFS),lfs_binary_sha256=LFSSHA)
 options=['-c','lfs.storage='+str(cache),'-c','lfs.fetchinclude=','-c','lfs.fetchexclude=']
 command('lfs_fetch_to_empty_clone_local_cache',['git','-C',str(clone),*options,'lfs','fetch','origin',RELEASE],timeout=180)
 command('lfs_checkout_actual_contents',['git','-C',str(clone),*options,'lfs','checkout'],timeout=90)
 assert not (clone/'.git/objects/info/alternates').exists();objects=[p for p in (clone/'.git/objects').rglob('*') if p.is_file()];assert objects and all(p.stat().st_nlink==1 for p in objects)
 clone_tree=tree(clone,RELEASE,[r['logical_path'] for r in rows]+[REL+'/'+r['payload_path'] for r in rows])
 for row in rows:
  top=clone/row['logical_path'];payload=clone/REL/row['payload_path'];mode=src_tree[row['source_path']]['mode']
  assert not top.is_symlink() and not payload.is_symlink() and top.stat().st_size==payload.stat().st_size==row['size_bytes'] and fsha(top)==fsha(payload)==row['sha256']
  assert clone_tree[row['logical_path']]['mode']==clone_tree[REL+'/'+row['payload_path']]['mode']==mode
  assert bool(top.stat().st_mode&0o111)==bool(payload.stat().st_mode&0o111)==(mode=='100755')
 actual_lfs=[]
 listing=command('lfs_ls_files_actual_status',['git','-C',str(clone),*options,'lfs','ls-files','--long']).stdout.decode()
 for line in listing.splitlines():
  oid,marker,name=line.split(' ',2);p=clone/name;pointer=git(clone,'show',RELEASE+':'+name);m=re.fullmatch(rb'version https://git-lfs.github.com/spec/v1\noid sha256:([0-9a-f]{64})\nsize ([0-9]+)\n',pointer);assert m and marker=='*' and m.group(1).decode()==oid and p.stat().st_size==int(m.group(2)) and fsha(p)==oid and not p.read_bytes().startswith(b'version https://git-lfs')
  cached=cache/'objects'/oid[:2]/oid[2:4]/oid;assert cached.is_file() and fsha(cached)==oid and cached.stat().st_nlink==1
  actual_lfs.append(dict(path=name,bytes=p.stat().st_size,sha256=oid,clone_local_object_path=str(cached),pointer_oid_size_actual_contents_match=True))
 assert actual_lfs and any(x['bytes']==2865 and x['sha256']=='ba982708a476be74e30ed966883d1eae8ef52010bf8df3763a83d6fc5c719d66' for x in actual_lfs)
 manifests=list((clone/'official_strategy_materials').glob('*/releases/*/manifest.json'))
 for path in manifests:verify_release_tree(path.parent)
 for rel,oid in old.items():assert git(clone,'rev-parse',RELEASE+':'+rel).decode().strip()==oid
 assert (clone/'official_strategy_materials/CURRENT.json').read_bytes()==before_current==(ROOT/'official_strategy_materials/CURRENT.json').read_bytes()
 assert not git(clone,'status','--porcelain').strip() and git(ROOT,'rev-parse','HEAD').decode().strip()==RELEASE and all(fsha(ROOT/p)==v for p,v in pins.items())
 report.update(status='passed_candidate_material_clone_only',finished_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),payloads_and_top_level_files_checked=381,git_and_filesystem_executable_modes_match=True,all_declared_executable_entries_present=True,independent_lfs_cache_actual=actual_lfs,git_alternates_absent=True,git_objects_not_hardlinked=True,old_m1_m2_tree_oids=old,old_m1_m2_unchanged=True,current_release_id=current['release_id'],current_unchanged=True,current_is_m3=False,all_release_manifests_verified=len(manifests),source_291_unchanged_after_clone=True,source_script_sha256=fsha(Path(__file__)))

if __name__=='__main__':
 try:main()
 except Exception as exc:
  report.update(status='blocked',failed_error_type=type(exc).__name__,failed_reason=str(exc) if isinstance(exc,(AssertionError,RuntimeError)) else type(exc).__name__,finished_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat());raise
 finally:
  (STAGE/'Stage022_m3_clone_receipt.json').write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
  print('RECEIPT',json.dumps({k:report.get(k) for k in ('status','clone_path','payloads_and_top_level_files_checked','all_release_manifests_verified','current_release_id','production_qualified','failed_error_type','failed_reason')},ensure_ascii=False),flush=True)
