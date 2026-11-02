"""Run the unchanged trusted CLI; retain private raw failure observations.

The side archive never qualifies a source, replaces a bundle artifact or alters
the child argv/environment. It only copies producer bytes before cleanup.
"""
import argparse,hashlib,json,os,stat,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path

def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def write_once(path,data):
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb')as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
def require_private(path):
 info=path.lstat()
 if not stat.S_ISDIR(info.st_mode)or info.st_uid!=os.geteuid()or stat.S_IMODE(info.st_mode)!=0o700:raise ValueError('private_owned_directory_required')

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--repo-root',type=Path,required=True);p.add_argument('--private-parent',type=Path,required=True)
 p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--review-report',type=Path,required=True)
 p.add_argument('--material-release-id');p.add_argument('--material-release-commit')
 args=p.parse_args();os.umask(0o077)
 repo=args.repo_root.resolve(strict=True);parent=args.private_parent.resolve(strict=True)
 output=args.output_dir.absolute();require_private(parent);require_private(output.parent)
 if parent.is_relative_to(repo)or output.is_relative_to(repo)or output.exists():raise ValueError('external_new_private_output_required')
 if bool(args.material_release_id)!=bool(args.material_release_commit):raise ValueError('both_candidate_bindings_required')
 archive=parent/'observer-archive';archive.mkdir(mode=0o700);objects=archive/'objects';objects.mkdir(mode=0o700)
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
 if subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip():raise ValueError('source_must_be_clean')
 argv=[str(repo/'.py311/bin/python'),str(repo/'examples/portfolio_backtesting/build_qmt_roll_stage179_production_qualification_bundle.py'),
  '--repo-root',str(repo),'--output-dir',str(output),'--review-report',str(args.review_report),
  '--confirm-trusted-production-qualification-run','I_APPROVE_RUNNING_EXACT_TESTS_AND_TWO_FORMAL_CTP_READONLY_CAPTURES']
 if args.material_release_id:argv+=['--material-release-id',args.material_release_id,'--material-release-commit',args.material_release_commit]
 invocation=dict(schema='qualification-observer.invocation.v1',started_at_utc=datetime.now(timezone.utc).isoformat(),
  source_commit=head,argv=argv,producer_cli_unchanged=True,observer_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
  qualification_authority=False,child_environment_override=False,archive_scope='producer raw-* files only; excludes runner HOME/TMP and credentials')
 write_once(parent/'observer-invocation.json',canonical(invocation))
 records={};seen_stats={};errors=[]
 def capture():
  for stage in output.parent.glob('.'+output.name+'.trusted-runner.*'):
   if stage.is_symlink()or not stage.is_dir():continue
   for first in stage.iterdir():
    if not first.name.startswith('raw-')or first.is_symlink():continue
    paths=first.rglob('*')if first.is_dir()else [first]
    for source in paths:
     try:
      info=source.lstat()
      if not stat.S_ISREG(info.st_mode)or info.st_uid!=os.geteuid():continue
      signature=(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns)
      key=str(source)
      if seen_stats.get(key)==signature:continue
      if source.name.startswith('raw-pytest-'):
       stem=source.name.split('.',1)[0]
       if not(source.parent/(stem+'.exit-status')).is_file():continue
      fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW)
      with os.fdopen(fd,'rb')as stream:
       before=os.fstat(stream.fileno());data=stream.read();after=os.fstat(stream.fileno())
      if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns)or len(data)!=after.st_size:continue
      digest=hashlib.sha256(data).hexdigest();destination=objects/digest
      if not destination.exists():write_once(destination,data)
      record_key=key+':'+digest
      records.setdefault(record_key,dict(original_path=key,relative_to_staging=str(source.relative_to(stage)),
       sha256=digest,bytes=len(data),object_path=str(destination),observed_at_utc=datetime.now(timezone.utc).isoformat()))
      seen_stats[key]=signature
     except FileNotFoundError:continue
     except OSError as exc:errors.append(dict(path=str(source),error_type=type(exc).__name__,errno=exc.errno))
 log=parent/'qualification-wrapper.log'
 with log.open('xb')as stream:
  child=subprocess.Popen(argv,cwd=repo,stdout=stream,stderr=subprocess.STDOUT)
  while child.poll()is None:
   capture();time.sleep(.02)
  capture();returncode=child.returncode
 result=dict(schema='qualification-observer.result.v1',finished_at_utc=datetime.now(timezone.utc).isoformat(),
  returncode=returncode,qualification_exists=(output/'qualification.json').is_file(),source_commit=head,
  qualification_authority=False,archive_is_not_qualification_evidence=True,captured_versions=len(records),
  records=list(records.values()),errors=errors,private_log=str(log))
 write_once(parent/'observer-result.json',canonical(result))
 print(json.dumps({k:result[k]for k in ('returncode','qualification_exists','captured_versions','private_log')},sort_keys=True))
 return returncode

if __name__=='__main__':raise SystemExit(main())
