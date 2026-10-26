"""Independent conservative XY checks using real pads/body outlines and readback."""
from pathlib import Path
import json,hashlib,math
from shapely.geometry import Point
from shapely.ops import unary_union
from placement_geometry import libs,placed_envelope,local_envelope,MIL
from shapely.affinity import rotate,translate,scale
P=Path(__file__).resolve().parents[1]
plan=json.loads((P/'hardware/bottom-connectors.json').read_text())
layout=json.loads((P/'shared/layout.json').read_text())
topplan=json.loads((P/'hardware/placement_candidate.json').read_text())
parts={c['ref']:c['part'] for c in json.loads((P/'hardware/power_candidate.json').read_text())['components']}
readback=json.loads((P/'verification/kicad-copper-roundtrip.json').read_text())
tops={p['designator']:placed_envelope('C52941391',p['x_mm'],p['y_mm']) for p in layout['leds']}
tops.update({p['ref']:placed_envelope(parts[p['ref']],p['x'],p['y'],p['angle']) for p in topplan['top']})
board=Point(0,0).buffer(90,quad_segs=360)
posts=unary_union([Point(p['x_mm'],p['y_mm']).buffer(4.5,quad_segs=96) for p in layout['mount_holes']])
checks=[];bodies={};holes=[]
for p in plan['components']:
    ref=p['ref'];r=math.radians(p['physical_angle_ccw'])
    body=translate(rotate(scale(local_envelope(p['part']),xfact=-1,yfact=1,origin=(0,0)),p['physical_angle_ccw'],origin=(0,0)),p['x'],p['y'])
    bodies[ref]=body
    pads=[]
    for n,s in libs[p['part']]['pads'].items():
        x,y=-s['centerX']*MIL,s['centerY']*MIL
        x,y=p['x']+x*math.cos(r)-y*math.sin(r),p['y']+x*math.sin(r)+y*math.cos(r)
        got=next(g for g in readback['bottom_pad_readback'] if g['ref']==ref and g['pad']==n)
        assert abs(got['x_mm']-100-x)<2e-6 and abs(100-got['y_mm']-y)<2e-6
        radius=max(s['defaultPad']['width'],s['defaultPad']['height'])*MIL/2
        pads.append(Point(x,y).buffer(radius,quad_segs=96))
        holes.append({'ref':ref,'pad':n,'x':x,'y':y,'drill_mm':got['drill_mm'],'anchor_unresolved':ref=='J1' and n in {'3','4'}})
    copper=unary_union(pads)
    nearest=min((copper.distance(s),name) for name,s in tops.items())
    row={'ref':ref,'minimum_copper_to_top_body_or_pad_mm':nearest[0],'nearest_top':nearest[1],
         'body_to_PCB_edge_mm':body.distance(board.boundary),'body_to_mount_post_mm':body.distance(posts),
         'conservative_library_body_bounds':list(body.bounds)}
    assert board.covers(body.buffer(1.5)) and nearest[0]>.8 and body.distance(posts)>1
    checks.append(row)
pairgap=bodies['J1'].distance(bodies['J2']);assert pairgap>2
report={'status':'analytical_placement_clearance_pass_not_physical_fit','checks':checks,'connector_pair_gap_mm':pairgap,
        'native_hole_positions_checked':holes,'board_sha256':readback['board_sha256'],
        'limits':['Library body/pad envelopes are not verified courtyards','No measured solder protrusion or wire bends',
                  'J1 3/4 PTH retained provisionally; unique KiCad NC nets are isolated, not circuit connections']}
(P/'verification/connector-placement-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
