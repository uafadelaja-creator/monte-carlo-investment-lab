/* PAIR//LAB Trade Research Workbench
 * Educational conditional plans and historical price-only paper replays.
 * Zero qualifying current trade alerts; this does NOT place or recommend trades.
 * No future data enters the rolling Z-score at the decision close.
 */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const NS = "http://www.w3.org/2000/svg";
  const money = n => (n < 0 ? "-$" : "$") + Math.abs(n).toFixed(2);
  const signed = n => (n > 0 ? "+" : "") + n.toFixed(2);
  const reportDate = str => new Date(str + "T12:00:00Z").toLocaleDateString("en-US",{timeZone:"UTC",month:"short",day:"numeric",year:"numeric"});
  const mean = array => array.reduce((s,v)=>s+v,0)/array.length;
  const getN = id => Number($(id).value);
  const tickers = ["AVAV/KTOS","KTOS/ONDS","SOFI/NU","AMD/MRVL","NVDA/TSM"];
  let pairs = [], series = null, dates = null, current = "AVAV/KTOS", chosenDate = "", rowsCache = new Map();
  let currentReplay = null;
  const latestPlan = () => pairs.find(x=>x.pair === current);
  function status(p) {
    const parts = [];
    if (p.p >= .05) parts.push("cointegration p is not below 0.05");
    if (p.q >= .05) parts.push("false-discovery-adjusted q is not below 0.05");
    if (p.correlation <= .75) parts.push("90-day correlation is not above 0.75");
    if (Math.abs(p.z) < 2) parts.push("the latest Z-score is not beyond ±2");
    if (!(p.beta > .1)) parts.push("the fitted positive hedge slope is unsuitable");
    return parts;
  }
  function alignedData(p) {
    if (rowsCache.has(p.pair)) return rowsCache.get(p.pair);
    const arr = [];
    for (let i=0;i<dates.length;i++) {
      const a=series[p.a][i],b=series[p.b][i];
      if (Number.isFinite(a)&&a>0&&Number.isFinite(b)&&b>0) arr.push({date:dates[i],a,b,z:null});
    }
    for (let t=252;t<arr.length;t++) {
      const sample=arr.slice(t-252,t);
      const x=sample.map(v=>Math.log(v.b)), y=sample.map(v=>Math.log(v.a));
      const mx=mean(x),my=mean(y);
      const cov=x.reduce((s,v,i)=>s+(v-mx)*(y[i]-my),0);
      const variance=x.reduce((s,v)=>s+(v-mx)*(v-mx),0);
      if(variance<1e-14) continue;
      const beta=cov/variance,alpha=my-beta*mx;
      const residual=sample.map(v=>Math.log(v.a)-alpha-beta*Math.log(v.b));
      const last=residual.slice(-60), center=mean(last);
      const sd=Math.sqrt(last.reduce((s,v)=>s+(v-center)*(v-center),0)/59);
      if(sd>1e-10) arr[t].z=(Math.log(arr[t].a)-alpha-beta*Math.log(arr[t].b)-center)/sd;
    }
    rowsCache.set(p.pair,arr);
    return arr;
  }
  const rules=()=>({entry:getN("plan-entry"), exit:getN("plan-exit"),stop:getN("plan-stop"),
    hold:getN("plan-hold"), gross:getN("plan-gross"),fees:getN("plan-fees"),borrow:getN("plan-borrow")});
  function renderPlan() {
    const p=latestPlan(),r=rules();
    if(!p) return;
    $("plan-selected").textContent = p.pair + " · snapshot " + reportDate("2026-11-11");
    $("plan-current").textContent = "Latest modeled Z " + signed(p.z) + " · r " + p.correlation.toFixed(2) +
      " · p " + p.p.toFixed(3) + " · q " + p.q.toFixed(3);
    const why=status(p);
    const eligible=why.length===0;
    $("plan-verdict").textContent = eligible ? "Numerical screen passes — additional risks unverified" : "NO CURRENT QUALIFIED ENTRY";
    $("plan-verdict").className = "plan-flag";
    const direction=p.z>=0 ? "SHORT "+p.a+" / LONG "+p.b : "LONG "+p.a+" / SHORT "+p.b;
    const condition="Wait for a NEW observed spread crossing at or beyond |Z| = "+r.entry.toFixed(2)+
      " using trailing-only data, cointegration p < 0.05, FDR q < 0.05, 90-day correlation > 0.75, a sensible positive hedge relationship, and no material earnings or business break.";
    $("plan-condition").textContent=condition;
    $("plan-direction").textContent="If future Z is positive: SHORT "+p.a+" / LONG "+p.b+
      ". If future Z is negative: LONG "+p.a+" / SHORT "+p.b+
      ". Current sign alone does not authorize a trade. The historical beta shown elsewhere is not a share quantity.";
    $("plan-exit-text").textContent="Research exit at |Z| ≤ "+r.exit.toFixed(2)+
      ", invalidation if |Z| ≥ "+r.stop.toFixed(2)+
      ", or time exit after "+r.hold+" sessions. All observations trigger an exit on the following session in the illustration.";
    $("plan-reject").textContent=why.length ? "Why this pair is not ready: "+why.join("; ")+
      ". The selected pair must be re-tested before any real position." :
      "The numerical snapshot alone does not validate earnings/news breaks, position sizing, short availability or out-of-sample net returns.";
    $("plan-notional-description").textContent="Illustrative gross exposure "+money(r.gross)+
      " (about "+money(r.gross/2)+" per leg). Not account cash required or maximum loss; actual shorts require margin/borrow, and losses can exceed this exposure.";
    updateEvents(false);
  }
  function findCrossings(arr,threshold) {
    const events=[];
    for(let i=253;i<arr.length-1;i++){
      const z=arr[i].z,prior=arr[i-1].z;
      if(z===null||prior===null)continue;
      if(Math.abs(z)>=threshold && (Math.abs(prior)<threshold || Math.sign(prior)!==Math.sign(z))){
        events.push({index:i,date:arr[i].date,z});
      }
    }
    return events.reverse();
  }
  function updateEvents(preserve=true){
    const p=latestPlan();
    if(!p)return;
    const list=findCrossings(alignedData(p),rules().entry),select=$("plan-event");
    if(!preserve)chosenDate="";
    select.replaceChildren();
    if(!list.length) {
      const opt=document.createElement("option");opt.value="";opt.textContent="No historical threshold crosses in chart history";select.append(opt);
      $("plan-event-count").textContent="0 past crossings for this selected Z threshold";
      currentReplay=null; drawReplay(null); return;
    }
    list.forEach(event=>{
      const option=document.createElement("option");option.value=event.date;
      option.textContent=reportDate(event.date)+" · Z "+signed(event.z);select.append(option);
    });
    // Select most recent completed opportunity if possible, not the best-returning one.
    const rows=alignedData(p),hold=rules().hold;
    const completed=list.find(v=>v.index+hold+2 < rows.length);
    if(!list.some(x=>x.date===chosenDate)) chosenDate=(completed||list[0]).date;
    select.value=chosenDate;
    $("plan-event-count").textContent=list.length+" historical price-only threshold crossings; this is NOT a list of statistically qualified signals";
    currentReplay=paperReplay(p,chosenDate);
    drawReplay(currentReplay);
  }
  function paperReplay(p,date){
    const r=rules(),arr=alignedData(p),trigger=arr.findIndex(x=>x.date===date);
    if(trigger<0||!arr[trigger+1])return null;
    const entry=trigger+1,start=arr[entry],signal=arr[trigger].z;
    const shortA=signal>0,half=r.gross/2;
    let exitIndex=arr.length-1,reason="Sample ends before a modeled exit (unclosed paper mark)",completed=false;
    // Entry occurs at the next session's CLOSE — a simplified academic assumption.
    // The signal at the entry close cannot be used to transact until the next close.
    for(let i=entry;i<arr.length-1;i++) {
      const age=i-entry+1,z=arr[i].z;
      let why="";
      if(Number.isFinite(z)&&Math.abs(z)<=r.exit)why="Spread returned toward modeled center";
      else if(Number.isFinite(z)&&Math.abs(z)>=r.stop)why="Spread crossed invalidation band";
      else if(age>=r.hold)why="Maximum holding period";
      if(why){exitIndex=i+1;reason=why;completed=true;break;}
    }
    if(exitIndex<=entry){return null;}
    const line=[];
    for(let i=entry;i<=exitIndex;i++){
      const aChange=arr[i].a/start.a-1,bChange=arr[i].b/start.b-1;
      const legA=shortA?-half*aChange:half*aChange;
      const legB=shortA?half*bChange:-half*bChange;
      const gross=legA+legB;
      const age=i-entry;const shortRatio=shortA?arr[i].a/start.a:arr[i].b/start.b;
      const entryCosts=r.gross*r.fees/10000;
      const exitGross=half*(arr[i].a/start.a+arr[i].b/start.b);
      const exitCosts=(completed&&i===exitIndex)?exitGross*r.fees/10000:0;
      const carry=half*(r.borrow/100)/252*age;
      line.push({date:arr[i].date,age,gross,net:gross-entryCosts-exitCosts-carry,z:arr[i].z});
    }
    const final=line.at(-1);
    return {pair:p.pair,sign:signal,trigger:arr[trigger],entryDate:start.date,
      entryA:start.a,entryB:start.b,endDate:arr[exitIndex].date,endA:arr[exitIndex].a,endB:arr[exitIndex].b,
      reason,completed,half,final,line};
  }
  function svg(name,attrs={},text) {
    const el=document.createElementNS(NS,name);
    for(const[k,v]of Object.entries(attrs))el.setAttribute(k,String(v));
    if(text!==undefined)el.textContent=String(text);
    return el;
  }
  function drawReplay(replay) {
    const host=$("plan-equity-chart");host.replaceChildren();host.setAttribute("viewBox","0 0 660 220");
    if(!replay){
      host.append(svg("text",{x:330,y:110,fill:"#9ab9cd","text-anchor":"middle"},"No price-only historical replay available"));
      $("plan-result").textContent="Choose a pair and a historical threshold crossing.";
      $("plan-net").textContent="—";$("plan-pnl-gross").textContent="—";$("plan-days").textContent="—";
      $("plan-reason").textContent="Historical prices and parameters are needed.";return;
    }
    const {line,final,completed}=replay;
    const W=660,H=220,l=47,top=15,bot=32,right=14,x=i=>l+(W-l-right)*i/Math.max(1,line.length-1);
    let ys=line.flatMap(d=>[d.net,d.gross,0]);
    let min=Math.min(...ys),max=Math.max(...ys),pad=Math.max(1,(max-min)*.13);
    min-=pad;max+=pad;
    const y=v=>top+(H-top-bot)*(max-v)/(max-min);
    for(let i=0;i<5;i++){const v=min+(max-min)*i/4;
      host.append(svg("line",{x1:l,x2:W-right,y1:y(v),y2:y(v),stroke:"#29445b","stroke-dasharray":"3 5"}));
      host.append(svg("text",{x:l-7,y:y(v)+3,fill:"#8facbf","font-size":"10","text-anchor":"end"},money(v)));
    }
    host.append(svg("line",{x1:l,x2:W-right,y1:y(0),y2:y(0),stroke:"#cfbe87","stroke-dasharray":"4 4"}));
    function path(key,color){
      const d=line.map((p,i)=>(i?"L":"M")+x(i).toFixed(1)+","+y(p[key]).toFixed(1)).join(" ");
      host.append(svg("path",{d,fill:"none",stroke:color,"stroke-width":"2.6","stroke-linejoin":"round","stroke-linecap":"round"}));
    }
    path("gross","#a9b8cf");path("net","#6fe6ff");
    host.append(svg("circle",{cx:x(line.length-1),cy:y(final.net),r:5,fill:final.net<0?"#ff889f":"#b9fa91"}));
    host.append(svg("text",{x:l,y:H-6,fill:"#8eacc3","font-size":"10"},reportDate(replay.entryDate)));
    host.append(svg("text",{x:W-right,y:H-6,fill:"#8eacc3","font-size":"10","text-anchor":"end"},reportDate(replay.endDate)));
    $("plan-pnl-gross").textContent=money(final.gross);
    $("plan-net").textContent=money(final.net);
    $("plan-net").className=final.net<0?"neg":"pos";
    $("plan-days").textContent=final.age+" sessions";
    $("plan-result").textContent=(completed?"CLOSED (HYPOTHETICAL)":"OPEN / UNRESOLVED AT DATA END")+
      " · "+reportDate(replay.entryDate)+" → "+reportDate(replay.endDate);
    $("plan-reason").textContent=replay.reason+
      ". A signal was observed on "+reportDate(replay.trigger.date)+", with assumed entry at the following session's close. "+
      (completed?"Exit was modeled on a later daily close.":"No complete closing observation exists; this is an unrealized mark.");
  }
  function exportPlan() {
    const p=latestPlan(),r=rules();if(!p)return;
    const why=status(p);
    const lines=[
      "PAIR//LAB — CONDITIONAL RESEARCH PLAN (NOT A LIVE TRADE ALERT)",
      "Prices and statistics through 2026-11-11. Generated from a static snapshot.",
      "Pair: "+p.pair+" | Z: "+signed(p.z)+" | 90d r: "+p.correlation+" | EG p: "+p.p+" | FDR q: "+p.q,
      "Present classification: "+(why.length?"NOT QUALIFIED":"NUMERICAL GATES ONLY; NEWS/BORROW VALIDATION PENDING"),
      "Missing checks: "+(why.join("; ")||"news, risk, executable pricing"),
      "Hypothetical entry: NEW |Z| >= "+r.entry+" after all statistical/structural gates pass",
      "Direction if Z positive: SHORT "+p.a+"; LONG "+p.b,
      "Direction if Z negative: LONG "+p.a+"; SHORT "+p.b,
      "Mean-reversion exit: |Z| <= "+r.exit+"; invalidation: |Z| >= "+r.stop+"; max time "+r.hold+" sessions",
      "Gross illustrative exposure: $"+r.gross+" (approximately half each leg)",
      "Assumed per-fill cost: "+r.fees+" bps; annual short-carry: "+r.borrow+"%",
      "Historic replay: "+(currentReplay?(currentReplay.entryDate+" to "+currentReplay.endDate+
        " net marked P/L "+money(currentReplay.final.net)+" ("+currentReplay.reason+")"):"none"),
      "WARNING: Close-to-close academic assumptions, not executable fills, not a verified edge. Shorting needs margin/borrow and losses can exceed notional. Price adjustment unverified."
    ];
    const blob=new Blob([lines.join("\n")+"\n"],{type:"text/plain"});
    const link=document.createElement("a"),url=URL.createObjectURL(blob);
    link.href=url;link.download="pairlab-research-plan-"+p.pair.replace("/","-")+".txt";link.click();
    setTimeout(()=>URL.revokeObjectURL(url),3000);
  }
  async function init() {
    try {
      const loads=await Promise.all(["screen.json","prices-1.json","prices-2.json"].map(async name=>{
        const resp=await fetch("./data/"+name,{cache:"no-store"});
        if(!resp.ok)throw Error("HTTP "+resp.status+" for "+name);
        return resp.json();
      }));
      const [snapshot,a,b]=loads;
      if(a.as_of!==snapshot.as_of||a.as_of!==b.as_of||
        a.dates.length!==b.dates.length||a.dates.some((x,i)=>x!==b.dates[i]))throw Error("Price dates don't match audited snapshot.");
      pairs=snapshot.pairs;dates=a.dates;series={...a.series,...b.series};
      const select=$("plan-pair");select.replaceChildren();
      for(const p of [...pairs].sort((a,b)=>a.pair.localeCompare(b.pair))){
        const opt=document.createElement("option");opt.value=p.pair;opt.textContent=p.pair+" · "+p.industry;select.append(opt);
      }
      select.onchange=()=>{current=select.value;chosenDate="";window.dispatchEvent(new CustomEvent("pairlab:request",{detail:{pair:current}}));renderPlan();};
      const onchange=()=>{const stop=$("plan-stop");if(getN("plan-stop")<=getN("plan-entry"))stop.value=Math.min(4,getN("plan-entry")+.5);renderPlan()};
      for(const id of ["plan-entry","plan-exit","plan-stop","plan-hold","plan-gross","plan-fees","plan-borrow"]){
        $(id).addEventListener("input",onchange);
        $(id).addEventListener("change",onchange);
      }
      $("plan-event").onchange=()=>{chosenDate=$("plan-event").value;currentReplay=paperReplay(latestPlan(),chosenDate);drawReplay(currentReplay);};
      $("plan-download").onclick=exportPlan;
      document.querySelectorAll("[data-proposal-pair]").forEach(button=>{
        button.onclick=()=>{const pair=button.dataset.proposalPair;if(!pairs.some(p=>p.pair===pair))return;
          current=pair;chosenDate="";select.value=pair;
          document.querySelectorAll("[data-proposal-pair]").forEach(b=>b.setAttribute("aria-pressed",String(b===button)));
          window.dispatchEvent(new CustomEvent("pairlab:request",{detail:{pair}}));
          renderPlan();
          document.getElementById("plan-builder").scrollIntoView({behavior:"smooth",block:"start"});
        };
      });
      window.addEventListener("pairlab:selected",event=>{
        if(pairs.some(p=>p.pair===event.detail.pair)&&current!==event.detail.pair){
          current=event.detail.pair;select.value=current;chosenDate="";renderPlan();
        }
      });
      current=window.pairlabCurrentPair&&pairs.some(p=>p.pair===window.pairlabCurrentPair)?
        window.pairlabCurrentPair:current;
      select.value=current;renderPlan();
    }catch(error){
      $("plan-result").textContent="Plan builder unavailable: "+error.message;
      $("plan-reason").textContent="Refresh the website. Research plans are never live broker orders.";
    }
  }
  init();
})();