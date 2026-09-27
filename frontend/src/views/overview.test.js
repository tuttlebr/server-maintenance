import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'vite';
import {createSSRApp} from 'vue';
import {renderToString} from '@vue/server-renderer';
import {createRouter, createMemoryHistory} from 'vue-router';
import {createPinia} from 'pinia';

test('Overview renders unavailable, first-run, partial-error, and ranked large-fleet states truthfully', async () => {
  const server = await createServer({server:{middlewareMode:true,hmr:false,ws:false}, appType:'custom'});
  try {
    const {default: component} = await server.ssrLoadModule('/src/views/Dashboard.vue');
    const {useDevicesStore} = await server.ssrLoadModule('/src/stores/devices.js');
    async function render(state) {
      const pinia=createPinia();
      const store=useDevicesStore(pinia); Object.assign(store,state);
      const router=createRouter({history:createMemoryHistory(),routes:[{path:'/',component},{path:'/:pathMatch(.*)*',component:{template:'<div />'}}]});
      await router.push('/'); await router.isReady();
      try { return await renderToString(createSSRApp(component).use(pinia).use(router)); }
      finally { store.$dispose(); }
    }
    const unavailable=await render({deviceError:new Error('503')});
    assert.match(unavailable,/Fleet state is unavailable/);
    assert.doesNotMatch(unavailable,/Connect your first device|No current device alerts/);
    const empty=await render({hasLoadedOnce:true,lastUpdated:'2026-09-25T12:00:00Z'});
    assert.match(empty,/Connect your first device/); assert.doesNotMatch(empty,/No current device alerts/);
    const devices=Array.from({length:200},(_,i)=>({id:i+1,name:`node-${String(i+1).padStart(3,'0')}`,status:'online',discovered_at:'2026-09-25T12:00:00Z',disk_root_percent:i===199?40:86,recovery_required:i===199}));
    const large=await render({devices,hasLoadedOnce:true,lastUpdated:'2026-09-25T12:00:00Z',activeError:new Error('503'),jobsError:new Error('503')});
    assert.match(large,/200 devices need attention/); assert.match(large,/Active work is unknown/);
    assert.ok(large.indexOf('Verify interrupted maintenance') < large.indexOf('Inspect root storage pressure'));
    assert.match(large,/operation=system.recover[^"<]*devices=200/);
    assert.doesNotMatch(large,/All devices are reachable|No active jobs/);
    const partial = {job_id:'partial-run',status:'partial',playbook:'preflight_check.yml',target_devices:'node-01,node-02',created_at:'2026-09-27T12:00:00Z'};
    const mixed = await render({devices:devices.slice(0,2),hasLoadedOnce:true,recentJobs:[partial],jobsUpdated:'2026-09-27T12:00:00Z',adverseJobs:[partial]});
    assert.match(mixed,/href="\/activity\?status=partial"[^>]*>1 partial/);
    assert.match(mixed,/condition-tag warning[^>]*>Partial/);
  } finally { await server.close(); }
});
