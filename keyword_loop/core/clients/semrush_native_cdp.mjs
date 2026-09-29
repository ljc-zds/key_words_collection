import process from 'node:process';
import { keywordCapture } from './semrush_response_capture.mjs';
import { paginateKeywords } from './semrush_pagination.mjs';

const [, , cdpUrl, keyword, database, queryFilter = '', capText = '100'] = process.argv;
const version = await (await fetch(`${cdpUrl}/json/version`)).json();
const socket = new WebSocket(version.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.onopen = resolve;
  socket.onerror = reject;
});

let sequence = 0;
const pending = new Map();
socket.onmessage = ({ data }) => {
  const message = JSON.parse(data);
  const callback = pending.get(message.id);
  if (callback) {
    pending.delete(message.id);
    callback(message);
  }
};
function send(method, params = {}, sessionId) {
  const id = ++sequence;
  socket.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(new Error(`${method} timed out`));
    }, 30_000);
    pending.set(id, message => {
      clearTimeout(timer);
      message.error ? reject(new Error(message.error.message)) : resolve(message.result);
    });
  });
}

let targetId;
let capture;
try {
  const target = await send('Target.createTarget', { url: 'about:blank', background: true });
  targetId = target.targetId;
  const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
  await send('Network.enable', {}, sessionId);
  await send('Page.enable', {}, sessionId);
  capture = keywordCapture(send, sessionId, 30000, {keyword,database});
  socket.onmessage = async ({ data }) => {
    const message = JSON.parse(data);
    const callback = pending.get(message.id);
    if (callback) {
      pending.delete(message.id);
      callback(message);
      return;
    }
    await capture.onEvent(message);
  };
  await send('Page.navigate', { url: `https://sem.3ue.co/analytics/keywordmagic/?q=${encodeURIComponent(keyword)}&db=${encodeURIComponent(database)}&type=all&mode=0${queryFilter ? '&filter=' + encodeURIComponent(queryFilter) : ''}` }, sessionId);
  const first = await capture.result;
  const template = capture.getTemplate();
  if (!template) throw Error('Semrush keyword request template unavailable');
  const result = await paginateKeywords(template.body, first, Number(capText), async body => {
    await new Promise(resolve => setTimeout(resolve, 1000));
    const expression = `fetch(${JSON.stringify(template.url)}, {method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:${JSON.stringify(JSON.stringify(body))}}).then(async r=>({status:r.status,body:await r.json()}))`;
    const response = await send('Runtime.evaluate', {expression,awaitPromise:true,returnByValue:true}, sessionId);
    const value = response.result?.value;
    if (value?.body?.error?.code === -2004) throw Error('SEMRUSH_REPORT_LIMIT: -2004 Report limit reached');
    if (value?.status !== 200 || value.body.error) throw Error(`Semrush pagination failed: HTTP ${value?.status}, RPC ${value?.body?.error?.code}`);
    return value.body.result;
  });
  process.stdout.write(JSON.stringify(result));
} finally {
  capture?.dispose();
  if (targetId) await send('Target.closeTarget', { targetId }).catch(() => {});
  socket.close();
}
