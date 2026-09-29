import process from 'node:process';
import {similarwebCapture} from './similarweb_response_capture.mjs';
const [, , cdpUrl, pageUrl, fragment, maxPages = '5'] = process.argv;
const routeQuery = new URLSearchParams(new URL(pageUrl).hash.split('?')[1]);
const requestedRange = routeQuery.has('cpcFromValue')
  ? `${routeQuery.has('volumeFromValue') ? 'dailyVolume,' + routeQuery.get('volumeFromValue') + ',|' : ''}cpc,${routeQuery.get('cpcFromValue')},|difficulty,${routeQuery.get('difficultyFromValue')},${routeQuery.get('difficultyToValue')}` : null;
const version = await (await fetch(`${cdpUrl}/json/version`)).json();
const socket = new WebSocket(version.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
let seq = 0; const pending = new Map(); let capture;
socket.onmessage = ({data}) => { const m=JSON.parse(data); const p=pending.get(m.id); if(p){pending.delete(m.id); m.error?p.reject(new Error(m.error.message)):p.resolve(m.result);} else capture?.onEvent(m); };
function send(method, params={}, sessionId){const id=++seq; socket.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})})); return new Promise((resolve,reject)=>{const t=setTimeout(()=>{pending.delete(id);reject(new Error(method+' timed out'))},30000);pending.set(id,{resolve:v=>{clearTimeout(t);resolve(v)},reject:e=>{clearTimeout(t);reject(e)}});});}
let targetId;
try {
  targetId = (await send('Target.createTarget', {url: 'about:blank', background: true})).targetId;
  const {sessionId} = await send('Target.attachToTarget', {targetId, flatten: true});
  await send('Emulation.setFocusEmulationEnabled', {enabled: true}, sessionId);
  await send('Network.enable', {}, sessionId);
  await send('Page.enable', {}, sessionId);
  capture = similarwebCapture(send, sessionId, {fragment,range:requestedRange}, async seedUrl => {
    const gridUrl = new URL(seedUrl);
    if (requestedRange) gridUrl.searchParams.set('rangeFilter', requestedRange);
    gridUrl.searchParams.delete('label');
    gridUrl.searchParams.set('type', 'Broad');
    gridUrl.searchParams.set('page', '1');
    const expression = `fetch(${JSON.stringify(gridUrl.toString())}, {method:'POST', credentials:'include'}).then(async r => ({status:r.status, body:await r.json()}))`;
    const grid = await send('Runtime.evaluate', {expression, awaitPromise: true, returnByValue: true}, sessionId);
    if (grid.result?.value?.status !== 200) throw Error(`Similarweb primary HTTP ${grid.result?.value?.status}`);
    return {url:gridUrl.toString(),status:200,body:grid.result.value.body};
  });
  await send('Page.navigate', {url: pageUrl}, sessionId);
  const primary = await capture.result;
  const out = [primary];
  const pageSize = primary?.body?.records?.length || 0;
  const totalPages = Math.min(Number(maxPages) || Infinity, Math.ceil((primary?.body?.totalRecords || 0) / pageSize));
  for (let page = 2; pageSize && page <= totalPages; page += 1) {
    const nextUrl = new URL(primary.url);
    nextUrl.searchParams.set('page', String(page));
    nextUrl.searchParams.set('orderBy', 'windowVolume desc');
    const expression = `fetch(${JSON.stringify(nextUrl.toString())}, {method:'POST', credentials:'include'}).then(async r => ({status:r.status, body:await r.json()}))`;
    const next = await send('Runtime.evaluate', {expression, awaitPromise: true, returnByValue: true}, sessionId);
    if (next.result?.value?.status !== 200 || !next.result?.value?.body) throw new Error(`Similarweb page ${page} returned an invalid response`);
    out.push({url: nextUrl.toString(), status: 200, body: next.result.value.body});
  }
  if (process.env.SIMILARWEB_CDP_DEBUG === '1') {
    const state = await send('Runtime.evaluate', {expression: 'JSON.stringify({url:location.href,title:document.title,text:(document.body?.innerText||"").slice(0,2000)})', returnByValue: true}, sessionId);
    process.stdout.write(JSON.stringify({entries: out, requestUrls: capture.urls, state: JSON.parse(state.result?.value || '{}')}));
  } else {
    process.stdout.write(JSON.stringify(out));
  }
} finally {
  capture?.dispose();
  if (targetId) await send('Target.closeTarget', {targetId}).catch(() => {});
  for (const call of pending.values()) call.reject(new Error('Similarweb capture closed'));
  pending.clear();
  socket.close();
}
