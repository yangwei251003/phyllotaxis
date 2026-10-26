import {DeviceConnection} from './telemetry.js';
const $ = id => document.getElementById(id);
const labels = {choosing:'选择串口',opening:'正在连接',waiting:'等待设备数据',online:'设备在线',stale:'数据超时',closing:'正在断开',disconnected:'未连接',cancelled:'未连接',unplugged:'连接已断开',error:'连接异常'};
const hints = {
  choosing:'在浏览器弹窗中选择连接 STM32 的 USB 转串口设备。',
  opening:'正在打开串口…', waiting:'已打开串口，等待固件每秒发送的运行状态。',
  online:'收到 PHYLLO 候选固件数据。下方为本次开机累计值；上方动画仍使用浏览器声音。',
  stale:'超过 2.5 秒未收到有效状态，显示值已过期。检查串口与固件；若灯阵冻结或异常，请断开唯一 5V 电源。',
  closing:'正在释放连接…', disconnected:'通过 USB 转串口连接后，可查看实体设备的运行状态。',
  cancelled:'已取消串口选择，可以随时重新连接。',
  unplugged:'串口数据已断开。断开网页连接不会关闭灯阵电源；重新插入后可再次连接。',
  error:'无法继续读取串口，请检查设备、波特率及串口是否被其他软件占用。'
};
const metrics = ['deviceUptime','deviceFrames','deviceBlocks','deviceDrop','deviceErrors','deviceRms'];
function update(view) {
  $('deviceState').textContent = labels[view.state]; $('hardwareSummary').textContent = labels[view.state];
  $('deviceStatus').textContent = hints[view.state];
  const online = view.state === 'online'; $('devicePanel').dataset.state = view.state;
  $('deviceConnect').disabled = ['choosing','opening','waiting','online','stale','closing'].includes(view.state);
  $('deviceDisconnect').disabled = !['choosing','opening','waiting','online','stale'].includes(view.state);
  $('deviceMetrics').classList.toggle('expired', !online);
  $('deviceMetrics').setAttribute('aria-label', online ? '设备累计运行数据' : '设备数据不可用或已过期');
  if (view.packet && ['online','stale'].includes(view.state)) {
    const p = view.packet, seconds = Math.floor(p.ms / 1000);
    $('deviceUptime').textContent = `${Math.floor(seconds/3600)}:${String(Math.floor(seconds/60)%60).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;
    [p.frames,p.blocks,p.drop,p.errors].forEach((n,i) => $(metrics[i+1]).textContent = n.toLocaleString('zh-CN'));
    $('deviceRms').textContent = (p.rms_ppm/10000).toFixed(2)+'%';
    $('deviceQuality').textContent = p.errors || p.drop ? '本次开机记录过音频丢块或错误，请结合累计变化排查。' : '未报告音频丢块或错误。此状态不代表供电、温升已验证。';
  } else if (!['choosing','opening','closing'].includes(view.state)) {
    metrics.forEach(id => $(id).textContent = '—'); $('deviceQuality').textContent = '尚无有效运行数据。';
  }
}
const supported = Boolean(navigator.serial && window.isSecureContext);
const connection = new DeviceConnection(supported ? navigator.serial : null, update);
update({state:'disconnected'});
if (!supported) {
  $('deviceConnect').disabled = true;
  $('deviceStatus').textContent = '设备连接需要桌面 Chrome 或 Edge，并通过 localhost 或 HTTPS 打开。声音演示仍可使用。';
}
$('deviceConnect').onclick = () => connection.connect();
$('deviceDisconnect').onclick = () => connection.disconnect();
const timer = setInterval(() => connection.checkTimeout(),250);
window.addEventListener('pagehide',() => { clearInterval(timer); void connection.dispose(); });
// A restored page otherwise keeps disposed audio/serial resources and no timeout timer.
window.addEventListener('pageshow',event => { if (event.persisted) location.reload(); });
