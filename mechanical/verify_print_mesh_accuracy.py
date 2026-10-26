"""Compare delivered STL bounds/volume to independently imported saved STEP."""
from pathlib import Path
import hashlib,json
import trimesh
from build123d import import_step
P=Path(__file__).resolve().parents[1];rows=[]
for name in ['base','microphone-holder']:
 step=P/'mechanical'/(name+'.step');stl=step.with_suffix('.stl')
 shape=import_step(step);bb=shape.bounding_box();mesh=trimesh.load_mesh(stl)
 assert mesh.is_watertight and mesh.is_volume and len(mesh.split())==1
 delta=max(abs(float(a)-float(b)) for source,target in [(bb.min,mesh.bounds[0]),(bb.max,mesh.bounds[1])] for a,b in zip(source,target))
 volume_delta=abs(float(mesh.volume)-shape.volume)/shape.volume
 assert delta<.02,(name,delta)
 assert volume_delta<.0005,(name,volume_delta)
 rows.append({'name':name,'STEP_sha256':hashlib.sha256(step.read_bytes()).hexdigest(),'STL_sha256':hashlib.sha256(stl.read_bytes()).hexdigest(),
  'STEP_bounds_mm':[list(bb.min),list(bb.max)],'STL_bounds_mm':mesh.bounds.tolist(),'max_bound_delta_mm':delta,'relative_volume_difference':volume_delta,
  'STL_watertight_positive_single_body':True,'triangles':len(mesh.faces)})
r={'status':'saved_STEP_vs_STL_dimension_and_volume_checks_pass','export_settings':{'mesh_tolerance':.001,'mesh_angular_tolerance':.025},
 'thresholds':{'max_bound_delta_mm':.02,'relative_volume_difference':.0005},'files':rows,
 'limits':['Bounds and volume are independent coarse checks, not a full Hausdorff-distance proof','CAD exports use the same requested geometry for STL and3MF','Does not include print shrinkage, hole fit, or material strength']}
(P/'verification/controls-print-mesh-accuracy.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps(r),flush=True)
