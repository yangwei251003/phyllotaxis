"""Inspect actual extrusion paths and render local slice sections (not a print simulation)."""
from pathlib import Path
from collections import defaultdict
import json, re, hashlib, math
import numpy as np
import trimesh
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import shapely
from shapely.geometry import Polygon, GeometryCollection

P=Path(__file__).resolve().parents[1];D=P/'verification/slicing'
PARTS={'base':1,'bezel':1,'carrier':1,'retainer':2,'microphone-holder':1}
NUM=re.compile(r'([XYZEF])([-+]?(?:\d+(?:\.\d*)?|\.\d+))')

def paths(path):
    pos={'X':0.,'Y':0.,'Z':0.,'E':0.}; absolute=True; e_absolute=True
    typ='Custom'; layerz=0.; width=.4; layers=defaultdict(list); lengths=defaultdict(float); meta={}; arcs=0
    for line in path.open(encoding='utf-8'):
        if line.startswith(';TYPE:'):typ=line[6:].strip();continue
        if line.startswith(';Z:'):layerz=float(line[3:]);continue
        if line.startswith(';WIDTH:'):width=float(line[7:]);continue
        if line.startswith('; ') and ' = ' in line:
            k,v=line[2:].rstrip('\r\n').split(' = ',1);meta[k]=v
        cmd=line.split(';',1)[0].strip()
        if not cmd:continue
        op=cmd.split()[0];t={k:float(v) for k,v in NUM.findall(cmd)}
        if op=='G90':absolute=e_absolute=True
        elif op=='G91':absolute=e_absolute=False
        elif op=='M82':e_absolute=True
        elif op=='M83':e_absolute=False
        elif op=='G92':
            for k in 'XYZE':
                if k in t:pos[k]=t[k]
        elif op in ('G0','G1','G2','G3'):
            old=pos.copy()
            for k in 'XYZ':
                if k in t:pos[k]=t[k] if absolute else pos[k]+t[k]
            if 'E' in t:pos['E']=t['E'] if e_absolute else pos['E']+t['E']
            de=pos['E']-old['E'];xy=math.hypot(pos['X']-old['X'],pos['Y']-old['Y'])
            if de>0 and xy>1e-6 and typ!='Custom' and layerz>0:
                if op in ('G2','G3'):arcs+=1
                layers[round(layerz,6)].append((old['X'],old['Y'],pos['X'],pos['Y'],typ,width))
                lengths[typ]+=de
    assert arcs==0,'Do not render arcs as straight lines'
    return layers,lengths,meta

def time_seconds(s):
    return sum(int(v)*{'h':3600,'m':60,'s':1}[unit] for v,unit in re.findall(r'(\d+)([hms])',s))

