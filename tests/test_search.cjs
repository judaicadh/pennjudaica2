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
    focus(){},scrollIntoView(){},handlers:{},addEventListener(type,handler){this.handlers[type]=handler;},appendChild(){},setAttribute(){}};
}
const document = {readyState:'complete',getElementById(id){if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);},
  createElement:element,querySelector(){return {offsetTop:0};},querySelectorAll(){return [];},addEventListener(){}};
const context = {document,MiniSearch,console,Set,Map,Array,Number,Promise,URLSearchParams,setTimeout,clearTimeout,
  localStorage:{setItem(){},removeItem(){},getItem(){return null;}},
  location:{hash:'',pathname:'/',search:''},history:{replaceState(_a,_b,url){context.location.hash=url.startsWith('#')?url:'';}},
  fetch:async()=>({ok:true,json:async()=>payload})};
context.scrollTo=()=>{};context.window=context;const windowHandlers={};context.addEventListener=(type,fn)=>{windowHandlers[type]=fn;};
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
  context.PJPapp.clearAll();
  const located=payload.items.find(i=>typeof i.lat==='number' && typeof i.lng==='number');
  const key=located.lat.toFixed(2)+','+located.lng.toFixed(2);
  context.location.hash='#mapLocation='+encodeURIComponent(key);
  windowHandlers.hashchange();
  const atLocation=payload.items.filter(i=>typeof i.lat==='number' && typeof i.lng==='number' && i.lat.toFixed(2)+','+i.lng.toFixed(2)===key);
  assert.equal(Number(nodes.get('matchCount').textContent),atLocation.length);
  assert(nodes.get('activeFilters').innerHTML.includes('Map location:'));
  context.location.hash='#mapLocation='+encodeURIComponent(key)+'&adv_type='+encodeURIComponent('Manuscripts');
  windowHandlers.hashchange();
  assert.equal(Number(nodes.get('matchCount').textContent),atLocation.filter(i=>i.formats.includes('Manuscripts')).length);
  context.PJPapp.clearAll();assert.equal(Number(nodes.get('matchCount').textContent),total);
  const markers=[];
  context.L={map:()=>({setView(){return this;},invalidateSize(){}}),tileLayer:()=>({addTo(){}}),
    layerGroup:()=>({addTo(){return this;},clearLayers(){markers.length=0;},addLayer(marker){markers.push(marker);}}),
    divIcon:()=>({}),marker:()=>({bindPopup(html){this.popup=html;return this;}})};
  context.PJPapp.setView('map');
  const barcelona=markers.find(m=>m.popup.includes('41.39%2C2.17'));
  assert(barcelona && barcelona.popup.includes('<div class="pop-title">Barcelona</div>'));
  assert(!barcelona.popup.includes('Venezuela'));
  assert(markers.some(m=>m.popup.includes('<div class="pop-title">Barcelona, Venezuela</div>')));
  const spain=markers.find(m=>m.popup.includes('40.00%2C-3.70'));
  assert(spain && spain.popup.includes('54 more · View all 60 items'));
  const href=spain.popup.match(/class="pop-more" href="([^"]+)"/)[1].replaceAll('&amp;','&');
  context.location.hash=href;windowHandlers.hashchange();
  assert.equal(Number(nodes.get('matchCount').textContent),60);
  context.PJPapp.clearAll();context.PJPapp.setView('timeline');
  assert(nodes.get('eraLinks').innerHTML.includes('1800–1899'));
  context.PJPapp.jumpEra('era-1800');
  console.log('PASS: map popup links open all 60 Spain items; timeline era links render.');
  console.log('PASS: map location links restore full results, preserve filters, and clear correctly.');
  console.log(`PASS: collection memberships, condensed formats and overlapping date ranges.\nPASS: live search returns ${matches} Leeser matches; no-match and clear restore correctly.`);
})().catch(err=>{console.error(err);process.exitCode=1;});
