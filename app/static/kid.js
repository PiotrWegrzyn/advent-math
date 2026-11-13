const CODE_KEY = "advent-code";
const $ = (id) => document.getElementById(id);
let code = null;
let me = null;
let task = null;
let clockOffset = 0;
let timerHandle = null;
let rankings = null;
let rankingTab = "my_class";

function storageGet() { try { return localStorage.getItem(CODE_KEY); } catch { return null; } }
function storageSet(v) { try { v ? localStorage.setItem(CODE_KEY, v) : localStorage.removeItem(CODE_KEY); } catch {} }

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", "X-Code": code || "", ...(options.headers || {}) },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.detail || "Coś poszło nie tak. Spróbuj jeszcze raz.");
    err.status = res.status;
    throw err;
  }
  return data;
}

function show(id, visible) { $(id).classList.toggle("hidden", !visible); }
function fmtNumber(n) { return n.toLocaleString("pl-PL", { maximumFractionDigits: 2 }); }
function fmtMult(m) { return "×" + m.toLocaleString("pl-PL", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
function fmtTime(sec) { const m = Math.floor(sec / 60); const s = sec % 60; return `${m}:${String(s).padStart(2, "0")}`; }

function potentialPoints(elapsed, wrong, multiplier) {
  const over = Math.max(0, elapsed - 300);
  const base = Math.max(10, 100 - 10 * Math.ceil(over / 60) - wrong);
  return Math.floor(base * multiplier + 0.5);
}

async function login(rawCode) {
  code = rawCode.replace(/\D/g, "");
  try {
    await api("/api/login", { method: "POST", body: JSON.stringify({ code }) });
    storageSet(code);
    await loadMe();
  } catch (e) {
    code = null;
    storageSet(null);
    showLogin(e.message);
  }
}

function showLogin(message = "") {
  show("main", false);
  show("login", true);
  $("login-error").textContent = message;
  $("code").focus();
}

async function loadMe() {
  me = await api("/api/me");
  show("login", false);
  show("main", true);
  $("nick").textContent = me.nick;
  $("class-name").textContent = `klasa ${me.class_name}`;
  $("total").textContent = fmtNumber(me.total_points);
  $("streak").textContent = me.streak;
  $("mult").textContent = fmtMult(me.today_multiplier);
  renderGrid();
}

function renderGrid() {
  const note = $("phase-note");
  if (me.phase === "before") {
    const start = new Date(me.start_date + "T00:00:00");
    note.textContent = `Kalendarz rusza ${start.toLocaleDateString("pl-PL", { day: "numeric", month: "long" })}. Wróć wtedy!`;
    show("phase-note", true);
  } else if (me.phase === "after") {
    note.textContent = "Kalendarz się skończył. Wesołych Świąt! 🎁";
    show("phase-note", true);
  } else if (me.unlocked) {
    note.textContent = "🧪 Tryb testowy: wszystkie okienka są otwarte.";
    show("phase-note", true);
  } else {
    show("phase-note", false);
  }
  const columns = wideScreen.matches ? 6 : 4;
  const floors = [];
  for (let i = 0; i < me.days.length; i += columns) {
    const floor = document.createElement("div");
    floor.className = "floor";
    me.days.slice(i, i + columns).forEach((d) => floor.appendChild(windowFor(d)));
    floors.push(floor);
  }
  $("grid").replaceChildren(...floors);
}

const SCENES = ["📚", "✏️", "🧮", "📐", "🎄", "⛄", "🎁", "🍪", "🦌", "🔔", "⭐", "🕯️",
  "🧣", "🎅", "📏", "🌟", "🎨", "🧸", "🛷", "🍊", "🎶", "🔭", "🧁", "🏆"];

function windowFor(d) {
  const win = document.createElement("button");
  win.className = `window ${d.status}`;
  const num = document.createElement("span");
  num.className = "num";
  num.textContent = d.day;
  win.appendChild(num);
  const label = document.createElement("small");
  if (d.status === "solved") {
    const scene = document.createElement("span");
    scene.className = "scene";
    scene.textContent = SCENES[(d.day - 1) % SCENES.length];
    win.appendChild(scene);
    label.textContent = `⭐ ${d.points}`;
  } else if (d.status === "available") label.textContent = me.unlocked ? "otwórz" : "dziś!";
  else if (d.status === "opened") label.textContent = "dokończ";
  if (label.textContent) win.appendChild(label);
  win.disabled = !["available", "opened", "solved"].includes(d.status);
  win.setAttribute("aria-label", `Okienko ${d.day}`);
  win.onclick = () => clickDoor(d);
  return win;
}

const wideScreen = window.matchMedia("(min-width: 640px)");
wideScreen.addEventListener("change", () => { if (me) renderGrid(); });

function clickDoor(d) {
  if (d.status === "available") {
    $("intro-day").textContent = d.day;
    $("intro-go").onclick = () => { show("intro-modal", false); openDay(d.day); };
    show("intro-modal", true);
  } else if (d.day === me.today || me.unlocked) {
    openDay(d.day);
  } else {
    alert(`Dzień ${d.day}: +${d.points} pkt ⭐`);
  }
}

async function openDay(day) {
  try {
    task = await api(`/api/days/${day}/open`, { method: "POST" });
  } catch (e) {
    alert(e.message);
    return loadMe();
  }
  if (task.solved) return openWrapped(SUMMARY);
  clockOffset = new Date(task.server_now).getTime() - Date.now();
  $("task-day").textContent = task.day;
  $("task-text").textContent = task.text;
  setImage($("task-image"), task.image);
  $("answer").value = "";
  $("feedback").textContent = "";
  $("feedback").className = "feedback";
  clearInterval(timerHandle);
  tick();
  timerHandle = setInterval(tick, 1000);
  show("task-modal", true);
  $("answer").focus();
}

function setImage(img, svg) {
  img.classList.toggle("hidden", !svg);
  img.src = svg ? "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg) : "";
}

function elapsedSeconds() {
  return Math.max(0, Math.floor((Date.now() + clockOffset - new Date(task.opened_at).getTime()) / 1000));
}

function tick() {
  const elapsed = elapsedSeconds();
  $("timer").textContent = fmtTime(elapsed);
  $("potential").textContent = potentialPoints(elapsed, task.wrong_attempts, task.multiplier);
}

const SLIDES = 4;
const SUMMARY = SLIDES - 1;
let slide = 0;
let animRun = 0;

function dec(n, digits = 4) {
  return n.toLocaleString("pl-PL", { maximumFractionDigits: digits });
}

function wait(ms, run) {
  return new Promise((resolve, reject) => setTimeout(() => (run === animRun ? resolve() : reject("cancelled")), ms));
}

function bump(node) {
  node.classList.remove("bump");
  void node.offsetWidth;
  node.classList.add("bump");
}

function countUp(node, target, ms, run) {
  return new Promise((resolve) => {
    const start = performance.now();
    function frame(now) {
      if (run !== animRun) return resolve();
      const t = Math.min(1, (now - start) / ms);
      node.textContent = Math.round(target * (1 - Math.pow(1 - t, 3)));
      if (t < 1) requestAnimationFrame(frame); else resolve();
    }
    requestAnimationFrame(frame);
  });
}

function openWrapped(startAt = 0) {
  const b = task.breakdown;
  if (!b) return;
  document.querySelectorAll(".wr-day").forEach((n) => (n.textContent = task.day));
  $("wr-task").textContent = task.text;
  setImage($("wr-image"), task.image);
  $("wr-sum-time").textContent = fmtTime(b.elapsed_seconds);
  $("wr-sum-wrong").textContent = b.wrong_attempts;
  $("wr-sum-base").textContent = b.base;
  $("wr-sum-mult").textContent = "×" + dec(b.multiplier);
  $("wr-sum-score").textContent = b.points;
  show("task-modal", false);
  show("wrapped", true);
  goTo(startAt);
}

function closeWrapped() {
  animRun++;
  show("wrapped", false);
  loadMe();
}

function goTo(index) {
  slide = Math.max(0, Math.min(SUMMARY, index));
  animRun++;
  const run = animRun;
  document.querySelectorAll(".wr-slide").forEach((node, i) => {
    node.classList.toggle("active", i === slide);
    node.classList.toggle("before", i < slide);
  });
  document.querySelectorAll("#wr-progress i").forEach((bar, i) => {
    bar.className = i < slide ? "done" : i === slide ? "active" : "";
  });
  show("wr-hint", slide < SUMMARY);
  [animatePoints, animateMultiplier, animateScore, async () => {}][slide](task.breakdown, run).catch(() => {});
}

async function animatePoints(b, run) {
  const big = $("wr-base");
  big.textContent = "0";
  const timeBonus = Math.max(0, 100 - b.time_penalty);
  const rows = [
    {
      icon: "⏱️", title: "Bonus za czas", value: `+${timeBonus}`,
      note: b.started_minutes_over
        ? `Czas ${fmtTime(b.elapsed_seconds)}: 100 pkt minus 10 za każdą zaczętą minutę po 5:00 (${b.started_minutes_over} × −10)`
        : `Czas ${fmtTime(b.elapsed_seconds)}: w 5 minutach, więc pełne 100 pkt!`,
    },
    {
      icon: "❌", title: "Kara za błędne odpowiedzi", value: `−${b.wrong_penalty}`,
      note: b.wrong_attempts ? `${b.wrong_attempts} × −1 pkt` : "Bez ani jednego błędu! 🎯",
    },
  ];
  if (b.minimum_applied) {
    rows.push({ icon: "🛟", title: "Gwarantowane minimum", value: "10", note: "Za poprawną odpowiedź zawsze dostajesz co najmniej 10 pkt.", cls: "guarantee" });
  }
  const list = $("wr-rows");
  list.replaceChildren(...rows.map((r) => {
    const li = document.createElement("li");
    if (r.cls) li.className = r.cls;
    const title = document.createElement("b");
    title.textContent = `${r.icon} ${r.title}`;
    const value = document.createElement("span");
    value.className = "v";
    value.textContent = r.value;
    const note = document.createElement("small");
    note.textContent = r.note;
    li.append(title, value, note);
    return li;
  }));
  await wait(250, run);
  const counting = countUp(big, b.base, 1100, run);
  for (const li of list.children) {
    await wait(450, run);
    li.classList.add("in");
  }
  await counting;
  bump(big);
}

function fly(from, to, text, run) {
  return new Promise((resolve) => {
    const start = from.getBoundingClientRect();
    const end = to.getBoundingClientRect();
    const flyer = document.createElement("p");
    flyer.className = "flyer";
    flyer.textContent = text;
    flyer.style.fontSize = getComputedStyle(from).fontSize;
    flyer.style.left = `${start.left}px`;
    flyer.style.top = `${start.top}px`;
    $("wrapped").append(flyer);
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (run !== animRun) { flyer.remove(); return resolve(); }
      const fly = flyer.getBoundingClientRect();
      const dx = end.left + end.width / 2 - (fly.left + fly.width / 2);
      const dy = end.top + end.height / 2 - (fly.top + fly.height / 2);
      flyer.style.transform = `translate(${dx}px, ${dy}px)`;
      flyer.style.fontSize = getComputedStyle(to).fontSize;
    }));
    setTimeout(() => { flyer.remove(); resolve(); }, 950);
  });
}

