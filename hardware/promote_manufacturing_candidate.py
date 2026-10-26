"""Promote a hash-bound candidate only after native readback and full parity DRC."""
from pathlib import Path
import hashlib,json,shutil
P=Path(__file__).resolve().parents[1];V=P/'verification';S=P/'hardware/manufacturing-review';D=P/'hardware/kicad-check'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
readback=json.loads((V/'manufacturing-layer-readback.json').read_text());drcpath=V/'manufacturing-candidate-drc.json';drc=json.loads(drcpath.read_text())
src=S/'phyllo-copper-review.kicad_pcb';dst=D/src.name
assert sha(src)==readback['board_sha256'] and sha(dst)==readback['base_sha256']
assert not drc['violations'] and not drc['unconnected_items'] and not drc['schematic_parity']
assert drcpath.stat().st_mtime>=src.stat().st_mtime and drc['source']==src.name
for p in [S/'phyllo-copper-review.kicad_sch',S/'PhylloReview.kicad_sym',*sorted((S/'sheets').glob('*.kicad_sch'))]:
    assert sha(p)==sha(D/p.relative_to(S)),f'Schematic changed since candidate: {p}'
for name in [src.name,'phyllo-copper-review.kicad_pro','fp-lib-table']:shutil.copy2(S/name,D/name)
shutil.copytree(S/'PhylloReview.pretty',D/'PhylloReview.pretty',dirs_exist_ok=True)
assert sha(dst)==readback['board_sha256']
r={**readback,'status':'MANUFACTURING_DETAIL_CANDIDATE_PROMOTED_NOT_PRODUCTION_RELEASE','drc_report_sha256':sha(drcpath),
 'drc_violations':0,'unconnected':0,'schematic_parity_issues':0,'ignored_checks':drc['ignored_checks']}
(V/'manufacturing-layer-promotion.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in r.items() if k!='custom_paste_apertures'}))
