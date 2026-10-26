from pathlib import Path
import json, math, sys
root=Path(__file__).resolve().parents[3]
layout=json.loads((root/'shared/layout.json').read_text())
chain=json.loads((root/'shared/chain.json').read_text())['chain_to_geometry_id']
assert len(layout['leds'])==144 and sorted(chain)==list(range(144))
lines=['/* Generated from shared geometry; physical PCB chain is still a candidate. */',
       '#ifndef PHYLLO_LAYOUT_GENERATED_H','#define PHYLLO_LAYOUT_GENERATED_H',
       'static const phyllo_point led_points[PHYLLO_LED_MAX] = {']
for p in layout['leds']:
    lines.append('{%.9ff,%.9ff},'%(p['radius_mm'],p['angle_rad']%(2*math.pi)))
lines+=['};','static const uint16_t led_chain[PHYLLO_LED_MAX] = {',
        ','.join(map(str,chain)), '};','#endif']
Path(sys.argv[1]).write_text('\n'.join(lines)+'\n',encoding='utf-8')
