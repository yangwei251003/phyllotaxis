"""Run native CAD inspectors sequentially with bounded memory use."""
import json, os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'verification'
SCRIPT = Path('<LOCAL_PATH>')
env = {**os.environ, 'OPENBLAS_NUM_THREADS':'1', 'OMP_NUM_THREADS':'1','CADGEN_COMPONENT_WORKERS':'1'}
targets = [(n, ROOT/'mechanical'/f'{n}.step.py') for n in
            ['carrier','retainer','controller-assembly','controller-space','service-assembly','assembly']]
receipt=[]
for name, target in targets:
    actions=[('refs',['--facts','--planes','--positioning'])]
    if name in ['carrier','retainer','controller-assembly']:
        actions.append(('validate',[]))
    for action, flags in actions:
        command=[sys.executable,'-X','utf8',str(SCRIPT),action,str(target),*flags]
        p=subprocess.run(command,env=env,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
        (OUT/f'cad-{name}-{action}.json').write_text(p.stdout,encoding='utf-8')
        (OUT/f'cad-{name}-{action}.log').write_text(p.stderr,encoding='utf-8')
        entry={'target':name,'action':action,'exit_code':p.returncode}
        if name=='controller-assembly' and action=='validate' and p.returncode==2:
            report=json.loads(p.stdout)
            source=json.loads((OUT/'cad-weact-reference-validate.json').read_text(encoding='utf-8'))
            source_issues=sorted((part['name'],tuple(part['reasons'])) for part in source['parts'])
            actual_issues=sorted((part['name'],tuple(part['reasons'])) for part in report['parts'])
            assert actual_issues==source_issues, 'Assembly has additional or changed issues'
            entry['status']='reference_geometry_issues_retained_NOT_full_assembly_pass'
            entry['same_source_issue_count']=report['failureCount']
        receipt.append(entry)
        (OUT/'controller-cad-checks.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
        print(json.dumps(receipt[-1]),flush=True)
        if p.returncode and 'same_source_issue_count' not in entry: raise SystemExit(p.returncode)
