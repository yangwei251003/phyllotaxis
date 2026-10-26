"""Save checked manufacturer maxima separately from our engineering reserves."""
from pathlib import Path
import json,hashlib,urllib.request,concurrent.futures
P=Path(__file__).resolve().parents[1];S=P/'hardware/datasheets';S.mkdir(exist_ok=True)
rows={
 'C2910138':('JSCJ-CJQ16P03.pdf','https://atta.szlcsc.com/upload/public/pdf/source/20240329/674A4B8EBD31C730C33351B5F04B40DF.pdf',[4],1.75,[5.10,6.20],'SOP8 D along library X; total E including leads along Y. A already includes own stand-off.'),
 'C12495':('Nexperia-SOT353-1.pdf','https://assets.nexperia.com/documents/package-information/SOT353-1.pdf',[1,2],1.10,[2.40,2.60],'Library X across lead rows, Y along D. D/E exclude up to0.2mm protrusion per edge; maximum body2.60x1.75 included.'),
 'C271259':('BORN-BZT52C-series.pdf','https://atta.szlcsc.com/upload/public/pdf/source/20180820/C271262_D2D0F24DD5A81EAE2A6B8B493A94E64A.pdf',[5],1.25,[3.85,1.70],'Manufacturer BZT52Cxx family includes C12 despite shared LCSC mirror filename.'),
 'C8545':('JSCJ-2N7002.pdf','https://www.jscj-elec.com/gallery/file/2N7002%20SOT-23%20V2.0.pdf',[4],1.15,[2.55,3.00],'Library X across leads (E1), Y along D.'),
 'C17313':('Bourns-MF-MSMF.pdf','https://www.bourns.com/docs/product-datasheets/mf-msmf.pdf',[4,7,11],.85,[4.73,3.41],'050 standard dimensions; -2 is packaging. Do not use 050/xxX length4.83.'),
 'C14663':('Yageo-CC0603KRX7R9BB104.pdf','https://yageogroup.com/download/specsheet/CC0603KRX7R9BB104',[1],.90,[1.70,.90],'Specific MPN; L1.6+0.1,W/T0.8+0.1.'),
 'C21190':('Uniroyal-catalog-2024.pdf','https://www.uni-royal.cn/images/upload/UniroyalCatalog2024.06.07.pdf',[10,175],.55,[1.70,.90],'0603 WAF: WA normal-size1/10W, F1%; height.45+.10.'),
 'C46550459':('JIERR-MA-series.pdf','https://atta.szlcsc.com/upload/public/pdf/source/20260306/24758A4FC016E80367B87853635CDCC1.pdf',[2],8.20,[6.80,6.80],'L7.7+a0.5=8.2; diameter6.3+0.5=6.8; base6.6+0.2=6.8. Do not add a twice.')}
def fetch(item):
    part,(name,url,pages,height,xy,note)=item;p=S/name
    if not p.exists():
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 PHYLLO-review'}),timeout=35) as response:data=response.read()
            assert data.startswith(b'%PDF'),f'Not PDF: {url}';p.write_bytes(data)
        except Exception as e:return part,{'download':'unavailable','error':str(e),'source_url':url}
    return part,{'download':'saved','path':p.relative_to(P).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'source_url':url}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:files=dict(pool.map(fetch,rows.items()))
specpath=P/'mechanical/component-heights.json';spec=json.loads(specpath.read_text())
for part,data in rows.items():
    name,url,pages,height,xy,note=data;record=spec['rows'][part]
    record.update({'manufacturer_max_height_mm':height,'maximum_overall_xy_in_library_axes_mm':xy,'source_url':url,'source_pages':pages,
      'source_file':files[part],'manufacturer_dimension_note':note,'basis':'Manufacturer dimensional maximum plus separately stated engineering height reserve.'})
    assert record['height_mm']>=height;record['extra_height_reserve_mm']=record['height_mm']-height
for part in ['C22935','C23138','C25803']:spec['rows'][part]=dict(spec['rows']['C21190'])
specpath.write_text(json.dumps(spec,indent=2),encoding='utf-8')
(P/'verification/component-dimension-sources.json').write_text(json.dumps({'status':'MANUFACTURER_MAXIMA_CHECKED_BY_READ_ONLY_HARDWARE_REVIEW','files':files,'note':'Diagram axis-to-library mappings explicit in component-heights.json. Height A already includes internal stand-off; selected reserve is engineering allowance, not manufacturer claim.'},indent=2),encoding='utf-8')
print(json.dumps({part:rec['download'] for part,rec in files.items()}))
