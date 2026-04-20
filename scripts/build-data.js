/**
 * Pre-aggregates data.csv into small JSON files so pages load only what they need.
 * Run: npm install && npm run build-data
 * Reads data.csv from project root; writes to data/
 */

const fs = require('fs');
const path = require('path');
const { parse } = require('csv-parse');

const ROOT = path.resolve(__dirname, '..');
const CSV_PATH = path.join(ROOT, 'data.csv');
const DATA_DIR = path.join(ROOT, 'data');

function slug(name) {
  if (!name || typeof name !== 'string') return 'unknown';
  return encodeURIComponent(name.trim());
}

function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

// --- Aggregates (single pass) ---
const hero = { evSum: 0, evN: 0, angleSum: 0, angleN: 0, hrDistSum: 0, hrN: 0, fourSum: 0, fourN: 0 };
const games = {}; // gameUID -> { date, away, home, awayRuns, homeRuns, leaders?: }
const hrLeaderboard = []; // { Batter, Distance } top N
const teamHrDist = {}; // teamFull -> { totalDist, count }
const searchIndex = []; // { name, type, url } for batters, pitchers, umps, teams
const battersSet = new Set();
const pitchersSet = new Set();
const umpsSet = new Set();
const teamsSet = new Set();

// Per-entity row buckets (we flush to NDJSON files at the end to avoid memory blow-up)
const batterRows = new Map();
const pitcherRows = new Map();
const teamRows = new Map();
const umpRows = new Map();
const gameRows = new Map();
const pitchToGame = {}; // PitchUID -> gameUID for Game-view?pitchUID=

// Leaderboards: we'll compute from aggregates; for now collect minimal for summary
const allHrs = []; // { Batter, Distance } for sorting top 3

// Park factors: raw rows per park (we'll compute in a second pass or here)
const parkFactorRows = [];

function num(r, key) {
  const v = r[key];
  if (v === undefined || v === null || v === '') return NaN;
  const n = parseFloat(v);
  return isNaN(n) ? NaN : n;
}

function processRow(r) {
  const pitchCall = r.PitchCall;
  const playResult = r.PlayResult;
  const gameUID = r.GameUID;
  const batter = r.Batter;
  const pitcher = r.Pitcher;
  const umpire = r.Umpire;
  const homeFull = r.HomeNameFull;
  const awayFull = r.AwayNameFull;
  const homeTeam = r.HomeTeam;
  const awayTeam = r.AwayTeam;
  const dateStr = r.LocalDateTime || r.Date || r.LocalDate;

  // --- Hero metrics ---
  if (pitchCall === 'InPlay') {
    const ev = num(r, 'ExitSpeed');
    if (!isNaN(ev)) { hero.evSum += ev; hero.evN++; }
    const angle = num(r, 'Angle');
    if (!isNaN(angle)) { hero.angleSum += angle; hero.angleN++; }
  }
  if (playResult === 'HomeRun') {
    const dist = num(r, 'Distance');
    if (!isNaN(dist)) {
      hero.hrDistSum += dist;
      hero.hrN++;
      allHrs.push({ Batter: batter, Distance: dist });
      const teamFull = (r.BatterTeam === homeTeam) ? homeFull : awayFull;
      if (teamFull) {
        teamHrDist[teamFull] = teamHrDist[teamFull] || { totalDist: 0, count: 0 };
        teamHrDist[teamFull].totalDist += dist;
        teamHrDist[teamFull].count++;
      }
    }
  }
  if (r.AutoPitchType === 'Four-Seam') {
    const rel = num(r, 'RelSpeed');
    if (!isNaN(rel)) { hero.fourSum += rel; hero.fourN++; }
  }

  // --- Games ---
  if (gameUID) {
    if (!games[gameUID]) {
      games[gameUID] = {
        gameUID,
        date: dateStr,
        away: awayFull,
        home: homeFull,
        awayRuns: 0,
        homeRuns: 0
      };
    }
    const runs = num(r, 'RunsScored') || 0;
    if (runs && r['Top/Bottom']) {
      if (r['Top/Bottom'] === 'Top') games[gameUID].awayRuns += runs;
      else games[gameUID].homeRuns += runs;
    }
  }

  // --- Search index (unique names) ---
  if (batter) battersSet.add(batter);
  if (pitcher) pitchersSet.add(pitcher);
  if (umpire) umpsSet.add(umpire);
  if (homeFull) teamsSet.add(homeFull);
  if (awayFull) teamsSet.add(awayFull);

  // --- Per-entity rows (keep full row for profile pages) ---
  if (batter) {
    if (!batterRows.has(batter)) batterRows.set(batter, []);
    batterRows.get(batter).push(r);
  }
  if (pitcher) {
    if (!pitcherRows.has(pitcher)) pitcherRows.set(pitcher, []);
    pitcherRows.get(pitcher).push(r);
  }
  if (umpire) {
    if (!umpRows.has(umpire)) umpRows.set(umpire, []);
    umpRows.get(umpire).push(r);
  }
  if (gameUID) {
    if (!gameRows.has(gameUID)) gameRows.set(gameUID, []);
    gameRows.get(gameUID).push(r);
    if (r.PitchUID) pitchToGame[r.PitchUID] = gameUID;
  }
  if (homeFull || awayFull) {
    const team = homeFull && (r.BatterTeam === homeTeam) ? homeFull : awayFull;
    if (team) {
      if (!teamRows.has(team)) teamRows.set(team, []);
      teamRows.get(team).push(r);
    }
  }
}

