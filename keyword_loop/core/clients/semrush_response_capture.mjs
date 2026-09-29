// Read response bodies only after Chrome reports the download complete.
export function keywordCapture(send, sessionId, timeoutMs = 30000, expected = null) {
  const requests = new Set();
  const templates = new Map();
  let template;
  let lastError = '';
  let settled = false;
  let resolveResult;
  let rejectResult;
  const result = new Promise((resolve, reject) => { resolveResult = resolve; rejectResult = reject; });
  result.catch(() => {}); // Navigation can still be pending when capture times out.
  const timer = setTimeout(() => {
    settled = true;
    rejectResult(new Error(`Semrush keyword JSON was not captured${lastError ? ': ' + lastError : ''}`));
  }, timeoutMs);
  async function onEvent(message) {
    if (settled || message.sessionId !== sessionId) return;
    const params = message.params || {};
    if (message.method === 'Network.requestWillBeSent' && params.request.url.includes('/kmtgw/v2/webapi')) {
      try {
        const data = params.request.postData || (await send('Network.getRequestPostData', {requestId:params.requestId}, sessionId)).postData;
        const body = JSON.parse(data);
        if (body.method === 'ideas.GetKeywords' && (!expected ||
            (body.params.phrase === expected.keyword && body.params.database === expected.database))) {
          templates.set(params.requestId, {url:params.request.url, body});
        }
      } catch {}
      return;
    }
    if (message.method === 'Network.responseReceived') {
      if (params.response.url.includes('/kmtgw/v2/webapi')) {
        if (params.response.status === 200) requests.add(params.requestId);
        else lastError = `HTTP ${params.response.status}`;
      }
      return;
    }
    if (!requests.has(params.requestId)) return;
    if (message.method === 'Network.loadingFailed') {
      requests.delete(params.requestId);
      lastError = params.errorText || 'download failed';
      return;
    }
    if (message.method !== 'Network.loadingFinished') return;
    requests.delete(params.requestId);
    try {
      const body = await send('Network.getResponseBody', {requestId: params.requestId}, sessionId);
      const parsed = JSON.parse(body.base64Encoded ? Buffer.from(body.body, 'base64').toString('utf8') : body.body);
      if (expected && !templates.has(params.requestId)) return;
      if (!settled && parsed?.error?.code === -2004) {
        settled = true;
        clearTimeout(timer);
        rejectResult(new Error('SEMRUSH_REPORT_LIMIT: -2004 Report limit reached'));
        return;
      }
      if (parsed?.error) lastError = `RPC error ${parsed.error.code}`;
      if (!settled && Array.isArray(parsed?.result?.keywords)) {
        template = templates.get(params.requestId);
        settled = true;
        clearTimeout(timer);
        resolveResult(parsed.result);
      }
    } catch (error) {
      lastError = error.message;
    }
  }
  return {result, onEvent, getTemplate() {return template;}, dispose() { settled = true; clearTimeout(timer); requests.clear(); templates.clear(); }};
}
