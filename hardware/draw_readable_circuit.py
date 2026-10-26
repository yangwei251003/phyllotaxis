"""Supplementary readable circuit, audited against the saved native netlist.

Does not import or mutate the native EDA sources. All coordinates are diagram
coordinates, never physical wiring or assembly positions.
"""
from pathlib import Path
import hashlib, json, xml.etree.ElementTree as ET,sys
import pymupdf as fitz

P = Path(__file__).resolve().parents[1]
V02='--prototype-v02' in sys.argv
OUT = P / ('hardware/prototype-v02/readable-circuit' if V02 else 'hardware/readable-circuit')
OUT.mkdir(exist_ok=True)
V = P / 'verification'
PCB = P / ('hardware/prototype-v02/phyllo-copper-review.kicad_pcb' if V02 else 'hardware/kicad-check/phyllo-copper-review.kicad_pcb')
EXPECTED = '3a58edfbd13dbbb5d1b225437de182d8879b73f9131223cfc42725c6b7bca050' if V02 else '17f93c409632b65271121363c62a9ff14ae228ac94b24b676f731eafd3b3479e'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(PCB) == EXPECTED
intent_file = P / ('hardware/prototype-v02/power_candidate.json' if V02 else 'hardware/power_candidate.json')
netlist_file = P/'hardware/prototype-v02/netlist.xml' if V02 else V / 'kicad-schematic-netlist.xml'
intent = json.loads(intent_file.read_text(encoding='utf-8'))
expected = {(c['ref'], str(pin)): net for c in intent['components'] for pin, net in c['pins'].items()}
native = {(n.attrib['ref'], n.attrib['pin']): net.attrib['name']
          for net in ET.parse(netlist_file).findall('nets/net') for n in net.findall('node')}
for key, net in expected.items():
    if net is not None:
        assert native[key] == net, (key, net, native.get(key))
    else:
        assert 'unconnected-' in native[key], (key, native[key])

INK = (0.10, 0.17, 0.23)
MUTED = (0.35, 0.42, 0.48)
POWER = (0.65, 0.22, 0.10)
SIGNAL = (0.04, 0.42, 0.44)
WARN = (0.64, 0.38, 0.05)
FONT = 'C:/Windows/Fonts/msyh.ttc'
doc = fitz.open()
drawn = []
wires = []
pages = []

def page(title, subtitle):
    p = doc.new_page(width=1600, height=1050)
    p.insert_font(fontname='phyllo', fontfile=FONT)
    pages.append(p)
    text(p, 60, 70, 'PHYLLO  /  ' + title, 32)
    text(p, 60, 106, subtitle, 17, MUTED)
    p.draw_line((60, 128), (1540, 128), color=INK, width=1)
    text(p, 60, 1005, 'PROTO-02 电路解释图 · 物理针序见接线说明 · 实物未验证' if V02 else '候选电路解释图 · 不按位置接线 · 未放行制造 / 烧录 / 采购', 17, WARN)
    text(p, 1120, 1005, f'2026-10-03   |   {len(pages):02d} / '+('03' if V02 else '02'), 17, MUTED)
    return p

def text(p, x, y, s, size=18, color=INK):
    p.insert_text((x,y), s, fontname='phyllo', fontsize=size, color=color)

def line(p, pts, color=INK, width=2):
    p.draw_polyline(pts, color=color, width=width)

def box(p, x, y, w, h, title, sub=''):
    p.draw_rect((x,y,x+w,y+h), color=INK, fill=(0.97,0.98,0.98), width=2)
    text(p,x+15,y+30,title,20)
    if sub: text(p,x+15,y+55,sub,16,MUTED)

def wire(p, net, *pts):
    color = POWER if net in ('5V_LED','5V_MCU','VIN_FUSED') else (MUTED if net=='GND' else SIGNAL)
    line(p,pts,color,2.5)
    wires.append({'page':p.number+1,'net':net,'points':pts})

def dot(p, x, y):
    p.draw_circle((x,y),3.3,color=INK,fill=INK)

