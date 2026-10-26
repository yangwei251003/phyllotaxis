"""Offline ELF/vector/range and binary consistency checks. Never flashes a target."""
from pathlib import Path
import hashlib,json,re,struct,subprocess
P=Path(__file__).resolve().parent
B=P/'out-f411'
elf=(B/'phyllo_candidate.elf').read_bytes()
binary=(B/'phyllo_candidate.bin').read_bytes()
header=struct.unpack_from('<16sHHIIIIIHHHHHH',elf)
assert header[0][:7]==b'\x7fELF\x01\x01\x01' and header[1]==2 and header[2]==40
entry,phoff,phsize,phnum=header[4],header[5],header[9],header[10]
flash=0x08000000;flash_end=flash+512*1024;ram=0x20000000;ram_end=ram+128*1024
segments=[]
for i in range(phnum):
    kind,offset,vaddr,paddr,filesz,memsz,flags,align=struct.unpack_from('<IIIIIIII',elf,phoff+i*phsize)
    if kind!=1:continue
    assert not flags&1 or not flags&2,'unexpected writable executable load segment'
    assert (flash<=vaddr and vaddr+memsz<=flash_end) or (ram<=vaddr and vaddr+memsz<=ram_end)
    if filesz:
        assert flash<=paddr and paddr+filesz<=flash_end
        start=paddr-flash
        assert binary[start:start+filesz]==elf[offset:offset+filesz]
    segments.append(dict(vaddr=hex(vaddr),paddr=hex(paddr),file_bytes=filesz,memory_bytes=memsz,flags=flags))
assert not subprocess.check_output(['arm-none-eabi-nm','-u',str(B/'phyllo_candidate.elf')],text=True).strip()
nm=subprocess.check_output(['arm-none-eabi-nm','-n',str(B/'phyllo_candidate.elf')],text=True)
symbols={m.group(3):(int(m.group(1),16),m.group(2)) for line in nm.splitlines() if (m:=re.match(r'^([0-9a-fA-F]+)\s+(\S)\s+(\S+)$',line))}
assert struct.unpack_from('<I',binary,0)[0]==ram_end
assert entry==symbols['Reset_Handler'][0]|1
vectors={'Reset_Handler':1,'HardFault_Handler':3,'SysTick_Handler':15,
         'DMA1_Stream3_IRQHandler':16+14,'DMA2_Stream5_IRQHandler':16+68}
for name,index in vectors.items():
    assert struct.unpack_from('<I',binary,index*4)[0]==symbols[name][0]|1,name
    if name!='Reset_Handler':assert symbols[name][1]=='T',name+' is not overridden'
assert 'malloc' not in symbols and '_sbrk' not in symbols
ram_static=symbols['_ebss'][0]-ram
stack=symbols['_Min_Stack_Size'][0]
assert ram_static+stack<=128*1024
report={'status':'offline_link_and_image_checks_pass','hardware_verified':False,'flash_authorized':False,
    'planned_target':'WeAct STM32F411CEU6 V3.1, 25MHz HSE (not received)',
    'flash_bytes':len(binary),'ram_static_bytes':ram_static,'stack_reserved_bytes':stack,
    'ram_reserved_total_bytes':ram_static+stack,'entry':hex(entry),'vectors_verified':list(vectors),
    'no_unresolved_symbols':True,'no_malloc_or_sbrk':True,'segments':segments,
    'artifacts':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in B.glob('phyllo_candidate.*') if f.suffix in ['.elf','.bin','.hex','.map']},
    'not_verified':['physical board identity','waveform timing','microphone data/slot','runtime/cycle budget','current/temperature','PCB chain after routing']}
(P.parent/'.runtime'/'verification').mkdir(parents=True,exist_ok=True)
(P.parent/'.runtime'/'verification'/'firmware-f411-image.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