def placement(layers,mesh):
    outer=np.array([p[:4] for paths_ in layers.values() for p in paths_ if p[4]=='Outer wall'])
    pathcenter=(np.minimum(outer[:,:2].min(0),outer[:,2:].min(0))+np.maximum(outer[:,:2].max(0),outer[:,2:].max(0)))/2
    modelcenter=mesh.bounds[:,:2].mean(0)
    # Orca's default arrangement may rotate models. Determine its orthogonal
    # placement against asymmetric STL sections, rather than assuming no rotation.
    scores=defaultdict(list);outside=defaultdict(int)
    zvals=sorted(z for z in layers if any(p[4]=='Outer wall' for p in layers[z]))
    sampled=[zvals[i] for i in np.unique(np.linspace(1,len(zvals)-2,14,dtype=int))]
    for z in sampled:
        sec=mesh.section(plane_origin=[0,0,max(.001,z-.1)],plane_normal=[0,0,1])
        if sec is None:continue
        shape=GeometryCollection()
        for v in sec.discrete:
            poly=Polygon(v[:,:2])
            if poly.is_valid:shape=shape.symmetric_difference(poly)
        if shape.is_empty:continue
        pts=np.array([[(p[0]+p[2])/2,(p[1]+p[3])/2,p[5]] for p in layers[z] if p[4]=='Outer wall'])
        if not len(pts):continue
        pts=pts[::max(1,len(pts)//1000)]
        for angle in (0,90,180,270):
            a=math.radians(angle);R=np.array([[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]])
            modelpts=(pts[:,:2]-pathcenter)@R+modelcenter
            sp=shapely.points(modelpts);dist=shapely.distance(sp,shape.boundary);inside=shapely.contains(shape,sp)
            err=np.abs(dist-pts[:,2]/2)+np.where(inside,0,2*dist)
            scores[angle].extend(err.tolist());outside[angle]+=int((~inside).sum())
    review={str(a):{'mean_boundary_offset_residual_mm':float(np.mean(s)), 'outside_midpoints':outside[a], 'sample_count':len(s)} for a,s in scores.items()}
    angle=min(scores,key=lambda a:np.mean(scores[a]));a=math.radians(angle)
    R=np.array([[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]])
    return pathcenter,modelcenter,R,{'model_to_plate_rotation_deg':angle,'plate_path_center_mm':pathcenter.tolist(),'model_bbox_center_mm':modelcenter.tolist(),'candidate_section_scores':review,
        'basis':'Orthogonal 0/90/180/270-degree candidates; outer wall midpoint boundary-offset residual against 14 STL sections. This diagnoses arrangement and supports visualization, not full geometry verification.'}

def render(name,layers,mesh,targets,place,zoom=None,filename=None):
    pathcenter,modelcenter,R,place_info=place
    fig,axes=plt.subplots(1,len(targets),figsize=(5*len(targets),5),squeeze=False)
    selected=[]
    for ax,target in zip(axes[0],targets):
        z=min(layers,key=lambda v:abs(v-target)); selected.append(z)
        grouped=defaultdict(list)
        shown=list(layers[z])
        # Supports can use independent layer Z values. Include their most
        # recent <=0.3mm slab, labeled explicitly, rather than hiding them.
        for sz in layers:
            if z-.3 < sz < z-1e-6:
                shown.extend(p for p in layers[sz] if 'Support' in p[4])
        for x1,y1,x2,y2,typ,w in shown:
            grouped['Support' if 'Support' in typ else ('Wall' if 'wall' in typ else 'Other')].append((np.array([[x1,y1],[x2,y2]])-pathcenter)@R+modelcenter)
        for group,color in [('Support','#df7627'),('Other','#99b1a6'),('Wall','#1e685c')]:
            if grouped[group]:ax.add_collection(LineCollection(grouped[group],colors=color,linewidths=.75,label=group))
        # Slice half a layer below extrusion Z to avoid coincident topological planes.
        sec=mesh.section(plane_origin=[0,0,max(.001,z-.1)],plane_normal=[0,0,1])
        if sec is not None:
            ax.add_collection(LineCollection([v[:,:2] for v in sec.discrete],colors='#222222',linewidths=.45,linestyles='dotted',label='STL section'))
        if zoom:
            ax.set_xlim(*zoom[0]);ax.set_ylim(*zoom[1])
        else:
            ax.set_xlim(mesh.bounds[0,0]-4,mesh.bounds[1,0]+4);ax.set_ylim(mesh.bounds[0,1]-4,mesh.bounds[1,1]+4)
        ax.set_aspect('equal');ax.set_title(f'{name}: body Z {z:.3f} mm\nSupport paths in previous 0.3 mm');ax.set_xlabel('Model X [mm]');ax.set_ylabel('Model Y [mm]');ax.grid(alpha=.15)
    axes[0,0].legend(fontsize=8,loc='best')
    fig.suptitle('OrcaSlicer 2.4.2 actual paths — review only, not physical print verification',fontsize=11)
    fig.tight_layout();out=D/(filename or name+'-layers.png');fig.savefig(out,dpi=180);plt.close(fig)
    return {'image':out.relative_to(P).as_posix(),'selected_z_mm':selected,'placement':place_info,
            'alignment_basis':'Recovered orthogonal arrangement; STL section at Z-0.1mm. Orange supports include Z-0.3 < support Z <= body Z to show independent support layers. Preview overlay only, not whole-surface metrology.'}

results=[];total_g=0.;total_s=0;previews=[]
for name,qty in PARTS.items():
    path=D/'final'/name/f'{name}-REVIEW-ONLY.gcode';layers,lengths,meta=paths(path)
    mesh=trimesh.load(P/'mechanical'/f'{name}.stl',force='mesh')
    gram=float(meta['filament used [g]']);seconds=time_seconds(meta['estimated printing time (normal mode)'])
    total_g+=qty*gram;total_s+=qty*seconds
    assert meta['curr_bed_type']=='High Temp Plate'
    code=path.read_text(encoding='utf-8')
    assert 'M140 S80' in code and 'M190 S80' in code
    mass={k:round(e*math.pi*(1.75/2)**2*1.27/1000,4) for k,e in lengths.items()}
    results.append({'part':name,'qty':qty,'STL_sha256':hashlib.sha256((P/'mechanical'/f'{name}.stl').read_bytes()).hexdigest(),
                    'gcode_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'slicer_estimated_g_each':gram,'slicer_estimated_seconds_each':seconds,
                    'actual_layer_z_count':len(layers),'extruding_path_filament_mass_by_role_g':mass,
                    'estimated_first_layer_time':meta.get('estimated first layer printing time (normal mode)'),
                    'source_mesh_bounds_mm':mesh.bounds.tolist(),
                    'bed_gcode_readback_C':80,'profile_readback':{k:meta[k] for k in ['curr_bed_type','layer_height','wall_loops','sparse_infill_density','enable_support','support_type','nozzle_temperature']}})
    if name in ('base','microphone-holder'):
        place=placement(layers,mesh)
        print(json.dumps({'part':name,'placement':place[3]},ensure_ascii=False),flush=True)
    if name=='base':
        previews.append(render(name,layers,mesh,[11,12.8,18],place,zoom=((38,53),(80,94)),filename='base-vent-detail.png'))
        previews.append(render(name,layers,mesh,[8,18,26],place,filename='base-support-layers.png'))
    elif name=='microphone-holder':previews.append(render(name,layers,mesh,[5,14.4,19.6],place,filename='microphone-holder-layers.png'))
report={'status':'OFFLINE_SLICING_REVIEW_NOT_FOR_PRINTING','parts':results,'total_g_for_required_quantities':round(total_g,2),
        'sum_of_individual_slicer_time_seconds':total_s,'previews':previews,
        'limits':['Slicer estimates are not supplier prices or measured runtime.',
                  'Two retainers required. Total time sums six individual jobs, not an optimized combined plate.',
                  'G-code role mass counts positive E on XY extrusion moves only; excludes stationary recovery/purge and is not identical to slicer total.',
                  '255C/80C from an installed MK4 PETG profile; actual supplier machine and material remain unknown.',
                  'Static validator reports retained native MK4 commands it does not interpret; this is not firmware or collision simulation.',
                  'Support detachment, warping, hole tolerances and structural strength require supplier review/physical sample.'],
        'software_reference':'https://github.com/OrcaSlicer/OrcaSlicer/wiki/cli_actions'}
(D/'slice-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'parts':len(results),'total_g':round(total_g,2),'sum_individual_seconds':total_s,'previews':previews},ensure_ascii=False))
