"""Record evidence from saved, identified library files; no physical-part claims."""
from pathlib import Path
import json,hashlib
from library_inspect import read_library
P=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
capfile=P/'hardware/library/C46550459.elibz2';a=read_library(capfile)
symbol={h['id']:b for h,b in a['docs'][('SYMBOL',a['device']['attributes']['Symbol'])] if h['type']=='POLY'}
assert symbol['e15']['points']==[{'x':-9,'y':-5},{'x':-5,'y':-5}]
assert symbol['e16']['points']==[{'x':-7,'y':-7},{'x':-7,'y':-3}]
assert a['pins']['1']['x']==-20 and a['pins']['2']['x']==20
assert a['pads']['1']['centerX']<0<a['pads']['2']['centerX']
components=json.loads((P/'hardware/power_candidate.json').read_text())['components']
for ref in ['C1','C2','C3','C4']:
    c=next(c for c in components if c['ref']==ref);assert c['pins']=={'1':'5V_LED','2':'GND'}
capart=[{'record':h,'data':b} for h,b in a['docs'][('FOOTPRINT',a['device']['attributes']['Footprint'])] if h['type']=='FILL' and b.get('layerId')==3]
xtfile=P/'hardware/library/C431092.elibz2';xt=read_library(xtfile)
plan=json.loads((P/'hardware/manufacturing-layers-plan.json').read_text())
paste=[{'ref':p['ref'],'part':p['part'],'source_sha256':p['source_library_sha256'],'pads':p['custom_paste_pad_numbers'],
        'apertures':[s for s in p['artwork'] if s['purpose']=='paste']} for p in plan['parts'] if p['custom_paste_pad_numbers']]
assert len(paste)==8 and sum(len(p['apertures']) for p in paste)==16
r={'status':'source_library_and_manufacturer_document_evidence_NOT_PHYSICAL_VERIFICATION',
 'capacitor':{'supplier':'C46550459','part':'MA10V470M6X8','source_sha256':sha(capfile),'pin1':'positive, supported by explicit plus in saved symbol and footprint','pin2':'negative',
 'symbol_plus_records':{k:symbol[k] for k in ['e15','e16']},'footprint_polarity_art':capart,
 'pins':a['pins'],'pads':a['pads'],'board_mapping':'C1-C4 pin1=5V_LED, pin2=GND',
 'datasheet_sha256':sha(P/'hardware/datasheets/JIERR-MA-series.pdf'),
 'datasheet_url':'https://atta.szlcsc.com/upload/public/pdf/source/20260306/24758A4FC016E80367B87853635CDCC1.pdf',
 'remaining':'Physical package stripe and factory placement rotation must be checked in assembly preview or on identified delivered parts.'},
 'XT30':{'supplier':'C431092','part':'XT30PW-M30.G.Y','source_sha256':sha(xtfile),'pads':xt['pads'],
 'datasheet_sha256':sha(P/'hardware/datasheets/AMASS-XT30PW-M30.pdf'),
 'datasheet_url':'https://www.china-amass.net/uploads/32.XT30PW-M30-SPEC-2025V0.pdf',
 'main_hole_nominal_mm':1.8,'auxiliary_hole_nominal_mm':1.1,
 'auxiliary_decision':'Preserve source plated through-holes 3/4, with isolated NC nets. Manufacturer drawing does not explicitly identify auxiliary-pin material; do not convert to NPTH or assign a circuit net.',
 'remaining':'Confirm auxiliary-pin material, solder/assembly treatment and mating harness with supplier/real part before production.'},
 'paste':{'negative_expansion_meaning':'A large negative value suppresses automatic aperture. It is not null/inheritance. Source library provides separate filled paste polygons.',
 'documentation':['https://prodocs.easyeda.com/en/faq/pcb/#how-to-delete-unwanted-paste-mask-layers','<LOCAL_PATH>'],
 'custom_apertures':paste,'conversion_assumptions':plan['assumptions']}}
(P/'verification/library-manufacturing-evidence.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'capacitor_pin1':'positive per library','custom_apertures':16,'XT30_auxiliary':'isolated source PTH; material pending'}))
