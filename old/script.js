// script.js
console.log('🔥 UPDATED script.js loaded at', new Date().toISOString());

function parseNum(str) {
  if (str == null) return NaN;
  let s = String(str).trim();
  if (!s) return NaN;

  // Check first character
  const first = s[0];
  const negative = !/[0-9.]/.test(first);

  // Extract only digits and dots
  const clean = s.replace(/[^\d.]/g, '');

  const n = parseFloat(clean);
  return negative ? -n : n;
}

// Quick sanity check:
console.log(parseNum('-12.3'),   // -12.3
            parseNum('–12.3'),  // -12.3
            parseNum('?45.6'),  // -45.6
            parseNum('12.3'));  //  12.3


let allData = [];
let playerName = '';
const COL = {};      // will hold our dynamic column names
let COLOR_MAP = {};  // pitch-type → HSL color

// ─────────────────────────────────────────────────────────────────
// 1) Map columns by cleaning the very first row’s headers
function initColumnKeys(sample) {
  const keys = Object.keys(sample);
  console.log('🧐 headers seen:', keys);

  // Normalize a header: remove diacritics, strip punctuation, collapse spaces, lowercase
  const clean = k => k
    .normalize('NFKD')           // decompose diacritics
    .replace(/[^\w ]/g, ' ')     // keep only letters, digits, underscore, space
    .replace(/\s+/g, ' ')        // collapse multiple spaces
    .trim()
    .toLowerCase();

  COL.batter    = keys.find(k => clean(k).startsWith('batter'));
  COL.pitcher   = keys.find(k => clean(k).startsWith('pitcher'));
  COL.pitch     = keys.find(k => clean(k) === 'pitch');
  COL.result    = keys.find(k => clean(k).startsWith('result'));
  COL.pitchType = keys.find(k => clean(k).includes('pitch type'));

  COL.runner1   = keys.find(k => clean(k).startsWith('runner_1b'));
  COL.runner2   = keys.find(k => clean(k).startsWith('runner_2b'));
  COL.runner3   = keys.find(k => clean(k).startsWith('runner_3b'));
  console.log('→ runner cols mapped to:', COL.runner1, COL.runner2, COL.runner3);

  COL.hand = keys.find(k =>
    clean(k).includes('pitcher_throw')
  )
  COL.exitVel   = keys.find(k => clean(k).includes('exit velocity'));
  COL.launchAng = keys.find(k => clean(k).startsWith('launch angle'));

  COL.hitType   = keys.find(k => clean(k).includes('hit type'));
  COL.distance  = keys.find(k => clean(k).startsWith('distance'));
  

  // THIS is critical: direction & bearing must map correctly
  COL.direction = keys.find(k => clean(k).startsWith('direction'));
  COL.time = keys.find(k => clean(k) === 'hit time');

  COL.bearing   = keys.find(k => clean(k).startsWith('bearing'));

  COL.locX      = keys.find(k => clean(k).includes('location side'));
  COL.locY      = keys.find(k => clean(k).includes('location height'));
  COL.locY      = keys.find(k => clean(k).includes('location height'));

  COL.relX      = keys.find(k => clean(k).includes('release side'));
  COL.relY      = keys.find(k => clean(k).includes('release height'));
  COL.sumHoriz  = keys.find(k => clean(k).includes('horizontal break') || clean(k).includes('movement horizontal'));
  COL.sumVert   = keys.find(k => clean(k).includes('vertical') || clean(k).includes('induced virtual break'));

  console.log('→ mapped COL keys:', COL);
}

// ─────────────────────────────────────────────────────────────────
// 2) Load all CSVs via a manifest, clean keys & cache rows
async function fetchAllCSVs() {
  if (allData.length) return allData;

  // 2a) get the list of filenames
  const files = await fetch('data/files.json')
    .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });

  const year = new Date().getFullYear();
  let rows = [];

  for (const f of files) {
    // 2b) fetch & parse each CSV
    const txt    = await fetch(`data/${f}`).then(r => {
      if (!r.ok) throw new Error(`Failed ${f}: ${r.status}`);
      return r.text();
    });
    const parsed = Papa.parse(txt, { header: true, skipEmptyLines: true }).data;

    // 2c) trim & clean each row’s keys
    parsed.forEach(r => {
      Object.keys(r).forEach(origKey => {
        const v = r[origKey];
        delete r[origKey];
        let tk = origKey.trim()
          .replace(/[^\w ]/g, ' ')
          .replace(/\s+/g, ' ')
          .trim();
        r[tk] = typeof v === 'string' ? v.trim() : v;
      });
      // 2d) annotate with parsed date from filename
      const m = f.match(/^(\d{2})-(\d{2})/);
      r.__gameDate = m
        ? new Date(year, +m[1] - 1, +m[2])
        : null;
    });

    rows.push(...parsed);
  }

  if (rows.length) initColumnKeys(rows[0]);
  allData = rows;
  console.log('fetchAllCSVs → total rows:', allData.length);
  return allData;
}


