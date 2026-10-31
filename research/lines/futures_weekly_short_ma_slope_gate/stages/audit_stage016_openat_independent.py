"""Isolate first lock creation race, private temp files only, no production."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import hashlib,json,os,platform,tempfile

def run_case(mode):
    with tempfile.TemporaryDirectory(dir='/private/tmp')as t:
        parent=str(Path(t).resolve());barrier=Barrier(2)
        def worker(i):
            fd=os.open(parent,os.O_RDONLY|os.O_DIRECTORY)
            try:
                barrier.wait();name='.lock'+(str(i)if mode=='different_names'else'')
                try:
                    flags=os.O_RDWR|os.O_NOFOLLOW
                    if mode=='absolute_same':opened=os.open(parent+'/'+name,flags|os.O_CREAT,0o600)
                    elif mode=='exclusive_then_existing':
                        try:opened=os.open(name,flags|os.O_CREAT|os.O_EXCL,0o600,dir_fd=fd)
                        except FileExistsError:opened=os.open(name,flags,dir_fd=fd)
                    else:opened=os.open(name,flags|os.O_CREAT,0o600,dir_fd=fd)
                    os.close(opened);return {'ok':True}
                except OSError as exc:return {'ok':False,'errno':exc.errno}
            finally:os.close(fd)
        with ThreadPoolExecutor(2)as pool:return list(pool.map(worker,[1,2]))
if __name__=='__main__':
    rows={mode:[run_case(mode)for _ in range(10)]for mode in ['dirfd_create_or_open_same','different_names','absolute_same','exclusive_then_existing']}
    print(json.dumps({'schema':'stage016_independent_openat_probe_v1','system':platform.system(),'release':platform.release(),'mac_version':platform.mac_ver()[0],'results':rows,'summary':{k:{'opens':len(v)*2,'failures':sum(not x['ok']for pair in v for x in pair)}for k,v in rows.items()},'auditor_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'CTP_connections':0,'SMTP_calls':0,'production_writes':0},indent=2))