def label(p, x, y, net):
    text(p,x,y-10,net,17,POWER if net.startswith(('5V','VIN')) else SIGNAL)

def pin(p, ref, pins, net, x, y, dx=8, dy=-8, extra=''):
    pins = [str(a) for a in pins]
    for num in pins:
        assert expected[ref,num] == net, (ref,num,net)
        assert not any(d['ref']==ref and d['pin']==num for d in drawn)
        drawn.append({'ref':ref,'pin':num,'net':net,'page':p.number+1,'x':x,'y':y})
    text(p,x+dx,y+dy,','.join(pins)+(' '+extra if extra else ''),14,MUTED)
    p.draw_circle((x,y),3,color=INK,fill=(1,1,1))

def resistor(p, ref, value, x, y, vertical, first, second, n1, n2):
    if vertical:
        p.draw_rect((x-10,y,x+10,y+65),color=INK,width=2)
        a,b=(x,y),(x,y+65)
        text(p,x+23,y+27,ref,19); text(p,x+23,y+53,value,16)
        pin(p,ref,[first],n1,*a,dx=-22);pin(p,ref,[second],n2,*b,dx=-22,dy=19)
    else:
        p.draw_rect((x,y-10,x+90,y+10),color=INK,width=2)
        a,b=(x,y),(x+90,y)
        text(p,x,y-47,ref,19); text(p,x,y-22,value,16)
        pin(p,ref,[first],n1,*a,dx=-18,dy=30);pin(p,ref,[second],n2,*b,dy=30)
    return a,b

def capacitor(p, ref, value, x, y, polarized=True):
    line(p,[(x-20,y),(x+20,y)])
    line(p,[(x-20,y+16),(x+20,y+16)])
    pin(p,ref,[1],'5V_LED',x,y,dx=-33)
    pin(p,ref,[2],'GND',x,y+16,dx=-33,dy=31)
    if polarized: text(p,x+26,y-5,'+',18,POWER)
    text(p,x+20,y+64,ref,18)
    text(p,x+20,y+90,value,14)

# Sheet 1: reverse-polarity and reservoir network.
p=page('供电与反接保护','从已保存的原生网表逐脚核对；相同网络名代表电气连接，框内为功能说明。')
box(p,95,220,155,185,'J1  XT30','C431092')
pin(p,'J1',[2],'VIN_FUSED',250,280,dx=-70,dy=35,extra='+')
pin(p,'J1',[1],'GND',250,365,dx=-70,extra='−')
pin(p,'J1',[3,4],None,150,405,dy=28,extra='NC')
text(p,95,468,'3/4 辅助脚独立悬空',16,MUTED)
text(p,95,495,'非正负电源端',16,MUTED)
wire(p,'VIN_FUSED',(250,280),(520,280));label(p,285,270,'VIN_FUSED')
box(p,520,220,240,125,'Q1  CJQ16P03','PMOS 反接保护')
pin(p,'Q1',[5,6,7,8],'VIN_FUSED',520,280,dx=13,dy=44,extra='D')
pin(p,'Q1',[1,2,3],'5V_LED',760,280,dx=-105,dy=44,extra='S')
pin(p,'Q1',[4],'PMOS_GATE',625,345,dx=12,dy=25,extra='G')
wire(p,'5V_LED',(760,280),(1460,280));label(p,1280,265,'5V_LED')
wire(p,'PMOS_GATE',(625,345),(625,435),(1025,435));label(p,650,430,'PMOS_GATE')
resistor(p,'R2','1M',850,335,True,2,1,'5V_LED','PMOS_GATE')
wire(p,'5V_LED',(850,280),(850,335));dot(p,850,280)
wire(p,'PMOS_GATE',(850,400),(850,435));dot(p,850,435)
# Explicit anode/cathode representation avoids ambiguous zener symbol polarity.
box(p,980,325,95,85,'D145','12V ZD')
pin(p,'D145',[1],'5V_LED',1025,325,dx=58,dy=9,extra='K')
pin(p,'D145',[2],'PMOS_GATE',1025,410,dx=58,dy=0,extra='A')
wire(p,'5V_LED',(1025,280),(1025,325));dot(p,1025,280)
wire(p,'PMOS_GATE',(1025,410),(1025,435))
resistor(p,'R1','1k',625,495,True,1,2,'PMOS_GATE','GND')
wire(p,'PMOS_GATE',(625,435),(625,495));dot(p,625,435)
wire(p,'GND',(625,560),(625,690))
wire(p,'GND',(250,365),(310,365),(310,690),(1500,690));label(p,1440,680,'GND')
for i,x in enumerate(() if V02 else (1130,1230,1330,1430),1):
    capacitor(p,f'C{i}','470µF/10V',x,515)
    wire(p,'5V_LED',(x,280),(x,515));dot(p,x,280)
    wire(p,'GND',(x,531),(x,690));dot(p,x,690)
