"""Derive a COPPER-GEOMETRY review board using installed KiCad's native API.

EasyEDA .epro2 is not accepted by KiCad 10.0.5's importer. This limited adapter
reads the actual candidate PCB records and real library pad records. It is NOT
a complete project importer: no schematic, routing, 3D, or manufacturing output.
Unsupported conductive geometry fails closed. The original files are untouched.
Bottom connector overlay is a new native design step, explicitly sourced from
bottom-connectors.json and power_candidate.json, not an imported placement.
Run with KiCad/10.0/bin/python.exe (pcbnew bindings).
"""
import hashlib,json,math
from pathlib import Path
import pcbnew as K
from eda_format import parse_records
from library_inspect import read_library

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'hardware/eda/phyllo-led-draft.epru'
OUT=ROOT/'hardware/kicad-check';OUT.mkdir(exist_ok=True)
existing=OUT/'phyllo-copper-review.kicad_pcb'
if existing.exists():
    previous_board=K.LoadBoard(str(existing))
    if list(previous_board.GetTracks()):
        raise RuntimeError('The review board now has routing. Do not regenerate placement over it; use the saved placement baseline or a new candidate path.')
MIL=.0254
ORIGIN=(100.,100.)
libs={}; footprints={}
for file in (ROOT/'hardware/library').glob('*.elibz2'):
    lib=read_library(file)
    libs[lib['device_id']]=lib
    footprints[lib['device']['attributes']['Footprint']]=lib
records=[];active=False
for h,b in parse_records(SOURCE.read_text(encoding='utf-8')):
    if h['type']=='DOCHEAD':active=b['docType']=='PCB'
    elif active:records.append((h,b))
attrs={};nets={};components={}
for h,b in records:
    if h['type']=='ATTR':attrs.setdefault(b['parentId'],{})[b['key']]=b['value']
    elif h['type']=='PAD_NET':
        _,parent,number,pad_id=json.loads(h['id'])
        nets[(parent,number)]={'name':b['padNet'],'library_pad_id':pad_id}
    elif h['type']=='COMPONENT':components[h['id']]=b
assert len(components)==161
source_component_count=len(components)
bottom_spec=json.loads((ROOT/'hardware/bottom-connectors.json').read_text(encoding='utf-8'))
power={c['ref']:c for c in json.loads((ROOT/'hardware/power_candidate.json').read_text(encoding='utf-8'))['components']}
bottom_refs=set()
for p in bottom_spec['components']:
    ref=p['ref'];assert ref not in components and power[ref]['part']==p['part']
    lib=next(l for l in libs.values() if l['device']['attributes']['Supplier Part']==p['part'])
    components[ref]={'layerId':2,'x':p['x']/MIL,'y':p['y']/MIL,'angle':p['physical_angle_ccw']}
    attrs[ref]={'Device':lib['device_id'],'Footprint':lib['device']['attributes']['Footprint']}
    # KiCad represents explicit schematic NC markers by unique isolated nets.
    # They do not imply that these mounting features are electrical terminals.
    for n,pad in lib['pads'].items():
        name=power[ref]['pins'][n]
        nets[(ref,n)]={'name':name if name is not None else f'unconnected-({ref}-Pad{n})', 'library_pad_id':pad['id']}
    bottom_refs.add(ref)

def vec(x,y):return K.VECTOR2I(K.FromMM(x),K.FromMM(y))
def world(x,y):return vec(ORIGIN[0]+x,ORIGIN[1]-y)
def rotated(x,y,a):
    r=math.radians(a);return x*math.cos(r)-y*math.sin(r),x*math.sin(r)+y*math.cos(r)
def outline_points(path):
    points=[];i=0
    while i<len(path):
        if isinstance(path[i],str):
            assert path[i]=='L',f'Unsupported body command: {path[i]}'
            i+=1
        else:
            assert isinstance(path[i+1],(int,float))
            points.append((path[i]*MIL,path[i+1]*MIL));i+=2
    return points

