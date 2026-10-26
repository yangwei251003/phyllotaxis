"""Generate and fill a power candidate from the immutable signal-routing baseline."""
from pathlib import Path
import hashlib,json,math,shutil
import pcbnew as K
P=Path(__file__).resolve().parents[1];D=P/'hardware/power-routing';D.mkdir(exist_ok=True)
src=D/'phyllo-power-prepared.kicad_pcb';dst=D/'phyllo-power.kicad_pcb'
plan=json.loads((P/'hardware/power-copper-plan.json').read_text())
assert hashlib.sha256(src.read_bytes()).hexdigest()==plan['base_sha256']
b=K.LoadBoard(str(src));nets={n.GetNetname():n for n in b.GetNetInfo().NetsByNetcode().values()}
def v(p):return K.VECTOR2I(round(p[0]*1e6),round(p[1]*1e6))
def track(net,a,c,w,layer):
    t=K.PCB_TRACK(b);t.SetNet(nets[net]);t.SetStart(v(a));t.SetEnd(v(c));t.SetWidth(K.FromMM(w));t.SetLayer(layer);b.Add(t)
def via(net,p,size,drill):
    t=K.PCB_VIA(b);t.SetNet(nets[net]);t.SetPosition(v(p));t.SetWidth(K.FromMM(size));t.SetDrill(K.FromMM(drill));t.SetLayerPair(K.F_Cu,K.B_Cu);b.Add(t)
for f in plan['fanouts']:
    track(f['net'],f['from'],f['via'],f['width'],K.F_Cu);via(f['net'],f['via'],f['diameter'],f['drill'])
f=plan['mcu_branch'];track(f['net'],f['from'],f['via'],f['width'],K.F_Cu);via(f['net'],f['via'],f['diameter'],f['drill'])
for a,c in zip(f['bottom_path'],f['bottom_path'][1:]):track(f['net'],a,c,f['width'],K.B_Cu)
def zone(net,layer,points,priority=0):
    z=K.ZONE(b);z.SetNet(nets[net]);z.SetLayer(layer);z.SetAssignedPriority(priority)
    z.SetLocalClearance(K.FromMM(.25));z.SetMinThickness(K.FromMM(.20));z.SetPadConnection(K.ZONE_CONNECTION_FULL)
    z.SetIslandRemovalMode(K.ISLAND_REMOVAL_MODE_ALWAYS);z.SetThermalReliefGap(K.FromMM(.25));z.SetThermalReliefSpokeWidth(K.FromMM(.5))
    outline=z.Outline();outline.NewOutline()
    for x,y in points:outline.Append(round(x*1e6),round(y*1e6))
    b.Add(z)
circle=[(100+89.4*math.cos(i*math.tau/720),100+89.4*math.sin(i*math.tau/720)) for i in range(720)]
zone('5V_LED',K.F_Cu,circle);zone('GND',K.B_Cu,circle)
# Full-current input copper, solid pad connections and center-fed drain bus.
# Q1 sources point into the array; VIN reaches the bus through its center stem.
zone('VIN_FUSED',K.F_Cu,[(84.8,182.8),(91.2,182.8),(91.2,186.8),(88.8,186.8),
    (88.8,187.5),(98.1,187.5),(98.1,178.9),(102.5,178.9),(102.5,188.8),
    (87.2,188.8),(87.2,186.8),(84.8,186.8)],10)
b.BuildConnectivity();ok=K.ZONE_FILLER(b).Fill(b.Zones());assert ok,'Native zone fill failed'
K.SaveBoard(str(dst),b)
# Stackup's C++ descriptor is not exposed by this installed SWIG build. Use the
# documented native file section, then immediately load/save it with KiCad.
stack='''
        (stackup
            (layer "F.SilkS" (type "Top Silk Screen"))
            (layer "F.Paste" (type "Top Solder Paste"))
            (layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
            (layer "F.Cu" (type "copper") (thickness 0.07))
            (layer "dielectric 1" (type "core") (thickness 1.44) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
            (layer "B.Cu" (type "copper") (thickness 0.07))
            (layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
            (layer "B.Paste" (type "Bottom Solder Paste"))
            (layer "B.SilkS" (type "Bottom Silk Screen"))
            (dielectric_constraints no)
        )'''
text=dst.read_text(encoding='utf-8');assert '(stackup' not in text
dst.write_text(text.replace('(setup','(setup'+stack,1),encoding='utf-8')
reloaded=K.LoadBoard(str(dst));K.SaveBoard(str(dst),reloaded)
assert dst.read_text(encoding='utf-8').count('(thickness 0.07)')==2
shutil.copy2(src.with_suffix('.kicad_pro'),dst.with_suffix('.kicad_pro'))
pro=json.loads(dst.with_suffix('.kicad_pro').read_text(encoding='utf-8'))
pro['board']['design_settings']['rules']['min_clearance']=.2
dst.with_suffix('.kicad_pro').write_text(json.dumps(pro,indent=2),encoding='utf-8')
(D/'fp-lib-table').write_text((P/'hardware/routing/fp-lib-table').read_text(),encoding='utf-8')
print(json.dumps({'candidate':str(dst),'zones':len(list(b.Zones())),'tracks_and_vias':len(list(b.GetTracks())),
 'sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),'filled':ok}))
