import test from 'node:test';
import assert from 'node:assert/strict';
import {keywordCapture} from '../keyword_loop/core/clients/semrush_response_capture.mjs';

const event = (method, requestId, extra = {}) => ({sessionId: 'test', method: 'Network.' + method, params: {requestId, ...extra}});
const headers = id => event('responseReceived', id, {response: {url: 'https://sem.3ue.co/kmtgw/v2/webapi', status: 200}});

test('HTTP 200 report limit is an explicit failure, never an empty keyword result', async () => {
  const capture = keywordCapture(async () => ({body: '{"jsonrpc":"2.0","error":{"code":-2004,"message":"Report limit reached"}}'}), 'test', 30);
  try {
    await capture.onEvent(headers('quota'));
    await capture.onEvent(event('loadingFinished', 'quota'));
    await assert.rejects(capture.result, /SEMRUSH_REPORT_LIMIT/);
  } finally {capture.dispose();}
});

test('headers do not read body; loadingFinished resolves even empty results', async () => {
  const calls = [];
  const capture = keywordCapture(async (...args) => {calls.push(args); return {body: '{"result":{"keywords":[]}}'};}, 'test');
  try {
    await capture.onEvent(headers('a'));
    assert.equal(calls.length, 0);
    await capture.onEvent({...event('loadingFinished', 'a'), sessionId: 'other'});
    assert.equal(calls.length, 0);
    await capture.onEvent(event('loadingFinished', 'a'));
    assert.deepEqual(await capture.result, {keywords: []});
    assert.equal(calls.length, 1);
  } finally {capture.dispose();}
});

test('unrelated RPC is ignored and base64 keyword body is decoded', async () => {
  const capture = keywordCapture(async (_, {requestId}) => requestId === 'a'
    ? {body: '{"result":{"topics":[]}}'}
    : {base64Encoded: true, body: Buffer.from('{"result":{"keywords":[{"phrase":"test"}]}}').toString('base64')}, 'test');
  try {
    for (const id of ['a', 'b']) {
      await capture.onEvent(headers(id));
      await capture.onEvent(event('loadingFinished', id));
    }
    assert.equal((await capture.result).keywords[0].phrase, 'test');
  } finally {capture.dispose();}
});

test('body errors are included in capture timeout', async () => {
  const capture = keywordCapture(async () => {throw new Error('body unavailable');}, 'test', 20);
  try {
    await capture.onEvent(headers('a'));
    await capture.onEvent(event('loadingFinished', 'a'));
    await assert.rejects(capture.result, /body unavailable/);
  } finally {capture.dispose();}
});
