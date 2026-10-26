"""DC resistor-grid estimate from actual filled copper, not a thermal simulation.

Grid edges sample copper every h/8; geometry is separately checked by native DRC.
Two mesh pitches provide a convergence check. Contacts are ideal/equipotential.
"""
from pathlib import Path
import json,math,time,sys
import numpy as np
from shapely.geometry import Polygon,Point,LineString
from shapely.ops import unary_union
from shapely import intersects_xy,make_valid
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.sparse.linalg import spsolve
P=Path(__file__).resolve().parents[1]
d=json.loads((P/'verification/power-copper-geometry.json').read_text());plan=json.loads((P/'hardware/power-copper-plan.json').read_text())
pads={(p['ref'],p['num']):p for p in d['pads']}
def geom(poly):return unary_union([make_valid(Polygon(p['outer'],p['holes'])) for p in poly])
def copper(net,layer):
    gs=[geom(z['filled']) for z in d['zones'] if z['net']==net and z['layer']==layer]
    gs += [geom(p['polygons'][str(layer)]) for p in d['pads'] if p['net']==net and layer in p['layers']]
    for t in d['tracks']:
        if t['net']!=net or layer not in t['layers']:continue
        gs.append(Point(t['a']).buffer(t['width']/2,quad_segs=16) if t['via'] else LineString([t['a'],t['b']]).buffer(t['width']/2,quad_segs=16))
    holes=[Point(p['xy']).buffer(p['drill'][0]/2,quad_segs=16) for p in d['pads'] if p['drill'][0]>0]
    holes += [Point(t['a']).buffer(t['drill']/2,quad_segs=16) for t in d['tracks'] if t['via']]
    return unary_union(gs).difference(unary_union(holes))
def contacts(ref,num,layer):return geom(pads[(ref,num)]['polygons'][str(layer)])
def solve(net,layer,h,source_shapes,loads,sink_shapes=None,terminal_amps=None):
    started=time.time();g=copper(net,layer);x0,y0,x1,y1=g.bounds
    xs=np.arange(math.floor(x0/h)*h+h/2,x1,h);ys=np.arange(math.floor(y0/h)*h+h/2,y1,h)
    xx,yy=np.meshgrid(xs,ys);mask=intersects_xy(g,xx,yy);ids=np.full(mask.shape,-1,np.int32);ids[mask]=np.arange(mask.sum());x=xx[mask];y=yy[mask];n=len(x)
    aa=[];bb=[]
    for dy,dx in [(0,1),(1,0)]:
        left=mask[:mask.shape[0]-dy or None,:mask.shape[1]-dx or None];right=mask[dy:,dx:]
        ok=left&right;iy,ix=np.where(ok);a=ids[iy,ix];b=ids[iy+dy,ix+dx]
        valid=np.ones(len(a),bool)
        for q in np.arange(1,8)/8:valid &= intersects_xy(g,x[a]*(1-q)+x[b]*q,y[a]*(1-q)+y[b]*q)
        aa.append(a[valid]);bb.append(b[valid])
    a=np.concatenate(aa);b=np.concatenate(bb)
    adj=coo_matrix((np.ones(len(a)*2),(np.r_[a,b],np.r_[b,a])),shape=(n,n)).tocsr()
    comps,labels=connected_components(adj,directed=False)
    source=np.zeros(n,bool)
    for s in source_shapes:source |= intersects_xy(s,x,y)
    assert source.any(),(net,h,'Source contact absent')
    live=np.isin(labels,np.unique(labels[source]));source|=~live
    # Sheet resistance at 20 C: rho=1.724e-8 ohm m, nominal finished copper=70 um.
    sheet=1.724e-8/70e-6;cond=1/sheet
    degree=np.bincount(np.r_[a,b],minlength=n);A=coo_matrix((np.r_[degree*cond,np.full(len(a)*2,-cond)],
      (np.r_[np.arange(n),a,b],np.r_[np.arange(n),b,a])),shape=(n,n)).tocsr()
    current=np.zeros(n);ports={};port_errors={}
    for name,p,amps in loads:
        distance=(x-p[0])**2+(y-p[1])**2;distance[~live]=np.inf;j=int(np.argmin(distance))
        error=math.sqrt(distance[j]);assert error<.65,(net,name,h,'Load contact too far',error)
        current[j]+=amps;ports[name]=j;port_errors[name]=error
    voltage=np.zeros(n);terminal=np.zeros(n,bool);pad_current={}
    if sink_shapes:
        # Q1 drain pins share one internal electrical node. Impose one volt on
        # ALL copper contact nodes, solve, then scale to requested port current.
        for s in sink_shapes.values():terminal |= intersects_xy(s,x,y)
        assert terminal.any() and not np.any(terminal&source)
        free=~(source|terminal);voltage[terminal]=1
        voltage[free]=spsolve(A[free][:,free],-(A[free][:,terminal]@np.ones(terminal.sum())))
        unit_current=A@voltage;conductance=float(unit_current[terminal].sum());assert conductance>0
        voltage*=terminal_amps/conductance;current[terminal]=(A@voltage)[terminal]
        ports={'Q1_DRAIN_PORT':int(np.flatnonzero(terminal)[0])};port_errors={'Q1_DRAIN_PORT':0}
        for name,s in sink_shapes.items():pad_current[name]=float(current[intersects_xy(s,x,y)].sum())
    else:
        free=~source;voltage[free]=spsolve(A[free][:,free],current[free])
    residual=A@voltage-current
    dissipation=float(np.sum((voltage[a]-voltage[b])**2)*cond)
    result={'net':net,'layer':layer,'pitch_mm':h,'nodes':n,'components':comps,'live_nodes':int(live.sum()),
      'load_a':float(current.sum()),'source_return_a':float(-residual[source].sum()),
      'max_kcl_residual_a':float(np.max(np.abs(residual[free]))),'copper_loss_w':dissipation,
      'contact_discretization_max_mm':max(port_errors.values()),'seconds':time.time()-started,
      'drop_mv':{name:float(voltage[j]*1000) for name,j in ports.items()},
      'equipotential_terminal_pad_current_a':pad_current}
    print(json.dumps({k:v for k,v in result.items() if k!='drop_mv'}),flush=True)
    if h==.25 and net in ['5V_LED','GND']:
        np.savez_compressed(P/f'verification/power-grid-{net}.npz',x=x,y=y,v=voltage)
    return result
