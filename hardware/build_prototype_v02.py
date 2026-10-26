"""Revise only the four bulk-capacitor islands on a fresh v01 board copy.
Run with KiCad Python. Official F61 lands: gap1.9, length3.5, width1.6 mm.
"""
from pathlib import Path
import pcbnew as K
import math,json,hashlib,uuid
P=Path(__file__).resolve().parents[1];S=P/'hardware/kicad-check';D=P/'hardware/prototype-v02'
src=S/'phyllo-copper-review.kicad_pcb';assert hashlib.sha256(src.read_bytes()).hexdigest()=='17f93c409632b65271121363c62a9ff14ae228ac94b24b676f731eafd3b3479e'
b=K.LoadBoard(str(src));fps={f.GetReference():f for f in b.GetFootprints()}
identities=json.loads((D/'symbol-identities.json').read_text())
def v(p):return K.VECTOR2I(round(p[0]*1e6),round(p[1]*1e6))
def xy(p):return [p.x/1e6,p.y/1e6]
def hash_geometry(f):return [xy(f.GetPosition()),f.GetOrientationDegrees(),[(p.GetNumber(),p.GetNetname(),xy(p.GetPosition())) for p in f.Pads()]]
unchanged={r:hash_geometry(f) for r,f in fps.items() if r not in ['C1','C2','C3','C4']}
centers=[xy(fps[f'C{i}'].GetPosition()) for i in range(1,5)]
# Only GND branches/through-vias within 7mm of the four former capacitors.
# Inspect/re-fill/DRC after regeneration; never remove data-chain tracks.
removed=[];detached=[]
for t in list(b.GetTracks()):
    if t.GetNetname()=='GND' and any(math.dist(xy(t.GetStart()),c)<7 and math.dist(xy(t.GetEnd()),c)<7 for c in centers):
        removed.append({'uuid':t.m_Uuid.AsString(),'a':xy(t.GetStart()),'b':xy(t.GetEnd()),'via':isinstance(t,K.PCB_VIA)})
        detached.append(t);b.Remove(t)
for ref in ['C1','C2','C3','C4']:b.Remove(fps[ref])
part='APXF100ARA271MF61G'
template=K.FOOTPRINT(b);template.SetFPID(K.LIB_ID('PhylloReview',part));template.SetValue(part);template.SetAttributes(K.FP_SMD);template.SetLayer(K.F_Cu)
template.Value().SetVisible(False)
template.GetField(K.FIELD_T_DATASHEET).SetText('https://www.chemi-con.co.jp/products/relatedfiles/capacitor/catalog/PXFRA-e.PDF')
template.GetField(K.FIELD_T_DESCRIPTION).SetText('Chemi-Con PXF F61; pin1 positive; black stripe negative; official NPCAP land 1.9/3.5/1.6 mm')
supplier=K.PCB_FIELD(template,K.FIELD_T_USER,'Manufacturer Part');supplier.SetText(part);supplier.SetVisible(False);template.Add(supplier)
for number,x in [('1',-2.7),('2',2.7)]:
    p=K.PAD(template);p.SetNumber(number);p.SetAttribute(K.PAD_ATTRIB_SMD);p.SetShape(K.PAD_SHAPE_RECT)
    p.SetPosition(v([x,0]));p.SetSize(v([3.5,1.6]));p.SetLayerSet(K.PAD.SMDMask());p.SetLocalSolderMaskMargin(K.FromMM(.05));p.SetLocalSolderPasteMargin(0);p.SetLocalSolderPasteMarginRatio(0.0)
    p.SetLocalZoneConnection(K.ZONE_CONNECTION_FULL);template.Add(p)
def line(a,c,layer,width=.12):
    g=K.PCB_SHAPE(template);g.SetShape(K.SHAPE_T_SEGMENT);g.SetStart(v(a));g.SetEnd(v(c));g.SetLayer(layer);g.SetWidth(K.FromMM(width));template.Add(g)
def outline(points,layer,width):
    for a,c in zip(points,points[1:]+points[:1]):line(a,c,layer,width)
