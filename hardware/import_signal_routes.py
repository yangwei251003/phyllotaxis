"""Import SES to a candidate copy; native DRC and pad/footprint invariants gate promotion."""
from pathlib import Path
import collections,hashlib,json,subprocess,shutil,sys
import pcbnew as K
P=Path(__file__).resolve().parents[1];D=P/'hardware/routing';V=P/'verification'
src=D/'phyllo-routing.kicad_pcb';ses=D/'phyllo-signals.ses';dst=D/'phyllo-signals.kicad_pcb'
manual={'5V_LED','5V_MCU','GND','VIN_FUSED'}
def inventory(b):
    return sorted((f.GetReference(),f.GetValue(),f.GetPath().AsString(),f.GetLayer(),tuple(f.GetPosition()),f.GetOrientationDegrees(),
      tuple(sorted((p.GetNumber(),p.GetNetname(),tuple(p.GetPosition()),tuple(p.GetSize()),tuple(p.GetDrillSize()),
                    p.GetOrientationDegrees(),p.GetLayerSet().FmtBin()) for p in f.Pads()))) for f in b.GetFootprints())
b=K.LoadBoard(str(src));before=inventory(b)
pad_counts=collections.Counter(p.GetNetname() for f in b.GetFootprints() for p in f.Pads())
single={n for n,count in pad_counts.items() if count<=1}
# KiCad 10.0.5 rejects FreeRouting's placement entry with an empty image ID.
# Placement is optional in SES and not wanted here: preserve the exact source
# coordinates/rotation instead of re-quantizing them through DSN resolution.
text=ses.read_text(encoding='utf-8');start=text.index('(placement');depth=0;quoted=False;end=None
for i in range(start,len(text)):
    c=text[i]
    if c=='"' and (i==0 or text[i-1]!='\\'):quoted=not quoted
    if not quoted:
        if c=='(':depth+=1
        elif c==')':
            depth-=1
            if depth==0:end=i+1;break
assert end is not None
routing_only=text[:start]+text[end:]
assert routing_only[routing_only.index('(routes'):]==text[text.index('(routes'):]
normalized=D/'phyllo-signals-routing-only.ses';normalized.write_text(routing_only,encoding='utf-8')
raw=D/'phyllo-ses-imported.kicad_pcb'
# Run the native importer in a separate process. In this installed build the
# scripting type registry loses typed iterators after SES import; a fresh load
# restores them. Native file save is still available in the importing process.
run=subprocess.run([sys.executable,str(Path(__file__).with_name('native_ses_import.py')),str(src),str(normalized),str(raw)],
 capture_output=True,text=True,encoding='utf-8',errors='replace')
(V/'native-ses-import.log').write_text(run.stdout+run.stderr,encoding='utf-8');assert run.returncode==0
b=K.LoadBoard(str(raw));assert inventory(b)==before
# This run routed ignored classes as well. Remove all power copper from the
# imported candidate; manual power-plane design remains a separate task.
removed=collections.Counter()
for track in list(b.GetTracks()):
    if track.GetNetname() in manual|single:removed[track.GetNetname()]+=1;b.Delete(track)
assert inventory(b)==before
K.SaveBoard(str(dst),b);readback=K.LoadBoard(str(dst));assert inventory(readback)==before
assert all(t.GetNetname() not in manual for t in readback.GetTracks())
shutil.copy2(src.with_suffix('.kicad_pro'),dst.with_suffix('.kicad_pro'))
table=(P/'hardware/kicad-check/fp-lib-table').read_text(encoding='utf-8')
(D/'fp-lib-table').write_text(table.replace('${KIPRJMOD}/PhylloReview.pretty','${KIPRJMOD}/../kicad-check/PhylloReview.pretty'),encoding='utf-8')
cli=Path('<LOCAL_PATH>')
args=[str(cli),'pcb','drc','--format','json','--severity-all','--exit-code-violations','--output',str(V/'signal-routing-drc.json'),str(dst)]
run=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace')
(V/'signal-routing-drc.log').write_text(run.stdout+run.stderr,encoding='utf-8');assert run.returncode in {0,5}
drc=json.loads((V/'signal-routing-drc.json').read_text(encoding='utf-8'))
counts=collections.Counter(t.GetNetname() for t in readback.GetTracks())
items={p.m_Uuid.AsString():p.GetNetname() for f in readback.GetFootprints() for p in f.Pads()}
items.update({t.m_Uuid.AsString():t.GetNetname() for t in readback.GetTracks()})
remaining=collections.Counter()
for problem in drc['unconnected_items']:
    nets={items[item['uuid']] for item in problem['items']}
    assert len(nets)==1,nets
    remaining[next(iter(nets))]+=1
violations=collections.Counter(v['type'] for v in drc['violations'])
report={'status':'signal_candidate_imported_NOT_production','base_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),
 'session_sha256':hashlib.sha256(ses.read_bytes()).hexdigest(),'board_sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),
 'routing_only_session_sha256':hashlib.sha256(normalized.read_bytes()).hexdigest(),
 'SES_normalization':'Removed optional placement section only; routes section byte-equivalent as decoded UTF-8; exact source placement retained.',
 'all_footprints_pads_and_nets_unchanged':True,'power_route_items_removed':dict(removed),
 'tracks_and_vias':len(list(readback.GetTracks())),'vias':sum(isinstance(t,K.PCB_VIA) for t in readback.GetTracks()),
 'nets_with_copper':len(counts),'per_net_items':dict(counts),'native_violations':dict(violations),
 'unconnected_items':len(drc['unconnected_items']),'unconnected_by_net':dict(remaining),
 'signal_nets_still_unconnected':sorted(set(remaining)-manual),
 'drc_exit_code':run.returncode,'promoted':False}
(V/'signal-routing-import.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='per_net_items'}))
