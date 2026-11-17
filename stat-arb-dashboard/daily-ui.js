"use strict";
const $ = id => document.getElementById(id);
const DATA_BASE = "https://raw.githubusercontent.com/uafadelaja-creator/monte-carlo-investment-lab/main/stat-arb-dashboard/data/";
const STATUS_LABELS = {research_candidate:"Research candidate",preliminary_watch:"Preliminary watch",not_qualified:"Not qualified",data_unavailable:"Data unavailable"};
let scan = null, journal = null;
let activeView = "latest";

function el(tag, className = "", text = null) {
  const node=document.createElement(tag);
  if(className)node.className=className;
  if(text!==null)node.textContent=String(text);
  return node;
}
function shortDate(day) {
  if(!/^\d{4}-\d{2}-\d{2}$/.test(day||""))return "Not available";
  const [y,m,d]=day.split("-").map(Number);
  return new Date(Date.UTC(y,m-1,d)).toLocaleDateString(undefined,{month:"short",day:"numeric",year:"numeric",timeZone:"UTC"});
}
function number(n, digits=2) {return typeof n==="number" && Number.isFinite(n) ? n.toFixed(digits) : "—";}
function pct(n, digits=1) {return typeof n==="number" && Number.isFinite(n) ? n.toFixed(digits)+"%" : "—";}
function classification(status) {
  return el("span","chip "+(status==="research_candidate"?"good":status==="preliminary_watch"?"watch":"no"),STATUS_LABELS[status]||"Unclassified");
}
function activate(view) {
  activeView=view;
  for(const button of document.querySelectorAll(".tab")){
    const selected=button.dataset.view===view;
    button.setAttribute("aria-selected",String(selected));
  }
  for(const panel of document.querySelectorAll(".view"))panel.hidden=panel.id!=="view-"+view;
}
function chart(points) {
  const svg=document.createElementNS("http://www.w3.org/2000/svg","svg");
  svg.setAttribute("class","chart");
  svg.setAttribute("viewBox","0 0 400 114");
  svg.setAttribute("role","img");
  svg.setAttribute("aria-label","Past approximately 30 observed Z-scores with positive and negative threshold guides");
  if(!Array.isArray(points)||points.length<2)return svg;
  const min=Math.min(-2.5,...points.map(p=>p.z));
  const max=Math.max(2.5,...points.map(p=>p.z));
  const y = n => 9+(max-n)/(max-min)*94;
  const make=(name,attrs)=>{
    const v=document.createElementNS("http://www.w3.org/2000/svg",name);
    for(const [k,val] of Object.entries(attrs))v.setAttribute(k,String(val));
    return v;
  };
  for(const level of [-2,0,2]){
    const guide=make("line",{x1:10,x2:390,y1:y(level),y2:y(level),stroke:level===0?"#45617a":"#846348","stroke-dasharray":"4 5"});
    svg.append(guide);
    const t=make("text",{x:13,y:y(level)-4,fill:"#b6cce0","font-size":9});
    t.textContent=level===0?"0":String(level);
    svg.append(t);
  }
  const coords=points.map((p,i)=>(10+(380*i)/(points.length-1)).toFixed(2)+","+y(p.z).toFixed(2)).join(" ");
  svg.append(make("polyline",{points:coords,fill:"none",stroke:"#63dff6","stroke-width":2.5,"stroke-linejoin":"round","stroke-linecap":"round"}));
  const last=points.at(-1);
  svg.append(make("circle",{cx:390,cy:y(last.z),r:4,fill:"#b4e6ae"}));
  const title=make("title",{});
  title.textContent="Latest: "+last.date+" | Z "+number(last.z);
  svg.append(title);
  return svg;
}
function addMetric(parent,name,value) {
  const box=el("div","mini");
  box.append(el("strong","",value),el("span","",name));
  parent.append(box);
}
function reviewCard(r) {
  const card=el("article","card");
  const top=el("div","card-title");
  const names=el("div","");
  names.append(el("div","pair",r.pair),el("div","sector",r.industry+" · Reviewed "+shortDate(r.review_date)));
  top.append(names,classification(r.classification));
  card.append(top);
  if(!r.input_provenance?.sha256_uncompressed_csv){
    card.append(el("p","provenance-warning","Archived before price checkpoints were introduced. This older review is not independently reproducible from a preserved source file."));
  } else {
    card.append(el("p","muted","Input snapshot retained · SHA-256 "+r.input_provenance.sha256_uncompressed_csv.slice(0,16)+"…"));
  }
  card.append(el("p","verdict",r.verdict));
  card.append(el("div","explain",r.relative_value_explanation));
  const stats=el("div","stat-row");
  addMetric(stats,"90-day correlation",number(r.metrics?.correlation_90d,2));
  addMetric(stats,"Spread Z-score",number(r.metrics?.z_score_60d));
  addMetric(stats,"Adjusted q",number(r.metrics?.universe_fdr_q,3));
  card.append(stats);
  const details=el("details");
  details.append(el("summary","","See deep analysis"));
  const content=el("div","");
  content.append(el("p","","Historical spread Z-score (computed with prior-day formation windows):"));
  content.append(chart(r.z_history));
  const checks=el("ul","checks");
  const labels={cointegration:"Historical cointegration",correlation:"Return correlation",deviation:"Spread deviation",fdr:"Multiple-testing adjustment",beta_stable:"Hedge stability"};
  for(const [key,label] of Object.entries(labels)){
    const good=r.gates?.[key]===true;
    checks.append(el("li",good?"good":"bad",(good?"✓ ":"✕ ")+label));
  }
  content.append(checks);
  const m=r.metrics||{};
  content.append(el("p","",
    "Cointegration p: "+number(m.engle_granger_p,4)+" · Hedge beta: "+number(m.hedge_beta_log_price,3)+
    " · Beta drift: "+pct(m.beta_drift_pct)+" · Estimated half-life: "+
    (m.half_life_sessions_estimate===null?"not estimable":number(m.half_life_sessions_estimate,1)+" sessions")));
  if(Array.isArray(m.half_window_eg_p)){
    content.append(el("p","","Sensitivity: first 126-session p = "+number(m.half_window_eg_p[0],4)+
      "; last 126-session p = "+number(m.half_window_eg_p[1],4)+". Short-window results can be unstable."));
  }
  const rep=r.retrospective_replay||{};
  const box=el("div","replay");
  box.append(el("strong","","Retrospective paper replay · NOT a validated edge"));
  box.append(el("p","",
    (rep.events||0)+" non-overlapping historical examples · "+
    "Hypothetical cumulative net return: "+pct(rep.cumulative_net_return_pct,2)+
    " · Win rate: "+pct(rep.win_rate_pct,1)+
    " · Max drawdown: "+pct(rep.max_drawdown_pct,2)+
    ". Assumes five sessions per trade, next-session closing entries, fixed costs and short borrow."));
  box.append(el("p","",rep.limitations||"Not independently validated."));
  content.append(box);
  content.append(el("p","",r.risk_note||"Educational analysis only."));
  details.append(content);card.append(details);
  return card;
}
function latestReviews() {
  const root=$("latest-cards");
  root.replaceChildren();
  if(!journal?.records?.length){
    root.append(el("p","empty","No completed deep reviews have been published yet. Check the scan status above."));return;
  }
  const day=journal.records.reduce((a,r)=>r.review_date>a?r.review_date:a,"");
  $("latest-head").textContent="Deep dives · "+shortDate(day);
  const today=journal.records.filter(r=>r.review_date===day).sort((a,b)=>a.pair.localeCompare(b.pair));
  for(const r of today)root.append(reviewCard(r));
}
function historyRows() {
  if(!journal)return;
  const term=$("history-search").value.toUpperCase().trim();
  const day=$("history-day").value;
  const matches=journal.records.filter(r=>
    (day==="all"||r.review_date===day) &&
    (r.pair+" "+r.industry+" "+r.classification).toUpperCase().includes(term)
  ).sort((a,b)=>b.review_date.localeCompare(a.review_date)||a.pair.localeCompare(b.pair));
  $("history-count").textContent=matches.length+" of "+journal.records.length+" reviews";
  const body=$("history-rows");body.replaceChildren();
  $("history-empty").hidden=matches.length>0;
  for(const r of matches){
    const tr=el("tr");
    for(const [value,cls] of [[shortDate(r.review_date),"muted"],[r.pair,"paircell"],[r.industry,"muted"]]){
      tr.append(el("td",cls,value));
    }
    const status=el("td");status.append(classification(r.classification));tr.append(status);
    tr.append(el("td","",number(r.metrics?.correlation_90d,2)));
    tr.append(el("td","",number(r.metrics?.z_score_60d,2)));
    const btn=el("button","view-detail","Open review");
    btn.type="button";btn.addEventListener("click",()=>{
      const detail=$("archive-detail");detail.replaceChildren(reviewCard(r));
      detail.scrollIntoView({behavior:"smooth",block:"start"});
    });
    const last=el("td");last.append(btn);tr.append(last);body.append(tr);
  }
}
function scanRows() {
  const body=$("scan-rows");body.replaceChildren();
  if(!scan?.pairs)return;
  const term=$("scan-search").value.trim().toUpperCase(),status=$("scan-filter").value;
  const visible=scan.pairs.filter(r=>(status==="all"||r.status===status)&&
      (r.pair+" "+r.industry).toUpperCase().includes(term));
  $("scan-count").textContent=visible.length+" / "+scan.pairs.length;
  $("scan-empty").hidden=visible.length>0;
  for(const p of visible){
    const tr=el("tr");
    tr.append(el("td","paircell",p.pair),el("td","muted",p.industry),el("td","",number(p.correlation,2)),
              el("td","",number(p.z,2)),el("td","",number(p.p,4)),el("td","",number(p.q,4)));
    const status=el("td");status.append(classification(p.status));tr.append(status);body.append(tr);
  }
}
function drawSummary() {
  if(journal){
    $("m-total").textContent=journal.total_reviews;
    $("m-unique").textContent=journal.unique_pairs_reviewed;
    const last=journal.records.reduce((a,r)=>r.review_date>a?r.review_date:a,"");
    $("m-date").textContent=shortDate(last);
    const totalEligible=scan?.pairs?.filter(x=>x.status!=="data_unavailable").length||0;
    $("progress-text").textContent=totalEligible?journal.unique_pairs_reviewed+" of "+totalEligible+" currently reviewable pairs":"Unique pairs examined";
    $("progress-fill").style.width=totalEligible?Math.min(100,100*journal.unique_pairs_reviewed/totalEligible).toFixed(1)+"%":"0%";
    const options=[...new Set(journal.records.map(r=>r.review_date))].sort().reverse();
    const selected=$("history-day").value;
    $("history-day").replaceChildren();
    const all=el("option","","All dates");all.value="all";$("history-day").append(all);
    for(const day of options){const option=el("option","",shortDate(day));option.value=day;$("history-day").append(option);}
    $("history-day").value=options.includes(selected)?selected:"all";
    historyRows();latestReviews();
  }
  if(scan){
    $("m-broad").textContent=scan.summary.pairs_enumerated;
    $("scan-meta").textContent="Latest close: "+shortDate(scan.as_of)+" · "+scan.summary.pairs_tested_cointegration+" cointegration tests · "+scan.summary.research_candidates+" strict candidates · "+scan.summary.pairs_unavailable+" unavailable.";
    scanRows();
  }
}
async function fetchDocument(file){
  const response=await fetch(DATA_BASE+file+"?v="+Date.now(),{cache:"no-store"});
  if(!response.ok)throw Error(file+" unavailable (HTTP "+response.status+")");
  const raw=await response.text();
  return {raw, data:JSON.parse(raw)};
}
async function sha256(text){
  if(!window.crypto?.subtle)throw Error("Cryptographic integrity checker unavailable on this connection");
  const bytes=new TextEncoder().encode(text);
  const buffer=await window.crypto.subtle.digest("SHA-256",bytes);
  return Array.from(new Uint8Array(buffer),v=>v.toString(16).padStart(2,"0")).join("");
}
function hideUnverified(){
  scan=null;journal=null;
  $("latest-cards").replaceChildren(el("p","empty","Research is hidden until its independent audit and stored data checks agree."));
  $("history-rows").replaceChildren();
  $("scan-rows").replaceChildren();
  $("archive-detail").replaceChildren();
  for(const id of ["m-date","m-total","m-unique","m-broad"])$(id).textContent="—";
  $("source-link").hidden=true;
}
async function loadData(){
  $("last-run").textContent="Checking the published data against independent audit hashes…";
  const [a,b,c]=await Promise.allSettled([
    fetchDocument("daily_discovery.json"),fetchDocument("review_history.json"),fetchDocument("daily_audit.json")
  ]);
  try{
    if(a.status!=="fulfilled"||b.status!=="fulfilled"||c.status!=="fulfilled"){
      const failures=[a,b,c].filter(x=>x.status!=="fulfilled").map(x=>x.reason?.message||"unavailable");
      throw Error("Missing independently audited data: "+failures.join("; "));
    }
    const freshScan=a.value.data, freshJournal=b.value.data, report=c.value.data;
    if(report.status!=="PASS"||report.schema_version!==1)throw Error("Audit did not pass");
    if(freshScan.schema_version!==1||!Array.isArray(freshScan.pairs))throw Error("Scan format invalid");
    if(freshJournal.schema_version!==1||!Array.isArray(freshJournal.records))throw Error("Review history format invalid");
    if(freshScan.as_of!==report.market_date || freshJournal.records.length!==report.review_records)throw Error("Scan, reviews, and audit refer to different versions");
    const [scanDigest, historyDigest]=await Promise.all([sha256(a.value.raw),sha256(b.value.raw)]);
    if(scanDigest!==report.scan_sha256)throw Error("Scanner results do not match the independently audited file");
    if(historyDigest!==report.review_history_sha256)throw Error("Saved reviews do not match the independently audited file");
    if(report.input_prices_sha256!==freshScan.input_provenance?.sha256_uncompressed_csv)
      throw Error("Source price checkpoint does not match the audit");
    scan=freshScan;journal=freshJournal;
    const provenance=scan.input_provenance;
    if(/^stat-arb-dashboard\/data\/source-snapshots\/[0-9-]+-[a-f0-9]+\.csv\.gz$/.test(provenance.path)){
      $("source-link").href="https://github.com/uafadelaja-creator/monte-carlo-investment-lab/blob/main/"+provenance.path;
      $("source-link").hidden=false;
    }
    const legacy=report.legacy_reviews_without_preserved_input;
    $("verification").textContent="INDEPENDENT AUDIT PASSED · "+report.all_pairs_enumerated+
       " hypotheses checked against saved prices"+(legacy?" · "+legacy+" legacy review(s) lack source checkpoints":"");
    $("verification").className="passed";
    drawSummary();
    const newest=journal.records.reduce((acc,r)=>r.review_date>acc?r.review_date:acc,"");
    const age=(Date.now()-new Date(scan.generated_at_utc).getTime())/3600000;
    $("last-run").textContent="Latest verified scan: "+shortDate(scan.as_of)+" · "+
       scan.summary.pairs_tested_cointegration+" cointegration tests · Latest deep reviews: "+shortDate(newest)+
       (age>48?" · STALE SNAPSHOT: check the run log":"")+
       " · Scanned data are daily-close estimates, not live exchange quotes.";
    $("last-run").classList.toggle("error",age>48);
  }catch(error){
    hideUnverified();
    $("verification").textContent="UNVERIFIED · "+error.message;
    $("verification").className="failed";
    $("last-run").textContent="Results hidden: verification was not completed. Open the run log for details.";
    $("last-run").classList.add("error");
  }
}
async function loadRunStatus(){
  const url="https://api.github.com/repos/uafadelaja-creator/monte-carlo-investment-lab/actions/workflows/daily-pair-discovery.yml/runs?per_page=1";
  $("auto-refresh-label").textContent="Auto-refreshes every 2 minutes";
  try{
    const result=await fetch(url,{cache:"no-store",headers:{"Accept":"application/vnd.github+json"}});
    if(!result.ok)throw Error("GitHub run status HTTP "+result.status);
    const data=await result.json();
    const run=data.workflow_runs?.[0];
    if(!run)throw Error("No workflow run found");
    const state=run.status,conclusion=run.conclusion;
    const dot=$("run-dot");
    const running=state==="in_progress"||state==="queued"||state==="waiting"||state==="pending";
    const passed=state==="completed"&&conclusion==="success";
    dot.className="live-dot "+(running?"running":passed?"passed":"failed");
    $("run-status").textContent=running?
      "Daily scanner "+(state==="in_progress"?"running now":"queued"):
      passed?"Last automated scan finished successfully":"Latest scan "+(conclusion||state)+" — prior audited snapshot retained";
    const when=new Date(run.updated_at||run.created_at);
    $("run-explain").textContent="GitHub Actions: "+(Number.isFinite(when.getTime())?when.toLocaleString():"time unknown")+
      ". This is a live workflow-status monitor, not streaming market prices.";
    $("run-open").href=run.html_url;
  }catch(error){
    $("run-dot").className="live-dot";
    $("run-status").textContent="Live run status unavailable";
    $("run-explain").textContent="GitHub's public status API could not be reached ("+error.message+"). Saved research is independently checked below.";
  }
}

function init(){
  for(const button of document.querySelectorAll(".tab")){
    button.addEventListener("click",()=>activate(button.dataset.view));
  }
  $("show-latest").addEventListener("click",()=>{
    activate("latest");
    $("view-latest").scrollIntoView({behavior:"smooth",block:"start"});
  });
  $("show-scanner").addEventListener("click",()=>{
    activate("scan");
    $("view-scan").scrollIntoView({behavior:"smooth",block:"start"});
  });
  $("refresh").addEventListener("click",()=>{loadData();loadRunStatus();});
  $("history-search").addEventListener("input",historyRows);
  $("history-day").addEventListener("change",historyRows);
  $("scan-search").addEventListener("input",scanRows);
  $("scan-filter").addEventListener("change",scanRows);
  activate("latest");
  loadData().catch(err=>{$("last-run").textContent="Data request failed: "+err.message;$("last-run").classList.add("error");});
  loadRunStatus();
  window.setInterval(()=>{loadData();loadRunStatus();},120000);
}
document.addEventListener("DOMContentLoaded",init);
