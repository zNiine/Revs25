// script.js

// ─────────────────────────────────────────────────────────────────
// Helper to parse numbers (strip non-digits except dot/minus)
function parseNum(str) {
  if (str == null) return NaN;
  return parseFloat(String(str).replace(/[^\d.\-]/g, ''));
}

// Globals
let allData = [];
let playerName = "";
const COL = {};       // dynamic column mapping
let COLOR_MAP = {};   // per-pitch-type colors

// ─────────────────────────────────────────────────────────────────
// 1) Detect actual CSV headers from first row
function initColumnKeys(sample) {
  const keys = Object.keys(sample);
  COL.batter    = keys.find(k => /batter/i.test(k) && !/name/i.test(k));
  COL.pitcher   = keys.find(k => /pitcher/i.test(k) && !/count/i.test(k));
  COL.pitch     = keys.find(k => /^pitch$/i.test(k));
  COL.result    = keys.find(k => /result/i.test(k));
  COL.pitchType = keys.find(k => /pitch\s*type/i.test(k));
  COL.runner1   = keys.find(k => /runner[_ ]?1b/i.test(k));
  COL.runner2   = keys.find(k => /runner[_ ]?2b/i.test(k));
  COL.runner3   = keys.find(k => /runner[_ ]?3b/i.test(k));
  COL.hand      = keys.find(k => /handedness/i.test(k) || /pitcher_throw/i.test(k));
  COL.exitVel   = keys.find(k => /exit\s*velocity/i.test(k));
  COL.launchAng = keys.find(k => /launch\s*ang/i.test(k));   // handles malformed °
  COL.hitType   = keys.find(k => /hit\s*type/i.test(k));
  COL.distance  = keys.find(k => /distance/i.test(k));
  COL.locX      = keys.find(k => /location.*side/i.test(k));
  COL.locY      = keys.find(k => /location.*height/i.test(k));
  COL.relX      = keys.find(k => /release.*side/i.test(k));
  COL.relY      = keys.find(k => /release.*height/i.test(k));
  COL.sumHoriz  = keys.find(k => /movement.*horizontal/i.test(k));
  COL.sumVert   = keys.find(k => /induced.*vertical/i.test(k));

  // fallback to exact names if detection missed them
  if (!COL.relX && keys.includes('Release Side (ft)'))   COL.relX = 'Release Side (ft)';
  if (!COL.relY && keys.includes('Release Height (ft)')) COL.relY = 'Release Height (ft)';

  console.log('✅ Column mapping:', COL);
}

// ─────────────────────────────────────────────────────────────────
// 2) Fetch & parse all CSVs, trim keys/values, parse filename dates
async function fetchAllCSVs() {
  const idx = await fetch('data/'),
        html = await idx.text(),
        files = [...html.matchAll(/href="([^"]+\.csv)"/g)].map(m => m[1]);
  let rows = [];
  const year = new Date().getFullYear();
  for (const f of files) {
    const txt  = await (await fetch(`data/${f}`)).text(),
          papa = Papa.parse(txt, { header:true, skipEmptyLines:true }),
          raw  = papa.data;
    raw.forEach(r => {
      // trim keys & values
      Object.keys(r).forEach(k => {
        const tk = k.trim(), v = r[k];
        delete r[k];
        r[tk] = typeof v === 'string' ? v.trim() : v;
      });
      // parse MM-DD from filename
      const m = f.match(/^(\d{2})-(\d{2})/);
      r.__gameDate = m
        ? new Date(year, parseInt(m[1],10)-1, parseInt(m[2],10))
        : null;
    });
    rows.push(...raw);
  }
  if (rows.length && !COL.batter) initColumnKeys(rows[0]);
  return rows;
}

// ─────────────────────────────────────────────────────────────────
// 3) Index: load players dropdown
async function loadPlayerOptions() {
  const sel = document.getElementById('playerSelect');
  if (!sel) return;
  allData = await fetchAllCSVs();
  [...new Set(allData.map(d=>d[COL.batter]).filter(Boolean))]
    .forEach(name => sel.append(new Option(name, name)));
}

// ─────────────────────────────────────────────────────────────────
// 4) Navigate to dashboard
function goToDashboard() {
  const sel = document.getElementById('playerSelect');
  if (!sel) return;
  const p = sel.value;
  if (p) window.location.href = `dashboard.html?player=${encodeURIComponent(p)}`;
}

