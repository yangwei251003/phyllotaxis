"""Package the already checked image only if both its source and binary hashes agree."""
from pathlib import Path
import json,hashlib,shutil,datetime
P=Path(__file__).resolve().parents[1];D=P/'deliverables/PHYLLO-v02/firmware';D.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
build=json.loads((P/'verification/firmware-f411-build-receipt.json').read_text(encoding='utf-8'));image=json.loads((P/'verification/firmware-f411-image.json').read_text())
assert build['exit_codes']==[0,0,0] and not build['warning_lines']
for name,wanted in build['sources'].items():assert sha(P/name)==wanted,name
for name,wanted in image['artifacts'].items():
    src=P/'firmware/out-f411'/name;assert sha(src)==wanted,name;shutil.copy2(src,D/name);assert sha(D/name)==wanted
for name in ['firmware-f411-image.json','firmware-f411-build-receipt.json']:shutil.copy2(P/'verification'/name,D/name)
shutil.copy2(P/'docs/22-bring-up-and-web.md',D/'接线与烧录说明.md')
(D/'SHA256SUMS.txt').write_text('\n'.join(f'{sha(f)}  {f.name}' for f in sorted(D.iterdir()) if f.is_file() and f.name not in ['SHA256SUMS.txt','package-manifest.json'])+'\n',encoding='utf-8')
result={'package':'PHYLLO-v02 candidate firmware','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'target':image['planned_target'],'bin_origin':'0x08000000','hardware_flashed':False,'hardware_verified':False,'binary_unchanged_by_PCB_capacitor_revision':True,'checked_source_files':len(build['sources']),'artifacts':image['artifacts']}
(D/'package-manifest.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');(P/'verification/firmware-v02-package.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
