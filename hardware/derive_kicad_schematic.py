"""Native, review-only schematic with explicit pin-table symbols.

Keeps saved EasyEDA pin definitions and applies explicit circuit-intent changes.
Symbol names and pin numbers come from saved libraries; graphics are functional boxes,
not an alleged full conversion of vendor symbols. Native netlist export is
checked separately against the source circuit, including cross-sheet nets.
Format: https://dev-docs.kicad.org/en/file-formats/sexpr-schematic/
"""
from pathlib import Path
import json,uuid,hashlib,argparse
from library_inspect import read_library

P=Path(__file__).resolve().parents[1]
args=argparse.ArgumentParser()
args.add_argument('--output',type=Path,default=P/'hardware/kicad-check')
args.add_argument('--power',type=Path,default=P/'hardware/power_candidate.json')
args.add_argument('--report',type=Path,default=P/'verification/kicad-schematic-generation.json')
args=args.parse_args()
OUT=args.output;OUT.mkdir(parents=True,exist_ok=True); SUB=OUT/'sheets';SUB.mkdir(exist_ok=True)
NAME='phyllo-copper-review'
def uid(s):return str(uuid.uuid5(uuid.NAMESPACE_URL,'phyllo-native-review/'+s))
def q(s):return json.dumps(str(s),ensure_ascii=False)
def datasheet(part):return 'https://www.chemi-con.co.jp/products/relatedfiles/capacitor/catalog/PXFRA-e.PDF' if part=='APXF100ARA271MF61G' else ''
def ef(size=1.0,extra=''):return f'(effects (font (size {size} {size})) {extra})'
def prop(k,v,x,y,hide=False,size=1.1):
    return f'(property {q(k)} {q(v)} (at {x} {y} 0) {ef(size,"(hide yes)" if hide else "")})'
rootid=uid('root')
libs={}
for f in sorted((P/'hardware/library').glob('*.elibz2')):
    lib=read_library(f);libs[lib['device']['attributes']['Supplier Part']]=lib
expected=json.loads((P/'hardware/eda/expected-led-netlist.json').read_text())
power=json.loads(args.power.read_text(encoding='utf-8'))['components']
# The F61 symbol is a project-owned pin table, drawn from the official Chemi-Con
# PXF / NPCAP 2026 documents. No distributor library or stock code is invented.
if any(c['part']=='APXF100ARA271MF61G' for c in power):
    libs['APXF100ARA271MF61G']={'device':{'attributes':{'Manufacturer Part':'APXF100ARA271MF61G'}},'pins':{'1':{'Pin Name':'+'},'2':{'Pin Name':'-'}}}
chain=json.loads((P/'shared/chain.json').read_text())['chain_to_geometry_id']
layout=json.loads((P/'shared/layout.json').read_text())['leds']
components={c['ref']:c for c in power}
for ref,pins in expected.items():components[ref]={'ref':ref,'part':'C52941391','pins':pins,'role':'RGB LED; physical ID is designator, chain order differs'}
intent=json.loads((P/'hardware/circuit-intent.json').read_text())
for item in intent['intentionally_unconnected']:
    assert components[item['ref']]['pins'][item['pin']]==item['source_net']
    components[item['ref']]['pins'][item['pin']]=None

def electrical(part,pin):
    if part=='C52941391':return {'1':'power_in','2':'output','3':'power_in','4':'input'}[pin]
    if part=='C12495':return {'1':'input','2':'input','3':'power_in','4':'tri_state','5':'power_in'}[pin]
    # Conservative passive semiconductor terminals; gate drive/source contract
    # is audited in circuit review, not asserted by this limited ERC model.
    return 'passive'