# Body: negative side square corners, positive side chamfer; see official PXF drawing.
outline([[-3.3,-2.2],[-2.2,-3.3],[3.3,-3.3],[3.3,3.3],[-2.2,3.3],[-3.3,2.2]],K.F_Fab,.1)
circle=K.PCB_SHAPE(template);circle.SetShape(K.SHAPE_T_CIRCLE);circle.SetStart(v([0,0]));circle.SetEnd(v([3.15,0]));circle.SetLayer(K.F_Fab);circle.SetWidth(K.FromMM(.1));template.Add(circle)
outline([[-4.7,-1.05],[-3.55,-1.05],[-3.55,-3.55],[3.55,-3.55],[3.55,-1.05],[4.7,-1.05],[4.7,1.05],[3.55,1.05],[3.55,3.55],[-3.55,3.55],[-3.55,1.05],[-4.7,1.05]],K.F_CrtYd,.05)
for side in [-1,1]:line([-2.2,side*3.45],[3.45,side*3.45],K.F_SilkS)
# '+' on positive side inside the body, clear of the copper lands; '-' negative.
line([-2.65,-2.55],[-1.85,-2.55],K.F_SilkS,.15);line([-2.25,-2.95],[-2.25,-2.15],K.F_SilkS,.15)
line([1.85,-2.55],[2.65,-2.55],K.F_Fab,.15)
template.Reference().SetLayer(K.F_SilkS);template.Reference().SetTextSize(v([1,1]));template.Reference().SetTextThickness(K.FromMM(.15));template.Reference().SetPosition(v([0,4.4]))
plugin=K.PCB_IO_MGR.FindPlugin(K.PCB_IO_MGR.KICAD_SEXP);plugin.FootprintSave(str(D/'PhylloReview.pretty'),template)
positions=[('C1',177.578482,68.789760,25),('C6',173.774918,60.632990,25),('C2',68.789760,22.421517,115),('C7',60.632990,26.225081,115),('C3',22.421517,131.210239,205),('C8',26.225081,139.367009,205),('C4',131.210239,177.578482,295),('C9',139.367009,173.774918,295)]
netnames={n.GetNetname():n for n in b.GetNetsByNetcode().values()}
added=[]
for ref,x,y,angle in positions:
    # Fourth pair rotates as a unit away from J2's through-hole tails.
    if ref in ['C4','C9']:
        delta=math.radians(8);dx,dy=x-100,y-100
        x,y=100+dx*math.cos(delta)+dy*math.sin(delta),100-dx*math.sin(delta)+dy*math.cos(delta);angle+=8
    fp=K.FOOTPRINT(template);fp.SetReference(ref);fp.SetPath(K.KIID_PATH(identities[ref]['path']))
    # KiCad copy preserves UUIDs; every board instance AND child needs a distinct identity.
    for index,item in enumerate([fp,*fp.Pads(),*fp.GraphicalItems(),*fp.GetFields()]):
        item.m_Uuid.Clone(K.KIID(str(uuid.uuid5(uuid.NAMESPACE_URL,f'phyllo-proto02/{ref}/{index}'))))
    b.Add(fp)
    fp.SetOrientationDegrees(angle);fp.SetPosition(v([x,y]));fp.GetField(K.FIELD_T_DESCRIPTION).SetText(identities[ref]['description'])
    pads={p.GetNumber():p for p in fp.Pads()}
    for number,net in [('1','5V_LED'),('2','GND')]:pads[number].SetNet(netnames[net])
    # Independent readback invariant: plus must face inward, minus outward.
    assert math.dist(xy(pads['1'].GetPosition()),[100,100]) < math.dist(xy(pads['2'].GetPosition()),[100,100]),ref
    theta=math.radians(angle);p2=xy(pads['2'].GetPosition())
    for offset in [-1.7,1.7]:
        end=[p2[0]+offset*math.sin(theta),p2[1]+offset*math.cos(theta)]
        t=K.PCB_TRACK(b);t.SetStart(pads['2'].GetPosition());t.SetEnd(v(end));t.SetWidth(K.FromMM(.65));t.SetLayer(K.F_Cu);t.SetNet(netnames['GND']);b.Add(t)
        via=K.PCB_VIA(b);via.SetPosition(v(end));via.SetWidth(K.FromMM(.8));via.SetDrill(K.FromMM(.4));via.SetViaType(K.VIATYPE_THROUGH);via.SetLayerPair(K.F_Cu,K.B_Cu);via.SetNet(netnames['GND']);b.Add(via)
    added.append({'ref':ref,'xy':[x,y],'rotation_native_deg':angle,'pads':{n:xy(p.GetPosition()) for n,p in pads.items()}})
for fp in b.GetFootprints():
    if fp.GetReference() in unchanged:assert hash_geometry(fp)==unchanged[fp.GetReference()]
    if fp.Reference().GetLayer() in [K.F_SilkS,K.B_SilkS]:
        fp.Reference().SetTextSize(v([1,1]));fp.Reference().SetTextThickness(K.FromMM(.15))
b.BuildConnectivity();assert K.ZONE_FILLER(b).Fill(b.Zones());out=D/'phyllo-copper-review.kicad_pcb';K.SaveBoard(str(out),b)
report={'status':'candidate_requires_DRC_ERC_parity','base_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'board_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'unchanged_part_geometries':len(unchanged),'capacitors':added,'removed_ground_features':removed,'land':{'gap':1.9,'length':3.5,'width':1.6,'source':'ChemiCon-NPCAP-reflow-2026.pdf'},'warning':'Native rotation verified by actual pad positions; advisory 335/245/155/65 angles were rejected because KiCad uses the opposite sign for board Y.'}
(P/'verification/prototype-v02-generation.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k not in ['capacitors','removed_ground_features']},ensure_ascii=False))
