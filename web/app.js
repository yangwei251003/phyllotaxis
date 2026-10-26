import {layout,clamp,demoSignal,rms,removeDC,frequencyBands,ledFrame,limitFrame} from './engine.js';
const $=id=>document.getElementById(id),canvas=$('field'),ctx=canvas.getContext('2d');
const design=await fetch('./design.json').then(r=>{if(!r.ok)throw Error('Missing design geometry');return r.json();});
let points=layout(design.led_count,design.led_radius_mm),source='demo',mode='spiral',running=true,simTime=0,lastTime=0;
$('count').value=String(design.led_count);$('pointReadout').textContent=points.length+' POINTS';document.querySelector('.candidate').textContent=points.length+' 灯 · 几何候选';
let ac,analyser,stream,mediaNode,micNode,objectURL,sourceGeneration=0;
let db,timeData,linear,signal=demoSignal(0),smoothLevel=0,previousLevel=0;
let frames=0,frameStart=0,width=500,height=480;
const bars=Array.from({length:7},()=>{const e=document.createElement('i');$('bars').append(e);return e;});
function status(message,error=false){$('status').textContent=message;$('status').classList.toggle('error',error);}
function selectedSource(){['demo','mic','fileButton'].forEach(id=>$(id).classList.toggle('selected',id===(source==='file'?'fileButton':source)));$('sourceBadge').textContent=source==='demo'?'内置演示 · 合成信号':source==='mic'?'浏览器麦克风 · 本地分析':'本地音频文件 · 真实频谱';}
function stopInput(){sourceGeneration++;if(stream){stream.getTracks().forEach(t=>t.stop());stream=null;}if(micNode){micNode.disconnect();micNode=null;}if(mediaNode)mediaNode.disconnect();$('audio').pause();$('audio').hidden=true;}
async function audioContext(){if(!ac){ac=new AudioContext();analyser=ac.createAnalyser();analyser.fftSize=2048;analyser.smoothingTimeConstant=.65;db=new Float32Array(analyser.frequencyBinCount);linear=new Float32Array(db.length);timeData=new Float32Array(analyser.fftSize);}if(ac.state!=='running')await ac.resume();}
$('demo').onclick=()=>{stopInput();source='demo';selectedSource();status('正在演示合成节拍；浏览器声音与设备状态独立。');};
$('mic').onclick=async()=>{
  stopInput();const generation=sourceGeneration;status('等待麦克风授权…');
  try{
    if(!navigator.mediaDevices?.getUserMedia)throw Error('此浏览器不支持麦克风，请在 localhost 或 HTTPS 页面使用新版浏览器。');
    await audioContext();const acquired=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:false,noiseSuppression:false,autoGainControl:false}});
    if(generation!==sourceGeneration){acquired.getTracks().forEach(t=>t.stop());return;}
    stream=acquired;micNode=ac.createMediaStreamSource(stream);micNode.connect(analyser);source='mic';selectedSource();status('麦克风正在本地分析，不录音、不上传；切回演示即可关闭。');
    stream.getAudioTracks()[0].addEventListener('ended',()=>{if(source==='mic'){$('demo').click();status('麦克风已结束，恢复演示信号。');}});
  }catch(e){if(generation!==sourceGeneration)return;source='demo';selectedSource();status('麦克风未启用：'+(e.name==='NotAllowedError'?'授权被拒绝，已恢复演示信号。':e.message),true);}
};
$('fileButton').onclick=()=>{$('audioFile').value='';$('audioFile').click();};
$('audioFile').onchange=async()=>{
  const f=$('audioFile').files[0];if(!f)return;stopInput();const generation=sourceGeneration;
  try {await audioContext();if(generation!==sourceGeneration)return;if(objectURL)URL.revokeObjectURL(objectURL);objectURL=URL.createObjectURL(f);$('audio').src=objectURL;
    if(!mediaNode)mediaNode=ac.createMediaElementSource($('audio'));mediaNode.connect(analyser);analyser.disconnect();analyser.connect(ac.destination);
    source='file';selectedSource();$('audio').hidden=false;status('本地文件：'+f.name+'。播放器可暂停或跳转。');await $('audio').play();
  }catch(e){if(generation!==sourceGeneration)return;status('音频未播放：'+e.message+'；可使用播放器重试或更换文件。',true);}
};
// Only files connect to speakers. Reusing the analyser for microphones must not create feedback.
$('mic').addEventListener('click',()=>{if(analyser)analyser.disconnect();});
$('audio').addEventListener('error',()=>{if(source==='file')status('此音频无法解码，请换成 MP3、WAV 或浏览器支持的格式。',true);});
$('audio').addEventListener('ended',()=>{if(source==='file')status('音频已播放结束；可重新播放或选择另一个文件。');});
document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>{mode=b.dataset.mode;document.querySelectorAll('[data-mode]').forEach(x=>x.classList.toggle('selected',x===b));});
$('play').onclick=()=>{running=!running;$('play').textContent=running?'暂停动画':'继续动画';$('play').setAttribute('aria-pressed',String(!running));if(!running)status('画面已暂停；麦克风或音频可继续分析。切回演示可关闭麦克风。');else status(source==='demo'?'正在演示合成节拍；浏览器声音与设备状态独立。':'画面已恢复，继续分析当前音频。');};
$('brightness').oninput=()=>{$('brightnessOut').textContent=$('brightness').value+'%';};
$('gain').oninput=()=>{$('gainOut').textContent=(+$('gain').value/10).toFixed(1)+'×';};
$('count').onchange=()=>{points=layout(+$('count').value,design.led_radius_mm);$('pointReadout').textContent=points.length+' POINTS';document.querySelector('.candidate').textContent=points.length+' 灯 · 几何候选';};
$('capture').onclick=()=>{canvas.toBlob(blob=>{if(!blob)return;const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='phyllo-'+points.length+'-preview.png';a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);});};
new ResizeObserver(entries=>{const r=entries[0].contentRect;const d=Math.min(devicePixelRatio||1,2);width=r.width;height=r.height;canvas.width=Math.round(width*d);canvas.height=Math.round(height*d);ctx.setTransform(d,0,0,d,0,0);}).observe(canvas.parentElement);
function getAudio(){
  if(source==='demo')return demoSignal(simTime);
  if(!analyser||source==='file'&&$('audio').paused)return {level:0,bands:Array(7).fill(0),beat:0};
  analyser.getFloatTimeDomainData(timeData);analyser.getFloatFrequencyData(db);
  for(let i=0;i<db.length;i++)linear[i]=Number.isFinite(db[i])?Math.pow(10,db[i]/20):0;
  const raw=rms(removeDC(timeData));const level=clamp(raw*4);smoothLevel+=(level-smoothLevel)*(level>smoothLevel?.55:.12);
  const beat=clamp((level-previousLevel)*10);previousLevel=level;
  return {level:smoothLevel,bands:frequencyBands(linear,ac.sampleRate,analyser.fftSize).map(v=>clamp(v*15)),beat};
}
function draw(t){
  const dt=Math.min((t-lastTime)/1000,.05);lastTime=t;if(running)simTime+=dt;
  signal=getAudio();bars.forEach((e,i)=>{e.style.height=Math.max(2,signal.bands[i]*32)+'px';});$('energy').textContent=(signal.level*100).toFixed(1)+'%';
  if(running||frames===0){
    const radius=Math.min(width*.38,height*.40),cx=width/2,cy=height/2,scale=radius/design.led_radius_mm;
    ctx.clearRect(0,0,width,height);ctx.fillStyle='#0d1b16';ctx.fillRect(0,0,width,height);
    const bg=ctx.createRadialGradient(cx,cy,0,cx,cy,radius*1.6);bg.addColorStop(0,'#173327');bg.addColorStop(1,'#0c1915');ctx.fillStyle=bg;ctx.fillRect(0,0,width,height);
    ctx.strokeStyle='#2b4335';ctx.lineWidth=.6;
    for(const r of [.34,.67,1.10]){ctx.beginPath();ctx.arc(cx,cy,radius*r,0,Math.PI*2);ctx.stroke();}
    for(let a=0;a<Math.PI*2;a+=Math.PI/12){const ri=radius*1.09,ro=radius*1.12;ctx.beginPath();ctx.moveTo(cx+Math.cos(a)*ri,cy+Math.sin(a)*ri);ctx.lineTo(cx+Math.cos(a)*ro,cy+Math.sin(a)*ro);ctx.stroke();}
    if($('guides').checked){ctx.beginPath();points.forEach((p,i)=>{const x=cx+p.x*scale,y=cy-p.y*scale;i?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.strokeStyle='#314738';ctx.stroke();}
    const rendered=limitFrame(ledFrame(points,simTime,signal,{mode,brightness:+$('brightness').value/100,palette:$('palette').value,gain:+$('gain').value/10}));
    $('current').textContent=(rendered.estimateMA/1000).toFixed(2)+' A';
    const ledSize=Math.max(2.2,radius/Math.sqrt(points.length)*.25);
    rendered.rgb.forEach((rgb,i)=>{const p=points[i],x=cx+p.x*scale,y=cy-p.y*scale;const display=rgb.map(v=>Math.min(255,Math.round(Math.pow(v/255,.5)*255))),color=`rgb(${display.join(',')})`;ctx.shadowColor=color;ctx.shadowBlur=ledSize*4.5;ctx.fillStyle=color;ctx.beginPath();ctx.arc(x,y,ledSize,0,2*Math.PI);ctx.fill();ctx.shadowBlur=0;ctx.fillStyle=`rgba(236,255,222,${Math.max(...display)/255*.50})`;ctx.beginPath();ctx.arc(x-.5,y-.5,ledSize*.35,0,2*Math.PI);ctx.fill();});
  }
  frames++;if(t-frameStart>1000){$('fps').textContent=running?Math.round(frames*1000/(t-frameStart))+' FPS':'PAUSED';frames=0;frameStart=t;}
  requestAnimationFrame(draw);
}
if(matchMedia('(prefers-reduced-motion: reduce)').matches){running=false;$('play').textContent='开始动画';$('play').setAttribute('aria-pressed','true');status('已遵循减少动态效果偏好；点击开始动画体验。');}
window.addEventListener('pagehide',()=>{stopInput();if(objectURL)URL.revokeObjectURL(objectURL);if(ac)ac.close();});
requestAnimationFrame(draw);
