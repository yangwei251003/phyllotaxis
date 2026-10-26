"""Side controls with source-defined radial datums. Units mm.

X points outward, Y is tangent, Z is up before the common Z rotation.
Reference parts are explicitly space models, not supplier detailed solids.
"""
import json, math
from pathlib import Path
from build123d import Align, Box, Cylinder, RegularPolygon, extrude, Pos, Rot, Compound, Color
HERE=Path(__file__).resolve().parent
P=json.loads((HERE/'controls.json').read_text(encoding='utf-8'))
M=P['microphone'];B=P['buttons'];F=P['feet']
MIN=(Align.CENTER,Align.CENTER,Align.MIN)

def x_cylinder(radius,x0,x1,y=0,z=0):
    return Pos(x0,y,z)*Rot(0,90,0)*Cylinder(radius,x1-x0,align=MIN)

def block(x0,x1,width,z0,z1,y=0):
    return Pos((x0+x1)/2,y,z0)*Box(x1-x0,width,z1-z0,align=MIN)

def hex_x(af,x0,x1,y,z):
    # Hex radius is circumradius; sqrt(3)*R is across flats.
    profile=RegularPolygon(af/math.sqrt(3),6)
    return Pos(x0,y,z)*Rot(0,90,0)*extrude(profile,amount=x1-x0)

def around(shape,angle):return shape.moved(Rot(0,0,angle))

def microphone_holder_local():
    f0,f1=M['foot_x_bounds'];z0=M['foot_floor_z'];z1=z0+M['foot_thickness']
    x0,x1=M['backplate_x_bounds'];top0,top1=M['backplate_z_bounds']
    foot=block(f0,f1,M['foot_width'],z0,z1)
    top=block(x0,x1,M['foot_width'],top0,top1)
    legs=[block(x0,x1,M['leg_width'],z1-.2,top0+.2,y) for y in M['leg_tangents']]
    bosses=[x_cylinder(M['boss_radius'],x0+.2,M['board_back_radius'],s*M['hole_tangent'],M['hole_z']) for s in [-1,1]]
    body=foot.fuse(top,*legs,*bosses)
    cuts=[Pos(M['mount_radius'],y,z0-1)*Cylinder(M['mount_hole_diameter']/2,M['foot_thickness']+2,align=MIN) for y in M['mount_tangents']]
    cuts += [x_cylinder(M['board_fastener_clearance']/2,x0-1,M['board_back_radius']+1,s*M['hole_tangent'],M['hole_z']) for s in [-1,1]]
    body=body.cut(*cuts)
    # Nut recesses are a separate family to avoid coincident overlapping cutters.
    body=body.cut(*[hex_x(M['nut_pocket_across_flats'],x0-.2,x0+M['nut_pocket_depth'],s*M['hole_tangent'],M['hole_z']) for s in [-1,1]])
    body.label='Microphone_holder_PETG_M1p6_nut_pockets_and_M3_base'
    body.color=Color(.30,.43,.36)
    return body

def microphone_holder():
    # Standalone printable part: base datum at Z0, radial centre moved to X0.
    return microphone_holder_local().moved(Pos(-sum(M['foot_x_bounds'])/2,0,-M['foot_floor_z']))

def microphone_module_local():
    front=M['front_radius'];zc=M['board_center_z']
    board=block(front-M['board_size'][0],front,M['board_size'][1],zc-M['board_size'][2]/2,zc+M['board_size'][2]/2)
    board=board.cut(*[x_cylinder(M['hole_diameter']/2,front-2,front+1,s*M['hole_tangent'],M['hole_z']) for s in [-1,1]])
    board.label='SEN0526_board_hole_datum_ENVELOPE_not_vendor_model';board.color=Color(.15,.23,.20)
    # Broad reserves cover datasheet maximum body and uncertain reference placement.
    body=block(front,front+1.75,8,zc-4,zc+4)
    body=body.fuse(block(front,front+1.75,3,zc+3.5,zc+5.75),
                   block(front,front+1.5,16.5,13.15,15.55))
    body.label='SEN0526_components_MAX_plus_RESERVE';body.color=Color(.68,.73,.75)
    return [board,body]

