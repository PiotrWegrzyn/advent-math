const TOKEN_KEY = "advent-admin-token";
const $ = (id) => document.getElementById(id);
let token = null;
let overview = null;
let currentClassId = null;
let currentDashboard = null;
let rankings = null;
let rankingTab = "school";

function storageGet() { try { return localStorage.getItem(TOKEN_KEY); } catch { return null; } }
function storageSet(v) { try { v ? localStorage.setItem(TOKEN_KEY, v) : localStorage.removeItem(TOKEN_KEY); } catch {} }
function show(id, visible) { $(id).classList.toggle("hidden", !visible); }
function fmt(n) { return Number(n).toLocaleString("pl-PL", { maximumFractionDigits: 1 }); }
function fmtTime(sec) { if (sec == null) return "—"; const m = Math.floor(sec / 60); return `${m}:${String(sec % 60).padStart(2, "0")}`; }
function el(tag, props = {}, children = []) {
  const node = Object.assign(document.createElement(tag), props);
  children.forEach((c) => node.append(c));
  return node;
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token || ""}` },
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && !path.endsWith("/login")) { storageSet(null); token = null; showLogin("Sesja wygasła, zaloguj się ponownie."); throw new Error("401"); }
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Błąd: sprawdź wpisane dane.");
  return data;
}

function showLogin(msg = "") { show("main", false); show("login", true); $("login-error").textContent = msg; }
function error(msg) { $("admin-error").textContent = msg || ""; }

$("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const { token: t } = await api("/api/admin/login", { method: "POST", body: JSON.stringify({ password: $("password").value }) });
    token = t; storageSet(t); $("password").value = ""; await start();
  } catch (err) { if (err.message !== "401") $("login-error").textContent = err.message; }
});
$("logout").addEventListener("click", () => { storageSet(null); token = null; showLogin(); });

async function start() {
  show("login", false); show("main", true);
  await loadOverview();
}

const PHASES = { before: "Kalendarz jeszcze nie wystartował", running: "Trwa", after: "Kalendarz zakończony" };

async function loadOverview() {
  overview = await api("/api/admin/overview");
  $("phase").textContent = overview.test_mode ? "Tryb testowy" : overview.phase === "running" ? `Dziś okienko ${overview.today}` : PHASES[overview.phase];
  renderTestMode();
  const setOptions = () => overview.task_sets.map((s) => el("option", { value: s.key, textContent: `${s.name} (${s.key})` }));
  $("new-set").replaceChildren(...setOptions());
  $("class-set").replaceChildren(...setOptions());
  $("preview-set").replaceChildren(...setOptions());
  const list = $("class-list");
  list.replaceChildren(...overview.classes.map((c) => {
    const b = el("button", { className: "subtab" + (c.id === currentClassId ? " active" : ""), textContent: `${c.name} (${c.active})` });
    b.onclick = () => loadClass(c.id);
    return b;
  }));
  if (!overview.classes.length) list.append(el("span", { className: "muted", textContent: "Nie ma jeszcze klas. Dodaj pierwszą poniżej." }));
  if (currentClassId) await loadClass(currentClassId);
}

$("create-form").addEventListener("submit", async (e) => {
  e.preventDefault(); error();
  try {
    const c = await api("/api/admin/classes", { method: "POST", body: JSON.stringify({
      name: $("new-name").value, task_set: $("new-set").value, size: Number($("new-size").value) }) });
    $("new-name").value = ""; $("new-size").value = "";
    currentClassId = c.id; await loadOverview();
  } catch (err) { error(err.message); }
});

async function loadClass(id) {
  currentClassId = id;
  document.querySelectorAll("#class-list .subtab").forEach((b, i) => b.classList.toggle("active", overview.classes[i]?.id === id));
  const d = await api(`/api/admin/classes/${id}/dashboard`);
  currentDashboard = d;
  show("class-panel", true);
  $("class-title").textContent = `Klasa ${d.name}`;
  $("class-set").value = d.task_set;
  const active = d.students.filter((s) => s.active);
  const todayStats = d.per_day.find((p) => p.day === d.today);
  $("class-summary").textContent = `${d.active} aktywnych uczniów z ${d.size}.` +
    (todayStats ? ` Dziś: otworzyło ${todayStats.opened}, rozwiązało ${todayStats.solved}.` : "") +
    ` Suma punktów klasy: ${fmt(active.reduce((a, s) => a + s.points, 0))}.`;
  renderDashboard(d);
}

function renderDashboard(d) {
  const t = el("table");
  const head = t.insertRow();
  const headers = ["Nr", "Nick", "Kod"];
  headers.forEach((h) => head.append(el("th", { className: "left", textContent: h })));
  for (let day = 1; day <= d.days; day++) head.append(el("th", { textContent: day, className: day === d.today ? "today-col" : "" }));
  ["Otw.", "Popr.", "Pkt", ""].forEach((h) => head.append(el("th", { textContent: h })));

  for (const s of d.students) {
    const tr = t.insertRow();
    if (!s.active) tr.className = "inactive";
    tr.append(el("td", { className: "left", textContent: s.number }));
    const nickCell = el("td", { className: "left" }, [el("a", { href: "#", textContent: s.nick, title: "Zmień nick", onclick: (e) => { e.preventDefault(); renameStudent(s); } })]);
    tr.append(nickCell);
    tr.append(el("td", { className: "left" }, [el("code", { textContent: s.active ? s.code : "wyłączony" })]));
    for (const c of s.days) {
      const td = el("td");
      if (c.status === "solved") {
        td.textContent = `✅${c.points}`; td.className = "cell-solved";
        td.title = `Wersja ${c.variant}, czas ${fmtTime(c.seconds)}, błędne próby: ${c.wrong_attempts}`;
      } else if (c.status === "opened") {
        td.textContent = "🟧"; td.className = "cell-opened";
        td.title = `Wersja ${c.variant}, otwarte, błędne próby: ${c.wrong_attempts}`;
      } else td.textContent = "—";
      if (c.day === d.today) td.classList.add("today-col");
      tr.append(td);
    }
    tr.append(el("td", { textContent: s.opened }), el("td", { textContent: s.solved }), el("td", { textContent: fmt(s.points) }));
    const actions = el("td", { className: "left" }, [
      el("button", { className: "btn secondary small", textContent: "Nowy kod", onclick: () => regenerate(s) }), " ",
      el("button", { className: "btn secondary small", textContent: s.active ? "Wyłącz" : "Włącz", onclick: () => toggleActive(s) }),
    ]);
    tr.append(actions);
  }
  const foot = t.insertRow();
  foot.append(el("td", { colSpan: 3, className: "left", innerHTML: "<b>Rozwiązało</b>" }));
  d.per_day.forEach((p) => foot.append(el("td", { textContent: p.day <= d.today ? p.solved : "", className: p.day === d.today ? "today-col" : "" })));
  $("dash").replaceChildren(t);
}

async function renameStudent(s) {
  const nick = prompt(`Nowy nick dla ucznia nr ${s.number}:`, s.nick);
  if (!nick || nick === s.nick) return;
  try { await api(`/api/admin/students/${s.id}`, { method: "PATCH", body: JSON.stringify({ nick }) }); await loadClass(currentClassId); }
  catch (e) { alert(e.message); }
}

async function regenerate(s) {
  if (!confirm(`Wygenerować nowy kod dla ucznia nr ${s.number} (${s.nick})? Stary kod przestanie działać, punkty zostają.`)) return;
  try { await api(`/api/admin/students/${s.id}/regenerate-code`, { method: "POST" }); await loadClass(currentClassId); }
  catch (e) { alert(e.message); }
}

async function toggleActive(s) {
  const msg = s.active
    ? `Wyłączyć ucznia nr ${s.number} (${s.nick})? Kod przestanie działać i uczeń zniknie z rankingów. Dane zostają, można go włączyć z powrotem.`
    : `Włączyć z powrotem ucznia nr ${s.number} (${s.nick})?`;
  if (!confirm(msg)) return;
  try { await api(`/api/admin/students/${s.id}`, { method: "PATCH", body: JSON.stringify({ active: !s.active }) }); await loadOverview(); }
  catch (e) { alert(e.message); }
}

$("grow-class").addEventListener("click", async () => {
  const d = currentDashboard;
  const value = prompt(`Klasa ${d.name} ma ${d.size} uczniów. Ilu ma mieć teraz? (liczby nie można zmniejszyć)`, d.size + 1);
  if (!value) return;
  try { await api(`/api/admin/classes/${d.id}`, { method: "PATCH", body: JSON.stringify({ size: Number(value) }) }); await loadOverview(); }
  catch (e) { alert(e.message); }
});

$("class-set").addEventListener("change", async (e) => {
  const d = currentDashboard;
  if (!confirm(`Zmienić zestaw zadań klasy ${d.name} na „${e.target.value}”?`)) { e.target.value = d.task_set; return; }
  try { await api(`/api/admin/classes/${d.id}`, { method: "PATCH", body: JSON.stringify({ task_set: e.target.value }) }); await loadOverview(); }
  catch (err) { alert(err.message); }
});

$("print-cards").addEventListener("click", () => window.open(`/cards.html?class=${currentClassId}`, "_blank"));

document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === t));
  ["dashboard", "rankings", "tasks"].forEach((name) => show(`tab-${name}`, t.dataset.tab === name));
  if (t.dataset.tab === "rankings") loadRankings();
  if (t.dataset.tab === "tasks") loadTasks();
}));

document.querySelectorAll(".subtab[data-r]").forEach((t) => t.addEventListener("click", () => {
  rankingTab = t.dataset.r;
  document.querySelectorAll(".subtab[data-r]").forEach((x) => x.classList.toggle("active", x === t));
  renderRankings();
}));

async function loadRankings() { rankings = await api("/api/admin/rankings"); renderRankings(); }

function renderRankings() {
  const list = rankings[rankingTab] || [];
  const t = el("table");
  const cols = {
    school: [["#", (r) => r.rank], ["Nick", (r) => r.nick], ["Klasa", (r) => r.class_name], ["Zadania", (r) => r.solved], ["Punkty", (r) => fmt(r.points)]],
    classes: [["#", (r) => r.rank], ["Klasa", (r) => r.class_name], ["Uczniów", (r) => r.students], ["Suma", (r) => fmt(r.total_points)], ["Średnio", (r) => fmt(r.average_points)]],
    today: [["#", (r) => r.rank], ["Nick", (r) => r.nick], ["Klasa", (r) => r.class_name], ["Czas", (r) => fmtTime(r.seconds)]],
  }[rankingTab];
  const head = t.insertRow();
  cols.forEach(([h]) => head.append(el("th", { textContent: h })));
  list.forEach((r) => { const tr = t.insertRow(); cols.forEach(([, f]) => tr.append(el("td", { textContent: f(r) }))); });
  $("ranking-body").replaceChildren(list.length ? t : el("p", { className: "muted", textContent: "Brak danych." }));
}

function renderTestMode() {
  const on = overview.test_mode;
  $("test-mode-box").classList.toggle("on", on);
  $("test-mode-text").textContent = on
    ? "Włączony: uczniowie mogą otwierać wszystkie okienka i podglądać odpowiedzi. Wyłącz przed startem kalendarza!"
    : "Wyłączony: okienka otwierają się dzień po dniu, odpowiedzi są ukryte.";
  $("test-mode-toggle").textContent = on ? "Wyłącz" : "Włącz";
  $("test-mode-toggle").className = on ? "btn small" : "btn secondary small";
}

$("test-mode-toggle").addEventListener("click", async () => {
  const enable = !overview.test_mode;
  const msg = enable
    ? "Włączyć tryb testowy? Wszystkie okienka będą otwarte i będzie można podejrzeć odpowiedzi."
    : "Wyłączyć tryb testowy? Okienka wrócą do otwierania dzień po dniu.";
  if (!confirm(msg)) return;
  try { await api("/api/admin/test-mode", { method: "POST", body: JSON.stringify({ enabled: enable }) }); await loadOverview(); }
  catch (e) { alert(e.message); }
});

$("delete-set").addEventListener("click", async () => {
  const key = $("preview-set").value;
  if (!key || !confirm(`Usunąć zestaw „${key}” z bazy? Tego nie da się cofnąć.`)) return;
  try { await api(`/api/admin/task-sets/${encodeURIComponent(key)}`, { method: "DELETE" }); await loadOverview(); await loadTasks(); }
  catch (e) { alert(e.message); }
});

$("preview-set").addEventListener("change", loadTasks);
async function loadTasks() {
  const key = $("preview-set").value;
  if (!key) { $("tasks-body").replaceChildren(); return; }
  const data = await api(`/api/admin/task-sets/${encodeURIComponent(key)}`);
  $("tasks-body").replaceChildren(...data.days.map((d) => el("div", { className: "tasks-day" }, [
    el("h3", { textContent: `Dzień ${d.day}` }),
    ...d.variants.map((v, i) => el("p", {}, [
      el("b", { textContent: `Wersja ${i + 1}: ` }), v.text,
      ...(v.image ? [el("img", { className: "task-image", alt: "Rysunek", src: "data:image/svg+xml;charset=utf-8," + encodeURIComponent(v.image) })] : []),
      el("br"), el("span", { className: "muted", textContent: `Odpowiedź: ${v.answer}` }),
    ])),
  ])));
}

(function init() {
  token = storageGet();
  if (token) start().catch(() => {}); else showLogin();
})();