async function animateMultiplier(b, run) {
  const p = $("wr-p");
  const n = $("wr-n");
  const mult = $("wr-mult");
  const result = document.querySelector(".wr-result");
  const factP = $("wr-fact-p");
  const factN = $("wr-fact-n");
  const chips = $("wr-chips");
  p.textContent = "P";
  n.textContent = "N";
  [p, n].forEach((node) => node.classList.remove("landed"));
  [factP, factN].forEach((node) => node.classList.remove("lit", "used"));
  $("wr-fact-n-val").textContent = `${b.streak} ${b.streak === 1 ? "dzień" : "dni"}`;
  mult.textContent = "1";
  result.classList.remove("in");
  chips.replaceChildren();
  $("wr-mult-text").textContent = "";

  await wait(900, run);
  factP.classList.add("lit");
  await wait(700, run);
  await fly($("wr-fact-p-val"), p, "10%", run);
  p.textContent = "0,1";
  p.classList.add("landed");
  factP.classList.remove("lit");
  factP.classList.add("used");

  await wait(700, run);
  factN.classList.add("lit");
  await wait(700, run);
  await fly($("wr-fact-n-val"), n, String(b.streak), run);
  n.textContent = b.streak;
  n.classList.add("landed");
  factN.classList.remove("lit");
  factN.classList.add("used");

  await wait(600, run);
  result.classList.add("in");
  const step = Math.max(120, Math.min(450, 2600 / Math.max(1, b.streak)));
  for (let k = 1; k <= b.streak; k++) {
    await wait(step, run);
    mult.textContent = dec(Math.round(Math.pow(1.1, k) * 10000) / 10000);
    const chip = document.createElement("span");
    chip.textContent = "🔥";
    chips.append(chip);
    bump(mult);
  }
  $("wr-mult-text").textContent = b.streak
    ? "10% to 0,1. Każdy dzień serii mnoży punkty przez 1,1. Nie przerwij jej jutro!"
    : "Dziś seria startuje od zera. Rozwiązuj codziennie, a mnożnik zacznie rosnąć!";
}

