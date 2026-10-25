// Omaha nut-awareness drill. Shared helpers are in common.js.
"use strict";

const FILTER_KEY = "pokerguru.nutsFilters";
const SCORE_DRILL = "plo_nut_hand";
const GRADE_WORDS = { correct: "Correct", wrong: "Wrong" };

let options = null;
let filters = { streets: [] };
let current = null;
let chosen = { nut: null, has: null, draw: null };
let shownAt = 0;
let busy = false;

function renderFilters() {
  const s = $("f-street"); s.replaceChildren();
  for (const o of options.streets) {
    s.append(chip(o.label, filters.streets.includes(o.id), () => { toggle(filters.streets, o.id); renderFilters(); }));
  }
}

async function nextSpot() {
  if (busy) return;
  busy = true;
  try {
    current = await api("/api/plo/nuts/next", filters);
    chosen = { nut: null, has: null, draw: null };
    renderSpot(current);
    show("drill-screen");
    shownAt = performance.now();
  } catch (e) {
    showMessage(e.message);
  } finally {
    busy = false;
  }
}

function optionButton(label, onClick) {
  return el("button", { class: "chip option", type: "button", "aria-pressed": "false", onclick: onClick }, label);
}

function renderSpot(s) {
  $("spot-tags").replaceChildren(
    el("span", { class: "tag strong" }, "Pot-Limit Omaha"),
    el("span", { class: "tag" }, s.street[0].toUpperCase() + s.street.slice(1)),
  );
  $("board").replaceChildren(...s.board.map(renderCard));
  $("hero-cards").replaceChildren(...s.hero_cards.map(renderCard));

  const nut = $("nut-options"); nut.replaceChildren();
  for (const label of s.options) {
    nut.append(optionButton(label, (ev) => pick("nut", label, nut, ev.currentTarget)));
  }
  for (const id of ["has-yes", "has-no"]) {
    $(id).setAttribute("aria-pressed", "false");
    $(id).disabled = false;
  }
  $("draw-block").hidden = !s.asks_draw;
  const draw = $("draw-options"); draw.replaceChildren();
  if (s.asks_draw) {
    for (const o of options.draw_options) {
      draw.append(optionButton(o.label, (ev) => pick("draw", o.id, draw, ev.currentTarget)));
    }
  }
  $("submit-btn").disabled = true;
}

function pick(kind, value, group, button) {
  if (busy) return;
  chosen[kind] = value;
  for (const b of group.querySelectorAll(".option")) b.setAttribute("aria-pressed", String(b === button));
  updateSubmit();
}

function pickHas(value) {
  if (busy) return;
  chosen.has = value;
  $("has-yes").setAttribute("aria-pressed", String(value === true));
  $("has-no").setAttribute("aria-pressed", String(value === false));
  updateSubmit();
}

function updateSubmit() {
  const needDraw = current && current.asks_draw;
  $("submit-btn").disabled = !(chosen.nut && chosen.has !== null && (!needDraw || chosen.draw));
}

async function submit() {
  if (busy) return;
  busy = true;
  const elapsed = Math.round(performance.now() - shownAt);
  for (const b of document.querySelectorAll("#drill-screen button")) b.disabled = true;
  try {
    const r = await api("/api/plo/nuts/answer", {
      street: current.street, hero_cards: current.hero_cards, board: current.board,
      nut_choice: chosen.nut, has_nuts: chosen.has, draw_choice: current.asks_draw ? chosen.draw : null,
      response_time_ms: elapsed,
    });
    renderResult(current, r);
    show("result-screen");
  } catch (e) {
    showMessage(e.message);
  } finally {
    busy = false;
  }
}

function gradeRow(title, grade, yours, correct) {
  const row = el("div", { class: `grade-row ${grade}` },
    el("div", { class: "gr-title" }, title),
    el("div", { class: "gr-grade" }, GRADE_WORDS[grade] || grade));
  if (grade !== "correct") row.append(el("div", { class: "gr-detail" }, `You said: ${yours}. Answer: ${correct}.`));
  else row.append(el("div", { class: "gr-detail" }, correct));
  return row;
}

function renderResult(s, r) {
  updateScore(r.summary);
  const g = $("grades"); g.replaceChildren();
  g.append(gradeRow("1. The nuts", r.nut_hand.grade, r.nut_hand.chosen, r.nut_hand.correct));
  const yn = (v) => (v ? "Yes" : "No");
  g.append(gradeRow("2. Do you have it?", r.has_nuts.grade, yn(r.has_nuts.chosen), yn(r.has_nuts.correct)));
  if (r.draw) {
    g.append(gradeRow("3. Your draw", r.draw.grade, r.draw.chosen_label, r.draw.correct_label));
  }
  $("explanation").textContent = r.explanation;
  renderTips($("tips"), r.tips);
  $("r-board").replaceChildren(...s.board.map(renderCard));
  $("r-hero").replaceChildren(...s.hero_cards.map(renderCard));
}

document.addEventListener("keydown", (e) => {
  if (!$("result-screen").hidden && (e.key === "Enter" || e.key === " ")) {
    e.preventDefault();
    nextSpot();
  }
});

$("has-yes").addEventListener("click", () => pickHas(true));
$("has-no").addEventListener("click", () => pickHas(false));
$("submit-btn").addEventListener("click", submit);
$("filters-btn").addEventListener("click", () => { renderFilters(); show("filters-screen"); });
$("start-btn").addEventListener("click", () => { saveJSON(FILTER_KEY, filters); nextSpot(); });
$("next-btn").addEventListener("click", nextSpot);

(async function init() {
  try {
    options = await api("/api/plo/nuts/options");
    updateScore(await api(`/api/summary?drill_type=${SCORE_DRILL}`));
  } catch (e) {
    showMessage("Can't reach the trainer server: " + e.message);
    return;
  }
  const saved = loadJSON(FILTER_KEY);
  if (saved) filters.streets = (saved.streets || []).filter((s) => options.streets.some((o) => o.id === s));
  nextSpot();
})();
