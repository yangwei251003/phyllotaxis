"""Promote verified signal copper only; all production gates remain open."""
from pathlib import Path
import hashlib,json,shutil
P=Path(__file__).resolve().parents[1];V=P/'verification';D=P/'hardware/routing'
receipt=json.loads((V/'signal-routing-import.json').read_text())
dst=P/'hardware/kicad-check/phyllo-copper-review.kicad_pcb';src=D/'phyllo-signals.kicad_pcb'
hashfile=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert hashfile(dst)==receipt['base_sha256']
assert hashfile(src)==receipt['board_sha256']
assert receipt['all_footprints_pads_and_nets_unchanged']
assert not receipt['native_violations'] and not receipt['signal_nets_still_unconnected']
shutil.copy2(dst,D/'phyllo-placement-baseline.kicad_pcb')
shutil.copy2(src,dst);assert hashfile(dst)==receipt['board_sha256']
receipt['promoted']=True;receipt['status']='signal_routes_merged_power_unrouted_NOT_production'
(V/'signal-routing-import.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps({'promoted':True,'tracks_and_vias':receipt['tracks_and_vias'],'power_unconnected':receipt['unconnected_items']}))
