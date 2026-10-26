"""Save cited manufacturer connector drawings and hashes for local review."""
from pathlib import Path
import urllib.request,hashlib,json
import pymupdf
P=Path(__file__).resolve().parents[1];D=P/'hardware/datasheets';D.mkdir(exist_ok=True)
sources=[('JST-XH.pdf','https://www.jst-mfg.com/product/pdf/eng/eXH.pdf',[1,3,4]),
 ('AMASS-XT30PW-M30.pdf','https://www.china-amass.net/uploads/32.XT30PW-M30-SPEC-2025V0.pdf',[0]),
 ('AMASS-XT30PW-M-drawing.pdf','https://store.comet.bg/download-file.php?id=30571',[0])]
report=[]
for name,url,pages in sources:
    path=D/name
    try:
        if not path.exists():
            with urllib.request.urlopen(url,timeout=40) as res:data=res.read()
            assert data.startswith(b'%PDF-'),'not a PDF'
            path.write_bytes(data)
        doc=pymupdf.open(path)
        for page in pages:
            assert page<len(doc)
            doc[page].get_pixmap(matrix=pymupdf.Matrix(2,2)).save(D/(path.stem+f'-p{page+1}.png'))
        report.append({'file':name,'url':url,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'pages':len(doc),'status':'saved'})
    except Exception as e:report.append({'file':name,'url':url,'status':'failed','error':str(e)})
(P/'verification/connector-source-files.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