vin_only='--vin-only' in sys.argv
results=[r for r in json.loads((P/'verification/power-drop-estimate.json').read_text())['runs'] if r['net']!='VIN_FUSED'] if vin_only else []
for h in [.5,.25]:
    if not vin_only:
        led=[('D'+str(i),pads[('D'+str(i),'1')]['xy'],.036) for i in range(1,145)]
        extra=[('MCU_BRANCH',pads[('F2','1')]['xy'],.5),('BUFFER',pads[('U1','5')]['xy'],.020)]
        results.append(solve('5V_LED',0,h,[contacts('Q1',str(i),0) for i in [1,2,3]],led+extra))
        ground=[(f['ref'],f['via'],.036) for f in plan['fanouts'] if f['ref'].startswith('D') and int(f['ref'][1:])<=144]
        ground += [('MCU_BRANCH',pads[('J2','1')]['xy'],.5),('BUFFER',next(f['via'] for f in plan['fanouts'] if f['ref']=='U1'),.020)]
        results.append(solve('GND',2,h,[contacts('J1','1',2)],ground))
    results.append(solve('VIN_FUSED',0,h,[contacts('J1','2',0)],[],
       {'Q1_'+str(i):contacts('Q1',str(i),0) for i in [5,6,7,8]},5.704))
fine={r['net']:r for r in results if r['pitch_mm']==.25};coarse={r['net']:r for r in results if r['pitch_mm']==.5}
loops={name:fine['5V_LED']['drop_mv'][name]+fine['GND']['drop_mv'][name] for name in fine['5V_LED']['drop_mv'] if name.startswith('D')}
coarse_loops={name:coarse['5V_LED']['drop_mv'][name]+coarse['GND']['drop_mv'][name] for name in loops}
summary={'status':'DC_MESH_ESTIMATE_NOT_HARDWARE_OR_THERMAL_VALIDATION','board_sha256':d['sha256'],
 'assumptions':{'copper_um':70,'rho_ohm_m_at20C':1.724e-8,'temperature_coefficient_per_C':.00393,
 'LED_load_each_a':.036,'LED_total_a':5.184,'controller_branch_a':.5,'buffer_allowance_a':.020,'input_total_a':5.704,
 'vias_finished_hole_mm':.3,'via_wall_um_assumed':18,'board_mm':1.6},
 'limitations':['Five-point uniform grid with edge copper samples; no subcell boundary conductance.',
 'Ideal equipotential contacts; Q1 drain pads form one terminal, current division solved from copper geometry.',
 'Return loads placed at fanout vias; top stubs and via barrels are separate analytic estimates.',
 'Excludes adapter/cable/fuse/connectors/PMOS/PTC/contact resistance and transient switching.',
 'Nominal 2 oz finished copper assumed, not a factory stackup approval. No thermal solver.'],
 'max_led_plane_loop_drop_mv_20C':max(loops.values()),'worst_LED':max(loops,key=loops.get),
 'coarse_max_led_loop_drop_mv_20C':max(coarse_loops.values()),
 'mesh_max_led_loop_difference_mv':max(abs(loops[n]-coarse_loops[n]) for n in loops),
 'VIN_port_drop_mv_20C':fine['VIN_FUSED']['drop_mv']['Q1_DRAIN_PORT'],
 'all_copper_loss_w_20C':sum(r['copper_loss_w'] for r in fine.values()),'runs':results}
(P/'verification/power-drop-estimate.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k not in ['runs','assumptions','limitations']}),flush=True)
