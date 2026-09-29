import test from 'node:test';
import assert from 'node:assert/strict';
import {paginateKeywords} from '../keyword_loop/core/clients/semrush_pagination.mjs';

const request = {method:'ideas.GetKeywords', params:{phrase:'seed',database:'us',filter:{difficulty:[{value:59}]},order:{field:'similarity_score'},page:{number:1,size:2}}};
test('zero cap fetches until empty page', async()=>{
  const result = await paginateKeywords(request,{keywords:[{phrase:'a'},{phrase:'b'}]},0,async body=>({keywords:body.params.page.number===2 ? [{phrase:'c'},{phrase:'d'}] : []}));
  assert.equal(result.keywords.length,4);
  assert.equal(result.pages_fetched,3);
});
test('pages preserve filter and order, deduplicate, and respect cap', async()=>{
  const calls=[];
  const result=await paginateKeywords(request,{keywords:[{phrase:'a'},{phrase:'b'}]},5,async body=>{
    calls.push(body);
    return {keywords:body.params.page.number===2 ? [{phrase:'b'},{phrase:'c'}] : [{phrase:'d'},{phrase:'e'}]};
  });
  assert.deepEqual(calls.map(x=>x.params.page.number),[2,3]);
  assert.deepEqual(calls[0].params.filter,request.params.filter);
  assert.deepEqual(calls[0].params.order,request.params.order);
  assert.equal(request.params.page.number,1);
  assert.deepEqual(result.keywords.map(x=>x.phrase),['a','b','c','d','e']);
});
test('short first page does not request another page', async()=>{
  await paginateKeywords(request,{keywords:[{phrase:'a'}]},5,()=>{throw Error('unexpected page');});
});
test('repeated full page and failed page are not successful completion', async()=>{
  const first={keywords:[{phrase:'a'},{phrase:'b'}]};
  await assert.rejects(paginateKeywords(request,first,5,async()=>first),/repeated/);
  await assert.rejects(paginateKeywords(request,first,5,async()=>{throw Error('HTTP 403');}),/403/);
});
