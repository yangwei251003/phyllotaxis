"""Engineering inspection plot, based on native polygons, tracks and planned fanout."""
from pathlib import Path
import json,sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon,Circle,PathPatch
from matplotlib.path import Path as MPath
P=Path(__file__).resolve().parents[1]
src=Path(sys.argv[1]) if len(sys.argv)>1 else P/'verification/copper-geometry.json'
d=json.loads(src.read_text());plan=json.loads((P/'hardware/power-copper-plan.json').read_text())
fig,ax=plt.subplots(figsize=(15,10));colors={'GND':'#247654','5V_LED':'#d39514','VIN_FUSED':'#cc2244','5V_MCU':'#7435c9'}
for z in d['zones']:
    if z['layer']!=0:continue
    for p in z['filled']:
        paths=[]
        for ring in [p['outer'],*p['holes']]:
            paths.append(MPath(ring+[ring[0]],[MPath.MOVETO]+[MPath.LINETO]*(len(ring)-1)+[MPath.CLOSEPOLY]))
        ax.add_patch(PathPatch(MPath.make_compound_path(*paths),color=colors.get(z['net'],'grey'),alpha=.22,lw=0))
for t in d['tracks']:
    c=colors.get(t['net'],'#e77979' if 0 in t['layers'] else '#5791cc')
    if t['via']:ax.add_patch(Circle(t['a'],t['width']/2,color=c))
    else:ax.plot([t['a'][0],t['b'][0]],[t['a'][1],t['b'][1]],color=c,linewidth=t['width']*2)
for p in d['pads']:
    for v in p['polygons'].get('0',[]):ax.add_patch(Polygon(v['outer'],facecolor=colors.get(p['net'],'#b9b9b9'),edgecolor='black',linewidth=.4))
    if p['xy'][1]>170:ax.text(*p['xy'],p['ref']+'-'+p['num'],fontsize=6,ha='center')
if not d['zones']:
    for f in plan['fanouts']:
        ax.add_patch(Circle(f['via'],.3,color='#247654'))
        ax.plot([f['from'][0],f['via'][0]],[f['from'][1],f['via'][1]],color='#247654',lw=.8)
ax.add_patch(Circle((100,100),90,fill=False,edgecolor='black'))
ax.set(xlim=(66,132),ylim=(188,166),aspect='equal',xlabel='Native board X / mm',ylabel='Native board Y / mm',title='Power entry inspection — front copper (bottom signals shown blue)')
ax.grid(alpha=.15);fig.tight_layout();dst=P/'verification/power-entry-inspection.png';fig.savefig(dst,dpi=160);print(dst)
