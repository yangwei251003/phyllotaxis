import json
from pathlib import Path
from build123d import Box,Pos,Color,Compound
HERE=Path(__file__).resolve().parent
SPEC=json.loads((HERE/'connector-envelopes.json').read_text())
def envelope(row):
    lo,hi=row['bounds_mm'];s=Pos(*[(a+b)/2 for a,b in zip(lo,hi)])*Box(*[b-a for a,b in zip(lo,hi)])
    s.label=row['name'];s.color=Color(*row['color']);return s
def connector_envelopes(include_wire_reserves=False):
    rows=SPEC['envelopes']+(SPEC['assumed_wire_reserves'] if include_wire_reserves else [])
    return Compound(children=[envelope(row) for row in rows],label='CONNECTOR_SPACE_not_vendor_models')
