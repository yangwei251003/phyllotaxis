"""Independent graph and shared-placement audit. Not native ERC/DRC."""
from pathlib import Path
import json, math
from collections import defaultdict
from eda_format import parse_records
P=Path(__file__).resolve().parents[1]
r=list(parse_records((P/'hardware/eda/phyllo-led-draft.epru').read_text(encoding='utf-8')))
layout=json.loads((P/'shared/layout.json').read_text(encoding='utf-8'))
chain=json.loads((P/'shared/chain.json').read_text(encoding='utf-8'))
components={};pins=defaultdict(dict);nets=defaultdict(list);pcb=False
led_refs={p['designator'] for p in layout['leds']}
layers={};physical={};holes={};footprints={};component_footprints={};pad_refs=[];doc_type=None;doc_id=None
for h,b in r:
    if h['type']=='DOCHEAD':
        doc_type=b['docType'];doc_id=b['uuid'];pcb=doc_type=='PCB'
    if doc_type=='FOOTPRINT' and h['type']=='PAD':
        footprints.setdefault(doc_id,{})[h['id']]=b
    if not pcb: continue
    if h['type']=='COMPONENT' and h['id'] in led_refs: components[h['id']]=b
    if h['type']=='ATTR' and b['key']=='Footprint':component_footprints[b['parentId']]=b['value']
    if h['type']=='LAYER': layers[json.loads(h['id'])[1]]=b
    if h['type']=='LAYER_PHYS': physical[json.loads(h['id'])[1]]=b
    if h['type']=='PAD' and h['id'].startswith('mount-'): holes[h['id']]=b
    if h['type']=='PAD_NET':
        _,ref,pin,primitive=json.loads(h['id'])
        if ref not in led_refs:continue
        pins[ref][pin]=b['padNet'];nets[b['padNet']].append((ref,pin))
        pad_refs.append((ref,pin,primitive))
assert len(components)==layout['config']['led_count']==144
for ref,pin,primitive in pad_refs:
    actual=footprints[component_footprints[ref]][primitive]
    assert actual['num']==pin
for p in layout['leds']:
    c=components[p['designator']]
    assert math.isclose(c['x']*.0254,p['x_mm'],abs_tol=1e-6)
    assert math.isclose(c['y']*.0254,p['y_mm'],abs_tol=1e-6)
    assert set(pins[p['designator']])=={'1','2','3','4'}
    assert pins[p['designator']]['1']=='5V_LED' and pins[p['designator']]['3']=='GND'
assert len(nets['LED_DATA_IN'])==1 and nets['LED_DATA_IN'][0][1]=='4'
ref=nets['LED_DATA_IN'][0][0]; visited=[]
while ref not in visited:
    visited.append(ref); out=pins[ref]['2']
    if out=='LED_LAST_OUT': break
    terminals=nets[out]
    assert len(terminals)==2 and sorted(pin for _,pin in terminals)==['2','4']
    ref=next(r for r,p in terminals if p=='4')
assert len(visited)==144 and pins[visited[-1]]['2']=='LED_LAST_OUT'
assert visited==[f'D{i+1}' for i in chain['chain_to_geometry_id']]
assert sorted(k for k,v in layers.items() if v['use'] and v['layerType'] in ['TOP','BOTTOM','SIGNAL','PLANE'])==[1,2]
assert sorted(k for k,v in layers.items() if v['use'] and v['layerType']=='SUBSTRATE')==[101]
assert sorted(k for k,v in physical.items() if v['material']=='COPPER')==[1,2]
assert math.isclose(sum(v['thickness'] for v in physical.values())*.0254,1.6,abs_tol=1e-9)
assert len(holes)==4
for i,p in enumerate(layout['mount_holes']):
    h=holes[f'mount-{i+1}']
    assert h['plated'] is False and h['netName']=='' and h['layerId']==12
    assert math.isclose(h['centerX']*.0254,p['x_mm'],abs_tol=1e-6)
    assert math.isclose(h['centerY']*.0254,p['y_mm'],abs_tol=1e-6)
    assert math.isclose(h['hole']['width']*.0254,layout['config']['hole_diameter_mm'],abs_tol=1e-6)
    assert h['hole']['holeType']=='ROUND' and h['defaultPad']['padType']=='ELLIPSE'
    for size in [h['hole']['height'],h['defaultPad']['width'],h['defaultPad']['height']]:
        assert math.isclose(size,h['hole']['width'],abs_tol=1e-6)
report={'status':'static_led_graph_and_placement_pass','leds':len(components),
        'pins':sum(map(len,pins.values())),'footprint_pad_ids_checked':len(pad_refs),
        'single_chain_covers_all_leds':True,'shared_coordinate_max_error_mm':1e-6,
        'copper_layers':sorted(k for k,v in physical.items() if v['material']=='COPPER'),
        'modeled_thickness_mm':round(sum(v['thickness'] for v in physical.values())*.0254,6),
        'candidate_outer_copper_um':{str(k):round(v['thickness']*25.4,6) for k,v in physical.items() if v['material']=='COPPER'},
        'npth_count':len(holes),'npth_diameters_mm':[round(v['hole']['width']*.0254,6) for v in holes.values()],
        'native_erc_drc':False,'manufacturing_ready':False,
        'incomplete':['support-circuit footprint polarity and mechanical checks','bottom connectors PCB placement','routing and copper pours','board rules','native import/render/readback','thermal/current verification']}
(P/'verification/led-draft-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
