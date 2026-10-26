"""Prepare an isolated editable revision; never overwrite the validated v01."""
from pathlib import Path
import json,shutil,subprocess,sys
P=Path(__file__).resolve().parents[1];S=P/'hardware/kicad-check';D=P/'hardware/prototype-v02'
D.mkdir(exist_ok=True)
for name in ['phyllo-copper-review.kicad_pro','fp-lib-table']:
    if not (D/name).exists():shutil.copy2(S/name,D/name)
shutil.copytree(S/'PhylloReview.pretty',D/'PhylloReview.pretty',dirs_exist_ok=True)
power=json.loads((P/'hardware/power_candidate.json').read_text(encoding='utf-8'))
power['status']='prototype_v02_design_not_hardware_verified'
power['supply']='Bel SDM50-5-U-P5 sealed 5V/9A candidate; external 7.5A MINI fuse and rated DC-to-XT30 harness. External 5V is the only supply while attached. No supplier inquiry prerequisite; verify polarity and loaded voltage on receipt.'
for c in power['components']:
    if c['ref'] in ['C1','C2','C3','C4']:
        c['part']='APXF100ARA271MF61G';c['role']='270uF 10V Chemi-Con PXF F61 polymer bulk; pin1 +5V, pin2 GND; stripe NEGATIVE'
for ref in ['C6','C7','C8','C9']:
    power['components'].append({'ref':ref,'part':'APXF100ARA271MF61G','role':'270uF 10V Chemi-Con PXF F61 polymer bulk; pin1 +5V, pin2 GND; stripe NEGATIVE','pins':{'1':'5V_LED','2':'GND'}})
assert len(power['components'])==23 and len({c['ref'] for c in power['components']})==23
(D/'power_candidate.json').write_text(json.dumps(power,indent=2,ensure_ascii=False),encoding='utf-8')
subprocess.run([sys.executable,str(P/'hardware/derive_kicad_schematic.py'),'--output',str(D),'--power',str(D/'power_candidate.json'),'--report',str(P/'verification/prototype-v02-schematic-generation.json')],check=True)
