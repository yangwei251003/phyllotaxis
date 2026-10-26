"""Build the LED and support-circuit engineering draft; NO manufacture release.

Actual vendor symbol/pad geometry is imported from the native EDA library.
Bottom connector placement, routing, copper fills and DRC remain separate work.
"""
from pathlib import Path
import json, zipfile, math, hashlib, time, copy
from eda_format import parse_records, serialize
from library_inspect import read_library

P=Path(__file__).resolve().parents[1]
OUT=P/'hardware/eda'; OUT.mkdir(exist_ok=True)
layout=json.loads((P/'shared/layout.json').read_text(encoding='utf-8'))
pts=layout['leds']; cfg=layout['config']; n=len(pts)
def uid(s): return hashlib.sha256(('phyllo-v01:'+s).encode()).hexdigest()[:16]
millis=int(time.time()*1000)
records=[]; ticket=0
def emit(kind,body,key=None):
    global ticket
    ticket+=1; h={'type':kind,'ticket':ticket}
    if key is not None: h['id']=key
    records.append((h,body))
def doc(kind,key):
    emit('DOCHEAD',{'docType':kind,'client':uid('local'),'uuid':key,'updateTime':millis,'version':str(millis),'user':{}})
def attr(parent,key,value,x=0,y=0,visible=False):
    emit('ATTR',dict(partId='',groupId='',locked=False,zIndex=1,parentId=parent,key=key,value=value,keyVisible=False,valueVisible=visible,x=x,y=y,rotation=0,color=None,fillColor=None,fontFamily='Arial',fontSize=7,strikeout=False,underline=False,italic=False,fontWeight=False,align='LEFT_MIDDLE',version='2.0'),f'a{ticket}')
def pcbattr(parent,key,value,x=None,y=None,visible=False):
    emit('ATTR',dict(partitionId='',groupId=0,parentId=parent,layerId=3,x=x,y=y,key=key,value=value,keyVisible=False,valueVisible=visible,fontFamily='default',fontSize=28,strokeWidth=5,bold=False,italic=False,origin='LEFT_BOTTOM',angle=0,reverse=False,expansion=0,mirror=False,locked=False,zIndex=None),f'a{ticket}')
def text(value,x,y,size=12):
    emit('TEXT',dict(groupId='',locked=False,zIndex=3,x=x,y=y,rotation=0,value=value,color='#283B47',fillColor=None,fontFamily='Arial',fontSize=size,strikeout=False,underline=False,italic=False,fontWeight=False,align='LEFT_MIDDLE',version='2.0'),f't{ticket}')

z=zipfile.ZipFile(P/'hardware/library/WS2812B-B-V6-C52941391.elibz2')
library=list(parse_records(z.read(next(k for k in z.namelist() if k.endswith('.elibu'))).decode('utf-8')))
devices=json.loads(z.read('device2.json'))['devices']
device_id,device=next(iter(devices.items()))
symbol=device['attributes']['Symbol']; footprint=device['attributes']['Footprint']
# Merge the metadata and geometry sections of the same official library document.
docs={}; current=None
for h,b in library:
    if h['type']=='DOCHEAD': current=(b['docType'],b['uuid']); docs.setdefault(current,[])
    else: docs[current].append((h,b))
for (kind,key),items in docs.items():
    doc(kind,key)
    for h,b in items: emit(h['type'],copy.deepcopy(b),h.get('id'))
doc('DEVICE',device_id)
emit('META',{'title':'WS2812B-B-V6','tags':[],'source':'','images':[],'attributes':device['attributes']},'META')
power=json.loads((P/'hardware/power_candidate.json').read_text(encoding='utf-8'))
support={}
for file in (P/'hardware/library').glob('*.elibz2'):
    lib=read_library(file); support[lib['device']['attributes']['Supplier Part']]=lib
emitted=set(docs)
for part in sorted({c['part'] for c in power['components']}):
    lib=support[part]
    for (kind,key),items in lib['docs'].items():
        if (kind,key) in emitted:continue
        emitted.add((kind,key));doc(kind,key)
        for h,b in items:emit(h['type'],copy.deepcopy(b),h.get('id'))
    doc('DEVICE',lib['device_id'])
    emit('META',{'title':lib['device']['attributes']['Manufacturer Part'],'tags':[],
         'source':'','images':[],'attributes':lib['device']['attributes']},'META')

