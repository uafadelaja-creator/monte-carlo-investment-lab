/* PAIR//LAB — free TradingView widget integration.
 * Uses TradingView's publicly documented advanced-chart embed script:
 * https://www.tradingview.com/widget-docs/widgets/charts/advanced-chart/
 * The widgets are separately hosted chart views; NO price data or user
 * TradingView-account information is sent back to this research dashboard.
 * Widgets may show delayed quotes depending on exchange licensing.
 */
(function () {
  "use strict";
  const WIDGET_URL = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
  const TV_SITE = "https://www.tradingview.com";
  const MARKET = Object.freeze({
    "AVAV":"NASDAQ","KTOS":"NASDAQ","ONDS":"NASDAQ","SOFI":"NASDAQ",
    "NU":"NYSE","NVDA":"NASDAQ","MU":"NASDAQ","WDC":"NASDAQ",
    "SNDK":"NASDAQ","RKLB":"NASDAQ","PL":"NYSE","TSM":"NYSE",
    "AMD":"NASDAQ","MRVL":"NASDAQ","INTC":"NASDAQ","AVGO":"NASDAQ",
    "GOOG":"NASDAQ","META":"NASDAQ","MSFT":"NASDAQ","ORCL":"NYSE"
  });
  const $ = id => document.getElementById(id);
  const symbol = ticker => MARKET[ticker] ? MARKET[ticker] + ":" + ticker : null;
  const chartUrl = ticker => MARKET[ticker] ?
    TV_SITE + "/symbols/" + MARKET[ticker] + "-" + ticker + "/" : null;
  let active = "", initialized = false;
  function getPair(pair) {
    if (typeof pair !== "string") return null;
    const chunks = pair.split("/");
    if (chunks.length !== 2 || !chunks.every(t => Object.prototype.hasOwnProperty.call(MARKET,t))) return null;
    return chunks;
  }
  function widgetOptions(ticker) {
    return {
      autosize:true, symbol:symbol(ticker), interval:"D", timezone:"Etc/UTC",
      theme:"dark", style:"1", locale:"en",
      backgroundColor:"#0b1727", gridColor:"rgba(115,167,199,0.11)",
      hide_top_toolbar:false, hide_side_toolbar:false, hide_legend:false,
      hide_volume:false, allow_symbol_change:false, save_image:true,
      withdateranges:true, calendar:false, details:false, hotlist:false,
      studies:[], compareSymbols:[], watchlist:[],
      show_popup_button:true, popup_width:"1150", popup_height:"680",
      support_host:TV_SITE
    };
  }
  function note(host,message,ticker){
    const div=document.createElement("div");
    div.className="tv-pending";
    div.textContent=message;
    host.replaceChildren(div);
    const a=document.createElement("a");
    a.href=chartUrl(ticker) || TV_SITE;
    a.target="_blank";a.rel="noopener noreferrer";
    a.textContent="Open on TradingView";
    a.style.color="#78ddff";a.style.marginTop="12px";
    div.append(document.createElement("br"),a);
  }
  function buildWidget(ticker, side) {
    const host=$("tv-host-"+side);
    const header=$("tv-symbol-"+side);
    const exchange=$("tv-exchange-"+side);
    const link=$("tv-link-"+side);
    const fullSymbol=symbol(ticker);
    if (!host || !header || !exchange || !link || !fullSymbol) return;
    header.textContent=ticker;
    exchange.textContent=fullSymbol;
    link.href=chartUrl(ticker);
    link.textContent="Open in TradingView";
    host.replaceChildren();
    const container=document.createElement("div");
    container.className="tradingview-widget-container";
    const target=document.createElement("div");
    target.className="tradingview-widget-container__widget";
    const attribution=document.createElement("div");
    attribution.className="tradingview-widget-copyright";
    const a=document.createElement("a");
    a.href=chartUrl(ticker); a.target="_blank";a.rel="noopener nofollow noreferrer";
    a.textContent=ticker+" chart";
    const by=document.createElement("span");
    by.textContent=" by TradingView";
    attribution.append(a,by);
    const script=document.createElement("script");
    script.type="text/javascript";
    script.src=WIDGET_URL;
    script.async=true;
    script.textContent=JSON.stringify(widgetOptions(ticker));
    script.addEventListener("error",()=> {
      if(host.contains(container))note(host,"The chart provider could not load. Check browser privacy settings or open the chart on TradingView.",ticker);
    });
    container.append(target,attribution,script);
    host.append(container);
  }
  function setPair(input,force=false) {
    const ticks=getPair(input);
    if (!ticks) return;
    if (active===input && !force) return;
    active=input;
    $("tv-pair-name").textContent=input;
    $("tv-chip-a").textContent=ticks[0];
    $("tv-chip-b").textContent=ticks[1];
    $("tv-data-label").textContent="TradingView chart feed • exchange delay varies";
    buildWidget(ticks[0],"a");
    buildWidget(ticks[1],"b");
    $("tv-chart-status").textContent="Showing "+ticks[0]+" and "+ticks[1]+
      ". Charts refresh from TradingView's own feed; PAIR//LAB's statistical analysis remains fixed to November 11, 2026.";
  }
  function init() {
    if(initialized)return;
    if(!$("tradingview-charts") || !$("tv-host-a") || !$("tv-host-b"))return;
    initialized=true;
    $("tv-reload").addEventListener("click",()=>setPair(active || "KTOS/ONDS",true));
    window.addEventListener("pairlab:selected",event=>{
      const pair=event && event.detail && event.detail.pair;
      if(getPair(pair))setPair(pair);
    });
    // Existing research scripts set this when changing a pair from the table,
    // chart selector, or conditional-plan panel.
    setPair(getPair(window.pairlabCurrentPair) ? window.pairlabCurrentPair : "KTOS/ONDS");
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);
  else init();
})();