if V02:
    box(p,1110,465,375,130,'8 × 270µF / 10V PXF','C1–C4、C6–C9；并联接法见第3页')
    wire(p,'5V_LED',(1295,280),(1295,465));dot(p,1295,280)
    wire(p,'GND',(1295,595),(1295,690));dot(p,1295,690)
dot(p,625,690)
wire(p,'5V_LED',(800,280),(800,205),(1020,205));dot(p,800,280)
resistor(p,'F2','MF-MSMF050-2',1020,205,False,1,2,'5V_LED','5V_MCU')
wire(p,'5V_MCU',(1110,205),(1450,205));label(p,1280,200,'5V_MCU')
text(p,770,730,'F2数据表：23°C保持0.5A；40°C为0.44A。',17,MUTED)
text(p,770,757,'实际PCB温度待测；PTC不会把电流精确限制在0.5A。',17,MUTED)
text(p,95,570,'Q1 仅防极性接反。',18)
text(p,95,600,'不能阻断输出倒灌。',18)
text(p,95,630,'D145 不是5V过压保护。',18,WARN)
text(p,60,794,'板外候选供电链（不在本PCB上）',21)
box(p,60,817,260,78,'封闭式稳压5V电源','SDM50-5-U-P5 · 5V/9A' if V02 else '≥8A候选；真实型号待定')
box(p,410,817,295,78,'7.5A MINI保险 + 保险座','靠近电源；额定值不等于快断')
box(p,805,817,280,78,'工厂预装输入线束','16AWG铜线候选；校核总压降')
box(p,1190,817,330,78,'对插J1 → VIN_FUSED / GND','极性、配对型号和总长待冻结')
for a,b in ((320,410),(705,805),(1085,1190)):
    line(p,[(a,855),(b,855)],MUTED);line(p,[(b-9,849),(b,855),(b-9,861)],MUTED)
text(p,60,946,'5.704A是规划工况：LED 144×36mA + 控制支路0.5A + 缓冲区0.02A；尚非保证最大电流。',18,WARN)

# Sheet 2: data isolation. The AHCT and FET have explicit functional pin labels.
p=page('电平转换与上电隔离','缓冲器供电须满足AHCT的4.5–5.5V推荐范围；软件限流与OE控制不切断灯珠电源。')
box(p,95,195,155,270,'J2  JST XH','C594232')
for num,net,y in [(4,'5V_MCU',260),(2,'DATA_3V3',330),(1,'GND',390),(3,'ENABLE_3V3',435)]:
    pin(p,'J2',[num],net,250,y,dx=-30,dy=-9)
