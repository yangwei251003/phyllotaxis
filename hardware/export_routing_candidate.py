"""Native DSN export; only a copy is routed, preserving the placement baseline."""
import json,hashlib,shutil
from pathlib import Path
import pcbnew as K
P=Path(__file__).resolve().parents[1]
src=P/'hardware/kicad-check/phyllo-copper-review.kicad_pcb'
out=P/'hardware/routing';out.mkdir(exist_ok=True)
board=K.LoadBoard(str(src))
assert len(list(board.GetTracks()))==0
dst=out/'phyllo-routing.kicad_pcb'
shutil.copy2(src,dst)
shutil.copy2(src.with_suffix('.kicad_pro'),dst.with_suffix('.kicad_pro'))
dsn=dst.with_suffix('.dsn')
assert K.ExportSpecctraDSN(board,str(dsn))
report={'status':'native_DSN_exported_no_routing_yet','source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),
        'dsn_sha256':hashlib.sha256(dsn.read_bytes()).hexdigest(),'native_version':K.Version()}
(P/'verification/routing-export.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