// ─────────────────────────────────────────────────────────────────
// 5) Dashboard init
async function startDashboard() {
  const hdr = document.getElementById('playerName');
  if (!hdr) return;
  if (!allData.length) allData = await fetchAllCSVs();
  playerName = new URLSearchParams(location.search).get('player');
  hdr.textContent = playerName;

  setupFilters();
  // wire up Show All checkbox
  const showAll = document.getElementById('showAllDates');
  if (showAll) {
    showAll.addEventListener('change', () => {
      const dis = showAll.checked;
      document.getElementById('startDate').disabled = dis;
      document.getElementById('endDate').disabled   = dis;
      applyFilters();
    });
  }

  applyFilters();
}

// ─────────────────────────────────────────────────────────────────
// 6) Build filters: pitcher & pitch type
function setupFilters() {
  // Pitcher
  const ps = document.getElementById('pitcherFilter');
  ps.innerHTML = `<option value="">All</option>`;
  [...new Set(allData.map(d=>d[COL.pitcher]).filter(Boolean))]
    .forEach(p => ps.append(new Option(p, p)));

  // Pitch Type
  const pt = document.getElementById('pitchTypeFilter');
  pt.innerHTML = `<option value="">All</option>`;
  [...new Set(allData.map(d=>d[COL.pitchType]).filter(Boolean))]
    .forEach(t => pt.append(new Option(t, t)));
}

// ─────────────────────────────────────────────────────────────────
// 7) Apply filters & redraw plate chart
function applyFilters() {
  let f = allData.filter(d => d[COL.batter] === playerName);

  // date range unless Show All
  const showAll = document.getElementById('showAllDates')?.checked;
  if (!showAll) {
    const sd = document.getElementById('startDate').value;
    if (sd) {
      const start = new Date(sd);
      f = f.filter(d => d.__gameDate && d.__gameDate >= start);
    }
    const ed = document.getElementById('endDate').value;
    if (ed) {
      const end = new Date(ed);
      f = f.filter(d => d.__gameDate && d.__gameDate <= end);
    }
  }

  // handedness
  const hand = document.getElementById('handFilter').value;
  if (hand) f = f.filter(d => d[COL.hand] === hand);

  // runners
  const run = document.getElementById('runnersFilter').value;
  if (run === "true") {
    f = f.filter(d =>
      d[COL.runner1] === '1' ||
      d[COL.runner2] === '1' ||
      d[COL.runner3] === '1'
    );
  }

  // pitcher
  const pit = document.getElementById('pitcherFilter').value;
  if (pit) f = f.filter(d => d[COL.pitcher] === pit);

  // pitch type
  const pt = document.getElementById('pitchTypeFilter').value;
  if (pt) f = f.filter(d => d[COL.pitchType] === pt);

  plotPlate(f);
}

// ─────────────────────────────────────────────────────────────────
// 8) Plot plate chart, legend, table, click→trajectory
function plotPlate(data) {
  if (!data.length) return;

  // number batted balls
  let hitNum = 0;
  data.forEach(d => {
    const ev = parseNum(d[COL.exitVel]),
          la = parseNum(d[COL.launchAng]);
    d.__hitNumber = (!isNaN(ev) && !isNaN(la)) ? ++hitNum : null;
  });

  // debug
  const hits = data.filter(d=>d.__hitNumber);
  console.group("🛠️ Batted-Ball Debug");
  console.log("Total:", data.length, "Hits:", hits.length);
  console.table(hits.map(d=>({"#":d.__hitNumber, EV:d[COL.exitVel], LA:d[COL.launchAng]})));
  console.groupEnd();

  // swing logic
  function isSwing(d) {
    const res = (d[COL.result]||'').toLowerCase(),
          pit = (d[COL.pitch ]||'').toLowerCase();
    if (res.includes("walk")) return false;
    if (pit==="swinging strike"||pit==="foul") return true;
    if (res && res!=="strike out") return true;
    return false;
  }

  // colors
  const types = [...new Set(data.map(d=>d[COL.pitchType]))];
  COLOR_MAP = {};
  types.forEach((t,i)=>COLOR_MAP[t]=`hsl(${(i*45)%360},70%,50%)`);

  // hover texts
  const hover = data.map(d =>
    `Type: ${d[COL.pitchType]}<br>`+
    `Pitch: ${d[COL.pitch]}<br>`+
    `Result: ${d[COL.result]}<br>`+
    `Pitcher: ${d[COL.pitcher]}`
  );

  // trace
  const trace = {
    x: data.map(d=>parseNum(d[COL.locX])),
    y: data.map(d=>parseNum(d[COL.locY])),
    text: data.map(d=>d.__hitNumber||''),
    textposition:'middle center',
    mode:'markers+text',
    type:'scatter',
    marker:{
      size:12,
      symbol:data.map(d=>isSwing(d)?'square':'circle'),
      color:data.map(d=>COLOR_MAP[d[COL.pitchType]]||'gray'),
      line:{color:'black',width:1}
    },
    hoverinfo:'text',
    hovertext:hover
  };

  const layout = {
    title:'Plate Location (Squares=Swung, Circles=Took)',
    height:750,
    xaxis:{ title:'Horizontal (ft)', range:[-1.5,1.5] },
    yaxis:{ title:'Vertical (ft)',   range:[0.25,5] },
    shapes:[{ type:'rect', x0:-0.708, x1:0.708, y0:1.5, y1:3.5, line:{color:'black'} }],
    clickmode:'event+select'
  };

  Plotly.newPlot('plateChart',[trace],layout);
  renderLegends(types);
  renderTable(data);

  document.getElementById('plateChart')
    .on('plotly_click', e => plotTrajectory(e.points[0].customdata));
}

