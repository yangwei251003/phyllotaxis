"""Collision-aware ground fanout from exported native copper; no EDA writes."""
from pathlib import Path
import json,math,heapq
import numpy as np
from shapely import intersects_xy
from shapely.geometry import Polygon,Point,LineString
from shapely.ops import unary_union
P=Path(__file__).resolve().parents[1]
d=json.loads((P/'verification/power-placement-geometry.json').read_text())
assert d['sha256']==json.loads((P/'hardware/power-layout-refinement.json').read_text())['prepared_sha256']
def shape(p):return unary_union([Polygon(v['outer'],v['holes']) for v in p])
objects=[];holes=[]
for p in d['pads']:
    for l in p['layers']:objects.append((p['net'],l,shape(p['polygons'][str(l)])))
    if p['drill'][0]:holes.append(Point(p['xy']).buffer(max(p['drill'])/2+.455))
for t in d['tracks']:
    g=Point(t['a']).buffer(t['width']/2) if t['via'] else LineString([t['a'],t['b']]).buffer(t['width']/2)
    for l in t['layers']:objects.append((t['net'],l,g))
    if t['via']:holes.append(Point(t['a']).buffer(t['drill']/2+.405))
obstacles={l:unary_union([g for n,k,g in objects if k==l and n!='GND']).buffer(.211) for l in [0,2]}
hole_obstacles=unary_union(holes)
usable=Point(100,100).buffer(89.45,quad_segs=512)
fanouts=[];failed=[]
for p in sorted((p for p in d['pads'] if p['net']=='GND' and p['layers']==[0]),key=lambda p:(p['ref'].startswith('D'),p['ref'])):
    center=Point(p['xy']);pad=shape(p['polygons']['0']);width=.25 if p['ref']=='U1' else .35
    # Prefer the shortest clear stub. Avoid via-in-pad and maintain drill spacing.
    choices=[]
    for radius in [.8,1,1.2,1.4,1.6,1.8,2,2.3,2.6,3,3.5]:
        for deg in range(0,360,15):
            a=math.radians(deg);q=[round(p['xy'][0]+radius*math.cos(a),6),round(p['xy'][1]+radius*math.sin(a),6)]
            v=Point(q).buffer(.3,quad_segs=16);stub=LineString([p['xy'],q]).buffer(width/2,quad_segs=16)
            if pad.distance(v)<.20 or not usable.contains(v):continue
            if v.intersects(obstacles[0]) or v.intersects(obstacles[2]) or stub.intersects(obstacles[0]):continue
            if Point(q).intersects(hole_obstacles):continue
            if any(Point(q).distance(Point(f['via']))<.66 for f in fanouts):continue
            choices.append((radius,deg,q));break
        if choices:break
    if not choices:failed.append(p['ref']+'-'+p['num']);continue
    _,deg,q=choices[0]
    fanouts.append({'ref':p['ref'],'pad':p['num'],'net':'GND','from':p['xy'],'via':q,'width':width,'diameter':.6,'drill':.3})
result={'base_sha256':d['sha256'],'fanouts':fanouts,'failed':failed,'status':'candidate_for_native_DRC','clearance_mm':.211}
# 500 mA controller branch: front launch via, then a 0.6 mm bottom trace.
for f in fanouts:
    objects.extend([('GND',0,LineString([f['from'],f['via']]).buffer(f['width']/2)),
                    ('GND',0,Point(f['via']).buffer(.3)),('GND',2,Point(f['via']).buffer(.3))])
branch_ob={l:unary_union([g for n,k,g in objects if k==l and n!='5V_MCU']).buffer(.215) for l in [0,2]}
start=[76.35,179.5];end=[120.249944,178.0];launch=[74.853438,179.5]
assert not Point(start).buffer(.4).intersects(branch_ob[0])
assert not Point(start).buffer(.4).intersects(branch_ob[2])
assert not LineString([launch,start]).buffer(.3).intersects(branch_ob[0])
# A* over a local 0.2 mm grid. Every resulting segment is checked continuously.
xs=np.arange(68,133.001,.2);ys=np.arange(168,188.001,.2);xx,yy=np.meshgrid(xs,ys)
blocked=intersects_xy(branch_ob[2].buffer(.3),xx,yy)|~intersects_xy(usable.buffer(-.3),xx,yy)
def index(p):return (int(round((p[1]-ys[0])/.2)),int(round((p[0]-xs[0])/.2)))
def coord(q):return [float(xs[q[1]]),float(ys[q[0]])]
a=index(start);b=index(end);dist={a:0};came={};heap=[(0,a)]
while heap:
    _,q=heapq.heappop(heap)
    if q==b:break
    for dy,dx in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1),(1,-1),(-1,1)]:
        t=(q[0]+dy,q[1]+dx)
        if not (0<=t[0]<len(ys) and 0<=t[1]<len(xs)) or blocked[t]:continue
        if dx and dy and (blocked[q[0],t[1]] or blocked[t[0],q[1]]):continue
        cost=dist[q]+math.hypot(dx,dy)
        if cost<dist.get(t,1e99):dist[t]=cost;came[t]=q;heapq.heappush(heap,(cost+math.hypot(t[0]-b[0],t[1]-b[1]),t))
assert b in came,'No clear controller branch route'
path=[b]
while path[-1]!=a:path.append(came[path[-1]])
raw=[start]+[coord(q) for q in reversed(path)]+[end]
simplified=[raw[0]];i=0
while i<len(raw)-1:
    j=len(raw)-1
    while j>i+1 and LineString([raw[i],raw[j]]).buffer(.3).intersects(branch_ob[2]):j-=1
    assert not LineString([raw[i],raw[j]]).buffer(.3).intersects(branch_ob[2])
    simplified.append(raw[j]);i=j
result['mcu_branch']={'net':'5V_MCU','from':launch,'via':start,'diameter':.8,'drill':.4,'width':.6,'bottom_path':simplified}
(P/'hardware/power-copper-plan.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({'ground_fanouts':len(fanouts),'failed':failed,'mcu_branch':result['mcu_branch']}))
