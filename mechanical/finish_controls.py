"""Finish new control geometry serially, preserving the one-live-process rule."""
from pathlib import Path
import sys,subprocess,os,json
P=Path(__file__).resolve().parents[1];env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1','CADGEN_COMPONENT_WORKERS':'1'}
steps=[('refined_print_meshes',['run_controls_delivery.py','meshes']),
       ('updated_controls_fit',['verify_controls.py']),
       ('support_components_against_new_shell',['verify_component_spaces.py']),
       ('connectors_against_new_shell',['verify_connectors.py']),
       ('whole_assembly',['run_controls_delivery.py','assembly']),
       ('saved_STEP_readback',['verify_export_current.py']),
       ('print_mesh_accuracy',['verify_print_mesh_accuracy.py']),
       ('saved_3MF_readback',['verify_controls_3mf.py']),
       ('minimum_wall_sample_trace',['trace_vent_sample.py'])]
receipt=[]
for name,args in steps:
 print('BEGIN '+name,flush=True)
 proc=subprocess.run([sys.executable,'-X','utf8',str(P/'mechanical'/args[0]),*args[1:]],env=env)
 receipt.append({'stage':name,'exit_code':proc.returncode})
 (P/'verification/controls-finalization.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
 if proc.returncode:raise SystemExit(proc.returncode)
 print('DONE '+name,flush=True)
