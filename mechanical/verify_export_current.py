"""Check saved deliverable STEP dimensions independently of preview caches."""
from pathlib import Path
import json,hashlib
from build123d import import_step
P=Path(__file__).resolve().parents[1];rows=[]
controls=json.loads((P/'mechanical/controls.json').read_text(encoding='utf-8'))
for name in ['assembly','connector-space']:
    path=P/'mechanical'/(name+'.step');shape=import_step(path);b=shape.bounding_box()
    row={'file':str(path.relative_to(P)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
         'size_mm':list(b.size),'min_mm':list(b.min),'max_mm':list(b.max),'solids':len(shape.solids())}
    if name=='assembly':assert abs(b.size.X-200)<.01 and abs(b.max.Z-46)<.01 and abs(b.min.Z+controls['feet']['height'])<.01
    else:assert abs(b.size.X-180)<.01 and abs(b.min.Z-5)<.01 and abs(b.max.Z-31.6)<.01
    rows.append(row)
report={'status':'saved_STEP_bounds_match_current_design_NOT_full_shape_validation','files':rows,
 'scope':'Independent direct STEP import avoids stale viewer/export cache. Vendor reference validity issues remain recorded separately.'}
(P/'verification/current-cad-export.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