function writeSummary() {
  const avgEv = hero.evN ? (hero.evSum / hero.evN).toFixed(1) : null;
  const avgAngle = hero.angleN ? (hero.angleSum / hero.angleN).toFixed(1) : null;
  const avgHrDist = hero.hrN ? (hero.hrDistSum / hero.hrN).toFixed(0) : null;
  const avgFour = hero.fourN ? (hero.fourSum / hero.fourN).toFixed(1) : null;

  const topHr = allHrs
    .sort((a, b) => b.Distance - a.Distance)
    .slice(0, 10)
    .map((x, i) => ({ rank: i + 1, Batter: x.Batter, Distance: Math.round(x.Distance) }));

  const teamAvgList = Object.entries(teamHrDist)
    .map(([team, s]) => ({ Team: team, AvgDistance: +(s.totalDist / s.count).toFixed(1) }))
    .sort((a, b) => b.AvgDistance - a.AvgDistance)
    .slice(0, 10);

  const gameList = Object.values(games)
    .map(g => ({
      gameUID: g.gameUID,
      date: g.date,
      away: g.away,
      home: g.home,
      awayRuns: g.awayRuns,
      homeRuns: g.homeRuns
    }))
    .sort((a, b) => new Date(b.date) - new Date(a.date))
    .slice(0, 50);

  const searchIndexList = [];
  umpsSet.forEach(name => {
    searchIndexList.push({ name, type: 'umpire', url: `ump-profiles.html?player=${encodeURIComponent(name)}` });
  });
  battersSet.forEach(name => {
    const isAlsoPitcher = pitchersSet.has(name);
    searchIndexList.push({ name, type: 'batter', url: `batter-profiles.html?player=${encodeURIComponent(name)}` });
    if (isAlsoPitcher) searchIndexList.push({ name, type: 'pitcher', url: `pitcher-profiles.html?player=${encodeURIComponent(name)}` });
  });
  pitchersSet.forEach(name => {
    if (!battersSet.has(name)) searchIndexList.push({ name, type: 'pitcher', url: `pitcher-profiles.html?player=${encodeURIComponent(name)}` });
  });
  teamsSet.forEach(name => {
    searchIndexList.push({ name, type: 'team', url: `team-profiles.html?team=${encodeURIComponent(name)}` });
  });

  const summary = {
    hero: { avgEv, avgAngle, avgHrDist, avgFour },
    topHr,
    teamHrAvg: teamAvgList,
    recentGames: gameList.slice(0, 6),
    allGames: gameList,
    searchIndex: searchIndexList
  };
  fs.writeFileSync(path.join(DATA_DIR, 'summary.json'), JSON.stringify(summary), 'utf8');
  console.log('Wrote data/summary.json');
  fs.writeFileSync(path.join(DATA_DIR, 'pitch-to-game.json'), JSON.stringify(pitchToGame), 'utf8');
  console.log('Wrote data/pitch-to-game.json');
}

