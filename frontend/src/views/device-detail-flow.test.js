import test from 'node:test';
import assert from 'node:assert/strict';
import {h} from 'vue';
import {createRouter,createMemoryHistory,RouterView} from 'vue-router';
import {element,renderer,text,flush,compileView} from '../../test-support/vue.js';

const {default:DeviceDetail}=await import(await compileView(new URL('./DeviceDetail.vue',import.meta.url)));
const device=id=>({id,name:`Device ${id}`,inventory_name:`node-${id}`,endpoint:`node-${id}.example`,kind:'server',transport:'ssh',status:'online',facts:{},annotations:{},capabilities:[]});

test('switching device routes reloads identity and rejects a late response for the previous device',async t=>{
  const originalStorage=Object.getOwnPropertyDescriptor(globalThis,'localStorage');
  Object.defineProperty(globalThis,'localStorage',{configurable:true,value:{getItem:()=> 'test'}});
  t.after(()=>{if(originalStorage)Object.defineProperty(globalThis,'localStorage',originalStorage);else delete globalThis.localStorage;});
  let release;
  const first=new Promise(resolve=>release=resolve);
  t.mock.method(globalThis,'fetch',async url=>{
    const id=url.split('/').at(-1);
    if(id==='1')await first;
    return new Response(JSON.stringify(device(id)));
  });
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/devices/:id',component:DeviceDetail,props:true},{path:'/:pathMatch(.*)*',component:{render:()=>null}}]});
  await router.push('/devices/1');await router.isReady();
  const app=renderer.createApp({render:()=>h(RouterView)}).use(router),root=element('root');
  app.mount(root);t.after(()=>app.unmount());
  try{
    await router.push('/devices/2');await flush();
    assert.match(text(root),/Device 2/);
  }finally{release();}
  await flush();
  assert.match(text(root),/Device 2/);assert.doesNotMatch(text(root),/Device 1/);
  await router.push('/devices/3');await flush();
  assert.match(text(root),/Device 3/);assert.doesNotMatch(text(root),/Device 2/);
});
