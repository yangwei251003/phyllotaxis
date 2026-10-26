from build123d import Compound,Pos
from parts import pcb,C
from connectors import connector_envelopes
def gen_step():
    # Remove the base for an unobstructed underside service view; the separate
    # collision check still uses the full base, pillars and controller envelope.
    return Compound(children=[pcb().moved(Pos(0,0,C['pcb_seat_z_mm'])),connector_envelopes(True)],label='PHYLLO_connector_space_base_removed_for_view')
