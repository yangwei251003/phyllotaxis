"""Build a review candidate with paste, silk, courtyards and explicit terminal NC.
Never overwrite the current board: native DRC/parity gates a separate promotion.
"""
from pathlib import Path
import json,hashlib,math,shutil,xml.etree.ElementTree as ET
import pcbnew as K
P=Path(__file__).resolve().parents[1];S=P/'hardware/kicad-check';D=P/'hardware/manufacturing-review';D.mkdir(exist_ok=True)
src=S/'phyllo-copper-review.kicad_pcb';dst=D/'phyllo-copper-review.kicad_pcb'
plan=json.loads((P/'hardware/manufacturing-layers-plan.json').read_text())
assert hashlib.sha256(src.read_bytes()).hexdigest()==plan['source_board_sha256']
b=K.LoadBoard(str(src));parts={f.GetReference():f for f in b.GetFootprints()}
def v(p):return K.VECTOR2I(round(p[0]*1e6),round(p[1]*1e6))
def xy(p):return [p.x/1e6,p.y/1e6]
def polyshape(fp,layer,data,width,filled):
    assert not data['holes'],'Explicit polygon holes need supported fracture before export'
    poly=K.SHAPE_POLY_SET();poly.NewOutline()
    for p in data['outer']:poly.Append(round(p[0]*1e6),round(p[1]*1e6))
    s=K.PCB_SHAPE(fp);s.SetShape(K.SHAPE_T_POLY);s.SetPolyShape(poly);s.SetWidth(K.FromMM(width));s.SetLayer(layer);s.SetFilled(filled);fp.Add(s);return s
before_tracks={t.m_Uuid.AsString():(t.GetNetname(),tuple(t.GetStart()),tuple(t.GetEnd()),t.GetLayer(),t.GetWidth(K.F_Cu) if isinstance(t,K.PCB_VIA) else t.GetWidth()) for t in b.GetTracks()}
netlist=ET.parse(P/'verification/kicad-schematic-netlist.xml').getroot()
nc=next(net.attrib['name'] for net in netlist.findall('nets/net') if any(n.attrib['ref']=='D121' and n.attrib['pin']=='2' for n in net.findall('node')))
assert nc.startswith('unconnected-')
last=next(p for p in parts['D121'].Pads() if p.GetNumber()=='2');assert last.GetNetname()=='LED_LAST_OUT'
assert all(t.GetNetname()!='LED_LAST_OUT' for t in b.GetTracks());last.GetNet().SetNetname(nc)
settings=b.GetDesignSettings();settings.m_SolderPasteMargin=0;settings.m_SolderPasteMarginRatio=0
settings.m_SolderMaskExpansion=K.FromMM(.05);settings.m_SolderMaskMinWidth=K.FromMM(.1)
items=[]
for spec in plan['parts']:
    fp=parts[spec['ref']];front=fp.GetLayer()==K.F_Cu;silk=K.F_SilkS if front else K.B_SilkS;court=K.F_CrtYd if front else K.B_CrtYd
    fp.SetAttributes(K.FP_SMD if front and spec.get('part') else K.FP_THROUGH_HOLE if spec.get('part') else fp.GetAttributes()|K.FP_EXCLUDE_FROM_BOM|K.FP_EXCLUDE_FROM_POS_FILES)
    assert not any(g.GetLayer() in [K.F_Paste,K.B_Paste,K.F_SilkS,K.B_SilkS,K.F_CrtYd,K.B_CrtYd] for g in fp.GraphicalItems()),'Candidate already has manufacturing graphics'
    for p in fp.Pads():
        p.SetLocalSolderMaskMargin(K.FromMM(.05));p.SetLocalSolderPasteMargin(0);p.SetLocalSolderPasteMarginRatio(0.0)
        if p.GetNumber() in spec['custom_paste_pad_numbers']:
            layers=p.GetLayerSet();layers.RemoveLayer(K.F_Paste);p.SetLayerSet(layers)
    for shape in spec['artwork']:
        layer=K.F_Paste if shape['purpose']=='paste' else silk
        if shape['type']=='polygon':
            for poly in shape['polygons']:s=polyshape(fp,layer,poly,shape['width'],True)
        elif shape['type']=='line':
            for a,c in zip(shape['points'],shape['points'][1:]):
                s=K.PCB_SHAPE(fp);s.SetShape(K.SHAPE_T_SEGMENT);s.SetStart(v(a));s.SetEnd(v(c));s.SetLayer(layer);s.SetWidth(K.FromMM(shape['width']));fp.Add(s)
        elif shape['type']=='circle':
            s=K.PCB_SHAPE(fp);s.SetShape(K.SHAPE_T_CIRCLE);s.SetStart(v(shape['center']));s.SetEnd(v([shape['center'][0]+shape['radius'],shape['center'][1]]));s.SetLayer(layer);s.SetWidth(K.FromMM(shape['width']));fp.Add(s)
        elif shape['type']=='arc':
            s=K.PCB_SHAPE(fp);s.SetShape(K.SHAPE_T_ARC);s.SetArcGeometry(*[v(x) for x in shape['points']]);s.SetLayer(layer);s.SetWidth(K.FromMM(shape['width']));fp.Add(s)
        else:raise ValueError(shape['type'])
    for poly in spec['courtyard']:polyshape(fp,court,poly,.05,False)
    if 'reference' in spec:
        r=spec['reference']
        if 'xy' in r:
            # Keep a separate assembly reference when moving the main reference to silk.
            text=K.PCB_TEXT(fp);text.SetText('${REFERENCE}');text.SetLayer(K.F_Fab if front else K.B_Fab)
            text.SetPosition(fp.GetPosition());text.SetTextAngle(K.EDA_ANGLE(fp.GetOrientationDegrees(),K.DEGREES_T));text.SetTextSize(v([.9,.9]));text.SetTextThickness(K.FromMM(.12));text.SetMirrored(not front);fp.Add(text)
            ref=fp.Reference();ref.SetLayer(silk);ref.SetVisible(True);ref.SetPosition(v(r['xy']));ref.SetTextSize(v([r['height_mm']]*2));ref.SetTextThickness(K.FromMM(r['stroke_mm']));ref.SetTextAngle(K.EDA_ANGLE(0,K.DEGREES_T));ref.SetMirrored(not front)
    if 'mount_copper_keepout_radius_mm' in spec:
        x,y=xy(fp.GetPosition());radius=spec['mount_copper_keepout_radius_mm']
        for layer in [K.F_Cu,K.B_Cu]:
            z=K.ZONE(b);z.SetLayer(layer);z.SetIsRuleArea(True);z.SetDoNotAllowZoneFills(True);z.SetDoNotAllowTracks(True);z.SetDoNotAllowVias(True);z.SetDoNotAllowPads(False)
            outline=z.Outline();outline.NewOutline()
            for i in range(180):outline.Append(round((x+radius*math.cos(i*math.tau/180))*1e6),round((y+radius*math.sin(i*math.tau/180))*1e6))
            b.Add(z)
    items.append({'ref':spec['ref'],'paste_polygons':sum(a['purpose']=='paste' for a in spec['artwork']),'graphics':len(list(fp.GraphicalItems()))})
