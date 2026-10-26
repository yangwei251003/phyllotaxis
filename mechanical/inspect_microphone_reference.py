"""Inspect the untouched official SEN0526 STEP before using any mating datums."""
from pathlib import Path
import json, subprocess, sys, os
P=Path(__file__).resolve().parents[1]; T=Path('<LOCAL_PATH>')
target=P/'mechanical/reference/SEN0526/SEN0526-reference.step'
env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','CADGEN_COMPONENT_WORKERS':'1'}
jobs={'jobs':[{'input':str(target),'mode':'view','outputs':[
 {'path':str(P/'verification/SEN0526-reference-iso.png'),'camera':'iso'},
 {'path':str(P/'verification/SEN0526-reference-top.png'),'camera':'top'}]}]}
job=P/'mechanical/microphone-reference-snapshots.json';job.write_text(json.dumps(jobs),encoding='utf-8')
for name,args in [('refs',[T/'inspect','refs',target,'--facts','--planes','--positioning']),
 ('validate',[T/'inspect','validate',target]),('snapshots',[T/'snapshot','--job',job,'--json'])]:
 print('START '+name,flush=True)
 r=subprocess.run([sys.executable,'-X','utf8',*map(str,args)],env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
 (P/'verification'/('microphone-reference-'+name+'.json')).write_text(r.stdout,encoding='utf-8')
 (P/'verification'/('microphone-reference-'+name+'.log')).write_text(r.stderr,encoding='utf-8')
 print(json.dumps({'stage':name,'exit_code':r.returncode}),flush=True)
 if name!='validate':assert r.returncode==0,r.stderr[-2500:]
