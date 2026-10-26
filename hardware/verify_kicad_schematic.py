"""Native parse/export and independent pin-net comparison. Never suppress ERC."""
from pathlib import Path
import json,subprocess,xml.etree.ElementTree as ET,hashlib
import pymupdf
P=Path(__file__).resolve().parents[1];O=P/'verification';D=P/'hardware/kicad-check'
CLI=Path('<LOCAL_PATH>')
SCH=D/'phyllo-copper-review.kicad_sch'
calls=[]
for name,args in [
 ('netlist',['sch','export','netlist','--format','kicadxml','--output',str(O/'kicad-schematic-netlist.xml'),str(SCH)]),
 ('pdf',['sch','export','pdf','--output',str(O/'kicad-schematic-review.pdf'),str(SCH)]),
 ('erc',['sch','erc','--format','json','--severity-all','--exit-code-violations','--output',str(O/'kicad-schematic-erc.json'),str(SCH)])]:
    p=subprocess.run([str(CLI),*args],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=90)
    (O/f'kicad-sch-{name}.log').write_text(p.stdout+'\n'+p.stderr,encoding='utf-8')
    calls.append({'action':name,'exit_code':p.returncode})
    assert p.returncode in ({0,5} if name=='erc' else {0}),calls
expected=json.loads((P/'hardware/eda/expected-led-netlist.json').read_text())
for c in json.loads((P/'hardware/power_candidate.json').read_text())['components']:expected[c['ref']]=c['pins']
for item in json.loads((P/'hardware/circuit-intent.json').read_text())['intentionally_unconnected']:
    assert expected[item['ref']][item['pin']]==item['source_net'];expected[item['ref']][item['pin']]=None
tree=ET.parse(O/'kicad-schematic-netlist.xml').getroot()
refs={c.attrib['ref'] for c in tree.findall('components/comp')};assert refs==set(expected)
actual={};duplicates=[]
for net in tree.findall('nets/net'):
    for node in net.findall('node'):
        key=(node.attrib['ref'],node.attrib['pin'])
        if key in actual:duplicates.append(key)
        actual[key]=net.attrib['name']
assert not duplicates
checked=0;unconnected=[]
for ref,pins in expected.items():
    for n,want in pins.items():
        if want is None:
            got=actual.get((ref,n));assert got is None or got.startswith('unconnected-'),(ref,n,got)
            unconnected.append([ref,n]);continue
        got=actual.get((ref,n));assert got==want,(ref,n,want,got)
        checked+=1
assert set(actual).issubset({(r,n) for r,p in expected.items() for n in p}), 'Unexpected connected pin'
pdf=pymupdf.open(O/'kicad-schematic-review.pdf');assert len(pdf)==6
for i in [0,1,5]:pdf[i].get_pixmap(matrix=pymupdf.Matrix(1.4,1.4)).save(O/f'kicad-schematic-page-{i+1}.png')
erc=json.loads((O/'kicad-schematic-erc.json').read_text(encoding='utf-8'));counts={}
for sheet in erc['sheets']:
    for v in sheet['violations']:counts[v['type']]=counts.get(v['type'],0)+1
dependencies=[SCH,*sorted((D/'sheets').glob('*.kicad_sch')),D/'PhylloReview.kicad_sym',D/'sym-lib-table',D/'fp-lib-table',*sorted((D/'PhylloReview.pretty').glob('*.kicad_mod'))]
report={'status':'native_netlist_matches_declared_intent_NOT_MANUFACTURING_RELEASE','native_tool':tree.findtext('design/tool'),
 'source_dependencies_sha256':{f.relative_to(P).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in dependencies},
 'schematic_root_sha256':hashlib.sha256(SCH.read_bytes()).hexdigest(),'components':len(refs),
 'connected_pins_checked':checked,'intentionally_unconnected_pins':unconnected,'pdf_pages':len(pdf),
 'erc_violation_counts':counts,'ignored_default_checks':erc.get('ignored_checks',[]),'commands':calls,
 'limits':['Pin-table symbols, not vendor graphics','Power drive declarations are intended circuit topology, not external hardware verification','No hardware functional proof','PCB parity is a separate check']}
(O/'kicad-schematic-readback.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
