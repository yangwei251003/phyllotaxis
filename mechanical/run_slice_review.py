"""Dry-run first; create and validate offline review slices only."""
from pathlib import Path
import json, subprocess, sys, hashlib
P=Path(__file__).resolve().parents[1]
D=P/'verification/slicing'
TOOL=Path('<LOCAL_PATH>')
PROFILE=D/'profile-REVIEW-ONLY.json'

def invoke(args, output):
    result=subprocess.run([sys.executable,'-X','utf8',str(TOOL),*map(str,args)],capture_output=True,encoding='utf-8')
    (D/output).write_text(result.stdout,encoding='utf-8')
    if result.returncode:
        print(result.stdout[-3000:], result.stderr[-500:]);raise SystemExit(result.returncode)
    return json.loads(result.stdout)

parts=sys.argv[1:] or ['base','bezel','carrier','retainer','microphone-holder']
for name in parts:
    mesh=P/'mechanical'/f'{name}.stl'
    out=D/'final'/name/f'{name}-REVIEW-ONLY.gcode'
    assert not out.exists(), 'Do not silently reuse/overwrite slice results'
    invoke(['inspect','--input',mesh,'--json'],f'{name}-input.json')
    common=['slice','--input',mesh,'--output',out,'--profile',PROFILE]
    plan=invoke(common+['--dry-run'],f'{name}-dry-run.json')
    assert '--slice' in plan['command'] and '--outputdir' in plan['command']
    result=invoke(common+['--execute'],f'{name}-slice.json')
    validation=invoke(['validate','--gcode',out,'--profile',PROFILE,'--json'],f'{name}-validation-final.json')
    metadata={}
    for line in out.read_text(encoding='utf-8').splitlines():
        for key in ['filament used [g]','estimated printing time (normal mode)','curr_bed_type','wall_loops','layer_height','enable_support']:
            if line.startswith('; '+key+' = '): metadata[key]=line.split(' = ',1)[1]
    assert metadata.get('curr_bed_type')=='High Temp Plate',metadata
    assert metadata.get('wall_loops')=='4',metadata
    print(json.dumps({'part':name,'static_validation':validation['ok'],'metadata':metadata,'sha256':hashlib.sha256(out.read_bytes()).hexdigest()},ensure_ascii=False),flush=True)
