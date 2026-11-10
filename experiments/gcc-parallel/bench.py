import concurrent.futures, json, os, pathlib, subprocess, sys, time
import psutil
root=pathlib.Path(sys.argv[1]); workers=int(sys.argv[2]); label=sys.argv[3]
files=sorted(root.glob('*.part*.c'))
files=[next(p for p in root.glob('*.c') if p.name == root.name+'.c'), *files]
out=pathlib.Path('target/compile-bench'); out.mkdir(exist_ok=True)
def compile_one(p):
    t=time.perf_counter(); obj=out/(p.name+'.o')
    proc=subprocess.Popen(['gcc','-O1','-std=gnu11','-w','-DPLAID_SAFEPOINTS','-c',str(p),'-o',str(obj)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    tracked={}; peak=0
    parent=psutil.Process(proc.pid)
    while proc.poll() is None:
        try:
            children=parent.children(recursive=True)
            for child in [parent,*children]:
                try:
                    c=child.cpu_times(); tracked[child.pid]=c.user+c.system
                    peak=max(peak,child.memory_info().rss)
                except (psutil.NoSuchProcess,psutil.AccessDenied): pass
        except psutil.NoSuchProcess: pass
        time.sleep(.1)
    err=proc.stderr.read().decode(errors='replace')
    if proc.returncode: raise RuntimeError(f'{p}: {err}')
    obj.unlink()
    return {'name':p.name,'bytes':p.stat().st_size,'wall':time.perf_counter()-t,'sampled_cpu':sum(tracked.values()),'peak_rss':peak}
t=time.perf_counter()
with concurrent.futures.ThreadPoolExecutor(workers) as pool: rows=list(pool.map(compile_one,files))
print(json.dumps({'label':label,'workers':workers,'wall':time.perf_counter()-t,'sampled_cpu':sum(r['sampled_cpu'] for r in rows),'parts':rows},indent=2))