async function animateScore(b, run) {
  const points = $("wr-eq-points");
  const times = $("wr-eq-times");
  const eq = $("wr-eq-eq");
  const result = $("wr-eq-result");
  [points, times, eq, result].forEach((node) => node.classList.remove("in"));
  result.classList.remove("landed", "spinning");
  points.textContent = b.base;
  times.textContent = "× " + dec(b.multiplier);
  result.textContent = "0";
  $("wr-score-text").textContent = "";
  await wait(300, run);
  points.classList.add("in");
  await wait(2000, run);
  times.classList.add("in");
  await wait(900, run);
  eq.classList.add("in");
  result.classList.add("in", "spinning");
  const duration = Math.min(7000, 1300 + 700 * (b.multiplier - 1));
  await new Promise((resolve) => {
    const start = performance.now();
    function frame(now) {
      if (run !== animRun) return resolve();
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      result.textContent = Math.floor(b.points * eased);
      if (t < 1) requestAnimationFrame(frame); else resolve();
    }
    requestAnimationFrame(frame);
  });
  if (run !== animRun) return;
  result.classList.remove("spinning");
  result.textContent = b.points;
  result.classList.add("landed");
  $("wr-score-text").textContent = `${b.base} pkt × ${dec(b.multiplier)} = ${b.points} pkt (po zaokrągleniu)`;
  confetti(Math.min(120, 30 + b.streak * 10));
}