function plotSprayChart(rows) {
  console.group("🗺️ sprayChart (with horizontal exaggeration)");

  // Tunable: exaggerate how far left/right points sit 
  const HORIZ_EXAGGERATION = 2.0;  // try 1.2 → 2.0

  // 1) Filter rows with valid angle+distance
  const hits = rows.filter(d => {
    const dir  = parseNum(d[COL.direction] ?? d[COL.bearing]);
    const dist = parseNum(d[COL.distance]);
    return !isNaN(dir) && !isNaN(dist);
  });
  if (!hits.length) {
    document.getElementById('sprayChart').innerHTML = '<em>No hits to plot</em>';
    console.groupEnd();
    return;
  }

  // 2) Convert each to (x,y), applying horizontal exaggeration
  const pts = hits.map(d => {
    const dist   = parseNum(d[COL.distance]);
    const dir    = parseNum(d[COL.direction] ?? d[COL.bearing]);
    const dirRad = dir * Math.PI / 180;

    const x = Math.sin(dirRad) * dist * HORIZ_EXAGGERATION;
    const y = Math.cos(dirRad) * dist;

    console.log(
      `#${d.__hitNumber}: dir=${dir}°, dist=${dist} → x=${x.toFixed(1)}, y=${y.toFixed(1)}`
    );

    return {
      num:      d.__hitNumber,
      x, y,
      ev:       parseNum(d[COL.exitVel]),
      la:       parseNum(d[COL.launchAng]),
      type:     d[COL.hitType],
      distance: dist
    };
  });

  // 3) Determine field radius (at least 400ft)
  const maxD = Math.max(...pts.map(p => p.distance), 400);
  const F    = maxD * 1.05;

  // 4) Build the marker+text trace
  const trace = {
    x: pts.map(p => p.x),
    y: pts.map(p => p.y),
    mode: 'markers+text',
    marker: {
      size:  pts.map(p => isNaN(p.ev) ? 10 : Math.min(p.ev / 2, 20)),
      color: pts.map(p => COLOR_MAP[p.type] || 'gray'),
      line:  { width: 1, color: '#333' },
      opacity: 0.8
    },
    text:          pts.map(p => p.num),
    textposition: 'middle center',
    textfont:     { size: 12, color: '#000' },
    hoverinfo:    'text',
    hovertext:    pts.map(p =>
      `#${p.num} ${p.type}<br>` +
      `EV: ${p.ev}<br>` +
      `LA: ${p.la}<br>` +
      `Dist: ${p.distance} ft`
    )
  };

  // 5) Render with your Trackman‐style background
  Plotly.newPlot('sprayChart', [trace], {
    images: [{
      source: 'assets/trackman-bg.png',
      xref:   'x', yref: 'y',
      x:      0,   y: 2,
      xanchor:'center', yanchor:'bottom',
      sizex:  2 * F, sizey: F,
      sizing: 'stretch',
      layer:  'below',
      opacity: 0.8
    }],
    xaxis: {
      range:      [-F, F],
      zeroline:   false,
      showgrid:   false,
      fixedrange: true,
      title:      'Left Field ←   → Right Field'
    },
    yaxis: {
      range:       [0, F],
      zeroline:    false,
      showgrid:    false,
      fixedrange:  true,
      scaleanchor: 'x',
      scaleratio:  1,
      title:       'Distance from Home Plate (ft)'
    },
    margin: { t:20, b:20, l:20, r:20 }
  });

  console.groupEnd();
}





// ─────────────────────────────────────────────────────────────────
// INDEX PAGE FUNCTIONS
// ─────────────────────────────────────────────────────────────────

