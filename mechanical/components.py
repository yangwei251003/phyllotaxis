"""Simple, explicitly conservative mounted-component spaces from native placement."""
import json,hashlib,os
from pathlib import Path
from build123d import Polygon,extrude,Pos,Color,Compound
P=Path(__file__).resolve().parents[1]
REV=os.environ.get('PHYLLO_COMPONENT_REVISION','prototype-v02')
assert REV in ['', 'prototype-v02']
SPACE=P/'mechanical'/REV if REV else P/'mechanical'
PCB=P/'hardware'/('prototype-v02' if REV else 'kicad-check')/'phyllo-copper-review.kicad_pcb'
SPEC=json.loads((SPACE/'component-envelopes.json').read_text())
assert SPEC['board_sha256']==hashlib.sha256(PCB.read_bytes()).hexdigest(),'PCB changed: regenerate component space from current native readback'
assert SPEC['height_spec_sha256']==hashlib.sha256((SPACE/'component-heights.json').read_bytes()).hexdigest(),'Height evidence changed: regenerate placement space'
def support_shapes():
    shapes=[]
    for row in SPEC['rows']:
        # build123d flattens list arguments; keep each coordinate an atomic tuple.
        s=Pos(0,0,row['pcb_seat_z_mm'])*extrude(Polygon(*[tuple(p) for p in row['profile_xy_mm']],align=None),amount=row['height_spec']['height_mm'],dir=(0,0,1))
        s.label=f"SPACE_{row['ref']}_{row['part']}_CONSERVATIVE_NOT_VENDOR_MODEL"
        s.color=Color(.68,.70,.66) if row['part'] in ['C46550459','APXF100ARA271MF61G'] else Color(.25,.28,.31)
        shapes.append(s)
    return shapes
def support_components():return Compound(children=support_shapes(),label=f'{len(SPEC["rows"])}_SMD_support_parts_CONSERVATIVE_SPACE')
