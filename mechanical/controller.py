"""Removable edge holder; model origin is carrier underside at case floor.

Board datum: measured board XY centre, lower PCB face at global Z=22.
No signal/plated hole is used as a mechanical fastener. Imported board geometry
is source evidence, whereas header/cable keepouts are explicitly assumptions.
"""
import hashlib
import json
from pathlib import Path
from build123d import Align, Box, Color, Compound, Cylinder, Location, Pos
from cadgen.step_scene import import_step
from cadgen.assembly import AssemblyHelper

HERE = Path(__file__).resolve().parent
P = json.loads((HERE / 'controller-holder.json').read_text(encoding='utf-8'))
CONFIG = json.loads((HERE.parent / 'shared/design.json').read_text(encoding='utf-8'))
MIN = (Align.CENTER, Align.CENTER, Align.MIN)
SEAT = P['board_seat_global_z'] - CONFIG['floor_mm']
RETAINER_Z = SEAT + P['board_thickness_allowance'] + P['retainer_vertical_clearance']
INNER_Y = P['board_width'] / 2 - P['edge_support_overlap']
WALL_INNER_Y = P['board_width'] / 2 + P['lateral_clearance_per_side']
WALL_OUTER_Y = WALL_INNER_Y + P['sidewall_thickness']
BOSS_XY = [(sx * P['boss_x'], sy * P['boss_y']) for sx in [-1, 1] for sy in [-1, 1]]

def carrier():
    plate = Box(P['plate_length'], P['plate_width'], P['plate_thickness'], align=MIN)
    additions = []
    for sign in [-1, 1]:
        additions.append(Pos(0, sign * (WALL_INNER_Y + WALL_OUTER_Y) / 2, P['plate_thickness']) *
            Box(P['sidewall_length'], P['sidewall_thickness'], SEAT - P['plate_thickness'], align=MIN))
        # 0.6 mm of outer bare-board edge is supported by a 2 mm thick ledge.
        additions.append(Pos(0, sign * (INNER_Y + WALL_OUTER_Y) / 2, SEAT - P['support_ledge_thickness']) *
            Box(P['sidewall_length'], WALL_OUTER_Y - INNER_Y, P['support_ledge_thickness'], align=MIN))
    for x, y in BOSS_XY:
        additions.append(Pos(x, y, P['plate_thickness']) *
            Cylinder(P['boss_radius'], RETAINER_Z - P['plate_thickness'], align=MIN))
    body = plate.fuse(*additions)
    cuts = [Pos(x, y, RETAINER_Z - P['pilot_depth']) *
            Cylinder(P['pilot_diameter'] / 2, P['pilot_depth'] + 1, align=MIN) for x, y in BOSS_XY]
    cuts += [Pos(sx * P['tie_slot_x'], sy * P['tie_slot_y'], -1) *
        Box(P['tie_slot_width'], P['tie_slot_length'], P['plate_thickness'] + 2, align=MIN)
        for sx in [-1, 1] for sy in [-1, 1]]
    body = body.cut(*cuts)
    body.label = 'Carrier_PETG_edge_seat_22mm_no_signal_hole_fixing'
    body.color = Color(.28, .40, .34)
    return body

def retainer():
    # Local Y=0 is the screw axis; one source prints both mirrored rails.
    y0 = INNER_Y - P['boss_y']
    y1 = P['retainer_outer_y'] - P['boss_y']
    body = Pos(0, (y0 + y1) / 2, 0) * Box(P['retainer_length'], y1-y0, P['retainer_thickness'], align=MIN)
    body = body.cut(*[Pos(sign * P['boss_x'], 0, -1) *
        Cylinder(P['retainer_hole_diameter'] / 2, P['retainer_thickness'] + 2, align=MIN) for sign in [-1, 1]])
    body.label = 'Retainer_PETG_print_2_M3_trial_pilot_not_validated'
    body.color = Color(.68, .75, .63)
    return body

def board_reference():
    source = HERE / P['board_model']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == P['board_model_sha256']
    # Preserve the manufacturer's complete tree. Its open cosmetic shells and
    # touching sub-bodies are documented in cad-weact-reference-validate.json.
    # This purchased reference is not a printable part; do not silently heal it.
    return import_step(source)

def board_in_carrier():
    return board_reference().moved(Pos(-P['board_length']/2, -P['board_width']/2, SEAT-P['model_board_bottom_z']))

def header_reserves():
    """Whole-row wire allowances, intentionally not actual purchased connectors."""
    z0 = P['header_wire_reserve_bottom_global_z'] - CONFIG['floor_mm']
    shapes = []
    for sign in [-1, 1]:
        s = Pos(0, sign * P['header_row_pitch']/2, z0) * Box(
            P['header_wire_reserve_length'], P['header_wire_reserve_width'], SEAT-z0, align=MIN)
        s.label = f'ASSUMED_header_wire_reserve_{sign:+d}_not_part'
        s.color = Color(.22, .60, .84, .35)
        shapes.append(s)
    return shapes

def usb_reserve():
    s = Pos(-P['board_length']/2-P['usb_reserve_length']/2, 0,
            SEAT-P['model_board_bottom_z']-.5) * Box(
                P['usb_reserve_length'], P['usb_reserve_width'], P['usb_reserve_height'], align=MIN)
    s.label = 'ASSUMED_USB_service_space_open_lid_only_not_part'
    s.color = Color(.91, .65, .20, .25)
    return s

def controller_assembly(include_reserves=False):
    asm = AssemblyHelper('WeAct_V31_removable_holder_candidate')
    tray = asm.add(carrier(), 'carrier_edge_supports')
    board = asm.add(board_reference(), 'WeAct_official_V31_reference_no_headers')
    fixed = asm.rigid_frame(tray, 'board_lower_face_seat', Location((0, 0, SEAT)))
    moving = asm.rigid_frame(board, 'board_xy_centre_lower_face', Location((
        P['board_length']/2, P['board_width']/2, P['model_board_bottom_z'])))
    asm.face_to_face(fixed, moving)
    for sign in [-1, 1]:
        rail = asm.add(retainer(), f'retainer_side_{sign:+d}')
        # Rotate the negative rail by 180 degrees: X screw pattern is symmetric.
        target = asm.rigid_frame(tray, f'retainer_seat_{sign:+d}',
            Location((0, sign*P['boss_y'], RETAINER_Z), (0, 0, 0 if sign>0 else 180)))
        underside = asm.rigid_frame(rail, 'underside_screw_centre', Location())
        asm.face_to_face(target, underside)
    result = asm.build()
    if include_reserves:
        return Compound(children=[result, *header_reserves(), usb_reserve()], label='Controller_with_ASSUMED_wire_reserves')
    return result
