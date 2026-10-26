"""Local, offline slicing profiles derived from installed Orca system presets."""
from pathlib import Path
import json, hashlib, subprocess, sys

P = Path(__file__).resolve().parents[1]
D = P / 'verification/slicing'
D.mkdir(parents=True, exist_ok=True)
PROFILE_ROOT = Path('C:/Program Files/OrcaSlicer/resources/profiles/Prusa')
SOURCES = {}

def resolved(kind, name, stack=()):
    assert name not in stack
    path = PROFILE_ROOT / kind / (name + '.json')
    data = json.loads(path.read_text(encoding='utf-8'))
    SOURCES[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    parent = data.get('inherits')
    merged = resolved(kind, parent, stack + (name,)) if parent else {}
    merged.update(data)
    merged.pop('inherits', None)
    return merged

def save(name, data):
    path = D / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return str(path.resolve())

machine = resolved('machine', 'Prusa MK4 0.4 nozzle')
process = resolved('process', '0.20mm Standard @MK4')
filament = resolved('filament', 'Prusa Generic PETG @MK4')
# Process choices are explicit review assumptions, not measured machine tuning.
overrides = {'wall_loops':'4','sparse_infill_density':'20%',
             'sparse_infill_pattern':'gyroid','enable_support':'1',
             'support_type':'normal(auto)','support_threshold_angle':'45',
             'support_on_build_plate_only':'0','support_top_z_distance':'0.2',
             'brim_width':'3','brim_type':'outer_only','skirt_loops':'0',
             'layer_height':'0.2','initial_layer_print_height':'0.2',
             'curr_bed_type':'High Temp Plate'}
process.update(overrides)
process['name'] = 'PHYLLO review PETG 0.20mm 4 walls 20pct normal support'
machine_path = save('mk4-system-machine.json', machine)
process_path = save('phyllo-review-process.json', process)
filament_path = save('mk4-system-petg.json', filament)
wrapper = {'backend':'orcaslicer','native_config':machine_path,
           'native_settings':[machine_path,process_path],
           'native_filaments':[filament_path],
           'machine':{'name':'Prusa MK4 0.4 nozzle — REVIEW ONLY, actual supplier machine unknown',
                      'bed_size_mm':[250,210],'z_height_mm':220,
                      'motion_bounds_mm':{'x':[0,250],'y':[-4,210],'z':[0,220]}},
           'filament':{'type':'PETG','nozzle_temp_c':255,'bed_temp_c':80}}
save('profile-REVIEW-ONLY.json',wrapper)
save('profile-provenance.json',{
    'status':'OFFLINE_REVIEW_NOT_FOR_PRINTING',
    'sources':SOURCES,'overrides':overrides,
    'native_profile_notes':'Original MK4 machine code retained. Native start G-code explicitly uses Y=-4 for purge, therefore validation motion bound includes -4. PETG 255C/bed80C from inherited system preset, not recommendation for an unknown filament.',
    'scope':'Print geometry and support review; no claim user or supplier owns MK4, no printer contact, no job upload, no machine qualification.',
    'official_CLI_reference':'https://github.com/OrcaSlicer/OrcaSlicer/wiki/cli_actions',
})
exe = 'C:/Program Files/OrcaSlicer/orca-slicer.exe'
r = subprocess.run([exe,'--help'],capture_output=True,encoding='utf-8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW)
(D/'orca-cli-help.txt').write_text(r.stdout+'\n'+r.stderr,encoding='utf-8')
print(json.dumps({'profiles':str(D),'native_sources':len(SOURCES),'help_returncode':r.returncode,'help_prefix':r.stdout[:400]},ensure_ascii=False))
