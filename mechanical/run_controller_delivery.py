"""Bounded sequential offline CAD checks/exports; does not release manufacturing."""
import json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORKSPACE=ROOT.parents[1]
OUT=ROOT/'verification'
SKILL=Path('<LOCAL_PATH>')
DFAM=Path('<LOCAL_PATH>')
env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','CADGEN_COMPONENT_WORKERS':'1'}
tasks=[('controller-fit',[ROOT/'mechanical/verify_controller.py']),
       ('controller-inspect',[ROOT/'mechanical/verify_controller_models.py'])]
for name in ['carrier','retainer']:
    tasks.append((f'controller-export-{name}',[SKILL/'export',ROOT/'mechanical'/f'{name}.step.py','--stl','--3mf','--json']))
    tasks.append((f'dfam-{name}',[DFAM,'measure',ROOT/'mechanical'/f'{name}.stl','--angle-limit','45']))
    tasks.append((f'dfam-{name}-orientations',[DFAM,'orientations',ROOT/'mechanical'/f'{name}.stl','--angle-limit','45']))
tasks.append(('controller-export-assembly',[SKILL/'export',ROOT/'mechanical/assembly.step.py','--glb','--json']))
tasks.append(('controller-snapshots',[SKILL/'snapshot','--job',ROOT/'mechanical/controller-snapshots.json','--json']))
receipt=[]
for name, args in tasks:
    print(f'START {name}',flush=True)
    p=subprocess.run([sys.executable,'-X','utf8',*map(str,args)],cwd=WORKSPACE,env=env,
                     capture_output=True,text=True,encoding='utf-8',errors='replace')
    (OUT/f'{name}-run.json').write_text(p.stdout,encoding='utf-8')
    (OUT/f'{name}-run.log').write_text(p.stderr,encoding='utf-8')
    receipt.append({'stage':name,'exit_code':p.returncode})
    (OUT/'controller-delivery-checks.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt[-1]),flush=True)
    if p.returncode:
        print(p.stderr[-3000:],flush=True)
        raise SystemExit(p.returncode)
