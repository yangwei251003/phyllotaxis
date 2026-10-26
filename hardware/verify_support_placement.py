"""Read generated PCB records and check top support placement against real geometry.
This checks envelopes and named nets only; no native DRC, routing or thermal claim.
"""
from pathlib import Path
from itertools import combinations
import json,math,hashlib
from shapely.geometry import Point
from eda_format import parse_records
from placement_geometry import placed_envelope,libs,MIL

P=Path(__file__).resolve().parents[1]
src=P/'hardware/eda/phyllo-led-draft.epru'
spec=json.loads((P/'hardware/power_candidate.json').read_text(encoding='utf8'))
plan=json.loads((P/'hardware/placement_candidate.json').read_text(encoding='utf8'))
layout=json.loads((P/'shared/layout.json').read_text(encoding='utf8'))
parts={p['ref']:p for p in spec['components']}
top={p['ref']:p for p in plan['top']}
comp={};attrs={};pins={};pcb=False
for h,b in parse_records(src.read_text(encoding='utf8')):
    if h['type']=='DOCHEAD':pcb=b['docType']=='PCB'
    if not pcb:continue
    if h['type']=='COMPONENT':comp[h['id']]=b
    if h['type']=='ATTR':attrs.setdefault(b['parentId'],{})[b['key']]=b['value']
    if h['type']=='PAD_NET':
        _,ref,num,pad_id=json.loads(h['id']);pins.setdefault(ref,{})[num]=(pad_id,b['padNet'])
assert len(comp)==144+len(top)==161
assert not ({p['ref'] for p in plan['deferred_bottom_candidates']} & set(comp))
envelopes={};pad_count=0
for ref,b in comp.items():
    part=attrs[ref]['Supplier Part'];a=libs[part]['device']['attributes']
    assert attrs[ref]['Footprint']==a['Footprint']
    assert b['layerId']==1
    envelopes[ref]=placed_envelope(part,b['x']*MIL,b['y']*MIL,b['angle'])
    if ref not in top:continue
    expected=top[ref]
    assert part==parts[ref]['part']
    for key,actual in [('x',b['x']*MIL),('y',b['y']*MIL),('angle',b['angle'])]:assert math.isclose(actual,expected[key],abs_tol=1e-6)
    assert set(pins[ref])==set(parts[ref]['pins'])
    for num,net in parts[ref]['pins'].items():
        assert pins[ref][num]==(libs[part]['pads'][num]['id'],net);pad_count+=1
board=Point(0,0).buffer(layout['config']['pcb_diameter_mm']/2,quad_segs=360)
mounts=[Point(p['x_mm'],p['y_mm']).buffer(plan['constraints']['mount_screw_keepout_radius_mm'],quad_segs=96) for p in layout['mount_holes']]
clearances=[];edge=[];mount=[]
for ref in top:
    s=envelopes[ref];assert board.covers(s)
    edge.append((s.distance(board.boundary),ref))
    for j,keepout in enumerate(mounts):
        assert not s.intersects(keepout);mount.append((s.distance(keepout),ref,j+1))
for a,b in combinations(comp,2):
    if a not in top and b not in top:continue
    assert not envelopes[a].intersects(envelopes[b]),(a,b)
    clearances.append((envelopes[a].distance(envelopes[b]),a,b))
assert min(clearances)[0]>=plan['constraints']['min_body_and_pad_gap_mm']
assert min(edge)[0]>=plan['constraints']['min_board_edge_mm']
report={'status':'conservative_top_envelope_and_net_readback_pass','pcb_components':len(comp),
 'top_support_components':len(top),'top_support_pins_checked':pad_count,
 'minimum_component_gap':dict(zip(['mm','first','second'],min(clearances))),
 'minimum_board_edge_gap':dict(zip(['mm','reference'],min(edge))),
 'minimum_mount_keepout_gap':dict(zip(['mm','reference','hole'],min(mount))),
 'generated_epru_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),
 'missing_pcb_components':['J1','J2'],'native_drc':False,'manufacturing_ready':False,
 'limits':['Body + pad bounding rectangles are not manufacturer courtyards',
           'Angle mapping must be read back in native EDA',
           'No routing or copper coverage checked','Capacitor polarity not yet proven',
           'Bottom connector mirror/mating/cable envelopes not modeled']}
(P/'verification/support-placement-audit.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report))
