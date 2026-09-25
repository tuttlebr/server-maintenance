import test from 'node:test';
import assert from 'node:assert/strict';
import { createPinia, setActivePinia } from 'pinia';
import { useDevicesStore } from './devices.js';

function setup(t, respond) {
  const originalFetch = globalThis.fetch, originalStorage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
  Object.defineProperty(globalThis, 'localStorage', {configurable:true, value:{getItem:() => 'test-only'}});
  globalThis.fetch = async url => respond(new URL(url,'http://test.local'));
  setActivePinia(createPinia());
  const store = useDevicesStore();
  t.after(() => { store.stop(); store.$dispose(); globalThis.fetch = originalFetch; if (originalStorage === undefined) delete globalThis.localStorage; else Object.defineProperty(globalThis, 'localStorage', originalStorage); });
  return store;
}
const json = (data,status=200) => new Response(JSON.stringify(data),{status,headers:{'content-type':'application/json'}});
const defaults = url => json(url.pathname.endsWith('/devices') ? [{id:1,name:'node-1'}] : url.pathname.endsWith('/summary') ? {active_count:0} : []);

test('jobs failure does not erase or hide a successful device observation', async t => {
  const store = setup(t,url => url.pathname.endsWith('/jobs') ? json({detail:'Unavailable'},503) : defaults(url));
  await store.refresh();
  assert.equal(store.hasLoadedOnce,true); assert.equal(store.devices[0].name,'node-1');
  assert.equal(store.deviceError,null); assert.ok(store.jobsError); assert.ok(store.lastUpdated);
  assert.equal(store.activeJobCount,null);
});
test('initial device failure is unavailable, not a successfully loaded empty fleet', async t => {
  const store=setup(t,url => url.pathname.endsWith('/devices') ? json({detail:'Unavailable'},503) : defaults(url));
  await store.refresh();
  assert.equal(store.hasLoadedOnce,false); assert.equal(store.lastUpdated,null); assert.ok(store.deviceError);
  assert.ok(store.jobsUpdated); assert.equal(store.activeJobCount,0);
});
test('later failures retain previous data and timestamps; recovery clears the error', async t => {
  let fail=false;
  const store=setup(t,url => fail ? json({detail:'Unavailable'},503) : defaults(url));
  await store.refresh(); const observed=store.lastUpdated;
  fail=true; await store.refresh();
  assert.equal(store.devices.length,1); assert.equal(store.lastUpdated,observed); assert.equal(store.hasLoadedOnce,true); assert.ok(store.deviceError);
  fail=false; await store.refresh(); assert.equal(store.error,null);
});
test('concurrent refresh requests coalesce, including force callers', async t => {
  let requests=0, release; const gate=new Promise(resolve => {release=resolve;});
  const store=setup(t,async url => {requests++; await gate; return defaults(url);});
  const first=store.refresh(), second=store.refresh({force:true});
  assert.equal(requests,6); release(); await Promise.all([first,second]); assert.equal(requests,6); assert.equal(store.loading,false);
});
