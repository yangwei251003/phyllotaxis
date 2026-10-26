"""Sequential native geometry checks; retain existing vendor issues explicitly."""
from pathlib import Path
import json,subprocess,sys,os,collections
P=Path(__file__).resolve().parents[1];V=P/'verification';T=Path('<LOCAL_PATH>')
env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','CADGEN_COMPONENT_WORKERS':'1'}
stages=[]
for name in ['component-space','assembly']:
    target=P/'mechanical'/(name+'.step.py')
    stages.extend([(name+'-gen',[T/'gen',target,'--write','--force','--json']),
      (name+'-refs',[T/'inspect','refs',target,'--facts','--planes','--positioning']),
      (name+'-validate',[T/'inspect','validate',target])])
stages.extend([('assembly-glb',[T/'export',P/'mechanical/assembly.step.py','--glb','--json']),
 ('component-snapshots',[T/'snapshot','--job',P/'mechanical/component-snapshots.json','--json']),
 ('saved-step-readback',[P/'mechanical/verify_export_current.py'])])
receipt=[]
for name,args in stages:
    print('START '+name,flush=True)
    proc=subprocess.run([sys.executable,'-X','utf8',*map(str,args)],cwd=P.parents[1],env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (V/('component-delivery-'+name+'.json')).write_text(proc.stdout,encoding='utf-8');(V/('component-delivery-'+name+'.log')).write_text(proc.stderr,encoding='utf-8')
    entry={'stage':name,'exit_code':proc.returncode}
    if name=='assembly-validate':
        data=json.loads(proc.stdout);known=json.loads((V/'cad-weact-reference-validate.json').read_text())
        signature=lambda data:collections.Counter((p['name'],tuple(sorted(p['reasons'])),p['solidCount']) for p in data['parts'])
        assert not data['errors'] and signature(data)==signature(known),(data,known)
        entry.update({'status':'same_imported_vendor_reference_issues_retained_NOT_full_geometry_pass','known_issue_count':data['failureCount']})
    else:assert proc.returncode==0,(name,proc.stderr[-2500:])
    receipt.append(entry);(V/'component-delivery-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps(entry),flush=True)
