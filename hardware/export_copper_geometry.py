"""Export exact native pad polygons and filled zones for local geometric analysis."""
from pathlib import Path
import json, hashlib, sys
import pcbnew as K
P=Path(__file__).resolve().parents[1]
src=Path(sys.argv[1]) if len(sys.argv)>1 else P/'hardware/kicad-check/phyllo-copper-review.kicad_pcb'
dst=Path(sys.argv[2]) if len(sys.argv)>2 else P/'verification/copper-geometry.json'
def xy(v):return [v.x/1e6,v.y/1e6]
def chain(c):return [xy(c.CPoint(i)) for i in range(c.PointCount())]
def polys(s):
    return [{'outer':chain(s.COutline(i)),'holes':[chain(s.CHole(i,j)) for j in range(s.HoleCount(i))]} for i in range(s.OutlineCount())]
b=K.LoadBoard(str(src));pads=[];tracks=[];zones=[]
for f in b.GetFootprints():
    for p in f.Pads():
        layers=[l for l in [K.F_Cu,K.B_Cu] if p.IsOnLayer(l)]
        pads.append({'ref':f.GetReference(),'num':p.GetNumber(),'net':p.GetNetname(),'xy':xy(p.GetPosition()),
          'size':xy(p.GetSize()),'drill':xy(p.GetDrillSize()),'uuid':p.m_Uuid.AsString(),'layers':layers,
          'polygons':{str(l):polys(p.GetEffectivePolygon(l,K.ERROR_OUTSIDE)) for l in layers}})
for t in b.GetTracks():
    tracks.append({'uuid':t.m_Uuid.AsString(),'net':t.GetNetname(),'a':xy(t.GetStart()),'b':xy(t.GetEnd()),
      'width':(t.GetWidth(K.F_Cu) if isinstance(t,K.PCB_VIA) else t.GetWidth())/1e6,'via':isinstance(t,K.PCB_VIA),'drill':t.GetDrillValue()/1e6 if isinstance(t,K.PCB_VIA) else 0,
      'layers':[K.F_Cu,K.B_Cu] if isinstance(t,K.PCB_VIA) else [t.GetLayer()]})
for z in b.Zones():
    if z.GetIsRuleArea():continue # actual exclusion is already reflected in filled copper
    zones.append({'net':z.GetNetname(),'layer':z.GetLayer(),'priority':z.GetAssignedPriority(),
      'outline':polys(z.Outline()),'filled':polys(z.GetFilledPolysList(z.GetLayer()))})
footprints=[{'ref':f.GetReference(),'part':str(f.GetFPID().GetLibItemName()),'xy':xy(f.GetPosition()),'angle':f.GetOrientationDegrees(),'layer':f.GetLayer()} for f in b.GetFootprints()]
dst.write_text(json.dumps({'board':str(src),'sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'pads':pads,'tracks':tracks,'zones':zones,'footprints':footprints}),encoding='utf-8')
print(json.dumps({'pads':len(pads),'tracks':len(tracks),'zones':len(zones),'out':str(dst)}))
