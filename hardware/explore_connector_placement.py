"""Geometric candidate search, not a routing/manufacturing decision."""
from pathlib import Path
import json,math
from shapely.geometry import Point
from shapely.affinity import scale,rotate,translate
from shapely.ops import unary_union
from placement_geometry import libs,placed_envelope,local_envelope,MIL
P=Path(__file__).resolve().parents[1]
layout=json.loads((P/'shared/layout.json').read_text());plan=json.loads((P/'hardware/placement_candidate.json').read_text())
parts={c['ref']:c['part'] for c in json.loads((P/'hardware/power_candidate.json').read_text())['components']}
tops={p['designator']:placed_envelope('C52941391',p['x_mm'],p['y_mm']) for p in layout['leds']}
tops.update({p['ref']:placed_envelope(parts[p['ref']],p['x'],p['y'],p['angle']) for p in plan['top']})
obstacles=unary_union(list(tops.values()))
board=Point(0,0).buffer(90,quad_segs=360)
mounts=unary_union([Point(p['x_mm'],p['y_mm']).buffer(3.5) for p in layout['mount_holes']])
def transform(s,x,y,a):return translate(rotate(scale(s,xfact=-1,yfact=1,origin=(0,0)),a,origin=(0,0)),x,y)
def evaluate(part,x,y,a):
    lib=libs[part];padparts=[]
    for n,p in lib['pads'].items():
        # Retain the actual library copper OD even for uncertain anchor pads.
        radius=max(p['defaultPad']['width'],p['defaultPad']['height'])*MIL/2
        padparts.append(Point(p['centerX']*MIL,p['centerY']*MIL).buffer(radius,quad_segs=32))
    pads=transform(unary_union(padparts),x,y,a);body=transform(local_envelope(part),x,y,a)
    if not board.covers(pads.buffer(1.5)) or not board.covers(body.buffer(1.5)) or body.intersects(mounts):return None
    gap=pads.distance(obstacles)
    if gap<.8:return None
    closest=min((pads.distance(s),r) for r,s in tops.items())
    return {'x':x,'y':y,'physical_angle_ccw':a,'top_pad_body_gap_mm':gap,'nearest_top':closest[1],'body_edge_mm':body.distance(board.boundary)}
found={}
for ref,part,xs,ys,a,target in [('J1','C431092',range(-10,11),range(-80,-67),180,(0,-76)),('J2','C594232',range(18,39),range(-81,-67),0,(24,-78))]:
    valid=[]
    for x in xs:
        for y in ys:
            p=evaluate(part,x,y,a)
            if p is not None:p['distance_to_initial_mm']=math.hypot(x-target[0],y-target[1]);valid.append(p)
    found[ref]=sorted(valid,key=lambda p:(p['distance_to_initial_mm'],-p['top_pad_body_gap_mm']))[:8]
print(json.dumps(found,indent=2))
