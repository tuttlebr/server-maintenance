import test from 'node:test';
import assert from 'node:assert/strict';
import {h} from 'vue';
import {createRouter, createMemoryHistory, RouterView} from 'vue-router';
import {element, renderer, flush, compileView, find, text} from '../../test-support/vue.js';

const {default: ContextManagement} = await import(await compileView(new URL('./ContextManagement.vue', import.meta.url)));

test('a context status response after navigation cannot restart background polling', async t => {
  const originalStorage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
  Object.defineProperty(globalThis, 'localStorage', {configurable: true, value: {getItem: () => 'test'}});
  t.after(() => {
    if (originalStorage) Object.defineProperty(globalThis, 'localStorage', originalStorage);
    else delete globalThis.localStorage;
  });
  let release, statusRequested = false;
  const pendingStatus = new Promise(resolve => { release = resolve; });
  t.mock.method(globalThis, 'fetch', async url => {
    if (url.endsWith('/context/status')) {
      statusRequested = true;
      await pendingStatus;
      return new Response(JSON.stringify({running: true}));
    }
    return new Response('[]');
  });
  const originalTimeout = globalThis.setTimeout;
  const polls = [];
  t.mock.method(globalThis, 'setTimeout', (callback, delay, ...args) => {
    const timer = originalTimeout(callback, delay, ...args);
    if (delay === 1500) polls.push(timer);
    return timer;
  });
  t.after(() => polls.forEach(clearTimeout));
  const router = createRouter({history: createMemoryHistory(), routes: [
    {path: '/context', component: ContextManagement},
    {path: '/', component: {render: () => null}},
  ]});
  await router.push('/context');
  await router.isReady();
  const app = renderer.createApp({render: () => h(RouterView)}).use(router);
  app.mount(element('root'));
  t.after(() => app.unmount());
  try {
    await flush();
    assert.equal(statusRequested, true);
    await router.push('/');
  } finally {
    release();
  }
  await flush();
  assert.equal(polls.length, 0);
});

test('a transient status failure does not stop an ongoing reindex poll', async t => {
  const originalStorage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
  const originalWindow = Object.getOwnPropertyDescriptor(globalThis, 'window');
  Object.defineProperty(globalThis, 'localStorage', {configurable:true, value:{getItem:()=> 'test'}});
  Object.defineProperty(globalThis, 'window', {configurable:true, value:{location:{hash:''}}});
  t.after(() => {
    if (originalStorage) Object.defineProperty(globalThis, 'localStorage', originalStorage); else delete globalThis.localStorage;
    if (originalWindow) Object.defineProperty(globalThis, 'window', originalWindow); else delete globalThis.window;
  });
  const polls = new Map();
  const realTimeout = globalThis.setTimeout, realClear = globalThis.clearTimeout;
  t.mock.method(globalThis, 'setTimeout', (callback, delay, ...args) => {
    if (delay !== 1500) return realTimeout(callback, delay, ...args);
    const id = {}; polls.set(id, callback); return id;
  });
  t.mock.method(globalThis, 'clearTimeout', id => {polls.delete(id); realClear(id);});
  let statusRequests = 0;
  t.mock.method(globalThis, 'fetch', async url => {
    if (url.endsWith('/context/status')) {
      statusRequests++;
      if (statusRequests === 2) throw new Error('Temporary disconnect');
      return new Response(JSON.stringify({running:statusRequests < 3}));
    }
    return new Response('[]');
  });
  const router = createRouter({history:createMemoryHistory(),routes:[{path:'/context',component:ContextManagement}]});
  await router.push('/context'); await router.isReady();
  const app = renderer.createApp(ContextManagement).use(router);
  app.mount(element('root')); t.after(()=> app.unmount()); await flush();
  assert.equal(polls.size, 1);
  for (let attempt=0; attempt<2; attempt++) {
    const [id, callback] = polls.entries().next().value;
    polls.delete(id); await callback(); await flush();
    assert.equal(polls.size, attempt === 0 ? 1 : 0);
  }
  assert.ok(statusRequests >= 3);
});

