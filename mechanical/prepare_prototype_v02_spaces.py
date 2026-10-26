from pathlib import Path
import json,math,hashlib
from shapely.geometry import Polygon
from shapely.ops import unary_union
P=Path(__file__).resolve().parents[1];D=P/'mechanical/prototype-v02';D.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
g=json.loads((P/'verification/prototype-v02-copper-geometry.json').read_text());assert g['sha256']==sha(P/'hardware/prototype-v02/phyllo-copper-review.kicad_pcb')
heights=json.loads((P/'mechanical/component-heights.json').read_text())
part='APXF100ARA271MF61G';del heights['rows']['C46550459']
heights['rows'][part]={'height_mm':6.5,'manufacturer_max_height_mm':6.1,'extra_height_reserve_mm':.4,'maximum_overall_xy_in_library_axes_mm':[7.4,6.8],'basis':'Official F61 L5.8±0.3, C7.2±0.2, B6.6±0.2; additional0.4mm engineering mounting reserve, not manufacturer tolerance.','source':'hardware/datasheets/ChemiCon-PXFRA-2026.pdf','source_url':'https://www.chemi-con.co.jp/products/relatedfiles/capacitor/catalog/PXFRA-e.PDF','source_sha256':sha(P/'hardware/datasheets/ChemiCon-PXFRA-2026.pdf'),'source_pages':[1]}
(D/'component-heights.json').write_text(json.dumps(heights,indent=2),encoding='utf-8')
old=json.loads((P/'mechanical/component-envelopes.json').read_text());rows=[r for r in old['rows'] if r['part']!='C46550459']
top=old['rows'][0]['pcb_seat_z_mm']
for fp in g['footprints']:
    if fp['part']!=part:continue
    x,y=fp['xy'][0]-100,100-fp['xy'][1];a=math.radians(fp['angle'])
    transform=lambda q:(x+q[0]*math.cos(a)-q[1]*math.sin(a),y+q[0]*math.sin(a)+q[1]*math.cos(a))
    body=Polygon([transform(q) for q in [(-3.7,-3.4),(3.7,-3.4),(3.7,3.4),(-3.7,3.4)]])
    pads=[Polygon([(qx-100,100-qy) for qx,qy in poly['outer']]) for p in g['pads'] if p['ref']==fp['ref'] for poly in p['polygons']['0']]
    space=unary_union([body,*pads]).convex_hull.buffer(.25,join_style=2)
    rows.append({'ref':fp['ref'],'part':part,'source_library_sha256':None,'native_angle_deg':fp['angle'],'center_xy_mm':[x,y],'pcb_seat_z_mm':top,'height_spec':heights['rows'][part],'profile_xy_mm':list(space.exterior.coords)[:-1],'profile_area_mm2':space.area,'xy_margin_mm':.25})
assert len(rows)==21
old.update(status='21_SUPPORT_COMPONENT_CONSERVATIVE_SPACES_NOT_VENDOR_MODELS',board_sha256=g['sha256'],height_spec_sha256=sha(D/'component-heights.json'),rows=rows)
(D/'component-envelopes.json').write_text(json.dumps(old,indent=2),encoding='utf-8');print(json.dumps({'parts':len(rows),'board_sha256':g['sha256']}))
