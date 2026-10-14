/* Test the delivered inline program in a DOM/localStorage model.
 * This is not a real browser, screenshot/layout, file-protocol or download test.
 * No network, browser protocol or computer interaction is used.
 */
'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const path=require('node:path');
const file=process.argv[2],out=process.argv[3];
const html=fs.readFileSync(file,'utf8');
const catalog=JSON.parse(html.match(/<script id="catalog" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const code=html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
new vm.Script(code);
const storage=new Map(),downloads=[],results=[];

class Element{
 constructor(tag='div'){this.tagName=tag.toUpperCase();this.children=[];this.parent=null;this.style={};this.dataset={};this.value='';this.className='';this.events={};this._text='';this.files=[];this.disabled=false;this.attributes={};this.classList={toggle:(name,on)=>{const a=new Set(this.className.split(' ').filter(Boolean));on?a.add(name):a.delete(name);this.className=[...a].join(' ');}};}
 set textContent(s){this._text=String(s);this.children=[];}
 get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
 set innerHTML(s){this._html=String(s);this._text=String(s);this.children=[];}
 get innerHTML(){return this._html||'';}
 append(...nodes){for(const n of nodes){if(n.tagName==='FRAGMENT'){this.append(...n.children);continue;}if(n.parent)n.parent.children=n.parent.children.filter(c=>c!==n);n.parent=this;this.children.push(n);}}
 prepend(...nodes){const old=this.children.slice();this.children=[];this.append(...nodes,...old);}
 replaceChildren(...nodes){this._text='';this.children=[];this.append(...nodes);}
 addEventListener(k,f){(this.events[k]??=[]).push(f);}
 emit(k,data={}){if(this.disabled)return;for(const f of this.events[k]||[])f({target:this,...data});}
 click(){if(this.tagName==='A'){downloads.push({name:this.download,url:this.href});return;}this.emit('click');}
 setAttribute(k,v){this.attributes[k]=v;}
 focus(){}scrollIntoView(){}
 remove(){if(this.parent)this.parent.children=this.parent.children.filter(c=>c!==this);}
 querySelectorAll(selector){const pieces=selector.split('.'),tag=pieces[0].toUpperCase(),cls=pieces[1];const found=[];const visit=e=>{for(const n of e.children){if((!tag||n.tagName===tag)&&(!cls||n.className.split(' ').includes(cls)))found.push(n);visit(n);}};visit(this);return found;}
 querySelector(s){return this.querySelectorAll(s)[0]||null;}
}

function boot({blockedStorage=false}={}){
 const ids={};
 for(const m of html.matchAll(/<([a-z][a-z0-9]*)\b[^>]*\bid="([^"]+)"/g))ids[m[2]]=new Element(m[1]);
 ids.catalog.textContent=JSON.stringify(catalog);
 const body=new Element('body'),document={body,getElementById:id=>ids[id],createElement:tag=>new Element(tag),createDocumentFragment:()=>new Element('fragment'),createTextNode:s=>{const e=new Element('text');e.textContent=s;return e;},events:{},addEventListener(k,f){(this.events[k]??=[]).push(f);}};
 const blobs=new Map(),timers=new Map();let next=0,confirmValue=true;
 const ctx={console,document,Blob,Map,Set,Date,JSON,Array,String,RegExp,Error,Object,Number,Boolean,URL:{createObjectURL(blob){const url='blob:test-'+blobs.size;blobs.set(url,blob);return url;},revokeObjectURL(){}},
 localStorage:{getItem(k){if(blockedStorage)throw Error('storage disabled');return storage.get(k)||null;},setItem(k,v){if(blockedStorage)throw Error('storage disabled');storage.set(k,v);}},
 setTimeout(f,ms){timers.set(++next,{f,ms});return next;},clearTimeout(id){timers.delete(id);},
 confirm(){return confirmValue;},
 };
 ctx.window=ctx;ctx.addEventListener=(k,f)=>{(ctx.windowEvents??={})[k]=f;};
 vm.createContext(ctx);vm.runInContext(code,ctx);
 return {ctx,ids,blobs,eval:s=>vm.runInContext(s,ctx),flush(){for(const [id,t]of timers)if(t.ms===400){timers.delete(id);t.f();}},
 select(key){const b=ids.results.children.find(e=>e.dataset.key===key);assert(b,'visible key '+key);b.click();},
 confirm(value){confirmValue=value;},
 async import(doc){ids['file-input'].files=[{size:10000,text:async()=>JSON.stringify(doc)}];ids['file-input'].emit('change');await new Promise(resolve=>setImmediate(resolve));},
 };
}
function ok(name){results.push({name,status:'pass'});}
const fresh=boot();
assert.equal(fresh.ids.total.textContent,'1,541');
assert.equal(fresh.ids.modified.textContent,'0');
assert.equal(fresh.eval('ENTRIES.filter(e=>invalid(e)).length'),0);
assert.equal(catalog.entries.length,1541);
assert.equal(catalog.entries.filter(e=>e.group==='优化版新增').length,75);
ok('actual 1088 texts and 453 shared names; all baseline entries validate');

fresh.ids.category.value='优化版新增';fresh.ids.category.emit('change');
assert.equal(fresh.ids.results.children.length,75);
fresh.ids.search.value='大阪旅馆在哪';fresh.ids.search.emit('input');
assert.equal(fresh.ids.results.children.length,1);
fresh.ids.results.children[0].click();
assert.equal(fresh.ids['entry-title'].textContent,'消息 302');
assert(fresh.ids.original.textContent.includes('ホテル'));
assert(fresh.ids.translation.textContent.includes('大阪旅馆'));
ok('category, original/Chinese search, selection and original/translation views');

const base=catalog.entries.find(e=>e.key==='message:302');
const fields=fresh.ids.editor.querySelectorAll('textarea');
const target=fields.find(e=>e.value.includes('大阪旅馆'));
assert(target);target.value='大阪旅馆究竟在哪儿？';target.emit('input');
fresh.ids.notes.value='测试备注：<img src=x onerror=alert(1)>，请结合前文。';fresh.ids.notes.emit('input');
fresh.ids['mark-reviewed'].click();fresh.flush();
const saved=fresh.ctx.workbenchChecks.exportDocument();
assert.equal(Object.keys(saved.revisions).length,1);
assert(saved.revisions[base.key].translation.includes('大阪旅馆究竟在哪儿？'));
assert.equal(saved.revisions[base.key].status,'reviewed');
assert.equal(JSON.stringify(fresh.ctx.workbenchChecks.split(base.translation).tokens),JSON.stringify(fresh.ctx.workbenchChecks.split(saved.revisions[base.key].translation).tokens));
assert(fresh.ids.notes.value.includes('<img'));
assert(fresh.ids['save-status'].textContent.includes('已自动暂存'));
ok('real editor handlers preserve tokens, save notes/review status, treat content as text');

const restored=boot();restored.ids.category.value='优化版新增';restored.ids.category.emit('change');restored.select('message:302');
assert(restored.ids.editor.querySelectorAll('textarea').some(t=>t.value.includes('究竟')));
assert.equal(restored.ids['entry-status'].textContent,'已校对');
assert.equal(restored.ids.notes.value,saved.revisions[base.key].note);
ok('new runtime restores actual edits and notes from shared localStorage model');

restored.ids.export.click();assert(downloads.at(-1).name.endsWith('.json'));
const exportBlob=restored.blobs.get(downloads.at(-1).url);
async function finish(){
 const exported=JSON.parse(await exportBlob.text());
 assert.equal(exported.revisions['message:302'].translation,saved.revisions['message:302'].translation);
 const cleanDoc=JSON.parse(JSON.stringify(exported));
 const changedDoc=JSON.parse(JSON.stringify(exported));changedDoc.revisions['message:302'].translation=changedDoc.revisions['message:302'].translation.replace('究竟','到底');
 restored.confirm(false);await restored.import(changedDoc);
 assert(restored.ctx.workbenchChecks.exportDocument().revisions['message:302'].translation.includes('究竟'));
 restored.confirm(true);await restored.import(changedDoc);
 assert(restored.ctx.workbenchChecks.exportDocument().revisions['message:302'].translation.includes('到底'));
 assert(restored.ids['entry-status'].textContent==='已校对');
 ok('JSON download payload, validated import and explicit conflict-cancel/accept behavior');
 const before=JSON.stringify(restored.ctx.workbenchChecks.exportDocument().revisions);
 for(const mutate of [
  d=>d.catalog_fingerprint='wrong',
  d=>d.revisions['unknown']=d.revisions['message:302'],
  d=>d.revisions['message:302'].source_hash='wrong',
  d=>d.revisions['message:302'].translation=d.revisions['message:302'].translation.replace('{E2}',''),
  d=>d.revisions['message:302'].status='unknown',
  d=>d.revisions['message:302'].base_translation='wrong',
  d=>d.revisions['message:302'].target={kind:'extended',message:9999},
 ]){const bad=JSON.parse(JSON.stringify(changedDoc));mutate(bad);assert.throws(()=>restored.ctx.workbenchChecks.validateImport(bad));await restored.import(bad);assert.equal(JSON.stringify(restored.ctx.workbenchChecks.exportDocument().revisions),before);}
 ok('seven invalid imports are rejected atomically without changing local records');
 restored.ids.filter.value='edited';restored.ids.filter.emit('change');assert.equal(restored.ids.results.children.length,1);
 restored.ids.csv.click();assert(downloads.at(-1).name.endsWith('.csv'));assert((await restored.blobs.get(downloads.at(-1).url).text()).includes('大阪旅馆到底在哪儿'));
 ok('modified-only filter and CSV export contain actual revision content');
 restored.ids.category.value='人物名';restored.ids.filter.value='';restored.ids.category.emit('change');restored.ids.search.value='';restored.ids.search.emit('input');restored.select('name:くにお');
 const nameField=restored.ids.editor.querySelector('textarea');nameField.value='国夫君';nameField.emit('input');
 assert(restored.ids.validation.textContent.includes('两个'));assert(restored.ids['mark-reviewed'].disabled);
 assert.throws(()=>restored.ctx.workbenchChecks.exportDocument());
 nameField.value='国夫';nameField.emit('input');assert.equal(restored.ids.validation.style.display,'none');assert.equal(restored.ids['mark-reviewed'].disabled,false);
 ok('shared-name width validation blocks unsafe export and clears after correction');
 const unavailable=boot({blockedStorage:true});unavailable.select(ENTRIES0());
 const uf=unavailable.ids.editor.querySelector('textarea');uf.value='拿到了';uf.emit('input');unavailable.flush();assert(unavailable.ids['save-status'].textContent.includes('无法暂存'));unavailable.ids.export.click();assert(downloads.at(-1).name.endsWith('.json'));
 ok('storage-disabled mode reports failure and still provides file export');
 // Save a genuine UI-handler export for the independent Python validator.
 if(out){fs.mkdirSync(path.dirname(out),{recursive:true});fs.writeFileSync(out,JSON.stringify(cleanDoc,null,2));fs.writeFileSync(out.replace(/\.json$/,'.checks.json'),JSON.stringify({status:'pass',checks:results,scope:'DOM/localStorage model and actual inline handlers; no real browser layout/file-protocol/download verification'},null,2));}
 console.log(JSON.stringify({status:'pass',checks:results,scope:'DOM/localStorage model; not an actual browser'},null,2));
}
function ENTRIES0(){return catalog.entries[0].key;}
finish().catch(e=>{console.error(e);process.exitCode=1;});