# Physical nearest-neighbour chain with open-path 2-opt. IDs remain golden-angle IDs.
def distance(i,j): return math.hypot(pts[i]['x_mm']-pts[j]['x_mm'],pts[i]['y_mm']-pts[j]['y_mm'])
start=min(range(n),key=lambda i:math.hypot(pts[i]['x_mm'],pts[i]['y_mm']+83))
order=[start]; remaining=set(range(n))-{start}
while remaining:
    k=min(remaining,key=lambda i:(distance(order[-1],i),i)); order.append(k); remaining.remove(k)
for _ in range(20):
    changed=False
    for a in range(1,n-2):
        for b in range(a+1,n-1):
            old=distance(order[a-1],order[a])+distance(order[b],order[b+1])
            new=distance(order[a-1],order[b])+distance(order[a],order[b+1])
            if new<old-1e-8: order[a:b+1]=reversed(order[a:b+1]); changed=True
    if not changed: break
rank={ident:i for i,ident in enumerate(order)}
chain={'status':'placement_candidate_unrouted','chain_to_geometry_id':order,'geometry_to_chain_id':[rank[i] for i in range(n)],'length_mm':sum(distance(a,b) for a,b in zip(order,order[1:])),'source':'shared/layout.json','note':'Native routing may require a revised mapping. No electrical completion claim.'}
(P/'shared/chain.json').write_text(json.dumps(chain,indent=2),encoding='utf-8')
def nets(ident):
    i=rank[ident]
    return {'1':'5V_LED','2':f'DATA_{i+1:03d}' if i<n-1 else 'LED_LAST_OUT','3':'GND','4':'LED_DATA_IN' if i==0 else f'DATA_{i:03d}'}