geometries={}; definitions={}
for part,lib in libs.items():
    nums=sorted(lib['pins'],key=int)
    # Functional grouping keeps the LED's signal flow readable left-to-right.
    left,right=(['4','1'],['2','3']) if part=='C52941391' else (nums[:(len(nums)+1)//2],nums[(len(nums)+1)//2:])
    h=max(len(left),len(right))*2.54+2.54
    pins={}
    for side,items in [(-1,left),(1,right)]:
        for i,n in enumerate(items):pins[n]={'x':side*12.7,'y':((len(items)-1)/2-i)*2.54,'a':0 if side==-1 else 180}
    geometries[part]=(h,pins)
    short=part;mpn=lib['device']['attributes']['Manufacturer Part']
    d=[f'(symbol {q("PhylloReview:"+short)} (pin_names (offset 0.508)) (in_bom yes) (on_board yes)',
       prop('Reference','U',0,h/2+2),prop('Value',mpn,0,-h/2-2),
       prop('Footprint','',0,0,True),prop('Datasheet',datasheet(part),0,0,True),
       prop('Description','Review pin table; names/numbers from saved EasyEDA library. NOT vendor graphics.',0,0,True),
       f'(symbol {q(short+"_0_1")} (rectangle (start -10.16 {h/2}) (end 10.16 {-h/2}) (stroke (width 0.254) (type default)) (fill (type background))))',
       f'(symbol {q(short+"_1_1")}']
    for n,p in pins.items():
        d.append(f'(pin {electrical(part,n)} line (at {p["x"]} {p["y"]} {p["a"]}) (length 2.54) (name {q(lib["pins"][n]["Pin Name"])} {ef(.95)}) (number {q(n)} {ef(.95)}))')
    definitions[part]='\n'.join(d)+'))'

# Conventional virtual power-output declaration, with no physical footprint.
definitions['PWR_FLAG']='''(symbol "PhylloReview:PWR_FLAG" (power global)
 (pin_numbers hide) (pin_names (offset 0) hide) (in_bom no) (on_board no)
 (property "Reference" "#FLG" (at 0 1.905 0) (effects (font (size 1.27 1.27)) (hide yes)))
 (property "Value" "PWR_FLAG" (at 0 3.81 0) (effects (font (size 1.27 1.27))))
 (symbol "PWR_FLAG_0_1" (polyline (pts (xy 0 0) (xy 0 1.27) (xy -1.016 1.905) (xy 0 2.54) (xy 1.016 1.905) (xy 0 1.27)) (stroke (width 0) (type default)) (fill (type none))))
 (symbol "PWR_FLAG_1_1" (pin power_out line (at 0 0 90) (length 0) (name "" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))))'''

def header(title,docid,parts=()):
    return [f'(kicad_sch (version 20250114) (generator "phyllo_review") (uuid {q(docid)}) (paper "A3")',
            f'(title_block (title {q(title)}) (date "2026-10-03") (rev "PROTO-02") (comment 1 "PROTOTYPE DESIGN - NO HARDWARE TEST EVIDENCE"))',
            '(lib_symbols '+'\n'.join(definitions[k] for k in sorted(set(parts)))+')']
def note(s,x,y,key,size=1.3):return f'(text {q(s)} (at {x} {y} 0) {ef(size,"(justify left)")} (uuid {q(uid(key))}))'

symbolmap={}
def place(c,x,y,page):
    ref,part=c['ref'],c['part'];h,pins=geometries[part];lib=libs[part];sid=uid('symbol/'+ref)
    symbolmap[ref]={'uuid':sid,'path':'/'+rootid+'/'+uid('sheet/'+page)+'/'+sid,'part':part,'description':c['role']}
    out=[f'(symbol (lib_id {q("PhylloReview:"+part)}) (at {x} {y} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {q(sid)})',
         prop('Reference',ref,x,y-h/2-2.54),prop('Value',lib['device']['attributes']['Manufacturer Part'],x,y+h/2+2.54,size=.95),
         prop('Footprint','PhylloReview:'+part,x,y,True),prop('Datasheet',datasheet(part),x,y,True),prop('Manufacturer Part' if datasheet(part) else 'Supplier Part',part,x,y,True),prop('Description',c['role'],x,y,True)]
    for n in pins:out.append(f'(pin {q(n)} (uuid {q(uid(ref+"/pin/"+n))}))')
    out.append(f'(instances (project {q(NAME)} (path {q("/"+rootid+"/"+uid("sheet/"+page))} (reference {q(ref)}) (unit 1)))))')
    for n,p in pins.items():
        px=x+p['x'];py=y-p['y'];net=c['pins'][n];key=ref+'/'+n
        if net is None:
            out.append(f'(no_connect (at {px} {py}) (uuid {q(uid(key+"/nc"))}))');continue
        dx=-5.08 if p['x']<0 else 5.08;ex=px+dx;angle=0 if dx<0 else 180
        out.append(f'(wire (pts (xy {px} {py}) (xy {ex} {py})) (stroke (width 0) (type default)) (uuid {q(uid(key+"/wire"))}))')
        out.append(f'(global_label {q(net)} (shape passive) (at {ex} {py} {angle}) {ef(.95,"(justify "+("right" if dx<0 else "left")+")")} (uuid {q(uid(key+"/label"))}))')
    return out

pages=[]
for index in range(4):
    name=f'led-{index+1}';title=f'LED chain {index*36+1:03d}-{index*36+36:03d}'
    cs=[components[layout[ident]['designator']] for ident in chain[index*36:index*36+36]]
    out=header(title,uid('document/'+name),[c['part'] for c in cs])
    out.append(note('PHYLLO / '+title+' / candidate pin-table schematic',15,15,name+'/title',2))
    out.append(note('Pin numbers/names from saved vendor library. Global labels join all sheets. No fabrication release.',15,22,name+'/subtitle'))
    for i,c in enumerate(cs):out.extend(place(c,44.45+(i%6)*66.04,48.26+(i//6)*35.56,name))
    out.append(')');(SUB/(name+'.kicad_sch')).write_text('\n'.join(out),encoding='utf-8');pages.append((name,title))
name='power-interface';out=header('Power and controller interface',uid('document/'+name),[c['part'] for c in power]+['PWR_FLAG'])
out.append(note('PHYLLO / power and controller interface / candidate pin tables',15,15,name+'/title',2))
out.append(note('External fused 5V only. PMOS D=input, S=protected rail. NEVER parallel controller USB VBUS with external 5V.',15,22,name+'/supply'))
out.append(note('C1-C4/C6-C9: Chemi-Con PXF 270uF/10V, pin1=positive. Physical harness and power tests remain required. ERC is not circuit simulation.',15,29,name+'/pending'))
for i,c in enumerate(power):out.extend(place(c,50.8+(i%5)*76.2,55.88+(i//5)*38.1,name))
for i,f in enumerate(intent['power_declarations']):
    x=76.2+i*76.2;y=251.46;sid=uid('flag/'+f['reference'])
    out.append(f'(symbol (lib_id "PhylloReview:PWR_FLAG") (at {x} {y} 0) (unit 1) (in_bom no) (on_board no) (dnp no) (uuid {q(sid)}) '+
      prop('Reference',f['reference'],x,y-5,True)+prop('Value','PWR_FLAG',x,y-3.81)+prop('Footprint','',x,y,True)+prop('Datasheet','',x,y,True)+
      f'(pin "1" (uuid {q(uid(f["reference"]+"/pin"))})) (instances (project {q(NAME)} (path {q("/"+rootid+"/"+uid("sheet/"+name))} (reference {q(f["reference"])}) (unit 1)))))')
    out.append(f'(global_label {q(f["net"])} (shape passive) (at {x} {y} 0) {ef(1,"(justify right)")} (uuid {q(uid(f["reference"]+"/net"))}))')
out.append(note('PWR_FLAG declares intended external supply through J1/Q1, not hardware proof. Last LED D121 DOUT is intentionally NC.',15,263,name+'/intent'))
out.append(')');(SUB/(name+'.kicad_sch')).write_text('\n'.join(out),encoding='utf-8');pages.append((name,'Power and interface'))

out=header('PHYLLO / circuit review index',rootid)
out.extend([note('PHYLLO / 144-point golden-angle audio display',20,20,'root/title',3),
 note('Native review companion to the EasyEDA candidate - not a full EasyEDA project import.',20,30,'root/subtitle',1.5),
 note(f'5 circuit sheets / {len(components)} components / explicit global-net connections',20,40,'root/count',1.5),
 note('STM32F411 development board and microphone are off-board modules. Their exact delivered identity is not frozen.',20,210,'root/modules'),
 note('ERC does not validate reverse-polarity operation, current capacity, heat, pin polarity or wire harness assembly.',20,219,'root/scope'),
 note('PCB routing is connected. External power intent is declared; final D121 DOUT is NC. Manufacturing review remains open.',20,228,'root/status')])
for i,(name,title) in enumerate(pages):
    x=25+(i%3)*125;y=65+(i//3)*70
    out.append(f'(sheet (at {x} {y}) (size 100 45) (stroke (width 0.254) (type default)) (fill (color 0 0 0 0)) (uuid {q(uid("sheet/"+name))}) '+
               prop('Sheetname',title,x,y-2)+prop('Sheetfile','sheets/'+name+'.kicad_sch',x,y+47)+
               f'(instances (project {q(NAME)} (path {q("/"+rootid)} (page {q(i+2)})))))')
out.extend(['(sheet_instances (path "/" (page "1")))',')'])
(OUT/(NAME+'.kicad_sch')).write_text('\n'.join(out),encoding='utf-8')
# Embedded and external definitions agree; the latter allows normal library checks.
library='(kicad_symbol_lib (version 20241209) (generator "phyllo_review")\n'+'\n'.join(d.replace('"PhylloReview:','"',1) for d in definitions.values())+'\n)'
(OUT/'PhylloReview.kicad_sym').write_text(library,encoding='utf-8')
(OUT/'sym-lib-table').write_text('(sym_lib_table (lib (name "PhylloReview") (type "KiCad") (uri "${KIPRJMOD}/PhylloReview.kicad_sym") (options "") (descr "Derived review pin tables, not vendor graphics")))\n',encoding='utf-8')
(OUT/'symbol-identities.json').write_text(json.dumps(symbolmap,indent=2),encoding='utf-8')
report={'status':'generated_NOT_yet_native_verified','components':len(components),'circuit_sheets':5,'index_sheets':1,
 'connected_pins':sum(n is not None for c in components.values() for n in c['pins'].values()),
 'unconnected_mechanical_pins':[['J1','3'],['J1','4']],
 'source_sha256':hashlib.sha256((P/'hardware/eda/phyllo-led-draft.epru').read_bytes()).hexdigest(),
 'circuit_intent_sha256':hashlib.sha256((P/'hardware/circuit-intent.json').read_bytes()).hexdigest(),
 'limitations':['New functional pin-table graphics, not original vendor symbols','Power flags declare intended external source, not verified hardware drive','Passive transistor pins do not model gate/source behavior','Footprint links require native PCB parity check; exact connector mating/anchor details remain pending']}
args.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