async function uploadHarness(t) {
  const originals = Object.fromEntries(['localStorage','window','XMLHttpRequest'].map(key=>[key,Object.getOwnPropertyDescriptor(globalThis,key)]));
  Object.defineProperty(globalThis,'localStorage',{configurable:true,value:{getItem:()=> 'test'}});
  Object.defineProperty(globalThis,'window',{configurable:true,value:{location:{hash:''}}});
  let xhr;
  class UploadRequest {
    constructor() { xhr=this; this.upload={}; }
    open() {} setRequestHeader() {} send() {}
  }
  Object.defineProperty(globalThis,'XMLHttpRequest',{configurable:true,value:UploadRequest});
  t.after(()=>{for(const [key,value] of Object.entries(originals)) { if(value) Object.defineProperty(globalThis,key,value); else delete globalThis[key]; }});
  let progress={phase:'parsing',completed:1,total:3,elapsed_seconds:8,seconds_since_last_page:2};
  let failPoll=false, releasePoll;
  const polls=new Map();
  const realTimeout=globalThis.setTimeout, realClear=globalThis.clearTimeout;
  t.mock.method(globalThis,'setTimeout',(callback,delay,...args)=>{
    if(delay!==1000) return realTimeout(callback,delay,...args);
    const id={};polls.set(id,callback);return id;
  });
  t.mock.method(globalThis,'clearTimeout',id=>{polls.delete(id);realClear(id);});
  t.mock.method(globalThis,'fetch',async url=>{
    if(url.endsWith('/context/status')) return new Response(JSON.stringify({parser_enabled:true,parser_timeout_seconds:100}));
    if(url.endsWith('/context/uploads')) return new Response('{"upload_id":"upload-id","parser_timeout_seconds":1800}',{status:201});
    if(url.endsWith('/context/uploads/upload-id')) {
      if(releasePoll) await new Promise(resolve=>{releasePoll.resolve=resolve;});
      if(failPoll) throw new Error('Connection interrupted');
      return new Response(JSON.stringify(progress));
    }
    return new Response('[]');
  });
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/context',component:ContextManagement}]});
  await router.push('/context');await router.isReady();
  const app=renderer.createApp(ContextManagement).use(router), root=element('root');
  app.mount(root); t.after(()=>app.unmount()); await flush();
  const file=new Blob(['PDF data'],{type:'application/pdf'});
  find(root,n=>n.props.id==='context-file').props.onChange({target:{files:[file]}});
  const pending=find(root,n=>n.tag==='form').props.onSubmit({preventDefault(){}});
  await flush();
  return {root, app, pending, polls, get xhr(){return xhr;}, setProgress:value=>{progress=value;}, fail:value=>{failPoll=value;}, hold:()=>{releasePoll={};return releasePoll;}, poll:async()=>{
    const [id,callback]=polls.entries().next().value;polls.delete(id);await callback();await flush();
  }};
}

test('upload shows measured stages, survives a polling failure, and confirms saving',async t=>{
  const h=await uploadHarness(t);
  assert.equal(h.xhr.timeout,1_920_000);
  h.xhr.upload.onprogress({loaded:512,total:1024,lengthComputable:true});await flush();
  assert.match(text(h.root),/512 B \/ 1.0 KB transferred/);
  assert.equal(find(h.root,n=>n.tag==='progress').props.value,50);
  h.xhr.upload.onload();await flush();
  assert.match(text(h.root),/Waiting for server/);
  assert.equal(find(h.root,n=>n.tag==='progress').props.value,undefined);
  await h.poll();
  assert.match(text(h.root),/1 of 3 pages complete; processing page 2/);
  assert.match(text(h.root),/Last page completed 2s ago/);
  h.fail(true);await h.poll();
  assert.match(text(h.root),/Progress updates unavailable/);
  assert.match(text(h.root),/1 of 3 pages complete/);
  assert.equal(h.polls.size,1);
  h.fail(false);h.setProgress({phase:'saving',completed:0,total:0,elapsed_seconds:12,seconds_since_last_page:0});await h.poll();
  assert.match(text(h.root),/Saving document/);
  assert.doesNotMatch(text(h.root),/Document saved/);
  h.xhr.status=201;h.xhr.responseText='{"id":7}';h.xhr.onload();await h.pending;await flush();
  assert.match(text(h.root),/Document saved/);
  assert.match(text(h.root),/Re-index to make this document searchable/);
  assert.equal(h.polls.size,0);
});

test('a parser failure keeps the page error visible and never shows success',async t=>{
  const h=await uploadHarness(t);
  h.setProgress({phase:'failed',error:'Parser request timed out for page 15. No document was saved.'});
  h.xhr.status=502;h.xhr.responseText=JSON.stringify({detail:'Parser request timed out for page 15. No document was saved.'});h.xhr.onload();
  await h.pending;await flush();
  assert.match(text(h.root),/Upload failed/);
  assert.match(text(h.root),/page 15/);
  assert.doesNotMatch(text(h.root),/Document saved/);
  assert.equal(h.polls.size,0);
});

test('a late upload status response after navigation cannot restart polling',async t=>{
  const h=await uploadHarness(t), held=h.hold();
  const pendingPoll=h.poll();await flush();
  h.app.unmount();held.resolve();await pendingPoll;
  assert.equal(h.polls.size,0);
  h.xhr.status=201;h.xhr.responseText='{"id":7}';h.xhr.onload();await h.pending;
  assert.equal(h.polls.size,0);
});

test('a lost upload response can still confirm the saved document from status',async t=>{
  const h=await uploadHarness(t);
  h.setProgress({phase:'complete',document_id:7,elapsed_seconds:12});
  h.xhr.onerror();await h.pending;await flush();
  assert.match(text(h.root),/Document saved/);
  assert.doesNotMatch(text(h.root),/Upload failed/);
  assert.equal(h.polls.size,0);
});

test('a proxy timeout does not claim failure when the parser is still running',async t=>{
  const h=await uploadHarness(t);
  h.xhr.status=504;h.xhr.responseText='{}';h.xhr.onload();await h.pending;await flush();
  assert.match(text(h.root),/Upload status unconfirmed/);
  assert.doesNotMatch(text(h.root),/Upload failed/);
});
