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
  } else if (d.status === "available") label.textContent = "dziś!";
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
  } else if (d.day === me.today) {
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
  clockOffset = new Date(task.server_now).getTime() - Date.now();
  $("task-day").textContent = task.day;
  $("task-text").textContent = task.text;
  $("answer").value = "";
  $("feedback").textContent = "";
  $("feedback").className = "feedback";
  renderTaskState();
  show("task-modal", true);
  if (!task.solved) $("answer").focus();
}

function elapsedSeconds() {
  return Math.max(0, Math.floor((Date.now() + clockOffset - new Date(task.opened_at).getTime()) / 1000));
}

function tick() {
  const elapsed = elapsedSeconds();
  $("timer").textContent = fmtTime(elapsed);
  $("potential").textContent = potentialPoints(elapsed, task.wrong_attempts, task.multiplier);
}

function renderTaskState() {
  clearInterval(timerHandle);
  show("answer-form", !task.solved);
  show("timer-box", !task.solved);
  show("solved-box", task.solved);
  if (task.solved) {
    $("won").textContent = task.points;
    renderBreakdown(task.breakdown);
    $("solved-note").textContent = "Wróć jutro po kolejne okienko!";
  } else {
    tick();
    timerHandle = setInterval(tick, 1000);
  }
}

function dec(n, digits = 4) {
  return n.toLocaleString("pl-PL", { maximumFractionDigits: digits });
}

function span(cls, text) {
  const s = document.createElement("span");
  s.className = cls;
  s.textContent = text;
  return s;
}

function line(id, parts, delay) {
  const node = $(id);
  node.replaceChildren(...parts.map((p) => (typeof p === "string" ? document.createTextNode(p) : p)));
  node.classList.remove("reveal");
  void node.offsetWidth;
  node.style.animationDelay = `${delay}s`;
  node.classList.add("reveal");
}

function renderBreakdown(b) {
  if (!b) return;
  const supEl = document.createElement("sup");
  supEl.className = "gold";
  supEl.textContent = b.streak;
  line("f-values", ["P = (100 − 10·", span("val", b.started_minutes_over), " − 1·", span("val", b.wrong_attempts), ") × 1,1", supEl], 0.3);
  const base = b.minimum_applied ? `${b.raw} → 10` : String(b.base);
  line("f-result", ["P = ", span("val", base), " × ", span("gold", dec(b.multiplier)), " ≈ ", span("total", b.points)], 0.9);

  const items = [
    ["⏱️ Czas: ", fmtTime(b.elapsed_seconds), b.started_minutes_over
      ? ` → ${b.started_minutes_over} zaczęt${b.started_minutes_over === 1 ? "a minuta" : "e minuty"} ponad 5:00, czyli m = ${b.started_minutes_over} (−${b.time_penalty} pkt)`
      : " → w 5 minutach, bez kary, m = 0"],
    ["❌ Błędne próby: ", String(b.wrong_attempts), b.wrong_attempts ? `, czyli b = ${b.wrong_attempts} (−${b.wrong_penalty} pkt)` : ", czyli b = 0 🎯"],
    ["🔥 Seria: ", null, ""],
  ];
  const list = $("f-explain");
  list.replaceChildren();
  items.forEach(([label, value, rest], i) => {
    const li = document.createElement("li");
    li.append(label);
    if (i === 2) {
      li.append(span("gold", `${b.streak} ${b.streak === 1 ? "dzień" : "dni"}`), ` z rzędu przed dzisiaj, czyli N = ${b.streak} → mnożnik ×${dec(b.multiplier)}`);
    } else {
      const strong = document.createElement("b");
      strong.textContent = value;
      li.append(strong, rest);
    }
    list.append(li);
  });
  if (b.minimum_applied) {
    const li = document.createElement("li");
    li.textContent = "🛟 Wyszło mniej niż 10, ale za dobrą odpowiedź zawsze dostajesz co najmniej 10 pkt!";
    list.append(li);
  }
}

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
      renderTaskState();
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