function writeGamesJson() {
  const list = Object.values(games)
    .map(g => ({
      gameUID: g.gameUID,
      date: g.date,
      away: g.away,
      home: g.home,
      awayRuns: g.awayRuns,
      homeRuns: g.homeRuns,
      leaders: computeGameLeaders(gameRows.get(g.gameUID) || [])
    }))
    .sort((a, b) => new Date(b.date) - new Date(a.date));
  fs.writeFileSync(path.join(DATA_DIR, 'games.json'), JSON.stringify(list), 'utf8');
  console.log('Wrote data/games.json');
}

function computeGameLeaders(rows) {
  if (!rows || !rows.length) return null;
  const bestPitch = rows.filter(r => !isNaN(num(r, 'RelSpeed'))).sort((a, b) => num(b, 'RelSpeed') - num(a, 'RelSpeed'))[0];
  const bestHit = rows.filter(r => !isNaN(num(r, 'ExitSpeed'))).sort((a, b) => num(b, 'ExitSpeed') - num(a, 'ExitSpeed'))[0];
  const hrs = rows.filter(r => r.PlayResult === 'HomeRun').sort((a, b) => num(b, 'Distance') - num(a, 'Distance'));
  return {
    fastestPitch: bestPitch ? { Pitcher: bestPitch.Pitcher, RelSpeed: num(bestPitch, 'RelSpeed') } : null,
    hardestHit: bestHit ? { Batter: bestHit.Batter, ExitSpeed: num(bestHit, 'ExitSpeed') } : null,
    homeRuns: hrs.map(r => ({ Batter: r.Batter, Distance: num(r, 'Distance') }))
  };
}

function writeEntityFiles() {
  const subdirs = ['batters', 'pitchers', 'teams', 'umpires', 'games'];
  subdirs.forEach(d => ensureDir(path.join(DATA_DIR, d)));

  let count = 0;
  batterRows.forEach((rows, name) => {
    const file = path.join(DATA_DIR, 'batters', slug(name) + '.json');
    fs.writeFileSync(file, JSON.stringify(rows), 'utf8');
    count++;
  });
  console.log('Wrote', count, 'batter files');

  count = 0;
  pitcherRows.forEach((rows, name) => {
    const file = path.join(DATA_DIR, 'pitchers', slug(name) + '.json');
    fs.writeFileSync(file, JSON.stringify(rows), 'utf8');
    count++;
  });
  console.log('Wrote', count, 'pitcher files');

  count = 0;
  teamRows.forEach((rows, name) => {
    const file = path.join(DATA_DIR, 'teams', slug(name) + '.json');
    fs.writeFileSync(file, JSON.stringify(rows), 'utf8');
    count++;
  });
  console.log('Wrote', count, 'team files');

  count = 0;
  umpRows.forEach((rows, name) => {
    const file = path.join(DATA_DIR, 'umpires', slug(name) + '.json');
    fs.writeFileSync(file, JSON.stringify(rows), 'utf8');
    count++;
  });
  console.log('Wrote', count, 'umpire files');

  count = 0;
  gameRows.forEach((rows, gameUID) => {
    const file = path.join(DATA_DIR, 'games', slug(gameUID) + '.json');
    fs.writeFileSync(file, JSON.stringify(rows), 'utf8');
    count++;
  });
  console.log('Wrote', count, 'game files');
}

function main() {
  if (!fs.existsSync(CSV_PATH)) {
    console.error('data.csv not found at', CSV_PATH);
    process.exit(1);
  }
  ensureDir(DATA_DIR);
  ensureDir(path.join(DATA_DIR, 'batters'));
  ensureDir(path.join(DATA_DIR, 'pitchers'));
  ensureDir(path.join(DATA_DIR, 'teams'));
  ensureDir(path.join(DATA_DIR, 'umpires'));
  ensureDir(path.join(DATA_DIR, 'games'));

  console.log('Streaming', CSV_PATH, '...');
  const parser = fs.createReadStream(CSV_PATH).pipe(parse({ columns: true, skip_empty_lines: true, trim: true }));
  let rowCount = 0;
  parser.on('data', (row) => {
    processRow(row);
    rowCount++;
    if (rowCount % 100000 === 0) console.log('Processed', rowCount, 'rows');
  });
  parser.on('error', (err) => {
    console.error(err);
    process.exit(1);
  });
  parser.on('end', () => {
    console.log('Total rows:', rowCount);
    writeSummary();
    writeGamesJson();
    writeEntityFiles();
    console.log('Build complete.');
  });
}

main();
