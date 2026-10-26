"""Read saved 3MF build items, applying their component/item transforms in mm."""
from pathlib import Path
import json, hashlib, zipfile, xml.etree.ElementTree as ET
import numpy as np
import trimesh

P = Path(__file__).resolve().parents[1]
rows = []
for name in ['base', 'microphone-holder']:
    path = P / 'mechanical' / (name + '.3mf')
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        root = ET.fromstring(archive.read('3D/3dmodel.model'))
    assert root.attrib['unit'] == 'millimeter'
    ns = {'m': root.tag.split('}')[0][1:]}
    objects = {o.attrib['id']: o for o in root.findall('m:resources/m:object', ns)}

    def transformed(mesh, text):
        if text:
            t = np.array([float(x) for x in text.split()]).reshape(4, 3)
            mesh.vertices = mesh.vertices @ t[:3] + t[3]
        return mesh

    def read_object(identifier, visited=()):
        assert identifier not in visited
        obj = objects[identifier]
        raw = obj.find('m:mesh', ns)
        if raw is not None:
            verts = [[float(v.attrib[k]) for k in ['x', 'y', 'z']]
                     for v in raw.findall('m:vertices/m:vertex', ns)]
            faces = [[int(v.attrib[k]) for k in ['v1', 'v2', 'v3']]
                     for v in raw.findall('m:triangles/m:triangle', ns)]
            return trimesh.Trimesh(verts, faces, process=True)
        pieces = [transformed(read_object(c.attrib['objectid'], (*visited, identifier)), c.attrib.get('transform'))
                  for c in obj.findall('m:components/m:component', ns)]
        assert pieces
        return trimesh.util.concatenate(pieces)

    built = [transformed(read_object(i.attrib['objectid']), i.attrib.get('transform'))
             for i in root.findall('m:build/m:item', ns)]
    mesh = trimesh.util.concatenate(built)
    stl = trimesh.load_mesh(path.with_suffix('.stl'))
    bounds_delta = float(np.max(np.abs(mesh.bounds - stl.bounds)))
    volume_delta = abs(float(mesh.volume) - float(stl.volume)) / float(stl.volume)
    assert mesh.is_watertight and mesh.is_volume and len(mesh.split()) == 1
    assert bounds_delta < .002 and volume_delta < .0001
    rows.append({'file': path.relative_to(P).as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                 'unit': 'millimeter', 'item_transforms_applied': True, 'watertight_positive_single_body': True,
                 'bounds_mm': mesh.bounds.tolist(), 'STL_bounds_max_difference_mm': bounds_delta,
                 'STL_volume_relative_difference': volume_delta})
result = {'status': 'saved_3MF_build_geometry_matches_STL_NOT_print_acceptance', 'files': rows}
(P / 'verification/controls-3mf-readback.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result))