board=K.BOARD();board.SetCopperLayerCount(2)
board.GetDesignSettings().SetBoardThickness(K.FromMM(1.6))
net_objects={}
for name in sorted({d['name'] for d in nets.values() if d['name']}):
    item=K.NETINFO_ITEM(board,name);board.Add(item);net_objects[name]=item
expected=[];paste_overrides=[]
pretty=OUT/'PhylloReview.pretty';pretty.mkdir(exist_ok=True)
native_plugin=K.PCB_IO_MGR.FindPlugin(K.PCB_IO_MGR.KICAD_SEXP)
bottom_library_parts=set()
identities_path=OUT/'symbol-identities.json'
identities=json.loads(identities_path.read_text()) if identities_path.exists() else {}
for ref,placement in components.items():
    is_bottom=ref in bottom_refs
    assert placement['layerId']==(2 if is_bottom else 1)
    metadata=attrs[ref];lib=libs[metadata['Device']]
    part=lib['device']['attributes']['Supplier Part']
    fp_uuid=metadata['Footprint']
    assert fp_uuid==lib['device']['attributes']['Footprint']
    final_a=placement['angle'];a=0 if is_bottom else final_a
    x=placement['x']*MIL;y=placement['y']*MIL
    fp=K.FOOTPRINT(board);fp.SetReference(ref);fp.SetValue(lib['device']['attributes']['Manufacturer Part'])
    fp.SetFPID(K.LIB_ID('PhylloReview',part))
    if ref in identities:
        assert identities[ref]['part']==part
        fp.SetPath(K.KIID_PATH(identities[ref]['path']))
        fp.GetField(K.FIELD_T_DESCRIPTION).SetText(identities[ref]['description'])
    supplier=K.PCB_FIELD(fp,K.FIELD_T_USER,'Supplier Part')
    supplier.SetText(part);supplier.SetVisible(False);fp.Add(supplier)
    fp.SetAttributes(K.FP_THROUGH_HOLE if is_bottom else K.FP_SMD);fp.SetLayer(K.F_Cu)
    fp.SetPosition(world(x,y));fp.SetOrientationDegrees(a)
    fp.Value().SetVisible(False)
    # These are review annotations, not a substitute for source manufacturing silk.
    fp.Reference().SetLayer(K.F_Fab)
    fp.Reference().SetTextSize(vec(.9,.9));fp.Reference().SetTextThickness(K.FromMM(.12))
    fp.Reference().SetPosition(world(x,y+4))
    board.Add(fp)
    for h,b in lib['docs'][('FOOTPRINT',fp_uuid)]:
        if h['type']=='CANVAS':
            assert not b.get('originX') and not b.get('originY'),'Nonzero footprint origin requires explicit conversion'
        elif h['type']=='PAD':
            assert not b['specialPad']
            assert (b['layerId']==12 and b['hole'] and b['plated']) if is_bottom else (b['layerId']==1 and b['hole'] is None)
            shape=b['defaultPad'];kind=shape['padType']
            assert kind in {'RECT','ELLIPSE','OVAL'}
            assert not shape.get('radius'),'Rounded rectangle conversion not implemented'
            number=str(b['num']);wire=nets[(ref,number)]
            assert wire['library_pad_id']==h['id'],(ref,number,h['id'],wire)
            pad=K.PAD(fp);pad.SetNumber(number);pad.SetAttribute(K.PAD_ATTRIB_PTH if is_bottom else K.PAD_ATTRIB_SMD)
            w,t=shape['width']*MIL,shape['height']*MIL
            pad.SetShape(K.PAD_SHAPE_RECT if kind=='RECT' else (K.PAD_SHAPE_CIRCLE if abs(w-t)<1e-8 else K.PAD_SHAPE_OVAL))
            pad.SetSize(vec(w,t));pad.SetLayerSet(K.PAD.PTHMask() if is_bottom else K.PAD.SMDMask())
            if is_bottom:
                assert b['hole']['holeType']=='ROUND'
                pad.SetDrillShape(K.PAD_DRILL_SHAPE_CIRCLE)
                pad.SetDrillSize(vec(b['hole']['width']*MIL,b['hole']['height']*MIL))
            lx,ly=rotated(b['centerX']*MIL,b['centerY']*MIL,a)
            gx,gy=x+lx,y+ly
            pad.SetPosition(world(gx,gy));pad.SetOrientationDegrees(a+b['padAngle'])
            pad.SetOffset(vec(b.get('padOffsetX',0)*MIL,-b.get('padOffsetY',0)*MIL))
            if wire['name']:pad.SetNet(net_objects[wire['name']])
            fp.Add(pad)
            mask=b.get('topSolderExpansion')
            if mask is not None:pad.SetLocalSolderMaskMargin(K.FromMM(mask*MIL))
            paste=b.get('topPasteExpansion')
            if paste is not None and paste*MIL < -10:
                paste_overrides.append({'ref':ref,'pad':number,'source_mil':paste,'review_margin_mm':0})
            elif paste is not None:pad.SetLocalSolderPasteMargin(K.FromMM(paste*MIL))
            if is_bottom:
                dx,dy=rotated(-b['centerX']*MIL,b['centerY']*MIL,final_a)
                egx,egy=x+dx,y+dy;eangle=(180-b['padAngle']+final_a)%360
            else:egx,egy,eangle=gx,gy,(a+b['padAngle'])%360
            expected.append({'ref':ref,'pad':number,'net':wire['name'],'x_mm':ORIGIN[0]+egx,'y_mm':ORIGIN[1]-egy,
                             'width_mm':w,'height_mm':t,'angle_deg':eangle,'bottom':is_bottom,
                             'drill_mm':b['hole']['width']*MIL if is_bottom else 0})
        elif h['type']=='POLY' and b.get('layerId')==48:
            pts=outline_points(b['path'])
            for p,q in zip(pts,pts[1:]):
                ax,ay=rotated(*p,a);bx,by=rotated(*q,a)
                line=K.PCB_SHAPE(fp);line.SetShape(K.SHAPE_T_SEGMENT);line.SetLayer(K.F_Fab)
                line.SetStart(world(x+ax,y+ay));line.SetEnd(world(x+bx,y+by))
                line.SetWidth(K.FromMM(max(.05,b.get('width',0)*MIL)));fp.Add(line)
    if is_bottom:
        # Save the reusable library footprint on F.Cu, then place the board copy
        # with native flip/rotate APIs. Compare against independent math below.
        native_plugin.FootprintSave(str(pretty),fp);bottom_library_parts.add(part)
        fp.Flip(fp.GetPosition(),K.FLIP_DIRECTION_LEFT_RIGHT)
        fp.Rotate(fp.GetPosition(),K.EDA_ANGLE(final_a,K.DEGREES_T))
        assert fp.GetLayer()==K.B_Cu

