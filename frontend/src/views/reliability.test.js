import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'vite';
import {createSSRApp} from 'vue';
import {renderToString} from '@vue/server-renderer';
import {createRouter, createMemoryHistory} from 'vue-router';

// Exercise actual Vue setup functions as well as compilation. In particular,
// reactive watchers must not access target selection before it is initialized.
test('maintenance views initialize with empty fleet data', async () => {
  const server = await createServer({server:{middlewareMode:true,hmr:false,ws:false}, appType:'custom'});
  try {
    for (const [name, expected] of [['Operations', 'Run checks and maintenance on your selected devices'], ['UserManagement', 'Loading users and devices'], ['JobHistory', 'Activity']]) {
      const {default: component} = await server.ssrLoadModule(`/src/views/${name}.vue`);
      const router=createRouter({history:createMemoryHistory(),routes:[{path:'/',component}]});
      await router.push('/'); await router.isReady();
      const html=await renderToString(createSSRApp(component).use(router));
      assert.ok(html.includes(expected), `${name} should render its initial UI`);
      if (name === 'JobHistory') assert.match(html, /<option value="partial"[^>]*>Partial<\/option>/);
    }
  } finally { await server.close(); }
});

test('Partial badge renders as a completed warning with an explanation', async () => {
  const server = await createServer({server:{middlewareMode:true,hmr:false,ws:false}, appType:'custom'});
  try {
    const {default: badge} = await server.ssrLoadModule('/src/components/StatusBadge.vue');
    const html = await renderToString(createSSRApp(badge, {status:'partial',withTooltip:true}));
    assert.match(html, /badge-orange/);
    assert.match(html, /dot-orange/);
    assert.match(html, /Partial/);
    assert.match(html, /Some, but not all, devices completed successfully/);
    assert.doesNotMatch(html, /badge-active|dot-pulse/);
  } finally { await server.close(); }
});
