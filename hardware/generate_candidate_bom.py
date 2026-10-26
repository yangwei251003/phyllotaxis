"""Candidate component rollup, not an order or fabrication BOM."""
from pathlib import Path
import csv,json
from collections import defaultdict
from library_inspect import read_library
P=Path(__file__).resolve().parent
refs=defaultdict(list)
for c in json.loads((P/'power_candidate.json').read_text())['components']:refs[c['part']].append(c['ref'])
refs['C52941391']=[f'D{i}' for i in range(1,145)]
libs={}
for file in (P/'library').glob('*.elibz2'):
    l=read_library(file);libs[l['device']['attributes']['Supplier Part']]=l['device']['attributes']
with (P/'eda/candidate-bom-NOT-FOR-ORDER.csv').open('w',newline='',encoding='utf-8-sig') as f:
    out=csv.writer(f);out.writerow(['Status','Designator','Quantity','Manufacturer','Manufacturer Part','Footprint','LCSC Part','Assembly class from library'])
    for part,names in sorted(refs.items()):
        a=libs[part];out.writerow(['DRAFT / no PCB parity',','.join(names),len(names),a['Manufacturer'],a['Manufacturer Part'],a['Supplier Footprint'],part,a.get('JLCPCB Part Class','unknown')])
print(json.dumps({'line_items':len(refs),'components':sum(map(len,refs.values())),'quoted':False,'order_ready':False}))
