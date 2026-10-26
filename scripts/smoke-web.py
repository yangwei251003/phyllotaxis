"""Start only our own temporary local web server and check static assets; no browser or hardware."""
from pathlib import Path
import json,os,re,subprocess,urllib.request
ROOT=Path(__file__).resolve().parents[1]
env=os.environ.copy();env['PORT']='0'
process=subprocess.Popen(['node',str(ROOT/'web/server.mjs')],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf8')
try:
    line=process.stdout.readline()
    match=re.search(r'http://127\.0\.0\.1:(\d+)',line)
    if not match:raise RuntimeError('Our isolated server did not announce a loopback port.')
    base=match.group(0);results={}
    for file in ('/','/app.js','/engine.js','/telemetry.js','/device-panel.js','/design.json','/style.css','/device-panel.css'):
        with urllib.request.urlopen(base+file,timeout=10) as response:
            data=response.read();assert response.status==200 and data;results[file]=len(data)
    print(json.dumps({'ok':True,'assets_checked':len(results),'hardware_accessed':False}))
finally:
    process.terminate()
    try:process.communicate(timeout=5)
    except subprocess.TimeoutExpired:process.kill();process.communicate(timeout=5)
