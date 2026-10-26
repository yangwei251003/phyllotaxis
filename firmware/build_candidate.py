"""Reproducible, logged offline build. Does not enumerate or access hardware."""
from pathlib import Path
import datetime,hashlib,json,subprocess,sys
F=Path(__file__).resolve().parent
commands=[['cmake','-S',str(F/'platform/stm32f411'),'-B',str(F/'out-f411'),'-G','Ninja','-DCMAKE_TOOLCHAIN_FILE=arm-gcc.cmake'],
          ['cmake','--build',str(F/'out-f411'),'--clean-first'],
          [sys.executable,str(F/'verify_candidate.py')]]
logs=[];codes=[]
for command in commands:
    r=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
    logs.append('COMMAND '+json.dumps(command,ensure_ascii=False)+'\n'+r.stdout);codes.append(r.returncode)
    if r.returncode:break
V=F.parent/'.runtime'/'verification';V.mkdir(parents=True,exist_ok=True)
(V/'firmware-f411-build.log').write_text('\n\n'.join(logs),encoding='utf-8')
sources=list((F/'platform/stm32f411').rglob('*'))+list((F/'src').glob('*.c'))+list((F/'include').glob('*.h'))+[F/'sources.lock.json',F.parent/'shared/chain.json',F.parent/'shared/layout.json']
receipt={'kind':'offline_build_not_hardware_test','time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'commands':commands[:len(codes)],'exit_codes':codes,'compiler':subprocess.check_output(['arm-none-eabi-gcc','--version'],text=True).splitlines()[0],
         'warning_lines':[line for block in logs for line in block.splitlines() if 'warning:' in line.lower()],
         'sources':{p.relative_to(F.parent).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources if p.is_file()}}
(V/'firmware-f411-build-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'exit_codes':codes,'warnings':len(receipt['warning_lines']),'hardware_accessed':False}))
raise SystemExit(0 if codes==[0,0,0] else 1)
