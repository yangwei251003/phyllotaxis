"""Rotate Q1 to point sources into array and allow a central drain bus feed."""
from pathlib import Path
import hashlib,json,shutil
import pcbnew as K
P=Path(__file__).resolve().parents[1];src=P/'hardware/routing/phyllo-signals.kicad_pcb';D=P/'hardware/power-routing';dst=D/'phyllo-power-prepared.kicad_pcb'
assert hashlib.sha256(src.read_bytes()).hexdigest()=='74e75be95ac4ad2fbf8e5cc23dd8f58ee7c9a6b8f6a4d256b89f2a312d7395fe'
prior=D/'phyllo-power.kicad_pcb';archive=D/'phyllo-power-v1-end-fed.kicad_pcb'
if prior.exists() and not archive.exists():shutil.copy2(prior,archive)
b=K.LoadBoard(str(src));f=next(f for f in b.GetFootprints() if f.GetReference()=='Q1');old=f.GetOrientationDegrees();f.SetOrientationDegrees(180)
removed=[]
for t in list(b.GetTracks()):
    if t.GetNetname()=='PMOS_GATE':removed.append(t.m_Uuid.AsString());b.Delete(t)
pads={(f.GetReference(),p.GetNumber()):p for f in b.GetFootprints() for p in f.Pads()};n=pads[('Q1','4')].GetNet()
for a,c in [(('R1','1'),('Q1','4')),(('R1','1'),('R2','1')),(('R2','1'),('D145','2'))]:
    t=K.PCB_TRACK(b);t.SetNet(n);t.SetLayer(K.F_Cu);t.SetWidth(K.FromMM(.2));t.SetStart(pads[a].GetPosition());t.SetEnd(pads[c].GetPosition());b.Add(t)
K.SaveBoard(str(dst),b);shutil.copy2(src.with_suffix('.kicad_pro'),dst.with_suffix('.kicad_pro'))
report={'baseline_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'prepared_sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),
 'reason':'Sources face array; drain row receives center-fed bus instead of end-fed copper.',
 'Q1_native_rotation_before_deg':old,'Q1_native_rotation_after_deg':180,'changed_signal_net_only':'PMOS_GATE',
 'removed_gate_track_uuids':removed,'replacement_gate_tracks':3,
 'Q1_pads_after':{p.GetNumber():[p.GetPosition().x/1e6,p.GetPosition().y/1e6] for p in f.Pads()}}
(P/'hardware/power-layout-refinement.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
