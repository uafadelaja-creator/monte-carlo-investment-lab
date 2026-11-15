#!/usr/bin/env node
/* Smoke test the free TradingView integration without needing network or browser. */
"use strict";
const fs=require("fs"),path=require("path"),vm=require("vm"),assert=require("assert");
const here=__dirname,html=fs.readFileSync(path.join(here,"index.html"),"utf8");
const ids=new Set([...html.matchAll(/id="([^"]+)"/g)].map(m=>m[1]));
class Element {
  constructor(tag,id=""){this.tagName=tag;this.id=id;this.children=[];this.handlers={};this.textContent="";this.className="";this.href="";this.rel="";this.target="";}
  replaceChildren(...children){this.children=[...children];}
  append(...children){this.children.push(...children);}
  addEventListener(kind,handler){this.handlers[kind]=handler;}
  contains(child){return this.children.includes(child);}
}
const elements=new Map();
for (const id of ids)elements.set(id,new Element("div",id));
const document={
  readyState:"complete",
  getElementById(id){return elements.get(id)||null;},
  createElement(tag){return new Element(tag);},
  addEventListener(){throw Error("DOMContentLoaded should not be used when already loaded");}
};
const events={};
const window={
  pairlabCurrentPair:"AVAV/KTOS",
  addEventListener(type,listener){(events[type] ||= []).push(listener);},
  dispatchEvent(event){for(const fn of events[event.type]||[])fn(event);}
};
const code=fs.readFileSync(path.join(here,"tradingview.js"),"utf8");
vm.runInNewContext(code,{window,document,console,JSON,Math,Object,Set,Map}, {timeout:2000});
function current(id){
  const host=elements.get(id);
  assert.strictEqual(host.children.length,1,"Expected one TradingView widget wrapper");
  const container=host.children[0];const script=container.children.find(c=>c.tagName==="script");
  assert.ok(script,"Widget must include embed script");
  assert.strictEqual(script.src,"https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js");
  assert.ok(script.async,"Widget script must load asynchronously");
  return JSON.parse(script.textContent);
}
assert.strictEqual(current("tv-host-a").symbol,"NASDAQ:AVAV");
assert.strictEqual(current("tv-host-b").symbol,"NASDAQ:KTOS");
assert.strictEqual(current("tv-host-a").theme,"dark");
assert.strictEqual(current("tv-host-a").allow_symbol_change,false);
assert.strictEqual(elements.get("tv-chip-a").textContent,"AVAV");
assert.strictEqual(elements.get("tv-chip-b").textContent,"KTOS");
assert.ok(elements.get("tv-link-a").href.startsWith("https://www.tradingview.com/symbols/"));
const firstHost=elements.get("tv-host-a").children[0];
window.dispatchEvent({type:"pairlab:selected",detail:{pair:"NVDA/AMD"}});
assert.strictEqual(current("tv-host-a").symbol,"NASDAQ:NVDA");
assert.strictEqual(current("tv-host-b").symbol,"NASDAQ:AMD");
assert.notStrictEqual(firstHost,elements.get("tv-host-a").children[0],"Changing pair must refresh widget");
assert.ok(elements.get("tv-chart-status").textContent.includes("remains fixed"));
const sameHost=elements.get("tv-host-a").children[0];
window.dispatchEvent({type:"pairlab:selected",detail:{pair:"NVDA/AMD"}});
assert.strictEqual(sameHost,elements.get("tv-host-a").children[0],"Same pair should not reload");
window.dispatchEvent({type:"pairlab:selected",detail:{pair:"__EVIL__/AMD"}});
assert.strictEqual(current("tv-host-a").symbol,"NASDAQ:NVDA","Reject unexpected tickers");
elements.get("tv-reload").handlers.click();
assert.strictEqual(current("tv-host-a").symbol,"NASDAQ:NVDA");
assert.notStrictEqual(sameHost,elements.get("tv-host-a").children[0],"Reload button must recreate widget");
window.dispatchEvent({type:"pairlab:selected",detail:{pair:"PL/TSM"}});
assert.strictEqual(current("tv-host-a").symbol,"NYSE:PL");
assert.strictEqual(current("tv-host-b").symbol,"NYSE:TSM");
assert.ok(html.includes("statistical scanner")||html.includes("statistical analysis"));
assert.ok(html.includes("delay")&&html.includes("November 11, 2026"));
console.log("PASS: two free TradingView widgets, valid exchange symbols, pair selector sync, reload, whitelisting and delayed-data disclaimers");
