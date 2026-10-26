"""Derive non-copper artwork from real EasyEDA libraries and current placement."""
from pathlib import Path
import json,math,hashlib
from shapely.geometry import Polygon,Point,LineString,box
from shapely.ops import unary_union
from shapely.strtree import STRtree
from library_inspect import read_library
P=Path(__file__).resolve().parents[1];MIL=.0254
d=json.loads((P/'verification/manufacturing-source-geometry.json').read_text())
assert d['sha256']=='bc4919a0897fa3c1bd7f7599c2af06550d658c7a40389389b04f112b766af0d0'
libraries={}
for p in (P/'hardware/library').glob('*.elibz2'):
    a=read_library(p);a['file']=p.name;a['sha256']=hashlib.sha256(p.read_bytes()).hexdigest();libraries[a['device']['attributes']['Supplier Part']]=a
def points(path):
    if path[0]=='CIRCLE':
        _,x,y,r,*rest=path;return [(x+r*math.cos(k*math.tau/180),y+r*math.sin(k*math.tau/180)) for k in range(181)]
    out=[(path[0],path[1])];i=2
    while i<len(path):
        if path[i]=='L':i+=1;continue
        if path[i]=='ARC':
            sweep=math.radians(path[i+1]);end=(path[i+2],path[i+3]);start=out[-1];dx=end[0]-start[0];dy=end[1]-start[1]
            cx=(start[0]+end[0])/2-dy/(2*math.tan(sweep/2));cy=(start[1]+end[1])/2+dx/(2*math.tan(sweep/2))
            radius=math.hypot(start[0]-cx,start[1]-cy);begin=math.atan2(start[1]-cy,start[0]-cx);count=max(4,math.ceil(abs(math.degrees(sweep))/3))
            out.extend((cx+radius*math.cos(begin+sweep*k/count),cy+radius*math.sin(begin+sweep*k/count)) for k in range(1,count+1));out[-1]=end;i+=4
        else:
            assert isinstance(path[i],(int,float)),path;out.append((path[i],path[i+1]));i+=2
    return out
def transform(fp,p):
    x,y=p[0]*MIL,p[1]*MIL;angle=fp['angle']
    if fp['layer']==2:x=-x;angle=(angle-180)%360
    a=math.radians(angle);return [fp['xy'][0]+x*math.cos(a)-y*math.sin(a),fp['xy'][1]-x*math.sin(a)-y*math.cos(a)]
def polydata(g):
    if g.is_empty:return []
    gs=[g] if g.geom_type=='Polygon' else list(g.geoms)
    return [{'outer':list(s.exterior.coords)[:-1],'holes':[list(h.coords)[:-1] for h in s.interiors]} for s in gs if s.geom_type=='Polygon']
padgeoms={};mask={0:[],2:[]}
for p in d['pads']:
    padgeoms[(p['ref'],p['num'])]={int(l):unary_union([Polygon(v['outer'],v['holes']) for v in ps]) for l,ps in p['polygons'].items()}
    for l,g in padgeoms[(p['ref'],p['num'])].items():mask[l].append(g.buffer(.05))
mask_tree={l:STRtree(g) for l,g in mask.items()}
usable=Point(100,100).buffer(89.6,quad_segs=360)
result={'source_board_sha256':d['sha256'],'default_paste_expansion_mm':0,'default_paste_ratio':0,
 'solder_mask_expansion_mm':.05,'silk_to_mask_mm':.15,'courtyard_clearance_mm':.25,'parts':[],
 'assumptions':['Custom paste FILL centerline stroke copied at 0.00508mm; source docs do not specify stroke alignment. Native KiCad centered stroke used.',
 'Non-custom SMD apertures use explicitly chosen 1:1 copper opening, not an assertion of unknown source board defaults.',
 'Courtyards are body-and-pad union plus0.25mm; not a physical assembly fit certificate. Source body envelope can omit mating plugs.']}
