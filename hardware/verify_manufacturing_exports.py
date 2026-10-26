"""Independently reconcile plotted holes, paste counts and positions to native geometry."""
from pathlib import Path
import json,hashlib,csv,re,collections,math
from library_inspect import read_library
P=Path(__file__).resolve().parents[1];D=P/'hardware/manufacturing-output-REVIEW';V=P/'verification'
g=json.loads((V/'power-copper-geometry.json').read_text());r=json.loads((V/'manufacturing-export-receipt.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert g['sha256']==r['board_sha256']==sha(P/'hardware/kicad-check/phyllo-copper-review.kicad_pcb')
for f in r['files']:assert sha(D/f['path'])==f['sha256']
positions=list(csv.DictReader((D/'native-positions-mm.csv').open(encoding='utf-8')))
fps={f['ref']:f for f in g['footprints'] if f['part']};assert len(positions)==len(fps)==163
assert {x['Ref'] for x in positions}==set(fps)
for row in positions:
    f=fps[row['Ref']];assert row['Package']==f['part'] and row['Side']==('top' if f['layer']==0 else 'bottom')
    assert abs(float(row['PosX'])-f['xy'][0])<.000002 and abs(float(row['PosY'])+f['xy'][1])<.000002
    assert abs((float(row['Rot'])-f['angle']+180)%360-180)<.000002
def drill(path):
    tools={};selected=None;holes=[]
    for line in path.read_text().splitlines():
        m=re.fullmatch(r'T(\d+)C([\d.]+)',line)
        if m:tools[m[1]]=float(m[2]);continue
        m=re.fullmatch(r'T(\d+)',line)
        if m:selected=m[1];continue
        m=re.fullmatch(r'X([-\d.]+)Y([-\d.]+)',line)
        if m:holes.append((float(m[1]),-float(m[2]),tools[selected]))
    return holes
pth=drill(D/'phyllo-copper-review-PTH.drl');npth=drill(D/'phyllo-copper-review-NPTH.drl')
expected_pth=[(*t['a'],t['drill']) for t in g['tracks'] if t['via']]+[(*p['xy'],p['drill'][0]) for p in g['pads'] if p['drill'][0] and p['num']]
expected_npth=[(*p['xy'],p['drill'][0]) for p in g['pads'] if p['drill'][0] and not p['num']]
max_error=0;max_diameter_error=0
for actual,wanted in [(pth,expected_pth),(npth,expected_npth)]:
    assert len(actual)==len(wanted)
    remaining=actual.copy()
    for x,y,d in wanted:
        matches=[(math.hypot(x-a,y-b),i) for i,(a,b,c) in enumerate(remaining) if abs(c-d)<.000501]
        err,i=min(matches);assert err<.00072,(x,y,d,err);max_error=max(max_error,err);max_diameter_error=max(max_diameter_error,abs(remaining[i][2]-d));remaining.pop(i)
paste=(D/'phyllo-copper-review-F_Paste.gtp').read_text();assert paste.count('G36*')==16 and len(re.findall(r'D03\*',paste))==604
libs={}
for path in (P/'hardware/library').glob('*.elibz2'):
    a=read_library(path);libs[a['device']['attributes']['Supplier Part']]=a
groups=collections.defaultdict(list)
for ref,f in fps.items():groups[f['part']].append(ref)
with (D/'BOM-for-review.csv').open('w',newline='',encoding='utf-8-sig') as out:
    w=csv.writer(out);w.writerow(['Designator','Quantity','Manufacturer Part Number','LCSC Part','Mount','Status'])
    for part,refs in sorted(groups.items()):
        refs.sort(key=lambda r:(re.sub(r'\d','',r),int(re.sub(r'\D','',r))))
        w.writerow([','.join(refs),len(refs),libs[part]['device']['attributes']['Manufacturer Part'],part,'THT hand assembly' if part in ['C431092','C594232'] else 'Top SMD','REVIEW ONLY; vendor availability/rotation/quote pending'])
with (D/'placement-pin1-audit.csv').open('w',newline='',encoding='utf-8-sig') as out:
    w=csv.writer(out);w.writerow(['Ref','Part','Side','CenterX_mm','CenterY_Gerber_mm','NativeAngle_deg','Pin1X_mm','Pin1Y_Gerber_mm','Pin1Net','Notice'])
    for row in positions:
        f=fps[row['Ref']];p=next(p for p in g['pads'] if p['ref']==row['Ref'] and p['num']=='1')
        w.writerow([row['Ref'],f['part'],row['Side'],row['PosX'],row['PosY'],row['Rot'],p['xy'][0],-p['xy'][1],p['net'],'Native angle; factory convention NOT approved'])
audit={'status':'EXPORT_CONSISTENCY_PASS_NOT_PRODUCTION_RELEASE','board_sha256':g['sha256'],'placements':len(positions),
 'top_smd':sum(r['Side']=='top' for r in positions),'bottom_tht':sum(r['Side']=='bottom' for r in positions),
 'bom_lines':len(groups),'bom_components':sum(len(x) for x in groups.values()),'paste_flashes':604,'paste_regions':16,
 'plated_holes':len(pth),'non_plated_holes':len(npth),'max_drill_coordinate_rounding_mm':max_error,'max_drill_diameter_rounding_mm':max_diameter_error,
 'limitations':['Gerber flash/region counts checked, not independent full CAM geometry simulation.','Supplier rotation/stripe match, stock/quote, finished tolerances and soldering process pending.']}
(V/'manufacturing-export-readback.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
r['files']=[{'path':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(D.iterdir()) if p.is_file() and p.name!='export-manifest.json']
(D/'export-manifest.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps(audit))
