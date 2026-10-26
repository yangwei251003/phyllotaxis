"""Bind conservative mechanical spaces to current native PCB and real libraries."""
from pathlib import Path
import json,sys,math,hashlib
from shapely.geometry import Polygon
from shapely.ops import unary_union
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'hardware'))
from library_inspect import read_library
g=json.loads((P/'verification/power-copper-geometry.json').read_text());pcb=P/'hardware/kicad-check/phyllo-copper-review.kicad_pcb'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert g['sha256']==sha(pcb)
H=json.loads((P/'mechanical/component-heights.json').read_text());layout=json.loads((P/'shared/layout.json').read_text())
libs={}
for file in (P/'hardware/library').glob('*.elibz2'):
    a=read_library(file);libs[a['device']['attributes']['Supplier Part']]=(a,file)
rows=[]
for fp in g['footprints']:
    if not fp['part'] or fp['layer']!=0:continue
    x,y=fp['xy'][0]-100,100-fp['xy'][1];angle=math.radians(fp['angle'])
    if fp['part']=='C52941391':
        led=next(p for p in layout['leds'] if p['designator']==fp['ref']);assert math.dist((x,y),(led['x_mm'],led['y_mm']))<.000002
        continue
    a,file=libs[fp['part']];bodies=[]
    def transform(q):return (x+q[0]*math.cos(angle)-q[1]*math.sin(angle),y+q[0]*math.sin(angle)+q[1]*math.cos(angle))
    for header,b in a['docs'][('FOOTPRINT',a['device']['attributes']['Footprint'])]:
        if header['type']=='POLY' and b.get('layerId')==48:
            coords=[v for v in b['path'] if v!='L'];assert all(isinstance(v,(int,float)) for v in coords)
            bodies.append(Polygon([transform((qx*.0254,qy*.0254)) for qx,qy in zip(coords[::2],coords[1::2])]))
    pads=[Polygon([(qx-100,100-qy) for qx,qy in poly['outer']]) for p in g['pads'] if p['ref']==fp['ref'] for poly in p['polygons']['0']]
    hx,hy=[size/2 for size in H['rows'][fp['part']]['maximum_overall_xy_in_library_axes_mm']]
    bodies.append(Polygon([transform(q) for q in [(-hx,-hy),(hx,-hy),(hx,hy),(-hx,hy)]]))
    assert bodies and all(p.is_valid for p in bodies+pads)
    raw=unary_union(bodies+pads).convex_hull;reserve=raw.buffer(H['xy_margin_mm'],join_style=2)
    rows.append({'ref':fp['ref'],'part':fp['part'],'source_library_sha256':sha(file),'native_angle_deg':fp['angle'],'center_xy_mm':[x,y],
        'pcb_seat_z_mm':layout['config']['pcb_seat_z_mm']+layout['config']['pcb_thickness_mm'],
        'height_spec':H['rows'][fp['part']],'profile_xy_mm':list(reserve.exterior.coords)[:-1],
        'profile_area_mm2':reserve.area,'xy_margin_mm':H['xy_margin_mm']})
assert len(rows)==17
result={'status':'17_SUPPORT_COMPONENT_CONSERVATIVE_SPACES_NOT_VENDOR_MODELS','board_sha256':g['sha256'],
 'height_spec_sha256':sha(P/'mechanical/component-heights.json'),'coordinate_mapping':'mechanical=(nativeX-100,100-nativeY,PCBtop); current footprint angles applied in physical XY CCW',
 'rows':rows,'scope':'Body plus solder-land convex envelope and 0.25mm XY allowance. Includes space outside actual component; not exact component geometry or a physical fit certificate.'}
(P/'mechanical/component-envelopes.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({'parts':len(rows),'board_sha256':g['sha256']}))