function confetti(count) {
  const box = $("wrapped");
  const colors = ["#ffe27a", "#ff6b6b", "#7be3a0", "#7fd0ff", "#ffffff"];
  for (let i = 0; i < count; i++) {
    const piece = document.createElement("i");
    piece.className = "confetti";
    piece.style.left = `${Math.random() * 100}%`;
    piece.style.background = colors[i % colors.length];
    piece.style.animationDuration = `${1.8 + Math.random() * 1.8}s`;
    piece.style.animationDelay = `${Math.random() * .6}s`;
    box.append(piece);
    setTimeout(() => piece.remove(), 4500);
  }
}

(function wrappedControls() {
  const box = $("wrapped");
  let startX = null;
  let startY = null;
  box.addEventListener("pointerdown", (e) => { startX = e.clientX; startY = e.clientY; });
  box.addEventListener("pointerup", (e) => {
    if (startX === null || e.target.closest("button")) { startX = null; return; }
    const dx = e.clientX - startX;
    const dy = e.clientY - startY;
    startX = null;
    if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy)) {
      goTo(slide + (dx < 0 ? 1 : -1));
    } else if (Math.abs(dx) < 10 && Math.abs(dy) < 10) {
      goTo(slide + (e.clientX < window.innerWidth * 0.3 ? -1 : 1));
    }
  });
  document.addEventListener("keydown", (e) => {
    if ($("wrapped").classList.contains("hidden")) return;
    if (e.key === "ArrowRight" || e.key === " ") goTo(slide + 1);
    if (e.key === "ArrowLeft") goTo(slide - 1);
    if (e.key === "Escape") closeWrapped();
  });
  $("wr-close").addEventListener("click", closeWrapped);
  $("wr-done").addEventListener("click", closeWrapped);
  $("wr-replay").addEventListener("click", () => goTo(0));
})();

$("answer").addEventListener("input", (e) => {
  let v = e.target.value.replace(/\./g, ",").replace(/[^\d,-]/g, "");
  const negative = v.startsWith("-");
  v = v.replace(/-/g, "");
  const parts = v.split(",");
  v = parts.length > 1 ? parts[0] + "," + parts.slice(1).join("") : parts[0];
  e.target.value = (negative ? "-" : "") + v;
});

