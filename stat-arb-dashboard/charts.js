/* PAIR//LAB historical chart module.
   All lines originate from dated third-party CLOSE prices frozen through 2026-11-11.
   No plotted crossing is claimed to be an executed or verified trade. */
(function () {
  "use strict";
  const SVG = "http://www.w3.org/2000/svg";
  const RANGE_DAYS = { "1M": 21, "3M": 63, "6M": 126, "1Y": 252 };
  const WIDTH = 720, HEIGHT = 260, LEFT = 51, RIGHT = 22, TOP = 16, BOTTOM = 32;
  const $ = (id) => document.getElementById(id);
  const fmt = (n, d = 2) => Number(n).toFixed(d);
  const dollars = (x) => "$" + Number(x).toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2});
  const dateDisplay = (s) => new Date(s + "T12:00:00Z").toLocaleDateString("en-US", {month: "short", day: "numeric", year: "numeric", timeZone: "UTC"});
  let history = null, allPairs = [], activePair = null, range = "3M";
  const cache = new Map();

  function element(tag, properties, label) {
    const e = document.createElementNS(SVG, tag);
    for (const [k, v] of Object.entries(properties || {})) e.setAttribute(k, String(v));
    if (label !== undefined) e.textContent = String(label);
    return e;
  }
  function mean(xs) { return xs.reduce((a, b) => a + b, 0) / xs.length; }
  function estimate(train) {
    const x = train.map((v) => Math.log(v.b));
    const y = train.map((v) => Math.log(v.a));
    const mx = mean(x), my = mean(y);
    let cov = 0, variance = 0;
    for (let i = 0; i < x.length; i++) {
      cov += (x[i] - mx) * (y[i] - my);
      variance += (x[i] - mx) ** 2;
    }
    if (variance < 1e-14) return null;
    const beta = cov / variance, alpha = my - beta * mx;
    const residual = x.map((z, i) => y[i] - alpha - beta * z);
    const last = residual.slice(-60), center = mean(last);
    const sd = Math.sqrt(last.reduce((s, v) => s + (v - center) ** 2, 0) / 59);
    return Number.isFinite(sd) && sd > 1e-10 ? {beta, alpha, center, sd} : null;
  }
  function buildPair(pair) {
    if (cache.has(pair.pair)) return cache.get(pair.pair);
    const aa = history.series[pair.a], bb = history.series[pair.b];
    if (!aa || !bb) throw Error("Missing price series for " + pair.pair);
    const aligned = [];
    history.dates.forEach((date, i) => {
      const a = aa[i], b = bb[i];
      if (Number.isFinite(a) && Number.isFinite(b) && a > 0 && b > 0) {
        aligned.push({date, a, b, z: null});
      }
    });
    // The day's own observation never enters its 252-day parameter-estimation window.
    for (let i = 252; i < aligned.length; i++) {
      const fit = estimate(aligned.slice(i - 252, i));
      if (fit) aligned[i].z = (Math.log(aligned[i].a) - fit.alpha -
          fit.beta * Math.log(aligned[i].b) - fit.center) / fit.sd;
    }
    cache.set(pair.pair, aligned);
    return aligned;
  }
  function svgPlot(id, rows, configuration) {
    const svg = $(id);
    svg.replaceChildren();
    svg.setAttribute("viewBox", "0 0 " + WIDTH + " " + HEIGHT);
    svg.setAttribute("tabindex", "0");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", configuration.label);
    const usableWidth = WIDTH - LEFT - RIGHT, usableHeight = HEIGHT - TOP - BOTTOM;
    const xs = (i) => LEFT + usableWidth * (i / Math.max(1, rows.length - 1));
    const allY = configuration.lines.flatMap((line) => line.values).filter(Number.isFinite);
    if (!rows.length || !allY.length) {
      svg.append(element("text", {x: WIDTH / 2, y: HEIGHT / 2, fill: "#b9cada", "text-anchor": "middle"}, "Not enough observations for this period"));
      configuration.onInspect(null);
      return;
    }
    const values = [...allY, ...(configuration.guides || []).map(g => g.value)];
    let min = Math.min(...values), max = Math.max(...values);
    if (max - min < .00001) { min -= 1; max += 1; }
    const padding = (max - min) * .11;
    min -= padding; max += padding;
    const ys = (v) => TOP + usableHeight * (max - v) / (max - min);

    for (let i = 0; i <= 4; i++) {
      const y = TOP + usableHeight * i / 4;
      const v = max - (max - min) * i / 4;
      svg.append(element("line", {x1: LEFT, x2: WIDTH - RIGHT, y1: y, y2: y,
        stroke: "#294154", "stroke-width": 1, "stroke-dasharray": "3 6"}));
      svg.append(element("text", {x: LEFT - 9, y: y + 4, fill: "#92a7bd", "text-anchor": "end", "font-size": 11},
        configuration.tick(v)));
    }
    for (const guide of configuration.guides || []) {
      const line = element("line", {x1: LEFT, x2: WIDTH - RIGHT, y1: ys(guide.value), y2: ys(guide.value),
        stroke: guide.color || "#ffc77e", "stroke-width": 1.5, "stroke-dasharray": "6 5"});
      svg.append(line);
      svg.append(element("text", {x: WIDTH - RIGHT - 3, y: ys(guide.value) - 5, fill: guide.color || "#ffc77e",
        "font-size": 11, "text-anchor": "end"}, guide.text));
    }
    svg.append(element("text", {x: LEFT, y: HEIGHT - 7, fill: "#8ea6c1", "font-size": 11}, dateDisplay(rows[0].date)));
    svg.append(element("text", {x: WIDTH - RIGHT, y: HEIGHT - 7, fill: "#8ea6c1", "font-size": 11,
      "text-anchor": "end"}, dateDisplay(rows[rows.length - 1].date)));

    for (const line of configuration.lines) {
      const segments = [];
      for (let i = 0; i < rows.length; i++) {
        const v = line.values[i];
        if (!Number.isFinite(v)) continue;
        segments.push((segments.length === 0 ? "M" : "L") + xs(i).toFixed(2) + "," + ys(v).toFixed(2));
      }
      svg.append(element("path", {d: segments.join(" "), fill: "none", stroke: line.color,
        "stroke-width": 2.7, "stroke-linecap": "round", "stroke-linejoin": "round",
        "vector-effect": "non-scaling-stroke"}));
    }

    if (configuration.markThreshold) {
      let prev = null;
      rows.forEach((p, i) => {
        const z = p.z;
        const crossing = Math.abs(z) >= 2 && (prev === null || Math.abs(prev) < 2 ||
          Math.sign(prev) !== Math.sign(z));
        if (crossing) {
          const c = element("circle", {cx: xs(i), cy: ys(z), r: 4.5,
            fill: z > 0 ? "#ffc77e" : "#75cfff", stroke: "#091321", "stroke-width": 1.7});
          c.append(element("title", {}, dateDisplay(p.date) + ": ±2 stretch threshold crossed (NOT a trade)"));
          svg.append(c);
        }
        prev = z;
      });
    }

    const hoverLine = element("line", {x1: 0, x2: 0, y1: TOP, y2: HEIGHT - BOTTOM,
      stroke: "#d4f4ff", "stroke-width": 1, "stroke-dasharray": "4 4", "pointer-events": "none"});
    const hoverDots = configuration.lines.map(line => {
      const c = element("circle", {r: 4.5, fill: line.color, stroke: "#091421", "stroke-width": 1.4,
        "pointer-events": "none"});
      svg.append(c);
      return c;
    });
    svg.append(hoverLine);
    const focus = (index) => {
      index = Math.max(0, Math.min(rows.length - 1, index));
      hoverLine.setAttribute("x1", xs(index));
      hoverLine.setAttribute("x2", xs(index));
      configuration.lines.forEach((line, j) => {
        const v = line.values[index];
        hoverDots[j].setAttribute("cx", xs(index));
        hoverDots[j].setAttribute("cy", Number.isFinite(v) ? ys(v) : -500);
      });
      svg.dataset.currentIndex = String(index);
      configuration.onInspect(rows[index], index);
    };
    svg.onpointermove = (event) => {
      const rect = svg.getBoundingClientRect();
      const fraction = (event.clientX - rect.left) / Math.max(rect.width, 1);
      const u = fraction * WIDTH;
      focus(Math.round((u - LEFT) / usableWidth * (rows.length - 1)));
    };
    svg.onkeydown = (event) => {
      if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        event.preventDefault();
        const delta = event.key === "ArrowRight" ? 1 : -1;
        focus(Number(svg.dataset.currentIndex || rows.length - 1) + delta);
      }
    };
    focus(rows.length - 1);
  }
  function interpret(pair) {
    const same = pair.beta > .1;
    const strongDeviation = Math.abs(pair.z) >= 2;
    const safe = pair.p < .05 && pair.correlation > .75 && strongDeviation &&
      pair.q < .05 && same;
    const why = [];
    if (!strongDeviation) why.push("The spread is not unusually stretched (|Z| is below 2).");
    if (pair.p >= .05) why.push("The long-run statistical relationship is not supported by the cointegration test.");
    if (pair.correlation <= .75) why.push("Their recent daily movements are not correlated enough.");
    if (pair.q >= .05) why.push("The relationship did not survive correction for testing many pairs.");
    if (!same) why.push("The hedge ratio does not support a straightforward two-sided trade.");
    const headline = $( "trade-explanation" );
    const heading = $("trade-explanation-heading");
    const note = $("trade-explanation-reason");
    const legs = $("trade-legs");
    const label = $("trade-signal-chip");
    heading.textContent = "What would " + pair.pair + " mean?";
    const direction = pair.z >= 0 ? "high" : "low";
    let message;
    if (Math.abs(pair.z) < .5) message = "These two stocks are trading close to their modeled usual relationship.";
    else message = pair.a + " is relatively " + direction + " versus " + pair.b +
      " according to this historical spread model (Z = " + (pair.z >= 0 ? "+" : "") + fmt(pair.z, 2) + ").";
    note.textContent = message + " " + (safe ? "The numerical gates pass, but execution/news checks are still required." :
      "Not a qualified trade: " + (why[0] || "Risk checks did not pass."));
    legs.replaceChildren();
    const first = document.createElement("span");
    const second = document.createElement("span");
    first.className = "leg-chip";
    second.className = "leg-chip";
    if (!same) {
      first.textContent = "No sensible positive hedge";
      second.textContent = "Do not use directional legs";
    } else if (pair.z >= 0) {
      first.textContent = "Example only: SHORT " + pair.a;
      second.textContent = "Example only: LONG " + pair.b;
    } else {
      first.textContent = "Example only: LONG " + pair.a;
      second.textContent = "Example only: SHORT " + pair.b;
    }
    legs.append(first, second);
    label.textContent = safe ? "NUMERIC GATES MET — REVIEW RISK" : "NOT A TRADE SIGNAL";
    label.className = "signal-chip" + (safe ? " ready" : "");
    headline.setAttribute("data-qualified", String(safe));
    $("chart-veto").textContent = why.length ? why.join(" ") :
      "Numerical checks pass, but earnings, structural breaks, liquidity, short availability, and trading costs still need review.";
  }
  function render() {
    if (!history || !allPairs.length) return;
    const pair = allPairs.find(p => p.pair === activePair) || allPairs[0];
    if (!pair) return;
    activePair = pair.pair;
    $("chart-pair").value = pair.pair;
    interpret(pair);
    const data = buildPair(pair);
    const period = RANGE_DAYS[range];
    const recent = data.slice(-period);
    if (!recent.length) return;
    const firstA = recent[0].a, firstB = recent[0].b;
    const baseA = recent.map(d => d.a / firstA * 100);
    const baseB = recent.map(d => d.b / firstB * 100);
    $("price-chart-title").textContent = pair.a + " vs " + pair.b + " — starting at 100";
    $("price-legend-a").textContent = pair.a + " (rebased)";
    $("price-legend-b").textContent = pair.b + " (rebased)";
    $("price-chart-explain").textContent = "Both prices start at 100 on " +
      dateDisplay(recent[0].date) + ". A higher line means a larger percentage gain, not necessarily a pairs-trade profit.";
    svgPlot("price-evolution", recent, {
      label: "Historical percentage-price comparison for " + pair.pair,
      tick: v => fmt(v, 0), guides: [],
      lines: [{color:"#6fe6ff", values:baseA},{color:"#be9eff", values:baseB}],
      onInspect: (_row, index) => {
        if (index === undefined) return;
        const d=recent[index];
        $("price-readout").textContent = dateDisplay(d.date) + " · " + pair.a + " " + dollars(d.a) +
          " (" + (baseA[index] - 100 >= 0 ? "+" : "") + fmt(baseA[index]-100, 1) + "%)" +
          " · " + pair.b + " " + dollars(d.b) +
          " (" + (baseB[index]-100 >= 0 ? "+" : "") + fmt(baseB[index]-100, 1) + "%)";
      }
    });
    const zRows = recent.filter(d => Number.isFinite(d.z));
    $("z-coverage").textContent = zRows.length + " calculated sessions in this period · last " +
      (zRows.length ? dateDisplay(zRows[zRows.length-1].date) : "unavailable");
    svgPlot("spread-evolution", zRows, {
      label: "Historical rolling spread Z-score for " + pair.pair + " with plus and minus two thresholds",
      tick: v => fmt(v, 1),
      guides: [{value: 2, text:"+2 WATCH", color:"#ffc77e"},
               {value: 0, text:"0 CENTER", color:"#63819a"},
               {value:-2, text:"−2 WATCH", color:"#75cfff"}],
      lines: [{color:"#6fe6ff",values:zRows.map(d=>d.z)}],
      markThreshold:true,
      onInspect: (d) => {
        if (!d) { $("spread-readout").textContent = "Insufficient history for rolling Z calculation."; return; }
        $("spread-readout").textContent = dateDisplay(d.date) + " · Z = " +
          (d.z >= 0 ? "+" : "") + fmt(d.z) + " · " +
          (Math.abs(d.z) >= 2 ? "Historically stretched; NOT an entry signal" :
           Math.abs(d.z) < .5 ? "Near modeled center" : "Within ±2 watch bands");
      }
    });
    const last = data[data.length-1];
    const err = last && Number.isFinite(last.z) ? Math.abs(last.z-pair.z) : NaN;
    $("chart-audit-readout").textContent = Number.isFinite(err) && err <= .025 ?
      "Cross-check passed: the latest rolling chart Z matches the published audited Z (difference " + fmt(err, 4) + ")." :
      "Chart-model cross-check inconclusive: check latest data dates and the stored formation estimate.";
  }
  async function start() {
    try {
      const filenames = ["data/prices-1.json", "data/prices-2.json", "data/screen.json"];
      const files = await Promise.all(filenames.map(async f => {
        const r = await fetch("./"+f, {cache:"no-store"});
        if (!r.ok) throw Error("Could not load "+f+" ("+r.status+")");
        return r.json();
      }));
      const [a,b,snapshot] = files;
      if (a.as_of !== snapshot.as_of || b.as_of !== snapshot.as_of ||
          a.dates.length !== b.dates.length ||
          a.dates.some((d,i)=>d!==b.dates[i])) throw Error("History and research snapshot dates don't align.");
      history = {dates:a.dates,series:{...a.series,...b.series}};
      allPairs = snapshot.pairs;
      for(const p of allPairs) if(!history.series[p.a] || !history.series[p.b]) throw Error("Missing "+p.pair+" historical price data");
      const picker = $("chart-pair");
      picker.replaceChildren();
      allPairs.slice().sort((x,y)=>x.pair.localeCompare(y.pair)).forEach(p=>{
        const option = document.createElement("option");
        option.value=p.pair;option.textContent=p.pair+" · "+p.industry;
        picker.append(option);
      });
      picker.onchange=()=> {
        activePair=picker.value;
        window.dispatchEvent(new CustomEvent("pairlab:request",{detail:{pair:activePair}}));
        render();
      };
      document.querySelectorAll("[data-chart-range]").forEach(button=>{
        button.onclick=()=> {
          range=button.dataset.chartRange;
          document.querySelectorAll("[data-chart-range]").forEach(b=>b.setAttribute("aria-pressed",String(b===button)));
          render();
        };
      });
      activePair=window.pairlabCurrentPair || "KTOS/ONDS";
      render();
    } catch(e) {
      $("price-readout").textContent = "Historical charts unavailable: "+e.message;
      $("spread-readout").textContent = "Check the price files and reload the website.";
    }
  }
  window.addEventListener("pairlab:selected",e=>{
    activePair=e.detail.pair;
    render();
  });
  start();
})();