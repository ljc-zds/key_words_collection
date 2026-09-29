// Executed inside the logged-in Trends page. Widget tokens stay in this scope.
async function trendsWidget(terms, timeframe, identifier, path, timeoutMs, pauseMs) {
  async function request(endpoint, params) {
    let response;
    try {
      response = await fetch('/trends/api/' + endpoint + '?' + new URLSearchParams(params), {
        credentials: 'same-origin', signal: AbortSignal.timeout(timeoutMs),
      });
    } catch (_) {
      throw { message: 'Trends request failed or timed out: ' + endpoint };
    }
    if (!response.ok) {
      const retry = response.headers.get('retry-after');
      const seconds = retry === null ? 0 : (/^\d+$/.test(retry) ? Number(retry) : Math.max(0, (Date.parse(retry) - Date.now()) / 1000));
      throw { message: 'Trends HTTP ' + response.status + ': ' + endpoint,
        status: response.status, retryAfter: Number.isFinite(seconds) ? seconds : 0 };
    }
    const text = await response.text();
    try {
      return JSON.parse(text.replace(/^\)\]\}'[^\n]*\n/, ''));
    } catch (_) {
      throw { message: 'Trends returned invalid JSON: ' + endpoint };
    }
  }
  try {
    const explore = await request('explore', { hl: 'en-US', tz: '0', req: JSON.stringify({
      comparisonItem: terms.map(keyword => ({keyword, geo: '', time: timeframe})),
      category: 0, property: '',
    }) });
    const widget = explore.widgets?.find(w => w.id === identifier);
    if (!widget?.request || !widget.token) throw { message: 'Trends missing widget: ' + identifier };
    await new Promise(resolve => setTimeout(resolve, pauseMs));
    const data = await request('widgetdata/' + path, {
      hl: 'en-US', tz: '0', req: JSON.stringify(widget.request), token: widget.token,
    });
    return { data };
  } catch (error) {
    return { error: error.message || 'Trends browser request failed', status: error.status || 0,
      retryAfter: error.retryAfter || 0 };
  }
}
