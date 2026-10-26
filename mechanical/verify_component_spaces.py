"""Fit checks on mounted conservative solid spaces, not just nominal height arithmetic."""
from pathlib import Path
import hashlib,json,math
from build123d import Box,Pos,Align
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from parts import base,bezel,diffuser,pcb,DATA,C
from components import SPEC,support_shapes,REV
from connectors import connector_envelopes
P=Path(__file__).resolve().parents[1]
def common_volume(a,b):
    q=BRepAlgoAPI_Common(a.wrapped,b.wrapped);q.Build();assert q.IsDone();props=GProp_GProps();BRepGProp.VolumeProperties_s(q.Shape(),props);return abs(props.Mass())
def bbox_gap(a,b):
    x,y=a.bounding_box(),b.bounding_box()
    return math.sqrt(sum(max(0,v1-u2,u1-v2)**2 for u1,u2,v1,v2 in zip(x.min,x.max,y.min,y.max)))
def no_intersection(a,b):
    gap=bbox_gap(a,b)
    if gap>1e-5:return {'test':'disjoint_axis_bounds','gap_lower_bound_mm':gap}
    vol=common_volume(a,b);assert vol<1e-5,(a.label,b.label,vol)
    return {'test':'OCC_common_volume','overlap_mm3':vol,'gap_mm':a.distance_to(b)}
parts=support_shapes();assert len(parts)==len(SPEC['rows'])
shell=base();rim=bezel().moved(Pos(0,0,C['case_height_mm']));lens=diffuser().moved(Pos(0,0,C['case_height_mm']+C['diffuser_seat_floor_mm']))
disk=pcb().moved(Pos(0,0,C['pcb_seat_z_mm']));connector=connector_envelopes(True)
leds=[]
for row in DATA['leds']:
    s=Pos(row['x_mm'],row['y_mm'],C['pcb_seat_z_mm']+C['pcb_thickness_mm'])*Box(*C['led_envelope_mm'],align=(Align.CENTER,Align.CENTER,Align.MIN));s.label=row['designator'];leds.append(s)
report=[];pair_counts={'structure':0,'LEDs':0,'support_pairs':0};nearest_led=(1e9,None);nearest_other=(1e9,None)
for i,(shape,spec) in enumerate(zip(parts,SPEC['rows'])):
    b=shape.bounding_box();assert shape.is_valid and len(shape.solids())==1 and shape.volume>0
    assert abs(b.min.Z-spec['pcb_seat_z_mm'])<1e-6
    assert abs(b.size.Z-spec['height_spec']['height_mm'])<1e-6
    struct=[]
    for name,other in [('base',shell),('bezel',rim),('diffuser',lens),('PCB',disk),('back_connectors_and_wires',connector)]:
        res=no_intersection(shape,other);pair_counts['structure']+=1
        # Distances to actual solids are used for enclosure, even when broadphase is disjoint.
        if name!='back_connectors_and_wires':res['actual_gap_mm']=shape.distance_to(other)
        struct.append({'other':name,**res})
    for other in leds:
        no_intersection(shape,other);pair_counts['LEDs']+=1
        if bbox_gap(shape,other)<nearest_led[0]:
            dist=shape.distance_to(other)
            if dist<nearest_led[0]:nearest_led=(dist,[spec['ref'],other.label])
    for j,other in enumerate(parts[:i]):
        no_intersection(shape,other);pair_counts['support_pairs']+=1
        if bbox_gap(shape,other)<nearest_other[0]:
            dist=shape.distance_to(other)
            if dist<nearest_other[0]:nearest_other=(dist,[spec['ref'],SPEC['rows'][j]['ref']])
    gap=lens.bounding_box().min.Z-b.max.Z
    assert gap-C['front_assembly_allowance_mm']>=C['front_clearance_target_mm']
    report.append({'ref':spec['ref'],'part':spec['part'],'size_mm':list(b.size),'min_mm':list(b.min),'max_mm':list(b.max),
      'volume_mm3':shape.volume,'valid_closed_positive_solid':True,'diffuser_gap_mm':gap,'after_assembly_allowance_mm':gap-C['front_assembly_allowance_mm'],'structure':struct})
r={'status':f'{len(parts)}_CONSERVATIVE_COMPONENT_SPACES_GEOMETRY_FIT_PASS_NOT_PHYSICAL_ACCEPTANCE','board_sha256':SPEC['board_sha256'],
 'source_height_spec_sha256':SPEC['height_spec_sha256'],'parts':report,'pair_counts':pair_counts,'closest_support_LED':{'gap_mm':nearest_led[0],'refs':nearest_led[1]},
 'closest_support_pair':{'gap_mm':nearest_other[0],'refs':nearest_other[1]},'smallest_top_clearance_mm':min(x['diffuser_gap_mm'] for x in report),
 'smallest_top_clearance_after_0_8mm_allowance':min(x['after_assembly_allowance_mm'] for x in report),
 'limits':['Shapes are source-bound conservative spaces, not vendor detailed models. Manufacturer maximum dimensions and extra engineering reserves are recorded separately.',
 'Actual solder stand-off, PCB/print tolerances and physical assembly not measured. Existing WeAct reference model issues are outside this new-subassembly check.',
 'No screw, microphone, button or full harness physical fit is inferred from this component-space check.']}
(P/'verification'/((REV+'-' if REV else '')+'component-space-audit.json')).write_text(json.dumps(r,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in r.items() if k!='parts'}))
