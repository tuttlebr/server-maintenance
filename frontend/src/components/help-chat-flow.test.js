import test from 'node:test';
import assert from 'node:assert/strict';
import DOMPurify from 'dompurify';
import {createRouter, createMemoryHistory} from 'vue-router';
import {element, renderer, text, find, flush, compileView} from '../../test-support/vue.js';

const {default: HelpChat} = await import(await compileView(new URL('./HelpChat.vue', import.meta.url)));

async function mount(t) {
  let app;
  const restore=[];
  t.after(()=>{app?.unmount();restore.reverse().forEach(reset=>reset());});
  // The node renderer does not parse HTML. This test covers chat state and
  // disclosure behavior, not the browser's Markdown sanitization pipeline.
  const globals = {
    localStorage: {getItem:()=> 'test', setItem(){}},
    window: {location:{hash:''}, addEventListener(){}, removeEventListener(){}},
    document: {createElement:()=>({innerHTML:'',setAttribute(){},content:{querySelectorAll:()=>[],append(){}}})},
    Document: class {},
    ShadowRoot: class {},
  };
  for (const [key,value] of Object.entries(globals)) {
    const original=Object.getOwnPropertyDescriptor(globalThis,key);
    Object.defineProperty(globalThis,key,{configurable:true,value});
    restore.push(()=>original ? Object.defineProperty(globalThis,key,original) : delete globalThis[key]);
  }
  const sanitize=Object.getOwnPropertyDescriptor(DOMPurify,'sanitize');
  DOMPurify.sanitize=value=>value;
  restore.push(()=>sanitize ? Object.defineProperty(DOMPurify,'sanitize',sanitize) : delete DOMPurify.sanitize);
  let controller;
  const requests=[];
  t.mock.method(globalThis,'fetch',async(url,options)=>{
    if(url.endsWith('/status'))return new Response(JSON.stringify({available:true,mode:'nat'}));
    requests.push(JSON.parse(options.body));
    return new Response(new ReadableStream({start(value){controller=value;}}));
  });
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/',component:{render:()=>null}}]});
  await router.push('/'); await router.isReady();
  const root=element('root');app=renderer.createApp(HelpChat).use(router);
  app.mount(root); await flush();
  find(root,node=>node.props['aria-label']==='Ask Fleet Help about devices, operations, and troubleshooting').props.onClick();
  await flush();
  return {
    root, requests,
    async send(query){
      find(root,node=>node.props.id==='chat-input').props['onUpdate:modelValue'](query);
      await flush();
      find(root,node=>node.tag==='form').props.onSubmit({preventDefault(){}});
      await flush();
    },
    async event(event){controller.enqueue(new TextEncoder().encode(`data: ${JSON.stringify(event)}\n\n`));await flush();},
    async done(){controller.enqueue(new TextEncoder().encode('event: done\ndata: {}\n\n'));await flush();},
  };
}

function all(root,predicate){return [ ...(predicate(root)?[root]:[]), ...root.children.flatMap(child=>all(child,predicate)) ];}

test('chat shows one live cue and keeps search activity collapsed after the final answer',async t=>{
  const view=await mount(t);
  await view.send('How many GPUs are in my fleet?');
  await view.event({type:'status',text:'Loading recent activity context'});
  await view.event({type:'status',text:'Preparing response'});
  await view.event({type:'status',text:'Searching indexed job history',activity:'search'});
  assert.equal(all(view.root,node=>node.props.role==='status').length,1);
  assert.match(text(view.root),/Searching indexed job history/);
  assert.doesNotMatch(text(view.root),/Loading recent activity context|Preparing response|Search activity/);
  assert.equal(all(view.root,node=>node.props['aria-label']==='Copy Fleet Help response').length,0);
  await view.event({type:'content',content:'Your fleet has 8 GPUs.'});
  await view.done();
  assert.equal(all(view.root,node=>node.props.role==='status').length,0);
  const disclosure=find(view.root,node=>node.tag==='button' && text(node).includes('Search activity'));
  assert.equal(disclosure.props['aria-expanded'],false);
  assert.doesNotMatch(text(view.root),/Searching indexed job history/);
  disclosure.props.onClick();await flush();
  assert.match(text(view.root),/Searching indexed job history/);
  assert.doesNotMatch(text(view.root),/Loading recent activity context|Preparing response/);
  await view.send('Thanks');
  assert.deepEqual(view.requests[1].messages,[
    {role:'user',content:'How many GPUs are in my fleet?'},
    {role:'assistant',content:'Your fleet has 8 GPUs.'},
    {role:'user',content:'Thanks'},
  ]);
  await view.event({type:'content',content:"You're welcome."});await view.done();
});

test('greetings do not acquire a generic steps disclosure',async t=>{
  const view=await mount(t);await view.send('Hello');
  await view.event({type:'status',text:'Preparing response'});
  await view.event({type:'content',content:'Hello.'});await view.done();
  assert.doesNotMatch(text(view.root),/Search activity|steps|Preparing response/);
});
