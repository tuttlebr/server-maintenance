import {readFile} from 'node:fs/promises';
import {parse,compileScript} from '@vue/compiler-sfc';
import {createRenderer,nextTick} from 'vue';

export function element(tag,text='') { return {tag,text,props:{},children:[],parent:null,get options(){return this.children.filter(c=>c.tag==='option');},get value(){return this.props.value;},set value(v){this.props.value=v;},getRootNode(){return {activeElement:null};},focus(){},scrollIntoView(){},addEventListener(){},removeEventListener(){},setAttribute(){},removeAttribute(){}}; }
const teleportTarget = element('body');
export const renderer=createRenderer({
 querySelector:()=>teleportTarget,
 createElement:tag=>element(tag), createText:text=>element('#text',text), createComment:text=>element('#comment',text),
 setText:(node,text)=>node.text=text,setElementText:(node,text)=>{node.text=text;node.children=[];},
 patchProp:(node,key,old,value)=>node.props[key]=value,
 insert(node,parent,anchor=null){if(node.parent){node.parent.children=node.parent.children.filter(c=>c!==node);}node.parent=parent;const i=anchor?parent.children.indexOf(anchor):-1;i<0?parent.children.push(node):parent.children.splice(i,0,node);},
 remove(node){if(node.parent)node.parent.children=node.parent.children.filter(c=>c!==node);},
 parentNode:node=>node.parent,nextSibling:node=>node.parent?.children[node.parent.children.indexOf(node)+1],
});
export function text(node) { return node.tag==='#comment'?'':node.text+node.children.map(text).join(''); }
export function find(node,predicate) { if(predicate(node))return node;for(const child of node.children){const match=find(child,predicate);if(match)return match;} }
export const flush=async()=>{for(let i=0;i<12;i++){await new Promise(resolve=>setImmediate(resolve));await nextTick();}};
export async function compileView(url) {
 const source=await readFile(url,'utf8');
 const {descriptor}=parse(source);
 // This renderer models nodes, not browser HTML parsing. Keep static template
 // nodes as VNodes so tests can inspect their controls and event handlers too.
 let code=compileScript(descriptor,{id:url.pathname,inlineTemplate:true,templateOptions:{compilerOptions:{hoistStatic:false}}}).content;
 const imports=[...code.matchAll(/from ['"]([^'"]+)['"]/g)];
 for(const [,name] of imports) {
  const resolved=name.endsWith('.vue')?await compileView(new URL(name,url)):name.startsWith('.')?new URL(name,url).href:import.meta.resolve(name);
  code=code.replaceAll(`from "${name}"`,`from ${JSON.stringify(resolved)}`).replaceAll(`from '${name}'`,`from ${JSON.stringify(resolved)}`);
 }
 return `data:text/javascript;base64,${Buffer.from(code).toString('base64')}`;
}
