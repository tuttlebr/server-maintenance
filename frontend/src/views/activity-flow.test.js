import test from 'node:test';
import assert from 'node:assert/strict';
import {createRouter, createMemoryHistory} from 'vue-router';
import {element, renderer, text, find, flush, compileView} from '../../test-support/vue.js';

const {default: Activity} = await import(await compileView(new URL('./JobHistory.vue', import.meta.url)));

async function mount(t, {status = 'running', query = {job:'job'}} = {}) {
  const originalStorage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
  const originalWindow = Object.getOwnPropertyDescriptor(globalThis, 'window');
  Object.defineProperty(globalThis, 'localStorage', {configurable:true, value:{getItem:()=> 'test'}});
  Object.defineProperty(globalThis, 'window', {configurable:true, value:{location:{hash:''}}});
  t.after(() => {
    if (originalStorage) Object.defineProperty(globalThis, 'localStorage', originalStorage); else delete globalThis.localStorage;
    if (originalWindow) Object.defineProperty(globalThis, 'window', originalWindow); else delete globalThis.window;
  });
  let current = status;
  const calls = [], timers = new Map();
  const realTimeout = globalThis.setTimeout, realClear = globalThis.clearTimeout;
  t.mock.method(globalThis, 'setTimeout', (callback, delay, ...args) => {
    if (delay !== 5000) return realTimeout(callback, delay, ...args);
    const id = {};
    timers.set(id, callback);
    return id;
  });
  t.mock.method(globalThis, 'clearTimeout', id => {timers.delete(id); realClear(id);});
  const job = () => ({job_id:'job',playbook:'host_facts.yml',status:current,target_devices:'node',result_artifacts:[],device_results:[],created_at:new Date().toISOString()});
  t.mock.method(globalThis, 'fetch', async url => {
    calls.push(url);
    if (url.endsWith('/stream')) return new Response('data: streamed prefix\n\n'); // interrupted connection
    if (url.startsWith('/api/v2/jobs?')) return new Response(JSON.stringify([job()]));
    if (url.endsWith('/progress')) return new Response(JSON.stringify(job()));
    return new Response(JSON.stringify({...job(),output_log:current === 'running' ? '' : 'saved prefix\nFINAL RESULT'}));
  });
  const router = createRouter({history:createMemoryHistory(),routes:[{path:'/activity',component:Activity},{path:'/',component:{render:()=>null}}]});
  await router.push({path:'/activity',query}); await router.isReady();
  const app = renderer.createApp(Activity).use(router), root = element('root');
  app.mount(root); t.after(()=> app.unmount()); await flush();
  async function poll() {
    const [id, callback] = timers.entries().next().value;
    timers.delete(id);
    await callback(); await flush();
  }
  return {root,router,calls,timers,poll,setStatus(value){current=value;}};
}

test('polling recovers the final log after a disconnected stream and stops downloading finished details', async t => {
  const view = await mount(t);
  assert.match(find(view.root, node => node.props.innerHTML)?.props.innerHTML || '', /streamed prefix/);
  view.setStatus('success');
  await view.poll();
  assert.match(find(view.root, node => node.props.innerHTML)?.props.innerHTML || '', /FINAL RESULT/);
  const detailRequests = view.calls.filter(url => url === '/api/v2/jobs/job').length;
  await view.poll();
  assert.equal(view.calls.filter(url => url === '/api/v2/jobs/job').length, detailRequests);
  assert.equal(view.calls.filter(url => url.endsWith('/progress')).length, 1);
});

test('changing an Activity filter resets pagination and uses the selected backend filter', async t => {
  const view = await mount(t, {status:'success',query:{page:'3'}});
  const filter = find(view.root, node => node.props.id === 'job-filter-status');
  filter.props['onUpdate:modelValue']('adverse'); await flush();
  assert.equal(view.router.currentRoute.value.query.page, undefined);
  const url = view.calls.filter(url => url.startsWith('/api/v2/jobs?')).at(-1);
  assert.equal(new URL(url, 'http://test').searchParams.get('offset'), '0');
  assert.equal(new URL(url, 'http://test').searchParams.get('status'), 'adverse');
  assert.match(text(view.root), /50 adverse jobs/);
});
