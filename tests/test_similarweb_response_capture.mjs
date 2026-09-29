import test from 'node:test';
import assert from 'node:assert/strict';
import {similarwebCapture} from '../keyword_loop/core/clients/similarweb_response_capture.mjs';
const url='https://sim.3ue.co/api/KeywordGenerator/google/suggest?type=Broad&rangeFilter=correct';
const event=(method,params)=>({sessionId:'s',method:'Network.'+method,params});
test('waits for complete filtered primary body and accepts empty records',async()=>{
  let reads=0;
  const c=similarwebCapture(async()=>{reads++;return {body:'{"records":[],"totalRecords":0}'};},'s',{fragment:'/api/KeywordGenerator/google/suggest',range:'correct'},()=>{throw Error('unexpected fallback');});
  try {
    await c.onEvent(event('responseReceived',{requestId:'a',response:{url,status:200}}));
    assert.equal(reads,0);
    await c.onEvent(event('loadingFinished',{requestId:'a'}));
    assert.deepEqual((await c.result).body.records,[]);
    assert.equal(reads,1);
  } finally {c.dispose();}
});
test('ignores stale filters and other sessions; decodes base64',async()=>{
  let reads=0;
  const c=similarwebCapture(async()=>{reads++;return {base64Encoded:true,body:Buffer.from('{"records":[{"keyword":"ok"}]}').toString('base64')};},'s',{fragment:'/suggest',range:'correct'},async()=>{});
  try {
    await c.onEvent({...event('responseReceived',{requestId:'foreign',response:{url,status:200}}),sessionId:'other'});
    await c.onEvent(event('responseReceived',{requestId:'stale',response:{url:url.replace('correct','stale'),status:200}}));
    await c.onEvent(event('loadingFinished',{requestId:'stale'}));
    assert.equal(reads,0);
    await c.onEvent(event('responseReceived',{requestId:'good',response:{url,status:200}}));
    await c.onEvent(event('loadingFinished',{requestId:'good'}));
    assert.equal((await c.result).body.records[0].keyword,'ok');
  } finally {c.dispose();}
});
test('auxiliary-only response triggers one primary fallback',async()=>{
  let calls=0;
  const c=similarwebCapture(async()=>({body:'{"records":[]}'}),'s',{fragment:'/suggest',range:'correct'},async seed=>{
    calls++;assert.ok(seed.includes('label=Trending'));return {url,body:{records:[{keyword:'main'}]}};
  });
  try {
    await c.onEvent(event('responseReceived',{requestId:'aux',response:{url:url+'&label=Trending',status:200}}));
    await c.onEvent(event('loadingFinished',{requestId:'aux'}));
    assert.equal((await c.result).body.records[0].keyword,'main');
    assert.equal(calls,1);
  } finally {c.dispose();}
});
test('invalid response times out with diagnostic rather than empty success',async()=>{
  const c=similarwebCapture(async()=>({body:'{"error":"failed"}'}),'s',{fragment:'/suggest',range:'correct',timeoutMs:20},async()=>{});
  try {
    await c.onEvent(event('responseReceived',{requestId:'bad',response:{url,status:200}}));
    await c.onEvent(event('loadingFinished',{requestId:'bad'}));
    await assert.rejects(c.result,/records/);
  } finally {c.dispose();}
});