// Populate player dropdown without duplicates
async function loadPlayerOptions() {
  const sel = document.getElementById('playerSelect');
  if (!sel) return;
  sel.innerHTML = `<option value="">-- Select Player --</option>`;

  const data = await fetchAllCSVs();
  const names = [...new Set(data.map(d => d[COL.batter]).filter(Boolean))];
  names.forEach(n => sel.append(new Option(n, n)));
}

// Navigate to dashboard for selected player
function goToDashboard() {
  const sel = document.getElementById('playerSelect');
  if (sel && sel.value) {
    window.location.href = `dashboard.html?player=${encodeURIComponent(sel.value)}`;
  }
}

// ─────────────────────────────────────────────────────────────────
// DASHBOARD PAGE FUNCTIONS
// ─────────────────────────────────────────────────────────────────

async function startDashboard() {
  const hdr = document.getElementById('playerName');
  if (!hdr) return;  // not on dashboard.html

  if (!allData.length) allData = await fetchAllCSVs();

  playerName = new URLSearchParams(location.search).get('player') || '';
  hdr.textContent = playerName;

  setupFilters();

  // Guarded Show-All checkbox listener
  const sa = document.getElementById('showAllDates');
  if (sa) {
    sa.addEventListener('change', () => {
      document.getElementById('startDate').disabled = sa.checked;
      document.getElementById('endDate').disabled   = sa.checked;
      applyFilters();
    });
  }

  applyFilters();

}

function setupFilters() {
  const data = allData.filter(d => d[COL.batter] === playerName);

  // Pitcher filter
  const ps = document.getElementById('pitcherFilter');
  ps.innerHTML = `<option value="">All</option>`;
  [...new Set(data.map(d => d[COL.pitcher]).filter(Boolean))]
    .forEach(p => ps.append(new Option(p, p)));

  // Pitch Type filter
  const pt = document.getElementById('pitchTypeFilter');
  pt.innerHTML = `<option value="">All</option>`;
  [...new Set(data.map(d => d[COL.pitchType]).filter(Boolean))]
    .forEach(t => pt.append(new Option(t, t)));
}

function applyFilters() {
  let f = allData.filter(d => d[COL.batter] === playerName);

  const sa = document.getElementById('showAllDates');
  if (!sa.checked) {
    const sv = document.getElementById('startDate').value;
    if (sv) f = f.filter(d => d.__gameDate >= new Date(sv));
    const ev = document.getElementById('endDate').value;
    if (ev) f = f.filter(d => d.__gameDate <= new Date(ev));
  }

  const hand = document.getElementById('handFilter').value;
  if (hand) f = f.filter(d => d[COL.hand] === hand);

  const runVal = document.getElementById('runnersFilter').value;
  if (runVal === 'true') {
    f = f.filter(d => d[COL.runner1] === 'TRUE' || d[COL.runner2] === 'TRUE' || d[COL.runner3] === 'TRUE');
  }

  const pit = document.getElementById('pitcherFilter').value;
  if (pit) f = f.filter(d => d[COL.pitcher] === pit);

  const ptVal = document.getElementById('pitchTypeFilter').value;
  if (ptVal) f = f.filter(d => d[COL.pitchType] === ptVal);

  plotPlate(f);
// ─────────────────────────────────────────────────────────────────
// 1) Take every EV+LA row → this is exactly your batted‐ball table
const tableRows = f
  .filter(d => {
    const ev = parseNum(d[COL.exitVel]);
    const la = parseNum(d[COL.launchAng]);
    return !isNaN(ev) && !isNaN(la);
  });

// 2) Number them in table order
tableRows.forEach((row, idx) => {
  row.__hitNumber = idx + 1;
});

// 3) Render the table from that numbered array
renderTable(tableRows);

// ─────────────────────────────────────────────────────────────────
// 4) Now build the array you’ll actually plot on the spray chart:
//    start from your numbered tableRows, but drop groundballs & bunts
const chartRows = tableRows.filter(d => {
  const ht = (d[COL.hitType]||'').toLowerCase();
  return ht !== 'groundball' && ht !== 'bunt';
});

// 5) Finally pass that into your spray‐chart function
plotSprayChart(chartRows);

}

