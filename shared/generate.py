"""Export a single candidate geometry for web, PCB placement, mechanical CAD and firmware."""
import csv
import hashlib
import json
import math
from pathlib import Path

P=Path(__file__).resolve().parents[1]
c=json.loads((P/'shared/design.json').read_text(encoding='utf-8'))
points=[]
for i in range(c['led_count']):
    r=c['led_radius_mm']*math.sqrt((i+c['radial_offset'])/c['led_count'])
    a=i*c['golden_angle_rad']
    points.append({'id':i,'designator':f'D{i+1}','x_mm':round(r*math.cos(a),6),'y_mm':round(r*math.sin(a),6),'radius_mm':round(r,6),'angle_rad':a})
holes=[{'x_mm':c['pcb_mount_radius_mm']*math.cos(math.radians(a)),'y_mm':c['pcb_mount_radius_mm']*math.sin(math.radians(a))} for a in c['pcb_mount_angles_deg']]
minimum=min(math.dist((p['x_mm'],p['y_mm']),(q['x_mm'],q['y_mm'])) for i,p in enumerate(points) for q in points[i+1:])
hole_clear=min(math.dist((p['x_mm'],p['y_mm']),(h['x_mm'],h['y_mm']))-math.hypot(*c['led_envelope_mm'][:2])/2-c['hole_diameter_mm']/2 for p in points for h in holes)
assert minimum>math.hypot(*c['led_envelope_mm'][:2])
assert hole_clear>2
assert max(p['radius_mm'] for p in points)+math.hypot(*c['led_envelope_mm'][:2])/2<c['pcb_diameter_mm']/2
result={'config':c,'leds':points,'mount_holes':holes,'checks':{'minimum_center_distance_mm':minimum,'minimum_led_to_mount_hole_edge_mm':hole_clear,'all_led_envelopes_inside_board':True,'status':'geometry_only'}}
(P/'shared/layout.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
(P/'web/design.json').write_text(json.dumps(c,indent=2),encoding='utf-8')
with (P/'shared/led-positions.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=list(points[0]));w.writeheader();w.writerows(points)
print(json.dumps(result['checks'],indent=2))
