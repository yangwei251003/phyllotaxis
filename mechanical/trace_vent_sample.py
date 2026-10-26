"""Locate the DfAM minimum ray on the exact delivered mesh, without discarding it."""
from pathlib import Path
import json, hashlib
import numpy as np
import trimesh

P = Path(__file__).resolve().parents[1]
path = P / 'mechanical/base.stl'
facts = json.loads((P / 'verification/controls-dfam-base.json').read_text())
sample = facts['wall_thickness']['thinnest_samples'][0]
mesh = trimesh.load_mesh(path)
target = np.array(sample['location_xyz'])
idx = int(np.argmin(np.linalg.norm(mesh.triangles_center - target, axis=1)))
origin = mesh.triangles_center[idx]
direction = -mesh.face_normals[idx]
assert np.linalg.norm(origin - target) < .01
hits, rays, faces = mesh.ray.intersects_location(
    ray_origins=[origin + direction * 1e-4],
    ray_directions=[direction], multiple_hits=False)
assert len(hits) == 1
distance = float(np.linalg.norm(hits[0] - origin - direction * 1e-4))
assert abs(distance - sample['thickness_mm']) < .001
assert abs(hits[0][0] - 48.5) < .001 and 9.5 <= hits[0][2] <= 12.5
assert np.linalg.norm(mesh.face_normals[faces[0]] - [-1, 0, 0]) < .001
# Original vent cutter: X41.5..48.5, Y84..106, Z9.5..12.5.
# The ray ends at its vertical end wall, before reaching the concentric bore.
result = {
    'status': 'minimum_ray_located_at_vent_end_NOT_global_wall_or_strength_proof',
    'mesh_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
    'dfam_min_mm': facts['wall_thickness']['min_mm'],
    'dfam_p05_mm': facts['wall_thickness']['p05_mm'],
    'surface_point_mm': origin.tolist(), 'surface_normal': (-direction).tolist(),
    'hit_point_mm': hits[0].tolist(), 'hit_normal': mesh.face_normals[faces[0]].tolist(),
    'ray_length_mm': distance,
    'source_vent_bounds_mm': [[41.5, 84, 9.5], [48.5, 106, 12.5]],
    'nominal_unperforated_radial_wall_mm': 3,
    'interpretation': 'Ray runs inward from outer cylindrical skin and exits at a vent end face; it is not distance between concentric wall faces. The short edge chord is retained as a local print concern, not silently discarded.',
    'disposition': 'Need slice/print review of vent edges. Sampled p05 meets the skill default 1.6mm, but no blanket all-walls pass or print release is asserted.'
}
(P / 'verification/controls-vent-thickness-trace.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result), flush=True)
