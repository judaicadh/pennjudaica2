// Exercise the actual app and search library against a minimal browser shell.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const MiniSearch = require('./vendor/minisearch.js');
const payload = JSON.parse(fs.readFileSync(new URL('../items.json', 'file://' + __filename)));
const nodes = new Map();
function element() {
  return {value:'',innerHTML:'',textContent:'',style:{},dataset:{},checked:false,
    classList:{add(){},remove(){},toggle(){},contains(){return false;}},
    focus(){},handlers:{},addEventListener(type,handler){this.handlers[type]=handler;},appendChild(){},setAttribute(){}};
}
const document = {readyState:'complete',getElementById(id){if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);},
  createElement:element,querySelector(){return {offsetTop:0};},querySelectorAll(){return [];},addEventListener(){}};
const context = {document,MiniSearch,console,Set,Map,Array,Number,Promise,setTimeout,clearTimeout,
  localStorage:{setItem(){},removeItem(){},getItem(){return null;}},
  location:{hash:'',pathname:'/',search:''},history:{replaceState(_a,_b,url){context.location.hash=url.startsWith('#')?url:'';}},
  fetch:async()=>({ok:true,json:async()=>payload})};
context.scrollTo=()=>{};context.window=context;context.addEventListener=()=>{};
vm.runInNewContext(fs.readFileSync(new URL('../app.js','file://'+__filename),'utf8'),context);
(async()=>{
  await new Promise(r=>setTimeout(r,0));
  const total=Number(nodes.get('matchCount').textContent);
  assert.equal(total,payload.items.length);
  nodes.get('q').value='leeser';
  nodes.get('q').handlers.input({isComposing:false});
  await new Promise(r=>setTimeout(r,200));
  const matches=Number(nodes.get('matchCount').textContent);
  assert(matches>0 && matches<total,`Expected Leeser matches, received ${matches}`);
  assert(nodes.get('grid').innerHTML.toLowerCase().includes('leeser'));
  assert.equal(context.location.hash,'#q=leeser');
  nodes.get('q').value='zzzznonexistentjudaica';
  nodes.get('q').handlers.input({isComposing:false});
  await new Promise(r=>setTimeout(r,200));
  assert.equal(Number(nodes.get('matchCount').textContent),0);
  nodes.get('q').value='';nodes.get('q').handlers.input({isComposing:false});
  await new Promise(r=>setTimeout(r,200));
  assert.equal(Number(nodes.get('matchCount').textContent),total);
  const options=nodes.get('aType').innerHTML;
  assert(options.includes('Letters &amp; correspondence'));
  assert(!options.includes('trade cards; advertisements'));
  context.PJPapp.resetAdv();
  const member=payload.items.find(i=>i.collections.length>1);
  nodes.get('aCollection').value=member.collections[1];
  context.PJPapp.applyAdv();
  assert.equal(Number(nodes.get('matchCount').textContent),payload.items.filter(i=>i.collections.includes(member.collections[1])).length);
  context.PJPapp.resetAdv();nodes.get('aFrom').value='1845';nodes.get('aTo').value='1845';context.PJPapp.applyAdv();
  assert.equal(Number(nodes.get('matchCount').textContent),payload.items.filter(i=>i.yearStart && i.yearStart<=1845 && i.yearEnd>=1845).length);
  context.PJPapp.resetAdv();nodes.get('aType').value='Letters & correspondence';context.PJPapp.applyAdv();
  assert.equal(Number(nodes.get('matchCount').textContent),payload.items.filter(i=>i.formats.includes('Letters & correspondence')).length);
  console.log(`PASS: collection memberships, condensed formats and overlapping date ranges.\nPASS: live search returns ${matches} Leeser matches; no-match and clear restore correctly.`);
})().catch(err=>{console.error(err);process.exitCode=1;});
