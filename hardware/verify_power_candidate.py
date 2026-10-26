"""Independent named-pin checks and readback of generated support schematic nets.
This is not ERC, analogue simulation, PCB parity or hardware verification.
"""
from pathlib import Path
import json,math
from eda_format import parse_records
from library_inspect import read_library
P=Path(__file__).resolve().parents[1]
spec=json.loads((P/'hardware/power_candidate.json').read_text())
libs={}
for f in (P/'hardware/library').glob('*.elibz2'):
    a=read_library(f);libs[a['device']['attributes']['Supplier Part']]=a
parts={c['ref']:c for c in spec['components']}
r=list(parse_records((P/'hardware/eda/phyllo-led-draft.epru').read_text(encoding='utf-8')))
page=False;components={};lines={};labels={}
for h,b in r:
    if h['type']=='DOCHEAD':page=b['docType']=='SCH_PAGE'
    if not page:continue
    if h['type']=='COMPONENT' and h['id'] in parts:components[h['id']]=b
    if h['type']=='LINE':lines[b['lineGroup']]=b
    if h['type']=='ATTR' and b['key']=='NET':labels[b['parentId']]=b['value']
assert set(components)==set(parts)
connected=0
for ref,c in parts.items():
    for num,net in c['pins'].items():
        if net is None:continue
        pin=libs[c['part']]['pins'][num];wire=f'{ref}-wire-{num}';component=components[ref]
        assert math.isclose(lines[wire]['startX'],component['x']+pin['x'],abs_tol=1e-6)
        assert math.isclose(lines[wire]['startY'],component['y']+pin['y'],abs_tol=1e-6)
        assert labels[wire]==net
        connected+=1
q=parts['Q1']['pins']
for n in ['1','2','3']:assert q[n]=='5V_LED' and libs['C2910138']['pins'][n]['Pin Name']=='S'
for n in ['5','6','7','8']:assert q[n]=='VIN_FUSED' and libs['C2910138']['pins'][n]['Pin Name']=='D'
assert q['4']=='PMOS_GATE'
assert parts['D145']['pins']=={'1':'5V_LED','2':'PMOS_GATE'}
assert libs['C271259']['pins']['1']['Pin Name']=='C'
assert parts['U1']['pins']=={'1':'DATA_OE_N','2':'DATA_3V3','3':'GND','4':'DATA_BUFFERED','5':'5V_LED'}
assert parts['Q2']['pins']=={'1':'ENABLE_3V3','2':'GND','3':'DATA_OE_N'}
assert parts['J2']['pins']['4']=='5V_MCU'
assert parts['F2']['pins']=={'1':'5V_LED','2':'5V_MCU'}
assert parts['J1']['pins']['1']=='GND' and libs['C431092']['pins']['1']['Pin Name']=='-'
assert parts['J1']['pins']['2']=='VIN_FUSED' and libs['C431092']['pins']['2']['Pin Name']=='+'
for ref in ['C1','C2','C3','C4','C5']:assert parts[ref]['pins']=={'1':'5V_LED','2':'GND'}
report={'status':'candidate_schematic_named_pin_readback_pass','support_components':len(parts),'connected_pins':connected,
        'pmos_orientation':'D=input/S=protected output; source and body-diode direction require manufacturer review',
        'gate_network_5V_nominal':{'R_gate_to_ground_ohm':1000,'R_gate_to_source_ohm':1000000,
          'bias_current_uA':5/1001000*1e6,'Vgs_V':-5*1000000/1001000},
        'buffer_default':'OE pulled high, DIN pulled low; enable NMOS switches OE only, never LED ground',
        'pcb_parity':False,'native_erc':False,'manufacturing_ready':False,
        'open_items':['XT30 mechanical pin 3/4 classification','bulk capacitor polarity and height','all manufacturer footprint checks','power protection/thermal calculations and tests','bottom connector placement and all PCB routing','native schematic/PCB netlist parity']}
(P/'verification/power-schematic-audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