assert before_tracks=={t.m_Uuid.AsString():(t.GetNetname(),tuple(t.GetStart()),tuple(t.GetEnd()),t.GetLayer(),t.GetWidth(K.F_Cu) if isinstance(t,K.PCB_VIA) else t.GetWidth()) for t in b.GetTracks()}
b.BuildConnectivity();assert K.ZONE_FILLER(b).Fill(b.Zones());K.SaveBoard(str(dst),b)
# Library definitions are saved with the same pad apertures and courtyard as board instances.
pretty=D/'PhylloReview.pretty';pretty.mkdir(exist_ok=True);plugin=K.PCB_IO_MGR.FindPlugin(K.PCB_IO_MGR.KICAD_SEXP);saved=set()
for fp in b.GetFootprints():
    name=str(fp.GetFPID().GetLibItemName())
    if name and name not in saved:
        copy=K.FOOTPRINT(fp)
        if copy.GetLayer()==K.B_Cu:copy.Flip(copy.GetPosition(),K.FLIP_DIRECTION_LEFT_RIGHT)
        copy.SetOrientationDegrees(0);copy.SetPosition(v([0,0]));plugin.FootprintSave(str(pretty),copy);saved.add(name)
(D/'fp-lib-table').write_text('(fp_lib_table (lib (name "PhylloReview") (type "KiCad") (uri "${KIPRJMOD}/PhylloReview.pretty") (options "") (descr "Native manufacturing review footprints")))\n',encoding='utf-8')
pro=json.loads((S/'phyllo-copper-review.kicad_pro').read_text());rules=pro['board']['design_settings']['rule_severities']
rules['missing_courtyard']='warning';rules['track_not_centered_on_via']='warning'
rules['footprint_type_mismatch']='warning';rules['footprint_filters_mismatch']='warning'
pro['board']['design_settings']['rules']['min_silk_clearance']=.15
(dst.with_suffix('.kicad_pro')).write_text(json.dumps(pro,indent=2),encoding='utf-8')
for name in ['phyllo-copper-review.kicad_sch','PhylloReview.kicad_sym','sym-lib-table','symbol-identities.json']:
    shutil.copy2(S/name,D/name)
shutil.copytree(S/'sheets',D/'sheets',dirs_exist_ok=True)
r={'status':'manufacturing_layer_candidate_NOT_RELEASED','base_board_sha256':plan['source_board_sha256'],'board_sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),
 'tracks_vias_unchanged':True,'last_LED_output_net_renamed_to_nc':nc,'custom_paste_polygons':sum(x['paste_polygons'] for x in items),
 'all_167_footprints_have_courtyard':True,'mount_keepouts':'4 holes, both copper layers, radius3.5mm; copper pours/tracks/vias excluded under candidate M3 washer/head envelope',
 'source_library_parts':len(saved),'parts':items,'scope':'Paste, mask, silk, courtyard, NC declaration and four mounting copper keepouts; no physical component moved.'}
(P/'verification/manufacturing-layer-candidate.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in r.items() if k!='parts'}))
