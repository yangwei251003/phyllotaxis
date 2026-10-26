"""Sequential CAD production and checks, one heavy process at a time."""
from pathlib import Path
import json,subprocess,sys,os,collections
P=Path(__file__).resolve().parents[1];V=P/'verification';T=Path('<LOCAL_PATH>')
D=Path('<LOCAL_PATH>')
env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1','CADGEN_COMPONENT_WORKERS':'1'}
phase=sys.argv[1] if len(sys.argv)>1 else 'parts'
tasks=[]
names=[] if phase=='meshes' else (['microphone-holder','base','controls-assembly'] if phase=='parts' else ['service-assembly','assembly'])
for name in names:
 t=P/'mechanical'/(name+'.step.py')
 tasks += [(name+'-gen',[T/'gen',t,'--write','--force','--json']),
           (name+'-refs',[T/'inspect','refs',t,'--facts','--planes','--positioning']),
           (name+'-validate',[T/'inspect','validate',t])]
 if name in ['microphone-holder','base']:
  tasks += [(name+'-mesh',[T/'export',t,'--stl','--3mf','--mesh-tolerance','0.001','--mesh-angular-tolerance','0.025','--json']),
            ('dfam-'+name,[D,'measure',t.with_name(name+'.stl'),'--angle-limit','45']),
            ('dfam-'+name+'-orientations',[D,'orientations',t.with_name(name+'.stl'),'--angle-limit','45'])]
 elif name=='assembly':tasks.append(('assembly-glb',[T/'export',t,'--glb','--json']))
if phase=='meshes':
 for name in ['microphone-holder','base']:
  t=P/'mechanical'/(name+'.step.py')
  tasks += [(name+'-mesh',[T/'export',t,'--stl','--3mf','--mesh-tolerance','0.001','--mesh-angular-tolerance','0.025','--json']),
            ('dfam-'+name,[D,'measure',t.with_name(name+'.stl'),'--angle-limit','45']),
            ('dfam-'+name+'-orientations',[D,'orientations',t.with_name(name+'.stl'),'--angle-limit','45'])]
else:
 tasks.append(('snapshots-'+phase,[T/'snapshot','--job',P/'mechanical'/('controls-snapshots-'+phase+'.json'),'--json']))
receipt=[]
for name,args in tasks:
 print('START '+name,flush=True)
 r=subprocess.run([sys.executable,'-X','utf8',*map(str,args)],cwd=P.parents[1],env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
 (V/('controls-'+name+'.json')).write_text(r.stdout,encoding='utf-8')
 (V/('controls-'+name+'.log')).write_text(r.stderr,encoding='utf-8')
 entry={'stage':name,'exit_code':r.returncode,'command':[str(a) for a in args]}
 if name in ['service-assembly-validate','assembly-validate']:
  data=json.loads(r.stdout);known=json.loads((V/'cad-weact-reference-validate.json').read_text())
  signature=lambda d:collections.Counter((p['name'],tuple(sorted(p['reasons'])),p['solidCount']) for p in d['parts'])
  assert not data['errors'] and signature(data)==signature(known),(name,data)
  entry.update({'status':'same_34_vendor_reference_issues_retained_NOT_full_shape_pass','known_issue_count':data['failureCount']})
 else:
  if r.returncode:print(r.stderr[-3000:],flush=True)
  assert r.returncode==0,name
 receipt.append(entry)
 (V/('controls-delivery-'+phase+'.json')).write_text(json.dumps(receipt,indent=2),encoding='utf-8')
 print(json.dumps(entry),flush=True)