// ─────────────────────────────────────────────────────────────────
// Plate chart + legend + table + trajectory
function plotPlate(data) {
  if (!data.length) {
    document.getElementById('plateChart').innerHTML = '<em>No data</em>';
    return;
  }

  // Number batted balls
  let hitNum = 0;
  data.forEach(d => {
    const ev = parseNum(d[COL.exitVel]), la = parseNum(d[COL.launchAng]);
    d.__hitNumber = (!isNaN(ev) && !isNaN(la)) ? ++hitNum : null;
  });

  // Swing vs Took logic
  function isSwing(d) {
    const res = (d[COL.result] || '').toLowerCase(),
          pit = (d[COL.pitch]  || '').toLowerCase();
    if (res.includes("walk")) return false;
    if (pit === "swinging strike" || pit === "foul") return true;
    if (res && res !== "strike out") return true;
    return false;
  }

  // Color map per pitch type
  const types = [...new Set(data.map(d => d[COL.pitchType]))];
  COLOR_MAP = {};
  types.forEach((t, i) => COLOR_MAP[t] = `hsl(${(i*45)%360},70%,50%)`);

  // Hover text
  const hover = data.map(d =>
    `Pitch Type: ${d[COL.pitchType]}<br>` +
    `Pitch: ${d[COL.pitch]}<br>` +
    `Result: ${d[COL.result]}<br>` +
    `Pitcher: ${d[COL.pitcher]}`
  );

  // Plotly trace
  const trace = {
    x: data.map(d => parseNum(d[COL.locX])),
    y: data.map(d => parseNum(d[COL.locY])),
    text: data.map(d => d.__hitNumber || ''),
    textposition: 'middle center',
    mode: 'markers+text',
    type: 'scatter',
    marker: {
      size: 12,
      symbol: data.map(d => isSwing(d) ? 'square' : 'circle'),
      color: data.map(d => COLOR_MAP[d[COL.pitchType]] || 'gray'),
      line: { color: 'black', width: 1 }
    },
    hoverinfo: 'text',
    hovertext: hover
  };

  const layout = {
    title: 'Plate Location (Squares=Swung, Circles=Took)',
    height: 750,
    xaxis: { title: 'Horizontal (ft)', range: [-1.5, 1.5] },
    yaxis: { title: 'Vertical (ft)',   range: [0.25, 5]   },
    shapes: [{
      type: 'rect', x0: -0.708, x1: 0.708,
      y0: 1.5,      y1: 3.5,
      line: { color: 'black' }
    }],
    clickmode: 'event+select'
  };

  Plotly.newPlot('plateChart', [trace], layout);
  renderLegends(types);
  renderTable(data);

  document.getElementById('plateChart')
    .on('plotly_click', e => plotTrajectory(e.points[0].customdata));
}

function renderLegends(types) {
  const div = document.getElementById('legendDiv');
  div.innerHTML = `<strong>Pitch Types:</strong><br>`;
  types.forEach(t => {
    div.innerHTML +=
      `<span style="display:inline-block;width:12px;height:12px;
                   background:${COLOR_MAP[t]};margin-right:5px;
                   vertical-align:middle;"></span>${t}<br>`;
  });
  div.innerHTML += `<br><strong>Action:</strong><br>` +
    `<span style="display:inline-block;width:12px;height:12px;
                  border:2px solid black;margin-right:5px;
                  vertical-align:middle;"></span>Swung<br>` +
    `<span style="display:inline-block;width:12px;height:12px;
                  border:2px solid black;border-radius:50%;
                  margin-right:5px;vertical-align:middle;"></span>Took`;
}

function renderTable(data) {
  // 1) Grab only the numbered rows and sort by hit number
  const rows = data
    .filter(d => d.__hitNumber)
    .sort((a, b) => a.__hitNumber - b.__hitNumber);

  const div = document.getElementById('battedBallTable');
  if (!rows.length) {
    div.innerHTML = '<em>No batted-ball data</em>';
    return;
  }

  // 2) Build the table header
  let html = `<table>
    <thead>
      <tr>
        <th>#</th>
        <th>Date</th>
        <th>Pitcher</th>
        <th>Inning</th>
        <th>${COL.hitType}</th>
        <th>${COL.exitVel}</th>
        <th>${COL.launchAng}</th>
        <th>${COL.distance}</th>
        <th>${COL.result}</th>
      </tr>
    </thead>
    <tbody>`;

  // 3) Populate each row, using `d` not `r`
  rows.forEach(d => {
    // format the date
    const dateStr = d.__gameDate
      ? d.__gameDate.toLocaleDateString()
      : (d[COL.gameDate] || '');

    html += `<tr>
      <td>${d.__hitNumber}</td>
      <td>${dateStr}</td>
      <td>${d[COL.pitcher] || ''}</td>
      <td>${d.inning || ''}</td>
      <td>${d[COL.hitType]  || ''}</td>
      <td>${!isNaN(parseNum(d[COL.exitVel])) ? parseNum(d[COL.exitVel]).toFixed(1) : ''}</td>
      <td>${!isNaN(parseNum(d[COL.launchAng])) ? parseNum(d[COL.launchAng]).toFixed(1) : ''}</td>
      <td>${!isNaN(parseNum(d[COL.distance])) ? parseNum(d[COL.distance]).toFixed(1) : ''}</td>
      <td>${d[COL.result]   || ''}</td>
    </tr>`;
  });

  html += `</tbody></table>`;
  div.innerHTML = html;
}


