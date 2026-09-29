// Resolve when a complete, correctly filtered primary response is available.
export function similarwebCapture(send, sessionId, {fragment, range, timeoutMs=30000}, fallback) {
  const requests=new Map();
  const urls=[];
  let settled=false, fallbackStarted=false, lastError='';
  let resolveResult, rejectResult;
  const result=new Promise((resolve,reject)=>{resolveResult=resolve;rejectResult=reject;});
  result.catch(()=>{});
  const timer=setTimeout(()=>{
    settled=true;
    rejectResult(Error(`Similarweb primary JSON was not captured${lastError ? ': '+lastError : ''}`));
  },timeoutMs);
  function finish(entry) {
    if (!Array.isArray(entry?.body?.records)) throw Error('Missing records array');
    if (!settled) {settled=true;clearTimeout(timer);resolveResult(entry);}
  }
  async function onEvent(message) {
    if (settled || message.sessionId!==sessionId) return;
    const p=message.params||{};
    if (message.method==='Network.responseReceived' && p.response.url.includes(fragment)) {
      urls.push(p.response.url);
      if (p.response.status!==200) {lastError=`HTTP ${p.response.status}`;return;}
      const query=new URL(p.response.url).searchParams;
      const primary=query.get('type')==='Broad' && !query.has('label');
      if (primary && range && query.get('rangeFilter')!==range) return;
      requests.set(p.requestId,{url:p.response.url,primary});
      return;
    }
    const request=requests.get(p.requestId);
    if (!request) return;
    if (message.method==='Network.loadingFailed') {
      requests.delete(p.requestId);lastError=p.errorText||'Download failed';return;
    }
    if (message.method!=='Network.loadingFinished') return;
    requests.delete(p.requestId);
    try {
      const body=await send('Network.getResponseBody',{requestId:p.requestId},sessionId);
      const parsed=JSON.parse(body.base64Encoded ? Buffer.from(body.body,'base64').toString('utf8') : body.body);
      if (request.primary) finish({url:request.url,status:200,body:parsed});
      else if (!settled && !fallbackStarted && ![...requests.values()].some(r=>r.primary)) {
        fallbackStarted=true;
        finish(await fallback(request.url));
      }
    } catch(error) {lastError=error.message;}
  }
  return {result,onEvent,urls,dispose(){settled=true;clearTimeout(timer);requests.clear();}};
}