# Original candidate outline is a 360-segment approximation; preserve its path.
for h,b in records:
    if h['type']=='POLY' and b.get('polyType')=='BOARD_OUTLINE':
        pts=outline_points(b['path'])
        for p,q in zip(pts,pts[1:]):
            edge=K.PCB_SHAPE(board);edge.SetShape(K.SHAPE_T_SEGMENT);edge.SetLayer(K.Edge_Cuts)
            edge.SetStart(world(*p));edge.SetEnd(world(*q));edge.SetWidth(K.FromMM(.05));board.Add(edge)
    elif h['type']=='PAD':
        assert not b['plated'] and b['hole']['holeType']=='ROUND' and not b['num']
        mount=K.FOOTPRINT(board);mount.SetReference(h['id']);mount.SetValue('NPTH_3.4mm')
        mount.SetAttributes(K.FP_BOARD_ONLY|K.FP_EXCLUDE_FROM_BOM|K.FP_EXCLUDE_FROM_POS_FILES)
        mount.SetPosition(world(b['centerX']*MIL,b['centerY']*MIL));mount.Reference().SetVisible(False);mount.Value().SetVisible(False)
        hole=K.PAD(mount);hole.SetAttribute(K.PAD_ATTRIB_NPTH);hole.SetShape(K.PAD_SHAPE_CIRCLE)
        hole.SetPosition(mount.GetPosition());hole.SetSize(vec(b['hole']['width']*MIL,b['hole']['height']*MIL))
        hole.SetDrillSize(hole.GetSize());hole.SetLayerSet(K.PAD.UnplatedHoleMask());mount.Add(hole);board.Add(mount)
    elif h['type'] in {'LINE','VIA','POUR','FILL','POURED'}:
        raise ValueError('Conductive routing appeared in the source; adapter does not cover it')

