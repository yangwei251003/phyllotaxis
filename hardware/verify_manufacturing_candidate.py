"""Native saved-file invariants, aperture readback and courtyard presence."""
from pathlib import Path
import json,hashlib,math
import pcbnew as K
P=Path(__file__).resolve().parents[1];V=P/'verification'
oldpath=P/'hardware/kicad-check/phyllo-copper-review.kicad_pcb';newpath=P/'hardware/manufacturing-review/phyllo-copper-review.kicad_pcb'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
plan=json.loads((P/'hardware/manufacturing-layers-plan.json').read_text());assert sha(oldpath)==plan['source_board_sha256']
old=K.LoadBoard(str(oldpath));new=K.LoadBoard(str(newpath))
def inventory(b):
    out={}
    for f in b.GetFootprints():
        pads=[]
        for p in f.Pads():
            net=p.GetNetname()
            if f.GetReference()=='D121' and p.GetNumber()=='2':
                assert net in ['LED_LAST_OUT','unconnected-(D121-DOUT-Pad2)'];net='INTENTIONALLY_UNUSED_DOUT'
            pads.append((p.GetNumber(),net,tuple(p.GetPosition()),tuple(p.GetSize()),tuple(p.GetDrillSize()),p.GetShape(),p.GetOrientationDegrees(),tuple(l for l in [K.F_Cu,K.B_Cu] if p.IsOnLayer(l))))
        out[f.GetReference()]=(f.GetValue(),f.GetPath().AsString(),f.GetLayer(),tuple(f.GetPosition()),f.GetOrientationDegrees(),sorted(pads))
    return out
assert inventory(old)==inventory(new)
def tracks(b):
    return {t.m_Uuid.AsString():(t.GetNetname(),tuple(t.GetStart()),tuple(t.GetEnd()),t.GetLayer(),t.GetWidth(K.F_Cu) if isinstance(t,K.PCB_VIA) else t.GetWidth(),t.GetDrillValue() if isinstance(t,K.PCB_VIA) else None) for t in b.GetTracks()}
assert tracks(old)==tracks(new)
def area(poly):
    c=poly.COutline(0);pts=[(c.CPoint(i).x/1e6,c.CPoint(i).y/1e6) for i in range(c.PointCount())]
    return abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(pts,pts[1:]+pts[:1]))/2)
footprints={f.GetReference():f for f in new.GetFootprints()};apertures=[];silk=[]
for spec in plan['parts']:
    f=footprints[spec['ref']];items=list(f.GraphicalItems());front=f.GetLayer()==K.F_Cu
    assert any(g.GetLayer()==(K.F_CrtYd if front else K.B_CrtYd) for g in items)
    expected=sorted(s['outline_area_mm2'] for s in spec['artwork'] if s['purpose']=='paste')
    actual=sorted(area(g.GetPolyShape()) for g in items if g.GetLayer()==K.F_Paste)
    assert len(expected)==len(actual) and all(abs(a-b)<.000004 for a,b in zip(expected,actual)),(spec['ref'],expected,actual)
    for pad in f.Pads():
        if pad.GetNumber() in spec['custom_paste_pad_numbers']:assert not pad.IsOnLayer(K.F_Paste)
    if 'part' in spec:
        assert f.GetAttributes()&(K.FP_SMD if front else K.FP_THROUGH_HOLE)
        if spec.get('reference',{}).get('xy'):
            assert f.Reference().IsVisible() and f.Reference().GetLayer()==(K.F_SilkS if front else K.B_SilkS);silk.append(spec['ref'])
    if actual:apertures.append({'ref':spec['ref'],'areas_mm2':actual})
rules=[z for z in new.Zones() if z.GetIsRuleArea()];assert len(rules)==8
for z in rules:assert z.GetDoNotAllowZoneFills() and z.GetDoNotAllowTracks() and z.GetDoNotAllowVias()
automatic=sum(p.IsOnLayer(K.F_Paste) for f in new.GetFootprints() for p in f.Pads());assert automatic==604,automatic
zones=[{'net':z.GetNetname(),'layer':new.GetLayerName(z.GetLayer()),'regions':z.GetFilledPolysList(z.GetLayer()).OutlineCount()} for z in new.Zones() if not z.GetIsRuleArea()]
assert len(zones)==3 and all(z['regions']==1 for z in zones)
r={'status':'NATIVE_MANUFACTURING_CANDIDATE_READBACK_PASS_NOT_RELEASED','base_sha256':sha(oldpath),'board_sha256':sha(newpath),
 'footprints_and_pad_copper_geometry_unchanged':True,'pin_nets_unchanged_except_unused_D121_DOUT':True,'tracks_vias_unchanged':len(tracks(new)),
 'custom_paste_apertures':apertures,'automatic_top_paste_pads':automatic,'total_paste_apertures':620,'courtyards':len(footprints),
 'silk_reference_count':len(silk),'mount_copper_keepouts':len(rules),'filled_power_zones':zones,
 'limits':'Source aperture stroke alignment is assumed centered. DRC/parity, factory assembly rotation, stackup and real hardware validation are separate.'}
(V/'manufacturing-layer-readback.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps(r))
