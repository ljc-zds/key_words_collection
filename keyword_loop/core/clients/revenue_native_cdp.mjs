import process from 'node:process';

const [, , cdpUrl, pageUrl] = process.argv;
const version = await (await fetch(`${cdpUrl}/json/version`)).json();
const socket = new WebSocket(version.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
let sequence = 0;
const pending = new Map();
socket.onmessage = ({ data }) => {
  const message = JSON.parse(data);
  const callback = pending.get(message.id);
  if (!callback) return;
  pending.delete(message.id);
  message.error ? callback.reject(new Error(message.error.message)) : callback.resolve(message.result);
};
function send(method, params = {}, sessionId) {
  const id = ++sequence;
  socket.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`${method} timed out`)); }, 30000);
    pending.set(id, { resolve: value => { clearTimeout(timer); resolve(value); }, reject });
  });
}
let targetId;
try {
  targetId = (await send('Target.createTarget', { url: 'about:blank', background: true, hidden: true })).targetId;
  const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
  await send('Page.enable', {}, sessionId);
  await send('Page.navigate', { url: pageUrl }, sessionId);
  await new Promise(resolve => setTimeout(resolve, 2500));
  const value = await send('Runtime.evaluate', { expression: 'document.documentElement.outerHTML', returnByValue: true }, sessionId);
  process.stdout.write(value.result?.value || '');
} finally {
  if (targetId) await send('Target.closeTarget', { targetId }).catch(() => {});
  socket.close();
}
