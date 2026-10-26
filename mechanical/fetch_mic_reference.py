"""Save official SEN0526 reference files. This does not order a module."""
from pathlib import Path
import urllib.request,json,hashlib,concurrent.futures
P=Path(__file__).resolve().parents[1];D=P/'mechanical/reference/SEN0526';D.mkdir(exist_ok=True)
base='https://img.dfrobot.com.cn/wiki/60c1e008bddfc41c3293de80/'
files={'3D.rar':'6918fc8040a7dd098f95f1aa456a8b82.rar','2D.rar':'ff4dffc10bed62f07a75e88906cea803.rar','dimensions.pdf':'c392d03506496e9d00cfa9574ffc1a57.pdf','schematic.pdf':'3017ec9cd1ba2da7c97616cfbeafebaf.PDF','MSM261S4030H0R.pdf':'ce307ae54346de48b38fe2a3bf730aba.pdf'}
def fetch(item):
    name,remote=item;path=D/name;url=base+remote
    if not path.exists():
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=35) as response:data=response.read()
        assert data.startswith(b'%PDF') if name.endswith('.pdf') else data.startswith((b'Rar!',b'PK'))
        path.write_bytes(data)
    return {'file':name,'url':url,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(fetch,files.items()))
r={'module':'DFRobot SEN0526 Fermion I2S','chip':'MSM261S4030H0R','wiki':'https://wiki.dfrobot.com.cn/_SKU_SEN0526_Fermion_I2S_%E9%BA%A6%E5%85%8B%E9%A3%8E%E6%A8%A1%E5%9D%97','files':rows,
 'limits':['Pre-soldered header/lead version not yet verified. Do not treat included loose header as assembled.','References do not prove received board identity or audio timing.']}
(D/'sources.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps({'files':len(rows),'bytes':sum(x['bytes'] for x in rows)}))
