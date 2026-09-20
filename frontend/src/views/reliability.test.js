import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'vite';
import {createSSRApp} from 'vue';
import {renderToString} from '@vue/server-renderer';
import {createRouter, createMemoryHistory} from 'vue-router';

// Exercise actual Vue setup functions as well as compilation. In particular,
// reactive watchers must not access target selection before it is initialized.
test('maintenance views initialize with empty fleet data', async () => {
  const server = await createServer({server:{middlewareMode:true}, appType:'custom'});
  try {
    for (const [name, expected] of [['Operations', 'Choose an action'], ['UserManagement', 'Target devices'], ['JobHistory', 'Activity']]) {
      const {default: component} = await server.ssrLoadModule(`/src/views/${name}.vue`);
      const router=createRouter({history:createMemoryHistory(),routes:[{path:'/',component}]});
      await router.push('/'); await router.isReady();
      const html=await renderToString(createSSRApp(component).use(router));
      assert.ok(html.includes(expected), `${name} should render its initial UI`);
    }
  } finally { await server.close(); }
});