board,sch,pcb=uid('board'),uid('sch'),uid('pcb')
doc('BOARD',board);emit('META',{'title':'PHYLLO 144 LED Panel DRAFT','zIndex':1},'META')
doc('SCH',sch);emit('META',{'title':'PHYLLO 144 LED Array','board':board,'source':'','zIndex':1},'META')
pinpos={'1':(-40,-5),'2':(-40,5),'3':(40,5),'4':(40,-5)}
for sheet in range(4):
    doc('SCH_PAGE',uid(f'led-page-{sheet}'))
    emit('CANVAS',{'originX':0,'originY':0},'CANVAS')
    emit('META',{'title':f'{sheet+1:02d} LED chain {sheet*36+1}-{(sheet+1)*36}','schematic':sch,'source':'','zIndex':sheet+1},'META')
    text('PHYLLO 144 / LED ARRAY / ENGINEERING DRAFT',20,30,17)
    text('Power/data candidate on page 5. Bottom connectors and all routing incomplete. DO NOT ORDER.',20,5,10)
    for local,ident in enumerate(order[sheet*36:(sheet+1)*36]):
        p=pts[ident]; ref=p['designator']; x=105+(local%6)*210; y=-70-(local//6)*100
        emit('COMPONENT',dict(locked=False,zIndex=2,partId='WS2812B-B-V6.1',groupId='',x=x,y=y,rotation=0,isMirror=False,attrs={'Unique ID':ref}),ref)
        for key,value in [('Device',device_id),('Symbol',symbol),('Footprint',footprint),('Unique ID',ref),('Designator',ref),('Supplier Part','C52941391')]:
            attr(ref,key,value,x-25,y+29,key=='Designator')
        for pin,(dx,dy) in pinpos.items():
            net=nets(ident)[pin]; xx=x+dx; yy=y+dy; end=xx+(-25 if dx<0 else 25); wid=f'{ref}-wire-{pin}'
            emit('WIRE',{'groupId':'','locked':False,'zIndex':4},wid)
            emit('LINE',dict(lineGroup=wid,startX=xx,startY=yy,endX=end,endY=yy,strokeColor='#0F766E',strokeStyle='SOLID',fillColor=None,strokeWidth=1,fillStyle=None),f'{wid}-line')
            attr(wid,'NET',net,end,yy+(-10 if dy<0 else 9),True)

doc('SCH_PAGE',uid('power-page'))
emit('CANVAS',{'originX':0,'originY':0},'CANVAS')
emit('META',{'title':'05 Power and data interface CANDIDATE','schematic':sch,'source':'','zIndex':5},'META')
text('PHYLLO / POWER + DATA INTERFACE / CANDIDATE ONLY',20,50,17)
text('External fused 5V supply. D-to-input PMOS. Controller USB and external 5V must not be paralleled.',20,25,10)
text('Support parts below are not placed/routed on PCB. Native ERC, polarity and package review pending.',20,5,10)
for i,component in enumerate(power['components']):
    ref=component['ref'];lib=support[component['part']];a=lib['device']['attributes']
    x=120+(i%5)*270;y=-90-(i//5)*180
    part_id=next(iter(lib['pins'].values()))['partId']
    assert set(component['pins'])==set(lib['pins'])
    emit('COMPONENT',dict(locked=False,zIndex=2,partId=part_id,groupId='',x=x,y=y,rotation=0,isMirror=False,attrs={'Unique ID':ref}),ref)
    for key,value in [('Device',lib['device_id']),('Symbol',a['Symbol']),('Footprint',a['Footprint']),('Unique ID',ref),('Designator',ref),('Supplier Part',component['part'])]:
        attr(ref,key,value,x-30,y+50,key=='Designator')
    text(a['Manufacturer Part'],x-75,y+65,8)
    for pin,p in lib['pins'].items():
        net=component['pins'][pin]
        if net is None:continue
        xx=x+p['x'];yy=y+p['y'];angle=math.radians(p['rotation'])
        ex=round(xx-30*math.cos(angle),6);ey=round(yy+30*math.sin(angle),6);wid=f'{ref}-wire-{pin}'
        emit('WIRE',{'groupId':'','locked':False,'zIndex':4},wid)
        emit('LINE',dict(lineGroup=wid,startX=xx,startY=yy,endX=ex,endY=ey,strokeColor='#0F766E',strokeStyle='SOLID',fillColor=None,strokeWidth=1,fillStyle=None),f'{wid}-line')
        attr(wid,'NET',net,ex,ey+3,True)

doc('PCB',pcb)
emit('CANVAS',{'originX':0,'originY':0,'unit':'mm','gridXSize':10,'gridYSize':10,'snapXSize':1,'snapYSize':1,'gridType':'NONE','multiGridType':'NONE','highlightValue':0.5},'CANVAS')
emit('META',{'title':'PHYLLO 144 Placement DRAFT','parent':'','source':'','board':board,'zIndex':1},'META')
# Generic layer definitions only, from the bundled official V3 sample, no circuitry.
template=json.loads((P/'hardware/reference/pcb-layer-template.json').read_text(encoding='utf-8'))
layers=set()
for entry in template['records']:
    h,b=entry['header'],entry['body']
    if h['type']=='LAYER':
        layernum=json.loads(h['id'])[1]
        if layernum in layers: continue
        layers.add(layernum); bb=copy.deepcopy(b)
        if bb.get('layerType') in {'SIGNAL','PLANE'}:
            bb['use']=False; bb['show']=False
        if bb.get('layerType')=='SUBSTRATE':
            bb['use']=layernum==101; bb['show']=False
            bb['layerName']=f'PHYLLO dielectric {layernum}'
        emit('LAYER',bb,h['id'])
mm=1/.0254
# Explicit two-layer candidate, 70um outer copper and 1.60mm total model.
# V3 fields: format/pcb/common.md; order adapted from the official two-layer
# Quick Start sample. Actual factory stack-up and finished copper remain pending.
stack=[(3,'SILK',0,0,0),(7,'PASTE',0,0,0),(5,'SOLDER_MASK',.01,3.3,.02),
       (1,'COPPER',.07,0,0),(101,'FR4',1.44,4.5,0),
       (2,'COPPER',.07,0,0),(6,'SOLDER_MASK',.01,3.3,.02),
       (8,'PASTE',0,0,0),(4,'SILK',0,0,0)]
for z,(layer,material,thickness,er,loss) in enumerate(stack):
    emit('LAYER_PHYS',dict(material=material,thickness=thickness*mm,
         permittivity=er,lossTangent=loss,isKeepIsland=False,zIndex=z+1),
         json.dumps(['LAYER_PHYS',layer],separators=(',',':')))
path=[]
for i in range(361):
    a=2*math.pi*i/360; xy=[round(cfg['pcb_diameter_mm']/2*mm*math.cos(a),6),round(cfg['pcb_diameter_mm']/2*mm*math.sin(a),6)]
    if i==0: path=xy+['L']
    else: path.extend(xy)
emit('POLY',{'partitionId':'','groupId':0,'netName':'','layerId':11,'width':0,'path':path,'locked':True,'zIndex':1,'polyType':'BOARD_OUTLINE'},'board-outline')
for i,hole in enumerate(layout['mount_holes']):
    diameter=cfg['hole_diameter_mm']*mm
    emit('PAD',dict(partitionId='',groupId=0,locked=True,zIndex=1,netName='',
        layerId=12,num='',centerX=hole['x_mm']*mm,centerY=hole['y_mm']*mm,padAngle=0,
        hole=dict(holeType='ROUND',width=diameter,height=diameter),
        defaultPad=dict(padType='ELLIPSE',width=diameter,height=diameter),
        specialPad=[],padOffsetX=0,padOffsetY=0,relativeAngle=0,plated=False,padType='NORMAL',
        topSolderExpansion=0,bottomSolderExpansion=0,topPasteExpansion=None,bottomPasteExpansion=None,
        connectMode=None,spokeSpace=None,spokeWidth=None,spokeAngle=None,unusedInnerLayers=[]),f'mount-{i+1}')
pad_ids={'1':'e23','2':'e24','3':'e21','4':'e22'}
for p in pts:
    ref=p['designator']; x=p['x_mm']*mm; y=p['y_mm']*mm
    emit('COMPONENT',{'partitionId':'','groupId':0,'layerId':1,'x':x,'y':y,'angle':0,'attrs':{'Unique ID':ref,'JLCPCB Part Class':'Extended Part'},'locked':True,'zIndex':p['id']+2},ref)
    for key,value in [('Footprint',footprint),('Device',device_id),('Designator',ref),('Name','WS2812B-B-V6'),('Supplier Part','C52941391'),('Unique ID',ref)]: pcbattr(ref,key,value,x-75,y+120,key=='Designator')
    for pin,net in nets(p['id']).items(): emit('PAD_NET',{'partitionId':'','padNet':net,'padLen':0},json.dumps(['PAD_NET',ref,pin,pad_ids[pin]],separators=(',',':')))
placement=json.loads((P/'hardware/placement_candidate.json').read_text(encoding='utf-8'))
by_ref={c['ref']:c for c in power['components']}
for p in placement['top']:
    ref=p['ref'];c=by_ref[ref];lib=support[c['part']];a=lib['device']['attributes'];x=p['x']*mm;y=p['y']*mm
    emit('COMPONENT',{'partitionId':'','groupId':0,'layerId':1,'x':x,'y':y,'angle':p['angle'],'attrs':{'Unique ID':ref},'locked':False,'zIndex':n+ticket},ref)
    for key,value in [('Footprint',a['Footprint']),('Device',lib['device_id']),('Designator',ref),('Name',a['Manufacturer Part']),('Supplier Part',c['part']),('Unique ID',ref)]:pcbattr(ref,key,value,x-40,y+60,key=='Designator')
    for pin,net in c['pins'].items():
        if net is not None:emit('PAD_NET',{'partitionId':'','padNet':net,'padLen':0},json.dumps(['PAD_NET',ref,pin,lib['pads'][pin]['id']],separators=(',',':')))
all_nets=set(net for p in pts for net in nets(p['id']).values())
all_nets.update(net for c in power['components'] for net in c['pins'].values() if net is not None)
for net in sorted(all_nets):
    emit('NET',{'netType':None,'specialColor':None,'retLine':True,'differentialName':None,'isPositiveNet':False,'equalLengthGroupName':None},json.dumps(['NET',net],separators=(',',':')))
doc('CONFIG','CONFIG')
emit('UNIVERSAL',{'allowLibRename':True,'defaultNetName':True,'wireMultipleNet':False,'netLabelCrossPageConnection':True},'UNIVERSAL')
emit('META',{'defaultSheet':''},'META')
source=serialize(records)
(OUT/'phyllo-led-draft.epru').write_text(source,encoding='utf-8',newline='\n')
with zipfile.ZipFile(OUT/'phyllo-led-draft.epro2','w',zipfile.ZIP_DEFLATED) as out:
    out.writestr('project2.json',json.dumps({'title':'PHYLLO 144 DRAFT v0.4','cbb_project':False,'editorVersion':'3.2.149','introduction':'Schematic and partial PCB placement engineering draft. NOT FOR MANUFACTURE.','description':'144 LEDs and 17 top support components. Bottom connectors, routing, copper and native DRC incomplete.','tags':'[]'}))
    out.writestr('phyllo-led-draft.epru',source)
(OUT/'expected-led-netlist.json').write_text(json.dumps({p['designator']:nets(p['id']) for p in pts},indent=2),encoding='utf-8')
(OUT/'document-ids.json').write_text(json.dumps({'board':board,'schematic':sch,'pcb':pcb},indent=2),encoding='utf-8')
assert len(list(parse_records(source)))==len(records)
print(json.dumps({'records':len(records),'leds':n,'chain_length_mm':chain['length_mm'],'pcb_placement_only':True,'archive':str(OUT/'phyllo-led-draft.epro2')},ensure_ascii=False))
