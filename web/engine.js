export const GOLDEN_ANGLE=Math.PI*(3-Math.sqrt(5));
export const clamp=(x,a=0,b=1)=>Math.min(b,Math.max(a,Number.isFinite(x)?x:a));
export function layout(count=128,radius=70){
  if(!Number.isInteger(count)||count<1||count>512||!(radius>0))throw new RangeError('Invalid geometry');
  return Array.from({length:count},(_,i)=>{const r=radius*Math.sqrt((i+.5)/count),a=i*GOLDEN_ANGLE;return {id:i,x:r*Math.cos(a),y:r*Math.sin(a),r,a};});
}
export function rms(samples){return Math.sqrt(samples.reduce((sum,x)=>sum+x*x,0)/Math.max(1,samples.length));}
export function removeDC(samples){const mean=samples.reduce((a,b)=>a+b,0)/Math.max(1,samples.length);return Float32Array.from(samples,x=>x-mean);}
export function frequencyBands(magnitudes,sampleRate,fftSize,edges=[60,140,300,600,1200,2400,4800,8000]){
  return edges.slice(0,-1).map((lo,i)=>{const a=Math.max(1,Math.ceil(lo*fftSize/sampleRate)),b=Math.min(magnitudes.length,Math.ceil(edges[i+1]*fftSize/sampleRate));let sum=0;for(let k=a;k<b;k++)sum+=magnitudes[k]*magnitudes[k];return b>a?Math.sqrt(sum/(b-a)):0;});
}
export function demoSignal(t){const beat=Math.pow(Math.max(0,Math.sin(t*Math.PI*4)),9);return {level:.17+.50*beat,bands:Array.from({length:7},(_,i)=>clamp(.12+.30*(Math.sin(t*(1+i*.17)-i*.73)+1)+beat*(1-i/8))),beat};}
export function hsv(h,s,v){h=((h%360)+360)%360;const c=v*s,x=c*(1-Math.abs((h/60)%2-1)),m=v-c;const rgb=h<60?[c,x,0]:h<120?[x,c,0]:h<180?[0,c,x]:h<240?[0,x,c]:h<300?[x,0,c]:[c,0,x];return rgb.map(v=>Math.round(clamp(v+m)*255));}
export function ledFrame(points,t,signal,{mode='spiral',brightness=.22,palette='botanical',gain=1}={}){
  const level=clamp(signal.level*gain),bands=signal.bands;const maxr=Math.max(...points.map(p=>p.r));
  return points.map((p,i)=>{
    const rr=p.r/maxr,aa=p.a%(Math.PI*2);let e;
    if(mode==='spectrum')e=clamp((bands[Math.min(6,Math.floor(rr*7))]??0)*gain)*(.65+.35*Math.sin(aa-t*2));
    else if(mode==='pulse')e=clamp(1-Math.abs(rr-((t*.28+signal.beat*.1)%1))/.18)*(.2+level*.8)+level*.15;
    else e=(.12+.88*Math.pow(Math.max(0,Math.sin(aa*3-rr*12+t*(.8+level*2))),3))*(.22+level*.78);
    const hue=palette==='ember'?22+rr*40:palette==='ocean'?175+rr*65:130+rr*85+Math.sin(t*.15)*18;
    return hsv(hue,.72,clamp(e)*clamp(brightness));
  });
}
export function estimatedCurrent(rgb,{idleMA=1,channelMA=20}={}){return rgb.length*idleMA+rgb.reduce((a,p)=>a+p.reduce((v,x)=>v+x,0)/255*channelMA,0);}
export function limitFrame(rgb,budgetMA=2000,{idleMA=1,channelMA=20}={}){
  const idle=rgb.length*idleMA,active=estimatedCurrent(rgb,{idleMA,channelMA})-idle;
  const scale=active>0?clamp((budgetMA-idle)/active):1;
  return {rgb:rgb.map(p=>p.map(v=>Math.floor(v*scale))),scale,estimateMA:idle+active*scale};
}