path=OUT/'phyllo-copper-review.kicad_pcb'
exported=set(bottom_library_parts)
for fp in board.GetFootprints():
    name=str(fp.GetFPID().GetLibItemName())
    if not name or name in exported:continue
    native_plugin.FootprintSave(str(pretty),fp)
    assert (pretty/(name+'.kicad_mod')).is_file()
    exported.add(name)
(OUT/'fp-lib-table').write_text('(fp_lib_table (lib (name "PhylloReview") (type "KiCad") (uri "${KIPRJMOD}/PhylloReview.pretty") (options "") (descr "REVIEW-ONLY pads from saved EasyEDA libraries")))\n',encoding='utf-8')
K.SaveBoard(str(path),board)
loaded=K.LoadBoard(str(path))
native={fp.GetReference():fp for fp in loaded.GetFootprints()}
assert len(native)==167 and len(list(loaded.GetTracks()))==0
maximum_error=0
for e in expected:
    pad=next(p for p in native[e['ref']].Pads() if p.GetNumber()==e['pad'])
    assert pad.GetNetname()==e['net']
    for got,want in [(K.ToMM(pad.GetPosition().x),e['x_mm']),(K.ToMM(pad.GetPosition().y),e['y_mm']),
                     (K.ToMM(pad.GetSize().x),e['width_mm']),(K.ToMM(pad.GetSize().y),e['height_mm'])]:
        maximum_error=max(maximum_error,abs(got-want));assert abs(got-want)<.000002
    assert abs(((pad.GetOrientationDegrees()-e['angle_deg']+180)%360)-180)<1e-6
    assert abs(K.ToMM(pad.GetDrillSize().x)-e['drill_mm'])<.000002
    if e['bottom']:
        assert native[e['ref']].GetLayer()==K.B_Cu and pad.GetAttribute()==K.PAD_ATTRIB_PTH
        assert pad.GetLayerSet().Contains(K.F_Cu) and pad.GetLayerSet().Contains(K.B_Cu)
assert len(expected)==628
report={'status':'native_copper_geometry_roundtrip_pass_NOT_full_import_NOT_manufacture',
 'kicad_version':K.Version(),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
 'board_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'placed_components':163,'imported_top_components':source_component_count,
 'native_bottom_additions':bottom_spec['components'],'mounting_holes':4,
 'copper_pads_checked':len(expected),'maximum_numeric_error_mm':maximum_error,'tracks':0,
 'source_paste_sentinel_overrides_REVIEW_ONLY':paste_overrides,
 'schematic_identities_linked':sum(ref in identities for ref in components),'native_footprint_library_parts':len(exported),
 'bottom_pad_readback':[e for e in expected if e['bottom']],
 'isolated_schematic_nc_pads':[['J1','3'],['J1','4']],
 'not_covered':['full schematic and project parity (check separately)','exact mating parts/anchor material and installed harness','copper thickness/stackup beyond total 1.6mm',
  'routing and copper zones','original silkscreen, courtyard, 3D, custom properties','paste sentinel semantics and final stencil apertures',
  'manufacturing release']}
(ROOT/'verification/kicad-copper-roundtrip.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='source_paste_sentinel_overrides_REVIEW_ONLY'},ensure_ascii=False))