wire(p,'5V_MCU',(250,260),(380,260));label(p,280,250,'5V_MCU')
wire(p,'GND',(250,390),(305,390),(305,510),(345,510));label(p,290,545,'GND')
box(p,680,260,190,190,'U1','74AHCT1G125GW')
pin(p,'U1',[2],'DATA_3V3',680,330,dx=12,dy=25,extra='A')
pin(p,'U1',[4],'DATA_BUFFERED',870,330,dx=-55,dy=25,extra='Y')
pin(p,'U1',[5],'5V_LED',775,260,dx=12,extra='VCC')
pin(p,'U1',[3],'GND',775,450,dx=10,dy=-10,extra='GND')
pin(p,'U1',[1],'DATA_OE_N',680,410,dx=12,dy=12,extra='/OE')
wire(p,'DATA_3V3',(250,330),(680,330));label(p,415,320,'DATA_3V3')
wire(p,'5V_LED',(775,260),(775,175),(975,175));label(p,800,168,'5V_LED')
wire(p,'GND',(775,450),(775,485),(825,485));label(p,800,515,'GND')
capacitor(p,'C5','100nF',975,220,False)
wire(p,'5V_LED',(975,175),(975,220))
wire(p,'GND',(975,236),(975,260),(1030,260));label(p,1010,245,'GND')
wire(p,'DATA_BUFFERED',(870,330),(1060,330));label(p,881,380,'DATA_BUFFERED')
resistor(p,'R3','330Ω',1060,330,False,1,2,'DATA_BUFFERED','LED_DATA_IN')
wire(p,'LED_DATA_IN',(1150,330),(1480,330));label(p,1235,320,'LED_DATA_IN')
text(p,1230,375,'至原生灯链的首灯DIN',17)
resistor(p,'R4','100k',450,455,True,1,2,'DATA_3V3','GND')
wire(p,'DATA_3V3',(450,330),(450,455));dot(p,450,330)
wire(p,'GND',(450,520),(450,600),(515,600));label(p,475,590,'GND')
resistor(p,'R5','100k',1370,455,True,1,2,'LED_DATA_IN','GND')
wire(p,'LED_DATA_IN',(1370,330),(1370,455));dot(p,1370,330)
wire(p,'GND',(1370,520),(1370,605),(1450,605));label(p,1405,595,'GND')
wire(p,'DATA_OE_N',(680,410),(630,410),(630,560),(1060,560))
label(p,775,550,'DATA_OE_N')
resistor(p,'R6','100k',1060,435,True,2,1,'5V_LED','DATA_OE_N')
wire(p,'5V_LED',(1060,435),(1060,406),(1150,406));label(p,1100,398,'5V_LED')
wire(p,'DATA_OE_N',(1060,500),(1060,560))
box(p,605,655,185,120,'Q2  2N7002','NMOS使能下拉')
pin(p,'Q2',[3],'DATA_OE_N',695,655,dx=12,extra='D')
pin(p,'Q2',[1],'ENABLE_3V3',605,735,dx=12,dy=23,extra='G')
pin(p,'Q2',[2],'GND',695,775,dx=12,dy=-10,extra='S')
wire(p,'DATA_OE_N',(695,560),(695,655));dot(p,695,560)
wire(p,'ENABLE_3V3',(250,435),(375,435),(375,735),(605,735));label(p,385,713,'ENABLE_3V3')
resistor(p,'R7','100k',470,790,True,1,2,'ENABLE_3V3','GND')
wire(p,'ENABLE_3V3',(470,735),(470,790));dot(p,470,735)
wire(p,'GND',(470,855),(470,900),(695,900),(695,775));label(p,605,893,'GND')
text(p,885,685,'默认：R7下拉 → Q2关断 → R6上拉/OE → 输出高阻。',17)
text(p,885,725,'使能：ENABLE_3V3拉高 → Q2导通 → /OE拉低。',17)
text(p,885,765,'R4与R5将输入和首灯DIN置低。',17)
text(p,885,822,'注意：故障时隔离数据，灯珠可能保留最后一帧。',17,WARN)
text(p,885,860,'J2是PCB针序；不代表已核验开发板接线位置。',17,WARN)
text(p,60,951,'开发板USB 5V与外置5V不能直接并联；确认到货板电源路径后才发布装机接线。',18,WARN)

