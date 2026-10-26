"""Engineering placement preview from checked native records; not an EDA screenshot."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as Patch,Circle
from matplotlib.font_manager import FontProperties
from pathlib import Path
import verify_support_placement as checked

FONT=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
plt.rcParams['font.family']=FONT.get_name()
plt.rcParams['axes.unicode_minus']=False
fig,(full,detail)=plt.subplots(1,2,figsize=(13,7),gridspec_kw={'width_ratios':[1.25,1]})
for ax in (full,detail):
    ax.set_aspect('equal');ax.set_facecolor('#f4f5ef')
    ax.add_patch(Circle((0,0),90,fill=False,color='#173c32',linewidth=1.5))
    for h in checked.layout['mount_holes']:
        ax.add_patch(Circle((h['x_mm'],h['y_mm']),1.7,color='white',ec='#173c32'))
        ax.add_patch(Circle((h['x_mm'],h['y_mm']),3.5,fill=False,ls='--',lw=.5,color='#999'))
    for ref,shape in checked.envelopes.items():
        support=ref in checked.top
        for p in ([shape] if shape.geom_type=='Polygon' else shape.geoms):
            ax.add_patch(Patch(list(p.exterior.coords),facecolor='#c39248' if support else '#4c7e64',edgecolor='#243c31',linewidth=.3,alpha=.8))
        b=checked.comp[ref]
        if support and (ax is detail or ref in ['C1','C2','C3','C4']):
            ax.annotate(ref,(b['x']*.0254,b['y']*.0254),xytext=(0,7),textcoords='offset points',fontsize=7,ha='center')
    ax.set_xlabel('X / mm');ax.set_ylabel('Y / mm');ax.grid(alpha=.12)
full.set(xlim=(-96,96),ylim=(-96,96),title='180 mm 圆板 · 144灯 + 17个顶面支持器件')
detail.set(xlim=(-35,44),ylim=(-92,-66),title='下缘电源与数据电路布局放大')
fig.suptitle('PHYLLO  PCB 布局候选 v0.4',fontsize=17,fontweight='bold')
fig.text(.5,.055,'从离线工程记录绘制；不是嘉立创原生截图。尚未布线/铺铜/DRC，J1/J2背面连接器未落板。',ha='center',fontsize=10,color='#a3422d')
fig.text(.5,.022,'铜焊盘与器件外形的保守包络：最小间距1.093 mm，最小板边距2.164 mm；不等于厂家装配禁布区。',ha='center',fontsize=9)
fig.tight_layout(rect=(0,.09,1,.94))
out=checked.P/'verification'
fig.savefig(out/'pcb-placement-preview.png',dpi=160)
fig.savefig(out/'pcb-placement-preview.pdf')
print('Saved verified-record placement preview')
