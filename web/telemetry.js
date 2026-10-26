// Read-only USART2 health telemetry. This protocol does not carry LED pixels or commands.
export const FIELDS = ['ms','blocks','drop','errors','frames','peak','rms_ppm','fft_cycles_max'];
export function parseTelemetry(line) {
  let value;
  try { value = JSON.parse(line); } catch { return null; }
  if (!value || value.type !== 'phyllo' || value.candidate !== true) return null;
  if (!FIELDS.every(k => Number.isInteger(value[k]) && value[k] >= 0 && value[k] <= 0xffffffff)) return null;
  if (value.peak > 256 || value.rms_ppm > 1000000) return null;
  return Object.fromEntries(['type','candidate',...FIELDS].map(k => [k,value[k]]));
}

export class TelemetryLines {
  constructor(limit = 512) { this.limit = limit; this.buffer = ''; this.dropping = false; this.invalid = 0; this.decoder = new TextDecoder(); }
  push(bytes) {
    const packets = [];
    for (const char of this.decoder.decode(bytes, {stream:true})) {
      if (char === '\n') {
        if (!this.dropping) {
          const packet = parseTelemetry(this.buffer.trim());
          if (packet) packets.push(packet); else if (this.buffer.trim()) this.invalid++;
        }
        this.buffer = ''; this.dropping = false;
      } else if (!this.dropping) {
        if (this.buffer.length >= this.limit) { this.buffer = ''; this.dropping = true; this.invalid++; }
        else this.buffer += char;
      }
    }
    return packets;
  }
}

export class DeviceConnection {
  constructor(serial, onChange, now = () => performance.now()) {
    this.serial = serial; this.onChange = onChange; this.now = now; this.active = null;
    this.unplug = event => {
      if (this.active && (event.target === this.active.port || event.port === this.active.port))
        void this.disconnect('unplugged');
    };
    serial?.addEventListener('disconnect', this.unplug);
  }
  emit(ctx, state, extra = {}) {
    if (this.active === ctx) this.onChange({state, packet:ctx.packet, invalid:ctx.lines.invalid, ...extra});
  }
  async connect() {
    if (!this.serial || this.active) return false;
    const ctx = {stopped:false, port:null, reader:null, opened:false, packet:null, lines:new TelemetryLines(), last:this.now(), reason:'disconnected'};
    ctx.done = new Promise(resolve => { ctx.resolve = resolve; });
    this.active = ctx; this.emit(ctx, 'choosing');
    try {
      ctx.port = await this.serial.requestPort();
      if (ctx.stopped) { await this.finish(ctx); return false; }
      this.emit(ctx, 'opening');
      await ctx.port.open({baudRate:115200, dataBits:8, stopBits:1, parity:'none', flowControl:'none'});
      ctx.opened = true;
      if (ctx.stopped) { await this.finish(ctx); return false; }
      if (!ctx.port.readable) throw new Error('此串口没有可读取的数据流。');
      ctx.reader = ctx.port.readable.getReader(); ctx.last = this.now();
      this.emit(ctx, 'waiting');
      ctx.readTask = this.read(ctx);
      return true;
    } catch (error) {
      if (!ctx.stopped) {
        ctx.reason = error.name === 'NotFoundError' ? 'cancelled' : 'error';
        ctx.error = error.message;
      }
      await this.finish(ctx); return false;
    }
  }
  async read(ctx) {
    try {
      while (!ctx.stopped) {
        const {value,done} = await ctx.reader.read();
        if (done) { if (!ctx.stopped) ctx.reason = 'unplugged'; break; }
        if (ctx.stopped) break;
        for (const packet of ctx.lines.push(value)) {
          ctx.packet = packet; ctx.last = this.now(); ctx.stale = false;
          this.emit(ctx, 'online');
        }
      }
    } catch (error) {
      if (!ctx.stopped) { ctx.reason = 'error'; ctx.error = error.message; }
    } finally {
      ctx.reader.releaseLock(); ctx.reader = null;
      await this.finish(ctx);
    }
  }
  checkTimeout() {
    const ctx = this.active;
    if (ctx?.reader && !ctx.stopped && !ctx.stale && this.now() - ctx.last >= 2500) {
      ctx.stale = true; this.emit(ctx, 'stale');
    }
  }
  async finish(ctx) {
    if (ctx.finishing) return ctx.done;
    ctx.finishing = true;
    if (ctx.opened) {
      try { await ctx.port.close(); }
      catch (error) { if (ctx.reason === 'disconnected') { ctx.reason = 'error'; ctx.error = error.message; } }
    }
    this.emit(ctx, ctx.reason, {error:ctx.error});
    if (this.active === ctx) this.active = null;
    ctx.resolve();
  }
  async disconnect(reason = 'disconnected') {
    const ctx = this.active; if (!ctx) return;
    ctx.stopped = true; ctx.reason = reason; this.emit(ctx, 'closing');
    if (ctx.reader) { try { await ctx.reader.cancel(); } catch { /* read loop owns lock release and close */ } }
    return ctx.done;
  }
  async dispose() {
    this.serial?.removeEventListener('disconnect', this.unplug);
    await this.disconnect();
  }
}
