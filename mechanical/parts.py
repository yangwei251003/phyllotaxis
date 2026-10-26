import json, math
from pathlib import Path
from build123d import Box,Cylinder,Pos,Rot,Compound,Color,Align
from controller import controller_assembly
from connectors import connector_envelopes
from components import support_components
from controls import base_additions,base_control_cuts,controls_assembly

DATA=json.loads((Path(__file__).resolve().parents[1]/'shared/layout.json').read_text(encoding='utf-8'))
C=DATA['config']
MIN=(Align.CENTER,Align.CENTER,Align.MIN)
LID_HOLES=[(C['lid_screw_radius_mm']*math.cos(a),C['lid_screw_radius_mm']*math.sin(a)) for a in [0,math.pi/2,math.pi,3*math.pi/2]]

def cyl(r,h,z=0,x=0,y=0):
    return Pos(x,y,z)*Cylinder(r,h,align=MIN)

def base():
    height=C['case_height_mm']; outer=C['case_diameter_mm']/2
    shell=cyl(outer,height)-cyl(outer-C['case_wall_mm'],height,C['floor_mm'])
    posts=[cyl(4.5,C['pcb_seat_z_mm']-C['floor_mm'],C['floor_mm'],h['x_mm'],h['y_mm']) for h in DATA['mount_holes']]
    posts += [cyl(C['lid_post_radius_mm'],height-C['floor_mm'],C['floor_mm'],x,y) for x,y in LID_HOLES]
    shell=shell.fuse(*posts,*base_additions())
    cuts=[cyl(C['hole_diameter_mm']/2,height+2,-1,h['x_mm'],h['y_mm']) for h in DATA['mount_holes']]
    # Blind pilot bores for candidate plastic screws; no nut recess is implied.
    cuts += [cyl(C['lid_pilot_diameter_mm']/2,12,height-10,x,y) for x,y in LID_HOLES]
    # Vents on opposite sides, kept away from mounting pillars.
    for y in [-95,95]:
        for x in [-45,-30,-15,15,30,45]:
            for z in [11,18]: cuts.append(Pos(x,y,z)*Box(7,22,3))
    # Rear cable aperture in wall. A grommet and strain relief are required in final assembly.
    cuts.append(Pos(0,-95,12)*Box(14,22,8))
    # Bottom cable-tie slots for a removable electronics carrier.
    for x in [-28,28]:
        for y in [-16,16]:cuts.append(Pos(x,y,1.5)*Box(3,10,5))
    shell=shell.cut(*cuts)
    shell=shell.cut(*base_control_cuts())
    shell.label='Base_PETG_200mm_ventilated';shell.color=Color(.12,.21,.17)
    return shell

def bezel():
    height=C['lid_thickness_mm']
    ring=cyl(C['case_diameter_mm']/2,height)-cyl(90.5,height+1,-.5)
    ring=ring-cyl(C['diffuser_seat_radius_mm'],height,C['diffuser_seat_floor_mm'])
    ring=ring.cut(*[cyl(1.7,height+2,-1,x,y) for x,y in LID_HOLES])
    ring.label='Front_bezel_PETG_M3';ring.color=Color(.23,.36,.28)
    return ring

def diffuser():
    panel=cyl(C['diffuser_radius_mm'],C['diffuser_thickness_mm'])
    panel.label='Diffuser_acrylic_2mm_optional';panel.color=Color(.86,.92,.8,.35)
    return panel

def pcb():
    board=cyl(C['pcb_diameter_mm']/2,C['pcb_thickness_mm'])
    board=board.cut(*[cyl(C['hole_diameter_mm']/2,4,-1,h['x_mm'],h['y_mm']) for h in DATA['mount_holes']])
    # Verified native readback positions; anchor plating is still provisional.
    audit=json.loads((Path(__file__).resolve().parents[1]/'verification/connector-placement-audit.json').read_text())
    board=board.cut(*[cyl(h['drill_mm']/2,4,-1,h['x'],h['y']) for h in audit['native_hole_positions_checked']])
    board.label='PCB_ENVELOPE_CURRENT_ROUTED_BOARD';board.color=Color(.10,.15,.11)
    return board

def assembly():
    b=base();rim=bezel().moved(Pos(0,0,C['case_height_mm']))
    disk=pcb().moved(Pos(0,0,C['pcb_seat_z_mm']))
    leds=[]
    for p in DATA['leds']:
        led=Pos(p['x_mm'],p['y_mm'],C['pcb_seat_z_mm']+C['pcb_thickness_mm'])*Box(*C['led_envelope_mm'],align=MIN)
        led.label=f"LED_ENVELOPE_{p['designator']}";led.color=Color(.77,.93,.61);leds.append(led)
    controller=controller_assembly().moved(Pos(0,0,C['floor_mm']))
    return Compound(children=[b,disk,rim,controller,connector_envelopes(),support_components(),controls_assembly(),*leds],label='PHYLLO_144_candidate_open_face')

def service_assembly():
    """Lid and LED disk removed to review the controller and service access."""
    return Compound(children=[base(),controller_assembly(include_reserves=True).moved(Pos(0,0,C['floor_mm'])),controls_assembly(True),connector_envelopes(True)],
                    label='PHYLLO_service_view_ASSUMED_wire_reserves')
