import test from 'node:test';
import assert from 'node:assert/strict';
import {parseTelemetry,TelemetryLines,DeviceConnection} from '../telemetry.js';
const packet = {type:'phyllo',candidate:true,ms:3000,blocks:93,drop:0,errors:0,frames:90,peak:24,rms_ppm:32000,fft_cycles_max:120000};
const enc = new TextEncoder(), line = JSON.stringify(packet)+'\r\n';
const tick = () => new Promise(r=>setTimeout(r,0));
function fakePort() {
  let controller;
  return {closed:0, opened:0, readable:new ReadableStream({start(c){controller=c;}}),
    async open(options){this.opened++;assert.equal(options.baudRate,115200);},
    async close(){assert.equal(this.readable.locked,false);this.closed++;},
    push(text){controller.enqueue(enc.encode(text));}, end(){controller.close();}, fail(){controller.error(Error('device removed'));}
  };
}
function fakeSerial(port, request = async()=>port) { const serial = new EventTarget();serial.requestPort=request;return serial; }
test('strict protocol rejects unrelated, missing, noninteger and out-of-range data',()=>{
  assert.deepEqual(parseTelemetry(line),packet);
  for (const p of [null,{}, {...packet,type:'other'}, {...packet,candidate:false}, {...packet,drop:-1}, {...packet,ms:2**32}, {...packet,frames:'90'}, {...packet,errors:.5}, {...packet,peak:257}, {...packet,rms_ppm:1000001}]) assert.equal(parseTelemetry(JSON.stringify(p)),null);
  assert.equal(parseTelemetry('<html>'),null);
});
test('split CRLF, multiple frames, invalid lines and oversized input recover with bounded storage',()=>{
  const parser=new TelemetryLines();const output=[];
  for (const byte of enc.encode(line)) output.push(...parser.push(new Uint8Array([byte])));
  assert.deepEqual(output,[packet]);
  assert.deepEqual(parser.push(enc.encode('bad\n'+'x'.repeat(100000))),[]);assert.equal(parser.buffer.length,0);
  assert.deepEqual(parser.push(enc.encode('\n'+line+line)),[packet,packet]);assert.equal(parser.invalid,2);
});
test('valid packets establish liveness; garbage does not; stale stream can recover',async()=>{
  const port=fakePort(), events=[];let now=0;
  const c=new DeviceConnection(fakeSerial(port),v=>events.push(v),()=>now);
  assert.equal(await c.connect(),true);assert.equal(await c.connect(),false);
  port.push(line);await tick();assert.equal(events.at(-1).state,'online');
  now=2600;port.push('garbage\n');await tick();c.checkTimeout();assert.equal(events.at(-1).state,'stale');
  const n=events.length;c.checkTimeout();assert.equal(events.length,n);
  port.push(line);await tick();assert.equal(events.at(-1).state,'online');
  await c.disconnect();assert.equal(port.closed,1);assert.equal(port.readable.locked,false);assert.equal(events.at(-1).state,'disconnected');
});
test('open but silent serial is never labelled online',async()=>{
  const port=fakePort(),events=[];let now=0;const c=new DeviceConnection(fakeSerial(port),v=>events.push(v),()=>now);
  await c.connect();now=2500;c.checkTimeout();assert.equal(events.at(-1).state,'stale');assert.equal(events.at(-1).packet,null);await c.dispose();
});
test('cancelled selection and failed open release the session for retry',async()=>{
  const events=[],port=fakePort(),s=fakeSerial(port,async()=>{const e=Error('cancel');e.name='NotFoundError';throw e;});
  const c=new DeviceConnection(s,v=>events.push(v));await c.connect();assert.equal(events.at(-1).state,'cancelled');assert.equal(c.active,null);
  s.requestPort=async()=>port;port.open=async()=>{throw Error('busy');};await c.connect();assert.equal(events.at(-1).state,'error');assert.equal(port.closed,0);assert.equal(c.active,null);
});
test('disconnect during picker and during opening cannot leave a late port open',async()=>{
  let resolvePick;const port=fakePort(),c=new DeviceConnection(fakeSerial(port,()=>new Promise(r=>resolvePick=r)),()=>{});
  const connect=c.connect(),stop=c.disconnect();resolvePick(port);await Promise.all([connect,stop]);assert.equal(port.opened,0);assert.equal(c.active,null);
  let resolveOpen;port.open=()=>new Promise(r=>resolveOpen=r);const second=c.connect();await tick();const stop2=c.disconnect();resolvePick(port);await tick();
  // Selection was stopped before open; verify separately with immediate selection.
  await Promise.all([second,stop2]);
  const p2=fakePort();p2.open=()=>new Promise(r=>resolveOpen=r);const c2=new DeviceConnection(fakeSerial(p2),()=>{});
  const third=c2.connect();await tick();const stop3=c2.disconnect();resolveOpen();await Promise.all([third,stop3]);assert.equal(p2.closed,1);assert.equal(c2.active,null);
});
test('EOF, read failure and physical disconnect close the stream and allow reconnect',async()=>{
  for (const reason of ['eof','failure','event']) {
    const port=fakePort(),events=[],s=fakeSerial(port),c=new DeviceConnection(s,v=>events.push(v));await c.connect();
    const done=c.active.done;
    if(reason==='eof')port.end();else if(reason==='failure')port.fail();else {const event=new Event('disconnect');event.port=port;s.dispatchEvent(event);}
    await done;assert.equal(port.closed,1);assert.equal(port.readable.locked,false);assert.equal(c.active,null);
    assert.equal(events.at(-1).state,reason==='failure'?'error':'unplugged');
    const second=fakePort();s.requestPort=async()=>second;await c.connect();await c.dispose();assert.equal(second.closed,1);
  }
});