$("sign-toggle").addEventListener("click", () => {
  const input = $("answer");
  input.value = input.value.startsWith("-") ? input.value.slice(1) : "-" + input.value;
  input.focus();
});

$("answer-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const answer = $("answer").value.trim();
  if (!/^-?\d+(,\d+)?$/.test(answer)) {
    $("feedback").textContent = "Wpisz liczbę, np. 12 albo 3,5.";
    $("feedback").className = "feedback bad";
    return;
  }
  try {
    const result = await api(`/api/days/${task.day}/answer`, { method: "POST", body: JSON.stringify({ answer }) });
    if (result.correct) {
      task.solved = true;
      task.points = result.points;
      task.breakdown = result.breakdown;
      clearInterval(timerHandle);
      openWrapped(0);
      loadMe();
    } else {
      task.wrong_attempts = result.wrong_attempts;
      $("feedback").textContent = "Niestety, to nie to. Spróbuj jeszcze raz! (−1 pkt)";
      $("feedback").className = "feedback bad";
      $("answer").select();
      tick();
    }
  } catch (err) {
    $("feedback").textContent = err.message;
    $("feedback").className = "feedback bad";
  }
});

document.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => {
  show("task-modal", false);
  show("intro-modal", false);
  clearInterval(timerHandle);
  loadMe();
}));

document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === t));
  show("tab-calendar", t.dataset.tab === "calendar");
  show("tab-rankings", t.dataset.tab === "rankings");
  if (t.dataset.tab === "rankings") loadRankings();
}));

document.querySelectorAll(".subtab").forEach((t) => t.addEventListener("click", () => {
  rankingTab = t.dataset.r;
  document.querySelectorAll(".subtab").forEach((x) => x.classList.toggle("active", x === t));
  renderRankings();
}));

async function loadRankings() {
  $("ranking-body").textContent = "Ładowanie…";
  try { rankings = await api("/api/rankings"); renderRankings(); }
  catch (e) { $("ranking-body").textContent = e.message; }
}

function table(headers, rows) {
  const t = document.createElement("table");
  const head = t.insertRow();
  headers.forEach(([label, cls]) => { const th = document.createElement("th"); th.textContent = label; if (cls) th.className = cls; head.appendChild(th); });
  rows.forEach(({ cells, me: mine }) => {
    const tr = t.insertRow();
    if (mine) tr.className = "me";
    cells.forEach(([value, cls]) => { const td = tr.insertCell(); td.textContent = value; if (cls) td.className = cls; });
  });
  return t;
}

function renderRankings() {
  const body = $("ranking-body");
  body.innerHTML = "";
  const list = rankings[rankingTab] || [];
  if (!list.length) { body.textContent = "Na razie pusto. Może to będziesz Ty?"; return; }
  if (rankingTab === "classes") {
    body.appendChild(table([["#"], ["Klasa"], ["Średnio pkt", "num"]],
      list.map((r) => ({ me: r.mine, cells: [[r.rank], [r.class_name], [fmtNumber(r.average_points), "num"]] }))));
  } else if (rankingTab === "today") {
    body.appendChild(table([["#"], ["Nick"], ["Klasa"], ["Czas", "num"]],
      list.map((r) => ({ me: r.me, cells: [[r.rank], [r.nick, "nick"], [r.class_name], [fmtTime(r.seconds), "num"]] }))));
  } else {
    const withClass = rankingTab === "school";
    body.appendChild(table([["#"], ["Nick"], ...(withClass ? [["Klasa"]] : []), ["Zadania", "num"], ["Punkty", "num"]],
      list.map((r) => ({ me: r.me, cells: [[r.rank], [r.nick, "nick"], ...(withClass ? [[r.class_name]] : []), [r.solved, "num"], [fmtNumber(r.points), "num"]] }))));
  }
}

$("login-form").addEventListener("submit", (e) => { e.preventDefault(); login($("code").value); });
$("logout").addEventListener("click", () => { storageSet(null); code = null; showLogin(); $("code").value = ""; });

(function init() {
  const match = location.hash.match(/k=(\d+)/);
  if (match) {
    history.replaceState(null, "", location.pathname);
    return login(match[1]);
  }
  const saved = storageGet();
  if (saved) return login(saved);
  showLogin();
})();
