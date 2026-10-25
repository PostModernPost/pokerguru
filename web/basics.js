// Basics drill: name your hand, count your outs, know the price. Shared helpers in common.js.
"use strict";

const FILTER_KEY = "pokerguru.basicsFilters";
const SCORE_DRILLS = ["basics_hand", "basics_outs", "basics_price"];

let options = null;
let filters = { questions: [], games: [] };
let current = null;
let shownAt = 0;
let busy = false;

function renderFilters() {
  const q = $("f-question"); q.replaceChildren();
  for (const o of options.questions) {
    q.append(chip(o.label, filters.questions.includes(o.id), () => { toggle(filters.questions, o.id); renderFilters(); }));
  }
  const g = $("f-game"); g.replaceChildren();
  for (const o of options.games) {
    g.append(chip(o.label, filters.games.includes(o.id), () => { toggle(filters.games, o.id); renderFilters(); }));
  }
}

async function nextSpot() {
  if (busy) return;
  busy = true;
  try {
    current = await api("/api/basics/next", filters);
    renderSpot(current);
    show("drill-screen");
    shownAt = performance.now();
  } catch (e) {
    showMessage(e.message);
  } finally {
    busy = false;
  }
}

function renderSpot(c) {
  const s = c.spot;
  $("spot-tags").replaceChildren(
    el("span", { class: "tag strong" }, c.question_label),
    el("span", { class: "tag" }, c.game_label),
    el("span", { class: "tag" }, s.street[0].toUpperCase() + s.street.slice(1)),
  );
  $("board").replaceChildren(...s.board.map(renderCard));
  const hero = $("hero-cards");
  hero.className = s.hero_cards.length > 2 ? "cards four" : "cards";
  hero.replaceChildren(...s.hero_cards.map(renderCard));
  const bet = $("bet-line");
  if (s.question === "price") {
    bet.hidden = false;
    bet.replaceChildren("Pot ", el("b", {}, `${num(s.pot_bb)}bb`), " · Villain bets ", el("b", {}, `${num(s.bet_bb)}bb`),
      " · To call ", el("b", {}, `${num(s.bet_bb)}bb`));
  } else {
    bet.hidden = true;
  }
  $("prompt").textContent = c.prompt;
  const list = $("options"); list.replaceChildren();
  for (const label of c.options) {
    list.append(el("button", { class: "chip option", type: "button", onclick: () => answer(label) }, label));
  }
}

async function answer(choice) {
  if (busy || !current) return;
  busy = true;
  const elapsed = Math.round(performance.now() - shownAt);
  for (const b of document.querySelectorAll("#options button")) b.disabled = true;
  try {
    const r = await api("/api/basics/answer", { spot: current.spot, answer: choice, response_time_ms: elapsed });
    renderResult(current, r);
    show("result-screen");
  } catch (e) {
    showMessage(e.message);
  } finally {
    busy = false;
  }
}

async function refreshScore() {
  let total = 0, correct = 0;
  for (const d of SCORE_DRILLS) {
    try { const s = await api(`/api/summary?drill_type=${d}`); total += s.total; correct += s.correct; } catch (_) { /* ignore */ }
  }
  updateScore({ total, correct });
}

function renderResult(c, r) {
  const s = c.spot;
  const b = $("grade-banner");
  b.className = `grade-banner ${r.grade}`;
  b.textContent = r.grade === "correct" ? "Correct" : "Wrong";
  $("answer-line").replaceChildren("Your answer: ", el("b", {}, r.answer), " · Correct: ", el("b", {}, r.correct));
  $("explanation").textContent = r.explanation;
  const dc = $("detail-cards"); dc.replaceChildren();
  if (r.detail.cards) dc.replaceChildren(...r.detail.cards.map(renderCard));
  else if (r.detail.outs) dc.replaceChildren(...r.detail.outs.map(renderCard));
  renderTips($("tips"), r.tips);
  $("r-board").replaceChildren(...s.board.map(renderCard));
  $("r-hero").replaceChildren(...s.hero_cards.map(renderCard));
  refreshScore();
}

document.addEventListener("keydown", (e) => {
  if (!$("result-screen").hidden && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); nextSpot(); return; }
  if (!$("drill-screen").hidden && /^[1-4]$/.test(e.key)) {
    const btn = document.querySelectorAll("#options button")[Number(e.key) - 1];
    if (btn) btn.click();
  }
});

$("filters-btn").addEventListener("click", () => { renderFilters(); show("filters-screen"); });
$("start-btn").addEventListener("click", () => { saveJSON(FILTER_KEY, filters); nextSpot(); });
$("next-btn").addEventListener("click", nextSpot);

(async function init() {
  try {
    options = await api("/api/basics/options");
    await refreshScore();
  } catch (e) {
    showMessage("Can't reach the trainer server: " + e.message);
    return;
  }
  const saved = loadJSON(FILTER_KEY);
  if (saved) {
    filters.questions = (saved.questions || []).filter((q) => options.questions.some((o) => o.id === q));
    filters.games = (saved.games || []).filter((g) => options.games.some((o) => o.id === g));
  }
  nextSpot();
})();
