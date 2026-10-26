"""Physical volumes of reserved space, not vendor connector models."""
from pathlib import Path
import json
from build123d import Box,Pos
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from connectors import SPEC,envelope
from parts import base,pcb,C
P=Path(__file__).resolve().parents[1]
def overlap(a,b):
    common=BRepAlgoAPI_Common(a.wrapped,b.wrapped);common.Build();assert common.IsDone()
    g=GProp_GProps();BRepGProp.VolumeProperties_s(common.Shape(),g);return abs(g.Mass())
shell=base();disk=pcb().moved(Pos(0,0,C['pcb_seat_z_mm']))
# Broad holder/reference-board envelope is deliberately larger than actual parts.
controller=Pos(0,0,15)*Box(66,46,24)
items=[envelope(r) for r in SPEC['envelopes']+SPEC['assumed_wire_reserves']]
checks=[]
for i,a in enumerate(items):
    for b in [shell,disk,controller,*items[:i]]:
        v=overlap(a,b);assert v<1e-4,(a.label,b.label,v)
        checks.append({'a':a.label,'b':b.label or 'controller_conservative_box','overlap_mm3':v,'gap_mm':a.distance_to(b)})
    assert a.is_valid and len(a.solids())==1
audit=json.loads((P/'verification/connector-placement-audit.json').read_text())
report={'status':'space_envelopes_fit_analytically_NOT_physical_connector_validation','pairs':checks,
 'PCB_connector_holes':audit['native_hole_positions_checked'],
 'limits':SPEC['limits']+['Hole registration sourced from independently checked native PCB pad readback','Touching the PCB underside is intentional; envelopes omit pins/solder']}
(P/'verification/connector-space-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'status':report['status'],'pairs':len(checks),'max_overlap_mm3':max(c['overlap_mm3'] for c in checks)}))
