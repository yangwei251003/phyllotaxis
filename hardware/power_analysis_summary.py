"""Analytic calibration, supplemental bounds, and readable DC plots."""
from pathlib import Path
import json,hashlib,math
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parents[1];V=P/'verification'
r=json.loads((V/'power-drop-estimate.json').read_text());g=json.loads((V/'power-copper-geometry.json').read_text())
assert r['board_sha256']==g['sha256']==hashlib.sha256((P/'hardware/kicad-check/phyllo-copper-review.kicad_pcb').read_bytes()).hexdigest()
# Known rectangular resistor sheet: 20 columns, 10 equal current rows,
# 19 length increments and 10 width increments. Exact R = Rs * 19 / 10.
idx=np.arange(200).reshape(10,20);a=np.r_[idx[:,:-1].ravel(),idx[:-1,:].ravel()];b=np.r_[idx[:,1:].ravel(),idx[1:,:].ravel()]
rs=1.724e-8/70e-6;deg=np.bincount(np.r_[a,b],minlength=200)
A=coo_matrix((np.r_[deg/rs,np.full(2*len(a),-1/rs)],(np.r_[np.arange(200),a,b],np.r_[np.arange(200),b,a])),shape=(200,200)).tocsr()
fixed=np.zeros(200,bool);fixed[idx[:,0]]=True;I=np.zeros(200);I[idx[:,-1]]=.1;v=np.zeros(200);v[~fixed]=spsolve(A[~fixed][:,~fixed],I[~fixed])
expected=rs*19/10;error=float(max(abs(v[idx[:,-1]]-expected)));assert error<1e-12
ass=r['assumptions'];factor=1+ass['temperature_coefficient_per_C']*(85-20);current=ass['input_total_a']
via_r=ass['rho_ohm_m_at20C']*.0016/(math.pi*.0003*.000018)
plan=json.loads((P/'hardware/power-copper-plan.json').read_text())
led_fanouts=[f for f in plan['fanouts'] if f['ref'].startswith('D') and int(f['ref'][1:])<=144]
max_stub=max(math.dist(f['from'],f['via'])/f['width'] for f in led_fanouts)*rs
analytic={'board_sha256':r['board_sha256'],'rectangular_sheet_reference':{'expected_ohm':expected,'max_abs_error_ohm':error,'passed':True},
 'via_barrel_ohm_at20C_18um_wall':via_r,'max_LED_ground_stub_bound_ohm_at20C':max_stub,
 'LED_ground_stub_plus_via_bound_mv_at20C':.036*(via_r+max_stub)*1000,
 'Q1_10mohm_drop_mv':current*.010*1000,'Q1_10mohm_loss_w':current**2*.010,
 'Q1_15mohm_drop_mv':current*.015*1000,'Q1_15mohm_loss_w':current**2*.015,
 'copper_20_to85C_resistance_factor':factor,
 'copper_path_bound_mv_at85C':factor*(r['max_led_plane_loop_drop_mv_20C']+r['VIN_port_drop_mv_20C']+.036*(via_r+max_stub)*1000),
 'note':'Q1 10mohm uses manufacturer maximum at25C/VGS=-4.5V. 15mohm is an engineering scenario/measurement limit, NOT a guaranteed hot maximum. Copper temperature assumed uniform; this is not predicted temperature.'}
(V/'power-analytic-checks.json').write_text(json.dumps(analytic,indent=2),encoding='utf-8')
fig,axes=plt.subplots(1,2,figsize=(13,6.5),layout='constrained')
for ax,net,title in zip(axes,['5V_LED','GND'],['5 V plane drop from Q1 source','Ground plane rise above input return']):
    mesh=np.load(V/f'power-grid-{net}.npz');a=ax.scatter(mesh['x'],mesh['y'],c=mesh['v']*1000,s=.30,marker='s',cmap='inferno',rasterized=True)
    ax.set(title=title,xlim=(10,190),ylim=(190,10),aspect='equal',xlabel='PCB X / mm',ylabel='PCB Y / mm');fig.colorbar(a,ax=ax,shrink=.8,label='mV at nominal 70 um copper, 20 C')
fig.suptitle('PHYLLO | DC copper estimate, 5.704 A total\n0.25 mm grid; not a thermal simulation or measured result',fontsize=14)
fig.savefig(V/'power-drop-map.png',dpi=160)
# Fix the receipt's layer labels using the numeric native layer evidence.
receipt=json.loads((V/'power-copper-import.json').read_text())
for z in receipt['zones']:
    numeric=next(n['layer'] for n in g['zones'] if n['net']==z['net']);z['layer']={0:'F.Cu',2:'B.Cu'}[numeric]
receipt['layer_name_readback_note']='Use BOARD.GetLayerName(ZONE.GetLayer()); default no-argument ZONE.GetLayerName() incorrectly reported F.Cu for B.Cu in installed SWIG.'
(V/'power-copper-import.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(analytic))
