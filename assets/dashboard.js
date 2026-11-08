'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const tickers = ['ARKK','QUAL','SPY'];
  const colors = {ARKK:'#8961c3',QUAL:'#4b80c0',SPY:'#167d70'};
  const money = n => new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(n);
  const pct = n => n == null ? '—' : `${(n*100).toFixed(1)}%`;
  const dot = t => `<i class="dot" style="background:${colors[t]}"></i>${t}`;
  let data;
  function metric(label,value,note,badge='') {
    return `<article class="metric"><div class="metric-top"><span>${label}</span>${badge ? `<span class="ticker">${badge}</span>`:''}</div><div class="metric-value">${value}</div><div class="metric-note">${note}</div></article>`;
  }
  function chart(id, series, labels, {band=null,deposit=null,readout,format=money}={}) {
    const el=$(id), w=Math.max(280,el.clientWidth||760),h=el.clientHeight||300,left=w<500?46:60,right=20,top=20,bottom=38;
    const values=series.flatMap(s=>s.values).concat(band ? band.upper:[],deposit||[]);
    const max=Math.max(...values)*1.08,min=0,n=labels.length;
    const x=i=>left+i/(n-1)*(w-left-right),y=v=>top+(max-v)/(max-min)*(h-top-bottom);
    const path=vs=>vs.map((v,i)=>`${i?'L':'M'}${x(i).toFixed(2)},${y(v).toFixed(2)}`).join(' ');
    let svg='';
    for(let i=0;i<=4;i++) {const value=max*i/4,yy=y(value);svg+=`<line class="grid-line" x1="${left}" x2="${w-right}" y1="${yy}" y2="${yy}"/><text x="${left-10}" y="${yy+4}" text-anchor="end">${value>=1000 ? '$'+(value/1000).toFixed(value>=10000?0:1)+'k' : money(value)}</text>`;}
    [...new Set(w<500 ? [0,Math.round((n-1)/2),n-1] : [0,Math.round((n-1)/4),Math.round((n-1)/2),Math.round((n-1)*.75),n-1])].forEach(i=>svg+=`<text x="${x(i)}" y="${h-10}" text-anchor="middle">${labels[i]}</text>`);
    if(band) {const points=band.upper.map((v,i)=>`${x(i)},${y(v)}`).concat(band.lower.map((v,i)=>`${x(i)},${y(v)}`).reverse()).join(' ');svg+=`<polygon points="${points}" fill="${band.color}" opacity=".12"/>`;}
    if(deposit) svg+=`<path d="${path(deposit)}" fill="none" stroke="#93a1a7" stroke-dasharray="5 5" stroke-width="1.5"/>`;
    series.forEach(s=>svg+=`<path d="${path(s.values)}" fill="none" stroke="${s.color}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>`);
    svg+='<g class="cursor"></g>';
    el.setAttribute('viewBox',`0 0 ${w} ${h}`);el.setAttribute('preserveAspectRatio','none');el.setAttribute('tabindex','0');el.innerHTML=svg;
    let selected=n-1;
    const inspect=i=>{selected=Math.max(0,Math.min(n-1,i));el.querySelector('.cursor').innerHTML=`<line x1="${x(selected)}" x2="${x(selected)}" y1="${top}" y2="${h-bottom}" stroke="#9aadb4" stroke-dasharray="3 3"/>`+series.map(s=>`<circle cx="${x(selected)}" cy="${y(s.values[selected])}" r="4" fill="${s.color}" stroke="white" stroke-width="2"/>`).join('');$(readout).textContent=labels[selected]+' · '+series.map(s=>`${s.name}: ${format(s.values[selected])}`).join(' · ')+(band ? ` · Range: ${format(band.lower[selected])}–${format(band.upper[selected])}`:'');};
    el.onpointermove=e=>{const rect=el.getBoundingClientRect();inspect(Math.round(((e.clientX-rect.left)/rect.width*w-left)/(w-left-right)*(n-1)));};
    el.onpointerdown=el.onpointermove;
    el.onkeydown=e=>{if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();inspect(selected+(e.key==='ArrowLeft'?-1:1));}};
    el.onfocus=()=>inspect(selected);
  }
  function history() {
    $('history-metrics').innerHTML=data.risk_metrics.map(r=>metric('Historical annualized return',pct(r.cagr),'CAGR · completed monthly history',dot(r.ticker))).join('');
    $('risk-table').innerHTML=data.risk_metrics.map(r=>`<tr><td>${dot(r.ticker)}</td><td>${pct(r.cagr)}</td><td>${pct(r.annualized_volatility)}</td><td>${pct(r.historical_max_drawdown_month_end)}</td><td>${pct(r.best_month)}</td><td>${pct(r.worst_month)}</td></tr>`).join('');
    chart('history-chart',tickers.map(t=>({name:t,color:colors[t],values:data.observed.growth[t].map(x=>x*1000)})),data.observed.dates,{readout:'history-readout'});
  }
  function selection() {
    const ticker=$('portfolio').value,months=Number($('horizon').value),weekly=$('weekly').value,scenario=$('scenario').value;
    const view=data.views[weekly][scenario],rows=view.summary.filter(r=>r.months===months);
    return {ticker,months,weekly,scenario,view,rows,row:rows.find(r=>r.ticker===ticker)};
  }
  function simulation() {
    const {ticker,months,weekly,scenario,view,rows,row}=selection();
    $('simulation-metrics').innerHTML=metric('Median ending value',money(row.median_ending_value),`${money(row.contributed_usd)} total deposited`,ticker)+metric('Frequency of a loss',pct(row.prob_loss),'Ending below total contributions')+metric('Median maximum drawdown',pct(row.median_max_drawdown),'Simulated peak-to-trough loss');
    const f=view.fan[ticker],med=[500,...f.median.slice(0,months)],lower=[500,...f.p05.slice(0,months)],upper=[500,...f.p95.slice(0,months)];
    $('fan-dot').style.background=colors[ticker];$('fan-title').textContent=`${ticker} · ${months}-month investment outlook`;
    $('fan-subtitle').textContent=`$500 starting investment · ${money(Number(weekly))}/week · ${scenario==='baseline'?'Historical bootstrap':'Hypothetical initial shock'}`;
    $('fan-readout').textContent='Hover, tap, or use arrow keys on the chart to inspect a month.';
    chart('fan-chart',[{name:'Median',color:colors[ticker],values:med}],Array.from({length:months+1},(_,i)=>`M${i}`),{band:{lower,upper,color:colors[ticker]},deposit:Array.from({length:months+1},(_,i)=>500+Number(weekly)*52/12*i),readout:'fan-readout'});
    $('comparison').innerHTML=rows.map(r=>`<tr${r.ticker===ticker?' style="background:#f4f9f6"':''}><td>${dot(r.ticker)}</td><td>${money(r.median_ending_value)}</td><td>${money(r.p05)}–${money(r.p95)}</td><td>${pct(r.prob_loss)}</td><td>${pct(r.prob_beat_spy)}</td><td>${pct(r.median_max_drawdown)}</td></tr>`).join('');
    $('scenario-note').textContent=scenario==='shock'?'Hypothetical extra first-month shocks: ARKK −25%, QUAL −15%, SPY −18%. These are assumptions, not historical observations.':'Loss and outperformance frequencies are conditional on the sampled history. They are not validated probabilities of future outcomes.';
  }
  function activate(tab) {
    const hist=tab==='history';
    ['history','monte'].forEach(key=>{const active=(key==='history')===hist;$(key+'-view').hidden=!active;$('tab-'+key).setAttribute('aria-selected',String(active));$('tab-'+key).tabIndex=active?0:-1;});
    if(!hist) simulation();
  }
  function research() {
    $('correlation-table').innerHTML=tickers.map(t=>`<tr><td>${dot(t)}</td>${tickers.map(u=>`<td style="background:rgba(22,125,112,${data.correlations[t][u]*.09})">${data.correlations[t][u].toFixed(2)}</td>`).join('')}</tr>`).join('');
    $('sensitivity-table').innerHTML=data.block_sensitivity_36m.map(r=>`<tr><td>${r.scenario.match(/_(\d+)m$/)[1]} ${r.scenario.endsWith('_1m')?'month':'months'}</td><td>${dot(r.ticker)}</td><td>${money(r.median_ending_value)}</td><td>${money(r.p05)}–${money(r.p95)}</td><td>${pct(r.prob_loss)}</td><td>${pct(r.prob_beat_spy)}</td></tr>`).join('');
  }
  async function init() {
    try {
      const response=await fetch('results/historical_dashboard_data.json');if(!response.ok) throw Error('Data could not be loaded.');data=await response.json();
      if(document.body.dataset.page==='research') {research();return;}
      history();simulation();
      let resizeTimer; window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{if(!$('history-view').hidden) history();else simulation();},120);});
      ['history','monte'].forEach(tab=>{$('tab-'+tab).onclick=()=>activate(tab);$('tab-'+tab).onkeydown=e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();const next=e.key==='Home'?'history':e.key==='End'?'monte':tab==='history'?'monte':'history';activate(next);$('tab-'+next).focus();}};});
      ['portfolio','horizon','weekly','scenario'].forEach(id=>$(id).onchange=simulation);
      $('download-comparison').onclick=()=>{const {rows,weekly,months,scenario}=selection();const fields=Object.keys(rows[0]);const text=[fields.join(','),...rows.map(r=>fields.map(f=>r[f]??'').join(','))].join('\n');const url=URL.createObjectURL(new Blob([text],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`historical_${scenario}_${months}m_${weekly}weekly.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
    } catch(error) {$('load-error').hidden=false;$('load-error').textContent='Unable to load historical results. Refresh this page or use the downloadable files on Research & data.';console.error(error);}
  }
  init();
})();
