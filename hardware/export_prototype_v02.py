"""Export the checked revision and self-contained prototype manufacturing inputs."""
from pathlib import Path
import json,subprocess,hashlib,xml.etree.ElementTree as ET,csv,collections,zipfile
import pymupdf as fitz
P=Path(__file__).resolve().parents[1];S=P/'hardware/prototype-v02';D=S/'manufacturing';D.mkdir(exist_ok=True);V=P/'verification'
CLI='<LOCAL_PATH>';B=S/'phyllo-copper-review.kicad_pcb';SCH=B.with_suffix('.kicad_sch')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
report=(V/'prototype-v02-drc.rpt').read_text(encoding='utf-8')
for text in ['Found 0 DRC violations','Found 0 unconnected pads','Found 0 Footprint errors']:assert text in report
assert sha(B)==json.loads((V/'prototype-v02-copper-geometry.json').read_text())['sha256']
runs=[]
def run(name,args,src=B):
    p=subprocess.run([CLI,*args,str(src)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
    (V/('prototype-v02-export-'+name+'.log')).write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,(name,p.stderr)
    runs.append({'stage':name,'exit_code':p.returncode})
gerber=D/'gerbers';gerber.mkdir(exist_ok=True)
run('gerbers',['pcb','export','gerbers','--output',str(gerber),'--layers','F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,F.Paste,Edge.Cuts'])
run('drills',['pcb','export','drill','--output',str(gerber),'--format','excellon','--drill-origin','absolute','--excellon-units','mm','--excellon-separate-th','--generate-report','--report-path',str(D/'drill-report.txt')])
run('positions',['pcb','export','pos','--output',str(D/'CPL-native-mm.csv'),'--format','csv','--units','mm','--side','both'])
run('netlist',['sch','export','netlist','--format','kicadxml','--output',str(S/'netlist.xml')],SCH)
run('schematic',['sch','export','pdf','--output',str(S/'PHYLLO-v02-schematic.pdf')],SCH)
for name,layers,mirror in [('front-assembly','F.Fab,F.Silkscreen,Edge.Cuts',False),('back-assembly','B.Fab,B.Silkscreen,Edge.Cuts',True),('front-copper','F.Cu,F.Silkscreen,Edge.Cuts',False),('front-paste','F.Paste,Edge.Cuts',False)]:
    out=D/(name+'.svg')
    run(name,['pcb','export','svg','--mode-single','--output',str(out),'--layers',layers,'--page-size-mode','2','--exclude-drawing-sheet',*(['--black-and-white'] if name!='front-copper' else []),*(['--mirror'] if mirror else [])])
    svg=fitz.open(out);pdf=fitz.open('pdf',svg.convert_to_pdf());pdf.save(out.with_suffix('.pdf'));pdf[0].get_pixmap(matrix=fitz.Matrix(2,2)).save(out.with_suffix('.png'))
root=ET.parse(S/'netlist.xml').getroot();groups=collections.defaultdict(list);rows=[]
for c in root.findall('components/comp'):
    ref=c.attrib['ref'];fields={f.attrib['name']:f.text or '' for f in c.findall('fields/field')}
    mpn=c.findtext('value');supplier=fields.get('Supplier Part','');footprint=c.findtext('footprint')
    groups[(mpn,supplier,footprint)].append(ref);rows.append(ref)
assert len(rows)==167 and len(set(rows))==167
with (D/'BOM.csv').open('w',encoding='utf-8-sig',newline='') as file:
    w=csv.writer(file);w.writerow(['Designator','Quantity','Manufacturer Part','LCSC Part (blank means no stock code asserted)','Footprint','Assembly note'])
    for (mpn,supplier,footprint),refs in sorted(groups.items()):
        note='8 total; pin1 positive/inward, black stripe negative/outward; see capacitor-map.csv' if mpn=='APXF100ARA271MF61G' else 'MSL5a, keep dry; do not substitute LED pinout/timing' if supplier=='C52941391' else 'Bottom through-hole; inspect pins/anchor soldering' if refs[0].startswith('J') else ''
        w.writerow([','.join(sorted(refs)),len(refs),mpn,supplier,footprint,note])
geo=json.loads((V/'prototype-v02-copper-geometry.json').read_text());caps=[f for f in geo['footprints'] if f['part']=='APXF100ARA271MF61G']
with (D/'capacitor-map.csv').open('w',encoding='utf-8-sig',newline='') as file:
    w=csv.writer(file);w.writerow(['Ref','Native center X mm','Native center Y mm','Native rotation deg','Plus pad1 X','Plus pad1 Y','Minus pad2 X','Minus pad2 Y','Stripe'])
    for fp in sorted(caps,key=lambda r:r['ref']):
        pads={p['num']:p for p in geo['pads'] if p['ref']==fp['ref']};w.writerow([fp['ref'],*fp['xy'],fp['angle'],*pads['1']['xy'],*pads['2']['xy'],'NEGATIVE / pad2 / OUTWARD'])
# Absolute XY native readback vs KiCad's Y-up position export.
with (D/'CPL-native-mm.csv').open(encoding='utf-8-sig',newline='') as f:positions=list(csv.DictReader(f))
lookup={f['ref']:f for f in geo['footprints']};assert len(positions)==167
for row in positions:
    fp=lookup[row['Ref']];assert abs(float(row['PosX'])-fp['xy'][0])<.00001 and abs(float(row['PosY'])+fp['xy'][1])<.00001
# Exact pin/net table parity, including the three explicit NC terminals.
nets={(n.attrib['ref'],n.attrib['pin']):net.attrib['name'] for net in root.findall('nets/net') for n in net.findall('node')}
for pad in geo['pads']:
    if pad['ref'] in rows:assert nets[(pad['ref'],pad['num'])]==pad['net'],(pad['ref'],pad['num'])
with zipfile.ZipFile(D/'PHYLLO-v02-Gerber.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(gerber.iterdir()):z.write(p,p.name)
with zipfile.ZipFile(D/'PHYLLO-v02-Gerber.zip') as z:assert z.testzip() is None
result={'revision':'PROTO-02','board_sha256':sha(B),'schematic_sha256':sha(SCH),'commands':runs,'BOM_parts':167,'capacitors':8,'CPL_positions':len(positions),'electrical_pad_net_parity':636,'physical_hardware_tested':False,'files':[{'path':str(p.relative_to(S)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(D.rglob('*')) if p.is_file()]}
(V/'prototype-v02-exports.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='files'}))