function plotTrajectory(d) {
  const fr = 50,
        rx = parseNum(d[COL.relX]), ry = parseNum(d[COL.relY]),
        px = parseNum(d[COL.locX]), py = parseNum(d[COL.locY]),
        dx = parseNum(d[COL.sumHoriz]) / 12,
        dy = parseNum(d[COL.sumVert ]) / 12;
  const xs = [], ys = [];
  for (let i = 0; i < fr; i++) {
    const t = i/(fr-1), ang = Math.PI*t;
    xs.push(rx + (px-rx)*t + Math.cos(ang)*dx);
    ys.push(ry + (py-ry)*t + Math.sin(ang)*dy);
  }
  Plotly.newPlot('trajectoryChart', [{
    x: xs, y: ys, mode: 'lines', type: 'scatter',
    line: { color: COLOR_MAP[d[COL.pitchType]] || 'gray', width: 2 }
  }], {
    title: `Trajectory for ${d[COL.pitchType]}`,
    xaxis: { title: 'Horizontal (ft)' },
    yaxis: { title: 'Vertical (ft)', scaleanchor: 'x', scaleratio: 1 },
    shapes: [{
      type: 'rect', x0: -0.71, x1: 0.71, y0: 1.5, y1: 3.5,
      line: { color: 'green', width: 2 }
    }]
  });
}

// ─────────────────────────────────────────────────────────────────
// LEADERBOARDS FUNCTIONS
// ─────────────────────────────────────────────────────────────────

async function startLeaderboards() {
  await fetchAllCSVs();
  const bf = document.getElementById('leaderBatterFilter');
  bf.innerHTML = `<option value="">All</option>`;
  const batters = [...new Set(allData.map(d => d[COL.batter]).filter(Boolean))];
  batters.forEach(b => bf.append(new Option(b, b)));
  bf.addEventListener('change', renderLeaderboards);
  renderLeaderboards();
}

