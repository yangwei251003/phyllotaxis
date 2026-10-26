"""Spec-driven mechanical checks, not a physical-fit or print approval."""
import json
from pathlib import Path
from build123d import Box, Compound, Pos
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder
from controller import P, CONFIG, SEAT, RETAINER_Z, BOSS_XY, carrier, retainer, controller_assembly, header_reserves, usb_reserve
from parts import base, pcb

OUT = Path(__file__).resolve().parents[1] / 'verification'
root = controller_assembly()
tray, board, negative, positive = root.children
floor = CONFIG['floor_mm']

def overlap(a, b):
    # Operate on the located OCC shapes. build123d's Compound distribution may
    # inspect unlocated children and report false intersections for a moved tree.
    common = BRepAlgoAPI_Common(a.wrapped, b.wrapped)
    common.Build()
    assert common.IsDone(), 'OCC common failed'
    shape = common.Shape()
    if shape.IsNull(): return 0.0
    properties = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, properties)
    return abs(properties.Mass())

def gap(a, b): return a.distance_to(b)

def bore_axes_xy(shape, radius):
    axes=[]
    for face in shape.faces():
        surface=BRepAdaptor_Surface(face.wrapped)
        if surface.GetType()!=GeomAbs_Cylinder: continue
        cylinder=surface.Cylinder()
        if abs(cylinder.Radius()-radius)>1e-6: continue
        axis=cylinder.Axis()
        assert abs(abs(axis.Direction().Z())-1)<1e-6
        origin=axis.Location()
        axes.append([round(origin.X(),6),round(origin.Y(),6)])
    return sorted(axes)

# A small known-volume case catches loss of a compound's parent transform.
unit = Box(2, 2, 2)
located = Compound(children=[Box(2,2,2)]).moved(Pos(10,0,0))
assert overlap(unit,located)<1e-6
assert abs(overlap(unit,Box(2,2,2).moved(Pos(1,0,0)))-4)<1e-6

pairs = [(tray, board), (negative, board), (positive, board), (tray, negative), (tray, positive)]
checks = []
for a, b in pairs:
    volume = overlap(a, b)
    checks.append({'a': a.label, 'b': b.label, 'overlap_mm3': volume, 'minimum_distance_mm': gap(a, b)})
    assert volume < 1e-3, checks[-1]

base_shape = base()
pcb_shape = pcb().moved(Pos(0, 0, CONFIG['pcb_seat_z_mm']))
placed = root.moved(Pos(0, 0, floor))
for target in [base_shape, pcb_shape]:
    volume = overlap(placed, target)
    checks.append({'a': placed.label, 'b': target.label, 'overlap_mm3': volume, 'minimum_distance_mm': gap(placed, target)})
    assert volume < 1e-3, checks[-1]

reserves = []
for region in header_reserves():
    volume = overlap(region, tray)
    reserves.append({'name':region.label,'overlap_carrier_mm3':volume,'clearance_carrier_mm':gap(region,tray),
                     'bbox_mm':list(region.bounding_box().size)})
    assert volume < 1e-3, reserves[-1]
port = usb_reserve()
port_overlap = overlap(port, tray)+overlap(port,negative)+overlap(port,positive)
assert port_overlap < 1e-3

dimensions = {}
for name, shape in [('carrier',carrier()), ('retainer',retainer())]:
    dimensions[name] = {'bbox_mm':list(shape.bounding_box().size),'solids':len(shape.solids()),
                        'volume_mm3':shape.volume,'valid':shape.is_valid}
    assert dimensions[name]['solids']==1 and shape.is_valid and shape.volume>0
assert dimensions['carrier']['bbox_mm'] == [P['plate_length'],P['plate_width'],RETAINER_Z]

# Source joint positions must agree with the documented imported-model datum.
lower_face = board.bounding_box().max.Z - 3.2500001 + P['model_board_bottom_z']
assert abs(lower_face-SEAT)<1e-6
assert abs(negative.bounding_box().min.Z-RETAINER_Z)<1e-6
assert abs(positive.bounding_box().min.Z-RETAINER_Z)<1e-6
pilot_axes=bore_axes_xy(tray,P['pilot_diameter']/2)
retainer_axes=sorted(bore_axes_xy(negative,P['retainer_hole_diameter']/2)+
                     bore_axes_xy(positive,P['retainer_hole_diameter']/2))
assert len(pilot_axes)==4 and pilot_axes==retainer_axes
board_top_global = SEAT-P['model_board_bottom_z']+floor
retainer_gap = RETAINER_Z+floor-board_top_global
assert retainer_gap >= P['retainer_vertical_clearance']
ceiling_gap = CONFIG['pcb_seat_z_mm']-placed.bounding_box().max.Z
assert ceiling_gap > 2.5

report = {
 'status':'analytical_geometry_pass_not_physical_fit', 'revision':P['revision'],
 'overlap_method':'OCC Common on located wrapped shapes; translated-compound and known-volume controls passed',
 'dimensions':dimensions, 'pairs':checks,'assumed_header_reserves':reserves,
 'usb_reserve_overlap_holder_mm3':port_overlap,'usb_access':'service_only_LED_board_removed_external_power_disconnected',
 'board_lower_face_global_z_mm':SEAT+floor,'retainer_gap_above_reference_PCB_mm':retainer_gap,
 'controller_to_LED_board_clearance_mm':ceiling_gap,
 'mounting':{'method':'two nylon ties through shared base slots',
   'slot_centres_xy_mm':[[x*P['tie_slot_x'],y*P['tie_slot_y']] for x in [-1,1] for y in [-1,1]],
   'retainer_screw_centres_xy_mm':BOSS_XY,
   'measured_pilot_axes_xy_mm':pilot_axes,'measured_retainer_axes_xy_mm':retainer_axes,
   'retainer_mate_z_error_mm':[negative.bounding_box().min.Z-RETAINER_Z,positive.bounding_box().min.Z-RETAINER_Z]},
 'not_verified':['actual header orientation, housing, wire bend radius and physical fit','bare-edge land and board tolerance after delivery',
 'fastener thread engagement and retention force','print shrinkage and slicing','microphone and external buttons','backside LED-board connector/harness envelopes']
}
(OUT/'controller-fit-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