// ─────────────────────────────────────────────────────────────────
// 9) Legend
function renderLegends(types) {
  const div = document.getElementById('legendDiv');
  div.innerHTML = `<strong>Pitch Types:</strong><br>`;
  types.forEach(t => {
    div.innerHTML +=
      `<span style="display:inline-block;width:12px;height:12px;
                   background:${COLOR_MAP[t]};margin-right:5px;
                   vertical-align:middle;"></span>${t}<br>`;
  });
  div.innerHTML += `<br><strong>Action:</strong><br>
    <span style="display:inline-block;width:12px;height:12px;
                 border:2px solid black;margin-right:5px;
                 vertical-align:middle;"></span>Swung<br>
    <span style="display:inline-block;width:12px;height:12px;
                 border:2px solid black;border-radius:50%;
                 margin-right:5px;vertical-align:middle;"></span>Took`;
}

// ─────────────────────────────────────────────────────────────────
// 10) Table
function renderTable(data) {
  const rows = data.filter(d=>d.__hitNumber)
                   .sort((a,b)=>a.__hitNumber-b.__hitNumber);
  const div = document.getElementById('battedBallTable');
  if (!rows.length) {
    div.innerHTML = '<em>No batted-ball data</em>';
    return;
  }
  let html = `<table><thead><tr>
    <th>#</th><th>${COL.hitType}</th>
    <th>${COL.exitVel}</th><th>${COL.launchAng}</th>
    <th>${COL.distance}</th><th>${COL.result}</th>
  </tr></thead><tbody>`;
  rows.forEach(d => {
    html += `<tr>
      <td>${d.__hitNumber}</td>
      <td>${d[COL.hitType]||''}</td>
      <td>${parseNum(d[COL.exitVel])}</td>
      <td>${parseNum(d[COL.launchAng])}</td>
      <td>${parseNum(d[COL.distance])||''}</td>
      <td>${d[COL.result]||''}</td>
    </tr>`;
  });
  html += `</tbody></table>`;
  div.innerHTML = html;
}

// ─────────────────────────────────────────────────────────────────
// 11) Trajectory per your Python logic
function plotTrajectory(d) {
  const fr = 50,
        rx = parseNum(d[COL.relX]), ry = parseNum(d[COL.relY]),
        px = parseNum(d[COL.locX]), py = parseNum(d[COL.locY]),
        dx = parseNum(d[COL.sumHoriz])/12, dy = parseNum(d[COL.sumVert])/12;
  const xs = [], ys = [];
  for (let i=0; i<fr; i++){
    const t=i/(fr-1), ang=Math.PI*t;
    xs.push(rx + (px-rx)*t + Math.cos(ang)*dx);
    ys.push(ry + (py-ry)*t + Math.sin(ang)*dy);
  }
  Plotly.newPlot('trajectoryChart',[{
    x:xs, y:ys, mode:'lines', type:'scatter',
    line:{color:COLOR_MAP[d[COL.pitchType]]||'gray',width:2}
  }],{
    title:`Trajectory for ${d[COL.pitchType]}`,
    xaxis:{title:'Horizontal (ft)'}, 
    yaxis:{title:'Vertical (ft)',scaleanchor:'x',scaleratio:1},
    shapes:[{type:'rect',x0:-0.71,x1:0.71,y0:1.5,y1:3.5,line:{color:'green',width:2}}]
  });
}

// ─────────────────────────────────────────────────────────────────
// 12) Entry points
window.addEventListener('DOMContentLoaded', () => {
  loadPlayerOptions();
  if (location.pathname.endsWith('dashboard.html')) startDashboard();
});
