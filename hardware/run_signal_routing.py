"""Bounded local FreeRouting candidate run. Power nets are explicitly excluded."""
from pathlib import Path
import hashlib,json,re,shlex,subprocess,os
P=Path(__file__).resolve().parents[1];D=P/'hardware/routing';V=P/'verification'
if (D/'phyllo-signals.ses').exists():
    raise RuntimeError('A completed SES exists. Preserve it and use a new explicitly named run for further routing.')
jar=Path(os.environ['LOCALAPPDATA'])/'PHYLLO/tools/freerouting-2.4.1.jar'
sha=hashlib.sha256(jar.read_bytes()).hexdigest()
assert sha=='251101c3eeac22d7e7dfcf6796603279e5d1000283eb82d8f093780f7afc6aa9'
source=D/'phyllo-routing.dsn';s=source.read_text(encoding='utf-8')
match=re.search(r'\(class kicad_default\s+(.*?)\s*\(circuit',s,re.S);assert match
members=shlex.split(match.group(1));manual=['5V_LED','5V_MCU','GND','VIN_FUSED']
assert all(n in members for n in manual)
signal=[n for n in members if n not in manual]
quote=lambda n:json.dumps(n) if any(c in n for c in ' ()') else n
header=' '.join(quote(n) for n in signal)+'\n      '
s=s[:match.start(1)]+header+s[match.end(1):]
# Make separate routing classes without changing any net's membership/pins.
at=s.index('    (class kicad_default')
power='    (class ManualPower '+' '.join(manual)+' (circuit (use_via "Via[0-1]_600:300_um")) (rule (width 1000) (clearance 250)))\n'
s=s[:at]+power+s[at:]
dst=D/'phyllo-signals.dsn';dst.write_text(s,encoding='utf-8')
user=Path(os.environ['LOCALAPPDATA'])/'PHYLLO/freerouting'
command=['C:/Program Files/Java/jdk-25/bin/java.exe','-Xmx2048m','-Dfile.encoding=UTF-8','-jar',str(jar),'-de',str(dst),'-do',str(D/'phyllo-signals.ses'),
 '-mp','20','-mt','2','-inc','ManualPower','-da','-l','en','--gui.enabled=false','--api_server.enabled=false',
 '--logging.file.enabled=false','--router.fanout.enabled=false',
 '--router.strict_drc=true','--router.optimizer.improvement_threshold=0.025',f'--user_data_path={user}']
receipt={'tool':'FreeRouting 2.4.1','jar_sha256':sha,'source':'https://github.com/freerouting/freerouting/releases/tag/v2.4.1',
 'source_dsn_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'modified_dsn_sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),
 'manual_power_nets':manual,'class_members':{'ManualPower':manual,'kicad_default':signal},'command':command,'status':'started'}
path=V/'signal-routing-run.json';path.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print('Starting local FreeRouting; four power nets excluded.',flush=True)
with (V/'signal-routing.log').open('w',encoding='utf-8') as log:
    p=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=900)
receipt['exit_code']=p.returncode;receipt['status']='run_finished_requires_native_import_and_DRC' if p.returncode==0 else 'run_failed_or_stopped_no_success_claim'
ses=D/'phyllo-signals.ses'
if ses.is_file():receipt['session_sha256']=hashlib.sha256(ses.read_bytes()).hexdigest()
path.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps({'status':receipt['status'],'exit_code':p.returncode,'session_exists':ses.is_file()}))
raise SystemExit(p.returncode)
