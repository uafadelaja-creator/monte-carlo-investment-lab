#!/usr/bin/env node
/* CI smoke-test for PairLab plan controls without a browser dependency.
 * Uses the exact HTML IDs and historic JSON files published by GitHub Pages.
 */
const fs=require("fs"), path=require("path"), vm=require("vm"), assert=require("assert");
const dir=__dirname;
const html=fs.readFileSync(path.join(dir,"index.html"),"utf8");
const ids=new Set([...html.matchAll(/id="([^"]+)"/g)].map(m=>m[1]));
const presets={
  "plan-entry":"2","plan-exit":"0.5","plan-stop":"3","plan-hold":"20",
  "plan-gross":"300","plan-fees":"10","plan-borrow":"3"
};
class Elem {
  constructor(tag="div",id=""){this.tag=tag;this.id=id;this.textContent="";this.className="";this.value=presets[id]||"";this.children=[];this.attributes={};this.dataset={};this.events={};}
  replaceChildren(...items){this.children=[...items];}
  append(...items){this.children.push(...items);}
  setAttribute(k,v){this.attributes[k]=String(v);}
  addEventListener(type,callback){this.events[type]=callback;}
  scrollIntoView(){}
  click(){}
}
const elements=new Map();
const get=id=>{
  if(!ids.has(id))throw Error("Missing HTML id: "+id);
  if(!elements.has(id))elements.set(id,new Elem("div",id));
  return elements.get(id);
};
const buttons=[...html.matchAll(/data-proposal-pair="([^"]+)"/g)].map(m=>{
  const b=new Elem("button");b.dataset.proposalPair=m[1];return b;
});
const listeners=new Map();
const windowStub={
  addEventListener(type,fn){const all=listeners.get(type)||[];all.push(fn);listeners.set(type,all);},
  dispatchEvent(event){for(const listener of listeners.get(event.type)||[])listener(event);}
};
class CustomEvent {constructor(type,opts){this.type=type;this.detail=opts.detail;}}
const documentStub={
  getElementById:get,
  createElement(tag){return new Elem(tag);},
  createElementNS(ns,tag){return new Elem(tag);},
  querySelectorAll(query){return query==="[data-proposal-pair]"?buttons:[];}
};
const context={
  document:documentStub,window:windowStub,CustomEvent,console,Math,Number,Date,Set,Map,
  Blob,URL:{createObjectURL:()=> "blob:test",revokeObjectURL:()=>{}},
  setTimeout:()=>{},
  fetch:async resource=>{
    const input=path.join(dir,resource.replace(/^\.\//,""));
    return {ok:fs.existsSync(input),status:fs.existsSync(input)?200:404,json:async()=>JSON.parse(fs.readFileSync(input,"utf8"))};
  }
};
(async()=>{
  vm.runInNewContext(fs.readFileSync(path.join(dir,"plans.js"),"utf8"),context,
                     {filename:"plans.js",timeout:12000});
  for(let i=0;i<10;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.strictEqual(get("plan-pair").value,"AVAV/KTOS");
  assert.ok(get("plan-verdict").textContent.includes("NO CURRENT QUALIFIED"));
  assert.ok(get("plan-condition").textContent.includes("FDR q"));
  assert.ok(get("plan-selected").textContent.includes("Nov"));
  assert.ok(get("plan-pair").children.length>=18);
  assert.ok(get("plan-event").children.length>=1);

  get("plan-pair").value="NVDA/TSM";
  get("plan-pair").onchange();
  assert.ok(get("plan-direction").textContent.includes("SHORT NVDA"));
  assert.ok(get("plan-reject").textContent.includes("not ready"));
  assert.ok(get("plan-event").children.length>1,
            "NVDA/TSM should offer real historic threshold-crossing replays");
  assert.ok(get("plan-result").textContent.includes("HYPOTHETICAL")||
            get("plan-result").textContent.includes("UNRESOLVED"));
  assert.ok(get("plan-net").textContent.includes("$"));
  assert.ok(get("plan-pnl-gross").textContent.includes("$"));
  const initialNet=get("plan-net").textContent;
  const event=get("plan-event").value;
  get("plan-gross").value="1000";
  get("plan-gross").events.input();
  assert.strictEqual(get("plan-event").value,event);
  assert.ok(get("plan-notional-description").textContent.includes("$1000.00"));
  assert.ok(get("plan-net").textContent.includes("$"));
  assert.strictEqual(get("plan-gross").value,"1000",
       "Updating P/L must not overwrite the notional input");
  assert.ok(get("plan-entry").value==="2");
  const thresholdCross=buttons.find(b=>b.dataset.proposalPair==="SOFI/NU");
  assert.ok(thresholdCross);
  thresholdCross.onclick();
  assert.strictEqual(get("plan-pair").value,"SOFI/NU");
  assert.ok(get("plan-verdict").textContent.includes("NO CURRENT QUALIFIED"));
  assert.ok(get("plan-reject").textContent.includes("not ready"));
  console.log("PASS: plan initialization, pair selection, historical replays, "+
              "price-derived P/L, notional editing and research-only gating");
})().catch(err=>{console.error(err);process.exitCode=1;});
