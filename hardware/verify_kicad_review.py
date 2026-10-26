"""Native DRC evidence for an explicitly incomplete review board."""
from pathlib import Path
import collections,hashlib,json,subprocess
import pymupdf as fitz
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'verification'
CLI=Path('<LOCAL_PATH>')
PCB=ROOT/'hardware/kicad-check/phyllo-copper-review.kicad_pcb'
receipt={'board_sha256':hashlib.sha256(PCB.read_bytes()).hexdigest(),'runs':[]}
commands=[('drc',['pcb','drc','--format','json','--severity-all','--exit-code-violations',
                  '--output',str(OUT/'kicad-unrouted-drc.json'),str(PCB)]),
          ('parity',['pcb','drc','--schematic-parity','--format','json','--severity-all','--exit-code-violations',
                  '--output',str(OUT/'kicad-native-parity.json'),str(PCB)]),
          ('svg',['pcb','export','svg','--mode-single','--output',str(OUT/'kicad-copper-review.svg'),
                  '--layers','F.Cu,F.Silkscreen,Edge.Cuts','--page-size-mode','2','--exclude-drawing-sheet',str(PCB)]),
          ('bottom-svg',['pcb','export','svg','--mode-single','--output',str(OUT/'kicad-bottom-review.svg'),
                  '--layers','B.Cu,B.Silkscreen,Edge.Cuts','--mirror','--page-size-mode','2','--exclude-drawing-sheet',str(PCB)])]
for stage,args in commands:
    p=subprocess.run([str(CLI),*args],capture_output=True,text=True,encoding='utf-8',errors='replace')
    (OUT/f'kicad-review-{stage}.log').write_text(p.stdout+p.stderr,encoding='utf-8')
    receipt['runs'].append({'stage':stage,'exit_code':p.returncode})
    if stage in {'drc','parity'}: assert p.returncode in {0,5},p.stderr
    else: assert p.returncode==0,p.stderr
drc=json.loads((OUT/'kicad-unrouted-drc.json').read_text(encoding='utf-8'))
parity=json.loads((OUT/'kicad-native-parity.json').read_text(encoding='utf-8'))
receipt.update({'status':'native_check_executed_DESIGN_INCOMPLETE',
 'violations_by_type':dict(collections.Counter(v['type'] for v in drc['violations'])),
 'unconnected_items':len(drc['unconnected_items']),'ignored_default_checks':drc['ignored_checks'],
 'schematic_parity_checked':True,'schematic_parity_issues':parity['schematic_parity'],
 'source_conversion_limits':'kicad-copper-roundtrip.json'})
for stem in ['kicad-copper-review','kicad-bottom-review']:
    svg=fitz.open(OUT/(stem+'.svg'))
    pdf=fitz.open('pdf',svg.convert_to_pdf())
    pdf.save(OUT/(stem+'.pdf'))
    pdf[0].get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False).save(OUT/(stem+'.png'))
(OUT/'kicad-native-review-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({**{k:v for k,v in receipt.items() if k!='schematic_parity_issues'},
 'parity_by_type':dict(collections.Counter(v['type'] for v in parity['schematic_parity']))},ensure_ascii=False))
