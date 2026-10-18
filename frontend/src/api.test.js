import test from 'node:test';
import assert from 'node:assert/strict';
import {getJob, getJobProgress, login, streamChat, streamJobOutput} from './api.js';
import {readSse} from './utils/sse.js';

function setup(t) {
  const storage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
  const window = Object.getOwnPropertyDescriptor(globalThis, 'window');
  let cleared = false;
  Object.defineProperty(globalThis, 'localStorage', {configurable:true, value:{getItem:()=> 'test', removeItem:()=> {cleared=true;}}});
  Object.defineProperty(globalThis, 'window', {configurable:true, value:{location:{hash:''}}});
  t.after(() => {
    if (storage) Object.defineProperty(globalThis, 'localStorage', storage); else delete globalThis.localStorage;
    if (window) Object.defineProperty(globalThis, 'window', window); else delete globalThis.window;
  });
  return () => cleared;
}

test('progress polling downloads full details only after terminal state', async t => {
  setup(t);
  let status = 'running';
  const calls = [];
  t.mock.method(globalThis, 'fetch', async url => {
    calls.push(url);
    return new Response(JSON.stringify(url.endsWith('/progress') ? {job_id:'job',status} : {job_id:'job',status,output_log:'complete log',result_artifacts:[{report_type:'packages'}]}));
  });
  const running = await getJobProgress('job');
  assert.equal(running.status, 'running');
  assert.deepEqual(calls, ['/api/v2/jobs/job/progress']);
  status = 'partial';
  const complete = await getJobProgress('job');
  assert.equal(complete.output_log, 'complete log');
  assert.equal(complete.result_artifacts.length, 1);
  assert.deepEqual(calls.slice(1), ['/api/v2/jobs/job/progress', '/api/v2/jobs/job']);
});

test('login preserves invalid credential errors instead of reporting an expired session', async t => {
  const cleared = setup(t);
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({detail:'Invalid username or password'}), {status:401}));
  await assert.rejects(login('admin','wrong'), error => error.status===401 && error.message==='Invalid username or password');
  assert.equal(cleared(),false);
});

test('request deadline includes reading a slow response body', async t => {
  setup(t);
  let expire;
  t.mock.method(globalThis, 'setTimeout', fn => {expire=fn;return 1;});
  t.mock.method(globalThis, 'clearTimeout', () => {});
  t.mock.method(globalThis, 'fetch', async (url, {signal}) => ({ok:true,status:200,json:()=>new Promise((resolve,reject) => {
    signal.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError')));
  })}));
  const request = getJob('slow');
  await Promise.resolve();
  expire();
  await assert.rejects(request, /timed out/);
});

test('SSE parser preserves multiline UTF-8 events at every byte boundary', async () => {
  const bytes = new TextEncoder().encode(':heartbeat\r\nevent: content\r\ndata: café\r\ndata: second line\r\n\r\nevent: done\r\ndata: success\r\n\r\n');
  const response = new Response(new ReadableStream({start(controller) {
    for (const byte of bytes) controller.enqueue(Uint8Array.of(byte));
    controller.close();
  }}));
  const events=[];
  for await (const event of readSse(response)) events.push(event);
  assert.deepEqual(events,[{type:'content',data:'café\nsecond line'},{type:'done',data:'success'}]);
  assert.equal(response.body.locked,false);
});

test('job completion closes the reader without waiting for the connection to close', async t => {
  setup(t);
  let cancelled=false, completed=null;
  const lines=[];
  const response = new Response(new ReadableStream({start(controller) {
    controller.enqueue(new TextEncoder().encode('data: first\ndata: second\n\nevent: done\ndata: success\n\n'));
  },cancel(){cancelled=true;}}));
  t.mock.method(globalThis,'fetch',async()=>response);
  await streamJobOutput('job',{onLine:line=>lines.push(line),onDone:status=>completed=status,onError:error=>assert.fail(error)});
  assert.deepEqual(lines,['first','second']);
  assert.equal(completed,'success');assert.equal(cancelled,true);assert.equal(response.body.locked,false);
});

test('truncated chat reports an error instead of a successful completion', async t => {
  setup(t);
  t.mock.method(globalThis,'fetch',async()=>new Response('data: {"type":"content","content":"Partial"}\n\n'));
  let completed=false,error,content='';
  await streamChat([{role:'user',content:'test'}],{onContent:text=>content+=text,onDone:()=>completed=true,onError:caught=>error=caught});
  assert.equal(content,'Partial');assert.equal(completed,false);assert.match(error.message,/disconnected before completion/);
});

test('chat errors cancel and unlock the stream', async t => {
  setup(t);
  let cancelled=false,error;
  const response=new Response(new ReadableStream({start(controller){controller.enqueue(new TextEncoder().encode('data: {"type":"error","message":"Provider failed"}\n\n'));},cancel(){cancelled=true;}}));
  t.mock.method(globalThis,'fetch',async()=>response);
  await streamChat([{role:'user',content:'test'}],{onError:caught=>error=caught});
  assert.equal(error.message,'Provider failed');assert.equal(cancelled,true);assert.equal(response.body.locked,false);
});