def microphone_fasteners_local():
    shapes=[]
    for s in [-1,1]:
        y=s*M['hole_tangent'];z=M['hole_z']
        bolt=x_cylinder(.8,86,94,y,z).fuse(x_cylinder(1.6,94,95.6,y,z))
        bolt.label=f'M1p6x8_head_ENVELOPE_{s:+}';bolt.color=Color(.65,.65,.66)
        nut_seat=M['backplate_x_bounds'][0]+M['nut_pocket_depth']
        nut=hex_x(3.2,nut_seat-1.3,nut_seat,y,z).cut(x_cylinder(.81,87,90,y,z))
        nut.label=f'M1p6_nut_ENVELOPE_{s:+}';nut.color=Color(.65,.65,.66)
        shapes.extend([bolt,nut])
    for i,y in enumerate(M['mount_tangents']):
        bolt=Pos(M['mount_radius'],y,-3.5)*Cylinder(3,3.5,align=MIN)
        bolt=bolt.fuse(Pos(M['mount_radius'],y,0)*Cylinder(1.5,10,align=MIN))
        bolt.label=f'M3x10_floor_screw_ENVELOPE_{i+1}';bolt.color=Color(.65,.65,.66)
        nut=Pos(M['mount_radius'],y,6)*extrude(RegularPolygon(3.4,6),amount=2.5)
        nut=nut.cut(Pos(M['mount_radius'],y,5)*Cylinder(1.51,5,align=MIN))
        nut.label=f'M3_floor_nut_ENVELOPE_{i+1}';nut.color=Color(.65,.65,.66)
        shapes.extend([bolt,nut])
    return shapes

def microphone_wire_reserves_local():
    h=block(71,93,16.5,11.85,16.85)
    h.label='ASSUMED_SEN0526_back_header_plug_space';h.color=Color(.21,.62,.80,.30)
    bend=block(60,71,16.5,8.85,16.85)
    bend.label='ASSUMED_SEN0526_wire_bend_space';bend.color=Color(.21,.62,.80,.25)
    return [h,bend]

def button_land_local():
    z=B['center_z'];return block(B['panel_inner_radius'],B['panel_outer_radius'],B['land_width'],z-B['land_height']/2,z+B['land_height']/2)

def button_parts_local():
    x=B['panel_outer_radius'];z=B['center_z']
    body=x_cylinder(B['nominal_thread_diameter']/2,x-B['rear_length'],x,0,z)
    body=body.fuse(x_cylinder(B['head_diameter']/2,x,x+B['head_projection'],0,z))
    body.label='GQ12H10M_N_body_and_terminals_ENVELOPE';body.color=Color(.70,.72,.72)
    nut=x_cylinder(B['nut_reserve_diameter']/2,B['panel_inner_radius']-B['nut_reserve_depth'],B['panel_inner_radius'],0,z)
    nut=nut.cut(x_cylinder(6.05,91,96,0,z))
    nut.label='GQ12_nut_RESERVE_not_exact_nut';nut.color=Color(.56,.58,.58)
    return [body,nut]

def button_wire_reserve_local():
    end=B['panel_outer_radius']-B['rear_length'];z=B['center_z']
    s=block(end-B['wire_bend_reserve_length'],end,B['wire_bend_reserve_width'],z-B['wire_bend_reserve_height']/2,z+B['wire_bend_reserve_height']/2)
    s.label='ASSUMED_button_pre_wired_bend_space';s.color=Color(.88,.60,.22,.30)
    return s

def feet():
    result=[]
    for i,a in enumerate(F['angles_deg']):
        s=Pos(F['radius_from_center']*math.cos(math.radians(a)),F['radius_from_center']*math.sin(math.radians(a)),-F['height'])*Cylinder(F['diameter']/2,F['height'],align=MIN)
        s.label=f'Adhesive_rubber_foot_ENVELOPE_{i+1}';s.color=Color(.08,.10,.09)
        result.append(s)
    return result

def base_additions():return [around(button_land_local(),a) for a in B['angles_deg']]

def base_control_cuts():
    holes=[around(x_cylinder(B['hole_diameter']/2,94,102,0,B['center_z']),a) for a in B['angles_deg']]
    holes.append(around(x_cylinder(M['acoustic_hole_diameter']/2,95,103,0,M['acoustic_center_z']),M['angle_deg']))
    holes += [around(Pos(M['mount_radius'],y,-1)*Cylinder(M['mount_hole_diameter']/2,5,align=MIN),M['angle_deg']) for y in M['mount_tangents']]
    return holes

def controls_shapes(include_reserves=False):
    result=[around(s,M['angle_deg']) for s in [microphone_holder_local(),*microphone_module_local(),*microphone_fasteners_local()]]
    if include_reserves:result += [around(s,M['angle_deg']) for s in microphone_wire_reserves_local()]
    for i,a in enumerate(B['angles_deg']):
        for s in button_parts_local()+([button_wire_reserve_local()] if include_reserves else []):
            s.label+=f'_{i+1}';result.append(around(s,a))
    return result+feet()

def controls_assembly(include_reserves=False):
    return Compound(children=controls_shapes(include_reserves),label='PHYLLO_side_controls_and_feet_CANDIDATE')
