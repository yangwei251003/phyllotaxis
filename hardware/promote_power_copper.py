"""Promote only a filled candidate with clean native DRC and preserved signals."""
from pathlib import Path
import hashlib,json,subprocess,shutil,collections
import pcbnew as K
P=Path(__file__).resolve().parents[1];V=P/'verification';src=P/'hardware/power-routing/phyllo-power.kicad_pcb';dst=P/'hardware/kicad-check/phyllo-copper-review.kicad_pcb'
baseline=P/'hardware/routing/phyllo-signals.kicad_pcb';expected='74e75be95ac4ad2fbf8e5cc23dd8f58ee7c9a6b8f6a4d256b89f2a312d7395fe'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(baseline)==expected
assert sha(dst)=='c201064b42583a03cd05a340135481fbb0aeb0ca613a18811522f9f2dee072bf','Active board changed; inspect before promotion'
def inventory(b):
    return sorted((f.GetReference(),f.GetValue(),f.GetPath().AsString(),f.GetLayer(),tuple(f.GetPosition()),f.GetOrientationDegrees(),
      tuple(sorted((p.GetNumber(),p.GetNetname(),tuple(p.GetPosition()),tuple(p.GetSize()),tuple(p.GetDrillSize()),
       p.GetOrientationDegrees(),p.GetLayerSet().FmtBin()) for p in f.Pads()))) for f in b.GetFootprints())
def tracks(b):
    return {t.m_Uuid.AsString():(t.GetNetname(),tuple(t.GetStart()),tuple(t.GetEnd()),t.GetLayer(),
      t.GetWidth(K.F_Cu) if isinstance(t,K.PCB_VIA) else t.GetWidth(),t.GetDrillValue() if isinstance(t,K.PCB_VIA) else None) for t in b.GetTracks()}
old=K.LoadBoard(str(baseline));new=K.LoadBoard(str(src));prepared=K.LoadBoard(str(P/'hardware/power-routing/phyllo-power-prepared.kicad_pcb'))
assert inventory(prepared)==inventory(new)
assert [f for f in inventory(old) if f[0]!='Q1']==[f for f in inventory(new) if f[0]!='Q1']
oldq=next(f for f in old.GetFootprints() if f.GetReference()=='Q1');newq=next(f for f in new.GetFootprints() if f.GetReference()=='Q1')
assert tuple(oldq.GetPosition())==tuple(newq.GetPosition()) and newq.GetOrientationDegrees()==180
assert sorted((p.GetNumber(),p.GetNetname(),tuple(p.GetSize())) for p in oldq.Pads())==sorted((p.GetNumber(),p.GetNetname(),tuple(p.GetSize())) for p in newq.Pads())
before=tracks(prepared);after=tracks(new);original=tracks(old)
assert all(after.get(k)==v for k,v in original.items() if v[0]!='PMOS_GATE')
assert all(after.get(k)==v for k,v in before.items())
cli=Path('<LOCAL_PATH>')
run=subprocess.run([str(cli),'pcb','drc','--format','json','--severity-all','--exit-code-violations','--output',str(V/'power-candidate-drc.json'),str(src)],capture_output=True,text=True,encoding='utf-8',errors='replace')
(V/'power-candidate-drc.log').write_text(run.stdout+run.stderr,encoding='utf-8');assert run.returncode==0
drc=json.loads((V/'power-candidate-drc.json').read_text());assert not drc['violations'] and not drc['unconnected_items']
shutil.copy2(src,dst);shutil.copy2(src.with_suffix('.kicad_pro'),dst.with_suffix('.kicad_pro'));assert sha(dst)==sha(src)
r={'status':'POWER_CANDIDATE_PROMOTED_NOT_MANUFACTURING_RELEASE','base_sha256':expected,'board_sha256':sha(dst),
 'all_pin_nets_unchanged':True,'all_non_Q1_footprints_pads_unchanged':True,'prepared_layout_matches_candidate':True,
 'original_992_signal_items_other_than_PMOS_GATE_unchanged':True,'Q1_rotation_deg':180,'PMOS_GATE_replaced_tracks':3,
 'new_power_copper_items':len(after)-len(before),'total_copper_items':len(after),'vias':sum(isinstance(t,K.PCB_VIA) for t in new.GetTracks()),
 'zones':[{'net':z.GetNetname(),'layer':new.GetLayerName(z.GetLayer()),'solid_connections':z.GetPadConnection()==K.ZONE_CONNECTION_FULL,
 'filled_polygons':z.GetFilledPolysList(z.GetLayer()).OutlineCount()} for z in new.Zones()],
 'candidate_drc_exit':run.returncode,'unconnected':0,'violations':0,'ignored_checks':drc['ignored_checks'],
 'stackup':'Nominal FR4 1.6 mm, 70 um outer copper each; dielectric and mask values provisional, factory confirmation outstanding.'}
(V/'power-copper-import.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps(r))