function renderLeaderboards() {
  const selected = document.getElementById('leaderBatterFilter').value;
  const data = selected
    ? allData.filter(d => d[COL.batter] === selected)
    : allData;

  // ── Average Exit Velocity ──────────────────────────────
  const evStats = {};
  allData.forEach(d => {
    const b  = d[COL.batter];
    const ev = parseNum(d[COL.exitVel]);
    if (!b || isNaN(ev)) return;
    if (!evStats[b]) evStats[b] = { sum: 0, count: 0 };
    evStats[b].sum   += ev;
    evStats[b].count += 1;
  });
  const avgEV = Object.entries(evStats)
    .map(([b, s]) => ({ batter: b, avg: s.sum / s.count }))
    .sort((a, b) => b.avg - a.avg);

  let htmlAvg = `<thead><tr><th>Batter</th><th>Avg Exit Vel (mph)</th></tr></thead><tbody>`;
  avgEV.forEach(r => {
    htmlAvg += `<tr>
      <td>${r.batter}</td>
      <td>${r.avg.toFixed(1)}</td>
    </tr>`;
  });
  htmlAvg += `</tbody>`;
  document.getElementById('leaderboard-avgexit').innerHTML = htmlAvg;

  // ── Hardest-Hit Balls ─────────────────────────────────
  const hardHits = data
    .filter(d => !isNaN(parseNum(d[COL.exitVel])))
    .map(d => ({
      batter:    d[COL.batter],
      exitVel:   parseNum(d[COL.exitVel]),
      distance:  parseNum(d[COL.distance]),
      pitcher:   d[COL.pitcher],
      pitchType: d[COL.pitchType],
      result:    d[COL.result],
      time:      d[COL.time]
    }))
    .sort((a, b) => b.exitVel - a.exitVel)
    .slice(0, 10);

  let htmlHard = `<thead><tr>
    <th>Batter</th><th>Exit Vel (mph)</th><th>Distance (ft)</th>
    <th>Pitcher</th><th>Pitch Type</th><th>Result</th><th>Hit Time</th>
  </tr></thead><tbody>`;
  hardHits.forEach(r => {
    htmlHard += `<tr>
      <td>${r.batter}</td>
      <td>${r.exitVel.toFixed(1)}</td>
      <td>${isNaN(r.distance)? '' : r.distance.toFixed(1)}</td>
      <td>${r.pitcher}</td>
      <td>${r.pitchType}</td>
      <td>${r.result}</td>
      <td>${r.time || ''}</td>
    </tr>`;
  });
  htmlHard += `</tbody>`;
  document.getElementById('leaderboard-hardest').innerHTML = htmlHard;

  // ── Longest Home Runs ──────────────────────────────────
  const hrRaw = data.filter(d =>
    (d[COL.result] || '').toLowerCase().includes('home run')
  );

  const hrHits = hrRaw
    .map(d => ({
      batter:    d[COL.batter],
      distance:  parseNum(d[COL.distance]),
      exitVel:   parseNum(d[COL.exitVel]),
      launchAng: parseNum(d[COL.launchAng]),
      pitcher:   d[COL.pitcher],
      pitchType: d[COL.pitchType],
      result:    d[COL.result],
      time:      d[COL.time]
    }))
    .filter(r => !isNaN(r.distance))
    .sort((a, b) => b.distance - a.distance)
    .slice(0, 10);

  let htmlHR = `<thead><tr>
    <th>Batter</th><th>Distance (ft)</th><th>Exit Vel (mph)</th>
    <th>Launch Ang (°)</th><th>Pitcher</th><th>Pitch Type</th>
    <th>Result</th><th>Hit Time</th>
  </tr></thead><tbody>`;
  hrHits.forEach(r => {
    htmlHR += `<tr>
      <td>${r.batter}</td>
      <td>${r.distance.toFixed(1)}</td>
      <td>${isNaN(r.exitVel)? '' : r.exitVel.toFixed(1)}</td>
      <td>${isNaN(r.launchAng)? '' : r.launchAng.toFixed(1)}</td>
      <td>${r.pitcher}</td>
      <td>${r.pitchType}</td>
      <td>${r.result}</td>
      <td>${r.time || ''}</td>
    </tr>`;
  });
  htmlHR += `</tbody>`;
  document.getElementById('leaderboard-hr').innerHTML = htmlHR;

  // ── Lowest Chase Rate ──────────────────────────────────
  const zone = { L: -0.708, R: 0.708, bottom: 1.5, top: 3.5 };
  const stats = {};
  allData.forEach(d => {
    const x = parseNum(d[COL.locX]), y = parseNum(d[COL.locY]);
    if (isNaN(x) || isNaN(y)) return;
    if (x < zone.L || x > zone.R || y < zone.bottom || y > zone.top) {
      const b = d[COL.batter];
      if (!stats[b]) stats[b] = { out: 0, ch: 0 };
      stats[b].out++;
      const pit = (d[COL.pitch] || '').toLowerCase();
      if (pit === 'swinging strike' || pit === 'foul') stats[b].ch++;
    }
  });

  const arrChase = Object.entries(stats)
    .filter(([_, s]) => s.out >= 10)
    .map(([b, s]) => ({
      player:  b,
      rate:    s.ch / s.out,
      outside: s.out
    }))
    .sort((a, b) => a.rate - b.rate);

  let htmlChase = `<thead><tr>
    <th>Player</th><th>Chase Rate (%)</th><th>Outside Pitches</th>
  </tr></thead><tbody>`;
  arrChase.forEach(r => {
    htmlChase += `<tr>
      <td>${r.player}</td>
      <td>${(r.rate * 100).toFixed(1)}</td>
      <td>${r.outside}</td>
    </tr>`;
  });
  htmlChase += `</tbody>`;
  document.getElementById('leaderboard-chase').innerHTML = htmlChase;
}

// ─────────────────────────────────────────────────────────────────
// Wire up on all pages
window.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('playerSelect')) loadPlayerOptions();
  if (location.pathname.endsWith('dashboard.html')) startDashboard();
  if (location.pathname.endsWith('leaderboard.html')) startLeaderboards();
});
