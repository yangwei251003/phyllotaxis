"""New side controls: closed solids, assembly fit, fastener axes and free sound path."""
from pathlib import Path
import json,math,hashlib
from build123d import Pos,Box,Align
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from parts import base,pcb,bezel,C
from controls import P,M,B,F,controls_shapes,microphone_holder,microphone_holder_local,microphone_module_local,microphone_fasteners_local,around,x_cylinder
from connectors import connector_envelopes
ROOT=Path(__file__).resolve().parents[1]
def common(a,b):
    op=BRepAlgoAPI_Common(a.wrapped,b.wrapped);op.Build();assert op.IsDone()
    props=GProp_GProps();BRepGProp.VolumeProperties_s(op.Shape(),props);return abs(props.Mass())
def gap_bound(a,b):
    x,y=a.bounding_box(),b.bounding_box()
    return math.sqrt(sum(max(0,v1-u2,u1-v2)**2 for u1,u2,v1,v2 in zip(x.min,x.max,y.min,y.max)))
checks=[]
def fit(a,b):
    g=gap_bound(a,b)
    if g>1e-5:r={'method':'separated_bounds','gap_lower_bound_mm':g}
    else:
        v=common(a,b)
        assert v<1e-5,(a.label,b.label,v)
        r={'method':'OCC_common','overlap_mm3':v,'gap_mm':a.distance_to(b)}
    checks.append({'a':a.label,'b':b.label,**r})

print('BUILD geometry',flush=True)
shell=base();shell.label='base';assert shell.is_valid and len(shell.solids())==1 and shell.volume>0
holder=microphone_holder();assert holder.is_valid and len(holder.solids())==1 and holder.volume>0
items=controls_shapes(True)
disk=pcb().moved(Pos(0,0,C['pcb_seat_z_mm']));disk.label='LED_PCB'
rim=bezel().moved(Pos(0,0,C['case_height_mm']));rim.label='bezel'
controller=Pos(0,0,3)*Box(66,46,26,align=(Align.CENTER,Align.CENTER,Align.MIN));controller.label='Controller_conservative_space'
usb=Pos(-39,0,21)*Box(26,13,8,align=(Align.CENTER,Align.CENTER,Align.MIN));usb.label='ASSUMED_USB_service'
connectors=connector_envelopes(True);connectors.label='back_connectors_and_wires'
print('CHECK control pairs',flush=True)
for i,s in enumerate(items):
    assert s.is_valid and len(s.solids())==1 and s.volume>0,s.label
    for other in [shell,disk,rim,controller,usb,connectors,*items[:i]]:fit(s,other)

# Hole tools evaluated independently of source cutting intent.
axis_tests=[]
for y in M['mount_tangents']:
    probe=around(Pos(M['mount_radius'],y,-.1)*__import__('build123d').Cylinder(1.65,6.2,align=(Align.CENTER,Align.CENTER,Align.MIN)),M['angle_deg'])
    for name,target in [('base',shell),('holder',items[0])]:
        v=common(probe,target);assert v<1e-5,(name,y,v)
        axis_tests.append({'type':'M3 coaxial through clearance','target':name,'tangent':y,'probe_diameter':3.3,'overlap_mm3':v})
for angle in B['angles_deg']:
    probe=around(x_cylinder(6.1,94.5,100.5,0,B['center_z']),angle)
    v=common(probe,shell);assert v<1e-5
    axis_tests.append({'type':'button radial bore','angle':angle,'probe_diameter':12.2,'overlap_mm3':v})
holder_local=microphone_holder_local();board_local=microphone_module_local()[0]
bearing_checks=[]
for sign in [-1,1]:
    y=sign*M['hole_tangent'];z=M['hole_z']
    probe=x_cylinder(.9,87,94.1,y,z)
    for name,target in [('holder',holder_local),('SEN0526 board',board_local)]:
        v=common(probe,target);assert v<1e-5
        axis_tests.append({'type':'M1p6 coaxial clearance','target':name,'tangent':y,'probe_diameter':1.8,'overlap_mm3':v})
    # The fused cylindrical boss carries the nut load beyond the backplate.
    seat=M['backplate_x_bounds'][0]+M['nut_pocket_depth']
    ring=x_cylinder(2.03,seat+.01,M['board_back_radius']-.01,y,z)
    ring=ring.cut(x_cylinder(1.11,seat-.1,M['board_back_radius']+.1,y,z))
    volume=common(ring,holder_local);assert abs(volume-ring.volume)<1e-4
    bearing_checks.append({'tangent':y,'full_annular_material_depth_mm':M['board_back_radius']-seat,'test_depth_mm':M['board_back_radius']-seat-.02,'expected_probe_volume_mm3':ring.volume,'material_common_mm3':volume})
for nut in [s for s in microphone_fasteners_local() if s.label.startswith('M1p6_nut')]:
    assert nut.distance_to(holder_local)<1e-6,(nut.label,'not seated')
sound=around(x_cylinder(3.5,95.8,103,0,M['acoustic_center_z']),M['angle_deg'])
sound.label='acoustic_7mm_path_after_component_space'
for s in [shell,*items]:fit(sound,s)
assert F['height']-3.5>=1.0
b=shell.bounding_box();h=holder.bounding_box()
r={'status':'controls_candidate_geometry_fit_PASS_NOT_physical_assembly','controls_sha256':hashlib.sha256((ROOT/'mechanical/controls.json').read_bytes()).hexdigest(),
 'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['mechanical/controls.py','mechanical/parts.py','mechanical/controls.json']},
 'base':{'valid':True,'solids':1,'volume_mm3':shell.volume,'size_mm':list(b.size)},
 'holder':{'valid':True,'solids':1,'volume_mm3':holder.volume,'size_mm':list(h.size),'min_mm':list(h.min)},
 'control_spaces':len(items),'checks':checks,'coaxial_checks':axis_tests,'nut_bearing_material_checks':bearing_checks,
 'floor_screw_to_table_nominal_gap_mm':F['height']-3.5,
 'nominal_assembly_height_with_uncompressed_feet_mm':C['case_height_mm']+C['lid_thickness_mm']+F['height'],
 'limits':['All purchased control/fastener parts are documented conservative envelopes, not certified vendor CAD','Only local connector and bend reserves; complete cable routes not yet proved','Acoustic hole is wide reserve, microphone real port/response not measured','Print tolerances, actual nuts/bolts, header assembly, foot compression, contact strength and physical installation not verified']}
(ROOT/'verification/controls-fit.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in r.items() if k not in ['checks','coaxial_checks']}),flush=True)
print(json.dumps({'pairs':len(checks),'coaxial_checks':len(axis_tests)}),flush=True)
