"""Export a LOCAL review set, never an order or a production-release package."""
from pathlib import Path
import hashlib,json,subprocess,re
import pymupdf as fitz
P=Path(__file__).resolve().parents[1];V=P/'verification';D=P/'hardware/manufacturing-output-REVIEW';D.mkdir(exist_ok=True)
B=P/'hardware/kicad-check/phyllo-copper-review.kicad_pcb';CLI='<LOCAL_PATH>'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(B)==json.loads((V/'manufacturing-layer-promotion.json').read_text())['board_sha256']
runs=[]
def run(name,args):
    p=subprocess.run([CLI,*args,str(B)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
    (V/('manufacturing-export-'+name+'.log')).write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,(name,p.stderr)
    runs.append({'stage':name,'exit_code':p.returncode})
run('gerbers',['pcb','export','gerbers','--output',str(D), '--layers','F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,F.Paste,Edge.Cuts'])
run('drills',['pcb','export','drill','--output',str(D),'--format','excellon','--drill-origin','absolute','--excellon-units','mm','--excellon-separate-th','--generate-report','--report-path',str(D/'drill-report.txt')])
run('positions',['pcb','export','pos','--output',str(D/'native-positions-mm.csv'),'--format','csv','--units','mm','--side','both'])
for name,layers,mirror,assembly in [
 ('front-silk','F.Silkscreen,Edge.Cuts',False,False),('back-silk','B.Silkscreen,Edge.Cuts',True,False),
 ('front-paste','F.Paste,Edge.Cuts',False,False),('front-assembly','F.Fab,Edge.Cuts',False,True),('back-assembly','B.Fab,Edge.Cuts',True,True)]:
    out=V/('manufacturing-'+name+'.svg')
    run(name,['pcb','export','svg','--mode-single','--output',str(out),'--layers',layers,'--page-size-mode','2','--exclude-drawing-sheet','--black-and-white',*(['--drill-shape-opt','0'] if name=='front-paste' else []),*(['--mirror'] if mirror else []),*(['--sketch-pads-on-fab-layers'] if assembly else [])])
    svg=fitz.open(out);pdf=fitz.open('pdf',svg.convert_to_pdf());pdf.save(out.with_suffix('.pdf'));pdf[0].get_pixmap(matrix=fitz.Matrix(2,2)).save(out.with_suffix('.png'))
    if name in ['front-assembly','front-paste','front-silk']:
        # Board-space bottom service strip: x=45..145 mm, y=168..190 mm.
        page=pdf[0];factor=page.rect.width/180;clip=fitz.Rect(35*factor,158*factor,135*factor,180*factor)
        page.get_pixmap(matrix=fitz.Matrix(4,4),clip=clip).save(V/('manufacturing-'+name+'-service-detail.png'))
paste=next(D.glob('*.gtp')).read_text();r={'status':'LOCAL_EXPORT_REVIEW_ONLY_NOT_FOR_ORDER','board_sha256':sha(B),'commands':runs,
 'paste_gerber':{'file':next(D.glob('*.gtp')).name,'region_start_count':paste.count('G36*'),'flash_commands':len(re.findall(r'D03\*',paste))},
 'limits':['No factory upload, quote or rotation preview performed. Native position angles are NOT asserted to match a particular PCBA vendor convention.',
 'Gerbers represent selected design rules; final stackup, physical polarity/assembly and mechanical checks remain outstanding.'],
 'files':[{'path':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(D.iterdir()) if p.is_file() and p.name not in ['README-NOT-FOR-ORDER.txt','export-manifest.json']]}
(D/'README-NOT-FOR-ORDER.txt').write_text('PHYLLO LOCAL MANUFACTURING REVIEW ONLY. DO NOT ORDER OR FABRICATE FROM THIS DIRECTORY.\nBoard SHA256: '+sha(B)+'\nCoordinate origin: KiCad absolute; native positions use Y-up and native angle conventions. Vendor BOM/CPL mapping and placement preview are not approved.\nPending: full assembly geometry, actual parts/harness, capacitor polarity/rotation confirmation, factory stackup/quote and final release review.\n',encoding='utf-8')
(D/'export-manifest.json').write_text(json.dumps(r,indent=2),encoding='utf-8');(V/'manufacturing-export-receipt.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
print(json.dumps(r))
