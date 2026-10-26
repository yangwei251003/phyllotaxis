"""Read native library pin numbers/positions and footprint pad IDs without editing EDA."""
from pathlib import Path
import json,zipfile,hashlib
from eda_format import parse_records

def read_library(path):
    z=zipfile.ZipFile(path)
    records=list(parse_records(z.read(next(k for k in z.namelist() if k.endswith('.elibu'))).decode('utf-8')))
    device_id,device=next(iter(json.loads(z.read('device2.json'))['devices'].items()))
    docs={};current=None
    for h,b in records:
        if h['type']=='DOCHEAD':current=(b['docType'],b['uuid']);docs.setdefault(current,[])
        else:docs[current].append((h,b))
    symbols=docs[('SYMBOL',device['attributes']['Symbol'])]
    pins={h['id']:dict(b) for h,b in symbols if h['type']=='PIN'}
    for h,b in symbols:
        if h['type']=='ATTR' and b.get('parentId') in pins:
            pins[b['parentId']][b['key']]=b['value']
    pads={b['num']:{'id':h['id'],**b} for h,b in docs[('FOOTPRINT',device['attributes']['Footprint'])] if h['type']=='PAD'}
    assert all(p['Pin Number'] in pads for p in pins.values())
    return dict(device_id=device_id,device=device,docs=docs,pins={p['Pin Number']:p for p in pins.values()},pads=pads)

if __name__=='__main__':
    root=Path(__file__).resolve().parent;report=[]
    for path in sorted((root/'library').glob('*.elibz2')):
        a=read_library(path)
        report.append({'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'supplier_part':a['device']['attributes']['Supplier Part'],
            'manufacturer_part':a['device']['attributes']['Manufacturer Part'],
            'pins':{n:{'name':p['Pin Name'],'x':p['x'],'y':p['y'],'rotation':p['rotation'],'footprint_pad_id':a['pads'][n]['id']} for n,p in a['pins'].items()}})
    (root/'library/library-pin-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{'part':p['supplier_part'],'pins':{n:q['name'] for n,q in p['pins'].items()}} for p in report]))
