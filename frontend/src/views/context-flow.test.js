import test from 'node:test';
import assert from 'node:assert/strict';
import {h} from 'vue';
import {createRouter, createMemoryHistory, RouterView} from 'vue-router';
import {element, renderer, flush, compileView} from '../../test-support/vue.js';

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