if V02:
    p=page('四区域并联储能电容','Chemi-Con APXF100ARA271MF61G；每区2颗，总标称2160µF；条纹为负极。')
    wire(p,'5V_LED',(100,285),(1500,285));label(p,100,260,'5V_LED')
    wire(p,'GND',(100,690),(1500,690));label(p,100,730,'GND')
    for i,ref in enumerate(['C1','C6','C2','C7','C3','C8','C4','C9']):
        x=155+i*180
        capacitor(p,ref,'270µF / 10V',x,480)
        wire(p,'5V_LED',(x,285),(x,480));dot(p,x,285)
        wire(p,'GND',(x,496),(x,690));dot(p,x,690)
    text(p,90,825,'原生焊盘：1 = 正极 / 5V_LED；2 = 负极 / GND。实物黑色条纹朝外缘。',22)
    text(p,90,869,'容量公差 ±20%；总容量和理想并联ESR不代表浪涌、动态压降或实测纹波。',20,MUTED)
    text(p,90,914,'C5 是 U1 旁的100nF去耦电容，见第2页；不属于此储能电容组。',20,MUTED)
assert set((x['ref'],x['pin']) for x in drawn)==set(expected)
def on_segment(x,y,a,b):
    cross=(x-a[0])*(b[1]-a[1])-(y-a[1])*(b[0]-a[0])
    return abs(cross)<1e-6 and min(a[0],b[0])-1e-6<=x<=max(a[0],b[0])+1e-6 and min(a[1],b[1])-1e-6<=y<=max(a[1],b[1])+1e-6
for pin_record in drawn:
    if pin_record['net'] is None: continue
    matches=[w for w in wires if w['page']==pin_record['page'] and any(on_segment(pin_record['x'],pin_record['y'],a,b) for a,b in zip(w['points'],w['points'][1:]))]
    assert matches and all(w['net']==pin_record['net'] for w in matches),pin_record
doc.subset_fonts()
pdf=OUT/'PHYLLO-power-and-data-REVIEW.pdf'
doc.save(pdf,garbage=4,deflate=True)
doc.close()
readback=fitz.open(pdf)
assert len(readback)==(3 if V02 else 2)
for i,p in enumerate(readback,1):
    (OUT/f'circuit-{i}.svg').write_text(p.get_svg_image(text_as_path=True),encoding='utf-8')
    p.get_pixmap(matrix=fitz.Matrix(1,1),alpha=False).save(OUT/f'circuit-{i}.png')
    extracted=p.get_text()
    for ref in sorted(set(d['ref'] for d in drawn if d['page']==i)):
        assert ref in extracted,ref
    assert 'PHYLLO' in extracted
assert sha(PCB)==EXPECTED
audit={'status':'supplementary_diagram_pin_and_net_audit_pass_NOT_manufacturing_release',
       'board_sha256_before_after':EXPECTED,'intent_sha256':sha(intent_file),'native_netlist_sha256':sha(netlist_file),
       'components':len(intent['components']),'pins':len(drawn),'connected_pins':sum(d['net'] is not None for d in drawn),
       'nc_pins':sum(d['net'] is None for d in drawn),'pages':len(readback),
       'checks':['complete support-component pin coverage','every manually assigned pin net equals saved native netlist and design intent','every connected drawn pin touches only its assigned network line','saved PDF reopened and all component reference text present','native PCB hash unchanged'],
       'limits':['Not a replacement native schematic or new ERC run','No general automatic wire-crossing/connectivity proof; visual review separately recorded','External source/fuse/harness are functional candidates, not exact purchased components','Diagrams are not physical connector orientation views'],
       'drawn_pins':drawn,'wire_segments':wires,
       'outputs':[{ 'path':str(x.relative_to(P)).replace('\\','/'),'sha256':sha(x)} for x in sorted(OUT.iterdir()) if x.is_file()]}
(V/('prototype-v02-readable-circuit-audit.json' if V02 else 'readable-circuit-audit.json')).write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in audit.items() if k not in ('drawn_pins','wire_segments','outputs')},ensure_ascii=False))
