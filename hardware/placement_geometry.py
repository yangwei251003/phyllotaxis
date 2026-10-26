"""Conservative 2D envelopes from real library records; not a courtyard or DRC."""
from pathlib import Path
from functools import lru_cache
from shapely.geometry import Polygon,box
from shapely.affinity import rotate,translate
from shapely.ops import unary_union
from library_inspect import read_library

MIL=.0254
libs={}
for file in (Path(__file__).resolve().parent/'library').glob('*.elibz2'):
    lib=read_library(file);libs[lib['device']['attributes']['Supplier Part']]=lib

def body_polygon(path):
    def pair(p):return len(p)==2 and all(isinstance(v,(int,float)) for v in p)
    if not pair(path[:2]):raise ValueError('Unsupported body path start')
    points=[(path[0]*MIL,path[1]*MIL)];i=2
    while i<len(path):
        if isinstance(path[i],str):
            if path[i]!='L':raise ValueError('Unsupported body command '+path[i])
            i+=1
        else:
            if not pair(path[i:i+2]):raise ValueError('Invalid coordinate pair')
            points.append((path[i]*MIL,path[i+1]*MIL));i+=2
    if points[0]!=points[-1]:raise ValueError('Unclosed body outline')
    p=Polygon(points)
    if not p.is_valid:raise ValueError('Invalid body polygon')
    return p

@lru_cache(None)
def local_envelope(part,include_body=True):
    lib=libs[part];fp=lib['device']['attributes']['Footprint'];shapes=[];body=False
    for h,b in lib['docs'][('FOOTPRINT',fp)]:
        if h['type']=='PAD':
            p=b['defaultPad']
            if p['padType'] not in {'RECT','ELLIPSE','OVAL'}:raise ValueError('Unsupported pad type')
            w,t=p['width']*MIL,p['height']*MIL
            s=rotate(box(-w/2,-t/2,w/2,t/2),b['padAngle'],origin=(0,0))
            shapes.append(translate(s,b['centerX']*MIL,b['centerY']*MIL))
        elif include_body and b.get('layerId')==48:
            if h['type']!='POLY':raise ValueError('Unsupported body primitive')
            body=True;shapes.append(body_polygon(b['path']).buffer(b.get('width',0)*MIL/2,join_style=2))
    if not shapes or (include_body and not body):raise ValueError('Missing real library geometry '+part)
    return unary_union(shapes)

def placed_envelope(part,x,y,angle=0,include_body=True):
    return translate(rotate(local_envelope(part,include_body),angle,origin=(0,0)),x,y)