art_occupied={0:[],2:[]};pending=[]
for fp in d['footprints']:
    p={'ref':fp['ref'],'layer':fp['layer'],'artwork':[],'custom_paste_pad_numbers':[]};padlist=[v for v in d['pads'] if v['ref']==fp['ref']]
    if not fp['part']:
        p['courtyard']=polydata(Point(fp['xy']).buffer(3.5,quad_segs=48));p['mount_copper_keepout_radius_mm']=3.5;result['parts'].append(p);continue
    lib=libraries[fp['part']];p.update({'part':fp['part'],'source_library_sha256':lib['sha256']})
    near=mask_tree[fp['layer']].query(Point(fp['xy']).buffer(20))
    local_mask=unary_union([mask[fp['layer']][int(j)] for j in near])
    # Independent source-to-native pad center check also verifies mirroring.
    for pad in padlist:
        source=lib['pads'][pad['num']];wanted=transform(fp,[source['centerX'],source['centerY']]);assert math.dist(wanted,pad['xy'])<.000002,(fp['ref'],pad['num'],wanted,pad['xy'])
        if source.get('topPasteExpansion') is not None and source['topPasteExpansion']*MIL<-10:p['custom_paste_pad_numbers'].append(pad['num'])
    body=[]
    for h,b in lib['docs'][('FOOTPRINT',lib['device']['attributes']['Footprint'])]:
        if h['type'] not in ['POLY','FILL'] or b.get('layerId') not in [3,7,48]:continue
        width=b.get('width',0)*MIL
        if b['layerId']==3 and h['type']=='POLY':width=max(.12,width)
        if b['layerId']==48:
            body.append(Polygon([transform(fp,q) for q in points(b['path'])]));continue
        side=fp['layer'];target='paste' if b['layerId']==7 else 'silk'
        if h['type']=='FILL':
            rings=[[transform(fp,q) for q in points(path)] for path in b['path']];shape=Polygon(rings[0],rings[1:]);assert shape.is_valid
            if target=='paste':
                assert side==0 and len(rings)==1 and b['fillStyle']=='SOLID'
                p['artwork'].append({'type':'polygon','purpose':'paste','source_id':h['id'],'width':width,'polygons':polydata(shape),'outline_area_mm2':shape.area});continue
            shape=shape.buffer(width/2).difference(local_mask.buffer(.15)).intersection(usable)
            for q in polydata(shape):
                if Polygon(q['outer'],q['holes']).area>.015:p['artwork'].append({'type':'polygon','purpose':'silk','source_id':h['id'],'width':0,'polygons':[q]});art_occupied[side].append(Polygon(q['outer'],q['holes']))
        else:
            rawpoints=[transform(fp,q) for q in points(b['path'])];line=LineString(rawpoints)
            keepout=local_mask.buffer(.15+width/2)
            if not line.intersects(keepout) and usable.buffer(-width/2).contains(line):
                if b['path'][0]=='CIRCLE':
                    p['artwork'].append({'type':'circle','purpose':'silk','source_id':h['id'],'width':width,'center':transform(fp,b['path'][1:3]),'radius':b['path'][3]*MIL});art_occupied[side].append(line.buffer(width/2));continue
                if len(b['path'])==6 and b['path'][2]=='ARC':
                    p['artwork'].append({'type':'arc','purpose':'silk','source_id':h['id'],'width':width,'points':[rawpoints[0],rawpoints[len(rawpoints)//2],rawpoints[-1]]});art_occupied[side].append(line.buffer(width/2));continue
            line=line.difference(keepout).intersection(usable.buffer(-width/2))
            lines=[line] if line.geom_type=='LineString' else list(getattr(line,'geoms',[]))
            for segment in lines:
                if segment.geom_type=='LineString' and segment.length>.08:
                    p['artwork'].append({'type':'line','purpose':'silk','source_id':h['id'],'width':width,'points':list(segment.coords)});art_occupied[side].append(segment.buffer(width/2))
    covered=unary_union(body+[padgeoms[(v['ref'],v['num'])][side] for v in padlist]);p['courtyard']=polydata(covered.buffer(.25,join_style=2))
    assert len(p['courtyard'])==1,(p['ref'],'disjoint courtyard')
    if p['custom_paste_pad_numbers']:assert len([a for a in p['artwork'] if a['purpose']=='paste'])==len(p['custom_paste_pad_numbers'])
    pending.append((fp,p,covered.bounds));result['parts'].append(p)
# Place readable references without crossing openings, graphics, or the board edge.
occupied={l:STRtree(art_occupied[l]+[g.buffer(.15) for g in mask[l]]) for l in [0,2]};placed_refs={0:[],2:[]}
for fp,p,bounds in sorted(pending,key=lambda item:(item[0]['ref'].startswith('D'),item[0]['ref'])):
    x,y=fp['xy'];x0,y0,x1,y1=bounds;w=max(.9,len(fp['ref'])*.8+.25);height=1.25
    choices=[(x,y0-1.0),(x,y1+1.0),(x0-w/2-.4,y),(x1+w/2+.4,y),(x,y)]
    if fp['part']=='C52941391':choices=[(x,y),*choices]
    placed=None
    for px,py in choices:
        region=box(px-w/2,py-height/2,px+w/2,py+height/2)
        if usable.contains(region) and len(occupied[fp['layer']].query(region,predicate='intersects'))==0 and not any(region.intersects(r) for r in placed_refs[fp['layer']]):placed=[px,py];break
    if placed:
        p['reference']={'xy':placed,'height_mm':.8,'stroke_mm':.12};placed_refs[fp['layer']].append(region.buffer(.1))
    else:p['reference']={'visible_on_silk':False,'reason':'No clear small local position; reference retained on assembly drawing.'}
(P/'hardware/manufacturing-layers-plan.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({'parts':len(result['parts']),'custom_paste_apertures':sum(a['purpose']=='paste' for p in result['parts'] for a in p['artwork']),
 'silk_refs':sum('xy' in p.get('reference',{}) for p in result['parts']),'references_retained_only_on_assembly':[p['ref'] for p in result['parts'] if p.get('reference',{}).get('visible_on_silk') is False]}))
