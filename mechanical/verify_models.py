import json, subprocess, sys
from pathlib import Path
from parts import base,bezel,diffuser,pcb,C,DATA,LID_HOLES

PROJECT=Path(__file__).resolve().parents[1]
ROOT=PROJECT
OUT=PROJECT/'verification';OUT.mkdir(exist_ok=True)
SKILL=Path('<LOCAL_PATH>')
results=[]
for name in ['base','bezel','diffuser','assembly']:
    target=PROJECT/'mechanical'/f'{name}.step.py'
    for action,flags in [('refs',['--facts','--planes','--positioning']),('validate',[])]:
        cmd=[sys.executable,'-X','utf8',str(SKILL/'scripts/inspect'),action,str(target),*flags]
        p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
        (OUT/f'cad-{name}-{action}.json').write_text(p.stdout,encoding='utf-8')
        (OUT/f'cad-{name}-{action}.log').write_text(p.stderr,encoding='utf-8')
        results.append({'model':name,'check':action,'exit_code':p.returncode})
        print(json.dumps(results[-1]),flush=True)
        if p.returncode:raise SystemExit(p.returncode)
parts={name:fn() for name,fn in [('base',base),('bezel',bezel),('diffuser',diffuser),('pcb',pcb)]}
dimensions={}
for name,shape in parts.items():
    bb=shape.bounding_box();dimensions[name]={'bbox_mm':[bb.size.X,bb.size.Y,bb.size.Z],'solids':len(shape.solids()),'volume_mm3':shape.volume,'valid':shape.is_valid}
    assert shape.is_valid and len(shape.solids())==1 and shape.volume>0
assert abs(dimensions['base']['bbox_mm'][0]-C['case_diameter_mm'])<1e-5
assert abs(dimensions['base']['bbox_mm'][2]-C['case_height_mm'])<1e-5
assert abs(dimensions['bezel']['bbox_mm'][2]-C['lid_thickness_mm'])<1e-5
assert abs(dimensions['pcb']['bbox_mm'][0]-C['pcb_diameter_mm'])<1e-5
led_top=C['pcb_seat_z_mm']+C['pcb_thickness_mm']+C['led_envelope_mm'][2]
diffuser_bottom=C['case_height_mm']+C['diffuser_seat_floor_mm']
gap=diffuser_bottom-led_top
assert gap>4
front_cavity=diffuser_bottom-C['pcb_seat_z_mm']-C['pcb_thickness_mm']
component_gap=front_cavity-C['front_component_height_max_mm']
remaining=component_gap-C['front_assembly_allowance_mm']
assert remaining>=C['front_clearance_target_mm']
report={'status':'geometry_pass_only','revision':C['revision'],'parts':dimensions,
        'assembly_height_mm':C['case_height_mm']+C['lid_thickness_mm'],
        'led_to_diffuser_clearance_mm':gap,
        'front_height_budget':{'cavity_mm':front_cavity,'component_max_mm':C['front_component_height_max_mm'],
          'nominal_gap_mm':component_gap,'assembly_allowance_mm':C['front_assembly_allowance_mm'],
          'remaining_mm':remaining,'target_min_mm':C['front_clearance_target_mm'],
          'kind':'analytical_envelope_budget_not_full_collision_test'},
        'mounting_holes_shared_source':True,'geometry_checks':DATA['checks'],
        'not_verified':['full support component and mating connector placement','thermal behavior','physical PCB/board/connector fit','fastener specification','supplier print shrinkage','electrical operation']}
(OUT/'mechanical-dimensions.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
